import numpy as np
import pytest

from messgraph import compare, progress
from messgraph.data_model import Channel, Dataset


def ds(path, sigs, **kw):
    return Dataset(path=path, channels=[Channel(name=n, unit="V", x=np.arange(len(v), dtype=float),
                                                y=np.asarray(v, dtype=float), **kw) for n, v in sigs.items()])


def test_similarity_and_groups():
    a = ds("/m/a.csv", {"U": [1], "I": [1], "T": [1]})
    b = ds("/m/b.csv", {"U": [1], "I": [1], "T": [1], "P": [1]})
    c = ds("/m/c.csv", {"x": [1], "y": [1]})
    d = ds("/n/a.csv", {"U": [1], "I": [1]})
    assert compare.similarity(a, b) == pytest.approx(0.75) and compare.similarity(a, c) == 0
    groups = compare.similar_groups([a, b, c, d])
    assert groups == [[a, b, d]]                                  # c passt nicht dazu
    assert compare.column_names([a, b, d]) == ["m/a.csv", "b.csv", "n/a.csv"]
    assert compare.signal_union([a, b, d]) == [("U", 3), ("I", 3), ("T", 2), ("P", 1)]


def test_compute_table_missing_nan_and_text():
    a = ds("/m/a.csv", {"U": [1, 2, 3, np.nan], "I": [5, 5]})
    b = ds("/m/b.csv", {"U": [10, 20], "X": [np.nan]})
    r = compare.compute([a, b], ["U", "I"], ["max", "avg"])        # Reihenfolge avg, min, max bleibt fest
    assert [(row.signal, row.stat) for row in r.rows] == [("U", "avg"), ("U", "max"), ("I", "avg"), ("I", "max")]
    assert r.rows[0].values == [2.0, 15.0] and r.rows[1].values == [3.0, 20.0]
    assert r.rows[2].values == [5.0, None] and r.rows[0].unit == "V"
    text = compare.to_text(r, ";", ",")
    assert text.splitlines()[0] == "Signal;Einheit;Kennwert;Toleranz %;a.csv;b.csv;Abweichung"
    assert "U;V;avg;;2;15;" in text and "I;V;avg;;5;;" in text
    text = compare.to_text(r, ";", ",", tolerances={"U": "50"})
    assert "U;V;avg;50;2;15;a.csv, b.csv" in text and "U;V;max;50;3;20;a.csv, b.csv" in text


def test_mf4_full_resolution_and_reduced_marker(tmp_path):
    calls = []
    def loader():
        calls.append(1)
        return np.arange(4.0), np.array([0.0, 9.0, -9.0, 0.0]), "V"
    mf4 = Dataset(path="m.mf4", channels=[Channel(name="U", source="m.mf4", loader=loader,
                                                  x=np.arange(2.0), y=np.array([0.0, 1.0]), ds_note="reduziert")])
    pq = ds("p.parquet", {"U": [1.0, 3.0]}, ds_note="reduziert")
    r = compare.compute([mf4, pq], ["U"], compare.STATS)
    assert calls == [1] and r.rows[1].values[0] == -9.0 and r.rows[2].values[0] == 9.0   # volle Auflösung
    assert r.rows[0].reduced == [False, True] and r.any_reduced
    assert "1*" in compare.to_text(r) or "3*" in compare.to_text(r)
    path = compare.write_csv(str(tmp_path / "v"), r)
    assert path.endswith(".csv") and (tmp_path / "v.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_compute_progress_and_cancel():
    a = ds("a.csv", {f"s{i}": [i] for i in range(4)})
    job = Job = progress.Job("v")
    with progress.track(job):
        compare.compute([a], ["s0", "s1"], ["avg"])
    assert job.fraction == 1.0
    job = progress.Job("v")
    job.cancelled = True
    with pytest.raises(progress.Cancelled), progress.track(job):
        compare.compute([a], ["s0"], ["avg"])


def test_deviations_and_percent_parsing():
    assert compare.parse_percent("2,5 %") == 2.5 and compare.parse_percent("") is None
    assert compare.parse_percent("x") is None and compare.parse_percent("-3") is None
    assert compare.deviations([100, 102, 99], None) == [False] * 3
    assert compare.deviations([100, 102, 99], 5) == [False, False, False]
    assert compare.deviations([100, 102, 120], 5) == [False, False, True]   # Median 102: 120 liegt 17,6 % darüber
    assert compare.deviations([100, 102, 120], 20) == [False, False, False]
    assert compare.deviations([10, 10.5], 4) == [True, True] and compare.deviations([10, 10.4], 4) == [False, False]
    assert compare.deviations([0, 0, 1], 1) == [False, False, True]        # Bezug 0: jeder Wert ungleich 0
    assert compare.deviations([5, None, 50], 10) == [True, False, True]
    assert compare.deviations([5, None, None], 1) == [False, False, False]
