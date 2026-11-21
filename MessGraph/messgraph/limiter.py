"""Limiter: Daten einer Datei auf die Abschnitte reduzieren, in denen Führungssignale in ihren Grenzen liegen.

Beispiel: Ein Rechtecksignal einer Datei; nur der obere Anteil (z. B. Wert >= 4.5) soll gelten. Die Regel
"Datei, Signal, Min, Max" ergibt eine Maske über die Zeit. Sie gilt für alle Signale derselben Datei: Werte
außerhalb entfallen (Datenmenge kleiner), an den Lücken trennt ein NaN-Punkt die Linie, damit nichts über die
entfernten Abschnitte hinweg verbunden wird. Mehrere Regeln einer Datei werden UND-verknüpft.

Die Zeitbasen der Signale können verschieden sein (MF4): Die Maske eines Führungssignals gilt zwischen seinen
Abtastpunkten unverändert weiter (Halten des letzten Werts), vor dem ersten Punkt ist sie aus.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .data_model import LoadError
from .i18n import t

FORMAT = "messgraph_limiter"
SUFFIXES = (".yaml", ".yml")


@dataclass
class Rule:
    file: str                       # Dateiname (auch Muster wie lauf_*.csv) oder * für alle Dateien
    signal: str                     # Signalname
    lo: float | None = None         # untere Grenze (einschließlich), None = keine
    hi: float | None = None         # obere Grenze (einschließlich), None = keine
    enabled: bool = True

    @property
    def usable(self) -> bool:
        return self.enabled and bool(self.signal) and (self.lo is not None or self.hi is not None) and \
            (self.lo is None or self.hi is None or self.hi >= self.lo)

    def matches_file(self, name: str) -> bool:
        pattern = (self.file or "*").strip()
        return pattern == "*" or pattern == name or fnmatch.fnmatchcase(name, pattern)

    def key(self) -> tuple:
        return (self.file, self.signal, self.lo, self.hi, self.enabled)


@dataclass
class LimiterConfig:
    rules: list[Rule] = field(default_factory=list)
    active: bool = True
    path: str | None = None

    def rules_for(self, file_name: str) -> list[Rule]:
        return [r for r in self.rules if r.usable and r.matches_file(file_name)] if self.active else []


def mask(y: np.ndarray, lo: float | None, hi: float | None) -> np.ndarray:
    """True, wo der Wert in den Grenzen liegt (NaN ist außerhalb)."""
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(y)
    if lo is not None:
        ok &= y >= lo
    if hi is not None:
        ok &= y <= hi
    return ok


def held(rule_x: np.ndarray, rule_mask: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Maske eines Führungssignals auf eine andere Zeitbasis übertragen (letzten Zustand halten)."""
    if rule_x.size == 0:
        return np.zeros(x.shape, dtype=bool)
    if rule_x.shape == x.shape and np.array_equal(rule_x, x):
        return rule_mask.copy()
    idx = np.searchsorted(rule_x, x, side="right") - 1
    out = np.zeros(x.shape, dtype=bool)
    inside = idx >= 0
    out[inside] = rule_mask[idx[inside]]
    return out


