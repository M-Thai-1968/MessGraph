"""Datenbasen für MF4/MDF und BLF: DBC und ARXML (CAN-Dekodierung), A2L (Einheiten/Umrechnungen), CDD.

Je Aufzeichnung lassen sich beliebig viele Dateien kombinieren (z. B. zwei DBC, eine ARXML, zwei A2L).
DBC/ARXML: asammdf.MDF.extract_bus_logging dekodiert Busrohdaten (CAN_DataFrame ...), je CAN-Kanal oder
für alle Kanäle; ARXML wird dafür in eine DBC umgesetzt. BLF dekodiert eigenständig (blf.apply_dbc).
Angewendet wird bei Bedarf: Dateien ohne passende Botschaft bzw. Messgröße werden nur gemeldet.
A2L: MEASUREMENT- und COMPU_METHOD-Blöcke liefern Einheit und optional die Umrechnung
von Rohwerten in physikalische Werte für gleichnamige Kanäle (die erste A2L mit dem Namen gilt).
CDD: wird zugeordnet und gemerkt; die Auswertung ist noch nicht eingebaut.
"""
from __future__ import annotations

import dataclasses
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .data_model import Channel, Dataset, LoadError
from .i18n import t

CAN_CHOICES = ["Alle Kanäle"] + [f"CAN {i}" for i in range(1, 9)]


KINDS = {".dbc": "dbc", ".arxml": "arxml", ".a2l": "a2l", ".cdd": "cdd"}


def kind_of(path: str) -> str | None:
    return KINDS.get(Path(path).suffix.lower())


def _paths(value) -> list[str]:
    """Liste von Pfaden; ältere Ansichten speicherten A2L/CDD als einzelnen Text."""
    if isinstance(value, str):
        return [value] if value else []
    return [str(p) for p in value or [] if p]


@dataclass
class DatabaseConfig:
    dbc: list = field(default_factory=list)      # [(Pfad, Kanal 0 = alle)]
    arxml: list = field(default_factory=list)    # [(Pfad, Kanal 0 = alle)]
    a2l: list = field(default_factory=list)      # [Pfad]
    a2l_convert: bool = False
    cdd: list = field(default_factory=list)      # [Pfad]

    def to_dict(self) -> dict:
        return {"dbc": [list(d) for d in self.dbc], "arxml": [list(d) for d in self.arxml], "a2l": list(self.a2l),
                "a2l_convert": self.a2l_convert, "cdd": list(self.cdd)}

    @classmethod
    def from_dict(cls, data: dict | None) -> "DatabaseConfig":
        data = data or {}
        bus = lambda key: [(str(p), int(c)) for p, c in data.get(key, []) if p]
        return cls(dbc=bus("dbc"), arxml=bus("arxml"), a2l=_paths(data.get("a2l")),
                   a2l_convert=bool(data.get("a2l_convert")), cdd=_paths(data.get("cdd")))

    @property
    def empty(self) -> bool:
        return not (self.dbc or self.arxml or self.a2l or self.cdd)

    @property
    def bus(self) -> list:
        """Alle Bus-Datenbasen (DBC und ARXML) mit Kanal, in der Reihenfolge DBC vor ARXML."""
        return list(self.dbc) + list(self.arxml)

    def files(self) -> list[tuple[str, str]]:
        """(Art, Pfad) aller zugeordneten Dateien."""
        return ([("dbc", p) for p, _ in self.dbc] + [("arxml", p) for p, _ in self.arxml]
                + [("a2l", p) for p in self.a2l] + [("cdd", p) for p in self.cdd])

    def add(self, paths) -> list[str]:
        """Dateien nach Endung einsortieren (doppelte werden übergangen). Liefert nicht erkannte Pfade."""
        known = {p for _k, p in self.files()}
        unknown = []
        for path in paths:
            kind = kind_of(path)
            if kind is None:
                unknown.append(path)
            elif path not in known:
                known.add(path)
                target = getattr(self, kind)
                target.append((path, 0) if kind in ("dbc", "arxml") else path)
        return unknown

    def remove(self, kind: str, index: int) -> None:
        del getattr(self, kind)[index]


# ---------------------------------------------------------------- A2L
@dataclass
class A2LMeasurement:
    name: str
    unit: str = ""
    compu: Callable[[np.ndarray], np.ndarray] | None = None
    compu_note: str = ""


_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|\S+')


def _tokens(text: str) -> list[str]:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    return _TOKEN.findall(text)


def _unquote(token: str) -> str:
    return token[1:-1].replace('\\"', '"') if token.startswith('"') else token


