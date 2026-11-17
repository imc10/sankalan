"""Phase 0 spike: rough read speed on one core (R2, R4). Results go in tools/spikes/RESULTS.md.

  xlsx: python-calamine values -> staged text CSV, plus the streaming sheet-XML scan for hidden rows / error cells.
  csv:  csv module read -> staged text CSV (one core, as T12 requires for a single large CSV).

Run: .venv\\Scripts\\python tools\\spikes\\spike_read_speed.py [--xlsx-rows 1000000] [--csv-rows 10000000]
"""
import argparse
import csv
import datetime as dt
import io
import re
import shutil
import tempfile
import time
import zipfile
from decimal import Decimal
from pathlib import Path

import duckdb
import python_calamine as pc
import xlsxwriter

STATES = ["Maharashtra", "Gujarat", "Karnataka", "Delhi"]
RATES = [0, 5, 12, 18, 28]


def canon(v):
    """Staged text form (Tech spec, Read): shortest exact decimal, no exponent; dates YYYY-MM-DD; text as is."""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return format(Decimal(repr(v)), "f")
    if isinstance(v, int):
        return str(v)
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    return str(v)


def make_xlsx(path, rows):
    wb = xlsxwriter.Workbook(str(path), {"constant_memory": True})
    ws = wb.add_worksheet("Sales")
    dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
    ws.write_row(0, 0, ["Invoice No", "Invoice Date", "Customer", "GSTIN", "State", "Taxable Value", "GST Rate",
                        "Tax Amount"])
    base = dt.datetime(2026, 10, 1)
    for n in range(1, rows + 1):
        tv = 1000 + ((n - 1) % 100) * 10.25
        rate = RATES[(n - 1) % 5]
        ws.write_string(n, 0, f"INV-{n:07d}")
        ws.write_datetime(n, 1, base + dt.timedelta(days=(n - 1) % 31), dfmt)
        ws.write_string(n, 2, f"Customer {(n - 1) % 1000}")
        ws.write_string(n, 3, f"27ABCDE{n % 10000:04d}F1Z5")
        ws.write_string(n, 4, STATES[(n - 1) % 4])
        ws.write_number(n, 5, tv)
        ws.write_number(n, 6, rate)
        ws.write_number(n, 7, round(tv * rate / 100, 2))
    wb.close()


ROW_TAG = re.compile(rb'<row [^>]*?hidden="1"[^>]*>')
ROW_NUM = re.compile(rb'r="(\d+)"')
ERR_CELL = re.compile(rb'<c r="([A-Z]+\d+)"[^>]*?t="e"[^>]*>(?:<f>.*?</f>)?<v>([^<]*)</v>')


def xml_scan(path):
    """Streaming scan of the decompressed sheet XML: hidden rows and error cells."""
    hidden, errors = [], []
    with zipfile.ZipFile(path) as z, z.open("xl/worksheets/sheet1.xml") as f:
        tail = b""
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            buf = tail + chunk
            cut = buf.rfind(b">") + 1
            for m in ROW_TAG.finditer(buf, 0, cut):
                hidden.append(int(ROW_NUM.search(m.group(0)).group(1)))
            errors += ERR_CELL.findall(buf, 0, cut)
            tail = buf[cut:]
    return hidden, errors


def time_xlsx(work, rows):
    path = work / "big.xlsx"
    t0 = time.perf_counter()
    make_xlsx(path, rows)
    gen = time.perf_counter() - t0
    print(f"\n== xlsx {rows:,} rows x 8: generated in {gen:.0f} s, {path.stat().st_size / 1e6:.0f} MB")

    t0 = time.perf_counter()
    hidden, errors = xml_scan(path)
    scan = time.perf_counter() - t0
    print(f"  XML scan (hidden rows + error cells): {scan:.1f} s  hidden={len(hidden)} errors={len(errors)}")

    out = work / "staged_xlsx.csv"
    t0 = time.perf_counter()
    wb = pc.CalamineWorkbook.from_path(str(path))
    sh = wb.get_sheet_by_name("Sales")
    t_open = time.perf_counter() - t0
    n = 0
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        it = sh.iter_rows()
        header = next(it)
        w.writerow(["_src_row"] + header)
        for i, row in enumerate(it, start=2):
            w.writerow([i] + [canon(v) for v in row])
            n += 1
    read = time.perf_counter() - t0
    print(f"  calamine open {t_open:.1f} s; open+read+stage {read:.1f} s = {n / read:,.0f} rows/s on one core")
    print(f"  => 10M rows from 10 files on 3 worker processes (4-core laptop): ~{1e7 / (n / read) / 3 / 60:.1f} min "
          f"(+ XML scan {scan * 10 / 3 / 60:.1f} min if run serially per file)")
    return read, scan


