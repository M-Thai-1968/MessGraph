import math
import sys
import types

import numpy as np
import pytest

from messgraph.csv_reader import read_csv
from messgraph.data_model import LoadError
from messgraph.layout import PlotLayout, parse_matrix
from messgraph.loaders import load_file
from messgraph.measure import decimate, drift_unit, fmt, measure, value_at


def write(tmp_path, text, name="d.csv", encoding="utf-8"):
    p = tmp_path / name
    p.write_bytes(text.encode(encoding))
    return str(p)


def ch(ds, name):
    return next(c for c in ds.channels if c.name == name)


def test_simple_comma(tmp_path):
    ds = read_csv(write(tmp_path, "time,speed,temp\n0,1.5,20\n1,2.5,21\n2,3.5,22\n"))
    assert [c.name for c in ds.channels] == ["speed", "temp"]
    assert ch(ds, "speed").x.tolist() == [0, 1, 2]
    assert ch(ds, "speed").y.tolist() == [1.5, 2.5, 3.5]


def test_german_preamble_units_cp1252(tmp_path):
    text = ("Messung: Prüfstand 3\nDatum: 05.11.2026\n\nBemerkung;Öltemperatur;kalt\n"
            "Zeit;Drehzahl;Öltemperatur\ns;rpm;°C\n0,0;1000,5;20,25\n0,5;1100,5;21,5\n1,0;1200;22\n")
    ds = read_csv(write(tmp_path, text, encoding="cp1252"))
    oil = ch(ds, "Öltemperatur")
    assert oil.unit == "°C" and oil.x_unit == "s"
    assert oil.y.tolist() == [20.25, 21.5, 22.0]
    assert oil.x.tolist() == [0.0, 0.5, 1.0]
    assert ch(ds, "Drehzahl").unit == "rpm"


def test_unit_in_header_and_bom_tab(tmp_path):
    ds = read_csv(write(tmp_path, "﻿Time [ms]\tSpeed [km/h]\tDruck (bar)\tName (Sensor 1)\n"
                                  "0\t1\t2\t3\n10\t4\t5\t6\n"))
    assert ch(ds, "Speed").unit == "km/h" and ch(ds, "Speed").x_unit == "ms"
    assert ch(ds, "Druck").unit == "bar"
    assert ch(ds, "Name (Sensor 1)").unit == ""


def test_utf16(tmp_path):
    ds = read_csv(write(tmp_path, "﻿t;a\n0;1\n1;2\n", encoding="utf-16-le"))
    assert ch(ds, "a").y.tolist() == [1, 2]


def test_no_header(tmp_path):
    ds = read_csv(write(tmp_path, "0.0,5.0\n1.0,6.0\n2.0,4.0\n"))
    assert ch(ds, "Spalte_2").y.tolist() == [5, 6, 4]
    assert ch(ds, "Spalte_2").x.tolist() == [0, 1, 2]


def test_no_time_uses_row_number(tmp_path):
    ds = read_csv(write(tmp_path, "a,b\n5,1\n3,2\n4,9\n"))
    assert ch(ds, "b").x.tolist() == [0, 1, 2] and ch(ds, "b").x_name == "Zeile"
    assert any("Zeilennummer" in w for w in ds.warnings)


def test_timestamp_column_and_text_column(tmp_path):
    text = ("Timestamp,State,Value\n2026-11-05 10:00:00.000,OK,1\n"
            "2026-11-05 10:00:01.500,OK,2\n2026-11-05 10:00:03.000,FAIL,3\n")
    ds = read_csv(write(tmp_path, text))
    assert [c.name for c in ds.channels] == ["Value"]
    assert ch(ds, "Value").x.tolist() == [0, 1.5, 3] and ch(ds, "Value").x_unit == "s"
    assert ds.extra["no_values"] == ["State"]


