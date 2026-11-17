"""What the data screens share: starting Jobs through the window's bridge, loading with retry, the name dialog
(new client, rename), delete confirmation (UI-8) and plain error messages."""
from __future__ import annotations

from typing import Any, Callable

import shiboken6
from PySide6.QtWidgets import QLineEdit

from sankalan import log
from sankalan.jobs import JobBusy
from sankalan.manage import DeleteSummary, NameRefused
from sankalan.model.template import TemplateError
from sankalan.ui.dialogs.base import Dialog
from sankalan.ui.dialogs.delete_confirm import DeleteConfirm
from sankalan.ui.jobs import BUSY_TOOLTIP
from sankalan.ui.screens.base import Screen
from sankalan.ui.widgets.banner import Banner

PLAIN_ERRORS = (NameRefused, TemplateError)
SOMETHING_WRONG = "Something went wrong. Try again; if it keeps happening, restart Sankalan."


def error_text(error: BaseException | None) -> str:
    """A message to show: the error's own text for the plain-language errors, else a generic line (SEC-5: no
    engine error text on screen or in the log)."""
    from sankalan.model.definition import DefinitionError
    from sankalan.validation.rules import RuleError
    if isinstance(error, PLAIN_ERRORS + (DefinitionError, RuleError)):
        return str(error)
    if isinstance(error, JobBusy):
        return BUSY_TOOLTIP + "."
    return SOMETHING_WRONG


class DataScreen(Screen):
    """A screen that reads and writes through Jobs."""

    def __init__(self, window=None, parent=None):
        super().__init__(window, parent)
        self._pending: list[tuple] = []
        self._alive = True
        self.dialog: Dialog | None = None          # the dialog open on this screen (tests drive it)
        if self.bridge is not None:
            self.bridge.jobFinished.connect(self._retry_pending)

    @property
    def bridge(self):
        return getattr(self.window_, "bridge", None)

    @property
    def storage(self):
        return getattr(self.window_, "storage", None)

    @property
    def folder(self):
        return self.storage.folder

    def closing(self) -> None:
        self._alive = False
        self._pending.clear()

    @property
    def alive(self) -> bool:
        """Still on screen: callbacks of Jobs that end after the screen (or the window) has gone do nothing."""
        return self._alive and shiboken6.isValid(self)

    # ------------------------------------------------------------------------------------------ Jobs
    def load(self, operation: str, work: Callable, on_done: Callable[[Any], None],
             on_failed: Callable[[BaseException | None], None] | None = None) -> None:
        """A read for the screen as a quiet Job; when the runner is busy it is tried again once it is free."""
        def done(result):
            if self.alive:
                on_done(result)

        def failed(error):
            if not self.alive:
                return
            log.failed(operation, error)
            (on_failed or self._show_error)(error)

        if self.bridge is None or self.bridge.try_quiet(operation, work, on_done=done, on_failed=failed,
                                                         on_cancelled=lambda: self._defer(operation, work, on_done,
                                                                                          on_failed)) is None:
            self._defer(operation, work, on_done, on_failed)

    def _defer(self, *args) -> None:
        if self.alive:
            self._pending.append(args)

    def _retry_pending(self, _job=None) -> None:
        if not self.alive or not self._pending or self.bridge is None or self.bridge.busy:
            return
        pending, self._pending = self._pending, []
        for args in pending:
            self.load(*args)

    def start(self, operation: str, work: Callable, on_done: Callable[[Any], None] | None = None,
              on_failed: Callable[[BaseException | None], None] | None = None, *, cancellable: bool = False,
              on_cancelled: Callable[[], None] | None = None):
        """A long Job (save, delete, test, preview): one at a time (T6), its controls guarded (SH-02)."""
        def done(result):
            if self.alive and on_done is not None:
                on_done(result)

        def failed(error):
            if not isinstance(error, PLAIN_ERRORS):
                log.failed(operation, error)
            if self.alive:
                (on_failed or self._show_error)(error)

        try:
            return self.bridge.start(operation, work, cancellable=cancellable, on_done=done, on_failed=failed,
                                     on_cancelled=on_cancelled, origin=self._origin())
        except JobBusy as e:
            failed(e)
            return None

    def _origin(self):
        return None

    def _show_error(self, error) -> None:
        self.show_banner(Banner("error", error_text(error)))

    # ------------------------------------------------------------------------------------------ dialogs
    def ask_name(self, title: str, label: str, value: str, submit: Callable[[str], Callable],
                 operation: str, on_saved: Callable[[Any], None], button: str = "Save") -> "NameDialog":
        """A name dialog whose Save runs ``submit(name)`` as a Job; a refused name keeps it open with the reason
        (C1-03, C1-04, C2-05)."""
        dlg = NameDialog(title, label, value, button, self)

        def save():
            dlg.set_error("")
            dlg.save.setEnabled(False)

            def done(result):
                dlg.accept()
                self.dialog = None
                on_saved(result)

            def failed(error):
                dlg.save.setEnabled(True)
                dlg.set_error(error_text(error))
            self.start(operation, submit(dlg.edit.text()), done, failed)
        dlg.save.clicked.connect(save)
        dlg.rejected.connect(lambda: setattr(self, "dialog", None))
        self.dialog = dlg
        dlg.open()
        return dlg

    def confirm_delete(self, summary: DeleteSummary, on_confirm: Callable[[], None]) -> DeleteConfirm:
        dlg = DeleteConfirm(summary.title, summary.intro, summary.items, note=summary.note, button=summary.button,
                            parent=self)
        dlg.accepted.connect(on_confirm)
        dlg.finished.connect(lambda _r: setattr(self, "dialog", None))
        self.dialog = dlg
        dlg.open()
        return dlg


class NameDialog(Dialog):
    """New client / Rename (1.1, 1.2): one name field, an inline reason when refused."""

    def __init__(self, title: str, label: str, value: str, button: str, parent=None):
        super().__init__(title, parent)
        lab = self.text(label, "small")
        self.edit = QLineEdit(value, self)
        self.edit.setAccessibleName(label)
        self.edit.selectAll()
        lab.setBuddy(self.edit)
        self.body.addWidget(self.edit)
        self.error = self.text("", "error")
        self.error.hide()
        self.add_button("Cancel", None, self.reject)
        self.save = self.add_button(button, "primary", default=True)
        self.edit.returnPressed.connect(self.save.click)

    def set_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))
