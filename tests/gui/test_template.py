"""Phase 7: Template screen (3.1 to 3.4): C4-01 to C4-18 on TPL-A with R-0001 to R-0003 committed through the real
pipeline. Tests run in file order: the editing tests near the end change the template (C4-16 removes GSTIN last)."""
import datetime as dt
from decimal import Decimal

import pytest

from conftest import OVERRIDE_REASON, commit_tpl_a_run, open_storage, settle_window, spec, tpl_a_template
from sankalan import formats
from sankalan.model import definition as d
from sankalan.model import export as ex
from sankalan.model.definition import Definition, Group, FlatMeasure, cards
from sankalan.model.rule import NOT_BLANK, WARNING
from sankalan.query import catalogue as q
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens import template_outputs
from sankalan.ui.screens.template import COLUMNS_TAB, OUTPUTS, RUNS, SETTINGS, TemplateScreen
from sankalan.ui.window import MainWindow

D = Decimal
INV, DATE_, CUST, GSTIN, STATE, TAXABLE, RATE, TAX = (f"c00{i}" for i in range(1, 9))


def settle(qtbot, w, timeout=20_000):
    settle_window(qtbot, w, timeout)


@pytest.fixture(scope="module")
def tpla(tmp_path_factory, fixtures_dir):
    s = open_storage(tmp_path_factory.mktemp("tpla"))
    acme = q.insert_client(s.con, "Acme Traders")
    tid = q.create_template(s.con, tpl_a_template(acme))
    runs = [commit_tpl_a_run(s, tid, fixtures_dir, "Sales_Oct.xlsx", comment="October sales, first load"),
            commit_tpl_a_run(s, tid, fixtures_dir, "Sales_Nov.xlsx"),
            commit_tpl_a_run(s, tid, fixtures_dir, "Sales_Errors.xlsx", reason=OVERRIDE_REASON)]
    yield {"storage": s, "tid": tid, "client": acme, "runs": runs}
    s.close()


@pytest.fixture
def screen(app, qtbot, tpla):
    s = tpla["storage"]
    w = MainWindow(JobBridge(s.runner), s)
    qtbot.addWidget(w)
    w.resize(1366, 768)
    w.show()
    w.go("template", template_id=tpla["tid"], name="Sales Register")
    settle(qtbot, w)
    sc = w.current
    assert isinstance(sc, TemplateScreen)
    yield sc
    w.bridge.wait_all(30)                 # pytest-qt has closed the window by now; Jobs still finish


def go_tab(qtbot, sc, index):
    sc.select_tab(index)
    settle(qtbot, sc.window_)
    assert sc.pages.currentIndex() == index


# ---------------------------------------------------------------------------------------------- 3.1 Runs
@spec("C4-01", "UX-4")
def test_header_and_summary(screen, tpla):
    s = tpla["storage"]
    last = q.latest_run(s.con, tpla["tid"])[3]
    size = screen.detail.size_bytes
    assert screen.breadcrumb.text() == "Clients › Acme Traders › Sales Register"
    assert screen.h1.text() == "Sales Register"
    assert screen.new_run_button.property("kind") == "primary"
    assert screen.subtitle.text() == (f"3 runs · 10,937 rows · {formats.gigabytes(size)} · last loaded "
                                      f"{formats.date_time(last)}")
    assert [screen.tabs.tabText(i) for i in range(4)] == ["Runs", "Default outputs  2", "Columns and rules",
                                                          "Settings"]


@spec("C4-02", "RUN-2")
def test_runs_grid(screen):
    tab = screen.runs_tab
    m = tab.model
    assert [c.title for c in m.columns] == ["Run ID", "Loaded on", "Files", "Rows", "Issues", "Status", "Comment", ""]
    shown = [[m.data(m.index(r, c)) for c in range(7)] for r in range(m.rowCount())]
    assert [r[0] for r in shown] == ["R-0003", "R-0002", "R-0001"]
    assert shown[2][2:6] == ["1 file", "5,000", "0 errors · 0 warnings", "Committed"]
    assert shown[1][2:6] == ["1 file", "4,000", "0 errors · 0 warnings", "Committed"]
    assert shown[0][2:7] == ["1 file", "1,937", "66 errors · 32 warnings", "Committed with override", OVERRIDE_REASON]
    from PySide6.QtCore import Qt
    assert m.data(m.index(0, 2), Qt.ItemDataRole.ToolTipRole) == "Sales_Errors.xlsx"
    assert m.data(m.index(0, 6), Qt.ItemDataRole.ToolTipRole) == OVERRIDE_REASON


