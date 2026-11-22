r"""Convert stage (Tech spec, Ingestion → 4. Convert; MAP-9, MAP-10, T13, T14).

One SELECT per file and sheet reads its raw staged text and lines its columns up by mapping onto template column
IDs (a column with no source → null). They are joined with UNION ALL, converted, and written to ``data.parquet``
sorted by ``_src_file, _src_row`` (Tech spec A2 T32: DuckDB doesn't keep a UNION ALL's order, spike S8a).

Text companions (Tech spec A2 5.1, T41; Feature Spec A2 TXT-1): every Number and Date column ``cNNN`` has a
``cNNN_t VARCHAR``. It holds the cell's text exactly as staged (spaces included, T14) where the cell isn't blank and
doesn't convert, and is null on every other row, so ``cNNN`` and ``cNNN_t`` are never both filled. A column with no
source in a file (MAP-6) is null in both. Is a number and Is a date issues read the companions (VAL-2, VAL-4).

The rules are the ones documented in ``sankalan/ingest/values.py`` (the Python oracle), using the same patterns.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from sankalan.ingest import values as rules
from sankalan.ingest.canonical import SRC_ROW, value_name
from sankalan.model.template import DATE, NUMBER, Column

DATA = "data.parquet"
FIXED_COLUMNS = ("run_id", "_src_file", "_src_sheet", "_src_row")


def companion(column_id: str) -> str:
    """The text companion of a Number or Date column (Tech spec A2 5.1)."""
    return f"{column_id}_t"


def has_companion(col: Column) -> bool:
    return col.type in (NUMBER, DATE)


def lit(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def _path(p: Path) -> str:
    return lit(Path(p).as_posix())


@dataclass
class RawPart:
    """One file and sheet's raw staged text."""
    file_index: int                 # _src_file: the run_file row
    sheet: str
    raw_path: Path
    width: int                      # number of source columns v0..v{width-1}
    mapping: dict[str, int | None] = field(default_factory=dict)   # column ID -> source column position


# ---------------------------------------------------------------------------------------------- rules as SQL
def blank_sql(v: str) -> str:
    return f"({v} IS NULL OR trim({v}, ' ') = '')"


def sql_type(col: Column) -> str:
    if col.type == NUMBER:
        return f"DECIMAL(38,{col.decimals})"
    if col.type == DATE:
        return "DATE"
    return "VARCHAR"


def text_sql(v: str) -> str:
    return f"(CASE WHEN {blank_sql(v)} THEN NULL ELSE {v} END)"


# Fast paths: most values are staged numbers and ISO dates, which convert with a plain CAST. The full rule (several
# regular expressions) runs only for the rest; CASE evaluates a branch only for the rows that reach it.
PLAIN_NUMBER = r"-?[0-9]+(\.[0-9]+)?"
PLAIN_ISO_DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"


def number_sql(v: str, decimals: int) -> str:
    """NUMBER rule → DECIMAL(38,d); null when blank or not readable. The CAST from text rounds half away from
    zero (spike: confirmed for d = 0, 2, 6 and negative values)."""
    t = f"lower(regexp_replace({v}, '[{rules.NUMBER_SPACES}]', '', 'g'))"
    pat = lit(rules.NUMBER_PATTERN)
    names = "[" + ", ".join(lit(n) for n in rules.NUMBER_GROUPS) + "]"
    m = f"regexp_extract({t}, {pat}, {names})"
    flag = "(CASE WHEN {x} <> '' THEN 1 ELSE 0 END)"
    markers = " + ".join(flag.format(x=f"{m}.{k}") for k in ("open", "s1", "s2"))
    neg = " OR ".join(f"{m}.{k} <> ''" for k in ("open", "s1", "s2"))
    value = f"TRY_CAST(replace({m}.num, ',', '') AS DECIMAL(38,{decimals}))"
    return (f"(CASE WHEN {blank_sql(v)} THEN NULL "
            f"WHEN regexp_full_match({v}, {lit(PLAIN_NUMBER)}) THEN TRY_CAST({v} AS DECIMAL(38,{decimals})) "
            f"WHEN NOT regexp_matches({t}, {pat}) THEN NULL "
            f"WHEN ({m}.open = '') <> ({m}.close = '') THEN NULL "
            f"WHEN ({markers}) > 1 THEN NULL "
            f"WHEN {m}.cur1 <> '' AND {m}.cur2 <> '' THEN NULL "
            f"WHEN {neg} THEN CAST(-{value} AS DECIMAL(38,{decimals})) "
            f"ELSE {value} END)")


