import struct

import numpy as np
import pytest

from messgraph import arxml, blf, dbc
from messgraph.data_model import LoadError
from messgraph.databases import DatabaseConfig, apply_databases, install_databases

ARXML = """<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR xmlns="http://autosar.org/schema/r4.0">
<AR-PACKAGES><AR-PACKAGE><SHORT-NAME>Sys</SHORT-NAME><AR-PACKAGES>
 <AR-PACKAGE><SHORT-NAME>Cluster</SHORT-NAME><ELEMENTS>
  <CAN-CLUSTER><SHORT-NAME>CAN1</SHORT-NAME><CAN-CLUSTER-VARIANTS><CAN-CLUSTER-CONDITIONAL><PHYSICAL-CHANNELS>
   <CAN-PHYSICAL-CHANNEL><SHORT-NAME>Ch</SHORT-NAME><FRAME-TRIGGERINGS>
    <CAN-FRAME-TRIGGERING><SHORT-NAME>T1</SHORT-NAME><FRAME-REF DEST="CAN-FRAME">/Sys/Frames/MotorFrame</FRAME-REF>
     <CAN-ADDRESSING-MODE>STANDARD</CAN-ADDRESSING-MODE><IDENTIFIER>256</IDENTIFIER></CAN-FRAME-TRIGGERING>
    <CAN-FRAME-TRIGGERING><SHORT-NAME>T2</SHORT-NAME><FRAME-REF DEST="CAN-FRAME">/Sys/Frames/BattFrame</FRAME-REF>
     <CAN-ADDRESSING-MODE>STANDARD</CAN-ADDRESSING-MODE><IDENTIFIER>0x200</IDENTIFIER></CAN-FRAME-TRIGGERING>
    <CAN-FRAME-TRIGGERING><SHORT-NAME>T3</SHORT-NAME><FRAME-REF DEST="CAN-FRAME">/Sys/Frames/ExtFrame</FRAME-REF>
     <CAN-ADDRESSING-MODE>EXTENDED</CAN-ADDRESSING-MODE><IDENTIFIER>419364864</IDENTIFIER></CAN-FRAME-TRIGGERING>
    <CAN-FRAME-TRIGGERING><SHORT-NAME>T4</SHORT-NAME><FRAME-REF DEST="CAN-FRAME">/Sys/Frames/MuxFrame</FRAME-REF>
     <IDENTIFIER>0x300</IDENTIFIER></CAN-FRAME-TRIGGERING>
   </FRAME-TRIGGERINGS></CAN-PHYSICAL-CHANNEL>
  </PHYSICAL-CHANNELS></CAN-CLUSTER-CONDITIONAL></CAN-CLUSTER-VARIANTS></CAN-CLUSTER>
 </ELEMENTS></AR-PACKAGE>
 <AR-PACKAGE><SHORT-NAME>Frames</SHORT-NAME><ELEMENTS>
  <CAN-FRAME><SHORT-NAME>MotorFrame</SHORT-NAME><FRAME-LENGTH>8</FRAME-LENGTH><PDU-TO-FRAME-MAPPINGS>
   <PDU-TO-FRAME-MAPPING><SHORT-NAME>m</SHORT-NAME><PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER>
    <PDU-REF DEST="I-SIGNAL-I-PDU">/Sys/Pdus/MotorPdu</PDU-REF><START-POSITION>0</START-POSITION></PDU-TO-FRAME-MAPPING>
  </PDU-TO-FRAME-MAPPINGS></CAN-FRAME>
  <CAN-FRAME><SHORT-NAME>BattFrame</SHORT-NAME><FRAME-LENGTH>8</FRAME-LENGTH><PDU-TO-FRAME-MAPPINGS>
   <PDU-TO-FRAME-MAPPING><SHORT-NAME>m</SHORT-NAME><PDU-REF DEST="I-SIGNAL-I-PDU">/Sys/Pdus/BattPdu</PDU-REF>
    <START-POSITION>0</START-POSITION></PDU-TO-FRAME-MAPPING>
  </PDU-TO-FRAME-MAPPINGS></CAN-FRAME>
  <CAN-FRAME><SHORT-NAME>ExtFrame</SHORT-NAME><FRAME-LENGTH>8</FRAME-LENGTH><PDU-TO-FRAME-MAPPINGS>
   <PDU-TO-FRAME-MAPPING><SHORT-NAME>m</SHORT-NAME><PDU-REF DEST="I-SIGNAL-I-PDU">/Sys/Pdus/ExtPdu</PDU-REF>
    <START-POSITION>8</START-POSITION></PDU-TO-FRAME-MAPPING>
  </PDU-TO-FRAME-MAPPINGS></CAN-FRAME>
  <CAN-FRAME><SHORT-NAME>MuxFrame</SHORT-NAME><FRAME-LENGTH>8</FRAME-LENGTH><PDU-TO-FRAME-MAPPINGS>
   <PDU-TO-FRAME-MAPPING><SHORT-NAME>m</SHORT-NAME><PDU-REF DEST="MULTIPLEXED-I-PDU">/Sys/Pdus/MuxPdu</PDU-REF>
    <START-POSITION>0</START-POSITION></PDU-TO-FRAME-MAPPING>
  </PDU-TO-FRAME-MAPPINGS></CAN-FRAME>
 </ELEMENTS></AR-PACKAGE>
 <AR-PACKAGE><SHORT-NAME>Pdus</SHORT-NAME><ELEMENTS>
  <I-SIGNAL-I-PDU><SHORT-NAME>MotorPdu</SHORT-NAME><LENGTH>8</LENGTH><I-SIGNAL-TO-PDU-MAPPINGS>
   <I-SIGNAL-TO-I-PDU-MAPPING><SHORT-NAME>a</SHORT-NAME><I-SIGNAL-REF DEST="I-SIGNAL">/Sys/Signals/Drehzahl</I-SIGNAL-REF>
    <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER><START-POSITION>0</START-POSITION></I-SIGNAL-TO-I-PDU-MAPPING>
   <I-SIGNAL-TO-I-PDU-MAPPING><SHORT-NAME>b</SHORT-NAME><I-SIGNAL-REF DEST="I-SIGNAL">/Sys/Signals/Leistung</I-SIGNAL-REF>
    <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER><START-POSITION>32</START-POSITION></I-SIGNAL-TO-I-PDU-MAPPING>
  </I-SIGNAL-TO-PDU-MAPPINGS></I-SIGNAL-I-PDU>
  <I-SIGNAL-I-PDU><SHORT-NAME>BattPdu</SHORT-NAME><LENGTH>8</LENGTH><I-SIGNAL-TO-PDU-MAPPINGS>
   <I-SIGNAL-TO-I-PDU-MAPPING><SHORT-NAME>c</SHORT-NAME><I-SIGNAL-REF DEST="I-SIGNAL">/Sys/Signals/Spannung</I-SIGNAL-REF>
    <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-FIRST</PACKING-BYTE-ORDER><START-POSITION>7</START-POSITION></I-SIGNAL-TO-I-PDU-MAPPING>
   <I-SIGNAL-TO-I-PDU-MAPPING><SHORT-NAME>d</SHORT-NAME><I-SIGNAL-REF DEST="I-SIGNAL">/Sys/Signals/Strom</I-SIGNAL-REF>
    <PACKING-BYTE-ORDER>MOST-SIGNIFICANT-BYTE-LAST</PACKING-BYTE-ORDER><START-POSITION>16</START-POSITION></I-SIGNAL-TO-I-PDU-MAPPING>
  </I-SIGNAL-TO-PDU-MAPPINGS></I-SIGNAL-I-PDU>
  <I-SIGNAL-I-PDU><SHORT-NAME>ExtPdu</SHORT-NAME><LENGTH>7</LENGTH><I-SIGNAL-TO-PDU-MAPPINGS>
   <I-SIGNAL-TO-I-PDU-MAPPING><SHORT-NAME>e</SHORT-NAME><I-SIGNAL-REF DEST="I-SIGNAL">/Sys/Signals/Geschwindigkeit</I-SIGNAL-REF>
    <START-POSITION>0</START-POSITION></I-SIGNAL-TO-I-PDU-MAPPING>
  </I-SIGNAL-TO-PDU-MAPPINGS></I-SIGNAL-I-PDU>
  <MULTIPLEXED-I-PDU><SHORT-NAME>MuxPdu</SHORT-NAME></MULTIPLEXED-I-PDU>
 </ELEMENTS></AR-PACKAGE>
 <AR-PACKAGE><SHORT-NAME>Signals</SHORT-NAME><ELEMENTS>
  <I-SIGNAL><SHORT-NAME>Drehzahl</SHORT-NAME><LENGTH>16</LENGTH><SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Sys/SysSig/Drehzahl</SYSTEM-SIGNAL-REF></I-SIGNAL>
  <I-SIGNAL><SHORT-NAME>Leistung</SHORT-NAME><LENGTH>32</LENGTH>
   <NETWORK-REPRESENTATION-PROPS><SW-DATA-DEF-PROPS-VARIANTS><SW-DATA-DEF-PROPS-CONDITIONAL>
    <BASE-TYPE-REF DEST="SW-BASE-TYPE">/Sys/Types/float32</BASE-TYPE-REF></SW-DATA-DEF-PROPS-CONDITIONAL></SW-DATA-DEF-PROPS-VARIANTS></NETWORK-REPRESENTATION-PROPS>
   <SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Sys/SysSig/Leistung</SYSTEM-SIGNAL-REF></I-SIGNAL>
  <I-SIGNAL><SHORT-NAME>Spannung</SHORT-NAME><LENGTH>16</LENGTH><SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Sys/SysSig/Spannung</SYSTEM-SIGNAL-REF></I-SIGNAL>
  <I-SIGNAL><SHORT-NAME>Strom</SHORT-NAME><LENGTH>16</LENGTH>
   <NETWORK-REPRESENTATION-PROPS><SW-DATA-DEF-PROPS-VARIANTS><SW-DATA-DEF-PROPS-CONDITIONAL>
    <BASE-TYPE-REF DEST="SW-BASE-TYPE">/Sys/Types/sint16</BASE-TYPE-REF></SW-DATA-DEF-PROPS-CONDITIONAL></SW-DATA-DEF-PROPS-VARIANTS></NETWORK-REPRESENTATION-PROPS>
   <SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Sys/SysSig/Strom</SYSTEM-SIGNAL-REF></I-SIGNAL>
  <I-SIGNAL><SHORT-NAME>Geschwindigkeit</SHORT-NAME><LENGTH>16</LENGTH><SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Sys/SysSig/Geschwindigkeit</SYSTEM-SIGNAL-REF></I-SIGNAL>
 </ELEMENTS></AR-PACKAGE>
 <AR-PACKAGE><SHORT-NAME>SysSig</SHORT-NAME><ELEMENTS>
  <SYSTEM-SIGNAL><SHORT-NAME>Drehzahl</SHORT-NAME><PHYSICAL-PROPS><SW-DATA-DEF-PROPS-VARIANTS><SW-DATA-DEF-PROPS-CONDITIONAL>
   <COMPU-METHOD-REF DEST="COMPU-METHOD">/Sys/Compu/Rpm</COMPU-METHOD-REF></SW-DATA-DEF-PROPS-CONDITIONAL></SW-DATA-DEF-PROPS-VARIANTS></PHYSICAL-PROPS></SYSTEM-SIGNAL>
  <SYSTEM-SIGNAL><SHORT-NAME>Leistung</SHORT-NAME></SYSTEM-SIGNAL>
  <SYSTEM-SIGNAL><SHORT-NAME>Spannung</SHORT-NAME><PHYSICAL-PROPS><SW-DATA-DEF-PROPS-VARIANTS><SW-DATA-DEF-PROPS-CONDITIONAL>
   <COMPU-METHOD-REF DEST="COMPU-METHOD">/Sys/Compu/Volt</COMPU-METHOD-REF></SW-DATA-DEF-PROPS-CONDITIONAL></SW-DATA-DEF-PROPS-VARIANTS></PHYSICAL-PROPS></SYSTEM-SIGNAL>
  <SYSTEM-SIGNAL><SHORT-NAME>Strom</SHORT-NAME><PHYSICAL-PROPS><SW-DATA-DEF-PROPS-VARIANTS><SW-DATA-DEF-PROPS-CONDITIONAL>
   <COMPU-METHOD-REF DEST="COMPU-METHOD">/Sys/Compu/Ampere</COMPU-METHOD-REF></SW-DATA-DEF-PROPS-CONDITIONAL></SW-DATA-DEF-PROPS-VARIANTS></PHYSICAL-PROPS></SYSTEM-SIGNAL>
  <SYSTEM-SIGNAL><SHORT-NAME>Geschwindigkeit</SHORT-NAME><PHYSICAL-PROPS><SW-DATA-DEF-PROPS-VARIANTS><SW-DATA-DEF-PROPS-CONDITIONAL>
   <COMPU-METHOD-REF DEST="COMPU-METHOD">/Sys/Compu/Kmh</COMPU-METHOD-REF></SW-DATA-DEF-PROPS-CONDITIONAL></SW-DATA-DEF-PROPS-VARIANTS></PHYSICAL-PROPS></SYSTEM-SIGNAL>
 </ELEMENTS></AR-PACKAGE>
 <AR-PACKAGE><SHORT-NAME>Compu</SHORT-NAME><ELEMENTS>
  <COMPU-METHOD><SHORT-NAME>Rpm</SHORT-NAME><CATEGORY>LINEAR</CATEGORY><UNIT-REF DEST="UNIT">/Sys/Units/rpm</UNIT-REF>
   <COMPU-INTERNAL-TO-PHYS><COMPU-SCALES><COMPU-SCALE><COMPU-RATIONAL-COEFFS>
    <COMPU-NUMERATOR><V>0</V><V>1</V></COMPU-NUMERATOR><COMPU-DENOMINATOR><V>4</V></COMPU-DENOMINATOR>
   </COMPU-RATIONAL-COEFFS></COMPU-SCALE></COMPU-SCALES></COMPU-INTERNAL-TO-PHYS></COMPU-METHOD>
  <COMPU-METHOD><SHORT-NAME>Volt</SHORT-NAME><CATEGORY>LINEAR</CATEGORY><UNIT-REF DEST="UNIT">/Sys/Units/V</UNIT-REF>
   <COMPU-INTERNAL-TO-PHYS><COMPU-SCALES><COMPU-SCALE><COMPU-RATIONAL-COEFFS>
    <COMPU-NUMERATOR><V>0</V><V>0.01</V></COMPU-NUMERATOR><COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>
   </COMPU-RATIONAL-COEFFS></COMPU-SCALE></COMPU-SCALES></COMPU-INTERNAL-TO-PHYS></COMPU-METHOD>
  <COMPU-METHOD><SHORT-NAME>Ampere</SHORT-NAME><CATEGORY>LINEAR</CATEGORY><UNIT-REF DEST="UNIT">/Sys/Units/A</UNIT-REF>
   <COMPU-INTERNAL-TO-PHYS><COMPU-SCALES><COMPU-SCALE><COMPU-RATIONAL-COEFFS>
    <COMPU-NUMERATOR><V>0</V><V>0.1</V></COMPU-NUMERATOR><COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>
   </COMPU-RATIONAL-COEFFS></COMPU-SCALE></COMPU-SCALES></COMPU-INTERNAL-TO-PHYS></COMPU-METHOD>
  <COMPU-METHOD><SHORT-NAME>Kmh</SHORT-NAME><CATEGORY>LINEAR</CATEGORY><UNIT-REF DEST="UNIT">/Sys/Units/kmh</UNIT-REF>
   <COMPU-INTERNAL-TO-PHYS><COMPU-SCALES><COMPU-SCALE><COMPU-RATIONAL-COEFFS>
    <COMPU-NUMERATOR><V>-10</V><V>0.5</V></COMPU-NUMERATOR><COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>
   </COMPU-RATIONAL-COEFFS></COMPU-SCALE></COMPU-SCALES></COMPU-INTERNAL-TO-PHYS></COMPU-METHOD>
 </ELEMENTS></AR-PACKAGE>
 <AR-PACKAGE><SHORT-NAME>Units</SHORT-NAME><ELEMENTS>
  <UNIT><SHORT-NAME>rpm</SHORT-NAME><DISPLAY-NAME>1/min</DISPLAY-NAME></UNIT>
  <UNIT><SHORT-NAME>V</SHORT-NAME></UNIT>
  <UNIT><SHORT-NAME>A</SHORT-NAME></UNIT>
  <UNIT><SHORT-NAME>kmh</SHORT-NAME><DISPLAY-NAME>km/h</DISPLAY-NAME></UNIT>
 </ELEMENTS></AR-PACKAGE>
 <AR-PACKAGE><SHORT-NAME>Types</SHORT-NAME><ELEMENTS>
  <SW-BASE-TYPE><SHORT-NAME>sint16</SHORT-NAME><BASE-TYPE-ENCODING>2C</BASE-TYPE-ENCODING></SW-BASE-TYPE>
  <SW-BASE-TYPE><SHORT-NAME>float32</SHORT-NAME><BASE-TYPE-ENCODING>IEEE754</BASE-TYPE-ENCODING></SW-BASE-TYPE>
 </ELEMENTS></AR-PACKAGE>
</AR-PACKAGES></AR-PACKAGE></AR-PACKAGES>
</AUTOSAR>
"""


