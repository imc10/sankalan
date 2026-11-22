"""6.2 New analysis and 6.3 a saved analysis (UX-10, ANA-1 to ANA-9, D32, D33; dialogs 7.7, 7.8; A0-02, A0-03,
A1-01 to A1-15).

Left, a 380 px settings panel: Data (client, template, the runs with Run ID and file names, Select all), then the
builder (AND filters, group levels, measures, Show subtotals), then Run. Right, the result: a summary line, Export
(.csv), the grid (first 100,000 rows, sortable, subtotal rows in medium weight) and the pinned grand total.

* A saved analysis opens locked: only the runs can be ticked, none are at first (D33). Duplicate to edit opens its
  settings as a new, unsaved analysis.
* Changing a setting greys the result with "Settings changed: Run again"; Cancel keeps the previous result, greyed.
* Changing the template clears the settings after a confirmation (ANA-3).
* Leaving a new analysis that has a result asks Save… / Leave without saving / Stay (7.7). Ad-hoc analyses are not
  kept when the user switches area (ANA-2).
* Rows view (6.4, Feature Spec A2 2): a Summary | Rows switch beside the title of a new analysis. Rows shows the
  same builder with filters only (group levels and measures are kept, hidden, and come back on Summary), a Columns
  section, and the Rows result (``ui/screens/rows_view.py``). Row views aren't saved: no Save, no leave prompt;
  leaving cancels a running Rows Job and drops the table (ROW-3).
"""
from __future__ import annotations

import datetime as dt
from functools import partial

from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QListWidget, QListWidgetItem, QMenu, QScrollArea,
                               QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import analyses, formats, rowsview
from sankalan.model import definition as d
from sankalan.model import export as ex
from sankalan.model.definition import Definition, DefinitionError
from sankalan.model.rowspec import RowSpec
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.dialogs.values_dialog import ValuesDialog
from sankalan.ui.screens.base import LeaveGuard
from sankalan.ui.screens.common import DataScreen, NameDialog, error_text
from sankalan.ui.screens.rows_view import ROWS, SUMMARY, ColumnsSection, ModeSwitch, RowsResult
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.breadcrumb import Crumb
from sankalan.ui.widgets.builder import DefinitionBuilder
from sankalan.ui.widgets.controls import heading, icon_button, note, panel, primary
from sankalan.ui.widgets.paged_grid import GridColumn, PagedGrid, PagedModel
from sankalan.ui.widgets.progress import ProgressPanel

SETTINGS_WIDTH = 380
NOT_SAVED = "Not saved"
NO_RUNS_TICKED = "No runs selected. Tick the runs to include."
LOCKED = "Settings are locked. Duplicate the analysis to change them."
STALE = "Settings changed: Run again"
CANCELLED = "Run cancelled. The result shown is from the previous run."
EMPTY_NEW = ("Choose runs, then press Run",
             "Pick a client, a template and the runs, add measures and press Run. The result can be exported as a "
             "CSV file.")
EMPTY_SAVED = ("Pick runs, then press Run",
               "This analysis reruns with its saved settings on the runs you tick. The result can be exported as a "
               "CSV file.")
SAVE_TEXT = ("Saved analyses keep their filters, groups and measures. Only the runs can be changed when you reopen "
             "one.")
TOTAL_BG = "#F3F8F7"
TOTAL_BORDER = "#D5E6E4"

# Tests replace this to drive the Save dialog opened from the leave prompt: ``fn(dialog) -> saved (bool)``.
save_hook = None


def runs_text(ticked: int, total: int) -> str:
    """"3 of 13 runs selected" (A1-01); none ticked: "No runs selected. Tick the runs to include."."""
    return NO_RUNS_TICKED if ticked == 0 else f"{ticked} of {formats.count(total, 'run')} selected"


def cap_note(count: int) -> str:
    return (f"Showing the first {formats.number(analyses.ROW_CAP)} of {formats.count(count, 'row')}. "
            "Export (.csv) writes every row.")


class SaveAnalysisDialog(NameDialog):
    """7.8: a name unique within the client's template."""

    def __init__(self, value: str, where: str, parent=None):
        super().__init__("Save analysis", "Name", value, "Save", parent)
        intro = QLabel(SAVE_TEXT, self)
        intro.setProperty("kind", "body")
        intro.setWordWrap(True)
        self.body.insertWidget(1, intro)
        hint = QLabel(f"Unique within {where}.", self)
        hint.setProperty("kind", "small")
        self.body.insertWidget(self.body.indexOf(self.edit) + 1, hint)


