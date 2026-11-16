"""Main window: sidebar with run steps, the five pages, and a busy bar for long jobs."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QProgressBar,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..core.output import OutputExists, TooManyRows
from ..core.readers import Cancelled
from ..core.session import Session, setup_logging, template_from_sample
from ..core.template import TemplateStore
from . import style as S
from .editor import TemplateEditor
from .pages import FilesPage, HomePage, MapPage, OutputPage, ValidatePage
from .prompter import Prompter
from .widgets import Job, button, label, restyle

STEPS = [("files", "Add files"), ("map", "Map columns"), ("validate", "Validate"), ("output", "Output")]


class MainWindow(QMainWindow):
    def __init__(self, prompter=None, store_folder=None, settings=None):
        super().__init__()
        self.setWindowTitle(APP_NAME)            # NF-8: app name only, no publisher
        self.resize(1280, 860)
        self.settings = settings or QSettings(APP_NAME, APP_NAME)
        folder = store_folder or self.settings.value("templates_folder") or None
        self.store = TemplateStore(folder)
        self.prompter = prompter or Prompter(self)
        self.session: Session | None = None
        self.job: Job | None = None
        self.result = None
        self.override = False
        self.reached = set()

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        # sidebar
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(230)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 16, 12, 16)
        sl.setSpacing(4)
        self.nav_home = button("⌂  Templates", "nav", self.go_home, "navHome")
        sl.addWidget(self.nav_home)
        sl.addSpacing(14)
        self.run_caption = label("NO RUN IN PROGRESS", "small")
        self.run_name = label("Run a template or start a new consolidation to see its steps here.", "small", wrap=True)
        sl.addWidget(self.run_caption)
        sl.addWidget(self.run_name)
        self.step_btns = {}
        for i, (key, cap) in enumerate(STEPS, start=2):
            b = button(f"{i}   {cap}", "nav", lambda _=False, k=key: self.go(k), f"nav_{key}")
            self.step_btns[key] = b
            sl.addWidget(b)
        sl.addStretch()
        sl.addWidget(label(f"{APP_NAME} {__version__} · offline", "small"))
        body.addWidget(side)
        # pages
        self.stack = QStackedWidget()
        self.pages = {"home": HomePage(self), "files": FilesPage(self), "map": MapPage(self),
                      "validate": ValidatePage(self), "output": OutputPage(self)}
        for p in self.pages.values():
            self.stack.addWidget(p)
        body.addWidget(self.stack, 1)
        # busy bar
        self.busy = QFrame()
        self.busy.setObjectName("card")
        bl = QHBoxLayout(self.busy)
        bl.setContentsMargins(16, 8, 16, 8)
        self.busy_lbl = QLabel("")
        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.cancel_btn = button("Cancel", slot=self.cancel_job, obj="cancelJob")
        bl.addWidget(self.busy_lbl)
        bl.addWidget(self.progress, 1)
        bl.addWidget(self.cancel_btn)
        self.busy.hide()
        outer.addWidget(self.busy)
        self.go_home()

    # ------------------------------------------------------------------ navigation
    def go(self, key):
        if key != "home" and (self.session is None or key not in self.reached):
            return
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.nav_home.setProperty("current", key == "home")
        restyle(self.nav_home)
        for k, b in self.step_btns.items():
            b.setProperty("current", k == key)
            b.setEnabled(self.session is not None and k in self.reached)
            restyle(b)
        if hasattr(page, "on_enter"):
            page.on_enter()
        self.current = key

    def go_home(self):
        self.stack.setCurrentWidget(self.pages["home"])
        self.pages["home"].refresh()
        self.current = "home"
        self.nav_home.setProperty("current", True)
        restyle(self.nav_home)
        for k, b in self.step_btns.items():
            b.setProperty("current", False)
            b.setEnabled(self.session is not None and k in self.reached)
            restyle(b)

    def _begin(self, template):
        self.session = Session(template)
        self.reached = {"files"}
        self.result = None
        self.run_caption.setText("CURRENT RUN")
        self.run_name.setText(f"{template.client} · {template.task}")
        self.go("files")

    def start_run(self, template):
        self._begin(template.copy())

    def new_consolidation(self):
        ans = self.prompter.new_consolidation()
        if not ans:
            return
        client, task, sample = ans
        if self.store.exists(client, task):
            self.prompter.error("Template exists", f'"{client} → {task}" already exists. Run it from the list.')
            return
        try:
            t = template_from_sample(sample, client, task)
        except Exception as exc:
            self.prompter.error("Couldn't read the sample file", str(exc))
            return
        self._begin(t)
        self.pages["files"].add_paths([sample])

    def go_map(self):
        if not self.session.good_sources():
            return
        self.reached.add("map")
        self.go("map")

    def go_validate(self):
        self.reached.add("validate")
        self.run_job(lambda p, c: self.session.validate(p, c), lambda _: self.go("validate"))

    def recheck(self):
        """Re-read the source files (after the executive fixed them) and validate again."""
        def work(p, c):
            self.session.load(p, c)
            return self.session.validate(p, c)
        self.run_job(work, lambda _: self.go("validate"))

    def go_output(self, override=False):
        self.override = override
        self.reached.add("output")
        self.go("output")

    # ------------------------------------------------------------------ output
    def write_output(self, overwrite=False):
        s = self.session
        folder = s.template.output.get("folder") or None

        def work(p, c):
            return s.write(override_errors=self.override, overwrite=overwrite, folder=folder, progress=p,
                           cancel=c)

        def fail(exc):
            if isinstance(exc, OutputExists):
                if self.prompter.confirm("Replace file?", f"{Path(str(exc)).name} already exists. Replace it?",
                                         yes="Replace"):
                    self.write_output(overwrite=True)
                return True
            if isinstance(exc, TooManyRows):
                self.prompter.error("Too many rows for Excel", str(exc))
                return True
            return False

        self.run_job(work, self.after_write, fail)

    def after_write(self, res):
        self.result = res
        page = self.pages["output"]
        page.result = res
        title = f"Written: {res.path.name}"
        body = f"{res.rows_written:,} rows"
        if res.totals:
            body += " · totals match the input files" if res.totals_match else " · TOTALS DO NOT MATCH"
        if res.errors_overridden:
            body += f" · {res.errors_overridden} errors written anyway"
        page.banner.show_msg("ok" if res.totals_match else "error", title, body)
        page.open_file.show()
        page.open_folder.show()
        page.show_summary(res)
        page.settings_changed()

    def open_output(self):
        if self.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result.path)))

    def open_output_folder(self):
        if self.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result.path.parent)))

    def save_run_template(self):
        try:
            self.session.save_template(self.store)
        except ValueError as exc:
            self.prompter.error("Couldn't save template", str(exc))
            return
        self.session.new_aliases = []
        self.pages["output"].settings_changed()
        self.prompter.info("Template saved", f"{self.session.template.client} → {self.session.template.task} "
                                             f"saved as version {self.session.template.version}.")

    # ------------------------------------------------------------------ templates
    def edit_template(self, t, editor_cb=None):
        dlg = TemplateEditor(t, self)
        if editor_cb:              # tests drive the dialog directly
            editor_cb(dlg)
            ok = True
        else:
            ok = bool(dlg.exec())
        if ok:
            nt = dlg.result_template()
            nt.path = t.path
            try:
                self.store.save(nt)
            except ValueError as exc:
                self.prompter.error("Couldn't save template", str(exc))
            self.go_home()

    def duplicate_template(self, t):
        name = self.prompter.text("Duplicate template", "New task name", f"{t.task} (copy)")
        if name:
            try:
                self.store.duplicate(t, name)
            except ValueError as exc:
                self.prompter.error("Couldn't duplicate", str(exc))
            self.go_home()

    def rename_template(self, t):
        client = self.prompter.text("Rename template", "Client", t.client)
        task = self.prompter.text("Rename template", "Task", t.task) if client else None
        if client and task:
            try:
                self.store.rename(t, client, task)
            except ValueError as exc:
                self.prompter.error("Couldn't rename", str(exc))
            self.go_home()

    def delete_template(self, t):
        if self.prompter.confirm("Delete template?", f'Delete "{t.client} → {t.task}"? This can\'t be undone.',
                                 yes="Delete"):
            self.store.delete(t)
            self.go_home()

    def change_template_folder(self):
        f = self.prompter.folder("Templates folder", str(self.store.folder))
        if f:
            self.store = TemplateStore(f)
            self.settings.setValue("templates_folder", f)
            self.go_home()

    # ------------------------------------------------------------------ jobs (NF-4)
    @property
    def is_busy(self):
        return self.job is not None

    def run_job(self, fn, on_done, on_fail=None):
        if self.job:
            return
        self.job = Job(fn)
        self.busy_lbl.setText("Working…")
        self.progress.setRange(0, 0)
        self.busy.show()
        self.cancel_btn.setEnabled(True)
        self.job.progress.connect(self._on_progress)

        def finish():
            self.busy.hide()
            j, self.job = self.job, None
            if j:
                j.wait()
                j.deleteLater()

        def done(res):
            finish()
            on_done(res)

        def failed(exc):
            finish()
            if isinstance(exc, Cancelled):
                self.prompter.info("Cancelled", "Stopped. Nothing was written.")
                return
            if on_fail and on_fail(exc):
                return
            self.prompter.error("Something went wrong", f"{type(exc).__name__}: {exc}")

        self.job.done.connect(done, Qt.ConnectionType.QueuedConnection)
        self.job.failed.connect(failed, Qt.ConnectionType.QueuedConnection)
        self.job.start()

    def _on_progress(self, stage, done, total):
        self.busy_lbl.setText(stage)
        if total > 1:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setRange(0, 0)

    def cancel_job(self):
        if self.job:
            self.job.cancel()
            self.cancel_btn.setEnabled(False)
            self.busy_lbl.setText("Cancelling…")


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--self-test" in argv:
        from ..selftest import run_self_test
        return run_self_test()
    setup_logging()
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(S.QSS)
    icon = Path(__file__).parent / "sankalan.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