@pytest.fixture
def ar(tmp_path):
    path = tmp_path / "system.arxml"
    path.write_text(ARXML, encoding="utf-8")
    return str(path)


def test_parse_frames_signals_compu(ar):
    messages, notes = arxml.parse(ar)
    assert set(messages) == {(256, False), (512, False), (0x18FF0000, True)}
    assert any("MuxPdu" in n for n in notes)
    motor = messages[(256, False)]
    rpm = next(s for s in motor.signals if s.name == "Drehzahl")
    assert (rpm.start, rpm.length, rpm.little_endian, rpm.factor, rpm.unit) == (0, 16, True, 0.25, "1/min")
    power = next(s for s in motor.signals if s.name == "Leistung")
    assert power.is_float and power.start == 32
    batt = messages[(512, False)]
    volt = next(s for s in batt.signals if s.name == "Spannung")
    assert not volt.little_endian and volt.start == 7 and volt.unit == "V"
    current = next(s for s in batt.signals if s.name == "Strom")
    assert current.signed and current.factor == pytest.approx(0.1)
    speed = messages[(0x18FF0000, True)].signals[0]
    assert speed.start == 8 and speed.offset == -10 and speed.unit == "km/h"     # PDU ab Byte 1


def test_decode_matches_dbc_semantics(ar):
    messages, _ = arxml.parse(ar)
    data = np.zeros((1, 8), dtype=np.uint8)
    data[0, :2] = list(struct.pack("<H", 4000))
    data[0, 4:8] = list(struct.pack("<f", 12.5))
    out = dbc.decode(messages[(256, False)], data)
    assert out["Drehzahl"][1][0] == 1000 and out["Leistung"][1][0] == pytest.approx(12.5)
    data = np.zeros((1, 8), dtype=np.uint8)
    data[0, :2] = list(struct.pack(">H", 40012))
    data[0, 2:4] = list(struct.pack("<h", -125))
    out = dbc.decode(messages[(512, False)], data)
    assert out["Spannung"][1][0] == pytest.approx(400.12) and out["Strom"][1][0] == pytest.approx(-12.5)


