# Stück der Woche

Erstellt Übersichtsblätter (DIN A5) für den Musikunterricht: Titel, Angaben,
Porträt, Infotext sowie Codes für YouTube, Spotify und Apple Music.

Stand: **Version 6.6** – alle Etappen fertig: Editor, Live-Vorschau, Speichern,
PDF-Export, Angaben und Porträts aus Wikipedia/Wikidata/Commons, Aufnahmen von
YouTube, Spotify und Apple Music, Infotext-Vorschläge per KI (Claude-Abo,
Claude-API oder andere – auch kostenlose – Dienste), Schriften und Gestaltung
sowie Installation, Update und Deinstallation für macOS und CachyOS/Arch.

---

## Installation

Die App braucht nur **Python 3.10 oder neuer** (ohne Zusatzpakete).

Für den automatischen PDF-Export nutzt sie einen unsichtbaren Chromium:

- Ist **Chrome, Chromium, Edge, Brave oder Vivaldi** installiert, wird dieser
  genutzt – es wird nichts heruntergeladen. Die App öffnet sich dann auch
  als eigenes Fenster ohne Adressleiste.
- Sonst lädt `install.sh` einmalig einen unsichtbaren Chromium herunter
  (ca. 100 MB, offizieller Download von Google, mit Ladebalken). Er liegt
  im Einstellungsordner der App, nicht im Programme-Ordner, und ist kein
  zusätzlicher Browser. Die App öffnet sich dann im Standardbrowser
  (z. B. Firefox oder Safari).
- Den eigenen Chromium kannst du auch erzwingen: `bash install.sh --chromium`
  oder in der App unter Einstellungen → Allgemein → „Chromium laden“.

### macOS – mit dem Installationsabbild (ohne Terminal)

1. **„Stueck-der-Woche-6.6.dmg“** (unter github.com/BeaverMusic/stueck-der-woche → Releases) doppelklicken. Es öffnet sich ein Fenster mit
   der App, einer Verknüpfung „Programme“ und einer kurzen Anleitung.
2. **„Stück der Woche“ doppelklicken.** Die App bietet an, sich selbst in den
   Ordner „Programme“ zu kopieren, und startet danach von dort.
   (Alternativ die App auf „Programme“ ziehen.)
3. **Beim ersten Öffnen** meldet macOS, die App könne nicht überprüft werden –
   sie ist nicht bei Apple registriert (das kostet eine Jahresgebühr). Dann
   „Fertig“ klicken, **Systemeinstellungen → Datenschutz & Sicherheit** öffnen,
   ganz nach unten scrollen und bei „Stück der Woche“ **„Dennoch öffnen“**
   klicken. Das ist nur einmal nötig.
4. Fehlt Python, fragt die App, ob sie es installieren soll, lädt das
   offizielle Paket von python.org, prüft dessen Signatur und installiert es
   mit der normalen Passwortabfrage von macOS.

Danach startet die App über Spotlight: **Cmd+Leertaste**, „Stück“ tippen,
Enter. (Beim ersten Start meldet sich die App dafür bei macOS an. Erscheint sie
trotzdem nicht: Systemeinstellungen → Spotlight → „Apps“ muss eingeschaltet
sein; sonst hilft meist ein Neustart des Macs.) Für ein Update einfach das neue Abbild öffnen und wieder Schritt 2 –
Blätter, Einstellungen und Schlüssel bleiben erhalten.

Das Abbild baut `python3 paket/mac/build_dmg.py` (auf dem Mac mit hdiutil,
sonst als ISO-Abbild, das macOS genauso öffnet).

### macOS – mit dem Terminal (Alternative)

1. Die ZIP-Datei entpacken (Doppelklick), z. B. in „Downloads“.
2. Im **Terminal** `cd ` eintippen (mit Leerzeichen), den Ordner
   `stueck-der-woche` ins Terminal-Fenster ziehen und Enter drücken.
3. Eintippen und Enter: `bash install.sh`

