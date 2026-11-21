"""Feature D in the run session: choosing sheets for a file (Feature Spec A2 5, 10.5; Tech spec A2 7.2, 7.5).

Template: TPL-A's columns with Sheets to read = Sales and Sales Returns; files S01-S04 from the fixture pack."""
import shutil

import pytest

from conftest import open_storage, run_job, spec, tpl_a_columns
from sankalan.ingest import probe as P
from sankalan.model.rule import with_type_rules
from sankalan.model.template import SourceSettings, Template
from sankalan.query import catalogue as q
from sankalan.run.pipeline import RunBlocked, RunSession

CENTRAL, EAST, WEST = "Sales_Nov-2026_Central.xlsx", "Sales_Nov-2026_East.xlsx", "Sales_Nov-2026_West.xlsx"
RENAMED = "Sales_Nov-2026_Central_Renamed.xlsx"
PLENTY = 10 * 1024 ** 3


@pytest.fixture(scope="module")
def s(tmp_path_factory):
    st = open_storage(tmp_path_factory.mktemp("sheets"))
    yield st
    st.close()


def template(s) -> str:
    cols = tpl_a_columns()
    return q.create_template(s.con, Template("", q.insert_client(s.con, f"Client {len(q.client_ids(s.con))}"),
                                             "Sales Register", SourceSettings(sheets="name",
                                                                              sheet_names=["Sales", "Sales Returns"]),
                                             cols, with_type_rules(cols, [])))


def session(s, tid, fx, *names) -> RunSession:
    sess = RunSession(s.folder, q.load_template(s.con, tid), workers=0)
    if names:
        run_job(s.runner, lambda ctx: sess.add_files(ctx, [fx / n for n in names]))
    return sess


def rows_of(sess):
    return [(f.file_name, f.sheet, f.status, f.problem) for f in sess.files]


@spec("AC-SHT-1", "SHT-2", "T46")
def test_can_choose_sheets(s, fixtures_dir):
    tid = template(s)
    sess = session(s, tid, fixtures_dir, CENTRAL, WEST, "Sales_Nov-2026_Central.xlsb", "Sales_Nov-2026_Central.xls",
                   "Sales_Macro.xlsm", "Conversion_Values.csv", "Sales_Protected.xlsx")
    can = {f.file_name: sess.can_choose_sheets(f.path) for f in sess.files}
    assert can == {CENTRAL: True, WEST: True, "Sales_Nov-2026_Central.xlsb": True, "Sales_Nov-2026_Central.xls": True,
                   "Sales_Macro.xlsm": True,                     # also when the file matches the rule (D65)
                   "Conversion_Values.csv": False, "Sales_Protected.xlsx": False}
    held = P.FileSheet(str(fixtures_dir / "Open.xlsx"), "Open.xlsx", P.ERROR, problem="locked", kind="xlsx",
                       sheets=[P.SheetEntry("Sales", True, 10)])
    sess.files.append(held)                                     # open in Excel: no sheet list to trust
    assert not sess.can_choose_sheets(held.path)


