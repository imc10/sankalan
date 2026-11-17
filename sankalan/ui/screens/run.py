"""5.1 Run (UX-9, RUN-2, RUN-9, RUN-12, RUN-13, ISS-4, DO-6, DO-7, T19; C6-01 to C6-10).

A committed run: header with the Run ID, its status badge and a summary line; Export data and a ⋯ menu (Export
issue list, Export left-out rows, Delete run); tabs Summary · Issues · Outputs · Source files. Saved outputs are
read back as stored, never recalculated (DO-6). The comment is read-only (RUN-13).
"""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QMenu,
                               QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import formats, manage, runs
from sankalan.model import export as ex
from sankalan.model.run import STATUS_OVERRIDE
from sankalan.ui import theme
from sankalan.ui.screens.common import DataScreen
from sankalan.ui.screens.new_run_steps import IssuesView, filters_text
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.breadcrumb import Crumb
from sankalan.ui.widgets.controls import CountTabs, heading, icon_button, note, panel, primary
from sankalan.ui.widgets.result_table import ResultTable

SUMMARY, ISSUES, OUTPUTS, SOURCES = range(4)
TAB_LABELS = ["Summary", "Issues", "Outputs", "Source files"]


def status_badge(status: str) -> str:
    return "Committed with override" if status == STATUS_OVERRIDE else "Committed"


def header_line(run: dict) -> str:
    """"Loaded 16-11-2026 18:36 · 4 files · 8 sheets · 9,344,350 rows · 2 errors · 23 warnings" (C6-01)."""
    files = run["files"]
    return (f"Loaded {formats.date_time(run['loaded_on'])} · "
            f"{formats.count(len({f['path'] for f in files}), 'file')} · {formats.count(len(files), 'sheet')} · "
            f"{formats.count(run['rows_loaded'], 'row')} · {formats.count(run['errors'], 'error')} · "
            f"{formats.count(run['warnings'], 'warning')}")


def summary_figures(view: runs.RunView) -> list[tuple[str, str]]:
    """The Summary tab's figures (RUN-12, C6-02, C6-03)."""
    run = view.run
    by = run["left_out_by_reason"] or {}
    files = run["files"]
    hidden_rows = sum(f["hidden_rows"] or 0 for f in files)
    hidden_sheets = sorted({s for f in files for s in f["sheets_skipped"] or []})
    errors = formats.number(run["errors"])
    if run["status"] == STATUS_OVERRIDE:
        errors += " (continued with a reason)"
    hidden = []
    if hidden_rows:
        hidden.append(formats.count(hidden_rows, "hidden row"))
    if hidden_sheets:
        hidden.append(f"hidden sheet{'s' if len(hidden_sheets) > 1 else ''} {', '.join(hidden_sheets)}")
    return [
        ("Committed on", formats.date_time(run["loaded_on"])),
        ("Files and sheets read", f"{formats.count(len({f['path'] for f in files}), 'file')} · "
                                  f"{formats.count(len(files), 'sheet')}"),
        ("Rows read", formats.number(run["rows_read"])),
        ("Rows loaded", formats.number(run["rows_loaded"])),
        ("Rows left out", f"{formats.number(run['rows_left_out'])} (rows with errors "
                          f"{formats.number(by.get('errors', 0))}, later duplicates "
                          f"{formats.number(by.get('duplicates', 0))}, blank rows {formats.number(by.get('blank', 0))})"),
        ("Errors", errors),
        ("Warnings", formats.number(run["warnings"])),
        ("Hidden data skipped", " and ".join(hidden) if hidden else "None"),
        ("Default outputs saved", formats.number(len(run["outputs"]))),
    ]


def decision_lines(view: runs.RunView) -> list[str]:
    ch = view.run["run_changes"] or {}
    cols = view.template.columns
    lines = runs.mapping_lines(ch.get("mapping") or [])
    lines += runs.rule_change_lines(ch.get("rules_saved") or [], cols, True)
    run_only = runs.rule_change_lines(ch.get("rules_run_only") or [], cols, False)
    lines += run_only or ["No rule changes for this run only"]
    return lines


def _table(headers: list[str], parent=None) -> QTableWidget:
    t = QTableWidget(0, len(headers), parent)
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
    t.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setShowGrid(False)
    return t


def _fill(t: QTableWidget, rows: list[list[str]], right: set[int] = frozenset()) -> None:
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            it = QTableWidgetItem(text)
            if c in right:
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            t.setItem(r, c, it)


def table_rows(t: QTableWidget) -> list[list[str]]:
    return [[t.item(r, c).text() if t.item(r, c) else "" for c in range(t.columnCount())] for r in range(t.rowCount())]


