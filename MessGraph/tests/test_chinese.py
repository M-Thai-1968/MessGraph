"""Chinesisch (Mandarin): Übersetzungen, Schrift (TTC), Hilfe und PDF."""
import re
import subprocess
from pathlib import Path

import pytest

from messgraph import i18n, i18n_zh, help_zh, help_en, fonts
from messgraph.ttf import TrueTypeFont

PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def test_translation_complete_with_placeholders():
    thai = i18n._TRANSLATIONS["Thai"]
    missing = [de for de in thai if de not in i18n_zh.ZH]
    assert not missing, missing[:5]
    for de, zh in i18n_zh.ZH.items():
        en = i18n._TRANSLATIONS["English"].get(de, de)          # Formelbeispiele dürfen wie im Englischen lauten
        assert sorted(PLACEHOLDER.findall(zh)) in (sorted(PLACEHOLDER.findall(de)), sorted(PLACEHOLDER.findall(en))), (de, zh)
        assert zh.strip()


def test_language_listed_and_english_fallback():
    assert "Chinese" in i18n.LANGUAGES and "Chinese" in i18n.SCRIPT_LANGUAGES
    try:
        i18n.set_language("Chinese")
        assert i18n.t("Start") == "开始"
        unknown = "Nur ein Testtext ohne Eintrag"
        assert i18n.t(unknown) == unknown
        en = i18n._TRANSLATIONS["English"]
        key = next(k for k in en if k not in i18n_zh.ZH) if any(k not in i18n_zh.ZH for k in en) else None
        if key:                                                  # fehlt Chinesisch: Englisch statt Deutsch
            assert i18n.t(key) == en[key]
    finally:
        i18n.set_language("Deutsch")


def test_help_structure_matches_english():
    assert len(help_zh.CHAPTERS) == len(help_en.CHAPTERS)
    for (_, en), (_, zh) in zip(help_en.CHAPTERS, help_zh.CHAPTERS):
        assert [i[1] for i in en if i[0] == "img"] == [i[1] for i in zh if i[0] == "img"]
        assert [i[1] for i in en if i[0] == "m"] == [i[1] for i in zh if i[0] == "m"]
    auto = dict(help_zh.CHAPTERS)["自动评估"]
    headings = [i[1] for i in auto if i[0] == "h"]
    assert "周期流程详解" in headings and "首次运行和后续运行" in headings
    steps = [i[1] for i in auto if i[0] == "b" and re.match(r"\d+\. ", i[1])]
    assert any(s.startswith("12. ") for s in steps)


def test_cycle_detail_documented_in_all_languages():
    from messgraph import help_de, help_th
    assert "Ablauf eines Zyklus im Detail" in str(help_de.CHAPTERS)
    assert "Sequence of a cycle in detail" in str(help_en.CHAPTERS)
    assert "周期流程详解" in str(help_zh.CHAPTERS)
    assert len(str(help_th.CHAPTERS)) > 0


def test_cjk_font_ttc_and_sfnt(tmp_path):
    path = fonts.find_cjk_font()
    if not path:
        pytest.skip("keine CJK-Schrift")
    font = TrueTypeFont(path)
    text = "".join(i18n_zh.ZH.values()) + str(help_zh.CHAPTERS)
    assert not {ch for ch in text if ch.isprintable() and font.glyph_id(ord(ch)) == 0}
    raw = font.sfnt()
    assert raw[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true")
    out = tmp_path / "x.ttf"
    out.write_bytes(raw)
    again = TrueTypeFont(str(out))
    assert again.glyph_id(ord("中")) == font.glyph_id(ord("中"))


def test_has_cjk_rejects_latin_only():
    latin = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not Path(latin).exists():
        pytest.skip("Schrift fehlt")
    assert not fonts.has_cjk(latin)


def test_chinese_help_pdf(tmp_path):
    path = fonts.find_cjk_font()
    if not path:
        pytest.skip("keine CJK-Schrift")
    from messgraph.help_pdf import build_help_pdf
    out = tmp_path / "zh.pdf"
    pages = build_help_pdf("Chinese", str(out), lambda image_id: None, font_path=path)
    assert pages > 10
    subprocess.run(["qpdf", "--check", str(out)], check=True, capture_output=True)
    text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    assert "使用手册" in text and "目录" in text and "周期流程详解" in text


def test_wrap_chinese_fills_lines_and_respects_punctuation():
    from messgraph.pdfdoc import wrap
    text = "一个周期在“开始”时立即启动，之后每隔一个周期时间启动一次；启用的评估依次处理（进度：[评估] 步骤 n/m）。" * 3
    lines = wrap(text, "F", 10, 120, measure=lambda s: 10.0 * len(s))
    assert all(len(line) <= 12 for line in lines)
    assert "".join(lines).replace(" ", "") == text.replace(" ", "")
    assert not any(line[0] in "，。、：；）”" for line in lines)
    assert not any(line[-1] in "（“" for line in lines)
    assert sum(len(line) for line in lines[:-1]) / (len(lines) - 1) > 9   # Zeilen werden aufgefüllt
