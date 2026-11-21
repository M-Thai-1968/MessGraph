"""Anordnung vorschlagen: Signale nach Namen und Einheit gruppieren und eine Matrix daraus bilden.

Je Signal werden bestimmt
    System   erstes Namensteil, z. B. AC, HVDC, LVDC, Kl30, Chiller, DUT (aus "AC_V_L1", "HVDC_I_Set")
    Größe    Spannung, Strom, Leistung, Frequenz, Temperatur ... aus der Einheit, sonst aus Namensteilen
             (V/U = Spannung, I = Strom, P = Leistung, T/TS/Temp = Temperatur, F = Frequenz bei AC, sonst Durchfluss)
Ein Graph fasst gleiche Größe desselben Systems zusammen (Ist- und Sollwerte gemeinsam). Eine Zeile der
Matrix gehört einem System (AC: Spannung, Strom, Leistung, Frequenz nebeneinander). Temperaturen und
Zustände (Mode, Status) bekommen eigene Zeilen am Ende. Zeilen mit weniger Graphen als Spalten werden über
zusammengefasste Bereiche gefüllt, zu volle Graphen und Zeilen werden geteilt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .i18n import t
from .layout import MAX_GRAPHS

# Größe: (Schlüssel, Anzeigename, Einheiten, Namensteile)
QUANTITIES = [
    ("voltage", "Spannung", {"v", "mv", "kv", "uv"}, {"v", "u", "ub", "volt", "voltage", "spannung", "vdc", "vac"}),
    ("current", "Strom", {"a", "ma", "ka", "ua"}, {"i", "cur", "current", "curr", "strom", "amp"}),
    ("power", "Leistung", {"w", "kw", "mw", "va", "kva", "var", "kvar"}, {"p", "pwr", "power", "leistung"}),
    ("frequency", "Frequenz", {"hz", "khz", "mhz"}, {"freq", "frequency", "frequenz", "hz"}),
    ("temperature", "Temperatur", {"°c", "degc", "c", "k", "°f", "grad", "°"},
     {"t", "ts", "temp", "temperature", "temperatur", "tmp", "tc"}),
    ("humidity", "Feuchte", {"%rh", "%rf", "rh"}, {"h", "rh", "hum", "humidity", "feuchte"}),
    ("flow", "Durchfluss", {"l/min", "l/h", "m3/h", "m³/h", "lpm"}, {"flow", "durchfluss", "q"}),
    ("pressure", "Druck", {"bar", "mbar", "pa", "kpa", "hpa", "mpa", "psi"}, {"press", "pressure", "druck", "bar"}),
    ("speed", "Drehzahl", {"rpm", "1/min", "u/min"}, {"n", "rpm", "speed", "drehzahl"}),
    ("velocity", "Geschwindigkeit", {"km/h", "m/s", "mph"}, {"vel", "velocity", "geschwindigkeit", "kmh"}),
    ("energy", "Energie", {"wh", "kwh", "mwh", "j", "kj"}, {"e", "energy", "energie", "wh", "kwh"}),
    ("resistance", "Widerstand", {"ohm", "Ω", "mohm", "kohm"}, {"r", "res", "ohm", "widerstand"}),
    ("ratio", "Anteil", {"%"}, {"soc", "duty", "pct", "percent"}),
    ("state", "Zustand", set(), {"mode", "state", "status", "zustand", "flag", "stat", "step"}),
]
NAMES = {key: name for key, name, _u, _t in QUANTITIES}
ORDER = {key: i for i, (key, *_rest) in enumerate(QUANTITIES)}
AC_DOMAINS = {"ac", "grid", "v2l", "netz", "mains", "l1", "l2", "l3"}
SET_WORDS = {"set", "soll", "sp", "target", "ref", "cmd"}
OWN_ROWS = ("temperature", "state")        # Größen mit eigener Zeile über alle Systeme
OWN_TITLES = {"temperature": "Temperaturen", "state": "Zustände", None: "Sonstige"}


def tokens(name: str) -> list[str]:
    """Namensteile: Trennzeichen _ - . / Leerzeichen, dazu Wechsel klein->groß (CoverT -> Cover, T).

    Ziffern trennen nicht: Kl30, V2L und TS01 bleiben ein Teil.
    """
    out = []
    for part in re.split(r"[\s_\-./\\:\[\]()]+", name):
        out += [p for p in re.split(r"(?<=[a-z])(?=[A-Z])", part) if p]
    return out


def quantity_of(name: str, unit: str = "") -> str | None:
    unit = (unit or "").strip().lower().replace(" ", "")
    for key, _name, units, _words in QUANTITIES:
        if unit and unit in units:
            return key
    parts = [p.lower() for p in tokens(name)]
    domain = parts[0] if parts else ""
    for index, part in enumerate(parts):
        if index == 0 and len(parts) > 1 and part not in ("temp", "temperatur", "temperature", "spannung", "strom",
                                                          "leistung", "drehzahl", "druck"):
            continue                       # erstes Teil ist meist das System (AC, HVDC, DUT ...)
        if part == "f":                    # F: Frequenz am Netz, sonst Durchfluss
            return "frequency" if domain in AC_DOMAINS else "flow"
        for key, _name, _units, words in QUANTITIES:
            if part in words:
                return key
    return None


def domain_of(name: str) -> str:
    parts = tokens(name)
    return parts[0] if len(parts) > 1 else ""


def is_setpoint(name: str) -> bool:
    return any(p.lower() in SET_WORDS for p in tokens(name))


@dataclass
class Group:
    title: str
    row: str
    signals: list = field(default_factory=list)


@dataclass
class Proposal:
    matrix: tuple[int, int] | None
    spans: list | None
    groups: list                      # Group je Graph in Reihenfolge der Matrix
    rows: list                        # Zeilenname je Matrixzeile
    notes: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.groups)


def _widths(count: int, cols: int) -> list[int]:
    """count Graphen auf cols Spalten verteilen (vordere Graphen etwas breiter)."""
    base, extra = divmod(cols, count)
    return [base + (1 if i < extra else 0) for i in range(count)]


def propose(channels: list, max_curves: int = 8, max_cols: int = 4, own_rows: bool = True,
            coarse: bool = False) -> Proposal:
    """channels: Objekte mit name, unit (und optional label). Liefert Graphen und Matrix.

    coarse: Graphen je Größe über alle Systeme (wird selbst gewählt, wenn es sonst zu viele Graphen wären).
    """
    max_curves, max_cols = max(1, int(max_curves)), max(1, int(max_cols))
    rows: dict[str, dict[tuple, list]] = {}
    row_titles: dict[str, str] = {}
    for channel in channels:
        quantity = quantity_of(channel.name, getattr(channel, "unit", ""))
        domain = "" if coarse else domain_of(channel.name)     # grob: über alle Systeme nach Größe
        if (own_rows and quantity in OWN_ROWS) or quantity is None:
            row = f"~{quantity}"                         # eigene Zeile am Ende (auch: Größe unbekannt)
            row_titles[row] = t(OWN_TITLES[quantity])
            key = (domain, quantity) if quantity == "temperature" else ("", quantity or "")   # Zustände gemeinsam
        else:
            row = domain or (t(NAMES[quantity]) if coarse else t("Allgemein"))
            row_titles.setdefault(row, row)
            key = (domain, quantity or "")
        rows.setdefault(row, {}).setdefault(key, []).append(channel)
    order = [r for r in rows if not r.startswith("~")] + [f"~{q}" for q in OWN_ROWS + (None,) if f"~{q}" in rows]

    def title_for(domain, quantity, part, parts):
        name = t(NAMES[quantity]) if quantity else t("Sonstige")
        if quantity == "state" and not domain:
            name = t("Zustände")
        text = f"{domain} {name}".strip() if domain and quantity else name
        return text + (f" ({part}/{parts})" if parts > 1 else "")

    def build(curves: int):
        row_groups = []
        for row in order:
            graphs = []
            for (domain, quantity), members in sorted(rows[row].items(),
                                                     key=lambda kv: (ORDER.get(kv[0][1], 99), )):
                members = sorted(members, key=lambda c: (is_setpoint(c.name),))     # Istwerte vor Sollwerten
                members = sorted(members, key=lambda c: c.name) if quantity in OWN_ROWS else members
                chunks = [members[i:i + curves] for i in range(0, len(members), curves)]
                for part, chunk in enumerate(chunks, 1):
                    graphs.append(Group(title_for(domain, quantity, part, len(chunks)), row_titles[row], chunk))
            for start in range(0, len(graphs), max_cols):           # zu volle Zeilen teilen
                # eigene Zeilen: Temperaturen bleiben für sich, Zustände und Sonstige dürfen sich eine Zeile teilen
                kind = "temp" if row == "~temperature" else ("small" if row.startswith("~") else "")
                row_groups.append((row_titles[row], graphs[start:start + max_cols], kind))
        # kleine Zeilen nebeneinander legen (z. B. Chiller | Clnt | Chamber), eigene Zeilen bleiben für sich
        cols = min(max_cols, max(len(g) for _t, g, _o in row_groups)) if row_groups else 1
        packed = []
        for title, graphs, own in row_groups:
            if packed and own != "temp" and own == packed[-1][2] and len(packed[-1][1]) + len(graphs) <= cols \
                    and len(graphs) < cols and len(packed[-1][1]) < cols:
                last = packed[-1]
                packed[-1] = (f"{last[0]}, {title}", last[1] + graphs, own)
            else:
                packed.append((title, list(graphs), own))
        return [(title, graphs) for title, graphs, _own in packed]

    curves = max_curves
    row_groups = build(curves)
    notes = []
    while sum(len(g) for _r, g in row_groups) > MAX_GRAPHS and curves < 64:
        curves *= 2
        row_groups = build(curves)
    if curves != max_curves:
        notes.append(t("Höchstens {count} Graphen: bis zu {curves} Kurven je Graph.", count=MAX_GRAPHS, curves=curves))
    if sum(len(g) for _r, g in row_groups) > MAX_GRAPHS and not coarse:
        result = propose(channels, max_curves, max_cols, own_rows, coarse=True)   # je Größe über alle Systeme
        result.notes.insert(0, t("Sehr viele Systeme: Graphen je Größe über alle Systeme zusammengefasst."))
        return result
    kept, total = [], 0
    for title, graphs in row_groups:                   # notfalls ganze Zeilen bis zur Höchstzahl
        if total + len(graphs) > MAX_GRAPHS:
            notes.append(t("Zu viele Signale: nur die ersten {count} Graphen werden übernommen.", count=total))
            break
        kept.append((title, graphs))
        total += len(graphs)
    row_groups = kept
    if not row_groups:
        return Proposal(None, None, [], [], [t("Keine Signale für einen Vorschlag.")])
    cols = max(len(g) for _r, g in row_groups)
    groups, spans, names = [], [], []
    for title, graphs in row_groups:
        groups += graphs
        spans.append(_widths(len(graphs), cols))
        names.append(title)
    return Proposal((len(row_groups), cols), spans, groups, names, notes)
