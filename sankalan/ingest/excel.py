"""Excel access: sheet list, first rows for the probe, the hidden-row and error-cell scan, and the full read (T11).

``open_book`` picks the reader by kind: ``Book`` here for .xlsx/.xlsm, ``xlsb.XlsbBook`` for .xlsb and
``xls.XlsBook`` for .xls (D38). All three give ``sheets``, ``peek`` and ``scan`` with the same results, and
``read_sheet`` is the same for all of them. For .xlsx/.xlsm:

- **Probe** reads the workbook parts with the standard library: the sheet list with visibility, the first rows of a
  sheet (for header detection, without loading the whole sheet), the dimension record (approximate row count) and
  a fast count of hidden rows.
- **Read** takes values from python-calamine (formulas give their last calculated values) and patches in what
  calamine can't report, from one streaming scan of the decompressed sheet XML: rows with ``hidden="1"`` (spike S4)
  and error cells such as ``#N/A``, which calamine returns as empty text (spike S3).
"""
from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable

from sankalan.ingest import detect
from sankalan.ingest.canonical import RawWriter, is_blank_row, staged_text

CHUNK = 1024 * 1024
PROGRESS_EVERY = 5000

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_STRICT_REL_NS = "http://purl.oclc.org/ooxml/officeDocument/relationships"
_COL_RE = re.compile(r"([A-Z]+)(\d+)")


class ExcelError(Exception):
    """The workbook structure can't be read (damaged or not an Excel workbook)."""


class ExcelPassword(ExcelError):
    """The workbook is password-protected (an .xls with a FILEPASS record, IN-9)."""


def open_book(fh, kind: str):
    """The workbook reader for ``kind`` (xlsx | xlsm | xlsb | xls), opened from a binary file object."""
    if kind == "xlsb":
        from sankalan.ingest.xlsb import XlsbBook
        return XlsbBook(fh)
    if kind == "xls":
        from sankalan.ingest.xls import XlsBook
        return XlsBook(fh)
    return Book(fh)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ns(tag: str) -> str:
    return tag[:tag.index("}") + 1] if tag.startswith("{") else ""


def col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _text_of(el) -> str:
    """Text of a string item: plain <t>, or rich-text runs <r><t> (phonetic <rPh> ignored)."""
    parts = []
    for child in el:
        name = _local(child.tag)
        if name == "t":
            parts.append(child.text or "")
        elif name == "r":
            for t in child:
                if _local(t.tag) == "t":
                    parts.append(t.text or "")
    return "".join(parts)


@dataclass
class SheetInfo:
    name: str
    visible: bool
    part: str               # zip member of the sheet XML


@dataclass
class Peek:
    rows: list[tuple[int, list]] = field(default_factory=list)   # (sheet row, values by absolute column)
    last_row: int | None = None                                  # from the dimension record


