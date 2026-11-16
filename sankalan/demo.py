"""Dummy data used by the automated tests and by `Sankalan.exe --self-test`.

Everything here is invented: company names, GSTINs (valid by checksum unless deliberately broken)
and amounts. The 'sales' set reproduces the run shown in the UI screens.
"""
from __future__ import annotations

import csv
import io
import random
import string
from datetime import date, datetime, timedelta
from pathlib import Path

import xlsxwriter

from .core.template import Template, new_column
from .core.validation import gstin_check_char

COMPANIES = ["Shree Ganesh Enterprises", "Blue Lotus Pvt Ltd", "Kaveri Textiles", "Sahyadri Foods LLP",
             "Indus Hardware Co", "Malabar Spices", "Narmada Logistics", "Tapti Agro Products",
             "Ganga Paper Mills", "Konark Electricals"]
STATES = [("27", "Maharashtra"), ("29", "Karnataka"), ("24", "Gujarat"), ("33", "Tamil Nadu"),
          ("07", "Delhi"), ("09", "Uttar Pradesh"), ("36", "Telangana"), ("32", "Kerala")]
MONTHS = [(4, "Apr"), (5, "May"), (6, "Jun"), (7, "Jul"), (8, "Aug"), (9, "Sep")]
HEADERS = ["Invoice No", "Invoice Date", "Company Name", "GSTIN", "Place of Supply", "Taxable Value",
           "Invoice Value"]


def make_gstin(rnd: random.Random, state="27") -> str:
    pan = "".join(rnd.choices(string.ascii_uppercase, k=3)) + rnd.choice("CPFHT") + rnd.choice(string.ascii_uppercase) \
        + "".join(rnd.choices(string.digits, k=4)) + rnd.choice(string.ascii_uppercase)
    first14 = state + pan + rnd.choice("123456789") + "Z"
    return first14 + gstin_check_char(first14)


def break_checksum(g: str) -> str:
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return g[:14] + chars[(chars.index(g[14]) + 1) % 36]


def _write_xlsx(path, sheets, hidden_rows=None, hidden_sheets=(), text_cols=()):
    """sheets: {name: [rows]}; rows may contain datetime/date; hidden_rows: {sheet: set(1-based)}."""
    hidden_rows = hidden_rows or {}
    wb = xlsxwriter.Workbook(str(path), {"strings_to_numbers": False})
    dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
    for name, rows in sheets.items():
        ws = wb.add_worksheet(name)
        for r, row in enumerate(rows):
            if (r + 1) in hidden_rows.get(name, set()):
                ws.set_row(r, None, None, {"hidden": True})
            for c, v in enumerate(row):
                if v is None:
                    continue
                if isinstance(v, (datetime, date)):
                    ws.write_datetime(r, c, datetime(v.year, v.month, v.day), dfmt)
                elif isinstance(v, str):
                    ws.write_string(r, c, v)
                else:
                    ws.write(r, c, v)
        if name in hidden_sheets:
            ws.hide()
    # xlsxwriter needs one visible active sheet
    for ws in wb.worksheets():
        if ws.name not in hidden_sheets:
            ws.activate()
            break
    wb.close()


