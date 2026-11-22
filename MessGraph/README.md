# MessGraph

Messdaten aus **mf4, mdf, blf, csv, ASCII (asc, txt, dat ...) und parquet** öffnen, Datenspalten automatisch finden, in einer
n*m-Matrix von Graphen anzeigen und mit zwei senkrechten Markern vermessen. Oberfläche: Dear PyGui.

## Start

- Windows: `start_windows.bat`
- Linux: `sh start_linux.sh`
- Manuell: `pip install -r requirements.txt`, dann `python main.py [Dateien]`

Benötigt Python 3.10 oder neuer – außer bei der portablen Version.

## Ohne installiertes Python (portable Version, Python 3.12.0)

Eine `.venv` allein reicht dafür nicht: sie verweist immer auf ein installiertes Python. Deshalb wird
**Python 3.12.0** samt allen Paketen in den Ordner `runtime/python` gelegt. Die Startdateien verwenden es
automatisch, wenn es vorhanden ist (sonst wie bisher `.venv` bzw. das installierte Python).

Einmalig auf einem Rechner **mit Internet** bauen (dort ist kein Python nötig):

| System | Aufruf | Ergebnis |
|---|---|---|
| Windows 10/11, 64 Bit | `tools\build_portable_windows.bat` | `dist\MessGraph_portable_windows.zip` |
| Linux x86_64 oder aarch64 | `sh tools/build_portable_linux.sh` | `dist/MessGraph_portable_linux_<arch>.tar.gz` |

Ablauf der Bauskripte:

1. Python 3.12.0 herunterladen: python-build-standalone, Release 20231002, von GitHub. Die offizielle
   SHA-256-Prüfsumme wird kontrolliert. Unter Windows dient das „embeddable package“ von python.org als
   Ausweichquelle (`-Source python.org`).
2. Prüfen, dass wirklich Python 3.12.0 läuft.
3. Alle Pakete aus `requirements.txt` in dieses Python installieren (dafür ist PyPI nötig).
4. Probelauf: Pakete und MessGraph importieren.
5. Paket packen (ZIP bzw. tar.gz). Unter Windows mit .NET-ZipFile und neuen Versuchen, falls Virenscanner oder
   Windows-Suche eine frisch kopierte Datei kurz geöffnet halten. Ist `runtime\python` schon fertig, packt
   `tools\build_portable_windows.bat -PackOnly` nur noch, ohne erneuten Download.

Auf dem Zielrechner entpacken und `start_windows.bat` bzw. `sh start_linux.sh` starten. Ein Paket gilt nur für
das Betriebssystem und die Prozessorart, für die es gebaut wurde. Unter Linux wird OpenGL vorausgesetzt (auf
Desktop-Systemen vorhanden). Ist die portable Version unvollständig, meldet `main.py` das mit dem nötigen Aufruf.

Die Bedienung beschreibt die Rubrik **Hilfe** im Programm.

## Struktur

| Datei | Aufgabe |
|---|---|
| `main.py` | Programmstart |
| `messgraph/gui.py` | Oberfläche, Graphen, Marker |
| `messgraph/csv_reader.py` | CSV- und ASCII-Strukturerkennung, Kopfzeile automatisch oder vom Nutzer, <{Continue}> |
| `messgraph/tabular.py` | Zeitachse und Datenspalten bestimmen |
| `messgraph/browser.py` | Verzeichnisinhalt für den Datei-Browser |
| `messgraph/timeparse.py` | Zeitformate, Startzeit, Datumsanzeige |
| `messgraph/blf.py`, `messgraph/dbc.py` | Vector BLF lesen, DBC lesen und CAN/CAN FD dekodieren (ohne Zusatzpakete) |
| `messgraph/arxml.py` | AUTOSAR-ARXML lesen (CAN-Frames, PDUs, I-Signale, Umrechnung) und als DBC ausgeben |
| `messgraph/databases.py` | Mehrere DBC/ARXML/A2L/CDD je Aufzeichnung (MF4, MDF, BLF), bei Bedarf angewendet |
| `messgraph/loaders.py` | Dateityp-Auswahl, Parquet, MF4/MDF |
| `messgraph/arrange.py` | Anordnung vorschlagen: Signale nach Größe und System gruppieren, Matrix mit Zeilen |
| `messgraph/layout.py` | Matrix und Signalzuordnung |
| `messgraph/measure.py` | Messrechnung, Datenreduktion beim Zeichnen |
| `messgraph/downsample.py` | Downsampling beim Einlesen (MF4, Parquet) |
| `messgraph/formula.py` | Berechnete Signale: Formeln mit + - * / und Klammern (eigener Parser, kein eval) |
| `messgraph/definitions.py` | Definitionsdateien *.def: Messdatei mit Pfad, Formeln, Titel, Bemerkungen |
| `messgraph/compare.py` | Dateivergleich als Tabelle (avg, min, max) |
| `messgraph/plotexport.py` | Graphen als Vektorgrafik: PDF, SVG, Druck, Seitenaufteilung DIN A0 bis A6 |
| `messgraph/report_html.py` | Dynamischer Report als eigenständige HTML-Datei (Hervorhebung per Klick) |
| `messgraph/report.py` | Report als PDF (Deckblatt, Inhaltsverzeichnis, je Graph Grafik und Tabellen) |
| `messgraph/progress.py` | Fortschritt und Abbruch beim Laden (MF4, Parquet, Ansicht) |
| `messgraph/themes.py` | Light/Dark |
| `messgraph/i18n.py` | Sprachumschaltung der Oberfläche (Deutsch, Englisch, Thai, Chinesisch) |
| `messgraph/safewrite.py` | Ergebnisdateien sicher schreiben: Sperren, Analyse belegter Dateien, Wiederholung |
| `messgraph/i18n_zh.py` | Chinesische Übersetzungen (deutscher Text -> Chinesisch; fehlt einer: Englisch) |
| `messgraph/help_content.py` | Hilfe: Sprachauswahl (help_de.py, help_en.py, help_th.py, help_zh.py) |
| `messgraph/help_images/` | mitgelieferte, nachgezeichnete Abbildungen mit Markierungen |
| `messgraph/fonts.py`, `ttf.py` | Thai-Schrift finden, TrueType/OpenType für das PDF lesen |
| `messgraph/help_pdf.py`, `pdfdoc.py`, `pdf_metrics.py` | Hilfe als PDF (ohne Zusatzpakete) |
| `messgraph/project.py` | Projektdateien (*.mgproj): Ansicht plus Dialog-Einstellungen, relative Pfade auch für Datenbasen |
| `messgraph/session.py` | Ansicht speichern und laden (.mgraph) |
| `tools/make_demo_data.py` | Beispieldaten erzeugen |

## Tests

`python -m pytest tests`

`tests/fake_dearpygui.py` bildet die genutzte Dear-PyGui-Schnittstelle nach, damit die
Programmlogik ohne Bildschirm läuft. Das ersetzt keinen Test mit dem echten Paket.

## Prüfstand

Die Versionen 1.0.0 bis 1.75.1 wurden ohne die Pakete `dearpygui`, `asammdf` und `pyarrow` entwickelt.
Mit echten Daten geprüft sind die CSV-Erkennung und die Messrechnung. Die Oberfläche sowie die
Parquet- und MF4-Leser liefen nur gegen Nachbildungen und sind beim ersten echten Start zu prüfen.

## Downsampling

Datei > Downsampling... wirkt beim Einlesen von MF4 und Parquet (CSV bleibt unverändert):
Aus, Automatisch (Vorgabe: ab 2.000.000 Werten je Signal auf etwa 500.000, Min/Max je Block) oder Manuell
mit Min/Max, Mittelwert, jedem n-ten Wert oder festem Zeitraster. Die Einstellung wird gespeichert und gehört
zur Ansicht. Die Reduktion beim Zeichnen (nur der sichtbare Ausschnitt) ist davon unabhängig.

## BLF (Vector)

BLF-Dateien enthalten CAN-/CAN-FD-Botschaften. Ohne DBC erscheinen die Datenbytes je Botschaft, mit DBC
("Datenbasen...") die dekodierten Signale. Beispiel: `demo_data/demo_can.blf` mit `demo_data/demo_can.dbc`.
Geprüft gegen selbst erzeugte BLF-Dateien nach der Formatbeschreibung; echte CANoe-Aufzeichnungen bitte gegenprüfen.

## Signale berechnen

Je Datei "Berechnen...": neues Signal aus Signalen der Datei, z. B. `{Strom} * {Spannung}` (bis zu 10 je Datei).
Das Ergebnis steht mit Name, Einheit und Werten in der Signalliste und wird mit der Ansicht gespeichert.
Graph-Optionen > Berechnungen speichern/laden (*.def) hinterlegt die Formeln samt Messdatei, Titel und Bemerkungen
unabhängig von der Ansicht (Beispiel: `demo_data/demo_berechnung.def`).

## Dateien vergleichen

"Dateien vergleichen..." (Werkzeugleiste oder Menü Datei) stellt gleich oder ähnlich aufgebaute Dateien
(ab 50 % gleiche Signalnamen) als Tabelle gegenüber: Zeilen = Signal und Kennwert (avg, min, max, wählbar),
Spalten = Dateien. Je Signal eine Toleranz in %: Zeilen mit Abweichung über der Toleranz (Bezug: Median der
Dateiwerte) werden rot. Kopieren für Excel oder Speichern als CSV. Beispiel: `demo_data/demo_lauf_1..3.csv`.

## Drucken, Export, Report

Rechtsklick auf einen Graphen > Drucken und Export: diesen Graphen oder alle Graphen an den Drucker, als PDF oder
SVG (Vektorgrafik, DIN A0 bis A6, automatisch Hoch-/Querformat) sowie ein Report als PDF mit Deckblatt und
Inhaltsverzeichnis. Die Lage der Legende (oben/unten, links/Mitte/rechts) wählt ein Rechtsklick auf die Legende.

## Schriftgröße

Der Schieberegler "Schrift" rechts neben Hell/Dunkel stellt die Schriftgröße der Graphen (Titel, Achsen, Legende)
und der Wertanzeige ein (10 bis 32 px, gespeichert in Einstellungen und Ansicht).

## Marker und Zoom

Nach Zoom oder Unzoom stehen aktive Marker neu bei 10 % (M1) und 90 % (M2) des Sichtbereichs; beim Verschieben
nur, wenn ein Marker aus dem Bild fällt.

## Grenzen und Prognose

Mit Markern hat die Wertanzeige je Signal die Eingaben Y min und Y max (Grenzlinien im Graphen). Die Spalte
Drift (Regression) zeigt die Steigung m der Regressionsgeraden über alle Daten des Signals (kleinste Quadrate).
Die Prognose setzt am letzten Messpunkt x1 = 0 mit b = letzter Wert an und berechnet x2 = (y2 - b) / m mit
y2 = Y max (steigend) bzw. Y min (fallend); mit Datumsachse als Zieldatum, sonst in X-Einheiten.

## Fortschritt

Beim Laden von MF4 und Parquet (auch beim Laden einer Ansicht und beim DBC-Dekodieren) zeigt eine Leiste über der
Statuszeile Prozent, Schritt und Dauer; "Abbrechen" beendet die Ladevorgänge. Parquet wird dazu blockweise
gelesen (`ParquetFile.iter_batches`).

## Hilfe-Bilder

Mitgeliefert: 13 nachgezeichnete Abbildungen mit nummerierten Markierungen in `messgraph/help_images`
(erzeugt mit `python tools/make_help_illustrations.py`, benötigt Playwright mit Chromium).
Echte Aufnahmen erzeugt das Programm selbst: Rubrik Hilfe > "Screenshots erzeugen". Sie werden mit denselben
Markierungen in `~/.messgraph_hilfe_bilder` gespeichert und haben Vorrang.

## Sprache

Rechts in der Menüleiste: "Sprache" schaltet Oberfläche, Meldungen und Hilfe zwischen Deutsch, Englisch und
Thai um. Neue Texte in `messgraph/i18n.py` eintragen (deutscher Text, Englisch, Thai) und in `messgraph/i18n_zh.py` (Chinesisch).

## Thai

Oberfläche, Hilfe und PDF auf Thai brauchen eine Schrift mit Thai- UND lateinischen Zeichen (Windows: Leelawadee
UI, Tahoma; Linux: fonts-tlwg, z. B. Loma, oder FreeSerif). Reine Thai-Schriften wie Noto Sans Thai werden
übergangen, weil darin die lateinischen Buchstaben fehlen. Das PDF bettet die Schrift ein.

## Mehrere Datenbasen, ARXML und MDF (ab 1.21.0)

Eine Aufzeichnung kann eine Kombination aus DBC, ARXML (AUTOSAR), A2L und CDD brauchen. Im Dialog
"Datenbasen..." wählt "Datenbasen hinzufügen..." beliebig viele Dateien aller Arten auf einmal; sie werden nach
der Endung einsortiert. Angewendet wird bei Bedarf: Dateien ohne passende Botschaft bzw. Messgröße werden als
"Nicht benötigt" gemeldet. Optional werden neue Busaufzeichnungen automatisch mit den zuletzt verwendeten
Datenbasen dekodiert. ARXML liest MessGraph selbst (BLF direkt, für MF4/MDF intern als DBC an asammdf).
Dateien mit der Endung `.mdf` (MDF 3.x) werden wie MF4 gelesen. Beispiel: `demo_data/demo_can.blf` mit
`demo_can_motor.dbc` und `demo_can_batterie.arxml`.