@spec("C4-03")
def test_search_runs(screen, qtbot):
    tab = screen.runs_tab
    for text, expect in (("Errors", [3]), ("Oct", [1]), ("revised", [3]), ("nothing like this", [])):
        tab.search.setText(text)
        settle(qtbot, screen.window_)
        assert [r[0] for r in tab.visible_rows()] == expect, text
    tab.search.clear()


@spec("C4-04", "T19")
def test_run_row_menu_and_export_prefill(screen, qtbot, answers, tpla):
    tab = screen.runs_tab
    menu = tab.row_menu(0)
    assert [a.text() for a in menu.actions()] == ["Open", "Export data", "Export issue list", "Export left-out rows",
                                                  "Delete"]
    menu.actions()[1].trigger()                          # Export data (C4-18 prefill)
    req = screen.window_.last_export
    folder = ex.default_folder()
    assert (req.kind, req.folder, req.file_name) == ("data", folder, "Acme Traders_Sales Register_R-0003_Data.csv")
    assert req.options == ex.ExportOptions(",", True) and req.run_id == tpla["runs"][2].run_id


# ---------------------------------------------------------------------------------------------- 3.2 Default outputs
@spec("C4-05", "UX-5", "DO-8")
def test_outputs_list_and_preview_on_latest_run(screen, qtbot):
    go_tab(qtbot, screen, OUTPUTS)
    tab = screen.outputs_tab
    assert [i.name.text() for i in tab.items()] == ["State-wise sales", "Latest month by GST rate"]
    assert tab.bar.note.text() == "Changes apply to future runs. Outputs already saved with earlier runs don't change."
    tab.preview()
    settle(qtbot, screen.window_)
    rows = tab.preview_rows()                             # RUNO-03 figures: the latest run is R-0003
    assert rows == [["Delhi", "739,448.00", "93,038.02", "480"], ["Goa", "28,075.00", "3,572.83", "25"],
                    ["Gujarat", "725,157.00", "93,821.11", "476"], ["Karnataka", "734,282.00", "94,229.23", "480"],
                    ["Maharashtra", "720,032.00", "90,333.16", "476"],
                    ["Grand total", "2,946,994.00", "374,994.35", "1,937"]]
    assert tab.preview_info.text().startswith("On R-0003 · 1,937 rows · 5 result rows · ")
    tab.select(1)
    tab.preview()
    settle(qtbot, screen.window_)
    rows = tab.preview_rows()
    assert rows[0] == ["Sep-2026", "0", "578,776.25"] and rows[5] == ["Sep-2026", "Total", "2,946,994.00"]


@spec("AC-MEA-8", "MEA-8", "T51", "3.2")
def test_preview_header_rename_marks_the_tab_changed(screen, qtbot, answers):
    go_tab(qtbot, screen, OUTPUTS)
    tab = screen.outputs_tab
    tab.select(0)
    tab.preview()
    settle(qtbot, screen.window_)
    hh = tab.table.horizontalHeader()

    def headers():
        return [tab.table.horizontalHeaderItem(i).text() for i in range(tab.table.columnCount())]
    assert headers() == ["State", "Taxable", "Tax", "Invoices"] and not tab.dirty
    assert not hh.renamable(0) and all(hh.renamable(i) for i in (1, 2, 3))
    assert [hh._tooltip(i) for i in range(4)] == [None, "Taxable Value · Sum", "Tax Amount · Sum",
                                                  "Invoice No · Count"]
    tab.rename_header(3, "taxable")
    assert hh.editor is not None and hh.error.text() == "Another column is already called taxable"
    hh.finish()
    assert not tab.dirty
    tab.rename_header(3, "Invoice count")
    assert headers() == ["State", "Taxable", "Tax", "Invoice count"] and hh.editor is None
    assert tab.dirty and tab.table.isEnabled() and tab.preview_info.text() != template_outputs.STALE
    assert tab.outputs[0].definition["measures"][2]["ops"] == [{"fn": "count", "name": "Invoice count"}]
    card = tab.builder.add_card(CUST)                   # AC-MEA-4: Preview shows the check and starts nothing
    tab.preview()
    assert card.error.text() == "Tick at least one operation for Customer, or remove it" and tab.progress.isHidden()
    answers.append("discard")
    screen.select_tab(RUNS)
    settle(qtbot, screen.window_)
    assert answers.asked[-1] == ("Save your changes?", ["Stay", "Discard", "Save"])
    assert screen.pages.currentIndex() == RUNS and not tab.dirty
    assert tab.outputs[0].definition["measures"][2]["ops"] == [{"fn": "count", "name": "Invoices"}]


