"""Feature A engine on TPL-R small: the Rows view's counts, fetch, pages and export (Feature Spec A2 2, 10.2; Tech
spec A2 T32, T48, 10.2–10.4).

The oracle is independent DuckDB counts over the runs' ``data.parquet`` with hand-written conditions, the generator's
manifest (rows loaded, planted text values, file order) and ``left_out.parquet``; the code under test is
``query/rows.py`` and ``rowsview.py``.
"""
import csv
import io
import re
import threading
import time

import pytest

from conftest import run_job, spec, temp_leftovers
from sankalan import exporting, rowsview
from sankalan.jobs.job import JobState
from sankalan.model import definition as d
from sankalan.model.definition import Filter
from sankalan.model.export import ExportOptions
from sankalan.model.rowspec import RowSpec
from sankalan.query import catalogue as q
from sankalan.query import rows as qr
from sankalan.query.split import LEFT_OUT

INV, DATE_, STATE, TAXABLE, PLACE = "c001", "c002", "c005", "c006", "c021"
SMALL_PARTS = 1000
SHEETS = {"Sales A": 0, "Sales B": 1, "": 2}


@pytest.fixture(scope="module")
def r(tpl_r_runs):
    s, tid = tpl_r_runs["s"], tpl_r_runs["tid"]
    t = q.load_template(s.con, tid)
    ids = [tpl_r_runs["runs"][k] for k in (1, 2, 3)]
    refs = run_job(s.runner, lambda ctx: rowsview.run_refs(ctx.cursor(), s.folder, tid, ids))
    return {**tpl_r_runs, "t": t, "cols": t.columns, "refs": refs, "ids": ids,
            "all": [c.id for c in t.columns if not c.removed]}


def make(r, filters=(), columns=None, show_source=False) -> RowSpec:
    return RowSpec(r["tid"], list(filters), list(r["all"] if columns is None else columns), show_source)


def refs(r, *ks):
    return [r["refs"][k - 1] for k in ks]


def counts(r, sp, *ks):
    return run_job(r["s"].runner, lambda ctx: qr.count_rows(ctx.cursor(), sp, r["cols"], refs(r, *ks)))


def independent(r, where, *ks):
    """count(*) per run with a hand-written condition, over the runs read together (columns a run lacks are null)."""
    files = ", ".join(f"'{x.data_path.as_posix()}'" for x in refs(r, *ks))
    got = dict(r["s"].con.execute(f"SELECT run_id, count(*) FROM read_parquet([{files}], union_by_name = true) "
                                  f"WHERE {where} GROUP BY run_id").fetchall())
    return {x.id: got.get(x.id, 0) for x in refs(r, *ks)}


def rows_run(r, sp, *ks, cap=SMALL_PARTS, drop=None):
    ids = [r["runs"][k] for k in ks]
    return run_job(r["s"].runner, lambda ctx: rowsview.run(ctx, r["s"].folder, r["t"], sp, ids, drop, cap))


def page(r, o, first, count):
    return run_job(r["s"].runner, lambda ctx: rowsview.RowsSource(o).page(ctx, first, count, []))


def table_names(r):
    return sorted(x[0] for x in r["s"].con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE temporary AND table_name LIKE '\\_rows\\_%' ESCAPE '\\'"
    ).fetchall())


def drop(r, o):
    run_job(r["s"].runner, lambda ctx: qr.drop_table(ctx.cursor(), o.table))


def export(r, o, folder, columns=None, part_rows=SMALL_PARTS, name="Rows.csv"):
    folder.mkdir(parents=True, exist_ok=True)
    (src, _n), = run_job(r["s"].runner, rowsview.export_items(o, o.spec.columns if columns is None else columns))
    res, = run_job(r["s"].runner, lambda ctx: exporting.export(ctx, r["s"].paths.temp, [src], folder, [name],
                                                               ExportOptions(), part_rows=part_rows))
    return src, res


def records(res):
    """(header, data rows over every part)."""
    head, out = None, []
    for p in res.paths:
        rows = list(csv.reader(io.StringIO(p.read_bytes().decode("utf-8-sig"), newline="")))
        assert head is None or rows[0] == head
        head = rows[0]
        out += rows[1:]
    return head, out


