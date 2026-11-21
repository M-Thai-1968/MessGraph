import numpy as np
import pytest

from messgraph import formula
from messgraph.data_model import Channel, Dataset
from messgraph.formula import FormulaError


def ds():
    x = np.arange(5.0)
    return Dataset(path="/m/a.csv", channels=[
        Channel(name="Strom", unit="A", x=x, y=np.array([1.0, 2, 3, 4, 5]), source="/m/a.csv"),
        Channel(name="Spannung", unit="V", x=x, y=np.array([10.0, 10, 10, 10, 0]), source="/m/a.csv"),
        Channel(name="U2", unit="V", x=x, y=np.array([2.0, 2, 2, 2, 2]), source="/m/a.csv")])


def test_parser_precedence_parentheses_and_numbers():
    values = {"a": np.array([2.0]), "b": np.array([3.0])}
    ev = lambda text: float(formula.evaluate(formula.parse(text), values)[0]) if formula.references(formula.parse(text)) \
        else float(formula.evaluate(formula.parse(text), values))
    assert ev("{a} + {b} * 2") == 8 and ev("({a} + {b}) * 2") == 10
    assert ev("-{a} - -{b}") == 1 and ev("{a} / {b} * 3") == pytest.approx(2.0)
    assert ev("1,5 * {a}") == 3 and ev("2e1 / 4") == 5 and ev("10 - 2 - 3") == 5
    assert formula.references(formula.parse("{b} * {a} + {b}")) == ["b", "a"]
    for bad in ("", "{a} *", "({a} + 1", "{a} {b}", "{} + 1", "{a} % 2", "2 ** 3"):
        with pytest.raises(FormulaError):
            formula.parse(bad)


def test_compute_power_units_division_by_zero():
    d = ds()
    p = formula.compute(d, "Leistung", "", "{Strom} * {Spannung}")
    assert p.y.tolist() == [10, 20, 30, 40, 0] and p.unit == "W" and p.formula == "{Strom} * {Spannung}"
    r = formula.compute(d, "R", "", "{Spannung} / {Strom}")
    assert r.unit == "V/A" and r.y[0] == 10
    q = formula.compute(d, "Q", "", "{Strom} / ({Spannung} - 10)")
    assert np.isnan(q.y[:4]).all() and q.y[4] == -0.5                # Division durch 0: Lücke statt unendlich
    s = formula.compute(d, "Summe", "mV", "({Spannung} + {U2}) * 1000")
    assert s.unit == "mV" and s.y[0] == 12000
    assert formula.guess_unit(formula.parse("{Spannung} - {U2}"), {"Spannung": "V", "U2": "V"}) == "V"
    with pytest.raises(FormulaError):
        formula.compute(d, "Strom", "", "{U2} * 2")                  # Name schon vergeben
    with pytest.raises(FormulaError):
        formula.compute(d, "X", "", "{Gibtsnicht} * 2")
    with pytest.raises(FormulaError):
        formula.compute(d, "X", "", "3 * 2")                         # kein Signal


def test_different_time_bases_are_interpolated_and_mf4_loaded():
    calls = []
    def loader():
        calls.append(1)
        return np.array([0.0, 4.0]), np.array([0.0, 40.0]), "V"
    d = Dataset(path="/m/a.mf4", channels=[
        Channel(name="I", unit="A", x=np.arange(5.0), y=np.ones(5), source="/m/a.mf4"),
        Channel(name="U", source="/m/a.mf4", loader=loader)])
    p = formula.compute(d, "P", "", "{I} * {U}")
    assert calls == [1] and p.y.tolist() == [0, 10, 20, 30, 40] and p.interpolated == ["U"] and p.unit == "W"


def test_limit_replace_dependents_and_rename():
    d = ds()
    for i in range(formula.MAX_COMPUTED):
        formula.add_or_replace(d, formula.compute(d, f"P{i}", "", "{Strom} * 2"))
    with pytest.raises(FormulaError):
        formula.add_or_replace(d, formula.compute(d, "Zuviel", "", "{Strom} * 2"))
    d = ds()
    p = formula.add_or_replace(d, formula.compute(d, "P", "", "{Strom} * {Spannung}"))
    e = formula.add_or_replace(d, formula.compute(d, "E", "", "{P} * 2"))   # berechnet aus berechnet
    assert e.y[1] == 40 and formula.dependents(d, "P") == [e]
    new = formula.compute(d, "Leistung", "", "{Strom} * {U2}", exclude=p)
    same = formula.add_or_replace(d, new, p)
    assert same is p and p.name == "Leistung" and p.y.tolist() == [2, 4, 6, 8, 10]
    formula.rename_references(d, "P", "Leistung")
    assert e.formula == "{Leistung} * 2"


def test_session_roundtrip_recomputes(tmp_path):
    from messgraph import session
    from messgraph.layout import PlotLayout
    from messgraph.loaders import load_file
    path = tmp_path / "m.csv"
    path.write_text("t;Strom [A];Spannung [V]\n" + "".join(f"{i};{i};{2 * i}\n" for i in range(10)))
    d = load_file(str(path))
    p = formula.add_or_replace(d, formula.compute(d, "P", "", "{Strom} * {Spannung}"))
    layout = PlotLayout()
    layout.add(p)
    data = session.build_session([d], layout, {})
    assert data["files"][0]["computed"] == [{"name": "P", "unit": "W", "formula": "{Strom} * {Spannung}", "comment": ""}]
    datasets, by_saved, problems = session.open_session(data, None)
    restored, missing = session.restore_layout(data, by_saved)
    assert not problems and not missing
    signal = restored.slots[0].signals[0]
    assert signal.name == "P" and signal.formula and signal.y[3] == 18
