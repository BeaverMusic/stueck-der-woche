#!/usr/bin/env bash
# Installiert oder aktualisiert „Stück der Woche“. Die App braucht nur Python 3.
#
# Das Programm wird an einen festen Ort kopiert – danach kann der heruntergeladene
# Ordner gelöscht werden:
#   macOS:  Programme (/Applications)/Stück der Woche.app  (Programm steckt in der App)
#   Linux:  ~/.local/share/stueck-der-woche/programm  + Eintrag im Anwendungsmenü
# Blätter, Einstellungen und Schlüssel bleiben bei einem Update erhalten.
# Fehlt Python, wird es automatisch installiert (macOS: offizielles Paket von
# python.org, Linux: über den Paketmanager) – dafür fragt der Rechner nach dem Passwort.
#
# Aufruf im Terminal:  bash install.sh
#   bash install.sh --chromium   lädt den eigenen Chromium (PDF-Export) in jedem Fall
set -e
cd "$(dirname "$0")"
SRC="$(pwd)"
FORCE_CHROMIUM=0
[ "$1" = "--chromium" ] && FORCE_CHROMIUM=1
OS="$(uname)"
PORT=47110

TOTAL=5
STEP=0
progress() {
  STEP=$(( STEP + 1 ))
  local width=30 done=$(( (STEP - 1) * 30 / TOTAL )) bar="" i
  for (( i = 0; i < width; i++ )); do
    if (( i < done )); then bar+="█"; else bar+="░"; fi
  done
  printf "\n\033[1m[%s] Schritt %d/%d\033[0m  \033[1;32m%s\033[0m\n" "$bar" "$STEP" "$TOTAL" "$1"
}

if [ ! -f "$SRC/stueck_der_woche.py" ] || [ ! -d "$SRC/app" ] || [ ! -d "$SRC/web" ]; then
  echo "Bitte install.sh im entpackten Ordner „stueck-der-woche“ ausführen."
  exit 1
fi

if [ "$OS" = "Darwin" ]; then
  APP="/Applications/Stück der Woche.app"
  OLD_APP="$HOME/Applications/Stück der Woche.app"  # Ort früherer Versionen
  DEST="$APP/Contents/Resources/programm"
else
  SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
  DEST="$SHARE/stueck-der-woche/programm"
fi

echo "== Stück der Woche: Einrichtung =="

# ------------------------------------------------------------ 1. Python
progress "Python prüfen"

