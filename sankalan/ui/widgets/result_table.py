"""A default output's rows as a table (4.4 Outputs step, 5.1 Outputs tab): group values, measures, subtotal rows in
medium weight, and the grand total pinned as the last row. Values formatted per UI-7."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from sankalan.model import definition as d
from sankalan.model.template import NUMBER
from sankalan.ui import theme


from sankalan.formats import result_cell as cell_text


class ResultTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, 0, parent)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setShowGrid(False)
        self.preview = None

    def clear_result(self) -> None:
        self.preview = None
        self.clear()
        self.setRowCount(0)
        self.setColumnCount(0)

    def show_result(self, p) -> None:
        """``p``: a ``manage.Preview`` (headers, kinds, rows as (_depth, values…), total, groups)."""
        self.preview = p
        self.clear()
        self.setColumnCount(len(p.headers))
        self.setHorizontalHeaderLabels(p.headers)
        rows = list(p.rows)
        self.setRowCount(len(rows) + (1 if p.total is not None else 0))
        bold = QFont(self.font())
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
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _put(self, r: int, c: int, text: str, kind: tuple, font) -> None:
        item = QTableWidgetItem(text)
        right = kind[0] in (NUMBER, "count")
        item.setTextAlignment((Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft)
                              | Qt.AlignmentFlag.AlignVCenter)
        if font is not None:
            item.setFont(font)
            item.setBackground(QColor(theme.HEADER_BG))
        self.setItem(r, c, item)

    def rows(self) -> list[list[str]]:
        return [[self.item(r, c).text() if self.item(r, c) else "" for c in range(self.columnCount())]
                for r in range(self.rowCount())]