@spec("AC-SHT-3", "AC-SHT-4", "SHT-5", "SHT-7", "SHT-9", "AC-SHT-8", "AC-SHT-7", "SHT-10")
def test_choose_recheck_remove_and_commit(s, fixtures_dir, tmp_path):
    tid = template(s)
    central = tmp_path / CENTRAL
    shutil.copyfile(fixtures_dir / CENTRAL, central)
    sess = RunSession(s.folder, q.load_template(s.con, tid), workers=0)
    run_job(s.runner, lambda ctx: sess.add_files(ctx, [central, fixtures_dir / EAST, fixtures_dir / WEST]))
    assert [r[3] for r in rows_of(sess)][:2] == ["sheet", "sheet"] and sess.files_blockers()
    assert sess.dialog_ticks(central) == []                             # no match: nothing ticked (SHT-5)
    assert sess.dialog_ticks(fixtures_dir / EAST) == ["Sales"]          # AC-SHT-4
    assert sess.dialog_ticks(fixtures_dir / WEST) == ["Sales", "Sales Returns"]
    with pytest.raises(RunBlocked):
        run_job(s.runner, lambda ctx: sess.choose_sheets(ctx, central, []))
    run_job(s.runner, lambda ctx: sess.choose_sheets(ctx, central, ["Returns Nov", "Sales Nov"]))
    assert sess.sheet_choice == {str(central): ["Sales Nov", "Returns Nov"]}
    assert rows_of(sess)[:2] == [(CENTRAL, "Sales Nov", "ready", ""), (CENTRAL, "Returns Nov", "ready", "")]
    assert sess.dialog_ticks(central) == ["Sales Nov", "Returns Nov"]
    run_job(s.runner, lambda ctx: sess.choose_sheets(ctx, fixtures_dir / EAST, ["Sales"]))
    assert not sess.files_blockers()
    run_job(s.runner, lambda ctx: sess.recheck_files(ctx))               # the choice is kept (SHT-9)
    assert [r[1] for r in rows_of(sess)] == ["Sales Nov", "Returns Nov", "Sales", "Sales", "Sales Returns"]
    plan = sess.files_next()                                             # headers match: Mapping skipped
    assert plan.skip
    # AC-SHT-6: Sales Nov renamed at source → Re-check → Sheet not found, Returns Nov still ticked
    shutil.copyfile(fixtures_dir / RENAMED, central)
    run_job(s.runner, lambda ctx: sess.recheck_files(ctx, [central]))
    assert rows_of(sess)[0] == (CENTRAL, "", "error", "sheet") and sess.mapping is None
    assert sess.file_rows(central)[0].message == "Sheets found: Sales November, Returns Nov"
    assert sess.dialog_ticks(central) == ["Returns Nov"]
    run_job(s.runner, lambda ctx: sess.choose_sheets(ctx, central, ["Sales November", "Returns Nov"]))
    sess.files_next()
    sess.mapping_next()
    run_job(s.runner, sess.validate)
    run_job(s.runner, lambda ctx: sess.leave_validate(ctx, None))
    run_job(s.runner, lambda ctx: sess.check_totals(ctx, fault={}))
    job = s.runner.run("commit", lambda ctx: sess.commit(ctx, "", free_bytes=PLENTY), cancellable=False)
    assert job.error is None, job.error
    run = q.run_details(s.con, job.result.run_id)
    assert [(f["file_name"], f["sheet"], f["sheets_chosen"]) for f in run["files"]] == [
        (CENTRAL, "Sales November", True), (CENTRAL, "Returns Nov", True), (EAST, "Sales", True),
        (WEST, "Sales", False), (WEST, "Sales Returns", False)]
    data = s.folder.run_dir(tid, job.result.run_id) / "data.parquet"
    sheets = [r[0] for r in s.con.execute(f"SELECT DISTINCT _src_sheet FROM read_parquet('{data.as_posix()}') "
                                          f"WHERE _src_file = 0 ORDER BY 1").fetchall()]
    assert sheets == ["Sales November"]                                  # Source Sheet: the sheet's own name
    t = q.load_template(s.con, tid)                                      # AC-SHT-7: the template is unchanged
    assert (t.source.sheets, t.source.sheet_names) == ("name", ["Sales", "Sales Returns"])
    again = session(s, tid, fixtures_dir, EAST)
    assert rows_of(again) == [(EAST, "", "error", "sheet")]               # a later run starts from the rule


@spec("AC-SHT-5", "SHT-8", "SHT-9")
def test_header_not_found_then_remove_and_add_again(s, fixtures_dir):
    tid = template(s)
    sess = session(s, tid, fixtures_dir, WEST)
    run_job(s.runner, lambda ctx: sess.choose_sheets(ctx, fixtures_dir / WEST, ["Cover"]))
    assert rows_of(sess) == [(WEST, "Cover", "error", "header")]
    assert not sess.can_choose_sheets(fixtures_dir / WEST)              # only Exclude file
    sess.remove_file(fixtures_dir / WEST)
    assert sess.sheet_choice == {} and sess.files == []
    run_job(s.runner, lambda ctx: sess.add_files(ctx, [fixtures_dir / WEST]))
    assert [r[1] for r in rows_of(sess)] == ["Sales", "Sales Returns"]   # starts from the rule again
    assert sess.can_choose_sheets(fixtures_dir / WEST)


@spec("AC-SHT-9", "SHT-10", "MAP-4")
def test_new_header_in_a_chosen_sheet_opens_mapping(s, fixtures_dir, tmp_path):
    import generate as g
    tid = template(s)
    path = tmp_path / CENTRAL
    returns = [r + (["Reason"] if i == 0 else ["Damaged"]) for i, r in enumerate(g.tpl(g.f00_rows(50, 100300, 2026,
                                                                                                   11)))]
    g.write_xlsx(path, [g.Sheet("Sales Nov", g.tpl(g.f00_rows(300, 100000, 2026, 11))),
                        g.Sheet("Returns Nov", returns)])
    sess = session(s, tid, fixtures_dir)
    run_job(s.runner, lambda ctx: sess.add_files(ctx, [path]))
    run_job(s.runner, lambda ctx: sess.choose_sheets(ctx, path, ["Sales Nov", "Returns Nov"]))
    plan = sess.files_next()
    assert not plan.skip
    sheets = {x.key: x.sheet for x in sess.mapping.sheets}
    assert [(k, sheets[a]) for k, a, _b in plan.undecided()] == [("extra", "Returns Nov")]   # only that column
