r"""The totals check (RUN-6, T20): Input = Loaded + Left out for every column ticked for it, all in DuckDB.

- Input: the raw staged text (``_staging\<id>\raw\``), converted with the column's Number rule and rounded per value
  to its decimal places; values that can't be read count as 0. Hidden rows were never staged, so they are in no
  total; blank rows convert to nothing.
- Loaded: ``data.parquet`` read back from disk.
- Left out: ``left_out.parquet`` (0 when there is none).

The check passes only when Input = Loaded + Left out exactly; there is no override.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sankalan.model.template import NUMBER, Column
from sankalan.query.convert import RawPart, _path, number_sql, read_raw_sql, value_name


@dataclass
class TotalsLine:
    column_id: str
    name: str
    decimals: int
    input: Decimal
    loaded: Decimal
    left_out: Decimal

    @property
    def passed(self) -> bool:
        return self.input == self.loaded + self.left_out

    def to_dict(self) -> dict:
        q = Decimal(1).scaleb(-self.decimals)
        return {"name": self.name, "decimals": self.decimals, "input": str(self.input.quantize(q)),
                "loaded": str(self.loaded.quantize(q)), "left_out": str(self.left_out.quantize(q)),
                "passed": self.passed}


def ticked(columns: list[Column]) -> list[Column]:
    """Active Number columns ticked for the totals check."""
    return [c for c in columns if c.totals_check and not c.removed and c.type == NUMBER]


def _zero(col: Column) -> str:
    return f"CAST(0 AS DECIMAL(38,{col.decimals}))"


def input_totals(con, parts: list[RawPart], columns: list[Column]) -> dict[str, Decimal]:
    """Per ticked column: the sum of the raw staged text, each value converted and rounded, unreadable = 0."""
    cols = ticked(columns)
    if not cols:
        return {}
    selects = []
    for p in parts:
        items = []
        for c in cols:
            pos = p.mapping.get(c.id)
            if pos is None or pos >= p.width:
                items.append(f"{_zero(c)} AS {c.id}")
            else:
                items.append(f"coalesce(CAST({number_sql(value_name(pos), c.decimals)} AS DECIMAL(38,{c.decimals})),"
                             f" {_zero(c)}) AS {c.id}")
        selects.append(f"SELECT {', '.join(items)} FROM {read_raw_sql(p)}")
    sums = ", ".join(f"coalesce(sum({c.id}), {_zero(c)})" for c in cols)
    row = con.execute(f"SELECT {sums} FROM ({' UNION ALL '.join(selects)})").fetchone()
    return {c.id: Decimal(row[i]) for i, c in enumerate(cols)}


def file_totals(con, path: Path, columns: list[Column]) -> dict[str, Decimal]:
    """Per ticked column: the sum in a Parquet file of the run (nulls count as 0); 0 when the file is missing."""
    cols = ticked(columns)
    if not cols:
        return {}
    if not Path(path).is_file():
        return {c.id: Decimal(0) for c in cols}
    sums = ", ".join(f"coalesce(sum({c.id}), {_zero(c)})" for c in cols)
    row = con.execute(f"SELECT {sums} FROM read_parquet({_path(path)})").fetchone()
    return {c.id: Decimal(row[i]) for i, c in enumerate(cols)}


def check(con, parts: list[RawPart], columns: list[Column], data: Path, left_out: Path,
          fault: dict[str, Decimal] | None = None) -> list[TotalsLine]:
    """The totals check lines, in column order. ``fault`` (test builds only, RUNC-10) adds an amount to Loaded."""
    inp = input_totals(con, parts, columns)
    loaded = file_totals(con, data, columns)
    left = file_totals(con, left_out, columns)
    fault = fault or {}
    return [TotalsLine(c.id, c.name, c.decimals, inp[c.id], loaded[c.id] + Decimal(fault.get(c.id, 0)), left[c.id])
            for c in ticked(columns)]
