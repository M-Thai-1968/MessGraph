"""Einstieg zum Laden: wählt den Leser nach der Dateiendung."""
from __future__ import annotations

import threading
from datetime import datetime
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .csv_reader import read_ascii
from .data_model import Channel, Dataset, LoadError
from . import downsample
from . import progress
from .i18n import t
from .tabular import build_dataset

ASCII_TYPES = (".csv", ".asc", ".txt", ".dat", ".tsv", ".log", ".prn")
SUPPORTED = (".mf4", ".mdf", ".blf", ".parquet") + ASCII_TYPES


def is_ascii(path: str) -> bool:
    return Path(path).suffix.lower() in ASCII_TYPES


def load_file(path: str, ascii_options: dict | None = None) -> Dataset:
    """ascii_options: Struktur einer CSV/ASCII-Datei (Kopfzeile, Trennzeichen ...), sonst automatisch."""
    ext = Path(path).suffix.lower()
    if ext in ASCII_TYPES:
        return read_ascii(path, ascii_options)
    if ext == ".parquet":
        return read_parquet(path)
    if ext in (".mf4", ".mdf"):   # .mdf: ASAM MDF 3.x (oder 4.x unter alter Endung), gleicher Leser
        return read_mf4(path)
    if ext == ".blf":
        from . import blf
        return blf.load(path)
    raise LoadError(t("Dateityp '{ext}' wird nicht unterstützt (mf4, mdf, blf, csv, asc, txt, dat, parquet).", ext=ext))