def time_csv(work, rows):
    src = work / "big.csv"
    con = duckdb.connect()
    t0 = time.perf_counter()
    con.execute(f"""COPY (SELECT 'INV-' || lpad(i::VARCHAR, 9, '0') AS "Invoice No",
                strftime(DATE '2026-01-01' + (i % 31)::INTEGER, '%d-%m-%Y') AS "Invoice Date",
                'CUST-' || lpad((i % 1000000 + 1)::VARCHAR, 7, '0') AS "Customer ID",
                'Customer ' || (i % 5000)::VARCHAR AS "Customer Name",
                '27ABCDE' || lpad((i % 10000)::VARCHAR, 4, '0') || 'F1Z5' AS "GSTIN",
                ['Maharashtra','Gujarat','Karnataka','Delhi'][(i % 4) + 1] AS "State",
                'CAT-' || lpad((i % 20 + 1)::VARCHAR, 2, '0') AS "Category",
                '8471' AS "HSN", 'Pune' AS "Branch", 'Person ' || (i % 50)::VARCHAR AS "Salesperson",
                (i % 7 + 1) AS "Qty", 125.50 AS "Rate",
                CAST(1000 + (i % 100) * 10.25 AS DECIMAL(18,2)) AS "Taxable Value",
                [0,5,12,18,28][(i % 5) + 1] AS "GST Rate", 0.00 AS "CGST", 0.00 AS "SGST", 0.00 AS "IGST",
                CAST((1000 + (i % 100) * 10.25) * [0,5,12,18,28][(i % 5) + 1] / 100 AS DECIMAL(18,2)) AS "Tax Amount",
                'Maharashtra' AS "Place of Supply", CASE WHEN i % 10 = 0 THEN 'checked' ELSE '' END AS "Remarks"
             FROM range({rows}) r(i)) TO '{src.as_posix()}' (HEADER)""")
    con.close()
    print(f"\n== csv {rows:,} rows x 20: generated in {time.perf_counter() - t0:.0f} s, "
          f"{src.stat().st_size / 1e9:.2f} GB")
    out = work / "staged_csv.csv"
    t0 = time.perf_counter()
    blank = 0
    with open(src, encoding="utf-8", newline="") as fi, open(out, "w", encoding="utf-8", newline="") as fo:
        r = csv.reader(fi)
        w = csv.writer(fo)
        w.writerow(["_src_row"] + next(r))
        for i, row in enumerate(r, start=2):
            if all(not c.strip(" ") for c in row):
                blank += 1
                continue
            row.insert(0, i)
            w.writerow(row)
    secs = time.perf_counter() - t0
    print(f"  read+stage on one core: {secs:.0f} s = {rows / secs:,.0f} rows/s (PERF-1 limit 120 s for the whole load)")
    # DuckDB reading the staged text afterwards (the Convert stage input)
    con = duckdb.connect()
    t0 = time.perf_counter()
    n = con.execute(f"SELECT count(*) FROM read_csv('{out.as_posix()}', all_varchar=true, header=true)").fetchone()[0]
    print(f"  DuckDB re-reads staged text ({n:,} rows) in {time.perf_counter() - t0:.1f} s")
    con.close()
    return secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx-rows", type=int, default=1_000_000)
    ap.add_argument("--csv-rows", type=int, default=10_000_000)
    args = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix="sankalan_spike_"))
    try:
        if args.xlsx_rows:
            time_xlsx(work, args.xlsx_rows)
        if args.csv_rows:
            time_csv(work, args.csv_rows)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
