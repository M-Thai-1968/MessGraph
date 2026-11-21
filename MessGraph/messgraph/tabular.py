"""Aus einer Tabelle (DataFrame) Zeitachse und Datenspalten bestimmen.

Wird von den CSV- und Parquet-Lesern gemeinsam genutzt.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .data_model import Channel, Dataset, LoadError, prepare_xy
from .i18n import t
from .timeparse import looks_like_time, parse_datetime64, parse_epoch_numbers, parse_text

_KNOWN_UNITS = {
    "s", "ms", "us", "µs", "ns", "min", "h", "v", "mv", "kv", "a", "ma", "w", "kw", "mw",
    "hz", "khz", "mhz", "rpm", "u/min", "1/min", "nm", "n", "kn", "bar", "mbar", "pa",
    "kpa", "hpa", "mpa", "psi", "°c", "degc", "c", "k", "°f", "%", "km/h", "kmh", "m/s",
    "m/s²", "m/s^2", "m/s2", "g", "kg", "t", "m", "mm", "cm", "km", "l", "ml", "ohm",
    "kohm", "mohm", "Ω", "wh", "kwh", "ah", "mah", "db", "dbm", "°", "deg", "rad",
    "rad/s", "lsb", "-", "l/min", "kg/h", "g/s", "v/s", "a/s", "1", "bit", "byte",
}

_TIME_EXACT = {
    "t", "time", "zeit", "timestamp", "timestamps", "zeitstempel", "datetime", "date_time",
    "datum_zeit", "datumzeit", "sec", "secs", "second", "seconds", "sekunde", "sekunden",
    "time_s", "time_ms", "zeit_s", "zeit_ms", "t_s", "t_ms", "abstime", "reltime",
    "absolute time", "relative time", "master", "ts",
}
_TIME_PREFIX = re.compile(r"^(time|zeit|timestamp|zeitstempel|datetime)\b", re.I)
_TIME_WORD = re.compile(r"(^|[\s_\-.])(time|zeit|timestamp|zeitstempel)($|[\s_\-.])", re.I)


def is_unit(text: str) -> bool:
    """True, wenn der Text wie eine Einheit aussieht (bekannt oder in Klammern)."""
    t = text.strip()
    if not t:
        return False
    if (t[0], t[-1]) in {("[", "]"), ("(", ")"), ("<", ">")}:
        return True
    return t.lower() in _KNOWN_UNITS or t in _KNOWN_UNITS


def split_unit(name: str) -> tuple[str, str]:
    """'Speed [km/h]' -> ('Speed', 'km/h'). Runde Klammern nur bei echten Einheiten."""
    name = name.strip()
    m = re.match(r"^(.*\S)\s*\[([^\]]*)\]$", name)
    if m:
        return m.group(1), m.group(2).strip()
    m = re.match(r"^(.*\S)\s*\(([^)]*)\)$", name)
    if m and is_unit(m.group(2)):
        return m.group(1), m.group(2).strip()
    return name, ""


def clean_names(raw: list) -> list[str]:
    """Leere Namen ersetzen, führendes # entfernen, Dubletten eindeutig machen."""
    seen: dict[str, int] = {}
    result = []
    for i, value in enumerate(raw, 1):
        name = "" if value is None else str(value).strip().strip('"').lstrip("#").strip()
        name = name or f"Spalte_{i}"
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return result


# Platzhalter für "kein Messwert" (z. B. x im Prüfstandsexport): zählen nicht als Text
PLACEHOLDERS = {"x", "-", "--", "---", "n/a", "na", "nan", "null", "none", "?", "*", "#n/a", "inf", "-inf", "+inf",
                "ovf", "err", "invalid"}


