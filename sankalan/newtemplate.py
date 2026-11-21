r"""The New template wizard as Job work (UX-3, F1, TPL-3; C3-01 to C3-22).

Nothing is loaded into the dataset and nothing is written under ``t\`` until Save (C3-02, C3-20). The sample rows
(up to 100,000) are read into a staging folder ``_staging\<id>\`` with the same reader and convert code as a run,
so the rules' dry-run counts and the default outputs' previews behave exactly like a run (Tech spec VR-8, DO-8).
The staging folder lives while the wizard is open; it is removed on Save, Cancel, leaving the wizard, a cancelled
or failed read, and at start-up (decision confirmed 16-11-2026).

Steps:

1. ``inspect`` the picked file; ``check_name`` (unique within the client, C3-05).
2. ``sheets_to_read`` for the chosen setting; ``stage`` reads the sample and profiles its columns (``detect``).
3. Columns are drafted from the profiles (``draft_columns``).
4. ``convert`` writes the sample's ``data.parquet`` (with text companions) for the drafted columns, then
   ``dry_run`` counts each rule's failures and keeps the first 20 (VR-8).
5. ``preview`` runs a default output on the sample (DO-8).
6. ``build_template`` + ``save`` (``create_template``, version 1).
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path

from sankalan import manage
from sankalan.db.datafolder import DataFolder, Staging
from sankalan.ingest import sample as smp
from sankalan.ingest.detect import norm
from sankalan.ingest.sample import SampleInfo
from sankalan.ingest.workers import TaskFailed, run_tasks
from sankalan.jobs import JobContext
from sankalan.model.rule import UNIQUE, Rule, with_type_rules
from sankalan.model.template import (DATE, DATE_FORMATS, DECIMALS_DEFAULT, NUMBER, SHEETS_ALL_VISIBLE,
                                     SHEETS_BY_NAME, TEXT, Column, DefaultOutput, SourceSettings, Template)
from sankalan.query import catalogue as q
from sankalan.query import convert
from sankalan.query import sample as qs

STEPS = ["Sample file", "Sheets", "Columns", "Rules", "Default outputs", "Review"]
DETECT_SHARE = Decimal("0.8")       # a column is Number / Date when at least 80% of its values look like one
EXCEL_DATES = "Excel dates"


class SampleProblem(ValueError):
    """The sample can't be used as it is; ``str(e)`` is the plain message shown on the step."""


# ---------------------------------------------------------------------------------------------- step 1
def inspect(ctx: JobContext, path, encoding: str | None = None, delimiter: str | None = None) -> SampleInfo:
    ctx.set_stage("Opening the sample file")
    try:
        return smp.inspect(path, encoding, delimiter)
    except smp.FileProblem as e:
        raise SampleProblem(e.message) from None


def check_name(ctx: JobContext, client_id: str, name: str) -> str:
    """The name to store, or ``NameRefused`` ("… is already in use", C3-05)."""
    return manage.check_name(name, q.template_names(ctx.cursor(), client_id), what="template")


# ---------------------------------------------------------------------------------------------- step 2
def default_source(info: SampleInfo) -> SourceSettings:
    """By name with the first visible sheet ticked (the canvas starts on "By name"); a CSV has no sheets."""
    if info.is_csv:
        return SourceSettings()
    return SourceSettings(SHEETS_BY_NAME, [info.visible_sheets[0].name])


def sheets_to_read(info: SampleInfo, source: SourceSettings) -> list[str]:
    """The sample's sheets the setting reads (IN-5): hidden sheets never (IN-13)."""
    if info.is_csv:
        return [""]
    visible = [s.name for s in info.visible_sheets]
    if source.sheets == SHEETS_BY_NAME:
        wanted = {n.casefold() for n in source.sheet_names}
        return [n for n in visible if n.casefold() in wanted]
    if source.sheets == SHEETS_ALL_VISIBLE:
        return visible
    return visible[:1]


