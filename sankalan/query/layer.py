"""The query layer (Tech spec, Query layer; V3-1, V3-4, ANA-4, ANA-7, ANA-8, DO-2, DO-6, T23).

Every read of committed data goes through here; screens never write SQL. All functions take the app connection
(``ctx.cursor()`` inside a Job).

- ``run_definition``: the result of an analysis into a temporary table (it can spill to disk), fetched in pages.
- ``write_output`` / ``open_output``: a default output's result stored as ``outputs\\<n>.parquet`` (DO-6) and read
  back for viewing and export, never recalculated.
- ``distinct_values``: the "Is one of" picker (ANA-4).
- ``select_only``: exactly one SELECT statement (V3-4).

A ``Result`` is read through ``rows(...)`` (detail rows, plus subtotals when shown; never the grand total, which is
pinned and read by ``grand_total``), in ``ROW_CAP``-row windows.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from sankalan.model import definition as d
from sankalan.model.definition import Definition
from sankalan.model.template import Column
from sankalan.query.compiler import (Compiled, OutColumn, column_expr, compile_definition, out_columns,
                                    present_columns, source_sql)
from sankalan.query.convert import _path, lit

ROW_CAP = 100_000           # ANA-7: the grid shows the first 100,000 rows
DISTINCT_TOP = 1_000        # ANA-4


@dataclass
class Result:
    relation: str                   # a temporary table name, or read_parquet(...) of a stored output
    columns: list[OutColumn]
    levels: int
    note: str | None = None
    input_rows: int = 0             # rows in the chosen runs ("3 runs · 28,796,813 rows")
    table: str | None = None        # the temporary table, dropped by ``drop``
    extra: dict = field(default_factory=dict)

    @property
    def groups(self) -> list[OutColumn]:
        return [c for c in self.columns if c.role == "group"]

    @property
    def measures(self) -> list[OutColumn]:
        return [c for c in self.columns if c.role == "measure"]


def _result_from(compiled: Compiled, relation: str, table: str | None, input_rows: int) -> Result:
    return Result(relation, compiled.columns, compiled.levels, compiled.note, input_rows, table)


def run_definition(con, definition: Definition, columns: list[Column], sources: list[Path], *,
                   output: bool = False) -> Result:
    """Run an analysis (or a default-output preview with ``output=True``) over ``sources`` (the ticked runs'
    ``data.parquet``) into a temporary table."""
    compiled = compile_definition(con, definition, columns, sources, output=output)
    table = "_result_" + uuid.uuid4().hex
    con.execute(f"CREATE TEMP TABLE {table} AS {compiled.sql}")
    rows = int(con.execute(f"SELECT count(*) FROM {source_sql(sources)}").fetchone()[0])
    return _result_from(compiled, table, table, rows)


def drop(con, result: Result) -> None:
    if result.table is not None:
        con.execute(f"DROP TABLE IF EXISTS {result.table}")
        result.table = None


def write_output(con, definition: Definition, columns: list[Column], data: Path, out: Path) -> Result:
    """A default output on one run's rows (DO-2), stored as Parquet (DO-6). Left-out rows are in their own file,
    so they never reach it."""
    compiled = compile_definition(con, definition, columns, [data], output=True)
    con.execute(f"COPY ({compiled.sql}) TO {_path(out)} (FORMAT parquet)")
    return _result_from(compiled, f"read_parquet({_path(out)})", None, 0)


def open_output(definition: Definition, columns: list[Column], stored: Path, con=None) -> Result:
    """A stored output, labelled from the definition used for that run (``run_output``) and today's column names.
    The note is recovered without recalculating: a relative date filter with an empty result means no dates."""
    out = out_columns(definition, {c.id: c for c in columns})
    rel = f"read_parquet({_path(stored)})"
    note = None
    if con is not None and definition.has_relative_filter:
        if int(con.execute(f"SELECT count(*) FROM {rel}").fetchone()[0]) == 0:
            note = d.NO_DATES_NOTE
    return Result(rel, out, len(definition.groups), note)


# ---------------------------------------------------------------------------------------------- reading a result
def visible_where(result: Result, subtotals: bool) -> str:
    """Detail rows, plus subtotal rows when shown. The grand total is read on its own."""
    n = result.levels
    if n == 0:
        return "WHERE false"
    if subtotals:
        return "WHERE _depth >= 1"
    return f"WHERE _depth = {n}"


def order_by(result: Result, subtotals: bool, sort: str | None = None, descending: bool = False) -> str:
    """Default: group values ascending, "(Null)" last, a subtotal after its rows. With subtotals on, a sort keeps
    rows within their parent group and subtotals with their group (T23); with them off, it sorts the whole list."""
    n = result.levels
    names = {c.name for c in result.columns}
    if sort is not None and sort not in names:
        raise ValueError(f"unknown result column {sort!r}")
    direction = "DESC" if descending else "ASC"
    if n == 0:
        return ""
    if not subtotals or n == 1:
        keys = ([f"{sort} {direction} NULLS LAST"] if sort is not None else []) + [
            f"g{i} ASC NULLS LAST" for i in range(1, n + 1)]
        return "ORDER BY " + ", ".join(keys)
    keys = []
    for i in range(1, n + 1):
        part = ", ".join(f"g{k}" for k in range(1, i + 1))
        keys.append(f"(_depth < {i})")                       # a level-(i-1) subtotal after its children
        if sort is not None and sort.startswith("m"):
            # the measure of this row's level-i ancestor (its subtotal row, or itself for a detail row)
            keys.append(f"max(CASE WHEN _depth = {i} THEN {sort} END) OVER "
                        f"(PARTITION BY {part}, (_depth >= {i})) {direction} NULLS LAST")
        g_dir = direction if sort == f"g{i}" else "ASC"
        keys.append(f"g{i} {g_dir} NULLS LAST")
    return "ORDER BY " + ", ".join(keys)


def count_rows(con, result: Result, subtotals: bool) -> int:
    """Rows the result has (shown capped at ``ROW_CAP``, with a note when there are more)."""
    return int(con.execute(f"SELECT count(*) FROM {result.relation} {visible_where(result, subtotals)}"
                           ).fetchone()[0])


def rows(con, result: Result, *, subtotals: bool, offset: int = 0, limit: int = 500, sort: str | None = None,
         descending: bool = False, cap: int | None = ROW_CAP) -> list[tuple]:
    """A page of rows: ``(_depth, g1.., m1..)``. Pages stop at ``cap`` (the screen's first 100,000 rows); exports
    pass ``cap=None``."""
    if cap is not None:
        limit = max(0, min(limit, cap - offset))
    if limit == 0:
        return []
    cols = ", ".join(["_depth"] + [c.name for c in result.columns])
    return [tuple(r) for r in con.execute(
        f"SELECT {cols} FROM {result.relation} {visible_where(result, subtotals)} "
        f"{order_by(result, subtotals, sort, descending)} LIMIT {int(limit)} OFFSET {int(offset)}").fetchall()]


def grand_total(con, result: Result) -> tuple | None:
    """The pinned grand total ``(m1, ..)``; None for an empty result ("No dates in this run")."""
    cols = ", ".join(c.name for c in result.measures)
    row = con.execute(f"SELECT {cols} FROM {result.relation} WHERE _depth = 0").fetchone()
    return tuple(row) if row is not None else None


# ---------------------------------------------------------------------------------------------- distinct values
def distinct_values(con, column: Column, sources: list[Path], search: str | None = None,
                    limit: int = DISTINCT_TOP) -> list[tuple[str, int]]:
    """The ``limit`` most frequent non-blank values with their counts over the ticked runs (ANA-4); with ``search``,
    values containing it (ignoring case) across the whole column."""
    present = present_columns(con, sources)
    if column.id not in present:
        return []
    v = column_expr(column, present)
    where = f"WHERE {v} IS NOT NULL AND trim({v}, ' ') <> ''"
    if search:
        where += f" AND contains(lower({v}), lower({lit(search)}))"
    return [(r[0], int(r[1])) for r in con.execute(
        f"SELECT {v} AS value, count(*) AS n FROM {source_sql(sources)} {where} "
        f"GROUP BY ALL ORDER BY n DESC, value LIMIT {int(limit)}").fetchall()]


# ---------------------------------------------------------------------------------------------- read-only SQL (V3-4)
class NotASelect(ValueError):
    """``select_only`` was given something other than exactly one SELECT statement."""


def select_only(con, sql: str, limit: int = ROW_CAP) -> tuple[list[str], list[tuple]]:
    """Run ``sql`` only if DuckDB's parser finds exactly one statement and classifies it as SELECT (V3-4).
    Returns (column names, first ``limit`` rows). Blocking file-reading table functions is left to V3."""
    try:
        statements = con.extract_statements(sql)
    except duckdb.Error:
        raise NotASelect("The query could not be read") from None
    if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
        raise NotASelect("Only a single SELECT statement is allowed")
    cur = con.execute(statements[0].query)
    names = [x[0] for x in cur.description]
    return names, [tuple(r) for r in cur.fetchmany(limit)]
