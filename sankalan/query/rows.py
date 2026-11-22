r"""Rows view queries (Feature Spec A2 ROW-6 to ROW-14, 8.7; Tech spec A2 T32, T48, 10.2–10.4).

Every read is of the ticked runs' ``data.parquet``; left-out rows are in their own file, so they are never read
(ROW-13). Filters compile through the compiler's ``filter_sql``, exactly as for Analysis (ROW-6, with Tech spec A2
5.6's companion rules). A column added after a run reads as a typed null for that run's rows (ROW-14); removed
columns are never selected.

* ``count_rows``: matches per run, one scan over the ticked runs (no scan at all with no filters: rows loaded).
* ``fetch_rows``: the first ``cap`` matches into a temporary table ``_rows_<uuid>`` with ``_seq``, run by run in Run
  ID order, each one ``ORDER BY _src_file, _src_row LIMIT <rows still needed>`` (T32, T48). The table holds every
  column and companion, so ticking, unticking or moving columns never reads the runs again (ROW-9).
* ``rows_page``: a ``_seq`` range of the table, for the grid's pages of 200.
* ``export_source``: every match in stored order, one chunk per run with matches (10.4).
"""
from __future__ import annotations

from pathlib import Path

from sankalan.model import definition as d
from sankalan.model.rowspec import RowSpec, RunRef
from sankalan.model.template import Column, active
from sankalan.query.compiler import filter_sql, present_columns, source_sql
from sankalan.query.convert import _path, companion, has_companion, lit, sql_type
from sankalan.query.export import SOURCE_COLUMNS, STORED_ORDER, Chunk, ExportSource, _file_name, _text

ROWS_CAP = 100_000          # ROW-11: the grid holds the first 100,000 matches; tests lower it
SOURCE = ("run_id", "_src_file", "_src_sheet", "_src_row")
SOURCE_TYPES = ("VARCHAR", "INTEGER", "VARCHAR", "BIGINT")


def table_columns(columns: list[Column]) -> list[str]:
    """The Rows table's columns after ``_seq``: each active column (its companion after a Number or Date column),
    then the source columns. ``rows_page`` returns them in this order."""
    out = []
    for c in active(columns):
        out.append(c.id)
        if has_companion(c):
            out.append(companion(c.id))
    return out + list(SOURCE)


def _check(spec: RowSpec, columns: list[Column]) -> dict[str, Column]:
    by_id = {c.id: c for c in active(columns)}
    for f in spec.filters:
        if f.column_id not in by_id:
            raise d.DefinitionError(f"unknown column {f.column_id!r}")
    # Analysis's filter checks; the Rows count card only satisfies "a group level or a measure", which a row view
    # doesn't have
    defn = spec.as_definition()
    defn.measures = [d.MeasureCard(d.ROWS, [d.Op(d.COUNT)])]
    d.check(defn, columns)
    return by_id


def _items(cols: list[Column], present: set[str]) -> list[str]:
    """Each column (and companion) as itself, or a typed null when the file doesn't have it (ROW-14)."""
    out = []
    for c in cols:
        out.append(f"{c.id if c.id in present else f'CAST(NULL AS {sql_type(c)})'} AS {c.id}")
        if has_companion(c):
            t = companion(c.id)
            out.append(f"{t if t in present else 'CAST(NULL AS VARCHAR)'} AS {t}")
    return out


def _where(spec: RowSpec, by_id: dict[str, Column]) -> str:
    conds = [filter_sql(f, by_id[f.column_id]) for f in spec.filters]
    return ("WHERE " + " AND ".join(conds)) if conds else ""


def _filtered(con, spec: RowSpec, by_id: dict[str, Column], cols: list[Column], path: Path) -> str:
    """One run's rows that match, with ``cols`` (and the filter columns) and the source columns, unordered."""
    present = present_columns(con, [path])
    need = list(cols) + [by_id[f.column_id] for f in spec.filters if by_id[f.column_id] not in cols]
    inner = ", ".join(_items(need, present) + list(SOURCE))
    return f"SELECT * FROM (SELECT {inner} FROM read_parquet({_path(path)})) {_where(spec, by_id)}"


# ---------------------------------------------------------------------------------------------- count (ROW-10)
def count_rows(con, spec: RowSpec, columns: list[Column], runs: list[RunRef]) -> dict[str, int]:
    """Matches per run ID. With no filters every loaded row matches, so the catalogue's rows loaded are used and
    nothing is scanned. The match count is the sum; rows searched is the sum of ``rows_loaded`` (ROW-10)."""
    by_id = _check(spec, columns)
    if not spec.filters:
        return {r.id: int(r.rows_loaded) for r in runs}
    if not runs:
        return {}
    paths = [r.data_path for r in runs]
    present = present_columns(con, paths)
    need = []
    for f in spec.filters:
        if by_id[f.column_id] not in need:
            need.append(by_id[f.column_id])
    inner = ", ".join(_items(need, present) + ["run_id"])
    got = dict(con.execute(f"SELECT run_id, count(*) FROM (SELECT {inner} FROM {source_sql(paths)}) "
                           f"{_where(spec, by_id)} GROUP BY run_id").fetchall())
    return {r.id: int(got.get(r.id, 0)) for r in runs}


