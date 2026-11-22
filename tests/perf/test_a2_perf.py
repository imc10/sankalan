r"""A2 performance suite (marker ``perf``; plan A2-6 step 4; Feature Spec A2 9; Tech spec A2 13).

Runs only in A2-6 and as a release step: ``pytest -m perf tests/perf``. Needs the data from
``tools/perf/build_a2_data.py`` (default root ``C:\SankalanPerf``, or ``SANKALAN_PERF_ROOT``): 12 committed runs of
10,000,000 rows in TPL-R's shape, the TPL-R 10M CSV, P01 file 1 and P02. Without it every test skips.

Settings (plan A2-O3): DuckDB pinned to 4 threads and an 8 GB memory limit, 3 reader workers. Method: each target runs
once untimed (warm-up), then 3 times; the median, min and max go to ``tools/perf/_results/a2_perf.json``, from which
``tools/perf/RESULTS-A2.md`` is written. A miss is reported, never a test failure (T4): the tests fail only when an
operation gives a wrong result. PERF-12 (the 120M-row export) was left out on 22-11-2026 by the user's choice.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import ROOT

pytestmark = pytest.mark.perf

PERF_ROOT = Path(os.environ.get("SANKALAN_PERF_ROOT", r"C:\SankalanPerf"))
MANIFEST = PERF_ROOT / "manifest.json"
RESULTS = ROOT / "tools" / "perf" / "_results"
OUT = PERF_ROOT / "out"
PRE_A2 = PERF_ROOT / "pre_a2"            # git worktree at 25f4d98 (plan A2-O4)
WARMUP, REPS = 1, 3
THREADS, MEMORY, WORKERS = 4, "8GB", 3

TARGETS = {   # id: (target seconds, operation)
    "PERF-7": (5, "Rows view Run on 1 run (10M), 2 filters: count + first 100,000"),
    "PERF-8": (30, "The same across 12 runs"),
    "PERF-9": (0.1, "Next page of 200 rows from the Rows table"),
    "PERF-10": (0.2, "Tick, untick or reorder a column (grid redraw, offscreen)"),
    "PERF-11": (60, "Export 10M rows, 20 columns, UTF-8 with BOM, 10 parts"),
    "PERF-13": (2, "Export dialog estimate (run data; Rows view with its counts)"),
    "PERF-14": (120, "Load step without checks: 10M-row CSV including text counts"),
    "PERF-1": (120, "Load 10M rows from CSV with validation and totals"),
    "PERF-2": (300, "Load 10M rows from 10 .xlsx (test sheet target)"),
    "PERF-3": (3, "Analysis on 1 run"),
    "PERF-4": (15, "Same analysis across 12 runs"),
    "PERF-5": (60, "~1M groups across 12 runs"),
    "PERF-6": (5, "Export a ~1M-row result"),
}

_results: dict = {}


def _manifest() -> dict:
    if not MANIFEST.is_file():
        pytest.skip(f"no performance data in {PERF_ROOT} (tools/perf/build_a2_data.py)")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if len(m.get("runs", [])) < 12:
        pytest.skip("the performance data has fewer than 12 runs")
    return m


def record(key: str, samples: list[float], **extra) -> dict:
    target, what = TARGETS[key.split(" ")[0]]
    r = {"operation": what, "target_s": target, "median_s": statistics.median(samples), "min_s": min(samples),
         "max_s": max(samples), "samples_s": samples, **extra}
    r["met"] = r["median_s"] <= target
    _results[key] = r
    _write()
    print(f"\n{key}: median {r['median_s']:.3f} s (min {r['min_s']:.3f}, max {r['max_s']:.3f}); target {target} s;"
          f" {'Met' if r['met'] else 'MISSED'}")
    return r


def _write() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    meta = {"machine": machine(), "settings": {"threads": THREADS, "memory_limit": MEMORY, "workers": WORKERS,
                                               "warmup": WARMUP, "reps": REPS},
            "date": time.strftime("%d-%m-%Y %H:%M")}
    path = RESULTS / "a2_perf.json"
    old = json.loads(path.read_text(encoding="utf-8")).get("results", {}) if path.is_file() else {}
    path.write_text(json.dumps({**meta, "results": {**old, **_results}}, indent=1, default=str), encoding="utf-8")


def machine() -> dict:
    out = {"python": sys.version.split()[0], "platform": platform.platform()}
    try:
        ps = ("$c=Get-CimInstance Win32_Processor; $m=Get-CimInstance Win32_ComputerSystem; "
              "$d=Get-PhysicalDisk | Select-Object -First 1; "
              "\"$($c.Name)|$($c.NumberOfCores)|$($c.NumberOfLogicalProcessors)|$($m.TotalPhysicalMemory)|"
              "$($d.FriendlyName)|$($d.MediaType)|$($d.BusType)\"")
        cpu, cores, logical, ram, disk, media, bus = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60
        ).stdout.strip().split("|")
        out.update(cpu=cpu.strip(), cores=int(cores), logical=int(logical), ram_gb=round(int(ram) / 1024 ** 3, 1),
                   disk=f"{disk} ({media}, {bus})")
    except Exception as e:  # noqa: BLE001  (report what we can)
        out["error"] = type(e).__name__
    return out


def timed(fn, warmup: int = WARMUP, reps: int = REPS):
    """(samples, last result): ``fn`` once untimed per warm-up, then ``reps`` timed calls."""
    for _ in range(warmup):
        fn()
    samples, last = [], None
    for _ in range(reps):
        t = time.perf_counter()
        last = fn()
        samples.append(time.perf_counter() - t)
    return samples, last


def run_job(runner, work):
    job = runner.run("perf", work)
    if job.error is not None:
        raise job.error
    return job.result


# ---------------------------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def perf():
    m = _manifest()
    from sankalan.db.storage import Storage
    from sankalan.paths import AppPaths
    from sankalan.query import catalogue as q
    s = Storage(AppPaths(PERF_ROOT / "local" / "Sankalan", PERF_ROOT / "temp" / "Sankalan"), memory_limit=MEMORY,
                threads=THREADS)
    s.open()
    t = q.load_template(s.con, m["template"])
    ids = [r["id"] for r in m["runs"]]
    OUT.mkdir(parents=True, exist_ok=True)
    state = {"s": s, "m": m, "t": t, "ids": ids, "cols": [c.id for c in t.columns if not c.removed]}
    yield state
    from sankalan.query import layer
    for o in state.get("drop", []):
        run_job(s.runner, lambda ctx, o=o: layer.drop(ctx.cursor(), o))
    s.close()
    _write()


def two_filters():
    """State is one of Maharashtra AND Taxable Value between 1,000 and 1,500 (about 12% of the rows)."""
    from sankalan.model import definition as d
    return [d.Filter("c005", d.ONE_OF, ["Maharashtra"]), d.Filter("c006", d.BETWEEN, ["1000", "1500"])]


def rows_run(p, run_ids):
    from sankalan import rowsview
    from sankalan.model.rowspec import RowSpec
    spec = RowSpec(p["t"].id, two_filters(), list(p["cols"]), False)
    return run_job(p["s"].runner, lambda ctx: rowsview.run(ctx, p["s"].folder, p["t"], spec, run_ids))


def drop(p, table):
    from sankalan.query import rows as qr
    run_job(p["s"].runner, lambda ctx: qr.drop_table(ctx.cursor(), table))


def expected_matches(p, run_ids) -> int:
    files = ", ".join(f"'{(p['s'].folder.run_dir(p['t'].id, r) / 'data.parquet').as_posix()}'" for r in run_ids)
    return p["s"].con.execute(f"SELECT count(*) FROM read_parquet([{files}]) WHERE c005 = 'Maharashtra' "
                              "AND c006 BETWEEN 1000 AND 1500").fetchone()[0]


# ---------------------------------------------------------------------------------------------- Rows view
def _rows_target(p, key, run_ids):
    from sankalan.query import rows as qr
    kept = []

    def once():
        o = rows_run(p, run_ids)
        if kept:
            drop(p, kept.pop().table)
        kept.append(o)
        return o
    samples, o = timed(once)
    assert o.match == expected_matches(p, run_ids)
    assert o.held == min(o.match, qr.ROWS_CAP)
    t0 = time.perf_counter()
    run_job(p["s"].runner, lambda ctx: qr.count_rows(ctx.cursor(), o.spec, p["t"].columns, o.runs))
    count_s = time.perf_counter() - t0
    record(key, samples, matches=o.match, searched=o.searched, held=o.held, count_only_s=count_s)
    return o


def test_perf_07_rows_view_one_run(perf):
    perf["o1"] = _rows_target(perf, "PERF-7", perf["ids"][:1])


def test_perf_08_rows_view_twelve_runs(perf):
    perf["o12"] = _rows_target(perf, "PERF-8", perf["ids"])
    assert perf["o12"].searched == sum(r["rows"] for r in perf["m"]["runs"])


def test_perf_09_next_page(perf):
    from sankalan import rowsview
    o = perf.get("o1") or rows_run(perf, perf["ids"][:1])
    src = rowsview.RowsSource(o)
    at = [min(50_000, o.held // 2)]

    def page():
        rows = run_job(perf["s"].runner, lambda ctx: src.page(ctx, at[0], 200, []))
        at[0] += 200
        return rows
    samples, rows = timed(page)
    assert len(rows) == 200
    record("PERF-9", samples)


def test_perf_10_column_redraw(perf, qtbot):
    from PySide6.QtWidgets import QApplication

    from sankalan.ui import theme
    from sankalan.ui.jobs import JobBridge
    from sankalan.ui.screens.rows_view import RowsResult
    theme.apply(QApplication.instance())
    o = perf.get("o1") or rows_run(perf, perf["ids"][:1])
    bridge = JobBridge(perf["s"].runner)
    w = RowsResult(bridge)
    qtbot.addWidget(w)
    w.resize(1366 - 380, 640)
    w.show()
    ticked = list(perf["cols"])
    w.show_outcome(o, ticked, False)
    w.stack.setCurrentWidget(w.page)
    qtbot.waitUntil(lambda: not w.model.loading and w.model.rowCount() == o.held
                    and w.model.row_values(0) is not None, timeout=30_000)

    def redraw(cols):
        def go():
            w.set_columns(o, cols, False)
            QApplication.processEvents()
            w.grid.viewport().repaint()
            w.grid.horizontalHeader().viewport().repaint()
        return go
    without = [c for c in ticked if c != "c005"]
    moved = list(ticked)
    moved.insert(3, moved.pop(5))
    out = {}
    for name, cols in (("untick", without), ("tick", ticked), ("reorder", moved)):
        samples = []
        for k in range(WARMUP + REPS):
            redraw(ticked if name != "tick" else without)()     # from the other state each time
            t = time.perf_counter()
            redraw(cols)()
            if k >= WARMUP:
                samples.append(time.perf_counter() - t)
        assert w.headers()[:3] == [next(c.name for c in perf["t"].columns if c.id == x) for x in cols[:3]]
        out[name] = samples
        record(f"PERF-10 {name}", samples)
    assert not bridge.busy          # no Job: the redraw reads only the loaded pages (ROW-9)


# ---------------------------------------------------------------------------------------------- exports
def _run_data_source(p, run_id, ctx):
    from sankalan import runs
    from sankalan.query import convert
    from sankalan.query import export as qx
    view = runs.run_view(ctx, p["s"].folder, run_id)
    return qx.run_data(ctx.cursor(), view.run_dir / convert.DATA, view.template.columns, view.file_names, view.label)


def test_perf_13_estimate(perf):
    from sankalan import exporting
    from sankalan.model.export import ExportOptions
    from sankalan.query import rows as qr
    s = perf["s"]

    def run_data():
        return run_job(s.runner, lambda ctx: exporting.estimate(ctx, s.paths.temp,
                                                                [_run_data_source(perf, perf["ids"][0], ctx)],
                                                                ExportOptions()))
    samples, est = timed(run_data)
    assert est.total_rows == perf["m"]["runs"][0]["rows"]
    assert est.files == exporting.part_count(est.total_rows)
    record("PERF-13 run data", samples, bytes=est.bytes)
    o = perf.get("o12") or rows_run(perf, perf["ids"])

    def rows_view():          # the Rows view reuses its counts (Tech spec A2 13): no scan before the sample
        return run_job(s.runner, lambda ctx: exporting.estimate(
            ctx, s.paths.temp, [qr.export_source(ctx.cursor(), o.spec, o.columns, o.runs, o.counts)],
            ExportOptions()))
    samples, est = timed(rows_view)
    assert est.total_rows == o.match
    record("PERF-13 rows view", samples, rows=o.match)


def _clear(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)


def test_perf_11_export_run_data(perf):
    from sankalan import exporting
    from sankalan.model.export import ExportOptions
    s = perf["s"]
    dest = OUT / "perf11"

    def export():
        _clear(dest)
        return run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp,
                                                              [_run_data_source(perf, perf["ids"][0], ctx)], dest,
                                                              ["Perf_R-0001_Data.csv"], ExportOptions()))
    samples, (res,) = timed(export)
    assert len(res.paths) == exporting.part_count(perf["m"]["runs"][0]["rows"])
    total = sum(p.stat().st_size for p in res.paths)
    with open(res.paths[-1], "rb") as f:
        assert f.read(3) == b"\xef\xbb\xbf"
    record("PERF-11", samples, parts=len(res.paths), bytes=total)
    _clear(dest)


def test_exp_9a_parts_open_in_excel(perf):
    """AC-EXP-9a: every part of a Rows export of about 2,100,000 rows (run 1, State is one of Maharashtra AND
    Taxable Value between 1,000 and 1,835) opens in Excel with all its records: 1,000,001 with the header for a full
    part. Narration values hold commas, quotes and line breaks. Not verified when Excel isn't installed."""
    import csv

    from sankalan import exporting, rowsview
    from sankalan.model import definition as d
    from sankalan.model.export import ExportOptions
    from sankalan.model.rowspec import RowSpec
    from sankalan.query import rows as qr
    s = perf["s"]
    spec = RowSpec(perf["t"].id, [d.Filter("c005", d.ONE_OF, ["Maharashtra"]),
                                  d.Filter("c006", d.BETWEEN, ["1000", "1835"])], list(perf["cols"]), False)
    o = run_job(s.runner, lambda ctx: rowsview.run(ctx, s.folder, perf["t"], spec, perf["ids"][:1]))
    dest = OUT / "exp9a"
    _clear(dest)
    res, = run_job(s.runner, lambda ctx: exporting.export(
        ctx, s.paths.temp, [qr.export_source(ctx.cursor(), o.spec, o.columns, o.runs, o.counts)], dest,
        ["Perf_Rows.csv"], ExportOptions()))
    drop(perf, o.table)
    expected = {}
    for p in res.paths:
        with open(p, encoding="utf-8-sig", newline="") as f:
            expected[str(p)] = sum(1 for _ in csv.reader(f))
    full = exporting.PART_ROWS + 1
    assert all(n == full for n in list(expected.values())[:-1])
    assert sum(expected.values()) - len(expected) == o.match
    exp_file, out_file = RESULTS / "exp9a_expected.json", RESULTS / "exp9a_excel.json"
    exp_file.write_text(json.dumps(expected, indent=1), encoding="utf-8")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "tools" / "perf" / "excel_open_check.ps1"), "-Expected", str(exp_file), "-Out",
                        str(out_file)], capture_output=True, text=True, timeout=3600)
    if r.returncode == 3:
        _results["AC-EXP-9a"] = {"verified": False, "reason": "Excel not installed"}
        _write()
        pytest.skip("Excel isn't installed: AC-EXP-9a not verified")
    got = json.loads(out_file.read_text(encoding="utf-8-sig"))
    _results["AC-EXP-9a"] = {"verified": True, "rows": o.match, "parts": len(res.paths), **got}
    _write()
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    _clear(dest)


