"""End-to-end tests of the consolidation engine on dummy files, one test per spec feature."""
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from conftest import spec
from sankalan.core.readers import collect_files, is_encrypted, read_file
from sankalan.core.session import Session, template_from_sample
from sankalan.core.template import Template, TemplateStore, new_column
from sankalan.core.output import OutputExists, TooManyRows, build_filename, write_output
from sankalan.core.validation import gstin_check_char
from sankalan.demo import make_sales_set, purchase_template, sales_template


def sales_session(sales, out_dir, **out):
    t = sales_template()
    t.output.update({"folder": str(out_dir), **out})
    s = Session(t)
    s.add([sales["folder"]])
    s.load()
    return s


def map_jul(s, save_alias=True):
    jul = next(f for f in s.sources if f.name.startswith("Sales_Jul"))
    s.set_mapping(jul, "Invoice Value", "Inv Amt", save_alias=save_alias)
    return jul


def read_xlsx(path, sheet="Consolidated"):
    wb = openpyxl.load_workbook(path)
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    return ws, rows[0], rows[1:]


# ============================================================================ INPUT
@spec("IN-1", "IN-2")
def test_add_files_folder_pattern_and_subfolders(tmp_path, sales):
    """A folder is expanded with a name pattern; subfolders only when switched on."""
    sub = sales["folder"] / "archive"
    sub.mkdir()
    make_sales_set(sub, rows_per_file=30)
    found, _ = collect_files([sales["folder"]], "Sales_*.xlsx", False)
    assert sorted(p.name for p in found) == sorted(sales["files"])
    found_sub, _ = collect_files([sales["folder"]], "Sales_*.xlsx", True)
    assert len(found_sub) == 12
    only_jun, _ = collect_files([sales["folder"]], "*jun*", False)  # case-insensitive pattern
    assert [p.name for p in only_jun] == ["Sales_Jun-2026.xlsx"]
    files, _ = collect_files([sales["folder"] / "Sales_Apr-2026.xlsx", sales["folder"] / "Sales_May-2026.xlsx"])
    assert len(files) == 2


@spec("IN-3")
def test_all_formats_read(misc):
    """.xlsx, .xlsm, .xls, .csv and delimited .txt are all read into the same columns."""
    for key in ("xlsm", "xls", "csv_bom_comma", "txt_pipe", "title_rows"):
        fd = read_file(misc[key])[0]
        assert fd.status in ("OK", "warning"), (key, fd.error)
        assert fd.headers == ["Bill No", "Bill Date", "Supplier", "GSTIN", "Invoice Type", "Amount"], key
        assert len(fd.rows) == 3, key


@spec("IN-4")
def test_csv_encoding_and_delimiter_detection(misc):
    """UTF-8 with BOM / comma, UTF-8 / semicolon, Windows-1252 / tab and pipe are detected; override works."""
    cases = {"csv_bom_comma": ("utf-8-sig", ","), "csv_utf8_semicolon": ("utf-8", ";"),
             "csv_cp1252_tab": ("cp1252", "\t"), "txt_pipe": ("utf-8", "|")}
    for key, (enc, delim) in cases.items():
        fd = read_file(misc[key])[0]
        assert (fd.csv_encoding, fd.csv_delimiter) == (enc, delim), key
        assert fd.rows[1][2] == "Café Mocha Traders", key
    forced = read_file(misc["csv_utf8_semicolon"], csv_delimiter=",")[0]
    assert forced.csv_delimiter == "," and len(forced.headers) == 1   # manual override is honoured


@spec("IN-5")
def test_sheet_selection_modes(misc):
    """First visible sheet, sheet by name, every sheet matching a pattern."""
    assert read_file(misc["multi"])[0].sheet == "Summary"
    assert read_file(misc["multi"], sheet_mode="name", sheet_value="sales south")[0].sheet == "Sales South"
    both = read_file(misc["multi"], sheet_mode="pattern", sheet_value="Sales*")
    assert [f.sheet for f in both] == ["Sales North", "Sales South"]
    assert sum(len(f.rows) for f in both) == 3
    missing = read_file(misc["multi"], sheet_mode="name", sheet_value="Nope")[0]
    assert missing.status == "error" and "no sheet named" in missing.error


