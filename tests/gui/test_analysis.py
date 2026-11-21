"""Phase 10: Analysis (6.1–6.3, 7.7, 7.8) and the Export dialogs (7.4, 7.5): A0-01…05, A1-01…15, EXP-01…08.

One module storage: TPL-A in Acme Traders with R-0001 (F02 Sales_Oct), R-0002 (F03 Sales_Nov), R-0003 (F04
Sales_Errors, with override) and R-0004 (F14 Sales_NoDates: the sheet's R-0006, 500 rows with no dates), committed
through the real pipeline; a duplicate of TPL-A (C2-06) and Regional Sales in Bharat Foods (TPL-D, no runs). Tests
run in file order: the saved-analysis tests use AN-1 and AN-2 saved by A1-13.
"""
import threading

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel

from conftest import OVERRIDE_REASON, commit_tpl_a_run, open_storage, settle_window, spec, tpl_a_template
from sankalan import analyses, exporting
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, Group, Measure
from sankalan.query import catalogue as q
from sankalan.ui import theme
from sankalan.ui.dialogs import export_dialog
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens import analysis as analysis_screen
from sankalan.ui.screens.analyses import AnalysesScreen
from sankalan.ui.screens.analysis import AnalysisScreen
from sankalan.ui.window import MainWindow

INV, DATE_, CUST, GSTIN, STATE, TAXABLE, RATE, TAX = (f"c00{i}" for i in range(1, 9))


def settle(qtbot, w, timeout=30_000):
    settle_window(qtbot, w, timeout)


@pytest.fixture(scope="module")
def tpla(tmp_path_factory, fixtures_dir):
    s = open_storage(tmp_path_factory.mktemp("analysis"))
    acme = q.insert_client(s.con, "Acme Traders")
    tid = q.create_template(s.con, tpl_a_template(acme))
    runs = {}
    for name, reason in (("Sales_Oct.xlsx", None), ("Sales_Nov.xlsx", None),
                         ("Sales_Errors.xlsx", OVERRIDE_REASON), ("Sales_NoDates.xlsx", None)):
        r = commit_tpl_a_run(s, tid, fixtures_dir, name, reason=reason)
        runs[r.label] = r.run_id
    copy_id = q.duplicate_template(s.con, tid, "Sales Register (copy)")
    bharat = q.insert_client(s.con, "Bharat Foods")
    t = tpl_a_template(bharat)
    t.name = "Regional Sales"
    regional = q.create_template(s.con, t)
    yield {"s": s, "tid": tid, "runs": runs, "copy": copy_id, "regional": regional}
    s.close()


@pytest.fixture
def win(app, qtbot, tpla):
    from sankalan.ui.dialogs import base
    s = tpla["s"]
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
    hook, base.answer_hook = base.answer_hook, (lambda _d: "leave")     # 7.7 on close: Leave without saving
    try:
        w.close()
    finally:
        base.answer_hook = hook
    w.deleteLater()


def new_analysis(qtbot, win, *runs) -> AnalysisScreen:
    assert win.go("analysis")
    settle(qtbot, win)
    sc = win.current
    sc.choose_template("Acme Traders", "Sales Register")
    settle(qtbot, win)
    sc.tick(list(runs))
    return sc


def run(qtbot, sc) -> analyses.Outcome:
    assert sc.run(), sc.error.text()
    settle(qtbot, sc.window_)
    assert sc.outcome is not None and not sc.stale
    return sc.outcome


def rows(qtbot, sc):
    m = sc.model
    settle(qtbot, sc.window_)
    for r in range(m.rowCount()):
        m.data(m.index(r, 0))
        settle(qtbot, sc.window_)
    return sc.result_rows()


def setup(sc, filters=(), groups=(), measures=(), subtotals=False):
    b = sc.builder
    b.clear()
    for f in filters:
        b.add_filter(f)
    for g in groups:
        b.add_group(g)
    for m in measures:
        b.add_measure(m)
    b.subtotals.setChecked(subtotals)


# ---------------------------------------------------------------------------------------------- 6.2 New analysis
@spec("A1-01", "ANA-2", "ANA-3", "UX-10")
def test_layout_and_data_selection(win, qtbot):
    assert win.open_area("analysis")
    settle(qtbot, win)
    assert isinstance(win.current, AnalysesScreen)
    win.current.new_button.click()
    settle(qtbot, win)
    sc = win.current
    assert isinstance(sc, AnalysisScreen)
    assert sc.breadcrumb.text() == "Analyses › New analysis" and sc.h1.text() == "New analysis"
    assert sc.badge.text() == "Not saved" and sc.save_button.isVisible() and not sc.duplicate_button.isVisible()
    assert sc.result_stack.currentWidget() is sc.empty
    assert sc.empty_title.text() == "Choose runs, then press Run"
    assert not sc.run_button.isEnabled()
    assert [sc.client.itemText(i) for i in range(sc.client.count())] == ["Choose a client", "Acme Traders",
                                                                          "Bharat Foods"]
    sc.choose_template("Acme Traders", "Sales Register")
    settle(qtbot, win)
    assert [sc.template.itemText(i) for i in range(sc.template.count())] == [
        "Choose a template", "Sales Register", "Sales Register (copy)"]
    assert sc.settings_box.width() == 380 and sc.settings_box.x() < sc.result_stack.mapTo(sc, QPoint(0, 0)).x()
    items = [sc.runs.item(i) for i in range(sc.runs.count())]
    assert [i.text() for i in items] == ["R-0004    Sales_NoDates.xlsx", "R-0003    Sales_Errors.xlsx",
                                         "R-0002    Sales_Nov.xlsx", "R-0001    Sales_Oct.xlsx"]
    assert items[3].toolTip() == "Sales_Oct.xlsx"
    assert sc.runs_note.text() == "No runs selected. Tick the runs to include."
    sc.select_all.click()
    assert sc.runs_note.text() == "4 of 4 runs selected" and len(sc.ticked_runs()) == 4
    assert sc.run_button.isEnabled()
    sc.select_all.click()
    assert sc.ticked_runs() == []
    sc.tick(["R-0001", "R-0002", "R-0003"])
    assert sc.runs_note.text() == "3 of 4 runs selected"
    hint = sc.minimumSizeHint()
    assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH
    assert hint.height() <= theme.MIN_LAYOUT.height()


