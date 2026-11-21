import numpy as np
import pytest

from messgraph import fourier, formula, plotexport
from messgraph.data_model import Channel, Dataset


def signal(fs=10000.0, seconds=2.0, offset=3.0):
    t = np.arange(0, seconds, 1 / fs)
    y = 325.27 * np.sin(2 * np.pi * 50 * t) + 20 * np.sin(2 * np.pi * 150 * t) + 5 * np.sin(2 * np.pi * 250 * t) + offset
    return t, y


def test_parse_and_text_roundtrip():
    spec = fourier.parse("FFT({U L1}; h=1..15; f0=auto; y=db; win=hann)")
    assert (spec.signal, spec.mode, spec.hmin, spec.hmax, spec.f0, spec.window, spec.scale) == \
        ("U L1", "harm", 1, 15, None, "hann", "db")
    assert fourier.parse(spec.text()) == spec
    assert fourier.parse("FFT({U}; h=0..15)").hmin == 1               # alte Zählung ab 0 -> ab 1
    spec = fourier.parse("fft({U}; f=10..500,5; f0=50; win=rechteck; y=%)")
    assert (spec.mode, spec.fmin, spec.fmax, spec.f0, spec.window, spec.scale) == ("range", 10.0, 500.5, 50.0, "rect", "pct")
    assert fourier.parse(spec.text()) == spec
    assert fourier.parse("FFT({U}; f=0..max)").fmax is None
    for bad in ("FFT({U}; h=0..16)", "FFT({U}; h=5..2)", "FFT({U}; f=100..50)", "FFT({U}; y=lin)",
                "FFT({U}; win=kaiser)", "FFT({U}; x=1)", "FFT(U)"):
        with pytest.raises(fourier.FourierError):
            fourier.parse(bad)


def test_harmonics_bars_percent_and_attenuation():
    t, y = signal()                                             # 50 Hz 325.27, 150 Hz 20, 250 Hz 5
    r = fourier.compute(t, y, "s", fourier.parse("FFT({U}; h=1..5; y=pct)"))
    assert r["info"]["f0"] == pytest.approx(50.0, abs=0.01) and r["y_unit"] == "%" and r["bar_width"] == 0.6
    assert list(r["x"]) == [1, 2, 3, 4, 5]                     # 1 = Grundschwingung, 3 = 150 Hz
    total = 325.27 + 20 + 5
    assert r["y"] == pytest.approx([32527 / total, 0, 2000 / total, 0, 500 / total], abs=0.05)
    assert r["y"].sum() == pytest.approx(100.0, abs=0.1) and r["y"][0] < 100
    pure = fourier.compute(t, 2 * np.sin(2 * np.pi * 50 * t), "s", fourier.parse("FFT({U}; h=1..15)"))
    assert pure["y"][0] == pytest.approx(100.0, abs=0.01) and pure["y"][1:] == pytest.approx(np.zeros(14), abs=1e-3)
    db = fourier.compute(t, y, "s", fourier.parse("FFT({U}; h=1..5; y=db)"))
    assert db["y_unit"] == "dB" and db["y"][0] == pytest.approx(0.0)
    assert db["y"][2] == pytest.approx(20 * np.log10(325.27 / 20), abs=0.05)
    assert db["y"][4] == pytest.approx(20 * np.log10(325.27 / 5), abs=0.05)
    assert db["y"][1] >= 60                                      # keine 2. Harmonische: starke Dämpfung (max 100 dB)
    assert r["info"]["table"]["columns"][6:9] == ["H1 [%]", "H2 [%]", "H3 [%]"]
    assert r["info"]["table"]["all"][5] == pytest.approx(325.27, abs=0.05)      # A1 = Amplitude Grundschwingung
    # Zeit in ms, ungleichmäßige Abtastung mit Lücken
    keep = np.ones(t.size, bool)
    keep[1000:1003] = False
    r2 = fourier.compute(t[keep] * 1000, y[keep], "ms", fourier.parse("FFT({U}; h=1..3)"))
    assert r2["y"][2] == pytest.approx(2000 / (325.27 + 20), abs=0.1)
    assert r2["info"]["harm"]["bounds"][0][1] == pytest.approx(20.0, abs=0.2)   # Periodengrenzen in ms


