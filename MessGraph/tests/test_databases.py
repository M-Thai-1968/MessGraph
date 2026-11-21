from pathlib import Path
import sys
import types
from datetime import datetime, timezone

import numpy as np
import pytest

from messgraph.data_model import LoadError
from messgraph.databases import DatabaseConfig, apply_databases, parse_a2l
from messgraph.loaders import _mf4_entries, load_file

A2L = r'''
/* Kommentar /begin MEASUREMENT kaputt /end MEASUREMENT */
ASAP2_VERSION 1 71
/begin PROJECT P ""
 /begin MODULE M ""
  /begin COMPU_METHOD CM_lin "linear" LINEAR "%6.2" "rpm" COEFFS_LINEAR 0.25 -100 /end COMPU_METHOD
  /begin COMPU_METHOD CM_rat "rat" RAT_FUNC "%6.2" "degC" COEFFS 0 1 40 0 0 1 /end COMPU_METHOD
  /begin COMPU_METHOD CM_rat2 "rat" RAT_FUNC "%6.2" "V" COEFFS 0 100 0 0 0 2 /end COMPU_METHOD
  /begin COMPU_METHOD CM_quad "q" RAT_FUNC "%6.2" "x" COEFFS 1 0 0 0 0 1 /end COMPU_METHOD
  /begin COMPU_METHOD CM_tab "tab" TAB_INTP "%6.2" "%" COMPU_TAB_REF TAB1 /end COMPU_METHOD
  /begin COMPU_METHOD CM_verb "verb" TAB_VERB "%6.2" "" COMPU_TAB_REF VT1 /end COMPU_METHOD
  /begin COMPU_METHOD CM_id "id" IDENTICAL "%6.2" "A" /end COMPU_METHOD
  /begin COMPU_TAB TAB1 "" TAB_INTP 3 0 0 10 50 20 100 /end COMPU_TAB
  /begin MEASUREMENT nEng "Drehzahl" UWORD CM_lin 0 0 0 65535
    ECU_ADDRESS 0x1000
    /begin IF_DATA XCP LINK_MAP "x" 0 /end IF_DATA
  /end MEASUREMENT
  /begin MEASUREMENT tOil "Oel" SBYTE CM_rat 0 0 -40 215 /end MEASUREMENT
  /begin MEASUREMENT uBat "Batt" UWORD CM_rat2 0 0 0 1 /end MEASUREMENT
  /begin MEASUREMENT q "q" UWORD CM_quad 0 0 0 1 /end MEASUREMENT
  /begin MEASUREMENT pedal "p" UBYTE CM_tab 0 0 0 1 /end MEASUREMENT
  /begin MEASUREMENT gear "g" UBYTE CM_verb 0 0 0 1 /end MEASUREMENT
  /begin MEASUREMENT iBat "i" FLOAT32_IEEE CM_id 0 0 0 1 PHYS_UNIT "mA" /end MEASUREMENT
 /end MODULE
/end PROJECT
'''


def test_parse_a2l_units_and_conversions(tmp_path):
    p = tmp_path / "ecu.a2l"
    p.write_text(A2L)
    t = parse_a2l(str(p))
    assert sorted(t) == ["gear", "iBat", "nEng", "pedal", "q", "tOil", "uBat"]
    x = np.array([0.0, 400.0, 1000.0])
    assert t["nEng"].unit == "rpm" and t["nEng"].compu(x).tolist() == [-100, 0, 150]
    assert t["tOil"].unit == "degC" and t["tOil"].compu(np.array([40.0, 0.0])).tolist() == [0, -40]
    assert t["uBat"].compu(np.array([700.0])).tolist() == [14.0]       # int = 100 p / 2
    assert t["q"].compu is None and "quadratisch" in t["q"].compu_note
    assert t["pedal"].compu(np.array([5.0, 15.0])).tolist() == [25, 75]
    assert t["gear"].compu is None and "Texttabelle" in t["gear"].compu_note
    assert t["iBat"].compu is None and t["iBat"].unit == "mA"


def test_parse_a2l_errors(tmp_path):
    p = tmp_path / "leer.a2l"
    p.write_text("/begin PROJECT P \"\" /end PROJECT")
    with pytest.raises(LoadError):
        parse_a2l(str(p))
    with pytest.raises(LoadError):
        parse_a2l(str(tmp_path / "fehlt.a2l"))


