"""CSV- und ASCII-Dateien lesen mit selbsttätiger Erkennung von Kodierung, Trennzeichen, Dezimalzeichen,
Vorspann, Kopfzeile und Einheitenzeile.

ASCII-Rohdaten (asc, txt, dat, log ...) haben oft einen variablen Vorspann. Die Kopfzeile wird erkannt oder vom
Nutzer als Zeilennummer festgelegt (AsciiOptions). Zusatzinformationen in spitzen/geschweiften Klammern wie
<{Continue}> werden entfernt; beginnt eine Zeile damit, setzt sie die vorige Zeile fort (z. B. eine Kopfzeile,
die der Schreiber nach 1000 Zeichen umgebrochen hat). So wird der Kopf logisch auf die Daten bezogen.
"""
from __future__ import annotations

import codecs
import csv
import io
import re
from collections import Counter
from dataclasses import asdict, dataclass

import pandas as pd

from .data_model import Dataset, LoadError
from .i18n import t
from .tabular import build_dataset, clean_names, is_unit, looks_like_date

SAMPLE_BYTES = 1_000_000
SAMPLE_LINES = 1000
SEPARATORS = [";", ",", "\t", "|", " "]
_SEP_NAMES = {";": "Semikolon", ",": "Komma", "\t": "Tabulator", "|": "Senkrechtstrich", " ": "Leerzeichen"}

_NUM_DOT = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
_NUM_COMMA = re.compile(r"^[+-]?(\d+(,\d*)?|,\d+)([eE][+-]?\d+)?$")
_NUM_WORD = {"nan", "inf", "-inf", "+inf", "na", "n/a", "x", "-", "--", "null", "none", "#n/a"}
MARKER = re.compile(r"<\{[^{}<>]*\}>")           # Zusatzinformation, z. B. <{Continue}>
_CAN_TRACE = re.compile(r"^\s*\d+\.\d+\s+\d+\s+[0-9A-Fa-f]+x?\s+(Rx|Tx)\s", re.M)


@dataclass
class AsciiOptions:
    """Vom Nutzer festgelegte Struktur einer ASCII-Datei (0 bzw. "" = automatisch)."""
    header_line: int = 0      # physische Zeilennummer der Kopfzeile, 1-basiert; -1 = keine Kopfzeile
    units_line: int = 0       # Einheitenzeile, 1-basiert; 0 = automatisch, -1 = keine
    sep: str = ""             # Trennzeichen
    decimal: str = ""         # Dezimalzeichen

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "AsciiOptions":
        data = data or {}
        sep = str(data.get("sep") or "")
        decimal = str(data.get("decimal") or "")
        return cls(int(data.get("header_line") or 0), int(data.get("units_line") or 0),
                   sep if sep in SEPARATORS else "", decimal if decimal in (".", ",") else "")

    @property
    def automatic(self) -> bool:
        return self == AsciiOptions()


def logical_lines(lines: list[str]) -> tuple[list[str], list[int], int]:
    """Entfernt Zusatzinformationen wie <{Continue}> und hängt Fortsetzungszeilen an die vorige Zeile.

    Liefert (logische Zeilen, physische Startzeile je logischer Zeile, Anzahl entfernter Marken).
    """
    out, starts, removed = [], [], 0
    for number, line in enumerate(lines):
        stripped = line.lstrip()
        marks = len(MARKER.findall(line))
        removed += marks
        if marks and MARKER.match(stripped) and out:
            out[-1] += MARKER.sub("", stripped)     # Fortsetzung: ohne Trennzeichen anhängen
            continue
        out.append(MARKER.sub("", line) if marks else line)
        starts.append(number)
    return out, starts, removed


def _physical_span(starts: list[int], index: int, total: int) -> tuple[int, int]:
    """Erste und letzte physische Zeile (1-basiert) einer logischen Zeile."""
    first = starts[index] + 1
    last = starts[index + 1] if index + 1 < len(starts) else total
    return first, max(first, last)


@dataclass
class Detection:
    sep: str
    decimal: str
    n_cols: int
    data_line: int           # physische Zeilennummer (0-basiert) der ersten Datenzeile
    header: list[str] | None
    units: list[str] | None
    header_line: int | None
    encoding: str


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    probe = raw[:4000]
    if probe:
        if probe[1::2].count(0) > len(probe) * 0.4:
            return "utf-16-le"
        if probe[0::2].count(0) > len(probe) * 0.4:
            return "utf-16-be"
    try:
        codecs.getincrementaldecoder("utf-8")().decode(raw, final=False)
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def _split(line: str, sep: str) -> list[str]:
    if sep == " ":
        return line.split()
    try:
        row = next(csv.reader([line], delimiter=sep, skipinitialspace=True))
    except (csv.Error, StopIteration):
        row = line.split(sep)
    return [c.strip() for c in row]