Fehlt Python (3.10 oder neuer), lädt die Einrichtung das offizielle Paket von
python.org, prüft dessen Signatur und installiert es. Dafür und beim ersten
Anlegen der App im Ordner „Programme“ fragt der Mac nach dem Passwort deines
Benutzers (beim Tippen erscheinen keine Zeichen – das ist normal).

Die App **„Stück der Woche“** liegt danach im Ordner **„Programme“** und ist
über Spotlight auffindbar: **Cmd+Leertaste**, „Stück“ tippen, Enter. Das
Programm steckt vollständig in der App. Der entpackte Ordner wird nicht mehr
gebraucht und kann gelöscht werden. Eine ältere Version unter
Benutzerordner → Programme wird dabei automatisch entfernt.

### CachyOS / Arch Linux – Variante A: install.sh (für deinen Benutzer)

1. ZIP entpacken, im Terminal in den Ordner `stueck-der-woche` wechseln.
2. `bash install.sh` ausführen. Fehlt Python, wird es per
   `sudo pacman -S python` mitinstalliert (Passwort eingeben).

Das Programm wird nach `~/.local/share/stueck-der-woche/programm` kopiert,
„Stück der Woche“ erscheint im Anwendungsmenü, und im Terminal startet die
App mit `stueck-der-woche`. Der entpackte Ordner kann danach gelöscht werden.

### CachyOS / Arch Linux – Variante B: als pacman-Paket

Wer Programme lieber über pacman verwaltet:

```
cd stueck-der-woche/paket/arch
makepkg -si
```

Das Paket installiert die App nach `/opt/stueck-der-woche` (mit Eintrag im
Anwendungsmenü und dem Befehl `stueck-der-woche`). Entfernen mit
`sudo pacman -R stueck-der-woche`. Bitte nur **eine** der beiden Varianten
nutzen, sonst steht die App zweimal im Menü.

Die Einrichtung prüft jeweils Python, sucht einen Browser und lädt bei Bedarf
den Chromium. Fehlt er (z. B. bei Variante B ohne installierten Chromium),
lässt er sich jederzeit in der App laden: Einstellungen → Allgemein →
**„Chromium laden“**.

## Update auf eine neue Version

**Am einfachsten in der App:** Gibt es auf GitHub eine neue Version, erscheint
oben der Hinweis „Version … ist da“. Ein Klick auf „Aktualisieren …“ zeigt die
Neuerungen; „Jetzt aktualisieren“ lädt die neue Version, prüft sie anhand der
veröffentlichten Prüfsumme und startet die App neu. Von Hand suchen:
Einstellungen → Hilfe & Fehler → „Jetzt nach Updates suchen“ (dort lässt sich
die automatische Suche auch abschalten). Dabei fragt die App nur bei GitHub
nach der neuesten Version; sonst wird nichts übertragen.

Ohne die Update-Funktion geht es wie bisher:

Mac: neues `.dmg` öffnen und die App doppelklicken (siehe oben). Sonst: neue
Version herunterladen, entpacken und darin wieder `bash install.sh` ausführen (bzw. bei Variante B `makepkg -si` im neuen Ordner). Eine laufende
App wird dabei automatisch beendet. **Blätter, PDFs, Einstellungen und
API-Schlüssel bleiben erhalten** – sie liegen getrennt vom Programm. Welche
Version installiert ist und wo, steht unter Einstellungen → Hilfe & Fehler.

## Deinstallieren

```
bash ~/.local/share/stueck-der-woche/programm/deinstallieren.sh          # Linux
bash /Applications/Stück\ der\ Woche.app/Contents/Resources/programm/deinstallieren.sh   # macOS
```

(Auf dem Mac geht auch einfach: App aus „Programme“ in den Papierkorb ziehen.) Das Skript fragt, ob
auch Einstellungen, Schlüssel, Zwischenspeicher und der Chromium entfernt
werden sollen. **Deine Blätter und PDFs werden nie gelöscht** – den Ordner
`Dokumente/Stück der Woche` entfernst du bei Bedarf selbst.

## Starten und Beenden

