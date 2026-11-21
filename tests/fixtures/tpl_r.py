"""TPL-R: the A2 test set with checks (Feature Spec A2 10.1; plan A2-1 → Test data; figures confirmed 21-11-2026).

20 template columns: 8 Text, 8 Number (2 decimals), 4 Date. Three runs R-0001…R-0003, each one .xlsx with two
sheets plus one or more CSV files, so stored order crosses files and sheets and Source Sheet is blank for CSV rows.

| Figure                                             | small (normal suite) | full (slow / perf) |
| -------------------------------------------------- | -------------------- | ------------------ |
| Rows per run                                       | 2,500                | 2,500,000          |
| R-0001 Taxable Value text "NA" / "Nil" / "12,000/-"| 10 / 5 / 1 (16)      | 1,000 / 500 / 10   |
| R-0002 Invoice Date text "NA" / "31-02-2026"       | 3 / 2 (5)            | 300 / 5            |
| R-0002 rows left out (Character pattern, override) | 63                   | 63                 |
| R-0003 rows from a file without Invoice No (MAP-6) | 400                  | 400,000            |
| Rows searched, all three runs (ROW-10)             | 7,437                | 7,499,937          |

R-0002's files add the column Place of Supply (21 columns in all); R-0003's files have it too. About 1% of cells are
blank, except Invoice No. Narration values contain commas, double quotes and line breaks (``\\n`` in the workbook,
``\\r\\n`` and ``\\n`` in the CSV files). Is a number on Taxable Value and Is a date on Invoice Date are Warnings, so
text rows load; the one Error rule (Character pattern on Invoice No) leaves out R-0002's 63 rows on override.

``generate(out, size)`` writes the files and returns a ``Manifest`` of figures computed from the generated values in
Python (the independent oracle the tests compare SQL against); ``verify(out, manifest)`` reads the files back the way
the app does (python-calamine, the csv module) and checks the planted counts.

Development only (XlsxWriter). Deterministic: the same size gives the same bytes.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SMALL, FULL = "small", "full"

COLUMNS = [  # (id, name, type, decimals, date_format, totals_check)
    ("c001", "Invoice No", "Text", None, None, False),
    ("c002", "Invoice Date", "Date", None, "DD-MM-YYYY", False),
    ("c003", "Customer", "Text", None, None, False),
    ("c004", "GSTIN", "Text", None, None, False),
    ("c005", "State", "Text", None, None, False),
    ("c006", "Taxable Value", "Number", 2, None, True),
    ("c007", "CGST", "Number", 2, None, False),
    ("c008", "SGST", "Number", 2, None, False),
    ("c009", "IGST", "Number", 2, None, False),
    ("c010", "Cess", "Number", 2, None, False),
    ("c011", "Discount", "Number", 2, None, False),
    ("c012", "Freight", "Number", 2, None, False),
    ("c013", "Invoice Value", "Number", 2, None, True),
    ("c014", "Due Date", "Date", None, "DD-MM-YYYY", False),
    ("c015", "Dispatch Date", "Date", None, "DD-MM-YYYY", False),
    ("c016", "Payment Date", "Date", None, "DD-MM-YYYY", False),
    ("c017", "Branch", "Text", None, None, False),
    ("c018", "HSN Code", "Text", None, None, False),
    ("c019", "Salesperson", "Text", None, None, False),
    ("c020", "Narration", "Text", None, None, False),
]
PLACE = "Place of Supply"          # added in R-0002 (c021)
NAMES = [c[1] for c in COLUMNS]
INV, DATE_, TAXABLE = "c001", "c002", "c006"
PATTERN = "INV-99999999"           # Character pattern on Invoice No (Error)

CUSTOMERS = ["Shree Ganesh Traders", "Patel Agencies", "Mehta & Sons", "Kaveri Distributors", "Sai Enterprises",
             "Laxmi Stores", "Om Sai Wholesale", "Krishna Retail", "Annapurna Foods", "Ganga Suppliers"]
STATES = ["Maharashtra", "Gujarat", "Karnataka", "Delhi"]
BRANCHES = ["Pune", "Nashik", "Nagpur"]
PEOPLE = ["Asha", "Ravi", "Meera", "Kiran", "Sunil", "Farah"]
RATES = [0, 5, 12, 18, 28]
D2 = Decimal("0.01")
MONTH = {1: (2026, 10), 2: (2026, 11), 3: (2026, 12)}

# files per run: ("xlsx", [(sheet, rows), (sheet, rows)]) or ("csv", rows) or ("csv-no-inv", rows)
LAYOUT = {
    SMALL: {1: [("xlsx", [("Sales A", 900), ("Sales B", 600)]), ("csv", 1000)],
            2: [("xlsx", [("Sales A", 900), ("Sales B", 600)]), ("csv", 500), ("csv", 500)],
            3: [("xlsx", [("Sales A", 900), ("Sales B", 700)]), ("csv", 500), ("csv-no-inv", 400)]},
    FULL: {1: [("xlsx", [("Sales A", 60_000), ("Sales B", 40_000)]), ("csv", 2_400_000)],
           2: [("xlsx", [("Sales A", 60_000), ("Sales B", 40_000)]), ("csv", 1_200_000), ("csv", 1_200_000)],
           3: [("xlsx", [("Sales A", 60_000), ("Sales B", 40_000)]), ("csv", 2_000_000),
               ("csv-no-inv", 400_000)]},
}
TAXABLE_TEXT = {SMALL: [("NA", 10), ("Nil", 5), ("12,000/-", 1)], FULL: [("NA", 1000), ("Nil", 500), ("12,000/-", 10)]}
DATE_TEXT = {SMALL: [("NA", 3), ("31-02-2026", 2)], FULL: [("NA", 300), ("31-02-2026", 5)]}
LEFT_OUT = 63
ROWS_PER_RUN = {SMALL: 2_500, FULL: 2_500_000}


def r2(x: Decimal) -> Decimal:
    return x.quantize(D2, rounding=ROUND_HALF_UP)


def blank_cell(n: int, j: int) -> bool:
    """About 1% of the cells of column j (1-based position, Invoice No never)."""
    return j > 1 and (n * 31 + j * 17) % 100 == 0


def spread(rows: int, count: int, offset: int) -> list[int]:
    """``count`` row numbers spread over 1..rows."""
    step = rows // (count + 1)
    return [offset + step * (k + 1) for k in range(count)]


def _planted(size: str) -> dict:
    """Run number → {row number: (column id, text)} and the rows with a bad Invoice No."""
    rows = ROWS_PER_RUN[size]
    out = {1: {}, 2: {}, 3: {}}
    tv = [t for t, k in TAXABLE_TEXT[size] for _ in range(k)]
    for n, text in zip(spread(rows, len(tv), 7), tv):
        while blank_cell(n, 6):
            n += 1
        out[1][n] = (TAXABLE, text)
    dv = [t for t, k in DATE_TEXT[size] for _ in range(k)]
    for n, text in zip(spread(rows, len(dv), 11), dv):
        while blank_cell(n, 2):
            n += 1
        out[2][n] = (DATE_, text)
    bad = set()
    for n in spread(rows, LEFT_OUT, 3):
        while n in out[2] or n in bad:
            n += 1
        bad.add(n)
    return {"text": out, "bad_invoice": bad}


@dataclass
class RunFigures:
    """Figures over a run's loaded rows (R-0002 without its 63 left-out rows), from the generated Python values."""
    rows_read: int = 0
    rows_loaded: int = 0
    left_out: int = 0
    taxable_text: dict = field(default_factory=dict)        # text -> count
    date_text: dict = field(default_factory=dict)
    taxable_count: int = 0                                  # numeric cells
    taxable_sum: str = "0"
    taxable_min: str | None = None
    taxable_max: str | None = None
    taxable_blank: int = 0
    invoice_value_sum: str = "0"
    date_count: int = 0                                     # real dates
    date_min: str | None = None
    date_max: str | None = None
    date_distinct: int = 0
    date_blank: int = 0
    no_invoice_no: int = 0
    files: list = field(default_factory=list)               # file names in load order


