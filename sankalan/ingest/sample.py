"""The New template wizard's sample file (TPL-3, F1, IN-3 to IN-6; C3-02 to C3-08).

``refusal`` screens the picked path (folders, .xls, other types). ``inspect`` opens the file read-only (SEC-2) and
returns what steps 1 and 2 show: the sheets (visible, hidden, approximate rows), the header row found in each
(IN-6, the same detection as a run), the first rows for the preview and, for a CSV file, the encoding and
delimiter detected (IN-4). It reads only the start of the file, never the whole of it (C3-03).

``read_part`` is the reader-worker task that writes up to ``limit`` data rows of one sheet (or CSV file) as raw
staged text, the same form a run stages (``ingest/canonical.py``).
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path

from sankalan.ingest import csvread, detect, excel, source
from sankalan.ingest.canonical import staged_text
from sankalan.ingest.probe import REFUSED, SKIPPED, screen_paths
from sankalan.ingest.source import FileProblem

SAMPLE_ROWS = 100_000           # TPL-3: rows read for previews
PREVIEW_ROWS = 10               # rows shown in the Sheets step preview (header and title rows included)
CHECK_BYTES = 4 * 1024 * 1024   # the UTF-8 check reads at most this much of a CSV file


@dataclass
class SampleSheet:
    """One sheet of the sample (a CSV file is one sheet named "")."""
    name: str
    visible: bool = True
    rows_approx: int | None = None          # below the header row, from the dimension record (Excel)
    header_row: int | None = None           # 1-based sheet row (CSV: record number); None = not found
    headers: list[str] = field(default_factory=list)
    preview: list[tuple[int, list[str]]] = field(default_factory=list)   # (row number, cell text)

    @property
    def readable(self) -> bool:
        return self.visible and self.header_row is not None


@dataclass
class SampleInfo:
    path: str
    file_name: str
    kind: str                               # xlsx | xlsm | csv
    size: int
    modified: float
    sheets: list[SampleSheet]
    encoding: str | None = None             # CSV: as detected (or as asked for)
    delimiter: str | None = None
    detected_encoding: str | None = None    # CSV: what detection found, whatever was asked for
    detected_delimiter: str | None = None

    @property
    def is_csv(self) -> bool:
        return self.kind == "csv"

    @property
    def visible_sheets(self) -> list[SampleSheet]:
        return [s for s in self.sheets if s.visible]

    @property
    def hidden_sheets(self) -> list[SampleSheet]:
        return [s for s in self.sheets if not s.visible]

    def sheet(self, name: str) -> SampleSheet:
        for s in self.sheets:
            if s.name == name:
                return s
        raise KeyError(name)

    def key(self) -> tuple:
        """Changes when the file on disk changes (C3-22: not re-read unless it changed)."""
        return (os.path.normcase(os.path.abspath(self.path)), self.size, self.modified)


def refusal(path) -> str | None:
    """The plain message for a path that can't be a sample file (IN-3, C3-04), else None."""
    p = Path(path)
    if not p.is_dir() and not p.exists():
        return f"{p.name} was not found. It may have been moved or deleted."
    _accepted, rows = screen_paths([p])
    for r in rows:
        if r.status in (REFUSED, SKIPPED):
            if r.status == SKIPPED:
                return f"{r.file_name} is an Excel lock file. Pick the workbook itself."
            return r.message
    return None


def file_key(path) -> tuple:
    st = os.stat(path)
    return (os.path.normcase(os.path.abspath(path)), st.st_size, st.st_mtime)


def cell_text(v) -> str:
    """A cell for the preview grid: dates as DD-MM-YYYY (UI-7), numbers as staged, text as typed."""
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        if (v.hour, v.minute, v.second) == (0, 0, 0):
            return v.strftime("%d-%m-%Y")
        return v.strftime("%d-%m-%Y %H:%M")
    if isinstance(v, dt.date):
        return v.strftime("%d-%m-%Y")
    return staged_text(v)


# ---------------------------------------------------------------------------------------------- inspect
def inspect(path, encoding: str | None = None, delimiter: str | None = None) -> SampleInfo:
    """Raises ``FileProblem`` (plain message) when the file can't be used as a sample."""
    p = Path(path)
    msg = refusal(p)
    if msg is not None:
        raise FileProblem("refused", msg)
    try:
        st = os.stat(p)
        with source.open_source(p) as fh:
            kind = source.sniff(fh.read(8))
            if kind == "ole":
                if source.ole_is_encrypted(fh):
                    raise FileProblem("password", f"{p.name} is password-protected. Remove the password, or pick "
                                                  "another file.")
                raise FileProblem("not_xlsx", f"{p.name} isn't an .xlsx workbook (it may be an old .xls file "
                                              "renamed). Save it as .xlsx in Excel, then pick it again.")
            fh.seek(0)
            ext = p.suffix.lower().lstrip(".")
            info = SampleInfo(str(p), p.name, ext, st.st_size, st.st_mtime, [])
            if kind == "zip":
                if info.kind not in ("xlsx", "xlsm"):
                    info.kind = "xlsx"
                _inspect_excel(fh, info)
            else:
                if ext != "csv":
                    raise FileProblem("not_xlsx", f"{p.name} isn't a valid Excel workbook.")
                _inspect_csv(fh, info, encoding, delimiter)
    except FileNotFoundError:
        raise FileProblem("missing", f"{p.name} was not found. It may have been moved or deleted.") from None
    except OSError as e:
        if source.is_sharing_violation(e):
            raise FileProblem("locked", f"{p.name} is open in another program. Close it, then pick it "
                                        "again.") from None
        raise FileProblem("unreadable", f"{p.name} can't be read.") from None
    return info


