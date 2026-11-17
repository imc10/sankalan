"""Type detection on the New template wizard's sample (TPL-3, MAP-10; C3-09, C3-11).

One scan over the sample's raw staged text counts, per source column: values that aren't blank (T14), values the
Number rule reads, values with a leading zero (codes such as 00123 stay Text, MAP-9), values shaped like an Excel /
ISO date or a DD-MM-YYYY or DD/MM/YYYY text date, and values each Date rule reads. The same SQL rules as the
convert stage are used, so the % note says what a run would make of the column.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sankalan.ingest import values as rules
from sankalan.ingest.canonical import value_name
from sankalan.model.template import DATE_FORMATS
from sankalan.query.convert import RawPart, blank_sql, date_sql, lit, number_sql, read_raw_sql

SAMPLE_VALUES = 2
SAMPLE_SCAN_ROWS = 200


@dataclass
class Profile:
    """Counts for one source column over the sample rows."""
    total: int = 0
    filled: int = 0
    numbers: int = 0
    leading_zero: int = 0
    iso_shaped: int = 0                                     # Excel dates (staged as ISO) and ISO text
    shaped: dict[str, int] = field(default_factory=dict)    # date format -> values shaped like it
    dates: dict[str | None, int] = field(default_factory=dict)   # date format (None = Excel dates) -> readable
    samples: list[str] = field(default_factory=list)        # the first distinct values that aren't blank


def _part_select(part: RawPart, positions: list[int | None]) -> str:
    items = [(value_name(p) if p is not None and p < part.width else "CAST(NULL AS VARCHAR)") + f" AS s{i}"
             for i, p in enumerate(positions)]
    return f"SELECT {', '.join(items) or 'NULL AS s0'} FROM {read_raw_sql(part)}"


def _union(parts: list[RawPart], positions: list[list[int | None]]) -> str:
    """``positions[i][k]``: source column k's position in part i (None = not in that sheet)."""
    return " UNION ALL ".join(_part_select(p, pos) for p, pos in zip(parts, positions))


def profile(con, parts: list[RawPart], positions: list[list[int | None]], n_columns: int) -> list[Profile]:
    if not parts or n_columns == 0:
        return [Profile() for _ in range(n_columns)]
    date_part = "regexp_extract(trim({v}, ' '), " + lit(rules.DATE_PART_PATTERN) + ", 1)"
    aggs = ["count(*)"]
    for k in range(n_columns):
        v = f"s{k}"
        filled = f"NOT {blank_sql(v)}"
        part = date_part.replace("{v}", v)
        aggs += [f"count_if({filled})",
                 f"count_if({number_sql(v, 6)} IS NOT NULL)",
                 f"count_if(regexp_full_match(trim({v}, ' '), '0[0-9]+'))",
                 f"count_if({filled} AND regexp_matches({part}, {lit(rules.ISO_PATTERN)}))"]
        for f in DATE_FORMATS:
            aggs.append(f"count_if({filled} AND regexp_matches({part}, {lit(rules.DATE_TEXT_FORMATS[f][0])}))")
        for f in (None,) + DATE_FORMATS:
            aggs.append(f"count_if({date_sql(v, f)} IS NOT NULL)")
    union = _union(parts, positions)
    row = con.execute(f"SELECT {', '.join(aggs)} FROM ({union})").fetchone()
    total = int(row[0])
    per = 5 + 2 * len(DATE_FORMATS)         # filled, numbers, leading zero, ISO, shaped per format, readable x3
    out = []
    for k in range(n_columns):
        r = [int(x or 0) for x in row[1 + k * per: 1 + (k + 1) * per]]
        p = Profile(total, r[0], r[1], r[2], r[3])
        nf = len(DATE_FORMATS)
        p.shaped = {f: r[4 + i] for i, f in enumerate(DATE_FORMATS)}
        p.dates = {f: r[4 + nf + i] for i, f in enumerate((None,) + DATE_FORMATS)}
        out.append(p)
    first = con.execute(f"SELECT * FROM ({union}) LIMIT {SAMPLE_SCAN_ROWS}").fetchall()
    for k, p in enumerate(out):
        for r in first:
            v = r[k]
            if v is None or not v.strip(" ") or v in p.samples:
                continue
            p.samples.append(v)
            if len(p.samples) >= SAMPLE_VALUES:
                break
    return out
