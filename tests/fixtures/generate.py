"""Build the test fixture pack F00-F21 (and P01/P02 with --perf) and check it against the Fixtures tab.

    python tests\\fixtures\\generate.py                      # F01-F21 into tests\\fixtures\\_generated, then verify
    python tests\\fixtures\\generate.py --out C:\\SankalanTest\\Fixtures
    python tests\\fixtures\\generate.py --perf [--perf-rows N] # also P01 (12 x 10M-row CSV) and P02 (10 x 1M-row .xlsx)

Every file is deterministic except F06 (encryption uses a random salt). The expected figures below are copied
from docs/specs/test-cases.md > Fixtures and are the acceptance oracle: `verify()` reads each file back the way the
app will (python-calamine, a sheet-XML scan for hidden rows, the csv module) and compares.

Development only: uses XlsxWriter and msoffcrypto-tool (requirements-dev.txt). F11 (.xls) is a checked-in binary
made by make_static_xls.py, because no runtime or dev package writes .xls any more.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import random
import re
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
DEFAULT_OUT = HERE / "_generated"
PASSWORD = "Sankalan@123"
FIXED_TIME = dt.datetime(2026, 11, 16, 0, 0, 0)   # document properties, so .xlsx bytes are reproducible

# ---------------------------------------------------------------- F00 common rule

HEADERS = ["Invoice No", "Invoice Date", "Customer", "GSTIN", "State", "Taxable Value", "GST Rate", "Tax Amount"]
CUSTOMERS = ["Shree Ganesh Traders", "Patel Agencies", "Mehta & Sons", "Kaveri Distributors", "Sai Enterprises",
             "Laxmi Stores", "Om Sai Wholesale", "Krishna Retail", "Annapurna Foods", "Ganga Suppliers"]
STATES = ["Maharashtra", "Gujarat", "Karnataka", "Delhi"]
RATES = [0, 5, 12, 18, 28]
BRANCHES = ["Pune", "Nashik", "Nagpur"]
D2 = Decimal("0.01")


def r2(x: Decimal) -> Decimal:
    """Round to 2 places, half away from zero (Decimal's ROUND_HALF_UP)."""
    return x.quantize(D2, rounding=ROUND_HALF_UP)


def month(year: int, m: int) -> tuple[dt.date, int]:
    start = dt.date(year, m, 1)
    nxt = dt.date(year + (m == 12), m % 12 + 1, 1)
    return start, (nxt - start).days


def f00(n: int, base: int, start: dt.date, days: int) -> dict:
    taxable = Decimal(1000) + Decimal((n - 1) % 100) * Decimal("10.25")
    rate = RATES[(n - 1) % 5]
    return {
        "Invoice No": f"INV-{base + n:05d}",
        "Invoice Date": start + dt.timedelta(days=(n - 1) % days),
        "Customer": CUSTOMERS[(n - 1) % 10],
        "GSTIN": f"27ABCDE{n % 10000:04d}F1Z5",
        "State": STATES[(n - 1) % 4],
        "Taxable Value": taxable,
        "GST Rate": rate,
        "Tax Amount": r2(taxable * rate / 100),
    }


def f00_rows(count: int, base: int, year: int, m: int, cols=HEADERS, extra=None) -> list[list]:
    start, days = month(year, m)
    out = []
    for n in range(1, count + 1):
        d = f00(n, base, start, days)
        if extra:
            d.update(extra(n))
        out.append([d.get(c, "") for c in cols])
    return out


# ---------------------------------------------------------------- writers


class Formula:
    def __init__(self, formula: str, value):
        self.formula, self.value = formula, value


class Sheet:
    def __init__(self, name, rows, hidden_rows=(), hidden=False):
        self.name, self.rows, self.hidden_rows, self.hidden = name, rows, set(hidden_rows), hidden


def write_xlsx(path: Path, sheets: list[Sheet]) -> None:
    """Rows are lists of cells; row index i is sheet row i + 1. '' or None = empty cell (not written)."""
    import xlsxwriter
    wb = xlsxwriter.Workbook(str(path), {"strings_to_numbers": False, "strings_to_formulas": False,
                                         "strings_to_urls": False})
    wb.set_properties({"created": FIXED_TIME, "author": "", "title": ""})
    dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
    dtfmt = wb.add_format({"num_format": "dd-mm-yyyy hh:mm"})
    for sh in sheets:
        ws = wb.add_worksheet(sh.name)
        for r, row in enumerate(sh.rows):
            if r in sh.hidden_rows:
                ws.set_row(r, None, None, {"hidden": True})
            for c, v in enumerate(row):
                if v is None or (isinstance(v, str) and v == ""):
                    continue
                if isinstance(v, str):
                    ws.write_string(r, c, v)
                elif isinstance(v, dt.datetime):
                    ws.write_datetime(r, c, v, dtfmt)
                elif isinstance(v, dt.date):
                    ws.write_datetime(r, c, dt.datetime.combine(v, dt.time()), dfmt)
                elif isinstance(v, Formula):
                    ws.write_formula(r, c, v.formula, None, v.value)
                else:
                    ws.write_number(r, c, float(v))
        if sh.hidden:
            ws.hide()
    wb.close()


def write_csv(path: Path, rows: list[list], encoding="utf-8", delimiter=",") -> None:
    with open(path, "w", encoding=encoding, newline="") as f:
        csv.writer(f, delimiter=delimiter).writerows(rows)


def csv_cell(v) -> str:
    if isinstance(v, dt.date):
        return v.isoformat()
    return "" if v is None else str(v)


def make_macro_enabled(path: Path) -> None:
    """Turn an .xlsx written by XlsxWriter into a macro-enabled workbook (.xlsm content type), keeping entry
    order and timestamps. No VBA part: generating vbaProject.bin needs an OLE writer (deviation, PROGRESS.md)."""
    src = path.read_bytes()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src)) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            data = zi.read(info)
            if info.filename == "[Content_Types].xml":
                data = data.replace(b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
                                    b"application/vnd.ms-excel.sheet.macroEnabled.main+xml")
            zo.writestr(info, data)
    path.write_bytes(out.getvalue())