@spec("IN-5", "IN-6")
def test_per_file_overrides_in_session(sales, out_dir):
    """Sheet and header row can be overridden for one file without affecting others."""
    s = sales_session(sales, out_dir)
    jul = next(f for f in s.sources if f.name.startswith("Sales_Jul"))
    assert jul.header_row == 3
    s.set_file_options(jul.path, header_row=1)
    jul2 = next(f for f in s.sources if f.name.startswith("Sales_Jul"))
    assert jul2.header_row == 1 and jul2.headers[0] == "Acme Traders — Sales July 2026"
    apr = next(f for f in s.sources if f.name.startswith("Sales_Apr"))
    assert apr.header_row == 1
    s.set_file_options(jul.path, header_row=None)
    assert next(f for f in s.sources if f.name.startswith("Sales_Jul")).header_row == 3


@spec("IN-6")
def test_header_auto_detection(misc, sales):
    """Title rows above the header are skipped, with and without a template's known column names."""
    fd = read_file(misc["title_rows"])[0]
    assert fd.header_row == 4 and fd.headers[0] == "Bill No"
    t = sales_template()
    jul = read_file(sales["folder"] / "Sales_Jul-2026.xlsx", known_names=t.known_names())[0]
    assert jul.header_row == 3 and "Inv Amt" in jul.headers


@spec("IN-7", "IN-8")
def test_trailer_and_blank_rows_dropped(misc, sales):
    """'Total'/'Grand Total' rows and fully blank rows are not data."""
    fd = read_file(misc["zeros"])[0]
    assert len(fd.rows) == 2 and fd.trailer_rows == 1 and fd.blank_rows == 2
    jul = read_file(sales["folder"] / "Sales_Jul-2026.xlsx")[0]
    assert jul.trailer_rows == 1 and len(jul.rows) == 300


@spec("IN-9")
def test_password_protected_file(misc, out_dir, tmp_path):
    """Encrypted workbooks need the password; a wrong one is refused; the password is never stored."""
    p = misc["password"]
    assert is_encrypted(p)
    t = purchase_template()
    t.output["folder"] = str(out_dir)
    s = Session(t)
    s.add([p])
    s.load()
    assert s.needs_password == [p] and s.sources[0].status == "password"
    s.set_password(p, "wrong")
    assert s.sources[0].status == "password"
    s.set_password(p, "acme@123")
    assert s.sources[0].status == "OK" and len(s.sources[0].rows) == 3
    store = TemplateStore(tmp_path / "tpl")
    s.save_template(store)
    assert "acme@123" not in store.list()[0].path.read_text()


@spec("IN-10")
def test_lock_files_and_duplicates_skipped(sales):
    """Excel lock files (~$...) and a file added twice are listed as skipped."""
    f = sales["folder"]
    s = Session(sales_template())
    s.add([f])
    s.add([f / "Sales_Apr-2026.xlsx"])
    reasons = {(x.path.name, x.reason) for x in s.skipped}
    assert ("~$Sales_Sep-2026.xlsx", "Excel lock file") in reasons
    assert ("Sales_Apr-2026.xlsx", "same file added twice") in reasons
    assert len(s.paths) == 6


@spec("IN-11", "IN-13")
def test_file_list_status_and_hidden_data(sales, out_dir):
    """Each file reports sheet, header row, rows, columns, status; hidden rows/sheets are skipped and listed."""
    s = sales_session(sales, out_dir)
    by = {f.name: f for f in s.sources}
    for name, n in sales["files"].items():
        assert len(by[name].rows) == n, name
        assert len(by[name].headers) == 7
    assert by["Sales_Apr-2026.xlsx"].status == "OK"
    assert by["Sales_Jun-2026.xlsx"].hidden_rows == 12 and "12 hidden rows skipped" in by["Sales_Jun-2026.xlsx"].notes
    aug = by["Sales_Aug-2026.xlsx"]
    assert aug.sheet == "Sales" and aug.hidden_sheets == ["Old"] and aug.status == "warning"
    assert by["Sales_Jul-2026.xlsx"].status == "warning"
    xls = read_file(Path(sales["folder"]).parent / "none.xls")  # missing file -> error, not a crash
    assert xls[0].status == "error"


@spec("IN-12")
def test_preview_first_200_rows(sales):
    """The preview holds the first 200 rows exactly as read, with original row numbers."""
    jul = read_file(sales["folder"] / "Sales_Jul-2026.xlsx")[0]
    assert len(jul.preview) == 200
    assert jul.preview[0] == (1, ["Acme Traders — Sales July 2026"] + [None] * 6)
    assert jul.preview[2][1][6] == "Inv Amt"


