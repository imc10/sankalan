"""A minimal read-only Compound File Binary reader ([MS-CFB]): the OLE container of .xls files and of encrypted
Office files (IN-3, IN-9).

Only what the probe and the .xls reader need: the names of the streams at the top level of the file, and one
stream's bytes. Version 3 (512-byte sectors) and version 4 (4096-byte sectors), regular and mini streams. A damaged
structure raises ``CfbError``; nothing here writes to the file (SEC-2).
"""
from __future__ import annotations

import struct

MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
NOSTREAM = 0xFFFFFFFF
_STORAGE, _STREAM, _ROOT = 1, 2, 5


class CfbError(Exception):
    """The container structure can't be read (damaged, or not a compound file)."""


class _Entry:
    __slots__ = ("name", "type", "left", "right", "child", "start", "size")

    def __init__(self, raw: bytes, v3: bool):
        n = struct.unpack_from("<H", raw, 64)[0]
        self.name = raw[:max(0, min(n, 64) - 2)].decode("utf-16-le", errors="replace")
        self.type = raw[66]
        self.left, self.right, self.child = struct.unpack_from("<III", raw, 68)
        self.start = struct.unpack_from("<I", raw, 116)[0]
        size = struct.unpack_from("<Q", raw, 120)[0]
        self.size = size & 0xFFFFFFFF if v3 else size


class CompoundFile:
    """The directory of a compound file opened from a seekable binary file object (kept open by the caller)."""

    def __init__(self, fh):
        self.fh = fh
        try:
            fh.seek(0, 2)
            self.file_size = fh.tell()
            fh.seek(0)
            header = fh.read(512)
        except OSError as e:
            raise CfbError(type(e).__name__) from None
        if len(header) < 512 or not header.startswith(MAGIC):
            raise CfbError("not a compound file")
        major, = struct.unpack_from("<H", header, 0x1A)
        shift, mini_shift = struct.unpack_from("<HH", header, 0x1E)
        if (major, shift) not in ((3, 9), (4, 12)) or mini_shift != 6:
            raise CfbError("unsupported header")
        self.v3 = major == 3
        self.sector_size = 1 << shift
        self.mini_size = 1 << mini_shift
        (n_fat, first_dir, _sig, self.mini_cutoff, first_minifat, n_minifat, first_difat,
         n_difat) = struct.unpack_from("<IIIIIIII", header, 0x2C)
        self.max_sectors = max(1, self.file_size // self.sector_size)

        # FAT: the first 109 sector numbers are in the header, the rest in the DIFAT chain
        fat_sectors = [s for s in struct.unpack_from("<109I", header, 0x4C)[:min(n_fat, 109)]]
        per = self.sector_size // 4 - 1
        sect, seen = first_difat, 0
        while len(fat_sectors) < n_fat and sect not in (ENDOFCHAIN, FREESECT):
            seen += 1
            if seen > n_difat + 1 or seen > self.max_sectors:
                raise CfbError("DIFAT loop")
            vals = struct.unpack(f"<{per + 1}I", self._sector(sect))
            fat_sectors.extend(vals[:per])
            sect = vals[per]
        fat_sectors = fat_sectors[:n_fat]
        self.fat: list[int] = []
        for s in fat_sectors:
            self.fat.extend(struct.unpack(f"<{self.sector_size // 4}I", self._sector(s)))

        # directory
        raw_dir = self._read_chain(first_dir, None)
        entries = [_Entry(raw_dir[i:i + 128], self.v3) for i in range(0, len(raw_dir) - 127, 128)]
        if not entries or entries[0].type != _ROOT:
            raise CfbError("no root entry")
        self.entries = entries
        self.root = entries[0]
        self.minifat: list[int] = []
        if n_minifat and first_minifat not in (ENDOFCHAIN, FREESECT):
            data = self._read_chain(first_minifat, None)
            self.minifat = list(struct.unpack(f"<{len(data) // 4}I", data[:len(data) // 4 * 4]))
        self._ministream: bytes | None = None
        self.streams = self._top_level_streams()

    # ------------------------------------------------------------------------------------------ internals
    def _sector(self, n: int) -> bytes:
        if n >= self.max_sectors + 1:
            raise CfbError("sector out of range")
        try:
            self.fh.seek((n + 1) * self.sector_size)
            data = self.fh.read(self.sector_size)
        except OSError as e:
            raise CfbError(type(e).__name__) from None
        if len(data) < self.sector_size:
            data = data.ljust(self.sector_size, b"\0")      # a short last sector (allowed in practice)
        return data

    def _chain(self, start: int) -> list[int]:
        out: list[int] = []
        sect = start
        fat = self.fat
        while sect not in (ENDOFCHAIN, FREESECT):
            if sect >= len(fat) or len(out) > self.max_sectors:
                raise CfbError("bad chain")
            out.append(sect)
            sect = fat[sect]
        return out

    def _read_chain(self, start: int, size: int | None) -> bytes:
        """The bytes of a regular-sector chain; consecutive sectors are read in one call."""
        chain = self._chain(start)
        parts: list[bytes] = []
        i = 0
        ss = self.sector_size
        try:
            while i < len(chain):
                j = i
                while j + 1 < len(chain) and chain[j + 1] == chain[j] + 1:
                    j += 1
                self.fh.seek((chain[i] + 1) * ss)
                parts.append(self.fh.read((j - i + 1) * ss))
                i = j + 1
        except OSError as e:
            raise CfbError(type(e).__name__) from None
        data = b"".join(parts)
        if size is not None:
            if len(data) < size:
                raise CfbError("stream shorter than its size")
            data = data[:size]
        return data

    def _top_level_streams(self) -> dict[str, _Entry]:
        """Streams directly under the root storage (not those inside embedded objects' storages)."""
        out: dict[str, _Entry] = {}
        stack = [self.root.child]
        seen: set[int] = set()
        while stack:
            i = stack.pop()
            if i == NOSTREAM or i in seen:
                continue
            if i >= len(self.entries):
                raise CfbError("bad directory link")
            seen.add(i)
            e = self.entries[i]
            if e.type == _STREAM:
                out.setdefault(e.name.lower(), e)
            elif e.type == _STORAGE:
                out.setdefault(e.name.lower(), e)
            stack.append(e.left)
            stack.append(e.right)
        return out

    # ------------------------------------------------------------------------------------------ public
    def has_stream(self, name: str) -> bool:
        e = self.streams.get(name.lower())
        return e is not None and e.type == _STREAM

    def has_entry(self, name: str) -> bool:
        return name.lower() in self.streams

    def read(self, name: str) -> bytes:
        e = self.streams.get(name.lower())
        if e is None or e.type != _STREAM:
            raise CfbError("stream missing")
        if e.size == 0:
            return b""
        if e.size < self.mini_cutoff:
            return self._read_mini(e)
        return self._read_chain(e.start, e.size)

    def _read_mini(self, e: _Entry) -> bytes:
        if self._ministream is None:
            self._ministream = self._read_chain(self.root.start, self.root.size) if self.root.size else b""
        ms, mini = self._ministream, self.minifat
        out: list[bytes] = []
        sect, n = e.start, 0
        limit = len(mini) + 1
        while sect not in (ENDOFCHAIN, FREESECT):
            if sect >= len(mini) or n > limit:
                raise CfbError("bad mini chain")
            off = sect * self.mini_size
            out.append(ms[off:off + self.mini_size])
            sect = mini[sect]
            n += 1
        data = b"".join(out)
        if len(data) < e.size:
            raise CfbError("mini stream shorter than its size")
        return data[:e.size]
