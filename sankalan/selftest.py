r"""``Sankalan.exe --self-test [--report <file.json>] [--expect-signed] [--no-window]``: a smoke test of the
installed or packaged app (Tech spec: Tests and release acceptance, "Self-test after install").

Everything happens in a new temporary folder that stands in for %LOCALAPPDATA%\Sankalan and %TEMP%\Sankalan, so
the user's own data folder, settings and log are never opened. Checks:

- DuckDB 2.0 and python-calamine load; the DuckDB configuration is hardened and locked (SEC-1).
- A small run end to end on generated files (one .xlsx with a hidden row, one CSV with a later duplicate): probe,
  read in reader workers (the same exe started again in worker mode), convert, validate, override, outputs,
  totals check (Input = Loaded + Left out), commit, CSV export with BOM; staging and temp emptied (SEC-4).
- Re-opening the data folder backs up the catalogue and leaves it at the current schema version, as the first start
  after an update does (T10, Install/update).
- Only the allowed compiled packages are loaded (Smart App Control, T2).
- The window opens titled "Sankalan" (skipped with ``--no-window``).
- Packaged app on Windows: every .exe/.dll/.pyd is checked with Get-AuthenticodeSignature. Unsigned files fail the
  check only with ``--expect-signed`` (the build passes it when it signed the app); otherwise they are reported.

Exit code 0 when every check passed. The JSON report holds no cell values beyond the generated sample.
"""
from __future__ import annotations

import datetime as dt
import gc
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from sankalan import APP_NAME, __version__

# The sample: 120 rows in the .xlsx (plus one hidden row that must not load), 80 rows in the CSV plus one row that
# repeats an .xlsx invoice number (a later duplicate, left out by the override, T18).
XLSX_ROWS = 120
CSV_ROWS = 80
HIDDEN_AFTER = 10                   # the hidden row sits after this data row
HIDDEN_VALUE = Decimal("999999.99")
DUPLICATE_OF = 7
HEADERS = ["Invoice No", "Invoice Date", "Customer", "Taxable Value", "GST Rate"]
OVERRIDE_REASON = "Self-test: later duplicate left out"
ALLOWED_COMPILED = {"PySide6", "shiboken6", "_duckdb", "duckdb", "python_calamine"}
SIGNED_SUFFIXES = (".exe", ".dll", ".pyd")
NO_WINDOW = 0x08000000              # CREATE_NO_WINDOW: no console flashes for the signature check


# ---------------------------------------------------------------------------------------------- sample files
def sample_row(i: int) -> tuple[str, dt.date, str, Decimal, int]:
    return (f"SLF-{i:05d}", dt.date(2026, 10, 1) + dt.timedelta(days=i % 28), f"Customer {i % 7}",
            Decimal(f"{i * 101}.{i % 100:02d}"), (5, 12, 18)[i % 3])


