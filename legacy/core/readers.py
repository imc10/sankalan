"""Reading input files (IN-1 .. IN-13).

Supported: .xlsx/.xlsm (standard-library reader in xlsx.py, incl. hidden rows/sheets),
.xls (xlrd with formatting info), .csv/.txt (encoding and delimiter detection).
Source files are only ever opened for reading (SEC-2).
"""
from __future__ import annotations

import csv
import fnmatch
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

SUPPORTED = {".xlsx", ".xlsm", ".xls", ".csv", ".txt"}
EXCEL = {".xlsx", ".xlsm", ".xls"}
HEADER_SCAN_ROWS = 30


class PasswordRequired(Exception):
    """The file is encrypted and no (or a wrong) password was given."""


class ReadError(Exception):
    pass


class Cancelled(Exception):
    pass


# ----------------------------------------------------------------------------- file collection

@dataclass
class Skipped:
    path: Path
    reason: str


def collect_files(paths: Iterable, pattern: str = "*", include_subfolders: bool = False):
    """IN-1, IN-2, IN-10: expand files/folders into a sorted, de-duplicated list of supported files."""
    found: list[Path] = []
    skipped: list[Skipped] = []
    seen: set = set()
    pat = (pattern or "*").lower()

    def consider(p: Path, from_folder: bool):
        if p.name.startswith("~$"):
            skipped.append(Skipped(p, "Excel lock file"))
            return
        if from_folder and not fnmatch.fnmatch(p.name.lower(), pat):
            return
        if p.suffix.lower() not in SUPPORTED:
            if not from_folder:
                skipped.append(Skipped(p, "unsupported file type"))
            return
        key = str(p.resolve()).lower()
        if key in seen:
            skipped.append(Skipped(p, "same file added twice"))
            return
        seen.add(key)
        found.append(p)

    for item in paths:
        p = Path(item)
        if p.is_dir():
            it = p.rglob("*") if include_subfolders else p.glob("*")
            for f in sorted(x for x in it if x.is_file()):
                consider(f, True)
        elif p.is_file():
            consider(p, False)
        else:
            skipped.append(Skipped(p, "not found"))
    return found, skipped


# ----------------------------------------------------------------------------- raw sheet access

@dataclass
class RawSheet:
    name: str
    rows: list            # list of row value lists
    row_numbers: list     # original 1-based row numbers, parallel to rows
    hidden_rows: set      # 1-based row numbers that are hidden


def _is_ole(data: bytes) -> bool:
    return data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _decrypt_if_needed(path: Path, data: bytes, password: Optional[str]) -> bytes:
    """IN-9: decrypt password-protected workbooks in memory. The password is never stored."""
    if not _is_ole(data):
        return data
    import msoffcrypto
    try:
        office = msoffcrypto.OfficeFile(io.BytesIO(data))
        encrypted = office.is_encrypted()
    except Exception:
        return data  # plain old .xls without encryption support -> let xlrd handle it
    if not encrypted:
        return data
    if not password:
        raise PasswordRequired(path.name)
    try:
        office.load_key(password=password)
        out = io.BytesIO()
        office.decrypt(out)
        return out.getvalue()
    except Exception as exc:  # wrong password
        raise PasswordRequired(path.name) from exc


def is_encrypted(path: Path) -> bool:
    data = Path(path).read_bytes()
    try:
        _decrypt_if_needed(Path(path), data, None)
        return False
    except PasswordRequired:
        return True


