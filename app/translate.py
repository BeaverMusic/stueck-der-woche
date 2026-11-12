"""Übersetzt kurze englische Texte (Beschreibungen, Bezeichnungen) ins Deutsche.

Genutzt wird der kostenlose Dienst MyMemory (ohne Schlüssel, begrenzte
Tagesmenge). Ergebnisse werden dauerhaft zwischengespeichert. Sobald in
einer späteren Etappe die KI-Anbindung da ist, kann sie diese Aufgabe
übernehmen – die Schnittstelle bleibt gleich.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait

from . import storage

API = "https://api.mymemory.translated.net/get"


def _cache_file(text: str):
    key = hashlib.sha1(("en>de:" + text).encode("utf-8")).hexdigest()
    return storage.config_dir() / "cache" / "uebersetzung" / key[:2] / f"{key}.json"


def _one(text: str) -> str:
    text = (text or "").strip()
    if not text or len(text.encode("utf-8")) > 480:
        return text
    cache = _cache_file(text)
    try:
        if cache.is_file():
            return json.loads(cache.read_text("utf-8"))["de"]
    except Exception:
        pass
    url = API + "?" + urllib.parse.urlencode({"q": text, "langpair": "en|de"})
    try:
        from .wiki import user_agent
        req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        result = ((data.get("responseData") or {}).get("translatedText") or "").strip()
        if (str(data.get("responseStatus")) != "200" or not result
                or "MYMEMORY WARNING" in result.upper() or data.get("quotaFinished")):
            return text
    except Exception:
        return text
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"en": text, "de": result}, ensure_ascii=False), "utf-8")
    except Exception:
        pass
    return result


_pool = ThreadPoolExecutor(max_workers=6)


def cached(text: str) -> str | None:
    try:
        return json.loads(_cache_file((text or "").strip()).read_text("utf-8"))["de"]
    except Exception:
        return None


def to_german(texts: list[str], budget: float = 2.5) -> list[str]:
    """Übersetzt mehrere Texte gleichzeitig – aber höchstens „budget“ Sekunden lang.
    Was bis dahin nicht fertig ist, bleibt vorerst englisch; die Übersetzung läuft
    im Hintergrund weiter und steht beim nächsten Mal sofort bereit."""
    if not texts:
        return []
    out = list(texts)
    pending = {}
    for i, text in enumerate(texts):
        hit = cached(text)
        if hit is not None:
            out[i] = hit
        else:
            pending[_pool.submit(_one, text)] = i
    if pending:
        done, _ = wait(pending, timeout=budget)
        for fut in done:
            try:
                out[pending[fut]] = fut.result()
            except Exception:
                pass
    return out
