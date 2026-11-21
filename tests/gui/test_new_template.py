"""Phase 8: New template wizard (2.1 to 2.6): C3-01 to C3-22 on the generated fixture pack (offscreen, real storage).
The sample is read in the Job's thread (``WORKERS = 0``); the reader workers are covered by the ingestion tests."""
import pytest

from conftest import settle_window, spec
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, Group, Measure
from sankalan.model.rule import (ALLOWED_VALUES, DATE_RANGE, NOT_BLANK, NUMBER_RANGE, PATTERN, TEXT_LENGTH, UNIQUE,
                                 WARNING)
from sankalan.model.template import SHEETS_ALL_VISIBLE, SHEETS_BY_NAME, SHEETS_FIRST_VISIBLE
from sankalan.query import catalogue as q
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens import new_template as ntui
from sankalan.ui.screens.client import ClientScreen
from sankalan.ui.screens.new_template import (COLUMNS, DATE_FORMAT, DECIMALS, INCLUDE, OUTPUTS, REVIEW, RULES,
                                              SAMPLE, SHEETS, NewTemplateScreen)
from sankalan.ui.window import MainWindow

INV, DATE_, CUST, GSTIN, STATE, TAXABLE, RATE, TAX = (f"c00{i}" for i in range(1, 9))


def settle(qtbot, w, timeout=30_000):
    settle_window(qtbot, w, timeout, extra=lambda: not getattr(w.current, "_dry_again", False))


@pytest.fixture(autouse=True)
def inline_reader(monkeypatch):
    monkeypatch.setattr(ntui, "WORKERS", 0)


@pytest.fixture(autouse=True)
def discard_on_close(monkeypatch):
    """pytest-qt closes the window before fixtures tear down; an open wizard would ask "Discard this template?".
    Tests that answer prompts themselves (``answers``) replace this hook."""
    from sankalan.ui.dialogs import base
    monkeypatch.setattr(base, "answer_hook", lambda dlg: "discard")


@pytest.fixture
def env(app, qtbot, storage):
    acme = q.insert_client(storage.con, "Acme Traders")
    bharat = q.insert_client(storage.con, "Bharat Foods")
    w = MainWindow(JobBridge(storage.runner), storage)
    qtbot.addWidget(w)
    w.resize(1366, 768)
    w.show()
    yield {"w": w, "s": storage, "acme": acme, "bharat": bharat}
    w.bridge.wait_all(30)
    w.bridge.poll()


def open_wizard(qtbot, env, client="acme", name="Sales Register", sample=None, fx=None) -> NewTemplateScreen:
    w = env["w"]
    cname = "Acme Traders" if client == "acme" else "Bharat Foods"
    assert w.go("new_template", client_id=env[client], name=cname)
    settle(qtbot, w)
    wz = w.current
    assert isinstance(wz, NewTemplateScreen)
    wz.sample_step.name.setText(name)
    if sample is not None:
        assert wz.pick(fx / sample)
        settle(qtbot, w)
        assert wz.staged is not None, wz.sample_step.file_error.text()
    return wz


def nxt(qtbot, wz, expect=None):
    wz.next()
    settle(qtbot, wz.window_)
    if expect is not None:
        assert wz.step == expect, (wz.step, [b.findChildren(object) for b in wz.banners()])


def to_step(qtbot, wz, step):
    while wz.step < step:
        nxt(qtbot, wz, wz.step + 1)


def staging_dirs(s):
    return list(s.folder.staging_root.iterdir())


def tpl_a_rules(rs):
    """Step 4: the TPL-A rule set (Test Cases, Read me)."""
    for cid, typ, settings, sev in [
            (INV, NOT_BLANK, {}, "Error"), (INV, PATTERN, {"pattern": "AAA-99999"}, "Error"),
            (INV, UNIQUE, {}, "Error"), (DATE_, DATE_RANGE, {"from": "2026-04-01", "to": "2027-03-31"}, WARNING),
            (CUST, NOT_BLANK, {}, WARNING), (GSTIN, TEXT_LENGTH, {"exact": 15}, "Error"),
            (STATE, ALLOWED_VALUES, {"values": ["Maharashtra", "Gujarat", "Karnataka", "Delhi"]}, WARNING),
            (TAXABLE, NUMBER_RANGE, {"not_negative": True}, "Error"),
            (RATE, ALLOWED_VALUES, {"values": ["0", "5", "12", "18", "28"]}, "Error")]:
        rs.select(cid)
        assert rs.add_rule(typ, settings, sev) is not None, rs.error.text()


