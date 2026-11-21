"""Saved and ad-hoc analyses as Job work for the Analysis area (6.1–6.3, dialogs 7.7, 7.8; UX-10, ANA-1 to ANA-9, D33).

No SQL here: the catalogue and the query layer do the reading. The screens start these through the window's Job
bridge and get plain Python objects back.

* Saved analyses keep the definition only (runs are never stored, D33). Names are required and unique within the
  template, ignoring case and leading or trailing spaces (the C1-04 / C2-05 rule, confirmed 17-11-2026).
* An analysis reads only the ticked runs' ``data.parquet`` (left-out rows are in their own file, so never part of
  one). The result goes into a temporary table, read a page at a time (first 100,000 rows) and exported in full.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from pathlib import Path

from sankalan import analysis, formats
from sankalan.db.datafolder import DataFolder
from sankalan.jobs import JobContext
from sankalan.manage import NameRefused, check_name
from sankalan.model import definition as d
from sankalan.model.definition import Definition, DefinitionError
from sankalan.model.run import run_label
from sankalan.model.template import DATE, Column, Template
from sankalan.query import catalogue as q
from sankalan.query import convert, layer

ROW_CAP = layer.ROW_CAP            # ANA-7: the first 100,000 rows on screen
DISTINCT_TOP = layer.DISTINCT_TOP  # ANA-4: the 1,000 most frequent values
NEW_NAME = "New analysis"
NO_RUNS = "Tick at least one run."
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")
FILTER_WORDS = {d.BLANK: "is blank", d.NOT_BLANK: "is not blank", d.NOT_NUMBER: "is not a number",
                d.NOT_DATE: "is not a date"}
GRAIN_WORDS = {"day": "Day", "month": "Month", "quarter": "Quarter", "year": "Year"}


# ---------------------------------------------------------------------------------------------- 6.1 list
@dataclass(frozen=True)
class AnalysisRow:
    id: str
    name: str
    client_id: str
    client: str
    template_id: str
    template: str
    saved_on: dt.datetime


def list_analyses(ctx: JobContext) -> list[AnalysisRow]:
    return [AnalysisRow(*r) for r in q.saved_analysis_rows(ctx.cursor())]


def matches(row: AnalysisRow, text: str) -> bool:
    """A0-01: search matches the name, the client and the template, ignoring case."""
    t = text.strip().casefold()
    return not t or any(t in x.casefold() for x in (row.name, row.client, row.template))


# ---------------------------------------------------------------------------------------------- data selection (ANA-3)
@dataclass(frozen=True)
class RunChoice:
    id: str
    label: str                      # R-0001
    files: tuple[str, ...]          # file names in file order

    @property
    def text(self) -> str:
        return ", ".join(self.files)


@dataclass
class TemplateData:
    template: Template
    client_id: str
    client_name: str
    runs: list[RunChoice] = field(default_factory=list)       # newest first

    @property
    def columns(self) -> list[Column]:
        return self.template.columns


def template_choices(ctx: JobContext) -> list[tuple]:
    """(client id, client name, template id, template name) for the Client and Template lists."""
    return q.template_choices(ctx.cursor())


def template_data(ctx: JobContext, template_id: str) -> TemplateData:
    con = ctx.cursor()
    head = q.template_header(con, template_id)
    if head is None:
        raise KeyError(template_id)
    t = q.load_template(con, template_id)
    runs = [RunChoice(r[0], run_label(r[1]), tuple(r[3])) for r in q.run_rows(con, template_id) if not r[9]]
    return TemplateData(t, head[0], head[1], runs)


# ---------------------------------------------------------------------------------------------- saved analyses (ANA-1)
@dataclass
class Saved:
    id: str
    name: str
    saved_on: dt.datetime
    definition: Definition
    data: TemplateData


def open_saved(ctx: JobContext, analysis_id: str) -> Saved:
    row = q.saved_analysis(ctx.cursor(), analysis_id)
    if row is None:
        raise KeyError(analysis_id)
    aid, tid, name, definition, saved_on = row
    defn = Definition.from_dict(definition)
    defn.template_id = tid
    return Saved(aid, name, saved_on, defn, template_data(ctx, tid))


def check_analysis_name(name: str, taken: dict[str, str], exclude: str | None = None) -> str:
    if not (name or "").strip():
        raise NameRefused("Enter a name for the analysis.")
    return check_name(name, taken, what="analysis", exclude=exclude)


def save(ctx: JobContext, template: Template, name: str, definition: Definition) -> str:
    """7.8 Save: the definition (no runs) under a name unique within the template."""
    con = ctx.cursor()
    clean = check_analysis_name(name, q.saved_analysis_names(con, template.id))
    defn = Definition.from_dict(definition.to_dict())
    defn.template_id = template.id
    d.check(defn, template.columns)
    return q.insert_saved_analysis(con, template.id, clean, defn.to_dict())


def rename(ctx: JobContext, analysis_id: str, name: str) -> str:
    """A0-04: refused when another analysis of the same template has the name."""
    con = ctx.cursor()
    row = q.saved_analysis(con, analysis_id)
    if row is None:
        raise KeyError(analysis_id)
    clean = check_analysis_name(name, q.saved_analysis_names(con, row[1]), exclude=analysis_id)
    q.rename_saved_analysis(con, analysis_id, clean)
    return clean


def delete(ctx: JobContext, analysis_id: str) -> None:
    q.delete_saved_analysis(ctx.cursor(), analysis_id)


# ---------------------------------------------------------------------------------------------- run (ANA-7, ANA-8)
@dataclass
class Outcome:
    """A result on screen: the temporary table, its figures for the summary line, and the pinned grand total."""
    result: layer.Result
    definition: Definition
    runs: int
    input_rows: int
    count: int                      # rows the result has (detail, plus subtotals when shown)
    total: tuple | None
    seconds: float
    subtotals: bool

    @property
    def capped(self) -> bool:
        return self.count > ROW_CAP

    @property
    def kinds(self) -> list[tuple]:
        return [(c.type, c.decimals, c.grain) for c in self.result.columns]

    @property
    def headers(self) -> list[str]:
        return [c.label for c in self.result.columns]

    def summary(self) -> str:
        """"3 runs · 28,796,813 rows · 15 result rows · 1.4 s" (6.2)."""
        return " · ".join([formats.count(self.runs, "run"), formats.count(self.input_rows, "row"),
                           formats.count(self.count, "result row"), f"{self.seconds:.1f} s"])


def sources(folder: DataFolder, template_id: str, run_ids: list[str]) -> list[Path]:
    if not run_ids:
        raise DefinitionError(NO_RUNS)
    return [folder.run_dir(template_id, rid) / convert.DATA for rid in run_ids]


def run(ctx: JobContext, folder: DataFolder, definition: Definition, template: Template, run_ids: list[str],
        drop: list[layer.Result] | None = None) -> Outcome:
    """Run the analysis over the ticked runs. Results in ``drop`` (the previous one, results of screens that were
    left) are dropped once the new table exists, so a Cancel keeps the previous result."""
    start = time.monotonic()
    d.check(definition, template.columns)
    src = sources(folder, template.id, run_ids)
    res = analysis.run_analysis(ctx, definition, template.columns, src)
    cur = ctx.cursor()
    for old in drop or []:
        layer.drop(cur, old)
    sub = definition.subtotals
    n = layer.count_rows(cur, res, sub)
    total = layer.grand_total(cur, res)
    return Outcome(res, definition, len(run_ids), res.input_rows, n, total, time.monotonic() - start, sub)


def distinct_values(ctx: JobContext, folder: DataFolder, template: Template, column_id: str, run_ids: list[str],
                    search: str | None = None) -> list[tuple[str, int]]:
    """The Is one of picker (ANA-4): top values with counts over the ticked runs, or a search of the whole column."""
    column = next(c for c in template.columns if c.id == column_id)
    return analysis.distinct_values(ctx, column, sources(folder, template.id, run_ids), search)


def export_items(outcome: Outcome, sort: str | None, descending: bool):
    """Job work for the Export dialog (ANA-9): the full result as shown (subtotals, sort), grand total last."""
    from sankalan.query import export as qx

    def items(_ctx):
        return [(qx.result(outcome.result, subtotals=outcome.subtotals, sort=sort, descending=descending), "")]
    return items


def drop_results(ctx: JobContext, results: list[layer.Result]) -> None:
    cur = ctx.cursor()
    for r in results:
        layer.drop(cur, r)


@dataclass
class ResultSource:
    """A ``PageSource`` over a result: the first 100,000 rows (ANA-7), sorted by a header (within each parent group
    with subtotals on, T23). Rows: the cells as shown, then ``_depth``."""
    outcome: Outcome

    def count(self, ctx, sort) -> int:
        return min(self.outcome.count, ROW_CAP)

    def page(self, ctx, offset: int, limit: int, sort) -> list[tuple]:
        key, asc = (sort[0] if sort else (None, True))
        o = self.outcome
        rows = layer.rows(ctx.cursor(), o.result, subtotals=o.subtotals, offset=offset, limit=limit, sort=key,
                          descending=not asc, cap=ROW_CAP)
        return [display_row(row, o.kinds, o.result.levels) for row in rows]


def display_row(row: tuple, kinds: list[tuple], groups: int) -> tuple:
    """(_depth, values…) → (cells…, _depth). A subtotal row says "Total" in its first rolled-up group cell."""
    depth, values = row[0], row[1:]
    out = []
    for c, v in enumerate(values):
        group = c < groups
        text = formats.result_cell(v, kinds[c], group)
        if group and depth < groups and c >= depth:
            text = d.SUBTOTAL_LABEL if c == depth else ""
        out.append(text)
    return tuple(out) + (depth,)


def total_cells(outcome: Outcome) -> list[str]:
    """The pinned grand total row: "Grand total" in the first group cell, then the measures."""
    groups = outcome.result.levels
    kinds = outcome.kinds
    cells = [d.TOTAL_LABEL if i == 0 else "" for i in range(groups)]
    t = outcome.total
    for i in range(len(outcome.result.measures)):
        cells.append("" if t is None else formats.result_cell(t[i], kinds[groups + i], False))
    return cells


# ---------------------------------------------------------------------------------------------- locked settings (6.3)
def describe_filter(f, columns: dict[str, Column]) -> str:
    col = columns.get(f.column_id)
    name = d.column_label(col) if col is not None else f.column_id
    v = f.values
    if f.op == d.ONE_OF:
        return f"{name} is one of {', '.join(str(x) for x in v)}"
    if f.op == d.CONTAINS:
        return f"{name} contains {v[0]}"
    if f.op == d.EQUALS:
        return f"{name} equals {v[0]}"
    if f.op == d.YEAR:
        return f"{name} year is {v[0]}"
    if f.op == d.QUARTER:
        return f"{name} quarter is Q{v[1]} {v[0]}"
    if f.op == d.MONTH:
        return f"{name} month is {MONTH_NAMES[int(v[1]) - 1]} {v[0]}"
    if f.op == d.BETWEEN:
        a, b = (list(v) + [None, None])[:2]
        if col is not None and col.type == DATE:
            a, b = (formats.date(dt.date.fromisoformat(x)) if x else None for x in (a, b))
        if a and b:
            return f"{name} is between {a} and {b}"
        return f"{name} is {'from ' + str(a) if a else 'up to ' + str(b)}"
    return f"{name} {FILTER_WORDS.get(f.op, f.op)}"


def describe(definition: Definition, columns: list[Column]) -> dict[str, list[str]]:
    """6.3 locked settings: Filters, Group by, Measures, Subtotals as lines."""
    by_id = {c.id: c for c in columns}
    filters = [describe_filter(f, by_id) for f in definition.filters] or ["None"]
    groups = []
    for i, g in enumerate(definition.groups, 1):
        col = by_id.get(g.column_id)
        name = d.column_label(col) if col is not None else g.column_id
        if col is not None and col.type == DATE:
            name += f" by {GRAIN_WORDS[g.grain or 'day']}"
        groups.append(f"{i}. {name}")
    measures = []
    for m in definition.measures:
        default = d.measure_label(d.Measure(m.column_id, m.fn, None), by_id)
        measures.append(f"{default} as {m.label}" if m.label else default)
    return {"Filters": filters, "Group by": groups or ["None"], "Measures": measures,
            "Subtotals": ["On" if definition.subtotals else "Off"]}
