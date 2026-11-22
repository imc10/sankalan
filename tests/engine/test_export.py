"""Exports (Phase 4, A2-3): EXP-02 to EXP-07, C6-06, ANA-9 / A1-12, byte-level checks; export in parts (Feature
Spec A2 EXP-8 to EXP-14, Tech spec A2 8.1–8.5). Expected figures are the Test Cases sheet's and Feature Spec A2 10.4's."""
import csv
import io
import re
import threading
from pathlib import Path

import pytest

from conftest import load_files, open_storage, run_job, spec, temp_leftovers, tpl_a_columns, tpl_a_rules, tpl_a_settings
from sankalan import analysis, exporting
from sankalan.jobs.job import JobState
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, Group, FlatMeasure, cards
from sankalan.model.export import (DEFAULT_PATTERN, ExportOptions, csv_file_name, fill_pattern, safe_file_name)
from sankalan.query import catalogue as q
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


def do_export(s, source, dest, options=ExportOptions(), replace=(), part_rows=exporting.PART_ROWS, **kw):
    """One source to ``dest`` (split into parts beside it when over ``part_rows``): its ExportResult."""
    return run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, [source], dest.parent, [dest.name],
                                                          options, replace=replace, part_rows=part_rows, **kw))[0]


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
    assert not list(tmp_path.glob("*.partial")) and temp_leftovers(s.paths.temp) == []


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
    assert by_row[214][12] == "Taxable Value: Is a number" and by_row[214][5] == "abc"   # text kept (TXT-4)
    assert by_row[705][12] == "Invoice No: Unique within the run"
    assert 704 not in by_row                                       # the first occurrence is kept (T18)
    assert by_row[102][12] == "Invoice No: Not blank"
    assert all(r[11] == "R-0003" for r in rows[1:])


@spec("EXP-05", "ISS-3", "UI-6")
def test_exp05_issue_list(env, tmp_path):
    s, runs = env
    st, names = runs["R-0003"]
    out = do_export(s, qx.issue_list(s.con, st.path / "issues.parquet", names, NAMES), tmp_path / "issues.csv")
    _raw, rows = read_csv(out.path)
    assert rows[0] == ["File", "Sheet", "Row", "Column", "Value", "Rule", "Severity", "Message"]
    assert out.rows == 98 and len(rows) == 99
    r214 = [r for r in rows[1:] if r[2] == "214"]
    assert r214 == [["Sales_Errors.xlsx", "Sales", "214", "Taxable Value", "abc", "Is a number", "Error",
                     "Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number"]]
    # a CSV file has no sheet; rows over 999 use grouping in the message only
    st, names = runs["F12"]
    out = do_export(s, qx.issue_list(s.con, st.path / "issues.parquet", names, NAMES), tmp_path / "f12.csv")
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
    do_export(s, data_query(env, "R-0001", "R-0001"), dest, replace={dest})
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


@spec("EXP-7", "EXP-08", "UI-5", "EXP-14")
def test_cancel_deletes_part_files(env, tmp_path, monkeypatch):
    s, _ = env
    q = data_query(env, "R-0001", "R-0001")
    dest = tmp_path / "c.csv"
    started = threading.Event()
    release = threading.Event()

    def after_block():
        started.set()
        release.wait(5)
    monkeypatch.setattr(exporting, "_after_block", after_block)
    job = s.runner.start("export", lambda ctx: exporting.export(ctx, s.paths.temp, [q], tmp_path, [dest.name],
                                                                ExportOptions()))
    assert started.wait(10)
    assert (tmp_path / "c.csv.partial").exists()       # mid-stream
    job.cancel()
    release.set()
    job.wait(10)
    assert job.state == JobState.CANCELLED
    assert list(tmp_path.iterdir()) == [] and temp_leftovers(s.paths.temp) == []


