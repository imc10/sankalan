"""Analysis and default-output definitions (ANA-1, ANA-4 to ANA-7, DO-1, DO-3, V3-2, T23).

A definition is structured JSON, compiled to SQL by ``sankalan.query.compiler``::

    {"definition_version": 2,
     "template_id": "...",
     "filters":  [{"column_id": "c002", "op": "month", "values": [2026, 10]}],
     "groups":   [{"column_id": "c002", "grain": "month"}, {"column_id": "c007"}],
     "measures": [{"column_id": "_rows", "ops": [{"fn": "count", "name": null}]},
                  {"column_id": "c006", "ops": [{"fn": "sum", "name": "Taxable"}, {"fn": "max", "name": null}]}],
     "subtotals": true}

Measures are cards (Feature Spec A2 3.1, Tech spec A2 T49): a column, or Rows (``ROWS``), and its ticked operations,
stored in the fixed order Sum, Count, Count distinct, Average, Min, Max (MEA-6). ``name: null`` is the default name
(MEA-7). ``measures`` may be empty when there is a group level (MEA-11). Only version 2 is read (T40).

Runs are never part of a definition (D33). Columns are referenced by stable ID, so a rename never breaks one.

Filter operators by column type (ANA-4, DO-3):

======== =========================================================================================================
Date     ``year`` [Y] · ``quarter`` [Y, Q] · ``month`` [Y, M] · ``between`` [from, to] (ISO, inclusive, either may
         be null) · ``blank`` · ``not_blank`` · ``not_date`` (holds text, TXT-7) · relative (default outputs only):
         ``latest_month``, ``latest_quarter``, ``latest_year``
Text     ``one_of`` [values] (exact) · ``contains`` [text] (ignores case, T23) · ``blank`` · ``not_blank``
Number   ``equals`` [x] · ``between`` [min, max] (either may be null), both at the column's decimal places ·
         ``blank`` · ``not_blank`` · ``not_number`` (holds text, TXT-6)

Number and Date columns keep text that doesn't convert (Feature Spec A2 TXT-1): value filters and Sum, Avg, Min, Max
use the values only; Blank means neither a value nor text; Count counts both (TXT-8). Grouping puts text in one
group, "(Not a number)" or "(Not a date)" (TXT-10).
======== =========================================================================================================

Numbers in filter values are kept as text so JSON never turns them into binary floats.

Operations by type (MEA-3, D70): Number sum, count, avg, min, max; Date count, count_distinct, min, max; Text count,
count_distinct; Rows count only.
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
NOT_NUMBER, NOT_DATE = "not_number", "not_date"            # the cell holds text (TXT-6, TXT-7, T55)
RELATIVE = (LATEST_MONTH, LATEST_QUARTER, LATEST_YEAR)
NO_VALUE_OPS = (BLANK, NOT_BLANK, NOT_NUMBER, NOT_DATE)
FILTER_OPS = {
    DATE: (YEAR, QUARTER, MONTH, BETWEEN, BLANK, NOT_BLANK, NOT_DATE) + RELATIVE,
    TEXT: (ONE_OF, CONTAINS, BLANK, NOT_BLANK),
    NUMBER: (EQUALS, BETWEEN, BLANK, NOT_BLANK, NOT_NUMBER),
}
# Default outputs: date filters are relative only (DO-3, C3-19); Blank / Not blank / Is not a date stay available.
OUTPUT_DATE_OPS = RELATIVE + (BLANK, NOT_BLANK, NOT_DATE)
FILTER_HELP = {NOT_NUMBER: "Cells with text such as NA or Nil instead of a number",
               NOT_DATE: "Cells with text such as NA instead of a date"}

# date grains (ANA-5): calendar year
DAY, GRAINS = "day", ("day", "month", "quarter", "year")

# measures (Feature Spec A2 3.1)
DEFINITION_VERSION = 2
ROWS = "_rows"                                   # the Rows card (MEA-10)
ROWS_NAME, ROWS_TYPE = "Rows", "All rows"
SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX = "sum", "count", "count_distinct", "avg", "min", "max"
MEASURE_FNS = (SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX)        # also the order within a card (MEA-6)
FN_NAMES = {SUM: "Sum", COUNT: "Count", COUNT_DISTINCT: "Count distinct", AVG: "Average", MIN: "Min", MAX: "Max"}
CHIP_NAMES = {SUM: "Sum", COUNT: "Count", COUNT_DISTINCT: "Distinct", AVG: "Avg", MIN: "Min", MAX: "Max"}
CARD_OPS = {NUMBER: (SUM, COUNT, AVG, MIN, MAX), DATE: (COUNT, COUNT_DISTINCT, MIN, MAX),
            TEXT: (COUNT, COUNT_DISTINCT), ROWS: (COUNT,)}                     # MEA-3; no Distinct on Number (D70)
NAME_MAX = 100                                   # MEA-8
HEADER_SEP = " · "
NEED_GROUP_OR_MEASURE = "Add a group level or a measure"                     # MEA-11

REMOVED_SUFFIX = " (removed)"
NULL_LABEL = "(Null)"
NOT_NUMBER_LABEL = "(Not a number)"      # the group of text values in a Number column (TXT-10)
NOT_DATE_LABEL = "(Not a date)"


class _TextGroup:
    """A group value standing for every text value of a Number or Date column (kind 1, Tech spec A2 T42): shown as
    "(Not a number)" or "(Not a date)"."""
    _one = None

    def __new__(cls):
        if cls._one is None:
            cls._one = super().__new__(cls)
        return cls._one

    def __repr__(self) -> str:
        return "TEXT_GROUP"


TEXT_GROUP = _TextGroup()


def text_group_label(col_type: str) -> str:
    return NOT_DATE_LABEL if col_type == DATE else NOT_NUMBER_LABEL
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
class Op:
    fn: str                         # sum | count | count_distinct | avg | min | max
    name: str | None = None         # the user's header (MEA-8); None = the default (MEA-7)

    def to_dict(self) -> dict:
        return {"fn": self.fn, "name": self.name}


@dataclass
class MeasureCard:
    column_id: str                  # a template column ID, or ROWS
    ops: list[Op] = field(default_factory=list)

    def sorted_ops(self) -> list[Op]:
        """The ops in the fixed order (MEA-6), whatever order they were ticked."""
        return sorted(self.ops, key=lambda o: MEASURE_FNS.index(o.fn) if o.fn in MEASURE_FNS else 99)

    def to_dict(self) -> dict:
        return {"column_id": self.column_id, "ops": [o.to_dict() for o in self.sorted_ops()]}


@dataclass(frozen=True)
class FlatMeasure:
    """One result measure column: a card's column (or ROWS) and one of its ops, in result order."""
    column_id: str
    fn: str
    name: str | None = None


