"""Probe: the Files-step list (IN-1 to IN-15, RUN-7, TPL-6; RUNF-01 to RUNF-13)."""
import shutil
import sys
from pathlib import Path

import pytest

from conftest import new_run, run_job, spec, stage_fake_run, tpl_a_columns, tpl_a_settings, tpl_c_columns
from sankalan.db import datafolder
from sankalan.ingest import probe as P
from sankalan.ingest import source
from sankalan.ingest.stage import probe
from sankalan.jobs import JobRunner
from sankalan.model.template import SourceSettings
from sankalan.query import catalogue as q


def _probe(fx, names, settings=None, columns=None, runner=None, template_id=None, workers=0, existing=()):
    runner = runner or JobRunner()
    paths = [str(fx / n) for n in names]
    return run_job(runner, lambda ctx: probe(ctx, paths, settings=settings or tpl_a_settings(),
                                             columns=tpl_a_columns() if columns is None else columns,
                                             template_id=template_id, existing=existing, workers=workers))


@spec("RUNF-02", "IN-11", "RUNF-12", "TPL-6")
def test_f02_row(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Sales_Oct.xlsx"])
    path = fixtures_dir / "Sales_Oct.xlsx"
    assert (row.file_name, row.sheet, row.status, row.header_row) == ("Sales_Oct.xlsx", "Sales", P.READY, 1)
    assert row.size == path.stat().st_size and row.rows_approx == 5000
    assert row.headers == ["Invoice No", "Invoice Date", "Customer", "GSTIN", "State", "Taxable Value", "GST Rate",
                           "Tax Amount"]
    assert row.headers_match is True                     # RUNF-12: Mapping is skipped
    import hashlib
    assert row.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@spec("RUNF-03", "IN-3", "C3-04", "D38")
def test_xlsm_and_xls_accepted_txt_refused(fixtures_dir):
    rows = _probe(fixtures_dir, ["Sales_Macro.xlsm", "Sales_Old.xls", "Sales_Notes.txt"])
    assert [(r.file_name, r.status) for r in rows] == [("Sales_Macro.xlsm", P.READY), ("Sales_Old.xls", P.READY),
                                                       ("Sales_Notes.txt", P.REFUSED)]
    assert rows[0].kind == "xlsm" and rows[0].rows_approx == 500
    assert (rows[1].kind, rows[1].sheet, rows[1].header_row, rows[1].rows_approx) == ("xls", "Sales", 1, 100)
    assert rows[1].headers_match is True
    assert rows[2].message == "Sales_Notes.txt: only .xlsx, .xlsm, .xlsb, .xls and .csv files can be added."


@spec("RUNF-15", "IN-3", "IN-13", "T11", "D38")
@pytest.mark.parametrize("name,kind", [("Sales_Nov.xls", "xls"), ("Sales_Nov.xlsb", "xlsb")])
def test_xls_and_xlsb_like_f03(fixtures_dir, name, kind):
    (ref,) = _probe(fixtures_dir, ["Sales_Nov.xlsx"])
    (row,) = _probe(fixtures_dir, [name])
    assert (row.kind, row.sheet, row.header_row, row.status) == (kind, "Sales", 2, P.READY)
    assert row.hidden_sheets == ["Old"] and row.hidden_rows == 25
    assert row.headers == ref.headers and row.headers_match is True
    assert row.rows_approx == ref.rows_approx
    assert row.notes == ref.notes


@spec("RUNF-16", "IN-9", "IN-15", "D38")
def test_password_protected_xls_and_xlsb(fixtures_dir):
    rows = _probe(fixtures_dir, ["Sales_Protected.xls", "Sales_Protected.xlsb"])
    assert [(r.status, r.problem) for r in rows] == [(P.ERROR, "password")] * 2
    assert rows[0].message == ("Sales_Protected.xls is password-protected. Remove the password at source, or "
                               "exclude the file.")


@spec("RUNF-17", "IN-15", "D38")
def test_web_page_named_xls(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Sales_Export.xls"])
    assert (row.status, row.problem) == (P.ERROR, "web_page")
    assert row.message == ("Sales_Export.xls is a web page or XML file with an Excel name. Open it in Excel and "
                           "save it as .xlsx.")


def _rename_workbook_stream(data: bytes, new_name: str) -> bytes:
    """The F11 container with its 'Workbook' directory entry renamed."""
    old = "Workbook".encode("utf-16-le") + b"\0\0"
    i = data.index(old)
    enc = new_name.encode("utf-16-le") + b"\0\0"
    out = bytearray(data)
    out[i:i + 64] = enc.ljust(64, b"\0")
    out[i + 64:i + 66] = len(enc).to_bytes(2, "little")
    return bytes(out)


def test_excel_95_and_other_office_files(fixtures_dir, tmp_path):
    """An OLE file with only a 'Book' stream is Excel 5.0/95; one with neither stream isn't a workbook."""
    data = (fixtures_dir / "Sales_Old.xls").read_bytes()
    (tmp_path / "Old95.xls").write_bytes(_rename_workbook_stream(data, "Book"))
    (tmp_path / "Letter.xls").write_bytes(_rename_workbook_stream(data, "WordDocument"))
    old, other = _probe(tmp_path, ["Old95.xls", "Letter.xls"])
    assert (old.status, old.problem, old.message) == (
        P.ERROR, "old_excel", "Old95.xls was saved in a format older than Excel 97. Open it in Excel and save it "
                              "as .xlsx.")
    assert (other.status, other.problem, other.message) == (P.ERROR, "not_excel",
                                                            "Letter.xls isn't a valid Excel workbook.")


@spec("RUNF-04", "IN-6", "IN-13", "IN-5")
def test_f03_header_row_2_and_hidden_data(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Sales_Nov.xlsx"])
    assert (row.sheet, row.header_row, row.status) == ("Sales", 2, P.READY)      # Notes is not listed
    assert row.hidden_sheets == ["Old"] and row.hidden_rows == 25
    assert "Hidden sheet Old skipped." in row.notes and "25 hidden rows skipped." in row.notes


@spec("RUNF-05", "IN-9", "IN-15")
def test_password_protected(fixtures_dir):
    rows = _probe(fixtures_dir, ["Sales_Oct.xlsx", "Sales_Protected.xlsx"])
    assert rows[0].status == P.READY
    assert (rows[1].status, rows[1].problem) == (P.ERROR, "password")
    assert rows[1].message.startswith("Sales_Protected.xlsx is password-protected")


class _HeldOpen:
    """Hold a file the way Excel does: open for read and write, other programs may only read."""

    def __init__(self, path: Path):
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows sharing modes")
@spec("RUNF-06", "IN-10", "IN-15", "UI-6")
def test_file_open_in_another_program(fixtures_dir, tmp_path):
    locked = tmp_path / "Sales_Locked.xlsx"
    shutil.copyfile(fixtures_dir / "Sales_Locked.xlsx", locked)
    lock = tmp_path / "~$Sales_Locked.xlsx"
    lock.write_bytes(b"owner")
    held = _HeldOpen(locked)
    try:
        rows = _probe(tmp_path, ["Sales_Locked.xlsx", "~$Sales_Locked.xlsx"])
    finally:
        held.close()
    assert [(r.file_name, r.status) for r in rows] == [("Sales_Locked.xlsx", P.ERROR),
                                                       ("~$Sales_Locked.xlsx", P.SKIPPED)]
    assert rows[0].message == "Sales_Locked.xlsx is open in another program. Close it, then Re-check."
    assert rows[0].problem == "locked"
    (again,) = _probe(tmp_path, ["Sales_Locked.xlsx"])                  # Re-check after closing
    assert again.status == P.READY and again.rows_approx == 1000


@spec("RUNF-07", "IN-15")
def test_sheet_not_found(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Sales_WrongSheet.xlsx"])
    assert (row.status, row.problem, row.message) == (P.ERROR, "sheet", "Sheet Sales not found.")


@spec("RUNF-08", "IN-6", "IN-15")
def test_header_not_found(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Sales_NoHeader.xlsx"])
    assert (row.status, row.problem) == (P.ERROR, "header") and row.header_row is None


@spec("RUNF-09")
def test_files_in_error_are_marked(fixtures_dir):
    rows = _probe(fixtures_dir, ["Sales_Oct.xlsx", "Sales_Protected.xlsx", "Sales_NoHeader.xlsx",
                                 "Sales_WrongSheet.xlsx"])
    assert [r.status for r in rows] == [P.READY, P.ERROR, P.ERROR, P.ERROR]
    assert [r.readable for r in rows] == [True, False, False, False]


@spec("RUNF-10", "IN-10")
def test_same_file_twice(fixtures_dir):
    rows = _probe(fixtures_dir, ["Sales_Oct.xlsx", "Sales_Oct.xlsx"])
    assert [r.status for r in rows] == [P.READY, P.SKIPPED]
    assert rows[1].message == "Same file added twice, skipped."
    (again,) = _probe(fixtures_dir, ["Sales_Oct.xlsx"], existing=[str(fixtures_dir / "Sales_Oct.xlsx")])
    assert again.status == P.SKIPPED


@spec("RUNF-01", "IN-1")
def test_folder_refused(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Run_Folder"])
    assert row.status == P.REFUSED and "Folders can't be added" in row.message


@spec("RUNF-11", "RUN-7", "C2-08")
def test_duplicate_contents_warning(fixtures_dir, storage):
    tid = q.insert_template(storage.con, q.insert_client(storage.con, "Acme Traders"), "Sales Register")
    other = q.insert_template(storage.con, q.insert_client(storage.con, "Bharat Foods"), "Copy")
    run = new_run(tid)
    run.files[0].sha256 = source.sha256_of(open(fixtures_dir / "Sales_Oct.xlsx", "rb"))
    datafolder.commit(storage.con, storage.folder, stage_fake_run(storage), run)
    loaded_on = q.list_runs(storage.con, tid)[0].loaded_on

    (row,) = _probe(fixtures_dir, ["Sales_Oct_copy.xlsx"], runner=storage.runner, template_id=tid)
    assert row.status == P.WARNING and row.duplicate_of == {"run": "R-0001", "loaded_on": loaded_on}
    assert row.message == (f"Sales_Oct_copy.xlsx has the same contents as a file loaded in R-0001 on "
                           f"{loaded_on:%d-%m-%Y}. Remove it, or Load anyway.")
    assert row.readable                                         # Load anyway keeps it
    (other_row,) = _probe(fixtures_dir, ["Sales_Oct_copy.xlsx"], runner=storage.runner, template_id=other)
    assert other_row.status == P.READY                          # per template only
    (f03,) = _probe(fixtures_dir, ["Sales_Nov.xlsx"], runner=storage.runner, template_id=tid)
    assert f03.status == P.READY


@spec("RUNF-13", "IN-5", "IN-13", "C3-07")
def test_one_row_per_sheet(fixtures_dir):
    rows = _probe(fixtures_dir, ["Sales_Regions.xlsx"], settings=SourceSettings(sheets="all"))
    assert [(r.sheet, r.status, r.rows_approx) for r in rows] == [("North", P.READY, 1500),
                                                                   ("South", P.READY, 2500)]
    assert all(r.hidden_sheets == ["Archive"] for r in rows)
    (first,) = _probe(fixtures_dir, ["Sales_Regions.xlsx"], settings=SourceSettings(sheets="first"))
    assert first.sheet == "North"
    rows = _probe(fixtures_dir, ["Sales_Regions.xlsx"],
                  settings=SourceSettings(sheets="name", sheet_names=["south", "Archive", "East"]))
    assert [(r.sheet, r.status, r.message) for r in rows] == [
        ("Archive", P.ERROR, "Sheet Archive is hidden, so it isn't read."), ("East", P.ERROR, "Sheet East not found."),
        ("South", P.READY, "")]


@spec("C3-08", "IN-4")
def test_csv_encoding_and_delimiter(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Conversion_1252.csv"], settings=SourceSettings(), columns=tpl_c_columns())
    assert (row.encoding, row.delimiter, row.header_row, row.rows_approx) == ("cp1252", ";", 1, 3)
    assert row.headers == ["Case", "Amount", "Amount0", "Doc Date", "Due Date", "Code"]
    (utf8,) = _probe(fixtures_dir, ["Conversion_Values.csv"], settings=SourceSettings(), columns=tpl_c_columns())
    assert (utf8.encoding, utf8.delimiter, utf8.rows_approx, utf8.headers_match) == ("utf-8", ",", 13, True)
    (forced,) = _probe(fixtures_dir, ["Conversion_1252.csv"], columns=tpl_c_columns(),
                       settings=SourceSettings(csv_encoding="cp1252", csv_delimiter=","))
    assert forced.delimiter == ","                              # the template's setting overrides detection


def test_renamed_headers_need_mapping(fixtures_dir):
    (row,) = _probe(fixtures_dir, ["Sales_Renamed_Headers.xlsx"])
    assert row.status == P.READY and row.header_row == 1 and row.headers_match is False


def test_content_decides_the_type(tmp_path, fixtures_dir):
    fake = tmp_path / "Report.xlsx"
    fake.write_text("a,b\n1,2\n", encoding="utf-8")
    shutil.copyfile(fixtures_dir / "Sales_Oct.xlsx", tmp_path / "Sales.csv")
    shutil.copyfile(fixtures_dir / "Sales_Old.xls", tmp_path / "Old.xlsx")
    shutil.copyfile(fixtures_dir / "Sales_Nov.xlsb", tmp_path / "Nov.xlsx")
    rows = _probe(tmp_path, ["Report.xlsx", "Sales.csv", "Old.xlsx", "Nov.xlsx"])
    assert (rows[0].status, rows[0].message) == (P.ERROR, "Report.xlsx isn't a valid Excel workbook.")
    assert (rows[1].status, rows[1].sheet, rows[1].rows_approx) == (P.READY, "Sales", 5000)
    assert (rows[2].status, rows[2].kind, rows[2].rows_approx) == (P.READY, "xls", 100)
    assert (rows[3].status, rows[3].kind, rows[3].hidden_rows) == (P.READY, "xlsb", 25)


def test_missing_file(tmp_path):
    (row,) = _probe(tmp_path, ["Gone.xlsx"])
    assert (row.status, row.problem) == (P.ERROR, "missing")


@spec("T5")
def test_probe_in_worker_processes(fixtures_dir):
    """The probe runs in spawned reader workers and gives the same rows."""
    names = ["Sales_Oct.xlsx", "Sales_Protected.xlsx", "Sales_Nov.xlsx", "Conversion_Values.csv", "Sales_Nov.xls",
             "Sales_Nov.xlsb", "Sales_Protected.xls"]
    inline = _probe(fixtures_dir, names, workers=0)
    spawned = _probe(fixtures_dir, names, workers=2)
    assert [r.__dict__ for r in spawned] == [r.__dict__ for r in inline]


def test_source_files_unchanged(fixtures_dir):
    """SEC-2: probing never writes to a source file."""
    path = fixtures_dir / "Sales_Nov.xlsx"
    before = (path.stat().st_mtime_ns, path.read_bytes())
    _probe(fixtures_dir, ["Sales_Nov.xlsx"])
    assert (path.stat().st_mtime_ns, path.read_bytes()) == before
