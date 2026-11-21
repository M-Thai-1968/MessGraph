"""Hilfe in mehreren Sprachen. Neue Sprache: Modul help_xx.py mit TITLE, SUBTITLE, CHAPTERS anlegen
und hier in LANGUAGES und UI_TEXT eintragen."""
from pathlib import Path

from . import help_de, help_en, help_th, help_zh

LANGUAGES = {"Deutsch": help_de, "English": help_en, "Thai": help_th, "Chinese": help_zh}
DEFAULT_LANGUAGE = "Deutsch"
NEEDS_UNICODE_FONT = {"Thai", "Chinese"}           # Sprachen außerhalb von Latin-1: eigene Schrift in Anzeige und PDF
BUNDLED_IMAGES = Path(__file__).resolve().parent / "help_images"
UI_TEXT = {
    "Deutsch": {"contents": "Inhalt", "page": "Seite", "language": "Sprache", "illustration": " (nachgezeichnet)",
                "missing": "Bild nicht vorhanden: \"Screenshots erzeugen\" klicken (Fenster Hilfe, Menü Hilfe > Hilfe anzeigen).",
                "no_font": "Keine Schrift mit thailändischen Zeichen gefunden."},
    "English": {"contents": "Contents", "page": "Page", "language": "Language", "illustration": " (illustration)",
                "missing": "Image not available: click \"Screenshots erzeugen\" (help window, menu Hilfe > Hilfe anzeigen).",
                "no_font": "No font with Thai characters found."},
    "Thai": {"contents": "สารบัญ", "page": "หน้า", "language": "Sprache / ภาษา", "illustration": " (ภาพจำลอง)",
             "missing": "ไม่มีภาพ: คลิก \"Screenshots erzeugen\" (หน้าต่างช่วยเหลือ เมนู Hilfe > Hilfe anzeigen)",
             "no_font": "Keine Schrift mit thailändischen und lateinischen Zeichen gefunden (z. B. Leelawadee UI, Tahoma, fonts-tlwg)."},
    "Chinese": {"contents": "目录", "page": "页", "language": "Sprache / 语言", "illustration": "（示意图）",
                "missing": "图片不存在：点击 \"Screenshots erzeugen\"（帮助窗口，菜单 Hilfe > Hilfe anzeigen）",
                "no_font": "Keine Schrift mit chinesischen und lateinischen Zeichen gefunden (z. B. Microsoft YaHei, fonts-wqy-microhei)."},
}

CHAPTERS = help_de.CHAPTERS  # rückwärtskompatibel


def module(language: str):
    return LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])


def chapters(language: str):
    return module(language).CHAPTERS


def ui(language: str) -> dict:
    return UI_TEXT.get(language, UI_TEXT[DEFAULT_LANGUAGE])


def image_ids() -> list[str]:
    ids = []
    for mod in LANGUAGES.values():
        for _, content in mod.CHAPTERS:
            ids += [item[1] for item in content if item[0] == "img" and item[1] not in ids]
    return ids


def image_path(image_id: str, captured_dir: Path) -> tuple[Path | None, bool]:
    """(Pfad, nachgezeichnet?): eigene Aufnahme hat Vorrang vor der mitgelieferten Abbildung."""
    captured = captured_dir / f"{image_id}.png"
    if captured.exists():
        return captured, False
    bundled = BUNDLED_IMAGES / f"{image_id}.png"
    if bundled.exists():
        return bundled, True
    return None, False
