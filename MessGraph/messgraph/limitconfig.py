"""Grenzen und Zielzeiten aus einer YAML-Konfiguration (*.yaml, *.yml), abhängig vom Mode.

Erwarteter Aufbau (weitere Schlüssel wie plot, colors, fonts werden ignoriert):

    limits:
      enabled: true
      upper: null            # Vorgabe für Signale ohne eigenen Wert (optional)
      lower: null
      modes:
        Heat_800V:
          steps: 26306       # Zielabstand bis zur Grenzverletzung: Zahl = Schritte, "7h 18m 26s" = Zeit
          signals:
            Kl30_V_Set: {enabled: true, lower: 12.825, upper: 14.175}

Nur Signale mit enabled: true gelten. Ein Signal der Messdatei wird über den Namen zugeordnet (genau, dann ohne
Groß-/Kleinschreibung, dann ohne Einheit in Klammern). Signale ohne Zuordnung behalten die manuellen Werte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .data_model import LoadError
from .i18n import t

SUFFIXES = (".yaml", ".yml")
# steps: Zahl ohne Einheit = Schritte (Messpunkte) bis zur Grenze, mit Einheiten = Zeit bis zur Grenze
_TIME_UNITS = {"d": 86400.0, "t": 86400.0, "h": 3600.0, "std": 3600.0, "m": 60.0, "min": 60.0,
               "s": 1.0, "sec": 1.0, "sek": 1.0}


def parse_steps(value):
    """steps aus Zahl oder Text: (Schritte, None) oder (None, Sekunden); (None, None) = keine.

    "26306" oder 26306 -> Schritte; "7h 18m 26s", "45m", "90s", "1d 2h" -> Zeit. Ungültig: ValueError."""
    if value is None or isinstance(value, bool):
        return None, None
    if isinstance(value, (int, float)):
        return (float(value), None) if value > 0 else (None, None)
    text = str(value).strip().lower().replace(",", ".")
    if not text:
        return None, None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        number = float(text)
        return (number, None) if number > 0 else (None, None)
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]+)", text)
    rest = re.sub(r"(\d+(?:\.\d+)?)\s*([a-z]+)", "", text).strip()
    if not parts or rest or any(unit not in _TIME_UNITS for _n, unit in parts):
        raise ValueError(text)
    seconds = sum(float(n) * _TIME_UNITS[u] for n, u in parts)
    return (None, seconds) if seconds > 0 else (None, None)


def format_time(seconds: float) -> str:
    """Sekunden als "7h 18m 26s" (Teile mit 0 entfallen, ganze Sekunden)."""
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    parts = ([f"{hours}h"] if hours else []) + ([f"{minutes}m"] if minutes else []) + ([f"{secs}s"] if secs else [])
    return " ".join(parts) or "0s"


@dataclass
class Entry:
    """Ein Signal im Mode, wie in der Datei (auch deaktivierte bleiben beim Speichern erhalten)."""
    enabled: bool = True
    lower: float | None = None
    upper: float | None = None


@dataclass
class ModeSpec:
    name: str
    steps: float | None = None                       # Zielabstand in Schritten (Messpunkten)
    signals: dict = field(default_factory=dict)      # Name -> (lower, upper), nur enabled und mit Grenze
    disabled: int = 0                                # Signale mit enabled: false
    entries: dict = field(default_factory=dict)      # Name -> Entry, alle Signale des Modes (zum Bearbeiten)
    steps_time: float | None = None                  # oder Zielabstand als Zeit in Sekunden

    def set_steps(self, value) -> None:
        """steps setzen aus Zahl (Schritte) oder Zeittext ("7h 18m 26s"); ValueError bei ungültiger Eingabe."""
        self.steps, self.steps_time = parse_steps(value)

    @property
    def target(self):
        """("steps", Schritte) oder ("s", Sekunden) oder None."""
        if self.steps_time:
            return "s", self.steps_time
        if self.steps:
            return "steps", self.steps
        return None

    def steps_text(self) -> str:
        if self.steps_time:
            return format_time(self.steps_time)
        if self.steps:
            return f"{self.steps:g}"
        return ""

    def set_entry(self, name: str, enabled: bool, lower, upper, order: bool = True) -> None:
        """Signal im Mode setzen (Konfigurator); signals, disabled und die Zuordnung werden nachgeführt.

        order=False lässt untere > obere stehen (während der Eingabe in der Wertanzeige nicht vertauschen)."""
        lower, upper = _number(lower), _number(upper)
        if order and lower is not None and upper is not None and lower > upper:
            lower, upper = upper, lower
        self.entries[name] = Entry(bool(enabled), lower, upper)
        self.refresh()

    def remove_entry(self, name: str) -> None:
        self.entries.pop(name, None)
        self.refresh()

    def refresh(self) -> None:
        self.signals = {n: (e.lower, e.upper) for n, e in self.entries.items()
                        if e.enabled and (e.lower is not None or e.upper is not None)}
        self.disabled = sum(1 for e in self.entries.values() if not e.enabled)
        self._cache = None

    def lookup(self, name: str):
        """(lower, upper) für ein Signal der Messdatei oder None (dann gelten die manuellen Werte)."""
        if name in self.signals:
            return self.signals[name]
        key = name.casefold()
        folded = self._folded()
        if key in folded:
            return folded[key]
        bare = re.sub(r"\s*[\[(].*?[\])]\s*$", "", name).strip().casefold()   # "Kl30_V [V]" -> "kl30_v"
        return folded.get(bare)

    def match_name(self, name: str) -> str | None:
        """Name des Eintrags in der Konfiguration, dem ein Signal der Messdatei zugeordnet ist."""
        found = self.lookup(name)
        if found is None:
            return None
        if name in self.signals:
            return name
        for key, value in self.signals.items():
            if value is found and (key.casefold() == name.casefold()
                                   or key.casefold() == re.sub(r"\s*[\[(].*?[\])]\s*$", "", name).strip().casefold()):
                return key
        return next((k for k, v in self.signals.items() if v is found), None)

    def _folded(self) -> dict:
        cache = getattr(self, "_cache", None)
        if cache is None:
            cache = {k.casefold(): v for k, v in self.signals.items()}
            self._cache = cache
        return cache


@dataclass
class LimitConfig:
    path: str
    enabled: bool = True
    modes: dict = field(default_factory=dict)        # Name -> ModeSpec, Reihenfolge wie in der Datei
    raw: dict = field(default_factory=dict)          # übrige Abschnitte der Datei (bleiben beim Speichern erhalten)
    default_lower: float | None = None
    default_upper: float | None = None
    modified: bool = False                           # im Konfigurator geändert, noch nicht gespeichert

    def add_mode(self, name: str, steps=None) -> ModeSpec:
        name = str(name).strip()
        if not name:
            raise ValueError(t("Bitte einen Namen für den Mode angeben."))
        if name in self.modes:
            raise ValueError(t("Den Mode {name} gibt es schon.", name=name))
        mode = ModeSpec(name)
        mode.set_steps(steps if steps else None)
        self.modes[name] = mode
        self.modified = True
        return mode

    def rename_mode(self, old: str, new: str) -> None:
        new = str(new).strip()
        if not new:
            raise ValueError(t("Bitte einen Namen für den Mode angeben."))
        if new != old and new in self.modes:
            raise ValueError(t("Den Mode {name} gibt es schon.", name=new))
        self.modes = {(new if k == old else k): v for k, v in self.modes.items()}   # Reihenfolge bleibt
        self.modes[new].name = new
        self.modified = True

    def copy_mode(self, source: str, new: str) -> ModeSpec:
        mode = self.add_mode(new)
        mode.steps, mode.steps_time = self.modes[source].steps, self.modes[source].steps_time
        for name, entry in self.modes[source].entries.items():
            mode.entries[name] = Entry(entry.enabled, entry.lower, entry.upper)
        mode.refresh()
        return mode

    def delete_mode(self, name: str) -> None:
        self.modes.pop(name, None)
        self.modified = True

    @property
    def name(self) -> str:
        return Path(self.path).name if self.path else t("(neu, nicht gespeichert)")

    def mode_names(self) -> list[str]:
        return list(self.modes)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _positive(value):
    number = _number(value)
    return number if number is not None and number > 0 else None


def new_config(mode: str = "Standard") -> LimitConfig:
    """Leere Konfiguration mit einem Mode (Konfigurator: Neu)."""
    config = LimitConfig(path="")
    config.add_mode(mode)
    config.modified = True
    return config


def load(path: str) -> LimitConfig:
    try:
        import yaml
    except ImportError as exc:   # PyYAML gehört zu den Abhängigkeiten; Meldung für unvollständige Installationen
        raise LoadError(t("YAML kann nicht gelesen werden: Paket PyYAML fehlt.")) from exc
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise LoadError(t("Konfiguration nicht lesbar: {error}", error=exc)) from exc
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)          # schneller, wenn libyaml vorhanden ist
    try:
        data = yaml.load(text, Loader=loader)
    except yaml.YAMLError as exc:
        raise LoadError(t("Keine gültige YAML-Datei: {error}", error=exc)) from exc
    limits = data.get("limits") if isinstance(data, dict) else None
    modes = limits.get("modes") if isinstance(limits, dict) else None
    if not isinstance(modes, dict) or not modes:
        raise LoadError(t("Die YAML-Datei enthält keine Modes unter limits: modes."))
    default_lower, default_upper = _number(limits.get("lower")), _number(limits.get("upper"))
    raw = {k: v for k, v in data.items() if k != "limits"}
    config = LimitConfig(path=str(path), enabled=limits.get("enabled", True) is not False, raw=raw,
                         default_lower=default_lower, default_upper=default_upper)
    for mode_name, spec in modes.items():
        spec = spec if isinstance(spec, dict) else {}
        mode = ModeSpec(str(mode_name))
        try:
            mode.set_steps(spec.get("steps"))
        except ValueError as exc:
            raise LoadError(t("Mode {name}: steps ungültig ({value}); Zahl = Schritte oder Zeit wie 7h 18m 26s.",
                              name=mode_name, value=spec.get("steps"))) from exc
        for signal, entry in (spec.get("signals") or {}).items():
            if not isinstance(entry, dict):
                continue
            lower = _number(entry.get("lower")) if "lower" in entry else default_lower
            upper = _number(entry.get("upper")) if "upper" in entry else default_upper
            if lower is not None and upper is not None and lower > upper:
                lower, upper = upper, lower
            mode.entries[str(signal)] = Entry(entry.get("enabled") is True, lower, upper)
        mode.refresh()
        config.modes[mode.name] = mode
    return config


def to_dict(config: LimitConfig) -> dict:
    """Gleicher Aufbau wie beim Laden; übrige Abschnitte der ursprünglichen Datei bleiben erhalten."""
    modes = {}
    for name, mode in config.modes.items():
        if mode.steps_time:
            steps = format_time(mode.steps_time)                    # Zeit als Text mit Einheiten
        else:
            steps = int(mode.steps) if mode.steps and float(mode.steps).is_integer() else mode.steps
        spec = {"steps": steps}
        if mode.entries:
            spec["signals"] = {signal: {"enabled": e.enabled, "lower": e.lower, "upper": e.upper}
                               for signal, e in mode.entries.items()}
        modes[name] = spec
    limits = {"enabled": config.enabled, "upper": config.default_upper, "lower": config.default_lower,
              "modes": modes}
    out = dict(config.raw)
    out["limits"] = limits
    return out


def save(config: LimitConfig, path: str) -> str:
    """Als YAML schreiben (erst vollständig in eine Hilfsdatei, dann ersetzen)."""
    import os
    try:
        import yaml
    except ImportError as exc:
        raise LoadError(t("YAML kann nicht gelesen werden: Paket PyYAML fehlt.")) from exc
    if not path.lower().endswith(SUFFIXES):
        path += ".yaml"
    dumper = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
    text = yaml.dump(to_dict(config), Dumper=dumper, sort_keys=False, allow_unicode=True, default_flow_style=False)
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(path + ".tmp")
        tmp.write_text("# Grenzwert-Konfiguration (MessGraph-Grenzwert-Konfigurator)\n" + text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        raise LoadError(t("Konfiguration nicht gespeichert: {error}", error=exc)) from exc
    config.path, config.modified = str(path), False
    return path


def describe(config: LimitConfig) -> str:
    active = sum(1 for m in config.modes.values() if m.signals)
    return t("{name}: {modes} Modes ({active} mit Grenzen)", name=config.name, modes=len(config.modes), active=active)
