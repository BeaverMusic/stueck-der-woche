# Stück der Woche

Eine kleine App für den Musikunterricht: Sie erstellt Übersichtsblätter (DIN A5)
zu einem Musikstück – mit Titel, Angaben, Porträt (Wikimedia Commons), einem
KI-Vorschlag für den Infotext und Codes für YouTube, Spotify und Apple Music.
Die Blätter lassen sich als PDF ausgeben, einzeln oder zu zweit auf A4.

## Herunterladen

Unter **[Releases](../../releases/latest)**:

- **Mac:** `Stueck-der-Woche-<Version>.dmg` öffnen und die App doppelklicken – sie
  kopiert sich selbst in „Programme“. Beim ersten Öffnen ggf. unter
  Systemeinstellungen → Datenschutz & Sicherheit „Dennoch öffnen“ wählen.
- **Linux (z. B. CachyOS/Arch):** `stueck-der-woche-<Version>.zip` entpacken und im
  Ordner `bash install.sh` ausführen.

Installierte Apps melden neue Versionen selbst und spielen sie auf Wunsch ein.

## Gut zu wissen

- Läuft lokal auf dem eigenen Rechner; braucht nur Python 3 (wird auf dem Mac bei
  Bedarf automatisch installiert).
- API-Schlüssel (YouTube, Spotify, KI) werden nur lokal gespeichert, nie im Code.
- Die App beantwortet nur Anfragen ihres eigenen Fensters; Schriften liegen bei
  (keine Abfrage bei Google Fonts).
- Ausführliche Anleitung: [LIESMICH.md](LIESMICH.md) · Änderungen: [NEUERUNGEN.md](NEUERUNGEN.md)

## Lizenz

Copyright © 2026 BeaverMusic

Lizenziert unter der **European Union Public Licence (EUPL) v. 1.2** – siehe
[LICENSE](LICENSE). Die App darf genutzt, verändert und weitergegeben werden;
wer veränderte Fassungen weitergibt, muss deren Quellcode ebenfalls unter der
EUPL (oder einer der darin genannten verträglichen Lizenzen) bereitstellen.
Die EUPL gibt es in allen EU-Amtssprachen mit gleicher Gültigkeit, auch auf
Deutsch: <https://interoperable-europe.ec.europa.eu/collection/eupl/eupl-text-eupl-12>

Enthaltener fremder Code: `app/qrencoder.py` (aus ReportLab) steht unter der
MIT-Lizenz; der Hinweis dazu steht in der Datei selbst. Die Schriften in
`web/fonts` stehen unter der SIL Open Font License 1.1 (siehe
`web/fonts/LIZENZ.txt`).
