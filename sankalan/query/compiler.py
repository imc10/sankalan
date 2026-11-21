"""Definition JSON → SQL (Tech spec, Query layer → Definition to SQL; ANA-4 to ANA-7, DO-3, T21, T23).

``compile_definition`` turns a ``Definition`` into one SELECT over the chosen runs' ``data.parquet`` files, read
together with ``union_by_name`` so a column missing from an older run reads as null (MAP-11). The result holds
every ROLLUP level, marked by ``_depth``:

    _depth INTEGER   number of group levels the row is grouped by: the group count for a detail row, 1 .. n-1 for
                     subtotals, 0 for the grand total
    g1 .. gn         group values, typed (DATE for a date group at any grain, truncated to the period's first day);
                     null in a rolled-up level, and also null for a text or "(Null)" group: the kind tells them apart
    m1 .. mk         measures
    k1 .. kn         group kinds (Tech spec A2 T42): 0 a value, 1 text kept in a Number or Date column ("(Not a
                     number)" / "(Not a date)"), 2 blank ("(Null)"); null in a rolled-up level. Grouping is
                     ``ROLLUP((k1, g1), …)``, so the text and the blank groups stay apart

Number and Date columns carry text companions ``cNNN_t`` (Tech spec A2 5.6): the compiler reads one only where a
filter (Blank, Not blank, Is not a number / date), Count or a group on that column needs it.

Show subtotals only hides or shows rows (DO-7), so subtotals of Average and Count distinct are always correct.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from sankalan.model import definition as d
from sankalan.model.definition import Definition, DefinitionError
from sankalan.model.template import DATE, NUMBER, Column
from sankalan.query.convert import _path, companion, has_companion, lit, sql_type

COUNT_TYPE = "count"


@dataclass(frozen=True)
class OutColumn:
    name: str                   # SQL name in the result: g1.., m1..
    label: str                  # header (display name, measure label, "(removed)")
    role: str                   # "group" or "measure"
    type: str                   # Text / Number / Date, or "count" for Count and Count distinct
    decimals: int | None = None
    grain: str | None = None    # date groups


@dataclass(frozen=True)
class Compiled:
    sql: str
    columns: list[OutColumn]
    levels: int                 # number of group levels
    note: str | None = None     # "No dates in this run" (T21)

    @property
    def groups(self) -> list[OutColumn]:
        return [c for c in self.columns if c.role == "group"]

    @property
    def measures(self) -> list[OutColumn]:
        return [c for c in self.columns if c.role == "measure"]


def source_sql(sources: list[Path]) -> str:
    """The chosen runs' rows, columns matched by name (missing ones null)."""
    if not sources:
        raise DefinitionError("Choose at least one run")
    files = ", ".join(_path(p) for p in sources)
    return f"read_parquet([{files}], union_by_name = true)"


