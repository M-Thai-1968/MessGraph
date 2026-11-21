"""AUTOSAR-ARXML lesen: CAN-Botschaften und Signale wie aus einer DBC (ohne Zusatzpakete).

Ausgewertet werden (AUTOSAR 4, tolerant auch 3.x):
    CAN-FRAME-TRIGGERING   IDENTIFIER, CAN-ADDRESSING-MODE (EXTENDED), FRAME-REF
    CAN-FRAME / FRAME      FRAME-LENGTH, PDU-TO-FRAME-MAPPING (PDU-REF, START-POSITION)
    I-SIGNAL-I-PDU         I-SIGNAL-TO-I-PDU-MAPPING (I-SIGNAL-REF, START-POSITION, PACKING-BYTE-ORDER)
    I-SIGNAL / SYSTEM-SIGNAL   LENGTH, COMPU-METHOD-REF, UNIT-REF, BASE-TYPE-REF (2C = mit Vorzeichen, IEEE754)
    COMPU-METHOD           COMPU-RATIONAL-COEFFS (Faktor/Offset), UNIT-REF
Bitpositionen nach AUTOSAR: Little Endian (MOST-SIGNIFICANT-BYTE-LAST) zählt ab dem niedrigstwertigen Bit,
Big Endian (MOST-SIGNIFICANT-BYTE-FIRST) ab dem höchstwertigen Bit, also wie Intel/Motorola in der DBC.
Gemultiplexte und Container-PDUs werden gemeldet und übersprungen.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .data_model import LoadError
from .dbc import Message, Signal
from .i18n import t


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _child(elem, name):
    for sub in elem:
        if _local(sub.tag) == name:
            return sub
    return None


def _text(elem, name, default=""):
    sub = _child(elem, name) if elem is not None else None
    return (sub.text or "").strip() if sub is not None and sub.text else default


def _find(elem, name):
    """Erstes Element dieses Namens unterhalb (beliebige Tiefe)."""
    if elem is None:
        return None
    for sub in elem.iter():
        if sub is not elem and _local(sub.tag) == name:
            return sub
    return None


def _number(text: str, default: float = 0.0) -> float:
    text = (text or "").strip()
    if not text:
        return default
    try:
        return float(int(text, 0))
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return default


class _Index:
    """Elemente über ihren AUTOSAR-Pfad (/Paket/Unterpaket/Name) und hilfsweise über den Namen."""

    def __init__(self, root):
        self.by_path, self.by_name = {}, {}
        self._walk(root, "")

    def _walk(self, elem, path):
        name = _text(elem, "SHORT-NAME")
        if name:
            path = f"{path}/{name}"
            self.by_path[path] = elem
            self.by_name.setdefault(name, elem)
        for sub in elem:
            self._walk(sub, path)

    def ref(self, elem, name):
        """Ziel einer Referenz <NAME DEST="...">/Pfad</NAME> unterhalb von elem."""
        node = _child(elem, name) if elem is not None else None
        if node is None:
            node = _find(elem, name)
        if node is None or not (node.text or "").strip():
            return None
        target = node.text.strip()
        found = self.by_path.get(target)
        return found if found is not None else self.by_name.get(target.rsplit("/", 1)[-1])


def _unit(index: _Index, holder) -> str:
    unit = index.ref(holder, "UNIT-REF")
    if unit is None:
        return ""
    return _text(unit, "DISPLAY-NAME") or _text(unit, "SHORT-NAME")


def _compu(index: _Index, compu) -> tuple[float, float, str]:
    """(Faktor, Offset, Einheit) aus der ersten linearen Stufe der COMPU-METHOD."""
    if compu is None:
        return 1.0, 0.0, ""
    unit = _unit(index, compu)
    coeffs = _find(compu, "COMPU-RATIONAL-COEFFS")
    if coeffs is None:
        return 1.0, 0.0, unit
    num, den = _values(_child(coeffs, "COMPU-NUMERATOR")), _values(_child(coeffs, "COMPU-DENOMINATOR"))
    offset = num[0] if num else 0.0
    factor = num[1] if len(num) > 1 else 1.0
    divisor = den[0] if den and den[0] else 1.0
    return factor / divisor, offset / divisor, unit


def _values(elem) -> list[float]:
    return [] if elem is None else [_number(v.text) for v in elem if _local(v.tag) == "V"]


def _signal(index: _Index, mapping, offset: int, notes: list) -> Signal | None:
    isignal = index.ref(mapping, "I-SIGNAL-REF")
    if isignal is None:
        isignal = index.ref(mapping, "SIGNAL-REF")
    if isignal is None:
        return None
    system = index.ref(isignal, "SYSTEM-SIGNAL-REF") if _local(isignal.tag) != "SYSTEM-SIGNAL" else isignal
    length = int(_number(_text(isignal, "LENGTH") or _text(system, "LENGTH")))
    if length <= 0:
        return None
    # physikalische Umrechnung: zuerst am System-Signal, sonst an der Netzdarstellung des I-Signals
    compu = index.ref(_child(system, "PHYSICAL-PROPS") if system is not None else None, "COMPU-METHOD-REF")
    if compu is None:
        compu = index.ref(isignal, "COMPU-METHOD-REF")
    factor, add, unit = _compu(index, compu)
    if not unit and system is not None:
        props = _child(system, "PHYSICAL-PROPS")
        unit = _unit(index, props if props is not None else system)
    base = index.ref(isignal, "BASE-TYPE-REF")
    encoding = _text(base, "BASE-TYPE-ENCODING").upper() if base is not None else ""
    is_float = "IEEE754" in encoding or encoding == "FLOAT"
    signed = encoding.startswith("2C") or encoding == "SIGNED"
    order = _text(mapping, "PACKING-BYTE-ORDER").upper()
    little = order != "MOST-SIGNIFICANT-BYTE-FIRST"
    start = int(_number(_text(mapping, "START-POSITION"), -1))
    if start < 0:
        return None
    name = re.sub(r"\W", "_", _text(isignal, "SHORT-NAME") or _text(mapping, "SHORT-NAME") or "Signal")
    if is_float and length not in (32, 64):
        notes.append(t("ARXML: {name} hat Gleitkomma mit {bits} Bit, wird als Ganzzahl gelesen.", name=name, bits=length))
        is_float = False
    return Signal(name=name, start=start + offset, length=length, little_endian=little, signed=signed,
                  factor=factor, offset=add, unit=unit, is_float=is_float)


def parse(path: str) -> tuple[dict, list[str]]:
    """Liefert ({(ID, extended): Message}, Hinweise)."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise LoadError(t("ARXML nicht lesbar: {error}", error=exc)) from exc
    index = _Index(root)
    messages, notes, skipped = {}, [], set()
    for trig in root.iter():
        if _local(trig.tag) != "CAN-FRAME-TRIGGERING":
            continue
        ident_text = _text(trig, "IDENTIFIER")
        frame = index.ref(trig, "FRAME-REF")
        if not ident_text or frame is None:
            continue
        ident = int(_number(ident_text))
        mode = _text(trig, "CAN-ADDRESSING-MODE").upper()
        extended = mode == "EXTENDED" or ident > 0x7FF
        frame_name = re.sub(r"\W", "_", _text(frame, "SHORT-NAME") or f"ID_{ident:X}")
        message = Message(ident & 0x1FFFFFFF, extended, frame_name, int(_number(_text(frame, "FRAME-LENGTH"), 8)))
        for mapping in frame.iter():
            if _local(mapping.tag) != "PDU-TO-FRAME-MAPPING":
                continue
            pdu = index.ref(mapping, "PDU-REF")
            if pdu is None:
                continue
            kind = _local(pdu.tag)
            if kind in ("MULTIPLEXED-I-PDU", "CONTAINER-I-PDU", "SECURED-I-PDU"):
                skipped.add(f"{_text(pdu, 'SHORT-NAME')} ({kind})")
                continue
            offset = int(_number(_text(mapping, "START-POSITION"), 0))
            for sig_map in pdu.iter():
                tag = _local(sig_map.tag)
                if tag.endswith("TO-I-PDU-MAPPING") or tag == "SIGNAL-TO-PDU-MAPPING":
                    signal = _signal(index, sig_map, offset, notes)
                    if signal is not None and all(s.name != signal.name for s in message.signals):
                        message.signals.append(signal)
        key = (message.frame_id, extended)
        if key in messages:   # gleiche ID in mehreren Clustern: Signale zusammenführen
            known = {s.name for s in messages[key].signals}
            messages[key].signals += [s for s in message.signals if s.name not in known]
        elif message.signals:
            messages[key] = message
    if skipped:
        notes.append(t("ARXML: {count} gemultiplexte oder Container-PDUs übersprungen: {names}",
                       count=len(skipped), names=", ".join(sorted(skipped)[:5])))
    if not messages:
        raise LoadError(t("Keine CAN-Botschaften in der ARXML gefunden: {name}", name=Path(path).name))
    return messages, notes


