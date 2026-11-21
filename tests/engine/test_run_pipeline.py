"""Run pipeline end to end, headless (Phase 5): the TPL-A run sequence R-0001 to R-0007 with the discarded runs,
then TPL-C and TPL-D. Expected figures are the Test Cases sheet's (run table, RUNF-11/12, RUNM, RUNV, RUNO, RUNC,
C2-06/07, C4-06/10/11/15, C6-02 to C6-04, C6-09/10)."""
from decimal import Decimal

import pytest

from conftest import open_storage, run_job, spec, tpl_a_columns, tpl_a_rules, tpl_a_settings, tpl_c_columns
from sankalan import analysis, mapping
from sankalan.db import datafolder
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, FlatMeasure, Group, MeasureCard, Op, cards
from sankalan.model.rule import IS_DATE, IS_NUMBER, NOT_BLANK, WARNING, ERROR, Rule, with_type_rules
from sankalan.model.run import STATUS_COMMITTED, STATUS_OVERRIDE
from sankalan.model.template import DefaultOutput, SourceSettings, Template, TemplateError
from sankalan.query import catalogue as q
from sankalan.query import export as qx
from sankalan.query import layer
from sankalan.run import pipeline as p
from sankalan.run.pipeline import RunBlocked, RunSession

D = Decimal
INV, DATE_, CUST, GSTIN, STATE, TAXABLE, RATE, TAX = (f"c00{i}" for i in range(1, 9))
DO1 = Definition("", [], [Group(STATE)],
                 cards(FlatMeasure(TAXABLE, d.SUM, "Taxable"), FlatMeasure(TAX, d.SUM, "Tax"), FlatMeasure(INV, d.COUNT, "Invoices")))
DO2 = Definition("", [Filter(DATE_, d.LATEST_MONTH)], [Group(DATE_, "month"), Group(RATE)],
                 cards(FlatMeasure(TAXABLE, d.SUM)), subtotals=True)
REASON = "Client confirmed errors; revised file next month"
PLENTY = 10 * 1024 ** 3          # free bytes passed to the commit check so tests never depend on this PC's disk


def job(s, work, cancellable=True):
    return run_job(s.runner, work) if cancellable else _uncancellable(s, work)


def _uncancellable(s, work):
    j = s.runner.run("commit", work, cancellable=False)
    if j.error is not None:
        raise j.error
    return j.result


def session(s, tid, fx, *names) -> RunSession:
    sess = RunSession(s.folder, q.load_template(s.con, tid), workers=0)
    job(s, lambda ctx: sess.add_files(ctx, [fx / n for n in names]))
    return sess


def to_commit(s, sess, reason=None):
    """Validate (if not yet), split, outputs and totals: the run is at the Commit step."""
    if sess.validation is None:
        job(s, sess.validate)
    job(s, lambda ctx: sess.leave_validate(ctx, reason))
    if sess.outputs:
        job(s, sess.run_outputs)
    job(s, lambda ctx: sess.check_totals(ctx, fault={}))
    return sess


def commit(s, sess, comment=""):
    return _uncancellable(s, lambda ctx: sess.commit(ctx, comment, free_bytes=PLENTY))


def shown(s, res, subtotals=False):
    return layer.rows(s.con, res, subtotals=subtotals, limit=1000)


def do1(s, res):
    return {r[1]: tuple(r[2:]) for r in shown(s, res)}


def totals(sess):
    return {t.column_id: (t.input, t.loaded, t.left_out, t.passed) for t in sess.totals}


def stored(s, tid):
    return sum(r.rows_loaded for r in q.list_runs(s.con, tid))


def tpl_a(con, client):
    cols = tpl_a_columns()
    t = Template("", client, "Sales Register", tpl_a_settings(), cols, with_type_rules(cols, tpl_a_rules()),
                 [DefaultOutput("State-wise sales", DO1.to_dict()),
                  DefaultOutput("Latest month by GST rate", DO2.to_dict())],
                 {"pattern": "{Template}_{RunID}_{Output}", "delimiter": ",", "encoding": "utf-8-sig"})
    return q.create_template(con, t)