def test_german_date_and_separate_columns(tmp_path):
    text = "Datum;Uhrzeit;Wert\n05.11.2026;10:00:00,5;1,5\n05.11.2026;10:00:01,5;2,5\n06.11.2026;10:00:00,5;3,5\n"
    ds = read_csv(write(tmp_path, text))
    assert ch(ds, "Wert").x.tolist() == [0, 1, 86400]
    assert ch(ds, "Wert").y.tolist() == [1.5, 2.5, 3.5]


def test_trailing_separator_and_bad_rows(tmp_path):
    text = "t;a;b;\n0;1;2;\n1;x;3;\n2;5;6;\n# Ende\n"
    ds = read_csv(write(tmp_path, text))
    assert [c.name for c in ds.channels] == ["a", "b"]
    a = ch(ds, "a").y
    assert a[0] == 1 and math.isnan(a[1]) and a[2] == 5


def test_unsorted_time_sorted(tmp_path):
    ds = read_csv(write(tmp_path, "time,a\n0,1\n2,3\n1,2\n3,4\n" + "".join(f"{i},{i+1}\n" for i in range(4, 400))))
    c = ch(ds, "a")
    assert np.all(np.diff(c.x) >= 0)
    assert np.all(c.y == c.x + 1)
    assert any("sortiert" in w for w in ds.warnings)


def test_header_only_and_empty(tmp_path):
    with pytest.raises(LoadError):
        read_csv(write(tmp_path, "a,b,c\n"))
    with pytest.raises(LoadError):
        read_csv(write(tmp_path, ""))


def test_duplicate_names_and_large_file_beyond_sample(tmp_path):
    body = "".join(f"{i},{i * 2},{i * 3}\n" for i in range(5000))
    ds = read_csv(write(tmp_path, "t,a,a\n" + body))
    assert [c.name for c in ds.channels] == ["a", "a_2"]
    assert ch(ds, "a_2").y.size == 5000 and ch(ds, "a_2").y[-1] == 4999 * 3


def test_single_column(tmp_path):
    ds = read_csv(write(tmp_path, "Wert\n1.5\n2.5\n"))
    assert ch(ds, "Wert").y.tolist() == [1.5, 2.5]


def test_unsupported_type(tmp_path):
    with pytest.raises(LoadError):
        load_file(write(tmp_path, "x", name="a.txt"))


def test_parquet_via_fake_pyarrow(tmp_path, monkeypatch):
    import pandas as pd
    df = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=3, freq="500ms"),
                       "v [V]": [1.0, 2.0, 3.0], "flag": [True, False, True], "txt": list("abc")})
    pa = types.ModuleType("pyarrow")
    pq = types.ModuleType("pyarrow.parquet")
    pq.read_table = lambda path: types.SimpleNamespace(to_pandas=lambda: df)
    pa.parquet = pq
    monkeypatch.setitem(sys.modules, "pyarrow", pa)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", pq)
    ds = load_file(write(tmp_path, "x", name="a.PARQUET"))
    v = ch(ds, "v")
    assert v.unit == "V" and v.x.tolist() == [0, 0.5, 1.0]
    assert ch(ds, "flag").y.tolist() == [1, 0, 1]
    assert not any(c.name == "txt" for c in ds.channels)


class FakeMDF:
    closed = False

    def __init__(self, path):
        C = lambda n, u="": types.SimpleNamespace(name=n, unit=u)
        self.groups = [types.SimpleNamespace(channels=[C("time"), C("speed", "km/h"), C("gear")]),
                       types.SimpleNamespace(channels=[C("t2"), C("speed", "m/s"), C("blob")])]
        self.masters_db = {0: 0, 1: 0}
        self.channels_db = {}
        for g, grp in enumerate(self.groups):
            for i, c in enumerate(grp.channels):
                self.channels_db.setdefault(c.name, []).append((g, i))

    def get(self, name, group=None, index=None, raw=False):
        t = np.array([0.0, 1.0, 2.0])
        if name == "gear" and not raw:
            return types.SimpleNamespace(samples=np.array([b"P", b"D", b"R"]), timestamps=t, unit="")
        if name == "blob":
            return types.SimpleNamespace(samples=np.zeros((3, 8)), timestamps=t, unit="")
        return types.SimpleNamespace(samples=np.array([1, 2, 3]) * (group + 1), timestamps=t, unit="km/h" if group == 0 else "m/s")

    def close(self):
        FakeMDF.closed = True


