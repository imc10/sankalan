"""Validation scan and issues on the fixture pack (Phase 3): RUNV-01 to RUNV-10, RUNV-13 count, C3-16, C4-12,
GEN-07. Expected figures are the Test Cases sheet's."""
import copy

import pytest

from conftest import (load_files, open_storage, run_job, spec, tpl_a_columns, tpl_a_rules, tpl_a_settings)
from sankalan.model.rule import ERROR, WARNING, Rule, rule_changes
from sankalan.query import catalogue as qc
from sankalan.query import convert
from sankalan.query import validate as qv
from sankalan.validation import issues as iss
from sankalan.validation import scan
from sankalan.validation.rules import describe

TPL_A_NAMES = {c.id: c.name for c in tpl_a_columns()}

# RUNV-03 / C3-16 by rule
F04_BY_RULE = {"r1": 12, "r2": 8, "r3": 6, "c002.type": 4, "r6": 10, "c006.type": 15, "r8": 5, "r9": 6,
               "r7": 25, "r5": 7, "r4": 0, "c007.type": 0, "c008.type": 0}


@pytest.fixture(scope="module")
def f04(tmp_path_factory, fixtures_dir):
    """F04 Sales_Errors.xlsx staged once for the module (the scans below only read it or rewrite issues)."""
    s = open_storage(tmp_path_factory.mktemp("f04"))
    st, res, rows = load_files(s, fixtures_dir, ["Sales_Errors.xlsx"], tpl_a_settings(), tpl_a_columns())
    yield s, st, res, {0: rows[0].file_name}
    s.close()


def _validate(storage, st, rules, names, columns=None):
    return run_job(storage.runner, lambda ctx: scan.validate(ctx, st, columns or tpl_a_columns(), rules, names))


@spec("RUNV-03", "ISS-1", "VR-3", "VR-7", "T16")
def test_runv03_errors_and_warnings_by_rule(f04):
    s, st, res, names = f04
    r = _validate(s, st, tpl_a_rules(), names)
    assert (r.errors, r.warnings, res.rows_read, res.hidden_rows) == (66, 32, 2000, 0)
    assert r.by_rule == F04_BY_RULE
    assert not r.passed                                            # Next disabled
    sev = {x.id: x.severity for x in r.rules}
    assert sum(n for k, n in r.by_rule.items() if sev[k] == WARNING) == 32
    # ISS-1: one file and sheet, so per-file counts equal the per-rule counts
    assert {(c.rule, c.file_index, c.sheet): (c.errors, c.warnings) for c in r.counts} == {
        (k, 0, "Sales"): ((n, 0) if sev[k] == ERROR else (0, n)) for k, n in F04_BY_RULE.items() if n}
    assert r.issues.name == "issues.parquet" and not (st.path / "issues.parquet.part").exists()


@spec("RUNV-04", "GEN-07", "ISS-2", "UI-6", "T17")
def test_runv04_issue_grid_order_filter_sort_and_gen07_message(f04):
    s, st, _res, names = f04
    r = _validate(s, st, tpl_a_rules(), names)
    con = s.con
    rows = qv.grid_page(con, r.issues, limit=100_000)
    assert len(rows) == 98
    assert [(x[0], x[2]) for x in rows] == sorted((x[0], x[2]) for x in rows)       # file, sheet, row order
    i214 = [iss.from_row(x, names, TPL_A_NAMES) for x in rows if x[2] == 214]
    assert [(i.column, i.value, i.rule, i.severity) for i in i214] == [("Taxable Value", "abc", "Is a number",
                                                                         "Error")]
    assert i214[0].message == "Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number"
    dup = {x[2]: iss.from_row(x, names, TPL_A_NAMES) for x in rows if x[4] == "r3"}
    assert dup[705].message.endswith("Invoice No: same Invoice No as row 704")
    assert dup[704].message.endswith("Invoice No: same Invoice No in 2 rows; this is the first")
    assert qv.grid_count(con, r.issues, severity=WARNING) == 32
    warn = qv.grid_page(con, r.issues, severity=WARNING, sort="column")
    assert len(warn) == 32 and [x[3] for x in warn] == ["c003"] * 7 + ["c005"] * 25
    desc = qv.grid_page(con, r.issues, severity=WARNING, sort="column", descending=True)
    assert [x[3] for x in desc] == ["c005"] * 25 + ["c003"] * 7


@spec("RUNV-05", "VAL-9", "T17")
def test_runv05_unique_flags_every_row_of_a_group(f04):
    s, st, _res, names = f04
    r = _validate(s, st, tpl_a_rules(), names)
    rows = qv.grid_page(s.con, r.issues, rule_id="r3")
    assert [x[2] for x in rows] == [702, 703, 704, 705, 706, 707]
    assert [x[9] for x in rows] == [True, False] * 3                     # first occurrences kept on override


