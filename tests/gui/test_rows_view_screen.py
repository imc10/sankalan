"""6.4 Rows view and 7.9 Export rows (Feature Spec A2 2, 10.2; Tech spec A2 10.5): AC-ROW-1 to AC-ROW-9b, 11a, 11b,
S1, S2 on screen, TXT-3.

One module storage: TPL-R small R-0001…R-0003 (Rao & Co · Sales Register R), committed through the real pipeline
(``conftest.tpl_r_runs``). R-0001 has 2,500 rows (16 Taxable Value text values), R-0002 2,437 loaded (Place of
Supply added; 5 Invoice Date text values), R-0003 2,500.
"""
import csv
import datetime as dt
import io
import threading
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from conftest import run_job, settle_window, spec
from sankalan import analyses, rowsview
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, FlatMeasure, Group, cards
from sankalan.query import rows as qr
from sankalan.ui import theme
from sankalan.ui.dialogs import export_dialog
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens.analyses import AnalysesScreen
from sankalan.ui.screens.analysis import AnalysisScreen
from sankalan.ui.screens.rows_view import ROWS, SUMMARY
from sankalan.ui.window import MainWindow

INV, DATE_, CUST, STATE, TAXABLE, CGST, PLACE = "c001", "c002", "c003", "c005", "c006", "c007", "c021"
CLIENT, TEMPLATE = "Rao & Co", "Sales Register R"


def settle(qtbot, w, timeout=30_000):
    settle_window(qtbot, w, timeout)


@pytest.fixture
def win(app, qtbot, tpl_r_runs):
    s = tpl_r_runs["s"]
    w = MainWindow(JobBridge(s.runner), s)
    w.resize(1366, 768)
    w.show()
    yield w
    if w.export_dialog is not None:
        try:
            w.export_dialog.hide()
        except RuntimeError:
            pass
    w.bridge.wait_all(30)
    w.bridge.poll()
    from sankalan.ui.dialogs import base
    hook, base.answer_hook = base.answer_hook, (lambda _d: "leave")
    try:
        w.close()
    finally:
        base.answer_hook = hook
    w.deleteLater()


def screen(qtbot, w, *runs, rows=True) -> AnalysisScreen:
    assert w.go("analysis")
    settle(qtbot, w)
    sc = w.current
    sc.choose_template(CLIENT, TEMPLATE)
    settle(qtbot, w)
    sc.tick(list(runs))
    if rows:
        sc.switch.buttons[ROWS].click()
        assert sc.mode == ROWS
    return sc


def load_all(qtbot, sc):
    m = sc.rows_result.model
    settle(qtbot, sc.window_)
    for r in range(0, m.rowCount(), 200):
        m.data(m.index(r, 0))
        settle(qtbot, sc.window_)
    return sc.rows_shown()


def run_rows(qtbot, sc) -> rowsview.RowsOutcome:
    assert sc.run(), (sc.error.text(), sc.runs_error.text(), sc.columns_section.error.text())
    settle(qtbot, sc.window_)
    assert sc.rows_outcome is not None and not sc.rows_stale
    return sc.rows_outcome


def rows_tables(s):
    return [x[0] for x in s.con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE temporary AND table_name LIKE '\\_rows\\_%' ESCAPE '\\'"
    ).fetchall()]


def headers(sc):
    return sc.rows_result.headers()


def jobs_started(monkeypatch, w) -> list:
    """Every Job started on the runner from now on (operation names)."""
    started = []
    runner = w.bridge.runner
    real = runner.start

    def start(operation, work, **kw):
        started.append(operation)
        return real(operation, work, **kw)
    monkeypatch.setattr(runner, "start", start)
    return started