@spec("EXP-7", "AC-EXP-14a")
def test_cancel_during_the_query(env, tmp_path):
    s, _ = env
    q = data_query(env, "R-0001", "R-0001")

    def work(ctx):
        ctx._job.cancel()                                # cancel pending as the COPY starts
        return exporting.export(ctx, s.paths.temp, [q], tmp_path, ["q.csv"], ExportOptions())
    job = s.runner.run("export", work)
    job.wait(10)
    assert job.state == JobState.CANCELLED and list(tmp_path.iterdir()) == []


@spec("ANA-9", "A1-12", "A1-05", "DO-7", "AC-MEA-5")
def test_analysis_result_export(env, tmp_path):
    s, runs = env
    src = [runs["R-0001"][0].path / "data.parquet"]
    defn = Definition("t", [], [Group("c005"), Group("c007")], cards(FlatMeasure("c006", d.SUM, "Taxable"),
                                                                 FlatMeasure("c006", d.AVG)), True)
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, defn, COLS, src))
    _raw, rows = read_csv(do_export(s, qx.result(s.con, res, subtotals=True), tmp_path / "a.csv").path)
    assert rows[0] == ["State", "GST Rate", "Taxable", "Taxable Value · Average"]
    assert len(rows) == 1 + 20 + 4 + 1
    assert rows[1:7] == [["Delhi", "0", rows[1][2], rows[1][3]]] + rows[2:7] and rows[6][:2] == ["Delhi", "Total"]
    assert rows[-1][:3] == ["Grand total", "", "7536875.00"]
    assert all(re.fullmatch(r"\d+\.\d\d", r[3]) for r in rows[1:])          # Average at 2 decimals (AC-MEA-5)
    mh = [r for r in rows if r[0] == "Maharashtra"]
    assert [(r[1], r[2]) for r in mh] == [("0", "352500.00"), ("5", "393500.00"), ("12", "383250.00"),
                                          ("18", "373000.00"), ("28", "362750.00"), ("Total", "1865000.00")]
    _raw, rows = read_csv(do_export(s, qx.result(s.con, res, subtotals=False, sort="m1", descending=True),
                                    tmp_path / "b.csv").path)
    sums = [float(r[2]) for r in rows[1:-1]]
    assert len(rows) == 1 + 20 + 1 and sums == sorted(sums, reverse=True) and rows[-1][0] == "Grand total"
    assert rows[1][:3] == ["Delhi", "28", "401187.50"]          # subtotals off: one list, sorted as a whole
    # the export is never capped at the screen's 100,000 rows: every row of a large result is written
    days = Definition("t", [], [Group("c002", "day")], cards(FlatMeasure(d.ROWS, d.COUNT)))
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, days, COLS, src))
    _raw, rows = read_csv(do_export(s, qx.result(s.con, res, subtotals=False), tmp_path / "c.csv").path)
    assert len(rows) == 1 + 31 + 1 and rows[1] == ["01-10-2026", "162"] and rows[-1] == ["Grand total", "5000"]


