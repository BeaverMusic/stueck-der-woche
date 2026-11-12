"""Stück der Woche – Startdatei.

Startet den lokalen Server und öffnet die App – als eigenes Fenster, wenn
Chrome/Chromium/Edge/Brave installiert ist, sonst im Standardbrowser.
Die App beendet sich von selbst, sobald das Fenster geschlossen wird.

Mit  --browser  öffnet sie sich stattdessen als Tab im Standardbrowser.
"""

import json
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser

from app import VERSION, browser, server, storage

PORT = 47110  # fester Port, damit Einstellungen im Fenster erhalten bleiben
IDLE_LIMIT = 30 * 60  # so lange ohne Lebenszeichen, dann beendet sich die App


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


def running_version() -> str | None:
    """Version einer bereits laufenden App (oder None, wenn keine läuft)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=2) as r:
            data = json.load(r)
            return str(data.get("version") or "alt") if data.get("ok") else None
    except Exception:
        return None


def ask_old_to_quit() -> None:
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/api/quit", data=b"{}", method="POST",
        headers={"X-App": "1", "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=2).read()
    except Exception:
        pass


def open_window(url: str):
    if "--browser" not in sys.argv:
        proc = browser.open_app_window(url)
        if proc is not None:
            return proc
        print("Kein Chrome/Chromium-Browser gefunden – öffne die App im Standardbrowser.")
    if sys.platform == "darwin":
        # Auf dem Mac zuverlässiger als webbrowser (das über AppleScript geht)
        try:
            subprocess.run(["/usr/bin/open", url], timeout=15, check=True)
            return None
        except Exception as exc:
            print(f"„open“ hat nicht geklappt ({exc}) – versuche es anders.")
    webbrowser.open(url)
    return None


def main() -> None:
    storage.secure_config()  # Einstellungen (mit API-Schlüsseln) nur für den eigenen Benutzer
    url = f"http://127.0.0.1:{PORT}/"
    httpd = None
    replaced = False
    for attempt in range(8):
        try:
            httpd = server.start(PORT)
            if replaced:
                time.sleep(1.5)  # dem alten Fenster Zeit zum Schließen geben
            break
        except OSError:
            version = running_version()
            if version == VERSION:
                # Dieselbe Version läuft schon – nur ein weiteres Fenster öffnen.
                if "--kein-fenster" not in sys.argv:
                    open_window(url)
                return
            if version and attempt == 0:
                print(f"Eine ältere Version ({version}) läuft noch – sie wird beendet …")
                ask_old_to_quit()
                replaced = True
            time.sleep(1)
    if httpd is None:
        # Port bleibt belegt (z. B. sehr alte Version) – auf freiem Port starten.
        httpd = server.start(0)
        url = "http://127.0.0.1:%d/" % httpd.server_address[1]

    # Nach einem Update startet die neue Version ohne neues Fenster, wenn die App
    # in einem normalen Browser-Tab läuft – der Tab lädt sich dann selbst neu.
    proc = None if "--kein-fenster" in sys.argv else open_window(url)
    server.activity["own_window"] = proc is not None
    print(f"Stück der Woche {VERSION} läuft unter {url}")
    print("Dieses Fenster darf geschlossen werden – die App läuft weiter, bis du sie schließt.")
    keep_running_without_terminal()

    started = time.time()
    act = server.activity
    last_tick = time.time()
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
            last_tick = now
            if act["quit"]:
                break  # eine neuere Version übernimmt
            if act["bye"] and now - act["bye"] > 10:
                break  # Fenster geschlossen (und nicht neu geladen)
            if act["seen"] and now - act["last"] > IDLE_LIMIT:
                break  # lange kein Lebenszeichen mehr
            if not act["seen"] and now - started > 300:
                break  # Fenster wurde nie geöffnet
    except KeyboardInterrupt:
        pass
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
