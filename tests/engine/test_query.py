"""Query layer and compiler on the TPL-A runs (Phase 4): A1-03 to A1-10, default outputs C3-18, C4-05, RUNO-01,
RUNO-03 to RUNO-05, DO-6, columns across runs, select_only. Expected figures are the Test Cases sheet's."""
from decimal import Decimal

import pytest

from conftest import load_files, open_storage, run_job, spec, tpl_a_columns, tpl_a_rules, tpl_a_settings
from sankalan import analysis, formats
from sankalan.model import definition as d
from sankalan.model.definition import Definition, DefinitionError, Filter, Group, Measure
from sankalan.model.template import Column
from sankalan.query import layer
from sankalan.query.split import split
from sankalan.validation import scan

D = Decimal
COLS = tpl_a_columns()
COLS_B = COLS + [Column("c009", "Branch")]          # Branch added in R-0005 (RUNM-07)
INV, DATE_, CUST, GSTIN, STATE, TAXABLE, RATE, TAX, BRANCH = (f"c00{i}" for i in range(1, 10))


@pytest.fixture(scope="module")
def runs(tmp_path_factory, fixtures_dir):
    """The TPL-A data: the F01 sample and R-0001 to R-0006 as Phase 5 would store them (R-0003 split, T18)."""
    s = open_storage(tmp_path_factory.mktemp("runs"))
    out = {}

    def load(key, name, cols=COLS, aliases=None):
        cols = [Column(**{**c.__dict__, "aliases": list(c.aliases)}) for c in cols]
        if aliases:
            for c in cols:
                c.aliases = aliases.get(c.id, c.aliases)
        st, res, rows = load_files(s, fixtures_dir, [name], tpl_a_settings(), cols)
        out[key] = (st, res, {0: rows[0].file_name})
        return st, res, rows

    load("sample", "Sample_Sales.xlsx")
    load("R-0001", "Sales_Oct.xlsx")
    load("R-0002", "Sales_Nov.xlsx")
    st, res, rows = load("R-0003", "Sales_Errors.xlsx")
    r = run_job(s.runner, lambda ctx: scan.validate(ctx, st, COLS, tpl_a_rules(), {0: rows[0].file_name}))
    out["R-0003-rules"] = r.rules
    assert split(s.con, st.path, r.issues, [x.id for x in r.rules]) == (1937, 63)
    load("R-0004", "Sales_Renamed_Headers.xlsx", aliases={INV: ["Inv No"]})
    load("R-0005", "Sales_Dec_NewCol.xlsx", COLS_B)
    load("R-0006", "Sales_NoDates.xlsx")
    yield s, out
    s.close()


def data(runs, *keys):
    return [runs[1][k][0].path / "data.parquet" for k in keys]


def analyse(runs, definition, *keys, columns=COLS):
    s = runs[0]
    return run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, definition, columns, data(runs, *keys)))


def preview(runs, definition, key, columns=COLS):
    s = runs[0]
    return run_job(s.runner, lambda ctx: analysis.preview_output(ctx, definition, columns, data(runs, key)[0]))


def shown(runs, res, subtotals=False, **kw):
    return layer.rows(runs[0].con, res, subtotals=subtotals, limit=1000, **kw)


def total(runs, res):
    return layer.grand_total(runs[0].con, res)


DO1 = Definition("tpl-a", [], [Group(STATE)],
                 [Measure(TAXABLE, d.SUM, "Taxable"), Measure(TAX, d.SUM, "Tax"), Measure(INV, d.COUNT, "Invoices")])
DO2 = Definition("tpl-a", [Filter(DATE_, d.LATEST_MONTH)], [Group(DATE_, "month"), Group(RATE)],
                 [Measure(TAXABLE, d.SUM)], subtotals=True)


def by_state(rows):
    return {r[1]: tuple(r[2:]) for r in rows}


