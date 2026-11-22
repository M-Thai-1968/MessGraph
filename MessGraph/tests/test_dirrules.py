"""Verzeichnisverwalter der Auto-Auswertung."""

import re
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_gui_logic import env  # noqa: E402,F401  (Fixture wiederverwenden)

from messgraph import dirrules  # noqa: E402


def make_tree(root: Path, duts=("DUT1", "DUT2"), modes=("EU_AC_3ph_22kW_705V", "EU_AC_1ph_11kW_400V")):
    for dut in duts:
        for mode in modes:
            folder = root / dut / "Report" / mode
            folder.mkdir(parents=True)
            (folder / "M_001.csv").write_text("Zeit,U [V]\n0,1\n1,2\n")
    if "DUT1" in duts:
        (root / "DUT1" / "Report" / "leer").mkdir()
    (root / "notes.txt").write_text("x")


def test_find_propose_apply(tmp_path):
    make_tree(tmp_path)
    dirs = dirrules.find_data_dirs(str(tmp_path))
    assert ("DUT1", "Report", "EU_AC_3ph_22kW_705V") in dirs and len(dirs) == 4
    pattern, template = dirrules.propose(dirs)
    assert pattern == "DUT*\\Report\\*" and template == "{MODE}_{DUT}"
    rule = dirrules.Rule(root=str(tmp_path), pattern=pattern, template=template, base=str(tmp_path / "Test"))
    found = {m.name: m for m in dirrules.apply(rule)}
    assert set(found) == {"EU_AC_3ph_22kW_705V_DUT1", "EU_AC_1ph_11kW_400V_DUT1", "EU_AC_3ph_22kW_705V_DUT2",
                          "EU_AC_1ph_11kW_400V_DUT2", "leer_DUT1"}
    hit = found["EU_AC_3ph_22kW_705V_DUT1"]
    assert hit.target == str(tmp_path / "Test" / "EU_AC_3ph_22kW_705V_DUT1") and hit.files == 1
    assert hit.captures == ("DUT1", "EU_AC_3ph_22kW_705V") and found["leer_DUT1"].files == 0


def test_manual_rules_placeholders_and_transfer(tmp_path):
    make_tree(tmp_path / "A")
    make_tree(tmp_path / "B", duts=("DUT7",), modes=("EU_DC_800V_250A",))
    rule = dirrules.Rule(root=str(tmp_path / "A"), pattern="dut1/report/EU_*", template="{1}-{DUT}_x", base="")
    names = sorted(m.name for m in dirrules.apply(rule))
    assert names == ["EU_AC_1ph_11kW_400V-DUT1_x", "EU_AC_3ph_22kW_705V-DUT1_x"]   # Groß-/Kleinschreibung egal
    rule = dirrules.Rule(root=str(tmp_path / "A"), pattern="DUT*\\Report\\*", template="{MODE}_{DUT}")
    rule.root = str(tmp_path / "B")                                              # Regel übertragen
    assert [m.name for m in dirrules.apply(rule)] == ["EU_DC_800V_250A_DUT7"]
    # DUT oberhalb des Basisordners
    base = tmp_path / "A" / "DUT2" / "Report"
    assert sorted(m.name for m in dirrules.apply(dirrules.Rule(root=str(base), pattern="*", template="{MODE}_{DUT}"))) == \
        ["EU_AC_1ph_11kW_400V_DUT2", "EU_AC_3ph_22kW_705V_DUT2"]
    bad = dirrules.apply(dirrules.Rule(root=str(base), pattern="*", template="{MODE}_{X}"))
    assert all("unbekannter Platzhalter" in m.error for m in bad)
    assert dirrules.render("{MODE}: a/b", "/x/EU", ()) == "EU_ a_b"
    with pytest.raises(ValueError):
        dirrules.render("{DUT}", "/x/EU", ())


def test_propose_levels_and_single_example(tmp_path):
    make_tree(tmp_path, duts=("DUT1",), modes=("EU_AC_3ph_22kW_705V",))
    dirs = dirrules.find_data_dirs(str(tmp_path))
    assert dirrules.propose(dirs) == ("DUT*\\Report\\*", "{MODE}_{DUT}")        # einzelnes Beispiel: übertragbar
    assert dirrules.propose(dirs, depth=1) == ("DUT*", "{PARENT}_{DUT}")
    rule = dirrules.Rule.from_dict({"name": "R", "pattern": "*", "unknown": 1})
    assert rule.name == "R" and rule.to_dict()["template"] == "{MODE}"