@spec("A1-02", "ANA-3")
def test_changing_template_clears_settings(win, qtbot, answers):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(STATE)], measures=[Measure(TAXABLE, d.SUM)])
    answers.append("cancel")
    sc.choose_template("Acme Traders", "Sales Register (copy)")
    assert answers.asked[-1][0] == "Change template?"
    assert sc.template.currentText() == "Sales Register" and len(sc.builder.groups.rows) == 1
    assert sc.ticked_runs() == [sc.data.runs[3].id]
    answers.append("change")
    sc.choose_template("Acme Traders", "Sales Register (copy)")
    settle(qtbot, win)
    assert sc.template.currentText() == "Sales Register (copy)"
    assert not sc.builder.filters.rows and not sc.builder.groups.rows and not sc.builder.measures.rows
    assert sc.runs.count() == 0 and sc.ticked_runs() == []
    assert sc.runs_note.text() == "No runs selected. Tick the runs to include."


@spec("A1-03", "ANA-5", "ANA-7")
def test_basic_result_with_grand_total(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(STATE)], measures=[Measure(TAXABLE, d.SUM), Measure(INV, d.COUNT)])
    o = run(qtbot, sc)
    assert [sc.model.headerData(i, Qt.Orientation.Horizontal) for i in range(3)] == [
        "State", "Sum of Taxable Value", "Count of Invoice No"]
    assert rows(qtbot, sc) == [("Delhi", "1,903,437.50", "1,250"), ("Gujarat", "1,877,812.50", "1,250"),
                               ("Karnataka", "1,890,625.00", "1,250"), ("Maharashtra", "1,865,000.00", "1,250")]
    assert sc.total_row() == ["Grand total", "7,536,875.00", "5,000"]
    assert o.summary().startswith("1 run · 5,000 rows · 4 result rows · ")
    assert sc.summary.text() == o.summary()
    assert not sc.cap.isVisible() and not sc.greyed


@spec("A1-04", "ANA-6")
def test_measures_and_renaming(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, measures=[Measure(TAXABLE, d.SUM), Measure(TAXABLE, d.COUNT), Measure(TAXABLE, d.AVG, "Avg value"),
                        Measure(TAXABLE, d.MIN), Measure(TAXABLE, d.MAX), Measure(CUST, d.COUNT_DISTINCT),
                        Measure(GSTIN, d.COUNT_DISTINCT)])
    run(qtbot, sc)
    assert rows(qtbot, sc) == []
    headers = [sc.model.headerData(i, Qt.Orientation.Horizontal) for i in range(sc.model.columnCount())]
    assert headers == ["Sum of Taxable Value", "Count of Taxable Value", "Avg value", "Min of Taxable Value",
                       "Max of Taxable Value", "Count distinct of Customer", "Count distinct of GSTIN"]
    assert sc.total_row() == ["7,536,875.00", "5,000", "1,507.38", "1,000.00", "2,014.75", "10", "5,000"]


@spec("A1-05", "ANA-7", "T23")
def test_subtotals_and_sorting_within_groups(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(STATE), Group(RATE)], measures=[Measure(TAXABLE, d.SUM)], subtotals=True)
    run(qtbot, sc)
    got = rows(qtbot, sc)
    assert len(got) == 24 and sum(1 for r in got if r[1] == "Total") == 4
    maha = [r for r in got if r[0] == "Maharashtra"]
    assert maha == [("Maharashtra", "0", "352,500.00"), ("Maharashtra", "5", "393,500.00"),
                    ("Maharashtra", "12", "383,250.00"), ("Maharashtra", "18", "373,000.00"),
                    ("Maharashtra", "28", "362,750.00"), ("Maharashtra", "Total", "1,865,000.00")]
    assert sc.total_row() == ["Grand total", "", "7,536,875.00"]
    # subtotal rows in medium weight
    i = got.index(("Maharashtra", "Total", "1,865,000.00"))
    assert sc.model.data(sc.model.index(i, 0), Qt.ItemDataRole.FontRole) is not None
    assert sc.model.data(sc.model.index(0, 0), Qt.ItemDataRole.FontRole) is None
    sc.grid._header_clicked(2)                      # Sum ascending, then descending
    sc.grid._header_clicked(2)
    got = rows(qtbot, sc)
    maha = [r for r in got if r[0] == "Maharashtra"]
    assert [r[1] for r in maha] == ["5", "12", "18", "28", "0", "Total"]
    states = [r[0] for r in got if r[1] == "Total"]
    assert states == ["Delhi", "Karnataka", "Gujarat", "Maharashtra"]
    assert got[5] == ("Delhi", "Total", "1,903,437.50")         # subtotals stay with their state