@pytest.fixture(scope="module")
def seq(tmp_path_factory, fixtures_dir):
    """Run the TPL-A sequence once, recording what each step showed."""
    s = open_storage(tmp_path_factory.mktemp("seq"))
    fx = fixtures_dir
    acme = q.insert_client(s.con, "Acme Traders")
    tid = tpl_a(s.con, acme)
    seen = {"tid": tid, "client": acme}

    # ---- R-0001 (F02): RUNF-12, RUNV-01, RUNO-01, RUNC-01, RUNC-04, RUNC-05
    a = session(s, tid, fx, "Sales_Oct.xlsx")
    plan = a.files_next()
    seen["r1_skip"] = plan.skip
    seen["r1_val"] = job(s, a.validate)
    to_commit(s, a)
    seen["r1_outputs"] = [(o.name, o.status, o.note) for o in a.outputs]
    seen["r1_do1"] = (do1(s, a.outputs[0].result), layer.grand_total(s.con, a.outputs[0].result))
    seen["r1_do2"] = [(r[0], r[1], r[2], r[3]) for r in shown(s, a.outputs[1].result, subtotals=True)]
    seen["r1_totals"] = totals(a)
    seen["r1_long_comment"] = a.commit_blockers("x" * 501, PLENTY)
    seen["r1_empty_comment"] = a.commit_blockers("", PLENTY)
    seen["r1_low_disk"] = a.commit_blockers("", p.COMMIT_FREE_BYTES - 1)
    staged = a.staging.path
    seen["r1"] = commit(s, a, "October sales, first load")
    seen["r1_staging_gone"] = not staged.exists()

    # ---- RUNF-11 / RUN-7: F05 has F02's contents
    dup = session(s, tid, fx, "Sales_Oct_copy.xlsx")
    row = dup.files[0]
    seen["dup_row"] = (row.status, row.duplicate_of["run"], row.message)
    seen["dup_blocked"] = dup.files_blockers()
    dup.load_anyway(row.path)
    seen["dup_after"] = (dup.files[0].status, dup.files_blockers())
    dup.remove_file(row.path)
    seen["dup_removed"] = (dup.files, dup.files_blockers())
    dup.discard()

    # ---- R-0002 (F03): RUNV-02, RUNC-03, C6-03
    b = session(s, tid, fx, "Sales_Nov.xlsx")
    b.files_next()
    seen["r2_val"] = job(s, b.validate)
    to_commit(s, b)
    seen["r2_totals"] = totals(b)
    seen["r2"] = commit(s, b)

    # ---- discarded run (F04): RUNV-09, then RUNC-07
    x = session(s, tid, fx, "Sales_Errors.xlsx")
    x.files_next()
    v = job(s, x.validate)
    seen["x_before"] = (v.errors, v.warnings)
    rules = [Rule.from_dict(r.to_dict()) for r in x.rules]
    gst = next(r for r in rules if r.id == "r9")
    gst.settings = {"values": ["0", "5", "12", "15", "18", "28"]}
    v = job(s, lambda ctx: x.edit_rules(ctx, rules))
    seen["x_after"] = (v.errors, v.scan.by_rule["r9"])
    x_staging = x.staging.path
    x.discard()
    seen["x_gone"] = not x_staging.exists()
    seen["x_template_r9"] = next(r for r in q.load_template(s.con, tid).rules if r.id == "r9").settings

    # ---- R-0003 (F04): RUNV-03, RUNV-13, RUNO-03, RUNC-02, RUNC-06, RUNC-07, C6-02
    c = session(s, tid, fx, "Sales_Errors.xlsx")
    c.files_next()
    v = seen["r3_val"] = job(s, c.validate)
    blocked = []
    for reason in (None, "", "   "):
        try:
            job(s, lambda ctx: c.leave_validate(ctx, reason))
        except RunBlocked as e:
            blocked.append(e.message)
    seen["r3_blocked"] = blocked
    seen["r3_override_count"] = v.left_out_on_override
    seen["r3_split"] = job(s, lambda ctx: c.leave_validate(ctx, REASON))
    job(s, c.run_outputs)
    job(s, lambda ctx: c.check_totals(ctx, fault={}))
    seen["r3_do1"] = (do1(s, c.outputs[0].result), layer.grand_total(s.con, c.outputs[0].result))
    seen["r3_do2"] = [(r[1], r[2], r[3]) for r in shown(s, c.outputs[1].result)]
    seen["r3_totals"] = totals(c)
    seen["r3_prefill"] = c.comment_prefill
    seen["r3_empty"] = c.commit_blockers("", PLENTY)
    seen["r3"] = commit(s, c, c.comment_prefill)

    # ---- RUNM-06: Inv No mapped for this run only, then discarded
    m = session(s, tid, fx, "Sales_Renamed_Headers.xlsx")
    plan = m.files_next()
    hdr = plan.sheets[0].headers
    plan.map(INV, 0, hdr.index("Inv No"), save_alias=False)
    plan.leave_null(STATE, 0)
    plan.leave_out(0, hdr.index("Remarks"))
    job(s, m.validate)
    m.discard()
    seen["runm06_aliases"] = q.load_template(s.con, tid).column(INV).aliases

    # ---- R-0004 (F08): RUNM-01 to RUNM-05, RUNV-08, RUNO-04, C6-04
    e = session(s, tid, fx, "Sales_Renamed_Headers.xlsx")
    plan = e.files_next()
    hdr = plan.sheets[0].headers
    seen["r4_plan"] = {
        "skip": plan.skip,
        "cells": {cid: (plan.cell(cid, 0).how, None if plan.cell(cid, 0).position is None
                        else hdr[plan.cell(cid, 0).position]) for cid in (INV, DATE_, CUST, GSTIN, STATE, TAXABLE,
                                                                          RATE, TAX)},
        "extras": {hdr[pos] for pos in plan.extra_headers(0)},
        "first": plan.first_undecided()}
    try:
        e.mapping_next()
    except RunBlocked as ex:
        seen["r4_next_blocked"] = ex.message
    plan.map(INV, 0, hdr.index("Inv No"), save_alias=True)
    seen["r4_null_warning"] = plan.leave_null(STATE, 0)
    seen["r4_first_after"] = plan.first_undecided()
    plan.leave_out(0, hdr.index("Remarks"))
    seen["r4_complete"] = plan.complete
    seen["r4_val"] = job(s, e.validate)
    to_commit(s, e)
    seen["r4_do1"] = shown(s, e.outputs[0].result)
    seen["r4"] = commit(s, e)
    seen["r4_template"] = q.load_template(s.con, tid)

    # ---- C2-06 / C2-07 / C4-10 / C4-15 / C4-06 (after R-0004, before R-0005)
    copy_id = q.duplicate_template(s.con, tid, "Sales Register copy")
    seen["copy"] = (q.load_template(s.con, copy_id), q.list_runs(s.con, copy_id))
    cp = q.load_template(s.con, copy_id)
    cp.column(CUST).type = "Number"
    cp.column(CUST).decimals = 2
    seen["copy_type_change"] = q.save_template(s.con, cp)
    orig = q.load_template(s.con, tid)
    orig.column(CUST).type = "Number"
    orig.column(CUST).decimals = 2
    with pytest.raises(TemplateError) as err:
        q.save_template(s.con, orig)
    seen["c410_type"] = str(err.value)
    orig = q.load_template(s.con, tid)
    orig.column(TAXABLE).decimals = 3
    with pytest.raises(TemplateError) as err:
        q.save_template(s.con, orig)
    seen["c410_decimals"] = str(err.value)
    orig = q.load_template(s.con, tid)
    orig.column(STATE).removed = True
    with pytest.raises(TemplateError) as err:
        q.save_template(s.con, orig)
    seen["c415"] = str(err.value)
    orig = q.load_template(s.con, tid)
    defn = Definition.from_dict(orig.outputs[0].definition)
    defn.measures.append(MeasureCard(CUST, [Op(d.COUNT_DISTINCT, "Customers")]))
    orig.outputs[0].definition = defn.to_dict()
    seen["c406_version"] = (q.template_version(s.con, tid), q.save_template(s.con, orig))

    # ---- R-0005 (F13): RUNM-07, RUNV-10, C4-06
    f = session(s, tid, fx, "Sales_Dec_NewCol.xlsx")
    plan = f.files_next()
    hdr = plan.sheets[0].headers
    seen["r5_first"] = plan.first_undecided()
    branch = plan.add_column(0, hdr.index("Branch"), "Branch", "Text")
    seen["r5_branch_id"] = branch
    job(s, f.validate)
    rules = [Rule.from_dict(r.to_dict()) for r in f.rules]
    next(r for r in rules if r.id == "r5").severity = ERROR
    v_before = q.template_version(s.con, tid)
    seen["r5_val"] = job(s, lambda ctx: f.edit_rules(ctx, rules, save_to_template=True))
    seen["r5_saved_version"] = (v_before, q.template_version(s.con, tid))
    to_commit(s, f)
    seen["r5_do1"] = (do1(s, f.outputs[0].result), [c.label for c in f.outputs[0].result.columns])
    seen["r5"] = commit(s, f)
    seen["r5_template"] = q.load_template(s.con, tid)
    t5 = q.load_template(s.con, tid)
    t5.column(branch).type = "Number"
    t5.column(branch).decimals = 2
    with pytest.raises(TemplateError) as err:
        q.save_template(s.con, t5)
    seen["r5_branch_locked"] = str(err.value)
    t5 = q.load_template(s.con, tid)
    runs = {r.label: r for r in q.list_runs(s.con, tid)}
    res = job(s, lambda ctx: analysis.run_analysis(
        ctx, Definition(tid, [], [Group(branch)], cards(FlatMeasure(INV, d.COUNT))), t5.columns,
        [s.folder.run_dir(tid, runs[k].id) / "data.parquet" for k in ("R-0001", "R-0005")]))
    seen["runm07_analysis"] = [(r[1], r[2]) for r in shown(s, res)]

    # ---- R-0006 (F14): RUNO-05; then C6-09 delete; R-0007 (F15): RUNC-08
    g = session(s, tid, fx, "Sales_NoDates.xlsx")
    seen["r6_skip"] = g.files_next().skip
    to_commit(s, g)
    seen["r6_outputs"] = [(o.name, o.status, o.note, layer.grand_total(s.con, o.result)) for o in g.outputs]
    seen["r6_outputs"][0] = seen["r6_outputs"][0][:3] + (seen["r6_outputs"][0][3][:3],)   # DO1 had Customers added
    seen["r6"] = commit(s, g)
    seen["stored_after_r6"] = stored(s, tid)
    datafolder.delete_run(s.con, s.folder, seen["r6"].run_id)
    seen["r6_folder_gone"] = not s.folder.run_dir(tid, seen["r6"].run_id).exists()
    seen["stored_after_delete"] = stored(s, tid)
    h = session(s, tid, fx, "Sales_Jan.xlsx")
    h.files_next()
    to_commit(s, h)
    seen["r7"] = commit(s, h)
    seen["stored_after_r7"] = stored(s, tid)
    yield s, seen
    s.close()


