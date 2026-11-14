"""Stück der Woche – Startdatei.

Startet den lokalen Server und öffnet die App – als eigenes Fenster, wenn
Chrome/Chromium/Edge/Brave installiert ist, sonst im Standardbrowser.
Die App beendet sich von selbst, sobald das Fenster geschlossen wird.

Mit  --browser  öffnet sie sich stattdessen als Tab im Standardbrowser.
"""

import hmac
import json
import plistlib
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from app import VERSION, browser, server, storage, zugang

PORT = 47110  # fester Port, damit Einstellungen im Fenster erhalten bleiben
IDLE_LIMIT = 30 * 60  # so lange ohne Lebenszeichen, dann beendet sich die App
WINDOW_WAIT = 25  # meldet sich das Fenster so lange nicht, folgt ein zweiter Versuch


def keep_running_without_terminal() -> None:
    """Schließen des Terminal-Fensters soll die App nicht beenden. Ausgaben
    gehen danach in eine Datei, damit ein geschlossenes Terminal nicht stört."""
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        path = storage.config_dir() / "ausgabe.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 1_000_000:
            path.unlink()
        out = open(path, "a", encoding="utf-8", buffering=1)
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = sys.stderr = out
    except Exception:
        pass


def running_app(key: str) -> tuple[str | None, bool]:
    """Version einer bereits laufenden App (None, wenn keine läuft) und ob es nachweislich
    die eigene ist: Sie muss beweisen, dass sie den Zugangsschlüssel kennt. Sonst könnte
    ein fremdes Programm auf demselben Port das Fenster – und damit den Schlüssel – abfangen."""
    nonce = secrets.token_urlsafe(18)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping?n={nonce}", timeout=2) as r:
            data = json.load(r)
    except Exception:
        return None, False
    if not isinstance(data, dict) or not data.get("ok"):
        return None, False
    proof = str(data.get("proof") or "")
    ours = bool(key and proof) and hmac.compare_digest(proof.encode(), zugang.proof(nonce, key).encode())
    return str(data.get("version") or "alt"), ours


def ask_old_to_quit(key: str) -> None:
    headers = {"X-App": "1", "Content-Type": "application/json"}
    if key:  # nur an die nachweislich eigene App schicken
        headers["X-App-Key"] = key
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/quit", data=b"{}", method="POST", headers=headers)
    try:
        urllib.request.urlopen(req, timeout=2).read()
    except Exception:
        pass