@spec("RUNV-13", "T18", "RUN-4")
def test_runv13_rows_left_out_on_override(f04):
    s, st, _res, names = f04
    assert _validate(s, st, tpl_a_rules(), names).left_out == 63          # "63 rows with errors will be left out"


@spec("RUNV-07", "ISS-3", "ISS-4")
def test_runv07_full_issue_list_kept(f04):
    s, st, _res, names = f04
    r = _validate(s, st, tpl_a_rules(), names)
    every = qv.read_issues(s.con, r.issues)
    assert len(every) == 98 and tuple(qv.ISSUE_COLUMNS) == (
        "_src_file", "_src_sheet", "_src_row", "column_id", "rule_id", "rule_type", "severity", "value", "problem",
        "duplicate_first")
    by = {(x[2], x[4]): x for x in every}
    assert by[(502, "c002.type")][7] == "31-02-2026"                      # value as typed when conversion failed
    assert by[(302, "r8")][7].startswith("-")                             # a stored number as plain decimal text
    assert by[(102, "r1")][7] == ""                                       # blank
    assert by[(402, "r6")][8] == "value has 14 characters; expected exactly 15"
    assert by[(802, "r7")][7] == "Goa"


@spec("RUNV-09", "VR-5", "TPL-8")
def test_runv09_run_only_rule_edit_reruns_only_the_scan(f04):
    s, st, res, names = f04
    tid = qc.insert_template(s.con, qc.insert_client(s.con, "Acme Traders"), "Sales Register")
    qc.save_rules(s.con, tid, tpl_a_rules())
    template_rules = qc.load_rules(s.con, tid)
    raw_before = (st.raw / "0.csv").stat().st_mtime_ns
    run_rules = copy.deepcopy(template_rules)
    gst = next(x for x in run_rules if x.id == "r9")
    gst.settings["values"].append("15")
    r = _validate(s, st, run_rules, names)
    assert (r.errors, r.by_rule["r9"]) == (60, 0)
    assert (st.raw / "0.csv").stat().st_mtime_ns == raw_before          # nothing re-read
    assert convert.parquet_rows(s.con, res.data) == 2000
    assert next(x for x in qc.load_rules(s.con, tid) if x.id == "r9").settings["values"] == ["0", "5", "12", "18",
                                                                                              "28"]
    changes = rule_changes(template_rules, run_rules)
    assert [(c["change"], c["rule_id"]) for c in changes] == [("changed", "r9")]
    assert describe(gst, tpl_a_columns()) == "Allowed values (GST Rate): 0, 5, 12, 18, 28, 15 · Error"


@spec("RUNV-10", "VR-5", "TPL-7", "TPL-8")
def test_runv10_save_rule_change_to_template(storage):
    con = storage.con
    tid = qc.insert_template(con, qc.insert_client(con, "Acme Traders"), "Sales Register")
    assert qc.save_rules(con, tid, tpl_a_rules()) == 2
    rules = qc.load_rules(con, tid)
    next(x for x in rules if x.id == "r5").severity = ERROR
    assert qc.save_rules(con, tid, rules) == 3
    assert qc.template_version(con, tid) == 3
    assert next(x for x in qc.load_rules(con, tid) if x.id == "r5").severity == ERROR
    snap = qc.template_snapshot(con, tid)
    assert next(x for x in snap["rules"] if x["id"] == "r5")["severity"] == ERROR
    assert next(x for x in qc.template_snapshot(con, tid, 2)["rules"] if x["id"] == "r5")["severity"] == WARNING
    assert [c["rule_id"] for c in rule_changes(tpl_a_rules(), rules)] == ["r5"]


@spec("C3-16", "VR-8", "T16", "T17")
def test_c316_dry_run_counts_and_show(f04):
    s, st, res, names = f04
    counts, first = run_job(s.runner, lambda ctx: scan.dry_run(ctx, res.data, tpl_a_columns(),
                                                                tpl_a_rules(), names))
    assert counts == F04_BY_RULE
    assert len(first["r7"]) == 20 and [x[2] for x in first["r7"]] == list(range(802, 822))
    assert [x[2] for x in first["c006.type"]] == list(range(214, 229))
    assert first["r4"] == []
    assert not (st.path / "dry.parquet").exists()


