"""KI-Vorschläge für den Infotext – mit austauschbaren Anbietern.

Anbieter:
- "claude_code": Claude-Abo (Pro/Max) über das installierte Claude Code (`claude -p`)
- "anthropic":   Claude-API mit eigenem Schlüssel (nach Verbrauch abgerechnet)
- "openai":      jeder OpenAI-kompatible Dienst, auch kostenlose oder lokale:
                 Google Gemini, Groq, OpenRouter, Mistral, Ollama, LM Studio …

Alle bekommen dieselbe Aufgabe (bearbeitbare Vorlage) und dieselben Quellen
(Angaben des Blatts und Wikipedia-Texte). Die Antwort enthält den Text und eine
Liste von Aussagen, die man prüfen sollte.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import storage

USER_AGENT = "StueckDerWoche/1.0 (Unterrichtsmaterial; lokale Desktop-App)"

# Voreinstellungen für OpenAI-kompatible Dienste. Modellnamen ändern sich –
# mit „Modelle laden“ holt die App die aktuelle Liste des Dienstes.
PRESETS = {
    "gemini": {"name": "Google Gemini (kostenloses Kontingent)",
               "base": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-flash-latest",
               "key_url": "https://aistudio.google.com/apikey"},
    "groq": {"name": "Groq (kostenloses Kontingent)", "base": "https://api.groq.com/openai/v1",
             "model": "llama-3.3-70b-versatile", "key_url": "https://console.groq.com/keys"},
    "openrouter": {"name": "OpenRouter (Modelle mit „:free“ kostenlos)", "base": "https://openrouter.ai/api/v1",
                   "model": "meta-llama/llama-3.3-70b-instruct:free", "key_url": "https://openrouter.ai/keys"},
    "mistral": {"name": "Mistral (kostenloses Kontingent)", "base": "https://api.mistral.ai/v1",
                "model": "mistral-small-latest", "key_url": "https://console.mistral.ai/api-keys"},
    "ollama": {"name": "Ollama (lokal auf diesem Rechner)", "base": "http://localhost:11434/v1",
               "model": "llama3.1", "key_url": ""},
    "lmstudio": {"name": "LM Studio (lokal auf diesem Rechner)", "base": "http://localhost:1234/v1",
                 "model": "", "key_url": ""},
    "custom": {"name": "Anderer Dienst (OpenAI-kompatibel)", "base": "", "model": "", "key_url": ""},
}

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
# Google Gemini ist die empfohlene Standard-Anbindung: kostenlos, nur ein Schlüssel nötig.
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"  # wandert mit der jeweils aktuellen Flash-Version mit
GEMINI_KEY_URL = "https://aistudio.google.com/apikey"
# Apple Intelligence (nur Mac): über einen Kurzbefehl mit der Aktion „Modell verwenden“
DEFAULT_APPLE_SHORTCUT = "Stück der Woche KI"
APPLE_SOURCE_LIMIT = 3500  # das Modell auf dem Mac verarbeitet nur kurze Anfragen

DEFAULT_PROMPT = """Du schreibst den Infotext für ein Übersichtsblatt „Stück der Woche“ im Musikunterricht eines Gymnasiums (Klassen 5–13). Das Blatt wird ausgeteilt; der Text soll Schüler:innen neugierig machen und fachlich korrekt sein.

Stück: {TITEL}
Art: {ART}

Angaben auf dem Blatt:
{ANGABEN}

Quellen (Auszüge aus Wikipedia):
{QUELLEN}

{WUNSCH}

Anforderungen:
- Deutsch, 80–150 Wörter, verständlich, aber nicht kindlich.
- Gendergerechte Sprache mit Doppelpunkt, wo es um Personengruppen geht (z. B. Musiker:innen, Zuhörer:innen). Einzelne bekannte Personen normal benennen.
- Inhalt ohne feste Gliederung: Entstehung, Einordnung ins Schaffen der Person bzw. Band, besondere musikalische Merkmale (was man beim Hören bemerken kann), Wirkung. Fun Facts nur, wenn sie wirklich relevant und belegt sind.
- Erfinde nichts. Nutze nur, was in den Quellen steht oder in der Musikwissenschaft gesichert ist. Keine Zitate, keine Jahreszahlen oder Namen, die du nicht sicher weißt.
- Kein Titel, keine Aufzählung, keine Wiederholung der Angaben im Wortlaut; ein oder zwei Absätze.

