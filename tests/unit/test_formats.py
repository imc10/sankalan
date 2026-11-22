"""Screen formats (UI-7) and period labels (ANA-5)."""
import datetime as dt
from decimal import Decimal

from conftest import spec
from sankalan import formats


@spec("UI-7", "GEN-04")
def test_numbers_and_dates():
    assert formats.number(9812345) == "9,812,345"
    assert formats.number(Decimal("7536875.00")) == "7,536,875.00"
    assert formats.number(Decimal("-1507.385"), 2) == "-1,507.39"         # half away from zero
    assert formats.number(Decimal("12")) == "12" and formats.number(None) == ""
    assert formats.date(dt.date(2026, 10, 1)) == "01-10-2026"


@spec("ANA-5")
def test_period_labels():
    x = dt.date(2026, 11, 1)
    assert [formats.period(x, g) for g in (None, "day", "month", "quarter", "year")] == [
        "01-11-2026", "01-11-2026", "Nov-2026", "Q4-2026", "2026"]


@spec("TXT-2", "TXT-3", "UI-7")
def test_cell_text_value_or_text():
    from sankalan.model.template import Column
    num = Column("c006", "Taxable Value", "Number", decimals=2)
    date = Column("c002", "Invoice Date", "Date")
    text = Column("c001", "Invoice No")
    assert formats.cell_text(num, Decimal("9812345.5"), None) == "9,812,345.50"
    assert formats.cell_text(num, None, "12,000/-") == "12,000/-"
    assert formats.cell_text(num, None, "  NA ") == "  NA "
    assert formats.cell_text(num, None, None) == ""
    assert formats.cell_text(date, dt.date(2026, 11, 5), None) == "05-11-2026"
    assert formats.cell_text(date, None, "31-02-2026") == "31-02-2026"
    assert formats.cell_text(text, "INV-1", None) == "INV-1"
    assert formats.right_aligned(num) and not formats.right_aligned(date) and not formats.right_aligned(text)
