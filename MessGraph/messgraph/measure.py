"""Messrechnung der Crosslines und Datenreduktion für die Anzeige."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

NAN = float("nan")


def value_at(x: np.ndarray, y: np.ndarray, xq: float | None) -> float:
    """Linear interpoliert. NaN außerhalb der Daten und in Messlücken."""
    if xq is None or x.size == 0 or not (x[0] <= xq <= x[-1]):
        return NAN
    i = int(np.searchsorted(x, xq, side="left"))
    if x[i] == xq:
        return float(y[i])
    x0, x1, y0, y1 = x[i - 1], x[i], y[i - 1], y[i]
    if not (math.isfinite(y0) and math.isfinite(y1)):
        return NAN
    return float(y0 + (y1 - y0) * (xq - x0) / (x1 - x0))


@dataclass
class Measurement:
    x1: float
    x2: float
    value1: float
    value2: float
    delta_x: float
    delta_y: float
    drift: float


def measure(x: np.ndarray, y: np.ndarray, x1: float | None, x2: float | None) -> Measurement:
    """Delta = Crossline 2 minus Crossline 1, Drift = Delta Y / Delta X."""
    x1f = NAN if x1 is None else float(x1)
    x2f = NAN if x2 is None else float(x2)
    v1, v2 = value_at(x, y, x1), value_at(x, y, x2)
    dx, dy = x2f - x1f, v2 - v1
    drift = dy / dx if dx != 0 and math.isfinite(dx) and math.isfinite(dy) else NAN
    return Measurement(x1f, x2f, v1, v2, dx, dy, drift)


# Art der Drift-Regression (Graph-Optionen > Drift-Regression); Reihenfolge = Menü
REG_METHODS = {
    "ols": "Lineare Regression (kleinste Quadrate)",
    "tls": "Minimale Abstandsquadrate (orthogonal)",
    "theilsen": "Robuste Regression (Theil-Sen)",
    "recent": "Lineare Regression über das letzte Viertel",
}
THEIL_SEN_POINTS = 1500          # Theil-Sen: höchstens so viele gleichmäßig verteilte Punkte (Paare ~ n²/2)
RECENT_SHARE = 0.25              # "letztes Viertel": Anteil der gültigen Punkte am Ende


def _ols(x: np.ndarray, y: np.ndarray, xm: float, ym: float) -> float:
    dx = x - xm
    sxx = float(np.dot(dx, dx))
    return NAN if sxx == 0 else float(np.dot(dx, y - ym)) / sxx


def regression(x: np.ndarray, y: np.ndarray, method: str = "ols") -> tuple[float, float]:
    """Regressionsgerade f(x) = m*x + b über alle gültigen Werte.

    method:
        ols       kleinste Quadrate der senkrechten (y-)Abstände, die übliche lineare Regression
        tls       minimale Quadrate der orthogonalen Abstände zur Geraden (Total Least Squares, Hauptachse);
                  hängt von den Einheiten ab, weil x und y gemeinsam gemessen werden
        theilsen  Median der Steigungen aller Punktpaare (robust gegen Ausreißer), b = Median(y - m*x)
        recent    kleinste Quadrate nur über das letzte Viertel der Daten (aktueller Trend)
    Gerechnet wird relativ zum Mittelwert von x, damit große Zeitwerte (Wanduhr-Sekunden) nicht an Genauigkeit
    verlieren. Weniger als zwei gültige Punkte oder konstantes x: (nan, nan).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 2:
        return NAN, NAN
    x, y = x[ok], y[ok]
    if method == "recent":
        x, y = x[-max(2, int(round(len(x) * RECENT_SHARE))):], y[-max(2, int(round(len(x) * RECENT_SHARE))):]
    xm, ym = float(x.mean()), float(y.mean())
    if method == "tls":
        dx, dy = x - xm, y - ym
        sxx, syy, sxy = float(np.dot(dx, dx)), float(np.dot(dy, dy)), float(np.dot(dx, dy))
        if sxx == 0:
            return NAN, NAN
        if sxy == 0:
            m = 0.0 if sxx >= syy else NAN       # Punktwolke ohne Richtung entlang x bzw. senkrecht
        else:                                     # Steigung der Hauptachse (größter Eigenwert der Kovarianz)
            m = (syy - sxx + np.hypot(syy - sxx, 2.0 * sxy)) / (2.0 * sxy)
        if not np.isfinite(m):
            return NAN, NAN
        return float(m), float(ym - m * xm)
    if method == "theilsen":
        if len(x) > THEIL_SEN_POINTS:             # gleichmäßig ausdünnen (reproduzierbar)
            pick = np.linspace(0, len(x) - 1, THEIL_SEN_POINTS).astype(int)
            xs, ys = x[pick] - xm, y[pick]
        else:
            xs, ys = x - xm, y
        i, j = np.triu_indices(len(xs), k=1)
        dx = xs[j] - xs[i]
        use = dx != 0
        if not use.any():
            return NAN, NAN
        m = float(np.median((ys[j] - ys[i])[use] / dx[use]))
        b0 = float(np.median(y - m * (x - xm)))   # Achsenabschnitt bezogen auf xm
        return m, b0 - m * xm
    m = _ols(x, y, xm, ym)
    if not np.isfinite(m):
        return NAN, NAN
    return m, float(ym - m * xm)