class SummaryTab(QWidget):
    def __init__(self, screen: "RunScreen"):
        super().__init__(screen)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(heading("Totals check", self, theme.BODY_PX))
        self.totals_state = note("", self)
        left.addWidget(self.totals_state)
        self.totals = _table(["Column", "In the files", "Loaded", "Left out"], self)
        self.totals.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.totals.setMaximumHeight(theme.ROW_HEIGHT * 5)
        left.addWidget(self.totals)
        self.comment_label = heading("Comment", self, theme.GRID_TEXT_PX)
        left.addWidget(self.comment_label)
        self.comment = QPlainTextEdit(self)
        self.comment.setReadOnly(True)              # RUN-13, C6-08
        self.comment.setAccessibleName("Comment")
        self.comment.setFixedHeight(88)
        left.addWidget(self.comment)
        self.committed = note("", self)
        left.addWidget(self.committed)
        left.addStretch(1)
        lay.addLayout(left, 1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        box = panel(scroll)
        self.right = QVBoxLayout(box)
        self.right.setContentsMargins(16, 14, 16, 14)
        self.right.setSpacing(8)
        scroll.setWidget(box)
        scroll.setFixedWidth(460)
        lay.addWidget(scroll)
        self.figures: list[tuple[str, str]] = []
        self.decisions: list[str] = []

    def load(self, view: runs.RunView) -> None:
        run = view.run
        totals = list((run["totals"] or {}).values())
        _fill(self.totals, [[t["name"], formats.number(_dec(t["input"]), t["decimals"]),
                             formats.number(_dec(t["loaded"]), t["decimals"]),
                             formats.number(_dec(t["left_out"]), t["decimals"])] for t in totals], {1, 2, 3})
        self.totals.setFixedHeight(theme.ROW_HEIGHT * (len(totals) + 1) + 2)
        self.totals_state.setText("All totals matched: In the files = Loaded + Left out." if totals else
                                  "No column was ticked for the totals check.")
        if run["status"] == STATUS_OVERRIDE:
            self.comment_label.setText(f"Comment · reason for continuing despite "
                                       f"{formats.count(run['errors'], 'error')}")
        else:
            self.comment_label.setText("Comment")
        self.comment.setPlainText(run["comment"] or "")
        self.committed.setText(f"Committed on {formats.date_time(run['loaded_on'])}")
        while self.right.count():
            w = self.right.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.figures = summary_figures(view)
        for label, value in self.figures:
            row = QWidget(self)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.addWidget(note(label, row))
            rl.addStretch(1)
            v = QLabel(value, row)
            v.setWordWrap(True)
            v.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; color: {theme.TEXT};")
            rl.addWidget(v)
            self.right.addWidget(row)
        self.right.addSpacing(8)
        self.right.addWidget(heading("Decisions in this run", self, theme.GRID_TEXT_PX))
        self.decisions = decision_lines(view)
        for line in self.decisions:
            lab = note(line, self)
            lab.setWordWrap(True)
            self.right.addWidget(lab)
        self.right.addStretch(1)


def _dec(text):
    from decimal import Decimal
    return Decimal(text)


class OutputsTab(QWidget):
    def __init__(self, screen: "RunScreen"):
        super().__init__(screen)
        self.screen = screen
        self.selected = 0
        self.view: runs.RunView | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)
        self.list_box = QWidget(self)
        self.list_box.setFixedWidth(260)
        self.list_lay = QVBoxLayout(self.list_box)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(8)
        self.list_lay.addStretch(1)
        lay.addWidget(self.list_box)
        right = QVBoxLayout()
        right.setSpacing(8)
        head = QHBoxLayout()
        self.title = heading("", self, theme.BODY_PX)
        head.addWidget(self.title, 1)
        self.subtotals = QCheckBox("Show subtotals", self)
        self.subtotals.toggled.connect(lambda _on: self.show_selected())
        head.addWidget(self.subtotals)
        self.export_button = primary("Export", self, "secondary")
        self.export_button.clicked.connect(lambda: screen.export("output", position=self.position))
        head.addWidget(self.export_button)
        self.export_all_button = primary("Export all outputs", self, "secondary")
        self.export_all_button.clicked.connect(lambda: screen.export("outputs"))
        head.addWidget(self.export_all_button)
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
    def outputs(self):
        return self.view.run["outputs"] if self.view else []

    @property
    def position(self) -> int | None:
        outs = self.outputs
        return outs[self.selected].position if 0 <= self.selected < len(outs) else None

    def load(self, view: runs.RunView) -> None:
        self.view = view
        for b in self.buttons:
            b.hide()
            b.setParent(None)
            b.deleteLater()
        self.buttons = []
        for i, o in enumerate(self.outputs):
            b = QPushButton(o.name, self.list_box)
            b.setCheckable(True)
            b.setStyleSheet(f"QPushButton {{ text-align: left; padding: 8px 12px; min-height: 40px; "
                            f"border: 1px solid {theme.INPUT_BORDER}; border-radius: 8px; background: {theme.WHITE}; }}"
                            f"QPushButton:checked {{ border-color: {theme.TEAL}; background: {theme.TINT}; "
                            f"color: {theme.TEAL_DARK}; }}")
            b.clicked.connect(lambda _c=False, i=i: self.select(i))
            self.list_lay.insertWidget(i, b)
            self.buttons.append(b)
        has = bool(self.outputs)
        self.export_button.setVisible(has)
        self.export_all_button.setVisible(has)
        self.subtotals.setVisible(has)
        if not has:
            self.title.setText("No default outputs were saved with this run.")
            self.table.clear_result()
            return
        self.select(min(self.selected, len(self.outputs) - 1))

    def select(self, i: int) -> None:
        self.selected = i
        for j, b in enumerate(self.buttons):
            b.setChecked(j == i)
        o = self.outputs[i]
        self.subtotals.blockSignals(True)
        self.subtotals.setChecked(bool(o.definition.get("subtotals")))
        self.subtotals.blockSignals(False)
        self.show_selected()

    def show_selected(self) -> None:
        if not self.outputs:
            return
        o = self.outputs[self.selected]
        view = self.view
        self.title.setText(o.name)
        self.filters.setText(filters_text(o.definition, view.template.columns))
        self.filters.setVisible(bool(self.filters.text()))
        self.table.clear_result()
        path, cols, sub = view.run_dir / o.file, view.template.columns, self.subtotals.isChecked()
        rows_in = view.run["rows_loaded"]

        def done(p):
            if not self.outputs or self.outputs[self.selected] is not o:
                return
            self.table.show_result(p)
            text = f"Saved with {view.label} · on {formats.count(rows_in, 'row')} · {formats.count(p.count, 'group')}"
            if p.note:
                text += f" · {p.note}"
            self.info.setText(text)

        self.screen.load("Read output", lambda ctx: runs.stored_output(ctx, o.definition, cols, path, subtotals=sub),
                         done)


