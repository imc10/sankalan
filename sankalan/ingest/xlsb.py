"""Excel Binary (.xlsb) access: sheet list, first rows for the probe, and the record scan (T11, IN-3, IN-13; D38).

An .xlsb workbook is a ZIP like .xlsx, with binary parts ([MS-XLSB]): each part is a sequence of records, each with
a variable-length type (1-2 bytes) and size (1-4 bytes), 7 bits per byte. python-calamine reads the values but reports
neither hidden rows nor error cells, so one streaming pass over the sheet part collects them:

- ``BrtRowHdr`` (0): the row number, and the hidden flag (bit 0x10 of byte 11).
- ``BrtCellError`` (3), ``BrtFmlaError`` (11) and ``BrtShortError`` (14): the error text.
- ``BrtWsDim`` (148): the last row, for the approximate row count.

The probe's first rows are decoded here too (numbers, text, shared strings, booleans, formula results), reading the
sheet part only as far as it needs, so a large .xlsb isn't loaded just to find its header (calamine loads the whole
sheet). Sheets come from ``xl/workbook.bin`` (``BrtBundleSh``: visibility, relationship, name).
"""
from __future__ import annotations

import posixpath
import struct
import zipfile
import xml.etree.ElementTree as ET
from typing import Callable, Iterator

from sankalan.ingest import detect
from sankalan.ingest.excel import ExcelError, Peek, Scan, SheetInfo, _Shared
from sankalan.ingest.xls import ERRORS

CHUNK = 1024 * 1024
STOP_EVERY = 50_000

ROW_HDR = 0
CELL_BLANK, CELL_RK, CELL_ERROR, CELL_BOOL, CELL_REAL, CELL_ST, CELL_ISST = 1, 2, 3, 4, 5, 6, 7
FMLA_STRING, FMLA_NUM, FMLA_BOOL, FMLA_ERROR = 8, 9, 10, 11
SHORT_BLANK, SHORT_RK, SHORT_ERROR, SHORT_BOOL, SHORT_REAL, SHORT_ST, SHORT_ISST = 12, 13, 14, 15, 16, 17, 18
SST_ITEM = 19
END_SHEET_DATA = 146
WS_DIM = 148
BUNDLE_SH = 156

_NORMAL_CELLS = frozenset(range(CELL_BLANK, FMLA_ERROR + 1))
_SHORT_CELLS = frozenset(range(SHORT_BLANK, SHORT_ISST + 1))
_ERROR_CELLS = frozenset((CELL_ERROR, FMLA_ERROR, SHORT_ERROR))
_REL_TYPE_SST = "/sharedStrings"


def _records(fh, stop: Callable[[], bool] | None = None) -> Iterator[tuple[int, bytes]]:
    """(record type, body) for every record of a binary part, read in chunks."""
    buf = b""
    pos = 0
    eof = False
    count = 0
    while True:
        # make sure a whole header (at most 6 bytes) is buffered
        if len(buf) - pos < 6 and not eof:
            more = fh.read(CHUNK)
            buf = buf[pos:] + more
            pos = 0
            eof = not more
        n = len(buf)
        if pos >= n:
            return
        b = buf[pos]
        if b & 0x80:
            if pos + 1 >= n:
                raise ExcelError("truncated record")
            typ = (b & 0x7F) | ((buf[pos + 1] & 0x7F) << 7)
            pos += 2
        else:
            typ = b
            pos += 1
        size = 0
        for k in range(4):
            if pos >= n:
                raise ExcelError("truncated record")
            c = buf[pos]
            pos += 1
            size |= (c & 0x7F) << (7 * k)
            if not c & 0x80:
                break
        end = pos + size
        while end > len(buf) and not eof:
            more = fh.read(max(CHUNK, end - len(buf)))
            eof = not more
            buf = buf[pos:] + more
            end -= pos
            pos = 0
        if end > len(buf):
            raise ExcelError("truncated record")
        yield typ, buf[pos:end]
        pos = end
        count += 1
        if stop is not None and count % STOP_EVERY == 0 and stop():
            return


