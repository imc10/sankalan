"""Phase 0 spike: DuckDB 2.0 behaviour the design relies on. Results go in tools/spikes/RESULTS.md.

Run: .venv\\Scripts\\python tools\\spikes\\spike_duckdb.py [--rows 10000000]
"""
import argparse
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

import duckdb


def section(title):
    print(f"\n== {title}")


def rounding(con):
    section("T13 rounding: CAST(text AS DECIMAL(38,d))")
    cases = ["2.345", "-2.345", "2.5", "-2.5", "0.005", "-0.005", "123456.789", "1234567.5", "0.5", "1.5",
             "2.675", "1.0000005", "99999999999999999999999999999999.995"]
    ok = True
    for d in (0, 2, 6):
        for v in cases:
            try:
                got = con.execute(f"SELECT CAST(? AS DECIMAL(38,{d}))::VARCHAR", [v]).fetchone()[0]
            except duckdb.Error as e:
                got = f"error {type(e).__name__}"
            from decimal import Decimal, ROUND_HALF_UP
            q = Decimal(1).scaleb(-d)
            try:
                want = str(Decimal(v).quantize(q, rounding=ROUND_HALF_UP))
            except Exception:
                want = "overflow"
            want = want.replace("-0", "0") if want.lstrip("-0.") == "" else want   # Decimal keeps -0
            flag = "" if got == want or want == "overflow" else "   <-- differs"
            ok &= got == want or want == "overflow"
            print(f"  d={d} {v:>40} -> {got:>40}  (half away from zero: {want}){flag}")
    # DECIMAL(38,6) -> DECIMAL(38,2), the path if text is first cast at full precision
    got = con.execute("SELECT CAST(CAST('2.345' AS DECIMAL(38,6)) AS DECIMAL(38,2))::VARCHAR").fetchone()[0]
    print(f"  DECIMAL(38,6) 2.345 -> DECIMAL(38,2): {got}")
    got = con.execute("SELECT CAST(2.345::DOUBLE AS DECIMAL(38,2))::VARCHAR").fetchone()[0]
    print(f"  DOUBLE 2.345 -> DECIMAL(38,2): {got}  (binary float; staged text avoids this path)")
    got = con.execute("SELECT TRY_CAST('12abc' AS DECIMAL(38,2)), TRY_CAST('' AS DECIMAL(38,2)), "
                      "TRY_CAST('1e3' AS DECIMAL(38,2))::VARCHAR").fetchone()
    print(f"  TRY_CAST '12abc', '', '1e3': {got}")
    print(f"  RESULT: text->DECIMAL rounds half away from zero: {ok}")
    return ok


def interrupt_latency(con, rows):
    section("interrupt() latency on a long query")
    res = {}

    def run():
        t0 = time.perf_counter()
        try:
            con.execute(f"SELECT sum(hash(i) % 1000) FROM range({rows * 50}) t(i)").fetchone()
            res["outcome"] = "finished"
        except duckdb.InterruptException:
            res["outcome"] = "interrupted"
        except duckdb.Error as e:
            res["outcome"] = type(e).__name__
        res["end"] = time.perf_counter()
        res["start"] = t0

    th = threading.Thread(target=run)
    th.start()
    time.sleep(1.0)
    t_int = time.perf_counter()
    con.interrupt()
    th.join()
    lat = (res["end"] - t_int) * 1000
    print(f"  outcome={res['outcome']}  latency after interrupt(): {lat:.0f} ms")
    # connection still usable afterwards?
    print(f"  connection usable afterwards: {con.execute('SELECT 42').fetchone()[0] == 42}")
    return res["outcome"], lat


def copy_speed(con, work, rows):
    section(f"COPY ... TO CSV, {rows:,} rows x 8 columns")
    con.execute(f"""CREATE OR REPLACE TABLE t AS
        SELECT 'INV-' || lpad((i % 100000000)::VARCHAR, 9, '0') AS inv,
               DATE '2026-01-01' + (i % 365)::INTEGER AS d,
               'CUST-' || lpad((i % 1000000)::VARCHAR, 7, '0') AS cust,
               ['Maharashtra','Gujarat','Karnataka','Delhi'][(i % 4) + 1] AS state,
               CAST(1000 + (i % 100) * 10.25 AS DECIMAL(38,2)) AS taxable,
               [0,5,12,18,28][(i % 5) + 1]::DECIMAL(38,0) AS rate,
               CAST((1000 + (i % 100) * 10.25) * [0,5,12,18,28][(i % 5) + 1] / 100 AS DECIMAL(38,2)) AS tax,
               CASE WHEN i % 10 = 0 THEN 'note' END AS remarks
        FROM range({rows}) r(i)""")
    out = work / "copy.csv"
    t0 = time.perf_counter()
    con.execute(f"COPY t TO '{out.as_posix()}' (HEADER, DELIMITER ',', DATEFORMAT '%d-%m-%Y')")
    secs = time.perf_counter() - t0
    size = out.stat().st_size
    print(f"  {secs:.1f} s, {size / 1e6:.0f} MB, {rows / secs / 1e6:.2f} M rows/s")
    head = out.read_bytes()[:160].decode()
    print("  first bytes:", head.replace("\n", " | "))
    pq = work / "t.parquet"
    t0 = time.perf_counter()
    con.execute(f"COPY t TO '{pq.as_posix()}' (FORMAT parquet)")
    psecs = time.perf_counter() - t0
    print(f"  Parquet write {psecs:.1f} s, {pq.stat().st_size / 1e6:.0f} MB")
    return secs, psecs


