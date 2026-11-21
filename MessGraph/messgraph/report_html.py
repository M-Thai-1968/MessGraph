"""Dynamischer Messbericht als eigenständige HTML-Datei (läuft in jedem Browser, ohne Internet).

Gleicher Inhalt wie der PDF-Report (Deckblatt-Angaben, Inhalt, Übersicht, je Graph Grafik, Signalspiegel,
Bemerkung, Tabellen). Zusätzlich: Ein Klick auf eine Kurve, einen Eintrag im Signalspiegel oder eine
Tabellenzeile hebt dieses Signal im Kapitel hervor; alle anderen Kurven, Einträge und Zeilen werden hellgrau.
Strg/Umschalt-Klick wählt mehrere Signale, erneuter Klick hebt die Wahl auf, Esc hebt alles auf.
"""
from __future__ import annotations

import html
from dataclasses import replace
from pathlib import Path

from .i18n import t
from .plotexport import SvgCanvas, render_plot
from .report import ReportData

PLOT_W, PLOT_H = 960.0, 540.0

CSS = """
:root { --text:#1c2026; --dim:#5f6670; --line:#d9dce1; --head:#1f5f99; --bg:#ffffff; --panel:#f5f6f8;
        --gray:#d3d3d3; --gray-text:#b9bcc1; --sel:#fff6d6; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 "Segoe UI", Helvetica, Arial, sans-serif; }
header { padding:28px 32px 18px; border-bottom:3px solid var(--head); }
header h1 { margin:0 0 4px; font-size:28px; color:var(--head); }
header .sub { color:var(--dim); }
.wrap { display:flex; align-items:flex-start; }
nav { position:sticky; top:0; width:250px; flex:none; max-height:100vh; overflow:auto; padding:18px 16px;
      border-right:1px solid var(--line); background:var(--panel); }
nav h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--dim); margin:0 0 8px; }
nav a { display:block; color:var(--text); text-decoration:none; padding:3px 6px; border-radius:4px; }
nav a:hover { background:#e6ebf2; }
main { flex:1; min-width:0; padding:8px 32px 48px; max-width:1180px; }
section { padding-top:18px; border-bottom:1px solid var(--line); padding-bottom:22px; }
h2 { color:var(--head); font-size:22px; margin:10px 0 10px; }
h3 { color:var(--head); font-size:15px; margin:18px 0 6px; }
.hint { color:var(--dim); font-size:12.5px; margin:0 0 8px; }
.tools { float:right; }
.tools button { font:inherit; font-size:12.5px; padding:3px 10px; border:1px solid var(--line); background:var(--panel);
                border-radius:4px; cursor:pointer; }
svg.plot { width:100%; height:auto; display:block; border:1px solid var(--line); border-radius:4px; }
g.sig, g.sig * { cursor:pointer; }
polyline.hit { pointer-events:stroke; }
ul.legend { list-style:none; padding:0; margin:4px 0 0; display:grid; grid-template-columns:repeat(auto-fill, minmax(min(300px, 100%), 1fr));
            gap:2px 18px; }
ul.legend li { display:flex; align-items:center; gap:8px; padding:2px 6px; border-radius:4px; cursor:pointer;
               overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
ul.legend li:hover, tr[data-key]:hover td { background:#eef2f7; }
.sw { width:18px; height:3px; flex:none; border-radius:2px; }
.tw { overflow-x:auto; }
table { border-collapse:collapse; width:100%; margin:4px 0 6px; font-size:13px; }
th, td { border:1px solid var(--line); padding:4px 7px; text-align:left; vertical-align:top; }
th { background:var(--panel); }
tr[data-key] { cursor:pointer; }
.note { color:var(--dim); font-size:12.5px; margin:4px 0; }
.comment { white-space:pre-wrap; background:var(--panel); border-left:3px solid var(--head); padding:6px 10px; }
/* Hervorhebung: alles außer den gewählten Signalen hellgrau */
section.focus g.sig:not(.on) polyline:not(.hit) { stroke:var(--gray) !important; }
section.focus g.sig.on polyline:not(.hit) { stroke-width:1.8px; }
section.focus ul.legend li:not(.on) { color:var(--gray-text); }
section.focus ul.legend li:not(.on) .sw { background:var(--gray) !important; }
section.focus ul.legend li.on { font-weight:600; background:var(--sel); }
section.focus tr[data-key]:not(.on) td { color:var(--gray-text); }
section.focus tr[data-key].on td { background:var(--sel); font-weight:600; }
tr.alarm td { background:#ffcdcd; }
section.focus tr.alarm.on td { background:#ffb4b4; }
@media (max-width:820px) { nav { display:none; } main { padding:8px 16px 40px; } header { padding:20px 16px 14px; } }
@media print { nav, .hint, .tools { display:none; } main { max-width:none; padding:0 8px; }
               section { break-inside:auto; } svg.plot { break-inside:avoid; } }
"""

JS = """
(function () {
  function apply(section) {
    var keys = section._keys || [];
    section.classList.toggle('focus', keys.length > 0);
    section.querySelectorAll('[data-key]').forEach(function (el) {
      el.classList.toggle('on', keys.indexOf(el.getAttribute('data-key')) >= 0);
    });
    var info = section.querySelector('.selinfo');
    if (info) { info.textContent = keys.length ? info.getAttribute('data-sel').replace('{n}', keys.length) : ''; }
  }
  document.querySelectorAll('section.graph').forEach(function (section) {
    section._keys = [];
    section.addEventListener('click', function (ev) {
      var el = ev.target.closest('[data-key]');
      if (!el || !section.contains(el)) { return; }
      var key = el.getAttribute('data-key'), keys = section._keys, at = keys.indexOf(key);
      if (ev.ctrlKey || ev.metaKey || ev.shiftKey) {
        if (at >= 0) { keys.splice(at, 1); } else { keys.push(key); }
      } else {
        section._keys = (at >= 0 && keys.length === 1) ? [] : [key];
      }
      apply(section);
    });
    var reset = section.querySelector('button.reset');
    if (reset) { reset.addEventListener('click', function () { section._keys = []; apply(section); }); }
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') {
      document.querySelectorAll('section.graph').forEach(function (s) { s._keys = []; apply(s); });
    }
  });
})();
"""


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in rgb[:3])


