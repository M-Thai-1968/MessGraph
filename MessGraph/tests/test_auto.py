"""Auto-Auswertung: Verzeichnis zyklisch, Gruppen nach Zeitstempel, PNG, Time_counter.json."""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_gui_logic import env, wait  # noqa: E402,F401  (Fixture wiederverwenden)

from messgraph import auto, limitconfig, limiter  # noqa: E402


def write_part(path, start, seconds, volt, step=1.0):
    t0 = datetime(2026, 6, 9, 10, 0, 0) + timedelta(seconds=start)
    lines = ["Zeit,U_DC [V],I [A]"]
    for i in range(int(seconds / step)):
        stamp = t0 + timedelta(seconds=i * step)
        lines.append(f"{stamp:%Y-%m-%d %H:%M:%S},{volt(i):.2f},{10 + (i % 3)}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def config_yaml(path):
    Path(path).write_text(
        "limits:\n  modes:\n"
        "    Precon:\n      steps: 100\n      signals:\n        U_DC: {enabled: true, lower: 700, upper: 750}\n"
        "    Precon_3ph_725V:\n      steps: 1m 40s\n      signals:\n        U_DC: {enabled: true, lower: 715, upper: 735}\n"
        "    Andere:\n      steps: 10\n      signals:\n        Druck: {enabled: true, lower: 1, upper: 2}\n",
        encoding="utf-8")
    return limitconfig.load(str(path))


def manual(app, src, dst, name="Auswertung_1", goal="24h"):
    """Auswertung mit einem Quellordner (ohne Verzeichnisregel) im geöffneten Auto-Fenster."""
    app.open_auto_window()
    return app.auto_add_job(name, str(src), str(dst), target_time=goal)


@pytest.fixture
def folders(tmp_path):
    src, dst = tmp_path / "roh", tmp_path / "aus"
    src.mkdir()
    return src, dst


def test_group_names():
    assert auto.group_name("DES202606090470000043_DUT2_001") == "DES202606090470000043_DUT2"
    assert auto.group_name("Messung-2026-06-09_1015") == "Messung"
    assert auto.group_name("lauf_20260609T101500") == "lauf"
    assert auto.group_name("x_DUT3_part2") == "x_DUT3"
    assert auto.group_name("abc_DUT2_7", r"(\w+?_DUT\d+)_") == "abc_DUT2"
    assert auto.group_name("HTOE_PV_DES202609090470500176_AC_22kW_3ph_725V_DUT3") == "DES202609090470500176_DUT3"
    assert auto.group_name("A_DES12_x_DUT2", r"(DES\d+).*(DUT\d+)") == "DES12_DUT2"      # Gruppen mit _ verbunden


def test_cycle_groups_by_timestamp_counts_and_writes_outputs(folders):
    src, dst = folders
    # zweiter Teil zuerst geschrieben (Änderungszeit falsch herum), Zeitstempel in den Daten entscheiden
    write_part(src / "DES1_DUT2_002.csv", 100, 100, lambda i: 725.0)
    write_part(src / "DES1_DUT2_001.csv", 0, 110, lambda i: 690.0 if i < 20 else 720.0)   # 10 s Überlappung
    write_part(src / "DES1_DUT3_001.csv", 0, 50, lambda i: 740.0)
    config = config_yaml(src.parent / "grenzen.yaml")
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst), cycle_s=60, only_hits=False,
                                               one_group=False))
    r = engine.run_cycle(config)
    assert sorted(Path(p).name for p in r.new_files) == ["DES1_DUT2_001.csv", "DES1_DUT2_002.csv", "DES1_DUT3_001.csv"]
    group = next(g for g in engine.groups.values() if g.name == "DES1_DUT2")
    x, y = group.merged["U_DC"]
    assert x.size == 200 and np.all(np.diff(x) > 0)              # Überlappung nur einmal, sortiert
    c = r.counters
    assert c["count_Precon_DES1_DUT2"] == {"actual": 180, "actual_count": 180, "steps": 100, "fulfillment_percent": 180.0}
    assert c["count_Precon_3ph_725V_DES1_DUT2"]["actual_count"] == 180
    assert c["count_Precon_3ph_725V_DES1_DUT2"]["actual"] == pytest.approx(179.0)   # Zeitziel: Sekunden
    assert c["count_Precon_3ph_725V_DES1_DUT2"]["steps"] == 100
    assert c["count_Precon_DES1_DUT3"]["actual"] == 50 and "count_Precon_3ph_725V_DES1_DUT3" in c
    assert not any("Andere" in k for k in c)                     # Mode ohne passende Signale fehlt
    data = json.loads((dst / "Time_counter.json").read_text())
    assert data == c and set(next(iter(data.values()))) == {"actual", "actual_count", "steps", "fulfillment_percent"}
    pngs = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*.png"))
    assert pngs == ["DES1_DUT2/I_A.png", "DES1_DUT2/U_DC_V.png", "DES1_DUT3/I_A.png", "DES1_DUT3/U_DC_V.png"]
    assert (dst / "MessGraph_Auto.log").read_text().count("Zyklus 1") == 1

    # zweiter Zyklus: nichts neu -> nichts gelesen, keine Bilder
    r2 = engine.run_cycle(config)
    assert not r2.new_files and r2.png_written == 0 and r2.counters == c
    # neue Datei kommt dazu: nur diese wird gelesen, die Gruppe ergänzt
    write_part(src / "DES1_DUT2_003.csv", 200, 20, lambda i: 725.0)
    r3 = engine.run_cycle(config)
    assert [Path(p).name for p in r3.new_files] == ["DES1_DUT2_003.csv"] and r3.png_written == 2
    assert r3.counters["count_Precon_DES1_DUT2"]["actual"] == 200
    # Datei gelöscht: Gruppe ohne sie
    os.remove(src / "DES1_DUT3_001.csv")
    r4 = engine.run_cycle(config)
    assert r4.removed and "count_Precon_DES1_DUT3" not in r4.counters
    assert "count_Precon_DES1_DUT3" in json.loads((dst / "Time_counter.json").read_text())   # alte Einträge bleiben


def test_budget_spreads_work_over_cycles_and_logs(folders):
    src, dst = folders
    for n in range(4):
        write_part(src / f"G_{n:03d}.csv", n * 10, 10, lambda i: 720.0)
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst), cycle_s=10, png=False))
    ticks = iter(range(0, 10_000, 5))                           # jede Abfrage der Uhr: 5 s später
    r = engine.run_cycle(None, budget=6, clock=lambda: next(ticks))
    assert r.first and len(r.new_files) == 4 and r.deferred_files == 0   # erster Durchlauf: alles, ohne Budget
    engine.settings.png = True
    for n in range(4, 8):                                       # Folgedurchlauf: viele neue Dateien -> verteilt
        write_part(src / f"G_{n:03d}.csv", n * 10, 10, lambda i: 720.0)
    r = engine.run_cycle(None, budget=6, clock=lambda: next(ticks))
    assert r.collision and r.deferred_files > 0 and len(r.new_files) < 4
    assert "Zykluszeit zu kurz" in (dst / "MessGraph_Auto.log").read_text()
    for _ in range(10):
        if not (r.deferred_files or r.deferred_png):
            break
        r = engine.run_cycle(None, budget=1e9)
    assert sum(len(g.files) for g in engine.groups.values()) == 8 and not r.collision


def test_proposal_without_config_and_limiter(folders):
    src, dst = folders
    write_part(src / "R_001.csv", 0, 100, lambda i: 725.0 if (i // 10) % 2 else 0.0)
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst), png=False))
    r = engine.run_cycle(None)
    proposal = r.proposal
    assert proposal is not None and list(proposal.modes) == ["Auto"]
    lo, hi = proposal.modes["Auto"].signals["U_DC"]
    assert lo < 0 < 725 < hi and proposal.modes["Auto"].steps_time == 24 * 3600
    assert r.counters["count_Auto_R"]["actual_count"] == 100 and not list(dst.rglob("*.png"))
    lim = limiter.LimiterConfig([limiter.Rule("R*", "U_DC", 700, None)])
    engine2 = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst / "b"), png=False))
    r2 = engine2.run_cycle(proposal, lim)
    assert r2.counters["count_Auto_R"]["actual_count"] == 50       # nur der obere Anteil zählt
    assert any("Limiter" in n for n in r2.notes)


def test_errors_and_missing_folder(folders):
    src, dst = folders
    (src / "kaputt.csv").write_text("nur text\nohne zahlen\n")
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    r = engine.run_cycle(None)
    assert r.errors and not r.counters
    assert not engine.run_cycle(None).errors                       # unveränderte kaputte Datei nicht erneut
    engine.settings.source = str(src / "fehlt")
    with pytest.raises(Exception, match="nicht gefunden"):
        engine.run_cycle(None)