class AnalysisScreen(DataScreen):
    area = "analysis"
    title = analyses.NEW_NAME

    def __init__(self, window=None, parent=None, *, analysis_id: str | None = None, template_id: str | None = None,
                 definition: Definition | None = None, runs: list[str] | None = None):
        super().__init__(window, parent)
        self.analysis_id = analysis_id
        self.saved: analyses.Saved | None = None
        self.data: analyses.TemplateData | None = None
        self.outcome: analyses.Outcome | None = None
        self.stale = False
        self.mode = SUMMARY                         # or ROWS (6.4)
        self.rows_outcome: rowsview.RowsOutcome | None = None
        self.rows_stale = ""                        # "" or the note on a greyed Rows result
        self.choices: list[tuple] = []
        self.job = None
        self._initial = (template_id, definition, list(runs or []))
        self._template_id: str | None = None
        self._client_id: str | None = None
        self.values_dialog: ValuesDialog | None = None

        # ---------------------------------------------------------------------------------------- header
        self.badge = QLabel(NOT_SAVED, self)
        self.badge.setStyleSheet(f"font-size: {theme.SMALL_PX}px; padding: 2px 8px; border-radius: 10px; "
                                 f"background: {theme.DIVIDER}; color: {theme.MUTED_2};")
        self.title_row.insertWidget(1, self.badge)
        self.switch = ModeSwitch(self)
        self.switch.picked.connect(self.choose_view)
        self.title_row.insertWidget(2, self.switch)
        self.save_button = primary("Save…", self, "secondary")
        self.save_button.clicked.connect(lambda: self.save_dialog())
        self.actions.addWidget(self.save_button)
        self.duplicate_button = primary("Duplicate to edit", self, "secondary")
        self.duplicate_button.clicked.connect(self.duplicate)
        self.actions.addWidget(self.duplicate_button)
        self.more = icon_button("more", "More actions for this analysis", self, 36)
        self.more.clicked.connect(lambda: self.more_menu().popup(self.more.mapToGlobal(self.more.rect().bottomLeft())))
        self.actions.addWidget(self.more)

        body = QHBoxLayout()
        body.setSpacing(16)
        self.settings_box = self._settings_panel()
        body.addWidget(self.settings_box)
        self.modes = QStackedWidget(self)
        self.summary_panel = self._result_panel()
        self.modes.addWidget(self.summary_panel)
        self.rows_panel = panel(self)
        rpl = QVBoxLayout(self.rows_panel)
        rpl.setContentsMargins(0, 0, 0, 0)
        self.rows_result = RowsResult(self.bridge, self.rows_panel)
        self.rows_result.export_button.clicked.connect(self.export_rows)
        rpl.addWidget(self.rows_result)
        self.modes.addWidget(self.rows_panel)
        body.addWidget(self.modes, 1)
        self.content.addLayout(body, 1)
        self._set_mode()
        self._show_result()

    # -------------------------------------------------------------------------------------------- settings panel
    def _settings_panel(self) -> QFrame:
        box = panel(self)
        box.setFixedWidth(SETTINGS_WIDTH)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea(box)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget(scroll)
        lay = QVBoxLayout(inner)
        p = theme.PANEL_PADDING
        lay.setContentsMargins(p, p, p, p)
        lay.setSpacing(12)
        lay.addWidget(heading("Data", inner, theme.GRID_TEXT_PX))
        # client and template (new) or the locked line (saved)
        self.choose = QWidget(inner)
        cl = QHBoxLayout(self.choose)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        self.client = QComboBox(self.choose)
        self.client.setAccessibleName("Client")
        self.template = QComboBox(self.choose)
        self.template.setAccessibleName("Template")
        cl.addWidget(self.client, 1)
        cl.addWidget(self.template, 1)
        self.client.activated.connect(self._client_picked)
        self.template.activated.connect(self._template_picked)
        lay.addWidget(self.choose)
        self.data_label = QLabel("", inner)
        self.data_label.setProperty("kind", "body")
        self.data_label.setWordWrap(True)
        lay.addWidget(self.data_label)
        self.select_all = QCheckBox("Select all runs", inner)
        self.select_all.clicked.connect(self._select_all)
        lay.addWidget(self.select_all)
        self.runs = QListWidget(inner)
        self.runs.setAccessibleName("Runs")
        self.runs.setFixedHeight(5 * 32 + 4)
        self.runs.setStyleSheet(f"QListWidget {{ border: 1px solid {theme.BORDER}; border-radius: 6px; }}"
                                f"QListWidget::item {{ height: 32px; }}")
        self.runs.itemChanged.connect(self._run_ticked)
        lay.addWidget(self.runs)
        self.runs_note = note("", inner)
        lay.addWidget(self.runs_note)
        self.runs_error = note("", inner, "error")          # Rows view: "Tick at least one run" (2.4)
        self.runs_error.hide()
        lay.addWidget(self.runs_error)
        sep = QFrame(inner)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {theme.DIVIDER};")
        lay.addWidget(sep)
        # builder (new) or locked settings (saved)
        self.settings = QStackedWidget(inner)
        self.builder = DefinitionBuilder([], parent=self.settings, picker=self.pick_values)
        self.builder.changed.connect(self._settings_changed)
        self.settings.addWidget(self.builder)
        self.locked = QWidget(self.settings)
        ll = QVBoxLayout(self.locked)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)
        self.locked_note = note(LOCKED, self.locked)
        ll.addWidget(self.locked_note)
        self.locked_grid = QGridLayout()
        self.locked_grid.setHorizontalSpacing(16)
        self.locked_grid.setVerticalSpacing(10)
        ll.addLayout(self.locked_grid)
        ll.addStretch(1)
        self.settings.addWidget(self.locked)
        lay.addWidget(self.settings)
        self.columns_section = ColumnsSection(inner)          # Rows view (ROW-7, ROW-8)
        self.columns_section.columns_changed.connect(self._rows_columns_changed)
        self.columns_section.hide()
        lay.addWidget(self.columns_section)
        lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        foot = QWidget(box)
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(p, 8, p, p)
        fl.setSpacing(8)
        self.error = note("", foot, "error")
        self.error.hide()
        fl.addWidget(self.error)
        row = QHBoxLayout()
        row.addStretch(1)
        self.run_button = primary("Run", foot)
        self.run_button.clicked.connect(self.run)
        row.addWidget(self.run_button)
        fl.addLayout(row)
        outer.addWidget(foot)
        if self.bridge is not None:
            self.bridge.guard(self.run_button, False)
            for b in self.switch.buttons.values():
                self.bridge.guard(b)
        return box

    # -------------------------------------------------------------------------------------------- result panel
    def _result_panel(self) -> QFrame:
        box = panel(self)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget(box)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 12, 10)
        bl.setSpacing(12)
        self.summary = QLabel("", bar)
        self.summary.setStyleSheet(f"font-size: {theme.SMALL_PX}px; color: {theme.SUBTLE};")
        bl.addWidget(self.summary, 1)
        self.stale_note = QLabel(STALE, bar)
        self.stale_note.setStyleSheet(f"font-size: {theme.SMALL_PX}px; color: {theme.WARNING}; font-weight: 500;")
        self.stale_note.hide()
        bl.addWidget(self.stale_note)
        self.export_button = primary("Export (.csv)", bar, "secondary")
        self.export_button.clicked.connect(self.export)
        bl.addWidget(self.export_button)
        lay.addWidget(bar)
        self.progress = ProgressPanel(box)
        self.progress.setContentsMargins(16, 0, 16, 12)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.result_stack = QStackedWidget(box)
        # empty state
        self.empty = QWidget(self.result_stack)
        el = QVBoxLayout(self.empty)
        el.setContentsMargins(32, 0, 32, 0)
        el.setSpacing(8)
        el.addStretch(1)
        self.empty_title = QLabel("", self.empty)
        self.empty_title.setStyleSheet(f"font-size: 15px; font-weight: 500; color: {theme.TEXT};")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        el.addWidget(self.empty_title)
        self.empty_text = QLabel("", self.empty)
        self.empty_text.setProperty("kind", "subtitle")
        self.empty_text.setWordWrap(True)
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        el.addWidget(self.empty_text)
        el.addStretch(2)
        self.result_stack.addWidget(self.empty)
        # grid, pinned total, cap note
        self.result_page = QWidget(self.result_stack)
        rl = QVBoxLayout(self.result_page)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.model = PagedModel(self.bridge, [], None, parent=self) if self.bridge is not None else None
        self.grid = PagedGrid(self.model, self.result_page) if self.model is not None else QWidget(self.result_page)
        if isinstance(self.grid, PagedGrid):
            self.grid.setFrameShape(QFrame.Shape.NoFrame)
            self.grid.horizontalHeader().sectionResized.connect(self._sync_total)
            self.grid.horizontalHeader().rename_requested.connect(self._rename_requested)
            self.model.emphasis = lambda row: bool(self.outcome) and row[-1] < self.outcome.result.levels
        rl.addWidget(self.grid, 1)
        self.total = QTableWidget(1, 0, self.result_page)
        self.total.setAccessibleName("Grand total")
        self.total.horizontalHeader().hide()
        self.total.verticalHeader().hide()
        self.total.setFixedHeight(theme.ROW_HEIGHT)
        self.total.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.total.setShowGrid(False)
        self.total.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.total.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.total.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.total.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.total.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.total.setStyleSheet(f"QTableWidget {{ background: {TOTAL_BG}; border: 0; "
                                 f"border-top: 1px solid {TOTAL_BORDER}; }}")
        rl.addWidget(self.total)
        self.cap = note("", self.result_page)
        self.cap.setContentsMargins(16, 6, 16, 6)
        self.cap.hide()
        rl.addWidget(self.cap)
        self.result_stack.addWidget(self.result_page)
        self.dim = QGraphicsOpacityEffect(self.result_page)
        self.dim.setOpacity(1.0)
        self.result_page.setGraphicsEffect(self.dim)
        lay.addWidget(self.result_stack, 1)
        if self.bridge is not None:
            self.bridge.guard(self.export_button, False)
        return box

    # -------------------------------------------------------------------------------------------- navigation
    def crumbs(self) -> list[Crumb]:
        return [Crumb("Analyses", lambda: self.window_.open_area("analysis")),
                Crumb(self.saved.name if self.saved else analyses.NEW_NAME)]

    def leave_guard(self) -> LeaveGuard | None:
        """7.7: a new analysis with a result that isn't saved. Row views aren't saved: no prompt (ROW-3)."""
        if self.saved is not None or self.outcome is None or self.mode == ROWS:
            return None
        return LeaveGuard.unsaved_analysis(self._save_before_leaving)

    def closing(self) -> None:
        if self.values_dialog is not None:
            self.values_dialog.reject()
        drops = []
        if self.job is not None:                # ROW-3: leaving cancels a running Run (it drops its new table)
            if not self.job.cancel():
                self.job.wait(5)                # it had already finished: drop what it made
                drops.append(self._made(self.job.result))
            self.job = None
        drops += [self.outcome.result if self.outcome is not None else None, self.rows_outcome]
        drops = [r for r in drops if r is not None]
        if drops and self.window_ is not None:
            self.window_.drop_results(drops)
        self.outcome = self.rows_outcome = None
        super().closing()

    @staticmethod
    def _made(result):
        """The temporary table a finished Run made: an analysis result or a Rows result."""
        if isinstance(result, analyses.Outcome):
            return result.result
        return result if isinstance(result, rowsview.RowsOutcome) else None

    # -------------------------------------------------------------------------------------------- loading
    def shown(self) -> None:
        if self.storage is None:
            return
        if self.analysis_id is not None:
            self.load("Read analysis", lambda ctx: analyses.open_saved(ctx, self.analysis_id), self._saved_loaded)
        else:
            self.load("Read templates", analyses.template_choices, self._choices_loaded)

    def _saved_loaded(self, saved: analyses.Saved) -> None:
        self.saved = saved
        self._template_id = saved.data.template.id
        self._data_ready(saved.data, None, [])

    def _choices_loaded(self, choices: list[tuple]) -> None:
        self.choices = choices
        tid, defn, runs = self._initial
        client = next((c[0] for c in choices if c[2] == tid), None)
        self._fill_clients(client)
        self._fill_templates(client, tid)
        if tid is not None and client is not None:
            self._load_template(tid, defn, runs)

    def _fill_clients(self, current: str | None) -> None:
        with QSignalBlocker(self.client):
            self.client.clear()
            self.client.addItem("Choose a client", None)
            seen = []
            for cid, cname, _tid, _tname in self.choices:
                if cid not in seen:
                    seen.append(cid)
                    self.client.addItem(cname, cid)
            i = self.client.findData(current)
            self.client.setCurrentIndex(i if i >= 0 else 0)
        self._client_id = current

    def _fill_templates(self, client_id: str | None, current: str | None) -> None:
        with QSignalBlocker(self.template):
            self.template.clear()
            self.template.addItem("Choose a template", None)
            for cid, _cname, tid, tname in self.choices:
                if cid == client_id:
                    self.template.addItem(tname, tid)
            i = self.template.findData(current)
            self.template.setCurrentIndex(i if i >= 0 else 0)
        self.template.setEnabled(client_id is not None)
        self._template_id = current if self.template.currentData() == current else None

    def _load_template(self, template_id: str, definition: Definition | None = None,
                       runs: list[str] | None = None) -> None:
        self._template_id = template_id
        self.load("Read template", lambda ctx: analyses.template_data(ctx, template_id),
                  lambda data: self._data_ready(data, definition, runs or []))

    def _data_ready(self, data: analyses.TemplateData, definition: Definition | None, runs: list[str]) -> None:
        if data.template.id != self._template_id:
            return                              # the user picked another template meanwhile
        self.data = data
        with QSignalBlocker(self.runs):
            self.runs.clear()
            for r in data.runs:
                it = QListWidgetItem(f"{r.label}    {r.text}", self.runs)
                it.setData(Qt.ItemDataRole.UserRole, r.id)
                it.setToolTip(r.text)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Checked if r.id in runs else Qt.CheckState.Unchecked)
        if self.saved is None:
            defn = definition or Definition(data.template.id)
            defn.template_id = data.template.id
            self.builder.set_definition(defn, data.columns)
            self.columns_section.set_columns(data.columns)
        self._set_mode()
        self._runs_changed()
        self._show_result()

    # -------------------------------------------------------------------------------------------- mode and state
    def _set_mode(self) -> None:
        saved = self.saved is not None
        rows = self.mode == ROWS and not saved
        self.set_title(self.saved.name if saved else analyses.NEW_NAME)
        self.badge.setText(f"Saved {formats.date(self.saved.saved_on.date())}" if saved else
                           rowsview.HEADER_NOTE if rows else NOT_SAVED)
        self.switch.setVisible(not saved)                       # ROW-4
        self.switch.set_mode(self.mode)
        self.save_button.setVisible(not saved and not rows)     # ROW-3
        self.columns_section.setVisible(rows)
        self.builder.set_sections(groups=not rows, measures=not rows, subtotals=not rows)
        self.modes.setCurrentWidget(self.rows_panel if rows else self.summary_panel)
        self.duplicate_button.setVisible(saved)
        self.more.setVisible(saved)
        self.choose.setVisible(not saved)
        self.data_label.setVisible(saved)
        if saved:
            t = self.saved.data
            self.data_label.setText(f"{t.client_name} · {t.template.name}")
            self._fill_locked()
            self.settings.setCurrentWidget(self.locked)
        else:
            self.settings.setCurrentWidget(self.builder)
        self.builder.setEnabled(self.data is not None)
        self.refresh_crumbs()
        self._update_buttons()

    def _fill_locked(self) -> None:
        while self.locked_grid.count():
            w = self.locked_grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        lines = analyses.describe(self.saved.definition, self.saved.data.columns)
        for r, (label, values) in enumerate(lines.items()):
            k = QLabel(label, self.locked)
            k.setStyleSheet(f"font-size: {theme.SMALL_PX}px; font-weight: 500; color: {theme.MUTED};")
            v = QLabel("\n".join(values), self.locked)
            v.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; color: {theme.TEXT};")
            v.setWordWrap(True)
            v.setTextFormat(Qt.TextFormat.PlainText)
            self.locked_grid.addWidget(k, r, 0, Qt.AlignmentFlag.AlignTop)
            self.locked_grid.addWidget(v, r, 1)
        self.locked_grid.setColumnStretch(1, 1)

    def locked_lines(self) -> dict[str, str]:
        """The locked settings as shown (tests)."""
        out = {}
        for r in range(self.locked_grid.rowCount()):
            k, v = self.locked_grid.itemAtPosition(r, 0), self.locked_grid.itemAtPosition(r, 1)
            if k is not None and v is not None:
                out[k.widget().text()] = v.widget().text()
        return out

    def ticked_runs(self) -> list[str]:
        return [self.runs.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.runs.count())
                if self.runs.item(i).checkState() == Qt.CheckState.Checked]

    def tick(self, labels: list[str] | str, on: bool = True) -> None:
        """Tick runs by Run ID (tests and keyboard users alike see the same list)."""
        labels = [labels] if isinstance(labels, str) else labels
        for i in range(self.runs.count()):
            it = self.runs.item(i)
            if it.text().split()[0] in labels:
                it.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _select_all(self, on: bool) -> None:
        with QSignalBlocker(self.runs):
            for i in range(self.runs.count()):
                self.runs.item(i).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self._runs_changed()

    def _run_ticked(self, _item) -> None:
        self._runs_changed()

    def _runs_changed(self) -> None:
        n, total = len(self.ticked_runs()), self.runs.count()
        with QSignalBlocker(self.select_all):
            self.select_all.setChecked(total > 0 and n == total)
        self.select_all.setEnabled(total > 0)
        self.runs_note.setText(runs_text(n, total) if self.data is not None else "")
        if n:
            self.set_runs_error("")
        self._mark_stale()
        self._update_buttons()

    def _settings_changed(self) -> None:
        self.set_error("")
        self._mark_stale()

    def _mark_stale(self) -> None:
        if self.mode == ROWS:                   # ROW-9: client, template, runs or filters
            if self.rows_outcome is not None and self.rows_stale != STALE and self.job is None:
                self.rows_stale = STALE
                self._show_rows()
            return
        if self.outcome is not None and not self.stale and self.job is None:
            self.stale = True
            self.stale_note.setText(STALE)
            self._show_result()

    def _update_buttons(self) -> None:
        if self.bridge is None:
            return
        if self.mode == ROWS and self.saved is None:    # Run is clickable with no runs ticked: it says why (2.4)
            self.bridge.set_allowed(self.run_button, self.data is not None)
            self.bridge.set_allowed(self.rows_result.export_button, self._rows_exportable(),
                                    "Run again to export." if self.rows_stale else "")
            return
        self.bridge.set_allowed(self.run_button, self.data is not None and bool(self.ticked_runs()))
        self.bridge.set_allowed(self.export_button, self.outcome is not None and not self.stale,
                                "" if self.outcome is None or not self.stale else "Run again to export.")
        self.save_button.setEnabled(self.data is not None)

    def set_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def set_runs_error(self, text: str) -> None:
        self.runs_error.setText(text)
        self.runs_error.setVisible(bool(text))

    # -------------------------------------------------------------------------------------------- template change
    def _has_settings(self) -> bool:
        b = self.builder
        return bool(b.filters.rows or b.groups.rows or b.measures.cards or self.ticked_runs() or self.outcome
                    or self.rows_outcome)

    def _confirm_clear(self) -> bool:
        if not self._has_settings():
            return True
        key = ask(self, "Change template?", "The filters, groups, measures and ticked runs are cleared.",
                  [("cancel", "Cancel", None), ("change", "Change template", "primary")])
        return key == "change"

    def _client_picked(self, _i: int) -> None:
        cid = self.client.currentData()
        if cid == self._client_id:
            return
        if self._template_id is not None and not self._confirm_clear():
            with QSignalBlocker(self.client):
                self.client.setCurrentIndex(self.client.findData(self._client_id))
            return
        self._clear()
        self._fill_clients(cid)
        self._fill_templates(cid, None)

    def _template_picked(self, _i: int) -> None:
        tid = self.template.currentData()
        if tid == self._template_id:
            return
        if self._template_id is not None and not self._confirm_clear():
            with QSignalBlocker(self.template):
                self.template.setCurrentIndex(self.template.findData(self._template_id))
            return
        self._clear()
        if tid is not None:
            self._load_template(tid)
        else:
            self._template_id = None

    def choose_template(self, client_name: str, template_name: str) -> None:
        """Pick a client and a template by name, as the combo boxes do."""
        self.client.setCurrentIndex(self.client.findText(client_name))
        self._client_picked(self.client.currentIndex())
        i = self.template.findText(template_name)
        if i >= 0 and self.template.currentIndex() != i:
            self.template.setCurrentIndex(i)
            self._template_picked(i)

    def _clear(self) -> None:
        """ANA-3: settings, runs and result cleared."""
        self.data = None
        self._template_id = None
        with QSignalBlocker(self.builder):
            self.builder.clear()
            self.builder.subtotals.setChecked(False)
        with QSignalBlocker(self.runs):
            self.runs.clear()
        drops = [r for r in (self.outcome.result if self.outcome is not None else None, self.rows_outcome)
                 if r is not None]
        if drops:                                       # a template change drops the Rows table too (8.7)
            self.window_.drop_results(drops)
        self.outcome = self.rows_outcome = None
        self.stale = False
        self.rows_stale = ""
        self.columns_section.set_columns([])
        self.set_error("")
        self.set_runs_error("")
        self._set_mode()
        self._runs_changed()
        self._show_result()

    # -------------------------------------------------------------------------------------------- values picker
    def pick_values(self, row) -> ValuesDialog | None:
        """ANA-4 Is one of: the most frequent values in the ticked runs, with a search."""
        if self.data is None:
            return None
        run_ids = self.ticked_runs()
        if not run_ids:
            self.set_error("Tick the runs to read values from.")
            return None
        template, column = self.data.template, row.col

        def read(search, on_done, on_failed, on_cancelled):
            return self.start("Read values", lambda ctx: analyses.distinct_values(
                ctx, self.folder, template, column.id, run_ids, search), on_done, on_failed, cancellable=True,
                on_cancelled=on_cancelled)

        dlg = ValuesDialog(column.name, row.picked, read, self)
        dlg.accepted.connect(lambda: row.set_picked(dlg.chosen))
        dlg.finished.connect(lambda _r: setattr(self, "values_dialog", None))
        self.values_dialog = dlg
        dlg.open()
        dlg.start_read()
        return dlg

    # -------------------------------------------------------------------------------------------- run
    def definition(self) -> Definition:
        if self.saved is not None:
            return self.saved.definition
        defn = self.builder.definition()
        defn.template_id = self.data.template.id
        return defn

    def run(self) -> bool:
        """ANA-8: progress and Cancel; the previous result stays (greyed) until the new one is ready."""
        if self.mode == ROWS and self.saved is None:
            return self.run_rows()
        self.set_error("")
        if self.data is None:
            self.set_error("Choose a client and a template.")
            return False
        run_ids = self.ticked_runs()
        if not run_ids:
            self.set_error(analyses.NO_RUNS)
            return False
        if self.saved is None and self.builder.problem() is not None:     # under its section (Tech spec A2 9.2)
            return False
        try:
            defn = self.definition()
            d.check(defn, self.data.columns)
        except DefinitionError as e:
            self.set_error(str(e))
            return False
        drop = ([self.outcome.result] if self.outcome is not None else []) + list(self.window_.pending_drops)
        template, folder = self.data.template, self.folder

        def done(outcome: analyses.Outcome) -> None:
            self.window_.pending_drops = [r for r in self.window_.pending_drops if r not in drop]
            self.job = None
            self.outcome = outcome
            self.stale = False
            self._show_outcome()

        def cancelled() -> None:
            if not self.alive:
                return
            self.job = None
            if self.outcome is not None:
                self.stale = True
                self.stale_note.setText(CANCELLED)
            self._show_result()

        def failed(error) -> None:
            self.job = None
            self.set_error(error_text(error))
            self._show_result()

        job = self.start("Run analysis", lambda ctx: analyses.run(ctx, folder, defn, template, run_ids, drop),
                         done, failed, cancellable=True, on_cancelled=cancelled)
        if job is None:
            return False
        self.job = job
        self.progress.bind(job)
        self._show_result()
        return True

    def _show_outcome(self) -> None:
        o = self.outcome
        cols = []
        for c in o.result.columns:
            cols.append(GridColumn(c.name, c.label, right=c.role == "measure"))
        if self.model is not None:
            self.model.set_columns(cols, analyses.ResultSource(o))
            hover = [c.hover for c in o.result.columns]
            self.grid.horizontalHeader().set_tooltips(lambda s: hover[s] if s < len(hover) else None)
            self.grid.apply_widths()
            self.grid.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            self.grid._sorted = None
        cells = analyses.total_cells(o)
        self.total.setColumnCount(len(cells))
        for i, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setFont(theme.font(theme.GRID_TEXT_PX, medium=True))
            right = i >= o.result.levels
            item.setTextAlignment((Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft)
                                  | Qt.AlignmentFlag.AlignVCenter)
            self.total.setItem(0, i, item)
        self.total.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        QTimer.singleShot(0, self._sync_total)
        self._sync_total()
        self.total.setVisible(bool(o.result.measures))          # no measures, no grand total (MEA-11, T39)
        self.summary.setText(o.summary())
        self.cap.setText(cap_note(o.count))
        self.cap.setVisible(o.capped)
        self._show_result()

    def _sync_total(self, *_args) -> None:
        if not isinstance(self.grid, PagedGrid):
            return
        hh = self.grid.horizontalHeader()
        for i in range(min(self.total.columnCount(), hh.count())):
            self.total.setColumnWidth(i, hh.sectionSize(i))

    def _show_result(self) -> None:
        if self.mode == ROWS and self.saved is None:
            self._show_rows()
            return
        running = self.job is not None
        self.progress.setVisible(running)
        if self.outcome is None:
            title, text = EMPTY_SAVED if self.saved is not None else EMPTY_NEW
            self.empty_title.setText(title)
            self.empty_text.setText(text)
            self.result_stack.setCurrentWidget(self.empty)
            self.summary.setText("")
        else:
            self.result_stack.setCurrentWidget(self.result_page)
        greyed = self.outcome is not None and (self.stale or running)
        self.dim.setOpacity(0.4 if greyed else 1.0)
        if isinstance(self.grid, PagedGrid):
            # ✎ on the measure columns of an unsaved, current result (MEA-8)
            o = self.outcome
            ok = o is not None and self.saved is None and not greyed
            self.grid.horizontalHeader().set_renamable(
                (lambda s: s >= o.result.levels and s < len(o.result.columns)) if ok else None)
        self.stale_note.setVisible(self.outcome is not None and self.stale and not running)
        self.export_button.setVisible(True)
        self._update_buttons()

    def _rename_requested(self, section: int, text: str) -> None:
        """MEA-8: Enter in the header's box. A clash keeps the box open; a rename never runs again or greys."""
        o, hh = self.outcome, self.grid.horizontalHeader()
        if o is None or self.data is None:
            hh.finish()
            return
        name = d.clean_name(text)
        problem = analyses.measure_name_problem(o, section, name)
        if problem:
            hh.show_error(problem)
            return
        self.builder.rename(section - o.result.levels, name)
        self.model.set_titles(analyses.rename_measure(o, section, name, self.data.columns))
        hh.finish()

    @property
    def greyed(self) -> bool:
        return self.dim.opacity() < 1.0

    def result_rows(self) -> list[tuple]:
        """The rows loaded in the grid, as shown (tests)."""
        if self.model is None:
            return []
        out = []
        for r in range(self.model.rowCount()):
            v = self.model.row_values(r)
            out.append(None if v is None else tuple(v[:-1]))
        return out

    def total_row(self) -> list[str]:
        return [self.total.item(0, i).text() for i in range(self.total.columnCount())]

    # -------------------------------------------------------------------------------------------- Rows view (6.4)
    def choose_view(self, mode: str) -> bool:
        """ROW-1, ROW-2: Summary | Rows. Client, template, ticked runs and filters stay; the result is cleared; the
        group levels and measures stay in the builder (hidden in Rows) and come back on Summary."""
        if self.saved is not None or mode == self.mode or self.job is not None:
            self.switch.set_mode(self.mode)
            return False
        drops = [r for r in (self.outcome.result if self.outcome is not None else None, self.rows_outcome)
                 if r is not None]
        if drops:                               # the Rows table is dropped on a switch to Summary (8.7)
            self.window_.drop_results(drops)
        self.outcome = self.rows_outcome = None
        self.stale = False
        self.rows_stale = ""
        self.set_error("")
        self.set_runs_error("")
        self.columns_section.set_error("")
        self.mode = mode
        self._set_mode()
        self._show_result()
        return True

    def run_rows(self) -> bool:
        """ROW-9, ROW-10, ROW-11: count, then fetch the first 100,000, as one Job with Cancel. Runs and columns are
        checked first, each message under its own list (2.4); the previous result stays greyed while it runs."""
        self.set_error("")
        self.set_runs_error("")
        self.columns_section.set_error("")
        if self.data is None:
            self.set_error("Choose a client and a template.")
            return False
        run_ids = self.ticked_runs()
        columns = self.columns_section.ticked()
        if not run_ids:
            self.set_runs_error(rowsview.NO_RUNS)
        if not columns:
            self.columns_section.set_error(rowsview.NO_COLUMNS)
        if not run_ids or not columns:
            return False
        try:
            filters = self.builder.definition().filters
        except DefinitionError as e:
            self.set_error(str(e))
            return False
        spec = RowSpec(self.data.template.id, filters, columns, self.columns_section.source)
        drop = ([self.rows_outcome] if self.rows_outcome is not None else []) + list(self.window_.pending_drops)
        template, folder = self.data.template, self.folder

        def done(outcome: rowsview.RowsOutcome) -> None:
            self.window_.pending_drops = [r for r in self.window_.pending_drops if r not in drop]
            self.job = None
            self.rows_outcome = outcome
            self.rows_stale = ""
            self.rows_result.show_outcome(outcome, self.columns_section.ticked(), self.columns_section.source)
            self._show_rows()

        def cancelled() -> None:
            if not self.alive:
                return
            self.job = None
            if self.rows_outcome is not None:
                self.rows_stale = rowsview.CANCELLED
            self._show_rows()

        def failed(error) -> None:
            self.job = None
            self.set_error(error_text(error))
            self._show_rows()

        job = self.start(rowsview.OPERATION, lambda ctx: rowsview.run(ctx, folder, template, spec, run_ids, drop),
                         done, failed, cancellable=True, on_cancelled=cancelled)
        if job is None:
            return False
        self.job = job
        self.rows_result.progress.bind(job)
        self._show_rows()
        return True

    def _rows_columns_changed(self) -> None:
        """ROW-9: ticks, order and Show them on screen redraw the grid from the rows already read: no Job, no
        greying."""
        o = self.rows_outcome
        if o is not None:
            ticked = self.columns_section.ticked()
            if not ticked:
                self.columns_section.set_error(rowsview.NO_COLUMNS)
            self.rows_result.set_columns(o, ticked, self.columns_section.source)
        self._show_rows()

    def _rows_exportable(self) -> bool:
        o = self.rows_outcome
        return (o is not None and not self.rows_stale and self.job is None and o.match > 0
                and bool(self.columns_section.ticked()))

    def _show_rows(self) -> None:
        """Feature Spec A2 2.4: before the first Run, running, no matches, no columns, cancelled, changed."""
        r, o = self.rows_result, self.rows_outcome
        running = self.job is not None
        r.progress.setVisible(running)
        if o is None:
            r.summary.setText("")
            r.show_message(rowsview.EMPTY)
        elif o.match == 0:
            r.show_message(rowsview.NO_MATCH)
        elif not self.columns_section.ticked():
            r.show_message(rowsview.NO_COLUMNS)
        else:
            r.show_grid()
        r.export_button.setVisible(o is None or o.match > 0)          # no matches: Export rows isn't offered
        r.set_greyed(o is not None and (bool(self.rows_stale) or running),
                     self.rows_stale if o is not None and not running else "")
        self._update_buttons()

    def rows_shown(self) -> list[tuple | None]:
        """The Rows grid's loaded rows, as shown (tests)."""
        return self.rows_result.shown_rows()

    def export_rows_request(self) -> ex.ExportRequest | None:
        """Export rows (7.9): every match in stored order with the columns ticked now."""
        o = self.rows_outcome
        if o is None or self.data is None or not self._rows_exportable():
            return None
        ticked = self.columns_section.ticked()
        t, client = self.data.template, self.data.client_name
        return ex.prefill_rows(t.export, template_id=t.id, client=client, template=t.name, rows=o.match,
                               items=rowsview.export_items(o, ticked), context=rowsview.context(o, client, t.name),
                               details=rowsview.describe(o, ticked))

    def export_rows(self) -> bool:
        req = self.export_rows_request()
        return req is not None and self.window_.go("export", request=req)

    # -------------------------------------------------------------------------------------------- export (ANA-9)
    def export_request(self) -> ex.ExportRequest | None:
        o = self.outcome
        if o is None or self.data is None:
            return None
        key, asc = (self.model.sort_spec[0] if self.model is not None and self.model.sort_spec else (None, True))
        name = self.saved.name if self.saved is not None else "Analysis"
        t = self.data.template
        return ex.prefill("analysis", t.export, template_id=t.id, client=self.data.client_name, template=t.name,
                          output=name, items=analyses.export_items(o, key, not asc),
                          rows=o.count + (1 if o.total is not None else 0))

    def export(self) -> bool:
        req = self.export_request()
        return req is not None and self.window_.go("export", request=req)

    # -------------------------------------------------------------------------------------------- save (7.8)
    def save_dialog(self, modal: bool = False) -> SaveAnalysisDialog | None:
        if self.data is None or self.saved is not None:
            return None
        if self.builder.problem() is not None:
            return None
        try:
            defn = self.definition()
            d.check(defn, self.data.columns)
        except DefinitionError as e:
            self.set_error(str(e))
            return None
        where = f"{self.data.client_name} · {self.data.template.name}"
        dlg = SaveAnalysisDialog("", where, self)
        template = self.data.template

        def save():
            dlg.set_error("")
            dlg.save.setEnabled(False)

            def done(aid):
                name = dlg.edit.text().strip()
                dlg.accept()
                self._became_saved(aid, name, defn)

            def failed(error):
                dlg.save.setEnabled(True)
                dlg.set_error(error_text(error))
            self.start("Save analysis", lambda ctx: analyses.save(ctx, template, dlg.edit.text(), defn), done, failed)
        dlg.save.clicked.connect(save)
        dlg.finished.connect(lambda _r: setattr(self, "dialog", None))
        self.dialog = dlg
        if not modal:
            dlg.open()
        return dlg

    def _save_before_leaving(self) -> bool:
        """Save… in 7.7: leave once the analysis is saved; Cancel in the Save dialog stays."""
        dlg = self.save_dialog(modal=True)
        if dlg is None:
            return False
        if save_hook is not None:
            return bool(save_hook(dlg))
        return dlg.exec() == NameDialog.DialogCode.Accepted

    def _became_saved(self, aid: str, name: str, defn: Definition) -> None:
        self.analysis_id = aid
        self.saved = analyses.Saved(aid, name, dt.datetime.now(), defn, self.data)
        self._set_mode()
        self._show_result()
        self.show_banner(Banner("success", f"“{name}” saved."))

    # -------------------------------------------------------------------------------------------- saved: actions
    def duplicate(self) -> bool:
        """ANA-1: the settings in a new, editable, unsaved analysis; the ticked runs come along."""
        if self.saved is None:
            return False
        return self.window_.go("analysis", template_id=self.saved.data.template.id,
                               definition=Definition.from_dict(self.saved.definition.to_dict()),
                               runs=self.ticked_runs())

    def more_menu(self) -> QMenu:
        menu = QMenu(self)
        rename = menu.addAction("Rename", self.rename)
        delete = menu.addAction("Delete", self.delete)
        for a in (rename, delete):
            a.setEnabled(self.bridge is not None and not self.bridge.busy)
        self.menu = menu
        return menu

    def rename(self) -> None:
        s = self.saved

        def renamed(name):
            s.name = name
            self._set_mode()
        self.ask_name("Rename analysis", "Name", s.name, lambda new: (lambda ctx: analyses.rename(ctx, s.id, new)),
                      "Rename analysis", renamed)

    def delete(self) -> None:
        s = self.saved
        key = ask(self, f"Delete “{s.name}”?", "The saved analysis is removed. Runs and their data don't change.",
                  [("cancel", "Cancel", None), ("delete", "Delete", "destructive")])
        if key != "delete":
            return
        banner = partial(Banner, "success", f"“{s.name}” deleted.")
        self.start("Delete analysis", lambda ctx: analyses.delete(ctx, s.id),
                   lambda _r: self.window_.open_screen(self.window_.factories["analysis"](self.window_),
                                                       banner=banner()))