@spec("IN-13")
def test_hidden_rows_in_xls(misc):
    """Hidden rows are skipped in old .xls files too."""
    fd = read_file(misc["xls"])[0]
    assert fd.hidden_rows == 1 and len(fd.rows) == 3
    assert isinstance(fd.rows[0][1], type(fd.rows[0][1])) and fd.rows[0][1].year == 2026


def test_corrupt_file_reported_not_crashing(misc):
    fd = read_file(misc["corrupt"])[0]
    assert fd.status == "error" and fd.error


# ============================================================================ MAPPING
@spec("MAP-1", "TPL-3")
def test_template_from_reference_file(sales):
    """A new template takes its columns and guessed types from a sample file."""
    t = template_from_sample(sales["folder"] / "Sales_Apr-2026.xlsx", "Acme", "Sales")
    assert [c["name"] for c in t.columns] == ["Invoice No", "Invoice Date", "Company Name", "GSTIN",
                                              "Place of Supply", "Taxable Value", "Invoice Value"]
    types = {c["name"]: c["type"] for c in t.columns}
    assert types["Invoice Date"] == "date" and types["Taxable Value"] == "number" and types["GSTIN"] == "text"
    assert {r["type"] for r in t.column("GSTIN")["rules"]} == {"gstin_format", "gstin_state", "gstin_checksum"}


@spec("MAP-2", "MAP-3")
def test_auto_match_and_aliases(sales, out_dir):
    """Headers match ignoring case/spaces/dots/underscores/hyphens; aliases match other names."""
    from sankalan.core.mapping import auto_map
    cols = sales_template().columns
    m = auto_map(cols, ["invoice_no", "INVOICE-DATE", "Company.Name", "GST No", "place of supply",
                        "Taxable  Value", "Invoice Value"])
    assert all(src for src, _ in m.values())
    assert m["GSTIN"] == ("GST No", "alias") and m["Invoice No"] == ("invoice_no", "name")
    s = sales_session(sales, out_dir)
    sep = next(f for f in s.sources if f.name.startswith("Sales_Sep"))
    assert s.mapping_for(sep)["GSTIN"] == ("GST No", "alias")


@spec("MAP-4", "MAP-6")
def test_required_unmapped_blocks_until_mapped(sales, out_dir):
    """Jul's 'Inv Amt' doesn't match Invoice Value (required) -> blocking problem until mapped."""
    s = sales_session(sales, out_dir)
    assert [(f.name, t) for f, t in s.mapping_problems()] == [("Sales_Jul-2026.xlsx", "Invoice Value")]
    v = s.validate()
    assert any(i.rule == "mapping" for i in v.errors)
    with pytest.raises(PermissionError):
        s.write()
    map_jul(s)
    assert s.mapping_problems() == []


@spec("MAP-5", "TPL-6")
def test_learned_alias_maps_next_month_automatically(sales, out_dir, tmp_path):
    """Saving 'Inv Amt' as an alias means the next run maps it without asking."""
    store = TemplateStore(tmp_path / "tpl")
    s = sales_session(sales, out_dir)
    map_jul(s, save_alias=True)
    assert s.new_aliases == [("Invoice Value", "Inv Amt")]
    s.save_template(store)
    t2 = store.list()[0]
    s2 = Session(t2)
    s2.add([sales["folder"]])
    s2.load()
    assert s2.mapping_problems() == [] and s2.unmatched() == []


@spec("MAP-6")
def test_optional_unmapped_is_left_blank(sales, out_dir):
    """An optional output column with no match is written blank."""
    s = sales_session(sales, out_dir, source_file=False, source_row=False)
    map_jul(s)
    s.template.columns.append(new_column("Remarks", "text", required=False))
    s.validate()
    s.write(override_errors=True)
    _, hdr, rows = read_xlsx(next(out_dir.glob("*.xlsx")))
    assert hdr[-1] == "Remarks" and all(r[-1] is None for r in rows)


