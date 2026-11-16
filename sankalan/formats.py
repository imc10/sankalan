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


def date_time(value: dt.datetime | None) -> str:
    """``16-11-2026 14:32`` (Loaded on, Last loaded on)."""
    return "" if value is None else value.strftime("%d-%m-%Y %H:%M")


def elapsed(seconds: float | None) -> str:
    """``0:42``, ``12:05``, ``1:02:09``: minutes:seconds, with hours once past an hour."""
    if seconds is None:
        return ""
    s = max(0, int(seconds))
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def size(num_bytes: int | None) -> str:
    """Disk sizes for the storage footer: ``41.6 GB``, ``812 MB``, ``4 KB`` (1 GB = 1024³ bytes, as Explorer)."""
    if num_bytes is None:
        return ""
    for unit, power in (("TB", 4), ("GB", 3), ("MB", 2), ("KB", 1)):
        scale = 1024 ** power
        if num_bytes >= scale:
            v = num_bytes / scale
            return f"{v:,.1f} {unit}" if v < 100 else f"{v:,.0f} {unit}"
    return f"{num_bytes:,} bytes"


def gigabytes(num_bytes: int | None) -> str:
    """Storage footer and C4 summary (UX-1): ``41.6 GB``, ``112 GB``, ``0 GB`` (1 GB = 1024³ bytes, as Explorer;
    to 0.1 GB, C1-09)."""
    if num_bytes is None:
        return ""
    v = num_bytes / 1024 ** 3
    if v < 0.05:
        return "0 GB"
    return f"{v:,.1f} GB" if v < 100 else f"{v:,.0f} GB"


def count(n: int, one: str, many: str | None = None) -> str:
    """``1 template``, ``13 templates``, ``241,334,120 rows``."""
    return f"{number(int(n))} {one if int(n) == 1 else (many or one + 's')}"
