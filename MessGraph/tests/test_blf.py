import struct
from datetime import datetime

import numpy as np
import pytest

from messgraph import blf, dbc
from messgraph.data_model import LoadError
from messgraph.databases import DatabaseConfig, apply_databases, install_databases

DBC = """VERSION ""
BU_: A
BO_ 256 Motor: 8 A
 SG_ Drehzahl : 0|16@1+ (0.25,0) [0|16000] "rpm" Vector__XXX
 SG_ Temp : 16|8@1+ (1,-40) [-40|215] "degC" Vector__XXX
BO_ 512 Batt: 8 A
 SG_ Spannung : 7|16@0+ (0.01,0) [0|655] "V" Vector__XXX
 SG_ Strom : 16|16@1- (0.1,0) [-3000|3000] "A" Vector__XXX
 SG_ Klein : 39|4@0- (1,0) [-8|7] "" Vector__XXX
BO_ 2566844672 Ext: 8 A
 SG_ V : 8|16@1+ (0.5,0) [0|250] "km/h" Vector__XXX
BO_ 768 Mux: 8 A
 SG_ Sel M : 0|8@1+ (1,0) [0|1] "" Vector__XXX
 SG_ A m0 : 8|8@1+ (1,0) [0|255] "" Vector__XXX
 SG_ B m1 : 8|8@1+ (2,0) [0|510] "" Vector__XXX
CM_ SG_ 256 Drehzahl "Kommentar";
"""


def test_dbc_parse_and_bit_layouts(tmp_path):
    path = tmp_path / "a.dbc"
    path.write_text(DBC)
    msgs = dbc.parse(str(path))
    assert set(msgs) == {(256, False), (512, False), (0x18FEF100, True), (768, False)}
    batt = msgs[(512, False)]
    spannung = next(s for s in batt.signals if s.name == "Spannung")
    assert spannung.bit_positions()[:9] == [7, 6, 5, 4, 3, 2, 1, 0, 15]          # Motorola-Sägezahn
    data = np.zeros((2, 8), dtype=np.uint8)
    data[0, :2] = list(struct.pack(">H", 40012))                                  # 400,12 V
    data[0, 2:4] = list(struct.pack("<h", -125))                                  # -12,5 A
    data[0, 4] = 0b1010_0000                                                      # Klein = -6 (4 Bit Motorola)
    data[1, :2] = list(struct.pack(">H", 100))
    out = dbc.decode(batt, data)
    assert out["Spannung"][1].tolist() == pytest.approx([400.12, 1.0])
    assert out["Strom"][1][0] == pytest.approx(-12.5) and out["Klein"][1][0] == -6
    mux = msgs[(768, False)]
    data = np.array([[0, 7, 0, 0, 0, 0, 0, 0], [1, 7, 0, 0, 0, 0, 0, 0]], dtype=np.uint8)
    out = dbc.decode(mux, data)
    assert out["A"][0].tolist() == [True, False] and out["B"][0].tolist() == [False, True] and out["B"][1][1] == 14


def make_blf(tmp_path, fd=False):
    msgs = []
    for k in range(200):
        ts = k * 0.01
        msgs.append((ts, 1, 0x100, False, struct.pack("<HB5x", int((1000 + k) / 0.25), 60)))
        if k % 2 == 0:
            msgs.append((ts + 0.001, 2, 0x18FEF100, True, bytes([0]) + struct.pack("<H", 2 * k) + bytes(5)))
        if fd and k % 4 == 0:
            msgs.append((ts + 0.002, 1, 0x300, False, bytes(range(20))))
    return blf.write(str(tmp_path / "m.blf"), msgs, datetime(2026, 11, 9, 8, 0, 0), per_container=37)


def test_read_blf_containers_ext_and_fd(tmp_path):
    frames = blf.read(make_blf(tmp_path, fd=True))
    assert frames.time.size == 350 and frames.start == (datetime(2026, 11, 9, 8) - datetime(1970, 1, 1)).total_seconds()
    assert frames.keys() == [(1, 0x100, False), (1, 0x300, False), (2, 0x18FEF100, True)]
    fd = frames.select(1, 0x300, False)
    assert frames.length[fd][0] == 20 and frames.data[fd][0, :20].tolist() == list(range(20))
    assert np.all(np.diff(frames.time) >= 0)
    with pytest.raises(LoadError):
        (tmp_path / "x.blf").write_bytes(b"nichts")
        blf.read(str(tmp_path / "x.blf"))


