"""PDF-Export über den installierten Chromium-Browser (unsichtbar).

Die Druckseite (web/print.html) nutzt dieselbe Blattvorlage wie die
Vorschau im Editor. Dadurch sieht das PDF genau wie die Vorschau aus.
"""

from __future__ import annotations

import threading
from pathlib import Path
from urllib.parse import quote

from . import browser, storage

_lock = threading.Lock()

SUFFIX = {"a5": "A5", "a4": "A4-Druck"}
SIZE_MM = {"a5": (148, 210), "a4": (297, 210)}


def export(base_url: str, mode: str, ids: list[str]) -> Path:
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
    target = storage.export_dir() / f"{'_'.join(names)}_{SUFFIX[mode]}.pdf"

    url = f"{base_url}/print.html?mode={mode}&ids={quote(','.join(ids))}"
    with _lock:
        browser.print_pdf(url, target, *SIZE_MM[mode])
    return target
