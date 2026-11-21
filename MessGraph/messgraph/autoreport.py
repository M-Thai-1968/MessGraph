"""Report über mehrere Auswertungen (je Auswertung ein DUT) aus den Ausgaben der Auto-Auswertung.

Aufbau wie das Muster (A4 quer):
1. Deckblatt: Test Report, Project, Mode, Date, Hinweiszeile
2. Summary Comparison: je Signal der Mittelwert je DUT, Average, Min %, Max % (Abweichung des kleinsten/größten
   DUT-Mittelwerts vom Average), Limit Min, Limit Max
3. Signal Plot Comparison: je Signal eine Seite mit den PNG aller DUTs (3 x 3)
4. je DUT: Tabelle Signal, Min, Max, Mean, Std, Limit Min, Limit Max (Mean grün im Limit, rot außerhalb), danach
   alle PNG des DUT (3 x 3)
"NOT RELEASED" als Wasserzeichen auf jeder Seite (abwählbar).

Der Report wird nie abgebrochen: Fehler (fehlende/kaputte Bilder, unlesbare statistics.json, Fehler in einem Abschnitt,
Schreibfehler) werden gesammelt, der Rest wird erzeugt. Ein unvollständiger Report bekommt am Ende einen Anhang
"Appendix: Incomplete Report" mit allen Gründen und die Endung _err (Report_..._err.pdf).

Grundlage je Auswertung: <Ziel>/<Gruppe>/statistics.json und die PNG daneben (von AutoEngine geschrieben).
PNG werden ohne Umrechnen eingebettet (IDAT-Daten mit PNG-Prädiktor), sonst über Pillow als RGB.
"""
from __future__ import annotations

import json
import math
import os
import re
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .data_model import LoadError
from .i18n import Translated, t, translate_to
from .pdfdoc import _escape, encode, text_width

PAGE_W, PAGE_H = 841.89, 595.28            # A4 quer
MARGIN = 56.0
TEXT = (0.11, 0.11, 0.11)
DIM = (0.45, 0.45, 0.45)
GRID = (0.55, 0.55, 0.55)
HEAD_FILL = (0.86, 0.86, 0.86)
GREEN = (0.0, 0.55, 0.0)
RED = (0.93, 0.05, 0.05)
WATERMARK = "NOT RELEASED"


@dataclass
class Dut:
    label: str                      # Spaltenkopf (DUT5 ...)
    title: str                      # Überschrift des DUT-Abschnitts
    folder: Path
    stats: dict                     # Signal -> Kennwerte (statistics.json)
    mode: str | None = None


@dataclass
class ReportOptions:
    project: str = ""
    mode: str = ""
    title: str = "Test Report"
    watermark: bool = True
    per_page: int = 9                                  # Graphen pro Seite nur im Mode-Teil (je DUT): 9, 4, 2 oder 1
    note: str = "Automatically generated report including signal statistics, plots and comparison across DUTs."


def collect(jobs: list[dict]) -> tuple[list[Dut], list[str]]:
    """DUTs der gewählten Auswertungen: je Gruppe mit statistics.json im Zielverzeichnis einer."""
    duts, problems = [], []
    for job in jobs:
        target = Path(job.get("target") or "")
        found = sorted(target.glob("*/statistics.json")) if target.is_dir() else []
        if not found:
            problems.append(t("{name}: keine Ausgaben in {target} - Zyklus ausführen bzw. Log prüfen (lesbar sind "
                              "*.csv, *.asc, *.parquet).", name=job.get("name", "?"), target=job.get("target") or "-"))
            continue
        for path in found:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                problems.append(f"{path}: {exc}")
                continue
            group = data.get("group") or path.parent.name
            own = re.search(r"(DUT\d+)$", str(job.get("name", "")).strip(), re.IGNORECASE)   # Name ist führend
            match = own or re.search(r"(DUT\d+)", group, re.IGNORECASE)
            label = match.group(1).upper() if match else job.get("name", group)
            duts.append(Dut(label, f"Mode: {group}", path.parent,
                            data.get("signals") or {}, data.get("mode")))
    used = {}
    for dut in duts:                                   # gleiche Kennung (zwei Auswertungen mit DUT2): eindeutig machen
        used[dut.label] = used.get(dut.label, 0) + 1
        if used[dut.label] > 1:
            dut.label = f"{dut.label}_{used[dut.label]}"
    return duts, problems


