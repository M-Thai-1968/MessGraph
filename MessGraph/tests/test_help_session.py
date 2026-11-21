"""Ansicht speichern/laden, Hilfe-Bilder, PDF und Screenshot-Ablauf."""
import json
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_gui_logic import by_kind, check, env, wait  # noqa: E402,F401  (Fixture wiederverwenden)


@pytest.fixture
def dirs(env, monkeypatch, tmp_path):
    images = tmp_path / "bilder"
    monkeypatch.setattr(env.gui, "HELP_IMAGES", images)
    monkeypatch.setattr(env.gui, "LAST_SESSION", tmp_path / "letzte.mgraph")
    return types.SimpleNamespace(images=images, tmp=tmp_path)


def test_session_roundtrip_with_titles_colors_options(env, dirs):
    app = env.app
    app.open_files([env.a, env.b])
    wait(app)
    chans = {c.name: c for d in app.datasets for c in d.channels}
    env.state.items[app.matrix_input]["value"] = "1*3"
    app._on_matrix()
    check(env, chans["U"])
    app._on_drop(app.slot_ui[0].plot, chans["p"])
    app.layout.slots[0].title = "Spannung"
    app.layout.slots[0].colors[chans["p"]] = (1, 2, 3)
    app._layout_changed()
    app._on_cross_toggle(None, True)
    app.layout.slots[0].cross = [10.0, 20.0]
    app.left_width, app.table_h = 420, 150
    path = dirs.tmp / "sub" / "ansicht"
    (dirs.tmp / "sub").mkdir()
    app.save_session(str(path))
    saved = Path(str(path) + ".mgraph")
    data = json.loads(saved.read_text())
    assert data["matrix"] == [1, 3] and data["graphs"][0]["title"] == "Spannung"
    assert data["graphs"][0]["signals"][1] == {"file": env.b, "name": "p", "color": [1, 2, 3], "axis": "left",
                                                 "limits": [None, None], "target": None}
    assert data["options"]["cross_on"] is True and data["options"]["left_width"] == 420
    assert data["files"][0]["relpath"].startswith("..")

    app._on_clear_signals()
    app.load_session(str(saved))
    wait(app)
    assert sorted(d.name for d in app.datasets) == ["a.csv", "b.csv"]
    slot = app.layout.slots[0]
    assert app.layout.matrix == (1, 3) and len(app.layout.slots) == 3
    assert slot.title == "Spannung" and [c.name for c in slot.signals] == ["U", "p"]
    assert slot.colors[slot.signals[1]] == (1, 2, 3) and slot.cross == [10.0, 20.0]
    assert app.cross_on and env.state.items[app.cross_box]["value"] is True
    assert env.state.items[app.left_panel]["width"] == 420 and env.state.items[app.matrix_input]["value"] == "1*3"
    assert env.state.items[app.slot_ui[0].plot]["label"] == "Spannung"
    assert "Ansicht geladen." in env.state.items[app.status]["value"]


def test_session_relative_paths_and_missing(env, dirs):
    app = env.app
    folder = dirs.tmp / "paket"
    folder.mkdir()
    data_file = folder / "m.csv"
    data_file.write_text("t,v\n0,1\n1,2\n")
    app.open_files([str(data_file)])
    wait(app)
    check(env, app.datasets[0].channels[0])
    app.save_session(str(folder / "a.mgraph"))
    moved = dirs.tmp / "kopie"
    folder.rename(moved)                                         # Ordner weitergegeben
    app.load_session(str(moved / "a.mgraph"))
    wait(app)
    assert app.datasets[0].path == str(moved / "m.csv") and app.layout.signals()

    text = (moved / "a.mgraph").read_text().replace('"name": "v"', '"name": "gibt_es_nicht"')
    (moved / "b.mgraph").write_text(text)
    app.load_session(str(moved / "b.mgraph"))
    wait(app)
    assert "1 Signale nicht gefunden" in env.state.items[app.status]["value"]

    (moved / "kaputt.mgraph").write_text("{kein json")
    app.load_session(str(moved / "kaputt.mgraph"))
    assert "keine gültige JSON" in env.state.items[app.status]["value"]
    (moved / "fremd.mgraph").write_text('{"format": "anders"}')
    app.load_session(str(moved / "fremd.mgraph"))
    assert "keine gespeicherte MessGraph-Ansicht" in env.state.items[app.status]["value"]


def test_last_view_restored_on_start(env, dirs):
    app = env.app
    app._on_restore_last(None, True)
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[1])
    app.shutdown()
    assert env.gui.LAST_SESSION.exists()
    app2 = env.gui.App()
    app2.build()
    app2.load_session(str(env.gui.LAST_SESSION))
    wait(app2)
    assert [c.name for c in app2.layout.signals()] == ["I"]
    app2.pool.shutdown(wait=True)


