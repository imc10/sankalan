"""Feature F on TPL-N small: templates without checks (Feature Spec A2 7, 10.7; Tech spec A2 6, T43 to T45).

The oracle is the generator's manifest (figures computed in Python from the values it wrote: 10,000 data rows,
3 blank rows, 20 repeated rows, 68 / 12 text values with their first file and row) and independent DuckDB queries.
"""
from decimal import Decimal

import pytest

import tpl_n
from conftest import commit_unchecked, load_tpl_n, open_storage, run_job, spec
from sankalan import analyses, manage, runs
from sankalan.jobs import JobState
from sankalan.model import definition as d
from sankalan.model import export as ex
from sankalan.model.definition import Definition, Group, FlatMeasure, cards
from sankalan.model.rule import IS_DATE, IS_NUMBER, NOT_BLANK, Rule
from sankalan.query import catalogue as q
from sankalan.query import convert
from sankalan.query import textvalues
from sankalan.query.split import LEFT_OUT
from sankalan.run import pipeline as p
from sankalan.run.pipeline import RunBlocked, RunSession

TAXABLE, DATE_, STATE = "c006", "c002", "c005"
F1, F2 = tpl_n.FILES
PLENTY = 10 * 1024 ** 3


@pytest.fixture(scope="module")
def n(tmp_path_factory, tpl_n_small):
    fx, m = tpl_n_small
    s = open_storage(tmp_path_factory.mktemp("tpl_n"))
    client = q.insert_client(s.con, "Acme Traders")
    tid = q.create_template(s.con, tpl_n.template(client))
    yield {"s": s, "fx": fx, "m": m, "client": client, "tid": tid}
    s.close()


def staged(s) -> list[str]:
    return sorted(x.name for x in s.folder.staging_root.iterdir()) if s.folder.staging_root.is_dir() else []


# ---------------------------------------------------------------------------------------------- model (T43)
@spec("AC-NCK-9", "NCK-1", "T43")
def test_checks_setting_round_trip_snapshot_and_duplicate(n):
    s, tid = n["s"], n["tid"]
    t = q.load_template(s.con, tid)
    assert t.checks is False and t.rules == []
    assert q.template_snapshot(s.con, tid)["settings"]["checks"] is False
    assert t.copy().checks is False
    dup = run_job(s.runner, lambda ctx: manage.duplicate_template(ctx, tid))
    assert q.load_template(s.con, dup).checks is False                      # AC-NCK-9
    other = tpl_n.template(n["client"])
    other.name, other.checks = "With checks", True
    assert q.load_template(s.con, q.create_template(s.con, other)).checks is True
    sess = RunSession(s.folder, t, workers=0)
    assert sess.checks is False and sess.third_step == p.LOAD


@spec("NCK-11", "VR-7")
def test_no_to_yes_adds_the_automatic_type_rules_and_keeps_rules(tmp_path, tpl_n_small):
    s = open_storage(tmp_path)
    try:
        tid = q.create_template(s.con, tpl_n.template(q.insert_client(s.con, "Acme Traders")))
        t = q.load_template(s.con, tid)
        t.checks = True
        t = run_job(s.runner, lambda ctx: manage.save_template(ctx, t))
        assert t.version == 2 and t.checks
        assert sorted((r.column_id, r.type) for r in t.rules) == sorted(
            [(c.id, IS_NUMBER) for c in t.columns if c.type == "Number"]
            + [(c.id, IS_DATE) for c in t.columns if c.type == "Date"])
        t.rules.append(Rule("r1", "c001", NOT_BLANK))
        t.checks = False                                                     # Yes -> No keeps the rules (NCK-11)
        t = run_job(s.runner, lambda ctx: manage.save_template(ctx, t))
        assert t.version == 3 and not t.checks and any(r.id == "r1" for r in t.rules)
        assert q.template_snapshot(s.con, tid, 3)["settings"]["checks"] is False
    finally:
        s.close()


# ---------------------------------------------------------------------------------------------- Load Job (T44, T45)
@spec("AC-NCK-2", "NCK-4", "NCK-6", "NCK-7", "T44", "T45")
def test_load_reads_every_row_with_no_checks(n):
    s, fx, m = n["s"], n["fx"], n["m"]
    sess = load_tpl_n(s, n["tid"], fx, [F1, F2])
    try:
        ls = sess.loaded
        assert (ls.files, ls.sheets) == (2, 2)
        assert ls.rows_read == m.rows_read == 10_003                          # blank rows included (T45)
        assert ls.blank_rows == m.blank_rows == 3
        assert ls.rows_to_load == m.rows_loaded == 10_000 == ls.rows_read - ls.blank_rows
        assert ls.hidden_rows == 0
        assert ls.text_counts == {TAXABLE: 68, DATE_: 12} and ls.text_total == 80
        st = sess.staging.path
        assert (st / convert.DATA).is_file()
        assert not (st / LEFT_OUT).exists() and not (st / "issues.parquet").exists()
        data = f"read_parquet('{(st / convert.DATA).as_posix()}')"
        cols = ", ".join(c.id for c in sess.columns)
        total, distinct = s.con.execute(f"SELECT count(*), count(DISTINCT ({cols})) FROM {data}").fetchone()
        assert (total, total - distinct) == (10_000, m.repeated) == (10_000, 20)   # repeated rows kept
        with pytest.raises(RunBlocked):
            run_job(s.runner, sess.validate)
        with pytest.raises(RunBlocked):
            run_job(s.runner, lambda ctx: sess.edit_rules(ctx, []))            # NCK-13
        assert sess.split_done and [o.name for o in sess.outputs] == ["Taxable by State"]
    finally:
        sess.discard()


