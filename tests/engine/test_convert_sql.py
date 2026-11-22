"""The SQL conversion rules agree with the Python oracle on every test vector (MAP-9, MAP-10, T13, T14, S5), and keep
the text of a value that doesn't convert in its companion (Feature Spec A2 TXT-1, Tech spec A2 5.1, 5.2)."""
import random
from decimal import Decimal

import pytest

from conftest import spec
from sankalan.ingest import values
from sankalan.model.template import Column
from sankalan.query import convert

NUMBER_VECTORS = [
    "₹1,23,456.789", "1,234,567.5", "(1,234)", "2.345", "-2.345", "2.5", "-2.5", "₹ 500", "  750  ", "0.005",
    "12abc", "", "   ", None, "Rs. 500", "Rs.1,000", "rs 50", "INR 1,23,456", "₹(1,234)", "(₹1,234)", "-₹500",
    "₹-500", "1 234", "5.", ".5", "0", "-0", "1e3", "12%", "500-", "+500", "(5", "5)", "-(5)", "(-5)", "--5",
    "₹₹5", "₹", "1,,000", ",100", "1.2.3", "abc", "#N/A", "2026-10-01", "TRUE", "5 INR", "1 234",
    "0.0000005", "-0.0000005", "999999999999999999999999999999999999.994", "1" * 37, "12345678901234570",
    "150", "0.1", "-1234.565", "1,23,45,678.125", "007", "-007.50", "1" * 36, "-" + "9" * 36 + ".995",
]

DATE_VECTORS = [
    "05-11-2026", "31-12-2026", "31-11-2026", "29-02-2028", "29-02-2027", "01-01-2027", "05/11/2026",
    "31/12/2026", "32/01/2027", "15/01/2027", "2026-11-05", "2026-11-05 14:30:00", "2026-11-05T14:30:00",
    "05-11-2026 14:30", " 5-1-2026 ", "", "   ", None, "45231", "Nov 5 2026", "31-02-2026", "2026-02-30",
    "2026-1-5", "05-11-26", "abc", "2026-13-01", "0001-01-01", "9999-12-31", "2026-11-05 00:00:00",
]


def _random_numbers(n=300, seed=7):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        v = Decimal(rnd.randint(-10 ** 9, 10 ** 9)) / Decimal(10 ** rnd.randint(0, 7))
        s = f"{v:f}"
        if rnd.random() < 0.3:
            s = f"{abs(v):,f}"
            s = f"({s})" if v < 0 else s
        if rnd.random() < 0.2:
            s = "₹ " + s
        out.append(s)
    return out


def _with_text(raw, oracle):
    """(value, companion text): the text as typed when the cell isn't blank and doesn't convert, else None."""
    value, ok = oracle
    return value, (None if ok else raw)


@spec("MAP-10", "T13", "S5")
@pytest.mark.parametrize("decimals", [0, 1, 2, 3, 6])
def test_number_sql_matches_oracle(storage, decimals):
    col = Column("c001", "Amount", "Number", decimals=decimals)
    vectors = NUMBER_VECTORS + _random_numbers()
    got = convert.convert_values(storage.con, vectors, col)
    want = [_with_text(v, values.to_number(v, decimals)) for v in vectors]
    diffs = [(v, g, w) for v, g, w in zip(vectors, got, want) if g != w]
    assert diffs == []


@spec("MAP-10", "CONV-02")
@pytest.mark.parametrize("fmt", [None, "DD-MM-YYYY", "DD/MM/YYYY"])
def test_date_sql_matches_oracle(storage, fmt):
    col = Column("c001", "Doc Date", "Date", date_format=fmt)
    got = convert.convert_values(storage.con, DATE_VECTORS, col)
    want = [_with_text(v, values.to_date(v, fmt)) for v in DATE_VECTORS]
    assert list(zip(DATE_VECTORS, got)) == list(zip(DATE_VECTORS, want))


@spec("MAP-9", "T14", "CONV-03")
def test_text_sql_matches_oracle(storage):
    col = Column("c001", "Code")
    vec = ["00123", " A1 ", "   ", "", None, "MIXED Case", "\t", "Café", "a'b", "line\nbreak"]
    assert convert.convert_values(storage.con, vec, col) == [(values.to_text(v), None) for v in vec]


# ---------------------------------------------------------------------------------------------- companions (A2)
@spec("TXT-1", "T41", "T14")
def test_companion_keeps_text_exactly_as_typed(storage):
    num = Column("c001", "Amount", "Number", decimals=2)
    got = convert.convert_values(storage.con, ["  NA ", "#N/A", "12,000/-", "Nil", "1,234.50", "", "   ", None], num)
    assert got == [(None, "  NA "), (None, "#N/A"), (None, "12,000/-"), (None, "Nil"), (Decimal("1234.50"), None),
                   (None, None), (None, None), (None, None)]
    date = Column("c002", "Doc Date", "Date", date_format="DD-MM-YYYY")
    got = convert.convert_values(storage.con, ["31-02-2026", "NA", "05-11-2026", " ", "#REF!"], date)
    assert [t for _v, t in got] == ["31-02-2026", "NA", None, None, "#REF!"]
    assert all(v is None or t is None for v, t in got)               # never both filled


def _raw(path, header, rows):
    import csv as _csv
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["_src_row"] + [f"v{i}" for i in range(len(header))])
        for r in rows:
            w.writerow(r)


@spec("T32", "MAP-6", "MAP-11", "T41")
def test_write_data_sorted_with_companions_and_missing_sources(storage):
    """Three file-sheets, the second without a source for Amount (MAP-6) and none for Due Date (a column added
    later, MAP-11): both null in value and companion. data.parquet is ascending in (_src_file, _src_row) even
    though the parts are given out of order."""
    cols = [Column("c001", "Code"), Column("c002", "Amount", "Number", decimals=2),
            Column("c003", "Due Date", "Date", date_format="DD-MM-YYYY")]
    tmp_path = storage.folder.new_staging().path        # DuckDB may read only the data and temp folders
    parts = []
    for fi, (rows, mapping) in enumerate([
            ([(2, "A", "10", "NA"), (3, "B", "x1", "01-01-2027")], {"c001": 0, "c002": 1, "c003": 2}),
            ([(5, "C", "1"), (2, "D", "2")], {"c001": 0, "c002": None, "c003": None}),
            ([(9, "E", " 7 ", "")], {"c001": 0, "c002": 1, "c003": 2})]):
        raw = tmp_path / f"{fi}.csv"
        width = max(len(r) for r in rows) - 1
        _raw(raw, range(width), rows)
        parts.append(convert.RawPart(fi, f"S{fi}", raw, width, mapping))
    out = tmp_path / "data.parquet"
    convert.write_data(storage.con, [parts[2], parts[0], parts[1]], cols, "run", out)
    got = storage.con.execute(f"SELECT _src_file, _src_row, c001, c002, c002_t, c003, c003_t "
                              f"FROM read_parquet('{out.as_posix()}')").fetchall()
    from datetime import date
    assert got == [(0, 2, "A", Decimal("10.00"), None, None, "NA"),
                   (0, 3, "B", None, "x1", date(2027, 1, 1), None),
                   (1, 2, "D", None, None, None, None),
                   (1, 5, "C", None, None, None, None),
                   (2, 9, "E", Decimal("7.00"), None, None, None)]
