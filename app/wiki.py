"""Vorschläge aus Wikipedia (de/en), Wikidata und Wikimedia Commons.

Es wird nichts automatisch übernommen: Die Oberfläche zeigt die Vorschläge,
und du wählst aus, was aufs Blatt kommt.

Geschwindigkeit: Alle Quellen werden gleichzeitig abgefragt, Antworten 30 Tage
zwischengespeichert, und die Vorschläge der besten Treffer werden schon im
Hintergrund geladen, während du noch die Trefferliste ansiehst.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from . import storage, translate

WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
DEWIKI_API = WIKI_API.format(lang="de")
ENWIKI_API = WIKI_API.format(lang="en")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "StueckDerWoche (Desktop-App fuer den Musikunterricht)"  # siehe user_agent()
LANGS = ["de", "en"]

FEMALE = "Q6581072"
GROUP_TYPES = {
    "Q215380",   # Musikgruppe
    "Q5741069",  # Rockband
    "Q2088357",  # Musikensemble
    "Q9212979",  # Musikduo
    "Q281643",   # Trio
    "Q4438121",  # Boygroup
    "Q105756498",  # Girlgroup
}
DISAMBIGUATION = re.compile(r"begriffsklärung|disambiguation", re.I)

# Bekannte Werkverzeichnisse → Kürzel
CATALOG_PREFIX = [
    ("bach-werke", "BWV"), ("bach works", "BWV"),
    ("köchel", "KV"), ("koechel", "KV"),
    ("hoboken", "Hob."),
    ("deutsch", "D"),
    ("ryom", "RV"),
    ("händel-werke", "HWV"), ("handel-werke", "HWV"), ("händel werke", "HWV"),
    ("handel werke", "HWV"),
    ("werke ohne opus", "WoO"), ("woo", "WoO"),
    ("opus", "op."),
]

# Zwei getrennte Pools, damit wartende Vorschläge nie die Einzelabfragen blockieren.
_pool = ThreadPoolExecutor(max_workers=12)          # einzelne Web-Abfragen
_suggest_pool = ThreadPoolExecutor(max_workers=4)   # Vorschläge (auch im Voraus)


class LookupError_(RuntimeError):
    pass


def _parallel(*funcs):
    """Führt mehrere Abfragen gleichzeitig aus. Fehler einzelner Quellen
    ergeben None statt alles abzubrechen."""
    futures = [_pool.submit(f) for f in funcs]
    results = []
    for fut in futures:
        try:
            results.append(fut.result())
        except LookupError_:
            results.append(None)
    return results


# ------------------------------------------------------------------ HTTP

CACHE_DAYS = 30


def _cache_file(full_url: str) -> Path:
    key = hashlib.sha1(full_url.encode("utf-8")).hexdigest()
    return storage.config_dir() / "cache" / "wiki" / key[:2] / f"{key}.json"


# Wikimedia bittet darum, nicht zu viele Anfragen gleichzeitig zu stellen.
# Je Server höchstens zwei gleichzeitig; der Rest wartet kurz.
PER_HOST = 2
_host_locks: dict[str, threading.BoundedSemaphore] = {}
_host_locks_guard = threading.Lock()
RETRY_CODES = {429, 500, 502, 503, 504}


def _host_lock(host: str) -> threading.BoundedSemaphore:
    with _host_locks_guard:
        if host not in _host_locks:
            _host_locks[host] = threading.BoundedSemaphore(PER_HOST)
        return _host_locks[host]


def user_agent() -> str:
    """Absenderkennung nach den Wikimedia-Regeln: App-Name, Version, Zweck, Kontakt."""
    from . import VERSION
    contact = storage.load_settings().get("wiki_contact", "").strip()
    contact = f"; {contact}" if contact else ""
    return f"StueckDerWoche/{VERSION} (Desktop-App fuer den Musikunterricht{contact}) Python-urllib"


def describe(exc: BaseException) -> str:
    """Verständliche Beschreibung eines Verbindungsfehlers."""
    if isinstance(exc, urllib.error.HTTPError):
        return {403: "Anfrage abgelehnt (HTTP 403)", 429: "zu viele Anfragen (HTTP 429)",
                503: "Server überlastet (HTTP 503)"}.get(exc.code, f"HTTP {exc.code}")
    reason = getattr(exc, "reason", exc)
    text = str(reason)
    if "CERTIFICATE" in text.upper() or "SSL" in text.upper():
        return f"Zertifikatsproblem ({text[:120]})"
    if isinstance(reason, TimeoutError) or "timed out" in text.lower():
        return "keine Antwort in der Wartezeit"
    if "nodename" in text or "Name or service" in text or "getaddrinfo" in text:
        return "Adresse nicht auflösbar (DNS)"
    return f"{type(reason).__name__}: {text[:120]}"


def _fetch(full: str, timeout: float = 15) -> dict:
    """Eine Anfrage mit bis zu drei Versuchen. Bei „zu viele Anfragen“ oder
    Überlastung wird kurz gewartet (bzw. so lange, wie der Server angibt)."""
    host = urllib.parse.urlsplit(full).hostname or ""
    last: BaseException | None = None
    for attempt in range(3):
        req = urllib.request.Request(full, headers={"User-Agent": user_agent(),
                                                    "Accept": "application/json"})
        try:
            with _host_lock(host):
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.load(resp)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in RETRY_CODES:
                break
            try:
                wait = float(exc.headers.get("Retry-After") or 0)
            except (TypeError, ValueError):
                wait = 0
            time.sleep(min(wait if wait > 0 else 1.5 * (attempt + 1), 10))
        except Exception as exc:  # Zeitüberschreitung, Verbindungsabbruch …
            last = exc
            if "CERTIFICATE" in str(exc).upper():
                break  # ein Zertifikatsproblem löst sich durch Warten nicht
            time.sleep(1.0 * (attempt + 1))
    reason = describe(last) if last else "unbekannt"
    storage.log("Netz", f"{host}: {reason} – {full[:200]}")
    if isinstance(last, urllib.error.HTTPError) and last.code == 403:
        raise LookupError_(f"{host} hat die Anfrage abgelehnt. Bitte in den Einstellungen unter "
                           "„Verbindungen prüfen“ nachsehen und das Ergebnis weitergeben.")
    raise LookupError_(f"Wikipedia/Wikidata antwortet gerade nicht ({reason}). "
                       "Bitte gleich noch einmal versuchen.")


def _get_json(url: str, params: dict) -> dict:
    """Ruft eine Wikimedia-API auf, mit 30 Tagen Zwischenspeicher."""
    full = url + "?" + urllib.parse.urlencode({**params, "format": "json"})
    cache = _cache_file(full)
    try:
        if cache.is_file() and time.time() - cache.stat().st_mtime < CACHE_DAYS * 86400:
            return json.loads(cache.read_text("utf-8"))
    except Exception:
        pass
    for attempt in range(3):
        data = _fetch(full)
        err = data.get("error") if isinstance(data, dict) else None
        if err and err.get("code") in ("ratelimited", "maxlag") and attempt < 2:
            time.sleep(2.0 * (attempt + 1))  # Wikipedia bremst: kurz warten, dann erneut
            continue
        break
    if err and not data.get("query") and not data.get("entities"):
        storage.log("Netz", f"API-Fehler: {err.get('code')}: {err.get('info', '')[:200]}")
        raise LookupError_(f"Wikipedia/Wikidata meldet einen Fehler: {err.get('info', err.get('code'))}")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        tmp.replace(cache)
    except Exception:
        pass
    return data


DIAGNOSE = [
    ("Deutsche Wikipedia", "https://de.wikipedia.org/w/api.php?action=query&meta=siteinfo&format=json"),
    ("Englische Wikipedia", "https://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&format=json"),
    ("Wikidata", "https://www.wikidata.org/w/api.php?action=query&meta=siteinfo&format=json"),
    ("Wikimedia Commons", "https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json"),
    ("Übersetzung (MyMemory)", "https://api.mymemory.translated.net/get?q=test&langpair=en%7Cde"),
]


def diagnose() -> list[dict]:
    """Prüft jede Quelle einzeln, ohne Zwischenspeicher und ohne Wiederholung."""
    import ssl
    import sys
    results = []
    for name, url in DIAGNOSE:
        started = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read(2000)
                ok, info = True, f"HTTP {resp.status}"
        except Exception as exc:
            ok, info = False, describe(exc)
        results.append({"name": name, "ok": ok, "info": info, "ms": int((time.time() - started) * 1000)})
    import os
    results.append({"name": "System", "ok": True, "ms": 0,
                    "info": f"Python {sys.version.split()[0]}, {sys.platform}, "
                            f"{ssl.OPENSSL_VERSION}, Zertifikate: {os.environ.get('SSL_CERT_FILE') or ssl.get_default_verify_paths().cafile or 'Standard'}"})
    storage.log("Prüfung", " | ".join(f"{r['name']}: {'ok' if r['ok'] else 'FEHLER'} {r['info']} {r['ms']} ms" for r in results))
    return results


# ------------------------------------------------------------------ Bilder laden

# Wikimedia erzeugt Vorschaubilder nur in festen Standardbreiten.
THUMB_WIDTH = 960
THUMB_FALLBACKS = (960, 500)
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
               "image/gif": ".gif"}


def _resize(url: str, width: int) -> str:
    return re.sub(r"/(\d+)px-([^/]+)$", rf"/{width}px-\2", url)


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def allowed_image_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(_normalize_url(url))
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("https", "http") and (
        host.endswith(".wikimedia.org") or host.endswith(".wikipedia.org")
    )


def _download(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read(15 * 1024 * 1024 + 1)
        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip()
    if len(data) > 15 * 1024 * 1024:
        raise ValueError("Das Bild ist zu groß")
    if ctype not in IMAGE_TYPES:
        raise ValueError(f"Unbekanntes Bildformat ({ctype or 'ohne Angabe'})")
    return data, IMAGE_TYPES[ctype]


def fetch_image(url: str, original: str = "") -> tuple[bytes, str]:
    """Lädt ein Bild von Wikimedia. Probiert mehrere Standardgrößen und zuletzt
    das Original. Gibt (Daten, Endung) zurück."""
    url, original = _normalize_url(url), _normalize_url(original)
    for u in (url, original):
        if u and not allowed_image_url(u):
            host = urllib.parse.urlparse(u).hostname or u[:40]
            raise ValueError(f"Bildadresse wird nicht unterstützt ({host})")
    candidates = []
    if url:
        if re.search(r"/\d+px-[^/]+$", url):
            candidates += [_resize(url, w) for w in THUMB_FALLBACKS]
        else:
            candidates.append(url)
    if original:
        candidates.append(original)
    last = "keine Adresse"
    for u in dict.fromkeys(candidates):
        try:
            return _download(u)
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except ValueError as exc:
            last = str(exc)
        except Exception as exc:
            last = exc.__class__.__name__
    raise LookupError_(f"Das Bild konnte nicht geladen werden ({last})")


# ------------------------------------------------------------------ Wikidata-Hilfen


def _entities(ids: list[str], props: str = "labels|descriptions|claims|sitelinks") -> dict:
    # Läuft selbst innerhalb paralleler Abfragen, daher hier nacheinander.
    ids = [i for i in dict.fromkeys(ids) if re.fullmatch(r"Q\d+", i or "")]
    result: dict = {}
    for start in range(0, len(ids), 50):
        result.update(_get_json(WIKIDATA_API, {
            "action": "wbgetentities", "ids": "|".join(ids[start:start + 50]), "props": props,
            "languages": "|".join(LANGS), "sitefilter": "dewiki|enwiki",
        }).get("entities", {}))
    return {k: v for k, v in result.items() if "missing" not in v}


def _sitelink(entity: dict, site: str) -> str:
    return ((entity.get("sitelinks") or {}).get(site) or {}).get("title", "")


def _strip_paren(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)$", "", title or "")  # „Klassik (Musik)“ → „Klassik“


def _label(entity: dict) -> tuple[str, bool]:
    """(Bezeichnung, ist_deutsch). Reihenfolge: deutsche Bezeichnung,
    deutscher Wikipedia-Titel, englische Bezeichnung, englischer Titel."""
    labels = entity.get("labels") or {}
    if "de" in labels:
        return labels["de"]["value"], True
    title = _sitelink(entity, "dewiki")
    if title:
        return _strip_paren(title), True
    if "en" in labels:
        return labels["en"]["value"], False
    return _strip_paren(_sitelink(entity, "enwiki")), False


def _text(entity: dict, key: str = "labels") -> str:
    if key == "labels":
        return _label(entity)[0]
    values = entity.get(key) or {}
    for lang in LANGS:
        if lang in values:
            return values[lang].get("value", "")
    return ""


def _statements(entity: dict, prop: str) -> list[dict]:
    claims = [c for c in (entity.get("claims") or {}).get(prop, []) if c.get("rank") != "deprecated"]
    preferred = [c for c in claims if c.get("rank") == "preferred"]
    return preferred or claims


def _value(statement: dict):
    snak = statement.get("mainsnak") or {}
    if snak.get("snaktype") != "value":
        return None
    return (snak.get("datavalue") or {}).get("value")


def _item_ids(entity: dict, prop: str) -> list[str]:
    out = []
    for st in _statements(entity, prop):
        v = _value(st)
        if isinstance(v, dict) and v.get("id"):
            out.append(v["id"])
    return out


def _year(entity: dict, *props: str) -> str:
    for prop in props:
        for st in _statements(entity, prop):
            v = _value(st)
            if isinstance(v, dict) and v.get("time"):
                m = re.match(r"([+-])0*(\d+)-", v["time"])
                if m:
                    year = int(m.group(2))
                    if v.get("precision", 9) < 9:  # nur Jahrzehnt/Jahrhundert bekannt
                        return f"um {year}"
                    return f"{year} v. Chr." if m.group(1) == "-" else str(year)
    return ""


def _strings(entity: dict, prop: str) -> list[str]:
    return [v for v in (_value(st) for st in _statements(entity, prop)) if isinstance(v, str)]


def _wiki_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


# ------------------------------------------------------------------ Suche

# Wikidata-Filter „hat mit Musik zu tun“: Werke mit Komponist/Interpret/Tonart/
# Besetzung/Werkverzeichnis/Label, Personen mit Musikberuf oder Instrument,
# Musikgruppen.
MUSIC_FILTER = "haswbstatement:" + "|".join([
    "P86", "P175", "P826", "P870", "P528", "P264", "P658", "P1303", "P412",
    "P31=Q215380", "P31=Q5741069", "P31=Q2088357", "P31=Q9212979",
    "P106=Q36834", "P106=Q639669", "P106=Q177220", "P106=Q488205", "P106=Q753110",
    "P106=Q486748", "P106=Q1259917", "P106=Q158852", "P106=Q2252262", "P106=Q855091",
])
MUSIC_WORDS = re.compile(
    r"komponist|musik|sänger|band\b|album|lied|song|single|sinfonie|symphon|konzert|"
    r"sonate|sonata|oper\b|opera|jazz|rapper|pianist|geiger|dirigent|chor|kantate|"
    r"messe|quartett|ouvertüre|suite|komposition|instrumental|rock|pop|hip-hop|"
    r"composer|musician|singer|concerto|symphony|composition|record|recording|"
    r"orchest|melod|ballett|ballet|musical|requiem|motette|choral|lieder",
    re.I,
)
STOPWORDS = {"der", "die", "das", "den", "dem", "des", "von", "vom", "und", "in", "im",
             "the", "of", "a", "an", "and", "by", "nr", "no", "op", "für", "for"}


def _first_sentences(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\s*\([^()]*\)", "", text) if len(text) > limit else text  # Klammern kürzen
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return (cut[: cut.rfind(" ")] if " " in cut else cut).rstrip(",;:") + " …"


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[0-9]+|[^\W\d_]+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and (w.isdigit() or len(w) >= 2)]


def _match_share(query_tokens: list[str], text: str) -> float:
    """Anteil der Suchwörter, die im Text vorkommen (Zahlen als ganzes Wort)."""
    if not query_tokens:
        return 0.0
    low = (text or "").lower()
    hits = 0
    for t in query_tokens:
        if t.isdigit():
            hits += bool(re.search(rf"(?<!\d){t}(?!\d)", low))
        else:
            hits += t in low
    return hits / len(query_tokens)


def _wiki_search(lang: str, query: str) -> list[str]:
    data = _get_json(WIKI_API.format(lang=lang), {
        "action": "query", "list": "search", "srsearch": query,
        "srlimit": 8, "srnamespace": 0, "srprop": "",
    })
    return [r["title"] for r in data.get("query", {}).get("search", [])]


def _wiki_pages(lang: str, titles: list[str]) -> dict:
    """Titel → {qid, extract} (Begriffsklärungen ausgelassen)."""
    if not titles:
        return {}
    info = _get_json(WIKI_API.format(lang=lang), {
        "action": "query", "titles": "|".join(titles), "prop": "pageprops|extracts",
        "ppprop": "wikibase_item|disambiguation", "exintro": 1, "explaintext": 1,
        "exchars": 400, "exlimit": "max", "redirects": 1,
    })
    out = {}
    for page in (info.get("query", {}).get("pages") or {}).values():
        props = page.get("pageprops") or {}
        if props.get("wikibase_item") and "disambiguation" not in props:
            out[page.get("title")] = {"qid": props["wikibase_item"], "extract": page.get("extract", "")}
    return out


def _wd_search(query: str, lang: str) -> list[str]:
    """Wikidata: Suche in den Namen (Wortanfang)."""
    data = _get_json(WIKIDATA_API, {
        "action": "wbsearchentities", "search": query, "language": lang,
        "uselang": lang, "type": "item", "limit": 8,
    })
    return [r["id"] for r in data.get("search", [])]


def _wd_fulltext(query: str, music_only: bool) -> list[str]:
    """Wikidata: Volltextsuche in Namen, Beschreibungen und Alternativnamen –
    die treffsicherste Quelle der ersten Version, jetzt auf Musik gefiltert."""
    data = _get_json(WIKIDATA_API, {
        "action": "query", "list": "search", "srlimit": 12, "srprop": "",
        "srsearch": f"{query} {MUSIC_FILTER}" if music_only else query,
    })
    return [r["title"] for r in data.get("query", {}).get("search", [])
            if re.fullmatch(r"Q\d+", r.get("title", ""))]


def search(query: str, kind: str = "") -> list[dict]:
    """Durchsucht Wikidata (gefiltert auf Musik), deutsche und englische Wikipedia
    gleichzeitig und führt die Treffer zusammen. Musikbezogene Treffer, deren
    Name oder Beschreibung die Suchwörter enthält, stehen vorn."""
    query = (query or "").strip()
    if not query:
        return []
    qtokens = _tokens(query)

    # 1. Alle Quellen gleichzeitig durchsuchen
    wd_music, wd_de, wd_en, de_titles, en_titles = _parallel(
        lambda: _wd_fulltext(query, True),
        lambda: _wd_search(query, "de"),
        lambda: _wd_search(query, "en"),
        lambda: _wiki_search("de", query),
        lambda: _wiki_search("en", query),
    )
    if all(r is None for r in (wd_music, wd_de, wd_en, de_titles, en_titles)):
        raise LookupError_("Wikipedia/Wikidata ist gerade nicht erreichbar (Internetverbindung?)")
    wd_music = wd_music or []

    # 2. Grundwertung nach Position in jeder Quelle
    score: dict[str, float] = {}

    def rank(ids, weight):
        for pos, qid in enumerate(ids):
            score[qid] = score.get(qid, 0) + weight / (pos + 1)

    rank(wd_music, 1.4)
    rank(wd_de or [], 0.8)
    rank(wd_en or [], 0.5)
    wd_ids = list(dict.fromkeys(wd_music + (wd_de or []) + (wd_en or [])))

    # 3. Wikipedia-Artikel → Wikidata-ID; zugleich Wikidata-Einträge laden
    de_pages, en_pages, ents = _parallel(
        lambda: _wiki_pages("de", de_titles or []),
        lambda: _wiki_pages("en", en_titles or []),
        lambda: _entities(wd_ids, "labels|descriptions|sitelinks|aliases"),
    )
    de_pages, en_pages, ents = de_pages or {}, en_pages or {}, ents or {}
    rank([de_pages[t]["qid"] for t in (de_titles or []) if t in de_pages], 0.7)
    rank([en_pages[t]["qid"] for t in (en_titles or []) if t in en_pages], 0.4)
    extract_de = {p["qid"]: p["extract"] for p in de_pages.values()}
    extract_en = {p["qid"]: p["extract"] for p in en_pages.values()}

    pool = sorted(score, key=lambda q: -score[q])[:24]
    missing = [q for q in pool if q not in ents]
    if missing:
        ents.update(_entities(missing, "labels|descriptions|sitelinks|aliases") or {})

    # 4. Feinwertung: Musikbezug und Übereinstimmung mit den Suchwörtern
    music_set = set(wd_music)
    final: list[tuple[float, str, bool]] = []
    for qid in pool:
        e = ents.get(qid)
        if not e:
            continue
        descs = e.get("descriptions") or {}
        desc_all = " ".join(d.get("value", "") for d in descs.values())
        if DISAMBIGUATION.search(desc_all):
            continue
        names = [v.get("value", "") for v in (e.get("labels") or {}).values()]
        for lang_aliases in (e.get("aliases") or {}).values():
            names += [a.get("value", "") for a in lang_aliases]
        names += [_sitelink(e, "dewiki"), _sitelink(e, "enwiki")]
        name_text = " ".join(names)
        context = " ".join([name_text, desc_all, extract_de.get(qid, "")[:300], extract_en.get(qid, "")[:300]])
        is_music = qid in music_set or bool(MUSIC_WORDS.search(desc_all + " " + extract_de.get(qid, "")[:300]
                                                               + " " + extract_en.get(qid, "")[:300]))
        s = score[qid]
        s *= 1 + 2.0 * _match_share(qtokens, name_text) + 1.0 * _match_share(qtokens, context)
        if not is_music:
            s *= 0.15
        final.append((s, qid, is_music))
    final.sort(key=lambda x: -x[0])
    # Musiktreffer zuerst; Nicht-Musik nur zum Auffüllen, wenn es kaum Musik gibt.
    music_hits = [f for f in final if f[2]]
    other_hits = [f for f in final if not f[2]]
    chosen = music_hits[:10] + other_hits[:max(0, 3 - len(music_hits))]

    # 5. Anzeige vorbereiten
    hits, to_translate = [], []
    for _, qid, _ in chosen:
        e = ents[qid]
        descs = e.get("descriptions") or {}
        desc_de = descs.get("de", {}).get("value", "")
        desc_en = descs.get("en", {}).get("value", "")
        label, _ = _label(e)
        hit = {"id": qid, "label": label or qid}
        if extract_de.get(qid):
            hit["description"] = _first_sentences(extract_de[qid])
        elif desc_de:
            hit["description"] = desc_de
        else:
            english = desc_en or _first_sentences(extract_en.get(qid, ""), 200)
            hit["description"] = english
            if english:
                to_translate.append(hit)
        de_title, en_title = _sitelink(e, "dewiki"), _sitelink(e, "enwiki")
        hit["source"] = "Wikipedia" if de_title else ("englische Wikipedia" if en_title else "Wikidata")
        hit["wiki"] = _wiki_url("de", de_title) if de_title else (
            _wiki_url("en", en_title) if en_title else f"https://www.wikidata.org/wiki/{qid}")
        hits.append(hit)

    if to_translate:
        for hit, text in zip(to_translate, translate.to_german([h["description"] for h in to_translate])):
            if text != hit["description"]:
                hit["description"] = text[:1].upper() + text[1:]
                hit["translated"] = True

    # 6. Vorschläge der besten Treffer schon im Hintergrund laden
    for hit in hits[:2]:
        prefetch(hit["id"], kind)
    return hits


# ------------------------------------------------------------------ Vorschläge


def _person_label(person: dict, role: str) -> str:
    types = set(_item_ids(person, "P31"))
    if types & GROUP_TYPES or (not _statements(person, "P569") and _statements(person, "P571")):
        return "Band" if role == "Interpret" else "Ensemble"
    female = FEMALE in _item_ids(person, "P21")
    return {"Komponist": "Komponistin" if female else "Komponist",
            "Interpret": "Interpretin" if female else "Interpret"}[role]


def _person_value(person: dict) -> str:
    name = _text(person)
    born, died = _year(person, "P569"), _year(person, "P570")
    founded, ended = _year(person, "P571"), _year(person, "P576")
    if born and died:
        return f"{name} ({born}–{died})"
    if born:
        return f"{name} (geb. {born})"
    if founded and ended:
        return f"{name} ({founded}–{ended})"
    if founded:
        return f"{name} (seit {founded})"
    return name


def _catalog(work: dict, labels: dict) -> str:
    codes = []
    for st in _statements(work, "P528"):
        code = _value(st)
        if not isinstance(code, str):
            continue
        catalog = ""
        for q in (st.get("qualifiers") or {}).get("P972", []):
            v = (q.get("datavalue") or {}).get("value") or {}
            catalog = labels.get(v.get("id"), "")
        prefix = ""
        low = catalog.lower()
        for key, pre in CATALOG_PREFIX:
            if key in low:
                prefix = pre
                break
        if prefix and not code.lower().startswith(prefix.lower().rstrip(".")):
            code = f"{prefix} {code}"
        codes.append(code)
    return " · ".join(dict.fromkeys(codes))


def _clean(html_text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _depicts(person_id: str | None) -> list[str]:
    if not person_id:
        return []
    data = _get_json(COMMONS_API, {
        "action": "query", "list": "search", "srnamespace": 6, "srlimit": 10,
        "srsearch": f"haswbstatement:P180={person_id}",
    })
    return [r["title"] for r in data.get("query", {}).get("search", [])]


def image_search(query: str) -> list[dict]:
    """Freie Bildsuche auf Wikimedia Commons (nur Fotos/Gemälde, keine Grafiken)."""
    query = (query or "").strip()
    if not query:
        return []
    data = _get_json(COMMONS_API, {
        "action": "query", "list": "search", "srnamespace": 6, "srlimit": 16, "srprop": "",
        "srsearch": f"{query} filetype:bitmap",
    })
    titles = [r["title"] for r in data.get("query", {}).get("search", [])]
    return _image_infos(titles, limit=12)


def _image_infos(titles: list[str], limit: int = 8) -> list[dict]:
    titles = [t for t in dict.fromkeys(titles)
              if not re.search(r"signatur|unterschrift|autograph|\.(pdf|djvu|ogg|oga|webm|mid|svg)$", t, re.I)][:limit]
    if not titles:
        return []
    data = _get_json(COMMONS_API, {
        "action": "query", "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size", "iiurlwidth": THUMB_WIDTH,
    })
    found = {}
    for page in (data.get("query", {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        thumb = _normalize_url(info.get("thumburl") or "")
        if not thumb or not str(info.get("mime", "")).startswith("image/"):
            continue
        meta = info.get("extmetadata") or {}
        artist = _clean((meta.get("Artist") or {}).get("value", "")) or "Unbekannt"
        if len(artist) > 70:
            artist = artist[:67].rstrip() + "…"
        license_ = _clean((meta.get("LicenseShortName") or {}).get("value", "")) or "Lizenz siehe Commons"
        license_ = {"Public domain": "gemeinfrei", "Public Domain": "gemeinfrei", "PD": "gemeinfrei"}.get(license_, license_)
        original = _normalize_url(info.get("url", ""))
        if info.get("mime") not in IMAGE_TYPES or (info.get("size") or 0) > 15 * 1024 * 1024:
            original = ""  # z. B. TIFF oder sehr große Dateien nicht als Original laden
        found[page.get("title")] = {
            "title": page.get("title", "").removeprefix("File:"),
            "thumb": thumb,
            "preview": _resize(thumb, 330),
            "original": original,
            "page": info.get("descriptionurl", ""),
            "credit": f"{artist} · {license_} · via Wikimedia Commons",
        }
    return [found[t] for t in titles if t in found]


_cache: dict = {}
_cache_lock = threading.Lock()


def prefetch(qid: str, kind: str) -> None:
    """Startet das Laden der Vorschläge im Hintergrund (falls nicht schon da)."""
    key = (qid, kind)
    with _cache_lock:
        if key in _cache:
            return
        _cache[key] = _suggest_pool.submit(_suggest, qid, kind)


def suggest(qid: str, kind: str) -> dict:
    if not re.fullmatch(r"Q\d+", qid or ""):
        raise ValueError("Ungültige Wikidata-ID")
    prefetch(qid, kind)
    fut: Future = _cache[(qid, kind)]
    try:
        return fut.result(timeout=60)
    except Exception:
        with _cache_lock:  # Fehler nicht merken, nächster Versuch lädt neu
            if _cache.get((qid, kind)) is fut:
                del _cache[(qid, kind)]
        raise


def _suggest(qid: str, kind: str) -> dict:
    work = _entities([qid]).get(qid)
    if not work:
        raise LookupError_("Eintrag nicht gefunden")

    composers = _item_ids(work, "P86")
    performers = _item_ids(work, "P175")
    parts = _item_ids(work, "P361")
    is_person = bool(_statements(work, "P569")) or bool(set(_item_ids(work, "P31")) & GROUP_TYPES) \
        or "Q5" in _item_ids(work, "P31")

    if is_person:
        main_id, role = qid, ("Komponist" if kind == "klassik" else "Interpret")
    elif kind == "klassik":
        main_id = (composers or performers or [None])[0]
        role = "Komponist" if composers else "Interpret"
    else:
        main_id = (performers or composers or [None])[0]
        role = "Interpret" if performers else "Komponist"

    translatable = _item_ids(work, "P135") + _item_ids(work, "P136")[:2] \
        + _item_ids(work, "P826")[:1] + _item_ids(work, "P870")[:6]
    catalogs = []
    for st in _statements(work, "P528"):
        for q in (st.get("qualifiers") or {}).get("P972", []):
            v = (q.get("datavalue") or {}).get("value") or {}
            if v.get("id"):
                catalogs.append(v["id"])
    related = composers[:2] + performers[:2] + parts[:1] + translatable + catalogs

    # Verknüpfte Einträge und Commons-Bilder gleichzeitig laden
    ents, depicted = _parallel(lambda: _entities(related), lambda: _depicts(main_id))
    ents, depicted = ents or {}, depicted or []
    if is_person:
        ents[qid] = work
    person = ents.get(main_id) if main_id else None

    labels = {k: _label(v)[0] for k, v in ents.items()}
    # Englische Fachbegriffe (Gattung, Epoche, Instrumente, Tonart) übersetzen;
    # Namen und Titel bleiben unverändert.
    english = [k for k in dict.fromkeys(translatable) if k in ents and not _label(ents[k])[1] and labels.get(k)]
    for k, text in zip(english, translate.to_german([labels[k] for k in english])):
        labels[k] = text

    # Bilder: 1. Hauptperson/Band (Wikidata-Bild und Commons „zeigt …“),
    # 2. weitere beteiligte Personen, 3. Namenssuche auf Commons.
    others = [p for p in dict.fromkeys(performers + composers if kind != "klassik" else composers + performers)
              if p != main_id]
    files = _strings(person, "P18")[:1] if person else []
    titles = ["File:" + f for f in files] + depicted
    for p in others:
        titles += ["File:" + f for f in _strings(ents.get(p) or {}, "P18")[:1]]
    try:
        images = _image_infos(titles)
        if not images:
            names = [_text(person)] if person else []
            names += [_text(ents[p]) for p in others if p in ents]
            names.append(_text(work))  # zuletzt: nach dem Eintrag selbst (z. B. Band ohne Bild)
            names = list(dict.fromkeys(n for n in names if n))[:3]
            # alle Namen gleichzeitig suchen, das erste Ergebnis in dieser Reihenfolge nehmen
            for found in _parallel(*[(lambda n=n: image_search(n)) for n in names]):
                if found:
                    images = found
                    break
    except LookupError_:
        images = []

    fields: list[dict] = []

    def add(label, value, wide=False):
        if value:
            fields.append({"label": label, "value": value, "wide": wide})

    if person:
        add(_person_label(person, role), _person_value(person), True)

    title = "" if is_person else _text(work)
    part_label = labels.get(parts[0], "") if parts else ""
    genres = ", ".join(labels[g] for g in _item_ids(work, "P136")[:2] if labels.get(g))
    epoch = ", ".join(labels[e] for e in _item_ids(work, "P135") if labels.get(e))

    if not is_person:
        if kind == "klassik":
            add("Werk", title, True)
            add("Gesamtwerk", part_label, True)
            add("Werkverzeichnis", _catalog(work, labels))
            add("Entstehung", _year(work, "P571", "P577", "P1191"))
            add("Epoche", epoch or genres)
            add("Tonart", ", ".join(labels[t] for t in _item_ids(work, "P826")[:1] if labels.get(t)))
            add("Besetzung", ", ".join(labels[i] for i in _item_ids(work, "P870") if labels.get(i)), True)
        else:
            add("Album", part_label, True)
            add("Erscheinungsjahr", _year(work, "P577", "P571"))
            add("Genre" if kind != "jazz" else "Stil", genres or epoch)
            if kind == "jazz" and performers and composers:
                comp = ents.get(composers[0])
                if comp:
                    add(_person_label(comp, "Komponist"), _person_value(comp), True)

    de_title, en_title = _sitelink(work, "dewiki"), _sitelink(work, "enwiki")
    url, url_label = f"https://www.wikidata.org/wiki/{qid}", "auf Wikidata ansehen"
    if de_title:
        url, url_label = _wiki_url("de", de_title), "auf Wikipedia ansehen"
    elif en_title:
        url, url_label = _wiki_url("en", en_title), "in der englischen Wikipedia ansehen"
    return {
        "id": qid,
        "label": _text(work),
        "description": _text(work, "descriptions"),
        "url": url,
        "url_label": url_label,
        "title": title,
        "short_title": title if len(title) <= 32 else "",
        "fields": fields,
        "images": images,
        "person": _text(person) if person else "",
    }


# ------------------------------------------------------------------ Quellen für den Infotext


def _extract(lang: str, title: str, intro_only: bool, limit: int) -> str:
    params = {"action": "query", "titles": title, "prop": "extracts", "explaintext": 1,
              "exsectionformat": "plain", "redirects": 1}
    if intro_only:
        params["exintro"] = 1
    data = _get_json(WIKI_API.format(lang=lang), params)
    for page in (data.get("query", {}).get("pages") or {}).values():
        text = re.sub(r"\n{3,}", "\n\n", page.get("extract", "") or "").strip()
        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0] + " …"
        return text
    return ""


def context(qid: str, kind: str = "") -> str:
    """Wikipedia-Texte zum Werk (ausführlicher) und zur Hauptperson/Band (Einleitung)
    als Grundlage für den KI-Infotext. Deutsch bevorzugt, sonst Englisch."""
    if not re.fullmatch(r"Q\d+", qid or ""):
        return ""
    work = _entities([qid], "labels|sitelinks|claims").get(qid)
    if not work:
        return ""
    people = (_item_ids(work, "P86")[:1] + _item_ids(work, "P175")[:1]) if kind == "klassik" \
        else (_item_ids(work, "P175")[:1] + _item_ids(work, "P86")[:1])
    ents = _entities(people, "labels|sitelinks") if people else {}

    jobs = []
    for ent, intro, limit in [(work, False, 5000)] + [(ents[p], True, 1500) for p in people if p in ents]:
        for lang in ("de", "en"):
            title = _sitelink(ent, f"{lang}wiki")
            if title:
                jobs.append((lang, title, intro, limit))
                break
    texts = _parallel(*[(lambda j=j: (j, _extract(j[0], j[1], j[2], j[3]))) for j in jobs])
    parts = []
    for item in texts:
        if not item:
            continue
        (lang, title, _, _), text = item
        if text:
            src = "deutsche" if lang == "de" else "englische"
            parts.append(f"[{src} Wikipedia: {title}]\n{text}")
    return "\n\n".join(parts)