def _inspect_excel(fh, info: SampleInfo) -> None:
    try:
        book = excel.Book(fh)
    except excel.ExcelError:
        raise FileProblem("damaged", f"{info.file_name} can't be read. It may be damaged, or not an Excel "
                                     "workbook.") from None
    for s in book.sheets:
        sheet = SampleSheet(s.name, s.visible)
        info.sheets.append(sheet)
        if not s.visible:
            continue
        try:
            peek = book.peek(s.name)
        except excel.ExcelError:
            continue
        idx = detect.detect_header([v for _r, v in peek.rows], None)
        if idx is not None:
            sheet.header_row = peek.rows[idx][0]
            sheet.headers = detect.make_headers(peek.rows[idx][1])
            if peek.last_row is not None:
                sheet.rows_approx = max(0, peek.last_row - sheet.header_row)
    if not info.visible_sheets:
        raise FileProblem("sheet", f"{info.file_name} has no visible sheet.")
    _excel_preview(info)


def _excel_preview(info: SampleInfo) -> None:
    """The first rows of each visible sheet as Excel shows them (dates formatted), read with calamine's row
    iterator, which stops reading as soon as it has them."""
    import python_calamine as pc
    try:
        wb = pc.CalamineWorkbook.from_path(info.path)
    except Exception:           # noqa: BLE001 - calamine's own errors: no preview
        return
    for sheet in info.visible_sheets:
        try:
            sh = wb.get_sheet_by_name(sheet.name)
            c0 = sh.start[1] if sh.start else 0
            want = max(PREVIEW_ROWS, (sheet.header_row or 0) + 6)
            rows = []
            for i, row in enumerate(sh.iter_rows()):
                n = i + 1
                if n > want:
                    break
                rows.append((n, [""] * c0 + [cell_text(v) for v in row]))
            sheet.preview = rows
        except Exception:       # noqa: BLE001
            sheet.preview = []


def _inspect_csv(fh, info: SampleInfo, encoding: str | None, delimiter: str | None) -> None:
    check = detect.Utf8Check()
    head = fh.read(CHECK_BYTES)
    check.feed(head)
    if len(head) < CHECK_BYTES:
        check.feed(b"", final=True)
    info.detected_encoding = detect.encoding_from_check(check)
    info.encoding = encoding or info.detected_encoding
    text = detect.decode_sample(head[:detect.CSV_SAMPLE_BYTES], info.encoding)
    info.detected_delimiter = detect.detect_delimiter(text)
    info.delimiter = delimiter or info.detected_delimiter
    records = csvread.first_records(text, info.delimiter)
    sheet = SampleSheet("")
    idx = detect.detect_header(records, None)
    if idx is not None:
        sheet.header_row = idx + 1
        sheet.headers = detect.make_headers(records[idx])
    want = max(PREVIEW_ROWS, (sheet.header_row or 0) + 6)
    sheet.preview = [(i + 1, list(r)) for i, r in enumerate(records[:want])]
    info.sheets = [sheet]


# ---------------------------------------------------------------------------------------------- read (worker)
@dataclass
class SampleCounts:
    rows: int
    blank_rows: int
    hidden_rows: int
    limited: bool


def read_part(path: str, kind: str, sheet: str, header_row: int, width: int, encoding: str | None,
              delimiter: str | None, out_path: str, limit: int, report=None, stop=None) -> SampleCounts:
    """Worker task: up to ``limit`` data rows of one sheet (or CSV file) into raw staged text."""
    name = Path(path).name
    try:
        with source.open_source(Path(path)) as fh:
            if kind == "csv":
                c = csvread.read_csv(fh, encoding or "utf-8", delimiter or ",", header_row, width, out_path,
                                     report=report, stop=stop, limit=limit)
            else:
                c = excel.read_sheet(path, fh, sheet, header_row, width, out_path, report=report, stop=stop,
                                     limit=limit)
    except excel.ExcelError:
        raise FileProblem("damaged", f"{name} can't be read. It may be damaged.") from None
    except OSError as e:
        if source.is_sharing_violation(e):
            raise FileProblem("locked", f"{name} is open in another program. Close it, then try again.") from None
        raise
    return SampleCounts(c.rows, c.blank_rows, c.hidden_rows, c.limited)