Antworte ausschließlich mit JSON in genau dieser Form, ohne weiteren Text:
{"text": "der Infotext", "pruefen": ["Aussage, bei der du unsicher bist oder die nicht in den Quellen steht", "…"]}
Wenn alles durch die Quellen belegt ist, ist "pruefen" eine leere Liste."""


class AIError(RuntimeError):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------ Aufgabe zusammenstellen


def build_prompt(sheet: dict, sources: str, wish: str, previous: str) -> str:
    template = storage.load_settings().get("ai_prompt", "").strip() or DEFAULT_PROMPT
    kinds = {"klassik": "Klassik", "pop": "Pop/Rock", "jazz": "Jazz", "sonstiges": "Sonstiges"}
    title = " – ".join(x for x in [sheet.get("title", ""), sheet.get("subtitle", "")] if x)
    fields = "\n".join(f"- {f.get('label')}: {f.get('value')}" for f in sheet.get("fields", [])
                       if f.get("value") and f.get("show", True)) or "- (keine)"
    wish_text = ""
    if previous and wish:
        wish_text = f"Bisheriger Text:\n{previous}\n\nÜberarbeite ihn nach diesem Wunsch: {wish}"
    elif wish:
        wish_text = f"Besonderer Wunsch: {wish}"
    elif previous:
        wish_text = "Schreibe eine neue, eigenständige Fassung (nicht den bisherigen Text umformulieren)."
    values = {"TITEL": title or "(ohne Titel)", "ART": kinds.get(sheet.get("kind"), ""),
              "ANGABEN": fields, "QUELLEN": sources or "(keine Quellen gefunden – nur gesichertes Wissen verwenden)",
              "WUNSCH": wish_text}
    # nur bekannte Platzhalter ersetzen (geschweifte Klammern im JSON-Beispiel bleiben)
    return re.sub(r"\{(TITEL|ART|ANGABEN|QUELLEN|WUNSCH)\}", lambda m: values[m.group(1)], template)


def parse_answer(raw: str) -> dict:
    """Holt Text und Prüfliste aus der Antwort – auch wenn das Modell Text drumherum schreibt."""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start:end + 1])
            text = str(data.get("text", "")).strip()
            checks = [str(x).strip() for x in data.get("pruefen", []) or [] if str(x).strip()]
            if text:
                return {"text": text, "pruefen": checks}
        except Exception:
            pass
    if not raw:
        raise AIError("Die KI hat keinen Text geliefert.")
    return {"text": raw, "pruefen": ["Die Antwort hatte nicht das erwartete Format – bitte besonders sorgfältig prüfen."]}


# ------------------------------------------------------------------ Anbieter: Claude-Abo über Claude Code


def find_claude() -> str | None:
    """Sucht das Programm „claude“ – auch dort, wo es ein per Doppelklick
    gestartetes Programm nicht im Suchpfad hat."""
    custom = storage.load_settings().get("claude_path", "").strip()
    if custom and Path(custom).expanduser().is_file():
        return str(Path(custom).expanduser())
    found = shutil.which("claude")
    if found:
        return found
    home = Path.home()
    for p in [home / ".local/bin/claude", home / ".claude/local/claude", Path("/opt/homebrew/bin/claude"),
              Path("/usr/local/bin/claude"), Path("/usr/bin/claude"), home / ".npm-global/bin/claude"]:
        if p.is_file():
            return str(p)
    return None


_help_cache: dict = {}
# Werkzeuge, die Claude Code bei älteren Versionen ausdrücklich verboten werden
_ALL_TOOLS = ("Bash,Edit,MultiEdit,Write,Read,Glob,Grep,LS,WebFetch,WebSearch,NotebookEdit,NotebookRead,"
              "Task,Agent,TodoWrite,KillShell,BashOutput,SlashCommand,Skill,mcp__*")


def _claude_flags(exe: str) -> list:
    """Sicherheitsschalter: Die KI soll nur Text schreiben – keine Befehle ausführen,
    keine Dateien lesen und keine Erweiterungen (MCP) nutzen. Das schützt davor, dass
    eingeschleuste Anweisungen in Quelltexten aus dem Internet etwas auf dem Rechner tun."""
    try:
        key = (exe, Path(exe).stat().st_mtime)
    except OSError:
        key = (exe, 0)
    if key not in _help_cache:
        try:
            out = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=20).stdout
        except Exception:
            out = ""
        _help_cache.clear()
        _help_cache[key] = out
    help_text = _help_cache[key]
    flags = []
    if re.search(r"--tools\b", help_text):
        flags += ["--tools", ""]
    flags += ["--disallowedTools", _ALL_TOOLS]
    if "--strict-mcp-config" in help_text:
        flags += ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
    if "--no-session-persistence" in help_text:
        flags += ["--no-session-persistence"]
    return flags


def _claude_code(prompt: str, model: str) -> str:
    exe = find_claude()
    if not exe:
        raise AIError("Claude Code ist nicht installiert. Anleitung: LIESMICH.md, Abschnitt „KI-Infotexte“.")
    # Die Anfrage geht über die Standardeingabe – nicht als Programmargument,
    # das andere Programme in der Prozessliste sehen könnten.
    cmd = [exe, "-p", "--output-format", "json", "--max-turns", "1", *_claude_flags(exe)]
    if model:
        cmd += ["--model", model]
    env = dict(os.environ)
    env.setdefault("DISABLE_AUTOUPDATER", "1")  # kein Update mitten in einer Anfrage
    with tempfile.TemporaryDirectory(prefix="stueck-ki-") as cwd:  # leerer Arbeitsordner
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180,
                                  cwd=cwd, env=env)
        except subprocess.TimeoutExpired:
            raise AIError("Claude Code hat nicht rechtzeitig geantwortet.")
    out = (proc.stdout or "").strip()
    try:
        data = json.loads(out.splitlines()[-1] if out else "{}")
    except Exception:
        data = {}
    if data.get("type") == "result" and not data.get("is_error") and data.get("result"):
        return data["result"]
    message = str(data.get("result") or proc.stderr or out or "unbekannter Fehler").strip()
    low = message.lower()
    if "login" in low or "log in" in low or "not logged" in low or "authenticat" in low or "api key" in low:
        raise AIError("Claude Code ist nicht angemeldet. Einmal im Terminal „claude“ starten und mit dem "
                      "Claude-Konto anmelden.")
    if "limit" in low or "usage" in low:
        raise AIError("Das Nutzungslimit deines Claude-Abos ist gerade erreicht – später erneut versuchen "
                      f"oder einen anderen Anbieter wählen. ({message[:160]})")
    raise AIError(f"Claude Code meldet: {message[:300]}")


# ------------------------------------------------------------------ Anbieter: Claude-API


def _post_json(url: str, body: dict, headers: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise AIError(_http_message(exc.code, _error_text(exc)), exc.code)
    except urllib.error.URLError as exc:
        raise AIError(f"Der KI-Dienst ist nicht erreichbar ({exc.reason}). Bei lokalen Modellen: läuft das Programm?")
    except TimeoutError:
        raise AIError("Der KI-Dienst hat nicht rechtzeitig geantwortet.")


def _error_text(exc: urllib.error.HTTPError) -> str:
    """Fehlermeldung des Dienstes herausholen. Google schickt sie als Liste
    ([{"error": {...}}]), andere als Objekt – beides wird verstanden."""
    try:
        raw = exc.read().decode("utf-8", "replace")
    except Exception:
        return ""
    try:
        detail = json.loads(raw)
    except Exception:
        return re.sub(r"<[^>]+>", " ", raw)[:200].strip()
    if isinstance(detail, list):
        detail = detail[0] if detail and isinstance(detail[0], dict) else {}
    if not isinstance(detail, dict):
        return str(detail)[:200]
    err = detail.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("status") or "")
    return str(err or detail.get("message") or detail.get("detail") or "")


def _http_message(code: int, msg: str) -> str:
    if code in (401, 403) or (code == 400 and "api key" in msg.lower()):
        return f"Der Schlüssel wurde abgelehnt – bitte in den Einstellungen prüfen (vollständig kopiert?). {msg[:200]}".strip()
    if code == 404:
        return f"Modell oder Adresse nicht gefunden – mit „Modelle laden“ ein verfügbares Modell wählen. {msg[:200]}".strip()
    if code == 429:
        return f"Das Kontingent des Dienstes ist gerade aufgebraucht – später erneut versuchen. {msg[:200]}".strip()
    return f"Der KI-Dienst meldet einen Fehler (HTTP {code}). {msg[:300]}".strip()


def _anthropic(prompt: str, key: str, model: str) -> str:
    if not key:
        raise AIError("Kein Claude-API-Schlüssel hinterlegt.")
    data = _post_json("https://api.anthropic.com/v1/messages",
                      {"model": model or DEFAULT_ANTHROPIC_MODEL, "max_tokens": 1500,
                       "messages": [{"role": "user", "content": prompt}]},
                      {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


# ------------------------------------------------------------------ Anbieter: OpenAI-kompatibel


def _openai(prompt: str, base: str, key: str, model: str) -> str:
    if not base:
        raise AIError("Keine Adresse für den KI-Dienst hinterlegt.")
    if not model:
        raise AIError("Kein Modell gewählt – in den Einstellungen „Modelle laden“ und eines auswählen.")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    data = _post_json(base.rstrip("/") + "/chat/completions",
                      {"model": model, "temperature": 0.4,
                       "messages": [{"role": "user", "content": prompt}]}, headers)
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise AIError("Unerwartete Antwort des KI-Dienstes.")


def _best_gemini(models: list[str]) -> str:
    """Bestes verfügbares Gemini-Textmodell: „Flash“, keine Vorschau-/Bild-/Audio-Varianten, neueste zuerst."""
    def version(m: str):
        return [int(x) for x in re.findall(r"\d+", m)[:3]]
    bad = ("image", "audio", "tts", "live", "embedding", "vision", "thinking", "exp", "preview", "lite")
    flash = [m for m in models if m.startswith("gemini") and "flash" in m and not any(b in m for b in bad)]
    if "gemini-flash-latest" in models:
        return "gemini-flash-latest"
    return max(flash, key=version) if flash else ""


def _gemini(prompt: str, key: str, model: str) -> str:
    if not key:
        raise AIError("Noch kein Gemini-Schlüssel hinterlegt – in den Einstellungen unter „KI-Anbindung“ "
                      "eintragen (kostenlos, Anleitung dort).")
    model = model or DEFAULT_GEMINI_MODEL
    try:
        return _openai(prompt, GEMINI_BASE, key, model)
    except AIError as exc:
        text = str(exc).lower()
        model_missing = exc.status == 404 or (exc.status == 400 and "model" in text and "key" not in text)
        if not model_missing:
            raise
        # Modell gibt es nicht (mehr)? Dann ein verfügbares wählen und merken.
        try:
            best = _best_gemini(list_models(GEMINI_BASE, key))
        except AIError:
            raise exc
        if not best or best == model:
            raise exc
        storage.log("KI", f"Gemini-Modell {model} nicht verfügbar – nutze {best}")
        storage.save_settings({"gemini_model": best})
        return _openai(prompt, GEMINI_BASE, key, best)


def list_models(base: str, key: str) -> list[str]:
    if not base:
        raise AIError("Bitte zuerst die Adresse des Dienstes eintragen.")
    req = urllib.request.Request(base.rstrip("/") + "/models",
                                 headers={"User-Agent": USER_AGENT, **({"Authorization": f"Bearer {key}"} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise AIError(_http_message(exc.code, _error_text(exc)), exc.code)
    except Exception as exc:
        raise AIError(f"Der Dienst ist nicht erreichbar ({exc}). Bei lokalen Modellen: läuft das Programm?")
    ids = [str(m.get("id", "")).removeprefix("models/") for m in data.get("data", []) if m.get("id")]
    return sorted(dict.fromkeys(ids), key=str.lower)


# ------------------------------------------------------------------ Anbieter: Apple Intelligence


def _shortcuts_exe() -> str | None:
    if sys.platform != "darwin":
        return None
    return shutil.which("shortcuts") or ("/usr/bin/shortcuts" if Path("/usr/bin/shortcuts").exists() else None)


def apple_shortcut_exists(name: str) -> bool | None:
    """Gibt es den Kurzbefehl? None = lässt sich nicht prüfen."""
    exe = _shortcuts_exe()
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "list"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return None
    import unicodedata
    norm = lambda t: unicodedata.normalize("NFC", t).strip().casefold()
    return norm(name) in {norm(line) for line in out.splitlines()}


def _apple(prompt: str, name: str) -> str:
    exe = _shortcuts_exe()
    if not exe:
        raise AIError("Apple Intelligence gibt es nur auf dem Mac (ab macOS 26, mit Apple-Chip).")
    name = name or DEFAULT_APPLE_SHORTCUT
    if apple_shortcut_exists(name) is False:
        raise AIError(f"Den Kurzbefehl „{name}“ gibt es noch nicht. Bitte nach der Anleitung unter "
                      "Einstellungen → KI-Anbindung anlegen (Name genau so schreiben).")
    # Die Anfrage geht als Text über die Standardeingabe, die Antwort kommt als Text zurück.
    try:
        proc = subprocess.run([exe, "run", name, "--input-path", "-", "--output-path", "-",
                               "--output-type", "public.plain-text"],
                              input=prompt, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        raise AIError("Apple Intelligence hat nicht rechtzeitig geantwortet. Im Kurzbefehl prüfen, "
                      "dass keine Aktion mehr nachfragt (z. B. „Nach Text fragen“ gelöscht?).")
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and out:
        return out
    err = (proc.stderr or "").strip()
    low = err.lower()
    if "not available" in low or "nicht verfügbar" in low or "apple intelligence" in low:
        raise AIError("Apple Intelligence ist auf diesem Mac nicht verfügbar oder nicht eingeschaltet. "
                      "Zum Prüfen in „Kurzbefehle“ → Galerie → „Apple Intelligence“ den Kurzbefehl „Haiku“ "
                      f"ausprobieren. ({err[:160]})")
    if proc.returncode == 0:
        raise AIError("Der Kurzbefehl hat nichts zurückgegeben. Als letzte Aktion muss „Stoppen und ausgeben“ "
                      "mit der „Antwort“ stehen (nicht „Antwort anzeigen“).")
    raise AIError(f"Der Kurzbefehl meldet einen Fehler: {err[:300] or 'unbekannt'}")


# ------------------------------------------------------------------ Gemeinsamer Einstieg


def default_provider(s: dict) -> str:
    """Ohne ausdrückliche Wahl: Gemini (empfohlen), wenn ein Schlüssel da ist, sonst das Claude-Abo,
    falls Claude Code installiert ist – sonst ebenfalls Gemini (die App erklärt dann die Einrichtung)."""
    if s.get("ai_provider"):
        return s["ai_provider"]
    if s.get("gemini_key"):
        return "gemini"
    return "claude_code" if find_claude() else "gemini"


def provider_info() -> dict:
    s = storage.load_settings()
    p = default_provider(s)
    if p == "gemini":
        return {"provider": p, "label": f"Google Gemini ({s.get('gemini_model') or DEFAULT_GEMINI_MODEL})"}
    if p == "apple":
        return {"provider": p, "label": "Apple Intelligence (Kurzbefehl)"}
    if p == "claude_code":
        return {"provider": p, "label": "Claude-Abo (Claude Code)" + (f", {s.get('claude_model')}" if s.get("claude_model") else "")}
    if p == "anthropic":
        return {"provider": p, "label": f"Claude-API ({s.get('anthropic_model') or DEFAULT_ANTHROPIC_MODEL})"}
    if p == "openai":
        preset = PRESETS.get(s.get("openai_preset") or "custom", PRESETS["custom"])
        return {"provider": p, "label": f"{preset['name'].split(' (')[0]} ({s.get('openai_model') or 'kein Modell'})"}
    return {"provider": "", "label": ""}


def complete(prompt: str) -> str:
    s = storage.load_settings()
    p = default_provider(s)
    if p == "gemini":
        return _gemini(prompt, s.get("gemini_key", "").strip(), s.get("gemini_model", "").strip())
    if p == "apple":
        return _apple(prompt, s.get("apple_shortcut", "").strip())
    if p == "claude_code":
        return _claude_code(prompt, s.get("claude_model", "").strip())
    if p == "anthropic":
        return _anthropic(prompt, s.get("anthropic_key", "").strip(), s.get("anthropic_model", "").strip())
    if p == "openai":
        return _openai(prompt, s.get("openai_base", "").strip(), s.get("openai_key", "").strip(),
                       s.get("openai_model", "").strip())
    raise AIError("Noch kein KI-Anbieter eingerichtet – bitte in den Einstellungen (Zahnrad) unter „KI-Anbindung“ wählen.")


def generate(sheet: dict, sources: str, wish: str = "", previous: str = "") -> dict:
    if default_provider(storage.load_settings()) == "apple" and len(sources) > APPLE_SOURCE_LIMIT:
        cut = sources[:APPLE_SOURCE_LIMIT]
        sources = cut[: cut.rfind(" ")] + " …"
    prompt = build_prompt(sheet, sources, wish, previous)
    result = parse_answer(complete(prompt))
    result["provider"] = provider_info()["label"]
    result["words"] = len(result["text"].split())
    return result


def test() -> str:
    raw = complete('Antworte nur mit diesem JSON: {"text": "Test erfolgreich", "pruefen": []}')
    text = parse_answer(raw)["text"]
    return f"Funktioniert ({provider_info()['label']}): „{text[:60]}“"
