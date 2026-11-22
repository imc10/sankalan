r"""Load and Probe timings for PERF-1, PERF-2 and R14, runnable against this build or the pre-A2 build (plan A2-6
step 4, "Before and after Convert"). Development only.

It uses only what both builds have (``RunSession``, ``Storage``, ``Template``, ``Rule``), so the same script times the
code at ``--code`` (default: this repository; for the comparison, a ``git worktree`` at ``25f4d98``) on the same
data, built by ``build_a2_data.py`` under ``--root``. Each build gets its own data folder (``<root>\load_<label>``),
created fresh, because the A2 catalogue is version 2 and the pre-A2 one is version 1.

| Target | Measured (stopwatch as test cases PERF-01 / PERF-02) |
| --- | --- |
| ``perf1`` | P01 file 1 (10,000,000 rows, CSV), template TPL-P with its rules: from Next on Files to the totals check on Commit (mapping, read + convert + rules, split, totals). Probe timed apart |
| ``perf2`` | P02 (10 × 1,000,000 rows, .xlsx), the same |
| ``probe`` | Probe (adding the files) of the A2 sheet files (template sheets by name: Sales, Sales Returns) and of P02 |

DuckDB is pinned to 4 threads and 8 GB, with 3 reader workers (plan A2-O3). Each target runs ``--warmup`` times
untimed, then ``--reps`` times; the staged run is discarded each time (nothing is committed).

    python tools\perf\load_timing.py --label a2 --what perf1 perf2 probe --out tools\perf\_results\load_a2.json
    python tools\perf\load_timing.py --code <worktree> --label pre_a2 --out tools\perf\_results\load_pre_a2.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
THREADS, MEMORY, WORKERS = 4, "8GB", 3


def setup(code: Path):
    sys.path.insert(0, str(code))
    import sankalan
    assert Path(sankalan.__file__).resolve().is_relative_to(code.resolve()), sankalan.__file__


def run_job(runner, work):
    job = runner.run("perf", work)
    if job.error is not None:
        raise job.error
    return job.result


def tpl_p(client_id: str):
    """TPL-P "Perf 20 col" (test sheet, reference templates): P01's columns, TPL-P's rules, totals check on Taxable
    Value and Tax Amount, no outputs."""
    from sankalan.model.rule import (ALLOWED_VALUES, NOT_BLANK, NUMBER_RANGE, TEXT_LENGTH, UNIQUE, WARNING, Rule,
                                     with_type_rules)
    from sankalan.model.template import Column, SourceSettings, Template
    spec = [("Invoice No", "Text", None, None), ("Invoice Date", "Date", None, "DD-MM-YYYY"),
            ("Customer ID", "Text", None, None), ("Customer Name", "Text", None, None), ("GSTIN", "Text", None, None),
            ("State", "Text", None, None), ("Category", "Text", None, None), ("HSN", "Text", None, None),
            ("Branch", "Text", None, None), ("Salesperson", "Text", None, None), ("Qty", "Number", 0, None),
            ("Rate", "Number", 2, None), ("Taxable Value", "Number", 2, None), ("GST Rate", "Number", 0, None),
            ("CGST", "Number", 2, None), ("SGST", "Number", 2, None), ("IGST", "Number", 2, None),
            ("Tax Amount", "Number", 2, None), ("Place of Supply", "Text", None, None), ("Remarks", "Text", None, None)]
    cols = [Column(f"c{i:03d}", n, t, d, f, totals_check=n in ("Taxable Value", "Tax Amount"))
            for i, (n, t, d, f) in enumerate(spec, 1)]
    ids = {c.name: c.id for c in cols}
    rules = [Rule("r1", ids["Invoice No"], NOT_BLANK, {}), Rule("r2", ids["Invoice No"], UNIQUE, {}),
             Rule("r3", ids["GSTIN"], TEXT_LENGTH, {"min": 15, "max": 15}),
             Rule("r4", ids["State"], ALLOWED_VALUES, {"values": ["Maharashtra", "Gujarat", "Karnataka", "Delhi"]},
                  WARNING),
             Rule("r5", ids["Taxable Value"], NUMBER_RANGE, {"min": "0"}),
             Rule("r6", ids["GST Rate"], ALLOWED_VALUES, {"values": ["0", "5", "12", "18", "28"]})]
    return Template("", client_id, "Perf 20 col", SourceSettings(sheets="first"), cols, with_type_rules(cols, rules),
                    [], {"pattern": "{Client}_{Template}_{RunID}_{Output}", "delimiter": ",", "encoding": "utf-8-sig"})


def tpl_sheets(client_id: str):
    """TPL-A's columns reading sheets Sales and Sales Returns by name (Feature Spec A2 10.1, sheet files)."""
    from sankalan.model.rule import with_type_rules
    from sankalan.model.template import Column, SourceSettings, Template
    spec = [("Invoice No", "Text", None), ("Invoice Date", "Date", None), ("Customer", "Text", None),
            ("GSTIN", "Text", None), ("State", "Text", None), ("Taxable Value", "Number", 2),
            ("GST Rate", "Number", 0), ("Tax Amount", "Number", 2)]
    cols = [Column(f"c{i:03d}", n, t, d) for i, (n, t, d) in enumerate(spec, 1)]
    return Template("", client_id, "Sheets", SourceSettings(sheets="name", sheet_names=["Sales", "Sales Returns"]),
                    cols, with_type_rules(cols, []), [], {})