def test_gui_auto_runs_cycle_proposes_config_and_skips_on_collision(env, folders):
    src, dst = folders
    write_part(src / "D_001.csv", 0, 60, lambda i: 725.0)
    app = env.app
    manual(app, src, dst)
    env.state.items[app.auto_cycle]["value"] = "abc"
    assert not app._auto_read_form() and "ungültig" in env.state.items[app.auto_hint]["value"]
    env.state.items[app.auto_cycle]["value"] = "2m"
    assert app._auto_read_form() and app.auto_settings.cycle_s == 120
    assert app.settings["auto"]["jobs"][0]["source"] == str(src)
    app.start_auto()
    assert app.auto_running
    end = time.time() + 10
    while app.auto_last is None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert app.auto_last is not None and app.limit_cfg is not None and app.limit_cfg.modified
    assert env.state.items["limit_editor"]["show"] is True           # Vorschlag zum Bearbeiten
    assert "count_Auswertung_1_D" in json.loads((dst / "Time_counter.json").read_text())
    rows = env.state.items[app.auto_table]["children"]
    assert rows and app.auto_next > time.monotonic() + 60
    # Kollision: Zyklus fällig, der vorige läuft noch -> übersprungen und protokolliert
    class Busy:
        def done(self):
            return False
    app.auto_future, app.auto_next = Busy(), 0
    app._poll_auto()
    assert "übersprungen" in (dst / "MessGraph_Auto.log").read_text()
    app.auto_future = None
    app.stop_auto()
    assert not app.auto_running


def test_only_modes_with_hits(folders):
    src, dst = folders
    write_part(src / "DES1_DUT2_001.csv", 0, 30, lambda i: 740.0)            # nur Precon trifft, 3ph_725V nicht
    config = config_yaml(src.parent / "grenzen.yaml")
    r = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst))).run_cycle(config)
    assert list(r.counters) == ["count_Precon_DES1_DUT2"]


def test_single_mode_for_all_files(folders):
    src, dst = folders
    write_part(src / "DES1_DUT2_001.csv", 0, 30, lambda i: 725.0)
    config = config_yaml(src.parent / "grenzen.yaml")
    r = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst))).run_cycle(config, mode="Precon_3ph_725V")
    assert list(r.counters) == ["count_Precon_3ph_725V_DES1_DUT2"]


def test_analyze_lists_all_signals_and_proposes(folders):
    src, _dst = folders
    write_part(src / "A_001.csv", 0, 50, lambda i: 720.0 + i % 5)
    write_part(src / "B_001.csv", 0, 50, lambda i: 730.0)
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src)))
    stats, result = engine.analyze()
    assert sorted(stats) == ["I", "U_DC"] and len(stats["U_DC"]["files"]) == 2 and not result.errors
    assert stats["U_DC"]["min"] == 720.0 and stats["U_DC"]["max"] == 730.0
    config = auto.AutoEngine.propose_from_stats(stats)
    mode = config.modes["Auto"]
    assert mode.steps_time == 24 * 3600 and mode.steps_text() == "24h"
    assert all(e.enabled for e in mode.entries.values()) and set(mode.entries) == {"I", "U_DC"}
    lo, hi = mode.signals["U_DC"]
    assert lo < 720 and hi > 730


def test_gui_choosing_source_folder_fills_configurator(env, folders):
    src, dst = folders
    write_part(src / "DES202609090470500176_X_DUT3_001.csv", 0, 40, lambda i: 725.0)
    app = env.app
    manual(app, src, src.parent / "aus")
    app.analyze_auto_source()
    end = time.time() + 10
    while (app.auto_analysis is not None or not app.auto_stats) and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert set(app.auto_stats) == {"U_DC", "I"}
    assert set(app.auto_mode_stats["Auswertung_1"]) == {"U_DC", "I"}                # für "alle Modes vorschlagen"
    assert app.auto_mode_stats["Auswertung_1"]["U_DC"][2:] == (725.0, 725.0)
    assert app.limit_cfg is not None and list(app.limit_cfg.modes) == ["Auswertung_1"] and app.cfg_mode == "Auswertung_1"
    mode = app.limit_cfg.modes["Auswertung_1"]
    assert mode.steps_text() == "24h" and all(e.enabled for e in mode.entries.values())
    assert env.state.items["limit_editor"]["show"] is True
    names = [r[0] for r in app._le_signals()]
    assert {"U_DC", "I"} <= set(names)                           # Signale des Quellordners im Konfigurator
    row = next(r for r in app._le_signals() if r[0] == "U_DC")
    assert row[3] == 725.0 and "Auto: 1 Dateien" in row[2]
    app._le_edit(None, False, ("I", "enabled"))                  # Signal deaktivieren
    assert not mode.entries["I"].enabled
    # mit vorhandener Konfiguration bleibt sie, nur der Mode wird gewählt
    config = config_yaml(src.parent / "g.yaml")
    app.limit_cfg = config
    app._auto_job()["mode"] = "Precon"                           # Mode der Konfiguration statt Name
    assert app._auto_mode() == "Precon"
    app.analyze_auto_source()
    end = time.time() + 10
    while app.auto_analysis is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert app.limit_cfg is config and app.le_edit_mode == "Precon"
    assert "ohne Eintrag" in env.state.items[app.status]["value"]


def test_forced_cycle_and_config_change_reevaluate(folders):
    src, dst = folders
    write_part(src / "DES1_DUT2_001.csv", 0, 30, lambda i: 725.0)
    config = config_yaml(src.parent / "grenzen.yaml")
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    engine.run_cycle(config, mode="Precon")
    r = engine.run_cycle(config, mode="Precon")
    assert not r.new_files and r.png_written == 0                 # nichts neu, nichts geändert
    r = engine.run_cycle(config, mode="Precon", force=True)
    assert r.forced and r.png_written == 2 and r.json_path        # von Hand: alles neu
    config.modes["Precon"].set_entry("U_DC", True, 730, 750)       # Konfiguration geändert -> neu bewertet
    r = engine.run_cycle(config, mode="Precon")
    assert "count_Precon_DES1_DUT2" not in r.counters                # 725 V liegt nicht mehr in 730..750
    assert r.png_written == 2


def test_gui_run_now_processes_even_without_new_files(env, folders):
    src, dst = folders
    write_part(src / "D_001.csv", 0, 60, lambda i: 725.0)
    app = env.app
    manual(app, src, dst)
    for _round in range(2):                                       # zweimal: beim zweiten ist keine Datei neu
        app.auto_last = None
        app.run_auto_now()
        assert "wird ausgeführt" in env.state.items[app.status]["value"]
        end = time.time() + 10
        while app.auto_last is None and time.time() < end:
            app.tick()
            time.sleep(0.01)
        assert app.auto_last is not None and app.auto_last.forced and app.auto_last.png_written == 2
        assert "Zähler, Ergebnis" in env.state.items[app.status]["value"]
    assert (dst / "Time_counter.json").exists() and not app.auto_running


def test_find_stamps_and_file_start_variants(tmp_path):
    s = auto.find_stamps("date Tue Jun 9 10:15:30.250 am 2026")
    assert s["full"] == datetime(2026, 6, 9, 10, 15, 30, 250000)
    assert auto.find_stamps("Start: 09.06.2026 08:00:05;x")["full"] == datetime(2026, 6, 9, 8, 0, 5)
    assert auto.find_stamps("Messung_20260609_101500")["full"] == datetime(2026, 6, 9, 10, 15)
    assert auto.find_stamps("10:00:01,5;400")["clock"] == 36001.5
    assert auto.find_stamps("Datum: 2026-06-09")["date"] == datetime(2026, 6, 9)


def _rel(path, lines, preamble=(), header="t [s];U [V]"):
    Path(path).write_text("\n".join(list(preamble) + [header] + lines) + "\n", encoding="utf-8")


def test_one_evaluation_joined_by_detected_time_stamps(folders):
    src, dst = folders
    rows = lambda v: [f"{i};{v}" for i in range(10)]                      # relative Zeit 0..9 s
    # Vorspann mit Startzeit (Datei 2 beginnt 1 h nach Datei 1); absichtlich falsche Änderungszeiten
    _rel(src / "b.csv", rows(2), preamble=["Prüfstand 7", "Start: 09.06.2026 11:00:00", ""])
    _rel(src / "a.csv", rows(1), preamble=["Start: 09.06.2026 10:00:00"])
    # Uhrzeit-Spalte + Datum im Vorspann
    _rel(src / "c.csv", [f"12:00:{i:02d};3" for i in range(10)], preamble=["Datum: 09.06.2026"], header="Uhrzeit;U [V]")
    # Zeitstempel nur im Dateinamen
    _rel(src / "d_20260609_130000.csv", rows(4))
    os.utime(src / "a.csv", (2e9, 2e9))
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst), png=False))
    stats, result = engine.analyze()
    assert len(engine.groups) == 1                                         # eine Auswertung
    sources = {Path(p).name: d.time_source for g in engine.groups.values() for p, d in g.files.items()}
    assert sources["a.csv"] == "Vorspann" and sources["d_20260609_130000.csv"] == "Dateiname"
    assert "Uhrzeit" in sources["c.csv"]
    r = engine.run_cycle(None)
    group = next(iter(engine.groups.values()))
    x, y = group.merged["U"]
    values = [v for v in y.tolist() if v == v]
    assert values == [1] * 10 + [2] * 10 + [3] * 10 + [4] * 10           # zeitlich richtig, nicht nach Name/mtime
    assert np.all(np.diff(x) > 0) and np.isnan(y).sum() == 3               # Lücken zwischen den Dateien getrennt
    assert x[0] == auto._wall(datetime(2026, 6, 9, 10, 0, 0))
    log = (dst / "MessGraph_Auto.log").read_text()
    assert "a.csv: Start 09.06.2026 10:00:00.000 (Vorspann)" in log


