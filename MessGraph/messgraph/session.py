"""Ansicht speichern und laden: Dateien, Datenbasen, Graphen, Namen, Farben und Optionen."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .data_model import Dataset, LoadError
from .i18n import t
from .databases import DatabaseConfig, apply_databases, install_databases
from .layout import MAX_GRAPHS, GraphSlot, PlotLayout, normalize_spans
from .data_model import find_channel
from .loaders import _mf4_entries, load_file
from . import formula, progress

FORMAT = "MessGraph-Ansicht"
VERSION = 1
SUFFIX = ".mgraph"


def build_session(datasets: list[Dataset], layout: PlotLayout, options: dict, base_dir: str | None = None) -> dict:
    files = []
    for ds in datasets:
        entry = {"path": os.path.abspath(ds.path)}
        if base_dir:
            try:
                entry["relpath"] = os.path.relpath(ds.path, base_dir)
            except ValueError:  # Windows: anderes Laufwerk
                pass
        config = ds.extra.get("config")
        if config is not None and not config.empty:
            entry["databases"] = config.to_dict()
        if ascii_options(ds):
            entry["ascii"] = ascii_options(ds)
        calc = [{"name": c.name, "unit": c.unit, "formula": c.formula, "comment": c.note} for c in ds.channels if c.formula]
        if calc:
            entry["computed"] = calc
        files.append(entry)
    graphs = []
    for slot in layout.slots:
        graphs.append({
            "title": slot.title,
            "cross": [c if c is None else float(c) for c in slot.cross],
            "cross3": None if slot.cross3 is None else float(slot.cross3),
            "legend": slot.legend,
            "log_x": bool(slot.log_x),
            "log_y": bool(slot.log_y),
            "note": slot.note,
            "comments": [[float(x), float(y), str(text)] for x, y, text in slot.comments],
            "signals": [{"file": os.path.abspath(ch.source), "name": ch.name,
                         "color": list(slot.colors[ch]) if ch in slot.colors else None,
                         "axis": "right" if ch in slot.right else "left",
                         "limits": slot.limits.get(ch, [None, None]),
                         "target": slot.targets.get(ch)} for ch in slot.signals],
        })
    return {"format": FORMAT, "version": VERSION, "files": files,
            "matrix": list(layout.matrix) if layout.matrix else None,
            "spans": layout.spans if layout.matrix and layout.spans else None, "graphs": graphs, "options": options}


def ascii_options(ds: Dataset) -> dict | None:
    """Vom Nutzer festgelegte ASCII-Struktur (Kopfzeile ...) oder None bei automatischer Erkennung."""
    options = (ds.extra.get("ascii") or {}).get("options")
    return options if options and any(options.values()) else None


def write_session(path: str, data: dict) -> str:
    if not path.lower().endswith(SUFFIX):
        path += SUFFIX
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_session(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise LoadError(t("Ansicht nicht lesbar: {error}", error=exc)) from exc
    except ValueError as exc:
        raise LoadError(t("Ansicht ist keine gültige JSON-Datei: {error}", error=exc)) from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise LoadError(t("Die Datei ist keine gespeicherte MessGraph-Ansicht."))
    if int(data.get("version", 0)) > VERSION:
        raise LoadError(t("Die Ansicht stammt aus einer neueren MessGraph-Version."))
    return data


def _resolve(entry: dict, base_dir: str | None) -> str | None:
    for candidate in (entry.get("path"), entry.get("relpath") and base_dir and os.path.join(base_dir, entry["relpath"])):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def open_session(data: dict, base_dir: str | None) -> tuple[list[Dataset], dict, list[str]]:
    """Im Hintergrund: Dateien laden, Datenbasen anwenden, angezeigte Kanäle laden.

    Liefert (Datasets, Abbildung gespeicherter Pfad -> Dataset, Meldungen).
    """
    datasets, by_saved, problems = [], {}, []
    files = data.get("files", [])
    signals = [sig for graph in data.get("graphs", []) for sig in graph.get("signals", [])]
    total = max(1, len(files) + len(signals))   # Fortschritt: je Datei und je angezeigtem Signal ein Teil
    done = 0
    try:
        for entry in files:
            saved = os.path.abspath(entry.get("path", ""))
            path = _resolve(entry, base_dir)
            with progress.section(done / total, (done + 1) / total,
                                  t("Datei {number} von {count}: {name}", number=done + 1, count=len(files),
                                    name=Path(entry.get("path", "?")).name)):
                done += 1
                if path is None:
                    problems.append(t("Datei fehlt: {path}", path=entry.get("path")))
                    continue
                try:
                    ds = load_file(path, entry.get("ascii"))
                    config = DatabaseConfig.from_dict(entry.get("databases"))
                    if not config.empty and ("mdf" in ds.extra or "blf" in ds.extra):
                        progress.busy(t("Datenbasen anwenden..."))
                        install_databases(ds, config, apply_databases(ds, config, set(), _mf4_entries, ds.extra.get("start")))
                    for calc in entry.get("computed", [])[:formula.MAX_COMPUTED]:   # berechnete Signale neu bilden
                        try:
                            made = formula.add_or_replace(ds, formula.compute(ds, calc.get("name", ""),
                                                                              calc.get("unit", ""), calc.get("formula", "")))
                            made.note = str(calc.get("comment") or "")
                        except progress.Cancelled:
                            raise
                        except LoadError as exc:
                            problems.append(t("{file}: berechnetes Signal {name}: {error}", file=Path(path).name,
                                              name=calc.get("name", "?"), error=exc))
                except progress.Cancelled:
                    raise
                except LoadError as exc:
                    problems.append(f"{Path(path).name}: {exc}")
                    continue
                datasets.append(ds)
                by_saved[saved] = ds
                by_saved[os.path.abspath(path)] = ds
        for sig in signals:
            with progress.section(done / total, (done + 1) / total, t("Signal {name}", name=sig.get("name", "?"))):
                done += 1
                ds = by_saved.get(os.path.abspath(sig.get("file", "")))
                channel = find_channel(ds.channels, sig.get("name")) if ds else None
                if channel is None:
                    continue
                try:
                    channel.load()
                except progress.Cancelled:
                    raise
                except LoadError as exc:
                    problems.append(str(exc))
    except progress.Cancelled:
        for ds in datasets:  # abgebrochen: nichts halb Geladenes zurücklassen
            ds.close()
        raise
    return datasets, by_saved, problems


def restore_layout(data: dict, by_saved: dict) -> tuple[PlotLayout, list[str]]:
    layout = PlotLayout()
    missing = []
    slots = []
    for graph in data.get("graphs", [])[:MAX_GRAPHS]:
        slot = GraphSlot(title=str(graph.get("title", "")))
        cross = graph.get("cross") or [None, None]
        slot.cross = [None if c is None else float(c) for c in list(cross)[:2]] + [None] * (2 - len(cross[:2]))
        slot.cross3 = None if graph.get("cross3") is None else float(graph["cross3"])
        slot.note = str(graph.get("note") or "")
        for item in graph.get("comments") or []:
            try:
                x, y, text = float(item[0]), float(item[1]), str(item[2])
            except (TypeError, ValueError, IndexError):
                continue
            if text.strip():
                slot.comments.append([x, y, text])
        slot.log_x, slot.log_y = bool(graph.get("log_x")), bool(graph.get("log_y"))
        legend = graph.get("legend")
        if legend in ("nw", "n", "ne", "sw", "s", "se"):
            slot.legend = legend
        for sig in graph.get("signals", []):
            ds = by_saved.get(os.path.abspath(sig.get("file", "")))
            channel = find_channel(ds.channels, sig.get("name")) if ds else None
            if channel is None or not channel.loaded:
                missing.append(sig.get("name", "?"))
                continue
            if channel not in slot.signals:
                slot.signals.append(channel)
                color = sig.get("color")
                if color and len(color) >= 3:
                    slot.colors[channel] = tuple(int(v) for v in color[:3])
                if sig.get("axis") == "right":
                    slot.right.add(channel)
                limits = sig.get("limits") or [None, None]
                if len(limits) == 2 and any(v is not None for v in limits):
                    slot.limits[channel] = [None if v is None else float(v) for v in limits]
                target = sig.get("target")
                if isinstance(target, (int, float)) and target > 0:
                    slot.targets[channel] = float(target)
        slots.append(slot)
    matrix = data.get("matrix")
    if matrix and len(matrix) == 2 and 1 <= int(matrix[0]) * int(matrix[1]) <= MAX_GRAPHS:
        layout.matrix = (int(matrix[0]), int(matrix[1]))
        layout.spans = normalize_spans(layout.matrix, data.get("spans"))
        count = sum(len(row) for row in layout.row_spans())
        layout.slots = slots[:count] + [GraphSlot() for _ in range(count - len(slots))]
    else:
        layout.slots = [s for s in slots if s.signals]
    return layout, missing


def remap(data: dict, mapping: dict, keep: list[str] | None = None) -> dict:
    """Einstellungen auf andere Dateien übertragen: Ansicht-Daten mit neuen Dateipfaden.

    mapping: gespeicherter Pfad -> Zieldatei (fehlt ein Eintrag, bleibt die Datei). Graphen verweisen danach auf
    die Signale der Zieldatei (gleicher Name). Datenbasen, ASCII-Struktur und berechnete Signale gehen mit.
    Werden mehrere gespeicherte Dateien auf dasselbe Ziel gelegt, werden ihre Einstellungen zusammengeführt.
    keep: zusätzlich geöffnet bleibende Dateien (ohne Einstellungen), z. B. die bisherigen Quelldateien.
    """
    import copy
    out = copy.deepcopy(data)
    norm = {os.path.abspath(k): os.path.abspath(v) for k, v in mapping.items() if v}
    files, by_target = [], {}
    for entry in out.get("files", []):
        saved = os.path.abspath(entry.get("path", ""))
        target = norm.get(saved, saved)
        if target != saved:
            entry = dict(entry, path=target)
            entry.pop("relpath", None)
        merged = by_target.get(target)
        if merged is None:
            by_target[target] = entry
            files.append(entry)
            continue
        names = {c.get("name") for c in merged.get("computed", [])}     # zusammenführen: erste Angabe gilt
        merged.setdefault("computed", []).extend(c for c in entry.get("computed", []) if c.get("name") not in names)
        for key in ("databases", "ascii"):
            if key not in merged and key in entry:
                merged[key] = entry[key]
    for path in keep or []:
        path = os.path.abspath(path)
        if path not in by_target:
            by_target[path] = {"path": path}
            files.append(by_target[path])
    out["files"] = files
    for graph in out.get("graphs", []):
        seen = set()
        signals = []
        for sig in graph.get("signals", []):
            saved = os.path.abspath(sig.get("file", ""))
            sig = dict(sig, file=norm.get(saved, saved))
            if (sig["file"], sig.get("name")) not in seen:       # gleiches Signal doppelt nach Zusammenführen
                seen.add((sig["file"], sig.get("name")))
                signals.append(sig)
        graph["signals"] = signals
    return out
