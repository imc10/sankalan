"""End-to-end tests that drive the real desktop window (off-screen) the way an executive would."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

from conftest import spec, wait_idle
from sankalan.core.template import TemplateStore
from sankalan.demo import make_perf_set, make_sales_set, purchase_template, sales_template

SHOTS = Path(__file__).parent / "_artifacts" / "screens"


def btn(w, testid):
    for b in w.findChildren(QPushButton):
        if b.property("testid") == testid and b.isVisible():
            return b
    for b in w.findChildren(QPushButton):
        if b.property("testid") == testid:
            return b
    raise AssertionError(f"no button {testid}")


def click(qtbot, b):
    assert b.isEnabled(), b.text()
    qtbot.mouseClick(b, Qt.MouseButton.LeftButton)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.processEvents()
    page = w.stack.currentWidget()
    inner = page.widget()
    # capture the whole window and the full page content (scrolled area)
    w.grab().save(str(SHOTS / f"{name}.png"))


def save_tpl(window, t, out_dir=None):
    if out_dir:
        t.output["folder"] = str(out_dir)
    window.store.save(t)
    window.go_home()
    return t


def run_first_template(qtbot, window):
    home = window.pages["home"]
    assert home.table.rowCount() >= 1
    cell = home.table.cellWidget(0, 6)
    run = [b for b in cell.findChildren(QPushButton) if b.text() == "Run"][0]
    click(qtbot, run)
    assert window.current == "files"


def map_combo(window, target, file_stem):
    mp = window.pages["map"]
    cols = [mp.grid.horizontalHeaderItem(i).text() for i in range(mp.grid.columnCount())]
    rows = [mp.grid.item(r, 0).text() for r in range(mp.grid.rowCount())]
    return mp.grid.cellWidget(rows.index(target), cols.index(file_stem))


# ============================================================================== main flow
@spec("IN-1", "IN-11", "IN-12", "IN-13", "MAP-4", "MAP-5", "VAL-report", "VAL-severity", "D4",
      "OUT-9", "OUT-10", "OUT-11", "OUT-5", "TPL-6", "TPL-7", "NF-9")
def test_full_run_through_the_ui(qtbot, window, prompter, sales, out_dir):
    """Templates → Run → Add folder → fix mapping (save alias) → validation stops on 3 errors →
    export issues → fix source files → Re-check → Output → totals match → replace file → save template."""
    save_tpl(window, sales_template(), out_dir)
    shot(window, "1_home")
    run_first_template(qtbot, window)

    # --- step 2: add folder
    prompter.answers["folder"] = str(sales["folder"])
    click(qtbot, btn(window, "addFolder"))
    wait_idle(qtbot, window)
    fp = window.pages["files"]
    assert fp.table.rowCount() == 6
    statuses = {fp.table.item(r, 0).text(): fp.table.item(r, 5).text() for r in range(6)}
    assert statuses["Sales_Apr-2026.xlsx"] == "OK"
    assert "12 hidden rows skipped" in statuses["Sales_Jun-2026.xlsx"]
    assert 'hidden sheet "Old" skipped' in statuses["Sales_Aug-2026.xlsx"]
    assert "header found on row 3" in statuses["Sales_Jul-2026.xlsx"]
    assert "~$Sales_Sep-2026.xlsx (Excel lock file)" in fp.skipped_lbl.text()
    assert fp.total_lbl.text() == f"Total: {sales['rows']:,} rows from 6 files"
    jul_row = [fp.table.item(r, 0).text() for r in range(6)].index("Sales_Jul-2026.xlsx")
    fp.table.selectRow(jul_row)
    assert fp.preview.rowCount() == 200
    assert "row 3" in fp.pv_note.text()
    assert fp.preview.item(2, 7).text() == "Inv Amt" and fp.preview.item(2, 7).font().bold()
    shot(window, "2_add_files")

    # --- step 3: map
    click(qtbot, btn(window, "nextMap"))
    mp = window.pages["map"]
    assert mp.banner.title.text() == "6 of 7 output columns matched in every file."
    assert "Invoice Value has no match in Sales_Jul-2026.xlsx" in mp.banner.body.text()
    combo = map_combo(window, "Invoice Value", "Sales_Jul-2026")
    assert combo.currentText() == "Choose…" and "C42B1C" in combo.styleSheet()
    sep = map_combo(window, "GSTIN", "Sales_Sep-2026")
    assert sep.currentText() == "GST No  · alias"
    shot(window, "3_map_unmatched")
    prompter.answers["confirm"] = [True]            # "Map and save as alias"
    combo.setCurrentIndex(combo.findData("Inv Amt"))
    assert any(a[0] == "confirm" and "Save alias" in a[1] for a in prompter.asked)
    assert mp.banner.title.text() == "All 7 output columns matched in every file."
    assert window.session.new_aliases == [("Invoice Value", "Inv Amt")]

    # --- step 4: validate -> blocked
    click(qtbot, btn(window, "nextValidate"))
    wait_idle(qtbot, window)
    vp = window.pages["validate"]
    assert window.current == "validate"
    assert vp.banner.title.text() == "Output not written: 3 errors in 3 files"
    assert vp.t_err.value.text() == "3" and vp.t_warn.value.text() == "16"
    assert vp.t_rows.value.text() == f"{sales['rows']:,}"
    assert vp.t_hidden.value.text() == "12 rows, 1 sheet"
    assert vp.issues.rowCount() == 3
    assert {vp.issues.item(r, 2).text() for r in range(3)} == {"10", "214", "301"}
    assert not btn(window, "nextOutput").isVisible() and btn(window, "writeAnyway").isVisible()
    shot(window, "4_validate_errors")
    click(qtbot, btn(window, "filter_warning"))
    assert vp.issues.rowCount() == 16
    click(qtbot, btn(window, "filter_all"))
    assert vp.issues.rowCount() == 19
    export = out_dir / "issues.xlsx"
    prompter.answers["save_file"] = str(export)
    click(qtbot, btn(window, "exportIssues"))
    assert openpyxl.load_workbook(export)["Issues"].max_row == 20
    assert list(out_dir.glob("Acme*")) == []          # nothing written while errors stand

    # --- the executive fixes the source files, then re-checks
    make_sales_set(sales["folder"], rows_per_file=300, fixed=True)
    click(qtbot, btn(window, "recheck"))
    wait_idle(qtbot, window)
    assert vp.banner.title.text() == "No errors"
    assert btn(window, "nextOutput").isVisible() and not btn(window, "writeAnyway").isVisible()

    # --- step 5: output
    click(qtbot, btn(window, "nextOutput"))
    op = window.pages["output"]
    assert op.folder.text() == str(out_dir)
    assert op.name_preview.text() == "Gives: Acme-Traders_Monthly-Sales-Register_202609.xlsx"
    click(qtbot, btn(window, "writeOutput"))
    wait_idle(qtbot, window)
    out = out_dir / "Acme-Traders_Monthly-Sales-Register_202609.xlsx"
    assert out.exists()
    assert op.banner.title.text() == f"Written: {out.name}"
    assert "totals match the input files" in op.banner.body.text()
    assert op.totals.rowCount() == 2
    assert {op.totals.item(r, 3).text() for r in range(2)} == {"Match"}
    assert "Sales_Jun-2026.xlsx: 12 hidden rows" in op.hidden_lbl.text()
    assert 'Sales_Aug-2026.xlsx: hidden sheet "Old"' in op.hidden_lbl.text()
    assert btn(window, "openFile").isVisible()
    assert 'This run added the alias "Inv Amt" → Invoice Value.' == op.alias_lbl.text()
    assert op.save_btn.text() == "Save to template (v1 → v2)"
    shot(window, "5_output_done")

    # write again: asks before replacing
    prompter.answers["confirm"] = [True]
    click(qtbot, btn(window, "writeOutput"))
    wait_idle(qtbot, window)
    wait_idle(qtbot, window)
    assert any(a[0] == "confirm" and a[1] == "Replace file?" for a in prompter.asked)
    assert op.banner.title.text() == f"Written: {out.name}"

    click(qtbot, btn(window, "saveTemplate"))
    t = window.store.list()[0]
    assert t.version == 2 and "Inv Amt" in t.column("Invoice Value")["aliases"]


@spec("D4", "VAL-severity")
def test_override_writes_with_errors(qtbot, window, prompter, sales, out_dir):
    """'Write output anyway…' asks first, then writes all rows and reports the errors written."""
    t = sales_template()
    t.column("Invoice Value")["aliases"].append("Inv Amt")
    save_tpl(window, t, out_dir)
    run_first_template(qtbot, window)
    prompter.answers["folder"] = str(sales["folder"])
    click(qtbot, btn(window, "addFolder"))
    wait_idle(qtbot, window)
    click(qtbot, btn(window, "nextMap"))
    click(qtbot, btn(window, "nextValidate"))
    wait_idle(qtbot, window)
    prompter.answers["confirm"] = [False]
    click(qtbot, btn(window, "writeAnyway"))
    assert window.current == "validate"            # cancelled: stays
    prompter.answers["confirm"] = [True]
    click(qtbot, btn(window, "writeAnyway"))
    assert window.current == "output"
    click(qtbot, btn(window, "writeOutput"))
    wait_idle(qtbot, window)
    op = window.pages["output"]
    assert "3 errors written anyway" in op.banner.body.text()
    texts = [op.summary.itemAt(i).widget().text() for i in range(op.summary.count())]
    assert "Errors written anyway" in texts


@spec("MAP-1", "TPL-3", "OUT-1", "OUT-3")
def test_new_consolidation_from_sample_to_csv(qtbot, window, prompter, misc, out_dir):
    """New consolidation: columns taken from a sample file; CSV output; saved as a new template."""
    prompter.answers["new_consolidation"] = ("Blue Lotus Pvt Ltd", "Bills", str(misc["csv_bom_comma"]))
    click(qtbot, btn(window, "newConsolidation"))
    wait_idle(qtbot, window)
    fp = window.pages["files"]
    assert fp.table.rowCount() == 1 and fp.table.item(0, 5).text() == "OK"
    prompter.answers["files"] = [str(misc["csv_utf8_semicolon"]), str(misc["txt_pipe"])]
    click(qtbot, btn(window, "addFiles"))
    wait_idle(qtbot, window)
    assert fp.table.rowCount() == 3
    click(qtbot, btn(window, "nextMap"))
    assert window.pages["map"].banner.title.text() == "All 6 output columns matched in every file."
    click(qtbot, btn(window, "nextValidate"))
    wait_idle(qtbot, window)
    vp = window.pages["validate"]
    # the same three bills in three files -> no checks configured on Bill No, so no errors
    assert vp.banner.title.text() == "No errors"
    click(qtbot, btn(window, "nextOutput"))
    op = window.pages["output"]
    op.fmt_csv.setChecked(True)
    op.folder.setText(str(out_dir))
    assert op.csv_box.isVisible()
    click(qtbot, btn(window, "writeOutput"))
    wait_idle(qtbot, window)
    out = next(out_dir.glob("*.csv"))
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")
    assert len(out.read_text(encoding="utf-8-sig").splitlines()) == 10
    assert op.totals.item(0, 3).text() == "Match"
    assert op.save_btn.text() == "Save as new template"
    click(qtbot, btn(window, "saveTemplate"))
    assert [t.task for t in window.store.list()] == ["Bills"]


@spec("IN-9")
def test_password_prompt(qtbot, window, prompter, misc, out_dir):
    """A protected file asks for its password; the right one opens it."""
    save_tpl(window, purchase_template(), out_dir)
    run_first_template(qtbot, window)
    prompter.answers["files"] = [str(misc["password"])]
    prompter.answers["password"] = ["acme@123"]
    click(qtbot, btn(window, "addFiles"))
    wait_idle(qtbot, window)
    fp = window.pages["files"]
    assert ("password", "bills_protected.xlsx") in prompter.asked
    assert fp.table.item(0, 5).text() == "OK" and fp.table.item(0, 3).text() == "3"


@spec("IN-9")
def test_password_wrong_then_retry(qtbot, window, prompter, misc, out_dir):
    save_tpl(window, purchase_template(), out_dir)
    run_first_template(qtbot, window)
    prompter.answers["files"] = [str(misc["password"])]
    prompter.answers["password"] = ["nope"]
    click(qtbot, btn(window, "addFiles"))
    wait_idle(qtbot, window)
    fp = window.pages["files"]
    assert fp.table.item(0, 5).text() == "Password needed"
    fp.table.selectRow(0)
    assert btn(window, "enterPassword").isVisible()
    prompter.answers["password"] = ["acme@123"]
    click(qtbot, btn(window, "enterPassword"))
    assert fp.table.item(0, 5).text() == "OK"


@spec("IN-1")
def test_drag_and_drop(qtbot, window, prompter, misc, out_dir):
    """Files dropped on the drop area are added."""
    save_tpl(window, purchase_template(), out_dir)
    run_first_template(qtbot, window)
    fp = window.pages["files"]
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(misc["xls"])), QUrl.fromLocalFile(str(misc["xlsm"]))])
    ev = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, md, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    fp.drop.dropEvent(ev)
    wait_idle(qtbot, window)
    assert fp.table.rowCount() == 2


@spec("IN-5", "IN-6")
def test_sheet_and_header_override_in_ui(qtbot, window, prompter, misc, out_dir):
    """Pick another sheet and a header row for one file in the preview panel."""
    save_tpl(window, purchase_template(), out_dir)
    run_first_template(qtbot, window)
    prompter.answers["files"] = [str(misc["multi"])]
    click(qtbot, btn(window, "addFiles"))
    wait_idle(qtbot, window)
    fp = window.pages["files"]
    fp.table.selectRow(0)
    assert fp.table.item(0, 1).text() == "Summary"
    fp.sheet.setCurrentText("Sales South")
    click(qtbot, btn(window, "applyOptions"))
    assert fp.table.item(0, 1).text() == "Sales South" and fp.table.item(0, 3).text() == "1"
    fp.table.selectRow(0)
    fp.header.setValue(2)
    click(qtbot, btn(window, "applyOptions"))
    assert fp.table.item(0, 2).text() == "2"


@spec("MAP-10", "VAL-config")
def test_column_settings_panel(qtbot, window, prompter, misc, out_dir):
    """Change a column's type and add a check from the side panel; validation uses them."""
    save_tpl(window, purchase_template(), out_dir)
    run_first_template(qtbot, window)
    prompter.answers["files"] = [str(misc["csv_bom_comma"])]
    click(qtbot, btn(window, "addFiles"))
    wait_idle(qtbot, window)
    click(qtbot, btn(window, "nextMap"))
    mp = window.pages["map"]
    rows = [mp.grid.item(r, 0).text() for r in range(mp.grid.rowCount())]
    mp.grid.selectRow(rows.index("Amount"))
    mp.show_column()
    assert mp.col_title.text() == "Amount"
    click(qtbot, btn(window, "addCheck"))
    r = mp.rules.t.rowCount() - 1
    mp.rules.t.cellWidget(r, 0).setCurrentIndex(mp.rules.t.cellWidget(r, 0).findData("number_range"))
    mp.rules.t.cellWidget(r, 1).setCurrentIndex(1)       # warning
    mp.rules.t.cellWidget(r, 2).setText("max=2000")
    mp.rules.t.cellWidget(r, 2).editingFinished.emit()
    col = window.session.template.column("Amount")
    assert {"type": "number_range", "severity": "warning", "max": 2000.0} in col["rules"]
    click(qtbot, btn(window, "nextValidate"))
    wait_idle(qtbot, window)
    v = window.session.validation
    assert [(i.rule, i.row) for i in v.warnings] == [("number_range", 3)]