def counts_by_name(wz):
    """{(column name, rule name): failures} from the dry run."""
    rs = wz.rules_step
    names = {c.id: c.name for c in rs.columns}
    return {(names[r.column_id], r.name): rs.counts.get(r.id) for r in rs.all_rules()}


# ---------------------------------------------------------------------------------------------- 2.1 Sample file
@spec("C3-01", "UX-3")
def test_steps_and_cancel(env, qtbot, fixtures_dir, answers):
    s, w = env["s"], env["w"]
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    assert wz.steps.labels == ["Sample file", "Sheets", "Columns", "Rules", "Default outputs", "Review"]
    assert wz.breadcrumb.text() == "Clients › Acme Traders › New template"
    to_step(qtbot, wz, COLUMNS)
    answers.append("stay")
    assert not wz.cancel()
    assert w.current is wz and wz.step == COLUMNS
    assert wz.sample_step.name.text() == "Sales Register" and len(wz.drafts) == 8
    assert answers.asked[-1] == ("Discard this template?", ["Keep editing", "Discard"])
    answers.append("discard")
    assert wz.cancel()
    settle(qtbot, w)
    assert isinstance(w.current, ClientScreen)
    assert q.template_names(s.con, env["acme"]) == {}
    assert staging_dirs(s) == []


@spec("C3-01", "UX §5")
def test_leaving_by_breadcrumb_asks(env, qtbot, fixtures_dir, answers):
    w = env["w"]
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    answers.append("stay")
    assert not w.open_area("clients") and w.current is wz
    answers.append("discard")
    assert w.open_area("clients")
    assert staging_dirs(env["s"]) == []


@spec("C3-02", "TPL-3")
def test_sample_file_and_rows_read(env, qtbot, fixtures_dir):
    s = env["s"]
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    st = wz.sample_step
    assert st.file_name.text() == "Sample_Sales.xlsx"
    assert st.rows.text() == "Read 1,000 rows for previews" and st.rows.isVisible()
    assert "1 sheet" in st.file_meta.text()
    assert list(s.folder.templates_root.iterdir()) == []         # nothing written under t\
    assert len(staging_dirs(s)) == 1


@spec("C3-04", "IN-3")
def test_allowed_sample_file_types(env, qtbot, fixtures_dir):
    assert ntui.FILE_FILTER == "Excel and CSV files (*.xlsx *.xlsm *.xlsb *.xls *.csv)"
    wz = open_wizard(qtbot, env)
    assert not wz.pick(fixtures_dir / "Sales_Notes.txt")
    assert wz.sample_step.file_error.text() == ("Sales_Notes.txt: only .xlsx, .xlsm, .xlsb, .xls and .csv files "
                                                "can be added.")
    assert wz.staged is None
    assert wz.pick(fixtures_dir / "Sales_Old.xls")
    settle(qtbot, wz.window_)
    assert wz.sample_step.file_error.isHidden()
    assert wz.info.kind == "xls" and wz.sample_step.rows.text() == "Read 100 rows for previews"
    assert wz.pick(fixtures_dir / "Sales_Macro.xlsm")
    settle(qtbot, wz.window_)
    assert wz.sample_step.file_error.isHidden()
    assert wz.info.kind == "xlsm" and wz.sample_step.rows.text() == "Read 500 rows for previews"


