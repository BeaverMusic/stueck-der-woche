"""QR-Codes (YouTube, Apple Music) und Spotify-Codes als SVG."""

from __future__ import annotations

import re
import urllib.request

from . import qrencoder, storage

SPOTIFY_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]{2}/)?(track|album|playlist|episode|show|artist)/([A-Za-z0-9]{10,40})"
)


def qr_svg(url: str, border: int = 2) -> str:
    """Erzeugt einen QR-Code (Fehlerkorrektur M) als skalierbares SVG."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Kein Link angegeben")
    code = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    code.addData(url)
    code.make()
    n = code.getModuleCount()
    size = n + 2 * border
    parts = []
    for r in range(n):
        for c in range(n):
            if code.isDark(r, c):
                parts.append(f"M{c + border} {r + border}h1v1h-1z")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'shape-rendering="crispEdges" role="img" aria-label="QR-Code">'
        f'<rect width="{size}" height="{size}" fill="#ffffff"/>'
        f'<path d="{"".join(parts)}" fill="#000000"/></svg>'
    )


def spotify_uri(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("spotify:"):
        return url
    m = SPOTIFY_RE.search(url)
    if not m:
        raise ValueError("Das ist kein gültiger Spotify-Link (open.spotify.com/…)")
    return f"spotify:{m.group(1)}:{m.group(2)}"


def spotify_svg(url: str) -> str:
    """Holt den offiziellen Spotify-Code vom Spotify-Generator."""
    uri = spotify_uri(url)
    cache = storage.config_dir() / "cache" / "spotify-codes" / (re.sub(r"[^A-Za-z0-9]", "_", uri) + ".svg")
    try:
        if cache.is_file():
            return clean_svg(cache.read_text("utf-8"))
    except Exception:
        pass
    api = f"https://scannables.scdn.co/uri/plain/svg/FFFFFF/black/640/{uri}"
    req = urllib.request.Request(api, headers={"User-Agent": "StueckDerWoche/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            svg = resp.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(
            "Spotify-Code konnte nicht geladen werden (Internetverbindung?)"
        ) from exc
    try:
        svg = clean_svg(svg)
    except ValueError:
        raise RuntimeError("Spotify hat keinen gültigen Code geliefert")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(svg, "utf-8")
    except Exception:
        pass
    return svg


_SVG_TAGS = {"svg", "g", "rect", "path", "circle", "ellipse", "line", "polyline", "polygon"}
_SVG_ATTRS = {"viewBox", "width", "height", "x", "y", "rx", "ry", "cx", "cy", "r", "d", "fill", "stroke",
              "stroke-width", "stroke-linecap", "stroke-linejoin", "fill-rule", "clip-rule", "transform",
              "points", "x1", "y1", "x2", "y2", "opacity", "fill-opacity", "shape-rendering", "version"}
_SAFE_VALUE = re.compile(r"^[\w\s.,:;#%()+-]*$")


def clean_svg(svg: str) -> str:
    """Baut ein SVG aus einer Positivliste neu auf: nur einfache Formen, keine Skripte,
    Verweise, Bilder oder externen Inhalte. Alles andere wird verworfen."""
    import xml.etree.ElementTree as ET

    if len(svg) > 2_000_000 or "<!DOCTYPE" in svg.upper() or "<!ENTITY" in svg.upper():
        raise ValueError("SVG nicht zulässig")
    start = svg.find("<svg")
    if start < 0:
        raise ValueError("kein SVG")
    try:
        root = ET.fromstring(svg[start:])
    except ET.ParseError as exc:
        raise ValueError("SVG fehlerhaft") from exc

    def local(name: str) -> str:
        return name.rsplit("}", 1)[-1]

    def build(el) -> str:
        tag = local(el.tag)
        if tag not in _SVG_TAGS:
            return ""
        attrs = []
        for k, v in el.attrib.items():
            k = local(k)
            if k in _SVG_ATTRS and _SAFE_VALUE.match(v) and "url" not in v.lower():
                attrs.append(f'{k}="{v}"')
        if tag == "svg":
            attrs.insert(0, 'xmlns="http://www.w3.org/2000/svg"')
        inner = "".join(build(c) for c in el)
        return f"<{tag} {' '.join(attrs)}>{inner}</{tag}>"

    if local(root.tag) != "svg":
        raise ValueError("kein SVG")
    return build(root)


def make_code(service: str, url: str) -> str:
    url = (url or "").strip()
    if service == "spotify":
        return spotify_svg(url)
    if service == "youtube":
        if not re.search(r"(youtube\.com|youtu\.be)/", url):
            raise ValueError("Das ist kein YouTube-Link")
    elif service == "apple":
        if "music.apple.com/" not in url:
            raise ValueError("Das ist kein Apple-Music-Link (music.apple.com/…)")
    else:
        raise ValueError("Unbekannter Dienst")
    return qr_svg(url)
