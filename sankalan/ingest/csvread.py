"""CSV files (IN-4, T12): detection for the probe, and the full read into raw staged text.

Read with Python's ``csv`` module on one core (a CSV can't be split safely when values may contain line breaks).
Windows-1252 is converted to UTF-8 with the standard library. Row numbers are record numbers (the header record is
row 1 when it is the first line), which is the row Excel shows when it opens the file.
"""
from __future__ import annotations

import csv
import io
import sys
from dataclasses import dataclass
from typing import Callable

from sankalan.ingest import detect
from sankalan.ingest.canonical import RawWriter, is_blank_row

PROGRESS_EVERY = 5000

csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))


def first_records(sample_text: str, delimiter: str, n: int = detect.HEADER_SCAN_ROWS) -> list[list]:
    out = []
    try:
        for rec in csv.reader(io.StringIO(sample_text, newline=""), delimiter=delimiter):
            out.append(rec)
            if len(out) >= n:
                break
    except csv.Error:
        pass
    return out


@dataclass
class ReadCounts:
    rows: int = 0
    blank_rows: int = 0
    hidden_rows: int = 0
    limited: bool = False       # stopped at the row limit: more rows follow


def read_csv(fh, encoding: str, delimiter: str, header_row: int, width: int, out_path, *,
             report: Callable[[int], None] | None = None, stop: Callable[[], bool] | None = None,
             limit: int | None = None) -> ReadCounts:
    """Write the raw staged text: records after ``header_row`` (1-based record number), first ``width`` fields,
    blank records dropped and counted (T14). ``fh`` is the open binary source file. ``limit`` stops after that many
    data rows (the New template wizard's sample, TPL-3), so the rest of the file is never read."""
    fh.seek(0)
    text = io.TextIOWrapper(fh, encoding=detect.read_codec(encoding), errors="replace", newline="")
    counts = ReadCounts()
    pending = 0
    try:
        with RawWriter(out_path, width) as w:
            for recno, rec in enumerate(csv.reader(text, delimiter=delimiter), start=1):
                if recno <= header_row:
                    continue
                vals = (rec + [""] * width)[:width] if len(rec) != width else rec
                if is_blank_row(vals):
                    counts.blank_rows += 1
                else:
                    w.write(recno, vals)
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
    finally:
        text.detach()
    if report is not None and pending:
        report(pending)
    return counts