def to_numeric(series: pd.Series, decimal: str = ".") -> np.ndarray | None:
    """Spalte als float64, oder None wenn sie keine Zahlenwerte liefert.

    Eine Spalte gilt als Signal, wenn mindestens die Hälfte der Einträge Zahlen sind oder alle Einträge, die
    keine Zahl sind, Platzhalter wie x, -, n/a sind (Messwert nur zeitweise aufgezeichnet).
    """
    if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)
    if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_timedelta64_dtype(series):
        return None
    filled = series.notna()
    if not filled.any():
        return None
    text = series[filled].astype(str).str.strip()
    if decimal == ",":
        text = text.str.replace(",", ".", regex=False)
    text = text[text != ""]
    if text.empty:
        return None
    values = pd.to_numeric(text, errors="coerce")
    if not values.notna().any():
        return None
    if values.notna().mean() < 0.5:
        rest = text[values.isna()].str.lower()
        if not rest.isin(PLACEHOLDERS).all():
            return None
        values = values.dropna()
    out = np.full(len(series), np.nan)
    out[series.index.get_indexer(values.index)] = values.to_numpy(dtype=np.float64)
    return out


def looks_like_date(text: str) -> bool:
    return looks_like_time(text)


def _to_seconds(series: pd.Series) -> tuple[np.ndarray, float | None] | None:
    """Datums-/Zeitspalte: (Sekunden seit dem ersten Wert, Startzeit). None, wenn es keine ist."""
    if pd.api.types.is_timedelta64_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
        if series.notna().any():
            return parse_datetime64(series)
        return None
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return None
    return parse_text(series)


def _time_score(name: str) -> int:
    n = split_unit(name)[0].strip().lower()
    if n in _TIME_EXACT:
        return 3
    if _TIME_PREFIX.match(n):
        return 2
    if _TIME_WORD.search(n):
        return 1
    return 0


def _mostly_rising(x: np.ndarray) -> bool:
    x = x[np.isfinite(x)]
    if x.size < 2 or x[0] == x[-1] and np.all(x == x[0]):
        return False
    return float(np.mean(np.diff(x) >= 0)) >= 0.99