# ---------------------------------------------------------------------------------------------- ROW-1, ROW-7
@spec("AC-ROW-1", "AC-ROW-7", "ROW-1", "ROW-3", "ROW-7", "2.4")
def test_switch_to_rows_layout_and_checks(win, qtbot, tpl_r_runs, monkeypatch):
    sc = screen(qtbot, win, rows=False)
    assert sc.mode == SUMMARY and sc.switch.isVisible() and sc.switch.buttons[SUMMARY].isChecked()
    assert [b.text() for b in sc.switch.buttons.values()] == ["Summary", "Rows"]
    assert sc.badge.text() == "Not saved" and sc.save_button.isVisible()
    sc.switch.buttons[ROWS].click()
    b = sc.builder
    assert sc.mode == ROWS and sc.switch.buttons[ROWS].isChecked()
    assert b.filters.isVisible() and not b.groups.isVisible() and not b.measures.isVisible()
    assert not b.subtotals.isVisible() and sc.columns_section.isVisible() and sc.run_button.isVisible()
    assert not sc.save_button.isVisible() and sc.badge.text() == "Row views aren't saved"
    assert sc.modes.currentWidget() is sc.rows_panel
    assert sc.rows_result.message.text() == "Pick runs and filters, then press Run"
    # every column ticked, Place of Supply included (AC-ROW-7)
    cs = sc.columns_section
    assert cs.count.text() == "21 of 21 ticked" and len(cs.ticked()) == 21 and cs.ticked()[-1] == PLACE
    assert not cs.source and cs.show_source.text() == "Show them on screen"
    # Run with no runs ticked: clickable, says why under the runs list; nothing starts
    started = jobs_started(monkeypatch, win)
    assert sc.run_button.isEnabled()
    assert not sc.run()
    assert sc.runs_error.isVisible() and sc.runs_error.text() == "Tick at least one run"
    sc.tick(["R-0001"])
    assert not sc.runs_error.isVisible()
    cs.tick_all(False)
    assert cs.count.text() == "0 of 21 ticked"
    assert not sc.run()
    assert cs.error.isVisible() and cs.error.text() == "Tick at least one column"
    assert started == [] and sc.job is None
    cs.tick(INV)
    assert not cs.error.isVisible() and cs.count.text() == "1 of 21 ticked"
    assert sc.leave_guard() is None


# ---------------------------------------------------------------------------------------------- ROW-2
@spec("AC-ROW-2", "ROW-2")
def test_switching_keeps_runs_filters_groups_and_measures(win, qtbot, tpl_r_runs):
    sc = screen(qtbot, win, "R-0001", "R-0002", rows=False)
    b = sc.builder
    b.add_filter(Filter(STATE, d.ONE_OF, ["Maharashtra", "Gujarat"]))
    b.add_filter(Filter(TAXABLE, d.NOT_BLANK))
    b.add_group(Group(STATE))
    b.add_group(Group(DATE_, "month"))
    for m in (FlatMeasure(TAXABLE, d.SUM), FlatMeasure(INV, d.COUNT), FlatMeasure(d.ROWS, d.COUNT)):
        b.add_measure(m)
    assert sc.run()
    settle(qtbot, win)
    assert sc.outcome is not None
    before = b.definition().to_dict()
    sc.switch.buttons[ROWS].click()
    settle(qtbot, win)
    assert sc.outcome is None and sc.rows_outcome is None                         # result cleared
    assert sorted(sc.ticked_runs()) == sorted(tpl_r_runs["runs"][k] for k in (1, 2))
    assert [f.to_dict() for f in b.definition().filters] == before["filters"]
    o = run_rows(qtbot, sc)
    assert o.match == run_job(win.storage.runner, lambda ctx: sum(qr.count_rows(
        ctx.cursor(), o.spec, sc.data.columns, o.runs).values()))
    table = o.table
    sc.switch.buttons[SUMMARY].click()
    settle(qtbot, win)
    assert sc.rows_outcome is None and sc.result_stack.currentWidget() is sc.empty
    assert b.definition().to_dict() == before                                     # groups and measures came back
    assert len(b.groups.rows) == 2 and len(d.flat_measures(b.definition())) == 3
    assert table not in rows_tables(win.storage)                                   # dropped on the switch


# ---------------------------------------------------------------------------------------------- ROW-3, ROW-4
@spec("AC-ROW-3", "ROW-3")
def test_leaving_clears_with_no_prompt_and_cancels_a_run(win, qtbot, answers, monkeypatch):
    earlier = rows_tables(win.storage)                  # left by earlier tests' windows in the module storage
    sc = screen(qtbot, win, "R-0001")
    run_rows(qtbot, sc)
    assert sc.leave_guard() is None
    assert win.open_area("clients")
    settle(qtbot, win)
    assert answers.asked == [] and win.current.area == "clients"
    assert rows_tables(win.storage) == earlier
    assert win.open_area("analysis")
    settle(qtbot, win)
    assert isinstance(win.current, AnalysesScreen)
    sc = screen(qtbot, win, rows=False)
    assert sc.mode == SUMMARY and sc.ticked_runs() == [] and not sc.builder.filters.rows
    assert sc.outcome is None and sc.rows_outcome is None
    # leaving while a Rows Run is fetching cancels it and leaves no table
    sc.tick(["R-0001"])
    sc.switch.buttons[ROWS].click()
    run_rows(qtbot, sc)
    started, release = threading.Event(), threading.Event()

    def hold(ctx):
        started.set()
        end = time.monotonic() + 20              # never outlive a failed test
        while not ctx.cancel_requested and time.monotonic() < end:
            release.wait(0.01)
    monkeypatch.setattr(rowsview, "_before_fetch", hold)
    sc.builder.add_filter(Filter(STATE, d.ONE_OF, ["Delhi"]))
    assert sc.run()
    assert started.wait(10)
    job = sc.job
    assert win.open_area("clients")
    assert job.wait(10)
    settle(qtbot, win)
    assert answers.asked == [] and job.state.name == "CANCELLED"
    assert rows_tables(win.storage) == earlier