def sales_template() -> Template:
    """'Acme Traders → Monthly Sales Register' as saved before this run (no alias for 'Inv Amt')."""
    E, W = "error", "warning"
    cols = [
        new_column("Invoice No", "text", True, rules=[{"type": "not_blank", "severity": E}]),
        new_column("Invoice Date", "date", True, rules=[{"type": "is_date", "severity": E},
                                                        {"type": "date_range", "severity": W,
                                                         "from": "01-04-2026", "to": "30-09-2026"}]),
        new_column("Company Name", "text", False),
        new_column("GSTIN", "text", True, aliases=["GSTIN/UIN", "GST No"],
                   rules=[{"type": "gstin_format", "severity": E}, {"type": "gstin_state", "severity": E},
                          {"type": "gstin_checksum", "severity": E}]),
        new_column("Place of Supply", "text", False, rules=[{"type": "not_blank", "severity": W}]),
        new_column("Taxable Value", "number", True, total=True,
                   rules=[{"type": "is_number", "severity": E}, {"type": "number_range", "severity": W, "min": 0}]),
        new_column("Invoice Value", "number", True, total=True,
                   rules=[{"type": "is_number", "severity": E}, {"type": "number_range", "severity": W, "min": 0}]),
    ]
    t = Template("Acme Traders", "Monthly Sales Register", cols,
                 duplicate_keys=[{"columns": ["GSTIN", "Invoice No"], "severity": E}])
    t.input["pattern"] = "Sales_*.xlsx"
    return t