@spec("MAP-7")
def test_extra_columns_drop_or_keep(misc, out_dir):
    """Unmapped source columns are dropped by default, or kept at the end."""
    t = purchase_template()
    t.columns = [c for c in t.columns if c["name"] != "Supplier"]
    t.output.update({"folder": str(out_dir), "source_file": False, "source_row": False, "issues_sheet": False})
    s = Session(t)
    s.add([misc["xlsm"]])
    s.load()
    assert s.extra_headers() == ["Supplier"]
    s.validate()
    r = s.write()
    _, hdr, _ = read_xlsx(r.path)
    assert "Supplier" not in hdr
    t.extra_columns = "keep"
    s.validation = None
    r = s.write(overwrite=True)
    _, hdr, rows = read_xlsx(r.path)
    assert hdr[-1] == "Supplier" and rows[0][-1] == "Kaveri Textiles"


@spec("MAP-8")
def test_rename_reorder_include_exclude(misc, out_dir):
    """Output columns can be renamed (old name kept as alias), reordered and excluded."""
    t = purchase_template()
    t.output.update({"folder": str(out_dir), "source_file": False, "source_row": False})
    amt = t.column("Amount")
    amt["name"], amt["aliases"] = "Bill Amount", ["Amount"]
    t.columns.insert(0, t.columns.pop(t.columns.index(amt)))
    t.column("Supplier")["include"] = False
    s = Session(t)
    s.add([misc["csv_bom_comma"]])
    s.load()
    s.validate()
    _, hdr, rows = read_xlsx(s.write().path)
    assert list(hdr) == ["Bill Amount", "Bill No", "Bill Date", "GSTIN", "Invoice Type"]
    assert rows[1][0] == 2500.5


@spec("MAP-9", "MAP-10")
def test_types_and_leading_zeros(misc, out_dir, sales):
    """Text keeps '00123'; numbers read Indian grouping, ₹ and (negatives); text dates become dates."""
    t = purchase_template()
    t.output.update({"folder": str(out_dir), "source_file": False, "source_row": False})
    s = Session(t)
    s.add([misc["zeros"]])
    s.load()
    s.validate()
    _, _, rows = read_xlsx(s.write().path)
    assert [r[0] for r in rows] == ["00123", "00456"]
    from sankalan.core.convert import to_date, to_number
    assert to_number("1,23,456.00") == (123456.0, True)
    assert to_number("₹ 500") == (500.0, True) and to_number("Rs. 1,000") == (1000.0, True)
    assert to_number("(1,234)") == (-1234.0, True)
    assert to_number("abc") == ("abc", False)
    assert to_date("05/09/2026")[0] == date(2026, 9, 5)
    assert to_date("05/09/2026", "MDY")[0] == date(2026, 5, 9)
    assert to_date(46271)[0] == date(2026, 9, 6)
    s2 = sales_session(sales, out_dir / "x", source_file=False, source_row=False)
    map_jul(s2)
    s2.validate()
    ws, hdr, rows = read_xlsx(s2.write(override_errors=True).path)
    sep_rows = [r for r in rows if isinstance(r[1], __import__("datetime").datetime) and r[1].month == 9]
    assert len(sep_rows) == 300                    # text dates in Sep converted to real dates
    assert all(isinstance(r[5], (int, float)) for r in rows)   # no text left in the number column
    assert any(r[5] == 123456.0 for r in rows) and any(r[5] == -1000.0 for r in rows)


# ============================================================================ VALIDATION
@spec("VAL-1", "VAL-2", "VAL-3", "VAL-4", "VAL-11")
def test_sales_run_finds_exactly_the_planted_problems(sales, out_dir):
    """3 errors (check character, 14-char GSTIN, cross-file duplicate) and 16 warnings, at the right rows."""
    s = sales_session(sales, out_dir)
    map_jul(s)
    v = s.validate()
    got_err = sorted((i.rule, i.file, i.row) for i in v.errors)
    assert got_err == sorted(sales["errors"])
    got_warn = sorted((i.rule, i.file, i.row) for i in v.warnings)
    assert got_warn == sorted(sales["warnings"])
    dup = next(i for i in v.errors if i.rule == "duplicates")
    assert "Sales_Apr-2026.xlsx, row 7" in dup.message
    fmt = next(i for i in v.errors if i.rule == "gstin_format")
    assert "has 14 characters" in fmt.message
    assert v.rows_checked == sales["rows"]


