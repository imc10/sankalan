"""Phase 9: New run wizard (4.1 to 4.5) and the Run screen (5.1), driven through the screens on the generated fixture
pack (offscreen, real storage). The TPL-A run sequence R-0001 to R-0007 runs in file order on one module storage,
with the discarded runs in between, as in the Test Cases sheet (RUNF, RUNM, RUNV, RUNO, RUNC, C6). Files are read
in the Job's thread (``WORKERS = 0``); the reader workers are covered by the ingestion tests."""
import pytest

from conftest import OVERRIDE_REASON, open_storage, settle_window, spec, tpl_a_template
from sankalan.model.rule import ERROR as SEV_ERROR, WARNING as SEV_WARNING
from sankalan.model.run import STATUS_OVERRIDE
from sankalan.query import catalogue as q
from sankalan.run import pipeline as pl
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens import new_run as nrui
from sankalan.ui.screens.new_run import COMMIT, FILES, MAPPING, OUTPUTS, VALIDATE, NewRunScreen
from sankalan.ui.screens.run import ISSUES, OUTPUTS as RUN_OUTPUTS, SOURCES, RunScreen
from sankalan.ui.screens.template import TemplateScreen
from sankalan.ui.window import MainWindow

INV, DATE_, CUST, GSTIN, STATE, TAXABLE, RATE, TAX = (f"c00{i}" for i in range(1, 9))
PLENTY = 50 * 1024 ** 3


def settle(qtbot, w, timeout=60_000):
    settle_window(qtbot, w, timeout)


@pytest.fixture(autouse=True)
def inline_reader(monkeypatch):
    monkeypatch.setattr(nrui, "WORKERS", 0)


@pytest.fixture(autouse=True)
def discard_on_close(monkeypatch):
    """pytest-qt closes the window before fixtures tear down; an open wizard would ask "Leave and discard this
    run?". Tests that answer prompts themselves (``answers``) replace this hook."""
    from sankalan.ui.dialogs import base
    monkeypatch.setattr(base, "answer_hook", lambda dlg: "discard")


@pytest.fixture(scope="module")
def tpla(tmp_path_factory, fixtures_dir):
    s = open_storage(tmp_path_factory.mktemp("runs"))
    acme = q.insert_client(s.con, "Acme Traders")
    tid = q.create_template(s.con, tpl_a_template(acme))
    yield {"s": s, "tid": tid, "client": acme, "fx": fixtures_dir, "runs": {}}
    s.close()


@pytest.fixture
def win(app, qtbot, tpla):
    s = tpla["s"]
    w = MainWindow(JobBridge(s.runner), s)
    qtbot.addWidget(w)
    w.resize(1366, 768)
    w.show()
    yield w
    w.bridge.wait_all(30)
    w.bridge.poll()


def wizard(qtbot, w, tpla, *files, free=PLENTY) -> NewRunScreen:
    assert w.go("new_run", template_id=tpla["tid"], name="Sales Register")
    settle(qtbot, w)
    wz = w.current
    assert isinstance(wz, NewRunScreen)
    assert wz.session is not None
    wz.start_info.free_bytes = free
    wz.free_bytes_for_commit = free
    wz.files_step.load()
    if files:
        assert wz.add_files([tpla["fx"] / f for f in files])
        settle(qtbot, w)
    return wz


def nxt(qtbot, wz, expect=None):
    wz.next()
    settle(qtbot, wz.window_)
    if expect is not None:
        assert wz.step == expect, (wz.step, [b.plain_text for b in wz.banners()])


def file_banners(wz):
    from sankalan.ui.widgets.banner import Banner
    return [b for b in wz.files_step.findChildren(Banner) if b.parent() is wz.files_step]


def to_commit(qtbot, wz, reason=None):
    """From Validate (done) to the Commit step."""
    if reason is not None:
        dlg = wz.continue_despite_errors()
        dlg.reason.setPlainText(reason)
        dlg.ok.click()
    else:
        wz.next()
    settle(qtbot, wz.window_)
    if wz.step == OUTPUTS:
        assert wz.session.outputs_done, wz.outputs_step.statuses()
        nxt(qtbot, wz, COMMIT)
    settle(qtbot, wz.window_)
    assert wz.step == COMMIT


def commit(qtbot, wz) -> RunScreen:
    w = wz.window_
    assert wz.commit_step.can_commit(), wz.commit_step.blocker_list()
    assert wz.commit()
    settle(qtbot, w)
    sc = w.current
    assert isinstance(sc, RunScreen), type(sc)
    settle(qtbot, w)
    return sc


# ---------------------------------------------------------------------------------------------- R-0001 (F02)
@spec("RUNF-01", "RUNF-02", "RUNF-03", "IN-1", "IN-3", "IN-11")
def test_add_files_grid_and_refusals(win, qtbot, tpla):
    wz = wizard(qtbot, win, tpla, "Sales_Oct.xlsx", "Sales_Macro.xlsm")
    rows = wz.files_step.rows()
    assert [r[0] for r in rows] == ["Sales_Oct.xlsx", "Sales_Macro.xlsm"]
    size = (tpla["fx"] / "Sales_Oct.xlsx").stat().st_size
    from sankalan import formats
    assert rows[0] == ["Sales_Oct.xlsx", "Sales", formats.size(size), "Row 1", "≈5,000", "Ready"]
    assert rows[1][5] == "Ready"                                    # .xlsm accepted
    wz.remove_file(str(tpla["fx"] / "Sales_Macro.xlsm"))           # ✕
    assert [r[0] for r in wz.files_step.rows()] == ["Sales_Oct.xlsx"]
    assert wz.add_files([tpla["fx"] / "Sales_Notes.txt", tpla["fx"] / "Run_Folder"])
    settle(qtbot, win)
    refused = wz.files_step.refused.text()
    assert "only .xlsx, .xlsm, .xlsb, .xls and .csv files can be added" in refused
    assert "Folders can't be added" in refused
    assert [r[0] for r in wz.files_step.rows()] == ["Sales_Oct.xlsx"]
    assert wz.next_button.isEnabled()


