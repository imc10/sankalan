"""Validation scan as SQL (Tech spec, Validation and issues; VAL-1 to VAL-9, T16, T17, ISS-1, ISS-2).

Every rule becomes a SQL condition; one scan of ``data.parquet`` finds the rules each row fails. Is a number and
Is a date fail on the text companions (Tech spec A2 5.4, TXT-13): a Number or Date cell that didn't convert is null
with its text in ``cNNN_t``. Range and Allowed values rules test the value only, so a text cell gives exactly one
issue; Not blank passes on text; Unique within the run compares the value shown (two "NA" are equal). Unique within
the run takes one extra grouping pass over its key columns.

``issues.parquet``: one row per failure, ordered by file, row and rule::

    _src_file INTEGER, _src_sheet VARCHAR, _src_row BIGINT, column_id VARCHAR, rule_id VARCHAR,
    rule_type VARCHAR, severity VARCHAR, value VARCHAR, problem VARCHAR, duplicate_first BOOLEAN

``value`` is the value as typed for Text columns and for text kept in a Number or Date column; a stored number is shown as
plain decimal text and a stored date as DD-MM-YYYY; a blank cell is ''. ``duplicate_first`` is true on the first
row of a Unique within the run group, which is kept when errors are overridden (T18), and null on every other issue.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sankalan.model.rule import (ALLOWED_VALUES, DATE_RANGE, ERROR, IS_DATE, IS_NUMBER, NOT_BLANK, NUMBER_RANGE,
                                 PATTERN, TEXT_LENGTH, UNIQUE, WARNING, Rule)
from sankalan.model.run import IssueCount
from sankalan.model.template import DATE, NUMBER, Column, active
from sankalan.query.convert import _path, companion, has_companion, lit, sql_type
from sankalan.validation import rules as meaning

ISSUES = "issues.parquet"
ISSUE_COLUMNS = ("_src_file", "_src_sheet", "_src_row", "column_id", "rule_id", "rule_type", "severity", "value",
                 "problem", "duplicate_first")
GRID_PER_RULE = 10_000      # ISS-2
SHOW_FIRST = 20             # VR-8

_EMPTY_FOUND = ("SELECT CAST(NULL AS INTEGER) AS _src_file, CAST(NULL AS VARCHAR) AS _src_sheet, "
                "CAST(NULL AS BIGINT) AS _src_row, CAST(NULL AS INTEGER) AS _rule, CAST(NULL AS VARCHAR) AS value, "
                "CAST(NULL AS VARCHAR) AS problem, CAST(NULL AS BOOLEAN) AS duplicate_first WHERE false")


def present_columns(con, data: Path) -> set[str]:
    return {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet({_path(data)})").fetchall()}


def _num_lit(text, scale: int) -> str:
    return f"CAST({lit(str(meaning.parse_number(text)))} AS DECIMAL(38,{scale}))"


def _scale(col: Column, *numbers) -> int:
    """Decimal places to compare at: the column's, or more if a setting has more (never rounds a setting)."""
    s = col.decimals or 0
    for n in numbers:
        if n not in (None, ""):
            s = max(s, -meaning.parse_number(n).as_tuple().exponent)
    return s


def _value_text(col: Column, v: str) -> str:
    if col.type == NUMBER:
        return f"CAST({v} AS VARCHAR)"
    if col.type == DATE:
        return f"strftime({v}, '%d-%m-%Y')"
    return v


