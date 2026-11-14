# Neuerungen

## 0.6.9
Sicherheit
- Zugriffsschutz: Die App beantwortet nur noch Anfragen des Fensters, das sie selbst geöffnet hat. Andere Programme und andere Benutzer desselben Rechners kommen nicht mehr an Blätter, Einstellungen und API-Schlüssel. Du musst dafür nichts eingeben. Wer die Adresse der App von Hand im Browser öffnet, sieht einen Hinweis und startet die App einfach über ihr Symbol.
- Nach dem Update auf diese Version öffnet sich einmalig ein neues Fenster; das bisherige zeigt den Hinweis „nicht verbunden“ und kann geschlossen werden.
- Die Kontakt-E-Mail für Wikipedia geht nur noch an die Wikimedia-Dienste (nicht mehr an den Übersetzungsdienst).
- Bilder werden nur noch verschlüsselt geladen, der YouTube-Schlüssel steht nicht mehr in der Adresse, und ein KI-Schlüssel wird nie unverschlüsselt ins Internet geschickt.
- Mac: Das Kopieren nach „Programme“ und die Python-Installation übergeben Pfade sicher; die Signatur des Python-Pakets wird strenger geprüft.

Neu
- Schriften liegen der App bei: nichts wird mehr bei Google Fonts geladen, und Vorschau und PDF sehen auch ohne Internet gleich aus.
- Papierkorb (unten links): gelöschte Blätter wiederherstellen oder endgültig löschen; direkt nach dem Löschen genügt „Rückgängig“.
- Eigene Angaben je Typ: Unter „+ Neues Blatt“ lässt sich für jeden Typ festlegen, welche Angaben neue Blätter bekommen (z. B. Filmmusik: Komponist, Film, Jahr) und ob die Suche sich wie bei Klassik, Pop/Rock oder Jazz verhält.
- Helles oder dunkles Erscheinungsbild – oder wie das System (Einstellungen → Allgemein). Die Blätter bleiben weiß.
- Liste links: Sortierung wählbar (zuletzt bearbeitet, zuletzt angelegt, Titel A–Z), mit Datum.
- „Text vorschlagen“ lässt sich abbrechen.
- Ist der Spotify-Code nicht abrufbar, entsteht ersatzweise ein QR-Code.
- PDF-Export fragt nach, bevor er eine gleichnamige Datei ersetzt („Ersetzen“ oder „Beide behalten“).
- Der geladene Chromium für den PDF-Export wird alle zwei Monate erneuert (und auf Knopfdruck unter Einstellungen → Allgemein).

Verbessert und behoben
- Die letzte Änderung geht nicht mehr verloren, wenn das Fenster direkt nach dem Tippen geschlossen wird.
- QR-Codes haben jetzt den weißen Rand, den die Norm verlangt (lassen sich zuverlässiger scannen); bestehende Blätter werden beim Öffnen und beim PDF-Export automatisch angepasst.
- Auf großen Bildschirmen wurde die Vorschau unten abgeschnitten.
- Gleichzeitiges Speichern der Einstellungen und „Zwischenspeicher leeren“ während einer Suche führen nicht mehr zu Fehlern; Fehlermeldungen sind verständlicher.
- KI „Anderer Dienst“: Modelle, die keine eigene „temperature“ zulassen, funktionieren jetzt.
- Überall heißt es „Typ“ (statt teils „Art“); veraltete Hinweise zum Update entfernt.
- Der Zwischenspeicher räumt alte Einträge selbst weg; der YouTube-Test verbraucht kaum noch Tageskontingent; Linux: schnellerer Zugriff auf den Dokumente-Ordner.
- Schlüsselfelder in den Einstellungen sind jetzt so breit wie die übrigen Felder.
- Mac: Die Installation aus dem .dmg schlägt nicht mehr fehl, wenn die Datei nicht aus dem Internet geladen wurde (z. B. vom USB-Stick).
- Nach dem Öffnen der Einstellungen schrieben spätere Dialoge unnötige Fehler ins Fehlerprotokoll.

## 0.6.1.2
- Alle Typen sind bearbeitbar – auch Klassik, Pop/Rock, Jazz und Sonstiges: Klick auf den Farbpunkt ändert Name und Farbe, „Standard“ stellt die Werkseinstellung wieder her.
- Das × entfernt jeden Typ: eigene werden gelöscht, eingebaute nur ausgeblendet („Ausgeblendete Typen wiederherstellen“). Blätter bleiben immer erhalten.
- Neu gestaltetes Kreuz: rund, innerhalb der Kachel, mit Rückfrage „Entfernen?“.

## 0.6.1.1
- Eigene Typen lassen sich nachträglich ändern: Im Dialog „+ Neues Blatt“ auf den farbigen Punkt eines eigenen Typs klicken – eine neue Farbe wird sofort übernommen, der Name mit „Fertig“. Bestehende Blätter behalten ihre Farbe.

## 0.6.1
- Mac: Die App startet nach einem Update wieder zuverlässig. Sie signiert sich nicht mehr selbst (eine solche Signatur passte nach Updates nicht mehr zum Inhalt); eine alte Signatur entfernt sie beim Start automatisch.
- Mac: genaueres Startprotokoll in `ausgabe.txt`.
- Hinweis: Wer 0.6.0.1 oder älter installiert hat, installiert 0.6.1 bitte einmal über das .dmg – danach funktionieren Updates wieder über den Knopf in der App.

## 0.6.0.1
- Das **+** zum Anlegen eines neuen Typs im Dialog „Neues Blatt“ ist jetzt umrandet und dadurch besser zu erkennen.

## 0.6
- Eigene Typen von Stücken: Beim „+ Neues Blatt“ legt das kleine **+** einen neuen Typ an (z. B. „Filmmusik“) – Name eintippen, Farbe wählen, fertig. Das Blatt wird gleich mit diesem Typ erstellt.
- Eigene Typen erscheinen im Filter links und in der Auswahl im Editor. Entfernen über das kleine × an der Kachel (die Blätter bleiben erhalten).
- Neue Versionsnummern: ab jetzt 0.6 (statt 6.x). Bereits installierte Versionen 6.x bitte einmal von Hand durch 0.6 ersetzen.
- Mac: Die App öffnet sich zuverlässiger (Fenster über „open“, Anmelden bei macOS erst nach dem Start).

## Vorgeschichte (Versionen 6.x)

### 6.6
- Updates direkt in der App: Neue Versionen erscheinen oben als Hinweis und lassen sich mit einem Klick einspielen (Blätter, Einstellungen und Schlüssel bleiben erhalten).
- Einstellungen → Hilfe & Fehler: „Jetzt nach Updates suchen“ und Schalter für die automatische Suche.
- Die Standard-Kopfzeile lautet jetzt neutral „Musik“ (eigener Text wie bisher unter Einstellungen → Allgemein).

### 6.5
- Apple Intelligence als KI ohne Schlüssel (Mac), Anleitung über den Kurzbefehl „Haiku“.

### 6.3
- Google Gemini als empfohlene Standard-KI; Fehlermeldungen von Google werden richtig angezeigt.
- Schritt-für-Schritt-Anleitungen für Gemini-, YouTube- und Spotify-Schlüssel.
