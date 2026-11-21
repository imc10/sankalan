"""Probe: builds the Files-step list, one row per file and sheet (IN-1 to IN-15, RUN-7, TPL-6).

``screen_paths`` runs in the app process and is cheap: folders and unsupported types are refused, lock files and
the same file added twice are skipped (IN-10). ``probe_file`` runs in a reader worker, one per file: file type from
content, password protection, sharing violations, sheets to read, header row, CSV encoding and delimiter,
approximate row count and SHA-256. Messages are plain text for the file list (UI-6) and never contain cell values.

Every Excel file that opens lists all its sheets with visibility and an approximate row count from the dimension
record (``SheetEntry``, T47), for Choose sheets (SHT-4). A file whose sheets don't satisfy the rule, or the user's
choice, is one Sheet not found row (``problem = "sheet"``) naming its visible sheets (SHT-6).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from sankalan.ingest import csvread, detect, source
from sankalan.ingest.excel import ExcelError, ExcelPassword, open_book
from sankalan.ingest.source import FileProblem
from sankalan.model.template import (ENCODING_LABELS, SHEETS_ALL_VISIBLE, SHEETS_BY_NAME, SourceSettings)

READY, WARNING, ERROR, SKIPPED, REFUSED = "ready", "warning", "error", "skipped", "refused"
SUPPORTED = (".xlsx", ".xlsm", ".xlsb", ".xls", ".csv")        # IN-3 (D38)


@dataclass(frozen=True)
class SheetEntry:
    """One sheet of an Excel file (T47): its name, whether it's visible, and about how many rows it has (the
    dimension's last row − 1, so the header row is not counted; None for a hidden sheet or no dimension)."""
    name: str
    visible: bool
    rows_approx: int | None = None


@dataclass
class FileSheet:
    """One row of the file list. ``status``: ready, warning (can still be read), error (blocks the run until
    excluded or fixed, IN-15), skipped (listed, never read, IN-10) or refused (not added: folders, .txt)."""
    path: str
    file_name: str
    status: str
    message: str = ""
    sheet: str = ""                     # "" for a CSV file
    kind: str = ""                      # xlsx | xlsm | xlsb | xls | csv
    size: int = 0
    modified: float | None = None       # seconds since the epoch
    sha256: str = ""
    header_row: int | None = None       # 1-based sheet row (CSV: record number)
    headers: list[str] = field(default_factory=list)
    rows_approx: int | None = None      # approximate until Validate reads the file (IN-11)
    hidden_rows: int = 0                # below the header; exact for Excel files
    hidden_sheets: list[str] = field(default_factory=list)
    encoding: str | None = None         # CSV only
    delimiter: str | None = None        # CSV only
    notes: list[str] = field(default_factory=list)       # information lines (header row, hidden data skipped)
    problem: str = ""                   # error code: password, locked, missing, sheet, header, damaged, ...
    duplicate_of: dict | None = None    # RUN-7: {"run": "R-0001", "loaded_on": datetime}
    headers_match: bool | None = None   # TPL-6: every template column found and no new header
    sheets: list[SheetEntry] = field(default_factory=list)   # every sheet of an Excel file that opened (T47)

    @property
    def readable(self) -> bool:
        return self.status in (READY, WARNING)


def resolved_key(path) -> str:
    try:
        p = Path(path).resolve()
    except OSError:
        p = Path(os.path.abspath(path))
    return os.path.normcase(str(p))


def screen_paths(paths, existing=()) -> tuple[list[str], list[FileSheet]]:
    """Split dropped or picked paths into files to probe and rows that are skipped or refused. ``existing`` are
    the paths already in the list."""
    seen = {resolved_key(p) for p in existing}
    accepted: list[str] = []
    rows: list[FileSheet] = []
    for item in paths:
        p = Path(item)
        name = p.name
        if p.is_dir():
            rows.append(FileSheet(str(p), name, REFUSED, "Folders can't be added. Add the files inside it."))
            continue
        if name.startswith("~$"):
            rows.append(FileSheet(str(p), name, SKIPPED, "Excel lock file, skipped."))
            continue
        ext = p.suffix.lower()
        if ext not in SUPPORTED:
            rows.append(FileSheet(str(p), name, REFUSED, refused_message(name)))
            continue
        key = resolved_key(p)
        if key in seen:
            rows.append(FileSheet(str(p), name, SKIPPED, "Same file added twice, skipped."))
            continue
        seen.add(key)
        accepted.append(str(p))
    return accepted, rows