# ---------------------------------------------------------------------------------------------- analysis (regression)
def _definition(tid, groups, cards, subtotals=True):
    from sankalan.model.definition import Definition
    return Definition(tid, [], groups, cards, subtotals)


def _analysis(p, key, definition, run_ids, keep=False):
    from sankalan import analyses
    from sankalan.query import layer
    s = p["s"]
    kept = []

    def once():
        o = run_job(s.runner, lambda ctx: analyses.run(ctx, s.folder, definition, p["t"], run_ids))
        if kept:
            old = kept.pop().result
            run_job(s.runner, lambda ctx: layer.drop(ctx.cursor(), old))
        kept.append(o)
        return o
    samples, o = timed(once)
    record(key, samples, rows=o.count, input_rows=o.input_rows)
    if keep:
        return o
    run_job(s.runner, lambda ctx: layer.drop(ctx.cursor(), o.result))
    return o


def perf3_definition(tid):
    from sankalan.model import definition as d
    return _definition(tid, [d.Group("c005"), d.Group("c017"), d.Group("c002", d.MONTH)],
                       d.cards(d.FlatMeasure("c006", d.SUM), d.FlatMeasure("c001", d.COUNT),
                               d.FlatMeasure("c007", d.AVG)))


def test_perf_03_analysis_one_run(perf):
    o = _analysis(perf, "PERF-3", perf3_definition(perf["t"].id), perf["ids"][:1])
    assert o.input_rows == perf["m"]["runs"][0]["rows"]


