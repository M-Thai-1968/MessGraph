"""Dateivergleich: gleich oder ähnlich aufgebaute Dateien Signal für Signal als Tabelle (avg, min, max).

Ähnlichkeit = Anteil gemeinsamer Signalnamen (Jaccard). Kennwerte werden je Signal über die ganze Aufzeichnung
gebildet. MF4-Kanäle werden dafür in voller Auflösung über ihren Loader gelesen (ohne sie im Speicher zu
behalten); bei CSV und Parquet dienen die geladenen Daten. Wurden diese beim Einlesen reduziert (Downsampling),
wird der Wert markiert.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import progress
from .data_model import Channel, Dataset, LoadError
from .i18n import t

STATS = ["avg", "min", "max"]
STAT_NAMES = {"avg": "Mittelwert (avg)", "min": "Minimum (min)", "max": "Maximum (max)"}
SIMILAR = 0.5          # ab diesem Anteil gemeinsamer Signalnamen gelten Dateien als ähnlich


def names(dataset: Dataset) -> list[str]:
    return [c.name for c in dataset.channels]


def similarity(a: Dataset, b: Dataset) -> float:
    sa, sb = set(names(a)), set(names(b))
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def similar_groups(datasets: list[Dataset], threshold: float = SIMILAR) -> list[list[Dataset]]:
    """Gruppen ähnlicher Dateien (verbunden über paarweise Ähnlichkeit), größte zuerst; Einzeldateien entfallen."""
    parent = list(range(len(datasets)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(datasets)):
        for j in range(i + 1, len(datasets)):
            if similarity(datasets[i], datasets[j]) >= threshold:
                parent[root(j)] = root(i)
    groups: dict[int, list[Dataset]] = {}
    for i, ds in enumerate(datasets):
        groups.setdefault(root(i), []).append(ds)
    result = [g for g in groups.values() if len(g) > 1]
    return sorted(result, key=len, reverse=True)


def group_similarity(dataset: Dataset, group: list[Dataset]) -> float:
    others = [g for g in group if g is not dataset]
    return sum(similarity(dataset, o) for o in others) / len(others) if others else 1.0


def signal_union(datasets: list[Dataset]) -> list[tuple[str, int]]:
    """Alle Signalnamen in Reihenfolge des ersten Auftretens mit der Anzahl Dateien, die sie enthalten."""
    order: dict[str, int] = {}
    for ds in datasets:
        for name in dict.fromkeys(names(ds)):
            order[name] = order.get(name, 0) + 1
    return list(order.items())


def column_names(datasets: list[Dataset]) -> list[str]:
    """Spaltenköpfe: Dateiname, bei gleichen Namen mit Ordner davor."""
    plain = [ds.name for ds in datasets]
    return [f"{Path(ds.path).parent.name}/{ds.name}" if plain.count(ds.name) > 1 else ds.name for ds in datasets]


@dataclass
class Row:
    signal: str
    unit: str
    stat: str
    values: list[float | None]
    reduced: list[bool]


@dataclass
class CompareResult:
    files: list[str]
    stats: list[str]
    rows: list[Row] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def any_reduced(self) -> bool:
        return any(any(r.reduced) for r in self.rows)


def _samples(channel: Channel) -> tuple[np.ndarray, bool]:
    """(y, reduziert). Volle Auflösung, wo möglich, ohne den Kanal dauerhaft zu laden."""
    if channel.loaded and not channel.ds_note:
        return channel.y, False
    if channel.loader is not None:
        _x, y, _unit = channel.loader()
        return np.asarray(y, dtype=np.float64), False
    return channel.y, bool(channel.ds_note)


def statistics(y: np.ndarray) -> dict[str, float | None]:
    y = np.asarray(y, dtype=np.float64)
    ok = y[np.isfinite(y)]
    if ok.size == 0:
        return {s: None for s in STATS}
    return {"avg": float(ok.mean()), "min": float(ok.min()), "max": float(ok.max())}


def compute(datasets: list[Dataset], signals: list[str], stats: list[str]) -> CompareResult:
    """Läuft im Hintergrund (Fortschritt und Abbruch über progress)."""
    stats = [s for s in STATS if s in stats]
    result = CompareResult(files=column_names(datasets), stats=stats)
    lookup = [{c.name: c for c in reversed(ds.channels)} for ds in datasets]   # erster Kanal gleichen Namens
    total, done = max(1, len(signals) * len(datasets)), 0
    for name in signals:
        values = {s: [None] * len(datasets) for s in stats}
        reduced = [False] * len(datasets)
        units = []
        for i, channels in enumerate(lookup):
            progress.step(done / total, t("{signal} in {file}", signal=name, file=result.files[i]))
            done += 1
            channel = channels.get(name)
            if channel is None:
                continue
            if channel.unit and channel.unit not in units:
                units.append(channel.unit)
            try:
                y, reduced[i] = _samples(channel)
            except progress.Cancelled:
                raise
            except Exception as exc:  # ein unlesbarer Kanal soll den Vergleich nicht verhindern
                result.problems.append(f"{result.files[i]}: {name}: {exc}")
                continue
            for stat, value in statistics(y).items():
                if stat in values:
                    values[stat][i] = value
            del y
        for stat in stats:
            result.rows.append(Row(name, " / ".join(units), stat, values[stat], list(reduced)))
    progress.step(1.0)
    return result


def parse_percent(text) -> float | None:
    """Toleranz aus der Eingabe ("5", "2,5", "3 %"); leer oder ungültig = keine Prüfung."""
    try:
        value = float(str(text).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def deviations(values: list[float | None], percent: float | None) -> list[bool]:
    """Je Datei: weicht der Wert um mehr als percent % vom typischen Wert der übrigen Dateien ab?

    Bezug ist der Median aller gültigen Werte; so fällt ein Ausreißer auf, ohne die übrigen Dateien
    mitzuziehen. Bei genau zwei Werten ist der Bezug der jeweils andere Wert. Ist der Bezug 0, gilt jeder Wert
    ungleich 0 als Abweichung. Mit weniger als zwei gültigen Werten gibt es nichts zu vergleichen.
    """
    flags = [False] * len(values)
    if percent is None:
        return flags
    valid = [(i, v) for i, v in enumerate(values) if v is not None and math.isfinite(v)]
    if len(valid) < 2:
        return flags
    median = float(np.median([v for _, v in valid]))
    for i, v in valid:
        ref = (valid[1][1] if i == valid[0][0] else valid[0][1]) if len(valid) == 2 else median
        if ref == 0:
            flags[i] = v != 0
        else:
            flags[i] = abs(v - ref) / abs(ref) * 100.0 > percent + 1e-12
    return flags


def format_value(value: float | None, decimal: str = ".", digits: int = 6) -> str:
    if value is None or not math.isfinite(value):
        return ""
    text = f"{value:.{digits}g}"
    return text.replace(".", decimal) if decimal != "." else text


def to_text(result: CompareResult, sep: str = ";", decimal: str = ".", digits: int = 10,
            tolerances: dict | None = None) -> str:
    """Tabelle als CSV (sep=';') oder für die Zwischenablage (sep='\\t'); mit Toleranz und abweichenden Dateien."""
    tolerances = tolerances or {}
    head = [t("Signal"), t("Einheit"), t("Kennwert"), t("Toleranz %")] + result.files + [t("Abweichung")]
    lines = [sep.join(head)]
    for row in result.rows:
        percent = parse_percent(tolerances.get(row.signal, ""))
        flags = deviations(row.values, percent)
        cells = ([row.signal, row.unit, row.stat, "" if percent is None else format_value(percent, decimal)]
                 + [format_value(v, decimal, digits) + ("*" if red and v is not None else "")
                    for v, red in zip(row.values, row.reduced)]
                 + [", ".join(name for name, bad in zip(result.files, flags) if bad)])
        lines.append(sep.join(c.replace(sep, " ") for c in cells))
    if result.any_reduced:
        lines.append(t("* aus reduzierten Daten (Downsampling beim Einlesen)"))
    return "\n".join(lines) + "\n"


def write_csv(path: str, result: CompareResult, decimal: str = ",", tolerances: dict | None = None) -> str:
    if not path.lower().endswith(".csv"):
        path += ".csv"
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # utf-8-sig: Excel erkennt Umlaute und Thai
        Path(path).write_text(to_text(result, ";", decimal, tolerances=tolerances), encoding="utf-8-sig")
    except OSError as exc:
        raise LoadError(t("CSV nicht gespeichert: {error}", error=exc)) from exc
    return path
