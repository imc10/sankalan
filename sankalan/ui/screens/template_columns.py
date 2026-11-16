"""3.3 Template › Columns and rules (UX-6, MAP-3, MAP-8, MAP-11, MAP-12, TPL-9, VR-8; C4-09 to C4-16).

Columns: rename, reorder, add, remove (refused while a default output uses the column). Type and decimal places are
fixed once the template has a committed run (a column added here stays editable until it is saved). Aliases and
rules per column; "Test rules on latest run" counts failures on the latest run and stores nothing.
"""
from __future__ import annotations

import copy
import datetime as dt

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import formats, manage
from sankalan.ingest.detect import norm
from sankalan.model.rule import ERROR, RULE_NAMES, SEVERITIES, UNIQUE, Rule, next_rule_id, with_type_rules
from sankalan.model.template import (DATE, DATE_FORMATS, DECIMALS_DEFAULT, DECIMALS_MAX, NUMBER, TEXT, TYPES, Column,
                                     Template, next_column_id, outputs_using)
from sankalan.ui import theme
from sankalan.ui.dialogs.rule_editor import NEEDS_SETTINGS, RuleDialog
from sankalan.ui.screens.template import TemplateTab
from sankalan.ui.widgets.controls import ChipList, SaveBar, heading, icon_button, note, panel, plus_button, primary
from sankalan.ui.widgets.progress import ProgressPanel
from sankalan.validation.rules import ALLOWED_ON, RuleError, check_rule, describe, rules_for_type

NOTE = "Changes apply from the next run. Data already loaded is never changed."
FIXED = "Fixed after the first run"
NOTHING_STORED = "Nothing is stored."
EXCEL_DATES = "Excel dates"


def setting_text(rule: Rule, columns: list[Column]) -> str:
    """The Setting cell: the detail of ``describe`` without the rule name and severity."""
    if rule.automatic:
        return "Plain numbers, 1,234.50 and (1,234)" if rule.type == "VAL-2" else "DD-MM-YYYY, DD/MM/YYYY or Excel dates"
    text = describe(rule, columns)
    head, _, rest = text.partition(": ")
    if not rest:
        return "No setting"
    return rest.rsplit(" · ", 1)[0]


def fails_text(n: int | None) -> str:
    if n is None:
        return ""
    return "1 row fails" if n == 1 else f"{formats.number(n)} rows fail"