def _blocks(tokens: list[str], wanted: set[str]) -> list[tuple[str, list[str]]]:
    """Blöcke /begin TYP ... /end TYP; je Block nur die direkten Token (ohne Unterblöcke)."""
    found = []
    stack: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "/begin" and i + 1 < len(tokens):
            stack.append((tokens[i + 1], []))
            i += 2
            continue
        if tok == "/end" and i + 1 < len(tokens):
            if stack:
                kind, body = stack.pop()
                if kind in wanted:
                    found.append((kind, body))
            i += 2
            continue
        if stack:
            stack[-1][1].append(tok)
        i += 1
    return found


def _num(token: str) -> float:
    return float(int(token, 16)) if token.lower().startswith("0x") else float(token)


def _after(body: list[str], keyword: str, count: int) -> list[str] | None:
    if keyword in body:
        i = body.index(keyword)
        return body[i + 1:i + 1 + count]
    return None


def _make_compu(kind: str, body: list[str], tables: dict) -> tuple[Callable | None, str]:
    if kind in ("IDENTICAL", "NO_COMPU_METHOD"):
        return None, ""
    if kind == "LINEAR":
        coeffs = _after(body, "COEFFS_LINEAR", 2)
        if coeffs and len(coeffs) == 2:
            a, b = map(_num, coeffs)
            return (lambda x, a=a, b=b: a * x + b), ""
    if kind == "RAT_FUNC":
        coeffs = _after(body, "COEFFS", 6)
        if coeffs and len(coeffs) == 6:
            a, b, c, d, e, f = map(_num, coeffs)
            # A2L: int = (a*p² + b*p + c) / (d*p² + e*p + f); hier p aus int bestimmen
            if a == 0 and d == 0 and e == 0 and b != 0:
                return (lambda x, b=b, c=c, f=f: (f * x - c) / b), ""
            if a == 0 and d == 0 and b != 0 and e != 0:   # int*(e*p + f) = b*p + c
                return (lambda x, b=b, c=c, e=e, f=f: (f * x - c) / (b - e * x)), ""
            return None, "RAT_FUNC mit quadratischen Anteilen wird nicht umgerechnet"
    if kind in ("TAB_INTP", "TAB_NOINTP"):
        ref = _after(body, "COMPU_TAB_REF", 1)
        table = tables.get(_unquote(ref[0])) if ref else None
        if table is not None:
            xs, ys = table
            if kind == "TAB_INTP":
                return (lambda x, xs=xs, ys=ys: np.interp(x, xs, ys)), ""
            def nearest(x, xs=xs, ys=ys):
                idx = np.clip(np.searchsorted(xs, x), 1, len(xs) - 1)
                left = np.abs(x - xs[idx - 1]) <= np.abs(xs[idx] - x)
                return np.where(left, ys[idx - 1], ys[idx])
            return nearest, ""
    if kind == "TAB_VERB":
        return None, "Texttabelle: Rohwerte bleiben"
    return None, f"Umrechnung {kind} wird nicht unterstützt"


def parse_a2l(path: str) -> dict[str, A2LMeasurement]:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise LoadError(t("A2L nicht lesbar: {error}", error=exc)) from exc
    blocks = _blocks(_tokens(text), {"MEASUREMENT", "COMPU_METHOD", "COMPU_TAB"})
    tables = {}
    for kind, body in blocks:
        if kind == "COMPU_TAB" and len(body) >= 4:
            try:
                n = int(_num(body[3]))
                pairs = [_num(t) for t in body[4:4 + 2 * n]]
                xs, ys = np.array(pairs[0::2]), np.array(pairs[1::2])
                order = np.argsort(xs)
                tables[_unquote(body[0])] = (xs[order], ys[order])
            except ValueError:
                pass
    methods = {}
    for kind, body in blocks:
        if kind == "COMPU_METHOD" and len(body) >= 5:
            compu, note = _make_compu(body[2], body, tables)
            methods[_unquote(body[0])] = (_unquote(body[4]), compu, note)
    result = {}
    for kind, body in blocks:
        if kind != "MEASUREMENT" or len(body) < 4:
            continue
        name = _unquote(body[0])
        unit, compu, note = methods.get(_unquote(body[3]), ("", None, ""))
        phys = _after(body, "PHYS_UNIT", 1)
        if phys:
            unit = _unquote(phys[0])
        result[name] = A2LMeasurement(name, unit, compu, note)
    if not result:
        raise LoadError(t("Die A2L-Datei enthält keine MEASUREMENT-Einträge."))
    return result