@spec("C6-06", "DO-7", "EXP-1", "RUNO-05")
def test_c606_export_all_outputs(env, tmp_path):
    s, runs = env
    st, _names = runs["R-0001"]
    outs = [("State-wise sales", Definition("t", [], [Group("c005")], cards(FlatMeasure("c006", d.SUM, "Taxable")))),
            ("Latest month by GST rate", Definition("t", [Filter("c002", d.LATEST_MONTH)],
                                                    [Group("c002", "month"), Group("c007")],
                                                    cards(FlatMeasure("c006", d.SUM)), True))]
    run_job(s.runner, lambda ctx: analysis.write_outputs(ctx, outs, COLS, st.path / "data.parquet",
                                                          st.path / "outputs"))
    sources, names = [], []
    for n, (name, defn) in enumerate(outs, 1):
        res = layer.open_output(defn, COLS, st.path / "outputs" / f"{n}.parquet", s.con)
        names.append(csv_file_name(DEFAULT_PATTERN, Client="Acme Traders", Template="Sales Register",
                                   RunID="R-0001", Output=name))
        sources.append(qx.result(s.con, res, subtotals=defn.subtotals, label=name))

    def export_all(ctx):
        return exporting.export(ctx, s.paths.temp, sources, tmp_path, names, ExportOptions())
    got = run_job(s.runner, export_all)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "Acme Traders_Sales Register_R-0001_Latest month by GST rate.csv",
        "Acme Traders_Sales Register_R-0001_State-wise sales.csv"]
    _raw, rows = read_csv(got[1].path)
    assert rows[0] == ["Invoice Date", "GST Rate", "Taxable Value · Sum"]
    assert rows[1:] == [["Oct-2026", "0", "1486875.00"], ["Oct-2026", "5", "1497125.00"],
                        ["Oct-2026", "12", "1507375.00"], ["Oct-2026", "18", "1517625.00"],
                        ["Oct-2026", "28", "1527875.00"], ["Oct-2026", "Total", "7536875.00"],
                        ["Grand total", "", "7536875.00"]]
    # a second Export all to the same folder is refused before anything is written, naming both files
    with pytest.raises(exporting.ExportExists) as e:
        run_job(s.runner, export_all)
    assert sorted(p.name for p in e.value.paths) == sorted(names)


@spec("EXP-3")
def test_header_quoting_and_null_group(env, tmp_path):
    s, runs = env
    st, _ = runs["R-0001"]
    cols = tpl_a_columns()
    cols[4].name = 'State, "region"'
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(
        ctx, Definition("t", [Filter("c003", d.BLANK)], [Group("c005")], cards(FlatMeasure(d.ROWS, d.COUNT))), cols,
        [st.path / "data.parquet"]))
    out = do_export(s, qx.result(s.con, res, subtotals=False), tmp_path / "h.csv", ExportOptions(bom=False))
    raw = out.path.read_bytes()
    assert raw.startswith('"State, ""region""",Rows · Count\n'.encode())
    assert raw.endswith(b"Grand total,0\n")
    assert exporting.header_line(["a;b", "c"], ";") == b'"a;b";c\n'


# ---------------------------------------------------------------------------------------------- A2: text values, order
def _tpl_r_export(r, k, tmp_path):
    s, tid = r["s"], r["tid"]
    rid = r["runs"][k]
    cols = q.load_template(s.con, tid).columns
    names = {f["file_index"]: f["file_name"] for f in q.run_details(s.con, rid)["files"]}
    query = qx.run_data(s.con, s.folder.run_dir(tid, rid) / "data.parquet", cols, names, f"R-000{k}")
    out = do_export(s, query, tmp_path / f"r{k}.csv")
    return cols, read_csv(out.path)


@spec("AC-TXT-1", "TXT-4", "EXP-3", "T32")
def test_text_values_export_as_typed_in_stored_order(tpl_r_runs, tmp_path):
    cols, (raw, rows) = _tpl_r_export(tpl_r_runs, 1, tmp_path)
    head = rows[0]
    ti, ni, fi, ri = (head.index(h) for h in ("Taxable Value", "Narration", "Source File", "Source Row"))
    assert sorted(r[ti] for r in rows[1:] if r[ti] and not re.fullmatch(r"-?[0-9]+\.[0-9]{2}", r[ti])) == \
        sorted(["NA"] * 10 + ["Nil"] * 5 + ["12,000/-"])
    assert b'"12,000/-"' in raw                                         # quoted: it holds the delimiter
    narr = [r[ni] for r in rows[1:]]
    assert any('"urgent"' in v and "," in v for v in narr)              # quotes doubled by DuckDB, read back whole
    assert any("\r\n" in v for v in narr) and any("\n" in v and "\r" not in v for v in narr)
    # stored order: files in load order (xlsx sheets, then the CSV), rows ascending within each
    files = tpl_r_runs["m"].files["1"]
    keys = [(files.index(r[fi]) if r[fi] in files else -1, r[head.index("Source Sheet")], int(r[ri]))
            for r in rows[1:]]
    order = [(f, {"Sales A": 0, "Sales B": 1}.get(sh, 2), row) for f, sh, row in keys]
    assert order == sorted(order) and len(rows) == 2501
    _cols, (_raw2, rows2) = _tpl_r_export(tpl_r_runs, 2, tmp_path)
    di = rows2[0].index("Invoice Date")
    assert sorted(r[di] for r in rows2[1:] if r[di] in ("NA", "31-02-2026")) == ["31-02-2026"] * 2 + ["NA"] * 3
    assert all(len(r[di]) == 10 and r[di][2] == "-" for r in rows2[1:] if r[di] not in ("", "NA", "31-02-2026"))