def _wide_string(body: bytes, pos: int) -> tuple[str, int]:
    """XLWideString: character count (4 bytes) then UTF-16 characters. Returns the text and the next position."""
    n = struct.unpack_from("<I", body, pos)[0]
    if n == 0xFFFFFFFF:                                     # XLNullableWideString: null
        return "", pos + 4
    end = pos + 4 + 2 * n
    return body[pos + 4:end].decode("utf-16-le", errors="replace"), end


def _rk(v: int) -> float:
    if v & 0x02:
        num = float(v >> 2) if not v & 0x80000000 else float((v >> 2) - (1 << 30))
    else:
        num = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return num / 100 if v & 0x01 else num


class XlsbBook:
    """The parts of an .xlsb workbook, opened from a binary file object (kept open by the caller)."""

    def __init__(self, fh):
        try:
            self.zip = zipfile.ZipFile(fh)
            names = set(self.zip.namelist())
            if "xl/workbook.bin" not in names:
                raise ExcelError("no workbook part")
            rels = {}
            if "xl/_rels/workbook.bin.rels" in names:
                for r in ET.fromstring(self.zip.read("xl/_rels/workbook.bin.rels")):
                    rels[r.get("Id")] = (r.get("Target", ""), r.get("Type", ""))
            self.sheets: list[SheetInfo] = []
            with self.zip.open("xl/workbook.bin") as wb:
                for typ, body in _records(wb):
                    if typ == BUNDLE_SH and len(body) >= 12:
                        state = struct.unpack_from("<I", body, 0)[0]
                        rid, pos = _wide_string(body, 8)
                        name, _ = _wide_string(body, pos)
                        target, _t = rels.get(rid, ("", ""))
                        self.sheets.append(SheetInfo(name, state == 0, self._resolve(target)))
        except (zipfile.BadZipFile, ET.ParseError, KeyError, OSError, struct.error, EOFError) as e:
            raise ExcelError(type(e).__name__) from None
        self._strings_part = None
        for target, typ in rels.values():
            if typ.endswith(_REL_TYPE_SST):
                self._strings_part = self._resolve(target)
        if self._strings_part is None and "xl/sharedStrings.bin" in names:
            self._strings_part = "xl/sharedStrings.bin"

    @staticmethod
    def _resolve(target: str) -> str:
        if target.startswith("/"):
            return target.lstrip("/")
        return posixpath.normpath(posixpath.join("xl", target))

    def sheet(self, name: str) -> SheetInfo:
        for s in self.sheets:
            if s.name == name:
                return s
        raise ExcelError("sheet missing")

    def _open(self, name: str):
        part = self.sheet(name).part
        try:
            return self.zip.open(part)
        except (KeyError, zipfile.BadZipFile, OSError) as e:
            raise ExcelError(type(e).__name__) from None

    # ------------------------------------------------------------------------------------------ the record scan
    def scan(self, name: str, *, errors: bool = True, stop: Callable[[], bool] | None = None) -> Scan:
        result = Scan()
        hidden = result.hidden_rows
        errs = result.error_cells
        rnum = 0
        col = -1
        try:
            with self._open(name) as fh:
                for typ, body in _records(fh, stop):
                    if typ == ROW_HDR:
                        if len(body) >= 12:
                            rnum = struct.unpack_from("<I", body, 0)[0] + 1
                            col = -1
                            if body[11] & 0x10:
                                hidden.add(rnum)
                    elif typ in _NORMAL_CELLS:
                        if errors:
                            col = struct.unpack_from("<I", body, 0)[0] if len(body) >= 4 else col + 1
                            if typ in _ERROR_CELLS and len(body) >= 9:
                                errs.setdefault(rnum, {})[col] = ERRORS.get(body[8], "#N/A")
                    elif typ in _SHORT_CELLS:
                        if errors:
                            col += 1
                            if typ == SHORT_ERROR and len(body) >= 5:
                                errs.setdefault(rnum, {})[col] = ERRORS.get(body[4], "#N/A")
                    elif typ == WS_DIM:
                        if len(body) >= 8:
                            result.last_row = struct.unpack_from("<I", body, 4)[0] + 1
                    elif typ == END_SHEET_DATA:
                        break
        except (zipfile.BadZipFile, OSError, EOFError, struct.error) as e:
            raise ExcelError(type(e).__name__) from None
        return result

    # ------------------------------------------------------------------------------------------ probe
    def last_row(self, name: str) -> int | None:
        """The last row from ``BrtWsDim``, which comes before the first row record (T47); None when absent."""
        try:
            with self._open(name) as fh:
                for typ, body in _records(fh):
                    if typ == WS_DIM:
                        return struct.unpack_from("<I", body, 4)[0] + 1 if len(body) >= 8 else None
                    if typ in (ROW_HDR, END_SHEET_DATA):
                        return None
        except (zipfile.BadZipFile, OSError, EOFError, struct.error) as e:
            raise ExcelError(type(e).__name__) from None
        return None

    def peek(self, name: str, n: int = detect.HEADER_SCAN_ROWS) -> Peek:
        """The first ``n`` visible rows, values typed as the .xlsx peek types them (numbers as floats, dates as
        serial numbers, text as text), and the last row from the dimension record."""
        out = Peek()
        cells: list[tuple[int, list]] = []
        need: set[int] = set()
        vals: list | None = None
        rnum = 0
        col = -1
        try:
            with self._open(name) as fh:
                for typ, body in _records(fh):
                    if typ == ROW_HDR:
                        if len(cells) >= n:
                            break
                        if len(body) < 12:
                            continue
                        rnum = struct.unpack_from("<I", body, 0)[0] + 1
                        col = -1
                        if body[11] & 0x10:
                            vals = None
                            continue
                        vals = []
                        cells.append((rnum, vals))
                    elif typ in _NORMAL_CELLS or typ in _SHORT_CELLS:
                        if typ in _NORMAL_CELLS:
                            col = struct.unpack_from("<I", body, 0)[0]
                            v = _cell_value(typ, body, 8, need)
                        else:
                            col += 1
                            v = _cell_value(typ - (SHORT_BLANK - CELL_BLANK), body, 4, need)
                        if vals is None or v is None:
                            continue
                        if col >= len(vals):
                            vals.extend([None] * (col - len(vals) + 1))
                        vals[col] = v
                    elif typ == WS_DIM:
                        if len(body) >= 8:
                            out.last_row = struct.unpack_from("<I", body, 4)[0] + 1
                    elif typ == END_SHEET_DATA:
                        break
        except (zipfile.BadZipFile, OSError, EOFError, struct.error) as e:
            raise ExcelError(type(e).__name__) from None
        cells = cells[:n]
        strings = self._shared_strings(max(need)) if need else []
        for r, row in cells:
            out.rows.append((r, [strings[v.index] if isinstance(v, _Shared) and v.index < len(strings)
                                 else ("" if isinstance(v, _Shared) else v) for v in row]))
        return out

    def _shared_strings(self, up_to: int) -> list[str]:
        """Shared strings 0..up_to, read in order and no further."""
        if self._strings_part is None:
            return []
        out: list[str] = []
        try:
            with self.zip.open(self._strings_part) as fh:
                for typ, body in _records(fh):
                    if typ == SST_ITEM and len(body) >= 5:
                        out.append(_wide_string(body, 1)[0])        # RichStr: flags byte, then the text
                        if len(out) > up_to:
                            break
        except (KeyError, zipfile.BadZipFile, OSError, EOFError, struct.error) as e:
            raise ExcelError(type(e).__name__) from None
        return out


def _cell_value(typ: int, body: bytes, at: int, need: set):
    """The value of a normal cell record (short records are mapped to the normal type by the caller)."""
    if typ == CELL_BLANK:
        return None
    if typ == CELL_RK:
        return _rk(struct.unpack_from("<I", body, at)[0])
    if typ in (CELL_ERROR, FMLA_ERROR):
        return ERRORS.get(body[at], "#N/A")
    if typ in (CELL_BOOL, FMLA_BOOL):
        return body[at] != 0
    if typ in (CELL_REAL, FMLA_NUM):
        return struct.unpack_from("<d", body, at)[0]
    if typ in (CELL_ST, FMLA_STRING):
        return _wide_string(body, at)[0]
    if typ == CELL_ISST:
        idx = struct.unpack_from("<I", body, at)[0]
        need.add(idx)
        return _Shared(idx)
    return None