class Workbook:
    """Uniform read-only view over xlsx/xls/csv."""

    def __init__(self, path: Path, password: Optional[str] = None):
        self.path = Path(path)
        self.ext = self.path.suffix.lower()
        self.csv_encoding = None
        self.csv_delimiter = None
        with open(self.path, "rb") as fh:  # read-only (SEC-2)
            data = fh.read()
        if self.ext in EXCEL:
            data = _decrypt_if_needed(self.path, data, password)
            if _is_ole(data) or self.ext == ".xls":
                if _is_ole(data):
                    self._init_xls(data)
                else:
                    self._init_xlsx(data)
            else:
                self._init_xlsx(data)
        else:
            self._init_csv(data)

    # ---- sheets: list of (name, visible)
    def sheets(self):
        return list(self._sheets)

    def visible_sheets(self):
        return [n for n, v in self._sheets if v]

    def hidden_sheets(self):
        return [n for n, v in self._sheets if not v]

    # ---- xlsx (standard-library reader: nothing compiled for Windows to block)
    def _init_xlsx(self, data: bytes):
        from .xlsx import XlsxBook, XlsxError
        try:
            self._book_x = XlsxBook(data)
        except XlsxError as exc:
            raise ReadError(str(exc)) from exc
        self._sheets = self._book_x.sheets()
        self.kind = "xlsx"

    def _xlsx_read(self, sheet: str) -> RawSheet:
        rows, hidden = self._book_x.read(sheet)
        return RawSheet(sheet, rows, list(range(1, len(rows) + 1)), hidden)

    # ---- xls
    def _init_xls(self, data: bytes):
        import xlrd
        try:
            self._book = xlrd.open_workbook(file_contents=data, formatting_info=True)
        except Exception:
            try:
                self._book = xlrd.open_workbook(file_contents=data)
            except Exception as exc:
                raise ReadError("not a valid .xls file") from exc
        self._sheets = [(s.name, s.visibility == 0) for s in self._book.sheets()]
        self.kind = "xls"

    def _xls_read(self, sheet: str) -> RawSheet:
        import xlrd
        sh = self._book.sheet_by_name(sheet)
        rows, nums, hidden = [], [], set()
        info = getattr(sh, "rowinfo_map", {}) or {}
        for r in range(sh.nrows):
            vals = []
            for c in range(sh.ncols):
                cell = sh.cell(r, c)
                if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    vals.append(None)
                elif cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        vals.append(xlrd.xldate_as_datetime(cell.value, self._book.datemode))
                    except Exception:
                        vals.append(cell.value)
                elif cell.ctype == xlrd.XL_CELL_TEXT:
                    vals.append(cell.value if cell.value != "" else None)
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    vals.append(bool(cell.value))
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    vals.append(None)
                else:
                    vals.append(cell.value)
            rows.append(vals)
            nums.append(r + 1)
            ri = info.get(r)
            if ri is not None and getattr(ri, "hidden", 0):
                hidden.add(r + 1)
        return RawSheet(sheet, rows, nums, hidden)

    # ---- csv
    def _init_csv(self, data: bytes):
        """IN-4: encoding (UTF-8 BOM, UTF-8, Windows-1252) and delimiter detection."""
        if data.startswith(b"\xef\xbb\xbf"):
            enc, text = "utf-8-sig", data.decode("utf-8-sig")
        else:
            try:
                enc, text = "utf-8", data.decode("utf-8")
            except UnicodeDecodeError:
                enc, text = "cp1252", data.decode("cp1252", errors="replace")
        self.csv_encoding = enc
        self._text = text
        self._sheets = [(self.path.stem, True)]
        self.kind = "csv"

    def _csv_read(self, delimiter: Optional[str] = None) -> RawSheet:
        text = self._text
        if not delimiter or delimiter == "auto":
            sample = "\n".join(text.splitlines()[:50])
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                counts = {d: sample.count(d) for d in ",;\t|"}
                delimiter = max(counts, key=counts.get) if any(counts.values()) else ","
        self.csv_delimiter = delimiter
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
        rows = [[(v if v.strip() != "" else None) for v in r] for r in reader]
        return RawSheet(self._sheets[0][0], rows, list(range(1, len(rows) + 1)), set())

    def read(self, sheet: str, delimiter: Optional[str] = None) -> RawSheet:
        if self.kind == "xlsx":
            return self._xlsx_read(sheet)
        if self.kind == "xls":
            return self._xls_read(sheet)
        return self._csv_read(delimiter)