def test_frequency_range_gives_bars_at_harmonic_frequencies():
    t, y = signal()
    r = fourier.compute(t, y, "s", fourier.parse("FFT({U}; f=100..400; y=db)"))
    assert r["x_unit"] == "Hz" and list(r["x"]) == pytest.approx([100, 150, 200, 250, 300, 350, 400], abs=0.01)
    assert r["bar_width"] == pytest.approx(30.0, abs=0.01)
    assert r["y"][1] == pytest.approx(20 * np.log10(325.27 / 20), abs=0.05)   # 150 Hz = H3 gegenüber H1
    full = fourier.compute(t, y, "s", fourier.parse("FFT({U}; f=0..max)"))
    assert full["x"].size == fourier.MAX_RANGE_HARMONIC                    # höchstens 50 Harmonische
    with pytest.raises(fourier.FourierError):
        fourier.compute(t, y, "s", fourier.parse("FFT({U}; f=10..20)"))    # keine Harmonische im Bereich
    with pytest.raises(fourier.FourierError):
        fourier.compute(t[:3], y[:3], "s", fourier.parse("FFT({U}; f=0..max)"))


def test_marker_selection_picks_periods_by_midpoint():
    fs = 10000.0
    t = np.arange(0, 0.1, 1 / fs)                               # 5 Perioden 50 Hz, ab Periode 3 mit 3. Harmonischer
    y = np.sin(2 * np.pi * 50 * t) + np.where(t >= 0.04, 0.5, 0.0) * np.sin(2 * np.pi * 150 * t)
    info = fourier.compute(t, y, "s", fourier.parse("FFT({U}; h=1..3)"))["info"]
    energy, chosen = fourier.select(info, 0.0002, 0.0298)       # 0.01 .. 1.49 Schwingungen -> 1. Schwingung
    first = fourier.display(energy, "pct")
    assert chosen == [1] and first[0] == pytest.approx(100.0, abs=1.5)
    energy, chosen = fourier.select(info, 0.0402, 0.0698)       # 2.01 .. 3.49 -> 3. Schwingung (mit Oberwelle)
    third = fourier.display(energy, "pct")
    assert chosen == [3] and third[0] == pytest.approx(100 / 1.5, abs=0.5) and third[2] == pytest.approx(50 / 1.5, abs=0.5)
    assert fourier.display(energy, "db")[2] == pytest.approx(20 * np.log10(2), abs=0.05)
    energy, chosen = fourier.select(info, 0.0, 0.049)
    assert chosen == [1, 2]
    energy, chosen = fourier.select(info, 0.0001, 0.0005)
    assert chosen == [] and not energy.any() and not fourier.display(energy, "pct").any()
    energy, chosen = fourier.select(info)
    assert len(chosen) == info["periods"]


def test_formula_integration_references_and_rename(tmp_path):
    t, y = signal()
    ds = Dataset(path=str(tmp_path / "a.csv"), channels=[Channel(name="U", unit="V", x=t, y=y)])
    out = formula.compute(ds, "Spektrum U", "", "FFT({U}; h=1..15; f0=auto; y=pct)")
    assert out.unit == "%" and out.plot_style == "bar" and out.bar_width == 0.6 and out.fourier["signal"] == "U"
    assert out.x_unit == "" and out.x_epoch is None and out.fourier["f0"] == pytest.approx(50, abs=0.01)
    assert formula.guess_unit(formula.parse("FFT({U}; h=1..3; y=db)"), {"U": "V"}) == "dB"
    formula.add_or_replace(ds, out)
    assert formula.dependents(ds, "U") == [out]
    formula.rename_references(ds, "U", "U_L1")
    assert out.formula.startswith("FFT({U_L1};")
    with pytest.raises(formula.FormulaError):
        formula.parse("FFT({U}; h=0..20)")