def test_to_dbc_roundtrip(ar, tmp_path):
    messages, _ = arxml.parse(ar)
    target = tmp_path / "out.dbc"
    target.write_text(arxml.to_dbc(messages))
    again = dbc.parse(str(target))
    assert set(again) == set(messages)
    for key, message in messages.items():
        for a, b in zip(message.signals, again[key].signals):
            assert (a.name, a.start, a.length, a.little_endian, a.signed, a.unit, a.is_float) == \
                   (b.name, b.start, b.length, b.little_endian, b.signed, b.unit, b.is_float)
            assert a.factor == pytest.approx(b.factor) and a.offset == pytest.approx(b.offset)


def test_bad_arxml(tmp_path):
    bad = tmp_path / "x.arxml"
    bad.write_text("<AUTOSAR")
    with pytest.raises(LoadError, match="ARXML"):
        arxml.parse(str(bad))
    empty = tmp_path / "e.arxml"
    empty.write_text("<AUTOSAR/>")
    with pytest.raises(LoadError, match="Keine CAN-Botschaften"):
        arxml.parse(str(empty))


def test_blf_with_dbc_and_arxml_combined(ar, tmp_path):
    msgs = []
    for k in range(50):
        msgs.append((k * 0.01, 1, 0x100, False, struct.pack("<H", 4000 + k) + bytes(2) + struct.pack("<f", k)))
        msgs.append((k * 0.01, 1, 0x200, False, struct.pack(">H", 1000) + struct.pack("<h", -5) + bytes(4)))
        msgs.append((k * 0.01, 1, 0x7FF, False, bytes([k]) + bytes(7)))
    path = blf.write(str(tmp_path / "log.blf"), msgs)
    extra = tmp_path / "extra.dbc"
    extra.write_text('VERSION ""\nBO_ 2047 Zaehler: 8 A\n SG_ Z : 0|8@1+ (1,0) [0|255] "" Vector__XXX\n')
    unused = tmp_path / "fremd.dbc"
    unused.write_text('VERSION ""\nBO_ 1000 Fremd: 8 A\n SG_ F : 0|8@1+ (1,0) [0|255] "" Vector__XXX\n')
    ds = blf.load(path)
    cfg = DatabaseConfig()
    cfg.add([str(extra), ar, str(unused)])
    result = apply_databases(ds, cfg, set(), None, None)
    install_databases(ds, cfg, result)
    by_name = {c.name: c for c in ds.channels}
    assert by_name["Z"].y[3] == 3 and by_name["Drehzahl"].y[0] == 1000 and by_name["Leistung"].y[2] == 2
    assert by_name["Spannung"].y[0] == pytest.approx(10.0) and by_name["Strom"].y[0] == pytest.approx(-0.5)
    assert not any("Byte" in name for name in by_name)        # alle Botschaften dekodiert
    assert any("Nicht benötigt" in i and "fremd.dbc" in i for i in ds.info)
    assert any("MuxPdu" in w for w in ds.warnings)