@spec("C3-05", "TPL-2")
def test_template_name_unique_within_client(env, qtbot, fixtures_dir):
    from conftest import tpl_a_template
    q.create_template(env["s"].con, tpl_a_template(env["acme"]))
    wz = open_wizard(qtbot, env, name=" sales register ", sample="Sample_Sales.xlsx", fx=fixtures_dir)
    nxt(qtbot, wz, SAMPLE)
    assert wz.sample_step.name_error.text() == "“Sales Register” is already in use. Choose another name."
    wz.sample_step.name.setText("")
    nxt(qtbot, wz, SAMPLE)
    assert wz.sample_step.name_error.text() == "Enter a template name."
    # the same name in another client is fine
    wz2 = open_wizard(qtbot, env, client="bharat", name="Sales Register", sample="Sample_Sales.xlsx",
                      fx=fixtures_dir)
    nxt(qtbot, wz2, SHEETS)


# ---------------------------------------------------------------------------------------------- 2.2 Sheets
@spec("C3-06", "IN-6", "IN-7")
def test_header_row_found(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    nxt(qtbot, wz, SHEETS)
    sh = wz.sheets_step
    assert sh.header_row_shown() == 3 and sh.header_found.text() == "Header found in row 3"
    assert sh.preview_rows()[2][1:4] == ["Invoice No", "Invoice Date", "Customer"]
    assert sh.preview_rows()[3][2] == "01-08-2026"                 # Excel date shown DD-MM-YYYY
    from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox
    inputs = [x.accessibleName().lower() for t in (QComboBox, QLineEdit, QSpinBox) for x in sh.findChildren(t)]
    assert not any("header" in x or "trailer" in x for x in inputs)       # no header-row or trailer setting
    assert sh.sheet_rows() == [("Sales", True, True, True)]
    assert wz.footer.text() == "Sales will be read"


@spec("C3-07", "IN-5", "IN-13")
def test_sheets_to_read_and_hidden_sheets(env, qtbot, fixtures_dir):
    s = env["s"]
    wz = open_wizard(qtbot, env, client="bharat", name="Regional Sales", sample="Sales_Regions.xlsx",
                     fx=fixtures_dir)
    nxt(qtbot, wz, SHEETS)
    sh = wz.sheets_step
    assert [rb.text() for rb in sh.radios.values()] == ["By name (one or more)", "First visible sheet",
                                                        "All visible sheets"]
    assert sh.sheet_rows() == [("North", True, True, True), ("South", True, False, True),
                               ("Archive", False, False, False)]
    assert "Hidden, skipped" in sh.sheet_list.item(2).text()
    sh.tick("South", True)
    assert wz.source.sheet_names == ["North", "South"] and wz.footer.text() == "North and South will be read"
    sh.set_mode(SHEETS_FIRST_VISIBLE)
    assert wz.footer.text() == "North will be read"
    assert [r[2] for r in sh.sheet_rows()] == [True, False, False]
    sh.set_mode(SHEETS_ALL_VISIBLE)
    assert wz.footer.text() == "North and South will be read"
    first = wz.staged
    nxt(qtbot, wz, COLUMNS)
    assert wz.staged is not first and wz.staged.sheets == ["North", "South"] and wz.staged.rows == 4000
    to_step(qtbot, wz, REVIEW)
    assert wz.review_step.summary()["Sheets to read"] == "All visible sheets"
    wz.save(False)
    settle(qtbot, wz.window_)
    tid = next(iter(q.template_names(s.con, env["bharat"])))
    t = q.load_template(s.con, tid)
    assert t.source.sheets == SHEETS_ALL_VISIBLE and [c.name for c in t.columns][:2] == ["Invoice No",
                                                                                        "Invoice Date"]
    assert t.outputs == [] and all(r.automatic for r in t.rules)          # TPL-D


@spec("C3-08", "IN-4")
def test_csv_encoding_and_delimiter(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, client="bharat", name="Conversion 1252", sample="Conversion_1252.csv",
                     fx=fixtures_dir)
    nxt(qtbot, wz, SHEETS)
    sh = wz.sheets_step
    assert sh.csv_box.isVisible() and not sh.excel_box.isVisible()
    assert sh.encoding.currentText() == "Windows-1252" and sh.delimiter.currentText() == "Semicolon"
    assert sh.encoding.isEnabled() and sh.delimiter.isEnabled()
    codes = [r[6] for r in sh.preview_rows()[1:]]
    assert codes == ["Café", "Müller", "Señor"]
    sh.delimiter.setCurrentIndex(sh.delimiter.findData(","))
    sh.delimiter.activated.emit(sh.delimiter.currentIndex())
    settle(qtbot, wz.window_)
    assert wz.info.delimiter == "," and wz.source.csv_delimiter == ","
    assert sh.preview_rows()[0][1].startswith("Case;Amount")
    sh.delimiter.setCurrentIndex(sh.delimiter.findData(";"))
    sh.delimiter.activated.emit(sh.delimiter.currentIndex())
    settle(qtbot, wz.window_)
    assert wz.source.csv_delimiter is None and wz.source.csv_encoding is None     # detected: not stored
    nxt(qtbot, wz, COLUMNS)
    assert wz.columns_step.rows()[5][6] == "Café, Müller"


# ---------------------------------------------------------------------------------------------- 2.3 Columns
@spec("C3-09", "C3-10", "C3-11", "TPL-3", "MAP-10", "T13")
def test_columns_grid_types_decimals_dates(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    to_step(qtbot, wz, COLUMNS)
    cs = wz.columns_step
    headers = [cs.table.horizontalHeaderItem(i).text() for i in range(cs.table.columnCount() - 1)]
    assert headers == ["Include", "Header in the file", "Column name", "Type", "Decimals", "Date format", "Detected",
                       "Sample values"]
    assert not any("required" in h.lower() for h in headers)
    rows = cs.rows()
    assert [(r[0], r[2]) for r in rows] == [("Invoice No", "Text"), ("Invoice Date", "Date"), ("Customer", "Text"),
                                            ("GSTIN", "Text"), ("State", "Text"), ("Taxable Value", "Number"),
                                            ("GST Rate", "Number"), ("Tax Amount", "Number")]
    assert all(r[5].startswith("100% ") for r in rows)
    assert rows[1][5] == "100% dates · Excel dates" and rows[5][5] == "100% numbers"
    assert rows[5][6] == "1,000.00, 1,010.25" and rows[1][6] == "01-08-2026, 02-08-2026"
    # C3-10 Decimals: Number columns only, default 2, 0-6
    assert [r[3] for r in rows] == ["", "", "", "", "", "2", "2", "2"]
    rate = cs.widget(6, DECIMALS)
    rate.setValue(0)
    assert wz.drafts[6].column.decimals == 0
    rate.setValue(7)
    assert rate.value() == 6 and wz.drafts[6].column.decimals == 6
    rate.setValue(-1)
    assert rate.value() == 0 and wz.drafts[6].column.decimals == 0
    # C3-11 Excel dates: no date format to pick
    fmt = cs.widget(1, DATE_FORMAT)
    assert fmt.currentText() == "Excel dates" and not fmt.isEnabled()


@spec("C3-11", "C3-09", "MAP-9", "MAP-10")
def test_text_dates_offer_formats(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, client="bharat", name="Conversion check", sample="Conversion_Values.csv",
                     fx=fixtures_dir)
    to_step(qtbot, wz, COLUMNS)
    cs = wz.columns_step
    rows = cs.rows()
    assert [r[2] for r in rows] == ["Text", "Number", "Number", "Date", "Date", "Text"]        # TPL-C
    assert rows[3][4] == "DD-MM-YYYY" and rows[4][4] == "DD/MM/YYYY"
    fmt = cs.widget(3, DATE_FORMAT)
    assert fmt.isEnabled() and [fmt.itemText(i) for i in range(fmt.count())] == ["DD-MM-YYYY", "DD/MM/YYYY"]
    assert rows[5][6].startswith("00123")                          # leading zeros: Text, as typed
    assert rows[1][5] == "90.9% numbers · 9.09% aren't numbers and are kept as text"     # 12abc


@spec("AC-TXT-10", "TXT-1")
def test_type_note_states_the_text_share(env, qtbot, tmp_path):
    """A sample with 2% text in a Number column (Feature Spec A2 6.2)."""
    rows = ["Code,Amount,Doc Date"] + [f"A{i},{'NA' if i in (10, 60) else str(100 + i) + '.50'},"
                                         f"{'31-02-2026' if i < 3 else f'{(i % 28) + 1:02d}-11-2026'}"
                                         for i in range(100)]
    (tmp_path / "Text_Share.csv").write_text("".join(r + "\n" for r in rows), encoding="utf-8")
    wz = open_wizard(qtbot, env, name="Text share", sample="Text_Share.csv", fx=tmp_path)
    to_step(qtbot, wz, COLUMNS)
    got = wz.columns_step.rows()
    assert got[1][2] == "Number" and got[1][5] == "98% numbers · 2% aren't numbers and are kept as text"
    assert got[2][2] == "Date" and got[2][5] == "97% dates · DD-MM-YYYY · 3% aren't dates and are kept as text"


@spec("C3-12", "TPL-3")
def test_include_rename_reorder(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    to_step(qtbot, wz, COLUMNS)
    cs = wz.columns_step
    cs.move(2, -1)                                                  # Customer above Invoice Date
    assert [r[0] for r in cs.rows()][:3] == ["Invoice No", "Customer", "Invoice Date"]
    cs.move(1, 1)
    assert [r[0] for r in cs.rows()][:3] == ["Invoice No", "Invoice Date", "Customer"]
    cs.move(2, -1)                                                  # keep the moved order for step 6
    cs.widget(3, INCLUDE).setChecked(False)                         # GSTIN
    assert wz.footer.text() == "7 of 8 columns included"
    nxt(qtbot, wz, RULES)
    assert [r[0] for r in wz.rules_step.list_rows()] == ["Invoice No", "Customer", "Invoice Date", "State",
                                                         "Taxable Value", "GST Rate", "Tax Amount"]
    nxt(qtbot, wz, OUTPUTS)
    assert "GSTIN" not in [c.name for c in wz.outputs_step.builder.columns]
    nxt(qtbot, wz, REVIEW)
    assert wz.review_step.summary()["Columns"] == "7 · 3 Text, 1 Date, 3 Number (GSTIN left out)"
    assert [r[0] for r in wz.review_step.column_rows()][:3] == ["Invoice No", "Customer", "Invoice Date"]
    for _ in range(3):
        wz.back()
    assert wz.step == COLUMNS
    cs.widget(3, INCLUDE).setChecked(True)
    cs.move(1, 1)
    assert wz.footer.text() == "8 of 8 columns included"
    assert [r[0] for r in cs.rows()] == ["Invoice No", "Invoice Date", "Customer", "GSTIN", "State", "Taxable Value",
                                         "GST Rate", "Tax Amount"]


# ---------------------------------------------------------------------------------------------- 2.4 Rules
@spec("C3-13", "C3-14", "C3-15", "VR-7", "VR-8")
def test_type_rules_menu_and_tpl_a_rules_on_f01(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    to_step(qtbot, wz, RULES)
    rs = wz.rules_step
    rs.select(TAXABLE)
    assert rs.type_line.text() == "Number · Becomes fixed after the first run"
    assert rs.rule_rows() == [("Is a number  Auto", "Plain numbers, 1,234.50 and (1,234)", "Error",
                               "0 of 1,000 fail", False)]
    rs.select(DATE_)
    assert rs.rule_rows()[0][0] == "Is a date  Auto" and rs.rule_rows()[0][2] == "Error"
    rs.remove_rule(f"{DATE_}.type")                                 # no remove control; refused anyway
    assert len(rs.rule_rows()) == 1
    rs.set_severity(f"{DATE_}.type", WARNING)
    settle(qtbot, wz.window_)
    assert rs.rule_rows()[0][2] == "Warning"
    rs.set_severity(f"{DATE_}.type", "Error")
    settle(qtbot, wz.window_)
    assert rs.rule_rows()[0][2] == "Error"
    for cid, expect in ((INV, ["Not blank", "Allowed values", "Text length", "Character pattern",
                               "Unique within the run"]),
                        (TAXABLE, ["Not blank", "Number range", "Allowed values", "Unique within the run"]),
                        (DATE_, ["Not blank", "Date range", "Unique within the run"])):
        rs.select(cid)
        assert [a.text() for a in rs.rule_menu().actions()] == expect
    tpl_a_rules(rs)
    settle(qtbot, wz.window_)
    counts = counts_by_name(wz)
    assert len(counts) == 13 and set(counts.values()) == {0}
    rs.select(INV)
    assert [(r[0], r[1], r[2], r[3]) for r in rs.rule_rows()] == [
        ("Not blank", "No setting", "Error", "0 of 1,000 fail"),
        ("Character pattern", "AAA-99999", "Error", "0 of 1,000 fail"),
        ("Unique within the run", "No setting", "Error", "0 of 1,000 fail")]
    assert rs.info.text() == ("Counts are on the first 1,000 rows of Sample_Sales.xlsx. Click a count to see the "
                              "first 20 failing rows.")


@spec("C3-16", "VR-8", "T16", "T17")
def test_dry_run_counts_and_show(env, qtbot, fixtures_dir, answers):
    wz = open_wizard(qtbot, env, name="Rules dry run", sample="Sales_Errors.xlsx", fx=fixtures_dir)
    to_step(qtbot, wz, COLUMNS)
    wz.columns_step.widget(6, DECIMALS).setValue(0)                 # GST Rate decimals 0
    nxt(qtbot, wz, RULES)
    tpl_a_rules(wz.rules_step)
    settle(qtbot, wz.window_)
    c = counts_by_name(wz)
    assert c[("Invoice No", "Not blank")] == 12 and c[("Invoice No", "Character pattern")] == 8
    assert c[("Invoice No", "Unique within the run")] == 6
    assert c[("Invoice Date", "Is a date")] == 4 and c[("GSTIN", "Text length")] == 10
    assert c[("Taxable Value", "Is a number")] == 15 and c[("Taxable Value", "Number range")] == 5
    assert c[("GST Rate", "Allowed values")] == 6
    assert c[("State", "Allowed values")] == 25 and c[("Customer", "Not blank")] == 7
    rs = wz.rules_step
    rs.select(STATE)
    assert rs.rule_rows()[0][3] == "25 of 2,000 fail"
    state_rule = next(r for r in rs.rules if r.column_id == STATE)
    dlg = rs.show_failures(state_rule.id)
    assert len(dlg.rows()) == 20 and dlg.findChildren(type(rs.name))[1].text() == "The first 20 of 25 failing rows."
    assert dlg.windowTitle() == "State: Allowed values"
    dlg.accept()
    dlg = rs.show_failures(f"{TAXABLE}.type")
    rows = dlg.rows()
    assert len(rows) == 15 and rows[0][0] == "214" and rows[0][1] == "abc"
    assert rows[0][2] == "Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number"
    dlg.accept()
    answers.append("discard")
    assert wz.cancel()
    assert staging_dirs(env["s"]) == []


# ---------------------------------------------------------------------------------------------- 2.5 Default outputs
DO1 = Definition("", [], [Group(STATE)], [Measure(TAXABLE, d.SUM, "Taxable"), Measure(TAX, d.SUM, "Tax"),
                                           Measure(INV, d.COUNT, "Invoices")])
DO2 = Definition("", [Filter(DATE_, d.LATEST_MONTH)], [Group(DATE_, "month"), Group(RATE)],
                 [Measure(TAXABLE, d.SUM)], subtotals=True)


def add_output(qtbot, wz, name, definition):
    st = wz.outputs_step
    st.add_output()
    st.name.setText(name)
    st.builder.set_definition(definition, st.template.columns)
    st._edited()
    st.preview()
    settle(qtbot, wz.window_)
    return st.preview_rows()


@spec("C3-17", "C3-18", "C3-19", "C3-20", "DO-1", "DO-3", "DO-8", "F1")
def test_outputs_review_and_save(env, qtbot, fixtures_dir):
    s = env["s"]
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    to_step(qtbot, wz, COLUMNS)
    wz.columns_step.widget(6, DECIMALS).setValue(0)
    nxt(qtbot, wz, RULES)
    tpl_a_rules(wz.rules_step)
    settle(qtbot, wz.window_)
    nxt(qtbot, wz, OUTPUTS)
    assert wz.footer.text() == "Optional: you can skip this step"
    nxt(qtbot, wz, REVIEW)                                          # C3-17
    assert wz.review_step.summary()["Default outputs"] == "0"
    wz.back()
    st = wz.outputs_step
    rows = add_output(qtbot, wz, "State-wise sales", DO1)
    assert rows == [["Delhi", "380,687.50", "48,131.00", "250"], ["Gujarat", "375,562.50", "47,977.00", "250"],
                    ["Karnataka", "378,125.00", "48,361.50", "250"],
                    ["Maharashtra", "373,000.00", "46,875.00", "250"],
                    ["Grand total", "1,507,375.00", "191,344.50", "1,000"]]
    assert st.preview_info.text().startswith("On the sample · 1,000 rows · 4 result rows · ")
    rows = add_output(qtbot, wz, "Latest month by GST rate", DO2)
    assert rows[:6] == [["Aug-2026", "0", "297,375.00"], ["Aug-2026", "5", "299,425.00"],
                        ["Aug-2026", "12", "301,475.00"], ["Aug-2026", "18", "303,525.00"],
                        ["Aug-2026", "28", "305,575.00"], ["Aug-2026", "Total", "1,507,375.00"]]
    # C3-19: date filters are relative only, plus Blank, Not blank and Is not a date (T55)
    row = st.builder.filters.rows[0]
    assert [row.op.itemText(i) for i in range(row.op.count())] == [
        "latest month in this run", "latest quarter in this run", "latest year in this run", "is blank",
        "is not blank", "is not a date"]
    # C3-18: a name is required
    st.name.setText("  ")
    st._edited()
    nxt(qtbot, wz, OUTPUTS)
    assert st.error.text() == "Every default output needs a name."
    st.name.setText("Latest month by GST rate")
    st._edited()
    nxt(qtbot, wz, REVIEW)
    # C3-20 Review and Save
    rv = wz.review_step.summary()
    assert rv == {"Client": "Acme Traders", "Template name": "Sales Register", "Sample file": "Sample_Sales.xlsx",
                  "Sheets to read": "By name: Sales", "Columns": "8 · 4 Text, 1 Date, 3 Number",
                  "Rules": "13 · 10 Errors, 3 Warnings",
                  "Default outputs": "2 · State-wise sales, Latest month by GST rate"}
    assert wz.review_step.column_rows() == [("Invoice No", "Text", "3"), ("Invoice Date", "Date", "2"),
                                            ("Customer", "Text", "1"), ("GSTIN", "Text", "1"), ("State", "Text", "1"),
                                            ("Taxable Value", "Number", "2"), ("GST Rate", "Number", "2"),
                                            ("Tax Amount", "Number", "1")]
    assert wz.save_button.isVisible() and wz.save_run_button.isVisible() and not wz.next_button.isVisible()
    wz.save(False)
    settle(qtbot, wz.window_)
    cur = wz.window_.current
    assert isinstance(cur, ClientScreen)
    settle(qtbot, wz.window_)
    assert [r[0] for r in cur.visible_rows()] == ["Sales Register"]
    row = cur.visible_rows()[0]
    tid = next(iter(q.template_names(s.con, env["acme"])))
    t = q.load_template(s.con, tid)
    assert t.version == 1 and [c.id for c in t.columns] == [f"c00{i}" for i in range(1, 9)]
    assert t.column(RATE).decimals == 0 and t.source.sheets == SHEETS_BY_NAME and t.source.sheet_names == ["Sales"]
    assert [o.name for o in t.outputs] == ["State-wise sales", "Latest month by GST rate"]
    assert all(o.definition["template_id"] == tid for o in t.outputs)
    assert len(t.rules) == 13
    assert q.template_rows(s.con, env["acme"])[0][4:6] == (0, 0)       # Runs 0, Rows stored 0
    assert not (s.folder.template_dir(tid) / "runs").exists()
    assert staging_dirs(s) == []
    assert row is not None


@spec("C3-21", "F1")
def test_save_and_start_first_run(env, qtbot, fixtures_dir):
    s = env["s"]
    wz = open_wizard(qtbot, env, client="bharat", name="Conversion check", sample="Conversion_Values.csv",
                     fx=fixtures_dir)
    to_step(qtbot, wz, COLUMNS)
    wz.columns_step.widget(2, DECIMALS).setValue(0)                 # Amount0
    nxt(qtbot, wz, RULES)
    rs = wz.rules_step
    for cid in ("c002", "c003", "c004", "c005"):
        rs.set_severity(f"{cid}.type", WARNING)
    settle(qtbot, wz.window_)
    assert counts_by_name(wz) == {("Amount", "Is a number"): 1, ("Amount0", "Is a number"): 1,
                                  ("Doc Date", "Is a date"): 2, ("Due Date", "Is a date"): 1}
    to_step(qtbot, wz, REVIEW)
    seen = []
    wz.window_.routes["new_run"] = lambda w, **kw: seen.append(kw) or True
    wz.save(True)
    settle(qtbot, wz.window_)
    tid = next(iter(q.template_names(s.con, env["bharat"])))
    assert seen == [{"template_id": tid, "name": "Conversion check"}]
    t = q.load_template(s.con, tid)
    assert [(c.name, c.type, c.decimals, c.date_format) for c in t.columns] == [
        ("Case", "Text", None, None), ("Amount", "Number", 2, None), ("Amount0", "Number", 0, None),
        ("Doc Date", "Date", None, "DD-MM-YYYY"), ("Due Date", "Date", None, "DD/MM/YYYY"), ("Code", "Text", None, None)]
    assert all(r.severity == WARNING for r in t.rules) and len(t.rules) == 4 and t.outputs == []


@spec("C3-21")
def test_save_and_start_opens_new_run(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, client="bharat", name="Conversion check", sample="Conversion_Values.csv",
                     fx=fixtures_dir)
    to_step(qtbot, wz, REVIEW)
    wz.save(True)
    settle(qtbot, wz.window_)
    assert wz.window_.current.title == "New run"


# ---------------------------------------------------------------------------------------------- Back
@spec("C3-22", "UX-3")
def test_back_keeps_entries(env, qtbot, fixtures_dir):
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    to_step(qtbot, wz, COLUMNS)
    wz.columns_step.widget(6, DECIMALS).setValue(0)
    wz.columns_step.table.cellWidget(2, 2).setText("Customer Name")
    wz.columns_step.table.cellWidget(2, 2).textEdited.emit("Customer Name")
    nxt(qtbot, wz, RULES)
    tpl_a_rules(wz.rules_step)
    settle(qtbot, wz.window_)
    nxt(qtbot, wz, OUTPUTS)
    add_output(qtbot, wz, "State-wise sales", DO1)
    staged = wz.staged
    while wz.step > SAMPLE:
        wz.back()
        settle(qtbot, wz.window_)
    assert wz.sample_step.name.text() == "Sales Register" and wz.sample_step.file_name.text() == "Sample_Sales.xlsx"
    to_step(qtbot, wz, OUTPUTS)
    assert wz.staged is staged                                      # not read again
    assert wz.source.sheet_names == ["Sales"]
    assert wz.drafts[6].column.decimals == 0 and wz.drafts[2].column.name == "Customer Name"
    assert len(wz.rules_step.all_rules()) == 13
    assert [o.name for o in wz.outputs_step.outputs] == ["State-wise sales"]
    to_step(qtbot, wz, REVIEW)
    assert wz.review_step.column_rows()[2] == ("Customer Name", "Text", "1")


def test_fits_minimum_layout(env, qtbot, fixtures_dir):
    from sankalan.ui import theme
    wz = open_wizard(qtbot, env, sample="Sample_Sales.xlsx", fx=fixtures_dir)
    for step in range(6):
        to_step(qtbot, wz, step)
        hint = wz.minimumSizeHint()
        assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH, (step, hint)
        assert hint.height() <= theme.MIN_LAYOUT.height(), (step, hint)
