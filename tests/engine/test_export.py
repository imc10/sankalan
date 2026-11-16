"""Exports (Phase 4): EXP-02 to EXP-07, C6-06, ANA-9 / A1-12, byte-level checks. Expected figures are the Test
Cases sheet's."""
import csv
import io
import threading

import pytest

from conftest import load_files, open_storage, run_job, spec, tpl_a_columns, tpl_a_rules, tpl_a_settings
from sankalan import analysis, exporting
from sankalan.jobs.job import JobState
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, Group, Measure
from sankalan.model.export import (DEFAULT_PATTERN, ExportOptions, csv_file_name, fill_pattern, safe_file_name)
from sankalan.query import export as qx
from sankalan.query import layer
from sankalan.query.split import LEFT_OUT, split
from sankalan.validation import scan

COLS = tpl_a_columns()
NAMES = {c.id: c.name for c in COLS}
TEMPLATE_HEADERS = [c.name for c in COLS]


@pytest.fixture(scope="module")
def env(tmp_path_factory, fixtures_dir):
    s = open_storage(tmp_path_factory.mktemp("exp"))
    runs = {}
    for key, name in (("R-0001", "Sales_Oct.xlsx"), ("R-0002", "Sales_Nov.xlsx"), ("R-0003", "Sales_Errors.xlsx"),
                      ("F12", "Sales_ManyIssues.csv")):
        st, res, rows = load_files(s, fixtures_dir, [name], tpl_a_settings(), COLS)
        runs[key] = (st, {0: rows[0].file_name})
    st, names = runs["R-0003"]
    r = run_job(s.runner, lambda ctx: scan.validate(ctx, st, COLS, tpl_a_rules(), names))
    runs["R-0003-rules"] = r.rules
    split(s.con, st.path, r.issues, [x.id for x in r.rules])
    st, names = runs["F12"]
    run_job(s.runner, lambda ctx: scan.validate(ctx, st, COLS, tpl_a_rules(), names))
    yield s, runs
    s.close()


def do_export(s, query, dest, options=ExportOptions(), overwrite=False):
    return run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, query, dest, options,
                                                          overwrite=overwrite))


def read_csv(path, delimiter=","):
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    return raw, list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))


def data_query(env, key, label):
    s, runs = env
    st, names = runs[key]
    return qx.run_data(s.con, st.path / "data.parquet", COLS, names, label)


@spec("EXP-02", "EXP-3", "EXP-6", "RUN-11", "UI-7")
def test_exp02_run_data_columns_and_formats(env, tmp_path):
    s, _ = env
    dest = tmp_path / "Acme Traders_Sales Register_R-0002_Data.csv"
    out = do_export(s, data_query(env, "R-0002", "R-0002"), dest)
    assert out.rows == 4000 and out.path == dest
    raw, rows = read_csv(dest)
    assert raw[:3] == b"\xef\xbb\xbf"
    assert rows[0] == TEMPLATE_HEADERS + ["Source File", "Source Sheet", "Source Row", "Run ID"]
    assert len(rows) == 4001
    first = dict(zip(rows[0], rows[1]))
    assert (first["Source File"], first["Source Sheet"], first["Source Row"], first["Run ID"]) == (
        "Sales_Nov.xlsx", "Sales", "3", "R-0002")                                  # header row 2
    assert first["Invoice Date"][2] == "-" and len(first["Invoice Date"]) == 10    # DD-MM-YYYY
    assert all("," not in r[5] and r[5].count(".") == 1 and len(r[5].split(".")[1]) == 2 for r in rows[1:])
    assert all(r[6].isdigit() for r in rows[1:])                                   # GST Rate: 0 decimals
    assert "1000.00" in {r[5] for r in rows[1:]}
    assert not list(tmp_path.glob("*.part")) and not list(s.paths.temp.glob("*"))