def open_storage(root: Path, label: str):
    from sankalan.db.storage import Storage
    from sankalan.paths import AppPaths
    base = root / f"load_{label}"
    shutil.rmtree(base, ignore_errors=True)
    s = Storage(AppPaths(base / "local" / "Sankalan", root / "temp" / "Sankalan"), memory_limit=MEMORY,
                threads=THREADS)
    s.open()
    return s


def load_once(s, tid: str, files: list[Path]) -> dict:
    """Probe, then Next on Files → totals check (the PERF-01 stopwatch), with stage times; then discard."""
    from sankalan.query import catalogue as q
    from sankalan.run.pipeline import RunSession
    sess = RunSession(s.folder, q.load_template(s.con, tid), workers=WORKERS)
    t = {}
    t0 = time.perf_counter()
    run_job(s.runner, lambda ctx: sess.add_files(ctx, files))
    t["probe"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    plan = sess.files_next()
    assert plan.skip or plan.complete
    sess.mapping_next()
    t1 = time.perf_counter()
    v = run_job(s.runner, sess.validate)
    t2 = time.perf_counter()
    run_job(s.runner, lambda ctx: sess.leave_validate(ctx, "perf" if v.scan.errors else None))
    t3 = time.perf_counter()
    totals = run_job(s.runner, lambda ctx: sess.check_totals(ctx, fault={}))
    t4 = time.perf_counter()
    t.update(load=t4 - t0, validate=t2 - t1, split=t3 - t2, totals=t4 - t3, rows=v.rows_to_load,
             errors=v.scan.errors, totals_ok=all(x.passed for x in totals))
    sess.discard()
    return t


def probe_once(s, tid: str, files: list[Path]) -> dict:
    from sankalan.query import catalogue as q
    from sankalan.run.pipeline import RunSession
    sess = RunSession(s.folder, q.load_template(s.con, tid), workers=WORKERS)
    t0 = time.perf_counter()
    rows = run_job(s.runner, lambda ctx: sess.add_files(ctx, files))
    return {"probe": time.perf_counter() - t0, "rows": len(rows)}


def measure(fn, warmup: int, reps: int) -> dict:
    for _ in range(warmup):
        fn()
    runs = [fn() for _ in range(reps)]
    keys = [k for k, v in runs[0].items() if isinstance(v, float)]
    out = {"runs": runs}
    for k in keys:
        xs = [r[k] for r in runs]
        out[k] = {"median": statistics.median(xs), "min": min(xs), "max": max(xs)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PERF-1 / PERF-2 / Probe timings for one build")
    ap.add_argument("--code", type=Path, default=HERE.parents[2])
    ap.add_argument("--root", type=Path, default=Path(r"C:\SankalanPerf"))
    ap.add_argument("--label", default="a2")
    ap.add_argument("--what", nargs="+", default=["probe", "perf1", "perf2"])
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    setup(a.code)
    from sankalan.query import catalogue as q
    src = a.root / "src"
    p01 = [src / "Perf_10M_01.csv"]
    p02 = sorted((src / "p02").glob("Perf_xlsx_*.xlsx"))
    sheets = [src / "sheets" / n for n in ("Sales_Nov-2026_Central.xlsx", "Sales_Nov-2026_East.xlsx",
                                           "Sales_Nov-2026_West.xlsx")]
    s = open_storage(a.root, a.label)
    result = {"label": a.label, "code": str(a.code), "threads": THREADS, "memory_limit": MEMORY, "workers": WORKERS,
              "warmup": a.warmup, "reps": a.reps}
    try:
        client = q.insert_client(s.con, "Perf Test")
        tp = q.create_template(s.con, tpl_p(client))
        ts = q.create_template(s.con, tpl_sheets(client))
        for what in a.what:
            print(f"{a.label}: {what} ...", flush=True)
            if what == "probe":
                result["probe_sheets"] = measure(lambda: probe_once(s, ts, sheets), a.warmup, a.reps)
                if p02:
                    result["probe_p02"] = measure(lambda: probe_once(s, tp, p02), a.warmup, a.reps)
            elif what == "perf1":
                result["perf1"] = measure(lambda: load_once(s, tp, p01), a.warmup, a.reps)
            elif what == "perf2" and p02:
                result["perf2"] = measure(lambda: load_once(s, tp, p02), a.warmup, a.reps)
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
            r = result.get(what if what != "probe" else "probe_sheets")
            if r:
                print({k: round(v["median"], 2) for k, v in r.items() if isinstance(v, dict)}, flush=True)
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