def to_dbc(messages: dict) -> str:
    """DBC-Text derselben Botschaften (für asammdf beim Dekodieren von MF4/MDF)."""
    lines = ['VERSION ""', "", "NS_ :", "", "BS_:", "", "BU_:", ""]
    floats = []
    for message in messages.values():
        raw = message.frame_id | (0x80000000 if message.extended else 0)
        lines.append(f"BO_ {raw} {message.name}: {message.length} Vector__XXX")
        for s in message.signals:
            unit = s.unit.replace('"', "'")
            lines.append(f' SG_ {s.name} : {s.start}|{s.length}@{1 if s.little_endian else 0}{"-" if s.signed else "+"} '
                         f'({s.factor!r},{s.offset!r}) [0|0] "{unit}" Vector__XXX')
            if s.is_float:
                floats.append(f"SIG_VALTYPE_ {raw} {s.name} : {1 if s.length == 32 else 2};")
        lines.append("")
    return "\n".join(lines + floats) + "\n"


def from_messages(messages, package: str = "MessGraph") -> str:
    """Minimale AUTOSAR-4-ARXML mit den Botschaften (für Beispieldaten und Tests)."""
    from xml.sax.saxutils import escape

    trig, frames, pdus, sigs, compus, units = [], [], [], [], [], {}
    for m in (messages.values() if isinstance(messages, dict) else messages):
        trig.append(f"<CAN-FRAME-TRIGGERING><SHORT-NAME>T_{m.name}</SHORT-NAME>"
                    f'<FRAME-REF DEST="CAN-FRAME">/{package}/Frames/{m.name}</FRAME-REF>'
                    f"<CAN-ADDRESSING-MODE>{'EXTENDED' if m.extended else 'STANDARD'}</CAN-ADDRESSING-MODE>"
                    f"<IDENTIFIER>{m.frame_id}</IDENTIFIER></CAN-FRAME-TRIGGERING>")
        frames.append(f"<CAN-FRAME><SHORT-NAME>{m.name}</SHORT-NAME><FRAME-LENGTH>{m.length}</FRAME-LENGTH>"
                      f"<PDU-TO-FRAME-MAPPINGS><PDU-TO-FRAME-MAPPING><SHORT-NAME>M</SHORT-NAME>"
                      f'<PDU-REF DEST="I-SIGNAL-I-PDU">/{package}/Pdus/{m.name}_Pdu</PDU-REF>'
                      f"<START-POSITION>0</START-POSITION></PDU-TO-FRAME-MAPPING></PDU-TO-FRAME-MAPPINGS></CAN-FRAME>")
        maps = []
        for s in m.signals:
            sid = f"{m.name}_{s.name}"
            order = "MOST-SIGNIFICANT-BYTE-LAST" if s.little_endian else "MOST-SIGNIFICANT-BYTE-FIRST"
            maps.append(f"<I-SIGNAL-TO-I-PDU-MAPPING><SHORT-NAME>{sid}</SHORT-NAME>"
                        f'<I-SIGNAL-REF DEST="I-SIGNAL">/{package}/Signals/{s.name}</I-SIGNAL-REF>'
                        f"<PACKING-BYTE-ORDER>{order}</PACKING-BYTE-ORDER><START-POSITION>{s.start}</START-POSITION>"
                        f"</I-SIGNAL-TO-I-PDU-MAPPING>")
            base = "float" if s.is_float else ("sint" if s.signed else "uint")
            sigs.append(f"<I-SIGNAL><SHORT-NAME>{s.name}</SHORT-NAME><LENGTH>{s.length}</LENGTH>"
                        f"<NETWORK-REPRESENTATION-PROPS><SW-DATA-DEF-PROPS-VARIANTS><SW-DATA-DEF-PROPS-CONDITIONAL>"
                        f'<BASE-TYPE-REF DEST="SW-BASE-TYPE">/{package}/Types/{base}</BASE-TYPE-REF>'
                        f"<COMPU-METHOD-REF DEST=\"COMPU-METHOD\">/{package}/Compu/{s.name}</COMPU-METHOD-REF>"
                        f"</SW-DATA-DEF-PROPS-CONDITIONAL></SW-DATA-DEF-PROPS-VARIANTS></NETWORK-REPRESENTATION-PROPS>"
                        f"</I-SIGNAL>")
            unit_ref = ""
            if s.unit:
                key = re.sub(r"\W", "_", s.unit) or "u"
                units[key] = s.unit
                unit_ref = f'<UNIT-REF DEST="UNIT">/{package}/Units/{key}</UNIT-REF>'
            compus.append(f"<COMPU-METHOD><SHORT-NAME>{s.name}</SHORT-NAME><CATEGORY>LINEAR</CATEGORY>{unit_ref}"
                          f"<COMPU-INTERNAL-TO-PHYS><COMPU-SCALES><COMPU-SCALE><COMPU-RATIONAL-COEFFS>"
                          f"<COMPU-NUMERATOR><V>{s.offset!r}</V><V>{s.factor!r}</V></COMPU-NUMERATOR>"
                          f"<COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR></COMPU-RATIONAL-COEFFS></COMPU-SCALE>"
                          f"</COMPU-SCALES></COMPU-INTERNAL-TO-PHYS></COMPU-METHOD>")
        pdus.append(f"<I-SIGNAL-I-PDU><SHORT-NAME>{m.name}_Pdu</SHORT-NAME><LENGTH>{m.length}</LENGTH>"
                    f"<I-SIGNAL-TO-PDU-MAPPINGS>{''.join(maps)}</I-SIGNAL-TO-PDU-MAPPINGS></I-SIGNAL-I-PDU>")
    unit_xml = "".join(f"<UNIT><SHORT-NAME>{k}</SHORT-NAME><DISPLAY-NAME>{escape(v)}</DISPLAY-NAME></UNIT>"
                       for k, v in units.items())
    types = "".join(f"<SW-BASE-TYPE><SHORT-NAME>{n}</SHORT-NAME><BASE-TYPE-ENCODING>{e}</BASE-TYPE-ENCODING></SW-BASE-TYPE>"
                    for n, e in (("uint", "NONE"), ("sint", "2C"), ("float", "IEEE754")))

    def pkg(name, body):
        return f"<AR-PACKAGE><SHORT-NAME>{name}</SHORT-NAME><ELEMENTS>{body}</ELEMENTS></AR-PACKAGE>\n"
    cluster = ("<CAN-CLUSTER><SHORT-NAME>CAN</SHORT-NAME><CAN-CLUSTER-VARIANTS><CAN-CLUSTER-CONDITIONAL>"
               "<PHYSICAL-CHANNELS><CAN-PHYSICAL-CHANNEL><SHORT-NAME>Kanal</SHORT-NAME><FRAME-TRIGGERINGS>"
               + "".join(trig) + "</FRAME-TRIGGERINGS></CAN-PHYSICAL-CHANNEL></PHYSICAL-CHANNELS>"
               "</CAN-CLUSTER-CONDITIONAL></CAN-CLUSTER-VARIANTS></CAN-CLUSTER>")
    body = (pkg("Cluster", cluster) + pkg("Frames", "".join(frames)) + pkg("Pdus", "".join(pdus))
            + pkg("Signals", "".join(sigs)) + pkg("Compu", "".join(compus)) + pkg("Units", unit_xml)
            + pkg("Types", types))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<AUTOSAR xmlns="http://autosar.org/schema/r4.0">\n'
            f"<AR-PACKAGES><AR-PACKAGE><SHORT-NAME>{package}</SHORT-NAME><AR-PACKAGES>\n{body}"
            "</AR-PACKAGES></AR-PACKAGE></AR-PACKAGES>\n</AUTOSAR>\n")