# ---------------------------------------------------------------- F04 plants

F04_PLANTS = {
    "invoice_blank": range(101, 113),        # 12, Error
    "invoice_no_hyphen": range(201, 209),    # 8, Error (pattern)
    "taxable_text": range(213, 228),         # 15, Error (Is a number); sheet rows 214-228
    "taxable_negative": range(301, 306),     # 5, Error (range)
    "gstin_14": range(401, 411),             # 10, Error (length)
    "date_text": range(501, 505),            # 4, Error (Is a date)
    "rate_15": range(601, 607),              # 6, Error (allowed values)
    "duplicate_later": (702, 704, 706),      # repeat 701/703/705: 6 rows flagged, 3 left out
    "state_goa": range(801, 826),            # 25, Warning
    "customer_blank": range(901, 908),       # 7, Warning
}


def f04_rows() -> list[list]:
    start, days = month(2026, 9)
    rows = []
    invoices = {}
    for n in range(1, 2001):
        d = f00(n, 40000, start, days)
        invoices[n] = d["Invoice No"]
        if n in F04_PLANTS["invoice_blank"]:
            d["Invoice No"] = ""
        if n in F04_PLANTS["invoice_no_hyphen"]:
            d["Invoice No"] = d["Invoice No"].replace("-", "")
        if n in F04_PLANTS["taxable_text"]:
            d["Taxable Value"] = "abc"
        if n in F04_PLANTS["taxable_negative"]:
            d["Taxable Value"] = -d["Taxable Value"]
            d["Tax Amount"] = r2(d["Taxable Value"] * d["GST Rate"] / 100)
        if n in F04_PLANTS["gstin_14"]:
            d["GSTIN"] = d["GSTIN"][:14]
        if n in F04_PLANTS["date_text"]:
            d["Invoice Date"] = "31-02-2026"
        if n in F04_PLANTS["rate_15"]:
            d["GST Rate"] = 15
            d["Tax Amount"] = r2(d["Taxable Value"] * 15 / 100)
        if n in F04_PLANTS["duplicate_later"]:
            d["Invoice No"] = invoices[n - 1]
        if n in F04_PLANTS["state_goa"]:
            d["State"] = "Goa"
        if n in F04_PLANTS["customer_blank"]:
            d["Customer"] = ""
        rows.append([d[c] for c in HEADERS])
    return rows


F04_LEFT_OUT = sorted(set().union(*(F04_PLANTS[k] for k in (
    "invoice_blank", "invoice_no_hyphen", "taxable_text", "taxable_negative", "gstin_14", "date_text", "rate_15",
    "duplicate_later"))))

# ---------------------------------------------------------------- F17

F17_HEADER = ["Case", "Amount", "Amount0", "Doc Date", "Due Date", "Code"]
F17_AMOUNTS = ["₹1,23,456.789", "1,234,567.5", "(1,234)", "2.345", "-2.345", "2.5", "-2.5", "₹ 500", "  750  ",
               "0.005", "12abc", "", "   "]
F17_DOC = {1: "05-11-2026", 2: "31-12-2026", 3: "31-11-2026", 4: "29-02-2028", 5: "29-02-2027"}
F17_DUE = {1: "05/11/2026", 2: "31/12/2026", 3: "32/01/2027"}
F17_CODE = {1: "00123", 2: " A1 ", 3: "   ", 4: "MIXED Case"}


def f17_rows() -> list[list]:
    return [[f"C{i:02d}", a, a, F17_DOC.get(i, "01-01-2027"), F17_DUE.get(i, "15/01/2027"), F17_CODE.get(i, "X")]
            for i, a in enumerate(F17_AMOUNTS, start=1)]


F18_ROWS = [["C01", "1234.50", "1234.50", "01-01-2027", "15/01/2027", "Café"],
            ["C02", "10", "10", "01-01-2027", "15/01/2027", "Müller"],
            ["C03", "20", "20", "01-01-2027", "15/01/2027", "Señor"]]

# ---------------------------------------------------------------- the pack


def tpl(rows, cols=HEADERS) -> list[list]:
    return [list(cols)] + rows


