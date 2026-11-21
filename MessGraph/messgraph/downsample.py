"""Downsampling beim Einlesen von MF4 und Parquet.

Die Datenreduktion beim Zeichnen (measure.decimate) bleibt davon unabhängig. Downsampling hier verkleinert
die Daten im Speicher und damit auch die Grundlage der Messwerte; die Wahl der Methode bestimmt, was
erhalten bleibt:

- minmax: je Block Minimum und Maximum in zeitlicher Reihenfolge, Spitzen bleiben erhalten
- mean:   je Block der Mittelwert, glättet Rauschen (wirkt wie ein Tiefpass)
- stride: jeder n-te Wert, schnell, kann kurze Spitzen verlieren
- grid:   festes Zeitraster, Mittelwert je Rasterintervall; Lücken bleiben Lücken
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from .i18n import t

APPLIES_TO = (".mf4", ".mdf", ".blf", ".parquet")
METHODS = ["minmax", "mean", "stride", "grid"]
METHOD_NAMES = {"minmax": "Min/Max je Block (Spitzen bleiben)", "mean": "Mittelwert je Block (glättet)",
                "stride": "Jeder n-te Wert (schnell)", "grid": "Festes Zeitraster (Mittelwert)"}
MODES = ["off", "auto", "manual"]
MODE_NAMES = {"off": "Aus (volle Auflösung)", "auto": "Automatisch", "manual": "Manuell"}


@dataclass
class DownsampleConfig:
    mode: str = "auto"
    auto_threshold: int = 2_000_000     # ab so vielen Werten je Signal wird automatisch reduziert
    auto_target: int = 500_000          # ... auf etwa so viele Werte (Min/Max, Spitzen bleiben)
    method: str = "minmax"
    factor: int = 10                    # Blockgröße bzw. n für manuelle Block-Methoden
    interval: float = 0.01              # Zeitraster in X-Einheiten (meist s)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "DownsampleConfig":
        cfg = cls()
        for key, value in (data or {}).items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.mode not in MODES:
            self.mode = "auto"
        if self.method not in METHODS:
            self.method = "minmax"
        self.auto_threshold = max(1000, int(self.auto_threshold))
        self.auto_target = max(100, min(int(self.auto_target), self.auto_threshold))
        self.factor = max(2, int(self.factor))
        self.interval = float(self.interval) if float(self.interval) > 0 else 0.01

    def describe(self) -> str:
        if self.mode == "off":
            return t("Downsampling: aus")
        if self.mode == "auto":
            return t("Downsampling: automatisch ab {threshold} Werten auf etwa {target} (Min/Max)",
                     threshold=f"{self.auto_threshold:,}".replace(",", "."), target=f"{self.auto_target:,}".replace(",", "."))
        if self.method == "grid":
            return t("Downsampling: Zeitraster {interval}", interval=f"{self.interval:g}")
        return t("Downsampling: {method}, Faktor {factor}", method=t(METHOD_NAMES[self.method]), factor=self.factor)


_config = DownsampleConfig()


def set_config(config: DownsampleConfig) -> None:
    global _config
    _config = config


def config() -> DownsampleConfig:
    return _config


def applies(path: str) -> bool:
    return str(path).lower().endswith(APPLIES_TO)


# ---------------------------------------------------------------- Verfahren
def _blocks(n: int, size: int) -> tuple[int, int]:
    count = n // size
    return count, count * size


def minmax(x: np.ndarray, y: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray]:
    """Je Block Minimum und Maximum an ihrer echten Zeit, zeitlich geordnet; Rest bleibt unverändert."""
    count, end = _blocks(x.size, size)
    if count == 0:
        return x, y
    yb = y[:end].reshape(count, size)
    filled = np.where(np.isnan(yb), np.inf, yb)
    lo = np.argmin(filled, axis=1)
    hi = np.argmax(np.where(np.isnan(yb), -np.inf, yb), axis=1)
    all_nan = np.isnan(yb).all(axis=1)
    rows = np.arange(count)
    first = np.minimum(lo, hi)
    second = np.maximum(lo, hi)
    idx = np.empty(count * 2, dtype=np.int64)
    idx[0::2] = rows * size + first
    idx[1::2] = rows * size + second
    out_x, out_y = x[idx], y[idx]
    out_y[np.repeat(all_nan, 2)] = np.nan          # Messlücke bleibt Lücke
    keep = np.ones(idx.size, dtype=bool)
    keep[1::2] = second != first                    # konstanter Block: ein Punkt genügt
    return np.concatenate((out_x[keep], x[end:])), np.concatenate((out_y[keep], y[end:]))


def mean(x: np.ndarray, y: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray]:
    count, end = _blocks(x.size, size)
    if count == 0:
        return x, y
    def nanmean_rows(block):
        ok = np.isfinite(block)
        n = ok.sum(axis=1)
        total = np.where(ok, block, 0.0).sum(axis=1)
        return np.where(n > 0, total / np.maximum(n, 1), np.nan)   # Block ohne Werte bleibt Lücke

    out_x = x[:end].reshape(count, size).mean(axis=1)
    out_y = nanmean_rows(y[:end].reshape(count, size))
    if end < x.size:  # angebrochener letzter Block
        out_x = np.append(out_x, x[end:].mean())
        out_y = np.append(out_y, nanmean_rows(y[end:].reshape(1, -1))[0])
    return out_x, out_y


def stride(x: np.ndarray, y: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    if x.size <= n:
        return x, y
    idx = np.arange(0, x.size, n)
    if idx[-1] != x.size - 1:
        idx = np.append(idx, x.size - 1)            # letzter Wert bleibt, damit der Zeitbereich stimmt
    return x[idx], y[idx]


def grid(x: np.ndarray, y: np.ndarray, interval: float) -> tuple[np.ndarray, np.ndarray]:
    """Mittelwert je Rasterintervall; Intervalle ohne Werte entfallen (Lücke im Graphen)."""
    if x.size < 2 or not np.isfinite(interval) or interval <= 0:
        return x, y
    start = x[0]
    bins = np.floor((x - start) / interval).astype(np.int64)
    ok = np.isfinite(y)
    count = np.bincount(bins[ok], minlength=bins[-1] + 1)
    total = np.bincount(bins[ok], weights=y[ok], minlength=bins[-1] + 1)
    present = np.bincount(bins, minlength=bins[-1] + 1) > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        values = total / count
    centers = start + (np.arange(values.size) + 0.5) * interval
    return centers[present], values[present]


def apply(x: np.ndarray, y: np.ndarray, cfg: DownsampleConfig | None = None) -> tuple[np.ndarray, np.ndarray, str]:
    """Liefert (x, y, Hinweis). Hinweis ist leer, wenn nichts reduziert wurde."""
    cfg = cfg or _config
    n = x.size
    if cfg.mode == "off" or n < 4:
        return x, y, ""
    if cfg.mode == "auto":
        if n <= cfg.auto_threshold:
            return x, y, ""
        size = max(2, math.ceil(2 * n / cfg.auto_target))   # Min/Max liefert zwei Punkte je Block
        nx, ny = minmax(x, y, size)
        method = "minmax"
    elif cfg.method == "grid":
        nx, ny = grid(x, y, cfg.interval)
        method = "grid"
    else:
        nx, ny = {"minmax": minmax, "mean": mean, "stride": stride}[cfg.method](x, y, cfg.factor)
        method = cfg.method
    if nx.size >= n:
        return x, y, ""
    note = t("reduziert ({method}): {before} -> {after} Werte", method=t(METHOD_NAMES[method]).split(" (")[0],
             before=f"{n:,}".replace(",", "."), after=f"{nx.size:,}".replace(",", "."))
    return nx, ny, note
