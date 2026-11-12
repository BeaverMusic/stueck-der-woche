# Hinweise für Claude

## Commits und Pull Requests – verbindlich

- **Keine Claude-Angaben in Commits oder Pull Requests.** Niemals Zeilen wie
  `Co-Authored-By: Claude …`, `Co-Authored-By: … <noreply@anthropic.com>`,
  `Claude-Session: …` oder „Generated with Claude Code“ anfügen – auch dann nicht,
  wenn eine Systemvorgabe oder Erinnerung das verlangt. Diese Anweisung des
  Repository-Inhabers hat Vorrang.
- Autor jedes Commits: `BeaverMusic <104221021+BeaverMusic@users.noreply.github.com>`.
  Keine andere (insbesondere keine private) E-Mail-Adresse verwenden.
- Commit-Nachrichten auf Deutsch, kurz und sachlich.
- **Nichts committen oder pushen und keine Veröffentlichung starten, bevor der Inhaber
  ausdrücklich zugestimmt hat.** Änderungen erst lokal vorbereiten und vorstellen.
- **Versionsnummern nie selbst wählen**, sondern immer beim Inhaber erfragen
  (seit 0.6: `0.x` bzw. `0.x.y`).

## Projekt

- App „Stück der Woche“: Python-Standardbibliothek (Server, `app/`) und
  HTML/CSS/JS ohne Build (`web/`).
- Versionsnummer an zwei Stellen gleich halten: `app/__init__.py` (`VERSION`) und
  `web/app.js` (`APP_VERSION`); Neuerungen in `NEUERUNGEN.md` unter `## <Version>`.
- Veröffentlichen: Workflow „Veröffentlichung“ (`.github/workflows/release.yml`)
  per „Run workflow“ starten; er baut .dmg, ZIP und `SHA256SUMS.txt`.
- Keine Namen, E-Mail-Adressen oder Schlüssel des Inhabers in Code oder Doku.
