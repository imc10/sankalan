"""6.4 the Rows view's own parts (Feature Spec A2 2, ROW-7 to ROW-11; Tech spec A2 10.5).

The Rows view is a mode of New analysis (``ui/screens/analysis.py``), which keeps the data selection, the filters,
Run and the Jobs. This module holds what only the Rows view has:

* ``ColumnsSection``: every non-removed column with a tick and ↑ ↓, "N of M ticked", and the tick Show them on
  screen for the source columns. ``columns_changed`` redraws the grid; it never starts a Job (ROW-9).
* ``RowsResult``: the result header (match count, runs, rows searched, time; Export rows (.csv)), the grid (frozen
  first column, no sorting, widths from the column type), the footer, and the states of Feature Spec A2 2.4.
"""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QStackedWidget,
                               QVBoxLayout, QWidget)

from sankalan import rowsview
from sankalan.model.template import DATE, NUMBER, Column
from sankalan.ui import theme
from sankalan.ui.widgets.controls import heading, icon_button, note, primary
from sankalan.ui.widgets.paged_grid import GridColumn, PagedGrid, PagedModel
from sankalan.ui.widgets.progress import ProgressPanel

EXPORT_ROWS = "Export rows (.csv)"
SHOW_SOURCE = "Show them on screen"
SOURCE_NOTE = "Source File, Source Sheet, Source Row and Run ID are always in the export."
WIDTHS = {"Text": 180, NUMBER: 140, DATE: 120}
SOURCE_WIDTHS = {"_file": 200, "_sheet": 120, "_row": 100, "_run": 90}


def ticked_text(ticked: int, total: int) -> str:
    return f"{ticked} of {total} ticked"


def one_line(value) -> str:
    """Long text on one line (2.2): line breaks shown as spaces; the full value on hover."""
    return "" if value is None else str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


SUMMARY, ROWS = "summary", "rows"


class ModeSwitch(QWidget):
    """"Summary | Rows" beside New analysis's title (ROW-1). ``picked(mode)`` when the user picks the other one."""
    picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.buttons: dict[str, QPushButton] = {}
        for mode, label, side in ((SUMMARY, "Summary", "left"), (ROWS, "Rows", "right")):
            b = QPushButton(label, self)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(28)
            b.setMinimumWidth(84)
            radius = ("border-top-left-radius: 6px; border-bottom-left-radius: 6px;" if side == "left" else
                      "border-top-right-radius: 6px; border-bottom-right-radius: 6px;")
            b.setStyleSheet(f"QPushButton {{ border: 1px solid {theme.INPUT_BORDER}; border-radius: 0; {radius} "
                            f"background: {theme.WHITE}; color: {theme.TEXT}; padding: 0 12px; }}"
                            f"QPushButton:checked {{ border-color: {theme.TEAL}; background: {theme.TINT}; "
                            f"color: {theme.TEAL_DARK}; font-weight: 500; }}"
                            f"QPushButton:disabled {{ color: {theme.MUTED}; }}")
            b.clicked.connect(lambda _c=False, m=mode: self._clicked(m))
            lay.addWidget(b)
            self.buttons[mode] = b
        self.mode = SUMMARY
        self.buttons[SUMMARY].setChecked(True)

    def _clicked(self, mode: str) -> None:
        self.set_mode(self.mode)                    # the screen decides; it calls set_mode when it switches
        if mode != self.mode:
            self.picked.emit(mode)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        for m, b in self.buttons.items():
            b.setChecked(m == mode)


class _ColumnRow(QWidget):
    def __init__(self, col: Column, parent=None):
        super().__init__(parent)
        self.col = col
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.tick = QCheckBox(col.name, self)
        self.tick.setChecked(True)
        lay.addWidget(self.tick, 1)
        self.up = icon_button("up", f"Move {col.name} up", self)
        self.down = icon_button("down", f"Move {col.name} down", self)
        lay.addWidget(self.up)
        lay.addWidget(self.down)