def make_sales_set(folder, rows_per_file=300, seed=7, fixed=False):
    """Six monthly files with the problems from the UI screens. Returns a dict of expectations.
    fixed=True writes the same files with the three errors corrected (the 're-check' scenario)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)
    buyers = [(c, make_gstin(rnd, STATES[i % len(STATES)][0]), STATES[i % len(STATES)][1])
              for i, c in enumerate(COMPANIES)]
    exp = {"files": {}, "rows": 0, "taxable": 0.0, "invoice": 0.0, "errors": [], "warnings": [],
           "hidden_rows": {}, "hidden_sheets": {}}
    inv_no = 400
    apr_first = None
    for m, mon in MONTHS:
        name = f"Sales_{mon}-2026.xlsx"
        data = []
        for i in range(rows_per_file):
            inv_no += 1
            comp, g, pos = buyers[rnd.randrange(len(buyers))]
            d = date(2026, m, 1 + rnd.randrange(28))
            tv = round(rnd.uniform(1000, 250000), 2)
            data.append([f"INV/26-27/{inv_no:04d}", d, comp, g, pos, tv, round(tv * 1.18, 2)])
        if m == 4:
            apr_first = list(data[5])
        hidden_rows, hidden_sheets, sheets = {}, (), None
        hdr = list(HEADERS)
        rows = [hdr] + data
        sheet = "Sales"
        if m == 5 and not fixed:      # cross-file duplicate of an April invoice
            data[8][0], data[8][3] = apr_first[0], apr_first[3]
            exp["errors"].append(("duplicates", name, 10))
        if m == 6:                     # 12 hidden rows; one GSTIN with a wrong check character
            hidden = set(range(40, 52))
            hidden_rows = {sheet: hidden}
            exp["hidden_rows"][name] = 12
            if not fixed:
                k = min(212, len(data) - 1)
                data[k][3] = break_checksum(data[k][3])
                exp["errors"].append(("gstin_checksum", name, k + 2))
        if m == 7:                     # title rows, header on row 3, 'Inv Amt', blank POS, total row
            hdr[6] = "Inv Amt"
            blanks = list(range(2, 2 + 14))
            for b in blanks:
                data[b][4] = None
                exp["warnings"].append(("not_blank", name, b + 4))
            total_row = ["Total", None, None, None, None, round(sum(r[5] for r in data), 2),
                         round(sum(r[6] for r in data), 2)]
            rows = [["Acme Traders — Sales July 2026"], [], hdr] + data + [total_row]
        if m == 8:                     # hidden sheet 'Old' first; a 14-character GSTIN
            hidden_sheets = ("Old",)
            exp["hidden_sheets"][name] = ["Old"]
            if not fixed:
                k = min(1085, len(data) - 1)
                data[k][3] = data[k][3][:14]
                exp["errors"].append(("gstin_format", name, k + 2))
        if m == 9:                     # 'GST No' header (alias), text dates/amounts, one credit note
            hdr[3] = "GST No"
            for r in data[:20]:
                r[1] = r[1].strftime("%d/%m/%Y")
                r[5] = "₹ " + f"{r[5]:,.2f}"
            data[20][5] = "1,23,456.00"
            data[20][6] = 145678.08
            data[21][5], data[21][6] = "(1,000.00)", "(1,180.00)"
            exp["warnings"] += [("number_range", name, 23), ("number_range", name, 23)]
        if m != 7:
            rows = [hdr] + data
        sheets = {"Old": [HEADERS, ["OLD-1", date(2025, 8, 1), "x", "y", "z", 1, 1]], sheet: rows} \
            if hidden_sheets else {sheet: rows}
        _write_xlsx(folder / name, sheets, hidden_rows, hidden_sheets)
        # expected totals exclude hidden rows
        from .core.convert import to_number
        for ri, r in enumerate(data):
            orig_row = ri + (4 if m == 7 else 2)
            if orig_row in hidden_rows.get(sheet, set()):
                continue
            exp["rows"] += 1
            exp["taxable"] += to_number(r[5])[0]
            exp["invoice"] += to_number(r[6])[0]
        exp["files"][name] = len(data) - len(hidden_rows.get(sheet, ()))
    (folder / "~$Sales_Sep-2026.xlsx").write_bytes(b"lock")
    exp["taxable"], exp["invoice"] = round(exp["taxable"], 2), round(exp["invoice"], 2)
    return exp


def make_misc_set(folder, seed=11):
    """Files for the other input features. Returns {feature: path}."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)
    out = {}
    g = [make_gstin(rnd, s) for s, _ in STATES]
    base = [["P-001", "02-09-2026", "Kaveri Textiles", g[0], "B2B", 1000.0],
            ["P-002", "03-09-2026", "Café Mocha Traders", g[1], "B2C", 2500.5],
            ["P-003", "04-09-2026", "Konark Electricals", g[2], "Export", 300.0]]
    hdr = ["Bill No", "Bill Date", "Supplier", "GSTIN", "Invoice Type", "Amount"]
    # CSV variants (IN-4)
    def csv_bytes(delim, enc):
        s = io.StringIO()
        w = csv.writer(s, delimiter=delim)
        w.writerow(hdr)
        for r in base:
            w.writerow(r)
        return s.getvalue().encode(enc)
    out["csv_bom_comma"] = folder / "bills_bom_comma.csv"
    out["csv_bom_comma"].write_bytes(b"\xef\xbb\xbf" + csv_bytes(",", "utf-8"))
    out["csv_utf8_semicolon"] = folder / "bills_utf8_semicolon.csv"
    out["csv_utf8_semicolon"].write_bytes(csv_bytes(";", "utf-8"))
    out["csv_cp1252_tab"] = folder / "bills_cp1252_tab.txt"
    out["csv_cp1252_tab"].write_bytes(csv_bytes("\t", "cp1252"))
    out["txt_pipe"] = folder / "bills_pipe.txt"
    out["txt_pipe"].write_bytes(csv_bytes("|", "utf-8"))
    # .xls with a hidden row and real date cells
    import xlwt
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Bills")
    df = xlwt.easyxf(num_format_str="DD-MM-YYYY")
    for c, h in enumerate(hdr):
        ws.write(0, c, h)
    for r, row in enumerate(base + [["P-004", "05-09-2026", "Hidden Row Co", g[3], "B2B", 9999.0]], start=1):
        for c, v in enumerate(row):
            if c == 1:
                ws.write(r, c, datetime.strptime(v, "%d-%m-%Y"), df)
            else:
                ws.write(r, c, v)
    ws.row(4).hidden = True
    out["xls"] = folder / "bills_old_format.xls"
    wb.save(str(out["xls"]))
    # .xlsm (macro-enabled extension)
    out["xlsm"] = folder / "bills_macro.xlsm"
    _write_xlsx(out["xlsm"], {"Bills": [hdr] + base})
    # multi-sheet workbook (IN-5)
    out["multi"] = folder / "regions.xlsx"
    _write_xlsx(out["multi"], {"Summary": [["Region", "Total"], ["North", 1], ["South", 2]],
                               "Sales North": [hdr] + base[:2], "Sales South": [hdr] + base[2:]})
    # password-protected (IN-9)
    plain = folder / "_plain_for_password.xlsx"
    _write_xlsx(plain, {"Bills": [hdr] + base})
    import msoffcrypto
    out["password"] = folder / "bills_protected.xlsx"
    with open(plain, "rb") as fi, open(out["password"], "wb") as fo:
        msoffcrypto.OfficeFile(fi).encrypt("acme@123", fo)
    plain.unlink()
    # corrupt file
    out["corrupt"] = folder / "broken.xlsx"
    out["corrupt"].write_bytes(b"this is not really an excel file")
    # leading zeros kept as text (MAP-9) + blank rows + 'Grand Total' trailer (IN-7, IN-8)
    out["zeros"] = folder / "zeros_and_totals.xlsx"
    _write_xlsx(out["zeros"], {"Bills": [hdr, ["00123", date(2026, 9, 6), "A", g[4], "B2B", 10.0], [],
                                         ["00456", date(2026, 9, 7), "B", g[5], "B2C", 20.0], [None] * 6,
                                         ["Grand Total", None, None, None, None, 30.0]]})
    # file whose header row is not first and has no known names (heuristic detection)
    out["title_rows"] = folder / "title_rows.xlsx"
    _write_xlsx(out["title_rows"], {"Bills": [["Purchase bills"], ["Printed on 01-10-2026"], [], hdr] + base})
    return out


