# Stück der Woche

Eine kleine App für den Musikunterricht: Sie erstellt Übersichtsblätter (DIN A5)
zu einem Musikstück – mit Titel, Angaben, Porträt (Wikimedia Commons), einem
KI-Vorschlag für den Infotext und Codes für YouTube, Spotify und Apple Music.
Die Blätter lassen sich als PDF ausgeben, einzeln oder zu zweit auf A4.

## Herunterladen

Unter **[Releases](../../releases/latest)**:

- **Mac:** `Stück der Woche <Version>.dmg` öffnen und die App doppelklicken – sie
  kopiert sich selbst in „Programme“. Beim ersten Öffnen ggf. unter
  Systemeinstellungen → Datenschutz & Sicherheit „Dennoch öffnen“ wählen.
- **Linux (z. B. CachyOS/Arch):** `stueck-der-woche-<Version>.zip` entpacken und im
  Ordner `bash install.sh` ausführen.

Installierte Apps melden neue Versionen selbst und spielen sie auf Wunsch ein.

## Gut zu wissen

- Läuft lokal auf dem eigenen Rechner; braucht nur Python 3 (wird auf dem Mac bei
  Bedarf automatisch installiert).
- API-Schlüssel (YouTube, Spotify, KI) werden nur lokal gespeichert, nie im Code.
- Ausführliche Anleitung: [LIESMICH.md](LIESMICH.md) · Änderungen: [NEUERUNGEN.md](NEUERUNGEN.md)

## Neue Version veröffentlichen

1. Versionsnummer in `app/__init__.py` und `web/app.js` (`APP_VERSION`) erhöhen und
   einen Eintrag in `NEUERUNGEN.md` ergänzen.
2. Auf GitHub **Actions → „Veröffentlichung“ → „Run workflow“** klicken. Nach etwa
   drei Minuten liegen .dmg, ZIP und Prüfsummen unter „Releases“ – und alle
   installierten Apps bieten das Update an.

## Lizenz

Copyright © 2026 BeaverMusic

Lizenziert unter der **European Union Public Licence (EUPL) v. 1.2** – siehe
[LICENSE](LICENSE). Die App darf genutzt, verändert und weitergegeben werden;
wer veränderte Fassungen weitergibt, muss deren Quellcode ebenfalls unter der
EUPL (oder einer der darin genannten verträglichen Lizenzen) bereitstellen.
Die EUPL gibt es in allen EU-Amtssprachen mit gleicher Gültigkeit, auch auf
Deutsch: <https://interoperable-europe.ec.europa.eu/collection/eupl/eupl-text-eupl-12>

Enthaltener fremder Code: `app/qrencoder.py` (aus ReportLab) steht unter der
MIT-Lizenz; der Hinweis dazu steht in der Datei selbst.
