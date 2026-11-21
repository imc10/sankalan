"""Dialog look (canvas): 500 px wide, 24 px padding, an 18 px title, buttons at the bottom right."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from sankalan.ui import theme


class Dialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None, width: int = theme.DIALOG_WIDTH):
        super().__init__(parent)
        self.setWindowTitle(title)             # Windows shows it in the dialog's own title bar
        self.setModal(True)
        self.setFixedWidth(width)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.body = QVBoxLayout(self)
        p = theme.DIALOG_PADDING
        self.body.setContentsMargins(p, p, p, p)
        self.body.setSpacing(16)
        self.title = QLabel(title, self)
        self.title.setProperty("kind", "h2")
        self.title.setWordWrap(True)
        self.body.addWidget(self.title)
        self._buttons = QHBoxLayout()
        self._buttons.setSpacing(theme.CONTROL_GAP)
        self._buttons.addStretch(1)
        self._buttons_added = False
        self.buttons: dict[str, QPushButton] = {}

    def text(self, text: str, kind: str = "body") -> QLabel:
        lab = QLabel(text, self)
        lab.setProperty("kind", kind)
        lab.setWordWrap(True)
        lab.setTextFormat(Qt.TextFormat.PlainText)
        self.body.addWidget(lab)
        return lab

    def add_button(self, label: str, kind: str | None = None, on_click: Callable[[], None] | None = None,
                   default: bool = False) -> QPushButton:
        if not self._buttons_added:
            self.body.addSpacing(4)
            self.body.addLayout(self._buttons)
            self._buttons_added = True
        b = QPushButton(label, self)
        if kind:
            b.setProperty("kind", kind)
        b.setDefault(default)
        b.setAutoDefault(default)
        if on_click is not None:
            b.clicked.connect(on_click)
        self._buttons.addWidget(b)
        self.buttons[label] = b
        return b


class Choice(Dialog):
    """A message with buttons; ``choice`` is the key of the button pressed (None when closed with Esc or ✕)."""

    def __init__(self, title: str, text: str, options: list[tuple[str, str, str | None]], parent=None,
                 width: int = 480):
        super().__init__(title, parent, width)
        self.choice: str | None = None
        self.message = text
        if text:
            self.text(text)
        for i, (key, label, kind) in enumerate(options):
            # clicked(bool) passes `checked` as the first argument: without `_c` it would overwrite `k` (False)
            self.add_button(label, kind, lambda _c=False, k=key: self._pick(k), default=(i == len(options) - 1))

    def _pick(self, key: str) -> None:
        self.choice = key
        self.accept()


# Tests replace this to answer prompts without showing them: ``fn(dialog) -> key | None``.
answer_hook: Callable[["Choice"], str | None] | None = None


def ask(parent, title: str, text: str, options: list[tuple[str, str, str | None]], width: int = 480) -> str | None:
    """Show a ``Choice`` and return the key of the button pressed. ``options``: (key, label, kind), shown left
    to right; the last is the default."""
    dlg = Choice(title, text, options, parent, width)
    if answer_hook is not None:
        result = answer_hook(dlg)
        dlg.deleteLater()
        return result
    dlg.exec()
    return dlg.choice