class Book:
    """The workbook parts of an .xlsx/.xlsm, opened from a binary file object (kept open by the caller)."""

    def __init__(self, fh):
        try:
            self.zip = zipfile.ZipFile(fh)
            names = set(self.zip.namelist())
            if "xl/workbook.xml" not in names:
                raise ExcelError("no workbook part")
            wb = ET.fromstring(self.zip.read("xl/workbook.xml"))
            rels = {}
            if "xl/_rels/workbook.xml.rels" in names:
                for r in ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels")):
                    rels[r.get("Id")] = (r.get("Target", ""), r.get("Type", ""))
        except (zipfile.BadZipFile, ET.ParseError, KeyError, OSError) as e:
            raise ExcelError(type(e).__name__) from None
        self._strings_part = None
        for target, typ in rels.values():
            if typ.endswith("/sharedStrings"):
                self._strings_part = self._resolve(target)
        if self._strings_part is None and "xl/sharedStrings.xml" in names:
            self._strings_part = "xl/sharedStrings.xml"
        ns = _ns(wb.tag)
        self.sheets: list[SheetInfo] = []
        sheets_el = wb.find(f"{ns}sheets")
        for s in (sheets_el if sheets_el is not None else []):
            rid = s.get(f"{{{_REL_NS}}}id") or s.get(f"{{{_STRICT_REL_NS}}}id")
            target, _typ = rels.get(rid, ("", ""))
            self.sheets.append(SheetInfo(s.get("name"), s.get("state", "visible") == "visible",
                                         self._resolve(target)))

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

    # ------------------------------------------------------------------------------------------ probe
    def peek(self, name: str, n: int = detect.HEADER_SCAN_ROWS) -> Peek:
        """The first ``n`` visible rows of a sheet, with values typed enough for header detection (text stays
        text), and the last row from the dimension record. Stops reading as soon as it has them."""
        info = self.sheet(name)
        out = Peek()
        cells: list[tuple[int, list]] = []
        need: set[int] = set()
        next_row = 1
        try:
            with self.zip.open(info.part) as fh:
                for _ev, el in ET.iterparse(fh, events=("end",)):
                    lname = _local(el.tag)
                    if lname == "dimension":
                        m = re.search(r"(\d+)$", el.get("ref", ""))
                        out.last_row = int(m.group(1)) if m else None
                    elif lname == "row":
                        r = el.get("r")
                        rnum = int(r) if r else next_row
                        next_row = rnum + 1
                        if el.get("hidden") in ("1", "true"):
                            el.clear()
                            continue
                        vals: list = []
                        pos = 0
                        for c in el:
                            if _local(c.tag) != "c":
                                continue
                            ref = c.get("r")
                            if ref:
                                m = _COL_RE.match(ref)
                                if m:
                                    pos = col_index(m.group(1))
                            val = self._peek_value(c, need)
                            if val is not None:
                                if pos >= len(vals):
                                    vals.extend([None] * (pos - len(vals) + 1))
                                vals[pos] = val
                            pos += 1
                        cells.append((rnum, vals))
                        el.clear()
                        if len(cells) >= n:
                            break
        except (ET.ParseError, KeyError, zipfile.BadZipFile, OSError) as e:
            raise ExcelError(type(e).__name__) from None
        strings = self._shared_strings(max(need)) if need else []
        for rnum, vals in cells:
            out.rows.append((rnum, [strings[v.index] if isinstance(v, _Shared) and v.index < len(strings)
                                    else ("" if isinstance(v, _Shared) else v) for v in vals]))
        return out

    @staticmethod
    def _peek_value(c, need: set):
        t = c.get("t")
        v_el = is_el = None
        for child in c:
            ln = _local(child.tag)
            if ln == "v":
                v_el = child
            elif ln == "is":
                is_el = child
        text = v_el.text if v_el is not None else None
        if t == "s":
            if text is None:
                return None
            idx = int(text)
            need.add(idx)
            return _Shared(idx)
        if t == "inlineStr":
            return _text_of(is_el) if is_el is not None else None
        if t in ("str", "e", "d"):
            return text
        if t == "b":
            return None if text is None else text == "1"
        if text is None or text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return text

    def _shared_strings(self, up_to: int) -> list[str]:
        """Shared strings 0..up_to, read in order and no further (headers come first in the table)."""
        if self._strings_part is None:
            return []
        out = []
        try:
            with self.zip.open(self._strings_part) as fh:
                for _ev, el in ET.iterparse(fh, events=("end",)):
                    if _local(el.tag) == "si":
                        out.append(_text_of(el))
                        el.clear()
                        if len(out) > up_to:
                            break
        except (ET.ParseError, KeyError, OSError) as e:
            raise ExcelError(type(e).__name__) from None
        return out

    # ------------------------------------------------------------------------------------------ the XML scan
    def scan(self, name: str, *, errors: bool = True, stop: Callable[[], bool] | None = None) -> "Scan":
        """One streaming pass over the decompressed sheet XML: hidden rows and (optionally) error cells."""
        info = self.sheet(name)
        result = Scan()
        carry = b""
        state = {"next_row": 1}
        try:
            with self.zip.open(info.part) as fh:
                while True:
                    chunk = fh.read(CHUNK)
                    if stop is not None and stop():
                        return result
                    if not chunk:
                        _scan_segment(carry, result, state, errors)
                        break
                    buf = carry + chunk
                    cut = _last_row_start(buf)
                    if cut <= 0:
                        carry = buf
                        continue
                    _scan_segment(buf[:cut], result, state, errors)
                    carry = buf[cut:]
        except (KeyError, zipfile.BadZipFile, OSError, EOFError) as e:
            raise ExcelError(type(e).__name__) from None
        return result


class _Shared:
    __slots__ = ("index",)

    def __init__(self, index: int):
        self.index = index


@dataclass
class Scan:
    hidden_rows: set[int] = field(default_factory=set)
    error_cells: dict[int, dict[int, str]] = field(default_factory=dict)   # sheet row -> {absolute column: text}
    last_row: int | None = None                                           # .xls/.xlsb: from the dimension record