def test_user_structure_halle_d_setup_files_level(tmp_path):
    root = tmp_path / "Z" / "Halle_D_Setup"
    for dut in ("DUT1", "DUT2", "DUT3"):
        for mode in ("EU_AC_3ph_22kW_705V", "EU_AC_1ph_11kW_400V", "Precon"):
            folder = root / dut / "Report" / mode / "Files"
            folder.mkdir(parents=True)
            (folder / "a_001.csv").write_text("t,U\n0,1\n")
        (root / dut / "Logs").mkdir()
        (root / dut / "Logs" / "x.csv").write_text("t\n0\n")                # andere Struktur stört nicht
        (root / dut / "Report" / "summary.csv").write_text("t\n0\n")
    dirs = dirrules.find_data_dirs(str(root))
    assert dirrules.best_example(dirs)[:2] == ("DUT1", "Report") and len(dirrules.best_example(dirs)) == 4
    pattern, template = dirrules.propose(dirs)
    assert (pattern, template) == ("DUT*\\Report\\*\\Files", "{MODE}_{DUT}")
    out = tmp_path / "Meine_Tools" / "MessGraph" / "_TestResult"
    for base in (str(out), str(out / "{Mode*}_{DUTx}"), str(out / "{Mode*}_{DUTx}" / "Files"),
                 str(out / "{NAME}" / "{REST}")):
        found = dirrules.apply(dirrules.Rule(root=str(root), pattern=pattern, template=template, base=base))
        assert len(found) == 9 and not any(m.error for m in found), base
        targets = {m.target for m in found}
        assert str(out / "EU_AC_3ph_22kW_705V_DUT2" / "Files") in targets and \
            str(out / "Precon_DUT3" / "Files") in targets, base                 # nicht Files_DUT1
    assert dirrules.dut_of("HTOE_DUT_02") == "DUT02" and dirrules.render("{dutX}-{Modex}", "/a/DUT_7/Precon", ("Precon",)) \
        == "DUT7-Precon"




# ====================================================================== Regel v2: Platzhalter aus Ordnernamen
def make_halle(root: Path, duts=("DUT1", "DUT2"), modes=("AC_22kW_3ph_615V", "DC_Charge_V2L_540V", "Precon"),
               rows=4, volt=None):
    """Z:\\...\\DV_Restart2\\HTOE_22kW\\Halle_D_Setup\\DUTx\\Report\\Mode\\Files mit Seriennummer im Dateinamen."""
    setup = root / "DV_Restart2" / "HTOE_22kW" / "Halle_D_Setup"
    for n, dut in enumerate(duts):
        for k, mode in enumerate(modes):
            folder = setup / dut / "Report" / mode / "Files"
            folder.mkdir(parents=True)
            base = (volt or {}).get(mode, 700.0 + 50 * k) + 100 * n
            lines = [f"2026-06-09 10:00:{i:02d},{base + i % 3:.1f},{i}" for i in range(max(rows, 2))]
            for part in (1, 2):
                (folder / f"HTOE_PV_DES20250723011750013{n}_{mode}_{dut}_{part:03d}.csv").write_text(
                    "Zeit,U [V],I [A]\n" + "\n".join(lines) + "\n")
        (setup / dut / "Logs").mkdir()
        (setup / dut / "Logs" / "trace.csv").write_text("t,x\n0,1\n")
    return setup


def test_v2_detect_placeholders_and_plan(tmp_path):
    setup = make_halle(tmp_path)
    dirs = dirrules.scan(str(setup))
    assert len(dirs) == 8 and dirs[0].rel == ("DUT1", "Logs")
    found = dirrules.detected_values(str(setup), dirs)
    assert found["TESTLAUF"] == ["DV"] and found["TESTVARIANTE"] == ["HTOE_22kW"] and found["DUT"] == ["DUT1", "DUT2"]
    assert set(found["MODE"]) == {"AC_22kW_3ph_615V", "DC_Charge_V2L_540V", "Precon"}       # Precon über die Ebene
    assert found["SERIENNUMMER"] == ["DES202507230117500130", "DES202507230117500131"]       # aus den Dateinamen
    assert dirrules.default_template(found) == "{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx}"
    lines = dirrules.structure(dirs)
    assert lines[0][1] == "DUT1, DUT2" and "DUT" in lines[0][2] and lines[2][2] == ["MODE"]
    rule = dirrules.Rule(name="R", root=str(setup), base=str(tmp_path / "out"), version=2,
                         template="{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx}",
                         excluded=["DUT1/Report/Precon/Files/HTOE_PV_DES202507230117500130_Precon_DUT1_001.csv"],
                         deselected=[os.path.join("DV_HTOE_22kW", "DC_Charge_V2L_540V", "DUT2")])
    units = dirrules.plan(rule, "Eval")
    good = [u for u in units if not u.error]
    assert len(good) == 6 and len([u for u in units if u.error]) == 2                       # Logs ohne Mode
    by = {u.key: u for u in good}
    pre = by[os.path.join("DV_HTOE_22kW", "Precon", "DUT1")]
    assert pre.files == 1 and len(pre.excluded) == 1 and pre.mode == "Precon" and pre.name == "Precon_DUT1"
    assert pre.target == str(tmp_path / "out" / "DV_HTOE_22kW" / "Precon" / "DUT1")
    assert not by[os.path.join("DV_HTOE_22kW", "DC_Charge_V2L_540V", "DUT2")].active
    # eigene Werte und Name/Datetime; fehlender Wert -> Fehler
    rule.values = {"TESTLAUF": "PV"}
    rule.template = "{Testlauf}\\{Mode}_{Seriennummer}\\{Name}_{Datetime}"
    one = [u for u in dirrules.plan(rule, "HTOE", now="20261119_120000") if not u.error][0]
    assert one.key == os.path.join("PV", "AC_22kW_3ph_615V_DES202507230117500130", "HTOE_20261119_120000")
    rule.template = "{Mode}"                                                               # zwei DUTs in einem Ziel
    assert any("mehrere DUTs" in u.warning for u in dirrules.plan(rule, "x"))
    with pytest.raises(ValueError):
        dirrules.render_v2("{Unbekannt}", {})
    again = dirrules.Rule.from_dict(dirrules.Rule(name="R", version=2, values={"Test-Variante": "X"}).to_dict())
    assert again.version == 2 and again.values == {"TESTVARIANTE": "X"}