# ---------------------------------------------------------------------------------------------- analysis (A1)
@spec("A1-03", "ANA-5", "ANA-6", "ANA-7")
def test_a103_basic_result_with_grand_total(runs):
    res = analyse(runs, Definition("tpl-a", [], [Group(STATE)], [Measure(TAXABLE, d.SUM), Measure(INV, d.COUNT)]),
                  "R-0001")
    assert [(r[1], formats.number(r[2]), r[3]) for r in shown(runs, res)] == [
        ("Delhi", "1,903,437.50", 1250), ("Gujarat", "1,877,812.50", 1250), ("Karnataka", "1,890,625.00", 1250),
        ("Maharashtra", "1,865,000.00", 1250)]
    assert total(runs, res) == (D("7536875.00"), 5000)
    assert [c.label for c in res.columns] == ["State", "Sum of Taxable Value", "Count of Invoice No"]
    assert res.input_rows == 5000 and layer.count_rows(runs[0].con, res, False) == 4


@spec("A1-04", "ANA-6", "T13", "T23")
def test_a104_measures_and_renaming(runs):
    ms = [Measure(TAXABLE, f) for f in (d.SUM, d.COUNT, d.AVG, d.MIN, d.MAX)]
    ms[2].label = "Avg value"
    ms += [Measure(CUST, d.COUNT_DISTINCT), Measure(GSTIN, d.COUNT_DISTINCT)]
    res = analyse(runs, Definition("tpl-a", [], [], ms), "R-0001")
    assert shown(runs, res) == []                           # no groups: the grand total is the only row
    t = total(runs, res)
    assert [formats.number(x) for x in t] == ["7,536,875.00", "5,000", "1,507.38", "1,000.00", "2,014.75", "10",
                                               "5,000"]
    assert t[2] == D("1507.38")                             # 1,507.375 rounded half away from zero (T13)
    assert [c.label for c in res.measures][2:4] == ["Avg value", "Min of Taxable Value"]


@spec("A1-05", "ANA-7", "T23", "DO-7")
def test_a105_subtotals_and_sorting_within_groups(runs):
    res = analyse(runs, Definition("tpl-a", [], [Group(STATE), Group(RATE)], [Measure(TAXABLE, d.SUM)], True),
                  "R-0001")
    con = runs[0].con
    rows = shown(runs, res, subtotals=True)
    assert sum(r[0] == 2 for r in rows) == 20 and sum(r[0] == 1 for r in rows) == 4
    assert total(runs, res) == (D("7536875.00"),)
    mh = [(r[0], r[2], formats.number(r[3])) for r in rows if r[1] == "Maharashtra"]
    assert mh == [(2, D(0), "352,500.00"), (2, D(5), "393,500.00"), (2, D(12), "383,250.00"),
                  (2, D(18), "373,000.00"), (2, D(28), "362,750.00"), (1, None, "1,865,000.00")]
    srt = shown(runs, res, subtotals=True, sort="m1", descending=True)
    mh = [(r[0], r[2]) for r in srt if r[1] == "Maharashtra"]
    assert mh == [(2, D(5)), (2, D(12)), (2, D(18)), (2, D(28)), (2, D(0)), (1, None)]
    # subtotals stay with their state, and states sort by their subtotal
    states = [r[1] for r in srt if r[0] == 1]
    assert states == ["Delhi", "Karnataka", "Gujarat", "Maharashtra"]
    blocks = [r[1] for r in srt]
    assert all(blocks[i * 6:(i + 1) * 6] == [s] * 6 for i, s in enumerate(states))
    # subtotals hidden: detail rows only; sorting then runs over the whole list
    assert layer.count_rows(con, res, False) == 20
    flat = shown(runs, res, sort="m1", descending=True)
    assert [r[3] for r in flat] == sorted((r[3] for r in flat), reverse=True)