@dataclass
class Prediction:
    """Prognose ab dem letzten Messpunkt. kind: none, inside (kein Schnitt), reached, max, min."""
    kind: str
    x2: float = NAN          # gesuchter Abstand ab dem letzten Messpunkt (x1 = 0) in X-Einheiten
    limit: float = NAN
    slope: float = NAN


def predict(slope: float, y_last: float, lo: float | None, hi: float | None) -> Prediction:
    """f(x) = m*x + b mit m aus der Regression und b = letzter y-Wert (x1 = 0 am letzten Messpunkt).

    Steigend: y2 = Y max, fallend: y2 = Y min; x2 = (y2 - b) / m.
    """
    if (lo is None and hi is None) or not (math.isfinite(slope) and math.isfinite(y_last)):
        return Prediction("none", slope=slope)
    if slope > 0 and hi is not None:
        kind, limit = "max", hi
    elif slope < 0 and lo is not None:
        kind, limit = "min", lo
    else:
        return Prediction("inside", slope=slope)
    x2 = (limit - y_last) / slope
    if x2 < 0:  # letzter Wert liegt schon jenseits der Grenze
        return Prediction("reached", x2, limit, slope)
    return Prediction(kind, x2, limit, slope)


# Sekunden je X-Einheit (Zielzeit und Verletzungszeit brauchen eine Zeitachse)
TIME_FACTORS = {"s": 1.0, "sec": 1.0, "ms": 1e-3, "us": 1e-6, "min": 60.0, "h": 3600.0, "d": 86400.0}
_DURATION_UNITS = {"d": 86400.0, "t": 86400.0, "tag": 86400.0, "tage": 86400.0, "day": 86400.0, "days": 86400.0,
                   "h": 3600.0, "std": 3600.0, "stunde": 3600.0, "stunden": 3600.0, "hr": 3600.0, "hrs": 3600.0,
                   "m": 60.0, "min": 60.0, "minute": 60.0, "minuten": 60.0, "mins": 60.0,
                   "s": 1.0, "sec": 1.0, "sek": 1.0, "sekunden": 1.0}


def parse_duration(text: str) -> float | None:
    """Zielzeit in Sekunden aus "2d 6h 30m", "2t 6std", "1,5h" oder Zahlen ohne Einheit:
    eine Zahl = Stunden, zwei = Stunden Minuten, drei = Tage Stunden Minuten. Leer = None; ungültig: ValueError."""
    text = str(text or "").strip().lower().replace(",", ".")
    if not text:
        return None
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*([a-zäöü]*)", text)
    rest = re.sub(r"(\d+(?:\.\d+)?)\s*([a-zäöü]*)", "", text).replace(":", " ").strip(" ")
    if not parts or rest.strip():
        raise ValueError(text)
    if all(not unit for _n, unit in parts):
        numbers = [float(n) for n, _u in parts]
        if len(numbers) > 3:
            raise ValueError(text)
        factors = {1: [3600.0], 2: [3600.0, 60.0], 3: [86400.0, 3600.0, 60.0]}[len(numbers)]
        return sum(n * f for n, f in zip(numbers, factors))
    total = 0.0
    for number, unit in parts:
        if unit not in _DURATION_UNITS:
            raise ValueError(text)
        total += float(number) * _DURATION_UNITS[unit]
    return total