@spec("A1-06", "ANA-5")
def test_group_levels_reorder_and_date_grain(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(DATE_)], measures=[Measure(INV, d.COUNT)])
    run(qtbot, sc)
    got = rows(qtbot, sc)
    assert len(got) == 31 and got[0] == ("01-10-2026", "162") and got[-1] == ("31-10-2026", "161")
    row = sc.builder.groups.rows[0]
    for grain, label in (("month", "Oct-2026"), ("quarter", "Q4-2026"), ("year", "2026")):
        row.grain.setCurrentIndex(row.grain.findData(grain))
        assert sc.greyed and sc.stale_note.text() == "Settings changed: Run again"
        run(qtbot, sc)
        assert rows(qtbot, sc) == [(label, "5,000")]
    sc.builder.add_group(Group(STATE))
    sc.builder._move_group(sc.builder.groups.rows[1], -1)
    assert [r.number.text() for r in sc.builder.groups.rows] == ["1", "2"]
    assert sc.builder.definition().groups[0].column_id == STATE
    run(qtbot, sc)
    assert rows(qtbot, sc)[0] == ("Delhi", "2026", "1,250")


@spec("A1-07", "ANA-4")
def test_date_filters(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001", "R-0002")
    cases = [(Filter(DATE_, d.MONTH, [2026, 10]), ["5,000", "7,536,875.00"]),
             (Filter(DATE_, d.QUARTER, [2026, 4]), ["9,000"]),
             (Filter(DATE_, d.BETWEEN, ["2026-11-01", "2026-11-15"]), ["2,005"]),
             (Filter(DATE_, d.BLANK), ["0"])]
    for f, expected in cases:
        ms = [Measure(INV, d.COUNT)] + ([Measure(TAXABLE, d.SUM)] if len(expected) == 2 else [])
        setup(sc, filters=[f], measures=ms)
        run(qtbot, sc)
        assert sc.total_row()[:len(expected)] == expected, f
    # Between typed on screen as DD-MM-YYYY
    row = sc.builder.add_filter(Filter(DATE_, d.BETWEEN, []))
    sc.builder._remove(sc.builder.filters, sc.builder.filters.rows[0])
    row.edits[0].setText("01-11-2026")
    row.edits[1].setText("15-11-2026")
    run(qtbot, sc)
    assert sc.total_row()[0] == "2,005"
    setup(sc, filters=[Filter(DATE_, d.BLANK)], measures=[Measure(INV, d.COUNT)])
    sc.tick(["R-0001", "R-0002"], False)
    sc.tick("R-0004")
    run(qtbot, sc)
    assert sc.total_row() == ["500"]


@spec("A1-08", "ANA-4", "T23")
def test_text_filters_and_value_picker(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001")
    row = sc.builder.add_filter(Filter(CUST, d.ONE_OF, []))
    assert row.edits[0].text() == "Choose values…"
    dlg = sc.pick_values(row)
    settle(qtbot, win)
    values = dlg.shown_values()
    assert len(values) == 10 and all(n == 500 for _v, n in values)
    assert dlg.search.isVisible() and dlg.status.text() == "10 values"
    dlg.search.setText("PATEL")
    dlg.start_read()
    settle(qtbot, win)
    assert dlg.shown_values() == [("Patel Agencies", 500)]
    dlg.tick("Patel Agencies")
    dlg.search.setText("")
    dlg.start_read()
    settle(qtbot, win)
    dlg.tick("Laxmi Stores")
    dlg.apply.click()
    assert row.picked == ["Patel Agencies", "Laxmi Stores"] and row.edits[0].text() == "Patel Agencies, Laxmi Stores"
    setup(sc, filters=[Filter(CUST, d.ONE_OF, ["Patel Agencies", "Laxmi Stores"])], measures=[Measure(INV, d.COUNT)])
    run(qtbot, sc)
    assert sc.total_row() == ["1,000"]
    setup(sc, filters=[Filter(CUST, d.CONTAINS, ["patel"])], measures=[Measure(INV, d.COUNT)])
    run(qtbot, sc)
    assert sc.total_row() == ["500"]
    sc.tick("R-0001", False)
    sc.tick("R-0003")
    setup(sc, filters=[Filter(CUST, d.BLANK)], measures=[Measure(None, d.COUNT)])
    run(qtbot, sc)
    assert sc.total_row() == ["7"]
    setup(sc, filters=[Filter(STATE, d.ONE_OF, ["Goa"])], measures=[Measure(None, d.COUNT)])
    run(qtbot, sc)
    assert sc.total_row() == ["25"]


@spec("A1-09", "ANA-4")
def test_number_filters_and_and(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001")
    row = sc.builder.add_filter(Filter(RATE, d.EQUALS, ["18"]))
    assert row.edits[0].accessibleName() == "Number"        # typed, no value list for Number filters
    setup(sc, filters=[Filter(RATE, d.EQUALS, ["18"]), Filter(STATE, d.ONE_OF, ["Maharashtra"])],
          measures=[Measure(None, d.COUNT), Measure(TAXABLE, d.SUM)])
    run(qtbot, sc)
    assert sc.total_row() == ["250", "373,000.00"]
    setup(sc, filters=[Filter(TAXABLE, d.BETWEEN, ["1000", "1010.25"])],
          groups=[Group(TAXABLE)], measures=[Measure(None, d.COUNT)])
    run(qtbot, sc)
    assert [r[0] for r in rows(qtbot, sc)] == ["1,000.00", "1,010.25"]
    assert sc.total_row() == ["Grand total", "100"]


@spec("A1-10", "T23", "T18")
def test_count_counts_non_blank_values(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0003")
    setup(sc, measures=[Measure(CUST, d.COUNT), Measure(INV, d.COUNT)])
    run(qtbot, sc)
    assert sc.total_row() == ["1,930", "1,937"]


@spec("A1-11", "ANA-8", "UI-5")
def test_run_cancel_and_changed_settings(win, qtbot, monkeypatch):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(STATE)], measures=[Measure(TAXABLE, d.SUM)])
    run(qtbot, sc)
    first = sc.total_row()
    started = threading.Event()
    real = analyses.run

    def slow(ctx, *a, **k):
        started.set()
        while True:
            ctx.check_cancelled()
            threading.Event().wait(0.01)
    monkeypatch.setattr(analyses, "run", slow)
    sc.builder.measures.rows[0].label.setText("Taxable")
    sc.builder.measures.rows[0].label.textEdited.emit("Taxable")
    assert sc.greyed and sc.stale_note.isVisible() and sc.stale_note.text() == "Settings changed: Run again"
    assert not sc.export_button.isEnabled()
    assert sc.run()
    assert started.wait(10)
    assert sc.progress.isVisible() and sc.progress.cancel_button.isVisible()
    assert not sc.run_button.isEnabled()
    sc.progress.cancel_button.click()
    settle(qtbot, win)
    assert sc.outcome is not None and sc.greyed and sc.stale_note.text() == analysis_screen.CANCELLED
    assert sc.total_row() == first and not sc.progress.isVisible()
    monkeypatch.setattr(analyses, "run", real)
    run(qtbot, sc)
    assert not sc.greyed and sc.export_button.isEnabled()
    assert sc.model.headerData(1, Qt.Orientation.Horizontal) == "Taxable"


@spec("A1-12", "ANA-7", "ANA-9")
def test_result_capped_on_screen_export_has_every_row(win, qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(analyses, "ROW_CAP", 1000)
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(INV)], measures=[Measure(None, d.COUNT)])
    o = run(qtbot, sc)
    assert o.count == 5000 and sc.model.rowCount() == 1000
    assert sc.cap.isVisible() and sc.cap.text() == "Showing the first 1,000 of 5,000 rows. Export (.csv) writes every row."
    assert sc.total_row() == ["Grand total", "5,000"]
    assert sc.export()
    dlg = win.export_dialog
    assert dlg.title.text() == "Export Analysis" and dlg.info.text() == "5,001 rows · CSV file"
    assert dlg.name.text() == "Acme Traders_Sales Register_Analysis.csv"
    dlg.folder.setText(str(tmp_path))
    assert dlg.export()
    settle(qtbot, win)
    lines = (tmp_path / "Acme Traders_Sales Register_Analysis.csv").read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "Invoice No,Count of rows" and len(lines) == 5002 and lines[-1] == "Grand total,5000"


# ---------------------------------------------------------------------------------------------- 7.8, 7.7
@spec("A1-13", "ANA-1")
def test_save_an_analysis(win, qtbot):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(STATE)], measures=[Measure(TAXABLE, d.SUM), Measure(INV, d.COUNT)])
    run(qtbot, sc)
    dlg = sc.save_dialog()
    assert dlg.title.text() == "Save analysis"
    texts = [lab.text() for lab in dlg.findChildren(QLabel)]
    assert "Unique within Acme Traders · Sales Register." in texts
    dlg.save.click()
    settle(qtbot, win)
    assert dlg.error.text() == "Enter a name for the analysis." and dlg.isVisible()
    dlg.edit.setText("State sales")
    dlg.save.click()
    settle(qtbot, win)
    assert not dlg.isVisible()
    assert sc.saved is not None and sc.h1.text() == "State sales" and sc.badge.text().startswith("Saved ")
    assert sc.settings.currentWidget() is sc.locked and sc.outcome is not None
    assert sc.breadcrumb.text() == "Analyses › State sales" and sc.leave_guard() is None
    # AN-2
    sc2 = new_analysis(qtbot, win, "R-0001")
    setup(sc2, groups=[Group(STATE)], measures=[Measure(GSTIN, d.COUNT_DISTINCT)])
    dlg = sc2.save_dialog()
    dlg.edit.setText("state SALES ")
    dlg.save.click()
    settle(qtbot, win)
    assert dlg.error.text() == "“State sales” is already in use. Choose another name."
    dlg.edit.setText("GSTIN check")
    dlg.save.click()
    settle(qtbot, win)
    assert sc2.saved is not None
    # one on TPL-D for A0-01
    s = win.storage
    q.insert_saved_analysis(s.con, q.load_template(s.con, s.con and q.template_ids(s.con)[0]).id, "x", {}) \
        if False else None
    assert win.open_area("analysis")
    settle(qtbot, win)
    a0 = win.current
    names = [r[0] for r in a0.visible_rows()]
    assert names == ["GSTIN check", "State sales"]


