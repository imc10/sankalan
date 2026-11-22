"""Excel 97-2003 (.xls, BIFF8) access: sheet list, password check, first rows for the probe, and the record scan
(T11, IN-3, IN-9, IN-13; D38).

The workbook is the ``Workbook`` stream of a compound file (``ingest/cfb.py``). python-calamine reads the values but,
as for .xlsx, reports neither hidden rows nor error cells (it gives ``''`` for ``#N/A``), so one pass over the sheet's
BIFF8 records collects them:

- ``ROW`` (0x0208): flag ``fDyZero`` (0x0020) marks a hidden row.
- ``BOOLERR`` (0x0205) with ``fError`` set, and ``FORMULA`` (0x0006) whose cached result is an error: the error text.
- ``DIMENSIONS`` (0x0200): the last row, for the approximate row count.

The globals give the sheets (``BOUNDSHEET8``: name, visibility, worksheet type, stream offset) and ``FILEPASS``
(0x002F), which marks a password-protected workbook.
"""
from __future__ import annotations

import struct
from typing import Callable

from sankalan.ingest import detect
from sankalan.ingest.cfb import CfbError, CompoundFile
from sankalan.ingest.excel import ExcelError, ExcelPassword, Peek, Scan, SheetInfo

BOF, EOF = 0x0809, 0x000A
FILEPASS, BOUNDSHEET = 0x002F, 0x0085
DIMENSIONS, ROW, BOOLERR, FORMULA = 0x0200, 0x0208, 0x0205, 0x0006
BIFF8 = 0x0600
ROW_HIDDEN = 0x0020

ERRORS = {0x00: "#NULL!", 0x07: "#DIV/0!", 0x0F: "#VALUE!", 0x17: "#REF!", 0x1D: "#NAME?", 0x24: "#NUM!",
          0x2A: "#N/A", 0x2B: "#GETTING_DATA"}

_HDR = struct.Struct("<HH")
STOP_EVERY = 50_000          # records between checks of ``stop``


def _short_string(data: bytes, pos: int) -> str:
    """ShortXLUnicodeString: character count (1 byte), flags (1 byte), characters."""
    n = data[pos]
    high = data[pos + 1] & 1
    raw = data[pos + 2:pos + 2 + n * (2 if high else 1)]
    return raw.decode("utf-16-le" if high else "latin-1", errors="replace")


