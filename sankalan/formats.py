"""Numbers and dates as shown on screen (UI-7): international grouping and DD-MM-YYYY, whatever the Windows region.

Date groups use calendar periods (ANA-5): day ``01-10-2026``, month ``Oct-2026``, quarter ``Q4-2026``, year
``2026``. CSV exports use the same group labels; their numbers have no grouping (EXP-3).
"""
from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def number(value, decimals: int | None = None) -> str:
    """``9812345`` → ``9,812,345``; a Decimal keeps its own decimal places unless ``decimals`` is given."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        if decimals is not None:
            value = value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)   # half away (T13)
        places = max(0, -value.as_tuple().exponent)
        return f"{value:,.{places}f}"
    return f"{int(value):,}"


def date(value: dt.date | None) -> str:
    return "" if value is None else value.strftime("%d-%m-%Y")


def period(value: dt.date | None, grain: str | None) -> str:
    """A date group's label at its grain."""
    if value is None:
        return ""
    if grain in (None, "day"):
        return date(value)
    if grain == "month":
        return f"{MONTHS[value.month - 1]}-{value.year}"
    if grain == "quarter":
        return f"Q{(value.month - 1) // 3 + 1}-{value.year}"
    if grain == "year":
        return str(value.year)
    raise ValueError(grain)
