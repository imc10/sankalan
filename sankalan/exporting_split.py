"""The export splitter (Feature Spec A2 EXP-9, 8.6; Tech spec A2 8.5).

DuckDB writes each export chunk to a file of data records with no header (T33). The splitter streams the chunk files,
in order, into the parts: it counts CSV **records**, not lines, and cuts only on a record boundary, so a value with a
line break, a quote or the delimiter is never split across two parts (R9). Each part starts with the BOM (when chosen)
and the header line.

A record ends at a ``\\n`` outside quotes. The quote state flips on every ``"``; a doubled quote inside a value flips
twice, so it needs no special case (S7h). The state is carried across blocks and must be "outside" at the end of every
chunk, which must end with a record end; anything else fails the export (``SplitError``).

No Qt and no DuckDB here, so it is unit-tested alone. File I/O and ``bytes`` methods release the GIL, so the window
stays responsive while it runs in the Job's thread (NF-3).
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Callable

BOM = b"\xef\xbb\xbf"
BLOCK = 8 << 20                 # 8 MB blocks
NL, QUOTE = b"\n", b'"'


class SplitError(Exception):
    """A chunk ended inside a quoted value or in the middle of a record."""


class Splitter:
    """``open_part(k)`` opens part *k* (0-based) for binary writing; the splitter writes the BOM and header first.
    ``tick(records_written, part_number)`` is called after every block (progress and cancel); ``block`` is the read
    size (tests use a small one)."""

    def __init__(self, open_part: Callable[[int], BinaryIO], header: bytes, bom: bool, part_rows: int, *,
                 tick: Callable[[int, int], None] | None = None, block: int = BLOCK):
        if part_rows < 1:
            raise ValueError("part_rows must be at least 1")
        self._open_part = open_part
        self._lead = (BOM if bom else b"") + header
        self.part_rows = part_rows
        self._tick = tick
        self._block = block
        self._out: BinaryIO | None = None
        self._counts: list[int] = []        # records per part
        self._full = False                  # the current part holds part_rows records
        self._inq = False                   # inside a quoted value
        self.written = 0                    # records written in all

    # -------------------------------------------------------------------------------------------- parts
    def _next_part(self) -> None:
        if self._out is not None:
            self._out.close()
            self._out = None
        self._out = self._open_part(len(self._counts))
        self._counts.append(0)
        self._full = False
        self._out.write(self._lead)

    # -------------------------------------------------------------------------------------------- scanning
    def _scan(self, b: bytes, pos: int, need: int) -> tuple[int, int]:
        """From ``pos``, the end of the ``need``-th record end (or of the block) and the record ends found. Updates
        the quote state."""
        end, found, i = len(b), 0, pos
        while i < end:
            if self._inq:
                q = b.find(QUOTE, i)
                if q < 0:
                    return end, found
                self._inq, i = False, q + 1
                continue
            q = b.find(QUOTE, i)
            stop = end if q < 0 else q
            c = b.count(NL, i, stop)            # the fast path: no quote before ``stop``
            if found + c >= need:
                j = i
                for _ in range(need - found):
                    j = b.find(NL, j, stop) + 1
                return j, need
            found += c
            if q < 0:
                return end, found
            self._inq, i = True, q + 1
        return end, found

    def _write_block(self, b: bytes) -> int:
        pos, n, found_all = 0, len(b), 0
        while pos < n:
            if self._out is None or self._full:
                self._next_part()
            need = self.part_rows - self._counts[-1]
            end, found = self._scan(b, pos, need)
            self._out.write(b[pos:end] if (pos or end != n) else b)
            self._counts[-1] += found
            found_all += found
            pos = end
            if self._counts[-1] == self.part_rows:
                self._full = True
        self.written += found_all
        return found_all

    # -------------------------------------------------------------------------------------------- interface
    @property
    def part(self) -> int:
        """The part being written, from 1."""
        return max(1, len(self._counts))

    def feed(self, path: Path) -> int:
        """Stream one chunk file into the parts; returns the records it held."""
        records, last = 0, NL
        with open(path, "rb") as f:
            while True:
                b = f.read(self._block)
                if not b:
                    break
                records += self._write_block(b)
                last = b[-1:]
                if self._tick is not None:
                    self._tick(self.written, len(self._counts))
        if self._inq or last != NL:
            raise SplitError("chunk ended inside a record")
        return records

    def close(self) -> list[int]:
        """Close the last part (an export with no rows still gets one part with the header); records per part."""
        if self._out is None and not self._counts:
            self._next_part()
        if self._out is not None:
            self._out.close()
            self._out = None
        return list(self._counts)

    def abandon(self) -> None:
        """Close the open part without finishing (cancel or failure); the caller deletes the files."""
        if self._out is not None:
            try:
                self._out.close()
            finally:
                self._out = None
