r"""Ingestion stages as Job work (Tech spec, Ingestion): probe (Files step), then read and convert (Validate step).

``probe`` builds the file list. ``load`` reads every chosen file and sheet in reader workers into
``_staging\<id>\raw\<file-index>.csv`` and converts them with DuckDB into ``data.parquet`` and
``conversion_failures.parquet``. Re-check (VR-6) or a return to Mapping runs ``load`` again on the same staging.
A cancelled or failed load deletes the staging folder (decision confirmed 16-11-2026); the wizard starts a new one.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from sankalan import mapping as mapping_mod
from sankalan.db.datafolder import DataFolder, Staging
from sankalan.ingest import csvread, excel, source
from sankalan.ingest.probe import ERROR, WARNING, FileSheet, probe_file, screen_paths
from sankalan.ingest.workers import TaskFailed, run_tasks
from sankalan.jobs import JobContext
from sankalan.model.run import run_label
from sankalan.model.template import Column, SourceSettings, active
from sankalan.query import catalogue as q
from sankalan.query import convert


class LoadFailed(Exception):
    """A file that was Ready at the Files step can't be read now. ``message`` names the file (UI-6)."""

    def __init__(self, file_index: int, message: str):
        super().__init__(file_index)
        self.file_index = file_index
        self.message = message


# ---------------------------------------------------------------------------------------------- probe
def probe(ctx: JobContext, paths, *, settings: SourceSettings, columns: list[Column] | None = None,
          template_id: str | None = None, existing=(), workers: int | None = None) -> list[FileSheet]:
    """The Files-step rows for newly added ``paths``. With ``template_id``, files whose contents were already
    loaded in an earlier run of that template (checked
    on the Job's connection) get a warning naming the run and its date (RUN-7)."""
    accepted, screened = screen_paths(paths, existing)
    ctx.set_stage("Checking files")
    known = mapping_mod.known_names(columns) if columns else None
    results = run_tasks(probe_file, [(p, settings, known) for p in accepted], workers=workers,
                        should_stop=lambda: ctx.cancel_requested) if accepted else []
    rows_by_path: dict[str, list[FileSheet]] = {}
    for p, res in zip(accepted, results):
        if isinstance(res, TaskFailed):
            res = [FileSheet(p, Path(p).name, ERROR, res.message or f"{Path(p).name} can't be read.",
                             problem=res.kind)]
        rows_by_path[p] = res
    for row in screened:
        rows_by_path.setdefault(row.path, []).append(row)
    out = [r for p in (str(x) for x in paths) for r in rows_by_path.pop(p, [])]
    out += [r for rs in rows_by_path.values() for r in rs]

    if columns:
        for r in out:
            if r.readable:
                r.headers_match = mapping_mod.headers_match(columns, r.headers)
    if template_id is not None:
        ctx.check_cancelled()
        seen = q.runs_with_sha256(ctx.cursor(), template_id, [r.sha256 for r in out if r.readable])
        for r in out:
            if r.readable and r.sha256 in seen:
                number, loaded_on = seen[r.sha256]
                r.duplicate_of = {"run": run_label(number), "loaded_on": loaded_on}
                r.status = WARNING
                r.message = (f"{r.file_name} has the same contents as a file loaded in {run_label(number)} on "
                             f"{loaded_on:%d-%m-%Y}. Remove it, or Load anyway.")
    return out


# ---------------------------------------------------------------------------------------------- read + convert
@dataclass
class LoadPart:
    """One file and sheet to read, with its mapping (column ID → source column position, or None)."""
    file_index: int
    path: str
    kind: str                       # xlsx | xlsm | xlsb | xls | csv
    sheet: str
    header_row: int
    width: int
    mapping: dict[str, int | None]
    encoding: str | None = None
    delimiter: str | None = None
    rows_approx: int | None = None

    @classmethod
    def from_probe(cls, file_index: int, row: FileSheet, mapping: dict[str, int | None]) -> "LoadPart":
        return cls(file_index, row.path, row.kind, row.sheet, row.header_row, len(row.headers), dict(mapping),
                   row.encoding, row.delimiter, row.rows_approx)