def _is_value(cell: str, decimal: str) -> bool:
    if decimal == ",":
        if _NUM_COMMA.match(cell):
            return True
    elif _NUM_DOT.match(cell):
        return True
    return cell.lower() in _NUM_WORD or looks_like_date(cell)


def _data_block(rows: list[list[str]], n_cols: int, decimal: str) -> int | None:
    """Index der ersten Zeile des Datenblocks; wird vom Dateiende her gesucht."""
    def is_data(row):
        return len(row) == n_cols and any(_is_value(c, decimal) for c in row)

    i = len(rows) - 1
    while i >= 0 and not is_data(rows[i]):
        i -= 1
    if i < 0:
        return None
    start = i
    while i > 0:
        i -= 1
        if is_data(rows[i]):
            start = i
        elif len(rows[i]) != n_cols and i > 0 and is_data(rows[i - 1]) \
                and any(_is_value(c, decimal) for c in rows[i]):
            continue  # einzelne fehlerhafte Datenzeile mitten im Block
        else:
            break
    return start


def analyze_lines(lines: list[str], encoding: str = "utf-8", sep: str | None = None,
                  decimal: str | None = None) -> Detection:
    """Erkennt die Struktur anhand der Probezeilen (sep/decimal: feste Vorgabe statt Erkennung)."""
    numbered = [(no, line) for no, line in enumerate(lines) if line.strip()]
    if not numbered:
        raise LoadError(t("Die Datei ist leer."))
    texts = [line for _, line in numbered]

    best = None
    fixed_sep, fixed_dec = sep, decimal
    for sep in ([fixed_sep] if fixed_sep else SEPARATORS):
        rows = [_split(t, sep) for t in texts]
        multi = Counter(len(r) for r in rows if len(r) >= 2)
        n_cols = multi.most_common(1)[0][0] if multi else 1
        for decimal in ([fixed_dec] if fixed_dec else (".", ",")):
            if decimal == sep:
                continue
            start = _data_block(rows, n_cols, decimal)
            if start is None:
                continue
            block = [r for r in rows[start:] if len(r) == n_cols]
            cells = sum(len(r) for r in block) or 1
            values = sum(_is_value(c, decimal) for r in block for c in r)
            ratio = values / cells
            score = len(block) * n_cols * ratio * ratio
            if best is None or score > best[0] * 1.000001:
                best = (score, sep, decimal, n_cols, start, rows)
    if best is None:
        raise LoadError(t("Kein Datenblock mit Zahlenwerten gefunden."))

    _, sep, decimal, n_cols, start, rows = best
    header = units = None
    header_line = None
    if start > 0 and _is_label_row(rows[start - 1], n_cols, decimal):
        header_idx = start - 1
        if start > 1 and _is_label_row(rows[start - 2], n_cols, decimal) and _is_unit_row(rows[start - 1]) \
                and not _is_unit_row(rows[start - 2]):
            units = rows[start - 1]
            header_idx = start - 2
        header = rows[header_idx]
        header_line = numbered[header_idx][0]
    return Detection(sep, decimal, n_cols, numbered[start][0], header, units, header_line, encoding)


def _is_label_row(row: list[str], n_cols: int, decimal: str) -> bool:
    return len(row) == n_cols and any(row) and not any(_is_value(c, decimal) for c in row)


def _is_unit_row(row: list[str]) -> bool:
    filled = [c for c in row if c]
    return bool(filled) and sum(is_unit(c) for c in filled) / len(filled) >= 0.5


def _read_sample(path: str) -> tuple[list[str], str]:
    with open(path, "rb") as fh:
        raw = fh.read(SAMPLE_BYTES)
        truncated = bool(fh.read(1))
    if not raw:
        raise LoadError(t("Die Datei ist leer."))
    encoding = detect_encoding(raw)
    text = codecs.getincrementaldecoder(encoding)(errors="replace").decode(raw, final=not truncated)
    lines = re.split(r"\r\n|\n|\r", text)
    if truncated:
        lines = lines[:-1]  # letzte Zeile ist evtl. abgeschnitten
    return lines[:SAMPLE_LINES], encoding