def apply(x: np.ndarray, y: np.ndarray, guides: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    """Nur die Punkte behalten, an denen alle Führungsmasken zutreffen; Lücken durch einen NaN-Punkt trennen."""
    keep = np.ones(x.shape, dtype=bool)
    for rule_x, rule_mask in guides:
        keep &= held(rule_x, rule_mask, x)
    idx = np.flatnonzero(keep)
    if idx.size == 0:                               # nichts im Limit: ein leerer Punkt, damit nichts gezeichnet wird
        return (x[:1].copy() if x.size else np.zeros(1)), np.full(1, np.nan)
    xk, yk = x[idx], y[idx]
    breaks = np.flatnonzero(np.diff(idx) > 1)
    if breaks.size:
        mids = (x[idx[breaks]] + x[idx[breaks + 1]]) / 2.0
        xk = np.insert(xk, breaks + 1, mids)
        yk = np.insert(yk.astype(np.float64), breaks + 1, np.nan)
    return xk, yk


def kept_share(guides: list[tuple[np.ndarray, np.ndarray]]) -> float | None:
    """Anteil der Messzeit im Limit (alle Regeln zugleich), auf der dichtesten Zeitbasis der Führungssignale."""
    if not guides:
        return None
    base = max((g[0] for g in guides), key=lambda a: a.size)
    if base.size < 2:
        return None
    keep = np.ones(base.shape, dtype=bool)
    for rule_x, rule_mask in guides:
        keep &= held(rule_x, rule_mask, base)
    dt = np.diff(base)
    total = float(dt.sum())
    return float(dt[keep[:-1]].sum()) / total if total > 0 else float(keep.mean())


# ---------------------------------------------------------------- Datei
def _number(value, where: str) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return float(str(value).replace(",", ".")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        raise LoadError(t("Limiter: ungültige Zahl {value} bei {where}", value=value, where=where)) from None


def from_dict(data: dict) -> LimiterConfig:
    section = data.get("limiter") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        raise LoadError(t("Keine Limiter-Konfiguration (Abschnitt \"limiter\" fehlt)."))
    rules = []
    for number, item in enumerate(section.get("rules") or [], 1):
        if not isinstance(item, dict) or not str(item.get("signal", "")).strip():
            raise LoadError(t("Limiter: Regel {number} ohne Signal.", number=number))
        where = f"{item.get('file', '*')} / {item['signal']}"
        rules.append(Rule(file=str(item.get("file", "*") or "*"), signal=str(item["signal"]).strip(),
                          lo=_number(item.get("min"), where), hi=_number(item.get("max"), where),
                          enabled=bool(item.get("enabled", True))))
    return LimiterConfig(rules=rules, active=bool(section.get("active", True)))


def to_dict(config: LimiterConfig) -> dict:
    return {"limiter": {"format": FORMAT, "version": 1, "active": config.active,
                        "rules": [{"file": r.file, "signal": r.signal, "min": r.lo, "max": r.hi, "enabled": r.enabled}
                                  for r in config.rules]}}


def _yaml():
    try:
        import yaml
    except ImportError as exc:
        raise LoadError(t("YAML kann nicht gelesen werden: Paket PyYAML fehlt.")) from exc
    return yaml


def load(path: str) -> LimiterConfig:
    yaml = _yaml()
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
        data = yaml.load(text, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    except OSError as exc:
        raise LoadError(t("Datei nicht lesbar: {error}", error=exc)) from exc
    except yaml.YAMLError as exc:
        raise LoadError(t("YAML nicht lesbar: {error}", error=exc)) from exc
    config = from_dict(data or {})
    config.path = str(path)
    return config


def save(config: LimiterConfig, path: str) -> str:
    """Als YAML schreiben; andere Abschnitte einer vorhandenen YAML-Datei (z. B. Grenzwert-Modes) bleiben."""
    yaml = _yaml()
    if not path.lower().endswith(SUFFIXES):
        path += ".yaml"
    data = {}
    if os.path.isfile(path):
        try:
            old = yaml.load(Path(path).read_text(encoding="utf-8-sig"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
            if isinstance(old, dict):
                data = {k: v for k, v in old.items() if k != "limiter"}
        except (OSError, yaml.YAMLError):
            data = {}
    data.update(to_dict(config))
    dumper = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
    text = yaml.dump(data, Dumper=dumper, sort_keys=False, allow_unicode=True, default_flow_style=False)
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(path + ".tmp")
        tmp.write_text("# Limiter-Konfiguration (MessGraph)\n" + text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        raise LoadError(t("Konfiguration nicht gespeichert: {error}", error=exc)) from exc
    config.path = str(path)
    return path
