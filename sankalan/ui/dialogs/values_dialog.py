"""The "Is one of" value picker (ANA-4, A1-08, A1-15): the 1,000 most frequent values in the ticked runs with their
counts, and a search across the whole column. Reading runs as a Job with a busy indicator and Cancel; ticks are kept
across searches, so values found by a search can be added to the top ones."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
                               QWidget)

from sankalan import formats
from sankalan.analyses import DISTINCT_TOP
from sankalan.ui.dialogs.base import Dialog
from sankalan.ui.widgets.controls import SearchBox

SEARCH_DELAY_MS = 300
TOP_NOTE = f"The {formats.number(DISTINCT_TOP)} most frequent values. Search to find others."
NONE_FOUND = "No values match."
STOPPED = "Stopped. Search, or press Read values, to try again."


class ValuesDialog(Dialog):
    """``read(search, on_done, on_failed, on_cancelled)`` starts the Job and returns it (None if it couldn't)."""

    def __init__(self, column_name: str, chosen: list[str], read: Callable, parent=None):
        super().__init__(f"{column_name} is one of", parent, 520)
        self.read = read
        self.chosen: list[str] = list(chosen)
        self.values: list[tuple[str, int]] = []
        self.job = None
        self.search = SearchBox("Search all values", self, width=472)
        self.body.addWidget(self.search)
        self.busy = QWidget(self)
        bl = QHBoxLayout(self.busy)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)
        self.spinner = QProgressBar(self.busy)
        self.spinner.setRange(0, 0)                 # busy indicator
        self.spinner.setTextVisible(False)
        self.spinner.setFixedHeight(8)
        bl.addWidget(QLabel("Reading values…", self.busy))
        bl.addWidget(self.spinner, 1)
        self.stop = QPushButton("Cancel", self.busy)
        self.stop.clicked.connect(self.cancel_read)
        bl.addWidget(self.stop)
        self.body.addWidget(self.busy)
        self.list = QListWidget(self)
        self.list.setMinimumHeight(280)
        self.list.itemChanged.connect(self._ticked)
        self.body.addWidget(self.list)
        self.status = self.text("", "small")
        self.reload = QPushButton("Read values", self)
        self.reload.setProperty("kind", "plain")
        self.reload.clicked.connect(self.start_read)
        self.body.addWidget(self.reload)
        self.add_button("Cancel", None, self.reject)
        self.apply = self.add_button("Apply", "primary", self.accept, default=True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SEARCH_DELAY_MS)
        self._timer.timeout.connect(self.start_read)
        self.search.textEdited.connect(lambda _t: self._timer.start())
        self.search.returnPressed.connect(self.start_read)
        self.finished.connect(lambda _r: self.cancel_read())
        self._show_busy(False)

    # -------------------------------------------------------------------------------------------- reading
    def start_read(self) -> None:
        self._timer.stop()
        if self.job is not None and not self.job.wait(0):
            self.job.cancel()
            self.job.wait(2.0)
        text = self.search.text().strip() or None
        self.job = self.read(text, lambda values, t=text: self._read(t, values), self._failed, self._stopped)
        self._show_busy(self.job is not None)

    def cancel_read(self) -> None:
        if self.job is not None and not self.job.wait(0):
            self.job.cancel()

    def _show_busy(self, busy: bool) -> None:
        self.busy.setVisible(busy)
        self.reload.setVisible(not busy and not self.values)

    def _read(self, search: str | None, values: list[tuple[str, int]]) -> None:
        self.job = None
        self.values = list(values)
        self._show_busy(False)
        self._fill()
        if not values:
            self.status.setText(NONE_FOUND)
        elif search is None and len(values) >= DISTINCT_TOP:
            self.status.setText(TOP_NOTE)
        else:
            self.status.setText(formats.count(len(values), "value"))

    def _failed(self, _error) -> None:
        self.job = None
        self._show_busy(False)
        self.status.setText("The values couldn't be read. Try again.")

    def _stopped(self) -> None:
        self.job = None
        self._show_busy(False)
        self.reload.setVisible(True)
        self.status.setText(STOPPED)

    # -------------------------------------------------------------------------------------------- list
    def _fill(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        shown = {v for v, _n in self.values}
        for v in self.chosen:                   # ticked values a search doesn't show stay listed first
            if v not in shown:
                self._item(v, None)
        for v, n in self.values:
            self._item(v, n)
        self.list.blockSignals(False)

    def _item(self, value: str, n: int | None) -> None:
        text = value if n is None else f"{value}  ·  {formats.number(n)}"
        it = QListWidgetItem(text, self.list)
        it.setData(Qt.ItemDataRole.UserRole, value)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if value in self.chosen else Qt.CheckState.Unchecked)

    def _ticked(self, item: QListWidgetItem) -> None:
        v = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            if v not in self.chosen:
                self.chosen.append(v)
        elif v in self.chosen:
            self.chosen.remove(v)

    def tick(self, value: str, on: bool = True) -> None:
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == value:
                it.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
                return
        raise KeyError(value)

    def shown_values(self) -> list[tuple[str, int]]:
        return list(self.values)
