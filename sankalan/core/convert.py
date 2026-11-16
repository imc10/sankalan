"""Column type conversion (MAP-9, MAP-10).

Each function returns (value, ok). When ok is False the original value is kept so nothing is lost,
and validation reports it.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

TEXT, NUMBER, DATE = "text", "number", "date"
TYPES = (TEXT, NUMBER, DATE)

_CURRENCY = re.compile(r"(₹|rs\.?|inr)", re.I)
_EXCEL_EPOCH = datetime(1899, 12, 30)


def to_text(v):
    if v is None:
        return None, True
    if isinstance(v, bool):
        return ("TRUE" if v else "FALSE"), True
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v)), True
        return repr(v), True
    if isinstance(v, int):
        return str(v), True
    if isinstance(v, datetime):
        return v.strftime("%d-%m-%Y") if v.time() == datetime.min.time() else v.strftime("%d-%m-%Y %H:%M:%S"), True
    if isinstance(v, date):
        return v.strftime("%d-%m-%Y"), True
    s = str(v).strip()
    return (s if s else None), True


def to_number(v):
    """Reads 1,23,456.00 / ₹ 500 / Rs. 500 / (1,234) / -1234 / 12%."""
    if v is None:
        return None, True
    if isinstance(v, bool):
        return v, False
    if isinstance(v, (int, float)):
        return float(v), True
    if isinstance(v, (date, datetime)):
        return v, False
    s = str(v).strip()
    if s == "":
        return None, True
    t = _CURRENCY.sub("", s).replace(",", "").replace(" ", "").replace(" ", "")
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1]
    if t.endswith("-") and not t.startswith("-"):
        neg, t = True, t[:-1]
    pct = t.endswith("%")
    if pct:
        t = t[:-1]
    try:
        n = float(t)
    except ValueError:
        return v, False
    if n != n or n in (float("inf"), float("-inf")):   # 'nan', 'inf' are not amounts
        return v, False
    if pct:
        n /= 100.0
    return (-n if neg else n), True


_DMY = ["%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%d.%m.%y"]
_MDY = ["%m-%d-%Y", "%m/%d/%Y", "%m.%d.%Y", "%m-%d-%y", "%m/%d/%y", "%m.%d.%y"]
_COMMON = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y", "%d-%b-%y",
           "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%d-%B-%Y"]


def to_date(v, order: str = "DMY"):
    if v is None:
        return None, True
    if isinstance(v, datetime):
        return v.date(), True
    if isinstance(v, date):
        return v, True
    if isinstance(v, bool):
        return v, False
    if isinstance(v, (int, float)):
        if 1 <= v < 2958466:  # Excel serial date
            return (_EXCEL_EPOCH + timedelta(days=float(v))).date(), True
        return v, False
    s = str(v).strip()
    if s == "":
        return None, True
    s2 = s.split("T")[0] if re.match(r"^\d{4}-\d{2}-\d{2}T", s) else s
    fmts = (_DMY if order == "DMY" else _MDY) + _COMMON
    for f in fmts:
        try:
            return datetime.strptime(s2, f).date(), True
        except ValueError:
            continue
    return v, False


def convert(v, col_type: str, date_order: str = "DMY"):
    if col_type == NUMBER:
        return to_number(v)
    if col_type == DATE:
        return to_date(v, date_order)
    return to_text(v)


def guess_type(values) -> str:
    """Used when a new template is built from a sample file."""
    vals = [v for v in values if v is not None and str(v).strip() != ""][:500]
    if not vals:
        return TEXT
    if sum(isinstance(v, (date, datetime)) for v in vals) >= 0.9 * len(vals):
        return DATE
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return NUMBER
    if all(isinstance(v, str) for v in vals):
        if sum(to_date(v)[1] and not isinstance(to_date(v)[0], str) for v in vals) >= 0.9 * len(vals) \
                and any(re.search(r"[-/.]", v) for v in vals):
            return DATE
        # amounts kept as text (CSV, '1,23,456.00', '₹ 500'); codes with leading zeros stay text
        if not any(re.match(r"^0\d", v.strip()) for v in vals) \
                and sum(to_number(v)[1] for v in vals) >= 0.9 * len(vals) \
                and any(re.search(r"[.,₹]|^\(|rs", v.strip().lower()) for v in vals):
            return NUMBER
    return TEXT