def test_export_log_axes_decades(tmp_path):
    f = np.array([1.0, 10.0, 100.0, 1000.0])
    a = np.array([100.0, 10.0, 1.0, 0.0])                       # 0 auf log. Achse nicht darstellbar
    spec = plotexport.PlotSpec(title="Spektrum", xlim=(1, 1000), ylim=(0, 100),
                               series=[plotexport.SeriesSpec("A", f, a, (0, 0, 255))], log_x=True, log_y=True)
    svg = plotexport.write_svg(str(tmp_path / "s.svg"), [spec], (1, 1), "A4", "landscape", "x")[0]
    text = open(svg, encoding="utf-8").read()
    for label in (">1<", ">10<", ">100<", ">1000<"):
        assert label in text
    assert plotexport.log_ticks(0.0, 0.5)                       # weniger als eine Dekade: Zwischenwerte


DEMO = __import__("pathlib").Path(__file__).resolve().parent.parent / "demo_data"


def load_demo(name):
    import pandas as pd
    return pd.read_csv(DEMO / name)


@pytest.mark.parametrize("name, column, text, periodic", [
    ("demo_fourier_netz_oberschwingungen.csv", "I_L1 [A]", "h=1..15", True),
    ("demo_fourier_rechteck_saegezahn.csv", "Rechteck [V]", "h=1..7", True),
    ("demo_fourier_frequenzrampe.csv", "Phasenstrom [A]", "h=1..6", True),
    ("demo_fourier_amplitude_wechselnd.csv", "Laststrom [A]", "h=1..2", True),
    ("demo_fourier_nicht_periodisch.csv", "Rauschen [mV]", "f=0..max", False),
    ("demo_fourier_ungleichmaessig.csv", "Vibration [g]", "h=1..3", True),
])
def test_demo_data_periodicity(name, column, text, periodic):
    data = load_demo(name)
    r = fourier.compute(data.iloc[:, 0].values, data[column].values, "s", fourier.parse(f"FFT({{X}}; {text})"))
    info = r["info"]
    assert info["periodic"] is periodic, info["reason"]
    table = info["table"]
    if periodic:
        assert info["periods"] >= 18 and len(table["rows"]) == info["periods"] and table["stats"][0][0] == "Mittel"
        assert len(table["rows"][0]) == len(table["columns"]) == len(table["all"])
    else:
        assert info["periods"] == 0 and table["rows"] == [] and info["reason"]


def test_whole_periods_exact_and_per_period_values():
    data = load_demo("demo_fourier_rechteck_saegezahn.csv")
    r = fourier.compute(data.iloc[:, 0].values, data["Rechteck [V]"].values, "s",
                        fourier.parse("FFT({X}; h=1..5)"))
    assert r["info"]["window"] == "rect"                           # auto: ganze Perioden -> Rechteck, kein Leckeffekt
    amps = np.array([1, 0, 1 / 3, 0, 1 / 5]) * 4 * 5 / np.pi
    energy = (np.array([1 / n if n % 2 else 0 for n in range(1, 16)]) * 4 * 5 / np.pi) ** 2
    assert r["y"] == pytest.approx(amps / np.sqrt(energy).sum() * 100, abs=0.3)   # Anteile H1..H5 in %
    assert r["info"]["table"]["all"][5] == pytest.approx(4 * 5 / np.pi, abs=0.03)
    assert r["info"]["table"]["all"][-1] == pytest.approx(45.0, abs=1.0)   # THD Rechteck aus H2..H15
    ramp = load_demo("demo_fourier_frequenzrampe.csv")
    r = fourier.compute(ramp.iloc[:, 0].values, ramp["Phasenstrom [A]"].values, "s",
                        fourier.parse("FFT({X}; h=1..4)"))
    rows = r["info"]["table"]["rows"]
    assert rows[0][3] == pytest.approx(40, abs=2) and rows[-1][3] == pytest.approx(60, abs=2)   # f je Periode
    assert r["info"]["table"]["stats"][0][5] == pytest.approx(80, abs=2)                         # A1 Mittel


