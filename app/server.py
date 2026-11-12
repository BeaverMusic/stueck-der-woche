"""Kleiner lokaler Webserver: liefert die Oberfläche aus und stellt die API bereit.

Er lauscht nur auf 127.0.0.1, ist also von anderen Rechnern nicht erreichbar.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import VERSION, ai, browser, codes, media, pdf_export, picker, storage, update, wiki

# Lebenszeichen der geöffneten Oberfläche (zum automatischen Beenden)
activity = {"last": time.time(), "bye": None, "seen": False, "quit": False}

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_BODY = 20 * 1024 * 1024
DATA_URL_RE = re.compile(r"^data:image/(jpeg|jpg|png|webp|gif);base64,(.+)$", re.S)

# Inhaltsrichtlinie: Die Oberfläche darf nur eigene Skripte ausführen und nur mit
# bekannten Adressen sprechen. Selbst eingeschleuster Text könnte so nichts anrichten.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https://upload.wikimedia.org https://*.wikimedia.org https://i.ytimg.com "
    "https://*.scdn.co https://*.spotifycdn.com https://*.mzstatic.com",
    "connect-src 'self' https://upload.wikimedia.org",
    "frame-src 'self'",
    "frame-ancestors 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
])
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "StueckDerWoche"

    def log_message(self, fmt, *args):  # ruhige Konsole
        pass

    # ------------------------------------------------------------ Antworten

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"error": message}, status)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            return self._error("Nicht gefunden", 404)
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, path.read_bytes(), ctype)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("Ungültige Anfrage")
        if length < 0:
            raise ValueError("Ungültige Anfrage")
        if length > MAX_BODY:
            raise ValueError("Datei zu groß (max. 20 MB)")
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if length and ctype not in ("application/json", "text/plain", ""):
            raise ValueError("Ungültige Anfrage")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("Ungültige Anfrage")
        return data

    def _host_ok(self) -> bool:
        """Nur Anfragen an die eigene Adresse beantworten (Schutz vor DNS-Rebinding)."""
        port = self.server.server_address[1]
        host = (self.headers.get("Host") or "").strip().lower()
        return host in (f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}")

    def _base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    # ------------------------------------------------------------ Routen

    def do_GET(self):
        if not self._host_ok():
            return self._error("Nicht erlaubt", 403)
        try:
            path = unquote(urlparse(self.path).path)
            if path == "/":
                return self._file(WEB_DIR / "index.html")
            if path == "/api/ping":
                activity.update(last=time.time(), bye=None, seen=True)
                return self._json({"ok": True, "version": VERSION})
            if path == "/api/sheets":
                return self._json(storage.list_sheets())
            m = re.fullmatch(r"/api/sheets/([a-z0-9-]+)", path)
            if m:
                return self._json(storage.load_sheet(m.group(1)))
            if path == "/api/settings":
                s = storage.load_settings()
                s["data_dir_effective"] = str(storage.data_dir())
                s["export_dir_effective"] = str(storage.export_dir())
                s["browser_effective"] = browser.find_browser() or ""
                s["pdf_engine_effective"] = browser.find_pdf_engine() or ""
                s["app_dir_effective"] = str(WEB_DIR.parent)
                s["update_repo_effective"] = update.repo()
                return self._json(s)
            m = re.fullmatch(r"/data/([a-z0-9-]+)/(bild\.[a-z]+)", path)
            if m:
                return self._file(storage.sheet_dir(m.group(1)) / m.group(2))
            target = (WEB_DIR / path.lstrip("/")).resolve()
            if WEB_DIR in target.parents:
                return self._file(target)
            return self._error("Nicht gefunden", 404)
        except FileNotFoundError:
            self._error("Nicht gefunden", 404)
        except Exception as exc:
            traceback.print_exc()
            storage.log("App", f"{self.command} {self.path}\n{traceback.format_exc()}")
            self._error(str(exc), 500)

    def do_POST(self):
        # Eigener Header: Webseiten aus dem Internet können ihn nicht setzen.
        if self.headers.get("X-App") != "1" or not self._host_ok():
            return self._error("Nicht erlaubt", 403)
        try:
            path = urlparse(self.path).path
            body = self._body()

            if path == "/api/quit":
                activity["quit"] = True  # eine neuere Version möchte übernehmen
                return self._json({"ok": True})
            if path == "/api/bye":
                activity["bye"] = time.time()
                return self._json({"ok": True})
            if path == "/api/sheets":
                return self._json(storage.save_sheet(body))
            m = re.fullmatch(r"/api/sheets/([a-z0-9-]+)/duplicate", path)
            if m:
                return self._json(storage.duplicate_sheet(m.group(1)))
            m = re.fullmatch(r"/api/sheets/([a-z0-9-]+)/delete", path)
            if m:
                storage.delete_sheet(m.group(1))
                return self._json({"ok": True})
            m = re.fullmatch(r"/api/sheets/([a-z0-9-]+)/image", path)
            if m:
                dm = DATA_URL_RE.match(body.get("data_url", ""))
                if not dm:
                    return self._error("Bitte ein Bild (JPG, PNG, WebP, GIF) wählen")
                ext = "." + dm.group(1).replace("jpeg", "jpg")
                name = storage.save_image(m.group(1), ext, base64.b64decode(dm.group(2)))
                return self._json({"file": name})
            if path == "/api/lookup/search":
                return self._json(wiki.search(str(body.get("q", "")), str(body.get("kind", ""))))
            if path == "/api/ai/infotext":
                sheet = storage.load_sheet(str(body.get("id", "")))
                chosen = (sheet.get("lookup") or {}).get("chosen") or ""
                try:
                    sources = wiki.context(chosen, sheet.get("kind", "")) if chosen else ""
                except wiki.LookupError_:
                    sources = ""
                result = ai.generate(sheet, sources, str(body.get("wish", "")).strip(),
                                     str(body.get("previous", "")).strip())
                result["sources"] = bool(sources)
                return self._json(result)
            if path == "/api/cache/clear":
                import shutil
                removed = 0
                for sub in ("wiki", "media", "uebersetzung"):
                    d = storage.config_dir() / "cache" / sub
                    if d.exists():
                        removed += sum(1 for _ in d.rglob("*.json"))
                        shutil.rmtree(d, ignore_errors=True)
                wiki._cache.clear()
                return self._json({"message": f"Zwischenspeicher geleert ({removed} Einträge). Suchen holen ab jetzt frische Daten."})
            if path == "/api/diagnose":
                return self._json(wiki.diagnose())
            if path == "/api/update/check":
                try:
                    return self._json(update.check(force=bool(body.get("force"))))
                except update.UpdateError as exc:
                    return self._error(str(exc))
            if path == "/api/update/install":
                try:
                    result = update.install()
                except update.UpdateError as exc:
                    storage.log("Update", str(exc))
                    return self._error(str(exc))
                own = bool(activity.get("own_window"))
                threading.Timer(0.8, update.restart, args=(own,)).start()
                return self._json({**result, "own_window": own})
            if path == "/api/open-shortcuts":
                if sys.platform != "darwin":
                    return self._error("Kurzbefehle gibt es nur auf dem Mac")
                import subprocess
                subprocess.Popen(["open", "shortcuts://"])
                return self._json({"ok": True})
            if path == "/api/ai/apple-check":
                name = str(body.get("name", "")).strip() or ai.DEFAULT_APPLE_SHORTCUT
                return self._json({"exists": ai.apple_shortcut_exists(name), "name": name})
            if path == "/api/ai/test":
                return self._json({"message": ai.test()})
            if path == "/api/ai/models":
                return self._json(ai.list_models(str(body.get("base", "")).strip(), str(body.get("key", "")).strip()))
            if path == "/api/ai/info":
                return self._json({"presets": ai.PRESETS, "default_prompt": ai.DEFAULT_PROMPT,
                                   "claude_path": ai.find_claude() or "",
                                   "default_anthropic_model": ai.DEFAULT_ANTHROPIC_MODEL,
                                   "default_gemini_model": ai.DEFAULT_GEMINI_MODEL,
                                   "gemini_key_url": ai.GEMINI_KEY_URL,
                                   "platform": sys.platform,
                                   "default_apple_shortcut": ai.DEFAULT_APPLE_SHORTCUT,
                                   "default_provider": ai.default_provider(storage.load_settings()),
                                   **ai.provider_info()})
            if path in ("/api/media/search", "/api/media/test"):
                service = str(body.get("service", ""))
                try:
                    if path.endswith("test"):
                        return self._json({"message": media.test(service)})
                    return self._json(media.search(service, str(body.get("q", ""))))
                except media.MediaError as exc:
                    if exc.code != "nokey":
                        storage.log("App", f"{service}: {exc}")
                    return self._json({"error": str(exc), "code": exc.code}, 400)
            if path == "/api/lookup/images":
                return self._json(wiki.image_search(str(body.get("q", ""))))
            if path == "/api/log":
                storage.log("Oberfläche", str(body.get("message", ""))[:4000])
                return self._json({"ok": True})
            if path == "/api/lookup/suggest":
                return self._json(wiki.suggest(str(body.get("id", "")), str(body.get("kind", ""))))
            m = re.fullmatch(r"/api/sheets/([a-z0-9-]+)/image-url", path)
            if m:
                data, ext = wiki.fetch_image(str(body.get("url", "")), str(body.get("original", "")))
                name = storage.save_image(m.group(1), ext, data)
                return self._json({"file": name})
            if path == "/api/code":
                svg = codes.make_code(body.get("service", ""), body.get("url", ""))
                return self._json({"svg": svg})
            if path == "/api/export":
                target = pdf_export.export(self._base_url(), body.get("mode", ""),
                                           list(body.get("ids") or []))
                return self._json({"path": str(target), "name": target.name})
            if path == "/api/open":
                what = body.get("what")
                if what == "log":
                    storage.log_file().parent.mkdir(parents=True, exist_ok=True)
                    storage.open_folder(storage.log_file().parent)
                else:
                    storage.open_folder(storage.export_dir() if what == "export" else storage.data_dir())
                return self._json({"ok": True})
            if path == "/api/open-url":
                url = str(body.get("url", "")).strip()
                parts = urlparse(url)
                if (parts.scheme not in ("http", "https") or not parts.netloc or len(url) > 2000
                        or re.search(r"[\s\x00-\x1f\x7f\\]", url)):
                    return self._error("Nur http- und https-Links können geöffnet werden")
                webbrowser.open(url)
                return self._json({"ok": True})
            if path == "/api/settings":
                return self._json(storage.save_settings(body))
            if path == "/api/chromium":
                from . import chromium
                try:
                    exe = chromium.download(show=False)
                except Exception as exc:
                    storage.log("Chromium", str(exc))
                    return self._error(f"Chromium konnte nicht geladen werden: {exc}")
                return self._json({"path": exe, "engine": browser.find_pdf_engine() or exe})
            if path == "/api/pick-folder":
                what = body.get("what")
                current = storage.export_dir() if what == "export" else storage.data_dir()
                start = str(body.get("start") or "").strip() or str(current)
                title = "Ordner für die PDFs wählen" if what == "export" else "Ordner für die Blätter wählen"
                try:
                    return self._json({"path": picker.pick_folder(title, start)})
                except picker.PickerError as exc:
                    return self._error(str(exc))
            return self._error("Diese Funktion ist unbekannt – bitte die App schließen und neu starten.", 404)
        except (ValueError, RuntimeError) as exc:
            storage.log("App", f"{self.command} {self.path}: {exc}")
            self._error(str(exc), 400)
        except Exception as exc:
            traceback.print_exc()
            storage.log("App", f"{self.command} {self.path}\n{traceback.format_exc()}")
            self._error(f"Unerwarteter Fehler: {exc}", 500)


def start(port: int = 0) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
