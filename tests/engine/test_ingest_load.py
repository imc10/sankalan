"""Read and convert: F02, F03, F04, F16, F17, F18 and F19 stage to the right data.parquet and conversion failures
(Phase 2 exit; CONV-01 to CONV-05, RUNV-02 counts, IN-8, IN-13, T11 to T14)."""
import csv
import multiprocessing
import time
from datetime import date
from decimal import Decimal

import pytest

from conftest import run_job, spec, tpl_a_columns, tpl_a_settings, tpl_c_columns
from sankalan import mapping
from sankalan.ingest import stage
from sankalan.jobs import JobState
from sankalan.model.template import SourceSettings
from sankalan.query import convert

TPL_C_FIRST = SourceSettings(sheets="first")


def _parts(storage, fx, names, settings, columns):
    rows = run_job(storage.runner, lambda ctx: stage.probe(ctx, [str(fx / n) for n in names], settings=settings,
                                                           columns=columns))
    assert all(r.readable for r in rows), [(r.file_name, r.message) for r in rows]
    return [stage.LoadPart.from_probe(i, r, mapping.auto_map(columns, r.headers)) for i, r in enumerate(rows)]


def _load(storage, fx, names, settings, columns, workers=0):
    parts = _parts(storage, fx, names, settings, columns)
    st = storage.folder.new_staging()
    res = run_job(storage.runner, lambda ctx: stage.load(ctx, storage.folder, st, parts, columns, workers=workers))
    return st, res


def _rows(storage, res, columns):
    return convert.read_rows(storage.con, res.data, [c.id for c in columns])


def _sums(storage, res, *ids):
    return convert.column_sums(storage.con, res.data, list(ids))