def sheets_problem(info: SampleInfo, source: SourceSettings) -> str | None:
    names = sheets_to_read(info, source)
    if not names:
        return "Tick at least one sheet to read."
    for n in names:
        if info.sheet(n).header_row is None:
            return (f"Header not found in {info.file_name}." if info.is_csv else
                    f"Header not found in sheet {n}. Pick another sheet, or fix the sample file.")
    return None


# ---------------------------------------------------------------------------------------------- stage (read)
@dataclass
class SourceColumn:
    """One header of the sample (headers in several sheets matched as a run matches them, MAP-2)."""
    header: str
    positions: list[int | None]         # position in each part (None = not in that sheet)
    profile: qs.Profile = field(default_factory=qs.Profile)


@dataclass
class StagedSample:
    staging: Staging
    key: tuple                          # file and settings it was read with (C3-22)
    file_name: str
    parts: list[convert.RawPart]
    rows: int                           # data rows read (at most SAMPLE_ROWS)
    limited: bool                       # the file holds more rows than were read
    columns: list[SourceColumn]
    data: Path | None = None            # after ``convert``
    converted_for: object = None        # the columns ``convert`` last ran for

    @property
    def sheets(self) -> list[str]:
        return [p.sheet for p in self.parts]


def stage_key(info: SampleInfo, source: SourceSettings) -> tuple:
    return (info.key(), tuple(sheets_to_read(info, source)), info.encoding, info.delimiter)


def stage(ctx: JobContext, folder: DataFolder, info: SampleInfo, source: SourceSettings,
          previous: StagedSample | None = None, *, workers: int | None = None,
          limit: int = smp.SAMPLE_ROWS) -> StagedSample:
    """Read up to ``limit`` rows of the chosen sheets (in order) into a new staging folder and profile the columns.
    The previous sample's staging folder is removed first; a cancelled or failed read removes the new one."""
    problem = sheets_problem(info, source)
    if problem:
        raise SampleProblem(problem)
    if (os.path.getsize(info.path), os.path.getmtime(info.path)) != (info.size, info.modified):
        raise SampleProblem(f"{info.file_name} has changed since it was picked. Pick it again.")
    if previous is not None:
        folder.discard_staging(previous.staging)
    staging = folder.new_staging()
    ctx.on_abort(lambda: folder.discard_staging(staging))
    names = sheets_to_read(info, source)
    ctx.set_stage("Reading the sample", rows_total=limit)
    parts: list[convert.RawPart] = []
    headers: list[list[str]] = []
    rows, limited = 0, False
    for i, name in enumerate(names):
        if rows >= limit:
            limited = True
            break
        sheet = info.sheet(name)
        raw = staging.raw / f"{i}.csv"
        task = (info.path, info.kind, name, sheet.header_row, len(sheet.headers), info.encoding, info.delimiter,
                str(raw), limit - rows)
        res = run_tasks(smp.read_part, [task], workers=workers, on_rows=ctx.add_rows,
                        should_stop=lambda: ctx.cancel_requested)[0]
        ctx.check_cancelled()
        if isinstance(res, TaskFailed):
            raise SampleProblem(res.message or f"{info.file_name} can't be read.")
        parts.append(convert.RawPart(0, name, raw, len(sheet.headers)))
        headers.append(sheet.headers)
        rows += res.rows
        limited = limited or res.limited
    columns = _source_columns(headers)
    ctx.set_stage("Checking column types")
    profiles = qs.profile(ctx.cursor(), parts, [[c.positions[i] for c in columns] for i in range(len(parts))],
                          len(columns))
    for c, p in zip(columns, profiles):
        c.profile = p
    return StagedSample(staging, stage_key(info, source), info.file_name, parts, rows, limited, columns)


def _source_columns(headers: list[list[str]]) -> list[SourceColumn]:
    """Headers in order of first appearance; the same header (MAP-2 normalised) in other sheets lines up."""
    out: list[SourceColumn] = []
    by_key: dict[str, SourceColumn] = {}
    for i, hs in enumerate(headers):
        for pos, h in enumerate(hs):
            k = norm(h)
            col = by_key.get(k)
            if col is None or col.positions[i] is not None:
                col = SourceColumn(h, [None] * len(headers))
                out.append(col)
                by_key.setdefault(k, col)
            col.positions[i] = pos
    return out