def purchase_template() -> Template:
    """A second client template using PAN, allowed values and date range checks."""
    E, W = "error", "warning"
    cols = [
        new_column("Bill No", "text", True, rules=[{"type": "not_blank", "severity": E}]),
        new_column("Bill Date", "date", True, rules=[{"type": "is_date", "severity": E},
                                                     {"type": "date_range", "severity": E,
                                                      "from": "01-09-2026", "to": "30-09-2026"}]),
        new_column("Supplier", "text", False),
        new_column("GSTIN", "text", True, rules=[{"type": "gstin_format", "severity": E},
                                                  {"type": "gstin_checksum", "severity": E}]),
        new_column("Invoice Type", "text", False, rules=[{"type": "allowed_values", "severity": E,
                                                          "values": ["B2B", "B2C", "Export"]}]),
        new_column("Amount", "number", True, total=True, rules=[{"type": "is_number", "severity": E}]),
    ]
    return Template("Blue Lotus Pvt Ltd", "Purchase Register", cols,
                    duplicate_keys=[{"columns": ["Bill No"], "severity": E}])


def make_perf_set(folder, files=50, rows=10_000, seed=3):
    """NF-3: 50 files x 10,000 rows = 500,000 rows."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)
    gst = [make_gstin(rnd, s) for s, _ in STATES]
    total = 0.0
    n = 0
    for f in range(files):
        wb = xlsxwriter.Workbook(str(folder / f"Perf_{f:02d}.xlsx"), {"constant_memory": True})
        ws = wb.add_worksheet("Sales")
        dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
        for c, h in enumerate(HEADERS):
            ws.write_string(0, c, h)
        for r in range(1, rows + 1):
            n += 1
            tv = round(rnd.uniform(100, 99999), 2)
            total += tv
            ws.write_string(r, 0, f"P{f:02d}-{r:06d}")
            ws.write_datetime(r, 1, datetime(2026, 9, 1 + r % 28), dfmt)
            ws.write_string(r, 2, COMPANIES[r % len(COMPANIES)])
            ws.write_string(r, 3, gst[r % len(gst)])
            ws.write_string(r, 4, STATES[r % len(STATES)][1])
            ws.write_number(r, 5, tv)
            ws.write_number(r, 6, round(tv * 1.18, 2))
        wb.close()
    return {"rows": n, "taxable": round(total, 2)}
