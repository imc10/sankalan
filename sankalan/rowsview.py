"""The Rows view as Job work (Feature Spec A2 2, ROW-1 to ROW-14; Tech spec A2 T48, 10).

No SQL here: ``sankalan.query.rows`` does the reading. The screen starts these through the window's Job bridge.

* ``run``: one Job, "Rows view", with the stages "Counting rows" and "Fetching the first 100,000". The new temporary
  table is dropped if the Job is cancelled or fails, so the previous result stays (2.4 Cancelled); the previous
  table is dropped only once the new one is full, as for analysis results.
* ``RowsSource``: a ``PageSource`` over the table. Its rows hold every column's display text (formats.cell_text) and
  the four source cells, so the screen picks and orders columns without reading again (ROW-9, PERF-10).
* ``export_items``: every match in stored order for the Export rows dialog (7.9), sized from the Run's counts.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace

from sankalan import formats
from sankalan.db.datafolder import DataFolder
from sankalan.jobs import JobContext
from sankalan.model.definition import DefinitionError
from sankalan.model.rowspec import RowSpec, RunRef
from sankalan.model.run import run_label
from sankalan.model.template import Column, Template, active
from sankalan.query import catalogue as q
from sankalan.query import convert
from sankalan.query import rows as qr
from sankalan.query.export import SOURCE_COLUMNS

STAGE_COUNT = "Counting rows"
OPERATION = "Rows view"
HEADER_NOTE = "Row views aren't saved"
NO_RUNS = "Tick at least one run"
NO_COLUMNS = "Tick at least one column"
NO_MATCH = "No rows match these filters."
CANCELLED = "Cancelled: Run again"
EMPTY = "Pick runs and filters, then press Run"
ORDER_LINE = "Rows in the order they were loaded: by Run ID, then file, sheet and row"
DROP_TRIES = 5

# Test hook: called with the Job context before each run's fetch (to hold a Job in the fetch stage).
_before_fetch = None


def fetch_stage(cap: int) -> str:
    return f"Fetching the first {formats.number(cap)}"


def run_refs(con, folder: DataFolder, template_id: str, run_ids: list[str]) -> list[RunRef]:
    """The ticked runs in Run ID order, with their data file, rows loaded and file names (Tech spec A2 10.1)."""
    return [RunRef(rid, number, run_label(number), folder.run_dir(template_id, rid) / convert.DATA, loaded, names)
            for rid, number, loaded, names in q.rows_view_runs(con, template_id, run_ids)]


@dataclass
class RowsOutcome:
    """A Rows result: the temporary table (``table``, dropped by ``layer.drop`` / ``window.drop_results`` like an
    analysis result), the counts per run and the figures for the header line."""
    table: str | None
    spec: RowSpec
    runs: list[RunRef]
    counts: dict[str, int]
    held: int
    seconds: float
    columns: list[Column]                      # the template's columns at Run
    cap: int = qr.ROWS_CAP

    @property
    def match(self) -> int:
        return sum(self.counts.values())

    @property
    def searched(self) -> int:
        """Rows searched: the rows loaded in the ticked runs (ROW-10)."""
        return sum(r.rows_loaded for r in self.runs)

    @property
    def capped(self) -> bool:
        return self.match > self.held

    def summary(self) -> str:
        """"2,341,118 rows match · 3 runs · 7,499,937 rows searched · 0.9 s" (ROW-10)."""
        n = self.match
        return " · ".join([f"{formats.number(n)} {'row matches' if n == 1 else 'rows match'}",
                           formats.count(len(self.runs), "run"), f"{formats.number(self.searched)} rows searched",
                           f"{self.seconds:.1f} s"])

    def footer(self) -> str:
        """ROW-11: "Showing all N rows", or the first 100,000 of N in load order."""
        if not self.capped:
            return f"Showing all {formats.count(self.match, 'row')}"
        return (f"Showing the first {formats.number(self.held)} of {formats.count(self.match, 'row')}, in the order "
                "they were loaded. Export gets all of them.")


def _drop(cur, table: str) -> None:
    """Drop a table even while a cancel is still interrupting the connection (each interrupt stops one query)."""
    for _ in range(DROP_TRIES):
        try:
            qr.drop_table(cur, table)
            return
        except Exception:               # an interrupt that landed on the DROP: try again
            time.sleep(0.02)


def run(ctx: JobContext, folder: DataFolder, template: Template, spec: RowSpec, run_ids: list[str],
        drop: list | None = None, cap: int | None = None) -> RowsOutcome:
    """Count, then fetch the first ``cap`` matches (ROW-10, ROW-11). Results in ``drop`` (the previous one, those of
    screens that were left) are dropped once the new table is full, so a Cancel keeps the previous result."""
    start = time.monotonic()
    cap = qr.ROWS_CAP if cap is None else cap
    if not run_ids:
        raise DefinitionError(NO_RUNS)
    if not spec.columns:
        raise DefinitionError(NO_COLUMNS)
    cur = ctx.cursor()
    runs = run_refs(cur, folder, template.id, run_ids)
    ctx.set_stage(STAGE_COUNT)
    counts = qr.count_rows(cur, spec, template.columns, runs)
    ctx.check_cancelled()
    ctx.set_stage(fetch_stage(cap))
    table = "_rows_" + uuid.uuid4().hex
    ctx.on_abort(lambda: _drop(cur, table))

    def between():
        if _before_fetch is not None:
            _before_fetch(ctx)
        ctx.check_cancelled()
    held = qr.fetch_rows(cur, spec, template.columns, runs, counts, table, cap=cap, between=between)
    ctx.check_cancelled()
    from sankalan.query import layer
    for old in drop or []:
        layer.drop(cur, old)
    snapshot = replace(spec, filters=list(spec.filters), columns=list(spec.columns))
    return RowsOutcome(table, snapshot, runs, counts, held, time.monotonic() - start, list(template.columns), cap)


# ---------------------------------------------------------------------------------------------- the grid
def display_columns(columns: list[Column]) -> list[tuple[str, str]]:
    """(key, header) of every cell a ``RowsSource`` row holds: each active column, then the four source columns."""
    keys = ["_file", "_sheet", "_row", "_run"]
    return [(c.id, c.name) for c in active(columns)] + list(zip(keys, SOURCE_COLUMNS))


def display_row(raw: tuple, columns: list[Column], runs: dict[str, RunRef]) -> tuple:
    """One table row (``rows.table_columns`` order) → its cells as shown: numbers with grouping at the column's
    decimals, dates DD-MM-YYYY, text kept in a Number or Date column as typed (TXT-2); blank values empty; the
    file name, the sheet (blank for CSV), the row and the Run ID."""
    out = []
    i = 0
    for c in active(columns):
        if convert.has_companion(c):
            out.append(formats.cell_text(c, raw[i], raw[i + 1]))
            i += 2
        else:
            out.append("" if raw[i] is None else str(raw[i]))
            i += 1
    run_id, src_file, sheet, row = raw[i:i + 4]
    ref = runs.get(run_id)
    out.append(ref.file_names.get(int(src_file), f"file {src_file}") if ref is not None else "")
    out.append(sheet or "")
    out.append(formats.number(int(row)) if row is not None else "")
    out.append(ref.label if ref is not None else "")
    return tuple(out)


@dataclass
class RowsSource:
    """A ``PageSource`` over a Rows result's table: the rows held (the first 100,000), never sorted (D71)."""
    outcome: RowsOutcome

    def count(self, ctx, sort) -> int:
        return self.outcome.held if self.outcome.table else 0

    def page(self, ctx, offset: int, limit: int, sort) -> list[tuple]:
        o = self.outcome
        if not o.table:
            return []
        runs = {r.id: r for r in o.runs}
        return [display_row(r, o.columns, runs) for r in qr.rows_page(ctx.cursor(), o.table, o.columns, offset,
                                                                       limit)]