def test_demo_definition_loads_all_signals():
    import json
    from messgraph import loaders
    data = json.loads((DEMO / "demo_fourier.def").read_text(encoding="utf-8"))
    for entry in data["files"]:
        ds = loaders.load_file(str(DEMO / entry["path"]))
        for calc in entry["computed"]:
            out = formula.compute(ds, calc["name"], calc["unit"], calc["formula"])
            assert out.fourier["periodic"], calc["name"]
            formula.add_or_replace(ds, out)


def test_export_harmonics_as_bars(tmp_path):
    orders = np.arange(6, dtype=float)
    amps = np.array([10.0, 0.1, 3.0, 0.1, 1.0, 0.1])
    spec = plotexport.PlotSpec(title="H", xlim=(-0.5, 5.5), ylim=(0, 11),
                               series=[plotexport.SeriesSpec("H", orders, amps, (200, 0, 0), bars=True)])
    svg = open(plotexport.write_svg(str(tmp_path / "b.svg"), [spec], (1, 1), "A4", "landscape", "x")[0],
               encoding="utf-8").read()
    assert svg.count('fill="#c80000"') >= 6 + 1                        # 6 Balken (+ Legendenfeld)
    spec.log_y = True
    open(plotexport.write_svg(str(tmp_path / "c.svg"), [spec], (1, 1), "A4", "landscape", "x")[0]).read()


def test_choice_continuous_spectrum_or_bars_and_amplitude():
    t, y = signal()                                             # 50 Hz 325.27, 150 Hz 20, 250 Hz 5, DC 3
    spec = fourier.parse("FFT({U}; f=0..300; f0=auto; y=amp; plot=line)")
    assert spec.view == "line" and spec.scale == "amp" and fourier.parse(spec.text()) == spec
    assert fourier.parse("FFT({U}; h=1..5; plot=line)").view == "bar"       # Harmonische nach Nummer: Balken
    with pytest.raises(fourier.FourierError):
        fourier.parse("FFT({U}; f=0..300; plot=area)")
    line = fourier.compute(t, y, "s", spec)
    assert line["plot_style"] == "line" and line["y_unit"] is None and line["x"].size > 100   # alle Frequenzlinien
    assert line["y"][0] == pytest.approx(3.0, abs=0.05)                     # Gleichanteil
    assert line["y"][np.argmin(abs(line["x"] - 150))] == pytest.approx(20.0, abs=0.05)
    db = fourier.compute(t, y, "s", fourier.parse("FFT({U}; f=0..300; y=db; plot=line)"))
    assert db["y"][np.argmin(abs(db["x"] - 50))] == pytest.approx(0.0, abs=0.01)
    assert db["y"][np.argmin(abs(db["x"] - 150))] == pytest.approx(20 * np.log10(325.27 / 20), abs=0.05)
    pct = fourier.compute(t, y, "s", fourier.parse("FFT({U}; f=0..300; y=pct; plot=line)"))
    assert pct["y"][np.argmin(abs(pct["x"] - 150))] == pytest.approx(20 / 325.27 * 100, abs=0.05)
    bars = fourier.compute(t, y, "s", fourier.parse("FFT({U}; f=0..300; y=amp)"))
    assert bars["plot_style"] == "bar" and bars["y"][:3] == pytest.approx([325.27, 0, 20], abs=0.05)
    # Spektrum einer einzelnen Schwingung (Marker): Auflösung = f0
    fx, fy = fourier.line_spectrum(line["info"], [3])
    assert fx[1] == pytest.approx(50, abs=0.1) and fy[1] == pytest.approx(325.27, abs=0.5)
    assert fy[3] == pytest.approx(20, abs=0.3)


