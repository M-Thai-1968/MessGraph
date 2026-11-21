#!/usr/bin/env python3
"""Erzeugt die mitgelieferten, nachgezeichneten Abbildungen der Hilfe (messgraph/help_images/*.png).

Die Abbildungen zeigen das Programmfenster mit den Beispieldaten und nummerierten Markierungen.
Kurven und Messwerte stammen aus demo_data und der Programmlogik (Leser, Messrechnung).
Benötigt Playwright mit Chromium. Echte Aufnahmen erzeugt das Programm selbst
("Screenshots erzeugen"); sie ersetzen diese Abbildungen.
"""
from __future__ import annotations

import html
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import dearpygui.dearpygui  # noqa: F401
except ImportError:  # nur die Farbtabelle aus themes wird gebraucht
    import types
    _dpg = types.ModuleType("dearpygui.dearpygui")
    sys.modules["dearpygui"] = types.ModuleType("dearpygui")
    sys.modules["dearpygui.dearpygui"] = _dpg
from messgraph import themes  # noqa: E402
from messgraph.plotexport import value_margin  # noqa: E402
from messgraph.loaders import load_file  # noqa: E402
from messgraph.measure import decimate, drift_unit, fmt, measure  # noqa: E402
from messgraph.timeparse import format_duration, format_wallclock  # noqa: E402

OUT = Path(os.environ.get("MESSGRAPH_SHOT_DIR") or ROOT / "messgraph" / "help_images")
W, H = 1400, 860
SCHEME = os.environ.get("MESSGRAPH_SCHEME", themes.DARK)   # Vorschau anderer Farbschemata
P = themes.PALETTE[SCHEME]


def rgb(c, a=None):
    return f"rgba({c[0]},{c[1]},{c[2]},{a})" if a is not None else f"rgb({c[0]},{c[1]},{c[2]})"


CSS = f"""
* {{ box-sizing: border-box; }}
body {{ margin:0; width:{W}px; height:{H}px; background:{rgb(P['window'])}; color:{rgb(P['text'])};
       font: 13px 'DejaVu Sans', 'Segoe UI', sans-serif; overflow:hidden; position:relative; }}
.menubar {{ height:24px; background:{rgb(P['menu'])}; display:flex; gap:18px; padding:4px 10px; }}
.tabs {{ height:30px; display:flex; gap:4px; padding:4px 8px 0; border-bottom:1px solid {rgb(P['border'])}; }}
.tab {{ padding:5px 14px; background:{rgb(P['tab'])}; border-radius:4px 4px 0 0; }}
.tab.on {{ background:{rgb(P['tab_active'])}; }}
.main {{ position:absolute; top:62px; left:8px; right:8px; bottom:30px; display:flex; gap:8px; }}
.panel {{ background:{rgb(P['child'])}; border:1px solid {rgb(P['border'])}; border-radius:4px; padding:8px; overflow:hidden; }}
.split-v {{ width:7px; background:{rgb(P['border'])}; }}
.split-h {{ height:7px; background:{rgb(P['border'])}; margin:4px 0; }}
.right {{ flex:1; display:flex; flex-direction:column; min-width:0; }}
.row {{ display:flex; gap:8px; align-items:center; margin-bottom:5px; white-space:nowrap; }}
.btn {{ background:{rgb(P['button'])}; padding:3px 10px; border-radius:3px; }}
.btn.small {{ padding:1px 7px; font-size:12px; }}
.btn.tb {{ padding:1px 9px; }}
.tsep {{ color:{rgb(P['border'])}; margin:0 2px; }}
.input {{ background:{rgb(P['frame'])}; padding:3px 8px; border-radius:3px; min-width:60px; color:{rgb(P['text'])}; }}
.hint {{ color:{rgb(P['text_dim'])}; }}
.combo {{ background:{rgb(P['frame'])}; padding:3px 24px 3px 8px; border-radius:3px; position:relative; }}
.combo:after {{ content:'\\25BE'; position:absolute; right:7px; top:2px; color:{rgb(P['text'])}; }}
.check {{ display:inline-flex; align-items:center; gap:6px; }}
.box {{ width:15px; height:15px; background:{rgb(P['frame'])}; border-radius:2px; display:inline-flex;
        align-items:center; justify-content:center; font-size:12px; color:{rgb(P['check'])}; }}
.header {{ background:{rgb(P['header'])}; padding:3px 6px; border-radius:3px; margin:6px 0 4px; }}
.status {{ position:absolute; left:10px; bottom:6px; right:10px; }}
.dim {{ color:{rgb(P['text_dim'])}; }}
.head {{ color:{rgb(P['heading'])}; }}
table.val {{ border-collapse:collapse; width:100%; font-size:12.5px; }}
table.val th {{ background:{rgb(P['table_header'])}; text-align:left; padding:3px 6px; font-weight:normal; }}
table.val td {{ padding:3px 6px; border-top:1px solid {rgb(P['border'])}; }}
table.val tr.alarm td {{ background:{rgb(themes.alarm_row_bg(SCHEME))}; }}
table.val tr:nth-child(odd) td {{ background:{rgb(P['row_alt'])}; }}
table.val tr.bad td {{ background:rgba(220,40,40,.35); }}
.window {{ position:absolute; background:{rgb(P['window'])}; border:1px solid {rgb(P['border'])};
           border-radius:5px; box-shadow:0 10px 40px rgba(0,0,0,.55); }}
.wtitle {{ background:{rgb(P['title_active'])}; padding:5px 10px; border-radius:5px 5px 0 0; }}
.popup {{ position:absolute; background:{rgb(P['popup'])}; border:1px solid {rgb(P['border'])};
          border-radius:4px; padding:8px; box-shadow:0 8px 30px rgba(0,0,0,.5); }}
.sel {{ padding:2px 6px; border-radius:3px; }}
.sel.hl {{ background:{rgb(P['header_hover'])}; }}
.sep {{ height:1px; background:{rgb(P['border'])}; margin:6px 0; }}
.mark {{ position:absolute; width:30px; height:30px; border-radius:50%; background:#e8590c; color:#fff;
         font: bold 16px 'DejaVu Sans', sans-serif; display:flex; align-items:center; justify-content:center;
         border:2px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,.6); z-index:50; }}
.ring {{ position:absolute; border:2.5px solid #e8590c; border-radius:6px; z-index:49; }}
.tooltip {{ position:absolute; background:{rgb(P['popup'])}; border:1px solid {rgb(P['border'])}; padding:6px 9px;
            border-radius:3px; z-index:40; line-height:1.45; }}
"""


# ------------------------------------------------------------------ Daten
DEMO = ROOT / "demo_data"
SIMPLE = {c.name: c for c in load_file(str(DEMO / "demo_einfach.csv")).channels}
GERMAN = {c.name: c for c in load_file(str(DEMO / "demo_deutsch_vorspann.csv")).channels}
STAMP = {c.name: c for c in load_file(str(DEMO / "demo_zeitstempel.csv")).channels}


# ------------------------------------------------------------------ Bausteine
def check(label, on=False):
    return f'<span class="check"><span class="box">{"&#10003;" if on else ""}</span>{html.escape(label)}</span>'


def nice_ticks(lo, hi, n=6):
    span = hi - lo if hi > lo else 1.0
    raw = span / n
    mag = 10 ** np.floor(np.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag * 10)
    start = np.ceil(lo / step) * step
    return [start + i * step for i in range(int((hi - start) / step) + 1)]


def _range(chs, extra=()):
    """Wie im Programm: Y max = größter Wert * 1,1, Y min = kleinster Wert * 0,9 (plotexport.value_margin)."""
    lo = min([float(np.nanmin(c.y)) for c in chs] + list(extra))
    hi = max([float(np.nanmax(c.y)) for c in chs] + list(extra))
    return value_margin(lo, hi)


def plot_svg(w, h, title, series, x_label="", y_label="", cross=None, date_axis=False, epoch=0.0, pid="p",
             right=(), y2_label="", limits=(), legend_pos=None, comments=(), alarm=False):
    """series: [(Kanal, Farbe, Beschriftung)]; right: Indizes der Signale auf der rechten Y-Achse.
    limits: [(Wert, Farbe)] waagerechte Grenzlinien (Y min / Y max) auf der linken Achse."""
    right = set(right)
    ml, mr, mt, mb = 62, (64 if right else 14), 26, 42
    pw, ph = w - ml - mr, h - mt - mb
    xs = [c.x for c, _, _ in series]
    x0, x1 = min(float(x[0]) for x in xs), max(float(x[-1]) for x in xs)
    if any(getattr(c, "bars", False) for c, _, _ in series):    # Balken: halbe Breite Rand links und rechts
        x0, x1 = x0 - 0.6, x1 + 0.6
    left_ch = [c for i, (c, _, _) in enumerate(series) if i not in right] or [series[0][0]]
    y0, y1 = _range(left_ch, [v for v, _ in limits])   # wie im Programm: Grenzlinien zählen beim Einpassen mit
    r0, r1 = _range([series[i][0] for i in right]) if right else (0.0, 1.0)

    def sx(v):
        return ml + (v - x0) / (x1 - x0) * pw

    def sy(v):
        return mt + (1 - (v - y0) / (y1 - y0)) * ph

    def sy2(v):
        return mt + (1 - (v - r0) / (r1 - r0)) * ph

    out = [f'<svg id="{pid}" width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg" style="display:block">',
           f'<rect width="{w}" height="{h}" fill="{rgb(P["plot_frame"])}"/>',
           f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="{rgb(themes.alarm_plot_bg(SCHEME) if alarm else P["plot_bg"])}" '
           f'stroke="{rgb(P["border"])}"/>',
           f'<text id="{pid}-title" x="{w / 2}" y="17" fill="{rgb(P["text"])}" font-size="13" text-anchor="middle">'
           f'{html.escape(title)}</text>']
    for t in nice_ticks(y0, y1, 5):
        y = sy(t)
        out.append(f'<line x1="{ml}" x2="{ml + pw}" y1="{y:.1f}" y2="{y:.1f}" stroke="{rgb(P["grid"], .55)}"/>')
        out.append(f'<text x="{ml - 6}" y="{y + 4:.1f}" fill="{rgb(P["text"])}" font-size="11" text-anchor="end">'
                   f'{t:g}</text>')
    if right:
        for tv in nice_ticks(r0, r1, 5):
            y = sy2(tv)
            out.append(f'<line x1="{ml + pw}" x2="{ml + pw + 5}" y1="{y:.1f}" y2="{y:.1f}" stroke="{rgb(P["text"])}"/>')
            out.append(f'<text x="{ml + pw + 8}" y="{y + 4:.1f}" fill="{rgb(P["text"])}" font-size="11">{tv:g}</text>')
        out.append(f'<text id="{pid}-y2" x="{w - 10}" y="{mt + ph / 2}" fill="{rgb(P["text"])}" font-size="12" '
                   f'text-anchor="middle" transform="rotate(90 {w - 10} {mt + ph / 2})">{html.escape(y2_label)}</text>')
    if date_axis:
        ticks = nice_ticks(x0, x1, 5)
        labels = [format_wallclock(epoch + t)[11:19] for t in ticks]
        labels[0] = format_wallclock(epoch + ticks[0])[:5] + " " + labels[0]
    else:
        ticks = nice_ticks(x0, x1, 7)
        labels = [f"{t:g}" for t in ticks]
    for t, label in zip(ticks, labels):
        x = sx(t)
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{mt}" y2="{mt + ph}" stroke="{rgb(P["grid"], .55)}"/>')
        out.append(f'<text x="{x:.1f}" y="{mt + ph + 15}" fill="{rgb(P["text"])}" font-size="11" '
                   f'text-anchor="middle">{label}</text>')
    out.append(f'<text id="{pid}-xlabel" x="{ml + pw / 2}" y="{h - 8}" fill="{rgb(P["text"])}" font-size="12" text-anchor="middle">'
               f'{html.escape(x_label)}</text>')
    if y_label:
        out.append(f'<text x="14" y="{mt + ph / 2}" fill="{rgb(P["text"])}" font-size="12" text-anchor="middle" '
                   f'transform="rotate(-90 14 {mt + ph / 2})">{html.escape(y_label)}</text>')
    out.append(f'<clipPath id="clip-{pid}"><rect x="{ml}" y="{mt}" width="{pw}" height="{ph}"/></clipPath>')
    for index, (channel, color, _) in enumerate(series):
        fy = sy2 if index in right else sy
        if getattr(channel, "bars", False):                       # Harmonische: senkrechte Balken (Breite 0,6)
            half = abs(sx(0.3) - sx(0.0))
            for bx, by in zip(channel.x, channel.y):
                top, base = fy(by), fy(0.0)
                out.append(f'<rect clip-path="url(#clip-{pid})" x="{sx(bx) - half:.1f}" y="{min(top, base):.1f}" '
                           f'width="{2 * half:.1f}" height="{abs(base - top):.1f}" fill="{rgb(color)}" '
                           f'fill-opacity="0.8" stroke="{rgb(color)}"/>')
            continue
        ok = np.isfinite(np.asarray(channel.y, float))
        edges = np.flatnonzero(np.diff(np.concatenate(([0], ok.astype(np.int8), [0]))))
        for start, stop in zip(edges[0::2], edges[1::2]):        # Lücken (NaN) trennen die Linie wie im Programm
            dx, dy = decimate(channel.x[start:stop], channel.y[start:stop], bins=600)
            pts = " ".join(f"{sx(a):.1f},{fy(b):.1f}" for a, b in zip(dx, dy) if np.isfinite(b))
            out.append(f'<polyline clip-path="url(#clip-{pid})" points="{pts}" fill="none" stroke="{rgb(color)}" '
                       f'stroke-width="1.6"/>')
    for li, (value, color) in enumerate(limits):
        out.append(f'<line id="{pid}-lim{li}" x1="{ml}" x2="{ml + pw}" y1="{sy(value):.1f}" y2="{sy(value):.1f}" '
                   f'stroke="{rgb(color)}" stroke-width="1.6"/>')
    if cross:
        for k, xv in enumerate(cross):
            col = P["cross"][k]
            x = sx(xv)
            out.append(f'<line id="{pid}-k{k + 1}" x1="{x:.1f}" x2="{x:.1f}" y1="{mt}" y2="{mt + ph}" stroke="{rgb(col)}" stroke-width="1.6"/>')
            out.append(f'<text x="{x + 4:.1f}" y="{mt + 13}" fill="{rgb(col)}" font-size="12">M{k + 1}</text>')
    series = [(c, col, f"{lbl} (rechts)" if i in right else lbl) for i, (c, col, lbl) in enumerate(series)]
    lw = max(len(lbl) for _, _, lbl in series) * 7.4 + 36
    lx, ly = (ml + 10, mt + 10) if legend_pos != "ne" else (ml + pw - lw - 10, mt + 10)   # Lage wie im Programm
    out.append(f'<rect id="{pid}-legend" x="{lx}" y="{ly}" width="{lw:.0f}" height="{8 + 18 * len(series)}" '
               f'fill="{rgb(P["popup"], .92)}" stroke="{rgb(P["border"])}"/>')
    for i, (_, color, label) in enumerate(series):
        yy = ly + 16 + 18 * i
        out.append(f'<rect x="{lx + 8}" y="{yy - 9}" width="11" height="11" fill="{rgb(color)}"/>')
        out.append(f'<text x="{lx + 26}" y="{yy}" fill="{rgb(P["text"])}" font-size="12">{html.escape(label)}</text>')
    for ci, (cx, cy, text) in enumerate(comments):   # Kommentarfelder wie im Programm (Anmerkung mit Versatz)
        px, py = sx(cx), sy(cy)
        lines = text.split("\n")
        bw, bh = max(len(t_) for t_ in lines) * 7.0 + 12, 18 * len(lines) + 4
        bx, by = px + 14, py - 14 - bh
        out.append(f'<g id="{pid}-comment{ci}"><circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{rgb(P["heading"])}"/>'
                   f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.0f}" height="{bh}" rx="2" fill="{rgb(P["heading"], .9)}"/>')
        for li, line in enumerate(lines):
            out.append(f'<text x="{bx + 6:.1f}" y="{by + 16 + 18 * li:.1f}" fill="#101418" font-size="12">'
                       f'{html.escape(line)}</text>')
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)