@spec("C4-08", "UX §5")
def test_unsaved_outputs_prompt(screen, qtbot, answers):
    go_tab(qtbot, screen, OUTPUTS)
    tab = screen.outputs_tab
    tab.select(0)
    tab.builder.measures.cards[0].tick(d.MAX)
    assert tab.dirty and tab.bar.dirty_label.isVisible()
    answers.append("stay")
    screen.select_tab(RUNS)
    assert screen.pages.currentIndex() == OUTPUTS and tab.builder.measures.cards[0].ticked() == [d.SUM, d.MAX]
    assert answers.asked[-1] == ("Save your changes?", ["Stay", "Discard", "Save"])
    answers.append("discard")
    screen.select_tab(RUNS)
    settle(qtbot, screen.window_)
    assert screen.pages.currentIndex() == RUNS and not tab.dirty
    assert tab.outputs[0].definition["measures"][0]["ops"] == [{"fn": "sum", "name": "Taxable"}]
    go_tab(qtbot, screen, OUTPUTS)
    tab.builder.measures.cards[0].tick(d.MAX)
    answers.append("save")
    screen.select_tab(RUNS)
    settle(qtbot, screen.window_)
    assert screen.pages.currentIndex() == RUNS and not tab.dirty
    t = q.load_template(screen.storage.con, screen.template_id)
    assert t.outputs[0].definition["measures"][0]["ops"] == [{"fn": "sum", "name": "Taxable"},
                                                             {"fn": "max", "name": None}]
    # put it back
    go_tab(qtbot, screen, OUTPUTS)
    tab.select(0)
    tab.builder.measures.cards[0].tick(d.MAX, False)
    tab.save()
    settle(qtbot, screen.window_)


@spec("C4-06", "C4-07", "DO-6", "DO-1")
def test_edit_and_reorder_outputs_future_runs_only(screen, qtbot, tpla):
    go_tab(qtbot, screen, OUTPUTS)
    tab = screen.outputs_tab
    con = screen.storage.con
    v = q.template_version(con, screen.template_id)
    tab.select(0)
    card = tab.builder.add_measure(FlatMeasure(CUST, d.COUNT_DISTINCT, "Customers"))
    assert card.name.text() == "Customer" and card.ticked() == [d.COUNT_DISTINCT]
    tab.move(1, -1)                                   # C4-07: DO2 above DO1
    assert [i.name.text() for i in tab.items()] == ["Latest month by GST rate", "State-wise sales"]
    tab.save()
    settle(qtbot, screen.window_)
    t = q.load_template(con, screen.template_id)
    assert q.template_version(con, screen.template_id) == v + 1
    assert [o.name for o in t.outputs] == ["Latest month by GST rate", "State-wise sales"]
    assert [o["name"] for m in t.outputs[1].definition["measures"] for o in m["ops"]] == [
        "Taxable", "Tax", "Invoices", "Customers"]
    saved = q.run_outputs(con, tpla["runs"][0].run_id)            # R-0001's saved DO1 keeps 3 measures (DO-6)
    assert [len(o.definition["measures"]) for o in saved] == [3, 1]
    tab.move(1, -1)                                               # restore the order
    tab.save()
    settle(qtbot, screen.window_)
    assert [o.name for o in q.load_template(con, screen.template_id).outputs] == ["State-wise sales",
                                                                                   "Latest month by GST rate"]


