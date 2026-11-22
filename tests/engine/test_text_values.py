"""Feature E on TPL-R small: Number and Date columns keep text (Feature Spec A2 6, 10.6; Tech spec A2 5).

The oracle is the generator's manifest (figures computed in Python from the values it wrote) and independent DuckDB
queries on the companions; the code under test is the compiler / query layer, the validation scan and the commit.
"""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

import pytest

from conftest import run_job, spec
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, Group, FlatMeasure, cards
from sankalan.model.rule import (ALLOWED_VALUES, DATE_RANGE, NOT_BLANK, NUMBER_RANGE, UNIQUE, Rule)
from sankalan.query import catalogue as q
from sankalan.query import convert, layer
from sankalan.query.split import LEFT_OUT
from sankalan.query.textvalues import text_counts
from sankalan.validation import scan

INV, DATE_, STATE, TAXABLE = "c001", "c002", "c005", "c006"


@pytest.fixture(scope="module")
def r(tpl_r_runs):
    s, tid = tpl_r_runs["s"], tpl_r_runs["tid"]
    t = q.load_template(s.con, tid)
    data = {k: s.folder.run_dir(tid, rid) / convert.DATA for k, rid in tpl_r_runs["runs"].items()}
    return {**tpl_r_runs, "t": t, "cols": t.columns, "data": data}


def result(r, definition, *runs):
    """Run a definition over the given runs; (rows with subtotals off, grand total)."""
    s = r["s"]

    def work(ctx):
        res = layer.run_definition(ctx.cursor(), definition, r["cols"], [r["data"][k] for k in runs])
        try:
            return (layer.rows(ctx.cursor(), res, subtotals=False, cap=None, limit=10 ** 6),
                    layer.grand_total(ctx.cursor(), res))
        finally:
            layer.drop(ctx.cursor(), res)
    return run_job(s.runner, work)


def total(r, *measures, filters=(), runs=(1,)):
    _rows, t = result(r, Definition("", list(filters), [], cards(*measures)), *runs)
    return t


def independent(r, sql, k):
    return r["s"].con.execute(sql.format(f=f"read_parquet('{r['data'][k].as_posix()}')")).fetchone()[0]


# ---------------------------------------------------------------------------------------------- storage
@spec("AC-BUG-1c", "T41")
def test_tpl_r_commits_three_runs_with_companions(r):
    s = r["s"]
    runs = q.list_runs(s.con, r["tid"])
    assert [(x.label, x.rows_loaded) for x in runs] == [("R-0001", 2500), ("R-0002", 2437), ("R-0003", 2500)]
    assert sum(x.rows_loaded for x in runs) == r["m"].rows_searched == 7_437
    cols = [c[0] for c in s.con.execute(f"DESCRIBE SELECT * FROM read_parquet('{r['data'][2].as_posix()}')")
            .fetchall()]
    typed = [c.id for c in r["cols"] if c.type in ("Number", "Date")]
    assert all(f"{c}_t" in cols for c in typed) and not any(f"{c.id}_t" in cols for c in r["cols"]
                                                              if c.type == "Text")
    # companions and values never both filled
    for k in (1, 2, 3):
        both = " OR ".join(f"({c} IS NOT NULL AND {c}_t IS NOT NULL)" for c in typed)
        assert independent(r, f"SELECT count(*) FROM {{f}} WHERE {both}", k) == 0


@spec("AC-TXT-1", "TXT-1", "T56")
def test_text_kept_as_typed_and_counted(r):
    s = r["s"]
    got = independent(r, "SELECT list(c006_t ORDER BY c006_t) FROM {f} WHERE c006_t IS NOT NULL", 1)
    assert sorted(got) == sorted(["NA"] * 10 + ["Nil"] * 5 + ["12,000/-"])
    got = independent(r, "SELECT list(c002_t ORDER BY c002_t) FROM {f} WHERE c002_t IS NOT NULL", 2)
    assert sorted(got) == sorted(["NA"] * 3 + ["31-02-2026"] * 2)
    # text_counts = an independent count(c_t), and stored on the run at commit (T56)
    for k, rid in r["runs"].items():
        counts = run_job(s.runner, lambda ctx: text_counts(ctx.cursor(), r["data"][k], r["cols"]))
        for c in counts:
            assert counts[c] == independent(r, f"SELECT count({c}_t) FROM {{f}}", k)
        assert q.run_details(s.con, rid)["text_counts"] == counts
    assert q.run_details(s.con, r["runs"][1])["text_counts"][TAXABLE] == 16
    assert q.run_details(s.con, r["runs"][2])["text_counts"][DATE_] == 5
    assert all(v == 0 for c, v in q.run_details(s.con, r["runs"][3])["text_counts"].items())
    assert q.run_details(s.con, r["runs"][1])["checks"] is True


