"""Full-size TPL-R (``slow``; Tech spec A2 T32, 14.2 Stored order; AC-BUG-1c).

Three runs of 2,500,000 rows each, read by reader workers and converted by DuckDB in parallel, committed through
the real pipeline on a storage with a 1 GiB memory limit (so DuckDB spills, as in BUG-1). ``data.parquet`` must be
strictly ascending in (_src_file, _src_row), and a run-data export must come out in the same order.

    pytest -m slow tests/engine/test_stored_order.py
"""
import csv

import pytest

from conftest import commit_tpl_r_runs, open_storage, run_job, spec
from sankalan import exporting
from sankalan.model.export import ExportOptions
from sankalan.query import catalogue as q
from sankalan.query import export as qx

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def full(tmp_path_factory, tpl_r_full):
    fx, m = tpl_r_full
    s = open_storage(tmp_path_factory.mktemp("tpl_r_full"))
    info = commit_tpl_r_runs(s, fx, m, workers=3)
    yield {"s": s, "m": m, **info}
    s.close()


@spec("AC-BUG-1c", "BUG-1")
def test_all_three_full_size_runs_commit(full):
    runs = q.list_runs(full["s"].con, full["tid"])
    assert [(r.label, r.rows_loaded) for r in runs] == [("R-0001", 2_500_000), ("R-0002", 2_499_937),
                                                         ("R-0003", 2_500_000)]
    assert sum(r.rows_loaded for r in runs) == 7_499_937
    texts = {r.label: q.run_details(full["s"].con, r.id)["text_counts"] for r in runs}
    assert texts["R-0001"]["c006"] == 1_510 and texts["R-0002"]["c002"] == 305


@spec("T32", "R7", "8.7")
def test_data_parquet_ascending_and_export_in_the_same_order(full, tmp_path):
    s, tid = full["s"], full["tid"]
    for rid in full["runs"].values():
        data = s.folder.run_dir(tid, rid) / "data.parquet"
        bad = s.con.execute(                     # in the file's physical row order
            f"SELECT count(*) FROM (SELECT _src_file, _src_row, lag(_src_file) OVER w AS pf, lag(_src_row) OVER w "
            f"AS pr FROM read_parquet('{data.as_posix()}', file_row_number = true) "
            f"WINDOW w AS (ORDER BY file_row_number)) "
            f"WHERE pf IS NOT NULL AND (pf > _src_file OR (pf = _src_file AND pr >= _src_row))").fetchone()[0]
        assert bad == 0
    rid = full["runs"][1]
    cols = q.load_template(s.con, tid).columns
    names = {f["file_index"]: f["file_name"] for f in q.run_details(s.con, rid)["files"]}
    query = qx.run_data(s.con, s.folder.run_dir(tid, rid) / "data.parquet", cols, names, "R-0001")
    out, = run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, [query], tmp_path, ["r1.csv"],
                                                          ExportOptions(), part_rows=10 ** 9))
    assert out.rows == 2_500_000
    files = full["m"].files["1"]
    with open(out.path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        head = next(r)
        fi, si, ri = head.index("Source File"), head.index("Source Sheet"), head.index("Source Row")
        prev = None
        n = 0
        for rec in r:
            key = (files.index(rec[fi]), {"Sales A": 0, "Sales B": 1}.get(rec[si], 2), int(rec[ri]))
            assert prev is None or key > prev, (prev, key)
            prev = key
            n += 1
    assert n == 2_500_000


@spec("AC-EXP-8b", "AC-EXP-9a", "AC-EXP-9b", "EXP-9", "T37")
def test_full_size_run_export_splits_into_three_parts(full, tmp_path):
    """A2-3: R-0002's data (2,499,937 rows) at the real part size: 3 parts of at most 1,048,576 records (Excel's
    limit), each with the BOM and header, continuing the stored order across the cuts."""
    s, tid = full["s"], full["tid"]
    rid = full["runs"][2]
    cols = q.load_template(s.con, tid).columns
    names = {f["file_index"]: f["file_name"] for f in q.run_details(s.con, rid)["files"]}
    query = qx.run_data(s.con, s.folder.run_dir(tid, rid) / "data.parquet", cols, names, "R-0002")
    out, = run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, [query], tmp_path, ["R2.csv"],
                                                          ExportOptions()))
    assert [p.name for p in out.paths] == ["R2_part01of03.csv", "R2_part02of03.csv", "R2_part03of03.csv"]
    files = full["m"].files["2"]
    counts, prev, header = [], None, None
    for path in out.paths:
        raw = path.open("rb").read(3)
        assert raw == b"\xef\xbb\xbf"
        with open(path, encoding="utf-8-sig", newline="") as f:
            r = csv.reader(f)
            head = next(r)
            assert header is None or head == header
            header = head
            fi, si, ri = head.index("Source File"), head.index("Source Sheet"), head.index("Source Row")
            n = 0
            for rec in r:
                key = (files.index(rec[fi]), {"Sales A": 0, "Sales B": 1}.get(rec[si], 2), int(rec[ri]))
                assert prev is None or key > prev, (prev, key)
                prev = key
                n += 1
        counts.append(n)
    assert counts == [1_000_000, 1_000_000, 499_937] and max(counts) <= 1_048_576