@spec("EXP-02", "MAP-11")
def test_run_data_with_added_and_removed_columns(env, tmp_path):
    s, runs = env
    st, names = runs["R-0001"]
    cols = [c for c in tpl_a_columns()]
    cols[3].removed = True                                                         # GSTIN removed (C4-16)
    from sankalan.model.template import Column
    cols.append(Column("c009", "Branch"))                                          # added after the run
    q = qx.run_data(s.con, st.path / "data.parquet", cols, names, "R-0001")
    _raw, rows = read_csv(do_export(s, q, tmp_path / "d.csv").path)
    assert "GSTIN" not in rows[0] and rows[0][7] == "Branch" and {r[7] for r in rows[1:]} == {""}


@spec("EXP-03", "EXP-3")
def test_exp03_bom_and_delimiters(env, tmp_path):
    s, _ = env
    q = data_query(env, "R-0001", "R-0001")
    raw, _ = read_csv(do_export(s, q, tmp_path / "bom.csv").path)
    assert raw[:3] == b"\xef\xbb\xbf" and raw[3:13] == b"Invoice No"
    raw, _ = read_csv(do_export(s, q, tmp_path / "plain.csv", ExportOptions(bom=False)).path)
    assert raw[:10] == b"Invoice No"
    for delim, name in ((";", "semi"), ("\t", "tab"), ("|", "pipe")):
        raw, rows = read_csv(do_export(s, q, tmp_path / f"{name}.csv", ExportOptions(delim)).path, delim)
        assert len(rows) == 5001 and all(len(r) == 12 for r in rows)
        assert raw.splitlines()[0].decode("utf-8-sig").split(delim)[:2] == ["Invoice No", "Invoice Date"]


@spec("EXP-04", "T19", "EXP-1")
def test_exp04_left_out_rows(env, tmp_path):
    s, runs = env
    st, names = runs["R-0003"]
    q = qx.left_out(s.con, st.path / LEFT_OUT, COLS, names, "R-0003", runs["R-0003-rules"])
    out = do_export(s, q, tmp_path / "left.csv")
    _raw, rows = read_csv(out.path)
    assert out.rows == 63 and len(rows) == 64
    assert rows[0] == TEMPLATE_HEADERS + ["Source File", "Source Sheet", "Source Row", "Run ID", "Reason"]
    by_row = {int(r[10]): r for r in rows[1:]}
    assert by_row[214][12] == "Taxable Value: Is a number" and by_row[214][5] == ""
    assert by_row[705][12] == "Invoice No: Unique within the run"
    assert 704 not in by_row                                       # the first occurrence is kept (T18)
    assert by_row[102][12] == "Invoice No: Not blank"
    assert all(r[11] == "R-0003" for r in rows[1:])


@spec("EXP-05", "ISS-3", "UI-6")
def test_exp05_issue_list(env, tmp_path):
    s, runs = env
    st, names = runs["R-0003"]
    out = do_export(s, qx.issue_list(st.path / "issues.parquet", names, NAMES), tmp_path / "issues.csv")
    _raw, rows = read_csv(out.path)
    assert rows[0] == ["File", "Sheet", "Row", "Column", "Value", "Rule", "Severity", "Message"]
    assert out.rows == 98 and len(rows) == 99
    r214 = [r for r in rows[1:] if r[2] == "214"]
    assert r214 == [["Sales_Errors.xlsx", "Sales", "214", "Taxable Value", "abc", "Is a number", "Error",
                     "Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number"]]
    # a CSV file has no sheet; rows over 999 use grouping in the message only
    st, names = runs["F12"]
    out = do_export(s, qx.issue_list(st.path / "issues.parquet", names, NAMES), tmp_path / "f12.csv")
    _raw, rows = read_csv(out.path)
    assert out.rows == 15000
    last = [r for r in rows if r[2] == "10001"][0]
    assert last[1] == "" and last[7] == "Sales_ManyIssues.csv, row 10,001, Customer: value is blank"


