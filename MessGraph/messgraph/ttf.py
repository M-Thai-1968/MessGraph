"""TrueType/OpenType lesen, soweit es das PDF braucht: Zeichen -> Glyphe, Breiten, Kennwerte."""
from __future__ import annotations

import struct


class TrueTypeFont:
    def __init__(self, path: str):
        with open(path, "rb") as fh:
            self.data = fh.read()
        base = 0
        self.collection = self.data[:4] == b"ttcf"
        if self.collection:                        # Schriftsammlung (.ttc): erste Schrift verwenden
            base = struct.unpack(">I", self.data[12:16])[0]
        tag = self.data[base:base + 4]
        if tag not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            raise ValueError("keine TrueType/OpenType-Schrift")
        self.sfnt_version = tag
        self.is_cff = tag == b"OTTO"
        count = struct.unpack(">H", self.data[base + 4:base + 6])[0]
        self.tables = {}
        for i in range(count):
            pos = base + 12 + 16 * i
            name, _, offset, length = struct.unpack(">4sIII", self.data[pos:pos + 16])
            self.tables[name.decode("latin-1")] = (offset, length)    # Offsets gelten ab Dateianfang
        head = self._table("head")
        self.units = struct.unpack(">H", head[18:20])[0]
        self.bbox = struct.unpack(">hhhh", head[36:44])
        hhea = self._table("hhea")
        self.ascent, self.descent = struct.unpack(">hh", hhea[4:8])
        n_metrics = struct.unpack(">H", hhea[34:36])[0]
        self.num_glyphs = struct.unpack(">H", self._table("maxp")[4:6])[0]
        hmtx = self._table("hmtx")
        advances = [struct.unpack(">H", hmtx[4 * i:4 * i + 2])[0] for i in range(n_metrics)]
        self.advances = advances + [advances[-1]] * (self.num_glyphs - n_metrics)
        self.cap_height = self.ascent
        if "OS/2" in self.tables:
            os2 = self._table("OS/2")
            if len(os2) >= 90 and struct.unpack(">H", os2[0:2])[0] >= 2:
                self.cap_height = struct.unpack(">h", os2[88:90])[0]
        self.cmap = self._read_cmap()
        name = self._ps_name()
        self.ps_name = name or "EmbeddedFont"

    def _table(self, tag: str) -> bytes:
        offset, length = self.tables[tag]
        return self.data[offset:offset + length]

    def _read_cmap(self) -> dict[int, int]:
        cmap = self._table("cmap")
        count = struct.unpack(">H", cmap[2:4])[0]
        subtables = []
        for i in range(count):
            platform, encoding, offset = struct.unpack(">HHI", cmap[4 + 8 * i:12 + 8 * i])
            fmt = struct.unpack(">H", cmap[offset:offset + 2])[0]
            if (platform, encoding) in ((3, 10), (0, 4), (0, 6)) and fmt == 12:
                subtables.insert(0, (fmt, offset))
            elif (platform, encoding) in ((3, 1), (0, 3), (0, 1), (0, 0)) and fmt == 4:
                subtables.append((fmt, offset))
        result: dict[int, int] = {}
        for fmt, offset in reversed(subtables):  # Format 12 zuletzt, damit es Vorrang hat
            if fmt == 4:
                seg = struct.unpack(">H", cmap[offset + 6:offset + 8])[0] // 2
                base = offset + 14
                ends = struct.unpack(f">{seg}H", cmap[base:base + 2 * seg])
                starts = struct.unpack(f">{seg}H", cmap[base + 2 * seg + 2:base + 4 * seg + 2])
                deltas = struct.unpack(f">{seg}h", cmap[base + 4 * seg + 2:base + 6 * seg + 2])
                range_pos = base + 6 * seg + 2
                ranges = struct.unpack(f">{seg}H", cmap[range_pos:range_pos + 2 * seg])
                for i in range(seg):
                    for code in range(starts[i], ends[i] + 1):
                        if code == 0xFFFF:
                            continue
                        if ranges[i] == 0:
                            glyph = (code + deltas[i]) & 0xFFFF
                        else:
                            pos = range_pos + 2 * i + ranges[i] + 2 * (code - starts[i])
                            glyph = struct.unpack(">H", cmap[pos:pos + 2])[0]
                            if glyph:
                                glyph = (glyph + deltas[i]) & 0xFFFF
                        if glyph:
                            result[code] = glyph
            else:
                groups = struct.unpack(">I", cmap[offset + 12:offset + 16])[0]
                for g in range(groups):
                    start, end, glyph = struct.unpack(">III", cmap[offset + 16 + 12 * g:offset + 28 + 12 * g])
                    for code in range(start, end + 1):
                        result[code] = glyph + code - start
        return result

    def _ps_name(self) -> str:
        if "name" not in self.tables:
            return ""
        data = self._table("name")
        count, string_offset = struct.unpack(">HH", data[2:6])
        for i in range(count):
            platform, encoding, _, name_id, length, offset = struct.unpack(">HHHHHH", data[6 + 12 * i:18 + 12 * i])
            if name_id != 6:
                continue
            raw = data[string_offset + offset:string_offset + offset + length]
            text = raw.decode("utf-16-be", errors="ignore") if platform in (0, 3) else raw.decode("latin-1")
            return "".join(ch for ch in text if ch.isalnum() or ch in "-_") or ""
        return ""

    def sfnt(self) -> bytes:
        """Eigenständige Schriftdatei (für das Einbetten ins PDF); aus einer .ttc wird die erste Schrift gelöst."""
        if not self.collection:
            return self.data
        names = sorted(self.tables)
        count = len(names)
        power = 1 << (count.bit_length() - 1)
        header = self.sfnt_version + struct.pack(">HHHH", count, power * 16, power.bit_length() - 1,
                                                 count * 16 - power * 16)
        offset = 12 + 16 * count
        records, bodies = [], []
        for name in names:
            body = self._table(name)
            records.append(struct.pack(">4sIII", name.encode("latin-1"), 0, offset, len(body)))
            padded = body + b"\0" * (-len(body) % 4)
            bodies.append(padded)
            offset += len(padded)
        return header + b"".join(records) + b"".join(bodies)

    def glyph_id(self, code: int) -> int:
        return self.cmap.get(code, 0)

    def advance(self, glyph: int) -> float:
        """Breite in 1/1000 em."""
        return self.advances[glyph] * 1000.0 / self.units if glyph < len(self.advances) else 0.0