- **macOS:** Cmd+Leertaste, „Stück der Woche“ tippen, Enter – oder im
  Finder unter „Programme“ doppelklicken. Am bequemsten:
  einmal ins Dock ziehen. Es öffnet sich kein Terminal-Fenster.
- **CachyOS:** Im Anwendungsmenü „Stück der Woche“ wählen oder im Terminal
  `stueck-der-woche` eingeben.

Wird das Fenster (bzw. der Browser-Tab) geschlossen, beendet sich die App nach
wenigen Sekunden von selbst; bleibt sie 30 Minuten ohne Lebenszeichen, ebenfalls.
Ruhezustand des Rechners und ein geschlossenes Terminal-Fenster beenden sie nicht.
Sollte die Verbindung trotzdem einmal abreißen, zeigt die App das oben an –
dann die App neu starten; die Seite speichert offene Änderungen danach nach.

Als Tab im normalen Browser geht es auch: `stueck-der-woche --browser`
(oder ohne Installation im entpackten Ordner: `./start.sh --browser`).

## Bedienung in Kürze

- **+ Neues Blatt** → Art wählen (Klassik, Pop/Rock, Jazz, Sonstiges).
  Die Art legt die vorgeschlagenen Felder und die Farbe fest.
- **Automatisch ausfüllen:** Stück, Person oder Band eingeben (z. B.
  „Mozart Violinkonzert Nr. 5“). Gesucht wird gleichzeitig in Wikidata
  (nur Einträge mit Musikbezug) sowie in der deutschen und englischen
  Wikipedia. Treffer, deren Name die Suchwörter enthält, stehen vorn;
  Filme, Orte usw. gleichen Namens werden aussortiert. Englische
  Beschreibungen und Fachbegriffe werden automatisch übersetzt (MyMemory).
  Passenden Eintrag anklicken – es erscheinen Vorschläge (Komponist:in bzw.
  Band, Werk, Werkverzeichnis, Jahr, Epoche, Tonart, Besetzung, Album …)
  und Bilder von Wikimedia Commons mit Bildquelle und Lizenz. Nur was
  angehakt ist, wird übernommen; die Texte lassen sich vorher ändern.
  Die Angaben stehen sofort im Blatt, das Bild folgt kurz danach.
  Wikidata ist nicht immer vollständig – bitte kurz prüfen.
- Die Trefferliste bleibt beim Blatt gespeichert; alle Abfragen werden
  30 Tage zwischengespeichert, und die Vorschläge der besten Treffer werden
  schon im Hintergrund geladen.
- **Versionen suchen …** (bei „Links und Codes“): sucht gleichzeitig bei
  YouTube, Spotify und Apple Music und zeigt je Dienst die Treffer mit
  Vorschaubild, Interpret:in, Album/Jahr und Dauer. Mit ▶ lässt sich jede
  Aufnahme vorher anhören. Bei Klassik ist nichts vorausgewählt – du wählst
  die Aufnahme. Wählst du sie bei einem Dienst, markiert die App bei den
  anderen dieselbe Aufnahme („passt zur Auswahl“: gleiche Interpret:innen,
  gleiche Dauer). Auf Wunsch werden die Interpret:innen ins Feld „Aufnahme“
  eingetragen. Die Codes entstehen beim Übernehmen automatisch.
- **Infotext vorschlagen:** Unter dem Infotext auf „Text vorschlagen“ klicken.
  Die KI bekommt die Angaben des Blatts und – wenn du oben „Automatisch
  ausfüllen“ genutzt hast – die passenden Wikipedia-Artikel als Quelle. Der
  Vorschlag erscheint zuerst in einem eigenen Kasten; erst „Übernehmen“
  ersetzt deinen Text. Ein Wunsch im Feld daneben (z. B. „einfacher für
  Klasse 5“, „mehr zur Wirkung“) überarbeitet den vorhandenen Text.
  Aussagen, bei denen die KI unsicher ist, stehen unter **„Bitte prüfen“** –
  nur im Editor, nie auf dem Blatt.
