"""Phase 0 spike: what python-calamine gives us (T11, CONV-05, R5). Results go in tools/spikes/RESULTS.md.

Run: .venv\\Scripts\\python tools\\spikes\\spike_calamine.py
"""
import datetime as dt
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import python_calamine as pc
import xlsxwriter


def build(path):
    wb = xlsxwriter.Workbook(str(path))
    dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
    dtfmt = wb.add_format({"num_format": "dd-mm-yyyy hh:mm"})
    ws = wb.add_worksheet("Data")
    ws.write_row(0, 0, ["Kind", "Value"])
    rows = [
        ("number 2.345", 2.345),
        ("number 0.1+0.2", 0.1 + 0.2),
        ("number 1e-7", 1e-7),
        ("number 12345678901234567", 12345678901234567),
        ("integer-valued float 150.0", 150.0),
        ("text 00123", "00123"),
        ("text with spaces", " A1 "),
        ("spaces only", "   "),
        ("bool", True),
    ]
    for r, (k, v) in enumerate(rows, start=1):
        ws.write(r, 0, k)
        if isinstance(v, str):
            ws.write_string(r, 1, v)
        else:
            ws.write(r, 1, v)
    r = len(rows) + 1
    ws.write(r, 0, "formula =100*1.5")
    ws.write_formula(r, 1, "=100*1.5", None, 150)
    ws.write(r + 1, 0, "error #N/A")
    ws.write_formula(r + 1, 1, "=NA()", None, "#N/A")
    ws.write(r + 2, 0, "error #REF!")
    ws.write_formula(r + 2, 1, "=#REF!", None, "#REF!")
    ws.write(r + 3, 0, "date 05-11-2026")
    ws.write_datetime(r + 3, 1, dt.datetime(2026, 11, 5), dfmt)
    ws.write(r + 4, 0, "date-time 05-11-2026 14:30")
    ws.write_datetime(r + 4, 1, dt.datetime(2026, 11, 5, 14, 30), dtfmt)
    ws.write(r + 5, 0, "hidden row")
    ws.write(r + 5, 1, 99999.99)
    ws.set_row(r + 5, None, None, {"hidden": True})
    ws.write(r + 6, 0, "after hidden")
    ws.write(r + 6, 1, 1)
    hid = wb.add_worksheet("Hidden")
    hid.write(0, 0, "x")
    hid.hide()
    vh = wb.add_worksheet("VeryHidden")
    vh.write(0, 0, "y")
    vh.very_hidden()
    wb.add_worksheet("Empty")
    wb.close()


def main():
    print("python-calamine", pc.__version__ if hasattr(pc, "__version__") else "?")
    work = Path(tempfile.mkdtemp(prefix="sankalan_spike_"))
    try:
        path = work / "probe.xlsx"
        build(path)
        wb = pc.CalamineWorkbook.from_path(str(path))
        print("\n== sheets with visibility")
        for m in wb.sheets_metadata:
            print(f"  {m.name!r:14} type={m.typ} visible={m.visible}")
        sh = wb.get_sheet_by_name("Data")
        print("\n== sheet attributes:", [a for a in dir(sh) if not a.startswith("_")])
        print(f"  dimensions: height={sh.height} width={sh.width} start={sh.start} end={sh.end}")
        print("\n== values (to_python)")
        for row in sh.to_python():
            print(f"  {row[0]!r:32} -> {row[1]!r} ({type(row[1]).__name__})")
        print("\n== hidden rows exposed by calamine?")
        names = [a for a in dir(sh) if "hidden" in a.lower() or "row" in a.lower()]
        print("  attributes mentioning row/hidden:", names)
        print("  'hidden row' still present in to_python():",
              any(r[0] == "hidden row" for r in sh.to_python()))
        print("\n== sheet XML hidden-row scan")
        with zipfile.ZipFile(path) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        hidden = [int(m.group(1)) for m in re.finditer(r'<row r="(\d+)"[^>]*hidden="1"', xml)]
        print("  rows with hidden=\"1\":", hidden)
        print("\n== iter_rows streaming available:", hasattr(sh, "iter_rows"))
        print("\n== empty sheet:", wb.get_sheet_by_name("Empty").to_python())
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