# ----------------------------------------------------------------------------- header + records

def _norm(s) -> str:
    return re.sub(r"[\s._\-]+", "", str(s).strip().lower())


def _nonempty(row):
    return [v for v in row if v is not None and str(v).strip() != ""]


def detect_header(rows: list, known_names: Optional[set] = None) -> int:
    """IN-6: return the 0-based index (into rows) of the header row."""
    scan = rows[:HEADER_SCAN_ROWS]
    if known_names:
        best, best_i = 0, None
        for i, r in enumerate(scan):
            score = sum(1 for v in r if v is not None and _norm(v) in known_names)
            if score > best:
                best, best_i = score, i
        if best_i is not None:
            return best_i
    widest = max((len(_nonempty(r)) for r in scan), default=0)
    for i, r in enumerate(scan):
        ne = _nonempty(r)
        if len(ne) >= 2 and len(ne) >= 0.6 * widest and all(isinstance(v, str) for v in ne):
            return i
    for i, r in enumerate(scan):
        if _nonempty(r):
            return i
    return 0


def _make_headers(raw):
    headers, seen = [], {}
    for i, v in enumerate(raw):
        name = str(v).strip() if v is not None and str(v).strip() != "" else f"Column {i + 1}"
        if isinstance(v, float) and v.is_integer():
            name = str(int(v))
        if isinstance(v, (datetime, date)):
            name = v.strftime("%d-%m-%Y")
        base, n = name, seen.get(name.lower(), 0)
        if n:
            name = f"{base} ({n + 1})"
        seen[base.lower()] = n + 1
        headers.append(name)
    return headers


def is_trailer(row, words) -> bool:
    """IN-7: the first non-empty cell starts with a trailer word, e.g. 'Total', 'Grand Total'."""
    ne = _nonempty(row)
    if not ne or not isinstance(ne[0], str):
        return False
    first = ne[0].strip().lower()
    return any(re.match(r"^%s\b" % re.escape(w.strip().lower()), first) for w in words if w.strip())


@dataclass
class FileData:
    path: Path
    sheet: str = ""
    header_row: int = 0                 # 1-based original row number
    headers: list = field(default_factory=list)
    rows: list = field(default_factory=list)          # data rows, aligned to headers
    row_numbers: list = field(default_factory=list)   # original row numbers of data rows
    hidden_rows: int = 0
    hidden_sheets: list = field(default_factory=list)
    blank_rows: int = 0
    trailer_rows: int = 0
    sheets: list = field(default_factory=list)        # visible sheet names
    status: str = "OK"                  # OK | warning | error | password
    notes: list = field(default_factory=list)
    error: str = ""
    preview: list = field(default_factory=list)       # first rows as read (with row numbers)
    csv_encoding: Optional[str] = None
    csv_delimiter: Optional[str] = None

    @property
    def name(self):
        return self.path.name


def select_sheets(wb: Workbook, mode: str, value: str):
    """IN-5: first visible sheet, sheet by name, or every visible sheet matching a pattern."""
    visible = wb.visible_sheets()
    if mode == "name" and value:
        for n in visible:
            if n.lower() == value.lower():
                return [n]
        for n in wb.hidden_sheets():
            if n.lower() == value.lower():
                raise ReadError(f'sheet "{n}" is hidden, so it was skipped')
        raise ReadError(f'no sheet named "{value}"')
    if mode == "pattern" and value:
        out = [n for n in visible if fnmatch.fnmatch(n.lower(), value.lower())]
        if not out:
            raise ReadError(f'no sheet matches "{value}"')
        return out
    if not visible:
        raise ReadError("no visible sheet")
    return [visible[0]]


