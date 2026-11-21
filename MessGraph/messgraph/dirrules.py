"""Verzeichnisverwalter der Auto-Auswertung: aus der Ordnerstruktur der Quelldaten Auswertungen ableiten.

Eine Regel besteht aus
- Basisordner (root): hier wird gesucht, z. B. ...\\Messungen
- Muster (pattern): Pfad der Quellordner relativ zum Basisordner, Teile durch \\ oder / getrennt; * (oder Muster
  wie DUT*) steht für einen beliebigen Ordner und wird als {1}, {2}, ... übernommen. Beispiel: *\\Report\\*
- Vorlage (template) für den Namen der Auswertung = Name des Zielordners. Platzhalter: {1}, {2}, ... (Teile des
  Musters mit *), {MODE} (letzter Ordner des Quellpfads), {DUT} (nächster Ordner DUTn im Quellpfad, auch oberhalb
  des Basisordners), {PARENT} (Ordner über dem Quellordner). Beispiel: {MODE}_{DUT} -> EU_AC_3ph_22kW_705V_DUT1
- Zielbasis (base): Zielordner = <Zielbasis>\\<Name>. Enthält die Zielbasis selbst Platzhalter, ist sie der ganze
  Zielpfad, z. B. ...\\MessGraph\\_TestResult\\{Mode*}_{DUT*} ({NAME} = Name aus der Vorlage).
  Platzhalter sind unabhängig von Groß-/Kleinschreibung, ein angehängtes * ist erlaubt ({Mode*} = {MODE}).

Weil Muster und Vorlage nur die Struktur beschreiben, lässt sich eine Regel auf weitere Mode-Ordner, weitere DUTs
und andere Basisordner übertragen.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

DATA_SUFFIXES = (".csv", ".asc", ".parquet")
DUT_RE = re.compile(r"^DUT[\s_-]?\d+$", re.IGNORECASE)
DUT_IN = re.compile(r"DUT[\s_-]?(\d+)", re.IGNORECASE)                   # auch in längeren Namen
MODE_HINT = re.compile(r"\d+\s*(kW|V|A|ph)(?![a-z])", re.IGNORECASE)      # z. B. 22kW, 705V, 3ph
INVALID = re.compile(r'[\\/:*?"<>|]+')
PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
WILD = set("*?[")


@dataclass
class Rule:
    """Verzeichnisregel. version 1: Muster + Vorlage (ältere Regeln). version 2 (Verzeichnisverwalter ab 1.65):
    Quellordner (root), ausgeschlossene Dateien, Basis-Zielordner (base), erweiterter Zielordner (template) mit
    Platzhaltern {Mode}, {Testlauf}, {Test-Variante}, {Seriennummer}, {DUTx}, {Datetime}, {Name}, eigene Werte je
    Platzhalter (values) und abgewählte Zielordner der Vorschau (deselected)."""
    name: str = "Regel"
    root: str = ""
    pattern: str = "*"
    template: str = "{MODE}"
    base: str = ""
    version: int = 1
    excluded: list = field(default_factory=list)     # Dateien relativ zum Quellordner, Trenner /
    values: dict = field(default_factory=dict)       # eigene Werte: Platzhalter (kanonisch) -> Wert
    deselected: list = field(default_factory=list)   # Schlüssel (erweiterter Zielordner) abgewählter Ziele
    datetime: str = ""                               # {Datetime}: beim ersten Speichern festgelegt

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        data = data or {}
        rule = cls()
        for key in ("name", "root", "pattern", "template", "base", "datetime"):
            if data.get(key) is not None:
                setattr(rule, key, str(data[key]))
        try:
            rule.version = int(data.get("version", 1) or 1)
        except (TypeError, ValueError):
            rule.version = 1
        rule.excluded = [str(x) for x in data.get("excluded") or [] if x]
        rule.values = {canon(str(k)): str(v) for k, v in (data.get("values") or {}).items() if str(v).strip()}
        rule.deselected = [str(x) for x in data.get("deselected") or [] if x]
        return rule


@dataclass
class Match:
    source: str                      # absoluter Quellordner
    rel: tuple                       # Teile relativ zum Basisordner
    captures: tuple                  # Werte der *-Teile
    files: int = 0                   # Messdateien darin (mit Unterordnern)
    name: str = ""
    target: str = ""
    error: str = ""
    mode: str = ""                   # {MODE} des Quellordners (Mode der Auswertung)
    extra: dict = field(default_factory=dict)


def split(pattern: str) -> list[str]:
    return [p for p in re.split(r"[\\/]+", (pattern or "").strip()) if p and p != "."]


def _has_data(names) -> bool:
    return any(n.lower().endswith(DATA_SUFFIXES) for n in names)


def count_files(folder: str, limit: int = 100000) -> int:
    count = 0
    for _dirpath, _dirs, files in os.walk(folder):
        count += sum(1 for f in files if f.lower().endswith(DATA_SUFFIXES))
        if count >= limit:
            break
    return count


def find_data_dirs(root: str, max_depth: int = 8, limit: int = 5000) -> list[tuple]:
    """Ordner unter root, die selbst Messdateien enthalten - als Teile relativ zu root (sortiert)."""
    root = os.path.abspath(root)
    found = []
    if not os.path.isdir(root):
        return found
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirs, files in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs.sort(key=str.casefold)
        if _has_data(files):
            rel = Path(os.path.relpath(dirpath, root)).parts
            found.append(() if rel == (".",) else tuple(rel))
            if len(found) >= limit:
                break
    return sorted(found, key=lambda r: [p.casefold() for p in r])


def is_mode_like(segment: str) -> bool:
    return bool(MODE_HINT.search(segment))


def kind(segment: str) -> str:
    return "dut" if dut_of(segment) else "mode" if is_mode_like(segment) else "other"


def shape(rel: tuple) -> tuple:
    return tuple(kind(x) for x in rel)


def best_example(dirs: list[tuple]) -> tuple:
    """Typische Fundstelle: die häufigste Struktur (Tiefe und Art der Ordner), bevorzugt mit DUT- und Mode-Ordner."""
    if not dirs:
        return ()
    counts = {}
    for d in dirs:
        counts[shape(d)] = counts.get(shape(d), 0) + 1
    best = max(counts, key=lambda sh: (("dut" in sh) + ("mode" in sh), counts[sh], -len(sh)))
    return next(d for d in dirs if shape(d) == best)


def propose(dirs: list[tuple], depth: int | None = None, example: tuple | None = None) -> tuple[str, str]:
    """Muster und Vorlage aus der gefundenen Struktur. Verglichen werden die Fundstellen mit derselben Struktur wie
    das Beispiel (gleiche Tiefe, DUT- und Mode-Ordner an denselben Stellen): DUT- und Mode-Ordner werden zu * bzw.
    DUT*, Ordner wie Report oder Files bleiben fest, Ordner mit lauter verschiedenen Namen (z. B. Datum) werden *.
    depth = Ebene des Quellordners (Anzahl Teile), Standard: ganze Tiefe des Beispiels."""
    if not dirs and not example:
        return "*", "{MODE}"
    example = tuple(example if example is not None else best_example(dirs))
    depth = len(example) if depth is None else max(0, min(depth, len(example)))
    if depth == 0:
        return ".", "{MODE}"
    want = shape(example[:depth])
    group = [d[:depth] for d in dirs if len(d) >= depth and shape(d[:depth]) == want] or [example[:depth]]
    unique = sorted(set(group))
    parts = []
    for i in range(depth):
        segment, sort = example[i], want[i]
        values = [d[i] for d in unique]
        if sort == "dut":
            parts.append("DUT*" if all(v.upper().startswith("DUT") for v in values) else "*")
        elif sort == "mode":
            parts.append("*")
        elif len(set(values)) > 1:
            parts.append("*")                            # unterscheidet sich zwischen den Funden (Mode, Datum ...)
        elif len(unique) == 1 and i == depth - 1 and "mode" not in want:
            parts.append("*")                            # einziger Fund ohne Mode-Ordner: Quellordner beliebig
        else:
            parts.append(segment)
    pattern = "\\".join(parts)
    has_dut = "dut" in want
    template = "{MODE}_{DUT}" if has_dut else "{MODE}"
    if has_dut and want[-1] == "dut" and "mode" not in want:
        template = "{PARENT}_{DUT}"                      # Quellordner ist selbst der DUT-Ordner
    return pattern, template


def match(root: str, pattern: str) -> list[Match]:
    """Alle Ordner unter root, die zum Muster passen (Groß-/Kleinschreibung egal)."""
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return []
    parts = split(pattern)
    states = [(root, (), ())]
    for part in parts:
        nxt = []
        wild = bool(WILD & set(part))
        for folder, rel, caps in states:
            if not wild:
                target = os.path.join(folder, part)
                if os.path.isdir(target):
                    nxt.append((target, rel + (part,), caps))
                else:                                     # andere Schreibweise des festen Teils
                    try:
                        entries = sorted(os.listdir(folder), key=str.casefold)
                    except OSError:
                        entries = []
                    for entry in entries:
                        if entry.casefold() == part.casefold() and os.path.isdir(os.path.join(folder, entry)):
                            nxt.append((os.path.join(folder, entry), rel + (entry,), caps))
                continue
            try:
                entries = sorted(os.listdir(folder), key=str.casefold)
            except OSError:
                continue
            for entry in entries:
                path = os.path.join(folder, entry)
                if os.path.isdir(path) and fnmatch.fnmatchcase(entry.casefold(), part.casefold()):
                    nxt.append((path, rel + (entry,), caps + (entry,)))
        states = nxt
    return [Match(path, rel, caps) for path, rel, caps in states]


def dut_of(segment: str) -> str | None:
    """DUT-Kennung eines Ordnernamens: DUT1, DUT_02, HTOE_DUT3_x -> DUT1, DUT02, DUT3."""
    found = DUT_IN.search(segment or "")
    return f"DUT{found.group(1)}" if found else None


def path_values(source: str, captures: tuple = (), rel: tuple | None = None) -> dict:
    """Werte der Platzhalter für einen Quellordner.
    MODE: Mode-Ordner = letzter Ordner, der wie ein Mode aussieht (22kW, 705V, 3ph ...), sonst der letzte *-Teil, der
    kein DUT ist, sonst der letzte Ordner. REST: Ordner unterhalb des Mode-Ordners (z. B. Files). DUT: nächster
    DUT-Ordner im Pfad (auch oberhalb des Basisordners). PARENT: Ordner über dem Quellordner."""
    segments = list(Path(source).parts)
    scope = list(rel) if rel else segments
    offset = len(segments) - len(scope)
    index = next((offset + k for k in range(len(scope) - 1, -1, -1)
                  if is_mode_like(scope[k]) and not dut_of(scope[k])), None)
    if index is None:
        own = [c for c in captures if not dut_of(c)]
        if own:
            last = own[-1]
            index = next((k for k in range(len(segments) - 1, offset - 1, -1) if segments[k] == last), None)
    if index is None:
        index = len(segments) - 1
    values = {"MODE": segments[index] if segments else "", "PARENT": segments[-2] if len(segments) > 1 else "",
              "REST": os.path.join(*segments[index + 1:]) if index + 1 < len(segments) else ""}
    dut = next((dut_of(x) for x in reversed(segments) if dut_of(x)), None)
    if dut:
        values["DUT"] = dut
    for k, value in enumerate(captures, 1):
        values[str(k)] = value
    return values


def _key(raw: str, values: dict) -> str:
    """{Mode*}, {DUTx}, {mode} -> MODE, DUT (angehängtes * oder x und Groß-/Kleinschreibung egal)."""
    key = raw.strip().rstrip("*").strip()
    if key.isdigit():
        return key
    upper = key.upper()
    if upper not in values and upper not in ("DUT", "NAME") and upper.endswith("X") and len(upper) > 1:
        upper = upper[:-1]
    return upper


def render(template: str, source: str, captures: tuple, extra: dict | None = None, rel: tuple | None = None,
           keep_seps: bool = False) -> str:
    """Namen aus der Vorlage bilden; unbekannter Platzhalter -> ValueError."""
    values = path_values(source, captures, rel)
    for key, value in (extra or {}).items():
        values[key.upper()] = value

    def repl(found):
        key = _key(found.group(1), values)
        if key in values:
            return values[key]
        if key == "DUT":
            raise ValueError(f"{{DUT}}: kein Ordner DUTn im Pfad {source}")
        raise ValueError(f"{{{found.group(1)}}}: unbekannter Platzhalter")

    name = PLACEHOLDER.sub(repl, template or "")
    if keep_seps:
        return name
    name = INVALID.sub("_", name).strip(" ._")
    if not name:
        raise ValueError("leerer Name")
    return name


def render_path(base: str, source: str, captures: tuple, name: str, rel: tuple | None = None) -> str:
    """Zielpfad. Zielbasis ohne Platzhalter: <Zielbasis>\\<Name>\\<REST>. Mit Platzhaltern werden nur die Teile mit {...}
    ersetzt (Laufwerk usw. bleibt); fehlt {REST}, wird der Teil unterhalb des Mode-Ordners angehängt, sofern die
    Zielbasis nicht schon damit endet. Beispiel: Quelle ...\\DUT1\\Report\\EU_AC_3ph_22kW_705V\\Files, Zielbasis
    C:\\...\\_TestResult -> C:\\...\\_TestResult\\EU_AC_3ph_22kW_705V_DUT1\\Files."""
    values = path_values(source, captures, rel)
    rest = values.get("REST", "")
    base = base.strip()
    if not has_placeholder(base):
        return os.path.normpath(os.path.join(base, name, rest)) if base else ""
    parts = re.split(r"([\\/]+)", base)
    out = []
    for part in parts:
        if "{" not in part:
            out.append(part)
        elif _key(part.strip("{}"), values) == "REST" and part.startswith("{") and part.endswith("}"):
            out.append(rest)
        else:
            out.append(render(part, source, captures, {"NAME": name}, rel))
    path = "".join(out)
    uses_rest = any(_key(m, values) == "REST" for m in PLACEHOLDER.findall(base))
    tail = [p for p in re.split(r"[\\/]+", base) if p]
    if rest and not uses_rest and [x.casefold() for x in tail[-len(Path(rest).parts):]] != \
            [x.casefold() for x in Path(rest).parts]:
        path = os.path.join(path, rest)
    return os.path.normpath(path)


def has_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER.search(text or ""))


def apply(rule: Rule, count: bool = True) -> list[Match]:
    """Regel ausführen: passende Quellordner mit Name und Zielordner."""
    found = match(rule.root, rule.pattern)
    for m in found:
        try:
            m.name = render(rule.template, m.source, m.captures, rel=m.rel)
            m.mode = INVALID.sub("_", path_values(m.source, m.captures, m.rel).get("MODE", "")).strip(" ._")
            m.target = render_path(rule.base, m.source, m.captures, m.name, m.rel)
        except ValueError as exc:
            m.error = str(exc)
        if count:
            m.files = count_files(m.source)
    return found


# ====================================================================== Version 2: Platzhalter aus Ordnernamen
# Anzeige-Namen der Platzhalter (Reihenfolge der Liste im Verzeichnisverwalter) und ihre kanonischen Schlüssel
PLACEHOLDERS = (("Mode", "MODE"), ("Testlauf", "TESTLAUF"), ("Test-Variante", "TESTVARIANTE"),
                ("Seriennummer", "SERIENNUMMER"), ("DUTx", "DUT"), ("Datetime", "DATETIME"), ("Name", "NAME"))
DETECTED = ("MODE", "TESTLAUF", "TESTVARIANTE", "SERIENNUMMER", "DUT")
_ALIASES = {"DUTX": "DUT", "DUTN": "DUT", "VARIANTE": "TESTVARIANTE", "TESTVARIANT": "TESTVARIANTE",
            "SN": "SERIENNUMMER", "SERIAL": "SERIENNUMMER", "SERIALNUMBER": "SERIENNUMMER", "DATUM": "DATETIME",
            "DATUMZEIT": "DATETIME", "NAMEAUSWERTUNG": "NAME", "AUSWERTUNG": "NAME", "RUN": "TESTLAUF"}
SERIAL_RE = re.compile(r"(DES\d{6,}|[A-Z]{2,4}\d{12,})", re.IGNORECASE)
TESTRUN_RE = re.compile(r"^(DV|PV|EV|PPV|SOP|QV)\d*(?=$|[_\-\s])", re.IGNORECASE)
VARIANT_RE = re.compile(r"^(HTOE|PTCE|HTOL|LTOE|THB|HAST|PCT|TCT)(?=$|[_\-\s\d])", re.IGNORECASE)   # HTOE_22kW, HTOE22kW
MAX_FILES = 20000                                    # so viele Dateien listet der Verzeichnisverwalter höchstens


def canon(key: str) -> str:
    """{Mode*}, {DUTx}, {Test-Variante}, {name} -> MODE, DUT, TESTVARIANTE, NAME."""
    raw = re.sub(r"[\s_\-*]", "", (key or "").strip()).upper()
    return _ALIASES.get(raw, raw)


def classify(segment: str) -> dict:
    """Was ein einzelner Ordnername verrät: {Schlüssel: Wert}."""
    found = {}
    serial = SERIAL_RE.search(segment)
    if serial:
        found["SERIENNUMMER"] = serial.group(1).upper()
    dut = dut_of(segment)
    if dut:
        found["DUT"] = dut
    run = TESTRUN_RE.match(segment)
    if run:
        found["TESTLAUF"] = run.group(0).upper()
    variant = VARIANT_RE.match(segment)
    if variant:
        found["TESTVARIANTE"] = segment
    elif is_mode_like(segment) and not serial and not dut and not run:
        found["MODE"] = segment
    return found


def detect(parts) -> dict:
    """Platzhalter-Werte aus allen Ordnern eines Pfads; der tiefste Treffer je Platzhalter gilt."""
    values = {}
    for segment in reversed(list(parts)):
        for key, value in classify(segment).items():
            values.setdefault(key, value)
    return values


@dataclass
class DataDir:
    rel: tuple                       # Ordner relativ zum Quellordner
    files: list                      # Dateinamen (nur Messdateien)


def scan(root: str, max_depth: int = 10, limit: int = MAX_FILES) -> list[DataDir]:
    """Ordner mit Messdateien unter root (sortiert); höchstens limit Dateien insgesamt."""
    root = os.path.abspath(root)
    found, total = [], 0
    if not os.path.isdir(root):
        return found
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirs, files in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        dirs.sort(key=str.casefold)
        data = sorted((f for f in files if f.lower().endswith(DATA_SUFFIXES)), key=str.casefold)
        if data:
            data = data[:max(0, limit - total)]
            total += len(data)
            rel = Path(os.path.relpath(dirpath, root)).parts
            found.append(DataDir(() if rel == (".",) else tuple(rel), data))
            if total >= limit:
                break
    return sorted(found, key=lambda d: [p.casefold() for p in d.rel])


def structure(dirs: list[DataDir], root: str = "", show: int = 6) -> list[str]:
    """Bezeichnung der Unterordner je Ebene, z. B. ["Ebene 1: DUT1, DUT2", "Ebene 2: Report", ...]."""
    levels = {}
    for d in dirs:
        for depth, name in enumerate(d.rel):
            levels.setdefault(depth, [])
            if name not in levels[depth]:
                levels[depth].append(name)
    lines = []
    for depth in sorted(levels):
        names = levels[depth]
        kinds = sorted({k for n in names for k in classify(n)})
        more = f" (+{len(names) - show})" if len(names) > show else ""
        label = ", ".join(names[:show]) + more
        lines.append((depth + 1, label, kinds))
    return lines


def rel_file(rel: tuple, name: str) -> str:
    return "/".join((*rel, name))


def default_template(found: dict) -> str:
    """Vorschlag für den erweiterten Zielordner aus den erkannten Platzhaltern, z. B.
    {Testlauf}_{Test-Variante}\\{Mode}\\{DUTx} (Testlauf/Test-Variante nur, wenn erkannt)."""
    head = "_".join(p for k, p in (("TESTLAUF", "{Testlauf}"), ("TESTVARIANTE", "{Test-Variante}")) if k in found)
    parts = [head] if head else []
    parts.append("{Mode}" if "MODE" in found else "{Name}")
    if "DUT" in found:
        parts.append("{DUTx}")
    elif "SERIENNUMMER" in found:
        parts.append("{Seriennummer}")
    return "\\".join(parts)


def serial_in_files(files) -> str:
    """Seriennummer aus den Dateinamen (häufigste), wenn die Ordner keine nennen."""
    counts = {}
    for name in files:
        found = SERIAL_RE.search(name)
        if found:
            counts[found.group(1).upper()] = counts.get(found.group(1).upper(), 0) + 1
    return max(counts, key=counts.get) if counts else ""


GENERIC = {"report", "reports", "files", "file", "data", "daten", "raw", "rohdaten", "messdaten", "logs", "log",
           "results", "result", "ergebnisse", "csv", "export", "measurements", "messungen"}


COUNTER_RE = re.compile(r"^(\d{1,4}|\d{6}|\d{8}|\d{8}T?\d{6}|\d{14})$")       # 001, Datum, Uhrzeit


def file_values(name: str) -> dict:
    """Was ein Dateiname verrät: Seriennummer, DUT und Mode (zusammenhängende Teile mit z. B. 22kW, 615V, 3ph -
    ohne Seriennummer, DUT, Testlauf, Test-Variante, Zähler und Zeitstempel). Beispiel:
    DES202507230117500132_AC_22kW_3ph_615V.csv -> Seriennummer DES..., Mode AC_22kW_3ph_615V."""
    stem = os.path.splitext(name)[0]
    values = {}
    serial = SERIAL_RE.search(stem)
    if serial:
        values["SERIENNUMMER"] = serial.group(1).upper()
    dut = dut_of(stem)
    if dut:
        values["DUT"] = dut
    runs, current = [], []
    for token in re.split(r"[_\s]+", stem):
        noise = (not token or SERIAL_RE.fullmatch(token) or DUT_RE.match(token) or TESTRUN_RE.fullmatch(token)
                 or VARIANT_RE.match(token) or COUNTER_RE.match(token))
        if noise:
            if current:
                runs.append(current)
            current = []
        else:
            current.append(token)
    if current:
        runs.append(current)
    modes = [r for r in runs if any(is_mode_like(t) for t in r)]
    if modes:
        values["MODE"] = "_".join(max(modes, key=len))
    return values


def mode_level(dirs: list[DataDir]) -> int | None:
    """Ebene (Index in rel), auf der die Mode-Ordner meist liegen - für Modes ohne Zahlen im Namen (z. B. Precon)."""
    counts = {}
    for d in dirs:
        for index, segment in enumerate(d.rel):
            if "MODE" in classify(segment):
                counts[index] = counts.get(index, 0) + 1
    return max(counts, key=counts.get) if counts else None


def dir_values(above: tuple, d: DataDir, level: int | None = None) -> dict:
    values = detect((*above, *d.rel))
    if "MODE" not in values and level is not None and level < len(d.rel):
        segment = d.rel[level]
        if not classify(segment):                      # Ordner auf der Mode-Ebene ohne andere Bedeutung
            values["MODE"] = segment
    elif "MODE" not in values and level is None:       # keine Mode-Namen mit Zahlen: tiefster eigener Ordnername
        segment = next((x for x in reversed(d.rel) if not classify(x) and x.casefold() not in GENERIC), None)
        if segment:
            values["MODE"] = segment
    if "SERIENNUMMER" not in values:
        serial = serial_in_files(d.files)
        if serial:
            values["SERIENNUMMER"] = serial
    return values


def detected_values(root: str, dirs: list[DataDir]) -> dict:
    """Erkannte Werte je Platzhalter über alle Ordner (für die Anzeige): Schlüssel -> Liste der Werte."""
    above = Path(os.path.abspath(root)).parts if root else ()
    level = mode_level(dirs)
    result = {}

    def add(key, value):
        values = result.setdefault(key, [])
        if value not in values:
            values.append(value)
    for d in dirs:
        base = dir_values(above, d, level)
        for key, value in base.items():
            add(key, value)
        if "MODE" not in base:                          # Modes aus den Dateinamen
            for name in d.files:
                mode = file_values(name).get("MODE")
                if mode:
                    add("MODE", mode)
    return result


def file_modes(dirs: list[DataDir], root: str = "") -> list[str]:
    """Modes, die nur in Dateinamen stehen (Ordner ohne Mode), z. B. AC_22kW_3ph_615V aus DES..._AC_22kW_3ph_615V.csv."""
    above = Path(os.path.abspath(root)).parts if root else ()
    level = mode_level(dirs)
    found = []
    for d in dirs:
        if "MODE" in dir_values(above, d, level):
            continue
        for name in d.files:
            mode = file_values(name).get("MODE")
            if mode and mode not in found:
                found.append(mode)
    return found


def render_v2(template: str, values: dict) -> str:
    """Erweiterten Zielordner bilden; Trenner \\ oder / bleiben Ordnergrenzen, jedes Stück wird bereinigt.
    Fehlender Wert -> ValueError."""
    def repl(found):
        key = canon(found.group(1))
        value = values.get(key)
        if not value:
            raise ValueError(f"{{{found.group(1)}}}: kein Wert (weder in Ordner- noch Dateinamen erkannt - Datei abwählen oder eigenen Wert eintragen)")
        return str(value)

    parts = []
    for part in re.split(r"[\\/]+", template or ""):
        if not part.strip():
            continue
        text = INVALID.sub("_", PLACEHOLDER.sub(repl, part)).strip(" ._")
        if text:
            parts.append(text)
    if not parts:
        raise ValueError("leerer Zielordner")
    return os.path.join(*parts)


@dataclass
class Unit:
    """Eine Auswertung aus Regel v2: alle Ordner, die zum selben Zielordner führen."""
    key: str                         # erweiterter Zielordner (relativ zur Basis)
    target: str = ""
    folders: list = field(default_factory=list)      # absolute Quellordner
    rels: list = field(default_factory=list)
    files: int = 0
    excluded: list = field(default_factory=list)     # absolute Pfade ausgeschlossener Dateien darin
    paths: list = field(default_factory=list)        # absolute Pfade der gewählten Dateien
    split: bool = False                              # Ordner teilt sich auf mehrere Ziele (Mode aus Dateinamen)
    values: dict = field(default_factory=dict)
    mode: str = ""
    name: str = ""
    active: bool = True
    warning: str = ""
    error: str = ""


def plan(rule: Rule, name: str = "", dirs: list[DataDir] | None = None, now: str | None = None) -> list[Unit]:
    """Regel v2 auswerten - je Datei: Platzhalter-Werte aus den Ordnern (tiefster Treffer), sonst aus dem Dateinamen
    (Mode, Seriennummer, DUT); eigene Werte haben Vorrang -> erweiterter Zielordner. Dateien mit demselben Ziel bilden
    eine Auswertung (z. B. Tagesordner eines DUTs oder alle Dateien eines Modes aus einem Ordner)."""
    import time as _time
    root = os.path.abspath(rule.root) if rule.root else ""
    dirs = scan(root) if dirs is None else dirs
    above = Path(root).parts if root else ()
    excluded = {x.replace("\\", "/").casefold() for x in rule.excluded}
    stamp = now or rule.datetime or _time.strftime("%Y%m%d_%H%M%S")
    own = {k: v for k, v in rule.values.items() if v}
    units: dict[str, Unit] = {}
    errors: dict[str, Unit] = {}
    level = mode_level(dirs)
    keys_of_folder: dict[str, set] = {}
    for d in dirs:
        folder = os.path.join(root, *d.rel)
        base = dir_values(above, d, level)
        for fname in d.files:
            path = os.path.join(folder, fname)
            values = dict(base)
            for key, value in file_values(fname).items():
                values.setdefault(key, value)              # Ordner gehen vor, sonst Dateiname
            values.update(own)
            values.setdefault("NAME", name or rule.name)
            values.setdefault("DATETIME", stamp)
            skipped = rel_file(d.rel, fname).casefold() in excluded
            try:
                key = render_v2(rule.template, values)
            except ValueError as exc:
                ekey = (os.path.join(*d.rel) if d.rel else ".") + "|" + str(exc)
                unit = errors.get(ekey)
                if unit is None:
                    unit = errors[ekey] = Unit(key=os.path.join(*d.rel) if d.rel else ".", values=values,
                                               error=str(exc), active=False)
                if folder not in unit.folders:
                    unit.folders.append(folder)
                    unit.rels.append(d.rel)
                if not skipped:
                    unit.files += 1
                    unit.paths.append(path)
                keys_of_folder.setdefault(folder, set()).add("!" + ekey)
                continue
            unit = units.get(key.casefold())
            if unit is None:
                unit = units[key.casefold()] = Unit(key=key, target=os.path.normpath(os.path.join(rule.base, key))
                                                    if rule.base else "", values=dict(values))
                unit.mode = INVALID.sub("_", values.get("MODE") or values.get("NAME") or "").strip(" ._")
            else:
                for k in ("DUT", "SERIENNUMMER"):
                    if not unit.warning and values.get(k) and unit.values.get(k) and values[k] != unit.values[k]:
                        unit.warning = f"mehrere {('DUTs' if k == 'DUT' else 'Seriennummern')} in einem Zielordner"
            if folder not in unit.folders:
                unit.folders.append(folder)
                unit.rels.append(d.rel)
            keys_of_folder.setdefault(folder, set()).add(key.casefold())
            if skipped:
                unit.excluded.append(path)
            else:
                unit.files += 1
                unit.paths.append(path)
    result = list(units.values())
    deselected = {x.casefold() for x in rule.deselected}
    for unit in result:
        unit.split = any(len(keys_of_folder.get(f, ())) > 1 for f in unit.folders)
        unit.active = unit.key.casefold() not in deselected and unit.files > 0
        if not rule.base:
            unit.error = "kein Basis-Zielordner"
        tag = unit.values.get("DUT") or unit.values.get("SERIENNUMMER") or ""
        unit.name = f"{unit.mode}_{tag}" if tag and unit.mode and tag not in unit.mode else (unit.mode or unit.key)
        unit.name = INVALID.sub("_", unit.name).strip(" ._")
    return sorted(result, key=lambda u: u.key.casefold()) + list(errors.values())
