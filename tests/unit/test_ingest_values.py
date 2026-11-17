"""Conversion rules (Python oracle), staged text form and detection helpers (MAP-9, MAP-10, T13, T14, IN-4, IN-6)."""
from datetime import date, datetime, time
from decimal import Decimal

import pytest

from conftest import spec
from sankalan.ingest import detect, values
from sankalan.ingest.canonical import staged_text

# F17 Amount raw text → (2 decimals, 0 decimals) per CONV-01. None = blank; "fail" = not a number.
CONV01 = [
    ("₹1,23,456.789", "123456.79", "123457"),
    ("1,234,567.5", "1234567.50", "1234568"),
    ("(1,234)", "-1234.00", "-1234"),
    ("2.345", "2.35", "2"),
    ("-2.345", "-2.35", "-2"),
    ("2.5", "2.50", "3"),
    ("-2.5", "-2.50", "-3"),
    ("₹ 500", "500.00", "500"),
    ("  750  ", "750.00", "750"),
    ("0.005", "0.01", "0"),
    ("12abc", "fail", "fail"),
    ("", None, None),
    ("   ", None, None),
]


@spec("CONV-01", "MAP-10", "T13", "T14")
@pytest.mark.parametrize("raw,d2,d0", CONV01)
def test_number_rule_conv01(raw, d2, d0):
    for decimals, want in ((2, d2), (0, d0)):
        got, ok = values.to_number(raw, decimals)
        if want == "fail":
            assert (got, ok) == (None, False)
        elif want is None:
            assert (got, ok) == (None, True)
        else:
            assert ok and got == Decimal(want) and str(got) == want


@spec("S5")
@pytest.mark.parametrize("raw,want", [
    ("Rs. 500", "500.00"), ("Rs.1,000", "1000.00"), ("rs 50", "50.00"), ("INR 1,23,456", "123456.00"),
    ("₹(1,234)", "-1234.00"), ("(₹1,234)", "-1234.00"), ("-₹500", "-500.00"), ("₹-500", "-500.00"),
    ("1 234", "1234.00"), ("5.", "5.00"), (".5", "0.50"), ("0", "0.00"), ("-0", "0.00"),
    ("1 234", "1234.00"),
])
def test_number_forms_accepted(raw, want):
    """Spec forms plus Rs./INR (decision confirmed 16-11-2026)."""
    got, ok = values.to_number(raw, 2)
    assert ok and str(got) == want


@spec("S5")
@pytest.mark.parametrize("raw", ["1e3", "12%", "500-", "+500", "(5", "5)", "-(5)", "(-5)", "--5", "₹₹5", "₹",
                                 "1,,000", ",100", "1.2.3", "abc", "#N/A", "2026-10-01", "TRUE", "5 INR"])
def test_number_forms_refused(raw):
    assert values.to_number(raw, 2) == (None, False)


def test_number_too_wide_for_decimal38():
    assert values.to_number("1" * 37, 2) == (None, False)
    assert values.to_number("1" * 36, 2)[1]


@spec("CONV-02", "MAP-10")
@pytest.mark.parametrize("raw,fmt,want", [
    ("05-11-2026", "DD-MM-YYYY", date(2026, 11, 5)), ("31-12-2026", "DD-MM-YYYY", date(2026, 12, 31)),
    ("31-11-2026", "DD-MM-YYYY", "fail"), ("29-02-2028", "DD-MM-YYYY", date(2028, 2, 29)),
    ("29-02-2027", "DD-MM-YYYY", "fail"), ("05/11/2026", "DD/MM/YYYY", date(2026, 11, 5)),
    ("32/01/2027", "DD/MM/YYYY", "fail"), ("05/11/2026", "DD-MM-YYYY", "fail"),
    ("05-11-2026", "DD/MM/YYYY", "fail"), ("05-11-2026", None, "fail"), ("31-02-2026", None, "fail"),
    ("2026-11-05", None, date(2026, 11, 5)), ("2026-11-05", "DD-MM-YYYY", date(2026, 11, 5)),
    ("2026-11-05 14:30:00", None, date(2026, 11, 5)), ("05-11-2026 14:30", "DD-MM-YYYY", date(2026, 11, 5)),
    ("2026-11-05T14:30:00", None, date(2026, 11, 5)), (" 5-1-2026 ", "DD-MM-YYYY", date(2026, 1, 5)),
    ("", "DD-MM-YYYY", None), ("   ", None, None), ("45231", None, "fail"), ("Nov 5 2026", None, "fail"),
])
def test_date_rule(raw, fmt, want):
    got, ok = values.to_date(raw, fmt)
    if want == "fail":
        assert (got, ok) == (None, False)
    else:
        assert ok and got == want


@spec("CONV-03", "MAP-9", "T14")
def test_text_kept_exactly_as_typed():
    assert values.to_text("00123") == "00123"
    assert values.to_text(" A1 ") == " A1 "
    assert values.to_text("   ") is None
    assert values.to_text("") is None
    assert values.to_text("MIXED Case") == "MIXED Case"
    assert values.to_text("\t") == "\t"          # only spaces count as blank


@spec("T11", "S6")
def test_staged_text_form():
    assert staged_text(2.345) == "2.345"
    assert staged_text(150.0) == "150"
    assert staged_text(12345678901234567.0) == "12345678901234568"
    assert staged_text(1e-7) == "0.0000001"
    assert staged_text(1e21) == "1000000000000000000000"
    assert "e" not in staged_text(1.5e-10)
    assert staged_text(-0.5) == "-0.5"
    assert staged_text(datetime(2026, 11, 5, 14, 30)) == "2026-11-05 14:30:00"
    assert staged_text(datetime(2026, 11, 5)) == "2026-11-05"
    assert staged_text(date(2026, 11, 5)) == "2026-11-05"
    assert staged_text(time(14, 30)) == "14:30:00"
    assert staged_text(True) == "TRUE"
    assert staged_text(" A1 ") == " A1 "
    assert staged_text(None) == ""


@spec("IN-6")
def test_header_detection():
    rows = [["Acme Traders — Sales Register"], ["Sample"], ["Invoice No", "Invoice Date", "Customer"],
            ["INV-1", 45000.0, "X"]]
    assert detect.detect_header(rows) == 2
    assert detect.detect_header(rows, {"invoiceno", "customer"}) == 2
    assert detect.detect_header([[1.0, 2.0], [3.0, 4.0]]) is None          # F09: numbers only → error
    assert detect.detect_header([[1.0, 2.0]], {"amount"}) is None
    assert detect.detect_header([["Amount"], ["5"]]) == 0                  # one-column sheet
    assert detect.detect_header([]) is None


def test_make_headers():
    assert detect.make_headers(["A", None, "a", "  ", 2026.0, None, "   "]) == ["A", "Column 2", "a (2)",
                                                                              "Column 4", "2026"]


@spec("IN-4")
def test_csv_detection():
    chk = detect.Utf8Check()
    chk.feed("Café".encode("cp1252"), final=True)
    assert detect.encoding_from_check(chk) == "cp1252"
    chk = detect.Utf8Check()
    data = b"\xef\xbb\xbf" + "Café".encode("utf-8")
    chk.feed(data[:5])                  # split inside a character: still valid
    chk.feed(data[5:], final=True)
    assert detect.encoding_from_check(chk) == "utf-8-sig"
    assert detect.detect_delimiter("a;b;c\n1;2;3\n") == ";"
    assert detect.detect_delimiter("a\tb\n1\t2\n") == "\t"
    assert detect.detect_delimiter("a|b\n1|2\n") == "|"
    assert detect.detect_delimiter("a,b\n1,2\n") == ","