def _fails(rule: Rule, col: Column, v: str) -> str:
    """SQL that is true when the row fails a per-row rule. ``v`` is the stored value; null = blank."""
    s = rule.settings
    if rule.type == NOT_BLANK:
        if has_companion(col):          # text kept in a Number or Date column isn't blank (TXT-8, TXT-13)
            return f"({v} IS NULL AND {companion(v)} IS NULL)"
        return f"({v} IS NULL)"
    if rule.type == NUMBER_RANGE:
        if s.get("not_negative"):
            cond = f"{v} < 0"
        else:
            sc = _scale(col, s.get("min"), s.get("max"))
            x = f"CAST({v} AS DECIMAL(38,{sc}))"
            parts = []
            if s.get("min") not in (None, ""):
                parts.append(f"{x} < {_num_lit(s['min'], sc)}")
            if s.get("max") not in (None, ""):
                parts.append(f"{x} > {_num_lit(s['max'], sc)}")
            cond = " OR ".join(parts)
    elif rule.type == DATE_RANGE:
        parts = []
        if s.get("from"):
            parts.append(f"{v} < DATE {lit(meaning.parse_date(s['from']).isoformat())}")
        if s.get("to"):
            parts.append(f"{v} > DATE {lit(meaning.parse_date(s['to']).isoformat())}")
        cond = " OR ".join(parts)
    elif rule.type == ALLOWED_VALUES:
        values = list(s["values"])
        if col.type == NUMBER:
            sc = _scale(col, *values)
            items = ", ".join(_num_lit(x, sc) for x in values)
            cond = f"NOT list_contains([{items}], CAST({v} AS DECIMAL(38,{sc})))"
        else:
            items = ", ".join(f"lower({lit(x)})" for x in values)
            cond = f"NOT list_contains([{items}], lower({v}))"
    elif rule.type == TEXT_LENGTH:
        if s.get("exact") is not None:
            cond = f"length({v}) <> {int(s['exact'])}"
        else:
            parts = []
            if s.get("min") is not None:
                parts.append(f"length({v}) < {int(s['min'])}")
            if s.get("max") is not None:
                parts.append(f"length({v}) > {int(s['max'])}")
            cond = " OR ".join(parts)
    elif rule.type == PATTERN:
        cond = f"NOT regexp_full_match({v}, {lit(meaning.pattern_regex(s['pattern']))})"
    else:
        raise AssertionError(rule.type)
    return f"({v} IS NOT NULL AND ({cond}))"


def _problem(rule: Rule, v: str) -> str:
    if rule.type == TEXT_LENGTH:
        return f"('value has ' || length({v}) || ' characters; expected ' || {lit(meaning.problem(rule))})"
    return lit(meaning.problem(rule))


@dataclass
class _Plan:
    rules: list[Rule]          # the rules that run, in order; _rule = position in this list
    columns: dict[str, Column]


def _plan(columns: list[Column], rules: list[Rule]) -> _Plan:
    cols = {c.id: c for c in active(columns)}
    keep = []
    for r in rules:
        ids = r.key_columns if r.type == UNIQUE else [r.column_id]
        if all(i in cols for i in ids):
            keep.append(r)
    return _Plan(keep, cols)