@spec("AC-ROW-4", "ROW-4")
def test_saved_analysis_has_no_switch(win, qtbot, tpl_r_runs):
    s = win.storage
    from sankalan.query import catalogue as q
    t = q.load_template(s.con, tpl_r_runs["tid"])
    aid = run_job(s.runner, lambda ctx: analyses.save(ctx, t, "Rows test saved", Definition(
        t.id, [], [Group(STATE)], cards(FlatMeasure(d.ROWS, d.COUNT)))))
    assert win.go("analysis", analysis_id=aid)
    settle(qtbot, win)
    sc = win.current
    assert sc.saved is not None and not sc.switch.isVisible() and sc.mode == SUMMARY
    assert not sc.choose_view(ROWS) and sc.mode == SUMMARY
    run_job(s.runner, lambda ctx: analyses.delete(ctx, aid))


# ---------------------------------------------------------------------------------------------- ROW-6
@spec("AC-ROW-6", "ROW-6", "TXT-6", "TXT-7")
def test_not_a_number_and_not_a_date_count_as_in_summary(win, qtbot):
    for f, expect in ((Filter(TAXABLE, d.NOT_NUMBER), 16), (Filter(DATE_, d.NOT_DATE), 5)):
        sc = screen(qtbot, win, "R-0001", "R-0002", "R-0003", rows=False)
        sc.builder.add_filter(f)
        sc.builder.add_measure(FlatMeasure(d.ROWS, d.COUNT))
        assert sc.run()
        settle(qtbot, win)
        summary = sc.total_row()[-1]
        sc.switch.buttons[ROWS].click()
        row = sc.builder.filters.rows[0]
        assert row.op.currentData() == f.op and row.isVisible()
        o = run_rows(qtbot, sc)
        assert o.match == expect and summary == str(expect)
        assert sc.rows_result.summary.text().startswith(f"{expect} rows match · 3 runs · 7,437 rows searched · ")


# ---------------------------------------------------------------------------------------------- ROW-8, ROW-9b, 2.2
@spec("AC-ROW-8", "AC-ROW-9b", "ROW-8", "ROW-9", "T52", "2.2", "TXT-3")
def test_columns_and_source_columns_redraw_without_a_job(win, qtbot, monkeypatch):
    sc = screen(qtbot, win, "R-0001")
    sc.builder.add_filter(Filter(TAXABLE, d.NOT_NUMBER))
    run_rows(qtbot, sc)
    shown = load_all(qtbot, sc)
    names = [c.name for c in sc.data.columns if not c.removed]
    assert headers(sc) == names and len(shown) == 16
    grid = sc.rows_result.grid
    assert grid.frozen is not None and grid.frozen.isVisible()
    assert grid.frozen.font().weight() == theme.font(theme.GRID_TEXT_PX, medium=True).weight()
    assert grid.frozen.columnWidth(0) == grid.columnWidth(0) and grid.frozen.isColumnHidden(1)
    # TXT-3: text in a Number column right-aligned, in a Date column left-aligned; cells as typed
    m = sc.rows_result.model
    ti, di = names.index("Taxable Value"), names.index("Invoice Date")
    assert sorted(r[ti] for r in shown) == sorted(["NA"] * 10 + ["Nil"] * 5 + ["12,000/-"])
    assert m.data(m.index(0, ti), Qt.ItemDataRole.TextAlignmentRole) & Qt.AlignmentFlag.AlignRight
    assert m.data(m.index(0, di), Qt.ItemDataRole.TextAlignmentRole) & Qt.AlignmentFlag.AlignLeft
    started = jobs_started(monkeypatch, win)
    cs = sc.columns_section
    cs.tick(INV, False)
    assert headers(sc) == names[1:] and not sc.rows_result.greyed and not sc.rows_stale
    cs.tick(INV, True)
    cs.move(TAXABLE, -5)
    order = cs.ticked()
    assert order[0] == TAXABLE and headers(sc)[0] == "Taxable Value"
    assert sc.rows_shown()[0][0] == shown[0][ti]                       # the same rows, the column moved
    cs.show_source.setChecked(True)
    assert headers(sc) == [n for n in (["Taxable Value"] + [x for x in names if x != "Taxable Value"])] + [
        "Source File", "Source Sheet", "Source Row", "Run ID"]
    last = sc.rows_shown()[0]
    assert last[-1] == "R-0001" and last[-4].startswith("TPLR_R1_") and last[-2].replace(",", "").isdigit()
    assert started == [] and not win.bridge._tracked and not sc.rows_result.greyed
    # unticking every column empties the grid with the message and disables Export rows
    cs.tick_all(False)
    assert sc.rows_result.message.text() == "Tick at least one column" and not sc.rows_result.export_button.isEnabled()
    cs.tick_all(True)
    assert sc.rows_result.stack.currentWidget() is sc.rows_result.page
    assert sc.rows_result.export_button.isEnabled() and started == []