# ---------------------------------------------------------------- Zahlen
def num(value, digits: int = 3) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "-"
    if value == 0:
        return "0.0"
    text = f"{round(value, digits):.{digits}f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def summary_rows(duts: list[Dut]) -> list[dict]:
    names = sorted({n for d in duts for n in d.stats}, key=str.casefold)
    rows = []
    for name in names:
        means = [d.stats.get(name, {}).get("mean") for d in duts]
        valid = [m for m in means if isinstance(m, (int, float)) and math.isfinite(m)]
        avg = sum(valid) / len(valid) if valid else None
        if avg:
            lo_pct = (min(valid) - avg) / abs(avg) * 100
            hi_pct = (max(valid) - avg) / abs(avg) * 100
            lo_txt, hi_txt = num(lo_pct, 2), num(hi_pct, 2)
        else:
            lo_txt = hi_txt = "n.a."
        limits = next(((d.stats[name].get("lo"), d.stats[name].get("hi")) for d in duts
                       if name in d.stats and (d.stats[name].get("lo") is not None or d.stats[name].get("hi") is not None)),
                      (None, None))
        rows.append({"name": name, "means": [num(m) for m in means], "avg": num(avg, 2), "min_pct": lo_txt,
                     "max_pct": hi_txt, "lo": limits[0], "hi": limits[1]})
    return rows


