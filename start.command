#!/usr/bin/env bash
# macOS: Startet die App, ohne dass das Terminal-Fenster offen bleiben muss.
# (Bequemer: die App „Stück der Woche“ im Ordner „Programme“ bzw. Cmd+Leertaste.)
APP="/Applications/Stück der Woche.app"
[ -d "$APP" ] || APP="$HOME/Applications/Stück der Woche.app"
if [ -d "$APP" ]; then
  open "$APP"
else
  cd "$(dirname "$0")" && nohup python3 stueck_der_woche.py >/dev/null 2>&1 &
fi
echo "Stück der Woche wird gestartet – dieses Fenster kann geschlossen werden."
exit 0