@spec("VAL-2", "VAL-3", "VAL-4", "VAL-5")
def test_identifier_rules():
    """GSTIN pattern, state code and check character; PAN pattern; exception list."""
    from sankalan.core.validation import check_value
    good = "27AAPFU0939F1ZV"
    assert gstin_check_char(good[:14]) == "V"
    r = lambda k: {"type": k}
    assert check_value(r("gstin_format"), good, good, True, "text") is None
    assert "15" in check_value(r("gstin_format"), good[:14], good[:14], True, "text")
    assert check_value(r("gstin_format"), "27aapfu0939f1zv", "27aapfu0939f1zv", True, "text") is None
    bad_state = "40" + good[2:14]
    bad_state += gstin_check_char(bad_state)
    assert "state code 40" in check_value(r("gstin_state"), bad_state, bad_state, True, "text")
    assert "check character" in check_value(r("gstin_checksum"), "27AAPFU0939F1ZW", "27AAPFU0939F1ZW", True, "text")
    un = "0717UNO00157UNO"
    assert check_value(r("gstin_format"), un, un, True, "text", exceptions={un}) is None
    assert check_value(r("pan_format"), "AAPFU0939F", "AAPFU0939F", True, "text") is None
    assert check_value(r("pan_format"), "AAPF0939F", "AAPF0939F", True, "text")


@spec("VAL-6", "VAL-7", "VAL-8", "VAL-9", "VAL-10")
def test_value_rules(tmp_path, out_dir):
    """Is a number, number range, is a date, date range and allowed values on a purchase file."""
    p = tmp_path / "p.csv"
    p.write_text("Bill No,Bill Date,Supplier,GSTIN,Invoice Type,Amount\n"
                 "B1,01-09-2026,A,27AAPFU0939F1ZV,B2B,100\n"
                 "B2,15-10-2026,A,27AAPFU0939F1ZV,Import,abc\n"
                 "B3,not a date,A,27AAPFU0939F1ZV,b2c,-5\n", encoding="utf-8")
    t = purchase_template()
    t.column("Amount")["rules"].append({"type": "number_range", "severity": "warning", "min": 0, "max": 1000})
    s = Session(t)
    s.add([p])
    s.load()
    v = s.validate()
    got = {(i.rule, i.row, i.severity) for i in v.issues}
    assert ("is_number", 3, "error") in got
    assert ("date_range", 3, "error") in got
    assert ("allowed_values", 3, "error") in got
    assert ("is_date", 4, "error") in got
    assert ("number_range", 4, "warning") in got
    assert not any(i.row == 2 for i in v.issues)
    assert not any(i.rule == "allowed_values" and i.row == 4 for i in v.issues)   # b2c case-insensitive


@spec("VAL-severity", "D4")
def test_errors_stop_run_override_writes(sales, out_dir):
    """Errors: no output until fixed or overridden. Warnings: output written."""
    s = sales_session(sales, out_dir)
    map_jul(s)
    s.validate()
    with pytest.raises(PermissionError):
        s.write()
    assert list(out_dir.iterdir()) == []
    res = s.write(override_errors=True)
    assert res.errors_overridden == 3 and res.rows_written == sales["rows"]


@spec("VAL-severity", "D4")
def test_recheck_after_source_files_fixed(sales, out_dir):
    """After the executive fixes the source files, re-check finds no errors and the run completes."""
    s = sales_session(sales, out_dir)
    map_jul(s)
    assert len(s.validate().errors) == 3
    make_sales_set(sales["folder"], rows_per_file=300, fixed=True)
    s.load()
    v = s.validate()
    assert v.errors == [] and len(v.warnings) == 16
    res = s.write()
    assert res.path.exists() and res.totals_match


@spec("VAL-report")
def test_issue_report_summary_and_export(sales, out_dir):
    """Issue summary per check and per file; detail has file, sheet, row, column, value; export to .xlsx."""
    s = sales_session(sales, out_dir)
    map_jul(s)
    v = s.validate()
    by_rule = v.by_rule()
    assert by_rule[("not_blank", "warning")]["count"] == 14
    assert by_rule[("not_blank", "warning")]["files"] == ["Sales_Jul-2026.xlsx"]
    assert v.by_file()["Sales_Jun-2026.xlsx"]["error"] == 1
    path = s.export_issues(out_dir / "issues.xlsx")
    _, hdr, rows = read_xlsx(path, "Issues")
    assert list(hdr) == ["File", "Sheet", "Row", "Column", "Value", "Check", "Severity", "Problem"]
    assert len(rows) == 19
    assert ("Sales_Jun-2026.xlsx", "Sales", 214, "GSTIN") in {r[:4] for r in rows}


