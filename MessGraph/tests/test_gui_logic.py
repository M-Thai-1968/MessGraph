"""Programmlogik der Oberfläche gegen die Nachbildung von Dear PyGui."""
import json
import os
import sys
import time
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import fake_dearpygui  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    state = fake_dearpygui.install()
    import messgraph
    for name in ("gui", "themes"):  # neu importieren, damit die frische Nachbildung gilt
        sys.modules.pop(f"messgraph.{name}", None)
        if hasattr(messgraph, name):
            delattr(messgraph, name)
    import messgraph.gui as gui
    monkeypatch.setattr(gui, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(gui, "LOG_FILE", tmp_path / "fehler.log")   # nicht ins echte Home schreiben
    monkeypatch.setattr(gui, "LAST_SESSION", tmp_path / "letzte.mgraph")
    app = gui.App()
    app.build()
    a = tmp_path / "a.csv"
    a.write_text("time [s];U [V];I [A]\n" + "".join(f"{i};{i * 2};{100 - i}\n" for i in range(101)))
    b = tmp_path / "b.csv"
    b.write_text("t,p\n" + "".join(f"{i * 2},{i}\n" for i in range(11)))
    yield types.SimpleNamespace(app=app, state=state, a=str(a), b=str(b), gui=gui, tmp=tmp_path)
    app.pool.shutdown(wait=True)


def wait(app):
    end = time.time() + 5
    while time.time() < end:
        app.tick()
        if app.pending == 0 and app.results.empty() and not app.loading:
            return
        time.sleep(0.01)
    raise AssertionError("Zeitüberschreitung")


def by_kind(state, kind):
    return [i for i in state.items.values() if i["kind"] == kind]


def check(env, channel):
    env.app._on_channel(None, True, channel)
    wait(env.app)


def texts_of_table(env):
    return [[env.state.items[c]["value"] for c in cells] for _, _, cells in env.app.table_rows]


def browser_files(env):
    return {Path(p).name: box for p, box in env.app.fb_boxes.items()}


def test_file_browser_lists_parquet_mf4_any_case_and_multi_select(env):
    data = env.tmp / "daten"
    sub = data / "Unterordner"
    sub.mkdir(parents=True)
    for name in ["m.PARQUET", "x.parquet", "y.MF4", "z.mf4", "notiz.txt", ".versteckt.csv"]:
        (sub / name).write_bytes(b"0")
    import shutil
    shutil.copy(env.a, sub / "a.csv")
    env.app._show_file_browser()
    assert env.state.items["file_browser"]["show"] is True
    env.app._fb_go(str(data))
    folders = [i for i in by_kind(env.state, "add_selectable") if i.get("user_data") == str(sub)]
    assert folders and folders[0]["label"].endswith("Unterordner")
    env.app._fb_dir_clicked(None, None, str(sub))
    assert sorted(browser_files(env)) == ["a.csv", "m.PARQUET", "notiz.txt", "x.parquet", "y.MF4", "z.mf4"]
    env.state.items[env.app.fb_filter]["value"] = "Parquet (*.parquet)"
    env.app._fb_refresh()
    assert sorted(browser_files(env)) == ["m.PARQUET", "x.parquet"]
    env.app._fb_select_all(True)
    env.state.items[env.app.fb_filter]["value"] = "Messdaten (mf4, mdf, blf, csv, asc, txt, dat, parquet)"
    env.state.items[env.app.fb_name]["value"] = "a."
    env.app._fb_refresh()
    assert list(browser_files(env)) == ["a.csv"]
    env.app._fb_file_toggled(None, True, str(sub / "a.csv"))
    env.app._fb_file_toggled(None, False, str(sub / "x.parquet"))
    assert "2 Datei(en)" in env.state.items[env.app.fb_count]["value"]
    env.app._fb_up()
    assert env.app.fb_dir == str(data) and "davon 2 aus anderen" in env.state.items[env.app.fb_count]["value"]
    env.app._fb_open()
    assert env.state.items["file_browser"]["show"] is False
    wait(env.app)
    assert [d.name for d in env.app.datasets] == ["a.csv"]       # m.PARQUET ist kein echtes Parquet
    assert "m.PARQUET" in env.state.items[env.app.status]["value"] or env.app.pending == 0
    assert str(data) in (env.tmp / "settings.json").read_text()


def test_file_browser_errors_and_typed_path(env):
    env.app._show_file_browser()
    env.app._fb_open()
    assert "mindestens eine" in env.state.items[env.app.fb_error]["value"]
    env.app._fb_go(str(env.tmp / "gibt_es_nicht"))
    assert "nicht gefunden" in env.state.items[env.app.fb_error]["value"]
    env.app._fb_go(env.a)                     # Dateipfad eingetippt
    assert env.app.fb_dir == str(env.tmp) and env.a in env.app.fb_selected
    assert env.state.items[browser_files(env)["a.csv"]]["value"] is True


def test_open_files_twice_is_ignored(env):
    env.app.open_files([env.a, env.b, env.a])
    wait(env.app)
    assert sorted(d.name for d in env.app.datasets) == ["a.csv", "b.csv"]
    assert len(env.app.checkboxes) == 3
    env.app.open_files([env.a])
    assert len(env.app.datasets) == 2 and env.app.pending == 0


def test_load_error_written_to_log(env, monkeypatch):
    log = env.tmp / "fehler.log"
    monkeypatch.setattr(env.gui, "LOG_FILE", log)
    bad = env.tmp / "kaputt.mf4"
    bad.write_bytes(b"kein mf4")
    env.app.open_files([str(bad)])
    wait(env.app)
    assert "kaputt.mf4" in log.read_text() and str(log) in env.state.items[env.app.status]["value"]


def test_broken_file_reports_error_and_keeps_running(env):
    bad = env.tmp / "x.parquet"
    bad.write_text("kein parquet")
    env.app.open_files([str(bad), env.a])
    wait(env.app)
    assert [d.name for d in env.app.datasets] == ["a.csv"]


def test_default_stacks_vertically(env):
    env.app.open_files([env.a, env.b])
    wait(env.app)
    for c in [c for d in env.app.datasets for c in d.channels]:
        check(env, c)
    sub = by_kind(env.state, "add_subplots")[0]
    assert sub["args"] == (3, 1) and len(by_kind(env.state, "add_plot")) == 3
    assert sub["height"] == -1
    env.state.viewport_h = 500
    env.app.tick()
    assert env.state.items[env.app.subplots]["height"] == 3 * 220


def test_matrix_and_target(env):
    env.app.open_files([env.a])
    wait(env.app)
    u, i = env.app.datasets[0].channels
    env.state.items[env.app.matrix_input]["value"] = "2*3"
    env.app._on_matrix()
    assert by_kind(env.state, "add_subplots")[0]["args"] == (2, 3) and len(by_kind(env.state, "add_plot")) == 6
    check(env, u)
    env.state.items[env.app.target_combo]["value"] = "Graph 1 (Z1/S1)"
    check(env, i)
    assert env.app.layout.slots[0].signals == [u, i]
    env.state.items[env.app.matrix_input]["value"] = "falsch"
    env.app._on_matrix()
    assert env.app.layout.matrix == (2, 3)
    env.state.items[env.app.matrix_input]["value"] = ""
    env.app._on_matrix()
    assert by_kind(env.state, "add_subplots")[0]["args"] == (1, 1)


def test_markers_values_sync_vertical_only(env):
    env.app.open_files([env.a])
    wait(env.app)
    u, i = env.app.datasets[0].channels
    check(env, u)
    check(env, i)
    for ui in env.app.slot_ui:                               # Ansicht = voller Datenbereich
        env.state.axis_limits[ui.x_axis] = [0.0, 100.0]
    env.app.tick()
    env.app._on_cross_toggle(None, True)
    assert env.state.items[env.app.table_area]["show"] is True
    ui0, ui1 = env.app.slot_ui
    assert ui0.slot.cross == pytest.approx([100 / 3, 200 / 3])

    env.state.items[ui0.v_lines[0]]["value"] = 10.0
    env.state.items[ui0.v_lines[1]]["value"] = 60.0
    env.app.tick()
    assert env.state.items[ui1.v_lines[0]]["value"] == 10.0
    rows = texts_of_table(env)
    assert rows[0] == ["10 s", "60 s", "20 V", "120 V", "50 s", "100 V", "2 V/s"]
    assert rows[1] == ["10 s", "60 s", "90 A", "40 A", "50 s", "-50 A", "-1 A/s"]
    lines = by_kind(env.state, "add_drag_line")                  # nur senkrechte Marker M1/M2 (+ M3, aus)
    assert len(lines) == 6 and all(line["vertical"] for line in lines)
    assert [line["label"] for line in lines] == ["M1", "M2", "M3", "M1", "M2", "M3"]
    assert all(line["show"] is False for line in lines if line["label"] == "M3")

    env.app._on_cross_sync(None, False)
    env.state.items[ui1.v_lines[0]]["value"] = 30.0
    env.app.tick()
    assert env.state.items[ui0.v_lines[0]]["value"] == 10.0
    assert texts_of_table(env)[1][0] == "30 s" and texts_of_table(env)[0][0] == "10 s"

    env.state.items[ui0.v_lines[0]]["value"] = 500.0  # außerhalb der Daten
    env.app.tick()
    row = texts_of_table(env)[0]
    assert row[2] == "-" and row[5] == "-" and row[6] == "-"

    env.app._on_cross_toggle(None, False)
    assert env.state.items[ui0.v_lines[0]]["show"] is False


def test_cross_position_survives_rebuild(env):
    env.app.open_files([env.a, env.b])
    wait(env.app)
    chans = {c.name: c for d in env.app.datasets for c in d.channels}
    check(env, chans["U"])
    env.app._on_cross_toggle(None, True)
    env.state.items[env.app.slot_ui[0].v_lines[0]]["value"] = 42.0
    env.app.tick()
    check(env, chans["p"])
    assert [u.slot.cross[0] for u in env.app.slot_ui] == [42.0, 42.0]
    assert env.state.items[env.app.slot_ui[1].v_lines[0]]["value"] == 42.0


def test_empty_graph_in_matrix_with_crosslines(env):
    env.state.items[env.app.matrix_input]["value"] = "2*2"
    env.app._on_matrix()
    env.app._on_cross_toggle(None, True)
    env.app.tick()
    env.app.open_files([env.a])
    wait(env.app)
    check(env, env.app.datasets[0].channels[0])
    env.app.tick()
    assert all(u.slot.cross[0] is not None for u in env.app.slot_ui)


def test_close_dataset_and_uncheck(env):
    env.app.open_files([env.a, env.b])
    wait(env.app)
    d = env.app.datasets[0]
    check(env, d.channels[0])
    env.app._on_channel(None, False, d.channels[0])
    assert env.app.layout.signals() == []
    check(env, d.channels[0])
    env.app._close_dataset(None, None, d)
    assert env.app.layout.signals() == [] and d not in env.app.datasets
    assert len(env.app.checkboxes) == 1


def test_filter_and_clear(env):
    env.app.open_files([env.a])
    wait(env.app)
    env.state.items[env.app.filter_input]["value"] = "[a]"
    env.app._refresh_channel_list()
    assert [c.name for c in env.app.checkboxes] == ["I"]
    check(env, env.app.datasets[0].channels[0])
    env.state.items[env.app.filter_input]["value"] = ""
    env.app._refresh_channel_list()
    assert env.state.items[env.app.checkboxes[env.app.datasets[0].channels[0]]]["value"] is True
    env.app._on_clear_signals()
    assert env.state.items[env.app.checkboxes[env.app.datasets[0].channels[0]]]["value"] is False


def test_theme_switch_persists(env):
    env.app.open_files([env.a])
    wait(env.app)
    check(env, env.app.datasets[0].channels[0])
    before = env.state.items[next(iter(env.app.slot_ui[0].series.values()))]["bound"]
    env.app._on_theme(None, "Hell")
    assert env.state.theme == env.app.global_themes["Hell"]
    assert env.state.items[next(iter(env.app.slot_ui[0].series.values()))]["bound"] != before
    assert "Hell" in (env.tmp / "settings.json").read_text()
    assert env.gui.App().mode == "Hell"


def test_lazy_channel_error_unchecks(env):
    from messgraph.data_model import Channel, Dataset, LoadError

    def boom():
        raise LoadError("keine Zahlenwerte")
    good_x = np.array([0.0, 1.0])
    ok = Channel(name="ok", source="m.mf4", loader=lambda: (good_x, good_x, "V"))
    bad = Channel(name="bad", source="m.mf4", loader=boom)
    env.app.datasets.append(Dataset(path="m.mf4", channels=[ok, bad]))
    env.app._refresh_channel_list()
    env.state.items[env.app.checkboxes[bad]]["value"] = True
    check(env, bad)
    env.app.pool.shutdown(wait=True)
    env.app.tick()
    assert env.state.items[env.app.checkboxes[bad]]["value"] is False and not env.app.layout.signals()


def test_lod_updates_visible_window(env):
    p = env.tmp / "big.csv"
    n = 200_000
    x = np.arange(n, dtype=float)
    np.savetxt(p, np.column_stack([x, np.sin(x / 1000)]), delimiter=",", header="time,s", comments="", fmt="%.6g")
    env.app.open_files([str(p)])
    wait(env.app)
    check(env, env.app.datasets[0].channels[0])
    ui = env.app.slot_ui[0]
    series = next(iter(ui.series.values()))
    assert len(env.state.items[series]["value"][0]) <= 6001
    env.state.axis_limits[ui.x_axis] = [1000.0, 2000.0]
    env.app.last_lod = 0
    env.app.tick()
    xs = env.state.items[series]["value"][0]
    arr = np.array(xs)
    assert np.all(np.diff(arr) >= 0)
    assert arr[0] == 0 and arr[-1] == n - 1  # "Alles anzeigen" erreicht weiter alle Daten
    assert ((arr >= 1000) & (arr <= 2000)).sum() == 1001  # sichtbarer Bereich ungekürzt
    assert arr.size < 3000


def test_help_languages_chapters_and_run_loop(env):
    from messgraph import help_content
    def allowed(ch, language):
        o = ord(ch)
        if o <= 0xFF:
            return True
        if language == "Thai":
            return 0x0E00 <= o <= 0x0E7F
        if language == "Chinese":                                   # CJK, Satzzeichen, Vollbreite, Anführung, Gedankenstrich
            return 0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF or o in (0x201C, 0x201D, 0x2014)
        return False

    images = {}
    for language in help_content.LANGUAGES:
        images[language] = []
        for title, content in help_content.chapters(language):
            assert all(allowed(ch, language) for ch in title)
            for item in content:
                assert item[0] in ("h", "p", "b", "img", "m")
                for text in item[1:]:
                    assert all(allowed(ch, language) for ch in text), (language, text)
                if item[0] == "img":
                    images[language].append(item[1])
    assert len({len(help_content.chapters(lang)) for lang in help_content.LANGUAGES}) == 1
    assert images["Deutsch"] == images["English"] == images["Thai"] == images["Chinese"] and len(images["Deutsch"]) == 25
    for image_id in images["Deutsch"]:                         # mitgelieferte Abbildungen vorhanden
        assert (help_content.BUNDLED_IMAGES / f"{image_id}.png").exists()
    names = list(env.app.help_groups)
    env.app._on_help_chapter(None, names[2])
    assert env.state.items[env.app.help_groups[names[2]]]["show"] is True
    assert env.state.items[env.app.help_groups[names[0]]]["show"] is False
    env.app._on_help_language(None, "English")
    assert list(env.app.help_groups)[0] == "Overview" and env.app.help_index == 2
    assert env.state.items[env.app.help_groups["Opening files"]]["show"] is True
    assert '"language": "English"' in (env.tmp / "settings.json").read_text()
    app = env.gui.App([env.a])
    assert app.help_lang == "English"
    app.run()


def test_gui_strings_latin1():
    root = Path(__file__).parent.parent / "messgraph"
    for f in ["gui.py", "layout.py", "csv_reader.py", "tabular.py", "loaders.py", "measure.py"]:
        src = (root / f).read_text(encoding="utf-8")
        allowed_extra = {"Ω", "µ", "²"}
        bad = {ch for ch in src if ord(ch) > 255 and ch not in allowed_extra}
        assert not bad, f"{f}: {bad}"


def menu_entries(env, kind="add_selectable"):
    return [(i["label"], i.get("user_data")) for i in by_kind(env.state, kind)]


def right_click(env, ui, start=(100, 100), end=(102, 101)):
    env.state.hovered = ui.plot
    env.state.mouse = list(start)
    env.app._on_right_down(None, None)
    env.state.hovered = None
    env.state.mouse = list(end)
    env.app._on_right_up(None, None)


def test_right_click_add_second_signal_and_remove(env):
    env.app.open_files([env.a, env.b])
    wait(env.app)
    chans = {c.name: c for d in env.app.datasets for c in d.channels}
    check(env, chans["U"])
    ui = env.app.slot_ui[0]
    right_click(env, ui)
    menu = env.state.items["ctx_menu"]
    assert menu["show"] is True and menu["pos"] == [102, 101]
    labels = [l for l, _ in menu_entries(env)]
    assert "I [A] - a.csv" in labels and "p - b.csv" in labels
    assert not any(l.startswith("U [V] -") for l in labels)       # schon im Graphen
    assert "Entfernen: U [V]" in labels

    env.state.items[env.app.ctx_filter]["value"] = "b.csv"
    env.app._fill_context_list()
    assert [u for l, u in menu_entries(env) if l.endswith(".csv")] == [chans["p"]]

    env.app._ctx_add(None, True, chans["p"])
    assert env.state.items["ctx_menu"]["show"] is False
    assert env.app.layout.slots[0].signals == [chans["U"], chans["p"]] and len(env.app.slot_ui) == 1
    assert env.state.items[env.app.checkboxes[chans["p"]]]["value"] is True
    assert len(env.app.slot_ui[0].series) == 2
    env.app._on_cross_toggle(None, True)
    assert [r[1] for r in env.app.table_rows] == [chans["U"], chans["p"]]

    right_click(env, env.app.slot_ui[0])
    labels = [l for l, _ in menu_entries(env)]
    assert "Alle Signale dieses Graphen entfernen" in labels
    env.app._ctx_remove(None, True, chans["U"])
    assert env.app.layout.slots[0].signals == [chans["p"]]
    assert env.state.items[env.app.checkboxes[chans["U"]]]["value"] is False
    assert [r[1] for r in env.app.table_rows] == [chans["p"]]

    right_click(env, env.app.slot_ui[0])
    env.app._ctx_remove(None, True, None)
    assert env.app.layout.slots == [] and env.app.slot_ui == []


def test_right_drag_is_zoom_not_menu(env):
    env.app.open_files([env.a])
    wait(env.app)
    check(env, env.app.datasets[0].channels[0])
    right_click(env, env.app.slot_ui[0], start=(100, 100), end=(180, 140))
    assert env.state.items["ctx_menu"]["show"] is False
    env.state.hovered = None
    env.app._on_right_down(None, None)      # Rechtsklick außerhalb der Graphen
    env.app._on_right_up(None, None)
    assert env.state.items["ctx_menu"]["show"] is False


def test_same_signal_in_two_graphs_and_uncheck_removes_all(env):
    env.app.open_files([env.a])
    wait(env.app)
    u, i = env.app.datasets[0].channels
    check(env, u)
    check(env, i)
    s0, s1 = env.app.layout.slots
    env.app._on_drop(env.app.slot_ui[1].plot, u)
    assert s1.signals == [i, u]
    env.app._on_drop(env.app.slot_ui[0].y_axis, u)   # dort schon vorhanden
    assert s0.signals == [u] and "bereits" in env.state.items[env.app.status]["value"]
    env.app._on_channel(None, False, u)
    assert [s.signals for s in env.app.layout.slots] == [[i]]


def test_drop_on_free_area_and_into_matrix_gap(env):
    env.app.open_files([env.a])
    wait(env.app)
    u, i = env.app.datasets[0].channels
    env.app._on_drop(env.app.plot_area, u)           # noch kein Graph: neuer Graph
    assert [s.signals for s in env.app.layout.slots] == [[u]]
    env.app._on_drop(env.app.plot_area, "kein Signal")
    env.state.items[env.app.matrix_input]["value"] = "1*3"
    env.app._on_matrix()
    env.app._on_drop(env.app.slot_ui[2].x_axis, i)
    assert [s.signals for s in env.app.layout.slots] == [[u], [], [i]]
    right_click(env, env.app.slot_ui[1])             # leerer Platz: nur Hinzufügen
    assert not any(l.startswith("Entfernen") for l, _ in menu_entries(env))
    env.app._ctx_remove(None, True, i)               # Menü von Graph 2: i steht nicht darin
    assert [s.signals for s in env.app.layout.slots] == [[u], [], [i]]


def test_drag_payload_on_every_checkbox(env):
    env.app.open_files([env.a])
    wait(env.app)
    payloads = by_kind(env.state, "drag_payload")
    assert {p["drag_data"] for p in payloads} == set(env.app.datasets[0].channels)
    assert all(env.state.items[p["parent"]]["kind"] == "add_checkbox" for p in payloads)
    plots = by_kind(env.state, "add_plot")
    assert all(p["no_menus"] and p["drop_callback"] for p in plots)


def test_lazy_channel_via_drop_lands_in_target(env):
    from messgraph.data_model import Channel, Dataset
    x = np.array([0.0, 1.0])
    loaded = Channel(name="ok", source="m.mf4", loader=lambda: (x, x, "V"))
    lazy = Channel(name="lazy", source="m.mf4", loader=lambda: (x, x * 3, "A"))
    env.app.datasets.append(Dataset(path="m.mf4", channels=[loaded, lazy]))
    env.app._refresh_channel_list()
    check(env, loaded)
    env.app._on_drop(env.app.slot_ui[0].plot, lazy)
    assert env.state.items[env.app.checkboxes[lazy]]["value"] is True   # während des Ladens
    env.app._rebuild_plots()                                          # andere Änderung dazwischen
    env.app.pool.shutdown(wait=True)
    env.app.tick()
    assert env.app.layout.slots[0].signals == [loaded, lazy]


def test_date_axis_plot_crosslines_and_table(env):
    p = env.tmp / "zeit.csv"
    p.write_text("Time;U [V]\n2026-10-01_23-00-00;10\n2026-10-01_23-01-00;20\n2026-10-02_01-00-00;140\n")
    q = env.tmp / "relativ.csv"
    q.write_text("t [s];I [A]\n0;1\n10;2\n")
    env.app.open_files([str(p), str(q)])
    wait(env.app)
    chans = {c.name: c for d in env.app.datasets for c in d.channels}
    u, i = chans["U"], chans["I"]
    check(env, u)
    env.app._on_date_axis(None, True)
    ui = env.app.slot_ui[0]
    assert ui.time_axis and env.state.items[ui.x_axis]["scale"] == "mvPlotScale_Time"
    assert env.state.items[ui.x_axis]["label"] == "Datum/Uhrzeit"
    xs = env.state.items[next(iter(ui.series.values()))]["value"][0]
    assert xs[0] == u.x_epoch and xs[-1] == u.x_epoch + 7200
    env.app._on_cross_toggle(None, True)
    env.state.items[ui.v_lines[0]]["value"] = u.x_epoch + 30
    env.state.items[ui.v_lines[1]]["value"] = u.x_epoch + 3660
    env.app.tick()
    v2 = 20 + 120 * 3600 / 7140                    # zwischen 23:01:00 (20 V) und 01:00:00 (140 V)
    assert texts_of_table(env)[0] == ["01.10.2026 23:00:30.000", "02.10.2026 00:01:00.000", "15 V",
                                      f"{v2:.6g} V", "01:00:30 (3630 s)", f"{v2 - 15:.6g} V",
                                      f"{(v2 - 15) / 3630:.6g} V/s"]

    check(env, i)                                   # Graph ohne Startzeit: Sekundenachse, X nicht gekoppelt
    assert [u_.time_axis for u_ in env.app.slot_ui] == [True, False]
    assert by_kind(env.state, "add_subplots")[0]["link_all_x"] is False
    assert "nicht gekoppelt" in env.state.items[env.app.status]["value"]
    assert env.app.slot_ui[1].slot.cross == pytest.approx([10 / 3, 20 / 3])   # eigene Positionen je Achsenart
    env.state.items[env.app.slot_ui[1].v_lines[0]]["value"] = 5.0
    env.app.tick()
    assert env.state.items[env.app.slot_ui[0].v_lines[0]]["value"] == u.x_epoch + 30
    assert texts_of_table(env)[1][:3] == ["5 s", "6.66667 s", "1.5 A"]

    env.app._on_date_axis(None, False)
    assert not any(x.time_axis for x in env.app.slot_ui)
    assert by_kind(env.state, "add_subplots")[0]["link_all_x"] is True
    assert env.app.slot_ui[0].slot.cross == pytest.approx([2400, 4800])
    assert "date_axis" in (env.tmp / "settings.json").read_text()


def test_date_axis_lod_uses_offset(env):
    p = env.tmp / "gross.csv"
    import pandas as pd
    n = 50_000
    stamps = pd.date_range("2026-10-01", periods=n, freq="s").strftime("%Y-%m-%d %H:%M:%S")
    pd.DataFrame({"Zeit": stamps, "v": np.arange(n, dtype=float)}).to_csv(p, index=False)
    env.app.open_files([str(p)])
    wait(env.app)
    c = env.app.datasets[0].channels[0]
    check(env, c)
    env.app._on_date_axis(None, True)
    ui = env.app.slot_ui[0]
    env.state.axis_limits[ui.x_axis] = [c.x_epoch + 1000, c.x_epoch + 2000]
    env.app.last_lod = 0
    env.app.tick()
    xs = np.array(env.state.items[ui.series[c]]["value"][0])
    inside = (xs >= c.x_epoch + 1000) & (xs <= c.x_epoch + 2000)
    assert inside.sum() == 1001 and xs[0] == c.x_epoch and xs[-1] == c.x_epoch + n - 1


def test_mf4_databases_dialog_flow(env, monkeypatch):
    import test_databases as td
    mod = types.ModuleType("asammdf")
    mod.MDF = td.FakeMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    folder = env.tmp / "db"
    folder.mkdir()
    (folder / "fzg.DBC").write_text("x")
    (folder / "zweite.dbc").write_text("x")
    (folder / "ecu.a2l").write_text(td.A2L)
    mf4 = env.tmp / "bus.mf4"
    mf4.write_bytes(b"x")
    env.app.open_files([str(mf4)])
    wait(env.app)
    ds = env.app.datasets[0]
    assert env.state.items["db_window"]["show"] is True and env.app.db_dataset is ds   # Rohdaten: öffnet selbst
    assert "dekodieren" in env.state.items[env.app.db_status]["value"]
    neng = ds.channels[0]
    check(env, neng)                                                                 # vorher schon angezeigt

    env.app._show_file_browser("dbc", env.app._db_add_dbc, "DBC-Dateien wählen")
    assert env.state.items["file_browser"]["label"] == "DBC-Dateien wählen"
    env.app._fb_go(str(folder))
    assert sorted(browser_files(env)) == ["fzg.DBC", "zweite.dbc"]
    env.app._fb_select_all(True)
    env.app._fb_open()
    env.app.tick()
    env.app.tick()                                   # Rückruf erst nach dem Schließen des Browsers
    assert [Path(p).name for p, _ in env.app.db_config.dbc] == ["fzg.DBC", "zweite.dbc"]
    env.app._db_channel_changed(None, "CAN 2", 0)
    env.app._db_remove_dbc(None, None, 1)
    env.app._show_file_browser("databases", env.app._db_add_files, "Datenbasen wählen (dbc, arxml, a2l, cdd)")
    assert sorted(browser_files(env)) == ["ecu.a2l", "fzg.DBC", "zweite.dbc"]
    env.app._fb_file_toggled(None, True, str(folder / "ecu.a2l"))
    env.app._fb_file_toggled(None, True, str(folder / "fzg.DBC"))       # schon zugeordnet: bleibt einmal
    env.app._fb_open()
    env.app.tick()
    env.app.tick()
    assert [Path(p).name for p in env.app.db_config.a2l] == ["ecu.a2l"] and len(env.app.db_config.dbc) == 1
    env.app._db_convert_toggled(None, True)
    env.app._db_apply()
    env.app.pool.shutdown(wait=True)
    env.app.tick()

    assert env.state.items["db_window"]["show"] is False
    assert ds.extra["mdf"].calls == [{"CAN": [(str(folder / "fzg.DBC"), 2)]}]
    names = [c.name for c in ds.channels]
    assert "VehSpeed" in names and len(names) == 5
    shown = env.app.layout.slots[0].signals[0]
    assert shown is not neng and shown.name == neng.name and shown.y.tolist() == [0, 100]   # A2L-umgerechnet
    assert env.state.items[env.app.checkboxes[shown]]["value"] is True
    assert any("DBC" in i for i in ds.info) and "angewendet" in env.state.items[env.app.status]["value"]
    assert "fzg.DBC" in (env.tmp / "settings.json").read_text()

    # Erneut öffnen: Zuordnung ist vorbelegt; leere Zuordnung stellt die Rohkanäle wieder her
    env.app._open_db_window(None, None, ds)
    assert env.app.db_config.dbc == [(str(folder / "fzg.DBC"), 2)]
    env.app.db_config.dbc = []
    env.app._db_set("a2l", [])
    env.app.pool = env.gui.ThreadPoolExecutor(max_workers=1)
    env.app._db_apply()
    env.app.pool.shutdown(wait=True)
    env.app.tick()
    assert len(ds.channels) == 3 and td.FakeDecoded.closed
    assert env.app.layout.slots[0].signals[0].y.tolist() == [400, 800]

    # Zweite Datei: "Zuletzt verwendete übernehmen"
    env.app._open_db_window(None, None, ds)
    assert env.state.items[env.app.db_last_button]["show"] is True
    env.app._db_take_last()
    assert env.app.db_config.dbc == [(str(folder / "fzg.DBC"), 2)] and env.app.db_config.a2l_convert


def test_databases_error_shown_in_dialog(env, monkeypatch):
    import test_databases as td
    mod = types.ModuleType("asammdf")
    mod.MDF = td.FakeMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    monkeypatch.setattr(env.gui, "LOG_FILE", env.tmp / "log.txt")
    mf4 = env.tmp / "bus.mf4"
    mf4.write_bytes(b"x")
    env.app.open_files([str(mf4)])
    wait(env.app)
    env.app.db_config.dbc = [(str(env.tmp / "fehlt.dbc"), 0)]
    env.app._db_apply()
    env.app.pool.shutdown(wait=True)
    env.app.tick()
    assert "nicht gefunden" in env.state.items[env.app.db_status]["value"]
    assert env.state.items["db_window"]["show"] is True
    assert "fehlt.dbc" in (env.tmp / "log.txt").read_text()


def test_data_browser_after_database_browser_uses_data_filters(env):
    env.app._show_file_browser("dbc", env.app._db_add_dbc, "DBC")
    env.app._show_file_browser()
    assert env.state.items[env.app.fb_filter]["value"].startswith("Messdaten") and env.app.fb_on_open is None


def test_context_menu_rename_and_colors(env):
    env.app.open_files([env.a])
    wait(env.app)
    u, i = env.app.datasets[0].channels
    check(env, u)
    env.state.items[env.app.target_combo]["value"] = "Graph 1"
    check(env, i)
    ui = env.app.slot_ui[0]
    default_theme = env.state.items[ui.series[i]]["bound"]
    right_click(env, ui)
    edits = by_kind(env.state, "add_color_edit")
    assert [e["label"] for e in edits] == ["U [V]", "I [A]"]
    from messgraph import themes
    assert tuple(edits[1]["default_value"][:3]) == themes.series_color("Dunkel", 1)

    env.app._ctx_color(None, [1.0, 0.0, 0.5, 1.0], i)            # Callback-Werte 0..1
    assert env.app.layout.slots[0].colors[i] == (255, 0, 128)
    assert env.state.items[ui.series[i]]["bound"] != default_theme
    assert env.state.items["ctx_menu"]["show"] is True            # Menü bleibt offen

    env.state.items[env.app.ctx_title]["value"] = "  Batterie  "
    env.app._ctx_rename()
    slot = env.app.layout.slots[0]
    assert slot.title == "Batterie" and env.state.items[env.app.slot_ui[0].plot]["label"] == "Batterie"
    assert "Graph 1: Batterie" in env.state.items[env.app.target_combo]["items"]
    env.app._on_cross_toggle(None, True)
    first_cells = [c for c in by_kind(env.state, "add_text") if c.get("value") == "Batterie"]
    assert first_cells                                            # Wertanzeige nennt den Namen

    # Farbe bleibt beim Neuaufbau und beim Wechsel Hell/Dunkel
    env.app._on_theme(None, "Hell")
    ui = env.app.slot_ui[0]
    custom = env.state.items[ui.series[i]]["bound"]
    assert custom == env.app.series_themes[("eigen", (255, 0, 128))]
    right_click(env, ui)
    assert any(s["label"] == "Standardfarben wiederherstellen" for s in by_kind(env.state, "add_selectable"))
    env.app._ctx_default_colors()
    assert slot.colors == {} and env.state.items[ui.series[i]]["bound"] == env.app.series_themes[("Hell", 1)]
    env.app._ctx_slot = None


def test_color_kept_after_remove_and_moves_with_signal(env):
    env.app.open_files([env.a])
    wait(env.app)
    u, i = env.app.datasets[0].channels
    check(env, u)
    env.app.ctx_slot = env.app.layout.slots[0]
    env.app._ctx_color(None, [10, 20, 30, 255], u)               # get_value-Werte 0..255
    assert env.app.layout.slots[0].colors[u] == (10, 20, 30)
    env.app.layout.remove_from(0, u)
    assert env.app.layout.slots == []


def test_splitters_resize_and_persist(env):
    app, st = env.app, env.state
    st.active = app.split_left
    st.mouse = [400.0, 300.0]
    app.tick()
    st.mouse = [520.0, 310.0]
    app.tick()
    assert app.left_width == 350 + 120 and st.items[app.left_panel]["width"] == 470
    st.mouse = [-500.0, 300.0]
    app.tick()
    assert app.left_width == 200                                  # Mindestbreite
    st.active = None
    app.tick()
    assert '"left_width": 200' in (env.tmp / "settings.json").read_text()

    app._on_cross_toggle(None, True)
    assert st.items[app.split_table]["show"] is True
    st.active = app.split_table
    st.mouse = [600.0, 700.0]
    app.tick()
    st.mouse = [600.0, 600.0]                                     # nach oben: Wertanzeige wird höher
    app.tick()
    assert app.table_h == 290 and st.items[app.table_area]["height"] == 290
    assert st.items[app.plot_area]["height"] == -(290 + 7 + 12)
    st.mouse = [600.0, 5000.0]
    app.tick()
    assert app.table_h == 80
    st.active = None
    app.tick()
    assert env.gui.App().table_h == 80 and env.gui.App().left_width == 200


def labels_of(env, kind):
    return [i.get("label") for i in by_kind(env.state, kind)]


def test_menu_bar_order_file_left_language_and_help_right(env):
    app = env.app
    children = env.state.items[app.menu_bar]["children"]
    kinds = [(env.state.items[c]["kind"], env.state.items[c].get("label")) for c in children]
    assert kinds == [("menu", "Datei"), ("menu", "Graph-Optionen"), ("menu", "Limiter"), ("menu", "Auto"), ("add_spacer", None), ("menu", "Hilfe"),
                     ("add_spacer", None), ("menu", "Sprache: Deutsch")]
    assert [i.get("label") for i in by_kind(env.state, "tab")] == ["Graph"]          # kein Reiter Hilfe mehr
    app.show_help()
    assert env.state.items["help_window"]["show"] is True
    app.hide_help()
    assert env.state.items["help_window"]["show"] is False
    rects = env.state.rects                                          # gezeichnete Lage der Menüs
    rects[app.file_menu] = ([8.0, 0.0], [40.0, 20.0])                # rechts bei 48
    rects[app.graph_menu] = ([56.0, 0.0], [110.0, 20.0])             # normaler Abstand 8, rechts bei 166
    rects[app.limiter_menu] = ([174.0, 0.0], [60.0, 20.0])           # normaler Abstand, rechts bei 234
    rects[app.auto_menu] = ([242.0, 0.0], [40.0, 20.0])              # normaler Abstand, rechts bei 282
    rects[app.help_menu] = ([290.0, 0.0], [40.0, 20.0])              # Abstand 8 -> soll 16 werden
    rects[app.lang_menu] = ([1300.0, 0.0], [150.0, 20.0])            # rechts bei 1450
    env.state.items[app.menu_spacer]["width"] = 900
    app.spacer_width = None
    app.spacer_checked = 0
    app.tick()
    assert env.state.items[app.help_gap]["width"] == 16              # doppelter Abstand vor Hilfe
    assert env.state.items[app.menu_spacer]["width"] == 900 + (1500 - app.MENU_RIGHT_MARGIN - 1450)   # Sprache rechts
    items = [env.state.items[c] for c in env.state.items[app.lang_menu]["children"]]
    thai = "ไทย (Thai)" if app.thai_font else "Thai"                 # ohne Thai-Schrift lateinisch
    chinese = "中文 (Chinese)" if getattr(app, "cjk_font", None) else "Chinese"
    assert [i["label"] for i in items] == ["Deutsch", "English", thai, chinese] and items[0]["default_value"] is True


def test_language_switch_translates_and_keeps_state(env):
    app = env.app
    app.open_files([env.a])
    wait(app)
    u, i = app.datasets[0].channels
    env.state.items[app.matrix_input]["value"] = "1*2"
    app._on_matrix()
    check(env, u)
    app.layout.slots[0].title = "Spannung"
    app.layout.slots[0].colors[u] = (1, 2, 3)
    app._on_cross_toggle(None, True)
    env.state.items[app.cross_box]["value"] = True
    app.layout.slots[0].cross = [10.0, 20.0]
    env.state.items[app.filter_input]["value"] = "U"
    lang_items = env.state.items[app.lang_menu]["children"]
    app._on_language_item(lang_items[1], True, "English")

    assert app.lang == "English" and app.help_lang == "English"
    assert "Open files..." in labels_of(env, "add_button") and "Couple X axes" in labels_of(env, "add_checkbox")
    menus = [env.state.items[c].get("label") for c in env.state.items[app.menu_bar]["children"]]
    assert menus == ["File", "Graph options", "Limiter", "Auto", None, "Help", None, "Language: English"]
    assert "Language: English" in env.state.items[app.status]["value"]
    assert list(app.help_groups)[0] == "Overview"
    # Zustand erhalten
    assert [d.name for d in app.datasets] == ["a.csv"] and app.layout.matrix == (1, 2)
    slot = app.layout.slots[0]
    assert slot.signals == [u] and slot.title == "Spannung" and slot.colors[u] == (1, 2, 3) and slot.cross == [10.0, 20.0]
    assert env.state.items[app.matrix_input]["value"] == "1*2" and env.state.items[app.filter_input]["value"] == "U"
    assert app.cross_on and env.state.items[app.cross_box]["value"] is True
    assert env.state.items[app.slot_ui[0].plot]["label"] == "Spannung"
    assert env.state.items[app.slot_ui[1].plot]["label"] == "Graph 2"
    assert env.state.items[app.target_combo]["items"][0] == "Automatic"
    assert [c.get("label") for c in by_kind(env.state, "add_table_column")][-14:][4] == "Value 1"
    assert env.state.items[app.theme_combo]["value"] == "Dark"
    app._on_theme(None, "Light")                                      # übersetzte Anzeige -> interner Name
    assert app.mode == "Hell"
    # neue Meldungen und Erkennungstexte in Englisch
    app.open_files([env.b])
    wait(app)
    assert "b.csv: 1 signals." in env.state.items[app.status]["value"]
    assert any(line.startswith("Separator: comma") for line in app.datasets[1].info)
    env.state.items[app.matrix_input]["value"] = "x"
    app._on_matrix()
    assert env.state.items[app.status]["value"] == "Please enter the matrix as n*m, for example 2*3"
    # Kontextmenü und Datei-Browser übersetzt
    right_click(env, app.slot_ui[0])
    assert "Remove all signals of this graph" not in labels_of(env, "add_selectable")   # nur ein Signal
    assert "Remove: U [V]" in labels_of(env, "add_selectable")
    app._show_file_browser()
    assert env.state.items[app.fb_filter]["items"][0] == "Measurement data (mf4, mdf, blf, csv, asc, txt, dat, parquet)"
    assert env.state.items["file_browser"]["label"] == "Open files..."
    # zurück auf Deutsch, Einstellung gemerkt
    app.set_language("Deutsch")
    assert "Dateien öffnen..." in labels_of(env, "add_button") and app.mode == "Hell"
    assert '"language": "Deutsch"' in (env.tmp / "settings.json").read_text()


def test_language_thai_uses_thai_font(env):
    app = env.app
    app.thai_font = "thai-font"
    bound = []
    env.gui.dpg.bind_font = bound.append
    app.set_language("Thai")
    assert app.lang == "Thai" and bound[-1] == "thai-font"
    assert "เปิดไฟล์..." in labels_of(env, "add_button")
    menus = [env.state.items[c].get("label") for c in env.state.items[app.menu_bar]["children"]]
    assert menus == ["ไฟล์", "ตัวเลือกกราฟ", "ตัวจำกัดข้อมูล", "อัตโนมัติ", None, "ช่วยเหลือ", None, "ภาษา: ไทย (Thai)"]
    assert env.state.items[app.lang_items["Thai"]]["font"] == "thai-font"   # Thai-Oberfläche: global gebunden
    assert list(app.help_groups)[0] == "ภาพรวม"
    app.set_language("English")
    assert bound[-1] == app.ui_font or app.ui_font is None


def test_language_survives_restart_and_db_dialog_choices(env, monkeypatch):
    import test_databases as td
    mod = types.ModuleType("asammdf")
    mod.MDF = td.FakeMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    app = env.app
    app.set_language("English")
    mf4 = env.tmp / "bus.mf4"
    mf4.write_bytes(b"x")
    dbc = env.tmp / "x.dbc"
    dbc.write_text("x")
    app.open_files([str(mf4)])
    wait(app)
    assert env.state.items["db_window"]["show"] is True
    texts = [i["value"] for i in by_kind(env.state, "add_text")]
    assert any("Bus raw data without physical values: CAN_DataFrame" in v for v in texts)   # Sprache der Oberfläche
    app._db_add_dbc([str(dbc)])
    combos = [c for c in by_kind(env.state, "add_combo") if c.get("user_data") == ("dbc", 0)]
    assert combos[-1]["items"][0] == "All channels"
    app._db_channel_changed(None, "CAN 3", 0)
    assert app.db_config.dbc == [(str(dbc), 3)]
    assert env.gui.App().lang == "English"


def test_secondary_right_y_axis(env):
    app = env.app
    app.open_files([env.a, env.b])
    wait(app)
    chans = {c.name: c for d in app.datasets for c in d.channels}
    u, i, p = chans["U"], chans["I"], chans["p"]
    check(env, u)
    env.state.items[app.target_combo]["value"] = "Graph 1"
    check(env, i)
    ui = app.slot_ui[0]
    assert ui.y2_axis is None                                        # ohne Signal rechts keine zweite Achse
    right_click(env, ui)
    boxes = [b for b in by_kind(env.state, "add_checkbox") if b.get("user_data") in (u, i)
             and env.state.items[b["parent"]]["kind"] == "add_window"]
    assert [b["label"] for b in boxes] == ["U [V]", "I [A]"] and not any(b["default_value"] for b in boxes)

    app._ctx_axis(None, True, i)                                     # I auf die rechte Achse
    ui = app.slot_ui[0]
    slot = app.layout.slots[0]
    assert slot.right == {i} and ui.y2_axis is not None
    y2 = env.state.items[ui.y2_axis]
    assert y2["args"][0] == "mvYAxis2" and y2["opposite"] is True and y2["label"] == "[A]"
    assert env.state.items[ui.y_axis]["label"] == "[V]"
    assert env.state.items[ui.series[i]]["parent"] == ui.y2_axis and env.state.items[ui.series[u]]["parent"] == ui.y_axis
    assert env.state.items[ui.series[i]]["label"] == "I [A] (rechts)"
    assert "I [A] auf der rechten Y-Achse." in env.state.items[app.status]["value"]
    assert ui.y2_axis in env.state.fixed_axes                        # rechte Achse eingepasst (mit Rand)
    app._on_cross_toggle(None, True)
    assert any(t.get("value") == "I [A] (rechts)" for t in by_kind(env.state, "add_text"))   # Wertanzeige

    # Drag and Drop auf die rechte Achse: neues Signal landet rechts
    app._on_drop(ui.y2_axis, p)
    assert p in slot.signals and p in slot.right
    # bereits vorhandenes Signal per Drop auf die rechte Achse verschieben
    app._on_drop(app.slot_ui[0].y2_axis, u)
    assert slot.right == {i, p, u}
    # zurück nach links, Speichern/Laden behält die Zuordnung
    app._set_axis(slot, u, False)
    assert slot.right == {i, p}
    data = app.session_dict()
    axes = {s["name"]: s["axis"] for s in data["graphs"][0]["signals"]}
    assert axes == {"U": "left", "I": "right", "p": "right"}
    app.layout.remove_from(0, i)
    assert i not in slot.right


def test_secondary_axis_restored_from_session(env, tmp_path):
    app = env.app
    app.open_files([env.a])
    wait(app)
    u, i = app.datasets[0].channels
    check(env, u)
    app.layout.slots[0].signals.append(i)
    app.layout.slots[0].right.add(i)
    app.save_session(str(tmp_path / "v.mgraph"))
    app.load_session(str(tmp_path / "v.mgraph"))
    wait(app)
    slot = app.layout.slots[0]
    assert [c.name for c in slot.signals] == ["U", "I"] and {c.name for c in slot.right} == {"I"}
    assert app.slot_ui[0].y2_axis is not None


def test_downsampling_dialog_settings_session_and_reload(env, monkeypatch):
    from messgraph import downsample
    app, dpg = env.app, env.gui.dpg
    try:
        assert "Downsampling..." in [i.get("label") for i in by_kind(env.state, "add_menu_item")]
        app._open_ds_window()
        assert dpg.get_value(app.ds_mode) == "Automatisch"
        assert env.state.items[app.ds_manual_group].get("show") is False
        dpg.set_value(app.ds_mode, "Manuell")
        dpg.set_value(app.ds_method, downsample.METHOD_NAMES["grid"])
        dpg.set_value(app.ds_interval, 0.5)
        app._ds_mode_changed()
        assert env.state.items[app.ds_interval_row].get("show") is True
        assert env.state.items[app.ds_factor_row].get("show") is False
        app._ds_apply(False)
        cfg = downsample.config()
        assert (cfg.mode, cfg.method, cfg.interval) == ("manual", "grid", 0.5)
        import json
        assert json.loads(Path(env.tmp / "settings.json").read_text())["downsampling"]["method"] == "grid"
        assert app.session_dict()["options"]["downsampling"]["interval"] == 0.5
        # Ansicht mit anderer Einstellung laden: gilt vor dem Laden der Dateien
        data = app.session_dict()
        data["options"]["downsampling"] = {"mode": "off"}
        app.apply_session(data, None)
        wait(app)
        assert downsample.config().mode == "off"
        # Neu laden nur, wenn MF4/Parquet geöffnet sind
        calls = []
        monkeypatch.setattr(app, "apply_session", lambda d, b: calls.append(d))
        app._ds_apply(True)
        assert calls == []
        from messgraph.data_model import Dataset
        app.datasets.append(Dataset(path=str(env.tmp / "x.parquet")))
        app._ds_apply(True)
        assert len(calls) == 1
        app.datasets.pop()
    finally:
        downsample.set_config(downsample.DownsampleConfig())


def test_downsampling_note_in_status(env, monkeypatch):
    from messgraph.data_model import Channel
    app, msgs = env.app, []
    monkeypatch.setattr(app, "_message", msgs.append)
    ch = Channel(name="s", source="a.parquet", x=np.arange(10.0), y=np.arange(10.0),
                 ds_note="reduziert (Mittelwert je Block): 100 -> 10 Werte")
    app._request_add(ch, None)
    assert "100 -> 10 Werte" in msgs[-1]


def test_progress_bar_for_mf4_parquet_and_cancel(env):
    from messgraph.data_model import Channel, Dataset
    from messgraph import progress
    app, dpg = env.app, env.gui.dpg
    gate, started = __import__("threading").Event(), __import__("threading").Event()

    def slow():
        started.set()
        gate.wait(5)
        progress.step(0.5, "lesen")   # nächster Meldepunkt: hier greift der Abbruch
        return np.arange(3.0), np.arange(3.0), "V"
    ch = Channel(name="slow", source="m.mf4", loader=slow)
    app.datasets.append(Dataset(path="m.mf4", channels=[ch]))
    app._refresh_channel_list()
    env.state.items[app.checkboxes[ch]]["value"] = True
    app._on_channel(None, True, ch)
    started.wait(5)
    app.tick()
    assert env.state.items[app.progress_row].get("show") is True
    assert "slow" in dpg.get_value(app.progress_text)
    assert "%" in env.state.items[app.progress_bar].get("overlay", "")
    app._cancel_jobs()
    gate.set()
    wait(app)
    app.tick()
    assert not ch.loaded and env.state.items[app.checkboxes[ch]]["value"] is False
    assert "abgebrochen" in dpg.get_value(app.status)
    assert env.state.items[app.progress_row].get("show") is False and app.jobs == []
    # CSV bekommt keine Fortschrittsanzeige
    app.open_files([env.a])
    assert app.jobs == []
    wait(app)


def test_compare_window_suggest_select_compute_export(env):
    app, dpg = env.app, env.gui.dpg
    c = env.tmp / "c.csv"
    c.write_text("time [s];U [V];I [A]\n" + "".join(f"{i};{i * 3};{50 - i}\n" for i in range(51)))
    app._open_cmp_window()
    assert "mindestens zwei" in dpg.get_value(app.status)
    app.open_files([env.a, env.b, str(c)])
    wait(app)
    assert "ähnlichem Aufbau" in dpg.get_value(app.status)
    app._open_cmp_window()
    assert {os.path.basename(p) for p in app.cmp_files} == {"a.csv", "c.csv"}      # b.csv ist anders aufgebaut
    assert app.cmp_signals == {"U", "I"}                                          # wenige gemeinsame: vorgewählt
    labels = [i.get("label") for i in by_kind(env.state, "add_checkbox") if i.get("parent") == app.cmp_signal_area]
    assert labels == ["U [V]", "I [A]"] or labels == ["U", "I"]
    dpg.set_value(app.cmp_stat_boxes["avg"], False)
    app._cmp_toggle_signal(None, False, "I")
    app._cmp_start()
    wait(app)
    while app.cmp_result is None or app.jobs:
        app.tick()
    r = app.cmp_result
    assert r.files == ["a.csv", "c.csv"] and [row.stat for row in r.rows] == ["min", "max"]
    assert r.rows[1].values == [200.0, 150.0]
    assert "a.csv" in [i.get("label") for i in by_kind(env.state, "add_table_column")]
    app._cmp_copy()
    assert dpg.clipboard[-1].startswith("Signal\tEinheit\tKennwert\tToleranz %\ta.csv\tc.csv\tAbweichung")
    dpg.set_value(app.cmp_path, str(env.tmp / "vergleich"))
    app._cmp_save()
    assert "U;V;max;;200;150;" in (env.tmp / "vergleich.csv").read_text(encoding="utf-8-sig")
    assert json.loads((env.tmp / "settings.json").read_text())["compare_stats"] == ["min", "max"]
    # Sprache wechseln: Fenster wird neu gebaut, Ergebnis bleibt
    app.set_language("English")
    assert app.cmp_result is r and "Compare files..." in [i.get("label") for i in by_kind(env.state, "add_menu_item")]
    app.set_language("Deutsch")


def test_limits_lines_and_prediction_with_date_axis(env, monkeypatch):
    p = env.tmp / "zeit.csv"
    p.write_text("Time;U [V]\n2026-10-01_23-00-00;10\n2026-10-01_23-01-00;20\n2026-10-02_01-00-00;140\n")
    env.app.open_files([str(p)])
    wait(env.app)
    u = env.app.datasets[0].channels[0]
    check(env, u)
    app = env.app
    app._on_cross_toggle(None, True)
    ui = app.slot_ui[0]
    labels = [c.get("label") for c in by_kind(env.state, "add_table_column")][-14:]
    assert labels[-5:] == ["Y min", "Y max", "Zielzeit", "Drift (Regression 1)", "Prognose"]
    app._on_limit(None, "150", (ui, u, 1))
    assert ui.slot.limits[u] == [None, 150.0]
    line = ui.limit_series[u][0]
    assert env.state.items[line]["value"][1] == [150.0, 150.0] and env.state.items[line]["label"].startswith("##")
    app._on_limit(None, "-", (ui, u, 0))                           # unvollständig: bleibt
    assert ui.slot.limits[u] == [None, 150.0]
    # Regression über alle Daten (0 s: 10 V, 60 s: 20 V, 7200 s: 140 V)
    xs, ys = np.array([0.0, 60.0, 7200.0]), np.array([10.0, 20.0, 140.0])
    m = np.polyfit(xs, ys, 1)[0]
    slope_text, pred_text = app.table_preds[0]
    assert env.state.items[slope_text]["value"] == f"{m:.6g} V/s"
    x2 = (150 - 140) / m                                            # ab letztem Wert 140 V
    mins = round(x2 / 60)
    assert env.state.items[pred_text]["value"] == f"max, x2 = {x2:.6g} s, 0 days {mins // 60} hrs {mins % 60} min"
    app._on_date_axis(None, True)
    ui = app.slot_ui[0]
    assert ui.limit_series[u] and env.state.items[ui.limit_series[u][0]]["value"][0][0] == u.x_epoch
    boxes = [i for i in by_kind(env.state, "add_input_text") if i.get("user_data") and len(i["user_data"]) == 3
             and i["user_data"][1] is u]
    assert boxes[-1]["default_value"] == "150"                     # Eingabe bleibt nach Neuaufbau erhalten
    import pandas as pd
    target = pd.Timestamp("2026-10-02 01:00:00") + pd.Timedelta(seconds=x2)
    text = env.state.items[app.table_preds[0][1]]["value"]
    assert text == f"max, {target:%d.%m.%Y %H:%M:%S}, 0 days {mins // 60} hrs {mins % 60} min"
    env.state.items[ui.v_lines[0]]["value"] = u.x_epoch + 100      # Marker beeinflussen die Prognose nicht
    app.tick()
    assert env.state.items[app.table_preds[0][1]]["value"] == text
    app._on_limit(None, "130", (ui, u, 1))
    assert env.state.items[app.table_preds[0][1]]["value"] == "Grenze 130 V schon überschritten (letzter Wert 140 V)"
    app._on_limit(None, "0", (ui, u, 0))
    app._on_limit(None, "", (ui, u, 1))
    assert "kein Schnitt" in env.state.items[app.table_preds[0][1]]["value"]
    app._on_cross_toggle(None, False)
    assert all(env.state.items[i].get("show") is False for i in ui.limit_series[u])
    data = app.session_dict()
    assert data["graphs"][0]["signals"][0]["limits"] == [0.0, None]
    app.layout.remove(u)
    assert u not in ui.slot.limits
    wait(app)


def test_compare_tolerance_highlights_rows(env):
    app, dpg = env.app, env.gui.dpg
    c = env.tmp / "c.csv"
    c.write_text("time [s];U [V];I [A]\n" + "".join(f"{i};{i * 2.1};{100 - i}\n" for i in range(101)))
    app.open_files([env.a, str(c)])
    wait(app)
    app._open_cmp_window()
    app._cmp_start()
    while app.cmp_result is None or app.jobs:
        app.tick()
    labels = [col.get("label") for col in by_kind(env.state, "add_table_column")][-5:]
    assert labels == ["Signal", "%", "Kennwert", "a.csv", "c.csv"]
    assert app.cmp_rows[0][1].signal == "U" and env.state.items[app.cmp_rows[0][2]]["value"] == "U [V]"
    assert not dpg.highlighted
    app._cmp_pct_changed(None, "4", "U")                    # U: 100 vs 105 (avg) = 5 % > 4 %
    flagged = {row for (table, row) in dpg.highlighted}
    u_rows = [n for n, row, _, _ in app.cmp_rows if row.signal == "U"]
    assert flagged == {u_rows[0], u_rows[2]}                # avg und max; min (0 = 0) nicht
    assert env.state.items[app.cmp_rows[0][2]]["color"] == (255, 85, 85, 255)
    assert env.state.items[app.cmp_rows[0][3][1]]["color"] == (255, 85, 85, 255)
    assert "Abweichung über der Toleranz" in dpg.get_value(app.cmp_status)
    app._cmp_pct_changed(None, "6", "U")
    assert not dpg.highlighted
    assert json.loads((env.tmp / "settings.json").read_text())["compare_tolerance"] == {"U": "6"}
    app._cmp_pct_changed(None, "", "U")
    assert app.cmp_pct == {}


def test_markers_follow_zoom_to_10_and_90_percent(env):
    app = env.app
    app.open_files([env.a, env.b])
    wait(app)
    chans = [ds.channels[0] for ds in app.datasets]
    for ch in chans:
        check(env, ch)
    app._on_cross_toggle(None, True)
    uis = app.slot_ui
    limits = env.state.axis_limits

    def frame(view):
        for ui in uis:
            limits[ui.x_axis] = list(view)
        app.tick()
    for _ in range(6):                       # Einpassen nach dem Aufbau verschiebt nichts
        frame((0.0, 50.0))
    start = list(uis[0].slot.cross)
    frame((0.0, 50.0))
    assert uis[0].slot.cross == start        # gleicher Sichtbereich: Marker bleiben, wo sie sind
    assert len(uis) == 2                     # zwei Graphen, Marker synchron
    frame((10.0, 30.0))                      # Zoom
    for ui in uis:
        assert ui.slot.cross == pytest.approx([12.0, 28.0])
        assert [env.state.items[v]["value"] for v in ui.v_lines] == pytest.approx([12.0, 28.0])
    frame((11.0, 31.0))                      # Verschieben, Marker bleiben im Bild: keine Änderung
    assert uis[0].slot.cross == pytest.approx([12.0, 28.0])
    frame((20.0, 40.0))                      # M1 fällt links heraus: neu ausrichten
    assert uis[0].slot.cross == pytest.approx([22.0, 38.0])
    frame((0.0, 100.0))                      # Unzoom
    assert uis[0].slot.cross == pytest.approx([10.0, 90.0])
    app._on_cross_toggle(None, False)        # ohne Marker: nichts nachführen
    frame((0.0, 10.0))
    assert uis[0].slot.cross == pytest.approx([10.0, 90.0])


def test_graph_font_size_slider(env):
    app, dpg = env.app, env.gui.dpg
    app.ui_font_path = "/fonts/DejaVuSans.ttf"     # Schriftdatei für die Größen (Datei wird im Fake nicht gelesen)
    app._build_size_fonts()                          # wie beim Start: alle Größen vorab
    assert all(("/fonts/DejaVuSans.ttf", size) in app.size_fonts for size in range(10, 33))
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    slider = env.state.items[app.font_slider]
    assert (slider["min_value"], slider["max_value"], slider["default_value"]) == (10, 32, 17)
    siblings = env.state.items[slider["parent"]]["children"]
    assert env.state.items[siblings[siblings.index(app.font_slider) - 1]]["kind"] == "add_text"    # Beschriftung "Schrift"
    app._on_font_size(None, 24)
    font = app.size_fonts[("/fonts/DejaVuSans.ttf", 24)]
    assert env.state.items[app.slot_ui[0].plot]["font"] == font
    assert env.state.items[app.table_area]["font"] == font
    assert json.loads((env.tmp / "settings.json").read_text())["graph_font_size"] == 24
    fonts_before = len([i for i in env.state.items.values() if i["kind"] == "font"])
    app._on_font_size(None, 24)
    assert len([i for i in env.state.items.values() if i["kind"] == "font"]) == fonts_before   # keine neuen Schriften
    app._on_matrix()                                 # Graphen neu aufbauen: Größe bleibt
    assert env.state.items[app.slot_ui[0].plot]["font"] == font
    assert app.session_dict()["options"]["graph_font_size"] == 24
    app._apply_options({"graph_font_size": 99})
    assert app.graph_font_size == 32 and dpg.get_value(app.font_slider) == 32


def test_context_menu_print_export_and_report(env, monkeypatch, tmp_path):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a, env.b])
    wait(app)
    for ds in app.datasets:
        check(env, ds.channels[0])
    app._on_cross_toggle(None, True)
    slot = app.layout.slots[0]
    app._open_context_menu(slot, (100, 100))
    labels = [i.get("label") for i in by_kind(env.state, "add_selectable") if i.get("parent") == "ctx_menu"]
    assert {"Diesen Graphen drucken / exportieren...", "Alle Graphen drucken / exportieren...",
            "Report als PDF erstellen..."} <= set(labels)
    # ein Graph als PDF (aus dem Kontextmenü: Dialog öffnet einige Bilder später)
    app._open_export("one", slot)
    assert env.state.items["export_window"].get("show") is False
    app.tick()
    app.tick()
    assert env.state.items["export_window"].get("show") is True
    assert env.state.items[app.exp_report_group].get("show") is False
    dpg.set_value(app.exp_target, "PDF-Datei")
    dpg.set_value(app.exp_path, str(tmp_path / "einer.pdf"))
    app._exp_run()
    assert (tmp_path / "einer.pdf").read_bytes().startswith(b"%PDF")
    assert "PDF gespeichert" in dpg.get_value(app.status)
    # alle als SVG: Dateiendung folgt der Wahl
    app._open_export("all")
    dpg.set_value(app.exp_target, "SVG-Vektorgrafik")
    app._exp_target_changed()
    assert dpg.get_value(app.exp_path).endswith(".svg")
    dpg.set_value(app.exp_path, str(tmp_path / "alle.svg"))
    dpg.set_value(app.exp_paper, "A3")
    app._exp_run()
    svg = (tmp_path / "alle.svg").read_text()
    assert svg.count("<polyline") >= 2 and 'width="420.0mm"' in svg     # A3 quer
    # Drucker: PDF wird an den Druckbefehl übergeben
    sent = []
    monkeypatch.setattr(env.gui.plotexport, "print_file", lambda path: sent.append(path) or "lp")
    app._open_export("all")
    dpg.set_value(app.exp_target, "Drucker")
    app._exp_target_changed()
    assert env.state.items[app.exp_path_row].get("show") is False
    app._exp_run()
    assert sent and sent[0].endswith("MessGraph_Druck.pdf") and "Drucker gesendet (lp)" in dpg.get_value(app.status)
    monkeypatch.setattr(env.gui.plotexport, "print_file", lambda path: (_ for _ in ()).throw(OSError("kein Drucker")))
    app._open_export("all")
    app._exp_run()
    assert "kein Drucker" in dpg.get_value(app.exp_status) and env.state.items["export_window"]["show"] is True
    # Report
    app._open_export("report")
    assert env.state.items[app.exp_report_group].get("show") is True
    dpg.set_value(app.exp_title, "Prüfbericht")
    dpg.set_value(app.exp_author, "M. F.")
    dpg.set_value(app.exp_path, str(tmp_path / "bericht.pdf"))
    app._exp_run()
    assert (tmp_path / "bericht.pdf").exists() and "Report gespeichert" in dpg.get_value(app.status)
    data = app._report_data("T", "", "")
    assert len(data.graphs) == 2 and [h for h, _c, _r in data.graphs[0].tables][:2] == ["Signale", "Marker-Messung"]
    assert data.graphs[0].tables[1][2][0][0] == app.layout.slots[0].signals[0].label
    assert json.loads((env.tmp / "settings.json").read_text())["export"]["author"] == "M. F."