def left_panel(width, files, search="", target="Automatisch", tooltip=None, multi=None):
    """files: [(Name, Hinweise, [(Signal, angehakt)], mf4)]; multi: (Titel, Signal, Info) der Leiste über alle Dateien"""
    parts = [f'<div class="panel" id="left" style="width:{width}px">',
             '<div class="row" id="l-buttons"><span class="btn">Dateien öffnen...</span><span class="btn">Alle abwählen</span></div>',
             '<div>Zielgraph</div>', f'<div class="row"><span class="combo" id="l-target" style="flex:1">{html.escape(target)}</span></div>',
             f'<div class="row"><span class="input" id="l-search" style="flex:1">{html.escape(search) or "<span class=dim>Signal suchen</span>"}'
             '</span></div>']
    if multi:
        title, signal, info = multi
        parts.append(f'<div id="l-multi"><div class="head">{html.escape(title)}</div>'
                     f'<div class="row"><span class="combo" id="l-mcombo" style="flex:1">{html.escape(signal)}</span></div>'
                     '<div class="row" id="l-mbtn" style="display:inline-flex"><span class="btn small">Gemeinsamer Graph</span><span class="btn small">Einzelgraphen</span>'
                     f'<span class="btn small">Entfernen</span></div><div class="dim" id="l-minfo">{html.escape(info)}</div></div>')
    parts.append('<div class="sep"></div>')
    for fi, (name, warnings, signals, mf4) in enumerate(files):
        parts.append(f'<div class="header" id="l-file{fi}">&#9662; {html.escape(name)}</div>')
        parts.append(f'<div class="row" id="l-close{fi}"><span class="btn small">Schließen</span>'
                     + ('<span class="btn small" id="l-db">Datenbasen...</span>' if mf4
                        else f'<span class="btn small" id="l-ascii{fi}">ASCII-Import...</span>')
                     + f'<span class="btn small" id="l-calc{fi}">Berechnen...</span></div>')
        parts.append(f'<div class="dim" style="margin-bottom:3px"><span id="l-detect{fi}">Erkennung (Maus hierher)</span></div>')
        for warning in warnings:
            parts.append(f'<div class="dim" id="l-warn{fi}" style="margin-bottom:3px;white-space:normal">Hinweis: {html.escape(warning)}</div>')
        for si, (signal, on) in enumerate(signals):
            parts.append(f'<div style="margin:3px 0"><span id="l-sig{fi}-{si}">{check(signal, on)}</span></div>')
    parts.append("</div>")
    return "".join(parts)


def toolbar(matrix="", cross=False, date=False, file=""):
    """Werkzeugleiste wie im Programm: zwei kompakte Zeilen mit Gruppen und Trennern."""
    m = html.escape(matrix) if matrix else '<span class="dim">z. B. 2*3</span>'
    sep = '<span class="tsep">|</span>'
    return (f'<div id="toolbar"><div class="row" id="t-row1"><span class="dim">Datei</span>'
            f'<span class="combo" id="t-file" style="width:200px;overflow:hidden">{html.escape(file)}</span>{sep}'
            f'<span class="dim">Matrix</span><span id="t-matrix" class="input" style="width:{140 if matrix else 110}px;overflow:hidden">{m}</span>'
            '<span class="btn tb" id="t-apply">Anwenden</span><span class="btn tb" id="t-rows">Zeilen...</span>'
            f'<span class="btn tb" id="t-arrange">Vorschlag...</span>{sep}'
            '<span class="btn tb" id="t-fit">Alles anzeigen</span><span class="btn tb" id="t-clear">Alle Plots löschen</span></div>'
            f'<div class="row" id="t-row2"><span id="t-cross">{check("Marker", cross)}</span>'
            f'<span id="t-sync">{check("Marker synchron", True)}</span>{sep}'
            f'<span>{check("X-Achsen koppeln", True)}</span><span id="t-date">{check("Datum/Uhrzeit-Achse", date)}</span>'
            f'<span id="t-reg">{check("Regressionslinien", False)}</span>{sep}'
            '<span class="btn tb" id="t-cmp">Dateien vergleichen...</span><span class="btn tb" id="t-view">Darstellung...</span>'
            '</div></div>')


def value_table(rows, prognosis=True):
    heads = ["Graph", "Signal", "X1", "X2", "Wert 1", "Wert 2", "Delta X", "Delta Y", "Drift", "Y min", "Y max",
             "Zielzeit", "Drift (Regression 1)", "Prognose"]
    head = "".join(f'<th{" id=v-w1" if h == "Wert 1" else ""}>{h}</th>' for h in heads)
    cell = lambda c: c if str(c).startswith("<span") else html.escape(str(c))   # Eingabefelder als HTML
    body = "".join(('<tr class="alarm">' if getattr(r, "alarm", False) else "<tr>")
                   + "".join(f"<td>{cell(c)}</td>" for c in r) + "</tr>" for r in rows)
    source = ('<div class="row" id="v-source" style="margin:0 0 4px 0"><span>Mode</span><span class="combo" '
              'style="width:200px">(manuell)</span><span class="dim">Keine Grenzwert-Konfiguration geladen (Graph-Optionen &gt; '
              'Grenzwert-Konfiguration laden).</span></div>')
    return f'{source}<table class="val"><tr>{head}</tr>{body}</table>'


def limit_input(value, kind, ident=""):
    text = f"{value:g}" if value is not None else f'<span class="dim">{kind}</span>'
    return f'<span class="input"{f" id={chr(34)}{ident}{chr(34)}" if ident else ""} style="display:inline-block;min-width:52px;padding:1px 6px">{text}</span>'


def _dhm(seconds):
    minutes = int(round(seconds / 60))
    return f"{minutes // 1440} days {minutes % 1440 // 60} hrs {minutes % 60} min"


def prognosis_text(channel, slope, lo, hi, date_axis):
    """Wie im Programm: x1 = 0 am letzten Messpunkt, b = letzter Wert, m aus der Regression."""
    from messgraph.measure import predict
    if lo is None and hi is None:
        return "-"
    p = predict(slope, float(channel.y[-1]), lo, hi)
    if p.kind == "inside":
        return "kein Schnitt (Drift führt von der Grenze weg)"
    if p.kind == "reached":
        return f"Grenze {fmt(p.limit, channel.unit)} schon überschritten (letzter Wert {fmt(channel.y[-1], channel.unit)})"
    if p.kind not in ("max", "min"):
        return "-"
    if date_axis:
        return f"{p.kind}, {format_wallclock(channel.x_epoch + float(channel.x[-1]) + p.x2)[:19]}, {_dhm(p.x2)}"
    return f"{p.kind}, x2 = {fmt(p.x2, channel.x_unit)}" + (f", {_dhm(p.x2)}" if channel.x_unit == "s" else "")


class Row(list):
    alarm = False


def target_input(seconds, ident=""):
    from messgraph.measure import format_target
    text = format_target(seconds) if seconds else '<span class="dim">z. B. 2d 6h 30m</span>'
    return (f'<span{f" id={chr(34)}{ident}{chr(34)}" if ident else ""}><span class="input" style="display:inline-block;'
            f'min-width:70px;padding:1px 6px">{text}</span> <span class="btn small">Alle</span></span>')


def measure_row(graph, channel, x1, x2, date_axis=False, lo=None, hi=None, prognosis=True, ids=("", ""), target=None):
    from messgraph.measure import regression
    m = measure(channel.x, channel.y, x1, x2)
    xu = channel.x_unit
    if date_axis:
        a, b, dx = format_wallclock(channel.x_epoch + x1), format_wallclock(channel.x_epoch + x2), format_duration(m.delta_x)
    else:
        a, b, dx = fmt(m.x1, xu), fmt(m.x2, xu), fmt(m.delta_x, xu)
    from messgraph.measure import format_target, predict
    slope = regression(channel.x, channel.y)[0]
    text = prognosis_text(channel, slope, lo, hi, date_axis)
    row = Row([graph, channel.label, a, b, fmt(m.value1, channel.unit), fmt(m.value2, channel.unit), dx,
               fmt(m.delta_y, channel.unit), fmt(m.drift, drift_unit(channel.unit, xu)),
               limit_input(lo, "Min", ids[0]), limit_input(hi, "Max", ids[1]), target_input(target, "v-target"),
               fmt(slope, drift_unit(channel.unit, xu)), text])
    if target and (lo is not None or hi is not None):      # wie im Programm: Prognose früher als Zielzeit
        p = predict(slope, float(channel.y[-1]), lo, hi)
        row.alarm = p.kind == "reached" or (p.kind in ("max", "min") and p.x2 < target)
        if row.alarm:
            row[-1] = text + f"  (Zielzeit {format_target(target)} verletzt)"
    return row


def page(body, status="Bereit.", tab="Graph"):
    tabs = '<span class="tab on">Graph</span>'                      # Hilfe ist ein eigenes Fenster, kein Reiter
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f'<div class="menubar" id="menubar"><span id="m-datei">Datei</span><span id="m-graph">Graph-Optionen</span><span id="m-limiter">Limiter</span><span id="m-auto">Auto</span>'
            f'<span id="m-hilfe" style="margin-left:18px">Hilfe</span><span style="flex:1"></span>'
            f'<span id="m-lang">Sprache: Deutsch</span></div><div class="tabs">{tabs}</div>'
            f'{body}<div class="status"><span id="status">{html.escape(status)}</span></div></body></html>')


def marks(*items):
    """Markierungen als (Nummer, CSS-Selektor, Lage, Rahmen). Lage: left, right, top, bottom, center, inside."""
    return list(items)


MARK_JS = """
(specs) => {
  const W = window.innerWidth, H = window.innerHeight;
  for (const [n, sel, where, ring] of specs) {
    const el = document.querySelector(sel);
    if (!el) throw new Error('Element fehlt: ' + sel);
    const r = el.getBoundingClientRect();
    if (ring) {
      const d = document.createElement('div'); d.className = 'ring';
      Object.assign(d.style, {left: (r.left - 4) + 'px', top: (r.top - 3) + 'px',
                              width: (r.width + 8) + 'px', height: (r.height + 6) + 'px'});
      document.body.appendChild(d);
    }
    let x = r.left + r.width / 2, y = r.top + r.height / 2;
    if (where === 'left') x = r.left - 22;
    if (where === 'right') x = r.right + 22;
    if (where === 'top') y = r.top - 20;
    if (where === 'bottom') y = r.bottom + 20;
    if (where === 'inside') { x = r.right - 24; y = r.top + 22; }
    x = Math.max(16, Math.min(W - 16, x)); y = Math.max(16, Math.min(H - 16, y));
    const m = document.createElement('div'); m.className = 'mark'; m.textContent = n;
    Object.assign(m.style, {left: (x - 15) + 'px', top: (y - 15) + 'px'});
    document.body.appendChild(m);
  }
}
"""


SER = P["series"]
LEFT = 330
PLOT_W = W - LEFT - 16 - 7 - 8 - 12


def plot_h(count, table_h=0, toolbar=46):
    avail = H - 62 - 30 - toolbar - 14 - (table_h + 22 if table_h else 0)
    return int((avail - 4 * (count - 1) - 8) / count)


def graph_main(plots_html, left_html, tb, table_html=None, table_h=170):
    right = [f'<div class="right">{tb}<div class="panel" id="plots" style="flex:1;padding:4px;display:flex;flex-direction:column;gap:4px">'
             f'{plots_html}</div>']
    if table_html:
        right.append(f'<div class="split-h" id="splith"></div><div class="panel" id="table" style="height:{table_h}px;padding:4px">{table_html}</div>')
    right.append("</div>")
    return f'<div class="main">{left_html}<div class="split-v" id="splitv"></div>{"".join(right)}</div>'


# ------------------------------------------------------------------ Motive
def swatch(color):
    return (f'<span style="width:18px;height:18px;background:{rgb(color)};display:inline-block;border-radius:2px;'
            f'border:1px solid {rgb(P["border"])}"></span>')


def scene_uebersicht():
    left = left_panel(LEFT, [("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", True),
                                                       ("voltage [V]", False)], False)])
    ph = plot_h(2)
    plots = (plot_svg(PLOT_W, ph, "Graph 1", [(SIMPLE["speed"], SER[0], "speed [km/h]")], "time [s]", "[km/h]", pid="p1")
             + plot_svg(PLOT_W, ph, "Graph 2", [(SIMPLE["temperature"], SER[0], "temperature [°C]")], "time [s]",
                        "[°C]", pid="p2"))
    body = graph_main(plots, left, toolbar(file="demo_einfach.csv"))
    return page(body, "temperature [°C]: 3000 Werte."), marks(
        (1, "#menubar", "bottom", True), (2, "#l-sig0-1", "right", False), (3, "#toolbar", "right", True),
        (4, "#p1-title", "right", False), (5, "#splitv", "right", True), (6, "#status", "right", False))