def _merge_date_and_clock(df: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    """Getrennte Spalten 'Datum' und 'Uhrzeit' zu einer Zeitspalte zusammenführen."""
    lower = {str(c).strip().lower(): c for c in df.columns}
    date_col = next((lower[k] for k in ("datum", "date") if k in lower), None)
    clock_col = next((lower[k] for k in ("uhrzeit", "time", "zeit", "clock") if k in lower), None)
    if date_col is None or clock_col is None:
        return df
    if pd.api.types.is_numeric_dtype(df[clock_col]) or pd.api.types.is_numeric_dtype(df[date_col]):
        return df
    merged = df[date_col].astype(str).str.strip() + " " + df[clock_col].astype(str).str.strip()
    out = df.drop(columns=[date_col, clock_col])
    out.insert(0, "Zeit", merged)
    warnings.append(t("Spalten '{a}' und '{b}' zur Zeitachse zusammengeführt", a=date_col, b=clock_col))
    return out


def build_dataset(path: str, df: pd.DataFrame, decimal: str = ".",
                  units: dict[str, str] | None = None,
                  info: list[str] | None = None) -> Dataset:
    """Bestimmt die Zeitachse und legt je Zahlenspalte einen Kanal an."""
    units = units or {}
    info = list(info or [])
    warnings: list[str] = []
    if df.empty:
        raise LoadError(t("Die Datei enthält keine Datenzeilen."))
    df = _merge_date_and_clock(df, warnings)

    numeric: dict[str, np.ndarray] = {}
    seconds: dict[str, np.ndarray] = {}
    ignored: list[str] = []
    from . import progress
    for number, col in enumerate(df.columns):
        progress.step(number / len(df.columns), t("Spalten erkennen: {done} von {total}", done=number + 1,
                                                  total=len(df.columns)))
        series = df[col]
        secs = _to_seconds(series)
        if secs is not None:
            seconds[col] = secs
            continue
        values = to_numeric(series, decimal)
        if values is None or not np.isfinite(values).any():
            ignored.append(str(col))
            continue
        numeric[col] = values
    if not numeric and not seconds:
        raise LoadError(t("Keine Spalte mit Zahlenwerten gefunden."))

    # Zeitachse: Name und Verlauf zählen; Datumsspalten haben Vorrang vor bloßen Zahlen.
    # Eintrag: (Rang, -Position, Spalte, Werte, Startzeit oder None, Art)
    candidates = []
    for pos, col in enumerate(df.columns):
        score = _time_score(str(col))
        if col in seconds:
            secs, epoch = seconds[col]
            if _mostly_rising(secs):
                candidates.append((score + 2, -pos, col, secs, epoch, "date" if epoch is not None else "duration"))
        elif col in numeric and (score or pos == 0) and _mostly_rising(numeric[col]):
            stamp = parse_epoch_numbers(numeric[col])
            if stamp is not None:
                candidates.append((score + 2, -pos, col, stamp[0], stamp[1], stamp[2]))
            elif score:
                candidates.append((score, -pos, col, numeric[col], None, "number"))

    keep_x_channel = False
    epoch = None
    kind = "number"
    if candidates:
        _, _, x_col, x_values, epoch, kind = max(candidates, key=lambda c: (c[0], c[1]))
    else:
        first = df.columns[0]
        if first in numeric and len(df) > 1 and np.all(np.diff(numeric[first][np.isfinite(numeric[first])]) > 0):
            x_col, x_values = first, numeric[first]
            keep_x_channel = True
            warnings.append(t("Keine Zeitspalte benannt: erste steigende Spalte '{name}' dient als X-Achse", name=first))
        else:
            x_col, x_values = None, np.arange(len(df), dtype=np.float64)
            warnings.append(t("Keine Zeitspalte gefunden: X-Achse ist die Zeilennummer"))

    if x_col is None:
        x_name, x_unit = t("Zeile"), ""
    elif kind == "number":
        x_name, x_unit = split_unit(str(x_col))
        x_unit = units.get(x_col, x_unit)
    else:
        x_name, x_unit = split_unit(str(x_col))[0], "s"
        if kind not in ("date", "duration"):
            info.append(t("Zeitspalte '{name}' als {kind} erkannt", name=x_col, kind=kind))

    x_values, order_probe = prepare_xy(x_values, np.arange(len(x_values), dtype=np.float64))
    if np.any(np.diff(order_probe) < 0):
        warnings.append(t("Zeitachse war nicht aufsteigend: Daten wurden sortiert"))
    picker = order_probe.astype(np.int64)

    channels = []
    for col, values in numeric.items():
        if col == x_col and not keep_x_channel:
            continue
        name, unit = split_unit(str(col))
        channels.append(Channel(name=name, unit=units.get(col, unit), x_name=x_name, x_unit=x_unit,
                                source=path, x=x_values, y=values[picker], x_epoch=epoch))
    if not channels:
        raise LoadError(t("Neben der Zeitachse wurde keine Datenspalte gefunden."))
    others = [str(col) for col in seconds if col != x_col]
    if others:   # liefern Zeitwerte, sind aber keine Signale: nur in der Erkennung nennen
        info.append(t("Weitere Zeitspalten (nicht als Signal): {names}", names=", ".join(others)))
    info.append(t("{rows} Zeilen, {count} Datenspalten", rows=len(df), count=len(channels)))
    info.append(t("X-Achse: {name}", name=x_name + (f" [{x_unit}]" if x_unit else "")))
    if epoch is not None:
        from .timeparse import format_wallclock
        info.append(t("Start: {time}", time=format_wallclock(epoch)))
    # Spalten ohne einen einzigen Zahlenwert; der Hinweis in der Dateiliste wird daraus beim Anzeigen gebildet
    return Dataset(path=path, channels=channels, info=info, warnings=warnings, extra={"no_values": ignored})