@spec("AC-NCK-4", "NCK-8", "Tech spec A2 5.7")
def test_values_list_order_counts_and_first_place(n):
    s, fx, m = n["s"], n["fx"], n["m"]
    sess = load_tpl_n(s, n["tid"], fx, [F1, F2])
    try:
        for cid, want in ((TAXABLE, m.taxable_text), (DATE_, m.date_text)):
            got = run_job(s.runner, lambda ctx: sess.text_values(ctx, cid))
            assert [(v.text, v.count, v.file_name, v.sheet, v.row) for v in got] == \
                [(w["text"], w["count"], tpl_n.FILES[w["file_index"]], "", w["row"]) for w in want]
        got = run_job(s.runner, lambda ctx: sess.text_values(ctx, TAXABLE))
        assert [v.text for v in got][:3] == ["NA", "Nil", "-"] and " NA " in [v.text for v in got]   # as typed
        assert run_job(s.runner, lambda ctx: sess.text_values(ctx, "c007")) == []
    finally:
        sess.discard()


@spec("NCK-8")
def test_values_list_stops_at_1000(storage):
    path = storage.folder.path / "tv.parquet"
    storage.con.execute(f"""COPY (SELECT 0 AS _src_file, NULL::VARCHAR AS _src_sheet, i + 2 AS _src_row,
                                 'v' || lpad(CAST(i % 1500 AS VARCHAR), 4, '0') AS c006_t
                                 FROM range(1600) t(i)) TO '{path.as_posix()}' (FORMAT parquet)""")
    got = textvalues.text_values(storage.con, path, "c006")
    assert len(got) == 1000
    assert got[:100] == [(f"v{k:04d}", 2, 0, None, k + 2) for k in range(100)]       # most frequent first
    assert got[100] == ("v0100", 1, 0, None, 102)                                 # then by text


@spec("AC-NCK-3", "NCK-7")
def test_cancel_load_empties_staging(n):
    s = n["s"]
    sess = RunSession(s.folder, q.load_template(s.con, n["tid"]), workers=0)
    run_job(s.runner, lambda ctx: sess.add_files(ctx, [n["fx"] / F1]))
    assert sess.files_next().skip

    def cancel_first(ctx):
        ctx._job.cancel()
        return sess.load_unchecked(ctx)
    j = s.runner.run("Load files", cancel_first)
    assert j.state is JobState.CANCELLED
    sess.drop_staging()
    assert staged(s) == [] and sess.loaded is None and not sess.split_done
    assert sess.mapping_skipped                                              # back to Files (Mapping skipped)


# ---------------------------------------------------------------------------------------------- commit (6.7)
@spec("AC-NCK-2", "AC-NCK-6", "AC-NCK-8", "NCK-9", "NCK-10", "NCK-12", "T45", "T56")
def test_commit_without_checks(n):
    s, fx, m = n["s"], n["fx"], n["m"]
    sess = load_tpl_n(s, n["tid"], fx, [F1, F2])
    assert sess.commit_blockers("", PLENTY) == ["The totals check hasn't run yet.",
                                                "Every default output must be generated first."]
    run_job(s.runner, sess.run_outputs)
    lines = run_job(s.runner, lambda ctx: sess.check_totals(ctx, fault={}))
    assert sess.totals_passed and all(t.left_out == 0 and t.input == t.loaded for t in lines)
    taxable = next(t for t in lines if t.column_id == TAXABLE)
    assert taxable.loaded == Decimal(m.taxable_sum)                            # text counts as 0 (TXT-14)
    assert sess.commit_blockers("", PLENTY) == []                             # comment optional (NCK-10)
    c = commit_unchecked(s, sess)
    run = q.run_details(s.con, c.run_id)
    assert run["checks"] is False and run["status"] == "committed"
    assert (run["errors"], run["warnings"], run["rows_left_out"]) == (0, 0, 0)
    assert run["left_out_by_reason"] == {"blank": 0, "errors": 0, "duplicates": 0}
    assert (run["rows_read"], run["rows_loaded"]) == (10_003, 10_000)
    assert run["text_counts"][TAXABLE] == 68 and run["text_counts"][DATE_] == 12
    assert q.run_issue_counts(s.con, c.run_id) == []
    assert [f["rows_read"] for f in run["files"]] == [5_002, 5_001]
    rd = s.folder.run_dir(n["tid"], c.run_id)
    assert not (rd / LEFT_OUT).exists() and not (rd / "issues.parquet").exists()     # AC-NCK-2
    view = run_job(s.runner, lambda ctx: runs.run_view(ctx, s.folder, c.run_id))
    assert view.checks is False and view.blank_rows == 3 and view.lines == []
    t = q.load_template(s.con, n["tid"])
    for kind in ex.CHECKED_ONLY:                                              # NCK-12, defence behind the UI
        req = ex.prefill(kind, t.export, template_id=t.id, client="Acme Traders", template=t.name,
                         run_id=c.run_id, run_label=c.label)
        with pytest.raises(runs.RunProblem, match="without checks"):
            run_job(s.runner, lambda ctx: runs.export_items(ctx, s.folder, req))
        with pytest.raises(ValueError):
            ex.prefill(kind, t.export, template_id=t.id, client="Acme Traders", template=t.name, run_id=c.run_id,
                       run_label=c.label, checks=False)
    summary = run_job(s.runner, lambda ctx: manage.run_delete_summary(ctx, c.run_id))
    assert "The issue list" not in summary.items
    n["committed"] = c.run_id