find_python() {
  PY=""
  local cand path
  for cand in python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
              /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    path="$(command -v "$cand" 2>/dev/null)" || continue
    # macOS: /usr/bin/python3 ist ohne Entwicklerwerkzeuge nur ein Platzhalter, der beim
    # Aufruf ein Installationsfenster öffnet – dann überspringen.
    if [ "$OS" = "Darwin" ] && [ "$path" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then
      continue
    fi
    if "$path" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      PY="$path"
      return 0
    fi
  done
  return 1
}

install_python_mac() {
  echo "Python wird jetzt automatisch installiert (offizielles Paket von python.org, ca. 70 MB)."
  local list v url pkg
  list="$(curl -fsSL https://www.python.org/ftp/python/ 2>/dev/null)" || {
    echo "python.org ist nicht erreichbar – bitte Internetverbindung prüfen."; return 1; }
  # Neueste fertige Version suchen, für die es ein macOS-Paket gibt
  for v in $(printf '%s\n' "$list" | grep -oE 'href="3\.[0-9]+\.[0-9]+/"' | grep -oE '3\.[0-9]+\.[0-9]+' | sort -t. -k1,1n -k2,2n -k3,3n -u | tail -n 8 | sort -t. -k1,1nr -k2,2nr -k3,3nr); do
    url="https://www.python.org/ftp/python/$v/python-$v-macos11.pkg"
    if curl -fsIL "$url" >/dev/null 2>&1; then break; fi
    url=""
  done
  [ -n "$url" ] || { echo "Kein passendes Python-Paket gefunden."; return 1; }
  pkg="$(mktemp -d)/python-$v.pkg"
  echo "Lade Python $v …"
  curl -fL --progress-bar -o "$pkg" "$url" || { echo "Download fehlgeschlagen."; return 1; }
  # Nur ein von der Python Software Foundation signiertes Paket installieren
  if ! pkgutil --check-signature "$pkg" 2>/dev/null | grep -q "Python Software Foundation"; then
    echo "Die Signatur des Pakets ist nicht in Ordnung – Abbruch."
    rm -f "$pkg"; return 1
  fi
  echo "Installiere Python $v – bitte gleich das Passwort deines Mac-Benutzers eingeben"
  echo "(beim Tippen erscheinen keine Zeichen, das ist normal):"
  sudo installer -pkg "$pkg" -target / || { rm -f "$pkg"; return 1; }
  rm -f "$pkg"
  # Zertifikate für sichere Verbindungen einrichten (gehört zur python.org-Installation)
  local certs
  certs="$(ls -d /Applications/Python\ 3.*/Install\ Certificates.command 2>/dev/null | tail -n 1)"
  [ -n "$certs" ] && bash "$certs" >/dev/null 2>&1 || true
}

install_python_linux() {
  echo "Python wird jetzt über den Paketmanager installiert – bitte ggf. das Passwort eingeben:"
  if command -v pacman >/dev/null 2>&1; then sudo pacman -S --needed --noconfirm python
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y python3
  elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y python3
  elif command -v zypper >/dev/null 2>&1; then sudo zypper install -y python3
  else echo "Kein bekannter Paketmanager gefunden."; return 1
  fi
}

if ! find_python; then
  echo "Python 3.10 oder neuer ist noch nicht installiert."
  if [ "$OS" = "Darwin" ]; then install_python_mac || true; else install_python_linux || true; fi
  hash -r
  if ! find_python; then
    echo
    echo "Python konnte nicht automatisch installiert werden. Bitte von Hand installieren:"
    echo "  macOS:   https://www.python.org/downloads/ (aktuelle Version)"
    echo "  CachyOS: sudo pacman -S python"
    echo "Danach  bash install.sh  erneut ausführen."
    exit 1
  fi
fi
PY="$("$PY" -c 'import sys; print(sys.executable)')"
echo "Python $("$PY" -c 'import platform; print(platform.python_version())') gefunden: $PY"
VER="$("$PY" -c 'from app import VERSION; print(VERSION)')"

# ------------------------------------------------------------ 2. Programm kopieren
progress "Programm installieren (Version $VER)"
# Läuft die App gerade, wird sie beendet – sie startet danach in der neuen Version.
"$PY" - "$PORT" <<'EOF' || true
import sys, urllib.request
port = sys.argv[1]
try:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/quit", data=b"{}", method="POST",
                                 headers={"X-App": "1", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=2).read()
    print("Die laufende App wurde beendet.")
except Exception:
    pass
EOF
if [ "$OS" = "Darwin" ] && [ ! -w "$APP" ]; then
  # Der Programme-Ordner gehört dem System. Die App wird einmalig mit Passwort angelegt
  # und gehört danach dir – Updates gehen dann ohne Passwort.
  if [ -w /Applications ] && [ ! -e "$APP" ]; then
    mkdir -p "$APP"
  else
    echo "Für den Ordner „Programme“ bitte das Passwort deines Mac-Benutzers eingeben:"
    sudo mkdir -p "$APP"
    sudo chown -R "$(id -un)" "$APP"
  fi
fi
if [ "$SRC" != "$DEST" ]; then
  TMP="$DEST.neu"
  rm -rf "$TMP"
  mkdir -p "$TMP"
  cp -R "$SRC/app" "$SRC/web" "$SRC/stueck_der_woche.py" "$SRC/LIESMICH.md" "$SRC/deinstallieren.sh" "$TMP/"
  find "$TMP" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
  chmod +x "$TMP/deinstallieren.sh"
  # Erst vollständig kopieren, dann austauschen – so bleibt nie eine halbe Version zurück.
  rm -rf "$DEST.alt"
  [ -d "$DEST" ] && mv "$DEST" "$DEST.alt"
  mv "$TMP" "$DEST"
  rm -rf "$DEST.alt"
fi
"$PY" -m compileall -q "$DEST/app" "$DEST/stueck_der_woche.py" >/dev/null 2>&1 || true
echo "Installiert in: $DEST"

# ------------------------------------------------------------ 3. Browser
progress "Browser suchen"
cd "$DEST"
FOUND=$("$PY" -c "from app import browser; print(browser.find_browser() or '')")
if [ -n "$FOUND" ]; then
  echo "Gefunden: $FOUND"
  echo "Die App öffnet sich darin als eigenes Fenster."
else
  echo "Kein Chrome/Chromium-Browser gefunden – die App öffnet sich im Standardbrowser."
fi

# ------------------------------------------------------------ 4. Chromium für PDF
progress "Chromium für den PDF-Export"
HAVE_SHELL=$("$PY" -c "from app import chromium; print(chromium.installed() or '')")
if [ -n "$HAVE_SHELL" ] && [ "$FORCE_CHROMIUM" = "0" ]; then
  echo "Bereits vorhanden: $HAVE_SHELL"
elif [ -n "$FOUND" ] && [ "$FORCE_CHROMIUM" = "0" ]; then
  echo "Nicht nötig – der PDF-Export nutzt den gefundenen Browser."
  echo "(Eigenen Chromium trotzdem laden:  bash install.sh --chromium)"
else
  if ! "$PY" -m app.chromium; then
    echo "Der PDF-Export funktioniert ohne Chromium nicht – „Drucken …“ in der App geht aber."
    echo "Später erneut versuchen mit:  bash install.sh --chromium"
  fi
fi

# ------------------------------------------------------------ 5. Starteinträge
progress "Starteinträge einrichten"

if [ "$OS" != "Darwin" ]; then
  BIN="$HOME/.local/bin"
  mkdir -p "$BIN" "$SHARE/applications" "$SHARE/icons/hicolor/256x256/apps"
  cat > "$BIN/stueck-der-woche" <<EOF
#!/bin/sh
# Startet „Stück der Woche“ (installiert von install.sh)
cd "$DEST" || exit 1
exec "$PY" stueck_der_woche.py "\$@"
EOF
  chmod +x "$BIN/stueck-der-woche"
  cp "$DEST/app/icon.png" "$SHARE/icons/hicolor/256x256/apps/stueck-der-woche.png"
  cat > "$SHARE/applications/stueck-der-woche.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Stück der Woche
Comment=Übersichtsblätter für den Musikunterricht
Exec="$BIN/stueck-der-woche"
Icon=stueck-der-woche
Terminal=false
Categories=Education;Office;
StartupNotify=false
EOF
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$SHARE/applications" 2>/dev/null || true
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "$SHARE/icons/hicolor" 2>/dev/null || true
  echo "Eintrag „Stück der Woche“ im Anwendungsmenü angelegt."
  echo "Im Terminal startet die App mit:  stueck-der-woche"
fi

if [ "$OS" = "Darwin" ]; then
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  # Startprogramm (dasselbe wie im .dmg): sucht Python und installiert es bei Bedarf
  cp "$SRC/paket/mac/StueckDerWoche" "$APP/Contents/MacOS/StueckDerWoche"
  chmod +x "$APP/Contents/MacOS/StueckDerWoche"

  cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Stück der Woche</string>
  <key>CFBundleDisplayName</key><string>Stück der Woche</string>
  <key>CFBundleIdentifier</key><string>de.musik.stueck-der-woche</string>
  <key>CFBundleExecutable</key><string>StueckDerWoche</string>
  <key>CFBundleIconFile</key><string>StueckDerWoche</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VER</string>
  <key>CFBundleVersion</key><string>$VER</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSUIElement</key><true/>
</dict></plist>
EOF

  # Symbol aus app/icon.png erzeugen
  ICONSET="$(mktemp -d)/StueckDerWoche.iconset"
  mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$DEST/app/icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    sips -z $((s*2)) $((s*2)) "$DEST/app/icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/StueckDerWoche.icns" 2>/dev/null || true
  rm -rf "$(dirname "$ICONSET")"
  xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
  touch "$APP"
  # Ältere Version aus dem Benutzer-Programmordner entfernen (sonst gibt es sie doppelt)
  if [ -d "$OLD_APP" ]; then
    rm -rf "$OLD_APP" && echo "Alte Version aus Benutzerordner → Programme entfernt."
  fi
  # Bei macOS anmelden, damit Finder und Spotlight (Cmd+Leertaste) die App sofort kennen
  # Nicht signieren (eine lokale Signatur passt nach Updates nicht mehr); alte entfernen
  if [ -d "$APP/Contents/_CodeSignature" ]; then
    codesign --remove-signature "$APP" >/dev/null 2>&1 || rm -rf "$APP/Contents/_CodeSignature"
  fi
  LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
  [ -x "$LSREG" ] && "$LSREG" -f -R "$APP" >/dev/null 2>&1 || true
  { mdimport -i "$APP" || mdimport "$APP"; } >/dev/null 2>&1 || true
  rm -f "$HOME/Library/Application Support/StueckDerWoche/angemeldet"
  echo "App „Stück der Woche“ liegt jetzt im Ordner „Programme“."
  echo "Tipp: Von dort ins Dock ziehen."
fi

printf "\n\033[1m[██████████████████████████████] fertig\033[0m\n\n"
echo "Version $VER ist installiert. Der heruntergeladene Ordner wird nicht mehr"
echo "gebraucht und kann gelöscht werden. Deine Blätter und Einstellungen bleiben."
echo "Entfernen:  bash \"$DEST/deinstallieren.sh\""
echo
if [ "$OS" = "Darwin" ]; then
  echo "Starten: Cmd+Leertaste drücken, „Stück der Woche“ tippen, Enter –"
  echo "         oder im Finder unter „Programme“ doppelklicken."
  open -R "$APP" 2>/dev/null || true
else
  echo "Starten: „Stück der Woche“ im Anwendungsmenü."
fi