def _table(headers, rows, keys=None, alarm=frozenset()) -> str:
    out = ['<div class="tw"><table><thead><tr>', "".join(f"<th>{_e(h)}</th>" for h in headers), "</tr></thead><tbody>"]
    for index, row in enumerate(rows):
        key = keys[index] if keys and index < len(keys) and keys[index] else ""
        attr = f' data-key="{_e(key)}"' if key else ""
        if key and key in alarm:
            attr += ' class="alarm"'                     # Zielzeit verletzt
        out.append(f"<tr{attr}>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _plot_svg(spec) -> str:
    canvas = SvgCanvas(PLOT_W, PLOT_H)
    canvas.rect(0, 0, PLOT_W, PLOT_H, fill=(255, 255, 255))
    render_plot(canvas, replace(spec, legend="none"), 0, 0, PLOT_W, PLOT_H, 11.0)
    return (f'<svg class="plot" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PLOT_W:.0f} {PLOT_H:.0f}" '
            f'role="img" aria-label="{_e(spec.title)}">' + "".join(canvas.parts) + "</svg>")


def build_html_report(path: str, data: ReportData, language: str = "de") -> str:
    if not path.lower().endswith((".html", ".htm")):
        path += ".html"
    toc = [("overview", t("Übersicht"))] + [(f"g{n}", f"{n}  {g.title}") for n, g in enumerate(data.graphs, 1)]
    sub = [t("Dynamischer Messbericht")]
    if data.author:
        sub.append(t("Erstellt von: {name}", name=data.author))
    sub.append(t("Erstellt am: {date}", date=data.created))
    sub.append(t("Dateien: {count}, Graphen: {graphs}", count=len(data.files), graphs=len(data.graphs)))
    parts = [f'<!DOCTYPE html><html lang="{_e(language)}"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             f"<title>{_e(data.title)}</title><style>{CSS}</style></head><body>",
             f'<header><h1>{_e(data.title)}</h1><div class="sub">{" · ".join(_e(s) for s in sub)}</div></header>',
             f'<div class="wrap"><nav><h2>{_e(t("Inhalt"))}</h2>',
             "".join(f'<a href="#{a}">{_e(text)}</a>' for a, text in toc), "</nav><main>"]
    # Übersicht
    parts.append(f'<section id="overview"><h2>{_e(t("Übersicht"))}</h2>')
    if data.comment.strip():
        parts.append(f'<h3>{_e(t("Bemerkung"))}</h3><div class="comment">{_e(data.comment.strip())}</div>')
    parts.append(f'<h3>{_e(t("Messdateien"))}</h3>')
    parts.append(_table([t("Datei"), t("Ordner"), t("Signale"), t("Startzeit"), t("Format")], data.files))
    if data.settings:
        parts.append(f'<h3>{_e(t("Einstellungen"))}</h3>' + _table([t("Einstellung"), t("Wert")], data.settings))
    parts.append(f'<h3>{_e(t("Graphen"))}</h3>')
    parts.append(_table(["#", t("Graph"), t("Signale")],
                        [[i + 1, g.title, ", ".join(s.label for s in g.spec.series)] for i, g in enumerate(data.graphs)]))
    parts.append("</section>")
    hint = t("Klick auf eine Kurve, einen Eintrag im Signalspiegel oder eine Tabellenzeile hebt das Signal hervor; "
             "Strg-Klick wählt mehrere, erneuter Klick oder Esc hebt die Wahl auf.")
    selected = t("{n} Signal(e) hervorgehoben")
    for number, graph in enumerate(data.graphs, 1):
        parts.append(f'<section class="graph" id="g{number}"><h2>{number}&nbsp; {_e(graph.title)}</h2>')
        parts.append(f'<p class="hint"><span class="tools"><span class="selinfo" data-sel="{_e(selected)}"></span> '
                     f'<button class="reset" type="button">{_e(t("Alle zeigen"))}</button></span>{_e(hint)}</p>')
        parts.append(_plot_svg(graph.spec))
        if graph.spec.series:
            parts.append(f'<h3>{_e(t("Signalspiegel"))}</h3><ul class="legend">')
            for s in graph.spec.series:
                label = s.label + (t(" (rechte Achse)") if s.right else "")
                attr = f' data-key="{_e(s.key)}"' if s.key else ""
                parts.append(f'<li{attr} title="{_e(label)}"><span class="sw" style="background:{_hex(s.rgb)}"></span>'
                             f"{_e(label)}</li>")
            parts.append("</ul>")
        if graph.comment.strip():
            parts.append(f'<h3>{_e(t("Bemerkung"))}</h3><div class="comment">{_e(graph.comment.strip())}</div>')
        for index, (heading, headers, rows) in enumerate(graph.tables):
            if rows:
                keys = graph.row_keys[index] if index < len(graph.row_keys) else None
                parts.append(f"<h3>{_e(heading)}</h3>" + _table(headers, rows, keys, graph.alarm_keys))
        for note in graph.notes:
            parts.append(f'<p class="note">{_e(note)}</p>')
        parts.append("</section>")
    parts.append(f"</main></div><script>{JS}</script></body></html>\n")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(parts), encoding="utf-8")
    return path
