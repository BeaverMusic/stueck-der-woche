"""Lädt bei Bedarf einen unsichtbaren Chromium („chrome-headless-shell“) für
den PDF-Export herunter. Quelle: Googles offizielle „Chrome for Testing“-Downloads.

Im Terminal:  python3 -m app.chromium
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from . import storage

INDEX_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)
EXE_NAME = "chrome-headless-shell"


def base_dir() -> Path:
    return storage.config_dir() / "chromium"


def platform_name() -> str:
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        return "mac-arm64" if machine in ("arm64", "aarch64") else "mac-x64"
    if sys.platform.startswith("linux") and machine in ("x86_64", "amd64"):
        return "linux64"
    raise RuntimeError(
        f"Für dieses System ({sys.platform}, {machine}) gibt es keinen fertigen Download."
    )


def installed() -> str | None:
    """Pfad zum heruntergeladenen Chromium oder None."""
    base = base_dir()
    if not base.is_dir():
        return None
    for exe in sorted(base.glob(f"*/{EXE_NAME}-*/{EXE_NAME}"), reverse=True):
        if os.access(exe, os.X_OK):
            return str(exe)
    return None


# ------------------------------------------------------------------ Anzeige


def _bar(done: int, total: int, started: float) -> None:
    width = 30
    if total:
        part = min(done / total, 1)
        filled = int(part * width)
        bar = "█" * filled + "░" * (width - filled)
        speed = done / max(time.time() - started, 0.1) / 1e6
        text = f"\r  [{bar}] {part * 100:5.1f} %  {done / 1e6:5.1f} von {total / 1e6:.0f} MB  ({speed:.1f} MB/s) "
    else:
        text = f"\r  {done / 1e6:5.1f} MB geladen "
    sys.stdout.write(text)
    sys.stdout.flush()


# ------------------------------------------------------------------ Download


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "StueckDerWoche/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _download(url: str, target: Path, show: bool) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "StueckDerWoche/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(target, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done, started, last = 0, time.time(), 0.0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if show and time.time() - last > 0.1:
                _bar(done, total, started)
                last = time.time()
        if show:
            _bar(done, total, started)
            print()


def _extract(zip_path: Path, dest: Path) -> None:
    """Entpackt mit Rechten und Verknüpfungen (wichtig unter macOS)."""
    if shutil.which("unzip"):
        subprocess.run(["unzip", "-q", "-o", str(zip_path), "-d", str(dest)], check=True)
        return
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            path = (dest / info.filename).resolve()
            if dest.resolve() not in path.parents and path != dest.resolve():
                raise RuntimeError("Ungültiger Eintrag im Archiv")
            mode = info.external_attr >> 16
            if info.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            elif stat.S_ISLNK(mode):
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.is_symlink() or path.exists():
                    path.unlink()
                os.symlink(zf.read(info).decode(), path)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(path, "wb") as out:
                    shutil.copyfileobj(src, out)
                if mode & 0o777:
                    os.chmod(path, mode & 0o777)


_lock = __import__("threading").Lock()


def download(show: bool = True) -> str:
    if not _lock.acquire(blocking=False):
        raise RuntimeError("Chromium wird bereits geladen – bitte warten.")
    try:
        return _download_locked(show)
    finally:
        _lock.release()


def _download_locked(show: bool) -> str:
    plat = platform_name()
    if show:
        print("  Suche aktuelle Version …")
    index = _fetch_json(INDEX_URL)
    stable = index["channels"]["Stable"]
    version = stable["version"]
    entry = next(
        (d for d in stable["downloads"].get(EXE_NAME, []) if d.get("platform") == plat), None
    )
    if not entry:
        raise RuntimeError(f"Kein Download für {plat} gefunden.")
    # Nur Googles offiziellen Download-Speicher akzeptieren
    if not str(entry.get("url", "")).startswith("https://storage.googleapis.com/chrome-for-testing-public/"):
        raise RuntimeError("Unerwartete Download-Adresse – Abbruch.")

    dest = base_dir() / version
    exe = dest / f"{EXE_NAME}-{plat}" / EXE_NAME
    if exe.is_file():
        if show:
            print(f"  Version {version} ist bereits vorhanden.")
        return str(exe)

    if show:
        print(f"  Lade Chromium {version} ({plat}) …")
    base_dir().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base_dir()) as tmp:
        zip_path = Path(tmp) / "chromium.zip"
        _download(entry["url"], zip_path, show)
        if show:
            print("  Entpacke …")
        unpack = Path(tmp) / "unpack"
        unpack.mkdir()
        _extract(zip_path, unpack)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(unpack), str(dest))

    if not exe.is_file():
        raise RuntimeError("Das Archiv hatte nicht den erwarteten Inhalt.")
    exe.chmod(exe.stat().st_mode | 0o111)

    # ältere Versionen entfernen
    for old in base_dir().iterdir():
        if old.is_dir() and old != dest:
            shutil.rmtree(old, ignore_errors=True)
    return str(exe)


if __name__ == "__main__":
    try:
        path = download(show=True)
        print(f"  Fertig: {path}")
    except Exception as exc:
        print(f"\n  Download fehlgeschlagen: {exc}")
        sys.exit(1)