- **Bild fehlt?** Die App sucht automatisch bei weiteren beteiligten
  Personen und per Namenssuche. Unter „Bild“ gibt es außerdem
  „Auf Commons suchen …“ für eine eigene Suche.
- Alles wird **automatisch gespeichert** (zusätzlich: Strg/Cmd + S).
- **Angaben:** Bezeichnung und Inhalt frei änderbar. Zum Sortieren am
  Griff ☰ links ziehen (oder den Griff anklicken und mit den Pfeiltasten
  verschieben). „breit“ = über die ganze Breite, „zeigen“ = auf dem Blatt
  sichtbar. Leere Felder erscheinen nicht auf dem Blatt.
- **Ladeanzeige:** Dauert etwas länger, tanzen kleine Noten – oben in der
  Leiste und an der Stelle, an der gerade gearbeitet wird.
- **Infotext:** Der Zähler wird grün bei 80–150 Wörtern.
  Eine Leerzeile beginnt einen neuen Absatz.
- **Infotext-Größe:** Unter dem Infotext lässt sich die Schriftgröße nur für
  dieses Blatt ändern (z. B. kleiner bei einem langen Text). „Schriften für
  alle Blätter …“ öffnet die Einstellungen im Reiter „Blatt & Schrift“.
- **Bild:** Bild wählen, Ausschnitt mit den Reglern einstellen (füllt das Bild
  den Rahmen in einer Richtung genau aus, lässt es sich dorthin erst nach dem
  Vergrößern verschieben – die App zeigt dann einen Hinweis),
  Bildquelle eintragen (Urheber:in · Lizenz · via Wikimedia Commons).
  **↺ Zurücksetzen** stellt Ausschnitt und Vergrößerung wieder auf die
  Ausgangswerte.
- **Links:** Link einfügen – der Code entsteht automatisch.
  Der Spotify-Code wird bei Spotify abgerufen und braucht Internet.
- Wird das Blatt zu voll, erscheint über der Vorschau ein Hinweis.
- **PDF digital (A5):** ein Blatt pro PDF, zum Verteilen.
- **PDF zum Drucken (A4):** zwei A5-Blätter nebeneinander auf A4 quer, mit
  Schnittlinie – dasselbe Blatt zweimal oder zwei verschiedene.
- **Drucken …:** öffnet den Druckdialog des Browsers (A4 mit zwei Blättern
  oder A5). Dort direkt drucken oder „Als PDF speichern“ wählen. Funktioniert
  auch ganz ohne Chromium. Falls Farben fehlen: „Hintergrundgrafiken“
  einschalten.

## Schlüssel für YouTube und Spotify einrichten

Für „Versionen suchen …“ braucht die App je einen Schlüssel für YouTube und
Spotify. Apple Music funktioniert ohne. Ohne Schlüssel geht es auch: Dann
öffnet „im Browser suchen“ die Suche, und du fügst den Link von Hand ein.
Die Schlüssel trägst du in der App unter **Einstellungen (Zahnrad) → Reiter
Musikdienste** ein und prüfst sie dort mit **Testen**. Sie werden nur auf
deinem Rechner gespeichert.

**Am einfachsten geht es direkt in der App:** Dort steht über jedem Feld eine
Schritt-für-Schritt-Anleitung, und Knöpfe öffnen jeweils genau die richtige
Seite bei Google bzw. Spotify. Hier dieselben Schritte zum Nachlesen:

### YouTube (kostenlos, ca. 5 Minuten)

1. <https://console.cloud.google.com> öffnen und mit einem Google-Konto anmelden.
2. Oben auf die Projektauswahl klicken → **Neues Projekt** → Name z. B.
   „Stück der Woche“ → **Erstellen**. Danach dieses Projekt auswählen.
3. Links im Menü **APIs & Dienste → Bibliothek**, nach
   **„YouTube Data API v3“** suchen und **Aktivieren** klicken.
4. **APIs & Dienste → Anmeldedaten → Anmeldedaten erstellen → API-Schlüssel**.
   Den angezeigten Schlüssel kopieren.