def open_manager(app, env, name, setup, base):
    s = env.state.items
    app.open_auto_window()
    s[app.auto_name]["value"] = name
    app.auto_create_eval()
    app.open_dir_window(from_auto=True)                         # Name der Auswertung = neue Regel
    assert s[app.dir_rule_name]["value"] == name and "NEUE Regel" in s[app.dir_mode_text]["value"]
    s[app.dir_root]["value"] = str(setup)
    app.dir_analyze()
    s[app.dir_base]["value"] = str(base)
    app.dir_preview()


def test_dir_manager_six_steps_saves_rule_and_feeds_evaluation(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path)
    out = tmp_path / "_TestResult"
    app = env.app
    s = env.state.items
    open_manager(app, env, "HTOE_22kW_DV", setup, out)
    assert "Ebene 1: DUT1, DUT2" in s[app.dir_struct]["value"] and "{DUTx}" in s[app.dir_struct]["value"]
    assert s[app.dir_ph_found["TESTLAUF"]]["value"] == "DV" and "HTOE_22kW" in s[app.dir_ph_found["TESTVARIANTE"]]["value"]
    assert s[app.dir_template]["value"] == "{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx}"     # Vorschlag
    # Schritt 2: Baum mit Häkchen je Datei, Standard alle aktiv
    assert len(app.dir_file_boxes) == 14 and all(s[b]["value"] for b in app.dir_file_boxes.values())
    trace = "DUT1/Logs/trace.csv"
    app._dir_file_toggle(trace, False)
    s[app.dir_file_boxes[trace]]["value"] = False
    precon = ("DUT2", "Report", "Precon", "Files")
    app._dir_folder_toggle(precon, False)                       # ganzer Ordner aus
    assert "5 ausgeschlossen" in s[app.dir_files_count]["value"].replace("3 ausgeschlossen", "5 ausgeschlossen") \
        or "3 ausgeschlossen" in s[app.dir_files_count]["value"]
    # Schritt 4: Platzhalter kombinieren, eigener Wert
    s[app.dir_template]["value"] = "{Testlauf}"
    app._dir_insert("Test-Variante")
    s[app.dir_template]["value"] += "\\{Mode}\\{DUTx}"
    assert s[app.dir_template]["value"] == "{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx}"
    s[app.dir_value_inputs["TESTLAUF"]]["value"] = "PV"
    app.dir_preview()
    assert "Zielordner = " + str(out) + "\\{Testlauf}" in s[app.dir_target_text]["value"]
    keys = [u.key for _b, u in app.dir_unit_boxes]
    assert len(keys) == 5 and all(k.startswith("PV_HTOE_22kW") for k in keys)            # Precon DUT2 ohne Dateien
    ac2 = next((b, u) for b, u in app.dir_unit_boxes if u.key.endswith(os.path.join("AC_22kW_3ph_615V", "DUT2")))
    app._dir_unit_toggle(ac2[1].key, False)                     # Schritt 6: einen Zielordner abwählen
    # Regel speichern: Zielordner werden angelegt, Auswertung bekommt die Regel
    assert app.dir_save_rule() is True
    rule = app._auto_rule_get("HTOE_22kW_DV")
    assert rule.version == 2 and trace in rule.excluded and rule.values == {"TESTLAUF": "PV"}
    assert len(rule.deselected) == 1
    assert (out / "PV_HTOE_22kW" / "Precon" / "DUT1").is_dir() and not (out / "PV_HTOE_22kW" / "AC_22kW_3ph_615V" / "DUT2").exists()
    ev = app._auto_eval()
    assert ev["rule"] == "HTOE_22kW_DV" and s[app.auto_rule]["value"] == "HTOE_22kW_DV"
    jobs = app._auto_eval_jobs()
    assert len(jobs) == 4 and all(j["rule"] == "HTOE_22kW_DV" and j["folders"] for j in jobs)
    assert {app._auto_mode_name(j) for j in jobs} == {"AC_22kW_3ph_615V", "DC_Charge_V2L_540V", "Precon"}
    info = s[app.auto_info]["value"]
    assert str(setup) in info and "15 Dateien ausgeschlossen" not in info and "Dateien ausgeschlossen" in info
    # erneut öffnen: Bearbeiten-Hinweis
    s[app.auto_name]["value"] = ""
    app.open_dir_window(from_auto=True)
    assert "BEARBEITEN" in s[app.dir_mode_text]["value"] and s[app.dir_template]["value"].startswith("{Testlauf}")


