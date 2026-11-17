"""4.3 Validate, 4.4 Outputs and 4.5 Commit of the New run wizard (RUN-3 to RUN-6, RUN-13, ISS-1 to ISS-3, VR-3 to
VR-6, DO-2 to DO-7, T18, T20, T22). The wizard frame is ``new_run.NewRunScreen``."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import formats, runs
from sankalan.model import definition as d
from sankalan.model import export as ex
from sankalan.model.rule import ERROR, WARNING
from sankalan.query import export as qx
from sankalan.run import pipeline as pl
from sankalan.ui import theme
from sankalan.ui.dialogs.run_dialogs import EditRulesDialog, LimitedText, OverrideDialog
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.builder import OP_LABELS
from sankalan.ui.widgets.controls import heading, note, panel, primary
from sankalan.ui.widgets.paged_grid import INTEGER, TEXT, GridColumn, PagedGrid, PagedModel
from sankalan.ui.widgets.result_table import ResultTable

if TYPE_CHECKING:
    from sankalan.ui.screens.new_run import NewRunScreen

ISSUE_COLUMNS = [
    GridColumn("file", "File", TEXT, width=180, tooltip=7),
    GridColumn("sheet", "Sheet", TEXT, width=110, tooltip=7),
    GridColumn("row", "Row", INTEGER, width=80, tooltip=7),
    GridColumn("column", "Column", TEXT, width=130, tooltip=7),
    GridColumn("value", "Value", TEXT, width=120, tooltip=7),
    GridColumn("rule", "Rule", TEXT, tooltip=7),
    GridColumn("severity", "Severity", TEXT, width=90, tooltip=7,
               colour=lambda v: theme.ERROR if v == ERROR else theme.OVERRIDE_TEXT),
]


def tile(title: str, parent=None) -> tuple[QFrame, QLabel]:
    box = panel(parent)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(2)
    lay.addWidget(note(title, box))
    value = QLabel("–", box)
    value.setStyleSheet(f"font-size: 20px; font-weight: 500; color: {theme.TEXT};")
    lay.addWidget(value)
    return box, value


def hidden_summary(rows: int, sheets: list[str]) -> str:
    """"25 rows and 1 sheet (Old)", "0" (RUNV-01, RUNV-02)."""
    parts = []
    if rows:
        parts.append(formats.count(rows, "row"))
    if sheets:
        parts.append(f"{formats.count(len(sheets), 'sheet')} ({', '.join(sheets)})")
    return " and ".join(parts) if parts else "0"


class ByRuleTable(QTableWidget):
    """Rule and column · Severity · Count (ISS-1). Clicking a row filters the issue grid to that rule."""

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.lines: list[runs.RuleLine] = []
        self.setHorizontalHeaderLabels(["Rule and column", "Severity", "Count"])
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, w in ((1, 84), (2, 76)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            hh.resizeSection(i, w)

    def set_lines(self, lines: list[runs.RuleLine]) -> None:
        self.lines = list(lines)
        self.blockSignals(True)
        self.clearSelection()
        self.setRowCount(len(lines))
        for r, ln in enumerate(lines):
            name = QTableWidgetItem(f"{ln.rule} · {ln.column}")
            name.setToolTip(name.text())
            sev = QTableWidgetItem(ln.severity)
            sev.setForeground(QBrush(QColor(theme.ERROR if ln.severity == ERROR else theme.OVERRIDE_TEXT)))
            count = QTableWidgetItem(formats.number(ln.count))
            count.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for c, it in enumerate((name, sev, count)):
                self.setItem(r, c, it)
        self.blockSignals(False)

    def rows(self) -> list[tuple[str, str, int]]:
        return [(f"{ln.rule} · {ln.column}", ln.severity, ln.count) for ln in self.lines]


class IssuesView(QWidget):
    """The by-rule table, the issue grid (first 10,000 per rule, filters, sort) and Export issue list. Shared by
    the Validate step (4.3) and the Run screen's Issues tab (5.1)."""

    def __init__(self, screen, parent=None, *, edit_rules: bool = False):
        super().__init__(parent)
        self.screen = screen
        self.source: runs.IssueSource | None = None
        self.passed = 0
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(8)
        self.by_rule = ByRuleTable(self)
        self.by_rule.setFixedWidth(360)
        self.by_rule.itemSelectionChanged.connect(self._rule_picked)
        left.addWidget(self.by_rule, 1)
        self.passed_note = note("", self)
        self.passed_note.setWordWrap(True)
        self.passed_note.setFixedWidth(360)
        left.addWidget(self.passed_note)
        self.edit_rules_button = primary("Edit rules for this run", self, "secondary")
        self.edit_rules_button.setVisible(edit_rules)
        screen.bridge.guard(self.edit_rules_button)
        left.addWidget(self.edit_rules_button)
        self.export_button = primary("Export issue list (.csv)", self, "secondary")
        screen.bridge.guard(self.export_button)
        left.addWidget(self.export_button)
        lay.addLayout(left)
        right = QVBoxLayout()
        right.setSpacing(8)
        bar = QHBoxLayout()
        self.filter_note = heading("", self, theme.GRID_TEXT_PX)
        bar.addWidget(self.filter_note, 1)
        self.severity = QComboBox(self)
        self.severity.setAccessibleName("Severity")
        for label, key in (("All severities", None), ("Errors", ERROR), ("Warnings", WARNING)):
            self.severity.addItem(label, key)
        self.severity.currentIndexChanged.connect(lambda _i: self.refresh())
        bar.addWidget(self.severity)
        self.show_all = QPushButton("Show all rules", self)
        self.show_all.setProperty("kind", "plain")
        self.show_all.clicked.connect(lambda: self.by_rule.clearSelection())
        bar.addWidget(self.show_all)
        right.addLayout(bar)
        self.model = PagedModel(screen.bridge, ISSUE_COLUMNS, None, parent=self)
        self.grid = PagedGrid(self.model, self)
        right.addWidget(self.grid, 1)
        self.limit_note = note("", self)
        self.limit_note.setWordWrap(True)
        right.addWidget(self.limit_note)
        lay.addLayout(right, 1)

    def set_issues(self, issues, file_names: dict[int, str], column_names: dict[str, str],
                   lines: list[runs.RuleLine], passed: int | None = None) -> None:
        self.source = runs.IssueSource(issues, file_names, column_names)
        self.by_rule.set_lines(lines)
        self.passed = passed or 0
        self.passed_note.setText(f"{formats.count(passed, 'other rule')} passed on every row."
                                 if passed else ("No issues." if not lines else ""))
        self.passed_note.setVisible(bool(self.passed_note.text()))
        self.refresh()

    def clear(self) -> None:
        self.source = None
        self.by_rule.set_lines([])
        self.model.set_source(None)
        self.filter_note.setText("")
        self.limit_note.setText("")
        self.passed_note.setText("")

    @property
    def rule(self) -> runs.RuleLine | None:
        rows = self.by_rule.selectionModel().selectedRows() if self.by_rule.selectionModel() else []
        return self.by_rule.lines[rows[0].row()] if rows else None

    def _rule_picked(self) -> None:
        self.refresh()

    def pick_rule(self, rule_id: str | None) -> None:
        if rule_id is None:
            self.by_rule.clearSelection()
            return
        ids = [ln.rule_id for ln in self.by_rule.lines]
        self.by_rule.selectRow(ids.index(rule_id))

    def set_severity(self, severity: str | None) -> None:
        self.severity.setCurrentIndex(self.severity.findData(severity))

    def refresh(self) -> None:
        if self.source is None:
            return
        rule = self.rule
        self.source.rule_id = rule.rule_id if rule else None
        self.source.severity = self.severity.currentData()
        self.model.set_source(self.source)
        cap = runs.qv.GRID_PER_RULE
        if rule is not None:
            how = f"showing all {formats.number(rule.count)}" if rule.count <= cap else \
                f"showing the first {formats.number(cap)} of {formats.number(rule.count)}"
            self.filter_note.setText(f"{rule.rule} · {rule.column} · {how}")
        else:
            total = sum(ln.count for ln in self.by_rule.lines)
            self.filter_note.setText(f"All rules · {formats.count(total, 'issue')}" if total else "No issues")
        over = [ln for ln in self.by_rule.lines if ln.count > cap and (rule is None or ln is rule)]
        self.limit_note.setText(
            f"The grid shows the first {formats.number(cap)} issues of each rule. Export issue list has all of "
            "them." if over else "")

    def grid_rows(self, qtbot=None) -> list:
        return [self.model.row_values(r) for r in range(self.model.rowCount())]


