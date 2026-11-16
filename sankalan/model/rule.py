"""Validation rules attached to template columns (VAL-1 to VAL-9, VR-1, VR-2, VR-5, VR-7).

A rule belongs to one column (its owner) and has a type, settings and a severity. Settings by type:

====== ====================== =====================================================================
VAL-1  Not blank              ``{}``
VAL-2  Is a number            ``{}`` (automatic on Number columns, VR-7)
VAL-3  Number range           ``{"min": "0", "max": "100"}`` (either may be left out) or ``{"not_negative": true}``
VAL-4  Is a date              ``{}`` (automatic on Date columns, VR-7)
VAL-5  Date range             ``{"from": "2026-04-01", "to": "2027-03-31"}`` (ISO; either may be left out)
VAL-6  Allowed values         ``{"values": ["B2B", "B2C", "Export"]}``
VAL-7  Text length            ``{"exact": 15}`` or ``{"min": 1, "max": 30}``
VAL-8  Character pattern      ``{"pattern": "AAAAA9999A"}``
VAL-9  Unique within the run  ``{"columns": ["c001", "c004"]}``: the key, owner column first
====== ====================== =====================================================================

Numbers in settings are kept as text so that JSON never turns them into binary floats.

Rule IDs are stable within a template: ``r1``, ``r2``, ... for rules the user adds, and ``<column-id>.type`` for the
automatic Is a number / Is a date rule. Issues and issue counts carry the rule ID.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from sankalan.model.template import DATE, NUMBER, Column, active

NOT_BLANK, IS_NUMBER, NUMBER_RANGE, IS_DATE, DATE_RANGE = "VAL-1", "VAL-2", "VAL-3", "VAL-4", "VAL-5"
ALLOWED_VALUES, TEXT_LENGTH, PATTERN, UNIQUE = "VAL-6", "VAL-7", "VAL-8", "VAL-9"
RULE_TYPES = (NOT_BLANK, IS_NUMBER, NUMBER_RANGE, IS_DATE, DATE_RANGE, ALLOWED_VALUES, TEXT_LENGTH, PATTERN, UNIQUE)
TYPE_RULES = (IS_NUMBER, IS_DATE)

RULE_NAMES = {
    NOT_BLANK: "Not blank", IS_NUMBER: "Is a number", NUMBER_RANGE: "Number range", IS_DATE: "Is a date",
    DATE_RANGE: "Date range", ALLOWED_VALUES: "Allowed values", TEXT_LENGTH: "Text length",
    PATTERN: "Character pattern", UNIQUE: "Unique within the run",
}

ERROR, WARNING = "Error", "Warning"
SEVERITIES = (ERROR, WARNING)


@dataclass
class Rule:
    id: str
    column_id: str                  # the owner column (VR-1)
    type: str
    settings: dict = field(default_factory=dict)
    severity: str = ERROR

    def __post_init__(self):
        if self.type not in RULE_TYPES:
            raise ValueError(f"unknown rule type {self.type!r}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity!r}")

    @property
    def name(self) -> str:
        return RULE_NAMES[self.type]

    @property
    def automatic(self) -> bool:
        return self.type in TYPE_RULES

    @property
    def key_columns(self) -> list[str]:
        """VAL-9: the key column IDs, owner first."""
        cols = list(self.settings.get("columns") or [])
        return [self.column_id] + [c for c in cols if c != self.column_id]

    def to_dict(self) -> dict:
        return {"id": self.id, "column_id": self.column_id, "type": self.type,
                "settings": copy.deepcopy(self.settings), "severity": self.severity}

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(d["id"], d["column_id"], d["type"], copy.deepcopy(d.get("settings") or {}),
                   d.get("severity", ERROR))


def type_rule_id(column_id: str) -> str:
    return f"{column_id}.type"


def with_type_rules(columns: list[Column], rules: list[Rule]) -> list[Rule]:
    """``rules`` with exactly one Is a number / Is a date rule per active Number / Date column (VR-7): a missing one
    is added as an Error, an existing one keeps its severity, and type rules that no longer fit their column are
    dropped. Type rules come first, in column order; the user's rules follow in their own order."""
    by_column = {r.column_id: r for r in rules if r.automatic}
    auto = []
    for col in active(columns):
        kind = IS_NUMBER if col.type == NUMBER else IS_DATE if col.type == DATE else None
        if kind is None:
            continue
        old = by_column.get(col.id)
        severity = old.severity if old is not None and old.type == kind else ERROR
        auto.append(Rule(type_rule_id(col.id), col.id, kind, {}, severity))
    live = {c.id for c in active(columns)}
    return auto + [r for r in rules if not r.automatic and r.column_id in live]


def next_rule_id(rules: list[Rule]) -> str:
    n = 0
    for r in rules:
        if r.id.startswith("r") and r.id[1:].isdigit():
            n = max(n, int(r.id[1:]))
    return f"r{n + 1}"


def copy_rules(rules: list[Rule]) -> list[Rule]:
    return [Rule.from_dict(r.to_dict()) for r in rules]


def rule_changes(before: list[Rule], after: list[Rule]) -> list[dict]:
    """Rules added, removed or changed between the template's rules and a run's rules (VR-5, RUN-12), in rule order.
    Each item: ``{"change": "added" | "removed" | "changed", "rule_id", "before": dict | None, "after": dict | None}``.
    """
    old = {r.id: r for r in before}
    new = {r.id: r for r in after}
    out = []
    for r in after:
        if r.id not in old:
            out.append({"change": "added", "rule_id": r.id, "before": None, "after": r.to_dict()})
        elif old[r.id].to_dict() != r.to_dict():
            out.append({"change": "changed", "rule_id": r.id, "before": old[r.id].to_dict(), "after": r.to_dict()})
    for r in before:
        if r.id not in new:
            out.append({"change": "removed", "rule_id": r.id, "before": r.to_dict(), "after": None})
    return out
