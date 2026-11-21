"""Kleiner PDF-Schreiber ohne Zusatzpakete: Text in Helvetica, Aufzählungen, Bilder, Inhaltsverzeichnis.

Für das Handbuch genügt: A4, schmale Ränder, Kapitel auf neuer Seite, Seitenzahlen.
Text wird in Windows-1252 kodiert (deutsche und westeuropäische Zeichen).
"""
from __future__ import annotations

import time
import zlib
from dataclasses import dataclass, field

from . import pdf_metrics

PAGE_W, PAGE_H = 595.28, 841.89          # A4 in Punkt
MARGIN = 40.0                            # etwa 14 mm: schmale Ränder
FOOTER = 24.0
FONTS = {"F1": ("Helvetica", pdf_metrics.REGULAR), "F2": ("Helvetica-Bold", pdf_metrics.BOLD),
         "F3": ("Helvetica-Oblique", pdf_metrics.OBLIQUE)}
HEADING_RGB = (0.08, 0.33, 0.59)
TEXT_RGB = (0.11, 0.13, 0.15)
DIM_RGB = (0.38, 0.41, 0.45)


def encode(text: str) -> bytes:
    return text.encode("cp1252", errors="replace")


def text_width(text: str, font: str, size: float) -> float:
    widths = FONTS[font][1]
    total = 0
    for byte in encode(text):
        total += widths[byte - 32] if 32 <= byte <= 255 else 556
    return total * size / 1000.0


THAI_MARKS = {0x0E31, *range(0x0E34, 0x0E3B), *range(0x0E47, 0x0E4F)}   # stehen über/unter dem Zeichen davor
THAI_LEADING = set(range(0x0E40, 0x0E45))                                 # Vokale vor dem Konsonanten


CJK_NO_START = set("，。、：；！？）”’》」』】〕…—·%")   # nicht am Zeilenanfang
CJK_NO_END = set("（“‘《「『【〔")                         # nicht am Zeilenende


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return 0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF


def _can_break(text: str, i: int) -> bool:
    """Darf vor text[i] umgebrochen werden? Nicht vor Thai-Zeichen über/unter der Zeile, nicht nach Vorvokalen;
    chinesisch nicht vor schließenden und nicht nach öffnenden Satzzeichen, nicht innerhalb lateinischer Wörter
    zwischen chinesischem Text."""
    a, b = text[i - 1], text[i]
    if ord(b) in THAI_MARKS or ord(a) in THAI_LEADING:
        return False
    if b in CJK_NO_START or a in CJK_NO_END:
        return False
    if (_is_cjk(a) or _is_cjk(b)) or not (a.isascii() and b.isascii()):
        return True
    return not any(_is_cjk(ch) for ch in text)               # lateinisches Wort mitten in CJK-Text: zusammenlassen


def _fit(prefix: str, word: str, width: float, measure) -> int:
    """Größte Zahl Zeichen von word, die hinter prefix noch in die Zeile passt (an erlaubter Stelle)."""
    cut = len(word) - 1
    while cut >= 1 and (measure(prefix + word[:cut]) > width or not _can_break(word, cut)):
        cut -= 1
    return max(cut, 0)


def wrap(text: str, font: str, size: float, width: float, measure=None) -> list[str]:
    measure = measure or (lambda t: text_width(t, font, size))
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}" if line else word
        if measure(candidate) <= width:
            line = candidate
            continue
        if line:
            cut = _fit(line + " ", word, width, measure) if any(_is_cjk(ch) for ch in word) else 0
            if cut:                                              # Chinesisch: Zeile mit dem Wortanfang auffüllen
                lines.append(f"{line} {word[:cut]}")
                word = word[cut:]
            else:
                lines.append(line)
        line = word
        while measure(line) > width and len(line) > 1:          # langes Wort (Thai, Chinesisch ohne Leerzeichen) teilen
            cut = _fit("", line, width, measure)
            if cut < 1:
                break
            lines.append(line[:cut])
            line = line[cut:]
    if line:
        lines.append(line)
    return lines or [""]


def _escape(data: bytes) -> bytes:
    return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


@dataclass
class _Image:
    width: int
    height: int
    rgb: bytes


@dataclass
class _Page:
    ops: list = field(default_factory=list)
    images: list = field(default_factory=list)   # Namen der benutzten Bilder


