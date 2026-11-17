"""`Sankalan --self-test --report <file.json>`: a smoke test of the packaged app.

Generates dummy files in a temp folder, runs the full pipeline (read, map, validate, block on errors,
override, re-check after fixes, write .xlsx and .csv, totals check), opens the main window off-screen,
and writes a JSON report. Exit code 0 = all checks passed.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path


def run_self_test(argv=None):
    argv = list(sys.argv if argv is None else argv)
    report_path = Path(argv[argv.index("--report") + 1]) if "--report" in argv else None
    checks = []

    def check(name, cond, detail=""):
        checks.append({"check": name, "passed": bool(cond), "detail": str(detail)})

    work = Path(tempfile.mkdtemp(prefix="sankalan_selftest_"))
    t0 = time.time()
    try:
        from .core.session import Session
        from .core.template import TemplateStore
        from .demo import make_sales_set, sales_template

        exp = make_sales_set(work / "sales", rows_per_file=120)
        t = sales_template()
        t.output["folder"] = str(work / "out")
        s = Session(t)
        s.add([work / "sales"])
        check("lock file skipped", any(x.reason == "Excel lock file" for x in s.skipped))
        s.load()
        check("six files read", len(s.good_sources()) == 6, len(s.good_sources()))
        jul = [f for f in s.sources if f.name.startswith("Sales_Jul")][0]
        check("header detected on row 3", jul.header_row == 3, jul.header_row)
        jun = [f for f in s.sources if f.name.startswith("Sales_Jun")][0]
        check("hidden rows skipped", jun.hidden_rows == 12, jun.hidden_rows)
        check("Inv Amt unmapped before mapping", any(tgt == "Invoice Value" for _, tgt in s.mapping_problems()))
        s.set_mapping(jul, "Invoice Value", "Inv Amt", save_alias=True)
        check("mapping complete", not s.mapping_problems())
        v = s.validate()
        check("3 errors found", len(v.errors) == 3, [i.message for i in v.errors])
        try:
            s.write()
            check("errors block output", False)
        except PermissionError:
            check("errors block output", True)
        res = s.write(override_errors=True)
        check("override writes output", res.path.exists() and res.errors_overridden == 3)
        check("totals match (override)", res.totals_match)
        # fixed files -> re-check -> clean run
        shutil.rmtree(work / "sales")
        exp2 = make_sales_set(work / "sales", rows_per_file=120, fixed=True)
        s.load()
        v2 = s.validate()
        check("no errors after fix", len(v2.errors) == 0, len(v2.errors))
        res2 = s.write(overwrite=True)
        check("rows written", res2.rows_written == exp2["rows"], (res2.rows_written, exp2["rows"]))
        tv = [x for x in res2.totals if x.column == "Taxable Value"][0]
        check("taxable total equals input", round(tv.output_total, 2) == exp2["taxable"],
              (tv.output_total, exp2["taxable"]))
        s.template.output["format"] = "csv"
        res3 = s.write(overwrite=True)
        check("csv written, totals match", res3.path.suffix == ".csv" and res3.totals_match)
        store = TemplateStore(work / "templates")
        s.save_template(store)
        check("template saved with alias", "Inv Amt" in store.list()[0].column("Invoice Value")["aliases"])
        # GUI smoke test, off-screen
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # headless Linux only
        from PySide6.QtWidgets import QApplication
        from .ui import style as S
        from .ui.app import MainWindow
        app = QApplication.instance() or QApplication([])
        app.setStyleSheet(S.QSS)
        w = MainWindow(store_folder=work / "templates")
        w.show()
        app.processEvents()
        check("main window opens", w.isVisible() and w.windowTitle() == "Sankalan")
        check("template listed on home screen", w.pages["home"].table.rowCount() == 1)
        shot = work / "home.png"
        w.grab().save(str(shot))
        check("window renders", shot.exists() and shot.stat().st_size > 1000)
        if report_path:
            shutil.copy(shot, report_path.with_suffix(".png"))
        w.close()
    except Exception:
        check("no unexpected exception", False, traceback.format_exc())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    passed = all(c["passed"] for c in checks)
    report = {"result": "PASS" if passed else "FAIL", "passed": passed, "seconds": round(time.time() - t0, 1), "checks": checks,
              "python": sys.version, "platform": sys.platform}
    text = json.dumps(report, indent=2)
    if report_path:
        report_path.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if passed else 1