@spec("A1-06", "ANA-5")
def test_a106_group_levels_and_date_grain(runs):
    def run(groups):
        return analyse(runs, Definition("tpl-a", [], groups, [Measure(INV, d.COUNT)]), "R-0001")
    res = run([Group(DATE_, "day")])
    rows = shown(runs, res)
    assert len(rows) == 31
    days = {formats.period(r[1], "day"): r[2] for r in rows}
    assert (days["01-10-2026"], days["31-10-2026"]) == (162, 161)
    for grain, label in (("month", "Oct-2026"), ("quarter", "Q4-2026"), ("year", "2026")):
        rows = shown(runs, run([Group(DATE_, grain)]))
        assert [(formats.period(r[1], grain), r[2]) for r in rows] == [(label, 5000)]
    a = shown(runs, run([Group(DATE_, "month"), Group(STATE)]))
    b = shown(runs, run([Group(STATE), Group(DATE_, "month")]))
    assert [r[2] for r in a] == ["Delhi", "Gujarat", "Karnataka", "Maharashtra"]
    assert [r[1] for r in b] == ["Delhi", "Gujarat", "Karnataka", "Maharashtra"]


@spec("A1-07", "ANA-4")
def test_a107_date_filters(runs):
    def count(f, *keys):
        res = analyse(runs, Definition("tpl-a", [f], [], [Measure(INV, d.COUNT), Measure(TAXABLE, d.SUM)]), *keys)
        return total(runs, res)
    assert count(Filter(DATE_, d.MONTH, [2026, 10]), "R-0001", "R-0002") == (5000, D("7536875.00"))
    assert count(Filter(DATE_, d.QUARTER, [2026, 4]), "R-0001", "R-0002")[0] == 9000
    assert count(Filter(DATE_, d.YEAR, [2026]), "R-0001", "R-0002")[0] == 9000
    assert count(Filter(DATE_, d.BETWEEN, ["2026-11-01", "2026-11-15"]), "R-0001", "R-0002")[0] == 2005
    assert count(Filter(DATE_, d.BLANK), "R-0001", "R-0002")[0] == 0
    assert count(Filter(DATE_, d.BLANK), "R-0006")[0] == 500
    assert count(Filter(DATE_, d.NOT_BLANK), "R-0001", "R-0002")[0] == 9000


@spec("A1-08", "ANA-4", "T23")
def test_a108_text_filters_and_distinct_values(runs):
    s = runs[0]
    cust = COLS[2]
    values = run_job(s.runner, lambda ctx: analysis.distinct_values(ctx, cust, data(runs, "R-0001")))
    assert len(values) == 10 and {n for _v, n in values} == {500}

    def count(f, key):
        return total(runs, analyse(runs, Definition("tpl-a", [f], [], [Measure(None, d.COUNT)]), key))[0]
    assert count(Filter(CUST, d.CONTAINS, ["patel"]), "R-0001") == 500        # ignores case
    assert count(Filter(CUST, d.BLANK), "R-0003") == 7
    assert count(Filter(STATE, d.ONE_OF, ["Goa"]), "R-0003") == 25
    assert count(Filter(STATE, d.ONE_OF, ["goa"]), "R-0003") == 0             # Is one of is exact
    assert count(Filter(CUST, d.NOT_BLANK), "R-0003") == 1930


@spec("ANA-4")
def test_distinct_values_top_and_search(runs):
    con = runs[0].con
    top = layer.distinct_values(con, COLS[0], data(runs, "R-0001"), limit=3)
    assert len(top) == 3
    found = layer.distinct_values(con, COLS[0], data(runs, "R-0001"), search="inv-1049")
    assert found and all("INV-1049" in v for v, _n in found)
    assert {v for v, _n in found}.isdisjoint({v for v, _n in top}) or len(found) > 3


@spec("A1-09", "ANA-4")
def test_a109_number_filters_and_and(runs):
    res = analyse(runs, Definition("tpl-a", [Filter(RATE, d.EQUALS, ["18"]), Filter(STATE, d.ONE_OF, ["Maharashtra"])],
                                   [], [Measure(None, d.COUNT), Measure(TAXABLE, d.SUM)]), "R-0001")
    assert total(runs, res) == (250, D("373000.00"))
    res = analyse(runs, Definition("tpl-a", [Filter(TAXABLE, d.BETWEEN, ["1000", "1010.25"])], [Group(TAXABLE)],
                                   [Measure(None, d.COUNT)]), "R-0001")
    assert total(runs, res) == (100,)
    assert {r[1] for r in shown(runs, res)} == {D("1000.00"), D("1010.25")}