# ============================================================================ OUTPUT
@spec("OUT-1", "OUT-4", "OUT-6", "OUT-9", "OUT-11")
def test_xlsx_output_end_to_end(sales, out_dir):
    """Clean run to .xlsx: traceability columns, formatting, summary, totals match the inputs."""
    make_sales_set(sales["folder"], rows_per_file=300, fixed=True)
    s = sales_session(sales, out_dir, source_sheet=True)
    map_jul(s)
    s.validate()
    res = s.write()
    assert res.path.name == "Acme-Traders_Monthly-Sales-Register_202609.xlsx"
    ws, hdr, rows = read_xlsx(res.path)
    assert list(hdr[:3]) == ["Source File", "Source Sheet", "Source Row"]
    assert len(rows) == sales["rows"] == res.rows_written == res.rows_read
    jul = [r for r in rows if r[0] == "Sales_Jul-2026.xlsx"]
    assert jul[0][2] == 4 and jul[0][1] == "Sales"          # traceable to the source row
    assert ws.freeze_panes == "A2" and ws.auto_filter.ref
    assert ws["A1"].font.b
    assert ws.cell(2, 5).number_format.lower() == "dd-mm-yyyy"
    assert ws.column_dimensions["D"].width >= len("Invoice Date")
    assert res.files_read == 6 and res.rows_left_out == 0 and res.warnings == 16
    assert 'Sales_Jun-2026.xlsx: 12 hidden rows' in res.hidden
    assert 'Sales_Aug-2026.xlsx: hidden sheet "Old"' in res.hidden
    tot = {t.column: t for t in res.totals}
    assert set(tot) == {"Taxable Value", "Invoice Value"}
    assert all(t.match for t in tot.values())
    assert round(tot["Taxable Value"].input_total, 2) == make_sales_set(
        out_dir / "_x", rows_per_file=300, fixed=True)["taxable"]


@spec("OUT-2")
def test_excel_row_limit(tmp_path):
    """More than 1,048,575 data rows can't go to .xlsx; the app says to use CSV."""
    rows = [[1]] * 1_048_576
    with pytest.raises(TooManyRows) as e:
        write_output(tmp_path / "big.xlsx", ["A"], ["number"], rows)
    assert "CSV" in str(e.value)
    assert not (tmp_path / "big.xlsx").exists()


@spec("OUT-1", "OUT-3")
def test_csv_output_options(sales, out_dir):
    """CSV: UTF-8 with BOM by default, plain UTF-8 and other delimiters on request; totals still checked."""
    make_sales_set(sales["folder"], rows_per_file=300, fixed=True)
    s = sales_session(sales, out_dir, format="csv")
    map_jul(s)
    s.validate()
    r = s.write()
    raw = r.path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and r.totals_match
    s.template.output.update({"csv_encoding": "utf-8", "csv_delimiter": ";"})
    r2 = s.write(overwrite=True)
    raw2 = r2.path.read_bytes()
    assert not raw2.startswith(b"\xef\xbb\xbf")
    lines = raw2.decode("utf-8").splitlines()
    assert lines[0].split(";")[:3] == ["Source File", "Source Row", "Invoice No"]
    assert len(lines) == sales["rows"] + 1
    row = next(csv.reader([lines[1]], delimiter=";"))
    assert row[3].count("-") == 2 and len(row[3]) == 10        # DD-MM-YYYY
    assert r2.totals_match


@spec("OUT-5")
def test_file_naming_and_overwrite(tmp_path):
    """Name pattern tokens; a file that exists is not replaced without confirmation."""
    n = build_filename("{client}_{task}_{yyyymm}", "Acme Traders", "Sales: Monthly/Reg", "xlsx", date(2026, 9, 30))
    assert n == "Acme-Traders_Sales-MonthlyReg_202609.xlsx"
    assert build_filename("{client}-{date}", "A", "B", "csv").endswith(".csv")
    p = tmp_path / "x.xlsx"
    write_output(p, ["A"], ["text"], [["1"]])
    with pytest.raises(OutputExists):
        write_output(p, ["A"], ["text"], [["2"]])
    write_output(p, ["A"], ["text"], [["2"]], overwrite=True)
    assert openpyxl.load_workbook(p).active["A2"].value == "2"