def test_legend_position_via_right_click(env, monkeypatch):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    ui = app.slot_ui[0]
    assert env.state.items[ui.legend]["location"] == dpg.mvPlot_Location_NorthWest      # Standard oben links
    # Rechtsklick auf die Legende: nur die Positionen
    monkeypatch.setattr(dpg, "is_item_hovered", lambda item: item in (ui.plot, ui.legend))
    monkeypatch.setattr(dpg, "get_mouse_pos", lambda local=False: [500, 300])
    app._on_right_down()
    app._on_right_up()
    items = [env.state.items[i]["label"] for i in app.ctx_legend_items.values()]
    assert [label.strip(" »") for label in items] == ["oben links", "oben Mitte", "oben rechts", "unten links",
                                                      "unten Mitte", "unten rechts"]
    assert items[0] == "» oben links"
    assert "Name des Graphen" not in [i.get("value") for i in by_kind(env.state, "add_text") if i.get("parent") == "ctx_menu"]
    app._set_legend(ui.slot, "se")
    assert env.state.items[ui.legend]["location"] == dpg.mvPlot_Location_SouthEast
    assert env.state.items["ctx_menu"]["show"] is False
    # Rechtsklick auf den Graphen: volles Menü, Legende ebenfalls wählbar
    monkeypatch.setattr(dpg, "is_item_hovered", lambda item: item == ui.plot)
    app._on_right_down()
    app._on_right_up()
    assert app.ctx_legend_items and env.state.items[app.ctx_legend_items["se"]]["label"] == "» unten rechts"
    # Lage bleibt beim Neuaufbau, gehört zur Ansicht und zum Export
    app._on_matrix()
    assert env.state.items[app.slot_ui[0].legend]["location"] == dpg.mvPlot_Location_SouthEast
    assert app.session_dict()["graphs"][0]["legend"] == "se"
    assert app._plot_spec(app.slot_ui[0], 0).legend == "se"


