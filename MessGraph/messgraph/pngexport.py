"""Graph als PNG-Bild: Zeichenfläche für plotexport.render_plot mit Pillow (wie SvgCanvas/PdfCanvas).

Koordinaten in Punkten wie bei SVG/PDF; scale bestimmt die Pixel je Punkt. Ohne Pillow gibt available() False
zurück (dann schreibt die Auto-Auswertung SVG statt PNG und vermerkt das im Log).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from .plotexport import TEXT_RGB, PlotSpec, render_plot

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
]
BOLD_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


_SCRIPT_CACHE: dict = {}


def _script_fonts() -> list[str]:
    """Thai/Chinesisch: Texte in den Bildern brauchen eine Schrift mit diesen Zeichen (vor den lateinischen)."""
    from . import fonts, i18n
    language = i18n.language()
    if language not in ("Thai", "Chinese"):
        return []
    if language not in _SCRIPT_CACHE:
        _SCRIPT_CACHE[language] = fonts.find_cjk_font() if language == "Chinese" else fonts.find_thai_font()
    return [_SCRIPT_CACHE[language]] if _SCRIPT_CACHE[language] else []


def available() -> bool:
    try:
        import PIL.Image  # noqa: F401
        return True
    except ImportError:
        return False


class PngCanvas:
    def __init__(self, width: float, height: float, scale: float = 2.0):
        from PIL import Image, ImageDraw
        self.Image, self.ImageDraw = Image, ImageDraw
        self.width, self.height, self.scale = width, height, scale
        self.image = Image.new("RGB", (int(round(width * scale)), int(round(height * scale))), "white")
        self.layers = [self.image]
        self.fonts = {}

    # ---------------------------------------------------------------- Hilfen
    @property
    def draw(self):
        return self.ImageDraw.Draw(self.layers[-1])

    def _font(self, size: float, bold: bool = False):
        key = (round(size * self.scale), bold)
        if key not in self.fonts:
            from PIL import ImageFont
            font = None
            for path in _script_fonts() + (BOLD_CANDIDATES if bold else []) + FONT_CANDIDATES:
                if os.path.isfile(path):
                    try:
                        font = ImageFont.truetype(path, max(6, key[0]))
                        break
                    except OSError:
                        continue
            if font is None:
                try:
                    font = ImageFont.load_default(size=max(6, key[0]))
                except TypeError:                    # ältere Pillow-Versionen
                    font = ImageFont.load_default()
            self.fonts[key] = font
        return self.fonts[key]

    def _p(self, x, y):
        return x * self.scale, y * self.scale

    # ---------------------------------------------------------------- Schnittstelle wie SvgCanvas
    def text_width(self, text: str, size: float, bold: bool = False) -> float:
        font = self._font(size, bold)
        try:
            return font.getlength(text) / self.scale
        except AttributeError:
            return len(text) * size * 0.55

    def line(self, points, rgb, width: float = 1.0, dash: str | None = None) -> None:
        if len(points) < 2:
            return
        px = [self._p(x, y) for x, y in points]
        w = max(1, int(round(width * self.scale)))
        color = tuple(int(c) for c in rgb[:3])
        if not dash:
            self.draw.line(px, fill=color, width=w, joint="curve")
            return
        values = [float(v) * self.scale for v in dash.replace(",", " ").split()[:2]] or [4.0 * self.scale]
        on, off = values[0], values[-1]
        draw, pen, left = self.draw, True, on
        for (x0, y0), (x1, y1) in zip(px, px[1:]):
            length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            pos = 0.0
            while pos < length - 1e-9:
                step = min(left, length - pos)
                if pen:
                    a, b = pos / length, (pos + step) / length
                    draw.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)],
                              fill=color, width=w)
                pos += step
                left -= step
                if left <= 1e-9:
                    pen = not pen
                    left = on if pen else off

    def rect(self, x, y, w, h, stroke=None, fill=None, width: float = 0.6) -> None:
        x0, y0 = self._p(x, y)
        x1, y1 = self._p(x + w, y + h)
        self.draw.rectangle([x0, y0, x1, y1], fill=tuple(fill[:3]) if fill else None,
                            outline=tuple(stroke[:3]) if stroke else None,
                            width=max(1, int(round(width * self.scale))) if stroke else 0)

    def text(self, x, y, text, size, rgb=TEXT_RGB, anchor="start", bold=False, rotate=False) -> None:
        font = self._font(size, bold)
        color = tuple(int(c) for c in rgb[:3])
        width = self.text_width(text, size, bold) * self.scale
        shift = {"start": 0.0, "middle": width / 2, "end": width}[anchor]
        px, py = self._p(x, y)
        if not rotate:                                   # y ist die Grundlinie wie in SVG/PDF
            self.draw.text((px - shift, py), text, fill=color, font=font, anchor="ls")
            return
        height = int(size * self.scale * 1.6) + 2
        tile = self.Image.new("RGBA", (int(width) + 4, height), (255, 255, 255, 0))
        self.ImageDraw.Draw(tile).text((2, height * 0.75), text, fill=color + (255,), font=font, anchor="ls")
        tile = tile.rotate(90, expand=True)
        target = self.layers[-1]
        target.paste(tile, (int(px - height * 0.75), int(py - shift - tile.size[1] + 2)), tile)

    @contextmanager
    def group(self, key: str):
        yield

    @contextmanager
    def clip(self, x, y, w, h):
        """Zeichnen auf einer eigenen Ebene, danach nur das Rechteck übernehmen."""
        layer = self.Image.new("RGBA", self.image.size, (0, 0, 0, 0))
        self.layers.append(layer)
        try:
            yield
        finally:
            self.layers.pop()
            box = tuple(int(round(v)) for v in (*self._p(x, y), *self._p(x + w, y + h)))
            part = layer.crop(box)
            self.layers[-1].paste(part, box[:2], part)

    def save(self, path: str) -> str:
        import io
        from . import safewrite
        buf = io.BytesIO()
        self.image.save(buf, "PNG", optimize=True)
        safewrite.write_bytes(path, buf.getvalue(), tmp_suffix=".tmp.png")   # PNG evtl. im Bildbetrachter offen
        return path


def write_png(path: str, spec: PlotSpec, width_px: int = 1600, height_px: int = 900, font: float = 9.0) -> str:
    """Einen Graphen als PNG (Größe in Pixeln)."""
    scale = 2.0
    canvas = PngCanvas(width_px / scale, height_px / scale, scale)
    render_plot(canvas, spec, 10, 6, width_px / scale - 20, height_px / scale - 12, font)
    return canvas.save(path)