@spec("RUNF-12", "RUNV-01", "RUNO-01", "RUNO-02", "RUNC-01", "RUNC-04", "RUNC-05", "TPL-6", "DO-7", "RUN-13")
def test_r0001_clean_run(win, qtbot, tpla):
    wz = wizard(qtbot, win, tpla, "Sales_Oct.xlsx")
    nxt(qtbot, wz, VALIDATE)                                        # Mapping skipped (RUNF-12)
    assert wz.steps.state(MAPPING) == "skipped"
    assert wz.validate_step.tile_values() == {"errors": "0", "warnings": "0", "rows": "5,000", "hidden": "0"}
    assert wz.validate_step.result_banner.kind == "success"
    assert wz.next_button.isEnabled() and not wz.override_button.isVisible()
    nxt(qtbot, wz, OUTPUTS)
    settle(qtbot, win)
    assert wz.outputs_step.statuses() == [("State-wise sales", pl.DONE), ("Latest month by GST rate", pl.DONE)]
    assert not [b for b in wz.outputs_step.findChildren(type(wz.next_button)) if b.text().startswith("Export")]
    assert wz.outputs_step.no_export.text() == "Export is available after commit"
    rows = wz.outputs_step.table.rows()
    assert rows[0] == ["Delhi", "1,903,437.50", "240,655.00", "1,250"]
    assert rows[-1] == ["Grand total", "7,536,875.00", "956,722.50", "5,000"]
    wz.outputs_step.select(1)
    settle(qtbot, win)
    rows = wz.outputs_step.table.rows()
    assert ["Oct-2026", "0", "1,486,875.00"] in rows and ["Oct-2026", "Total", "7,536,875.00"] in rows
    wz.outputs_step.subtotals.setChecked(False)
    settle(qtbot, win)
    assert ["Oct-2026", "Total", "7,536,875.00"] not in wz.outputs_step.table.rows()
    nxt(qtbot, wz, COMMIT)
    settle(qtbot, win)
    assert wz.commit_step.totals_rows() == [["Taxable Value", "7,536,875.00", "7,536,875.00", "0.00"],
                                            ["Tax Amount", "956,722.50", "956,722.50", "0.00"]]
    assert wz.commit_button.isEnabled() and wz.commit_button.text() == "Commit R-0001"
    wz.commit_step.comment.setPlainText("x" * 501)                  # RUNC-04
    assert len(wz.commit_step.comment.toPlainText()) == 500 and wz.commit_step.counter.text() == "500 / 500"
    wz.commit_step.comment.setPlainText("")
    assert wz.commit_button.isEnabled()                             # optional
    wz.commit_step.comment.setPlainText("October sales, first load")
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0001"
    assert any(b.kind == "success" and "R-0001 committed: 5,000 rows and 2 outputs saved." in b.plain_text
               for b in sc.banners())
    assert q.list_runs(tpla["s"].con, tpla["tid"])[-1].label == "R-0001"
    assert not any(tpla["s"].folder.staging_root.iterdir())
    tpla["runs"]["R-0001"] = sc.run_id


class _HeldOpen:
    """Hold a file the way Excel does: open for read and write, other programs may only read."""

    def __init__(self, path):
        import ctypes
        from ctypes import wintypes
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32.CreateFileW.restype = wintypes.HANDLE
        self.k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                         wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.h = self.k32.CreateFileW(str(path), 0x80000000 | 0x40000000, 0x1, None, 3, 0x80, None)
        assert self.h not in (None, wintypes.HANDLE(-1).value)

    def close(self):
        self.k32.CloseHandle(self.h)


def by_name(wz, name):
    return [r for r in wz.files_step.rows() if r[0] == name]


def job_ctx(tpla):
    """A Job context for calling Job work from a test on the main thread while the runner is idle."""
    class Ctx:
        cancel_requested = False

        def cursor(self):
            return tpla["s"].con

        def set_stage(self, *a, **k):
            pass

        def set_rows(self, *a, **k):
            pass

        add_rows = set_rows

        def check_cancelled(self):
            pass

        def on_abort(self, fn):
            pass

        def on_cancel(self, fn):
            pass

        def set_cancellable(self, v):
            pass
    return Ctx()


def grid(qtbot, view):
    """Every row of an issue grid (pages fetched as the view would)."""
    m = view.model
    qtbot.waitUntil(lambda: (view.screen.bridge.poll() or True) and not m.loading, timeout=20_000)
    for r in range(m.rowCount()):
        m.data(m.index(r, 0))
    qtbot.waitUntil(lambda: (view.screen.bridge.poll() or True) and not m.loading, timeout=20_000)
    return [m.row_values(r) for r in range(m.rowCount())]


def table_rows_of(t):
    from sankalan.ui.screens.run import table_rows
    return table_rows(t)