def test_output_checks(screen, qtbot):
    go_tab(qtbot, screen, OUTPUTS)
    tab = screen.outputs_tab
    tab.add_output()
    assert tab.outputs[-1].name == "New output" and tab.dirty
    tab.name.setText("State-wise sales")
    tab.name.textEdited.emit("State-wise sales")
    tab.save()
    assert "Two default outputs are named" in tab.error.text()
    tab.delete(2)
    tab.save()
    settle(qtbot, screen.window_)
    assert not tab.dirty and len(q.load_template(screen.storage.con, screen.template_id).outputs) == 2
    from sankalan.ui.widgets.builder import FilterRow
    tab.select(0)
    f = tab.builder.add_filter()
    f.column.setCurrentIndex(f.column.findData(DATE_))
    ops = [f.op.itemData(i) for i in range(f.op.count())]
    assert ops == [d.LATEST_MONTH, d.LATEST_QUARTER, d.LATEST_YEAR, d.BLANK, d.NOT_BLANK, d.NOT_DATE]  # DO-3, T55
    assert isinstance(f, FilterRow)
    tab.discard()


# ---------------------------------------------------------------------------------------------- 3.3 Columns and rules
@spec("C4-09", "C4-10", "UX-6", "TPL-9", "MAP-12")
def test_columns_layout_and_locks(screen, qtbot):
    go_tab(qtbot, screen, COLUMNS_TAB)
    tab = screen.columns_tab
    rows = tab.list_rows()
    assert rows[0] == ("Invoice No", "Text", "3", "0")
    assert rows[5] == ("Taxable Value", "Number", "2", "0")
    assert [r[0] for r in rows] == ["Invoice No", "Invoice Date", "Customer", "GSTIN", "State", "Taxable Value",
                                    "GST Rate", "Tax Amount"]
    assert tab.test_button.text() == "Test rules on latest run" and tab.add_button.text() == "+ Add column"
    tab.select(TAXABLE)
    assert not tab.type.isEnabled() and not tab.decimals.isEnabled() and tab.fixed.isVisible()
    assert tab.fixed.text() == "Fixed after the first run" and tab.decimals.value() == 2
    assert [r[0] for r in tab.rule_rows()] == ["Is a number  Auto", "Number range"]
    tab.select(CUST)
    assert not tab.type.isEnabled()
    tab.type.setCurrentIndex(1)                              # a locked column ignores a type change
    assert tab.col(CUST).type == "Text"


@spec("C4-12", "VR-8")
def test_test_rules_on_latest_run(screen, qtbot, tpla):
    go_tab(qtbot, screen, COLUMNS_TAB)
    tab = screen.columns_tab
    tab.test_rules()
    settle(qtbot, screen.window_)
    by_name = {}
    for cid in (STATE, CUST, INV, GSTIN, RATE, TAXABLE):
        for r in tab.column_rules(cid):
            by_name[(cid, r.name)] = tab.tested[r.id]
    assert by_name[(STATE, "Allowed values")] == 25 and by_name[(CUST, "Not blank")] == 7
    assert all(n == 0 for (cid, name), n in by_name.items()
               if next(r for r in tab.column_rules(cid) if r.name == name).severity == "Error")
    assert tab.test_info.text().startswith("Last tested on R-0003 · 1,937 rows · ")
    assert tab.test_info.text().endswith("Nothing is stored.")
    tab.select(STATE)
    assert tab.rule_rows()[0][3] == "25 rows fail"
    r3 = next(r for r in q.run_rows(screen.storage.con, screen.template_id) if r[1] == 3)
    assert (r3[5], r3[6]) == (66, 32)


@spec("C4-11", "MAP-3")
def test_aliases(screen, qtbot):
    go_tab(qtbot, screen, COLUMNS_TAB)
    tab = screen.columns_tab
    tab.select(INV)
    tab.aliases.edit.setText("Bill No")
    assert tab.aliases.add_typed()
    tab.aliases.edit.setText("customer")                     # another column's name: refused
    assert not tab.aliases.add_typed() and "already maps to Customer" in tab.aliases.error.text()
    tab.save()
    settle(qtbot, screen.window_)
    con = screen.storage.con
    assert q.load_template(con, screen.template_id).column(INV).aliases == ["Bill No"]
    tab.select(INV)
    tab.aliases.remove_value("Bill No")
    tab.save()
    settle(qtbot, screen.window_)
    assert q.load_template(con, screen.template_id).column(INV).aliases == []