@dataclass
class PartResult:
    file_index: int
    rows: int               # data rows read (not blank, not hidden)
    blank_rows: int         # dropped, IN-8 / T14
    hidden_rows: int        # dropped, IN-13


@dataclass
class LoadResult:
    parts: list[PartResult]
    rows_loaded: int                                    # rows in data.parquet
    failures: dict[str, int] = field(default_factory=dict)   # column ID -> values that failed conversion
    data: Path | None = None
    failures_file: Path | None = None

    @property
    def rows_read(self) -> int:
        return sum(p.rows for p in self.parts)

    @property
    def blank_rows(self) -> int:
        return sum(p.blank_rows for p in self.parts)

    @property
    def hidden_rows(self) -> int:
        return sum(p.hidden_rows for p in self.parts)


def raw_path(staging: Staging, file_index: int) -> Path:
    return staging.raw / f"{file_index}.csv"


def read_part(path: str, kind: str, sheet: str, header_row: int, width: int, encoding: str | None,
              delimiter: str | None, out_path: str, report=None, stop=None) -> PartResult:
    """Worker task: one file and sheet into raw staged text."""
    name = Path(path).name
    try:
        with source.open_source(Path(path)) as fh:
            if kind == "csv":
                c = csvread.read_csv(fh, encoding or "utf-8", delimiter or ",", header_row, width, out_path,
                                     report=report, stop=stop)
            else:
                c = excel.read_sheet(path, fh, sheet, header_row, width, out_path, report=report, stop=stop,
                                     kind=kind)
    except excel.ExcelError:
        raise source.FileProblem("damaged", f"{name} can't be read. It may be damaged.") from None
    except OSError as e:
        if source.is_sharing_violation(e):
            raise source.FileProblem("locked", source.locked_message(name)) from None
        raise
    return PartResult(-1, c.rows, c.blank_rows, c.hidden_rows)


def load(ctx: JobContext, folder: DataFolder, staging: Staging, parts: list[LoadPart], columns: list[Column],
         *, workers: int | None = None) -> LoadResult:
    """Read (workers, in parallel) then convert (DuckDB). Raises ``LoadFailed`` naming the first file that can't
    be read; on cancel or failure the staging folder is deleted."""
    ctx.on_abort(lambda: folder.discard_staging(staging))
    _clear(staging)
    cols = active(columns)
    ctx.set_stage("Reading files", rows_total=sum(p.rows_approx or 0 for p in parts) or None)
    tasks = [(p.path, p.kind, p.sheet, p.header_row, p.width, p.encoding, p.delimiter,
              str(raw_path(staging, p.file_index))) for p in parts]
    results = run_tasks(read_part, tasks, workers=workers, on_rows=ctx.add_rows,
                        should_stop=lambda: ctx.cancel_requested)
    ctx.check_cancelled()
    out: list[PartResult] = []
    for p, res in zip(parts, results):
        if isinstance(res, TaskFailed):
            raise LoadFailed(p.file_index, res.message or f"{Path(p.path).name} can't be read.")
        res.file_index = p.file_index
        out.append(res)

    ctx.set_stage("Converting")
    cur = ctx.cursor()
    raws = [convert.RawPart(p.file_index, p.sheet, raw_path(staging, p.file_index), p.width, p.mapping)
            for p in parts]
    data = staging.path / convert.DATA
    fails = staging.path / convert.FAILURES
    convert.write_data(cur, raws, cols, staging.id, data)
    ctx.check_cancelled()
    convert.write_failures(cur, raws, cols, fails)
    result = LoadResult(out, convert.parquet_rows(cur, data), convert.failure_counts(cur, fails), data, fails)
    return result


def _clear(staging: Staging) -> None:
    staging.raw.mkdir(parents=True, exist_ok=True)
    for f in staging.raw.iterdir():
        if f.is_file():
            f.unlink()
    for name in (convert.DATA, convert.FAILURES):
        try:
            os.remove(staging.path / name)
        except FileNotFoundError:
            pass