class SourcesTab(QWidget):
    COLUMNS = ["File", "Sheet", "Path at load" " time", "Size", "Modified", "Header", "Rows loaded"]   # split for test_offline

    def __init__(self, screen: "RunScreen"):
        super().__init__(screen)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(8)
        self.table = _table(self.COLUMNS, self)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        self.hidden = note("", self)
        self.hidden.setWordWrap(True)
        lay.addWidget(self.hidden)

    def load(self, view: runs.RunView) -> None:
        rows, prev, hidden = [], None, []
        from pathlib import PureWindowsPath
        for f in view.run["files"]:
            first = f["path"] != prev
            prev = f["path"]
            rows.append([f["file_name"], f["sheet"] or "", str(PureWindowsPath(f["path"]).parent),
                         formats.size(f["size"]) if first else "", formats.date_time(f["modified"]) if f["modified"]
                         else "", f"Row {f['header_row']}" if f["header_row"] else "",
                         formats.number(view.rows_loaded.get(f["file_index"], 0))])
            where = f"{f['file_name']}, {f['sheet']}" if f["sheet"] else f["file_name"]
            if f["hidden_rows"]:
                hidden.append(f"{formats.count(f['hidden_rows'], 'hidden row')} in {where}")
            if first and f["sheets_skipped"]:
                names = ", ".join(f'"{s}"' for s in f["sheets_skipped"])
                hidden.append(f"sheet{'s' if len(f['sheets_skipped']) > 1 else ''} {names} in {f['file_name']}")
        _fill(self.table, rows, {3, 6})
        self.hidden.setText(("Hidden data skipped: " + "; ".join(hidden) + ".") if hidden else "")

    def rows(self) -> list[list[str]]:
        return table_rows(self.table)


