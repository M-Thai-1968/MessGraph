"""Graphen als Vektorgrafik: PDF (eigener Schreiber), SVG und Druck.

Ein Graph wird als PlotSpec beschrieben (Sichtbereich, Serien, Marker, Grenzlinien, Legende) und von
render_plot auf eine Zeichenfläche gezeichnet. Zeichenflächen: SvgCanvas (SVG-Datei) und PdfCanvas
(Seite eines PdfDocument). Koordinaten in Punkt, Ursprung oben links.
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import numpy as np

from .i18n import t
from .measure import fmt, view_points
from .pdfdoc import PdfDocument, text_width

MM = 72.0 / 25.4
PAPER = {"A0": (841, 1189), "A1": (594, 841), "A2": (420, 594), "A3": (297, 420), "A4": (210, 297),
         "A5": (148, 210), "A6": (105, 148)}
ORIENTATIONS = ["auto", "portrait", "landscape"]
TARGETS = ["printer", "pdf", "svg"]
GRID_RGB = (222, 225, 230)
FRAME_RGB = (150, 155, 162)
TEXT_RGB = (28, 32, 38)
DIM_RGB = (95, 102, 112)


def page_size(paper: str, landscape: bool) -> tuple[float, float]:
    w, h = PAPER.get(paper, PAPER["A4"])
    w, h = w * MM, h * MM
    return (h, w) if landscape else (w, h)


# ---------------------------------------------------------------- Beschreibung eines Graphen
@dataclass
class SeriesSpec:
    label: str
    x: np.ndarray            # Plot-Koordinaten (mit Datumsachse: Wanduhr-Sekunden)
    y: np.ndarray
    rgb: tuple
    right: bool = False
    key: str = ""            # Kennung des Signals (dynamischer Report: Kurve, Spiegel und Tabellen verknüpfen)
    bars: bool = False       # senkrechte Balken statt Linie (Harmonische der Fourier-Analyse)


@dataclass
class PlotSpec:
    title: str
    xlim: tuple
    ylim: tuple
    series: list = field(default_factory=list)
    y2lim: tuple | None = None
    markers: list = field(default_factory=list)       # (x, Beschriftung, rgb)
    limits: list = field(default_factory=list)        # (y, rgb, rechts[, Kennung des Signals])
    xlabel: str = ""
    ylabel: str = ""
    y2label: str = ""
    time_axis: bool = False
    legend: str = "nw"                                 # nw, n, ne, sw, s, se (wie im Programm); none = ohne
    comments: list = field(default_factory=list)      # Kommentarfelder (x, y, Text) in Achsenwerten (linke Achse)
    alarm: bool = False                                # Zielzeit verletzt: Plotfläche schwach rot
    alarm_rgb: tuple | None = None                     # eigene Hintergrundfarbe der Plotfläche (überschreibt alarm)
    regressions: list = field(default_factory=list)   # (x0, y0, x1, y1, Farbe, rechts, Kennung): gestrichelt
    info: list = field(default_factory=list)          # Textblock rechts neben dem Graphen: Text oder (Text, Farbe, fett)
    log_x: bool = False                                # X-Achse logarithmisch (Dekaden)
    log_y: bool = False                                # Y-Achsen logarithmisch


# ---------------------------------------------------------------- Achsenteilung
def nice_ticks(lo: float, hi: float, count: int = 6) -> list[float]:
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return [lo] if math.isfinite(lo) else []
    raw = (hi - lo) / max(1, count)
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    first = math.ceil(lo / step - 1e-9) * step
    ticks, value = [], first
    while value <= hi + step * 1e-9:
        ticks.append(0.0 if abs(value) < step * 1e-9 else round(value, 12))
        value += step
    return ticks


_DATE_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400,
               172800, 604800, 2592000, 31536000]


def _wall(seconds: float) -> datetime:
    return datetime(1970, 1, 1) + timedelta(seconds=float(seconds))


def date_ticks(lo: float, hi: float, count: int = 6) -> list[tuple[float, str]]:
    """Ticks auf runden Uhrzeiten; Beschriftung je nach Abstand mit Sekunden, Minuten oder Datum."""
    if hi <= lo:
        return []
    step = next((s for s in _DATE_STEPS if s >= (hi - lo) / max(1, count)), _DATE_STEPS[-1])
    first = math.ceil(lo / step) * step
    ticks, value = [], first
    while value <= hi:
        when = _wall(value)
        if step < 60:
            label = when.strftime("%H:%M:%S")
        elif step < 86400:
            label = when.strftime("%H:%M") if ticks else when.strftime("%d.%m. %H:%M")
        else:
            label = when.strftime("%d.%m.%Y")
        ticks.append((value, label))
        value += step
    return ticks


# ---------------------------------------------------------------- Zeichenflächen
def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb[:3])


class SvgCanvas:
    def __init__(self, width: float, height: float):
        self.width, self.height = width, height
        self.parts: list[str] = []
        self.clips = 0
        self.hit = False          # in einer Signalgruppe: breite unsichtbare Linie zum Anklicken

    def text_width(self, text: str, size: float, bold: bool = False) -> float:
        return text_width(text, "F2" if bold else "F1", size)

    def line(self, points, rgb, width: float = 1.0, dash: str | None = None) -> None:
        if len(points) < 2:
            return
        path = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<polyline points="{path}" fill="none" stroke="{_hex(rgb)}" stroke-width="{width:.2f}" '
                          f'stroke-linejoin="round"{extra}/>')
        if self.hit:
            self.parts.append(f'<polyline class="hit" points="{path}" fill="none" stroke="transparent" stroke-width="7"/>')

    @contextmanager
    def group(self, key: str):
        """Elemente eines Signals zusammenfassen (<g class="sig" data-key=...>); ohne Kennung wirkungslos."""
        if not key:
            yield
            return
        self.parts.append(f'<g class="sig" data-key="{escape(key)}">')
        self.hit = True
        try:
            yield
        finally:
            self.hit = False
            self.parts.append("</g>")

    def rect(self, x, y, w, h, stroke=None, fill=None, width: float = 0.6) -> None:
        self.parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
                          f'fill="{_hex(fill) if fill else "none"}" '
                          f'stroke="{_hex(stroke) if stroke else "none"}" stroke-width="{width:.2f}"/>')

    def text(self, x, y, text, size, rgb=TEXT_RGB, anchor="start", bold=False, rotate=False) -> None:
        transform = f' transform="rotate(-90 {x:.2f} {y:.2f})"' if rotate else ""
        weight = ' font-weight="bold"' if bold else ""
        self.parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-family="Helvetica, Arial, sans-serif" '
                          f'font-size="{size:.2f}" fill="{_hex(rgb)}" text-anchor="{anchor}"{weight}{transform}>'
                          f'{escape(text)}</text>')

    @contextmanager
    def clip(self, x, y, w, h):
        self.clips += 1
        cid = f"c{self.clips}"
        self.parts.append(f'<clipPath id="{cid}"><rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"/>'
                          f'</clipPath><g clip-path="url(#{cid})">')
        try:
            yield
        finally:
            self.parts.append("</g>")

    def to_svg(self) -> str:
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{self.width / MM:.1f}mm" height="{self.height / MM:.1f}mm" '
                f'viewBox="0 0 {self.width:.2f} {self.height:.2f}">\n<rect width="100%" height="100%" fill="white"/>\n'
                + "\n".join(self.parts) + "\n</svg>\n")


class PdfCanvas:
    """Zeichnet in die aktuelle Seite eines PdfDocument; (x0, top) ist die linke obere Ecke in PDF-Punkten."""

    def __init__(self, doc: PdfDocument, x0: float, top: float):
        self.doc, self.x0, self.top = doc, x0, top

    def _p(self, x, y):
        return self.x0 + x, self.top - y

    def _ops(self, data: bytes) -> None:
        self.doc.pages[-1].ops.append(data)

    def text_width(self, text: str, size: float, bold: bool = False) -> float:
        return self.doc.width(text, "F2" if bold else "F1", size)

    def line(self, points, rgb, width: float = 1.0, dash: str | None = None) -> None:
        if len(points) < 2:
            return
        r, g, b = (c / 255 for c in rgb[:3])
        parts = [b"q %.3f %.3f %.3f RG %.2f w 1 J 1 j" % (r, g, b, width)]
        if dash:
            parts.append(b"[%s] 0 d" % dash.replace(",", " ").encode())
        x, y = self._p(*points[0])
        parts.append(b"%.2f %.2f m" % (x, y))
        parts += [b"%.2f %.2f l" % self._p(px, py) for px, py in points[1:]]
        parts.append(b"S Q")
        self._ops(b" ".join(parts))

    def rect(self, x, y, w, h, stroke=None, fill=None, width: float = 0.6) -> None:
        px, py = self._p(x, y + h)
        ops = [b"q"]
        if fill:
            ops.append(b"%.3f %.3f %.3f rg" % tuple(c / 255 for c in fill[:3]))
        if stroke:
            ops.append(b"%.3f %.3f %.3f RG %.2f w" % (*(c / 255 for c in stroke[:3]), width))
        ops.append(b"%.2f %.2f %.2f %.2f re %s Q" % (px, py, w, h, b"B" if fill and stroke else b"f" if fill else b"S"))
        self._ops(b" ".join(ops))

    def text(self, x, y, text, size, rgb=TEXT_RGB, anchor="start", bold=False, rotate=False) -> None:
        font = "F2" if bold else "F1"
        width = self.text_width(text, size, bold)
        shift = {"start": 0.0, "middle": width / 2, "end": width}[anchor]
        px, py = self._p(x, y)
        name, operand = self.doc._string(text, font)
        r, g, b = (c / 255 for c in rgb[:3])
        if rotate:   # 90 Grad gegen den Uhrzeigersinn, Text läuft nach oben
            matrix = b"0 1 -1 0 %.2f %.2f Tm" % (px, py - shift)
        else:
            matrix = b"1 0 0 1 %.2f %.2f Tm" % (px - shift, py)
        self._ops(b"BT %.3f %.3f %.3f rg /%s %.2f Tf %s " % (r, g, b, name, size, matrix) + operand + b" Tj ET")

    @contextmanager
    def group(self, key: str):
        yield

    @contextmanager
    def clip(self, x, y, w, h):
        px, py = self._p(x, y + h)
        self._ops(b"q %.2f %.2f %.2f %.2f re W n" % (px, py, w, h))
        try:
            yield
        finally:
            self._ops(b"Q")


# ---------------------------------------------------------------- Graph zeichnen
def _polylines(px: np.ndarray, py: np.ndarray):
    """Teilt an Lücken (NaN) in zusammenhängende Linienzüge."""
    ok = np.isfinite(px) & np.isfinite(py)
    if not ok.any():
        return
    edges = np.flatnonzero(np.diff(np.concatenate(([0], ok.astype(np.int8), [0]))))
    for start, end in zip(edges[0::2], edges[1::2]):
        if end - start >= 1:
            yield list(zip(px[start:end].tolist(), py[start:end].tolist()))


REPORT_MARGIN = 0.10      # Report: Y-Achse mindestens 10 % über dem größten und unter dem kleinsten Wert


def value_margin(lo: float, hi: float, share: float = REPORT_MARGIN) -> tuple[float, float]:
    """Achsenbereich mit Abstand: oben hi + share*|hi|, unten lo - share*|lo|.

    Ist ein Wert 0, gilt der Anteil der Spannweite (sonst läge die Kurve auf dem Rand); ohne Spannweite 1.
    """
    span = hi - lo
    top = share * abs(hi) if hi != 0 else share * span
    bottom = share * abs(lo) if lo != 0 else share * span
    if top <= 0 and bottom <= 0:
        top = bottom = 1.0
    return lo - bottom, hi + top


def _visible_extent(series: list, xlim, extra=()) -> tuple[float, float] | None:
    """Kleinster und größter Wert der Signale im sichtbaren X-Bereich (plus zusätzliche Werte, z. B. Grenzen)."""
    lo, hi = math.inf, -math.inf
    x0, x1 = (float(v) for v in xlim) if xlim else (-math.inf, math.inf)
    for s in series:
        x, y = np.asarray(s.x, dtype=np.float64), np.asarray(s.y, dtype=np.float64)
        if x.size == 0 or y.size == 0:
            continue
        mask = np.isfinite(y) & (x >= x0) & (x <= x1)
        if not mask.any():
            mask = np.isfinite(y)                 # nichts im Ausschnitt: ganzes Signal
        if mask.any():
            lo, hi = min(lo, float(y[mask].min())), max(hi, float(y[mask].max()))
    for value in extra:
        if value is not None and math.isfinite(value):
            lo, hi = min(lo, float(value)), max(hi, float(value))
    return (lo, hi) if math.isfinite(lo) and math.isfinite(hi) else None


def with_report_margins(spec: PlotSpec, share: float = REPORT_MARGIN) -> PlotSpec:
    """Y-Achsen für den Report: max mindestens +10 % über dem größten, min mindestens -10 % unter dem kleinsten
    Wert aller dargestellten Signale (je Achse, im sichtbaren X-Bereich; Grenzlinien zählen mit)."""
    left = [s for s in spec.series if not s.right]
    right = [s for s in spec.series if s.right]
    lines_left = [entry[0] for entry in spec.limits if not entry[2]]
    lines_right = [entry[0] for entry in spec.limits if entry[2]]
    ylim, y2lim = spec.ylim, spec.y2lim
    extent = _visible_extent(left, spec.xlim, lines_left)
    if extent:
        ylim = value_margin(*extent, share)
    if spec.y2lim is not None and right:
        extent = _visible_extent(right, spec.xlim, lines_right)
        if extent:
            y2lim = value_margin(*extent, share)
    return replace(spec, ylim=ylim, y2lim=y2lim)


def _range(lim) -> tuple[float, float]:
    lo, hi = (float(v) for v in lim)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return 0.0, 1.0
    if hi <= lo:
        pad = abs(lo) * 0.05 or 1.0
        return lo - pad, hi + pad
    return lo, hi


def _log10(values):
    """log10 für Achsenwerte; Werte <= 0 -> NaN (auf log. Achse nicht darstellbar)."""
    arr = np.asarray(values, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(arr > 0, np.log10(np.where(arr > 0, arr, 1.0)), np.nan)


def _log_lim(lim, data) -> tuple:
    """Grenzen einer log. Achse: positive Grenzen logarithmieren, sonst aus den positiven Daten."""
    lo, hi = (float(v) for v in lim)
    pos = np.asarray(data, dtype=np.float64)
    pos = pos[np.isfinite(pos) & (pos > 0)]
    if lo <= 0:
        lo = float(pos.min()) if pos.size else 1e-3
    if hi <= lo:
        hi = float(pos.max()) if pos.size and pos.max() > lo else lo * 10
    return math.log10(lo), math.log10(hi)


def log_transformed(spec: PlotSpec) -> PlotSpec:
    """Kopie des Graphen mit logarithmierten Koordinaten (log_x/log_y); Beschriftung macht render_plot."""
    import copy
    out = copy.copy(spec)
    fx = _log10 if spec.log_x else (lambda v: np.asarray(v, dtype=np.float64))
    fy = _log10 if spec.log_y else (lambda v: np.asarray(v, dtype=np.float64))
    if spec.log_x:
        out.xlim = _log_lim(spec.xlim, np.concatenate([np.asarray(s.x, float) for s in spec.series] or [np.ones(1)]))
    if spec.log_y:
        left = [np.asarray(s.y, float) for s in spec.series if not s.right]
        right = [np.asarray(s.y, float) for s in spec.series if s.right]
        out.ylim = _log_lim(spec.ylim, np.concatenate(left or [np.ones(1)]))
        if spec.y2lim is not None:
            out.y2lim = _log_lim(spec.y2lim, np.concatenate(right or [np.ones(1)]))
    out.series = [SeriesSpec(s.label, fx(s.x), fy(s.y), s.rgb, s.right, s.key, s.bars) for s in spec.series]
    out.bar_base = math.log10(max(1e-12, 10 ** out.ylim[0])) if spec.log_y else None
    out.markers = [(float(fx([m])[0]), label, rgb) for m, label, rgb in spec.markers]
    out.limits = [(float(fy([e[0]])[0]), *e[1:]) for e in spec.limits]
    out.comments = [(float(fx([cx])[0]), float(fy([cy])[0]), text) for cx, cy, text in spec.comments]
    out.regressions = [(float(fx([a])[0]), float(fy([b])[0]), float(fx([cc])[0]), float(fy([d])[0]), *rest)
                       for a, b, cc, d, *rest in spec.regressions]
    return out


def log_ticks(lo: float, hi: float) -> list[tuple[float, str]]:
    """Dekaden-Teilung einer log. Achse (lo, hi als log10): Positionen und Beschriftung 10^k als Zahl."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return []
    first, last = math.ceil(lo - 1e-9), math.floor(hi + 1e-9)
    step = max(1, int(math.ceil((last - first + 1) / 8)))
    ticks = [(float(k), fmt(10.0 ** k)) for k in range(first, last + 1, step)]
    if len(ticks) < 2:                               # weniger als eine Dekade: 2er/5er-Zwischenwerte
        ticks = [(math.log10(v), fmt(v)) for k in range(first - 1, last + 2) for m in (1, 2, 5)
                 for v in [m * 10.0 ** k] if lo <= math.log10(v) <= hi]
    return ticks