@spec("C4-13", "MAP-8")
def test_rename_column_keeps_parquet(screen, qtbot, tpla):
    go_tab(qtbot, screen, COLUMNS_TAB)
    tab = screen.columns_tab
    data = screen.storage.folder.run_dir(screen.template_id, tpla["runs"][0].run_id) / "data.parquet"
    before = data.stat().st_mtime_ns
    tab.select(CUST)
    tab.name.setText("Customer Name")
    tab.name.textEdited.emit("Customer Name")
    tab.save()
    settle(qtbot, screen.window_)
    t = q.load_template(screen.storage.con, screen.template_id)
    assert t.column(CUST).name == "Customer Name" and data.stat().st_mtime_ns == before
    tab.select(CUST)
    tab.name.setText("Customer")
    tab.name.textEdited.emit("Customer")
    tab.save()
    settle(qtbot, screen.window_)


@spec("C4-15", "MAP-11")
def test_remove_column_used_by_output_refused(screen, qtbot):
    go_tab(qtbot, screen, COLUMNS_TAB)
    tab = screen.columns_tab
    tab.select(STATE)
    assert not tab.remove_selected()
    assert tab.error.text() == ("State can't be removed while the default output “State-wise sales” uses it. "
                                "Change that output first.")
    assert not tab.dirty


@spec("C4-14", "MAP-8", "MAP-11")
def test_add_column_null_in_older_runs(screen, qtbot, tpla):
    go_tab(qtbot, screen, COLUMNS_TAB)
    tab = screen.columns_tab
    tab.add_column()
    new = tab.selected
    assert tab.type.isEnabled() and new == "c009"
    tab.name.setText("Region Code")
    tab.name.textEdited.emit("Region Code")
    tab.type.setCurrentIndex(0)
    tab.add_rule(NOT_BLANK)
    tab.set_severity(next(r.id for r in tab.column_rules(new)), WARNING)
    tab.save()
    settle(qtbot, screen.window_)
    s = tpla["storage"]
    t = q.load_template(s.con, screen.template_id)
    assert t.column(new).name == "Region Code" and any(r.column_id == new and r.severity == WARNING for r in t.rules)
    from sankalan import analysis
    from sankalan.query import layer
    from conftest import run_job
    data = s.folder.run_dir(screen.template_id, tpla["runs"][0].run_id) / "data.parquet"
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(
        ctx, Definition(screen.template_id, [], [Group(new)], cards(FlatMeasure(INV, d.COUNT))), t.columns, [data]))
    assert layer.rows(s.con, res, subtotals=False) == [(1, None, 5000)]
    tab.select(new)
    assert tab.remove_selected()                  # locked now (the template has runs): kept as removed
    tab.save()
    settle(qtbot, screen.window_)
    t = q.load_template(s.con, screen.template_id)
    assert t.column(new).removed and not any(r.column_id == new for r in t.rules)
    assert "Region Code" not in [r[0] for r in tab.list_rows()]


# ---------------------------------------------------------------------------------------------- 3.4 Settings
@spec("C4-17", "UX-7", "TPL-1")
def test_settings_fields(screen, qtbot):
    go_tab(qtbot, screen, SETTINGS)
    tab = screen.settings_tab
    assert tab.name.text() == "Sales Register"
    assert tab.by_name.isChecked() and tab.sheet_names.values == ["Sales"]
    assert tab.csv_delimiter.currentText() == "Detect automatically"
    assert tab.csv_encoding.currentText() == "Detect automatically"
    assert tab.pattern.text() == "{Client}_{Template}_{RunID}_{Output}"
    assert tab.delimiter.currentText() == "Comma"
    assert tab.encoding.currentText() == "UTF-8 with BOM (opens cleanly in Excel)"
    assert [tab.encoding.itemText(i) for i in range(tab.encoding.count())] == [
        "UTF-8 with BOM (opens cleanly in Excel)", "UTF-8"]
    assert tab.dates.text() == "DD-MM-YYYY · same as the app"
    assert tab.example.text() == "Example: Acme Traders_Sales Register_R-0003_State-wise sales.csv"
    tab.by_name.setChecked(False)
    tab.first.setChecked(True)
    tab.by_name.setChecked(True)
    tab.sheet_names.remove_value("Sales")
    assert tab.check() == "Add at least one sheet name, or choose another option."
    tab.discard()
    assert tab.sheet_names.values == ["Sales"] and not tab.dirty