def test_mf4_lazy_via_fake_asammdf(tmp_path, monkeypatch):
    mod = types.ModuleType("asammdf")
    mod.MDF = FakeMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    ds = load_file(write(tmp_path, "x", name="a.mf4"))
    assert [c.name for c in ds.channels] == ["speed [g0]", "gear", "speed [g1]", "blob"]
    assert ds.channels[0].aliases == ("speed (G0)",) and ds.channels[0].matches("speed (G0)")
    assert not ds.channels[0].loaded
    ds.channels[2].load()
    assert ds.channels[2].y.tolist() == [2, 4, 6] and ds.channels[2].unit == "m/s"
    ds.channels[1].load()
    assert ds.channels[1].y.tolist() == [1, 2, 3]  # Rohwerte statt Text
    with pytest.raises(LoadError):
        ds.channels[3].load()
    ds.close()
    assert FakeMDF.closed


def test_missing_libs_give_clear_message(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "asammdf", None)
    with pytest.raises(LoadError, match="pip install asammdf"):
        load_file(write(tmp_path, "x", name="a.mf4"))


@pytest.mark.parametrize("text,expected", [("", None), (" ", None), ("2x3", (2, 3)), ("2*3", (2, 3)),
                                           ("2 X 3", (2, 3)), ("4,1", (4, 1)), ("2 3", (2, 3))])
def test_parse_matrix(text, expected):
    assert parse_matrix(text) == expected


@pytest.mark.parametrize("text", ["abc", "0x3", "2", "9x9", "2x3x4"])
def test_parse_matrix_invalid(text):
    with pytest.raises(ValueError):
        parse_matrix(text)


def test_layout_free_stacks_each_signal():
    lay = PlotLayout()
    for s in "abc":
        lay.add(s)
    assert lay.grid() == (3, 1)
    lay.add("d", target=0)
    assert lay.grid() == (3, 1) and lay.slots[0].signals == ["a", "d"]
    lay.remove("b")
    assert lay.grid() == (2, 1)
    assert lay.target_names() == ["Automatisch", "Graph 1", "Graph 2"]


def test_layout_matrix_fill_overflow_and_shrink():
    lay = PlotLayout()
    lay.set_matrix((2, 2))
    for s in "abcde":
        lay.add(s)
    assert [x.signals for x in lay.slots] == [["a", "e"], ["b"], ["c"], ["d"]]
    assert lay.target_names()[2] == "Graph 2 (Z1/S2)" and lay.target_names()[3] == "Graph 3 (Z2/S1)"
    lay.remove("b")
    assert len(lay.slots) == 4
    lay.set_matrix((1, 2))
    assert sorted(lay.signals()) == list("acde") and len(lay.slots) == 2
    lay.set_matrix(None)
    assert lay.grid() == (2, 1) and sorted(lay.signals()) == list("acde")


def test_layout_matrix_from_free_keeps_signals():
    lay = PlotLayout()
    for s in "abc":
        lay.add(s)
    lay.set_matrix((3, 2))
    assert len(lay.slots) == 6 and lay.signals() == list("abc")
    lay.clear()
    assert lay.signals() == [] and len(lay.slots) == 6