def log_minor(lo: float, hi: float) -> list[float]:
    """Hilfslinien einer log. Achse (lo, hi als log10): 2..9 * 10^k zwischen den Dekaden (Positionen in log10)."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo or hi - lo > 12:
        return []
    out = []
    for k in range(math.floor(lo) - 1, math.ceil(hi) + 1):
        for m in range(2, 10):
            v = math.log10(m) + k
            if lo < v < hi:
                out.append(v)
    return out


MINOR_RGB = (236, 238, 241)


def render_plot(c, spec: PlotSpec, x: float, y: float, w: float, h: float, font: float = 8.5) -> None:
    """Zeichnet den Graphen in das Rechteck (x, y, w, h)."""
    log_x, log_y = spec.log_x and not spec.time_axis, spec.log_y
    if log_x or log_y:
        spec = log_transformed(spec)
    small = font * 0.92
    x0, x1 = _range(spec.xlim)
    y0, y1 = _range(spec.ylim)
    has_y2 = spec.y2lim is not None and any(s.right for s in spec.series)
    if has_y2:
        r0, r1 = _range(spec.y2lim)
    if log_y:
        pairs = log_ticks(y0, y1)
        yt, ylabels = [p for p, _l in pairs], [label for _p, label in pairs]
    else:
        yt = nice_ticks(y0, y1, max(3, int(h / 45)))
        ylabels = [fmt(v) for v in yt]
    left = max([c.text_width(s, small) for s in ylabels] + [10]) + 8 + (font * 1.4 if spec.ylabel else 0)
    right = 10.0
    if has_y2:
        if log_y:
            pairs = log_ticks(r0, r1)
            rt, rlabels = [p for p, _l in pairs], [label for _p, label in pairs]
        else:
            rt = nice_ticks(r0, r1, max(3, int(h / 45)))
            rlabels = [fmt(v) for v in rt]
        right = max([c.text_width(s, small) for s in rlabels] + [10]) + 8 + (font * 1.4 if spec.y2label else 0)
    info = [(e, None, False) if isinstance(e, str) else tuple(e) for e in spec.info]
    if info:                                           # Platz für den Textblock rechts reservieren
        panel = max(c.text_width(text, small, bold) for text, _rgb, bold in info) + small * 1.6
        panel = min(panel, w * 0.42)
        right += panel + small
    top = font * 2.2 if spec.title else font * 0.8
    bottom = small * 2.2 + (font * 1.5 if spec.xlabel else 0)
    ax, ay, aw, ah = x + left, y + top, max(10.0, w - left - right), max(10.0, h - top - bottom)

    def sx(v):
        return ax + (v - x0) / (x1 - x0) * aw

    def sy(v, lo=y0, hi=y1):
        return ay + ah - (v - lo) / (hi - lo) * ah

    if spec.title:
        c.text(ax + aw / 2, y + font * 1.3, spec.title, font * 1.15, TEXT_RGB, "middle", bold=True)
    c.rect(ax, ay, aw, ah, fill=spec.alarm_rgb or (ALARM_PLOT_RGB if spec.alarm else (255, 255, 255)))
    # Gitter und Achsen; log. Achsen zusätzlich Hilfslinien 2..9 je Dekade
    if log_y:
        for v in log_minor(y0, y1):
            c.line([(ax, sy(v)), (ax + aw, sy(v))], MINOR_RGB, 0.3)
    if log_x:
        for v in log_minor(x0, x1):
            px = ax + (v - x0) / (x1 - x0) * aw
            c.line([(px, ay), (px, ay + ah)], MINOR_RGB, 0.3)
    for v, label in zip(yt, ylabels):
        py = sy(v)
        c.line([(ax, py), (ax + aw, py)], GRID_RGB, 0.4)
        c.text(ax - 4, py + small * 0.35, label, small, DIM_RGB, "end")
    if has_y2:
        for v, label in zip(rt, rlabels):
            py = sy(v, r0, r1)
            c.line([(ax + aw, py), (ax + aw + 3, py)], FRAME_RGB, 0.5)
            c.text(ax + aw + 5, py + small * 0.35, label, small, DIM_RGB, "start")
    if spec.time_axis:
        xt = date_ticks(x0, x1, max(2, int(aw / 90)))
    elif log_x:
        xt = log_ticks(x0, x1)
    else:
        xt = [(v, fmt(v)) for v in nice_ticks(x0, x1, max(2, int(aw / 70)))]
    for v, label in xt:
        px = sx(v)
        c.line([(px, ay), (px, ay + ah)], GRID_RGB, 0.4)
        c.text(px, ay + ah + small * 1.35, label, small, DIM_RGB, "middle")
    if spec.xlabel:
        c.text(ax + aw / 2, y + h - font * 0.35, spec.xlabel, font, TEXT_RGB, "middle")
    if spec.ylabel:
        c.text(x + font, ay + ah / 2, spec.ylabel, font, TEXT_RGB, "middle", rotate=True)
    if has_y2 and spec.y2label:
        c.text(x + w - font * 0.3, ay + ah / 2, spec.y2label, font, TEXT_RGB, "middle", rotate=True)
    # Daten
    width_px = max(200, int(aw * 2))
    with c.clip(ax, ay, aw, ah):
        for entry in spec.limits:
            limit, rgb, on_right = entry[:3]
            lo, hi = (r0, r1) if on_right and has_y2 else (y0, y1)
            py = sy(limit, lo, hi)
            with c.group(entry[3] if len(entry) > 3 else ""):
                c.line([(ax, py), (ax + aw, py)], rgb, 0.9, dash="4,2")
        for s in spec.series:
            if s.x is None or not len(s.x):
                continue
            vx, vy = view_points(s.x, s.y, x0, x1, bins=width_px, overview_bins=50)
            keep = (vx >= x0 - (x1 - x0)) & (vx <= x1 + (x1 - x0))
            vx, vy = vx[keep], vy[keep]
            lo, hi = (r0, r1) if s.right and has_y2 else (y0, y1)
            if s.bars:                                     # Balken von der Nulllinie (log: Unterkante) bis zum Wert
                xs, ys = np.asarray(s.x, float), np.asarray(s.y, float)
                ok = np.isfinite(xs) & np.isfinite(ys)
                xs, ys = xs[ok], ys[ok]
                step = float(np.min(np.diff(np.unique(xs)))) if np.unique(xs).size > 1 else (x1 - x0) / 20
                half = 0.3 * step / (x1 - x0) * aw
                base = getattr(spec, "bar_base", None)
                base = lo if base is not None else min(max(0.0, lo), hi)
                with c.group(s.key):
                    for bx, by in zip(xs, ys):
                        top, bottom = sy(by, lo, hi), sy(base, lo, hi)
                        c.rect(sx(bx) - half, min(top, bottom), 2 * half, abs(bottom - top), stroke=s.rgb,
                               fill=s.rgb, width=0.4)
                continue
            px = ax + (vx - x0) / (x1 - x0) * aw
            py = ay + ah - (vy - lo) / (hi - lo) * ah
            with c.group(s.key):
                for points in _polylines(px, py):
                    c.line(points, s.rgb, 0.9)
        for x_a, y_a, x_b, y_b, rgb, on_right, key in spec.regressions:   # Regressionsgeraden, gestrichelt
            lo, hi = (r0, r1) if on_right and has_y2 else (y0, y1)
            with c.group(key):
                c.line([(sx(x_a), sy(y_a, lo, hi)), (sx(x_b), sy(y_b, lo, hi))], rgb, 0.9, dash="5,3")
        for mx, label, rgb in spec.markers:
            if x0 <= mx <= x1:
                px = sx(mx)
                c.line([(px, ay), (px, ay + ah)], rgb, 0.9)
                c.text(px + 3, ay + small * 1.2, label, small, rgb, "start", bold=True)
    _draw_comments(c, spec.comments, sx, sy, (ax, ay, aw, ah), small)
    if info:
        px0 = x + w - panel
        line_h = small * 1.45
        ph = len(info) * line_h + small * 0.8
        c.rect(px0, ay, panel, min(ph, ah), stroke=FRAME_RGB, fill=(250, 250, 251), width=0.5)
        for i, (text, rgb, bold) in enumerate(info):
            ty = ay + small * 0.4 + (i + 1) * line_h - small * 0.35
            if ty > ay + ah:
                break
            if text:
                c.text(px0 + small * 0.7, ty, text, small, rgb or TEXT_RGB, bold=bold)
    c.rect(ax, ay, aw, ah, stroke=FRAME_RGB, width=0.6)
    # Legende an der gespeicherten Stelle
    entries = [(s.label, s.rgb) for s in spec.series]
    if entries and spec.legend != "none":
        size = small
        lw = max(c.text_width(label, size) for label, _ in entries) + size * 2.6
        lh = len(entries) * size * 1.35 + size * 0.6
        key = spec.legend if spec.legend in ("nw", "n", "ne", "sw", "s", "se") else "nw"
        pad = size * 0.6
        lx = {"w": ax + pad, "e": ax + aw - lw - pad}.get(key[-1], ax + (aw - lw) / 2)
        ly = ay + pad if key[0] == "n" else ay + ah - lh - pad
        c.rect(lx, ly, lw, lh, stroke=FRAME_RGB, fill=(250, 250, 251), width=0.4)
        for i, (label, rgb) in enumerate(entries):
            ty = ly + size * 0.3 + (i + 1) * size * 1.35
            c.rect(lx + size * 0.5, ty - size * 0.8, size * 0.9, size * 0.9, fill=rgb)
            c.text(lx + size * 1.9, ty - size * 0.05, label, size, TEXT_RGB)


COMMENT_RGB = (178, 96, 0)
ALARM_PLOT_RGB = (255, 232, 232)      # Druck/Report (hell): schwach rot hinterlegter Graph
PEAK_PLOT_RGB = (255, 249, 200)       # Messwerte (Peaks) außerhalb der Grenzen: hellgelb
BOTH_PLOT_RGB = (236, 224, 252)       # Regression und Peaks verletzt: hellviolett
ALARM_ROW_RGB = (255, 205, 205)       # rot hinterlegte Tabellenzeile
COMMENT_FILL = (255, 248, 225)


def _draw_comments(c, comments, sx, sy, area, size) -> None:
    """Kommentarfelder: Punkt an der Stelle, Kasten mit dem Text rechts oberhalb (im Plotbereich gehalten)."""
    ax, ay, aw, ah = area
    for x, y, text in comments:
        if not (math.isfinite(x) and math.isfinite(y)):
            continue
        px, py = sx(x), sy(y)
        if not (ax <= px <= ax + aw and ay <= py <= ay + ah):
            continue                                    # außerhalb des sichtbaren Ausschnitts
        lines = [line for line in str(text).splitlines() if line.strip()] or [str(text)]
        bw = max(c.text_width(line, size) for line in lines) + size * 1.0
        bh = len(lines) * size * 1.3 + size * 0.5
        bx = min(max(ax + 2, px + size * 0.8), ax + aw - bw - 2)
        by = min(max(ay + 2, py - bh - size * 0.8), ay + ah - bh - 2)
        c.line([(px, py), (bx + (0 if bx >= px else bw), by + bh)], COMMENT_RGB, 0.6)
        c.rect(px - 1.6, py - 1.6, 3.2, 3.2, fill=COMMENT_RGB)
        c.rect(bx, by, bw, bh, stroke=COMMENT_RGB, fill=COMMENT_FILL, width=0.6)
        for i, line in enumerate(lines):
            c.text(bx + size * 0.5, by + size * 0.25 + (i + 1) * size * 1.3 - size * 0.3, line, size, TEXT_RGB)


# ---------------------------------------------------------------- Seiten
def layout_cells(count: int, grid: tuple[int, int], page_w: float, page_h: float, margin: float = 28.0,
                 header: float = 22.0, gap: float = 10.0, min_h: float = 150.0, spans: list | None = None):
    """Verteilt count Graphen im Raster (Zeilen, Spalten) auf Seiten. Liefert je Seite [(Index, x, y, w, h)].

    spans: Breiten der Graphen je Zeile in Spalten (zusammengefasste Bereiche); eine Zeile bleibt auf einer Seite.
    """
    rows, cols = grid
    cols = max(1, cols)
    if spans and sum(len(row) for row in spans) == count:
        avail_w, avail_h = page_w - 2 * margin, page_h - 2 * margin - header
        per_page = max(1, min(len(spans), int((avail_h + gap) // (min_h + gap))))
        cell_w = (avail_w - gap * (cols - 1)) / cols
        pages, index = [], 0
        for start in range(0, len(spans), per_page):
            chunk = spans[start:start + per_page]
            cell_h = (avail_h - gap * (len(chunk) - 1)) / len(chunk)
            cells = []
            for r, widths in enumerate(chunk):
                col = 0
                for width in widths:
                    cells.append((index, margin + col * (cell_w + gap), margin + header + r * (cell_h + gap),
                                  width * cell_w + (width - 1) * gap, cell_h))
                    col += width
                    index += 1
            pages.append(cells)
        return pages
    rows = max(1, rows or math.ceil(count / cols))
    avail_w, avail_h = page_w - 2 * margin, page_h - 2 * margin - header
    per_page = max(1, min(rows, int((avail_h + gap) // (min_h + gap))))
    cell_w = (avail_w - gap * (cols - 1)) / cols
    pages, index = [], 0
    while index < count:
        rows_here = min(per_page, math.ceil((count - index) / cols))
        cell_h = (avail_h - gap * (rows_here - 1)) / rows_here
        cells = []
        for r in range(rows_here):
            for col in range(cols):
                if index >= count:
                    break
                cells.append((index, margin + col * (cell_w + gap), margin + header + r * (cell_h + gap), cell_w, cell_h))
                index += 1
        pages.append(cells)
    return pages


def choose_landscape(orientation: str, grid: tuple[int, int]) -> bool:
    if orientation in ("portrait", "landscape"):
        return orientation == "landscape"
    rows, cols = grid
    return cols >= rows or rows <= 2   # wenige Zeilen: Querformat nutzt die Breite der Zeitachse


def write_pdf(path: str, specs: list[PlotSpec], grid, paper: str, orientation: str, title: str, header: str,
              font_path: str | None = None, font: float = 8.5, spans: list | None = None) -> str:
    landscape = choose_landscape(orientation, grid)
    w, h = page_size(paper, landscape)
    scale = max(0.6, min(2.5, (w * h / (842 * 595)) ** 0.5))   # Schrift wächst mit dem Papier
    doc = PdfDocument(title, front=False, footer=True, page_size=(w, h), font_path=font_path, page_label=t("Seite"))
    for cells in layout_cells(len(specs), grid, w, h, header=22 * scale, min_h=150 * scale, spans=spans):
        doc.new_page()
        canvas = PdfCanvas(doc, 0.0, h)
        canvas.text(28, 28 + 10 * scale, header, 9 * scale, DIM_RGB)
        for index, x, y, cw, ch in cells:
            render_plot(canvas, specs[index], x, y, cw, ch, font * scale)
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def write_svg(path: str, specs: list[PlotSpec], grid, paper: str, orientation: str, header: str,
              font: float = 8.5, spans: list | None = None) -> list[str]:
    """Eine SVG-Datei je Seite (name.svg, bei mehreren Seiten name_1.svg, name_2.svg, ...)."""
    landscape = choose_landscape(orientation, grid)
    w, h = page_size(paper, landscape)
    scale = max(0.6, min(2.5, (w * h / (842 * 595)) ** 0.5))
    base = path[:-4] if path.lower().endswith(".svg") else path
    pages = layout_cells(len(specs), grid, w, h, header=22 * scale, min_h=150 * scale, spans=spans)
    written = []
    for number, cells in enumerate(pages, 1):
        canvas = SvgCanvas(w, h)
        canvas.text(28, 28 + 10 * scale, header, 9 * scale, DIM_RGB)
        for index, x, y, cw, ch in cells:
            render_plot(canvas, specs[index], x, y, cw, ch, font * scale)
        target = f"{base}_{number}.svg" if len(pages) > 1 else f"{base}.svg"
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(canvas.to_svg(), encoding="utf-8")
        written.append(target)
    return written


def print_file(path: str) -> str:
    """Schickt das PDF an den Standarddrucker. Liefert den genutzten Weg; Fehler als OSError."""
    if sys.platform.startswith("win"):
        os.startfile(path, "print")  # type: ignore[attr-defined]  # Standard-PDF-Programm druckt
        return "Windows"
    for command in ("lp", "lpr"):
        exe = shutil.which(command)
        if exe:
            result = subprocess.run([exe, path], capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise OSError((result.stderr or result.stdout).strip() or f"{command}: Fehler {result.returncode}")
            return command
    raise OSError("kein Druckbefehl gefunden (lp oder lpr)")