def issues_sql(con, data: Path, columns: list[Column], rules: list[Rule],
               file_names: dict[int, str] | None = None) -> str:
    """The SELECT that finds every issue (columns as in ``issues.parquet``), ordered by file, row and rule."""
    plan = _plan(columns, rules)
    present = present_columns(con, data)
    items = ["_src_file", "_src_sheet", "_src_row"]
    for cid, c in plan.columns.items():
        items.append(f"{cid if cid in present else f'CAST(NULL AS {sql_type(c)})'} AS {cid}")
        if has_companion(c):
            t = companion(cid)
            items.append(f"{t if t in present else 'CAST(NULL AS VARCHAR)'} AS {t}")
    d_cols = ", ".join(items)

    found: list[str] = []
    # per-row rules
    row_rules = [(i, r) for i, r in enumerate(plan.rules) if r.type not in (IS_NUMBER, IS_DATE, UNIQUE)]
    if row_rules:
        flags = ", ".join(f"{_fails(r, plan.columns[r.column_id], r.column_id)} AS f{i}" for i, r in row_rules)
        structs = ", ".join(
            f"{{'ri': {i}, 'fail': f{i}, 'value': {_value_text(plan.columns[r.column_id], r.column_id)}, "
            f"'problem': {_problem(r, r.column_id)}}}" for i, r in row_rules)
        any_fail = " OR ".join(f"f{i}" for i, _r in row_rules)
        found.append(
            f"SELECT _src_file, _src_sheet, _src_row, x.ri AS _rule, x.value AS value, x.problem AS problem, "
            f"CAST(NULL AS BOOLEAN) AS duplicate_first FROM ("
            f"SELECT _src_file, _src_sheet, _src_row, unnest([{structs}]) AS x FROM ("
            f"SELECT *, {flags} FROM d) WHERE {any_fail}) WHERE x.fail")
    # Is a number / Is a date: the text kept in the companions (TXT-13)
    for i, r in enumerate(plan.rules):
        if r.type in (IS_NUMBER, IS_DATE) and has_companion(plan.columns[r.column_id]):
            t = companion(r.column_id)
            found.append(f"SELECT _src_file, _src_sheet, _src_row, {i} AS _rule, {t} AS value, "
                         f"{lit(meaning.problem(r))} AS problem, CAST(NULL AS BOOLEAN) AS duplicate_first "
                         f"FROM d WHERE {t} IS NOT NULL")
    # Unique within the run: every row of a duplicate group (T17); rows with a blank key column are skipped
    for i, r in enumerate(plan.rules):
        if r.type == UNIQUE:
            found.append(_unique_sql(i, r, plan, file_names or {}))

    rules_vals = ", ".join(f"({i}, {lit(r.id)}, {lit(r.type)}, {lit(r.severity)}, {lit(r.column_id)})"
                           for i, r in enumerate(plan.rules)) or "(NULL, NULL, NULL, NULL, NULL)"
    union = " UNION ALL ".join(found) if found else _EMPTY_FOUND
    return (f"WITH d AS (SELECT {d_cols} FROM read_parquet({_path(data)})), "
            f"found AS ({union}) "
            f"SELECT f._src_file, f._src_sheet, f._src_row, r.column_id, r.rule_id, r.rule_type, r.severity, "
            f"coalesce(f.value, '') AS value, f.problem, f.duplicate_first "
            f"FROM found f JOIN (VALUES {rules_vals}) r(_rule, rule_id, rule_type, severity, column_id) "
            f"USING (_rule) ORDER BY f._src_file, f._src_row, f._rule")


def _key_part(col: Column, prefix: str = "") -> str:
    """A Unique key part: the value as shown, so text kept in a Number or Date column takes part and two "NA" are
    equal (TXT-13). Numbers compare as their stored text (the column's decimals), dates as DD-MM-YYYY."""
    v = f"{prefix}{col.id}"
    if has_companion(col):
        return f"coalesce({_value_text(col, v)}, {prefix}{companion(col.id)})"
    return v