def test_value_at_and_measure():
    x = np.array([0.0, 1.0, 2.0, 4.0])
    y = np.array([0.0, 10.0, np.nan, 40.0])
    assert value_at(x, y, 0.5) == 5.0
    assert value_at(x, y, 4.0) == 40.0
    assert math.isnan(value_at(x, y, 1.5)) and math.isnan(value_at(x, y, 5.0))
    m = measure(np.array([0.0, 10.0]), np.array([100.0, 200.0]), 2.0, 7.0)
    assert (m.value1, m.value2, m.delta_x, m.delta_y, m.drift) == (120, 170, 5, 50, 10)
    m = measure(np.array([0.0, 10.0]), np.array([100.0, 200.0]), 7.0, 2.0)
    assert (m.delta_x, m.delta_y, m.drift) == (-5, -50, 10)
    m = measure(np.array([0.0, 10.0]), np.array([1.0, 2.0]), 5.0, 5.0)
    assert m.delta_x == 0 and math.isnan(m.drift)
    assert math.isnan(measure(np.array([0.0, 1.0]), np.array([1.0, 2.0]), None, 1.0).drift)


def test_fmt():
    assert fmt(float("nan")) == "-" and fmt(1.23456789, "V") == "1.23457 V"
    assert drift_unit("V", "s") == "V/s" and drift_unit("", "s") == "1/s" and drift_unit("V", "") == "V"


def test_decimate_keeps_spikes_and_window():
    x = np.arange(1_000_000, dtype=float)
    y = np.zeros_like(x)
    y[123456] = 99.0
    y[654321] = -77.0
    dx, dy = decimate(x, y, bins=1000)
    assert dx.size <= 2001 and dy.max() == 99 and dy.min() == -77
    assert np.all(np.diff(dx) >= 0) and dx[0] == 0 and dx[-1] == 999_999
    wx, wy = decimate(x, y, 100_000, 200_000, bins=1000)
    assert wx[0] <= 100_000 and wx[-1] >= 199_000 and wy.max() == 99
    sx, _ = decimate(x, y, 10, 20, bins=1000)
    assert sx.size < 20
    fx, _ = decimate(x, y, 5e9, 6e9, bins=1000)
    assert fx.size <= 2001


def test_decimate_keeps_the_end_of_the_data():
    # 8999 Punkte auf 3000 Blöcke: früher fielen fast 3000 Punkte am Ende weg (gerade Linie zum letzten Wert)
    x = np.arange(8999, dtype=float)
    y = np.sin(x / 50.0)
    y[8800] = 5.0
    dx, dy = decimate(x, y, bins=3000)
    assert dx.size <= 6002 and dx[-1] == 8998 and dy.max() == 5.0
    assert np.max(np.diff(dx)) <= 6                # keine großen Sprünge
    assert np.all(np.diff(dx) >= 0)


def test_decimate_all_nan_block():
    x = np.arange(100_000, dtype=float)
    y = np.full_like(x, np.nan)
    _, dy = decimate(x, y, bins=100)
    assert np.isnan(dy).all()


def test_layout_add_to_target_and_remove_from():
    lay = PlotLayout()
    assert lay.add("a") and lay.add("b")
    assert not lay.add("a")                      # automatisch nur einmal
    assert lay.add("a", target=1)                # gezielt auch in weiteren Graphen
    assert not lay.add("a", target=1)
    assert [s.signals for s in lay.slots] == [["a"], ["b", "a"]]
    lay.remove_from(1, "a")
    assert [s.signals for s in lay.slots] == [["a"], ["b"]]
    lay.remove_from(0, "a")                      # ohne Matrix entfällt der leere Graph
    assert [s.signals for s in lay.slots] == [["b"]]
    lay.set_matrix((1, 2))
    lay.add("c", target=1)
    lay.add("d", target=1)
    lay.clear_slot(1)                            # mit Matrix bleibt der Platz
    assert [s.signals for s in lay.slots] == [["b"], []]
    lay.add("b", target=1)
    lay.clear()
    assert lay.signals() == []