def details(seq, key):
    s, seen = seq
    return q.run_details(s.con, seen[key].run_id)


# ---------------------------------------------------------------------------------------------- the run table
@spec("TPL-A run sequence", "T22", "RUNC-05", "RUNC-07", "RUNC-08", "RUN-2")
def test_run_table(seq):
    s, seen = seq
    assert [seen[k].label for k in ("r1", "r2", "r3", "r4", "r5", "r6", "r7")] == [
        "R-0001", "R-0002", "R-0003", "R-0004", "R-0005", "R-0006", "R-0007"]
    runs = q.list_runs(s.con, seen["tid"])
    assert [(r.label, r.rows_loaded) for r in runs] == [
        ("R-0001", 5000), ("R-0002", 4000), ("R-0003", 1937), ("R-0004", 1000), ("R-0005", 3000), ("R-0007", 2000)]
    cum, out = 0, []
    for r in runs:
        cum += r.rows_loaded
        out.append(cum)
    assert out == [5000, 9000, 10937, 11937, 14937, 16937]
    assert seen["stored_after_r6"] == 15437 and seen["stored_after_delete"] == 14937
    assert seen["stored_after_r7"] == 16937
    assert seen["r6_folder_gone"] and seen["r1_staging_gone"]
    assert list(s.folder.staging_root.iterdir()) == []            # discarded runs keep nothing (RUN-14)
    assert q.last_run_number(s.con, seen["tid"]) == 7


