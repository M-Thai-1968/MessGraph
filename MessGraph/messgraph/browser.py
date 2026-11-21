"""Verzeichnisinhalt für den eigenen Datei-Browser (ohne Oberfläche, testbar)."""
from __future__ import annotations

import os
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path

FILTERS = {
    "Messdaten (mf4, mdf, blf, csv, asc, txt, dat, parquet)": (".mf4", ".mdf", ".blf", ".csv", ".asc", ".txt", ".dat",
                                                              ".tsv", ".log", ".prn", ".parquet"),
    "MF4 (*.mf4)": (".mf4",),
    "MDF (*.mdf)": (".mdf",),
    "BLF (*.blf)": (".blf",),
    "CSV (*.csv)": (".csv",),
    "ASCII (asc, txt, dat, tsv, log, prn)": (".asc", ".txt", ".dat", ".tsv", ".log", ".prn"),
    "Parquet (*.parquet)": (".parquet",),
    "Alle Dateien": None,
}
DEFAULT_FILTER = "Messdaten (mf4, mdf, blf, csv, asc, txt, dat, parquet)"
MAX_ENTRIES = 3000


@dataclass
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int = 0
    mtime: float = 0.0


DATABASE_FILTERS = {
    "databases": {"Datenbasen (dbc, arxml, a2l, cdd)": (".dbc", ".arxml", ".a2l", ".cdd"), "DBC (*.dbc)": (".dbc",),
                  "ARXML (*.arxml)": (".arxml",), "A2L (*.a2l)": (".a2l",), "CDD (*.cdd)": (".cdd",),
                  "Alle Dateien": None},
    "dbc": {"DBC (*.dbc)": (".dbc",), "Alle Dateien": None},
    "arxml": {"ARXML (*.arxml)": (".arxml",), "Alle Dateien": None},
    "a2l": {"A2L (*.a2l)": (".a2l",), "Alle Dateien": None},
    "cdd": {"CDD (*.cdd)": (".cdd",), "Alle Dateien": None},
    "session": {"MessGraph-Ansicht (*.mgraph)": (".mgraph",), "Alle Dateien": None},
    "project": {"MessGraph-Projekt (*.mgproj)": (".mgproj",), "Alle Dateien": None},
    "definition": {"MessGraph-Definition (*.def)": (".def",), "Alle Dateien": None},
    "limitconfig": {"Grenzwert-Konfiguration (*.yaml, *.yml)": (".yaml", ".yml"), "Alle Dateien": None},
    "limiter": {"Limiter-Konfiguration (*.yaml, *.yml)": (".yaml", ".yml"), "Alle Dateien": None},
    "folder": {"Ordner (der angezeigte Ordner wird gewählt)": (".\x00ordner",)},
}


def list_dir(path: str, filter_name: str = DEFAULT_FILTER, name_filter: str = "",
             show_hidden: bool = False, filters: dict | None = None) -> tuple[list[Entry], list[Entry], str]:
    """Ordner und passende Dateien, je alphabetisch. Dateiendung ohne Rücksicht auf Groß-/Kleinschreibung."""
    filters = filters or FILTERS
    suffixes = filters[filter_name] if filter_name in filters else next(iter(filters.values()))
    words = name_filter.lower().split()
    dirs, files = [], []
    try:
        with os.scandir(path) as it:
            for entry in it:
                name = entry.name
                if not show_hidden and name.startswith("."):
                    continue
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    continue
                if is_dir:
                    dirs.append(Entry(name, entry.path, True))
                    continue
                if suffixes is not None and Path(name).suffix.lower() not in suffixes:
                    continue
                if not all(w in name.lower() for w in words):
                    continue
                try:
                    st = entry.stat()
                    files.append(Entry(name, entry.path, False, st.st_size, st.st_mtime))
                except OSError:
                    files.append(Entry(name, entry.path, False))
    except OSError as exc:
        from .i18n import t
        return [], [], t("Ordner nicht lesbar: {error}", error=exc.strerror or exc)
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())
    return dirs, files, ""


def parent_dir(path: str) -> str:
    parent = os.path.dirname(os.path.abspath(path).rstrip("\\/")) or path
    return parent if os.path.isdir(parent) else path


def drives() -> list[str]:
    """Laufwerke unter Windows, sonst leer."""
    if sys.platform != "win32":
        return []
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "kB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def human_time(stamp: float) -> str:
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(stamp)) if stamp else ""
