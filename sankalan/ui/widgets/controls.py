"""Small controls from the canvas: the search box, icon buttons (↑ ↓ ✕ ⋯), removable chips (aliases, sheet names),
a section heading, a tab bar with counts, and the "Unsaved changes · Discard · Save" bar."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QTabBar,
                               QToolButton, QVBoxLayout, QWidget)

from sankalan.ui import theme
from sankalan.ui.widgets import icons


class SearchBox(QLineEdit):
    """260 px search field with the magnifier icon (C1, C2, C4)."""

    def __init__(self, placeholder: str, parent=None, width: int = 260):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAccessibleName(placeholder)
        self.setClearButtonEnabled(True)
        self.setFixedWidth(width)
        self.setFixedHeight(theme.BUTTON_HEIGHT)
        self.addAction(icons.icon("search", theme.SUBTLE, 16), QLineEdit.ActionPosition.LeadingPosition)


def icon_button(name: str, tip: str, parent=None, size: int = 28, colour: str = theme.MUTED) -> QToolButton:
    b = QToolButton(parent)
    b.setIcon(icons.icon(name, colour, 16, disabled_colour=theme.DISABLED_TEXT))
    b.setIconSize(QSize(16, 16))
    b.setFixedSize(size, size)
    b.setToolTip(tip)
    b.setAccessibleName(tip)
    b.setAutoRaise(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"QToolButton {{ border: 0; border-radius: 6px; background: transparent; }}"
                    f"QToolButton:hover {{ background: {theme.HEADER_BG}; }}")
    return b


def primary(label: str, parent=None, kind: str = "primary") -> QPushButton:
    b = QPushButton(label, parent)
    b.setProperty("kind", kind)
    return b


def plus_button(label: str, parent=None) -> QPushButton:
    """"+ Add filter" style: a plain teal text button."""
    b = QPushButton(f"+ {label}", parent)
    b.setProperty("kind", "plain")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def heading(text: str, parent=None, px: int = theme.BODY_PX) -> QLabel:
    lab = QLabel(text, parent)
    lab.setStyleSheet(f"font-size: {px}px; font-weight: 500; color: {theme.TEXT};")
    return lab


def note(text: str, parent=None, kind: str = "small") -> QLabel:
    lab = QLabel(text, parent)
    lab.setProperty("kind", kind)
    lab.setWordWrap(True)
    return lab


def panel(parent=None) -> QFrame:
    """A bordered 8 px panel (lists, detail panels)."""
    f = QFrame(parent)
    f.setObjectName("Panel")
    f.setStyleSheet(f"#Panel {{ border: 1px solid {theme.BORDER}; border-radius: 8px; background: {theme.WHITE}; }}")
    return f


class Chip(QFrame):
    removed = Signal(str)

    def __init__(self, text: str, parent=None, removable: bool = True):
        super().__init__(parent)
        self.value = text
        self.setObjectName("Chip")
        self.setStyleSheet(f"#Chip {{ background: {theme.HEADER_BG}; border: 1px solid {theme.BORDER}; "
                           f"border-radius: 6px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 4, 2)
        lay.setSpacing(4)
        self.label = QLabel(text, self)
        self.label.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; border: 0;")
        lay.addWidget(self.label)
        self.remove = icon_button("close", f"Remove {text}", self, 22)
        self.remove.clicked.connect(lambda: self.removed.emit(self.value))
        self.remove.setVisible(removable)
        lay.addWidget(self.remove)


class ChipList(QWidget):
    """Removable values with "+ Add …": aliases (C4-11), sheet names (3.4). ``changed`` after every edit."""
    changed = Signal()

    def __init__(self, add_label: str, parent=None, placeholder: str = "", check: Callable[[str], str | None] = None):
        super().__init__(parent)
        self.values: list[str] = []
        self.check = check
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)
        self._chips = QHBoxLayout()
        self._chips.setSpacing(6)
        self._chips.addStretch(1)
        self._lay.addLayout(self._chips)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setAccessibleName(add_label)
        self.edit.returnPressed.connect(self.add_typed)
        self.add_button = plus_button(add_label, self)
        self.add_button.clicked.connect(self.add_typed)
        row.addWidget(self.edit, 1)
        row.addWidget(self.add_button)
        self._lay.addLayout(row)
        self.error = note("", self, "error")
        self.error.hide()
        self._lay.addWidget(self.error)

    def set_values(self, values: list[str]) -> None:
        self.values = list(values)
        self._redraw()

    def add_typed(self) -> bool:
        text = self.edit.text().strip()
        if not text:
            return False
        problem = self.check(text) if self.check else None
        if problem is None and any(v.casefold() == text.casefold() for v in self.values):
            problem = f"{text} is already listed."
        if problem:
            self.error.setText(problem)
            self.error.show()
            return False
        self.error.hide()
        self.values.append(text)
        self.edit.clear()
        self._redraw()
        self.changed.emit()
        return True

    def remove_value(self, value: str) -> None:
        if value in self.values:
            self.values.remove(value)
            self._redraw()
            self.changed.emit()

    def chips(self) -> list[Chip]:
        return [self._chips.itemAt(i).widget() for i in range(self._chips.count())
                if isinstance(self._chips.itemAt(i).widget(), Chip)]

    def _redraw(self) -> None:
        for c in self.chips():
            self._chips.removeWidget(c)
            c.deleteLater()
        for i, v in enumerate(self.values):
            chip = Chip(v, self)
            chip.removed.connect(self.remove_value)
            self._chips.insertWidget(i, chip)


class CountTabs(QTabBar):
    """Template tabs (C4): "Runs · Default outputs 3 · Columns and rules · Settings"."""

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setDocumentMode(True)
        self._labels = list(labels)
        for lab in labels:
            self.addTab(lab)

    def set_count(self, index: int, n: int | None) -> None:
        self.setTabText(index, self._labels[index] + (f"  {n}" if n else ""))


class SaveBar(QWidget):
    """"Unsaved changes · Discard · Save …" at the top right of an editing tab (3.2, 3.3, 3.4)."""

    def __init__(self, save_label: str, note_text: str, parent=None, bridge=None):
        super().__init__(parent)
        self.bridge = bridge
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.note = note(note_text, self, "subtitle")
        self.note.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.note, 1)
        self.dirty_label = QLabel("Unsaved changes", self)
        self.dirty_label.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; color: {theme.WARNING};")
        lay.addWidget(self.dirty_label)
        self.discard = QPushButton("Discard", self)
        self.discard.setProperty("kind", "secondary")
        lay.addWidget(self.discard)
        self.save = primary(save_label, self)
        lay.addWidget(self.save)
        if bridge is not None:
            bridge.guard(self.save)                 # saving runs a Job (SH-02)
        self.set_dirty(False)

    def set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self.dirty_label.setVisible(dirty)
        self.discard.setEnabled(dirty)
        if self.bridge is not None:
            self.bridge.set_allowed(self.save, dirty)
        else:
            self.save.setEnabled(dirty)