## Ein Signal über alle Dateien (ab 1.22.0)

Findet die Signalsuche ein Signal in mindestens zwei geladenen Dateien, erscheint unter dem Suchfeld die
Leiste "Treffer in mehreren Dateien". Dort wird das Signal gewählt und aus allen Dateien geplottet:
"Gemeinsamer Graph" (gewählter Zielgraph oder ein neuer, Legende nennt die Datei) oder "Einzelgraphen"
(je Datei ein Graph). "Entfernen" nimmt das Signal aller Dateien wieder aus den Graphen.

## Report: Signalspiegel unter dem Graphen (ab 1.23.0)

Im PDF-Report enthält die Grafik keine Legende mehr. Darunter steht der Signalspiegel (Farbe und Bezeichnung
jeder Kurve, bis zu drei Spalten, bei sehr vielen Kurven auf der nächsten Seite fortgesetzt). So bleibt der
Report auch bei vielen Kurven je Graph sauber formatiert.

## Report: Werte der Signaltabelle wählbar (ab 1.24.0)

Im Report-Dialog wird festgelegt, welche Werte die Signaltabellen enthalten: Minimum, Maximum, Mittelwert,
Drift (Vorgabe: alle; die Wahl wird gemerkt). Ist keiner gewählt, enthält der Report keine Signaltabellen.

## Dynamischer Report (ab 1.25.0)

Der Report entsteht wahlweise als festes PDF, als dynamische HTML-Datei oder beides (Vorgabe). Die HTML-Datei
läuft in jedem Browser ohne Internet. Ein Klick auf eine Kurve, einen Eintrag im Signalspiegel oder eine
Tabellenzeile hebt das Signal hervor, alle anderen Kurven, Einträge und Zeilen des Kapitels werden hellgrau.
Strg-Klick wählt mehrere Signale, erneuter Klick, "Alle zeigen" oder Esc hebt die Wahl auf.

## ASCII-Dateien mit variablem Vorspann (ab 1.26.0)

Neben CSV werden beliebige ASCII-Rohdaten geöffnet (asc, txt, dat, tsv, log, prn). Die Datei wird eingelesen,
die Signal-Kopfzeile automatisch erkannt oder im Dialog "ASCII-Import..." als Zeilennummer festgelegt (dazu
Einheitenzeile, Trenn- und Dezimalzeichen); danach werden die Daten wie üblich behandelt. Zusatzinformationen
wie `<{Continue}>` werden ignoriert: Beginnt eine Zeile damit, setzt sie die vorige fort, so dass eine
umgebrochene Kopfzeile logisch zu den Datenspalten passt. Nicht erkannte Dateien öffnen den Dialog von selbst;
festgelegte Angaben werden mit der Ansicht gespeichert und lassen sich als Vorlage für weitere Dateien merken.
Beispiel: `demo_data/demo_pruefstand.asc`.

## Projekte (ab 1.27.0)

Datei > "Projekt speichern", "Projekt speichern unter...", "Projekt öffnen...", "Zuletzt verwendete Projekte"
und "Projekt schließen". Ein Projekt (*.mgproj) hält alles für die Wiederverwendung: Messdateien mit Pfad,
Datenbasen (DBC, ARXML, A2L, CDD) je Datei, ASCII-Struktur, berechnete Signale, Matrix und Graphen mit Signalen,
Farben, Achsen, Grenzen, Legenden und Bemerkungen, Optionen sowie die Einstellungen für Report, Export, Vergleich,
Downsampling, Definitionen, zuletzt verwendete Datenbasen und ASCII-Vorlage, dazu Projektname und Bemerkung.
Pfade werden auch relativ zur Projektdatei gespeichert; ein verschobener Projektordner wird wiedergefunden.
Beim Start: `python main.py Pruefstand3.mgproj`.

## Einstellungen auf andere Dateien übertragen (ab 1.28.0)

"Ansicht laden" und "Projekt öffnen" öffnen immer die gespeicherten Dateien. Für eine neue Messung gleicher
Struktur überträgt Datei > "Einstellungen auf andere Dateien übertragen..." die Auswertung: Quelle ist der
aktuelle Stand, eine Ansicht oder ein Projekt; je gespeicherter Datei wird die Zieldatei gewählt (Vorschlag:
geöffnete Datei mit den meisten gleichen Signalnamen). Übertragen werden Graphen mit Signalen, Farben, Achsen,
Grenzen, Legenden und Bemerkungen, Matrix, Optionen, berechnete Signale, Datenbasen und ASCII-Struktur;
Signale werden über den Namen zugeordnet, fehlende gemeldet.

## Zeilen der Matrix zusammenfassen (ab 1.29.0)

In einer Matrix lassen sich die Graphbereiche einzelner Zeilen frei zusammenfassen, direkt im Matrixfeld
(`4*3: 3, 3, 2+1, 1`) oder im Dialog "Zeilen..." mit Vorschau. Je Zeile steht eine Zahl für die Anzahl gleich
breiter Graphen (3 = drei Graphen, 1 = ein Graph über die ganze Breite) oder es werden die Breiten in Spalten mit
"+" angegeben (2+1 = ein Graph über zwei Spalten und einer über eine). Die X-Kopplung wirkt auch über die Zeilen;
die Aufteilung wird mit Ansicht und Projekt gespeichert und beim Drucken aller Graphen übernommen.

## Report: Y-Achsen mit 10 % Abstand (ab 1.30.0)

In beiden Reports (PDF und HTML) liegt das Maximum der Y-Achse mindestens 10 % über dem größten und das Minimum
mindestens 10 % unter dem kleinsten Wert aller dargestellten Signale (je Achse, im sichtbaren X-Bereich,
Grenzlinien eingeschlossen). Ist ein Extremwert 0, gelten 10 % der Spannweite.

Ab 1.34.0 gilt derselbe Rand auch für die Plots in der Oberfläche (Aufbau, Doppelklick, "Alles anzeigen"):
Y max = größter Wert * 1,1, Y min = kleinster Wert * 0,9, bei negativen Werten 10 % des Betrags nach außen.
Danach ist die Achse wieder frei zum Zoomen.

## Anordnung vorschlagen (ab 1.32.0)

"Vorschlag..." in der Werkzeugleiste analysiert die Signale (angezeigte, Treffer der Suche oder alle einer
Datei) nach Namen und Einheit und schlägt Graphen und Matrix vor: gleiche Größe desselben Systems in einem
Graphen (z. B. AC Spannung, AC Strom, AC Leistung; Sollwerte bei den Istwerten), je System eine Zeile (kleine
Systeme teilen sich eine), Temperaturen und Zustände in eigenen Zeilen am Ende. Zu volle Graphen und Zeilen werden
geteilt, kürzere Zeilen über zusammengefasste Bereiche gefüllt. Vorschau vor dem Übernehmen.

## Menü Graph-Optionen, Art der Drift-Regression (ab 1.47.0)

Neues Menü "Graph-Optionen" neben "Datei": Grenzwerte (Konfiguration laden, Konfigurator, entfernen) und
Berechnungen (*.def laden/speichern) sind aus "Datei" hierher umgezogen. Neu ist die Auswahl der Drift-Regression
(`measure.REG_METHODS`, `measure.regression(x, y, method)`):

- Lineare Regression (kleinste Quadrate der y-Abstände, Vorgabe, `ols`)
- Minimale Abstandsquadrate (orthogonal, Hauptachse/Total Least Squares, einheitenabhängig, `tls`)
- Robuste Regression (Theil-Sen, Median der Paarsteigungen, höchstens 1500 Punkte, `theilsen`)
- Lineare Regression über das letzte Viertel der Daten (aktueller Trend, `recent`)

Die Wahl gilt für Drift (Regression), Prognose, Zielzeit-Bewertung, Regressionslinien, Druck/Export und Report
(Einstellungen) und wird in den Einstellungen sowie als Option `regression_method` in Ansicht und Projekt gespeichert.
Dazu im Menü ein Schalter für die Regressionslinien.
Ab 1.47.1 sind die Arten im Menü nummeriert ((1) bis (4)); die Nummer steht im Spaltenkopf der Wertanzeige
("Drift (Regression 3)"), im Detailfenster und in der Signaltabelle des Reports und wechselt beim Umschalten sofort.

## Grenzwert-Konfigurator: Abstand berechnet Vorschläge neu (1.75.1)

- "Dieser Mode"/"Alle Modes" wirkten scheinbar nicht: sie füllten nur aktive Signale ganz ohne Grenzen - nach der
  Analyse haben aber alle aktiven Signale Grenzen. Jetzt werden vorhandene Grenzen aktiver Signale mit Daten neu
  berechnet (Datenbereich plus Abstand).
- Abstand ändern (`_le_margin_changed`) berechnet die sichtbaren aktiven Signale des bearbeiteten Modes sofort neu.
- Von Hand in der Tabelle eingetragene Grenzen (`le_manual`, je Sitzung) werden nicht überschrieben; die
  Statuszeile nennt ihre Anzahl.

## Zähler je Mode in Schritt 2, Schritte einzeln rücksetzbar (1.75.0)

- Der Zähler kommt nicht mehr aus den Daten bzw. einem globalen Schalter in Schritt 4, sondern je Mode aus
  Schritt 2: Zeit, Flanke oder Ignorieren (`goal_kind` time | edges | ignore an den Teilen/DUTs). Ignorieren = keine
  Bewertung (`AutoSettings.no_eval`: keine Zähler, keine Violation, Bilder/Statistik weiter); Häkchen aus = nicht
  verarbeiten. Modes und Zielzeiten... ist immer bedienbar; Änderungen gelten sofort (nächster Zyklus bewertet neu).
- Flanken je Mode: `ev["mode_edges"][Mode]`, Fenster über "Flanken..." in der Mode-Zeile. `_auto_job_settings`
  setzt edge_count/edges/edge_target/no_eval je Teil. Schritt 2 und Start prüfen Modes mit Flanke ohne Flanke.
- Ergebnisdateien: Zeit -> Time_counter.json (bzw. eigener Name), Flanke -> `_edge_json_name` daneben
  (Flanken_counter.json, HTOE_Flanken_counter.json, <Name>_Flanken.json).
- Entfernt: Zähler-Auswahl und "Flanken definieren..." in Schritt 4, eigene Modes (vorab festgelegte Modes, die
  beim Auftauchen übernommen wurden) samt Sonderfall aus 1.74.1. Neue DUT-Ordner übernehmen Zähler/Ziel ihres Modes.
- Jeder Schritt hat "Schritt zurücksetzen": setzt ihn und alle folgenden zurück (Schritt 1 = alle), stoppt einen
  laufenden Zyklus; Einstellungen und Ergebnisse bleiben.

## Eigene Modes ohne Daten reichen für Schritt 2-4 (1.74.1)

- Fehler "Schritt 2: mindestens einen Mode zum Verarbeiten anhaken", obwohl ein eigener Mode (wartet auf Daten)
  angehakt war: Schritt 2 zählte nur gefundene Modes. Jetzt zählen eigene Modes mit (`_auto_waiting_modes`).
- Schritt 3 ohne Grenzwert-Konfiguration abschließbar, wenn nur eigene Modes warten (Grenzen beim ersten Zyklus);
  Analysieren meldet das statt eines Fehlers. Start ohne aktive Teile erlaubt: jeder Zyklus sucht die Ordner neu.
- Zielart im Eingabefeld "Eigener Mode" springt nach Hinzufügen auf Zeit zurück.

## Violation gegen die Ziel-Flankenzahl (1.74.0)

- Flanken Counter mit Ziel (Flanke in Schritt 4 oder `edge_target` des Modes): `auto.edge_goals(counters)` liefert
  je Eintrag gezählt/Ziel/Messzeit (`duration_s`, Lücken > 5 * Median nicht gezählt).
- `assess(..., edge_goals)` -> `edge_violation`: Flanken bis Violation = gezählt + Rate * Zeit bis Violation
  (Trend). Weniger als Ziel = Violation (roter Hintergrund, "Violation vor Ziel-Flankenzahl!"); Grenze erreicht ->
  gezählt gegen Ziel; Trend ohne Grenze -> unendlich. Ohne Flankenziel keine Violation.
- `write_statistics` schreibt je Signal `edge_goals` und je Flanken-Eintrag `violation`, `edges_to_violation`
  (frühstes Signal), `violation_signal` in die Ergebnisdatei. Tabelle: "Erfüllung - Violation", Tooltip.

## Zielvorgabe je Mode: Zeit, Flankenzahl, Ignorieren (1.73.0)

- Schritt 2 (Modes und Zielzeiten), gefundene und eigene Modes: Zielart `goal_kind` = time | edges | ignore,
  dazu `target_time` bzw. `target_edges` (am Teil/DUT und am eigenen Mode gespeichert, beim Auftauchen eines Ordners
  übernommen; ältere Einstellungen ohne Zielart = time).
- Ignorieren = enabled aus (komplett ignoriert); Häkchen setzen stellt auf Zeit zurück.
- Flankenzahl: `AutoSettings.edge_target` je Auswertung; `evaluate_edges(..., default_target)` nimmt es für Flanken
  ohne eigenes Ziel. Hinweis in der Zeile/Meldung, solange Schritt 4 nicht Flanken Counter ist oder keine Flanke
  definiert ist. Keine Zielzeit -> keine Violation.
