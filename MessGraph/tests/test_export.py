import subprocess

import numpy as np
import pytest

from messgraph import plotexport as pe
from messgraph.report import GraphSection, ReportData, build_report


def spec(title="Graph 1", time_axis=False, **kw):
    x = np.linspace(0, 60, 9001)
    y = np.sin(x / 5) * 10
    y[4000] = np.nan                                         # Messlücke
    base = dict(title=title, xlim=(0, 60), ylim=(-11, 11), xlabel="time [s]", ylabel="[V]",
                series=[pe.SeriesSpec("U [V]", x, y, (31, 119, 180)), pe.SeriesSpec("I [A] (rechts)", x, y / 10, (255, 127, 14), True)],
                y2lim=(-1.2, 1.2), y2label="[A]", markers=[(20.0, "M1", (205, 95, 0))], limits=[(9.0, (31, 119, 180), False)],
                time_axis=time_axis, legend="ne")
    base.update(kw)
    return pe.PlotSpec(**base)


def test_ticks_and_paper():
    assert pe.nice_ticks(0, 60, 6) == [0, 10, 20, 30, 40, 50, 60]
    assert pe.nice_ticks(12.71, 13.99, 5) == pytest.approx([13.0, 13.5])
    assert pe.nice_ticks(12.71, 13.99, 8) == pytest.approx([12.8, 13.0, 13.2, 13.4, 13.6, 13.8])
    ticks = pe.date_ticks(1_793_000_000, 1_793_000_060, 6)        # 60 s: alle 10 s, mit Sekunden
    assert ticks[0][1].count(":") == 2 and ticks[1][0] - ticks[0][0] == 10
    assert pe.page_size("A4", True) == pytest.approx((841.89, 595.28), abs=0.1)
    assert pe.page_size("A3", False)[1] == pytest.approx(420 * pe.MM)
    assert pe.choose_landscape("auto", (1, 1)) and not pe.choose_landscape("auto", (4, 1))
    assert pe.choose_landscape("portrait", (1, 3)) is False


def test_layout_cells_splits_pages_and_keeps_columns():
    pages = pe.layout_cells(6, (6, 1), 595, 842, min_h=150)
    assert [len(p) for p in pages] == [4, 2]                  # höchstens 4 Graphen à 150 pt auf A4 hoch
    pages = pe.layout_cells(4, (2, 2), 842, 595)
    assert len(pages) == 1 and pages[0][1][1] > pages[0][0][1]  # zweite Spalte rechts daneben
    x, y, w, h = pages[0][3][1:]
    assert x + w <= 842 - 28 + 0.01 and y + h <= 595 - 28 + 0.01


def test_svg_contains_all_elements(tmp_path):
    files = pe.write_svg(str(tmp_path / "g"), [spec(), spec("Zweiter", True, xlim=(1.793e9, 1.793e9 + 60))],
                         (2, 1), "A4", "auto", "Kopf")
    assert files == [str(tmp_path / "g.svg")]
    svg = (tmp_path / "g.svg").read_text()
    assert svg.count("<polyline") >= 8 and "Graph 1" in svg and "Zweiter" in svg and "M1" in svg
    assert "stroke-dasharray" in svg and "U [V]" in svg
    assert 'viewBox="0 0 841.89 595.28"' in svg and 'width="297.0mm"' in svg   # zwei Graphen: Querformat


def test_pdf_is_valid_and_vector(tmp_path):
    path = pe.write_pdf(str(tmp_path / "g"), [spec()] * 5, (5, 1), "A4", "portrait", "MessGraph", "Kopf")
    data = open(path, "rb").read()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page ") == 2 and b"/Image" not in data
    try:
        text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return
    assert "Graph 1" in text and "time [s]" in text and "Seite 1 / 2" in text


def test_report_structure(tmp_path):
    data = ReportData("Prüfbericht", "M. F.", "Kommentar", "07.11.2026 15:00",
                      files=[("a.csv", "/m", 2, "-", "CSV")], settings=[("Marker", "ein")],
                      graphs=[GraphSection("Graph 1", spec(), [("Signale", ["Signal", "Min"], [["U", "1 V"]])], ["Hinweis"])])
    path = build_report(str(tmp_path / "r"), data, "A4")
    try:
        text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return
    for word in ("Prüfbericht", "Messbericht", "Erstellt von: M. F.", "Inhalt", "Übersicht", "Messdateien",
                 "Graph 1", "Signale", "Hinweis"):
        assert word in text, word
    assert text.index("Inhalt") < text.index("Messdateien")


