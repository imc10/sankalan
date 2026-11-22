"""Text values in Number and Date columns (Tech spec A2 5.7, T56; Feature Spec A2 TXT-1, NCK-8, NCK-9).

A Number or Date cell that isn't blank and doesn't convert keeps its text in the column's companion ``cNNN_t``
(``query/convert.py``). ``text_counts`` counts them per column in one scan that reads the companions only: for
``run.text_counts`` at commit, the Load step and the 2.4b panel. ``text_values`` is the values list of a run without
checks (NCK-8).
"""
from __future__ import annotations

from pathlib import Path

from sankalan.model.template import Column, typed
from sankalan.query.convert import _path, companion

VALUES_LIMIT = 1000             # NCK-8: at most 1,000 values listed


def text_counts(con, data: Path, columns: list[Column]) -> dict[str, int]:
    """Column ID → text values in ``data`` (a ``data.parquet``), for every active Number and Date column. A column
    the file doesn't have (added after the run) counts 0."""
    cols = typed(columns)
    if not cols:
        return {}
    present = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet({_path(data)})").fetchall()}
    have = [c for c in cols if companion(c.id) in present]
    out = {c.id: 0 for c in cols}
    if have:
        row = con.execute(f"SELECT {', '.join(f'count({companion(c.id)})' for c in have)} "
                          f"FROM read_parquet({_path(data)})").fetchone()
        out.update({c.id: int(n) for c, n in zip(have, row)})
    return out


def text_values(con, data: Path, column_id: str, limit: int = VALUES_LIMIT) -> list[tuple]:
    """The text values of one column (NCK-8): (text, count, file index, sheet, row) for each different value as
    typed, most frequent first, then by text, at most ``limit``. File, sheet and row are where it first appears in
    stored order (file, then row), taken in the same scan with ``arg_min``."""
    col = companion(column_id)
    present = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet({_path(data)})").fetchall()}
    if col not in present:
        return []
    rows = con.execute(f"""
        SELECT {col}, count(*) AS n, arg_min(_src_file, (_src_file, _src_row)) AS f,
               arg_min(_src_sheet, (_src_file, _src_row)) AS sheet, arg_min(_src_row, (_src_file, _src_row)) AS r
        FROM read_parquet({_path(data)}) WHERE {col} IS NOT NULL
        GROUP BY {col} ORDER BY n DESC, {col} LIMIT {int(limit)}""").fetchall()
    return [(t, int(n), int(f), sheet, int(r)) for t, n, f, sheet, r in rows]