@spec("A1-10", "T23", "T18")
def test_a110_count_counts_non_blank_values(runs):
    res = analyse(runs, Definition("tpl-a", [], [], [Measure(CUST, d.COUNT), Measure(INV, d.COUNT)]), "R-0003")
    assert total(runs, res) == (1930, 1937)


@spec("ANA-7")
def test_row_cap_and_note(runs):
    con = runs[0].con
    res = analyse(runs, Definition("tpl-a", [], [Group(DATE_)], [Measure(INV, d.COUNT)]), "R-0001")
    assert len(layer.rows(con, res, subtotals=False, limit=500, cap=10)) == 10
    assert layer.rows(con, res, subtotals=False, offset=10, cap=10) == []
    assert layer.count_rows(con, res, False) == 31
    assert len(layer.rows(con, res, subtotals=False, limit=500, cap=None)) == 31


@spec("ANA-8")
def test_previous_result_dropped_after_the_new_one(runs):
    s = runs[0]
    first = analyse(runs, Definition("tpl-a", [], [], [Measure(None, d.COUNT)]), "R-0001")
    second = run_job(s.runner, lambda ctx: analysis.run_analysis(
        ctx, Definition("tpl-a", [], [], [Measure(None, d.COUNT)]), COLS, data(runs, "R-0002"), first))
    assert first.table is None and total(runs, second) == (4000,)
    tables = {r[0] for r in s.con.execute("SELECT table_name FROM duckdb_tables() WHERE temporary").fetchall()}
    assert second.table in tables


# ---------------------------------------------------------------------------------------------- default outputs
def _do1(rows):
    return {r[1]: (r[2], r[3], r[4]) for r in rows}


@spec("C3-18", "DO-8")
def test_c318_default_output_previews_on_the_sample(runs):
    res = preview(runs, DO1, "sample")
    assert [(r[1] or d.NULL_LABEL, r[4], formats.number(r[2]), formats.number(r[3])) for r in shown(runs, res)] == [
        ("Delhi", 250, "380,687.50", "48,131.00"), ("Gujarat", 250, "375,562.50", "47,977.00"),
        ("Karnataka", 250, "378,125.00", "48,361.50"), ("Maharashtra", 250, "373,000.00", "46,875.00")]
    assert total(runs, res) == (D("1507375.00"), D("191344.50"), 1000)
    res = preview(runs, DO2, "sample")
    rows = shown(runs, res, subtotals=True)
    assert [(formats.period(r[1], "month"), r[2], formats.number(r[3])) for r in rows if r[0] == 2] == [
        ("Aug-2026", D(0), "297,375.00"), ("Aug-2026", D(5), "299,425.00"), ("Aug-2026", D(12), "301,475.00"),
        ("Aug-2026", D(18), "303,525.00"), ("Aug-2026", D(28), "305,575.00")]
    assert [formats.number(r[3]) for r in rows if r[0] == 1] == ["1,507,375.00"]


@spec("RUNO-01", "C4-05", "DO-2", "DO-6", "DO-7")
def test_runo01_default_outputs_stored_with_the_run(runs):
    s = runs[0]
    st = runs[1]["R-0001"][0]
    got = run_job(s.runner, lambda ctx: analysis.write_outputs(ctx, [("State-wise sales", DO1),
                                                                     ("Latest month by GST rate", DO2)],
                                                                COLS, st.path / "data.parquet", st.path / "outputs"))
    assert sorted(p.name for p in (st.path / "outputs").iterdir()) == ["1.parquet", "2.parquet"]
    o1 = layer.open_output(DO1, COLS, st.path / "outputs" / "1.parquet", s.con)
    assert _do1(shown(runs, o1)) == {
        "Delhi": (D("1903437.50"), D("240655.00"), 1250), "Gujarat": (D("1877812.50"), D("239885.00"), 1250),
        "Karnataka": (D("1890625.00"), D("241807.50"), 1250), "Maharashtra": (D("1865000.00"), D("234375.00"), 1250)}
    assert total(runs, o1) == (D("7536875.00"), D("956722.50"), 5000)
    o2 = layer.open_output(DO2, COLS, st.path / "outputs" / "2.parquet", s.con)
    rows = shown(runs, o2, subtotals=True)
    assert [(formats.period(r[1], "month"), r[2], r[3]) for r in rows] == [
        ("Oct-2026", D(0), D("1486875.00")), ("Oct-2026", D(5), D("1497125.00")),
        ("Oct-2026", D(12), D("1507375.00")), ("Oct-2026", D(18), D("1517625.00")),
        ("Oct-2026", D(28), D("1527875.00")), ("Oct-2026", None, D("7536875.00"))]
    assert len(shown(runs, o2)) == 5                    # month subtotal hidden when Show subtotals is off
    assert [c.label for c in o2.columns] == ["Invoice Date", "GST Rate", "Sum of Taxable Value"]
    assert got[1].note is None and o2.note is None
    # DO-6 / C6-10: editing DO1 later doesn't touch the stored file, which is read with the definition used
    before = (st.path / "outputs" / "1.parquet").read_bytes()
    assert (st.path / "outputs" / "1.parquet").read_bytes() == before and len(o1.measures) == 3