# ---------------------------------------------------------------------------------------------- counts (ROW-10)
@spec("AC-ROW-10", "ROW-10", "ROW-6", "AC-ROW-6", "TXT-6", "TXT-7")
def test_counts_equal_an_independent_count(r):
    m = r["m"]
    none = counts(r, make(r), 1, 2, 3)
    assert none == {x.id: x.rows_loaded for x in r["refs"]}
    assert sum(none.values()) == m.rows_searched == 7_437
    # with no filters nothing is read: the catalogue's rows loaded
    assert qr.count_rows(None, make(r), r["cols"], refs(r, 1, 2, 3)) == none
    cases = [
        ([Filter(TAXABLE, d.NOT_NUMBER)], "c006_t IS NOT NULL"),
        ([Filter(DATE_, d.NOT_DATE)], "c002_t IS NOT NULL"),
        ([Filter(STATE, d.ONE_OF, ["Maharashtra", "Delhi"]), Filter(TAXABLE, d.BETWEEN, ["1100", "1500.50"])],
         "c005 IN ('Maharashtra', 'Delhi') AND c006 >= 1100 AND c006 <= 1500.50"),
        ([Filter(PLACE, d.ONE_OF, ["Gujarat"])], "c021 = 'Gujarat'"),
        ([Filter(INV, d.CONTAINS, ["inv-2000"])], "contains(lower(c001), 'inv-2000')"),
        ([Filter(TAXABLE, d.BLANK)], "c006 IS NULL AND c006_t IS NULL"),
        ([Filter(INV, d.BLANK)], "(c001 IS NULL OR trim(c001, ' ') = '')"),
    ]
    for filters, where in cases:
        got = counts(r, make(r, filters), 1, 2, 3)
        assert got == independent(r, where, 1, 2, 3), filters
    assert counts(r, make(r, [Filter(TAXABLE, d.NOT_NUMBER)]), 1, 2, 3)[r["runs"][1]] == 16
    assert counts(r, make(r, [Filter(DATE_, d.NOT_DATE)]), 1, 2, 3)[r["runs"][2]] == 5
    assert counts(r, make(r, [Filter(PLACE, d.ONE_OF, ["Gujarat"])]), 1)[r["runs"][1]] == 0      # ROW-14
    assert counts(r, make(r, [Filter(INV, d.BLANK)]), 3)[r["runs"][3]] == m.run(3).no_invoice_no >= 400


# ---------------------------------------------------------------------------------------------- fetch (ROW-11, T48)
def _stored(r, where, k, limit):
    path = r["refs"][k - 1].data_path.as_posix()
    return [(k, f, row) for f, row in r["s"].con.execute(
        f"SELECT _src_file, _src_row FROM read_parquet('{path}') WHERE {where} ORDER BY _src_file, _src_row "
        f"LIMIT {limit}").fetchall()]


@spec("AC-ROW-11a", "ROW-11", "ROW-12", "T48", "T32")
def test_fetch_crosses_runs_in_stored_order_and_pages_by_seq(r):
    sp = make(r, [Filter(STATE, d.ONE_OF, ["Maharashtra"])])
    o = rows_run(r, sp, 1, 2, 3, cap=SMALL_PARTS)
    try:
        c = independent(r, "c005 = 'Maharashtra'", 1, 2, 3)
        n1 = c[r["runs"][1]]
        assert 0 < n1 < SMALL_PARTS < n1 + c[r["runs"][2]]          # R-0001 alone can't fill the table
        assert o.counts == c and o.match == sum(c.values()) and o.held == SMALL_PARTS and o.capped
        assert o.searched == 7_437
        con = r["s"].con
        got = con.execute(f"SELECT run_id, _src_file, _src_row, _seq FROM {o.table} ORDER BY _seq").fetchall()
        assert [x[3] for x in got] == list(range(1, SMALL_PARTS + 1))
        num = {x.id: x.number for x in r["refs"]}
        want = _stored(r, "c005 = 'Maharashtra'", 1, n1) + _stored(r, "c005 = 'Maharashtra'", 2, SMALL_PARTS - n1)
        assert [(num[x[0]], x[1], x[2]) for x in got] == want
        # pages read a _seq range; the source's display rows follow it
        full = qr.rows_page(con, o.table, r["cols"], 0, SMALL_PARTS)
        assert qr.rows_page(con, o.table, r["cols"], 200, 200) == full[200:400]
        assert qr.rows_page(con, o.table, r["cols"], 900, 200) == full[900:]
        shown = page(r, o, 200, 200)
        assert len(shown) == 200 and [int(x[-2].replace(",", "")) for x in shown] == [x[2] for x in got[200:400]]
        assert o.footer() == (f"Showing the first 1,000 of {o.match:,} rows, in the order they were loaded. Export "
                              "gets all of them.")
        assert o.summary().startswith(f"{o.match:,} rows match · 3 runs · 7,437 rows searched · ")
        # under the cap: everything, "Showing all N rows"
        small = rows_run(r, make(r, [Filter(TAXABLE, d.NOT_NUMBER)]), 1, 2, 3)
        assert small.held == small.match == 16 and not small.capped and small.footer() == "Showing all 16 rows"
        drop(r, small)
    finally:
        drop(r, o)
    assert table_names(r) == []


