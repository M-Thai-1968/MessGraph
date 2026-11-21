"""Definitionsdateien (*.def): berechnete Signale dauerhaft hinterlegen.

Inhalt (JSON, lesbar und von Hand änderbar):
    format, version, title, comment, author, created
    files: je Messdatei Pfad (absolut und relativ zur .def) und die Formeln
           [{"name", "unit", "formula", "comment"}]

Vor dem Laden wird je Eintrag das Ziel gewählt: die gespeicherte Messdatei (wird bei Bedarf samt DBC/A2L
geöffnet; verschoben: Suche relativ zur .def) und/oder geöffnete Dateien mit allen verwendeten Signalen.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import formula, progress
from .data_model import Channel, Dataset, LoadError
from .i18n import t

FORMAT = "MessGraph-Definition"
VERSION = 1
SUFFIX = ".def"


def build(datasets: list[Dataset], title: str = "", comment: str = "", author: str = "",
          base_dir: str | None = None) -> dict:
    files = []
    for ds in datasets:
        calc = [{"name": c.name, "unit": c.unit, "formula": c.formula, "comment": getattr(c, "note", "")}
                for c in formula.computed(ds)]
        if not calc:
            continue
        entry = {"path": os.path.abspath(ds.path)}
        options = (ds.extra.get("ascii") or {}).get("options")
        if options and any(options.values()):        # ASCII mit festgelegter Kopfzeile o. Ä.
            entry["ascii"] = options
        config = ds.extra.get("config")
        if config is not None and not config.empty:   # DBC/A2L: dekodierte MF4-Signale gibt es erst damit
            entry["databases"] = config.to_dict()
        if base_dir:
            try:
                entry["relpath"] = os.path.relpath(ds.path, base_dir)
            except ValueError:   # Windows: anderes Laufwerk
                pass
        entry["computed"] = calc
        files.append(entry)
    return {"format": FORMAT, "version": VERSION, "title": title, "comment": comment, "author": author,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"), "files": files}


def write(path: str, data: dict) -> str:
    if not path.lower().endswith(SUFFIX):
        path += SUFFIX
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise LoadError(t("Definition nicht gespeichert: {error}", error=exc)) from exc
    return path


def read(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise LoadError(t("Definition nicht lesbar: {error}", error=exc)) from exc
    except ValueError as exc:
        raise LoadError(t("Definition ist keine gültige JSON-Datei: {error}", error=exc)) from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise LoadError(t("Die Datei ist keine MessGraph-Definition (*.def)."))
    if int(data.get("version", 0)) > VERSION:
        raise LoadError(t("Die Definition stammt aus einer neueren MessGraph-Version."))
    return data


@dataclass
class Result:
    """Ergebnis im Hintergrund; übernommen wird im Oberflächen-Thread."""
    new_datasets: list = field(default_factory=list)
    assignments: list = field(default_factory=list)     # (Dataset, [Channel], {Name: bisheriges Signal})
    problems: list = field(default_factory=list)
    title: str = ""
    comment: str = ""


@dataclass
class Target:
    """Wohin die Formeln eines Eintrags sollen (für die Auswahl vor dem Laden)."""
    index: int                    # Eintrag in files
    stored_name: str              # Name der gespeicherten Messdatei
    stored_path: str | None       # gefundener Pfad oder None
    stored_open: Dataset | None   # schon geöffnet?
    matches: list                 # andere geöffnete Dateien mit allen verwendeten Signalen
    use_stored: bool = True
    use: list = field(default_factory=list)


def same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _resolve(entry: dict, base_dir: str) -> str | None:
    for candidate in (entry.get("path"), entry.get("relpath") and os.path.join(base_dir, entry["relpath"]),
                      entry.get("path") and os.path.join(base_dir, os.path.basename(entry["path"]))):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _references(entry: dict) -> set[str]:
    names, own = set(), {c.get("name") for c in entry.get("computed", [])}
    for calc in entry.get("computed", []):
        try:
            names |= set(formula.references(formula.parse(calc.get("formula", ""))))
        except formula.FormulaError:
            continue
    return names - own


def plan(path: str, loaded: list[Dataset]) -> tuple[dict, list[Target]]:
    """Vorschlag: gespeicherte Datei (geöffnet oder zu öffnen) und passende geöffnete Dateien.

    Ist die gespeicherte Datei offen oder gibt es keine passende andere, gilt die gespeicherte; sonst die
    passenden geöffneten Dateien (typisch: anderer Lauf gleicher Struktur nach dem Neustart).
    """
    data = read(path)
    base_dir = os.path.dirname(os.path.abspath(path))
    targets = []
    for index, entry in enumerate(data.get("files", [])):
        stored = _resolve(entry, base_dir)
        stored_open = next((d for d in loaded if stored and same_path(d.path, stored)), None)
        needed = _references(entry)
        matches = [d for d in loaded if d is not stored_open and needed and needed <= {c.name for c in d.channels}]
        target = Target(index, Path(entry.get("path", "?")).name, stored, stored_open, matches)
        target.use_stored = stored is not None and (stored_open is not None or not matches)
        target.use = [] if target.use_stored else list(matches)
        targets.append(target)
    return data, targets


def _compute_into(dataset: Dataset, entry: dict, result: Result) -> None:
    # Rechnen auf einer Kopie der Signalliste: frühere Formeln stehen späteren zur Verfügung
    work = Dataset(path=dataset.path, channels=list(dataset.channels))
    made, previous = [], {}
    for calc in entry.get("computed", [])[:formula.MAX_COMPUTED]:
        name = str(calc.get("name", "")).strip()
        old = next((c for c in work.channels if c.name == name), None)
        if old is not None and not old.formula:
            result.problems.append(t("{file}: {name} ist ein Messsignal und wird nicht ersetzt.",
                                     file=dataset.name, name=name))
            continue
        try:
            channel = formula.compute(work, name, str(calc.get("unit", "")), str(calc.get("formula", "")), exclude=old)
        except progress.Cancelled:
            raise
        except LoadError as exc:
            result.problems.append(t("{file}: berechnetes Signal {name}: {error}", file=dataset.name,
                                     name=name or "?", error=exc))
            continue
        channel.note = str(calc.get("comment") or "")
        if old is not None:
            if old in dataset.channels:
                previous[name] = old
            work.channels[work.channels.index(old)] = channel
        else:
            work.channels.append(channel)
        made.append(channel)
    if made:
        result.assignments.append((dataset, made, previous))


def apply(path: str, loaded: list[Dataset], load_file, targets: list[Target] | None = None) -> Result:
    """Liest die .def, öffnet nötige Dateien und berechnet die Signale (ohne die Datasets zu verändern)."""
    data, proposal = plan(path, loaded)
    targets = targets if targets is not None else proposal
    result = Result(title=str(data.get("title") or ""), comment=str(data.get("comment") or ""))
    entries = data.get("files", [])
    for number, target in enumerate(targets):
        entry = entries[target.index]
        with progress.section(number / max(1, len(targets)), (number + 1) / max(1, len(targets)),
                              t("Definition: {name}", name=target.stored_name)):
            datasets = list(target.use)
            if target.use_stored:
                dataset = target.stored_open
                if dataset is None and target.stored_path:
                    try:
                        dataset = (load_file(target.stored_path, entry["ascii"]) if entry.get("ascii")
                                   else load_file(target.stored_path))
                        _install_databases(dataset, entry)
                    except progress.Cancelled:
                        raise
                    except LoadError as exc:
                        result.problems.append(f"{target.stored_name}: {exc}")
                        dataset = None
                    if dataset is not None:
                        result.new_datasets.append(dataset)
                if dataset is None and not target.stored_path:
                    result.problems.append(t("Datei fehlt: {path}", path=entry.get("path")))
                if dataset is not None:
                    datasets.insert(0, dataset)
            if not datasets and not target.use_stored:
                result.problems.append(t("Keine Zieldatei für die Formeln von {name} gewählt.", name=target.stored_name))
            for dataset in datasets:
                _compute_into(dataset, entry, result)
    return result


def _install_databases(dataset: Dataset, entry: dict) -> None:
    if not entry.get("databases") or not ("mdf" in dataset.extra or "blf" in dataset.extra):
        return
    from .databases import DatabaseConfig, apply_databases, install_databases
    from .loaders import _mf4_entries
    config = DatabaseConfig.from_dict(entry["databases"])
    if not config.empty:
        progress.busy(t("Datenbasen anwenden..."))
        install_databases(dataset, config, apply_databases(dataset, config, set(), _mf4_entries, dataset.extra.get("start")))


def install(result: Result) -> int:
    """Im Oberflächen-Thread: berechnete Signale übernehmen (bestehende gleichen Namens werden ersetzt)."""
    count = 0
    for dataset, channels, previous in result.assignments:
        for channel in channels:
            old = previous.get(channel.name) or next((c for c in dataset.channels if c.name == channel.name), None)
            if old is not None and not old.formula:
                result.problems.append(t("{file}: {name} ist ein Messsignal und wird nicht ersetzt.",
                                         file=dataset.name, name=channel.name))
                continue
            try:
                formula.add_or_replace(dataset, channel, old)
                count += 1
            except formula.FormulaError as exc:
                result.problems.append(f"{dataset.name}: {channel.name}: {exc}")
    return count
