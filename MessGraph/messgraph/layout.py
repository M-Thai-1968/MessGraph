"""Zuordnung der Signale zu den Graphen (n*m-Matrix oder untereinander).

In einer Matrix lassen sich Zeilen frei zusammenfassen: je Zeile die Breiten der Graphen in Spalten, z. B. bei
4*3 die Zeilen [1,1,1], [1,1,1], [2,1], [3] (Zeile 3: ein Graph über 2 Spalten und einer über 1, Zeile 4: ein
Graph über die ganze Breite). Kurzschreibweise im Matrixfeld: "4*3: 3, 3, 2+1, 1" - je Zeile entweder die
Anzahl gleich breiter Graphen (3 = drei Graphen, 1 = ein Graph über alle Spalten) oder die Breiten mit "+".
"""
from __future__ import annotations

import re

from .i18n import t
from dataclasses import dataclass, field

MAX_GRAPHS = 64


def parse_matrix(text: str) -> tuple[int, int] | None:
    """'2x3', '2*3', '2,3', '2 3' -> (2, 3). Leer -> None. Ungültig -> ValueError."""
    text = (text or "").strip().lower()
    if not text:
        return None
    m = re.fullmatch(r"(\d+)\s*(?:[x*×,;/]|\s)\s*(\d+)", text)
    if not m:
        raise ValueError(t("Matrix bitte als n*m angeben, zum Beispiel 2*3"))
    rows, cols = int(m.group(1)), int(m.group(2))
    if rows < 1 or cols < 1:
        raise ValueError(t("Zeilen und Spalten müssen mindestens 1 sein"))
    if rows * cols > MAX_GRAPHS:
        raise ValueError(t("Höchstens {count} Graphen möglich", count=MAX_GRAPHS))
    return rows, cols