def scene_dateiliste():
    left = left_panel(LEFT, [("demo_deutsch_vorspann.csv", ["Ohne Zahlenwerte, nicht angeboten: Status"],
                              [("Drehzahl [rpm]", True), ("Öltemperatur [°C]", False)], False),
                             ("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", False),
                                                       ("voltage [V]", False)], False)])
    ph = plot_h(2)
    plots = (plot_svg(PLOT_W, ph, "Graph 1", [(GERMAN["Drehzahl"], SER[0], "Drehzahl [rpm]")], "Zeit [s]", "[rpm]", pid="p1")
             + plot_svg(PLOT_W, ph, "Graph 2", [(SIMPLE["speed"], SER[0], "speed [km/h]")], "time [s]", "[km/h]", pid="p2"))
    body = graph_main(plots, left, toolbar())
    body += ('<div class="tooltip" id="tip" style="left:372px;top:212px;width:310px">Trennzeichen: Semikolon, '
             'Dezimalzeichen: ,<br>Kodierung: cp1252<br>Kopfzeile: Zeile 5 (automatisch erkannt)<br>Daten ab Zeile 7<br>'
             '3000 Zeilen, 2 Datenspalten<br>X-Achse: Zeit [s]</div>')
    return page(body, "demo_einfach.csv: 3 Signale."), marks(
        (1, "#l-buttons", "right", False), (2, "#l-target", "right", False), (3, "#l-search", "right", False),
        (4, "#l-file0", "right", False), (5, "#tip", "right", True), (6, "#l-warn0", "right", False),
        (7, "#l-sig0-0", "right", False))


def scene_browser():
    left = left_panel(LEFT, [])
    body = graph_main('', left, toolbar())        # ohne Datei bleibt der Plotbereich leer
    x, y, w, h = 250, 120, 900, 600
    rows = [("[Ordner]  Archiv", "", "", None), ("demo_deutsch_vorspann.csv", "68.5 kB", "06.11.2026 07:35", True),
            ("demo_einfach.csv", "85.9 kB", "06.11.2026 07:35", True),
            ("demo_zeitstempel.csv", "99.4 kB", "06.11.2026 07:35", True),
            ("Messung_Pruefstand_3.MF4", "12.4 MB", "05.11.2026 16:02", False),
            ("HTOE_PV_DUT3.parquet", "619.0 kB", "06.11.2026 07:04", False)]
    table = "".join(
        f'<tr><td>{"<span class=sel id=b-folder>" + html.escape(n) + "</span>" if on is None else f"<span id=b-file{i}>" + check(n, on) + "</span>"}</td>'
        f'<td class="dim">{sz}</td><td class="dim">{d}</td></tr>' for i, (n, sz, d, on) in enumerate(rows))
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
             '<div class="wtitle">Dateien öffnen</div><div style="padding:10px">'
             '<div class="row" id="b-nav"><span class="btn">Hoch</span><span class="btn">Start</span>'
             '<span class="input" style="flex:1">C:\\Messdaten\\MessGraph\\demo_data</span></div>'
             '<div class="row" id="b-filter"><span>Dateityp</span><span class="combo" style="width:260px">Messdaten (mf4, blf, csv, parquet)</span>'
             '<span class="input" style="width:200px"><span class="dim">Name enthält</span></span>'
             '<span class="btn">Alle im Ordner</span><span class="btn">Keine</span></div>'
             f'<div class="panel" style="height:{h - 175}px"><table class="val"><tr><th style="width:62%">Name</th>'
             f'<th>Größe</th><th>Geändert</th></tr>{table}</table></div>'
             '<div style="margin:8px 0"><span id="b-count">3 Datei(en) ausgewählt.</span></div>'
             '<div class="row"><span id="b-open" class="btn" style="width:120px;text-align:center">Öffnen</span>'
             '<span class="btn" style="width:120px;text-align:center">Abbrechen</span></div></div></div>')
    return page(body), marks((1, "#b-nav", "left", False), (2, "#b-filter", "right", True),
                             (3, "#b-folder", "right", False), (4, "#b-file2", "right", False),
                             (5, "#b-count", "right", False), (6, "#b-open", "right", False))


def scene_matrix():
    left = left_panel(LEFT, [("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", True),
                                                       ("voltage [V]", True)], False),
                             ("demo_zeitstempel.csv", [], [("Current [A]", True)], False)],
                      target="Graph 1 (Z1/S1): Fahrzeug")
    cw = (PLOT_W - 4) // 2
    ch = plot_h(2)
    g1 = plot_svg(cw, ch, "Fahrzeug", [(SIMPLE["speed"], SER[0], "speed [km/h]"),
                                       (SIMPLE["temperature"], (240, 200, 60), "temperature [°C]")], "time [s]",
                  "[km/h]", pid="p1", right={1}, y2_label="[°C]")
    g2 = plot_svg(cw, ch, "Bordnetz", [(SIMPLE["voltage"], SER[0], "voltage [V]")], "time [s]", "[V]", pid="p2")
    g3 = plot_svg(cw, ch, "Prüfstand", [(GERMAN["Drehzahl"], SER[0], "Drehzahl [rpm]")], "Zeit [s]", "[rpm]", pid="p3")
    g4 = plot_svg(cw, ch, "Graph 4", [(STAMP["Current"], SER[0], "Current [A]")], "Timestamp [s]", "[A]", pid="p4")
    plots = f'<div style="display:flex;gap:4px">{g1}{g2}</div><div style="display:flex;gap:4px">{g3}{g4}</div>'
    body = graph_main(plots, left, toolbar("2*2", file="Mehrere Dateien"))
    return page(body, "Matrix 2*2."), marks((1, "#t-matrix", "bottom", True), (2, "#p1-title", "right", False),
                                            (3, "#p1-legend", "right", True), (4, "#l-target", "right", False),
                                            (5, "#p1-y2", "left", True))


def scene_zeilen():
    left = left_panel(LEFT, [("demo_lauf_1.csv", [], [("Spannung [V]", True), ("Strom [A]", True),
                                                      ("Temperatur [°C]", True)], False)])
    run = load_file(str(DEMO / "demo_lauf_1.csv"))
    by = {c.name: c for c in run.channels}
    names = list(by)
    rows = [[1, 1, 1], [1, 1, 1], [2, 1], [3]]
    rh = int((plot_h(1) - 3 * 4) / 4)
    unit = (PLOT_W - 2 * 4) / 3
    html_rows, number = [], 0
    for r, widths in enumerate(rows):
        cells = []
        for width in widths:
            number += 1
            ch = by[names[(number - 1) % len(names)]]
            w = int(width * unit + (width - 1) * 4)
            cells.append(plot_svg(w, rh, f"Graph {number}", [(ch, SER[(number - 1) % len(SER)], ch.label)], "time [s]",
                                  f"[{ch.unit}]", pid=f"z{number}"))
        html_rows.append(f'<div style="display:flex;gap:4px" id="z-row{r + 1}">' + "".join(cells) + "</div>")
    body = graph_main("".join(html_rows), left, toolbar("4*3: 3, 3, 2+1, 1", file="demo_lauf_1.csv"))
    x, y = 866, 112
    preview = []
    pw, prh, gap = 300, 34, 4
    cw = (pw - 2 * gap) / 3
    number = 0
    for r, widths in enumerate(rows):
        col = 0
        for width in widths:
            number += 1
            left_px = col * (cw + gap)
            preview.append(f'<div style="position:absolute;left:{left_px:.0f}px;top:{r * (prh + gap)}px;'
                           f'width:{width * cw + (width - 1) * gap:.0f}px;height:{prh}px;border:1px solid '
                           f'{rgb(P["heading"])};background:{rgb(P["frame"])};font-size:12px;padding:8px 6px;'
                           f'box-sizing:border-box">Graph {number}</div>')
            col += width
    inputs = "".join(f'<div class="row"><span style="width:60px">Zeile {r + 1}</span><span class="input" '
                     f'style="width:90px">{v}</span></div>' for r, v in enumerate(["3", "3", "2+1", "1"]))
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:520px;height:330px">'
             '<div class="wtitle">Zeilen zusammenfassen</div><div style="padding:10px">'
             '<div class="head">Matrix 4*3</div>'
             '<div class="dim">Je Zeile die Anzahl gleich breiter Graphen (3 = drei Graphen, 1 = ein Graph über die '
             'ganze Breite) oder die Breiten in Spalten mit + (2+1 = ein Graph über zwei Spalten und einer über eine).</div>'
             f'<div style="display:flex;gap:16px;margin-top:8px"><div id="r-inputs">{inputs}</div>'
             f'<div><div>Vorschau</div><div id="r-preview" style="position:relative;width:{pw}px;height:{4 * (prh + gap)}px">'
             + "".join(preview) + '</div></div></div>'
             '<div>9 Graphen</div>'
             '<div class="row" id="r-btn" style="display:inline-flex"><span class="btn" style="width:110px;text-align:center">Übernehmen</span>'
             '<span class="btn">Alle Einzelgraphen</span><span class="btn">Schließen</span></div></div></div>')
    return page(body, "Matrix 4*3 mit zusammengefassten Bereichen: 9 Graphen."), marks(
        (1, "#t-matrix", "bottom", True), (2, "#t-rows", "bottom", True), (3, "#z-row3", "left", True),
        (4, "#z-row4", "left", True), (5, "#r-inputs", "left", False), (6, "#r-preview", "top", False),
        (7, "#r-btn", "right", False))


def scene_vorschlag():
    from messgraph import arrange
    run = load_file(str(DEMO / "demo_pruefstand.asc"))
    p = arrange.propose(run.channels)
    left = left_panel(LEFT, [(run.name, [], [(c.label, False) for c in run.channels[:9]], False)])
    body = graph_main("", left, toolbar())
    x, y, w, h = 330, 96, 980, 545
    pw, ph, gap = 540.0, 360.0, 4.0
    rows, cols = p.matrix
    row_h = min(70.0, (ph - gap * (rows - 1)) / rows)
    col_w = (pw - gap * (cols - 1)) / cols
    boxes, index = [], 0
    for r, widths in enumerate(p.spans):
        col = 0
        for width in widths:
            g = p.groups[index]
            boxes.append(f'<div style="position:absolute;left:{col * (col_w + gap):.0f}px;top:{r * (row_h + gap):.0f}px;'
                         f'width:{width * col_w + (width - 1) * gap:.0f}px;height:{row_h:.0f}px;border:1px solid '
                         f'{rgb(P["heading"])};background:{rgb(P["frame"])};font-size:12px;padding:3px 5px;'
                         f'box-sizing:border-box;overflow:hidden">{html.escape(g.title)}<br>'
                         f'<span style="color:{rgb(P["text_dim"])}">{len(g.signals)} Kurven</span></div>')
            col += width
            index += 1
    lines, current = [], None
    for number, g in enumerate(p.groups, 1):
        if g.row != current:
            current = g.row
            lines.append(f'<div class="head">{html.escape(current)}</div>')
        names = ", ".join(c.name for c in g.signals)
        names = names if len(names) < 70 else names[:68] + " ..."
        lines.append(f'<div style="font-size:12px">&nbsp;&nbsp;{number}. {html.escape(g.title)}: {html.escape(names)}</div>')
    summary = (f"Vorschlag: Matrix {arrange_layout(p)}, {p.count} Graphen mit "
               f"{sum(len(g.signals) for g in p.groups)} Signalen")
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
             '<div class="wtitle">Anordnung vorschlagen</div><div style="padding:10px">'
             '<div class="dim">Die Signale werden nach Namen und Einheit gruppiert: gleiche Größe desselben Systems in '
             'einen Graphen (Ist- und Sollwerte gemeinsam), je System eine Zeile der Matrix (z. B. AC: Spannung, Strom, '
             'Leistung, Frequenz), Temperaturen und Zustände in eigenen Zeilen.</div>'
             '<div class="row" id="v-src"><span>Signale</span><span class="combo" style="width:330px">Alle Signale: '
             f'{html.escape(run.name)} ({len(run.channels)})</span><span>Kurven je Graph höchstens</span>'
             '<span class="input" style="width:60px">8</span><span>Spalten höchstens</span>'
             '<span class="input" style="width:60px">4</span></div>'
             f'<div class="row">{check("Temperaturen und Zustände in eigenen Zeilen", True)}</div>'
             f'<div class="head" id="v-sum">{html.escape(summary)}</div>'
             f'<div style="display:flex;gap:10px"><div id="v-prev" style="position:relative;width:{pw:.0f}px;'
             f'height:{ph:.0f}px">' + "".join(boxes) + '</div>'
             f'<div id="v-list" style="flex:1;height:{ph:.0f}px;overflow:hidden;border:1px solid {rgb(P["frame"])};'
             'padding:4px">' + "".join(lines) + '</div></div>'
             '<div class="row" id="v-btn" style="display:inline-flex;margin-top:8px"><span class="btn" '
             'style="width:110px;text-align:center">Übernehmen</span><span class="btn" style="width:110px;'
             'text-align:center">Schließen</span></div></div></div>')
    return page(body, "Anordnung vorschlagen"), marks(
        (1, "#t-arrange", "bottom", True), (2, "#v-src", "left", False), (3, "#v-prev", "left", False),
        (4, "#v-list", "right", False), (5, "#v-btn", "right", False))


def arrange_layout(p):
    from messgraph.layout import format_layout
    return format_layout(p.matrix, p.spans)