# ---------------------------------------------------------------- PNG einbetten
def png_image(path: Path, max_px: int = 1600):
    """(Breite, Höhe, Datenstrom, Decode-Parameter) für ein PDF-Bild-XObject.

    RGB-PNG mit 8 Bit ohne Zeilensprung: IDAT direkt übernehmen (schnell, klein). Sonst mit Pillow umrechnen."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        pos, idat, width = 8, [], 0
        ok = True
        while pos < len(data):
            length, kind = struct.unpack(">I4s", data[pos:pos + 8])
            chunk = data[pos + 8:pos + 8 + length]
            if kind == b"IHDR":
                width, height, depth, color, _c, _f, interlace = struct.unpack(">IIBBBBB", chunk)
                ok = depth == 8 and color == 2 and interlace == 0
            elif kind == b"IDAT":
                idat.append(chunk)
            elif kind in (b"PLTE", b"tRNS"):
                ok = False
            pos += 12 + length
        if ok and idat and width:
            parms = b"/DecodeParms << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns %d >>" % width
            return width, height, b"".join(idat), parms
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        if im.width > max_px:
            im = im.resize((max_px, round(im.height * max_px / im.width)))
        return im.width, im.height, zlib.compress(im.tobytes(), 6), b""


# ---------------------------------------------------------------- PDF
@dataclass
class _Page:
    ops: list = field(default_factory=list)
    images: list = field(default_factory=list)


class ReportPdf:
    """Kleiner PDF-Schreiber für den Report: Helvetica, Tabellen, eingebettete PNG, Wasserzeichen."""

    def __init__(self, watermark: bool):
        self.pages: list[_Page] = []
        self.images: dict[str, tuple] = {}
        self.watermark = watermark

    def page(self) -> _Page:
        self.pages.append(_Page())
        return self.pages[-1]

    def text(self, x, y, text, size, bold=False, rgb=TEXT, anchor="start") -> None:
        font = "F2" if bold else "F1"
        width = text_width(text, font, size)
        x -= {"start": 0, "middle": width / 2, "end": width}[anchor]
        self.pages[-1].ops.append(b"BT %.3f %.3f %.3f rg /%s %.2f Tf %.2f %.2f Td (%s) Tj ET"
                                  % (*rgb, font.encode(), size, x, y, _escape(encode(text))))

    def fit(self, text: str, size: float, width: float, bold=False) -> str:
        font = "F2" if bold else "F1"
        if text_width(text, font, size) <= width:
            return text
        while text and text_width(text + "...", font, size) > width:
            text = text[:-1]
        return text + "..."

    def rect(self, x, y, w, h, fill=None, stroke=None, width=0.5) -> None:
        ops = [b"q"]
        if fill:
            ops.append(b"%.3f %.3f %.3f rg" % fill)
        if stroke:
            ops.append(b"%.3f %.3f %.3f RG %.2f w" % (*stroke, width))
        ops.append(b"%.2f %.2f %.2f %.2f re %s Q" % (x, y, w, h, b"B" if fill and stroke else b"f" if fill else b"S"))
        self.pages[-1].ops.append(b" ".join(ops))

    def line(self, x0, y0, x1, y1, rgb=GRID, width=0.5) -> None:
        self.pages[-1].ops.append(b"q %.3f %.3f %.3f RG %.2f w %.2f %.2f m %.2f %.2f l S Q" % (*rgb, width, x0, y0, x1, y1))

    def image(self, path: Path, x, y, w, h) -> tuple[float, float]:
        """Bild in das Feld (x, y unten links, w, h) einpassen; liefert die tatsächliche Größe."""
        key = str(path)
        if key not in self.images:
            self.images[key] = (f"Im{len(self.images) + 1}",) + png_image(path)
        name, iw, ih, _data, _parms = self.images[key]
        scale = min(w / iw, h / ih)
        dw, dh = iw * scale, ih * scale
        ox, oy = x + (w - dw) / 2, y + (h - dh)
        self.pages[-1].ops.append(b"q %.2f 0 0 %.2f %.2f %.2f cm /%s Do Q" % (dw, dh, ox, oy, name.encode()))
        self.pages[-1].images.append(key)
        return dw, dh

    def _watermark(self) -> bytes:
        """Großer, schräger Umriss-Text in hellem Grau über der Seite."""
        size = 92.0
        width = text_width(WATERMARK, "F2", size)
        angle = math.atan2(PAGE_H, PAGE_W) * 0.9
        c, s = math.cos(angle), math.sin(angle)
        cx, cy = PAGE_W / 2, PAGE_H / 2
        x0 = cx - c * width / 2 + s * size * 0.35
        y0 = cy - s * width / 2 - c * size * 0.35
        return (b"q 0.82 0.82 0.82 RG 1.2 w BT 1 Tr /F2 %.1f Tf %.5f %.5f %.5f %.5f %.2f %.2f Tm (%s) Tj ET Q"
                % (size, c, s, -s, c, x0, y0, _escape(encode(WATERMARK))))

    def to_bytes(self) -> bytes:
        objects: list[bytes] = []

        def add(body: bytes) -> int:
            objects.append(body)
            return len(objects)

        fonts = {"F1": add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"),
                 "F2": add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")}
        image_ids = {}
        for key, (name, w, h, data, parms) in self.images.items():
            image_ids[key] = (name, add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                                        b"/BitsPerComponent 8 /Filter /FlateDecode %s /Length %d >>\nstream\n"
                                        % (w, h, parms, len(data)) + data + b"\nendstream"))
        total = len(self.pages)
        pages_id = len(objects) + 1 + 2 * total
        font_res = b" ".join(b"/%s %d 0 R" % (k.encode(), v) for k, v in fonts.items())
        page_ids = []
        for number, page in enumerate(self.pages, 1):
            ops = list(page.ops)
            label = f"Page {number} / {total}"
            ops.append(b"BT %.3f %.3f %.3f rg /F1 7.5 Tf %.2f %.2f Td (%s) Tj ET"
                       % (*TEXT, PAGE_W - MARGIN * 0.7 - text_width(label, "F1", 7.5), 22.0, encode(label)))
            if self.watermark:
                ops.append(self._watermark())
            stream = zlib.compress(b"\n".join(ops), 6)
            content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
            xobj = b" ".join(b"/%s %d 0 R" % (image_ids[k][0].encode(), image_ids[k][1]) for k in dict.fromkeys(page.images))
            res = b"<< /Font << %s >>%s >>" % (font_res, b" /XObject << %s >>" % xobj if xobj else b"")
            page_ids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R /Resources %s >>"
                                % (pages_id, PAGE_W, PAGE_H, content, res)))
        assert len(objects) + 1 == pages_id
        add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % i for i in page_ids), total))
        catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
        info = add(b"<< /Title (Test Report) /Producer (MessGraph) >>")
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, body in enumerate(objects, 1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
        out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
        out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            len(objects) + 1, catalog, info, xref)
        return bytes(out)


# ---------------------------------------------------------------- Inhalt
def _table(pdf: ReportPdf, headers: list[str], rows: list[list], weights: list[float], top: float,
           heading: str | None, fills=None, gap_after: int | None = None) -> None:
    """Tabelle mit Kopfzeile, über Seiten fortgesetzt (Kopf wiederholt). rows: Zellen als Text oder (Text, Farbe, Füllung)."""
    row_h, size = 18.0, 6.8
    usable = PAGE_W - 2 * MARGIN
    gap = 10.0 if gap_after is not None else 0.0
    scale = (usable - gap) / sum(weights)
    widths = [w * scale for w in weights]
    xs, x = [], MARGIN
    for i, w in enumerate(widths):
        xs.append(x)
        x += w + (gap if gap_after is not None and i == gap_after else 0)

    def header(y):
        for i, label in enumerate(headers):
            pdf.rect(xs[i], y - row_h, widths[i], row_h, fill=HEAD_FILL, stroke=GRID)
            pdf.text(xs[i] + 4, y - row_h + 6, pdf.fit(label, size, widths[i] - 6), size)
        return y - row_h

    index = 0
    first = True
    while index < len(rows) or first:
        pdf.page()
        y = top
        if heading and first:
            pdf.text(MARGIN, y, heading, 15, bold=True)
            y -= 26
        y = header(y)
        first = False
        while index < len(rows) and y - row_h >= MARGIN + 10:
            for i, cell in enumerate(rows[index]):
                text, rgb, fill = (cell, TEXT, None) if not isinstance(cell, tuple) else cell
                pdf.rect(xs[i], y - row_h, widths[i], row_h, fill=fill, stroke=GRID)
                pdf.text(xs[i] + 4, y - row_h + 6, pdf.fit(str(text), size, widths[i] - 6), size, rgb=rgb)
            y -= row_h
            index += 1


def _limit_cell(value):
    return (num(value), TEXT, None) if value is not None else ("-", DIM, None)


def _grid(pdf: ReportPdf, items: list[tuple[Path, str]], cols: int, rows: int, top: float, heading: str | None = None,
          subheading: str | None = None, progress=None, issues: list | None = None) -> None:
    """Bilder im Raster mit Bildunterschrift; neue Seite, wenn voll."""
    per_page = cols * rows
    for start in range(0, max(1, len(items)), per_page):
        pdf.page()
        y = top
        if heading and start == 0:
            pdf.text(MARGIN, y, heading, 15, bold=True)
            y -= 30
        if subheading and start == 0:
            pdf.text(MARGIN, y, subheading, 12, bold=True)
            y -= 14
        cell_w = (PAGE_W - 2 * MARGIN) / cols
        cell_h = (y - MARGIN - 6) / rows
        for i, (path, caption) in enumerate(items[start:start + per_page]):
            r, c = divmod(i, cols)
            x0, y0 = MARGIN + c * cell_w, y - (r + 1) * cell_h
            box_h = cell_h - 18
            caption_y = y0 + 4
            placed = False
            if path is not None and path.is_file():
                try:
                    _dw, dh = pdf.image(path, x0 + 4, y0 + 14, cell_w - 8, box_h)
                    caption_y = y0 + 14 + box_h - dh - 10      # Bildunterschrift direkt unter dem Bild
                    placed = True
                except Exception as exc:                       # kaputtes Bild: Platzhalter, Grund in den Anhang
                    if issues is not None:
                        issues.append(t("Bild nicht eingebettet: {path} ({error})", path=path,
                                        error=f"{type(exc).__name__}: {exc}"))
            elif path is not None and issues is not None:
                issues.append(t("Bild fehlt: {path}", path=path))
            if not placed:
                pdf.text(x0 + cell_w / 2, y0 + cell_h / 2, "(image missing)", 8, rgb=DIM, anchor="middle")
            pdf.text(x0 + cell_w / 2, caption_y, pdf.fit(caption, 7.5, cell_w - 8), 7.5, anchor="middle")
            if progress:
                progress()


GRID_LAYOUTS = {9: (3, 3), 4: (2, 2), 2: (2, 1), 1: (1, 1)}     # Graphen pro Seite -> Spalten x Zeilen


def grid_layout(per_page) -> tuple[int, int]:
    try:
        return GRID_LAYOUTS[int(per_page)]
    except (KeyError, TypeError, ValueError):
        return GRID_LAYOUTS[9]


def err_path(path: str) -> str:
    """Report_x.pdf -> Report_x_err.pdf (unvollständiger Report)."""
    base, ext = os.path.splitext(path)
    return path if base.endswith("_err") else f"{base}_err{ext or '.pdf'}"


def _english(text) -> str:
    """Gründe im Anhang auf Englisch (der Report ist englisch, Helvetica kann kein Thai/Chinesisch)."""
    if isinstance(text, Translated):
        values = {k: _english(v) for k, v in text.values.items()}
        try:
            found = translate_to("English", text.key)
            return found.format(**values) if values else found
        except (KeyError, IndexError, ValueError):
            pass
    return str(text)


def _wrap(text: str, size: float, width: float) -> list[str]:
    lines, line = [], ""
    for word in str(text).replace("\n", " ").split(" "):
        candidate = f"{line} {word}" if line else word
        if text_width(candidate, "F1", size) <= width or not line:
            line = candidate
            while text_width(line, "F1", size) > width and len(line) > 1:   # sehr langes Wort (Pfad): hart trennen
                cut = len(line)
                while cut > 1 and text_width(line[:cut], "F1", size) > width:
                    cut -= 1
                lines.append(line[:cut])
                line = line[cut:]
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]


def _appendix(pdf: ReportPdf, issues: list[str]) -> None:
    """Anhang mit den Gründen für einen unvollständigen Report; auf dem Deckblatt ein roter Hinweis."""
    if pdf.pages:
        pdf.pages[0].ops.append(b"BT %.3f %.3f %.3f rg /F2 11 Tf %.2f %.2f Td (%s) Tj ET" % (
            *RED, MARGIN + 10, 130.0, _escape(encode("INCOMPLETE REPORT - see Appendix (file name suffix _err)"))))
    size, width, lead = 9.0, PAGE_W - 2 * MARGIN - 24, 12.0
    pdf.page()
    y = PAGE_H - 70
    pdf.text(MARGIN, y, "Appendix: Incomplete Report", 15, bold=True)
    y -= 24
    intro = ("This report could not be generated completely. Report generation was not cancelled: all content that "
             "could be produced is included, the affected parts are missing or incomplete for the reasons listed "
             "below. The file name carries the suffix _err.")
    for line in _wrap(intro, size, width + 24):
        pdf.text(MARGIN, y, line, size)
        y -= lead
    y -= 8
    pdf.text(MARGIN, y, f"Reasons ({len(issues)}):", 11, bold=True)
    y -= 18
    for number, issue in enumerate(issues, 1):
        lines = _wrap(_english(issue), size, width)
        for k, line in enumerate(lines):
            if y < MARGIN + 10:
                pdf.page()
                y = PAGE_H - 70
                pdf.text(MARGIN, y, "Appendix: Incomplete Report (continued)", 12, bold=True)
                y -= 22
            if k == 0:
                pdf.text(MARGIN, y, f"{number}.", size, bold=True)
            pdf.text(MARGIN + 24, y, line, size, rgb=TEXT)
            y -= lead
        y -= 3


def _cover(pdf: ReportPdf, duts: list[Dut], options: ReportOptions) -> None:
    pdf.page()
    pdf.text(PAGE_W / 2, PAGE_H - 92, options.title or "Test Report", 20, bold=True, anchor="middle")
    y = PAGE_H - 150
    for label, value in (("Project:", options.project), ("Mode:", options.mode)):
        pdf.text(MARGIN + 10, y, label, 11, bold=True)
        pdf.text(MARGIN + 10 + text_width(label + " ", "F2", 11), y, value or "-", 11)
        y -= 20
    pdf.text(MARGIN + 10, y - 66, "Date:", 11, bold=True)
    pdf.text(MARGIN + 10 + text_width("Date: ", "F2", 11), y - 66, datetime.now().strftime("%Y-%m-%d %H:%M"), 11)
    pdf.text(MARGIN + 10, y - 100, "DUTs:", 9, bold=True)
    pdf.text(MARGIN + 10 + text_width("DUTs: ", "F2", 9), y - 100,
             pdf.fit(", ".join(d.label for d in duts) or "-", 9, PAGE_W - 2 * MARGIN - 60), 9)
    pdf.text(PAGE_W / 2, 92, options.note, 7.5, anchor="middle")


def _png(dut: Dut, name: str, issues: list) -> Path | None:
    """Bild eines Signals laut statistics.json; fehlt der Eintrag, Grund in den Anhang."""
    entry = dut.stats.get(name)
    if entry is None:
        return None                                    # Signal gibt es bei diesem DUT nicht: kein Fehler
    png = entry.get("png") if isinstance(entry, dict) else None
    if not png:
        issues.append(t("{dut}: kein Bild für {name} in statistics.json ({folder})", dut=dut.label, name=name,
                        folder=dut.folder))
        return None
    return dut.folder / png


def build_report(path: str, duts: list[Dut], options: ReportOptions, progress=None, cancel=None,
                 issues: list | None = None) -> str:
    """Report als PDF schreiben. progress(Schritt, Gesamt, Text) für die Fortschrittsanzeige.

    Wird nie abgebrochen (cancel wird nicht mehr ausgewertet): Fehler eines Abschnitts oder Bildes werden gesammelt,
    alle übrigen Inhalte erzeugt. issues: bereits bekannte Gründe (z. B. Auswertungen ohne Ausgaben). Gibt es Gründe,
    bekommt der Report einen Anhang mit allen Gründen und die Endung _err. Liefert den geschriebenen Pfad."""
    issues = list(issues or [])
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    if not duts:
        issues.append(t("Keine Auswertung mit Ausgaben gefunden - der Report enthält nur Deckblatt und Anhang."))
    for dut in duts:                                   # unlesbare Kennwerte vorab aussortieren, Rest bleibt vollständig
        if not isinstance(dut.stats, dict):
            issues.append(t("{dut}: Kennwerte von {name} unlesbar", dut=dut.label, name="statistics.json"))
            dut.stats = {}
        for name in [n for n, st in dut.stats.items() if not isinstance(st, dict)]:
            issues.append(t("{dut}: Kennwerte von {name} unlesbar", dut=dut.label, name=name))
            del dut.stats[name]
    pdf = ReportPdf(options.watermark)
    names = sorted({n for d in duts for n in d.stats}, key=str.casefold)
    total = len(names) * len(duts) * 2 + 2
    done = [0]

    def step(text=""):
        done[0] += 1
        if progress:
            try:
                progress(done[0], total, text)
            except Exception:                          # Anzeige darf den Report nie stoppen
                pass

    def guard(section: str, action) -> None:
        try:
            action()
        except Exception as exc:
            issues.append(t("Abschnitt {section} unvollständig: {error}", section=section,
                            error=f"{type(exc).__name__}: {exc}"))

    guard("Cover", lambda: _cover(pdf, duts, options))
    step(t("Deckblatt"))

    def summary():
        rows = []
        for row in summary_rows(duts):
            rows.append([row["name"], *row["means"], row["avg"], row["min_pct"], row["max_pct"],
                         _limit_cell(row["lo"]), _limit_cell(row["hi"])])
        headers = ["Signal", *[d.label for d in duts], "Average", "Min %", "Max %", "Limit Min", "Limit Max"]
        weights = [2.2] + [1.0] * len(duts) + [1.0, 0.9, 0.9, 0.9, 0.9]
        _table(pdf, headers, rows, weights, PAGE_H - 70, "Summary Comparison", gap_after=len(duts) + 3)

    if duts:
        guard("Summary Comparison", summary)
    step(t("Übersicht"))

    # Signal Plot Comparison
    for number, name in enumerate(names):
        def comparison(number=number, name=name):
            items = [(_png(d, name, issues), f"{name.replace('_', ' ')} {d.label}") for d in duts]
            # Vergleichsteil immer 9 pro Seite (die Auswahl Graphen pro Seite gilt nur für den Mode-Teil)
            _grid(pdf, items, 3, 3, PAGE_H - 70, "Signal Plot Comparison" if number == 0 else None,
                  f"Signal Comparison: {name}", progress=lambda: step(t("Vergleich {name}", name=name)), issues=issues)
        guard(f"Signal Comparison {name}", comparison)

    # je DUT
    for dut in duts:
        def table(dut=dut):
            rows = []
            for name in sorted(dut.stats, key=str.casefold):
                st = dut.stats[name]
                if not isinstance(st, dict):
                    issues.append(t("{dut}: Kennwerte von {name} unlesbar", dut=dut.label, name=name))
                    continue
                mean = num(st.get("mean"), 2)
                inside = st.get("mean_inside")
                mean_cell = (mean, (1, 1, 1) if inside is not None else TEXT,
                             GREEN if inside else RED if inside is False else None)
                rows.append([name, num(st.get("min"), 2), num(st.get("max"), 2), mean_cell, num(st.get("std"), 2),
                             _limit_cell(st.get("lo")), _limit_cell(st.get("hi"))])
            _table(pdf, ["Signal", "Min", "Max", "Mean", "Std", "Limit Min", "Limit Max"], rows,
                   [2.2, 1, 1, 1, 1, 1, 1], PAGE_H - 70, dut.title)

        def images(dut=dut):
            items = [(_png(dut, n, issues), n.replace("_", " ")) for n in sorted(dut.stats, key=str.casefold)]
            _grid(pdf, items, *grid_layout(options.per_page), PAGE_H - 50,
                  progress=lambda: step(t("{dut}: Bilder", dut=dut.label)), issues=issues)
        guard(f"{dut.label} table", table)
        guard(f"{dut.label} plots", images)

    return _finish(path, pdf, duts, options, issues)


def _finish(path: str, pdf: ReportPdf, duts: list[Dut], options: ReportOptions, issues: list) -> str:
    """PDF erzeugen und schreiben; bei Gründen mit Anhang und Endung _err. Schlägt das Schreiben fehl, wird der
    Grund ergänzt und unter einem Ausweichnamen (gleicher Ordner, dann Benutzerordner) geschrieben."""
    from . import safewrite
    content = len(pdf.pages)
    candidates = [path]
    for attempt in range(4):
        issues[:] = list(dict.fromkeys(issues))       # doppelte Gründe (Bild im Vergleich und je DUT) einmal
        del pdf.pages[content:]
        if pdf.pages:
            pdf.pages[0].ops = [op for op in pdf.pages[0].ops if b"INCOMPLETE REPORT" not in op]
        if issues:
            _appendix(pdf, issues)
        try:
            data = pdf.to_bytes()
        except Exception as exc:                       # z. B. Bilddaten: Report ohne Bilder, nur Tabellen + Anhang
            issues.append(t("PDF mit Bildern nicht erzeugbar, Bilder weggelassen: {error}",
                            error=f"{type(exc).__name__}: {exc}"))
            pdf.images.clear()
            for page in pdf.pages:
                page.ops = [op for op in page.ops if not op.endswith(b" Do Q")]
                page.images.clear()
            continue
        target = err_path(candidates[-1]) if issues else candidates[-1]
        try:
            safewrite.write_bytes(target, data)
            return target
        except Exception as exc:
            issues.append(t("Report nicht schreibbar als {path}: {error}", path=target,
                            error=f"{type(exc).__name__}: {exc}"))
            folder, name = os.path.split(path)
            base = os.path.splitext(name)[0]
            stamp = datetime.now().strftime("%H%M%S")
            nxt = os.path.join(folder, f"{base}_{stamp}.pdf") if len(candidates) == 1 else \
                os.path.join(str(Path.home()), name)
            candidates.append(nxt)
    raise LoadError(t("Report nicht erstellt: {error}", error="; ".join(_english(i) for i in issues[-3:])))