@spec("TPL-1", "TPL-4", "MAP-8", "VAL-config", "VAL-11")
def test_template_editor(qtbot, window, prompter, out_dir):
    """Edit a template: rename and reorder columns, exclude one, add checks, duplicates, input settings."""
    t = save_tpl(window, purchase_template(), out_dir)

    def drive(dlg):
        dlg.task.setText("Purchase Register FY27")
        cols = dlg.cols
        names = [cols.item(r, 0).text() for r in range(cols.rowCount())]
        cols.item(names.index("Amount"), 0).setText("Bill Amount")
        cols.item(names.index("Amount"), 6).setText("Amount|Amt")
        cols.item(names.index("Supplier"), 4).setCheckState(Qt.CheckState.Unchecked)
        cols.selectRow(names.index("Bill Amount") if "Bill Amount" in names else names.index("Amount"))
        cols.setCurrentCell(names.index("Amount"), 0)
        dlg._move(-1)
        dlg.tabs.setCurrentIndex(2)       # Checks tab
        items = [dlg.col_list.item(i).text() for i in range(dlg.col_list.count())]
        dlg.col_list.setCurrentRow(items.index("Supplier"))
        dlg.rules.add_rule({"type": "not_blank", "severity": "warning"})
        dlg.dup_keys.setText("GSTIN|Bill No")
        dlg.gst_exc.setText("0717uno00157uno")
        dlg.in_sheet_mode.setCurrentIndex(dlg.in_sheet_mode.findData("pattern"))
        dlg.in_sheet_value.setText("Sales*")
        dlg.out_fmt.setCurrentIndex(1)

    window.edit_template(window.store.list()[0], editor_cb=drive)
    saved = window.store.list()[0]
    assert saved.task == "Purchase Register FY27" and saved.version == 2
    names = [c["name"] for c in saved.columns]
    assert names.index("Bill Amount") < names.index("Invoice Type")
    assert saved.column("Bill Amount")["aliases"] == ["Amount", "Amt"]
    assert saved.column("Supplier")["include"] is False
    assert saved.column("Supplier")["rules"] == [{"type": "not_blank", "severity": "warning"}]
    assert saved.duplicate_keys == [{"columns": ["GSTIN", "Bill No"], "severity": "error"}]
    assert saved.gstin_exceptions == ["0717UNO00157UNO"]
    assert saved.input["sheet_mode"] == "pattern" and saved.output["format"] == "csv"
    assert len(list(window.store.folder.glob("*.json"))) == 1     # renamed, not copied