# ---------------------------------------------------------------------------------------------- A2-5: Rows view
def _rows_refs(full):
    from sankalan import rowsview
    s, tid = full["s"], full["tid"]
    ids = [full["runs"][k] for k in (1, 2, 3)]
    return run_job(s.runner, lambda ctx: rowsview.run_refs(ctx.cursor(), s.folder, tid, ids)), ids


@spec("AC-ROW-10", "AC-ROW-11a", "AC-ROW-12a", "AC-ROW-12b", "ROW-12", "T48", "T32")
def test_full_size_rows_view_count_fetch_and_export(full, tmp_path):
    """A2-5: rows searched 7,499,937; the first 100,000 in stored order; every row exported in parts at the real
    part size, Run ID never going back and rows ascending (file, sheet, row) within each run."""
    from sankalan import rowsview
    from sankalan.model.definition import Filter
    from sankalan.model.rowspec import RowSpec
    from sankalan.model import definition as d
    from sankalan.query import rows as qr
    s, tid = full["s"], full["tid"]
    t = q.load_template(s.con, tid)
    refs, ids = _rows_refs(full)
    all_cols = [c.id for c in t.columns if not c.removed]
    spec_ = RowSpec(tid, [], all_cols)
    o = run_job(s.runner, lambda ctx: rowsview.run(ctx, s.folder, t, spec_, ids))
    try:
        assert o.searched == o.match == 7_499_937 and o.held == 100_000 and o.capped
        got = s.con.execute(f"SELECT run_id, _src_file, _src_row, _seq FROM {o.table} ORDER BY _seq").fetchall()
        assert [x[3] for x in got] == list(range(1, 100_001)) and {x[0] for x in got} == {full["runs"][1]}
        keys = [(x[1], x[2]) for x in got]
        assert keys == sorted(keys) and len(set(keys)) == 100_000
        # a filter: counts equal an independent count(*)
        f = RowSpec(tid, [Filter("c006", d.NOT_NUMBER)], all_cols)
        counts = run_job(s.runner, lambda ctx: qr.count_rows(ctx.cursor(), f, t.columns, refs))
        assert counts == {full["runs"][1]: 1_510, full["runs"][2]: 0, full["runs"][3]: 0}
        (src, _n), = run_job(s.runner, rowsview.export_items(o, all_cols))
        out, = run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, [src], tmp_path, ["rows.csv"],
                                                              ExportOptions()))
        assert len(out.paths) == 8 and out.rows == 7_499_937
        files = {k: full["m"].files[str(k)] for k in (1, 2, 3)}
        sheets = {"Sales A": 0, "Sales B": 1, "": 2}
        prev, n, first = None, 0, []
        for path in out.paths:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                r = csv.reader(fh)
                head = next(r)
                fi, si, ri, ui = (head.index(h) for h in ("Source File", "Source Sheet", "Source Row", "Run ID"))
                for rec in r:
                    run = int(rec[ui][2:])
                    key = (run, files[run].index(rec[fi]), sheets[rec[si]], int(rec[ri]))
                    assert prev is None or key > prev, (prev, key)
                    prev = key
                    if n < 100_000:
                        first.append((rec[ui], int(rec[ri])))
                    n += 1
        assert n == 7_499_937
        assert first == [("R-0001", x[2]) for x in got]                       # AC-ROW-11b at full size
    finally:
        run_job(s.runner, lambda ctx: qr.drop_table(ctx.cursor(), o.table))