# ---------------------------------------------------------------------------------------------- ROW-9a
@spec("AC-ROW-9a", "ROW-9", "ROW-5")
def test_settings_changes_grey_the_result(win, qtbot, answers):
    sc = screen(qtbot, win, "R-0001")
    run_rows(qtbot, sc)
    r = sc.rows_result
    assert not r.greyed and r.export_button.isEnabled()
    sc.builder.add_filter(Filter(STATE, d.ONE_OF, ["Delhi"]))
    assert r.greyed and r.stale_note.isVisible() and r.stale_note.text() == "Settings changed: Run again"
    assert not r.export_button.isEnabled()
    run_rows(qtbot, sc)
    assert not r.greyed and r.export_button.isEnabled()
    sc.tick(["R-0002"])
    assert r.greyed and r.stale_note.text() == "Settings changed: Run again" and not r.export_button.isEnabled()
    run_rows(qtbot, sc)
    # the template: after the confirmation the settings and the result are cleared and the table dropped (ROW-5)
    table = sc.rows_outcome.table
    answers.append("cancel")
    sc.template.setCurrentIndex(0)
    sc._template_picked(0)
    assert sc.rows_outcome is not None and not r.greyed
    answers.append("change")
    sc.template.setCurrentIndex(0)
    sc._template_picked(0)
    settle(qtbot, win)
    assert sc.rows_outcome is None and not r.export_button.isEnabled() and sc.mode == ROWS
    assert r.message.text() == "Pick runs and filters, then press Run" and table not in rows_tables(win.storage)


# ---------------------------------------------------------------------------------------------- ROW-11
@spec("AC-ROW-11a", "AC-ROW-11b", "ROW-11", "D71")
def test_cap_footer_and_no_sorting(win, qtbot, monkeypatch):
    monkeypatch.setattr(qr, "ROWS_CAP", 1000)
    sc = screen(qtbot, win, "R-0001", "R-0002", "R-0003")
    o = run_rows(qtbot, sc)
    r = sc.rows_result
    assert o.match == 7_437 and r.model.rowCount() == 1000
    assert r.footer.text() == ("Showing the first 1,000 of 7,437 rows, in the order they were loaded. Export gets "
                               "all of them.")
    first = load_all(qtbot, sc)[:3]
    hh = r.grid.horizontalHeader()
    assert not hh.isSortIndicatorShown()
    QTest.mouseClick(hh.viewport(), Qt.MouseButton.LeftButton, pos=hh.rect().center())
    settle(qtbot, win)
    assert r.model.sort_spec == [] and not hh.isSortIndicatorShown() and sc.rows_shown()[:3] == first
    sc.builder.add_filter(Filter(TAXABLE, d.NOT_NUMBER))
    run_rows(qtbot, sc)
    assert r.footer.text() == "Showing all 16 rows" and r.model.rowCount() == 16