def test_one_evaluation_with_different_signals_and_mtime_fallback(folders):
    src, dst = folders
    _rel(src / "x_1.csv", [f"{i};5" for i in range(5)], header="t [s];U [V]")
    _rel(src / "x_2.csv", [f"{i};7" for i in range(5)], header="t [s];T [°C]")
    os.utime(src / "x_1.csv", (1.7e9, 1.7e9))
    os.utime(src / "x_2.csv", (1.7e9 + 100, 1.7e9 + 100))
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst), png=False))
    r = engine.run_cycle(None)
    group = next(iter(engine.groups.values()))
    assert sorted(group.merged) == ["T", "U"] and group.name == "x"
    assert any("Änderungszeit" in n for n in r.notes)


def test_png_contents_trend_limits_text_and_alarm(folders, monkeypatch):
    src, dst = folders
    # Temperatur steigt 1 K je 100 s, Grenze 75 -> nach wenigen Minuten verletzt, Zielzeit 24h -> Violation
    lines = ["Zeit,T [°C],U [V]"] + [f"2026-06-09 10:{i // 60:02d}:{i % 60:02d},{40 + i / 100:.3f},{725:.1f}"
                                     for i in range(0, 1800, 10)]
    (src / "M_001.csv").write_text("\n".join(lines) + "\n")
    cfg = limitconfig.new_config("Auto")
    cfg.modes["Auto"].set_entry("T", True, 0, 75)
    cfg.modes["Auto"].set_entry("U", True, 700, 750)
    cfg.modes["Auto"].set_steps("24h")
    specs = []
    import messgraph.pngexport as pe
    real = pe.write_png
    monkeypatch.setattr(pe, "write_png", lambda path, spec, *a: specs.append(spec) or real(path, spec, *a))
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    engine.run_cycle(cfg, mode="Auto", reg_method="theilsen")
    by = {s.title.split(": ")[1]: s for s in specs}
    temp, volt = by["T [°C]"], by["U [V]"]
    assert [round(v[0]) for v in temp.limits] == [75, 0]                      # obere und untere Grenzlinie
    assert len(temp.regressions) == 1 and temp.alarm is True                   # Trendlinie, roter Hintergrund
    text = "\n".join(e[0] for e in temp.info)
    for part in ("Signal: T [°C]", "Limit_max: 75", "Limit_min: 0", "Trendlinie (gestrichelt): Regression (3)", "Robuste Regression (Theil-Sen)",
                 "m = 0.01 °C/s", "f(x) = 0.01 * x + 40", "Zielzeit: 24h", "Zeit bis Violation: 28m 30s", "Violation vor Zielzeit!"):
        assert part in text, part
    assert volt.alarm is False and "Keine Violation vor Zielzeit (OK)" in "\n".join(e[0] for e in volt.info)
    assert (dst / "M" / "T_C.png").stat().st_size > 1000


def test_progress_and_cancel(folders):
    src, dst = folders
    for n in range(5):
        write_part(src / f"P_{n:03d}.csv", n * 100, 50, lambda i: 720.0)
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    seen = []
    original = engine._step
    def spy(phase, done, total, name=""):
        seen.append((phase, done, total))
        if phase == "read" and done == 2:
            engine.cancel = True                                  # während des Lesens abbrechen
        original(phase, done, total, name)
    engine._step = spy
    r = engine.run_cycle(None)
    assert ("read", 0, 5) in seen and r.cancelled and r.deferred_files == 2
    assert engine.progress["phase"] == "" and not engine.cancel
    assert "Abgebrochen" in (dst / "MessGraph_Auto.log").read_text()
    seen.clear()
    r = engine.run_cycle(None, force=True)
    phases = [p for p, *_ in seen]
    assert "read" in phases and "png" in phases and "json" in phases and not r.cancelled


def test_gui_shows_progress_while_busy(env, folders):
    src, dst = folders
    app = env.app
    class Busy:
        def done(self):
            return False
    app.auto_engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    app.auto_engine.progress = {"phase": "png", "done": 4, "total": 10, "name": "G: U_DC"}
    app.auto_future = Busy()
    app._auto_progress()
    assert env.state.items[app.auto_progress_row]["show"] is True
    assert "Erzeuge Bilder 5/10: G: U_DC" in env.state.items[app.auto_progress]["overlay"]
    assert env.state.items[app.progress_row]["show"] is True and "Auto:" in env.state.items[app.progress_text]["value"]
    app._cancel_jobs()
    assert app.auto_engine.cancel is True
    app.auto_future = None
    app._auto_progress()
    assert env.state.items[app.auto_progress_row]["show"] is False and env.state.items[app.progress_row]["show"] is False


def test_gui_several_evaluations_own_name_goal_shared_result(env, tmp_path):
    src1, src2 = tmp_path / "q1", tmp_path / "q2"
    dst1, dst2 = tmp_path / "z1", tmp_path / "z2"
    src1.mkdir()
    src2.mkdir()
    write_part(src1 / "DES202609090470500176_A_DUT2_001.csv", 0, 60, lambda i: 725.0)
    write_part(src2 / "DES202609090470500177_B_DUT3_001.csv", 0, 30, lambda i: 640.0)
    app = env.app
    manual(app, src1, dst1, "Precon 725V", "2h")
    manual(app, src2, dst2, "Precon_615V", "100")              # Zielzeit als Schritte
    shared = tmp_path / "gesamt" / "Time_counter.json"
    env.state.items[app.auto_json]["value"] = str(shared)
    app._auto_read_form()
    app.auto_add_job("Auswertung_3", "", "")                    # unvollständig -> wird ausgelassen
    stored = app.settings["auto"]["jobs"]
    assert [j["name"] for j in stored] == ["Precon 725V", "Precon_615V", "Auswertung_3"]
    assert [e["name"] for e in app.settings["auto"]["evaluations"]] == ["Precon 725V", "Precon_615V", "Auswertung_3"]
    assert app._auto_check() and "ausgelassen - Auswertung_3" in env.state.items[app.status]["value"]
    app.run_auto_now()
    end = time.time() + 15
    while app.auto_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    data = json.loads(shared.read_text())                       # eine Ergebnisdatei für alle Auswertungen
    assert set(data) == {"count_Precon_725V_DES202609090470500176_DUT2", "count_Precon_615V_DES202609090470500177_DUT3"}
    assert data["count_Precon_725V_DES202609090470500176_DUT2"]["steps"] == 7200        # eigene Zielzeit 2h
    assert data["count_Precon_615V_DES202609090470500177_DUT3"]["steps"] == 100         # eigene Zielzeit 100 Schritte
    assert list(dst1.rglob("*.png")) and list(dst2.rglob("*.png"))                      # Bilder je Zielverzeichnis
    assert (dst1 / "MessGraph_Auto.log").exists() and (dst2 / "MessGraph_Auto.log").exists()
    assert set(app.limit_cfg.modes) == {"Precon_725V", "Precon_615V"}                    # je Auswertung ein Mode
    rows = env.gui.dpg.get_item_children(app.auto_table, 1)
    assert len(rows) == 2
    # Auswahl wechseln zeigt die Angaben der Auswertung; Löschen
    app.auto_pick_eval("Precon 725V")
    assert str(src1) in env.state.items[app.auto_info]["value"] and app._auto_job()["target_time"] == "2h"
    app.auto_pick_eval("Auswertung_3")
    app.auto_delete_eval()
    assert [j["name"] for j in app.auto_jobs] == ["Precon 725V", "Precon_615V"]
    # Neuaufbau der Oberfläche behält Auswertungen
    jobs = app.auto_jobs
    app._rebuild_ui()
    assert app.auto_jobs is jobs

def test_auto_settings_migrate_single_folder(env, tmp_path):
    app = env.app
    app.auto_jobs, app.auto_evals_loaded = [], False
    app.settings["auto"] = {"source": str(tmp_path), "target": str(tmp_path / "o"), "cycle_s": 30}
    app._auto_load_jobs()
    assert len(app.auto_jobs) == 1 and app.auto_jobs[0]["source"] == str(tmp_path)
    assert app.auto_jobs[0]["target_time"] == "24h"
    assert app.auto_evals == [{"name": "Auswertung_1", "rule": ""}] and app.auto_jobs[0]["evaluation"] == "Auswertung_1"


def _dut_folder(tmp_path, dut, volt, config, name):
    src, dst = tmp_path / f"q{dut}", tmp_path / f"z{dut}"
    src.mkdir()
    write_part(src / f"HTOE_DES20260909047050017{dut}_DcChrg_DUT{dut}_001.csv", 0, 120, lambda i: volt)
    auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst))).run_cycle(config, mode="Precon")
    return {"name": name, "source": str(src), "target": str(dst)}