@dataclass
class Manifest:
    size: str
    runs: dict                                              # "1" / "2" / "3" -> RunFigures as dict
    files: dict                                             # "1" -> [file names]

    def run(self, k: int) -> RunFigures:
        return RunFigures(**self.runs[str(k)])

    @property
    def rows_searched(self) -> int:
        return sum(self.run(k).rows_loaded for k in (1, 2, 3))


def row_values(run: int, n: int, planted: dict) -> dict:
    """Column ID → value for row n (1-based within the run): str, Decimal, date or None (blank)."""
    year, month = MONTH[run]
    start = dt.date(year, month, 1)
    days = (dt.date(year + (month == 12), month % 12 + 1, 1) - start).days
    inv_date = start + dt.timedelta(days=(n - 1) % days)
    taxable = Decimal(1000) + Decimal((n - 1) % 100) * Decimal("10.25")
    rate = RATES[(n - 1) % 5]
    state = STATES[(n - 1) % 4]
    intra = state == "Maharashtra"
    cgst = r2(taxable * rate / 200) if intra else Decimal("0.00")
    igst = Decimal("0.00") if intra else r2(taxable * rate / 100)
    cess = r2(taxable / 100) if n % 3 == 0 else Decimal("0.00")
    discount = r2(Decimal(n % 7) * Decimal("5.5"))
    freight = r2(Decimal(n % 11) * Decimal("12.75"))
    value = taxable + cgst * 2 + igst + cess - discount + freight
    narration = f"Order {n}"
    if n % 50 == 0:
        narration = f'Goods, "urgent" {n}'
    elif n % 50 == 25:
        narration = f"Line one {n}\nline two"
    elif n % 50 == 13:
        narration = f"Part A, part B {n}"
    v = {"c001": f"INV-{run}{n:07d}", "c002": inv_date, "c003": CUSTOMERS[(n - 1) % 10],
         "c004": f"27ABCDE{n % 10000:04d}F1Z5", "c005": state, "c006": taxable, "c007": cgst, "c008": cgst,
         "c009": igst, "c010": cess, "c011": discount, "c012": freight, "c013": value,
         "c014": inv_date + dt.timedelta(days=30), "c015": inv_date + dt.timedelta(days=2),
         "c016": inv_date + dt.timedelta(days=45), "c017": BRANCHES[(n - 1) % 3],
         "c018": f"{8471 + n % 9:04d}", "c019": PEOPLE[(n - 1) % 6], "c020": narration}
    for j, (cid, *_rest) in enumerate(COLUMNS, 1):
        if blank_cell(n, j):
            v[cid] = None
    if n in planted["text"][run]:
        cid, text = planted["text"][run][n]
        v[cid] = text
    if run == 2 and n in planted["bad_invoice"]:
        v["c001"] = f"INV/{run}{n:07d}"
    if run >= 2:
        v["c021"] = STATES[n % 4]
    return v


