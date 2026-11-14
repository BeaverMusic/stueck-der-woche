"""Zugriffsschutz: Nur das eigene App-Fenster darf mit der App sprechen.

Die App ist ein kleiner Webserver auf dem eigenen Rechner. Ohne Schutz könnte
jedes andere Programm und jeder andere angemeldete Benutzer desselben Rechners
ihre Adresse aufrufen und z. B. die API-Schlüssel lesen. Deshalb:

- Bei jedem Start erzeugt die App einen langen Zufallsschlüssel.
- Er steht in zwei Dateien im Einstellungsordner, die nur der eigene Benutzer
  lesen darf: ``zugang`` (der Schlüssel) und ``start.html`` (eine Startseite, die
  das Fenster zur App schickt und ihm den Schlüssel mitgibt).
- Das Fenster merkt sich den Schlüssel und schickt ihn bei jeder Anfrage mit.
  Anfragen ohne ihn werden abgelehnt.

Der Schlüssel taucht nie in einer Befehlszeile auf (die könnten andere Benutzer
in der Prozessliste sehen) – darum der Umweg über die Startdatei.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from pathlib import Path

from . import storage

KEY_RE = re.compile(r"[A-Za-z0-9_-]{30,100}")
TICKET_SECONDS = 120

_state = {"key": "", "tickets": {}}
_lock = threading.Lock()


def key_file() -> Path:
    return storage.config_dir() / "zugang"


def start_file() -> Path:
    return storage.config_dir() / "start.html"


def _write_private(path: Path, text: str) -> None:
    storage._private_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def stored_key() -> str:
    """Schlüssel der zuletzt gestarteten App (leer, wenn es keinen gibt)."""
    try:
        key = key_file().read_text("utf-8").strip()
    except OSError:
        return ""
    return key if KEY_RE.fullmatch(key) else ""


def prepare(keep: bool = False) -> str:
    """Schlüssel festlegen, noch bevor der Server Anfragen annimmt. ``keep`` behält den
    bisherigen – nach einem Update oder Absturz, damit das schon offene Fenster
    weiterarbeiten kann. Sonst gibt es bei jedem Start einen neuen."""
    key = (stored_key() if keep else "") or secrets.token_urlsafe(32)
    with _lock:
        _state["key"] = key
        _state["tickets"].clear()
    return key


def publish(url: str) -> None:
    """Schlüssel und Startdatei schreiben (wenn die Adresse des Servers feststeht)."""
    key = _state["key"]
    _write_private(key_file(), key + "\n")
    target = f"{url}#k={key}"
    _write_private(start_file(), (
        '<!doctype html>\n<html lang="de"><head><meta charset="utf-8">'
        "<title>Stück der Woche</title>\n"
        f'<meta http-equiv="refresh" content="0;url={target}"></head>\n'
        '<body style="font-family:system-ui,sans-serif;margin:3em">'
        f'<p>Stück der Woche wird geöffnet … <a href="{target}">Weiter</a></p></body></html>\n'
    ))


def activate(url: str, keep: bool = False) -> str:
    key = prepare(keep)
    publish(url)
    return key


def deactivate() -> None:
    """Beim Beenden: Die Startdatei führt sonst ins Leere."""
    try:
        start_file().unlink()
    except OSError:
        pass


def current_key() -> str:
    return _state["key"]


def check(candidate: str) -> bool:
    key = _state["key"]
    return bool(key) and hmac.compare_digest(key.encode(), str(candidate or "").encode())


def asset_key() -> str:
    """Abgeleiteter Schlüssel nur für Bilder (steht in Bildadressen, öffnet sonst nichts)."""
    return hashlib.sha256((_state["key"] + ":bild").encode()).hexdigest()[:40]


def check_asset(candidate: str) -> bool:
    return bool(_state["key"]) and hmac.compare_digest(asset_key().encode(), str(candidate or "").encode())


def proof(nonce: str, key: str | None = None) -> str:
    """Nachweis „ich kenne den Schlüssel“, ohne ihn zu verraten. Damit erkennt eine
    zweite gestartete App, ob auf dem Port wirklich die eigene App läuft."""
    key = _state["key"] if key is None else key
    if not key:
        return ""
    return hmac.new(key.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def new_ticket() -> str:
    """Einmal-Eintrittskarte (zwei Minuten gültig) – Notlösung, falls ein Browser die
    Startdatei nicht öffnen kann. Sie wird im Fenster gegen den Schlüssel getauscht."""
    ticket = secrets.token_urlsafe(24)
    with _lock:
        _state["tickets"][ticket] = time.time() + TICKET_SECONDS
    return ticket


def redeem(ticket: str) -> str:
    with _lock:
        expires = _state["tickets"].pop(str(ticket or ""), 0)
    return _state["key"] if expires and time.time() < expires else ""
