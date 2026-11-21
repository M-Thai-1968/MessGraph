"""Limiter: Daten je Datei auf die Abschnitte kürzen, in denen Führungssignale in ihren Grenzen liegen."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_gui_logic import env, wait  # noqa: E402,F401  (Fixture wiederverwenden)

from messgraph import limiter  # noqa: E402
from messgraph.data_model import LoadError  # noqa: E402


def test_mask_held_and_gaps():
    x = np.arange(10.0)
    rect = np.array([0, 5, 5, 5, 0, 0, 5, 5, 0, 0], dtype=float)
    m = limiter.mask(rect, 4.0, None)
    assert m.tolist() == [False, True, True, True, False, False, True, True, False, False]
    y = x * 10
    xk, yk = limiter.apply(x, y, [(x, m)])
    assert xk.tolist()[:3] == [1, 2, 3] and np.isnan(yk[3]) and xk[3] == 4.5          # Lücke getrennt
    assert [v for v in yk.tolist() if v == v] == [10, 20, 30, 60, 70]
    # andere Zeitbasis: Zustand des Führungssignals wird gehalten, vor dem ersten Punkt aus
    fine = np.array([-1.0, 1.5, 3.9, 4.1, 6.5])
    assert limiter.held(x, m, fine).tolist() == [False, True, True, False, True]
    assert limiter.kept_share([(x, m)]) == pytest.approx(5 / 9)
    xk, yk = limiter.apply(x, y, [(x, np.zeros(10, bool))])                            # nichts im Limit
    assert xk.size == 1 and np.isnan(yk[0])


def test_rules_and(tmp_path):
    a = limiter.Rule("lauf_*.csv", "rect", 4.0, None)
    assert a.matches_file("lauf_1.csv") and not a.matches_file("x.csv") and a.usable
    assert not limiter.Rule("*", "rect").usable and not limiter.Rule("*", "rect", 5, 1).usable
    cfg = limiter.LimiterConfig([a, limiter.Rule("*", "temp", None, 30.0, enabled=False)])
    assert cfg.rules_for("lauf_2.csv") == [a]
    cfg.active = False
    assert cfg.rules_for("lauf_2.csv") == []


def test_yaml_roundtrip_keeps_other_sections(tmp_path):
    path = tmp_path / "konfig.yaml"
    path.write_text("modes:\n  A:\n    steps: 10\n", encoding="utf-8")
    cfg = limiter.LimiterConfig([limiter.Rule("lauf_1.csv", "rect", 4.5, None), limiter.Rule("*", "T", -1, 2.5)])
    written = limiter.save(cfg, str(path))
    text = path.read_text(encoding="utf-8")
    assert "modes:" in text and "limiter:" in text
    back = limiter.load(written)
    assert [r.key() for r in back.rules] == [r.key() for r in cfg.rules] and back.active
    (tmp_path / "leer.yaml").write_text("modes: {}\n")
    with pytest.raises(LoadError, match="limiter"):
        limiter.load(str(tmp_path / "leer.yaml"))
    (tmp_path / "falsch.yaml").write_text("limiter:\n  rules:\n    - signal: a\n      min: abc\n")
    with pytest.raises(LoadError, match="ungültige Zahl"):
        limiter.load(str(tmp_path / "falsch.yaml"))
    assert limiter.save(cfg, str(tmp_path / "neu")).endswith("neu.yaml")


@pytest.fixture
def rect_files(tmp_path):
    t = np.arange(0, 20, 0.5)
    rect = np.where((t // 5) % 2 == 1, 5.0, 0.0)          # 0..5 aus, 5..10 an, ...
    one = tmp_path / "lauf_1.csv"
    one.write_text("t,rect,temp\n" + "".join(f"{a},{b},{a * 2}\n" for a, b in zip(t, rect)))
    two = tmp_path / "lauf_2.csv"
    two.write_text("t,temp\n" + "".join(f"{a},{a}\n" for a in t))
    return str(one), str(two)


def test_gui_limiter_reduces_all_signals_of_file(env, rect_files, tmp_path):
    app = env.app
    app.open_files(list(rect_files))
    wait(app)
    one = next(d for d in app.datasets if d.name == "lauf_1.csv")
    two = next(d for d in app.datasets if d.name == "lauf_2.csv")
    temp1 = next(c for c in one.channels if c.name == "temp")
    temp2 = next(c for c in two.channels if c.name == "temp")
    full = temp1.x.size
    app._request_add(temp1, None)
    app._request_add(temp2, None)
    app.open_limiter_window()
    assert env.state.items["limiter_window"]["show"] is True and len(app.limiter.rules) == 1
    app._lim_set(0, "signal", "rect")
    app._lim_set(0, "lo", "4,5")                              # Komma als Dezimalzeichen
    kept = temp1.y[np.isfinite(temp1.y)]
    assert 0 < kept.size < full and temp1.raw[0].size == full
    assert all(5 <= x < 10 or 15 <= x < 20 for x in temp1.x[np.isfinite(temp1.y)])
    assert np.isnan(temp1.y).sum() == 1                       # eine Lücke zwischen den beiden Abschnitten
    assert temp2.raw is None and temp2.x.size == full         # andere Datei unberührt (Regel nur für lauf_1)
    assert "48,7 % der Messzeit" in app._limiter_text(one) and "Limiter" in env.state.items[app.lim_result]["value"]
    app._lim_set(0, "file", "*")                              # alle Dateien: lauf_2 hat kein rect
    assert "Nicht in der Datei: rect" in app._limiter_text(two) and temp2.raw is None
    app._lim_set(0, "lo", "abc")                              # unfertige Eingabe: Grenze bleibt
    assert app.limiter.rules[0].lo == 4.5
    app.set_limiter_active(False)
    assert temp1.raw is None and temp1.x.size == full and env.state.items[app.limiter_item]["value"] is False
    app.set_limiter_active(True)
    assert temp1.raw is not None

    path = tmp_path / "lim"
    app.save_limiter(str(path))
    session = app.session_dict()
    assert session["options"]["limiter"]["rules"][0]["signal"] == "rect"
    app.remove_limiter()
    assert app.limiter is None and temp1.x.size == full
    assert app.load_limiter(str(path) + ".yaml") and temp1.raw is not None
    app.remove_limiter()
    app._apply_options(session["options"])                    # Ansicht mit Limiter laden
    app._layout_changed()
    assert temp1.raw is not None and app.limiter.path.endswith("lim.yaml")


def test_gui_limiter_reapplies_after_reload_and_two_rules_and(env, rect_files):
    app = env.app
    app.open_files([rect_files[0]])
    wait(app)
    ds = app.datasets[0]
    temp = next(c for c in ds.channels if c.name == "temp")
    app.limiter = limiter.LimiterConfig([limiter.Rule("*", "rect", 4, None), limiter.Rule("*", "temp", None, 30)])
    app._limiter_changed()
    finite = temp.x[np.isfinite(temp.y)]
    assert finite.max() <= 15 and finite.min() >= 5           # UND: rect hoch und temp <= 30 (t <= 15)
    temp.x, temp.y = temp.raw                                 # Daten neu geladen (z. B. Downsampling geändert)
    assert app._apply_limiter() and temp.raw is not None and np.isfinite(temp.y).sum() == finite.size


def test_demo_limiter_on_square_wave(env):
    demo = Path(__file__).parent.parent / "demo_data"
    app = env.app
    app.open_files([str(demo / "demo_rechteck.csv")])
    wait(app)
    assert app.load_limiter(str(demo / "demo_limiter.yaml"))
    current = next(c for c in app.datasets[0].channels if c.name == "Strom")
    values = current.y[np.isfinite(current.y)]
    assert values.min() > 10                                   # nur Abschnitte mit Rechteck oben (Strom ~16 A)
    share = app.limiter_state[app.datasets[0].path][0]
    assert 0.45 < share < 0.55 and np.isnan(current.y).sum() == 5   # 6 Abschnitte, 5 Lücken



def test_gui_transfer_rule_to_selected_files(env, tmp_path):
    app = env.app
    s = env.state.items
    paths = []
    for name, cols in (("A_001.csv", "U,I"), ("B_001.csv", "U,I"), ("C_001.csv", "U,I"), ("D_001.csv", "T")):
        p = tmp_path / name
        p.write_text("Zeit," + cols + "\n" + "\n".join(f"{i}," + ",".join(["1"] * len(cols.split(","))) for i in range(5)) + "\n")
        paths.append(str(p))
    app.open_limiter_window()
    app._lim_read_files(paths)                                     # Dateien bekannt machen (nur Signalnamen)
    rule = app.limiter.rules[0]
    rule.file, rule.signal, rule.lo, rule.hi = "A_001.csv", "U", 0.5, 2.0
    app.limiter.rules.append(limiter.Rule(file="B_001.csv", signal="U", lo=9, hi=10, enabled=False))
    app._lim_rows()
    assert s[app.lim_xfer_rule]["value"].startswith("1: A_001.csv / U [0.5 .. 2]")
    names = set(app.lim_xfer_boxes)
    assert "A_001.csv" not in names and {"B_001.csv", "C_001.csv", "D_001.csv"} <= names   # Ausgangsdatei fehlt
    assert "ohne Signal" in s[app.lim_xfer_boxes["D_001.csv"]]["label"]
    app._lim_xfer_select(None)                                     # nur Dateien mit Signal U
    assert app._lim_xfer_chosen() == [n for n in app.lim_xfer_boxes if n in ("B_001.csv", "C_001.csv")] or \
        set(app._lim_xfer_chosen()) == {"B_001.csv", "C_001.csv"}
    assert s[app.lim_xfer_btn]["label"] == "Dateien: 2 gewählt..."
    app.lim_transfer()
    rules = {(r.file, r.signal): r for r in app.limiter.rules}
    assert (rules[("B_001.csv", "U")].lo, rules[("B_001.csv", "U")].hi, rules[("B_001.csv", "U")].enabled) == (0.5, 2.0, True)
    assert (rules[("C_001.csv", "U")].lo, rules[("C_001.csv", "U")].hi) == (0.5, 2.0) and len(app.limiter.rules) == 3
    assert "1 neu, 1 aktualisiert" in s[app.lim_xfer_note]["value"] and app._lim_xfer_chosen() == []
    app._lim_xfer_select(False)
    app.lim_transfer()
    assert "mindestens eine Datei" in s[app.lim_xfer_note]["value"]
    s[app.lim_xfer_boxes["D_001.csv"]]["value"] = True             # Datei ohne Signal: übernommen, aber gemeldet
    app.lim_transfer()
    assert ("D_001.csv", "U") in {(r.file, r.signal) for r in app.limiter.rules}
    assert "fehlt in: D_001.csv" in s[app.lim_xfer_note]["value"]