5. Empfohlen: Beim Schlüssel auf **Bearbeiten** → unter „API-Einschränkungen“
   **Schlüssel einschränken** → nur „YouTube Data API v3“ auswählen → Speichern.
6. In der App bei „YouTube-API-Schlüssel“ einfügen und **Testen**.

Das kostenlose Tageskontingent reicht für etwa 100 Suchen pro Tag.
Wiederholte Suchen kommen aus dem Zwischenspeicher und zählen nicht.

### Spotify (benötigt Spotify Premium, ca. 5 Minuten)

1. <https://developer.spotify.com/dashboard> öffnen und mit dem
   Spotify-Konto anmelden, das Premium hat. Beim ersten Mal die
   Entwickler-Bedingungen bestätigen.
2. **Create app** klicken und ausfüllen:
   - App name: z. B. „Stück der Woche“
   - App description: z. B. „Übersichtsblätter für den Musikunterricht“
   - Redirect URI: `http://127.0.0.1:47110/callback` eintragen und
     **Add** klicken (wird nicht genutzt, ist aber Pflicht)
   - Bei „Which API/SDKs are you planning to use?“ **Web API** anhaken
   - Bedingungen bestätigen → **Save**
3. In der neuen App auf **Settings** gehen. Dort stehen die **Client ID** und
   unter **View client secret** das **Client secret**.
4. Beides in der App eintragen und **Testen**.

Hinweis: Spotify verlangt seit Februar 2026 für solche Entwickler-Apps ein
aktives Premium-Abo des Kontos, dem die App gehört. Endet das Abo, findet die
App bei Spotify nichts mehr – die anderen Dienste funktionieren weiter.

## KI-Infotexte einrichten

Über das Zahnrad ⚙ neben „Text vorschlagen“ (oder Einstellungen → Reiter „KI-Anbindung“)
wählst du den Anbieter. Mit **Testen** prüfst du die Einrichtung.

### Google Gemini (Standard, kostenlos, ca. 2 Minuten)

Voreingestellt und empfohlen – es braucht nur einen Schlüssel:

1. In der App bei „KI-Anbindung“ auf **Google AI Studio öffnen** klicken
   (oder <https://aistudio.google.com/apikey>) und mit einem Google-Konto anmelden.
2. **API-Schlüssel erstellen** klicken; fragt Google nach einem Projekt, ein
   neues anlegen lassen.
3. Den Schlüssel (beginnt mit „AIza…“) in der App einfügen und **Testen**.

Das Modell wählt die App selbst (das jeweils aktuelle „Gemini Flash“). Schaltet
Google ein Modell ab, weicht sie automatisch auf ein verfügbares aus. Im
kostenlosen Kontingent darf Google die Anfragen zur Verbesserung seiner Dienste
nutzen – übermittelt werden nur Angaben zum Stück und Wikipedia-Auszüge.

### Apple Intelligence (nur Mac, ohne Schlüssel)

Kostenlos, ohne Konto und ohne Schlüssel – auf Macs mit Apple-Chip, auf denen
Apple Intelligence bereitsteht. Prüfen: In „Kurzbefehle“ links auf „Galerie“
klicken – gibt es dort den Bereich „Apple Intelligence“ (z. B. mit „Haiku“),
ist alles da.
Die App nutzt dafür einen Kurzbefehl, den man einmal anlegt – die genaue
Anleitung mit Knopf „Kurzbefehle öffnen“ steht in der App unter
„KI-Anbindung“, wenn dort „Apple Intelligence“ gewählt ist. Kurz:

1. In „Kurzbefehle“ → Galerie → „Apple Intelligence“ den Kurzbefehl **„Haiku“**
   hinzufügen, dann duplizieren und die Kopie **„Stück der Woche KI“** nennen.
2. Darin die erste Aktion „Nach Text … fragen“ löschen.
3. In **„Cloud-Modell verwenden“** den Text löschen und per Rechtsklick →
   „Variable einfügen“ die **„Kurzbefehleingabe“** einsetzen.
4. „Antwort anzeigen“ durch **„Stoppen und ausgeben“** mit der **„Antwort“** ersetzen.
5. In der App **Testen** – sie zeigt auch an, ob sie den Kurzbefehl findet.

Die Texte sind etwas schlichter als bei Gemini oder Claude; lange
Wikipedia-Auszüge werden gekürzt, weil das Modell nur kürzere Anfragen verarbeitet.

### Claude-Abo über Claude Code (für Claude Pro/Max)

Läuft über dein Claude-Abo, ohne Zusatzkosten; zählt zu den Nutzungslimits.

1. Claude Code installieren – im Terminal:
   `curl -fsSL https://claude.ai/install.sh | bash`
   (macOS alternativ: `brew install --cask claude-code`)
2. Einmal `claude` im Terminal starten und im Browser mit deinem
   Claude-Konto anmelden. Danach das Terminal schließen.
3. In der App „Claude-Abo (über Claude Code)“ wählen und **Testen**.
   Wird `claude` nicht gefunden, den Pfad eintragen (meist `~/.local/bin/claude`).

Hinweis: Ist die Umgebungsvariable `ANTHROPIC_API_KEY` gesetzt, nutzt Claude
Code diesen Schlüssel statt des Abos.

Sicherheit: Die App startet Claude Code ohne Werkzeuge – es darf nur Text
schreiben, keine Befehle ausführen, keine Dateien lesen und keine
Erweiterungen nutzen. So können Anweisungen, die jemand in einen
Wikipedia-Artikel schmuggelt, auf deinem Rechner nichts anrichten.

### Claude-API mit Schlüssel

Schlüssel unter <https://console.anthropic.com> anlegen (nach Verbrauch
abgerechnet, getrennt vom Abo; bei Max-Plänen können monatliche API-Guthaben
enthalten sein).

