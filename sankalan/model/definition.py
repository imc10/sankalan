"""Analysis and default-output definitions (ANA-1, ANA-4 to ANA-7, DO-1, DO-3, V3-2, T23).

A definition is structured JSON, compiled to SQL by ``sankalan.query.compiler``::

    {"template_id": "...",
     "filters":  [{"column_id": "c002", "op": "month", "values": [2026, 10]}],
     "groups":   [{"column_id": "c002", "grain": "month"}, {"column_id": "c007"}],
     "measures": [{"column_id": "c006", "fn": "sum", "label": "Taxable"}, {"column_id": null, "fn": "count"}],
     "subtotals": true}

Runs are never part of a definition (D33). Columns are referenced by stable ID, so a rename never breaks one.

Filter operators by column type (ANA-4, DO-3):

======== =========================================================================================================
Date     ``year`` [Y] · ``quarter`` [Y, Q] · ``month`` [Y, M] · ``between`` [from, to] (ISO, inclusive, either may
         be null) · ``blank`` · ``not_blank`` · relative (default outputs only): ``latest_month``,
         ``latest_quarter``, ``latest_year``
Text     ``one_of`` [values] (exact) · ``contains`` [text] (ignores case, T23) · ``blank`` · ``not_blank``
Number   ``equals`` [x] · ``between`` [min, max] (either may be null), both at the column's decimal places ·
         ``blank`` · ``not_blank``
======== =========================================================================================================

Numbers in filter values are kept as text so JSON never turns them into binary floats.

Measures: ``sum`` and ``avg`` (Number), ``min`` and ``max`` (Number, Date), ``count`` (non-blank values; with no
column, rows), ``count_distinct`` (any column).
"""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from sankalan.model.template import DATE, NUMBER, TEXT, Column

# filter operators
YEAR, QUARTER, MONTH, BETWEEN, BLANK, NOT_BLANK = "year", "quarter", "month", "between", "blank", "not_blank"
LATEST_MONTH, LATEST_QUARTER, LATEST_YEAR = "latest_month", "latest_quarter", "latest_year"
ONE_OF, CONTAINS, EQUALS = "one_of", "contains", "equals"
RELATIVE = (LATEST_MONTH, LATEST_QUARTER, LATEST_YEAR)
FILTER_OPS = {
    DATE: (YEAR, QUARTER, MONTH, BETWEEN, BLANK, NOT_BLANK) + RELATIVE,
    TEXT: (ONE_OF, CONTAINS, BLANK, NOT_BLANK),
    NUMBER: (EQUALS, BETWEEN, BLANK, NOT_BLANK),
}
# Default outputs: date filters are relative only (DO-3, C3-19); Blank / Not blank stay available.
OUTPUT_DATE_OPS = RELATIVE + (BLANK, NOT_BLANK)

# date grains (ANA-5): calendar year
DAY, GRAINS = "day", ("day", "month", "quarter", "year")

# measures (ANA-6)
SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX = "sum", "count", "count_distinct", "avg", "min", "max"
MEASURE_FNS = (SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX)
FN_NAMES = {SUM: "Sum", COUNT: "Count", COUNT_DISTINCT: "Count distinct", AVG: "Average", MIN: "Min", MAX: "Max"}
MEASURE_TYPES = {SUM: (NUMBER,), AVG: (NUMBER,), MIN: (NUMBER, DATE), MAX: (NUMBER, DATE),
                 COUNT: (TEXT, NUMBER, DATE), COUNT_DISTINCT: (TEXT, NUMBER, DATE)}

REMOVED_SUFFIX = " (removed)"
NULL_LABEL = "(Null)"
NO_DATES_NOTE = "No dates in this run"
TOTAL_LABEL = "Grand total"
SUBTOTAL_LABEL = "Total"


class DefinitionError(ValueError):
    """A definition that can't be compiled; the message is plain enough to show."""


@dataclass
class Filter:
    column_id: str
    op: str
    values: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"column_id": self.column_id, "op": self.op, "values": copy.deepcopy(self.values)}


@dataclass
class Group:
    column_id: str
    grain: str | None = None        # Date columns: day (default), month, quarter, year

    def to_dict(self) -> dict:
        return {"column_id": self.column_id, "grain": self.grain}


@dataclass
class Measure:
    column_id: str | None           # None: Count of rows
    fn: str
    label: str | None = None        # the user's name for it (ANA-6); None = the default

    def to_dict(self) -> dict:
        return {"column_id": self.column_id, "fn": self.fn, "label": self.label}