def read_file(path, *, sheet_mode="first", sheet_value="", header_row: Optional[int] = None,
              known_names: Optional[set] = None, trailer_words=("Total", "Grand Total"),
              password: Optional[str] = None, csv_delimiter: Optional[str] = None,
              cancel: Optional[Callable] = None) -> list:
    """Read one file into one FileData per selected sheet. Errors are captured, not raised
    (except PasswordRequired, which the caller handles by asking for a password)."""
    path = Path(path)
    try:
        wb = Workbook(path, password)
    except PasswordRequired:
        raise
    except ReadError as exc:
        return [FileData(path, status="error", error=str(exc))]
    except Exception as exc:  # corrupt file etc.
        return [FileData(path, status="error", error=f"could not read ({type(exc).__name__})")]
    try:
        sheets = select_sheets(wb, sheet_mode, sheet_value) if wb.kind != "csv" else [wb.sheets()[0][0]]
    except ReadError as exc:
        return [FileData(path, status="error", error=str(exc), sheets=wb.visible_sheets(),
                         hidden_sheets=wb.hidden_sheets())]
    out = []
    for sh in sheets:
        if cancel and cancel():
            raise Cancelled()
        fd = FileData(path, sheet=sh, sheets=wb.visible_sheets(), hidden_sheets=wb.hidden_sheets())
        try:
            raw = wb.read(sh, csv_delimiter)
        except Exception as exc:
            fd.status, fd.error = "error", f"could not read sheet ({type(exc).__name__})"
            out.append(fd)
            continue
        fd.csv_encoding, fd.csv_delimiter = wb.csv_encoding, wb.csv_delimiter
        fd.preview = [(n, r) for n, r in zip(raw.row_numbers[:200], raw.rows[:200])]
        # IN-13: drop hidden rows before anything else
        keep = [(n, r) for n, r in zip(raw.row_numbers, raw.rows) if n not in raw.hidden_rows]
        fd.hidden_rows = len(raw.row_numbers) - len(keep)
        rows = [r for _, r in keep]
        nums = [n for n, _ in keep]
        if not rows:
            fd.status, fd.error = "error", "sheet is empty"
            out.append(fd)
            continue
        if header_row:  # manual override, 1-based original row number
            if header_row not in nums:
                fd.status, fd.error = "error", f"header row {header_row} is hidden or outside the sheet"
                out.append(fd)
                continue
            hi = nums.index(header_row)
        else:
            hi = detect_header(rows, known_names)
        fd.header_row = nums[hi]
        width = max(len(r) for r in rows)
        hdr = list(rows[hi]) + [None] * (width - len(rows[hi]))
        # trim trailing unnamed, empty columns
        last = width
        while last > 0 and (hdr[last - 1] is None or str(hdr[last - 1]).strip() == "") and \
                all((len(r) < last or r[last - 1] is None) for r in rows[hi + 1:]):
            last -= 1
        fd.headers = _make_headers(hdr[:last])
        for n, r in zip(nums[hi + 1:], rows[hi + 1:]):
            r = (list(r) + [None] * last)[:last]
            if not _nonempty(r):
                fd.blank_rows += 1          # IN-8
                continue
            if is_trailer(r, trailer_words):
                fd.trailer_rows += 1        # IN-7
                continue
            fd.rows.append(r)
            fd.row_numbers.append(n)
        if fd.header_row != nums[0]:
            fd.notes.append(f"header found on row {fd.header_row}")
        if fd.hidden_rows:
            fd.notes.append(f"{fd.hidden_rows} hidden row{'s' if fd.hidden_rows != 1 else ''} skipped")
        if fd.hidden_sheets:
            fd.notes.append("hidden sheet " + ", ".join(f'"{s}"' for s in fd.hidden_sheets) + " skipped")
        if fd.trailer_rows:
            fd.notes.append(f"{fd.trailer_rows} total row{'s' if fd.trailer_rows != 1 else ''} skipped")
        if not fd.rows:
            fd.status = "warning"
            fd.notes.append("no data rows")
        elif fd.notes:
            fd.status = "warning"
        out.append(fd)
    return out