# ---------------------------------------------------------------------------------------------- 4.3 Validate
class ValidateStep(QWidget):
    def __init__(self, wizard: "NewRunScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        self.dialog = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.banner_slot = QVBoxLayout()
        lay.addLayout(self.banner_slot)
        self.result_banner: Banner | None = None
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tiles: dict[str, QLabel] = {}
        for key, title in (("errors", "Errors"), ("warnings", "Warnings"), ("rows", "Rows read"),
                           ("hidden", "Hidden data skipped")):
            box, value = tile(title, self)
            tiles.addWidget(box, 2 if key == "hidden" else 1)
            self.tiles[key] = value
        lay.addLayout(tiles)
        self.issues = IssuesView(wizard, self, edit_rules=True)
        self.issues.edit_rules_button.clicked.connect(self.edit_rules)
        self.issues.export_button.clicked.connect(self.export_issues)
        lay.addWidget(self.issues, 1)

    def clear(self) -> None:
        if self.result_banner is not None:
            self.result_banner.dismiss()
            self.result_banner = None
        for v in self.tiles.values():
            v.setText("–")
        self.issues.clear()

    def show_failure(self, text: str) -> None:
        self.clear()
        self.result_banner = Banner("error", text, closable=False, parent=self)
        self.banner_slot.addWidget(self.result_banner)

    def load(self) -> None:
        self.clear()
        sess = self.wizard.session
        v = sess.validation
        if v is None:
            return
        sc = v.scan
        files_with_errors = len({c.file_index for c in sc.counts if c.errors})
        if v.errors:
            text = (f"{formats.count(v.errors, 'error')} in {formats.count(files_with_errors, 'file')}. Fix the "
                    "source file and re-check, or continue with a reason. Warnings don't stop the run.")
            kind = "error"
        elif v.warnings:
            text = f"No errors. {formats.count(v.warnings, 'warning')} don't stop the run."
            kind = "warning"
        else:
            text = f"No errors or warnings. {formats.count(v.rows_to_load, 'row')} ready to load."
            kind = "success"
        self.result_banner = Banner(kind, text, closable=False, auto_hide=False, parent=self)
        self.banner_slot.addWidget(self.result_banner)
        self.tiles["errors"].setText(formats.number(v.errors))
        self.tiles["warnings"].setText(formats.number(v.warnings))
        self.tiles["rows"].setText(formats.number(v.rows_read))
        self.tiles["hidden"].setText(hidden_summary(v.hidden_rows, v.hidden_sheets))
        if v.blank_rows:
            self.tiles["rows"].setToolTip(f"{formats.count(v.blank_rows, 'blank row')} left out")
        lines, passed = runs.rule_lines(sc.rules, sc.by_rule, sess.columns)
        names = {p.file_index: Path(p.path).name for p in sess._parts}
        self.issues.set_issues(sc.issues, names, {c.id: c.name for c in sess.columns}, lines, passed)

    def tile_values(self) -> dict[str, str]:
        return {k: v.text() for k, v in self.tiles.items()}

    def footer_text(self) -> str:
        v = self.wizard.session.validation if self.wizard.session else None
        if v is None:
            return "Checking the files…" if self.wizard.job is not None else ""
        if v.errors:
            return "Fix the errors and re-check, or continue with a reason"
        return f"{formats.count(v.rows_to_load, 'row')} will load"

    # ------------------------------------------------------------------------------------------ actions
    def edit_rules(self) -> EditRulesDialog | None:
        """VR-5: change rules for this run; only the rule check runs again (RUNV-09). Save to template makes it a
        new template version (RUNV-10)."""
        wz = self.wizard
        sess = wz.session
        if sess is None or sess.validation is None or wz.job is not None:
            return None
        dlg = EditRulesDialog(sess.columns, sess.rules, sess.validation.scan.by_rule, sess.validation.rows_to_load,
                              self)
        self.dialog = dlg

        def accepted():
            self.dialog = None
            rules, save = dlg.result_rules, dlg.save_to_template.isChecked()
            wz.run("Check rules", lambda ctx: sess.edit_rules(ctx, rules, save_to_template=save),
                   lambda _v: self.load(), on_failed=lambda e: self._edit_failed(e))
            if save:
                wz.show_banner(Banner("success", "Rule changes saved to the template."))

        dlg.accepted.connect(accepted)
        dlg.rejected.connect(lambda: setattr(self, "dialog", None))
        dlg.open()
        return dlg

    def _edit_failed(self, error) -> None:
        from sankalan.ui.screens.new_run import plain_error
        self.wizard.show_banner(Banner("error", plain_error(error)))
        self.load()

    def export_issues(self) -> bool:
        """RUNV-07: the full issue list as CSV, before commit (ISS-3)."""
        wz = self.wizard
        sess = wz.session
        if sess is None or sess.validation is None or wz.start_info is None:
            return False
        issues = sess.validation.scan.issues
        names = {p.file_index: Path(p.path).name for p in sess._parts}
        col_names = {c.id: c.name for c in sess.columns}
        info = wz.start_info
        req = ex.prefill("issues", info.template.export, template_id=info.template.id, client=info.client_name,
                         template=info.template.name, run_label=wz.run_label)
        req = ex.ExportRequest(**{**req.__dict__, "items": lambda _ctx: [(qx.issue_list(issues, names, col_names),
                                                                           req.file_name)]})
        return wz.window_.go("export", request=req)


def open_override(wz: "NewRunScreen") -> OverrideDialog | None:
    """7.1 Continue despite errors… (RUN-4, T18, RUNV-13)."""
    sess = wz.session
    if sess is None or sess.validation is None or sess.validation.passed or wz.job is not None:
        return None
    v = sess.validation
    dlg = OverrideDialog(v.errors, v.left_out_on_override, wz.run_label, wz)
    wz.dialog = dlg

    def accepted():
        wz.dialog = None
        wz.leave_validate(dlg.value)

    dlg.accepted.connect(accepted)
    dlg.rejected.connect(lambda: setattr(wz, "dialog", None))
    dlg.open()
    return dlg


# ---------------------------------------------------------------------------------------------- 4.4 Outputs
def filters_text(definition: dict, columns) -> str:
    """"Invoice Date is latest month in this run · Invoice Type is one of B2B, B2CL"."""
    names = {c.id: c.name for c in columns}
    parts = []
    for f in definition.get("filters") or []:
        op = OP_LABELS.get(f["op"], f["op"])
        if f["op"] in d.RELATIVE:
            op = "is " + op
        values = ", ".join(str(v) for v in f.get("values") or [] if v not in (None, ""))
        parts.append(" ".join(x for x in (names.get(f["column_id"], f["column_id"]), op, values) if x))
    return " · ".join(parts)


OUTPUTS_STEP = 3                    # new_run.OUTPUTS (not imported: new_run imports this module)
STATUS_TEXT = {pl.PENDING: "Waiting", pl.RUNNING: "Generating…", pl.DONE: "Done", pl.FAILED: "Failed",
               pl.CANCELLED: "Cancelled"}


class OutputsStep(QWidget):
    """4.4: each default output generated on this run's rows (DO-2, DO-4) with its status; Cancel marks it and
    those not started for Retry (DO-5). No export before commit (DO-7, RUNO-02)."""

    def __init__(self, wizard: "NewRunScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        self.selected = 0
        self.times: dict[int, float] = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(8)
        self.list_box = QWidget(self)
        self.list_box.setFixedWidth(280)
        self.list_lay = QVBoxLayout(self.list_box)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(8)
        left.addWidget(self.list_box)
        self.retry_button = primary("Retry", self, "secondary")
        self.retry_button.clicked.connect(self.generate)
        wizard.bridge.guard(self.retry_button)
        left.addWidget(self.retry_button)
        left.addStretch(1)
        lay.addLayout(left)
        right = QVBoxLayout()
        right.setSpacing(8)
        head = QHBoxLayout()
        self.title = heading("", self, theme.BODY_PX)
        head.addWidget(self.title, 1)
        self.no_export = note("Export is available after commit", self)
        self.no_export.setWordWrap(False)
        head.addWidget(self.no_export)
        self.subtotals = QCheckBox("Show subtotals", self)
        self.subtotals.toggled.connect(lambda _on: self.show_selected())
        head.addWidget(self.subtotals)
        right.addLayout(head)
        self.filters = note("", self)
        right.addWidget(self.filters)
        self.info = note("", self)
        right.addWidget(self.info)
        self.table = ResultTable(self)
        right.addWidget(self.table, 1)
        lay.addLayout(right, 1)
        self.buttons: list[QPushButton] = []

    @property
    def outputs(self) -> list[pl.OutputState]:
        return self.wizard.session.outputs if self.wizard.session else []

    def load(self) -> None:
        for b in self.buttons:
            b.hide()
            b.setParent(None)
            b.deleteLater()
        self.buttons = []
        for i, o in enumerate(self.outputs):
            b = QPushButton(self.list_box)
            b.setCheckable(True)
            b.setChecked(i == self.selected)
            b.setStyleSheet(f"QPushButton {{ text-align: left; padding: 8px 12px; min-height: 48px; "
                            f"border: 1px solid {theme.INPUT_BORDER}; border-radius: 8px; background: {theme.WHITE}; }}"
                            f"QPushButton:checked {{ border-color: {theme.TEAL}; background: {theme.TINT}; "
                            f"color: {theme.TEAL_DARK}; }}")
            b.setText(self.item_text(i))
            b.setMinimumHeight(56)
            b.clicked.connect(lambda _c=False, i=i: self.select(i))
            self.list_lay.addWidget(b)
            self.buttons.append(b)
        retry = any(o.status in (pl.CANCELLED, pl.FAILED) for o in self.outputs)
        self.retry_button.setVisible(retry and self.wizard.job is None)
        self.show_selected()

    def item_text(self, i: int) -> str:
        o = self.outputs[i]
        status = STATUS_TEXT[o.status]
        if o.status == pl.DONE and i in self.times:
            status = f"Done · {self.times[i]:.1f} s"
        if o.status in (pl.CANCELLED, pl.FAILED):
            status += " · Retry"
        return f"{o.name}\n{status}"

    def statuses(self) -> list[tuple[str, str]]:
        return [(o.name, o.status) for o in self.outputs]

    def select(self, i: int) -> None:
        self.selected = i
        for j, b in enumerate(self.buttons):
            b.setChecked(j == i)
        o = self.outputs[i] if 0 <= i < len(self.outputs) else None
        if o is not None:
            self.subtotals.blockSignals(True)
            self.subtotals.setChecked(bool(o.definition.get("subtotals")))
            self.subtotals.blockSignals(False)
        self.show_selected()

    def show_selected(self) -> None:
        self.table.clear_result()
        outs = self.outputs
        if not (0 <= self.selected < len(outs)):
            self.title.setText("")
            self.filters.setText("")
            self.info.setText("")
            return
        o = outs[self.selected]
        sess = self.wizard.session
        self.title.setText(o.name)
        self.filters.setText(filters_text(o.definition, sess.columns))
        self.filters.setVisible(bool(self.filters.text()))
        if o.status != pl.DONE:
            self.info.setText({pl.CANCELLED: "Cancelled. Retry to generate it.",
                               pl.FAILED: "This output couldn't be generated. Retry."}.get(o.status, "Waiting…"))
            return
        path, cols, sub = sess.staging.path / o.file, sess.columns, self.subtotals.isChecked()
        rows_in = sess.validation.rows_to_load if sess.validation else 0

        def done(p):
            if self.wizard.step != OUTPUTS_STEP or self.outputs[self.selected] is not o:
                return
            self.table.show_result(p)
            text = f"On this run's {formats.count(rows_in, 'row')} · {formats.count(p.count, 'group')}"
            if p.note:
                text += f" · {p.note}"
            self.info.setText(text)

        self.wizard.load("Read output", lambda ctx: runs.stored_output(ctx, o.definition, cols, path, subtotals=sub),
                         done)

    def generate(self) -> bool:
        """Generate every output not yet done (DO-4); Retry after a cancel or failure (DO-5, RUNO-06)."""
        import time
        wz = self.wizard
        sess = wz.session
        if sess is None or wz.job is not None or sess.outputs_done:
            return False
        started = time.monotonic()
        pending = [i for i, o in enumerate(sess.outputs) if o.status != pl.DONE]

        def done(_outs):
            per = (time.monotonic() - started) / max(1, len(pending))
            for i in pending:
                self.times[i] = per
            self.load()

        def stopped(error=None):
            self.load()
            if error is not None:
                from sankalan.ui.screens.new_run import plain_error
                wz.show_banner(Banner("error", plain_error(error)))

        self.load()
        job = wz.run("Generate outputs", sess.run_outputs, done, on_cancelled=stopped, on_failed=stopped)
        self.load()
        return job is not None

    def footer_text(self) -> str:
        sess = self.wizard.session
        if sess is None:
            return ""
        outs = sess.outputs
        if sess.outputs_done:
            return f"All {formats.count(len(outs), 'output')} generated" if len(outs) > 1 else "Output generated"
        if any(o.status in (pl.CANCELLED, pl.FAILED) for o in outs):
            return "Retry the outputs that didn't finish to continue"
        return "Generating outputs…"


# ---------------------------------------------------------------------------------------------- 4.5 Commit
class CommitStep(QWidget):
    def __init__(self, wizard: "NewRunScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        left = panel(scroll)
        self.summary_lay = QVBoxLayout(left)
        self.summary_lay.setContentsMargins(16, 14, 16, 14)
        self.summary_lay.setSpacing(8)
        scroll.setWidget(left)
        scroll.setFixedWidth(460)
        lay.addWidget(scroll)
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(heading("Totals check", self, theme.BODY_PX))
        self.totals_state = note("", self)
        right.addWidget(self.totals_state)
        self.totals = QTableWidget(0, 4, self)
        self.totals.setHorizontalHeaderLabels(["Column", "In the files", "Loaded", "Left out"])
        self.totals.verticalHeader().hide()
        self.totals.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.totals.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.totals.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.totals.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.totals.setShowGrid(False)
        self.totals.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.totals.setMaximumHeight(theme.ROW_HEIGHT * 6)
        right.addWidget(self.totals)
        self.comment_label = heading("Comment · optional", self, theme.GRID_TEXT_PX)
        right.addWidget(self.comment_label)
        self.comment = LimitedText(pl.COMMENT_MAX, self)
        self.comment.setAccessibleName("Comment")
        self.comment.setFixedHeight(96)
        self.comment.textChanged.connect(self._comment_changed)
        right.addWidget(self.comment)
        line = QHBoxLayout()
        line.addWidget(note("Comments can't be edited after the run is committed.", self), 1)
        self.counter = note("0 / 500", self)
        line.addWidget(self.counter)
        right.addLayout(line)
        self.blockers = note("", self, "error")
        self.blockers.setWordWrap(True)
        right.addWidget(self.blockers)
        right.addStretch(1)
        lay.addLayout(right, 1)
        self._loaded_for = None

    def _comment_changed(self) -> None:
        self.counter.setText(self.comment.counter())
        self.wizard.update_footer()

    def _row(self, label: str, value: str) -> None:
        line = QHBoxLayout()
        a = note(label, self)
        b = QLabel(value, self)
        b.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; color: {theme.TEXT};")
        b.setWordWrap(True)
        line.addWidget(a)
        line.addStretch(1)
        line.addWidget(b)
        self.summary_lay.addLayout(line)
        self.summary[label] = value

    def load(self) -> None:
        wz = self.wizard
        sess = wz.session
        while self.summary_lay.count():
            item = self.summary_lay.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)
                item.widget().deleteLater()
            elif item.layout():
                lay = item.layout()
                while lay.count():
                    w = lay.takeAt(0).widget()
                    if w is not None:
                        w.hide()
                        w.setParent(None)
                        w.deleteLater()
        self.summary: dict[str, str] = {}
        self.summary_lay.addWidget(heading(f"{wz.run_label} · what will be committed", self, theme.BODY_PX))
        v = sess.validation
        files = sess.readable_files
        self._row("Files and sheets", f"{formats.count(len({f.path for f in files}), 'file')} · "
                                      f"{formats.count(len(files), 'sheet')}")
        self._row("Rows to load", formats.number(v.rows_to_load - (v.left_out_on_override if sess.override_reason
                                                                   is not None else 0)))
        err = formats.number(v.errors) + (" · continued with a reason" if sess.override_reason is not None else "")
        self._row("Errors", err)
        self._row("Warnings", formats.number(v.warnings))
        self._row("Default outputs", "Skipped: this template has none" if sess.outputs_skipped else
                  f"{formats.number(len(sess.outputs))} generated")
        lines = runs.mapping_lines(sess._mapping_result.decisions if sess._mapping_result else [])
        lines += runs.rule_change_lines(sess.saved_rule_changes, sess.columns, True)
        from sankalan.model.rule import rule_changes
        lines += runs.rule_change_lines(rule_changes(sess.template.rules, sess.rules), sess.columns, False)
        self.decisions = lines
        if lines:
            self.summary_lay.addSpacing(6)
            self.summary_lay.addWidget(heading("Decisions in this run", self, theme.GRID_TEXT_PX))
            for ln in lines:
                lab = note(ln, self)
                lab.setWordWrap(True)
                self.summary_lay.addWidget(lab)
        self.summary_lay.addStretch(1)
        if sess.override_reason is not None:
            self.comment_label.setText("Comment · required because errors were overridden")
        else:
            self.comment_label.setText("Comment · optional")
        if self._loaded_for is not sess.validation:      # prefill once per pass through Validate (RUNC-06)
            self._loaded_for = sess.validation
            self.comment.setPlainText(sess.comment_prefill)
        self.totals.setRowCount(0)
        self.totals_state.setText("Checking totals…")
        wz.run("Check totals", sess.check_totals, lambda _t: self.show_totals(), progress=False)

    def show_totals(self) -> None:
        sess = self.wizard.session
        lines = sess.totals or []
        self.totals.setRowCount(len(lines))
        self.totals.setFixedHeight(theme.ROW_HEIGHT * (len(lines) + 1) + 2)
        for r, t in enumerate(lines):
            values = [t.name, formats.number(t.input, t.decimals), formats.number(t.loaded, t.decimals),
                      formats.number(t.left_out, t.decimals)]
            for c, text in enumerate(values):
                it = QTableWidgetItem(text)
                if c:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if not t.passed:
                    it.setForeground(QBrush(QColor(theme.ERROR)))
                self.totals.setItem(r, c, it)
        if not lines:
            self.totals_state.setText("No column is ticked for the totals check.")
        elif sess.totals_passed:
            self.totals_state.setText("All totals match: In the files = Loaded + Left out.")
            self.totals_state.setStyleSheet(f"color: {theme.SUCCESS};")
        else:
            names = ", ".join(t.name for t in lines if not t.passed)
            self.totals_state.setText(f"Totals don't match for {names}. This run can't be committed.")
            self.totals_state.setStyleSheet(f"color: {theme.ERROR};")
        self.wizard.update_footer()

    def totals_rows(self) -> list[list[str]]:
        return [[self.totals.item(r, c).text() for c in range(4)] for r in range(self.totals.rowCount())]

    def blocker_list(self) -> list[str]:
        sess = self.wizard.session
        if sess is None or self.wizard.job is not None:
            return ["…"]
        return sess.commit_blockers(self.comment.toPlainText(), free_bytes=self.free_bytes())

    def free_bytes(self) -> int | None:
        return getattr(self.wizard, "free_bytes_for_commit", None)

    def can_commit(self) -> bool:
        return not self.blocker_list()

    def footer_text(self) -> str:
        if self.wizard.job is not None:
            return "Checking totals…"
        blockers = self.blocker_list()
        shown = [b for b in blockers if b != "…"]
        self.blockers.setText(" ".join(shown[1:]) if len(shown) > 1 else "")
        return shown[0] if shown else "Data and outputs are saved together"


def commit_run(wz: "NewRunScreen") -> bool:
    """Commit (RUN-5, T8, T22): not cancellable; then the Run screen opens with a success banner (RUNC-05)."""
    sess = wz.session
    if sess is None or wz.job is not None or not wz.commit_step.can_commit():
        return False
    comment = wz.commit_step.comment.toPlainText()
    free = wz.commit_step.free_bytes()
    template_id, name = wz.template_id, wz.template_name

    def done(c: pl.Committed):
        wz.finished = True
        n_out = len(sess.outputs)
        v = sess.validation
        loaded = v.rows_to_load - (v.left_out_on_override if sess.override_reason is not None else 0)
        text = f"{c.label} committed: {formats.count(loaded, 'row')}"
        text += f" and {formats.count(n_out, 'output')} saved." if n_out else " saved."
        wz.window_.go("run", run_id=c.run_id, template_id=template_id, name=name, banner=Banner("success", text))

    return wz.run("Commit", lambda ctx: sess.commit(ctx, comment, free_bytes=free), done, cancellable=False) is not None