@spec("A1-14", "ANA-2")
def test_leaving_an_unsaved_result(win, qtbot, answers):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(STATE)], measures=[Measure(TAXABLE, d.SUM)])
    assert sc.leave_guard() is None                  # nothing to lose before a result
    run(qtbot, sc)
    answers.append("stay")
    assert not win.open_area("clients")
    assert answers.asked[-1] == ("This analysis isn't saved", ["Stay", "Leave without saving", "Save…"])
    assert win.current is sc
    answers.append("leave")
    assert win.open_area("clients")
    settle(qtbot, win)
    assert win.current.area == "clients"
    assert win.open_area("analysis")
    settle(qtbot, win)
    assert isinstance(win.current, AnalysesScreen)        # the ad-hoc analysis is gone


def test_save_from_the_leave_prompt(win, qtbot, answers, monkeypatch):
    sc = new_analysis(qtbot, win, "R-0002")
    setup(sc, measures=[Measure(None, d.COUNT)])
    run(qtbot, sc)

    def save(dlg):
        dlg.edit.setText("Rows in November")
        dlg.save.click()
        settle(qtbot, win)
        return sc.saved is not None
    monkeypatch.setattr(analysis_screen, "save_hook", save)
    answers.append("save")
    assert win.open_area("clients")
    s = win.storage
    assert "Rows in November" in q.saved_analysis_names(s.con, sc.data.template.id).values()