@spec("OUT-7", "OUT-8")
def test_indian_format_and_issues_sheet(sales, out_dir):
    """Number columns use 1,23,45,678.00 grouping (negatives standard); warnings go to an Issues sheet."""
    s = sales_session(sales, out_dir)
    map_jul(s)
    s.validate()
    res = s.write(override_errors=True)
    wb = openpyxl.load_workbook(res.path)
    ws = wb["Consolidated"]
    hdr = [c.value for c in ws[1]]
    ci = hdr.index("Taxable Value") + 1
    fmts = {ws.cell(r, ci).number_format for r in range(2, ws.max_row + 1) if ws.cell(r, ci).value is not None}
    assert any("##\\,##\\,##0.00" in f for f in fmts)
    neg = [ws.cell(r, ci) for r in range(2, ws.max_row + 1) if (ws.cell(r, ci).value or 0) < 0]
    assert neg and all(c.number_format == "#,##0.00" for c in neg)
    assert "Issues" in wb.sheetnames and wb["Issues"].max_row == 17      # 16 warnings + header
    s.template.output.update({"indian_format": False, "issues_sheet": False})
    res2 = s.write(override_errors=True, overwrite=True)
    wb2 = openpyxl.load_workbook(res2.path)
    assert wb2.sheetnames == ["Consolidated"]


@spec("OUT-11")
def test_totals_check_detects_a_mismatch(sales, out_dir, monkeypatch):
    """If the written file's totals differ from the inputs, the check says Mismatch."""
    import sankalan.core.session as sess
    make_sales_set(sales["folder"], rows_per_file=300, fixed=True)
    s = sales_session(sales, out_dir)
    map_jul(s)
    s.validate()
    real = sess.read_back_totals
    monkeypatch.setattr(sess, "read_back_totals",
                        lambda *a, **k: {c: v + 1.0 for c, v in real(*a, **k).items()})
    res = s.write()
    assert not res.totals_match and all(not t.match for t in res.totals)


# ============================================================================ TEMPLATES
@spec("TPL-1", "TPL-2", "TPL-4", "TPL-5", "TPL-7")
def test_template_store_lifecycle(tmp_path):
    """Save, list by client, search, duplicate, rename, delete; one JSON per template; version + dates."""
    store = TemplateStore(tmp_path / "shared")
    t = sales_template()
    store.save(t)
    p = Path(t.path)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["client"] == "Acme Traders" and data["version"] == 1
    for key in ("input", "columns", "duplicate_keys", "output", "created", "modified"):
        assert key in data
    assert data["columns"][3]["aliases"] == ["GSTIN/UIN", "GST No"]
    store.save(purchase_template())
    assert [x.client for x in store.list()] == ["Acme Traders", "Blue Lotus Pvt Ltd"]
    assert [x.task for x in store.list("purchase")] == ["Purchase Register"]
    d = store.duplicate(t, "Monthly Sales Register (copy)")
    assert len(store.list()) == 3 and d.version == 1
    with pytest.raises(ValueError):
        store.duplicate(t, "Monthly Sales Register (copy)")
    store.rename(d, "Acme Traders", "Quarterly Sales")
    assert {x.task for x in store.list("acme")} == {"Monthly Sales Register", "Quarterly Sales"}
    assert not any("copy" in f.name for f in (tmp_path / "shared").glob("*.json"))
    store.save(t)
    assert store.list("monthly")[0].version == 2
    store.delete(d)
    assert len(store.list()) == 2
    other_pc = TemplateStore(tmp_path / "shared")       # TPL-5: another PC pointing at the same folder
    assert len(other_pc.list()) == 2


@spec("TPL-6")
def test_fast_rerun_with_saved_template(sales, out_dir, tmp_path):
    """Second month: template run needs no mapping when all headers match."""
    store = TemplateStore(tmp_path / "tpl")
    s = sales_session(sales, out_dir)
    map_jul(s)
    s.save_template(store)
    t = store.list()[0]
    t.output["folder"] = str(out_dir)
    s2 = Session(t)
    s2.add([sales["folder"]])
    s2.load()
    assert s2.unmatched() == []
    assert len(s2.validate().errors) == 3
