"""3.2 Template › Default outputs (UX-5, DO-1, DO-6, DO-8; C4-05 to C4-08): the ordered list, the builder, and a
preview on the latest committed run. Saved edits apply to future runs only."""
from __future__ import annotations

import copy

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
                               QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import formats, manage
from sankalan.model import definition as d
from sankalan.model.definition import Definition, DefinitionError
from sankalan.model.template import DATE, NUMBER, DefaultOutput, Template
from sankalan.ui import theme
from sankalan.ui.screens.template import TemplateTab
from sankalan.ui.widgets.builder import NEW_OUTPUT, DefinitionBuilder, definition_summary
from sankalan.ui.widgets.controls import SaveBar, heading, icon_button, note, panel, plus_button, primary
from sankalan.ui.widgets.progress import ProgressPanel

FUTURE_ONLY = "Changes apply to future runs. Outputs already saved with earlier runs don't change."
NO_RUN = "Preview runs on the latest committed run. This template has none yet."
STALE = "Settings changed: Preview again."


def cell_text(value, kind: tuple, group: bool) -> str:
    typ, decimals, grain = kind
    if value is None:
        return d.NULL_LABEL if group else ""
    if typ == DATE:
        return formats.period(value, grain) if group else formats.date(value)
    if typ == NUMBER:
        return formats.number(value, decimals)
    if typ == "count":
        return formats.number(int(value))
    return str(value)