def parse_row(text: str, cols: int) -> list[int]:
    """Eine Zeile: '3' = drei gleich breite Graphen, '2+1' = Breiten in Spalten. Leer = je Spalte ein Graph."""
    text = (text or "").strip()
    if not text:
        return [1] * cols
    if "+" in text:
        try:
            widths = [int(part) for part in text.split("+")]
        except ValueError:
            raise ValueError(t("Zeile \"{text}\": Breiten als Zahlen mit + angeben, z. B. 2+1", text=text)) from None
        if any(w < 1 for w in widths) or sum(widths) != cols:
            raise ValueError(t("Zeile \"{text}\": die Breiten müssen zusammen {cols} Spalten ergeben",
                               text=text, cols=cols))
        return widths
    try:
        count = int(text)
    except ValueError:
        raise ValueError(t("Zeile \"{text}\": Anzahl der Graphen (z. B. 3) oder Breiten mit + (z. B. 2+1) angeben",
                           text=text)) from None
    if count < 1 or count > cols or cols % count:
        raise ValueError(t("Zeile \"{text}\": {cols} Spalten lassen sich nicht in {count} gleich breite Graphen "
                           "teilen; Breiten mit + angeben, z. B. 2+1", text=text, cols=cols, count=count))
    return [cols // count] * count


def format_row(widths: list[int]) -> str:
    return str(len(widths)) if len(set(widths)) == 1 else "+".join(str(w) for w in widths)


def default_spans(matrix: tuple[int, int]) -> list[list[int]]:
    return [[1] * matrix[1] for _ in range(matrix[0])]


def parse_layout(text: str) -> tuple[tuple[int, int] | None, list[list[int]] | None]:
    """'4*3' oder '4*3: 3, 3, 2+1, 1' -> (Matrix, Zeilenbreiten oder None für lauter Einzelgraphen)."""
    head, _sep, rows_text = (text or "").partition(":")
    matrix = parse_matrix(head)
    if matrix is None:
        if rows_text.strip():
            raise ValueError(t("Matrix bitte als n*m angeben, zum Beispiel 2*3"))
        return None, None
    parts = [p for p in re.split(r"[;,|]", rows_text)] if rows_text.strip() else []
    if len(parts) > matrix[0]:
        raise ValueError(t("{count} Zeilenangaben, aber nur {rows} Zeilen", count=len(parts), rows=matrix[0]))
    spans = [parse_row(parts[r] if r < len(parts) else "", matrix[1]) for r in range(matrix[0])]
    return matrix, normalize_spans(matrix, spans)


def normalize_spans(matrix, spans) -> list[list[int]] | None:
    """Prüft die Zeilenbreiten; lauter Einzelgraphen -> None."""
    if not matrix or not spans:
        return None
    rows, cols = matrix
    if len(spans) != rows or any(sum(row) != cols or not row or min(row) < 1 for row in spans):
        return None
    spans = [[int(w) for w in row] for row in spans]
    return None if spans == default_spans(matrix) else spans


def format_layout(matrix, spans=None) -> str:
    if not matrix:
        return ""
    text = f"{matrix[0]}*{matrix[1]}"
    if spans:
        text += ": " + ", ".join(format_row(row) for row in spans)
    return text


@dataclass(eq=False)
class GraphSlot:
    signals: list = field(default_factory=list)
    cross: list = field(default_factory=lambda: [None, None])  # X-Position der Crosslines
    cross3: float | None = None                                 # X-Position von Marker 3 (Wertetabelle)
    title: str = ""                                             # eigener Name, leer = "Graph k"
    colors: dict = field(default_factory=dict)                  # Signal -> (r, g, b); fehlt = Standardfarbe
    right: set = field(default_factory=set)                     # Signale auf der rechten (sekundären) Y-Achse
    limits: dict = field(default_factory=dict)                  # Signal -> [Minimum, Maximum] (None = keine Grenze)
    targets: dict = field(default_factory=dict)                 # Signal -> Zielzeit in Sekunden (Prognose >= Ziel)
    note: str = ""                                              # Bemerkung für den Report
    legend: str | None = None                                   # Lage der Legende: nw, n, ne, sw, s, se (None = oben links)
    comments: list = field(default_factory=list)                # Kommentarfelder [x, y, Text]; x ohne Startzeit
    log_x: bool = False                                         # X-Achse logarithmisch (z. B. Spektrum)
    log_y: bool = False                                         # Y-Achsen logarithmisch

    def display_name(self, index: int) -> str:
        return self.title or t("Graph {number}", number=index + 1)


class PlotLayout:
    """Ohne Matrix: je ausgewähltes Signal ein eigener Graph, untereinander."""

    def __init__(self):
        self.matrix: tuple[int, int] | None = None
        self.spans: list[list[int]] | None = None     # je Zeile die Breiten der Graphen; None = Einzelgraphen
        self.slots: list[GraphSlot] = []

    def row_spans(self) -> list[list[int]]:
        """Breiten der Graphen je Zeile (ohne Matrix: je Graph eine Zeile)."""
        if not self.matrix:
            return [[1] for _ in self.slots]
        return self.spans or default_spans(self.matrix)

    def cells(self) -> list[tuple[int, int, int]]:
        """Je Graph (Zeile, erste Spalte, Breite in Spalten)."""
        out = []
        for row, widths in enumerate(self.row_spans()):
            col = 0
            for width in widths:
                out.append((row, col, width))
                col += width
        return out

    @property
    def merged(self) -> bool:
        return bool(self.matrix and self.spans)

    def grid(self) -> tuple[int, int]:
        return self.matrix if self.matrix else (len(self.slots), 1)

    def signals(self) -> list:
        return [s for slot in self.slots for s in slot.signals]

    def contains(self, signal) -> bool:
        return any(signal in slot.signals for slot in self.slots)

    def _auto_slot(self) -> GraphSlot:
        if not self.matrix:
            slot = GraphSlot()
            self.slots.append(slot)
            return slot
        return min(self.slots, key=lambda s: len(s.signals))  # min nimmt den ersten Treffer

    def add(self, signal, target: int | None = None) -> bool:
        """target: Index des Graphen; None füllt automatisch.

        Mit Ziel darf ein Signal zusätzlich in weiteren Graphen stehen, ohne Ziel nur einmal.
        Rückgabe False: Das Signal war dort schon vorhanden.
        """
        if target is not None and 0 <= target < len(self.slots):
            slot = self.slots[target]
            if signal in slot.signals:
                return False
            slot.signals.append(signal)
            return True
        if self.contains(signal):
            return False
        self._auto_slot().signals.append(signal)
        return True

    def remove_from(self, index: int, signal) -> None:
        """Signal nur aus einem Graphen entfernen."""
        slot = self.slots[index]
        if signal in slot.signals:
            slot.signals.remove(signal)
            slot.colors.pop(signal, None)
            slot.right.discard(signal)
            slot.limits.pop(signal, None)
            slot.targets.pop(signal, None)
        if not self.matrix and not slot.signals:
            del self.slots[index]

    def clear_slot(self, index: int) -> None:
        self.slots[index].signals.clear()
        self.slots[index].right.clear()
        self.slots[index].limits.clear()
        self.slots[index].targets.clear()
        if not self.matrix:
            del self.slots[index]

    def remove(self, signal) -> None:
        for slot in self.slots:
            if signal in slot.signals:
                slot.signals.remove(signal)
            slot.right.discard(signal)
            slot.limits.pop(signal, None)
            slot.targets.pop(signal, None)
        if not self.matrix:
            self.slots = [s for s in self.slots if s.signals]

    def clear(self) -> None:
        for sig in set(self.signals()):
            self.remove(sig)

    def set_matrix(self, matrix: tuple[int, int] | None, spans: list[list[int]] | None = None) -> None:
        """Neue Aufteilung (spans: Breiten je Zeile); bestehende Zuordnungen bleiben, soweit sie passen."""
        old = self.slots
        self.matrix = matrix
        self.spans = normalize_spans(matrix, spans)
        if matrix is None:
            kept = [s for s in old if s.signals]
            self.slots = kept
            return
        count = sum(len(row) for row in self.row_spans())
        self.slots = old[:count] + [GraphSlot() for _ in range(count - len(old))]
        for slot in old[count:]:
            for sig in slot.signals:
                self._auto_slot().signals.append(sig)

    def target_names(self) -> list[str]:
        """Einträge für die Auswahl 'Zielgraph'."""
        names = [t("Automatisch")]
        cells = self.cells()
        for i, slot in enumerate(self.slots):
            name = t("Graph {number}", number=i + 1)
            if self.matrix and i < len(cells):
                row, col, width = cells[i]
                columns = f"{col + 1}" if width == 1 else f"{col + 1}-{col + width}"
                name += f" (Z{row + 1}/S{columns})"
            if slot.title:
                name += f": {slot.title}"
            names.append(name)
        return names
