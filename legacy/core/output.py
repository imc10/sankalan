"""Writing the consolidated file (OUT-1 .. OUT-8) and reading it back for the totals check (OUT-11)."""
from __future__ import annotations

import csv
import os
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

EXCEL_MAX_ROWS = 1_048_576
# OUT-7: Indian grouping 1,23,45,678.00 for zero and positive values. Negative values use the
# standard format, because Excel conditional sections don't reliably show the minus sign.
INDIAN_FMT = r'[>=10000000]##\,##\,##\,##0.00;[>=100000]##\,##\,##0.00;##,##0.00'
PLAIN_FMT = "#,##0.00"
DATE_FMT = "dd-mm-yyyy"
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


class OutputExists(Exception):
    pass


class TooManyRows(Exception):
    pass


def build_filename(pattern: str, client: str, task: str, fmt: str, period: date | None = None,
                   now: datetime | None = None) -> str:
    """OUT-5: tokens {client} {task} {yyyymm} {date} {time}. {yyyymm} is the month of the latest date
    in the data (first Date column), or this month when the data has no dates."""
    now = now or datetime.now()
    period = period or now.date()

    def clean(s):
        return re.sub(r"\s+", "-", _BAD.sub("", str(s).strip()))

    name = (pattern or "{client}_{task}_{yyyymm}")
    name = name.replace("{client}", clean(client)).replace("{task}", clean(task))
    name = name.replace("{yyyymm}", period.strftime("%Y%m")).replace("{date}", now.strftime("%Y%m%d"))
    name = name.replace("{time}", now.strftime("%H%M%S"))
    name = _BAD.sub("", name).strip(" .") or "consolidated"
    ext = ".csv" if fmt == "csv" else ".xlsx"
    if not name.lower().endswith(ext):
        name += ext
    return name


def _csv_value(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (datetime, date)):
        return v.strftime("%d-%m-%Y")
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return ("%.10f" % v).rstrip("0").rstrip(".")
    return str(v)


def write_output(path: Path, headers, types, rows, *, fmt="xlsx", indian=True, issues=None,
                 csv_encoding="utf-8-sig", csv_delimiter=",", overwrite=False, progress=None,
                 cancel=None):
    """Write via a temp file in the system temp folder, then move into place (SEC-3).
    types: per column 'text'|'number'|'date'|'meta'."""
    from .readers import Cancelled
    path = Path(path)
    if path.exists() and not overwrite:
        raise OutputExists(str(path))
    if fmt != "csv" and len(rows) + 1 > EXCEL_MAX_ROWS:
        raise TooManyRows(f"{len(rows):,} rows is more than Excel's limit of {EXCEL_MAX_ROWS - 1:,}. "
                          f"Choose CSV output instead.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="sankalan_", suffix=path.suffix)
    os.close(fd)
    try:
        if fmt == "csv":
            with open(tmp, "w", newline="", encoding=csv_encoding) as fh:
                w = csv.writer(fh, delimiter=csv_delimiter)
                w.writerow(headers)
                for i, r in enumerate(rows):
                    if cancel and i % 20000 == 0 and cancel():
                        raise Cancelled()
                    w.writerow([_csv_value(v) for v in r])
                    if progress and i % 20000 == 0:
                        progress(i, len(rows))
        else:
            _write_xlsx(tmp, headers, types, rows, indian, issues, progress, cancel)
        shutil.move(tmp, path)
        if os.name != "nt":   # mkstemp creates 0600; give the output normal permissions
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(path, 0o666 & ~umask)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def _write_xlsx(tmp, headers, types, rows, indian, issues, progress, cancel):
    from .xlsx_writer import write_xlsx
    sheets = [("Consolidated", headers, rows, types)]
    if issues:
        cols = ["File", "Sheet", "Row", "Column", "Value", "Check", "Severity", "Problem"]
        irows = [[it.file, it.sheet, it.row, it.column, it.value, it.rule, it.severity.capitalize(), it.message]
                 for it in issues]
        sheets.append(("Issues", cols, irows, ["text"] * len(cols)))
    write_xlsx(tmp, sheets, indian=indian, indian_fmt=INDIAN_FMT, plain_fmt=PLAIN_FMT, date_fmt=DATE_FMT,
               progress=progress, cancel=cancel)


def write_issue_list(path: Path, issues):
    """Validation › Issue report: export the issue list to .xlsx."""
    import xlsxwriter
    path = Path(path)
    wb = xlsxwriter.Workbook(str(path))
    ws = wb.add_worksheet("Issues")
    bold = wb.add_format({"bold": True, "bg_color": "#F2F2F2", "bottom": 1})
    cols = ["File", "Sheet", "Row", "Column", "Value", "Check", "Severity", "Problem"]
    for c, h in enumerate(cols):
        ws.write_string(0, c, h, bold)
    for i, it in enumerate(issues, start=1):
        for c, v in enumerate([it.file, it.sheet, it.row, it.column, it.value, it.rule,
                               it.severity.capitalize(), it.message]):
            ws.write(i, c, v)
    for c, w in enumerate([28, 14, 8, 18, 22, 18, 10, 70]):
        ws.set_column(c, c, w)
    ws.freeze_panes(1, 0)
    wb.close()
    return path


def read_back_totals(path: Path, fmt: str, columns, csv_encoding="utf-8-sig", csv_delimiter=","):
    """OUT-11: re-read the written file and sum the given columns."""
    path = Path(path)
    sums = {c: 0.0 for c in columns}
    if fmt == "csv":
        with open(path, newline="", encoding=csv_encoding) as fh:
            r = csv.reader(fh, delimiter=csv_delimiter)
            hdr = next(r)
            idx = {c: hdr.index(c) for c in columns if c in hdr}
            for row in r:
                for c, i in idx.items():
                    v = row[i] if i < len(row) else ""
                    try:
                        sums[c] += float(v) if v != "" else 0.0
                    except ValueError:
                        pass
    else:
        from .xlsx import XlsxBook
        with open(path, "rb") as fh:
            sums.update(XlsxBook(fh.read()).sum_columns("Consolidated", list(columns)))
    return sums
