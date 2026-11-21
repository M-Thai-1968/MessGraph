"""Gemeinsames Datenmodell für alle Dateiformate."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np


class LoadError(Exception):
    """Datei oder Kanal kann nicht gelesen werden (Text ist für den Nutzer)."""


def prepare_xy(x, y) -> tuple[np.ndarray, np.ndarray]:
    """Liefert float64-Arrays mit gültiger, aufsteigend sortierter X-Achse."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape != y.shape:
        raise LoadError(f"X- und Y-Länge unterschiedlich ({x.size} / {y.size})")
    ok = np.isfinite(x)
    if not ok.all():
        x, y = x[ok], y[ok]
    if x.size > 1 and np.any(np.diff(x) < 0):
        order = np.argsort(x, kind="stable")
        x, y = x[order], y[order]
    return x, y


@dataclass(eq=False)
class Channel:
    """Ein Messsignal. Daten liegen vor (CSV/Parquet) oder kommen per loader (MF4)."""

    name: str
    unit: str = ""
    x_name: str = "Zeit"
    x_unit: str = "s"
    source: str = ""
    x: np.ndarray | None = None
    y: np.ndarray | None = None
    loader: Callable[[], tuple] | None = None
    x_epoch: float | None = None   # Startzeit (Wanduhr-Sekunden ab 1970) für x = 0; None = ohne Datum
    ds_note: str = ""              # Hinweis, wenn beim Laden reduziert wurde (Downsampling)
    formula: str = ""              # berechnetes Signal: Formel, z. B. {Strom} * {Spannung}
    note: str = ""                 # Bemerkung zum berechneten Signal
    raw: tuple | None = None       # Limiter aktiv: ungekürzte Daten (x, y); x/y enthalten dann nur den Limit-Anteil
    limit_key: tuple | None = None   # Regeln, mit denen x/y zuletzt gekürzt wurden (None = ungekürzt)
    limit_out: object = None       # das gekürzte x (erkennt, wenn die Daten inzwischen neu geladen wurden)
    kind: str = ""                 # "" = darstellbar; "text" (VLSD/String/Byte-Feld), "empty" (0 Werte), "const" (1 Wert)
    aliases: tuple = ()            # frühere Anzeigenamen (ältere Ansichten/Projekte finden den Kanal weiter)
    value_text: dict | None = None # Wert->Text-Umrechnung: Rohwert -> Text (Wertanzeige, Tooltip)

    @property
    def plottable(self) -> bool:
        return self.kind not in ("text", "empty", "const")

    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases

    @property
    def loaded(self) -> bool:
        return self.x is not None

    def load(self) -> None:
        """Lädt die Daten nach. Der Loader liefert (x, y, unit)."""
        if self.loaded:
            return
        if self.loader is None:
            raise LoadError(f"{self.name}: keine Daten vorhanden")
        from . import downsample, progress  # MF4: Downsampling beim Nachladen des Kanals
        from .i18n import t
        progress.busy(t("{name}: Messwerte lesen...", name=self.name))
        result = self.loader()
        x, y, unit = result[:3]
        extra = result[3] if len(result) > 3 else {}
        x, y = prepare_xy(x, y)
        note = ""
        if downsample.applies(self.source):
            progress.step(0.8, t("{name}: {count} Werte, Downsampling...", name=self.name, count=progress.thousands(x.size)))
            x, y, note = downsample.apply(x, y)
        progress.check()  # erst nach erfolgreichem Lesen übernehmen, Abbruch lässt den Kanal ungeladen
        self.x, self.y, self.ds_note = x, y, note
        if extra.get("value_text"):
            self.value_text = extra["value_text"]
        if unit:
            self.unit = unit

    @property
    def label(self) -> str:
        return f"{self.name} [{self.unit}]" if self.unit else self.name


def find_channel(channels, name: str | None) -> "Channel | None":
    """Kanal zu einem gespeicherten Namen: zuerst der Anzeigename, dann frühere Namen (Alias)."""
    if not name:
        return None
    return next((c for c in channels if c.name == name), None) or \
        next((c for c in channels if name in c.aliases), None)


@dataclass(eq=False)
class Dataset:
    """Eine geöffnete Datei mit ihren Kanälen und dem Erkennungsergebnis."""

    path: str
    channels: list[Channel] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    closer: Callable[[], None] | None = None
    extra: dict = field(default_factory=dict)   # formatabhängige Zusatzdaten (MF4: mdf, Datenbasen)

    @property
    def name(self) -> str:
        return Path(self.path).name

    def close(self) -> None:
        for extra in self.extra.pop("opened", []):
            try:
                extra.close()
            except Exception:
                pass
        if self.closer:
            self.closer()
            self.closer = None