def open_running(url: str, key: str) -> None:
    """Die App läuft schon: nur ein weiteres Fenster öffnen. Kann der Browser die Startdatei
    nicht lesen (Snap/Flatpak), stellt die laufende App eine Einmal-Eintrittskarte aus."""
    exe = None if "--browser" in sys.argv else browser.find_browser()
    if (exe and _sandboxed(exe)) or (not exe and _default_browser_sandboxed()):
        try:
            req = urllib.request.Request(f"{url}api/ticket", data=b"{}", method="POST", headers={
                "X-App": "1", "X-App-Key": key, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as r:
                target = f"{url}#t={json.load(r)['ticket']}"
        except Exception as exc:
            print(f"Eintrittskarte nicht erhalten ({exc}).")
            return
        if exe and browser.open_app_window(target) is not None:
            return
        open_in_browser(target)
        return
    open_window(url)


def _mac_browser_id() -> str:
    """Kennung des Standardbrowsers auf dem Mac (leer, wenn nicht feststellbar)."""
    try:
        plist = (Path.home() / "Library/Preferences/com.apple.LaunchServices"
                 / "com.apple.launchservices.secure.plist")
        for handler in plistlib.loads(plist.read_bytes()).get("LSHandlers", []):
            if handler.get("LSHandlerURLScheme") == "https":
                return str(handler.get("LSHandlerRoleAll") or "")
    except Exception:
        pass
    return ""


def open_in_browser(target: str) -> None:
    """Öffnet eine Adresse oder die Startdatei im Standardbrowser."""
    is_file = not target.startswith("http")
    if sys.platform == "darwin":
        # Auf dem Mac zuverlässiger als webbrowser (das über AppleScript geht). Die
        # Startdatei gezielt im Standardbrowser öffnen – nicht in dem Programm, das
        # sonst für .html-Dateien zuständig ist.
        attempts = []
        browser_id = _mac_browser_id() if is_file else ""
        if browser_id:
            attempts.append(["/usr/bin/open", "-b", browser_id, target])
        attempts.append(["/usr/bin/open", target])
        for cmd in attempts:
            try:
                subprocess.run(cmd, timeout=15, check=True)
                return
            except Exception as exc:
                print(f"„{' '.join(cmd[:3])} …“ hat nicht geklappt ({exc}) – versuche es anders.")
    webbrowser.open(Path(target).as_uri() if is_file else target)


def _sandboxed(path: str) -> bool:
    """Liegt das Programm in einem abgeschotteten Paket (Snap, Flatpak)? Solche Browser
    dürfen den Einstellungsordner – und damit die Startdatei – nicht lesen."""
    try:
        real = str(Path(path).resolve())
    except OSError:
        return False
    if real.startswith(("/snap/", "/var/lib/snapd/", "/var/lib/flatpak/")) or "/flatpak/" in real \
            or Path(real).name in ("snap", "flatpak"):
        return True
    try:  # kleines Startskript, das an ein Snap- oder Flatpak-Paket weiterreicht (z. B. Ubuntu)
        if Path(real).stat().st_size < 8000:
            head = Path(real).read_bytes()[:8000]
            return head.startswith(b"#!") and (b"/snap/" in head or b"flatpak run" in head)
    except OSError:
        pass
    return False


def _default_browser_sandboxed() -> bool:
    """Linux: Ist der Standardbrowser ein Snap- oder Flatpak-Paket?"""
    if not sys.platform.startswith("linux"):
        return False
    try:
        name = subprocess.run(["xdg-settings", "get", "default-web-browser"], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except Exception:
        return False
    if not name:
        return False
    home = Path.home()
    return any((d / name).exists() for d in (
        Path("/var/lib/snapd/desktop/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        home / ".local/share/flatpak/exports/share/applications",
    ))


def open_window(url: str):
    """Öffnet das App-Fenster über die Startdatei (sie enthält den Zugangsschlüssel und
    ist nur für den eigenen Benutzer lesbar). Kann der Browser die Datei nicht lesen
    (Snap/Flatpak), bekommt er stattdessen eine Einmal-Eintrittskarte in der Adresse."""
    start = zugang.start_file()
    if "--browser" not in sys.argv:
        exe = browser.find_browser()
        if exe:
            target = f"{url}#t={zugang.new_ticket()}" if _sandboxed(exe) else start.as_uri()
            proc = browser.open_app_window(target)
            if proc is not None:
                return proc
        print("Kein Chrome/Chromium-Browser gefunden – öffne die App im Standardbrowser.")
    if _default_browser_sandboxed():
        open_in_browser(f"{url}#t={zugang.new_ticket()}")
    else:
        open_in_browser(str(start))
    return None


def main() -> None:
    storage.secure_config()  # Einstellungen (mit API-Schlüsseln) nur für den eigenen Benutzer
    no_window = "--kein-fenster" in sys.argv
    url = f"http://127.0.0.1:{PORT}/"
    old_key = zugang.stored_key()
    # Gibt es die Startdatei noch, wurde die App zuletzt nicht ordentlich beendet (oder läuft noch).
    leftover = zugang.start_file().exists()
    httpd = None
    replaced = replaced_ours = False

    def keep_key() -> bool:
        """Bleibt der bisherige Zugangsschlüssel gültig? Ja, wenn ein schon offenes Fenster
        weiterarbeiten soll: nach einem Update im Browser-Tab (der Tab lädt sich selbst neu)
        oder wenn die App zuletzt unsanft beendet wurde (ein offenes Fenster kann dann
        nachspeichern). Sonst gibt es bei jedem Start einen neuen Schlüssel."""
        return bool(old_key) and ((no_window and (replaced_ours or not replaced)) or (leftover and not replaced))

    for attempt in range(8):
        try:
            # Der Schlüssel steht fest, bevor der Server die erste Anfrage annimmt – sonst
            # würde ein Fenster, das sich sofort meldet, kurz abgewiesen.
            zugang.prepare(keep=keep_key())
            httpd = server.start(PORT)
            if replaced:
                time.sleep(1.5)  # dem alten Fenster Zeit zum Schließen geben
            break
        except OSError:
            version, ours = running_app(old_key)
            if version == VERSION and ours:
                # Dieselbe Version läuft schon – nur ein weiteres Fenster öffnen.
                if not no_window:
                    open_running(url, old_key)
                return
            if version and attempt == 0:
                if ours or version != VERSION:
                    print(f"Eine andere Version ({version}) läuft noch – sie wird beendet …")
                else:
                    print("Auf dem Anschluss der App antwortet ein Programm, das sich nicht als diese App "
                          "ausweist – es wird gebeten, sich zu beenden …")
                ask_old_to_quit(old_key if ours else "")
                replaced, replaced_ours = True, ours
            time.sleep(1)
    if httpd is None:
        # Port bleibt belegt (z. B. sehr alte Version) – auf freiem Port starten.
        zugang.prepare(keep=False)
        httpd = server.start(0)
        url = "http://127.0.0.1:%d/" % httpd.server_address[1]

    # Nach einem Update startet die neue Version ohne neues Fenster, wenn die App in einem
    # normalen Browser-Tab läuft – der Tab lädt sich dann selbst neu und kennt den bisherigen
    # Schlüssel. Kam das Update von einer Version ohne Zugangsschutz (vor 0.6.9), kennt der
    # Tab keinen Schlüssel: dann doch ein Fenster öffnen.
    kept = bool(old_key) and zugang.current_key() == old_key
    zugang.publish(url)
    want_window = not no_window or not kept
    proc = open_window(url) if want_window else None
    server.activity["own_window"] = proc is not None
    print(f"Stück der Woche {VERSION} läuft unter {url}")
    print("Dieses Fenster darf geschlossen werden – die App läuft weiter, bis du sie schließt.")
    keep_running_without_terminal()
    threading.Thread(target=server.housekeeping, daemon=True).start()

    started = time.time()
    act = server.activity
    last_tick = time.time()
    retried = False
    try:
        while True:
            time.sleep(1)
            now = time.time()
            # Nach dem Ruhezustand springt die Uhrzeit, die Schleife lief aber nicht.
            if now - last_tick > 10:
                # Der Rechner war im Ruhezustand: Zeit dafür nicht als „kein Lebenszeichen“ werten.
                act["last"] = now
                if act["bye"]:
                    act["bye"] = now
                started += now - last_tick
            last_tick = now
            if act["quit"]:
                break  # eine neuere Version übernimmt
            if act["bye"] and now - act["bye"] > 10:
                break  # Fenster geschlossen (und nicht neu geladen)
            if act["seen"] and now - act["last"] > IDLE_LIMIT:
                break  # lange kein Lebenszeichen mehr
            if want_window and not act["seen"] and not retried and now - started > WINDOW_WAIT:
                # Das Fenster hat sich nicht gemeldet – vielleicht konnte der Browser die
                # Startdatei nicht öffnen. Zweiter Versuch mit einer Einmal-Eintrittskarte.
                retried = True
                print("Das Fenster hat sich nicht gemeldet – zweiter Versuch im Standardbrowser.")
                try:
                    open_in_browser(f"{url}#t={zugang.new_ticket()}")
                except Exception as exc:
                    print(f"Auch das hat nicht geklappt: {exc}")
            if not act["seen"] and now - started > 300:
                break  # Fenster wurde nie geöffnet
    except KeyboardInterrupt:
        pass
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
        zugang.deactivate()
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
