"""Issues as people read them (ISS-2, ISS-3, UI-6, NF-5).

A message names the file, sheet, row and column, then the problem:
"Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number". A CSV file has no sheet, so its
message leaves the sheet out. Row numbers use international grouping (UI-7).
"""
from __future__ import annotations

from dataclasses import dataclass

from sankalan.model.rule import RULE_NAMES


def message(file_name: str, sheet: str, row: int, column_name: str, problem: str) -> str:
    where = f"{file_name}, {sheet}" if sheet else file_name
    return f"{where}, row {int(row):,}, {column_name}: {problem}"


@dataclass(frozen=True)
class Issue:
    """One issue as the grid and the export show it: File, Sheet, Row, Column, Value, Rule, Severity, Message."""
    file: str
    sheet: str
    row: int
    column: str
    value: str
    rule: str
    severity: str
    message: str
    rule_id: str
    column_id: str


def from_row(row: tuple, file_names: dict[int, str], column_names: dict[str, str]) -> Issue:
    """An ``issues.parquet`` row (``query.validate.ISSUE_COLUMNS`` order) with names filled in."""
    src_file, sheet, src_row, column_id, rule_id, rule_type, severity, value, problem = row[:9]
    file_name = file_names.get(src_file, f"file {src_file}")
    column = column_names.get(column_id, column_id)
    return Issue(file_name, sheet, int(src_row), column, value, RULE_NAMES[rule_type], severity,
                 message(file_name, sheet, src_row, column, problem), rule_id, column_id)