### Andere Dienste – auch kostenlos oder lokal

„Anderer Dienst“ wählen und eine Voreinstellung nehmen. Mit **Modelle laden**
holt die App die aktuell verfügbaren Modelle des Dienstes.

- **Google Gemini:** kostenloser Schlüssel unter <https://aistudio.google.com/apikey>
- **Groq:** kostenloser Schlüssel unter <https://console.groq.com/keys>
- **OpenRouter:** Schlüssel unter <https://openrouter.ai/keys>; Modelle mit
  „:free“ im Namen sind kostenlos (begrenzte Anzahl pro Tag)
- **Mistral:** kostenloser Schlüssel unter <https://console.mistral.ai/api-keys>
- **Ollama / LM Studio:** laufen komplett auf deinem Rechner, ohne Schlüssel und
  ohne Internet – brauchen aber ein heruntergeladenes Modell (mehrere GB) und
  einen leistungsfähigen Rechner.

Kostenlose Kontingente und Modellnamen ändern sich häufig. Bei manchen
kostenlosen Angeboten dürfen die Anbieter die Anfragen zum Training nutzen –
hier geht es nur um Informationen zu Musikstücken, aber gut zu wissen.
Die Qualität der Texte ist je nach Modell sehr unterschiedlich; kleine Modelle
erfinden eher etwas. Die Prüfliste ist deshalb bei jedem Anbieter wichtig.

### Aufgabe für die KI anpassen

Im KI-Dialog unter „Aufgabe für die KI (Vorlage) bearbeiten“ lässt sich der
Auftrag ändern, z. B. Länge, Ton oder Schwerpunkte. „Standard wiederherstellen“
setzt ihn zurück.

## Wo liegen meine Daten?

Standardmäßig in `Dokumente/Stück der Woche/`:

- `blaetter/` – ein Ordner pro Blatt (Angaben und Bild)
- `PDF/` – die exportierten PDFs
- `papierkorb/` – gelöschte Blätter (zum Wiederherstellen zurück nach
  `blaetter/` verschieben)

Zum Sichern einfach diesen Ordner kopieren.

## Einstellungen

Das Zahnrad oben rechts öffnet die Einstellungen mit sechs Reitern:

