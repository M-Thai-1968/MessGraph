"""Zeitangaben erkennen: Text-Zeitstempel, Uhrzeiten, Dauern und Zahlen-Zeitstempel.

Ergebnis ist immer (Sekunden seit dem ersten Wert, Startzeit). Die Startzeit ist
"Wanduhr-Sekunden": die Uhrzeit, wie sie in der Datei steht, gezählt ab 1970-01-01
ohne Zeitzonenumrechnung. So zeigt die Datumsachse genau die Zeit aus der Datei.
Unix-Zeitstempel (echte UTC-Zeit) werden dafür in Ortszeit umgerechnet.
"""
from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd

MONTHS = {
    "jan": 1, "jän": 1, "feb": 2, "mar": 3, "mär": 3, "mrz": 3, "apr": 4, "may": 5, "mai": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12, "dez": 12,
}
_EPOCH = pd.Timestamp("1970-01-01")

_TZ = r"(?:\s*(?:Z|UTC|GMT|[+-]\d{2}:?\d{2}))?"
_AMPM = r"(?:\s*(?P<ampm>[AaPp]\.?\s?[Mm]\.?))?"
_HMS = (r"(?:(?:[ T_]+|,\s*|\s+um\s+)(?P<H>\d{1,2})[-:._h](?P<M>\d{2})"
        r"(?:[-:._m](?P<S>\d{2})(?:[.,](?P<f>\d+))?)?" + _AMPM + _TZ + r")?")
_MON = r"(?P<mon>[A-Za-zÄÖÜäöü]{3,9})\.?"

# Reihenfolge = Vorrang. "dm" sind Tag/Monat, deren Reihenfolge je Spalte bestimmt wird.
PATTERNS = [
    ("iso", re.compile(r"^(?P<Y>\d{4})[-./_](?P<m>\d{1,2})[-./_](?P<d>\d{1,2})" + _HMS + r"$")),
    ("dm", re.compile(r"^(?P<a>\d{1,2})(?P<sep>[./-])(?P<b>\d{1,2})[./-](?P<Y>\d{4}|\d{2})" + _HMS + r"$")),
    ("compact", re.compile(r"^(?P<Y>\d{4})(?P<m>\d{2})(?P<d>\d{2})[ T_]?(?P<H>\d{2})(?P<M>\d{2})(?P<S>\d{2})"
                           r"(?:[.,](?P<f>\d+))?" + _TZ + r"$")),
    ("dmon", re.compile(r"^(?:[A-Za-zÄÖÜäöü]{2,10}\.?,?\s+)?(?P<d>\d{1,2})\.?[ \-/]?" + _MON
                        + r"[ \-/,]*(?P<Y>\d{4}|\d{2})" + _HMS + r"$")),
    ("mond", re.compile(r"^(?:[A-Za-z]{3,9},?\s+)?" + _MON + r"\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<Y>\d{4})"
                        + _HMS + r"$")),
    ("asctime", re.compile(r"^[A-Za-z]{3}\s+" + _MON + r"\s+(?P<d>\d{1,2})\s+(?P<H>\d{1,2}):(?P<M>\d{2}):(?P<S>\d{2})"
                           r"(?:[.,](?P<f>\d+))?\s+(?P<Y>\d{4})$")),
]
CLOCK = re.compile(r"^(?:(?P<days>\d+)\s*(?:days?|d|Tage?|T)\s*,?\s*)?(?P<H>\d+):(?P<M>\d{2})"
                   r"(?::(?P<S>\d{2})(?:[.,](?P<f>\d+))?)?" + _AMPM + r"$")

_FIELDS = ["Y", "m", "d", "H", "M", "S", "f", "ampm"]


def looks_like_time(text: str) -> bool:
    t = str(text).strip()
    return bool(CLOCK.match(t) or any(rx.match(t) for _, rx in PATTERNS))


def _fraction(series: pd.Series) -> pd.Series:
    text = series.fillna("0").astype(str).str.ljust(9, "0").str[:9]
    return pd.to_numeric(text, errors="coerce").fillna(0) / 1e9


def _hour24(hour: pd.Series, ampm: pd.Series) -> pd.Series:
    marker = ampm.fillna("").astype(str).str.lower().str.replace(r"[.\s]", "", regex=True)
    hour = hour.where(~marker.isin(["am", "pm"]), hour % 12)
    return hour.where(marker != "pm", hour + 12)