- Leer = unendlich: `_auto_goal` -> (None, None), der Mode bekommt beim Zyklus keine Zielzeit (auch nicht die der
  Konfiguration); `assess` meldet dann keine Violation, Textblock "Zielzeit: unendlich (keine Violation möglich)".
  Schritt 2 ist ohne Zielzeit abschließbar; Vorschläge aus Daten ohne Zielzeit statt 24h.

## Flanken Counter (1.72.0)

- Schritt 4, Zähler: Time Counter (bisher) oder Flanken Counter (`AutoSettings.edge_count`, Definitionen in
  `AutoSettings.edges`: signal, upper = Wert1, lower = Wert2, n, target; Fenster "Flanken definieren...").
- `auto.count_edges`: Flanke über Wert1 = übersteigen, mindestens n Werte darüber, danach mindestens n Werte darunter
  (Wert2 spiegelbildlich). Läufe kürzer als n zählen nicht und unterbrechen keinen Zustand; der Anfangszustand gilt
  ohne Mindestlänge, ein Start jenseits der Schwelle zählt nicht (kein Übersteigen). NaN (Lücken) wird übersprungen.
  Am Ende ausstehende Rückkehr -> `pending`.
- `auto.evaluate_edges` ersetzt im Flanken Counter `evaluate`: Schlüssel `edges_<Signal>_<Gruppe>` mit actual,
  edges_upper, edges_lower, upper, lower, n, pending, steps (Ziel), fulfillment_percent.
- Ergebnisdatei: Standardname Flanken_counter.json (folgt der Zählerart, eigene Namen bleiben). Tabelle: Spalten
  Signal und Flanken, Tooltip mit den Einzelzählern; "nur Modes mit Treffern" ist im Flanken Counter ausgeblendet.
- Testattrappe: `get_item_children(table, 1)` liefert wie Dear PyGui nur Zeilen, Slot 0 die Spalten.

## Fourier: Schwingungen ohne Nulldurchgang (1.71.4)

- Alternierende Signale mit Offset (z. B. Drehzahl 1500 +- 600 rpm in `demo_lauf_*.csv`, etwa 1,6 Schwingungen in
  60 s) sind zulässig. Perioden = steigende Durchgänge durch den Mittelwert der Grundschwingung.
- f0 (`fourier.estimate_f0`): Spitze im aufgefüllten Hann-Spektrum ohne Gleichanteil, dann Sinus-Ausgleich mit
  Offset und Trend (Raster + Goldener Schnitt), genau auch bei 1 bis 2 Schwingungen. Vorher: FFT-Linie mit
  Auflösung 1/T und Abbruch unter 2 Schwingungen.
- Trend (`remove_trend`) wird gemeinsam mit dem Sinus ausgeglichen; eine Gerade allein schluckte bei wenigen
  Schwingungen einen Teil der Schwingung.
- Mindestens 1 ganze Periode (vorher 2); weniger als eine Schwingung in der Messung -> Meldung.
- Rand (`_edges`): Liegt ein Durchgang genau am Anfang/Ende (Index 0 bzw. n), zählt die Periode mit. Ein 1-s-Signal
  mit 50 Hz ab Phase 0 hat damit 50 statt 49 ganze Perioden.

## Regressionslinie ohne eigenen Legendeneintrag (1.71.3)

- Kurve und Regressionslinie sind eine Serie: Daten = Kurve, NaN-Lücke, Striche der Geraden (`App._apply_series`,
  `SlotUI.curve`/`reg_points`). Dadurch ein einziger Eintrag im Signalspiegel; Aktivieren/Deaktivieren dort schaltet
  beide gemeinsam (unabhängig davon, wie Dear PyGui die Legende intern verwaltet). Detail-Nachladen beim Zoomen und
  das Anpassen der Striche setzen Kurve und Linie gemeinsam.
- Hintergrund: In 1.71.2 trug die Linie die Beschriftung des Signals; Dear PyGui hängt intern eine eindeutige
  Kennung an, deshalb entstanden doppelte Einträge.

## Regressionslinien der aktiven Signale (1.71.2, ersetzt 1.71.1)

- "Aktiv" = in der Legende eingeschaltet (Dear PyGui/ImPlot: Klick auf den Legendeneintrag schaltet ein Signal
  aus und ein). Jedes aktive Signal hat seine Regressionslinie; ein deaktiviertes nicht.
- Umsetzung: Die Regressionslinie trägt dieselbe Beschriftung wie ihr Signal, ImPlot führt beide unter einem
  Legendeneintrag und blendet sie gemeinsam aus. Zusätzlich gleicht `_poll_reg_visibility` die Sichtbarkeit mit
  `show` der Serie ab; Druck/Export (`_spec_regressions`) nehmen nur aktive Signale.
- Die Auswahl per Klick auf eine Kurve aus 1.71.1 entfällt.

## Gleichnamige Signale aller Dateien zugleich wählen (1.71.0)

- Neue Checkbox "Gleichnamige Signale aller Dateien" unter "Dateien öffnen / Alle abwählen" (nur bei mehr als einer
  offenen Datei sichtbar, Einstellung `settings["same_name"]`).
- An: Häkchen bei einem Signal wählt das gleichnamige Signal in allen offenen Dateien zugleich, zusammen in einem
  Graphen (gewählter Zielgraph, sonst ein neuer); Abwählen entfernt es aus allen Dateien. Aus: Einzelauswahl.

## Hilfslinien bei logarithmischen Achsen (1.70.4)

- Logarithmische X/Y-Achsen zeichnen Hilfslinien bei 1..9 * 10^k (`App._log_gridlines`: unendliche Linien
  `add_inf_line_series` in Gitterfarbe, ohne Legendeneintrag, über den Datenbereich bis zur nächsten vollen Dekade).
- Druck/PDF/SVG: zusätzlich zu den Dekaden feine Hilfslinien 2..9 (`plotexport.log_minor`).

## Fourier: Marker nur am Grundsignal, keine X-Kopplung, Zoom bewertet neu (1.70.3)

- Graphen, die nur Fourier-Ergebnisse zeigen (`SlotUI.fourier`), haben keine Marker (M1/M2/M3 ausgeblendet), werden
  bei "Marker synchron" nicht mitgeführt (`_peer`) und bei "X-Achsen koppeln" ausgelassen: native Kopplung der
  Subplots wird dann abgeschaltet, die übrigen Graphen koppelt `_poll_link` (`manual_link`).
- Neubewertung: Markerverschiebung (wie bisher) und Zoom/Verschieben des Grundsignals (`_poll_view` ->
  `_update_harmonics`). Ohne Marker zählen die Perioden im sichtbaren Bereich des Grundsignals (ganz heraus-
  gezoomt: alle).

## Fourier: wahlweise durchgehendes Spektrum oder Balken, Anzeige auch als Amplitude (1.70.2)

- Frequenzbereich mit Auswahl "Darstellung": Balken an den Harmonischen (Standard) oder Spektrum (durchgehend,
  `plot=line`, Linie über alle Frequenzlinien). Harmonische nach Nummer bleiben Balken.
- Anzeige zusätzlich `y=amp` (Amplitude in der Einheit des Signals). Beim Spektrum gelten % und dB bezogen auf A1.
- Auch das Spektrum folgt den Markern (`fourier.line_spectrum`: Abschnitt vom ersten bis zum letzten gewählten
  Periodenrand, exakt neu abgetastet; eine Schwingung -> Auflösung f0).

## Fourier: nur Balken an den Harmonischen, Anzeige % oder dB (1.70.1)

- Beide Varianten liefern einzelne senkrechte Balken an den Harmonischen (kein durchgehendes Spektrum mehr):
  Harmonische 1..15 (X = Nummer) bzw. Frequenzbereich (X = Hz, Balken bei allen n*f0 im Bereich, höchstens 50,
  Balkenbreite 0,6*f0). Beide folgen den Markern.
- Anzeige wählbar (`y=pct` / `y=db`): Anteil [%] = An / Summe der Amplituden * 100 (reiner Sinus H1 = 100 %), oder
  Dämpfung [dB] = 20*log10(A1/An) gegenüber H1 (H1 = 0 dB, fehlend 100 dB). Einheit des Ergebnisses % bzw. dB.
- Perioden genauer: steigende Nulldurchgänge per Sinus-Ausgleich über eine Periode am Rohsignal verfeinert, jede
  Periode exakt auf ganze Länge neu abgetastet (weniger Leckeffekt in den Balken einzelner Schwingungen).

## Fourier: Harmonische ab 1, Anteile, Auswahl der Schwingung mit den Markern (1.70.0)

- Nummerierung: Harmonische 1 = Grundschwingung f0, Harmonische n bei n*f0 (50 Hz: H3 = 150 Hz); Bereich 1..15.
  Ältere Formeln mit `h=0..` werden als `h=1..` gelesen.
- Balkenhöhe = Anteil an der Energie der Harmonischen 1..15 (Summe 1): reiner Sinus H1 = 1, mit Oberwellen H1 < 1.
  Einheit des Ergebnisses leer (Anteil); Amplitude der Grundschwingung (A1) und THD in der Tabelle.
- Marker-Auswahl (`fourier.select`, `App._update_harmonics`, aufgerufen mit `_update_measurements`): Steht das
  Grundsignal in einem Graphen mit Markern, zeigen die Balken die Perioden, deren Mitte zwischen M1 und M2 liegt
  (0,01..1,49 Schwingungen -> 1. Schwingung); ohne Marker alle. Energien je Periode werden einmal berechnet
  (`info["harm"]`: energy, bounds in X-Einheit des Signals), die Balken nur summiert und per `set_value` aktualisiert.
- Tooltip/Tabellenfenster mit aktueller Auswahl; Spalten Start, Dauer, f, DC, A1, H1..Hn (Anteile), THD.
- Demo-Definition und Hilfe (Bild 20b: Grundsignal mit Markern, Harmonische als Balken) angepasst.

## Fourier: Harmonische als Balken, Periodentabelle im eigenen Fenster (1.69.1)

- Harmonische (`FFT(...; h=...)`) setzen `channel.plot_style = "bar"`: im Graphen `add_bar_series` (Breite 0,6,
  Farbe über das Serien-Theme mit mvBarSeries), in Druck/PDF/SVG Balken (`SeriesSpec.bars`). Frequenzbereich bleibt Linie.
- Doppelklick auf ein Fourier-Ergebnis in der Signalliste (bzw. Knopf "Tabelle..." im Rechendialog) öffnet
  `fourier_window`: alle Angaben und die vollständige Periodentabelle (scrollY/scrollX, Kopfzeile und erste Spalte
  fixiert, bis 5000 Zeilen), "Tabelle kopieren" (tabulatorgetrennt in die Zwischenablage). Tooltip mit Hinweis.

## Fourier-Analyse: Periodizität, ganze Perioden, Tabelle je Periode, Demodaten (1.69.0)

- Periodizitätsprüfung (`fourier.detect_periods`): Grundschwingung per Bandpass 0,5..1,5*f0, steigende Nulldurchgänge
  = Periodengrenzen. Periodisch bei >= 2 ganzen Perioden, Streuung der Periodendauer <= 25 % und Kurvenform-
  Korrelation >= 0,7 (Frequenz-/Amplitudenwechsel je Periode erlaubt). Linearer Trend wird vorher entfernt.
- Periodisch: Analyse nur über ganze Perioden (erster bis letzter Nulldurchgang); Fenster "auto" (neuer Standard) =
  Rechteck, Harmonische exakt auf Linie count*(n+1). Nicht periodisch: ganzes Signal, Hann, Grund wird gemeldet.
- `info["table"]`: Spalten Periode, Start, Dauer, f, DC, H0..Hn, THD; Zeile "Alle" (über alle ganzen Perioden),
  "Mittel"/"Min"/"Max" über die Perioden, Zeilen je Periode. Anzeige als Tabellen-Tooltip am Ergebnis in der
  Signalliste und in der Liste des Rechendialogs (bis 30 Perioden), Kurzfassung in der Statuszeile.
- Demodaten (`tools/make_demo_fourier.py`): demo_fourier_netz_oberschwingungen.csv, _rechteck_saegezahn.csv,
  _frequenzrampe.csv, _amplitude_wechselnd.csv, _nicht_periodisch.csv, _ungleichmaessig.csv und demo_fourier.def.

## Signal berechnen: Fourier-Analyse, logarithmische Achsen (1.68.0)

- Rechendialog mit Auswahl "Art": Formel oder Fourier-Analyse (neues Modul `fourier.py`).
- Fourier-Analyse eines Signals (Fenster Hann mit Amplitudenkorrektur oder Rechteck; ungleichmäßige Abtastung wird auf
  ein gleichmäßiges Raster interpoliert, Lücken überbrückt; Zeiteinheit s/ms/us/min/h):
  - Frequenzbereich von ... bis ... Hz (bis leer = halbe Abtastrate): X = Frequenz [Hz], Y = Amplitude (Spitzenwert),
    0 Hz = Gleichanteil.
  - Harmonische 0 bis 15: Ordnung 0 = Eigenfrequenz f0, Ordnung n = n-te Harmonische bei (n+1)*f0; f0 = auto
    (stärkste Linie ohne Gleichanteil, parabolisch verfeinert) oder fest in Hz.
- Ergebnis frei benennbar, Einheit = Einheit des Signals; gespeichert als Formel `FFT({U}; f=0..500; win=hann)` bzw.
  `FFT({U}; h=0..15; f0=auto; win=hann)` - geht mit Ansicht, Projekt und *.def mit, Bearbeiten lädt die Felder.