# ---------------------------------------------------------------------------------------------- 2.4 states
@spec("AC-ROW-S1", "AC-ROW-S2", "2.4")
def test_no_match_and_cancel(win, qtbot, monkeypatch):
    earlier = rows_tables(win.storage)
    sc = screen(qtbot, win, "R-0001")
    run_rows(qtbot, sc)
    sc.builder.add_filter(Filter(INV, d.CONTAINS, ["no such invoice"]))
    o = run_rows(qtbot, sc)
    r = sc.rows_result
    assert o.match == 0 and r.message.text() == "No rows match these filters." and not r.export_button.isVisible()
    sc.builder.clear()
    sc.builder.changed.emit()
    run_rows(qtbot, sc)
    summary = r.summary.text()
    started = threading.Event()

    def hold(ctx):
        started.set()
        end = time.monotonic() + 20              # never outlive a failed test
        while not ctx.cancel_requested and time.monotonic() < end:
            threading.Event().wait(0.01)
    monkeypatch.setattr(rowsview, "_before_fetch", hold)
    sc.tick(["R-0002"])
    assert sc.run()
    assert started.wait(10)
    assert r.progress.isVisible() and r.greyed and not sc.run_button.isEnabled()
    qtbot.waitUntil(lambda: r.progress.stage.text() == "Fetching the first 100,000", timeout=5000)
    r.progress.cancel_button.click()
    settle(qtbot, win)
    assert sc.rows_outcome is not None and r.greyed and r.stale_note.text() == "Cancelled: Run again"
    assert r.summary.text() == summary and not r.progress.isVisible() and not r.export_button.isEnabled()
    assert sorted(rows_tables(win.storage)) == sorted(earlier + [sc.rows_outcome.table])


# ---------------------------------------------------------------------------------------------- 7.9 Export rows
@spec("ROW-12", "2.3", "AC-ROW-8", "EXP-8")
def test_export_rows_dialog_and_file(win, qtbot, tmp_path):
    sc = screen(qtbot, win, "R-0001")
    sc.builder.add_filter(Filter(TAXABLE, d.NOT_NUMBER))
    run_rows(qtbot, sc)
    sc.columns_section.tick_all(False)
    for cid in (TAXABLE, INV, CUST):
        sc.columns_section.tick(cid)
    assert sc.rows_result.export_button.text() == "Export rows (.csv)"
    assert sc.export_rows()
    dlg = win.export_dialog
    settle_window(qtbot, win, extra=lambda: not dlg._checking)
    assert dlg.title.text() == "Export 16 rows"
    assert dlg.info.text().startswith("Rao & Co · Sales Register R · 1 run · 1 filter · about ")
    assert dlg.info.text().endswith(" · CSV file")
    assert dlg.details.isVisible() and dlg.details.text().splitlines() == [
        "Filters: Taxable Value is not a number",
        "Columns: the 3 ticked columns, in their order, then Source File, Source Sheet, Source Row and Run ID",
        "Rows in the order they were loaded: by Run ID, then file, sheet and row"]
    today = dt.date.today().strftime("%d-%m-%Y")
    assert dlg.name.text() == f"Rao & Co_Sales Register R_Rows_{today}.csv"
    assert not dlg.parts.isVisible()
    export_dialog.folder_hook = lambda _d: str(tmp_path)
    try:
        dlg.change.click()
    finally:
        export_dialog.folder_hook = None
    assert dlg.export()
    settle(qtbot, win)
    text = (tmp_path / f"Rao & Co_Sales Register R_Rows_{today}.csv").read_bytes().decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    assert rows[0] == ["Invoice No", "Customer", "Taxable Value", "Source File", "Source Sheet", "Source Row",
                       "Run ID"]                                     # the Columns list's order, not the tick order
    assert len(rows) == 17 and sorted(x[2] for x in rows[1:]) == sorted(["NA"] * 10 + ["Nil"] * 5 + ["12,000/-"])
    assert {x[-1] for x in rows[1:]} == {"R-0001"}
    assert [x[0] for x in rows[1:]] == [x[0] for x in load_all(qtbot, sc)]          # the grid's order


@spec("FIT-04", "UI-2")
def test_rows_view_fits_1280_by_640(win, qtbot):
    sc = screen(qtbot, win, "R-0001")
    run_rows(qtbot, sc)
    sc.columns_section.show_source.setChecked(True)
    hint = sc.minimumSizeHint()
    assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH
    assert hint.height() <= theme.MIN_LAYOUT.height()
    assert sc.switch.y() < sc.rows_panel.mapTo(sc, sc.rows_panel.rect().topLeft()).y()