def scene_kontextmenue():
    left = left_panel(LEFT, [("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", True),
                                                       ("voltage [V]", True)], False)])
    ph = plot_h(2)
    plots = (plot_svg(PLOT_W, ph, "Fahrzeug", [(SIMPLE["speed"], SER[0], "speed [km/h]"),
                                               (SIMPLE["temperature"], (240, 200, 60), "temperature [°C]")],
                      "time [s]", "[km/h]", pid="p1", right={1}, y2_label="[°C]")
             + plot_svg(PLOT_W, ph, "Bordnetz", [(SIMPLE["voltage"], SER[0], "voltage [V]")], "time [s]", "[V]", pid="p2",
                        comments=[(1.5, float(SIMPLE["voltage"].y[int(len(SIMPLE["voltage"].y) * 1.5 / 60)]),
                                   "Welligkeit beim Start")]))
    body = graph_main(plots, left, toolbar())
    x, y = 640, 30
    body += (f'<div class="popup" style="left:{x}px;top:{y}px;width:470px">'
             '<div class="head">Fahrzeug</div><div class="sep"></div>'
             '<div class="head">Name des Graphen</div>'
             '<div class="row" id="c-name"><span class="input" style="flex:1">Fahrzeug</span><span class="btn">Übernehmen</span></div>'
             '<div class="sep"></div><div class="head">Kommentar an der Klickstelle</div>'
             '<div id="c-comment"><div class="input" style="height:34px">Höchstgeschwindigkeit erreicht</div>'
             '<div class="row" style="margin-top:3px"><span class="btn">Kommentar einfügen</span></div>'
             '<div class="row" style="margin-top:3px"><span class="input" style="flex:1">Anfahren</span>'
             '<span class="btn small">Übernehmen</span><span class="btn small">Hierher</span>'
             '<span class="btn small">Löschen</span></div></div>'
             '<div class="sep"></div><div class="head">Legende (auch per Rechtsklick auf die Legende)</div>'
             '<div id="c-legend" style="display:grid;grid-template-columns:1fr 1fr 1fr">'
             '<div class="sel">» oben links</div><div class="sel">oben Mitte</div><div class="sel">oben rechts</div>'
             '<div class="sel">unten links</div><div class="sel">unten Mitte</div><div class="sel">unten rechts</div></div>'
             '<div class="sep"></div><div class="head">Drucken und Export</div>'
             '<div id="c-print"><div class="sel">Diesen Graphen drucken / exportieren...</div>'
             '<div class="sel">Alle Graphen drucken / exportieren...</div><div class="sel">Report als PDF erstellen...</div></div>'
             '<div class="sep"></div><div class="head">Signal hinzufügen</div>'
             '<div class="row"><span class="input" id="c-search" style="flex:1">volt</span></div>'
             '<div class="panel" style="height:30px;padding:2px"><div class="sel hl">voltage [V]</div></div>'
             '<div class="sep"></div><div class="head">Signal entfernen</div>'
             '<div id="c-remove"><div class="sel">Entfernen: speed [km/h]</div><div class="sel">Entfernen: temperature [°C]</div>'
             '<div class="sel">Alle Signale dieses Graphen entfernen</div></div>'
             '<div class="sep"></div><div class="head">Signalfarben (Klick auf das Farbfeld)</div>'
             f'<div id="c-colors"><div class="row">{swatch(SER[0])}speed [km/h]</div>'
             f'<div class="row">{swatch((240, 200, 60))}temperature [°C]</div></div>'
             '<div class="sel" id="c-default">Standardfarben wiederherstellen</div>'
             '<div class="sep"></div><div class="head">Rechte Y-Achse (sekundär)</div>'
             f'<div id="c-axis"><div class="row">{check("speed [km/h]", False)}</div>'
             f'<div class="row">{check("temperature [°C]", True)}</div></div>'
             '<div class="sep"></div><div class="sel">Schließen</div></div>')
    return page(body, "Rechtsklick auf den Graphen Fahrzeug."), marks(
        (1, "#c-name", "left", False), (2, "#c-search", "left", False), (3, "#c-remove", "left", False),
        (4, "#c-colors", "left", False), (5, "#c-default", "left", False), (6, "#c-axis", "left", False),
        (7, "#c-print", "left", False), (8, "#c-legend", "left", False), (9, "#c-comment", "left", False),
        (10, "#p2-comment0", "bottom", False))


def scene_crosslines():
    left = left_panel(LEFT, [("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", True),
                                                       ("voltage [V]", True)], False)])
    ph = plot_h(2, table_h=150)
    x1, x2 = 20.0, 40.0
    s, t, v = SIMPLE["speed"], SIMPLE["temperature"], SIMPLE["voltage"]
    plots = (plot_svg(PLOT_W, ph, "Fahrzeug", [(s, SER[0], "speed [km/h]"), (t, (240, 200, 60), "temperature [°C]")],
                      "time [s]", cross=(x1, x2), pid="p1")
             + plot_svg(PLOT_W, ph, "Bordnetz", [(v, SER[0], "voltage [V]")], "time [s]", "[V]", cross=(x1, x2), pid="p2",
                        limits=[(12.8, SER[0]), (13.95, SER[0])]))
    table = value_table([measure_row("Fahrzeug", s, x1, x2), measure_row("Fahrzeug", t, x1, x2),
                         measure_row("Bordnetz", v, x1, x2, lo=12.8, hi=13.95, ids=("v-min", ""))])
    body = graph_main(plots, left, toolbar(cross=True), table, 150)
    return page(body, "voltage [V]: 3000 Werte."), marks(
        (1, "#t-cross", "bottom", True), (2, "#p1-k1", "center", False), (3, "#p1-k2", "center", False),
        (4, "#v-w1", "top", False), (5, "#splith", "center", True), (6, "#v-min", "bottom", True),
        (7, "#p2-lim0", "center", False))


def scene_datumsachse():
    left = left_panel(LEFT, [("demo_zeitstempel.csv", [], [("Current [A]", True)], False)])
    c = STAMP["Current"]
    ph = plot_h(1, table_h=200)
    x1, x2 = 12.5, 47.25
    row = measure_row("Graph 1", c, x1, x2, date_axis=True, lo=-20.0, prognosis=True, ids=("v-min", ""),
                      target=3600)                             # Zielzeit 1 h: Prognose früher -> verletzt
    plots = plot_svg(PLOT_W, ph, "Graph 1", [(c, SER[0], "Current [A]")], "Datum/Uhrzeit", "[A]", cross=(x1, x2),
                     date_axis=True, epoch=c.x_epoch, pid="p1", limits=[(-20.0, SER[0])], alarm=row.alarm)
    row[-1] = f'<span id="v-prog">{html.escape(row[-1])}</span>'
    table = value_table([row])
    body = graph_main(plots, left, toolbar(cross=True, date=True), table, 200)
    body = body.replace("<td>" + format_wallclock(c.x_epoch + x1), '<td><span id="v-x1">' + format_wallclock(c.x_epoch + x1)) \
               .replace(format_wallclock(c.x_epoch + x1) + "</td>", format_wallclock(c.x_epoch + x1) + "</span></td>", 1)
    dur = format_duration(x2 - x1)
    body = body.replace(f"<td>{dur}</td>", f'<td><span id="v-dx">{dur}</span></td>', 1)
    return page(body, "Current [A]: 3000 Werte."), marks(
        (1, "#t-date", "bottom", True), (2, "#p1-xlabel", "right", True), (3, "#v-x1", "bottom", True),
        (4, "#v-dx", "bottom", True), (5, "#v-min", "bottom", True), (6, "#v-prog", "top", True),
        (7, "#v-target", "bottom", True))


def scene_konfigurator():
    """Grenzwert-Konfigurator mit den Signalen der Prüfstandsdatei und der Beispielkonfiguration."""
    from messgraph import limitconfig
    data = load_file(str(DEMO / "demo_pruefstand.asc"))
    config = limitconfig.load(str(DEMO / "demo_grenzen.yaml"))
    mode = config.modes["EU_AC_3ph_11kW_800V"]
    left = left_panel(LEFT, [("demo_pruefstand.asc", [], [("AC_V_L1", True), ("DUT_TS_01", True)], False)])
    body = graph_main('<div class="dim" style="padding:8px">Noch kein Signal ausgewählt.</div>', left, toolbar())
    x, y, w, h = 300, 70, 1060, 700
    rows = []
    for channel in data.channels[:13]:
        finite = channel.y[np.isfinite(channel.y)]
        lo = fmt(float(finite.min()), channel.unit) if finite.size else "-"
        hi = fmt(float(finite.max()), channel.unit) if finite.size else "-"
        entry = mode.entries.get(channel.name)
        low = "" if entry is None or entry.lower is None else f"{entry.lower:g}"
        up = "" if entry is None or entry.upper is None else f"{entry.upper:g}"
        field = lambda v: (f'<span class="input" style="display:block">{v}</span>' if v
                           else '<span class="input dim" style="display:block">leer = keine</span>')
        rows.append(f'<tr><td>{check("", bool(entry and entry.enabled))}</td><td>{html.escape(channel.name)}</td>'
                    f'<td>demo_pruefstand.asc</td><td>{lo}</td><td>{hi}</td><td>{field(low)}</td><td>{field(up)}</td></tr>')
    rows.append(f'<tr><td>{check("", True)}</td><td class="dim">Signal_nicht_in_Datei (nicht in den Daten)</td><td>-</td>'
                '<td>-</td><td>-</td><td><span class="input" style="display:block">0</span></td>'
                '<td><span class="input" style="display:block">1</span></td></tr>')
    heads = "".join(f"<th>{h_}</th>" for h_ in ("Aktiv", "Signal", "Datei", "Daten min", "Daten max",
                                                 "Untere Grenze", "Obere Grenze"))
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
             '<div class="wtitle">Grenzwert-Konfigurator</div><div style="padding:10px">'
             '<div class="row" id="k-file"><span class="head" style="margin:0">demo_grenzen.yaml  *</span>'
             '<span class="btn">Neu</span><span class="btn">Laden...</span><span class="btn">Speichern</span>'
             '<span class="btn">Speichern unter...</span></div>'
             '<div class="dim">Signale aus den geladenen Dateien. Je Mode: aktiv, untere und obere Grenze sowie steps '
             '(Zielabstand bis zur Grenzverletzung). Änderungen wirken sofort, wenn der Mode im Programm gewählt ist; '
             'Signale ohne aktive Grenze behalten die manuellen Werte.</div><div class="sep"></div>'
             '<div class="row" id="k-mode"><span class="head" style="margin:0">Mode</span>'
             '<span class="combo" style="width:210px">EU_AC_3ph_11kW_800V</span>'
             '<span class="input dim" style="width:150px">Name für neuen Mode</span><span class="btn">Anlegen</span>'
             '<span class="btn">Kopieren</span><span class="btn">Umbenennen</span><span class="btn">Löschen</span></div>'
             '<div class="row" id="k-steps"><span>steps</span><span class="input" style="width:90px">600</span>'
             '<span class="dim">= 600 Schritte</span><span style="color:' + rgb(P["ok"]) + '">wirkt im Programm</span></div>'
             '<div class="row" id="k-filter"><span class="input dim" style="width:200px">Signal suchen</span>'
             f'{check("Nur aktive", False)}<span class="btn">Sichtbare aktivieren</span>'
             '<span class="btn">Sichtbare deaktivieren</span></div>'
             '<div class="row"><span>Grenzen aus Daten vorschlagen:</span><span class="btn">Dieser Mode</span>'
             '<span class="btn">Alle Modes</span><span>Abstand</span><span class="input" id="k-suggest" style="width:70px">10.0 %</span></div>'
             '<div class="dim">14 Signale angezeigt · 9 aktive Signale im Mode, 8 davon in den geladenen Dateien.</div>'
             f'<table class="val" id="k-table" style="margin-top:4px"><tr>{heads}</tr>{"".join(rows)}</table>'
             '</div></div>')
    return page(body, "Mode EU_AC_3ph_11kW_800V: 8 von 9 Signalen der Konfiguration zugeordnet."), marks(
        (1, "#k-file", "right", False), (2, "#k-mode", "right", False), (3, "#k-steps", "right", False),
        (4, "#k-suggest", "right", False), (5, "#k-table", "left", False))


def scene_datenbasen():
    left = left_panel(LEFT, [("Messung_Pruefstand_3.MF4", ["Busrohdaten ohne physikalische Werte: CAN_DataFrame. "
                                                           "Signale entstehen erst durch Dekodierung mit DBC oder "
                                                           "ARXML: Schaltfläche \"Datenbasen...\"."],
                              [("CAN_DataFrame.ID", False), ("CAN_DataFrame.DataBytes", False)], True)])
    body = graph_main('<div class="dim" style="padding:8px">Noch kein Signal ausgewählt.</div>', left, toolbar())
    x, y, w, h = 380, 110, 820, 430

    def row(kind, channel, name):
        combo = f'<span class="combo" style="width:130px">{channel}</span>' if channel else ""
        tag = f'<span style="width:46px;display:inline-block">{kind}</span>' if kind else ""
        return f'<div class="row">{tag}{combo}<span class="btn small">Entfernen</span><span>{name}</span></div>'
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
             '<div class="wtitle">Datenbasen</div><div style="padding:10px">'
             '<div class="head">Datenbasen für Messung_Pruefstand_3.MF4</div>'
             '<div class="dim">Eine Aufzeichnung kann mehrere Datenbasen brauchen: DBC, ARXML, A2L und CDD lassen sich '
             'beliebig kombinieren. Angewendet wird bei Bedarf; Dateien ohne passende Botschaft oder Messgröße werden '
             'nur gemeldet.</div>'
             '<div class="row"><span class="btn" id="d-add">Datenbasen hinzufügen...</span><span class="btn">Alle entfernen</span></div>'
             '<div class="sep"></div>'
             '<div class="head">DBC und ARXML (AUTOSAR): CAN-Botschaften der Aufzeichnung in Signale dekodieren</div>'
             '<div id="d-dbc">' + row("DBC", "CAN 1", "Antrieb.dbc") + row("DBC", "CAN 2", "Ladegeraet.dbc")
             + row("ARXML", "Alle Kanäle", "Fahrzeug_System.arxml") + '</div><div class="sep"></div>'
             '<div class="head">A2L: Einheiten und Umrechnungen für gleichnamige Kanäle</div>'
             '<div id="d-a2l">' + row("", "", "OBC_ECU.a2l") + row("", "", "BMS_ECU.a2l")
             + f'<div class="row">{check("Rohwerte mit der A2L-Umrechnung in physikalische Werte umrechnen", False)}</div></div>'
             '<div class="sep"></div><div class="head">CDD: Diagnosebeschreibung</div>'
             '<div id="d-cdd">' + row("", "", "OBC_Diagnose.cdd") + '</div>'
             '<div class="dim">Die CDD wird zugeordnet und gemerkt. Die Auswertung von Diagnosedaten ist noch nicht eingebaut.</div>'
             '<div class="sep"></div>'
             f'<div class="row" id="d-auto">{check("Neue Busaufzeichnungen (MF4/MDF/BLF) automatisch mit den zuletzt verwendeten Datenbasen dekodieren", True)}</div>'
             '<div style="height:8px"></div>'
             '<div class="row" id="d-apply" style="display:inline-flex"><span class="btn">Zuletzt verwendete übernehmen</span><span class="btn" style="width:110px;'
             'text-align:center">Anwenden</span><span class="btn" style="width:110px;text-align:center">Schließen</span></div>'
             '</div></div>')
    return page(body, "Messung_Pruefstand_3.MF4: 2 Signale."), marks(
        (1, "#d-dbc", "left", False), (2, "#d-add", "left", False), (3, "#d-a2l", "left", False),
        (4, "#d-cdd", "left", False), (5, "#d-apply", "right", False), (6, "#l-db", "right", True),
        (7, "#d-auto", "left", False))