@spec("RUNF-05", "RUNF-06", "RUNF-07", "RUNF-08", "RUNF-09", "RUNF-10", "IN-9", "IN-10", "IN-15")
def test_files_in_error_exclude_and_recheck(win, qtbot, tpla, tmp_path):
    import shutil
    import sys
    fx = tpla["fx"]
    locked = tmp_path / "Sales_Locked.xlsx"
    shutil.copyfile(fx / "Sales_Locked.xlsx", locked)
    (tmp_path / "~$Sales_Locked.xlsx").write_bytes(b"owner")
    wz = wizard(qtbot, win, tpla, "Sales_Macro.xlsm", "Sales_Protected.xlsx", "Sales_NoHeader.xlsx",
                "Sales_WrongSheet.xlsx")
    assert wz.add_files([fx / "Sales_Macro.xlsm"])                     # RUNF-10: same path again
    settle(qtbot, win)
    held = _HeldOpen(locked) if sys.platform == "win32" else None
    try:
        assert wz.add_files([locked, tmp_path / "~$Sales_Locked.xlsx"])
        settle(qtbot, win)
    finally:
        if held is not None:
            held.close()
    status = {r[0]: r[5] for r in wz.files_step.rows()}
    assert [r[5] for r in by_name(wz, "Sales_Macro.xlsm")] == ["Ready", "Skipped"]
    assert status["Sales_Protected.xlsx"] == "Can't read" and status["Sales_NoHeader.xlsx"] == "Can't read"
    assert status["Sales_WrongSheet.xlsx"] == "Can't read" and status["~$Sales_Locked.xlsx"] == "Skipped"
    texts = [b.plain_text for b in file_banners(wz)]
    assert "Sales_Protected.xlsx is password-protected. Remove the password at source, or exclude the file." in texts
    assert "Sheet Sales not found." in texts
    if held is not None:
        assert "Sales_Locked.xlsx is open in another program. Close it, then Re-check." in texts
    assert all(set(b.buttons) == {"Exclude file", "Re-check"} for b in file_banners(wz) if b.kind == "error")
    assert not wz.next_button.isEnabled()
    assert wz.footer.text() == f"Exclude or fix {4 if held else 3} files to continue"
    if held is not None:                                             # RUNF-06: Excel closed, Re-check → Ready
        banner = next(b for b in file_banners(wz) if "Sales_Locked.xlsx" in b.plain_text)
        banner.buttons["Re-check"].click()
        settle(qtbot, win)
        assert by_name(wz, "Sales_Locked.xlsx")[0][5] == "Ready", [(f.file_name, f.status, f.message) for f in wz.session.files]
        wz.remove_file(str(locked))
    for _name in ("Sales_Protected.xlsx", "Sales_NoHeader.xlsx", "Sales_WrongSheet.xlsx"):    # RUNF-09
        assert not wz.next_button.isEnabled()
        banner = next(b for b in file_banners(wz) if b.kind == "error")
        banner.buttons["Exclude file"].click()
    assert wz.next_button.isEnabled()
    assert [f.file_name for f in wz.session.readable_files] == ["Sales_Macro.xlsm"]


@spec("RUNF-11", "RUN-7")
def test_duplicate_contents_remove_and_load_anyway(win, qtbot, tpla):
    wz = wizard(qtbot, win, tpla, "Sales_Oct_copy.xlsx")
    (banner,) = [b for b in file_banners(wz) if b.kind == "warning"]
    loaded = q.list_runs(tpla["s"].con, tpla["tid"])[0].loaded_on
    assert "R-0001" in banner.plain_text and f"{loaded:%d-%m-%Y}" in banner.plain_text
    assert wz.files_step.rows()[0][5] == "Already loaded" and not wz.next_button.isEnabled()
    assert banner.buttons["Remove file"].isEnabled(), (win.bridge.busy, wz.job)
    banner.buttons["Remove file"].click()
    assert wz.files_step.rows() == []
    assert wz.add_files([tpla["fx"] / "Sales_Oct_copy.xlsx"])
    settle(qtbot, win)
    next(b for b in file_banners(wz) if b.kind == "warning").buttons["Load anyway"].click()
    assert wz.files_step.rows()[0][5] == "Ready" and wz.next_button.isEnabled()


@spec("RUNF-14", "C1-10")
def test_low_disk_warning(win, qtbot, tpla):
    wz = wizard(qtbot, win, tpla, "Sales_Oct.xlsx", free=3 * 1024 ** 3)
    assert any(b.kind == "warning" and "free on the data folder's drive" in b.plain_text for b in file_banners(wz))


# ---------------------------------------------------------------------------------------------- R-0002 (F03)
@spec("RUNF-04", "RUNV-02", "RUNC-03", "C6-03", "C6-07", "IN-13", "T14")
def test_r0002_hidden_and_blank_rows(win, qtbot, tpla):
    from sankalan import formats
    wz = wizard(qtbot, win, tpla, "Sales_Nov.xlsx")
    (row,) = wz.files_step.rows()
    assert row[:2] == ["Sales_Nov.xlsx", "Sales"] and row[3] == "Row 2" and row[5] == "Ready"
    assert 'Hidden sheet "Old" in Sales_Nov.xlsx is skipped.' in wz.files_step.summary.text()
    assert "25 hidden rows in Sales_Nov.xlsx, Sales are skipped." in wz.files_step.summary.text()
    nxt(qtbot, wz, VALIDATE)
    assert wz.validate_step.tile_values() == {"errors": "0", "warnings": "0", "rows": "4,010",
                                              "hidden": "25 rows and 1 sheet (Old)"}
    to_commit(qtbot, wz)
    assert wz.commit_step.totals_rows() == [["Taxable Value", "6,029,500.00", "6,029,500.00", "0.00"],
                                            ["Tax Amount", "765,378.00", "765,378.00", "0.00"]]
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0002"
    fig = dict(sc.summary_tab.figures)
    assert fig["Rows read"] == "4,010" and fig["Rows loaded"] == "4,000"
    assert fig["Rows left out"] == "10 (rows with errors 0, later duplicates 0, blank rows 10)"
    assert fig["Hidden data skipped"] == "25 hidden rows and hidden sheet Old"
    sc.select_tab(SOURCES)
    (row,) = sc.sources_tab.rows()
    f03 = tpla["fx"] / "Sales_Nov.xlsx"
    assert row[:4] == ["Sales_Nov.xlsx", "Sales", str(f03.parent), formats.size(f03.stat().st_size)]
    assert row[5:] == ["Row 2", "4,000"] and row[4]
    assert sc.sources_tab.hidden.text() == ('Hidden data skipped: 25 hidden rows in Sales_Nov.xlsx, Sales; sheet '
                                            '"Old" in Sales_Nov.xlsx.')
    tpla["runs"]["R-0002"] = sc.run_id