def flat_measures(definition: "Definition") -> list[FlatMeasure]:
    """The measure columns in result order (MEA-6): cards in order, each card's ops in the fixed order."""
    return [FlatMeasure(c.column_id, o.fn, o.name) for c in definition.measures for o in c.sorted_ops()]


def cards(*flat: FlatMeasure) -> list[MeasureCard]:
    """Cards from flat measures: one card per column, in order of first appearance."""
    out: dict[str, MeasureCard] = {}
    for m in flat:
        out.setdefault(m.column_id, MeasureCard(m.column_id)).ops.append(Op(m.fn, m.name))
    return list(out.values())


@dataclass
class Definition:
    template_id: str = ""
    filters: list[Filter] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    measures: list[MeasureCard] = field(default_factory=list)
    subtotals: bool = False

    def to_dict(self) -> dict:
        return {"definition_version": DEFINITION_VERSION,
                "template_id": self.template_id, "filters": [f.to_dict() for f in self.filters],
                "groups": [g.to_dict() for g in self.groups], "measures": [m.to_dict() for m in self.measures],
                "subtotals": bool(self.subtotals)}

    @classmethod
    def from_dict(cls, d: dict) -> "Definition":
        """Version 2 only (T49); there is no upgrade from older definitions (T40)."""
        if d.get("definition_version") != DEFINITION_VERSION:
            raise DefinitionError(f"definition version {d.get('definition_version')!r} is not supported")
        return cls(d.get("template_id", ""),
                   [Filter(f["column_id"], f["op"], copy.deepcopy(f.get("values") or [])) for f in d.get("filters", [])],
                   [Group(g["column_id"], g.get("grain")) for g in d.get("groups", [])],
                   [MeasureCard(m["column_id"], [Op(o["fn"], o.get("name")) for o in m.get("ops") or []])
                    for m in d.get("measures", [])],
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


def card_name(column_id: str, columns: dict[str, Column]) -> str:
    """A card's column as named in headers: "Rows", or the column's name with "(removed)" for a removed column."""
    if column_id == ROWS:
        return ROWS_NAME
    col = columns.get(column_id)
    return column_label(col) if col is not None else column_id


def default_name(column_id: str, fn: str, columns: dict[str, Column]) -> str:
    """The default header (MEA-7): "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count"."""
    return f"{card_name(column_id, columns)}{HEADER_SEP}{FN_NAMES[fn]}"


def card_ops(column_id: str, columns: dict[str, Column]) -> tuple[str, ...]:
    """The ops a card offers (MEA-3)."""
    if column_id == ROWS:
        return CARD_OPS[ROWS]
    col = columns.get(column_id)
    return CARD_OPS[col.type] if col is not None else ()


def no_op_message(column_id: str, columns: dict[str, Column]) -> str:
    """MEA-4, shown under the card."""
    return f"Tick at least one operation for {card_name(column_id, columns)}, or remove it"


def name_taken_message(name: str) -> str:
    """MEA-8, under the rename box."""
    return f"Another column is already called {name}"


def clean_name(name: str | None) -> str | None:
    """A typed header: trimmed; blank means the default (None)."""
    t = (name or "").strip()
    return t or None


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
    seen = set()
    for card in definition.measures:
        if card.column_id in seen:
            raise DefinitionError(f"{card_name(card.column_id, by_id)} is on two measure cards")
        seen.add(card.column_id)
        if card.column_id != ROWS:
            col(card.column_id)
        allowed = card_ops(card.column_id, by_id)
        fns = [o.fn for o in card.ops]
        if len(set(fns)) != len(fns):
            raise DefinitionError(f"an operation is ticked twice for {card_name(card.column_id, by_id)}")
        for fn in fns:
            if fn not in allowed:
                raise DefinitionError(f"{FN_NAMES.get(fn, fn)} can't be used on {card_name(card.column_id, by_id)}")
    problem = first_problem(definition, columns)
    if problem is not None:
        raise DefinitionError(problem[2])
    taken = [column_label(by_id[g.column_id]).lower() for g in definition.groups]
    for m in flat_measures(definition):
        if m.name is None:
            continue
        if not 1 <= len(m.name) <= NAME_MAX or m.name != m.name.strip():
            raise DefinitionError(f"A column name must be 1 to {NAME_MAX} characters")
        if m.name.lower() in taken:
            raise DefinitionError(name_taken_message(m.name))
        taken.append(m.name.lower())


def first_problem(definition: Definition, columns: list[Column]) -> tuple[str, int | None, str] | None:
    """The first of the checks the screens show before Run, Save and Preview (Tech spec A2 9.2, checks 3 and 4):
    ("measures", None, "Add a group level or a measure") or ("card", index, "Tick at least one operation for …")."""
    if not definition.groups and not definition.measures:
        return "measures", None, NEED_GROUP_OR_MEASURE
    by_id = {c.id: c for c in columns}
    for i, card in enumerate(definition.measures):
        if not card.ops:
            return "card", i, no_op_message(card.column_id, by_id)
    return None


def _ints(values: list, n: int) -> list:
    if len(values) != n:
        raise DefinitionError("wrong number of values")
    try:
        return [int(x) for x in values]
    except (TypeError, ValueError):
        raise DefinitionError("expected whole numbers") from None