def test_save_dialog_validation(env, dirs):
    app = env.app
    got = []
    app._ask_save_path("T", "P", str(dirs.tmp / "x.mgraph"), got.append)
    assert env.state.items["save_dialog"]["show"] is True
    env.state.items[app.save_path]["value"] = str(dirs.tmp / "fehlt" / "x.mgraph")
    app._save_dialog_ok()
    assert not got and "Ordner nicht gefunden" in env.state.items[app.save_note]["value"]
    env.state.items[app.save_path]["value"] = "   "
    app._save_dialog_ok()
    assert not got and "Dateinamen" in env.state.items[app.save_note]["value"]
    env.state.items[app.save_path]["value"] = str(dirs.tmp / "ok.mgraph")
    app._save_dialog_ok()
    assert got == [str(dirs.tmp / "ok.mgraph")] and env.state.items["save_dialog"]["show"] is False


def test_help_pdf_without_and_with_images(env, dirs):
    app = env.app
    pdf = dirs.tmp / "hilfe"
    app.save_help_pdf(str(pdf))
    out = Path(str(pdf) + ".pdf")
    assert out.exists() and "25 Bilder sind nachgezeichnet" in env.state.items[app.status]["value"]
    subprocess.run(["qpdf", "--check", str(out)], check=True, capture_output=True)
    text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    assert "MessGraph - Handbuch" in text and "Kontextmenü im Graphen" in text
    assert "Bild 1: Hauptfenster (nachgezeichnet)" in text and "Statuszeile: Ergebnis der letzten Aktion" in text
    images = subprocess.run(["pdfimages", "-list", str(out)], capture_output=True, text=True)
    if images.returncode == 0:
        rows = [line for line in images.stdout.splitlines()[2:] if line.strip()]
        assert len(rows) == 25

    dirs.images.mkdir()                                              # eigene Aufnahme hat Vorrang
    from PIL import Image
    Image.new("RGB", (40, 30), (200, 10, 10)).save(dirs.images / "uebersicht.png")
    app._on_help_language(None, "English")
    assert len(by_kind(env.state, "add_image")) == 25
    captions = [t["value"] for t in by_kind(env.state, "add_text") if str(t.get("value", "")).startswith("Figure")]
    assert "Figure 1: main window" in captions and "Figure 2: file browser (illustration)" in captions
    app.save_help_pdf(str(dirs.tmp / "manual.pdf"))
    text = subprocess.run(["pdftotext", str(dirs.tmp / "manual.pdf"), "-"], capture_output=True, text=True).stdout
    assert "MessGraph - Manual" in text and "Figure 1: main window\n" in text and "Graph context menu" in text
    assert "24 images are illustrations" in env.state.items[app.status]["value"]   # Oberfläche jetzt englisch


@pytest.mark.parametrize("font", ["/usr/share/fonts/opentype/tlwg/Loma.otf",
                                  "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"])
def test_thai_help_display_and_pdf(env, dirs, monkeypatch, font):
    if not Path(font).exists():
        pytest.skip("Schrift fehlt")
    import messgraph.help_pdf as help_pdf
    monkeypatch.setattr(help_pdf, "find_thai_font", lambda: font)
    app = env.app
    app.thai_font = "thai-font"
    app._on_help_language(None, "Thai")
    assert list(app.help_groups)[0] == "ภาพรวม"
    assert env.state.items[app.help_content]["font"] == "thai-font"
    out = dirs.tmp / "th.pdf"
    app.save_help_pdf(str(out))
    subprocess.run(["qpdf", "--check", str(out)], check=True, capture_output=True)
    text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    assert "คู่มือการใช้งาน" in text and "สารบัญ" in text and "ภาพที่ 9: เมนูหลังคลิกขวาที่กราฟ (ภาพจำลอง)" in text
    fonts = subprocess.run(["pdffonts", str(out)], capture_output=True, text=True).stdout
    assert "yes" in fonts.splitlines()[-1]                           # eingebettet
    app._on_help_language(None, "Deutsch")
    assert env.state.items[app.help_content]["font"] != "thai-font"


def test_thai_without_font(env, dirs, monkeypatch):
    import messgraph.help_pdf as help_pdf
    monkeypatch.setattr(help_pdf, "find_thai_font", lambda: None)
    app = env.app
    app.thai_font = None
    app.set_language("Thai")                                         # ohne Schrift abgelehnt
    assert app.lang == "Deutsch" and "Thai ist nicht verfügbar" in env.state.items[app.status]["value"]
    app.help_lang = "Thai"                                            # PDF direkt angefordert
    app.save_help_pdf(str(dirs.tmp / "th.pdf"))
    assert "PDF nicht erstellt" in env.state.items[app.status]["value"] and not (dirs.tmp / "th.pdf").exists()