@spec("AC-ROW-S2", "2.4", "T48")
def test_cancel_keeps_the_previous_table_and_drops_the_new_one(r, monkeypatch):
    s = r["s"]
    old = rows_run(r, make(r), 1, cap=100)
    started, release = threading.Event(), threading.Event()

    def hold(ctx):
        started.set()
        end = time.monotonic() + 20              # never outlive a failed test
        while not ctx.cancel_requested and time.monotonic() < end:
            release.wait(0.01)
    monkeypatch.setattr(rowsview, "_before_fetch", hold)
    ids = [r["runs"][1]]
    job = s.runner.start("Rows view", lambda ctx: rowsview.run(ctx, s.folder, r["t"], make(r), ids, [old], 100))
    assert started.wait(10)
    assert job.progress().stage == rowsview.fetch_stage(100)
    job.cancel()
    assert job.wait(10) and job.state is JobState.CANCELLED
    assert table_names(r) == [old.table]                            # the new table is gone, the previous one kept
    assert len(page(r, old, 0, 50)) == 50
    monkeypatch.setattr(rowsview, "_before_fetch", None)
    new = rows_run(r, make(r), 1, cap=100, drop=[old])             # a finished Run drops the previous table
    assert table_names(r) == [new.table] and old.table is None
    drop(r, new)
    assert temp_leftovers(s.paths.temp) == []


# ---------------------------------------------------------------------------------------------- export (ROW-8, ROW-12)
@spec("AC-ROW-11b", "AC-ROW-12a", "AC-ROW-12b", "AC-ROW-8", "ROW-8", "ROW-12", "EXP-8")
def test_export_in_parts_stored_order_and_byte_identical(r, tmp_path):
    files = {k: r["m"].files[str(k)] for k in (1, 2, 3)}
    o = rows_run(r, make(r), 1, 2, 3, cap=SMALL_PARTS)
    try:
        src, res = export(r, o, tmp_path / "a")
        assert src.rows == o.match == 7_437 and [c.rows for c in src.chunks] == [2500, 2437, 2500]
        assert all("ORDER BY _src_file, _src_row" in c.sql for c in src.chunks)
        assert len(res.paths) == exporting.part_count(7_437, SMALL_PARTS) == 8
        head, data = records(res)
        assert head == [c.name for c in r["cols"] if not c.removed] + ["Source File", "Source Sheet", "Source Row",
                                                                       "Run ID"]
        assert len(data) == 7_437                                                                  # AC-ROW-12a
        fi, si, ri, ui = (head.index(h) for h in ("Source File", "Source Sheet", "Source Row", "Run ID"))
        keys = [(int(x[ui][2:]), files[int(x[ui][2:])].index(x[fi]), SHEETS[x[si]], int(x[ri])) for x in data]
        assert keys == sorted(keys) and len(set(keys)) == len(keys)                               # AC-ROW-12b
        assert all(x[si] == "" for x in data if x[fi].endswith(".csv"))                           # AC-ROW-8
        assert {x[si] for x in data if x[fi].endswith(".xlsx")} == {"Sales A", "Sales B"}
        # the grid's rows are the export's first rows, in the same order (AC-ROW-11b)
        grid = page(r, o, 0, SMALL_PARTS)
        assert [(g[-1], g[-4], g[-3], g[-2].replace(",", "")) for g in grid] == \
            [(x[ui], x[fi], x[si], x[ri]) for x in data[:SMALL_PARTS]]
        # the same settings again: byte-identical parts
        _src2, res2 = export(r, o, tmp_path / "b")
        assert [p.name for p in res2.paths] == [p.name for p in res.paths]
        assert all(a.read_bytes() == b.read_bytes() for a, b in zip(res.paths, res2.paths))
        # ticked columns in the chosen order, then the source columns
        _src3, res3 = export(r, o, tmp_path / "c", columns=[TAXABLE, INV], part_rows=10 ** 6, name="two.csv")
        head3, data3 = records(res3)
        assert head3 == ["Taxable Value", "Invoice No", "Source File", "Source Sheet", "Source Row", "Run ID"]
        assert [x[1] for x in data3] == [x[0] for x in data]
    finally:
        drop(r, o)
    assert temp_leftovers(r["s"].paths.temp) == []


