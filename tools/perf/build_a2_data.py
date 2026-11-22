r"""Build the A2 performance data (plan A2-6 step 4; Tech spec A2 13). Development only.

Everything goes under one root (default ``C:\SankalanPerf``, outside OneDrive), never into the repository:

| Path | Contents |
| --- | --- |
| ``local\Sankalan``, ``temp\Sankalan`` | The app paths: data folder ``local\Sankalan\Data`` and the Job temp folder |
| ``src\seed`` | The small seed files each committed run starts from (one .xlsx with sheets Sales A and Sales B, one CSV) |
| ``src\TPLR_10M.csv`` | 10,000,000 rows in TPL-R's shape with planted text values (PERF-14) |
| ``src\Perf_10M_01.csv`` | P01 file 1, 10,000,000 rows (PERF-1, as test case PERF-01) |
| ``src\p02\Perf_xlsx_01…10.xlsx`` | P02, 10 × 1,000,000 rows (PERF-2) |
| ``src\sheets`` | The A2 sheet files (Probe timing, R14) |
| ``manifest.json`` | Template and run IDs, row counts, build times |

**Runs.** Template "Perf R" has TPL-R's 20 columns and rules. Each of the 12 runs is a real ``RunSession`` on the seed
files (probe, mapping, validate, split, totals check), whose staged ``data.parquet`` is then replaced by 10,000,000
rows written straight by DuckDB in the same schema and stored order, and committed by the real commit (folder rename
and one catalogue transaction). Rows loaded and text counts are read from the new file at commit, as for any run.

Row n (1-based) of run k: TPL-R's ``row_values`` formulas, month k of 2026, about 1% blank cells, Taxable Value text on
about 1,510 rows ("NA", "Nil", "12,000/-") and Invoice Date text on about 305 rows ("NA", "31-02-2026"), as TPL-R's
R-0001 / R-0002. GSTIN has 1,000,000 distinct values (the same in every run), so PERF-5 has about 1,000,000 groups.

    python tools\perf\build_a2_data.py [--root C:\SankalanPerf] [--runs 12] [--rows 10000000] [--skip-p02]
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

DEFAULT_ROOT = Path(r"C:\SankalanPerf")
ROWS = 10_000_000
RUNS = 12
PARTS = [(0, "Sales A", 600_000), (1, "Sales B", 400_000), (2, None, 9_000_000)]     # per 10M rows
SEED_ROWS = [30, 20, 50]                     # Sales A, Sales B, CSV
TAXABLE_EVERY, DATE_EVERY = 6_623, 32_768    # ~1,510 and ~305 text cells per 10M rows
THREADS, MEMORY = 4, "8GB"                   # plan A2-O3


def app_paths(root: Path):
    from sankalan.paths import AppPaths
    return AppPaths(root / "local" / "Sankalan", root / "temp" / "Sankalan")


def open_storage(root: Path):
    from sankalan.db.storage import Storage
    s = Storage(app_paths(root), memory_limit=MEMORY, threads=THREADS)
    s.open()
    return s


def run_job(runner, work):
    job = runner.run("perf", work)
    if job.error is not None:
        raise job.error
    return job.result


def sql_list(values) -> str:
    return "[" + ", ".join("'" + str(v).replace("'", "''") + "'" for v in values) + "]"


# ---------------------------------------------------------------------------------------------- row formulas (SQL)
def value_exprs(k: int) -> dict[str, str]:
    """Column ID → SQL over ``n`` (1-based row in the run) for TPL-R's 20 columns in run k (month k of 2026);
    companions ``cNNN_t`` for the planted text. Blank cells (about 1%) are applied by the caller."""
    import tpl_r
    start = f"DATE '2026-{k:02d}-01'"
    days = f"(date_diff('day', {start}, {start} + INTERVAL 1 MONTH))"
    tv = "(1000 + ((n - 1) % 100) * 10.25)::DECIMAL(38,2)"
    rate = f"({tpl_r.RATES}[((n - 1) % 5) + 1])"
    intra = f"({sql_list(tpl_r.STATES)}[((n - 1) % 4) + 1] = 'Maharashtra')"
    cgst = f"(CASE WHEN {intra} THEN round({tv} * {rate} / 200, 2) ELSE 0 END)::DECIMAL(38,2)"
    igst = f"(CASE WHEN {intra} THEN 0 ELSE round({tv} * {rate} / 100, 2) END)::DECIMAL(38,2)"
    cess = f"(CASE WHEN n % 3 = 0 THEN round({tv} / 100, 2) ELSE 0 END)::DECIMAL(38,2)"
    disc = "((n % 7) * 5.5)::DECIMAL(38,2)"
    freight = "((n % 11) * 12.75)::DECIMAL(38,2)"
    inv_date = f"({start} + ((n - 1) % {days})::INTEGER)"
    t_text = f"(n % {TAXABLE_EVERY} = 7)"
    d_text = f"(n % {DATE_EVERY} = 11)"
    return {
        "c001": f"'INV-' || lpad('{k}', 2, '0') || lpad(n::VARCHAR, 8, '0')",
        "c002": f"CASE WHEN {d_text} THEN NULL ELSE {inv_date} END",
        "c002_t": f"CASE WHEN {d_text} THEN (CASE WHEN n % 61 = 0 THEN '31-02-2026' ELSE 'NA' END) END",
        "c003": f"{sql_list(tpl_r.CUSTOMERS)}[((n - 1) % 10) + 1]",
        "c004": "'27' || lpad(((n - 1) % 1000000)::VARCHAR, 7, '0') || 'ABCDE1Z5'",
        "c005": f"{sql_list(tpl_r.STATES)}[((n - 1) % 4) + 1]",
        "c006": f"CASE WHEN {t_text} THEN NULL ELSE {tv} END",
        "c006_t": f"CASE WHEN {t_text} THEN (CASE n % 151 WHEN 0 THEN '12,000/-' ELSE "
                  f"(CASE WHEN n % 3 = 0 THEN 'Nil' ELSE 'NA' END) END) END",
        "c007": cgst, "c008": cgst, "c009": igst, "c010": cess, "c011": disc, "c012": freight,
        "c013": f"({tv} + {cgst} * 2 + {igst} + {cess} - {disc} + {freight})::DECIMAL(38,2)",
        "c014": f"{inv_date} + 30", "c015": f"{inv_date} + 2", "c016": f"{inv_date} + 45",
        "c017": f"{sql_list(tpl_r.BRANCHES)}[((n - 1) % 3) + 1]",
        "c018": "lpad((8471 + n % 9)::VARCHAR, 4, '0')",
        "c019": f"{sql_list(tpl_r.PEOPLE)}[((n - 1) % 6) + 1]",
        "c020": "CASE WHEN n % 50 = 0 THEN 'Goods, \"urgent\" ' || n WHEN n % 50 = 25 THEN 'Line one ' || n || "
                "chr(10) || 'line two' WHEN n % 50 = 13 THEN 'Part A, part B ' || n ELSE 'Order ' || n END",
    }


def blanked(cid: str, expr: str) -> str:
    """About 1% of a column's cells blank (TPL-R's ``blank_cell``; Invoice No never)."""
    import tpl_r
    j = int(cid[1:4])
    if j == 1:
        return expr
    return f"CASE WHEN (n * 31 + {j} * 17) % 100 = 0 THEN NULL ELSE {expr} END"


def data_sql(k: int, rows: int, schema: list[tuple[str, str]], parts: list[tuple[int, str, int, int]],
             run_id: str) -> str:
    """Run k's rows in ``data.parquet``'s exact schema and stored order. ``parts``: (file index, sheet, rows,
    first source row) in load order."""
    exprs = value_exprs(k)
    bounds, at = [], 0
    for idx, sheet, count, first in parts:
        bounds.append((at, at + count, idx, sheet, first))
        at += count
    assert at == rows, (at, rows)
    f_case = " ".join(f"WHEN n <= {hi} THEN {idx}" for lo, hi, idx, _s, _f in bounds)
    s_case = " ".join(f"WHEN n <= {hi} THEN '{sheet}'" for lo, hi, _i, sheet, _f in bounds)
    r_case = " ".join(f"WHEN n <= {hi} THEN n - {lo} + {first} - 1" for lo, hi, _i, _s, first in bounds)
    out = []
    for name, typ in schema:
        if name == "run_id":
            e = f"'{run_id}'"
        elif name == "_src_file":
            e = f"CASE {f_case} END"
        elif name == "_src_sheet":
            e = f"CASE {s_case} END"
        elif name == "_src_row":
            e = f"CASE {r_case} END"
        else:
            base = name[:4]
            e = blanked(base, exprs[name]) if name in exprs else "NULL"
        out.append(f"CAST({e} AS {typ}) AS \"{name}\"")
    return f"SELECT {', '.join(out)} FROM range(1, {rows} + 1) r(n) ORDER BY n"


def csv_sql(rows: int, k: int = 1) -> str:
    """The same rows as text in a TPL-R CSV (headers as the template; dates DD-MM-YYYY; planted text as typed)."""
    import tpl_r
    exprs = value_exprs(k)
    cols = []
    for cid, name, typ, *_ in tpl_r.COLUMNS:
        e = blanked(cid, exprs[cid])
        if typ == "Date":
            e = f"strftime({e}, '%d-%m-%Y')"
        elif typ == "Number":
            e = f"CAST({e} AS VARCHAR)"
        if cid + "_t" in exprs:
            e = f"coalesce({e}, {exprs[cid + '_t']})"
        cols.append(f"{e} AS \"{name}\"")
    return f"SELECT {', '.join(cols)} FROM range(1, {rows} + 1) r(n) ORDER BY n"


# ---------------------------------------------------------------------------------------------- templates
def perf_template(client_id: str, name: str, checks: bool = True):
    """TPL-R's columns and rules, no default outputs."""
    import tpl_r
    t = tpl_r.template(client_id)
    t.name, t.outputs, t.checks = name, [], checks
    return t