def test_mf4_bus_logging_hint_and_bytes_unit(tmp_path, monkeypatch):
    class BusMDF:
        def __init__(self, path):
            C = types.SimpleNamespace
            self.groups = [C(channels=[C(name="t", unit="", channel_type=2), C(name="CAN_DataFrame.ID", unit=b"-"),
                                       C(name="CAN_DataFrame.DataBytes", unit="")])]
            self.channels_db = {"t": ((0, 0),), "CAN_DataFrame.ID": ((0, 1),), "CAN_DataFrame.DataBytes": ((0, 2),)}

        def get(self, name, group=None, index=None, raw=False):
            t = np.array([0.0, 1.0])
            if name.endswith("DataBytes"):
                return types.SimpleNamespace(samples=np.zeros((2, 8), dtype=np.uint8), timestamps=t, unit="")
            return types.SimpleNamespace(samples=np.array([0x100, 0x200]), timestamps=t, unit=b"-")

        def close(self):
            pass

    mod = types.ModuleType("asammdf")
    mod.MDF = BusMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    ds = load_file(write(tmp_path, "x", name="bus.MF4"))
    assert [c.name for c in ds.channels] == ["CAN_DataFrame.ID", "CAN_DataFrame.DataBytes"]
    assert ds.channels[0].unit == "-" and ds.extra["bus_raw"] and not ds.warnings   # Hinweis bildet die Dateiliste
    ds.channels[0].load()
    assert ds.channels[0].y.tolist() == [256, 512]
    with pytest.raises(LoadError, match="Byte-Feld"):
        ds.channels[1].load()


def test_text_timestamp_formats(tmp_path):
    from messgraph.tabular import build_dataset
    import pandas as pd
    df = pd.DataFrame({"Time": ["2026-10-01_23-00-51", "2026-10-04_01-15-28", "2026-10-04_01-15-38"],
                       "SN_DUT": ["DES1"] * 3, "KL30C_V": [13.81, 13.79, 13.84]})
    ds = build_dataset("x.parquet", df)
    c = ds.channels[0]
    assert c.name == "KL30C_V" and c.x_name == "Time" and c.x_unit == "s"
    assert c.x.tolist() == [0.0, 180877.0, 180887.0]
    for stamps, expected in [(["05.11.2026 10:00:00,5", "05.11.2026 10:00:01,0"], [0, 0.5]),
                             (["20261105_100000", "20261105_100002"], [0, 2]),
                             (["2026-11-05T10:00:00Z", "2026-11-05T10:00:00.25Z"], [0, 0.25]),
                             (["10:00:00", "10:00:01.5"], [0, 1.5])]:
        df = pd.DataFrame({"t": stamps, "v": [1.0, 2.0]})
        assert build_dataset("x.csv", df).channels[0].x.tolist() == expected, stamps


TIME_CASES = [
    # (Werte, erwartete Sekunden, erwartete Startzeit als Text oder None)
    (["2026-10-01_23-00-51", "2026-10-01_23-00-52"], [0, 1], "01.10.2026 23:00:51.000"),
    (["2026-10-01T23:00:51.250+02:00", "2026-10-01T23:00:52.500+02:00"], [0, 1.25], "01.10.2026 23:00:51.250"),
    (["01.10.2026 23:00:51,5", "01.10.2026 23:00:52,0"], [0, 0.5], "01.10.2026 23:00:51.500"),
    (["01.10.26 23:00", "01.10.26 23:01"], [0, 60], "01.10.2026 23:00:00.000"),
    (["13/10/2026 08:00:00", "14/10/2026 08:00:00"], [0, 86400], "13.10.2026 08:00:00.000"),
    (["10/13/2026 08:00:00 AM", "10/13/2026 08:00:00 PM"], [0, 43200], "13.10.2026 08:00:00.000"),
    (["10/01/2026", "10/02/2026", "10/03/2026"], [0, 86400, 172800], "01.10.2026 00:00:00.000"),
    (["01/10/2026", "02/10/2026", "03/10/2026"], [0, 86400, 172800], "01.10.2026 00:00:00.000"),
    (["20261001_230051", "20261001_230053.5"], [0, 2.5], "01.10.2026 23:00:51.000"),
    (["01-Oct-2026 23:00:51", "01-Oct-2026 23:00:52"], [0, 1], "01.10.2026 23:00:51.000"),
    (["1. Okt. 2026 um 23:00", "2. Okt. 2026 um 23:00"], [0, 86400], "01.10.2026 23:00:00.000"),
    (["Oct 1, 2026 11:00:51 PM", "Oct 2, 2026 1:00:51 AM"], [0, 7200], "01.10.2026 23:00:51.000"),
    (["Thursday, October 1, 2026 23:00", "Thursday, October 1, 2026 23:30"], [0, 1800], "01.10.2026 23:00:00.000"),
    (["Thu Oct  1 23:00:51 2026", "Thu Oct  1 23:00:55 2026"], [0, 4], "01.10.2026 23:00:51.000"),
    (["23:59:59.5", "00:00:00.5", "00:00:01.5"], [0, 1, 2], None),
    (["00:00:00", "25:30:00"], [0, 91800], None),
    (["0 days 00:00:01.5", "1 days 00:00:01.5"], [0, 86400], None),
]