def test_from_messages_roundtrip(tmp_path):
    src = tmp_path / "a.dbc"
    src.write_text('VERSION ""\nBO_ 512 Batt: 8 A\n SG_ U : 7|16@0+ (0.01,0) [0|655] "V" Vector__XXX\n'
                   ' SG_ I : 16|16@1- (0.1,-5) [0|1] "A" Vector__XXX\n'
                   'BO_ 2566844672 Ext: 64 A\n SG_ P : 0|32@1- (1,0) [0|1] "kW" Vector__XXX\n'
                   'SIG_VALTYPE_ 2566844672 P : 1;\n')
    original = dbc.parse(str(src))
    assert original[(0x18FEF100, True)].signals[0].is_float
    path = tmp_path / "a.arxml"
    path.write_text(arxml.from_messages(original), encoding="utf-8")
    again, notes = dbc.load(str(path))
    assert not notes and set(again) == set(original)
    for key in original:
        for a, b in zip(original[key].signals, again[key].signals):
            assert (a.name, a.start, a.length, a.little_endian, a.unit, a.is_float) == \
                   (b.name, b.start, b.length, b.little_endian, b.unit, b.is_float)
            assert a.is_float or a.signed == b.signed              # Vorzeichen zählt bei Gleitkomma nicht
            assert (a.factor, a.offset) == pytest.approx((b.factor, b.offset))
    assert again[(0x18FEF100, True)].length == 64
