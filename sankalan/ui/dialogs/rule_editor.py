"""A rule's settings (VAL-3, VAL-5 to VAL-9): shared by Columns and rules (3.3), the New template wizard (2.4) and
Edit rules for this run (4.3). The settings are checked with ``validation.rules.check_rule`` before OK closes."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QRadioButton, QWidget

from sankalan.model.rule import (ALLOWED_VALUES, DATE_RANGE, NUMBER_RANGE, PATTERN, RULE_NAMES, TEXT_LENGTH, UNIQUE,
                                 Rule)
from sankalan.model.template import Column
from sankalan.ui.dialogs.base import Dialog
from sankalan.ui.widgets.builder import parse_typed_date, show_date
from sankalan.validation.rules import RuleError, check_rule

NEEDS_SETTINGS = (NUMBER_RANGE, DATE_RANGE, ALLOWED_VALUES, TEXT_LENGTH, PATTERN, UNIQUE)
PATTERN_HINT = "A = a letter, 9 = a digit; any other character must match exactly. Example: AAA-99999."


def _int(text: str, what: str):
    t = text.strip()
    if not t:
        return None
    if not t.isdigit():
        raise RuleError(f"{what} must be a whole number, 0 or more.")
    return int(t)


class RuleDialog(Dialog):
    def __init__(self, rule: Rule, columns: list[Column], parent=None):
        self.columns = [c for c in columns if not c.removed]
        self.col = next(c for c in self.columns if c.id == rule.column_id)
        super().__init__(f"{RULE_NAMES[rule.type]} ({self.col.name})", parent)
        self.rule = Rule.from_dict(rule.to_dict())
        s = self.rule.settings
        t = self.rule.type
        self.fields: dict[str, QWidget] = {}
        if t == NUMBER_RANGE:
            self.not_negative = QRadioButton("Not negative", self)
            self.between = QRadioButton("Between (either may be left empty)", self)
            self.body.addWidget(self.not_negative)
            self.body.addWidget(self.between)
            self._pair("min", "max", "Minimum", "Maximum", s.get("min") or "", s.get("max") or "")
            (self.not_negative if s.get("not_negative") or not s else self.between).setChecked(True)
        elif t == DATE_RANGE:
            self.text("Dates as DD-MM-YYYY; either may be left empty.", "small")
            self._pair("from", "to", "From", "To", show_date(s.get("from")), show_date(s.get("to")))
        elif t == ALLOWED_VALUES:
            self.text("Separate values with commas. Matching ignores case.", "small")
            self._line("values", "Allowed values", ", ".join(str(v) for v in s.get("values") or []))
        elif t == TEXT_LENGTH:
            self.exact_radio = QRadioButton("Exactly", self)
            self.range_radio = QRadioButton("Between (either may be left empty)", self)
            self.body.addWidget(self.exact_radio)
            self._line("exact", "Length", "" if s.get("exact") is None else str(s["exact"]))
            self.body.addWidget(self.range_radio)
            self._pair("min", "max", "Minimum", "Maximum", "" if s.get("min") is None else str(s["min"]),
                       "" if s.get("max") is None else str(s["max"]))
            (self.range_radio if s and s.get("exact") is None else self.exact_radio).setChecked(True)
        elif t == PATTERN:
            self.text(PATTERN_HINT, "small")
            self._line("pattern", "Pattern", s.get("pattern") or "")
        elif t == UNIQUE:
            self.text(f"Rows must not repeat the same {self.col.name}. Add columns to make the key wider:", "small")
            self.keys: dict[str, QCheckBox] = {}
            chosen = set(rule.key_columns[1:])
            for c in self.columns:
                if c.id == self.col.id:
                    continue
                box = QCheckBox(c.name, self)
                box.setChecked(c.id in chosen)
                self.keys[c.id] = box
                self.body.addWidget(box)
        self.error = self.text("", "error")
        self.error.hide()
        self.add_button("Cancel", None, self.reject)
        self.ok = self.add_button("OK", "primary", self._ok, default=True)

    def _line(self, key: str, label: str, value: str) -> QLineEdit:
        lab = QLabel(label, self)
        lab.setProperty("kind", "small")
        e = QLineEdit(value, self)
        e.setAccessibleName(label)
        self.body.addWidget(lab)
        self.body.addWidget(e)
        self.fields[key] = e
        return e

    def _pair(self, k1: str, k2: str, l1: str, l2: str, v1: str, v2: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        for k, label, v in ((k1, l1, v1), (k2, l2, v2)):
            e = QLineEdit(v, self)
            e.setPlaceholderText(label)
            e.setAccessibleName(label)
            self.fields[k] = e
            row.addWidget(e, 1)
        self.body.addLayout(row)

    def value(self) -> dict:
        """The settings typed, as the rule stores them. Raises ``RuleError`` for a value that can't be read."""
        t, f = self.rule.type, self.fields
        if t == NUMBER_RANGE:
            if self.not_negative.isChecked():
                return {"not_negative": True}
            out = {}
            for k in ("min", "max"):
                if f[k].text().strip():
                    out[k] = f[k].text().strip().replace(",", "")
            return out
        if t == DATE_RANGE:
            try:
                out = {k: parse_typed_date(f[k].text()) for k in ("from", "to")}
            except ValueError as e:
                raise RuleError(str(e)) from None
            return {k: v for k, v in out.items() if v}
        if t == ALLOWED_VALUES:
            return {"values": [v.strip() for v in f["values"].text().split(",") if v.strip()]}
        if t == TEXT_LENGTH:
            if self.exact_radio.isChecked():
                return {"exact": _int(f["exact"].text(), "The length")}
            out = {k: _int(f[k].text(), "The " + ("minimum" if k == "min" else "maximum")) for k in ("min", "max")}
            return {k: v for k, v in out.items() if v is not None}
        if t == PATTERN:
            return {"pattern": f["pattern"].text()}
        if t == UNIQUE:
            keys = [cid for cid, box in self.keys.items() if box.isChecked()]
            return {"columns": [self.col.id] + keys} if keys else {}
        return {}

    def _ok(self) -> None:
        try:
            self.rule.settings = self.value()
            if self.rule.type == TEXT_LENGTH and self.rule.settings.get("exact", 0) is None:
                raise RuleError("Text length needs an exact, minimum or maximum length.")
            check_rule(self.rule, self.columns)
        except (RuleError, KeyError) as e:
            self.error.setText(str(e) if isinstance(e, RuleError) else "Fill in the settings.")
            self.error.show()
            return
        self.accept()
