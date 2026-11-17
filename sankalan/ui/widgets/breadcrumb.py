"""Breadcrumbs (GEN-06): "Clients › Acme Traders › Sales Register › R-0001"; every part but the last opens its level."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from sankalan.ui import theme

SEPARATOR = "›"


@dataclass(frozen=True)
class Crumb:
    label: str
    open: Callable[[], None] | None = None      # None for the current level


class Breadcrumb(QWidget):
    def __init__(self, crumbs: list[Crumb] | None = None, parent=None):
        super().__init__(parent)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)
        self.parts: list[QLabel] = []
        self.set_crumbs(crumbs or [])

    def set_crumbs(self, crumbs: list[Crumb]) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().hide()            # deleted on the next loop pass; never drawn under the new ones
                item.widget().deleteLater()
        self.parts = []
        self.crumbs = list(crumbs)
        for i, c in enumerate(self.crumbs):
            if i:
                sep = QLabel(SEPARATOR, self)
                sep.setStyleSheet(f"color: {theme.SUBTLE}; font-size: {theme.GRID_TEXT_PX}px;")
                self._lay.addWidget(sep)
            last = i == len(self.crumbs) - 1
            lab = QLabel(self)
            lab.setObjectName(f"crumb-{i}")
            if c.open is not None and not last:
                lab.setText(f'<a href="#" style="color:{theme.TEAL}; text-decoration:none">{escape(c.label)}</a>')
                lab.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse
                                            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
                lab.setCursor(Qt.CursorShape.PointingHandCursor)
                lab.linkActivated.connect(lambda _h, fn=c.open: fn())
            else:
                lab.setTextFormat(Qt.TextFormat.PlainText)
                lab.setText(c.label)
                lab.setAccessibleDescription("current page")
            lab.setStyleSheet(f"color: {theme.MUTED}; font-size: {theme.GRID_TEXT_PX}px;")
            self._lay.addWidget(lab)
            self.parts.append(lab)
        self._lay.addStretch(1)
        self.setVisible(bool(self.crumbs))

    def text(self) -> str:
        return f" {SEPARATOR} ".join(c.label for c in self.crumbs)

    def activate(self, index: int) -> None:
        """Open part ``index`` as a click would (keyboard and tests)."""
        c = self.crumbs[index]
        if c.open is not None and index < len(self.crumbs) - 1:
            c.open()
