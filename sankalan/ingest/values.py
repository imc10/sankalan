"""Conversion rules for Text, Number and Date columns (MAP-9, MAP-10, T13, T14), as a Python oracle.

The SQL in ``sankalan/query/convert.py`` is authoritative: it converts every run. These functions apply the same
rules to one staged-text value, for tests (the two are checked against each other) and for type guessing in the
new-template wizard. Both read the patterns defined here.

Number (decision confirmed 16-11-2026, spike S5): spaces, ``₹``, ``Rs.``/``Rs``/``INR`` (any case) and ``,``
grouping (Indian or international) are removed; ``(1,234)`` and a leading minus mean negative. Not accepted, so
reported as "not a number": exponent form (``1e3``), percentages (``12%``), a trailing minus (``500-``) and a
leading plus. Rounded half away from zero to the column's decimal places (T13).

Date: ISO ``YYYY-MM-DD`` (how Excel dates are staged) is always read; text dates in the column's format
(``DD-MM-YYYY`` or ``DD/MM/YYYY``); a time of day after the date is dropped.

Text: kept exactly as typed. Blank (empty or only spaces, T14) → null in every type, never an issue.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Context, Decimal, InvalidOperation

MAX_DIGITS = 38
_CTX = Context(prec=80, rounding=ROUND_HALF_UP)     # wide enough for any value before the width check

# Applied to the value with every space (U+0020) and no-break space (U+00A0) removed, lower-cased.
# Groups: currency before, open bracket, minus, currency after, minus, the number, close bracket.
_CUR = r"(₹|rs\.?|inr)?"
NUMBER_PATTERN = (r"^" + _CUR + r"(\()?(-)?" + _CUR + r"(-)?([0-9]+(?:,[0-9]+)*(?:\.[0-9]*)?|\.[0-9]+)(\))?$")
NUMBER_GROUPS = ("cur1", "open", "s1", "cur2", "s2", "num", "close")
NUMBER_SPACES = "  "         # space and no-break space

# Date: the date part, with an optional time of day after a space or T.
DATE_PART_PATTERN = r"^(\S+?)(?:[ T][0-9]{1,2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?)?$"
ISO_PATTERN = r"^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$"
DATE_TEXT_FORMATS = {
    "DD-MM-YYYY": (r"^[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}$", "%d-%m-%Y"),
    "DD/MM/YYYY": (r"^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$", "%d/%m/%Y"),
}

_NUM_RE = re.compile(NUMBER_PATTERN)
_DATE_PART_RE = re.compile(DATE_PART_PATTERN)
_ISO_RE = re.compile(ISO_PATTERN)


def is_blank(raw: str | None) -> bool:
    return raw is None or raw.strip(" ") == ""


def to_text(raw: str | None) -> str | None:
    return None if is_blank(raw) else raw


def to_number(raw: str | None, decimals: int) -> tuple[Decimal | None, bool]:
    """(value, ok). Blank → (None, True). Not readable → (None, False): the text goes to the issue list."""
    if is_blank(raw):
        return None, True
    t = raw
    for ch in NUMBER_SPACES:
        t = t.replace(ch, "")
    m = _NUM_RE.match(t.lower())
    if not m:
        return None, False
    g = dict(zip(NUMBER_GROUPS, m.groups(default="")))
    if (g["open"] == "") != (g["close"] == ""):
        return None, False
    if sum(1 for k in ("open", "s1", "s2") if g[k]) > 1 or (g["cur1"] and g["cur2"]):
        return None, False
    try:
        value = _CTX.quantize(Decimal(g["num"].replace(",", "")), Decimal(1).scaleb(-decimals))
    except InvalidOperation:
        return None, False
    if len(value.as_tuple().digits) > MAX_DIGITS:
        return None, False
    if g["open"] or g["s1"] or g["s2"]:
        value = -value
    if value == 0:
        value = abs(value)
    return value, True


def to_date(raw: str | None, date_format: str | None) -> tuple[date | None, bool]:
    if is_blank(raw):
        return None, True
    m = _DATE_PART_RE.match(raw.strip(" "))
    if not m:
        return None, False
    d = m.group(1)
    candidates = [(_ISO_RE, "%Y-%m-%d")]
    if date_format is not None:
        pat, fmt = DATE_TEXT_FORMATS[date_format]
        candidates.append((re.compile(pat), fmt))
    for rx, fmt in candidates:
        if rx.match(d):
            try:
                return datetime.strptime(d, fmt).date(), True
            except ValueError:
                return None, False
    return None, False