def test_svg_without_legend():
    canvas = pe.SvgCanvas(400, 300)
    pe.render_plot(canvas, spec(legend="none"), 0, 0, 400, 300)
    svg = "".join(canvas.parts)
    assert "U [V]" not in svg


def test_report_signal_legend_below_graph_many_series(tmp_path):
    x = np.linspace(0, 10, 200)
    many = [pe.SeriesSpec(f"Zelle {i:02d} Spannung [V] - messung_lang_{i}.csv", x, x * 0 + i, (20 * i % 255, 80, 160),
                          right=i == 3)
            for i in range(60)]
    data = ReportData("Viele Kurven", created="11.11.2026",
                      graphs=[GraphSection("Zellen", spec(series=many, y2lim=(0, 70)), comment="nach dem Spiegel")])
    path = build_report(str(tmp_path / "r"), data, "A4")
    try:
        text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return
    assert "Signalspiegel" in text
    for i in (0, 31, 59):                                     # alle Einträge vorhanden, auch über den Seitenumbruch
        assert f"Zelle {i:02d} Spannung" in text, i
    assert "(rechte Achse)" in text
    graph_page = text.split("\f")
    first = next(i for i, p in enumerate(graph_page) if "Signalspiegel" in p)
    assert "Zellen" in graph_page[first]                       # Spiegel beginnt auf der Seite des Graphen
    assert text.index("Signalspiegel") < text.index("nach dem Spiegel")
    lines = [l for l in text.splitlines() if "Zelle 0" in l]
    assert any(l.count("Zelle") >= 2 for l in lines)            # mehrspaltig


def _dynamic_report(tmp_path):
    from messgraph.report_html import build_html_report
    x = np.linspace(0, 10, 300)
    series = [pe.SeriesSpec(f"Signal {i} [V]", x, np.sin(x + i), rgb, right=i == 2, key=f"s{i}")
              for i, rgb in enumerate([(31, 119, 180), (255, 127, 14), (44, 160, 44)])]
    graph = GraphSection("Graph A", spec(series=series, limits=[(0.5, (31, 119, 180), False, "s0")]),
                         [("Signale", ["Signal", "Max"], [["Signal 0 [V]", "1 V"], ["Signal 1 [V]", "1 V"],
                                                           ["Signal 2 [V]", "1 V"]])],
                         ["Hinweis <b>"], "Bemerkung & mehr", [["s0", "s1", "s2"]])
    data = ReportData("Bericht <Test>", "M. F.", "Allgemein", "11.11.2026", files=[("a.csv", "/m", 3, "-", "CSV")],
                      graphs=[graph, GraphSection("Graph B", spec())])
    return build_html_report(str(tmp_path / "dyn"), data)


def test_dynamic_report_structure(tmp_path):
    path = _dynamic_report(tmp_path)
    assert path.endswith("dyn.html")
    text = open(path, encoding="utf-8").read()
    assert text.count('class="graph"') == 2 and "Bericht &lt;Test&gt;" in text and "Hinweis &lt;b&gt;" in text
    for key in ("s0", "s1", "s2"):                       # Kurve, Spiegel und Tabellenzeile tragen dieselbe Kennung
        assert text.count(f'data-key="{key}"') >= 3, key
    assert text.count('<g class="sig" data-key="s0">') == 2   # Kurve und Grenzlinie
    assert "(rechte Achse)" in text and "http" not in text.split("<svg", 1)[0].replace("http-equiv", "")
    assert "<script>" in text and "Signalspiegel" in text