def _headers(run: int, no_inv: bool) -> list[str]:
    names = list(NAMES) + ([PLACE] if run >= 2 else [])
    return [h for h in names if not (no_inv and h == "Invoice No")]


def _ids(run: int, no_inv: bool) -> list[str]:
    ids = [c[0] for c in COLUMNS] + (["c021"] if run >= 2 else [])
    return [i for i in ids if not (no_inv and i == INV)]


def _csv_cell(v, crlf: bool) -> str:
    if v is None:
        return ""
    if isinstance(v, dt.date):
        return v.strftime("%d-%m-%Y")
    if isinstance(v, str) and crlf:
        return v.replace("\n", "\r\n")
    return str(v)


def generate(out: Path, size: str = SMALL) -> Manifest:
    import xlsxwriter
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    planted = _planted(size)
    runs, files = {}, {}
    for run in (1, 2, 3):
        fig = RunFigures()
        tsum, vsum = Decimal(0), Decimal(0)
        dates = set()
        ttext, dtext = Counter(), Counter()
        n = 0
        names = []
        for k, (kind, spec) in enumerate(LAYOUT[size][run]):
            if kind == "xlsx":
                name = f"TPLR_R{run}_Sales.xlsx"
                wb = xlsxwriter.Workbook(str(out / name), {"strings_to_numbers": False, "strings_to_formulas": False,
                                                          "strings_to_urls": False, "constant_memory": True})
                wb.set_properties({"created": dt.datetime(2026, 11, 21), "author": "", "title": ""})
                dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
                for sheet, count in spec:
                    ws = wb.add_worksheet(sheet)
                    ids = _ids(run, False)
                    for c, h in enumerate(_headers(run, False)):
                        ws.write_string(0, c, h)
                    for r in range(1, count + 1):
                        n += 1
                        v = row_values(run, n, planted)
                        for c, cid in enumerate(ids):
                            x = v[cid]
                            if x is None:
                                continue
                            if isinstance(x, str):
                                ws.write_string(r, c, x)
                            elif isinstance(x, dt.date):
                                ws.write_datetime(r, c, dt.datetime.combine(x, dt.time()), dfmt)
                            else:
                                ws.write_number(r, c, float(x))
                        _account(fig, v, run, n, planted, ttext, dtext, dates)
                        if run != 2 or n not in planted["bad_invoice"]:
                            tsum += v[TAXABLE] if isinstance(v[TAXABLE], Decimal) else 0
                            vsum += v["c013"] if isinstance(v["c013"], Decimal) else 0
                wb.close()
                names.append(name)
            else:
                no_inv = kind == "csv-no-inv"
                name = f"TPLR_R{run}_{'NoInvoiceNo' if no_inv else 'Part' + str(k)}.csv"
                ids = _ids(run, no_inv)
                with open(out / name, "w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(_headers(run, no_inv))
                    for _r in range(spec):
                        n += 1
                        v = row_values(run, n, planted)
                        if no_inv:
                            v[INV] = None
                            fig.no_invoice_no += 1
                        w.writerow([_csv_cell(v[cid], crlf=(n % 100 == 25)) for cid in ids])
                        _account(fig, v, run, n, planted, ttext, dtext, dates)
                        if run != 2 or n not in planted["bad_invoice"]:
                            tsum += v[TAXABLE] if isinstance(v[TAXABLE], Decimal) else 0
                            vsum += v["c013"] if isinstance(v["c013"], Decimal) else 0
                names.append(name)
        fig.rows_read = n
        fig.left_out = LEFT_OUT if run == 2 else 0
        fig.rows_loaded = n - fig.left_out
        fig.taxable_text, fig.date_text = dict(ttext), dict(dtext)
        fig.taxable_sum, fig.invoice_value_sum = str(tsum), str(vsum)
        fig.date_distinct = len(dates)
        fig.files = names
        runs[str(run)] = asdict(fig)
        files[str(run)] = names
    m = Manifest(size, runs, files)
    (out / f"tpl_r_{size}.json").write_text(json.dumps(asdict(m), indent=1), encoding="utf-8")
    return m


def _account(fig: RunFigures, v: dict, run: int, n: int, planted: dict, ttext, dtext, dates) -> None:
    """Figures over loaded rows only (R-0002's bad Invoice No rows are left out)."""
    if run == 2 and n in planted["bad_invoice"]:
        return
    t = v[TAXABLE]
    if isinstance(t, Decimal):
        fig.taxable_count += 1
        fig.taxable_min = str(t) if fig.taxable_min is None else str(min(Decimal(fig.taxable_min), t))
        fig.taxable_max = str(t) if fig.taxable_max is None else str(max(Decimal(fig.taxable_max), t))
    elif isinstance(t, str):
        ttext[t] += 1
    else:
        fig.taxable_blank += 1
    d = v[DATE_]
    if isinstance(d, dt.date):
        fig.date_count += 1
        dates.add(d)
        fig.date_min = d.isoformat() if fig.date_min is None else min(fig.date_min, d.isoformat())
        fig.date_max = d.isoformat() if fig.date_max is None else max(fig.date_max, d.isoformat())
    elif isinstance(d, str):
        dtext[d] += 1
    else:
        fig.date_blank += 1


def load_manifest(out: Path, size: str = SMALL) -> Manifest:
    return Manifest(**json.loads((Path(out) / f"tpl_r_{size}.json").read_text(encoding="utf-8")))


# ---------------------------------------------------------------- verify: read the files back as the app does
def verify(out: Path, m: Manifest) -> None:
    """The planted counts, read back with python-calamine and the csv module (independent of the generator's
    bookkeeping). Raises AssertionError on any difference."""
    from python_calamine import CalamineWorkbook
    out = Path(out)
    for run in (1, 2, 3):
        fig = m.run(run)
        rows = 0
        taxable, dates, bad, no_inv = Counter(), Counter(), 0, 0
        for name in m.files[str(run)]:
            path = out / name
            if name.endswith(".xlsx"):
                wb = CalamineWorkbook.from_path(str(path))
                tables = [wb.get_sheet_by_name(s).to_python() for s in wb.sheet_names]
            else:
                with open(path, encoding="utf-8", newline="") as f:
                    tables = [list(csv.reader(f))]
            for table in tables:
                head = [str(h) for h in table[0]]
                ti, di = head.index("Taxable Value"), head.index("Invoice Date")
                ii = head.index("Invoice No") if "Invoice No" in head else None
                assert (PLACE in head) == (run >= 2), (name, head)
                for rec in table[1:]:
                    rows += 1
                    if isinstance(rec[ti], str) and rec[ti] not in ("",) and not _is_num(rec[ti]):
                        taxable[rec[ti]] += 1
                    if isinstance(rec[di], str) and rec[di] in ("NA", "31-02-2026"):
                        dates[rec[di]] += 1
                    if ii is None:
                        no_inv += 1
                    elif rec[ii] and not re.fullmatch(r"INV-[0-9]{8}", str(rec[ii])):   # PATTERN
                        bad += 1
        assert rows == fig.rows_read == ROWS_PER_RUN[m.size], (run, rows)
        assert dict(taxable) == fig.taxable_text == ({t: k for t, k in TAXABLE_TEXT[m.size]} if run == 1 else {}), \
            (run, taxable)
        assert dict(dates) == fig.date_text == ({t: k for t, k in DATE_TEXT[m.size]} if run == 2 else {}), \
            (run, dates)
        assert bad == (LEFT_OUT if run == 2 else 0), (run, bad)
        assert no_inv == fig.no_invoice_no, (run, no_inv)
    assert m.rows_searched == ROWS_PER_RUN[m.size] * 3 - LEFT_OUT
    want_no_inv = {SMALL: 400, FULL: 400_000}[m.size]
    assert m.run(3).no_invoice_no == want_no_inv
    if m.size == SMALL:
        assert m.rows_searched == 7_437
    else:
        assert m.rows_searched == 7_499_937


def _is_num(s: str) -> bool:
    try:
        Decimal(s)
        return True
    except ArithmeticError:
        return False
    except ValueError:
        return False


# ---------------------------------------------------------------- the template
def template(client_id: str):
    """TPL-R as a ``Template``: type rules on Taxable Value and Invoice Date set to Warning, Character pattern on
    Invoice No (Error), one default output "Latest month by State" (relative date filter, AC-TXT-9)."""
    from sankalan.model import definition as d
    from sankalan.model.definition import Definition, Filter, Group, FlatMeasure, cards
    from sankalan.model.rule import IS_DATE, IS_NUMBER, PATTERN as PATTERN_RULE, WARNING, Rule, with_type_rules
    from sankalan.model.template import Column, DefaultOutput, SourceSettings, Template
    cols = [Column(i, name, typ, dec, fmt, totals_check=tot) for i, name, typ, dec, fmt, tot in COLUMNS]
    rules = [Rule("c006.type", "c006", IS_NUMBER, {}, WARNING), Rule("c002.type", "c002", IS_DATE, {}, WARNING),
             Rule("r1", "c001", PATTERN_RULE, {"pattern": PATTERN})]
    do1 = Definition("", [Filter("c002", d.LATEST_MONTH)], [Group("c005")],
                     cards(FlatMeasure(d.ROWS, d.COUNT), FlatMeasure("c006", d.SUM)))
    return Template("", client_id, "Sales Register R", SourceSettings(sheets="all"), cols,
                    with_type_rules(cols, rules), [DefaultOutput("Latest month by State", do1.to_dict())],
                    {"pattern": "{Client}_{Template}_{RunID}_{Output}", "delimiter": ",", "encoding": "utf-8-sig"})


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Build TPL-R")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "_generated" / "tpl_r")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args(argv)
    size = FULL if a.full else SMALL
    m = generate(a.out / size, size)
    verify(a.out / size, m)
    print(f"TPL-R {size}: {m.rows_searched:,} rows searched, files in {a.out / size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