# ---------------------------------------------------------------------------------------------- R-0001
@spec("RUNF-12", "TPL-6", "RUNV-01")
def test_r0001_mapping_skipped_and_clean_counts(seq):
    _, seen = seq
    assert seen["r1_skip"] is True
    v = seen["r1_val"]
    assert (v.errors, v.warnings, v.rows_read, v.hidden_rows, v.hidden_sheets, v.passed) == (0, 0, 5000, 0, [], True)


@spec("RUNO-01", "DO-2", "DO-4")
def test_r0001_outputs(seq):
    _, seen = seq
    assert seen["r1_outputs"] == [("State-wise sales", p.DONE, None), ("Latest month by GST rate", p.DONE, None)]
    by_state, total = seen["r1_do1"]
    assert by_state == {
        "Delhi": (D("1903437.50"), D("240655.00"), 1250), "Gujarat": (D("1877812.50"), D("239885.00"), 1250),
        "Karnataka": (D("1890625.00"), D("241807.50"), 1250), "Maharashtra": (D("1865000.00"), D("234375.00"), 1250)}
    assert total == (D("7536875.00"), D("956722.50"), 5000)
    rows = seen["r1_do2"]
    assert [(r[2], r[3]) for r in rows] == [(D(0), D("1486875.00")), (D(5), D("1497125.00")),
                                            (D(12), D("1507375.00")), (D(18), D("1517625.00")),
                                            (D(28), D("1527875.00")), (None, D("7536875.00"))]
    assert {r[1].month for r in rows} == {10} and rows[-1][0] == 1


@spec("RUNC-01", "RUN-6", "T20")
def test_r0001_totals(seq):
    _, seen = seq
    assert seen["r1_totals"] == {TAXABLE: (D("7536875.00"), D("7536875.00"), D("0.00"), True),
                                 TAX: (D("956722.50"), D("956722.50"), D("0.00"), True)}


@spec("RUNC-04", "RUN-13", "RUNC-05")
def test_r0001_comment_rules_and_commit(seq):
    _, seen = seq
    assert seen["r1_long_comment"] == ["The comment can be at most 500 characters."]
    assert seen["r1_empty_comment"] == []                       # optional when not overridden
    assert seen["r1_low_disk"] == ["There isn't enough free disk space to commit this run."]
    r = details(seq, "r1")
    assert (r["status"], r["comment"], r["rows_read"], r["rows_loaded"], r["rows_left_out"]) == (
        STATUS_COMMITTED, "October sales, first load", 5000, 5000, 0)
    assert r["totals"][TAXABLE] == {"name": "Taxable Value", "decimals": 2, "input": "7536875.00",
                                    "loaded": "7536875.00", "left_out": "0.00", "passed": True}
    assert [(o.position, o.name, o.file) for o in r["outputs"]] == [(1, "State-wise sales", "outputs/1.parquet"),
                                                                   (2, "Latest month by GST rate", "outputs/2.parquet")]
    s, seen_ = seq
    folder = s.folder.run_dir(seen_["tid"], seen_["r1"].run_id)
    assert sorted(x.name for x in folder.iterdir()) == ["data.parquet", "issues.parquet", "left_out.parquet",
                                                        "outputs"]     # raw\ and conversion failures removed


@spec("RUNF-11", "RUN-7")
def test_duplicate_contents_warning(seq):
    _, seen = seq
    status, run, message = seen["dup_row"]
    assert status == "warning" and run == "R-0001"
    assert "R-0001" in message and "Remove it, or Load anyway" in message
    assert seen["dup_blocked"] == [message]
    assert seen["dup_after"] == ("ready", [])
    assert seen["dup_removed"] == ([], ["Add at least one file."])


# ---------------------------------------------------------------------------------------------- R-0002
@spec("RUNV-02", "RUNC-03", "C6-03", "IN-13")
def test_r0002_hidden_and_blank_rows(seq):
    _, seen = seq
    v = seen["r2_val"]
    assert (v.rows_read, v.rows_to_load, v.blank_rows, v.hidden_rows, v.hidden_sheets, v.errors, v.warnings) == (
        4010, 4000, 10, 25, ["Old"], 0, 0)
    assert seen["r2_totals"] == {TAXABLE: (D("6029500.00"), D("6029500.00"), D("0.00"), True),
                                 TAX: (D("765378.00"), D("765378.00"), D("0.00"), True)}
    r = details(seq, "r2")
    assert (r["rows_read"], r["rows_loaded"], r["rows_left_out"]) == (4010, 4000, 10)
    assert r["left_out_by_reason"] == {"blank": 10, "errors": 0, "duplicates": 0}
    f = r["files"][0]
    assert (f["file_name"], f["sheet"], f["header_row"], f["hidden_rows"], f["sheets_skipped"]) == (
        "Sales_Nov.xlsx", "Sales", 2, 25, ["Old"])                      # C6-07