def date_sql(v: str, date_format: str | None) -> str:
    part = f"regexp_extract(trim({v}, ' '), {lit(rules.DATE_PART_PATTERN)}, 1)"
    whens = [f"WHEN regexp_full_match({v}, {lit(PLAIN_ISO_DATE)}) THEN TRY_CAST({v} AS DATE)",
             f"WHEN regexp_matches({part}, {lit(rules.ISO_PATTERN)}) "
             f"THEN CAST(try_strptime({part}, '%Y-%m-%d') AS DATE)"]
    if date_format is not None:
        pat, fmt = rules.DATE_TEXT_FORMATS[date_format]
        whens.append(f"WHEN regexp_matches({part}, {lit(pat)}) THEN CAST(try_strptime({part}, {lit(fmt)}) AS DATE)")
    return f"(CASE WHEN {blank_sql(v)} THEN NULL {' '.join(whens)} ELSE NULL END)"


def convert_sql(col: Column, v: str) -> str:
    if col.type == NUMBER:
        return number_sql(v, col.decimals)
    if col.type == DATE:
        return date_sql(v, col.date_format)
    return text_sql(v)


# ---------------------------------------------------------------------------------------------- statements
def read_raw_sql(part: RawPart) -> str:
    cols = ", ".join([f"{lit(SRC_ROW)}: 'BIGINT'"] + [f"{lit(value_name(i))}: 'VARCHAR'" for i in range(part.width)])
    return (f"read_csv({_path(part.raw_path)}, header = true, auto_detect = false, delim = ',', quote = '\"', "
            f"escape = '\"', strict_mode = true, columns = {{{cols}}})")


def _source(part: RawPart, col: Column) -> str | None:
    pos = part.mapping.get(col.id)
    if pos is None or pos >= part.width:
        return None
    return value_name(pos)


def _converted(col: Column, value: str | None, raw: str | None) -> list[str]:
    """The outer level's items for one column, given the inner level's converted ``value`` and staged ``raw`` text
    (both None when the file has no source for it)."""
    if value is None:
        items = [f"CAST(NULL AS {sql_type(col)}) AS {col.id}"]
        if has_companion(col):
            items.append(f"CAST(NULL AS VARCHAR) AS {companion(col.id)}")
        return items
    if not has_companion(col):
        return [f"{value} AS {col.id}"]
    return [f"{value} AS {col.id}",
            f"CAST(CASE WHEN {value} IS NULL AND NOT {blank_sql(raw)} THEN {raw} END AS VARCHAR) "
            f"AS {companion(col.id)}"]


def part_select(part: RawPart, columns: list[Column], run_id: str) -> str:
    """Two levels, so each conversion is computed once per cell: the inner level converts, the outer level picks the
    value or keeps the text in the companion (Tech spec A2 5.2)."""
    inner = [f"{lit(run_id)} AS run_id", f"CAST({part.file_index} AS INTEGER) AS _src_file",
             f"{lit(part.sheet)} AS _src_sheet", f"{SRC_ROW} AS _src_row"]
    outer = ["run_id", "_src_file", "_src_sheet", "_src_row"]
    for n, col in enumerate(columns):
        src = _source(part, col)
        if src is None:
            outer += _converted(col, None, None)
            continue
        inner.append(f"CAST({convert_sql(col, src)} AS {sql_type(col)}) AS x{n}")
        if has_companion(col):
            inner.append(f"{src} AS r{n}")
        outer += _converted(col, f"x{n}", f"r{n}")
    return f"SELECT {', '.join(outer)} FROM (SELECT {', '.join(inner)} FROM {read_raw_sql(part)})"


