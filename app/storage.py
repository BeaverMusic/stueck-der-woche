"""Speicherung von Einstellungen und Blättern.

Jedes Blatt liegt in einem eigenen Ordner:
    <Datenordner>/blaetter/<id>/sheet.json   (alle Angaben)
    <Datenordner>/blaetter/<id>/bild.jpg     (Porträt, falls vorhanden)

Gelöschte Blätter werden nicht sofort entfernt, sondern in
<Datenordner>/papierkorb/ verschoben.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ---------------------------------------------------------------- Ordner


def _documents_dir() -> Path:
    home = Path.home()
    if sys.platform.startswith("linux"):
        try:
            out = subprocess.run(
                ["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=3
            ).stdout.strip()
            if out and Path(out).is_dir() and Path(out) != home:
                return Path(out)
        except Exception:
            pass
        for name in ("Dokumente", "Documents"):
            if (home / name).is_dir():
                return home / name
    return home / "Documents"


def config_dir() -> Path:
    override = os.environ.get("STUECK_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "StueckDerWoche"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "stueck-der-woche"


DEFAULT_SETTINGS = {
    "data_dir": "",  # leer = Standard (Dokumente/Stück der Woche)
    "export_dir": "",  # leer = <Datenordner>/PDF
    "header_right": "Musik",
    "browser_path": "",  # leer = automatisch suchen
    "youtube_key": "",  # YouTube Data API v3
    "spotify_id": "",  # Spotify-Entwickler-App: Client-ID
    "spotify_secret": "",  # Spotify-Entwickler-App: Client-Secret
    # KI-Infotext
    "ai_provider": "",  # leer = Standard (Google Gemini bzw. Claude-Abo, siehe ai.default_provider)
    "gemini_key": "",
    "gemini_model": "",
    "apple_shortcut": "",
    "custom_kinds": "[]",  # eigene Arten von Stücken (JSON, siehe _clean_kinds)
    "update_auto": "1",  # beim Start nach neuen Versionen auf GitHub schauen
    "update_repo": "",  # anderes GitHub-Repository („Konto/Name“), leer = Standard  # Name des Kurzbefehls für Apple Intelligence (leer = „Stück der Woche KI“)  # "claude_code" | "anthropic" | "openai" (leer = automatisch)
    "claude_model": "",  # für Claude Code, leer = Standard
    "claude_path": "",  # Pfad zu „claude“, leer = automatisch suchen
    "anthropic_key": "",
    "anthropic_model": "",
    "openai_preset": "",  # gemini | groq | openrouter | mistral | ollama | lmstudio | custom
    "openai_base": "",
    "openai_key": "",
    "openai_model": "",
    "ai_prompt": "",  # eigene Vorlage, leer = Standard
    "wiki_contact": "",  # Kontakt (E-Mail) für die Wikimedia-Absenderkennung, optional
    # Gestaltung aller Blätter (leer = Standard)
    "font_head": "",  # Schrift für Titel
    "font_body": "",  # Schrift für Kopfzeile, Angaben und Codes
    "font_info": "",  # Schrift für den Infotext (leer = wie font_body)
    "size_title": "",  # Punkt
    "size_fields": "",
    "size_info": "",
}

# Erlaubte Schriften (müssen zu FONTS in web/sheet.js passen)
HEAD_FONTS = {"DM Serif Display", "Playfair Display", "Merriweather", "Lora", "Source Serif 4", "Fraunces",
              "Montserrat", "Georgia"}
BODY_FONTS = {"DM Sans", "Source Sans 3", "Open Sans", "Lato", "Nunito", "Atkinson Hyperlegible", "Andika",
              "Merriweather", "Lora", "Helvetica"}
SIZE_LIMITS = {"size_title": (16, 40), "size_fields": (7, 13), "size_info": (7, 13)}


BASE_KINDS = ("klassik", "pop", "jazz", "sonstiges")


def _clean_kinds(value: str) -> str:
    """Eigene Arten prüfen: feste Schlüssel, kurze Texte, gültige Farbe, bekannte Grundlage."""
    try:
        data = json.loads(value or "[]")
    except ValueError:
        return "[]"
    out, seen = [], set()
    for item in data[:20] if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", ""))
        label = " ".join(str(item.get("label", "")).split())[:40]
        if not re.fullmatch(r"k-[a-z0-9-]{1,48}", key) or key in seen or not label:
            continue
        accent = str(item.get("accent", ""))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            accent = "#1F3A5F"
        base = item.get("base") if item.get("base") in BASE_KINDS else "sonstiges"
        fields = []
        for f in item.get("fields", [])[:12] if isinstance(item.get("fields"), list) else []:
            if isinstance(f, (list, tuple)) and f:
                name, wide = f[0], (f[1] if len(f) > 1 else False)
            elif isinstance(f, dict):
                name, wide = f.get("label", ""), f.get("wide", False)
            else:
                continue
            name = " ".join(str(name).split())[:30]
            if name:
                fields.append([name, bool(wide)])
        out.append({"key": key, "label": label, "accent": accent, "base": base,
                    "fields": fields or [["Künstler:in", True]]})
        seen.add(key)
    return json.dumps(out, ensure_ascii=False)


def custom_kinds() -> list:
    try:
        return json.loads(load_settings().get("custom_kinds") or "[]")
    except ValueError:
        return []


def base_kind(kind: str) -> str:
    """Eigene Arten verhalten sich wie eine der eingebauten (für Suche und Aufnahmen)."""
    if kind in BASE_KINDS:
        return kind
    return next((k["base"] for k in custom_kinds() if k.get("key") == kind), "sonstiges")


def kind_label(kind: str) -> str:
    labels = {"klassik": "Klassik", "pop": "Pop/Rock", "jazz": "Jazz", "sonstiges": "Sonstiges"}
    if kind in labels:
        return labels[kind]
    return next((k["label"] for k in custom_kinds() if k.get("key") == kind), "Sonstiges")


def _clean_setting(key: str, value: str) -> str:
    """Prüft Gestaltungswerte – sie landen später im Blatt, daher nur Bekanntes zulassen."""
    if key == "custom_kinds":
        return _clean_kinds(value)
    if key == "font_head":
        return value if value in HEAD_FONTS else ""
    if key in ("font_body", "font_info"):
        return value if value in BODY_FONTS else ""
    if key in SIZE_LIMITS:
        try:
            num = float(value.replace(",", "."))
        except ValueError:
            return ""
        lo, hi = SIZE_LIMITS[key]
        return f"{round(min(hi, max(lo, num)) * 2) / 2:g}"
    return value


_settings_cache: dict = {"key": None, "value": None}


def load_settings() -> dict:
    """Liest die Einstellungen – aus dem Speicher, solange sich die Datei nicht geändert hat."""
    path = config_dir() / "settings.json"
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(path), None, None)
    if _settings_cache["key"] == key and _settings_cache["value"] is not None:
        return dict(_settings_cache["value"])
    settings = dict(DEFAULT_SETTINGS)
    if key[1] is not None:
        try:
            settings.update(json.loads(path.read_text("utf-8")))
        except Exception:
            pass
    _settings_cache.update(key=key, value=dict(settings))
    return settings


def save_settings(new: dict) -> dict:
    settings = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in new and isinstance(new[key], str):
            settings[key] = _clean_setting(key, new[key].strip()[:20000])
    path = config_dir() / "settings.json"
    _private_dir(path.parent)
    tmp = path.with_suffix(".tmp")
    # Die Datei enthält API-Schlüssel: nur für den eigenen Benutzer lesbar
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(settings, ensure_ascii=False, indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    _settings_cache.update(key=None, value=None)
    return settings


def _private_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass


def secure_config() -> None:
    """Beim Start: Einstellungsordner und -datei nur für den eigenen Benutzer."""
    d = config_dir()
    if d.exists():
        _private_dir(d)
        f = d / "settings.json"
        try:
            if f.exists() and f.stat().st_mode & 0o077:
                os.chmod(f, 0o600)
        except OSError:
            pass


def data_dir() -> Path:
    custom = load_settings().get("data_dir")
    d = Path(custom).expanduser() if custom else _documents_dir() / "Stück der Woche"
    (d / "blaetter").mkdir(parents=True, exist_ok=True)
    return d


def export_dir() -> Path:
    custom = load_settings().get("export_dir")
    d = Path(custom).expanduser() if custom else data_dir() / "PDF"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sheets_dir() -> Path:
    return data_dir() / "blaetter"


def sheet_dir(sheet_id: str) -> Path:
    if not ID_RE.match(sheet_id or ""):
        raise ValueError("Ungültige Blatt-ID")
    return sheets_dir() / sheet_id


# ---------------------------------------------------------------- Hilfen


def slugify(text: str) -> str:
    text = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:40] or "blatt"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(title: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{slugify(title)}-{uuid.uuid4().hex[:4]}"


# ---------------------------------------------------------------- Blätter


_summary_cache: dict = {}


def list_sheets() -> list[dict]:
    """Übersicht aller Blätter. Unveränderte Dateien werden nicht erneut gelesen."""
    result = []
    seen = set()
    for folder in sheets_dir().iterdir():
        f = folder / "sheet.json"
        try:
            st = f.stat()
        except OSError:
            continue
        key = str(f)
        seen.add(key)
        hit = _summary_cache.get(key)
        if hit and hit[0] == (st.st_mtime_ns, st.st_size):
            result.append(dict(hit[1]))
            continue
        try:
            s = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        summary = {
            "id": folder.name,
            "short_title": s.get("short_title", ""),
            "title": s.get("title", ""),
            "person": _person(s),
            "kind": s.get("kind", ""),
            "updated": s.get("updated", ""),
        }
        _summary_cache[key] = ((st.st_mtime_ns, st.st_size), summary)
        result.append(dict(summary))
    for key in list(_summary_cache):
        if key not in seen:
            del _summary_cache[key]
    result.sort(key=lambda s: s["updated"], reverse=True)
    return result


def _person(sheet: dict) -> str:
    for field in sheet.get("fields", []):
        if field.get("value"):
            return field["value"]
    return ""


def load_sheet(sheet_id: str) -> dict:
    f = sheet_dir(sheet_id) / "sheet.json"
    sheet = json.loads(f.read_text("utf-8"))
    sheet["id"] = sheet_id
    return sheet


def save_sheet(sheet: dict) -> dict:
    if not isinstance(sheet, dict):
        raise ValueError("Ungültige Daten")
    with _lock:
        sheet_id = sheet.get("id")
        if sheet_id:
            folder = sheet_dir(str(sheet_id))
            # Ein gelöschtes Blatt darf nicht durch ein verspätetes Speichern zurückkehren
            if not folder.is_dir():
                raise ValueError("Dieses Blatt wurde gelöscht.")
        else:
            sheet_id = _new_id(str(sheet.get("short_title") or sheet.get("title") or ""))
            folder = sheet_dir(sheet_id)
            folder.mkdir(parents=True, exist_ok=True)
        sheet["id"] = sheet_id
        sheet.setdefault("created", _now())
        sheet["updated"] = _now()
        tmp = folder / "sheet.json.tmp"
        tmp.write_text(json.dumps(sheet, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(folder / "sheet.json")
        return sheet


def duplicate_sheet(sheet_id: str) -> dict:
    src = sheet_dir(sheet_id)
    sheet = load_sheet(sheet_id)
    new_id = _new_id(sheet.get("short_title") or sheet.get("title"))
    shutil.copytree(src, sheet_dir(new_id))
    sheet["id"] = new_id
    sheet["created"] = _now()
    sheet["short_title"] = (sheet.get("short_title") or "") + " (Kopie)"
    return save_sheet(sheet)


def delete_sheet(sheet_id: str) -> None:
    src = sheet_dir(sheet_id)
    with _lock:
        if not src.exists():
            return
        trash = data_dir() / "papierkorb"
        trash.mkdir(exist_ok=True)
        shutil.move(str(src), str(trash / f"{sheet_id}-{uuid.uuid4().hex[:4]}"))


def save_image(sheet_id: str, ext: str, data: bytes) -> str:
    ext = image_type(data)  # Endung nach dem tatsächlichen Inhalt, nicht nach der Angabe
    if not ext:
        raise ValueError("Die Datei ist kein Bild im Format JPG, PNG, WebP oder GIF.")
    folder = sheet_dir(sheet_id)
    with _lock:
        if not folder.is_dir():
            raise ValueError("Dieses Blatt wurde gelöscht.")
        for old in folder.glob("bild.*"):
            old.unlink()
        name = f"bild{ext}"
        (folder / name).write_bytes(data)
    return name


def image_type(data: bytes) -> str:
    """Erkennt das Bildformat an den ersten Bytes."""
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ""


def log_file() -> Path:
    return config_dir() / "protokoll.txt"


SECRET_KEYS = ("youtube_key", "spotify_secret", "anthropic_key", "openai_key", "gemini_key")


def _redact(text: str) -> str:
    """API-Schlüssel tauchen nie im Protokoll auf (es soll weitergegeben werden können)."""
    try:
        settings = load_settings()
        for k in SECRET_KEYS:
            v = settings.get(k) or ""
            if len(v) >= 6:
                text = text.replace(v, "•••")
    except Exception:
        pass
    text = re.sub(r"(?i)(key=|token=|secret=|bearer\s+|x-api-key:\s*)[^\s&\"']+", r"\1•••", text)
    return text


def log(source: str, message: str) -> None:
    """Schreibt Fehler in ein Protokoll, das man bei Problemen weitergeben kann."""
    try:
        path = log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 1_000_000:
            text = path.read_text("utf-8", errors="replace")
            path.write_text(text[-500_000:], "utf-8")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{_now()}] {source}: {_redact(message.strip())}\n")
    except Exception:
        pass


def open_folder(path: Path) -> None:
    path = Path(path)
    if not path.is_dir():  # nur Ordner öffnen, niemals Dateien oder Programme
        raise ValueError("Ordner nicht gefunden")
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
