"""App settings (UX-11, ND-1, DEP-04/06…09): the data folder with Change…, and the app version. Nothing else.

Change… picks a folder that is new or empty, checks it (network paths refused, OneDrive warned, T25), then moves
the data as a long Job with its progress in this dialog.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton

from sankalan import __version__
from sankalan.db.storage import MoveRefused
from sankalan.jobs import JobBusy
from sankalan.ui.dialogs.base import Dialog, ask
from sankalan.ui.jobs import JobBridge
from sankalan.ui.widgets.progress import ProgressPanel

MOVED = "Data folder moved."
FAILED = "The data folder couldn't be moved. Your data is unchanged, in the old folder."
CANCELLED = "Move cancelled. Your data is unchanged, in the old folder."


def choose_folder(parent, start: str) -> str | None:
    path = QFileDialog.getExistingDirectory(parent, "Choose a new or empty folder for your data", start)
    return path or None


class AppSettingsDialog(Dialog):
    dataFolderChanged = Signal(str)

    def __init__(self, storage, bridge: JobBridge, parent=None,
                 chooser: Callable[[object, str], str | None] = choose_folder):
        super().__init__("App settings", parent, width=560)
        self.storage = storage
        self.bridge = bridge
        self.chooser = chooser
        self.moving = False

        cap = QLabel("Data folder", self)
        cap.setProperty("kind", "small")
        self.body.addWidget(cap)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.folder = QLineEdit(str(storage.folder.path), self)
        self.folder.setObjectName("data-folder")
        self.folder.setReadOnly(True)
        self.folder.setCursorPosition(0)
        row.addWidget(self.folder, 1)
        self.change = QPushButton("Change…", self)
        self.change.setProperty("kind", "secondary")
        self.change.clicked.connect(self.change_folder)
        row.addWidget(self.change)
        self.body.addLayout(row)
        bridge.guard(self.change)

        self.message = QLabel("", self)
        self.message.setObjectName("settings-message")
        self.message.setWordWrap(True)
        self.message.hide()
        self.body.addWidget(self.message)

        self.progress = ProgressPanel(self, cancel_text="Cancel move", unit="bytes")
        self.progress.hide()
        self.body.addWidget(self.progress)

        self.version = QLabel(f"Version {__version__}", self)
        self.version.setObjectName("app-version")
        self.version.setProperty("kind", "small")
        self.body.addWidget(self.version)
        self.close_button = self.add_button("Close", None, self.accept, default=True)

    # ------------------------------------------------------------------------------------------ Change…
    def _say(self, text: str, kind: str = "error") -> None:
        self.message.setProperty("kind", kind)
        self.message.setText(text)
        self.message.setVisible(bool(text))
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)

    def change_folder(self) -> None:
        self._say("")
        picked = self.chooser(self, str(Path(self.storage.folder.path).parent))
        if not picked:
            return
        check = self.storage.check_move(Path(picked))
        if not check.ok:
            self._say(check.refusal)
            return
        if check.warnings:
            key = ask(self, "Use a synced folder?", "\n\n".join(check.warnings),
                      [("cancel", "Cancel", None), ("move", "Move anyway", "primary")])
            if key != "move":
                return
        self.start_move(Path(picked))

    def start_move(self, dest: Path) -> None:
        try:
            job = self.bridge.start("Move data folder", self.storage.move_work(dest),
                                    on_done=self._moved, on_failed=self._failed, on_cancelled=self._cancelled,
                                    on_finished=lambda _j: self._ended(), origin=self.show)
        except JobBusy:
            self._say("Another operation is running")
            return
        self.moving = True
        self.close_button.setEnabled(False)
        self.progress.show()
        self.progress.bind(job)

    def _moved(self, dest) -> None:
        self.folder.setText(str(dest))
        self._say(MOVED, "subtitle")
        self.dataFolderChanged.emit(str(dest))

    def _failed(self, error) -> None:
        self._say(error.message if isinstance(error, MoveRefused) else FAILED)

    def _cancelled(self) -> None:
        self._say(CANCELLED, "subtitle")

    def _ended(self) -> None:
        self.moving = False
        self.close_button.setEnabled(True)
        self.progress.hide()

    # ------------------------------------------------------------------------------------------ closing
    def reject(self) -> None:
        if not self.moving:                     # Esc and ✕ wait for the move (its progress is here)
            super().reject()

    def keyPressEvent(self, event) -> None:
        if self.moving and event.key() == Qt.Key.Key_Escape:
            return
        super().keyPressEvent(event)
