r"""Convert stage (Tech spec, Ingestion → 4. Convert; MAP-9, MAP-10, T13, T14).

One SELECT per file and sheet reads its raw staged text and lines its columns up by mapping onto template column
IDs (a column with no source → null). They are joined with UNION ALL, converted, and written to ``data.parquet``.
Values that are not blank but don't convert go to ``conversion_failures.parquet`` with the text as typed: for
values that failed conversion this is the only place the original text is kept, and the validation scan turns
them into Is a number / Is a date issues (VAL-2, VAL-4).

The rules are the ones documented in ``sankalan/ingest/values.py`` (the Python oracle), using the same patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sankalan.ingest import values as rules
from sankalan.ingest.canonical import SRC_ROW, value_name
from sankalan.model.template import DATE, NUMBER, Column

DATA = "data.parquet"
FAILURES = "conversion_failures.parquet"
FIXED_COLUMNS = ("run_id", "_src_file", "_src_sheet", "_src_row")


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


def part_select(part: RawPart, columns: list[Column], run_id: str) -> str:
    items = [f"{lit(run_id)} AS run_id", f"CAST({part.file_index} AS INTEGER) AS _src_file",
             f"{lit(part.sheet)} AS _src_sheet", f"{SRC_ROW} AS _src_row"]
    for col in columns:
        src = _source(part, col)
        expr = f"CAST(NULL AS {sql_type(col)})" if src is None else f"CAST({convert_sql(col, src)} AS {sql_type(col)})"
        items.append(f"{expr} AS {col.id}")
    return f"SELECT {', '.join(items)} FROM {read_raw_sql(part)}"


def failures_select(part: RawPart, columns: list[Column]) -> str | None:
    typed = [(col, _source(part, col)) for col in columns if col.type in (NUMBER, DATE)]
    typed = [(c, s) for c, s in typed if s is not None]
    if not typed:
        return None
    bads = [f"(NOT {blank_sql(s)} AND {convert_sql(c, s)} IS NULL)" for c, s in typed]
    inner = ", ".join([f"CAST({part.file_index} AS INTEGER) AS _src_file", f"{lit(part.sheet)} AS _src_sheet",
                       f"{SRC_ROW} AS _src_row"]
                      + [f"{s} AS raw{i}" for i, (_c, s) in enumerate(typed)]
                      + [f"{b} AS bad{i}" for i, b in enumerate(bads)])
    structs = ", ".join(f"{{'column_id': {lit(c.id)}, 'value': raw{i}, 'bad': bad{i}}}"
                        for i, (c, _s) in enumerate(typed))
    any_bad = " OR ".join(f"bad{i}" for i in range(len(typed)))
    return (f"SELECT _src_file, _src_sheet, _src_row, f.column_id AS column_id, f.value AS value FROM ("
            f"SELECT _src_file, _src_sheet, _src_row, unnest([{structs}]) AS f FROM ("
            f"SELECT {inner} FROM {read_raw_sql(part)}) WHERE {any_bad}) WHERE f.bad")


_EMPTY_FAILURES = ("SELECT CAST(NULL AS INTEGER) AS _src_file, CAST(NULL AS VARCHAR) AS _src_sheet, "
                   "CAST(NULL AS BIGINT) AS _src_row, CAST(NULL AS VARCHAR) AS column_id, "
                   "CAST(NULL AS VARCHAR) AS value WHERE false")


def write_data(con, parts: list[RawPart], columns: list[Column], run_id: str, out: Path) -> None:
    if not parts:
        raise ValueError("no file to convert")
    union = " UNION ALL ".join(part_select(p, columns, run_id) for p in parts)
    con.execute(f"COPY ({union}) TO {_path(out)} (FORMAT parquet)")


def write_failures(con, parts: list[RawPart], columns: list[Column], out: Path) -> None:
    selects = [s for s in (failures_select(p, columns) for p in parts) if s is not None] or [_EMPTY_FAILURES]
    con.execute(f"COPY ({' UNION ALL '.join(selects)}) TO {_path(out)} (FORMAT parquet)")


def parquet_rows(con, path: Path) -> int:
    return int(con.execute(f"SELECT count(*) FROM read_parquet({_path(path)})").fetchone()[0])


def failure_counts(con, path: Path) -> dict[str, int]:
    """Failures per column ID."""
    rows = con.execute(f"SELECT column_id, count(*) FROM read_parquet({_path(path)}) GROUP BY column_id").fetchall()
    return {r[0]: int(r[1]) for r in rows}


def read_failures(con, path: Path) -> list[tuple]:
    """(file, sheet, row, column ID, value as typed), ordered by file, sheet and row: for tests and Phase 3."""
    return [tuple(r) for r in con.execute(
        f"SELECT _src_file, _src_sheet, _src_row, column_id, value FROM read_parquet({_path(path)}) "
        f"ORDER BY _src_file, _src_row, column_id").fetchall()]


def read_rows(con, path: Path, column_ids: list[str]) -> list[tuple]:
    """Rows of a data file, ordered by file and row: for tests."""
    cols = ", ".join(["_src_file", "_src_sheet", "_src_row"] + list(column_ids))
    return [tuple(r) for r in con.execute(
        f"SELECT {cols} FROM read_parquet({_path(path)}) ORDER BY _src_file, _src_row").fetchall()]


def column_sums(con, path: Path, column_ids: list[str]) -> dict[str, object]:
    sel = ", ".join(f"sum({c})" for c in column_ids)
    row = con.execute(f"SELECT {sel} FROM read_parquet({_path(path)})").fetchone()
    return dict(zip(column_ids, row))


def convert_values(con, raws: list[str | None], col: Column) -> list:
    """Convert loose values with the SQL rule (tests check it against the Python oracle). No files touched."""
    if not raws:
        return []
    rows = ", ".join(f"({i}, {'NULL' if r is None else lit(r)})" for i, r in enumerate(raws))
    sql = (f"SELECT CAST({convert_sql(col, 'v')} AS {sql_type(col)}) FROM (VALUES {rows}) t(i, v) ORDER BY i")
    return [r[0] for r in con.execute(sql).fetchall()]