def scene_ansicht():
    left = left_panel(LEFT, [("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", True)], False)])
    ph = plot_h(2)
    plots = (plot_svg(PLOT_W, ph, "Fahrzeug", [(SIMPLE["speed"], SER[0], "speed [km/h]")], "time [s]", "[km/h]", pid="p1")
             + plot_svg(PLOT_W, ph, "Graph 2", [(SIMPLE["temperature"], SER[0], "temperature [°C]")], "time [s]",
                        "[°C]", pid="p2"))
    body = graph_main(plots, left, toolbar())
    body += ('<div class="popup" id="a-menu" style="left:4px;top:24px;width:340px;padding:4px">'
             '<div class="sel">Projekt öffnen...</div><div class="sel">Projekt speichern</div>'
             '<div class="sel hl">Projekt speichern unter...</div>'
             '<div class="sel" id="a-recent">Zuletzt verwendete Projekte &#9656;</div>'
             '<div class="sel">Projekt schließen</div><div class="sep"></div>'
             '<div class="sel">Dateien öffnen...</div><div class="sep"></div><div class="sel">Ansicht speichern...</div>'
             '<div class="sel">Ansicht laden...</div>'
             '<div class="sel">&#10003; Letzte Ansicht beim Start wiederherstellen</div></div>')
    x, y = 400, 150
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:760px;height:345px">'
             '<div class="wtitle">Projekt speichern</div><div style="padding:10px">'
             '<div class="dim">Das Projekt hält alles für die Wiederverwendung: Messdateien mit Pfad, Datenbasen, '
             'ASCII-Struktur, berechnete Signale, Graphen mit Signalen, Farben, Achsen, Grenzen, Legenden und '
             'Bemerkungen, Matrix, Optionen sowie die Einstellungen für Report, Export, Vergleich und Downsampling.</div>'
             '<div style="margin-top:6px">Projektname</div>'
             '<div class="row"><span class="input" id="a-name" style="flex:1">Prüfstand 3</span></div>'
             '<div>Bemerkung</div>'
             '<div class="row"><span class="input" style="flex:1;height:70px;align-items:flex-start">Lauf nach '
             'Software-Update, Vergleich mit Lauf 2</span></div>'
             '<div>Projektdatei (*.mgproj)</div>'
             '<div class="row"><span class="input" id="a-path" style="flex:1">C:\\Users\\Messtechnik\\Pruefstand3\\Pruefstand3.mgproj</span></div>'
             '<div class="dim" id="a-sum">Inhalt: 1 Dateien, 2 Graphen mit 2 Signalen, 0 berechnete Signale, 0 Datenbasen</div>'
             '<div class="dim">Vorhandene Datei wird überschrieben.</div>'
             '<div class="row" style="margin-top:8px;display:inline-flex" id="a-save"><span class="btn" style="width:120px;text-align:center">Speichern</span>'
             '<span class="btn" style="width:120px;text-align:center">Abbrechen</span></div></div></div>')
    return page(body, "Projekt gespeichert."), marks((1, "#a-menu", "right", True), (2, "#a-recent", "right", False),
                                                     (3, "#a-name", "left", False), (4, "#a-path", "right", False),
                                                     (5, "#a-save", "right", False))


def main_window_bg():
    """Hauptfenster im Hintergrund (für Motive mit eigenem Fenster davor)."""
    left = left_panel(LEFT, [("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", False)], False)])
    plots = plot_svg(PLOT_W, plot_h(1), "Graph 1", [(SIMPLE["speed"], SER[0], "speed [km/h]")], "time [s]", "[km/h]",
                     pid="bg1")
    return graph_main(plots, left, toolbar())


def scene_hilfe():
    chapters = ["Überblick", "Installation und Start", "Dateien öffnen", "Datenerkennung", "Zeitformate",
                "Signale und Graphen", "Kontextmenü im Graphen", "Messen mit Markern", "Datum/Uhrzeit-Achse",
                "Datenbasen (DBC, ARXML, A2L, CDD)", "Signale berechnen", "Dateien vergleichen", "Drucken, Export und Report", "Downsampling", "Fensterbereiche anpassen", "Projekte und Ansichten",
                "Hilfe, PDF und Screenshots", "Fehlerbehebung"]
    items = "".join(f'<div class="sel{" hl" if i == 6 else ""}">{html.escape(c)}</div>' for i, c in enumerate(chapters))
    body = (main_window_bg() + '<div class="window" style="left:110px;top:70px;right:110px;bottom:40px">'
            '<div class="wtitle">Hilfe</div><div style="position:absolute;top:36px;left:8px;right:8px;bottom:8px;display:flex;gap:8px">'
            '<div class="panel" style="width:280px">'
            '<div class="row"><span class="btn" id="h-pdf" style="flex:1;text-align:center">Als PDF speichern...</span></div>'
            '<div class="row"><span class="btn" id="h-shots" style="flex:1;text-align:center">Screenshots erzeugen</span></div>'
            f'<div class="sep"></div><div class="head">Inhalt</div><div class="panel" id="h-toc" style="padding:4px">{items}</div></div>'
            '<div class="panel" style="flex:1;padding:14px">'
            '<div class="head" style="font-size:15px">Kontextmenü im Graphen</div><div class="sep"></div>'
            '<div style="max-width:900px">Ein Rechtsklick auf einen Graphen (ohne die Maus zu ziehen) öffnet sein '
            'Kontextmenü. Ein Klick außerhalb oder "Schließen" schließt es.</div>'
            '<img id="h-img" src="@@KONTEXT_IMG@@" style="width:620px;margin:10px 0;border:1px solid #444">'
            '<div class="dim">Bild 5: Kontextmenü - nummerierte Markierungen, Erklärung darunter</div>'
            '<div style="margin-top:8px">&bull; 1 Name des Graphen</div><div>&bull; 2 Signal suchen und hinzufügen</div>'
            '<div>&bull; 3 Signal entfernen</div></div></div></div>')
    return page(body, "Hilfe."), marks(
        (1, "#m-lang", "bottom", True), (6, "#m-hilfe", "bottom", True), (2, "#h-pdf", "right", False), (3, "#h-shots", "right", False),
        (4, "#h-toc", "right", True), (5, "#h-img", "inside", False))

def scene_allefiles():
    runs = [load_file(str(DEMO / f"demo_lauf_{i}.csv")) for i in (1, 2, 3)]
    left = left_panel(LEFT, [(d.name, [], [(c.label, True) for c in d.channels if c.name == "Temperatur"], False)
                             for d in runs], search="temp",
                      multi=("Treffer in mehreren Dateien: 1 Signal(e)", "Temperatur",
                             "in 2 von 3 Dateien, 2 davon angezeigt"))
    series = []
    for i, d in enumerate(runs):
        for ch in d.channels:
            if ch.name == "Temperatur":
                series.append((ch, SER[i], f"{ch.label} - {d.name}"))
    plots = plot_svg(PLOT_W, plot_h(1), "Graph 1", series, "time [s]", "[°C]", pid="p1")
    body = graph_main(plots, left, toolbar())
    return page(body, "Temperatur: 2 Dateien in einem gemeinsamen Graphen."), marks(
        (1, "#l-search", "right", False), (2, "#l-mcombo", "right", False), (3, "#l-mbtn", "right", False),
        (4, "#l-minfo", "right", False))


def scene_ascii():
    from messgraph.csv_reader import preview
    path = DEMO / "demo_pruefstand.asc"
    result = preview(str(path))
    left = left_panel(LEFT, [("demo_pruefstand.asc", [], [("AC_V_L1", False), ("AC_I_L1", False), ("HVDC_V", False)],
                              False)])
    rows = []
    for number, line in enumerate(result.lines[:13], 1):
        text = line if len(line) <= 92 else line[:92] + " ..."
        mark, colour = "   ", ""
        if result.header_span[0] <= number <= result.header_span[1]:
            mark, colour = "K> ", f"color:{rgb(P['heading'])};font-weight:600"
        elif number == result.data_line:
            mark, colour = "D> ", f"color:{rgb(P['ok'])}"
        rows.append(f'<div style="{colour};white-space:pre">{mark}{number:>4} | {html.escape(text)}</div>')
    names = ", ".join(result.names[:16]) + f" ... und {len(result.names) - 16} weitere"
    x, y, w, h = 300, 150, 980, 430
    body = graph_main("", left, toolbar())
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
             '<div class="wtitle">ASCII-Import</div><div style="padding:10px">'
             '<div class="head">ASCII-Import: demo_pruefstand.asc</div>'
             '<div class="dim">Anfang der Datei (Zeilennummern wie im Editor). Markiert: Kopfzeile, Einheitenzeile, '
             'erste Datenzeile. Zusatzinformationen wie &lt;{Continue}&gt; werden ignoriert, die Fortsetzung gehört '
             'zur vorigen Zeile.</div>'
             f'<div id="a-lines" style="border:1px solid {rgb(P["frame"])};padding:6px;margin:6px 0;'
             'font-family:Consolas,monospace;font-size:12px;height:205px;overflow:hidden">' + "".join(rows) + '</div>'
             '<div class="row"><span id="a-head" style="display:inline-flex;gap:8px;align-items:center"><span>Kopfzeile</span>'
             '<span class="input" style="width:80px">0</span></span>'
             '<span>Einheitenzeile</span><span class="input" style="width:80px">0</span>'
             '<span id="a-sep" style="display:inline-flex;gap:8px;align-items:center"><span>Trennzeichen</span>'
             '<span class="combo" style="width:110px">Automatisch</span><span>Dezimalzeichen</span>'
             '<span class="combo" style="width:100px">Automatisch</span></span></div>'
             f'<div id="a-result"><div>Kopfzeile: Zeilen {result.header_span[0]}-{result.header_span[1]}  |  Daten ab '
             f'Zeile {result.data_line}  |  {len(result.names)} Spalten  |  Trennzeichen: Komma, Dezimalzeichen: .  |  '
             f'{result.removed} Zusatzinformation(en) entfernt</div>'
             f'<div class="dim">Signale: {html.escape(names)}</div></div>'
             f'<div class="row">{check("Als Vorlage für weitere ASCII-Dateien (asc, txt, dat ...) verwenden", False)}</div>'
             '<div class="row" id="a-btn" style="display:inline-flex"><span class="btn">Übernehmen und einlesen</span>'
             '<span class="btn">Automatisch</span><span class="btn">Schließen</span></div>'
             '</div></div>')
    return page(body, "demo_pruefstand.asc: 51 Signale."), marks(
        (1, "#a-lines", "left", False), (2, "#a-head", "left", False), (3, "#a-sep", "right", False),
        (4, "#a-result", "left", False), (5, "#a-btn", "right", False), (6, "#l-ascii0", "bottom", True))


def scene_vergleich():
    from messgraph import compare
    runs = [load_file(str(DEMO / f"demo_lauf_{i}.csv")) for i in (1, 2, 3)]
    others = ["demo_einfach.csv", "demo_zeitstempel.csv"]
    left = left_panel(LEFT, [(d.name, [], [(c.label, False) for c in d.channels], False) for d in runs[:2]])
    body = graph_main('<div class="dim" style="padding:8px">Noch kein Signal ausgewählt.</div>', left, toolbar())
    signals = ["Drehzahl", "Strom", "Spannung", "Temperatur"]
    result = compare.compute(runs, signals, compare.STATS)
    files = "".join(f'<div style="margin:3px 0">{check(f"{d.name}  ({round(compare.group_similarity(d, runs) * 100)} % gleiche Signalnamen)", True)}</div>'
                    for d in runs) + "".join(f'<div style="margin:3px 0">{check(n + "  (0 % gleiche Signalnamen)")}</div>' for n in others)
    union = compare.signal_union(runs)
    sigs = "".join(f'<div style="margin:3px 0">{check(n if c == 3 else f"{n}  (in {c} von 3 Dateien)", n in signals)}</div>'
                   for n, c in union)
    head = "".join(f"<th>{html.escape(h)}</th>" for h in ["Signal", "%", "Kennwert"] + result.files)
    tol = {"Strom": "4", "Spannung": "1"}
    rows = []
    for i, r in enumerate(result.rows):
        first = i == 0 or result.rows[i - 1].signal != r.signal
        flags = compare.deviations(r.values, compare.parse_percent(tol.get(r.signal, "")))
        signal_red = any(any(compare.deviations(o.values, compare.parse_percent(tol.get(o.signal, ""))))
                         for o in result.rows if o.signal == r.signal)
        name = f"{r.signal} [{r.unit}]" if first else ""
        name_html = f'<span style="color:#ff5555">{html.escape(name)}</span>' if signal_red else html.escape(name)
        pct = (f'<span class="input"{" id=v-pct" if r.signal == "Strom" else ""} style="display:inline-block;'
               f'min-width:50px;padding:1px 6px">{tol[r.signal]}</span>' if r.signal in tol else
               '<span class="input" style="display:inline-block;min-width:50px;padding:1px 6px">'
               '<span class="dim">%</span></span>') if first else ""
        vals = "".join(f'<td{" style=color:#ff5555" if bad else ""}>{html.escape(compare.format_value(v) or "-")}</td>'
                       for v, bad in zip(r.values, flags))
        style = ' class="bad"' if any(flags) else ""
        rows.append(f"<tr{style}{" id=v-red" if any(flags) and "v-red" not in "".join(rows) else ""}><td>{name_html}</td><td>{pct}</td><td>{html.escape(r.stat)}</td>{vals}</tr>")
    x, y, w, h = 300, 130, 1000, 690
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
             '<div class="wtitle">Dateien vergleichen</div><div style="padding:10px">'
             '<div style="display:flex;gap:14px"><div style="width:430px">'
             '<div class="head">Dateien</div><div class="row" id="v-fbtn" style="display:inline-flex"><span class="btn small">Ähnliche wählen</span>'
             '<span class="btn small">Alle</span><span class="btn small">Keine</span></div>'
             f'<div class="panel" id="v-files" style="height:150px">{files}</div>'
             '<div class="head" style="margin-top:8px">Kennwerte</div>'
             f'<div class="row" id="v-stats" style="display:inline-flex">{check("Mittelwert (avg)", True)}{check("Minimum (min)", True)}{check("Maximum (max)", True)}</div>'
             '</div><div style="flex:1">'
             '<div class="head">Signale</div><div class="row" id="v-filter"><span class="input" style="width:220px">'
             '<span class="dim">Signal suchen</span></span><span class="btn small">Alle</span><span class="btn small">Keine</span>'
             f'{check("nur gemeinsame")}</div><div class="panel" id="v-sigs" style="height:190px">{sigs}</div></div></div>'
             '<div class="row" id="v-actions" style="margin-top:8px"><span class="btn">Vergleichen</span>'
             '<span class="btn">In Zwischenablage kopieren</span><span class="input" style="width:300px">'
             'C:\\Messungen\\MessGraph_Vergleich.csv</span><span class="btn">CSV speichern</span><span class="btn">Schließen</span></div>'
             '<div class="dim">4 Signale x 3 Dateien verglichen.  3 Zeilen mit Abweichung über der Toleranz (Strom).  - = Signal fehlt in der Datei oder hat keine gültigen Werte.</div>'
             f'<div class="panel" id="v-table" style="margin-top:6px;height:330px;padding:0"><table class="val"><tr>{head}</tr>'
             f'{"".join(rows)}</table></div></div></div>')
    return page(body, "demo_lauf_3.csv: 4 Signale. 3 Dateien mit ähnlichem Aufbau: Vergleich über \"Dateien vergleichen...\"."), marks(
        (1, "#v-files", "left", True), (2, "#v-fbtn", "right", False), (3, "#v-stats", "right", False),
        (4, "#v-filter", "top", False), (5, "#v-sigs", "right", True), (6, "#v-actions", "right", False),
        (7, "#v-table", "left", True), (8, "#t-cmp", "right", True), (9, "#v-pct", "right", True),
        (10, "#v-red", "right", True))

