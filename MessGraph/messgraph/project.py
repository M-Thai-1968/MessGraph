"""Projektdateien (*.mgproj): alles, was für die Wiederverwendung einer Auswertung nötig ist.

Ein Projekt enthält die vollständige Ansicht (Messdateien mit Pfad, Datenbasen je Datei, ASCII-Struktur,
berechnete Signale, Graphen mit Signalen, Farben, Achsen, Grenzen, Legende, Bemerkungen, Matrix, Optionen)
und zusätzlich Name, Bemerkung, die Einstellungen der Dialoge (Report, Export, Vergleich, Downsampling,
Definitionen, zuletzt verwendete Datenbasen, ASCII-Vorlage) sowie Suchtext und Zielgraph.

Pfade werden absolut und relativ zur Projektdatei gespeichert. Wird der Projektordner samt Mess- und
Datenbasis-Dateien verschoben, findet das Projekt sie wieder (zuerst am alten Ort, dann relativ, dann mit
gleichem Namen neben der Projektdatei).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import __version__
from .data_model import LoadError
from .i18n import t

FORMAT = "MessGraph-Projekt"
VERSION = 1
SUFFIX = ".mgproj"
# Einstellungen der Dialoge, die zum Projekt gehören (persönliche wie Sprache oder letzter Ordner nicht)
SETTINGS_KEYS = ("export", "compare_stats", "compare_tolerance", "definition", "databases_last", "databases_auto",
                 "ascii_template", "downsampling")


def _database_paths(config: dict | None) -> list[str]:
    if not config:
        return []
    paths = [p for key in ("dbc", "arxml") for p, *_rest in config.get(key, []) or [] if p]
    paths += [p for key in ("a2l", "cdd") for p in (config.get(key) or []) if isinstance(p, str) and p]
    if isinstance(config.get("a2l"), str) and config["a2l"]:      # Ansichten älterer Versionen
        paths.append(config["a2l"])
    if isinstance(config.get("cdd"), str) and config["cdd"]:
        paths.append(config["cdd"])
    return paths


def _all_database_paths(session: dict, settings: dict) -> list[str]:
    paths = []
    for entry in session.get("files", []):
        paths += _database_paths(entry.get("databases"))
    paths += _database_paths(settings.get("databases_last"))
    return list(dict.fromkeys(paths))


def build(session: dict, settings: dict, name: str = "", comment: str = "", ui: dict | None = None,
          base_dir: str | None = None, created: str | None = None) -> dict:
    project_settings = {key: settings[key] for key in SETTINGS_KEYS if key in settings}
    relpaths = {}
    if base_dir:
        for path in _all_database_paths(session, project_settings):
            try:
                relpaths[os.path.abspath(path)] = os.path.relpath(path, base_dir)
            except ValueError:     # Windows: anderes Laufwerk
                pass
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    return {"format": FORMAT, "version": VERSION, "app_version": __version__, "name": name, "comment": comment,
            "created": created or now, "saved": now, "session": session, "settings": project_settings,
            "ui": ui or {}, "database_relpaths": relpaths}


def write(path: str, data: dict) -> str:
    if not path.lower().endswith(SUFFIX):
        path += SUFFIX
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(path + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)           # erst vollständig schreiben, dann ersetzen
    except OSError as exc:
        raise LoadError(t("Projekt nicht gespeichert: {error}", error=exc)) from exc
    return path


def read(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise LoadError(t("Projekt nicht lesbar: {error}", error=exc)) from exc
    except ValueError as exc:
        raise LoadError(t("Projekt ist keine gültige JSON-Datei: {error}", error=exc)) from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("session"), dict):
        raise LoadError(t("Die Datei ist kein MessGraph-Projekt (*.mgproj)."))
    if int(data.get("version", 0)) > VERSION:
        raise LoadError(t("Das Projekt stammt aus einer neueren MessGraph-Version."))
    return data


def _locate(path: str, relpaths: dict, base_dir: str) -> str | None:
    candidates = [path]
    rel = relpaths.get(os.path.abspath(path))
    if rel:
        candidates.append(os.path.join(base_dir, rel))
    candidates.append(os.path.join(base_dir, os.path.basename(path)))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _relocate_config(config: dict | None, relpaths: dict, base_dir: str, missing: list) -> None:
    if not config:
        return
    for key in ("dbc", "arxml"):
        entries = []
        for item in config.get(key, []) or []:
            path, channel = (item[0], item[1]) if len(item) > 1 else (item[0], 0)
            found = _locate(path, relpaths, base_dir)
            if found is None:
                missing.append(path)
            entries.append([found or path, channel])
        if key in config:
            config[key] = entries
    for key in ("a2l", "cdd"):
        value = config.get(key)
        values = [value] if isinstance(value, str) and value else list(value or [])
        fixed = []
        for path in values:
            found = _locate(path, relpaths, base_dir)
            if found is None:
                missing.append(path)
            fixed.append(found or path)
        if key in config:
            config[key] = fixed


def relocate(data: dict, base_dir: str) -> list[str]:
    """Datenbasis-Pfade auf vorhandene Dateien umstellen (verschobener Projektordner). Liefert fehlende Pfade."""
    relpaths = data.get("database_relpaths") or {}
    missing: list[str] = []
    for entry in data["session"].get("files", []):
        _relocate_config(entry.get("databases"), relpaths, base_dir, missing)
    _relocate_config((data.get("settings") or {}).get("databases_last"), relpaths, base_dir, missing)
    return list(dict.fromkeys(missing))


def summary(data: dict) -> dict:
    """Kennzahlen für die Anzeige: Dateien, Graphen, Signale, berechnete Signale, Datenbasen."""
    session = data.get("session", data)
    files = session.get("files", [])
    graphs = session.get("graphs", [])
    return {"files": len(files), "graphs": len(graphs),
            "signals": sum(len(g.get("signals", [])) for g in graphs),
            "computed": sum(len(e.get("computed", [])) for e in files),
            "databases": len({p for e in files for p in _database_paths(e.get("databases"))})}