def build_f03() -> tuple[list[list], set[int]]:
    """Sales: title row 1, header row 2. Hidden row after data rows 150, 300 ... 3750; blank row after 400 ... 4000
    (after 2000 and 4000: spaces only). Where both follow the same data row, the hidden row comes first."""
    data = f00_rows(4000, 20000, 2026, 11)
    rows = [["Acme Traders — Sales Register, November 2026"], list(HEADERS)]
    hidden = set()
    start, _ = month(2026, 11)
    for n, row in enumerate(data, start=1):
        rows.append(row)
        if n % 150 == 0 and n <= 3750:
            k = n // 150
            hidden.add(len(rows))
            rows.append([f"INV-{29000 + k:05d}", start, CUSTOMERS[0], "27ABCDE0000F1Z5", STATES[0],
                         Decimal("99999.99"), 18, r2(Decimal("99999.99") * 18 / 100)])
        if n % 400 == 0:
            rows.append([" " * 3] * len(HEADERS) if n in (2000, 4000) else [])
    return rows, hidden


def generate(out: Path = DEFAULT_OUT) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    p = out.joinpath

    write_xlsx(p("Sample_Sales.xlsx"), [Sheet("Sales", [["Acme Traders — Sales Register"], ["Sample"]]
                                              + tpl(f00_rows(1000, 60000, 2026, 8)))])
    write_xlsx(p("Sales_Oct.xlsx"), [Sheet("Sales", tpl(f00_rows(5000, 10000, 2026, 10)))])
    f03, f03_hidden = build_f03()
    write_xlsx(p("Sales_Nov.xlsx"), [
        Sheet("Sales", f03, hidden_rows=f03_hidden),
        Sheet("Notes", [["Notes"], ["November register. Hidden rows are corrections not yet approved."],
                        ["Prepared by accounts."]]),
        Sheet("Old", tpl(f00_rows(500, 21000, 2026, 11)), hidden=True),
    ])
    write_xlsx(p("Sales_Errors.xlsx"), [Sheet("Sales", tpl(f04_rows()))])
    shutil.copyfile(p("Sales_Oct.xlsx"), p("Sales_Oct_copy.xlsx"))
    make_f06(p("Sales_Protected.xlsx"))
    write_xlsx(p("Sales_Locked.xlsx"), [Sheet("Sales", tpl(f00_rows(1000, 16000, 2026, 10)))])
    f08_cols = ["Invoice No", "Invoice Date", "Customer", "GSTIN", "Taxable Value", "GST Rate", "Tax Amount", "Remarks"]
    f08_head = ["Inv No", "invoice_date", "CUSTOMER", "G.S.T.I.N", "Taxable Value", "GST-Rate", "Tax Amount", "Remarks"]
    write_xlsx(p("Sales_Renamed_Headers.xlsx"), [Sheet("Sales", [f08_head] + f00_rows(
        1000, 70000, 2026, 11, cols=f08_cols, extra=lambda n: {"Remarks": "ok"}))])
    rnd = random.Random(9)
    write_xlsx(p("Sales_NoHeader.xlsx"), [Sheet("Sales", [[rnd.randint(1, 999) for _ in range(8)]
                                                          for _ in range(100)])])
    write_xlsx(p("Sales_WrongSheet.xlsx"), [Sheet("Data", tpl(f00_rows(100, 17000, 2026, 10)))])
    shutil.copyfile(STATIC / "Sales_Old.xls", p("Sales_Old.xls"))
    f12 = f00_rows(15000, 25000, 2026, 10, extra=lambda n: {"Customer": ""})
    write_csv(p("Sales_ManyIssues.csv"), [HEADERS] + [[csv_cell(v) for v in r] for r in f12])
    with_branch = HEADERS + ["Branch"]
    branch = lambda n: {"Branch": BRANCHES[(n - 1) % 3]}  # noqa: E731
    write_xlsx(p("Sales_Dec_NewCol.xlsx"), [Sheet("Sales", tpl(f00_rows(3000, 50000, 2026, 12, with_branch, branch),
                                                               with_branch))])
    write_xlsx(p("Sales_NoDates.xlsx"), [Sheet("Sales", tpl(f00_rows(
        500, 80000, 2026, 12, with_branch, lambda n: {**branch(n), "Invoice Date": ""}), with_branch))])
    write_xlsx(p("Sales_Jan.xlsx"), [Sheet("Sales", tpl(f00_rows(2000, 85000, 2027, 1, with_branch, branch),
                                                        with_branch))])
    write_xlsx(p("Sales_Regions.xlsx"), [
        Sheet("North", tpl(f00_rows(1500, 90000, 2026, 10))),
        Sheet("South", tpl(f00_rows(2500, 91500, 2026, 10))),
        Sheet("Archive", tpl(f00_rows(300, 95000, 2026, 10)), hidden=True),
    ])
    write_csv(p("Conversion_Values.csv"), [F17_HEADER] + f17_rows())
    write_csv(p("Conversion_1252.csv"), [F17_HEADER] + F18_ROWS, encoding="cp1252", delimiter=";")
    write_xlsx(p("Conversion_Values.xlsx"), [Sheet("Data", [
        F17_HEADER,
        ["C01", 2.345, "", dt.datetime(2026, 11, 5, 14, 30), "", "00123"],
        ["C02", Formula("=100*1.5", 150), "", "", "", ""],
        ["C03", Formula("=NA()", "#N/A"), "", "", "", ""],
    ])])
    write_xlsx(p("Sales_Macro.xlsm"), [Sheet("Sales", tpl(f00_rows(500, 15000, 2026, 10)))])
    make_macro_enabled(p("Sales_Macro.xlsm"))
    folder = p("Run_Folder")
    folder.mkdir(exist_ok=True)
    shutil.copyfile(p("Sales_Oct.xlsx"), folder / "Sales_Oct.xlsx")
    return out