# ---------------------------------------------------------------------------------------------- discarded run
@spec("RUNV-09", "VR-5", "TPL-8", "RUN-14")
def test_run_only_rule_edit_then_discard(seq):
    _, seen = seq
    assert seen["x_before"] == (66, 32)
    assert seen["x_after"] == (60, 0)
    assert seen["x_gone"]
    assert seen["x_template_r9"] == {"values": ["0", "5", "12", "18", "28"]}


# ---------------------------------------------------------------------------------------------- R-0003
@spec("RUNV-03", "RUNV-13", "RUN-4", "T18")
def test_r0003_override(seq):
    _, seen = seq
    v = seen["r3_val"]
    assert (v.errors, v.warnings, v.rows_read, v.hidden_rows) == (66, 32, 2000, 0)
    assert seen["r3_override_count"] == 63
    assert seen["r3_blocked"] == ["Enter a reason to continue despite errors."] * 3
    assert seen["r3_split"] == (1937, 63)


@spec("RUNO-03", "DO-2", "T18")
def test_r0003_outputs_exclude_left_out_rows(seq):
    _, seen = seq
    by_state, total = seen["r3_do1"]
    assert by_state == {
        "Delhi": (D("739448.00"), D("93038.02"), 480), "Goa": (D("28075.00"), D("3572.83"), 25),
        "Gujarat": (D("725157.00"), D("93821.11"), 476), "Karnataka": (D("734282.00"), D("94229.23"), 480),
        "Maharashtra": (D("720032.00"), D("90333.16"), 476)}
    assert total == (D("2946994.00"), D("374994.35"), 1937)
    rows = seen["r3_do2"]
    assert {r[0].month for r in rows} == {9}
    assert [(r[1], r[2]) for r in rows] == [(D(0), D("578776.25")), (D(5), D("583835.25")), (D(12), D("590089.00")),
                                            (D(18), D("594117.25")), (D(28), D("600176.25"))]


@spec("RUNC-02", "RUNC-06", "C6-02", "RUN-12", "RUN-13")
def test_r0003_totals_comment_and_summary(seq):
    _, seen = seq
    assert seen["r3_totals"] == {TAXABLE: (D("2986623.75"), D("2946994.00"), D("39629.75"), True),
                                 TAX: (D("381662.10"), D("374994.35"), D("6667.75"), True)}
    assert seen["r3_prefill"] == REASON
    assert seen["r3_empty"] == ["Enter a comment: this run continues despite errors."]
    r = details(seq, "r3")
    assert (r["label"], r["status"], r["comment"]) == ("R-0003", STATUS_OVERRIDE, REASON)
    assert (r["rows_read"], r["rows_loaded"], r["rows_left_out"], r["errors"], r["warnings"]) == (
        2000, 1937, 63, 66, 32)
    assert r["left_out_by_reason"] == {"blank": 0, "errors": 60, "duplicates": 3}
    assert r["run_changes"]["override_reason"] == REASON
    s, seen_ = seq
    counts = q.run_issue_counts(s.con, seen_["r3"].run_id)
    assert sum(c[3] for c in counts) == 66 and sum(c[4] for c in counts) == 32


# ---------------------------------------------------------------------------------------------- mapping (R-0004)
@spec("RUNM-01", "RUNM-02", "MAP-2", "MAP-4", "MAP-13")
def test_r0004_mapping_grid(seq):
    _, seen = seq
    m = seen["r4_plan"]
    assert m["skip"] is False
    assert m["cells"] == {INV: (None, None), DATE_: ("name", "invoice_date"), CUST: ("name", "CUSTOMER"),
                          GSTIN: ("name", "G.S.T.I.N"), STATE: (None, None), TAXABLE: ("name", "Taxable Value"),
                          RATE: ("name", "GST-Rate"), TAX: ("name", "Tax Amount")}
    assert m["extras"] == {"Inv No", "Remarks"}
    assert m["first"] == ("cell", INV, 0)
    assert seen["r4_next_blocked"] == "Some columns still need a decision."


@spec("RUNM-03", "RUNM-04", "RUNM-05", "RUNM-06", "MAP-5", "MAP-6", "MAP-7", "C4-11")
def test_r0004_mapping_decisions(seq):
    _, seen = seq
    assert seen["r4_null_warning"] == ['Default output "State-wise sales" will show these rows as (Null).']
    assert seen["r4_first_after"][0] == "extra"
    assert seen["r4_complete"]
    assert seen["runm06_aliases"] == []                         # This run only, discarded: nothing saved
    assert seen["r4_template"].column(INV).aliases == ["Inv No"]


@spec("RUNV-08", "RUNO-04", "C6-04", "RUN-12")
def test_r0004_validate_outputs_summary(seq):
    _, seen = seq
    v = seen["r4_val"]
    assert (v.rows_read, v.errors) == (1000, 0) and v.scan.by_rule["r7"] == 0
    assert [(r[1], r[2], r[3], r[4]) for r in seen["r4_do1"]] == [(None, D("1507375.00"), D("191344.50"), 1000)]
    r = details(seq, "r4")
    assert [mapping.describe(x) for x in r["run_changes"]["mapping"]] == [
        "Inv No mapped to Invoice No and saved as an alias (Sales_Renamed_Headers.xlsx · Sales)",
        "State left as null (Sales_Renamed_Headers.xlsx · Sales)",
        "Remarks left out (Sales_Renamed_Headers.xlsx · Sales)"]
    assert r["template_version"] == seen["r4_template"].version          # the version with the alias