# ---------------------------------------------------------------------------------------------- discarded F04 runs
RUNV03 = {("Not blank · Invoice No", "Error", 12), ("Character pattern · Invoice No", "Error", 8),
          ("Unique within the run · Invoice No", "Error", 6), ("Is a date · Invoice Date", "Error", 4),
          ("Text length · GSTIN", "Error", 10), ("Is a number · Taxable Value", "Error", 15),
          ("Number range · Taxable Value", "Error", 5), ("Allowed values · GST Rate", "Error", 6),
          ("Allowed values · State", "Warning", 25), ("Not blank · Customer", "Warning", 7)}


@spec("RUNV-03", "RUNV-04", "RUNV-05", "RUNV-07", "RUNV-09", "RUNV-12", "ISS-1", "ISS-2", "ISS-3", "VR-5", "TPL-8")
def test_f04_validate_issues_and_rules_for_this_run_only(win, qtbot, tpla, tmp_path):
    import threading
    from sankalan import exporting, runs
    wz = wizard(qtbot, win, tpla, "Sales_Errors.xlsx")
    nxt(qtbot, wz, VALIDATE)
    vs = wz.validate_step
    assert vs.tile_values() == {"errors": "66", "warnings": "32", "rows": "2,000", "hidden": "0"}
    assert vs.result_banner.kind == "error"
    rows = vs.issues.by_rule.rows()
    assert set(rows) == RUNV03 and [r[1] for r in rows] == ["Error"] * 8 + ["Warning"] * 2
    assert not wz.next_button.isEnabled() and wz.override_button.isVisible()
    # RUNV-04: order, row 214, duplicates name the first, Warning filter, sort
    g = grid(qtbot, vs.issues)
    assert len(g) == 98 and [r[2] for r in g] == sorted(r[2] for r in g)
    assert ("Sales_Errors.xlsx", "Sales", 214, "Taxable Value", "abc", "Is a number", "Error") in [r[:7] for r in g]
    assert next(r for r in g if r[2] == 705 and r[5] == "Unique within the run")[7].endswith(
        "same Invoice No as row 704")
    vs.issues.set_severity(SEV_WARNING)
    assert len(grid(qtbot, vs.issues)) == 32
    vs.issues.set_severity(None)
    vs.issues.model.sort(2, Qt_Descending())
    assert [r[2] for r in grid(qtbot, vs.issues)][:1] == [max(r[2] for r in g)]
    vs.issues.model.sort(2, Qt_Descending(False))
    # RUNV-05
    vs.issues.pick_rule("r3")
    assert [r[2] for r in grid(qtbot, vs.issues)] == [702, 703, 704, 705, 706, 707]
    assert vs.issues.filter_note.text() == "Unique within the run · Invoice No · showing all 6"
    # RUNV-07: the full issue list from Validate, before commit
    assert vs.export_issues()
    req = win.last_export
    assert req.kind == "issues" and req.file_name == "Acme Traders_Sales Register_R-0003_Issues.csv"
    items = runs.export_items(job_ctx(tpla), tpla["s"].folder, req)
    out = exporting.export(job_ctx(tpla), tpla["s"].paths.temp, items[0][0], tmp_path / "issues.csv", req.options)
    assert out.rows == 98
    text = (tmp_path / "issues.csv").read_text(encoding="utf-8-sig").splitlines()
    assert text[0] == "File,Sheet,Row,Column,Value,Rule,Severity,Message"
    assert any("Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number" in ln for ln in text)
    # RUNV-09: GST Rate allowed values + 15, for this run only
    dlg = vs.edit_rules()
    r9 = next(r for r in dlg.rules.rules if r.id == "r9")
    r9.settings = {"values": ["0", "5", "12", "15", "18", "28"]}
    dlg.rules._changed()
    dlg.apply.click()
    settle(qtbot, win)
    assert vs.tile_values()["errors"] == "60"
    assert not [r for r in vs.issues.by_rule.rows() if r[0] == "Allowed values · GST Rate"]
    t = q.load_template(tpla["s"].con, tpla["tid"])
    assert next(r for r in t.rules if r.id == "r9").settings["values"] == ["0", "5", "12", "18", "28"]
    # RUNV-12: Cancel during Validate returns to Files (Mapping was skipped) and keeps nothing
    sess = wz.session
    orig = sess.validate
    hold = threading.Event()

    def slow(ctx):
        res = orig(ctx)
        hold.set()
        while not ctx.cancel_requested:
            threading.Event().wait(0.01)
        ctx.check_cancelled()
        return res

    sess.validate = slow
    assert wz.recheck()
    assert hold.wait(30)
    wz.progress.cancel()
    settle(qtbot, win)
    assert wz.step == FILES and sess.staging is None
    assert not any(tpla["s"].folder.staging_root.iterdir())


def Qt_Descending(descending: bool = True):
    from PySide6.QtCore import Qt
    return Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder


@spec("RUNV-06", "ISS-2", "VR-4", "RUNC-09", "RUN-14")
def test_many_issues_first_10000_then_discard(win, qtbot, tpla, answers):
    wz = wizard(qtbot, win, tpla, "Sales_ManyIssues.csv")
    nxt(qtbot, wz, VALIDATE)
    vs = wz.validate_step
    assert ("Not blank · Customer", "Warning", 15000) in vs.issues.by_rule.rows()
    assert wz.next_button.isEnabled()
    vs.issues.pick_rule("r5")
    qtbot.waitUntil(lambda: (win.bridge.poll() or True) and not vs.issues.model.loading, timeout=20_000)
    assert vs.issues.model.total == 10_000
    assert vs.issues.filter_note.text() == "Not blank · Customer · showing the first 10,000 of 15,000"
    assert "first 10,000 issues of each rule" in vs.issues.limit_note.text()
    answers.append("stay")
    assert not win.open_area("clients")                              # 7.6 Stay keeps the run
    assert win.current is wz and wz.session.validation is not None
    answers.append("discard")
    assert win.open_area("clients")
    assert answers.asked[-1][0] == "Leave and discard this run?"
    settle(qtbot, win)
    assert not any(tpla["s"].folder.staging_root.iterdir())
    assert [r.label for r in q.list_runs(tpla["s"].con, tpla["tid"])] == ["R-0001", "R-0002"]


# ---------------------------------------------------------------------------------------------- R-0003 (F04 override)
@spec("RUNV-13", "RUNO-03", "RUNC-02", "RUNC-06", "RUNC-07", "C6-01", "C6-02", "C6-05", "C6-08", "T18")
def test_r0003_continue_despite_errors(win, qtbot, tpla):
    wz = wizard(qtbot, win, tpla, "Sales_Errors.xlsx")
    nxt(qtbot, wz, VALIDATE)
    dlg = wz.continue_despite_errors()
    assert dlg.windowTitle() == "Continue despite 66 errors?"
    assert any("63 rows with errors will be left out. R-0003 will be marked Committed with override." in
               lab.text() for lab in dlg.findChildren(type(dlg.title)))
    assert not dlg.ok.isEnabled()                                    # empty reason refused
    dlg.reason.setPlainText("   ")
    assert not dlg.ok.isEnabled()
    dlg.reason.setPlainText(OVERRIDE_REASON)
    dlg.ok.click()
    settle(qtbot, win)
    assert wz.step == OUTPUTS and wz.session.outputs_done
    settle(qtbot, win)
    assert wz.outputs_step.table.rows() == [
        ["Delhi", "739,448.00", "93,038.02", "480"], ["Goa", "28,075.00", "3,572.83", "25"],
        ["Gujarat", "725,157.00", "93,821.11", "476"], ["Karnataka", "734,282.00", "94,229.23", "480"],
        ["Maharashtra", "720,032.00", "90,333.16", "476"], ["Grand total", "2,946,994.00", "374,994.35", "1,937"]]
    wz.outputs_step.select(1)
    settle(qtbot, win)
    assert [r[1:] for r in wz.outputs_step.table.rows()[:5]] == [
        ["0", "578,776.25"], ["5", "583,835.25"], ["12", "590,089.00"], ["18", "594,117.25"], ["28", "600,176.25"]]
    nxt(qtbot, wz, COMMIT)
    settle(qtbot, win)
    cs = wz.commit_step
    assert cs.totals_rows() == [["Taxable Value", "2,986,623.75", "2,946,994.00", "39,629.75"],
                                ["Tax Amount", "381,662.10", "374,994.35", "6,667.75"]]
    assert cs.comment.toPlainText() == OVERRIDE_REASON
    assert cs.comment_label.text() == "Comment · required because errors were overridden"
    assert cs.summary["Errors"] == "66 · continued with a reason" and cs.summary["Rows to load"] == "1,937"
    cs.comment.setPlainText("")
    assert not wz.commit_button.isEnabled()
    cs.comment.setPlainText(OVERRIDE_REASON)
    assert wz.commit_button.text() == "Commit R-0003"               # RUNC-07: discarded runs used no Run ID
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0003" and sc.badge.text() == "Committed with override"
    assert sc.subtitle.text().startswith("Loaded ")
    assert "1 file · 1 sheet · 1,937 rows · 66 errors · 32 warnings" in sc.subtitle.text()
    assert [a.text() for a in sc.more_menu().actions() if a.text()] == ["Export issue list", "Export left-out rows",
                                                                         "Delete run"]
    fig = dict(sc.summary_tab.figures)
    assert fig["Files and sheets read"] == "1 file · 1 sheet" and fig["Rows read"] == "2,000"
    assert fig["Rows loaded"] == "1,937"
    assert fig["Rows left out"] == "63 (rows with errors 60, later duplicates 3, blank rows 0)"
    assert fig["Errors"] == "66 (continued with a reason)" and fig["Warnings"] == "32"
    assert table_rows_of(sc.summary_tab.totals)[0] == ["Taxable Value", "2,986,623.75", "2,946,994.00", "39,629.75"]
    assert sc.summary_tab.comment.toPlainText() == OVERRIDE_REASON and sc.summary_tab.comment.isReadOnly()
    sc.select_tab(ISSUES)
    g = grid(qtbot, sc.issues_tab)
    assert len(g) == 98 and set(sc.issues_tab.by_rule.rows()) == RUNV03
    sc.issues_tab.set_severity(SEV_WARNING)
    assert len(grid(qtbot, sc.issues_tab)) == 32
    tpla["runs"]["R-0003"] = sc.run_id
    run = q.list_runs(tpla["s"].con, tpla["tid"])[-1]
    assert run.status == STATUS_OVERRIDE and run.comment == OVERRIDE_REASON


