"""2.4 New template › Rules and 2.5 › Default outputs (VR-1, VR-2, VR-7, VR-8, DO-1, DO-3, DO-8; C3-13 to C3-19).

Rules: the included columns on the left; the selected column's rules on the right, each with its setting, an
Error / Warning choice and its failure count on the sample rows. The automatic Is a number / Is a date rules have
no remove control (VR-7). Counts are a dry run on the sample after every change (VR-8); a count opens the first
20 failing rows.

Check data before loading (NCK-2, NCK-3; Tech spec A2 6.2): a Yes / No bar at the top. No replaces the rule editor
with the 2.4b panel: what No means, the sample's values that aren't numbers or dates per column, and "No rules will
be set for this template". The rules entered stay in memory and come back on Yes.

Default outputs: the template's Default outputs tab without its save bar, previewing on the sample (DO-8).
"""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QMenu, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import formats
from sankalan.model.rule import ERROR, IS_DATE, IS_NUMBER, RULE_NAMES, SEVERITIES, Rule, next_rule_id, with_type_rules
from sankalan.model.template import NUMBER, Column, Template
from sankalan.ui import theme
from sankalan.ui.dialogs.base import Dialog
from sankalan.ui.dialogs.rule_editor import NEEDS_SETTINGS, RuleDialog
from sankalan.ui.screens.template_columns import setting_text
from sankalan.ui.screens.template_outputs import OutputsTab
from sankalan.ui.widgets.controls import YesNoBar, heading, icon_button, note, panel, plus_button
from sankalan.validation import issues as iss
from sankalan.validation.rules import RuleError, check_rule, rules_for_type


BECOMES_FIXED = "Becomes fixed after the first run"

# Check data before loading (NCK-2, NCK-3, NCK-11)
CHECKS_LABEL = "Check data before loading"
CHECKS_HINT_NEW = "Applies to every run of this template. Can be changed later in Settings."
NO_CHECKS_TEXT = ("Every row read is loaded, duplicates included. No rules run, no issues are listed and nothing is "
                  "left out. Values that aren't numbers or dates are kept as typed and counted at Load and Commit. "
                  "File errors, Mapping, the duplicate-file warning and the totals check still apply.")
NO_RULES_FOOTER = "No rules will be set for this template"


def text_count_line(name: str, count: int, rows: int) -> str:
    """"Tax Amount · 38 of 100,000" (2.4b)."""
    return f"{name} · {formats.number(count)} of {formats.number(rows)}"


def sample_fails(n: int | None, rows: int) -> str:
    """"0 of 1,000 fail" (canvas 2.4)."""
    if n is None:
        return "…"
    return f"{formats.number(n)} of {formats.number(rows)} fail"


def rules_summary(rules: list[Rule]) -> str:
    """"19 · 15 Errors, 4 Warnings" (canvas 2.6)."""
    errors = sum(1 for r in rules if r.severity == ERROR)
    warnings = len(rules) - errors
    return (f"{len(rules)} · {formats.count(errors, 'Error')}, {formats.count(warnings, 'Warning')}")


