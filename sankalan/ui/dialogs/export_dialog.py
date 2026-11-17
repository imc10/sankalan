"""7.4 Export and 7.5 Export in progress (EXP-1 to EXP-7, UI-5; C4-18, EXP-01 to EXP-08).

The dialog opens with the template's export defaults (folder, name pattern resolved, delimiter, encoding), all
editable; CSV is the only format (EXP-2). Export checks the folder and asks before replacing a file (EXP-4), then
runs the export as a long Job that can be cancelled: the dialog turns into its progress view and stops being modal
("You can keep working in other screens"). Cancel deletes the part-written file (EXP-7). When it is done the dialog
closes and the screen shows a banner with Open folder.

Several files (Export all outputs) take a name pattern instead of a file name; each output's name fills {Output}.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from sankalan import exporting, formats, log, runs
from sankalan.exporting import ExportExists
from sankalan.jobs import JobBusy
from sankalan.model import export as ex
from sankalan.ui import theme
from sankalan.ui.dialogs.base import Dialog, ask
from sankalan.ui.jobs import BUSY_TOOLTIP
from sankalan.ui.widgets.banner import Banner, success
from sankalan.ui.widgets.progress import ProgressPanel

WIDTH = 540
KEEP_WORKING = "You can keep working in other screens. Cancelling deletes the part-written file."
ENCODING_LABELS = {True: "UTF-8 with BOM", False: "UTF-8"}
SOMETHING_WRONG = "Something went wrong. Try again; if it keeps happening, restart Sankalan."

# Tests replace this to answer the folder picker: ``fn(dialog) -> folder | None``.
folder_hook: Callable[["ExportDialog"], str | None] | None = None


def replace_prompt(parent, name: str) -> bool:
    """EXP-06: confirm before overwriting; Cancel keeps the old file."""
    key = ask(parent, f"Replace “{name}”?",
              "A file with this name is already in the folder. Replacing it can't be undone.",
              [("cancel", "Cancel", None), ("replace", "Replace", "destructive")])
    return key == "replace"


def file_name_of(text: str) -> str:
    """The name typed, made safe for Windows (EXP-07) and ending in .csv."""
    name = ex.safe_file_name(text.strip())
    return name if name.lower().endswith(".csv") else name + ".csv"


def error_text(error: BaseException | None, dest: Path | None = None) -> str:
    if isinstance(error, runs.RunProblem):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "The folder can't be found. Choose another folder."
    if isinstance(error, PermissionError):
        name = dest.name if dest is not None else "the file"
        return f"Sankalan can't write {name}. If it is open in another program, close it and try again."
    if isinstance(error, JobBusy):
        return BUSY_TOOLTIP + "."
    return SOMETHING_WRONG


class ExportDialog(Dialog):
    def __init__(self, window, request: ex.ExportRequest, parent=None):
        super().__init__(f"Export {request.what}".strip(), parent or window, WIDTH)
        self.window_ = window
        self.request = request
        self.job = None
        self.result = None
        self._overwrite = False

        # ---------------------------------------------------------------------------------------- 7.4 form
        self.form = QWidget(self)
        fl = QVBoxLayout(self.form)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(16)
        parts = [f"{formats.count(request.rows, 'row')}"] if request.rows is not None else []
        parts.append("one CSV file per output" if request.many else "CSV file")
        self.info = self._label(" · ".join(parts), "body")
        fl.addWidget(self.info)

        fl.addLayout(self._field("Folder", self._folder_row()))
        if request.many:
            self.name = QLineEdit(request.pattern, self.form)
            self.name.setAccessibleName("Name pattern")
            fl.addLayout(self._field("Name pattern", self.name,
                                     "{Client}, {Template}, {RunID} and {Output} are filled for each output."))
        else:
            self.name = QLineEdit(request.file_name, self.form)
            self.name.setAccessibleName("File name")
            fl.addLayout(self._field("File name", self.name))
        self.name.textEdited.connect(lambda _t: self.set_error(""))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        self.delimiter = QComboBox(self.form)
        self.delimiter.setAccessibleName("Delimiter")
        for key, label in ex.DELIMITERS.items():
            self.delimiter.addItem(label, key)
        self.delimiter.setCurrentIndex(self.delimiter.findData(request.options.delimiter))
        self.encoding = QComboBox(self.form)
        self.encoding.setAccessibleName("Encoding")
        for bom in (True, False):
            self.encoding.addItem(ENCODING_LABELS[bom], bom)
        self.encoding.setCurrentIndex(self.encoding.findData(request.options.bom))
        grid.addLayout(self._field("Delimiter", self.delimiter), 0, 0)
        grid.addLayout(self._field("Encoding", self.encoding), 0, 1)
        fl.addLayout(grid)
        self.error = self._label("", "error")
        self.error.hide()
        fl.addWidget(self.error)
        self.body.addWidget(self.form)

        # ---------------------------------------------------------------------------------------- 7.5 progress
        self.running = QWidget(self)
        rl = QVBoxLayout(self.running)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(16)
        self.writing = self._label("", "body")
        rl.addWidget(self.writing)
        self.progress = ProgressPanel(self.running, cancel_text="Cancel export", note=KEEP_WORKING)
        rl.addWidget(self.progress)
        self.running.hide()
        self.body.addWidget(self.running)

        self.cancel_button = self.add_button("Cancel", None, self.reject)
        self.export_button = self.add_button("Export", "primary", self.export, default=True)
        self.window_.bridge.guard(self.export_button)

    # -------------------------------------------------------------------------------------------- layout helpers
    def _label(self, text: str, kind: str) -> QLabel:
        lab = QLabel(text, self)
        lab.setProperty("kind", kind)
        lab.setWordWrap(True)
        lab.setTextFormat(Qt.TextFormat.PlainText)
        return lab

    def _field(self, label: str, widget, hint: str | None = None) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(6)
        lab = self._label(label, "small")
        lab.setStyleSheet(f"font-weight: 500; color: {theme.MUTED};")
        box.addWidget(lab)
        if isinstance(widget, QWidget):
            box.addWidget(widget)
        else:
            box.addLayout(widget)
        if hint:
            box.addWidget(self._label(hint, "small"))
        return box

    def _folder_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self.folder = QLineEdit(self.request.folder, self.form)
        self.folder.setReadOnly(True)
        self.folder.setAccessibleName("Folder")
        self.folder.setStyleSheet(f"background: {theme.HEADER_BG}; color: {theme.MUTED_2};")
        row.addWidget(self.folder, 1)
        self.change = QPushButton("Change…", self.form)
        self.change.clicked.connect(self.pick_folder)
        row.addWidget(self.change)
        return row

    # -------------------------------------------------------------------------------------------- form
    def pick_folder(self) -> None:
        if folder_hook is not None:
            chosen = folder_hook(self)
        else:
            chosen = QFileDialog.getExistingDirectory(self, "Choose a folder", self.folder.text())
        if chosen:
            self.folder.setText(str(Path(chosen)))
            self.set_error("")

    def set_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    @property
    def options(self) -> ex.ExportOptions:
        return ex.ExportOptions(self.delimiter.currentData(), bool(self.encoding.currentData()))

    @property
    def destination(self) -> Path:
        """The file to write (one file), or the folder (Export all outputs)."""
        folder = Path(self.folder.text())
        return folder if self.request.many else folder / file_name_of(self.name.text())

    # -------------------------------------------------------------------------------------------- export
    def export(self) -> bool:
        """Check the form, confirm a replace, and start the Job. False when it didn't start."""
        self.set_error("")
        self._overwrite = False
        folder = Path(self.folder.text())
        if not self.name.text().strip():
            self.set_error("Enter a name pattern." if self.request.many else "Enter a file name.")
            return False
        if not folder.is_dir():
            self.set_error("The folder can't be found. Choose another folder.")
            return False
        if not self.request.many:
            dest = self.destination
            self.name.setText(dest.name)              # shows what is written (EXP-07)
            if dest.exists() and not self._overwrite and not replace_prompt(self, dest.name):
                return False
            if dest.exists():
                self._overwrite = True
        return self._start()

    def _work(self):
        folder = self.window_.storage.folder
        temp = self.window_.storage.paths.temp
        request = dataclasses.replace(self.request, folder=self.folder.text(),
                                      pattern=self.name.text() if self.request.many else self.request.pattern)
        options, overwrite, dest = self.options, self._overwrite, self.destination

        def work(ctx):
            items = runs.export_items(ctx, folder, request)
            if request.many:
                return exporting.export_many(ctx, temp, [(q, dest / name) for q, name in items], options,
                                             overwrite=overwrite)
            return [exporting.export(ctx, temp, items[0][0], dest, options, overwrite=overwrite)]
        return work

    def _start(self) -> bool:
        try:
            job = self.window_.bridge.start("Export", self._work(), cancellable=True, on_done=self._done,
                                            on_failed=self._failed, on_cancelled=self._cancelled)
        except JobBusy as e:
            self.set_error(error_text(e))
            return False
        self.job = job
        self._show_running(job)
        return True

    def _show_running(self, job) -> None:
        self.setWindowTitle(f"Exporting {self.request.what}")
        self.title.setText(f"Exporting {self.request.what}")
        self.writing.setText(f"Writing to {self.folder.text()}")
        self.form.hide()
        self.export_button.hide()
        self.cancel_button.hide()
        self.running.show()
        self.progress.bind(job)
        if self.isVisible():                  # keep working in other screens while it runs
            self.hide()
            self.setWindowModality(Qt.WindowModality.NonModal)
            self.show()
        else:
            self.setWindowModality(Qt.WindowModality.NonModal)

    def _show_form(self) -> None:
        self.setWindowTitle(f"Export {self.request.what}")
        self.title.setText(f"Export {self.request.what}")
        self.running.hide()
        self.form.show()
        self.export_button.show()
        self.cancel_button.show()
        self.job = None

    def _banner(self, banner: Banner) -> None:
        screen = getattr(self.window_, "current", None)
        if screen is not None:
            screen.show_banner(banner)

    def _done(self, results) -> None:
        self.result = results
        self.job = None
        if len(results) == 1 and not self.request.many:
            r = results[0]
            text = f"Exported {r.path.name} · {formats.count(r.rows, 'row')}."
            where = r.path
        else:
            text = f"Exported {formats.count(len(results), 'file')} to {self.folder.text()}."
            where = results[0].path if results else Path(self.folder.text())
        self.banner = success(text, folder=where)
        self._banner(self.banner)
        self.accept()

    def _cancelled(self) -> None:
        self.job = None
        self.banner = Banner("info", "Export cancelled. The part-written file was deleted.")
        self._banner(self.banner)
        self.reject()

    def _failed(self, error) -> None:
        self._show_form()
        if isinstance(error, ExportExists):
            if replace_prompt(self, error.path.name):
                self._overwrite = True
                self._start()
            return
        log.failed("Export", error)
        self.set_error(error_text(error, self.destination))

    def reject(self) -> None:
        """Esc or ✕ while exporting does nothing: Cancel export is the way to stop it."""
        if self.job is not None and not self.job.wait(0):
            return
        super().reject()