@spec("AC-ROW-13", "ROW-13")
def test_left_out_rows_never_appear(r, tmp_path):
    s, tid, rid = r["s"], r["tid"], r["runs"][2]
    left = s.folder.run_dir(tid, rid) / LEFT_OUT
    out = set(s.con.execute(f"SELECT _src_file, _src_row FROM read_parquet('{left.as_posix()}')").fetchall())
    assert len(out) == 63
    sp = make(r)
    assert counts(r, sp, 2) == {rid: 2437}
    assert counts(r, make(r, [Filter(INV, d.CONTAINS, ["INV/"])]), 2) == {rid: 0}
    o = rows_run(r, sp, 2, cap=10_000)
    try:
        held = set(s.con.execute(f"SELECT _src_file, _src_row FROM {o.table}").fetchall())
        assert o.held == 2437 and not (held & out)
        _src, res = export(r, o, tmp_path)
        head, data = records(res)
        assert len(data) == 2437
        assert not any(x[head.index("Invoice No")].startswith("INV/") for x in data)
    finally:
        drop(r, o)


@spec("AC-ROW-14", "ROW-14", "AC-TXT-1", "TXT-2", "TXT-4")
def test_new_column_blank_for_older_runs_and_text_as_typed(r, tmp_path):
    o = rows_run(r, make(r), 1, 2, cap=10_000)
    try:
        cols = [c for c in r["cols"] if not c.removed]
        pi, ti = [c.id for c in cols].index(PLACE), [c.id for c in cols].index(TAXABLE)
        grid = page(r, o, 0, 10_000)
        assert len(grid) == 2500 + 2437
        assert all(g[pi] == "" for g in grid if g[-1] == "R-0001")                                # AC-ROW-14
        assert sum(1 for g in grid if g[-1] == "R-0002" and g[pi]) > 2000
        _src, res = export(r, o, tmp_path, part_rows=10 ** 6)
        head, data = records(res)
        assert all(x[head.index(PLACE_NAME)] == "" for x in data if x[-1] == "R-0001")
        # text kept in a Number column, as typed, in the grid and the export (AC-TXT-1 Rows half)
        text = sorted(["NA"] * 10 + ["Nil"] * 5 + ["12,000/-"])
        number = re.compile(r"-?[0-9]{1,3}(,[0-9]{3})*\.[0-9]{2}")
        assert sorted(g[ti] for g in grid if g[-1] == "R-0001" and g[ti] and not number.fullmatch(g[ti])) == text
        assert "1,000.00" in {g[ti] for g in grid}                                                 # UI-7 grouping
        plain = re.compile(r"-?[0-9]+\.[0-9]{2}")
        col = head.index("Taxable Value")
        assert sorted(x[col] for x in data if x[-1] == "R-0001" and x[col] and not plain.fullmatch(x[col])) == text
    finally:
        drop(r, o)
    # Invoice Date text in R-0002, as typed, through the Is not a date filter
    o = rows_run(r, make(r, [Filter(DATE_, d.NOT_DATE)]), 1, 2, 3)
    try:
        di = [c.id for c in r["cols"] if not c.removed].index(DATE_)
        assert sorted(g[di] for g in page(r, o, 0, 100)) == ["31-02-2026"] * 2 + ["NA"] * 3
    finally:
        drop(r, o)


PLACE_NAME = "Place of Supply"


@spec("ROW-7", "2.4")
def test_refused_without_runs_or_columns(r):
    with pytest.raises(d.DefinitionError, match="Tick at least one column"):
        rows_run(r, make(r, columns=[]), 1)
    with pytest.raises(d.DefinitionError, match="Tick at least one run"):
        rows_run(r, make(r))
    assert table_names(r) == []