@spec("TPL-2", "TPL-4")
def test_home_search_duplicate_rename_delete(qtbot, window, prompter, out_dir):
    save_tpl(window, sales_template(), out_dir)
    save_tpl(window, purchase_template(), out_dir)
    home = window.pages["home"]
    assert home.table.rowCount() == 2
    qtbot.keyClicks(home.search, "lotus")
    assert home.table.rowCount() == 1 and home.table.item(0, 0).text() == "Blue Lotus Pvt Ltd"
    home.search.clear()
    t = window.store.list()[0]
    prompter.answers["text"] = ["Monthly Sales Copy"]
    window.duplicate_template(t)
    assert home.table.rowCount() == 3
    prompter.answers["text"] = ["Acme Traders Ltd", "Sales Register"]
    window.rename_template(window.store.list("copy")[0])
    assert [x.task for x in window.store.list("acme traders ltd")] == ["Sales Register"]
    prompter.answers["confirm"] = [True]
    window.delete_template(window.store.list("sales register")[0])
    assert home.table.rowCount() == 2
    assert "2 templates across 2 clients" in home.count.text()
    prompter.answers["folder"] = str(out_dir / "other_templates")
    (out_dir / "other_templates").mkdir()
    click(qtbot, btn(window, "changeFolder"))
    assert home.table.rowCount() == 0 and "other_templates" in home.folder_lbl.text()