def test_statistics_and_report_pdf(tmp_path):
    from messgraph import autoreport
    config = config_yaml(tmp_path / "g.yaml")
    jobs = [_dut_folder(tmp_path, 5, 725.0, config, "A"), _dut_folder(tmp_path, 6, 760.0, config, "B")]
    stats = json.loads(next(Path(jobs[0]["target"]).glob("*/statistics.json")).read_text())
    u = stats["signals"]["U_DC"]
    assert u["mean"] == 725.0 and u["lo"] == 700 and u["hi"] == 750 and u["mean_inside"] is True and u["png"] == "U_DC_V.png"
    duts, problems = autoreport.collect(jobs + [{"name": "leer", "target": str(tmp_path / "nichts")}])
    assert [d.label for d in duts] == ["DUT5", "DUT6"] and len(problems) == 1
    rows = {r["name"]: r for r in autoreport.summary_rows(duts)}
    assert rows["U_DC"]["means"] == ["725.0", "760.0"] and rows["U_DC"]["avg"] == "742.5"
    assert rows["U_DC"]["min_pct"] == "-2.36" and rows["U_DC"]["max_pct"] == "2.36"
    steps = []
    out = autoreport.build_report(str(tmp_path / "rep" / "Report"), duts,
                                  autoreport.ReportOptions(project="OneBox", mode="Precon"),
                                  progress=lambda d, total, text: steps.append((d, total)))
    assert out.endswith("Report.pdf") and steps[-1][0] == steps[-1][1]
    import subprocess
    subprocess.run(["qpdf", "--check", out], check=True, capture_output=True)
    text = subprocess.run(["pdftotext", "-raw", out, "-"], capture_output=True, text=True).stdout
    for part in ("Test Report", "Project: OneBox", "Mode: Precon", "Summary Comparison", "Signal Plot Comparison",
                 "Signal Comparison: U_DC", "U DC DUT5", "Mode: DES202609090470500175_DUT5", "Limit Max", "NOT RELEASED"):
        assert part in text, part
    images = subprocess.run(["pdfimages", "-list", out], capture_output=True, text=True).stdout.splitlines()[2:]
    objects = {line.split()[10] for line in images if line.strip()}
    assert len(objects) == 4 and len(images) == 8              # 2 Signale x 2 DUTs, je einmal eingebettet, zweimal gezeigt
    plain = autoreport.build_report(str(tmp_path / "ohne.pdf"), duts, autoreport.ReportOptions(watermark=False))
    text = subprocess.run(["pdftotext", "-raw", plain, "-"], capture_output=True, text=True).stdout
    assert "NOT RELEASED" not in text and "Summary Comparison" in text


def test_gui_report_window_selection_and_creation(env, tmp_path):
    config = config_yaml(tmp_path / "g.yaml")
    a = _dut_folder(tmp_path, 2, 725.0, config, "Dut2")
    b = _dut_folder(tmp_path, 3, 728.0, config, "Dut3")
    app = env.app
    app.auto_jobs = [dict(a, mode="", target_time="24h", enabled=True), dict(b, mode="", target_time="24h", enabled=True),
                     {"name": "ohne", "source": "", "target": "", "mode": "", "target_time": "24h", "enabled": True}]
    app.auto_sel = 0
    app.open_report_window()
    boxes = app.report_boxes
    assert [env.state.items[box]["value"] for box, _ in boxes] == [True, True, False]   # ohne Ausgaben: abgewählt
    assert env.state.items[app.report_watermark]["value"] is True                      # Wasserzeichen standardmäßig an
    env.state.items[boxes[1][0]]["value"] = False                                       # nur eine Auswertung
    env.state.items[app.report_project]["value"] = "OneBox"
    env.state.items[app.report_watermark]["value"] = False
    app.create_report()
    end = time.time() + 15
    while app.report_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    made = list(Path(a["target"]).glob("Report_Dut2_*.pdf"))                   # Report_<Mode>_<Zeit>
    assert len(made) == 1 and "Report erstellt" in env.state.items[app.status]["value"]
    out = made[0]
    import subprocess
    text = subprocess.run(["pdftotext", "-raw", str(out), "-"], capture_output=True, text=True).stdout
    assert "DUT2" in text and "DUT3" not in text and "NOT RELEASED" not in text
    app._report_select(False)
    app.create_report()
    assert "mindestens eine" in env.state.items[app.status]["value"]


def test_evaluation_name_create_pick_delete_and_hints(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.gui, "AUTO_BASE", tmp_path / "Test")
    app = env.app
    app.open_auto_window()
    items = env.state.items
    assert app.auto_evals == [] and "Name ist notwendig" in items[app.auto_name_hint]["value"]
    assert "Noch keine Auswertung" in items[app.auto_eval_hint]["value"]
    assert "Noch keine Verzeichnisregel" in items[app.auto_rule_hint]["value"]
    app.auto_create_eval()                                      # leerer Name, keine Auswertung: Hinweis
    assert "Name ist notwendig" in items[app.auto_name_hint]["value"] and not app.auto_evals
    items[app.auto_name]["value"] = "HTOE_22kW_DV"
    app.auto_create_eval()                                      # Anlegen
    assert [e["name"] for e in app.auto_evals] == ["HTOE_22kW_DV"] and items[app.auto_eval_combo]["value"] == "HTOE_22kW_DV"
    assert items[app.auto_eval_combo]["items"] == ["HTOE_22kW_DV"] and items[app.auto_eval_hint]["value"] == ""
    items[app.auto_name]["value"] = "Zweite"
    app.auto_create_eval()
    items[app.auto_name]["value"] = ""
    app.auto_create_eval()                                      # leer, aber Auswertungen da: Hinweis auf Auswahl
    assert "vorhandene Auswertung" in items[app.auto_name_hint]["value"]
    app.auto_pick_eval("HTOE_22kW_DV")
    assert items[app.auto_name]["value"] == "HTOE_22kW_DV" and app._auto_eval()["name"] == "HTOE_22kW_DV"
    assert not app.auto_finish_step(1) and "Verzeichnisregel" in items[app.status]["value"]
    app.auto_delete_eval()
    assert [e["name"] for e in app.auto_evals] == ["Zweite"] and app._auto_eval()["name"] == "Zweite"
    assert app._auto_start_dir("") == str(tmp_path / "Test") and (tmp_path / "Test").is_dir()
    for name in ("Precon 725V", "DUT_7", "X-DUT12"):
        assert app._auto_mode_name({"name": name}) == {"Precon 725V": "Precon_725V", "DUT_7": "DUT_7", "X-DUT12": "X"}[name]

def test_report_schedule_times_and_trigger(env, tmp_path):
    from datetime import datetime
    app = env.app
    assert app.parse_times("00:00:00, 6:30 18") == [(0, 0, 0), (6, 30, 0), (18, 0, 0)]
    with pytest.raises(ValueError):
        app.parse_times("25:00")
    now = datetime(2026, 11, 16, 7, 0, 0)
    assert app.next_report_time([(0, 0, 0), (6, 30, 0)], now) == datetime(2026, 11, 17, 0, 0, 0)
    assert app.next_report_time([(0, 0, 0), (18, 0, 0)], now) == datetime(2026, 11, 16, 18, 0, 0)
    config = config_yaml(tmp_path / "g.yaml")
    job = _dut_folder(tmp_path, 4, 725.0, config, "D4")
    app.auto_jobs = [dict(job, mode="", target_time="24h", enabled=True)]
    app.auto_sel = 0
    clock = [datetime(2026, 11, 16, 23, 59, 50)]
    app._now = lambda: clock[0]
    app.open_report_window()
    env.state.items[app.report_times]["value"] = "00:00:00"
    env.state.items[app.report_repeat]["value"] = "täglich"
    env.state.items[app.report_sched_on]["value"] = True
    app._report_schedule_changed()
    assert app.report_next_due == datetime(2026, 11, 17, 0, 0, 0)
    assert "Nächster Report: 17.11.2026 00:00:00 (täglich)" in env.state.items[app.report_next]["value"]
    app.tick()                                                   # noch nicht fällig
    assert app.report_future is None
    clock[0] = datetime(2026, 11, 17, 0, 0, 1)                   # Datenzyklus egal: Uhrzeit erreicht
    app.tick()
    end = time.time() + 15
    while app.report_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    made = list(Path(job["target"]).glob("Report_D4_20261117_0000*.pdf"))
    assert made and "Zeitplan" in env.state.items[app.status]["value"]
    assert app.report_next_due == datetime(2026, 11, 18, 0, 0, 0)          # täglich: nächster Tag
    env.state.items[app.report_repeat]["value"] = "einmalig"
    app._report_schedule_changed()
    clock[0] = datetime(2026, 11, 18, 0, 0, 2)
    app.tick()
    while app.report_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert app.report_next_due is None and env.state.items[app.report_sched_on]["value"] is False   # einmalig: aus
    env.state.items[app.report_times]["value"] = "99:00"
    env.state.items[app.report_sched_on]["value"] = True
    app._report_schedule_changed()
    assert "ungültig" in env.state.items[app.report_next]["value"]