def sig(samples, unit="", t=None):
    return types.SimpleNamespace(samples=np.asarray(samples), timestamps=np.arange(len(samples), dtype=float)
                                 if t is None else t, unit=unit)


class FakeDecoded:
    closed = False

    def __init__(self, names):
        C = types.SimpleNamespace
        self.groups = [C(channels=[C(name="t", channel_type=2)] + [C(name=n, unit="km/h") for n in names])]
        self.channels_db = {"t": ((0, 0),), **{n: ((0, i + 1),) for i, n in enumerate(names)}}

    def get(self, name, group=None, index=None, raw=False):
        return sig([10.0, 20.0], "km/h")

    def close(self):
        FakeDecoded.closed = True


class FakeMDF:
    def __init__(self, path):
        C = types.SimpleNamespace
        self.header = C(start_time=datetime(2026, 10, 1, 21, 0, 0, tzinfo=timezone.utc))
        self.groups = [C(channels=[C(name="time", channel_type=2), C(name="nEng\\XCP:1", unit=""),
                                   C(name="CAN_DataFrame.ID", unit=""), C(name="CAN_DataFrame.DataBytes", unit="")])]
        self.channels_db = {"time": ((0, 0),), "nEng\\XCP:1": ((0, 1),), "CAN_DataFrame.ID": ((0, 2),),
                            "CAN_DataFrame.DataBytes": ((0, 3),)}
        self.calls = []

    def get(self, name, group=None, index=None, raw=False):
        return sig([400.0, 800.0]) if name.startswith("nEng") else sig([1, 2])

    def extract_bus_logging(self, database_files):
        self.calls.append(database_files)
        dbcs = database_files["CAN"]
        if any("leer" in p for p, _ in dbcs):
            return FakeDecoded([])
        return FakeDecoded(["VehSpeed", "nEng\\XCP:1"])

    def close(self):
        pass


@pytest.fixture
def mf4(tmp_path, monkeypatch):
    mod = types.ModuleType("asammdf")
    mod.MDF = FakeMDF
    monkeypatch.setitem(sys.modules, "asammdf", mod)
    monkeypatch.setattr("time.localtime", lambda t=None: types.SimpleNamespace(tm_gmtoff=7200))
    p = tmp_path / "bus.mf4"
    p.write_bytes(b"x")
    return load_file(str(p)), tmp_path


def test_mf4_start_time_and_bus_hint(mf4):
    ds, _ = mf4
    assert ds.extra["bus_raw"]
    start = ds.channels[0].x_epoch
    from messgraph.timeparse import format_wallclock
    assert format_wallclock(start)[:16] == datetime(2026, 10, 1, 21, tzinfo=timezone.utc).astimezone() \
        .strftime("%d.%m.%Y %H:%M")


def test_apply_dbc_per_channel_and_a2l(mf4):
    ds, tmp = mf4
    dbc = tmp / "fzg.dbc"
    dbc.write_text("VERSION \"\"")
    a2l = tmp / "ecu.a2l"
    a2l.write_text(A2L)
    cfg = DatabaseConfig(dbc=[(str(dbc), 2)], a2l=[str(a2l)], a2l_convert=True, cdd=[str(tmp / "d.cdd")])
    chans, info, warns, opened = apply_databases(ds, cfg, {"VehSpeed [km/h]", "nEng\\XCP:1 [rpm]"},
                                                 _mf4_entries, ds.extra["start"])
    assert ds.extra["mdf"].calls == [{"CAN": [(str(dbc), 2)]}]
    names = [c.name for c in chans]
    assert names == ["nEng\\XCP:1", "CAN_DataFrame.ID", "CAN_DataFrame.DataBytes", "VehSpeed", "nEng\\XCP:1 [DBC g0]"]
    assert chans[4].matches("nEng\\XCP:1 (DBC G0)")                          # ältere Ansichten finden ihn weiter
    neng = chans[0]
    assert neng.unit == "rpm" and neng.loaded and neng.y.tolist() == [0, 100]   # A2L: 0.25*x - 100
    assert chans[3].loaded and chans[3].x_epoch == ds.extra["start"]
    assert ds.channels[0] is not neng                                           # neue Objekte
    assert any("2 Signale" in i for i in info) and any("CAN 2" in i for i in info)
    assert any("CDD" in w for w in warns) and len(opened) == 1