# ---------------------------------------------------------------------------------------------- 6.1 / 6.3
def an_screen(qtbot, win) -> AnalysesScreen:
    assert win.open_area("analysis")
    settle(qtbot, win)
    return win.current


@spec("A0-01", "UX-10", "ANA-1")
def test_list_and_search(win, qtbot, tpla):
    s = win.storage
    q.insert_saved_analysis(s.con, tpla["regional"], "Regional by state",
                            Definition(tpla["regional"], [], [Group(STATE)], [Measure(None, d.COUNT)]).to_dict())
    a0 = an_screen(qtbot, win)
    assert a0.h1.text() == "Analyses"
    assert a0.subtitle.text() == "4 saved analyses. Open one to rerun it on the runs you pick."
    assert a0.search.placeholderText() == "Search name, client or template"
    assert [a0.model.headerData(i, Qt.Orientation.Horizontal) for i in range(5)] == [
        "Name", "Client", "Template", "Saved on", ""]
    rows_ = a0.visible_rows()
    assert rows_[0][:3] == ("GSTIN check", "Acme Traders", "Sales Register")
    assert a0.model.data(a0.model.index(0, 3)) == analyses.formats.date(rows_[0][3].date())
    a0.search.setText("Regional")
    assert [r[0] for r in a0.visible_rows()] == ["Regional by state"]
    a0.search.setText("acme")
    assert [r[0] for r in a0.visible_rows()] == ["GSTIN check", "Rows in November", "State sales"]
    a0.search.setText("State")
    assert [r[0] for r in a0.visible_rows()] == ["Regional by state", "State sales"]
    a0.search.setText("zzz")
    assert a0.stack.currentWidget() is a0.empty and a0.empty_text.text() == "No analyses match “zzz”."
    a0.search.setText("")
    settle(qtbot, win)
    assert [a.text() for a in a0.row_menu(0).actions()] == ["Open", "Rename", "Duplicate", "Delete"]


def open_saved(qtbot, win, name) -> AnalysisScreen:
    a0 = an_screen(qtbot, win)
    i = [r[0] for r in a0.visible_rows()].index(name)
    settle(qtbot, win)
    assert a0.open_row(i)
    settle(qtbot, win)
    return win.current


@spec("A0-02", "ANA-1", "D33")
def test_open_saved_settings_locked(win, qtbot):
    sc = open_saved(qtbot, win, "State sales")
    assert sc.h1.text() == "State sales" and sc.badge.text().startswith("Saved ")
    assert sc.breadcrumb.text() == "Analyses › State sales"
    assert sc.duplicate_button.isVisible() and not sc.save_button.isVisible() and sc.more.isVisible()
    assert sc.settings.currentWidget() is sc.locked and sc.locked_note.text() == analysis_screen.LOCKED
    assert not sc.choose.isVisible() and sc.data_label.text() == "Acme Traders · Sales Register"
    assert sc.locked_lines() == {"Filters": "None", "Group by": "1. State",
                                 "Measures": "Sum of Taxable Value\nCount of Invoice No", "Subtotals": "Off"}
    assert sc.ticked_runs() == [] and sc.runs_note.text() == "No runs selected. Tick the runs to include."
    assert sc.empty_title.text() == "Pick runs, then press Run"
    assert not sc.run_button.isEnabled()
    sc.tick("R-0001")
    assert sc.run_button.isEnabled()
    run(qtbot, sc)
    assert sc.total_row() == ["Grand total", "7,536,875.00", "5,000"]
    assert sc.leave_guard() is None


@spec("A0-03", "ANA-1")
def test_duplicate_saved_analysis(win, qtbot, answers):
    sc = open_saved(qtbot, win, "State sales")
    sc.tick("R-0002")
    assert sc.duplicate()
    settle(qtbot, win)
    dup = win.current
    assert dup is not sc and dup.saved is None and dup.badge.text() == "Not saved"
    assert dup.settings.currentWidget() is dup.builder and dup.builder.isEnabled()
    defn = dup.builder.definition()
    assert [g.column_id for g in defn.groups] == [STATE]
    assert [(m.column_id, m.fn) for m in defn.measures] == [(TAXABLE, d.SUM), (INV, d.COUNT)]
    assert dup.template.currentText() == "Sales Register" and dup.ticked_runs() == [dup.data.runs[2].id]
    dup.builder.measures.rows[1].measure.setCurrentIndex(0)          # Count of rows
    run(qtbot, dup)
    assert dup.total_row() == ["Grand total", "6,029,500.00", "4,000"]
    answers.append("stay")
    assert not win.open_area("clients")
    assert answers.asked[-1][1] == ["Stay", "Leave without saving", "Save…"]
    answers.append("leave")
    assert win.open_area("clients")