@pytest.mark.parametrize("values,expected,start", TIME_CASES)
def test_time_formats(values, expected, start):
    import pandas as pd
    from messgraph.tabular import build_dataset
    from messgraph.timeparse import format_wallclock
    df = pd.DataFrame({"Zeitpunkt": values, "v": [float(i) for i in range(len(values))]})
    c = build_dataset("x.csv", df).channels[0]
    assert c.x.tolist() == pytest.approx(expected), values
    assert (format_wallclock(c.x_epoch) if c.x_epoch is not None else None) == start
    assert c.x_unit == "s"


def test_numeric_timestamps(monkeypatch):
    import pandas as pd
    from messgraph.tabular import build_dataset
    monkeypatch.setattr("messgraph.timeparse.time.localtime", lambda t: types.SimpleNamespace(tm_gmtoff=3600))
    base = 1_790_000_000.0  # 21.09.2026 12:53:20 UTC
    for divisor, offset in [(1, 0), (1e-3, 0), (1e-6, 0), (1e-9, 0), (1, 2_082_844_800.0)]:
        df = pd.DataFrame({"timestamp": [(base + offset) / divisor, (base + offset + 2) / divisor], "v": [1.0, 2.0]})
        c = build_dataset("x.csv", df).channels[0]
        assert c.x.tolist() == pytest.approx([0, 2]) and c.x_epoch == pytest.approx(base + 3600), divisor
    df = pd.DataFrame({"time": [0.0, 0.5], "v": [1.0, 2.0]})  # normale Sekunden bleiben ohne Datum
    c = build_dataset("x.csv", df).channels[0]
    assert c.x.tolist() == [0, 0.5] and c.x_epoch is None
    df = pd.DataFrame({"Messwert": [5000.0, 6000.0], "v": [1.0, 2.0]})  # kein Zeitname, kein Zeitbereich
    assert build_dataset("x.csv", df).channels[0].x_epoch is None


def test_datetime64_with_timezone(monkeypatch):
    import pandas as pd
    from messgraph.tabular import build_dataset
    from messgraph.timeparse import format_wallclock
    monkeypatch.setattr("messgraph.timeparse.time.localtime", lambda t: types.SimpleNamespace(tm_gmtoff=3600))
    df = pd.DataFrame({"ts": pd.to_datetime(["2026-11-05 09:00:00", "2026-11-05 09:00:02"]).tz_localize("UTC"),
                       "v": [1.0, 2.0]})
    c = build_dataset("x.parquet", df).channels[0]
    assert format_wallclock(c.x_epoch) == "05.11.2026 10:00:00.000" and c.x.tolist() == [0, 2]


