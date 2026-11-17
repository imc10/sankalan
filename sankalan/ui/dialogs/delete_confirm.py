"""DeleteConfirm (UI-8, dialogs 7.2, 7.3): lists exactly what will be deleted; the red button stays disabled until
"I understand this can't be undone" is ticked."""
from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QCheckBox, QLabel

from sankalan.ui import theme
from sankalan.ui.dialogs.base import Dialog

UNDERSTAND = "I understand this can't be undone"


class DeleteConfirm(Dialog):
    def __init__(self, title: str, intro: str, items: list[str], *, note: str | None = None,
                 button: str = "Delete", parent=None):
        super().__init__(title, parent)
        self.text(intro)
        self.items = QLabel(self)
        self.items.setObjectName("delete-items")
        self.items.setText("<ul style='margin:0; -qt-list-indent:1'>"
                           + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>")
        self.items.setStyleSheet(f"background: {theme.ERROR_TINT}; color: {theme.ERROR_TEXT}; border-radius: 8px;"
                                 f" padding: 12px 16px; font-size: {theme.BODY_PX}px;")
        self.items.setWordWrap(True)
        self.items.setAccessibleName("What will be deleted")
        self.listed = list(items)
        self.body.addWidget(self.items)
        if note:
            self.text(note)
        self.understand = QCheckBox(UNDERSTAND, self)
        self.body.addWidget(self.understand)
        self.add_button("Cancel", None, self.reject)
        self.delete_button = self.add_button(button, "destructive", self.accept)
        self.delete_button.setDefault(False)
        self.delete_button.setAutoDefault(False)
        self.delete_button.setEnabled(False)
        self.understand.toggled.connect(self.delete_button.setEnabled)
