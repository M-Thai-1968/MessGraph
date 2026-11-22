"""Hilfe auf Deutsch.

Elemente: ("h", Überschrift), ("p", Absatz), ("b", Aufzählungspunkt), ("img", Bild-ID, Bildunterschrift).
Nur Zeichen bis U+00FF verwenden (Schrift der Oberfläche und PDF-Kodierung).
"""

TITLE = "MessGraph - Handbuch"
SUBTITLE = "Messdaten aus MF4, MDF, BLF, CSV, ASCII und Parquet anzeigen und vermessen"

CHAPTERS = [
    ("Überblick", [
        ("p", "MessGraph öffnet Messdateien im Format MF4, MDF, BLF, CSV, ASCII und Parquet, findet Zeitachse und Datenspalten "
              "selbst und zeigt die gewählten Signale in einem oder mehreren Graphen. Zwei senkrechte Marker vermessen "
              "die Signale: Werte, Abstände und Drift erscheinen in der Wertanzeige."),
        ("img", "uebersicht", "Bild 1: Hauptfenster"),
        ("m", "1", "Menüleiste: Datei, Graph-Optionen, Limiter, Auto und Hilfe links; Sprache am rechten Rand"),
        ("m", "2", "Dateiliste: ein Häkchen zeigt das Signal"),
        ("m", "3", "Werkzeugleiste in zwei Zeilen: Datei, Matrix, Alles anzeigen, Alle Plots löschen; darunter Marker, Achsen, Regressionslinien, Dateien vergleichen, Darstellung"),
        ("m", "4", "Graphen, hier untereinander"),
        ("m", "5", "Trenner: ziehen ändert die Breite der Dateiliste"),
        ("m", "6", "Statuszeile: Ergebnis der letzten Aktion"),
        ("h", "Die Bereiche des Hauptfensters"),
        ("b", "Menüleiste: links Datei (Projekt öffnen und speichern, Dateien öffnen, Ansicht speichern und laden) und "
              "Graph-Optionen (Grenzwerte, Berechnungen, Art der Drift-Regression), Limiter (Daten je Datei auf Grenzen von Führungssignalen kürzen), Auto (Verzeichnis zyklisch auswerten), mit etwas Abstand Hilfe (Handbuch, PDF, "
              "Screenshots); die Sprachumschaltung sitzt am rechten Rand. Unter der Menüleiste gibt es nur noch den "
              "Reiter Graph - die Hilfe öffnet sich in einem eigenen Fenster."),
        ("b", "Dateiliste links: geladene Dateien mit ihren Signalen. Ein Häkchen zeigt das Signal an."),
        ("b", "Werkzeugleiste: zwei kompakte Zeilen, Gruppen durch einen dünnen Strich getrennt. Erste Zeile - Daten und "
              "Aufteilung: Datei (für alle Graphen) | Matrix mit Anwenden, Zeilen..., Vorschlag... | Alles anzeigen, "
              "Alle Plots löschen. Zweite Zeile - Anzeige und Messen: Marker, Marker synchron | X-Achsen koppeln, "
              "Datum/Uhrzeit-Achse, Regressionslinien | Dateien vergleichen..., Darstellung.... Die Dateiauswahl wird "
              "schmaler, wenn der Platz knapp wird (schmales Fenster, breite Dateiliste)."),
        ("b", "Darstellung... (rechts in der zweiten Zeile der Werkzeugleiste, klappt auf): Farbschema der Oberfläche und der Graphen. Neben Dunkel "
              "und Hell stehen Solar dunkel und Solar hell (Petrol bzw. Creme, Solarized-Farben), Nord (kühles "
              "Blaugrau, Pastelllinien), Kontrast (Schwarz mit kräftigen Farben, für Beamer und helle Umgebung), "
              "Papier (Cremeweiß mit Tintenfarben) und Farbenblind (Okabe-Ito-Farben, auch bei Rot-Grün-Schwäche "
              "unterscheidbar) zur Wahl. Linien- und Markerfarben sind je Schema auf den Plothintergrund abgestimmt "
              "(Kontrast mindestens 3:1, untereinander unterscheidbar). Das Schema bleibt gespeichert und gehört zur "
              "Ansicht; Druck, Export und Report verwenden immer die helle Darstellung, eigene Signalfarben bleiben."),
        ("b", "Schrift: Der Schieberegler unter Darstellung... stellt die Schriftgröße der Graphen (Titel, Achsen, "
              "Legende, Marker-Beschriftung) und der Wertanzeige ein, 10 bis 32 px. Die Größe bleibt gespeichert."),
        ("b", "Graphen: ein oder mehrere Diagramme, untereinander oder als Matrix n*m."),
        ("b", "Wertanzeige: Messwerte an den Markern, sichtbar sobald \"Marker\" angehakt ist."),
        ("b", "Statuszeile unten: Ergebnis der letzten Aktion, Hinweise und Fehlermeldungen."),
        ("p", "Die Trenner zwischen Dateiliste und Graphen sowie zwischen Graphen und Wertanzeige lassen sich "
              "mit der Maus ziehen (Kapitel Fensterbereiche)."),
        ("h", "Der schnelle Weg"),
        ("b", "\"Dateien öffnen...\" klicken, Dateien anhaken, \"Öffnen\"."),
        ("b", "Links Signale anhaken: jedes erscheint in einem eigenen Graphen."),
        ("b", "Rechtsklick auf einen Graphen: weitere Signale hinzufügen, Farben und Namen ändern, drucken, exportieren, Report."),
        ("b", "\"Marker\" anhaken und die senkrechten Marker ziehen: unten stehen die Messwerte."),
        ("b", "Datei > Ansicht speichern...: alles für das nächste Mal sichern."),
    ]),
    ("Installation und Start", [
        ("h", "Voraussetzungen"),
        ("p", "Python 3.10 oder neuer unter Windows oder Linux. Benötigte Pakete stehen in requirements.txt: "
              "dearpygui, numpy, pandas, pyarrow (Parquet), asammdf (MF4) und canmatrix (DBC)."),
        ("h", "Windows"),
        ("p", "start_windows.bat doppelt anklicken. Beim ersten Start entsteht eine eigene Python-Umgebung im "
              "Ordner .venv und die Pakete werden installiert. Danach startet das Programm direkt."),
        ("h", "Linux"),
        ("p", "Im Terminal sh start_linux.sh ausführen. Der erste Start richtet die Umgebung ebenso ein "
              "(benötigt python3-venv)."),
        ("h", "Rechner ohne Python (portable Version)"),
        ("p", "Liegt im Programmordner runtime\\python ein mitgeliefertes Python, verwenden es die Startdateien "
              "automatisch; ein installiertes Python ist dann nicht nötig. Mitgeliefert wird Python 3.12.0. Diese "
              "Version wird einmalig auf einem Rechner mit Internet gebaut: unter Windows "
              "tools\\build_portable_windows.bat (ergibt dist\\MessGraph_portable_windows.zip), unter Linux "
              "sh tools/build_portable_linux.sh (ergibt dist/MessGraph_portable_linux_x86_64.tar.gz bzw. _aarch64). "
              "Das Skript lädt Python 3.12.0 (python-build-standalone von GitHub, mit Prüfung der SHA-256-Prüfsumme; "
              "unter Windows notfalls von python.org), prüft die Version, installiert alle Pakete und packt das "
              "Ergebnis. Auf dem Zielrechner entpacken und wie gewohnt starten."),
        ("p", "Eine .venv allein genügt dafür nicht, weil sie immer auf ein installiertes Python verweist. Das Paket "
              "gilt nur für das Betriebssystem, auf dem es gebaut wurde."),
        ("h", "Mit Dateien starten"),
        ("p", "python main.py messung1.mf4 messung2.csv öffnet die Dateien gleich beim Start."),
        ("h", "Beispieldaten"),
        ("p", "Der Ordner demo_data enthält drei CSV-Beispiele. python tools/make_demo_data.py erzeugt sie neu, "
              "dazu demo.mf4 und demo.parquet, wenn asammdf und pyarrow installiert sind. Die Beispiele dienen "
              "auch der Erzeugung der Screenshots für diese Hilfe."),
    ]),
    ("Dateien öffnen", [
        ("p", "\"Dateien öffnen...\" (links oben oder im Menü Datei) zeigt den Datei-Browser."),
        ("img", "browser", "Bild 2: Datei-Browser"),
        ("m", "1", "Hoch, Start und Pfadeingabe"),
        ("m", "2", "Dateityp, Name enthält, Alle im Ordner, Keine"),
        ("m", "3", "Ordner: Klick öffnet ihn"),
        ("m", "4", "Dateien mit Häkchen, Größe und Änderungsdatum"),
        ("m", "5", "Anzahl der gewählten Dateien"),
        ("m", "6", "Öffnen lädt alle gewählten Dateien"),
        ("h", "Im Datei-Browser bewegen"),
        ("b", "Klick auf einen [Ordner]-Eintrag öffnet den Ordner."),
        ("b", "\"Hoch\" wechselt in den übergeordneten Ordner, \"Start\" in das Benutzerverzeichnis."),
        ("b", "Unter Windows wählt die Auswahl neben \"Start\" das Laufwerk."),
        ("b", "Oben lässt sich ein Pfad eintippen und mit der Eingabetaste öffnen. Ein eingetippter Dateipfad "
              "wählt die Datei gleich aus."),
        ("h", "Filtern"),
        ("b", "Dateityp: Messdaten (mf4, blf, csv, parquet), nur ein Format oder alle Dateien. Groß- und "
              "Kleinschreibung der Endung spielen keine Rolle (.MF4 = .mf4)."),
        ("b", "\"Name enthält\": Suchwörter im Dateinamen; mehrere Wörter müssen alle vorkommen."),
        ("h", "Mehrere Dateien wählen"),
        ("p", "Jede Datei hat ein Häkchen. \"Alle im Ordner\" hakt alle angezeigten Dateien an, \"Keine\" entfernt "
              "sie. Die Auswahl bleibt beim Ordnerwechsel erhalten: So lassen sich Dateien aus mehreren Ordnern "
              "gemeinsam öffnen. Unten steht die Anzahl, auch wie viele aus anderen Ordnern stammen."),
        ("p", "\"Öffnen\" lädt alle gewählten Dateien im Hintergrund. Der Ordner wird für das nächste Mal gemerkt. "
              "Eine bereits geöffnete Datei wird nicht doppelt geladen."),
        ("h", "Geladene Dateien"),
        ("img", "dateiliste", "Bild 3: Dateiliste mit zwei geladenen Dateien"),
        ("m", "1", "Dateien öffnen und Alle abwählen"),
        ("m", "2", "Zielgraph für das nächste angehakte Signal"),
        ("m", "3", "Signalsuche über alle Dateien"),
        ("m", "4", "Dateieintrag, aufklappbar, mit Schließen"),
        ("m", "5", "Erkennung: erscheint, wenn die Maus auf \"Erkennung\" steht"),
        ("m", "6", "Hinweis, hier eine Textspalte ohne Zahlen"),
        ("m", "7", "Signal-Häkchen"),
        ("p", "Jede Datei erscheint links als aufklappbarer Eintrag mit ihren Signalen. Die Maus auf \"Erkennung\" "
              "zeigt, was erkannt wurde (Trennzeichen, Kopfzeile, Zeitachse, Startzeit). Darunter stehen Hinweise, "
              "etwa zu Textspalten. \"Schließen\" entfernt die Datei und ihre Signale aus allen Graphen. "
              "MF4-Dateien haben zusätzlich die Schaltfläche \"Datenbasen...\"."),
        ("h", "Ein Signal über alle Dateien"),
        ("p", "Sind mehrere Dateien geladen und findet die Signalsuche ein Signal in mindestens zwei Dateien (z. B. "
              "\"Temp\" in mehreren Messläufen), erscheint unter dem Suchfeld die Leiste \"Treffer in mehreren "
              "Dateien\". Die Auswahlliste nennt alle solchen Signale; darunter steht, in wie vielen Dateien das "
              "Signal vorkommt und wie viele davon angezeigt sind."),
        ("img", "allefiles", "Bild 4: Signal Temperatur aus allen Dateien in einem gemeinsamen Graphen"),
        ("m", "1", "Suchtext"),
        ("m", "2", "Signale, die in mehreren Dateien vorkommen"),
        ("m", "3", "Gemeinsamer Graph, Einzelgraphen, Entfernen"),
        ("m", "4", "In wie vielen Dateien vorhanden und angezeigt"),
        ("b", "\"Gemeinsamer Graph\": das Signal aller Dateien in einem Graphen, gut zum direkten Vergleich. Ziel ist "
              "der gewählte Zielgraph; bei \"Automatisch\" ein neuer Graph (mit Matrix der erste leere). Die Legende "
              "nennt zu jeder Kurve die Datei."),
        ("b", "\"Einzelgraphen\": je Datei ein eigener Graph mit dem Signal (mit Matrix in die leeren bzw. am "
              "wenigsten belegten Graphen). Mit \"X-Achsen koppeln\" zoomen alle gemeinsam."),
        ("b", "\"Entfernen\": das Signal aller Dateien aus allen Graphen."),
        ("p", "Gezählt wird der genaue Signalname. Danach lassen sich die Kurven wie gewohnt vermessen, vergleichen, "
              "drucken und in den Report übernehmen."),
        ("h", "Fortschritt beim Laden"),
        ("p", "Beim Laden von MF4- und Parquet-Dateien erscheint über der Statuszeile eine Fortschrittsanzeige: "
              "Balken mit Prozent, Datei und aktueller Schritt (z. B. \"Parquet lesen: 1.200.000 von 3.000.000 "
              "Zeilen\", \"Spalten erkennen\", \"Downsampling\") und die bisherige Dauer. Bei mehreren Dateien zeigt "
              "der Balken den Gesamtfortschritt und den Stand \"2 von 5 fertig\"."),
        ("b", "Parquet wird blockweise gelesen, der Balken wächst gleichmäßig."),
        ("b", "MF4: Öffnen der Datei, Lesen eines Kanals beim Anhaken und DBC-Dekodierung erledigt asammdf in einem "
              "Schritt, dessen Dauer vorher nicht bekannt ist. Dann laufen Punkte hinter der Prozentangabe."),
        ("b", "Ansicht laden: jede Datei und jedes angezeigte Signal ist ein Teilschritt."),
        ("b", "\"Abbrechen\" beendet alle laufenden Ladevorgänge beim nächsten Zwischenstand. Bereits geladene "
              "Dateien bleiben, abgebrochene Signale werden wieder abgehakt. Innerhalb eines asammdf-Schritts "
              "greift der Abbruch, sobald dieser Schritt fertig ist."),
    ]),
    ("Datenerkennung", [
        ("h", "CSV"),
        ("p", "Die Struktur wird ohne Einstellungen erkannt:"),
        ("b", "Kodierung UTF-8, UTF-16 oder Windows-1252."),
        ("b", "Trennzeichen Semikolon, Komma, Tabulator, Senkrechtstrich oder Leerzeichen."),
        ("b", "Dezimalzeichen Punkt oder Komma."),
        ("b", "Vorspann: Zeilen vor der Tabelle (Prüfstand, Datum ...) werden übersprungen."),
        ("b", "Kopfzeile: die letzte reine Textzeile direkt vor den Daten. Ohne Kopfzeile heißen die Spalten "
              "Spalte_1, Spalte_2 und so weiter."),
        ("b", "Einheiten aus einer eigenen Zeile unter der Kopfzeile oder aus dem Namen: Speed [km/h], Druck (bar)."),
        ("h", "ASCII-Dateien mit variablem Vorspann (asc, txt, dat ...)"),
        ("p", "Neben CSV werden beliebige ASCII-Rohdaten geöffnet: Endungen asc, txt, dat, tsv, log und prn. Solche "
              "Dateien beginnen oft mit einem Vorspann unterschiedlicher Länge (Datum, Version, Kommentare). Die "
              "Datei wird eingelesen, dann wird die Signal-Kopfzeile automatisch erkannt oder vom Nutzer "
              "festgelegt; danach werden die Daten wie jede andere Datei behandelt (Zeitachse, Signale, Graphen)."),
        ("img", "ascii", "Bild 5: ASCII-Import mit Kopfzeile in Zeile 7, fortgesetzt in Zeile 8"),
        ("m", "1", "Anfang der Datei mit Zeilennummern; K = Kopfzeile, E = Einheitenzeile, D = erste Datenzeile"),
        ("m", "2", "Kopfzeile als Zeilennummer (0 = automatisch, -1 = keine)"),
        ("m", "3", "Trenn- und Dezimalzeichen (Automatisch oder fest)"),
        ("m", "4", "Ergebnis: erkannte Zeilen, Spaltenzahl und Signalnamen"),
        ("m", "5", "Übernehmen und einlesen, Automatisch, Schließen"),
        ("m", "6", "Schaltfläche ASCII-Import im Dateieintrag"),
        ("b", "Zusatzinformationen in der Form <{...}>, z. B. <{Continue}>, werden ignoriert. Beginnt eine Zeile mit "
              "einer solchen Marke, setzt sie die vorige Zeile fort: Eine Kopfzeile, die der Schreiber nach 1000 "
              "Zeichen umgebrochen hat (Zeile 7 endet mit DUT_TS_, Zeile 8 beginnt mit <{Continue}>12,...), ergibt "
              "wieder einen Signalnamen DUT_TS_12. So passen Kopf und Datenspalten logisch zusammen."),
        ("b", "Werte wie x, - oder leer gelten als fehlend; Spalten ganz ohne Zahlen (Text, nur x) werden gemeldet und "
              "nicht angeboten. Zeitstempel wie 2026-11-10_16-00-51 werden als Datum/Uhrzeit erkannt."),
        ("b", "\"ASCII-Import...\" im Dateieintrag zeigt die Erkennung. Dort lässt sich die Kopfzeile als "
              "Zeilennummer wie im Editor angeben (z. B. 7, auch wenn sie in Zeile 8 fortgesetzt wird), dazu "
              "Einheitenzeile, Trenn- und Dezimalzeichen. Das Ergebnis erscheint sofort; \"Übernehmen und "
              "einlesen\" liest die Datei neu. Angezeigte Signale bleiben in ihren Graphen."),
        ("b", "Wird eine Datei nicht erkannt, öffnet sich der Dialog von selbst."),
        ("b", "\"Als Vorlage ... verwenden\": weitere ASCII-Dateien (nicht CSV) werden zuerst mit diesen Angaben "
              "gelesen; passt es nicht, wird automatisch erkannt."),
        ("b", "Festgelegte Angaben werden mit der Ansicht und in Definitionsdateien gespeichert."),
        ("b", "Vector-ASC-Busaufzeichnungen (CAN-Trace mit Botschaften statt Werten) sind keine Wertetabellen; "
              "MessGraph weist darauf hin. Sie lassen sich als BLF speichern und mit DBC/ARXML öffnen."),
        ("p", "Beispiel: demo_data/demo_pruefstand.asc."),
        ("h", "Parquet"),
        ("p", "Alle Zahlenspalten werden angeboten, Datumsspalten als Zeitachse genutzt."),
        ("h", "X-Achse bei CSV und Parquet"),
        ("p", "Gesucht wird in dieser Reihenfolge:"),
        ("b", "eine steigende Datums- oder Zeitspalte (Text oder Datumstyp), auch getrennt als Datum und Uhrzeit;"),
        ("b", "eine steigende Zahlenspalte mit Zahlen-Zeitstempeln (Unix, LabVIEW);"),
        ("b", "eine steigende Zahlenspalte mit einem Namen wie time, zeit oder timestamp;"),
        ("b", "die erste Spalte, wenn sie streng steigt. Sie bleibt zusätzlich als Signal wählbar;"),
        ("b", "sonst die Zeilennummer."),
        ("h", "Besondere Daten"),
        ("b", "Spalten ohne einen einzigen Zahlenwert (Text, leer, nur Platzhalter) werden nicht angeboten; der "
              "Hinweis nennt genau diese Spalten der Datei. Er wird beim Anzeigen gebildet: Bei aktiver Signalsuche "
              "nennt er nur die passenden Namen und verschwindet, wenn keiner passt."),
        ("b", "Ein Signal, das nur zeitweise aufgezeichnet wurde (sonst Platzhalter wie x, -, n/a), wird angeboten; "
              "die Platzhalter werden zu Messlücken. Weitere Datums- oder Zeitspalten nennt die Erkennung."),
        ("b", "MF4 mit Busrohdaten: Der Hinweis nennt die vorhandenen Rahmenkanäle (z. B. CAN_DataFrame, LIN_Frame) "
              "und nach dem Zuordnen von Datenbasen die Zahl der dekodierten Signale."),
        ("b", "Einzelne ungültige Werte werden zu Messlücken."),
        ("b", "Eine nicht aufsteigende Zeitachse wird sortiert; auch dazu erscheint ein Hinweis."),
        ("h", "MF4"),
        ("p", "Die Kanäle stehen sofort in der Liste, die Messwerte werden erst beim Anhaken gelesen (auf Abruf). So "
              "öffnen sich auch große Dateien mit Tausenden Kanälen schnell; das Suchfeld über der Liste filtert, "
              "gezeigt werden höchstens 400 Treffer je Datei. Enthält die Datei CAN-Rohdaten, öffnet sich der Dialog "
              "Datenbasen."),
        ("b", "Doppelte Kanalnamen (MF4 und MDF): Jeder Kanal wird über Gruppe und Index gelesen, nie über den Namen "
              "allein. Eindeutige Namen bleiben unverändert; bei gleichen Namen zeigt die Liste \"Gruppe / Kanal\" "
              "(z. B. IVT6_Msg_Result_I / IVT_Result_I, die Gruppe ist bei Buslogging meist die Botschaft) oder bei "
              "einer Gruppe mit nur einem Datenkanal bzw. ohne Gruppennamen \"Kanal [g714]\"; bleibt es doppelt, "
              "\"Kanal [g714:i3]\". Ansichten und Projekte mit den früheren Namen (Kanal (G714)) finden die Kanäle "
              "weiter; auch die Suche kennt sie. Die Erkennungsangaben nennen die Zahl umbenannter Kanäle."),
        ("b", "Jedes Signal behält seine eigene Zeitachse (Zeitstempel und Werte aus der Datei, kein Umrechnen auf ein "
              "gemeinsames Raster); der Graph zeichnet jedes Signal mit seiner Zeit."),
        ("b", "Wert->Text-Umrechnung (z. B. 0 = Idle, 1 = Charging): Im Graphen erscheinen die Rohwerte als Zahlen; "
              "die Wertanzeige ergänzt den Text, z. B. 1 (Charging), der Tooltip am Kanal listet die Zuordnung."),
        ("b", "Nicht darstellbar und grau in der Liste: Text-Kanäle (VLSD-Strings, Byte-Felder), Kanäle mit nur einem "
              "Wert (Konstante; Knopf Wert zeigt ihn in der Statuszeile) und Kanäle ohne Werte. Sie lassen sich nicht "
              "anhaken; die Erkennungsangaben nennen ihre Anzahl."),
    ]),
    ("Zeitformate", [
        ("p", "Die Zeitspalte wird ohne Vorgabe erkannt. Intern zählt die X-Achse die Sekunden ab dem ersten Wert. "
              "Zeitstempel mit Datum liefern zusätzlich die Startzeit für die Datum/Uhrzeit-Achse."),
        ("h", "Zeitstempel als Text"),
        ("b", "ISO und Varianten: 2026-10-01 23:00:51, 2026-10-01T23:00:51.250, 2026-10-01_23-00-51"),
        ("b", "Deutsch: 01.10.2026 23:00:51,5 und 01.10.26 23:00 (zweistellige Jahre ab 2000)"),
        ("b", "Mit Schrägstrich: 13/10/2026 oder 10/13/2026 08:00:00 AM"),
        ("b", "Ohne Trennzeichen: 20261001_230051 oder 20261001T230051.5"),
        ("b", "Mit Monatsnamen, deutsch oder englisch: 01-Oct-2026 23:00:51, 1. Okt. 2026 um 23:00, "
              "Oct 1, 2026 11:00:51 PM, Thu Oct 1 23:00:51 2026"),
        ("h", "Tag oder Monat zuerst?"),
        ("p", "Bei 03/04/2026 entscheidet das Programm je Spalte: Ein Wert über 12 legt die Reihenfolge fest, ein "
              "Punkt bedeutet immer Tag.Monat. Sonst gewinnt die Lesart, bei der die Zeit steigt und die Schritte am "
              "kleinsten sind. Bei Gleichstand gilt Tag zuerst."),
        ("h", "Uhrzeiten und Dauern ohne Datum"),
        ("b", "Folgt auf 23:59:59 die Zeit 00:00:00, zählt das als neuer Tag."),
        ("b", "Dauern wie 25:30:00, 0 days 00:00:01.5 oder 1 d 02:00:00 werden als Sekunden übernommen."),
        ("p", "Ohne Datum gibt es keine Startzeit und damit keine Datumsachse."),
        ("h", "Zahlen-Zeitstempel"),
        ("p", "Eine steigende Zahlenspalte gilt als Zeitstempel, wenn sie zeitartig heißt oder die erste Spalte ist "
              "und alle Werte in die Jahre 2000 bis 2050 fallen: Unix-Zeit in s, ms, µs oder ns, LabVIEW-Zeit "
              "(Sekunden ab 1904). Unix-Zeit erscheint in Ortszeit."),
        ("h", "Zeitzonen"),
        ("p", "Zonenangaben in Text (Z, UTC, +02:00) werden ignoriert: Die Uhrzeit erscheint wie in der Datei. "
              "Parquet-Zeitstempel mit Zeitzone und die Startzeit von MF4-Dateien erscheinen in Ortszeit."),
    ]),
    ("Signale und Graphen", [
        ("h", "Signale wählen"),
        ("p", "Ein Häkchen in der Dateiliste zeigt das Signal, Entfernen des Häkchens nimmt es aus allen Graphen. "
              "Das Suchfeld über der Liste grenzt nach Namen ein; mehrere Wörter müssen alle vorkommen. Je Datei "
              "werden höchstens 400 Treffer gelistet. \"Alle abwählen\" leert alle Graphen."),
        ("b", "Gleichnamige Signale aller Dateien (Häkchen unter den Knöpfen, nur bei mehreren offenen Dateien): An - ein "
              "Häkchen bei einem Signal wählt das gleichnamige Signal in allen offenen Dateien zugleich, zusammen in "
              "einem Graphen (gewählter Zielgraph, sonst ein neuer); Abwählen entfernt es aus allen Dateien. Aus - "
              "Einzelauswahl je Datei. Die Einstellung bleibt gespeichert."),
        ("h", "Zielgraph"),
        ("b", "Automatisch ohne Matrix: jedes angehakte Signal erhält einen eigenen Graphen, untereinander."),
        ("b", "Automatisch mit Matrix: in den ersten Graphen mit den wenigsten Signalen."),
        ("b", "Graph k: das nächste angehakte Signal kommt in Graph k."),
        ("h", "Matrix n*m"),
        ("p", "In der Werkzeugleiste eine Aufteilung wie 2*3 (2 Zeilen, 3 Spalten) eintragen und \"Anwenden\" "
              "klicken; 2x3 oder 2,3 gehen ebenso. Die Graphen sind zeilenweise nummeriert, höchstens 64. "
              "Ein leeres Feld stellt alle Graphen untereinander; reicht die Höhe nicht, erscheint ein Rollbalken."),
        ("img", "matrix", "Bild 6: Matrix 2*2 mit mehreren Signalen je Graph"),
        ("m", "1", "Matrix 2*2 eingetragen und angewendet"),
        ("m", "2", "Eigener Name des Graphen"),
        ("m", "3", "Zwei Signale in einem Graphen, temperature mit eigener Farbe auf der rechten Achse"),
        ("m", "4", "Zielgraph zeigt Nummer, Lage und Namen"),
        ("m", "5", "Rechte (sekundäre) Y-Achse mit eigener Einheit"),
        ("h", "Zeilen zusammenfassen"),
        ("p", "In einer Matrix lassen sich die Graphbereiche einzelner Zeilen frei zusammenfassen. Beispiel 4*3: "
              "Zeile 1 und 2 mit je 3 Graphen, Zeile 3 mit einem Graphen über 2 Spalten und einem über 1 Spalte, "
              "Zeile 4 mit einem Graphen über die ganze Breite."),
        ("img", "zeilen", "Bild 7: Matrix 4*3 mit zusammengefassten Bereichen"),
        ("m", "1", "Matrixfeld mit Zeilenangaben: 4*3: 3, 3, 2+1, 1"),
        ("m", "2", "Schaltfläche Zeilen... öffnet den Dialog"),
        ("m", "3", "Zeile 3: Graph über zwei Spalten und Graph über eine Spalte"),
        ("m", "4", "Zeile 4: ein Graph über die ganze Breite"),
        ("m", "5", "Angabe je Zeile"),
        ("m", "6", "Vorschau der Aufteilung"),
        ("m", "7", "Übernehmen, Alle Einzelgraphen, Schließen"),
        ("p", "Je Zeile gilt: eine Zahl ist die Anzahl gleich breiter Graphen (3 = drei Graphen, 1 = ein Graph über "
              "alle Spalten, bei 4 Spalten 2 = zwei Graphen über je zwei Spalten); mit + werden die Breiten in Spalten "
              "angegeben (2+1, 1+2, 1+1+2). Die Breiten einer Zeile ergeben zusammen die Spaltenzahl."),
        ("b", "Direkt im Matrixfeld: nach der Matrix ein Doppelpunkt und die Zeilen durch Komma getrennt, z. B. "
              "4*3: 3, 3, 2+1, 1. Fehlende Zeilen bleiben Einzelgraphen."),
        ("b", "Oder mit \"Zeilen...\": je Zeile ein Eingabefeld, die Vorschau zeigt die Aufteilung sofort, "
              "\"Übernehmen\" wendet sie an. \"Alle Einzelgraphen\" setzt alle Zeilen zurück."),
        ("p", "Die Graphen sind zeilenweise nummeriert; der Zielgraph nennt die belegten Spalten, z. B. Graph 7 "
              "(Z3/S1-2). Signale bleiben beim Ändern der Aufteilung erhalten; fallen Graphen weg, werden ihre Signale "
              "auf die übrigen verteilt. \"X-Achsen koppeln\" wirkt auch über die Zeilen hinweg. Die Aufteilung wird "
              "mit Ansicht und Projekt gespeichert; \"Alle Graphen drucken\" übernimmt sie (eine Zeile bleibt auf "
              "einer Seite)."),
        ("h", "Anordnung vorschlagen"),
        ("p", "\"Vorschlag...\" neben \"Zeilen...\" analysiert die Signale und schlägt Graphen und Matrix vor. "
              "Beispiel Prüfstand: AC-Spannungen, AC-Ströme, AC-Leistungen und AC-Frequenzen in je einem Graphen und "
              "zusammen in einer Zeile, darunter HVDC, LVDC usw., am Ende die Temperaturen und die Zustände."),
        ("img", "vorschlag", "Bild 8: Anordnung vorschlagen für demo_pruefstand.asc"),
        ("m", "1", "Schaltfläche Vorschlag..."),
        ("m", "2", "Welche Signale, höchstens Kurven je Graph und Spalten"),
        ("m", "3", "Vorschau der Matrix mit Graphnamen und Kurvenzahl"),
        ("m", "4", "Zeilen und Graphen mit ihren Signalen"),
        ("m", "5", "Übernehmen ersetzt die aktuelle Anordnung"),
        ("b", "Signale: die angezeigten Signale, die Treffer der Signalsuche oder alle Signale einer Datei."),
        ("b", "Größe aus der Einheit (V, A, W, Hz, °C, bar, rpm ...) oder aus dem Namen: V/U = Spannung, I = Strom, "
              "P = Leistung, T/TS/Temp = Temperatur, H = Feuchte, F = Frequenz bei AC/Netz/V2L, sonst Durchfluss, "
              "Mode/Status = Zustand. Das System ist der erste Namensteil (AC, HVDC, LVDC, Kl30, Chiller, DUT ...)."),
        ("b", "Ein Graph fasst gleiche Größe desselben Systems zusammen; Sollwerte (Set, Soll) stehen bei den Istwerten. "
              "Je System eine Zeile; kleine Systeme teilen sich eine Zeile (z. B. HVDC und LVDC). Temperaturen und "
              "Zustände bekommen eigene Zeilen (abschaltbar), Signale ohne erkennbare Größe kommen unter Sonstige."),
        ("b", "Mehr Kurven als erlaubt teilen den Graphen (DUT Temperatur 1/5 ...), mehr Graphen als Spalten teilen "
              "die Zeile. Zeilen mit weniger Graphen werden über zusammengefasste Bereiche gefüllt. Bei sehr vielen "
              "Systemen fasst der Vorschlag je Größe über alle Systeme zusammen (höchstens 64 Graphen)."),
        ("p", "\"Übernehmen\" setzt Matrix, Graphnamen und Signale; danach lässt sich alles wie gewohnt ändern."),
        ("h", "Datei für die Graphen wählen"),
        ("p", "Vorn in der Werkzeugleiste stehen in der Auswahl \"Datei\" alle geladenen Dateien. Die Auswahl zeigt, "
              "aus welcher Datei die Graphen stammen (\"Mehrere Dateien\", wenn sie gemischt sind)."),
        ("b", "Eine andere Datei wählen: Alle vorhandenen Graphen zeigen die gleichnamigen Signale dieser Datei. "
              "Signale der vorherigen Datei werden ersetzt, ebenso ein Signal, das über mehrere Dateien in einem "
              "Graphen stand (es bleibt einmal, aus der gewählten Datei)."),
        ("b", "Matrix, zusammengefasste Bereiche, Graphnamen, Farben, rechte Achse, Grenzen und Bemerkungen bleiben. "
              "So lässt sich eine Anordnung (selbst gebaut oder aus \"Vorschlag...\") nacheinander für mehrere "
              "Messungen ansehen."),
        ("b", "Zugeordnet wird über den Signalnamen (dann die Beschriftung, dann ohne Groß-/Kleinschreibung). "
              "Fehlt ein Signal in der gewählten Datei, fällt es weg und die Statuszeile nennt es. MF4-Kanäle werden "
              "zuerst geladen, danach wechseln alle Graphen auf einmal."),
        ("b", "\"Alle Dateien\" (erster Eintrag, sobald mehr als eine Datei geladen ist) wechselt zurück auf alle "
              "Dateien. Wurden die Graphen seit dem Wechsel auf eine Datei nicht anders belegt, kommt genau die "
              "Darstellung von vorher zurück, auch mit eigenen Farben und Graphen, die nur eine Datei zeigten. "
              "Sonst zeigt jeder Graph zu jedem seiner Signale das gleichnamige Signal aller geladenen Dateien "
              "(rechte Achse, Grenzen und Zielzeit gehen mit, die Farben vergibt das Farbschema)."),
        ("b", "Alles Bisherige bleibt: Häkchen, Ziehen, Zielgraph, Suche über alle Dateien und \"Dateien "
              "vergleichen...\" funktionieren wie gewohnt."),
        ("h", "Alle Plots löschen"),
        ("p", "\"Alle Plots löschen\" leert den Plotbereich: Alle Graphen und die Aufteilung (Matrix, "
              "zusammengefasste Bereiche) werden entfernt, ebenso Graphnamen, Farben, Grenzen, Bemerkungen und "
              "Kommentare. Die Dateien bleiben geladen; das nächste Signal beginnt wie nach dem Öffnen."),
        ("p", "Ist keine Datei geladen, bleibt der Plotbereich leer, auch bei eingestellter Matrix. Die Matrix bleibt "
              "gespeichert und erscheint mit der nächsten Datei; wird die letzte Datei geschlossen, wird der Bereich "
              "wieder leer."),
        ("h", "Mehrere Signale in einem Graphen"),
        ("p", "Ein Graph zeigt beliebig viele Signale. Weitere Signale kommen hinzu"),
        ("b", "per Rechtsklick auf den Graphen (Kapitel Kontextmenü); dort lässt sich ein Signal auch auf die "
              "rechte Y-Achse legen,"),
        ("b", "per Drag and Drop: Signalnamen links greifen und auf den Graphen oder eine Achse ziehen; auf der "
              "freien Fläche abgelegt, wird das Signal automatisch verteilt,"),
        ("b", "über Zielgraph und Häkchen."),
        ("p", "Dasselbe Signal darf in mehreren Graphen stehen. Ohne Matrix entfällt ein leerer Graph, mit Matrix "
              "bleibt er als leerer Platz stehen."),
        ("h", "Graph bedienen"),
        ("b", "Mausrad: zoomen, auch nur über einer Achse."),
        ("b", "Linke Maustaste ziehen: verschieben."),
        ("b", "Rechte Maustaste ziehen: Bereich zoomen."),
        ("b", "Rechte Maustaste klicken (ohne Ziehen): Kontextmenü."),
        ("b", "\"Alles anzeigen\": auf die Daten einpassen. Doppelklick auf einen Graphen öffnet ihn groß im "
              "Detailfenster (siehe unten); im Detailfenster passt der Doppelklick ein."),
        ("b", "Die Y-Achse wird dabei wie im Report mit Rand eingepasst: Y max = größter Wert * 1,1, Y min = kleinster "
              "Wert * 0,9 (allgemein 10 % des Betrags nach außen, damit auch negative Werte Platz haben; ist ein "
              "Wert 0, gelten 10 % der Spannweite). Das gilt beim Aufbau, bei \"Alles anzeigen\" und beim Doppelklick im Detailfenster, "
              "je Achse über alle Signale des Graphen. Danach lässt sich wie gewohnt zoomen."),
        ("b", "Klick auf einen Legendeneintrag: Signal aus- und einblenden."),
        ("h", "Graph im Detailfenster (Doppelklick)"),
        ("p", "Ein Doppelklick mit der linken Maustaste auf einen Graphen öffnet ihn in einem eigenen, großen Fenster. "
              "Es zeigt denselben Graphen, nicht eine Kopie: Signale, Farben, rechte Achse, Grenzen, Marker, Legende, "
              "Name und Kommentare gehören zum Graphen und gelten im Plotbereich und im Detailfenster zugleich."),
        ("b", "Zoomen, Verschieben und Rechteck aufziehen wirken nur im Detailfenster; der Plotbereich bleibt, wie er "
              "ist. Doppelklick oder \"Alles anzeigen\" im Detailfenster passt ein."),
        ("b", "Leiste oben: Alles anzeigen, Marker, Marker synchron, Drucken / exportieren (der sichtbare Ausschnitt "
              "des Detailfensters), Report und Schließen. Mit Markern zeigt das Detailfenster seine eigene Wertanzeige; "
              "die Marker laufen mit demselben Graphen im Plotbereich mit, Grenzen gelten in beiden Wertanzeigen."),
        ("b", "Rechtsklick öffnet dasselbe Kontextmenü wie im Plotbereich (Name, Signale hinzufügen und entfernen, "
              "Farben, rechte Achse, Legende, Kommentare, Drucken). Kommentare lassen sich mit der linken Maustaste "
              "verschieben, Signale aus der Liste hierher ziehen."),
        ("b", "Doppelklick auf einen anderen Graphen zeigt diesen im Detailfenster. Verschwindet der Graph (alle "
              "Signale entfernt, Datei geschlossen, Alle Plots löschen), schließt sich das Fenster."),
        ("h", "X-Achsen koppeln"),
        ("p", "Zoomen und Verschieben wirken in allen Graphen zugleich. Beim Umschalten werden die Graphen neu "
              "aufgebaut und der Zoom zurückgesetzt."),
        ("h", "Große Datenmengen"),
        ("p", "Bei langen Signalen zeichnet MessGraph je Abschnitt des sichtbaren Bereichs Minimum und Maximum. "
              "Spitzen bleiben sichtbar, die Anzeige bleibt flüssig. Die Messwerte stammen immer aus den "
              "vollständigen Daten."),
    ]),
    ("Kontextmenü im Graphen", [
        ("p", "Ein Rechtsklick auf einen Graphen (ohne die Maus zu ziehen) öffnet sein Kontextmenü. Ein Klick "
              "außerhalb oder \"Schließen\" schließt es."),
        ("img", "kontextmenue", "Bild 9: Kontextmenü nach Rechtsklick auf einen Graphen"),
        ("m", "1", "Name des Graphen"),
        ("m", "2", "Signal suchen und mit Klick hinzufügen"),
        ("m", "3", "Signal aus diesem Graphen entfernen"),
        ("m", "4", "Farbfelder: Klick öffnet die Farbauswahl"),
        ("m", "5", "Standardfarben wiederherstellen"),
        ("m", "6", "Rechte Y-Achse: Häkchen legt das Signal auf die sekundäre Achse"),
        ("m", "7", "Drucken und Export: Graph, alle Graphen, Report"),
        ("m", "8", "Lage der Legende: oben links, Mitte, rechts oder unten links, Mitte, rechts"),
        ("m", "9", "Kommentar an der Klickstelle: neuer Text, vorhandene Kommentare ändern, verschieben, löschen"),
        ("m", "10", "Kommentarfeld im Graphen"),
        ("h", "Name des Graphen"),
        ("p", "Eigenen Namen eintragen und Eingabetaste oder \"Übernehmen\" drücken. Der Name erscheint als Titel "
              "des Graphen, in der Auswahl Zielgraph und in der Wertanzeige. Ein leeres Feld stellt den "
              "Standardnamen \"Graph k\" wieder her."),
        ("h", "Kommentarfelder"),
        ("p", "Mit der rechten Maustaste an die gewünschte Stelle im Graphen klicken. Unter \"Kommentar an der "
              "Klickstelle\" den Text eintragen (mehrzeilig möglich) und \"Kommentar einfügen\" wählen. Der "
              "Kommentar erscheint als Feld im Graphen, verankert an der Klickstelle (X-Wert und Wert der linken "
              "Y-Achse); beim Zoomen und Verschieben wandert er mit."),
        ("b", "Verschieben mit der Maus: Über dem Kommentar wird er farbig hervorgehoben. Linke Maustaste gedrückt "
              "halten und ziehen, der Kommentar folgt der Maus; der Graph bleibt dabei stehen. Loslassen legt ihn ab."),
        ("b", "Vorhandene Kommentare stehen darunter: Text ändern und Eingabetaste oder \"Übernehmen\" "
              "(leer übernommen löscht ihn), \"Hierher\" verschiebt ihn an die Stelle des Rechtsklicks, "
              "\"Löschen\" entfernt ihn."),
        ("b", "Beliebig viele Kommentare je Graph. Sie werden mit Ansicht und Projekt gespeichert, beim Wechsel der "
              "Datei (Auswahl \"Datei\") behalten und erscheinen beim Drucken, im Export (PDF, SVG) und in beiden "
              "Reports als Kasten mit Punkt an der Stelle."),
        ("b", "\"Alle Plots löschen\" entfernt auch die Kommentare (mit allen Graphen und der Aufteilung)."),
        ("h", "Signal hinzufügen"),
        ("p", "Die Liste enthält alle Signale aller geladenen Dateien, die der Graph noch nicht zeigt. Das Suchfeld "
              "grenzt ein; ein Klick fügt das Signal hinzu."),
        ("h", "Signal entfernen"),
        ("b", "\"Entfernen: Signalname\" nimmt das Signal nur aus diesem Graphen."),
        ("b", "\"Alle Signale dieses Graphen entfernen\" leert den Graphen."),
        ("h", "Signalfarben"),
        ("p", "Je Signal gibt es ein Farbfeld. Ein Klick darauf öffnet die Farbauswahl; die neue Farbe gilt sofort "
              "und nur in diesem Graphen. Signale ohne eigene Farbe erhalten die Standardfarbe ihrer Position, "
              "passend zum gewählten Farbschema. \"Standardfarben wiederherstellen\" entfernt alle eigenen Farben des "
              "Graphen. Eigene Farben werden mit der Ansicht gespeichert."),
        ("h", "Rechte Y-Achse (sekundär)"),
        ("p", "Signale mit sehr unterschiedlichem Wertebereich, etwa Drehzahl und Temperatur, lassen sich in einem "
              "Graphen gemeinsam lesen: Ein Häkchen bei \"Rechte Y-Achse (sekundär)\" legt das Signal auf eine zweite "
              "Y-Achse am rechten Rand mit eigener Skala und Einheit. Ohne Häkchen liegt es wieder links."),
        ("b", "Die rechte Achse erscheint nur, wenn mindestens ein Signal des Graphen sie nutzt."),
        ("b", "In Legende und Wertanzeige steht hinter dem Signal der Zusatz \"(rechts)\"."),
        ("b", "Drag and Drop auf die rechte Achse legt ein Signal direkt dort ab; ein Signal des Graphen wechselt so "
              "nach rechts."),
        ("b", "Die Zuordnung gilt je Graph und wird mit der Ansicht gespeichert. Zoomen mit dem Mausrad über der "
              "rechten Achse ändert nur deren Skala, über der Zeichenfläche zoomt es beide Y-Achsen um die Mausposition; "
              "\"Alles anzeigen\" passt beide Achsen an. Zoomt die eingesetzte Dear-PyGui-Version die rechte Achse "
              "nicht selbst, übernimmt MessGraph das (10 % je Rastung). Gleiches gilt fürs Verschieben mit der linken "
              "Maustaste: über der Zeichenfläche folgt die rechte Achse der linken, über der rechten Achse der Maus."),
    ]),
    ("Messen mit Markern", [
        ("p", "Das Häkchen \"Marker\" zeigt in jedem Graphen zwei senkrechte Marker M1 und M2 und darunter die "
              "Wertanzeige. Die Marker kennzeichnen nur die Zeitpunkte; die Werte der Signale stehen in der "
              "Wertanzeige, so bleibt der Graph übersichtlich."),
        ("img", "crosslines", "Bild 10: Marker M1 und M2 mit Wertanzeige"),
        ("m", "1", "Häkchen Marker"),
        ("m", "2", "Marker M1: senkrechte Linie, mit der Maus ziehen"),
        ("m", "3", "Marker M2 ebenso"),
        ("m", "4", "Wertanzeige mit Werten, Delta und Drift"),
        ("m", "5", "Trenner: ziehen ändert die Höhe der Wertanzeige"),
        ("m", "6", "Y min / Y max: Grenzen je Signal"),
        ("m", "7", "Grenzlinie im Graphen"),
        ("h", "Bedienen"),
        ("p", "Einen Marker an der Linie oder an seiner Beschriftung M1 oder M2 greifen und waagerecht ziehen. "
              "Neue Marker beginnen bei 1/3 und 2/3 des Datenbereichs. Mit \"Marker synchron\" bewegt sich derselbe "
              "Marker in allen Graphen mit; ohne das Häkchen hat jeder Graph eigene Positionen."),
        ("b", "Zoom und Unzoom (Mausrad, Rechteck aufziehen, Doppelklick, \"Alles anzeigen\"): Danach stehen die "
              "Marker neu bei 10 % (M1) und 90 % (M2) des neuen Sichtbereichs; das ist die neue Basis der Messung. "
              "Ändern mehrere Graphen gleichzeitig ihren Ausschnitt (z. B. gekoppelte X-Achsen), gilt der Graph unter "
              "der Maus. Beim Einschalten der Marker landen Marker außerhalb des Ausschnitts ebenfalls bei 10 % und 90 %."),
        ("b", "Verschieben des Ausschnitts lässt die Marker stehen. Fällt dabei ein Marker aus dem Bild, werden "
              "beide ebenso auf 10 % und 90 % gesetzt."),
        ("h", "Messwerte je Signal"),
        ("b", "X1, X2: Position von M1 und M2."),
        ("b", "Wert 1, Wert 2: Signalwert an M1 und M2, zwischen zwei Messpunkten linear interpoliert."),
        ("b", "Delta X = X2 - X1 und Delta Y = Wert 2 - Wert 1."),
        ("b", "Drift = Delta Y / Delta X: die Änderung je X-Einheit, zum Beispiel V/s."),
        ("b", "Drift (Regression) und Prognose: siehe Kapitel Datum/Uhrzeit-Achse, Prognose bis zur Grenze."),
        ("p", "Ein Strich (-) bedeutet: kein Wert. Der Marker steht außerhalb der Daten oder in einer Messlücke, "
              "oder Delta X ist 0. Die Einheiten stammen aus der Datei."),
        ("h", "Marker 3 mit Wertetabelle"),
        ("p", "Das Häkchen \"Marker 3\" (neben \"Marker synchron\") zeigt in jedem Graphen einen dritten, grünen "
              "Marker M3. Er ist unabhängig von M1 und M2: er funktioniert auch ohne eingeschaltete Marker, ändert "
              "die Wertanzeige nicht und wird beim Zoomen nicht auf 10 %/90 % gesetzt (nur wenn er aus dem Bild "
              "fällt, kommt er in die Mitte des Ausschnitts)."),
        ("b", "Steht die Maus an M3 (etwa 10 Pixel waagerecht) oder wird M3 gezogen, zeigt ein Tooltip eine "
              "Wertetabelle: oben die Position (X bzw. Datum/Uhrzeit), darunter je Signal des Graphen eine Zeile mit "
              "Name, Wert an M3 (zwischen den Messpunkten interpoliert, mit Einheit und ggf. Text der "
              "Wert->Text-Umrechnung; Signale der rechten Achse mit (rechts)), Min, Max, Average und Drift. Solange "
              "die Tabelle zu sehen ist, ruht der Signal-Tooltip."),
        ("b", "Bereich für Min, Max, Average und Drift: Auswahl neben \"Marker 3\" - \"Zwischen M1 und M2\" "
              "(Standard; nur bei eingeschalteten Markern, sonst gilt der gesamte Verlauf, die Tabelle sagt es) oder "
              "\"Gesamter Signalverlauf\". Drift = Delta Y / Delta X: zwischen M1 und M2 aus den Werten an den "
              "Markern (wie in der Wertanzeige), über den gesamten Verlauf vom ersten zum letzten Messpunkt. Die "
              "Zeile unter der Tabelle nennt den verwendeten Bereich."),
        ("b", "Mit \"Marker synchron\" laufen die M3 aller Graphen gleicher Achsenart mit; das Detailfenster läuft "
              "immer mit. Position und Häkchen werden mit Ansicht und Projekt gespeichert."),
        ("h", "Tooltip am Signal"),
        ("p", "Bei eingeschalteten Markern zeigt ein Tooltip die Messwerte des Signals, auf dessen Kurve die "
              "Mausspitze zeigt: X1-Wert, X2-Wert, Y1-Wert, Y2-Wert, Delta X, Delta Y, Average Signal (Mittelwert "
              "zwischen M1 und M2), Drift-Signal (zwischen M1 und M2), Drift-Regression und die Regressionsgerade "
              "f(x) = m*x + b (gewählte Art der Drift-Regression, x ab dem ersten Messpunkt)."),
        ("b", "Liegen viele Kurven in einem Graphen, gilt der Tooltip nur für die Kurve, die der Mausspitze am "
              "nächsten ist (höchstens etwa 10 Pixel senkrecht entfernt); Signale an der rechten Y-Achse werden in "
              "deren Maßstab gemessen und mit (rechts) gekennzeichnet."),
        ("b", "Abseits der Kurven, ohne Marker, bei offenem Kontextmenü oder beim Verschieben eines Kommentars "
              "verschwindet der Tooltip. Er funktioniert auch im Detailfenster."),
        ("h", "Grenzen Y min und Y max"),
        ("p", "In den Spalten Y min und Y max der Wertanzeige lässt sich je Signal ein unterer und ein oberer Grenzwert "
              "eintragen (Dezimalpunkt oder -komma). Gesetzte Grenzen erscheinen im Graphen als waagerechte Linie in "
              "der Farbe des Signals, solange die Marker eingeschaltet sind. Ein leeres Feld bedeutet keine Grenze. "
              "Die Grenzen werden mit der Ansicht gespeichert."),
    ]),
    ("Datum/Uhrzeit-Achse", [
        ("p", "Das Häkchen \"Datum/Uhrzeit-Achse\" zeigt die X-Achse als Datum und Uhrzeit. Das gilt für jeden "
              "Graphen, dessen Signale alle eine Startzeit haben: Text- oder Zahlen-Zeitstempel, Datumsspalten in "
              "Parquet und MF4-Dateien mit gesetzter Startzeit."),
        ("img", "datumsachse", "Bild 11: Datum/Uhrzeit-Achse"),
        ("m", "1", "Häkchen Datum/Uhrzeit-Achse"),
        ("m", "2", "X-Achse mit Datum und Uhrzeit"),
        ("m", "3", "X1 und X2 als Datum mit Millisekunden"),
        ("m", "4", "Delta X als Dauer"),
        ("m", "5", "Grenze Y min, hier -20 A"),
        ("m", "6", "Prognose: wann der Drift die Grenze erreicht"),
        ("m", "7", "Zielzeit (hier 1 h) mit \"Alle\"; die Prognose ist früher, daher Zeile rot und Graph schwach rot"),
        ("b", "Signale verschiedener Dateien liegen zeitrichtig übereinander; in Sekunden beginnt jede Datei bei 0."),
        ("b", "In der Wertanzeige stehen X1 und X2 als Datum mit Millisekunden, Delta X als Dauer, "
              "zum Beispiel 1 d 02:03:04.5 (93784.5 s). Die Drift gilt je Sekunde."),
        ("b", "Ein Graph mit einem Signal ohne Startzeit bleibt in Sekunden. Gibt es beide Arten, sind die X-Achsen "
              "nicht gekoppelt, und \"Marker synchron\" verbindet nur Graphen gleicher Art."),
        ("b", "Beim Umschalten beginnen die Marker neu bei 1/3 und 2/3 des Datenbereichs."),
        ("h", "Prognose bis zur Grenze"),
        ("p", "Die Spalte Drift (Regression) zeigt die Steigung m der Regressionsgeraden f(x) = m*x + b, berechnet nach "
              "der unter Graph-Optionen > Drift-Regression gewählten Art (Vorgabe: kleinste Quadrate) über alle Daten "
              "des Signals. Die Spalte Prognose rechnet "
              "damit vom letzten Messpunkt aus weiter: Dort ist x1 = 0 und f(x1) = b der letzte y-Wert. Endwert y2 ist "
              "bei steigendem Drift Y max, bei fallendem Y min. Gesucht ist x2 = (y2 - b) / m."),
        ("b", "Arten der Drift-Regression (Graph-Optionen > Drift-Regression), nummeriert: (1) Lineare Regression "
              "(kleinste Quadrate der Abstände in y-Richtung, Vorgabe); (2) Minimale Abstandsquadrate (orthogonal: "
              "kleinste Quadrate der rechtwinklig zur Geraden gemessenen Abstände, Hauptachse; da x und y gemeinsam "
              "zählen, hängt das Ergebnis von den Einheiten ab); (3) Robuste Regression (Theil-Sen: Median der "
              "Steigungen aller Punktpaare, kaum beeinflusst von Ausreißern); (4) Lineare Regression über das letzte "
              "Viertel (aktueller Trend, z. B. nach einem Lastwechsel). Die Nummer steht im Spaltenkopf der "
              "Wertanzeige, z. B. Drift (Regression 3), und wechselt beim Umschalten sofort mit; ebenso im "
              "Detailfenster und in der Signaltabelle des Reports. Die Wahl gilt für Drift (Regression), Prognose, Zielzeit-Bewertung, "
              "Regressionslinien, Druck, Export und Report; sie wird gemerkt und mit Ansicht und Projekt gespeichert."),
        ("b", "Mit Datum/Uhrzeit-Achse: Grenze, Zieldatum/-zeit und Dauer ab dem letzten Messpunkt, z. B. "
              "\"max, 08.11.2026 20:02:01, 2 days 6 hrs 2 min\"."),
        ("b", "Ohne Datumsachse (Sekunden oder Zeilen): x2 in der Einheit der X-Achse, z. B. \"min, x2 = 44.8218 s, "
              "0 days 0 hrs 1 min\"."),
        ("b", "\"schon überschritten\": Der letzte Wert liegt bereits jenseits der Grenze in Driftrichtung."),
        ("b", "\"kein Schnitt\": Die Steigung ist 0 oder es fehlt die Grenze in Driftrichtung (z. B. steigend, aber "
              "nur Y min gesetzt)."),
        ("p", "Die Marker beeinflussen die Prognose nicht; ihr Drift (Spalte Drift) gilt nur zwischen M1 und M2."),
        ("h", "Regressionslinien im Graphen"),
        ("p", "Das Häkchen \"Regressionslinien\" (zweite Zeile der Werkzeugleiste, ebenso im Detailfenster) blendet "
              "je Signal die lineare Regressionsgerade über alle Daten ein: gestrichelt, in der Farbe des Signals, "
              "über den Datenbereich des Signals und an der Achse des Signals (links oder rechts). Es ist dieselbe "
              "Gerade, aus der die Spalten Drift (Regression) und Prognose rechnen."),
        ("b", "Beim Zoomen bleiben die Striche gleich lang; die Linien stehen nicht in der Legende."),
        ("b", "Die Regressionslinien haben keine eigenen Einträge im Signalspiegel (Legende) des Graphen: Kurve und "
              "Linie bilden ein Element. Ein Klick auf den Eintrag eines Signals im Signalspiegel deaktiviert das "
              "Signal samt Regressionslinie, ein weiterer Klick aktiviert beide wieder. Druck und Export zeigen nur die "
              "Linien der aktiven Signale."),
        ("b", "Druck, Export und beide Reports zeigen die Geraden ebenfalls gestrichelt. Die Einstellung wird gemerkt "
              "und mit Ansicht und Projekt gespeichert."),
        ("h", "Zielzeit"),
        ("p", "Neben Y max steht je Signal das Feld Zielzeit: die Zeit, die bis zum Erreichen der Grenze mindestens "
              "vergehen soll, in Tagen, Stunden und Minuten, z. B. 2d 6h 30m (auch 2t 6std, 90min, 1,5h). Ohne "
              "Einheit gilt: eine Zahl = Stunden, zwei Zahlen = Stunden Minuten, drei = Tage Stunden Minuten. Leer = "
              "keine Zielzeit."),
        ("b", "\"Alle\" neben dem Feld überträgt diese Zielzeit auf alle Signale aller Graphen (leeres Feld entfernt "
              "sie überall); danach lässt sie sich je Signal wieder ändern."),
        ("b", "Verletzt ist die Zielzeit, wenn die Prognose die Grenze früher erreicht als die Zielzeit oder die "
              "Grenze schon überschritten ist. Dann wird die Zeile des Signals rot hinterlegt, die Prognose um "
              "\"(Zielzeit ... verletzt)\" ergänzt und der Graph, in dem das Signal steht, schwach rot hinterlegt. "
              "Das Rot ist je Farbschema abgestimmt: Linien und Text bleiben gut lesbar."),
        ("b", "Bewertet wird nur mit aktiven Markern, gesetzter Grenze und Zielzeit sowie einer Zeitachse "
              "(Datum/Uhrzeit-Achse oder X in s, min, h, d)."),
        ("b", "Gilt ebenso im Detailfenster (Graph und eigene Wertanzeige), beim Drucken und Export (schwach roter "
              "Graph) und in beiden Reports: Tabelle Grenzen und Prognose mit Zielzeit und Zielzeit-Status, rot "
              "hinterlegte Zeilen des Signals in allen Tabellen des Graphen. Zielzeiten werden in Ansicht und "
              "Projekt gespeichert und beim Dateiwechsel übernommen."),
        ("h", "Grenzwert-Konfiguration (YAML) je Mode"),
        ("p", "Graph-Optionen > Grenzwert-Konfiguration laden (*.yaml) liest eine Konfigurationsdatei mit Grenzen und "
              "Zielabständen je Mode (Aufbau: limits > modes > Mode > steps und signals > Signal > enabled, lower, "
              "upper; weitere Abschnitte der Datei werden nicht verwendet). Ohne Konfiguration gelten die manuellen "
              "Werte."),
        ("b", "Die Modes der Datei stehen in der Auswahl \"Mode\" in der Kopfzeile der Wertanzeige (Marker aktiv); "
              "\"(manuell)\" schaltet zurück auf die manuellen Werte. Daneben stehen Name und Umfang der geladenen "
              "Konfiguration."),
        ("b", "Die Signale werden über den Namen zugeordnet (genau, ohne Groß-/Kleinschreibung, ohne Einheit in "
              "Klammern). Für zugeordnete Signale mit enabled: true gelten die Grenzen des Modes; ihre Felder "
              "zeigen die Werte der Konfiguration. Signale, die der Mode nicht nennt oder die "
              "nicht passen, behalten die manuellen Grenzen und Zielzeiten."),
        ("b", "steps ist der Zielabstand bis zur Grenzverletzung, als Schritte oder als Zeit: Eine Zahl ohne Einheit "
              "(steps: 26306) bedeutet Schritte, also Messpunkte (Abstand bis zur Grenze geteilt durch den typischen "
              "Abstand zweier Messpunkte); mit Einheiten (steps: 7h 18m 26s, 45m, 90s, auch d für Tage) bedeutet es "
              "Zeit. Ist die Prognose kürzer, gilt das Signal als verletzt (rote Zeile, "
              "schwach roter Graph, wie bei der Zielzeit). Ein Mode ohne steps (null) lässt die manuellen "
              "Zielzeiten gelten."),
        ("b", "Die Statuszeile meldet, wie viele Signale des Modes zugeordnet wurden. Konfiguration und Mode "
              "werden mit Ansicht und Projekt gespeichert; der Report nennt sie unter Einstellungen "
              "und kennzeichnet Ziele aus der Konfiguration mit (YAML). Beispiel: demo_data/demo_grenzen.yaml zu "
              "demo_pruefstand.asc."),
        ("h", "Werte in der Wertanzeige ändern und in die YAML zurückschreiben"),
        ("p", "Ist eine Konfiguration übernommen, lassen sich Grenzen und steps auch direkt in der Wertanzeige ändern "
              "(ebenso im Detailfenster). Bei Signalen aus der Konfiguration geht die Änderung in den Mode, nicht in "
              "die manuellen Werte: Grenzlinien, Prognose und Bewertung folgen sofort, ein offener Konfigurator zeigt "
              "die neuen Werte, die Kopfzeile meldet \"* geändert\"."),
        ("b", "Hat der Mode steps, gilt dieser eine Wert als Zielzeit für alle Signale der Wertanzeige, auch für "
              "Signale ohne Eintrag in der Konfiguration (wie im Konfigurator: eine Einstellung je Mode). Das Feld "
              "Zielzeit zeigt ihn bei jedem Signal (Zahl = Schritte, mit Einheiten = Zeit); eine Änderung in "
              "irgendeiner Zeile gilt für alle, \"Alle\" entfällt dann. Ein Mode ohne steps lässt die manuellen "
              "Zielzeiten gelten."),
        ("b", "\"In YAML speichern\" in der Kopfzeile schreibt die Änderungen in die geladene Datei zurück (andere "
              "Modes und Abschnitte bleiben); eine neue, noch nicht gespeicherte Konfiguration fragt nach dem "
              "Dateinamen."),
        ("b", "Werden beide Grenzen eines Signals geleert, gilt es nicht mehr als konfiguriert und nutzt wieder die "
              "manuellen Werte. Signale ohne Eintrag in der Konfiguration bleiben manuell."),
        ("h", "Grenzwert-Konfigurator"),
        ("p", "Graph-Optionen > Grenzwert-Konfigurator öffnet ein Fenster, in dem sich eine Grenzwert-Konfiguration anlegen, "
              "bearbeiten, mit Namen speichern und laden lässt. Ist noch keine geladen, legt es eine neue mit dem "
              "Mode \"Standard\" an und verwendet sie sofort."),
        ("img", "konfigurator", "Bild 12: Grenzwert-Konfigurator"),
        ("m", "1", "Name der Konfiguration (* = geändert, nicht gespeichert); Neu, Laden, Speichern, Speichern unter"),
        ("m", "2", "Mode wählen, neu anlegen, kopieren, umbenennen, löschen (Name im Feld daneben)"),
        ("m", "3", "steps des Modes: Zahl = Schritte, mit Einheiten = Zeit (z. B. 7h 18m 26s); daneben die Deutung und ob der Mode im Programm gilt"),
        ("m", "4", "Grenzen aus Daten vorschlagen: Dieser Mode / Alle Modes; Abstand in Prozent der Spannweite gilt für beide"),
        ("m", "5", "Alle Signale der geladenen Dateien mit Datenbereich: aktiv, untere und obere Grenze"),
        ("b", "Die Tabelle zeigt jedes Signal der geladenen Dateien einmal, mit Datei sowie kleinstem und größtem "
              "Wert. Signale, die nur in der Konfiguration stehen, folgen am Ende (nicht in den Daten). Suche und "
              "\"Nur aktive\" grenzen die Liste ein; \"Sichtbare aktivieren/deaktivieren\" wirkt auf die "
              "angezeigten Zeilen."),
        ("b", "Grenzen aus Daten - zwei Varianten mit demselben Prozent-Abstand: \"Dieser Mode\" gilt "
              "nur für den bearbeiteten Mode (sichtbare aktive Signale ohne Grenzen). \"Alle Modes\" geht alle Modes der Konfiguration durch (aktive Signale ohne Grenzen, Suchfeld gilt): Daten "
              "je Mode aus der Auto-Analyse aller Dateien dieses Modes (alle DUTs), für Modes ohne Analyse aus allen "
              "geladenen Dateien. Vorhandene Grenzen und inaktive Signale bleiben unverändert; Modes ganz ohne Daten "
              "nennt die Statuszeile. Beispiel 10 %: Daten 600..630 -> Grenzen 597..633."),
        ("b", "Eine Grenze für ein noch nicht konfiguriertes Signal aktiviert es. Leere Felder bedeuten keine "
              "Grenze auf dieser Seite; ein Signal ohne aktive Grenze behält die manuellen Werte."),
        ("b", "Änderungen wirken sofort: Ist der bearbeitete Mode im Programm gewählt (\"wirkt im Programm\"), "
              "folgen Grenzlinien, Wertanzeige, Prognose, Zielzeit-Bewertung, Detailfenster und Report direkt. "
              "\"Diesen Mode im Programm verwenden\" wählt ihn dort aus."),
        ("b", "Speichern schreibt die YAML im gleichen Aufbau (limits > modes > ...); eine neue Konfiguration "
              "fragt dabei nach dem Dateinamen. Andere Abschnitte einer geladenen Datei (z. B. plot, colors) und "
              "deaktivierte Signale bleiben erhalten. Laden geht im Fenster oder über Graph-Optionen > Grenzwert-Konfiguration "
              "laden."),
    ]),
    ("Limiter", [
        ("p", "Der Limiter reduziert die Daten einzelner Dateien auf die Abschnitte, in denen ein oder mehrere "
              "Führungssignale in ihren Grenzen liegen. Beispiel: Eine Datei enthält ein Rechtecksignal; nur der obere "
              "Anteil (z. B. Wert ab 4,5) soll der führende Plotbereich sein - und zwar für alle Signale dieser Datei."),
        ("img", "limiter", "Bild 13: Limiter - nur die obere Phase des Rechtecksignals gilt für alle Signale der Datei"),
        ("m", "1", "Menü Limiter: bearbeiten, Konfiguration laden/speichern, Limiter aktiv, Limiter entfernen"),
        ("m", "2", "Limiter aktiv, Laden..., Speichern, Speichern unter... und Name der Konfigurationsdatei"),
        ("m", "3", "Regel hinzufügen"),
        ("m", "4", "Regeltabelle: aktiv, Datei (Name, Muster oder *), Führungssignal, Limit min, Limit max, Löschen"),
        ("m", "5", "Ergebnis je Datei: Anteil der Messzeit im Limit"),
        ("m", "6", "Hinweis in der Dateiliste"),
        ("m", "7", "Gekürzte Daten: Strom nur noch in der oberen Rechteckphase, Lücken trennen die Linie"),
        ("h", "So geht's (Beispiel demo_rechteck.csv)"),
        ("b", "1. demo_data/demo_rechteck.csv öffnen und Rechteck sowie Strom anzeigen."),
        ("b", "2. Limiter > Limiter bearbeiten...: Die erste Regel ist mit der Datei vorbelegt. Signal Rechteck wählen, "
              "Limit min 4,5 eintragen, Limit max leer lassen."),
        ("b", "3. Sofort zeigen alle Graphen der Datei nur noch die obere Phase; in der Dateiliste und im Fenster steht "
              "der Anteil (hier 50 % der Messzeit)."),
        ("b", "4. Weitere Regeln (z. B. Temperatur höchstens 80) wirken zusammen mit der ersten (UND); der Haken aktiv "
              "schaltet eine Regel ab, ohne sie zu löschen."),
        ("b", "5. Speichern unter... legt die Regeln als YAML ab (oder Laden: demo_data/demo_limiter.yaml)."),
        ("h", "Regeln"),
        ("b", "Je Regel: Datei, Signal, Limit min, Limit max. Ein leeres Feld bedeutet keine Grenze auf dieser Seite; "
              "die Grenzen gehören zum Bereich (einschließlich)."),
        ("b", "Mehrere Regeln derselben Datei gelten gleichzeitig (UND): Es bleibt nur, was alle Führungssignale "
              "erfüllen."),
        ("b", "Datei * gilt für alle Dateien, die das Signal enthalten; Muster wie lauf_*.csv sind möglich. Fehlt das "
              "Signal in einer Datei, bleibt diese Datei ungekürzt (Hinweis in der Dateiliste)."),
        ("b", "Haben die Signale verschiedene Zeitbasen (MF4), gilt der Zustand des Führungssignals bis zu seinem "
              "nächsten Messpunkt weiter. Führungssignale aus MF4-Dateien werden dafür automatisch geladen."),
        ("h", "Wirkung"),
        ("b", "Werte außerhalb entfallen wirklich (kleinere Datenmenge). An jeder Lücke trennt ein leerer Punkt die "
              "Linie, damit nichts über die entfernten Abschnitte hinweg verbunden wird."),
        ("b", "Alles arbeitet mit den gekürzten Daten: Graphen, Marker und Wertanzeige (Min, Max, Mittelwert, Drift), "
              "Detailfenster, Druck, Export und Report."),
        ("b", "In der Dateiliste steht je betroffener Datei, wie viel Prozent der Messzeit im Limit liegen."),
        ("h", "Menü Limiter"),
        ("b", "Limiter bearbeiten...: Fenster mit der Regeltabelle. Änderungen wirken sofort (Grenzen als Zahl, Komma "
              "oder Punkt). Zur Auswahl stehen Datei und Signal aus den geladenen Dateien, aus den Auto-Auswertungen "
              "(nach Analysieren oder einem Zyklus: der Gruppenname, z. B. DES202609090470500176_DUT3, steht für alle "
              "Dateien der Auswertung, dazu die einzelnen Dateien) und aus Dateien, die über Datei wählen... manuell "
              "gewählt werden (nur die Signalnamen werden gelesen, die Datei wird nicht angezeigt)."),
        ("b", "Limiter-Konfiguration laden (*.yaml)... / speichern...: Die Regeln stehen im Abschnitt limiter einer "
              "YAML-Datei. Andere Abschnitte bleiben beim Speichern erhalten; Limiter und Grenzwert-Modes können also "
              "in derselben Datei stehen."),
        ("b", "Limiter aktiv: schaltet die Kürzung aus und wieder ein, ohne die Regeln zu verlieren. Limiter entfernen: "
              "alle Regeln weg, alle Daten wieder sichtbar."),
        ("b", "Die Regeln werden mit der Ansicht (*.mgraph) gespeichert und beim Laden wieder angewendet."),
        ("p", "Aufbau der Datei: Abschnitt limiter mit active (true/false) und rules, einer Liste von Regeln mit "
              "file (Dateiname, Muster oder *), signal, min, max (null = keine Grenze) und enabled (true/false)."),
    ]),
    ("Auto-Auswertung", [
        ("p", "Menü Auto > Auto-Auswertung einrichten... wertet ein Verzeichnis selbsttätig und zyklisch aus: Rohdaten "
              "(*.csv, *.asc, *.parquet) einlesen, je Gruppe nach Zeitstempel zusammenfassen, Limiter anwenden, je Signal "
              "einen Einzelgraphen als PNG ablegen und die Istwerte gegen die Grenzwert-Konfiguration als "
              "Time_counter.json bewerten."),
        ("img", "auto", "Bild 14: Fenster Auto-Auswertung (Schritte 1-3) und Fenster Schritt 4"),
        ("m", "1", "Menü Auto: einrichten, Start, Stopp, Einen Zyklus jetzt ausführen, Report erstellen..., Log anzeigen"),
        ("m", "2", "Aktueller Schritt und Zurücksetzen (alle Schritte wieder frei, Beginn bei Schritt 1)"),
        ("m", "3", "Schritt 1: Name der neuen Auswertung und Anlegen"),
        ("m", "4", "Auswertung (nur Auswahl) und Löschen"),
        ("m", "5", "Verzeichnisregel wählen und Verzeichnisregel verwalten..."),
        ("m", "6", "Angaben der Regel zur Information: Quelle, Ziel, Einlesen bzw. Ausschlüsse, Zielordner und Modes"),
        ("m", "7", "Schritt 2: Modes und Zielzeiten... mit Zustand"),
        ("m", "8", "Fenster Modes und Zielzeiten: ähnliche Namen gruppiert, Häkchen = verarbeiten, Zielzeit hh:mm:ss je Mode"),
        ("m", "9", "Schritt 3: Analysieren, Grenzwert-Konfigurator, Limiter, Grenzen neu vorschlagen"),
        ("m", "10", "Schritt 4: Fenster Schritt 4 öffnen... (öffnet sich beim Abschließen von Schritt 3 von selbst)"),
        ("m", "11", "Fenster Schritt 4: Zykluszeit, Ergebnisdatei, Start, Stopp, Jetzt ausführen, Log, Report - darunter "
                    "der Fortschritt"),
        ("m", "12", "Ergebnis aller Auswertungen: Auswertung, DUT/Teil, Mode, Gruppe, Ist, Ziel, Erfüllung (darunter das Log)"),
        ("b", "Ergebnistabelle (Schritt 4): je Zeile Auswertung, DUT/Teil, Mode, Gruppe (Seriennummer/DUT, gleichnamiger "
              "Bildordner; der Schlüssel count_<Mode>_<Gruppe> der Ergebnisdatei steht im Tooltip der Zelle), Ist und Ziel "
              "(bei Zielzeit als h:mm:ss, z. B. 180:51:08 von 24:00:00, sonst Messpunkte mit Tausenderpunkt) und Erfüllung "
              "in Prozent (grün ab 100 %, sonst rot). Die Tabelle füllt das Fenster bis zum Log."),
        ("b", "Gruppen und Bildordner: Liegen die Dateien eines Quellordners in Unterordnern mit Seriennummer (z. B. "
              "...\\HTOE22kW\\CSV\\DES202507230117500132\\*.csv), bekommt jede Seriennummer eine eigene Gruppe und einen "
              "eigenen Bildordner - die Seriennummern werden nicht mehr zu einer Gruppe \"CSV\" zusammengeworfen. Ohne "
              "Seriennummer-Ordner heißt die Gruppe nach DES-Nummer + DUT, sonst nach der Seriennummer im Dateinamen (z. B. "
              "DS202608200479700017), sonst nach dem gemeinsamen Dateinamen; ein nichtssagender Ordnername (CSV, Files, "
              "Report, Data ...) wird nie verwendet, dann der nächste Ordner darüber (z. B. HTOE22kW)."),
        ("h", "So geht's - feste Reihenfolge in vier Schritten"),
        ("b", "Jeder Schritt hat eine Überschrift mit Zustand ([jetzt], [erledigt - gesperrt], [folgt]), einen "
              "erklärenden Text und ausführliche Tooltips an allen Feldern und Schaltflächen. Nur der aktuelle Schritt ist "
              "bedienbar; Schritt abschließen prüft ihn, sperrt ihn und gibt den nächsten frei. Start (Durchlauf "
              "gestartet) gibt alle Schritte wieder frei, ebenso Zurücksetzen (dann Beginn bei Schritt 1)."),
        ("b", "Schritt 1 - Auswertung festlegen, Feld für Feld: (1) Name: Namen der neuen Auswertung eingeben und mit "
              "Anlegen bestätigen; ist das Feld leer, wird unten eine vorhandene Auswertung gewählt; gibt es noch keine, "
              "weist ein Hinweis darauf hin, dass ein Name notwendig ist. (2) Auswertung: nur Auswahl; ohne Einträge "
              "Hinweis auf die Eingabe eines Namens. (3) Verzeichnisregel: Regel aus den bisher definierten wählen; gibt "
              "es noch keine, weist ein Hinweis darauf hin, dass eine Regel erstellt werden muss. Verzeichnisregel "
              "verwalten... öffnet den Verzeichnisverwalter und nimmt den Namen als neue Regel (hat die Auswertung schon "
              "eine Regel, wird diese bearbeitet)."),
        ("b", "Darunter stehen die Angaben der Regel nur zur Information (ohne Eingabe): Quellverzeichnis, Zielverzeichnis "
              "(Basis Zielordner + erweiterter Zielordner), Einlesen (alle Dateien oder Zahl der Ausschlüsse) und wie viele "
              "Zielordner und Modes die Regel liefert. Jeder Zielordner der Regel ist ein Teil der Auswertung (z. B. ein "
              "DUT in einem Mode). Abschließen verlangt eine Auswertung mit Regel, die Zielordner mit Messdateien liefert."),
        ("b", "Schritt 2 - Modes und Zielzeiten: Modes und Zielzeiten... öffnet ein Fenster mit allen Modes der "
              "Auswertung; Modes mit ähnlichem Namen sind gruppiert (z. B. AC: AC_22kW_3ph_615V, AC_11kW_1ph_230V). Je Mode "
              "ein Häkchen (verarbeiten) und die Zielzeit hh:mm:ss (z. B. 24:00:00 oder 07:18:26; gilt für alle DUTs des "
              "Modes). Nicht angehakte Modes brauchen keine Zielzeit. Alle/Keine und für alle angehakten setzen viele auf "
              "einmal. Abschließen verlangt für jeden angehakten Mode eine Zielzeit."),
        ("b", 'Eigene Modes: unten im Fenster lässt sich ein Mode mit Name und Zielzeit (hh:mm:ss) vorab festlegen ("Eigener Mode", "Hinzufügen"), auch wenn es ihn im Quellverzeichnis noch nicht gibt. Er steht unter "Eigene Modes, noch nicht gefunden" mit Häkchen, Zielzeit und "Entfernen". Kommt später ein Mode gleicher Struktur mit genau diesem Namen hinzu (z. B. AC_22kW_3ph_900V neben ..._615V), übernehmen seine neuen DUTs beim nächsten Zyklus Zielzeit und Häkchen. Gibt es den Mode schon, gilt die Zielzeit sofort für alle seine DUTs. Eigene Modes werden mit der Auswertung gespeichert.'),
        ("b", 'Zielvorgabe je Mode (gefunden und eigene): Zeit (hh:mm:ss), Flankenzahl oder Ignorieren. Zeit = Zielzeit für Time Counter und Violation. Flankenzahl = Ziel des Flanken Counters für Flanken ohne eigenes Ziel; die Signale und das Werteband werden in Schritt 4 unter "Flanken definieren..." festgelegt (die Zeile weist darauf hin, solange der Flanken Counter nicht gewählt oder keine Flanke definiert ist); eine Zielzeit gibt es dann nicht. Ignorieren = der Mode wird komplett ignoriert (Häkchen aus, keine Bilder, Zähler oder Reports); Häkchen wieder setzen stellt auf Zeit zurück. Leere Zeit bzw. Flankenzahl = unendlich: der Mode wird verarbeitet, es kann keine Violation geben (Textblock: Zielzeit unendlich), Erfüllung bleibt leer. Schritt 2 lässt sich ohne Zielzeit abschließen und nennt diese Modes.'),
        ("b", 'Nur eigene Modes ohne Daten: Ist kein gefundener Mode angehakt, aber ein eigener Mode (nicht Ignorieren) wartet auf Daten, lassen sich Schritt 2 und 3 trotzdem abschließen und der Zyklus starten. Jeder Zyklus sucht die Ordner der Verzeichnisregel neu; taucht der Mode auf, wird er mit seiner Zielvorgabe verarbeitet und seine Grenzen werden aus den Daten vorgeschlagen.'),
        ("b", "Schritt 3 - Analysieren und Grenzen prüfen: Analysieren liest alle Dateien (alle angehakten Modes und DUTs) "
              "und schlägt je Mode Grenzen vor; im Grenzwert-Konfigurator prüfen und speichern, bei Bedarf Limiter-Regeln "
              "setzen und Grenzen neu vorschlagen."),
        ("b", "Schritt 4 - eigenes Fenster: Wegen der Informationsmenge öffnet Schritt abschließen in Schritt 3 ein "
              "zweites Fenster Auto-Auswertung - Schritt 4; das Fenster mit den Schritten 1 bis 3 bleibt offen. Später "
              "öffnet Fenster Schritt 4 öffnen... (oder Auto > Log anzeigen) es wieder. Der Fortschritt erscheint in "
              "beiden Fenstern."),
        ("b", "Schritt 4 - Zyklus starten: Zykluszeit (z. B. 2m), PNG und Ergebnisdatei festlegen, dann Start (zyklisch) "
              "oder Jetzt ausführen (ein Zyklus sofort). Ergebnisse: PNG und statistics.json im Zielordner, Zähler in "
              "der Ergebnisdatei; Report über Report erstellen... (je Mode einer mit allen DUTs)."),
        ("h", "Mehrere Auswertungen"),
        ("b", "Es können mehrere Auswertungen angelegt werden (je Name eine, mit eigener Verzeichnisregel). Der Zyklus "
              "bearbeitet alle Auswertungen nacheinander; Schritte 2 und 3 beziehen sich auf die gewählte Auswertung."),
        ("b", "Mode und DUT kommen aus der Regel ({Mode}, {DUTx}); so teilen sich alle DUTs eines Modes dessen Grenzen. "
              "Der Schlüssel in der Ergebnisdatei ist count_<Mode>_<Gruppe>, die Spalte im Report heißt nach dem DUT."),
        ("b", "Zielzeit (hh:mm:ss, auch 24h, 7h 18m 26s oder Schritte als Zahl): gilt statt der Zielzeit (steps) des Modes "
              "für Zähler, steps in der Ergebnisdatei, Zeit bis Violation und den roten Hintergrund."),
        ("b", "Ergebnisdatei (alle) = Zielverzeichnis\\Time_counter.json: Zielverzeichnis ist der Basis-Zielordner der "
              "Verzeichnisregel (z. B. C:\\MessGraph\\_TestResult), nicht der erweiterte Ordner je Mode/DUT. Im Feld steht "
              "nur der Dateiname: Standard Time_counter.json, andere Namen möglich (z. B. HTOE_time_counter.json; .json wird "
              "ergänzt, \\ / : * ? \" < > | sind nicht erlaubt). \"Standard\" setzt den Namen zurück; darunter steht der volle "
              "Pfad. Alle Modes und DUTs schreiben in jedem Zyklus nacheinander in diese eine Datei und ergänzen ihre "
              "Einträge; Bilder und Log liegen im jeweiligen erweiterten Zielordner."),
        ("b", "Teile ohne Messdateien oder ohne Zielordner werden mit Hinweis ausgelassen, die anderen laufen. Die Tabelle "
              "zeigt die Zähler aller Auswertungen, der Fortschrittsbalken nennt die gerade laufende."),
        ("b", "Ältere Einstellungen mit von Hand eingetragenem Quell- und Zielverzeichnis bleiben als Auswertungen ohne "
              "Verzeichnisregel erhalten und laufen weiter (Info: Ohne Verzeichnisregel)."),
        ("h", "Einstellungen"),
        ("b", "Basisordner des Programms: Programmordner\\Test. Die Ordnerauswahl im Verzeichnisverwalter beginnt dort "
              "(oder beim schon eingetragenen Ordner)."),
        ("b", "Erweitert: Gruppierung der Dateien (aufklappbar in Schritt 1): Alle Dateien eines Zielordners = eine "
              "Auswertung (Standard) oder Gruppen nach Gruppenmuster."),
        ("b", "Zykluszeit: 60s, 5m, 1h ... (mindestens 5 s). Der erste Zyklus startet sofort."),
        ("b", "Ergebnisdatei (Standard Time_counter.json), PNG je Signal ein/aus, nur Modes mit Treffern."),
        ("b", 'Zähler: Time Counter (Standard) oder Flanken Counter. Der Flanken Counter zählt statt der Zeit in den Grenzen die Flanken eines oder mehrerer Signale über alle Daten-Files der Gruppe. "Flanken definieren...": je Signal Wert1 (oben), Wert2 (unten, je eins darf leer bleiben), Mindestanzahl n und optional ein Ziel (Anzahl Flanken).'),
        ("b", 'Flanke über Wert1: Signal übersteigt Wert1, bleibt mindestens n Werte darüber und fällt danach für mindestens n Werte wieder darunter. Flanke unter Wert2: Signal unterschreitet Wert2, bleibt mindestens n Werte darunter und steigt danach für mindestens n Werte wieder darüber. Kürzere Ausreißer zählen nicht; beginnt das Signal schon jenseits der Schwelle, zählt dieser erste Abschnitt nicht; ist die Rückkehr am Ende noch offen, steht in der Tabelle "(+1 offen)". Ergebnisdatei dann Flanken_counter.json (Schlüssel edges_<Signal>_<Gruppe> mit actual, edges_upper, edges_lower, steps, fulfillment_percent); eigene Dateinamen bleiben. In der Tabelle heißen die Spalten dann Signal und Flanken.'),
        ("b", 'Violation im Flanken Counter: Ist eine Flankenzahl als Ziel angegeben (Ziel der Flanke in Schritt 4 oder Flankenzahl des Modes in Schritt 2), bezieht sich die Violation nicht auf die Zeit, sondern auf die Flanken. Je Signal mit Grenzen: zu erwartende Flanken bis zur Grenzverletzung = gezählte Flanken + Flankenrate (gezählt / Messzeit ohne Lücken) * Zeit bis Violation aus der Trendlinie. Weniger als das Ziel = "Violation vor Ziel-Flankenzahl!" (roter Hintergrund). Grenze schon erreicht: gezählte Flanken gegen das Ziel; Trend läuft auf keine Grenze zu: unendlich, keine Violation. Textblock: Ziel, gezählte Flanken, Flanken bis Violation. In der Ergebnisdatei je Eintrag violation, edges_to_violation, violation_signal und duration_s; in der Tabelle "Erfüllung ... - Violation" mit Tooltip. Ohne Flankenziel gibt es keine Violation.'),
        ("b", "Gruppenmuster: leer = automatisch. Dateinamen mit DES-Nummer und DUT (z. B. HTOE_PV_DES202609090470500176_"
              "AC_22kW_3ph_725V_DUT3) bilden die Gruppe DES202609090470500176_DUT3; sonst gilt der Dateiname ohne "
              "angehängte Zähler und Zeitstempel (Messung_001, Messung_002 -> Messung). Eigenes Muster: regulärer Ausdruck, "
              "alle Klammergruppen werden mit _ verbunden, z. B. (DES\\d+).*(DUT\\d+)."),
        ("h", "Ablauf eines Zyklus"),
        ("b", "Nur neue oder geänderte Dateien werden gelesen (Änderungszeit und Größe); bereits gelesene Daten bleiben im "
              "Speicher. Gelöschte Dateien fallen aus ihrer Gruppe heraus. Nicht lesbare Dateien werden erst wieder "
              "versucht, wenn sie sich ändern."),
        ("b", "Alle Dateien des Quellordners = eine Auswertung (Standard): Alle Dateien werden zu einer Messung "
              "zusammengefügt, auch wenn sie unterschiedliche Signale enthalten. Name der Auswertung: DES-Nummer + DUT "
              "aus den Dateinamen, sonst gemeinsamer Grundname, sonst Ordnername. Ausgeschaltet bilden die Dateien "
              "Gruppen nach Dateiname (Gruppenmuster)."),
        ("b", "Zeitstempelrichtig aneinanderreihen: Beim Lesen wird je Datei die Kopfzeile gesucht (auch hinter einem "
              "Vorspann) und die Startzeit bestimmt - in dieser Reihenfolge: Datumsspalte in den Daten, Datum und "
              "Uhrzeit in der ersten Datenzeile, Uhrzeit der ersten Datenzeile mit Datum aus Vorspann oder Dateiname, "
              "Zeitstempel im Vorspann (z. B. Start: 09.06.2026 10:00:00), Zeitstempel im Dateinamen, zuletzt die "
              "Änderungszeit der Datei (Hinweis im Log). Danach werden die Dateien nach dieser Zeit sortiert - nicht "
              "nach Name oder Änderungszeit - und aneinandergehängt; doppelte Zeiten nur einmal, Lücken zwischen "
              "Dateien trennen die Linie."),
        ("b", "Das Log nennt je Datei die erkannte Startzeit und woher sie stammt; das Fenster zeigt nach der Analyse "
              "eine Übersicht (z. B. 12x Datumsspalte)."),
        ("b", "Der Limiter (Menü Limiter) gilt auch hier: Regeln, deren Datei-Muster auf den Gruppennamen oder eine "
              "Datei der Gruppe passt, kürzen die zusammengefassten Daten. Limiter bearbeiten... im Auto-Fenster bietet "
              "nach Analysieren die Gruppe und die Signale des Quellordners an; Datei wählen... beginnt im Quellordner."),
        ("b", "Jede Datei steht nur einmal zur Wahl (auch wenn sie in mehreren Auswertungen vorkommt, ohne Rücksicht auf "
              "Groß-/Kleinschreibung); eine Auswertungsgruppe aus genau einer Datei erscheint nur als diese Datei."),
        ("b", "Regel übertragen: eine definierte Regel (Datei, Signal, Limit min/max, aktiv) auf eine Auswahl von Dateien "
              "anwenden. Regel wählen, über die Schaltfläche Dateien: ... die Dateien anhaken (Alle, Keine, Nur mit Signal; "
              "Dateien ohne das Signal sind gekennzeichnet), Auf Auswahl anwenden. Hat eine Datei schon eine Regel für "
              "dieses Signal, übernimmt sie Grenzen und aktiv, sonst wird eine Regel ergänzt. Zur Auswahl stehen alle "
              "bekannten Dateien und Auswertungsgruppen (geladene Dateien, Auto-Auswertungen, Datei wählen...)."),
        ("b", "Grenzen und Limiter: Analysieren und die Vorschläge berücksichtigen den Limiter - Minimum, Maximum und "
              "vorgeschlagene Grenzen stammen nur aus den Abschnitten im Limit, weggeschnittene Spitzen zählen nicht "
              "mit. Wird eine Limiter-Regel nachträglich angelegt oder geändert, erscheint im Auto-Fenster ein Hinweis; "
              "Grenzen neu vorschlagen berechnet dann die Grenzen des Modes der Auswertung neu aus den gekürzten Daten "
              "(aktiv/inaktiv und Zielzeit bleiben). Danach prüfen und die Grenzwert-Konfiguration speichern."),
        ("b", "Bewertung je Mode der Grenzwert-Konfiguration: gezählt werden die Messpunkte, in denen alle Signale des "
              "Modes in ihren Grenzen liegen. Ergebnis je Mode und Gruppe unter count_<Mode>_<Gruppe>: actual (in der "
              "Einheit des Ziels: Messpunkte, bei steps als Zeit Sekunden), actual_count (Messpunkte), steps (Ziel aus der "
              "Konfiguration) und fulfillment_percent (actual / steps * 100). Vorhandene Einträge anderer Gruppen in der "
              "Datei bleiben erhalten."),
        ("h", "Quellordner analysieren und bedaten"),
        ("b", "Analysieren (Schritt 3) liest alle Dateien der angehakten Modes und DUTs. Die Signale erscheinen im "
              "Grenzwert-Konfigurator (Spalte Datei: Auto: n Dateien, dazu Daten min/max über alle Dateien)."),
        ("b", "Ist eine Grenzwert-Konfiguration geladen, gilt sie; die Statuszeile nennt, wie viele Signale noch keinen "
              "Eintrag haben. Im Konfigurator lassen sie sich aktivieren und mit Vorschlagen aus den Daten bedaten."),
        ("b", "Ohne Konfiguration werden alle Signale mit Vorschlägen aufgelistet: Mode Auto, alle Signale aktiv, untere "
              "und obere Grenze aus den Daten (1-%- bis 99-%-Wert plus 10 % der Spannweite), Zielzeit 24h (24h 00m 00s). "
              "Signale lassen sich deaktivieren, Grenzen und Zielzeit ändern; Speichern legt die Konfigurationsdatei an."),
        ("b", "Mode: Jeder Teil der Auswertung nutzt genau einen Mode ({Mode} der Verzeichnisregel). Seine Grenzen und "
              "seine Zielzeit gelten für alle Dateien dieses Teils."),
        ("img", "autograph", "Bild 15: Einzelgraph der Auto-Auswertung (Violation vor Zielzeit)"),
        ("m", "1", "Obere Grenzlinie (Limit_max)"),
        ("m", "2", "Untere Grenzlinie (Limit_min)"),
        ("m", "3", "Trendlinie (gestrichelt), über das Datenende hinaus verlängert"),
        ("m", "4", "Textblock: Signal, Grenzen, Regression mit m, b und f(x) = m * x + b"),
        ("m", "5", "Zielzeit, Zeit bis Violation und Bewertung"),
        ("m", "6", "Roter Hintergrund: Violation vor Zielzeit"),
        ("b", "Hintergrundfarbe des Graphen: hellrot = Regression erreicht eine Grenze vor der Zielzeit; hellgelb = "
              "Messwerte (Peaks) liegen außerhalb Limit_min/Limit_max (Textzeile \"Peaks außerhalb der Grenzen!\"); "
              "hellviolett = beides; weiß = in Ordnung."),
        ("b", "Bilder: je Signal ein Einzelgraph mit allen Daten der Auswertung im Unterordner der Auswertung. Ohne das "
              "Paket Pillow entsteht SVG statt PNG. Inhalt jedes Graphen:"),
        ("b", "obere und untere Grenzlinie (rot gestrichelt, aus dem Mode) und die Trendlinie (orange gestrichelt, "
              "Regressionsgerade der unter Graph-Optionen > Drift-Regression gewählten Art, 20 % über das Datenende "
              "hinaus verlängert)."),
        ("b", "Textblock rechts: Signalname, Limit_max, Limit_min, verwendete Regression mit Nummer, m und b sowie die "
              "Geradengleichung f(x) = m * x + b (x in Sekunden ab dem ersten Messpunkt), Zielzeit, Zeit bis Violation "
              "(ab dem letzten Messpunkt entlang der Trendlinie bis zur Grenze) und die Bewertung."),
        ("b", "Liegt die Violation vor der Zielzeit (oder ist die Grenze schon erreicht), ist die Plotfläche rot "
              "hinterlegt und der Textblock meldet Violation vor Zielzeit!"),
        ("h", "Fortschritt"),
        ("b", "Während Analysieren und während eines Zyklus zeigt ein Fortschrittsbalken im Auto-Fenster und in der "
              "Statuszeile des Hauptfensters, was gerade passiert: Lese Dateien 3/12: Dateiname, Erzeuge Bilder 5/80: "
              "Signal, Schreibe Ergebnisdatei. Abbrechen beendet die Arbeit nach der aktuellen Datei bzw. dem aktuellen "
              "Bild; der Rest folgt im nächsten Zyklus."),
        ("h", "Report über mehrere Auswertungen"),
        ("img", "report", "Bild 16: Report erstellen mit Zeitplan"),
        ("m", "1", "Auswertungen (je eine ein DUT) anhaken"),
        ("m", "2", "Titel, Projekt, Mode"),
        ("m", "3", "Ausgabeordner (leer = gemeinsamer Ordner der Zielverzeichnisse)"),
        ("m", "4", "Wasserzeichen NOT RELEASED (standardmäßig an)"),
        ("m", "5", "Zeitplan ein/aus"),
        ("m", "6", "Uhrzeiten, täglich oder einmalig"),
        ("m", "7", "Nächster Termin"),
        ("m", "8", "Report sofort erstellen"),
        ("m", "9", "Fortschritt (der Report wird nicht abgebrochen)"),
        ("b", "Auto > Report erstellen...: Jede Auswertung entspricht einem DUT. In der Liste werden die Auswertungen "
              "angehakt, die in den Report sollen (Auswertungen ohne Ausgaben sind abgewählt; Alle/Keine). Titel, Projekt, "
              "Mode und Ausgabeordner lassen sich eintragen."),
        ("b", "Auswertung (oben im Fenster): Der Report nimmt nur die DUTs der gewählten Auswertung (Standard: die in Auto "
              "gewählte), also nur deren Zielordner - Teile anderer oder alter Auswertungen mit gleichem Namen werden nicht "
              "gemischt. Neue Modes und DUTs, die die Verzeichnisregel später findet, sind automatisch angehakt (auch "
              "beim Report nach Zeitplan); gemerkt werden nur ausdrücklich abgewählte Zielordner. \"Alle Auswertungen\" "
              "zeigt alle Teile mit vorangestelltem [Auswertung]. Steht ein DUT ohne Ausgaben in der Liste, nennt der "
              "Hinweis den Grund (z. B. Mode in Schritt 2 nicht zur Verarbeitung gewählt, Quellverzeichnis fehlt)."),
        ("b", "Je Mode ein Report: Die angehakten Auswertungen werden nach Mode gruppiert; jeder Mode bekommt einen eigenen "
              "Report mit allen gewählten DUTs dieses Modes. Dateiname: Report_<Mode>_<Datum_Uhrzeit>.pdf, z. B. "
              "Report_DC_Charge_V2L_540V_20261116_151230.pdf. Ausgabeordner leer = gemeinsamer Ordner der "
              "Zielverzeichnisse des Modes (z. B. _TestResult), bei einem DUT dessen Zielverzeichnis. Mode leer = Mode der "
              "Auswertungen; ein eingetragener Mode gilt nur, wenn genau ein Report entsteht."),
        ("b", "Jedes Zielverzeichnis steht nur einmal zur Wahl; doppelte Auswertungen (gleiche Quelle und gleiches Ziel) "
              "werden beim Laden und Anlegen automatisch entfernt."),
        ("b", "Ohne vorherigen Zyklus: Gewählte Auswertungen ohne Ausgaben (z. B. nur Analysieren gedrückt) bekommen beim "
              "Report erstellen zuerst automatisch einen Zyklus, danach entstehen die Reports. Läuft gerade eine Analyse "
              "oder ein Zyklus, wird der Report danach erstellt. Auswertungen ohne Ausgaben sind in der Liste markiert."),
        ("b", "Wasserzeichen: \"NOT RELEASED\" schräg auf jeder Seite ist standardmäßig an und kann vor dem Erstellen "
              "abgewählt werden."),
        ("b", "Graphen pro Seite: 9 (3 x 3), 4 (2 x 2), 2 (nebeneinander) oder 1 (ganze Seite) - gilt nur für den "
              "Mode-Teil (Bilder je DUT); der Vergleichsteil hat immer 9 Graphen pro Seite. Der Abschnitt je DUT ist "
              "mit \"Mode: <Gruppe>\" überschrieben."),
        ("b", "Aufbau (A4 quer): Deckblatt (Test Report, Project, Mode, Date, DUTs) - Summary Comparison (je Signal "
              "der Mittelwert je DUT, Average, Min % und Max % als Abweichung des kleinsten/größten DUT-Werts vom "
              "Average, Limit Min, Limit Max) - Signal Plot Comparison (je Signal eine Seite mit den PNG aller DUTs) - je "
              "DUT eine Tabelle (Min, Max, Mean, Std, Limit Min, Limit Max; Mean grün im Limit, rot außerhalb) und alle "
              "PNG des DUT (3 x 3 je Seite)."),
        ("b", "Grundlage sind die Ausgaben der Zyklen: je Auswertung die PNG und statistics.json im Zielverzeichnis. "
              "Der Report läuft im Hintergrund mit Fortschrittsbalken; die PNG werden unverändert eingebettet."),
        ("b", "Report erstellen wird nicht abgebrochen (auch kein Abbrechen-Knopf): Fehler wie fehlende oder kaputte Bilder, "
              "unlesbare statistics.json, Auswertungen ohne Ausgaben, Fehler in einem Abschnitt oder ein belegter "
              "Dateiname werden gesammelt, alles Übrige wird erzeugt. Ein so unvollständiger Report bekommt auf dem "
              "Deckblatt den roten Hinweis INCOMPLETE REPORT, am Ende den Anhang \"Appendix: Incomplete Report\" mit allen "
              "Gründen und die Dateinamenserweiterung _err, z. B. Report_Precon_20261119_124400_err.pdf. Ist der "
              "Dateiname nicht schreibbar, entsteht der Report unter einem Ausweichnamen (gleicher Ordner mit Uhrzeit, "
              "sonst Benutzerordner); auch das steht im Anhang. Die Statuszeile nennt die Zahl unvollständiger Reports."),
        ("h", "Report nach Zeitplan"),
        ("b", "Der Zeitplan ist vom Datenzyklus entkoppelt: Die Daten können z. B. alle 2 Minuten aktualisiert werden, "
              "der Report entsteht trotzdem nur zu festen Uhrzeiten, z. B. 00:00:00."),
        ("b", "Uhrzeiten: eine oder mehrere, durch Komma getrennt (00:00:00, 12:00, 18:30). täglich: jeden Tag zu jeder "
              "Uhrzeit; einmalig: nur beim nächsten Termin, danach schaltet sich der Zeitplan aus."),
        ("b", "Zum Termin wird der Report mit den gespeicherten Einstellungen erstellt (angehakte Auswertungen, Titel, "
              "Projekt, Mode, Ausgabeordner, Wasserzeichen) - je Mode einer; dank Datum/Uhrzeit im Namen entsteht jedes "
              "Mal eine eigene Datei (Report_<Mode>_20261117_000000.pdf)."),
        ("b", "Der nächste Termin steht im Report-Fenster und im Auto-Fenster; das Log der Auswertungen vermerkt jeden "
              "Report nach Zeitplan. Der Zeitplan läuft, solange MessGraph geöffnet ist, und bleibt für den nächsten "
              "Start gespeichert."),
        ("img", "reportseite", "Bild 17: Beispiel-Report - Summary Comparison und Signal Plot Comparison"),
        ("m", "1", "Summary Comparison: Mittelwert je DUT und Average"),
        ("m", "2", "Min % und Max %: Abweichung des kleinsten/größten DUT-Werts vom Average"),
        ("m", "3", "Limit Min und Limit Max aus dem Mode"),
        ("m", "4", "Signal Plot Comparison: die PNG aller DUTs je Signal"),
        ("m", "5", "Wasserzeichen NOT RELEASED"),
        ("h", "Verzeichnisverwalter"),
        ("img", "verzeichnis", "Bild 18: Verzeichnisverwalter - Verzeichnisregel in sechs Schritten"),
        ("m", "1", "Name der Regel (aus der Auto-Auswertung: Name der Auswertung), vorhandene Regel bearbeiten, löschen"),
        ("m", "2", "Anzeige NEUE Regel bzw. BEARBEITEN einer vorhandenen Regel"),
        ("m", "3", "Schritt 1: Quellordner wählen und Struktur analysieren - Unterordner je Ebene"),
        ("m", "4", "Schritt 2: Daten als Baum, auf- und zuklappbar, Häkchen je Datei bzw. Ordner"),
        ("m", "5", "Schritt 3: Basis Zielordner"),
        ("m", "6", "Schritt 4: erkannte Platzhalter, eigener Wert, einfügen"),
        ("m", "7", "Erweiterter Zielordner aus Platzhaltern, frei kombiniert"),
        ("m", "8", "Schritt 5: Zielordner = Basis Zielordner + Erw. Zielordner, mit Beispiel"),
        ("m", "9", "Schritt 6: Vorschau je Zielordner mit Häkchen, Mode, DUT, Dateien, Status"),
        ("m", "10", "Regel speichern: alle Angaben übernehmen, fehlende Zielordner anlegen"),
        ("b", "Aufruf: Auto-Auswertung, Schritt 1, Verzeichnisregel verwalten... Hier wird die Regel definiert. Standard ist "
              "der Name der Auswertung als Name einer neuen Regel. Wird oben eine andere (vorhandene) Regel gewählt, handelt "
              "es sich um ein Bearbeiten - der Hinweis unter dem Namen zeigt deutlich NEUE Regel bzw. BEARBEITEN; beim "
              "Speichern wird die vorhandene Regel geändert und alle Auswertungen, die sie nutzen, werden nachgezogen."),
        ("b", "Schritt 1 - Quellordner: wählen und Struktur analysieren. Struktur meint die Bezeichnungen der "
              "Unterordner je Ebene, z. B. Ebene 1: DUT1, DUT2 -> {DUTx}; Ebene 3: AC_22kW_3ph_615V, Precon -> {Mode}."),
        ("b", "Schritt 2 - Daten auswählen: alle gefundenen Messdateien als Baum; Ordner sind auf- und zuklappbar, "
              "Standard: alle aktiv. Dateien, die ignoriert werden sollen, abhaken (Häkchen je Datei; je Ordner alle "
              "Dateien dieses Ordners). Bei sehr vielen Dateien (mehr als 3000) gibt es nur Häkchen je Ordner."),
        ("b", "Schritt 3 - Basis Zielordner: über den Browser wählen (z. B. ...\\MessGraph\\_TestResult)."),
        ("b", "Schritt 4 - Platzhalter: MessGraph erkennt selbständig aus den Namen der Unterordner {Mode} (z. B. "
              "AC_22kW_3ph_615V; Ordnernamen wie Precon über ihre Ebene), {Testlauf} (DV, PV), {Test-Variante} "
              "(HTOE_11kW, HTOE_22kW, HTOE_Mix, PTCE_...), {Seriennummer} (DES202507230117500132 ...; sonst aus den "
              "Dateinamen), {DUTx} (setzt die Seriennummer in ein festes Verhältnis) sowie {Datetime} (Systemzeit beim "
              "ersten Speichern) und {Name} (Name der Auswertung). Jedes Element lässt sich optional mit einem eigenen "
              "Wert belegen (Spalte eigener Wert). Der erweiterte Zielordner kombiniert sie frei, z. B. "
              "{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx} oder {Mode}\\{Name}; einfügen hängt einen Platzhalter an."),
        ("b", "Steht der Mode nicht im Ordner-, sondern im Dateinamen, wird er dort erkannt: Beispiel ...\\DV\\HTOE22kW\\CSV\\"
              "DES202507230117500132\\DES202507230117500132_AC_22kW_3ph_615V.csv (ebenso _725V, _800V) -> {Testlauf} = DV "
              "(Quellordner), {Test-Variante} = HTOE22kW, {Seriennummer} = DES202507230117500132, {Mode} = "
              "AC_22kW_3ph_615V usw. aus den Dateinamen; vorgeschlagen wird {Testlauf}_{Test-Variante}\\{Mode}\\"
              "{Seriennummer}. Dann wird ein Ordner auf mehrere Zielordner verteilt (je Mode einer, jeder liest nur "
              "seine Dateien). Eine Datei ohne Mode im Namen (z. B. DES202507230117500132_.csv) erscheint in der "
              "Vorschau gekennzeichnet; in Schritt 2 abwählen. Ein eigener Wert für {Mode} gilt für alle Dateien."),
        ("b", "Schritt 5 - Zielordner = Basis Zielordner + erweiterter Zielordner; ein Beispiel zeigt den ersten Zielordner."),
        ("b", "Schritt 6 - Vorschau prüfen: je Zielordner eine Zeile mit Häkchen (Alle, Keine), Mode, DUT bzw. "
              "Seriennummer, Zahl der Ordner und Dateien (ausgeschlossene in Klammern) und Status (neu, vorhanden). Ordner "
              "ohne Wert für einen Platzhalter (z. B. Logs ohne Mode) sind gekennzeichnet und bleiben außen vor; landen "
              "mehrere DUTs in einem Zielordner, warnt der Status."),
        ("b", "Regel speichern: alle Angaben werden in der Regel gespeichert; fehlende Zielordner werden angelegt. Ist das "
              "nicht möglich (z. B. fehlende Rechte), erscheint ein Fenster mit der Fehlermeldung, und die Regel wird nicht "
              "gespeichert. Kam der Aufruf aus der Auto-Auswertung, bekommt die Auswertung die neue Regel."),
        ("b", "Nur neue Daten werden synchronisiert und bearbeitet: Vorhandene Teile einer Auswertung behalten beim "
              "Speichern ihre gelesenen Daten; neue Ordner und Dateien kommen hinzu, abgewählte fallen heraus. Vor jedem "
              "Zyklus nimmt MessGraph neue Ordner der Regel auf (z. B. ein neuer Mode-Ordner) und legt deren Zielordner an."),
        ("b", "Ältere Regeln (Muster und Vorlage) funktionieren weiter; im Verzeichnisverwalter geöffnet, werden Quellordner "
              "und Zielbasis übernommen und die Platzhalter neu vorgeschlagen."),
        ("h", "Ablauf eines Zyklus im Detail"),
        ("p", "Ein Zyklus startet mit Start sofort und danach jeweils nach der Zykluszeit, mit Jetzt ausführen einmalig. "
              "Die aktiven Auswertungen werden nacheinander bearbeitet (Fortschritt: [Auswertung] Schritt n/m); für jede "
              "laufen die folgenden Schritte. Danach wird die gemeinsame Ergebnisdatei geschrieben."),
        ("b", "1. Fälligkeit: Ist der vorige Zyklus noch nicht fertig, wenn der nächste fällig ist, wird der fällige "
              "ausgelassen (übersprungen, Hinweis im Fenster und im Log); es laufen nie zwei Zyklen gleichzeitig."),
        ("b", "2. Grundlage: Mode der Auswertung aus der Grenzwert-Konfiguration, Zielzeit der Auswertung (ersetzt die "
              "steps des Modes), Limiter-Regeln, Regressionsart. Hat sich eines davon geändert (oder das Ziel, die "
              "PNG-Einstellung), werden alle Gruppen neu bewertet und alle Bilder neu gezeichnet."),
        ("b", "3. Quellordner abgleichen: vorher werden neue Ordner der Verzeichnisregel aufgenommen; gelesen werden "
              "die *.csv, *.asc und *.parquet der Ordner des Teils ohne die im Verzeichnisverwalter abgewählten Dateien; "
              "Dateien im Zielordner werden nie gelesen. Je Datei zählen Änderungszeit und Größe. Gelöschte Dateien werden aus "
              "ihrer Gruppe entfernt (die Gruppe wird neu bewertet)."),
        ("b", "4. Lesen: im ersten Durchlauf alle Dateien, danach nur neue und geänderte, die älteste zuerst. Beim Lesen "
              "werden Kopfzeile und Spalten erkannt und der Zeitstempel bestimmt - in dieser Reihenfolge: Datumsspalte, "
              "Datum/Uhrzeit in der ersten Datenzeile, Uhrzeit mit Datum aus dem Vorspann, Vorspann, Dateiname, "
              "Änderungszeit. Alle Signale werden auf absolute Zeit gebracht. Defekte oder noch im Schreiben befindliche "
              "Dateien werden protokolliert und erst nach einer weiteren Änderung erneut versucht."),
        ("b", "5. Gruppieren: Mit Alle Dateien des Quellordners = eine Auswertung bilden alle Dateien eine Gruppe; sonst "
              "nach dem Dateinamen (Gruppenmuster, DES..._DUTn oder Name ohne angehängte Zähler/Zeitstempel)."),
        ("b", "6. Zusammenfügen: Je Gruppe, in der sich etwas geändert hat, werden alle ihre Dateien nach Zeitstempel "
              "aneinandergereiht. Überlappende Zeitbereiche zählen nur einmal; Lücken zwischen Dateien bleiben Lücken "
              "(die Linie wird getrennt, die Zeit nicht mitgezählt)."),
        ("b", "7. Limiter: Regeln, deren Datei-Muster auf die Gruppe oder eine ihrer Dateien passt, schneiden die "
              "Abschnitte außerhalb ihrer Grenzen heraus - für alle Signale der Gruppe. Der Anteil der Messzeit im Limit "
              "steht im Log."),
        ("b", "8. Bewerten: Gezählt werden die Messpunkte, in denen alle Signale des Modes gleichzeitig innerhalb ihrer "
              "Grenzen liegen. actual = diese Zeit in Sekunden (Zielzeit als Zeit) bzw. die Zahl der Punkte (Zielzeit als "
              "Schritte), actual_count = Zahl der Punkte, steps = Zielzeit, fulfillment_percent = actual / steps. Ohne "
              "Grenzwert-Konfiguration entsteht ein Vorschlag aus den Daten (Grenzen und Zielzeit 24h), der zum Prüfen im "
              "Grenzwert-Konfigurator erscheint."),
        ("b", "9. statistics.json: je Gruppe im Zielordner (Kennwerte, Grenzen, Trend, Zeit bis Violation, Peaks) - "
              "Grundlage für den Report."),
        ("b", "10. Bilder: je Signal ein PNG mit Grenzlinien, gestrichelter Trendlinie, Textblock und Hintergrundfarbe "
              "(rot = Regression verletzt die Zielzeit, gelb = Peaks außerhalb der Grenzen, violett = beides) - nur für "
              "Gruppen mit Änderungen."),
        ("b", "11. Ergebnisdatei: Die Zähler aller Auswertungen gehen in die gemeinsame Time_counter.json (Schlüssel "
              "count_<Mode>_<Gruppe>); vorhandene Einträge anderer Auswertungen bleiben. Geschrieben wird erst in eine "
              ".tmp-Datei, die dann die alte ersetzt - ein Leser sieht nie eine halbe Datei."),
        ("b", "Belegte Ergebnisdatei: Innerhalb von MessGraph schreibt immer nur ein Vorgang (Sperre); mehrere "
              "MessGraph-Instanzen stimmen sich über die Sperrdatei Time_counter.json.lock ab (eine verwaiste Sperrdatei "
              "eines beendeten Programms wird entfernt). Lässt sich die Datei trotzdem nicht ersetzen (unter Windows "
              "\"Access is denied\"), ermittelt MessGraph den belegenden Prozess (z. B. Virenscanner, Windows-Suche, "
              "OneDrive, Editor, zweite Instanz), schreibt ihn ins Log und versucht es etwa 10 s lang erneut; danach wird "
              "der Inhalt direkt in die Datei geschrieben. Fremde Prozesse werden nicht beendet. Gleiches gilt für "
              "statistics.json, PNG und Report."),
        ("b", "12. Log und Anzeige: MessGraph_Auto.log im Zielordner (Erster Durchlauf bzw. Folgedurchlauf, jede Datei "
              "mit Start und Zeitstempelquelle, Limiter, Hinweise, Fehler, Dauer); im Fenster Schritt 4 Statuszeile, "
              "Zähler-Tabelle und Log."),
        ("b", "Abbrechen: hält nach der laufenden Datei bzw. dem laufenden Bild an; der nächste Zyklus macht mit den "
              "offenen Dateien und Bildern weiter."),
        ("b", "Arbeitsspeicher: Die gelesenen Daten bleiben bis zum Programmende im Speicher (daher liest ein "
              "Folgedurchlauf nur Neues). Nach einem Programmstart ist der nächste Zyklus wieder ein erster Durchlauf."),
        ("b", "Report-Zeitplan: läuft unabhängig vom Datenzyklus zu den eingestellten Uhrzeiten; fehlen einer gewählten "
              "Auswertung noch Ausgaben, läuft vorher ein Zyklus."),
        ("h", "Erster Durchlauf und Folgedurchläufe"),
        ("b", "Erster Durchlauf (nach Start, Jetzt ausführen oder Programmstart bzw. nach Änderung von Quelle, "
              "Unterordnern oder Gruppierung): alle Dateien des gewählten Quellordners werden verarbeitet - ohne "
              "Zeitbudget, auch wenn das länger als die Zykluszeit dauert. Im Log steht Erster Durchlauf: alle n Dateien."),
        ("b", "Ab dem zweiten Durchlauf: nur neue und geänderte Dateien (andere Änderungszeit oder Größe) werden gelesen; "
              "gelöschte fallen heraus. Ausgewertet werden die Gruppen, in denen sich etwas geändert hat, jeweils mit "
              "allen ihren Daten. Im Log steht Folgedurchlauf: n neue/geänderte Dateien. Ohne Änderung wird nichts "
              "gelesen und nichts neu gezeichnet."),
        ("h", "Zykluszeit zu kurz"),
        ("b", "Ab dem zweiten Durchlauf arbeitet ein Zyklus höchstens 70 % der Zykluszeit. Was nicht mehr hineinpasst (weitere Dateien, Bilder), "
              "wird auf die folgenden Zyklen verteilt. Läuft ein Zyklus noch, wenn der nächste fällig ist, wird dieser "
              "ausgelassen. In beiden Fällen erscheint ein Hinweis im Fenster und im Log."),
        ("b", "Log: MessGraph_Auto.log im Zielverzeichnis (Start, Stopp, jeder Zyklus, Hinweise, Fehler); Log anzeigen "
              "zeigt die letzten Zeilen im Fenster."),
        ("b", "Start, Stopp und Einen Zyklus jetzt ausführen gibt es im Menü Auto und im Fenster; die Tabelle zeigt die "
              "Zähler des letzten Zyklus. Die Einstellungen bleiben für den nächsten Programmstart gespeichert."),
        ("b", "Einen Zyklus jetzt ausführen (auch ohne Start): sofort und ohne Zeitbudget; alle Gruppen werden neu "
              "bewertet, alle Bilder und die Ergebnisdatei neu geschrieben, auch wenn keine Datei neu ist. Gelesen werden "
              "dabei wie sonst nur neue und geänderte Dateien (beim ersten Durchlauf alle). Die Statuszeile meldet das "
              "Ergebnis."),
        ("b", "Werden Grenzwert-Konfiguration, Mode oder Limiter geändert, bewertet der nächste Zyklus alle Gruppen "
              "neu und zeichnet die Bilder neu."),
    ]),
    ("Datenbasen (DBC, ARXML, A2L, CDD)", [
        ("p", "Eine aufgezeichnete Log-Datei braucht oft mehrere Definitionsdateien zugleich, z. B. eine DBC für den "
              "Antriebs-CAN, eine AUTOSAR-ARXML für den Fahrzeug-CAN, zwei A2L für zwei Steuergeräte und eine CDD. "
              "Zu jeder MF4-, MDF- und BLF-Datei lassen sich deshalb beliebig viele Datenbasen kombinieren: "
              "Schaltfläche \"Datenbasen...\" im Dateieintrag. Enthält die Aufzeichnung CAN-Rohdaten "
              "(CAN_DataFrame), öffnet sich der Dialog beim Laden."),
        ("img", "datenbasen", "Bild 19: Dialog Datenbasen mit DBC, ARXML, zwei A2L und CDD"),
        ("m", "1", "DBC- und ARXML-Dateien, je mit Auswahl des CAN-Kanals"),
        ("m", "2", "Datenbasen hinzufügen (mehrere Dateien auf einmal, alle Arten gemischt)"),
        ("m", "3", "A2L-Dateien und Umrechnung der Rohwerte"),
        ("m", "4", "CDD-Dateien"),
        ("m", "5", "Zuletzt verwendete übernehmen, Anwenden, Schließen"),
        ("m", "6", "Schaltfläche Datenbasen im Dateieintrag"),
        ("m", "7", "Neue Busaufzeichnungen automatisch dekodieren"),
        ("h", "Dateien wählen"),
        ("p", "\"Datenbasen hinzufügen...\" öffnet den Datei-Browser mit dem Filter \"Datenbasen (dbc, arxml, a2l, cdd)\". "
              "Mehrere Dateien lassen sich anhaken, auch aus verschiedenen Ordnern nacheinander. Sie werden nach der "
              "Endung einsortiert; doppelte werden übergangen, andere Endungen gemeldet. \"Entfernen\" je Zeile oder "
              "\"Alle entfernen\" ändert die Auswahl."),
        ("h", "Bei Bedarf anwenden"),
        ("p", "\"Anwenden\" verwendet alle gewählten Dateien. Was nicht zur Aufzeichnung passt, stört nicht: Eine DBC "
              "oder ARXML ohne passende CAN-ID bzw. eine A2L ohne passende Messgröße wird in der Erkennungsinfo als "
              "\"Nicht benötigt\" gemeldet. So kann eine feste Sammlung von Datenbasen für viele Aufzeichnungen "
              "dienen. Kennen zwei Dateien dieselbe Botschaft, gilt die zuerst genannte (DBC vor ARXML)."),
        ("p", "Mit \"Neue Busaufzeichnungen automatisch ... dekodieren\" werden neu geöffnete MF4/MDF/BLF-Dateien gleich "
              "mit den zuletzt angewendeten Datenbasen dekodiert, ohne dass der Dialog erscheint. Fehlt eine der "
              "Dateien oder schlägt die Dekodierung fehl, öffnet sich der Dialog mit der Meldung."),
        ("h", "DBC"),
        ("p", "Je DBC legt die Auswahl fest, für welchen CAN-Kanal sie gilt: alle Kanäle oder CAN 1 bis CAN 8. "
              "\"Anwenden\" dekodiert die Botschaften; die Signale erscheinen in der Liste der Datei. Gleichnamige "
              "Signale erhalten den Zusatz (DBC G...). Passt keine Botschaft, erscheint ein Hinweis: CAN-IDs und "
              "Kanal prüfen."),
        ("h", "ARXML (AUTOSAR)"),
        ("p", "Eine ARXML-Datei (AUTOSAR-Systembeschreibung) wird wie eine DBC verwendet, ebenfalls mit Kanalauswahl. "
              "MessGraph liest sie ohne Zusatzpakete: CAN-Frame-Triggerings (ID, Standard/Extended), Frames mit ihren "
              "PDUs, I-Signal-Zuordnungen (Startbit, Länge, Byteordnung), Umrechnung aus COMPU-METHOD (Faktor, "
              "Offset), Einheit sowie Vorzeichen und Gleitkomma aus dem Basistyp. Gemultiplexte und Container-PDUs "
              "werden übersprungen und gemeldet. Bei MF4/MDF wird die ARXML dafür intern in eine DBC umgesetzt."),
        ("h", "A2L"),
        ("p", "Kanäle, deren Name einer MEASUREMENT einer A2L entspricht, erhalten die Einheit, wenn die Aufzeichnung "
              "keine hat. Bei mehreren A2L gilt für einen Namen die erste Datei. Zusätze wie \\XCP:1 im Kanalnamen werden "
              "beim Vergleich ignoriert. \"Rohwerte ... umrechnen\" wendet zusätzlich die Umrechnung an (LINEAR, "
              "RAT_FUNC linear, TAB_INTP, TAB_NOINTP). Nur einschalten, wenn die Aufzeichnung Steuergeräte-Rohwerte "
              "enthält, sonst wird doppelt umgerechnet."),
        ("h", "CDD"),
        ("p", "CDD-Dateien werden zugeordnet und gemerkt. Die Auswertung von Diagnosedaten ist noch nicht eingebaut."),
        ("h", "Anwenden und ändern"),
        ("p", "Angezeigte Signale bleiben nach \"Anwenden\" in ihren Graphen, samt Farbe. Eine leere Zuordnung "
              "stellt die ursprünglichen Kanäle wieder her. \"Zuletzt verwendete übernehmen\" setzt die letzte "
              "Zuordnung ein. Die Zuordnung wird mit der Ansicht und in Definitionsdateien gespeichert; Ansichten "
              "älterer Versionen (eine A2L, eine CDD) werden weiter gelesen."),
        ("h", "MDF-Dateien"),
        ("p", "Dateien mit der Endung .mdf (ASAM MDF 3.x, gelegentlich auch MDF 4 unter alter Endung) werden wie MF4 "
              "gelesen, mit denselben Möglichkeiten: Kanäle beim Anhaken laden, Downsampling, Datenbasen, "
              "Datum/Uhrzeit-Achse. Die Erkennungsinfo nennt die MDF-Version."),
        ("h", "BLF-Dateien (Vector)"),
        ("p", "BLF (Binary Logging Format) ist das Aufzeichnungsformat von Vector-Werkzeugen wie CANoe und CANalyzer. "
              "Eine BLF enthält die CAN- und CAN-FD-Botschaften so, wie sie auf dem Bus lagen, aber keine "
              "physikalischen Werte. MessGraph liest BLF ohne Zusatzpakete:"),
        ("b", "Ohne DBC erscheint je Botschaft (ID und Bus) jedes Datenbyte als Signal, z. B. \"0x100 (CAN 1) "
              "Byte 0\" mit Werten 0 bis 255. Die Erkennungsinfo nennt Anzahl der Botschaften, IDs und Busse."),
        ("b", "Mit DBC oder ARXML (Schaltfläche \"Datenbasen...\" unter dem Dateinamen, auch mehrere kombiniert) werden die Signale dekodiert: Name, "
              "Einheit, Faktor/Offset, Intel- und Motorola-Byteordnung, Vorzeichen, Standard- und Extended-IDs, "
              "Multiplexing und CAN FD bis 64 Byte. Botschaften ohne DBC-Eintrag bleiben als Datenbytes sichtbar."),
        ("b", "Der Kanal je DBC (Alle, CAN 1, CAN 2 ...) begrenzt die Dekodierung auf einen Bus. Kommt dieselbe ID auf "
              "mehreren Bussen vor, trägt der Signalname den Bus, z. B. \"Drehzahl (CAN 2)\"."),
        ("b", "Die Zeitachse beginnt beim Messstart aus dem BLF-Kopf; die Datum/Uhrzeit-Achse funktioniert damit."),
        ("b", "A2L und CDD werden für BLF nicht ausgewertet. Die DBC/ARXML-Zuordnung wird mit der Ansicht und in "
              "Definitionsdateien gespeichert; berechnete Signale aus dekodierten Signalen sind möglich."),
        ("p", "Beispiel: demo_data/demo_can.blf mit demo_data/demo_can.dbc (Motor, Batterie, Fahrzeuggeschwindigkeit "
              "mit Extended-ID, Zellspannungen als CAN FD auf CAN 2). Für die Kombination mehrerer Datenbasen: "
              "demo_can_motor.dbc (Motor, Fahrzeug) zusammen mit demo_can_batterie.arxml (Batterie, Zellen)."),
    ]),
    ("Signale berechnen", [
        ("p", "Aus Signalen einer Datei lassen sich neue Signale berechnen, z. B. die Leistung aus Strom und Spannung. "
              "Das Ergebnis ist ein eigenes Signal mit Name, Einheit und Werten. Es steht in der Signalliste der Datei "
              "(mit = davor) und lässt sich wie jedes andere Signal verwenden: in Graphen ziehen, mit Markern "
              "vermessen, rechte Y-Achse, Grenzen und Prognose, Dateivergleich, Druck, Export und Report. Je Datei "
              "sind bis zu 10 berechnete Signale möglich."),
        ("img", "berechnen", "Bild 20: Signal berechnen"),
        ("m", "1", "Schaltfläche Berechnen... unter dem Dateinamen"),
        ("m", "2", "Berechnete Signale der Datei mit Formel: Bearbeiten, Löschen"),
        ("m", "3", "Name (frei wählbar) und Einheit (leer = automatisch)"),
        ("m", "4", "Formel"),
        ("m", "5", "Signal wählen und einfügen, Rechenzeichen + - * / und Klammern"),
        ("m", "6", "Berechnen und als neues Signal hinzufügen"),
        ("m", "7", "Das neue Signal in der Signalliste, hier im Graphen angezeigt"),
        ("m", "8", "Berechnungen als Definitionsdatei (*.def) speichern oder laden"),
        ("h", "Formel"),
        ("p", "Signale stehen in geschweiften Klammern, Zahlen direkt (Dezimalpunkt oder -komma). Erlaubt sind "
              "+ - * /, Klammern und Vorzeichen; Punkt- vor Strichrechnung gilt. Beispiele:"),
        ("b", "{Strom} * {Spannung}  (Leistung, Einheit A*V wird zu W)"),
        ("b", "{Strom} * {Spannung} / 1000  (in kW, Einheit von Hand: kW)"),
        ("b", "({U1} + {U2} + {U3}) / 3  (Mittelwert dreier Signale)"),
        ("b", "{Leistung} * 0.25  (berechnete Signale lassen sich weiterverwenden)"),
        ("h", "Fourier-Analyse"),
        ("p", "Unter Art \"Fourier-Analyse\" zerlegt der Dialog ein Signal in seine Harmonischen. Das Ergebnis bekommt "
              "einen frei wählbaren Namen und steht wie jedes berechnete Signal in der Signalliste. Typischer Aufbau: "
              "Grundsignal in Graph 1, Harmonische in Graph 2 - die Marker in Graph 1 wählen die Schwingung(en), deren "
              "Harmonische Graph 2 als senkrechte Balken zeigt."),
        ("img", "fourier", "Bild 20b: Fourier-Analyse - Marker wählen die Schwingung, Balken zeigen die Harmonischen"),
        ("m", "1", "Name des Ergebnisses (frei wählbar)"),
        ("m", "2", "Art: Formel oder Fourier-Analyse"),
        ("m", "3", "Grundsignal und Fenster"),
        ("m", "4", "Harmonische (X = Nummer) oder Frequenzbereich (X = Hz), Anzeige Anteil [%] oder Dämpfung [dB]"),
        ("m", "5", "Frequenzbereich von ... bis ... Hz (bis leer = halbe Abtastrate)"),
        ("m", "6", "Harmonische von ... bis ... (1 bis 15) und Grundfrequenz f0 (auto oder fest in Hz)"),
        ("m", "7", "Berechnen und hinzufügen"),
        ("m", "8", "Graph 1: Grundsignal, die Marker M1/M2 umschließen eine Schwingung"),
        ("m", "9", "Graph 2: Harmonische dieser Schwingung als Balken (H1 = Grundschwingung)"),
        ("b", "Nummerierung: Harmonische 1 ist die Grundschwingung f0, Harmonische n liegt bei n * f0. Beispiel 50 Hz: "
              "H1 = 50 Hz, H3 = 150 Hz, H5 = 250 Hz. f0 = auto nimmt die stärkste Frequenz (ohne Gleichanteil)."),
        ("b", "Anzeige wahlweise: Anteil [%] = Amplitude der Harmonischen in Prozent der Summe aller Harmonischen "
              "(Summe 100 %): reiner Sinus (0 % Oberwellen) H1 = 100 %, alle anderen 0; mit Oberwellen ist H1 < 100 % und "
              "der Rest verteilt sich entsprechend der Fourier-Analyse. Dämpfung [dB] = 20 * log10(A1 / An) gegenüber "
              "der Grundschwingung: H1 = 0 dB, 20 dB = ein Zehntel, 40 dB = ein Hundertstel; fehlende Harmonische 100 dB. "
              "Die Amplitude der Grundschwingung (A1) und den THD zeigt die Tabelle."),
        ("b", "Auswahl mit den Markern: Sind die Marker an und steht das Grundsignal in einem Graphen, zeigen die Balken "
              "die Schwingungen (Perioden), deren Mitte zwischen M1 und M2 liegt. Beispiel: Marker bei 0,01 und 1,49 "
              "Schwingungen -> 1. Schwingung; Marker verschieben auf 1,01 bis 2,49 -> 2. Schwingung usw. Mehrere "
              "Schwingungen zwischen den Markern werden zusammen ausgewertet. Ohne Marker: alle Schwingungen. Die Balken "
              "folgen den Markern sofort; Tooltip und Tabellenfenster nennen die gewählten Perioden."),
        ("b", "Marker gelten nur für das Grundsignal: Im Graphen mit dem Fourier-Ergebnis gibt es keine Marker, sie werden "
              "auch mit \"Marker synchron\" nicht dorthin übertragen, und \"X-Achsen koppeln\" lässt diesen Graphen aus "
              "(seine X-Achse ist Frequenz bzw. Nummer der Harmonischen). Verschieben der Marker oder Zoomen des "
              "Grundsignals bewertet die Fourier-Analyse sofort neu; ohne Marker gelten die Schwingungen im sichtbaren "
              "Bereich des Grundsignals (ganz herausgezoomt: alle)."),
        ("b", "Frequenzbereich, Darstellung wahlweise: \"Balken an den Harmonischen\" (Balken bei allen n * f0 zwischen fmin "
              "und fmax, höchstens 50) oder \"Spektrum (durchgehend)\" (Linie über alle Frequenzlinien, auch Rauschen "
              "und Anteile zwischen den Harmonischen). X = Frequenz [Hz]. Anzeige zusätzlich \"Amplitude\" "
              "(Spitzenwert in der Einheit des Signals); beim Spektrum beziehen sich % und dB auf die Amplitude der "
              "Grundschwingung. Auch das Spektrum folgt den Markern: bei einer Schwingung zwischen den Markern ist die "
              "Auflösung f0 (nur die Harmonischen), bei vielen Schwingungen entsprechend feiner."),
        ("b", "Gespeichert wird die Analyse als Formel, z. B. FFT({U_L1}; h=1..15; f0=auto; y=pct) oder "
              "FFT({U_L1}; f=0..500; f0=auto; y=db) - so geht sie mit Ansicht, Projekt und *.def mit und lässt sich über "
              "Bearbeiten ändern. Ältere Formeln mit h=0.. werden als h=1.. gelesen."),
        ("b", "Darstellung dezimal oder logarithmisch: Rechtsklick in den Graphen > Achsen: X logarithmisch, Y "
              "logarithmisch (je Graph, in Ansicht/Projekt gespeichert, gilt auch für Druck und Export). Logarithmische Achsen zeigen Hilfslinien bei 1 bis 9 je Dekade (auch in Druck, PDF und SVG)."),
        ("h", "Periodizität und Tabelle je Periode"),
        ("b", "Vor der Analyse prüft MessGraph, ob das Signal periodisch ist - auch wenn sich Frequenz oder Amplitude von "
              "Schwingung zu Schwingung ändern: Die Grundschwingung (Bandpass um f0) teilt das Signal an ihren steigenden "
              "Durchgängen durch den Mittelwert in Perioden. Periodisch heißt: mindestens 1 ganze Periode, Streuung der Periodendauer "
              "höchstens 25 % und ähnliche Kurvenform. Dann wird nur über ganze Perioden analysiert (kein Leckeffekt), "
              "zusätzlich jede Periode einzeln. Nicht periodisch: Analyse über das ganze Signal, der Grund wird genannt."),
        ("b", "Nulldurchgänge sind nicht nötig: Ein alternierendes Signal mit Gleichanteil (z. B. Drehzahl 1500 +- 600 "
              "rpm in demo_lauf_*.csv) wird um seinen Mittelwert geteilt. f0 wird per Sinus-Ausgleich mit Offset und "
              "Trend bestimmt und ist so auch bei nur 1 bis 2 Schwingungen in der Messung genau; ein linearer Trend "
              "wird entfernt, ohne die Schwingung zu verfälschen. Mindestens eine ganze Schwingung muss enthalten sein. "
              "Beginnt die Messung genau auf dem Mittelwert, zählt die erste Schwingung mit."),
        ("b", "Tooltip am Ergebnis (Signalliste, Liste im Rechendialog) als Tabelle: Anzahl Perioden, aktuelle Auswahl, "
              "Zeile \"Alle\" (alle ganzen Perioden), \"Mittel\"/\"Min\"/\"Max\" über die Perioden und jede Periode "
              "(bis 30). Spalten: Start [s], Dauer [ms], f [Hz], DC, A1 (Amplitude der Grundschwingung), H1..Hn (Anteile), "
              "THD [%]."),
        ("b", "Vollständige Tabelle: Doppelklick auf das Ergebnis in der Signalliste (oder \"Tabelle...\" im "
              "Rechendialog) öffnet ein eigenes Fenster mit allen Angaben und der ganzen Periodentabelle (scrollbar, "
              "Kopfzeile und Spalte Periode bleiben stehen); \"Tabelle kopieren\" legt alles tabulatorgetrennt in die "
              "Zwischenablage."),
        ("h", "Demodaten zur Fourier-Analyse"),
        ("b", "demo_fourier_netz_oberschwingungen.csv: 50 Hz, Spannung U_L1 und Gleichrichterstrom I_L1 mit den "
              "Harmonischen 3, 5, 7, 9 ..."),
        ("b", "demo_fourier_rechteck_saegezahn.csv: 20 Hz Rechteck (nur ungerade Harmonische), Sägezahn (alle), Dreieck."),
        ("b", "demo_fourier_frequenzrampe.csv: Hochlauf 40 -> 60 Hz - periodisch, Periodendauer ändert sich je Schwingung."),
        ("b", "demo_fourier_amplitude_wechselnd.csv: 50 Hz mit Laststufen, 3. Harmonische erst ab 0,5 s - mit den "
              "Markern Schwingungen vor und nach 0,5 s vergleichen."),
        ("b", "demo_fourier_nicht_periodisch.csv: Rauschen, Sprünge, Drift - die Prüfung meldet \"nicht periodisch\"."),
        ("b", "demo_fourier_ungleichmaessig.csv: Vibration 120 Hz mit Zeitstempel-Jitter und Lücken (wie MF4/CAN)."),
        ("b", "demo_fourier.def: fertige Fourier-Berechnungen zu den ersten drei Dateien (Definition laden...)."),
        ("h", "Definitionsdatei (*.def)"),
        ("p", "Damit Berechnungen nach einem Neustart nicht neu eingegeben werden müssen, lassen sie sich in einer "
              "Definitionsdatei hinterlegen: Graph-Optionen > Berechnungen speichern (*.def)... oder im Rechendialog "
              "\"Definition speichern...\". Gespeichert werden alle berechneten Signale aller geöffneten Dateien:"),
        ("b", "die Messdatei mit Pfad (absolut und relativ zur .def), in der die Basissignale liegen, bei MF4 samt "
              "zugeordneter DBC/A2L,"),
        ("b", "je Signal Name, Einheit, Formel und Bemerkung,"),
        ("b", "dazu Titel, Ersteller, Bemerkung und Datum der Definition."),
        ("p", "Laden über Graph-Optionen > Berechnungen laden (*.def)... oder \"Definition laden...\": Der Datei-Browser "
              "zeigt *.def-Dateien, mehrere lassen sich gleichzeitig wählen. Noch nicht geöffnete Messdateien "
              "werden samt zugeordneter DBC/A2L geöffnet, dann werden die Signale berechnet. Ist eine Messdatei "
              "verschoben, wird sie relativ zur .def gesucht. Sind Dateien geöffnet, die alle verwendeten Signale "
              "enthalten (z. B. ein anderer Lauf gleicher Struktur), fragt ein Dialog, wohin die Formeln sollen: in "
              "die gespeicherte Datei, in die geöffneten Dateien oder in beide. Berechnete Signale gleichen Namens werden "
              "ersetzt, Messsignale nie. Die .def ist eine lesbare Textdatei (JSON) und lässt sich auch von Hand "
              "anpassen. Beispiel: demo_data/demo_berechnung.def."),
        ("h", "Gut zu wissen"),
        ("b", "Haben die Signale verschiedene Zeitachsen (häufig bei MF4), werden alle linear auf die Zeitachse des "
              "ersten Signals der Formel interpoliert; außerhalb seines Bereichs entstehen Lücken. Die Meldung nennt "
              "die interpolierten Signale."),
        ("b", "Division durch 0 ergibt eine Lücke statt eines unendlichen Werts."),
        ("b", "Bearbeiten ändert Name, Einheit oder Formel; Graphen mit dem Signal zeigen sofort die neuen Werte. "
              "Beim Umbenennen werden Verweise in anderen Formeln mitgeändert. Ein Signal, das noch in einer anderen "
              "Formel steht, lässt sich erst löschen, wenn diese geändert oder gelöscht ist."),
        ("b", "Die Formeln werden mit der Ansicht gespeichert und beim Laden neu berechnet, auch nach dem Neuladen "
              "mit geänderter Downsampling-Einstellung."),
    ]),
    ("Dateien vergleichen", [
        ("p", "Mehrere Messungen mit gleichem oder ähnlichem Aufbau, etwa mehrere Prüfläufe, lassen sich Signal für "
              "Signal als Tabelle vergleichen: je Signal eine Zeile pro Kennwert, je Datei eine Spalte. Öffnen: "
              "Schaltfläche \"Dateien vergleichen...\" in der Werkzeugleiste oder Menü Datei. Sind beim Laden Dateien "
              "mit ähnlichem Aufbau dabei, weist die Statuszeile darauf hin."),
        ("img", "vergleich", "Bild 21: Drei Prüfläufe im Vergleich"),
        ("m", "1", "Dateien mit Anteil gleicher Signalnamen (Kopfzeile)"),
        ("m", "2", "Ähnliche wählen, Alle, Keine"),
        ("m", "3", "Kennwerte avg, min, max einzeln wählbar"),
        ("m", "4", "Signalsuche, Alle/Keine für die gefilterte Liste, nur gemeinsame Signale"),
        ("m", "5", "Signale zum Vergleich anhaken"),
        ("m", "6", "Berechnen, kopieren, als CSV speichern"),
        ("m", "7", "Ergebnis: Zeilen Signal [Einheit] und Kennwert, Spalten Dateien"),
        ("m", "8", "Fenster öffnen"),
        ("m", "9", "Toleranz in % je Signal"),
        ("m", "10", "Rote Zeile: Abweichung über der Toleranz, abweichender Wert rot"),
        ("h", "Ähnlichkeit"),
        ("p", "Verglichen wird über die Signalnamen. Der Prozentwert hinter jeder Datei nennt den Anteil gleicher "
              "Namen gegenüber den übrigen gewählten Dateien. Ab 50 % gelten Dateien als ähnlich. \"Ähnliche wählen\" "
              "wählt die größte Gruppe ähnlicher Dateien und schlägt bis zu 20 gemeinsame Signale vor. Jede Datei "
              "lässt sich trotzdem frei an- und abwählen."),
        ("h", "Signale und Kennwerte"),
        ("b", "Signale, die nicht in allen gewählten Dateien vorkommen, zeigen \"(in 2 von 3 Dateien)\". In der "
              "Tabelle steht dann \"-\" für die fehlende Datei."),
        ("b", "avg ist der Mittelwert aller gültigen Werte, min und max der kleinste und größte Wert, jeweils über die "
              "ganze Aufzeichnung. Lücken (leere Zellen, NaN) zählen nicht."),
        ("b", "MF4-Kanäle werden dafür in voller Auflösung gelesen, auch wenn sie noch nicht angezeigt sind. Bei CSV "
              "und Parquet dienen die geladenen Daten. Wurde eine Parquet-Datei beim Einlesen reduziert, steht ein * "
              "am Wert (mit Min/Max-Downsampling bleiben min und max trotzdem exakt)."),
        ("b", "Die Berechnung läuft im Hintergrund mit Fortschrittsanzeige und lässt sich abbrechen."),
        ("h", "Toleranz in %"),
        ("p", "Die Spalte % neben dem Signalnamen nimmt je Signal eine Toleranz auf, z. B. 4 oder 2,5. Weicht ein "
              "Dateiwert um mehr als diese Prozent ab, wird die Zeile dieses Kennwerts rot hinterlegt, der "
              "abweichende Wert und der Signalname werden rot geschrieben. Die Statuszeile zählt die betroffenen Zeilen."),
        ("b", "Bezug ist der Median aller Dateiwerte des Kennwerts. So fällt ein einzelner Ausreißer auf, ohne die "
              "übrigen Dateien mitzuziehen. Bei genau zwei Dateien ist der Bezug der jeweils andere Wert."),
        ("b", "Ist der Bezug 0, gilt jeder Wert ungleich 0 als Abweichung."),
        ("b", "Leeres Feld: keine Prüfung. Die Toleranzen bleiben je Signalname für den nächsten Start gespeichert "
              "und stehen in CSV und Zwischenablage mit der Spalte \"Abweichung\" (abweichende Dateien). Die Einheit "
              "steht in der Tabelle hinter dem Signalnamen, im Export als eigene Spalte."),
        ("h", "Weitergeben"),
        ("p", "\"In Zwischenablage kopieren\" legt die Tabelle tabulatorgetrennt ab, zum direkten Einfügen in Excel. "
              "\"CSV speichern\" schreibt sie mit Semikolon. Bei deutscher Oberfläche wird das Dezimalkomma verwendet, "
              "sonst der Punkt. Die gewählten Kennwerte bleiben für den nächsten Start gespeichert."),
    ]),
    ("Drucken, Export und Report", [
        ("p", "Im Kontextmenü eines Graphen (Rechtsklick) stehen unter \"Drucken und Export\" drei Funktionen. Gedruckt "
              "und exportiert wird der sichtbare Ausschnitt so, wie er auf dem Bildschirm steht: Zoom, Marker, "
              "Grenzlinien, eigene Farben, rechte Y-Achse und die Lage der Legende. Ausgeblendete Signale fehlen. "
              "Die Ausgabe ist Vektorgrafik in den Farben der hellen Darstellung."),
        ("img", "drucken", "Bild 22: Alle Graphen drucken oder exportieren, Legende oben rechts"),
        ("m", "1", "Ausgabe: Drucker, PDF-Datei oder SVG-Vektorgrafik"),
        ("m", "2", "Ausrichtung: Automatisch, Hochformat oder Querformat"),
        ("m", "3", "Papier: DIN A0 bis A6"),
        ("m", "4", "Zieldatei (nicht beim Drucker)"),
        ("m", "5", "Ausführen"),
        ("m", "6", "Legende, hier oben rechts (Lage per Rechtsklick wählbar)"),
        ("h", "Diesen Graphen drucken / exportieren"),
        ("p", "Der Graph, auf dem der Rechtsklick lag, füllt eine Seite des gewählten Formats."),
        ("h", "Alle Graphen drucken / exportieren"),
        ("p", "Alle Graphen mit Signalen werden auf die gewählte DIN-Seite verteilt: mit Matrix in deren Spalten, sonst "
              "untereinander. Jeder Graph bleibt mindestens etwa 5 cm hoch (mit größerem Papier entsprechend mehr); "
              "passen nicht alle auf eine Seite, folgen weitere Seiten. \"Automatisch\" wählt Querformat für ein oder "
              "zwei Zeilen von Graphen, sonst Hochformat. Schrift und Linien wachsen mit dem Papierformat."),
        ("b", "Drucker: Das PDF geht an den Standarddrucker (Windows: über das PDF-Programm, Linux/macOS: lp oder lpr). "
              "Gelingt das nicht, nennt die Meldung, wo das PDF liegt."),
        ("b", "PDF-Datei: eine Datei mit Seitenzahlen."),
        ("b", "SVG-Vektorgrafik: eine Datei je Seite (name.svg, bei mehreren Seiten name_1.svg, name_2.svg ...), "
              "zum Weiterbearbeiten z. B. in Inkscape oder Office."),
        ("h", "Report als PDF erstellen"),
        ("p", "Der Report fasst alle Graphen in einem Dokument zusammen: Deckblatt mit Titel, Ersteller, Datum und "
              "Dateien, Inhaltsverzeichnis, Kapitel Übersicht (Bemerkung, Messdateien, Einstellungen, Liste der "
              "Graphen) und je Graph ein Kapitel mit der Grafik und Tabellen:"),
        ("b", "Y-Achsen der Report-Grafiken (PDF und HTML): Das Maximum liegt mindestens 10 % über dem größten, das "
              "Minimum mindestens 10 % unter dem kleinsten Wert aller dargestellten Signale (je Achse, im sichtbaren "
              "X-Bereich; Grenzlinien zählen mit). Beispiel 396 bis 400 V: Achse 356,4 bis 440 V. Ist ein Extremwert 0, "
              "gelten 10 % der Spannweite. Druck und Export der Graphen behalten den Ausschnitt aus dem Programm."),
        ("b", "Signalspiegel direkt unter der Grafik: Farbe und Bezeichnung jeder Kurve, je nach Länge der Namen in "
              "bis zu drei Spalten, bei sehr vielen Kurven auf der nächsten Seite fortgesetzt. Die Grafik selbst "
              "enthält im Report keine Legende, damit sie auch bei vielen Kurven lesbar bleibt."),
        ("b", "Signale: Datei, Einheit und die im Dialog gewählten Werte Minimum, Maximum, Mittelwert und Drift "
              "(Regression) über alle Daten. Vorgabe: alle vier; die Wahl wird gemerkt. Ist kein Wert gewählt, "
              "enthält der Report keine Signaltabellen."),
        ("b", "Marker-Messung (wenn Marker aktiv): X1, X2, Wert 1, Wert 2, Delta X, Delta Y, Drift."),
        ("b", "Grenzen und Prognose (wenn Y min oder Y max gesetzt), mit Zielzeit und Zielzeit-Status; Signale mit "
              "verletzter Zielzeit sind rot hinterlegt, ihr Graph schwach rot."),
        ("p", "Im Dialog werden Titel, Ersteller, eine allgemeine Bemerkung und je Graph eine eigene Bemerkung "
              "eingetragen. Die allgemeine Bemerkung steht im Kapitel Übersicht, die Bemerkung eines Graphen in "
              "seinem Kapitel unter Grafik und Signalspiegel. Beide gehören zur Ansicht und werden mit ihr gespeichert; "
              "Ersteller, Papier und Ausgabe bleiben in den Einstellungen."),
        ("h", "Dynamischer Report (HTML)"),
        ("p", "Neben dem festen PDF gibt es einen dynamischen Report als HTML-Datei. Im Report-Dialog wählt "
              "\"Report\" zwischen \"PDF und dynamisch (HTML)\" (Vorgabe), \"PDF (fest)\" und \"Dynamisch (HTML)\"; "
              "beide Dateien erhalten denselben Namen mit .pdf bzw. .html. Die HTML-Datei öffnet sich in jedem "
              "Browser, braucht kein Internet und lässt sich weitergeben."),
        ("p", "Sie enthält denselben Inhalt wie das PDF: Angaben zum Bericht, Inhaltsverzeichnis am Rand, "
              "Übersicht und je Graph Grafik, Signalspiegel, Bemerkung und Tabellen. Zusätzlich lässt sich ein "
              "Signal hervorheben:"),
        ("b", "Klick auf eine Kurve im Graphen, einen Eintrag im Signalspiegel oder eine Zeile der Wertetabellen: "
              "Dieses Signal behält seine Farbe (Kurve etwas kräftiger, Zeile und Eintrag markiert), alle anderen "
              "Kurven, Einträge und Zeilen des Kapitels werden hellgrau."),
        ("b", "Strg-Klick (oder Umschalt-Klick) nimmt weitere Signale dazu oder wieder heraus."),
        ("b", "Erneuter Klick auf das gewählte Signal, \"Alle zeigen\" oder Esc hebt die Hervorhebung auf."),
        ("p", "Jedes Kapitel wird für sich hervorgehoben. Gedruckt wird die HTML-Datei so, wie sie gerade aussieht."),
        ("h", "Lage der Legende"),
        ("p", "Ein Rechtsklick auf die Legende eines Graphen öffnet die Wahl der Position: oben links, oben Mitte, "
              "oben rechts, unten links, unten Mitte oder unten rechts. Dieselbe Wahl steht auch im Kontextmenü des "
              "Graphen. Die Lage bleibt beim Neuaufbau der Graphen, wird mit der Ansicht gespeichert und im Druck, "
              "Export und Report übernommen. Ein Klick auf einen Legendeneintrag blendet das Signal am Bildschirm aus "
              "und wieder ein."),
    ]),
    ("Downsampling", [
        ("p", "Sehr lange Messungen aus MF4 und Parquet können mehrere Millionen Werte je Signal haben. Downsampling "
              "reduziert sie schon beim Einlesen, spart Speicher und macht das Arbeiten flüssiger. Einstellung: "
              "Datei > Downsampling... Die Wahl bleibt für den nächsten Start gespeichert und gehört zur Ansicht. "
              "CSV-Dateien werden nicht reduziert."),
        ("h", "Modus"),
        ("b", "Aus: volle Auflösung, jeder Wert bleibt erhalten."),
        ("b", "Automatisch (Vorgabe): nur Signale mit mehr Werten als die Schwelle (Vorgabe 2.000.000) werden auf etwa "
              "die Zielanzahl (Vorgabe 500.000) reduziert, immer mit Min/Max je Block. Kürzere Signale bleiben "
              "unverändert."),
        ("b", "Manuell: Methode und Faktor bzw. Zeitraster selbst wählen; gilt für jedes Signal."),
        ("h", "Methoden"),
        ("b", "Min/Max je Block: je Block aus n Werten bleiben Minimum und Maximum an ihrer echten Zeit. Spitzen und "
              "Ausreißer bleiben sichtbar und messbar. Empfohlen für die meisten Messungen."),
        ("b", "Mittelwert je Block: je Block ein Mittelwert. Glättet Rauschen wie ein Tiefpass, kurze Spitzen werden "
              "abgeschwächt."),
        ("b", "Jeder n-te Wert: am schnellsten, kann aber kurze Ereignisse verlieren. Gut für langsame, glatte Signale."),
        ("b", "Festes Zeitraster: Mittelwert je Zeitintervall (z. B. 0,01 s). Ergibt ein gleichmäßiges Raster, "
              "praktisch zum Vergleichen von Signalen mit unterschiedlicher Abtastrate. Intervalle ohne Werte bleiben "
              "Lücken."),
        ("h", "Übernehmen"),
        ("p", "\"Übernehmen\" gilt für danach geöffnete Dateien. \"Übernehmen und geladene Dateien neu laden\" lädt "
              "geöffnete MF4- und Parquet-Dateien neu; Graphen, Namen, Farben und Marker bleiben. Beim Hinzufügen "
              "eines reduzierten Signals nennt die Statuszeile die Anzahl vorher und nachher, die Erkennungsinfo der "
              "Datei die gewählte Einstellung."),
        ("h", "Gut zu wissen"),
        ("b", "Die Messwerte der Marker (Wert 1, Wert 2, Delta, Drift) stammen aus den reduzierten Daten. Für exakte "
              "Werte einzelner Abtastpunkte Downsampling ausschalten und neu laden."),
        ("b", "Unabhängig davon reduziert MessGraph beim Zeichnen immer nur den sichtbaren Ausschnitt; beim Zoomen "
              "erscheinen alle vorhandenen Werte."),
    ]),
    ("Fensterbereiche anpassen", [
        ("p", "Zwischen den Bereichen liegen schmale Trenner (Bild 1, Nummer 5, und Bild 10, Nummer 5). Sie färben "
              "sich beim Überfahren mit der Maus."),
        ("b", "Senkrechter Trenner rechts neben der Dateiliste: nach links oder rechts ziehen ändert die Breite der "
              "Dateiliste und damit die der Graphen."),
        ("b", "Waagerechter Trenner über der Wertanzeige (sichtbar mit Markern): nach oben ziehen vergrößert "
              "die Wertanzeige, nach unten die Graphen."),
        ("p", "Mindestgrößen verhindern, dass ein Bereich verschwindet. Die Größen bleiben für den nächsten Start "
              "gespeichert und gehören auch zur gespeicherten Ansicht."),
    ]),
    ("Projekte und Ansichten", [
        ("p", "Anordnung von Signalen und Graphen, Berechnungen, Datenbasen und alle weiteren Einstellungen lassen "
              "sich als Projekt (Endung .mgproj) speichern und später wieder verwenden."),
        ("img", "ansicht", "Bild 23: Projekt speichern"),
        ("m", "1", "Menü Datei mit den Projektbefehlen"),
        ("m", "2", "Zuletzt verwendete Projekte"),
        ("m", "3", "Projektname und Bemerkung"),
        ("m", "4", "Projektdatei (.mgproj)"),
        ("m", "5", "Speichern"),
        ("h", "Was ein Projekt enthält"),
        ("b", "Messdateien mit Pfad (absolut und relativ zur Projektdatei), je Datei die Datenbasen (DBC, ARXML, "
              "A2L, CDD mit Kanalzuordnung und Umrechnungsoption) und eine festgelegte ASCII-Struktur,"),
        ("b", "berechnete Signale mit Formel, Einheit und Bemerkung,"),
        ("b", "Matrix und Graphen: Titel, Signale, Farben, rechte Achse, Grenzen, Lage der Legende, Bemerkungen, "
              "Positionen der Marker,"),
        ("b", "Optionen: X-Achsen koppeln, Marker, synchron, Datumsachse, Farbschema, Schriftgröße, Größe der "
              "Fensterbereiche, Downsampling, allgemeine Report-Bemerkung,"),
        ("b", "Einstellungen der Dialoge: Report und Export (Papier, Werte der Signaltabelle, PDF/HTML, Titel, Autor), "
              "Dateien vergleichen (Werte, Toleranz), Definitionsdateien, zuletzt verwendete Datenbasen und "
              "automatisches Dekodieren, ASCII-Vorlage,"),
        ("b", "Suchtext und Zielgraph sowie Projektname, Bemerkung und Erstellungsdatum."),
        ("p", "Persönliche Einstellungen wie Sprache oder zuletzt benutzter Ordner gehören nicht zum Projekt."),
        ("h", "Projekt speichern"),
        ("p", "Datei > \"Projekt speichern unter...\" fragt nach Projektname, Bemerkung und Projektdatei und zeigt, "
              "was gespeichert wird. Datei > \"Projekt speichern\" schreibt ohne Rückfrage in das geöffnete Projekt "
              "(beim ersten Mal wie \"speichern unter\"). Der Projektname steht in der Titelleiste."),
        ("h", "Projekt öffnen"),
        ("p", "Datei > \"Projekt öffnen...\" oder \"Zuletzt verwendete Projekte\" ersetzt den aktuellen Stand: "
              "Dateien werden geladen, Datenbasen angewendet, Signale berechnet und die Graphen wiederhergestellt. "
              "Eine Projektdatei kann auch beim Start übergeben werden: main.py Pruefstand3.mgproj."),
        ("p", "Wird der Projektordner samt Messdaten und Datenbasen verschoben oder weitergegeben, findet MessGraph "
              "die Dateien wieder: zuerst am gespeicherten Ort, dann relativ zur Projektdatei, dann mit gleichem "
              "Namen neben der Projektdatei. Was fehlt, nennt die Statuszeile."),
        ("p", "\"Projekt schließen\" schließt alle Dateien und beginnt leer."),
        ("h", "Einstellungen auf andere Dateien übertragen"),
        ("p", "Projekt öffnen und Ansicht laden öffnen immer die gespeicherten Dateien. Kommt eine neue Messung gleicher "
              "Struktur hinzu (nächster Lauf, anderer Prüfling), überträgt Datei > \"Einstellungen auf andere "
              "Dateien übertragen...\" die Auswertung auf diese Datei:"),
        ("b", "Quelle: \"Aktueller Stand\", eine gespeicherte Ansicht (.mgraph) oder ein Projekt (.mgproj)."),
        ("b", "Zuordnung: Für jede gespeicherte Datei mit Graphen, Berechnungen, Datenbasen oder ASCII-Struktur wird "
              "die Zieldatei gewählt: eine geöffnete Datei oder \"Andere Datei wählen...\". Vorgeschlagen wird die "
              "geöffnete Datei mit den meisten gleichen Signalnamen. Die Spalte \"Signale im Ziel\" zeigt, wie "
              "viele der angezeigten Signale die Zieldatei hat (berechnete Signale zählen mit)."),
        ("b", "Übertragen werden Graphen mit Titel, Signalen, Farben, rechter Achse, Grenzen, Legende, Bemerkung und "
              "Markern, Matrix, Optionen, berechnete Signale, Datenbasen (DBC, ARXML, A2L, CDD) und die "
              "ASCII-Struktur. Signale werden über den Namen zugeordnet; fehlende nennt die Statuszeile."),
        ("b", "\"Bisherige Dateien zusätzlich geöffnet lassen\" behält die Quelldateien geöffnet (ohne Graphen), "
              "etwa für einen Vergleich. Bei einem Projekt als Quelle lassen sich dessen Einstellungen (Report, "
              "Export, Vergleich, Downsampling ...) mit übernehmen."),
        ("b", "Mehrere gespeicherte Dateien können auf dieselbe Zieldatei gelegt werden; ihre Einstellungen werden "
              "zusammengeführt."),
        ("p", "Das Ergebnis ist eine neue Auswertung: \"Projekt speichern\" fragt nach einem neuen Namen, das "
              "Quellprojekt bleibt unverändert. Nur die Formeln überträgt weiterhin \"Berechnungen laden (*.def)\"."),
        ("h", "Ansicht speichern und laden"),
        ("p", "Eine Ansicht (Endung .mgraph) ist die schlanke Form: Dateien, Datenbasen, Berechnungen, Graphen und "
              "Optionen, ohne Projektname und ohne die Einstellungen der Dialoge. Ansichten älterer Versionen "
              "bleiben lesbar."),
        ("h", "Speichern"),
        ("p", "Datei > Ansicht speichern... fragt nach dem Dateinamen. Vorgeschlagen wird der zuletzt benutzte."),
        ("h", "Laden"),
        ("p", "Datei > Ansicht laden... wählt eine .mgraph-Datei im Datei-Browser. Die aktuelle Ansicht wird "
              "ersetzt, die Dateien werden neu geladen. Fehlt eine Datei am gespeicherten Ort, sucht MessGraph sie "
              "relativ zur Ansichtsdatei; so lassen sich Ordner mit Ansicht und Messdaten weitergeben. Fehlende "
              "Dateien oder Signale nennt die Statuszeile."),
        ("h", "Letzte Ansicht beim Start"),
        ("p", "Mit Datei > \"Letzte Ansicht beim Start wiederherstellen\" sichert MessGraph den Stand beim Beenden "
              "und stellt ihn beim nächsten Start wieder her (nicht, wenn Dateien beim Start übergeben werden)."),
    ]),
    ("Hilfe, PDF und Screenshots", [
        ("h", "Sprache"),
        ("p", "Oberfläche und Hilfe gibt es auf Deutsch, Englisch, Thai und Chinesisch (Mandarin, Kurzzeichen). Umgeschaltet wird rechts in der "
              "Menüleiste über \"Sprache\". Alle Beschriftungen, Meldungen und die Hilfe wechseln sofort; geladene "
              "Dateien, Graphen, Farben und Einstellungen bleiben erhalten. Die Wahl gilt auch für das PDF und "
              "bleibt für den nächsten Start gespeichert."),
        ("p", "Die Erkennungsangaben einer Datei (Erkennung, Maus hierher) und die Hinweise in der Dateiliste "
              "folgen der gewählten Sprache, auch für Dateien, die in einer anderen Sprache geöffnet wurden. Thai stellt nur die Bedienungstexte und die Hilfe um; Datei- und Signalnamen, Einheiten und Werte bleiben, wie sie sind. "
              "Dafür braucht der Rechner eine Schrift mit thailändischen UND lateinischen Zeichen, "
              "zum Beispiel Leelawadee UI oder Tahoma (Windows) oder fonts-tlwg, etwa Loma (Linux). Reine Thai-Schriften "
              "wie Noto Sans Thai werden nicht verwendet, weil darin die lateinischen Buchstaben fehlen; fehlt eine "
              "passende Schrift, ist Thai nicht wählbar. Im PDF wird die Schrift eingebettet. Die mitgelieferten Abbildungen zeigen die deutsche "
              "Oberfläche; \"Screenshots erzeugen\" nimmt sie in der eingestellten Sprache auf."),
        ("p", "Chinesisch braucht entsprechend eine Schrift mit chinesischen UND lateinischen Zeichen, zum Beispiel "
              "Microsoft YaHei (bei Windows vorhanden), DengXian oder SimHei, unter Linux fonts-wqy-microhei, "
              "fonts-wqy-zenhei oder Noto Sans CJK, unter macOS PingFang. Auch hier bleiben Datei- und Signalnamen, "
              "Einheiten und Werte unverändert; fehlt die Schrift, ist Chinesisch nicht wählbar."),
        ("img", "hilfe", "Bild 24: Hilfe-Fenster"),
        ("m", "1", "Sprachumschaltung am rechten Rand der Menüleiste"),
        ("m", "2", "Hilfe als PDF speichern"),
        ("m", "3", "Screenshots erzeugen"),
        ("m", "4", "Inhaltsverzeichnis"),
        ("m", "5", "Bild mit nummerierten Markierungen, Erklärung darunter"),
        ("m", "6", "Menü Hilfe: Hilfe anzeigen öffnet dieses Fenster"),
        ("p", "Die Hilfe ist ein eigenes Fenster über dem Hauptfenster: Hilfe > Hilfe anzeigen öffnet es, das Kreuz in "
              "der Titelzeile schließt es. Es lässt sich verschieben und in der Größe ändern; Graphen und Wertanzeige "
              "bleiben dahinter bedienbar."),
        ("h", "Hilfe als PDF"),
        ("p", "\"Als PDF speichern...\" im Hilfe-Fenster oder Hilfe > Hilfe als PDF speichern... erzeugt ein "
              "Handbuch im A4-Format mit schmalen Rändern, Inhaltsverzeichnis, Seitenzahlen und Screenshots in der "
              "gewählten Sprache."),
        ("h", "Screenshots"),
        ("p", "Die Hilfe enthält zehn Bilder mit nummerierten Markierungen; unter jedem Bild erklärt eine Liste die "
              "Nummern. Mitgeliefert werden nachgezeichnete Abbildungen des Programmfensters (Bildunterschrift mit "
              "dem Zusatz \"nachgezeichnet\")."),
        ("p", "\"Screenshots erzeugen\" ersetzt sie durch echte Aufnahmen Ihres Fensters: Das Programm baut mit den "
              "Beispieldaten nacheinander die gezeigten Situationen auf, setzt dieselben Markierungen und fotografiert "
              "das Fenster. Das dauert einige Sekunden; währenddessen bitte nichts bedienen. Danach kehrt die "
              "vorherige Ansicht zurück. Die Aufnahmen liegen im Ordner .messgraph_hilfe_bilder im "
              "Benutzerverzeichnis und haben Vorrang vor den mitgelieferten Bildern. Für das Bild Datenbasen wird "
              "demo_data/demo.mf4 benötigt; geöffnete Menüs (Bild 23) lassen sich nicht automatisch aufnehmen."),
    ]),
    ("Fehlerbehebung", [
        ("h", "Häufige Meldungen"),
        ("b", "\"Für MF4 wird asammdf benötigt\", \"Für Parquet wird pyarrow benötigt\", \"Für die DBC-Dekodierung "
              "wird canmatrix benötigt\": pip install -r requirements.txt ausführen."),
        ("b", "\"Kein Datenblock mit Zahlenwerten gefunden\": Die CSV-Datei enthält keine erkennbaren Zahlen."),
        ("b", "Falsche Spalten oder falsche X-Achse: \"Erkennung\" im Dateieintrag zeigt, was erkannt wurde."),
        ("b", "X-Achse in Sekunden bis in die Millionen: Die Datei umfasst mehrere Tage; die Datum/Uhrzeit-Achse "
              "ist dann übersichtlicher."),
        ("h", "Fehlerprotokoll"),
        ("p", "Jeder Lade- oder Bedienfehler steht mit vollständiger Ursache in messgraph_fehler.log im "
              "Benutzerverzeichnis. Die Statuszeile nennt den Pfad. Diese Datei hilft bei der Fehlersuche."),
        ("h", "Einstellungen zurücksetzen"),
        ("p", "Darstellung, Ordner, Fenstergrößen und Sprache stehen in .messgraph.json im Benutzerverzeichnis. "
              "Wird die Datei gelöscht, gelten wieder die Standardwerte."),
    ]),
]