# ---------------------------------------------------------------------------------------------- R-0004 (F08 mapping)
@spec("RUNM-01", "RUNM-02", "RUNM-03", "RUNM-04", "RUNM-05", "RUNM-08", "RUNV-08", "RUNO-04", "C6-04", "MAP-4",
      "MAP-5", "MAP-6", "MAP-7", "MAP-13")
def test_r0004_mapping_decisions(win, qtbot, tpla, answers):
    wz = wizard(qtbot, win, tpla, "Sales_Renamed_Headers.xlsx")
    nxt(qtbot, wz, MAPPING)
    ms = wz.mapping_step
    assert ms.table.horizontalHeaderItem(2).text() == "Sales_Renamed_Headers.xlsx · Sales"
    cells = {r[0]: r[2] for r in ms.grid_rows()}
    assert cells["Invoice No"] == "Choose…" and cells["State"] == "Choose…"
    assert cells["Invoice Date"] == "invoice_date" and cells["Customer"] == "CUSTOMER"
    assert cells["GSTIN"] == "G.S.T.I.N" and cells["GST Rate"] == "GST-Rate"
    assert cells["Taxable Value"] == "Taxable Value" and cells["Tax Amount"] == "Tax Amount"
    assert cells["“Remarks”"] == "Decide…"
    rows = ms.grid_rows()
    assert [rows[r][0] for r, c in sorted(ms.pending_cells())] == ["Invoice No", "State", "“Inv No”", "“Remarks”"]
    ms.show_item(("cell", STATE, 0))
    nxt(qtbot, wz, MAPPING)                                          # RUNM-02: focus goes to Invoice No
    assert ms.selected == ("cell", INV, 0) and ms.table.currentRow() == 0
    headers = wz.session.mapping._sheet[0].headers
    assert ms.decide("save_alias", position=headers.index("Inv No"))           # RUNM-03
    assert {r[0]: r[2] for r in ms.grid_rows()}["Invoice No"] == "Inv No · alias"
    assert ms.selected == ("cell", STATE, 0)
    assert 'Default output "State-wise sales" would show these rows as (Null).' in ms.warning.text()
    assert ms.decide("null")                                                    # RUNM-04
    assert ms.warning.text() == 'Default output "State-wise sales" will show these rows as (Null).'
    answers.append("stay")                                                      # RUNM-08
    assert not win.open_area("clients")
    assert win.current is wz and {r[0]: r[2] for r in ms.grid_rows()}["State"] == "(Null)"
    assert ms.footer_text() == "1 decision left"
    assert ms.decide("leave_out")                                               # RUNM-05
    assert {r[0]: r[2] for r in ms.grid_rows()}["“Remarks”"] == "Left out"
    nxt(qtbot, wz, VALIDATE)
    assert wz.validate_step.tile_values()["rows"] == "1,000" and wz.validate_step.tile_values()["errors"] == "0"
    assert not [r for r in wz.validate_step.issues.by_rule.rows() if r[0] == "Allowed values · State"]
    wz.next()
    settle(qtbot, win)
    assert wz.step == OUTPUTS
    settle(qtbot, win)
    assert wz.outputs_step.table.rows() == [["(Null)", "1,507,375.00", "191,344.50", "1,000"],
                                            ["Grand total", "1,507,375.00", "191,344.50", "1,000"]]
    nxt(qtbot, wz, COMMIT)
    settle(qtbot, win)
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0004"
    assert sc.summary_tab.decisions[:3] == [
        "Inv No mapped to Invoice No and saved as an alias (Sales_Renamed_Headers.xlsx · Sales)",
        "State left as null (Sales_Renamed_Headers.xlsx · Sales)",
        "Remarks left out (Sales_Renamed_Headers.xlsx · Sales)"]
    assert q.load_template(tpla["s"].con, tpla["tid"]).column(INV).aliases == ["Inv No"]
    tpla["runs"]["R-0004"] = sc.run_id


# ---------------------------------------------------------------------------------------------- R-0005 (F13)
@spec("RUNM-07", "RUNV-10", "MAP-7", "MAP-11", "VR-5", "TPL-7")
def test_r0005_add_column_and_save_rule_to_template(win, qtbot, tpla):
    wz = wizard(qtbot, win, tpla, "Sales_Dec_NewCol.xlsx")
    nxt(qtbot, wz, MAPPING)
    ms = wz.mapping_step
    assert ms.selected[0] == "extra"
    assert "A new column shows as null in the 4 earlier runs." in ms.hint.text()
    assert ms.decide("add", name="Branch", type_="Text")
    assert {r[0]: r[1:] for r in ms.grid_rows()}["Branch"] == ["Text", "Branch · new column"]
    nxt(qtbot, wz, VALIDATE)
    vs = wz.validate_step
    dlg = vs.edit_rules()
    dlg.rules.set_severity("r5", SEV_ERROR)
    dlg.save_to_template.setChecked(True)
    dlg.apply.click()
    settle(qtbot, win)
    t = q.load_template(tpla["s"].con, tpla["tid"])
    assert next(r for r in t.rules if r.id == "r5").severity == SEV_ERROR
    assert any("Rule changes saved to the template." in b.plain_text for b in wz.banners())
    to_commit(qtbot, wz)
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0005"
    dec = sc.summary_tab.decisions
    assert "Branch added as new column Branch (Text) (Sales_Dec_NewCol.xlsx · Sales)" in dec
    assert "Changed saved to the template: Not blank (Customer) · Error" in dec
    assert "No rule changes for this run only" in dec
    t = q.load_template(tpla["s"].con, tpla["tid"])
    assert t.columns[-1].name == "Branch" and t.columns[-1].type == "Text"
    tpla["runs"]["R-0005"] = sc.run_id