def test_format_helpers():
    from messgraph.timeparse import format_duration
    assert format_duration(5.25) == "5.25 s"
    assert format_duration(93784.5) == "1 d 02:03:04.5 (93784.5 s)"
    assert format_duration(-120) == "-00:02:00 (-120 s)"


def test_regression_and_prediction():
    from messgraph.measure import predict, regression
    x = np.arange(10.0)
    y = 2.0 * x + 1.0 + np.array([0.1, -0.1] * 5)          # Rauschen hebt sich im Mittel auf
    m, b = regression(x, y)
    ref_m, ref_b = np.polyfit(x, y, 1)                        # Referenz: numpy kleinste Quadrate
    assert m == pytest.approx(ref_m, rel=1e-12) and b == pytest.approx(ref_b, rel=1e-12)
    m2, _ = regression(x + 1.8e9, y)                          # Wanduhr-Sekunden: gleiche Steigung
    assert m2 == pytest.approx(m, rel=1e-9)
    assert np.isnan(regression([1.0, 1.0], [1.0, 2.0])[0]) and np.isnan(regression([1.0], [1.0])[0])
    assert regression([0.0, 1.0, 2.0, 3.0], [0.0, np.nan, 2.0, 3.0])[0] == pytest.approx(1.0)
    # x1 = 0 am letzten Messpunkt, b = letzter Wert: x2 = (y2 - b) / m
    p = predict(0.5, 50.0, 0.0, 80.0)
    assert (p.kind, p.x2, p.limit) == ("max", 60.0, 80.0)
    p = predict(-2.0, 50.0, 10.0, None)
    assert (p.kind, p.x2) == ("min", 20.0)
    assert predict(1.0, 90.0, None, 80.0).kind == "reached"
    assert predict(1.0, 50.0, 10.0, None).kind == "inside" and predict(0.0, 50.0, 10.0, 60.0).kind == "inside"
    assert predict(float("nan"), 50.0, 10.0, 60.0).kind == "none" and predict(1.0, 50.0, None, None).kind == "none"


def test_format_span_compact():
    from messgraph.timeparse import format_span
    assert format_span(4.62577e6) == "53 d 12 h 56 min"
    assert format_span(-3 * 3600 - 65) == "3 h 01 min"
    assert format_span(727) == "12 min 07 s" and format_span(42.31) == "42.3 s"
    assert format_span(float("nan")) == "-"


def test_only_columns_without_any_number_are_listed(tmp_path):
    rows = ["Zeit;Spannung;Sensor_B;Modus;Leer;Ende"]
    for i in range(10):
        sensor = f"{20 + i}" if i in (3, 4, 5) else "x"          # nur zeitweise aufgezeichnet, sonst Platzhalter
        rows.append(f"{i};{230 + i};{sensor};Lauf {i % 2};;2026-11-05 10:00:{i:02d}")
    ds = read_csv(write(tmp_path, "\n".join(rows) + "\n"))
    names = [c.name for c in ds.channels]
    assert "Sensor_B" in names                                     # liefert Zahlen: wird angeboten
    assert np.isnan(ch(ds, "Sensor_B").y[0]) and ch(ds, "Sensor_B").y[4] == 24
    assert ds.extra["no_values"] == ["Modus", "Leer"]              # nur Spalten ohne einen Zahlenwert
    assert not any("Ende" in w for w in ds.warnings)               # weitere Zeitspalte ist kein "ohne Zahlen"
    assert any("Ende" in i for i in ds.info)


def test_text_column_with_few_numbers_stays_text(tmp_path):
    rows = ["t;Status;Wert"] + [f"{i};{'OK' if i % 4 else '1'};{i}" for i in range(12)]
    ds = read_csv(write(tmp_path, "\n".join(rows) + "\n"))
    assert [c.name for c in ds.channels] == ["Wert"] and ds.extra["no_values"] == ["Status"]