def refused_message(name: str) -> str:
    return f"{name}: only .xlsx, .xlsm, .xlsb, .xls and .csv files can be added."


def _password(name: str) -> FileProblem:
    return FileProblem("password", f"{name} is password-protected. Remove the password at source, or exclude the "
                                   "file.")


# ---------------------------------------------------------------------------------------------- in a worker
def probe_file(path: str, settings: SourceSettings, known_names: set[str] | None = None,
               chosen: list[str] | None = None, report=None, stop=None) -> list[FileSheet]:
    """Probe one file. Never raises for a problem with the file: it becomes an error row. ``chosen``: the sheets
    the user chose for this file in this run (SHT-3), read instead of the template's rule."""
    p = Path(path)
    base = FileSheet(str(p), p.name, ERROR, kind=p.suffix.lower().lstrip("."))
    try:
        st = os.stat(p)
        base.size, base.modified = st.st_size, st.st_mtime
        with source.open_source(p) as fh:
            try:
                base.kind = source.file_kind(fh, p.name)
            except FileProblem as e:
                if e.kind == "password":
                    raise _password(p.name) from None
                raise
            if base.kind != "csv":
                return _probe_excel(fh, base, settings, known_names, chosen)
            return [_probe_csv(fh, base, settings, known_names)]
    except FileProblem as e:
        base.message = e.message
        base.problem = e.kind
        return [base]
    except FileNotFoundError:
        base.message, base.problem = f"{p.name} was not found. It may have been moved or deleted.", "missing"
        return [base]
    except OSError as e:
        locked = source.is_sharing_violation(e)
        base.message = source.locked_message(p.name) if locked else f"{p.name} can't be read."
        base.problem = "locked" if locked else "unreadable"
        return [base]


def _copy(base: FileSheet, **kw) -> FileSheet:
    d = dict(base.__dict__)
    d["notes"] = list(base.notes)
    d.update(kw)
    return FileSheet(**d)


def sheet_entries(book) -> list[SheetEntry]:
    """Every sheet in workbook order with its approximate row count (dimension only, no header scan, T47)."""
    out = []
    for s in book.sheets:
        rows = None
        if s.visible:
            try:
                last = book.last_row(s.name)
            except ExcelError:
                last = None
            rows = max(0, last - 1) if last else None
        out.append(SheetEntry(s.name, s.visible, rows))
    return out


def sheets_found_message(name: str, visible: list[str]) -> str:
    """Sheet not found (SHT-6, T47): "Sheets found: Sales Nov, Returns Nov", or "<file> has no visible sheet."."""
    return f"Sheets found: {', '.join(visible)}" if visible else f"{name} has no visible sheet."


def resolve_sheets(settings: SourceSettings, sheets: list[SheetEntry],
                   chosen: list[str] | None = None) -> list[str] | None:
    """The sheets to read (T47), or None when the file is in Sheet not found:

    - ``chosen``: the chosen names matched case-insensitively to visible sheets, in workbook order; any chosen sheet
      missing or hidden is Sheet not found (SHT-9);
    - by name: each named sheet, in the order named; any named sheet missing or hidden is Sheet not found, even if
      others match (SHT-6);
    - first visible / all visible: as before; no visible sheet is Sheet not found."""
    visible = [s.name for s in sheets if s.visible]
    if chosen is not None:
        want = {c.lower() for c in chosen}
        found = [v for v in visible if v.lower() in want]
        return found if found and len({f.lower() for f in found}) == len(want) else None
    if settings.sheets == SHEETS_BY_NAME:
        targets: list[str] = []
        for want in settings.sheet_names:
            match = next((v for v in visible if v.lower() == want.lower()), None)
            if match is None:
                return None
            if match not in targets:
                targets.append(match)
        return targets
    if not visible:
        return None
    return visible if settings.sheets == SHEETS_ALL_VISIBLE else visible[:1]