def test_report_label_from_evaluation_name(tmp_path):
    from messgraph import autoreport
    config = config_yaml(tmp_path / "g.yaml")
    job = _dut_folder(tmp_path, 5, 725.0, config, "AC_11_22kW_1ph_615V_DUT9")
    duts, _ = autoreport.collect([job])
    assert [d.label for d in duts] == ["DUT9"]                  # Name ist führend vor dem Dateinamen (DUT5)


def test_save_dialog_for_folders_creates_parents(env, tmp_path):
    app = env.app
    made = []
    app._ask_save_path("Neuen Ordner anlegen", "Pfad:", str(tmp_path / "x"), made.append, folder=True)
    assert env.state.items[app.save_ok_btn]["label"] == "Anlegen"
    wanted = tmp_path / "Test" / "A" / "B"                         # Elternordner fehlt
    env.state.items[app.save_path]["value"] = str(wanted)
    app._save_dialog_ok()
    assert made == [str(wanted)] and env.state.items["save_dialog"]["show"] is False
    app._ask_save_path("Speichern unter", "Datei:", str(tmp_path / "fehlt" / "x.png"), lambda p: None)
    assert env.state.items[app.save_ok_btn]["label"] == "Speichern"   # normale Dateidialoge unverändert
    app._save_dialog_ok()
    assert "nicht gefunden" in env.state.items[app.save_note]["value"]

def test_limiter_editor_offers_auto_signals_and_manual_file(env, folders, tmp_path):
    src, dst = folders
    write_part(src / "DES202609090470500176_X_DUT3_001.csv", 0, 40, lambda i: 725.0)
    other = tmp_path / "extra" / "Manuell_001.csv"
    other.parent.mkdir()
    write_part(other, 0, 10, lambda i: 1.0)
    app = env.app
    assert not app.datasets
    manual(app, src, dst)
    app.analyze_auto_source()
    end = time.time() + 10
    while (app.auto_analysis is not None or not app.auto_stats) and time.time() < end:
        app.tick()
        time.sleep(0.01)
    app.open_limiter_window()                                    # ohne geladene Dateien: Auto-Signale wählbar
    sources = app._lim_sources()
    group = "DES202609090470500176_X_DUT3_001.csv"                 # eine Datei: Gruppe = Datei, nur einmal
    assert list(sources) == [group]
    rule = app.limiter.rules[0]
    assert rule.file == group and set(app._lim_signal_names(rule.file)) == {"U_DC", "I"}
    app._lim_set(0, "signal", "U_DC")
    app._lim_set(0, "lo", "700")
    assert app.limiter.rules[0].usable and app.limiter.rules[0].file == group
    app._lim_add()
    app._lim_read_files([str(other)])                            # manuell gewählte Datei -> leere Regel nutzt sie
    assert "Manuell_001.csv" in app._lim_sources() and set(app._lim_signal_names("Manuell_*.csv")) == {"U_DC", "I"}
    assert app.limiter.rules[1].file == "Manuell_001.csv" and app.limiter.rules[0].file == group
    assert not app.datasets                                      # nur Signalnamen gelesen, nichts geladen


def test_limiter_rule_on_group_name_applies_in_cycle(folders):
    from messgraph import limiter
    src, dst = folders
    write_part(src / "DES202609090470500176_X_DUT3_001.csv", 0, 100, lambda i: 725.0 if i < 50 else 600.0)
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    engine.analyze()
    group = next(iter(engine.groups.values())).name
    cfg = limiter.LimiterConfig(rules=[limiter.Rule(file=group, signal="U_DC", lo=700)])
    result = engine.run_cycle(None, cfg, force=True)
    assert any("Limiter" in str(n) and "% der Messzeit" in str(n) for n in result.notes), result.notes


def test_png_background_peak_yellow_both_violet(folders, monkeypatch):
    from messgraph import plotexport
    src, dst = folders
    # T: steigender Trend (Regression verletzt), P: flach mit Spitze über der Grenze, B: Trend + Spitze, U: ok
    rows = []
    for i in range(0, 1800, 10):
        p = 130.0 if i == 900 else 100.0
        rows.append(f"2026-06-09 10:{i // 60:02d}:{i % 60:02d},{40 + i / 100:.3f},{p:.1f},{40 + i / 100 + (60 if i == 600 else 0):.3f},725.0")
    (src / "M_001.csv").write_text("Zeit,T [°C],P [W],B [K],U [V]\n" + "\n".join(rows) + "\n")
    cfg = limitconfig.new_config("Auto")
    for name, lo, hi in (("T", 0, 75), ("P", 50, 120), ("B", 0, 75), ("U", 700, 750)):
        cfg.modes["Auto"].set_entry(name, True, lo, hi)
    cfg.modes["Auto"].set_steps("24h")
    specs = []
    import messgraph.pngexport as pe
    real = pe.write_png
    monkeypatch.setattr(pe, "write_png", lambda path, spec, *a: specs.append(spec) or real(path, spec, *a))
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    engine.run_cycle(cfg, mode="Auto", reg_method="theilsen")
    by = {s.title.split(": ")[1].split(" ")[0]: s for s in specs}
    assert by["T"].alarm_rgb == plotexport.ALARM_PLOT_RGB                     # nur Regression: hellrot
    assert by["P"].alarm_rgb == plotexport.PEAK_PLOT_RGB                      # nur Peak: hellgelb
    assert by["B"].alarm_rgb == plotexport.BOTH_PLOT_RGB                      # beides: hellviolett
    assert by["U"].alarm_rgb is None                                          # ok: weiß
    assert "Peaks außerhalb der Grenzen!" in "\n".join(e[0] for e in by["P"].info)
    stats = json.loads((dst / "M" / "statistics.json").read_text())
    assert stats["signals"]["P"]["peak_violated"] is True and stats["signals"]["U"]["peak_violated"] is False


def test_report_graphs_per_page(tmp_path):
    from messgraph import autoreport
    import subprocess
    config = config_yaml(tmp_path / "g.yaml")
    duts = autoreport.collect([_dut_folder(tmp_path, 5, 725.0, config, "X")])[0]
    assert autoreport.grid_layout(4) == (2, 2) and autoreport.grid_layout("2") == (2, 1)
    assert autoreport.grid_layout(7) == (3, 3)
    pages = {}
    for per in (9, 4, 2, 1):
        out = autoreport.build_report(str(tmp_path / f"r{per}.pdf"), duts, autoreport.ReportOptions(per_page=per))
        info = subprocess.run(["pdfinfo", out], capture_output=True, text=True).stdout
        pages[per] = int(next(l for l in info.splitlines() if l.startswith("Pages:")).split()[1])
    signals = len(duts[0].stats)                                              # 2 Signale
    assert signals == 2
    assert pages[9] == pages[4] == pages[2] and pages[1] == pages[2] + 1      # DUT-Teil: 2 Seiten statt 1


def _rect_with_peaks(path):
    # Rechteck: 100 s an (U = 725 mit Spitzen bis 900), 100 s aus (U = 0); I folgt
    rows = []
    for i in range(400):
        on = (i // 100) % 2 == 0
        u = (900.0 if i % 37 == 0 else 725.0 + (i % 5)) if on else 0.0
        rows.append(f"2026-06-09 10:{i // 60:02d}:{i % 60:02d},{u:.1f},{(50.0 if on else 0.0):.1f}")
    path.write_text("Zeit,U [V],I [A]\n" + "\n".join(rows) + "\n")


def test_analyze_with_limiter_proposes_limits_without_cut_parts(folders):
    from messgraph import limiter
    src, _dst = folders
    _rect_with_peaks(src / "R_001.csv")
    plain, _r = auto.AutoEngine(auto.AutoSettings(source=str(src))).analyze()
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src)))
    cfg = limiter.LimiterConfig(rules=[limiter.Rule(file="*", signal="U", lo=700, hi=800)])
    cut, _r = engine.analyze(cfg)
    assert plain["U"]["limited"] is None and abs(cut["U"]["limited"] - 0.485) < 0.01
    assert plain["U"]["min"] == 0.0 and cut["U"]["min"] >= 700 and cut["U"]["max"] <= 800
    lo_plain, hi_plain = auto.AutoEngine.suggest_limits(plain["U"]["values"])
    lo_cut, hi_cut = auto.AutoEngine.suggest_limits(cut["U"]["values"])
    assert lo_plain < 0 and lo_cut > 700 and hi_cut < 740                     # Grenzen eng um den Messbereich
    assert cut["I"]["min"] == 50.0                                            # gilt für alle Signale der Datei
    inactive = limiter.LimiterConfig(rules=cfg.rules, active=False)
    again, _r = auto.AutoEngine(auto.AutoSettings(source=str(src))).analyze(inactive)
    assert again["U"]["limited"] is None and again["U"]["min"] == 0.0


