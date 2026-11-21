"""Fortschritt langer Ladevorgänge (MF4, Parquet), threadsicher und abbrechbar.

Ein Hintergrund-Job meldet über die Modulfunktionen step/busy/section; ohne aktiven Job sind sie wirkungslos.
So brauchen Leser und Datenmodell keinen zusätzlichen Parameter. Die Oberfläche liest den Zustand im
Render-Thread (Job.snapshot) und setzt beim Abbrechen nur ein Kennzeichen; der Job bricht beim nächsten
Meldepunkt mit Cancelled ab.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager, nullcontext

from .data_model import LoadError


class Cancelled(LoadError):
    """Vom Benutzer abgebrochen."""


class Job:
    def __init__(self, name: str):
        self.name = name
        self.fraction = 0.0          # 0..1 über den ganzen Job
        self.text = ""
        self.indeterminate = True    # Dauer unbekannt (z. B. innerhalb von asammdf)
        self.done = False
        self.cancelled = False
        self.started = time.monotonic()
        self._ranges = [(0.0, 1.0)]  # (Anfang, Spanne) verschachtelter Abschnitte

    def check(self) -> None:
        if self.cancelled:
            raise Cancelled("abgebrochen")

    def step(self, fraction: float, text: str | None = None) -> None:
        base, span = self._ranges[-1]
        value = base + span * min(1.0, max(0.0, float(fraction)))
        self.fraction = max(self.fraction, value)   # nie rückwärts
        self.indeterminate = False
        if text is not None:
            self.text = text
        self.check()

    def busy(self, text: str | None = None) -> None:
        if text is not None:
            self.text = text
        self.indeterminate = True
        self.check()

    @contextmanager
    def section(self, lo: float, hi: float, text: str | None = None):
        base, span = self._ranges[-1]
        self._ranges.append((base + span * lo, span * (hi - lo)))
        try:
            self.step(0.0, text)
            yield self
        finally:
            self._ranges.pop()
        self.step(hi)

    def snapshot(self) -> tuple[float, str, bool]:
        return self.fraction, self.text, self.indeterminate


_local = threading.local()


def current() -> Job | None:
    return getattr(_local, "job", None)


@contextmanager
def track(job: Job | None):
    """Bindet den Job an den laufenden Thread."""
    previous = current()
    _local.job = job
    try:
        yield job
    finally:
        _local.job = previous
        if job is not None:
            job.done = True


def step(fraction: float, text: str | None = None) -> None:
    job = current()
    if job is not None:
        job.step(fraction, text)


def busy(text: str | None = None) -> None:
    job = current()
    if job is not None:
        job.busy(text)


def check() -> None:
    job = current()
    if job is not None:
        job.check()


def section(lo: float, hi: float, text: str | None = None):
    job = current()
    return job.section(lo, hi, text) if job is not None else nullcontext()


def overall(jobs: list[Job]) -> float:
    """Gesamtfortschritt: fertige Jobs zählen voll, laufende mit ihrem Anteil."""
    if not jobs:
        return 0.0
    return sum(1.0 if j.done else j.fraction for j in jobs) / len(jobs)


def thousands(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")
