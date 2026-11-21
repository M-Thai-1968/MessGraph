#!/usr/bin/env python3
"""Erzeugt Beispieldateien in demo_data/. mf4 und parquet nur, wenn die Pakete da sind."""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "demo_data"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(1)
t = np.arange(0, 60, 0.02)
speed = 50 + 30 * np.sin(t / 8) + rng.normal(0, 0.5, t.size)
temp = 20 + 0.25 * t + rng.normal(0, 0.05, t.size)
volt = 13.8 - 0.01 * t + 0.1 * np.sin(t * 2)

# Englisches Format: Komma, Punkt, Einheiten im Namen
pd.DataFrame({"time [s]": t, "speed [km/h]": speed, "temperature [°C]": temp, "voltage [V]": volt}) \
    .round(4).to_csv(OUT / "demo_einfach.csv", index=False, encoding="utf-8")

# Deutsches Format: Vorspann, Semikolon, Dezimalkomma, Einheitenzeile, Windows-1252
with open(OUT / "demo_deutsch_vorspann.csv", "w", encoding="cp1252", newline="\n") as fh:
    fh.write("Prüfstand: P3\nDatum: 05.11.2026\nBearbeiter;Muster;\n\n")
    fh.write("Zeit;Drehzahl;Öltemperatur;Status\ns;rpm;°C;\n")
    for ti, sp, te in zip(t, speed, temp):
        status = "OK" if te < 30 else "WARM"
        fh.write(f"{ti:.2f};{sp * 40:.1f};{te:.3f};{status}\n".replace(".", ","))

# Zeitstempel als Text
stamps = pd.Timestamp("2026-11-05 10:00:00") + pd.to_timedelta(t, unit="s")
pd.DataFrame({"Timestamp": stamps.strftime("%Y-%m-%d %H:%M:%S.%f"), "Current [A]": (volt - 13) * 12}) \
    .round(4).to_csv(OUT / "demo_zeitstempel.csv", index=False)

# Drei Prüfläufe gleicher Struktur für den Dateivergleich; Lauf 3 ohne Temperatur, dafür mit Druck
for run, (gain, offset) in enumerate([(1.0, 0.0), (1.04, 0.3), (0.97, -0.2)], 1):
    r = np.random.default_rng(10 + run)
    cols = {"time [s]": t, "Drehzahl [rpm]": gain * (1500 + 600 * np.sin(t / 6)) + r.normal(0, 8, t.size),
            "Strom [A]": gain * (32 + 4 * np.sin(t / 4)) + offset + r.normal(0, 0.3, t.size),
            "Spannung [V]": 400 - 0.05 * t * gain + r.normal(0, 0.4, t.size)}
    if run < 3:
        cols["Temperatur [°C]"] = 25 + 0.2 * t * gain + offset
    else:
        cols["Druck [bar]"] = 2.0 + 0.1 * np.sin(t / 5)
    pd.DataFrame(cols).round(3).to_csv(OUT / f"demo_lauf_{run}.csv", index=False, encoding="utf-8")

try:
    pd.DataFrame({"timestamp": stamps, "pressure [bar]": 2 + np.sin(t / 3), "flow": temp * 0.4}) \
        .to_parquet(OUT / "demo.parquet")
    print("demo.parquet erzeugt")
except ImportError:
    print("pyarrow fehlt: demo.parquet übersprungen")

try:
    from asammdf import MDF, Signal
except ImportError:
    print("asammdf fehlt: demo.mf4 übersprungen")
else:
    with MDF(version="4.10") as mdf:
        mdf.append([Signal(speed, t, name="Speed", unit="km/h"), Signal(temp, t, name="Temp", unit="°C")])
        slow = t[::10]
        mdf.append([Signal(volt[::10], slow, name="Voltage", unit="V")])
        mdf.save(OUT / "demo.mf4", overwrite=True)
    print("demo.mf4 erzeugt")
print("Fertig:", OUT)

# CAN-Aufzeichnung als BLF mit passender DBC (Beispiel für "Datenbasen..." bei BLF)
import struct as _struct
import sys as _sys
_sys.path.insert(0, str(OUT.parent))
from messgraph import blf as _blf