class ColumnsSection(QWidget):
    """ROW-7, ROW-8: the columns of the grid and the export, in order."""
    columns_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(heading("Columns", self, theme.GRID_TEXT_PX))
        head.addStretch(1)
        self.count = note("", self)
        head.addWidget(self.count)
        lay.addLayout(head)
        self.rows_lay = QVBoxLayout()
        self.rows_lay.setSpacing(2)
        lay.addLayout(self.rows_lay)
        self.error = note("", self, "error")
        self.error.hide()
        lay.addWidget(self.error)
        self.source_note = note(SOURCE_NOTE, self)
        self.source_note.setWordWrap(True)
        lay.addWidget(self.source_note)
        self.show_source = QCheckBox(SHOW_SOURCE, self)
        self.show_source.toggled.connect(lambda _on: self.columns_changed.emit())
        lay.addWidget(self.show_source)
        self.rows: list[_ColumnRow] = []

    def set_columns(self, columns: list[Column]) -> None:
        """Every non-removed column, all ticked, in template order (ROW-7); Show them on screen off (ROW-8)."""
        for r in self.rows:
            self.rows_lay.removeWidget(r)
            r.deleteLater()
        self.rows = []
        for c in columns:
            if c.removed:
                continue
            row = _ColumnRow(c, self)
            row.tick.toggled.connect(lambda _on: self._changed())
            row.up.clicked.connect(lambda _c=False, r=row: self.move(r.col.id, -1))
            row.down.clicked.connect(lambda _c=False, r=row: self.move(r.col.id, 1))
            self.rows.append(row)
            self.rows_lay.addWidget(row)
        with QSignalBlocker(self.show_source):
            self.show_source.setChecked(False)
        self.set_error("")
        self._count()

    def ticked(self) -> list[str]:
        """Ticked column IDs, in the chosen order."""
        return [r.col.id for r in self.rows if r.tick.isChecked()]

    def order(self) -> list[str]:
        return [r.col.id for r in self.rows]

    @property
    def source(self) -> bool:
        return self.show_source.isChecked()

    def tick(self, column_id: str, on: bool = True) -> None:
        next(r for r in self.rows if r.col.id == column_id).tick.setChecked(on)

    def tick_all(self, on: bool) -> None:
        for r in self.rows:
            with QSignalBlocker(r.tick):
                r.tick.setChecked(on)
        self._changed()

    def move(self, column_id: str, step: int) -> None:
        i = next(k for k, r in enumerate(self.rows) if r.col.id == column_id)
        j = i + step
        if not 0 <= j < len(self.rows):
            return
        row = self.rows.pop(i)
        self.rows.insert(j, row)
        self.rows_lay.removeWidget(row)
        self.rows_lay.insertWidget(j, row)
        self.columns_changed.emit()

    def set_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def _changed(self) -> None:
        if self.ticked():
            self.set_error("")
        self._count()
        self.columns_changed.emit()

    def _count(self) -> None:
        self.count.setText(ticked_text(len(self.ticked()), len(self.rows)))


