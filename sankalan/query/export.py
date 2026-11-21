"""What each export writes, as SQL, and the DuckDB half of writing it (EXP-1 to EXP-6, T19, ISS-3, ANA-9, DO-7).

Every export is a header (display names, written by Python) plus one SELECT whose values are already text in the
export's form: numbers at the column's decimal places with no grouping, dates DD-MM-YYYY (EXP-3). ``copy_csv``
writes that SELECT to a ``.part`` file in a folder DuckDB may write to (spike S2: external access is off, so it
can't write to the folder the user chose); ``sankalan.exporting`` then streams it to the destination.

| Export            | Columns                                                                              |
| ----------------- | ------------------------------------------------------------------------------------ |
| A run's data      | Template columns + Source File, Source Sheet, Source Row, Run ID (EXP-6)             |
| Left-out rows     | The same + Reason ("Invoice No: Character pattern; Taxable Value: Is a number")      |
| Issue list        | File, Sheet, Row, Column, Value, Rule, Severity, Message (ISS-3)                     |
| Output / analysis | Group columns + measures; subtotal rows when shown; the grand total last             |

A Number or Date cell holding text exports the text as typed (Feature Spec A2 TXT-4; one expression, Tech spec A2
5.3), quoted by DuckDB where CSV needs it. A run's data and left-out rows come in stored order (``ORDER BY
_src_file, _src_row``, T32). Result exports label the text group "(Not a number)" / "(Not a date)" (TXT-10).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sankalan.model import definition as d
from sankalan.model.rule import RULE_NAMES, Rule
from sankalan.model.template import DATE, NUMBER, Column, active
from sankalan.query import layer
from sankalan.query.compiler import COUNT_TYPE, OutColumn
from sankalan.query.convert import _path, companion, has_companion, lit
from sankalan.query.validate import present_columns

SOURCE_COLUMNS = ("Source File", "Source Sheet", "Source Row", "Run ID")
STORED_ORDER = "ORDER BY _src_file, _src_row"      # the order rows were loaded in (T32)
ISSUE_HEADERS = ("File", "Sheet", "Row", "Column", "Value", "Rule", "Severity", "Message")
REASON = "Reason"


@dataclass(frozen=True)
class ExportQuery:
    headers: list[str]
    sql: str


def _value_text(col: Column, v: str) -> str:
    if col.type == NUMBER:
        return f"CAST({v} AS VARCHAR)"          # DECIMAL(38,d) as text: the column's decimals, no grouping
    if col.type == DATE:
        return f"strftime({v}, '%d-%m-%Y')"
    return v


def _text(col: Column, present: set[str]) -> str:
    """One export column: the value in the export's form, else the text as typed (TXT-4). A column the file
    doesn't have (added after the run) is empty."""
    if col.id not in present:
        return "NULL"
    value = _value_text(col, col.id)
    t = companion(col.id)
    if has_companion(col) and t in present:
        return f"coalesce({value}, {t})"
    return value


def _case(expr: str, mapping: dict, default: str) -> str:
    if not mapping:
        return default
    whens = " ".join(f"WHEN {lit(k) if isinstance(k, str) else int(k)} THEN {lit(v)}" for k, v in mapping.items())
    return f"(CASE {expr} {whens} ELSE {default} END)"


def _file_name(file_names: dict[int, str]) -> str:
    return _case("_src_file", file_names, "'file ' || _src_file")


# ---------------------------------------------------------------------------------------------- run data, left out
def _row_columns(con, path: Path, columns: list[Column], file_names: dict[int, str], run_label: str):
    present = present_columns(con, path)
    cols = active(columns)
    exprs = [_text(c, present) for c in cols]
    exprs += [_file_name(file_names), "_src_sheet", "_src_row", lit(run_label)]
    return [c.name for c in cols] + list(SOURCE_COLUMNS), exprs


def run_data(con, data: Path, columns: list[Column], file_names: dict[int, str], run_label: str) -> ExportQuery:
    """A run's rows (EXP-6). ``columns``: the template's columns; removed ones are left out, ones added after the
    run are empty."""
    headers, exprs = _row_columns(con, data, columns, file_names, run_label)
    return ExportQuery(headers, f"SELECT {', '.join(exprs)} FROM read_parquet({_path(data)}) {STORED_ORDER}")


def reason_text(rules: list[Rule], columns: list[Column]) -> dict[str, str]:
    """Rule ID → "Column: Rule" for the Reason column."""
    names = {c.id: c.name for c in columns}
    return {r.id: f"{names.get(r.column_id, r.column_id)}: {RULE_NAMES[r.type]}" for r in rules}