- Darstellung dezimal oder logarithmisch je Graph: Kontextmenü (Rechtsklick) > Achsen: X logarithmisch, Y
  logarithmisch (`GraphSlot.log_x/log_y`, in Ansicht/Projekt gespeichert; Druck/PDF/SVG mit Dekaden-Teilung).

## Kein Bildordner "CSV" mehr, lesbare Ergebnistabelle (1.67.2)

Ursache Ordner "CSV": Bei "eine Auswertung je Quellordner" (z. B. Quelle ...\HTOE22kW\CSV mit Unterordnern je
Seriennummer) wurden alle Seriennummern zu einer Gruppe zusammengeworfen. Ohne DES..._DUTn im Dateinamen fiel der
Gruppenname auf den Namen des Quellordners zurück ("CSV"); Bilder landeten in Ziel\CSV, Schlüssel
count_<Mode>_CSV - nicht zuordenbar. Bei einer einzelnen Datei wurde der ganze Dateiname zum Gruppennamen.

- Engine: Unterordner mit Seriennummer (`SERIAL`: 1-4 Großbuchstaben + mindestens 12 Ziffern, z. B. DES...,
  DS...) bilden je eine eigene Gruppe (Schlüssel `("*", Seriennummer)`), Name = Seriennummer bzw. Seriennummer_DUTn.
- Gruppenname sonst: DES-Nummer + DUT bzw. eigenes Muster -> Seriennummer im Dateinamen -> gemeinsamer Grundname ->
  aussagekräftiger Ordnername (`meaningful_dir`, überspringt CSV, Files, Report, Data, ...).
- Ergebnistabelle Schritt 4: Spalten Auswertung, DUT/Teil, Mode, Gruppe (Schlüssel im Tooltip), Ist, Ziel
  (bei Zielzeit h:mm:ss, sonst Messpunkte mit Tausenderpunkt statt 3.5691e+06), Erfüllung in % (grün ab 100 %,
  sonst rot); sortiert, Zeilenhintergrund, füllt das Fenster bis zum Log. Time_counter.json bleibt unverändert.

## Report: nur die gewählte Auswertung, Name Report_{Mode}_{DateTime}.pdf (1.67.1)

Ursache der Meldung (Modes ohne Report, Anhang verweist auf ...\MessGraph\_TestResult):
- Die Report-Auswahl wurde über Teilenamen gespeichert und die Liste zeigte die Teile aller Auswertungen. Eine
  alte Auswertung mit Ziel ...\_TestResult hatte dieselben Namen (z. B. Drive_V2L_705V_DUT2), die neuen Teile hießen
  dann "... (2)". Gewählt blieben die alten Namen (ohne Ausgaben -> _err mit Verweis auf _TestResult), neue Modes
  wie AC_22kW_3ph_725V standen nicht in der gespeicherten Auswahl und waren abgewählt. Zusätzlich wurden gleiche
  Modes verschiedener Auswertungen in einen Report gemischt.

Änderungen:
- Report-Fenster: Auswahl "Auswertung" (Standard: die in Auto gewählte; "Alle Auswertungen" möglich). Die Liste
  zeigt nur deren Teile; gespeichert werden `evaluation` und die ausdrücklich abgewählten Zielordner
  (`deselected`). Neue Modes/DUTs der Auswertung sind automatisch gewählt, auch beim Report nach Zeitplan.
  Die alte Namensliste `jobs` wird nicht mehr verwendet.
- Teile werden über Auswertung + Zielordner erkannt (nicht über den Namen); Gruppierung je Auswertung und Mode.
- Hinweis bei DUTs ohne Ausgaben nennt den Grund (Mode in Schritt 2 nicht gewählt, Quellverzeichnis fehlt ...).
- Dateiname `Report_<Mode>_<JJJJMMTT_hhmmss>.pdf` (bei Fehlern `..._err.pdf`).
- Verzeichnisverwalter: Quell- und Basis-Zielordner werden beim Speichern der Regel als absoluter Pfad abgelegt
  (`.\Projekt_Daten\DV_HTOE22kW` hängt sonst vom Startordner des Programms ab).

## Grenzwert-Konfigurator: Grenzen aus Daten für alle Modes (1.67.0)

- Eigene Zeile "Grenzen aus Daten vorschlagen: [Dieser Mode] [Alle Modes] Abstand [10 %]". Der Prozent-Abstand
  (Anteil der Spannweite Min..Max) gilt für beide Varianten.
- "Dieser Mode": wie bisher, sichtbare aktive Signale ohne Grenzen im bearbeiteten Mode.
- "Alle Modes": alle Modes der Konfiguration, aktive Signale ohne Grenzen (Suchfeld gilt). Datenbereich je Mode aus
  der Auto-Analyse aller Dateien dieses Modes (`auto_mode_stats`, gefüllt bei Analysieren einer Auswertung bzw. aller
  Modes einer Verzeichnisregel), für Modes ohne Analyse aus allen geladenen Dateien. Vorhandene Grenzen und inaktive
  Signale bleiben; Modes ohne Daten nennt die Statuszeile.

## Report wird nie abgebrochen, unvollständig = Anhang + _err (1.66.0)

- `autoreport.build_report` bricht nicht mehr ab (kein Abbrechen-Knopf, `cancel` wird ignoriert). Fehler werden
  gesammelt und der Rest erzeugt: kaputte/fehlende Bilder (Platzhalter "(image missing)"), Einträge ohne Bild,
  unlesbare Kennwerte, Fehler eines Abschnitts (Deckblatt, Summary, Vergleich je Signal, Tabelle/Bilder je DUT),
  Auswertungen ohne Ausgaben (aus `collect`, je Mode an den Report übergeben), PDF-Erzeugung mit Bildern
  (dann ohne Bilder).
- Unvollständiger Report: roter Hinweis "INCOMPLETE REPORT" auf dem Deckblatt, Anhang "Appendix: Incomplete Report"
  mit allen Gründen (englisch) und Dateiname `..._err.pdf`.
- Ist der Zielname nicht schreibbar, wird mit Grund im Anhang unter einem Ausweichnamen geschrieben
  (`Report_..._<hhmmss>_err.pdf`, sonst im Benutzerordner).
- Ein Mode ganz ohne Ausgaben bekommt ebenfalls einen Report (Deckblatt + Anhang, `_err`). Mehrere Reports laufen
  unabhängig; die Statuszeile nennt unvollständige Reports.

## Schritt 4: Ergebnisdatei im Zielverzeichnis, eigener Name (1.65.4)

- Ergebnisdatei (alle) = Zielverzeichnis\Time_counter.json. Zielverzeichnis ist der Basis-Zielordner der
  Verzeichnisregel (vorher landete die Datei im erweiterten Ordner des ersten Teils, z. B. ...\Precon\DUT1);
  Auswertungen ohne Regel nutzen ihren Zielordner. Alle Modes/DUTs mit demselben Zielverzeichnis schreiben in eine Datei.
