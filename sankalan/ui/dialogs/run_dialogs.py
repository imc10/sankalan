"""Dialogs of the New run wizard: 7.1 Continue despite errors (RUN-4, T18), Add as new column (MAP-7, MAP-11) and
Edit rules for this run (VR-5, TPL-8)."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLineEdit, QPlainTextEdit, QSpinBox, QWidget

from sankalan import formats
from sankalan.model.rule import Rule
from sankalan.model.template import (DATE, DATE_FORMATS, DECIMALS_DEFAULT, DECIMALS_MAX, NUMBER, TEXT, TYPES, Column)
from sankalan.run.pipeline import COMMENT_MAX
from sankalan.ui.dialogs.base import Dialog


class LimitedText(QPlainTextEdit):
    """Plain text up to ``limit`` characters; more is cut off (RUN-13, RUNC-04)."""

    def __init__(self, limit: int = COMMENT_MAX, parent=None):
        super().__init__(parent)
        self.limit = limit
        self.setTabChangesFocus(True)
        self.textChanged.connect(self._trim)

    def _trim(self) -> None:
        text = self.toPlainText()
        if len(text) > self.limit:
            cur = self.textCursor()
            pos = min(cur.position(), self.limit)
            self.blockSignals(True)
            self.setPlainText(text[:self.limit])
            self.blockSignals(False)
            cur = self.textCursor()
            cur.setPosition(pos)
            self.setTextCursor(cur)
            self.textChanged.emit()

    def counter(self) -> str:
        return f"{len(self.toPlainText())} / {self.limit}"


class OverrideDialog(Dialog):
    """7.1: "Continue despite 66 errors?" with the rows that will be left out and a required reason."""

    def __init__(self, errors: int, left_out: int, run_label: str, parent=None):
        super().__init__(f"Continue despite {formats.count(errors, 'error')}?", parent)
        self.text(f"{formats.count(left_out, 'row')} with errors will be left out. {run_label} will be marked "
                  "Committed with override. Your reason becomes the run's comment, and it can't be edited after "
                  "the commit.")
        self.label = self.text("Reason (required)", "small")
        self.reason = LimitedText(COMMENT_MAX, self)
        self.reason.setAccessibleName("Reason")
        self.reason.setFixedHeight(96)
        self.body.addWidget(self.reason)
        self.count = self.text(self.reason.counter(), "small")
        self.add_button("Go back", None, self.reject)
        self.ok = self.add_button("Continue with this reason", "primary", self._ok, default=True)
        self.reason.textChanged.connect(self._changed)
        self._changed()

    def _changed(self) -> None:
        self.count.setText(self.reason.counter())
        self.ok.setEnabled(bool(self.reason.toPlainText().strip()))

    def _ok(self) -> None:
        if self.reason.toPlainText().strip():         # an empty reason is refused (RUNV-13)
            self.accept()

    @property
    def value(self) -> str:
        return self.reason.toPlainText()


class AddColumnDialog(Dialog):
    """MAP-7: add a file column as a new template column; its type is fixed once the run is committed."""

    def __init__(self, header: str, earlier_runs: int, parent=None):
        super().__init__(f"Add “{header}” as a new column", parent)
        form = QFormLayout()
        form.setSpacing(10)
        self.name = QLineEdit(header, self)
        self.name.setAccessibleName("Column name")
        self.name.setMaxLength(100)
        form.addRow("Name", self.name)
        self.type = QComboBox(self)
        self.type.setAccessibleName("Type")
        for t in TYPES:
            self.type.addItem(t, t)
        form.addRow("Type", self.type)
        self.decimals = QSpinBox(self)
        self.decimals.setRange(0, DECIMALS_MAX)
        self.decimals.setValue(DECIMALS_DEFAULT)
        self.decimals.setAccessibleName("Decimals")
        form.addRow("Decimals", self.decimals)
        self.date_format = QComboBox(self)
        self.date_format.setAccessibleName("Date format")
        self.date_format.addItem("Excel dates", None)
        for f in DATE_FORMATS:
            self.date_format.addItem(f, f)
        form.addRow("Date format", self.date_format)
        holder = QWidget(self)
        holder.setLayout(form)
        self.body.addWidget(holder)
        runs = (f"A new column shows as null in the {formats.count(earlier_runs, 'earlier run')}. " if earlier_runs
                else "")
        self.text(runs + "Its type is fixed once this run is committed.", "small")
        self.error = self.text("", "error")
        self.error.hide()
        self.add_button("Cancel", None, self.reject)
        self.ok = self.add_button("Add column", "primary", self._ok, default=True)
        self.type.currentIndexChanged.connect(self._typed)
        self._typed()

    def _typed(self) -> None:
        t = self.type.currentData()
        self.decimals.setEnabled(t == NUMBER)
        self.date_format.setEnabled(t == DATE)

    def set_type(self, type_: str) -> None:
        self.type.setCurrentIndex(TYPES.index(type_))

    def _ok(self) -> None:
        if not self.name.text().strip():
            self.set_error("Enter a column name.")
            return
        self.accept()

    def set_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    @property
    def values(self) -> dict:
        t = self.type.currentData() or TEXT
        return {"name": self.name.text().strip(), "type_": t,
                "decimals": self.decimals.value() if t == NUMBER else None,
                "date_format": self.date_format.currentData() if t == DATE else None}


class EditRulesDialog(Dialog):
    """Edit rules for this run (VR-5, TPL-8): the rules editor of the New template wizard on this run's columns.
    Apply re-runs only the rule check; "Also save to the template" makes the change permanent (RUNV-10)."""

    def __init__(self, columns: list[Column], rules: list[Rule], counts: dict[str, int], rows: int, parent=None):
        super().__init__("Edit rules for this run", parent, width=1040)
        from sankalan.ui.screens.new_template_rules import RulesStep


        class RunRulesStep(RulesStep):
            def select(self, cid):
                super().select(cid)
                c = self.col(cid)
                if c is not None:
                    self.type_line.setText(c.type)

            def show_failures(self, rule_id):
                return None

        self.sample_rows = rows
        self.sample_name = "this run"
        self.rules = RunRulesStep(self)
        self.rules.rules_table.setHorizontalHeaderLabels(["Rule", "Setting", "If it fails", "In this run", ""])
        self.rules.setMinimumHeight(380)
        self.body.addWidget(self.rules)
        self.rules.load([c for c in columns if not c.removed], [Rule.from_dict(r.to_dict()) for r in rules])
        self.rules.set_counts(dict(counts))
        self.rules.info.setText("Counts are from the last check. Apply to check the rules again.")
        self.save_to_template = QCheckBox("Also save these rule changes to the template", self)
        self.body.addWidget(self.save_to_template)
        self.text("Without it, the changes apply to this run only and are listed in its summary.", "small")
        self.add_button("Cancel", None, self.reject)
        self.apply = self.add_button("Apply and check again", "primary", self._apply, default=True)

    def rules_changed(self) -> None:
        """RulesStep calls this after every change: the counts are out of date until Apply."""
        self.rules.counts = None
        self.rules._fill_rules()
        self.rules.info.setText("Apply to check the rules again with your changes.")

    def _apply(self) -> None:
        problem = self.rules.check()
        self.rules.show_error(problem or "")
        if not problem:
            self.accept()

    @property
    def result_rules(self) -> list[Rule]:
        return self.rules.all_rules()
