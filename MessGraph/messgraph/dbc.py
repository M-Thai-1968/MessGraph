"""DBC lesen und CAN-Botschaften dekodieren (ohne Zusatzpakete), vektorisiert mit numpy.

Unterstützt: Standard- und Extended-IDs, Intel (@1) und Motorola (@0), vorzeichenbehaftete Signale,
Faktor/Offset, Einheit, einfaches Multiplexing (M / mN), CAN FD bis 64 Byte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .data_model import LoadError
from .i18n import t

_BO = re.compile(r"^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\S+)")
_VALTYPE = re.compile(r"^SIG_VALTYPE_\s+(\d+)\s+(\w+)\s*:\s*([12])")
_SG = re.compile(r'^SG_\s+(\w+)\s*(M|m\d+)?\s*:\s*(\d+)\|(\d+)@([01])([+-])\s*\(\s*([^,]+)\s*,\s*([^)]+)\)\s*'
                 r'\[\s*([^|]*)\|\s*([^\]]*)\]\s*"([^"]*)"')


@dataclass
class Signal:
    name: str
    start: int
    length: int
    little_endian: bool
    signed: bool
    factor: float
    offset: float
    unit: str
    multiplexer: bool = False
    mux_value: int | None = None   # nur gültig, wenn der Multiplexer diesen Wert hat
    is_float: bool = False         # IEEE 754 (32 oder 64 Bit, SIG_VALTYPE_ bzw. ARXML)

    def bit_positions(self) -> list[int]:
        """Bitnummern (Byte*8 + Bit, Bit 0 = LSB) vom höchstwertigen zum niedrigstwertigen Bit."""
        if self.little_endian:
            return list(range(self.start + self.length - 1, self.start - 1, -1))
        positions, bit = [], self.start          # Motorola: Startbit ist das MSB, "Sägezahn"-Zählung
        for _ in range(self.length):
            positions.append(bit)
            bit = bit - 1 if bit % 8 else bit + 15
        return positions


@dataclass
class Message:
    frame_id: int
    extended: bool
    name: str
    length: int
    signals: list = field(default_factory=list)


def parse(path: str) -> dict:
    """Liest eine DBC. Liefert {(ID, extended): Message}."""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    messages, current, floats = {}, None, []
    for line in text.splitlines():
        line = line.strip()
        match = _VALTYPE.match(line)
        if match:
            floats.append((int(match.group(1)), match.group(2)))
            current = None
            continue
        match = _BO.match(line)
        if match:
            raw_id = int(match.group(1))
            extended = bool(raw_id & 0x80000000)
            current = Message(raw_id & 0x1FFFFFFF, extended, match.group(2), int(match.group(3)))
            if current.name != "VECTOR__INDEPENDENT_SIG_MSG":
                messages[(current.frame_id, extended)] = current
            continue
        if not line.startswith("SG_"):
            if line:
                current = None      # anderer Abschnitt (CM_, BA_, VAL_ ...): Signale gehören zu keiner Botschaft
            continue
        match = _SG.match(line)
        if match and current is not None:
            mux = match.group(2)
            current.signals.append(Signal(
                name=match.group(1), start=int(match.group(3)), length=int(match.group(4)),
                little_endian=match.group(5) == "1", signed=match.group(6) == "-",
                factor=float(match.group(7)), offset=float(match.group(8)), unit=match.group(11),
                multiplexer=mux == "M", mux_value=int(mux[1:]) if mux and mux.startswith("m") else None))
    for raw_id, name in floats:
        message = messages.get((raw_id & 0x1FFFFFFF, bool(raw_id & 0x80000000)))
        for signal in message.signals if message else []:
            if signal.name == name:
                signal.is_float = True
    if not messages:
        raise LoadError(t("Keine Botschaften in der DBC gefunden: {name}", name=Path(path).name))
    return messages


def load(path: str) -> tuple[dict, list[str]]:
    """Bus-Datenbasis nach Endung: DBC oder AUTOSAR-ARXML. Liefert (Botschaften, Hinweise)."""
    if path.lower().endswith((".arxml", ".xml")):
        from . import arxml
        return arxml.parse(path)
    return parse(path), []


def raw_values(data: np.ndarray, signal: Signal) -> np.ndarray:
    """data: (N, Bytes) uint8. Liefert die Rohwerte als float64 (bis 64 Bit, mit Vorzeichen)."""
    bits = np.unpackbits(data, axis=1, bitorder="little")          # Spalte Byte*8 + Bit
    positions = signal.bit_positions()
    if max(positions) >= bits.shape[1] or min(positions) < 0:
        return np.full(data.shape[0], np.nan)
    value = np.zeros(data.shape[0], dtype=np.uint64)
    for pos in positions:
        value = (value << np.uint64(1)) | bits[:, pos].astype(np.uint64)
    if signal.is_float and signal.length == 32:
        return value.astype(np.uint32).view(np.float32).astype(np.float64)
    if signal.is_float and signal.length == 64:
        return value.view(np.float64).copy()
    if signal.signed and signal.length < 64:
        sign = np.uint64(1) << np.uint64(signal.length - 1)
        out = value.astype(np.float64)
        negative = (value & sign) != 0
        out[negative] -= float(1 << signal.length)
        return out
    if signal.signed:
        return value.view(np.int64).astype(np.float64)
    return value.astype(np.float64)


def decode(message: Message, data: np.ndarray) -> dict:
    """Physikalische Werte je Signal: {Name: (Maske gültiger Zeilen, Werte)}."""
    out = {}
    mux_raw = None
    for signal in message.signals:
        if signal.multiplexer:
            mux_raw = raw_values(data, signal)
    for signal in message.signals:
        values = raw_values(data, signal) * signal.factor + signal.offset
        mask = np.ones(data.shape[0], dtype=bool)
        if signal.mux_value is not None and mux_raw is not None:
            mask = mux_raw == signal.mux_value
        out[signal.name] = (mask, values)
    return out