@spec("T41", "TXT-13")
def test_left_out_rows_keep_their_companions(r):
    s = r["s"]
    left = s.folder.run_dir(r["tid"], r["runs"][2]) / LEFT_OUT
    cols = [c[0] for c in s.con.execute(f"DESCRIBE SELECT * FROM read_parquet('{left.as_posix()}')").fetchall()]
    assert "c006_t" in cols and "c002_t" in cols and "_reason" in cols
    assert convert.parquet_rows(s.con, left) == 63
    ordered = s.con.execute(f"SELECT list(_src_file * 1000000 + _src_row) FROM read_parquet('{left.as_posix()}')"
                            ).fetchone()[0]
    assert ordered == sorted(ordered)


@spec("TXT-14", "AC-TXT-8", "T20")
def test_totals_check_passes_with_text(r):
    m = r["m"].run(1)
    totals = q.run_details(r["s"].con, r["runs"][1])["totals"]
    assert totals[TAXABLE] == {"name": "Taxable Value", "decimals": 2, "input": m.taxable_sum,
                               "loaded": m.taxable_sum, "left_out": "0.00", "passed": True}
    assert totals["c013"]["passed"] and totals["c013"]["loaded"] == m.invoice_value_sum


# ---------------------------------------------------------------------------------------------- measures
@spec("AC-TXT-2", "TXT-9", "T13")
def test_sum_avg_min_max_use_numbers_only(r):
    m = r["m"].run(1)
    got = total(r, FlatMeasure(TAXABLE, d.SUM), FlatMeasure(TAXABLE, d.AVG), FlatMeasure(TAXABLE, d.MIN), FlatMeasure(TAXABLE, d.MAX))
    avg = (Decimal(m.taxable_sum) / m.taxable_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert got == (Decimal(m.taxable_sum), avg, Decimal(m.taxable_min), Decimal(m.taxable_max))
    m2 = r["m"].run(2)
    got = total(r, FlatMeasure(DATE_, d.MIN), FlatMeasure(DATE_, d.MAX), runs=(2,))
    assert got == (dt.date.fromisoformat(m2.date_min), dt.date.fromisoformat(m2.date_max))


@spec("AC-TXT-3", "TXT-8", "TXT-9", "D70")
def test_count_counts_text_distinct_does_not(r):
    m1, m2 = r["m"].run(1), r["m"].run(2)
    assert total(r, FlatMeasure(TAXABLE, d.COUNT)) == (m1.taxable_count + 16,)
    assert total(r, FlatMeasure(DATE_, d.COUNT), FlatMeasure(DATE_, d.COUNT_DISTINCT), runs=(2,)) == \
        (m2.date_count + 5, m2.date_distinct)
    assert total(r, FlatMeasure(d.ROWS, d.COUNT)) == (2500,)


# ---------------------------------------------------------------------------------------------- filters
@spec("AC-TXT-4", "TXT-5", "TXT-6", "TXT-7", "TXT-8", "T55")
def test_filters(r):
    m1, m2 = r["m"].run(1), r["m"].run(2)
    rows = FlatMeasure(d.ROWS, d.COUNT)
    assert total(r, rows, filters=[Filter(TAXABLE, d.NOT_NUMBER)]) == (16,)
    assert total(r, rows, filters=[Filter(DATE_, d.NOT_DATE)], runs=(2,)) == (5,)
    assert total(r, rows, filters=[Filter(TAXABLE, d.BLANK)]) == (m1.taxable_blank,)
    assert total(r, rows, filters=[Filter(TAXABLE, d.NOT_BLANK)]) == (2500 - m1.taxable_blank,)
    assert total(r, rows, filters=[Filter(DATE_, d.BLANK)], runs=(2,)) == (m2.date_blank,)
    # value filters never return a text row
    for f in (Filter(TAXABLE, d.EQUALS, ["1000"]), Filter(TAXABLE, d.BETWEEN, ["0", "99999999"]),
              Filter(TAXABLE, d.BETWEEN, [None, "1500"])):
        assert total(r, rows, filters=[f, Filter(TAXABLE, d.NOT_NUMBER)]) == (0,)
    assert total(r, rows, filters=[Filter(TAXABLE, d.BETWEEN, ["0", "99999999"])]) == (m1.taxable_count,)
    for f in (Filter(DATE_, d.MONTH, [2026, 11]), Filter(DATE_, d.YEAR, [2026]),
              Filter(DATE_, d.BETWEEN, ["2000-01-01", "2100-01-01"])):
        assert total(r, rows, filters=[f, Filter(DATE_, d.NOT_DATE)], runs=(2,)) == (0,)
        assert total(r, rows, filters=[f], runs=(2,)) == (m2.date_count,)
    assert independent(r, "SELECT count(*) FROM {f} WHERE c006_t IS NOT NULL", 1) == 16


def test_filter_ops_offered_for_typed_columns_only():
    assert d.NOT_NUMBER in d.FILTER_OPS["Number"] and d.NOT_DATE in d.FILTER_OPS["Date"]
    assert d.NOT_DATE in d.OUTPUT_DATE_OPS
    assert d.NOT_NUMBER not in d.FILTER_OPS["Text"] and d.NOT_DATE not in d.FILTER_OPS["Text"]
    assert d.FILTER_HELP[d.NOT_NUMBER] == "Cells with text such as NA or Nil instead of a number"
    assert d.FILTER_HELP[d.NOT_DATE] == "Cells with text such as NA instead of a date"


# ---------------------------------------------------------------------------------------------- groups and sorting
def _groups(rows):
    return {row[1]: row[2] for row in rows}


@spec("AC-TXT-5", "TXT-10", "T42")
def test_text_group_separate_from_null(r):
    m1, m2 = r["m"].run(1), r["m"].run(2)
    rows, tot = result(r, Definition("", [], [Group(TAXABLE)], cards(FlatMeasure(d.ROWS, d.COUNT))), 1)
    g = _groups(rows)
    assert g[d.TEXT_GROUP] == 16 and g[None] == m1.taxable_blank
    assert sum(g.values()) == tot[0] == 2500
    for grain in ("month", "year", "day"):
        rows, tot = result(r, Definition("", [], [Group(DATE_, grain)], cards(FlatMeasure(d.ROWS, d.COUNT))), 2)
        g = _groups(rows)
        assert g[d.TEXT_GROUP] == 5 and g[None] == m2.date_blank and sum(g.values()) == 2437
    # two levels: the text group of the first level keeps its own subtotal
    defn = Definition("", [], [Group(TAXABLE), Group(STATE)], cards(FlatMeasure(d.ROWS, d.COUNT)), subtotals=True)

    def work(ctx):
        res = layer.run_definition(ctx.cursor(), defn, r["cols"], [r["data"][1]])
        try:
            return layer.rows(ctx.cursor(), res, subtotals=True, cap=None, limit=10 ** 6)
        finally:
            layer.drop(ctx.cursor(), res)
    rows = run_job(r["s"].runner, work)
    subs = {row[1]: row[3] for row in rows if row[0] == 1}
    assert subs[d.TEXT_GROUP] == 16 and subs[None] == m1.taxable_blank


@spec("AC-TXT-6", "TXT-11", "P8")
@pytest.mark.parametrize("subtotals", [False, True])
@pytest.mark.parametrize("descending", [False, True])
def test_sort_values_then_text_then_null(r, descending, subtotals):
    for col, grain, k in ((TAXABLE, None, 1), (DATE_, "month", 2), (DATE_, None, 2)):
        defn = Definition("", [], [Group(col, grain), Group(STATE)], cards(FlatMeasure(d.ROWS, d.COUNT)), subtotals=subtotals)

        def work(ctx):
            res = layer.run_definition(ctx.cursor(), defn, r["cols"], [r["data"][k]])
            try:
                return layer.rows(ctx.cursor(), res, subtotals=subtotals, sort="g1", descending=descending,
                                  cap=None, limit=10 ** 6)
            finally:
                layer.drop(ctx.cursor(), res)
        rows = run_job(r["s"].runner, work)
        firsts = []
        for row in rows:                    # the first level's values in order, repeats collapsed
            if row[0] >= 1 and (not firsts or row[1] is not firsts[-1] and row[1] != firsts[-1]):
                firsts.append(row[1])
        values = [v for v in firsts if v is not None and v is not d.TEXT_GROUP]
        tail = firsts[len(values):]
        assert values == sorted(values, reverse=descending)
        assert tail == [d.TEXT_GROUP, None], tail[:3]


@spec("TXT-10", "UI-7")
def test_result_cell_labels():
    from sankalan import formats
    assert formats.result_cell(d.TEXT_GROUP, ("Number", 2, None), True) == "(Not a number)"
    assert formats.result_cell(d.TEXT_GROUP, ("Date", None, "month"), True) == "(Not a date)"
    assert formats.result_cell(None, ("Number", 2, None), True) == "(Null)"


# ---------------------------------------------------------------------------------------------- default outputs
@spec("AC-TXT-9", "TXT-12", "DO-3")
def test_latest_month_uses_real_dates_and_leaves_text_out(r):
    s = r["s"]
    m2 = r["m"].run(2)
    o = q.run_outputs(s.con, r["runs"][2])[0]
    assert o.headers == ["State", "Rows · Count", "Taxable Value · Sum"]
    path = s.folder.run_dir(r["tid"], r["runs"][2]) / o.file

    def work(ctx):
        res = layer.open_output(Definition.from_dict(o.definition), r["cols"], path, ctx.cursor(), o.headers)
        return layer.grand_total(ctx.cursor(), res)
    tot = run_job(s.runner, work)
    assert tot[0] == m2.date_count                 # every row with a November date; text and blank rows left out
    # the latest real date is 30-11-2026: a filter on it, built independently, gives the same rows
    assert independent(r, "SELECT count(*) FROM {f} WHERE c002 >= DATE '2026-11-01' AND c002 < DATE '2026-12-01'",
                       2) == m2.date_count


# ---------------------------------------------------------------------------------------------- rules (TXT-13)
@spec("AC-TXT-7", "TXT-13", "VR-8")
def test_rules_on_committed_text(r):
    """Test rules on latest run (VR-8) finds type failures in committed text; range, allowed values and date range
    skip text like a blank; Not blank passes on text; two "NA" are duplicates in a Unique key."""
    s = r["s"]
    rules = [Rule("r1", TAXABLE, NUMBER_RANGE, {"min": "0", "max": "1500"}),
             Rule("r2", TAXABLE, ALLOWED_VALUES, {"values": ["1000"]}),
             Rule("r3", TAXABLE, NOT_BLANK),
             Rule("r4", TAXABLE, UNIQUE),
             Rule("r5", DATE_, DATE_RANGE, {"from": "2026-10-05"}),
             Rule("r6", DATE_, NOT_BLANK)]
    run_dir = s.folder.run_dir(r["tid"], r["runs"][1])
    counts = run_job(s.runner, lambda ctx: scan.test_rules_on_run(ctx, run_dir, r["cols"], rules))
    m1 = r["m"].run(1)
    assert counts["c006.type"] == 16 and counts["c002.type"] == 0
    assert counts["r3"] == m1.taxable_blank                       # text isn't blank
    assert counts["r1"] == independent(r, "SELECT count(*) FROM {f} WHERE c006 > 1500", 1)
    assert counts["r2"] == independent(r, "SELECT count(*) FROM {f} WHERE c006 <> 1000", 1)
    assert counts["r5"] == independent(r, "SELECT count(*) FROM {f} WHERE c002 < DATE '2026-10-05'", 1)
    assert counts["r6"] == m1.date_blank
    first = run_job(s.runner, lambda ctx: scan.dry_run(ctx, run_dir / convert.DATA, r["cols"], rules,
                                                       keep=100_000)[1])
    text_rows = set(independent(r, "SELECT list(_src_file * 1000000 + _src_row) FROM {f} WHERE c006_t IS NOT NULL",
                                1))

    def keyed(rid):
        return {x[0] * 1_000_000 + x[2] for x in first[rid]}
    assert keyed("c006.type") == text_rows                        # one issue per text cell, from the type rule
    assert not (keyed("r1") | keyed("r2")) & text_rows
    assert {x[7] for x in first["c006.type"]} == {"NA", "Nil", "12,000/-"}
    dup_values = {x[7] for x in first["r4"]}
    assert "NA" in dup_values and "Nil" in dup_values and "12,000/-" not in dup_values
    assert sum(1 for x in first["r4"] if x[7] == "NA") == 10


@spec("T32")
def test_data_parquet_in_stored_order(r):
    """Physically ascending in (_src_file, _src_row): the xlsx sheets then the CSV files, rows in order."""
    for k in (1, 2, 3):
        bad = independent(r, "SELECT count(*) FROM (SELECT _src_file, _src_row, lag(_src_file) OVER w AS pf, "
                             "lag(_src_row) OVER w AS pr FROM read_parquet('" + r["data"][k].as_posix() + "', "
                             "file_row_number = true) WINDOW w AS (ORDER BY file_row_number)) "
                             "WHERE pf IS NOT NULL AND (pf > _src_file OR (pf = _src_file AND pr >= _src_row))", k)
        assert bad == 0
    files = independent(r, "SELECT list(DISTINCT _src_sheet ORDER BY _src_sheet) FROM {f}", 3)
    assert files == ["", "Sales A", "Sales B"]                        # Source Sheet is blank for CSV rows


# ---------------------------------------------------------------------------------------------- Rows card (A2-4)
@spec("AC-MEA-10", "MEA-10")
def test_rows_count_against_column_count(r):
    m3 = r["m"].run(3)
    assert m3.no_invoice_no == 400
    assert total(r, FlatMeasure(d.ROWS, d.COUNT), FlatMeasure(INV, d.COUNT), runs=(3,)) == \
        (m3.rows_loaded, m3.rows_loaded - 400)
    rows, tot = result(r, Definition("", [], [Group(STATE)], cards(FlatMeasure(d.ROWS, d.COUNT))), 3)
    assert len(rows) > 1 and sum(x[2] for x in rows) == tot[0] == m3.rows_loaded