class ShowDialog(Dialog):
    """The first 20 failing sample rows of one rule (VR-8, C3-16)."""

    def __init__(self, title: str, intro: str, rows: list[tuple[str, str, str]], parent=None):
        super().__init__(title, parent, width=720)
        self.text(intro, "small")
        self.table = QTableWidget(len(rows), 3, self)
        self.table.setHorizontalHeaderLabels(["Row", "Value", "Message"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QTableWidgetItem(text)
                if c == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, item)
        self.table.setMinimumHeight(min(420, 40 + 32 * max(len(rows), 3)))
        self.body.addWidget(self.table)
        self.add_button("Close", "primary", self.accept, default=True)

    def rows(self) -> list[list[str]]:
        return [[self.table.item(r, c).text() for c in range(3)] for r in range(self.table.rowCount())]


class NoChecksPanel(QWidget):
    """2.4b: what No means, the sample's text counts per Number and Date column, and the footer (NCK-3)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        box = panel(self)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(12)
        bl.addWidget(heading("This template loads without checks", box, theme.BODY_PX))
        self.explain = note(NO_CHECKS_TEXT, box, "body")
        bl.addWidget(self.explain)
        self.title = heading("Values in the sample that aren't numbers or dates", box, theme.GRID_TEXT_PX)
        bl.addWidget(self.title)
        self.table = QTableWidget(0, 3, box)
        self.table.setHorizontalHeaderLabels(["Column", "Type", "Values"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, w in ((1, 100), (2, 200)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            hh.resizeSection(i, w)
        bl.addWidget(self.table, 1)
        self.none = note("", box)
        bl.addWidget(self.none)
        lay.addWidget(box, 1)
        self.footer = note(NO_RULES_FOOTER, self, "body")
        lay.addWidget(self.footer)

    def set_counts(self, lines, rows: int | None, sample: str) -> None:
        """``lines``: ``newtemplate.SampleTextCount`` per column with text values; None while counting."""
        if lines is None:
            self.table.setRowCount(0)
            self.none.setText("Counting values in the sample…")
            return
        self.table.setRowCount(len(lines))
        for r, x in enumerate(lines):
            items = [QTableWidgetItem(x.name), QTableWidgetItem(x.type),
                     QTableWidgetItem(f"{formats.number(x.count)} of {formats.number(x.rows)}")]
            items[2].setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for c, it in enumerate(items):
                self.table.setItem(r, c, it)
        self.none.setText(f"Every value in the Number and Date columns of the first {formats.count(rows or 0, 'row')} "
                          f"of {sample} is a number or a date." if not lines else
                          f"Counted on the first {formats.count(rows or 0, 'row')} of {sample}.")

    def lines(self) -> list[str]:
        """The table as "Column · N of M" lines."""
        return [f"{self.table.item(r, 0).text()} · {self.table.item(r, 2).text()}"
                for r in range(self.table.rowCount())]


class RulesStep(QWidget):
    checks_changed = Signal(bool)

    def __init__(self, wizard):
        super().__init__(wizard)
        self.wizard = wizard
        self.columns: list[Column] = []
        self.rules: list[Rule] = []             # the user's rules plus automatic ones whose severity changed
        self.selected: str | None = None
        self.counts: dict[str, int] | None = None
        self.first: dict[str, list[tuple]] = {}
        self.text_lines = None                  # 2.4b counts (newtemplate.SampleTextCount), None until counted
        self.dialog = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)
        self.checks_bar = YesNoBar(CHECKS_LABEL, CHECKS_HINT_NEW, self)
        self.checks_bar.changed.connect(self._checks_picked)
        outer.addWidget(self.checks_bar)
        self.no_panel = NoChecksPanel(self)
        self.no_panel.hide()
        outer.addWidget(self.no_panel, 1)
        self.editor = QWidget(self)
        outer.addWidget(self.editor, 1)
        lay = QHBoxLayout(self.editor)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        left = panel(self)
        left.setFixedWidth(330)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 3, left)
        self.table.setHorizontalHeaderLabels(["Column", "Type", "Rules"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("QTableWidget { border: 0; }")
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, w in ((1, 80), (2, 56)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            hh.resizeSection(i, w)
        self.table.itemSelectionChanged.connect(self._row_selected)
        ll.addWidget(self.table)
        lay.addWidget(left)

        right = panel(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(12)
        self.name = QLabel("", right)
        self.name.setProperty("kind", "h2")
        rl.addWidget(self.name)
        self.type_line = note("", right)
        rl.addWidget(self.type_line)
        head = QHBoxLayout()
        head.addWidget(heading("Rules", right, theme.GRID_TEXT_PX))
        head.addStretch(1)
        self.add_rule_button = plus_button("Add rule", right)
        self.add_rule_button.clicked.connect(lambda: self.rule_menu().popup(
            self.add_rule_button.mapToGlobal(self.add_rule_button.rect().bottomLeft())))
        head.addWidget(self.add_rule_button)
        rl.addLayout(head)
        self.rules_table = QTableWidget(0, 5, right)
        self.rules_table.setHorizontalHeaderLabels(["Rule", "Setting", "If it fails", "On sample rows", ""])
        self.rules_table.verticalHeader().hide()
        self.rules_table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.rules_table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.rules_table.setShowGrid(False)
        rh = self.rules_table.horizontalHeader()
        rh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, w in ((2, 120), (3, 160), (4, 40)):
            rh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            rh.resizeSection(i, w)
        self.rules_table.cellDoubleClicked.connect(lambda r, _c: self.edit_rule(r))
        rl.addWidget(self.rules_table, 1)
        self.error = note("", right, "error")
        self.error.hide()
        rl.addWidget(self.error)
        self.info = note("", right)
        rl.addWidget(self.info)
        lay.addWidget(right, 1)

    # ------------------------------------------------------------------------------------------ checks (NCK-2)
    @property
    def checks(self) -> bool:
        return self.checks_bar.value()

    def set_checks(self, yes: bool) -> None:
        """Yes shows the rule editor, No the 2.4b panel. The rules entered stay in ``rules`` either way."""
        if yes != self.checks_bar.value():
            self.checks_bar.set_value(yes)
        self.editor.setVisible(yes)
        self.no_panel.setVisible(not yes)

    def _checks_picked(self, yes: bool) -> None:
        self.set_checks(yes)
        self.show_error("")
        self.checks_changed.emit(yes)

    def set_text_counts(self, lines) -> None:
        self.text_lines = lines
        self.no_panel.set_counts(lines, self.wizard.sample_rows, self.wizard.sample_name)

    # ------------------------------------------------------------------------------------------ load
    def load(self, columns: list[Column], rules: list[Rule]) -> None:
        """Columns as drafted on step 3 (included only); rules kept from an earlier visit (C3-22)."""
        self.columns = columns
        live = {c.id: c for c in columns}
        self.rules = [r for r in rules if r.column_id in live and (not r.automatic or
                      r.type == (IS_NUMBER if live[r.column_id].type == NUMBER else IS_DATE))]
        keep = self.selected if self.selected in live else None
        self.selected = None
        self.counts = None
        self._fill_list()
        self.select(keep or (columns[0].id if columns else None))

    def all_rules(self) -> list[Rule]:
        """Every rule that runs: one automatic type rule per Number / Date column (VR-7), then the user's."""
        return with_type_rules(self.columns, self.rules)

    def column_rules(self, cid: str) -> list[Rule]:
        return [r for r in self.all_rules() if r.column_id == cid]

    def col(self, cid: str | None = None) -> Column | None:
        cid = cid or self.selected
        return next((c for c in self.columns if c.id == cid), None)

    def _fill_list(self) -> None:
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self.columns))
            for r, c in enumerate(self.columns):
                for i, text in enumerate((c.name, c.type, str(len(self.column_rules(c.id))))):
                    item = QTableWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, c.id)
                    if i == 2:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(r, i, item)
            ids = [c.id for c in self.columns]
            if self.selected in ids:
                self.table.selectRow(ids.index(self.selected))

    def list_rows(self) -> list[tuple[str, str, str]]:
        return [tuple(self.table.item(r, i).text() for i in range(3)) for r in range(self.table.rowCount())]

    def _row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.select(self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def select(self, cid: str | None) -> None:
        self.selected = cid
        c = self.col(cid)
        self.add_rule_button.setEnabled(c is not None)
        if c is None:
            self.name.setText("")
            self.type_line.setText("")
            self.rules_table.setRowCount(0)
            return
        with QSignalBlocker(self.table):
            self.table.selectRow([x.id for x in self.columns].index(cid))
        self.name.setText(c.name)
        self.type_line.setText(f"{c.type} · {BECOMES_FIXED}")
        self._fill_rules()

    def _fill_rules(self) -> None:
        c = self.col()
        rules = self.column_rules(c.id) if c else []
        rows = self.wizard.sample_rows
        self.rules_table.setRowCount(len(rules))
        for r, rule in enumerate(rules):
            name = QTableWidgetItem(rule.name + ("  Auto" if rule.automatic else ""))
            name.setData(Qt.ItemDataRole.UserRole, rule.id)
            self.rules_table.setItem(r, 0, name)
            setting = QTableWidgetItem(setting_text(rule, self.columns))
            setting.setToolTip("Double-click to change" if rule.type in NEEDS_SETTINGS else "")
            self.rules_table.setItem(r, 1, setting)
            sev = QComboBox()
            sev.setAccessibleName(f"If {rule.name} fails")
            for s in SEVERITIES:
                sev.addItem(s, s)
            sev.setCurrentIndex(SEVERITIES.index(rule.severity))
            sev.currentIndexChanged.connect(lambda _i, rid=rule.id, cb=sev: self.set_severity(rid, cb.currentData()))
            self.rules_table.setCellWidget(r, 2, sev)
            n = None if self.counts is None else self.counts.get(rule.id, 0)
            count = QPushButton(sample_fails(n, rows))
            count.setProperty("kind", "plain")
            count.setAccessibleName(f"{rule.name} failures on the sample")
            count.setToolTip("Show the first 20 failing rows" if n else "")
            colour = theme.SUBTLE if not n else (theme.ERROR if rule.severity == ERROR else theme.OVERRIDE_TEXT)
            count.setStyleSheet(f"color: {colour}; text-align: left;")
            count.clicked.connect(lambda _c=False, rid=rule.id: self.show_failures(rid))
            self.rules_table.setCellWidget(r, 3, count)
            if not rule.automatic:
                rm = icon_button("close", f"Remove rule {rule.name}")
                rm.clicked.connect(lambda _c=False, rid=rule.id: self.remove_rule(rid))
                self.rules_table.setCellWidget(r, 4, rm)
            else:
                self.rules_table.removeCellWidget(r, 4)

    def rule_rows(self) -> list[tuple[str, str, str, str, bool]]:
        """(rule, setting, severity, count, removable) per row of the selected column, for tests."""
        out = []
        for r in range(self.rules_table.rowCount()):
            out.append((self.rules_table.item(r, 0).text(), self.rules_table.item(r, 1).text(),
                        self.rules_table.cellWidget(r, 2).currentText(), self.rules_table.cellWidget(r, 3).text(),
                        self.rules_table.cellWidget(r, 4) is not None))
        return out

    # ------------------------------------------------------------------------------------------ editing
    def _changed(self) -> None:
        self._fill_list()
        self._fill_rules()
        self.wizard.rules_changed()

    def rule_menu(self) -> QMenu:
        """C3-14: the rule types this column's type allows (no type rules, no between-column rules)."""
        menu = QMenu(self)
        c = self.col()
        for t in rules_for_type(c.type) if c else []:
            menu.addAction(RULE_NAMES[t], lambda t=t: self.add_rule(t))
        self.menu = menu
        return menu

    def add_rule(self, rule_type: str, settings: dict | None = None, severity: str = ERROR) -> Rule | None:
        c = self.col()
        rule = Rule(next_rule_id(self.rules), c.id, rule_type, dict(settings or {}), severity)
        if settings is None and rule_type in NEEDS_SETTINGS:
            dlg = RuleDialog(rule, self.columns, self)
            self.dialog = dlg
            accepted = dlg.exec() == RuleDialog.DialogCode.Accepted
            self.dialog = None
            if not accepted:
                return None
            rule = dlg.rule
        else:
            try:
                check_rule(rule, self.columns)
            except RuleError as e:
                self.show_error(str(e))
                return None
        self.show_error("")
        self.rules.append(rule)
        self._changed()
        return rule

    def edit_rule(self, row: int) -> None:
        rid = self.rules_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        rule = next((r for r in self.rules if r.id == rid), None)
        if rule is None or rule.type not in NEEDS_SETTINGS:
            return
        dlg = RuleDialog(rule, self.columns, self)
        self.dialog = dlg
        if dlg.exec() == RuleDialog.DialogCode.Accepted:
            rule.settings = dlg.rule.settings
            self._changed()
        self.dialog = None

    def set_severity(self, rule_id: str, severity: str) -> None:
        """VR-7: a type rule can be set to Warning (kept as a rule with that severity), never removed."""
        if not any(r.id == rule_id for r in self.rules):
            auto = next(r for r in self.all_rules() if r.id == rule_id)
            self.rules.append(auto)
        rule = next(r for r in self.rules if r.id == rule_id)
        if rule.severity != severity:
            rule.severity = severity
            self._changed()

    def remove_rule(self, rule_id: str) -> None:
        rule = next((r for r in self.rules if r.id == rule_id), None)
        if rule is None or rule.automatic:
            return
        self.rules.remove(rule)
        self._changed()

    def show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    # ------------------------------------------------------------------------------------------ counts (VR-8)
    def set_counts(self, counts: dict[str, int] | None, first: dict[str, list[tuple]] | None = None) -> None:
        self.counts = counts
        self.first = first or {}
        rows, name = self.wizard.sample_rows, self.wizard.sample_name
        self.info.setText(f"Counts are on the first {formats.count(rows, 'row')} of {name}. Click a count to see the "
                          "first 20 failing rows." if counts is not None else "Counting failures on the sample…")
        self._fill_rules()

    def show_failures(self, rule_id: str) -> ShowDialog | None:
        if not self.counts or not self.counts.get(rule_id):
            return None
        rule = next(r for r in self.all_rules() if r.id == rule_id)
        names = {c.id: c.name for c in self.columns}
        file_names = {0: self.wizard.sample_name}
        rows = []
        for t in self.first.get(rule_id, []):
            issue = iss.from_row(t, file_names, names)
            rows.append((formats.number(issue.row), issue.value or "", issue.message))
        n = self.counts[rule_id]
        col = names.get(rule.column_id, rule.column_id)
        intro = (f"All {formats.number(n)} failing rows." if n <= len(rows) else
                 f"The first {len(rows)} of {formats.number(n)} failing rows.")
        dlg = ShowDialog(f"{col}: {rule.name}", intro, rows, self)
        self.dialog = dlg
        dlg.finished.connect(lambda _r: setattr(self, "dialog", None))
        dlg.open()
        return dlg

    def check(self) -> str | None:
        if not self.checks:
            return None                     # no rules are saved (Tech spec A2 6.2)
        for rule in self.all_rules():
            try:
                check_rule(rule, self.columns)
            except RuleError as e:
                col = self.col(rule.column_id)
                return f"{rule.name} ({col.name if col else rule.column_id}): {e}"
        return None


class SampleRef:
    """Stands in for the latest run in the outputs tab: previews say "On the sample · 1,000 rows · …"."""
    label = "the sample"
    data = None


class OutputsStep(OutputsTab):
    """2.5: the Default outputs tab on the drafted columns, previewing on the sample (DO-8); optional (C3-17)."""

    def __init__(self, wizard):
        super().__init__(wizard)
        self.wizard = wizard
        self.bar.hide()
        self.none.setText("No default outputs yet. They are optional: add one, or go on to Review.")

    def load_draft(self, template: Template) -> None:
        """Columns from step 3; outputs kept from an earlier visit (C3-22)."""
        keep = self.selected
        self._store()
        self.template = template
        self.latest = SampleRef()
        self.builder.columns = template.active_columns
        self.selected = -1
        self._redraw_list()
        self.select(keep if 0 <= keep < len(self.outputs) else (0 if self.outputs else -1))
        self._clear_preview("Preview runs on the sample rows. Click Preview.")

    def _clear_preview(self, text: str | None) -> None:
        super()._clear_preview(text)
        self.screen.bridge.set_allowed(self.preview_button, bool(self.outputs))

    def preview_work(self, definition):
        return self.wizard.preview_work(definition)

    def set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