def test_log_gridlines_export_and_gui_helper(tmp_path):
    assert plotexport.log_minor(0.0, 1.0) == pytest.approx([np.log10(m) for m in range(2, 10)])
    spec = plotexport.PlotSpec(title="L", xlim=(1, 1000), ylim=(0.1, 100),
                               series=[plotexport.SeriesSpec("A", np.array([1.0, 10, 100, 1000]),
                                                             np.array([100.0, 10, 1, 0.1]), (0, 0, 255))],
                               log_x=True, log_y=True)
    svg = open(plotexport.write_svg(str(tmp_path / "g.svg"), [spec], (1, 1), "A4", "landscape", "x")[0],
               encoding="utf-8").read()
    assert svg.count("#eceef1") >= 2 * 8 * 3 - 2                      # Hilfslinien 2..9 je Dekade, X und Y
    from messgraph.gui import App
    lines = App._log_lines([0.5, 3.0, 80.0])
    assert lines[0] == pytest.approx(0.1) and lines[-1] == pytest.approx(100.0) and 0.2 in [round(v, 6) for v in lines]
    assert App._log_lines([0.0, -1.0]) == []


def test_offset_oscillation_without_zero_crossing():
    # Drehzahl: 1500 +- 600 rpm, keine Nulldurchgänge, nur ~1,6 Schwingungen in der Messung
    t = np.arange(0, 60, 0.02)
    y = 1500 + 600 * np.sin(t / 6) + 30 * np.sin(3 * t / 6)
    assert y.min() > 0
    r = fourier.compute(t, y, "s", fourier.parse("FFT({n}; h=1..5; y=amp)"))
    info = r["info"]
    assert info["f0"] == pytest.approx(1 / (12 * np.pi), rel=1e-3)
    assert info["periodic"] and info["periods"] == 1
    assert r["y"][0] == pytest.approx(600, rel=0.01) and r["y"][2] == pytest.approx(30, rel=0.05)
    assert r["y"][1] == pytest.approx(0, abs=2)
    # mit Trend: Schwingung bleibt unverfälscht
    r2 = fourier.compute(t, y + 5 * t, "s", fourier.parse("FFT({n}; h=1..5; y=amp)"))
    assert r2["info"]["f0"] == pytest.approx(1 / (12 * np.pi), rel=2e-3) and r2["y"][0] == pytest.approx(600, rel=0.02)
    # mehrere Schwingungen mit Offset: periodisch, Perioden um den Mittelwert
    t3 = np.arange(0, 10, 0.001)
    r3 = fourier.compute(t3, 80 + 5 * np.sin(2 * np.pi * 1.3 * t3), "s", fourier.parse("FFT({p}; h=1..3)"))
    assert r3["info"]["f0"] == pytest.approx(1.3, rel=1e-3) and r3["info"]["periods"] == 13
    assert r3["y"][0] == pytest.approx(100, abs=0.1)
    # weniger als eine Schwingung -> Meldung
    with pytest.raises(fourier.FourierError):
        fourier.compute(t, 1500 + 600 * np.sin(t / 30), "s", fourier.parse("FFT({n}; h=1..5)"))


@pytest.mark.parametrize("name", ["demo_lauf_1.csv", "demo_lauf_2.csv", "demo_lauf_3.csv"])
def test_demo_drehzahl_fourier(name):
    from pathlib import Path
    from messgraph import loaders
    ds = loaders.load_file(str(Path(__file__).resolve().parent.parent / "demo_data" / name))
    ch = next(c for c in ds.channels if c.name.startswith("Drehzahl"))
    r = fourier.compute(ch.x, ch.y, "s", fourier.parse("FFT({Drehzahl}; h=1..15)"))
    assert r["info"]["periodic"] and r["info"]["periods"] >= 1
    assert r["info"]["f0"] == pytest.approx(1 / (12 * np.pi), rel=0.01) and r["y"][0] > 95