- Im Feld steht nur der Dateiname (Standard Time_counter.json, z. B. HTOE_time_counter.json; .json wird ergänzt,
  ungültige Zeichen \ / : * ? " < > | mit Hinweis abgewiesen). "Standard" setzt zurück, darunter der volle Pfad.
  Ein voller Pfad aus älteren Einstellungen gilt weiter für alle Auswertungen.

## Schritt 2: eigene Modes mit Zielzeiten (1.65.3)

- Unten im Fenster "Modes und Zielzeiten": "Eigener Mode" (Name, Leerzeichen werden zu `_`), Zielzeit hh:mm:ss,
  "Hinzufügen". Gespeichert in der Auswertung (`settings["auto"]["evaluations"][..]["modes"]`).
- Noch nicht vorhandene eigene Modes stehen unter "Eigene Modes, noch nicht gefunden" (Häkchen, Zielzeit, "wartet auf
  Daten", Entfernen) und in der Zusammenfassung von Schritt 2.
- Taucht im Quellverzeichnis ein neuer Mode mit genau diesem Namen auf (Abgleich vor jedem Zyklus bzw. beim Speichern
  der Regel), bekommen seine neuen DUTs Zielzeit und Häkchen des eigenen Modes. Gibt es den Mode schon, gilt die
  Zielzeit sofort für alle seine DUTs; Änderungen an Häkchen/Zielzeit eines gefundenen Modes werden in den eigenen
  Mode übernommen.

## Schritt 2: Modes und Zielzeiten im eigenen Fenster (1.65.2)

- Das Popup "Modes und Zielzeiten" blieb in Dear PyGui leer (der Inhalt wurde erst beim Klick in ein Popup-Fenster
  geschrieben, das innerhalb des Auto-Fensters angelegt war). Jetzt ein eigenes Fenster `auto_modes_window`: beim
  Öffnen gefüllt, je Gruppe ähnlicher Modes ein Knoten, je Mode Häkchen, Zielzeit hh:mm:ss, Zahl der DUTs und
  Hinweis "Zielzeit fehlt"; Alle/Keine, "für alle angehakten", Schließen. Wechselt die Auswertung, wird die Liste
  nachgezogen.

## Verzeichnisverwalter: Mode aus Dateinamen (1.65.1)

- Struktur wie `...\DV\HTOE22kW\CSV\DES202507230117500132\DES202507230117500132_AC_22kW_3ph_615V.csv`: Vorschläge
  {Testlauf} = DV, {Test-Variante} = HTOE22kW (jetzt auch ohne Trennzeichen, vorher fälschlich als Mode erkannt),
  {Seriennummer} = DES..., {Mode} aus den Dateinamen (`dirrules.file_values`: zusammenhängende Teile mit 22kW/615V/3ph
  ohne Seriennummer, DUT, Testlauf, Variante, Zähler, Zeitstempel). Erweiterter Zielordner vorgeschlagen als
  {Testlauf}_{Test-Variante}\{Mode}\{Seriennummer} (Testlauf/Variante nur, wenn erkannt).
- `dirrules.plan` arbeitet je Datei: Ordner mit Dateien verschiedener Modes werden auf mehrere Zielordner verteilt;
  diese Teile lesen nur ihre Dateien (`AutoSettings.files`, Job-Feld `files`), neue Dateien kommen beim Abgleich vor
  dem Zyklus hinzu. Dateien ohne Mode (z. B. DES..._.csv) erscheinen in der Vorschau gekennzeichnet.
- Struktur-Anzeige mit Zeile "Dateinamen: ... -> {Mode}".

## Auto-Auswertung neu: Name -> Verzeichnisregel, Verzeichnisverwalter in 6 Schritten (1.65.0)

- Schritt 1 "Auswertung festlegen": Name (mit Anlegen bestätigen; leer = vorhandene Auswertung wählen; ohne
  Auswertungen Hinweis, dass ein Name nötig ist) -> Auswertung (nur Auswahl) -> Verzeichnisregel (Auswahl aus den
  definierten Regeln, sonst Hinweis) mit "Verzeichnisregel verwalten..." (übernimmt den Namen als neue Regel; hat
  die Auswertung schon eine Regel, wird sie bearbeitet). Darunter die Angaben der Regel nur zur Information
  (Quellverzeichnis, Zielverzeichnis, Einlesen/Ausschlüsse, Zielordner, Modes). Manuelle Quell-/Zielfelder entfallen;
  ältere Auswertungen mit Handeingabe laufen als "ohne Verzeichnisregel" weiter (`settings["auto"]["evaluations"]`,
  Job-Feld `evaluation`).
- Schritt 2 "Modes und Zielzeiten": Dropdown (Popup) mit allen Modes, ähnliche Namen gruppiert (Baum je Gruppe),
  je Mode Häkchen (verarbeiten) und Zielzeit hh:mm:ss; nicht angehakte Modes brauchen keine Zielzeit; Abschließen
  verlangt sie für alle angehakten. Alle/Keine, "für alle angehakten".
- Verzeichnisverwalter (Regel v2, `dirrules.Rule.version = 2`): Name der Regel (neu bzw. BEARBEITEN mit Hinweis),
  1 Quellordner + Struktur (Unterordner je Ebene), 2 Daten als auf-/zuklappbarer Baum mit Häkchen je Datei bzw.
  Ordner (Ausschlüsse `excluded`), 3 Basis Zielordner, 4 Platzhalter automatisch aus den Ordnernamen erkannt -
  {Mode}, {Testlauf} (DV, PV), {Test-Variante} (HTOE_..., PTCE_...), {Seriennummer} (DES..., sonst aus Dateinamen),
  {DUTx}, {Datetime}, {Name} - mit optionalen eigenen Werten und frei kombinierbarem erweitertem Zielordner,
  5 Zielordner = Basis + erweitert, 6 Vorschau mit Häkchen je Zielordner. "Regel speichern" legt fehlende
  Zielordner an; Fehler zeigt ein eigenes Fenster (`dir_error`). Modes ohne Zahlen im Namen (z. B. Precon) werden
  über ihre Ebene erkannt.
- Nur neue Daten: Ordner mit demselben Ziel bilden einen Teil (`folders`), abgewählte Dateien (`exclude`) liest die
  Engine nicht; vorhandene Teile behalten ihre gelesenen Daten (Engine bleibt bei Ordneränderungen), vor jedem
  Zyklus werden neue Ordner der Regel aufgenommen und ihre Zielordner angelegt.
- Ältere Regeln (Muster/Vorlage) funktionieren weiter. Abbildungen 14 und 18 und das Handbuch (DE/EN/TH/ZH) sind
  angepasst.

## Marker 3: Min, Max, Average, Drift in der Wertetabelle (1.64.1)

- Die M3-Wertetabelle hat je Signal: Wert an M3, Min, Max, Average, Drift. Bereich wählbar neben "Marker 3":
  "Zwischen M1 und M2" (Standard; ohne eingeschaltete Marker gilt der gesamte Verlauf, mit Hinweis) oder
  "Gesamter Signalverlauf" (Einstellung `m3_range`, in Ansicht/Projekt `marker3_range`). Drift = Delta Y / Delta X
  (zwischen M1 und M2 wie in der Wertanzeige, gesamt vom ersten zum letzten Messpunkt). Die Tabelle wird nur bei
  Änderungen (Position, Bereich, Daten) neu gerechnet.

## Marker beim Zoomen auf 10 %/90 %, Marker 3 mit Wertetabelle (1.64.0)

- Zoom/Unzoom (Mausrad, Rechteck, Doppelklick, "Alles anzeigen", Kopplung) setzt M1 auf 10 % und M2 auf 90 % der
  neuen Ansicht. Ändern mehrere Graphen im selben Bild ihre Ansicht, gilt der Graph unter der Maus zuerst;
  mitgeführte Graphen (Marker synchron) mit anderer Ansicht werden im selben Bild nicht erneut gesetzt (kein
  Hin und Her). Beim Einschalten der Marker landen Marker außerhalb der Ansicht ebenfalls bei 10 %/90 %.
- Neues Häkchen "Marker 3": dritter (grüner) Marker M3 je Graph, unabhängig von M1/M2 (`GraphSlot.cross3`,
  `SlotUI.m3_line`). Maus an M3 (12 Pixel) oder beim Ziehen: Tooltip-Fenster `m3_tip` mit Wertetabelle aller
  Signale des Graphen an M3 (Signal, Wert mit Einheit und Wert->Text). Synchron mit "Marker synchron";
  fällt M3 beim Zoomen aus dem Bild, kommt er in die Mitte. Gespeichert in Ansicht/Projekt
  (`marker3_on`, `cross3`).

## Verschieben der sekundären Y-Achse (1.63.2)

- Ziehen mit der linken Maustaste verschob die rechte Y-Achse nicht. Neu `_poll_y2_pan` (je Bild): Über der
  Zeichenfläche folgt die rechte Achse der Verschiebung der linken (gleicher Anteil des Bereichs), über der rechten
  Achse folgt sie der Maus. Verschiebt ImPlot die rechte Achse selbst, greift MessGraph für diesen Zug nicht ein.
  Marker- und Kommentarziehen verändern die linke Achse nicht und lassen auch die rechte stehen.

## Mausrad zoomt die sekundäre Y-Achse (1.63.1)

- Mit Dear PyGui 2.x zoomte das Mausrad nur die erste (linke) Y-Achse. Neuer Mausrad-Handler (`_on_wheel`): Über
  der Zeichenfläche oder der rechten Achse zoomt MessGraph die rechte Achse um die Mausposition (10 % je Rastung,
  wie ImPlot), aber nur wenn ImPlot sie im selben Bild nicht schon verändert hat (Vergleich mit dem vor dem Bild
  gemerkten Bereich, `_snapshot_y2`) - kein Doppelzoom bei Versionen, die es selbst können. Über der linken Achse
  bleibt die rechte unverändert. Die Achse ist nach einem Bild wieder frei (Ziehen, weiteres Zoomen).

## Tooltip am Signal bei aktiven Markern (1.63.0)

- Mit eingeschalteten Markern zeigt ein Tooltip (Fenster `marker_tip`, folgt der Maus) für das Signal unter der
  Mausspitze: X1-Wert, X2-Wert, Y1-Wert, Y2-Wert, Delta X, Delta Y, Average Signal (Mittelwert zwischen M1 und M2),
  Drift-Signal, Drift-Regression und Regression f(x) = m*x + b (gewählte Art der Drift-Regression).
- Bei mehreren Kurven nur ein Tooltip: für die Kurve mit dem kleinsten senkrechten Abstand zur Mausspitze (höchstens
  10 Pixel); Signale an der rechten Y-Achse werden in deren Maßstab gemessen. Auch im Detailfenster.
- Ausgeblendet ohne Marker, abseits der Kurven, bei offenem Kontextmenü und beim Verschieben eines Kommentars.

## MDF/MF4: doppelte Kanalnamen, Text-Kanäle, Konstanten, Wert->Text (1.62.0)

- Jeder Kanal wird über (Gruppe, Index) gelesen und bekommt einen eindeutigen Anzeigenamen
  (`loaders.mf4_display_names`): eindeutige Namen bleiben; bei Konflikten "Gruppe / Kanal" (Gruppenname aus
  acq_name, bei Buslogging die Botschaft, z. B. `IVT6_Msg_Result_I / IVT_Result_I`), bei einer Gruppe mit nur einem
  Datenkanal oder ohne Gruppennamen `Kanal [g714]`, verbleibende Doppelte `Kanal [g714:i3]`. Vorher konnten zwei
  Kanäle derselben Gruppe denselben Namen "Kanal (G714)" bekommen. Gleiches für DBC-dekodierte Signale.
- Frühere Namen bleiben als Alias (`Channel.aliases`, `data_model.find_channel`): Ansichten, Projekte, Formeln und
  die Suche finden die Kanäle weiter.
- Jedes Signal behält eigene Zeitstempel und Werte (kein Resampling); der Graph zeichnet jedes mit seiner Zeit.
- Wert->Text-Umrechnung: Rohwerte (`raw=True`) als Zahlen im Graphen, Texte in `Channel.value_text`; Wertanzeige
  "1 (Charging)", Tooltip am Kanal mit der Zuordnung.
- VLSD-Strings/Byte-Felder (kind "text"), Kanäle mit 1 Wert ("const", Knopf "Wert") und ohne Werte ("empty")
  stehen grau in der Liste und werden nicht gezeichnet; Erkennungsangaben mit Anzahl. Ermittelt ohne Laden aus
  Datentyp, Kanaltyp und cycles_nr der Gruppe.
- Große Dateien (z. B. 3284 Kanäle): Laden auf Abruf und Suchfeld (höchstens 400 Treffer je Datei) waren schon
  vorhanden; die Suche findet jetzt auch Gruppen- und frühere Namen.

## Hilfe-PDF: "ValueError: negative dimensions are not allowed" behoben (1.61.3)

Die Bilder für das Hilfe-PDF wurden mit `dpg.load_image` gelesen und ohne Prüfung umgeformt; eine beschädigte oder
leere eigene Aufnahme (Ordner .messgraph_hilfe_bilder) lieferte ungültige Maße und brach das ganze PDF ab. Jetzt:
Lesen über Pillow (sonst `dpg.load_image` mit Prüfung von Breite, Höhe, Kanälen und Datenmenge); ist eine Aufnahme
unlesbar, wird die mitgelieferte Abbildung verwendet (Meldung "Bild nicht lesbar, übersprungen", Details im
Fehlerprotokoll), fehlt auch die, steht ein Hinweis im PDF. Das PDF wird immer erstellt.

## Belegte Ergebnisdatei: "[WinError 5] Access is denied" (1.61.2)

Neues Modul `messgraph/safewrite.py` für Time_counter.json, statistics.json, PNG und Report:
- Sperre im Programm je Datei (Threads schreiben nie gleichzeitig) und Sperrdatei `<Datei>.lock` mit PID für mehrere
  MessGraph-Instanzen; eine verwaiste Sperrdatei (Prozess beendet) wird entfernt. Lesen-Ergänzen-Schreiben der
  gemeinsamen Time_counter.json geschieht unter beiden Sperren.
- Schlägt das Ersetzen fehl, wird der Zugriff analysiert: Windows Restart Manager (unter Linux /proc) nennt die
  Prozesse, die Datei oder .tmp offen halten; Eintrag im Log. Wiederholung mit wachsender Pause (etwa 10 s), danach
  wird der Inhalt direkt in die Datei geschrieben (braucht keine Lösch-Freigabe). Erst wenn auch das scheitert,
  erscheint ein Fehler mit den belegenden Prozessen.
- Fremde Prozesse werden bewusst nicht beendet (Virenscanner, Suche, OneDrive geben die Datei selbst frei; eine
  andere Instanz könnte gerade schreiben). Handbuch: Abschnitt "Ablauf eines Zyklus im Detail", Punkt Ergebnisdatei.

## Sprachwechsel: Absturz "Alias already exists" behoben (1.61.1)

- Beim Umschalten der Sprache (gemeldet bei Chinesisch, betraf jede Sprache) brach der Neuaufbau mit "Alias already
  exists" ab: Das Popup "Regel übertragen" des Limiters (`lim_xfer_popup`) und der Verzeichnisverwalter
  (`dir_window`) wurden vor dem Neuaufbau nicht gelöscht. Popups sind in Dear PyGui eigene Fenster und verschwinden
  nicht mit dem Fenster, in dem sie angelegt werden. Alle festen Tags stehen jetzt in `App.REBUILD_TAGS`; ein Test
  prüft, dass jeder `tag="..."` im Code dort aufgeführt ist.
- Die Nachbildung von Dear PyGui in den Tests meldet jetzt doppelte Tags wie das Original und lässt Popups das
  Löschen ihres Auslösers überleben; Test: alle Sprachen nacheinander umschalten.
- `add_font_chars` wird nur noch bei Dear PyGui vor 2.0 aufgerufen (ab 2.0 werden Zeichen automatisch geladen; die
  Warnung "deprecated function add_font_chars" entfällt).

## Chinesisch (Mandarin) und Zyklusablauf im Handbuch (1.61.0)

- Sprache Chinesisch (vereinfachte Schriftzeichen): Sprache > 中文 (Chinese). Oberfläche (`i18n_zh.py`, alle Texte;
  fehlt künftig eine Übersetzung, erscheint Englisch) und vollständiges Handbuch (`help_zh.py`, alle 20 Kapitel mit
  denselben 24 Abbildungen und Markierungen), Hilfe als PDF mit eingebetteter Schrift, PNG-Texte.
- Schrift: braucht chinesische UND lateinische Zeichen - Windows: Microsoft YaHei (msyh.ttc, vorhanden), DengXian,
  SimHei; Linux: fonts-wqy-microhei/-zenhei, Noto Sans CJK; macOS: PingFang. Ohne passende Schrift ist Chinesisch
  nicht wählbar (Meldung). `ttf.py` liest jetzt TrueType-Sammlungen (.ttc, erste Schrift) und bettet sie als
  einzelne Schrift ins PDF ein; in Dear PyGui werden nur die tatsächlich verwendeten ~750 Zeichen geladen.
- Handbuch (Deutsch, Englisch, Thai, Chinesisch), Kapitel Auto-Auswertung: neuer Abschnitt "Ablauf eines Zyklus im
  Detail" mit 12 Schritten (Fälligkeit, Grundlagen, Quellordner abgleichen, Lesen mit Zeitstempel-Reihenfolge,
  Gruppieren, Aneinanderfügen, Limiter, Bewertung, statistics.json, Bilder, Ergebnisdatei atomar, Log/Anzeige) sowie
  Abbrechen, Arbeitsspeicher und Report-Zeitplan; danach "Erster Durchlauf und Folgedurchläufe".
- Behoben: Hilfe-PDF in Thai/Chinesisch fiel ohne passende Schrift auf die Latin-Schrift zurück; jetzt Meldung
  "PDF nicht erstellt".

## Auto: erster Durchlauf alle Dateien, danach nur neue/geänderte (1.60.3)

Geprüft und abgesichert: Der erste Durchlauf einer Auswertung verarbeitet jetzt immer alle Dateien des Quellordners
(ohne Zeitbudget; vorher konnte er bei großen Datenmengen auf mehrere Zyklen verteilt werden). Ab dem zweiten
Durchlauf werden nur neue und geänderte Dateien gelesen (Änderungszeit/Größe), gelöschte fallen heraus; das Zeitbudget
(70 % der Zykluszeit) gilt erst dann. "Jetzt ausführen" bewertet alles neu, liest aber ebenfalls nur Neues. Log:
"Erster Durchlauf: alle n Dateien ..." bzw. "Folgedurchlauf: n neue/geänderte Dateien ...". Tests für Engine und
Oberfläche (Start, zweiter und dritter Zyklus).

## Auto: Schritt 4 im eigenen Fenster (1.60.2)

Schritt 4 (Zykluszeit, PNG, Ergebnisdatei, Start/Stopp/Jetzt ausführen, Fortschritt, Zähler, Log) steht wegen der
Informationsmenge im eigenen Fenster "Auto-Auswertung - Schritt 4: Zyklus starten" (`auto_run_window`). Es öffnet
sich beim Abschließen von Schritt 3; das Fenster mit den Schritten 1 bis 3 bleibt offen. "Fenster Schritt 4
öffnen..." bzw. Auto > Log anzeigen öffnen es erneut; der Fortschrittsbalken erscheint in beiden Fenstern.

## Auto: wechselnde Anteile einer Verzeichnisregel als **** (1.60.1)

Mit gewählter Verzeichnisregel zeigt das Auto-Fenster die wechselnden Anteile als `****`: Auswertung =
`**** (Regel <Name>, n Auswertungen)` (ein Eintrag je Regel in der Auswahl), Name = `****`, Quellverzeichnis =
Basisordner der Regel + `\****`, Zielverzeichnis = fester Teil der Zielbasis + `\****`, Mode = `****` (alle Modes).
Zielzeit und "verarbeiten" bei Mode `****` gelten für alle Modes der Regel (verschiedene Zielzeiten: Feld leer, nichts
wird überschrieben), bei gewähltem Mode nur für diesen. Löschen entfernt alle Auswertungen der Regel, Kopieren ist
gesperrt, Neu legt eine manuelle Auswertung an. `****` wird nie in die Auswertungen übernommen.

## Auto neu strukturiert: feste Schritte, Verzeichnisregel im Auto-Fenster, keine Doppel (ab 1.60.0)

- Auto-Auswertung in vier Schritten mit Erklärtext und ausführlichen Tooltips: 1 Auswertungen festlegen (einzeln oder
  per Verzeichnisregel), 2 Modes und Zielzeiten, 3 Analysieren und Grenzen prüfen, 4 Zyklus starten (plus Report).
  Nur der aktuelle Schritt ist bedienbar; "Schritt abschließen" prüft und sperrt ihn und gibt den nächsten frei.
  Start (Durchlauf gestartet) und "Zurücksetzen" geben alle Schritte wieder frei (Einstellung `auto_step`).
- Verzeichnisverwalter nicht mehr im Menü Auto, sondern über "Verzeichnisregel verwalten..." in Schritt 1; das
  Fenster führt in sechs Schritten mit Tooltips, neu "Speichern und Auswertungen anlegen".
- Keine Doppel: Limiter bietet jede Datei nur einmal an (ohne Groß/klein; Ein-Datei-Gruppen nur als Datei), der
  Report jedes Zielverzeichnis nur einmal; doppelte Auswertungen (gleiche Quelle und Ziel) werden entfernt.
- Handbuch-Bilder 14 und 18 neu.

## Korrektur: Report ohne fertigen Zyklus (1.59.3)

"Report erstellen" bricht nicht mehr mit "noch keine Ausgaben" ab: Gewählte Auswertungen ohne `statistics.json` (z. B.
nur analysiert, oder der erste Zyklus läuft noch) bekommen zuerst automatisch einen Zyklus, danach werden die Reports
erstellt; während einer laufenden Analyse bzw. eines laufenden Zyklus wird der Report vorgemerkt und danach erstellt.
Bereite Auswertungen ohne Ausgaben sind im Report-Fenster angehakt und markiert. Gilt auch für den Zeitplan.

## Limiter: Regel auf eine Auswahl von Dateien übertragen (1.59.2)

Limiter bearbeiten... -> Zeile "Regel übertragen": Regel wählen, Dateien über das Auswahlmenü anhaken (Alle, Keine,
Nur mit Signal; Dateien ohne das Signal gekennzeichnet), "Auf Auswahl anwenden". Vorhandene Regel derselben Datei und
desselben Signals übernimmt Grenzen und aktiv, sonst wird eine Regel ergänzt; fehlende Signale werden gemeldet.

## Report je Mode mit allen gewählten DUTs (1.59.1)

"Report erstellen" gruppiert die angehakten Auswertungen nach Mode und erstellt je Mode einen Report mit allen
gewählten DUTs dieses Modes: `Report_<JJJJMMTT_hhmmss>_<Mode>_<DUT1_DUT2 ...>.pdf`. Das Feld heißt jetzt
"Ausgabeordner" (leer = gemeinsamer Ordner der Zielverzeichnisse des Modes, bei einem DUT dessen Zielverzeichnis);
der Schalter "Datum/Uhrzeit an den Dateinamen" entfällt, weil Datum/Uhrzeit immer im Namen stehen. Gilt auch für den
Zeitplan; Fortschritt "1/3 <Mode>: ...".

## Auto: Modes einer Regel mit Zielzeit, Analyse aller Modes (ab 1.59.0)

- Mit Verzeichnisregel listet "Mode (alle Dateien)" alle Modes der Regel; Zielzeit und "verarbeiten" stehen in derselben
  Zeile und gelten für alle DUTs des gewählten Modes. Übersicht darunter: alle Modes mit Zielzeit (neue: offen) und
  wie viele noch keine Zielzeit haben. Die Zielzeit-Zeile ist dafür in die Mode-Zeile gewandert.
- Analysieren mit Regel: alle zu verarbeitenden Auswertungen der Regel (alle gewählten Modes und DUTs) nacheinander,
  danach je Mode Vorschläge aus den Daten aller DUTs (neuer Mode komplett mit Zielzeit des Modes, vorhandener Mode
  um fehlende Signale ergänzt; "Grenzen neu vorschlagen" erneuert alle Grenzen). Zum Schluss Grenzwert-Konfigurator.

## Auto: Regel legt alle Auswertungen an, Mode = {Mode*} (1.58.4)

Verzeichnisregel im Auto-Fenster gewählt -> je passendem Quellordner (mit Messdateien) eine Auswertung: Auswertung =
Name = Name aus der Regel, Quelle/Ziel aus der Regel, Mode (alle Dateien) = `{Mode*}` der Regel (Feld `rule_mode`).
Gleiche Quelle wird aktualisiert statt doppelt angelegt; die Quellordner-Auswahl wechselt zur passenden Auswertung;
Regel speichern im Verzeichnisverwalter zieht die Auswertungen nach.

## Verzeichnisverwalter: Struktur DUTx\Report\Modex\Files richtig erkannt (1.58.3)

- Beispiel: Basisordner `Z:\...\Halle_D_Setup` mit `DUTx\Report\Modex\Files` (mehrere DUTs und Modes) ->
  Muster `DUT*\Report\*\Files`, Vorlage `{MODE}_{DUT}`, Ziel `<Zielbasis>\EU_AC_3ph_22kW_705V_DUT1\Files`.
- `{MODE}` ist jetzt der Mode-Ordner (wie `EU_AC_3ph_22kW_705V`, sonst der letzte `*`-Teil, der kein DUT ist) statt
  des letzten Ordners (vorher wurde daraus `Files_DUT1`). Neu `{REST}` = Ordner unterhalb des Mode-Ordners.
- Zielbasis ohne Platzhalter: Ziel = Zielbasis\Name\REST; mit Platzhaltern wird REST angehängt (außer der Pfad endet
  schon damit oder enthält `{REST}`). `{DUTx}`/`{Modex}` wie `{DUT}`/`{MODE}`; DUT-Ordner auch als `DUT_02`, `HTOE_DUT3`.
- Strukturvorschlag aus der häufigsten Struktur (`dirrules.best_example`); andere Ordner mit Messdateien (z. B.
  `DUTx\Logs`, Dateien direkt in `Report`) stören nicht; Mode-Ordner mit beliebigen Namen werden zu `*`.

## Auto: Quelle und Ziel aus der Verzeichnisregel (1.58.2)

Im Auto-Fenster je Auswertung die Zeile "Verzeichnisregel": gespeicherte Regel des Verzeichnisverwalters wählen ->
passenden Quellordner wählen; Quelle, Ziel und Name kommen aus der Regel, die Felder sind dann schreibgeschützt.
"(manuelle Eingabe)" = Quelle und Ziel von Hand wie bisher. Feld `rule` je Auswertung; vom Verzeichnisverwalter
angelegte Auswertungen merken sich die gespeicherte Regel, eine gelöschte Regel schaltet auf manuelle Eingabe zurück.

## Verzeichnisverwalter: Zielbasis mit Platzhaltern (1.58.1)

Die Zielbasis darf selbst Platzhalter enthalten und ist dann der ganze Zielpfad, z. B.
`...\MessGraph\_TestResult\{Mode*}_{DUT*}` (`dirrules.render_path`, zusätzlich `{NAME}`). Platzhalter sind
unabhängig von Groß-/Kleinschreibung, ein angehängtes `*` ist erlaubt. Fehlende Zielordner werden angelegt, doppelte
Zielordner in der Vorschau gemeldet.

## Auto: Verzeichnisverwalter (ab 1.58.0)

Auto > Verzeichnisverwalter... (auch als Schaltfläche im Auto-Fenster, Logik in `messgraph/dirrules.py`): legt
Auswertungen aus der Ordnerstruktur an, z. B. Quelle `...\DUT1\Report\EU_AC_3ph_22kW_705V` -> Zielordner
`Test\EU_AC_3ph_22kW_705V_DUT1`.

- Struktur analysieren: sucht unter dem Basisordner alle Ordner mit Messdateien und schlägt Muster und Vorlage vor
  (unterschiedliche Ordner sowie DUT- und Mode-Ordner werden zu `*`, z. B. `DUT*\Report\*` und `{MODE}_{DUT}`);
  Beispiel und Ebene des Quellordners wählbar.
- Manuelle Eingabe: Muster (Ordner relativ zum Basisordner, `*`/`DUT*` beliebig, Groß-/Kleinschreibung egal) und
  Vorlage mit `{MODE}`, `{DUT}` (auch oberhalb des Basisordners), `{PARENT}`, `{1}`, `{2}` ... und freiem Text.
- Vorschau mit Dateien, Name, Zielordner und Status (leere Ordner und vorhandene Auswertungen abgewählt, doppelte
  Namen gemeldet); Auswertungen anlegen mit Zielzeit, Zielordner gleich anlegen, optional vorhandene aktualisieren.
- Regeln speichern/laden/löschen (Einstellungen `auto_dirrules`) und auf weitere Mode-/DUT-Ordner oder andere
  Basisordner übertragen.
- Handbuch: neues Kapitel mit Bild 18 (Bilder jetzt 24).

## Auto: Grenzvorschläge mit Limiter (1.57.1)

- Analysieren berücksichtigt den Limiter (`AutoEngine.analyze(limiter_cfg)`, gemeinsame Regelanwendung
  `AutoEngine.limit`): Minimum, Maximum und vorgeschlagene Grenzen nur aus den Abschnitten im Limit; Anteil im Limit
  in der Analysezeile.
- Neue Schaltfläche "Grenzen neu vorschlagen" im Auto-Fenster: Grenzen des Modes der Auswertung neu aus den
  (gekürzten) Daten, aktiv/inaktiv und Zielzeit bleiben. Nach einer Limiter-Änderung weist das Auto-Fenster darauf hin.

## Report: Graphen pro Seite, Mode-Überschrift; Peak-Farben in den Graphen (ab 1.57.0)

- Report-Fenster: Auswahl "Graphen pro Seite" 9 (3 x 3), 4 (2 x 2), 2 (nebeneinander), 1 (ganze Seite) für die
  Bilder je DUT im Mode-Teil (`ReportOptions.per_page`, gespeichert, auch für den Zeitplan). Der Vergleichsteil hat
  ab 1.57.2 immer 9 Graphen pro Seite (3 x 3).
- Abschnitt je DUT heißt jetzt "Mode: <Gruppe>" statt "<Auswertung>: <Gruppe>".
- Hintergrund der Auto-Graphen: hellrot = Regression verletzt die Zielzeit (wie bisher), hellgelb = Messwerte (Peaks)
  außerhalb Limit_min/Limit_max, hellviolett = beides. Textzeile "Peaks außerhalb der Grenzen!", in statistics.json
  `peak_violated`.

## Limiter mit Auto-Auswertung verbunden (1.56.3)

Limiter bearbeiten... (Menü Limiter oder Auto-Fenster) bietet Dateien und Signale jetzt auch ohne geladene Dateien an:
aus den Auto-Auswertungen (Gruppenname = alle Dateien der Auswertung, dazu die einzelnen Dateien; nach Analysieren oder
einem Zyklus) und aus manuell gewählten Dateien (Schaltfläche "Datei wählen...", beginnt im Quellordner der gewählten
Auswertung; nur die Signalnamen werden gelesen). Eine neue Regel ist mit der Gruppe der gewählten Auswertung vorbelegt.
Nach einer Analyse wird ein offenes Limiter-Fenster aktualisiert.

## Korrektur: Neuen Zielordner anlegen (1.56.2)

Der Dialog "Neuen Zielordner anlegen" legt den Ordner beim Bestätigen (Schaltfläche jetzt "Anlegen") samt fehlender
Elternordner an, statt mit "Ordner nicht gefunden" abzubrechen. Kann der Ordner nicht angelegt werden (z. B. keine
Schreibrechte), steht der Grund im Dialog. Andere Speichern-Dialoge sind unverändert.

## Auto: Name ist führend, Mode und DUT aus dem Namen (ab 1.56.1)

- Neu/Kopieren übernimmt den im Feld Name eingetragenen Namen als neue Auswertung im Auswahlfeld (z. B.
  `AC_11_22kW_1ph_615V_DUT1`); die vorher gewählte Auswertung behält ihren Namen. Unveränderter Name: nächste
  DUT-Nummer (`..._DUT1` -> `..._DUT2`), sonst "(2)".
- Mode = Name ohne angehängtes `_DUTn` (`AC_11_22kW_1ph_615V`), DUTs eines Modes teilen dessen Grenzen; Umbenennen
  benennt einen gemeinsam genutzten Mode nicht mit um. Report-Spalte = DUT aus dem Namen (vor dem Dateinamen).
- Verzeichnisse unter `Test` folgen dem Namen: Vorschlag `Test\<Name>`, Kopieren setzt einen Zielordner unter Test auf
  den neuen Namen.

## Handbuch mit Abbildungen für Limiter und Auto, Report-Zeitplan (ab 1.56.0)

- Handbuch (DE/EN/TH): Kapitel Limiter und Auto-Auswertung mit fünf neuen Abbildungen und nummerierten
  Erläuterungen (limiter, auto, autograph, report, reportseite; erzeugt von `tools/make_help_illustrations.py`, die
  Beispielgraphen und der Beispiel-Report entstehen dabei mit der echten Auto-Auswertung), dazu Schritt-für-Schritt-
  Anleitungen. Bilder jetzt 23 (neu durchnummeriert).
- Report nach Zeitplan (Auto > Report erstellen...): unabhängig vom Datenzyklus zu festen Uhrzeiten (eine oder mehrere,
  z. B. "00:00:00, 12:00"), täglich oder einmalig; optional Datum/Uhrzeit im Dateinamen. Gespeicherte Auswahl und
  Optionen werden verwendet; nächster Termin im Report- und Auto-Fenster, Vermerk im Log. Läuft, solange MessGraph
  geöffnet ist; Einstellungen bleiben gespeichert.

## Auto: Namen als Standard, Basisordner Test (ab 1.55.1)

- Auch die einzige Auswertung ist löschbar; dann bleibt eine leere Auswertung (Quelle, Ziel, Mode gelöscht, Zielzeit 24h).
- Basisordner `<Programmordner>/Test` (`gui.AUTO_BASE`): Ordnerauswahl für Quelle und Ziel beginnt dort; "Neuen
  Zielordner anlegen" schlägt `<Programmordner>/Test/<Name der Auswertung>` vor.
- Mode (alle Dateien) und Mode im Grenzwert-Konfigurator (auch bei neuer Konfiguration) sind standardmäßig der Name der
  Auswertung, solange kein anderer gewählt/angelegt wird; Umbenennen der Auswertung benennt diesen Mode mit um.
  Fehlt der Mode in der geladenen Konfiguration, schlägt der Zyklus ihn aus den Daten vor.

## Auto: Report über mehrere Auswertungen (ab 1.55.0)

Auto > Report erstellen...: Auswertungen (je eine = ein DUT) per Haken wählen, Titel/Projekt/Mode/Ausgabedatei,
Wasserzeichen "NOT RELEASED" (standardmäßig an, abwählbar). Aufbau wie das Muster (A4 quer, `messgraph/autoreport.py`):
Deckblatt, Summary Comparison (Mittelwert je DUT, Average, Min %, Max %, Limit Min/Max), Signal Plot Comparison (je
Signal die PNG aller DUTs, 3 x 2), je DUT Tabelle (Min, Max, Mean grün/rot, Std, Limits) und alle PNG (3 x 3).
Grundlage: je Auswertungsgruppe schreibt jeder Zyklus `statistics.json` neben die PNG (`AutoEngine.write_statistics`).
PNG werden ohne Umrechnung eingebettet (IDAT mit PNG-Prädiktor). Erstellung im Hintergrund mit Fortschritt und Abbruch.

## Auto: Neuen Zielordner anlegen (ab 1.54.1)

Schaltfläche "Neuen Zielordner anlegen" neben dem Zielverzeichnis: ein eingetragener, noch fehlender Ordner wird
sofort angelegt; sonst schlägt ein Dialog `<Name>_Ergebnis` neben dem Quellordner vor und legt den bestätigten Pfad an.
Fehlende Zielordner werden außerdem beim Start bzw. bei "Jetzt ausführen" angelegt.

## Auto: mehrere Auswertungen (ab 1.54.0)

Die Auto-Auswertung verwaltet beliebig viele Auswertungen (Neu, Kopieren, Löschen, aktiv). Jede hat Name,
Quellverzeichnis, Zielverzeichnis, Mode und eigene Zielzeit (Zeit oder Schritte; ersetzt die Zielzeit des Modes für
diese Auswertung). Der Name wird zum Mode-Namen (Leerzeichen -> _) und damit zum Schlüssel `count_<Name>_<Gruppe>`;
ohne Konfiguration bzw. ohne passenden Mode legt Analysieren einen Mode mit Vorschlägen unter diesem Namen an.
Zykluszeit, PNG, Gruppierung und die Ergebnisdatei gelten für alle; die Ergebnisdatei ist gemeinsam (voller Pfad oder
Dateiname im Ziel der ersten Auswertung). Je Zyklus laufen die Auswertungen nacheinander (eigene Engine je Auswertung,
Zeitbudget geteilt); Bilder und Log je Zielverzeichnis; unvollständige Auswertungen werden mit Hinweis ausgelassen.
Die Auswertungen werden in den Programmeinstellungen gespeichert (ältere Einstellungen mit einem Quellordner werden
übernommen).

## Auto: Fortschritt und aussagekräftige Graphen (ab 1.53.0)

- Fortschrittsbalken bei Analysieren und in jedem Zyklus (Auto-Fenster und Statuszeile des Hauptfensters):
  "Lese Dateien 3/12: Datei", "Erzeuge Bilder 5/80: Signal", "Schreibe Ergebnisdatei"; Abbrechen beendet nach der
  aktuellen Datei bzw. dem aktuellen Bild (`AutoEngine.progress`, `AutoEngine.cancel`).
- Jedes PNG: obere/untere Grenzlinie, Trendlinie (gestrichelt, Regression der unter Graph-Optionen gewählten Art,
  20 % über das Datenende verlängert), Textblock rechts (`PlotSpec.info`) mit Signalname, Limit_max, Limit_min,
  Regression (Nummer, Name, m, b, f(x) = m * x + b mit x in s ab Start), Zielzeit, Zeit bis Violation, Bewertung.
  Violation vor Zielzeit: Plotfläche rot (`AutoEngine.assess` wie die Wertanzeige: Prognose ab letztem Messpunkt).

## Auto: eine Auswertung, zeitstempelrichtig zusammengefügt (ab 1.52.0)

- Standard "Alle Dateien des Quellordners = eine Auswertung" (`AutoSettings.one_group`): alle Dateien werden zu einer
  Messung zusammengefügt, auch mit unterschiedlichen Signalen. Name: DES-Nummer + DUT aus den Dateinamen, sonst
  gemeinsamer Grundname, sonst Ordnername. Abwählbar (dann Gruppen nach Dateiname wie bisher).
- Startzeit je Datei (`auto.file_start`, `auto.find_stamps`): Datumsspalte (normaler Leser, findet die Kopfzeile auch
  hinter einem Vorspann), sonst Datum+Uhrzeit in der ersten Datenzeile, Uhrzeit der ersten Datenzeile + Datum aus
  Vorspann/Dateiname, Zeitstempel im Vorspann, im Dateinamen, zuletzt Änderungszeit minus Messdauer (Hinweis).
  Formate u. a. 2026-06-09 10:00:00, 09.06.2026 10:00:00, 06/09/2026 10:00:00 PM, "Tue Jun 9 10:00:00.000 am 2026",
  20260609_101500. Relative Zeiten werden auf diese Startzeit gesetzt, dann wird nach Zeit sortiert und angehängt.
- Log und Analysefenster nennen je Datei Startzeit und Herkunft.

## Auto: Einen Zyklus jetzt ausführen (ab 1.51.2)

"Einen Zyklus jetzt ausführen" verarbeitet jetzt immer: ohne Zeitbudget, alle Gruppen neu bewertet, alle Bilder und
die Ergebnisdatei neu geschrieben, auch wenn keine Datei neu ist (`run_cycle(force=True)`); die Statuszeile meldet
das Ergebnis. Bisher passierte ohne neue Dateien (z. B. direkt nach der Analyse oder nach einem Lauf) sichtbar nichts.
Zusätzlich bewertet jeder Zyklus alle Gruppen neu, wenn sich Grenzwert-Konfiguration, Mode, Limiter oder
Ausgabeeinstellungen geändert haben (Fingerabdruck), statt alte Zähler stehen zu lassen.

## Auto: Quellordner analysieren und bedaten (ab 1.51.1)

Nach Wahl des Quellordners (oder Schaltfläche "Analysieren") liest die Auto-Auswertung alle Dateien darin
(`AutoEngine.analyze`) und stellt die Signale im Grenzwert-Konfigurator bereit (Spalte Datei "Auto: n Dateien",
Daten min/max über alle Dateien). Mit geladener Konfiguration gilt diese. Ohne Konfiguration entsteht ein Vorschlag
(`AutoEngine.propose_from_stats`): Mode "Auto", alle Signale aktiv, Grenzen aus den Daten (1-%- bis 99-%-Wert plus
10 % Spannweite), Zielzeit 24h; Signale abwählbar, Werte und Zielzeit änderbar. Im Konfigurator heißt das Feld jetzt
"Zielzeit (steps)". Neue Auswahl "Mode (alle Dateien)": die Bewertung nutzt genau diesen einen Mode für alle Dateien
des Quellordners. Die gelesenen Dateien werden für die Zyklen wiederverwendet.

## Auto-Auswertung (ab 1.51.0)

Neues Menü "Auto" zwischen Limiter und Hilfe (Auto-Auswertung einrichten..., Start, Stopp, Einen Zyklus jetzt
ausführen, Log anzeigen). Ein Verzeichnis wird zyklisch ausgewertet (`messgraph/auto.py`, `AutoEngine`):

- Rohdaten *.csv, *.asc, *.parquet (optional mit Unterordnern); nur neue/geänderte Dateien werden gelesen
  (Änderungszeit und Größe), gelesene Daten bleiben im Speicher, gelöschte fallen heraus.
- Gruppen: DES-Nummer + DUT aus dem Dateinamen (HTOE_PV_DES202609090470500176_AC_22kW_3ph_725V_DUT3 ->
  DES202609090470500176_DUT3), sonst Dateiname ohne angehängte Zähler/Zeitstempel, oder eigenes Muster (Regex,
  Klammergruppen mit _ verbunden). Gleiche Gruppe = gleicher Name, Ordner und Signale. Innerhalb der Gruppe nach
  Zeitstempel in den Daten sortiert und aneinandergehängt (Überlappungen nur einmal).
- Limiter wird angewendet (Regel passt auf Gruppenname oder eine Datei der Gruppe).
- Bewertung je Mode der Grenzwert-Konfiguration: Messpunkte, in denen alle Signale des Modes in ihren Grenzen liegen.
  Ergebnis wie Time_counter.json: `count_<Mode>_<Gruppe>` mit `actual` (Einheit des Ziels: Messpunkte bzw. Sekunden
  bei steps als Zeit), `actual_count`, `steps`, `fulfillment_percent`. Standard: nur Modes mit Treffern. Einträge
  anderer Gruppen in der Datei bleiben.
- Ohne Grenzwert-Konfiguration: Vorschlag aus den Daten (Mode Auto), gilt sofort und öffnet sich im
  Grenzwert-Konfigurator zum Bearbeiten.
- Je Signal ein Einzelgraph mit allen Daten als PNG im Zielverzeichnis (Unterordner je Gruppe;
  `messgraph/pngexport.py`, Pillow; ohne Pillow SVG).
- Zeitbudget 70 % der Zykluszeit; was nicht passt, wird auf die nächsten Zyklen verteilt; läuft ein Zyklus noch,
  wird der nächste ausgelassen. Hinweis im Fenster und in `MessGraph_Auto.log` im Zielverzeichnis.
- Einstellungen werden in den Programmeinstellungen gespeichert.
- Neue Abhängigkeit: `pillow` (requirements.txt).

## Limiter (ab 1.50.0)

Neues Menü "Limiter" zwischen Graph-Optionen und Hilfe. Der Limiter kürzt die Daten einer Datei auf die
Abschnitte, in denen Führungssignale in ihren Grenzen liegen, und zwar für alle Signale dieser Datei
(z. B. nur der obere Anteil eines Rechtecksignals).

- Regeln: Datei (Name, Muster wie lauf_*.csv oder * für alle), Signal, Limit min, Limit max (leer = keine Grenze),
  aktiv. Mehrere Regeln einer Datei gelten gleichzeitig (UND).
- Werte außerhalb entfallen; an jeder Lücke trennt ein NaN-Punkt die Linie. Verschiedene Zeitbasen (MF4): Der
  Zustand des Führungssignals wird bis zum nächsten Messpunkt gehalten; MF4-Führungssignale werden automatisch geladen.
- Graphen, Marker, Wertanzeige, Detailfenster, Druck, Export und Report arbeiten mit den gekürzten Daten. Die
  Dateiliste zeigt je Datei den Anteil der Messzeit im Limit.
- Menü: Limiter bearbeiten... (Regeltabelle, wirkt sofort), Konfiguration laden/speichern (*.yaml, Abschnitt
  "limiter"; andere Abschnitte der Datei bleiben erhalten), Limiter aktiv (ein/aus), Limiter entfernen.
- Die Regeln werden mit der Ansicht (*.mgraph) gespeichert.
- Beispiel: demo_data/demo_rechteck.csv mit demo_data/demo_limiter.yaml.
- Modul: messgraph/limiter.py (Rule, LimiterConfig, mask, held, apply, kept_share, load, save).

## Erkennung (Maus hierher) folgt der Sprache (ab 1.49.3)

Die Erkennungsangaben einer Datei entstanden beim Laden in der damals eingestellten Sprache. Nach einem Wechsel
von Thai auf Deutsch oder Englisch zeigte der Tooltip deshalb Thai-Text, den die lateinische Oberflächenschrift
nicht enthält: lauter Ersatzzeichen (Fragezeichen in einer Raute). Übersetzte Texte behalten jetzt Schlüssel und
Werte (i18n.Translated, i18n.retranslate) und werden bei der Anzeige in der aktuellen Sprache neu gebildet.

## Thai: Datei- und Signalnamen bleiben sichtbar (ab 1.49.2)

Bei Sprache Thai verschwanden Datei- und Signalnamen, Legenden und lateinische Teile der Bedienung, wenn als
Thai-Schrift eine reine Thai-Schrift (z. B. Noto Sans Thai) gefunden wurde: Dear PyGui zeigt alles in einer Schrift,
und dieser fehlen die lateinischen Buchstaben. Die Schriftsuche nimmt jetzt nur Schriften mit Thai- und
lateinischen Zeichen (alle druckbaren ASCII-Zeichen sowie ° µ ä ö ü ß); gesucht wird in den bekannten Pfaden,
unter /usr/share/fonts (tlwg, freefont, *Thai*) und in den eigenen Schriften (~/.local/share/fonts, ~/.fonts).
Thai stellt damit nur Bedienungstexte und Hilfe um.

## Datei-Auswahl: "Alle Dateien" (ab 1.49.1)

Die Auswahl "Datei" hat als ersten Eintrag "Alle Dateien" (sobald mehr als eine Datei geladen ist). Damit geht es
nach dem Wechsel auf eine einzelne Datei wieder zurück: Wurden die Graphen seither nicht anders belegt, kommt die
vorherige Darstellung exakt zurück (gemerkt beim ersten Wechsel weg von mehreren Dateien, auch über mehrere
Einzelwechsel hinweg). Sonst wird je Signal das gleichnamige Signal aller geladenen Dateien angezeigt; MF4-Kanäle
werden dafür erst geladen.

## Werkzeugleiste aufgeräumt (ab 1.49.0)

Über den Graphen stehen jetzt zwei kompakte Zeilen statt drei, Gruppen durch einen dünnen Strich getrennt:

- Zeile 1, Daten und Aufteilung: Datei | Matrix (z. B. 2*3), Anwenden, Zeilen..., Vorschlag... | Alles anzeigen, Alle Plots löschen
- Zeile 2, Anzeige und Messen: Marker, Marker synchron | X-Achsen koppeln, Datum/Uhrzeit-Achse, Regressionslinien |
  Dateien vergleichen..., Darstellung...

Farbschema und Schriftgröße liegen im Aufklapper "Darstellung...". Schaltflächen sind flach (kompakte Höhe),
Beschriftungen vor Eingaben gedimmt. Die Dateiauswahl passt ihre Breite (140 bis 320 px) laufend dem freien
Platz an, damit die erste Zeile nie über den Plotbereich hinausragt. Der Plotbereich gewinnt eine Zeile Höhe.

## Menüleiste und Hilfe-Fenster (ab 1.48.0)

Der Reiter "Hilfe" neben "Graph" entfällt; die Hilfe öffnet sich über Hilfe > Hilfe anzeigen in einem eigenen,
verschieb- und skalierbaren Fenster (Kreuz schließt es, beim Sprachwechsel bleibt es offen). Die Menüleiste ist
jetzt: Datei - Graph-Optionen (normaler Abstand) - Hilfe (doppelter Abstand) - ... - Sprache am rechten Rand.
Die Abstände werden laufend am tatsächlich gezeichneten Abstand Datei/Graph-Optionen nachgemessen und passen
sich so Schriftgröße, Sprache und Fensterbreite an.

## Wertanzeige ändert die YAML (ab 1.46.0)

Mit übernommener Konfiguration sind die Felder Y min, Y max und Zielzeit auch für Signale aus der YAML editierbar.
Änderungen gehen in den Mode (Grenzen je Signal, steps je Mode) statt in die manuellen Werte und wirken sofort;
"In YAML speichern" in der Kopfzeile der Wertanzeige schreibt sie in die geladene Datei zurück (`limitconfig.save`).
Beide Grenzen leer: das Signal ist nicht mehr konfiguriert und nutzt wieder die manuellen Werte.
Ab 1.46.1 gilt steps des gewählten Modes als Zielzeit für alle Signale der Wertanzeige (auch ohne YAML-Eintrag);
nur ein Mode ohne steps lässt die manuellen Zielzeiten gelten.
1.46.2: Felder werden je Tabellenzeile geführt (`limit_box_list`, `target_box_list`). Vorher überschrieben sich
die Felder gleichnamiger Signale aus mehreren Dateien im selben Graphen, sodass Zielzeit und YAML-Grenzen nicht in
jeder Zeile ankamen.

## steps als Schritte oder Zeit (ab 1.45.0)

steps je Mode (YAML und Grenzwert-Konfigurator): Zahl ohne Einheit = Schritte (Messpunkte), mit Einheiten = Zeit,
z. B. `7h 18m 26s`, `45m`, `90s`, `1d 2h`. Gespeichert wird Zeit als Text (`steps: 7h 18m 26s`), Schritte als Zahl.
Die frühere globale Auswahl "steps als" entfällt. Auch die manuelle Zielzeit versteht jetzt Sekunden (`90s`).

## Grenzwert-Konfigurator (ab 1.44.0)

Datei > "Grenzwert-Konfigurator...": Fenster zum Anlegen, Bearbeiten, Speichern (mit Dateinamen) und Laden einer
Grenzwert-Konfiguration. Die Tabelle listet alle Signale der geladenen Dateien (mit Datei, Daten-Min/-Max) und je
Mode die Felder aktiv, untere und obere Grenze; dazu steps des Modes. Modes lassen sich anlegen, kopieren,
umbenennen und löschen; "Grenzen aus Daten vorschlagen" setzt Min/Max ± Prozent der Spannweite. Das Fenster
bearbeitet direkt die geladene Konfiguration: Ist der Mode im Programm gewählt, wirken Änderungen sofort (Linien,
Wertanzeige, Prognose, Zielzeit, Detailfenster, Report). Speichern erhält andere Abschnitte der YAML und
deaktivierte Signale (`limitconfig.save`, `to_dict`).

## Grenzwert-Konfiguration (YAML) je Mode (ab 1.43.0)

Datei > "Grenzwert-Konfiguration laden (*.yaml)" liest `limits > modes > <Mode> > steps / signals > <Signal> >
enabled, lower, upper` (`messgraph/limitconfig.py`, PyYAML). Die Modes erscheinen in der Auswahl "Mode" in der
Kopfzeile der Wertanzeige. Zugeordnete Signale (Name genau, ohne Groß-/Kleinschreibung, ohne Einheit in Klammern) mit
`enabled: true` nutzen Grenzen und steps des Modes (Felder gesperrt); alle anderen Signale behalten die manuellen
Werte, ebenso ohne Konfiguration oder mit "(manuell)". steps ist eine Zahl (Schritte: Abstand bis zur Grenze
durch den Median-Messpunktabstand) oder eine Zeit mit Einheiten (`7h 18m 26s`, `45m`, `90s`; ab 1.45.0,
`limitconfig.parse_steps`). Konfiguration und Mode stehen in den Optionen von Ansicht und Projekt (`limit_config`,
`limit_mode`). Beispiel: `demo_data/demo_grenzen.yaml`.
Neue Abhängigkeit: `pyyaml` (requirements.txt).

## Regressionslinien im Graphen (ab 1.42.0)

Häkchen "Regressionslinien" (Werkzeugleiste und Detailfenster): je Signal die lineare Regressionsgerade über alle
Daten (dieselbe wie für Drift (Regression) und Prognose) als gestrichelte Linie in der Signalfarbe, an der Achse des
Signals. Die Striche entstehen über NaN-Lücken in einer Linie und werden beim Zoomen für den Ausschnitt neu
berechnet (`_poll_reg_dashes`). Druck, Export und Reports zeichnen sie gestrichelt (`PlotSpec.regressions`).
Gespeichert in den Einstellungen und als Option `regression_lines` in Ansicht und Projekt.

## Zielzeit je Signal (ab 1.41.0)

In der Wertanzeige steht neben Y max je Signal das Feld "Zielzeit" (Tage, Stunden, Minuten, z. B. `2d 6h 30m`;
`measure.parse_duration`). "Alle" überträgt die Zielzeit auf alle Signale. Mit aktiven Markern, gesetzter Grenze und
Zeitachse wird verglichen: Erreicht die Prognose die Grenze früher als die Zielzeit (oder ist sie schon
überschritten), wird die Tabellenzeile rot und der Graph schwach rot hinterlegt (`themes.alarm_row_bg`,
`themes.alarm_plot_bg`: je Farbschema abgestimmt, Kontrast der Linien mindestens 3:1). Das gilt auch im
Detailfenster, beim Drucken/Export (`PlotSpec.alarm`) und in beiden Reports (Spalten Zielzeit und Zielzeit-Status,
rote Zeilen über `GraphSection.alarm_keys`). Gespeichert als `graphs[].signals[].target` (Sekunden).

## Graph im Detailfenster (ab 1.40.0)

Doppelklick mit der linken Maustaste auf einen Graphen öffnet ihn groß in einem eigenen Fenster. Das Fenster zeigt
dasselbe `GraphSlot`-Objekt und wird mit derselben Aufbaufunktion (`_build_plot(..., zoom=True)`) erzeugt; alle
Funktionen, die über `_all_ui()` laufen (Marker, Grenzen, Legende, Farben, Kommentare samt Ziehen, Kontextmenü,
Drag and Drop, Schriftgröße, Farbschema), gelten damit in beiden Darstellungen. Zoom und Ausschnitt sind
unabhängig; Export und Report aus dem Detailfenster nutzen dessen Ausschnitt, "Alle Graphen" und die X-Kopplung
nur den Plotbereich. Leiste: Alles anzeigen, Marker, Marker synchron, Drucken/Export, Report, Schließen; mit Markern
eine eigene Wertanzeige. Doppelklick im Detailfenster passt ein (wie bisher mit Y-Rand).

1.40.1: Mit bereits aktiven Markern wurden die Kurven im Detailfenster nicht sichtbar (Markerlinien starteten bei
x = 0 und zogen beim Einpassen den Bereich auf, besonders mit Datumsachse). Markerlinien starten jetzt an der
gespeicherten Position bzw. im Datenbereich.

## Dynamische Hinweise in der Dateiliste (ab 1.38.0)

Der Hinweis unter einer Datei nennt nur Spalten, die in dieser Datei keinen einzigen Zahlenwert liefern
(`Dataset.extra["no_values"]`), und wird beim Anzeigen gebildet: Bei aktiver Signalsuche erscheinen nur passende
Namen, ohne Treffer entfällt der Hinweis; er folgt der eingestellten Sprache. Spalten, die nur zeitweise Werte haben
und sonst Platzhalter (x, -, n/a ...) enthalten, werden als Signal angeboten. Weitere Zeitspalten stehen in der
Erkennung statt im Hinweis. Bei MF4 mit Busrohdaten nennt der Hinweis die vorhandenen Rahmenkanäle statt eines
festen Beispiels und nach der Dekodierung die Zahl der dekodierten Signale.

## Farbschemata (ab 1.37.0)

"Darstellung" (dritte Zeile der Werkzeugleiste) bietet neben Dunkel und Hell sechs weitere Schemata: Solar dunkel,
Solar hell, Nord, Kontrast, Papier und Farbenblind (Okabe-Ito). Jedes Schema hat eigene Linien- und Markerfarben,
abgestimmt auf seinen Plothintergrund: Kontrast jeder Linie mindestens 3:1, Text mindestens 7:1, Linien untereinander
und gegenüber den Markern unterscheidbar (geprüft in `tests/test_gui_logic.py`). Definiert in `messgraph/themes.py`
(`_scheme` leitet die Flächen aus Hintergrund, Text und Akzent ab). Druck, Export und Report bleiben hell.

## Kommentarfelder per Rechtsklick (ab 1.36.0)

Rechtsklick auf eine Stelle im Graphen: Im Kontextmenü unter "Kommentar an der Klickstelle" Text eintragen und
"Kommentar einfügen". Der Kommentar wird an X-Wert und Wert der linken Y-Achse verankert, wandert beim Zoomen mit
und lässt sich im selben Menü ändern, an eine neue Klickstelle verschieben oder löschen. Ab 1.39.0 wird ein Kommentar
unter der Maus hervorgehoben und lässt sich mit gedrückter linker Maustaste frei verschieben (der Graph wird dabei
festgehalten). Kommentare werden in Ansicht
und Projekt gespeichert (`graphs[].comments`), bleiben beim Dateiwechsel erhalten und erscheinen in Druck, Export und
beiden Reports.

## Datei für die Graphen wählen, alle Plots löschen (ab 1.35.0)

Unter der Werkzeugleiste listet die Auswahl "Datei" alle geladenen Dateien. Eine Datei wählen stellt alle
vorhandenen Graphen auf die gleichnamigen Signale dieser Datei um; Signale der vorherigen Datei und Signale über
mehrere Dateien werden ersetzt. Matrix, Bereiche, Graphnamen, Farben, rechte Achse, Grenzen und Bemerkungen
bleiben, fehlende Signale nennt die Statuszeile. MF4-Kanäle werden vorher geladen. "Alle Plots löschen" leert den
Plotbereich: Graphen und Aufteilung (Matrix, Bereiche) werden entfernt, die Dateien bleiben geladen (ab 1.39.1). Das Kreuz zum Schließen einzelner Graphen (1.33.0) ist wieder
entfernt.

Ab 1.33.1 bleibt der Plotbereich ohne geladene Datei leer, auch bei eingestellter Matrix. Die Matrix bleibt
erhalten und wird mit der nächsten Datei aufgebaut; nach dem Schließen der letzten Datei ist der Bereich wieder leer.
