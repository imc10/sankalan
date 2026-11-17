"""Banners (UX §5, SH-05): success, warning, error and info, with optional action buttons such as "Open folder".

A success banner without actions hides itself after ``SUCCESS_SECONDS``; others stay until closed or the screen
changes.
"""
from __future__ import annotations

import os
import subprocess
import sys
from html import escape
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton

from sankalan.ui import theme
from sankalan.ui.widgets import icons

SUCCESS_SECONDS = 8

_STYLES = {   # background, border, text, icon
    "success": (theme.SUCCESS_TINT, theme.SUCCESS_TINT, theme.SUCCESS_TEXT, theme.SUCCESS),
    "warning": (theme.WARNING_TINT, theme.WARNING_BORDER, theme.WARNING_TEXT, theme.WARNING),
    "error": (theme.ERROR_TINT, "#F4C7C2", theme.ERROR_TEXT, theme.ERROR),
    "info": (theme.TINT, theme.TINT_BORDER, theme.TEAL_DARK, theme.TEAL),
}


def open_folder(path) -> None:
    """Open Explorer at ``path``: a file is selected in its folder, a folder is opened."""
    p = Path(path)
    if sys.platform == "win32":
        if p.is_file():
            subprocess.Popen(["explorer", f"/select,{p}"])
        else:
            os.startfile(str(p))            # noqa: S606 - a local folder chosen by the user
    else:                                   # pragma: no cover - development on other systems
        subprocess.Popen(["xdg-open", str(p if p.is_dir() else p.parent)])


class Banner(QFrame):
    def __init__(self, kind: str, text: str, *, lead: str | None = None,
                 actions: list[tuple[str, Callable[[], None]]] | None = None, closable: bool = True,
                 auto_hide: bool | None = None, parent=None):
        super().__init__(parent)
        self.kind = kind
        bg, border, fg, icon_colour = _STYLES[kind]
        self.setObjectName("Banner")
        self.setAccessibleName(f"{kind} message")
        self.setStyleSheet(f"#Banner {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
                           f"#Banner QLabel {{ color: {fg}; font-size: {theme.GRID_TEXT_PX}px; background: transparent; }}"
                           f"#Banner QPushButton {{ min-height: 30px; max-height: 30px; padding: 0 12px; "
                           f"background: {theme.WHITE}; color: {fg}; border: 1px solid {border}; font-size: 13px;"
                           f" font-weight: 500; }}"
                           f"#Banner QToolButton {{ border: 0; background: transparent; }}")
        self.setMinimumHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 8, 4)
        lay.setSpacing(10)
        ic = QLabel(self)
        ic.setPixmap(icons.pixmap("check" if kind == "success" else "alert", icon_colour, 16, stroke=2.0))
        lay.addWidget(ic)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        body = escape(text)
        self.label.setText(f"<b style='font-weight:500'>{escape(lead)}</b> {body}" if lead else body)
        self.plain_text = f"{lead} {text}" if lead else text
        lay.addWidget(self.label, 1)
        self.buttons: dict[str, QPushButton] = {}
        for label, fn in actions or []:
            b = QPushButton(label, self)
            b.clicked.connect(fn)
            lay.addWidget(b)
            self.buttons[label] = b
        if closable:
            x = QToolButton(self)
            x.setObjectName("banner-close")
            x.setAccessibleName("Close message")
            x.setIcon(icons.icon("close", fg, 14))
            x.clicked.connect(self.dismiss)
            lay.addWidget(x)
        if auto_hide is None:
            auto_hide = kind == "success" and not actions
        if auto_hide:
            QTimer.singleShot(SUCCESS_SECONDS * 1000, self.dismiss)

    def dismiss(self) -> None:
        self.hide()
        self.deleteLater()


def success(text: str, *, lead: str | None = None, folder=None, parent=None) -> Banner:
    """A success banner; ``folder`` (a file or folder path) adds "Open folder" (SH-05, EXP)."""
    actions = [("Open folder", lambda: open_folder(folder))] if folder is not None else None
    return Banner("success", text, lead=lead, actions=actions, parent=parent)