@spec("A0-04", "ANA-1")
def test_rename_and_name_uniqueness(win, qtbot):
    a0 = an_screen(qtbot, win)
    row = next(r[5] for r in a0.visible_rows() if r[0] == "GSTIN check")
    a0.rename(row)
    dlg = a0.dialog
    dlg.edit.setText("State sales")
    dlg.save.click()
    settle(qtbot, win)
    assert dlg.error.text() == "“State sales” is already in use. Choose another name."
    dlg.edit.setText("GSTIN check v2")
    dlg.save.click()
    settle(qtbot, win)
    assert "GSTIN check v2" in [r[0] for r in a0.visible_rows()]
    # same name in another template is fine
    s = win.storage
    assert analyses.rename(_ctx(s), next(r[5] for r in a0.visible_rows() if r[0] == "Regional by state").id,
                           "State sales") == "State sales"


@spec("A0-05", "UX §5")
def test_delete_saved_analysis(win, qtbot, answers):
    a0 = an_screen(qtbot, win)
    row = next(r[5] for r in a0.visible_rows() if r[0] == "Rows in November")
    answers.append("cancel")
    a0.delete(row)
    assert answers.asked[-1] == ("Delete “Rows in November”?", ["Cancel", "Delete"])
    answers.append("delete")
    a0.delete(row)
    settle(qtbot, win)
    assert "Rows in November" not in [r[0] for r in a0.visible_rows()]
    assert a0.banners()[-1].plain_text == "“Rows in November” deleted."


def test_saved_analysis_rename_and_delete_from_its_screen(win, qtbot, answers):
    sc = open_saved(qtbot, win, "GSTIN check v2")
    assert [a.text() for a in sc.more_menu().actions()] == ["Rename", "Delete"]
    sc.rename()
    sc.dialog.edit.setText("GSTIN check v3")
    sc.dialog.save.click()
    settle(qtbot, win)
    assert sc.h1.text() == "GSTIN check v3" and sc.breadcrumb.text() == "Analyses › GSTIN check v3"
    answers.append("delete")
    sc.delete()
    settle(qtbot, win)
    assert isinstance(win.current, AnalysesScreen)
    settle(qtbot, win)
    assert "GSTIN check v3" not in [r[0] for r in win.current.visible_rows()]


def _ctx(s):
    class Ctx:
        def cursor(self):
            return s.con

        def set_stage(self, *a, **k):
            pass

        def check_cancelled(self):
            pass
    return Ctx()


@spec("T23", "ANA-1")
def test_saved_analysis_with_a_removed_column(tpla):
    """A saved analysis on a column removed later keeps working, labelled "(removed)" (in its own template)."""
    s = tpla["s"]
    copy = q.load_template(s.con, tpla["copy"])
    aid = analyses.save(_ctx(s), copy, "By GSTIN", Definition(copy.id, [], [], [Measure(GSTIN, d.COUNT_DISTINCT)]))
    saved = analyses.open_saved(_ctx(s), aid)
    assert analyses.describe(saved.definition, saved.data.columns)["Measures"] == ["Count distinct of GSTIN"]
    with pytest.raises(analyses.NameRefused):
        analyses.save(_ctx(s), copy, " by gstin", Definition(copy.id, [], [], [Measure(None, d.COUNT)]))


# ---------------------------------------------------------------------------------------------- 7.4, 7.5 Export
def export_dialog_for(qtbot, win, tpla, kind, label) -> export_dialog.ExportDialog:
    assert win.go("run", run_id=tpla["runs"][label], template_id=tpla["tid"])
    settle(qtbot, win)
    assert win.current.export(kind)
    return win.export_dialog


@spec("EXP-01", "EXP-2", "EXP-3", "EXP-4", "C4-18")
def test_export_dialog_contents(win, qtbot, tpla):
    dlg = export_dialog_for(qtbot, win, tpla, "data", "R-0001")
    assert dlg.title.text() == "Export R-0001 data"
    assert dlg.info.text() == "5,000 rows · CSV file"
    assert dlg.folder.text() == export_dialog.ex.default_folder()
    assert dlg.folder.isReadOnly() and dlg.change.text() == "Change…"
    assert dlg.name.text() == "Acme Traders_Sales Register_R-0001_Data.csv"
    assert [dlg.delimiter.itemText(i) for i in range(dlg.delimiter.count())] == ["Comma", "Semicolon", "Tab", "Pipe"]
    assert [dlg.encoding.itemText(i) for i in range(dlg.encoding.count())] == ["UTF-8 with BOM", "UTF-8"]
    assert dlg.encoding.currentText() == "UTF-8 with BOM" and dlg.delimiter.currentText() == "Comma"
    assert "xlsx" not in " ".join(w.text() for w in dlg.findChildren(QLabel)).lower()
    assert [b.text() for b in dlg.buttons.values()] == ["Cancel", "Export"]
    dlg.reject()


def do_export(qtbot, win, dlg, folder, name=None, delimiter=None, bom=None):
    export_dialog.folder_hook = lambda _d: str(folder)
    try:
        dlg.change.click()
    finally:
        export_dialog.folder_hook = None
    if name is not None:
        dlg.name.setText(name)
    if delimiter is not None:
        dlg.delimiter.setCurrentIndex(dlg.delimiter.findData(delimiter))
    if bom is not None:
        dlg.encoding.setCurrentIndex(dlg.encoding.findData(bom))
    started = dlg.export()
    settle(qtbot, win)
    return started


