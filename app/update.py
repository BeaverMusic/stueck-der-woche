"""Updates über GitHub: neue Version finden, sicher herunterladen und einspielen.

Ablauf
------
1. ``check()`` fragt bei GitHub nach der neuesten Veröffentlichung („Release“)
   des Repositorys und vergleicht deren Versionsnummer mit der laufenden.
2. ``install()`` lädt die Programm-ZIP dieser Veröffentlichung, prüft sie gegen
   die mitveröffentlichte Prüfsumme (SHA-256), entpackt sie in einen
   Zwischenordner und tauscht dann den Programmordner in einem Schritt aus.
   Blätter, Einstellungen und Schlüssel liegen woanders und bleiben unberührt.
3. ``restart()`` startet die neue Version; sie übernimmt wie bei jedem Start
   von einer älteren Version (siehe stueck_der_woche.py).

Aktualisiert werden nur Installationen, deren Programm in einem Ordner namens
„programm“ liegt (Mac-App bzw. install.sh unter Linux). Ein pacman-Paket wird
über makepkg aktualisiert.
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import VERSION, storage

# GitHub-Repository („Konto/Name“). Leer = Update-Funktion aus.
REPO = "BeaverMusic/stueck-der-woche"

APP_DIR = Path(__file__).resolve().parent.parent  # …/programm
ALLOWED_HOSTS = {"api.github.com", "github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com", "codeload.github.com"}
CHECK_EVERY = 6 * 3600
MAX_DOWNLOAD = 50 * 1024 * 1024
_state = {"checked": 0.0, "result": None}
_lock = threading.Lock()


class UpdateError(RuntimeError):
    pass


def repo() -> str:
    custom = storage.load_settings().get("update_repo", "").strip()
    name = custom or REPO
    return name if re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", name or "") else ""


def parse_version(text: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", text or "")[:4]) or (0,)


def _get(url: str, limit: int = MAX_DOWNLOAD, accept: str = "application/vnd.github+json") -> bytes:
    host = urllib.parse.urlsplit(url).hostname or ""
    if urllib.parse.urlsplit(url).scheme != "https" or host not in ALLOWED_HOSTS:
        raise UpdateError(f"Unerwartete Download-Adresse ({host}) – abgebrochen.")
    req = urllib.request.Request(url, headers={"User-Agent": f"StueckDerWoche/{VERSION}", "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            final = urllib.parse.urlsplit(resp.geturl()).hostname or ""
            if final not in ALLOWED_HOSTS:
                raise UpdateError(f"Weiterleitung zu unerwarteter Adresse ({final}) – abgebrochen.")
            data = resp.read(limit + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("Auf GitHub gibt es noch keine veröffentlichte Version.")
        if exc.code == 403:
            raise UpdateError("GitHub lässt gerade keine weiteren Anfragen zu – später erneut versuchen.")
        raise UpdateError(f"GitHub meldet einen Fehler (HTTP {exc.code}).")
    except urllib.error.URLError as exc:
        raise UpdateError(f"GitHub ist nicht erreichbar ({exc.reason}).")
    if len(data) > limit:
        raise UpdateError("Die Datei ist unerwartet groß – abgebrochen.")
    return data


def install_kind() -> str:
    """mac (in der App), linux (install.sh), paket (pacman) oder ordner (entpackter Download)."""
    if APP_DIR.name == "programm" and APP_DIR.parent.name == "Resources" and APP_DIR.parent.parent.name == "Contents":
        return "mac"
    if APP_DIR.name == "programm":
        return "linux"
    if str(APP_DIR).startswith("/opt/"):
        return "paket"
    return "ordner"


def check(force: bool = False) -> dict:
    """Neueste Version auf GitHub. Wird höchstens alle paar Stunden wirklich abgefragt."""
    name = repo()
    base = {"current": VERSION, "repo": name, "kind": install_kind(), "available": False}
    if not name:
        return {**base, "message": "Updates sind noch nicht eingerichtet."}
    with _lock:
        if not force and _state["result"] and time.time() - _state["checked"] < CHECK_EVERY \
                and _state["result"].get("repo") == name:
            return _state["result"]
        release = json.loads(_get(f"https://api.github.com/repos/{name}/releases/latest"))
        tag = str(release.get("tag_name", ""))
        assets = {a.get("name"): a.get("browser_download_url") for a in release.get("assets", [])}
        latest = tag.lstrip("vV")
        zip_name = f"stueck-der-woche-{latest}.zip"
        result = {
            **base,
            "latest": latest,
            "available": parse_version(latest) > parse_version(VERSION),
            "notes": str(release.get("body") or "")[:4000],
            "page": release.get("html_url", ""),
            "zip": assets.get(zip_name, ""),
            "sums": assets.get("SHA256SUMS.txt", ""),
            "dmg": next((u for n, u in assets.items() if n and n.endswith(".dmg")), ""),
            "zip_name": zip_name,
        }
        _state.update(checked=time.time(), result=result)
        return result


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    root = dest.resolve()
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if root not in target.parents and target != root:
            raise UpdateError("Ungültiger Eintrag im Update – abgebrochen.")
        mode = info.external_attr >> 16
        if (mode & 0o170000) == 0o120000:
            raise UpdateError("Das Update enthält eine Verknüpfung – abgebrochen.")
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
        os.chmod(target, 0o755 if mode & 0o111 else 0o644)


def install() -> dict:
    info = check(force=True)
    kind = info["kind"]
    if not info["available"]:
        raise UpdateError(f"Version {VERSION} ist bereits aktuell.")
    if kind == "paket":
        raise UpdateError("Diese Installation stammt aus dem pacman-Paket. Bitte die neue Version herunterladen "
                          "und in paket/arch „makepkg -si“ ausführen.")
    if kind == "ordner":
        raise UpdateError("Die App läuft direkt aus dem heruntergeladenen Ordner. Bitte die neue Version "
                          "herunterladen und installieren.")
    if not info["zip"] or not info["sums"]:
        raise UpdateError("Zu dieser Version fehlen die Update-Dateien auf GitHub.")
    if not os.access(APP_DIR.parent, os.W_OK):
        raise UpdateError("Keine Schreibrechte für den Programmordner – bitte neu installieren.")

    data = _get(info["zip"], accept="application/octet-stream")
    sums = _get(info["sums"], limit=100_000, accept="application/octet-stream").decode("utf-8", "replace")
    expected = next((line.split()[0].lower() for line in sums.splitlines()
                     if line.strip().endswith(info["zip_name"])), "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or hashlib.sha256(data).hexdigest() != expected:
        raise UpdateError("Die Prüfsumme des Updates stimmt nicht – es wurde nichts verändert.")

    parent = APP_DIR.parent
    with tempfile.TemporaryDirectory(dir=parent, prefix=".update-") as tmp:
        tmp = Path(tmp)
        zpath = tmp / "update.zip"
        zpath.write_bytes(data)
        with zipfile.ZipFile(zpath) as zf:
            _safe_extract(zf, tmp / "inhalt")
        src = tmp / "inhalt" / "stueck-der-woche"
        init = src / "app" / "__init__.py"
        if not init.is_file():
            raise UpdateError("Das Update ist unvollständig – es wurde nichts verändert.")
        m = re.search(r'VERSION\s*=\s*"([^"]+)"', init.read_text("utf-8"))
        if not m or m.group(1) != info["latest"]:
            raise UpdateError("Die Versionsnummer im Update passt nicht – es wurde nichts verändert.")

        new = tmp / "programm"
        new.mkdir()
        for item in ("app", "web"):
            shutil.copytree(src / item, new / item)
        for item in ("stueck_der_woche.py", "LIESMICH.md", "deinstallieren.sh", "LICENSE"):
            if (src / item).exists():
                shutil.copy2(src / item, new / item)
        # Austausch: alter Ordner beiseite, neuer an seine Stelle, alter weg
        old = tmp / "alt"
        APP_DIR.rename(old)
        try:
            new.rename(APP_DIR)
        except Exception:
            old.rename(APP_DIR)
            raise
        if kind == "mac":
            _update_mac_bundle(src, info["latest"])
    # Erst jetzt (Zwischenordner ist weg) eine frühere Signatur entfernen
    if kind == "mac":
        _remove_signature(APP_DIR.parent.parent.parent)
    storage.log("Update", f"Version {VERSION} → {info['latest']} installiert")
    return {"version": info["latest"]}


def _update_mac_bundle(src: Path, version: str) -> None:
    """Startprogramm und Versionsangabe der Mac-App mitziehen."""
    contents = APP_DIR.parent.parent
    launcher = src / "paket" / "mac" / "StueckDerWoche"
    if launcher.is_file():
        target = contents / "MacOS" / "StueckDerWoche"
        shutil.copy2(launcher, target)
        target.chmod(0o755)
    plist = contents / "Info.plist"
    try:
        info = plistlib.loads(plist.read_bytes())
        nums = ([int(x) for x in re.findall(r"\d+", version)] + [0, 0, 0, 0])[:4]
        info["CFBundleShortVersionString"] = version
        info["CFBundleVersion"] = f"{nums[0]}.{nums[1]}.{nums[2] * 1000 + nums[3]}"  # wie build_dmg.bundle_version
        plist.write_bytes(plistlib.dumps(info))
    except Exception:
        pass


def _remove_signature(app: Path) -> None:
    """Die App wird nicht signiert: Eine lokale Signatur passt nach jedem Update nicht mehr
    zum Inhalt und kann den Start verhindern. Eine Signatur früherer Versionen entfernen."""
    sig = app / "Contents" / "_CodeSignature"
    if not sig.exists():
        return
    try:
        if shutil.which("codesign"):
            subprocess.run(["codesign", "--remove-signature", str(app)], capture_output=True, timeout=60)
    except Exception:
        pass
    shutil.rmtree(sig, ignore_errors=True)


def restart(own_window: bool) -> None:
    """Neue Version starten; sie beendet die laufende und übernimmt."""
    args = [sys.executable, str(APP_DIR / "stueck_der_woche.py")]
    if not own_window:
        args.append("--kein-fenster")  # die offene Browser-Seite lädt sich selbst neu
    log = storage.config_dir() / "ausgabe.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as out:
        subprocess.Popen(args, cwd=str(APP_DIR), stdout=out, stderr=out, stdin=subprocess.DEVNULL,
                         start_new_session=True,
                         env={**os.environ, "PYTHONPYCACHEPREFIX": str(storage.config_dir() / "pycache")})
