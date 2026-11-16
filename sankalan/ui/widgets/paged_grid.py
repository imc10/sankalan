"""PagedGrid: a table that fetches its rows a page at a time through quiet Jobs (UX §2, V3-1).

The screen supplies a ``PageSource``: ``count(ctx, sort)`` and ``page(ctx, offset, limit, sort)``, both run as quiet
Jobs (they call the query layer; the grid never sees SQL). Rows not loaded yet show blank until their page
arrives. Clicking a sortable header asks the source for a new order and drops the loaded pages.

Values are formatted on screen with ``sankalan.formats`` (UI-7): numbers with international grouping, dates
DD-MM-YYYY, whatever the Windows region. Rows and header are 40 px (GEN-05).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Protocol, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QStyledItemDelegate, QTableView

import shiboken6

from sankalan import formats
from sankalan.jobs import JobContext
from sankalan.ui import theme
from sankalan.ui.jobs import JobBridge

PAGE_SIZE = 200
TEXT, NUMBER, INTEGER, DATE, DATETIME = "text", "number", "integer", "date", "datetime"
ACTION, MENU, LINK = "action", "menu", "link"     # a button drawn in the cell ("New run"), the row's menu, a name


@dataclass(frozen=True)
class GridColumn:
    key: str
    title: str
    kind: str = TEXT
    decimals: int | None = None     # Number columns: shown at the column's decimals
    width: int | None = None        # px; None stretches
    sortable: bool = True
    muted: bool = False             # secondary text colour (e.g. dates in the Clients grid)
    fmt: Callable[[Any], str] | None = None         # display text instead of the kind's format
    tooltip: int | None = None      # index in the row of the value shown on hover (e.g. a run's file names)
    colour: Callable[[Any], str | None] | None = None   # text colour from the value (e.g. override status)
    right: bool | None = None       # alignment; None = numbers and dates right


Sort = list[tuple[str, bool]]       # (column key, ascending)


class PageSource(Protocol):
    def count(self, ctx: JobContext, sort: Sort) -> int: ...
    def page(self, ctx: JobContext, offset: int, limit: int, sort: Sort) -> list[Sequence[Any]]: ...


def display(value: Any, column: GridColumn) -> str:
    if column.fmt is not None:
        return column.fmt(value)
    if value is None:
        return ""
    if column.kind == NUMBER:
        return formats.number(value if isinstance(value, Decimal) else Decimal(str(value)), column.decimals)
    if column.kind == INTEGER:
        return formats.number(int(value))
    if column.kind == DATETIME and isinstance(value, dt.datetime):
        return formats.date_time(value)
    if column.kind in (DATE, DATETIME) and isinstance(value, dt.date):
        return formats.date(value)
    return str(value)


class PagedModel(QAbstractTableModel):
    loadingChanged = Signal(bool)
    failed = Signal(object)                 # the error of a failed count or page

    def __init__(self, bridge: JobBridge, columns: list[GridColumn], source: PageSource | None = None,
                 page_size: int = PAGE_SIZE, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.columns = list(columns)
        self.source = source
        self.page_size = page_size
        self.sort_spec: Sort = []
        self._total = 0
        self._pages: dict[int, list[Sequence[Any]]] = {}
        self._wanted: set[int] = set()
        self._in_flight: int | None = None   # page number, or -1 for the count
        self._generation = 0
        self._need_count = False
        bridge.jobFinished.connect(self._job_finished)     # a bound slot: dropped with the model

    # ------------------------------------------------------------------------------------------ loading
    def _job_finished(self, _job) -> None:
        self._pump()

    def set_source(self, source: PageSource | None) -> None:
        self.source = source
        self.refresh()

    def refresh(self) -> None:
        """Count again and drop every loaded page (after a change or a new sort)."""
        self.beginResetModel()
        self._generation += 1
        self._pages.clear()
        self._wanted.clear()
        self._total = 0
        self._in_flight = None
        self._need_count = self.source is not None
        self.endResetModel()
        self._pump()

    @property
    def loading(self) -> bool:
        return self._in_flight is not None or self._need_count or bool(self._wanted)

    @property
    def total(self) -> int:
        return self._total

    def _pump(self) -> None:
        if self._in_flight is not None or self.source is None:
            return
        gen, src, sort = self._generation, self.source, list(self.sort_spec)
        if self._need_count:
            job = self.bridge.try_quiet("Count rows", lambda ctx: src.count(ctx, sort),
                                        on_done=lambda n, g=gen: self._counted(g, n),
                                        on_failed=lambda e, g=gen: self._failed(g, e),
                                        on_cancelled=lambda g=gen: self._retry(g))
            if job is not None:
                self._in_flight = -1
                self.loadingChanged.emit(True)
            return
        if not self._wanted:
            return
        page = min(self._wanted)
        offset, limit = page * self.page_size, self.page_size
        job = self.bridge.try_quiet("Fetch rows", lambda ctx: src.page(ctx, offset, limit, sort),
                                    on_done=lambda rows, g=gen, p=page: self._paged(g, p, rows),
                                    on_failed=lambda e, g=gen: self._failed(g, e),
                                    on_cancelled=lambda g=gen: self._retry(g))
        if job is not None:
            self._in_flight = page
            self.loadingChanged.emit(True)

    def _counted(self, gen: int, n: int) -> None:
        if not shiboken6.isValid(self) or gen != self._generation:
            return
        self._in_flight = None
        self._need_count = False
        if n:
            self.beginInsertRows(QModelIndex(), 0, n - 1)
            self._total = n
            self.endInsertRows()
            self._wanted.add(0)
        self._after_load()

    def _paged(self, gen: int, page: int, rows) -> None:
        if not shiboken6.isValid(self) or gen != self._generation:
            return
        self._in_flight = None
        self._wanted.discard(page)
        self._pages[page] = list(rows)
        first = page * self.page_size
        last = min(self._total, first + self.page_size) - 1
        if last >= first:
            self.dataChanged.emit(self.index(first, 0), self.index(last, len(self.columns) - 1))
        self._after_load()

    def _retry(self, gen: int) -> None:
        if shiboken6.isValid(self) and gen == self._generation:
            self._in_flight = None          # pumped again when the runner is free (jobFinished)

    def _failed(self, gen: int, error) -> None:
        if not shiboken6.isValid(self) or gen != self._generation:
            return
        self._in_flight = None
        self._wanted.clear()
        self._need_count = False
        self.failed.emit(error)
        self.loadingChanged.emit(False)

    def _after_load(self) -> None:
        self._pump()
        if not self.loading:
            self.loadingChanged.emit(False)

    def row_values(self, row: int) -> Sequence[Any] | None:
        page = row // self.page_size
        rows = self._pages.get(page)
        if rows is None:
            if 0 <= row < self._total and page != self._in_flight:
                self._wanted.add(page)
                self._pump()
            return None
        i = row - page * self.page_size
        return rows[i] if i < len(rows) else None

    # ------------------------------------------------------------------------------------------ Qt model
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self._total

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        col = self.columns[index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int((Qt.AlignmentFlag.AlignRight if _right(col) else Qt.AlignmentFlag.AlignLeft)
                       | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole:
            if col.colour is not None:
                values = self.row_values(index.row())
                c = col.colour(values[index.column()]) if values is not None else None
                if c:
                    return QColor(c)
            if col.muted:
                return QColor(theme.MUTED)
            return None
        if role == Qt.ItemDataRole.FontRole and col.kind == LINK:
            return theme.font(theme.GRID_TEXT_PX, medium=True)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            values = self.row_values(index.row())
            if values is None:
                return "" if role == Qt.ItemDataRole.DisplayRole else None
            text = display(values[index.column()], col)
            if role == Qt.ItemDataRole.ToolTipRole:
                if col.tooltip is not None:
                    tip = values[col.tooltip]
                    return (", ".join(tip) if isinstance(tip, (list, tuple)) else str(tip)) or None
                return None if col.kind in (ACTION, MENU) else (text or None)
            return text
        if role == Qt.ItemDataRole.UserRole:
            values = self.row_values(index.row())
            return None if values is None else values[index.column()]
        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        col = self.columns[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return col.title
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int((Qt.AlignmentFlag.AlignRight if _right(col) else Qt.AlignmentFlag.AlignLeft)
                       | Qt.AlignmentFlag.AlignVCenter)
        return None

    def sort(self, column: int, order=Qt.SortOrder.AscendingOrder) -> None:
        col = self.columns[column]
        if not col.sortable:
            return
        self.sort_spec = [(col.key, order == Qt.SortOrder.AscendingOrder)]
        self.refresh()


def _right(col: GridColumn) -> bool:
    return col.right if col.right is not None else col.kind in (NUMBER, INTEGER, DATE, DATETIME)


class ListSource:
    """A ``PageSource`` over rows already in memory (clients, templates, runs): sorted and searched in Python.
    ``search`` keeps the rows for which ``matches(row, text)`` is true. Values sort by type, blanks last."""

    def __init__(self, columns: list[GridColumn], rows: list[Sequence[Any]] | None = None,
                 default_sort: Sort | None = None, matches: Callable[[Sequence[Any], str], bool] | None = None):
        self.keys = [c.key for c in columns]
        self.rows = list(rows or [])
        self.default_sort = list(default_sort or [])
        self.matches = matches
        self.search = ""

    def view(self, sort: Sort) -> list[Sequence[Any]]:
        rows = self.rows
        text = self.search.strip()
        if text and self.matches is not None:
            rows = [r for r in rows if self.matches(r, text)]
        for key, ascending in reversed(sort or self.default_sort):
            i = self.keys.index(key)
            present = [r for r in rows if r[i] is not None]
            blank = [r for r in rows if r[i] is None]
            present.sort(key=lambda r: _sort_key(r[i]), reverse=not ascending)
            rows = present + blank
        return rows

    def count(self, ctx, sort: Sort) -> int:
        return len(self.view(sort))

    def page(self, ctx, offset: int, limit: int, sort: Sort) -> list[Sequence[Any]]:
        return self.view(sort)[offset:offset + limit]


def _sort_key(v):
    if isinstance(v, str):
        return v.casefold()
    if isinstance(v, list):                     # e.g. file names: by how many
        return len(v)
    return v


class CellDelegate(QStyledItemDelegate):
    """Draws ACTION cells as a small outline button and MENU cells as three dots (canvas row actions)."""

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)
        col = index.model().columns[index.column()]
        if col.kind not in (ACTION, MENU):
            return
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not text and col.kind == ACTION:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = option.rect
        if col.kind == ACTION:
            painter.setFont(theme.font(theme.GRID_TEXT_PX, medium=True))
            w = painter.fontMetrics().horizontalAdvance(text) + 24
            box = QRect(r.right() - w - 8, r.center().y() - 14, w, 28)
            painter.setPen(QPen(QColor(theme.TINT_BORDER), 1))
            painter.setBrush(QColor(theme.WHITE))
            painter.drawRoundedRect(box, 6, 6)
            painter.setPen(QColor(theme.TEAL_DARK))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.MUTED))
            cx, cy = r.right() - 20, r.center().y()
            for dx in (-6, 0, 6):
                painter.drawEllipse(cx + dx - 2, cy - 2, 4, 4)
        painter.restore()

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        if index.model().columns[index.column()].kind in (ACTION, MENU):
            option.text = ""


class PagedGrid(QTableView):
    """A ``QTableView`` set up as the canvas grid: 40 px rows and header, no row numbers, whole-row selection,
    scrolling inside its own panel (UI-2)."""
    rowActivated = Signal(int)
    cellClicked = Signal(int, str)      # row, column key (ACTION, MENU and LINK cells)

    def __init__(self, model: PagedModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setFont(theme.font(theme.GRID_TEXT_PX))
        vh = self.verticalHeader()
        vh.hide()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(theme.ROW_HEIGHT)
        vh.setMinimumSectionSize(theme.ROW_HEIGHT)
        hh = self.horizontalHeader()
        hh.setFixedHeight(theme.ROW_HEIGHT)
        hh.setFont(theme.font(theme.GRID_HEADER_PX, medium=True))
        hh.setHighlightSections(False)
        hh.setSectionsClickable(True)
        hh.setSortIndicatorShown(False)
        hh.setStretchLastSection(False)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hh.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)   # no order until a header is clicked
        hh.setSortIndicatorShown(True)
        hh.sectionClicked.connect(self._header_clicked)
        self._sorted: tuple[int, Qt.SortOrder] | None = None
        self.doubleClicked.connect(self._double_clicked)
        self.clicked.connect(self._clicked)
        self.setItemDelegate(CellDelegate(self))
        self.apply_widths()

    def _clicked(self, idx) -> None:
        col = self.model().columns[idx.column()]
        if col.kind in (ACTION, MENU, LINK) and self.model().row_values(idx.row()) is not None:
            self.cellClicked.emit(idx.row(), col.key)

    def _double_clicked(self, idx) -> None:
        if self.model().columns[idx.column()].kind not in (ACTION, MENU):
            self.rowActivated.emit(idx.row())

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.currentIndex().isValid():
            self.rowActivated.emit(self.currentIndex().row())
            return
        super().keyPressEvent(event)

    def cell_rect(self, row: int, key: str) -> QRect:
        keys = [c.key for c in self.model().columns]
        return self.visualRect(self.model().index(row, keys.index(key)))

    def apply_widths(self) -> None:
        hh = self.horizontalHeader()
        for i, c in enumerate(self.model().columns):
            if c.width is None:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                hh.resizeSection(i, c.width)

    def _header_clicked(self, section: int) -> None:
        col = self.model().columns[section]
        if not col.sortable:
            return
        order = Qt.SortOrder.AscendingOrder
        if self._sorted and self._sorted[0] == section and self._sorted[1] == Qt.SortOrder.AscendingOrder:
            order = Qt.SortOrder.DescendingOrder
        self._sorted = (section, order)
        self.horizontalHeader().setSortIndicator(section, order)
        self.model().sort(section, order)