def test_blf_dataset_raw_then_dbc(tmp_path):
    from messgraph.loaders import load_file
    ds = load_file(make_blf(tmp_path))
    names = [c.name for c in ds.channels]
    assert names[0] == "0x100 (CAN 1) Byte 0" and "0x18FEF100 (CAN 2) Byte 2" in names
    assert ds.channels[0].x_epoch == ds.extra["start"] and "Datenbasen" in ds.info[1]
    (tmp_path / "a.dbc").write_text(DBC)
    config = DatabaseConfig.from_dict({"dbc": [[str(tmp_path / "a.dbc"), 0]]})
    install_databases(ds, config, apply_databases(ds, config, set(), None, ds.extra["start"]))
    by = {c.name: c for c in ds.channels}
    assert by["Drehzahl"].y[:3].tolist() == [1000, 1001, 1002] and by["Drehzahl"].unit == "rpm"
    assert by["Temp"].y[0] == 20 and by["V"].y[5] == 10 and by["V"].x[1] == pytest.approx(0.021)
    assert not any(n.startswith("0x100") for n in by)                 # dekodiert: keine Rohbytes mehr
    assert ds.extra["config"] is config and any("2 Botschaften" in i for i in ds.info)
    # nur Bus 2 dekodieren: Motor bleibt als Rohbytes
    config = DatabaseConfig.from_dict({"dbc": [[str(tmp_path / "a.dbc"), 2]]})
    install_databases(ds, config, apply_databases(ds, config, set(), None, ds.extra["start"]))
    names = [c.name for c in ds.channels]
    assert "V" in names and "Drehzahl" not in names and "0x100 (CAN 1) Byte 0" in names


def test_demo_blf_is_decodable():
    from pathlib import Path
    from messgraph.loaders import load_file
    demo = Path(__file__).parent.parent / "demo_data"
    ds = load_file(str(demo / "demo_can.blf"))
    config = DatabaseConfig.from_dict({"dbc": [[str(demo / "demo_can.dbc"), 0]]})
    install_databases(ds, config, apply_databases(ds, config, set(), None, ds.extra["start"]))
    by = {c.name: c for c in ds.channels}
    assert {"Drehzahl", "Kuehlmittel", "Spannung", "Strom", "Geschwindigkeit", "Zelle_min", "Zelle_max"} <= set(by)
    assert by["Spannung"].y[0] == pytest.approx(400.08, abs=1) and "0x7FF (CAN 1) Byte 0" in by


def test_reader_tolerates_missing_padding_inside_containers(tmp_path):
    """Manche Schreiber füllen Objekte im Container nicht auf 4 Byte auf; dann darf keine Botschaft fehlen."""
    import zlib
    objects = []
    for k in range(10):
        body = blf.CAN_MSG.pack(1, 0, 3, 0x123, bytes([k, 1, 2]).ljust(8, b"\0")) + b"\x01"   # 1 Byte extra: ungerade
        size = blf.OBJ_BASE.size + blf.OBJ_V1.size + len(body)
        objects.append(blf.OBJ_BASE.pack(b"LOBJ", 32, 1, size, blf.CAN_MESSAGE2)
                       + blf.OBJ_V1.pack(blf.TIME_TEN_MICS, 0, 0, k * 100) + body)        # ohne Füllbytes
    plain = b"".join(objects)
    half = len(plain) // 2 + 3                                                          # Objekt über zwei Container
    out = b""
    for part in (plain[:half], plain[half:]):
        packed = zlib.compress(part)
        size = blf.OBJ_BASE.size + blf.CONTAINER.size + len(packed)
        out += blf.OBJ_BASE.pack(b"LOBJ", 16, 1, size, blf.LOG_CONTAINER) + blf.CONTAINER.pack(2, len(part)) + packed
        out += b"\0" * (size % 4)
    st = (2026, 11, 1, 9, 8, 0, 0, 0)
    header = blf.FILE_HEADER.pack(b"LOGG", 144, 0, 1, 0, 0, 4, 7, 1, 0, 144 + len(out), 0, 10, 0, *st, *st)
    path = tmp_path / "p.blf"
    path.write_bytes(header.ljust(144, b"\0") + out)
    frames = blf.read(str(path))
    assert frames.time.size == 10 and frames.data[:, 0].tolist() == list(range(10))
    assert frames.time[1] == pytest.approx(0.001)                                       # 10-µs-Zeitstempel