def rule_ticks(settings: SourceSettings, sheets: list[SheetEntry]) -> list[str]:
    """The visible sheets the template's rule selects, for the Choose sheets dialog's first ticks (SHT-5): by name
    the named ones that exist (in workbook order), first visible, or every visible sheet."""
    visible = [s.name for s in sheets if s.visible]
    if settings.sheets == SHEETS_BY_NAME:
        names = {n.lower() for n in settings.sheet_names}
        return [v for v in visible if v.lower() in names]
    return visible if settings.sheets == SHEETS_ALL_VISIBLE else visible[:1]


def _probe_excel(fh, base: FileSheet, settings: SourceSettings, known,
                 chosen: list[str] | None = None) -> list[FileSheet]:
    name = base.file_name
    try:
        book = open_book(fh, base.kind)
    except ExcelPassword:
        raise _password(name) from None
    except ExcelError:
        raise FileProblem("damaged", f"{name} can't be read. It may be damaged, or not an Excel workbook.") from None
    base.sha256 = source.sha256_of(fh)
    base.sheets = sheet_entries(book)
    visible = [s.name for s in base.sheets if s.visible]
    base.hidden_sheets = [s.name for s in base.sheets if not s.visible]

    out: list[FileSheet] = []
    targets = resolve_sheets(settings, base.sheets, chosen)
    if targets is None:                 # one Sheet not found row for the file (T47)
        return [_copy(base, sheet="", status=ERROR, message=sheets_found_message(name, visible), problem="sheet")]

    for sheet in targets:
        row = _copy(base, sheet=sheet)
        try:
            peek = book.peek(sheet)
            idx = detect.detect_header([v for _r, v in peek.rows], known)
            if idx is None:
                row.status, row.message, row.problem = ERROR, f"Header not found in sheet {sheet}.", "header"
                out.append(row)
                continue
            row.header_row = peek.rows[idx][0]
            row.headers = detect.make_headers(peek.rows[idx][1])
            scan = book.scan(sheet, errors=False)
            row.hidden_rows = sum(1 for r in scan.hidden_rows if r > row.header_row)
            if peek.last_row is not None:
                row.rows_approx = max(0, peek.last_row - row.header_row - row.hidden_rows)
        except ExcelError:
            row.status, row.message, row.problem = ERROR, f"Sheet {sheet} can't be read.", "damaged"
            out.append(row)
            continue
        row.status = READY
        _info(row)
        out.append(row)
    return out


def _probe_csv(fh, base: FileSheet, settings: SourceSettings, known) -> FileSheet:
    check = detect.Utf8Check()
    lines = {"n": 0, "last": b""}

    def each(chunk: bytes):
        check.feed(chunk)
        lines["n"] += chunk.count(b"\n")
        lines["last"] = chunk[-1:]

    base.sha256 = source.sha256_of(fh, extra=each)
    check.feed(b"", final=True)
    n_lines = lines["n"] + (1 if lines["last"] not in (b"", b"\n") else 0)
    base.encoding = settings.csv_encoding or detect.encoding_from_check(check)
    fh.seek(0)
    sample = fh.read(detect.CSV_SAMPLE_BYTES)
    text = detect.decode_sample(sample, base.encoding)
    base.delimiter = settings.csv_delimiter or detect.detect_delimiter(text)
    records = csvread.first_records(text, base.delimiter)
    idx = detect.detect_header(records, known)
    if idx is None:
        base.status, base.message, base.problem = ERROR, f"Header not found in {base.file_name}.", "header"
        return base
    base.header_row = idx + 1
    base.headers = detect.make_headers(records[idx])
    base.rows_approx = max(0, n_lines - base.header_row)
    base.status = READY
    _info(base)
    return base


def _info(row: FileSheet) -> None:
    if row.header_row and row.header_row != 1:
        row.notes.append(f"Header found on row {row.header_row}.")
    if row.hidden_rows:
        row.notes.append(f"{row.hidden_rows:,} hidden row{'s' if row.hidden_rows != 1 else ''} skipped.")
    if row.hidden_sheets:
        names = ", ".join(row.hidden_sheets)
        row.notes.append(f"Hidden sheet{'s' if len(row.hidden_sheets) != 1 else ''} {names} skipped.")
    if row.encoding:
        row.notes.append(f"Encoding {ENCODING_LABELS[row.encoding]}.")