@spec("C4-12", "VR-8")
def test_c412_test_rules_on_latest_run(f04):
    """R-0003 holds the 1,937 rows kept on override (T18). Counts only; nothing is stored."""
    s, st, res, names = f04
    r = _validate(s, st, tpl_a_rules(), names)
    run_dir = s.folder.run_dir("tpl-a", "r-0003")
    run_dir.mkdir(parents=True)
    s.con.execute(f"""COPY (SELECT d.* FROM read_parquet('{res.data.as_posix()}') d ANTI JOIN (
                          SELECT _src_file, _src_row FROM read_parquet('{r.issues.as_posix()}')
                          WHERE severity = 'Error' AND NOT coalesce(duplicate_first, false)) x
                          USING (_src_file, _src_row) ORDER BY _src_file, _src_row)
                      TO '{(run_dir / 'data.parquet').as_posix()}' (FORMAT parquet)""")
    assert convert.parquet_rows(s.con, run_dir / "data.parquet") == 1937
    before = sorted(p.name for p in run_dir.iterdir())
    counts = run_job(s.runner, lambda ctx: scan.test_rules_on_run(ctx, run_dir, tpl_a_columns(), tpl_a_rules()))
    assert counts["r7"] == 25 and counts["r5"] == 7
    assert all(n == 0 for k, n in counts.items() if k not in ("r7", "r5"))
    assert sorted(p.name for p in run_dir.iterdir()) == before
    assert qv.totals(s.con, r.issues) == (66, 32)


@spec("RUNV-01", "R-0001")
def test_runv01_clean_run(storage, fixtures_dir):
    st, res, rows = load_files(storage, fixtures_dir, ["Sales_Oct.xlsx"], tpl_a_settings(), tpl_a_columns())
    r = _validate(storage, st, tpl_a_rules(), {0: rows[0].file_name})
    assert (r.errors, r.warnings, res.rows_read, res.hidden_rows, r.passed) == (0, 0, 5000, 0, True)
    assert r.counts == [] and r.left_out == 0


@spec("RUNV-02", "R-0002")
def test_runv02_hidden_and_blank_rows_raise_no_issues(storage, fixtures_dir):
    st, res, rows = load_files(storage, fixtures_dir, ["Sales_Nov.xlsx"], tpl_a_settings(), tpl_a_columns())
    r = _validate(storage, st, tpl_a_rules(), {0: rows[0].file_name})
    assert (r.errors, r.warnings, res.rows_loaded, res.blank_rows, res.hidden_rows) == (0, 0, 4000, 10, 25)
    assert res.rows_read + res.blank_rows == 4010                # Rows read (RUNV-02, confirmed 17-11-2026)


@spec("RUNV-08", "MAP-6", "T16", "R-0004")
def test_runv08_null_state_is_skipped(storage, fixtures_dir):
    cols = tpl_a_columns()
    cols[0].aliases = ["Inv No"]
    st, res, rows = load_files(storage, fixtures_dir, ["Sales_Renamed_Headers.xlsx"], tpl_a_settings(), cols)
    assert rows[0].headers[0] == "Inv No"
    r = _validate(storage, st, tpl_a_rules(), {0: rows[0].file_name}, cols)
    assert (res.rows_read, r.errors, r.by_rule["r7"], r.passed) == (1000, 0, 0, True)


@spec("RUNV-06", "ISS-2", "ISS-3", "VR-4")
def test_runv06_grid_holds_first_10000_per_rule(storage, fixtures_dir):
    st, res, rows = load_files(storage, fixtures_dir, ["Sales_ManyIssues.csv"], tpl_a_settings(), tpl_a_columns())
    r = _validate(storage, st, tpl_a_rules(), {0: rows[0].file_name})
    assert (r.errors, r.warnings, r.by_rule["r5"], r.passed) == (0, 15000, 15000, True)
    assert qv.grid_count(storage.con, r.issues) == 10000
    assert qv.grid_count(storage.con, r.issues, rule_id="r5") == 10000
    last = qv.grid_page(storage.con, r.issues, offset=9999, limit=10)
    assert len(last) == 1 and last[0][2] == 10001             # CSV record 10,001 = the 10,000th data row
    assert len(qv.read_issues(storage.con, r.issues)) == 15000   # the export holds all of them
    i = iss.from_row(last[0], {0: "Sales_ManyIssues.csv"}, TPL_A_NAMES)
    assert i.message == "Sales_ManyIssues.csv, row 10,001, Customer: value is blank"


@spec("VR-6")
def test_rerun_replaces_the_issue_list(f04):
    s, st, _res, names = f04
    _validate(s, st, [Rule("r1", "c001", "VAL-1")], names)
    assert qv.totals(s.con, st.path / "issues.parquet") == (31, 0)       # 12 blank + automatic type rules 15 + 4
    _validate(s, st, tpl_a_rules(), names)
    assert qv.totals(s.con, st.path / "issues.parquet") == (66, 32)
