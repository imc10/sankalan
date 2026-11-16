"""Leaving the Validate step: the rows to load and the rows left out (Tech spec, Outputs → Leaving the Validate step;
RUN-4, T18, T19).

Rows with an Error-level issue are left out; in a duplicate group (Unique within the run) the first occurrence is
kept unless it has another error. Warnings never leave a row out.

``left_out.parquet`` holds the left-out rows with every ``data.parquet`` column plus ``_reason``: the IDs of the
Error rules that caused it, comma-separated in rule order (e.g. ``r2,c006.type``). The export turns them into
"Column: Rule" text. ``left_out.parquet`` is always written (empty when nothing is left out); ``data.parquet`` is
rewritten only when something is.
"""
from __future__ import annotations

import os
from pathlib import Path

from sankalan.model.rule import ERROR
from sankalan.query.convert import DATA, _path, lit

LEFT_OUT = "left_out.parquet"


def _reasons(issues: Path, rule_order: list[str]) -> str:
    rank = " ".join(f"WHEN {lit(r)} THEN {i}" for i, r in enumerate(rule_order)) or "WHEN NULL THEN 0"
    return (f"SELECT _src_file, _src_row, string_agg(rule_id, ',' ORDER BY "
            f"(CASE rule_id {rank} ELSE {len(rule_order)} END), rule_id) AS _reason "
            f"FROM read_parquet({_path(issues)}) "
            f"WHERE severity = {lit(ERROR)} AND NOT coalesce(duplicate_first, false) GROUP BY ALL")


def split(con, folder: Path, issues: Path, rule_order: list[str]) -> tuple[int, int]:
    """Split ``folder``'s ``data.parquet`` by ``issues``: (rows loaded, rows left out). Writes through ``.part``
    files and renames, so a cancel leaves the staged rows as they were. Run it once per scan: after a split,
    ``data.parquet`` no longer holds the left-out rows."""
    folder = Path(folder)
    data = folder / DATA
    left = folder / LEFT_OUT
    reasons = _reasons(issues, rule_order)
    left_part = left.with_name(left.name + ".part")
    con.execute(f"COPY (SELECT d.*, x._reason FROM read_parquet({_path(data)}) d JOIN ({reasons}) x "
                f"USING (_src_file, _src_row) ORDER BY d._src_file, d._src_row) TO {_path(left_part)} "
                f"(FORMAT parquet)")
    left_n = int(con.execute(f"SELECT count(*) FROM read_parquet({_path(left_part)})").fetchone()[0])
    total = int(con.execute(f"SELECT count(*) FROM read_parquet({_path(data)})").fetchone()[0])
    if left_n:
        data_part = data.with_name(data.name + ".part")
        con.execute(f"COPY (SELECT d.* FROM read_parquet({_path(data)}) d ANTI JOIN ({reasons}) x "
                    f"USING (_src_file, _src_row) ORDER BY d._src_file, d._src_row) TO {_path(data_part)} "
                    f"(FORMAT parquet)")
    os.replace(left_part, left)              # left-out rows first: until data.parquet is replaced, a rerun is safe
    if left_n:
        os.replace(data_part, data)
    return total - left_n, left_n