def _rising_share(values: pd.Series) -> float:
    v = values.dropna().to_numpy()
    return float(np.mean(np.diff(v) >= 0)) if v.size > 1 else 0.0


def _resolve_day_month(found: pd.DataFrame) -> pd.DataFrame:
    """Tag.Monat oder Monat/Tag: eindeutige Werte entscheiden, sonst der steigende Zeitverlauf."""
    a = pd.to_numeric(found["a"], errors="coerce")
    b = pd.to_numeric(found["b"], errors="coerce")
    out = found.copy()
    if (a > 12).any():
        day_first = True
    elif (b > 12).any():
        day_first = False
    elif (found["sep"] == ".").any():
        day_first = True  # Punkt ist im deutschen Format immer Tag.Monat
    else:
        # Beide Lesarten möglich: die steigende, dann die mit kleineren Zeitschritten
        # (aufeinanderfolgende Messpunkte liegen dicht beieinander); Gleichstand: Tag zuerst.
        trial = {}
        for flag in (True, False):
            probe = out.assign(d=found["a"] if flag else found["b"], m=found["b"] if flag else found["a"])
            secs = _assemble(probe).dropna().to_numpy()
            step = float(np.median(np.abs(np.diff(secs)))) if secs.size > 1 else 0.0
            trial[flag] = (_rising_share(_assemble(probe)), -step)
        day_first = trial[True] >= trial[False]
    out["d"], out["m"] = (found["a"], found["b"]) if day_first else (found["b"], found["a"])
    return out


def _assemble(parts: pd.DataFrame) -> pd.Series:
    """Teile in Wanduhr-Sekunden ab 1970 (float, NaN wo nichts erkannt)."""
    num = {k: pd.to_numeric(parts.get(k), errors="coerce") for k in ("Y", "m", "d", "H", "M", "S")}
    year = num["Y"]
    year = year.where(year >= 100, year + np.where(year < 70, 2000, 1900))
    hour = _hour24(num["H"].fillna(0), parts.get("ampm", pd.Series(index=parts.index, dtype=object)))
    frame = pd.DataFrame({"year": year, "month": num["m"], "day": num["d"], "hour": hour,
                          "minute": num["M"].fillna(0), "second": num["S"].fillna(0)})
    stamps = pd.to_datetime(frame, errors="coerce")
    seconds = (stamps - _EPOCH).dt.total_seconds()
    return seconds + _fraction(parts.get("f", pd.Series(index=parts.index, dtype=object)))


def parse_text(series: pd.Series) -> tuple[np.ndarray, float | None] | None:
    """Textspalte als Zeit. None, wenn weniger als 80 % der Werte passen."""
    text = series.where(series.notna(), "").astype(str).str.strip()
    filled = text[text != ""]
    if filled.empty:
        return None
    probe = filled.head(200)
    if probe.map(looks_like_time).mean() < 0.8:
        return None

    clock = probe.str.match(CLOCK)
    if clock.mean() >= 0.8:
        return _parse_clock(text)

    result = pd.Series(np.nan, index=text.index)
    for kind, rx in PATTERNS:
        if not probe.str.match(rx).any():
            continue  # spart bei großen Dateien unnötige Durchläufe
        found = text.str.extract(rx)
        hit = found.notna().any(axis=1) & result.isna()
        if not hit.any():
            continue
        found = found[hit]
        if kind == "dm":
            found = _resolve_day_month(found)
        if "mon" in found:
            found["m"] = found["mon"].str[:3].str.lower().map(MONTHS)
        result[hit] = _assemble(found)
    if result.notna().mean() < 0.8:
        return None
    first = result.dropna().iloc[0]
    return (result - first).to_numpy(dtype=np.float64), float(first)


def _parse_clock(text: pd.Series) -> tuple[np.ndarray, None] | None:
    """Uhrzeit ohne Datum oder Dauer. Bei Uhrzeiten zählt ein Rücksprung über Mitternacht als neuer Tag."""
    found = text.str.extract(CLOCK)
    num = {k: pd.to_numeric(found[k], errors="coerce") for k in ("days", "H", "M", "S")}
    hour = _hour24(num["H"], found["ampm"])
    secs = (num["days"].fillna(0) * 86400 + hour * 3600 + num["M"] * 60 + num["S"].fillna(0)
            + _fraction(found["f"]))
    if secs.notna().mean() < 0.8:
        return None
    is_duration = found["days"].notna().any() or (num["H"] >= 24).any()
    values = secs.to_numpy(dtype=np.float64, copy=True)
    if not is_duration:
        valid = np.isfinite(values)
        steps = np.diff(values[valid], prepend=values[valid][0])
        values[valid] += np.cumsum(steps < -12 * 3600) * 86400.0
    first = values[np.isfinite(values)][0]
    return values - first, None


