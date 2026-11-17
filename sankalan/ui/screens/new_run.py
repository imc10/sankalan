"""4.1–4.5 New run wizard (F2, UX-8, RUN-1 to RUN-14; RUNF, RUNM, RUNV, RUNO, RUNC test cases).

Five steps over one ``RunSession`` (``sankalan.run.pipeline``): Files · Mapping · Validate · Outputs · Commit.
Mapping is skipped when every header matches (TPL-6) and Outputs when the template has none (DO-4); the step bar
shows them as skipped. Every step that reads files or DuckDB is a Job. Leaving the wizard any other way than
Commit asks "Leave and discard this run?" (7.6) and deletes the staging folder (RUN-14).

This module holds the frame and steps 1–2; ``new_run_steps`` holds Validate, Outputs and Commit.
"""
from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import formats
from sankalan import mapping as mp
from sankalan import runs
from sankalan.ingest.probe import ERROR, SKIPPED, FileSheet
from sankalan.ingest.stage import LoadFailed
from sankalan.model.template import active
from sankalan.run.pipeline import RunBlocked, RunSession
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.dialogs.run_dialogs import AddColumnDialog
from sankalan.ui.screens.base import LeaveGuard
from sankalan.ui.screens.common import DataScreen, error_text
from sankalan.ui.screens.new_template import sheets_text
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.breadcrumb import Crumb
from sankalan.ui.widgets.controls import heading, icon_button, note, panel, primary
from sankalan.ui.widgets.progress import ProgressPanel
from sankalan.ui.widgets.stepbar import StepBar

FILES, MAPPING, VALIDATE, OUTPUTS, COMMIT = range(5)
STEPS = ["Files", "Mapping", "Validate", "Outputs", "Commit"]
FILE_FILTER = "Excel and CSV files (*.xlsx *.xlsm *.csv)"       # IN-3
WORKERS: int | None = None          # reader workers (tests set 0: read in the Job's thread)
LEAVE_TITLE = "Leave and discard this run?"
LOAD_ANYWAY = "Load" " anyway"      # split so the SQL LOAD guard (test_offline) never reads it as a statement


def plain_error(error) -> str:
    """Errors with plain wording of their own (a file that can't be read now, a step that can't go on)."""
    if isinstance(error, (LoadFailed, RunBlocked)):
        return error.message
    if isinstance(error, (runs.RunProblem, mp.MappingError)):
        return str(error)
    return error_text(error)


def file_status(f: FileSheet, decided: bool) -> str:
    if f.status == ERROR:
        return "Can't read"
    if f.status == SKIPPED:
        return "Skipped"
    if f.duplicate_of and not decided:
        return "Already loaded"
    return "Ready"


def hidden_text(files: list[FileSheet]) -> str:
    """"Hidden sheet "Old" in Sales_Nov.xlsx is skipped. 25 hidden rows in Sales_Nov.xlsx are skipped." (IN-13)"""
    out, seen = [], set()
    for f in files:
        if not f.readable:
            continue
        if f.hidden_sheets and f.path not in seen:
            seen.add(f.path)
            names = ", ".join(f'"{s}"' for s in f.hidden_sheets)
            word = "sheet" if len(f.hidden_sheets) == 1 else "sheets"
            verb = "is" if len(f.hidden_sheets) == 1 else "are"
            out.append(f"Hidden {word} {names} in {f.file_name} {verb} skipped.")
        if f.hidden_rows:
            where = f"{f.file_name}, {f.sheet}" if f.sheet else f.file_name
            out.append(f"{formats.count(f.hidden_rows, 'hidden row')} in {where} "
                       f"{'is' if f.hidden_rows == 1 else 'are'} skipped.")
    return " ".join(out)


