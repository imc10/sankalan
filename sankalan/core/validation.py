"""Validation rules (VAL-1 .. VAL-11).

Rules hang off output columns in the template; duplicate checks are template level.
Blank cells are checked only by 'not_blank'.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

ERROR, WARNING = "error", "warning"

RULES = {
    "not_blank": "Not blank",
    "gstin_format": "GSTIN format",
    "gstin_state": "GSTIN state code",
    "gstin_checksum": "GSTIN check character",
    "pan_format": "PAN format",
    "is_number": "Is a number",
    "number_range": "Number range",
    "is_date": "Is a date",
    "date_range": "Date range",
    "allowed_values": "Allowed values",
    "duplicates": "Duplicates",
}

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_check_char(first14: str) -> str:
    """GSTN check character: weights alternate 1,2; sum of quotient+remainder base 36."""
    total = 0
    for i, ch in enumerate(first14):
        prod = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return _CHARS[(36 - total % 36) % 36]


@dataclass
class Issue:
    file: str
    sheet: str
    row: int            # original row number in the source sheet
    column: str
    value: str
    rule: str           # key from RULES (or 'mapping', 'read')
    severity: str
    message: str

    def location(self) -> str:
        return f"{self.file}, {self.sheet}, row {self.row:,}"


def _fmt_value(v) -> str:
    if v is None:
        return "(blank)"
    if isinstance(v, (datetime, date)):
        return v.strftime("%d-%m-%Y")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _parse_limit_date(s):
    if isinstance(s, date):
        return s
    from .convert import to_date
    d, ok = to_date(s)
    return d if ok and isinstance(d, date) else None


def check_value(rule: dict, raw, converted, conv_ok: bool, col_type: str, exceptions=()):
    """Return a message if the rule fails for this cell, else None."""
    kind = rule["type"]
    blank = converted is None or (isinstance(converted, str) and converted.strip() == "")
    if kind == "not_blank":
        return "is blank" if blank else None
    if blank:
        return None
    if kind in ("gstin_format", "gstin_state", "gstin_checksum"):
        g = str(converted).strip().upper()
        if g in exceptions:
            return None
        if kind == "gstin_format":
            if len(g) != 15:
                return f"has {len(g)} characters; a GSTIN has 15"
            if not GSTIN_RE.match(g):
                return "doesn't follow the GSTIN pattern (state code, PAN, entity, Z, check character)"
            return None
        if not GSTIN_RE.match(g):
            return None  # format rule reports it
        if kind == "gstin_state":
            return None if g[:2] in STATE_CODES else f"state code {g[:2]} isn't valid"
        return None if gstin_check_char(g[:14]) == g[14] else \
            "last character doesn't match the GSTIN check character, so a character is likely mistyped"
    if kind == "pan_format":
        p = str(converted).strip().upper()
        return None if PAN_RE.match(p) else "isn't a valid PAN (5 letters, 4 digits, 1 letter)"
    if kind == "is_number":
        if not conv_ok or not isinstance(converted, (int, float)) or isinstance(converted, bool):
            return "isn't a number"
        return None
    if kind == "number_range":
        if not isinstance(converted, (int, float)) or isinstance(converted, bool):
            return None
        lo, hi = rule.get("min"), rule.get("max")
        if lo is not None and converted < lo:
            return "is negative" if lo == 0 else f"is below {lo:g}"
        if hi is not None and converted > hi:
            return f"is above {hi:g}"
        return None
    if kind == "is_date":
        if not conv_ok or not isinstance(converted, date):
            return "isn't a date"
        return None
    if kind == "date_range":
        if not isinstance(converted, date):
            return None
        lo = rule["_from"] if "_from" in rule else _parse_limit_date(rule.get("from"))
        hi = rule["_to"] if "_to" in rule else _parse_limit_date(rule.get("to"))
        if lo and converted < lo:
            return f"is before {lo.strftime('%d-%m-%Y')}"
        if hi and converted > hi:
            return f"is after {hi.strftime('%d-%m-%Y')}"
        return None
    if kind == "allowed_values":
        allowed = rule.get("values") or []
        if rule.get("case_sensitive"):
            ok = str(converted).strip() in allowed
        else:
            ok = str(converted).strip().lower() in {str(a).lower() for a in allowed}
        return None if ok else "isn't one of: " + ", ".join(map(str, allowed))
    return None


def run_validation(columns, rows, raws, oks, origins, dup_rules, exceptions=(), cancel=None):
    """columns: list of template column dicts (output order, mapped);
    rows: converted values; raws: original values; oks: conversion flags;
    origins: (file, sheet, row) per row. Returns list[Issue]."""
    from .readers import Cancelled
    issues = []
    exc = {e.strip().upper() for e in exceptions}
    for ci, col in enumerate(columns):
        rules = [dict(r) for r in col.get("rules", [])]
        if not rules:
            continue
        for r in rules:   # parse limits once, not per cell
            if r["type"] == "date_range":
                r["_from"], r["_to"] = _parse_limit_date(r.get("from")), _parse_limit_date(r.get("to"))
        name = col["name"]
        for ri in range(len(rows)):
            if cancel and ri % 20000 == 0 and cancel():
                raise Cancelled()
            v = rows[ri][ci]
            for rule in rules:
                msg = check_value(rule, raws[ri][ci], v, oks[ri][ci], col.get("type", "text"), exc)
                if msg:
                    f, s, r = origins[ri]
                    issues.append(Issue(f, s, r, name, _fmt_value(raws[ri][ci]), rule["type"],
                                        rule.get("severity", ERROR), f"{name} {msg}"))
    # VAL-11 duplicates on key columns, within and across files
    names = [c["name"] for c in columns]
    for d in dup_rules:
        keys = [names.index(k) for k in d.get("columns", []) if k in names]
        if not keys:
            continue
        first = {}
        for ri, row in enumerate(rows):
            key = tuple((str(row[k]).strip().upper() if row[k] is not None else None) for k in keys)
            if all(k is None for k in key):
                continue
            if key in first:
                f0, s0, r0 = origins[first[key]]
                f, s, r = origins[ri]
                where = f"row {r0:,}" if f0 == f else f"{f0}, row {r0:,}"
                label = " and ".join(names[k] for k in keys)
                issues.append(Issue(f, s, r, names[keys[-1]], _fmt_value(row[keys[-1]]), "duplicates",
                                    d.get("severity", ERROR), f"Same {label} as {where}"))
            else:
                first[key] = ri
    return issues