UNSORTED = ".unsorted"


def write_data(con, parts: list[RawPart], columns: list[Column], run_id: str, out: Path) -> None:
    """The run's rows in stored order: file (the file-sheets in load order), then source row (T32).

    Two statements: convert into ``<out>.unsorted``, then sort that plain Parquet into ``out`` and delete it. Fusing
    the conversion and the sort in one statement ran out of memory on 2,500,000 rows × 20 columns at a 1 GiB limit
    (dev PC, 21-11-2026); in two steps the same load took 32 s + 5 s within the limit."""
    if not parts:
        raise ValueError("no file to convert")
    union = " UNION ALL ".join(part_select(p, columns, run_id) for p in parts)
    tmp = Path(out).with_name(Path(out).name + UNSORTED)
    try:
        con.execute(f"COPY ({union}) TO {_path(tmp)} (FORMAT parquet)")
        con.execute(f"COPY (SELECT * FROM read_parquet({_path(tmp)}) ORDER BY _src_file, _src_row) "
                    f"TO {_path(out)} (FORMAT parquet)")
    finally:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            pass


def parquet_rows(con, path: Path) -> int:
    return int(con.execute(f"SELECT count(*) FROM read_parquet({_path(path)})").fetchone()[0])


def read_text_values(con, path: Path, columns: list[Column]) -> list[tuple]:
    """(file, sheet, row, column ID, text as typed) of every companion value, ordered by file, row and column: for
    tests."""
    cols = [c for c in columns if has_companion(c) and not c.removed]
    if not cols:
        return []
    union = " UNION ALL ".join(
        f"SELECT _src_file, _src_sheet, _src_row, {lit(c.id)} AS column_id, {companion(c.id)} AS value "
        f"FROM read_parquet({_path(path)}) WHERE {companion(c.id)} IS NOT NULL" for c in cols)
    return [tuple(r) for r in con.execute(f"SELECT * FROM ({union}) ORDER BY _src_file, _src_row, column_id")
            .fetchall()]


def read_rows(con, path: Path, column_ids: list[str]) -> list[tuple]:
    """Rows of a data file, ordered by file and row: for tests."""
    cols = ", ".join(["_src_file", "_src_sheet", "_src_row"] + list(column_ids))
    return [tuple(r) for r in con.execute(
        f"SELECT {cols} FROM read_parquet({_path(path)}) ORDER BY _src_file, _src_row").fetchall()]


def column_sums(con, path: Path, column_ids: list[str]) -> dict[str, object]:
    sel = ", ".join(f"sum({c})" for c in column_ids)
    row = con.execute(f"SELECT {sel} FROM read_parquet({_path(path)})").fetchone()
    return dict(zip(column_ids, row))


def convert_values(con, raws: list[str | None], col: Column) -> list[tuple]:
    """Convert loose values with the SQL rule (tests check it against the Python oracle): ``(value, text)`` per
    value, ``text`` being what the companion keeps (always None for a Text column). No files touched."""
    if not raws:
        return []
    rows = ", ".join(f"({i}, {'NULL' if r is None else lit(r)})" for i, r in enumerate(raws))
    items = ", ".join(_converted(col, "x", "v"))
    sql = (f"SELECT {items} FROM (SELECT i, v, CAST({convert_sql(col, 'v')} AS {sql_type(col)}) AS x "
           f"FROM (VALUES {rows}) t(i, v) ORDER BY i)")
    return [(r[0], r[1] if len(r) > 1 else None) for r in con.execute(sql).fetchall()]


def rows_by_file(con, path: Path) -> dict[int, int]:
    """Rows per source file in a run's ``data.parquet`` (5.1 Source files: rows loaded)."""
    return {int(f): int(n) for f, n in con.execute(
        f"SELECT _src_file, count(*) FROM read_parquet({_path(path)}) GROUP BY _src_file").fetchall()}
