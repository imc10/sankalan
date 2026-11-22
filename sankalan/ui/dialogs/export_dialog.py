"""7.4 Export and 7.5 Export in progress (EXP-1 to EXP-14, UI-5; C4-18, EXP-01 to EXP-08; Tech spec A2 8.6).

The dialog opens with the template's export defaults (folder, name pattern resolved, delimiter, encoding), all
editable; CSV is the only format (EXP-2). On open a quiet "Checking size" Job estimates the export (rows, files, bytes;
EXP-13) and Export stays disabled until it returns. The summary says "N rows · CSV file" or "N rows · 3 CSV files ·
about X"; an export over the part size gets a parts line under the file name (EXP-9, EXP-10), and a drive without
enough free space a message above the buttons, read again (no Job) when the folder changes.

Export lists every file it would replace and asks first (EXP-4, EXP-10), then runs the export as a long Job that can
be cancelled: the dialog turns into its progress view (stage, rows written of N, "part K of M", elapsed; EXP-11) and
stops being modal ("You can keep working in other screens"). Cancel deletes everything written so far and leaves the
files it would have replaced unchanged (EXP-14). When it is done the dialog closes and the screen shows a banner with
Open folder.

Several files (Export all outputs) take a name pattern instead of a file name; each output's name fills {Output}.
"""
from __future__ import annotations

import dataclasses
import errno
from pathlib import Path
from typing import Callable

import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from sankalan import exporting, formats, log, runs
from sankalan.exporting import ExportCheckFailed, ExportExists, FileInUse, NotEnoughSpace
from sankalan.jobs import JobBusy
from sankalan.model import export as ex
from sankalan.ui import theme
from sankalan.ui.dialogs.base import Dialog, ask
from sankalan.ui.jobs import BUSY_TOOLTIP
from sankalan.ui.widgets.banner import Banner, success
from sankalan.ui.widgets.progress import ProgressPanel

WIDTH = 540
KEEP_WORKING = "You can keep working in other screens. Cancelling deletes the files written so far."
CANCELLED = "Export cancelled. No files were written; files that would have been replaced are unchanged."
CHECKING = "Checking size…"
ENCODING_LABELS = {True: "UTF-8 with BOM", False: "UTF-8"}
SOMETHING_WRONG = "Something went wrong. Try again; if it keeps happening, restart Sankalan."
DISK_FULL = ("The drive {drive} became full, so the export stopped. No files were written; files that would have "
             "been replaced are unchanged. Free up space or choose a folder on another drive.")
REPLACE_LIST = 10               # files named in the overwrite confirmation, then "and N more"
RETRY_MS = 250                  # the size check waits for the runner to be free

# Tests replace these: the folder picker ``fn(dialog) -> folder | None``, and the part size (T37: the app never does).
folder_hook: Callable[["ExportDialog"], str | None] | None = None
part_rows_hook: int | None = None


def replace_prompt(parent, names: list[str] | str) -> bool:
    """EXP-06, EXP-10: confirm before replacing files, listing every one (up to 10, then "and N more"); Cancel keeps
    them."""
    names = [names] if isinstance(names, str) else list(names)
    if len(names) == 1:
        title = f"Replace “{names[0]}”?"
        text = "A file with this name is already in the folder. Replacing it can't be undone."
    else:
        title = f"Replace {len(names)} files?"
        shown = names[:REPLACE_LIST]
        more = len(names) - len(shown)
        lines = shown + ([f"and {formats.number(more)} more"] if more else [])
        text = "These files are already in the folder:\n" + "\n".join(lines) + "\nReplacing them can't be undone."
    key = ask(parent, title, text, [("cancel", "Cancel", None), ("replace", "Replace", "destructive")])
    return key == "replace"


def file_name_of(text: str) -> str:
    """The name typed, made safe for Windows (EXP-07) and ending in .csv."""
    name = ex.safe_file_name(text.strip())
    return name if name.lower().endswith(".csv") else name + ".csv"


def summary_text(est: exporting.Estimate, many: bool, context: tuple = ()) -> str:
    """"5,000 rows · CSV file", "2,341,118 rows · 3 CSV files · about 610 MB", "one CSV file per output". Export
    rows (7.9) leads with its ``context`` and always gives the size: "Rao & Co · Sales · 3 runs · 2 filters · about
    610 MB · 3 CSV files"."""
    if context:
        files = "CSV file" if est.files == 1 else f"{formats.number(est.files)} CSV files"
        return " · ".join([*context, f"about {formats.size(est.bytes)}", files])
    parts = [formats.count(est.total_rows, "row")]
    if many and not est.split:
        parts.append("one CSV file per output")
    elif est.files == 1:
        parts.append("CSV file")
    else:
        parts.append(f"{formats.number(est.files)} CSV files")
    if est.split:
        parts.append(f"about {formats.size(est.bytes)}")
    return " · ".join(parts)