@spec("EXP-06", "EXP-4")
def test_exp06_overwrite_needs_confirmation(env, tmp_path):
    s, _ = env
    dest = tmp_path / "x.csv"
    dest.write_bytes(b"old")
    with pytest.raises(exporting.ExportExists):
        do_export(s, data_query(env, "R-0001", "R-0001"), dest)
    assert dest.read_bytes() == b"old"
    do_export(s, data_query(env, "R-0001", "R-0001"), dest, overwrite=True)
    assert dest.read_bytes()[:3] == b"\xef\xbb\xbf"


@spec("EXP-07", "EXP-4")
def test_exp07_file_names():
    assert safe_file_name('GST: Q3/Q4') == "GST_ Q3_Q4"
    assert safe_file_name('a\\b*c?d"e<f>g|h') == "a_b_c_d_e_f_g_h"
    assert safe_file_name("CON") == "_CON" and safe_file_name("Report. ") == "Report__"
    assert csv_file_name(DEFAULT_PATTERN, Client="Acme Traders", Template="GST: Q3/Q4", RunID="R-0001",
                         Output="State-wise sales") == "Acme Traders_GST_ Q3_Q4_R-0001_State-wise sales.csv"
    assert fill_pattern(DEFAULT_PATTERN, Client="Acme", Template="Sales", Output="State sales") == \
        "Acme_Sales_State sales"                       # an analysis has no Run ID
    assert fill_pattern("{Client}-{Unknown}", Client="A") == "A-{Unknown}"
    with pytest.raises(ValueError):
        ExportOptions(":")


@spec("EXP-7", "EXP-08", "UI-5")
def test_cancel_deletes_part_files(env, tmp_path, monkeypatch):
    s, _ = env
    q = data_query(env, "R-0001", "R-0001")
    dest = tmp_path / "c.csv"
    monkeypatch.setattr(exporting, "CHUNK", 4096)
    started = threading.Event()
    release = threading.Event()

    def after_chunk():
        started.set()
        release.wait(5)
    monkeypatch.setattr(exporting, "_after_chunk", after_chunk)
    job = s.runner.start("export", lambda ctx: exporting.export(ctx, s.paths.temp, q, dest, ExportOptions()))
    assert started.wait(10)
    assert (tmp_path / "c.csv.part").exists()          # mid-stream
    job.cancel()
    release.set()
    job.wait(10)
    assert job.state == JobState.CANCELLED
    assert list(tmp_path.iterdir()) == [] and list(s.paths.temp.iterdir()) == []


@spec("EXP-7")
def test_cancel_during_the_query(env, tmp_path):
    s, _ = env
    q = data_query(env, "R-0001", "R-0001")

    def work(ctx):
        ctx._job.cancel()                                # cancel pending as the COPY starts
        return exporting.export(ctx, s.paths.temp, q, tmp_path / "q.csv", ExportOptions())
    job = s.runner.run("export", work)
    job.wait(10)
    assert job.state == JobState.CANCELLED and list(tmp_path.iterdir()) == []


@spec("ANA-9", "A1-12", "A1-05", "DO-7")
def test_analysis_result_export(env, tmp_path):
    s, runs = env
    src = [runs["R-0001"][0].path / "data.parquet"]
    defn = Definition("t", [], [Group("c005"), Group("c007")], [Measure("c006", d.SUM, "Taxable"),
                                                                 Measure("c006", d.AVG)], True)
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, defn, COLS, src))
    _raw, rows = read_csv(do_export(s, qx.result(res, subtotals=True), tmp_path / "a.csv").path)
    assert rows[0] == ["State", "GST Rate", "Taxable", "Average of Taxable Value"]
    assert len(rows) == 1 + 20 + 4 + 1
    assert rows[1:7] == [["Delhi", "0", rows[1][2], rows[1][3]]] + rows[2:7] and rows[6][:2] == ["Delhi", "Total"]
    assert rows[-1][:3] == ["Grand total", "", "7536875.00"]
    mh = [r for r in rows if r[0] == "Maharashtra"]
    assert [(r[1], r[2]) for r in mh] == [("0", "352500.00"), ("5", "393500.00"), ("12", "383250.00"),
                                          ("18", "373000.00"), ("28", "362750.00"), ("Total", "1865000.00")]
    _raw, rows = read_csv(do_export(s, qx.result(res, subtotals=False, sort="m1", descending=True),
                                    tmp_path / "b.csv").path)
    sums = [float(r[2]) for r in rows[1:-1]]
    assert len(rows) == 1 + 20 + 1 and sums == sorted(sums, reverse=True) and rows[-1][0] == "Grand total"
    assert rows[1][:3] == ["Delhi", "28", "401187.50"]          # subtotals off: one list, sorted as a whole
    # the export is never capped at the screen's 100,000 rows: every row of a large result is written
    days = Definition("t", [], [Group("c002", "day")], [Measure(None, d.COUNT)])
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, days, COLS, src))
    _raw, rows = read_csv(do_export(s, qx.result(res, subtotals=False), tmp_path / "c.csv").path)
    assert len(rows) == 1 + 31 + 1 and rows[1] == ["01-10-2026", "162"] and rows[-1] == ["Grand total", "5000"]


