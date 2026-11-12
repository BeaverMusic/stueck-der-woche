"""App-Fenster und PDF-Export.

Fenster: ein installierter Chromium-Browser (Chrome, Chromium, Edge, Brave,
Vivaldi) als eigenes Fenster ohne Adressleiste – sonst der Standardbrowser.

PDF: der heruntergeladene unsichtbare Chromium (siehe chromium.py) oder,
falls vorhanden, ein installierter Chromium-Browser.
"""

from __future__ import annotations

import base64
import fcntl
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import chromium, storage

MAC_APPS = [
    "Google Chrome.app/Contents/MacOS/Google Chrome",
    "Chromium.app/Contents/MacOS/Chromium",
    "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "Brave Browser.app/Contents/MacOS/Brave Browser",
    "Vivaldi.app/Contents/MacOS/Vivaldi",
]
LINUX_CMDS = [
    "google-chrome-stable", "google-chrome", "chromium", "chromium-browser",
    "brave", "brave-browser", "microsoft-edge-stable", "microsoft-edge",
    "vivaldi-stable", "vivaldi",
]

NO_PDF_ENGINE = (
    "Für den PDF-Export fehlt Chromium. Unter Einstellungen → Allgemein "
    "„Chromium laden“ klicken – oder „Drucken …“ nutzen."
)


def _custom() -> str | None:
    custom = storage.load_settings().get("browser_path", "")
    if custom and Path(custom).expanduser().is_file():
        return str(Path(custom).expanduser())
    return os.environ.get("STUECK_BROWSER") or None


def find_pdf_engine() -> str | None:
    """Für den PDF-Export: eigener Pfad, dann heruntergeladener Chromium,
    dann ein installierter Chromium-Browser."""
    return _custom() or chromium.installed() or find_browser()


def find_browser() -> str | None:
    """Installierter Chromium-Browser für das App-Fenster (oder None)."""
    custom = _custom()
    if custom and chromium.EXE_NAME not in Path(custom).name:
        return custom
    if sys.platform == "darwin":
        for base in ("/Applications", str(Path.home() / "Applications")):
            for app in MAC_APPS:
                p = Path(base) / app
                if p.is_file():
                    return str(p)
        return None
    for cmd in LINUX_CMDS:
        found = shutil.which(cmd)
        if found:
            return found
    return None


def open_app_window(url: str) -> subprocess.Popen | None:
    """Öffnet die App als eigenes Fenster ohne Adressleiste."""
    exe = find_browser()
    if not exe:
        return None
    profile = storage.config_dir() / "fenster-profil"
    profile.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            exe,
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--window-size=1440,920",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # unabhängig vom Terminal-Fenster
    )


class _Pipe:
    """Minimaler Client für das DevTools-Protokoll über --remote-debugging-pipe."""

    def __init__(self, exe: str, profile: str):
        to_child_r, self._w = os.pipe()
        self._r, from_child_w = os.pipe()

        def setup_fds():  # im Kindprozess: Pipes auf fd 3 (lesen) und 4 (schreiben)
            a = fcntl.fcntl(to_child_r, fcntl.F_DUPFD, 10)
            b = fcntl.fcntl(from_child_w, fcntl.F_DUPFD, 10)
            os.dup2(a, 3)
            os.dup2(b, 4)

        args = [
            exe,
            "--remote-debugging-pipe",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-component-update",
            "--mute-audio",
            "about:blank",
        ]
        if chromium.EXE_NAME not in Path(exe).name:
            args.insert(1, "--headless=new")  # normaler Browser: unsichtbar starten
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            args.insert(1, "--no-sandbox")  # Chrome verweigert sonst den Start als root
        self.proc = subprocess.Popen(
            args, preexec_fn=setup_fds, pass_fds=(3, 4),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.close(to_child_r)
        os.close(from_child_w)
        self._buf = b""
        self._id = 0

    def call(self, method: str, params: dict | None = None, session: str | None = None,
             timeout: float = 30) -> dict:
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        os.write(self._w, json.dumps(msg).encode() + b"\0")
        deadline = time.time() + timeout
        while True:
            while b"\0" in self._buf:
                raw, self._buf = self._buf.split(b"\0", 1)
                reply = json.loads(raw)
                if reply.get("id") == self._id:
                    if "error" in reply:
                        raise RuntimeError(reply["error"].get("message", "DevTools-Fehler"))
                    return reply.get("result", {})
            left = deadline - time.time()
            if left <= 0:
                raise RuntimeError("Der PDF-Export hat zu lange gedauert.")
            ready, _, _ = select.select([self._r], [], [], left)
            if ready:
                chunk = os.read(self._r, 1 << 16)
                if not chunk:
                    raise RuntimeError("Der Browser wurde unerwartet beendet.")
                self._buf += chunk

    def close(self) -> None:
        try:
            self.call("Browser.close", timeout=5)
        except Exception:
            pass
        for fd in (self._r, self._w):
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def print_pdf(url: str, target: Path, width_mm: float, height_mm: float) -> None:
    """Lädt die Seite unsichtbar, wartet bis alles fertig ist, und speichert sie als PDF."""
    exe = find_pdf_engine()
    if not exe:
        raise RuntimeError(NO_PDF_ENGINE)
    with tempfile.TemporaryDirectory(prefix="stueck-pdf-") as profile:
        pipe = _Pipe(exe, profile)
        try:
            target_id = pipe.call("Target.createTarget", {"url": "about:blank"})["targetId"]
            session = pipe.call("Target.attachToTarget",
                                {"targetId": target_id, "flatten": True})["sessionId"]
            pipe.call("Page.navigate", {"url": url}, session)
            deadline = time.time() + 30
            while True:
                res = pipe.call("Runtime.evaluate", {
                    "expression": "window.__printReady === true ? (window.__printError || 'ok') : ''",
                    "returnByValue": True,
                }, session)
                value = res.get("result", {}).get("value") or ""
                if value == "ok":
                    break
                if value:
                    raise RuntimeError(value)
                if time.time() > deadline:
                    raise RuntimeError("Die Druckseite wurde nicht fertig geladen.")
                time.sleep(0.2)
            pdf = pipe.call("Page.printToPDF", {
                "paperWidth": width_mm / 25.4,
                "paperHeight": height_mm / 25.4,
                "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0,
                "printBackground": True,
                "preferCSSPageSize": True,
            }, session, timeout=60)
        finally:
            pipe.close()
    target.write_bytes(base64.b64decode(pdf["data"]))