def union_by_name(con, work):
    section("read_parquet([...], union_by_name=true) across runs with different columns")
    a, b = work / "r1.parquet", work / "r2.parquet"
    con.execute(f"COPY (SELECT 1 AS c001, 'x' AS c002) TO '{a.as_posix()}' (FORMAT parquet)")
    con.execute(f"COPY (SELECT 2 AS c001, 'y' AS c002, 'Pune' AS c009) TO '{b.as_posix()}' (FORMAT parquet)")
    rows = con.execute(f"SELECT * FROM read_parquet(['{a.as_posix()}', '{b.as_posix()}'], union_by_name=true) "
                       "ORDER BY c001").fetchall()
    print("  ", rows)
    ok = rows == [(1, "x", None), (2, "y", "Pune")]
    print(f"  RESULT: older run gets NULL for new column: {ok}")
    return ok


def offline_lock(work):
    """Hardened config. NOTE: with only autoinstall/autoload off and lock_configuration on, an explicit
    `INSTALL httpfs` / `INSTALL httpfs FROM core` still downloads from extensions.duckdb.org (seen on 16-11-2026),
    so that case is deliberately not executed here. enable_external_access=false + allowed_directories closes it."""
    section("Offline config: extensions off, external access off, configuration locked")
    data, spill, ext, out = (work / n for n in ("data", "spill", "ext", "elsewhere"))
    for d in (data, spill, ext, out):
        d.mkdir()
    (data / "x.csv").write_text("a\n1\n")
    con = duckdb.connect(str(data / "lock.duckdb"), config={
        "autoinstall_known_extensions": False,
        "autoload_known_extensions": False,
        "allow_community_extensions": False,
        "allow_unsigned_extensions": False,
        "extension_directory": str(ext),                      # empty: no cached extension can be loaded
        "custom_extension_repository": str(work / "no_repo"),  # local, missing: plain INSTALL fails offline
    })
    con.execute(f"SET temp_directory = '{spill.as_posix()}'")
    con.execute("SET memory_limit = '4GB'")
    con.execute(f"SET threads = {os.cpu_count()}")
    con.execute(f"SET allowed_directories = ['{data.as_posix()}/', '{spill.as_posix()}/']")
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    results = {}
    for name, sql in [
        ("SET after lock", "SET memory_limit = '1GB'"),
        ("autoload re-enable", "SET autoload_known_extensions = true"),
        ("external access re-enable", "SET enable_external_access = true"),
        ("INSTALL httpfs", "INSTALL httpfs"),
        ("INSTALL httpfs FROM core", "INSTALL httpfs FROM core"),
        ("LOAD httpfs", "LOAD httpfs"),
        ("read https URL (.invalid host)", "SELECT * FROM read_csv('https://sankalan.invalid/x.csv')"),
        ("read file in data folder", f"SELECT * FROM read_csv('{(data / 'x.csv').as_posix()}')"),
        ("COPY into data folder", f"COPY (SELECT 1) TO '{(data / 'y.csv').as_posix()}'"),
        ("COPY outside allowed dirs", f"COPY (SELECT 1) TO '{(out / 'y.csv').as_posix()}'"),
    ]:
        try:
            con.execute(sql)
            results[name] = "ALLOWED"
        except duckdb.Error as e:
            results[name] = f"refused ({type(e).__name__})"
        print(f"  {name:32} {results[name]}")
    try:   # duckdb_extensions() lists the extension folder, which external-access-off refuses
        loaded = con.execute("SELECT extension_name FROM duckdb_extensions() WHERE loaded").fetchall()
    except duckdb.Error as e:
        loaded = [(f"(duckdb_extensions() refused: {type(e).__name__})",)]
    print("  loaded extensions:", [r[0] for r in loaded])
    print("  extension dir after test:", [p.name for p in ext.rglob("*")])
    settings = dict(con.execute("SELECT name, value FROM duckdb_settings() WHERE name IN "
                                "('memory_limit','threads','temp_directory','lock_configuration',"
                                "'autoinstall_known_extensions','autoload_known_extensions',"
                                "'allow_community_extensions','enable_external_access')").fetchall())
    for k, v in sorted(settings.items()):
        print(f"  {k} = {v}")
    con.close()
    return results, [r[0] for r in loaded]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=10_000_000)
    args = ap.parse_args()
    print("duckdb", duckdb.__version__, "cores", os.cpu_count())
    work = Path(tempfile.mkdtemp(prefix="sankalan_spike_"))
    try:
        con = duckdb.connect(str(work / "spike.duckdb"))
        rounding(con)
        union_by_name(con, work)
        interrupt_latency(con, args.rows)
        copy_speed(con, work, args.rows)
        con.close()
        offline_lock(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