# ---------------------------------------------------------------------------------------------- template rules
@spec("C2-06", "C2-07", "TPL-4", "TPL-9")
def test_duplicate_template(seq):
    s, seen = seq
    copy, runs = seen["copy"]
    orig = seen["r4_template"]
    assert runs == [] and copy.name == "Sales Register copy" and copy.version == 1
    assert copy.snapshot()["columns"] == orig.snapshot()["columns"]
    assert [r.to_dict() for r in copy.rules] == [r.to_dict() for r in orig.rules]
    assert [o.name for o in copy.outputs] == ["State-wise sales", "Latest month by GST rate"]
    assert copy.outputs[0].definition["template_id"] == copy.id
    assert copy.source == orig.source and copy.export == orig.export
    assert seen["copy_type_change"] == 2                        # type editable with no runs (C2-07)


@spec("C4-10", "C4-15", "MAP-11", "MAP-12", "TPL-9")
def test_template_locks(seq):
    _, seen = seq
    assert seen["c410_type"] == "The type of Customer can't change: data has already been loaded with it."
    assert "decimal places of Taxable Value" in seen["c410_decimals"]
    assert seen["c415"] == ("State can't be removed while the default output \"State-wise sales\" uses it. "
                            "Change that output first.")
    assert "Branch can't change" in seen["r5_branch_locked"]


@spec("C4-06", "C6-10", "DO-6")
def test_edited_output_affects_future_runs_only(seq):
    s, seen = seq
    before, after = seen["c406_version"]
    assert after == before + 1
    by_state, labels = seen["r5_do1"]
    assert labels == ["State", "Taxable", "Tax", "Invoices", "Customers"]
    # The sheet says 10 per state; F00 gives each state only 5 of the 10 customers (both cycles share the factor 2).
    # Confirmed by the user 17-11-2026: the expected figure is 5.
    assert {k: v[3] for k, v in by_state.items()} == {"Delhi": 5, "Gujarat": 5, "Karnataka": 5, "Maharashtra": 5}
    # R-0001's saved DO1 still has its 3 measures and values (C6-10)
    r1 = details(seq, "r1")
    out = r1["outputs"][0]
    assert len(out.definition["measures"]) == 3
    cols = q.load_template(s.con, seen["tid"]).columns
    res = layer.open_output(Definition.from_dict(out.definition), cols,
                            s.folder.run_dir(seen["tid"], seen["r1"].run_id) / out.file, s.con)
    assert [c.label for c in res.columns] == ["State", "Taxable", "Tax", "Invoices"]
    assert layer.grand_total(s.con, res) == (D("7536875.00"), D("956722.50"), 5000)


# ---------------------------------------------------------------------------------------------- R-0005 .. R-0007
@spec("RUNM-07", "MAP-7", "MAP-11", "RUNV-10", "TPL-7")
def test_r0005_new_column_and_saved_rule(seq):
    _, seen = seq
    assert seen["r5_first"][0] == "extra"
    t = seen["r5_template"]
    assert t.column(seen["r5_branch_id"]).name == "Branch" and t.column("c009").type == "Text"
    assert next(r for r in t.rules if r.id == "r5").severity == ERROR
    before, after = seen["r5_saved_version"]
    assert after == before + 1
    r = details(seq, "r5")
    assert r["run_changes"]["rules_saved"] == [{"change": "changed", "rule_id": "r5",
                                                "before": {"id": "r5", "column_id": CUST, "type": NOT_BLANK,
                                                           "settings": {}, "severity": WARNING},
                                                "after": {"id": "r5", "column_id": CUST, "type": NOT_BLANK,
                                                          "settings": {}, "severity": ERROR}}]
    assert r["run_changes"]["rules_run_only"] == []
    assert r["template_version"] == t.version
    assert seen["runm07_analysis"] == [("Nagpur", 1000), ("Nashik", 1000), ("Pune", 1000), (None, 5000)]


@spec("RUNO-05", "T21", "C6-09", "RUNC-08")
def test_r0006_no_dates_then_delete(seq):
    _, seen = seq
    assert seen["r6_skip"] is True                              # Branch is now a template column
    (n1, s1, note1, t1), (n2, s2, note2, t2) = seen["r6_outputs"]
    assert (s1, note1, t1) == (p.DONE, None, (D("753687.50"), D("95672.25"), 500))
    assert (s2, note2, t2) == (p.DONE, d.NO_DATES_NOTE, None)


# ---------------------------------------------------------------------------------------------- RUNC-10 fault hook
@spec("RUNC-10", "RUN-6")
def test_runc10_totals_mismatch_blocks_commit(tmp_path, fixtures_dir, monkeypatch):
    s = open_storage(tmp_path)
    try:
        tid = tpl_a(s.con, q.insert_client(s.con, "Acme Traders"))
        sess = session(s, tid, fixtures_dir, "Sales_Oct.xlsx")
        sess.files_next()
        to_commit(s, sess)
        assert sess.totals_passed
        monkeypatch.setenv(p.FAULT_ENV, f"{TAXABLE}:0.01")
        lines = job(s, sess.check_totals)                       # reads the hook: running from source
        assert [(t.column_id, t.loaded, t.passed) for t in lines] == [(TAXABLE, D("7536875.01"), False),
                                                                     (TAX, D("956722.50"), True)]
        assert sess.commit_blockers("", PLENTY) == [
            "The totals check doesn't match for Taxable Value. This run can't be committed."]
        with pytest.raises(RunBlocked):
            commit(s, sess)
        assert q.list_runs(s.con, tid) == []
        monkeypatch.delenv(p.FAULT_ENV)
        job(s, sess.check_totals)
        assert commit(s, sess).label == "R-0001"
    finally:
        s.close()