class XlsBook:
    """The sheets of an .xls workbook, opened from a binary file object (kept open by the caller)."""

    def __init__(self, fh):
        self.fh = fh
        try:
            self.data = CompoundFile(fh).read("Workbook")
        except CfbError as e:
            raise ExcelError(type(e).__name__) from None
        data = self.data
        if len(data) < 8:
            raise ExcelError("no workbook stream")
        typ, size = _HDR.unpack_from(data, 0)
        if typ != BOF or size < 4 or struct.unpack_from("<H", data, 4)[0] != BIFF8:
            raise ExcelError("not BIFF8")
        self.sheets: list[SheetInfo] = []
        self._offsets: dict[str, int] = {}
        pos = 4 + size
        n = len(data)
        while pos + 4 <= n:
            typ, size = _HDR.unpack_from(data, pos)
            body = pos + 4
            if typ == FILEPASS:
                raise ExcelPassword("FILEPASS")
            if typ == BOUNDSHEET and size >= 8:
                offset = struct.unpack_from("<I", data, body)[0]
                state, kind = data[body + 4] & 0x03, data[body + 5]
                if kind == 0:                                   # worksheet (not chart, macro or VB module)
                    name = _short_string(data, body + 6)
                    self.sheets.append(SheetInfo(name, state == 0, str(offset)))
                    self._offsets[name] = offset
            elif typ == EOF:
                break
            pos = body + size

    def sheet(self, name: str) -> SheetInfo:
        for s in self.sheets:
            if s.name == name:
                return s
        raise ExcelError("sheet missing")

    # ------------------------------------------------------------------------------------------ the record scan
    def scan(self, name: str, *, errors: bool = True, stop: Callable[[], bool] | None = None) -> Scan:
        self.sheet(name)
        data = self.data
        pos = self._offsets[name]
        n = len(data)
        if pos + 4 > n or _HDR.unpack_from(data, pos)[0] != BOF:
            raise ExcelError("sheet stream")
        result = Scan()
        hidden = result.hidden_rows
        errs = result.error_cells
        unpack_hdr = _HDR.unpack_from
        pos += 4 + _HDR.unpack_from(data, pos)[1]
        count = 0
        while pos + 4 <= n:
            typ, size = unpack_hdr(data, pos)
            body = pos + 4
            pos = body + size
            if typ == ROW:
                if size >= 16 and struct.unpack_from("<H", data, body + 12)[0] & ROW_HIDDEN:
                    hidden.add(struct.unpack_from("<H", data, body)[0] + 1)
            elif typ == FORMULA:
                # FormulaValue: an error when bytes 6-7 are 0xFFFF and byte 0 is 2; the code is byte 2
                if errors and size >= 14 and data[body + 6] == 2 and data[body + 12] == 0xFF \
                        and data[body + 13] == 0xFF:
                    r, c = struct.unpack_from("<HH", data, body)
                    errs.setdefault(r + 1, {})[c] = ERRORS.get(data[body + 8], "#N/A")
            elif typ == BOOLERR:
                if errors and size >= 8 and data[body + 7] == 1:
                    r, c = struct.unpack_from("<HH", data, body)
                    errs.setdefault(r + 1, {})[c] = ERRORS.get(data[body + 6], "#N/A")
            elif typ == DIMENSIONS:
                if size >= 8:
                    result.last_row = struct.unpack_from("<I", data, body + 4)[0] or None
            elif typ == EOF:
                break
            count += 1
            if stop is not None and count % STOP_EVERY == 0 and stop():
                return result
        return result

    # ------------------------------------------------------------------------------------------ probe
    def last_row(self, name: str) -> int | None:
        """The last row from the sheet's ``DIMENSIONS`` record, which comes before the cells (T47)."""
        self.sheet(name)
        data = self.data
        pos = self._offsets[name]
        n = len(data)
        if pos + 4 > n or _HDR.unpack_from(data, pos)[0] != BOF:
            raise ExcelError("sheet stream")
        pos += 4 + _HDR.unpack_from(data, pos)[1]
        while pos + 4 <= n:
            typ, size = _HDR.unpack_from(data, pos)
            body = pos + 4
            pos = body + size
            if typ == DIMENSIONS:
                return (struct.unpack_from("<I", data, body + 4)[0] or None) if size >= 8 else None
            if typ in (ROW, EOF):
                return None
        return None

    def peek(self, name: str, n: int = detect.HEADER_SCAN_ROWS) -> Peek:
        """The first ``n`` visible rows (values from calamine; an .xls sheet holds at most 65,536 rows, so loading
        it whole is cheap) and the last row from the dimension record."""
        import python_calamine as pc

        scan = self.scan(name, errors=False)
        out = Peek(last_row=scan.last_row)
        try:
            self.fh.seek(0)
            sh = pc.CalamineWorkbook.from_filelike(self.fh).get_sheet_by_name(name)
        except Exception as e:      # noqa: BLE001 - calamine's own errors: the workbook can't be read
            if type(e).__name__ == "PasswordError":
                raise ExcelPassword("calamine") from None
            raise ExcelError(type(e).__name__) from None
        c0 = sh.start[1] if sh.start else 0
        for i, row in enumerate(sh.iter_rows()):
            rnum = i + 1
            if rnum in scan.hidden_rows:
                continue
            vals = [None] * c0 + [None if v == "" else v for v in row]
            if all(v is None for v in vals):
                continue
            out.rows.append((rnum, vals))
            if len(out.rows) >= n:
                break
        return out