def calc_wait(app):
    """Bis die Berechnung im Hintergrund fertig ist und das Ergebnis übernommen wurde."""
    import messgraph.gui as gui
    end = time.time() + 5
    while time.time() < end:
        app.tick()
        if gui.dpg.get_value(app.calc_status) != "Wird berechnet...":
            return
        time.sleep(0.01)
    raise AssertionError("Zeitüberschreitung")


def test_calc_dialog_create_edit_delete(env):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a])
    wait(app)
    ds = app.datasets[0]
    buttons = [i for i in by_kind(env.state, "add_button") if i.get("label") == "Berechnen..."]
    assert buttons and buttons[0]["user_data"] is ds
    app._open_calc_window(None, None, ds)
    assert env.state.items["calc_window"]["show"] is True
    dpg.set_value(app.calc_name, "P")
    dpg.set_value(app.calc_signal, "U")
    app._calc_insert_signal()
    app._calc_insert(None, None, " * ")
    dpg.set_value(app.calc_signal, "I")
    app._calc_insert_signal()
    assert dpg.get_value(app.calc_formula) == "{U} * {I}"
    app._calc_apply()
    calc_wait(app)
    p = next(c for c in ds.channels if c.name == "P")
    assert p.y[10] == 20 * 90 and p.unit == "W"     # U [V] * I [A] = W
    assert "berechnet" in dpg.get_value(app.status)
    labels = [i.get("label") for i in by_kind(env.state, "add_checkbox") if i.get("user_data") is p]
    assert labels and labels[-1].startswith("= P")
    check(env, p)                                     # wie jedes Signal plotten
    assert app.layout.contains(p)
    # Fehler wird im Dialog gemeldet
    dpg.set_value(app.calc_name, "X")
    dpg.set_value(app.calc_formula, "{U} *")
    app._calc_apply()
    assert "Fehler" in dpg.get_value(app.calc_status)
    # zweites Signal aus dem ersten, dann das erste umbenennen und ändern
    dpg.set_value(app.calc_name, "P2")
    dpg.set_value(app.calc_formula, "{P} / 1000")
    app._calc_apply()
    calc_wait(app)
    p2 = next(c for c in ds.channels if c.name == "P2")
    app._calc_edit(p)
    dpg.set_value(app.calc_name, "Leistung")
    dpg.set_value(app.calc_formula, "{U} * {I} * 2")
    app._calc_apply()
    calc_wait(app)
    assert p.name == "Leistung" and p.y[10] == 2 * 20 * 90 and app.layout.contains(p)
    assert p2.formula == "{Leistung} / 1000"
    app._calc_delete(p)                               # wird noch von P2 verwendet
    assert p in ds.channels and "noch verwendet" in dpg.get_value(app.calc_status)
    app._calc_delete(p2)
    app._calc_delete(p)
    assert p not in ds.channels and not app.layout.contains(p)