@spec("AC-NCK-5", "NCK-5", "RUN-7", "IN-15")
def test_file_errors_mapping_and_duplicate_warning_still_apply(n, fixtures_dir, tmp_path):
    s, fx = n["s"], n["fx"]
    t = q.load_template(s.con, n["tid"])
    sess = RunSession(s.folder, t, workers=0)
    rows = run_job(s.runner, lambda ctx: sess.add_files(ctx, [fixtures_dir / "Sales_Protected.xlsx"]))
    assert rows[0].status == "error" and sess.files_blockers()                # password file blocks
    with pytest.raises(RunBlocked):
        sess.files_next()
    extra = tmp_path / "Purchases_Extra.csv"
    lines = (fx / F1).read_text(encoding="utf-8").splitlines()[:5]
    extra.write_text("\n".join(f"{x},{'Remarks' if i == 0 else 'ok'}" for i, x in enumerate(lines)) + "\n",
                     encoding="utf-8")
    sess = RunSession(s.folder, t, workers=0)
    run_job(s.runner, lambda ctx: sess.add_files(ctx, [extra]))
    plan = sess.files_next()
    assert not plan.skip and [k for k, *_ in plan.undecided()] == ["extra"]   # a new header needs a decision
    if "committed" not in n:
        pytest.skip("needs test_commit_without_checks")
    sess = RunSession(s.folder, t, workers=0)
    rows = run_job(s.runner, lambda ctx: sess.add_files(ctx, [fx / F1]))
    assert rows[0].duplicate_of and sess.files_blockers() == [rows[0].message]   # RUN-7 warning


@spec("AC-NCK-10", "NCK-14")
def test_analysis_over_runs_with_and_without_checks(tmp_path, tpl_n_small):
    fx, _m = tpl_n_small
    s = open_storage(tmp_path)
    try:
        tid = q.create_template(s.con, tpl_n.template(q.insert_client(s.con, "Acme Traders")))
        a = commit_unchecked(s, load_tpl_n(s, tid, fx, [F1]))
        t = q.load_template(s.con, tid)
        t.checks = True
        run_job(s.runner, lambda ctx: manage.save_template(ctx, t))
        sess = RunSession(s.folder, q.load_template(s.con, tid), workers=0)
        run_job(s.runner, lambda ctx: sess.add_files(ctx, [fx / F2]))
        sess.files_next()
        run_job(s.runner, sess.validate)
        assert sess.validation.errors > 0                                     # the text values are now errors
        run_job(s.runner, lambda ctx: sess.leave_validate(ctx, "Text values left out"))
        b = commit_unchecked(s, sess, "Text values left out")
        assert q.run_details(s.con, b.run_id)["checks"] is True
        t = q.load_template(s.con, tid)
        defn = Definition(tid, [], [Group(STATE)], cards(FlatMeasure(d.ROWS, d.COUNT), FlatMeasure(TAXABLE, d.SUM),
                                                    FlatMeasure(DATE_, d.COUNT)))

        def rows_of(*ids):
            def work(ctx):
                out = analyses.run(ctx, s.folder, defn, t, list(ids))
                try:
                    from sankalan.query import layer
                    return {r[1]: r[2:5] for r in layer.rows(ctx.cursor(), out.result, subtotals=False, cap=None,
                                                             limit=10 ** 6) if r[1] is not None}
                finally:
                    analyses.drop_results(ctx, [out.result])
            return run_job(s.runner, work)
        both, one, two = rows_of(a.run_id, b.run_id), rows_of(a.run_id), rows_of(b.run_id)
        assert set(both) == set(one) == set(two) and len(both) == 4
        for k in both:
            assert both[k] == tuple(x + y for x, y in zip(one[k], two[k])), k
    finally:
        s.close()