def test_apply_errors_and_empty_result(mf4):
    ds, tmp = mf4
    with pytest.raises(LoadError, match="nicht gefunden"):
        apply_databases(ds, DatabaseConfig(dbc=[(str(tmp / "fehlt.dbc"), 0)]), set(), _mf4_entries, None)
    leer = tmp / "leer.dbc"
    leer.write_text("x")
    chans, info, warns, _ = apply_databases(ds, DatabaseConfig(dbc=[(str(leer), 0)]), set(), _mf4_entries, None)
    assert len(chans) == 3 and any("passt zu keiner" in w for w in warns)

    def boom(database_files):
        raise ModuleNotFoundError("No module named 'canmatrix'")
    ds.extra["mdf"].extract_bus_logging = boom
    with pytest.raises(LoadError, match="canmatrix"):
        apply_databases(ds, DatabaseConfig(dbc=[(str(leer), 0)]), set(), _mf4_entries, None)


def test_config_roundtrip():
    cfg = DatabaseConfig(dbc=[("a.dbc", 0), ("b.dbc", 3)], arxml=[("s.arxml", 1)], a2l=["x.a2l", "y.a2l"],
                         a2l_convert=True, cdd=["d.cdd"])
    assert DatabaseConfig.from_dict(cfg.to_dict()) == cfg
    assert DatabaseConfig.from_dict(None).empty
    old = DatabaseConfig.from_dict({"dbc": [["a.dbc", 0]], "a2l": "x.a2l", "cdd": ""})   # Ansicht bis 1.20
    assert old.a2l == ["x.a2l"] and old.cdd == [] and old.arxml == []


def test_config_add_sorts_by_extension():
    cfg = DatabaseConfig()
    unknown = cfg.add(["/p/a.DBC", "/p/s.arxml", "/p/e.a2l", "/p/f.a2l", "/p/d.cdd", "/p/notiz.txt", "/p/a.DBC"])
    assert unknown == ["/p/notiz.txt"]
    assert cfg.dbc == [("/p/a.DBC", 0)] and cfg.arxml == [("/p/s.arxml", 0)]
    assert cfg.a2l == ["/p/e.a2l", "/p/f.a2l"] and cfg.cdd == ["/p/d.cdd"]
    assert cfg.bus == [("/p/a.DBC", 0), ("/p/s.arxml", 0)] and len(cfg.files()) == 5
    cfg.remove("a2l", 0)
    assert cfg.a2l == ["/p/f.a2l"]


def test_mf4_arxml_converted_and_multiple_a2l(mf4):
    from test_arxml import ARXML
    ds, tmp = mf4
    ar = tmp / "system.arxml"
    ar.write_text(ARXML, encoding="utf-8")
    seen = {}
    original = ds.extra["mdf"].extract_bus_logging

    def capture(database_files):
        seen["files"] = database_files["CAN"]
        seen["text"] = [open(p, encoding="utf-8").read() for p, _ in database_files["CAN"]]
        return original(database_files)
    ds.extra["mdf"].extract_bus_logging = capture
    first, second = tmp / "a.a2l", tmp / "b.a2l"
    first.write_text(A2L)
    second.write_text(A2L.replace("nEng", "anders"))
    cfg = DatabaseConfig(arxml=[(str(ar), 2)], a2l=[str(first), str(second)])
    chans, info, warns, _ = apply_databases(ds, cfg, set(), _mf4_entries, None)
    (path, channel), = seen["files"]
    assert channel == 2 and path.endswith(".dbc") and not Path(path).exists()     # Hilfsdatei wieder gelöscht
    assert "BO_ 256 MotorFrame: 8" in seen["text"][0] and "SG_ Drehzahl : 0|16@1+ (0.25,0.0)" in seen["text"][0]
    assert any("Nicht benötigt" in i and "b.a2l" in i for i in info)
    assert any("a.a2l, b.a2l" in i for i in info)