def test_report_general_and_per_graph_comments(env, tmp_path):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a, env.b])
    wait(app)
    for ds in app.datasets:
        check(env, ds.channels[0])
    app._open_export("report")
    boxes = [i for i in by_kind(env.state, "add_input_text") if i.get("parent") == app.exp_graph_notes]
    assert len(boxes) == 2 and env.state.items["export_window"]["height"] > 470
    app._exp_comment_changed(None, "Allgemein: Lauf nach Update")
    app._exp_note_changed(None, "Spitze bei 40 s prüfen", app.layout.slots[0])
    dpg.set_value(app.exp_comment, "Allgemein: Lauf nach Update")
    data = app._report_data("T", "", dpg.get_value(app.exp_comment))
    assert data.comment.startswith("Allgemein") and data.graphs[0].comment == "Spitze bei 40 s prüfen"
    assert data.graphs[1].comment == ""
    dpg.set_value(app.exp_path, str(tmp_path / "r.pdf"))
    app._exp_run()
    assert (tmp_path / "r.pdf").exists()
    session = app.session_dict()
    assert session["graphs"][0]["note"] == "Spitze bei 40 s prüfen"
    assert session["options"]["report_comment"] == "Allgemein: Lauf nach Update"
    app._open_export("report")                       # erneut öffnen: Eingaben bleiben
    assert dpg.get_value(app.exp_comment) == "Allgemein: Lauf nach Update"
    boxes = [i for i in by_kind(env.state, "add_input_text") if i.get("parent") == app.exp_graph_notes]
    assert boxes[0]["default_value"] == "Spitze bei 40 s prüfen"
    try:
        import subprocess
        text = subprocess.run(["pdftotext", str(tmp_path / "r.pdf"), "-"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return
    assert "Spitze bei 40 s prüfen" in text and "Allgemein: Lauf nach Update" in text


def test_help_chapter_list_without_fixed_height(env):
    app = env.app
    assert env.state.items[app.help_list]["kind"] == "add_group"
    items = list(app.help_items.values())
    assert len(items) == len(app.help_groups) and env.state.items[items[0]]["default_value"] is True
    title = list(app.help_items)[3]
    app._on_help_select(None, True, title)
    assert env.state.items[app.help_groups[title]]["show"] is True
    assert env.state.items[items[3]]["value"] is True and env.state.items[items[0]]["value"] is False


def test_thai_font_only_on_thai_language_entry(env):
    app = env.app
    app.thai_font = "thai-font"
    app._apply_font()
    items = app.lang_items
    assert env.state.items[items["Thai"]].get("font") == "thai-font"
    assert env.state.items[items["Deutsch"]].get("font") is None and env.state.items[items["English"]].get("font") is None
    assert env.state.items[app.lang_menu].get("font") is None     # Beschriftung "Sprache: ..." in Oberflächenschrift


def test_definition_file_save_and_load_after_restart(env, tmp_path):
    app, dpg = env.app, env.gui.dpg
    app._open_def_window()
    assert "noch keine berechneten" in dpg.get_value(app.status)
    app.open_files([env.a])
    wait(app)
    ds = app.datasets[0]
    app._open_calc_window(None, None, ds)
    dpg.set_value(app.calc_name, "P")
    dpg.set_value(app.calc_formula, "{U} * {I}")
    dpg.set_value(app.calc_note, "Leistung")
    app._calc_apply()
    calc_wait(app)
    p = next(c for c in ds.channels if c.name == "P")
    assert p.note == "Leistung"
    app._open_def_window()                           # aus dem offenen Rechendialog: einige Bilder später
    app.tick()
    app.tick()
    assert env.state.items["def_window"]["show"] is True and dpg.get_value(app.def_path).endswith(".def")
    dpg.set_value(app.def_title, "Leistungsrechnung")
    dpg.set_value(app.def_comment, "für alle Läufe")
    dpg.set_value(app.def_path, str(tmp_path / "rechnung"))
    app._save_definitions()
    assert (tmp_path / "rechnung.def").exists() and "gespeichert" in dpg.get_value(app.status)
    # "Neustart": Datei schließen, Definition über den Datei-Browser laden
    app.datasets.clear()
    app._refresh_channel_list()
    app._ask_load_definitions()
    assert app.fb_mode == "definition" and list(app.fb_filters)[0] == "MessGraph-Definition (*.def)"
    app._load_definitions([str(tmp_path / "rechnung.def")])
    wait(app)
    assert len(app.datasets) == 1
    p2 = next(c for c in app.datasets[0].channels if c.name == "P")
    assert p2.formula == "{U} * {I}" and p2.note == "Leistung" and p2.y[10] == 20 * 90
    assert "1 berechnete Signale geladen (Leistungsrechnung)" in dpg.get_value(app.status)
    assert app.settings["definition"]["title"] == "Leistungsrechnung"



def test_definition_load_offers_open_run_of_same_structure(env, tmp_path):
    from messgraph import definitions, formula
    from messgraph.loaders import load_file
    app, dpg = env.app, env.gui.dpg
    run1 = tmp_path / "lauf1.csv"
    run1.write_text("time [s];U [V];I [A]\n" + "".join(f"{i};{i};{2}\n" for i in range(11)))
    first = load_file(str(run1))
    formula.add_or_replace(first, formula.compute(first, "P", "", "{U} * {I}"))
    target = definitions.write(str(tmp_path / "p.def"), definitions.build([first], "Leistung", base_dir=str(tmp_path)))
    app.open_files([env.a])                          # nach Neustart: anderer Lauf gleicher Struktur geöffnet
    wait(app)
    app._load_definitions([target])
    assert env.state.items["def_load_window"]["show"] is True
    boxes = [i for i in by_kind(env.state, "add_checkbox") if i.get("parent") == app.def_load_area]
    labels = [b["label"] for b in boxes]
    assert labels[0].endswith("(gespeicherte Datei, wird geöffnet)") and boxes[0]["default_value"] is False
    assert labels[1] == "a.csv (geöffnet, passende Signale)" and boxes[1]["default_value"] is True
    app._run_definitions()
    wait(app)
    assert [d.name for d in app.datasets] == ["a.csv"]          # gespeicherte Datei nicht zusätzlich geöffnet
    p = next(c for c in app.datasets[0].channels if c.name == "P")
    assert p.y[10] == 20 * 90
    # erneut laden, diesmal beide: P in a.csv wird ersetzt, nicht verdoppelt; lauf1.csv kommt dazu
    app._load_definitions([target])
    plan_target = app.def_plans[0][2][0]
    plan_target.use_stored = True
    app._run_definitions()
    wait(app)
    assert sorted(d.name for d in app.datasets) == ["a.csv", "lauf1.csv"]
    assert [c.name for c in app.datasets[0].channels].count("P") == 1
    assert "2 berechnete Signale geladen" in dpg.get_value(app.status)



def test_calc_dialog_opens_browser_and_save_dialog_after_closing(env):
    """Modales Fenster -> modales Fenster: erst schließen, dann einige Bilder später öffnen."""
    app = env.app
    app.open_files([env.a])
    wait(app)
    ds = app.datasets[0]
    app._open_calc_window(None, None, ds)
    app._ask_load_definitions()
    assert env.state.items["calc_window"]["show"] is False and env.state.items["file_browser"].get("show") is not True
    app.tick()
    app.tick()
    assert env.state.items["file_browser"]["show"] is True and app.fb_mode == "definition"
    # Definition speichern aus dem Rechendialog
    from messgraph import formula
    formula.add_or_replace(ds, formula.compute(ds, "P", "", "{U} * {I}"))
    env.state.items["file_browser"]["show"] = False
    app._open_calc_window(None, None, ds)
    app._open_def_window()
    assert env.state.items["def_window"].get("show") is not True
    app.tick()
    app.tick()
    assert env.state.items["def_window"]["show"] is True


def test_blf_open_and_decode_via_databases_dialog(env):
    from pathlib import Path as P
    demo = P(__file__).parent.parent / "demo_data"
    app = env.app
    app.open_files([str(demo / "demo_can.blf")])
    wait(app)
    ds = app.datasets[0]
    buttons = [i for i in by_kind(env.state, "add_button") if i.get("label") == "Datenbasen..." and i.get("user_data") is ds]
    assert buttons, "Datenbasen-Schaltfläche fehlt für BLF"
    app._open_db_window(None, None, ds)
    app._db_add_dbc([str(demo / "demo_can.dbc")])
    app._db_apply()
    end = time.time() + 5
    while time.time() < end and (app.jobs or not any(c.name == "Drehzahl" for c in ds.channels)):
        app.tick()
        time.sleep(0.01)
    names = [c.name for c in ds.channels]
    assert "Drehzahl" in names and "Spannung" in names
    check(env, next(c for c in ds.channels if c.name == "Spannung"))
    assert app.layout.slots[0].signals[0].unit == "V"
    session = app.session_dict()
    assert session["files"][0]["databases"]["dbc"][0][0].endswith("demo_can.dbc")


def test_databases_auto_apply_for_new_bus_recording(env, monkeypatch):
    import test_databases as td
    mod = types.ModuleType("asammdf")
    mod.MDF = td.FakeMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    dbc = env.tmp / "fzg.dbc"
    dbc.write_text("x")
    env.app.settings["databases_last"] = {"dbc": [[str(dbc), 0]], "a2l": [], "cdd": []}
    env.app._db_auto_toggled(None, True)
    mf4 = env.tmp / "bus.mdf"                      # MDF 3: gleicher Leser wie MF4
    mf4.write_bytes(b"x")
    env.app.open_files([str(mf4)])
    wait(env.app)
    env.app.pool.shutdown(wait=True)
    env.app.tick()
    ds = env.app.datasets[0]
    assert env.state.items["db_window"]["show"] is False                    # kein Dialog nötig
    assert ds.extra["config"].dbc == [(str(dbc), 0)] and "VehSpeed" in [c.name for c in ds.channels]
    assert ds.info[0].startswith("MDF")


def _three_runs(env):
    paths = []
    for k in range(3):
        p = env.tmp / f"lauf_{k}.csv"
        p.write_text("time [s];Temp [C];Druck [bar]\n" + "".join(f"{i};{i + k};{2 * i}\n" for i in range(20)))
        paths.append(str(p))
    env.app.open_files(paths + [env.b])
    wait(env.app)


def test_search_signal_over_all_files_shared_and_single(env):
    _three_runs(env)
    assert env.state.items[env.app.multi_area]["show"] is False          # ohne Suche keine Leiste
    env.state.items[env.app.filter_input]["value"] = "temp"
    env.app._refresh_channel_list()
    assert env.state.items[env.app.multi_area]["show"] is True
    assert env.state.items[env.app.multi_combo]["items"] == ["Temp"]
    env.app._multi_plot(None, None, "shared")
    wait(env.app)
    assert len(env.app.layout.slots) == 1 and len(env.app.layout.slots[0].signals) == 3
    assert {c.source for c in env.app.layout.slots[0].signals} == {str(env.tmp / f"lauf_{k}.csv") for k in range(3)}
    assert "3 von 4 Dateien, 3 davon angezeigt" in env.state.items[env.app.multi_info]["value"]
    env.app._multi_remove()
    assert env.app.layout.signals() == []
    env.app._multi_plot(None, None, "single")
    wait(env.app)
    assert [len(s.signals) for s in env.app.layout.slots] == [1, 1, 1]


def test_search_over_all_files_shared_into_target_and_matrix(env):
    _three_runs(env)
    env.app.layout.set_matrix((2, 2))
    env.app._layout_changed()
    env.state.items[env.app.filter_input]["value"] = "druck"
    env.app._refresh_channel_list()
    env.state.items[env.app.target_combo]["value"] = env.app.layout.target_names()[3]   # Graph 3
    env.app._multi_plot(None, None, "shared")
    wait(env.app)
    assert len(env.app.layout.slots[2].signals) == 3
    env.state.items[env.app.target_combo]["value"] = env.app.layout.target_names()[0]
    env.state.items[env.app.filter_input]["value"] = "temp"
    env.app._refresh_channel_list()
    env.app._multi_plot(None, None, "single")
    wait(env.app)
    assert sorted(len(s.signals) for s in env.app.layout.slots) == [1, 1, 1, 3]   # leere Graphen zuerst


def test_search_single_file_hit_shows_no_bar(env):
    env.app.open_files([env.a, env.b])
    wait(env.app)
    env.state.items[env.app.filter_input]["value"] = "U"
    env.app._refresh_channel_list()
    assert env.state.items[env.app.multi_area]["show"] is False


def test_report_signal_table_values_selectable(env, tmp_path):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    app._open_export("report")
    assert all(dpg.get_value(box) for box in app.exp_stats.values())            # Vorgabe: alle aktiv
    data = app._report_data("T", "", "", app._exp_selected_stats())
    heading, headers, rows = data.graphs[0].tables[0]
    assert headers[3:] == ["Minimum (min)", "Maximum (max)", "Mittelwert (avg)", "Drift (Regression 1)"]
    assert len(rows[0]) == 7
    dpg.set_value(app.exp_stats["min"], False)
    dpg.set_value(app.exp_stats["avg"], False)
    data = app._report_data("T", "", "", app._exp_selected_stats())
    heading, headers, rows = data.graphs[0].tables[0]
    assert heading == "Signale" and headers[3:] == ["Maximum (max)", "Drift (Regression 1)"] and len(rows[0]) == 5
    dpg.set_value(app.exp_path, str(tmp_path / "r.pdf"))
    app._exp_run()
    assert app.settings["export"]["report_stats"] == ["max", "drift"]
    app._open_export("report")                                                  # Wahl bleibt erhalten
    assert [k for k, b in app.exp_stats.items() if dpg.get_value(b)] == ["max", "drift"]
    for box in app.exp_stats.values():
        dpg.set_value(box, False)
    data = app._report_data("T", "", "", app._exp_selected_stats())
    assert all(h != "Signale" for h, _c, _r in data.graphs[0].tables)           # keine Signaltabelle
    dpg.set_value(app.exp_path, str(tmp_path / "ohne.pdf"))
    app._exp_run()
    try:
        import subprocess
        text = subprocess.run(["pdftotext", str(tmp_path / "ohne.pdf"), "-"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return
    assert "Signalspiegel" in text and "Mittelwert" not in text and "Drift (Regression)" not in text


def test_report_formats_pdf_html_both(env, tmp_path):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    check(env, app.datasets[0].channels[1])
    app._open_export("report")
    assert app._exp_report_format() == "both"                                  # Vorgabe: beide
    dpg.set_value(app.exp_path, str(tmp_path / "bericht.pdf"))
    app._exp_run()
    assert (tmp_path / "bericht.pdf").exists() and (tmp_path / "bericht.html").exists()
    text = (tmp_path / "bericht.html").read_text(encoding="utf-8")
    assert text.count('class="graph"') == 2 and text.count('data-key="s0"') >= 6     # je Graph: Kurve, Spiegel, Tabelle
    app._open_export("report")
    dpg.set_value(app.exp_format, "Dynamisch (HTML)")
    dpg.set_value(app.exp_path, str(tmp_path / "nur_dyn"))
    app._exp_run()
    assert (tmp_path / "nur_dyn.html").exists() and not (tmp_path / "nur_dyn.pdf").exists()
    assert app.settings["export"]["report_format"] == "html"
    app._open_export("report")
    assert app._exp_report_format() == "html"                                  # Wahl gemerkt
    dpg.set_value(app.exp_format, "PDF (fest)")
    dpg.set_value(app.exp_path, str(tmp_path / "nur_pdf.pdf"))
    app._exp_run()
    assert (tmp_path / "nur_pdf.pdf").exists() and not (tmp_path / "nur_pdf.html").exists()


def test_ascii_import_dialog_reload_keeps_graphs(env):
    import test_ascii
    app, dpg = env.app, env.gui.dpg
    path = test_ascii.raw_file(env.tmp)
    app.open_files([path])
    wait(app)
    ds = app.datasets[0]
    channel = next(c for c in ds.channels if c.name == "Kl30_V")
    check(env, channel)
    assert app.layout.contains(channel)
    buttons = [b for b in by_kind(env.state, "add_button") if b.get("label") == "ASCII-Import..."]
    assert buttons and buttons[0]["user_data"] == ds.path
    app._open_ascii_window(None, None, ds.path)
    assert env.state.items["ascii_window"]["show"] is True
    assert "Kopfzeile: Zeilen 7-8" in dpg.get_value(app.ascii_result)
    marked = [i["value"] for i in by_kind(env.state, "add_text") if str(i.get("value", "")).startswith("K> ")]
    assert len(marked) == 2 and "<{Continue}>" in marked[1]                   # Zeile 7 und Fortsetzung 8
    dpg.set_value(app.ascii_header, 7)
    dpg.set_value(app.ascii_sep, "Komma")
    app._ascii_preview()
    app._ascii_apply()
    wait(app)
    app.pool.shutdown(wait=True)
    app.tick()
    assert app.datasets == [ds] and "Kopfzeile: Zeilen 7-8 (vom Nutzer festgelegt)" in ds.info
    assert next(c for c in ds.channels if c.name == "Kl30_V") is channel and app.layout.contains(channel)
    assert ds.extra["ascii"]["options"]["sep"] == ","


def test_ascii_unrecognised_opens_dialog_and_template(env):
    app, dpg = env.app, env.gui.dpg
    path = env.tmp / "nur_text.txt"
    path.write_text("Messung Halle drei\nKommentar ohne Zahlen\n")
    app.open_files([str(path)])
    wait(app)
    app.pool.shutdown(wait=True)
    app.tick()
    assert not app.datasets and env.state.items["ascii_window"]["show"] is True
    assert "Nicht erkannt" in dpg.get_value(app.ascii_status)
    import test_ascii
    good = test_ascii.raw_file(env.tmp, name="vorlage.dat")
    app._open_ascii_window(None, None, good)
    dpg.set_value(app.ascii_header, 7)
    dpg.set_value(app.ascii_template, True)
    app.pool = __import__("concurrent.futures").futures.ThreadPoolExecutor(2)
    app._ascii_apply()
    wait(app)
    app.pool.shutdown(wait=True)
    app.tick()
    assert app.settings["ascii_template"]["header_line"] == 7
    assert app.datasets and "vom Nutzer festgelegt" in " ".join(app.datasets[0].info)
    assert app._load_with_template(test_ascii.raw_file(env.tmp, name="weitere.asc"), None).extra["ascii"]["options"]["header_line"] == 7


def _settle(app):
    wait(app)
    app.pool.shutdown(wait=True)
    app.tick()
    import concurrent.futures
    app.pool = concurrent.futures.ThreadPoolExecutor(2)


def test_project_save_close_open_restores_everything(env):
    import json
    from messgraph import formula, project
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a, env.b])
    wait(app)
    ds_a = next(d for d in app.datasets if d.path == env.a)
    made = formula.add_or_replace(ds_a, formula.compute(ds_a, "P", "", "{U} * {I}"))
    made.note = "Leistung"
    app._refresh_channel_list()
    check(env, ds_a.channels[0])
    check(env, made)
    app.layout.slots[0].note = "Bemerkung Graph"
    app.layout.slots[0].legend = "se"
    app.layout.slots[0].limits[ds_a.channels[0]] = [10.0, 150.0]
    app.report_comment = "Allgemein"
    app.settings["export"] = {"paper": "A3", "report_stats": ["max", "drift"], "report_format": "html"}
    app.settings["compare_tolerance"] = 4.0
    app.settings["language"] = "Deutsch"
    dpg.set_value(app.filter_input, "U")
    app._open_project_window()
    assert env.state.items["project_window"]["show"] is True
    assert "2 Dateien" in dpg.get_value(app.proj_summary) and "1 berechnete" in dpg.get_value(app.proj_summary)
    dpg.set_value(app.proj_name, "Prüfstand 3")
    dpg.set_value(app.proj_comment, "Lauf nach Software-Update")
    dpg.set_value(app.proj_path, str(env.tmp / "Pruefstand3"))
    app._project_window_ok()
    path = env.tmp / "Pruefstand3.mgproj"
    assert path.exists() and app.project_path == str(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == project.FORMAT and data["settings"]["export"]["paper"] == "A3"
    assert data["session"]["files"][0]["relpath"] in ("a.csv", "b.csv") and data["ui"]["filter"] == "U"
    assert app.settings["recent_projects"][0] == str(path)
    app.close_project()
    _settle(app)
    assert app.datasets == [] and app.project_path is None and not app.layout.signals()
    app.settings["export"] = {}
    app.open_project(str(path))
    _settle(app)
    assert app.project_name == "Prüfstand 3" and app.project_comment == "Lauf nach Software-Update"
    assert {d.name for d in app.datasets} == {"a.csv", "b.csv"}
    ds = next(d for d in app.datasets if d.name == "a.csv")
    p = next(c for c in ds.channels if c.name == "P")
    assert p.formula == "{U} * {I}" and p.note == "Leistung"
    slot = app.layout.slots[0]
    assert slot.note == "Bemerkung Graph" and slot.legend == "se" and list(slot.limits.values()) == [[10.0, 150.0]]
    assert app.report_comment == "Allgemein" and app.settings["export"]["report_format"] == "html"
    assert app.settings["compare_tolerance"] == 4.0 and dpg.get_value(app.filter_input) == "U"
    app.layout.slots[0].note = "geändert"
    app._save_project_now()                                     # Projekt speichern: ohne Rückfrage ins Projekt
    assert json.loads(path.read_text(encoding="utf-8"))["session"]["graphs"][0]["note"] == "geändert"
    assert json.loads(path.read_text(encoding="utf-8"))["created"] == data["created"]


def test_project_moved_folder_with_blf_and_databases(env):
    import shutil
    app, dpg = env.app, env.gui.dpg
    demo = Path(__file__).resolve().parent.parent / "demo_data"
    old = env.tmp / "alt"
    (old / "db").mkdir(parents=True)
    shutil.copy(demo / "demo_can.blf", old / "log.blf")
    shutil.copy(demo / "demo_can_motor.dbc", old / "db")
    shutil.copy(demo / "demo_can_batterie.arxml", old / "db")
    app.open_files([str(old / "log.blf")])
    wait(app)
    ds = app.datasets[0]
    app._open_db_window(None, None, ds)
    app._db_add_files([str(old / "db" / "demo_can_motor.dbc"), str(old / "db" / "demo_can_batterie.arxml")])
    app._db_apply()
    _settle(app)
    check(env, next(c for c in ds.channels if c.name == "Drehzahl"))
    check(env, next(c for c in ds.channels if c.name == "Spannung"))
    assert app.save_project(str(old / "projekt"))
    new = env.tmp / "neu"
    shutil.copytree(old, new)
    shutil.rmtree(old)
    app.close_project()
    _settle(app)
    env.state.items[app.recent_menu]                            # Menü vorhanden
    app.open_project(str(new / "projekt.mgproj"))
    _settle(app)
    ds = app.datasets[0]
    assert ds.path == str(new / "log.blf")
    assert {c.name for c in app.layout.signals()} == {"Drehzahl", "Spannung"}
    assert [Path(p).parent for p, _ in ds.extra["config"].bus] == [new / "db", new / "db"]
    assert "nicht gefunden" not in env.state.items[app.status]["value"]


def _runs(env, count=2, missing=False):
    paths = []
    for k in range(count):
        p = env.tmp / f"lauf_{k + 1}.csv"
        cols = "time [s];U [V];I [A]" + ("" if missing and k else ";T [C]")
        rows = "".join(f"{i};{i + k};{2 * i}" + ("" if missing and k else f";{20 + i}") + "\n" for i in range(30))
        p.write_text(cols + "\n" + rows)
        paths.append(str(p))
    return paths


def _setup_source(env, path):
    from messgraph import formula
    app = env.app
    app.open_files([path])
    wait(app)
    ds = next(d for d in app.datasets if d.path == path)
    made = formula.add_or_replace(ds, formula.compute(ds, "P", "", "{U} * {I}"))
    app._refresh_channel_list()
    for name in ("U", "P", "T"):
        channel = next((c for c in ds.channels if c.name == name), None)
        if channel is not None:
            app._on_channel(None, True, channel)
            wait(app)
            env.gui.dpg.set_value(app.target_combo, app.layout.target_names()[1])   # alle in Graph 1
    slot = app.layout.slots[0]
    slot.colors[slot.signals[0]] = (10, 20, 30)
    slot.limits[slot.signals[0]] = [1.0, 40.0]
    slot.note, slot.legend, slot.title = "Notiz", "ne", "Spannung"
    return ds


def test_transfer_current_state_to_other_file(env):
    app, dpg = env.app, env.gui.dpg
    one, two = _runs(env)
    _setup_source(env, one)
    app.open_files([two])
    wait(app)
    app._open_transfer_window()
    assert env.state.items["transfer_window"]["show"] is True
    assert app.tr_targets == {one: two}                                     # Vorschlag: gleiche Struktur
    texts = [i["value"] for i in by_kind(env.state, "add_text")]
    assert any("3 von 3 vorhanden" in str(v) for v in texts)
    app._tr_apply()
    _settle(app)
    assert [d.path for d in app.datasets] == [two]
    ds = app.datasets[0]
    assert next(c for c in ds.channels if c.name == "P").formula == "{U} * {I}"
    slot = app.layout.slots[0]
    assert slot.title == "Spannung" and slot.note == "Notiz" and slot.legend == "ne"
    assert all(c.source == two for c in app.layout.signals())
    first = slot.signals[0]
    assert slot.colors[first] == (10, 20, 30) and slot.limits[first] == [1.0, 40.0]
    assert "Einstellungen übertragen: lauf_1.csv -> lauf_2.csv" in env.state.items[app.status]["value"]
    assert app.project_path is None


def test_transfer_from_saved_view_reports_missing_and_keeps_files(env):
    app, dpg = env.app, env.gui.dpg
    one, two = _runs(env, missing=True)                                    # lauf_2 ohne Signal T
    _setup_source(env, one)
    view = env.tmp / "vorlage.mgraph"
    app.save_session(str(view))
    app.close_project()
    _settle(app)
    app.open_files([two, env.b])
    wait(app)
    app._open_transfer_window()
    app._tr_set_source(str(view))
    assert app.tr_targets == {one: two}
    assert any("2 von 3 vorhanden" in str(i["value"]) for i in by_kind(env.state, "add_text"))
    dpg.set_value(app.tr_keep, True)
    app._tr_apply()
    _settle(app)
    assert sorted(d.name for d in app.datasets) == ["b.csv", "lauf_2.csv"]
    assert {c.name for c in app.layout.signals()} == {"U", "P"}
    status = env.state.items[app.status]["value"]
    assert "lauf_1.csv -> lauf_2.csv" in status and "T" in status and "nicht gefunden" in status


def test_transfer_from_project_with_other_file_chosen(env):
    app, dpg = env.app, env.gui.dpg
    one, two = _runs(env)
    _setup_source(env, one)
    app.settings["export"] = {"paper": "A5"}
    app.save_project(str(env.tmp / "vorlage"))
    app.close_project()
    _settle(app)
    app.settings["export"] = {}
    app._open_transfer_window(str(env.tmp / "vorlage.mgproj"))
    assert app.tr_targets == {}                                               # keine Datei offen: kein Vorschlag
    app._tr_choice_changed(None, "Andere Datei wählen...", one)
    for _ in range(4):
        app.tick()
    app._fb_file_toggled(None, True, two)
    app._fb_open()
    for _ in range(4):
        app.tick()
    assert app.tr_targets == {one: two}
    app._tr_apply()
    _settle(app)
    assert [d.path for d in app.datasets] == [two] and app.settings["export"]["paper"] == "A5"
    assert len(app.layout.slots[0].signals) == 3


def test_matrix_rows_merged_builds_row_subplots(env):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    dpg.set_value(app.matrix_input, "4*3: 3, 3, 2+1, 1")
    app._on_matrix()
    assert len(app.layout.slots) == 9 and app.layout.spans == [[1, 1, 1], [1, 1, 1], [2, 1], [3]]
    subs = by_kind(env.state, "add_subplots")
    assert [s.get("column_ratios") for s in subs] == [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [2.0, 1.0], [3.0]]
    assert len(app.slot_ui) == 9 and app.layout.signals()                 # Signal bleibt erhalten
    assert "Matrix 4*3 mit zusammengefassten Bereichen: 9 Graphen." in env.state.items[app.status]["value"]
    assert "Graph 7 (Z3/S1-2)" in app.layout.target_names()
    data = app.session_dict(None)
    assert data["spans"] == [[1, 1, 1], [1, 1, 1], [2, 1], [3]]
    dpg.set_value(app.matrix_input, "4*3: 2")
    app._on_matrix()
    assert "nicht in 2 gleich breite" in env.state.items[app.status]["value"] and len(app.layout.slots) == 9


def test_rows_dialog_preview_and_apply(env):
    app, dpg = env.app, env.gui.dpg
    app._open_rows_window()                                                   # ohne Matrix: Hinweis
    assert "zuerst eine Matrix" in env.state.items[app.status]["value"]
    dpg.set_value(app.matrix_input, "4*3")
    app._on_matrix()
    app._open_rows_window()
    assert env.state.items["rows_window"]["show"] is True and len(app.rows_inputs) == 4
    assert [dpg.get_value(f) for f in app.rows_inputs] == ["3", "3", "3", "3"]
    dpg.set_value(app.rows_inputs[2], "2+1")
    dpg.set_value(app.rows_inputs[3], "1")
    app._rows_preview()
    assert dpg.get_value(app.rows_status) == "9 Graphen"
    dpg.set_value(app.rows_inputs[1], "5")
    app._rows_preview()
    assert "Zeile 2" in dpg.get_value(app.rows_status)
    dpg.set_value(app.rows_inputs[1], "3")
    app._rows_apply()
    assert dpg.get_value(app.matrix_input) == "4*3: 3, 3, 2+1, 1" and len(app.layout.slots) == 9
    app._open_rows_window()
    assert [dpg.get_value(f) for f in app.rows_inputs] == ["3", "3", "2+1", "1"]
    app._rows_reset()
    app._rows_apply()
    assert app.layout.spans is None and dpg.get_value(app.matrix_input) == "4*3"


def test_merged_rows_link_x_axes_across_rows(env):
    app, dpg = env.app, env.gui.dpg
    app.open_files([env.a])
    wait(app)
    dpg.set_value(app.matrix_input, "2*2: 1, 2")
    app._on_matrix()
    for channel in app.datasets[0].channels[:2]:
        app.layout.slots[0 if channel is app.datasets[0].channels[0] else 1].signals.append(channel)
    app._layout_changed()
    axes = [ui.x_axis for ui in app.slot_ui]
    for axis in axes:
        env.state.axis_limits[axis] = [0.0, 10.0]
    for _ in range(6):                                                        # Aufbauphase
        app._poll_link()
    env.state.axis_limits[axes[0]] = [2.0, 4.0]                               # Zoom im oberen Graphen
    app._poll_link()
    assert all(env.state.axis_limits[a] == [2.0, 4.0] for a in axes)
    assert set(axes[1:]) <= env.state.fixed_axes
    app._poll_link()                                                          # nächstes Bild: wieder frei
    assert not env.state.fixed_axes & set(axes)
    app._on_link(None, False)
    for _ in range(6):
        app._poll_link()
    env.state.axis_limits[app.slot_ui[0].x_axis] = [5.0, 6.0]
    app._poll_link()
    assert dpg.get_axis_limits(app.slot_ui[1].x_axis) != [5.0, 6.0]          # ohne Kopplung unabhängig


def test_report_graphs_have_ten_percent_y_margin(env):
    import numpy as np
    app = env.app
    app.open_files([env.a])
    wait(app)
    channel = app.datasets[0].channels[0]
    check(env, channel)
    env.state.axis_limits[app.slot_ui[0].x_axis] = [-1e9, 1e9]                 # ganzer Verlauf sichtbar
    data = app._report_data("T", "", "")
    lo, hi = data.graphs[0].spec.ylim
    vmin, vmax = float(np.nanmin(channel.y)), float(np.nanmax(channel.y))
    assert hi >= vmax + 0.1 * abs(vmax) - 1e-9 and lo <= vmin - 0.1 * abs(vmin) + 1e-9
    spec = app._plot_spec(app.slot_ui[0], 0)               # die Plots haben inzwischen denselben Rand
    assert spec.ylim == data.graphs[0].spec.ylim


def test_arrange_proposal_dialog_and_apply(env):
    app, dpg = env.app, env.gui.dpg
    demo = Path(__file__).resolve().parent.parent / "demo_data" / "demo_pruefstand.asc"
    app.open_files([str(demo), env.a])
    wait(app)
    app._open_arrange_window()
    assert env.state.items["arrange_window"]["show"] is True
    labels = env.state.items[app.arr_source]["items"]
    assert any(label.startswith("Alle Signale: demo_pruefstand.asc") for label in labels)
    dpg.set_value(app.arr_source, next(l for l in labels if l.startswith("Alle Signale: demo_pruefstand.asc")))
    app._arrange_preview()
    proposal = app.arr_proposal
    titles = [g.title for g in proposal.groups]
    assert titles[:3] == ["AC Spannung", "AC Strom", "AC Leistung"] or titles[:2] == ["AC Spannung", "AC Strom"]
    assert "Temperaturen" in proposal.rows and "Vorschlag: Matrix" in dpg.get_value(app.arr_summary)
    drawn = [d for d in env.state.drawn if d[2] == app.arr_preview]
    assert drawn                                                            # Vorschau gezeichnet
    app._arrange_apply()
    wait(app)
    assert env.state.items["arrange_window"]["show"] is False
    assert app.layout.matrix == proposal.matrix and app.layout.spans == proposal.spans
    assert [s.title for s in app.layout.slots] == titles
    assert [len(s.signals) for s in app.layout.slots] == [len(g.signals) for g in proposal.groups]
    assert dpg.get_value(app.matrix_input).startswith(f"{proposal.matrix[0]}*{proposal.matrix[1]}")
    assert "Anordnung übernommen" in env.state.items[app.status]["value"]
    app._open_arrange_window()                                             # jetzt mit angezeigten Signalen
    assert env.state.items[app.arr_source]["items"][0].startswith("Angezeigte Signale")
    dpg.set_value(app.arr_curves, 2)
    app._arrange_preview()
    assert max(len(g.signals) for g in app.arr_proposal.groups) <= 2


def test_plot_area_empty_without_files(env):
    app = env.app
    def area_children():
        return [k for k, v in env.state.items.items() if v.get("parent") == app.plot_area]
    env.state.items[app.matrix_input]["value"] = "2*2"
    app._on_matrix()
    assert app.layout.matrix == (2, 2)
    assert area_children() == [] and not by_kind(env.state, "add_plot") and app.slot_ui == []
    app.open_files([env.a])
    wait(app)
    assert by_kind(env.state, "add_subplots")[0]["args"] == (2, 2) and len(by_kind(env.state, "add_plot")) == 4
    app._close_dataset(None, None, app.datasets[0])
    assert area_children() == [] and not by_kind(env.state, "add_plot")
    assert app.layout.matrix == (2, 2)          # die Matrix bleibt für die nächste Datei eingestellt


def test_plot_y_axis_fitted_with_ten_percent_margin(env):
    import numpy as np
    app = env.app
    app.open_files([env.a])
    wait(app)
    u, i = app.datasets[0].channels
    check(env, u)
    ui = app.slot_ui[0]
    vmin, vmax = float(np.nanmin(u.y)), float(np.nanmax(u.y))
    lo, hi = env.state.axis_limits[ui.y_axis]
    assert hi == pytest.approx(vmax * 1.1)
    assert lo == pytest.approx(vmin * 0.9 if vmin else vmin - 0.1 * (vmax - vmin))   # min 0: 10 % der Spannweite
    assert ui.y_axis in env.state.fixed_axes and ui.x_axis in env.state.fits
    for _ in range(app.Y_HOLD_FRAMES + 1):                    # danach wieder frei (Zoomen möglich)
        app._poll_y_release()
    assert ui.y_axis not in env.state.fixed_axes
    env.state.axis_limits[ui.y_axis] = [0.0, 1.0]           # gezoomt; "Alles anzeigen" stellt den Rand wieder her
    app._fit_all()
    assert env.state.axis_limits[ui.y_axis] == [pytest.approx(lo), pytest.approx(hi)]
    env.state.hovered = ui.plot                             # Doppelklick öffnet das Detailfenster ...
    app._on_double_click()
    zoom = app.zoom_ui
    assert zoom is not None and env.state.axis_limits[zoom.y_axis] == [pytest.approx(lo), pytest.approx(hi)]
    env.state.axis_limits[zoom.y_axis] = [0.0, 1.0]         # ... dort passt er mit Rand ein
    env.state.hovered = zoom.plot
    app._on_double_click()
    assert env.state.axis_limits[zoom.y_axis] == [pytest.approx(lo), pytest.approx(hi)]


def test_y_margin_rules():
    from messgraph.plotexport import value_margin
    assert value_margin(10.0, 100.0) == (pytest.approx(9.0), pytest.approx(110.0))       # min*0,9  max*1,1
    assert value_margin(-50.0, -10.0) == (pytest.approx(-55.0), pytest.approx(-9.0))    # negative Werte
    assert value_margin(0.0, 200.0) == (pytest.approx(-20.0), pytest.approx(220.0))     # 0: 10 % der Spannweite


def _switch_runs(env):
    """Drei gleich aufgebaute Dateien; die dritte mit nachzuladenden Kanälen (wie MF4) und ohne I."""
    import numpy as np
    from messgraph.data_model import Channel, Dataset
    paths = []
    for k in (1, 2):
        p = env.tmp / f"lauf_{k}.csv"
        p.write_text("time [s];U [V];I [A];T [°C]\n" + "".join(f"{i};{i * k};{50 - i};{20 + k}\n" for i in range(51)))
        paths.append(str(p))
    env.app.open_files(paths)
    wait(env.app)
    x = np.arange(51.0)
    lazy = Dataset(path=str(env.tmp / "lauf_3.mf4"), channels=[
        Channel(name="U", unit="V", source=str(env.tmp / "lauf_3.mf4"), loader=lambda: (x, x * 3, "V")),
        Channel(name="T", unit="°C", source=str(env.tmp / "lauf_3.mf4"), loader=lambda: (x, x * 0 + 23, "°C"))])
    env.app.datasets.append(lazy)
    env.app._refresh_channel_list()
    return env.app.datasets


def test_file_combo_switches_all_graphs_to_selected_file(env):
    app = env.app
    first, second, third = _switch_runs(env)
    by = lambda d, name: next(c for c in d.channels if c.name == name)
    env.state.items[app.matrix_input]["value"] = "2*1"
    app._on_matrix()
    app.layout.slots[0].title = "Elektrik"
    for name in ("U", "I"):
        app._request_add(by(first, name), 0)
    app._request_add(by(first, "T"), 1)
    app.layout.slots[0].right.add(by(first, "I"))
    app.layout.slots[0].colors[by(first, "U")] = (1, 2, 3)
    app.layout.slots[0].limits[by(first, "U")] = [0.0, 40.0]
    app._layout_changed()
    items = env.state.items[app.file_combo]
    assert items["items"] == ["Alle Dateien", "lauf_1.csv", "lauf_2.csv", "lauf_3.mf4"] and items["value"] == "lauf_1.csv"
    app._on_file_combo(None, "lauf_2.csv")                                     # eingelesene Datei: sofort
    slot = app.layout.slots[0]
    assert [c.source for c in app.layout.signals()] == [second.path] * 3
    assert slot.title == "Elektrik" and slot.right == {by(second, "I")}        # Einstellungen gehen mit
    assert slot.colors == {by(second, "U"): (1, 2, 3)} and slot.limits == {by(second, "U"): [0.0, 40.0]}
    assert env.state.items[app.file_combo]["value"] == "lauf_2.csv"
    app._on_file_combo(None, "lauf_3.mf4")                                     # Kanäle werden erst geladen
    wait(app)
    assert [c.name for c in app.layout.slots[0].signals] == ["U"] and [c.name for c in app.layout.slots[1].signals] == ["T"]
    assert all(c.source == third.path and c.loaded for c in app.layout.signals())
    assert "Nicht in lauf_3.mf4: I [A]" in env.state.items[app.status]["value"]
    assert app.layout.matrix == (2, 1) and app.layout.slots[0].title == "Elektrik"


def test_file_combo_replaces_signal_plotted_over_all_files(env):
    app = env.app
    first, second, _third = _switch_runs(env)
    us = [c for d in (first, second) for c in d.channels if c.name == "U"]
    for channel in us:                                        # gemeinsamer Graph über die Dateien (Suche)
        app._request_add(channel, None if not app.layout.slots else 0)
    assert len(app.layout.slots[0].signals) == 2
    assert env.state.items[app.file_combo]["value"] == "Mehrere Dateien"
    app._on_file_combo(None, "lauf_2.csv")
    assert app.layout.slots[0].signals == [us[1]]             # nur noch einmal, aus der gewählten Datei
    app._on_file_combo(None, "keine Datei")                  # unbekannter Eintrag: nichts passiert
    assert app.layout.slots[0].signals == [us[1]]


def test_file_combo_without_plots_and_existing_functions_untouched(env):
    app = env.app
    first, second, _third = _switch_runs(env)
    app._on_file_combo(None, "lauf_2.csv")
    assert "Noch keine Plots" in env.state.items[app.status]["value"] and not app.layout.slots
    check(env, first.channels[0])                            # bisherige Wege bleiben: Häkchen setzen
    assert app.layout.signals() == [first.channels[0]]
    app._close_dataset(None, None, first)                     # Datei schließen nimmt ihre Signale weg
    assert not app.layout.signals() and env.state.items[app.file_combo]["items"] == ["Alle Dateien", "lauf_2.csv", "lauf_3.mf4"]


def test_clear_all_plots_removes_graphs_and_layout(env):
    app = env.app
    first, *_rest = _switch_runs(env)
    env.state.items[app.matrix_input]["value"] = "3*2: 2, 1, 1+1"
    app._on_matrix()
    assert app.layout.merged
    app.layout.slots[0].title = "AC Spannung"
    app.layout.slots[0].comments.append([1.0, 2.0, "Notiz"])
    for channel in first.channels[:3]:
        check(env, channel)
    assert len(by_kind(env.state, "add_line_series")) >= 3
    app._clear_all_plots()
    assert app.layout.matrix is None and app.layout.spans is None and app.layout.slots == []   # Aufteilung weg
    assert env.state.items[app.matrix_input]["value"] == "" and len(app.datasets) == 3          # Dateien bleiben
    assert not by_kind(env.state, "add_plot") and not by_kind(env.state, "add_subplots")       # Plotbereich leer
    assert "Alle Plots und die Aufteilung gelöscht" in env.state.items[app.status]["value"]
    assert not any(env.state.items[b]["value"] for b in app.checkboxes.values())
    assert app.layout.target_names() == ["Automatisch"]
    check(env, first.channels[0])                              # danach wie neu: ein Signal = ein Graph
    assert len(app.layout.slots) == 1 and app.layout.slots[0].title == "" and not app.layout.slots[0].comments


def _right_click(env, ui, plot_pos):
    env.state.hovered = ui.plot
    env.state.plot_mouse = list(plot_pos)
    env.app._on_right_down()
    env.app._on_right_up()


def test_comment_fields_by_right_click(env):
    app = env.app
    app.open_files([env.a])
    wait(app)
    u, _i = app.datasets[0].channels
    check(env, u)
    ui = app.slot_ui[0]
    _right_click(env, ui, (20.0, 55.0))
    assert env.state.items["ctx_menu"]["show"] is True
    env.state.items[app.ctx_comment]["value"] = "Sprung\nnach Lastwechsel"
    app._ctx_add_comment()
    slot = app.layout.slots[0]
    assert slot.comments == [[20.0, 55.0, "Sprung\nnach Lastwechsel"]]
    notes = by_kind(env.state, "add_plot_annotation")
    assert len(notes) == 1 and notes[0]["parent"] == ui.plot and notes[0]["default_value"] == (20.0, 55.0)
    assert "Kommentar in Graph 1 eingefügt." in env.state.items[app.status]["value"]
    _right_click(env, app.slot_ui[0], (40.0, 10.0))                     # bearbeiten, verschieben, löschen
    assert len(app.ctx_comment_edits) == 1
    env.state.items[app.ctx_comment_edits[0]]["value"] = "Lastwechsel"
    app._ctx_edit_comment(None, None, 0)
    _right_click(env, app.slot_ui[0], (40.0, 10.0))
    app._ctx_move_comment(None, None, 0)
    assert slot.comments == [[40.0, 10.0, "Lastwechsel"]]
    assert by_kind(env.state, "add_plot_annotation")[0]["label"] == "Lastwechsel"
    spec = app._plot_spec(app.slot_ui[0], 0)                             # Report und Export zeigen sie
    assert spec.comments == [(40.0, 10.0, "Lastwechsel")]
    app._layout_changed()                                                 # Neuaufbau behält sie
    assert len(by_kind(env.state, "add_plot_annotation")) == 1
    _right_click(env, app.slot_ui[0], (0.0, 0.0))
    env.state.items[app.ctx_comment]["value"] = "   "                    # leerer Text: nichts
    app._ctx_add_comment()
    assert len(slot.comments) == 1
    _right_click(env, app.slot_ui[0], (0.0, 0.0))
    app._ctx_delete_comment(None, None, 0)
    assert slot.comments == [] and not by_kind(env.state, "add_plot_annotation")


def test_comments_saved_in_view_and_cleared_with_all_plots(env):
    from messgraph import session as sessions
    app = env.app
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    app.layout.slots[0].comments.append([5.0, 12.5, "Start"])
    data = app.session_dict()
    assert data["graphs"][0]["comments"] == [[5.0, 12.5, "Start"]]
    by_saved = {os.path.abspath(d.path): d for d in app.datasets}
    layout, _missing = sessions.restore_layout(data, by_saved)
    assert layout.slots[0].comments == [[5.0, 12.5, "Start"]]
    app._clear_all_plots()
    assert app.layout.slots == []


def test_comment_box_drawn_in_report_svg(tmp_path):
    import numpy as np
    from messgraph import plotexport
    spec = plotexport.PlotSpec("G", (0.0, 10.0), (0.0, 10.0), comments=[(5.0, 5.0, "Hinweis A"), (50.0, 5.0, "weg")],
                               series=[plotexport.SeriesSpec("s", np.arange(11.0), np.arange(11.0), (0, 0, 255), False)])
    path = tmp_path / "g.svg"
    files = plotexport.write_svg(str(path), [spec], (1, 1), "A4", "auto", "Kopf")
    text = "".join(open(p, encoding="utf-8").read() for p in files)
    assert "Hinweis A" in text and "weg" not in text                 # außerhalb des Ausschnitts nicht gezeichnet


def _contrast(a, b):
    def lum(c):
        def ch(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b_ = map(ch, c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_colour_schemes_sensible_combinations(env):
    import itertools
    themes = env.gui.themes
    assert len(themes.MODES) >= 7 and themes.MODES[:2] == ["Dunkel", "Hell"]
    roles = set(themes.PALETTE["Dunkel"])
    for mode, p in themes.PALETTE.items():
        assert set(p) == roles, mode                                       # alle Rollen vorhanden
        assert len(p["series"]) == 8 and len(p["cross"]) == 2
        assert _contrast(p["text"], p["window"]) >= 7, mode                # Text gut lesbar
        assert _contrast(p["text"], p["plot_bg"]) >= 7, mode               # Achsen und Titel im Plot
        for col in p["series"] + p["cross"]:                               # Linien heben sich vom Plot ab
            assert _contrast(col, p["plot_bg"]) >= 3, (mode, col)
        distance = min(sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 for a, b in itertools.combinations(p["series"], 2))
        assert distance >= 40, mode                                        # Linien untereinander unterscheidbar
        assert _contrast(p["grid"], p["plot_bg"]) < _contrast(p["series"][0], p["plot_bg"])   # Gitter zurückhaltend
        if mode not in ("Dunkel", "Hell"):                                 # Marker M1/M2 nicht wie eine Linie
            for col in p["cross"]:
                assert min(sum((x - y) ** 2 for x, y in zip(col, c)) ** 0.5 for c in p["series"]) >= 60, (mode, col)


def test_switch_through_all_colour_schemes(env):
    app = env.app
    themes = env.gui.themes
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    items = env.state.items[app.theme_combo]["items"]
    assert len(items) == len(themes.MODES) and "Nord" in items
    for mode in themes.MODES:
        app._on_theme(None, mode)
        assert app.mode == mode and app.settings["theme"] == mode
        series = next(iter(app.slot_ui[0].series.values()))
        assert env.state.items[series]["bound"] == app.series_themes[mode, 0]     # Linienfarbe des Schemas
    app._on_theme(None, "Papier")
    assert app.session_dict()["options"]["theme"] == "Papier"           # Schema gehört zur Ansicht


def _hint_texts(env):
    return [i["value"] for i in by_kind(env.state, "add_text") if str(i.get("value", "")).startswith("Hinweis: ")]


def test_file_hint_lists_only_real_names_and_follows_search(env):
    app = env.app
    p = env.tmp / "pruef.csv"
    p.write_text("Zeit;U_AC;Modus;SN;Temp\n" + "".join(f"{i};{230 + i};Lauf;;{20 + i}\n" for i in range(5)))
    app.open_files([str(p)])
    wait(app)
    assert _hint_texts(env) == ["Hinweis: Ohne Zahlenwerte, nicht angeboten: Modus, SN"]
    env.state.items[app.filter_input]["value"] = "mod"          # Suche: nur passende Namen
    app._refresh_channel_list()
    assert _hint_texts(env) == ["Hinweis: Ohne Zahlenwerte, nicht angeboten: Modus"]
    env.state.items[app.filter_input]["value"] = "temp"         # nichts Passendes: kein Hinweis
    app._refresh_channel_list()
    assert _hint_texts(env) == []


def test_bus_hint_names_present_frames_and_reflects_decoding(env):
    from messgraph.data_model import Channel, Dataset
    app = env.app
    raw = [Channel(name="LIN_Frame.ID", source="m.mf4", loader=lambda: (None, None, "")),
           Channel(name="LIN_Frame.DataBytes", source="m.mf4", loader=lambda: (None, None, ""))]
    ds = Dataset(path=str(env.tmp / "m.mf4"), channels=list(raw), extra={"bus_raw": True, "base": list(raw)})
    app.datasets.append(ds)
    app._refresh_channel_list()
    hints = _hint_texts(env)
    assert len(hints) == 1 and "LIN_Frame" in hints[0] and "CAN_DataFrame" not in hints[0]   # nur was es gibt
    ds.channels.append(Channel(name="Motordrehzahl (DBC G1)", source="m.mf4", loader=lambda: (None, None, "")))
    app._refresh_channel_list()
    assert _hint_texts(env) == ["Hinweis: Busrohdaten LIN_Frame: 1 Signale über die Datenbasen dekodiert."]


def test_comment_hover_and_drag_with_left_mouse(env):
    app = env.app
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    ui = app.slot_ui[0]
    app.layout.slots[0].comments.append([20.0, 100.0, "Test"])
    app._draw_comments(ui)
    note = ui.comment_items[0]
    env.state.rects[ui.plot] = ([400.0, 100.0], [800.0, 400.0])
    env.state.axis_limits[ui.x_axis] = [0.0, 100.0]
    env.state.axis_limits[ui.y_axis] = [0.0, 200.0]
    env.state.hovered = ui.plot
    env.state.plot_mouse = [60.0, 100.0]                       # neben dem Kommentar: kein Treffer
    app._poll_comment_drag()
    assert app.comment_hover is None
    app._on_left_down()
    assert app.comment_drag is None
    env.state.plot_mouse = [24.0, 110.0]                       # auf dem Kasten: hervorgehoben
    app._poll_comment_drag()
    assert app.comment_hover == note
    assert env.state.items[note]["color"][:3] == tuple(env.gui.themes.color(app.mode, "ok"))
    env.state.left_down = True                                 # greifen und ziehen
    app._on_left_down()
    assert app.comment_drag is not None and ui.x_axis in env.state.fixed_axes   # Graph wird nicht verschoben
    env.state.plot_mouse = [54.0, 60.0]
    app._poll_comment_drag()
    assert app.layout.slots[0].comments[0][:2] == [pytest.approx(50.0), pytest.approx(50.0)]   # Griffstelle bleibt
    assert env.state.items[note]["default_value"] == (pytest.approx(50.0), pytest.approx(50.0))
    env.state.left_down = False                                # loslassen
    app._poll_comment_drag()
    assert app.comment_drag is None and ui.x_axis not in env.state.fixed_axes
    assert "Kommentar verschoben." in env.state.items[app.status]["value"]
    assert app._plot_spec(ui, 0).comments == [(pytest.approx(50.0), pytest.approx(50.0), "Test")]


def test_double_click_opens_graph_in_detail_window_with_shared_functions(env):
    app = env.app
    app.open_files([env.a])
    wait(app)
    u, i = app.datasets[0].channels
    check(env, u)
    check(env, i)
    main = app.slot_ui[1]
    env.state.hovered = main.plot
    app._on_double_click()
    zoom = app.zoom_ui
    assert env.state.items["zoom_window"]["show"] is True and app.zoom_slot is main.slot
    assert zoom.slot is main.slot and zoom not in app.slot_ui                       # dasselbe GraphSlot-Objekt
    assert env.state.items[zoom.plot]["parent"] == app.zoom_plot_area
    assert env.state.items[app.zoom_title]["value"] == "Graph 2"
    assert "Graph 2 im Detailfenster." in env.state.items[app.status]["value"]
    # Marker aus dem Detailfenster: gelten überall, eigene Wertanzeige im Detailfenster
    app._set_cross(True)
    assert app.cross_on and env.state.items[app.cross_box]["value"] is True
    assert env.state.items[app.zoom_table_area]["show"] is True
    assert sum(1 for r in app.table_rows if r[0] is zoom) == 1 and ("zoom", "I", 0) in app.limit_boxes
    env.state.items[zoom.v_lines[0]]["value"] = 42.0                                # Marker im Detail ziehen
    app._poll_crosslines()
    assert main.slot.cross[0] == 42.0 and env.state.items[main.v_lines[0]]["value"] == 42.0
    # Grenze im Detailfenster: Linie und Eingabefeld auch im Plotbereich
    app._on_limit(None, "80", (zoom, i, 1))
    assert main.slot.limits[i] == [None, 80.0] and env.state.items[app.limit_boxes[(1, "I", 1)]]["value"] == "80"
    assert main.limit_series.get(i)
    # Kontextmenü im Detailfenster: Name und Kommentar gelten für den Graphen
    env.state.hovered = zoom.plot
    env.state.plot_mouse = [10.0, 50.0]
    app._on_right_down()
    app._on_right_up()
    assert app.ctx_slot is main.slot and app.ctx_from_zoom
    env.state.items[app.ctx_comment]["value"] = "im Detail"
    app._ctx_add_comment()
    notes = [n for n in by_kind(env.state, "add_plot_annotation") if n["label"] == "im Detail"]
    assert {n["parent"] for n in notes} == {zoom.plot, app.slot_ui[1].plot}             # in beiden Darstellungen
    # Drucken aus dem Detailfenster: dessen Ausschnitt
    env.state.axis_limits[zoom.x_axis] = [20.0, 30.0]
    app._open_export("one", app.zoom_slot, zoom=True)
    specs, grid = app._export_specs()
    assert grid == (1, 1) and specs[0].xlim == (20.0, 30.0) and specs[0].title == "Graph 2"
    app.exp_mode = "all"                                                             # alle Graphen: ohne Detail
    specs, _grid = app._export_specs()
    assert len(specs) == 2
    # Umbenennen über den Plotbereich: Detailfenster zieht mit; Signal entfernen: Graph weg -> Fenster zu
    app.layout.slots[1].title = "Strom"
    app._layout_changed()
    assert app.zoom_ui is not None and env.state.items[app.zoom_title]["value"] == "Strom"
    app.layout.remove(i)
    app._layout_changed()
    assert app.zoom_ui is None and env.state.items["zoom_window"]["show"] is False
    assert not any(r[0] is zoom for r in app.table_rows)


def test_detail_window_close_and_fit(env):
    app = env.app
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    app.open_zoom(app.layout.slots[0])
    zoom = app.zoom_ui
    env.state.axis_limits[zoom.y_axis] = [0.0, 1.0]
    app._zoom_fit()
    assert env.state.axis_limits[zoom.y_axis] != [0.0, 1.0] and zoom.x_axis in env.state.fits
    app.close_zoom()
    assert app.zoom_ui is None and app.zoom_slot is None and env.state.items["zoom_window"]["show"] is False
    env.state.hovered = app.slot_ui[0].plot                                       # erneut öffnen geht
    app._on_double_click()
    assert app.zoom_ui is not None
    app.set_language("English")                                                   # Sprachwechsel: bleibt offen
    assert app.zoom_ui is not None and env.state.items["zoom_window"]["show"] is True


def test_detail_window_with_active_markers_keeps_lines_in_data_range(env):
    app = env.app
    p = env.tmp / "zeit.csv"
    p.write_text("Timestamp,U\n" + "".join(f"2026-11-13 10:00:{i:02d},{230 + i}\n" for i in range(30)))
    app.open_files([str(p)])
    wait(app)
    app._on_date_axis(None, True)
    check(env, app.datasets[0].channels[0])
    env.state.items[app.cross_box]["value"] = True
    app._on_cross_toggle(None, True)                     # Marker schon im Plotbereich aktiv
    env.state.hovered = app.slot_ui[0].plot
    app._on_double_click()
    zoom = app.zoom_ui
    assert zoom is not None and zoom.time_axis
    lo, hi = app._data_range(zoom)
    assert lo > 1e9                                      # Datumsachse: X-Werte als Epoch
    for k in (0, 1):                                     # Linien im Datenbereich, nicht bei 0 (sonst Kurve unsichtbar)
        value = env.state.items[zoom.v_lines[k]]["default_value"]
        assert lo <= value <= hi
        assert env.state.items[zoom.v_lines[k]]["value"] == pytest.approx(app.layout.slots[0].cross[k])


def test_target_time_marks_rows_graphs_zoom_and_report(env):
    app = env.app
    themes = env.gui.themes
    app.open_files([env.a])
    wait(app)
    u, i = app.datasets[0].channels                       # U: 2 V/s bis 200 V bei 100 s; I: -1 A/s bis 0 A
    check(env, u)
    check(env, i)
    app._on_cross_toggle(None, True)
    ui_u, ui_i = app.slot_ui
    labels = [c.get("label") for c in by_kind(env.state, "add_table_column")][-14:]
    assert labels[labels.index("Y max") + 1] == "Zielzeit"            # neben Y max
    app._on_limit(None, "300", (ui_u, u, 1))                          # Grenze in 50 s erreicht
    box_u = app.target_boxes[(0, "U")]
    app._on_target(box_u, "1m", (ui_u, u))                            # Ziel 60 s > 50 s: verletzt
    assert ui_u.slot.targets[u] == 60
    table, row = app.table_row_pos[0]
    assert env.gui.dpg.highlighted[(table, row)][:3] == themes.alarm_row_bg(app.mode)
    assert env.state.items[ui_u.plot]["bound"] == app.alarm_themes[app.mode]          # Graph schwach rot
    assert env.state.items[ui_i.plot].get("bound") in (None, 0)
    assert "(Zielzeit 1m verletzt)" in env.state.items[app.table_preds[0][1]]["value"]
    app._on_target(box_u, "0,5m", (ui_u, u))                          # 30 s < 50 s: eingehalten
    assert (table, row) not in env.gui.dpg.highlighted and env.state.items[ui_u.plot]["bound"] == 0
    app._on_target(box_u, "2", (ui_u, u))                             # 2 h: verletzt
    app._on_target(box_u, "2x", (ui_u, u))                            # ungültig: bleibt
    assert ui_u.slot.targets[u] == 7200
    # auf alle Signale übertragen; I hat noch keine Grenze -> keine Bewertung
    app._target_to_all(None, None, (ui_u, u))
    assert ui_i.slot.targets[i] == 7200 and env.state.items[app.target_boxes[(1, "I")]]["value"] == "2h 0m"
    assert "für alle 2 Signale übernommen" in env.state.items[app.status]["value"]
    assert env.state.items[ui_i.plot].get("bound") in (None, 0)
    app._on_limit(None, "-10", (ui_i, i, 0))                          # jetzt auch I verletzt (10 s < 2 h)
    assert env.state.items[ui_i.plot]["bound"] == app.alarm_themes[app.mode]
    # Detailfenster: derselbe Zustand
    app.open_zoom(ui_u.slot)
    zoom = app.zoom_ui
    assert env.state.items[zoom.plot]["bound"] == app.alarm_themes[app.mode]
    assert any(pos[0] != table for pos in app.table_row_pos)          # eigene Wertanzeige, ebenfalls rot
    zt, zr = app.table_row_pos[-1]
    assert (zt, zr) in env.gui.dpg.highlighted
    assert env.state.items[app.target_boxes[("zoom", "U")]]["value"] == "2h 0m"
    # Report: Zielzeit-Spalte, Status, rote Zeilen und schwach roter Graph
    data = app._report_data("R", "", "")
    section = data.graphs[0]
    heading, headers, rows = section.tables[-1]
    assert headers[3] == "Zielzeit" and headers[-1] == "Zielzeit-Status"
    assert rows[0][3] == "2h 0m" and rows[0][-1] == "verletzt"
    assert section.alarm_keys == {"s0"} and section.spec.alarm
    from messgraph import report, report_html
    pdf = report.build_report(str(env.tmp / "r.pdf"), data)
    import re
    import zlib
    raw = open(pdf, "rb").read()
    content = b"".join(zlib.decompress(m) for m in re.findall(rb"stream\n(.*?)\nendstream", raw, re.S)
                       if m[:1] == b"x")
    assert b"1.000 0.804 0.804 rg" in content                          # rote Tabellenzeile im PDF
    html = open(report_html.build_html_report(str(env.tmp / "r.html"), data), encoding="utf-8").read()
    assert 'class="alarm"' in html and "#ffcdcd" in html
    # Farbschema wechseln: Hintergrund passt sich an
    app._on_theme(None, "Papier")
    assert env.state.items[ui_u.plot]["bound"] == app.alarm_themes["Papier"]
    # Marker aus: keine Bewertung, nichts hinterlegt
    app._on_cross_toggle(None, False)
    assert env.state.items[app.slot_ui[0].plot]["bound"] == 0 and not app._plot_spec(app.slot_ui[0], 0).alarm
    # Zielzeit wird gespeichert
    saved = app.session_dict()["graphs"][0]["signals"][0]
    assert saved["target"] == 7200


def test_alarm_colours_fit_every_scheme(env):
    themes = env.gui.themes
    for mode in themes.MODES:
        p = themes.PALETTE[mode]
        bg, row = themes.alarm_plot_bg(mode), themes.alarm_row_bg(mode)
        assert bg[0] > bg[1] and bg[0] > bg[2] or bg[0] - p["plot_bg"][0] > 5, mode    # rötlich
        assert sum((a - b) ** 2 for a, b in zip(bg, p["plot_bg"])) ** 0.5 >= 25, mode  # sichtbar anders
        for col in p["series"]:                                    # Linien bleiben gut sichtbar
            assert _contrast(col, bg) >= 3, (mode, col)
        for col in p["cross"]:
            assert _contrast(col, bg) >= 2.5, (mode, col)
        assert _contrast(p["text"], row) >= 4.5, mode              # Zeilentext bleibt lesbar


def test_regression_lines_dashed_in_signal_colour(env):
    import math
    import numpy as np
    from messgraph import plotexport
    app = env.app
    app.open_files([env.a])
    wait(app)
    u, i = app.datasets[0].channels                       # U = 2*t, I = 100 - t
    check(env, u)
    app._request_add(i, 0)                                 # beide in einem Graphen, I rechts
    app.layout.slots[0].right.add(i)
    app._layout_changed()
    ui = app.slot_ui[0]
    assert not ui.reg_series                               # erst auf Anforderung
    app._set_regression(True)
    assert app.reg_on and env.state.items[app.reg_box]["value"] is True and app.settings["regression_lines"]
    assert set(ui.reg_series) == {u, i}
    # keine eigenen Einträge im Signalspiegel: Kurve und Regressionslinie sind eine Serie
    assert ui.reg_series[u] == ui.series[u] and ui.reg_series[i] == ui.series[i]
    assert len(by_kind(env.state, "add_line_series")) == len([c for c in ui.series])
    xs, ys = env.state.items[ui.series[u]]["value"]
    curve_x, curve_y = ui.curve[u]
    assert xs[:len(curve_x)] == curve_x and math.isnan(xs[len(curve_x)])  # Kurve, Lücke, Striche
    rx, ry = ui.reg_points[u]
    assert sum(1 for v in rx if isinstance(v, float) and math.isnan(v)) == app.REG_DASHES       # Lücken = Striche
    pairs = [(x, y) for x, y in zip(rx, ry) if not math.isnan(x)]
    assert all(y == pytest.approx(2 * x) for x, y in pairs)                                  # y = 2 x
    assert pairs[0][0] == pytest.approx(0.0) and max(x for x, _ in pairs) < 100.0
    assert xs[len(curve_x) + 1:] == list(rx)
    # Signal I im Signalspiegel deaktiviert: Linie verschwindet mit (dieselbe Serie), nicht im Export
    env.state.items[ui.series[i]]["show"] = False
    assert [r[-1] for r in app._plot_spec(ui, 0).regressions] == ["s0"]
    env.state.items[ui.series[i]]["show"] = True
    # Zoom: Striche werden für den Ausschnitt neu berechnet, Kurve bleibt vorn
    env.state.axis_limits[ui.x_axis] = [40.0, 60.0]
    app._poll_reg_dashes()
    finite = [x for x in ui.reg_points[u][0] if not math.isnan(x)]
    assert min(finite) == pytest.approx(40.0) and max(finite) < 60.0
    assert env.state.items[ui.series[u]]["value"][0][:len(curve_x)] == curve_x
    # Farbe ändern: Gerade zieht mit
    app.ctx_slot = app.layout.slots[0]
    app._ctx_color(None, (1.0, 0.0, 0.0, 1.0), u)
    assert env.state.items[ui.reg_series[u]]["bound"] == env.state.items[ui.series[u]]["bound"]
    # Druck/Export/Report: gestrichelt in der Signalfarbe
    spec = app._plot_spec(ui, 0)
    reg = {r[-1]: r for r in spec.regressions}
    assert reg["s0"][:4] == (pytest.approx(0.0), pytest.approx(0.0), pytest.approx(100.0), pytest.approx(200.0))
    assert reg["s0"][4] == (255, 0, 0) and reg["s1"][5] is True
    files = plotexport.write_svg(str(env.tmp / "r.svg"), [spec], (1, 1), "A4", "auto", "Kopf")
    svg = open(files[0], encoding="utf-8").read()
    assert 'stroke="#ff0000" stroke-width="0.90" stroke-linejoin="round" stroke-dasharray="5,3"' in svg
    # Detailfenster: eigene Striche, Häkchen dort wirkt überall
    app.open_zoom(app.layout.slots[0])
    assert app.zoom_ui.reg_series and env.state.items[app.zoom_reg]["value"] is True
    app._set_regression(False)
    assert not ui.reg_series and not app.zoom_ui.reg_series and not ui.reg_points
    assert env.state.items[ui.series[u]]["value"][0] == ui.curve[u][0]      # nur noch die Kurve
    assert env.state.items[app.reg_box]["value"] is False and app._plot_spec(ui, 0).regressions == []
    assert app.session_dict()["options"]["regression_lines"] is False


def test_yaml_limit_config_with_modes_and_manual_fallback(env):
    from pathlib import Path
    demo = Path(__file__).resolve().parent.parent / "demo_data"
    app = env.app
    app.open_files([str(demo / "demo_pruefstand.asc")])
    wait(app)
    ds = app.datasets[0]
    by = {c.name: c for c in ds.channels}
    for name in ("AC_V_L1", "DUT_TS_01", "LVDC_I"):
        check(env, by[name])
    app._on_cross_toggle(None, True)
    ui_v, ui_t, ui_i = app.slot_ui
    app._on_limit(None, "260", (ui_v, by["AC_V_L1"], 1))                       # manuelle Werte
    app._on_limit(None, "20", (ui_i, by["LVDC_I"], 1))
    app.layout.slots[1].targets[by["DUT_TS_01"]] = 7200
    assert app._limits_for(ui_v.slot, by["AC_V_L1"]) == [None, 260.0]
    # Konfiguration laden: Modes im Auswahlfeld, noch kein Mode -> manuelle Werte
    assert app.load_limit_config(str(demo / "demo_grenzen.yaml"))
    assert env.state.items[app.mode_combo]["items"] == ["(manuell)", "Interface", "EU_AC_3ph_11kW_800V",
                                                       "EU_AC_3ph_22kW_800V"]
    assert "3 Modes" in env.state.items[app.status]["value"]
    assert app._limits_for(ui_v.slot, by["AC_V_L1"]) == [None, 260.0]
    # Mode wählen: zugeordnete Signale aus der YAML, nicht zugeordnete (LVDC_I) manuell
    app.set_limit_mode("EU_AC_3ph_11kW_800V")
    assert "9 Signalen" in env.state.items[app.status]["value"] and "8 von 9" in env.state.items[app.status]["value"]
    assert app._limits_for(ui_v.slot, by["AC_V_L1"]) == [207.0, 253.0]
    assert app._limits_for(ui_i.slot, by["LVDC_I"]) == [None, 20.0]
    box = app.limit_boxes[(0, "AC_V_L1", 1)]
    assert env.state.items[box]["value"] == "253" and env.state.items[box].get("enabled", True) is True   # editierbar
    assert env.state.items[app.limit_boxes[(2, "LVDC_I", 1)]].get("enabled", True) is True
    assert env.state.items[app.slot_ui[0].limit_series[by["AC_V_L1"]][1]]["value"][1] == [253.0, 253.0]
    # steps als Zahl: Ziel 600 Schritte für DUT_TS_01 (Grenze 80 °C)
    ui_t = app.slot_ui[1]
    target = app._target_for(ui_t.slot, by["DUT_TS_01"])
    assert target == ("steps", 600.0, "yaml")
    assert env.state.items[app.target_boxes[(1, "DUT_TS_01")]]["value"] == "600"
    state = app._violation(ui_t, by["DUT_TS_01"])
    dt = app._sample_step(by["DUT_TS_01"])
    m = app._regression(by["DUT_TS_01"])
    remaining = (80.0 - float(by["DUT_TS_01"].y[-1])) / m / dt
    assert state == (remaining < 600, pytest.approx(remaining))
    # steps als Zeit (22 kW: "2h 30m")
    app.set_limit_mode("EU_AC_3ph_22kW_800V")
    assert app._target_for(app.slot_ui[1].slot, by["DUT_TS_01"]) == ("s", 9000.0, "yaml")
    assert env.state.items[app.target_boxes[(1, "DUT_TS_01")]]["value"] == "2h 30m"
    # Mode ohne steps (Interface) oder ohne Zuordnung: manuelle Zielzeit
    app.set_limit_mode("Interface")
    assert app._target_for(ui_t.slot, by["DUT_TS_01"]) == ("s", 7200, "manual")
    assert app._limits_for(ui_v.slot, by["AC_V_L1"]) == [None, 260.0]
    # Ansicht/Projekt merken sich Konfiguration und Mode
    app.set_limit_mode("EU_AC_3ph_22kW_800V")
    options = app.session_dict()["options"]
    assert options["limit_config"].endswith("demo_grenzen.yaml") and options["limit_mode"] == "EU_AC_3ph_22kW_800V"
    data = app._report_data("R", "", "")
    assert any(k == "Grenzwert-Konfiguration" and "EU_AC_3ph_22kW_800V" in v and "steps 2h 30m" in v
               for k, v in data.settings)
    limit_table = data.graphs[0].tables[-1][2]
    assert limit_table[0][1] == "220" and limit_table[0][2] == "240" and limit_table[0][3].endswith("(YAML)")
    app.close_limit_config()
    assert app.limit_cfg is None and app._limits_for(ui_v.slot, by["AC_V_L1"]) == [None, 260.0]
    assert env.state.items[app.mode_combo]["items"] == ["(manuell)"]
    app._apply_options(options)                                                # Ansicht laden: wieder aktiv
    assert app.limit_cfg is not None and app.cfg_mode == "EU_AC_3ph_22kW_800V"
    bad = tmp = env.tmp / "kaputt.yaml"
    tmp.write_text("limits: [", encoding="utf-8")
    assert not app.load_limit_config(str(bad)) and app.limit_cfg is not None   # Fehler: bisherige bleibt
    assert "gültige YAML" in env.state.items[app.status]["value"]


def test_limit_configurator_create_edit_live_save_load(env):
    from pathlib import Path
    from messgraph import limitconfig
    demo = Path(__file__).resolve().parent.parent / "demo_data"
    app = env.app
    app.open_files([str(demo / "demo_pruefstand.asc")])
    wait(app)
    by = {c.name: c for c in app.datasets[0].channels}
    check(env, by["DUT_TS_01"])
    check(env, by["LVDC_I"])
    app._on_cross_toggle(None, True)
    ui_t, ui_i = app.slot_ui
    app._on_limit(None, "30", (ui_i, by["LVDC_I"], 1))                          # manuell
    # Konfigurator ohne Konfiguration: neue anlegen, Mode "Standard" wirkt sofort (keine Auto-Auswertung)
    app.open_limit_editor()
    assert env.state.items["limit_editor"]["show"] is True
    assert app.limit_cfg is not None and app.cfg_mode == "Standard" and app.le_edit_mode == "Standard"
    assert "nicht gespeichert" in env.state.items[app.le_file]["value"]
    assert set(app.le_widgets) >= {"DUT_TS_01", "LVDC_I", "AC_V_L1"}            # Signale der geladenen Dateien
    # Grenze eintragen: Signal wird aktiv, wirkt sofort im Programm (Linie, gesperrtes Feld)
    box, lower, upper = app.le_widgets["DUT_TS_01"]
    app._le_edit(upper, "80", ("DUT_TS_01", "upper"))
    assert env.state.items[box]["value"] is True
    assert app._limits_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == [None, 80.0]
    assert env.state.items[app.limit_boxes[(0, "DUT_TS_01", 1)]]["value"] == "80"
    assert app._limits_for(app.slot_ui[1].slot, by["LVDC_I"]) == [None, 30.0]   # nicht konfiguriert: manuell
    app._le_edit(lower, "12,5", ("DUT_TS_01", "lower"))                          # Komma
    app._le_edit(lower, "1-", ("DUT_TS_01", "lower"))                            # unvollständig: bleibt
    assert app._limits_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == [12.5, 80.0]
    assert env.state.items[app.le_file]["value"].endswith("*")
    # steps eintragen: Ziel aus der Konfiguration
    app._le_steps(None, "500")
    assert app._target_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == ("steps", 500.0, "yaml")
    # deaktivieren: wieder manuell
    app._le_edit(box, False, ("DUT_TS_01", "enabled"))
    assert app._limits_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == [None, None]
    app._le_edit(box, True, ("DUT_TS_01", "enabled"))
    # Vorschlag aus den Daten für aktive Signale ohne Grenzen
    env.state.items[app.le_filter]["value"] = "HVDC_V"
    app._le_rows()
    assert list(app.le_widgets) == ["HVDC_V"]
    app._le_bulk_enable(True)
    app._le_suggest()
    lo, hi = app.limit_cfg.modes["Standard"].signals["HVDC_V"]
    data = by["HVDC_V"].y[np.isfinite(by["HVDC_V"].y)]
    span = float(data.max() - data.min())
    assert lo == pytest.approx(float(data.min()) - 0.1 * span) and hi == pytest.approx(float(data.max()) + 0.1 * span)
    # zweiter Mode, umbenennen, im Programm verwenden
    env.state.items[app.le_mode_name]["value"] = "Heizen"
    app._le_mode_action("copy")
    assert app.le_edit_mode == "Heizen" and env.state.items[app.mode_combo]["items"] == ["(manuell)", "Standard", "Heizen"]
    app._le_edit(upper, "60", ("DUT_TS_01", "upper"))
    assert app._limits_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == [12.5, 80.0]    # Programm: noch Standard
    app._le_use()
    assert app.cfg_mode == "Heizen" and app._limits_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == [12.5, 60.0]
    env.state.items[app.le_mode_name]["value"] = "Heizen 800V"
    app._le_mode_action("rename")
    assert app.cfg_mode == "Heizen 800V" and app.limit_cfg.mode_names() == ["Standard", "Heizen 800V"]
    # speichern mit Namen, danach laden
    target = env.tmp / "meine_grenzen.yaml"
    app._le_save()                                                               # neu: fragt nach dem Namen
    assert env.state.items["save_dialog"]["show"] is True
    env.state.items[app.save_path]["value"] = str(target)
    app._save_dialog_ok()
    assert target.is_file() and app.limit_cfg.path == str(target) and not app.limit_cfg.modified
    assert "gespeichert" in env.state.items[app.status]["value"] and app.settings["limit_config"] == str(target)
    saved = limitconfig.load(str(target))
    assert saved.modes["Heizen 800V"].signals["DUT_TS_01"] == (12.5, 60.0) and saved.modes["Standard"].steps == 500
    app._le_edit(upper, "65", ("DUT_TS_01", "upper"))                           # Speichern: gleicher Name
    app._le_save()
    assert limitconfig.load(str(target)).modes["Heizen 800V"].signals["DUT_TS_01"] == (12.5, 65.0)
    app.close_limit_config()
    assert app._limits_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == [None, None]
    app._le_load(str(target))                                                    # über den Konfigurator laden
    assert app.limit_cfg.mode_names() == ["Standard", "Heizen 800V"]
    app.set_limit_mode("Heizen 800V")
    assert app._limits_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == [12.5, 65.0]
    # Mode löschen, der im Programm gilt: zurück auf manuell
    app.open_limit_editor()
    app._le_select_mode("Heizen 800V")
    app._le_mode_action("delete")
    assert app.cfg_mode is None and app.le_edit_mode == "Standard"
    env.state.items[app.le_mode_name]["value"] = "Standard"
    app._le_mode_action("add")                                                   # doppelter Name: Meldung
    assert "gibt es schon" in env.state.items[app.status]["value"]


def test_configurator_suggest_for_all_modes_same_percent(env):
    from pathlib import Path
    from messgraph import limitconfig
    demo = Path(__file__).resolve().parent.parent / "demo_data"
    app = env.app
    app.open_files([str(demo / "demo_pruefstand.asc")])
    wait(app)
    by = {c.name: c for c in app.datasets[0].channels}
    app.open_limit_editor()
    cfg = app.limit_cfg
    cfg.modes["AC_615V"] = limitconfig.new_config("AC_615V").modes["AC_615V"]
    cfg.modes["DC_800V"] = limitconfig.new_config("DC_800V").modes["DC_800V"]
    cfg.modes["Leer"] = limitconfig.new_config("Leer").modes["Leer"]
    for mode in ("Standard", "AC_615V", "DC_800V"):
        cfg.modes[mode].set_entry("HVDC_V", True, None, None)
    cfg.modes["Standard"].set_entry("LVDC_I", True, 1.0, 2.0)                  # hat Grenzen: bleibt
    cfg.modes["AC_615V"].set_entry("DUT_TS_01", False, None, None)              # inaktiv: bleibt ohne Grenzen
    # Analyse je Mode (Auto, alle Dateien des Modes); DC_800V ohne Analyse -> geladene Dateien
    app.auto_mode_stats = {"AC_615V": {"HVDC_V": ("V", ["a.csv", "b.csv"], 600.0, 630.0),
                                       "DUT_TS_01": ("°C", ["a.csv"], 20.0, 40.0)}}
    env.state.items[app.le_margin]["value"] = 20.0                              # Prozent gilt für beide Varianten
    app._le_suggest_all()
    assert cfg.modes["AC_615V"].signals["HVDC_V"] == (pytest.approx(594.0), pytest.approx(636.0))
    off = cfg.modes["AC_615V"].entries["DUT_TS_01"]
    assert off.lower is None and off.upper is None
    data = by["HVDC_V"].y[np.isfinite(by["HVDC_V"].y)]
    lo, hi, span = float(data.min()), float(data.max()), float(data.max() - data.min())
    for mode in ("Standard", "DC_800V"):
        assert cfg.modes[mode].signals["HVDC_V"] == (pytest.approx(lo - 0.2 * span), pytest.approx(hi + 0.2 * span))
    assert cfg.modes["Standard"].signals["LVDC_I"] == (1.0, 2.0)
    text = env.state.items[app.status]["value"]
    assert "3 Signale in 3 Modes" in text and "(20 %)" in text and cfg.modified
    # Einzel-Mode mit demselben Prozentwert
    cfg.modes["AC_615V"].set_entry("HVDC_V", True, None, None)
    app._le_select_mode("Standard")
    cfg.modes["Standard"].set_entry("HVDC_V", True, None, None)
    env.state.items[app.le_filter]["value"] = "HVDC_V"
    app._le_rows()
    app._le_suggest()
    assert cfg.modes["Standard"].signals["HVDC_V"] == (pytest.approx(lo - 0.2 * span), pytest.approx(hi + 0.2 * span))
    still = cfg.modes["AC_615V"].entries["HVDC_V"]
    assert still.lower is None and still.upper is None                          # nur dieser Mode
    # ohne geladene Dateien und ohne Analyse: Hinweis
    app.datasets.clear()
    app._le_suggest_all()
    assert "Ohne Daten:" in env.state.items[app.status]["value"] and "Leer" in env.state.items[app.status]["value"]


def test_configurator_steps_as_count_or_time(env):
    from pathlib import Path
    demo = Path(__file__).resolve().parent.parent / "demo_data"
    app = env.app
    app.open_files([str(demo / "demo_pruefstand.asc")])
    wait(app)
    by = {c.name: c for c in app.datasets[0].channels}
    check(env, by["DUT_TS_01"])
    app._on_cross_toggle(None, True)
    app.open_limit_editor()
    app._le_edit(None, "80", ("DUT_TS_01", "upper"))
    slot = app.slot_ui[0].slot
    app._le_steps(None, "500")                                                   # Zahl: Schritte
    assert app._target_for(slot, by["DUT_TS_01"]) == ("steps", 500.0, "yaml")
    assert env.state.items[app.le_steps_unit]["value"] == "= 500 Schritte"
    assert env.state.items[app.target_boxes[(0, "DUT_TS_01")]]["value"] == "500"
    app._le_steps(None, "1h 30m 15s")                                            # Zeit
    assert app._target_for(slot, by["DUT_TS_01"]) == ("s", 5415.0, "yaml")
    assert env.state.items[app.le_steps_unit]["value"] == "= Zeit 1h 30m 15s"
    assert env.state.items[app.target_boxes[(0, "DUT_TS_01")]]["value"] == "1h 30m 15s"
    app._le_steps(None, "1h 3")                                                  # unvollständig: bleibt
    assert app._target_for(slot, by["DUT_TS_01"]) == ("s", 5415.0, "yaml")
    assert "unvollständig" in env.state.items[app.le_steps_unit]["value"]
    app._le_steps(None, "")                                                      # leer: kein Ziel aus der YAML
    assert app._target_for(slot, by["DUT_TS_01"]) is None
    app._on_target(None, "90s", (app.slot_ui[0], by["DUT_TS_01"]))               # manuell geht auch mit Sekunden
    assert slot.targets[by["DUT_TS_01"]] == 90


def test_marker_table_edits_write_back_into_loaded_yaml(env):
    import shutil
    from pathlib import Path
    from messgraph import limitconfig
    demo = Path(__file__).resolve().parent.parent / "demo_data"
    config_path = env.tmp / "grenzen.yaml"
    shutil.copy(demo / "demo_grenzen.yaml", config_path)
    app = env.app
    app.open_files([str(demo / "demo_pruefstand.asc")])
    wait(app)
    by = {c.name: c for c in app.datasets[0].channels}
    check(env, by["DUT_TS_01"])
    check(env, by["LVDC_I"])
    app._on_cross_toggle(None, True)
    app.load_limit_config(str(config_path), "EU_AC_3ph_11kW_800V")
    assert env.state.items[app.cfg_save]["show"] is True
    ui_t, ui_i = app.slot_ui
    # Grenze eines YAML-Signals in der Wertanzeige ändern: geht in den Mode, Linie folgt sofort
    box = app.limit_boxes[(0, "DUT_TS_01", 1)]
    app._on_limit(box, "85", (ui_t, by["DUT_TS_01"], 1))
    mode = app.limit_cfg.modes["EU_AC_3ph_11kW_800V"]
    assert mode.signals["DUT_TS_01"] == (0.0, 85.0) and app.limit_cfg.modified
    assert env.state.items[app.slot_ui[0].limit_series[by["DUT_TS_01"]][1]]["value"][1] == [85.0, 85.0]
    assert "* geändert" in env.state.items[app.cfg_label]["value"]
    assert ui_t.slot.limits.get(by["DUT_TS_01"]) is None                  # manuelle Werte unberührt
    app._on_limit(box, "8-", (ui_t, by["DUT_TS_01"], 1))                   # unvollständig: bleibt
    assert mode.signals["DUT_TS_01"] == (0.0, 85.0)
    # steps in der Wertanzeige: gilt für den Mode
    target = app.target_boxes[(0, "DUT_TS_01")]
    assert env.state.items[target]["value"] == "600"
    app._on_target(target, "3h 20m", (ui_t, by["DUT_TS_01"]))
    assert mode.target == ("s", 12000.0)
    assert app._target_for(ui_t.slot, by["DUT_TS_01"]) == ("s", 12000.0, "yaml")
    # nicht konfiguriertes Signal: Grenzen manuell, steps des Modes gilt trotzdem (eine Einstellung je Mode)
    app._on_limit(None, "25", (ui_i, by["LVDC_I"], 1))
    assert ui_i.slot.limits[by["LVDC_I"]] == [None, 25.0] and "LVDC_I" not in mode.signals
    assert app._target_for(ui_i.slot, by["LVDC_I"]) == ("s", 12000.0, "yaml")
    assert env.state.items[app.target_boxes[(1, "LVDC_I")]]["value"] == "3h 20m"
    app._on_target(app.target_boxes[(1, "LVDC_I")], "3h 30m", (ui_i, by["LVDC_I"]))      # Änderung hier gilt überall
    assert mode.target == ("s", 12600.0) and env.state.items[target]["value"] == "3h 30m"
    app._on_target(target, "3h 20m", (ui_t, by["DUT_TS_01"]))
    assert env.state.items[app.target_boxes[(1, "LVDC_I")]]["value"] == "3h 20m"
    # offener Konfigurator zeigt die Änderung
    app.open_limit_editor()
    app._on_limit(box, "90", (app.slot_ui[0], by["DUT_TS_01"], 1))
    assert env.state.items[app.le_widgets["DUT_TS_01"][2]]["value"] == "90"
    # zurück in die geladene YAML schreiben
    app.save_limit_config_back()
    assert not app.limit_cfg.modified and "gespeichert" in env.state.items[app.status]["value"]
    saved = limitconfig.load(str(config_path))
    assert saved.modes["EU_AC_3ph_11kW_800V"].signals["DUT_TS_01"] == (0.0, 90.0)
    assert saved.modes["EU_AC_3ph_11kW_800V"].target == ("s", 12000.0)
    assert saved.modes["EU_AC_3ph_22kW_800V"].signals["HVDC_V"] == (800.0, 815.0)   # anderes bleibt
    assert "steps: 3h 20m" in config_path.read_text(encoding="utf-8")
    assert "* geändert" not in env.state.items[app.cfg_label]["value"]
    # beide Grenzen leeren: Signal fällt auf die manuellen Werte zurück
    app._on_limit(box, "", (app.slot_ui[0], by["DUT_TS_01"], 0))
    app._on_limit(box, "", (app.slot_ui[0], by["DUT_TS_01"], 1))
    assert app._config_limits(by["DUT_TS_01"]) is None
    assert app._target_for(app.slot_ui[0].slot, by["DUT_TS_01"]) == ("s", 12000.0, "yaml")   # steps gilt weiter


def test_mode_steps_apply_to_every_signal_in_marker_table(env):
    from pathlib import Path
    demo = Path(__file__).resolve().parent.parent / "demo_data"
    app = env.app
    app.open_files([str(demo / "demo_pruefstand.asc")])
    wait(app)
    by = {c.name: c for c in app.datasets[0].channels}
    names = ("AC_V_L1", "LVDC_I", "AC_I_L1", "DUT_TS_01")                       # zwei mit, zwei ohne YAML-Eintrag
    for name in names:
        check(env, by[name])
    app._on_cross_toggle(None, True)
    app.layout.slots[1].targets[by["LVDC_I"]] = 60                              # manuelle Zielzeit
    app.load_limit_config(str(demo / "demo_grenzen.yaml"), "EU_AC_3ph_22kW_800V")   # steps: 2h 30m
    for index, name in enumerate(names):
        assert app._target_for(app.slot_ui[index].slot, by[name]) == ("s", 9000.0, "yaml"), name
        assert env.state.items[app.target_boxes[(index, name)]]["value"] == "2h 30m", name
    hidden = [b for b in by_kind(env.state, "add_button") if b.get("label") == "Alle"
              and b.get("callback") == app._target_to_all]
    assert hidden and all(b.get("show") is False for b in hidden)           # "Alle" unnötig: steps gilt für alle
    app.set_limit_mode("Interface")                                         # Mode ohne steps: wieder manuell
    assert app._target_for(app.slot_ui[1].slot, by["LVDC_I"]) == ("s", 60, "manual")
    assert app._target_for(app.slot_ui[2].slot, by["AC_I_L1"]) is None
    assert env.state.items[app.target_boxes[(1, "LVDC_I")]]["value"] == "1m"


def test_target_reaches_every_row_with_same_signal_from_several_files(env):
    app = env.app
    first, second, _third = _switch_runs(env)
    us = [c for d in (first, second) for c in d.channels if c.name == "U"]
    ts = [c for d in (first, second) for c in d.channels if c.name == "T"]
    for channel in us:                                       # U aus zwei Dateien in einem Graphen
        app._request_add(channel, None if not app.layout.slots else 0)
    for channel in ts:                                       # T aus zwei Dateien in einem zweiten Graphen
        app._request_add(channel, 1 if len(app.layout.slots) > 1 else None)
    app._on_cross_toggle(None, True)
    rows = [(ui, c) for ui in app.slot_ui for c in ui.slot.signals]
    assert len(rows) == 4 and len(app.target_box_list) == 4                 # jede Zeile hat ihr Feld
    assert len(app.target_boxes) == 2                                       # (nach Name wären es nur zwei)
    # manuell mit "Alle": wirklich jede Zeile
    ui0, u0 = rows[0]
    app._on_target(app.target_box_list[0][2], "5m", (ui0, u0))
    app._target_to_all(None, None, (ui0, u0))
    assert [env.state.items[b]["value"] for _u, _c, b in app.target_box_list] == ["5m"] * 4
    # Konfiguration mit steps: jede Zeile zeigt und übernimmt denselben Wert
    p = env.tmp / "g.yaml"
    p.write_text("limits:\n  modes:\n    A:\n      steps: 3m\n      signals:\n        U: {enabled: true, lower: 800, "
                 "upper: 2400}\n", encoding="utf-8")
    app.load_limit_config(str(p), "A")
    assert [env.state.items[b]["value"] for _u, _c, b in app.target_box_list] == ["3m"] * 4
    sender = app.target_box_list[2][2]
    ui2, c2 = app.target_box_list[2][:2]
    app._on_target(sender, "5m", (ui2, c2))                                  # in einer T-Zeile geändert
    others = [env.state.items[b]["value"] for _u, _c, b in app.target_box_list if b != sender]
    assert others == ["5m"] * 3
    assert all(app._target_for(ui.slot, c) == ("s", 300.0, "yaml") for ui, c in rows)
    # YAML-Grenze in einer U-Zeile: beide U-Zeilen (beide Dateien) zeigen den neuen Wert
    u_boxes = [b for ui, c, k, b in app.limit_box_list if c.name == "U" and k == 1]
    assert len(u_boxes) == 2
    app._on_limit(u_boxes[0], "2500", (rows[0][0], rows[0][1], 1))
    assert env.state.items[u_boxes[1]]["value"] == "2500"
    # manuelle Grenze bleibt je Signal (T aus Datei 1 ändert T aus Datei 2 nicht)
    t_boxes = [(ui, c, b) for ui, c, k, b in app.limit_box_list if c.name == "T" and k == 1]
    app._on_limit(t_boxes[0][2], "40", (t_boxes[0][0], t_boxes[0][1], 1))
    assert t_boxes[0][0].slot.limits[t_boxes[0][1]] == [None, 40.0]
    assert t_boxes[1][1] not in t_boxes[1][0].slot.limits


def test_graph_options_menu_and_regression_method(env):
    app = env.app
    # Grenzwert- und Berechnungs-Einträge stehen jetzt unter Graph-Optionen, nicht mehr unter Datei
    labels = {i.get("label"): i.get("parent") for i in by_kind(env.state, "add_menu_item")}
    for label in ("Grenzwert-Konfiguration laden (*.yaml)...", "Grenzwert-Konfigurator...",
                  "Grenzwert-Konfiguration entfernen", "Berechnungen laden (*.def)...", "Berechnungen speichern (*.def)..."):
        assert labels[label] == app.graph_menu, label
    assert labels["Dateien öffnen..."] == app.file_menu
    methods = [i["label"] for i in by_kind(env.state, "add_menu_item") if i.get("parent") == app.graph_menu
               and i.get("user_data") in env.gui.REG_METHODS]
    assert len(methods) == 4 and methods[1] == "(2) Minimale Abstandsquadrate (orthogonal)"
    # Daten mit Ausreißern: Theil-Sen ändert Drift, Prognose und Regressionslinie
    p = env.tmp / "drift.csv"
    p.write_text("t;V\n" + "".join(f"{i};{1000 if i == 5 else (-900 if i == 30 else 2 * i)}\n" for i in range(50)))
    app.open_files([str(p)])
    wait(app)
    channel = app.datasets[0].channels[0]
    check(env, channel)
    app._on_cross_toggle(None, True)
    app._set_regression(True)
    assert env.state.items[app.reg_menu_item]["value"] is True              # Menü und Häkchen gleich
    ols = app._regression(channel)
    line = app.slot_ui[0].reg_series[channel]
    item = app.reg_method_items["theilsen"]
    env.state.items[item]["callback"](item, True, "theilsen")               # Klick im Menü
    assert app.reg_method == "theilsen" and app.settings["regression_method"] == "theilsen"
    assert app._regression(channel) == pytest.approx(2.0) and abs(ols - 2.0) > 0.1
    assert env.state.items[item]["value"] is True and env.state.items[app.reg_method_items["ols"]]["value"] is False
    assert "Drift-Regression: (3) Robuste Regression (Theil-Sen)" in env.state.items[app.status]["value"]
    xs, ys = app.slot_ui[0].reg_points[channel]
    pairs = [(x, y) for x, y in zip(xs, ys) if x == x]
    assert all(y == pytest.approx(2 * x) for x, y in pairs)                # Linie folgt der Methode
    reg_cell = [r for r in app.table_rows if r[1] is channel][0][2]
    assert any("2" in str(env.state.items[c].get("value", "")) for c in reg_cell)
    spec_reg = app._plot_spec(app.slot_ui[0], 0).regressions[0]
    assert (spec_reg[3] - spec_reg[1]) / (spec_reg[2] - spec_reg[0]) == pytest.approx(2.0)
    data = app._report_data("R", "", "")
    assert ("Drift-Regression", "(3) Robuste Regression (Theil-Sen)") in data.settings
    assert app.session_dict()["options"]["regression_method"] == "theilsen"
    app.set_regression_method("ols", quiet=True)
    app._apply_options({"regression_method": "tls"})                         # Ansicht laden
    assert app.reg_method == "tls" and env.state.items[app.reg_method_items["tls"]]["value"] is True


def test_regression_number_in_menu_and_column_switches_dynamically(env):
    app = env.app
    app.open_files([env.a])
    wait(app)
    check(env, app.datasets[0].channels[0])
    app._on_cross_toggle(None, True)
    menu = [i["label"] for i in by_kind(env.state, "add_menu_item") if i.get("user_data") in env.gui.REG_METHODS]
    assert [m.split(")")[0] + ")" for m in menu] == ["(1)", "(2)", "(3)", "(4)"]
    def column():
        heads = [c.get("label") for c in by_kind(env.state, "add_table_column") if c.get("parent") is not None]
        return [h for h in heads if str(h).lower().startswith("drift (regression")]
    assert column() == ["Drift (Regression 1)"]
    for method, number in (("tls", 2), ("theilsen", 3), ("recent", 4), ("ols", 1)):
        app.set_regression_method(method)                         # Umschalten: Spalte sofort neu beschriftet
        assert column() == [f"Drift (Regression {number})"]
    app.open_zoom(app.layout.slots[0])                            # Detailfenster: gleiche Beschriftung
    app.set_regression_method("theilsen")
    assert column() == ["Drift (Regression 3)"] * 2
    data = app._report_data("R", "", "")
    assert data.graphs[0].tables[0][1][-1] == "Drift (Regression 3)"
    app.set_language("English")
    assert column() == ["Drift (regression 3)"] * 2


def test_toolbar_two_compact_rows_with_appearance_popup(env):
    app = env.app
    rows = env.state.items[app.toolbar_group]["children"]
    assert rows == [app.toolbar_row1, app.toolbar_row2]                 # zwei statt drei Zeilen
    row1 = env.state.items[app.toolbar_row1]["children"]
    row2 = env.state.items[app.toolbar_row2]["children"]
    assert row1.index(app.file_combo) < row1.index(app.matrix_input) < row1.index(app.clear_plots_button)
    assert row2.index(app.cross_box) < row2.index(app.link_box) < row2.index(app.cmp_button) < row2.index(app.view_button)
    popup = env.state.items["view_popup"]
    assert popup["kind"] == "popup" and popup["parent"] == app.view_button
    assert app.theme_combo in popup["children"] and app.font_slider in popup["children"]
    buttons = [env.state.items[c] for c in row1 + row2 if env.state.items[c]["kind"] == "add_button"]
    assert buttons and all(b.get("small") for b in buttons)              # kompakte Schaltflächen
    app._rebuild_ui()                                                    # Sprachwechsel baut neu, ohne Doppel-Tag
    assert env.state.items["view_popup"]["parent"] == app.view_button


def test_toolbar_file_combo_adapts_to_free_width(env):
    app = env.app
    env.state.rects[app.plot_area] = ([400.0, 120.0], [900.0, 600.0])      # rechts bei 1300
    env.state.rects[app.toolbar_row1] = ([400.0, 60.0], [1000.0, 24.0])     # ragt 100 px hinaus
    env.state.items[app.file_combo]["width"] = 260
    app.toolbar_checked = 0
    app._poll_toolbar_width()
    assert env.state.items[app.file_combo]["width"] == 260 - 106
    env.state.rects[app.toolbar_row1] = ([400.0, 60.0], [700.0, 24.0])      # viel Platz: bis zur Obergrenze
    app.toolbar_checked = 0
    app._poll_toolbar_width()
    assert env.state.items[app.file_combo]["width"] == app.FILE_COMBO_RANGE[1]


def test_file_combo_all_files_restores_view_over_all_files(env):
    app = env.app
    first, second, third = _switch_runs(env)
    by = lambda d, name: next(c for c in d.channels if c.name == name)
    env.state.items[app.matrix_input]["value"] = "2*1"
    app._on_matrix()
    app._request_add(by(first, "U"), 0)                      # Graph 1: U aus zwei Dateien, eigene Farbe
    app._request_add(by(second, "U"), 0)
    app._request_add(by(first, "T"), 1)                       # Graph 2: nur Lauf 1
    app.layout.slots[0].colors[by(second, "U")] = (9, 8, 7)
    app._layout_changed()
    before = [list(s.signals) for s in app.layout.slots]
    assert env.state.items[app.file_combo]["value"] == "Mehrere Dateien"
    app._on_file_combo(None, "lauf_2.csv")
    app._on_file_combo(None, "lauf_3.mf4")                    # mehrfach wechseln: Merkstand bleibt
    wait(app)
    assert all(c.source == third.path for c in app.layout.signals())
    app._on_file_combo(None, "Alle Dateien")                  # genau die Darstellung von vorher zurück
    assert [list(s.signals) for s in app.layout.slots] == before
    assert app.layout.slots[0].colors == {by(second, "U"): (9, 8, 7)}
    assert "Alle Dateien: 3 Signale" in env.state.items[app.status]["value"]
    assert env.state.items[app.file_combo]["value"] == "Mehrere Dateien"


def test_file_combo_all_files_expands_when_graphs_changed(env):
    app = env.app
    first, second, third = _switch_runs(env)
    by = lambda d, name: next(c for c in d.channels if c.name == name)
    app._request_add(by(first, "U"), None)                   # nur eine Datei angezeigt, kein Merkstand
    app.layout.slots[0].limits[by(first, "U")] = [1.0, 2.0]
    app._layout_changed()
    app._on_file_combo(None, "Alle Dateien")                  # je Signal das gleichnamige aller Dateien
    wait(app)
    signals = app.layout.slots[0].signals
    assert [c.source for c in signals] == [first.path, second.path, third.path] and all(c.loaded for c in signals)
    assert all(app.layout.slots[0].limits[c] == [1.0, 2.0] for c in signals)    # Grenzen gehen mit
    app._on_file_combo(None, "lauf_1.csv")
    app._request_add(by(first, "I"), None)                    # Graphen geändert: Merkstand verfällt
    app._on_file_combo(None, "Alle Dateien")
    wait(app)
    names = sorted((c.name, os.path.basename(c.source)) for c in app.layout.signals())
    assert ("I", "lauf_2.csv") in names and ("U", "lauf_3.mf4") in names


def test_detection_tooltip_follows_language_after_loading_in_thai(env):
    """Datei unter Thai geladen, dann Deutsch: Erkennung (Maus hierher) zeigt deutschen Text, keine Ersatzzeichen."""
    import pickle
    from messgraph import i18n
    app = env.app
    app.thai_font = "thai-font"
    app.set_language("Thai")
    app.open_files([env.a])
    wait(app)
    info = app.datasets[0].info
    assert any(any(0x0E00 <= ord(ch) <= 0x0E7F for ch in line) for line in info)       # beim Laden: Thai
    app.set_language("Deutsch")
    tips = [str(v.get("value", "")) for v in by_kind(env.state, "add_text")
            if env.state.items.get(v.get("parent"), {}).get("kind") == "tooltip"]
    detection = next(text for text in tips if "Trennzeichen" in text)
    assert not any(0x0E00 <= ord(ch) <= 0x0E7F for ch in detection) and "Kodierung" in detection
    assert info == app.datasets[0].info                                                # Daten unverändert
    line = info[0]
    assert pickle.loads(pickle.dumps(line)) == line and i18n.retranslate("fest") == "fest"


def _tip_setup(env):
    env.app.open_files([env.a])
    wait(env.app)
    chans = {c.name: c for d in env.app.datasets for c in d.channels}
    check(env, chans["U"])                                   # U = 2*t (0..200 V), I = 100 - t
    env.app.layout.add(chans["I"], 0)
    env.app._layout_changed()
    wait(env.app)
    ui = env.app.slot_ui[0]
    env.state.rects[ui.plot] = (None, [800.0, 500.0])
    env.state.axis_limits[ui.x_axis] = [0.0, 100.0]
    env.state.axis_limits[ui.y_axis] = [0.0, 200.0]
    env.state.hovered = ui.plot
    env.state.mouse = [400.0, 300.0]
    return ui, chans


def test_marker_tooltip_only_with_markers_and_for_nearest_signal(env):
    ui, chans = _tip_setup(env)
    app = env.app
    env.state.plot_mouse = [50.0, 100.5]                     # auf U (100 V bei t = 50), I liegt bei 50
    app._poll_marker_tip()
    assert env.state.items[app.marker_tip]["show"] is False  # ohne Marker kein Tooltip
    app._on_cross_toggle(None, True)
    ui.slot.cross = [20.0, 60.0]
    app._poll_marker_tip()
    items = env.state.items
    assert items[app.marker_tip]["show"] is True
    assert items[app.tip_title]["value"].startswith("U")
    values = [items[v]["value"] for v in app.tip_values]
    assert values[0].startswith("20") and values[1].startswith("60")
    assert values[2].startswith("40") and values[3].startswith("120")   # Y1, Y2
    assert values[5].startswith("80")                                  # Delta Y
    assert values[6].startswith("80")                                  # Mittelwert 2*t über 20..60
    assert values[7].startswith("2") and values[8].startswith("2")     # Drift und Regression 2 V/s
    assert values[9].startswith("f(x) = 2") and "x" in values[9]
    assert items[app.marker_tip]["pos"] == [418.0, 318.0]
    env.state.plot_mouse = [50.0, 51.0]                      # jetzt nahe I (50 A): nur ein Tooltip, für I
    app._poll_marker_tip()
    assert items[app.tip_title]["value"].startswith("I")
    assert [items[v]["value"] for v in app.tip_values][9].startswith("f(x) = -1")
    env.state.plot_mouse = [50.0, 160.0]                     # weit weg von beiden Kurven
    app._poll_marker_tip()
    assert items[app.marker_tip]["show"] is False
    env.state.plot_mouse = [50.0, 100.5]
    env.state.hovered = None                                  # Maus nicht über dem Graphen
    app._poll_marker_tip()
    assert items[app.marker_tip]["show"] is False


def test_marker_tooltip_right_axis_signal(env):
    ui, chans = _tip_setup(env)
    app = env.app
    app._on_cross_toggle(None, True)
    app._set_right(ui.slot, chans["I"], True) if hasattr(app, "_set_right") else ui.slot.right.add(chans["I"])
    app._layout_changed()
    ui = app.slot_ui[0]
    env.state.rects[ui.plot] = (None, [800.0, 500.0])
    env.state.axis_limits[ui.x_axis] = [0.0, 100.0]
    env.state.axis_limits[ui.y_axis] = [0.0, 200.0]
    env.state.axis_limits[ui.y2_axis] = [0.0, 400.0]        # rechte Achse halber Maßstab
    env.state.hovered = ui.plot
    env.state.plot_mouse = [50.0, 25.0]                      # I = 50 A rechts entspricht 25 im linken Maßstab
    app._poll_marker_tip()
    assert env.state.items[app.tip_title]["value"].startswith("I") and "(rechts)" in env.state.items[app.tip_title]["value"]


def test_wheel_zooms_secondary_axis_when_implot_does_not(env):
    ui, chans = _tip_setup(env)
    app = env.app
    ui.slot.right.add(chans["I"])
    app._layout_changed()
    ui = app.slot_ui[0]
    env.state.rects[ui.plot] = ([100.0, 100.0], [800.0, 500.0])        # Graph 100..900 x 100..600
    env.state.axis_limits[ui.y_axis] = [0.0, 200.0]
    env.state.axis_limits[ui.y2_axis] = [0.0, 100.0]
    env.state.hovered = ui.plot
    env.state.mouse = [500.0, 350.0]                                    # Zeichenfläche
    env.state.plot_mouse = [50.0, 100.0]                                # Mitte -> rechts 50
    app.y_release = {}
    app._snapshot_y2()
    app._on_wheel(None, 1)
    lo, hi = env.state.axis_limits[ui.y2_axis]
    assert lo == pytest.approx(5.0) and hi == pytest.approx(95.0)       # 10 % enger um die Maus
    assert app.y_release[ui.y2_axis] == 1
    app.tick(); app.tick()
    assert ui.y2_axis not in app.y_release                              # wieder frei
    env.state.axis_limits[ui.y2_axis] = [0.0, 100.0]
    app._snapshot_y2()
    env.state.axis_limits[ui.y2_axis] = [10.0, 90.0]                    # ImPlot hat selbst gezoomt: kein Doppelzoom
    app._on_wheel(None, 1)
    assert env.state.axis_limits[ui.y2_axis] == [10.0, 90.0]
    app._snapshot_y2()
    env.state.mouse = [880.0, 350.0]                                    # über der rechten Achse, herauszoomen
    app._on_wheel(None, -1)
    lo, hi = env.state.axis_limits[ui.y2_axis]
    assert hi - lo == pytest.approx(80.0 / 0.9)
    app._snapshot_y2()
    before = list(env.state.axis_limits[ui.y2_axis])
    env.state.mouse = [120.0, 350.0]                                    # linke Achse: nur ImPlot (linke Achse)
    app._on_wheel(None, 1)
    assert env.state.axis_limits[ui.y2_axis] == before


def test_left_drag_pans_secondary_axis(env):
    ui, chans = _tip_setup(env)
    app = env.app
    ui.slot.right.add(chans["I"])
    app._layout_changed()
    ui = app.slot_ui[0]
    lim = env.state.axis_limits
    env.state.rects[ui.plot] = ([100.0, 100.0], [800.0, 500.0])
    lim[ui.x_axis], lim[ui.y_axis], lim[ui.y2_axis] = [0.0, 100.0], [0.0, 200.0], [0.0, 100.0]
    env.state.hovered = ui.plot
    env.state.mouse = [500.0, 300.0]
    app.y_release = {}
    env.state.left_down = True
    app._poll_y2_pan()                                   # Zug beginnt auf der Zeichenfläche
    lim[ui.y_axis] = [20.0, 220.0]                       # ImPlot verschiebt links um 10 % des Bereichs
    app._poll_y2_pan()
    assert lim[ui.y2_axis] == [pytest.approx(10.0), pytest.approx(110.0)]
    lim[ui.y_axis] = [10.0, 210.0]
    app._poll_y2_pan()
    assert lim[ui.y2_axis] == [pytest.approx(5.0), pytest.approx(105.0)]
    env.state.left_down = False
    app._poll_y2_pan()
    assert app.y2_pan is None
    # ImPlot verschiebt die rechte Achse selbst: kein Eingriff
    lim[ui.y_axis], lim[ui.y2_axis] = [0.0, 200.0], [0.0, 100.0]
    env.state.left_down = True
    app._poll_y2_pan()
    lim[ui.y_axis], lim[ui.y2_axis] = [20.0, 220.0], [10.0, 110.0]
    app._poll_y2_pan()
    lim[ui.y_axis] = [40.0, 240.0]
    lim[ui.y2_axis] = [20.0, 120.0]
    app._poll_y2_pan()
    assert lim[ui.y2_axis] == [20.0, 120.0]
    env.state.left_down = False
    app._poll_y2_pan()
    # über der rechten Achse ziehen: folgt der Maus
    lim[ui.y_axis], lim[ui.y2_axis] = [0.0, 200.0], [0.0, 100.0]
    env.state.mouse = [880.0, 300.0]
    env.state.left_down = True
    app._poll_y2_pan()
    env.state.mouse = [880.0, 340.0]
    app._poll_y2_pan()
    lo, hi = lim[ui.y2_axis]
    assert lo > 0 and hi - lo == pytest.approx(100.0)
    env.state.left_down = False
    app._poll_y2_pan()
    # Marker ziehen (linke Achse bleibt): rechte bleibt auch
    lim[ui.y2_axis] = [0.0, 100.0]
    env.state.mouse = [500.0, 300.0]
    env.state.left_down = True
    app._poll_y2_pan()
    env.state.mouse = [520.0, 330.0]
    app._poll_y2_pan()
    assert lim[ui.y2_axis] == [0.0, 100.0]
    env.state.left_down = False


def _two_graphs(env):
    env.app.open_files([env.a])
    wait(env.app)
    u, i = env.app.datasets[0].channels
    check(env, u)
    check(env, i)
    for ui in env.app.slot_ui:
        env.state.axis_limits[ui.x_axis] = [0.0, 100.0]
    for _ in range(6):                                          # Einpassen nach dem Aufbau abwarten
        env.app.tick()
    return env.app.slot_ui[0], env.app.slot_ui[1], u, i


def test_zoom_sets_markers_to_10_and_90_percent_with_hovered_graph_first(env):
    ui0, ui1, u, i = _two_graphs(env)
    app = env.app
    app._on_cross_toggle(None, True)
    env.state.hovered = ui1.plot                               # Benutzer zoomt Graph 2
    env.state.axis_limits[ui0.x_axis] = [0.0, 50.0]            # Graph 1 ändert sich im selben Bild anders
    env.state.axis_limits[ui1.x_axis] = [20.0, 40.0]
    app.tick()
    assert ui1.slot.cross == pytest.approx([22.0, 38.0])        # 10 % / 90 % der neuen Ansicht von Graph 2
    assert ui0.slot.cross == pytest.approx([22.0, 38.0])        # Marker synchron: mitgeführt, nicht überschrieben
    app.tick()
    assert ui1.slot.cross == pytest.approx([22.0, 38.0])        # stabil, kein Hin und Her
    env.state.axis_limits[ui1.x_axis] = [21.0, 41.0]           # nur verschoben, Marker noch im Bild: bleiben
    app.tick()
    assert ui1.slot.cross == pytest.approx([22.0, 38.0])
    env.state.axis_limits[ui1.x_axis] = [25.0, 45.0]           # verschoben, M1 fällt heraus: 10 % / 90 %
    app.tick()
    assert ui1.slot.cross == pytest.approx([27.0, 43.0])
    app._on_cross_sync(None, False)
    env.state.axis_limits[ui1.x_axis] = [0.0, 10.0]            # wieder gezoomt
    app.tick()
    assert ui1.slot.cross == pytest.approx([1.0, 9.0])


def test_markers_switched_on_while_zoomed_land_in_view(env):
    ui0, ui1, u, i = _two_graphs(env)
    app = env.app
    ui0.slot.cross = [5.0, 95.0]
    ui1.slot.cross = [5.0, 95.0]
    for ui in (ui0, ui1):
        env.state.axis_limits[ui.x_axis] = [40.0, 60.0]
    app.tick()
    app._on_cross_toggle(None, True)
    assert ui0.slot.cross == pytest.approx([42.0, 58.0]) and ui1.slot.cross == pytest.approx([42.0, 58.0])


def test_marker3_value_table_tooltip(env):
    ui0, ui1, u, i = _two_graphs(env)
    app = env.app
    app.layout.add(i, 0)                                       # Graph 1: U und I
    app._layout_changed()
    wait(app)
    ui0, ui1 = app.slot_ui[0], app.slot_ui[1]
    for ui in (ui0, ui1):
        env.state.axis_limits[ui.x_axis] = [0.0, 100.0]
        env.state.axis_limits[ui.y_axis] = [0.0, 200.0]
        env.state.rects[ui.plot] = (None, [800.0, 500.0])
    for _ in range(6):
        app.tick()
    app.set_marker3(True)
    items = env.state.items
    assert items[ui0.m3_line]["show"] is True and ui0.slot.cross3 == pytest.approx(50.0)
    assert app.cross_on is False                               # unabhängig von M1/M2
    items[ui0.m3_line]["value"] = 25.0                         # M3 ziehen
    app.tick()
    assert ui0.slot.cross3 == 25.0 and items[ui1.m3_line]["value"] == 25.0   # synchron
    env.state.hovered = ui0.plot
    env.state.mouse = [300.0, 300.0]
    env.state.plot_mouse = [25.5, 120.0]                      # waagerecht nah an M3
    app.tick()
    assert items[app.m3_tip]["show"] is True
    assert items[app.m3_title]["value"].startswith("M3: 25")
    rows = [[items[c]["value"] for c in items[r]["children"]] for r in app.m3_rows_items]
    assert rows == [["U [V]", "50 V", "0 V", "200 V", "100 V", "2 V/s"],
                    ["I [A]", "75 A", "0 A", "100 A", "50 A", "-1 A/s"]]     # M1/M2 aus: gesamter Verlauf
    assert "gesamter Signalverlauf" in items[app.m3_range_text]["value"]
    app._on_cross_toggle(None, True)                          # Bereich zwischen M1 und M2 (Standard)
    ui0.slot.cross = [20.0, 60.0]
    app.tick()
    rows = [[items[c]["value"] for c in items[r]["children"]] for r in app.m3_rows_items]
    assert rows[0] == ["U [V]", "50 V", "40 V", "120 V", "80 V", "2 V/s"]
    assert rows[1][2:] == ["40 A", "80 A", "60 A", "-1 A/s"]
    assert "zwischen M1 und M2 (20 s bis 60 s)" in items[app.m3_range_text]["value"]
    app._on_m3_range(None, "Gesamter Signalverlauf")          # wahlweise gesamter Verlauf
    app.tick()
    rows = [[items[c]["value"] for c in items[r]["children"]] for r in app.m3_rows_items]
    assert app.m3_range == "all" and rows[0][2:] == ["0 V", "200 V", "100 V", "2 V/s"]
    app.set_m3_range("markers")
    app._on_cross_toggle(None, False)
    env.state.plot_mouse = [60.0, 120.0]                      # weit weg
    app.tick()
    assert items[app.m3_tip]["show"] is False
    env.state.left_down = True                                 # beim Ziehen bleibt die Tabelle sichtbar
    env.state.plot_mouse = [25.0, 120.0]
    app.tick()
    env.state.plot_mouse = [70.0, 120.0]
    items[ui0.m3_line]["value"] = 70.0
    app.tick()
    assert items[app.m3_tip]["show"] is True and items[app.m3_title]["value"].startswith("M3: 70")
    env.state.left_down = False
    env.state.axis_limits[ui0.x_axis] = [0.0, 50.0]            # Zoom: M3 fällt aus dem Bild -> Mitte
    app.tick()
    assert ui0.slot.cross3 == pytest.approx(25.0)
    data = app.session_dict()
    assert data["options"]["marker3_on"] is True and data["graphs"][0]["cross3"] == pytest.approx(25.0)
    app.set_marker3(False)
    assert items[ui0.m3_line]["show"] is False and items[app.m3_tip]["show"] is False


def _ancestors(state, tag):
    out = []
    while tag is not None and tag in state.items:
        tag = state.items[tag]["parent"]
        out.append(tag)
    return out


def test_calc_fourier_dialog_log_axes_and_session(env, tmp_path):
    from messgraph import session as sessions
    app, dpg = env.app, env.gui.dpg
    path = tmp_path / "netz.csv"
    t = np.arange(0, 1, 1e-4)
    y = 325.0 * np.sin(2 * np.pi * 50 * t) + np.where(t >= 0.5, 65.0, 0.0) * np.sin(2 * np.pi * 250 * t)
    path.write_text("Zeit [s],U [V]\n" + "".join(f"{a:.4f},{b:.4f}\n" for a, b in zip(t, y)))
    app.open_files([str(path)])
    wait(app)
    ds = app.datasets[0]
    app._open_calc_window(None, None, ds)
    dpg.set_value(app.calc_kind, "Fourier-Analyse")
    app._calc_kind_show()
    assert env.state.items[app.calc_fft_group]["show"] is True and env.state.items[app.calc_formula_group]["show"] is False
    dpg.set_value(app.calc_name, "Harmonische U")                 # frei benannt
    dpg.set_value(app.calc_fft_signal, "U")
    dpg.set_value(app.calc_fft_mode, "Harmonische")
    dpg.set_value(app.calc_fft_hmin, "1")
    dpg.set_value(app.calc_fft_hmax, "15")
    app._calc_fft_preview()
    assert dpg.get_value(app.calc_fft_text) == "Formel: FFT({U}; h=1..15; f0=auto; y=pct)"
    app._calc_apply()
    calc_wait(app)
    h = next(c for c in ds.channels if c.name == "Harmonische U")
    a1, a5 = 325.0, np.sqrt(25 * 65.0 ** 2 / 50)                    # Effektivwert der Amplituden über alle Perioden
    assert h.unit == "%" and list(h.x[:5]) == [1, 2, 3, 4, 5]
    assert h.y[0] == pytest.approx(100 * a1 / (a1 + a5), abs=0.3) and h.y[4] == pytest.approx(100 * a5 / (a1 + a5), abs=0.3)
    assert h.y.sum() == pytest.approx(100.0, abs=0.01)
    assert "f0 = 50" in dpg.get_value(app.calc_status)
    assert "Periodisch: ja, 50 ganze Perioden" in dpg.get_value(app.calc_status)
    assert h.fourier["periodic"] and h.fourier["periods"] == 50 and len(h.fourier["table"]["rows"]) == 50
    texts = [i.get("default_value") or i.get("value") for i in by_kind(env.state, "add_text")]
    assert "Anzahl Perioden: 50" in texts and "Alle" in texts and "Mittel" in texts      # Tooltip-Tabelle
    assert "... 20 weitere Perioden" in texts
    # Frequenzbereich als zweites Ergebnis
    dpg.set_value(app.calc_name, "Spektrum U")
    dpg.set_value(app.calc_fft_mode, "Frequenzbereich")
    dpg.set_value(app.calc_fft_fmin, "10")
    dpg.set_value(app.calc_fft_fmax, "1000")
    app._calc_apply()
    calc_wait(app)
    sp = next(c for c in ds.channels if c.name == "Spektrum U")
    assert sp.x_unit == "Hz" and sp.x[0] == pytest.approx(50, abs=0.1) and sp.x.size == 20   # Balken bei n*f0
    assert sp.plot_style == "bar" and sp.bar_width == pytest.approx(30, abs=0.1)
    # Bearbeiten lädt die Felder zurück
    app._calc_edit(h)
    assert dpg.get_value(app.calc_kind) == "Fourier-Analyse" and dpg.get_value(app.calc_fft_mode) == "Harmonische"
    dpg.set_value(app.calc_fft_hmax, "5")
    app._calc_apply()
    calc_wait(app)
    assert h.x.size == 5
    # darstellen, Achsen logarithmisch (Kontextmenü)
    check(env, sp)
    slot = next(s for s in app.layout.slots if sp in s.signals)
    app.ctx_slot = slot
    app._ctx_log("x", True)
    app._ctx_log("y", True)
    axes = [i for i in by_kind(env.state, "add_plot_axis") if i.get("scale") == "mvPlotScale_Log10"]
    assert len(axes) >= 2
    grid = by_kind(env.state, "add_inf_line_series")                 # Hilfslinien der log. Achsen
    assert {g.get("label") for g in grid} >= {"##logx", "##logy"}
    data = sessions.build_session(app.datasets, app.layout, {})
    graph = next(g for g in data["graphs"] if any(s["name"] == "Spektrum U" for s in g["signals"]))
    assert graph["log_x"] and graph["log_y"]
    assert any(c["formula"].startswith("FFT({U}; f=10..1000; f0=auto; y=pct") for c in data["files"][0]["computed"])
    spec = app._plot_spec(app.slot_ui[app.layout.slots.index(slot)], app.layout.slots.index(slot)) \
        if hasattr(app, "_plot_spec") else None
    if spec is not None:
        assert spec.log_x and spec.log_y
    # Harmonische als senkrechte Balken, Frequenzbereich als Linie
    check(env, h)
    bars = [i for i in by_kind(env.state, "add_bar_series") if i["args"][0] == h.x.tolist()]
    assert bars and bars[-1]["weight"] == 0.6
    assert not [i for i in by_kind(env.state, "add_line_series") if i.get("label", "").startswith(("Harmonische U", "Spektrum U"))]
    hslot = next(s_ for s_ in app.layout.slots if h in s_.signals)
    hindex = app.layout.slots.index(hslot)
    hspec = app._plot_spec(app.slot_ui[hindex], hindex)
    assert any(se.bars for se in hspec.series)
    # Marker im Graphen des Grundsignals bestimmen die Schwingung(en) der Balken
    check(env, ds.channels[0])                                       # U in einen eigenen Graphen
    uslot = next(s_ for s_ in app.layout.slots if ds.channels[0] in s_.signals)
    assert uslot is not hslot
    dpg.set_value(app.cross_box, True)
    app._on_cross_toggle(None, True)
    uslot.cross = [0.0002, 0.0298]                                   # 0,01 .. 1,49 Schwingungen -> 1. Schwingung
    app._update_harmonics()
    assert h.y[0] == pytest.approx(100.0, abs=0.5) and h.y[4] == pytest.approx(0.0, abs=0.2)
    assert "Periode 1 (1 von 50)" in h.fourier["selection_text"]
    hui = next(u for u in app.slot_ui if u.slot is hslot)
    assert env.state.items[hui.series[h]]["value"][1][0] == pytest.approx(100.0, abs=0.5)   # Balken aktualisiert
    uslot.cross = [0.6002, 0.6298]                                   # Schwingung mit 5. Harmonischer
    app._update_harmonics()
    assert h.y[0] == pytest.approx(100 * 325 / (325 + 65), abs=0.5) and h.y[4] == pytest.approx(100 * 65 / 390, abs=0.5)
    uslot.cross = [0.0001, 0.0004]
    app._update_harmonics()
    assert not h.y.any() and "keine Periode" in h.fourier["selection_text"]
    # Marker gelten nur für das Grundsignal: im Fourier-Graphen unsichtbar, nicht synchron, keine X-Kopplung
    dpg.set_value(app.cross_box, True)
    app._on_cross_toggle(None, True)
    hui = next(u for u in app.slot_ui if u.slot is hslot)
    uui = next(u for u in app.slot_ui if u.slot is uslot)
    assert hui.fourier and not uui.fourier
    assert all(env.state.items[line].get("show") is False for line in hui.v_lines)
    assert all(env.state.items[line].get("show") is not False for line in uui.v_lines)
    before = list(hslot.cross)
    app.cross_sync = True
    app._place_markers(uui, [0.3002, 0.3298])
    assert hslot.cross == before and uslot.cross == [0.3002, 0.3298]
    assert app.manual_link and not any(i.get("link_all_x") for i in by_kind(env.state, "add_subplots")[-1:])
    app.link_settle, app.link_last = 0, {}
    env.state.axis_limits[uui.x_axis] = [0.0, 1.0]
    env.state.axis_limits[hui.x_axis] = [0.5, 15.5]
    app._poll_link()
    env.state.axis_limits[uui.x_axis] = [0.2, 0.4]                   # Zoom am Grundsignal
    app._poll_link()
    assert env.state.axis_limits[hui.x_axis] == [0.5, 15.5]          # Fourier-Graph bleibt
    dpg.set_value(app.cross_box, False)
    app._on_cross_toggle(None, False)                                # ohne Marker: alle Perioden
    assert h.y[0] == pytest.approx(100 * a1 / (a1 + a5), abs=0.3)
    # ohne Marker: Zoomen des Grundsignals bewertet neu (Perioden im sichtbaren Bereich)
    uui.view = None
    env.state.axis_limits[uui.x_axis] = [0.0, 1.0]
    app._poll_view()
    env.state.axis_limits[uui.x_axis] = [0.1, 0.3]                   # nur Schwingungen ohne Oberwelle
    uui.settle = 0
    app._poll_view()
    assert h.y[0] == pytest.approx(100.0, abs=0.5) and "sichtbarer Bereich" in h.fourier["selection_text"]
    env.state.axis_limits[uui.x_axis] = [-0.05, 1.05]                # wieder alles
    app._poll_view()
    assert h.y[0] == pytest.approx(100 * a1 / (a1 + a5), abs=0.3)
    # Dämpfung in dB statt Anteil
    app._calc_edit(h)
    dpg.set_value(app.calc_fft_scale, "Dämpfung [dB]")
    app._calc_apply()
    calc_wait(app)
    assert h.unit == "dB" and h.y[0] == pytest.approx(0.0) and h.y[4] == pytest.approx(20 * np.log10(a1 / a5), abs=0.3)
    dpg.set_value(app.calc_fft_scale, "Anteil [%]")
    # Spektrum wahlweise durchgehend (Linie) statt Balken; folgt ebenfalls den Markern
    app._calc_edit(sp)
    assert dpg.get_value(app.calc_fft_mode) == "Frequenzbereich"
    dpg.set_value(app.calc_fft_view, "Spektrum (durchgehend)")
    dpg.set_value(app.calc_fft_scale, "Amplitude")
    app._calc_fft_preview()
    assert dpg.get_value(app.calc_fft_text) == "Formel: FFT({U}; f=10..1000; f0=auto; y=amp; plot=line)"
    app._calc_apply()
    calc_wait(app)
    assert sp.plot_style == "line" and sp.unit == "V" and sp.x.size > 500
    assert any(i.get("label", "").startswith("Spektrum U") for i in by_kind(env.state, "add_line_series"))
    dpg.set_value(app.cross_box, True)
    app._on_cross_toggle(None, True)
    uslot.cross = [0.6002, 0.6298]                                   # eine Schwingung: Linien im Abstand f0
    app._update_harmonics()
    assert sp.x.size < 25 and sp.y[np.argmin(abs(sp.x - 250))] == pytest.approx(65.0, abs=1.0)
    dpg.set_value(app.cross_box, False)
    app._on_cross_toggle(None, False)
    assert sp.x.size > 500
    # Doppelklick auf das Ergebnis in der Signalliste: eigenes Fenster mit allen Perioden
    app._calc_edit(h)
    dpg.set_value(app.calc_fft_hmax, "15")
    app._calc_apply()
    calc_wait(app)
    app._refresh_channel_list()
    env.state.hovered = app.checkboxes[h]
    app._on_double_click()
    assert "fourier_window" in env.state.items and env.state.items["fourier_window"].get("show", True) is not False
    rows = [i for i in by_kind(env.state, "table_row") if env.state.items.get(i["id"]) and
            app.fourier_table in _ancestors(env.state, i["id"])]
    assert len(rows) == 1 + 3 + 50                                   # Alle, Mittel/Min/Max, 50 Perioden
    app._fourier_copy(h)
    assert dpg.clipboard[-1].count("\n") == 54 and dpg.clipboard[-1].startswith("Periode\t")
    env.state.hovered = None
    # auch über den Knopf in der Liste des Rechendialogs
    app._open_calc_window(None, None, ds)
    assert any(i.get("label") == "Tabelle..." for i in by_kind(env.state, "add_button"))


def test_same_name_signals_of_all_files_with_checkbox(env, tmp_path):
    app, dpg = env.app, env.gui.dpg
    for name, k in (("a.csv", 1.0), ("b.csv", 2.0), ("c.csv", 3.0)):
        (tmp_path / name).write_text("Zeit [s],U [V],I [A]\n" + "".join(f"{i},{k * i},{i}\n" for i in range(20)))
    app.open_files([str(tmp_path / n) for n in ("a.csv", "b.csv")])
    wait(app)
    app.open_files([str(tmp_path / "c.csv")])
    wait(app)
    assert len(app.datasets) == 3
    app._refresh_channel_list()
    assert env.state.items[app.same_name_box]["show"] is True           # nur bei mehreren Dateien sichtbar
    u = [next(c for c in d.channels if c.name == "U") for d in app.datasets]
    # aus: Einzelauswahl
    dpg.set_value(app.same_name_box, False)
    app._on_channel(None, True, u[0])
    assert app.layout.contains(u[0]) and not app.layout.contains(u[1])
    app._on_channel(None, False, u[0])
    # an: alle gleichnamigen Signale zugleich, gemeinsamer Graph
    dpg.set_value(app.same_name_box, True)
    app._on_same_name(None, True)
    assert app.settings["same_name"] is True
    app._on_channel(None, True, u[1])
    slots = [s for s in app.layout.slots if s.signals]
    assert len(slots) == 1 and set(slots[0].signals) == set(u)
    assert all(dpg.get_value(app.checkboxes[c]) for c in u)
    assert not any(c.name == "I" for c in slots[0].signals)
    app._on_channel(None, False, u[2])                                   # Abwählen entfernt alle
    assert not any(app.layout.contains(c) for c in u)
    # eine Datei: Checkbox verborgen, Einzelauswahl
    for d in list(app.datasets[1:]):
        app.close_dataset(d) if hasattr(app, "close_dataset") else app.datasets.remove(d)
    app._refresh_channel_list()
    assert env.state.items[app.same_name_box]["show"] is False
    assert app._same_name_peers(u[0]) == []
