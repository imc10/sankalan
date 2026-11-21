"""Wizard steps (UX-3, UX-8): numbered dots joined by lines. Done steps show ✓, the current step is teal, a skipped
step (Mapping when every header matches, Outputs when the template has none) shows "–" with a dashed outline."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from sankalan.ui import theme
from sankalan.ui.widgets import icons

DONE, CURRENT, PENDING, SKIPPED = "done", "current", "pending", "skipped"


class StepBar(QWidget):
    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self.labels = list(labels)
        self._current = 0
        self._skipped: set[int] = set()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.dots: list[QLabel] = []
        self.names: list[QLabel] = []
        for i, label in enumerate(self.labels):
            dot = QLabel(self)
            dot.setFixedSize(24, 24)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name = QLabel(label, self)
            lay.addWidget(dot)
            lay.addWidget(name)
            self.dots.append(dot)
            self.names.append(name)
            if i < len(self.labels) - 1:
                line = QFrame(self)
                line.setFixedSize(28, 1)
                line.setStyleSheet(f"background: {theme.INPUT_BORDER};")
                lay.addWidget(line)
        lay.addStretch(1)
        self._paint()

    def set_label(self, index: int, label: str) -> None:
        """Rename a step: the New run wizard's third step is Validate or Load (T44)."""
        self.labels[index] = label
        self.names[index].setText(label)

    def set_current(self, index: int) -> None:
        self._current = index
        self._paint()

    def set_skipped(self, indexes) -> None:
        self._skipped = set(indexes)
        self._paint()

    def state(self, index: int) -> str:
        if index in self._skipped:
            return SKIPPED
        if index == self._current:
            return CURRENT
        return DONE if index < self._current else PENDING

    def _paint(self) -> None:
        for i, (dot, name) in enumerate(zip(self.dots, self.names)):
            s = self.state(i)
            if s == CURRENT:
                bg, fg, border, text, weight, colour = theme.TEAL, theme.WHITE, f"1px solid {theme.TEAL}", str(i + 1), 500, theme.TEXT
            elif s == DONE:
                bg, fg, border, text, weight, colour = theme.TINT, theme.TEAL_DARK, f"1px solid {theme.TINT}", "✓", 400, theme.SUBTLE
            elif s == SKIPPED:
                bg, fg, border, text, weight, colour = theme.WHITE, theme.DISABLED_TEXT, f"1px dashed {theme.INPUT_BORDER}", "–", 400, theme.DISABLED_TEXT
            else:
                bg, fg, border, text, weight, colour = theme.WHITE, theme.SUBTLE, f"1px solid {theme.INPUT_BORDER}", str(i + 1), 400, theme.SUBTLE
            if text == "✓":                 # Plex has no ✓ glyph: draw the canvas check
                dot.setPixmap(icons.pixmap("check", theme.TEAL_DARK, 14, stroke=2.2))
            else:
                dot.setText(text)
            dot.setProperty("state", s)
            dot.setStyleSheet(f"background: {bg}; color: {fg}; border: {border}; border-radius: 12px; "
                              f"font-size: {theme.SMALL_PX}px; font-weight: 500;")
            name.setStyleSheet(f"color: {colour}; font-size: {theme.GRID_TEXT_PX}px; font-weight: {weight};")
            name.setToolTip("Skipped" if s == SKIPPED else "")
            name.setAccessibleDescription({CURRENT: "current step", DONE: "done", SKIPPED: "skipped",
                                           PENDING: ""}[s])