# ---------------------------------------------------------------------------------------------- R-0006, R-0007
@spec("RUNO-05", "C6-09", "T21", "RUN-9")
def test_r0006_no_dates_then_delete(win, qtbot, tpla):
    wz = wizard(qtbot, win, tpla, "Sales_NoDates.xlsx")
    nxt(qtbot, wz, VALIDATE)
    wz.next()
    settle(qtbot, win)
    assert wz.step == OUTPUTS
    settle(qtbot, win)
    assert wz.outputs_step.statuses() == [("State-wise sales", pl.DONE), ("Latest month by GST rate", pl.DONE)]
    assert wz.outputs_step.table.rows()[-1][1:] == ["753,687.50", "95,672.25", "500"]
    wz.outputs_step.select(1)
    settle(qtbot, win)
    assert wz.outputs_step.table.rows() == [] and "No dates in this run" in wz.outputs_step.info.text()
    assert wz.next_button.isEnabled()
    nxt(qtbot, wz, COMMIT)
    settle(qtbot, win)
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0006"
    run_dir = sc.view.run_dir
    sc.delete_run()
    settle(qtbot, win)
    dlg = sc.dialog
    assert dlg.windowTitle() == "Delete R-0006?" and dlg.listed == ["500 rows", "The issue list", "2 saved outputs"]
    dlg.understand.setChecked(True)
    dlg.delete_button.click()
    settle(qtbot, win)
    assert isinstance(win.current, TemplateScreen)
    assert any("R-0006 deleted." in b.plain_text for b in win.current.banners())
    assert not run_dir.exists()
    assert "R-0006" not in [r.label for r in q.list_runs(tpla["s"].con, tpla["tid"])]


@spec("RUNC-08", "RUNO-06", "DO-5", "T22")
def test_r0007_cancel_and_retry_an_output(win, qtbot, tpla, monkeypatch):
    import threading
    wz = wizard(qtbot, win, tpla, "Sales_Jan.xlsx")
    wz.next()
    settle(qtbot, win)
    assert wz.step == VALIDATE, wz.step                               # Branch is in the template now
    release = threading.Event()
    orig = pl.layer.write_output

    def slow(*a, **k):
        release.wait(30)
        return orig(*a, **k)

    monkeypatch.setattr(pl.layer, "write_output", slow)
    wz.next()
    qtbot.waitUntil(lambda: (win.bridge.poll() or True) and wz.job is not None
                    and wz.job.operation == "Generate outputs", timeout=20_000)
    wz.progress.cancel()
    release.set()
    settle(qtbot, win)
    assert [s for _n, s in wz.outputs_step.statuses()] == [pl.CANCELLED, pl.CANCELLED]
    assert not wz.outputs_step.retry_button.isHidden() and not wz.next_button.isEnabled()
    assert "Retry" in wz.outputs_step.buttons[0].text()
    monkeypatch.setattr(pl.layer, "write_output", orig)
    wz.outputs_step.retry_button.click()
    settle(qtbot, win)
    assert [s for _n, s in wz.outputs_step.statuses()] == [pl.DONE, pl.DONE] and wz.next_button.isEnabled()
    nxt(qtbot, wz, COMMIT)
    settle(qtbot, win)
    assert wz.commit_button.text() == "Commit R-0007"
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0007"


# ---------------------------------------------------------------------------------------------- Run screen
@spec("C6-06", "C6-10", "DO-6", "DO-7", "EXP-1", "T19")
def test_run_screen_outputs_and_exports(win, qtbot, tpla, tmp_path):
    from sankalan import exporting, runs
    assert win.go("run", run_id=tpla["runs"]["R-0001"], template_id=tpla["tid"])
    settle(qtbot, win)
    sc = win.current
    settle(qtbot, win)
    assert [c.label for c in sc.crumbs()] == ["Clients", "Acme Traders", "Sales Register", "R-0001"]
    assert sc.badge.text() == "Committed"
    sc.select_tab(RUN_OUTPUTS)
    settle(qtbot, win)
    ot = sc.outputs_tab
    assert ot.table.rows()[-1] == ["Grand total", "7,536,875.00", "956,722.50", "5,000"]   # never recalculated
    ot.select(1)
    settle(qtbot, win)
    assert ["Oct-2026", "Total", "7,536,875.00"] in ot.table.rows()
    ot.subtotals.setChecked(False)
    settle(qtbot, win)
    assert ["Oct-2026", "Total", "7,536,875.00"] not in ot.table.rows()
    ot.export_button.click()
    req = win.last_export
    assert (req.kind, req.output, req.subtotals) == ("output", 2, False)
    assert req.file_name == "Acme Traders_Sales Register_R-0001_Latest month by GST rate.csv"
    ot.export_all_button.click()
    req = win.last_export
    items = runs.export_items(job_ctx(tpla), tpla["s"].folder, req)
    dest = tmp_path / "all"
    dest.mkdir()
    exporting.export_many(job_ctx(tpla), tpla["s"].paths.temp, [(qq, dest / n) for qq, n in items], req.options)
    assert sorted(p.name for p in dest.iterdir()) == [
        "Acme Traders_Sales Register_R-0001_Latest month by GST rate.csv",
        "Acme Traders_Sales Register_R-0001_State-wise sales.csv"]
    sc.export("data")
    assert win.last_export.kind == "data" and win.last_export.run_id == sc.run_id
    data = runs.export_items(job_ctx(tpla), tpla["s"].folder, win.last_export)
    out = exporting.export(job_ctx(tpla), tpla["s"].paths.temp, data[0][0], tmp_path / "data.csv", req.options)
    assert out.rows == 5000