def format_target(seconds: float) -> str:
    """Zielzeit: Sekunden als "2d 6h 30m" (auf Minuten gerundet)."""
    if seconds is None or not math.isfinite(seconds):
        return "-"
    sign = "-" if seconds < 0 else ""
    minutes = int(math.floor(abs(seconds) / 60.0 + 0.5))
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    parts = ([f"{days}d"] if days else []) + ([f"{hours}h"] if hours or days else []) + [f"{mins}m"]
    return sign + " ".join(parts)


def fmt(value: float, unit: str = "") -> str:
    """Anzeigeformat mit 6 signifikanten Stellen; ungültige Werte als '-'."""
    if value is None or not math.isfinite(value):
        return "-"
    return f"{value:.6g} {unit}" if unit else f"{value:.6g}"


def drift_unit(unit: str, x_unit: str) -> str:
    if unit and x_unit:
        return f"{unit}/{x_unit}"
    if x_unit:
        return f"1/{x_unit}"
    return unit


def decimate(x: np.ndarray, y: np.ndarray, lo: float | None = None, hi: float | None = None,
             bins: int = 3000) -> tuple[np.ndarray, np.ndarray]:
    """Min/Max je Abschnitt: Spitzen bleiben sichtbar, die Punktzahl bleibt begrenzt."""
    start, stop = 0, x.size
    if lo is not None and hi is not None and hi > lo:
        start = max(int(np.searchsorted(x, lo, side="left")) - 1, 0)
        stop = min(int(np.searchsorted(x, hi, side="right")) + 1, x.size)
        if stop - start < 2:
            start, stop = 0, x.size
    n = stop - start
    if n <= 2 * bins:
        return x[start:stop], y[start:stop]
    size = -(-n // bins)                 # aufrunden: höchstens bins Blöcke
    count = n // size
    end = start + count * size
    xb = x[start:end].reshape(count, size)
    yb = y[start:end].reshape(count, size)
    rest = stop - end                    # angebrochener letzter Block wird ebenfalls verdichtet
    out_x = np.empty(count * 2 + (2 if rest else 0))
    out_y = np.empty_like(out_x)
    out_x[0:count * 2:2] = xb[:, 0]
    out_x[1:count * 2:2] = xb[:, -1]
    with np.errstate(invalid="ignore"):
        out_y[0:count * 2:2] = np.fmin.reduce(yb, axis=1)
        out_y[1:count * 2:2] = np.fmax.reduce(yb, axis=1)
        if rest:
            tail = y[end:stop]
            out_x[-2], out_x[-1] = x[end], x[stop - 1]
            out_y[-2], out_y[-1] = np.fmin.reduce(tail), np.fmax.reduce(tail)
    return out_x, out_y


def view_points(x: np.ndarray, y: np.ndarray, lo: float, hi: float,
                bins: int = 3000, overview_bins: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Sichtbarer Bereich fein, der Rest grob.

    Der grobe Rest hält Gesamtbereich und Extremwerte in der Serie, damit
    "Alles anzeigen" und der Doppelklick auch nach dem Zoomen alles einpassen.
    """
    fine_x, fine_y = decimate(x, y, lo, hi, bins)
    if fine_x.size == 0 or (fine_x[0] <= x[0] and fine_x[-1] >= x[-1]):
        return fine_x, fine_y
    over_x, over_y = decimate(x, y, bins=overview_bins)
    left = over_x < fine_x[0]
    right = over_x > fine_x[-1]
    return np.concatenate((over_x[left], fine_x, over_x[right])), np.concatenate((over_y[left], fine_y, over_y[right]))