def test_fault_hook_only_from_source():
    env = {p.FAULT_ENV: "c006:0.01, c008:-1"}
    assert p.fault_from_env(env, frozen=False) == {"c006": D("0.01"), "c008": D("-1")}
    assert p.fault_from_env(env, frozen=True) == {}
    assert p.fault_from_env({}, frozen=False) == {}


# ---------------------------------------------------------------------------------------------- outputs: cancel, retry
@spec("RUNO-06", "DO-5")
def test_output_cancel_and_retry(tmp_path, fixtures_dir):
    s = open_storage(tmp_path)
    try:
        tid = tpl_a(s.con, q.insert_client(s.con, "Acme Traders"))
        sess = session(s, tid, fixtures_dir, "Sales_Oct.xlsx")
        sess.files_next()
        job(s, sess.validate)
        job(s, lambda ctx: sess.leave_validate(ctx))
        from sankalan.jobs import JobState

        def cancel_first(ctx):
            ctx._job.cancel()                                    # cancel lands while the first output runs
            return sess.run_outputs(ctx)
        j = s.runner.run("outputs", cancel_first)
        assert j.state is JobState.CANCELLED
        assert [o.status for o in sess.outputs] == [p.CANCELLED, p.CANCELLED]
        assert not sess.outputs_done
        assert "Every default output must be generated first." in sess.commit_blockers("", PLENTY)
        assert not any((sess.staging.path / "outputs").glob("*.parquet"))
        job(s, sess.run_outputs)                                 # Retry
        assert [o.status for o in sess.outputs] == [p.DONE, p.DONE] and sess.outputs_done
    finally:
        s.close()


# ---------------------------------------------------------------------------------------------- TPL-C, TPL-D
@spec("RUNO-07", "C3-21", "DO-4", "TPL-C")
def test_tpl_c_conversion_run(tmp_path, fixtures_dir):
    s = open_storage(tmp_path)
    try:
        client = q.insert_client(s.con, "Bharat Foods")
        cols = tpl_c_columns()
        rules = [Rule(r.id, r.column_id, r.type, r.settings, WARNING) for r in with_type_rules(cols, [])]
        assert {r.type for r in rules} == {IS_NUMBER, IS_DATE}
        tid = q.create_template(s.con, Template("", client, "Conversion check", SourceSettings(sheets="first"),
                                                cols, rules))
        sess = session(s, tid, fixtures_dir, "Conversion_Values.csv")
        assert sess.files_next().skip
        v = job(s, sess.validate)
        assert (v.errors, v.warnings, v.rows_read) == (0, 5, 13)
        assert {k: n for k, n in v.scan.by_rule.items() if n} == {"c002.type": 1, "c003.type": 1, "c004.type": 2,
                                                                  "c005.type": 1}
        job(s, lambda ctx: sess.leave_validate(ctx))
        assert sess.outputs_skipped and sess.outputs_done
        assert job(s, lambda ctx: sess.check_totals(ctx, fault={})) == []
        done = commit(s, sess)
        assert done.label == "R-0001"
        r = q.run_details(s.con, done.run_id)
        assert (r["status"], r["rows_loaded"], r["warnings"], r["outputs"]) == (STATUS_COMMITTED, 13, 5, [])
    finally:
        s.close()


@spec("TPL-D", "RUNF-13", "IN-5")
def test_tpl_d_all_visible_sheets(tmp_path, fixtures_dir):
    s = open_storage(tmp_path)
    try:
        client = q.insert_client(s.con, "Bharat Foods")
        cols = tpl_a_columns()
        tid = q.create_template(s.con, Template("", client, "Regional Sales", SourceSettings(sheets="all"), cols,
                                                with_type_rules(cols, [])))
        sess = session(s, tid, fixtures_dir, "Sales_Regions.xlsx")
        assert [(f.sheet, f.status) for f in sess.files] == [("North", "ready"), ("South", "ready")]
        assert sess.files_next().skip
        v = job(s, sess.validate)
        assert (v.rows_read, v.errors, v.warnings) == (4000, 0, 0)
        job(s, lambda ctx: sess.leave_validate(ctx))
        lines = job(s, lambda ctx: sess.check_totals(ctx, fault={}))
        assert [(t.column_id, t.input, t.loaded, t.passed) for t in lines][0] == (
            TAXABLE, D("6029500.00"), D("6029500.00"), True)
        done = commit(s, sess)
        r = q.run_details(s.con, done.run_id)
        assert (done.label, r["rows_loaded"]) == ("R-0001", 4000)
        assert [(f["sheet"], f["rows_read"]) for f in r["files"]] == [("North", 1500), ("South", 2500)]
        assert all(f["sheets_skipped"] == ["Archive"] for f in r["files"])
    finally:
        s.close()


# ---------------------------------------------------------------------------------------------- mapping unit cases
def _plan(headers, outputs=()):
    cols = tpl_a_columns()
    t = Template("t", "c", "T", tpl_a_settings(), cols, [], [DefaultOutput(n, dd.to_dict()) for n, dd in outputs])
    return mapping.MappingPlan(t, [mapping.Sheet(0, "a.xlsx", "Sales", headers),
                                   mapping.Sheet(1, "b.xlsx", "Sales", headers)])