@dataclass
class Definition:
    template_id: str = ""
    filters: list[Filter] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    subtotals: bool = False

    def to_dict(self) -> dict:
        return {"template_id": self.template_id, "filters": [f.to_dict() for f in self.filters],
                "groups": [g.to_dict() for g in self.groups], "measures": [m.to_dict() for m in self.measures],
                "subtotals": bool(self.subtotals)}

    @classmethod
    def from_dict(cls, d: dict) -> "Definition":
        return cls(d.get("template_id", ""),
                   [Filter(f["column_id"], f["op"], copy.deepcopy(f.get("values") or [])) for f in d.get("filters", [])],
                   [Group(g["column_id"], g.get("grain")) for g in d.get("groups", [])],
                   [Measure(m.get("column_id"), m["fn"], m.get("label")) for m in d.get("measures", [])],
                   bool(d.get("subtotals", False)))

    @property
    def has_relative_filter(self) -> bool:
        return any(f.op in RELATIVE for f in self.filters)


# ---------------------------------------------------------------------------------------------- names
def column_label(col: Column) -> str:
    """A column's name as a result header: "(removed)" added for a removed column (T23)."""
    return col.name + (REMOVED_SUFFIX if col.removed else "")


def group_label(group: Group, col: Column) -> str:
    return column_label(col)


def measure_label(measure: Measure, columns: dict[str, Column]) -> str:
    """The measure's header: the user's name, else "Sum of Taxable Value", "Count of rows", ..."""
    if measure.label:
        return measure.label
    if measure.column_id is None:
        return "Count of rows"
    col = columns.get(measure.column_id)
    name = column_label(col) if col is not None else measure.column_id
    return f"{FN_NAMES[measure.fn]} of {name}"


# ---------------------------------------------------------------------------------------------- checks
def parse_number(text) -> Decimal:
    try:
        d = Decimal(str(text).strip())
    except InvalidOperation:
        raise DefinitionError(f"{text!r} is not a number") from None
    if not d.is_finite():
        raise DefinitionError(f"{text!r} is not a number")
    return d


def parse_date(text) -> dt.date:
    if isinstance(text, dt.date):
        return text
    try:
        return dt.date.fromisoformat(str(text))
    except ValueError:
        raise DefinitionError(f"{text!r} is not a date") from None


def check(definition: Definition, columns: list[Column], *, output: bool = False) -> None:
    """Raise ``DefinitionError`` if the definition doesn't fit the template's columns. ``output``: a default
    output, whose date filters must be relative (DO-3)."""
    by_id = {c.id: c for c in columns}

    def col(cid) -> Column:
        if cid not in by_id:
            raise DefinitionError(f"unknown column {cid!r}")
        return by_id[cid]

    for f in definition.filters:
        c = col(f.column_id)
        if f.op not in FILTER_OPS[c.type]:
            raise DefinitionError(f"{f.op!r} is not a filter for a {c.type} column ({c.name})")
        if output and c.type == DATE and f.op not in OUTPUT_DATE_OPS:
            raise DefinitionError("Default outputs can only filter dates relative to the run (latest month, "
                                  "quarter or year)")
        if not output and f.op in RELATIVE:
            raise DefinitionError("Latest month, quarter or year is for default outputs only")
        v = f.values
        if f.op == YEAR:
            _ints(v, 1)
        elif f.op == QUARTER:
            if not (len(_ints(v, 2)) == 2 and 1 <= int(v[1]) <= 4):
                raise DefinitionError("quarter must be 1 to 4")
        elif f.op == MONTH:
            if not 1 <= int(_ints(v, 2)[1]) <= 12:
                raise DefinitionError("month must be 1 to 12")
        elif f.op == BETWEEN:
            if len(v) != 2 or (v[0] in (None, "") and v[1] in (None, "")):
                raise DefinitionError("Between needs a from or to value")
            parse = parse_date if c.type == DATE else parse_number
            for x in v:
                if x not in (None, ""):
                    parse(x)
        elif f.op == EQUALS:
            if len(v) != 1:
                raise DefinitionError("Equals needs one value")
            parse_number(v[0])
        elif f.op == ONE_OF:
            if not v:
                raise DefinitionError("Is one of needs at least one value")
        elif f.op == CONTAINS:
            if len(v) != 1 or str(v[0]) == "":
                raise DefinitionError("Contains needs some text")
    for g in definition.groups:
        c = col(g.column_id)
        if g.grain is not None and (c.type != DATE or g.grain not in GRAINS):
            raise DefinitionError(f"{g.grain!r} is not a grain for {c.name}")
    if not definition.measures:
        raise DefinitionError("Add at least one measure")
    for m in definition.measures:
        if m.fn not in MEASURE_FNS:
            raise DefinitionError(f"unknown measure {m.fn!r}")
        if m.column_id is None:
            if m.fn != COUNT:
                raise DefinitionError(f"{FN_NAMES[m.fn]} needs a column")
            continue
        c = col(m.column_id)
        if c.type not in MEASURE_TYPES[m.fn]:
            raise DefinitionError(f"{FN_NAMES[m.fn]} can't be used on {c.type} column {c.name}")


def _ints(values: list, n: int) -> list:
    if len(values) != n:
        raise DefinitionError("wrong number of values")
    try:
        return [int(x) for x in values]
    except (TypeError, ValueError):
        raise DefinitionError("expected whole numbers") from None