# ---------------------------------------------------------------------------------------------- export (7.9)
def export_items(outcome: RowsOutcome, columns: list[str]):
    """Job work for the Export dialog: every match in stored order with the ``columns`` ticked now (they can change
    after Run without running again, ROW-9), then the source columns (ROW-8)."""
    spec = replace(outcome.spec, columns=list(columns))

    def items(ctx):
        return [(qr.export_source(ctx.cursor(), spec, outcome.columns, outcome.runs, outcome.counts), "")]
    return items


def columns_line(n: int) -> str:
    return (f"Columns: the {formats.count(n, 'ticked column')}, in their order, then Source File, Source Sheet, "
            "Source Row and Run ID")


def describe(outcome: RowsOutcome, columns: list[str]) -> list[str]:
    """The Export rows box (7.9): the filters in words, the columns line, the row-order line."""
    from sankalan import analyses
    filters = analyses.describe(outcome.spec.as_definition(), outcome.columns)["Filters"]
    head = ["Filters: none"] if filters == ["None"] else ["Filters: " + "; ".join(filters)]
    return head + [columns_line(len(columns)), ORDER_LINE]


def context(outcome: RowsOutcome, client: str, template: str) -> list[str]:
    """The Export rows summary's leading items: Client · Template · runs · filters (7.9)."""
    return [client, template, formats.count(len(outcome.runs), "run"),
            formats.count(len(outcome.spec.filters), "filter")]


def check_columns(columns: list[str]) -> None:
    if not columns:
        raise DefinitionError(NO_COLUMNS)

