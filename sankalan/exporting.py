r"""Exports as Job work (EXP-3, EXP-4, EXP-7; Tech spec Exports; spike S2, confirmed 17-11-2026).

DuckDB's external access is off, so it can only write inside the data folder and ``%TEMP%\Sankalan``. An export:

1. DuckDB writes the rows (no header) to ``%TEMP%\Sankalan\<id>.csv.part``.
2. Python writes ``<destination>.part`` next to the chosen file: the BOM (EF BB BF) for UTF-8 with BOM, the header
   line, then the rows streamed from the temp part in 1 MiB chunks, checking for Cancel between chunks.
3. ``<destination>.part`` is renamed to the file name. A cross-volume destination works, since the rows are copied.

Cancel or a failure deletes both ``.part`` files (EXP-7); the temp folder is emptied after every Job anyway.
Overwriting an existing file needs ``overwrite=True``, which the UI passes only after the user confirms (EXP-4).
"""
from __future__ import annotations

import csv
import io
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from sankalan.jobs import JobContext
from sankalan.model.export import ExportOptions
from sankalan.query.export import ExportQuery, copy_csv

BOM = b"\xef\xbb\xbf"
CHUNK = 1 << 20
STAGE_QUERY = "Exporting"
STAGE_WRITE = "Writing file"


class ExportExists(Exception):
    """The destination file exists and overwriting wasn't confirmed."""

    def __init__(self, path: Path):
        super().__init__(str(path))
        self.path = path


@dataclass(frozen=True)
class ExportResult:
    path: Path
    rows: int


def header_line(headers: list[str], delimiter: str) -> bytes:
    """The header as DuckDB would quote it: a name with the delimiter, a quote or a line break is quoted."""
    buf = io.StringIO()
    csv.writer(buf, delimiter=delimiter, quotechar='"', lineterminator="\n",
               quoting=csv.QUOTE_MINIMAL).writerow(headers)
    return buf.getvalue().encode("utf-8")


def _remove(path: Path) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _after_chunk() -> None:
    """Called after each chunk is written (tests use it to cancel mid-stream)."""


def _check_destination(dest: Path, overwrite: bool) -> None:
    if not dest.parent.is_dir():
        raise FileNotFoundError(str(dest.parent))
    if dest.exists() and not overwrite:
        raise ExportExists(dest)


def export(ctx: JobContext, temp_dir: Path, query: ExportQuery, dest: Path, options: ExportOptions, *,
           overwrite: bool = False) -> ExportResult:
    dest = Path(dest)
    _check_destination(dest, overwrite)
    temp_part = Path(temp_dir) / f"{uuid.uuid4().hex}.csv.part"
    dest_part = dest.with_name(dest.name + ".part")
    ctx.on_abort(lambda: (_remove(temp_part), _remove(dest_part)))
    try:
        ctx.set_stage(STAGE_QUERY)
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        rows = copy_csv(ctx.cursor(), query, temp_part, options.delimiter)
        ctx.check_cancelled()
        ctx.set_stage(STAGE_WRITE, rows)
        done = 0
        with open(temp_part, "rb") as src, open(dest_part, "wb") as out:
            if options.bom:
                out.write(BOM)
            out.write(header_line(query.headers, options.delimiter))
            while True:
                chunk = src.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                done = min(rows, done + chunk.count(b"\n"))
                ctx.set_rows(done)
                _after_chunk()
                ctx.check_cancelled()
        os.replace(dest_part, dest)
    finally:
        _remove(temp_part)
    return ExportResult(dest, rows)


def export_many(ctx: JobContext, temp_dir: Path, items: list[tuple[ExportQuery, Path]], options: ExportOptions, *,
                overwrite: bool = False) -> list[ExportResult]:
    """Several files in one Job, e.g. Export all outputs (DO-7, C6-06): one CSV file per output. Every
    destination is checked before anything is written; a cancel deletes the file being written and keeps the
    ones already finished."""
    for _q, dest in items:
        _check_destination(Path(dest), overwrite)
    return [export(ctx, temp_dir, q, dest, options, overwrite=overwrite) for q, dest in items]