def _unique_sql(i: int, rule: Rule, plan: _Plan, file_names: dict[int, str]) -> str:
    keys = rule.key_columns
    cols = [plan.columns[k] for k in keys]
    key_names = " + ".join(c.name for c in cols)
    parts = ", ".join(f"{_key_part(c)} AS k{n}" for n, c in enumerate(cols))
    not_null = " AND ".join(f"k{n} IS NOT NULL" for n in range(len(cols)))
    on = " AND ".join(f"d.k{n} = g.k{n}" for n in range(len(cols)))
    value = " || ' + ' || ".join(f"d.k{n}" for n in range(len(cols)))
    whens = " ".join(f"WHEN {n} THEN {lit(name)}" for n, name in sorted(file_names.items()))
    file_name = f"(CASE g.m.f {whens} ELSE 'file ' || g.m.f END)" if whens else "('file ' || g.m.f)"
    first = "(d._src_file = g.m.f AND d._src_row = g.m.r)"
    problem = (f"(CASE WHEN {first} THEN 'same ' || {lit(key_names)} || ' in ' || g.n || ' rows; this is the first' "
               f"WHEN d._src_file = g.m.f THEN 'same ' || {lit(key_names)} || ' as row ' || g.m.r "
               f"ELSE 'same ' || {lit(key_names)} || ' as ' || {file_name} || "
               f"(CASE WHEN g.m.s = '' THEN '' ELSE ', ' || g.m.s END) || ', row ' || g.m.r END)")
    keyed = f"(SELECT _src_file, _src_sheet, _src_row, {parts} FROM d)"
    groups = (f"SELECT {', '.join(f'k{n}' for n in range(len(cols)))}, count(*) AS n, "
              f"min({{'f': _src_file, 'r': _src_row, 's': _src_sheet}}) AS m "
              f"FROM {keyed} WHERE {not_null} GROUP BY ALL HAVING count(*) > 1")
    return (f"SELECT d._src_file, d._src_sheet, d._src_row, {i} AS _rule, {value} AS value, {problem} AS problem, "
            f"{first} AS duplicate_first FROM {keyed} d JOIN ({groups}) g ON {on}")


# ---------------------------------------------------------------------------------------------- writing and reading
def write_issues(con, data: Path, columns: list[Column], rules: list[Rule], out: Path,
                 file_names: dict[int, str] | None = None) -> None:
    sql = issues_sql(con, data, columns, rules, file_names)
    con.execute(f"COPY ({sql}) TO {_path(out)} (FORMAT parquet)")


def _src(issues: Path) -> str:
    return f"read_parquet({_path(issues)})"


def totals(con, issues: Path) -> tuple[int, int]:
    """(errors, warnings): the number of failures at each severity."""
    row = con.execute(f"SELECT count(*) FILTER (WHERE severity = {lit(ERROR)}), "
                      f"count(*) FILTER (WHERE severity = {lit(WARNING)}) FROM {_src(issues)}").fetchone()
    return int(row[0]), int(row[1])


def rule_counts(con, issues: Path) -> dict[str, int]:
    """Failures per rule ID (ISS-1)."""
    return {r[0]: int(r[1]) for r in con.execute(
        f"SELECT rule_id, count(*) FROM {_src(issues)} GROUP BY rule_id").fetchall()}


def rule_lines(con, issues: Path) -> list[tuple]:
    """Failures per rule as stored (ISS-1, the Run screen's by-rule table): (rule ID, rule type, column ID,
    severity, count), in rule ID order."""
    return [tuple(r) for r in con.execute(
        f"SELECT rule_id, any_value(rule_type), any_value(column_id), any_value(severity), count(*) "
        f"FROM {_src(issues)} GROUP BY rule_id ORDER BY rule_id").fetchall()]


def issue_counts(con, issues: Path) -> list[IssueCount]:
    """Errors and warnings per rule and per file and sheet, for ``run_issue_count`` (ISS-1)."""
    rows = con.execute(
        f"SELECT rule_id, _src_file, _src_sheet, count(*) FILTER (WHERE severity = {lit(ERROR)}), "
        f"count(*) FILTER (WHERE severity = {lit(WARNING)}) FROM {_src(issues)} "
        f"GROUP BY ALL ORDER BY _src_file, rule_id").fetchall()
    return [IssueCount(r[0], int(r[1]), r[2], int(r[3]), int(r[4])) for r in rows]


def left_out_rows(con, issues: Path) -> int:
    """Rows that Continue despite errors leaves out (T18): every row with an Error-level issue, except that the
    first row of a duplicate group is kept unless it has another error."""
    return int(con.execute(
        f"SELECT count(*) FROM (SELECT DISTINCT _src_file, _src_row FROM {_src(issues)} "
        f"WHERE severity = {lit(ERROR)} AND NOT coalesce(duplicate_first, false))").fetchone()[0])