def test_dir_manager_save_errors_in_popup(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path, duts=("DUT1",), modes=("Precon",))
    app = env.app
    s = env.state.items
    blocker = tmp_path / "datei"
    blocker.write_text("x")                                   # Zielbasis ist eine Datei -> anlegen unmöglich
    open_manager(app, env, "R", setup, blocker)
    assert app.dir_save_rule() is False
    assert s["dir_error"]["show"] is True and "nicht angelegt" in s[app.dir_error_text]["value"]
    s["dir_error"]["show"] = False
    s[app.dir_base]["value"] = ""
    assert app.dir_save_rule() is False and "Basis Zielordner fehlt" in s[app.dir_error_text]["value"]
    assert app._auto_rule_get("R") is None


def test_modes_dropdown_grouped_goal_hhmmss_and_step2(env, tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path, modes=("AC_22kW_3ph_615V", "AC_11kW_1ph_230V", "DC_Charge_V2L_540V", "Precon"),
                       rows=30)
    app = env.app
    s = env.state.items
    open_manager(app, env, "E", setup, tmp_path / "out")
    assert app.dir_save_rule()
    assert app.auto_finish_step(1) is True
    app.open_auto_modes()                                                       # eigenes Fenster mit den Modes
    assert s["auto_modes_window"]["show"] is True
    boxes = [i for i in s.values() if i.get("kind") == "add_checkbox" and i.get("label") == "Precon"]
    assert boxes and boxes[-1]["value"] is True
    nodes = [i["label"] for i in s.values() if i.get("kind") == "add_tree_node" and i.get("parent")
             and s.get(i["parent"], {}).get("tag") == app.auto_modes_box or i.get("parent") == app.auto_modes_box]
    assert "AC (2)" in nodes and "DC_Charge (1)" in nodes and "Precon (1)" in nodes        # ähnliche Namen gruppiert
    assert set(app.auto_mode_rows) == {"AC_22kW_3ph_615V", "AC_11kW_1ph_230V", "DC_Charge_V2L_540V", "Precon"}
    # leere Zielzeit = unendlich: kein Fehler mehr, Hinweis in der Zeile
    assert "4 verarbeiten, 4 ohne Zielvorgabe (unendlich)" in s[app.auto_modes_text]["value"]
    assert s[app.auto_mode_rows["Precon"][4]]["value"] == "unendlich - keine Violation möglich"
    app._auto_mode_goal("Precon", "07:18:26")
    assert {j["target_time"] for j in app._auto_rule_jobs(mode="Precon")} == {"7h 18m 26s"}
    assert app._goal_hms("7h 18m 26s") == "07:18:26" and app._goal_hms("26306") == "26306"
    app._auto_mode_goal("AC_22kW_3ph_615V", "25:61:00")                         # ungültig
    assert s[app.auto_mode_rows["AC_22kW_3ph_615V"][2]]["value"] == "hh:mm:ss erwartet"
    app._auto_mode_toggle("AC_22kW_3ph_615V", False)                            # nicht verarbeiten: keine Zielzeit nötig
    app._auto_mode_toggle("AC_11kW_1ph_230V", False)
    s[app.auto_modes_goal_all]["value"] = "24:00:00"
    app._auto_modes_goal_all()                                                  # alle angehakten
    assert {j["target_time"] for j in app._auto_rule_jobs(mode="DC_Charge_V2L_540V")} == {"24h"}
    assert not app._auto_rule_jobs(mode="AC_11kW_1ph_230V")[0]["target_time"]
    assert "2 verarbeiten, 0 ohne Zielvorgabe (unendlich)" in s[app.auto_modes_text]["value"]
    assert app.auto_finish_step(2) is True
    # Schritt 3: Analyse über alle angehakten Modes und DUTs
    app.analyze_auto_source()
    end = time.time() + 20
    while (app.auto_analysis is not None or app.auto_batch) and time.time() < end:
        app.tick()
        time.sleep(0.01)
    cfg = app.limit_cfg
    assert set(cfg.modes) == {"Precon", "DC_Charge_V2L_540V"}
    assert cfg.modes["Precon"].steps_text() == "24h"                        # "für alle angehakten" galt auch hier
    assert "4 Auswertungen in 2 Modes" in s[app.status]["value"]


