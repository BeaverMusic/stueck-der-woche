"""PDF-Export über den installierten Chromium-Browser (unsichtbar).

Die Druckseite (web/print.html) nutzt dieselbe Blattvorlage wie die
Vorschau im Editor. Dadurch sieht das PDF genau wie die Vorschau aus.
"""

from __future__ import annotations

import threading
from pathlib import Path
from urllib.parse import quote

from . import browser, chromium, storage, zugang

_lock = threading.Lock()

SUFFIX = {"a5": "A5", "a4": "A4-Druck"}
SIZE_MM = {"a5": (148, 210), "a4": (297, 210)}


def export(base_url: str, mode: str, ids: list[str], overwrite: str = "ask") -> dict:
    """Erstellt das PDF. Gibt es die Datei schon, entscheidet ``overwrite``:
    "ask" = nichts tun und nachfragen lassen, "replace" = ersetzen, "new" = neuer Name."""
    if mode not in SUFFIX:
        raise ValueError("Unbekanntes Format")
    if mode == "a5":
        ids = ids[:1]
    elif len(ids) == 1:
        ids = ids * 2  # dasselbe Blatt zweimal nebeneinander
    ids = ids[:2]
    if not ids:
        raise ValueError("Kein Blatt ausgewählt")

    names = []
    for sheet_id in dict.fromkeys(ids):
        s = storage.load_sheet(sheet_id)  # prüft auch, ob es das Blatt gibt
        names.append(storage.slugify(s.get("short_title") or s.get("title")))
    stem = f"{'_'.join(names)}_{SUFFIX[mode]}"
    folder = storage.export_dir()
    target = folder / f"{stem}.pdf"
    if target.exists():
        if overwrite == "new":
            n = 2
            while (folder / f"{stem}_{n}.pdf").exists():
                n += 1
            target = folder / f"{stem}_{n}.pdf"
        elif overwrite != "replace":
            return {"exists": True, "name": target.name}

    url = f"{base_url}/print.html?mode={mode}&ids={quote(','.join(ids))}"
    with _lock:
        # Der unsichtbare Browser weist sich mit dem Zugangsschlüssel aus (als Kopfzeile,
        # nicht in der Adresse – die wäre in der Prozessliste sichtbar).
        browser.print_pdf(url, target, *SIZE_MM[mode], headers={"X-App-Key": zugang.current_key()})
    return {"path": str(target), "name": target.name}


def refresh_chromium() -> str:
    """Lädt den aktuellen Chromium für den PDF-Export; alte Versionen werden erst
    entfernt, wenn gerade kein PDF entsteht."""
    exe = chromium.download(show=False, cleanup=False)
    with _lock:
        chromium.cleanup_old(exe)
    return exe