def _line_text(first: int, last: int) -> str:
    return t("Zeile {line}", line=first) if first == last else t("Zeilen {first}-{last}", first=first, last=last)


def read_csv(path: str, options: AsciiOptions | dict | None = None) -> Dataset:
    return read_ascii(path, options)


def read_ascii(path: str, options: AsciiOptions | dict | None = None) -> Dataset:
    """CSV/ASCII lesen. options: Kopfzeile, Einheitenzeile, Trennzeichen, Dezimalzeichen (sonst automatisch)."""
    opts = options if isinstance(options, AsciiOptions) else AsciiOptions.from_dict(options)
    sample, encoding = _read_sample(path)
    if _CAN_TRACE.search("\n".join(sample[:200])):
        raise LoadError(t("Die Datei ist eine Vector-ASC-Busaufzeichnung (CAN-Trace), keine Wertetabelle. "
                          "Bitte in CANoe/CANalyzer als BLF speichern und die BLF mit DBC/ARXML öffnen."))
    lines, starts, removed = logical_lines(sample)
    manual = not opts.automatic
    det = _structure(lines, encoding, opts, starts)
    names = clean_names(det.header) if det.header else [f"Spalte_{i}" for i in range(1, det.n_cols + 1)]
    if len(names) < det.n_cols:
        names += [f"Spalte_{i}" for i in range(len(names) + 1, det.n_cols + 1)]
    sep = r"\s+" if det.sep == " " else det.sep
    common = dict(sep=sep, decimal=det.decimal, header=None, names=names, index_col=False, on_bad_lines="skip",
                  low_memory=False, skipinitialspace=True, engine="python" if det.sep == " " else "c")
    if det.sep == " ":
        common.pop("low_memory")
    try:
        if removed:   # Marken auch im übrigen Text: ganze Datei bereinigt einlesen
            with open(path, encoding=encoding, errors="replace", newline="") as fh:
                full, _starts, removed = logical_lines(re.split(r"\r\n|\n|\r", fh.read()))
            df = pd.read_csv(io.StringIO("\n".join(full[det.data_line:])), **common)
        else:
            df = pd.read_csv(path, skiprows=det.data_line, encoding=encoding, encoding_errors="replace", **common)
    except (ValueError, pd.errors.ParserError) as exc:
        raise LoadError(t("CSV nicht lesbar: {error}", error=exc)) from exc

    # Spalten ganz ohne Inhalt (z. B. durch ein Trennzeichen am Zeilenende) entfallen.
    empty = [c for c in df.columns if df[c].isna().all() and str(c).startswith("Spalte_")]
    df = df.drop(columns=empty)

    units = {}
    if det.units:
        for name, unit in zip(names, det.units):
            unit = unit.strip().strip("[]()<>").strip()
            if unit and unit != "-":
                units[name] = unit

    total = len(sample)
    info = [t("Trennzeichen: {sep}, Dezimalzeichen: {dec}", sep=t(_SEP_NAMES.get(det.sep, det.sep)), dec=det.decimal),
            t("Kodierung: {encoding}", encoding=encoding)]
    if det.header_line is not None:
        span = _line_text(*_physical_span(starts, det.header_line, total))
        info.append(t("Kopfzeile: {lines} (vom Nutzer festgelegt)", lines=span) if manual and opts.header_line > 0
                    else t("Kopfzeile: {lines} (automatisch erkannt)", lines=span))
    else:
        info.append(t("Keine Kopfzeile gefunden: Spaltennamen wurden erzeugt"))
    info.append(t("Daten ab Zeile {line}", line=_physical_span(starts, min(det.data_line, len(starts) - 1), total)[0]))
    if removed:
        info.append(t("Zusatzinformationen wie <{{Continue}}> ignoriert ({count}x), Fortsetzungszeilen angefügt",
                      count=removed))
    dataset = build_dataset(path, df, det.decimal, units, info)
    dataset.extra["ascii"] = {"options": opts.to_dict(), "header_line": (
        _physical_span(starts, det.header_line, total)[0] if det.header_line is not None else None),
        "data_line": _physical_span(starts, min(det.data_line, len(starts) - 1), total)[0],
        "columns": len(names), "sep": det.sep, "decimal": det.decimal}
    return dataset


def _logical_index(starts: list[int], physical: int) -> int:
    """Logische Zeile, die die physische Zeile (1-basiert) enthält."""
    index = 0
    for i, start in enumerate(starts):
        if start <= physical - 1:
            index = i
        else:
            break
    return index


