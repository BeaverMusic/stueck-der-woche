#!/usr/bin/env bash
# Startet „Stück der Woche“.  Mit  ./start.sh --browser  als Tab im Standardbrowser.
cd "$(dirname "$0")"
exec python3 stueck_der_woche.py "$@"