@spec("T19", "EXP-4", "ISS-4")
def test_run_screen_left_out_and_issue_exports(win, qtbot, tpla, tmp_path):
    from sankalan import exporting, runs
    assert win.go("run", run_id=tpla["runs"]["R-0003"], template_id=tpla["tid"])
    settle(qtbot, win)
    sc = win.current
    sc.export("left_out")
    req = win.last_export
    items = runs.export_items(job_ctx(tpla), tpla["s"].folder, req)
    out = exporting.export(job_ctx(tpla), tpla["s"].paths.temp, items[0][0], tmp_path / "left.csv", req.options)
    assert out.rows == 63
    sc.export("issues")
    items = runs.export_items(job_ctx(tpla), tpla["s"].folder, win.last_export)
    out = exporting.export(job_ctx(tpla), tpla["s"].paths.temp, items[0][0], tmp_path / "issues.csv", req.options)
    assert out.rows == 98


@spec("C4-04", "UX-9")
def test_template_runs_grid_opens_the_run(win, qtbot, tpla):
    win.go("template", template_id=tpla["tid"], name="Sales Register")
    settle(qtbot, win)
    ts = win.current
    labels = [f"R-{r[0]:04d}" for r in ts.runs_tab.visible_rows()]
    assert labels == ["R-0007", "R-0005", "R-0004", "R-0003", "R-0002", "R-0001"]
    ts.runs_tab.open_row(labels.index("R-0004"))
    settle(qtbot, win)
    assert isinstance(win.current, RunScreen) and win.current.view.label == "R-0004"


# ---------------------------------------------------------------------------------------------- TPL-C, TPL-D
@spec("RUNO-07", "DO-4")
def test_tpl_c_outputs_step_skipped(win, qtbot, tpla):
    from conftest import tpl_c_columns
    from sankalan.model.rule import Rule, with_type_rules
    from sankalan.model.template import SourceSettings, Template
    cols = tpl_c_columns()
    rules = [Rule(r.id, r.column_id, r.type, r.settings, SEV_WARNING) for r in with_type_rules(cols, [])]
    tid = q.create_template(tpla["s"].con, Template("", tpla["client"], "Conversion check",
                                                    SourceSettings(sheets="first"), cols, rules))
    assert win.go("new_run", template_id=tid, name="Conversion check")
    settle(qtbot, win)
    wz = win.current
    wz.free_bytes_for_commit = PLENTY
    wz.add_files([tpla["fx"] / "Conversion_Values.csv"])
    settle(qtbot, win)
    nxt(qtbot, wz, VALIDATE)
    assert wz.next_button.text() == "Next: Commit"
    assert wz.validate_step.tile_values()["warnings"] == "5"
    nxt(qtbot, wz, COMMIT)
    assert wz.steps.state(OUTPUTS) == "skipped" and wz.steps.state(MAPPING) == "skipped"
    settle(qtbot, win)
    assert wz.commit_step.summary["Default outputs"] == "Skipped: this template has none"
    sc = commit(qtbot, wz)
    assert sc.view.label == "R-0001"
    assert any("R-0001 committed: 13 rows saved." in b.plain_text for b in sc.banners())


@spec("RUNF-13", "IN-5", "TPL-D")
def test_tpl_d_one_row_per_sheet(win, qtbot, tpla):
    from conftest import tpl_a_columns
    from sankalan.model.rule import with_type_rules
    from sankalan.model.template import SourceSettings, Template
    cols = tpl_a_columns()
    tid = q.create_template(tpla["s"].con, Template("", tpla["client"], "Regional Sales",
                                                    SourceSettings(sheets="all"), cols, with_type_rules(cols, [])))
    assert win.go("new_run", template_id=tid, name="Regional Sales")
    settle(qtbot, win)
    wz = win.current
    wz.add_files([tpla["fx"] / "Sales_Regions.xlsx"])
    settle(qtbot, win)
    rows = wz.files_step.rows()
    assert [(r[0], r[1], r[5]) for r in rows] == [("Sales_Regions.xlsx", "North", "Ready"),
                                                   ("Sales_Regions.xlsx", "South", "Ready")]
    assert rows[1][2] == ""                                          # size on the file's first row only
    assert 'Hidden sheet "Archive" in Sales_Regions.xlsx is skipped.' in wz.files_step.summary.text()


@spec("FIT-04")
def test_wizard_and_run_screen_fit_the_smallest_layout(win, qtbot, tpla):
    from sankalan.ui import theme
    wz = wizard(qtbot, win, tpla, "Sales_Renamed_Headers.xlsx")
    wz.load_anyway(str(tpla["fx"] / "Sales_Renamed_Headers.xlsx"))      # loaded in R-0004 already
    nxt(qtbot, wz, MAPPING)
    for step in (FILES, MAPPING, VALIDATE, OUTPUTS, COMMIT):
        wz.pages.setCurrentIndex(step)
        hint = wz.minimumSizeHint()
        assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH, (step, hint)
        assert hint.height() <= theme.MIN_LAYOUT.height(), (step, hint)
    assert win.go("run", run_id=tpla["runs"]["R-0003"], template_id=tpla["tid"])
    settle(qtbot, win)
    sc = win.current
    for tab in range(4):
        sc.select_tab(tab)
        settle(qtbot, win)
        hint = sc.minimumSizeHint()
        assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH, (tab, hint)
        assert hint.height() <= theme.MIN_LAYOUT.height(), (tab, hint)
