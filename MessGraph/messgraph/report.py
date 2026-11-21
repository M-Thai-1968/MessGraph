"""Messbericht als PDF: Deckblatt, Inhaltsverzeichnis, Übersicht und je Graph Grafik und Tabellen."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .i18n import t
from .pdfdoc import PdfDocument
from .plotexport import ALARM_ROW_RGB, PlotSpec, page_size, render_plot


@dataclass
class GraphSection:
    title: str
    spec: PlotSpec
    tables: list = field(default_factory=list)    # (Überschrift, Kopfzeile, Zeilen)
    notes: list = field(default_factory=list)
    comment: str = ""                             # Bemerkung zu diesem Graphen
    row_keys: list = field(default_factory=list)  # je Tabelle die Signalkennung jeder Zeile (dynamischer Report)
    alarm_keys: set = field(default_factory=set)  # Signale mit verletzter Zielzeit: Zeilen rot hinterlegt


@dataclass
class ReportData:
    title: str
    author: str = ""
    comment: str = ""
    created: str = ""
    files: list = field(default_factory=list)       # (Datei, Ordner, Signale, Startzeit, Format)
    settings: list = field(default_factory=list)    # (Bezeichnung, Wert)
    graphs: list = field(default_factory=list)      # GraphSection


LEGEND_SIZE = 8.0
LEGEND_ROW = 11.5


def legend_columns(labels: list[str], width: float, measure, size: float = LEGEND_SIZE) -> int:
    """So viele Spalten (1 bis 3), wie die längste Beschriftung samt Farbmuster zulässt."""
    longest = max((measure(text, "F1", size) for text in labels), default=0) + 34
    return max(1, min(3, int(width // max(longest, 1)), len(labels)))


def _fit(text: str, width: float, measure, size: float) -> str:
    if measure(text, "F1", size) <= width:
        return text
    while text and measure(text + "...", "F1", size) > width:
        text = text[:-1]
    return text + "..."


def signal_legend(doc: PdfDocument, series: list) -> None:
    """Signalspiegel unter dem Graphen: Farbmuster und Bezeichnung, spaltenweise, über Seiten fortgesetzt."""
    if not series:
        return
    labels = [s.label + (t(" (rechte Achse)") if getattr(s, "right", False) else "") for s in series]
    doc.heading(t("Signalspiegel"))
    cols = legend_columns(labels, doc.content_w, doc.width)
    col_w = doc.content_w / cols
    rows = [list(range(i, min(i + cols, len(labels)))) for i in range(0, len(labels), cols)]
    start = 0
    while start < len(rows):
        fit = int(max(0.0, doc.available() - 6) // LEGEND_ROW)
        if fit < 1:
            doc.new_page()
            continue
        chunk = rows[start:start + fit]

        def draw(c, cw, ch, chunk=chunk):
            for r, row in enumerate(chunk):
                y = r * LEGEND_ROW + LEGEND_ROW * 0.75
                for k, index in enumerate(row):
                    x = k * col_w
                    rgb = series[index].rgb
                    c.line([(x + 1, y - 3), (x + 15, y - 3)], rgb, 2.2)
                    c.text(x + 20, y, _fit(labels[index], col_w - 26, doc.width, LEGEND_SIZE), LEGEND_SIZE)
        doc.drawing(len(chunk) * LEGEND_ROW, draw)
        start += len(chunk)


def build_report(path: str, data: ReportData, paper: str = "A4", font_path: str | None = None) -> str:
    w, h = page_size(paper, False)
    cover = []
    if data.author:
        cover.append(t("Erstellt von: {name}", name=data.author))
    cover.append(t("Erstellt am: {date}", date=data.created))
    cover.append(t("Dateien: {count}, Graphen: {graphs}", count=len(data.files), graphs=len(data.graphs)))
    cover += [f"  {row[0]}" for row in data.files[:12]]
    if len(data.files) > 12:
        cover.append(t("  ... und {count} weitere", count=len(data.files) - 12))
    doc = PdfDocument(data.title, t("Messbericht"), toc_title=t("Inhalt"), page_label=t("Seite"),
                      font_path=font_path, page_size=(w, h), cover_lines=cover)
    # Übersicht
    doc.chapter(t("Übersicht"))
    if data.comment:
        doc.heading(t("Bemerkung"))
        for part in data.comment.splitlines():
            if part.strip():
                doc.paragraph(part.strip())
    doc.heading(t("Messdateien"))
    doc.table([t("Datei"), t("Ordner"), t("Signale"), t("Startzeit"), t("Format")],
              [[str(v) for v in row] for row in data.files], weights=[2.2, 3.0, 0.8, 1.6, 1.0])
    if data.settings:
        doc.heading(t("Einstellungen"))
        doc.table([t("Einstellung"), t("Wert")], [[a, b] for a, b in data.settings], weights=[1.2, 3.0])
    doc.heading(t("Graphen"))
    doc.table(["#", t("Graph"), t("Signale")],
              [[str(i + 1), g.title, ", ".join(s.label for s in g.spec.series)] for i, g in enumerate(data.graphs)],
              weights=[0.3, 1.5, 4.0])
    # je Graph ein Kapitel
    for number, graph in enumerate(data.graphs, 1):
        doc.chapter(f"{number}  {graph.title}")
        height = min(doc.content_w * 0.62, (h - 160) * 0.55)
        plain = replace(graph.spec, legend="none")      # Legende nicht im Graphen, sondern als Signalspiegel darunter
        doc.drawing(height, lambda c, cw, ch, spec=plain: render_plot(c, spec, 0, 0, cw, ch, 8.0))
        signal_legend(doc, graph.spec.series)
        if graph.comment.strip():
            doc.heading(t("Bemerkung"))
            for part in graph.comment.splitlines():
                if part.strip():
                    doc.paragraph(part.strip())
        for index, (heading, headers, rows) in enumerate(graph.tables):
            if rows:
                doc.heading(heading)
                keys = graph.row_keys[index] if index < len(graph.row_keys) else []
                fills = [tuple(v / 255 for v in ALARM_ROW_RGB) if i < len(keys) and keys[i] in graph.alarm_keys
                         else None for i in range(len(rows))]
                doc.table(headers, rows, fills=fills if any(fills) else None)
        for note in graph.notes:
            doc.note(note)
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path