def make_f06(path: Path) -> None:
    import msoffcrypto
    with tempfile.TemporaryDirectory() as td:
        plain = Path(td) / "plain.xlsx"
        write_xlsx(plain, [Sheet("Sales", tpl(f00_rows(100, 10000, 2026, 10)))])
        with open(plain, "rb") as fi, open(path, "wb") as fo:
            msoffcrypto.OfficeFile(fi).encrypt(PASSWORD, fo)


# ---------------------------------------------------------------- expected figures (Fixtures tab)

FILES = {
    "F01": "Sample_Sales.xlsx", "F02": "Sales_Oct.xlsx", "F03": "Sales_Nov.xlsx", "F04": "Sales_Errors.xlsx",
    "F05": "Sales_Oct_copy.xlsx", "F06": "Sales_Protected.xlsx", "F07": "Sales_Locked.xlsx",
    "F08": "Sales_Renamed_Headers.xlsx", "F09": "Sales_NoHeader.xlsx", "F10": "Sales_WrongSheet.xlsx",
    "F11": "Sales_Old.xls", "F12": "Sales_ManyIssues.csv", "F13": "Sales_Dec_NewCol.xlsx",
    "F14": "Sales_NoDates.xlsx", "F15": "Sales_Jan.xlsx", "F16": "Sales_Regions.xlsx",
    "F17": "Conversion_Values.csv", "F18": "Conversion_1252.csv", "F19": "Conversion_Values.xlsx",
    "F20": "Sales_Macro.xlsm", "F21": "Run_Folder",
}

EXPECTED = {
    "F01": {"rows": 1000, "taxable": "1507375.00", "tax": "191344.50", "per_state": 250, "per_rate": 200,
            "header_row": 3},
    "F02": {"rows": 5000, "taxable": "7536875.00", "tax": "956722.50", "per_state": 1250, "per_rate": 1000,
            "days": {**{d: 162 for d in range(1, 10)}, **{d: 161 for d in range(10, 32)}}},
    "F03": {"rows": 4000, "taxable": "6029500.00", "tax": "765378.00", "hidden_rows": 25,
            "hidden_rows_taxable": "99999.99", "hidden_sheets": ["Old"], "blank_rows": 10,
            "blank_rows_spaces_only": 2, "header_row": 2},
    "F04": {"rows": 2000,
            "plants": {"invoice_blank": 12, "invoice_no_hyphen": 8, "taxable_text": 15, "taxable_negative": 5,
                       "gstin_14": 10, "date_text": 4, "rate_15": 6, "duplicate_flagged": 6, "duplicate_left_out": 3,
                       "state_goa": 25, "customer_blank": 7},
            "taxable_text_sheet_rows": (214, 228),
            "left_out_rows": 63, "loaded_rows": 1937,
            "taxable": {"input": "2986623.75", "loaded": "2946994.00", "left_out": "39629.75"},
            "tax": {"input": "381662.10", "loaded": "374994.35", "left_out": "6667.75"}},
    "F06": {"rows": 100},
    "F07": {"rows": 1000},
    "F08": {"rows": 1000, "taxable": "1507375.00", "tax": "191344.50",
            "headers": ["Inv No", "invoice_date", "CUSTOMER", "G.S.T.I.N", "Taxable Value", "GST-Rate",
                        "Tax Amount", "Remarks"]},
    "F09": {"rows": 100, "cols": 8},
    "F10": {"rows": 100, "sheets": ["Data"]},
    "F11": {"rows": 100},
    "F12": {"rows": 15000, "customer_blank": 15000},
    "F13": {"rows": 3000, "taxable": "4522125.00", "tax": "574033.50", "per_branch": 1000},
    "F14": {"rows": 500, "taxable": "753687.50", "tax": "95672.25"},
    "F15": {"rows": 2000, "taxable": "3014750.00", "tax": "382689.00"},
    "F16": {"North": {"rows": 1500, "taxable": "2261062.50"}, "South": {"rows": 2500, "taxable": "3768437.50"},
            "taxable": "6029500.00", "hidden_sheets": ["Archive"]},
    "F17": {"rows": 13},
    "F18": {"rows": 3, "codes": ["Café", "Müller", "Señor"]},
    "F20": {"rows": 500},
}

# ---------------------------------------------------------------- verification (reads files back)


class FixtureError(AssertionError):
    pass


def check(cond, msg):
    if not cond:
        raise FixtureError(msg)


def dec(v) -> Decimal:
    """Number cell as the app will stage it: shortest exact decimal of the float."""
    return Decimal(repr(v)) if isinstance(v, float) else Decimal(v)