def scene_drucken():
    left = left_panel(LEFT, [("demo_einfach.csv", [], [("speed [km/h]", True), ("temperature [°C]", True),
                                                       ("voltage [V]", True)], False)])
    ph = plot_h(2)
    plots = (plot_svg(PLOT_W, ph, "Fahrzeug", [(SIMPLE["speed"], SER[0], "speed [km/h]"),
                                               (SIMPLE["temperature"], (240, 200, 60), "temperature [°C]")],
                      "time [s]", "[km/h]", pid="p1", legend_pos="ne")
             + plot_svg(PLOT_W, ph, "Bordnetz", [(SIMPLE["voltage"], SER[0], "voltage [V]")], "time [s]", "[V]", pid="p2"))
    body = graph_main(plots, left, toolbar())
    x, y, w = 470, 300, 620
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px">'
             '<div class="wtitle">Drucken und Export</div><div style="padding:10px">'
             '<div class="head">Alle Graphen drucken / exportieren</div>'
             '<div>Ausgabe</div><div class="row" id="e-target" style="display:inline-flex">'
             '<span>○ Drucker</span><span>● PDF-Datei</span><span>○ SVG-Vektorgrafik</span></div>'
             '<div class="row"><span>Ausrichtung</span><span class="combo" id="e-orient" style="width:130px">Automatisch</span></div>'
             '<div class="row"><span>Papier</span><span class="combo" id="e-paper" style="width:60px">A4</span></div>'
             '<div class="row"><span>Datei</span><span class="input" id="e-path" style="flex:1">'
             'C:\\Messungen\\MessGraph_Graphen.pdf</span></div>'
             '<div class="row" style="margin-top:10px"><span class="btn" id="e-run">Ausführen</span>'
             '<span class="btn">Abbrechen</span></div></div></div>')
    return page(body, "Rechtsklick > Alle Graphen drucken / exportieren..."), marks(
        (1, "#e-target", "right", True), (2, "#e-orient", "right", True), (3, "#e-paper", "right", True),
        (4, "#e-path", "bottom", True), (5, "#e-run", "bottom", True), (6, "#p1-legend", "left", True))

def scene_berechnen():
    from messgraph import formula
    run = load_file(str(DEMO / "demo_lauf_1.csv"))
    power = formula.add_or_replace(run, formula.compute(run, "Leistung", "kW", "{Strom} * {Spannung} / 1000"))
    signals = [(c.label if not c.formula else "= " + c.label, c is power) for c in run.channels]
    left = left_panel(LEFT, [(run.name, [], signals, False)])
    ph = plot_h(1)
    plots = plot_svg(PLOT_W, ph, "Graph 1", [(power, SER[0], power.label)], "time [s]", "[kW]", pid="p1")
    body = graph_main(plots, left, toolbar())
    x, y, w = 380, 130, 780
    names = "".join(f'<option>{html.escape(c.name)}</option>' for c in run.channels)
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px">'
             '<div class="wtitle">Signal berechnen</div><div style="padding:10px">'
             f'<div class="head">Signal berechnen: {run.name}</div>'
             '<div class="panel" id="k-list" style="height:70px">'
             '<div>Berechnete Signale: 1 von 10</div>'
             '<div class="row"><span class="btn small">Bearbeiten</span><span class="btn small">Löschen</span>'
             f'<span>{html.escape(power.label)} = {html.escape(power.formula)}</span></div></div>'
             '<div class="head" style="margin-top:6px">Neues Signal</div>'
             '<div class="row" id="k-name"><span>Name</span><span class="input" style="width:200px">Widerstand</span>'
             '<span>Einheit</span><span class="input" style="width:100px"><span class="dim">automatisch</span></span></div>'
             '<div class="row"><span>Art</span><span>&#9673; Formel</span><span>&#9675; Fourier-Analyse</span></div>'
             '<div>Formel</div><div class="row"><span class="input" id="k-formula" style="flex:1">'
             '{Spannung} / {Strom}</span></div>'
             '<div class="row"><span>Bemerkung</span><span class="input" style="flex:1">Innenwiderstand der Quelle</span></div>'
             '<div class="row" id="k-tools" style="display:inline-flex"><span class="combo" style="width:240px">Strom</span>'
             '<span class="btn">Signal einfügen</span><span class="btn">&nbsp;+&nbsp;</span><span class="btn">&nbsp;-&nbsp;</span>'
             '<span class="btn">&nbsp;*&nbsp;</span><span class="btn">&nbsp;/&nbsp;</span><span class="btn">&nbsp;(&nbsp;</span>'
             '<span class="btn">&nbsp;)&nbsp;</span></div>'
             '<div class="dim" style="white-space:normal">Signale in geschweiften Klammern, Zahlen direkt: '
             '({U1} + {U2}) / 2, {Strom} * {Spannung} * 0.001. Verschiedene Zeitachsen werden auf die des ersten '
             'Signals interpoliert.</div>'
             '<div class="row" style="margin-top:8px"><span class="btn" id="k-run">Berechnen und hinzufügen</span>'
             '<span class="btn">Neu</span><span id="k-def" style="display:inline-flex;gap:6px">'
             '<span class="btn">Definition speichern...</span><span class="btn">Definition laden...</span></span>'
             '<span class="btn">Schließen</span></div></div></div>')
    return page(body, f"{power.label} berechnet ({power.y.size:,} Werte).".replace(",", ".")), marks(
        (1, "#l-calc0", "right", True), (2, "#k-list", "right", True), (3, "#k-name", "right", True),
        (4, "#k-formula", "right", True), (5, "#k-tools", "right", True), (6, "#k-run", "bottom", True),
        (7, f"#l-sig0-{len(run.channels) - 1}", "right", True), (8, "#k-def", "bottom", True))


def scene_fourier():
    """Grundsignal in Graph 1 mit Markern um die 1. Schwingung, Harmonische dieser Schwingung als Balken in Graph 2."""
    from messgraph import fourier
    t = np.arange(0, 0.1, 1e-4)
    on = np.where(t >= 0.04, 1.0, 0.0)                      # Oberwellen erst ab der 3. Schwingung
    u = 325 * np.sin(2 * np.pi * 50 * t) + on * (60 * np.sin(2 * np.pi * 150 * t) + 30 * np.sin(2 * np.pi * 250 * t))
    res = fourier.compute(t, u, "s", fourier.parse("FFT({U_L1}; h=1..15; f0=auto; y=pct)"))
    info = res["info"]
    m1, m2 = 0.0402, 0.0698                                 # 2,01 .. 3,49 Schwingungen -> 3. Schwingung
    energy, chosen = fourier.select(info, m1, m2)
    part = fourier.display(energy, "pct")
    base = _Sig("U_L1", "V", t, u)
    harm = _Sig("Harmonische U_L1", "%", res["x"], np.array([part[int(n) - 1] for n in res["x"]]))
    harm.bars = True
    ph = plot_h(2)
    plots = (plot_svg(PLOT_W, ph, "Graph 1", [(base, SER[0], "U_L1 [V]")], "Zeit [s]", "[V]", cross=(m1, m2), pid="p1")
             + plot_svg(PLOT_W, ph, "Graph 2", [(harm, SER[1], "Harmonische U_L1 [%]")], "Harmonische", "[%]",
                        pid="p2"))
    left = left_panel(LEFT, [("netz_messung.csv", [], [("U_L1 [V]", True), ("I_L1 [A]", False),
                                                      ("= Harmonische U_L1 [%]", True)], False)])
    body = graph_main(plots, left, toolbar(cross=True))
    x, y, w = 900, 520, 480
    body += (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px">'
             '<div class="wtitle">Signal berechnen</div><div style="padding:8px;font-size:12px">'
             '<div class="row" id="f-name"><span>Name</span><span class="input" style="width:170px">Harmonische U_L1</span>'
             '<span>Einheit</span><span class="input" style="width:70px"><span class="dim">automatisch</span></span></div>'
             '<div class="row" id="f-kind"><span>Art</span><span>&#9675; Formel</span><span>&#9673; Fourier-Analyse</span></div>'
             '<div class="row" id="f-sig"><span>Signal</span><span class="combo" style="width:150px">U_L1</span>'
             '<span>Fenster</span><span class="combo" style="width:100px">Automatisch</span></div>'
             '<div class="row" id="f-mode"><span>&#9673; Harmonische</span><span>&#9675; Frequenzbereich</span>'
             '<span>Anzeige</span><span class="combo" style="width:110px">Anteil [%]</span></div>'
             '<div class="row" id="f-range"><span class="dim">Frequenz von</span><span class="input" style="width:50px">0</span>'
             '<span class="dim">bis</span><span class="input" style="width:50px"><span class="dim">max</span></span><span class="dim">Hz</span></div>'
             '<div class="row" id="f-harm"><span>Harmonische von</span><span class="combo" style="width:40px">1</span>'
             '<span>bis</span><span class="combo" style="width:40px">15</span><span>f0</span>'
             '<span class="input" style="width:50px">auto</span><span>Hz</span></div>'
             '<div>Formel: FFT({U_L1}; h=1..15; f0=auto; y=pct)</div>'
             '<div class="row" style="margin-top:6px"><span class="btn" id="f-run">Berechnen und hinzufügen</span>'
             '<span class="btn">Schließen</span></div></div></div>')
    status = (f"Harmonische U_L1 berechnet ({res['x'].size} Werte). Grundfrequenz f0 = {info['f0']:.6g} Hz. "
              f"Periodisch: ja, {info['periods']} ganze Perioden. Auswahl (Marker): Periode {chosen[0]} "
              f"(1 von {info['periods']}): H1 = {part[0]:.1f} %, H3 = {part[2]:.1f} %, H5 = {part[4]:.1f} %.")
    return page(body, status), marks(
        (1, "#f-name", "left", True), (2, "#f-kind", "left", True), (3, "#f-sig", "left", True),
        (4, "#f-mode", "left", True), (5, "#f-range", "left", True), (6, "#f-harm", "left", True),
        (7, "#f-run", "bottom", True), (8, "#p1-k1", "top", False), (9, "#p2-legend", "right", True))


# ------------------------------------------------------------------ Limiter und Auto-Auswertung
class _Sig:
    """Kanal-Ersatz für plot_svg (x, y, Name, Einheit)."""

    def __init__(self, name, unit, x, y):
        self.name, self.unit, self.x, self.y = name, unit, np.asarray(x, float), np.asarray(y, float)
        self.label = f"{name} [{unit}]" if unit else name


def _b64(path):
    import base64
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def scene_limiter():
    """Limiter-Fenster: obere Phase des Rechtecksignals gilt für alle Signale der Datei."""
    from messgraph import limiter
    data = {c.name: c for c in load_file(str(DEMO / "demo_rechteck.csv")).channels}
    rect, current = data["Rechteck"], data["Strom"]
    guide = [(rect.x, limiter.mask(rect.y, 4.5, None))]
    share = limiter.kept_share(guide)
    rx, ry = limiter.apply(rect.x, rect.y, guide)
    cx, cy = limiter.apply(current.x, current.y, guide)
    h2 = plot_h(2)
    plots = (plot_svg(PLOT_W, h2, "Graph 1", [(_Sig("Rechteck", "V", rx, ry), SER[0], "Rechteck [V]")], "Zeit [s]", "[V]",
                      pid="lim1")
             + plot_svg(PLOT_W, h2, "Graph 2", [(_Sig("Strom", "A", cx, cy), SER[1], "Strom [A]")], "Zeit [s]", "[A]",
                        pid="lim2"))
    hint = f"Limiter: {share * 100:.1f} % der Messzeit im Limit".replace(".", ",")
    left = left_panel(LEFT, [("demo_rechteck.csv", [], [("Rechteck [V]", True), ("Strom [A]", True),
                                                       ("Temperatur [°C]", False)], False)])
    left = left.replace('<div style="margin:3px 0"><span id="l-sig0-0">',
                        f'<div id="l-limhint" style="color:{rgb(P["heading"])};margin-bottom:4px">{hint}</div>'
                        '<div style="margin:3px 0"><span id="l-sig0-0">', 1)
    body = graph_main(plots, left, toolbar(cross=False))
    rows = (f'<tr><td>{check("", True)}</td><td><span class="combo" style="display:block">demo_rechteck.csv</span></td>'
            '<td><span class="combo" style="display:block">Rechteck</span></td>'
            '<td><span class="input" style="display:block">4,5</span></td>'
            '<td><span class="input dim" style="display:block">-</span></td><td><span class="btn small">Löschen</span></td></tr>'
            f'<tr><td>{check("", False)}</td><td><span class="combo" style="display:block">*</span></td>'
            '<td><span class="combo" style="display:block">Temperatur</span></td>'
            '<td><span class="input dim" style="display:block">-</span></td>'
            '<td><span class="input" style="display:block">80</span></td><td><span class="btn small">Löschen</span></td></tr>')
    heads = "".join(f"<th>{x}</th>" for x in ("Aktiv", "Datei", "Signal", "Limit min", "Limit max", ""))
    body += ('<span id="lim-gap" style="position:absolute;left:556px;top:600px;width:2px;height:2px"></span>'
             '<div class="window" style="left:430px;top:120px;width:900px;height:320px">'
             '<div class="wtitle">Limiter</div><div style="padding:10px">'
             f'<div class="row" id="lim-top">{check("Limiter aktiv", True)}<span class="btn small">Laden...</span>'
             '<span class="btn small">Speichern</span><span class="btn small">Speichern unter...</span>'
             '<span class="dim">C:\\MessGraph\\Test\\Limiter.yaml</span></div>'
             '<div class="dim" style="white-space:normal">Je Regel: Datei, Führungssignal, untere und obere Grenze '
             '(leer = keine). Angezeigt werden nur die Abschnitte, in denen das Signal in seinen Grenzen liegt - für ALLE '
             'Signale dieser Datei. Mehrere Regeln einer Datei gelten gleichzeitig (UND). Datei * = alle Dateien mit diesem '
             'Signal, Muster wie lauf_*.csv sind möglich.</div><div class="sep"></div>'
             '<div class="row"><span class="btn" id="lim-add">Regel hinzufügen</span><span class="dim">2 Regeln, 1 wirksam</span></div>'
             f'<table class="val" id="lim-table"><tr>{heads}</tr>{rows}</table>'
             f'<div id="lim-result" style="margin-top:10px;color:{rgb(P["heading"])}">demo_rechteck.csv: {hint}</div>'
             '</div></div>')
    return page(body, "Limiter geladen: 2 Regeln aus Limiter.yaml.").replace(
        '<span id="m-limiter">', '<span id="m-limiter" style="outline:1px solid #e07020">', 1), marks(
        (1, "#m-limiter", "bottom", True), (2, "#lim-top", "right", False), (3, "#lim-add", "left", False),
        (4, "#lim-table", "left", True), (5, "#lim-result", "right", False), (6, "#l-limhint", "right", True),
        (7, "#lim-gap", "center", False))


