"""Anordnung vorschlagen: Gruppierung nach Namen/Einheit und Matrix mit zusammengefassten Zeilen."""
from types import SimpleNamespace as S

import pytest

from messgraph import arrange
from messgraph.layout import MAX_GRAPHS, PlotLayout

BENCH = ("Test_Mode,OBC_Mode,Kl30_V_Set,Kl30_I_Set,Kl30_V,Kl30_I,AC_V_L1,AC_F_L1,AC_I_L1,AC_P_L1,AC_V_L1_ext,"
         "AC_V_L2,AC_F_L2,AC_I_L2,AC_P_L2,AC_V_L3,AC_I_L3,AC_P_L3,AC_P_total_ext,HVDC_V_Set,HVDC_V,HVDC_I,"
         "LVDC_V,LVDC_I,Chiller_T_Set,Chiller_F_Set,Chiller_T,Clnt_DUT_IN_T,Clnt_DUT_F_ext,Chamber_T,Chamber_H,"
         "DUT_CoverT_S01,DUT_TS_01,DUT_TS_02,Grid").split(",")


def sig(name, unit=""):
    return S(name=name, unit=unit)


@pytest.mark.parametrize("name, unit, expected", [
    ("AC_V_L1", "", "voltage"), ("AC_I_L2_ext", "", "current"), ("AC_P_total_ext", "", "power"),
    ("AC_F_L1", "", "frequency"), ("V2L_F_Set", "", "frequency"), ("Chiller_F_total", "", "flow"),
    ("DUT_TS_07", "", "temperature"), ("DUT_CoverT_S01", "", "temperature"), ("Clnt_DUT_OUT_T", "", "temperature"),
    ("Chamber_H", "", "humidity"), ("OBC_Mode", "", "state"), ("Kl30_V_Set", "", "voltage"),
    ("Messwert", "°C", "temperature"), ("Zelle 3", "mV", "voltage"), ("Batterie Strom", "", "current"),
    ("motorSpeed", "rpm", "speed"), ("Temperatur", "", "temperature"), ("SN_DUT", "", None)])
def test_quantity_detection(name, unit, expected):
    assert arrange.quantity_of(name, unit) == expected


def test_tokens_keep_digits_and_split_camel_case():
    assert arrange.tokens("Kl30_V_Set") == ["Kl30", "V", "Set"]
    assert arrange.tokens("V2L_I_IS_Set") == ["V2L", "I", "IS", "Set"]
    assert arrange.tokens("DUT_CoverT_S01") == ["DUT", "Cover", "T", "S01"]
    assert arrange.domain_of("AC_V_L1") == "AC" and arrange.domain_of("Spannung") == ""


def test_proposal_for_test_bench_signals():
    p = arrange.propose([sig(n) for n in BENCH])
    by_title = {g.title: [c.name for c in g.signals] for g in p.groups}
    assert by_title["AC Spannung"] == ["AC_V_L1", "AC_V_L1_ext", "AC_V_L2", "AC_V_L3"]
    assert by_title["AC Strom"] == ["AC_I_L1", "AC_I_L2", "AC_I_L3"]
    assert by_title["AC Leistung"][-1] == "AC_P_total_ext" and "AC Frequenz" in by_title
    assert by_title["HVDC Spannung"] == ["HVDC_V", "HVDC_V_Set"]                       # Ist vor Soll
    assert by_title["DUT Temperatur"] == ["DUT_CoverT_S01", "DUT_TS_01", "DUT_TS_02"]
    assert by_title["Zustände"] == ["OBC_Mode", "Test_Mode"] and by_title["Sonstige"] == ["Grid"]
    rows = p.rows
    assert rows[rows.index("AC")] == "AC"
    ac = [g.title for g in p.groups if g.row == "AC"]
    assert ac == ["AC Spannung", "AC Strom", "AC Leistung", "AC Frequenz"]            # AC-Werte in einer Zeile
    assert rows[-2:] in (["Temperaturen", "Zustände, Sonstige"],) and "HVDC, LVDC" in rows   # kleine Zeilen geteilt
    assert p.matrix == (len(p.spans), 4) and all(sum(r) == 4 for r in p.spans)
    temps = [g for g in p.groups if g.row == "Temperaturen"]
    assert {c.name for g in temps for c in g.signals} == {"Chiller_T", "Chiller_T_Set", "Clnt_DUT_IN_T", "Chamber_T",
                                                         "DUT_CoverT_S01", "DUT_TS_01", "DUT_TS_02"}
    lay = PlotLayout()
    lay.set_matrix(p.matrix, p.spans)                                                 # passt in die Matrix
    assert len(lay.slots) == p.count


def test_limits_split_graphs_and_rows():
    many = [sig(f"DUT_TS_{i:02d}") for i in range(1, 21)]
    p = arrange.propose(many, max_curves=8)
    assert [len(g.signals) for g in p.groups] == [8, 8, 4]
    assert [g.title for g in p.groups] == ["DUT Temperatur (1/3)", "DUT Temperatur (2/3)", "DUT Temperatur (3/3)"]
    wide = [sig(f"AC_{q}_L1") for q in ("V", "I", "P", "F")] + [sig("AC_E_total", "kWh")]
    p = arrange.propose(wide, max_cols=3)
    assert p.matrix == (2, 3) and p.spans == [[1, 1, 1], [2, 1]]
    assert all(len(r) <= 3 for r in p.spans)
    p = arrange.propose([sig(n) for n in BENCH], own_rows=False)
    assert "Temperaturen" not in p.rows and any(g.title == "Chiller Temperatur" and g.row.startswith("Chiller")
                                                 for g in p.groups)


def test_too_many_signals_raise_curves_per_graph():
    names = [sig(f"S{i}_{q}") for i in range(80) for q in ("V", "I")]
    p = arrange.propose(names, max_curves=1)
    assert p.count <= MAX_GRAPHS and p.notes
    assert arrange.propose([]).groups == []


def test_many_systems_fall_back_to_groups_per_quantity():
    p = arrange.propose([sig(f"S{i}_{q}") for i in range(80) for q in ("V", "I")], max_curves=8)
    assert p.count <= MAX_GRAPHS and "Größe über alle Systeme" in p.notes[0]
    assert {g.title.split(" (")[0] for g in p.groups} == {"Spannung", "Strom"}
    assert sum(len(g.signals) for g in p.groups) == 160
    lay = PlotLayout()
    lay.set_matrix(p.matrix, p.spans)
    assert len(lay.slots) == p.count