def num_or_zero(v) -> Decimal:
    """Input side of the totals check: unreadable = 0, per-value rounding to 2 places (T20)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return r2(dec(v))
    return Decimal(0)


def hidden_rows(path: Path, sheet_index: int) -> set[int]:
    """1-based sheet rows with hidden="1" (the scan the app does, T11). XlsxWriter names parts sheetN.xml."""
    with zipfile.ZipFile(path) as z:
        xml = z.read(f"xl/worksheets/sheet{sheet_index + 1}.xml")
    return {int(m.group(1)) for m in re.finditer(rb'<row r="(\d+)"[^>]*?hidden="1"', xml)}


def blank(row) -> bool:
    return all((c is None) or (isinstance(c, str) and c.strip(" ") == "") for c in row)


def read_sheet(path: Path, name: str, header_row: int = 1):
    """Visible data rows as {sheet_row: dict}, plus counts of hidden and blank rows."""
    import python_calamine as pc
    wb = pc.CalamineWorkbook.from_path(str(path))
    idx = wb.sheet_names.index(name)
    sh = wb.get_sheet_by_index(idx)
    raw = sh.to_python(skip_empty_area=False)
    hid = hidden_rows(path, idx)
    header = raw[header_row - 1]
    data, n_hidden, n_blank, n_spaces = {}, 0, 0, 0
    for i, row in enumerate(raw[header_row:], start=header_row + 1):
        if i in hid:
            n_hidden += 1
            continue
        if blank(row):
            n_blank += 1
            n_spaces += any(isinstance(c, str) and c != "" for c in row)
            continue
        data[i] = dict(zip(header, row))
    return header, data, {"hidden": n_hidden, "blank": n_blank, "spaces": n_spaces, "hidden_set": hid}


def sums(rows, col) -> Decimal:
    return sum((num_or_zero(r[col]) for r in rows), Decimal(0))


def check_totals(fid, rows, exp):
    rows = list(rows)
    check(len(rows) == exp["rows"], f"{fid}: {len(rows)} rows, expected {exp['rows']}")
    if "taxable" in exp:
        got = sums(rows, "Taxable Value")
        check(got == Decimal(exp["taxable"]), f"{fid}: Taxable {got}, expected {exp['taxable']}")
    if "tax" in exp:
        got = sums(rows, "Tax Amount")
        check(got == Decimal(exp["tax"]), f"{fid}: Tax {got}, expected {exp['tax']}")


def verify(out: Path = DEFAULT_OUT) -> dict:
    """Read every fixture back and compare with EXPECTED. Returns a short report; raises FixtureError."""
    import python_calamine as pc
    out = Path(out)
    f = {k: out / v for k, v in FILES.items()}
    report = {}

    # F01-F02: clean TPL-A sheets
    for fid, header_row in (("F01", 3), ("F02", 1)):
        header, data, _ = read_sheet(f[fid], "Sales", header_row)
        check(header == HEADERS, f"{fid}: header {header}")
        rows = list(data.values())
        check_totals(fid, rows, EXPECTED[fid])
        st = Counter(r["State"] for r in rows)
        check(set(st.values()) == {EXPECTED[fid]["per_state"]}, f"{fid}: per state {st}")
        rt = Counter(r["GST Rate"] for r in rows)
        check(set(rt.values()) == {EXPECTED[fid]["per_rate"]}, f"{fid}: per rate {rt}")
        check(all(isinstance(r["Invoice Date"], dt.date) for r in rows), f"{fid}: dates must be real Excel dates")
        if "days" in EXPECTED[fid]:
            days = Counter(r["Invoice Date"].day for r in rows)
            check(dict(days) == EXPECTED[fid]["days"], f"{fid}: rows per day {days}")
    wb = pc.CalamineWorkbook.from_path(str(f["F01"]))
    first = wb.get_sheet_by_name("Sales").to_python()[:2]
    check(first[0][0] == "Acme Traders — Sales Register" and first[1][0] == "Sample", "F01: title rows")

    # F03: hidden rows, hidden sheet, blank rows
    e = EXPECTED["F03"]
    header, data, cnt = read_sheet(f["F03"], "Sales", 2)
    check(header == HEADERS, "F03: header row 2")
    check_totals("F03", data.values(), e)
    check(cnt["hidden"] == e["hidden_rows"], f"F03: hidden rows {cnt['hidden']}")
    check(cnt["blank"] == e["blank_rows"], f"F03: blank rows {cnt['blank']}")
    check(cnt["spaces"] == e["blank_rows_spaces_only"], f"F03: spaces-only rows {cnt['spaces']}")
    import python_calamine as _pc
    raw = _pc.CalamineWorkbook.from_path(str(f["F03"])).get_sheet_by_name("Sales").to_python(skip_empty_area=False)
    hid_tax = {dec(raw[i - 1][5]) for i in cnt["hidden_set"]}
    check(hid_tax == {Decimal(e["hidden_rows_taxable"])}, f"F03: hidden-row Taxable {hid_tax}")
    meta = {m.name: str(m.visible) for m in _pc.CalamineWorkbook.from_path(str(f["F03"])).sheets_metadata}
    check([n for n, v in meta.items() if "Visible" not in v or "Hidden" in v] == e["hidden_sheets"],
          f"F03: sheet visibility {meta}")
    check(list(meta) == ["Sales", "Notes", "Old"], f"F03: sheets {list(meta)}")

    # F04: planted errors and the totals reconciliation
    e = EXPECTED["F04"]
    header, data, _ = read_sheet(f["F04"], "Sales", 1)
    rows = {i - 1: r for i, r in data.items()}          # n = sheet row - 1
    check(len(rows) == e["rows"], f"F04: rows {len(rows)}")
    pat = re.compile(r"^[A-Za-z]{3}-\d{5}$")
    found = {
        "invoice_blank": [n for n, r in rows.items() if r["Invoice No"] == ""],
        "invoice_no_hyphen": [n for n, r in rows.items() if r["Invoice No"] and not pat.match(r["Invoice No"])],
        "taxable_text": [n for n, r in rows.items() if isinstance(r["Taxable Value"], str)],
        "taxable_negative": [n for n, r in rows.items()
                             if isinstance(r["Taxable Value"], float) and r["Taxable Value"] < 0],
        "gstin_14": [n for n, r in rows.items() if len(r["GSTIN"]) != 15],
        "date_text": [n for n, r in rows.items() if isinstance(r["Invoice Date"], str)],
        "rate_15": [n for n, r in rows.items() if r["GST Rate"] not in (0, 5, 12, 18, 28)],
        "state_goa": [n for n, r in rows.items() if r["State"] not in STATES],
        "customer_blank": [n for n, r in rows.items() if r["Customer"] == ""],
    }
    groups = Counter(r["Invoice No"] for r in rows.values() if r["Invoice No"])
    dup_flagged = sorted(n for n, r in rows.items() if r["Invoice No"] and groups[r["Invoice No"]] > 1)
    seen, dup_later = set(), []
    for n in sorted(rows):
        inv = rows[n]["Invoice No"]
        if inv and groups[inv] > 1:
            (dup_later.append(n) if inv in seen else seen.add(inv))
    for k, ns in found.items():
        check(len(ns) == e["plants"][k], f"F04: {k} {len(ns)} rows, expected {e['plants'][k]}")
        check(sorted(ns) == sorted(F04_PLANTS[k]), f"F04: {k} on rows {ns[:5]}...")
    check(len(dup_flagged) == e["plants"]["duplicate_flagged"], f"F04: duplicates flagged {dup_flagged}")
    check(len(dup_later) == e["plants"]["duplicate_left_out"], f"F04: later duplicates {dup_later}")
    tt = [n + 1 for n in found["taxable_text"]]
    check((min(tt), max(tt)) == e["taxable_text_sheet_rows"], f"F04: 'abc' sheet rows {min(tt)}-{max(tt)}")
    left = set(dup_later).union(*(found[k] for k in ("invoice_blank", "invoice_no_hyphen", "taxable_text",
                                                     "taxable_negative", "gstin_14", "date_text", "rate_15")))
    check(len(left) == e["left_out_rows"] and sorted(left) == F04_LEFT_OUT, f"F04: left out {len(left)}")
    check(len(rows) - len(left) == e["loaded_rows"], "F04: loaded rows")
    for col, key in (("Taxable Value", "taxable"), ("Tax Amount", "tax")):
        inp = sums(rows.values(), col)
        lo = sums((rows[n] for n in left), col)
        ld = sums((r for n, r in rows.items() if n not in left), col)
        check(inp == Decimal(e[key]["input"]), f"F04: {col} Input {inp}, expected {e[key]['input']}")
        check(lo == Decimal(e[key]["left_out"]), f"F04: {col} Left out {lo}, expected {e[key]['left_out']}")
        check(ld == Decimal(e[key]["loaded"]), f"F04: {col} Loaded {ld}, expected {e[key]['loaded']}")
        check(inp == ld + lo, f"F04: {col} Input = Loaded + Left out")

    # F05: byte copy
    check(sha256(f["F05"]) == sha256(f["F02"]), "F05: must be byte-identical to F02")

    # F06: encrypted OLE container that opens with the password
    import msoffcrypto
    check(f["F06"].read_bytes()[:8] == bytes.fromhex("D0CF11E0A1B11AE1"), "F06: not an OLE (encrypted) container")
    with open(f["F06"], "rb") as fi:
        of = msoffcrypto.OfficeFile(fi)
        check(of.is_encrypted(), "F06: not encrypted")
        of.load_key(password=PASSWORD)
        buf = io.BytesIO()
        of.decrypt(buf)
    with tempfile.TemporaryDirectory() as td:
        plain = Path(td) / "f06.xlsx"
        plain.write_bytes(buf.getvalue())
        header, data, _ = read_sheet(plain, "Sales", 1)
        check(header == HEADERS and len(data) == EXPECTED["F06"]["rows"], "F06: decrypted content")

    for fid in ("F07", "F20"):
        header, data, _ = read_sheet(f[fid], "Sales", 1)
        check(header == HEADERS and len(data) == EXPECTED[fid]["rows"], f"{fid}: rows {len(data)}")
    with zipfile.ZipFile(f["F20"]) as z:
        check(b"macroEnabled.main+xml" in z.read("[Content_Types].xml"), "F20: not a macro-enabled workbook")

    e = EXPECTED["F08"]
    header, data, _ = read_sheet(f["F08"], "Sales", 1)
    check(header == e["headers"], f"F08: headers {header}")
    check_totals("F08", data.values(), e)
    check({r["Remarks"] for r in data.values()} == {"ok"}, "F08: Remarks")

    raw = pc.CalamineWorkbook.from_path(str(f["F09"])).get_sheet_by_name("Sales").to_python()
    check(len(raw) == 100 and all(len(r) == 8 for r in raw), "F09: shape")
    check(all(isinstance(v, float) and 1 <= v <= 999 and v.is_integer() for r in raw for v in r),
          "F09: only integers 1-999, no text row")

    wb = pc.CalamineWorkbook.from_path(str(f["F10"]))
    check(wb.sheet_names == EXPECTED["F10"]["sheets"], f"F10: sheets {wb.sheet_names}")
    header, data, _ = read_sheet(f["F10"], "Data", 1)
    check(len(data) == 100, "F10: rows")

    check(f["F11"].read_bytes()[:8] == bytes.fromhex("D0CF11E0A1B11AE1"), "F11: not an Excel 97-2003 file")
    raw = pc.CalamineWorkbook.from_path(str(f["F11"])).get_sheet_by_name("Sales").to_python()
    check(raw[0] == HEADERS and len(raw) - 1 == EXPECTED["F11"]["rows"], "F11: content")

    with open(f["F12"], encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    check(len(rows) == 15000 and sum(r["Customer"] == "" for r in rows) == 15000, "F12: Customer blank everywhere")
    check(list(rows[0]) == HEADERS, "F12: header")

    for fid in ("F13", "F14", "F15"):
        header, data, _ = read_sheet(f[fid], "Sales", 1)
        check(header == HEADERS + ["Branch"], f"{fid}: header {header}")
        check_totals(fid, data.values(), EXPECTED[fid])
        if fid == "F13":
            br = Counter(r["Branch"] for r in data.values())
            check(set(br.values()) == {1000} and set(br) == set(BRANCHES), f"F13: branches {br}")
        if fid == "F14":
            check(all(r["Invoice Date"] == "" for r in data.values()), "F14: Invoice Date must be empty")

    e = EXPECTED["F16"]
    total = Decimal(0)
    for name in ("North", "South"):
        header, data, _ = read_sheet(f["F16"], name, 1)
        check_totals(f"F16 {name}", data.values(), e[name])
        total += sums(data.values(), "Taxable Value")
    check(total == Decimal(e["taxable"]), f"F16: total {total}")
    meta = {m.name: str(m.visible) for m in pc.CalamineWorkbook.from_path(str(f["F16"])).sheets_metadata}
    check(list(meta) == ["North", "South", "Archive"] and "Hidden" in meta["Archive"]
          and "Hidden" not in meta["North"] + meta["South"], f"F16: sheets {meta}")

    raw17 = f["F17"].read_bytes()
    check(not raw17.startswith(b"\xef\xbb\xbf"), "F17: UTF-8 without BOM")
    with open(f["F17"], encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    check(rows[0] == F17_HEADER and rows[1:] == f17_rows(), "F17: content")
    check(len(rows) - 1 == EXPECTED["F17"]["rows"], "F17: rows")
    raw18 = f["F18"].read_bytes()
    check("Café".encode("cp1252") in raw18 and b";" in raw18.splitlines()[0], "F18: Windows-1252 + semicolon")
    try:
        raw18.decode("utf-8")
        check(False, "F18: must not be valid UTF-8")
    except UnicodeDecodeError:
        pass
    with open(f["F18"], encoding="cp1252", newline="") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    check([r[5] for r in rows[1:]] == EXPECTED["F18"]["codes"], "F18: codes")

    wb = pc.CalamineWorkbook.from_path(str(f["F19"]))
    check(wb.sheet_names[0] == "Data", "F19: first sheet Data")
    raw = wb.get_sheet_by_name("Data").to_python()
    check(raw[0] == F17_HEADER, "F19: header")
    check(raw[1][1] == 2.345 and raw[1][3] == dt.datetime(2026, 11, 5, 14, 30) and raw[1][5] == "00123",
          f"F19: row C01 {raw[1]}")
    check(raw[2][1] == 150.0, f"F19: formula cached value {raw[2][1]!r}")
    with zipfile.ZipFile(f["F19"]) as z:
        xml = z.read("xl/worksheets/sheet1.xml").decode()
    check(re.search(r'<c r="B4"[^>]*t="e"[^>]*><f>NA\(\)</f><v>#N/A</v></c>', xml) is not None,
          "F19: #N/A error cell")

    check(f["F21"].is_dir() and sha256(f["F21"] / "Sales_Oct.xlsx") == sha256(f["F02"]), "F21: folder with F02")
    report["checked"] = sorted(FILES)
    return report


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- P01 / P02 (performance pack)

P_HEADERS = ["Invoice No", "Invoice Date", "Customer ID", "Customer Name", "GSTIN", "State", "Category", "HSN",
             "Branch", "Salesperson", "Qty", "Rate", "Taxable Value", "GST Rate", "CGST", "SGST", "IGST",
             "Tax Amount", "Place of Supply", "Remarks"]
FIRST = ["Amit", "Priya", "Rahul", "Sneha", "Vikram", "Anjali", "Rohan", "Kavita", "Suresh", "Neha"]
LAST = ["Shah", "Patil", "Iyer", "Gupta", "Reddy"]
SALESPEOPLE = [f"{a} {b}" for a in FIRST for b in LAST]           # 50 names
HSN = ["8471", "8517", "3004", "1006", "6109"]


def _sql_list(xs) -> str:
    return "[" + ", ".join("'" + x.replace("'", "''") + "'" for x in xs) + "]"


def p01_sql(k: int, rows: int) -> str:
    """Row n (1-based) of file k; month k of 2026; Invoice No continues across files; all rows clean."""
    start, days = month(2026, k)
    return f"""
    WITH b AS (SELECT n, ({(k - 1)} * {rows}::BIGINT + n) AS g,
                      CAST(1000 + ((n - 1) % 100) * 10.25 AS DECIMAL(18,2)) AS tv,
                      {RATES}[((n - 1) % 5) + 1] AS rate,
                      ((n - 1) % 1000000) + 1 AS cid,
                      {_sql_list(STATES)}[((n - 1) % 4) + 1] AS state
               FROM range(1, {rows} + 1) r(n)),
         c AS (SELECT *, CAST(tv * rate / 100 AS DECIMAL(18,2)) AS tax, ((n - 1) % 10) + 1 AS qty FROM b)
    SELECT 'INV-' || lpad(g::VARCHAR, 9, '0') AS "Invoice No",
           strftime(DATE '{start.isoformat()}' + ((n - 1) % {days})::INTEGER, '%d-%m-%Y') AS "Invoice Date",
           'CUST-' || lpad(cid::VARCHAR, 7, '0') AS "Customer ID",
           {_sql_list(CUSTOMERS)}[((cid - 1) % 10) + 1] || ' ' || cid::VARCHAR AS "Customer Name",
           '27ABCDE' || lpad((n % 10000)::VARCHAR, 4, '0') || 'F1Z5' AS "GSTIN",
           state AS "State",
           'CAT-' || lpad((((n - 1) % 20) + 1)::VARCHAR, 2, '0') AS "Category",
           {_sql_list(HSN)}[((n - 1) % 5) + 1] AS "HSN",
           {_sql_list(BRANCHES)}[((n - 1) % 3) + 1] AS "Branch",
           {_sql_list(SALESPEOPLE)}[((n - 1) % 50) + 1] AS "Salesperson",
           qty AS "Qty",
           CAST(tv / qty AS DECIMAL(18,2)) AS "Rate",
           tv AS "Taxable Value",
           rate AS "GST Rate",
           CASE WHEN state = 'Maharashtra' THEN CAST(tax / 2 AS DECIMAL(18,2)) ELSE 0.00 END AS "CGST",
           CASE WHEN state = 'Maharashtra' THEN tax - CAST(tax / 2 AS DECIMAL(18,2)) ELSE 0.00 END AS "SGST",
           CASE WHEN state = 'Maharashtra' THEN 0.00 ELSE tax END AS "IGST",
           tax AS "Tax Amount",
           state AS "Place of Supply",
           CASE WHEN n % 10 = 0 THEN 'Checked' END AS "Remarks"
    FROM c ORDER BY n"""


def generate_perf(out: Path, rows_csv: int = 10_000_000, rows_xlsx: int = 1_000_000,
                  csv_files: int = 12, xlsx_files: int = 10) -> None:
    import duckdb
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for k in range(1, csv_files + 1):
        path = out / f"Perf_10M_{k:02d}.csv"
        print(f"  {path.name} ...", flush=True)
        con.execute(f"COPY ({p01_sql(k, rows_csv)}) TO '{path.as_posix()}' (HEADER, DELIMITER ',')")
    for k in range(1, xlsx_files + 1):
        path = out / f"Perf_xlsx_{k:02d}.xlsx"
        print(f"  {path.name} ...", flush=True)
        # same columns as P01; invoice numbers continue across the .xlsx files (k-th block of rows_xlsx)
        cur = con.execute(p01_sql(k, rows_xlsx))
        import xlsxwriter
        wb = xlsxwriter.Workbook(str(path), {"constant_memory": True, "strings_to_numbers": False})
        wb.set_properties({"created": FIXED_TIME})
        ws = wb.add_worksheet("Sales")
        ws.write_row(0, 0, P_HEADERS)
        dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
        i = 0
        while batch := cur.fetchmany(50_000):
            for r in batch:
                i += 1
                for c, v in enumerate(r):
                    if v is None:
                        continue
                    if c == 1:
                        ws.write_datetime(i, c, dt.datetime.strptime(v, "%d-%m-%Y"), dfmt)
                    elif isinstance(v, str):
                        ws.write_string(i, c, v)
                    else:
                        ws.write_number(i, c, float(v))
        wb.close()
    con.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--perf", action="store_true", help="also build P01/P02 (about 30 GB; takes a long time)")
    ap.add_argument("--perf-rows", type=int, default=None, help="rows per P01 file (default 10,000,000); "
                                                                "P02 uses a tenth")
    args = ap.parse_args(argv)
    if not args.verify_only:
        generate(args.out)
        print(f"F01-F21 written to {args.out}")
    verify(args.out)
    print("F01-F21 verified against the Fixtures tab")
    if args.perf:
        rows = args.perf_rows or 10_000_000
        generate_perf(args.out / "perf", rows_csv=rows, rows_xlsx=max(1, rows // 10))
        print(f"P01/P02 written to {args.out / 'perf'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