- **Allgemein:** Kopfzeile (z. B. „Musik · Name“), Ordner für Blätter und PDFs –
  jeweils mit **Auswählen …** (öffnet den Finder bzw. Dateimanager) und
  **Öffnen** –, ggf. Pfad zum Browser
- **Blatt & Schrift:** Schriften für Titel, Angaben und Infotext sowie die
  Schriftgrößen (in Punkt) für alle Blätter, mit Live-Vorschau und
  „Standard wiederherstellen“. Zur Wahl stehen u. a. gut lesbare Schriften
  wie Atkinson Hyperlegible und Andika (Leseschrift für Kinder).
- **Wikipedia:** Kontakt-E-Mail, „Verbindungen prüfen“, Zwischenspeicher leeren
- **Musikdienste:** Schlüssel für YouTube und Spotify, jeweils mit „Testen“
  (Apple Music braucht keinen Schlüssel)
- **KI-Anbindung:** Anbieter, Modell, Schlüssel, Aufgabe für die KI
  (das Zahnrad ⚙ neben „Text vorschlagen“ öffnet direkt diesen Reiter)
- **Hilfe & Fehler:** Version, Fehlerprotokoll, Verbindungen prüfen

**Speichern** übernimmt die Einstellungen und lässt das Fenster offen.
**Schließen** (oder Esc) schließt es; gibt es noch nicht gespeicherte
Änderungen, fragt die App nach („Speichern und schließen“ oder „Verwerfen“).

Unter Linux nutzt „Auswählen …“ je nach Desktop `kdialog` (KDE) oder
`zenity` (GNOME); fehlt beides, hilft `sudo pacman -S kdialog` bzw.
`sudo pacman -S zenity` – oder den Pfad einfach eintippen.

Bei Problemen die Datei `protokoll.txt` (Hilfe & Fehler → Fehlerprotokoll)
mitschicken, dann lässt sich der Fehler genau finden.

## Hinweise

- **„Wikipedia/Wikidata antwortet gerade nicht“:** Die App wiederholt Anfragen
  automatisch und stellt höchstens zwei gleichzeitig. Bleibt der Fehler, in den
  Einstellungen (Reiter „Wikipedia“) **„Verbindungen prüfen“** klicken und das Ergebnis (oder die
  `protokoll.txt`) weitergeben. Dort lässt sich auch eine Kontakt-E-Mail für
  Wikipedia eintragen, worum Wikimedia Programme bittet.
- **macOS, Fehler „CERTIFICATE_VERIFY_FAILED“:** Das Python von python.org
  bringt keine eigenen Sicherheitszertifikate mit. Die App nutzt dann
  automatisch die Zertifikate von macOS. Sollte der Fehler trotzdem
  auftreten: im Finder unter „Programme → Python 3.x“ einmal
  „Install Certificates.command“ doppelklicken.

- Die Schriften werden bei Google Fonts geladen (dabei sieht Google, wie bei
  jeder Webseite, deine IP-Adresse). Ohne Internet wird eine Ersatzschrift
  verwendet. Wer das vermeiden möchte, wählt unter „Blatt & Schrift“ die
  Systemschriften Georgia und Helvetica/Arial.
- **Sicherheit:** Die App läuft nur auf deinem Rechner; der eingebaute Server
  ist von außen nicht erreichbar und beantwortet nur Anfragen der App selbst
  (Webseiten im Internet können ihn nicht fernsteuern). Die Oberfläche darf
  nur eigene Programmteile ausführen; Codes (SVG) und Bilder werden vor dem
  Speichern geprüft. Die Einstellungsdatei mit den API-Schlüsseln ist nur für
  deinen Benutzer lesbar, und im Fehlerprotokoll werden Schlüssel unkenntlich
  gemacht. Die Schlüssel werden nur an den jeweiligen Dienst gesendet.
- Der heruntergeladene Chromium liegt unter
  `~/.config/stueck-der-woche/chromium` (Linux) bzw.
  `~/Library/Application Support/StueckDerWoche/chromium` (macOS).
  Zum Entfernen einfach diesen Ordner löschen.