def test_perf_04_analysis_twelve_runs(perf):
    _analysis(perf, "PERF-4", perf3_definition(perf["t"].id), perf["ids"])


def test_perf_05_06_million_groups_and_export(perf):
    from sankalan import exporting
    from sankalan.model import definition as d
    from sankalan.model.export import ExportOptions
    from sankalan.query import export as qx
    from sankalan.query import layer
    s = perf["s"]
    de = _definition(perf["t"].id, [d.Group("c005"), d.Group("c004")], d.cards(d.FlatMeasure("c001",
                                                                                             d.COUNT_DISTINCT)))
    o = _analysis(perf, "PERF-5", de, perf["ids"], keep=True)
    assert o.count >= 0.98 * min(perf["m"]["rows"], 1_000_000)
    dest = OUT / "perf6"

    def export():
        _clear(dest)
        return run_job(s.runner, lambda ctx: exporting.export(
            ctx, s.paths.temp, [qx.result(ctx.cursor(), o.result, subtotals=True)], dest, ["Result.csv"],
            ExportOptions()))
    samples, (res,) = timed(export)
    record("PERF-6", samples, rows=o.count, parts=len(res.paths))
    run_job(s.runner, lambda ctx: layer.drop(ctx.cursor(), o.result))
    _clear(dest)