def test_gui_readjust_limits_with_limiter(env, folders):
    from messgraph import limiter
    src, _dst = folders
    _rect_with_peaks(src / "R_001.csv")
    app = env.app
    manual(app, src, _dst)

    def wait():
        end = time.time() + 10
        while app.auto_analysis is not None and time.time() < end:
            app.tick()
            time.sleep(0.01)

    app.analyze_auto_source()
    wait()
    mode = app.limit_cfg.modes[app._auto_mode()]
    assert mode.entries["U"].lower < 0                                        # ohne Limiter: Bereich inkl. 0 V
    app._le_edit(None, False, ("I", "enabled"))                               # I deaktiviert
    app.limiter = limiter.LimiterConfig(rules=[limiter.Rule(file="*", signal="U", lo=700, hi=800)])
    app._limiter_changed()
    assert "Grenzen neu vorschlagen" in env.state.items[app.auto_analysis_text]["value"]
    app.analyze_auto_source(readjust=True)
    wait()
    mode = app.limit_cfg.modes[app._auto_mode()]
    assert mode.entries["U"].lower > 700 and mode.entries["U"].upper < 740
    assert mode.entries["I"].enabled is False and mode.steps_text() == "24h"  # aktiv/inaktiv und Zielzeit bleiben
    assert "neu vorgeschlagen (mit Limiter)" in env.state.items[app.status]["value"]


def test_report_comparison_always_nine_per_page(tmp_path, monkeypatch):
    from messgraph import autoreport
    config = config_yaml(tmp_path / "g.yaml")
    duts = autoreport.collect([_dut_folder(tmp_path, 5, 725.0, config, "X")])[0]
    real, calls = autoreport._grid, []
    monkeypatch.setattr(autoreport, "_grid", lambda pdf, items, cols, rows, *a, **k: calls.append(
        ("cmp" if k.get("subheading") or (len(a) > 2 and a[2]) else "mode", cols, rows)) or real(pdf, items, cols, rows, *a, **k))
    for per in (9, 4, 2, 1):
        calls.clear()
        autoreport.build_report(str(tmp_path / f"c{per}.pdf"), duts, autoreport.ReportOptions(per_page=per))
        assert {c[1:] for c in calls if c[0] == "cmp"} == {(3, 3)}                # Vergleich immer 9 pro Seite
        assert {c[1:] for c in calls if c[0] == "mode"} == {autoreport.grid_layout(per)}


def test_reports_per_mode_with_all_duts(env, tmp_path):
    import subprocess
    from datetime import datetime
    config = config_yaml(tmp_path / "g.yaml")
    base = tmp_path / "_TestResult"
    base.mkdir()
    jobs = []
    for dut, mode in ((5, "DC_Charge"), (6, "DC_Charge"), (7, "Precon")):
        job = _dut_folder(tmp_path, dut, 725.0 + dut, config, f"{mode}_DUT{dut}")
        target = base / f"{mode}_DUT{dut}"
        Path(job["target"]).rename(target)
        jobs.append(dict(job, target=str(target), mode="", target_time="24h", enabled=True))
    app = env.app
    app.auto_jobs, app.auto_sel = jobs, 0
    app._now = lambda: datetime(2026, 11, 16, 15, 12, 30)
    app.open_report_window()
    assert all(env.state.items[box]["value"] for box, _j in app.report_boxes)
    app.create_report()
    end = time.time() + 30
    while app.report_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    names = sorted(p.name for p in base.glob("Report_*.pdf"))                   # gemeinsamer Ordner der Ziele
    assert names == ["Report_DC_Charge_20261116_151230.pdf"]
    assert (base / "Precon_DUT7" / "Report_Precon_20261116_151230.pdf").exists()   # ein DUT: dessen Ziel
    assert "2 Reports erstellt" in env.state.items[app.status]["value"]
    text = subprocess.run(["pdftotext", "-raw", str(base / names[0]), "-"], capture_output=True, text=True).stdout
    assert "Mode: DC_Charge" in text and "DUT5" in text and "DUT6" in text and "DUT7" not in text
    env.state.items[app.report_path]["value"] = str(tmp_path / "Reports")      # eigener Ausgabeordner
    app.create_report()
    while app.report_future is not None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert len(list((tmp_path / "Reports").glob("Report_*.pdf"))) == 2


def test_first_run_all_files_then_only_new_and_changed(folders):
    src, dst = folders
    for i in range(6):
        write_part(src / f"M_{i:03d}.csv", i * 100, 100, lambda k: 725.0)
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst), cycle_s=1))
    ticks = iter(range(0, 10 ** 6, 10))                     # jede Uhrabfrage +10 s: Budget sofort erschöpft
    first = engine.run_cycle(clock=lambda: next(ticks) * 1.0)
    assert first.first and len(first.new_files) == 6 and first.deferred_files == 0   # erster Durchlauf: alle
    second = engine.run_cycle(clock=lambda: next(ticks) * 1.0)
    assert not second.first and second.new_files == [] and second.png_written == 0    # nichts neu: nichts gelesen
    write_part(src / "M_006.csv", 600, 100, lambda k: 726.0)                          # neu
    time.sleep(0.01)
    write_part(src / "M_002.csv", 200, 120, lambda k: 727.0)                          # geändert (größer)
    (src / "M_005.csv").unlink()                                                      # gelöscht
    third = engine.run_cycle()
    assert sorted(Path(p).name for p in third.new_files) == ["M_002.csv", "M_006.csv"]
    assert [Path(p).name for p in third.removed] == ["M_005.csv"]
    log = Path(engine.log_path()).read_text(encoding="utf-8")
    assert "Erster Durchlauf: alle 6 Dateien" in log and "Folgedurchlauf: 2 neue/geänderte Dateien" in log
    forced = engine.run_cycle(force=True)                                             # Jetzt ausführen: neu bewerten,
    assert forced.new_files == [] and forced.png_written > 0                          # aber nichts neu lesen


def test_gui_cyclic_first_all_then_only_new(env, folders):
    src, dst = folders
    for i in range(3):
        write_part(src / f"D_{i:03d}.csv", i * 60, 60, lambda k: 725.0)
    app = env.app
    manual(app, src, dst)
    app._auto_read_form()
    app.start_auto()

    def cycle():
        app.auto_last, app.auto_next = None, 0                  # nächster Zyklus fällig
        end = time.time() + 15
        while app.auto_last is None and time.time() < end:
            app.tick()
            time.sleep(0.01)
        return app.auto_last

    first = cycle()
    assert len(first.new_files) == 3                             # erster Durchlauf: alle Dateien
    second = cycle()
    assert second.new_files == []                                # zweiter: nichts neu -> nichts gelesen
    write_part(src / "D_003.csv", 180, 60, lambda k: 726.0)
    third = cycle()
    assert [Path(p).name for p in third.new_files] == ["D_003.csv"]   # nur die neue Datei
    app.stop_auto()


def test_report_never_cancelled_incomplete_gets_appendix_and_err_suffix(tmp_path, monkeypatch):
    """Fehler führen nicht zum Abbruch: Report wird erzeugt, Anhang mit Begründung, Dateiname ..._err.pdf."""
    from messgraph import autoreport, safewrite
    import subprocess
    config = config_yaml(tmp_path / "g.yaml")
    jobs = [_dut_folder(tmp_path, 5, 725.0, config, "A"), _dut_folder(tmp_path, 6, 760.0, config, "B")]
    duts, problems = autoreport.collect(jobs + [{"name": "leer", "target": str(tmp_path / "nichts")}])
    names = sorted(duts[0].stats)
    (duts[0].folder / duts[0].stats[names[0]]["png"]).write_bytes(b"\x89PNG\r\n\x1a\nkaputt")   # kaputtes Bild
    (duts[1].folder / duts[1].stats[names[0]]["png"]).unlink()                                  # fehlendes Bild
    del duts[1].stats[names[1]]["png"]                                                         # Eintrag ohne Bild
    duts[1].stats["Broken"] = "kein dict"                                                      # unlesbare Kennwerte
    out = autoreport.build_report(str(tmp_path / "rep" / "Report.pdf"), duts, autoreport.ReportOptions(),
                                  cancel=lambda: True, issues=problems)                         # cancel wirkt nicht
    assert out.endswith("Report_err.pdf") and not (tmp_path / "rep" / "Report.pdf").exists()
    subprocess.run(["qpdf", "--check", out], check=True, capture_output=True)
    text = subprocess.run(["pdftotext", "-raw", out, "-"], capture_output=True, text=True).stdout
    for part in ("Summary Comparison", "Signal Plot Comparison", "INCOMPLETE REPORT", "Appendix: Incomplete Report",
                 "Image not embedded", "Image missing", "no image for", "values of Broken unreadable",
                 "leer: no outputs in", "(image missing)"):
        assert part in text, part
    assert "Mode: DES202609090470500176_DUT6" in text                            # Rest trotzdem vollständig
    assert "Section" not in text and "U DC DUT5" in text                         # Übersicht und Vergleich vollständig

    # keine Ausgaben: Deckblatt + Anhang
    empty = autoreport.build_report(str(tmp_path / "leer.pdf"), [], autoreport.ReportOptions(), issues=problems)
    assert empty.endswith("leer_err.pdf")
    text = subprocess.run(["pdftotext", "-raw", empty, "-"], capture_output=True, text=True).stdout
    assert "Test Report" in text and "No evaluation with outputs found" in text

    # Zielname nicht schreibbar: Ausweichname, Grund im Anhang
    real = safewrite.write_bytes
    def busy(path, data, *a, **k):
        if os.path.basename(path) == "voll_err.pdf":
            raise PermissionError("belegt")
        return real(path, data, *a, **k)
    monkeypatch.setattr(safewrite, "write_bytes", busy)
    other = autoreport.build_report(str(tmp_path / "voll.pdf"), duts[:1], autoreport.ReportOptions(watermark=False))
    assert os.path.basename(other).startswith("voll_") and other.endswith("_err.pdf")
    text = subprocess.run(["pdftotext", "-raw", other, "-"], capture_output=True, text=True).stdout
    assert "Report not writable as" in text and "belegt" in text