@spec("TXT-10", "EXP-12")
def test_result_export_labels_text_group(tpl_r_runs, tmp_path):
    s, tid = tpl_r_runs["s"], tpl_r_runs["tid"]
    cols = q.load_template(s.con, tid).columns
    data = s.folder.run_dir(tid, tpl_r_runs["runs"][1]) / "data.parquet"
    defn = Definition("", [], [Group("c006")], cards(FlatMeasure(d.ROWS, d.COUNT)))
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, defn, cols, [data]))
    out = do_export(s, qx.result(s.con, res, subtotals=False, sort="g1", descending=True), tmp_path / "res.csv")
    _raw, rows = read_csv(out.path)
    assert rows[-3:] == [["(Not a number)", "16"], ["(Null)", str(tpl_r_runs["m"].run(1).taxable_blank)],
                         ["Grand total", "2500"]]
    assert rows[1][0] == "2014.75"                                      # values first, descending
    run_job(s.runner, lambda ctx: layer.drop(ctx.cursor(), res))


# ---------------------------------------------------------------------------------------------- A2-3: export in parts
SMALL_PARTS = 1000                  # the normal suite's part size (plan A2-3); the app's is 1,000,000 (T37)


def _request(r, kind, k=1, **kw):
    from sankalan.model import export as ex
    s, tid = r["s"], r["tid"]
    t = q.load_template(s.con, tid)
    return ex.prefill(kind, t.export, template_id=tid, client="Rao & Co", template=t.name,
                      run_id=r["runs"][k], run_label=f"R-000{k}", **kw)


def _items(r, req):
    from sankalan import runs
    return run_job(r["s"].runner, lambda ctx: runs.export_items(ctx, r["s"].folder, req))


def _export(s, sources, folder, names, options=ExportOptions(), **kw):
    return run_job(s.runner, lambda ctx: exporting.export(ctx, s.paths.temp, sources, folder, names, options, **kw))


def _parts(paths, options=ExportOptions()):
    """Each part as (raw bytes, parsed rows)."""
    return [read_csv(p, options.delimiter) for p in paths]


def check_split(s, source, name, folder, part_rows, options=ExportOptions()):
    """AC-EXP-9a / 9b: split with ``part_rows`` and as one file; same header and BOM on every part, at most
    ``part_rows`` records each, and the parts' data joined byte-identical to the one file's data."""
    one_dir, parts_dir = folder / "one", folder / "parts"
    one_dir.mkdir(parents=True)
    parts_dir.mkdir(parents=True)
    one = do_export(s, source, one_dir / name, options, part_rows=10 ** 9)
    split = do_export(s, source, parts_dir / name, options, part_rows=part_rows)
    m = exporting.part_count(source.rows, part_rows)
    assert split.paths == [parts_dir / n for n in exporting.plan(source.rows, name, part_rows)]
    assert len(split.paths) == m and one.rows == split.rows == source.rows
    lead = (b"\xef\xbb\xbf" if options.bom else b"") + exporting.header_line(source.headers, options.delimiter)
    one_raw = one.path.read_bytes()
    assert one_raw.startswith(lead)
    joined = b""
    counts = []
    for raw, rows in _parts(split.paths, options):
        assert raw.startswith(lead) and rows[0] == source.headers
        counts.append(len(rows) - 1)
        joined += raw[len(lead):]
    assert counts == [min(part_rows, source.rows - k * part_rows) for k in range(m)]
    assert joined == one_raw[len(lead):]
    assert sorted(p.name for p in parts_dir.iterdir()) == sorted(p.name for p in split.paths)   # no .partial
    assert temp_leftovers(s.paths.temp) == []
    return split


