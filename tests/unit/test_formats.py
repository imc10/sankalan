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