def test_gui_report_without_cancel_button_and_err_report(env, tmp_path):
    from messgraph import autoreport
    app = env.app
    app.open_report_window()
    assert not any(i.get("kind") == "add_button" and i.get("label") == "Abbrechen" and i.get("parent") ==
                   app.report_progress_row for i in env.state.items.values())
    calls = []
    real = autoreport.build_report
    def spy(path, duts, options, progress=None, cancel=None, issues=None):
        calls.append(issues)
        return real(path, duts, options, progress, issues=issues)
    import messgraph.gui as gui
    gui.autoreport.build_report = spy
    try:
        job = {"name": "Precon_DUT1", "source": "", "target": str(tmp_path / "leer")}
        (tmp_path / "leer").mkdir()
        assert app._start_report([job], {"path": str(tmp_path)})
        end = time.time() + 15
        while app.report_future is not None and time.time() < end:
            app.tick()
            time.sleep(0.01)
    finally:
        gui.autoreport.build_report = real
    made = list(tmp_path.glob("Report_*_err.pdf"))
    assert len(made) == 1 and calls and calls[0]
    assert "unvollständig (Endung _err" in env.state.items[app.status]["value"]


def test_serial_folders_get_own_groups_no_generic_csv_folder(tmp_path):
    """Z:\\...\\DV\\HTOE22kW\\CSV\\<Seriennummer>\\*.csv: je Seriennummer eine Gruppe und ein Bildordner, kein Ordner "CSV"."""
    src = tmp_path / "DV" / "HTOE22kW" / "CSV"
    dst = tmp_path / "aus"
    for n, serial in enumerate(("DES202507230117500132", "DES202507230117500133")):
        (src / serial).mkdir(parents=True)
        write_part(src / serial / f"{serial}_AC_22kW_3ph_615V.csv", n * 100, 30, lambda i: 725.0)
    config = config_yaml(tmp_path / "grenzen.yaml")
    engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(dst)))
    r = engine.run_cycle(config, mode="Precon_3ph_725V")
    assert sorted(r.counters) == ["count_Precon_3ph_725V_DES202507230117500132",
                                  "count_Precon_3ph_725V_DES202507230117500133"]
    assert not (dst / "CSV").exists()
    assert list((dst / "DES202507230117500132").glob("*.png")) and list((dst / "DES202507230117500133").glob("*.png"))
    # ohne Seriennummer-Ordner: Seriennummer aus dem Dateinamen statt des ganzen Namens bzw. "CSV"
    src2 = tmp_path / "x" / "CSV"
    src2.mkdir(parents=True)
    write_part(src2 / "HTOE_Report_IPB22kWBiDi_DS202608200479700017_2026_11_06_16_02_49_Drive_V2L_705V.csv", 0, 30,
               lambda i: 725.0)
    write_part(src2 / "HTOE_Report_IPB22kWBiDi_DS202608200479700017_2026_11_07_08_00_00_Drive_V2L_705V.csv", 40, 30,
               lambda i: 725.0)
    r2 = auto.AutoEngine(auto.AutoSettings(source=str(src2), target=str(tmp_path / "aus2"))).run_cycle(
        config, mode="Precon_3ph_725V")
    assert list(r2.counters) == ["count_Precon_3ph_725V_DS202608200479700017"]
    # nichtssagender Ordnername -> nächster sinnvoller Ordner darüber
    assert auto.meaningful_dir(str(tmp_path / "HTOE22kW" / "CSV")) == "HTOE22kW"
    assert auto.serial_of("a_DS202608200479700017_2026") == "DS202608200479700017" and auto.serial_of("DUT1_001") == ""


def test_result_table_readable_columns(env, folders):
    app = env.app
    cfg = config_yaml(folders[0].parent / "g.yaml")
    app.limit_cfg = cfg
    assert cfg.modes["Precon_3ph_725V"].target[0] == "s"                         # Zielzeit -> h:mm:ss
    job = {"evaluation": "DV", "name": "EU_AC_3ph_22kW_705V_DUT1", "rule_mode": "Precon_3ph_725V", "target": ""}
    cells = app._auto_cell_values(job, "count_Precon_3ph_725V_DES202507230117500132",
                                  {"actual": 651068.0, "actual_count": 66254, "steps": 86400,
                                   "fulfillment_percent": 753.6})
    assert cells == ["DV", "EU_AC_3ph_22kW_705V_DUT1", "Precon_3ph_725V", "DES202507230117500132", "180:51:08",
                     "24:00:00", "753.6 %"]
    counted = app._auto_cell_values(dict(job, rule_mode="Precon"), "count_Precon_X",
                                    {"actual": 3569100, "steps": 86400, "fulfillment_percent": 4130.9})
    assert counted[2:] == ["Precon", "X", "3.569.100", "86.400", "4130.9 %"]           # Schritte, kein 3.5691e+06
    app.open_auto_window()
    app._auto_fill_table([(job, "count_Precon_3ph_725V_DES1", {"actual": 10.0, "steps": 86400,
                                                               "fulfillment_percent": 0.0})])
    row = env.state.items[app.auto_table]["children"][-1]
    texts = [env.state.items[c].get("default_value") or env.state.items[c].get("value")
             for c in env.state.items[row]["children"]]
    assert "0:00:10" in texts and "DES1" in texts


def test_count_edges_rules():
    y = np.array([0] * 5 + [10] * 5 + [0] * 5 + [10] * 2 + [0] * 5 + [10] * 6 + [0] + [10] * 4 + [0] * 6 + [10] * 7,
                 dtype=float)
    # über Wert1 = 5, n = 5: Flanke 1 (5 oben, 5 unten), kurzer Ausreißer (2) zählt nicht, Flanke 2 trotz 1-Wert-Delle,
    # am Ende oben ohne Rückkehr -> offen
    assert auto.count_edges(y, 5, 5) == (2, True)
    assert auto.count_edges(y, 5, 1) == (4, True)                  # n = 1: jeder Ausflug zählt
    assert auto.count_edges(y, 5, 8) == (0, False)
    # unter Wert2: Anfang schon unten -> kein Unterschreiten, zählt nicht
    assert auto.count_edges(y, 5, 5, above=False) == (2, False)
    # Lücken (NaN zwischen Dateien) unterbrechen nicht
    gap = np.array([0, 0, 10, 10, np.nan, 10, 0, 0, 0], dtype=float)
    assert auto.count_edges(gap, 5, 3) == (1, False)
    assert auto.count_edges(np.array([np.nan]), 5, 1) == (0, False)