def write_seed(out: Path) -> list[Path]:
    """One .xlsx (Sales A, Sales B) and one CSV in TPL-R's run-1 layout, a few rows each."""
    import datetime as dt

    import xlsxwriter

    import tpl_r
    out.mkdir(parents=True, exist_ok=True)
    planted = {"text": {1: {}, 2: {}, 3: {}}, "bad_invoice": set()}
    xlsx, csvp = out / "Perf_Seed.xlsx", out / "Perf_Seed.csv"
    wb = xlsxwriter.Workbook(str(xlsx), {"strings_to_numbers": False})
    dfmt = wb.add_format({"num_format": "dd-mm-yyyy"})
    ids = [c[0] for c in tpl_r.COLUMNS]
    n = 0
    for sheet, count in (("Sales A", SEED_ROWS[0]), ("Sales B", SEED_ROWS[1])):
        ws = wb.add_worksheet(sheet)
        ws.write_row(0, 0, tpl_r.NAMES)
        for r in range(1, count + 1):
            n += 1
            v = tpl_r.row_values(1, n, planted)
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
    wb.close()
    with open(csvp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(tpl_r.NAMES)
        for _ in range(SEED_ROWS[2]):
            n += 1
            v = tpl_r.row_values(1, n, planted)
            w.writerow(["" if v[c] is None else (v[c].strftime("%d-%m-%Y") if isinstance(v[c], dt.date) else v[c])
                        for c in ids])
    return [xlsx, csvp]


# ---------------------------------------------------------------------------------------------- one committed run
def commit_run(s, tid: str, seed: list[Path], k: int, rows: int) -> tuple[str, float]:
    """A real RunSession on the seed files whose staged data.parquet is replaced by ``rows`` generated rows before
    the real commit. Returns (run id, seconds)."""
    from sankalan.query import catalogue as q
    from sankalan.query.convert import DATA
    from sankalan.run.pipeline import RunSession
    t0 = time.monotonic()
    sess = RunSession(s.folder, q.load_template(s.con, tid), workers=0)
    run_job(s.runner, lambda ctx: sess.add_files(ctx, seed))
    if k > 1:                                   # the same seed files as earlier runs: Load anyway (RUN-7)
        for p in seed:
            sess.load_anyway(str(p))
    plan = sess.files_next()
    assert plan.skip or plan.complete, "seed headers must match the template"
    sess.mapping_next()
    run_job(s.runner, sess.validate)
    run_job(s.runner, lambda ctx: sess.leave_validate(ctx, "Perf data" if sess.validation.scan.errors else None))
    run_job(s.runner, lambda ctx: sess.check_totals(ctx, fault={}))
    data = sess.staging.path / DATA
    schema = [(r[0], r[1]) for r in s.con.execute(f"DESCRIBE SELECT * FROM read_parquet('{data.as_posix()}')")
              .fetchall()]
    firsts = dict(s.con.execute(f"SELECT _src_file, min(_src_row) FROM read_parquet('{data.as_posix()}') "
                                "GROUP BY ALL").fetchall())
    sheets = dict(s.con.execute(f"SELECT DISTINCT _src_file, _src_sheet FROM read_parquet('{data.as_posix()}')")
                  .fetchall())
    run_id = s.con.execute(f"SELECT any_value(run_id) FROM read_parquet('{data.as_posix()}')").fetchone()[0]
    scale = rows / ROWS
    sizes = [round(c * scale) for _i, _s, c in PARTS]
    sizes[-1] = rows - sum(sizes[:-1])
    parts = [(idx, sheets[idx], size, firsts[idx]) for (idx, _s, _c), size in zip(PARTS, sizes)]
    tmp = data.with_name("data.parquet.gen")
    s.con.execute(f"COPY ({data_sql(k, rows, schema, parts, run_id)}) TO '{tmp.as_posix()}' (FORMAT parquet)")
    data.unlink()
    tmp.rename(data)
    # the figures the commit records from the session: rows read per file-sheet
    sess.validation = dataclasses.replace(sess.validation, rows_read=rows, rows_to_load=rows, blank_rows=0)
    by_idx = dict(zip([p[0] for p in parts], sizes))
    sess._load.parts = [dataclasses.replace(p, rows=by_idx[p.file_index], blank_rows=0)
                        for p in sess._load.parts]
    job = s.runner.run("commit", lambda ctx: sess.commit(ctx, "Perf data", free_bytes=100 * 1024 ** 3),
                       cancellable=False)
    if job.error is not None:
        raise job.error
    return job.result.run_id, time.monotonic() - t0


def check_order(s, path: Path) -> None:
    """Rows in the file's own order ascend in (_src_file, _src_row) (T32)."""
    bad = s.con.execute(
        "SELECT count(*) FROM (SELECT _src_file AS f, _src_row AS r, lag(_src_file) OVER w AS pf, "
        f"lag(_src_row) OVER w AS pr FROM read_parquet('{path.as_posix()}', file_row_number = true) "
        "WINDOW w AS (ORDER BY file_row_number)) WHERE f < pf OR (f = pf AND r <= pr)").fetchone()[0]
    assert bad == 0, f"{path}: {bad} rows out of stored order"


# ---------------------------------------------------------------------------------------------- build
def build(root: Path, runs: int, rows: int, skip_p02: bool, force: bool) -> dict:
    import duckdb

    import generate
    from sankalan.db import catalogue as _c  # noqa: F401  (import check)
    from sankalan.query import catalogue as q
    root.mkdir(parents=True, exist_ok=True)
    mpath = root / "manifest.json"
    man = json.loads(mpath.read_text(encoding="utf-8")) if mpath.is_file() and not force else {}
    src = root / "src"
    src.mkdir(exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET threads = {THREADS}")
    con.execute(f"SET memory_limit = '{MEMORY}'")

    def timed(key, fn):
        if key in man.get("built", {}):
            print(f"  {key}: kept")
            return
        t = time.monotonic()
        fn()
        man.setdefault("built", {})[key] = round(time.monotonic() - t, 1)
        mpath.write_text(json.dumps(man, indent=1), encoding="utf-8")
        print(f"  {key}: {man['built'][key]} s", flush=True)

    timed("tplr_csv", lambda: con.execute(f"COPY ({csv_sql(rows)}) TO '{(src / 'TPLR_10M.csv').as_posix()}' "
                                          "(HEADER, DELIMITER ',')"))
    timed("p01_01", lambda: con.execute(f"COPY ({generate.p01_sql(1, rows)}) TO "
                                        f"'{(src / 'Perf_10M_01.csv').as_posix()}' (HEADER, DELIMITER ',')"))
    if not skip_p02:
        timed("p02", lambda: generate.generate_perf(src / "p02", rows_csv=1, rows_xlsx=1_000_000, csv_files=0,
                                                    xlsx_files=10))

    def sheets():
        (src / "sheets").mkdir(exist_ok=True)
        generate.write_sheet_files(src / "sheets")
    timed("sheet_files", sheets)
    con.close()

    if "template" not in man:
        shutil.rmtree(root / "local", ignore_errors=True)
        shutil.rmtree(root / "temp", ignore_errors=True)
    s = open_storage(root)
    try:
        if "template" not in man:
            client = q.insert_client(s.con, "Perf Test")
            man["client"] = client
            man["template"] = q.create_template(s.con, perf_template(client, "Perf R"))
            man["template_nck"] = q.create_template(s.con, perf_template(client, "Perf N", checks=False))
            man["runs"] = []
            mpath.write_text(json.dumps(man, indent=1), encoding="utf-8")
        seed = write_seed(src / "seed")
        while len(man["runs"]) < runs:
            k = len(man["runs"]) + 1
            run_id, sec = commit_run(s, man["template"], seed, k, rows)
            data = s.folder.run_dir(man["template"], run_id) / "data.parquet"
            check_order(s, data)
            n = s.con.execute(f"SELECT count(*) FROM read_parquet('{data.as_posix()}')").fetchone()[0]
            assert n == rows, n
            man["runs"].append({"id": run_id, "k": k, "rows": rows, "seconds": round(sec, 1),
                                "bytes": data.stat().st_size})
            mpath.write_text(json.dumps(man, indent=1), encoding="utf-8")
            print(f"  run {k}: {run_id} {rows:,} rows, {data.stat().st_size / 1e9:.2f} GB, {sec:.0f} s", flush=True)
    finally:
        s.close()
    man["rows"] = rows
    mpath.write_text(json.dumps(man, indent=1), encoding="utf-8")
    return man


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the A2 performance data")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--rows", type=int, default=ROWS)
    ap.add_argument("--skip-p02", action="store_true")
    ap.add_argument("--force", action="store_true", help="start again (deletes the perf data folder)")
    a = ap.parse_args(argv)
    free = shutil.disk_usage(a.root.anchor).free
    print(f"Free on {a.root.anchor}: {free / 1e9:.0f} GB")
    if free < 40e9:
        print("Less than 40 GB free: stopping (ask before scaling anything down).")
        return 2
    man = build(a.root, a.runs, a.rows, a.skip_p02, a.force)
    print(f"Done: {len(man['runs'])} runs in {a.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
