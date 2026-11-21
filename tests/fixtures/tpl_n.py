"""TPL-N: the A2 test set without checks (Feature Spec A2 10.1; plan A2-2 → Test data; figures confirmed 21-11-2026).

TPL-R's 20 columns, Check data before loading = No, two CSV files.

| Figure                                   | small (normal suite) | full (slow) |
| ---------------------------------------- | -------------------- | ----------- |
| Data rows per file                       | 5,000                | 500,000     |
| Rows repeated exactly (file 2 repeats 1) | 20                   | 2,000       |
| Taxable Value text values                | 68                   | 6,802       |
| Invoice Date text values                 | 12                   | 120         |
| Blank rows (dropped, "Blank rows skipped")| 3                    | 10          |

"Data rows per file" excludes the blank rows, which are extra lines in the files (file 1 has the first half of
them, file 2 the rest), so Rows read = 2 × data rows + blank rows and Rows loaded = 2 × data rows (T45).

The repeated rows are the first rows of file 2: exact copies of rows of file 1 that hold no text value. Taxable
Value text is spread over both files with several different values (so the values list has an order to check),
including one with spaces around it, which is kept as typed (T14).

``generate(out, size)`` writes the files and a manifest of figures computed in Python from the written values (the
oracle); ``verify(out, manifest)`` reads the files back with the csv module and checks the planted counts.
Deterministic: the same size gives the same bytes.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

import tpl_r

SMALL, FULL = tpl_r.SMALL, tpl_r.FULL
ROWS_PER_FILE = {SMALL: 5_000, FULL: 500_000}
REPEATED = {SMALL: 20, FULL: 2_000}
BLANK_ROWS = {SMALL: 3, FULL: 10}
TAXABLE_TEXT = {SMALL: [("NA", 40), ("Nil", 20), ("-", 5), ("12,000/-", 2), (" NA ", 1)],
                FULL: [("NA", 4_000), ("Nil", 2_000), ("-", 790), ("12,000/-", 10), (" NA ", 2)]}
DATE_TEXT = {SMALL: [("NA", 8), ("31-02-2026", 4)], FULL: [("NA", 100), ("31-02-2026", 20)]}
FILES = ("TPLN_Purchases_Part1.csv", "TPLN_Purchases_Part2.csv")
TAXABLE, DATE_ = tpl_r.TAXABLE, tpl_r.DATE_


@dataclass
class TextValue:
    text: str
    count: int
    file_index: int         # where it first appears (stored order: file, then row)
    row: int                # sheet row number: the header is row 1


@dataclass
class Manifest:
    size: str
    files: list
    rows_read: int                  # data rows + blank rows
    rows_loaded: int
    blank_rows: int
    repeated: int
    taxable_text: list = field(default_factory=list)        # TextValue dicts, most frequent first, then text
    date_text: list = field(default_factory=list)
    taxable_sum: str = "0"

    @property
    def taxable_text_count(self) -> int:
        return sum(t["count"] for t in self.taxable_text)

    @property
    def date_text_count(self) -> int:
        return sum(t["count"] for t in self.date_text)


def _ordered(found: dict) -> list[dict]:
    """text -> [count, file, row] as the values list orders them: most frequent first, then by text."""
    return [asdict(TextValue(t, v[0], v[1], v[2])) for t, v in sorted(found.items(), key=lambda kv: (-kv[1][0],
                                                                                                    kv[0]))]


def _plan(size: str) -> dict:
    """(file index, data row number) → (column id, text); and the data rows that blank lines follow."""
    rows = ROWS_PER_FILE[size]
    planted = {}
    tv = [t for t, k in TAXABLE_TEXT[size] for _ in range(k)]
    for k, text in enumerate(tv):          # alternate files so each value appears in both
        f = k % 2
        n = 101 + (k // 2) * ((rows - 200) // (len(tv) // 2 + 1))
        while tpl_r.blank_cell(n, 6) or (f, n) in planted or (f == 1 and n <= REPEATED[size]):
            n += 1                          # file 2's first rows are the repeated ones: no text planted there
        planted[(f, n)] = (TAXABLE, text)
    dv = [t for t, k in DATE_TEXT[size] for _ in range(k)]
    for k, text in enumerate(dv):
        f = k % 2
        n = 157 + (k // 2) * ((rows - 300) // (len(dv) // 2 + 1))
        while tpl_r.blank_cell(n, 2) or (f, n) in planted or (f == 1 and n <= REPEATED[size]):
            n += 1
        planted[(f, n)] = (DATE_, text)
    blanks = BLANK_ROWS[size]
    first = (blanks + 1) // 2
    after = {0: [rows // (first + 1) * (k + 1) for k in range(first)],
             1: [rows // (blanks - first + 1) * (k + 1) for k in range(blanks - first)]}
    src, n = [], 1000
    while len(src) < REPEATED[size]:            # rows of file 1 that hold no text value
        if (0, n) not in planted:
            src.append(n)
        n += 1
    return {"text": planted, "blank_after": after, "repeat_src": src}


def _values(f: int, n: int, size: str, planted: dict) -> dict:
    """Column ID → value of data row n (1-based) of file f. File 2's first REPEATED rows copy rows of file 1 from
    row 1000 on that hold no text value."""
    if f == 1 and n <= REPEATED[size]:
        return _values(0, planted["repeat_src"][n - 1], size, planted)
    v = tpl_r.row_values(1, n + f * ROWS_PER_FILE[size], {"text": {1: {}, 2: {}, 3: {}}, "bad_invoice": set()})
    v.pop("c021", None)
    v["c001"] = f"PUR-{f + 1}{n:07d}"
    if (f, n) in planted["text"]:
        cid, text = planted["text"][(f, n)]
        v[cid] = text
    return v


def generate(out: Path, size: str = SMALL) -> Manifest:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    plan = _plan(size)
    ids = [c[0] for c in tpl_r.COLUMNS]
    taxable, dates = {}, {}
    tsum = Decimal(0)
    seen_rows = Counter()
    blanks = 0
    for f, name in enumerate(FILES):
        with open(out / name, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(tpl_r.NAMES)
            line = 1                                    # the header is line 1
            for n in range(1, ROWS_PER_FILE[size] + 1):
                v = _values(f, n, size, plan)
                line += 1
                w.writerow([tpl_r._csv_cell(v[cid], crlf=False) for cid in ids])
                seen_rows[tuple(str(v[c]) for c in ids)] += 1
                for cid, found in ((TAXABLE, taxable), (DATE_, dates)):
                    x = v[cid]
                    if isinstance(x, str):
                        rec = found.setdefault(x, [0, f, line])
                        rec[0] += 1
                if isinstance(v[TAXABLE], Decimal):
                    tsum += v[TAXABLE]
                if n in plan["blank_after"][f]:
                    w.writerow([""] * len(ids))
                    line += 1
                    blanks += 1
    loaded = 2 * ROWS_PER_FILE[size]
    m = Manifest(size, list(FILES), loaded + blanks, loaded, blanks, sum(k - 1 for k in seen_rows.values()),
                 _ordered(taxable), _ordered(dates), str(tsum))
    (out / f"tpl_n_{size}.json").write_text(json.dumps(asdict(m), indent=1), encoding="utf-8")
    return m


def load_manifest(out: Path, size: str = SMALL) -> Manifest:
    return Manifest(**json.loads((Path(out) / f"tpl_n_{size}.json").read_text(encoding="utf-8")))


def verify(out: Path, m: Manifest) -> None:
    """The planted figures, read back with the csv module. Raises AssertionError on any difference."""
    out = Path(out)
    rows, blanks = 0, 0
    taxable, dates, seen = Counter(), Counter(), Counter()
    for name in m.files:
        with open(out / name, encoding="utf-8", newline="") as f:
            table = list(csv.reader(f))
        head = table[0]
        assert head == tpl_r.NAMES, head
        ti, di = head.index("Taxable Value"), head.index("Invoice Date")
        for rec in table[1:]:
            if not any(c.strip() for c in rec):
                blanks += 1
                continue
            rows += 1
            seen[tuple(rec)] += 1
            if rec[ti] and not tpl_r._is_num(rec[ti]):
                taxable[rec[ti]] += 1
            if rec[di] in ("NA", "31-02-2026"):
                dates[rec[di]] += 1
    assert rows == m.rows_loaded == 2 * ROWS_PER_FILE[m.size], rows
    assert blanks == m.blank_rows == BLANK_ROWS[m.size], blanks
    assert sum(k - 1 for k in seen.values()) == m.repeated == REPEATED[m.size]
    assert dict(taxable) == {t: k for t, k in TAXABLE_TEXT[m.size]} == {t["text"]: t["count"] for t in m.taxable_text}
    assert dict(dates) == {t: k for t, k in DATE_TEXT[m.size]} == {t["text"]: t["count"] for t in m.date_text}
    want = {SMALL: (68, 12), FULL: (6_802, 120)}[m.size]
    assert (m.taxable_text_count, m.date_text_count) == want


def template(client_id: str):
    """TPL-N as a ``Template``: TPL-R's columns, no user rules, Check data before loading = No, all visible sheets,
    one default output "Taxable by State"."""
    from sankalan.model import definition as d
    from sankalan.model.definition import Definition, Group, FlatMeasure, cards
    from sankalan.model.template import Column, DefaultOutput, SourceSettings, Template
    cols = [Column(i, name, typ, dec, fmt, totals_check=tot) for i, name, typ, dec, fmt, tot in tpl_r.COLUMNS]
    do1 = Definition("", [], [Group("c005")], cards(FlatMeasure(d.ROWS, d.COUNT), FlatMeasure("c006", d.SUM)))
    return Template("", client_id, "Purchase Register N", SourceSettings(sheets="all"), cols, [],
                    [DefaultOutput("Taxable by State", do1.to_dict())],
                    {"pattern": "{Client}_{Template}_{RunID}_{Output}", "delimiter": ",", "encoding": "utf-8-sig"},
                    checks=False)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Build TPL-N")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "_generated" / "tpl_n")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args(argv)
    size = FULL if a.full else SMALL
    m = generate(a.out / size, size)
    verify(a.out / size, m)
    print(f"TPL-N {size}: {m.rows_loaded:,} rows, files in {a.out / size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