# ---------------------------------------------------------------------------------------------- loads
def test_perf_14_load_without_checks(perf):
    from sankalan.query import catalogue as q
    from sankalan.run.pipeline import RunSession
    s = perf["s"]
    csv_path = PERF_ROOT / "src" / "TPLR_10M.csv"
    probes, loads = [], []
    last = None
    for k in range(WARMUP + REPS):
        sess = RunSession(s.folder, q.load_template(s.con, perf["m"]["template_nck"]), workers=WORKERS)
        t = time.perf_counter()
        run_job(s.runner, lambda ctx: sess.add_files(ctx, [csv_path]))
        probe = time.perf_counter() - t
        plan = sess.files_next()
        assert plan.skip or plan.complete
        sess.mapping_next()
        t = time.perf_counter()
        last = run_job(s.runner, sess.load_unchecked)
        load = time.perf_counter() - t
        sess.discard()
        if k >= WARMUP:
            probes.append(probe)
            loads.append(load)
    rows = perf["m"]["rows"]
    assert last.rows_to_load == rows
    assert last.text_counts.get("c006", 0) >= rows // 6_623 and last.text_counts.get("c002", 0) >= rows // 32_768 - 30
    record("PERF-14", loads, probe_s=statistics.median(probes), text_counts=last.text_counts)