@spec("R-0001", "RUNV-01")
def test_f02(storage, fixtures_dir):
    cols = tpl_a_columns()
    st, res = _load(storage, fixtures_dir, ["Sales_Oct.xlsx"], tpl_a_settings(), cols)
    assert (res.rows_loaded, res.rows_read, res.blank_rows, res.hidden_rows, res.failures) == (5000, 5000, 0, 0, {})
    assert _sums(storage, res, "c006", "c008") == {"c006": Decimal("7536875.00"), "c008": Decimal("956722.50")}
    rows = _rows(storage, res, cols)
    assert rows[0] == (0, "Sales", 2, "INV-10001", date(2026, 10, 1), "Shree Ganesh Traders", "27ABCDE0001F1Z5",
                       "Maharashtra", Decimal("1000.00"), Decimal("0"), Decimal("0.00"))
    assert rows[-1][2] == 5001
    types = {r[0]: r[1] for r in storage.con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{res.data.as_posix()}')").fetchall()}
    assert types == {"run_id": "VARCHAR", "_src_file": "INTEGER", "_src_sheet": "VARCHAR", "_src_row": "BIGINT",
                     "c001": "VARCHAR", "c002": "DATE", "c003": "VARCHAR", "c004": "VARCHAR", "c005": "VARCHAR",
                     "c006": "DECIMAL(38,2)", "c007": "DECIMAL(38,0)", "c008": "DECIMAL(38,2)"}
    assert storage.con.execute(f"SELECT DISTINCT run_id FROM read_parquet('{res.data.as_posix()}')").fetchall() \
        == [(st.id,)]
    assert (st.raw / "0.csv").is_file()                          # raw text stays until commit (T20)


@spec("RUNV-02", "IN-8", "IN-13", "T14", "R-0002")
def test_f03_hidden_and_blank_rows(storage, fixtures_dir):
    cols = tpl_a_columns()
    _st, res = _load(storage, fixtures_dir, ["Sales_Nov.xlsx"], tpl_a_settings(), cols)
    assert (res.rows_loaded, res.hidden_rows, res.blank_rows) == (4000, 25, 10)
    assert _sums(storage, res, "c006", "c008") == {"c006": Decimal("6029500.00"), "c008": Decimal("765378.00")}
    rows = _rows(storage, res, cols)
    assert rows[0][2] == 3                                       # title row 1, header row 2
    assert not any(r[3].startswith("INV-29") for r in rows)       # the hidden rows' invoices
    assert res.failures == {}


@spec("RUNV-03", "C3-16", "T20", "R-0003")
def test_f04_conversion_failures(storage, fixtures_dir):
    cols = tpl_a_columns()
    _st, res = _load(storage, fixtures_dir, ["Sales_Errors.xlsx"], tpl_a_settings(), cols)
    assert res.rows_loaded == 2000
    assert res.failures == {"c006": 15, "c002": 4}
    fails = convert.read_failures(storage.con, res.failures_file)
    taxable = [(r[2], r[4]) for r in fails if r[3] == "c006"]
    assert taxable == [(row, "abc") for row in range(214, 229)]  # sheet rows 214-228
    assert [(r[2], r[4]) for r in fails if r[3] == "c002"] == [(n + 1, "31-02-2026") for n in range(501, 505)]
    # Input side of the totals check: unreadable values count as 0 (T20)
    assert _sums(storage, res, "c006", "c008") == {"c006": Decimal("2986623.75"), "c008": Decimal("381662.10")}


@spec("RUNF-13", "IN-5", "C3-07")
def test_f16_two_sheets_in_workers(storage, fixtures_dir):
    cols = tpl_a_columns()
    _st, res = _load(storage, fixtures_dir, ["Sales_Regions.xlsx"], SourceSettings(sheets="all"), cols, workers=2)
    assert [(p.file_index, p.rows) for p in res.parts] == [(0, 1500), (1, 2500)]
    assert res.rows_loaded == 4000
    got = dict(storage.con.execute(
        f"SELECT _src_sheet, sum(c006) FROM read_parquet('{res.data.as_posix()}') GROUP BY 1").fetchall())
    assert got == {"North": Decimal("2261062.50"), "South": Decimal("3768437.50")}


CONV_EXPECTED = {   # Case: (Amount, Amount0, Doc Date, Due Date, Code)
    "C01": ("123456.79", "123457", date(2026, 11, 5), date(2026, 11, 5), "00123"),
    "C02": ("1234567.50", "1234568", date(2026, 12, 31), date(2026, 12, 31), " A1 "),
    "C03": ("-1234.00", "-1234", None, None, None),
    "C04": ("2.35", "2", date(2028, 2, 29), date(2027, 1, 15), "MIXED Case"),
    "C05": ("-2.35", "-2", None, date(2027, 1, 15), "X"),
    "C06": ("2.50", "3", date(2027, 1, 1), date(2027, 1, 15), "X"),
    "C07": ("-2.50", "-3", date(2027, 1, 1), date(2027, 1, 15), "X"),
    "C08": ("500.00", "500", date(2027, 1, 1), date(2027, 1, 15), "X"),
    "C09": ("750.00", "750", date(2027, 1, 1), date(2027, 1, 15), "X"),
    "C10": ("0.01", "0", date(2027, 1, 1), date(2027, 1, 15), "X"),
    "C11": (None, None, date(2027, 1, 1), date(2027, 1, 15), "X"),
    "C12": (None, None, date(2027, 1, 1), date(2027, 1, 15), "X"),
    "C13": (None, None, date(2027, 1, 1), date(2027, 1, 15), "X"),
}


@spec("CONV-01", "CONV-02", "CONV-03", "MAP-9", "MAP-10", "T13", "T14")
def test_f17_conversion_values(storage, fixtures_dir):
    cols = tpl_c_columns()
    _st, res = _load(storage, fixtures_dir, ["Conversion_Values.csv"], TPL_C_FIRST, cols)
    rows = {r[3]: r[4:] for r in _rows(storage, res, cols)}
    want = {k: (None if a is None else Decimal(a), None if b is None else Decimal(b), dd, du, code)
            for k, (a, b, dd, du, code) in CONV_EXPECTED.items()}
    assert rows == want
    assert str(rows["C02"][0]) == "1234567.50" and str(rows["C06"][1]) == "3"
    fails = convert.read_failures(storage.con, res.failures_file)
    assert sorted((r[2], r[3], r[4]) for r in fails) == [
        (4, "c004", "31-11-2026"), (4, "c005", "32/01/2027"), (6, "c004", "29-02-2027"),
        (12, "c002", "12abc"), (12, "c003", "12abc")]
    assert res.failures == {"c002": 1, "c003": 1, "c004": 2, "c005": 1}      # C12, C13: blank, no issue


@spec("CONV-04", "IN-4", "T12", "C3-08")
def test_f18_windows_1252(storage, fixtures_dir):
    cols = tpl_c_columns()
    st, res = _load(storage, fixtures_dir, ["Conversion_1252.csv"], TPL_C_FIRST, cols)
    rows = _rows(storage, res, cols)
    assert [(r[4], r[8]) for r in rows] == [(Decimal("1234.50"), "Café"), (Decimal("10.00"), "Müller"),
                                            (Decimal("20.00"), "Señor")]
    raw = (st.raw / "0.csv").read_bytes().decode("utf-8")       # staged as UTF-8
    assert "Café" in raw and "Señor" in raw


@spec("CONV-05", "T11", "S3", "S6")
def test_f19_formulas_errors_times(storage, fixtures_dir):
    cols = tpl_c_columns()
    st, res = _load(storage, fixtures_dir, ["Conversion_Values.xlsx"], TPL_C_FIRST, cols)
    rows = {r[3]: r[4:] for r in _rows(storage, res, cols)}
    assert rows["C01"] == (Decimal("2.35"), None, date(2026, 11, 5), None, "00123")
    assert rows["C02"][0] == Decimal("150.00")                   # last calculated value
    assert rows["C03"][0] is None
    assert convert.read_failures(storage.con, res.failures_file) == [(0, "Data", 4, "c002", "#N/A")]
    with open(st.raw / "0.csv", encoding="utf-8", newline="") as f:
        raw = list(csv.reader(f))
    assert raw[0] == ["_src_row", "v0", "v1", "v2", "v3", "v4", "v5"]
    assert raw[1] == ["2", "C01", "2.345", "", "2026-11-05 14:30:00", "", "00123"]
    assert raw[2][:2] == ["3", "C02"] and raw[2][2] == "150"
    assert raw[3][2] == "#N/A"


def test_missing_mapping_and_extra_columns(storage, fixtures_dir):
    """F08 has no State column and an extra Remarks: unmatched columns read as null (until Phase 5's decisions)."""
    cols = tpl_a_columns()
    _st, res = _load(storage, fixtures_dir, ["Sales_Renamed_Headers.xlsx"], tpl_a_settings(), cols)
    rows = _rows(storage, res, cols)
    assert res.rows_loaded == 1000 and all(r[7] is None for r in rows)          # State
    assert _sums(storage, res, "c006", "c008") == {"c006": Decimal("1507375.00"), "c008": Decimal("191344.50")}


def test_recheck_reruns_on_the_same_staging(storage, fixtures_dir):
    cols = tpl_c_columns()
    parts = _parts(storage, fixtures_dir, ["Conversion_Values.csv"], TPL_C_FIRST, cols)
    st = storage.folder.new_staging()
    first = run_job(storage.runner, lambda ctx: stage.load(ctx, storage.folder, st, parts, cols, workers=0))
    second = run_job(storage.runner, lambda ctx: stage.load(ctx, storage.folder, st, parts, cols, workers=0))
    assert (first.rows_loaded, first.failures) == (second.rows_loaded, second.failures)
    assert sorted(p.name for p in st.raw.iterdir()) == ["0.csv"]


def test_failed_load_removes_staging(storage, fixtures_dir, tmp_path):
    import shutil
    src = tmp_path / "Sales_Oct.xlsx"
    shutil.copyfile(fixtures_dir / "Sales_Oct.xlsx", src)
    cols = tpl_a_columns()
    parts = _parts(storage, tmp_path, ["Sales_Oct.xlsx"], tpl_a_settings(), cols)
    src.unlink()                                                 # gone between Files and Validate
    st = storage.folder.new_staging()
    job = storage.runner.run("load", lambda ctx: stage.load(ctx, storage.folder, st, parts, cols, workers=0))
    assert job.state is JobState.FAILED and isinstance(job.error, stage.LoadFailed)
    assert job.error.message == "Sales_Oct.xlsx was not found. It may have been moved or deleted."
    assert not st.path.exists()


@spec("UI-5", "T5")
def test_cancel_stops_workers_and_removes_staging(storage, tmp_path):
    big = tmp_path / "Big.csv"
    with open(big, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Case", "Amount", "Amount0", "Doc Date", "Due Date", "Code"])
        for i in range(400_000):
            w.writerow([f"C{i}", "1,234.50", "10", "01-01-2027", "15/01/2027", "X"])
    cols = tpl_c_columns()
    parts = _parts(storage, tmp_path, ["Big.csv"], TPL_C_FIRST, cols)
    st = storage.folder.new_staging()
    job = storage.runner.start("load", lambda ctx: stage.load(ctx, storage.folder, st, parts, cols, workers=1))
    deadline = time.monotonic() + 30
    while (job.progress().rows_done or 0) == 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert job.progress().rows_done > 0 and job.progress().rows_total == 400_000
    assert job.cancel()
    assert job.wait(15)
    assert job.state is JobState.CANCELLED
    assert not st.path.exists()
    assert multiprocessing.active_children() == []


@pytest.mark.parametrize("workers", [0, 2])
def test_same_result_inline_and_in_workers(storage, fixtures_dir, workers):
    cols = tpl_a_columns()
    _st, res = _load(storage, fixtures_dir, ["Sales_Nov.xlsx", "Sales_Errors.xlsx"], tpl_a_settings(), cols,
                     workers=workers)
    assert (res.rows_loaded, res.hidden_rows, res.blank_rows, res.failures) == (6000, 25, 10,
                                                                                {"c006": 15, "c002": 4})