_ROW_RE = re.compile(rb"<(?:\w+:)?row\b([^>]*)>")
_R_ATTR = re.compile(rb'\sr="(\d+)"')
_HIDDEN_ATTR = re.compile(rb'\shidden="(?:1|true)"')
_ERR_CELL = re.compile(rb'<(?:\w+:)?c\b([^>]*?\st="e"[^>]*?)(?<!/)>(.*?)</(?:\w+:)?c>', re.S)
_REF_ATTR = re.compile(rb'\sr="([A-Z]+)(\d+)"')
_V_EL = re.compile(rb"<(?:\w+:)?v>([^<]*)</(?:\w+:)?v>")


def _last_row_start(buf: bytes) -> int:
    i = buf.rfind(b"<row")
    j = buf.rfind(b":row")
    if j > i:
        k = buf.rfind(b"<", 0, j)
        if k > i:
            i = k
    return i


def _scan_segment(seg: bytes, result: Scan, state: dict, errors: bool) -> None:
    if not seg:
        return
    for m in _ROW_RE.finditer(seg):
        attrs = m.group(1)
        r = _R_ATTR.search(attrs)
        rnum = int(r.group(1)) if r else state["next_row"]
        state["next_row"] = rnum + 1
        if _HIDDEN_ATTR.search(attrs):
            result.hidden_rows.add(rnum)
    if errors and b't="e"' in seg:
        for m in _ERR_CELL.finditer(seg):
            ref = _REF_ATTR.search(b" " + m.group(1))
            v = _V_EL.search(m.group(2))
            if ref and v:
                text = v.group(1).decode("utf-8", errors="replace")
                result.error_cells.setdefault(int(ref.group(2)), {})[col_index(ref.group(1).decode("ascii"))] = text


# ---------------------------------------------------------------------------------------------- read (T11)
@dataclass
class ReadCounts:
    rows: int = 0               # data rows written (not blank, not hidden)
    blank_rows: int = 0         # IN-8, T14
    hidden_rows: int = 0        # IN-13, below the header
    limited: bool = False       # stopped at the row limit: more rows follow


def read_sheet(path: str, fh, sheet: str, header_row: int, width: int, out_path, *,
               report: Callable[[int], None] | None = None, stop: Callable[[], bool] | None = None,
               limit: int | None = None, kind: str = "xlsx") -> ReadCounts:
    """Write the raw staged text of one sheet: rows below ``header_row``, columns 0..width-1, hidden and blank
    rows dropped and counted. ``fh`` is the open source file (for the scan); calamine opens ``path`` itself.
    ``limit`` stops after that many data rows (the New template wizard's sample, TPL-3)."""
    import python_calamine as pc

    scan = open_book(fh, kind).scan(sheet, stop=stop)
    counts = ReadCounts()
    try:
        wb = pc.CalamineWorkbook.from_path(path)
        sh = wb.get_sheet_by_name(sheet)
    except Exception as e:      # noqa: BLE001 - calamine's own errors: the workbook can't be read
        raise ExcelError(type(e).__name__) from None
    start = sh.start
    first_col = start[1] if start else 0
    pending = 0
    conv = staged_text
    with RawWriter(out_path, width) as w:
        for i, row in enumerate(sh.iter_rows()):
            rnum = i + 1
            if rnum <= header_row:
                continue
            if rnum in scan.hidden_rows:
                counts.hidden_rows += 1
                continue
            if first_col == 0:
                vals = [conv(v) for v in row[:width]]
                if len(vals) < width:
                    vals.extend([""] * (width - len(vals)))
            else:
                vals = [""] * first_col + [conv(v) for v in row[:max(0, width - first_col)]]
                vals.extend([""] * (width - len(vals)))
            errs = scan.error_cells.get(rnum)
            if errs:
                for col, text in errs.items():
                    if col < width:
                        vals[col] = text
            if is_blank_row(vals):
                counts.blank_rows += 1
            else:
                w.write(rnum, vals)
                counts.rows += 1
                if limit is not None and counts.rows >= limit:
                    counts.limited = True
                    break
            pending += 1
            if pending >= PROGRESS_EVERY:
                if report is not None:
                    report(pending)
                pending = 0
                if stop is not None and stop():
                    return counts
        # hidden rows listed past the last row calamine returns (an empty hidden row at the end)
        if not counts.limited:
            counts.hidden_rows += sum(1 for r in scan.hidden_rows
                                      if r > header_row and r > max(len_rows(sh), 0))
    if report is not None and pending:
        report(pending)
    return counts


def len_rows(sh) -> int:
    end = sh.end
    return (end[0] + 1) if end else 0
