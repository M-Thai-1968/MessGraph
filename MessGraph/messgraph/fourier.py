"""Fourier-Analyse eines Signals auf Harmonische für "Signal berechnen".

Darstellung wahlweise einzelne senkrechte Balken an den Harmonischen oder (Frequenzbereich) durchgehendes Spektrum:
  FFT({Signal}; h=1..15; f0=auto; y=pct)            X = Nummer der Harmonischen 1..15 (Balken)
  FFT({Signal}; f=0..1000; f0=auto; y=db)           X = Frequenz [Hz]: Balken an allen n*f0 im Bereich (bis 50)
  FFT({Signal}; f=0..1000; f0=auto; y=db; plot=line) X = Frequenz [Hz]: durchgehendes Spektrum als Linie

Harmonische 1 = Grundschwingung f0 (z. B. 50 Hz), Harmonische n bei n * f0 (150 Hz = 3. Harmonische).
Anzeige wahlweise
  y=pct  Anteil [%] der Amplitude An an der Summe der Amplituden aller berechneten Harmonischen (Summe 100 %):
         reiner Sinus H1 = 100 %, alle anderen 0; mit Oberwellen H1 < 100 % und der Rest verteilt sich auf die
         Harmonischen (über mehrere Perioden: Effektivwert der Amplituden).
  y=db   Dämpfung [dB] gegenüber der Grundschwingung: 20*log10(A1/An), H1 = 0 dB; fehlende Harmonische 100 dB.
  y=amp  Amplitude (Spitzenwert) in der Einheit des Signals.
  Spektrum (plot=line): y=amp Amplitude jeder Frequenzlinie, y=pct in % der Grundschwingungs-Amplitude A1,
  y=db Dämpfung gegenüber A1.

Periodizität: Aus dem Signal wird die Grundschwingung (Bandpass um f0) gebildet; ihre steigenden Nulldurchgänge
teilen das Signal in Perioden (Schwingungen). Periodisch (auch bei wechselnder Frequenz oder Amplitude) bei mindestens
2 ganzen Perioden, Streuung der Periodendauer <= 25 % und ähnlicher Kurvenform (Korrelation >= 0,7). Dann wird jede
Periode einzeln zerlegt (DFT über genau eine Periode: Linie n = n-te Harmonische, kein Leckeffekt). Welche Perioden
die Balken zeigen, bestimmen die Marker im Graphen des Grundsignals (select): Perioden, deren Mitte zwischen M1 und M2
liegt; ohne Marker alle. Nicht periodisch: Spitzen bei n*f0 im Spektrum des ganzen Signals (Hann-Fenster).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .i18n import t

MAX_HARMONIC = 15
MAX_RANGE_HARMONIC = 50     # Frequenzbereich: höchstens so viele Harmonische
DB_FLOOR = 100.0            # Dämpfung einer Harmonischen ohne Energie
SCALES = ("pct", "db", "amp")
VIEWS = ("bar", "line")
WINDOWS = ("auto", "hann", "rect")
PERIOD_CV_MAX = 0.25        # Streuung der Periodendauer (Standardabweichung / Mittelwert)
PERIOD_CORR_MIN = 0.7       # Ähnlichkeit der Kurvenform je Periode (Median der Korrelation mit der mittleren Form)
TIME_FACTORS = {"s": 1.0, "sec": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9, "min": 60.0, "h": 3600.0}
_FFT = re.compile(r"^\s*FFT\s*\(\s*\{([^{}]+)\}\s*((?:;[^;()]*)*)\)\s*$", re.IGNORECASE)


class FourierError(ValueError):
    """Ungültige Fourier-Angabe (Text für den Nutzer)."""


@dataclass
class Spec:
    signal: str
    mode: str = "range"          # "range" = Frequenzbereich, "harm" = Harmonische
    fmin: float = 0.0
    fmax: float | None = None    # None = bis zur halben Abtastrate
    hmin: int = 1
    hmax: int = MAX_HARMONIC
    f0: float | None = None      # None = automatisch
    window: str = "auto"
    scale: str = "pct"           # "pct" = Anteil [%], "db" = Dämpfung [dB] gegenüber H1, "amp" = Amplitude
    view: str = "bar"            # "bar" = Balken an den Harmonischen, "line" = durchgehendes Spektrum (Frequenzbereich)

    def text(self) -> str:
        """Formeltext, z. B. FFT({U}; h=1..15; f0=auto; y=pct)."""
        f0 = "auto" if self.f0 is None else f"{self.f0:g}"
        win = "" if self.window == "auto" else f"; win={self.window}"
        if self.mode == "harm":
            return f"FFT({{{self.signal}}}; h={self.hmin}..{self.hmax}; f0={f0}; y={self.scale}{win})"
        fmax = "max" if self.fmax is None else f"{self.fmax:g}"
        view = "; plot=line" if self.view == "line" else ""
        return f"FFT({{{self.signal}}}; f={self.fmin:g}..{fmax}; f0={f0}; y={self.scale}{view}{win})"


def is_fft(text: str) -> bool:
    return bool(re.match(r"^\s*FFT\s*\(", text or "", re.IGNORECASE))


def _number(text: str, what: str) -> float:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        raise FourierError(t("Fourier: {what} ist keine Zahl: {value}", what=what, value=text.strip())) from None


def parse(text: str) -> Spec:
    """FFT(...)-Formeltext -> Spec (FourierError bei Fehlern)."""
    match = _FFT.match(text or "")
    if not match:
        raise FourierError(t("Fourier: Schreibweise FFT({Signal}; f=0..500) oder FFT({Signal}; h=0..15; f0=auto)."))
    spec = Spec(signal=match.group(1).strip())
    seen = set()
    for part in filter(None, (p.strip() for p in match.group(2).split(";"))):
        if "=" not in part:
            raise FourierError(t("Fourier: unbekannte Angabe {value}", value=part))
        key, value = (s.strip() for s in part.split("=", 1))
        key = key.lower()
        seen.add(key)
        if key == "f":
            lo, _sep, hi = value.partition("..")
            spec.mode = "range"
            spec.fmin = max(0.0, _number(lo or "0", "fmin"))
            spec.fmax = None if hi.strip().lower() in ("", "max") else _number(hi, "fmax")
            if spec.fmax is not None and spec.fmax <= spec.fmin:
                raise FourierError(t("Fourier: Frequenzbereich bis muss größer als von sein."))
        elif key == "h":
            lo, _sep, hi = value.partition("..")
            spec.mode = "harm"
            try:
                spec.hmin, spec.hmax = int(lo or 1), int(hi if hi.strip() else lo or MAX_HARMONIC)
            except ValueError:
                raise FourierError(t("Fourier: Harmonische als ganze Zahlen 1..15 angeben.")) from None
            spec.hmin = max(1, spec.hmin)                  # ältere Formeln mit h=0..: 0 gibt es nicht mehr
            if not 1 <= spec.hmin <= spec.hmax <= MAX_HARMONIC:
                raise FourierError(t("Fourier: Harmonische von 1 (Grundschwingung) bis höchstens 15, von <= bis."))
        elif key == "f0":
            spec.f0 = None if value.lower() in ("", "auto") else _number(value, "f0")
            if spec.f0 is not None and spec.f0 <= 0:
                raise FourierError(t("Fourier: Eigenfrequenz f0 muss größer als 0 Hz sein."))
        elif key in ("y", "anzeige", "scale"):
            value = value.lower().strip("[] ")
            spec.scale = {"%": "pct", "prozent": "pct", "anteil": "pct", "daempfung": "db", "dämpfung": "db",
                          "amplitude": "amp"}.get(value, value)
            if spec.scale not in SCALES:
                raise FourierError(t("Fourier: Anzeige y=pct (Anteil in %), y=db (Dämpfung in dB) oder y=amp "
                                     "(Amplitude)."))
        elif key in ("plot", "darstellung", "view"):
            value = value.lower()
            spec.view = {"bars": "bar", "balken": "bar", "spektrum": "line", "spectrum": "line",
                         "linie": "line"}.get(value, value)
            if spec.view not in VIEWS:
                raise FourierError(t("Fourier: Darstellung plot=bar (Balken) oder plot=line (Spektrum)."))
        elif key in ("win", "window", "fenster"):
            value = value.lower()
            spec.window = {"rechteck": "rect", "none": "rect", "keins": "rect"}.get(value, value)
            if spec.window not in WINDOWS:
                raise FourierError(t("Fourier: Fenster auto, hann oder rect."))
        else:
            raise FourierError(t("Fourier: unbekannte Angabe {value}", value=part))
    if spec.mode == "harm":
        spec.view = "bar"                              # Harmonische nach Nummer: immer Balken
    return spec


def time_factor(x_unit: str) -> float:
    return TIME_FACTORS.get((x_unit or "s").strip().lower(), 1.0)


def uniform(x: np.ndarray, y: np.ndarray, x_unit: str = "s") -> tuple[np.ndarray, float, float]:
    """Gleichmäßig abgetastete Werte, Abtastabstand und Startzeit in Sekunden (NaN überbrückt, ungleichmäßig ->
    interpoliert)."""
    factor = time_factor(x_unit)
    x = np.asarray(x, dtype=np.float64) * factor
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 4:
        raise FourierError(t("Fourier: zu wenige gültige Werte (mindestens 4)."))
    order = np.argsort(x, kind="stable")
    x, y = x[order], y[order]
    steps = np.diff(x)
    steps = steps[steps > 0]
    if not steps.size:
        raise FourierError(t("Fourier: X-Achse ohne Zeitverlauf."))
    dt = float(np.median(steps))
    if np.max(np.abs(steps - dt)) > 0.01 * dt or steps.size != x.size - 1:   # ungleichmäßig: neu abtasten
        count = int(round((x[-1] - x[0]) / dt)) + 1
        grid = x[0] + dt * np.arange(count)
        y = np.interp(grid, x, y)
    return y, dt, float(x[0])


def spectrum(y: np.ndarray, dt: float, window: str = "hann") -> tuple[np.ndarray, np.ndarray]:
    """Einseitiges Amplitudenspektrum: (Frequenzen [Hz], Amplituden als Spitzenwert; 0 Hz = Mittelwert)."""
    n = y.size
    if window in ("hann", "auto"):
        w = np.hanning(n)
        gain = w.sum() / n                      # kohärenter Gewinn (0,5) -> Amplitude korrigieren
    else:
        w, gain = np.ones(n), 1.0
    values = np.fft.rfft(y * w)
    amp = np.abs(values) / (n * gain)
    amp[1:] *= 2.0
    if n % 2 == 0:
        amp[-1] /= 2.0                          # Nyquist-Linie nur einmal
    return np.fft.rfftfreq(n, dt), amp


def _peak(freqs: np.ndarray, amp: np.ndarray, target: float, width: int) -> float:
    """Größte Amplitude im Fenster ±width Linien um die Zielfrequenz (Leckeffekt)."""
    df = freqs[1] - freqs[0]
    k = int(round(target / df))
    lo, hi = max(1, k - width), min(amp.size - 1, k + width)
    return float(np.max(amp[lo:hi + 1])) if lo <= hi else float("nan")


def fundamental(freqs: np.ndarray, amp: np.ndarray) -> float:
    """Eigenfrequenz: stärkste Linie ohne Gleichanteil, parabolisch verfeinert."""
    if amp.size < 3:
        raise FourierError(t("Fourier: Spektrum zu kurz für eine Eigenfrequenz."))
    k = int(np.argmax(amp[1:])) + 1
    if 1 <= k < amp.size - 1:
        a, b, c = amp[k - 1], amp[k], amp[k + 1]
        denom = a - 2 * b + c
        shift = 0.5 * (a - c) / denom if denom else 0.0
        return float((k + max(-0.5, min(0.5, shift))) * (freqs[1] - freqs[0]))
    return float(freqs[k])


def _sine_fit(values: np.ndarray, dt: float, f: float, trend: bool = True) -> tuple[float, np.ndarray]:
    """Ausgleich values ~ c0 (+ c1*t) + a*sin + b*cos bei Frequenz f: (Restfehler, Koeffizienten)."""
    tt = np.arange(values.size) * dt
    cols = [np.ones(values.size)] + ([tt - tt.mean()] if trend else []) + \
           [np.sin(2 * np.pi * f * tt), np.cos(2 * np.pi * f * tt)]
    design = np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(design, values, rcond=None)
    rest = values - design @ coef
    return float(rest @ rest), coef


def estimate_f0(values: np.ndarray, dt: float) -> float:
    """Eigenfrequenz auch bei wenigen Schwingungen und Gleichanteil (z. B. Drehzahl ohne Nulldurchgang): grobe
    Spitze im Spektrum (Gleichanteil entfernt, 8-fach aufgefüllt), dann Sinus-Ausgleich mit Offset und Trend."""
    n = values.size
    y0 = values - float(np.mean(values))
    pad = 8 * n
    win = np.hanning(n)
    amp = np.abs(np.fft.rfft(y0 * win, pad))
    freqs = np.fft.rfftfreq(pad, dt)
    span = 1.0 / (n * dt)                              # eine Schwingung in der Messung
    valid = freqs >= 0.75 * span
    if not np.any(valid) or amp.size < 3:
        raise FourierError(t("Fourier: Spektrum zu kurz für eine Eigenfrequenz."))
    k = int(np.argmax(np.where(valid, amp, -1.0)))
    coarse = float(freqs[k])
    if n < 16:
        return coarse
    grid = np.linspace(max(0.5 * span, 0.6 * coarse), 1.4 * coarse, 81)
    errors = [_sine_fit(values, dt, f)[0] for f in grid]
    best = int(np.argmin(errors))
    lo, hi = grid[max(0, best - 1)], grid[min(grid.size - 1, best + 1)]
    for _ in range(30):                                # Goldener Schnitt im engen Intervall
        m1, m2 = lo + 0.382 * (hi - lo), lo + 0.618 * (hi - lo)
        if _sine_fit(values, dt, m1)[0] < _sine_fit(values, dt, m2)[0]:
            hi = m2
        else:
            lo = m1
    return float(0.5 * (lo + hi))


def remove_trend(values: np.ndarray, dt: float, f0: float) -> np.ndarray:
    """Linearen Trend entfernen, ohne die Schwingung zu verfälschen: Trend gemeinsam mit dem Sinus bei f0 ausgleichen
    (eine Gerade allein würde bei wenigen Schwingungen einen Teil der Schwingung schlucken)."""
    if values.size < 8 or f0 <= 0:
        return values
    _err, coef = _sine_fit(values, dt, f0)
    tt = np.arange(values.size) * dt
    return values - coef[1] * (tt - tt.mean())


def detect_periods(values: np.ndarray, dt: float, f0: float) -> dict:
    """Perioden über die steigenden Nulldurchgänge der Grundschwingung (Bandpass 0,5..1,5 * f0).
    Liefert crossings (Bruchteil-Indizes), count, cv, corr, periodic, reason."""
    n = values.size
    y0 = values - float(np.mean(values))
    freqs = np.fft.rfftfreq(n, dt)
    spec = np.fft.rfft(y0)
    band = (freqs >= 0.5 * f0) & (freqs <= 1.5 * f0)
    base = np.fft.irfft(np.where(band, spec, 0), n)
    rising = np.where((base[:-1] < 0) & (base[1:] >= 0))[0]
    crossings = []
    minimum = 0.5 / (f0 * dt)                          # Störungen: Nulldurchgänge näher als eine halbe Periode
    for i in rising:
        c = i + base[i] / (base[i] - base[i + 1])
        if not crossings or c - crossings[-1] >= minimum:
            crossings.append(float(c))
    if not crossings:                                  # Bandpass ohne Durchgang (z. B. sehr wenige Schwingungen)
        crossings = _fit_crossings(values, dt, f0)
    for _ in range(3):                                 # Nachbarn verfeinert -> Periodendauer genauer
        crossings = _refine(values, crossings, 1.0 / (f0 * dt))
    crossings = _edges(values, dt, f0, crossings)
    out = {"crossings": crossings, "count": max(0, len(crossings) - 1), "cv": float("nan"), "corr": float("nan"),
           "periodic": False, "reason": ""}
    if out["count"] < 1:
        out["reason"] = t("keine ganze Periode gefunden")
        return out
    lengths = np.diff(crossings)
    out["cv"] = float(np.std(lengths) / np.mean(lengths)) if lengths.size > 1 else 0.0
    index = np.arange(n)
    shapes = []
    for a, b in zip(crossings[:-1], crossings[1:]):
        shape = np.interp(np.linspace(a, b, 64, endpoint=False), index, values)
        shape = shape - shape.mean()
        norm = np.linalg.norm(shape)
        shapes.append(shape / norm if norm > 0 else shape)
    shapes = np.array(shapes)
    mean = shapes.mean(axis=0)
    norm = np.linalg.norm(mean)
    out["corr"] = float(np.median(shapes @ (mean / norm))) if norm > 0 else 0.0
    if out["cv"] > PERIOD_CV_MAX:
        out["reason"] = t("Periodendauer streut zu stark ({cv} %)", cv=f"{out['cv'] * 100:.0f}")
    elif out["corr"] < PERIOD_CORR_MIN:
        out["reason"] = t("Kurvenform der Perioden zu unterschiedlich (Korrelation {corr})", corr=f"{out['corr']:.2f}")
    else:
        out["periodic"] = True
    return out


def _fit_crossings(values: np.ndarray, dt: float, f0: float) -> list[float]:
    """Steigende Durchgänge durch den Mittelwert aus dem Sinus-Ausgleich über die ganze Messung."""
    _err, coef = _sine_fit(values, dt, f0)
    a, b = coef[-2], coef[-1]                          # a*sin(wt) + b*cos(wt) = R*sin(wt + phase)
    phase = np.arctan2(b, a)
    period = 1.0 / (f0 * dt)
    first = (-phase / (2 * np.pi)) % 1.0 * period
    return [float(c) for c in np.arange(first, values.size - 1 + 1e-9, period)]


def _edges(values: np.ndarray, dt: float, f0: float, crossings: list[float]) -> list[float]:
    """Durchgang genau am Anfang oder Ende der Messung (Signal startet z. B. auf dem Mittelwert): eine Periode vor dem
    ersten bzw. nach dem letzten Durchgang zulassen, wenn er höchstens 2 % der Periode außerhalb liegt, verfeinern und
    nur behalten, wenn die Periode vollständig in den Abtastwerten liegt (Ende darf auf Index n liegen: der Endpunkt
    gehört zur nächsten Periode). Kleine Überstände (0,1 % der Periode) werden auf den Rand gesetzt."""
    if not crossings:
        return crossings
    n = values.size
    period = (crossings[-1] - crossings[0]) / (len(crossings) - 1) if len(crossings) > 1 else 1.0 / (f0 * dt)
    tol = max(1.0, 0.02 * period)
    out, added = list(crossings), False
    before = out[0] - period
    if -tol <= before <= tol and before < out[0] - 0.5 * period:
        out.insert(0, before)
        added = True
    after = out[-1] + period
    if n - tol <= after <= n + tol:
        out.append(after)
        added = True
    if added:
        out = _refine(values, out, period)
    snap = max(0.05, 0.001 * period)
    if out and out[0] < 0:
        out = out[1:] if out[0] < -snap else [0.0] + out[1:]
    if out and out[-1] > n:
        out = out[:-1] if out[-1] > n + snap else out[:-1] + [float(n)]
    return out


def _refine(values: np.ndarray, crossings: list[float], period: float) -> list[float]:
    """Nulldurchgänge der Grundschwingung genauer: je Durchgang Sinus-Ausgleich über eine Periode am Rohsignal
    (Oberwellen sind über eine Periode orthogonal) und dort der steigende Nulldurchgang der Grundschwingung."""
    n = values.size
    out = []
    for k, c in enumerate(crossings):
        local = period
        if 0 < k < len(crossings) - 1:
            local = 0.5 * (crossings[k + 1] - crossings[k - 1])
        elif len(crossings) > 1:
            local = abs(crossings[1] - crossings[0]) if k == 0 else abs(crossings[-1] - crossings[-2])
        for _ in range(2):
            lo = c - local / 2
            lo = min(max(0.0, lo), max(0.0, n - 1 - local))
            idx = np.arange(int(np.ceil(lo)), int(np.floor(min(n - 1, lo + local))) + 1)
            if idx.size < 8:
                break
            w = 2 * np.pi / local
            design = np.column_stack([np.sin(w * (idx - c)), np.cos(w * (idx - c)), np.ones(idx.size)])
            (a, b, _c0), *_ = np.linalg.lstsq(design, values[idx], rcond=None)
            phase = np.arctan2(b, a)                       # values ~ R*sin(w*(i-c) + phase)
            shift = -phase / w
            if abs(shift) > local / 2:
                break
            c = c + shift
        out.append(float(c))
    return out


def _amplitudes(seg: np.ndarray) -> np.ndarray:
    """Amplituden der DFT-Linien eines Abschnitts (Rechteck): [0] = Mittelwert, [k] = k-te Linie (Spitzenwert)."""
    a = np.abs(np.fft.rfft(seg)) / seg.size
    a[1:] *= 2.0
    if seg.size % 2 == 0:
        a[-1] /= 2.0
    return a


def _thd(amps: np.ndarray) -> float:
    """THD in % aus den Amplituden der Harmonischen 1..n (Index 0 = Grundschwingung)."""
    if amps.size < 2 or not np.isfinite(amps[0]) or amps[0] <= 0:
        return float("nan")
    rest = amps[1:][np.isfinite(amps[1:])]
    return float(np.sqrt(np.sum(rest ** 2)) / amps[0] * 100.0)


def shares(energy: np.ndarray) -> np.ndarray:
    """Anteile an der Summe (Summe 1); Summe 0 -> alle 0."""
    energy = np.nan_to_num(np.asarray(energy, dtype=np.float64))
    total = float(energy.sum())
    return energy / total if total > 0 else np.zeros_like(energy)


def select(info: dict, lo: float | None = None, hi: float | None = None) -> tuple[np.ndarray, list[int]]:
    """Energien der Harmonischen (info["harm"]["numbers"]) für die Perioden zwischen den Markern (Mitte der Periode
    in [lo, hi], X in der Einheit des Grundsignals); ohne Marker alle. Liefert (Energien, Nummern der Perioden ab 1)."""
    harm = info.get("harm") or {}
    energy = np.asarray(harm.get("energy") or [], dtype=np.float64)
    bounds = harm.get("bounds") or []
    if energy.ndim != 2 or not len(bounds):            # nicht periodisch: Ergebnis über das ganze Signal
        return np.asarray(harm.get("total") or [], dtype=np.float64), []
    if lo is None or hi is None:
        chosen = list(range(len(bounds)))
    else:
        lo, hi = min(lo, hi), max(lo, hi)
        chosen = [i for i, (a, b) in enumerate(bounds) if lo <= 0.5 * (a + b) <= hi]
    if not chosen:
        return np.zeros(energy.shape[1]), []
    return energy[chosen].sum(axis=0), [i + 1 for i in chosen]


def display(energy: np.ndarray, scale: str, count: int = 1) -> np.ndarray:
    """Balkenwerte aus den Energien der Harmonischen 1..N (Summe über count Perioden): Anteil in %, Dämpfung in dB
    gegenüber H1 oder Amplitude (Effektivwert der Amplituden über die Perioden)."""
    energy = np.nan_to_num(np.asarray(energy, dtype=np.float64))
    if scale == "amp":
        return np.sqrt(energy / max(1, count))
    if scale == "db":
        if not energy.size or energy[0] <= 0:
            return np.full(energy.size, np.nan)
        with np.errstate(divide="ignore"):
            out = 10.0 * np.log10(energy[0] / np.where(energy > 0, energy, np.nan))
        return np.where(np.isfinite(out), np.minimum(out, DB_FLOOR), DB_FLOOR)
    return shares(np.sqrt(energy)) * 100.0             # Anteil der Amplitude an der Summe der Amplituden


def scale_line(amp: np.ndarray, a1: float, scale: str) -> np.ndarray:
    """Durchgehendes Spektrum: Amplitude, % von A1 oder Dämpfung gegenüber A1 (dB)."""
    if scale == "amp":
        return amp
    if not np.isfinite(a1) or a1 <= 0:
        return np.full(amp.size, np.nan)
    if scale == "pct":
        return amp / a1 * 100.0
    with np.errstate(divide="ignore"):
        out = 20.0 * np.log10(a1 / np.where(amp > 0, amp, np.nan))
    return np.where(np.isfinite(out), np.minimum(out, DB_FLOOR), DB_FLOOR)


def line_spectrum(info: dict, chosen: list[int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Durchgehendes Spektrum (Frequenzbereich, plot=line) über die gewählten Perioden (Nummern ab 1, zusammen-
    hängend vom ersten bis zum letzten) bzw. über alle ganzen Perioden / das ganze Signal."""
    data = info.get("line") or {}
    values, dt = data.get("values"), data.get("dt", 1.0)
    if values is None:
        return np.array([]), np.array([])
    crossings = data.get("crossings") or []
    window = info.get("window", "hann")
    if chosen and crossings:
        a, b = crossings[chosen[0] - 1], crossings[chosen[-1]]
        length = b - a
        count = chosen[-1] - chosen[0] + 1
        size = max(8, int(round(length)))
        seg = np.interp(a + length * np.arange(size) / size, np.arange(values.size), values)
        f0 = count / (length * dt)
        freqs, amp = spectrum(seg, length * dt / size, window)
        k = count                                      # Linie der Grundschwingung
    else:
        seg = values[data["i0"]:data["i1"]]
        freqs, amp = spectrum(seg, dt, window)
        f0 = info.get("f0", 0.0)
        k = data.get("count") or int(round(f0 / (freqs[1] - freqs[0]))) if freqs.size > 1 else 0
    a1 = float(amp[k]) if 0 < k < amp.size else float("nan")
    lo, hi = data.get("fmin", 0.0), data.get("fmax")
    hi = freqs[-1] if hi is None else hi
    mask = (freqs >= lo) & (freqs <= hi)
    return freqs[mask], scale_line(amp[mask], a1, info.get("scale", "amp"))