DBC_TEXT = """VERSION ""

NS_ :

BS_:

BU_: Motor Batterie Fahrzeug

BO_ 256 Motor: 8 Motor
 SG_ Drehzahl : 0|16@1+ (0.25,0) [0|16000] "rpm" Vector__XXX
 SG_ Kuehlmittel : 16|8@1+ (1,-40) [-40|215] "degC" Vector__XXX

BO_ 512 Batterie: 8 Batterie
 SG_ Spannung : 7|16@0+ (0.01,0) [0|655.35] "V" Vector__XXX
 SG_ Strom : 16|16@1- (0.1,0) [-3276.8|3276.7] "A" Vector__XXX

BO_ 2566844672 Fahrzeug: 8 Fahrzeug
 SG_ Geschwindigkeit : 8|16@1+ (0.00390625,0) [0|250] "km/h" Vector__XXX

BO_ 768 Zellen: 16 Batterie
 SG_ Zelle_min : 0|16@1+ (0.001,0) [0|5] "V" Vector__XXX
 SG_ Zelle_max : 16|16@1+ (0.001,0) [0|5] "V" Vector__XXX

CM_ SG_ 256 Drehzahl "Motordrehzahl";
"""
(OUT / "demo_can.dbc").write_text(DBC_TEXT, encoding="utf-8")
_msgs = []
_r = np.random.default_rng(7)
for _k in range(3000):
    _ts = _k * 0.02
    _rpm = 1500 + 600 * np.sin(_ts / 6) + _r.normal(0, 5)
    _cool = 70 + 15 * (1 - np.exp(-_ts / 30))
    _msgs.append((_ts, 1, 0x100, False, _struct.pack("<HB5x", int(_rpm / 0.25), int(_cool + 40))))
    if _k % 2 == 0:
        _volt = 400 - 0.05 * _ts + _r.normal(0, 0.3)
        _amp = 32 + 4 * np.sin(_ts / 4) + _r.normal(0, 0.2)
        _msgs.append((_ts + 0.001, 1, 0x200, False, _struct.pack(">H", int(_volt / 0.01)) + _struct.pack("<h", int(round(_amp / 0.1))) + bytes(4)))
    if _k % 5 == 0:
        _speed = 60 + 30 * np.sin(_ts / 10)
        _msgs.append((_ts + 0.002, 1, 0x18FEF100, True, bytes([0]) + _struct.pack("<H", int(_speed / 0.00390625)) + bytes(5)))
        _msgs.append((_ts + 0.003, 2, 0x300, False, _struct.pack("<HH", int((3.62 - 0.0005 * _ts) / 0.001), int((3.71 - 0.0004 * _ts) / 0.001)) + bytes(12)))
    if _k % 50 == 0:
        _msgs.append((_ts + 0.004, 1, 0x7FF, False, bytes([_k // 50 % 256, 0xAA])))
_blf.write(str(OUT / "demo_can.blf"), _msgs)

# Kombination mehrerer Datenbasen: Motor/Fahrzeug als DBC, Batterie/Zellen als AUTOSAR-ARXML
from messgraph import arxml as _arxml, dbc as _dbc
_all = _dbc.parse(str(OUT / "demo_can.dbc"))
_battery = {k: m for k, m in _all.items() if m.name in ("Batterie", "Zellen")}
(OUT / "demo_can_batterie.arxml").write_text(_arxml.from_messages(_battery, "Batterie"), encoding="utf-8")
_motor = DBC_TEXT.split("BO_ 512")[0] + "BO_ 2566844672" + DBC_TEXT.split("BO_ 2566844672")[1].split("BO_ 768")[0]
(OUT / "demo_can_motor.dbc").write_text(_motor, encoding="utf-8")
print("demo_can_motor.dbc + demo_can_batterie.arxml erzeugt (zusammen für demo_can.blf)")

# ASCII-Rohdaten wie aus einem Prüfstandsschreiber: Vorspann, Kopfzeile nach 1000 Zeichen mit <{Continue}>
# umgebrochen, Zeitstempel 2026-11-10_16-00-51, "x" für fehlende Werte, Textspalte, Komma am Zeilenende
import datetime as _dt
_names = ["Time", "SN_DUT", "Test_Mode", "OBC_Mode", "Grid"] + \
    [f"{p}_{q}" for p in ("AC_V", "AC_I", "AC_P") for q in ("L1", "L2", "L3")] + \
    ["HVDC_V", "HVDC_I", "LVDC_V", "LVDC_I", "Chiller_T", "Clnt_IN_T", "Clnt_OUT_T"] + \
    [f"DUT_TS_{i:02d}" for i in range(1, 41)]
_header = ",".join(_names) + ","
_rows = []
_t0 = _dt.datetime(2026, 11, 10, 16, 0, 51)
for _k in range(120):
    _on = _k >= 12
    _vals = [(_t0 + _dt.timedelta(seconds=10 * _k)).strftime("%Y-%m-%d_%H-%M-%S"), "", "EU_AC_3ph_11kW_800V",
             f"{1.0 if _on else 0.0:.6f}", "5.000000"]
    for _q in range(3):
        _vals.append(f"{229.4 + 0.3 * np.sin(_k / 9 + _q):.6f}")
    for _q in range(3):
        _vals.append(f"{(15.7 + 0.2 * _q if _on else 0.0) + 0.05 * np.sin(_k / 5 + _q):.6f}")
    _vals += ["x", "x", "x"]
    _vals += [f"{807.9 + 0.2 * np.sin(_k / 11):.6f}", f"{12.58 if _on else 0.0:.6f}", f"{13.4:.6f}",
              f"{15.0 if _on else 0.0:.6f}", f"{70.3 + 0.1 * np.sin(_k / 13):.6f}", "68.000000", f"{69 + 0.02 * _k:.6f}"]
    _vals += [f"{60 + 0.08 * _k + _i * 0.5 + 0.3 * np.sin(_k / 7 + _i):.6f}" if _i < 36 else "x" for _i in range(40)]
    _rows.append(",".join(_vals) + ",")
_cut = 307                     # mitten im Signalnamen umbrechen, wie der Schreiber nach 1000 Zeichen
_text = ["date Tue Nov 10 03:56:00.857 pm 2026", "base hex  timestamps absolute", "no internal events logged",
         "// version 14.4.0", "//   0.000000 previous log file: demo_vorher.asc",
         "// Measurement UUID: 00000000-0000-4000-8000-000000000000",
         _header[:_cut], "<{Continue}>" + _header[_cut:]] + _rows
(OUT / "demo_pruefstand.asc").write_text("\r\n".join(_text) + "\r\n", encoding="utf-8")
print("demo_pruefstand.asc erzeugt (ASCII mit Vorspann und <{Continue}>)")

# ---------------------------------------------------------------- Grenzwert-Konfiguration (YAML) zum Prüfstand
_yaml = """# Beispiel: Grenzen und Zielabstand je Mode für demo_pruefstand.asc (Aufbau wie eine Prüfstands-config.yaml)
limits:
  enabled: true
  upper: null
  lower: null
  modes:
    Interface:
      steps: null
    EU_AC_3ph_11kW_800V:
      steps: 600          # Zahl ohne Einheit: Schritte (Messpunkte) bis zur Grenzverletzung
      signals:
        AC_V_L1: {enabled: true, lower: 207.0, upper: 253.0}
        AC_V_L2: {enabled: true, lower: 207.0, upper: 253.0}
        AC_V_L3: {enabled: true, lower: 207.0, upper: 253.0}
        HVDC_V: {enabled: true, lower: 780.0, upper: 830.0}
        LVDC_V: {enabled: true, lower: 13.0, upper: 14.5}
        DUT_TS_01: {enabled: true, lower: 0.0, upper: 80.0}
        DUT_TS_02: {enabled: true, lower: 0.0, upper: 80.0}
        Clnt_OUT_T: {enabled: true, lower: 0.0, upper: 75.0}
        Chiller_T: {enabled: false, lower: 0.0, upper: 0.0}
        Signal_nicht_in_Datei: {enabled: true, lower: 0.0, upper: 1.0}
    EU_AC_3ph_22kW_800V:
      steps: 2h 30m       # mit Einheiten: Zeit bis zur Grenzverletzung
      signals:
        AC_V_L1: {enabled: true, lower: 220.0, upper: 240.0}
        HVDC_V: {enabled: true, lower: 800.0, upper: 815.0}
        DUT_TS_01: {enabled: true, lower: 0.0, upper: 90.0}
"""
(OUT / "demo_grenzen.yaml").write_text(_yaml, encoding="utf-8")
print("demo_grenzen.yaml erzeugt (Grenzen je Mode)")

# Limiter-Beispiel: Rechtecksignal (Takt 20 s), nur der obere Anteil soll für alle Signale gelten
tr = np.arange(0, 120, 0.1)
rect = np.where((tr % 20) >= 10, 5.0, 0.0) + rng.normal(0, 0.02, tr.size)
pd.DataFrame({"Zeit [s]": tr, "Rechteck [V]": rect.round(3),
              "Strom [A]": (np.where(rect > 2.5, 16.0, 0.4) + rng.normal(0, 0.1, tr.size)).round(3),
              "Temperatur [°C]": (25 + 0.08 * tr + np.where(rect > 2.5, 3.0, 0.0) + rng.normal(0, 0.05, tr.size)).round(3)}) \
    .to_csv(OUT / "demo_rechteck.csv", index=False, encoding="utf-8")
(OUT / "demo_limiter.yaml").write_text(
    "# Limiter-Konfiguration (MessGraph): nur der obere Anteil des Rechtecksignals\n"
    "limiter:\n  format: messgraph_limiter\n  version: 1\n  active: true\n  rules:\n"
    "  - file: demo_rechteck.csv\n    signal: Rechteck\n    min: 4.5\n    max: null\n    enabled: true\n",
    encoding="utf-8")
print("demo_rechteck.csv und demo_limiter.yaml erzeugt (Limiter)")
