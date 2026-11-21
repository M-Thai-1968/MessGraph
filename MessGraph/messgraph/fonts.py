"""Schriftdateien finden: Oberfläche (lateinisch), Thai und Chinesisch (Oberfläche, Hilfe und PDF)."""
from __future__ import annotations

import glob
import os

THAI_CANDIDATES = [
    r"C:\Windows\Fonts\LeelawUI.ttf", r"C:\Windows\Fonts\leelawad.ttf", r"C:\Windows\Fonts\tahoma.ttf",
    "/usr/share/fonts/truetype/tlwg/Loma.ttf", "/usr/share/fonts/truetype/tlwg/Garuda.ttf",
    "/usr/share/fonts/opentype/tlwg/Loma.otf", "/usr/share/fonts/opentype/tlwg/Garuda.otf",
    "/usr/share/fonts/truetype/tlwg/Waree.ttf", "/usr/share/fonts/opentype/tlwg/Waree.otf",
    "/usr/share/fonts/truetype/tlwg/Sawasdee.ttf", "/usr/share/fonts/opentype/tlwg/Sawasdee.otf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/gnu-free/FreeSans.ttf", "/usr/share/fonts/gnu-free/FreeSans.otf",
    "/usr/share/fonts/truetype/noto/NotoSansThaiUI-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/noto/NotoSansThai-Regular.ttf", "/usr/share/fonts/google-noto/NotoSansThai-Regular.ttf",
    "/Library/Fonts/Thonburi.ttf", "/System/Library/Fonts/Supplemental/Ayuthaya.ttf",
]
# weitere Fundorte unter Linux (Reihenfolge: TLWG, FreeFont, alles mit "Thai" im Namen)
THAI_GLOBS = ["/usr/share/fonts/**/tlwg/*.[ot]tf", "/usr/share/fonts/**/freefont/*.[ot]tf",
              "/usr/share/fonts/**/*Thai*.[ot]tf", os.path.expanduser("~/.local/share/fonts/**/*.[ot]tf"),
              os.path.expanduser("~/.fonts/**/*.[ot]tf")]

# Zeichen, die außer Thai vorhanden sein müssen: In Thai wechseln nur die Bedienungstexte, Datei- und
# Signalnamen, Einheiten und Zahlen bleiben lateinisch und müssen mit derselben Schrift lesbar sein.
LATIN_REQUIRED = [chr(c) for c in range(0x20, 0x7F)] + list("°µäöüÄÖÜß")


def find_thai_font(extra: list[str] | None = None) -> str | None:
    """Erste vorhandene Schrift mit Thai- UND lateinischen Zeichen (TrueType oder OpenType, keine .ttc).

    Reine Thai-Schriften (z. B. Noto Sans Thai) werden übergangen: Dear PyGui kann keine zweite Schrift für
    fehlende Zeichen einblenden, Datei- und Signalnamen würden sonst leer angezeigt."""
    seen = set()
    candidates = (extra or []) + THAI_CANDIDATES
    for pattern in THAI_GLOBS:
        candidates += sorted(glob.glob(pattern, recursive=True))
    for path in candidates:
        if not path or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        if has_thai(path) and has_latin(path):
            return path
    return None


def _font(path: str):
    from .ttf import TrueTypeFont
    return TrueTypeFont(path)


def has_thai(path: str) -> bool:
    try:
        return _font(path).glyph_id(ord("\u0e01")) != 0
    except Exception:
        return False


def has_latin(path: str) -> bool:
    """Alle druckbaren ASCII-Zeichen und die üblichen Zeichen für Einheiten und Umlaute vorhanden."""
    try:
        font = _font(path)
        return all(font.glyph_id(ord(ch)) != 0 for ch in LATIN_REQUIRED)
    except Exception:
        return False



# Chinesisch (vereinfacht): Schriften mit chinesischen UND lateinischen Zeichen; .ttc wird unterstützt (erste Schrift)
CJK_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf", r"C:\Windows\Fonts\Deng.ttf",
    r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\msyhl.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/arphic/uming.ttc", "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc", "/Library/Fonts/Arial Unicode.ttf",
]
CJK_GLOBS = ["/usr/share/fonts/**/*CJK*Regular*.[ot]t[fc]", "/usr/share/fonts/**/wqy*.tt[fc]",
             "/usr/share/fonts/**/*[Hh]ei*.tt[fc]", os.path.expanduser("~/.local/share/fonts/**/*.[ot]t[fc]")]
CJK_SAMPLE = "中文设置帮助"


def has_cjk(path: str) -> bool:
    try:
        font = _font(path)
        return all(font.glyph_id(ord(ch)) != 0 for ch in CJK_SAMPLE)
    except Exception:
        return False


def find_cjk_font(extra: list[str] | None = None) -> str | None:
    """Erste vorhandene Schrift mit chinesischen (vereinfacht) UND lateinischen Zeichen."""
    seen = set()
    candidates = (extra or []) + CJK_CANDIDATES
    for pattern in CJK_GLOBS:
        candidates += sorted(glob.glob(pattern, recursive=True))
    for path in candidates:
        if not path or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        if has_cjk(path) and has_latin(path):
            return path
    return None