class RowsResult(QWidget):
    """The Rows view's result panel (6.4): header line and Export rows, progress, the grid and its footer."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget(self)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 12, 10)
        bl.setSpacing(12)
        self.summary = QLabel("", bar)
        self.summary.setStyleSheet(f"font-size: {theme.SMALL_PX}px; color: {theme.SUBTLE};")
        bl.addWidget(self.summary, 1)
        self.stale_note = QLabel("", bar)
        self.stale_note.setStyleSheet(f"font-size: {theme.SMALL_PX}px; color: {theme.WARNING}; font-weight: 500;")
        self.stale_note.hide()
        bl.addWidget(self.stale_note)
        self.export_button = primary(EXPORT_ROWS, bar, "secondary")
        bl.addWidget(self.export_button)
        lay.addWidget(bar)
        self.progress = ProgressPanel(self)
        self.progress.setContentsMargins(16, 0, 16, 12)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.stack = QStackedWidget(self)
        self.empty = QWidget(self.stack)
        el = QVBoxLayout(self.empty)
        el.setContentsMargins(32, 0, 32, 0)
        el.addStretch(1)
        self.message = QLabel(rowsview.EMPTY, self.empty)
        self.message.setStyleSheet(f"font-size: 15px; font-weight: 500; color: {theme.TEXT};")
        self.message.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.message.setWordWrap(True)
        el.addWidget(self.message)
        el.addStretch(2)
        self.stack.addWidget(self.empty)
        self.page = QWidget(self.stack)
        pl = QVBoxLayout(self.page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        self.model = PagedModel(bridge, [], None, parent=self) if bridge is not None else None
        self.grid = PagedGrid(self.model, self.page) if self.model is not None else QWidget(self.page)
        if isinstance(self.grid, PagedGrid):
            self.grid.setFrameShape(QFrame.Shape.NoFrame)
            self.grid.set_sorting(False)
            self.grid.resizable = True
            self.grid.set_frozen(True)
        pl.addWidget(self.grid, 1)
        self.footer = note("", self.page)
        self.footer.setContentsMargins(16, 6, 16, 6)
        pl.addWidget(self.footer)
        self.stack.addWidget(self.page)
        self.dim = QGraphicsOpacityEffect(self.page)
        self.dim.setOpacity(1.0)
        self.page.setGraphicsEffect(self.dim)
        lay.addWidget(self.stack, 1)
        if bridge is not None:
            bridge.guard(self.export_button, False)

    # -------------------------------------------------------------------------------------------- grid
    def show_outcome(self, outcome: rowsview.RowsOutcome, ticked: list[str], source: bool) -> None:
        """A new result: the table's rows read a page at a time, the chosen columns shown."""
        self.summary.setText(outcome.summary())
        self.footer.setText(outcome.footer())
        if self.model is not None:
            self.model.set_columns([], rowsview.RowsSource(outcome))
            self.set_columns(outcome, ticked, source)

    def set_columns(self, outcome: rowsview.RowsOutcome, ticked: list[str], source: bool) -> None:
        """ROW-9: the ticked columns in order, then the source columns when shown, from the rows already read (no
        Job). The first column stays frozen; widths come from the column type and can be dragged."""
        if self.model is None:
            return
        cells = rowsview.display_columns(outcome.columns)
        where = {key: i for i, (key, _t) in enumerate(cells)}
        by_id = {c.id: c for c in outcome.columns}
        cols, pos = [], []
        for cid in ticked:
            if cid not in where:
                continue
            c = by_id[cid]
            cols.append(GridColumn(cid, c.name, width=WIDTHS.get(c.type, 160), sortable=False,
                                   right=c.type == NUMBER, fmt=one_line if c.type not in (NUMBER, DATE) else None))
            pos.append(where[cid])
        if source and cols:
            for key, title in cells[-4:]:
                cols.append(GridColumn(key, title, width=SOURCE_WIDTHS[key], sortable=False, right=key == "_row",
                                       fmt=one_line))
                pos.append(where[key])
        self.model.rearrange(cols, pos)
        self.grid.apply_widths()
        self.grid.set_frozen(bool(cols))

    def headers(self) -> list[str]:
        if self.model is None:
            return []
        return [c.title for c in self.model.columns]

    def shown_rows(self) -> list[tuple | None]:
        """The rows loaded in the grid, as shown (tests)."""
        if self.model is None:
            return []
        out = []
        for r in range(self.model.rowCount()):
            v = self.model.row_values(r)
            out.append(None if v is None else tuple(self.model.data(self.model.index(r, c))
                                                    for c in range(self.model.columnCount())))
        return out

    # -------------------------------------------------------------------------------------------- states (2.4)
    def show_message(self, text: str) -> None:
        self.message.setText(text)
        self.stack.setCurrentWidget(self.empty)

    def show_grid(self) -> None:
        self.stack.setCurrentWidget(self.page)

    def set_greyed(self, greyed: bool, note_text: str = "") -> None:
        self.dim.setOpacity(0.4 if greyed else 1.0)
        self.stale_note.setText(note_text)
        self.stale_note.setVisible(bool(note_text))

    @property
    def greyed(self) -> bool:
        return self.dim.opacity() < 1.0