class RunScreen(DataScreen):
    area = "clients"

    def __init__(self, run_id: str, template_id: str = "", name: str = "", window=None, parent=None):
        self.run_id = run_id
        self.template_id = template_id
        self.template_name = name
        self.title = ""
        super().__init__(window, parent)
        self.view: runs.RunView | None = None
        self.badge = QLabel("", self)
        self.badge.setStyleSheet(f"background: {theme.OVERRIDE_BG}; color: {theme.OVERRIDE_TEXT}; border-radius: "
                                 f"10px; padding: 2px 10px; font-size: {theme.SMALL_PX}px; font-weight: 500;")
        self.badge.hide()
        self.title_row.insertWidget(1, self.badge)
        self.export_button = primary("Export data", self, "secondary")
        self.export_button.clicked.connect(lambda: self.export("data"))
        self.actions.addWidget(self.export_button)
        self.menu_button = icon_button("more", "More actions", self)
        self.menu_button.clicked.connect(lambda: self.more_menu().popup(
            self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft())))
        self.actions.addWidget(self.menu_button)

        self.tabs = CountTabs(TAB_LABELS, self)
        self.content.setSpacing(0)
        self.content.addWidget(self.tabs)
        rule = QWidget(self)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {theme.BORDER};")
        self.content.addWidget(rule)
        self.pages = QStackedWidget(self)
        self.summary_tab = SummaryTab(self)
        issues_page = QWidget(self)
        il = QVBoxLayout(issues_page)
        il.setContentsMargins(0, 16, 0, 0)
        self.issues_tab = IssuesView(self, issues_page)
        self.issues_tab.export_button.clicked.connect(lambda: self.export("issues"))
        il.addWidget(self.issues_tab)
        self.outputs_tab = OutputsTab(self)
        self.sources_tab = SourcesTab(self)
        for page in (self.summary_tab, issues_page, self.outputs_tab, self.sources_tab):
            self.pages.addWidget(page)
        self.content.addWidget(self.pages, 1)
        self.tabs.currentChanged.connect(self.pages.setCurrentIndex)

    def crumbs(self) -> list[Crumb]:
        v = self.view
        client = v.client_name if v else ""
        cid = v.client_id if v else None
        tname = v.template.name if v else self.template_name
        return [Crumb("Clients", lambda: self.window_.open_area("clients")),
                Crumb(client, (lambda: self.window_.go("client", client_id=cid, name=client)) if cid else None),
                Crumb(tname, lambda: self.window_.go("template", template_id=self.template_id, name=tname)),
                Crumb(v.label if v else "")]

    def shown(self) -> None:
        if self.storage is not None:
            self.load("Read run", lambda ctx: runs.run_view(ctx, self.folder, self.run_id), self._loaded)

    def _loaded(self, view: runs.RunView) -> None:
        self.view = view
        run = view.run
        self.template_id = run["template_id"]
        self.template_name = view.template.name
        self.set_title(view.label, header_line(run))
        self.badge.setText(status_badge(run["status"]))
        self.badge.setStyleSheet(self.badge.styleSheet() if run["status"] == STATUS_OVERRIDE else
                                 f"background: {theme.SUCCESS_TINT}; color: {theme.SUCCESS_TEXT}; border-radius: "
                                 f"10px; padding: 2px 10px; font-size: {theme.SMALL_PX}px; font-weight: 500;")
        self.badge.show()
        self.refresh_crumbs()
        self.tabs.set_count(ISSUES, run["errors"] + run["warnings"])
        self.tabs.set_count(OUTPUTS, len(run["outputs"]))
        self.tabs.set_count(SOURCES, len(run["files"]))
        self.summary_tab.load(view)
        self.issues_tab.set_issues(view.issues, view.file_names, view.column_names, view.lines)
        self.outputs_tab.load(view)
        self.sources_tab.load(view)

    def select_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)

    # ------------------------------------------------------------------------------------------ actions
    def more_menu(self) -> QMenu:
        """C6-01: Export issue list, Export left-out rows, Delete run."""
        menu = QMenu(self)
        menu.addAction("Export issue list", partial(self.export, "issues"))
        menu.addAction("Export left-out rows", partial(self.export, "left_out"))
        menu.addSeparator()
        menu.addAction("Delete run", self.delete_run).setEnabled(not self.bridge.busy)
        self.menu = menu
        return menu

    def export_request(self, kind: str, position: int | None = None) -> ex.ExportRequest | None:
        v = self.view
        if v is None:
            return None
        output = ""
        sub = None
        if kind == "output":
            o = next((o for o in v.run["outputs"] if o.position == position), None)
            if o is None:
                return None
            output = o.name
            sub = self.outputs_tab.subtotals.isChecked()
        return ex.prefill(kind, v.template.export, template_id=v.template.id, client=v.client_name,
                          template=v.template.name, run_id=self.run_id, run_label=v.label, output=output,
                          position=position, subtotals=sub)

    def export(self, kind: str, position: int | None = None) -> bool:
        req = self.export_request(kind, position)
        return req is not None and self.window_.go("export", request=req)

    def delete_run(self) -> None:
        """7.2 (RUN-9, C6-09): then back to the template's runs."""
        if self.view is None:
            return
        label, tid, tname = self.view.label, self.template_id, self.template_name

        def confirmed():
            def done(_r):
                self.window_.go("template", template_id=tid, name=tname, banner=Banner("success", f"{label} deleted."))
            self.start("Delete run", lambda ctx: manage.delete_run(ctx, self.folder, self.run_id), done)

        self.load("Read run", lambda ctx: manage.run_delete_summary(ctx, self.run_id),
                  lambda summary: self.confirm_delete(summary, confirmed))