def test_mapping_add_column_spans_sheets_and_undo():
    hdr = [c.name for c in tpl_a_columns()] + ["Branch"]
    plan = _plan(hdr)
    assert not plan.skip and plan.first_undecided() == ("extra", 0, 8)
    cid = plan.add_column(0, 8, "Branch", "Text")
    assert cid == "c009" and plan.complete                      # the same header in b.xlsx maps to it
    assert plan.cell(cid, 1).position == 8
    plan.leave_out(0, 8)                                        # changing the decision drops the new column
    assert [c.id for c in plan.columns][-1] == "c008"
    assert plan.first_undecided() == ("extra", 1, 8)
    with pytest.raises(mapping.MappingError):
        plan.add_column(1, 8, "Invoice No", "Text")             # name taken
    res = (plan.leave_out(1, 8), plan.result())[1]
    assert res.new_columns == [] and [x["kind"] for x in res.decisions] == ["leave_out", "leave_out"]


def test_mapping_run_only_and_release():
    hdr = ["Inv No"] + [c.name for c in tpl_a_columns()][1:]
    plan = _plan(hdr, [("DO", DO1)])
    plan.map(INV, 0, 0, save_alias=False)
    plan.map(INV, 1, 0, save_alias=True)
    with pytest.raises(mapping.MappingError):
        plan.map(CUST, 0, 0, save_alias=False)                 # already used by Invoice No
    assert plan.leave_null(STATE, 0) == ['Default output "DO" will show these rows as (Null).']
    res = plan.result()
    assert res.aliases == {INV: ["Inv No"]}
    assert [x["kind"] for x in res.decisions] == ["run_only", "alias", "null"]
    plan.leave_null(INV, 0)                                     # the header goes back to the extras
    assert plan.first_undecided() == ("extra", 0, 0)
    assert plan.null_warnings(INV) == ['Default output "DO" will show these rows as (Null).']


# ---------------------------------------------------------------------------------------------- A2-1
@spec("T50", "MEA-9", "DO-6", "AC-TXT-8")
def test_stored_output_headers_survive_a_column_rename(tmp_path, fixtures_dir):
    """run_output.headers holds the headers at commit (T50): renaming a template column afterwards changes neither
    the stored headers nor what the Run screen and its exports show; a new run uses the new name."""
    from conftest import commit_tpl_a_run, tpl_a_template
    from sankalan import runs
    s = open_storage(tmp_path)
    try:
        acme = q.insert_client(s.con, "Acme Traders")
        tid = q.create_template(s.con, tpl_a_template(acme))
        r1 = commit_tpl_a_run(s, tid, fixtures_dir, "Sales_Oct.xlsx")
        stored = q.run_outputs(s.con, r1.run_id)
        assert [o.headers for o in stored] == [["State", "Taxable", "Tax", "Invoices"],
                                              ["Invoice Date", "GST Rate", "Taxable Value · Sum"]]
        t = q.load_template(s.con, tid)
        for cid, new, old in ((STATE, "Region", "State"), (TAXABLE, "Taxable Amt", "Taxable Value")):
            col = next(c for c in t.columns if c.id == cid)
            col.name, col.aliases = new, [*col.aliases, old]     # the files keep the old headers
        q.save_template(s.con, t)
        assert [o.headers for o in q.run_outputs(s.con, r1.run_id)] == [o.headers for o in stored]
        cols = q.load_template(s.con, tid).columns
        o = stored[1]
        path = s.folder.run_dir(tid, r1.run_id) / o.file
        shown = run_job(s.runner, lambda ctx: runs.stored_output(ctx, o.definition, cols, path, headers=o.headers))
        assert shown.headers == ["Invoice Date", "GST Rate", "Taxable Value · Sum"]
        r2 = commit_tpl_a_run(s, tid, fixtures_dir, "Sales_Nov.xlsx")
        assert [o.headers for o in q.run_outputs(s.con, r2.run_id)][1] == ["Invoice Date", "GST Rate",
                                                                           "Taxable Amt · Sum"]
        assert q.run_details(s.con, r1.run_id)["text_counts"] == {"c002": 0, "c006": 0, "c007": 0, "c008": 0}
        # AC-MEA-9: a default output's measure renamed, then a new run: it uses the name, earlier runs keep theirs
        t = q.load_template(s.con, tid)
        defn = Definition.from_dict(t.outputs[1].definition)
        defn.measures[0].ops[0].name = "Taxable value"
        t.outputs[1].definition = defn.to_dict()
        q.save_template(s.con, t)
        r3 = commit_tpl_a_run(s, tid, fixtures_dir, "Sales_Jan.xlsx")
        got = [q.run_outputs(s.con, r.run_id)[1] for r in (r1, r2, r3)]
        assert [o.headers[2] for o in got] == ["Taxable Value · Sum", "Taxable Amt · Sum", "Taxable value"]
        o3 = got[2]
        res = layer.open_output(Definition.from_dict(o3.definition), cols, s.folder.run_dir(tid, r3.run_id) / o3.file,
                                s.con, o3.headers)
        assert qx.result(s.con, res, subtotals=False).headers == ["Invoice Date", "GST Rate", "Taxable value"]
    finally:
        s.close()
