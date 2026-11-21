import sys
import types

import numpy as np
import pytest

from messgraph import downsample as ds
from messgraph.downsample import DownsampleConfig


def data(n=1000):
    x = np.arange(n, dtype=float) * 0.001
    y = np.sin(x * 20)
    return x, y


def test_minmax_keeps_extremes_in_time_order():
    x, y = data(1000)
    y[123], y[777] = 9.0, -9.0
    nx, ny = ds.minmax(x, y, 10)
    assert ny.max() == 9.0 and ny.min() == -9.0
    assert np.all(np.diff(nx) >= 0) and nx.size <= 200
    assert nx[ny.argmax()] == x[123] and nx[ny.argmin()] == x[777]   # echte Zeit der Spitze


def test_minmax_gap_constant_and_remainder():
    x = np.arange(25, dtype=float)
    y = np.ones(25)
    y[10:20] = np.nan                     # ein ganzer Block ohne Werte
    nx, ny = ds.minmax(x, y, 10)
    assert nx.tolist() == [0, 10, 20, 21, 22, 23, 24]   # konstanter Block: ein Punkt; Rest unverändert
    assert ny[0] == 1 and np.isnan(ny[1]) and ny[2:].tolist() == [1] * 5   # Lücke bleibt Lücke


def test_mean_blocks_nan_and_remainder():
    x = np.arange(7, dtype=float)
    y = np.array([1, 3, np.nan, np.nan, 5, 7, 10], dtype=float)
    nx, ny = ds.mean(x, y, 2)
    assert nx.tolist() == [0.5, 2.5, 4.5, 6.0]
    assert ny[0] == 2 and np.isnan(ny[1]) and ny[2] == 6 and ny[3] == 10


def test_stride_keeps_last_value():
    x, y = data(105)
    nx, ny = ds.stride(x, y, 10)
    assert nx[0] == x[0] and nx[-1] == x[-1] and nx.size == 12


def test_grid_means_and_gaps():
    x = np.array([0.0, 0.004, 0.009, 0.010, 0.031, 0.039])
    y = np.array([1.0, 2.0, 3.0, 10.0, 5.0, 7.0])
    nx, ny = ds.grid(x, y, 0.01)
    assert nx.tolist() == pytest.approx([0.005, 0.015, 0.035])       # Intervall 0.02..0.03 fehlt: Lücke
    assert ny.tolist() == pytest.approx([2.0, 10.0, 6.0])


def test_apply_modes_and_auto_threshold():
    x, y = data(10_000)
    assert ds.apply(x, y, DownsampleConfig(mode="off"))[2] == ""
    auto = DownsampleConfig(mode="auto", auto_threshold=20_000, auto_target=1000)
    assert ds.apply(x, y, auto)[0] is x                               # unter der Schwelle unverändert
    auto = DownsampleConfig(mode="auto", auto_threshold=5000, auto_target=1000)
    nx, ny, note = ds.apply(x, y, auto)
    assert 500 <= nx.size <= 1000 and "10.000 -> " in note
    for method, size in (("minmax", 2000), ("mean", 1000), ("stride", 1000)):
        nx, _, note = ds.apply(x, y, DownsampleConfig(mode="manual", method=method, factor=10))
        assert abs(nx.size - size) <= 2 and note, method
    nx, _, _ = ds.apply(x, y, DownsampleConfig(mode="manual", method="grid", interval=0.1))
    assert nx.size == 100


def test_config_roundtrip_validation_and_description():
    cfg = DownsampleConfig.from_dict({"mode": "manual", "method": "grid", "interval": 0.5, "unbekannt": 1})
    assert cfg.method == "grid" and cfg.interval == 0.5
    assert DownsampleConfig.from_dict(cfg.to_dict()) == cfg
    bad = DownsampleConfig.from_dict({"mode": "x", "method": "y", "factor": 0, "interval": -1, "auto_target": 10**9})
    assert (bad.mode, bad.method, bad.factor, bad.interval) == ("auto", "minmax", 2, 0.01)
    assert bad.auto_target == bad.auto_threshold
    assert "2.000.000" in DownsampleConfig().describe()
    assert "Zeitraster 0.5" in cfg.describe()


def test_parquet_and_mf4_are_downsampled_csv_not(tmp_path, monkeypatch):
    import pandas as pd
    from messgraph.loaders import load_file
    n = 50_000
    df = pd.DataFrame({"time": np.arange(n) * 0.001, "v": np.sin(np.arange(n) / 100.0)})
    pa = types.ModuleType("pyarrow")
    pq = types.ModuleType("pyarrow.parquet")
    pq.read_table = lambda path: types.SimpleNamespace(to_pandas=lambda: df)
    pa.parquet = pq
    monkeypatch.setitem(sys.modules, "pyarrow", pa)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", pq)
    ds.set_config(DownsampleConfig(mode="manual", method="mean", factor=10))
    try:
        p = tmp_path / "a.parquet"
        p.write_bytes(b"x")
        dataset = load_file(str(p))
        c = dataset.channels[0]
        assert c.y.size == 5000 and "50.000 -> 5.000" in c.ds_note
        assert any("Faktor 10" in line for line in dataset.info) and any("1 Signale reduziert" in line for line in dataset.info)

        class MDF:
            def __init__(self, path):
                C = types.SimpleNamespace
                self.groups = [C(channels=[C(name="t", channel_type=2), C(name="s", unit="V")])]
                self.channels_db = {"t": ((0, 0),), "s": ((0, 1),)}

            def get(self, name, group=None, index=None, raw=False):
                return types.SimpleNamespace(samples=np.arange(n, dtype=float), timestamps=np.arange(n) * 0.001, unit="V")

            def close(self):
                pass
        mod = types.ModuleType("asammdf")
        mod.MDF = MDF
        monkeypatch.setitem(sys.modules, "asammdf", mod)
        m = tmp_path / "a.mf4"
        m.write_bytes(b"x")
        mf4 = load_file(str(m))
        ch = mf4.channels[0]
        ch.load()
        assert ch.y.size == 5000 and ch.ds_note and any("Faktor 10" in line for line in mf4.info)

        csv = tmp_path / "a.csv"
        csv.write_text("t,v\n" + "".join(f"{i},{i}\n" for i in range(1000)))
        assert load_file(str(csv)).channels[0].y.size == 1000        # CSV bleibt unverändert
    finally:
        ds.set_config(DownsampleConfig())
