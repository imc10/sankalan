r"""One-off: build tests/fixtures/static/Sales_Old.xls (F11: F02 layout, 100 rows, Excel 97-2003).

xlwt is no longer a dependency, so the file is checked in. To rebuild it:
    pip install --target <scratch> xlwt==1.3.0
    set PYTHONPATH=<scratch>
    python tests\fixtures\make_static_xls.py
"""
import datetime as dt
from pathlib import Path

import xlwt

from generate import HEADERS, STATIC, f00_rows

FIXED_TIME = dt.datetime(2026, 11, 16)


def main():
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sales")
    dfmt = xlwt.easyxf(num_format_str="DD-MM-YYYY")
    for c, h in enumerate(HEADERS):
        ws.write(0, c, h)
    for r, row in enumerate(f00_rows(100, 10000, 2026, 10), start=1):
        for c, v in enumerate(row):
            if isinstance(v, dt.date):
                ws.write(r, c, dt.datetime.combine(v, dt.time()), dfmt)
            elif isinstance(v, str):
                ws.write(r, c, v)
            else:
                ws.write(r, c, float(v))
    STATIC.mkdir(exist_ok=True)
    out = STATIC / "Sales_Old.xls"
    wb.save(str(out))
    print("wrote", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