def _read_parquet_table(path: str, pq):
    """Liest blockweise, damit der Fortschritt sichtbar ist und abgebrochen werden kann."""
    parquet_file = getattr(pq, "ParquetFile", None)
    if parquet_file is None:
        progress.busy(t("Parquet lesen..."))
        return pq.read_table(path)
    pf = parquet_file(path)
    total = max(1, int(pf.metadata.num_rows))
    batches, rows = [], 0
    for batch in pf.iter_batches(batch_size=max(65_536, total // 50)):
        batches.append(batch)
        rows += batch.num_rows
        progress.step(rows / total, t("Parquet lesen: {done} von {total} Zeilen", done=progress.thousands(rows),
                                      total=progress.thousands(total)))
    if not batches:
        return pf.read()
    import pyarrow as pa
    try:  # Schema der Datei samt Pandas-Metadaten (Index, Datentypen)
        return pa.Table.from_batches(batches, schema=pf.schema_arrow)
    except Exception:
        return pa.Table.from_batches(batches)


def read_parquet(path: str) -> Dataset:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        try:
            progress.busy(t("Parquet lesen..."))
            df = pd.read_parquet(path)
        except ImportError as exc:
            raise LoadError(t("Für Parquet wird pyarrow benötigt: pip install pyarrow")) from exc
    else:
        with progress.section(0.0, 0.6, t("Parquet lesen...")):
            table = _read_parquet_table(path, pq)
        with progress.section(0.6, 0.7):
            progress.busy(t("In Tabelle umwandeln..."))
            df = table.to_pandas()
            del table
    if not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()
    df.columns = [str(c) for c in df.columns]
    with progress.section(0.7, 0.9, t("Spalten erkennen...")):
        dataset = build_dataset(path, df, info=["Parquet"])
    reduced = 0
    with progress.section(0.9, 1.0, downsample.config().describe()):
        for number, channel in enumerate(dataset.channels, 1):  # Downsampling je Signal
            channel.x, channel.y, channel.ds_note = downsample.apply(channel.x, channel.y)
            reduced += bool(channel.ds_note)
            progress.step(number / len(dataset.channels))
    dataset.info.append(downsample.config().describe())
    if reduced:
        sample = next(c.ds_note for c in dataset.channels if c.ds_note)
        dataset.info.append(t("{count} Signale reduziert, z. B. {note}", count=reduced, note=sample))
    return dataset


def _numeric_samples(samples) -> np.ndarray | None:
    arr = np.asarray(samples)
    if arr.ndim != 1 or arr.dtype.kind not in "iufb":
        return None
    return arr.astype(np.float64)


def _text(value) -> str:
    if isinstance(value, bytes):
        return value.decode("latin-1", errors="replace")
    return value if isinstance(value, str) else ""


BUS_FRAME_PREFIXES = ("CAN_DataFrame", "CAN_RemoteFrame", "CAN_ErrorFrame", "LIN_Frame",
                      "FLX_Frame", "ETH_Frame", "CANFD_DataFrame")


TEXT_TYPES_V4 = {6, 7, 8, 9, 10, 11, 12}   # MDF 4: Strings, Byte-Feld, MIME
TEXT_TYPES_V3 = {7, 8}                     # MDF 3: String, Byte-Feld


def _mf4_entries(mdf) -> list[dict]:
    """Alle Messkanäle ohne Zeitkanäle: {name, group, index, unit, kind, cycles}.

    Jeder Kanal ist über (Gruppe, Index) eindeutig. channels_db ist die stabile öffentliche Liste von asammdf;
    groups und masters_db dienen nur der Zusatzinformation (Einheit, Datentyp, Anzahl Werte) und dürfen fehlen.
    kind: "" darstellbar, "text" (VLSD-String, String, Byte-Feld), "empty" (0 Werte), "const" (1 Wert).
    """
    masters = getattr(mdf, "masters_db", None) or {}
    groups = getattr(mdf, "groups", None) or []
    v3 = str(getattr(mdf, "version", "4") or "4").startswith("3")
    entries, seen = [], set()
    for name, places in mdf.channels_db.items():
        if not name:
            continue
        for place in places:
            group, index = int(place[0]), int(place[1])
            if masters.get(group) == index or (group, index) in seen:
                continue
            unit, kind, cycles = "", "", None
            try:
                ch = groups[group].channels[index]
                if getattr(ch, "channel_type", 0) in (2, 3):  # Master oder virtueller Master
                    continue
                unit = _text(getattr(ch, "unit", ""))
                data_type = getattr(ch, "data_type", None)
                if (not v3 and getattr(ch, "channel_type", 0) == 1) or \
                        (isinstance(data_type, int) and data_type in (TEXT_TYPES_V3 if v3 else TEXT_TYPES_V4)):
                    kind = "text"
            except (IndexError, AttributeError, TypeError):
                pass
            try:
                cycles = int(groups[group].channel_group.cycles_nr)
            except (IndexError, AttributeError, TypeError, ValueError):
                cycles = None
            if not kind and cycles is not None and cycles < 2:
                kind = "empty" if cycles == 0 else "const"
            seen.add((group, index))
            entries.append({"name": name, "group": group, "index": index, "unit": unit, "kind": kind,
                            "cycles": cycles})
    entries.sort(key=lambda e: (e["group"], e["index"]))
    return entries


def _group_label(mdf, group: int) -> str:
    """Name der Kanalgruppe (bei Buslogging meist die Botschaft, z. B. IVT6_Msg_Result_I) oder ""."""
    try:
        cg = mdf.groups[group].channel_group
    except (IndexError, AttributeError, TypeError):
        return ""
    for attr in ("acq_name", "name"):
        text = _text(getattr(cg, attr, "") or "").strip()
        if text:
            return text
    source = getattr(cg, "acq_source", None)
    text = _text(getattr(source, "name", "") or "").strip() if source is not None else ""
    if text:
        return text
    comment = _text(getattr(cg, "comment", "") or "").strip()
    return comment if comment and len(comment) <= 60 and "\n" not in comment and "<" not in comment else ""


def mf4_display_names(mdf, entries: list[dict]) -> list[tuple[str, tuple]]:
    """Eindeutige Anzeigenamen (Name, frühere Namen) in der Reihenfolge von entries.

    Ein eindeutiger Kanalname bleibt, wie er ist. Bei Namenskonflikten: "Gruppe / Kanal" (z. B.
    IVT6_Msg_Result_I / IVT_Result_I), bei einer Gruppe mit nur einem Datenkanal oder ohne Gruppennamen
    "Kanal [g714]"; bleibt es doppelt, "[g714]" bzw. "[g714:i3]" angehängt. Frühere Namen ("Kanal (G714)")
    bleiben als Alias erhalten.
    """
    counts = Counter(e["name"] for e in entries)
    per_group = Counter(e["group"] for e in entries)
    shown = []
    for e in entries:
        name, g = e["name"], e["group"]
        if counts[name] == 1:
            shown.append(name)
            continue
        label = _group_label(mdf, g)
        if label and per_group[g] > 1 and label != name:
            shown.append(f"{label} / {name}")
        else:
            shown.append(f"{name} [g{g}]")
    for level in (1, 2):                                   # verbliebene Doppelte eindeutig machen
        dup = Counter(shown)
        for i, e in enumerate(entries):
            if dup[shown[i]] > 1:
                if level == 1 and f"[g{e['group']}]" not in shown[i]:
                    shown[i] = f"{shown[i]} [g{e['group']}]"
                elif level == 2:
                    shown[i] = f"{e['name']} [g{e['group']}:i{e['index']}]"
    result = []
    for e, display in zip(entries, shown):
        legacy = f"{e['name']} (G{e['group']})" if counts[e["name"]] > 1 else e["name"]
        aliases = (legacy,) if legacy != display else ()
        result.append((display, aliases))
    return result


def _value_texts(raw: np.ndarray, converted) -> dict | None:
    """Rohwert -> Text aus Wert->Text-Umrechnung (höchstens 256 verschiedene Werte)."""
    try:
        conv = np.asarray(converted)
        if conv.shape != raw.shape:
            return None
        values, first = np.unique(raw, return_index=True)
        if values.size > 256:
            return None
        table = {}
        for value, pos in zip(values, first):
            text = conv[pos]
            text = text.decode("latin-1", errors="replace") if isinstance(text, bytes) else str(text)
            if text and text != str(value):
                table[float(value)] = text.strip()
        return table or None
    except Exception:
        return None


def mf4_start_time(mdf) -> float | None:
    """Startzeit der Aufzeichnung als Wanduhr-Sekunden (Ortszeit)."""
    try:
        start = mdf.header.start_time
    except AttributeError:
        return None
    if not isinstance(start, datetime):
        return None
    if start.tzinfo is not None:
        start = start.astimezone().replace(tzinfo=None)
    if start.year < 1990:  # nicht gesetzt
        return None
    return (start - datetime(1970, 1, 1)).total_seconds()


def read_mf4(path: str) -> Dataset:
    """Listet die Kanäle sofort; Messwerte werden erst bei Bedarf gelesen."""
    try:
        from asammdf import MDF
    except ImportError as exc:
        raise LoadError(t("Für MF4 wird asammdf benötigt: pip install asammdf")) from exc

    progress.busy(t("MF4 öffnen (Blöcke und Kanäle lesen)..."))
    try:
        mdf = MDF(path)
    except Exception as exc:  # asammdf meldet Dateifehler mit vielen Typen
        raise LoadError(t("MF4 nicht lesbar: {error}", error=f"{type(exc).__name__}: {exc}")) from exc

    lock = threading.Lock()  # asammdf ist nicht threadsicher

    def make_loader(name: str, group: int, index: int):
        def loader():
            extra = {}
            with lock:
                sig = mdf.get(name, group=group, index=index)
                y = _numeric_samples(sig.samples)
                if y is None:  # Wert->Text-Umrechnung: Rohwerte als Zahlen, Texte für Wertanzeige/Tooltip
                    converted = sig.samples
                    sig = mdf.get(name, group=group, index=index, raw=True)
                    y = _numeric_samples(sig.samples)
                    if y is not None:
                        table = _value_texts(np.asarray(sig.samples), converted)
                        if table:
                            extra["value_text"] = table
            if y is None:
                raise LoadError(t("{name}: keine Zahlenwerte (Text, Byte-Feld oder strukturierte Daten)", name=name))
            return sig.timestamps, y, _text(sig.unit), extra   # jede Größe mit eigener Zeitachse, kein Resampling
        return loader

    try:
        progress.step(0.8, t("Kanalliste erstellen..."))
        entries = _mf4_entries(mdf)
    except progress.Cancelled:
        mdf.close()
        raise
    except Exception as exc:
        mdf.close()
        raise LoadError(t("MF4-Kanalliste nicht lesbar: {error}", error=f"{type(exc).__name__}: {exc}")) from exc
    if not entries:
        mdf.close()
        raise LoadError(t("Die MF4-Datei enthält keine Messkanäle."))

    start = mf4_start_time(mdf)
    channels = []
    for e, (shown, aliases) in zip(entries, mf4_display_names(mdf, entries)):
        channels.append(Channel(name=shown, unit=e["unit"], x_name="Zeit", x_unit="s", source=path,
                                loader=make_loader(e["name"], e["group"], e["index"]), x_epoch=start,
                                kind=e["kind"], aliases=aliases))
    warnings = []      # Hinweis zu Busrohdaten bildet die Dateiliste aus den tatsächlichen Kanalnamen
    bus_raw = any(e["name"].startswith(BUS_FRAME_PREFIXES) for e in entries)
    renamed = sum(1 for c, e in zip(channels, entries) if c.name != e["name"])
    skipped = Counter(c.kind for c in channels if not c.plottable)
    groups = len(getattr(mdf, "groups", []) or [])
    version = str(getattr(mdf, "version", "") or "")
    if path.lower().endswith(".mdf") or (version and not version.startswith("4")):
        first = t("MDF {version}: {count} Kanäle in {groups} Gruppen", version=version or "3", count=len(channels),
                  groups=groups)
    else:
        first = t("MF4: {count} Kanäle in {groups} Gruppen", count=len(channels), groups=groups)
    info = [first,
            t("Messwerte werden beim Auswählen geladen"), downsample.config().describe()]
    if renamed:
        info.append(t("{count} Kanäle mit doppeltem Namen: als \"Gruppe / Kanal\" bzw. \"Kanal [gN]\" benannt",
                      count=renamed))
    if skipped:
        info.append(t("Nicht darstellbar (in der Liste grau): {text} Text/Byte-Feld, {const} mit 1 Wert, {empty} ohne Werte",
                      text=skipped.get("text", 0), const=skipped.get("const", 0), empty=skipped.get("empty", 0)))
    if start is not None:
        from .timeparse import format_wallclock
        info.append(t("Start: {time}", time=format_wallclock(start)))
    return Dataset(path=path, channels=channels, info=info, warnings=warnings, closer=mdf.close,
                   extra={"mdf": mdf, "lock": lock, "base": list(channels), "bus_raw": bus_raw,
                          "start": start, "base_info": list(info), "base_warnings": list(warnings)})