@spec("NF-4")
def test_progress_and_cancel(qtbot, window, prompter, tmp_path, out_dir):
    """Long jobs show a progress bar and can be cancelled; the window stays responsive."""
    perf = tmp_path / "perf"
    make_perf_set(perf, files=8, rows=20000)
    save_tpl(window, sales_template(), out_dir)
    run_first_template(qtbot, window)
    window.session.template.input["pattern"] = "*.xlsx"
    window.pages["files"].pattern.setText("*.xlsx")
    window.pages["files"].add_paths([str(perf)])
    assert window.is_busy and window.busy.isVisible()
    QApplication.processEvents()
    click(qtbot, btn(window, "cancelJob"))
    wait_idle(qtbot, window)
    assert ("info", "Cancelled", "Stopped. Nothing was written.") in prompter.asked
    assert not window.busy.isVisible()
    assert list(out_dir.iterdir()) == []


@spec("NF-8")
def test_branding_no_publisher(window):
    """Title bar shows 'Sankalan' only; no publisher name anywhere in the app's text."""
    assert window.windowTitle() == "Sankalan"
    root = Path(__file__).resolve().parents[1] / "sankalan"
    for p in root.rglob("*.py"):
        text = p.read_text(encoding="utf-8").lower()
        for name in ("vyazen", "ollyver"):
            assert name not in text, (p, name)


