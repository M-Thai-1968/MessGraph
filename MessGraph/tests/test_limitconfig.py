"""Grenzwert-Konfiguration (YAML): Laden, Modes, Zuordnung der Signale."""
from pathlib import Path

import pytest

from messgraph import limitconfig
from messgraph.data_model import LoadError

DEMO = Path(__file__).resolve().parent.parent / "demo_data" / "demo_grenzen.yaml"


def test_demo_config_modes_steps_and_signals():
    config = limitconfig.load(str(DEMO))
    assert config.mode_names() == ["Interface", "EU_AC_3ph_11kW_800V", "EU_AC_3ph_22kW_800V"]
    mode = config.modes["EU_AC_3ph_11kW_800V"]
    assert mode.steps == 600 and config.modes["Interface"].steps is None and not config.modes["Interface"].signals
    assert mode.signals["AC_V_L1"] == (207.0, 253.0)
    assert "Chiller_T" not in mode.signals and mode.disabled == 1          # enabled: false zählt nicht
    assert limitconfig.describe(config).endswith("3 Modes (2 mit Grenzen)")


def test_signal_lookup_by_name():
    mode = limitconfig.load(str(DEMO)).modes["EU_AC_3ph_11kW_800V"]
    assert mode.lookup("AC_V_L1") == (207.0, 253.0)
    assert mode.lookup("ac_v_l1") == (207.0, 253.0)                        # ohne Groß-/Kleinschreibung
    assert mode.lookup("AC_V_L1 [V]") == (207.0, 253.0)                    # Einheit im Namen
    assert mode.lookup("AC_I_L1") is None and mode.lookup("Chiller_T") is None


def test_structure_like_test_bench_config(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("""plot: {width: 1400}
limits:
  enabled: true
  upper: 99.0
  lower: null
  modes:
    None:
      steps: 1000
      signals:
        A: {enabled: false, lower: 0.0, upper: 0.0}
    Heat_800V:
      steps: 26306
      signals:
        Test_Mode: {enabled: true, lower: 44.1, upper: 39.9}
        B: {enabled: true, lower: 1.0}
        C: {enabled: true}
regression: {enabled: true}
""", encoding="utf-8")
    config = limitconfig.load(str(p))
    heat = config.modes["Heat_800V"]
    assert config.modes["None"].steps == 1000 and not config.modes["None"].signals
    assert heat.signals["Test_Mode"] == (39.9, 44.1)                       # vertauscht: geordnet
    assert heat.signals["B"] == (1.0, 99.0)                                # fehlendes upper: Vorgabe
    assert heat.signals["C"] == (None, 99.0)


@pytest.mark.parametrize("text, message", [("plot: {a: 1}\n", "keine Modes"), ("limits: [1, 2\n", "gültige YAML"),
                                           ("limits:\n  modes: {}\n", "keine Modes")])
def test_invalid_configs(tmp_path, text, message):
    p = tmp_path / "x.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(LoadError, match=message):
        limitconfig.load(str(p))
    with pytest.raises(LoadError, match="nicht lesbar"):
        limitconfig.load(str(tmp_path / "fehlt.yaml"))


def test_edit_save_and_reload_keeps_other_sections(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("plot: {width: 1400}\nlimits:\n  enabled: true\n  modes:\n    A:\n      steps: 100\n      signals:\n"
                 "        X: {enabled: false, lower: 0.0, upper: 1.0}\n", encoding="utf-8")
    config = limitconfig.load(str(p))
    mode = config.modes["A"]
    assert mode.entries["X"].enabled is False and mode.disabled == 1 and not mode.signals
    mode.set_entry("Y", True, "5", 2.0)                                     # vertauscht, Text: wird geordnet
    assert mode.signals == {"Y": (2.0, 5.0)}
    config.copy_mode("A", "B")
    config.rename_mode("A", "A2")
    config.add_mode("C", steps=0)
    assert config.mode_names() == ["A2", "B", "C"] and config.modes["C"].steps is None
    with pytest.raises(ValueError):
        config.add_mode("B")
    with pytest.raises(ValueError):
        config.rename_mode("B", " ")
    config.delete_mode("C")
    out = limitconfig.save(config, str(tmp_path / "neu"))                   # Endung wird ergänzt
    assert out.endswith("neu.yaml") and config.path == out and not config.modified
    again = limitconfig.load(out)
    assert again.raw == {"plot": {"width": 1400}}                           # übrige Abschnitte bleiben
    assert again.mode_names() == ["A2", "B"] and again.modes["B"].signals == {"Y": (2.0, 5.0)}
    assert again.modes["A2"].entries["X"].enabled is False and again.modes["A2"].steps == 100


def test_new_config():
    config = limitconfig.new_config("Standard")
    assert config.mode_names() == ["Standard"] and config.modified and config.path == ""
    assert "nicht gespeichert" in config.name


def test_steps_as_count_or_time(tmp_path):
    from messgraph.limitconfig import format_time, parse_steps
    assert parse_steps(26306) == (26306.0, None) and parse_steps("26306") == (26306.0, None)
    assert parse_steps("7h 18m 26s") == (None, 26306.0) and parse_steps("45m") == (None, 2700.0)
    assert parse_steps("90s") == (None, 90.0) and parse_steps("1d 2h") == (None, 93600.0)
    assert parse_steps("1,5h") == (None, 5400.0) and parse_steps("") == (None, None) and parse_steps(None) == (None, None)
    for bad in ("7x", "abc", "7h foo"):
        with pytest.raises(ValueError):
            parse_steps(bad)
    assert format_time(26306) == "7h 18m 26s" and format_time(2700) == "45m" and format_time(0) == "0s"
    p = tmp_path / "c.yaml"
    p.write_text("limits:\n  modes:\n    A: {steps: 26306}\n    B: {steps: '7h 18m 26s'}\n    C: {steps: 45m}\n",
                 encoding="utf-8")
    config = limitconfig.load(str(p))
    assert config.modes["A"].target == ("steps", 26306.0) and config.modes["B"].target == ("s", 26306.0)
    assert config.modes["C"].target == ("s", 2700.0) and config.modes["B"].steps_text() == "7h 18m 26s"
    config.modes["A"].set_steps("2h")
    again = limitconfig.load(limitconfig.save(config, str(tmp_path / "out.yaml")))
    assert again.modes["A"].target == ("s", 7200.0) and again.modes["C"].target == ("s", 2700.0)
    assert "steps: 2h" in (tmp_path / "out.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text("limits:\n  modes:\n    A: {steps: 7x}\n", encoding="utf-8")
    with pytest.raises(LoadError, match="steps ungültig"):
        limitconfig.load(str(bad))