@spec("AC-EXP-8b", "AC-EXP-9a", "AC-EXP-9b", "EXP-8", "EXP-9", "T32")
def test_every_kind_splits(tpl_r_runs, tmp_path):
    r, s = tpl_r_runs, tpl_r_runs["s"]
    tname = q.load_template(s.con, r["tid"]).name
    # a run's data: 2,500 rows in parts of 1,000, in stored order (with text values, quotes and line breaks)
    (src, name), = _items(r, _request(r, "data", 1))
    assert src.rows == 2500 and len(src.chunks) == 1 and "ORDER BY _src_file, _src_row" in src.chunks[0].sql
    out = check_split(s, src, name, tmp_path / "data", SMALL_PARTS)
    assert [p.name for p in out.paths] == [f"Rao & Co_{tname}_R-0001_Data_part0{k}of03.csv" for k in (1, 2, 3)]
    check_split(s, src, name, tmp_path / "data_plain", 999, ExportOptions(";", bom=False))
    # left-out rows (63 on R-0002), the issue list, the default output: lowered part sizes so each splits
    (src, name), = _items(r, _request(r, "left_out", 2))
    assert src.rows == 63
    check_split(s, src, name, tmp_path / "left", 25)
    (src, name), = _items(r, _request(r, "issues", 1))
    assert src.rows == 16                                    # the 16 Taxable Value text values (Warning)
    check_split(s, src, name, tmp_path / "issues", 7)
    (src, name), = _items(r, _request(r, "output", 1, output="Latest month by State", position=1))
    assert src.rows >= 3
    check_split(s, src, name, tmp_path / "output", 2)
    # all outputs: one source per output, each split on its own (R-0001's and R-0002's, so two sources)
    items = _items(r, _request(r, "outputs", 1))
    assert [x.label for x, _n in items] == ["Latest month by State"]
    sources = [x for x, _n in items + _items(r, _request(r, "outputs", 2))]
    names = ["R-0001.csv", "R-0002.csv"]
    (tmp_path / "all").mkdir()
    res = _export(s, sources, tmp_path / "all", names, part_rows=2)
    assert [len(x.paths) for x in res] == [exporting.part_count(x.rows, 2) for x in sources]
    assert sorted(p.name for p in (tmp_path / "all").iterdir()) == sorted(
        n for x, name in zip(sources, names) for n in exporting.plan(x.rows, name, 2))


@spec("AC-EXP-12", "EXP-12", "T38", "AC-EXP-8b")
def test_result_with_subtotals_split_grand_total_last(tpl_r_runs, tmp_path):
    from sankalan import analyses
    s, tid = tpl_r_runs["s"], tpl_r_runs["tid"]
    cols = q.load_template(s.con, tid).columns
    data = s.folder.run_dir(tid, tpl_r_runs["runs"][1]) / "data.parquet"
    by = {c.name: c.id for c in cols}
    defn = Definition("", [], [Group(by["Customer"]), Group(by["Invoice No"])],
                      cards(FlatMeasure(by["Taxable Value"], d.SUM)), True)
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, defn, cols, [data]))
    outcome = analyses.Outcome(res, defn, 1, res.input_rows, layer.count_rows(s.con, res, True),
                               layer.grand_total(s.con, res), 0.0, True)
    (src, _n), = run_job(s.runner, analyses.export_items(outcome, None, False))
    assert src.rows == outcome.count + 1 and src.rows > 2 * SMALL_PARTS        # visible rows + grand total
    out = check_split(s, src, "Result.csv", tmp_path, SMALL_PARTS)
    parts = _parts(out.paths)
    flat = [row for _raw, rows in parts for row in rows[1:]]
    assert [row[0] for row in flat if row[0] == "Grand total"] == ["Grand total"]
    assert parts[-1][1][-1][0] == "Grand total" and flat[-1][0] == "Grand total"
    # rows and subtotals in on-screen order: the subtotal pattern matches the screen's rows
    screen = layer.rows(s.con, res, subtotals=True, limit=10 ** 6, cap=None)
    assert len(screen) == len(flat) - 1
    assert [row[1] == "Total" for row in flat[:-1]] == [row[0] < res.levels for row in screen]
    run_job(s.runner, lambda ctx: layer.drop(ctx.cursor(), res))


