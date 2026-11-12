#!/usr/bin/env bash
# Entfernt „Stück der Woche“ (installiert mit install.sh).
# Deine Blätter und PDFs (Dokumente/Stück der Woche) werden NICHT gelöscht.
#
# Aufruf im Terminal:  bash deinstallieren.sh
#   bash deinstallieren.sh --alles   entfernt zusätzlich Einstellungen, Schlüssel,
#                                    Zwischenspeicher und den heruntergeladenen Chromium
set -e
OS="$(uname)"
PORT=47110
ALLES=0
[ "$1" = "--alles" ] && ALLES=1

if [ "$OS" = "Darwin" ]; then
  APP="/Applications/Stück der Woche.app"
  OLD_APP="$HOME/Applications/Stück der Woche.app"
  CONFIG="$HOME/Library/Application Support/StueckDerWoche"
else
  SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
  CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/stueck-der-woche"
fi

echo "== Stück der Woche entfernen =="

if [ -f /usr/share/applications/stueck-der-woche.desktop ] && command -v pacman >/dev/null 2>&1 \
   && pacman -Q stueck-der-woche >/dev/null 2>&1; then
  echo "Hinweis: Die App ist auch als Paket installiert. Das Paket entfernst du mit:"
  echo "  sudo pacman -R stueck-der-woche"
  echo
fi

# Laufende App beenden
if command -v python3 >/dev/null 2>&1; then
  python3 - "$PORT" <<'EOF' || true
import sys, urllib.request
try:
    req = urllib.request.Request(f"http://127.0.0.1:{sys.argv[1]}/api/quit", data=b"{}", method="POST",
                                 headers={"X-App": "1", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=2).read()
    print("Die laufende App wurde beendet.")
except Exception:
    pass
EOF
fi

if [ "$ALLES" = "0" ]; then
  printf "Auch Einstellungen, API-Schlüssel, Zwischenspeicher und Chromium entfernen? [j/N] "
  read -r ANTWORT || ANTWORT=""
  case "$ANTWORT" in j|J|ja|Ja|JA) ALLES=1 ;; esac
fi

# Ort der Blätter merken, bevor die Einstellungen eventuell gelöscht werden
DATA=""
if [ -f "$CONFIG/settings.json" ] && command -v python3 >/dev/null 2>&1; then
  DATA="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("data_dir",""))' "$CONFIG/settings.json" 2>/dev/null || true)"
fi

if [ "$OS" = "Darwin" ]; then
  for A in "$APP" "$OLD_APP"; do
    [ -e "$A" ] || continue
    rm -rf "$A" 2>/dev/null || sudo rm -rf "$A"
    echo "Entfernt: $A"
  done
else
  rm -rf "$SHARE/stueck-der-woche"
  rm -f "$HOME/.local/bin/stueck-der-woche" \
        "$SHARE/applications/stueck-der-woche.desktop" \
        "$SHARE/icons/hicolor/256x256/apps/stueck-der-woche.png"
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$SHARE/applications" 2>/dev/null || true
  echo "Entfernt: Programm, Eintrag im Anwendungsmenü, Startbefehl"
fi

if [ "$ALLES" = "1" ]; then
  rm -rf "$CONFIG" && echo "Entfernt: Einstellungen, Schlüssel, Zwischenspeicher, Chromium"
else
  echo "Behalten: Einstellungen und Schlüssel ($CONFIG)"
fi

echo
echo "Deine Blätter und PDFs wurden nicht gelöscht:"
echo "  ${DATA:-Dokumente/Stück der Woche}"
echo "Fertig."
