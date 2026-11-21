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
    out = run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, query, tmp_path / "r1.csv",
                                                         ExportOptions()))
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