def parse_datetime64(series: pd.Series) -> tuple[np.ndarray, float | None]:
    if pd.api.types.is_timedelta64_dtype(series):
        secs = series.dt.total_seconds()
        first = secs.dropna().iloc[0]
        return (secs - first).to_numpy(dtype=np.float64, na_value=np.nan), None
    shift = 0.0
    if getattr(series.dt, "tz", None) is not None:  # mit Zeitzone: als Ortszeit zeigen
        series = series.dt.tz_convert(None)
        utc_first = (series.dropna().iloc[0] - _EPOCH).total_seconds()
        shift = float(time.localtime(utc_first).tm_gmtoff or 0)
    secs = (series - _EPOCH).dt.total_seconds()
    first = secs.dropna().iloc[0]
    return (secs - first).to_numpy(dtype=np.float64, na_value=np.nan), float(first) + shift


# Zahlen-Zeitstempel: (Name, Teiler in Sekunden, Bereich in Sekunden ab 1970 = Jahre 2000..2050)
_LABVIEW_OFFSET = 2_082_844_800.0  # 1904-01-01 bis 1970-01-01
_SPAN = (946_684_800.0, 2_524_608_000.0)
EPOCH_UNITS = [("Unix-Zeit [s]", 1.0, 0.0), ("Unix-Zeit [ms]", 1e3, 0.0), ("Unix-Zeit [µs]", 1e6, 0.0),
               ("Unix-Zeit [ns]", 1e9, 0.0), ("LabVIEW-Zeit [s]", 1.0, _LABVIEW_OFFSET)]


def parse_epoch_numbers(values: np.ndarray) -> tuple[np.ndarray, float, str] | None:
    """Zahlenspalte, deren Werte vollständig in einem Zeitstempel-Bereich liegen."""
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return None
    lo, hi = float(finite.min()), float(finite.max())
    for name, divisor, offset in EPOCH_UNITS:
        start, end = lo / divisor - offset, hi / divisor - offset
        if _SPAN[0] <= start and end <= _SPAN[1]:
            secs = values / divisor - offset
            first = float(secs[np.isfinite(secs)][0])
            return secs - first, first + float(time.localtime(first).tm_gmtoff or 0), name
    return None


def format_wallclock(seconds: float) -> str:
    """Wanduhr-Sekunden als 01.10.2026 23:00:51.250"""
    if seconds is None or not np.isfinite(seconds):
        return "-"
    stamp = _EPOCH + pd.Timedelta(milliseconds=round(seconds * 1000))
    return stamp.strftime("%d.%m.%Y %H:%M:%S.") + f"{stamp.microsecond // 1000:03d}"


def now_wallclock() -> float:
    """Jetzt als Wanduhr-Sekunden (Ortszeit), passend zu den Startzeiten der Signale."""
    return (pd.Timestamp.now() - _EPOCH).total_seconds()


def format_span(seconds: float) -> str:
    """Kurze Dauer für Prognosen: 53 d 12 h 56 min, 5 h 03 min, 12 min 07 s, 42.3 s (ohne Vorzeichen)."""
    if seconds is None or not np.isfinite(seconds):
        return "-"
    rest = abs(float(seconds))
    if rest < 60:
        return f"{rest:.3g} s"
    days, rest = divmod(rest, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{int(days)} d {int(hours)} h {int(minutes):02d} min"
    if hours:
        return f"{int(hours)} h {int(minutes):02d} min"
    return f"{int(minutes)} min {int(secs):02d} s"


def format_duration(seconds: float) -> str:
    """Dauer lesbar: 1 d 02:03:04.5 (93784.5 s); kurze Dauern nur in s."""
    if seconds is None or not np.isfinite(seconds):
        return "-"
    if abs(seconds) < 60:
        return f"{seconds:.6g} s"
    sign = "-" if seconds < 0 else ""
    rest = abs(seconds)
    days, rest = divmod(rest, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    clock = f"{int(hours):02d}:{int(minutes):02d}:{secs:06.3f}".rstrip("0").rstrip(".")
    text = f"{int(days)} d {clock}" if days else clock
    return f"{sign}{text} ({seconds:.6g} s)"