def _lookup_names(name: str) -> list[str]:
    """Kanalname aus der MF4 auf A2L-Namen abbilden: 'nEng\\XCP:1 (G3)' -> 'nEng'."""
    base = re.sub(r"\s\(G\d+\)$", "", name)
    names = [base, base.split("\\")[0], base.split(":")[0]]
    names.append(names[1].rsplit(".", 1)[-1])
    return list(dict.fromkeys(n for n in names if n))


# ---------------------------------------------------------------- Anwenden
def apply_databases(dataset: Dataset, config: DatabaseConfig, preload: set[str],
                    entries_of: Callable, start_time: float | None) -> tuple[list[Channel], list[str], list[str], list]:
    """Läuft im Hintergrund. Liefert (Kanäle, Info, Hinweise, neue MDF-Objekte zum späteren Schließen).

    preload: Namen der gerade angezeigten Kanäle; sie werden gleich geladen, damit die
    Graphen sie nach dem Tausch sofort wieder zeigen.
    """
    if "blf" in dataset.extra:   # BLF: eigene DBC-Dekodierung der CAN-Botschaften
        from .blf import apply_dbc
        return apply_dbc(dataset, config)
    mdf, lock = dataset.extra["mdf"], dataset.extra["lock"]
    base: list[Channel] = dataset.extra["base"]
    channels = [dataclasses.replace(c, x=None, y=None) for c in base]
    info, warnings, opened = [], [], []

    if config.bus:
        missing = [p for p, _ in config.bus if not Path(p).is_file()]
        if missing:
            raise LoadError(t("Datenbasis nicht gefunden: {names}", names=", ".join(missing)))
        from . import progress
        progress.busy(t("DBC dekodieren (Busrohdaten in Signale umrechnen)..."))
        files, signal_names, temp_dir = [], {}, None
        try:
            for path, ch in config.bus:
                if kind_of(path) != "arxml":
                    try:   # nur zur Auskunft, ob die DBC gebraucht wurde; dekodiert wird von asammdf
                        messages, _notes = _bus_messages(path)
                        signal_names[path] = {s.name for m in messages.values() for s in m.signals}
                    except (LoadError, OSError):
                        pass
                    files.append((path, ch))
                    continue
                messages, notes = _bus_messages(path)
                warnings += notes
                signal_names[path] = {s.name for m in messages.values() for s in m.signals}
                if kind_of(path) == "arxml":   # asammdf/canmatrix: ARXML als gleichwertige DBC übergeben
                    import tempfile
                    from . import arxml
                    temp_dir = temp_dir or tempfile.mkdtemp(prefix="messgraph_arxml_")
                    target = Path(temp_dir) / f"{len(files)}_{Path(path).stem}.dbc"
                    target.write_text(arxml.to_dbc(messages), encoding="utf-8")
                    files.append((str(target), ch))
            with lock:
                try:
                    decoded = mdf.extract_bus_logging(database_files={"CAN": files})
                except ImportError as exc:
                    raise LoadError(t("Für die DBC-Dekodierung wird canmatrix benötigt: pip install canmatrix")) from exc
                except Exception as exc:
                    raise LoadError(t("DBC-Dekodierung fehlgeschlagen: {error}", error=f"{type(exc).__name__}: {exc}")) from exc
        finally:
            if temp_dir:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        opened.append(decoded)
        dec_lock = threading.Lock()
        entries = entries_of(decoded)
        known = {c.name for c in channels}
        from .loaders import mf4_display_names
        for e, (shown, aliases) in zip(entries, mf4_display_names(decoded, entries)):
            name, group, index = e["name"], e["group"], e["index"]
            legacy = name if name not in known else f"{name} (DBC G{group})"
            if shown in known:                                  # Name schon von einem Rohkanal belegt
                shown = f"{shown} [DBC g{group}]"
                n = 2
                while shown in known:
                    shown = f"{name} [DBC g{group}:i{index}]" if n == 2 else f"{name} [DBC g{group}:i{index}:{n}]"
                    n += 1
            known.add(shown)
            aliases = tuple(a for a in dict.fromkeys((*aliases, legacy)) if a != shown)
            channels.append(Channel(name=shown, unit=e["unit"], x_name="Zeit", x_unit="s", source=dataset.path,
                                    loader=_decoded_loader(decoded, dec_lock, name, group, index), x_epoch=start_time,
                                    kind=e["kind"], aliases=aliases))
        names = ", ".join(f"{Path(p).name} ({t(CAN_CHOICES[ch]) if ch < len(CAN_CHOICES) else ch})" for p, ch in config.bus)
        info.append(t("DBC: {count} Signale dekodiert aus {files}", count=len(entries), files=names))
        if not entries:
            warnings.append(t("Die DBC passt zu keiner Botschaft der Aufzeichnung (CAN-IDs und Kanal prüfen)."))
        else:  # bei Bedarf: welche Datenbasen wurden tatsächlich gebraucht?
            decoded_names = {e["name"].rsplit(".", 1)[-1] for e in entries}
            unused = [Path(p).name for p, _ in config.bus if p in signal_names and not signal_names[p] & decoded_names]
            if unused:
                info.append(t("Nicht benötigt (keine passende Botschaft): {names}", names=", ".join(unused)))

    if config.a2l:
        table, per_file = {}, {}
        for path in config.a2l:
            part = parse_a2l(path)
            per_file[path] = set(part)
            for name, entry in part.items():
                table.setdefault(name, entry)        # die erste A2L mit diesem Namen gilt
        units = converted = 0
        notes, used = set(), set()
        for i, channel in enumerate(channels):
            key = next((n for n in _lookup_names(channel.name) if n in table), None)
            if key is None:
                continue
            match = table[key]
            used.add(key)
            if match.unit and not channel.unit:
                channel.unit = match.unit
                units += 1
            if config.a2l_convert and match.compu is not None:
                channels[i] = dataclasses.replace(channel, unit=match.unit or channel.unit,
                                                  loader=_converted_loader(channel.loader, match))
                converted += 1
            elif config.a2l_convert and match.compu_note:
                notes.add(match.compu_note)
        info.append(t("A2L {name}: {count} Messgrößen, {units} Einheiten ergänzt",
                      name=", ".join(Path(p).name for p in config.a2l), count=len(table), units=units)
                    + (t(", {count} Kanäle umgerechnet", count=converted) if config.a2l_convert else ""))
        unused = [Path(p).name for p in config.a2l if not per_file[p] & used]
        if unused and len(config.a2l) > 1:
            info.append(t("Nicht benötigt (keine passende Messgröße): {names}", names=", ".join(unused)))
        warnings += sorted(notes)

    for path in config.cdd:
        warnings.append(t("CDD {name} ist zugeordnet; die Auswertung von Diagnosedaten ist noch nicht eingebaut.",
                          name=Path(path).name))

    from .progress import Cancelled, check
    try:
        check()
        for channel in channels:
            if channel.label in preload or channel.name in preload:
                try:
                    channel.load()
                except Cancelled:
                    raise
                except LoadError:
                    pass  # erscheint beim erneuten Anhaken als Meldung
    except Cancelled:
        for item in opened:  # abgebrochen: neue Dekodierung wieder schließen
            item.close()
        raise
    return channels, info, warnings, opened


