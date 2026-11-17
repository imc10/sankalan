"""What each rule means (T16, T17; Tech spec, Validation and issues → Rule meanings).

This module checks a rule's settings against its column, turns a character pattern into a regular expression,
and words the problem each failure reports. ``sankalan/query/validate.py`` turns the rules into SQL.

Blank means empty or only spaces (T14), which is null in ``data.parquet``. A blank cell can only fail Not blank;
every other rule skips it. A value that failed conversion is stored null but is not blank: in a run it fails only
Is a number / Is a date. On a committed run (Test rules on latest run) the original text is gone, so it counts as
blank there.
"""
from __future__ import annotations

import string
from datetime import date
from decimal import Decimal, InvalidOperation

from sankalan.model.rule import (ALLOWED_VALUES, DATE_RANGE, IS_DATE, IS_NUMBER, NOT_BLANK, NUMBER_RANGE, PATTERN,
                                 TEXT_LENGTH, UNIQUE, Rule)
from sankalan.model.template import DATE, DECIMALS_MAX, NUMBER, TEXT, TYPES, Column

# Column types each rule can be attached to (Tech spec rule table).
ALLOWED_ON = {
    NOT_BLANK: TYPES, IS_NUMBER: (NUMBER,), NUMBER_RANGE: (NUMBER,), IS_DATE: (DATE,), DATE_RANGE: (DATE,),
    ALLOWED_VALUES: (TEXT, NUMBER), TEXT_LENGTH: (TEXT,), PATTERN: (TEXT,), UNIQUE: TYPES,
}


class RuleError(ValueError):
    """A rule's settings don't fit its column. ``str(e)`` is a plain-language message for the rule editor."""


def rules_for_type(column_type: str) -> list[str]:
    """Rule types the user can add to a column of this type (the automatic type rules are not offered)."""
    return [t for t, on in ALLOWED_ON.items() if column_type in on and t not in (IS_NUMBER, IS_DATE)]


# ---------------------------------------------------------------------------------------------- settings
def parse_number(text) -> Decimal:
    """A number in rule settings: plain decimal text (``-12.5``), at most 6 decimals."""
    try:
        d = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        raise RuleError(f"{text} is not a number.") from None
    if not d.is_finite():
        raise RuleError(f"{text} is not a number.")
    if -d.as_tuple().exponent > DECIMALS_MAX:
        raise RuleError(f"{text} has more than {DECIMALS_MAX} decimal places.")
    return d


def parse_date(text) -> date:
    try:
        return date.fromisoformat(str(text))
    except ValueError:
        raise RuleError(f"{text} is not a date.") from None