def discard(folder: DataFolder, staged: StagedSample | None) -> None:
    if staged is not None:
        folder.discard_staging(staged.staging)


# ---------------------------------------------------------------------------------------------- step 3 (detect)
def percent(part: int, whole: int) -> str:
    """"100%", "99.98%", "91%": never rounded up to 100% (C3-09 % note)."""
    if whole <= 0:
        return "0%"
    v = (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    text = f"{v:f}".rstrip("0").rstrip(".")
    return f"{text}%"


@dataclass
class Detected:
    type: str
    date_format: str | None
    note: str
    exact: bool                         # every value that isn't blank fits the type (else the note is amber)


def detect(p: qs.Profile) -> Detected:
    """The type a column's sample values suggest, with the % note (TPL-3, MAP-10)."""
    if p.filled == 0:
        return Detected(TEXT, None, "100% blank" if p.total else "No rows", True)
    whole = Decimal(p.filled)
    # the date format whose shapes cover most values; Excel dates (ISO) are read under every format
    best_fmt, best = None, p.iso_shaped
    for f in DATE_FORMATS:
        n = p.iso_shaped + p.shaped.get(f, 0)
        if n > best:
            best_fmt, best = f, n
    blank_share = Decimal(p.total - p.filled) / Decimal(p.total) if p.total else Decimal(0)
    if Decimal(best) / whole >= DETECT_SHARE and best >= p.numbers:
        typ, fmt, ok = DATE, best_fmt, p.dates.get(best_fmt, 0)
        note = f"{percent(ok, p.filled)} dates · {best_fmt or EXCEL_DATES}"
    elif Decimal(p.numbers) / whole >= DETECT_SHARE and p.leading_zero == 0:
        typ, fmt, ok = NUMBER, None, p.numbers
        note = f"{percent(ok, p.filled)} numbers"
    else:
        typ, fmt, ok = TEXT, None, p.filled
        note = "100% text"
    if typ in (NUMBER, DATE) and ok < p.filled:     # the rest is kept as text (Feature Spec A2 6.2, Tech spec 5.9)
        what = "numbers" if typ == NUMBER else "dates"
        note += f" · {percent(p.filled - ok, p.filled)} aren't {what} and are kept as text"
    if blank_share >= Decimal("0.5"):
        note = f"{percent(p.total - p.filled, p.total)} blank"
    return Detected(typ, fmt, note, ok == p.filled)


@dataclass
class DraftColumn:
    """A row of the Columns step: the source header, Include, and the template column it becomes."""
    source: int                         # index into StagedSample.columns
    header: str
    include: bool
    column: Column
    detected: Detected

    @property
    def id(self) -> str:
        return self.column.id


def draft_columns(staged: StagedSample) -> list[DraftColumn]:
    """Every header included, named as in the file, typed as detected, Number with 2 decimals (T13)."""
    out = []
    for i, sc in enumerate(staged.columns):
        det = detect(sc.profile)
        col = Column(f"c{i + 1:03d}", sc.header.strip() or f"Column {i + 1}", det.type,
                     DECIMALS_DEFAULT if det.type == NUMBER else None, det.date_format if det.type == DATE else None)
        out.append(DraftColumn(i, sc.header, True, col, det))
    return out


def included(drafts: list[DraftColumn]) -> list[Column]:
    return [d.column for d in drafts if d.include]


def columns_problem(drafts: list[DraftColumn]) -> str | None:
    cols = included(drafts)
    if not cols:
        return "Include at least one column."
    seen: set[str] = set()
    for c in cols:
        name = c.name.strip()
        if not name:
            return "Every included column needs a name."
        if name.casefold() in seen:
            return f"Two columns are named “{name}”. Use a different name for each."
        seen.add(name.casefold())
    return None


# ---------------------------------------------------------------------------------------------- step 4 (dry run)
def columns_signature(drafts: list[DraftColumn]) -> tuple:
    return tuple((d.source, d.column.id, d.column.type, d.column.decimals, d.column.date_format)
                 for d in drafts if d.include)


def convert_sample(ctx: JobContext, staged: StagedSample, drafts: list[DraftColumn]) -> None:
    """The sample's rows converted for the drafted columns (same code as a run's convert stage)."""
    sig = columns_signature(drafts)
    if staged.converted_for == sig and staged.data is not None:
        return
    ctx.set_stage("Converting the sample")
    cols = [d for d in drafts if d.include]
    parts = [convert.RawPart(p.file_index, p.sheet, p.raw_path, p.width,
                             {d.column.id: staged.columns[d.source].positions[i] for d in cols})
             for i, p in enumerate(staged.parts)]
    data = staged.staging.path / convert.DATA
    staged.data = staged.converted_for = None
    cur = ctx.cursor()
    columns = [d.column for d in cols]
    convert.write_data(cur, parts, columns, staged.staging.id, data)
    ctx.check_cancelled()
    staged.data, staged.converted_for = data, sig


@dataclass
class DryRun:
    counts: dict[str, int]              # rule ID -> failures on the sample
    first: dict[str, list[tuple]]       # rule ID -> first 20 failing issues (validate.ISSUE_COLUMNS)
    rows: int                           # sample rows


def dry_run(ctx: JobContext, staged: StagedSample, drafts: list[DraftColumn], rules: list[Rule]) -> DryRun:
    """VR-8: each rule's failure count on the sample and its first 20 failing rows. Nothing is written but the
    sample's converted rows."""
    from sankalan.validation import scan
    convert_sample(ctx, staged, drafts)
    counts, first = scan.dry_run(ctx, staged.data, included(drafts), rules, {0: staged.file_name})
    return DryRun(counts, first, staged.rows)


# ---------------------------------------------------------------------------------------------- step 5 (preview)
def preview(ctx: JobContext, staged: StagedSample, drafts: list[DraftColumn], definition) -> manage.Preview:
    """DO-8: a default output on the sample rows."""
    convert_sample(ctx, staged, drafts)
    return manage.output_preview(ctx, definition, included(drafts), staged.data)


# ---------------------------------------------------------------------------------------------- step 6 (save)
def _remap_definition(definition: dict, ids: dict[str, str]) -> dict:
    out = copy.deepcopy(definition)
    for key in ("filters", "groups", "measures"):
        for item in out.get(key) or []:
            if item.get("column_id") in ids:
                item["column_id"] = ids[item["column_id"]]
    return out


def build_template(client_id: str, name: str, source: SourceSettings, drafts: list[DraftColumn],
                   rules: list[Rule], outputs: list[DefaultOutput], export: dict | None = None) -> Template:
    """The template to save: included columns in the order shown, numbered c001… in that order (V3-2 stable IDs
    from here on), the rules with the automatic type rules (VR-7), the default outputs pointing at the new IDs."""
    cols = [copy.deepcopy(d.column) for d in drafts if d.include]
    ids = {c.id: f"c{i + 1:03d}" for i, c in enumerate(cols)}
    for c in cols:
        c.id = ids[c.id]
        c.name = c.name.strip()
    out_rules = []
    for r in rules:
        if r.column_id not in ids:
            continue
        r = Rule.from_dict(r.to_dict())
        r.column_id = ids[r.column_id]
        if r.type == UNIQUE and r.settings.get("columns"):
            keys = [ids[k] for k in r.settings["columns"] if k in ids]
            r.settings = {"columns": keys} if len(keys) > 1 else {}
        out_rules.append(r)
    t = Template("", client_id, name.strip(), copy.deepcopy(source), cols, with_type_rules(cols, out_rules),
                 [DefaultOutput(o.name.strip(), _remap_definition(o.definition, ids)) for o in outputs],
                 dict(export or {}))
    return t


def save(ctx: JobContext, t: Template) -> str:
    """Create the template (version 1). The name is checked again (C3-05); nothing is written under ``t\\``."""
    con = ctx.cursor()
    ctx.set_stage("Saving template")
    t.name = manage.check_name(t.name, q.template_names(con, t.client_id), what="template")
    t.id = q.new_id()
    for o in t.outputs:
        o.definition["template_id"] = t.id
    return q.create_template(con, t)