@spec("C4-18", "EXP-4")
def test_export_defaults_prefill(screen, qtbot, answers, tmp_path, tpla):
    go_tab(qtbot, screen, SETTINGS)
    tab = screen.settings_tab
    tab.chooser = lambda _parent, _start: str(tmp_path / "Exports")
    tab.pick_folder()
    tab.delimiter.setCurrentIndex(tab.delimiter.findData(";"))
    tab.save()
    settle(qtbot, screen.window_)
    t = q.load_template(screen.storage.con, screen.template_id)
    assert t.export["folder"] == str(tmp_path / "Exports") and t.export["delimiter"] == ";"
    run1 = tpla["runs"][0].run_id
    screen.export("data", run1, "R-0001")
    req = screen.window_.last_export
    assert req.folder == str(tmp_path / "Exports") and req.options.delimiter == ";"
    assert req.file_name == "Acme Traders_Sales Register_R-0001_Data.csv"


def test_rename_template_in_settings(screen, qtbot):
    go_tab(qtbot, screen, SETTINGS)
    tab = screen.settings_tab
    tab.name.setText("   ")
    tab.name.textEdited.emit("   ")
    tab.save()
    assert tab.error.text() == "Enter a template name."
    tab.name.setText("Sales Register 2026")
    tab.name.textEdited.emit("Sales Register 2026")
    tab.save()
    settle(qtbot, screen.window_)
    assert screen.h1.text() == "Sales Register 2026"
    assert screen.breadcrumb.text() == "Clients › Acme Traders › Sales Register 2026"
    tab.name.setText("Sales Register")
    tab.name.textEdited.emit("Sales Register")
    tab.save()
    settle(qtbot, screen.window_)


@spec("UI-8", "RUN-9")
def test_delete_run_dialog(screen, qtbot, tpla, fixtures_dir):
    s = tpla["storage"]
    extra = commit_tpl_a_run(s, screen.template_id, fixtures_dir, "Sales_NoDates.xlsx")
    screen.refresh()
    settle(qtbot, screen.window_)
    screen.delete_run(extra.run_id)
    settle(qtbot, screen.window_)
    dlg = screen.dialog
    assert dlg.windowTitle() == "Delete R-0004?"
    assert dlg.listed == ["500 rows", "The issue list", "2 saved outputs"]
    dlg.understand.setChecked(True)
    dlg.delete_button.click()
    settle(qtbot, screen.window_)
    assert [r[0] for r in screen.runs_tab.visible_rows()] == [3, 2, 1]
    assert not s.folder.run_dir(screen.template_id, extra.run_id).exists()


@spec("C4-16", "MAP-11", "T23")
def test_remove_column_used_only_in_saved_analysis(screen, qtbot, tpla):
    """Last: removes GSTIN from TPL-A."""
    s = tpla["storage"]
    an2 = Definition(screen.template_id, [], [], cards(FlatMeasure(GSTIN, d.COUNT_DISTINCT)))
    q.insert_saved_analysis(s.con, screen.template_id, "AN-2", an2.to_dict())
    go_tab(qtbot, screen, COLUMNS_TAB)
    tab = screen.columns_tab
    tab.select(GSTIN)
    assert tab.remove_selected()
    tab.save()
    settle(qtbot, screen.window_)
    t = q.load_template(s.con, screen.template_id)
    assert t.column(GSTIN).removed
    from sankalan import analysis
    from sankalan.query import layer
    from conftest import run_job
    data = s.folder.run_dir(screen.template_id, tpla["runs"][0].run_id) / "data.parquet"
    res = run_job(s.runner, lambda ctx: analysis.run_analysis(ctx, an2, t.columns, [data]))
    assert [c.label for c in res.columns] == ["GSTIN (removed) · Count distinct"]
    assert layer.grand_total(s.con, res) == (5000,)


@spec("UI-2", "FIT-04")
def test_template_tabs_fit_the_smallest_layout(screen, qtbot):
    """Every tab's minimum fits 1280×640; long panels scroll inside themselves."""
    from sankalan.ui import theme
    w = screen.window_
    for i in range(4):
        go_tab(qtbot, screen, i)
        hint = w.centralWidget().minimumSizeHint()
        assert hint.width() <= theme.MIN_LAYOUT.width() and hint.height() <= theme.MIN_LAYOUT.height(), (i, hint)
