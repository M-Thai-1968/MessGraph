"""MDF/MF4 mit doppelten Kanalnamen, Text-Kanälen, Konstanten und Wert->Text-Umrechnung."""
import sys
import types

import numpy as np
import pytest

from messgraph.data_model import find_channel
from messgraph.loaders import load_file
from test_gui_logic import env  # noqa: E402,F401  (Fixture wiederverwenden)

SN = types.SimpleNamespace


def C(name, unit="", channel_type=0, data_type=0):
    return SN(name=name, unit=unit, channel_type=channel_type, data_type=data_type)


class BigMDF:
    """Gruppe 0: Zeit; 1: Botschaft IVT6_Msg_Result_I (2 Kanäle, Name IVT_Result_I doppelt mit Gruppe 2);
    2: IVT7_Msg_Result_I; 3: einzelner Kanal Temp (doppelt mit Gruppe 4, beide ohne Gruppennamen);
    5: zweimal "dup" in derselben Gruppe; 6: VLSD-String; 7: 1 Wert; 8: 0 Werte; 9: Wert->Text."""
    version = "4.10"

    def __init__(self, path):
        def G(channels, cycles=100, acq=""):
            return SN(channels=channels, channel_group=SN(cycles_nr=cycles, acq_name=acq, comment=""))
        self.groups = [
            G([C("time")]),
            G([C("t1", channel_type=2), C("IVT_Result_I", "A"), C("IVT_Counter")], acq="IVT6_Msg_Result_I"),
            G([C("t2", channel_type=2), C("IVT_Result_I", "A"), C("IVT_Status")], acq="IVT7_Msg_Result_I"),
            G([C("t3", channel_type=2), C("Temp", "degC")]),
            G([C("t4", channel_type=2), C("Temp", "degC")]),
            G([C("t5", channel_type=2), C("dup"), C("dup")]),
            G([C("t6", channel_type=2), C("Comment", channel_type=1, data_type=7)]),
            G([C("t7", channel_type=2), C("SW_Version")], cycles=1),
            G([C("t8", channel_type=2), C("Never")], cycles=0),
            G([C("t9", channel_type=2), C("ChargeState")]),
        ]
        self.masters_db = {g: 0 for g in range(1, 10)}
        self.channels_db = {}
        for g, grp in enumerate(self.groups):
            for i, c in enumerate(grp.channels):
                self.channels_db.setdefault(c.name, []).append((g, i))
        self.calls = []

    def get(self, name, group=None, index=None, raw=False):
        self.calls.append((name, group, index, raw))
        n = 5 + group                                     # jede Gruppe mit eigener Zeitachse
        t = np.linspace(0, 1, n) + group
        if name == "ChargeState":
            raw_vals = np.array([0, 1, 1, 3, 3, 0, 1, 3, 3, 1, 0, 0, 3, 1][:n])
            if raw:
                return SN(samples=raw_vals, timestamps=t, unit="")
            names = {0: b"Idle", 1: b"Charging", 3: b"Done"}
            return SN(samples=np.array([names[v] for v in raw_vals]), timestamps=t, unit="")
        if name == "SW_Version":
            return SN(samples=np.array([42.0]), timestamps=np.array([0.5]), unit="")
        return SN(samples=np.arange(n, dtype=float) * (group + 1) + index, timestamps=t, unit="")

    def close(self):
        pass


@pytest.fixture
def ds(tmp_path, monkeypatch):
    mod = types.ModuleType("asammdf")
    mod.MDF = BigMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    path = tmp_path / "big.mdf"
    path.write_bytes(b"x")
    return load_file(str(path))


def test_unique_display_names(ds):
    names = [c.name for c in ds.channels]
    assert len(names) == len(set(names))
    assert "IVT6_Msg_Result_I / IVT_Result_I" in names and "IVT7_Msg_Result_I / IVT_Result_I" in names
    assert "Temp [g3]" in names and "Temp [g4]" in names              # Gruppe mit nur einem Datenkanal
    assert "dup [g5:i1]" in names and "dup [g5:i2]" in names          # doppelt in derselben Gruppe
    assert "IVT_Counter" in names                                     # eindeutige Namen bleiben
    assert find_channel(ds.channels, "IVT_Result_I (G1)").name == "IVT6_Msg_Result_I / IVT_Result_I"
    assert any("doppeltem Namen" in line for line in ds.info)


def test_each_channel_loads_by_group_and_index_with_own_time(ds):
    a = find_channel(ds.channels, "IVT6_Msg_Result_I / IVT_Result_I")
    b = find_channel(ds.channels, "IVT7_Msg_Result_I / IVT_Result_I")
    d1, d2 = find_channel(ds.channels, "dup [g5:i1]"), find_channel(ds.channels, "dup [g5:i2]")
    for c in (a, b, d1, d2):
        c.load()
    assert a.x.size == 6 and b.x.size == 7 and a.x[0] == 1.0 and b.x[0] == 2.0   # kein Resampling
    assert not np.array_equal(d1.y, d2.y)
    calls = ds.extra["mdf"].calls
    assert ("IVT_Result_I", 1, 1, False) in calls and ("dup", 5, 2, False) in calls


def test_kinds_and_value_text(ds):
    kinds = {c.name: c.kind for c in ds.channels}
    assert kinds["Comment"] == "text" and kinds["SW_Version"] == "const" and kinds["Never"] == "empty"
    assert kinds["ChargeState"] == "" and kinds["IVT_Counter"] == ""
    assert any("Nicht darstellbar" in line for line in ds.info)
    state = find_channel(ds.channels, "ChargeState")
    state.load()
    assert state.y.dtype.kind == "f" and set(state.y.tolist()) <= {0.0, 1.0, 3.0}       # Zahlen im Graphen
    assert state.value_text == {0.0: "Idle", 1.0: "Charging", 3.0: "Done"}


def test_gui_handling(env, ds):
    app = env.app
    app.datasets.append(ds)
    app._refresh_channel_list()
    texts = [i["value"] for i in env.state.items.values() if i["kind"] == "add_text"]
    assert any("Comment" in str(v) and "nicht darstellbar" in str(v) for v in texts)
    assert not any(c.name in ("Comment", "SW_Version", "Never") for c in app.checkboxes)
    const = find_channel(ds.channels, "SW_Version")
    app._request_add(const, None)
    assert "Konstante 42" in env.state.items[app.status]["value"]
    assert not app.layout.contains(const)
    text = find_channel(ds.channels, "Comment")
    app._request_add(text, None)
    assert "nicht darstellbar" in env.state.items[app.status]["value"]
    state = find_channel(ds.channels, "ChargeState")
    state.load()
    assert app._with_text(state, 1.0).endswith("(Charging)") and "(" not in app._with_text(state, 0.5)
    env.state.items[app.filter_input]["value"] = "ivt_result_i (g1)"            # Suche auch über frühere Namen
    app._refresh_channel_list()
    assert [c.name for c in app.checkboxes] == ["IVT6_Msg_Result_I / IVT_Result_I"]