class ColumnsTab(TemplateTab):
    def __init__(self, screen):
        super().__init__(screen)
        self.template: Template | None = None
        self.columns: list[Column] = []
        self.rules: list[Rule] = []
        self.locked: set[str] = set()
        self.selected: str | None = None
        self.tested: dict[str, int] = {}
        self.tested_on = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(12)
        self.bar = SaveBar("Save changes", NOTE, self, screen.bridge)
        self.bar.save.clicked.connect(lambda: self.save())
        self.bar.discard.clicked.connect(self.discard)
        lay.addWidget(self.bar)
        self.error = note("", self, "error")
        self.error.hide()
        lay.addWidget(self.error)
        body = QHBoxLayout()
        body.setSpacing(16)

        # ---- column list
        left = panel(self)
        left.setFixedWidth(360)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 12)
        ll.setSpacing(8)
        self.table = QTableWidget(0, 5, left)
        self.table.setHorizontalHeaderLabels(["Column", "Type", "Rules", "Aliases", ""])
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
        for i, w in ((1, 70), (2, 46), (3, 56), (4, 60)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            hh.resizeSection(i, w)
        self.table.itemSelectionChanged.connect(self._row_selected)
        ll.addWidget(self.table, 1)
        add_row = QHBoxLayout()
        add_row.setContentsMargins(12, 0, 12, 0)
        self.add_button = plus_button("Add column", left)
        self.add_button.clicked.connect(self.add_column)
        add_row.addWidget(self.add_button)
        add_row.addStretch(1)
        ll.addLayout(add_row)
        body.addWidget(left)

        # ---- detail
        right = panel(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(12)
        scroll = QScrollArea(right)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail = QWidget()
        dl = QVBoxLayout(self.detail)
        dl.setContentsMargins(0, 0, 8, 0)
        dl.setSpacing(12)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.name = QLineEdit(self.detail)
        self.name.setAccessibleName("Column name")
        self.name.textEdited.connect(self._name_edited)
        form.addRow("Column name", self.name)
        type_row = QHBoxLayout()
        self.type = QComboBox(self.detail)
        self.type.setAccessibleName("Type")
        for t in TYPES:
            self.type.addItem(t, t)
        self.type.currentIndexChanged.connect(self._type_changed)
        type_row.addWidget(self.type)
        self.fixed = QLabel(FIXED, self.detail)
        self.fixed.setProperty("kind", "small")
        type_row.addWidget(self.fixed, 1)
        form.addRow("Type", type_row)
        self.decimals = QSpinBox(self.detail)
        self.decimals.setRange(0, DECIMALS_MAX)
        self.decimals.setAccessibleName("Decimal places")
        self.decimals.valueChanged.connect(self._decimals_changed)
        self.decimals_label = QLabel("Decimals", self.detail)
        form.addRow(self.decimals_label, self.decimals)
        self.date_format = QComboBox(self.detail)
        self.date_format.setAccessibleName("Date format")
        self.date_format.addItem(EXCEL_DATES, None)
        for f in DATE_FORMATS:
            self.date_format.addItem(f"Text dates {f}", f)
        self.date_format.currentIndexChanged.connect(self._date_format_changed)
        self.date_format_label = QLabel("Date format", self.detail)
        form.addRow(self.date_format_label, self.date_format)
        self.totals = QCheckBox("Check this column's grand total on every run", self.detail)
        self.totals.toggled.connect(self._totals_changed)
        self.totals_label = QLabel("Totals check", self.detail)
        form.addRow(self.totals_label, self.totals)
        dl.addLayout(form)
        dl.addWidget(heading("Aliases (other headers that map to this column)", self.detail, theme.GRID_TEXT_PX))
        self.aliases = ChipList("Add alias", self.detail, "Another header name", check=self._alias_problem)
        self.aliases.changed.connect(self._aliases_changed)
        dl.addWidget(self.aliases)
        rules_head = QHBoxLayout()
        rules_head.addWidget(heading("Rules", self.detail, theme.GRID_TEXT_PX))
        rules_head.addStretch(1)
        self.add_rule_button = plus_button("Add rule", self.detail)
        self.add_rule_button.clicked.connect(lambda: self.rule_menu().popup(
            self.add_rule_button.mapToGlobal(self.add_rule_button.rect().bottomLeft())))
        rules_head.addWidget(self.add_rule_button)
        dl.addLayout(rules_head)
        self.rules_table = QTableWidget(0, 5, self.detail)
        self.rules_table.setHorizontalHeaderLabels(["Rule", "Setting", "If it fails", "Test", ""])
        self.rules_table.verticalHeader().hide()
        self.rules_table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.rules_table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.rules_table.setShowGrid(False)
        self.rules_table.setMinimumHeight(3 * theme.ROW_HEIGHT)
        rh = self.rules_table.horizontalHeader()
        rh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, w in ((2, 120), (3, 120), (4, 40)):
            rh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            rh.resizeSection(i, w)
        self.rules_table.cellDoubleClicked.connect(lambda r, _c: self.edit_rule(r))
        dl.addWidget(self.rules_table)
        remove_row = QHBoxLayout()
        remove_row.addStretch(1)
        self.remove_button = QPushButton("Remove column", self.detail)
        self.remove_button.setProperty("kind", "plain")
        self.remove_button.setStyleSheet(f"color: {theme.ERROR};")
        self.remove_button.clicked.connect(self.remove_selected)
        remove_row.addWidget(self.remove_button)
        dl.addLayout(remove_row)
        dl.addStretch(1)
        scroll.setWidget(self.detail)
        rl.addWidget(scroll, 1)
        foot = QHBoxLayout()
        self.test_info = note("", right)
        foot.addWidget(self.test_info, 1)
        self.test_button = primary("Test rules on latest run", right, "secondary")
        self.test_button.clicked.connect(self.test_rules)
        screen.bridge.guard(self.test_button)
        foot.addWidget(self.test_button)
        rl.addLayout(foot)
        self.progress = ProgressPanel(right)
        self.progress.hide()
        rl.addWidget(self.progress)
        body.addWidget(right, 1)
        lay.addLayout(body, 1)

    # ------------------------------------------------------------------------------------------ load
    def load(self, detail: manage.TemplateDetail) -> None:
        self.template = detail.template
        self.columns = [copy.deepcopy(c) for c in detail.template.columns]
        self.rules = [Rule.from_dict(r.to_dict()) for r in detail.template.rules]
        self.locked = {c.id for c in self.columns} if detail.has_runs else set()
        self.latest = detail.latest
        self.tested = {}
        self.test_info.setText("" if detail.latest else "Test rules needs a committed run.")
        self.screen.bridge.set_allowed(self.test_button, detail.latest is not None)
        keep = self.selected if any(c.id == self.selected for c in self.active) else None
        self.selected = None
        self._fill_list()
        self.select(keep or (self.active[0].id if self.active else None))

    @property
    def active(self) -> list[Column]:
        return [c for c in self.columns if not c.removed]

    def col(self, cid: str | None = None) -> Column | None:
        cid = cid or self.selected
        return next((c for c in self.columns if c.id == cid), None)

    def column_rules(self, cid: str) -> list[Rule]:
        return [r for r in self.all_rules() if r.column_id == cid]

    def all_rules(self) -> list[Rule]:
        """The rules with one automatic type rule per Number / Date column (VR-7)."""
        return with_type_rules(self.columns, self.rules)

    def _fill_list(self) -> None:
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self.active))
            for r, c in enumerate(self.active):
                for i, text in enumerate((c.name, c.type, str(len(self.column_rules(c.id))), str(len(c.aliases)))):
                    item = QTableWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, c.id)
                    if i >= 2:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(r, i, item)
                cell = QWidget()
                cl = QHBoxLayout(cell)
                cl.setContentsMargins(0, 0, 4, 0)
                cl.setSpacing(0)
                up = icon_button("up", f"Move {c.name} up", cell, 26)
                down = icon_button("down", f"Move {c.name} down", cell, 26)
                up.setEnabled(r > 0)
                down.setEnabled(r < len(self.active) - 1)
                up.clicked.connect(lambda _c=False, cid=c.id: self.move(cid, -1))
                down.clicked.connect(lambda _c=False, cid=c.id: self.move(cid, 1))
                cl.addWidget(up)
                cl.addWidget(down)
                self.table.setCellWidget(r, 4, cell)
            ids = [c.id for c in self.active]
            if self.selected in ids:
                self.table.selectRow(ids.index(self.selected))

    def list_rows(self) -> list[tuple[str, str, str, str]]:
        return [tuple(self.table.item(r, i).text() for i in range(4)) for r in range(self.table.rowCount())]

    def _row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.select(self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def select(self, cid: str | None) -> None:
        self.selected = cid
        c = self.col(cid)
        self.detail.setEnabled(c is not None)
        if c is None:
            return
        ids = [x.id for x in self.active]
        with QSignalBlocker(self.table):
            self.table.selectRow(ids.index(cid))
        locked = cid in self.locked
        for w in (self.name, self.type, self.decimals, self.date_format, self.totals):
            w.blockSignals(True)
        self.name.setText(c.name)
        self.type.setCurrentIndex(TYPES.index(c.type))
        self.type.setEnabled(not locked)
        self.fixed.setVisible(locked)
        self.decimals.setValue(c.decimals if c.decimals is not None else DECIMALS_DEFAULT)
        self.decimals.setEnabled(not locked)
        self.date_format.setCurrentIndex(self.date_format.findData(c.date_format))
        self.totals.setChecked(c.totals_check)
        for w in (self.name, self.type, self.decimals, self.date_format, self.totals):
            w.blockSignals(False)
        for w in (self.decimals, self.decimals_label, self.totals, self.totals_label):
            w.setVisible(c.type == NUMBER)
        for w in (self.date_format, self.date_format_label):
            w.setVisible(c.type == DATE)
        if locked:
            tip = "Data has already been loaded with this type, so it can't change (TPL-9)."
            self.type.setToolTip(tip)
            self.decimals.setToolTip(tip)
        self.aliases.set_values(c.aliases)
        self.aliases.error.hide()
        self._fill_rules()

    def _fill_rules(self) -> None:
        c = self.col()
        rules = self.column_rules(c.id) if c else []
        self.rules_table.setRowCount(len(rules))
        head = f"Test on {self.tested_on}" if self.tested_on else "Test"
        self.rules_table.setHorizontalHeaderItem(3, QTableWidgetItem(head))
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
            n = self.tested.get(rule.id)
            test = QTableWidgetItem(fails_text(n))
            if n:
                test.setForeground(Qt.GlobalColor.darkRed if rule.severity == ERROR else Qt.GlobalColor.darkYellow)
            self.rules_table.setItem(r, 3, test)
            if not rule.automatic:
                rm = icon_button("close", f"Remove rule {rule.name}")
                rm.clicked.connect(lambda _c=False, rid=rule.id: self.remove_rule(rid))
                self.rules_table.setCellWidget(r, 4, rm)
            else:
                self.rules_table.removeCellWidget(r, 4)

    def rule_rows(self) -> list[tuple[str, str, str, str]]:
        out = []
        for r in range(self.rules_table.rowCount()):
            sev = self.rules_table.cellWidget(r, 2)
            out.append((self.rules_table.item(r, 0).text(), self.rules_table.item(r, 1).text(),
                        sev.currentText(), self.rules_table.item(r, 3).text()))
        return out

    # ------------------------------------------------------------------------------------------ column edits
    def _changed(self, relist: bool = True) -> None:
        self.set_dirty(True)
        if relist:
            self._fill_list()

    def _name_edited(self, text: str) -> None:
        self.col().name = text
        self._changed()

    def _type_changed(self, _i) -> None:
        c = self.col()
        new = self.type.currentData()
        if c is None or c.id in self.locked or new == c.type:
            return
        c.type = new
        c.decimals = DECIMALS_DEFAULT if new == NUMBER else None
        c.date_format = None
        if new != NUMBER:
            c.totals_check = False
        self.rules = [r for r in self.rules if r.automatic or r.column_id != c.id or new in ALLOWED_ON[r.type]]
        self._changed()
        self.select(c.id)

    def _decimals_changed(self, v: int) -> None:
        c = self.col()
        if c is not None and c.id not in self.locked and c.type == NUMBER:
            c.decimals = v
            self._changed(False)

    def _date_format_changed(self, _i) -> None:
        c = self.col()
        if c is not None and c.type == DATE:
            c.date_format = self.date_format.currentData()
            self._changed(False)

    def _totals_changed(self, on: bool) -> None:
        c = self.col()
        if c is not None:
            c.totals_check = bool(on) and c.type == NUMBER
            self._changed(False)

    def _alias_problem(self, text: str) -> str | None:
        key = norm(text)
        for c in self.active:
            if c.id == self.selected:
                continue
            if norm(c.name) == key or any(norm(a) == key for a in c.aliases):
                return f"{text} already maps to {c.name}."
        return None

    def _aliases_changed(self) -> None:
        self.col().aliases = list(self.aliases.values)
        self._changed()

    def move(self, cid: str, step: int) -> None:
        act = self.active
        ids = [c.id for c in act]
        i = ids.index(cid)
        j = i + step
        if not 0 <= j < len(act):
            return
        a, b = self.columns.index(act[i]), self.columns.index(act[j])
        self.columns[a], self.columns[b] = self.columns[b], self.columns[a]
        self._changed()

    def add_column(self) -> None:
        names = {c.name.casefold() for c in self.active}
        name, n = "New column", 2
        while name.casefold() in names:
            name, n = f"New column {n}", n + 1
        c = Column(next_column_id(self.columns), name, TEXT)
        self.columns.append(c)
        self._changed()
        self.select(c.id)
        self.name.setFocus()
        self.name.selectAll()

    def remove_selected(self) -> bool:
        """MAP-11, C4-15: refused while a default output uses the column (as saved)."""
        c = self.col()
        if c is None:
            return False
        users = outputs_using(self.template, c.id)
        if users:
            names = ", ".join(f"“{u}”" for u in users)
            self.show_error(f"{c.name} can't be removed while the default output {names} uses it. "
                            f"Change that output first.")
            return False
        if c.id in self.locked:
            c.removed = True                    # kept in older runs, hidden (MAP-11)
        else:
            self.columns.remove(c)
        self.rules = [r for r in self.rules if r.column_id != c.id]
        for r in self.rules:
            if r.type == UNIQUE and c.id in r.key_columns:
                keys = [k for k in r.key_columns if k != c.id]
                r.settings = {"columns": keys} if len(keys) > 1 else {}
        self.show_error("")
        self.selected = None
        self._changed()
        self.select(self.active[0].id if self.active else None)
        return True

    # ------------------------------------------------------------------------------------------ rules
    def rule_menu(self) -> QMenu:
        menu = QMenu(self)
        c = self.col()
        for t in rules_for_type(c.type) if c else []:
            menu.addAction(RULE_NAMES[t], lambda t=t: self.add_rule(t))
        self.menu = menu
        return menu

    def add_rule(self, rule_type: str, settings: dict | None = None) -> Rule | None:
        c = self.col()
        rule = Rule(next_rule_id(self.rules), c.id, rule_type, dict(settings or {}), ERROR)
        if settings is None and rule_type in NEEDS_SETTINGS:
            dlg = RuleDialog(rule, self.columns, self)
            self.dialog = dlg
            if dlg.exec() != RuleDialog.DialogCode.Accepted:
                return None
            rule = dlg.rule
        elif settings is not None:
            try:
                check_rule(rule, self.columns)
            except RuleError as e:
                self.show_error(str(e))
                return None
        self.rules.append(rule)
        self._changed()
        self._fill_rules()
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
            self._changed(False)
            self._fill_rules()

    def set_severity(self, rule_id: str, severity: str) -> None:
        rules = self.all_rules()
        rule = next(r for r in rules if r.id == rule_id)
        if rule.automatic and not any(r.id == rule_id for r in self.rules):
            self.rules.append(rule)             # keep the changed severity of an automatic rule
        rule = next(r for r in self.rules if r.id == rule_id)
        rule.severity = severity
        self._changed(False)

    def remove_rule(self, rule_id: str) -> None:
        self.rules = [r for r in self.rules if r.id != rule_id]
        self._changed()
        self._fill_rules()

    # ------------------------------------------------------------------------------------------ test (VR-8)
    def test_rules(self) -> None:
        if self.latest is None:
            return
        columns = copy.deepcopy(self.columns)
        rules = self.all_rules()
        latest = self.latest
        run_dir = latest.data.parent
        self.progress.show()

        def done(counts: dict[str, int]):
            self.progress.hide()
            self.tested = {r.id: counts.get(r.id, 0) for r in rules}
            self.tested_on = latest.label
            self.test_info.setText(f"Last tested on {latest.label} · {formats.count(latest.rows, 'row')} · "
                                   f"{formats.date_time(dt.datetime.now())}. {NOTHING_STORED}")
            self._fill_rules()

        def failed(e):
            self.progress.hide()
            from sankalan.ui.screens.common import error_text
            self.show_error(error_text(e))

        job = self.screen.start("Test rules", lambda ctx: manage.test_rules(ctx, run_dir, columns, rules), done,
                                failed, cancellable=True, on_cancelled=self.progress.hide)
        if job is not None:
            self.progress.bind(job)
        else:
            self.progress.hide()

    # ------------------------------------------------------------------------------------------ save
    def show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def check(self) -> str | None:
        seen: dict[str, str] = {}
        for c in self.active:
            name = c.name.strip()
            if not name:
                return "Every column needs a name."
            if name.casefold() in seen:
                return f"Two columns are named “{name}”. Use a different name for each."
            seen[name.casefold()] = name
        for rule in self.all_rules():
            try:
                check_rule(rule, self.columns)
            except RuleError as e:
                col = self.col(rule.column_id)
                return f"{rule.name} ({col.name if col else rule.column_id}): {e}"
        return None

    def apply(self, t: Template) -> None:
        cols = copy.deepcopy(self.columns)
        for c in cols:
            c.name = c.name.strip()
        t.columns = cols
        t.rules = with_type_rules(cols, self.rules)