@spec("NF-5", "NF-9")
@pytest.mark.parametrize("scale", ["1", "1.25", "1.5"])
def test_display_scaling(tmp_path, scale):
    """The window renders at 100%, 125% and 150% scaling with its content fitting the window."""
    code = (
        "import os,sys; sys.path.insert(0, %r)\n"
        "from PySide6.QtWidgets import QApplication\n"
        "from sankalan.ui import style as S\nfrom sankalan.ui.app import MainWindow\n"
        "app=QApplication([]); app.setStyleSheet(S.QSS)\n"
        "w=MainWindow(store_folder=%r); w.show(); app.processEvents()\n"
        "img=w.grab(); img.save(%r)\n"
        "ok = w.minimumSizeHint().width() <= w.width() and w.minimumSizeHint().height() <= w.height()\n"
        "print(img.devicePixelRatio(), img.width(), ok)\n"
    ) % (str(Path(__file__).resolve().parents[1]), str(tmp_path / "tpl"), str(tmp_path / f"scale_{scale}.png"))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR=scale)
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    dpr, width, ok = out.stdout.split()[-3:]
    assert float(dpr) == pytest.approx(float(scale)) and ok == "True"
    SHOTS.mkdir(parents=True, exist_ok=True)
    shutil.copy(tmp_path / f"scale_{scale}.png", SHOTS / f"scale_{scale.replace('.', '_')}.png")