def parts_text(names: list[str], part_rows: int) -> str:
    """Feature Spec A2 4.3: "Saved as 3 files of up to 1,000,000 rows each, so each opens fully in Excel:
    Acme_Sales_R-0003_part01of03.csv to …_part03of03.csv"."""
    if len(names) < 2:
        return ""
    last = names[-1]
    tail = last[last.rindex("_part"):]
    return (f"Saved as {formats.number(len(names))} files of up to {formats.number(part_rows)} rows each, so each "
            f"opens fully in Excel: {names[0]} to …{tail}")


def error_text(error: BaseException | None, dest: Path | None = None) -> str:
    if isinstance(error, (runs.RunProblem, NotEnoughSpace, FileInUse, ExportCheckFailed)):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "The folder can't be found. Choose another folder."
    if isinstance(error, PermissionError):
        name = dest.name if dest is not None else "the file"
        return f"Sankalan can't write {name}. If it is open in another program, close it and try again."
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        folder = dest if dest is not None and dest.is_dir() else (dest.parent if dest is not None else Path.cwd())
        return DISK_FULL.format(drive=exporting._drive(folder) or str(folder))
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
        self.estimate: exporting.Estimate | None = None
        self.estimate_job = None
        self.part_rows = part_rows_hook or exporting.PART_ROWS
        self._replace: set[Path] = set()
        self._space = ""
        self._checking = True                         # until the size check returns (or fails)

        # ---------------------------------------------------------------------------------------- 7.4 form
        self.form = QWidget(self)
        fl = QVBoxLayout(self.form)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(16)
        self.info = self._label(CHECKING, "body")
        fl.addWidget(self.info)
        self.details = self._label("\n".join(request.details), "small")      # Export rows: filters, columns, order
        self.details.setObjectName("ExportDetails")
        self.details.setStyleSheet(f"QLabel#ExportDetails {{ background: {theme.HEADER_BG}; border: 1px solid "
                                   f"{theme.BORDER}; border-radius: 6px; padding: 10px 12px; color: {theme.TEXT}; }}")
        self.details.setVisible(bool(request.details))
        fl.addWidget(self.details)

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
        self.name.textEdited.connect(self._name_edited)
        self.parts = self._label("", "small")
        self.parts.hide()
        fl.addWidget(self.parts)

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
        self.space = self._label("", "error")         # EXP-13, above the buttons
        self.space.hide()
        fl.addWidget(self.space)
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
        self.window_.bridge.guard(self.export_button, False)
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.setInterval(RETRY_MS)
        self._retry.timeout.connect(self.check_size)
        self.check_size()

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

    # -------------------------------------------------------------------------------------------- size (EXP-13)
    def _work_inputs(self):
        folder = self.window_.storage.folder
        temp = self.window_.storage.paths.temp
        request = dataclasses.replace(self.request, folder=self.folder.text(),
                                      pattern=self.name.text() if self.request.many else self.request.pattern)
        return folder, temp, request

    def check_size(self) -> None:
        """Start the "Checking size" quiet Job; when the runner is busy, try again shortly."""
        if not shiboken6.isValid(self) or self.estimate is not None or self.estimate_job is not None \
                or self.job is not None:
            return
        folder, temp, request = self._work_inputs()
        options, part_rows = self.options, self.part_rows

        def work(ctx):
            sources = [s for s, _name in runs.export_items(ctx, folder, request)]
            return exporting.estimate(ctx, temp, sources, options, part_rows)

        def done(est):
            self.estimate_job = None
            if shiboken6.isValid(self):
                self._checking = False
                self._estimated(est)

        def failed(error):
            self.estimate_job = None
            if shiboken6.isValid(self):
                self._checking = False
                log.failed("Checking size", error)
                self.info.setText(self._fallback_info())
                self.set_error(error_text(error))
                self._allow()

        def cancelled():
            self.estimate_job = None
            if shiboken6.isValid(self):
                self._retry.start()

        job = self.window_.bridge.try_quiet(exporting.STAGE_CHECK, work, on_done=done, on_failed=failed,
                                            on_cancelled=cancelled)
        if job is None:
            self._retry.start()
        else:
            self.estimate_job = job

    def _fallback_info(self) -> str:
        if self.request.context:
            return " · ".join([*self.request.context, "CSV file"])
        parts = [formats.count(self.request.rows, "row")] if self.request.rows is not None else []
        parts.append("one CSV file per output" if self.request.many else "CSV file")
        return " · ".join(parts)

    def _estimated(self, est: exporting.Estimate) -> None:
        self.estimate = est
        self.info.setText(summary_text(est, self.request.many, self.request.context))
        self._update_parts()
        self.update_space()

    def planned(self) -> list[list[str]] | None:
        """The final names of each file, from the estimate's rows (None until the size check returns)."""
        est = self.estimate
        if est is None:
            return None
        if self.request.many:
            v = self.request.values or {}
            base = [ex.csv_file_name(self.name.text(), Client=v.get("Client", ""), Template=v.get("Template", ""),
                                     RunID=v.get("RunID", ""), Output=label) for label in est.labels]
        else:
            base = [file_name_of(self.name.text())] * len(est.rows)
        return [exporting.plan(rows, name, est.part_rows) for rows, name in zip(est.rows, base)]

    def _update_parts(self) -> None:
        text = ""
        names = self.planned()
        if names and not self.request.many and self.name.text().strip():
            text = parts_text(names[0], self.part_rows)
        self.parts.setText(text)
        self.parts.setVisible(bool(text))

    def update_space(self) -> None:
        """EXP-13: free space read now (no Job, no DuckDB); Export is disabled while a drive is short."""
        problem = ""
        if self.estimate is not None and Path(self.folder.text()).is_dir():
            try:
                problem = exporting.space_problem(self.estimate, Path(self.folder.text()),
                                                  self.window_.storage.paths.temp) or ""
            except OSError:
                problem = ""
        self._space = problem
        self.space.setText(problem)
        self.space.setVisible(bool(problem))
        self._allow()

    def _allow(self) -> None:
        ready = not self._checking and not self._space
        self.window_.bridge.set_allowed(self.export_button, ready)

    # -------------------------------------------------------------------------------------------- form
    def _name_edited(self, _text: str) -> None:
        self.set_error("")
        self._update_parts()

    def pick_folder(self) -> None:
        if folder_hook is not None:
            chosen = folder_hook(self)
        else:
            chosen = QFileDialog.getExistingDirectory(self, "Choose a folder", self.folder.text())
        if chosen:
            self.folder.setText(str(Path(chosen)))
            self.set_error("")
            self.update_space()

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
        """Check the form, confirm replacing files, and start the Job. False when it didn't start."""
        self.set_error("")
        self._replace = set()
        if self._checking:                                      # Export is disabled until the size check returns
            return False
        folder = Path(self.folder.text())
        if not self.name.text().strip():
            self.set_error("Enter a name pattern." if self.request.many else "Enter a file name.")
            return False
        if not folder.is_dir():
            self.set_error("The folder can't be found. Choose another folder.")
            return False
        if not self.request.many:
            self.name.setText(self.destination.name)              # shows what is written (EXP-07)
            self._update_parts()
        self.update_space()
        if self._space:
            return False
        planned = self.planned()
        if planned is not None:
            existing = [folder / n for names in planned for n in names if (folder / n).exists()]
            if existing and not replace_prompt(self, [p.name for p in existing]):
                return False
            self._replace = set(existing)
        return self._start()

    def _work(self):
        folder, temp, request = self._work_inputs()
        options, replace, est, part_rows = self.options, set(self._replace), self.estimate, self.part_rows
        out, single = Path(self.folder.text()), file_name_of(self.name.text())

        def work(ctx):
            items = runs.export_items(ctx, folder, request)
            sources = [s for s, _name in items]
            names = [name for _s, name in items] if request.many else [single]
            return exporting.export(ctx, temp, sources, out, names, options, replace=replace, part_rows=part_rows,
                                    estimate_=est)
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

    def _done(self, results: list[exporting.ExportResult]) -> None:
        self.result = results
        self.job = None
        if len(results) == 1 and not self.request.many:
            r = results[0]
            if r.split:                                         # EXP-14
                text = f"Exported {formats.count(r.rows, 'row')} to {formats.count(len(r.paths), 'file')}"
                where = Path(self.folder.text())
            else:
                text = f"Exported {r.path.name} · {formats.count(r.rows, 'row')}."
                where = r.path
        else:
            files = sum(len(r.paths) for r in results)
            text = f"Exported {formats.count(files, 'file')} to {self.folder.text()}."
            where = results[0].path if results else Path(self.folder.text())
        self.banner = success(text, folder=where)
        self._banner(self.banner)
        self.accept()

    def _cancelled(self) -> None:
        self.job = None
        self.banner = Banner("info", CANCELLED)
        self._banner(self.banner)
        self.reject()

    def _failed(self, error) -> None:
        self._show_form()
        if isinstance(error, ExportExists):
            if replace_prompt(self, [p.name for p in error.paths]):
                self._replace |= set(error.paths)
                self._start()
            return
        log.failed("Export", error)
        self.set_error(error_text(error, self.destination))
        if isinstance(error, NotEnoughSpace):
            self.update_space()

    def reject(self) -> None:
        """Esc or ✕ while exporting does nothing: Cancel export is the way to stop it."""
        if self.job is not None and not self.job.wait(0):
            return
        self._retry.stop()
        super().reject()