def present_columns(con, sources: list[Path]) -> set[str]:
    return {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {source_sql(sources)}").fetchall()}


def column_expr(col: Column, present: set[str]) -> str:
    """The column, or a typed null when none of the runs has it (added after them)."""
    return col.id if col.id in present else f"CAST(NULL AS {sql_type(col)})"


def companion_expr(col: Column, present: set[str]) -> str:
    """The column's text companion, or a null when none of the runs has it."""
    t = companion(col.id)
    return t if t in present else "CAST(NULL AS VARCHAR)"


def needs_companion(definition: Definition, col: Column) -> bool:
    """Whether the compiled query reads ``col``'s companion: a group, Count, or a Blank / Not blank / Is not a
    number / date filter on it (Tech spec A2 5.6)."""
    if not has_companion(col):
        return False
    return (any(g.column_id == col.id for g in definition.groups)
            or any(m.column_id == col.id and m.fn == d.COUNT for m in definition.measures)
            or any(f.column_id == col.id and f.op in d.NO_VALUE_OPS for f in definition.filters))


def kind_sql(col: Column) -> str:
    """The group kind (T42): 0 a value, 1 text kept in a Number or Date column, 2 blank."""
    if has_companion(col):
        return (f"(CASE WHEN {col.id} IS NOT NULL THEN 0 WHEN {companion(col.id)} IS NOT NULL THEN 1 ELSE 2 END)")
    return f"(CASE WHEN {col.id} IS NOT NULL THEN 0 ELSE 2 END)"


# ---------------------------------------------------------------------------------------------- pieces
def _date(x: dt.date) -> str:
    return f"DATE {lit(x.isoformat())}"


def _add_months(x: dt.date, months: int) -> dt.date:
    m = x.month - 1 + months
    return dt.date(x.year + m // 12, m % 12 + 1, 1)


def _period(start: dt.date, months: int, v: str) -> str:
    return f"({v} >= {_date(start)} AND {v} < {_date(_add_months(start, months))})"


def _num(text, scale: int) -> str:
    return f"CAST({lit(str(d.parse_number(text)))} AS DECIMAL(38,{scale}))"


def blank(v: str) -> str:
    return f"({v} IS NULL OR trim(CAST({v} AS VARCHAR), ' ') = '')"


def latest_period(op: str, latest: dt.date) -> tuple[dt.date, int]:
    """The calendar month, quarter or year containing ``latest`` (DO-3): (first day, months)."""
    if op == d.LATEST_MONTH:
        return dt.date(latest.year, latest.month, 1), 1
    if op == d.LATEST_QUARTER:
        return dt.date(latest.year, (latest.month - 1) // 3 * 3 + 1, 1), 3
    return dt.date(latest.year, 1, 1), 12


def filter_sql(f: d.Filter, col: Column, latest: dt.date | None = None) -> str:
    """The condition for one filter. Value filters test the value only, so text never matches (TXT-5, TXT-7);
    Blank on a Number or Date column means neither a value nor text (TXT-8)."""
    v, x = col.id, f.values
    if f.op in (d.BLANK, d.NOT_BLANK):
        cond = f"({v} IS NULL AND {companion(v)} IS NULL)" if has_companion(col) else blank(v)
        return cond if f.op == d.BLANK else f"NOT {cond}"
    if f.op in (d.NOT_NUMBER, d.NOT_DATE) and has_companion(col):
        return f"({companion(v)} IS NOT NULL)"
    if col.type == DATE:
        if f.op == d.YEAR:
            return _period(dt.date(int(x[0]), 1, 1), 12, v)
        if f.op == d.QUARTER:
            return _period(dt.date(int(x[0]), (int(x[1]) - 1) * 3 + 1, 1), 3, v)
        if f.op == d.MONTH:
            return _period(dt.date(int(x[0]), int(x[1]), 1), 1, v)
        if f.op == d.BETWEEN:
            parts = [f"{v} >= {_date(d.parse_date(x[0]))}" if x[0] not in (None, "") else None,
                     f"{v} <= {_date(d.parse_date(x[1]))}" if x[1] not in (None, "") else None]
            return "(" + " AND ".join(p for p in parts if p) + ")"
        if f.op in d.RELATIVE:
            if latest is None:
                return "false"
            start, months = latest_period(f.op, latest)
            return _period(start, months, v)
    if col.type == NUMBER:
        s = col.decimals or 0
        if f.op == d.EQUALS:
            return f"({v} = {_num(x[0], s)})"
        if f.op == d.BETWEEN:
            parts = [f"{v} >= {_num(x[0], s)}" if x[0] not in (None, "") else None,
                     f"{v} <= {_num(x[1], s)}" if x[1] not in (None, "") else None]
            return "(" + " AND ".join(p for p in parts if p) + ")"
    else:
        if f.op == d.ONE_OF:
            return f"({v} IN ({', '.join(lit(str(i)) for i in x)}))"
        if f.op == d.CONTAINS:
            return f"contains(lower({v}), lower({lit(str(x[0]))}))"
    raise DefinitionError(f"{f.op!r} is not a filter for {col.name}")


def group_sql(g: d.Group, col: Column) -> str:
    if col.type == DATE and g.grain not in (None, d.DAY):
        return f"CAST(date_trunc({lit(g.grain)}, {col.id}) AS DATE)"
    return col.id


def average_sql(v: str, decimals: int) -> str:
    """Average rounded half away from zero to the column's decimals (T13), in exact integer arithmetic: DuckDB's
    ``avg`` of a DECIMAL is a DOUBLE."""
    units = f"CAST(replace(CAST(sum({v}) AS VARCHAR), '.', '') AS HUGEINT)"   # the sum in 10^-d units
    n = f"count({v})"
    q = f"((abs({units}) * 2 + {n}) // (2 * {n}))"
    text = f"(CASE WHEN {units} < 0 THEN '-' ELSE '' END) || CAST({q} AS VARCHAR) || 'e-{decimals}'"
    return f"(CASE WHEN {n} = 0 THEN NULL ELSE CAST({text} AS DECIMAL(38,{decimals})) END)"


def measure_sql(m: d.Measure, col: Column | None) -> str:
    if m.column_id is None:
        return "count(*)"
    v = col.id
    if m.fn == d.SUM:
        return f"sum({v})"
    if m.fn == d.COUNT:
        if has_companion(col):        # values and text: every non-blank cell (TXT-8); never both filled
            return f"(count({v}) + count({companion(v)}))"
        return f"count({v})"          # null = blank, so only non-blank values count (T23)
    if m.fn == d.COUNT_DISTINCT:
        return f"count(DISTINCT {v})"
    if m.fn == d.AVG:
        return average_sql(v, col.decimals or 0)
    if m.fn == d.MIN:
        return f"min({v})"
    if m.fn == d.MAX:
        return f"max({v})"
    raise DefinitionError(m.fn)


def _measure_type(m: d.Measure, col: Column | None) -> tuple[str, int | None]:
    if m.fn in (d.COUNT, d.COUNT_DISTINCT):
        return COUNT_TYPE, None
    return col.type, col.decimals


# ---------------------------------------------------------------------------------------------- compile
def out_columns(definition: Definition, by_id: dict[str, Column]) -> list[OutColumn]:
    """The result's columns and headers: today's column names, so a renamed column shows its new name."""
    out = []
    for i, g in enumerate(definition.groups, 1):
        col = by_id[g.column_id]
        out.append(OutColumn(f"g{i}", d.group_label(g, col), "group", col.type, col.decimals,
                             (g.grain or d.DAY) if col.type == DATE else None))
    for i, m in enumerate(definition.measures, 1):
        col = by_id.get(m.column_id) if m.column_id is not None else None
        typ, dec = _measure_type(m, col)
        out.append(OutColumn(f"m{i}", d.measure_label(m, by_id), "measure", typ, dec))
    return out


def compile_definition(con, definition: Definition, columns: list[Column], sources: list[Path], *,
                       output: bool = False) -> Compiled:
    """The SELECT for ``definition`` over ``sources`` (data.parquet paths). ``columns``: every template column,
    removed ones included, so a saved analysis that uses a removed column keeps working (T23). ``output``: a
    default output (relative date filters, DO-3)."""
    d.check(definition, columns, output=output)
    by_id = {c.id: c for c in columns}
    present = present_columns(con, sources)
    src = source_sql(sources)
    used = []
    for cid in ([f.column_id for f in definition.filters] + [g.column_id for g in definition.groups]
                + [m.column_id for m in definition.measures if m.column_id is not None]):
        if cid not in used:
            used.append(cid)
    items = []
    for c in used:
        items.append(f"{column_expr(by_id[c], present)} AS {c}")
        if needs_companion(definition, by_id[c]):
            items.append(f"{companion_expr(by_id[c], present)} AS {companion(c)}")
    select = ", ".join(items) or "1 AS _one"

    note = None
    conds = []
    for f in definition.filters:
        col = by_id[f.column_id]
        latest = None
        if f.op in d.RELATIVE:
            latest = (con.execute(f"SELECT max({column_expr(col, present)}) FROM {src}").fetchone()[0]
                      if col.id in present else None)
            if latest is None:
                note = d.NO_DATES_NOTE
        conds.append(filter_sql(f, col, latest))
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    out = out_columns(definition, by_id)
    group_exprs = [f"{group_sql(g, by_id[g.column_id])} AS g{i}, {kind_sql(by_id[g.column_id])} AS k{i}"
                   for i, g in enumerate(definition.groups, 1)]
    measure_exprs = [f"{measure_sql(m, by_id.get(m.column_id) if m.column_id is not None else None)} AS m{i}"
                     for i, m in enumerate(definition.measures, 1)]

    base = f"SELECT {select} FROM {src} {where}"
    n = len(group_exprs)
    if n:
        gnames = ", ".join(f"g{i}" for i in range(1, n + 1))
        knames = ", ".join(f"k{i}" for i in range(1, n + 1))
        levels = ", ".join(f"(k{i}, g{i})" for i in range(1, n + 1))
        depth = f"{n} - (" + " + ".join(f"grouping(g{i})" for i in range(1, n + 1)) + ")"
        sql = (f"SELECT CAST({depth} AS INTEGER) AS _depth, {gnames}, {', '.join(measure_exprs)}, {knames} "
               f"FROM (SELECT *, {', '.join(group_exprs)} FROM ({base})) GROUP BY ROLLUP ({levels})")
    else:
        sql = f"SELECT CAST(0 AS INTEGER) AS _depth, {', '.join(measure_exprs)} FROM ({base})"
    if note is not None:
        sql = f"SELECT * FROM ({sql}) WHERE false"       # an empty result, not a failure (T21)
    return Compiled(sql, out, n, note)
