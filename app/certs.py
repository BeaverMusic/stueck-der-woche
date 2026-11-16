"""Sicherheitszertifikate für Internetverbindungen.

Das Python von python.org bringt unter macOS keine Zertifikate mit
(Fehler „CERTIFICATE_VERIFY_FAILED“). Statt etwas nachzuinstallieren, nutzt die
App dann die Zertifikate, die macOS ohnehin in seinen Schlüsselbunden hat:
Sie werden einmal in eine Datei geschrieben und Python darüber bekannt gemacht.
"""

from __future__ import annotations

import os
import ssl
import subprocess
import sys
import time
from pathlib import Path

KEYCHAINS = [
    "/System/Library/Keychains/SystemRootCertificates.keychain",
    "/Library/Keychains/System.keychain",  # z. B. vom Schulnetz installierte Zertifikate
]
REFRESH_DAYS = 30
CACERT_URL = "https://curl.se/ca/cacert.pem"


def _python_has_certs() -> bool:
    paths = ssl.get_default_verify_paths()
    if paths.cafile and Path(paths.cafile).is_file():
        return True
    if paths.capath and Path(paths.capath).is_dir():
        try:
            return any(Path(paths.capath).iterdir())
        except OSError:
            return False
    return False


def _from_certifi() -> str | None:
    try:
        import certifi  # falls „Install Certificates.command“ schon ausgeführt wurde
        path = certifi.where()
        return path if Path(path).is_file() else None
    except Exception:
        return None


def _from_keychains(target: Path) -> str | None:
    pems = []
    for keychain in KEYCHAINS:
        if not Path(keychain).exists():
            continue
        try:
            out = subprocess.run(["/usr/bin/security", "find-certificate", "-a", "-p", keychain],
                                 capture_output=True, text=True, timeout=30).stdout
        except Exception:
            continue
        if "BEGIN CERTIFICATE" in out:
            pems.append(out.strip())
    if not pems:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text("\n".join(pems) + "\n", "utf-8")
    tmp.replace(target)
    return str(target)


def _windows(config_dir: Path) -> None:
    """Windows: zusätzlich zum Zertifikatspeicher von Windows der Mozilla-Liste
    (cacert.pem) vertrauen. Windows lädt fehlende Stammzertifikate nur für eigene
    Programme nach – Python sieht sie dann nicht (z. B. bei accounts.spotify.com)."""
    path = config_dir / "cacert.pem"
    if not path.exists():
        return

    def context(purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None):
        ctx = ssl.create_default_context(purpose, cafile=cafile, capath=capath, cadata=cadata)
        if not (cafile or capath or cadata):
            ctx.load_verify_locations(cafile=str(path))
        return ctx

    ssl._create_default_https_context = context
    try:  # urllib merkt sich seine Einstellungen nach der ersten Verbindung
        import urllib.request
        urllib.request._opener = None
    except Exception:
        pass


def refresh_windows(config_dir: Path) -> bool:
    """Windows: Lädt die Mozilla-Liste neu, wenn sie fehlt oder älter als REFRESH_DAYS
    Tage ist. Gibt True zurück, wenn eine neue Liste geladen wurde."""
    if sys.platform != "win32":
        return False
    target = config_dir / "cacert.pem"
    if target.is_file() and time.time() - target.stat().st_mtime < REFRESH_DAYS * 86400:
        return False  # noch frisch genug
    import urllib.request
    with urllib.request.urlopen(CACERT_URL, timeout=30) as resp:
        data = resp.read(2_000_000)
    if data.count(b"BEGIN CERTIFICATE") < 100:
        raise RuntimeError("Die heruntergeladene Zertifikatsliste sieht nicht richtig aus.")
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    _windows(config_dir)  # neue Liste sofort benutzen
    return True


def install(config_dir: Path) -> None:
    """Sorgt dafür, dass Python Zertifikate findet (nur nötig, wenn keine da sind)."""
    if sys.platform == "win32" and not os.environ.get("SSL_CERT_FILE"):
        _windows(config_dir)
        return
    if sys.platform != "darwin" or os.environ.get("SSL_CERT_FILE") or _python_has_certs():
        return
    path = _from_certifi()
    if not path:
        target = config_dir / "zertifikate.pem"
        fresh = target.is_file() and time.time() - target.stat().st_mtime < REFRESH_DAYS * 86400
        path = str(target) if fresh else _from_keychains(target)
    if path:
        use(path)


def use(path: str) -> None:
    """Alle HTTPS-Verbindungen dieses Programms prüfen gegen diese Zertifikate."""
    os.environ["SSL_CERT_FILE"] = path  # auch für Hilfsprozesse

    def context(purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None):
        return ssl.create_default_context(purpose, cafile=cafile or path, capath=capath, cadata=cadata)

    ssl._create_default_https_context = context
    try:  # urllib merkt sich seine Einstellungen nach der ersten Verbindung
        import urllib.request
        urllib.request._opener = None
    except Exception:
        pass