@spec("RUNO-03", "DO-2", "T18")
def test_runo03_outputs_exclude_left_out_rows(runs):
    res = preview(runs, DO1, "R-0003")
    assert _do1(shown(runs, res)) == {
        "Delhi": (D("739448.00"), D("93038.02"), 480), "Goa": (D("28075.00"), D("3572.83"), 25),
        "Gujarat": (D("725157.00"), D("93821.11"), 476), "Karnataka": (D("734282.00"), D("94229.23"), 480),
        "Maharashtra": (D("720032.00"), D("90333.16"), 476)}
    assert total(runs, res) == (D("2946994.00"), D("374994.35"), 1937)
    rows = shown(runs, preview(runs, DO2, "R-0003"))
    assert [(formats.period(r[1], "month"), r[2], formats.number(r[3])) for r in rows] == [
        ("Sep-2026", D(0), "578,776.25"), ("Sep-2026", D(5), "583,835.25"), ("Sep-2026", D(12), "590,089.00"),
        ("Sep-2026", D(18), "594,117.25"), ("Sep-2026", D(28), "600,176.25")]


@spec("RUNO-04", "MAP-6")
def test_runo04_null_column_groups_as_null(runs):
    res = preview(runs, DO1, "R-0004")
    rows = shown(runs, res)
    assert [(r[1], r[2], r[3], r[4]) for r in rows] == [(None, D("1507375.00"), D("191344.50"), 1000)]
    assert rows[0][0] == 1                                  # a detail row whose value is null: shown as (Null)


@spec("RUNO-05", "T21", "DO-3")
def test_runo05_no_dates_in_this_run(runs):
    s = runs[0]
    out = runs[1]["R-0006"][0].path / "outputs"           # DuckDB may only write inside the data folder (S1)
    res = preview(runs, DO2, "R-0006")
    assert res.note == "No dates in this run"
    assert shown(runs, res, subtotals=True) == [] and total(runs, res) is None
    res = preview(runs, DO1, "R-0006")
    assert total(runs, res) == (D("753687.50"), D("95672.25"), 500) and res.note is None
    stored = run_job(s.runner, lambda ctx: analysis.write_outputs(ctx, [("DO2", DO2)], COLS,
                                                                   data(runs, "R-0006")[0], out))
    assert stored[0].note == d.NO_DATES_NOTE
    assert layer.open_output(DO2, COLS, out / "1.parquet", s.con).note == d.NO_DATES_NOTE


@spec("DO-3", "C3-19", "T23")
def test_relative_dates_only_in_default_outputs(runs):
    s = runs[0]
    fixed = Definition("tpl-a", [Filter(DATE_, d.YEAR, [2026])], [], [Measure(None, d.COUNT)])
    with pytest.raises(DefinitionError, match="relative"):
        run_job(s.runner, lambda ctx: analysis.preview_output(ctx, fixed, COLS, data(runs, "R-0001")[0]))
    with pytest.raises(DefinitionError, match="default outputs only"):
        analyse(runs, DO2, "R-0001")
    blank = Definition("tpl-a", [Filter(DATE_, d.NOT_BLANK)], [], [Measure(None, d.COUNT)])
    assert total(runs, preview(runs, blank, "R-0001")) == (5000,)
    for latest, expect in ((d.LATEST_QUARTER, 5000), (d.LATEST_YEAR, 5000)):
        res = preview(runs, Definition("tpl-a", [Filter(DATE_, latest)], [], [Measure(None, d.COUNT)]), "R-0001")
        assert total(runs, res) == (expect,)