class OutputItem(QFrame):
    """One row of the Run order list: number, name, "2 groups · 3 measures", ↑ ↓ ⋯."""

    def __init__(self, tab: "OutputsTab", index: int, output: DefaultOutput, selected: bool):
        super().__init__(tab)
        self.setObjectName("OutputItem")
        bg, fg = (theme.TINT, theme.TEAL_DARK) if selected else ("transparent", theme.TEXT)
        self.setStyleSheet(f"#OutputItem {{ background: {bg}; border-radius: 6px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 4, 6)
        lay.setSpacing(8)
        n = QLabel(str(index + 1), self)
        n.setProperty("kind", "small")
        lay.addWidget(n)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.name = QLabel(output.name, self)
        self.name.setStyleSheet(f"color: {fg}; font-size: {theme.GRID_TEXT_PX}px; font-weight: 500;")
        texts.addWidget(self.name)
        meta = QLabel(definition_summary(output.definition), self)
        meta.setProperty("kind", "small")
        texts.addWidget(meta)
        lay.addLayout(texts, 1)
        up = icon_button("up", f"Move {output.name} up", self)
        down = icon_button("down", f"Move {output.name} down", self)
        more = icon_button("more", f"More actions for {output.name}", self)
        up.clicked.connect(lambda: tab.move(index, -1))
        down.clicked.connect(lambda: tab.move(index, 1))
        more.clicked.connect(lambda: tab.item_menu(index).popup(more.mapToGlobal(more.rect().bottomLeft())))
        up.setEnabled(index > 0)
        down.setEnabled(index < len(tab.outputs) - 1)
        for b in (up, down, more):
            lay.addWidget(b)
        self.index = index
        self.tab = tab

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.tab.select(self.index)


class OutputsTab(TemplateTab):
    def __init__(self, screen):
        super().__init__(screen)
        self.template: Template | None = None
        self.outputs: list[DefaultOutput] = []
        self.selected = -1
        self.latest: manage.LatestRun | None = None
        self.preview_result: manage.Preview | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(12)
        self.bar = SaveBar("Save outputs", FUTURE_ONLY, self, screen.bridge)
        self.bar.save.clicked.connect(lambda: self.save())
        self.bar.discard.clicked.connect(self.discard)
        lay.addWidget(self.bar)
        self.error = note("", self, "error")
        self.error.hide()
        lay.addWidget(self.error)

        body = QHBoxLayout()
        body.setSpacing(16)
        # list
        left = panel(self)
        left.setFixedWidth(280)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(heading("Run order", left, theme.GRID_TEXT_PX))
        head.addStretch(1)
        self.add_button = plus_button("Add output", left)
        self.add_button.clicked.connect(self.add_output)
        head.addWidget(self.add_button)
        ll.addLayout(head)
        self.list_box = QWidget(left)
        self.list_lay = QVBoxLayout(self.list_box)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(2)
        ll.addWidget(self.list_box)
        self.none = note("No default outputs. Runs skip the Outputs step until one is added.", left)
        ll.addWidget(self.none)
        ll.addStretch(1)
        body.addWidget(left)
        # builder
        mid = panel(self)
        mid.setMinimumWidth(440)
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(16, 12, 16, 12)
        ml.setSpacing(12)
        name_lab = QLabel("Output name", mid)
        name_lab.setProperty("kind", "small")
        ml.addWidget(name_lab)
        self.name = QLineEdit(mid)
        self.name.setAccessibleName("Output name")
        self.name.textEdited.connect(self._edited)
        ml.addWidget(self.name)
        self.builder = DefinitionBuilder([], output=True, parent=mid)
        self.builder.changed.connect(self._edited)
        scroll = QScrollArea(mid)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.builder)
        ml.addWidget(scroll, 1)
        self.preview_button = primary("Preview", mid, "secondary")
        self.preview_button.clicked.connect(self.preview)
        screen.bridge.guard(self.preview_button)
        pr = QHBoxLayout()
        pr.addStretch(1)
        pr.addWidget(self.preview_button)
        ml.addLayout(pr)
        self.editor = mid
        body.addWidget(mid, 5)
        # preview
        right = panel(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(8)
        rl.addWidget(heading("Preview", right, theme.GRID_TEXT_PX))
        self.preview_info = note("", right)
        rl.addWidget(self.preview_info)
        self.progress = ProgressPanel(right)
        self.progress.hide()
        rl.addWidget(self.progress)
        self.table = QTableWidget(right)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        rl.addWidget(self.table, 1)
        body.addWidget(right, 6)
        lay.addLayout(body, 1)

    # ------------------------------------------------------------------------------------------ load
    def load(self, detail: manage.TemplateDetail) -> None:
        self.template = detail.template
        self.latest = detail.latest
        self.outputs = [DefaultOutput.from_dict(o.to_dict()) for o in detail.template.outputs]
        self.builder.columns = detail.template.active_columns
        self.selected = -1
        self._redraw_list()
        self.select(0 if self.outputs else -1)
        self._clear_preview(NO_RUN if self.latest is None else
                            f"Preview runs on {self.latest.label}, the latest run. Click Preview.")

    def _redraw_list(self) -> None:
        while self.list_lay.count():
            w = self.list_lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for i, o in enumerate(self.outputs):
            self.list_lay.addWidget(OutputItem(self, i, o, i == self.selected))
        self.none.setVisible(not self.outputs)
        self.editor.setEnabled(bool(self.outputs))

    def items(self) -> list[OutputItem]:
        return [self.list_lay.itemAt(i).widget() for i in range(self.list_lay.count())]

    def select(self, index: int) -> None:
        if index == self.selected:
            return
        self._store()
        self.selected = index
        with QSignalBlocker(self.name):
            self.name.setText(self.outputs[index].name if index >= 0 else "")
        if index >= 0:
            o = self.outputs[index]
            self.builder.set_definition(Definition.from_dict(o.definition), self.template.active_columns)
        else:
            self.builder.set_definition(Definition(), self.template.active_columns if self.template else [])
        self._redraw_list()
        self._clear_preview(None)

    # ------------------------------------------------------------------------------------------ editing
    def _store(self) -> bool:
        """Copy the builder into the selected output. False (with the reason shown) when a value can't be read."""
        if not 0 <= self.selected < len(self.outputs):
            return True
        o = self.outputs[self.selected]
        o.name = self.name.text()
        try:
            o.definition = self.builder.definition().to_dict()
        except DefinitionError as e:
            self.show_error(str(e))
            return False
        return True

    def _edited(self, *_a) -> None:
        self._store()
        self.set_dirty(True)
        if 0 <= self.selected < len(self.items()):
            item = self.items()[self.selected]
            item.name.setText(self.name.text())
        if self.preview_result is not None:
            self.preview_info.setText(STALE)
            self.table.setEnabled(False)

    def add_output(self) -> None:
        self._store()
        names = {o.name.casefold() for o in self.outputs}
        name, n = "New output", 2
        while name.casefold() in names:
            name, n = f"New output {n}", n + 1
        self.outputs.append(DefaultOutput(name, NEW_OUTPUT.to_dict()))
        self.set_dirty(True)
        self.selected = -1
        self.select(len(self.outputs) - 1)

    def move(self, index: int, step: int) -> None:
        """C4-07: outputs run and show in this order."""
        j = index + step
        if not 0 <= j < len(self.outputs):
            return
        self._store()
        self.outputs[index], self.outputs[j] = self.outputs[j], self.outputs[index]
        if self.selected in (index, j):
            self.selected = j if self.selected == index else index
        self.set_dirty(True)
        self._redraw_list()

    def item_menu(self, index: int) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Duplicate", lambda: self.duplicate(index))
        menu.addAction("Delete", lambda: self.delete(index))
        self.menu = menu
        return menu

    def duplicate(self, index: int) -> None:
        self._store()
        o = copy.deepcopy(self.outputs[index])
        o.name = f"{o.name} (copy)"
        self.outputs.insert(index + 1, o)
        self.set_dirty(True)
        self.selected = -1
        self.select(index + 1)

    def delete(self, index: int) -> None:
        self._store()
        del self.outputs[index]
        self.set_dirty(True)
        self.selected = -1
        self.select(min(index, len(self.outputs) - 1))
        self._redraw_list()

    def show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    # ------------------------------------------------------------------------------------------ save
    def check(self) -> str | None:
        if not self._store():
            return self.error.text()
        seen = set()
        for o in self.outputs:
            name = o.name.strip()
            if not name:
                return "Every default output needs a name."
            if name.casefold() in seen:
                return f"Two default outputs are named “{name}”. Use a different name for each."
            seen.add(name.casefold())
            try:
                d.check(Definition.from_dict(o.definition), self.template.columns, output=True)
            except DefinitionError as e:
                return f"{name}: {e}"
        return None

    def apply(self, t: Template) -> None:
        outs = []
        for o in self.outputs:
            definition = copy.deepcopy(o.definition)
            definition["template_id"] = t.id
            outs.append(DefaultOutput(o.name.strip(), definition))
        t.outputs = outs

    # ------------------------------------------------------------------------------------------ preview (DO-8)
    def _clear_preview(self, text: str | None) -> None:
        self.preview_result = None
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.table.setEnabled(True)
        if text is not None:
            self.preview_info.setText(text)
        self.screen.bridge.set_allowed(self.preview_button, self.latest is not None and bool(self.outputs))

    def preview(self) -> None:
        if self.latest is None or not self._store() or self.selected < 0:
            return
        try:
            definition = Definition.from_dict(self.outputs[self.selected].definition)
            d.check(definition, self.template.columns, output=True)
        except DefinitionError as e:
            self.show_error(str(e))
            return
        self.show_error("")
        columns, data = self.template.columns, self.latest.data
        self.progress.show()

        def done(p: manage.Preview):
            self.progress.hide()
            self.show_preview(p)

        def failed(e):
            self.progress.hide()
            from sankalan.ui.screens.common import error_text
            self.show_error(error_text(e))

        job = self.screen.start("Preview output", lambda ctx: manage.output_preview(ctx, definition, columns, data),
                                done, failed, cancellable=True, on_cancelled=lambda: self.progress.hide())
        if job is not None:
            self.progress.bind(job)
        else:
            self.progress.hide()

    def show_preview(self, p: manage.Preview) -> None:
        self.preview_result = p
        self.table.setEnabled(True)
        info = (f"On {self.latest.label} · {formats.count(p.input_rows, 'row')} · "
                f"{formats.count(p.count, 'result row')} · {p.seconds:.1f} s")
        if p.note:
            info += f" · {p.note}"
        if p.count > len(p.rows):
            info += f" · first {formats.number(len(p.rows))} shown"
        self.preview_info.setText(info)
        self.table.setColumnCount(len(p.headers))
        self.table.setHorizontalHeaderLabels(p.headers)
        rows = list(p.rows)
        self.table.setRowCount(len(rows) + (1 if p.total is not None else 0))
        bold = QFont(self.table.font())
        bold.setWeight(QFont.Weight.Medium)
        for r, row in enumerate(rows):
            depth, values = row[0], row[1:]
            for c, v in enumerate(values):
                group = c < p.groups
                text = cell_text(v, p.kinds[c], group)
                if group and depth < p.groups and c >= depth:
                    text = d.SUBTOTAL_LABEL if c == depth else ""
                self._put(r, c, text, p.kinds[c], bold if depth < p.groups else None)
        if p.total is not None:
            r = len(rows)
            for c in range(len(p.headers)):
                if c < p.groups:
                    text = d.TOTAL_LABEL if c == 0 else ""
                else:
                    text = cell_text(p.total[c - p.groups], p.kinds[c], False)
                self._put(r, c, text, p.kinds[c], bold)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _put(self, r: int, c: int, text: str, kind: tuple, font) -> None:
        item = QTableWidgetItem(text)
        right = kind[0] in (NUMBER, "count")
        item.setTextAlignment((Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft)
                              | Qt.AlignmentFlag.AlignVCenter)
        if font is not None:
            item.setFont(font)
            item.setBackground(QColor(theme.HEADER_BG))
        self.table.setItem(r, c, item)

    def preview_rows(self) -> list[list[str]]:
        return [[self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(self.table.columnCount())]
                for r in range(self.table.rowCount())]
