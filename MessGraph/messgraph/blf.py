"""Vector BLF (Binary Logging Format) lesen, ohne Zusatzpakete.

Eine BLF enthält Busbotschaften (CAN, CAN FD), keine physikalischen Werte. Ohne DBC zeigt MessGraph je
Botschaft (Bus, ID) die Datenbytes als Signale; mit DBC (Dialog "Datenbasen...") die dekodierten Signale.

Aufbau: Dateikopf "LOGG" (Startzeit als SYSTEMTIME), danach Objekte "LOBJ". Die Botschaften liegen meist
in LOG_CONTAINER-Objekten (zlib-komprimiert); ein Objekt kann über zwei Container reichen.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from . import progress
from .data_model import Channel, Dataset, LoadError
from .i18n import t

FILE_HEADER = struct.Struct("<4sLBBBBBBBBQQLL8H8H")
OBJ_BASE = struct.Struct("<4sHHLL")
OBJ_V1 = struct.Struct("<LHHQ")
OBJ_V2 = struct.Struct("<LBBHQQ")
CONTAINER = struct.Struct("<H6xL4x")
CAN_MSG = struct.Struct("<HBBL8s")
CAN_FD_MSG = struct.Struct("<HBBLLBBB5x64s")
CAN_FD_MSG_64 = struct.Struct("<BBBBLLLLLLLHBBL")

LOG_CONTAINER, CAN_MESSAGE, CAN_MESSAGE2, CAN_FD_MESSAGE, CAN_FD_MESSAGE_64 = 10, 1, 86, 100, 101
TIME_TEN_MICS, TIME_ONE_NANS = 0x1, 0x2
CAN_MSG_EXT = 0x80000000
REMOTE_FLAG = 0x80
DLC_BYTES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64]


@dataclass
class Frames:
    """Alle Botschaften einer BLF als Spalten."""
    time: np.ndarray        # Sekunden ab Messbeginn
    bus: np.ndarray         # Kanalnummer wie in der BLF (CAN 1 = 1)
    ident: np.ndarray       # Botschafts-ID ohne Extended-Kennung
    extended: np.ndarray    # bool
    length: np.ndarray      # Datenbytes
    data: np.ndarray        # (N, 64) uint8
    start: float | None     # Wanduhr-Sekunden ab 1970 für time = 0

    def keys(self) -> list[tuple[int, int, bool]]:
        """(Bus, ID, extended) aller vorkommenden Botschaften, sortiert."""
        if not self.time.size:
            return []
        combined = np.unique(np.stack([self.bus, self.ident, self.extended.astype(np.int64)], axis=1), axis=0)
        return [(int(b), int(i), bool(e)) for b, i, e in combined]

    def select(self, bus: int | None, ident: int, extended: bool) -> np.ndarray:
        mask = (self.ident == ident) & (self.extended == extended)
        if bus:
            mask &= self.bus == bus
        return mask


def _systemtime(values) -> float | None:
    year, month, _dow, day, hour, minute, second, millis = values
    try:
        when = datetime(year, month, day, hour, minute, second, millis * 1000)
    except ValueError:
        return None
    return (when - datetime(1970, 1, 1)).total_seconds()


def read(path: str) -> Frames:
    raw = Path(path).read_bytes()
    if len(raw) < FILE_HEADER.size or raw[:4] != b"LOGG":
        raise LoadError(t("Keine gültige BLF-Datei (Kennung LOGG fehlt)."))
    header = FILE_HEADER.unpack_from(raw, 0)
    header_size, object_count = header[1], header[12]
    start = _systemtime(header[14:22])
    times, buses, idents, exts, lengths, payloads = [], [], [], [], [], []

    def handle(buf: bytes, pos: int) -> int:
        """Ein Objekt ab pos auswerten. Liefert die nächste Position oder -1, wenn es nicht vollständig ist."""
        found = buf.find(b"LOBJ", pos, pos + 8)   # Füllbytes je nach Schreiber 0 bis 7: Kennung suchen
        if found < 0:
            if pos + 8 > len(buf):
                return -1                          # Rest steht im nächsten Container
            found = buf.find(b"LOBJ", pos)         # beschädigte Stelle überspringen
            if found < 0:
                return len(buf)
        pos = found
        if pos + OBJ_BASE.size > len(buf):
            return -1
        sig, obj_header_size, header_version, obj_size, obj_type = OBJ_BASE.unpack_from(buf, pos)
        if obj_size < OBJ_BASE.size:
            return pos + 4
        end = pos + obj_size
        if end > len(buf):
            return -1
        body = pos + OBJ_BASE.size
        if header_version == 1:
            flags, _client, _version, timestamp = OBJ_V1.unpack_from(buf, body)
            body += OBJ_V1.size
        elif header_version == 2:
            flags, _status, _res, _version, timestamp, _orig = OBJ_V2.unpack_from(buf, body)
            body += OBJ_V2.size
        else:
            return end
        factor = 1e-5 if flags == TIME_TEN_MICS else 1e-9
        stamp = timestamp * factor
        try:
            if obj_type in (CAN_MESSAGE, CAN_MESSAGE2):
                channel, mflags, dlc, ident, data = CAN_MSG.unpack_from(buf, body)
                if not mflags & REMOTE_FLAG:
                    n = min(dlc, 8)
                    times.append(stamp); buses.append(channel); idents.append(ident & 0x1FFFFFFF)
                    exts.append(bool(ident & CAN_MSG_EXT)); lengths.append(n); payloads.append(data[:n])
            elif obj_type == CAN_FD_MESSAGE:
                channel, mflags, dlc, ident, _fl, _bc, _fd, valid, data = CAN_FD_MSG.unpack_from(buf, body)
                n = min(valid or DLC_BYTES[min(dlc, 15)], 64)
                times.append(stamp); buses.append(channel); idents.append(ident & 0x1FFFFFFF)
                exts.append(bool(ident & CAN_MSG_EXT)); lengths.append(n); payloads.append(data[:n])
            elif obj_type == CAN_FD_MESSAGE_64:
                fields = CAN_FD_MSG_64.unpack_from(buf, body)
                channel, dlc, valid, ident = fields[0], fields[1], fields[2], fields[4]
                n = min(valid or DLC_BYTES[min(dlc, 15)], 64)
                data_start = body + CAN_FD_MSG_64.size
                times.append(stamp); buses.append(channel); idents.append(ident & 0x1FFFFFFF)
                exts.append(bool(ident & CAN_MSG_EXT)); lengths.append(n)
                payloads.append(buf[data_start:data_start + n])
        except struct.error:
            pass
        return end

    pos, tail, done = header_size, b"", 0
    total = max(1, len(raw))
    while pos + OBJ_BASE.size <= len(raw):
        found = raw.find(b"LOBJ", pos, pos + 8)
        if found < 0:
            found = raw.find(b"LOBJ", pos)
            if found < 0:
                break
        pos = found
        sig, _hs, _hv, obj_size, obj_type = OBJ_BASE.unpack_from(raw, pos)
        if obj_size < OBJ_BASE.size:
            pos += 4
            continue
        if obj_type == LOG_CONTAINER:
            method, _size = CONTAINER.unpack_from(raw, pos + OBJ_BASE.size)
            payload = raw[pos + OBJ_BASE.size + CONTAINER.size:pos + obj_size]
            if method == 2:
                try:
                    payload = zlib.decompress(payload)
                except zlib.error as exc:
                    raise LoadError(t("BLF-Container nicht lesbar: {error}", error=exc)) from exc
            buf = tail + payload
            inner = 0
            while True:
                nxt = handle(buf, inner)
                if nxt < 0:
                    break
                inner = nxt
            tail = buf[inner:]
        else:
            handle(raw, pos)
        pos += obj_size
        done += 1
        if done % 200 == 0:
            progress.step(pos / total, t("BLF lesen: {count} Botschaften", count=f"{len(times):,}".replace(",", ".")))
    data = np.zeros((len(payloads), 64), dtype=np.uint8)
    for row, chunk in enumerate(payloads):
        if chunk:
            data[row, :len(chunk)] = np.frombuffer(bytes(chunk), dtype=np.uint8)
    frames = Frames(np.asarray(times, dtype=np.float64), np.asarray(buses, dtype=np.int64),
                    np.asarray(idents, dtype=np.int64), np.asarray(exts, dtype=bool),
                    np.asarray(lengths, dtype=np.int64), data, start)
    order = np.argsort(frames.time, kind="stable")
    if frames.time.size and np.any(np.diff(frames.time) < 0):
        for name in ("time", "bus", "ident", "extended", "length", "data"):
            setattr(frames, name, getattr(frames, name)[order])
    return frames


def key_label(bus: int, ident: int, extended: bool) -> str:
    return f"0x{ident:0{8 if extended else 3}X} (CAN {bus})"


def raw_channels(path: str, frames: Frames, skip: set | None = None) -> list[Channel]:
    """Ohne DBC: je Botschaft ihre Datenbytes als Signale (Werte 0..255)."""
    channels = []
    for bus, ident, extended in frames.keys():
        if skip and (ident, extended) in skip:
            continue
        mask = frames.select(bus, ident, extended)
        size = int(frames.length[mask].max()) if mask.any() else 0
        x = frames.time[mask]
        for byte in range(size):
            channels.append(Channel(name=f"{key_label(bus, ident, extended)} Byte {byte}", source=path, x=x,
                                    y=frames.data[mask, byte].astype(np.float64), x_epoch=frames.start))
    return channels


def load(path: str) -> Dataset:
    frames = read(path)
    if not frames.time.size:
        raise LoadError(t("Die BLF enthält keine CAN-Botschaften."))
    keys = frames.keys()
    buses = sorted({b for b, _i, _e in keys})
    info = [t("BLF (Vector): {count} CAN-Botschaften, {ids} IDs auf {buses}", count=f"{frames.time.size:,}".replace(",", "."),
              ids=len({(i, e) for _b, i, e in keys}), buses=", ".join(f"CAN {b}" for b in buses)),
            t("Ohne DBC: Datenbytes je Botschaft. Signale über \"Datenbasen...\" mit einer DBC dekodieren.")]
    channels = raw_channels(path, frames)
    dataset = Dataset(path=path, channels=channels, info=list(info))
    dataset.extra.update({"blf": frames, "base": list(channels), "base_info": list(info), "base_warnings": [],
                          "start": frames.start})
    return dataset


def apply_dbc(dataset: Dataset, config) -> tuple[list[Channel], list[str], list[str], list]:
    """Signale aller zugeordneten DBC/ARXML dekodieren; Botschaften ohne Eintrag bleiben als Datenbytes.

    Mehrere Datenbasen ergänzen sich; kennt schon eine frühere Datei die Botschaft, gilt diese.
    """
    from . import dbc, downsample
    frames: Frames = dataset.extra["blf"]
    bus_files = config.bus
    missing = [p for p, _ in bus_files if not Path(p).is_file()]
    if missing:
        raise LoadError(t("Datenbasis nicht gefunden: {names}", names=", ".join(missing)))
    progress.busy(t("DBC dekodieren (Busrohdaten in Signale umrechnen)..."))
    channels, known, info, warnings = [], set(), [], []
    names_used: dict[str, int] = {}
    present = frames.keys()
    decoded, unused = set(), []
    for number, (path, bus_filter) in enumerate(bus_files):
        messages, notes = dbc.load(path)
        warnings += notes
        hits = 0
        for bus, ident, extended in present:
            if bus_filter and bus != bus_filter:
                continue
            message = messages.get((ident, extended))
            if message is None or (bus, ident, extended) in decoded:
                continue
            decoded.add((bus, ident, extended))
            known.add((ident, extended))
            hits += 1
            mask = frames.select(bus, ident, extended)
            data = frames.data[mask]
            x_all = frames.time[mask]
            for name, (valid, values) in dbc.decode(message, data).items():
                signal = next(s for s in message.signals if s.name == name)
                multi_bus = len({b for b, i, e in present if (i, e) == (ident, extended)}) > 1
                label = f"{name} (CAN {bus})" if multi_bus else name
                if label in names_used:          # gleicher Signalname in mehreren Botschaften
                    label = f"{message.name}.{label}"
                names_used[label] = 1
                x, y = x_all[valid], values[valid]
                x, y, note = downsample.apply(x, y) if downsample.applies(dataset.path) else (x, y, "")
                channels.append(Channel(name=label, unit=signal.unit, source=dataset.path, x=x, y=y,
                                        x_epoch=frames.start, ds_note=note))
        progress.step((number + 1) / len(bus_files))
        if hits:
            text = ("ARXML {name}: {count} Botschaften der BLF dekodiert" if path.lower().endswith(".arxml")
                    else "DBC {name}: {count} Botschaften der BLF dekodiert")
            info.append(t(text, name=Path(path).name, count=hits))
        else:
            unused.append(Path(path).name)
    if unused and decoded:   # bei Bedarf: nicht gebrauchte Datenbasen nur melden
        info.append(t("Nicht benötigt (keine passende Botschaft): {names}", names=", ".join(unused)))
    elif unused:
        for name in unused:
            warnings.append(t("{name}: keine passende Botschaft in der BLF (Kanal und IDs prüfen).", name=name))
    channels += raw_channels(dataset.path, frames, skip=known)
    if config.a2l or config.cdd:
        warnings.append(t("A2L und CDD werden für BLF nicht ausgewertet, nur DBC und ARXML."))
    return channels, info, warnings, []


# ---------------------------------------------------------------- Schreiben (Beispieldaten, Tests)
def write(path: str, messages: list[tuple[float, int, int, bool, bytes]], start: datetime | None = None,
          per_container: int = 500) -> str:
    """Schreibt CAN- bzw. CAN-FD-Botschaften (Zeit s, Bus, ID, extended, Daten) als BLF mit zlib-Containern."""
    start = start or datetime(2026, 11, 9, 8, 0, 0)
    objects = []
    for stamp, bus, ident, extended, data in messages:
        ts = int(round(stamp * 1e9))
        arb = ident | (CAN_MSG_EXT if extended else 0)
        if len(data) <= 8:
            body = CAN_MSG.pack(bus, 0, len(data), arb, bytes(data).ljust(8, b"\0"))
            obj_type = CAN_MESSAGE
        else:
            dlc = DLC_BYTES.index(next(n for n in DLC_BYTES if n >= len(data)))
            body = CAN_FD_MSG.pack(bus, 0, dlc, arb, 0, 0, 1, len(data), bytes(data).ljust(64, b"\0"))
            obj_type = CAN_FD_MESSAGE
        header_size = OBJ_BASE.size + OBJ_V1.size
        size = header_size + len(body)
        obj = OBJ_BASE.pack(b"LOBJ", header_size, 1, size, obj_type) + OBJ_V1.pack(TIME_ONE_NANS, 0, 0, ts) + body
        objects.append(obj + b"\0" * (size % 4))
    out = bytearray()
    for i in range(0, len(objects), per_container):
        plain = b"".join(objects[i:i + per_container])
        packed = zlib.compress(plain)
        size = OBJ_BASE.size + CONTAINER.size + len(packed)
        out += OBJ_BASE.pack(b"LOBJ", 16, 1, size, LOG_CONTAINER) + CONTAINER.pack(2, len(plain)) + packed
        out += b"\0" * (size % 4)
    st = (start.year, start.month, start.isoweekday() % 7, start.day, start.hour, start.minute, start.second,
          start.microsecond // 1000)
    header = FILE_HEADER.pack(b"LOGG", 144, 0, 1, 0, 0, 4, 7, 1, 0, 144 + len(out), 0, len(messages), 0, *st, *st)
    Path(path).write_bytes(header.ljust(144, b"\0") + bytes(out))
    return path