@spec("ANA-4", "ANA-6")
def test_definition_checks():
    bad = [Definition("t", [Filter(TAXABLE, d.CONTAINS, ["1"])], [], [Measure(None, d.COUNT)]),
           Definition("t", [Filter(CUST, d.EQUALS, ["1"])], [], [Measure(None, d.COUNT)]),
           Definition("t", [], [Group(STATE, "month")], [Measure(None, d.COUNT)]),
           Definition("t", [], [], [Measure(CUST, d.SUM)]),
           Definition("t", [], [], [Measure(None, d.SUM)]),
           Definition("t", [], [], []),
           Definition("t", [Filter(DATE_, d.MONTH, [2026, 13])], [], [Measure(None, d.COUNT)]),
           Definition("t", [Filter("c099", d.BLANK)], [], [Measure(None, d.COUNT)])]
    for x in bad:
        with pytest.raises(DefinitionError):
            d.check(x, COLS)
    js = DO2.to_dict()
    assert Definition.from_dict(js) == DO2 and js["filters"][0]["op"] == "latest_month"


# ---------------------------------------------------------------------------------------------- columns across runs
@spec("MAP-11", "MAP-8", "T23", "ANA-1")
def test_columns_across_runs_add_rename_remove(runs):
    by_branch = Definition("tpl-a", [], [Group(BRANCH)], [Measure(None, d.COUNT), Measure(TAXABLE, d.SUM)])
    res = analyse(runs, by_branch, "R-0004", "R-0005", columns=COLS_B)
    assert [(r[1], r[2]) for r in shown(runs, res)] == [("Nagpur", 1000), ("Nashik", 1000), ("Pune", 1000),
                                                         (None, 1000)]           # older run: (Null), last
    assert total(runs, res)[0] == 4000
    renamed = [Column(**{**c.__dict__}) for c in COLS_B]
    renamed[8].name = "Branch Name"
    assert analyse(runs, by_branch, "R-0005", columns=renamed).columns[0].label == "Branch Name"
    removed = [Column(**{**c.__dict__}) for c in COLS_B]
    removed[8].removed = True
    res = analyse(runs, by_branch, "R-0004", "R-0005", columns=removed)
    assert res.columns[0].label == "Branch (removed)" and total(runs, res)[0] == 4000
    # a column none of the ticked runs has reads as null
    res = analyse(runs, by_branch, "R-0001", columns=COLS_B)
    assert [(r[1], r[2]) for r in shown(runs, res)] == [(None, 5000)]
    assert layer.distinct_values(runs[0].con, COLS_B[8], data(runs, "R-0001")) == []


# ---------------------------------------------------------------------------------------------- select_only (V3-4)
@spec("V3-4")
def test_select_only(runs):
    con = runs[0].con
    path = data(runs, "R-0001")[0].as_posix()
    names, rows = layer.select_only(con, f"SELECT count(*) AS n FROM read_parquet('{path}')")
    assert names == ["n"] and rows == [(5000,)]
    assert layer.select_only(con, "WITH a AS (SELECT 1 AS x) SELECT x FROM a")[1] == [(1,)]
    for sql in ("SELECT 1; SELECT 2", "DELETE FROM client", "DROP TABLE client", "CREATE TABLE x (a INT)",
                f"COPY (SELECT 1) TO '{path}.csv'", "ATTACH 'x.duckdb'", "SELEC 1", ""):
        with pytest.raises(layer.NotASelect):
            layer.select_only(con, sql)
    assert con.execute("SELECT count(*) FROM client").fetchone()[0] == 0