@spec("C6-06", "DO-7", "EXP-1", "RUNO-05")
def test_c606_export_all_outputs(env, tmp_path):
    s, runs = env
    st, _names = runs["R-0001"]
    outs = [("State-wise sales", Definition("t", [], [Group("c005")], [Measure("c006", d.SUM, "Taxable")])),
            ("Latest month by GST rate", Definition("t", [Filter("c002", d.LATEST_MONTH)],
                                                    [Group("c002", "month"), Group("c007")],
                                                    [Measure("c006", d.SUM)], True))]
    run_job(s.runner, lambda ctx: analysis.write_outputs(ctx, outs, COLS, st.path / "data.parquet",
                                                          st.path / "outputs"))
    items = []
    for n, (name, defn) in enumerate(outs, 1):
        res = layer.open_output(defn, COLS, st.path / "outputs" / f"{n}.parquet", s.con)
        dest = tmp_path / csv_file_name(DEFAULT_PATTERN, Client="Acme Traders", Template="Sales Register",
                                        RunID="R-0001", Output=name)
        items.append((qx.result(res, subtotals=defn.subtotals), dest))
    got = run_job(s.runner, lambda ctx: exporting.export_many(ctx, s.paths.temp, items, ExportOptions()))
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "Acme Traders_Sales Register_R-0001_Latest month by GST rate.csv",
        "Acme Traders_Sales Register_R-0001_State-wise sales.csv"]
    _raw, rows = read_csv(got[1].path)
    assert rows[0] == ["Invoice Date", "GST Rate", "Sum of Taxable Value"]
    assert rows[1:] == [["Oct-2026", "0", "1486875.00"], ["Oct-2026", "5", "1497125.00"],
                        ["Oct-2026", "12", "1507375.00"], ["Oct-2026", "18", "1517625.00"],
                        ["Oct-2026", "28", "1527875.00"], ["Oct-2026", "Total", "7536875.00"],
                        ["Grand total", "", "7536875.00"]]
    # a second Export all to the same folder is refused before anything is written
    with pytest.raises(exporting.ExportExists):
        run_job(s.runner, lambda ctx: exporting.export_many(ctx, s.paths.temp, items, ExportOptions()))


@spec("EXP-3")
def test_header_quoting_and_null_group(env, tmp_path):
    s, runs = env
    st, _ = runs["R-0001"]
    cols = tpl_a_columns()
    cols[4].name = 'State, "region"'
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(
        ctx, Definition("t", [Filter("c003", d.BLANK)], [Group("c005")], [Measure(None, d.COUNT)]), cols,
        [st.path / "data.parquet"]))
    out = do_export(s, qx.result(res, subtotals=False), tmp_path / "h.csv", ExportOptions(bom=False))
    raw = out.path.read_bytes()
    assert raw.startswith(b'"State, ""region""",Count of rows\n')
    assert raw.endswith(b"Grand total,0\n")
    assert exporting.header_line(["a;b", "c"], ";") == b'"a;b";c\n'
