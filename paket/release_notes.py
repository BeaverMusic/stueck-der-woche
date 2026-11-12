#!/usr/bin/env python3
"""Gibt die Neuerungen einer Version aus NEUERUNGEN.md aus (für die GitHub-Veröffentlichung
und den Update-Hinweis in der App).   Aufruf:  python3 paket/release_notes.py 6.6"""
import re
import sys
from pathlib import Path

version = sys.argv[1]
text = (Path(__file__).resolve().parent.parent / "NEUERUNGEN.md").read_text("utf-8")
m = re.search(rf"^## {re.escape(version)}\b.*?\n(.*?)(?=^## |\Z)", text, re.S | re.M)
print((m.group(1).strip() if m else f"Version {version}") + "\n\n**Mac:** das .dmg herunterladen und öffnen. "
      "**Linux:** die ZIP-Datei entpacken und `bash install.sh` ausführen. "
      "Bereits installierte Apps bieten das Update selbst an.")