def _structure(lines: list[str], encoding: str, opts: AsciiOptions, starts: list[int]) -> Detection:
    """Struktur bestimmen: automatisch oder mit den Vorgaben des Nutzers.

    lines sind logische Zeilen; Zeilennummern in opts sind physisch (1-basiert) und werden umgerechnet.
    """
    if opts.header_line <= 0 and opts.units_line <= 0 and not opts.sep and not opts.decimal:
        det = analyze_lines(lines, encoding)
        if opts.header_line < 0:                     # ausdrücklich ohne Kopfzeile
            det.header = det.units = det.header_line = None
        return det
    head = _logical_index(starts, opts.header_line) if opts.header_line > 0 else None
    # Trenn- und Dezimalzeichen: Vorgabe, sonst Erkennung (bei fester Kopfzeile auf dem Teil danach)
    sep, decimal = opts.sep, opts.decimal
    if not sep or not decimal:
        probe = lines[head + 1:] if head is not None else lines
        try:
            found = analyze_lines(probe, encoding, sep=sep or None, decimal=decimal or None)
            sep, decimal = sep or found.sep, decimal or found.decimal
        except LoadError:
            sep, decimal = sep or ",", decimal or "."
    if decimal == sep:
        decimal = "," if sep == "." else "."
    if head is None:   # nur Zeichen vorgegeben: Erkennung mit diesen Zeichen
        det = analyze_lines(lines, encoding, sep=sep, decimal=decimal)
        if opts.header_line < 0:
            det.header = det.units = det.header_line = None
        return det
    rows = [_split(line, sep) if line.strip() else [] for line in lines]
    if head >= len(rows) or not rows[head]:
        raise LoadError(t("Zeile {line} ist leer oder nicht vorhanden; bitte eine andere Kopfzeile wählen.",
                          line=opts.header_line))
    header, units, data = rows[head], None, head + 1
    if opts.units_line > 0:
        u = _logical_index(starts, opts.units_line)
        units = rows[u] if u < len(rows) else None
        data = max(data, u + 1)
    elif opts.units_line == 0 and data < len(rows) and rows[data] and _is_unit_row(rows[data]) \
            and not any(_is_value(c, decimal) for c in rows[data]):
        units = rows[data]
        data += 1
    while data < len(rows) and not rows[data]:
        data += 1
    counts = Counter(len(r) for r in rows[data:data + 200] if r)
    n_cols = max(len(header), counts.most_common(1)[0][0] if counts else len(header))
    return Detection(sep, decimal, n_cols, data, header, units, head, encoding)


@dataclass
class Preview:
    """Ergebnis der Strukturerkennung ohne die Daten zu lesen (für den ASCII-Import-Dialog)."""
    lines: list[str]               # physische Zeilen des Anfangs (Rohtext)
    header_span: tuple | None      # (erste, letzte) physische Zeile der Kopfzeile, 1-basiert
    units_line: int | None
    data_line: int | None
    names: list[str]
    sep: str
    decimal: str
    columns: int
    removed: int
    error: str = ""


def preview(path: str, options: AsciiOptions | dict | None = None, max_lines: int = 80) -> Preview:
    opts = options if isinstance(options, AsciiOptions) else AsciiOptions.from_dict(options)
    try:
        sample, encoding = _read_sample(path)
    except (OSError, LoadError) as exc:
        return Preview([], None, None, None, [], "", "", 0, 0, str(exc))
    raw = sample[:max_lines]
    lines, starts, removed = logical_lines(sample)
    try:
        det = _structure(lines, encoding, opts, starts)
    except LoadError as exc:
        return Preview(raw, None, None, None, [], "", "", 0, removed, str(exc))
    total = len(sample)
    span = _physical_span(starts, det.header_line, total) if det.header_line is not None else None
    units = None
    if det.units is not None and det.header_line is not None:
        units = _physical_span(starts, min(det.header_line + 1, len(starts) - 1), total)[0]
    data = _physical_span(starts, min(det.data_line, len(starts) - 1), total)[0]
    names = clean_names(det.header) if det.header else [f"Spalte_{i}" for i in range(1, det.n_cols + 1)]
    while names and names[-1].startswith("Spalte_") and det.header and not det.header[-1]:
        names.pop()                                   # Trennzeichen am Zeilenende
        break
    return Preview(raw, span, units, data, names, det.sep, det.decimal, det.n_cols, removed)