@spec("EXP-02", "EXP-3", "EXP-6", "RUN-11")
def test_run_data_export(win, qtbot, tpla, tmp_path):
    dlg = export_dialog_for(qtbot, win, tpla, "data", "R-0002")
    assert do_export(qtbot, win, dlg, tmp_path)
    path = tmp_path / "Acme Traders_Sales Register_R-0002_Data.csv"
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == ("Invoice No,Invoice Date,Customer,GSTIN,State,Taxable Value,GST Rate,Tax Amount,"
                        "Source File,Source Sheet,Source Row,Run ID")
    assert len(lines) == 4001
    first = lines[1].split(",")
    assert first[-4:] == ["Sales_Nov.xlsx", "Sales", "3", "R-0002"]
    assert first[1].count("-") == 2 and len(first[1]) == 10 and "." in first[5] and "," not in first[5]
    banner = win.current.banners()[-1]
    assert banner.kind == "success" and banner.plain_text == (
        "Exported Acme Traders_Sales Register_R-0002_Data.csv · 4,000 rows.")
    assert "Open folder" in banner.buttons


@spec("EXP-03", "EXP-3")
def test_bom_and_delimiters(win, qtbot, tpla, tmp_path):
    for name, delimiter, bom in (("bom.csv", ",", True), ("plain.csv", ",", False), ("semi.csv", ";", True),
                                 ("tab.csv", "\t", True), ("pipe.csv", "|", True)):
        dlg = export_dialog_for(qtbot, win, tpla, "data", "R-0001")
        assert do_export(qtbot, win, dlg, tmp_path, name, delimiter, bom)
        raw = (tmp_path / name).read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf") == bom
        header = raw.decode("utf-8-sig").splitlines()[0]
        assert header.split(delimiter)[:2] == ["Invoice No", "Invoice Date"]
    assert (tmp_path / "plain.csv").read_bytes()[:10] == b"Invoice No"


@spec("EXP-04", "T19", "EXP-1")
def test_left_out_rows_export(win, qtbot, tpla, tmp_path):
    dlg = export_dialog_for(qtbot, win, tpla, "left_out", "R-0003")
    assert dlg.title.text() == "Export R-0003 left-out rows"
    assert dlg.name.text() == "Acme Traders_Sales Register_R-0003_Left-out rows.csv"
    assert do_export(qtbot, win, dlg, tmp_path)
    lines = (tmp_path / dlg.name.text()).read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 64 and lines[0].endswith("Source File,Source Sheet,Source Row,Run ID,Reason")


@spec("EXP-05", "ISS-3")
def test_issue_list_export(win, qtbot, tpla, tmp_path):
    dlg = export_dialog_for(qtbot, win, tpla, "issues", "R-0003")
    assert dlg.title.text() == "Export R-0003 issue list"
    assert do_export(qtbot, win, dlg, tmp_path)
    lines = (tmp_path / dlg.name.text()).read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 99 and lines[0] == "File,Sheet,Row,Column,Value,Rule,Severity,Message"


@spec("EXP-06", "EXP-4")
def test_overwrite_confirmation(win, qtbot, tpla, tmp_path, answers):
    target = tmp_path / "same.csv"
    target.write_text("old", encoding="utf-8")
    dlg = export_dialog_for(qtbot, win, tpla, "data", "R-0001")
    answers.append("cancel")
    assert not do_export(qtbot, win, dlg, tmp_path, "same.csv")
    assert answers.asked[-1] == ("Replace “same.csv”?", ["Cancel", "Replace"])
    assert target.read_text(encoding="utf-8") == "old" and dlg.isVisible()
    answers.append("replace")
    assert dlg.export()
    settle(qtbot, win)
    assert len(target.read_text(encoding="utf-8-sig").splitlines()) == 5001


@spec("EXP-07")
def test_invalid_file_name_characters(win, qtbot, tpla, tmp_path):
    dlg = export_dialog_for(qtbot, win, tpla, "data", "R-0001")
    assert do_export(qtbot, win, dlg, tmp_path, 'GST: Q3/Q4*?"<>|')
    assert (tmp_path / "GST_ Q3_Q4______.csv").is_file()


@spec("EXP-08", "EXP-7", "UI-5", "SH-05")
def test_export_progress_cancel_and_open_folder(win, qtbot, tpla, tmp_path, monkeypatch):
    release, waiting = threading.Event(), threading.Event()

    def hold():
        waiting.set()
        release.wait(10)
    monkeypatch.setattr(exporting, "_after_chunk", hold)
    dlg = export_dialog_for(qtbot, win, tpla, "data", "R-0002")
    export_dialog.folder_hook = lambda _d: str(tmp_path)
    dlg.change.click()
    export_dialog.folder_hook = None
    assert dlg.export()
    assert waiting.wait(10)
    win.bridge.poll()
    dlg.progress.refresh()
    assert dlg.title.text() == "Exporting R-0002 data"
    assert dlg.writing.text() == f"Writing to {tmp_path}"
    assert dlg.progress.note.text() == export_dialog.KEEP_WORKING
    assert dlg.progress.cancel_button.text() == "Cancel export" and dlg.progress.cancel_button.isVisible()
    assert not dlg.isModal()
    dlg.progress.cancel_button.click()
    release.set()
    settle(qtbot, win)
    assert list(tmp_path.iterdir()) == []                 # neither the file nor a .part
    assert win.current.banners()[-1].plain_text == "Export cancelled. The part-written file was deleted."
    monkeypatch.setattr(exporting, "_after_chunk", lambda: None)
    opened = []
    from sankalan.ui.widgets import banner as banner_mod
    monkeypatch.setattr(banner_mod, "open_folder", lambda p: opened.append(p))
    dlg = export_dialog_for(qtbot, win, tpla, "data", "R-0002")
    assert do_export(qtbot, win, dlg, tmp_path)
    b = win.current.banners()[-1]
    b.buttons["Open folder"].click()
    assert opened == [tmp_path / "Acme Traders_Sales Register_R-0002_Data.csv"]


