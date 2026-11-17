"""The SQL conversion rules agree with the Python oracle on every test vector (MAP-9, MAP-10, T13, T14, S5)."""
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


@spec("MAP-10", "T13", "S5")
@pytest.mark.parametrize("decimals", [0, 1, 2, 3, 6])
def test_number_sql_matches_oracle(storage, decimals):
    col = Column("c001", "Amount", "Number", decimals=decimals)
    vectors = NUMBER_VECTORS + _random_numbers()
    got = convert.convert_values(storage.con, vectors, col)
    want = [values.to_number(v, decimals)[0] for v in vectors]
    diffs = [(v, g, w) for v, g, w in zip(vectors, got, want) if g != w]
    assert diffs == []


@spec("MAP-10", "CONV-02")
@pytest.mark.parametrize("fmt", [None, "DD-MM-YYYY", "DD/MM/YYYY"])
def test_date_sql_matches_oracle(storage, fmt):
    col = Column("c001", "Doc Date", "Date", date_format=fmt)
    got = convert.convert_values(storage.con, DATE_VECTORS, col)
    want = [values.to_date(v, fmt)[0] for v in DATE_VECTORS]
    assert list(zip(DATE_VECTORS, got)) == list(zip(DATE_VECTORS, want))


@spec("MAP-9", "T14", "CONV-03")
def test_text_sql_matches_oracle(storage):
    col = Column("c001", "Code")
    vec = ["00123", " A1 ", "   ", "", None, "MIXED Case", "\t", "Café", "a'b", "line\nbreak"]
    assert convert.convert_values(storage.con, vec, col) == [values.to_text(v) for v in vec]
