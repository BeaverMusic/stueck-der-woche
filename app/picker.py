"""Ordnerauswahl mit dem Dialog des Betriebssystems (Finder bzw. Linux-Dateimanager).

macOS: AppleScript („choose folder“) – kein Zusatzprogramm nötig.
Linux: kdialog (KDE), zenity (GNOME/GTK), yad – oder notfalls Tkinter.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 15 * 60  # so lange darf man sich mit der Auswahl Zeit lassen


class PickerError(RuntimeError):
    pass


def _start_dir(start: str) -> str:
    """Vorhandenen Ordner zum Starten finden (notfalls den nächsthöheren)."""
    p = Path(start).expanduser() if start else Path.home()
    while not p.is_dir() and p != p.parent:
        p = p.parent
    return str(p if p.is_dir() else Path.home())


def _run(cmd: list[str]) -> str | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:  # abgebrochen
        return None
    out = proc.stdout.strip()
    return out or None


def _mac(title: str, start: str) -> str | None:
    # Titel und Startordner gehen als Argumente hinein – nichts wird in den
    # AppleScript-Text eingesetzt, also keine Probleme mit Anführungszeichen.
    script = [
        "on run argv",
        "activate",
        "set p to POSIX path of (choose folder with prompt (item 1 of argv) "
        "default location (POSIX file (item 2 of argv)))",
        "return p",
        "end run",
    ]
    cmd = ["osascript"]
    for line in script:
        cmd += ["-e", line]
    return _run(cmd + [title, start])


_TK = r"""
import sys, tkinter
from tkinter import filedialog
root = tkinter.Tk(); root.withdraw()
try:
    root.attributes("-topmost", True)
except Exception:
    pass
path = filedialog.askdirectory(title=sys.argv[1], initialdir=sys.argv[2], mustexist=False)
print(path or "")
"""


def _linux(title: str, start: str) -> str | None:
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP", "") + os.environ.get("DESKTOP_SESSION", "")).lower()
    tools = []
    kde = [("kdialog", ["kdialog", "--title", title, "--getexistingdirectory", start])]
    gtk = [
        ("zenity", ["zenity", "--file-selection", "--directory", "--title", title, "--filename", start + "/"]),
        ("yad", ["yad", "--file", "--directory", "--title", title, "--filename", start + "/"]),
    ]
    tools = kde + gtk if "kde" in desktop or "plasma" in desktop else gtk + kde
    for name, cmd in tools:
        if shutil.which(name):
            return _run(cmd)
    # Notfalls Tkinter (gehört bei vielen Python-Installationen dazu)
    try:
        import tkinter  # noqa: F401
    except Exception:
        raise PickerError(
            "Kein Auswahlfenster verfügbar. Bitte den Pfad eintippen – oder „kdialog“ bzw. „zenity“ installieren."
        )
    try:
        proc = subprocess.run([sys.executable, "-c", _TK, title, start], capture_output=True, text=True,
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        raise PickerError("Das Auswahlfenster ließ sich nicht öffnen. Bitte den Pfad eintippen – "
                          "oder „kdialog“ bzw. „zenity“ installieren.")
    return proc.stdout.strip() or None


def pick_folder(title: str, start: str = "") -> str | None:
    """Öffnet den Ordnerdialog. Gibt den Pfad zurück oder None bei „Abbrechen“."""
    start = _start_dir(start)
    title = (title or "Ordner wählen")[:120]
    path = _mac(title, start) if sys.platform == "darwin" else _linux(title, start)
    if not path:
        return None
    path = path.rstrip("/") or "/"
    if not Path(path).is_dir():
        raise PickerError("Der gewählte Ordner ist nicht vorhanden.")
    return path