def test_result_file_in_target_directory_with_own_name(env, tmp_path, monkeypatch):
    import json
    import time
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path, modes=("AC_22kW_3ph_615V", "Precon"), rows=20)
    out = tmp_path / "out"
    app = env.app
    s = env.state.items
    open_manager(app, env, "E", setup, out)
    assert app.dir_save_rule()
    for mode in ("AC_22kW_3ph_615V", "Precon"):
        app._auto_mode_goal(mode, "01:00:00")
    # Standard: Zielverzeichnis\Time_counter.json (nicht im erweiterten Ordner je Mode/DUT)
    assert app._auto_json_path() == str(out / "Time_counter.json")
    assert {app._auto_json_path(j) for j in app._auto_eval_jobs()} == {str(out / "Time_counter.json")}
    # ungültiger Name: Hinweis, alter Name bleibt
    s[app.auto_json]["value"] = "a/b.json"
    assert app._auto_read_form() is False and "Dateiname ungültig" in s[app.auto_json_note]["value"]
    assert app.auto_settings.json_name == "Time_counter.json"
    # eigener Name, .json wird ergänzt
    s[app.auto_json]["value"] = "HTOE_time_counter"
    assert app._auto_read_form() is True and s[app.auto_json_note]["value"] == ""
    assert app.auto_settings.json_name == "HTOE_time_counter.json"
    assert s[app.auto_json_where]["value"] == "= " + str(out / "HTOE_time_counter.json")
    app.start_auto()
    end = time.time() + 20
    while (app.auto_last is None or app.auto_future is not None) and time.time() < end:
        app.tick()
        time.sleep(0.01)
    app.stop_auto()
    data = json.loads((out / "HTOE_time_counter.json").read_text())
    assert any("Precon" in k for k in data) and any("AC_22kW_3ph_615V" in k for k in data)   # alle Modes, eine Datei
    assert not list(out.rglob("Time_counter.json"))
    assert app.settings["auto"]["json_name"] == "HTOE_time_counter.json"
    app._auto_json_default()
    assert app.auto_settings.json_name == "Time_counter.json"


def test_cycle_reads_only_selected_files_and_picks_up_new_folders(env, tmp_path, monkeypatch):
    import json
    import time
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path, duts=("DUT1",), modes=("Precon",), rows=20)
    out = tmp_path / "out"
    app = env.app
    s = env.state.items
    open_manager(app, env, "E", setup, out)
    skip = "DUT1/Report/Precon/Files/HTOE_PV_DES202507230117500130_Precon_DUT1_002.csv"
    app._dir_file_toggle(skip, False)
    assert app.dir_save_rule()
    app._auto_mode_goal("Precon", "01:00:00")

    def cycle():
        app.auto_last, app.auto_next = None, 0
        end = time.time() + 15
        while (app.auto_last is None or app.auto_future is not None) and time.time() < end:
            app.tick()
            time.sleep(0.01)
        return app.auto_last

    app.start_auto()
    first = cycle()
    assert [Path(p).name for p in first.new_files] == ["HTOE_PV_DES202507230117500130_Precon_DUT1_001.csv"]
    # neuer Mode-Ordner erscheint: wird beim nächsten Zyklus aufgenommen, Zielordner angelegt
    new = setup / "DUT1" / "Report" / "AC_22kW_3ph_615V" / "Files"
    new.mkdir(parents=True)
    (new / "A_001.csv").write_text("Zeit,U [V]\n" + "\n".join(f"2026-06-09 10:00:{i:02d},{i}" for i in range(10)) + "\n")
    cycle()
    assert any(j["rule_mode"] == "AC_22kW_3ph_615V" for j in app._auto_eval_jobs())
    assert (out / "DV_HTOE_22kW" / "AC_22kW_3ph_615V" / "DUT1").is_dir()
    app.stop_auto()
    data = json.loads(Path(app._auto_json_path()).read_text())
    assert any("Precon" in k for k in data)


def test_report_after_analysis_runs_cycle_first_and_waits(env, tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path, modes=("DC_Charge_V2L_540V", "Precon"), rows=30)
    out = tmp_path / "_TestResult"
    app = env.app
    s = env.state.items
    open_manager(app, env, "E", setup, out)
    s[app.dir_template]["value"] = "{Mode}_{DUTx}"
    app.dir_preview()
    assert app.dir_save_rule()

    def run(cond):
        end = time.time() + 30
        while cond() and time.time() < end:
            app.tick()
            time.sleep(0.01)

    app.open_report_window()                                   # noch keine Ausgaben, aber bereit -> angehakt
    assert all(s[box]["value"] for box, _j in app.report_boxes)
    assert "Zyklus läuft vor dem Report" in s[app.report_boxes[0][0]]["label"]
    app.create_report()
    assert app.auto_future is not None and "zuerst ein Zyklus für 4 Auswertungen" in s[app.status]["value"]
    run(lambda: app.auto_future is not None or app.report_pending or app.report_future is not None)
    reports = sorted(p.name for p in out.glob("Report_*.pdf"))
    assert len(reports) == 2 and re.fullmatch(r"Report_DC_Charge_V2L_540V_\d{8}_\d{6}\.pdf", reports[0])   # Report_{Mode}_{DateTime}
    assert "2 Reports erstellt" in s[app.status]["value"]
    for p in out.glob("Report_*.pdf"):
        p.unlink()
    app.run_auto_now()
    app.create_report()
    assert "nach dem laufenden Zyklus" in s[app.status]["value"]
    run(lambda: app.auto_future is not None or app.report_pending or app.report_future is not None)
    assert len(list(out.glob("Report_*.pdf"))) == 2