def _bus_messages(path: str) -> tuple[dict, list[str]]:
    from . import dbc
    return dbc.load(path)


def install_databases(dataset: Dataset, config: DatabaseConfig, result) -> None:
    """Ergebnis von apply_databases in das Dataset übernehmen (vorher geöffnete Dekodierungen schließen)."""
    channels, info, warnings, opened = result
    for item in dataset.extra.get("opened", []):
        item.close()
    dataset.channels = channels
    dataset.info = dataset.extra["base_info"] + info
    dataset.warnings = dataset.extra["base_warnings"] + warnings
    dataset.extra["opened"] = opened
    dataset.extra["config"] = config


def _decoded_loader(mdf, lock, name, group, index):
    from .loaders import _value_texts
    def loader():
        extra = {}
        with lock:
            sig = mdf.get(name, group=group, index=index)
            y = np.asarray(sig.samples)
            if y.ndim != 1 or y.dtype.kind not in "iufb":     # Wert->Text (DBC VAL_): Rohwerte, Texte für Anzeige
                converted = sig.samples
                sig = mdf.get(name, group=group, index=index, raw=True)
                y = np.asarray(sig.samples)
                if y.ndim == 1 and y.dtype.kind in "iufb":
                    table = _value_texts(y, converted)
                    if table:
                        extra["value_text"] = table
        if y.ndim != 1 or y.dtype.kind not in "iufb":
            raise LoadError(f"{name}: keine Zahlenwerte")
        unit = sig.unit.decode("latin-1") if isinstance(sig.unit, bytes) else (sig.unit or "")
        return sig.timestamps, y.astype(np.float64), unit, extra
    return loader


def _converted_loader(loader, match: A2LMeasurement):
    def converted():
        result = loader()
        x, y, unit = result[:3]
        return x, match.compu(np.asarray(y, dtype=np.float64)), match.unit or unit, *result[3:]
    return converted