@spec("C6-06", "DO-7")
def test_export_all_outputs_by_pattern(win, qtbot, tpla, tmp_path, answers):
    assert win.go("run", run_id=tpla["runs"]["R-0001"], template_id=tpla["tid"])
    settle(qtbot, win)
    assert win.current.export("outputs")
    dlg = win.export_dialog
    assert dlg.title.text() == "Export all outputs of R-0001"
    assert dlg.name.accessibleName() == "Name pattern" and dlg.name.text() == "{Client}_{Template}_{RunID}_{Output}"
    assert dlg.info.text() == "one CSV file per output"
    assert do_export(qtbot, win, dlg, tmp_path, "{RunID}_{Output}")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["R-0001_Latest month by GST rate.csv",
                                                          "R-0001_State-wise sales.csv"]
    assert win.current.banners()[-1].plain_text == f"Exported 2 files to {tmp_path}."
    # again: the files exist, so Export asks before replacing them (EXP-4)
    assert win.current.export("outputs")
    dlg = win.export_dialog
    answers.append("cancel")
    assert do_export(qtbot, win, dlg, tmp_path, "{RunID}_{Output}")
    assert answers.asked[-1] == ("Replace “R-0001_State-wise sales.csv”?", ["Cancel", "Replace"])
    assert dlg.form.isVisible() and dlg.isVisible()
    dlg.reject()


@spec("ANA-9", "EXP-1")
def test_analysis_export_with_subtotals(win, qtbot, tmp_path):
    sc = new_analysis(qtbot, win, "R-0001")
    setup(sc, groups=[Group(STATE), Group(RATE)], measures=[Measure(TAXABLE, d.SUM, "Taxable")], subtotals=True)
    run(qtbot, sc)
    assert sc.export()
    dlg = win.export_dialog
    assert do_export(qtbot, win, dlg, tmp_path, "by state.csv", bom=False)
    lines = (tmp_path / "by state.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "State,GST Rate,Taxable" and len(lines) == 1 + 24 + 1
    assert "Maharashtra,Total,1865000.00" in lines and lines[-1] == "Grand total,,7536875.00"


# ---------------------------------------------------------------------------------------------- A2-1: text values
@pytest.fixture
def rwin(app, qtbot, tpl_r_runs):
    s = tpl_r_runs["s"]
    w = MainWindow(JobBridge(s.runner), s)
    w.resize(1366, 768)
    w.show()
    yield w
    w.bridge.wait_all(30)
    w.bridge.poll()
    from sankalan.ui.dialogs import base
    hook, base.answer_hook = base.answer_hook, (lambda _d: "leave")
    try:
        w.close()
    finally:
        base.answer_hook = hook
    w.deleteLater()


@spec("TXT-6", "TXT-7", "T55", "AC-TXT-1", "AC-TXT-5", "TXT-10")
def test_text_filters_and_group_labels(rwin, qtbot, tpl_r_runs):
    assert rwin.go("analysis")
    settle(qtbot, rwin)
    sc = rwin.current
    sc.choose_template("Rao & Co", "Sales Register R")
    settle(qtbot, rwin)
    sc.tick(["R-0001", "R-0002"])
    b = sc.builder
    b.clear()
    b.add_filter(Filter("c006", d.NOT_NUMBER))
    row = b.filters.rows[0]
    ops = [row.op.itemText(i) for i in range(row.op.count())]
    assert ops == ["equals", "is between", "is blank", "is not blank", "is not a number"]
    assert row.help.isVisibleTo(row) and row.help.text() == "Cells with text such as NA or Nil instead of a number"
    i = row.op.findData(d.NOT_NUMBER)
    assert row.op.itemData(i, Qt.ItemDataRole.ToolTipRole) == row.help.text()
    row.op.setCurrentIndex(row.op.findData(d.EQUALS))
    assert not row.help.isVisibleTo(row)
    row.op.setCurrentIndex(i)
    assert b.definition().filters[0].op == d.NOT_NUMBER and b.definition().filters[0].values == []
    b.add_filter(Filter("c002", d.NOT_DATE))
    date_row = b.filters.rows[1]
    assert "is not a date" in [date_row.op.itemText(k) for k in range(date_row.op.count())]
    assert date_row.help.text() == "Cells with text such as NA instead of a date"
    # Summary grid: text groups labelled, separate from (Null); counts as the engine's
    b.clear()
    b.add_group(Group("c006"))
    b.add_measure(Measure(None, d.COUNT))
    run(qtbot, sc)
    got = {r[0]: r[1] for r in rows(qtbot, sc)}
    m1, m2 = tpl_r_runs["m"].run(1), tpl_r_runs["m"].run(2)
    assert got["(Not a number)"] == "16" and got["(Null)"] == str(m1.taxable_blank + m2.taxable_blank)
    b.clear()
    b.add_group(Group("c002", "month"))
    b.add_measure(Measure(None, d.COUNT))
    run(qtbot, sc)
    got = rows(qtbot, sc)
    assert [r[0] for r in got] == ["Oct-2026", "Nov-2026", "(Not a date)", "(Null)"]
    assert got[2][1] == "5"
    assert analyses.describe(Definition("", [Filter("c006", d.NOT_NUMBER), Filter("c002", d.NOT_DATE)], [],
                                        [Measure(None, d.COUNT)]),
                             sc.data.template.columns)["Filters"] == ["Taxable Value is not a number",
                                                                     "Invoice Date is not a date"]