# ---------------------------------------------------------------------------------------------- fetch (ROW-11, T48)
def create_table(con, columns: list[Column], table: str) -> None:
    defs = ["_seq BIGINT"]
    for c in active(columns):
        defs.append(f"{c.id} {sql_type(c)}")
        if has_companion(c):
            defs.append(f"{companion(c.id)} VARCHAR")
    defs += [f"{n} {t}" for n, t in zip(SOURCE, SOURCE_TYPES)]
    con.execute(f"CREATE TEMP TABLE {table} ({', '.join(defs)})")


def fetch_rows(con, spec: RowSpec, columns: list[Column], runs: list[RunRef], counts: dict[str, int], table: str,
               *, cap: int = ROWS_CAP, between=None) -> int:
    """Create ``table`` and fill it with the first ``cap`` matches in stored order; returns the rows held. Runs are
    read in Run ID order and only until the table is full, so later runs are usually never read. ``between()`` is
    called before each run (the Job's cancel check)."""
    by_id = _check(spec, columns)
    cols = active(columns)
    create_table(con, columns, table)
    names = table_columns(columns)
    held = 0
    for r in sorted(runs, key=lambda x: x.number):
        if held >= cap:
            break
        if not counts.get(r.id):
            continue
        if between is not None:
            between()
        want = cap - held
        src = _filtered(con, spec, by_id, cols, r.data_path)
        row = con.execute(f"INSERT INTO {table} (_seq, {', '.join(names)}) "
                          f"SELECT {held} + row_number() OVER (ORDER BY _src_file, _src_row), {', '.join(names)} "
                          f"FROM ({src} {STORED_ORDER} LIMIT {int(want)})").fetchone()
        held += int(row[0]) if row else 0
    return held


def rows_page(con, table: str, columns: list[Column], first: int, count: int) -> list[tuple]:
    """Rows ``first + 1`` … ``first + count`` of the table in ``_seq`` order, as ``table_columns`` lists them."""
    names = ", ".join(table_columns(columns))
    return [tuple(r) for r in con.execute(
        f"SELECT {names} FROM {table} WHERE _seq > {int(first)} AND _seq <= {int(first) + int(count)} "
        f"ORDER BY _seq").fetchall()]


def drop_table(con, table: str | None) -> None:
    if table:
        con.execute(f"DROP TABLE IF EXISTS {table}")


# ---------------------------------------------------------------------------------------------- export (ROW-8, ROW-12)
def export_headers(spec: RowSpec, columns: list[Column]) -> list[str]:
    """The ticked columns' names in order, then Source File, Source Sheet, Source Row, Run ID (ROW-8)."""
    by_id = {c.id: c for c in active(columns)}
    return [by_id[cid].name for cid in spec.columns] + list(SOURCE_COLUMNS)


def export_source(con, spec: RowSpec, columns: list[Column], runs: list[RunRef], counts: dict[str, int]
                  ) -> ExportSource:
    """Every match in stored order (ROW-12): one chunk per run with matches, in Run ID order, each over that run's
    file alone and ordered by ``_src_file, _src_row`` (T32). Values as the export writes them (Tech spec A2 5.3:
    text in a Number or Date column as typed); Source Sheet blank for CSV files. Chunk rows come from
    ``count_rows``, so the size estimate needs no count of its own."""
    by_id = _check(spec, columns)
    if not spec.columns:
        raise d.DefinitionError("Tick at least one column")
    ticked = [by_id[cid] for cid in spec.columns]
    chunks = []
    for r in sorted(runs, key=lambda x: x.number):
        n = int(counts.get(r.id, 0))
        if not n:
            continue
        src = _filtered(con, spec, by_id, ticked, r.data_path)
        present = set(table_columns(columns))                 # every column is in the inner SELECT
        exprs = [_text(c, present) for c in ticked]
        exprs += [_file_name(r.file_names), "nullif(_src_sheet, '')", "_src_row", lit(r.label)]
        chunks.append(Chunk(f"SELECT {', '.join(exprs)} FROM ({src})", n, STORED_ORDER))
    return ExportSource(export_headers(spec, columns), chunks, sum(c.rows for c in chunks))
