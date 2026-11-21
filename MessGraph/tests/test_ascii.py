"""ASCII-Rohdaten: variabler Vorspann, Kopfzeile automatisch oder vom Nutzer, <{Continue}> ignorieren."""
from pathlib import Path

import numpy as np
import pytest

from messgraph import csv_reader, session
from messgraph.csv_reader import AsciiOptions, logical_lines, preview, read_ascii
from messgraph.data_model import LoadError
from messgraph.layout import PlotLayout
from messgraph.loaders import SUPPORTED, is_ascii, load_file

DEMO = Path(__file__).resolve().parent.parent / "demo_data"

NAMES = ["Time", "SN_DUT", "Test_Mode", "OBC_Mode", "Kl30_V", "Kl30_I"] + [f"DUT_TS_{i:02d}" for i in range(1, 21)]


def raw_file(tmp_path, cut=97, rows=12, name="lauf.asc", preamble=True, sep=",", newline="\r\n"):
    header = sep.join(NAMES) + sep
    lines = []
    if preamble:
        lines += ["date Tue Nov 10 03:56:00.857 pm 2026", "base hex  timestamps absolute", "no internal events logged",
                  "// version 14.4.0", "//   0.000000 previous log file: SaveCSV3.asc",
                  "// Measurement UUID: 25b8e878-c19d-4717-99aa-836f2641a383"]
    if cut:
        lines += [header[:cut], "<{Continue}>" + header[cut:]]
    else:
        lines.append(header)
    for k in range(rows):
        values = [f"2026-11-10_16-{k // 6:02d}-{(k % 6) * 10:02d}", "", "EU_AC_3ph", f"{k % 2:.6f}",
                  f"{13.5 - 0.01 * k:.6f}", "x" if k == 3 else f"{0.47 + 0.001 * k:.6f}"]
        values += [f"{60 + i + 0.1 * k:.6f}" if i < 18 else "x" for i in range(20)]
        lines.append(sep.join(values) + sep)
    path = tmp_path / name
    path.write_text(newline.join(lines) + newline, encoding="utf-8")
    return str(path)


def test_logical_lines_join_continuation_and_ignore_markers():
    lines, starts, removed = logical_lines(["a", "b,c,DUT_", "<{Continue}>12,DUT_13", "1,2<{Info}>,3", "4"])
    assert lines == ["a", "b,c,DUT_12,DUT_13", "1,2,3", "4"]
    assert starts == [0, 1, 3, 4] and removed == 2


def test_auto_detects_header_in_line_7_split_by_continue(tmp_path):
    ds = read_ascii(raw_file(tmp_path))                  # Schnitt mitten in "DUT_TS_.."
    names = [c.name for c in ds.channels]
    assert "Kopfzeile: Zeilen 7-8 (automatisch erkannt)" in ds.info
    assert "Daten ab Zeile 9" in ds.info and any("<{Continue}>" in i for i in ds.info)
    assert names[:3] == ["OBC_Mode", "Kl30_V", "Kl30_I"] and "DUT_TS_18" in names
    assert not any("Continue" in n or n.startswith("Spalte_") for n in names)
    by = {c.name: c for c in ds.channels}
    assert by["DUT_TS_05"].y[2] == pytest.approx(64.2)               # Kopf logisch richtig auf die Daten bezogen
    assert np.isnan(by["Kl30_I"].y[3])                                # "x" = fehlender Wert
    assert by["Kl30_V"].x[1] == 10 and by["Kl30_V"].x_epoch is not None   # Zeitstempel 2026-11-10_16-00-10
    assert {"Test_Mode", "DUT_TS_19"} <= set(ds.extra["no_values"])   # Text und nur "x": nicht angeboten
    assert ds.extra["ascii"]["header_line"] == 7 and ds.extra["ascii"]["data_line"] == 9


def test_user_defined_header_line(tmp_path):
    path = raw_file(tmp_path)
    ds = read_ascii(path, {"header_line": 7})
    assert "Kopfzeile: Zeilen 7-8 (vom Nutzer festgelegt)" in ds.info
    assert [c.name for c in ds.channels] == [c.name for c in read_ascii(path).channels]
    assert ds.extra["ascii"]["options"]["header_line"] == 7
    ds = read_ascii(path, {"header_line": 8})                         # Zeile 8 gehört logisch zu Zeile 7
    assert "DUT_TS_05" in [c.name for c in ds.channels]


def test_header_without_marker_and_other_separators(tmp_path):
    ds = read_ascii(raw_file(tmp_path, cut=0, sep=";", name="b.txt", newline="\n"))
    assert "Kopfzeile: Zeile 7 (automatisch erkannt)" in ds.info and "DUT_TS_10" in [c.name for c in ds.channels]
    ds = read_ascii(raw_file(tmp_path, cut=0, sep="\t", preamble=False, name="c.dat"), {"sep": "\t"})
    assert "Kl30_V" in [c.name for c in ds.channels]


def test_wrong_header_line_and_none(tmp_path):
    path = raw_file(tmp_path)
    ds = read_ascii(path, {"header_line": -1})                        # ohne Kopfzeile: Namen erzeugt
    assert all(c.name.startswith("Spalte_") for c in ds.channels)
    with pytest.raises(LoadError, match="Zeile 500"):
        read_ascii(path, {"header_line": 500})


def test_preview_shows_detection(tmp_path):
    path = raw_file(tmp_path)
    result = preview(path)
    assert result.header_span == (7, 8) and result.data_line == 9 and result.removed == 1
    assert result.names[:2] == ["Time", "SN_DUT"] and len(result.names) == len(NAMES)
    assert result.lines[7].startswith("<{Continue}>") and not result.error
    manual = preview(path, AsciiOptions(header_line=2))
    assert manual.header_span == (2, 2) and manual.data_line == 3


def test_options_roundtrip_and_automatic():
    assert AsciiOptions().automatic
    opts = AsciiOptions(7, -1, ";", ",")
    assert AsciiOptions.from_dict(opts.to_dict()) == opts and not opts.automatic
    assert AsciiOptions.from_dict({"sep": "x", "decimal": "#"}) == AsciiOptions()


def test_can_trace_asc_is_rejected_with_hint(tmp_path):
    path = tmp_path / "trace.asc"
    path.write_text("date Tue Nov 10 2026\nbase hex  timestamps absolute\nBegin Triggerblock\n"
                    "   0.010000 1  123             Rx   d 8 00 11 22 33 44 55 66 77\n"
                    "   0.020000 1  124             Rx   d 8 00 11 22 33 44 55 66 77\n")
    with pytest.raises(LoadError, match="BLF"):
        load_file(str(path))


def test_extensions_and_demo_file():
    assert {".asc", ".txt", ".dat", ".csv"} <= set(SUPPORTED) and is_ascii("x.ASC") and not is_ascii("x.mf4")
    ds = load_file(str(DEMO / "demo_pruefstand.asc"))
    assert "Kopfzeile: Zeilen 7-8 (automatisch erkannt)" in ds.info and len(ds.channels) > 40


def test_session_keeps_user_options(tmp_path):
    path = raw_file(tmp_path)
    ds = load_file(path, {"header_line": 7, "sep": ","})
    data = session.build_session([ds], PlotLayout(), {})
    assert data["files"][0]["ascii"] == {"header_line": 7, "units_line": 0, "sep": ",", "decimal": ""}
    auto = session.build_session([load_file(path)], PlotLayout(), {})
    assert "ascii" not in auto["files"][0]
    datasets, _by, problems = session.open_session(data, None)
    assert not problems and "Kopfzeile: Zeilen 7-8 (vom Nutzer festgelegt)" in datasets[0].info