def test_edge_counter_cycle_writes_flanken_counter(folders):
    src, dst = folders
    pulse = lambda i: 800.0 if (i // 10) % 2 else 700.0             # noqa: E731  10 s oben, 10 s unten
    write_part(src / "DES1_DUT2_001.csv", 0, 60, pulse)
    write_part(src / "DES1_DUT2_002.csv", 60, 60, pulse)
    settings = auto.AutoSettings.from_dict({
        "source": str(src), "target": str(dst), "one_group": False, "edge_count": True,
        "edges": [{"signal": "U_DC", "upper": "750", "lower": "720,5", "n": 5, "target": 4},
                  {"signal": "I [A]", "upper": 11.5, "n": 1},
                  {"signal": "Druck", "upper": 1},
                  {"signal": "", "upper": 1}]})
    assert len(settings.edges) == 3 and settings.edges[0]["lower"] == 720.5
    assert auto.AutoSettings.from_dict(settings.to_dict()).edges == settings.edges
    engine = auto.AutoEngine(settings)
    r = engine.run_cycle(config_yaml(src.parent / "g.yaml"))
    c = r.counters
    u = c["edges_U_DC_DES1_DUT2"]
    # 120 s: oben 10..19, 30..39, ... 110..119 -> 6 Ausflüge über 750, der letzte ohne Rückkehr
    assert (u["edges_upper"], u["edges_lower"], u["pending"]) == (5, 5, True)
    assert u["actual"] == 10 and u["steps"] == 4 and u["fulfillment_percent"] == 250.0
    assert c["edges_I [A]_DES1_DUT2"]["edges_upper"] == 39          # I = 10, 11, 12, ...: jede 12 über 11.5
    assert not any(k.startswith("count_") for k in c)
    assert any("Druck" in n for n in r.notes)
    assert json.loads((dst / "Flanken_counter.json").read_text()) == c
    assert not (dst / "Time_counter.json").exists()


def test_gui_counter_per_mode_time_edge_ignore(env, folders):
    """Zähler je Mode in Schritt 2 (Zeit, Flanke, Ignorieren), gilt sofort für die gewählten Daten."""
    src, dst = folders
    write_part(src / "D_001.csv", 0, 60, lambda i: 800.0 if (i // 10) % 2 else 700.0)
    app = env.app
    job = manual(app, src, dst)
    s = env.state.items
    mode = app._auto_mode_name(job)
    app.open_auto_modes()
    row = app.auto_mode_rows[mode]
    assert s[row[3]]["value"] == "Zeit" and s[row[5]]["show"] is False
    assert app._auto_json_path(job).endswith("Time_counter.json")
    # Flanke: Knopf Flanken..., ohne Definition Hinweis und kein Abschluss/Start
    app._auto_mode_kind(mode, "Flanke")
    assert job["goal_kind"] == "edges" and s[row[5]]["show"] is True
    assert s["auto_edges_window"]["show"] is True and mode in s["auto_edges_window"]["label"]
    assert "Flanken fehlen" in s[row[2]]["value"]
    assert app._auto_json_path(job).endswith("Flanken_counter.json")
    assert not app._auto_check() and "Zähler Flanke ohne Flanken bei: " + mode in s[app.status]["value"]
    app.auto_add_edge()
    app._auto_edge_set(0, "upper", "abc")
    assert s[app.auto_edge_rows[0][1]]["value"] == "Signal fehlt"
    app._auto_edge_pick(0, "U_DC")
    assert "keine Zahl" in s[app.auto_edge_rows[0][1]]["value"]
    app._auto_edge_set(0, "upper", "750")
    app._auto_edge_set(0, "n", "3")
    assert s[app.auto_edge_rows[0][1]]["value"] == "" and s[row[2]]["value"] == ""
    assert "U_DC (> 750, n = 3)" in s[row[4]]["value"]
    assert app._auto_eval()["mode_edges"][mode][0]["signal"] == "U_DC"
    settings = app._auto_job_settings(job)
    assert settings.edge_count and not settings.no_eval and settings.edges[0]["signal"] == "U_DC"
    app.auto_last = None
    app.run_auto_now()
    end = time.time() + 10
    while app.auto_last is None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert app.auto_last.counters["edges_U_DC_D"]["edges_upper"] == 2       # 3. Ausflug ohne Rückkehr: offen
    assert (dst / "Flanken_counter.json").exists() and not (dst / "Time_counter.json").exists()
    cells = app._auto_cell_values(job, "edges_U_DC_D", app.auto_last.counters["edges_U_DC_D"])
    assert cells[2:5] == ["U_DC", "D", "2 (+1 offen)"]
    assert "über Wert1 = 750: 2 Flanken" in app._edge_tip(app.auto_last.counters["edges_U_DC_D"])
    # Ignorieren: keine Bewertung, aber verarbeitet (Bilder), kein Zähler, keine Ergebnisdatei-Einträge
    app._auto_mode_kind(mode, "Ignorieren")
    assert job["enabled"] and job["goal_kind"] == "ignore"
    assert s[row[4]]["value"] == "keine Bewertung (kein Zähler, keine Violation)"
    assert app._auto_job_settings(job).no_eval and app._auto_goal(job) == (None, None)
    app.auto_last = None
    app.run_auto_now()
    end = time.time() + 10
    while app.auto_last is None and time.time() < end:
        app.tick()
        time.sleep(0.01)
    assert app.auto_last.counters == {}
    # zurück auf Zeit: Zeit-Datei, Flanken bleiben gespeichert
    app._auto_mode_kind(mode, "Zeit")
    assert s[row[5]]["show"] is False and app._auto_json_path(job).endswith("Time_counter.json")
    assert app._auto_eval()["mode_edges"][mode]
    app._auto_remove_edge(0)
    assert app._auto_edges(mode) == []
    assert app._edge_json_name("HTOE_time_counter.json") == "HTOE_Flanken_counter.json"
    assert app._edge_json_name("Ergebnis.json") == "Ergebnis_Flanken.json"

def test_no_goal_means_infinite_no_violation_and_mode_edge_target():
    engine = auto.AutoEngine(auto.AutoSettings())
    cfg = auto.AutoEngine.propose_from_stats({"U": {"values": np.linspace(700, 760, 50)}}, "M", "")
    mode = cfg.modes["M"]
    assert mode.target is None                                     # leer = keine Zielzeit
    assert mode.lookup("U") is not None and mode.lookup("U")[1] < 800
    x = np.arange(100, dtype=float)
    y = np.linspace(700, 800, 100)                                  # Grenze schon überschritten
    a = engine.assess(x, y, mode, "U")
    assert a["state"] == "reached" and a["violated"] is False       # Grenze erreicht, aber keine Violation
    lines = [text for text, _c, _b in engine._info_lines("U", a, "V")]
    assert "Zielzeit: unendlich (keine Violation möglich)" in lines and "Violation vor Zielzeit!" not in lines
    # Flankenzahl des Modes gilt für Flanken ohne eigenes Ziel
    sig = {"U": (x, np.where((np.arange(100) // 10) % 2, 10.0, 0.0))}
    out, _ = auto.evaluate_edges(sig, [{"signal": "U", "upper": 5, "n": 3}], "G", default_target=8)
    assert out["edges_U_G"]["actual"] == 4 and out["edges_U_G"]["steps"] == 8   # letzte offen
    assert out["edges_U_G"]["fulfillment_percent"] == 50.0
    out, _ = auto.evaluate_edges(sig, [{"signal": "U", "upper": 5, "n": 3, "target": 2}], "G", default_target=8)
    assert out["edges_U_G"]["steps"] == 2                          # eigenes Ziel der Flanke geht vor
    out, _ = auto.evaluate_edges(sig, [{"signal": "U", "upper": 5}], "G")
    assert out["edges_U_G"]["steps"] is None and out["edges_U_G"]["fulfillment_percent"] is None
    s = auto.AutoSettings.from_dict({"edge_target": "12"})
    assert s.edge_target == 12 and auto.AutoSettings.from_dict(s.to_dict()).edge_target == 12
    assert auto.AutoSettings.from_dict({"edge_target": "0"}).edge_target is None


def test_edge_counter_violation_against_target_edges(folders):
    src, dst = folders
    write_part(src / "D_001.csv", 0, 200, lambda i: 710.0 + 0.15 * i)     # U_DC steigt Richtung Grenze 750
    config = config_yaml(src.parent / "g.yaml")

    def run(target, folder):
        settings = auto.AutoSettings(source=str(src), target=str(folder), one_group=False, edge_count=True,
                                     edges=({"signal": "I", "upper": 11.5, "n": 1},), edge_target=target)
        engine = auto.AutoEngine(settings)
        return engine, engine.run_cycle(config, mode="Precon")

    # I = 10, 11, 12, ...: eine Flanke je 3 s; U_DC erreicht 750 in ~67 s -> ~22 weitere Flanken bis Violation
    engine, r = run(200, dst)
    entry = r.counters["edges_I_D"]
    assert entry["actual"] == 66 and entry["duration_s"] == pytest.approx(199.0)
    assert entry["violation"] is True and entry["violation_signal"] == "U_DC"
    assert 85 <= entry["edges_to_violation"] <= 92
    stats = json.loads((dst / "D" / "statistics.json").read_text())
    goal = stats["signals"]["U_DC"]["edge_goals"][0]
    assert goal["violated"] and goal["target"] == 200 and stats["signals"]["U_DC"]["violated"]
    a = engine.assess(*engine.groups[next(iter(engine.groups))].merged["U_DC"], config.modes["Precon"], "U_DC",
                      auto.edge_goals(r.counters))
    lines = [text for text, _c, _b in engine._info_lines("U_DC", a, "V")]
    assert "Ziel: 200 Flanken (I, gezählt 66)" in lines and "Violation vor Ziel-Flankenzahl!" in lines
    assert any(x.startswith("Flanken bis Violation: 8") for x in lines)
    # Ziel 80 wird vor der Grenzverletzung erreicht -> keine Violation
    _engine, r2 = run(80, dst.parent / "aus2")
    e2 = r2.counters["edges_I_D"]
    assert e2["violation"] is False and e2["steps"] == 80
    assert not json.loads((dst.parent / "aus2" / "D" / "statistics.json").read_text())["signals"]["U_DC"]["violated"]
    # ohne Flankenziel: keine Violation (unendlich)
    _engine, r3 = run(None, dst.parent / "aus3")
    assert "violation" not in r3.counters["edges_I_D"] and r3.counters["edges_I_D"]["steps"] is None


def test_gui_edge_violation_cell_and_tip(env, folders):
    app = env.app
    job = manual(app, *folders)
    mode = app._auto_mode_name(job)
    app.auto_add_edge("I", upper=11.5, mode=mode)
    job.update(evaluation=job["evaluation"])
    entry = {"counter": "edges", "actual": 66, "steps": 200, "fulfillment_percent": 33.0, "upper": 11.5,
             "edges_upper": 66, "n": 1, "violation": True, "edges_to_violation": 88.4, "violation_signal": "U_DC"}
    cells = app._auto_cell_values(job, "edges_I_D", entry)
    assert cells[2:] == ["I", "D", "66", "200", "33.0 % - Violation"]
    tip = app._edge_tip(entry)
    assert "Flanken bis Violation: 88 (U_DC)" in tip and "Violation vor Ziel-Flankenzahl!" in tip
    app._auto_fill_table([(job, "edges_I_D", entry)])