def _cell(ref: str, value) -> str:
    if isinstance(value, dt.date):
        serial = (value - dt.date(1899, 12, 30)).days
        return f'<c r="{ref}" s="1"><v>{serial}</v></c>'
    if isinstance(value, (int, Decimal)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def write_xlsx(path: Path, rows: list[tuple], hidden: set[int]) -> None:
    """A minimal workbook, standard library only (no writer package ships with the app): one sheet "Sales",
    inline strings, dates styled as dates, rows in ``hidden`` (1-based sheet rows) hidden."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    lines = []
    for r, row in enumerate([tuple(HEADERS), *rows], start=1):
        cells = "".join(_cell(f"{chr(65 + c)}{r}", v) for c, v in enumerate(row))
        attr = ' hidden="1"' if r in hidden else ""
        lines.append(f'<row r="{r}"{attr}>{cells}</row>')
    sheet = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="{main}">'
             f'<sheetData>{"".join(lines)}</sheetData></worksheet>')
    parts = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels":
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{pkg}">'
            f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook xmlns="{main}" xmlns:r="{rel}">'
            '<sheets><sheet name="Sales" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{pkg}">'
            f'<Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{rel}/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml":
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<styleSheet xmlns="{main}">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
            '</styleSheet>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in parts.items():
            z.writestr(name, text)


def write_samples(folder: Path) -> dict:
    """The two source files and the figures a correct run must show."""
    folder.mkdir(parents=True, exist_ok=True)
    xrows = [sample_row(i) for i in range(1, XLSX_ROWS + 1)]
    hidden_row = ("SLF-HIDDEN", dt.date(2026, 10, 1), "Hidden", HIDDEN_VALUE, 18)
    sheet_rows = xrows[:HIDDEN_AFTER] + [hidden_row] + xrows[HIDDEN_AFTER:]
    xlsx = folder / "Sales_Oct.xlsx"
    write_xlsx(xlsx, sheet_rows, hidden={HIDDEN_AFTER + 2})       # +1 header row, +1 to sit after the data row
    crows = [sample_row(i) for i in range(XLSX_ROWS + 1, XLSX_ROWS + CSV_ROWS + 1)]
    dup = sample_row(DUPLICATE_OF)
    csv = folder / "Sales_Nov.csv"
    with open(csv, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(HEADERS) + "\r\n")
        for inv, d, cust, val, rate in [*crows, dup]:
            f.write(f"{inv},{d:%d-%m-%Y},{cust},{val},{rate}\r\n")
    every = xrows + crows + [dup]
    return {"xlsx": xlsx, "csv": csv, "rows": len(every), "loaded": len(every) - 1, "left_out": 1,
            "input": sum(r[3] for r in every), "left_out_value": dup[3]}


# ---------------------------------------------------------------------------------------------- the checks
class Checks:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, name: str, passed, detail="", skipped: bool = False) -> bool:
        self.items.append({"check": name, "passed": bool(passed), "skipped": skipped, "detail": str(detail)})
        return bool(passed)

    def skip(self, name: str, why: str) -> None:
        self.add(name, True, why, skipped=True)

    @property
    def passed(self) -> bool:
        return bool(self.items) and all(c["passed"] for c in self.items)


def _job(storage, name, work, cancellable=True):
    j = storage.runner.run(name, work, cancellable=cancellable)
    if j.error is not None:
        raise j.error
    return j.result


def _empty(folder: Path) -> bool:
    return not folder.exists() or not any(folder.iterdir())


def check_engines(checks: Checks, sample: dict) -> None:
    import duckdb
    import python_calamine
    checks.add("DuckDB 2.0 loads", duckdb.__version__.startswith("2.0."), duckdb.__version__)
    rows = python_calamine.CalamineWorkbook.from_path(str(sample["xlsx"])).get_sheet_by_name("Sales").to_python()
    checks.add("python-calamine reads .xlsx", len(rows) == XLSX_ROWS + 2 and rows[0][0] == HEADERS[0], len(rows))


def check_run(checks: Checks, storage, sample: dict, out: Path) -> None:
    """A run from Files to Commit, then an export of its data."""
    from sankalan.db import connection
    from sankalan.exporting import export
    from sankalan.model import definition as d
    from sankalan.model import export as ex
    from sankalan.model.rule import NOT_BLANK, UNIQUE, Rule, with_type_rules
    from sankalan.model.template import Column, DefaultOutput, Template
    from sankalan.query import catalogue as q
    from sankalan.run import pipeline as p
    from sankalan.runs import export_items

    con = storage.con
    cfg = connection.settings(con)
    checks.add("DuckDB offline and locked",
               str(cfg.get("enable_external_access")).lower() == "false"
               and str(cfg.get("lock_configuration")).lower() == "true" and connection.configuration_locked(con),
               {k: cfg.get(k) for k in ("enable_external_access", "lock_configuration")})

    columns = [Column("c001", "Invoice No"), Column("c002", "Invoice Date", "Date", date_format="DD-MM-YYYY"),
               Column("c003", "Customer"), Column("c004", "Taxable Value", "Number", decimals=2, totals_check=True),
               Column("c005", "GST Rate", "Number", decimals=0)]
    rules = with_type_rules(columns, [Rule("r1", "c001", NOT_BLANK), Rule("r2", "c001", UNIQUE)])
    by_rate = d.Definition("", [], [d.Group("c005")], [d.Measure("c004", d.SUM, "Taxable")])
    client = q.insert_client(con, "Self-test client")
    tid = q.create_template(con, Template("", client, "Self-test sales", columns=columns, rules=rules,
                                          outputs=[DefaultOutput("By GST rate", by_rate.to_dict())],
                                          export={"pattern": "{Template}_{RunID}_{Output}", "delimiter": ",",
                                                  "encoding": "utf-8-sig"}))
    template = q.load_template(con, tid)
    sess = p.RunSession(storage.folder, template, workers=2)       # two files: two reader worker processes
    files = _job(storage, "Add files", lambda ctx: sess.add_files(ctx, [sample["xlsx"], sample["csv"]]))
    checks.add("Files probed", [f.status for f in files] == ["ready", "ready"] and not sess.files_blockers(),
               [(f.file_name, f.status, f.problem) for f in files])
    plan = sess.files_next()
    if not plan.skip:
        sess.mapping_next()
    v = _job(storage, "Validate", sess.validate)
    checks.add("Read in reader workers", v.rows_to_load == sample["rows"] and v.hidden_rows == 1,
               f"rows {v.rows_to_load}, hidden {v.hidden_rows}")
    checks.add("Duplicate found", v.errors == 2 and v.left_out_on_override == 1,
               f"errors {v.errors}, left out on override {v.left_out_on_override}")
    _job(storage, "Override", lambda ctx: sess.leave_validate(ctx, OVERRIDE_REASON))
    outs = _job(storage, "Outputs", sess.run_outputs)
    checks.add("Default output", [o.status for o in outs] == [p.DONE], [(o.name, o.status) for o in outs])
    lines = _job(storage, "Totals", lambda ctx: sess.check_totals(ctx, fault={}))
    tv = next(t for t in lines if t.column_id == "c004")
    checks.add("Totals reconcile", tv.passed and tv.input == sample["input"]
               and tv.left_out == sample["left_out_value"] and HIDDEN_VALUE not in (tv.input, tv.loaded),
               f"input {tv.input}, loaded {tv.loaded}, left out {tv.left_out}")
    staging = sess.staging.path
    committed = _job(storage, "Commit", lambda ctx: sess.commit(ctx, "Self-test"), cancellable=False)
    runs = q.list_runs(con, tid)
    checks.add("Run committed", committed.label == "R-0001" and len(runs) == 1
               and runs[0].rows_loaded == sample["loaded"] and not staging.exists(),
               f"{committed.label}, rows {[r.rows_loaded for r in runs]}")

    req = ex.prefill("data", template.export, template_id=tid, client="Self-test client",
                     template=template.name, run_id=committed.run_id, run_label=committed.label)
    out.mkdir(parents=True, exist_ok=True)

    def export_work(ctx):
        (query, name), = export_items(ctx, storage.folder, req)
        return export(ctx, storage.paths.temp, query, out / name, req.options)
    res = _job(storage, "Export", export_work)
    raw = res.path.read_bytes()
    checks.add("CSV export", raw.startswith(b"\xef\xbb\xbf") and res.rows == sample["loaded"]
               and raw.count(b"\n") == sample["loaded"] + 1 and not list(out.glob("*.part")),
               f"{res.path.name}, {res.rows} rows")
    checks.add("Staging and temp emptied", _empty(storage.folder.staging_root) and _empty(storage.paths.temp))


def check_reopen(checks: Checks, paths) -> None:
    """The first start after an update: back up the catalogue, then bring it to the current schema version."""
    from sankalan.db import catalogue
    from sankalan.db.storage import Storage
    s = Storage(paths, memory_limit="1GiB", threads=2)
    s.open()
    try:
        backups = catalogue.list_backups(s.folder.backups)
        version = catalogue.current_version(s.con)
        checks.add("Catalogue backed up and upgraded at start", backups and version == catalogue.SCHEMA_VERSION,
                   f"{len(backups)} backup(s), schema {version}")
    finally:
        s.close()


def check_window(checks: Checks, storage, shot: Path | None) -> None:
    from sankalan.app import make_application
    from sankalan.ui.jobs import JobBridge
    from sankalan.ui.window import MainWindow
    app = make_application([sys.argv[0]])
    bridge = JobBridge()
    bridge.set_runner(storage.runner)
    w = MainWindow(bridge, storage)
    w.resize(1366, 768)
    w.open_area("clients")
    w.show()
    for _ in range(5):
        app.processEvents()
    pix = w.grab()
    if shot is not None:
        pix.save(str(shot))
    checks.add("Window opens", w.isVisible() and w.windowTitle() == APP_NAME and not pix.isNull(),
               w.windowTitle())
    w._may_close = True
    w.hide()
    w.storage = None                # let the connection go with the storage (no DuckDB object left for exit)
    bridge.set_runner(None)
    w.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    del w, bridge
    gc.collect()


def compiled_modules() -> set[str]:
    """Top-level names of compiled add-ons loaded from outside the Python standard library."""
    std = set(sys.stdlib_module_names)
    found = set()
    for name, mod in list(sys.modules.items()):
        f = (getattr(mod, "__file__", "") or "").lower()
        if not f.endswith((".pyd", ".so")):
            continue
        top = name.split(".")[0]
        if top in std or top.lstrip("_") in std:
            continue
        found.add(top)
    return found


def unsigned_files(folder: Path) -> list[str] | None:
    """Program files in ``folder`` whose Authenticode signature isn't Valid; None when the check can't run."""
    script = (f"Get-ChildItem -LiteralPath '{folder}' -Recurse -File -Include *.exe,*.dll,*.pyd | "
              "Where-Object { (Get-AuthenticodeSignature -LiteralPath $_.FullName).Status -ne 'Valid' } | "
              "ForEach-Object { $_.FullName }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=600, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def check_signatures(checks: Checks, expect_signed: bool) -> None:
    name = "Program files signed"
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        checks.skip(name, "running from source")
        return
    app_dir = Path(sys.executable).parent
    bad = unsigned_files(app_dir)
    if bad is None:
        checks.add(name, not expect_signed, "Get-AuthenticodeSignature could not run", skipped=not expect_signed)
        return
    detail = f"{len(bad)} unsigned" + (f", e.g. {Path(bad[0]).name}" if bad else "")
    if expect_signed:
        checks.add(name, not bad, detail)
    else:
        checks.add(name, True, detail + " (signing not expected for this build)", skipped=True)


# ---------------------------------------------------------------------------------------------- entry
def _arg(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None


def run_self_test(argv=None) -> int:
    from sankalan import log
    from sankalan.db.storage import Storage
    from sankalan.paths import AppPaths

    argv = list(sys.argv[1:] if argv is None else argv)
    report = Path(_arg(argv, "--report")) if _arg(argv, "--report") else None
    checks = Checks()
    t0 = time.monotonic()
    work = Path(tempfile.mkdtemp(prefix="sankalan-selftest-"))
    paths = AppPaths(work / APP_NAME, work / "temp")
    storage = None
    try:
        sample = write_samples(work / "sources")
        check_engines(checks, sample)
        storage = Storage(paths, memory_limit="1GiB", threads=2)
        storage.open()
        check_run(checks, storage, sample, work / "exports")
        if "--no-window" in argv:
            checks.skip("Window opens", "--no-window")
        else:
            check_window(checks, storage, report.with_suffix(".png") if report else None)
        storage.close()
        storage = None
        check_reopen(checks, paths)
        loaded = compiled_modules()
        checks.add("Only allowed compiled packages", loaded <= ALLOWED_COMPILED, sorted(loaded))
        check_signatures(checks, "--expect-signed" in argv)
    except Exception as e:      # noqa: BLE001 - every failure is a failed check
        checks.add("No unexpected error", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
    finally:
        if storage is not None:
            try:
                storage.close()
            except Exception:   # noqa: BLE001
                pass
        log.close_handlers_under(work)
        shutil.rmtree(work, ignore_errors=True)
    result = {"result": "PASS" if checks.passed else "FAIL", "passed": checks.passed, "version": __version__,
              "frozen": bool(getattr(sys, "frozen", False)), "seconds": round(time.monotonic() - t0, 1),
              "python": sys.version.split()[0], "platform": sys.platform, "checks": checks.items}
    text = json.dumps(result, indent=2)
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        print(text)
    return 0 if checks.passed else 1