def _load_timing(label: str, code: Path, what: list[str]) -> dict:
    out = RESULTS / f"load_{label}.json"
    cmd = [sys.executable, str(ROOT / "tools" / "perf" / "load_timing.py"), "--code", str(code), "--root",
           str(PERF_ROOT), "--label", label, "--what", *what, "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3 * 3600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(out.read_text(encoding="utf-8"))


def test_perf_01_02_loads_and_probe_before_and_after(perf):
    """PERF-1, PERF-2 re-measured, and the same loads and Probe on the pre-A2 build (R13, R14) when its worktree is
    there (``git worktree add --detach C:\\SankalanPerf\\pre_a2 25f4d98``)."""
    has_p02 = any((PERF_ROOT / "src" / "p02").glob("*.xlsx"))
    what = ["probe", "perf1"] + (["perf2"] if has_p02 else [])
    a2 = _load_timing("a2", ROOT, what)
    for key, name in (("PERF-1", "perf1"), ("PERF-2", "perf2")):
        if name in a2:
            runs = a2[name]["runs"]
            assert all(r["totals_ok"] and r["errors"] == 0 for r in runs)
            stages = {k: a2[name][k]["median"] for k in ("probe", "validate", "split", "totals")}
            record(key, [r["load"] for r in runs], stages=stages, rows=runs[0]["rows"])
    if (PRE_A2 / "sankalan").is_dir():
        pre = _load_timing("pre_a2", PRE_A2, what)
        _results["compare"] = {"a2": {k: a2[k] for k in a2 if k.startswith(("perf", "probe"))},
                               "pre_a2": {k: pre[k] for k in pre if k.startswith(("perf", "probe"))}}
        _write()
