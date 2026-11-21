"""Hilfe als PDF-Handbuch."""
from __future__ import annotations

from typing import Callable

from . import __version__, help_content
from .data_model import LoadError
from .fonts import find_cjk_font, find_thai_font
from .pdfdoc import PdfDocument


def build_help_pdf(language: str, path: str, load_image: Callable[[str], tuple | None],
                   font_path: str | None = None) -> int:
    """Schreibt das Handbuch. load_image(Bild-ID) -> (Breite, Höhe, RGB-Bytes, nachgezeichnet) oder None.

    Für Sprachen außerhalb von Windows-1252 (Thai) wird eine Schrift eingebettet. Liefert die Seitenzahl.
    """
    mod = help_content.module(language)
    ui = help_content.ui(language)
    if language in help_content.NEEDS_UNICODE_FONT:
        font_path = font_path or (find_cjk_font() if language == "Chinese" else find_thai_font())
        if not font_path:
            raise LoadError(ui["no_font"])
    doc = PdfDocument(mod.TITLE, f"{mod.SUBTITLE}  -  Version {__version__}", ui["contents"], ui["page"],
                      font_path=font_path if language in help_content.NEEDS_UNICODE_FONT else None)
    for title, content in mod.CHAPTERS:
        doc.chapter(title)
        for item in content:
            kind = item[0]
            if kind == "h":
                doc.heading(item[1])
            elif kind == "b":
                doc.bullet(item[1])
            elif kind == "m":
                doc.marker(item[1], item[2])
            elif kind == "img":
                image = load_image(item[1])
                if image is not None:
                    width, height, rgb, illustration = image
                    doc.image(width, height, rgb, caption=item[2] + (ui["illustration"] if illustration else ""))
                else:
                    doc.note(f"[{item[2]}] {ui['missing']}")
            else:
                doc.paragraph(item[1])
    data = doc.to_bytes()
    with open(path, "wb") as fh:
        fh.write(data)
    return data.count(b"/Type /Page ")