def _sha(p):
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def data_source(tpl_r_runs):
    (src, _name), = _items(tpl_r_runs, _request(tpl_r_runs, "data", 1))
    return tpl_r_runs["s"], src


def _old_targets(folder):
    """Two parts of an earlier 3-part export (to be replaced) and an older _part04of04 (never touched)."""
    old = {n: folder / n for n in ("D_part01of03.csv", "D_part02of03.csv", "D_part04of04.csv")}
    for n, p in old.items():
        p.write_bytes(f"old {n}".encode())
    return old, {n: _sha(p) for n, p in old.items()}


def _start_held(s, sources, folder, names, **kw):
    return s.runner.start("export", lambda ctx: exporting.export(ctx, s.paths.temp, sources, folder, names,
                                                                 ExportOptions(), **kw))


def _left_as_before(folder, s, shas):
    assert sorted(p.name for p in folder.iterdir()) == sorted(shas)          # no part, .partial or .replaced
    assert {p.name: _sha(p) for p in folder.iterdir()} == shas
    assert temp_leftovers(s.paths.temp) == []


@spec("AC-EXP-14a", "EXP-14", "T35", "AC-EXP-10")
def test_cancel_during_extract_split_and_before_finish_leaves_files_as_they_were(data_source, tmp_path,
                                                                                 monkeypatch):
    s, src = data_source
    old, shas = _old_targets(tmp_path)
    replace = {old["D_part01of03.csv"], old["D_part02of03.csv"]}
    # 1. during extract: cancel as the COPY of the chunk starts
    holder, ready = {}, threading.Event()
    real_copy = exporting.copy_csv

    def copy_and_cancel(*a, **k):
        ready.wait(5)
        holder["job"].cancel()
        return real_copy(*a, **k)
    monkeypatch.setattr(exporting, "copy_csv", copy_and_cancel)
    holder["job"] = _start_held(s, [src], tmp_path, ["D.csv"], replace=replace, part_rows=SMALL_PARTS)
    ready.set()
    holder["job"].wait(10)
    assert holder["job"].state == JobState.CANCELLED
    _left_as_before(tmp_path, s, shas)
    monkeypatch.setattr(exporting, "copy_csv", real_copy)
    # 2. during the split, in part 2 of 3 (small blocks so the split takes several)
    monkeypatch.setattr(exporting, "SPLIT_BLOCK", 4096)
    p2 = tmp_path / "D_part02of03.csv.partial"
    seen = []

    def in_part_two():
        if p2.exists():
            seen.append(True)
            holder["job"].cancel()
    monkeypatch.setattr(exporting, "_after_block", in_part_two)
    holder["job"] = _start_held(s, [src], tmp_path, ["D.csv"], replace=replace, part_rows=SMALL_PARTS)
    holder["job"].wait(10)
    assert holder["job"].state == JobState.CANCELLED and seen
    _left_as_before(tmp_path, s, shas)
    monkeypatch.setattr(exporting, "_after_block", lambda: None)
    # 3. just before the finish
    monkeypatch.setattr(exporting, "_before_finish", lambda: holder["job"].cancel())
    holder["job"] = _start_held(s, [src], tmp_path, ["D.csv"], replace=replace, part_rows=SMALL_PARTS)
    holder["job"].wait(10)
    assert holder["job"].state == JobState.CANCELLED
    _left_as_before(tmp_path, s, shas)
    monkeypatch.setattr(exporting, "_before_finish", lambda: None)
    # and done: the two old parts replaced, part 3 new, the older _part04of04 untouched
    out = _export(s, [src], tmp_path, ["D.csv"], replace=replace, part_rows=SMALL_PARTS)[0]
    assert [p.name for p in out.paths] == ["D_part01of03.csv", "D_part02of03.csv", "D_part03of03.csv"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["D_part01of03.csv", "D_part02of03.csv",
                                                          "D_part03of03.csv", "D_part04of04.csv"]
    assert _sha(old["D_part04of04.csv"]) == shas["D_part04of04.csv"]
    assert _sha(out.paths[0]) != shas["D_part01of03.csv"]


@spec("T35", "AC-EXP-14a", "EXP-14")
def test_failure_during_finish_restores_the_originals(data_source, tmp_path, monkeypatch):
    s, src = data_source
    old, shas = _old_targets(tmp_path)
    replace = {old["D_part01of03.csv"], old["D_part02of03.csv"]}
    calls = []
    real = exporting._rename

    def fail_fourth(a, b):
        calls.append((a, b))
        if len(calls) == 4:                 # both originals moved aside, part 1 placed, part 2 fails
            raise OSError("simulated")
        return real(a, b)
    monkeypatch.setattr(exporting, "_rename", fail_fourth)
    with pytest.raises(OSError):
        _export(s, [src], tmp_path, ["D.csv"], replace=replace, part_rows=SMALL_PARTS)
    assert [Path(b).name for _a, b in calls[:3]] == ["D_part01of03.csv.replaced", "D_part02of03.csv.replaced",
                                                     "D_part01of03.csv"]
    _left_as_before(tmp_path, s, shas)


@spec("AC-EXP-14b", "EXP-14", "8.2")
def test_count_mismatch_and_disk_full_fail_with_the_same_clean_up(data_source, tmp_path, monkeypatch):
    import errno
    s, src = data_source
    old, shas = _old_targets(tmp_path)
    replace = {old["D_part01of03.csv"], old["D_part02of03.csv"]}
    with pytest.raises(exporting.ExportCheckFailed) as e:
        _export(s, [src], tmp_path, ["D.csv"], replace=replace, part_rows=SMALL_PARTS, missing_rows=1)
    assert str(e.value) == "Export check failed: wrote 2,499 of 2,500 rows"
    _left_as_before(tmp_path, s, shas)

    class Full:
        """A part writer whose disk fills after 50,000 bytes."""
        def __init__(self, path):
            self.f = open(path, "wb")
            self.n = 0

        def write(self, b):
            self.n += len(b)
            if self.n > 50_000:
                raise OSError(errno.ENOSPC, "No space left on device")
            return self.f.write(b)

        def close(self):
            self.f.close()
    monkeypatch.setattr(exporting, "_open_write", Full)
    with pytest.raises(OSError) as e:
        _export(s, [src], tmp_path, ["D.csv"], replace=replace, part_rows=SMALL_PARTS)
    assert e.value.errno == errno.ENOSPC
    _left_as_before(tmp_path, s, shas)
    from sankalan.ui.dialogs.export_dialog import error_text
    assert error_text(e.value, tmp_path).startswith(f"The drive {tmp_path.drive.upper()} became full")


def _hold_like_excel(path):
    """Open ``path`` the way Excel does: other programs may read it, not write or delete it."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k32.CreateFileW(str(path), 0x80000000 | 0x40000000, 0x1, None, 3, 0x80, None)   # read+write, share read
    assert h and h != wintypes.HANDLE(-1).value
    return lambda: k32.CloseHandle(h)


@spec("T36", "EXP-10", "EXP-14")
def test_a_file_open_in_excel_is_refused(data_source, tmp_path):
    s, src = data_source
    target = tmp_path / "D.csv"
    target.write_bytes(b"old")
    release = _hold_like_excel(target)
    try:
        with pytest.raises(exporting.FileInUse) as e:
            _export(s, [src], tmp_path, ["D.csv"], replace={target})
    finally:
        release()
    assert str(e.value) == "D.csv is open in another program. Close it, then export again."
    assert [p.name for p in tmp_path.iterdir()] == ["D.csv"] and target.read_bytes() == b"old"


@spec("EXP-13", "T34", "AC-EXP-13")
def test_free_space_check(data_source, tmp_path, monkeypatch):
    import collections
    s, src = data_source
    GB = 1024 ** 3
    Usage = collections.namedtuple("Usage", "total used free")
    free = {}
    monkeypatch.setattr(exporting.shutil, "disk_usage", lambda p: Usage(0, 0, free[exporting._drive(p)]))
    est = exporting.Estimate((10,), (1,), ("",), 10 * GB, 3 * GB)
    drive = exporting._drive(tmp_path)
    # same drive: destination 10 + 1 GB and working space 3 + 1 GB add up to 15 GB
    free[drive] = 14 * GB
    assert exporting.space_problem(est, tmp_path, s.paths.temp) == (
        f"Not enough free space on {drive}. This export needs about 15.0 GB, including working space; 14.0 GB is "
        f"free. Free up space or choose a folder on another drive.")
    free[drive] = 15 * GB
    assert exporting.space_problem(est, tmp_path, s.paths.temp) is None
    # the export itself checks again before writing anything
    free[drive] = 1 * GB
    with pytest.raises(exporting.NotEnoughSpace):
        _export(s, [src], tmp_path, ["D.csv"])
    assert list(tmp_path.iterdir()) == []
    # two drives: each needs only its own part
    temp = Path(s.paths.temp)
    monkeypatch.setattr(exporting, "_drive", lambda p: "T:" if Path(p) == temp else "D:")
    free.update({"D:": 11 * GB, "T:": 4 * GB})
    assert exporting.space_problem(est, tmp_path, temp) is None
    free["T:"] = int(3.5 * GB)
    assert exporting.space_problem(est, tmp_path, temp) == (
        "Not enough free space on T: for working files. This export needs about 4.0 GB there; 3.5 GB is free. "
        "Free up space on T:.")
    free["D:"] = 2 * GB
    assert exporting.space_problem(est, tmp_path, temp) == (       # no working space on D: (decision 22-11-2026)
        "Not enough free space on D:. This export needs about 11.0 GB; 2.0 GB is free. Free up space or choose a "
        "folder on another drive.")


@spec("EXP-13", "T34", "8.4")
def test_estimate_is_close_to_the_written_size(data_source, tmp_path):
    s, src = data_source
    est = run_job(s.runner, lambda ctx: exporting.estimate(ctx, s.paths.temp, [src], ExportOptions(), SMALL_PARTS))
    out = do_export(s, src, tmp_path / "D.csv", part_rows=SMALL_PARTS)
    written = sum(p.stat().st_size for p in out.paths)
    assert (est.rows, est.parts, est.files, est.split) == ((2500,), (3,), 3, True)
    assert written * 0.95 <= est.bytes <= written * 1.25
    assert 0 < est.largest_chunk <= est.bytes and temp_leftovers(s.paths.temp) == []


@spec("AC-MEA-11", "MEA-11", "T39")
def test_result_without_measures_has_no_grand_total(env, tmp_path):
    s, runs = env
    src = [runs["R-0001"][0].path / "data.parquet"]
    defn = Definition("t", [], [Group("c005")], [], True)
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, defn, COLS, src))
    _raw, rows = read_csv(do_export(s, qx.result(s.con, res, subtotals=True), tmp_path / "g.csv").path)
    assert rows == [["State"], ["Delhi"], ["Gujarat"], ["Karnataka"], ["Maharashtra"]]
