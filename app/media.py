"""Suche nach Aufnahmen bei YouTube, Spotify und Apple Music.

- YouTube: YouTube Data API v3 (eigener, kostenloser Schlüssel aus der Google Cloud)
- Spotify: Spotify Web API (eigene Entwickler-App; benötigt Spotify Premium)
- Apple Music: Apples freie Suchschnittstelle (ohne Schlüssel)

Ergebnisse werden 7 Tage zwischengespeichert – das schont das YouTube-Kontingent.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import storage

USER_AGENT = "StueckDerWoche/1.0 (Unterrichtsmaterial; lokale Desktop-App)"
CACHE_DAYS = 7


class MediaError(RuntimeError):
    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code


# ------------------------------------------------------------------ Hilfen


def _cache_path(key: str):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return storage.config_dir() / "cache" / "media" / h[:2] / f"{h}.json"


def _cached(key: str):
    p = _cache_path(key)
    try:
        if p.is_file() and time.time() - p.stat().st_mtime < CACHE_DAYS * 86400:
            return json.loads(p.read_text("utf-8"))
    except Exception:
        pass
    return None


def _store(key: str, value) -> None:
    p = _cache_path(key)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False), "utf-8")
    except Exception:
        pass


def _request(url: str, headers: dict | None = None, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.load(resp)
    finally:
        took = time.time() - started
        if took > 4:  # langsame Verbindungen fürs Fehlerprotokoll festhalten
            host = urllib.parse.urlsplit(url).hostname
            storage.log("Netz", f"{host} brauchte {took:.1f} s")


def _http_error_body(exc: urllib.error.HTTPError) -> dict:
    try:
        data = json.loads(exc.read().decode("utf-8", "replace"))
    except Exception:
        return {}
    if isinstance(data, list):  # manche Google-Dienste schicken eine Liste
        data = data[0] if data and isinstance(data[0], dict) else {}
    return data if isinstance(data, dict) else {}


def _duration(ms: int | None) -> str:
    if not ms:
        return ""
    s = round(ms / 1000)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _iso_duration(text: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60000 + s * 1000


def _settings() -> dict:
    return storage.load_settings()


# ------------------------------------------------------------------ YouTube


def youtube(query: str) -> list[dict]:
    key = _settings().get("youtube_key", "").strip()
    if not key:
        raise MediaError("Kein YouTube-Schlüssel hinterlegt", "nokey")
    ck = "yt:" + query.lower()
    hit = _cached(ck)
    if hit is not None:
        return hit
    try:
        data = _request("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode({
            "part": "snippet", "type": "video", "maxResults": 10, "q": query,
            "regionCode": "DE", "relevanceLanguage": "de", "key": key,
        }))
        ids = [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]
        details = {}
        if ids:
            more = _request("https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode({
                "part": "contentDetails,statistics", "id": ",".join(ids), "key": key,
            }))
            details = {v["id"]: v for v in more.get("items", [])}
    except urllib.error.HTTPError as exc:
        body = _http_error_body(exc)
        reasons = " ".join(e.get("reason", "") for e in (body.get("error", {}).get("errors") or []))
        message = body.get("error", {}).get("message", "")
        if "quota" in reasons.lower():
            raise MediaError("Das YouTube-Tageskontingent ist aufgebraucht (morgen geht es wieder)", "quota")
        if "API key not valid" in message or "keyInvalid" in reasons or exc.code == 400:
            raise MediaError("Der YouTube-Schlüssel ist ungültig – bitte in den Einstellungen prüfen", "badkey")
        if exc.code == 403:
            raise MediaError("YouTube verweigert den Zugriff – ist die „YouTube Data API v3“ im "
                             "Google-Cloud-Projekt aktiviert?", "badkey")
        raise MediaError(f"YouTube meldet einen Fehler (HTTP {exc.code})")
    except Exception as exc:
        raise MediaError("YouTube ist gerade nicht erreichbar (Internetverbindung?)") from exc

    results = []
    for it in data.get("items", []):
        vid = it.get("id", {}).get("videoId")
        if not vid:
            continue
        sn = it.get("snippet", {})
        det = details.get(vid, {})
        thumbs = sn.get("thumbnails", {})
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        views = int(det.get("statistics", {}).get("viewCount", 0) or 0)
        results.append({
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": _unescape(sn.get("title", "")),
            "artist": _unescape(sn.get("channelTitle", "")),
            "extra": (sn.get("publishedAt", "")[:4] + (f" · {_views(views)} Aufrufe" if views else "")).strip(" ·"),
            "thumb": thumb,
            "duration_ms": _iso_duration(det.get("contentDetails", {}).get("duration", "")),
        })
    for r in results:
        r["duration"] = _duration(r["duration_ms"])
    _store(ck, results)
    return results


def _unescape(text: str) -> str:
    import html
    return html.unescape(text or "")


def _views(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",") + " Mio."
    if n >= 1000:
        return f"{n // 1000} Tsd."
    return str(n)


# ------------------------------------------------------------------ Spotify

_token = {"value": "", "expires": 0.0, "for": ""}
_token_lock = threading.Lock()


def _spotify_token() -> str:
    s = _settings()
    cid, secret = s.get("spotify_id", "").strip(), s.get("spotify_secret", "").strip()
    if not cid or not secret:
        raise MediaError("Keine Spotify-Zugangsdaten hinterlegt", "nokey")
    with _token_lock:
        if _token["value"] and _token["for"] == cid and time.time() < _token["expires"] - 60:
            return _token["value"]
        auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        try:
            data = _request("https://accounts.spotify.com/api/token",
                            {"Authorization": f"Basic {auth}",
                             "Content-Type": "application/x-www-form-urlencoded"},
                            b"grant_type=client_credentials")
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401):
                raise MediaError("Spotify-Client-ID oder -Secret ist falsch – bitte in den Einstellungen prüfen", "badkey")
            raise MediaError(f"Spotify-Anmeldung fehlgeschlagen (HTTP {exc.code})")
        except Exception as exc:
            raise MediaError("Spotify ist gerade nicht erreichbar (Internetverbindung?)") from exc
        _token.update(value=data["access_token"], expires=time.time() + int(data.get("expires_in", 3600)), **{"for": cid})
        return _token["value"]


def spotify(query: str) -> list[dict]:
    token = _spotify_token()
    ck = "sp:" + query.lower()
    hit = _cached(ck)
    if hit is not None:
        return hit
    url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
        {"q": query, "type": "track", "limit": 10, "market": "DE"})
    try:
        data = _request(url, {"Authorization": f"Bearer {token}"})
    except urllib.error.HTTPError as exc:
        body = _http_error_body(exc)
        msg = (body.get("error") or {}).get("message", "") if isinstance(body.get("error"), dict) else ""
        if exc.code == 403:
            raise MediaError("Spotify verweigert den Zugriff. Ist das Premium-Abo des App-Kontos "
                             f"aktiv? {msg}".strip(), "badkey")
        if exc.code == 429:
            raise MediaError("Zu viele Spotify-Anfragen – bitte kurz warten")
        raise MediaError(f"Spotify meldet einen Fehler (HTTP {exc.code}) {msg}".strip())
    except Exception as exc:
        raise MediaError("Spotify ist gerade nicht erreichbar (Internetverbindung?)") from exc

    results = []
    for t in (data.get("tracks") or {}).get("items", []) or []:
        if not t:
            continue
        album = t.get("album") or {}
        images = sorted(album.get("images") or [], key=lambda i: i.get("width") or 0)
        thumb = next((i["url"] for i in images if (i.get("width") or 0) >= 60), images[-1]["url"] if images else "")
        results.append({
            "url": (t.get("external_urls") or {}).get("spotify", ""),
            "title": t.get("name", ""),
            "artist": ", ".join(a.get("name", "") for a in t.get("artists") or []),
            "extra": " · ".join(x for x in [album.get("name", ""), (album.get("release_date") or "")[:4]] if x),
            "thumb": thumb,
            "duration_ms": t.get("duration_ms") or 0,
            "duration": _duration(t.get("duration_ms")),
        })
    _store(ck, results)
    return results


# ------------------------------------------------------------------ Apple Music


def apple(query: str) -> list[dict]:
    ck = "ap:" + query.lower()
    hit = _cached(ck)
    if hit is not None:
        return hit
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode({
        "term": query, "media": "music", "entity": "song", "country": "DE", "limit": 15, "lang": "de_de",
    })
    try:
        data = _request(url)
    except Exception as exc:
        raise MediaError("Apple Music ist gerade nicht erreichbar (Internetverbindung?)") from exc
    results = []
    for t in data.get("results", []):
        link = t.get("trackViewUrl", "")
        if not link:
            continue
        # „uo=4“ (Werbe-Kennung) entfernen, Rest des Links bleibt unverändert
        parts = urllib.parse.urlsplit(link)
        query_args = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "uo"]
        link = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query_args)))
        results.append({
            "url": link,
            "title": t.get("trackName", ""),
            "artist": t.get("artistName", ""),
            "extra": " · ".join(x for x in [t.get("collectionName", ""), (t.get("releaseDate") or "")[:4]] if x),
            "thumb": t.get("artworkUrl100", ""),
            "duration_ms": t.get("trackTimeMillis") or 0,
            "duration": _duration(t.get("trackTimeMillis")),
        })
    _store(ck, results)
    return results


SERVICES = {"youtube": youtube, "spotify": spotify, "apple": apple}


def search(service: str, query: str) -> list[dict]:
    query = (query or "").strip()
    if service not in SERVICES:
        raise MediaError("Unbekannter Dienst")
    if not query:
        return []
    return SERVICES[service](query)


def test(service: str) -> str:
    """Prüft die Zugangsdaten mit einer kleinen Suche (ohne Zwischenspeicher)."""
    probe = f"Beethoven Mondscheinsonate {int(time.time())}" if service == "youtube" else "Beethoven Mondscheinsonate"
    if service == "spotify":
        _token.update(value="", expires=0)
    results = SERVICES[service](probe)
    if service == "youtube":
        try:
            _cache_path("yt:" + probe.lower()).unlink()
        except Exception:
            pass
    return f"Funktioniert – {len(results)} Treffer bei der Testsuche."