def test_dynamic_report_click_highlights(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    path = _dynamic_report(tmp_path)
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1300, "height": 900})
            page.goto("file://" + path)
            section = page.locator("#g1")

            def stroke(key):
                return page.eval_on_selector(f'#g1 g.sig[data-key="{key}"] polyline:not(.hit)',
                                             "e => getComputedStyle(e).stroke")
            original = stroke("s1")
            page.click('#g1 ul.legend li[data-key="s1"]')
            assert "focus" in section.get_attribute("class")
            assert stroke("s1") == original and stroke("s0") == "rgb(211, 211, 211)"
            assert page.locator('#g1 tr[data-key="s1"]').get_attribute("class") == "on"
            page.click('#g1 tr[data-key="s0"]', modifiers=["Control"])          # Strg: zweites Signal dazu
            assert stroke("s0") != "rgb(211, 211, 211)" and stroke("s2") == "rgb(211, 211, 211)"
            page.click('#g1 tr[data-key="s2"]')                                 # ohne Strg: nur dieses
            assert stroke("s2") != "rgb(211, 211, 211)" and stroke("s1") == "rgb(211, 211, 211)"
            page.click('#g1 tr[data-key="s2"]')                                 # erneut: Wahl aufgehoben
            assert "focus" not in section.get_attribute("class")
            page.click('#g1 ul.legend li[data-key="s0"]')
            page.keyboard.press("Escape")
            assert "focus" not in section.get_attribute("class")
            assert "focus" not in (page.locator("#g2").get_attribute("class") or "")
            browser.close()
    except Exception as exc:                                                    # ohne Browser: überspringen
        if "Executable doesn't exist" in str(exc):
            pytest.skip("Chromium fehlt")
        raise


def test_report_margins_ten_percent_of_extreme_values():
    x = np.linspace(0, 10, 101)
    spec_in = pe.PlotSpec(title="G", xlim=(0, 10), ylim=(396, 400),
                          series=[pe.SeriesSpec("U", x, 396 + 0.4 * x, (0, 0, 255)),
                                  pe.SeriesSpec("U2", x, 397 + 0 * x, (255, 0, 0))])
    spec_out = pe.with_report_margins(spec_in)
    lo, hi = spec_out.ylim
    assert hi == pytest.approx(400 * 1.1) and lo == pytest.approx(396 * 0.9)   # +10 % / -10 % der Extremwerte
    assert spec_in.ylim == (396, 400)                                          # Original unverändert


def test_report_margins_negative_zero_visible_range_and_right_axis():
    x = np.linspace(0, 10, 101)
    y = np.where(x <= 5, -20.0, 500.0)                                         # Spitze außerhalb des Ausschnitts
    spec_in = pe.PlotSpec(title="G", xlim=(0, 5), ylim=(0, 1), y2lim=(0, 1),
                          series=[pe.SeriesSpec("a", x, y + x, (0, 0, 0)),
                                  pe.SeriesSpec("b", x, 0 * x, (0, 0, 0), right=True),
                                  pe.SeriesSpec("c", x, 50 + 0 * x, (0, 0, 0), right=True)],
                          limits=[(-40.0, (0, 0, 0), False)])
    out = pe.with_report_margins(spec_in)
    assert out.ylim == pytest.approx((-44.0, -15.0 + 1.5))     # min -40 (Grenze) -10 %, max -15 +10 % von |-15|
    assert out.y2lim == pytest.approx((-5.0, 55.0))            # 0: 10 % der Spannweite, 50: +10 %
    flat = pe.with_report_margins(pe.PlotSpec(title="G", xlim=(0, 1), ylim=(0, 1),
                                              series=[pe.SeriesSpec("z", x, 0 * x, (0, 0, 0))]))
    assert flat.ylim == (-1.0, 1.0)


def test_report_pdf_and_html_use_margins(tmp_path):
    from messgraph.report_html import build_html_report
    x = np.linspace(0, 10, 101)
    spec_in = pe.with_report_margins(pe.PlotSpec(title="G", xlim=(0, 10), ylim=(10, 20),
                                                 series=[pe.SeriesSpec("U [V]", x, 10 + x, (0, 0, 255))]))
    data = ReportData("R", created="13.11.2026", graphs=[GraphSection("G", spec_in)])
    html = open(build_html_report(str(tmp_path / "r"), data), encoding="utf-8").read()
    ticks = [float(v) for v in __import__("re").findall(r">(-?\d+(?:\.\d+)?)</text>", html)]
    assert max(ticks) >= 20 and min(ticks) <= 10 and spec_in.ylim == pytest.approx((9.0, 22.0))
    assert build_report(str(tmp_path / "r"), data).endswith(".pdf")