def test_auto_steps_lock_and_unlock(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    app = env.app
    s = env.state.items
    assert not any(r.get("label") == "Verzeichnisverwalter..." for r in s.values() if r.get("kind") == "menu_item")
    app.open_auto_window()
    assert app._auto_step() == 1
    assert s[app.auto_name]["enabled"] is True and s[app.auto_analyze_btn]["enabled"] is False   # Schritt 3 folgt
    assert s[app.auto_step_state[1]]["value"] == "[jetzt]" and s[app.auto_step_state[3]]["value"] == "[folgt]"
    assert app.auto_finish_step(1) is False                     # ohne Auswertung nicht abschließbar
    setup = make_halle(tmp_path, duts=("DUT1",), modes=("Precon",))
    open_manager(app, env, "E", setup, tmp_path / "out")
    assert app.dir_save_rule()
    assert app.auto_finish_step(1) is True
    assert s[app.auto_name]["enabled"] is False                                                  # 1 gesperrt
    assert s[app.auto_modes_btn].get("enabled", True) is True                                    # Modes: immer offen
    assert s[app.auto_step_state[1]]["value"] == "[erledigt - gesperrt]"
    assert s[app.auto_step_reset[1]]["show"] is True and s[app.auto_step_reset[2]]["show"] is False
    app._auto_mode_goal("Precon", "02:00:00")
    app.auto_finish_step(2)
    assert s[app.auto_analyze_btn]["enabled"] is True and s[app.auto_modes_btn].get("enabled", True) is True
    assert app.auto_finish_step(3) is False                      # noch nicht analysiert
    app.auto_reset_step(2)                                       # Schritt 2 und folgende zurücksetzen
    assert app._auto_step() == 2 and s[app.auto_name]["enabled"] is False
    assert s[app.auto_analyze_btn]["enabled"] is False and "Schritt 2 und folgende" in s[app.status]["value"]
    app.auto_finish_step(2)
    app.auto_reset_steps()                                       # Zurücksetzen: wieder Schritt 1
    assert app._auto_step() == 1 and s[app.auto_name]["enabled"] is True
    for step in (1, 2):
        app.auto_finish_step(step)
    app.start_auto()                                             # Durchlauf gestartet: alles frei
    assert app._auto_step() == 0 and s[app.auto_name]["enabled"] is True and s[app.auto_analyze_btn]["enabled"] is True
    assert s[app.auto_step_reset[4]]["show"] is True
    app.auto_reset_step(4)                                       # Schritt 4 zurücksetzen: Zyklus stoppt
    assert not app.auto_running and app._auto_step() == 4


def test_no_duplicates_in_limiter_report_and_jobs(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    import time
    setup = make_halle(tmp_path, modes=("Precon",))
    app = env.app
    open_manager(app, env, "E", setup, tmp_path / "out")
    assert app.dir_save_rule()
    app.auto_jobs.append(dict(app.auto_jobs[0], name="Kopie"))  # Doppel (gleiche Quelle und Ziel)
    assert app._auto_dedupe() == 1 and len(app.auto_jobs) == 2
    app.analyze_auto_source()
    end = time.time() + 20
    while (app.auto_analysis is not None or app.auto_batch) and time.time() < end:
        app.tick()
        time.sleep(0.01)
    app.open_limiter_window()
    names = list(app._lim_sources())
    assert len(names) == len({n.casefold() for n in names})
    assert len(app.lim_xfer_boxes) == len(set(app.lim_xfer_boxes))
    app.auto_jobs.append(dict(app.auto_jobs[0], name="Gleiches Ziel", source=str(tmp_path)))
    app.open_report_window()
    targets = [j["target"] for _b, j in app.report_boxes]
    assert len(targets) == len(set(targets)) == 2                  # gleiches Zielverzeichnis nur einmal


def test_legacy_rule_v1_still_usable(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    root = tmp_path / "H"
    make_tree(root)
    app = env.app
    s = env.state.items
    app.settings["auto_dirrules"] = {"rules": [dirrules.Rule(name="Alt", root=str(root), pattern="DUT*\\Report\\*",
                                                             template="{MODE}_{DUT}", base=str(tmp_path / "o")).to_dict()]}
    app.open_auto_window()
    s[app.auto_name]["value"] = "E"
    app.auto_create_eval()
    app._auto_set_rule("Alt")
    jobs = app._auto_eval_jobs()
    assert len(jobs) == 4 and {j["rule_mode"] for j in jobs} == {"EU_AC_3ph_22kW_705V", "EU_AC_1ph_11kW_400V"}
    app.open_dir_window(from_auto=True)                       # alte Regel im neuen Verwalter: Vorschlag
    assert "BEARBEITEN" in s[app.dir_mode_text]["value"] and s[app.dir_template]["value"] == "{Mode}\\{DUTx}"


def test_step4_opens_in_own_window_after_step3(env, tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    app = env.app
    s = env.state.items
    setup = make_halle(tmp_path, duts=("DUT1",), modes=("Precon",), rows=20)
    open_manager(app, env, "E", setup, tmp_path / "out")
    assert app.dir_save_rule()
    assert s["auto_run_window"]["show"] is False and s[app.auto_run_open_btn]["enabled"] is False
    app.auto_finish_step(1)
    app._auto_mode_goal("Precon", "01:00:00")
    app.auto_finish_step(2)
    app.analyze_auto_source()
    end = time.time() + 10
    while (app.auto_analysis is not None or app.auto_batch) and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert app.auto_finish_step(3) is True
    assert s["auto_run_window"]["show"] is True and s["auto_window"]["show"] is True     # Auto-Fenster bleibt
    assert s[app.auto_run_open_btn]["enabled"] is True and s[app.auto_start_btn]["enabled"] is True
    assert s[app.auto_run_step_state]["value"] == "[jetzt]"
    s["auto_run_window"]["show"] = False
    app.open_auto_run_window()
    assert s["auto_run_window"]["show"] is True
    app.run_auto_now()
    while app.auto_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert app.auto_jobs and s[app.auto_table]


def test_user_structure_dv_htoe_csv_serial_modes_in_file_names(env, tmp_path, monkeypatch):
    """...\\DV\\HTOE22kW\\CSV\\DES...\\DES..._AC_22kW_3ph_615V.csv: Mode steht nur im Dateinamen."""
    import json
    import time
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    root = tmp_path / "Messung" / "DV"
    folder = root / "HTOE22kW" / "CSV" / "DES202507230117500132"
    folder.mkdir(parents=True)
    rows = "\n".join(f"2026-06-09 10:00:{i:02d},{700 + i}" for i in range(20))
    names = ["DES202507230117500132_.csv", "DES202507230117500132_AC_22kW_3ph_615V.csv",
             "DES202507230117500132_AC_22kW_3ph_725V.csv", "DES202507230117500132_AC_22kW_3ph_800V.csv"]
    for name in names:
        (folder / name).write_text("Zeit,U [V]\n" + rows + "\n")
    assert dirrules.file_values(names[1]) == {"SERIENNUMMER": "DES202507230117500132", "MODE": "AC_22kW_3ph_615V"}
    assert dirrules.file_values(names[0]) == {"SERIENNUMMER": "DES202507230117500132"}
    assert dirrules.file_values("HTOE_PV_DES202609090470500176_AC_22kW_3ph_725V_DUT3_001.csv")["MODE"] == "AC_22kW_3ph_725V"
    assert dirrules.classify("HTOE22kW") == {"TESTVARIANTE": "HTOE22kW"}                  # nicht Mode
    out = tmp_path / "_TestResult"
    app = env.app
    s = env.state.items
    open_manager(app, env, "HTOE22kW_DV", root, out)
    struct = s[app.dir_struct]["value"]
    assert "Ebene 1: HTOE22kW" in struct and "{Test-Variante}" in struct and "{Seriennummer}" in struct
    assert "Dateinamen: AC_22kW_3ph_615V, AC_22kW_3ph_725V, AC_22kW_3ph_800V" in struct
    assert s[app.dir_ph_found["TESTLAUF"]]["value"] == "DV" and s[app.dir_ph_found["TESTVARIANTE"]]["value"] == "HTOE22kW"
    assert s[app.dir_ph_found["SERIENNUMMER"]]["value"] == "DES202507230117500132"
    assert s[app.dir_ph_found["MODE"]]["value"] == "AC_22kW_3ph_615V, AC_22kW_3ph_725V, AC_22kW_3ph_800V"
    assert s[app.dir_ph_found["DUT"]]["value"] == "nicht erkannt"
    assert s[app.dir_template]["value"] == "{Testlauf}_{Test-Variante}\\{Mode}\\{Seriennummer}"
    good = [u for _b, u in app.dir_unit_boxes]
    assert [u.key for u in good] == [os.path.join("DV_HTOE22kW", m, "DES202507230117500132")
                                     for m in ("AC_22kW_3ph_615V", "AC_22kW_3ph_725V", "AC_22kW_3ph_800V")]
    assert all(u.files == 1 and u.split for u in good)
    bad = [u for u in app.dir_units if u.error]
    assert len(bad) == 1 and bad[0].files == 1 and "{Mode}" in bad[0].error                # DES..._.csv ohne Mode
    assert app.dir_save_rule()
    jobs = app._auto_eval_jobs()
    assert len(jobs) == 3 and all(len(j["files"]) == 1 for j in jobs)
    app._auto_modes_all(True)
    for mode in app._auto_eval_modes():
        app._auto_mode_goal(mode, "01:00:00")
    app.run_auto_now()
    end = time.time() + 20
    while app.auto_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    data = json.loads(Path(app._auto_json_path()).read_text())
    assert {k for k in data if "AC_22kW_3ph_615V" in k} and {k for k in data if "AC_22kW_3ph_800V" in k}
    log = (out / "DV_HTOE22kW" / "AC_22kW_3ph_725V" / "DES202507230117500132" / "MessGraph_Auto.log").read_text()
    assert "AC_22kW_3ph_725V.csv" in log and "AC_22kW_3ph_615V.csv" not in log            # nur die eigene Datei


def test_report_only_current_evaluation_new_modes_included_no_foreign_folders(env, tmp_path, monkeypatch):
    """Nachstellung: alte Auswertung (Ziel ..._TestResult, gleiche Namen) + aktuelle (Projekt_Daten\\DV_HTOE22kW).
    Report nimmt nur die aktuelle Auswertung, auch Modes, die in der gespeicherten Auswahl nicht vorkamen."""
    import time
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path, modes=("Drive_V2L_705V", "AC_22kW_3ph_725V"), rows=30)
    out = tmp_path / "Projekt_Daten" / "DV_HTOE22kW"
    app = env.app
    s = env.state.items
    open_manager(app, env, "DV", setup, out)
    s[app.dir_template]["value"] = "{Mode}_{DUTx}"
    app.dir_preview()
    assert app.dir_save_rule()
    current = app._auto_eval_jobs()
    old_base = tmp_path / "MessGraph" / "_TestResult"
    app.auto_evals.append({"name": "Alt", "rule": ""})
    for job in current:                                         # alte Auswertung mit denselben Teilenamen
        app.auto_jobs.append(dict(job, evaluation="Alt", rule="", target=str(old_base / Path(job["target"]).name)))
    app.settings["auto_report"] = {"jobs": [j["name"] for j in current if "705V" in j["name"]]}  # alte Namenswahl
    app.open_report_window()
    assert s[app.report_eval]["value"] == "DV"
    assert {j["evaluation"] for _b, j in app.report_boxes} == {"DV"} and len(app.report_boxes) == len(current)
    assert all(s[b]["value"] for b, _j in app.report_boxes)     # neue Modes (725V) sind dabei
    app.create_report()
    end = time.time() + 40
    while (app.auto_future is not None or app.report_pending or app.report_future is not None) and time.time() < end:
        app.tick()
        time.sleep(0.01)
    reports = sorted(p.name for p in out.rglob("Report_*.pdf"))
    assert len(reports) == 2 and all(re.fullmatch(r"Report_(Drive_V2L_705V|AC_22kW_3ph_725V)_\d{8}_\d{6}\.pdf", r)
                                     for r in reports), reports
    assert not old_base.exists()                               # kein Zugriff auf fremde Zielordner
    assert app.settings["auto_report"]["evaluation"] == "DV" and "jobs" not in app.settings["auto_report"]
    # abgewählter DUT bleibt abgewählt, neue Teile der Auswertung bleiben gewählt; "Alle Auswertungen" zeigt beide
    s[app.report_boxes[0][0]]["value"] = False
    app._report_save_form()
    app.open_report_window()
    assert [s[b]["value"] for b, _j in app.report_boxes].count(False) == 1
    app._report_pick_eval("Alle Auswertungen")
    assert {j["evaluation"] for _b, j in app.report_boxes} == {"DV", "Alt"}
    assert app._report_selected("DV", app.settings["auto_report"].get("deselected"))  # Zeitplan: ohne Fenster


def test_step2_counter_kinds_apply_to_rule_data_and_new_duts(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    setup = make_halle(tmp_path, duts=("DUT1",), modes=("AC_22kW_3ph_615V", "Precon"))
    app = env.app
    s = env.state.items
    open_manager(app, env, "E", setup, tmp_path / "out")
    assert app.dir_save_rule()
    assert app.auto_finish_step(1) is True
    app.open_auto_modes()
    assert not any(i.get("label") == "Eigener Mode" for i in s.values())       # keine eigenen Modes mehr
    app._auto_mode_kind("Precon", "Flanke")
    app._auto_mode_goal("Precon", "25")
    app._auto_mode_kind("AC_22kW_3ph_615V", "Ignorieren")
    assert app.auto_finish_step(2) is False and "Zähler Flanke ohne Flanken bei: Precon" in s[app.status]["value"]
    app.auto_add_edge("U", upper=1.5, mode="Precon")
    assert app.auto_finish_step(2) is True and "Ohne Bewertung: AC_22kW_3ph_615V" in s[app.status]["value"]
    assert "Precon: 25 Flanken" in s[app.auto_modes_text]["value"]
    # nach Abschluss jederzeit änderbar: gilt sofort für die gewählten Daten
    app._auto_mode_kind("AC_22kW_3ph_615V", "Zeit")
    assert {j["goal_kind"] for j in app._auto_rule_jobs(mode="AC_22kW_3ph_615V")} == {"time"}
    # neuer DUT der Regel übernimmt Zähler und Ziel seines Modes
    folder = setup / "DUT2" / "Report" / "Precon" / "Files"
    folder.mkdir(parents=True)
    (folder / "HTOE_PV_DES202507230117500131_Precon_DUT2_001.csv").write_text(
        "Zeit,U [V],I [A]\n2026-06-09 10:00:00,1,1\n2026-06-09 10:00:01,2,2\n")
    app._auto_resync_rules()
    jobs = app._auto_rule_jobs(mode="Precon")
    assert len(jobs) == 2 and {j["goal_kind"] for j in jobs} == {"edges"} and {j["target_edges"] for j in jobs} == {"25"}
    assert app._auto_job_settings(jobs[-1]).edge_target == 25