def _count(v, what: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise RuleError(f"{what} must be a whole number, 0 or more.")
    return v


def check_rule(rule: Rule, columns: list[Column]) -> None:
    """Raise ``RuleError`` when the rule can't be used on its column as set."""
    by_id = {c.id: c for c in columns}
    col = by_id.get(rule.column_id)
    if col is None or col.removed:
        raise RuleError("The rule's column is not in the template.")
    if col.type not in ALLOWED_ON[rule.type]:
        raise RuleError(f"{rule.name} can't be used on a {col.type} column.")
    s = rule.settings
    if rule.type == NUMBER_RANGE:
        if s.get("not_negative"):
            return
        lo = parse_number(s["min"]) if s.get("min") not in (None, "") else None
        hi = parse_number(s["max"]) if s.get("max") not in (None, "") else None
        if lo is None and hi is None:
            raise RuleError("Number range needs a minimum, a maximum, or Not negative.")
        if lo is not None and hi is not None and lo > hi:
            raise RuleError("The minimum is more than the maximum.")
    elif rule.type == DATE_RANGE:
        lo = parse_date(s["from"]) if s.get("from") else None
        hi = parse_date(s["to"]) if s.get("to") else None
        if lo is None and hi is None:
            raise RuleError("Date range needs a from date, a to date, or both.")
        if lo is not None and hi is not None and lo > hi:
            raise RuleError("The from date is after the to date.")
    elif rule.type == ALLOWED_VALUES:
        values = list(s.get("values") or [])
        if not values:
            raise RuleError("Allowed values needs at least one value.")
        if col.type == NUMBER:
            for v in values:
                parse_number(v)
        elif any(not isinstance(v, str) or v.strip(" ") == "" for v in values):
            raise RuleError("An allowed value can't be blank.")
    elif rule.type == TEXT_LENGTH:
        if s.get("exact") is not None:
            _count(s["exact"], "The length")
        else:
            lo = _count(s["min"], "The minimum") if s.get("min") is not None else None
            hi = _count(s["max"], "The maximum") if s.get("max") is not None else None
            if lo is None and hi is None:
                raise RuleError("Text length needs an exact, minimum or maximum length.")
            if lo is not None and hi is not None and lo > hi:
                raise RuleError("The minimum is more than the maximum.")
    elif rule.type == PATTERN:
        if not isinstance(s.get("pattern"), str) or s["pattern"] == "":
            raise RuleError("Character pattern needs a pattern, e.g. AAAAA9999A.")
    elif rule.type == UNIQUE:
        for cid in rule.key_columns:
            if cid not in by_id or by_id[cid].removed:
                raise RuleError("A key column is not in the template.")


# ---------------------------------------------------------------------------------------------- pattern
def pattern_regex(pattern: str) -> str:
    """VAL-8 as a full-match regular expression (RE2): ``A`` = a letter A-Z of either case, ``9`` = a digit, any
    other character matches itself exactly, so the value has the pattern's length."""
    out = []
    for ch in pattern:
        if ch == "A":
            out.append("[A-Za-z]")
        elif ch == "9":
            out.append("[0-9]")
        elif ch in string.punctuation:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------------------------- wording (UI-6)
def fmt_number(d: Decimal) -> str:
    """International grouping (UI-7): 9,812,345.5."""
    return f"{d:,}"


def fmt_date(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def problem(rule: Rule) -> str:
    """The fixed part of a failure's message: "value is not a number". Text length and Unique within the run add
    the value's own figures (``sankalan/query/validate.py``)."""
    s = rule.settings
    if rule.type == NOT_BLANK:
        return "value is blank"
    if rule.type == IS_NUMBER:
        return "value is not a number"
    if rule.type == IS_DATE:
        return "value is not a date"
    if rule.type == NUMBER_RANGE:
        if s.get("not_negative"):
            return "value is negative"
        lo = parse_number(s["min"]) if s.get("min") not in (None, "") else None
        hi = parse_number(s["max"]) if s.get("max") not in (None, "") else None
        if lo is not None and hi is not None:
            return f"value is not between {fmt_number(lo)} and {fmt_number(hi)}"
        return f"value is less than {fmt_number(lo)}" if lo is not None else f"value is more than {fmt_number(hi)}"
    if rule.type == DATE_RANGE:
        lo = parse_date(s["from"]) if s.get("from") else None
        hi = parse_date(s["to"]) if s.get("to") else None
        if lo is not None and hi is not None:
            return f"date is not between {fmt_date(lo)} and {fmt_date(hi)}"
        return f"date is before {fmt_date(lo)}" if lo is not None else f"date is after {fmt_date(hi)}"
    if rule.type == ALLOWED_VALUES:
        return "value is not one of the allowed values"
    if rule.type == PATTERN:
        return f"value doesn't match the pattern {s['pattern']}"
    if rule.type == TEXT_LENGTH:
        if s.get("exact") is not None:
            return f"exactly {s['exact']}"
        if s.get("min") is not None and s.get("max") is not None:
            return f"{s['min']} to {s['max']}"
        return f"at least {s['min']}" if s.get("min") is not None else f"at most {s['max']}"
    if rule.type == UNIQUE:
        return "duplicate"
    raise AssertionError(rule.type)


def describe(rule: Rule, columns: list[Column]) -> str:
    """One line for the rule list and the run summary's rule changes (RUN-12): "Allowed values (GST Rate): 0, 5,
    12, 18, 28 · Error"."""
    names = {c.id: c.name for c in columns}
    s = rule.settings
    detail = ""
    if rule.type == NUMBER_RANGE:
        if s.get("not_negative"):
            detail = "not negative"
        else:
            lo = fmt_number(parse_number(s["min"])) if s.get("min") not in (None, "") else None
            hi = fmt_number(parse_number(s["max"])) if s.get("max") not in (None, "") else None
            detail = f"{lo} to {hi}" if lo and hi else f"at least {lo}" if lo else f"at most {hi}"
    elif rule.type == DATE_RANGE:
        lo = fmt_date(parse_date(s["from"])) if s.get("from") else None
        hi = fmt_date(parse_date(s["to"])) if s.get("to") else None
        detail = f"{lo} to {hi}" if lo and hi else f"from {lo}" if lo else f"to {hi}"
    elif rule.type == ALLOWED_VALUES:
        detail = ", ".join(str(v) for v in s.get("values") or [])
    elif rule.type == TEXT_LENGTH:
        detail = problem(rule)
    elif rule.type == PATTERN:
        detail = s["pattern"]
    elif rule.type == UNIQUE and len(rule.key_columns) > 1:
        detail = " + ".join(names.get(c, c) for c in rule.key_columns)
    head = f"{rule.name} ({names.get(rule.column_id, rule.column_id)})"
    return f"{head}: {detail} · {rule.severity}" if detail else f"{head} · {rule.severity}"