SORTABLE = {"file": "_src_file", "sheet": "_src_sheet", "row": "_src_row", "column": "column_id",
            "value": "value", "rule": "rule_id", "severity": "severity"}


def _grid_where(rule_id, severity, column_id) -> str:
    conds = []
    if rule_id is not None:
        conds.append(f"rule_id = {lit(rule_id)}")
    if severity is not None:
        conds.append(f"severity = {lit(severity)}")
    if column_id is not None:
        conds.append(f"column_id = {lit(column_id)}")
    return ("WHERE " + " AND ".join(conds)) if conds else ""


def _grid_rows(issues: Path, per_rule: int) -> str:
    """The issues the grid holds: up to ``per_rule`` per rule, ordered by file, sheet and row (ISS-2)."""
    return (f"(SELECT * FROM {_src(issues)} QUALIFY row_number() OVER "
            f"(PARTITION BY rule_id ORDER BY _src_file, _src_row) <= {int(per_rule)})")


def grid_count(con, issues: Path, *, rule_id=None, severity=None, column_id=None,
               per_rule: int = GRID_PER_RULE) -> int:
    return int(con.execute(f"SELECT count(*) FROM {_grid_rows(issues, per_rule)} "
                           f"{_grid_where(rule_id, severity, column_id)}").fetchone()[0])


def grid_page(con, issues: Path, *, offset: int = 0, limit: int = 500, rule_id=None, severity=None,
              column_id=None, sort: str | None = None, descending: bool = False,
              per_rule: int = GRID_PER_RULE) -> list[tuple]:
    """One page of the issue grid, as tuples in ``ISSUE_COLUMNS`` order. Filter and sort work within the rows the
    grid holds. ``sort`` is a key of ``SORTABLE``; ties keep file, sheet and row order."""
    order = "_src_file, _src_row, rule_id"
    if sort is not None:
        order = f"{SORTABLE[sort]} {'DESC' if descending else 'ASC'}, " + order
    return [tuple(r) for r in con.execute(
        f"SELECT {', '.join(ISSUE_COLUMNS)} FROM {_grid_rows(issues, per_rule)} "
        f"{_grid_where(rule_id, severity, column_id)} ORDER BY {order} "
        f"LIMIT {int(limit)} OFFSET {int(offset)}").fetchall()]


def read_issues(con, issues: Path) -> list[tuple]:
    """Every issue, in file order (tests and export)."""
    return [tuple(r) for r in con.execute(f"SELECT {', '.join(ISSUE_COLUMNS)} FROM {_src(issues)}").fetchall()]


def dry_run(con, data: Path, columns: list[Column], rules: list[Rule],
            keep: int = SHOW_FIRST, file_names: dict[int, str] | None = None
            ) -> tuple[dict[str, int], dict[str, list[tuple]]]:
    """Failure counts per rule and the first ``keep`` failing issues per rule (VR-8), without writing anything.
    ``keep=0`` returns counts only."""
    sql = issues_sql(con, data, columns, rules, file_names)
    counts = {r.id: 0 for r in _plan(columns, rules).rules}
    first: dict[str, list[tuple]] = {rid: [] for rid in counts}
    if keep <= 0:
        for rid, n in con.execute(f"SELECT rule_id, count(*) FROM ({sql}) GROUP BY rule_id").fetchall():
            counts[rid] = int(n)
        return counts, first
    rows = con.execute(
        f"SELECT {', '.join(ISSUE_COLUMNS)}, count(*) OVER (PARTITION BY rule_id) AS n FROM ({sql}) "
        f"QUALIFY row_number() OVER (PARTITION BY rule_id ORDER BY _src_file, _src_row) <= {int(keep)} "
        f"ORDER BY _src_file, _src_row").fetchall()
    for r in rows:
        counts[r[4]] = int(r[-1])
        first[r[4]].append(tuple(r[:-1]))
    return counts, first