class PdfDocument:
    """font_path: TrueType/OpenType-Schrift, die eingebettet wird (für Thai und andere Schriften außerhalb
    von Windows-1252). Ohne font_path: Standardschrift Helvetica."""

    def __init__(self, title: str, subtitle: str = "", toc_title: str = "Inhalt", page_label: str = "Seite",
                 font_path: str | None = None, page_size: tuple[float, float] = (PAGE_W, PAGE_H),
                 front: bool = True, footer: bool = True, cover_lines: list[str] | None = None):
        """front: Deckblatt und Inhaltsverzeichnis; footer: Titel und Seitenzahl unten; cover_lines: weitere
        Zeilen auf dem Deckblatt (z. B. Ersteller, Dateien)."""
        self.title, self.subtitle, self.toc_title, self.page_label = title, subtitle, toc_title, page_label
        self.page_w, self.page_h = page_size
        self.front, self.footer, self.cover_lines = front, footer, cover_lines or []
        self.ufont = None
        self.used: dict[int, str] = {}
        if font_path:
            from .ttf import TrueTypeFont
            self.ufont = TrueTypeFont(font_path)
        self.pages: list[_Page] = []
        self.images: dict[str, _Image] = {}
        self.chapters: list[tuple[str, int]] = []
        self.y = 0.0
        self.content_w = self.page_w - 2 * MARGIN

    # ------------------------------------------------------------ Seitenaufbau
    def _new_page(self) -> None:
        self.pages.append(_Page())
        self.y = self.page_h - MARGIN

    def _need(self, height: float) -> None:
        if not self.pages or self.y - height < MARGIN + FOOTER:
            self._new_page()

    def width(self, text: str, font: str, size: float) -> float:
        if self.ufont is None:
            return text_width(text, font, size)
        return sum(self.ufont.advance(self.ufont.glyph_id(ord(ch))) for ch in text) * size / 1000.0

    def _string(self, text: str, font: str) -> tuple[bytes, bytes]:
        """(Schriftname, Textoperand) für den Inhaltsstrom."""
        if self.ufont is None:
            return font.encode(), b"(" + _escape(encode(text)) + b")"
        glyphs = []
        for ch in text:
            gid = self.ufont.glyph_id(ord(ch))
            self.used.setdefault(gid, ch)
            glyphs.append(gid)
        return b"U1", b"<" + b"".join(b"%04X" % g for g in glyphs) + b">"

    def _text(self, x: float, y: float, text: str, font: str, size: float, rgb=TEXT_RGB) -> None:
        name, operand = self._string(text, font)
        self.pages[-1].ops.append(b"BT %.3f %.3f %.3f rg /%s %.2f Tf %.2f %.2f Td " % (*rgb, name, size, x, y)
                                  + operand + b" Tj ET")

    def _lines(self, text: str, font: str, size: float, indent: float = 0.0, rgb=TEXT_RGB,
               bullet: str | None = None, gap: float = 4.0) -> None:
        leading = size * (1.6 if self.ufont else 1.35)   # Thai/Chinesisch brauchen mehr Zeilenabstand
        lines = wrap(text, font, size, self.content_w - indent, lambda t: self.width(t, font, size))
        for number, line in enumerate(lines):
            self._need(leading)
            self.y -= leading
            if bullet and number == 0:
                self._text(MARGIN + indent - 11, self.y, bullet, font, size, rgb)
            self._text(MARGIN + indent, self.y, line, font, size, rgb)
        self.y -= gap

    # ------------------------------------------------------------ Inhalte
    def chapter(self, title: str) -> None:
        self._new_page()
        self.chapters.append((title, len(self.pages)))
        self.y -= 20
        self._text(MARGIN, self.y, title, "F2", 20, HEADING_RGB)
        self.y -= 10
        self.pages[-1].ops.append(b"%.3f %.3f %.3f RG 1 w %.2f %.2f m %.2f %.2f l S"
                                  % (*HEADING_RGB, MARGIN, self.y, self.page_w - MARGIN, self.y))
        self.y -= 8

    def heading(self, text: str) -> None:
        self._need(40)  # Überschrift nicht allein am Seitenende
        self.y -= 6
        self._lines(text, "F2", 12.5, rgb=HEADING_RGB, gap=2)

    def paragraph(self, text: str) -> None:
        self._lines(text, "F1", 10.5)

    def bullet(self, text: str) -> None:
        mark = "\u2022" if self.ufont is None or self.ufont.glyph_id(0x2022) else "-"
        self._lines(text, "F1", 10.5, indent=14, bullet=mark, gap=2)

    def marker(self, number: str, text: str) -> None:
        """Nummerierte Erklärung zu einer Bildmarkierung: oranger Kreis mit Nummer, daneben der Text."""
        size, leading = 10.0, 10.0 * (1.6 if self.ufont else 1.35)
        lines = wrap(text, "F1", size, self.content_w - 26, lambda t: self.width(t, "F1", size))
        self._need(leading + 4)
        self.y -= leading + 1
        cx, cy, r = MARGIN + 8, self.y + 3.4, 7.2
        k = 0.5523 * r
        self.pages[-1].ops.append(
            b"0.91 0.35 0.05 rg %.2f %.2f m %.2f %.2f %.2f %.2f %.2f %.2f c %.2f %.2f %.2f %.2f %.2f %.2f c "
            b"%.2f %.2f %.2f %.2f %.2f %.2f c %.2f %.2f %.2f %.2f %.2f %.2f c f"
            % (cx + r, cy, cx + r, cy + k, cx + k, cy + r, cx, cy + r, cx - k, cy + r, cx - r, cy + k, cx - r, cy,
               cx - r, cy - k, cx - k, cy - r, cx, cy - r, cx + k, cy - r, cx + r, cy - k, cx + r, cy))
        self._text(cx - self.width(number, "F2", 8.5) / 2, cy - 3.0, number, "F2", 8.5, (1, 1, 1))
        for i, line in enumerate(lines):
            if i:
                self._need(leading)
                self.y -= leading
            self._text(MARGIN + 22, self.y, line, "F1", size)
        self.y -= 2

    def note(self, text: str) -> None:
        self._lines(text, "F3", 9.5, rgb=DIM_RGB)

    def image(self, width: int, height: int, rgb: bytes, caption: str = "") -> None:
        name = f"Im{len(self.images) + 1}"
        self.images[name] = _Image(width, height, rgb)
        max_h = (self.page_h - 2 * MARGIN - FOOTER) * 0.62
        scale = min(self.content_w / width, max_h / height)
        w, h = width * scale, height * scale
        self._need(h + 30)
        self.y -= h + 4
        page = self.pages[-1]
        page.ops.append(b"q %.2f 0 0 %.2f %.2f %.2f cm /%s Do Q" % (w, h, MARGIN + (self.content_w - w) / 2, self.y,
                                                                   name.encode()))
        page.ops.append(b"0.75 0.77 0.80 RG 0.5 w %.2f %.2f %.2f %.2f re S" % (MARGIN + (self.content_w - w) / 2,
                                                                              self.y, w, h))
        page.images.append(name)
        if caption:
            self.y -= 2
            self._lines(caption, "F3", 9.5, rgb=DIM_RGB, gap=8)
        else:
            self.y -= 8

    def new_page(self) -> None:
        self._new_page()

    def available(self) -> float:
        """Freie Höhe bis zur Fußzeile auf der aktuellen Seite."""
        return (self.y - MARGIN - FOOTER) if self.pages else 0.0

    def space(self, height: float) -> None:
        self.y -= height

    def drawing(self, height: float, draw, width: float | None = None) -> None:
        """Fläche der Höhe height (Breite: ganze Spalte) für Vektorzeichnungen; draw(canvas, w, h)."""
        self._need(height + 6)
        width = width or self.content_w
        from .plotexport import PdfCanvas
        canvas = PdfCanvas(self, MARGIN, self.y)
        draw(canvas, width, height)
        self.y -= height + 6

    def table(self, headers: list[str], rows: list[list[str]], size: float = 8.5, weights: list[float] | None = None,
              bold_first: bool = False, fills: list | None = None) -> None:
        """Tabelle über die Spaltenbreite, Zellen mit Zeilenumbruch; Kopf wird nach Seitenwechsel wiederholt."""
        if not headers:
            return
        n = len(headers)
        if weights is None:
            natural = [max([self.width(str(h), "F2", size)] + [self.width(str(r[i]), "F1", size) for r in rows]) + 8
                       for i, h in enumerate(headers)]
            total = sum(natural)
            weights = [w / total for w in natural]
            minimum = 34.0 / self.content_w   # schmale Spalten nicht unter etwa 12 mm
            weights = [max(w, minimum) for w in weights]
        total = sum(weights)
        widths = [self.content_w * w / total for w in weights]
        leading = size * (1.6 if self.ufont else 1.3)

        def cells(values, font):
            return [wrap(str(v), font, size, w - 6, lambda t, f=font: self.width(t, f, size)) or [""]
                    for v, w in zip(values, widths)]

        def draw_row(values, font, fill=None):
            lines = cells(values, font)
            height = max(len(c) for c in lines) * leading + 4
            if not self.pages or self.y - height < MARGIN + FOOTER:
                return None
            top = self.y
            page = self.pages[-1]
            if fill:
                page.ops.append(b"%.3f %.3f %.3f rg %.2f %.2f %.2f %.2f re f" % (*fill, MARGIN, top - height,
                                                                               self.content_w, height))
            x = MARGIN
            for c, w in zip(lines, widths):
                y = top - 2
                for line in c:
                    y -= leading
                    self._text(x + 3, y + leading * 0.25, line, font, size,
                               HEADING_RGB if font == "F2" else TEXT_RGB)
                x += w
            page.ops.append(b"0.80 0.82 0.85 RG 0.4 w %.2f %.2f m %.2f %.2f l S" % (MARGIN, top - height,
                                                                                MARGIN + self.content_w, top - height))
            self.y = top - height
            return height

        def header():
            if draw_row(headers, "F2", (0.92, 0.94, 0.97)) is None:
                self._new_page()
                draw_row(headers, "F2", (0.92, 0.94, 0.97))

        self._need(leading * 3 + 8)
        header()
        for number, row in enumerate(rows):
            row = list(row) + [""] * (n - len(row))
            fill = fills[number] if fills and number < len(fills) else None    # z. B. rot: Zielzeit verletzt
            if draw_row(row, "F2" if bold_first and False else "F1", fill) is None:
                self._new_page()
                header()
                draw_row(row, "F1", fill)
        self.y -= 8

    # ------------------------------------------------------------ Ausgabe
    def _front_pages(self) -> list[_Page]:
        content, self.pages = self.pages, []
        self._new_page()
        self.y = self.page_h * 0.62
        self._text(MARGIN, self.y, self.title, "F2", 30, HEADING_RGB)
        self.y -= 28
        if self.subtitle:
            self._lines(self.subtitle, "F1", 13, rgb=DIM_RGB)
        if self.cover_lines:
            self.y -= 18
            for line in self.cover_lines:
                self._lines(line, "F1", 11, gap=1)
        self._text(MARGIN, MARGIN + FOOTER + 10, time.strftime("%d.%m.%Y"), "F1", 10, DIM_RGB)
        self._new_page()
        self.y -= 20
        self._text(MARGIN, self.y, self.toc_title, "F2", 20, HEADING_RGB)
        self.y -= 24
        for title, page in self.chapters:
            self.y -= 17
            number = str(page + 2 if self.front else page)
            self._text(MARGIN, self.y, title, "F1", 11.5)
            self._text(self.page_w - MARGIN - self.width(number, "F1", 11.5), self.y, number, "F1", 11.5)
        front, self.pages = self.pages, content
        return front

    def to_bytes(self) -> bytes:
        front = self._front_pages() if self.front else []
        pages = front + self.pages
        total = len(pages)
        first_footer = len(front) + 1
        objects: list[bytes] = []

        def add(body: bytes) -> int:
            objects.append(body)
            return len(objects)

        if self.ufont is None:
            font_ids = {key: add(b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
                                 % name.encode()) for key, (name, _) in FONTS.items()}
        else:
            for number in range(first_footer, total + 1):  # Fußzeilen-Glyphen vorab erfassen
                self._string(f"{self.title}  |  {self.page_label} {number} / {total}", "F1")
            font_ids = {"U1": self._embed_font(add)}
        image_ids = {}
        for name, img in self.images.items():
            data = zlib.compress(img.rgb, 6)
            image_ids[name] = add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                                  b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n"
                                  % (img.width, img.height, len(data)) + data + b"\nendstream")
        pages_id = len(objects) + 1 + 2 * total  # Platz für Inhalte und Seiten freihalten
        page_ids = []
        fonts = b" ".join(b"/%s %d 0 R" % (k.encode(), v) for k, v in font_ids.items())
        for number, page in enumerate(pages, 1):
            ops = list(page.ops)
            if number >= first_footer and self.footer:
                label = f"{self.title}  |  {self.page_label} {number} / {total}"
                width = self.width(label, "F1", 8.5)
                name, operand = self._string(label, "F1")
                ops.append(b"BT %.3f %.3f %.3f rg /%s 8.5 Tf %.2f %.2f Td " % (*DIM_RGB, name, self.page_w - MARGIN - width,
                                                                             MARGIN * 0.6) + operand + b" Tj ET")
            stream = zlib.compress(b"\n".join(ops), 6)
            content_id = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
            xobjects = b" ".join(b"/%s %d 0 R" % (n.encode(), image_ids[n]) for n in dict.fromkeys(page.images))
            resources = b"<< /Font << %s >>%s >>" % (fonts, b" /XObject << %s >>" % xobjects if xobjects else b"")
            page_ids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R "
                                b"/Resources %s >>" % (pages_id, self.page_w, self.page_h, content_id, resources)))
        assert len(objects) + 1 == pages_id
        add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % i for i in page_ids), total))
        catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
        info = add(b"<< /Title (" + _escape(encode(self.title)) + b") /Producer (MessGraph) >>")

        version = b"1.6" if self.ufont is not None and self.ufont.is_cff else b"1.4"
        out = bytearray(b"%PDF-" + version + b"\n%\xe2\xe3\xcf\xd3\n")
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

    def _embed_font(self, add) -> int:
        """Schrift vollständig einbetten (Type0, Identity-H) mit Breiten und ToUnicode für Textsuche/Kopieren."""
        font = self.ufont
        name = font.ps_name.encode()
        scale = 1000.0 / font.units
        raw = font.sfnt()                                  # .ttc: nur die verwendete Schrift
        data = zlib.compress(raw, 6)
        if font.is_cff:
            file_id = add(b"<< /Subtype /OpenType /Length %d /Filter /FlateDecode >>\nstream\n" % len(data)
                          + data + b"\nendstream")
            file_key, subtype, extra = b"/FontFile3", b"/CIDFontType0", b""
        else:
            file_id = add(b"<< /Length %d /Length1 %d /Filter /FlateDecode >>\nstream\n" % (len(data), len(raw))
                          + data + b"\nendstream")
            file_key, subtype, extra = b"/FontFile2", b"/CIDFontType2", b" /CIDToGIDMap /Identity"
        bbox = b" ".join(b"%d" % round(v * scale) for v in font.bbox)
        descriptor = add(b"<< /Type /FontDescriptor /FontName /%s /Flags 32 /FontBBox [%s] /ItalicAngle 0 "
                         b"/Ascent %d /Descent %d /CapHeight %d /StemV 80 %s %d 0 R >>"
                         % (name, bbox, round(font.ascent * scale), round(font.descent * scale),
                            round(font.cap_height * scale), file_key, file_id))
        widths = b" ".join(b"%d [%d]" % (g, round(font.advance(g))) for g in sorted(self.used))
        cid = add(b"<< /Type /Font /Subtype %s /BaseFont /%s /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
                  b"/Supplement 0 >> /FontDescriptor %d 0 R /DW 1000 /W [%s]%s >>"
                  % (subtype, name, descriptor, widths, extra))
        entries = []
        for gid, ch in sorted(self.used.items()):
            code = ord(ch)
            if code > 0xFFFF:
                code -= 0x10000
                utf16 = b"%04X%04X" % (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF))
            else:
                utf16 = b"%04X" % code
            entries.append(b"<%04X> <%s>" % (gid, utf16))
        chunks = [b"%d beginbfchar\n" % len(entries[i:i + 100]) + b"\n".join(entries[i:i + 100]) + b"\nendbfchar"
                  for i in range(0, len(entries), 100)]
        cmap = (b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry (Adobe) "
                b"/Ordering (UCS) /Supplement 0 >> def\n/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
                b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n" + b"\n".join(chunks)
                + b"\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend")
        to_unicode = add(b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream")
        return add(b"<< /Type /Font /Subtype /Type0 /BaseFont /%s /Encoding /Identity-H /DescendantFonts [%d 0 R] "
                   b"/ToUnicode %d 0 R >>" % (name, cid, to_unicode))

    def save(self, path: str) -> None:
        with open(path, "wb") as fh:
            fh.write(self.to_bytes())