def test_parse_and_format_target_duration():
    from messgraph.measure import format_target, parse_duration
    assert parse_duration("2d 6h 30m") == 2 * 86400 + 6 * 3600 + 30 * 60
    assert parse_duration("2t 6std") == 2 * 86400 + 6 * 3600
    assert parse_duration("1,5h") == 5400
    assert parse_duration("90min") == 5400
    assert parse_duration("3") == 3 * 3600                          # eine Zahl: Stunden
    assert parse_duration("1 30") == 5400                           # zwei: h m
    assert parse_duration("1 2 30") == 86400 + 2 * 3600 + 1800      # drei: d h m
    assert parse_duration("") is None and parse_duration("  ") is None
    for bad in ("abc", "2x", "1 2 3 4", "2d foo"):
        with pytest.raises(ValueError):
            parse_duration(bad)
    assert format_target(2 * 86400 + 6 * 3600 + 30 * 60) == "2d 6h 30m"
    assert format_target(5400) == "1h 30m" and format_target(30) == "1m" and format_target(0) == "0m"
    assert format_target(float("nan")) == "-"


def test_regression_methods():
    from messgraph.measure import REG_METHODS, regression
    x = np.arange(100.0)
    y = 2 * x + 5
    for method in REG_METHODS:                                   # exakte Gerade: alle gleich
        assert regression(x, y, method) == (pytest.approx(2.0), pytest.approx(5.0))
    noisy = y.copy()
    noisy[10], noisy[50] = 1000.0, -900.0
    assert regression(x, noisy, "theilsen") == (pytest.approx(2.0), pytest.approx(5.0))   # robust
    assert abs(regression(x, noisy, "ols")[0] - 2.0) > 0.3
    knee = np.concatenate([np.zeros(75), np.arange(25.0) * 3])  # Trend erst am Ende
    assert regression(x, knee, "recent")[0] == pytest.approx(3.0)
    assert regression(x, knee, "ols")[0] < 1.0
    # orthogonal: Steigung der Hauptachse liegt zwischen y-auf-x und (x-auf-y)^-1
    rng = np.random.default_rng(1)
    xs = rng.normal(0, 1, 500)
    ys = xs + rng.normal(0, 0.8, 500)
    m_ols, m_tls = regression(xs, ys, "ols")[0], regression(xs, ys, "tls")[0]
    m_inv = 1.0 / regression(ys, xs, "ols")[0]
    assert m_ols < m_tls < m_inv
    # große Zeitwerte (Epoch) bleiben genau
    t = 1.79e9 + np.arange(1000.0)
    for method in REG_METHODS:
        m, b = regression(t, 0.5 * (t - 1.79e9) + 3, method)
        assert m == pytest.approx(0.5) and m * t[0] + b == pytest.approx(3.0, abs=1e-3)
    assert regression(np.ones(5), np.arange(5.0), "tls") == (pytest.approx(float("nan"), nan_ok=True),) * 2


def test_thai_font_needs_latin_letters_too(tmp_path):
    import os
    """Reine Thai-Schrift (wie Noto Sans Thai) wird übergangen: sonst fehlen Datei- und Signalnamen."""
    import pytest
    from messgraph import fonts
    loma = "/usr/share/fonts/opentype/tlwg/Loma.otf"
    try:
        from fontTools import subset
    except ImportError:
        pytest.skip("fontTools fehlt")
    if not os.path.exists(loma):
        pytest.skip("Loma fehlt")
    thai_only = tmp_path / "NurThai.otf"
    options = subset.Options()
    font = subset.load_font(loma, options)
    sub = subset.Subsetter(options)
    sub.populate(unicodes=list(range(0x0E00, 0x0E80)))
    sub.subset(font)
    subset.save_font(font, str(thai_only), options)
    assert fonts.has_thai(str(thai_only)) and not fonts.has_latin(str(thai_only))
    assert fonts.has_latin(loma)
    assert fonts.find_thai_font([str(thai_only), loma]) == loma
    assert fonts.find_thai_font([str(thai_only)]) != str(thai_only)