def _auto_window(x, y, w, h, extra=""):
    def head(n, title, state, text, hid=""):
        return (f'<div class="sep"></div><div class="row" id="{hid}" style="margin:2px 0"><span style="color:{rgb(P["heading"])}">'
                f'Schritt {n}: {title}</span><span class="dim">{state}</span></div>'
                f'<div class="dim" style="white-space:normal;font-size:12px">{text}</div>')
    lock = ' style="opacity:.45"'
    err = rgb(P["error"]) if "error" in P else "#e05050"
    return (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
            '<div class="wtitle">Auto-Auswertung</div><div style="padding:8px 10px;font-size:13px">'
            '<div class="dim" style="white-space:normal">Ablauf: 1 Auswertung festlegen -&gt; 2 Modes und Zielzeiten -&gt; '
            '3 Analysieren und Grenzen prüfen -&gt; 4 Zyklus starten. Abgeschlossene Schritte sind gesperrt, bis der '
            'Durchlauf gestartet oder Zurücksetzen gedrückt wird.</div>'
            f'<div class="row" id="a-steps"><span class="btn small">Zurücksetzen</span><span style="color:{rgb(P["heading"])}">'
            'Aktuell: Schritt 2 - Modes und Zielzeiten</span></div>'
            + head(1, "Auswertung festlegen", "[erledigt - gesperrt]", "1. Name eingeben und mit Anlegen bestätigen - oder "
                   "bei leerem Namen eine vorhandene Auswertung wählen. 2. Verzeichnisregel wählen oder mit Verzeichnisregel "
                   "verwalten... anlegen.")
            + '<table style="width:100%;border-collapse:collapse">'
            + f'<tr><td style="width:150px">Name</td><td><div class="row" style="margin:0" id="a-name"><span{lock} class="input" '
              f'style="width:300px">HTOE_22kW_DV</span><span{lock} class="btn small">Anlegen</span></div></td></tr>'
            + f'<tr><td>Auswertung</td><td><div class="row" style="margin:0" id="a-eval"><span{lock} class="combo" '
              f'style="width:276px">HTOE_22kW_DV</span><span{lock} class="btn small">Löschen</span></div></td></tr>'
            + f'<tr><td>Verzeichnisregel</td><td><div class="row" style="margin:0" id="a-rule"><span{lock} class="combo" '
              f'style="width:276px">HTOE_22kW_DV</span><span{lock} class="btn small">Verzeichnisregel verwalten...</span>'
              '</div></td></tr>'
            + '<tr><td>Regel (Info)</td><td><div class="dim" id="a-info" style="white-space:pre;font-size:12px">'
              'Quellverzeichnis: Z:\\DV_Restart2\\HTOE_22kW\\Halle_D_Setup\n'
              'Zielverzeichnis: C:\\MessGraph\\_TestResult\\{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx}\n'
              'Einlesen: 2 Dateien ausgeschlossen\n6 Zielordner (6 aktiv), 3 Modes</div></td></tr>'
            + '</table>'
            + head(2, "Modes und Zielzeiten", "[jetzt]", "Häkchen = Mode verarbeiten, dahinter die Zielzeit hh:mm:ss (gilt "
                   "für alle DUTs des Modes). Nicht angehakte Modes brauchen keine Zielzeit.", "a-step2")
            + '<div class="row" style="margin:2px 0"><span class="btn small" id="a-modes">Modes und Zielzeiten...</span>'
              f'<span style="color:{rgb(P["heading"])}">3 Modes, 1 ohne Zielzeit</span></div>'
            + '<div class="panel" id="a-popup" style="position:absolute;left:150px;top:500px;width:560px;font-size:12px;'
              'box-shadow:0 0 14px #000">'
              '<div class="wtitle" style="margin:-8px -8px 6px -8px">Modes und Zielzeiten</div>'
              '<div class="dim">Häkchen = verarbeiten; Zielzeit hh:mm:ss (z. B. 24:00:00, 07:18:26)</div>'
              '<div class="row"><span class="btn small">Alle</span><span class="btn small">Keine</span>'
              '<span class="input" style="width:80px">24:00:00</span><span class="btn small">für alle angehakten</span></div>'
              '<div>&#9662; AC (2)</div>'
              f'<div class="row" style="margin-left:18px">{check("AC_22kW_3ph_615V", True)}<span class="input" style="width:70px">24:00:00</span><span>2 DUT</span></div>'
              f'<div class="row" style="margin-left:18px">{check("AC_11kW_1ph_230V", False)}<span class="input dim" style="width:70px">&nbsp;</span><span>2 DUT</span></div>'
              '<div>&#9662; DC_Charge (1)</div>'
              f'<div class="row" style="margin-left:18px">{check("DC_Charge_V2L_540V", True)}<span class="input" style="width:70px">&nbsp;</span>'
              f'<span>2 DUT</span><span style="color:{err}">Zielzeit fehlt</span></div>'
              '<div>&#9662; Precon (1)</div>'
              f'<div class="row" style="margin-left:18px">{check("Precon", True)}<span class="input" style="width:70px">07:18:26</span><span>2 DUT</span></div>'
              '<div class="row"><span>Eigener Mode</span><span class="input" style="width:150px">AC_22kW_3ph_900V</span>'
              '<span class="input" style="width:60px">12:00:00</span><span class="btn small">Hinzufügen</span></div>'
              '<div class="row"><span class="btn small">Schließen</span></div></div>'
            + head(3, "Analysieren und Grenzen prüfen", "[folgt]", "Analysieren liest alle Dateien und schlägt je Mode "
                   "Grenzen vor; im Grenzwert-Konfigurator prüfen und speichern.")
            + f'<div class="row" id="a-step3"><span{lock} class="btn small" id="a-analyze">Analysieren</span>'
              f'<span{lock} class="btn small">Grenzwert-Konfigurator...</span><span{lock} class="btn small">Limiter bearbeiten...</span>'
              f'<span{lock} class="btn small">Grenzen neu vorschlagen</span></div>'
            + head(4, "Zyklus starten", "[folgt]", "Zykluszeit, Ausgaben, Start/Stopp, Fortschritt, Zähler und Log stehen "
                   "in einem eigenen Fenster; es öffnet sich beim Abschließen von Schritt 3.")
            + f'<div class="row" id="a-run"><span{lock} class="btn small">Fenster Schritt 4 öffnen...</span></div>'
            '</div></div>')


def _auto_run_window(x, y, w, h):
    lock = ""
    def field(label, value, fid="", buttons="", locked=False):
        return (f'<tr><td style="width:140px">{label}</td><td><div class="row" style="margin:0">'
                f'<span class="input" id="{fid}" style="flex:1">{html.escape(value)}</span>{buttons}</div></td></tr>')
    rows = [("DV", "Precon_DUT2", "Precon", "DES2026090904705001", "18:12:40", "24:00:00", "75.9 %", "error"),
            ("DV", "Precon_DUT3", "Precon", "DES2026090904705002", "26:03:10", "24:00:00", "108.6 %", "ok")]
    trs = "".join(f'<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td><td>{f_}</td>'
                  f'<td style="color:{rgb(P[r])}">{g}</td></tr>' for a, b, c, d, e, f_, g, r in rows)
    extra = ""
    return (f'<div class="window" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;box-shadow:0 0 18px #000">'
            '<div class="wtitle">Auto-Auswertung - Schritt 4: Zyklus starten</div><div style="padding:8px 10px;font-size:13px">'
            '<div class="dim" style="white-space:normal">Zykluszeit und Ausgaben festlegen, dann Start (zyklisch, nur neue '
            'Daten) oder Jetzt ausführen. Schritte 1 bis 3 bleiben im Fenster Auto-Auswertung.</div>'
            f'<div class="row"><span style="color:{rgb(P["heading"])}">Schritt 4: Zyklus starten</span><span class="dim">[jetzt]</span></div>'
            + '<table style="width:100%;border-collapse:collapse">'
            + f'<tr><td style="width:140px">Zykluszeit</td><td><div class="row" style="margin:0" id="a-cycle"><span{lock} '
              f'class="input" style="width:70px">2m</span>{check("PNG je Signal", True)}{check("nur Modes mit Treffern", True)}</div></td></tr>'
            + field("Ergebnisdatei (alle)", "Time_counter.json", "a-json",
                    buttons=f'<span{lock} class="btn small">Standard</span>', locked=True)
            + '<tr><td></td><td class="dim">= C:\\MessGraph\\_TestResult\\Time_counter.json</td></tr>'
            + '</table>'
            f'<div class="row" id="a-buttons"><span{lock} class="btn small">Start</span><span class="btn small">Stopp</span>'
            f'<span{lock} class="btn small">Jetzt ausführen</span><span class="btn small">Log anzeigen</span>'
            '<span class="btn small">Report erstellen...</span></div>'
            '<div class="row" id="a-progress"><span style="flex:1;height:18px;background:'
            f'{rgb(P["frame"]) if "frame" in P else "#ccc"};border:1px solid {rgb(P["border"])};position:relative">'
            f'<span style="position:absolute;left:0;top:0;bottom:0;width:38%;background:{rgb(P["check"])}"></span>'
            '<span style="position:absolute;left:8px;top:1px;font-size:12px">Analysiere 3/4: DC_800V_250A_DUT1</span>'
            '</span><span class="btn small">Abbrechen</span></div>'
            '<table class="val" id="a-table" style="font-size:11px"><tr><th>Auswertung</th><th>DUT / Teil</th><th>Mode</th>'
            f'<th>Gruppe</th><th>Ist</th><th>Ziel</th><th>Erfüllung</th></tr>{trs}</table>{extra}'
            '</div></div>')
def scene_auto():
    body = main_window_bg() + _auto_window(40, 40, 760, 800) + _auto_run_window(820, 300, 560, 430)
    return page(body, "Auto: 2 Auswertungen, 2 Dateien neu, 160 Bilder, 2 Zähler, Ergebnis C:\\MessGraph\\_TestResult\\"
                      "Time_counter.json").replace('<span id="m-auto">', '<span id="m-auto" style="outline:1px solid #e07020">', 1), marks(
        (1, "#m-auto", "bottom", True), (2, "#a-steps", "right", True), (3, "#a-name", "right", True),
        (4, "#a-eval", "right", True), (5, "#a-rule", "right", True), (6, "#a-info", "right", True),
        (7, "#a-modes", "left", True), (8, "#a-popup", "right", True), (9, "#a-step3", "right", True),
        (10, "#a-run", "left", True), (11, "#a-buttons", "left", True), (12, "#a-table", "bottom", True))


def _auto_example(tmp):
    """Beispieldaten (drei DUTs, je 6 h) durch die Auto-Auswertung schicken: PNG, statistics.json, Report."""
    from datetime import datetime, timedelta
    from messgraph import auto, autoreport, limitconfig
    rng = np.random.default_rng(3)
    cfg = limitconfig.new_config("Precon_725V")
    mode = cfg.modes["Precon_725V"]
    mode.set_entry("HVDC_V", True, 715, 735)
    mode.set_entry("Clnt_T", True, 0, 75)
    mode.set_entry("Test_Mode", True, 16.15, 17.85)
    mode.set_steps("24h")
    jobs = []
    for k, dut in enumerate((2, 3, 5)):
        src = Path(tmp) / f"src{dut}"
        src.mkdir(parents=True, exist_ok=True)
        t0 = datetime(2026, 6, 9, 8, 0, 0)
        lines = ["Zeit,HVDC_V [V],Clnt_T [°C],Test_Mode,HVDC_I [A]"]
        for i in range(0, 6 * 3600, 20):
            h = i / 3600
            lines.append(f"{t0 + timedelta(seconds=i):%Y-%m-%d %H:%M:%S},{725 + np.sin(i / 600) * 3 + k:.2f},"
                         f"{42 + h * (1.5 + 1.6 * k) + rng.normal(0, .3):.2f},17,{250 + rng.normal(0, 1.5):.1f}")
        (src / f"HTOE_PV_DES20260909047050017{k + 5}_Precon_725V_DUT{dut}_001.csv").write_text("\n".join(lines))
        engine = auto.AutoEngine(auto.AutoSettings(source=str(src), target=str(Path(tmp) / f"out{dut}")))
        engine.run_cycle(cfg, mode="Precon_725V")
        jobs.append({"name": f"Precon_725V_DUT{dut}", "target": str(Path(tmp) / f"out{dut}")})
    duts, _ = autoreport.collect(jobs)
    pdf = autoreport.build_report(str(Path(tmp) / "Report_Precon_725V.pdf"), duts,
                                  autoreport.ReportOptions(project="OneBox", mode="Precon_725V"))
    return jobs, pdf


_EXAMPLE = {}


def _example():
    if not _EXAMPLE:
        import tempfile
        tmp = tempfile.mkdtemp(prefix="mg_auto_")
        _EXAMPLE["jobs"], _EXAMPLE["pdf"] = _auto_example(tmp)
    return _EXAMPLE


def scene_autograph():
    """Ein PNG der Auto-Auswertung mit Grenzlinien, Trendlinie, Textblock und rotem Hintergrund."""
    ex = _example()
    png = next(Path(ex["jobs"][2]["target"]).glob("*/Clnt_T_C.png"))
    body = (f'<div style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;background:#fff">'
            f'<img src="{_b64(png)}" style="width:{W}px;height:{int(W * 900 / 1600)}px;display:block">'
            '<div style="padding:16px 24px;font-size:14px;color:#333">Einzelgraph aus der Auto-Auswertung '
            '(Zielverzeichnis\\&lt;Gruppe&gt;\\Clnt_T_C.png): Violation vor Zielzeit, deshalb rot hinterlegt.</div>'
            '<span id="g-lim" style="position:absolute;left:700px;top:88px;width:2px;height:2px"></span>'
            '<span id="g-low" style="position:absolute;left:700px;top:646px;width:2px;height:2px"></span>'
            '<span id="g-trend" style="position:absolute;left:965px;top:100px;width:2px;height:2px"></span>'
            '<span id="g-info" style="position:absolute;left:1068px;top:45px;width:315px;height:305px"></span>'
            '<span id="g-bg" style="position:absolute;left:250px;top:520px;width:2px;height:2px"></span>'
            '<span id="g-target" style="position:absolute;left:1074px;top:283px;width:300px;height:60px"></span></div>')
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    return doc, marks((1, "#g-lim", "center", False), (2, "#g-low", "center", False), (3, "#g-trend", "center", False),
                      (4, "#g-info", "inside", False), (5, "#g-target", "left", True), (6, "#g-bg", "center", False))