def compute(x: np.ndarray, y: np.ndarray, x_unit: str, spec: Spec) -> dict:
    """Ergebnis: x, y, x_name, x_unit, y_unit sowie info (f0, Auflösung, Periodizität, Tabelle, Daten je Periode)."""
    values, dt, t0 = uniform(x, y, x_unit)
    values_all = values
    factor = time_factor(x_unit)
    index = np.arange(values.size)
    f0 = spec.f0 if spec.f0 is not None else estimate_f0(values, dt)   # Gleichanteil/Offset stört nicht
    df_full = 1.0 / (values.size * dt)
    if f0 * values.size * dt < 1.0:                               # weniger als eine Schwingung in der Messung
        raise FourierError(t("Fourier: Grundfrequenz {f0} Hz ergibt weniger als eine Schwingung in der Messung "
                             "(Auflösung {df} Hz).", f0=f"{f0:.4g}", df=f"{df_full:.4g}"))
    values = remove_trend(values, dt, f0)                         # Trend gehört nicht zur Schwingung
    values_all = values
    period = detect_periods(values, dt, f0)
    info = {"fs": 1.0 / dt, "n": values.size, "periodic": period["periodic"], "reason": period["reason"],
            "periods": period["count"] if period["periodic"] else 0, "candidates": period["count"],
            "cv": period["cv"], "corr": period["corr"], "x_unit": x_unit or "s"}
    crossings = [int(round(c)) for c in period["crossings"]]
    if period["periodic"]:                             # nur ganze Perioden: erster bis letzter Nulldurchgang
        i0, i1 = crossings[0], crossings[-1]
        seg, count = values[i0:i1], period["count"]
        f0 = count / (seg.size * dt)                   # mittlere Grundfrequenz der ganzen Perioden
        window = "rect" if spec.window == "auto" else spec.window
        info["start"], info["duration"] = t0 + i0 * dt, seg.size * dt
    else:
        seg, count = values, 0
        window = "hann" if spec.window == "auto" else spec.window
        info["start"], info["duration"] = t0, values.size * dt
    freqs, amp = spectrum(seg, dt, window)
    df = float(freqs[1] - freqs[0]) if freqs.size > 1 else 0.0
    info.update(f0=f0, df=df, window=window)
    nyquist = 0.5 / dt
    if spec.mode == "harm":                            # Harmonische 1 (= f0) .. 15
        limit = MAX_HARMONIC
    else:                                              # Frequenzbereich: alle Harmonischen bis fmax
        fmax = nyquist if spec.fmax is None else min(spec.fmax, nyquist)
        limit = max(1, min(MAX_RANGE_HARMONIC, int(fmax / f0 + 0.01)))
    numbers = list(range(1, limit + 1))

    def at(n: int) -> float:                           # Amplitude der n-ten Harmonischen (n * f0)
        target = n * f0
        if target > freqs[-1]:
            return float("nan")
        if count:
            k = count * n
            return float(amp[k]) if k < amp.size else float("nan")
        return _peak(freqs, amp, target, 2 if window == "hann" else 1)

    total_amps = np.array([at(n) for n in numbers])
    per_amps, bounds, rows = [], [], []
    if period["periodic"]:
        exact = period["crossings"]                    # Bruchteil-Indizes: Periode exakt neu abtasten
        for number, (a, b) in enumerate(zip(exact[:-1], exact[1:]), 1):
            length = b - a
            size = max(8, int(round(length)))
            if length < 4:
                continue
            piece = np.interp(a + length * np.arange(size) / size, index, values)
            lines = _amplitudes(piece)                 # DFT über genau eine Periode: Linie n = n-te Harmonische
            amps = np.array([float(lines[n]) if n < lines.size // 1 and n < size // 2 else float("nan")
                             for n in numbers])
            per_amps.append(amps)
            start = (t0 + a * dt) / factor             # Periodengrenzen in der X-Einheit des Signals (Marker)
            bounds.append((start, (t0 + b * dt) / factor))
            rows.append((number, t0 + a * dt, length * dt * 1000, 1.0 / (length * dt), float(lines[0]), amps))
    energy = [np.nan_to_num(a) ** 2 for a in per_amps]
    total_energy = np.sum(energy, axis=0) if energy else np.nan_to_num(total_amps) ** 2
    if spec.mode == "harm":
        shown = [n for n in range(spec.hmin, spec.hmax + 1) if n * f0 <= nyquist]
    else:
        shown = [n for n in numbers if spec.fmin - 0.01 * f0 <= n * f0 <= fmax + 0.01 * f0]
    if not shown:
        raise FourierError(t("Fourier: keine Harmonische von f0 = {f0} Hz im gewählten Bereich (bis {nyq} Hz).",
                             f0=f"{f0:.4g}", nyq=f"{nyquist:.4g}"))
    info["harm"] = {"numbers": numbers, "energy": [e.tolist() for e in energy], "bounds": bounds,
                    "total": np.asarray(total_energy).tolist(), "amps": [a.tolist() for a in per_amps]}
    info["shown"], info["scale"], info["mode"], info["view"] = shown, spec.scale, spec.mode, spec.view

    # Tabelle: Werte der Harmonischen in der gewählten Anzeige, Amplitude der Grundschwingung A1, THD
    unit = {"pct": "%", "db": "dB"}.get(spec.scale, "A")
    table_cols = shown[:20]
    columns = [t("Periode"), t("Start [s]"), t("Dauer [ms]"), "f [Hz]", "DC", "A1"] + \
              [f"H{n} [{unit}]" for n in table_cols] + ["THD [%]"]

    def row(label, start, dur, freq, dc, amps, energy_row, count=1):
        part = display(energy_row, spec.scale, count)
        return [label, start, dur, freq, dc, float(amps[0])] + [float(part[n - 1]) for n in table_cols] + \
               [_thd(amps)]
    rows_all = row(t("Alle"), info["start"], info["duration"] * 1000, f0, float(amp[0]),
                   np.sqrt(total_energy / max(1, len(energy))) if energy else total_amps, total_energy,
                   max(1, len(energy)))
    table_rows = [row(n, start, dur, freq, dc, amps, np.nan_to_num(amps) ** 2)
                  for n, start, dur, freq, dc, amps in rows]
    stats = []
    if table_rows:                                     # Mittel, Minimum, Maximum über die einzelnen Perioden
        data = np.array([r[2:] for r in table_rows], dtype=np.float64)
        with np.errstate(all="ignore"):
            for label, func in ((t("Mittel"), np.nanmean), (t("Min"), np.nanmin), (t("Max"), np.nanmax)):
                stats.append([label, float("nan")] + [float(v) for v in func(data, axis=0)])
    info["table"] = {"columns": columns, "all": rows_all, "stats": stats, "rows": table_rows}

    total, chosen_all = select(info)
    values = display(total, spec.scale, max(1, len(chosen_all)))
    ys = np.array([values[n - 1] for n in shown])
    unit = {"pct": "%", "db": "dB"}.get(spec.scale)   # None = Einheit des Signals (Amplitude)
    if spec.mode == "range" and spec.view == "line":   # durchgehendes Spektrum
        info["line"] = {"values": values_all, "dt": dt, "crossings": list(period["crossings"]) if count else [],
                        "i0": crossings[0] if count else 0, "i1": crossings[-1] if count else values_all.size,
                        "count": count, "fmin": spec.fmin, "fmax": spec.fmax}
        fx, fy = line_spectrum(info)
        if not fx.size:
            raise FourierError(t("Fourier: keine Frequenzlinie zwischen {lo} und {hi} Hz (Auflösung {df} Hz, bis "
                                 "{nyq} Hz).", lo=f"{spec.fmin:g}", hi=f"{spec.fmax or nyquist:g}", df=f"{df:.4g}",
                                 nyq=f"{nyquist:.4g}"))
        return {"x": fx, "y": fy, "x_name": t("Frequenz"), "x_unit": "Hz", "y_unit": unit, "plot_style": "line",
                "info": info}
    if spec.mode == "harm":
        return {"x": np.array(shown, dtype=float), "y": ys, "x_name": t("Harmonische"), "x_unit": "", "y_unit": unit,
                "bar_width": 0.6, "plot_style": "bar", "info": info}
    return {"x": np.array(shown, dtype=float) * f0, "y": ys, "x_name": t("Frequenz"), "x_unit": "Hz", "y_unit": unit,
            "bar_width": 0.6 * f0, "plot_style": "bar", "info": info}
