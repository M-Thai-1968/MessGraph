"""Auto-Auswertung: Verzeichnis zyklisch einlesen, Dateien je Gruppe nach Zeitstempel zusammenfassen,
Graphen als PNG ablegen und die Istwerte gegen die Grenzwert-Konfiguration als Time_counter.json bewerten.

Ablauf eines Zyklus (AutoEngine.run_cycle):
1. Verzeichnis durchsuchen (*.csv, *.asc, *.parquet, auf Wunsch mit Unterordnern). Nur neue oder geänderte Dateien
   (Änderungszeit/Größe) werden gelesen; bereits gelesene bleiben im Speicher (nur neue Daten ergänzen).
2. Dateien bilden Gruppen: gleicher Grundname (ohne angehängte Zähler/Zeitstempel, z. B. Messung_001 -> Messung,
   oder per regulärem Ausdruck) im selben Ordner und gleiche Signale. Innerhalb der Gruppe werden die Dateien nach
   dem Zeitstempel IN den Daten sortiert und aneinandergehängt (Überlappungen nur einmal).
3. Limiter (falls gesetzt) kürzt die Daten der Gruppe.
4. Je Mode der Grenzwert-Konfiguration: Zählen der Messpunkte, in denen alle Signale des Modes in ihren Grenzen
   liegen ("actual_count"); "actual" in der Einheit des Ziels (steps: Messpunkte, Zeit: Sekunden), dazu "steps"
   (Ziel) und "fulfillment_percent". Schlüssel: count_<Mode>_<Gruppe> (wie Time_counter.json).
5. Je Signal ein Einzelgraph mit allen Daten als PNG im Zielverzeichnis (Unterordner je Gruppe).

Zeitbudget: Ein Zyklus arbeitet höchstens budget Sekunden (Anteil der Zykluszeit). Was nicht mehr passt (weitere
Dateien, Bilder), wird auf die folgenden Zyklen verteilt; das steht im Ergebnis und im Log.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from . import limitconfig, limiter, loaders, pngexport, safewrite
from .data_model import LoadError
from .i18n import t
from .plotexport import PlotSpec, SeriesSpec, value_margin
from .timeparse import format_wallclock
from .measure import REG_METHODS, fmt, predict, regression

DATA_SUFFIXES = (".csv", ".asc", ".parquet")
LIGHT_SERIES = (0, 92, 190)
LIMIT_RGB = (190, 40, 30)
TREND_AHEAD = 0.2                  # Trendlinie und X-Achse 20 % über das Datenende hinaus
TREND_RGB = (225, 110, 0)          # Trendlinie (Regressionsgerade), gestrichelt, kräftig gegen die Messkurve
NAN = float("nan")
PNG_POINTS = 6000                  # so viele Punkte je Bild (Hüllkurve min/max, Spitzen bleiben sichtbar)
_TRAILING = re.compile(r"(?:[_\-. ]+(?:\d{8}(?:[T_\-]?\d{4,6})?|\d{4}-\d{2}-\d{2}(?:[T_ ]\d{2}[-:]?\d{2}(?:[-:]?\d{2})?)?"
                       r"|\d{1,6}|part\d+|teil\d+))+$", re.IGNORECASE)


@dataclass
class AutoSettings:
    source: str = ""
    target: str = ""
    cycle_s: float = 60.0
    recursive: bool = True
    group_regex: str = ""               # optional: Gruppe = Gruppe 1 (oder ganzer Treffer) im Dateinamen ohne Endung
    json_name: str = "Time_counter.json"
    png: bool = True
    png_size: tuple = (1600, 900)
    only_hits: bool = True              # Time_counter nur für Modes, in denen Messpunkte gezählt wurden
    mode: str = ""                      # Mode der Grenzwert-Konfiguration für alle Dateien des Quellordners
    one_group: bool = True              # alle Dateien des Quellordners gehören zu einer Auswertung
    budget_share: float = 0.7           # Anteil der Zykluszeit für die Arbeit eines Zyklus
    log_name: str = "MessGraph_Auto.log"
    folders: tuple = ()                 # nur diese Ordner lesen (je ohne Unterordner); leer = Quellordner
    exclude: tuple = ()                 # diese Dateien nicht lesen (absolute Pfade)
    files: tuple = ()                   # nur diese Dateien lesen (Mode aus Dateinamen: ein Ordner, mehrere Ziele)
    edge_count: bool = False            # Flanken Counter statt Time Counter
    edges: tuple = ()                   # Flankendefinitionen: {"signal", "upper" (Wert1), "lower" (Wert2), "n", "target"}
    edge_target: int | None = None      # Flankenzahl des Modes (Schritt 2), gilt für Flanken ohne eigenes Ziel
    no_eval: bool = False               # Zähler "Ignorieren": keine Bewertung (kein Zähler, keine Violation)

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "cycle_s": self.cycle_s, "recursive": self.recursive,
                "group_regex": self.group_regex, "json_name": self.json_name, "png": self.png, "only_hits": self.only_hits, "mode": self.mode, "one_group": self.one_group,
                "png_size": list(self.png_size), "folders": list(self.folders), "exclude": list(self.exclude),
                "files": list(self.files), "edge_count": self.edge_count,
                "edges": [dict(e) for e in self.edges], "edge_target": self.edge_target,
                "no_eval": self.no_eval}

    @classmethod
    def from_dict(cls, data: dict | None) -> "AutoSettings":
        data = data or {}
        s = cls()
        for key in ("source", "target", "group_regex", "json_name", "mode"):
            if isinstance(data.get(key), str):
                setattr(s, key, data[key])
        try:
            s.cycle_s = max(1.0, float(data.get("cycle_s", s.cycle_s)))
        except (TypeError, ValueError):
            pass
        s.recursive = bool(data.get("recursive", s.recursive))
        s.png = bool(data.get("png", s.png))
        s.only_hits = bool(data.get("only_hits", s.only_hits))
        s.one_group = bool(data.get("one_group", s.one_group))
        s.folders = tuple(str(x) for x in data.get("folders") or () if x)
        s.exclude = tuple(str(x) for x in data.get("exclude") or () if x)
        s.files = tuple(str(x) for x in data.get("files") or () if x)
        s.edge_count = bool(data.get("edge_count", False))
        s.no_eval = bool(data.get("no_eval", False))
        target = _num(data.get("edge_target"))
        s.edge_target = int(target) if target is not None and target >= 1 else None
        s.edges = tuple(e for e in (normalize_edge(x) for x in data.get("edges") or ()) if e is not None)
        size = data.get("png_size")
        if isinstance(size, (list, tuple)) and len(size) == 2:
            s.png_size = (int(size[0]), int(size[1]))
        return s


@dataclass
class FileData:
    path: str
    stamp: tuple                        # (Änderungszeit, Größe)
    group: tuple
    start: float                        # erster Zeitstempel (Wanduhr-Sekunden) oder Änderungszeit
    timed: bool                         # Zeitstempel in den Daten vorhanden
    signals: dict                       # Name -> (t, y)
    labels: dict                        # Name -> Anzeigename (mit Einheit)


@dataclass
class Group:
    key: tuple
    name: str
    files: dict = field(default_factory=dict)       # Pfad -> FileData
    dirty: bool = True                              # Daten geändert, Ausgaben (Bilder, Zähler) fehlen noch
    png_todo: list = field(default_factory=list)    # noch zu schreibende Bilder (verteilt auf mehrere Zyklen)
    merged: dict | None = None                      # Name -> (t, y) zusammengefasst und gekürzt
    labels: dict = field(default_factory=dict)
    counters: dict = field(default_factory=dict)


@dataclass
class CycleResult:
    started: float
    seconds: float = 0.0
    new_files: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    deferred_files: int = 0
    deferred_png: int = 0
    png_written: int = 0
    json_path: str | None = None
    counters: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    proposal: object = None                         # vorgeschlagene Grenzwert-Konfiguration (keine geladen)
    forced: bool = False                            # von Hand ausgelöst (Einen Zyklus jetzt ausführen)
    first: bool = False                             # erster Durchlauf: alle Dateien gelesen
    cancelled: bool = False

    @property
    def collision(self) -> bool:
        return bool(self.deferred_files or self.deferred_png)


EDGE_JSON = "Flanken_counter.json"   # Standardname der Ergebnisdatei im Flanken Counter


def _num(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        out = float(str(value).replace(",", ".")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def normalize_edge(data) -> dict | None:
    """Flankendefinition prüfen: Signal, Wert1 (oben) und/oder Wert2 (unten), n >= 1, Ziel (Anzahl) optional."""
    if not isinstance(data, dict) or not str(data.get("signal") or "").strip():
        return None
    upper, lower = _num(data.get("upper")), _num(data.get("lower"))
    try:
        n = max(1, int(float(str(data.get("n") or 1).replace(",", "."))))
    except (TypeError, ValueError):
        n = 1
    target = _num(data.get("target"))
    return {"signal": str(data["signal"]).strip(), "upper": upper, "lower": lower, "n": n,
            "target": int(target) if target is not None and target > 0 else None}


def count_edges(y: np.ndarray, level: float, n: int, above: bool = True) -> tuple[int, bool]:
    """Flankenzähler. above=True (Wert1): eine Flanke = Signal steigt über level, bleibt mindestens n Werte darüber
    und fällt danach für mindestens n Werte wieder darunter. above=False (Wert2): unter level, mindestens n Werte
    darunter, danach mindestens n Werte wieder darüber. Kürzere Ausreißer (weniger als n Werte) zählen nicht und
    unterbrechen keinen Zustand. Der Anfangszustand gilt ohne Mindestlänge; beginnt das Signal schon jenseits von
    level, fehlt das Übersteigen - dieser erste Abschnitt zählt nicht. Lücken (NaN) werden übersprungen.
    Liefert (Anzahl, offen): offen = Signal ist am Ende jenseits von level, die Rückkehr steht noch aus."""
    values = np.asarray(y, dtype=np.float64)
    values = values[np.isfinite(values)]
    if not values.size:
        return 0, False
    state = values > level if above else values < level
    change = np.flatnonzero(state[1:] != state[:-1]) + 1
    starts = np.concatenate(([0], change))
    lengths = np.diff(np.concatenate((starts, [state.size])))
    kinds = state[starts]
    current = bool(kinds[0])                           # Anfangszustand
    armed = False                                      # über level gestiegen (von unten kommend), n Werte gehalten
    count = 0
    n = max(1, int(n))
    for kind, length in zip(kinds[1:].tolist(), lengths[1:].tolist()):
        if length < n or kind == current:              # Ausreißer oder kein Wechsel
            continue
        if kind:                                       # Übersteigen bestätigt
            armed = True
        elif armed:                                    # Rückkehr bestätigt -> eine Flanke
            count += 1
            armed = False
        current = kind
    return count, bool(current and armed)


def edge_goals(counters: dict) -> list:
    """Flanken-Einträge einer Gruppe mit Ziel (Flankenzahl): Grundlage der Violation im Flanken Counter."""
    return [{"key": k, "signal": e.get("signal", ""), "actual": int(e.get("actual") or 0), "target": e["steps"],
             "duration_s": float(e.get("duration_s") or 0.0)}
            for k, e in (counters or {}).items() if e.get("counter") == "edges" and e.get("steps")]


def edge_violation(goal: dict, state: str, remaining: float | None) -> dict:
    """Violation im Flanken Counter: Wie viele Flanken sind bis zur Grenzverletzung zu erwarten (gezählte Flanken +
    Flankenrate * Zeit bis Violation)? Weniger als die Ziel-Flankenzahl = Violation. Grenze schon erreicht: gezählte
    Flanken gegen das Ziel. Trend läuft auf keine Grenze zu: unendlich viele, keine Violation."""
    actual, target = goal["actual"], goal["target"]
    rate = actual / goal["duration_s"] if goal.get("duration_s") else 0.0
    if state == "reached":
        at = float(actual)
    elif state in ("max", "min") and remaining is not None:
        at = actual + rate * float(remaining)
    else:
        at = None
    return dict(goal, rate_per_s=rate, at_violation=at, violated=at is not None and at < target)


def find_signal(signals: dict, name: str, labels: dict | None = None) -> str | None:
    """Signal zu einem Namen: genau, ohne Groß-/Kleinschreibung, ohne Einheit [..] oder über den Anzeigenamen."""
    if name in signals:
        return name
    key = name.casefold().strip()
    bare = re.sub(r"\s*\[[^\]]*\]\s*$", "", key)
    for candidate in signals:
        c = candidate.casefold()
        label = (labels or {}).get(candidate, candidate).casefold()
        if key in (c, label) or bare in (c, re.sub(r"\s*\[[^\]]*\]\s*$", "", c), label):
            return candidate
    return None


def evaluate_edges(signals: dict, edges, group: str, labels: dict | None = None,
                   default_target: int | None = None) -> tuple[dict, list]:
    """Flanken Counter: je Flankendefinition ein Eintrag edges_<Signal>_<Gruppe> über alle Daten der Gruppe. Ziel:
    das der Flanke, sonst die Flankenzahl des Modes (default_target), sonst keins (unendlich)."""
    out, notes = {}, []
    for edge in edges or ():
        edge = normalize_edge(edge)
        if edge is None or (edge["upper"] is None and edge["lower"] is None):
            continue
        name = find_signal(signals, edge["signal"], labels)
        if name is None:
            notes.append(t("{name}: Signal {signal} für den Flanken Counter nicht gefunden.", name=group,
                           signal=edge["signal"]))
            continue
        x, y = signals[name]
        dt = np.diff(np.asarray(x, dtype=np.float64)[np.isfinite(y)])
        dt = dt[np.isfinite(dt) & (dt > 0)]
        if dt.size:
            dt = np.minimum(dt, 5 * float(np.median(dt)))  # Lücken zwischen Dateien nicht mitzählen
        duration = float(dt.sum()) if dt.size else 0.0
        up, up_open = count_edges(y, edge["upper"], edge["n"], True) if edge["upper"] is not None else (0, False)
        down, down_open = count_edges(y, edge["lower"], edge["n"], False) if edge["lower"] is not None else (0, False)
        total = up + down
        steps = edge["target"] or default_target
        out[f"edges_{edge['signal']}_{group}"] = {
            "counter": "edges", "signal": name, "actual": total, "actual_count": total, "edges_upper": up,
            "edges_lower": down, "upper": edge["upper"], "lower": edge["lower"], "n": edge["n"],
            "pending": bool(up_open or down_open), "steps": steps, "duration_s": round(duration, 3),
            "fulfillment_percent": round(100.0 * total / steps, 1) if steps else None}
    return out, notes


# Prüfstandsdateien wie HTOE_PV_DES202609090470500176_AC_22kW_3ph_725V_DUT3: Gruppe = DES-Nummer und DUT
DES_DUT = r"(DES\d{6,}).*?_(DUT\d+)(?![A-Za-z0-9])"
# Seriennummer in Ordner- oder Dateinamen: 1-4 Großbuchstaben + mindestens 12 Ziffern (DES202507230117500132,
# DS202608200479700017). Ordner mit Seriennummer trennen bei "eine Auswertung je Quellordner" die Gruppen.
SERIAL = r"(?<![A-Za-z0-9])([A-Z]{1,4}\d{12,})(?!\d)"
# Ordnernamen ohne Aussage (taugen nicht als Gruppenname): eine Ebene höher suchen
GENERIC_DIRS = {"csv", "mf4", "mdf", "dat", "parquet", "asc", "blf", "data", "daten", "messdaten", "files", "file",
                "report", "reports", "raw", "export", "exports", "log", "logs", "result", "results", "files.csv",
                "_testresult", "test", "output", "input", "source", "quelle", "ziel"}


def serial_of(text: str) -> str:
    """Erste Seriennummer im Text (Ordnerpfad oder Dateiname), sonst ""."""
    match = re.search(SERIAL, text or "")
    return match.group(1) if match else ""


def meaningful_dir(path: str) -> str:
    """Name des Ordners; ist er nichtssagend (CSV, Files, Report ...), der nächste sinnvolle Ordner darüber."""
    for part in reversed(Path(path).parts):
        name = part.strip("\\/: ")
        if name and name.casefold() not in GENERIC_DIRS:
            return name
    return ""


def group_name(stem: str, pattern: str = "") -> str:
    """Gruppenname einer Datei. Reihenfolge: eigenes Muster (alle Gruppen mit _ verbunden, sonst der Treffer),
    DES-Nummer + DUT (DES202606090470000043_DUT2), sonst Dateiname ohne angehängte Zähler und Zeitstempel
    (Messung_001, Lauf-2026-06-09_1015 ...)."""
    for expr in ([pattern] if pattern else []) + [DES_DUT]:
        try:
            match = re.search(expr, stem)
        except re.error:
            match = None
        if match:
            parts = [g for g in match.groups() if g] if match.groups() else []
            name = "_".join(parts) if parts else match.group(0)
            if name.strip():
                return name.strip()
    name = _TRAILING.sub("", stem).strip(" _-.")
    return name or stem


# ---------------------------------------------------------------- Zeitstempel einer Datei finden
_STAMP_PATTERNS = [   # (Art, Ausdruck) - Reihenfolge = Vorrang innerhalb einer Zeile
    ("full", r"\d{4}[-./]\d{1,2}[-./]\d{1,2}[ T_]+\d{1,2}[:.]\d{2}(?:[:.]\d{2}(?:[.,]\d+)?)?"),
    ("full", r"\d{1,2}\.\d{1,2}\.\d{2,4}[ ,]+\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?"),
    ("full", r"\d{1,2}/\d{1,2}/\d{4}[ ,]+\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?(?:\s*[AaPp][Mm])?"),
    ("full", r"[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?(?:\s*[ap]m)?\s+\d{4}"),
    ("full", r"(?<!\d)\d{8}[_T ]?\d{6}(?!\d)"),
    ("date", r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\.\d{1,2}\.\d{4}|(?<!\d)20\d{6}(?!\d)"),
    ("clock", r"(?<![\d.:])\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?(?![\d:])"),
]
_EPOCH0 = datetime(1970, 1, 1)


def _wall(dt: datetime) -> float:
    """Wanduhr-Sekunden wie in timeparse (Uhrzeit wie in der Datei, ohne Zeitzone)."""
    return (dt - _EPOCH0).total_seconds()


def _parse_stamp(text: str, kind: str):
    """Text -> datetime (full/date) oder Sekunden ab Mitternacht (clock); None, wenn nicht lesbar."""
    text = re.sub(r"\s+", " ", text.strip())
    if kind == "clock":
        parts = re.split(r"[:]", text.replace(",", "."))
        try:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except (ValueError, IndexError):
            return None
    candidates = [text, text.replace(",", ".")]
    formats = ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S.%f",
               "%Y-%m-%dT%H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d_%H:%M:%S",
               "%d.%m.%Y %H:%M:%S.%f", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%y %H:%M:%S",
               "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M",
               "%a %b %d %H:%M:%S.%f %Y", "%a %b %d %H:%M:%S %Y", "%a %b %d %I:%M:%S.%f %p %Y", "%a %b %d %I:%M:%S %p %Y",
               "%Y%m%d%H%M%S", "%Y%m%d_%H%M%S", "%Y%m%dT%H%M%S", "%Y%m%d %H%M%S",
               "%Y-%m-%d", "%d.%m.%Y", "%Y%m%d"]
    for candidate in candidates:
        candidate = re.sub(r"(\.\d{6})\d+", r"\1", candidate)          # mehr als Mikrosekunden kürzen
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    return None


def find_stamps(line: str) -> dict:
    """Erster Zeitstempel je Art in einer Textzeile: {"full": datetime, "date": datetime, "clock": Sekunden}."""
    found = {}
    for kind, expr in _STAMP_PATTERNS:
        if kind in found:
            continue
        for match in re.finditer(expr, line):
            value = _parse_stamp(match.group(0), kind)
            if value is not None:
                found[kind] = value
                break
    return found


def _read_head(path: str, lines: int) -> list[str]:
    try:
        with open(path, "rb") as fh:
            raw = fh.read(256 * 1024)
    except OSError:
        return []
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return text.splitlines()[:lines]


def file_start(path: str, dataset, mtime: float, duration: float) -> tuple[float, str]:
    """Absolute Startzeit (Wanduhr-Sekunden) einer Datei ohne erkannte Datumsspalte, mit Herkunft.

    1. erste Datenzeile: Datum und Uhrzeit (der übliche Fall) oder nur Uhrzeit + Datum aus Vorspann/Dateiname,
    2. Vorspann über der Kopfzeile (z. B. "Start: 09.06.2026 10:00:00", "date Mon Jun 9 10:00:00 am 2026"),
    3. Datum und Uhrzeit im Dateinamen (..._20260609_101500),
    4. sonst Änderungszeit der Datei minus Messdauer (Hinweis im Log)."""
    info = dataset.extra.get("ascii") or {}
    header = info.get("header_line")
    data_line = info.get("data_line")
    head = _read_head(path, max(int(data_line or 0) + 3, 60)) if Path(path).suffix.lower() != ".parquet" else []
    first = {}
    if data_line and 0 < data_line <= len(head):
        first = find_stamps(head[data_line - 1])
    preamble = {}
    stop = (header - 1) if header else (data_line - 1 if data_line else len(head))
    for line in head[:max(0, stop)]:
        for kind, value in find_stamps(line).items():
            preamble.setdefault(kind, value)
    name = find_stamps(Path(path).stem)
    if "full" in first:
        return _wall(first["full"]), t("erste Datenzeile")
    date = preamble.get("full") or preamble.get("date") or name.get("full") or name.get("date")
    if "clock" in first and date is not None:
        midnight = datetime(date.year, date.month, date.day)
        return _wall(midnight) + first["clock"], t("Uhrzeit der ersten Datenzeile, Datum aus Vorspann/Dateiname")
    if "full" in preamble:
        return _wall(preamble["full"]), t("Vorspann")
    if "full" in name:
        return _wall(name["full"]), t("Dateiname")
    end = datetime.fromtimestamp(mtime)
    return _wall(end) - duration, t("Änderungszeit der Datei (kein Zeitstempel gefunden)")


def _envelope(x: np.ndarray, y: np.ndarray, points: int = PNG_POINTS) -> tuple[np.ndarray, np.ndarray]:
    """Für das Bild verkleinern: je Abschnitt Minimum und Maximum (Lücken/NaN bleiben erhalten)."""
    if x.size <= points:
        return x, y
    bins = points // 2
    edges = np.linspace(0, x.size, bins + 1).astype(int)
    xs, ys = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        seg = y[a:b]
        if b <= a:
            continue
        finite = np.isfinite(seg)
        if not finite.all():                      # Lücke im Abschnitt: als NaN-Punkt erhalten
            if finite.any():
                i, j = a + int(np.nanargmin(seg)), a + int(np.nanargmax(seg))
                for k in sorted({i, j}):
                    xs.append(x[k])
                    ys.append(y[k])
            xs.append(x[a + int(np.flatnonzero(~finite)[0])])
            ys.append(np.nan)
            continue
        i, j = a + int(seg.argmin()), a + int(seg.argmax())
        for k in sorted({i, j}):
            xs.append(x[k])
            ys.append(y[k])
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def _long_time(seconds: float) -> str:
    """Zeit als "13d 6h 21m 15s" (ab einem Tag mit Tagen)."""
    if seconds is None or not math.isfinite(seconds):
        return "-"
    days, rest = divmod(int(round(seconds)), 86400)
    return ((f"{days}d " if days else "") + (limitconfig.format_time(rest) if rest or not days else "")).strip()


def _safe(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE).strip("_") or "signal"


class AutoEngine:
    def __init__(self, settings: AutoSettings):
        self.settings = settings
        self.groups: dict[tuple, Group] = {}
        self.files: dict[str, tuple] = {}            # Pfad -> Gruppenschlüssel (gelesene Dateien)
        self.failed: dict[str, tuple] = {}           # Pfad -> stamp, Fehler (nicht jeden Zyklus neu versuchen)
        self.pending: list[str] = []
        self.cycles = 0
        self.reg_method = "ols"
        self.cancel = False                          # Abbrechen angefordert (laufender Zyklus/Analyse hört auf)
        self.progress = {"phase": "", "done": 0, "total": 0, "name": ""}

    def _step(self, phase: str, done: int, total: int, name: str = "") -> None:
        """Fortschritt für die Anzeige (wird aus dem Arbeits-Thread geschrieben, vom Programm nur gelesen)."""
        self.progress = {"phase": phase, "done": done, "total": total, "name": name}

    # ---------------------------------------------------------------- Log
    def log_path(self) -> Path:
        base = self.settings.target or self.settings.source or "."
        return Path(base) / self.settings.log_name

    def log(self, text: str) -> None:
        try:
            path = self.log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {text}\n")
        except OSError:
            pass

    # ---------------------------------------------------------------- Dateien
    def _walk(self):
        """Dateien der Auswertung: die Ordner der Verzeichnisregel (je ohne Unterordner) oder der Quellordner."""
        if self.settings.files:                       # feste Dateiliste der Verzeichnisregel
            paths = [Path(f) for f in self.settings.files]
            if not any(p.parent.is_dir() for p in paths):
                raise LoadError(t("Quellverzeichnis nicht gefunden: {path}", path=str(paths[0].parent)))
            yield from (p for p in paths if p.is_file())
            return
        folders = [Path(f) for f in self.settings.folders]
        if folders:
            existing = [f for f in folders if f.is_dir()]
            if not existing:
                raise LoadError(t("Quellverzeichnis nicht gefunden: {path}", path=", ".join(map(str, folders[:3]))))
            for folder in existing:
                yield from folder.glob("*")
            return
        root = Path(self.settings.source)
        if not root.is_dir():
            raise LoadError(t("Quellverzeichnis nicht gefunden: {path}", path=self.settings.source))
        yield from (root.rglob("*") if self.settings.recursive else root.glob("*"))

    def scan(self) -> dict[str, tuple]:
        target = Path(self.settings.target).resolve() if self.settings.target else None
        excluded = {os.path.normcase(os.path.abspath(p)) for p in self.settings.exclude}
        found = {}
        for path in self._walk():
            if excluded and os.path.normcase(os.path.abspath(str(path))) in excluded:
                continue                                   # im Verzeichnisverwalter abgewählt
            if path.suffix.lower() not in DATA_SUFFIXES or not path.is_file():
                continue
            if target is not None and target in path.resolve().parents:
                continue                                   # eigene Ausgaben nicht wieder einlesen
            try:
                st = path.stat()
            except OSError:
                continue
            found[str(path)] = (st.st_mtime, st.st_size)
        return found

    def _read(self, path: str, stamp: tuple) -> FileData:
        """Datei lesen (Kopfzeile, Spalten und Zeitspalte erkennt der normale Leser) und alle Signale auf absolute
        Zeit bringen: Datumsspalte, sonst Zeitstempel aus erster Datenzeile, Vorspann oder Dateiname."""
        dataset = loaders.load_file(path)
        try:
            signals, labels, epoch_found = {}, {}, False
            for channel in dataset.channels:
                if not channel.loaded:
                    channel.load()
                if channel.x is None or channel.y is None or channel.x.size == 0:
                    continue
                y = np.asarray(channel.y)
                if y.dtype.kind not in "fiub":
                    continue
                x = np.asarray(channel.x, dtype=np.float64)
                if channel.x_epoch is not None:
                    x = x + float(channel.x_epoch)
                    epoch_found = True
                signals[channel.name] = (x, y.astype(np.float64))
                labels[channel.name] = channel.label
            if not signals:
                raise LoadError(t("Keine Zahlenwerte gefunden."))
            source = t("Datumsspalte")
            if not epoch_found:                               # relative Zeit: Startzeitpunkt suchen
                x0 = min(float(x[0]) for x, _y in signals.values())
                x1 = max(float(x[-1]) for x, _y in signals.values())
                start, source = file_start(path, dataset, stamp[0], x1 - x0)
                signals = {n: (x - x0 + start, y) for n, (x, y) in signals.items()}
        finally:
            dataset.close()
        start = min(float(x[0]) for x, _y in signals.values())
        rel = os.path.relpath(os.path.dirname(path), self.settings.source)
        if self.settings.one_group:                           # alle Dateien des Quellordners = eine Auswertung ...
            serial = serial_of(rel.replace("\\", "/")) if rel not in (".", "") else ""
            key = ("*", serial) if serial else ("*",)         # ... aber je Seriennummer-Ordner eine eigene Gruppe
        else:
            key = (rel, group_name(Path(path).stem, self.settings.group_regex), tuple(sorted(signals)))
        data = FileData(path, stamp, key, start, True, signals, labels)
        data.time_source = source
        data.time_guess = source == t("Änderungszeit der Datei (kein Zeitstempel gefunden)")
        return data

    def _single_name(self, key: tuple = ("*",)) -> str:
        """Name einer Gruppe "eine Auswertung je Quellordner": DES-Nummer + DUT bzw. eigenes Muster aus den
        Dateinamen; sonst die Seriennummer (Ordner, dann Dateinamen); sonst gemeinsamer Grundname; zuletzt ein
        aussagekräftiger Ordnername (nicht CSV, Files, Report ...)."""
        group = self.groups.get(key)
        files = list(group.files) if group is not None else [p for g in self.groups.values() for p in g.files]
        names = sorted(Path(p).stem for p in files)
        if len(key) > 1 and key[1]:
            counts = {}
            for stem in names:                                # DUT-Nummer zur Ordner-Seriennummer
                match = re.search(DES_DUT, stem)
                if match and match.group(1) == key[1]:
                    found = f"{match.group(1)}_{match.group(2)}"
                    counts[found] = counts.get(found, 0) + 1
            return max(counts, key=lambda k: (counts[k], k)) if counts else key[1]
        counts = {}
        for stem in names:
            if self.settings.group_regex or re.search(DES_DUT, stem):
                found = group_name(stem, self.settings.group_regex)
                counts[found] = counts.get(found, 0) + 1
        if counts:
            return max(counts, key=lambda k: (counts[k], k))
        serials = {serial_of(stem) for stem in names} - {""}
        if len(serials) == 1:                                 # ..._DS202608200479700017_2026_11_06_... -> Seriennummer
            return next(iter(serials))
        bases = {group_name(stem) for stem in names}
        if len(bases) == 1:                                   # Messung_001, Messung_002 ... -> Messung
            return next(iter(bases))
        return _safe(meaningful_dir(os.path.abspath(self.settings.source)) or "Auswertung")

    def _group_label(self, key: tuple) -> str:
        """Name der Gruppe für Schlüssel und Ordner; gleiche Grundnamen mit anderen Signalen/Ordnern: _2, _3 ..."""
        if key[0] == "*":
            return self._single_name(key)
        used = {g.name for g in self.groups.values() if g.key != key}
        label, number = key[1], 1
        while label in used:
            number += 1
            label = f"{key[1]}_{number}"
        return label

    # ---------------------------------------------------------------- Zusammenfassen
    @staticmethod
    def merge(group: Group) -> tuple[dict, dict, list]:
        """Dateien der Gruppe nach Zeitstempel sortiert aneinanderhängen; ohne Zeitstempel nach Änderungszeit."""
        files = sorted(group.files.values(), key=lambda f: (f.start, f.path))
        notes = []
        guessed = [Path(f.path).name for f in files if getattr(f, "time_guess", False)]
        if guessed:
            notes.append(t("{name}: ohne Zeitstempel, nach Änderungszeit eingereiht: {files}", name=group.name,
                           files=", ".join(guessed)))
        merged, labels = {}, {}
        offset = 0.0
        for f in files:
            shift = 0.0
            if not f.timed:                                 # relative Zeit: an das Ende der vorigen Datei
                shift = offset
            ends = []
            for name, (x, y) in f.signals.items():
                labels.setdefault(name, f.labels.get(name, name))
                x = x + shift
                ends.append(float(x[-1]) if x.size else shift)
                if name in merged:
                    px, py = merged[name]
                    last = px[-1][-1] if px and px[-1].size else -math.inf
                    keep = x > last                         # Überlappung nur einmal
                    if keep.any():
                        if not keep.all():
                            x, y = x[keep], y[keep]
                        if px and x.size and x[0] - last > 0 and math.isfinite(last):
                            step = np.median(np.diff(x)) if x.size > 1 else 0
                            if step > 0 and x[0] - last > 5 * step:      # Lücke zwischen Dateien: Linie trennen
                                px.append(np.array([(last + x[0]) / 2]))
                                py.append(np.array([np.nan]))
                        px.append(x)
                        py.append(y)
                else:
                    merged[name] = ([x], [y])
            if ends:
                step = 0.0
                some = next(iter(f.signals.values()))[0]
                if some.size > 1:
                    step = float(np.median(np.diff(some)))
                offset = max(ends) + step
        out = {name: (np.concatenate(px), np.concatenate(py)) for name, (px, py) in merged.items()}
        return out, labels, notes

    # ---------------------------------------------------------------- Bewertung
    @staticmethod
    def evaluate(signals: dict, config, group: str, only_hits: bool = False, mode_name: str | None = None) -> tuple[dict, list]:
        """Time_counter-Einträge je Mode: Messpunkte, in denen alle Signale des Modes in ihren Grenzen liegen."""
        out, notes = {}, []
        if config is None:
            return out, notes
        modes = [config.modes[mode_name]] if mode_name in config.modes else list(config.modes.values())
        for mode in modes:
            guides = []
            for name, (x, y) in signals.items():
                found = mode.lookup(name)
                if found is None:
                    continue
                lo, hi = found
                guides.append((x, limiter.mask(y, lo, hi)))
            if not guides:
                continue
            base = max((g[0] for g in guides), key=lambda a: a.size)
            ok = np.ones(base.shape, dtype=bool)
            for x, m in guides:
                ok &= limiter.held(x, m, base)
            ok &= np.isfinite(base)
            count = int(ok.sum())
            if only_hits and count == 0:
                continue
            target = mode.target
            if target and target[0] == "s":
                dt = np.diff(base)
                step = float(np.median(dt)) if dt.size else 0.0
                dt = np.minimum(dt, 5 * step) if step > 0 else dt   # Lücken zwischen Dateien nicht mitzählen
                actual = float(dt[ok[:-1] & ok[1:]].sum()) if dt.size else 0.0
                actual = round(actual, 1)
            else:
                actual = count
            steps = target[1] if target else None
            entry = {"actual": actual, "actual_count": count,
                     "steps": (int(steps) if steps is not None and float(steps).is_integer() else steps),
                     "fulfillment_percent": (round(100.0 * actual / steps, 1) if steps else None)}
            out[f"count_{mode.name}_{group}"] = entry
        if config.modes and not out and not only_hits:
            notes.append(t("{name}: kein Mode der Grenzwert-Konfiguration passt zu den Signalen.", name=group))
        return out, notes

    @staticmethod
    def propose(signals: dict, labels: dict, name: str = "Auto", target: str = "24h") -> "limitconfig.LimitConfig":
        """Grenzwert-Konfiguration aus zusammengefassten Daten vorschlagen (wie propose_from_stats)."""
        return AutoEngine.propose_from_stats({n: {"values": y} for n, (_x, y) in signals.items()}, name, target)

    # ---------------------------------------------------------------- Bilder
    def assess(self, x: np.ndarray, y: np.ndarray, mode, name: str, edge_goals=None) -> dict:
        """Bewertung eines Signals wie in der Wertanzeige: Grenzen und Zielzeit aus dem Mode, Regressionsgerade
        (gewählte Art), Zeit bis zur Grenzverletzung ab dem letzten Messpunkt, verletzt = früher als die Zielzeit."""
        out = {"lo": None, "hi": None, "m": NAN, "b": NAN, "x0": float(x[0]) if x.size else 0.0, "target": None,
               "remaining": None, "remaining_steps": None, "state": "none", "violated": False, "peak": False}
        found = mode.lookup(name) if mode is not None else None
        if found:
            out["lo"], out["hi"] = found
            values = np.asarray(y, dtype=np.float64)
            values = values[np.isfinite(values)]                # Peaks: ein Messwert außerhalb der Grenzen
            out["peak"] = bool(values.size and ((out["lo"] is not None and values.min() < out["lo"]) or
                                                (out["hi"] is not None and values.max() > out["hi"])))
        m, b = regression(x, y, self.reg_method)
        out["m"], out["b"] = m, b
        out["target"] = mode.target if mode is not None else None
        ok = np.flatnonzero(np.isfinite(y))
        if not ok.size or (out["lo"] is None and out["hi"] is None):
            return out
        p = predict(m, float(y[ok[-1]]), out["lo"], out["hi"])
        out["edge_goals"] = []
        dt = np.diff(x[np.isfinite(x)])
        step = float(np.median(dt)) if dt.size else NAN
        if p.kind == "reached":
            out.update(state="reached", remaining=0.0, remaining_steps=0.0, violated=out["target"] is not None)
        elif p.kind in ("max", "min"):
            out.update(state=p.kind, remaining=float(p.x2),
                       remaining_steps=float(p.x2 / step) if step and math.isfinite(step) and step > 0 else None)
            target = out["target"]
            if target is not None:
                value = out["remaining_steps"] if target[0] == "steps" else out["remaining"]
                out["violated"] = value is not None and value < target[1]
        else:
            out["state"] = p.kind                       # inside: Trend läuft nicht auf eine Grenze zu
        if edge_goals:                                  # Flanken Counter: Violation gegen die Ziel-Flankenzahl
            out["edge_goals"] = [edge_violation(goal, out["state"], out["remaining"]) for goal in edge_goals]
            out["violated"] = any(g["violated"] for g in out["edge_goals"])
        return out

    @staticmethod
    def background(a: dict) -> tuple | None:
        """Hintergrund des Graphen: Regression verletzt Zielzeit = hellrot, Peaks außerhalb der Grenzen = hellgelb,
        beides = hellviolett, sonst weiß (None)."""
        from .plotexport import ALARM_PLOT_RGB, BOTH_PLOT_RGB, PEAK_PLOT_RGB
        if a.get("violated") and a.get("peak"):
            return BOTH_PLOT_RGB
        if a.get("peak"):
            return PEAK_PLOT_RGB
        return ALARM_PLOT_RGB if a.get("violated") else None

    def _info_lines(self, label: str, a: dict, unit: str) -> list:
        """Textblock rechts neben dem Graphen."""
        def num(v):
            return "-" if v is None or not math.isfinite(v) else fmt(v)
        number = list(REG_METHODS).index(self.reg_method) + 1 if self.reg_method in REG_METHODS else 1
        b_rel = a["m"] * a["x0"] + a["b"] if math.isfinite(a["m"]) else NAN     # b bezogen auf x = 0 am Start
        lines = [(t("Signal: {name}", name=label), None, True),
                 (t("Limit_max: {value}", value=num(a["hi"])), LIMIT_RGB, False),
                 (t("Limit_min: {value}", value=num(a["lo"])), LIMIT_RGB, False), ("", None, False),
                 (t("Trendlinie (gestrichelt): Regression ({n})", n=number), TREND_RGB, False),
                 (t(REG_METHODS.get(self.reg_method, "")), None, False),
                 (f"m = {num(a['m'])} {unit + '/s' if unit else '1/s'}", None, False),
                 (f"b = {num(b_rel)} {unit}".rstrip(), None, False),
                 (f"f(x) = {num(a['m'])} * x + {num(b_rel)}", None, False),
                 (t("x: Sekunden ab {start}", start=format_wallclock(a["x0"])[:19]), None, False), ("", None, False)]
        target = a["target"]
        goals = a.get("edge_goals") or []
        if goals:
            for g in goals:
                lines.append((t("Ziel: {target} Flanken ({signal}, gezählt {actual})", target=g["target"],
                                signal=g["signal"], actual=g["actual"]), None, False))
        elif target is None:
            lines.append((t("Zielzeit: unendlich (keine Violation möglich)"), None, False))
        elif target[0] == "steps":
            lines.append((t("Zielzeit: {steps} Schritte", steps=f"{target[1]:g}"), None, False))
        else:
            lines.append((t("Zielzeit: {time}", time=limitconfig.format_time(target[1])), None, False))
        if a["state"] == "reached":
            violation = t("Grenze bereits erreicht")
        elif a["remaining"] is None:
            violation = t("keine (Trend nicht in Richtung einer Grenze)") if a["state"] == "inside" else "-"
        else:
            violation = _long_time(a["remaining"])
            if a["remaining_steps"] is not None and target is not None and target[0] == "steps":
                violation += t(" ({steps} Schritte)", steps=f"{a['remaining_steps']:.0f}")
        lines.append((t("Zeit bis Violation: {time}", time=violation), None, False))
        for g in goals:
            at = g["at_violation"]
            lines.append((t("Flanken bis Violation: {count}", count=t("unendlich") if at is None else f"{at:.0f}"),
                          None, False))
        if a.get("peak"):
            lines.append((t("Peaks außerhalb der Grenzen!"), (150, 110, 0), True))
        if goals:
            if a["violated"]:
                lines.append((t("Violation vor Ziel-Flankenzahl!"), LIMIT_RGB, True))
            elif a["state"] != "none":
                lines.append((t("Keine Violation vor Ziel-Flankenzahl (OK)"), (20, 125, 70), True))
        elif a["violated"]:
            lines.append((t("Violation vor Zielzeit!"), LIMIT_RGB, True))
        elif target is not None and a["state"] != "none":
            lines.append((t("Keine Violation vor Zielzeit (OK)"), (20, 125, 70), True))
        return lines

    def _png(self, group: Group, name: str, labels: dict, config, mode_name: str | None) -> str | None:
        x, y = group.merged[name]
        finite = np.isfinite(y)
        if not finite.any():
            return None
        px, py = _envelope(x, y)
        lo, hi = float(np.nanmin(y)), float(np.nanmax(y))
        mode = None
        if config is not None and config.modes:
            mode = config.modes.get(mode_name) if mode_name in config.modes else next(iter(config.modes.values()))
        a = self.assess(x, y, mode, name, self._edge_goals(group))
        limits, extra = [], []
        for value in (a["hi"], a["lo"]):
            if value is not None:
                limits.append((value, LIMIT_RGB, False))
                extra.append(value)
        label = labels.get(name, name)
        unit = label[len(name):].strip(" []") if label.startswith(name) else ""
        regressions = []
        span = float(x[-1] - x[0]) if x[-1] > x[0] else 1.0
        x_end = float(x[-1]) + TREND_AHEAD * span                 # Trend etwas über die Daten hinaus (Prognose)
        if math.isfinite(a["m"]) and math.isfinite(a["b"]):
            x_a, x_b = float(x[0]), x_end
            regressions.append((x_a, a["m"] * x_a + a["b"], x_b, a["m"] * x_b + a["b"], TREND_RGB, False, ""))
            extra += [a["m"] * x_a + a["b"], a["m"] * x_b + a["b"]]
        ylo, yhi = value_margin(min([lo] + extra), max([hi] + extra))
        timed = all(f.timed for f in group.files.values())
        spec = PlotSpec(title=f"{group.name}: {label}", xlim=(float(x[0]), x_end),
                        ylim=(ylo, yhi), series=[SeriesSpec(label, px, py, LIGHT_SERIES)], limits=limits,
                        xlabel=t("Zeit") if timed else t("Zeit [s]"), time_axis=timed, legend="none",
                        regressions=regressions, alarm=a["violated"], alarm_rgb=self.background(a),
                        info=self._info_lines(label, a, unit))
        folder = Path(self.settings.target) / _safe(group.name)
        if pngexport.available():
            return pngexport.write_png(str(folder / f"{_safe(label)}.png"), spec, *self.settings.png_size)
        from .plotexport import SvgCanvas, render_plot
        w, h = self.settings.png_size[0] / 2, self.settings.png_size[1] / 2
        canvas = SvgCanvas(w, h)
        render_plot(canvas, spec, 10, 6, w - 20, h - 12, 9.0)
        path = folder / f"{_safe(label)}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(canvas.to_svg(), encoding="utf-8")
        return str(path)

    def _edge_goals(self, group: Group) -> list:
        return edge_goals(group.counters) if self.settings.edge_count else []

    # ---------------------------------------------------------------- Statistik für den Report
    STATS_NAME = "statistics.json"

    def write_statistics(self, group: Group, config, mode_name: str | None) -> str:
        """Je Auswertungsgruppe: Kennwerte je Signal (Min, Max, Mittelwert, Standardabweichung, Grenzen, Bewertung)
        und Name des PNG - Grundlage des Reports (Auto > Report erstellen)."""
        mode = None
        if config is not None and config.modes:
            mode = config.modes.get(mode_name) if mode_name in config.modes else next(iter(config.modes.values()))
        signals = {}
        goals = self._edge_goals(group)
        for g in goals:                                   # neu bewerten
            entry = group.counters.get(g["key"], {})
            entry.update(violation=False, edges_to_violation=None, violation_signal=None)
        for name, (x, y) in (group.merged or {}).items():
            finite = y[np.isfinite(y)]
            label = group.labels.get(name, name)
            a = self.assess(x, y, mode, name, goals) if finite.size else {"lo": None, "hi": None, "violated": False,
                                                                           "remaining": None, "m": NAN}
            for g in a.get("edge_goals") or []:          # Ergebnis je Flanken-Eintrag: frühste Violation
                entry = group.counters.get(g["key"])
                if entry is None:
                    continue
                at = g["at_violation"]
                if at is not None and (entry.get("edges_to_violation") is None or at < entry["edges_to_violation"]):
                    entry["edges_to_violation"] = round(at, 1)
                    entry["violation_signal"] = name
                entry["violation"] = bool(entry.get("violation")) or g["violated"]
            mean = float(finite.mean()) if finite.size else None
            inside = None
            if mean is not None and (a["lo"] is not None or a["hi"] is not None):
                inside = (a["lo"] is None or mean >= a["lo"]) and (a["hi"] is None or mean <= a["hi"])
            signals[name] = {"label": label, "png": f"{_safe(label)}.png",
                             "min": float(finite.min()) if finite.size else None,
                             "max": float(finite.max()) if finite.size else None, "mean": mean,
                             "std": float(finite.std()) if finite.size else None,
                             "count": int(finite.size), "lo": a["lo"], "hi": a["hi"], "mean_inside": inside,
                             "violated": bool(a["violated"]), "peak_violated": bool(a.get("peak")),
                             "remaining_s": a["remaining"] if a.get("remaining") is not None else None,
                             "edge_goals": [{k: g[k] for k in ("signal", "actual", "target", "at_violation",
                                                                "violated")} for g in a.get("edge_goals") or []]}
        data = {"group": group.name, "source": self.settings.source, "mode": mode.name if mode else None,
                "files": sorted(Path(p).name for p in group.files), "updated": datetime.now().isoformat(timespec="seconds"),
                "signals": signals}
        folder = Path(self.settings.target) / _safe(group.name)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / self.STATS_NAME
        safewrite.write_text(path, json.dumps(data, indent=1, ensure_ascii=False, default=float), log=self.log)
        return str(path)

    # ---------------------------------------------------------------- JSON
    def json_path(self) -> Path:
        """Ergebnisdatei: absoluter Pfad (gemeinsam für mehrere Auswertungen) oder Dateiname im Zielverzeichnis."""
        name = self.settings.json_name or "Time_counter.json"
        if name in ("Time_counter.json", EDGE_JSON):         # Standardname folgt der Zählerart
            name = EDGE_JSON if self.settings.edge_count else "Time_counter.json"
        path = Path(os.path.expanduser(name))
        return path if path.is_absolute() else Path(self.settings.target) / path

    def write_json(self, counters: dict) -> str:
        """Zähler in die (gemeinsame) Ergebnisdatei: Lesen, Ergänzen und Ersetzen unter Sperre; ist die Datei belegt,
        wird der Zugriff analysiert, protokolliert und wiederholt (siehe safewrite)."""
        return safewrite.update_json(self.json_path(), counters, log=self.log)

    # ---------------------------------------------------------------- Zyklus
    def _ingest(self, result: "CycleResult", over) -> int:
        """Verzeichnis abgleichen und neue/geänderte Dateien lesen, bis over() True liefert (mindestens eine)."""
        found = self.scan()
        for path in [p for p in self.files if p not in found]:          # gelöschte Dateien
            key = self.files.pop(path)
            group = self.groups.get(key)
            if group and group.files.pop(path, None):
                group.dirty = True
                result.removed.append(path)
        known = {p: g.files[p].stamp for g in self.groups.values() for p in g.files}
        todo = [p for p, stamp in found.items() if known.get(p) != stamp and self.failed.get(p) != stamp]
        todo.sort(key=lambda p: (found[p][0], p))                         # älteste zuerst
        self.pending = [p for p in self.pending if p in todo] + [p for p in todo if p not in self.pending]

        done = 0
        total = len(self.pending)
        while self.pending:
            if (done and over()) or self.cancel:
                break
            path = self.pending.pop(0)
            self._step("read", done, total, Path(path).name)
            stamp = found[path]
            try:
                data = self._read(path, stamp)
            except Exception as exc:                                     # Datei kaputt oder noch im Schreiben
                self.failed[path] = stamp
                result.errors.append(f"{Path(path).name}: {exc}")
                done += 1
                continue
            self.failed.pop(path, None)
            old = self.files.get(path)
            if old is not None and old != data.group and old in self.groups:
                self.groups[old].files.pop(path, None)
                self.groups[old].dirty = True
            group = self.groups.get(data.group)
            if group is None:
                group = self.groups[data.group] = Group(data.group, "")
                group.name = self._group_label(data.group)
            group.files[path] = data
            group.dirty = True
            self.files[path] = data.group
            result.new_files.append(path)
            result.notes.append(t("{file}: Start {time} ({source})", file=Path(path).name,
                                  time=format_wallclock(data.start), source=data.time_source))
            done += 1
        for key in [k for k in self.groups if k[0] == "*"]:  # Name der Auswertung aus allen ihren Dateinamen
            self.groups[key].name = self._single_name(key)
        return done

    @staticmethod
    def _signature(config, limiter_cfg, mode, settings) -> str:
        """Fingerabdruck der Bewertungsgrundlage: ändert er sich, werden alle Gruppen neu bewertet und gezeichnet."""
        try:
            parts = [limitconfig.to_dict(config) if config is not None else None,
                     limiter.to_dict(limiter_cfg) if limiter_cfg is not None else None, mode,
                     settings.only_hits, settings.png, list(settings.png_size), settings.target,
                     settings.edge_count, [dict(e) for e in settings.edges] if settings.edge_count else None,
                     settings.edge_target if settings.edge_count else None, settings.no_eval]
            return json.dumps(parts, sort_keys=True, default=str)
        except Exception:
            return repr(time.time())

    def run_cycle(self, config=None, limiter_cfg=None, mode: str | None = None, budget: float | None = None,
                  clock=time.monotonic, force: bool = False, reg_method: str | None = None,
                  proposal_name: str = "Auto", proposal_target: str = "24h") -> CycleResult:
        """Ein Zyklus. Erster Durchlauf: alle Dateien des Quellordners (ohne Zeitbudget). Ab dem zweiten Durchlauf: nur
        neue und geänderte Dateien (Änderungszeit oder Größe anders; gelöschte fallen heraus), große Mengen notfalls
        über mehrere Zyklen. force=True (Einen Zyklus jetzt ausführen): ohne Zeitbudget, alle Gruppen neu bewerten,
        alle Bilder und die Ergebnisdatei neu schreiben - gelesen werden auch dann nur neue/geänderte Dateien."""
        start = clock()
        budget = self.settings.cycle_s * self.settings.budget_share if budget is None else budget
        first = not getattr(self, "initial_done", False)
        if force or first:
            budget = float("inf")
        result = CycleResult(started=time.time())
        result.forced = force
        result.first = first
        self.cycles += 1
        over = lambda: clock() - start > budget             # noqa: E731
        if not self.settings.target:
            raise LoadError(t("Bitte ein Zielverzeichnis wählen."))
        if reg_method in REG_METHODS:
            self.reg_method = reg_method
        signature = self._signature(config, limiter_cfg, mode, self.settings) + self.reg_method
        if force or signature != getattr(self, "last_signature", None):
            for group in self.groups.values():          # Konfiguration, Limiter, Mode oder Ziel geändert
                group.dirty = True
                group.force_png = True
        self.last_signature = signature

        done = self._ingest(result, over)
        result.deferred_files = len(self.pending)
        self.log(t("Erster Durchlauf: alle {count} Dateien des Quellordners verarbeitet.", count=len(self.files)) if first else
                 t("Folgedurchlauf: {count} neue/geänderte Dateien gelesen.", count=done))

        # Auswertung je geänderter Gruppe (schnell), Bilder je Signal (langsam, notfalls über mehrere Zyklen)
        for key in list(self.groups):
            group = self.groups[key]
            if not group.files:
                del self.groups[key]
                continue
            if group.dirty:
                if key[0] == "*":
                    group.name = self._single_name(key)
                merged, labels, notes = self.merge(group)
                result.notes += notes
                merged, share = self.limit(group, merged, limiter_cfg)
                if share is not None:
                    result.notes.append(t("{name}: Limiter, {share} % der Messzeit im Limit.", name=group.name,
                                          share=f"{share * 100:.1f}"))
                group.merged, group.labels = merged, labels
        changed = [g for g in self.groups.values() if g.dirty]
        if config is None and changed:                  # Vorschlag über alle Gruppen (gleiche Signalnamen gemeinsam)
            union, names = {}, {}
            for group in self.groups.values():
                for name, (x, y) in (group.merged or {}).items():
                    union.setdefault(name, []).append((x, y))
                    names.setdefault(name, group.labels.get(name, name))
            result.proposal = self.propose({n: (np.concatenate([a for a, _b in v]), np.concatenate([b for _a, b in v]))
                                            for n, v in union.items()}, names, proposal_name,
                                           proposal_target or "24h")
            for group in self.groups.values():          # mit neuem Vorschlag alle neu bewerten
                group.dirty = True
        use = config if config is not None else result.proposal
        if config is None and result.proposal is not None:
            mode = proposal_name
        for group in self.groups.values():
            if group.dirty:
                if self.settings.no_eval:               # Zähler "Ignorieren": keine Bewertung
                    group.counters, notes = {}, []
                elif self.settings.edge_count:          # Flanken Counter statt Time Counter
                    group.counters, notes = evaluate_edges(group.merged, self.settings.edges, group.name, group.labels,
                                                           self.settings.edge_target)
                else:
                    group.counters, notes = self.evaluate(group.merged, use, group.name, self.settings.only_hits, mode)
                result.notes += notes
                try:
                    self.write_statistics(group, use, mode)
                except OSError as exc:
                    result.errors.append(f"{group.name}: {exc}")
                if (group in changed or getattr(group, "force_png", False)) and self.settings.png:
                    group.png_todo = sorted(group.merged)
                group.force_png = False
                group.dirty = False
            result.counters.update(group.counters)

        png_total = sum(len(g.png_todo) for g in self.groups.values())
        png_done = 0
        for group in self.groups.values():
            while group.png_todo:
                if ((result.png_written or done) and over()) or self.cancel:
                    break
                name = group.png_todo.pop(0)
                self._step("png", png_done, png_total, f"{group.name}: {name}")
                png_done += 1
                try:
                    if self._png(group, name, group.labels, config if config is not None else result.proposal, mode):
                        result.png_written += 1
                except Exception as exc:
                    result.errors.append(f"{group.name}/{name}: {exc}")
        result.deferred_png = sum(len(g.png_todo) for g in self.groups.values())
        if first and not self.pending and not self.cancel:
            self.initial_done = True                        # ab jetzt nur neue/geänderte Dateien
        if result.counters:
            self._step("json", 0, 1, self.settings.json_name)
            result.json_path = self.write_json(result.counters)
        result.cancelled = self.cancel
        if self.cancel:
            self.log(t("Abgebrochen - der Rest folgt im nächsten Zyklus."))
        self.cancel = False
        self._step("", 0, 0)
        result.seconds = clock() - start
        self._log_cycle(result)
        return result

    @staticmethod
    def limit(group: Group, merged: dict, limiter_cfg) -> tuple[dict, float | None]:
        """Limiter-Regeln, deren Datei-Muster auf die Gruppe oder eine ihrer Dateien passt, auf die zusammengefassten
        Daten anwenden. Gibt (Daten, Anteil im Limit) zurück; Anteil None = keine Regel griff."""
        if limiter_cfg is None or not limiter_cfg.active:
            return merged, None
        probe = [group.name] + [Path(p).name for p in group.files]
        rules = [r for r in limiter_cfg.rules if r.usable and any(r.matches_file(n) for n in probe)]
        guides = [(merged[r.signal][0], limiter.mask(merged[r.signal][1], r.lo, r.hi)) for r in rules if r.signal in merged]
        if not guides:
            return merged, None
        share = limiter.kept_share(guides)
        return {n: limiter.apply(x, y, guides) for n, (x, y) in merged.items()}, (share or 0.0)

    def analyze(self, limiter_cfg=None) -> tuple[dict, "CycleResult"]:
        """Alle (neuen) Dateien des Quellordners lesen, ohne Ausgaben: je Signalname über alle Dateien
        {Name: (Einheit, Dateien, Minimum, Maximum, Werte)} für den Grenzwert-Konfigurator und den Vorschlag.
        Mit Limiter: Minimum, Maximum und Werte (Grundlage der Vorschläge) nur aus den Abschnitten im Limit,
        die Spitzen außerhalb zählen dann nicht mit (Eintrag "limited" = Anteil im Limit)."""
        result = CycleResult(started=time.time())
        self._ingest(result, lambda: False)
        result.cancelled, self.cancel = self.cancel, False
        self._step("", 0, 0)
        self.log(t("Analyse {path}: {files} Dateien gelesen", path=self.settings.source, files=len(result.new_files)))
        for line in result.notes + [t("Fehler: {text}", text=e) for e in result.errors]:
            self.log(str(line))
        stats = {}
        for group in self.groups.values():
            limited = None
            if limiter_cfg is not None and limiter_cfg.active and limiter_cfg.rules:
                if group.key[0] == "*":
                    group.name = self._single_name(group.key)
                merged, _labels, _notes = self.merge(group)
                limited, share = self.limit(group, merged, limiter_cfg)
                if share is None:
                    limited = None
                else:
                    self.log(t("{name}: Limiter, {share} % der Messzeit im Limit.", name=group.name,
                               share=f"{share * 100:.1f}"))
            for path, data in group.files.items():
                for name, (x, y) in data.signals.items():
                    entry = stats.setdefault(name, {"label": data.labels.get(name, name), "files": [], "parts": [],
                                                    "limited": None})
                    entry["files"].append(Path(path).name)
                    if limited is None:
                        entry["parts"].append(y)
            if limited is not None:
                for name, (_x, y) in limited.items():
                    if name in stats:
                        stats[name]["parts"].append(y)
                        stats[name]["limited"] = share
        out = {}
        for name, entry in stats.items():
            y = np.concatenate(entry["parts"]) if entry["parts"] else np.zeros(0)
            finite = y[np.isfinite(y)]
            out[name] = {"label": entry["label"], "files": entry["files"],
                         "min": float(finite.min()) if finite.size else None,
                         "max": float(finite.max()) if finite.size else None, "values": finite,
                         "limited": entry["limited"]}
        return out, result

    @staticmethod
    def propose_from_stats(stats: dict, name: str = "Auto", target: str = "24h") -> "limitconfig.LimitConfig":
        """Vorschlag für alle Signale des Quellordners: alle aktiv, untere/obere Grenze aus den Daten
        (1-%- bis 99-%-Wert plus 10 % der Spannweite), Zielzeit voreingestellt (24h)."""
        config = limitconfig.new_config(name)
        mode = config.modes[name]
        for signal, entry in stats.items():
            lo, hi = AutoEngine.suggest_limits(entry.get("values"))
            mode.set_entry(signal, True, lo, hi)
        mode.set_steps(target)
        config.modified = True
        return config

    @staticmethod
    def suggest_limits(values) -> tuple:
        if values is None:
            return None, None
        values = np.asarray(values, dtype=np.float64)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return None, None
        lo, hi = (np.percentile(values, [1, 99]) if values.size >= 2 else (values[0], values[0]))
        span = float(hi - lo) or abs(float(hi)) * 0.1 or 1.0
        lo, hi = float(lo) - 0.1 * span, float(hi) + 0.1 * span
        digits = max(0, 2 - int(math.floor(math.log10(span))))
        return round(lo, digits), round(hi, digits)

    def _log_cycle(self, r: CycleResult) -> None:
        parts = [t("Zyklus {n}: {files} neue/geänderte Dateien, {png} Bilder, {count} Zähler, {sec} s",
                   n=self.cycles, files=len(r.new_files), png=r.png_written, count=len(r.counters), sec=f"{r.seconds:.1f}")]
        if r.collision:
            parts.append(t("Hinweis: Zykluszeit zu kurz für die Datenmenge - {files} Dateien und {png} Bilder werden auf "
                           "die nächsten Zyklen verteilt.", files=r.deferred_files, png=r.deferred_png))
        for line in parts + list(r.notes) + [t("Fehler: {text}", text=e) for e in r.errors]:
            self.log(str(line))
        if r.removed:
            self.log(t("Entfernt: {names}", names=", ".join(Path(p).name for p in r.removed)))