def scene_report():
    body = main_window_bg()
    jobs = "".join(f'<div style="margin:3px 0">{check(f"Precon_725V_DUT{d}   (C:\\Projekt_Daten\\DV_HTOE22kW\\Precon_725V\\DUT{d})", d != 5)}</div>'
                   for d in (2, 3, 5))

    def row(label, value, rid="", buttons=""):
        cls = "input" if value else "input dim"
        return (f'<tr><td style="width:140px">{label}</td><td><div class="row" style="margin:0">'
                f'<span class="{cls}" id="{rid}" style="flex:1">{value or "&nbsp;"}</span>{buttons}</div></td></tr>')
    body += ('<div class="window" style="left:280px;top:60px;width:840px;height:740px">'
             '<div class="wtitle">Report erstellen</div><div style="padding:10px">'
             '<div class="dim" style="white-space:normal">Report aus den PNG und Kennwerten der gewählten Auswertungen '
             '(je Auswertung ein DUT): Deckblatt, Summary Comparison, Signal Plot Comparison und je DUT Tabelle und Graphen.</div>'
             '<div class="row"><span>Auswertung</span><span class="input" style="width:280px">DV_HTOE22kW &#9662;</span></div>'
             '<div class="row"><span>Auswertungen (DUTs)</span><span class="btn small">Alle</span><span class="btn small">Keine</span></div>'
             f'<div class="panel" id="r-list" style="height:110px;padding:6px">{jobs}</div>'
             '<table style="width:100%;border-collapse:collapse;margin-top:6px">'
             + row("Titel", "Test Report", "r-title") + row("Projekt", "OneBox", "r-project")
             + row("Mode", '<span class="dim">leer = je Report der Mode seiner Auswertungen</span>', "r-mode")
             + row("Ausgabeordner", "C:\\Projekt_Daten\\DV_HTOE22kW", "r-path",
                   '<span class="btn small">Wählen...</span>')
             + f'<tr><td>Wasserzeichen</td><td><span id="r-wm">{check(chr(34) + "NOT RELEASED" + chr(34) + " auf jeder Seite", True)}</span></td></tr>'
             + '</table><div class="sep"></div>'
             f'<div class="row"><span id="r-sched">{check("Zeitplan: Report automatisch zu festen Uhrzeiten", True)}</span></div>'
             '<div class="row" id="r-times"><span>Uhrzeiten</span><span class="input" style="width:200px">00:00:00, 12:00:00</span>'
             '<span class="combo" style="width:100px">täglich</span>'
             '</div>'
             f'<div id="r-next" style="color:{rgb(P["heading"])}">Nächster Report: 17.11.2026 00:00:00 (täglich)</div>'
             '<div class="row" style="margin-top:8px"><span class="btn" id="r-create" style="width:150px;text-align:center">'
             'Report erstellen</span></div>'
             '<div class="row" id="r-progress"><span style="flex:1;height:20px;border:1px solid '
             f'{rgb(P["border"])};position:relative"><span style="position:absolute;left:0;top:0;bottom:0;width:62%;'
             f'background:{rgb(P["check"])}"></span><span style="position:absolute;left:8px;top:2px">62 %  1/2 Precon_725V: DUT3: Bilder</span>'
             '</span></div>'
             '<div>2 Reports werden erstellt: Report_Precon_725V_20261116_151230.pdf, Report_DC_800V_20261116_151230.pdf</div>'
             '</div></div>')
    return page(body, "Report: 2 DUTs, wird erstellt...").replace(
        '<span id="m-auto">', '<span id="m-auto" style="outline:1px solid #e07020">', 1), marks(
        (1, "#r-list", "left", True), (2, "#r-title", "left", True), (3, "#r-path", "left", True),
        (4, "#r-wm", "right", True), (5, "#r-sched", "right", True), (6, "#r-times", "left", False),
        (7, "#r-next", "left", False), (8, "#r-create", "right", False), (9, "#r-progress", "left", True))


def scene_reportseite():
    """Zwei Seiten des Beispiel-Reports: Summary Comparison und Signal Plot Comparison."""
    import shutil
    import subprocess
    import tempfile
    ex = _example()
    if not shutil.which("pdftoppm"):
        raise RuntimeError("pdftoppm fehlt")
    tmp = tempfile.mkdtemp(prefix="mg_rep_")
    pics = []
    for number in (2, 3):
        base = Path(tmp) / f"s{number}"
        subprocess.run(["pdftoppm", "-f", str(number), "-l", str(number), "-r", "80", "-png", "-singlefile",
                        ex["pdf"], str(base)], check=True)
        pics.append(base.with_suffix(".png"))
    width = (W - 60) // 2
    imgs = "".join(f'<img id="rp{i}" src="{_b64(p)}" style="width:{width}px;border:1px solid #999;margin:0 10px">'
                   for i, p in enumerate(pics))
    body = (f'<div style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;background:#e9ebee;padding-top:120px">'
            f'<div style="display:flex;justify-content:center">{imgs}</div>'
            '<div style="padding:24px 30px;font-size:14px;color:#333">Beispiel-Report (A4 quer): links Summary Comparison, '
            'rechts Signal Plot Comparison; "NOT RELEASED" als Wasserzeichen.</div>'
            '<span id="rp-table" style="position:absolute;left:65px;top:197px;width:362px;height:72px"></span>'
            '<span id="rp-pct" style="position:absolute;left:428px;top:197px;width:103px;height:72px"></span>'
            '<span id="rp-lim" style="position:absolute;left:538px;top:197px;width:107px;height:72px"></span>'
            '<span id="rp-grid" style="position:absolute;left:755px;top:215px;width:575px;height:118px"></span>'
            '<span id="rp-wm" style="position:absolute;left:985px;top:470px;width:2px;height:2px"></span></div>')
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    return doc, marks((1, "#rp-table", "top", True), (2, "#rp-pct", "bottom", True), (3, "#rp-lim", "top", True),
                      (4, "#rp-grid", "bottom", True), (5, "#rp-wm", "center", False))


def scene_verzeichnis():
    body = main_window_bg()

    def head(n, title, text=""):
        return (f'<div class="sep" style="margin:4px 0"></div><span style="color:{rgb(P["heading"])}">Schritt {n}: {title}</span>'
                + (f' <span class="dim" style="font-size:11px">{text}</span>' if text else ""))
    tree = ('<div class="panel" id="d-tree" style="padding:4px 8px;font-size:12px;height:118px">'
            '<div>&#9662; DUT1 (14)</div><div style="margin-left:14px">&#9656; Logs (1)</div>'
            '<div style="margin-left:14px">&#9662; Report (13)</div>'
            '<div style="margin-left:28px">&#9662; AC_22kW_3ph_615V (4) &#9662; Files (4)</div>'
            f'<div style="margin-left:42px">{check("alle Dateien dieses Ordners (3/4)", True)}</div>'
            f'<div style="margin-left:42px">{check("HTOE_PV_DES202507230117500132_AC_22kW_3ph_615V_DUT1_001.csv", True)}</div>'
            f'<div style="margin-left:42px">{check("HTOE_PV_DES202507230117500132_AC_22kW_3ph_615V_DUT1_002.csv", False)}</div>'
            '<div>&#9656; DUT2 (14)</div></div>')
    ph = [("{Mode}", "AC_22kW_3ph_615V, DC_Charge_V2L_540V, Precon", ""), ("{Testlauf}", "DV", "PV"),
          ("{Test-Variante}", "HTOE_22kW", ""), ("{Seriennummer}", "DES202507230117500132, DES202507230117500133", ""),
          ("{DUTx}", "DUT1, DUT2", ""), ("{Datetime}", "Systemzeit beim ersten Speichern", ""), ("{Name}", "HTOE_22kW_DV", "")]
    pht = ('<table id="d-ph" style="width:100%;border-collapse:collapse;font-size:12px"><tr class="dim"><td>Platzhalter</td>'
           '<td>erkannt</td><td>eigener Wert (optional)</td><td></td></tr>'
           + "".join(f'<tr><td>{a}</td><td>{b}</td><td><span class="input" style="display:inline-block;width:110px">'
                     f'{c or "&nbsp;"}</span></td><td><span class="btn small">einfügen</span></td></tr>' for a, b, c in ph)
           + '</table>')
    rows = [("PV_HTOE_22kW\\AC_22kW_3ph_615V\\DUT1", "AC_22kW_3ph_615V", "DUT1", "3 (-1)", "neu", True),
            ("PV_HTOE_22kW\\AC_22kW_3ph_615V\\DUT2", "AC_22kW_3ph_615V", "DUT2", "4", "neu", True),
            ("PV_HTOE_22kW\\Precon\\DUT1", "Precon", "DUT1", "4", "vorhanden (Precon_DUT1)", True),
            ("PV_HTOE_22kW\\Precon\\DUT2", "Precon", "DUT2", "4", "neu", False),
            ("DUT1\\Logs", "-", "DUT1", "1", "{Mode}: kein Wert (eigenen Wert eintragen)", None)]
    table = ('<table style="width:100%;border-collapse:collapse;font-size:12px"><tr class="dim"><td></td><td>Zielordner</td>'
             '<td>Mode</td><td>DUT / Seriennummer</td><td>Dateien</td><td>Status</td></tr>')
    for key, mode, dut, files, status, ok in rows:
        box = "-" if ok is None else check("", ok)
        table += (f'<tr><td>{box}</td><td>...\\_TestResult\\{key}</td><td>{mode}</td><td>{dut}</td><td>{files}</td>'
                  f'<td>{status}</td></tr>')
    table += '</table>'
    body += ('<div class="window" style="left:110px;top:34px;width:1180px;height:812px;font-size:13px">'
             '<div class="wtitle">Verzeichnisverwalter</div><div style="padding:6px 10px">'
             '<div class="row" id="d-rule"><span>Name der Regel</span><span class="input" style="width:200px">HTOE_22kW_DV</span>'
             '<span>Vorhandene Regel bearbeiten</span><span class="combo" style="width:180px">&nbsp;</span>'
             '<span class="btn small">Regel löschen</span></div>'
             f'<div id="d-state" style="color:{rgb(P["heading"])}">NEUE Regel HTOE_22kW_DV wird definiert.</div>'
             + head(1, "Quellordner", "Ordner wählen und Struktur analysieren")
             + '<div class="row" id="d-root"><span class="input" style="flex:1">Z:\\DV_Restart2\\HTOE_22kW\\Halle_D_Setup</span>'
               '<span class="btn small">Wählen...</span><span class="btn small">Struktur analysieren</span></div>'
               '<div class="dim" style="font-size:12px">8 Ordner mit 28 Messdateien. Ebene 1: DUT1, DUT2 -&gt; {DUTx} | '
               'Ebene 2: Logs, Report | Ebene 3: AC_22kW_3ph_615V, DC_Charge_V2L_540V, Precon -&gt; {Mode} | Ebene 4: Files</div>'
             + head(2, "Daten auswählen", "Standard: alle aktiv; zu ignorierende Dateien abhaken")
             + '<div class="row"><span class="btn small">Alle</span><span class="btn small">Keine</span>'
               f'<span style="color:{rgb(P["heading"])}">28 Dateien, 2 ausgeschlossen</span></div>' + tree
             + head(3, "Basis Zielordner")
             + '<div class="row" id="d-base"><span class="input" style="flex:1">C:\\Users\\defiscm\\Desktop\\Meine_Tools\\'
               'MessGraph\\_TestResult</span><span class="btn small">Wählen...</span></div>'
             + head(4, "Platzhalter und erweiterter Zielordner", "aus den Unterordnern erkannt, eigene Werte möglich")
             + pht
             + '<div class="row" id="d-template"><span>Erw. Zielordner</span><span class="input" style="flex:1">'
               '{Testlauf}_{Test-Variante}\\{Mode}\\{DUTx}</span></div>'
             + head(5, "Zielordner")
             + f'<div id="d-target" style="color:{rgb(P["heading"])}">Zielordner = C:\\...\\_TestResult\\{{Testlauf}}_{{Test-Variante}}'
               '\\{Mode}\\{DUTx} &nbsp; Beispiel: C:\\...\\_TestResult\\PV_HTOE_22kW\\AC_22kW_3ph_615V\\DUT1</div>'
             + head(6, "Vorschau prüfen")
             + f'<div class="row"><span class="btn small">Vorschau aktualisieren</span><span class="btn small">Alle</span>'
               f'<span class="btn small">Keine</span><span style="color:{rgb(P["heading"])}">6 Zielordner, 5 gewählt</span></div>'
             + f'<div class="panel" id="d-table" style="padding:4px 8px">{table}</div>'
             '<div class="dim" style="font-size:12px">Nur neue Daten werden synchronisiert und bearbeitet: Vorhandene '
             'Auswertungen behalten ihre gelesenen Daten, neue Ordner und Dateien kommen hinzu.</div>'
             '<div class="row"><span class="btn" id="d-save">Regel speichern</span></div>'
             '</div></div>')
    return page(body, "Regel HTOE_22kW_DV gespeichert: 5 Zielordner (angelegt bzw. vorhanden).").replace(
        '<span id="m-auto">', '<span id="m-auto" style="outline:1px solid #e07020">', 1), marks(
        (1, "#d-rule", "right", True), (2, "#d-state", "right", True), (3, "#d-root", "left", True),
        (4, "#d-tree", "left", True), (5, "#d-base", "left", True), (6, "#d-ph", "left", True),
        (7, "#d-template", "left", True), (8, "#d-target", "left", True), (9, "#d-table", "left", True),
        (10, "#d-save", "right", True))


SCENES = {"uebersicht": scene_uebersicht, "dateiliste": scene_dateiliste, "browser": scene_browser,
          "matrix": scene_matrix, "kontextmenue": scene_kontextmenue, "crosslines": scene_crosslines,
          "datumsachse": scene_datumsachse, "konfigurator": scene_konfigurator, "datenbasen": scene_datenbasen, "allefiles": scene_allefiles, "zeilen": scene_zeilen, "vorschlag": scene_vorschlag, "ascii": scene_ascii, "ansicht": scene_ansicht, "vergleich": scene_vergleich, "drucken": scene_drucken, "berechnen": scene_berechnen, "fourier": scene_fourier,
          "hilfe": scene_hilfe, "limiter": scene_limiter, "auto": scene_auto, "autograph": scene_autograph,
          "report": scene_report, "reportseite": scene_reportseite, "verzeichnis": scene_verzeichnis}


def main(only=None):
    import base64
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page_ = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for name, build in SCENES.items():
            if only and name not in only:
                continue
            content, specs = build()
            if "@@KONTEXT_IMG@@" in content:  # Hilfe-Motiv zeigt das Kontextmenü-Bild
                data = base64.b64encode((OUT / "kontextmenue.png").read_bytes()).decode()
                content = content.replace("@@KONTEXT_IMG@@", "data:image/png;base64," + data)
            page_.set_content(content)
            page_.evaluate(MARK_JS, specs)
            page_.screenshot(path=str(OUT / f"{name}.png"))
            print("erzeugt:", OUT / f"{name}.png")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:] or None)