def test_screenshot_run_creates_images_and_restores_view(env, dirs, monkeypatch):
    import shutil
    demo = dirs.tmp / "demo"
    demo.mkdir()
    for name in ("demo_einfach.csv", "demo_deutsch_vorspann.csv", "demo_zeitstempel.csv", "demo_lauf_1.csv",
                 "demo_lauf_2.csv", "demo_lauf_3.csv", "demo_pruefstand.asc"):
        shutil.copy(Path(__file__).parent.parent / "demo_data" / name, demo / name)
    monkeypatch.setattr(env.gui, "DEMO_DIR", demo)
    app = env.app
    app.open_files([env.b])
    wait(app)
    check(env, app.datasets[0].channels[0])
    before = app.session_dict()
    app.start_screenshots()
    end = time.time() + 20
    while app.shots and time.time() < end:
        app.tick()
        time.sleep(0.002)
    assert app.shots is None
    wait(app)
    names = sorted(p.stem for p in dirs.images.glob("*.png"))
    assert names == sorted(["uebersicht", "dateiliste", "allefiles", "ascii", "browser", "matrix", "zeilen", "vorschlag", "kontextmenue", "crosslines",
                            "datumsachse", "ansicht", "berechnen", "vergleich", "drucken", "hilfe"])
    assert app.cmp_result is None and not any(d.extra.get("shot_demo") for d in app.datasets)
    circles = [d for d in env.state.drawn if d[0] == "circle"]
    texts = [d[1] for d in env.state.drawn if d[0] == "text"]
    assert len(circles) >= 25 and {"1", "2", "3", "4", "5", "6"} <= set(texts)        # Markierungen gezeichnet
    assert all(not env.state.items.get(d[2]) for d in env.state.drawn if d[2] not in (app.rows_preview, app.arr_preview))   # und wieder entfernt
    assert "datenbasen" in env.state.items[app.status]["value"]           # ohne demo.mf4 übersprungen
    assert [d.name for d in app.datasets] == ["b.csv"]                    # vorherige Ansicht zurück
    assert app.session_dict()["graphs"] == before["graphs"] and not app.date_axis
    assert env.state.items["help_window"]["show"] is True                # Hilfe-Fenster offen
    assert len(by_kind(env.state, "add_image")) >= 5


def test_screenshots_need_demo_data(env, dirs, monkeypatch):
    monkeypatch.setattr(env.gui, "DEMO_DIR", dirs.tmp / "leer")
    env.app.start_screenshots()
    assert env.app.shots is None and "Beispieldaten fehlen" in env.state.items[env.app.status]["value"]


def test_chinese_language_switch_and_help(env, dirs):
    from messgraph import fonts
    path = fonts.find_cjk_font()
    if not path:
        pytest.skip("keine CJK-Schrift")
    app = env.app
    app.cjk_font, app.cjk_font_path = "cjk-font", path
    app.set_language("Chinese")
    assert app.lang == "Chinese"
    app._on_help_language(None, "Chinese")
    assert list(app.help_groups)[0] == "概览"
    assert env.state.items[app.help_content]["font"] == "cjk-font"
    out = dirs.tmp / "zh.pdf"
    app.save_help_pdf(str(out))
    assert out.exists()
    text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    assert "图 14：自动评估窗口" in text
    app.set_language("Deutsch")
    assert app.lang == "Deutsch"


def test_chinese_without_font(env):
    app = env.app
    app.cjk_font = None
    app.set_language("Chinese")
    assert app.lang == "Deutsch" and "Chinesisch ist nicht verfügbar" in env.state.items[app.status]["value"]


def test_rebuild_tags_cover_all_fixed_tags():
    import re
    source = (Path(__file__).parent.parent / "messgraph" / "gui.py").read_text(encoding="utf-8")
    tags = set(re.findall(r'tag="([A-Za-z0-9_]+)"', source))
    from messgraph.gui import App
    assert tags <= set(App.REBUILD_TAGS), tags - set(App.REBUILD_TAGS)


def test_language_switch_all_languages_rebuilds_without_alias_clash(env):
    app = env.app
    app.cjk_font, app.cjk_font_path = "cjk-font", "/x.ttc"
    app.thai_font = app.thai_font or "thai-font"
    for language in ["Chinese", "English", "Thai", "Deutsch", "Chinese", "Deutsch"]:
        app.set_language(language)
        assert app.lang == language
        assert "lim_xfer_popup" in env.state.items and "dir_window" in env.state.items


def test_help_pdf_with_broken_screenshot_uses_bundled_image(env, dirs, monkeypatch):
    dirs.images.mkdir()
    (dirs.images / "uebersicht.png").write_bytes(b"")                   # abgebrochene Aufnahme
    (dirs.images / "matrix.png").write_bytes(b"\x89PNG\r\n\x1a\n kaputt")
    app = env.app
    w, h, rgb, drawn = app._load_help_image("uebersicht")
    assert w > 0 and h > 0 and len(rgb) == w * h * 3 and drawn is True
    import PIL
    monkeypatch.setattr(PIL, "Image", None, raising=False)             # ohne Pillow: dpg.load_image mit Prüfung
    import sys
    monkeypatch.setitem(sys.modules, "PIL.Image", None)
    monkeypatch.setattr(env.gui.dpg, "load_image", lambda path: (-1, 5, 4, []), raising=False)
    assert app._load_help_image("uebersicht") is None                  # negative Maße: kein Absturz
    monkeypatch.undo()
    monkeypatch.setattr(env.gui, "HELP_IMAGES", dirs.images)
    app.help_lang = "Deutsch"
    out = dirs.tmp / "hilfe.pdf"
    app.save_help_pdf(str(out))
    assert out.exists() and "PDF nicht erstellt" not in env.state.items[app.status]["value"]