# ---------------------------------------------------------------------------------------------- step 1 Files
class FilesStep(QWidget):
    COLUMNS = ["File", "Sheet", "Size", "Header", "Rows", "Status", ""]

    def __init__(self, wizard: "NewRunScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        top = QHBoxLayout()
        drop = panel(self)
        drop.setObjectName("DropZone")
        dl = QHBoxLayout(drop)
        dl.setContentsMargins(16, 10, 16, 10)
        dl.setSpacing(12)
        dl.addWidget(heading("Drag files here, or", drop, theme.GRID_TEXT_PX))
        self.add_button = primary("Add files…", drop, "secondary")
        self.add_button.clicked.connect(self.browse)
        wizard.bridge.guard(self.add_button)
        dl.addWidget(self.add_button)
        self.accepts = note("", drop)
        dl.addWidget(self.accepts, 1)
        top.addWidget(drop, 1)
        self.recheck_button = primary("Re-check files", self, "secondary")
        self.recheck_button.clicked.connect(lambda: wizard.recheck_files())
        wizard.bridge.guard(self.recheck_button)
        top.addWidget(self.recheck_button)
        lay.addLayout(top)
        self.refused = note("", self, "error")
        self.refused.hide()
        lay.addWidget(self.refused)
        self.problems = QVBoxLayout()
        self.problems.setSpacing(8)
        lay.addLayout(self.problems)
        self.table = QTableWidget(0, len(self.COLUMNS), self)
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, w in ((1, 160), (2, 96), (3, 88), (4, 110), (5, 140), (6, 44)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            hh.resizeSection(i, w)
        lay.addWidget(self.table, 1)
        self.summary = note("", self)
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------------------------------ adding
    def browse(self) -> None:
        paths, _f = QFileDialog.getOpenFileNames(self, "Add files", "", FILE_FILTER)
        if paths:
            self.wizard.add_files(paths)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.wizard.add_files(urls)
            event.acceptProposedAction()

    def set_refused(self, messages: list[str]) -> None:
        self.refused.setText("\n".join(messages))
        self.refused.setVisible(bool(messages))

    # ------------------------------------------------------------------------------------------ showing
    def load(self) -> None:
        wz = self.wizard
        sess = wz.session
        if wz.start_info is not None:
            self.accepts.setText(".xlsx, .xlsm or .csv · " + sheets_text(wz.start_info.template.source))
        files = sess.files if sess else []
        decided = sess.duplicate_decisions if sess else {}
        while self.problems.count():
            w = self.problems.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        if wz.start_info is not None and wz.start_info.low_disk:
            free = formats.gigabytes(wz.start_info.free_bytes)
            self.problems.addWidget(Banner(
                "warning", f"Only {free} free on the data folder's drive. A large run may not fit: free some "
                           "space before loading.", closable=False, parent=self))
        seen: set[str] = set()
        for f in files:
            if f.path in seen:
                continue
            if f.status == ERROR:
                seen.add(f.path)
                self.problems.addWidget(Banner(
                    "error", f.message or f"{f.file_name} can't be read.", closable=False, parent=self,
                    actions=[("Exclude file", lambda _c=False, p=f.path: wz.remove_file(p)),
                             ("Re-check", lambda _c=False, p=f.path: wz.recheck_files([p]))]))
            elif f.duplicate_of and f.path not in decided:
                seen.add(f.path)
                self.problems.addWidget(Banner(
                    "warning", f.message, closable=False, parent=self,
                    actions=[("Remove file", lambda _c=False, p=f.path: wz.remove_file(p)),
                             (LOAD_ANYWAY, lambda _c=False, p=f.path: wz.load_anyway(p))]))
        for b in self.findChildren(Banner):
            for btn in b.buttons.values():
                wz.bridge.guard(btn)
        self.table.setRowCount(len(files))
        prev = None
        for r, f in enumerate(files):
            first = f.path != prev
            prev = f.path
            values = [f.file_name, f.sheet, formats.size(f.size) if first and f.size else "",
                      f"Row {f.header_row}" if f.header_row else "–",
                      f"≈{formats.number(f.rows_approx)}" if f.rows_approx is not None and f.readable else "–",
                      file_status(f, f.path in decided)]
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                if c == 0 and not first:
                    item.setForeground(QBrush(QColor(theme.DISABLED_TEXT)))
                if c in (2, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 5:
                    colour = {"Ready": theme.SUCCESS, "Can't read": theme.ERROR,
                              "Already loaded": theme.OVERRIDE_TEXT}.get(text, theme.MUTED)
                    item.setForeground(QBrush(QColor(colour)))
                    item.setToolTip(f.message)
                self.table.setItem(r, c, item)
            if first:
                rm = icon_button("close", f"Remove {f.file_name}")
                rm.clicked.connect(lambda _c=False, p=f.path: wz.remove_file(p))
                wz.bridge.guard(rm)
                self.table.setCellWidget(r, 6, rm)
            else:
                self.table.removeCellWidget(r, 6)
        self.summary.setText(self.summary_text(files))

    @staticmethod
    def summary_text(files: list[FileSheet]) -> str:
        ok = [f for f in files if f.readable]
        if not files:
            return "No files added yet."
        n_files = len({f.path for f in ok})
        rows = sum(f.rows_approx or 0 for f in ok)
        parts = [formats.count(n_files, "file"), formats.count(len(ok), "sheet"), f"about {formats.count(rows, 'row')}"]
        bad = len({f.path for f in files if f.status == ERROR})
        if bad:
            parts.append(f"{formats.count(bad, 'file')} can't be read")
        skipped = [f for f in files if f.status == SKIPPED]
        text = " · ".join(parts) + "."
        hidden = hidden_text(files)
        if hidden:
            text += " " + hidden
        for f in skipped:
            text += f" {f.file_name}: {f.message}"
        return text

    def rows(self) -> list[list[str]]:
        return [[self.table.item(r, c).text() for c in range(6)] for r in range(self.table.rowCount())]

    def footer_text(self) -> str:
        sess = self.wizard.session
        if sess is None or not sess.files:
            return "Add the files for this run"
        bad = len({f.path for f in sess.files if f.status == ERROR})
        if bad:
            return f"Exclude or fix {formats.count(bad, 'file')} to continue"
        dup = len({f.path for f in sess.files if f.duplicate_of and f.path not in sess.duplicate_decisions})
        if dup:
            return f"Remove or load {formats.count(dup, 'file')} to continue"
        if not sess.readable_files:
            return "Add a file that can be read"
        return "Mapping is checked next"


# ---------------------------------------------------------------------------------------------- step 2 Mapping
def cell_text(plan: mp.MappingPlan, cell: mp.Cell) -> tuple[str, str | None, bool]:
    """(text, colour, undecided) for one mapping grid cell (MAP-4)."""
    headers = plan._sheet[cell.sheet].headers
    h = headers[cell.position] if cell.position is not None else ""
    how = cell.how
    if how is None:
        return "Choose…", theme.WARNING, True
    if how == mp.BY_NAME:
        return h, None, False
    if how in (mp.BY_ALIAS, mp.SAVE_ALIAS):
        return f"{h} · alias", theme.TEAL_DARK, False
    if how == mp.RUN_ONLY:
        return f"{h} · this run only", theme.TEAL_DARK, False
    if how == mp.LEAVE_NULL:
        return "(Null)", theme.MUTED, False
    if how == mp.ADDED:
        return f"{h} · new column", theme.TEAL_DARK, False
    return h, None, False


class MappingStep(QWidget):
    """4.2: rows = template columns (then file headers not in the template), columns = file-sheets (MAP-4).
    Undecided cells are amber; the panel on the right decides the selected item (MAP-5 to MAP-7)."""

    def __init__(self, wizard: "NewRunScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        self.items: list[tuple] = []        # per grid row: ("col", column ID) or ("extra", header text)
        self.selected: tuple | None = None  # ("cell", column ID, sheet) | ("extra", sheet, position)
        self.dialog = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.info = heading("", self, theme.GRID_TEXT_PX)
        lay.addWidget(self.info)
        body = QHBoxLayout()
        body.setSpacing(16)
        self.table = QTableWidget(0, 0, self)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setShowGrid(False)
        self.table.currentCellChanged.connect(lambda r, c, _r, _c: self._cell_selected(r, c))
        body.addWidget(self.table, 1)
        self.panel = panel(self)
        self.panel.setFixedWidth(360)
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(10)
        self.where = note("", self.panel)
        self.where.setWordWrap(True)
        pl.addWidget(self.where)
        self.question = heading("", self.panel, theme.BODY_PX)
        self.question.setWordWrap(True)
        pl.addWidget(self.question)
        self.header_pick = QComboBox(self.panel)
        self.header_pick.setAccessibleName("Pick a header")
        pl.addWidget(self.header_pick)
        self.map_alias = primary("Map and save as alias", self.panel)
        self.map_alias.clicked.connect(lambda: self.decide("save_alias"))
        self.run_only = primary("This run only", self.panel, "secondary")
        self.run_only.clicked.connect(lambda: self.decide("run_only"))
        self.null = primary("Leave as null", self.panel, "secondary")
        self.null.clicked.connect(lambda: self.decide("null"))
        self.leave_out = primary("Leave out", self.panel, "secondary")
        self.leave_out.clicked.connect(lambda: self.decide("leave_out"))
        self.add_col = primary("Add as new column…", self.panel)
        self.add_col.clicked.connect(lambda: self.decide("add"))
        for b in (self.map_alias, self.run_only, self.null, self.leave_out, self.add_col):
            pl.addWidget(b)
        self.hint = note("", self.panel)
        self.hint.setWordWrap(True)
        pl.addWidget(self.hint)
        self.warning = note("", self.panel, "warning")
        self.warning.setWordWrap(True)
        pl.addWidget(self.warning)
        self.error = note("", self.panel, "error")
        self.error.setWordWrap(True)
        pl.addWidget(self.error)
        pl.addStretch(1)
        body.addWidget(self.panel)
        lay.addLayout(body, 1)

    @property
    def plan(self) -> mp.MappingPlan:
        return self.wizard.session.mapping

    # ------------------------------------------------------------------------------------------ grid
    def load(self) -> None:
        plan = self.plan
        sheets = plan.sheets
        cols = active(plan.columns)
        extras: dict[str, list[tuple[int, int]]] = {}
        for (key, pos), _how in sorted(plan.extras.items()):
            header = plan._sheet[key].headers[pos]
            if _how == mp.ADD_COLUMN:
                continue
            extras.setdefault(header, []).append((key, pos))
        self.items = [("col", c.id) for c in cols] + [("extra", h) for h in extras]
        self._extras = extras
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setColumnCount(2 + len(sheets))
        self.table.setHorizontalHeaderLabels(["Template column", "Type"] + [s.label for s in sheets])
        for i, s in enumerate(sheets):
            self.table.horizontalHeaderItem(2 + i).setToolTip(f"{s.file_name}, sheet {s.sheet}" if s.sheet
                                                             else s.file_name)
        self.table.setRowCount(len(self.items))
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(len(sheets)):
            hh.setSectionResizeMode(2 + i, QHeaderView.ResizeMode.Stretch)
        for r, item in enumerate(self.items):
            if item[0] == "col":
                c = next(x for x in cols if x.id == item[1])
                self._put(r, 0, c.name)
                self._put(r, 1, c.type, theme.MUTED)
                for i, s in enumerate(sheets):
                    cell = plan.cells.get((c.id, s.key))
                    if cell is None:
                        self._put(r, 2 + i, "")
                        continue
                    text, colour, pending = cell_text(plan, cell)
                    self._put(r, 2 + i, text, colour, pending)
            else:
                header = item[1]
                self._put(r, 0, f"“{header}”")
                self._put(r, 1, "Not in the template", theme.MUTED)
                where = dict(self._extras[header])
                for i, s in enumerate(sheets):
                    if s.key not in where:
                        self._put(r, 2 + i, "")
                        continue
                    how = plan.extras.get((s.key, where[s.key]))
                    text = {None: "Decide…", mp.LEAVE_OUT: "Left out"}.get(how, header)
                    self._put(r, 2 + i, text, theme.WARNING if how is None else theme.MUTED, how is None)
        self.table.blockSignals(False)
        left = len(plan.undecided())
        n_cols = len(cols)
        matched = sum(1 for c in cols if all((plan.cells.get((c.id, s.key)) or mp.Cell(c.id, 0)).how in mp.AUTOMATIC
                                               for s in sheets))
        text = f"{matched} of {formats.count(n_cols, 'column')} matched" + (
            f" in all {formats.count(len(sheets), 'sheet')}." if len(sheets) > 1 else ".")
        if left:
            text += f" {formats.count(left, 'item')} {'needs' if left == 1 else 'need'} a decision before validation."
        self.info.setText(text)
        if self.selected is None or not self._valid(self.selected):
            self.selected = plan.first_undecided()
        self.show_item(self.selected)

    def _put(self, r: int, c: int, text: str, colour: str | None = None, pending: bool = False) -> None:
        item = QTableWidgetItem(text)
        if colour:
            item.setForeground(QBrush(QColor(colour)))
        if pending:
            item.setBackground(QBrush(QColor(theme.WARNING_TINT)))
        self.table.setItem(r, c, item)

    def _valid(self, sel: tuple) -> bool:
        plan = self.plan
        if sel[0] == "cell":
            return (sel[1], sel[2]) in plan.cells
        return (sel[1], sel[2]) in plan.extras

    def grid_rows(self) -> list[list[str]]:
        return [[self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(self.table.columnCount())]
                for r in range(self.table.rowCount())]

    def pending_cells(self) -> list[tuple[int, int]]:
        """Grid cells shown amber (undecided), as (row, column)."""
        out = []
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                if it is not None and it.background().color() == QColor(theme.WARNING_TINT):
                    out.append((r, c))
        return out

    def _position(self, sel: tuple) -> tuple[int, int] | None:
        sheets = [s.key for s in self.plan.sheets]
        if sel[0] == "cell":
            if ("col", sel[1]) not in self.items:
                return None
            return self.items.index(("col", sel[1])), 2 + sheets.index(sel[2])
        header = self.plan._sheet[sel[1]].headers[sel[2]]
        if ("extra", header) not in self.items:
            return None
        return self.items.index(("extra", header)), 2 + sheets.index(sel[1])

    def _cell_selected(self, r: int, c: int) -> None:
        if r < 0 or c < 2 or r >= len(self.items):
            return
        sheet = self.plan.sheets[c - 2].key
        kind, key = self.items[r]
        if kind == "col":
            if (key, sheet) in self.plan.cells:
                self.show_item(("cell", key, sheet), move=False)
        else:
            where = dict(self._extras.get(key, []))
            if sheet in where:
                self.show_item(("extra", sheet, where[sheet]), move=False)

    # ------------------------------------------------------------------------------------------ decision panel
    def show_item(self, sel: tuple | None, move: bool = True) -> None:
        """Show the decision panel for an item and select its cell (MAP-13: Next moves focus here)."""
        self.selected = sel
        self.error.setText("")
        for b in (self.map_alias, self.run_only, self.null, self.leave_out, self.add_col, self.header_pick):
            b.hide()
        self.warning.setText("")
        self.hint.setText("")
        if sel is None:
            self.where.setText("")
            self.question.setText("Every column is decided. Next checks the rules.")
            return
        plan = self.plan
        if move:
            pos = self._position(sel)
            if pos is not None:
                self.table.blockSignals(True)
                self.table.setCurrentCell(*pos)
                self.table.blockSignals(False)
                self.table.setFocus()
        left = plan.undecided()
        n = (left.index(sel) + 1) if sel in left else None
        prefix = f"{n} of {len(left)} · " if n else ""
        if sel[0] == "cell":
            _k, cid, key = sel
            s = plan._sheet[key]
            col = next(c for c in plan.columns if c.id == cid)
            cell = plan.cells[(cid, key)]
            self.where.setText(f"{prefix}{s.file_name}" + (f", {s.sheet}" if s.sheet else ""))
            free = plan.headers_free(key)
            if cell.position is not None and cell.position not in free:
                free = [cell.position] + free
            self.header_pick.clear()
            for p in free:
                self.header_pick.addItem(s.headers[p], p)
            if cell.position is not None:
                self.header_pick.setCurrentIndex(max(0, self.header_pick.findData(cell.position)))
            if cell.how is None:
                self.question.setText(f"No column found for {col.name}. Pick a header, or leave it as null.")
            else:
                self.question.setText(f"{col.name}: {cell_text(plan, cell)[0]}")
            has = self.header_pick.count() > 0
            self.header_pick.setVisible(has)
            self.map_alias.setVisible(has)
            self.run_only.setVisible(has)
            self.null.show()
            self.hint.setText("Saving the alias maps this header automatically in future runs." if has else
                              "This file-sheet has no header left to pick.")
            warn = plan.null_warnings(cid)
            if warn:
                self.warning.setText(" ".join(w.replace("will show", "would show") for w in warn))
        else:
            _k, key, pos = sel
            s = plan._sheet[key]
            header = s.headers[pos]
            self.where.setText(f"{prefix}{s.file_name}" + (f", {s.sheet}" if s.sheet else ""))
            how = plan.extras.get((key, pos))
            state = {None: "", mp.LEAVE_OUT: " It is left out."}.get(how, "")
            self.question.setText(f"“{header}” isn't in the template.{state}")
            self.leave_out.show()
            self.add_col.show()
            runs_before = self.wizard.start_info.next_number - 1 if self.wizard.start_info else 0
            self.hint.setText((f"A new column shows as null in the {formats.count(runs_before, 'earlier run')}. "
                               if runs_before else "") + "Its type is fixed once this run is committed.")

    def decide(self, action: str, **values) -> bool:
        """Apply a decision to the selected item; then go to the next undecided one."""
        sel = self.selected
        if sel is None:
            return False
        plan = self.plan
        try:
            if sel[0] == "cell":
                _k, cid, key = sel
                if action in ("save_alias", "run_only"):
                    pos = values.get("position", self.header_pick.currentData())
                    if pos is None:
                        return False
                    plan.map(cid, key, pos, save_alias=action == "save_alias")
                elif action == "null":
                    plan.leave_null(cid, key)
                else:
                    return False
            else:
                _k, key, pos = sel
                if action == "leave_out":
                    plan.leave_out(key, pos)
                elif action == "add":
                    if not values:
                        dlg = AddColumnDialog(plan._sheet[key].headers[pos],
                                              self.wizard.start_info.next_number - 1 if self.wizard.start_info else 0,
                                              self)
                        self.dialog = dlg
                        ok = dlg.exec() == AddColumnDialog.DialogCode.Accepted
                        self.dialog = None
                        if not ok:
                            return False
                        values = dlg.values
                    plan.add_column(key, pos, values["name"], values.get("type_", "Text"),
                                    decimals=values.get("decimals"), date_format=values.get("date_format"))
                else:
                    return False
        except mp.MappingError as e:
            self.error.setText(str(e))
            return False
        warn = plan.null_warnings(sel[1]) if action == "null" else []
        self.selected = plan.first_undecided()
        self.load()
        if warn:
            self.warning.setText(" ".join(warn))
        self.wizard.update_footer()
        return True

    def footer_text(self) -> str:
        left = len(self.plan.undecided()) if self.plan else 0
        return f"{formats.count(left, 'decision')} left" if left else "Every column is decided"


# ---------------------------------------------------------------------------------------------- the wizard
class NewRunScreen(DataScreen):
    area = "clients"
    title = "New run"

    def __init__(self, template_id: str, name: str = "", window=None, parent=None):
        self.template_id = template_id
        self.template_name = name
        super().__init__(window, parent)
        from sankalan.ui.screens.new_run_steps import CommitStep, OutputsStep, ValidateStep
        self.step = FILES
        self.start_info: runs.WizardStart | None = None
        self.session: RunSession | None = None
        self.finished = False               # committed or discarded: leaving asks nothing
        self.job = None

        self.steps = StepBar(STEPS, self)
        self.content.addWidget(self.steps)
        self.pages = QStackedWidget(self)
        self.files_step = FilesStep(self)
        self.mapping_step = MappingStep(self)
        self.validate_step = ValidateStep(self)
        self.outputs_step = OutputsStep(self)
        self.commit_step = CommitStep(self)
        for p in (self.files_step, self.mapping_step, self.validate_step, self.outputs_step, self.commit_step):
            self.pages.addWidget(p)
        self.content.addWidget(self.pages, 1)
        self.progress = ProgressPanel(self)
        self.progress.hide()
        self.content.addWidget(self.progress)

        foot = QHBoxLayout()
        foot.setSpacing(12)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setProperty("kind", "plain")
        self.cancel_button.clicked.connect(self.cancel)
        self.back_button = primary("Back", self, "secondary")
        self.back_button.clicked.connect(self.back)
        foot.addWidget(self.cancel_button)
        foot.addWidget(self.back_button)
        foot.addStretch(1)
        self.footer = note("", self)
        self.footer.setWordWrap(False)
        foot.addWidget(self.footer)
        self.override_button = primary("Continue despite errors…", self, "secondary")
        self.override_button.clicked.connect(self.continue_despite_errors)
        self.recheck_button = primary("Re-check files", self, "secondary")
        self.recheck_button.clicked.connect(self.recheck)
        self.next_button = primary("Next: Mapping", self)
        self.next_button.clicked.connect(self.next)
        self.commit_button = primary("Commit", self)
        self.commit_button.clicked.connect(self.commit)
        for b in (self.override_button, self.recheck_button, self.next_button, self.commit_button):
            foot.addWidget(b)
            self.bridge.guard(b)
        self.content.addLayout(foot)
        self._show_step()

    # ------------------------------------------------------------------------------------------ frame
    def crumbs(self) -> list[Crumb]:
        info = self.start_info
        client = info.client_name if info else ""
        cid = info.client_id if info else None
        out = [Crumb("Clients", lambda: self.window_.open_area("clients"))]
        out.append(Crumb(client, (lambda: self.window_.go("client", client_id=cid, name=client)) if cid else None))
        out.append(Crumb(self.template_name, lambda: self.window_.go("template", template_id=self.template_id,
                                                                     name=self.template_name)))
        out.append(Crumb("New run"))
        return out

    def shown(self) -> None:
        if self.start_info is None and self.storage is not None:
            self.load("Read template", lambda ctx: runs.wizard_start(ctx, self.folder, self.template_id),
                      self._started)

    def _started(self, info: runs.WizardStart) -> None:
        self.start_info = info
        self.template_name = info.template.name
        self.session = RunSession(self.folder, info.template, workers=WORKERS)
        self.refresh_crumbs()
        self.files_step.load()
        self.update_footer()

    @property
    def run_label(self) -> str:
        return f"R-{self.start_info.next_number:04d}" if self.start_info else "This run"

    def _show_step(self) -> None:
        self.pages.setCurrentIndex(self.step)
        self.steps.set_current(self.step)
        skipped = []
        sess = self.session
        if sess is not None and sess.mapping is not None and sess.mapping_skipped:
            skipped.append(MAPPING)
        if sess is not None and sess.outputs_skipped:
            skipped.append(OUTPUTS)
        self.steps.set_skipped(skipped)
        self.back_button.setVisible(self.step > FILES)
        self.update_footer()

    def update_footer(self) -> None:
        step = self.step
        sess = self.session
        text = ""
        next_label, next_on = "", False
        if step == FILES:
            text = self.files_step.footer_text()
            next_label = "Next: Mapping"
            next_on = sess is not None and not sess.files_blockers()
        elif step == MAPPING:
            text = self.mapping_step.footer_text() if sess and sess.mapping else ""
            next_label, next_on = "Next: Validate", True        # Next with decisions left moves focus (MAP-13)
        elif step == VALIDATE:
            text = self.validate_step.footer_text()
            next_label = "Next: Commit" if sess and not sess.template.outputs else "Next: Outputs"
            next_on = bool(sess and sess.validation is not None and sess.validation.passed and self.job is None)
        elif step == OUTPUTS:
            text = self.outputs_step.footer_text()
            next_label = "Next: Commit"
            next_on = bool(sess and sess.outputs_done and self.job is None)
        elif step == COMMIT:
            text = self.commit_step.footer_text()
        self.footer.setText(text)
        self.next_button.setVisible(step != COMMIT)
        self.next_button.setText(next_label or "Next")
        self.bridge.set_allowed(self.next_button, next_on)
        validated = step == VALIDATE and sess is not None and sess.validation is not None
        self.override_button.setVisible(validated and not sess.validation.passed)
        self.bridge.set_allowed(self.override_button, validated and self.job is None)
        self.recheck_button.setVisible(step == VALIDATE)
        self.bridge.set_allowed(self.recheck_button, step == VALIDATE and self.job is None)
        self.commit_button.setVisible(step == COMMIT)
        self.commit_button.setText(f"Commit {self.run_label}")
        self.bridge.set_allowed(self.commit_button, step == COMMIT and self.commit_step.can_commit())

    # ------------------------------------------------------------------------------------------ Jobs
    def run(self, operation: str, work, on_done, *, cancellable: bool = True, progress: bool = True,
            on_failed=None, on_cancelled=None):
        def done(result):
            self.progress.hide()
            self.job = None
            on_done(result)
            self.update_footer()

        def failed(error):
            self.progress.hide()
            self.job = None
            (on_failed or self._failed)(error)
            self.update_footer()

        def cancelled():
            self.progress.hide()
            self.job = None
            if on_cancelled is not None:
                on_cancelled()
            self.update_footer()

        job = self.start(operation, work, done, failed, cancellable=cancellable, on_cancelled=cancelled)
        self.job = job
        if job is not None and progress:
            self.progress.bind(job)
            self.progress.show()
        self.update_footer()
        return job

    def _failed(self, error) -> None:
        self.show_banner(Banner("error", plain_error(error)))

    def _clear_banners(self) -> None:
        for b in self.banners():
            b.dismiss()

    # ------------------------------------------------------------------------------------------ step 1
    def add_files(self, paths) -> bool:
        """Add files by picker or drag and drop (IN-1). Folders and unsupported types are refused with a message
        (RUNF-01, RUNF-03); lock files and the same file twice are listed as skipped (IN-10)."""
        if self.session is None or self.job is not None:
            return False
        sess = self.session

        def done(rows: list[FileSheet]):
            self.files_step.set_refused([r.message for r in rows if r.status == "refused"])
            self.files_step.load()

        return self.run("Check files", lambda ctx: sess.add_files(ctx, [str(p) for p in paths]), done) is not None

    def remove_file(self, path) -> None:
        """✕, Remove file (RUN-7) or Exclude file (IN-15): the file isn't read in this run."""
        if self.session is None or self.job is not None:
            return
        self.session.remove_file(path)
        self.files_step.load()
        self.update_footer()

    def load_anyway(self, path) -> None:
        if self.session is None or self.job is not None:
            return
        self.session.load_anyway(path)
        self.files_step.load()
        self.update_footer()

    def recheck_files(self, paths=None) -> bool:
        """Re-check (RUNF-06): probe the files again where they are."""
        if self.session is None or self.job is not None or not self.session.files:
            return False
        sess = self.session
        return self.run("Check files", lambda ctx: sess.recheck_files(ctx, paths),
                        lambda _rows: self.files_step.load()) is not None

    # ------------------------------------------------------------------------------------------ navigation
    def next(self) -> None:
        if self.job is not None or self.session is None:
            return
        {FILES: self._next_files, MAPPING: self._next_mapping, VALIDATE: self._next_validate,
         OUTPUTS: self._next_outputs}.get(self.step, lambda: None)()

    def go_step(self, step: int) -> None:
        self._clear_banners()
        self.step = step
        if step == FILES:
            self.files_step.load()
        elif step == MAPPING:
            self.mapping_step.load()
        elif step == OUTPUTS:
            self.outputs_step.load()
        elif step == COMMIT:
            self.commit_step.load()
        self._show_step()

    def _next_files(self) -> None:
        sess = self.session
        try:
            plan = sess.mapping if sess.mapping is not None else sess.files_next()
        except RunBlocked as e:
            self.show_banner(Banner("error", e.message))
            return
        if plan.skip:                   # TPL-6, RUNF-12
            try:
                sess.mapping_next()
            except RunBlocked as e:
                self.show_banner(Banner("error", e.message))
                return
            self.validate()
        else:
            self.go_step(MAPPING)

    def _next_mapping(self) -> None:
        sess = self.session
        first = sess.mapping.first_undecided()
        if first is not None:           # MAP-13, RUNM-02
            self.mapping_step.show_item(first)
            return
        sess.mapping_next()
        self.validate()

    def validate(self) -> bool:
        """Read, convert and check the rules (RUN-3) with progress and Cancel. Cancel returns to Mapping, or Files
        when Mapping was skipped, and nothing is kept (RUNV-12)."""
        sess = self.session
        self.go_step(VALIDATE)
        self.validate_step.clear()

        def done(_v):
            self.validate_step.load()

        def back_out():
            sess.drop_staging()
            self.go_step(FILES if sess.mapping_skipped else MAPPING)

        def failed(error):
            sess.drop_staging()
            self.validate_step.show_failure(plain_error(error))

        return self.run("Validate", sess.validate, done, on_cancelled=back_out, on_failed=failed) is not None

    def recheck(self) -> bool:
        """Re-check files (VR-6, RUNV-11): read the files again and check the rules, without leaving the run."""
        if self.job is not None or self.session is None:
            return False
        return self.validate()

    def continue_despite_errors(self):
        from sankalan.ui.screens.new_run_steps import open_override
        return open_override(self)

    def leave_validate(self, reason: str | None = None) -> bool:
        """Next on Validate, or the override's Continue (T18): the split, then Outputs (or Commit, DO-4)."""
        sess = self.session

        def done(_r):
            if sess.outputs_skipped:
                self.go_step(COMMIT)
            else:
                self.go_step(OUTPUTS)
                self.outputs_step.generate()

        return self.run("Prepare rows", lambda ctx: sess.leave_validate(ctx, reason), done,
                        cancellable=False) is not None

    def _next_validate(self) -> None:
        self.leave_validate(None)

    def _next_outputs(self) -> None:
        if self.session.outputs_done:
            self.go_step(COMMIT)

    def back(self) -> None:
        if self.job is not None or self.step == FILES:
            return
        sess = self.session
        if self.step == MAPPING:
            self.go_step(FILES)
        elif self.step == VALIDATE:
            sess.drop_staging()
            self.go_step(FILES if sess.mapping_skipped else MAPPING)
        elif self.step == OUTPUTS:
            self.validate()             # the rows were split: check again to change anything (pipeline)
        elif self.step == COMMIT:
            if sess.outputs_skipped:
                self.validate()
            else:
                self.go_step(OUTPUTS)

    # ------------------------------------------------------------------------------------------ commit
    def commit(self) -> bool:
        from sankalan.ui.screens.new_run_steps import commit_run
        return commit_run(self)

    # ------------------------------------------------------------------------------------------ leaving (7.6)
    def cancel(self) -> bool:
        guard = self.leave_guard()
        if guard is None:
            return False
        key = ask(self, guard.title, guard.text, [(k, label, kind) for k, label, kind, _fn in guard.options])
        if key != "discard":
            return False
        self._discard()
        self.window_.go("template", template_id=self.template_id, name=self.template_name)
        return True

    def _discard(self) -> bool:
        self.finished = True
        if self.job is not None and self.job.cancellable:
            self.job.cancel()
            self.job.wait(5.0)
        if self.session is not None:
            self.session.discard()
        return True

    def leave_guard(self) -> LeaveGuard | None:
        if self.finished:
            return None
        return LeaveGuard.discard_run(self._discard)

    def closing(self) -> None:
        if not self.finished:
            self._discard()
        super().closing()