def left_out(con, path: Path, columns: list[Column], file_names: dict[int, str], run_label: str,
             rules: list[Rule]) -> ExportQuery:
    """A run's left-out rows with the reason (T19). ``rules``: the rules that ran for the run."""
    headers, exprs = _row_columns(con, path, columns, file_names, run_label)
    one = _case("x", reason_text(rules, columns), "x")
    reason = f"array_to_string(list_transform(string_split(_reason, ','), lambda x: {one}), '; ')"
    return ExportQuery(headers + [REASON],
                       f"SELECT {', '.join(exprs + [reason])} FROM read_parquet({_path(path)}) {STORED_ORDER}")


# ---------------------------------------------------------------------------------------------- issue list
def issue_list(issues: Path, file_names: dict[int, str], column_names: dict[str, str]) -> ExportQuery:
    """The full issue list (ISS-3) in file, row and rule order. The message is UI-6's: file, sheet (none for a
    CSV file), row with grouping, column, problem."""
    file_name = _file_name(file_names)
    column = _case("column_id", column_names, "column_id")
    rule = _case("rule_type", RULE_NAMES, "rule_type")
    where = (f"{file_name} || (CASE WHEN coalesce(_src_sheet, '') = '' THEN '' ELSE ', ' || _src_sheet END)")
    message = f"{where} || ', row ' || format('{{:,}}', _src_row) || ', ' || {column} || ': ' || problem"
    sql = (f"SELECT {file_name}, nullif(_src_sheet, ''), _src_row, {column}, nullif(value, ''), {rule}, severity, "
           f"{message} FROM read_parquet({_path(issues)})")
    return ExportQuery(list(ISSUE_HEADERS), sql)


# ---------------------------------------------------------------------------------------------- results
def _group_text(c: OutColumn) -> str:
    v = c.name
    if c.type == DATE:
        if c.grain in (None, d.DAY):
            return f"strftime({v}, '%d-%m-%Y')"
        if c.grain == "month":
            return f"strftime({v}, '%b-%Y')"
        if c.grain == "quarter":
            return f"('Q' || quarter({v}) || '-' || year({v}))"
        return f"CAST(year({v}) AS VARCHAR)"
    return f"CAST({v} AS VARCHAR)"


def _measure_text(c: OutColumn) -> str:
    if c.type == DATE:
        return f"strftime({c.name}, '%d-%m-%Y')"
    if c.type in (NUMBER, COUNT_TYPE):
        return f"CAST({c.name} AS VARCHAR)"
    return c.name


def result(res: layer.Result, *, subtotals: bool, sort: str | None = None, descending: bool = False) -> ExportQuery:
    """The full result (ANA-9, DO-7): every row, not only the first 100,000; subtotals when shown; the grand total
    last. Group cells: "(Null)" for a blank value, "Total" on a subtotal row's first rolled-up level, "Grand total"
    on the grand total row."""
    groups, measures = res.groups, res.measures
    exprs = []
    for i, g in enumerate(groups, 1):
        label = (f"(CASE k{i} WHEN 1 THEN {lit(d.text_group_label(g.type))} WHEN 2 THEN {lit(d.NULL_LABEL)} "
                 f"ELSE coalesce({_group_text(g)}, {lit(d.NULL_LABEL)}) END)")
        exprs.append(f"(CASE WHEN _depth >= {i} THEN {label} "
                     f"WHEN _depth = 0 AND {i} = 1 THEN {lit(d.TOTAL_LABEL)} "
                     f"WHEN _depth = {i - 1} THEN {lit(d.SUBTOTAL_LABEL)} END)")
    exprs += [_measure_text(m) for m in measures]
    where = layer.visible_where(res, subtotals)
    where = f"{where} OR _depth = 0" if where != "WHERE false" else "WHERE _depth = 0"
    order = layer.order_by(res, subtotals, sort, descending)
    order = "ORDER BY (_depth = 0)" + (", " + order[len("ORDER BY "):] if order else "")
    return ExportQuery([c.label for c in res.columns],
                       f"SELECT {', '.join(exprs)} FROM {res.relation} {where} {order}")


# ---------------------------------------------------------------------------------------------- writing
def copy_csv(con, query: ExportQuery, part: Path, delimiter: str) -> int:
    """Write the query's rows (no header) to ``part``; returns the number of rows."""
    row = con.execute(f"COPY ({query.sql}) TO {_path(part)} "
                      f"(FORMAT csv, HEADER false, DELIMITER {lit(delimiter)}, QUOTE '\"', "
                      f"DATEFORMAT '%d-%m-%Y')").fetchone()
    return int(row[0]) if row else 0
