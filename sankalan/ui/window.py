"""The main window (UX §1–5): title "Sankalan", the rail, one screen at a time, and closing rules.

* Minimum size (FIT-04, decided 17-11-2026): 1366×768 including the frame, capped to the screen's work area so
  1920×1080 at 150% (1280×720 logical) still fits. The window never scrolls (UI-2).
* Leaving a screen with unsaved work asks first (its ``LeaveGuard``).
* Closing (Tech spec, Closing): while a long Job that can be cancelled runs, "Cancel <operation> and close?"; No keeps
  working, Yes cancels and closes once the Job has stopped (SH-03). During a Job that can't be cancelled (the
  commit) the window waits for it, then closes (SH-04).
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QMargins, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QWidget

from sankalan import APP_NAME
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens.base import STAY, PlaceholderScreen, Screen
from sankalan.ui.widgets.rail import Rail

ScreenFactory = Callable[["MainWindow"], Screen]


def minimum_window_size(available: QSize, frame: QMargins = QMargins()) -> QSize:
    """The smallest client area: the design size (frame included) capped to the work area (FIT-04)."""
    w = min(theme.DESIGN_SIZE.width(), available.width()) - frame.left() - frame.right()
    h = min(theme.DESIGN_SIZE.height(), available.height()) - frame.top() - frame.bottom()
    return QSize(max(w, 0), max(h, 0))


def close_prompt(operation: str) -> str:
    """ "Cancel validate and close?" (Tech spec, Closing)."""
    op = operation[:1].lower() + operation[1:] if operation else "the operation"
    return f"Cancel {op} and close?"


def default_screens() -> dict[str, ScreenFactory]:
    from sankalan.ui.screens.clients import ClientsScreen
    return {
        "clients": lambda w: ClientsScreen(w),
        "analysis": lambda w: PlaceholderScreen("analysis", "Analysis", "Saved analyses appear here.", w),
    }


def _later(title: str, phase: int):
    """A screen a later phase builds (New run and Run: 9)."""
    return lambda w, **_kw: w.open_screen(PlaceholderScreen("clients", title, f"Arrives in Phase {phase}.", w))


def _open_client(w: "MainWindow", client_id: str, name: str = "", banner=None, **_kw) -> bool:
    from sankalan.ui.screens.client import ClientScreen
    return w.open_screen(ClientScreen(client_id, name, w), banner=banner)


def _open_new_template(w: "MainWindow", client_id: str, name: str = "", **_kw) -> bool:
    from sankalan.ui.screens.new_template import NewTemplateScreen
    return w.open_screen(NewTemplateScreen(client_id, name, w))


def _open_template(w: "MainWindow", template_id: str, name: str = "", tab: int = 0, banner=None, **_kw) -> bool:
    from sankalan.ui.screens.template import TemplateScreen
    return w.open_screen(TemplateScreen(template_id, name, w, tab=tab), banner=banner)


def _export_later(w: "MainWindow", request=None, **_kw) -> bool:
    """The Export dialog (7.4) arrives in Phase 10; until then the request is kept for it."""
    w.last_export = request
    ask(w, "Export", "The Export dialog arrives in Phase 10.", [("ok", "OK", "primary")])
    return True


def default_routes() -> dict[str, Callable[..., bool]]:
    """Where navigation goes (``MainWindow.go``). Later phases replace the placeholders."""
    return {"client": _open_client, "template": _open_template, "new_template": _open_new_template,
            "new_run": _later("New run", 9), "run": _later("Run", 9), "export": _export_later}


class MainWindow(QMainWindow):
    screenChanged = Signal(object)

    def __init__(self, bridge: JobBridge | None = None, storage=None,
                 screens: dict[str, ScreenFactory] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(theme.app_icon())
        self.bridge = bridge or JobBridge(parent=self)
        self.storage = storage
        self.factories = dict(default_screens())
        self.factories.update(screens or {})
        self.routes = default_routes()
        self.last_export = None
        self._closing = False           # waiting for a Job to stop before closing
        self._may_close = False

        central = QWidget(self)
        central.setObjectName("Central")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.rail = Rail(central)
        lay.addWidget(self.rail)
        self.stack = QStackedWidget(central)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.status = QLabel("", self)          # "Opening your data…", "Finishing the commit…"
        self.status.setObjectName("window-status")
        self.status.setProperty("kind", "subtitle")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.hide()

        self.rail.areaClicked.connect(self.open_area)
        self.rail.settingsClicked.connect(self.open_settings)
        self.rail.jobClicked.connect(self._open_job_origin)
        self.bridge.progressed.connect(self.rail.show_job)
        self.bridge.busyChanged.connect(self._busy_changed)
        self.bridge.jobFinished.connect(self._job_finished)
        self.update_minimum_size()

    # ------------------------------------------------------------------------------------------ size
    def update_minimum_size(self) -> None:
        screen = self.screen() or (self.windowHandle().screen() if self.windowHandle() else None)
        if screen is None:
            return
        frame = self.frameGeometry()
        geo = self.geometry()
        margins = QMargins(geo.left() - frame.left(), geo.top() - frame.top(),
                           frame.right() - geo.right(), frame.bottom() - geo.bottom())
        self.setMinimumSize(minimum_window_size(screen.availableGeometry().size(), margins))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.update_minimum_size()
        handle = self.windowHandle()
        if handle is not None and not getattr(self, "_watching_screen", False):
            handle.screenChanged.connect(self._screen_changed)
            self._watching_screen = True

    def _screen_changed(self, *_args) -> None:
        self.update_minimum_size()

    # ------------------------------------------------------------------------------------------ navigation
    @property
    def current(self) -> Screen | None:
        w = self.stack.currentWidget()
        return w if isinstance(w, Screen) else None

    def may_leave(self) -> bool:
        """Ask the current screen's leave guard, if any. True when leaving may go on."""
        screen = self.current
        guard = screen.leave_guard() if screen is not None else None
        if guard is None:
            return True
        key = ask(self, guard.title, guard.text, [(k, label, kind) for k, label, kind, _fn in guard.options])
        if key is None or key == STAY:
            return False
        for k, _label, _kind, fn in guard.options:
            if k == key:
                return True if fn is None else bool(fn())
        return False

    def open_screen(self, screen: Screen, *, banner=None, check_leave: bool = True) -> bool:
        """Replace the current screen (one level per screen). False if the user chose to stay."""
        if check_leave and not self.may_leave():
            screen.deleteLater()
            return False
        old = self.current
        self.stack.addWidget(screen)
        self.stack.setCurrentWidget(screen)
        if old is not None:
            old.closing()
            self.stack.removeWidget(old)
            old.deleteLater()
        screen.refresh_crumbs()
        self.rail.select(screen.area)
        if banner is not None:
            screen.show_banner(banner)
        screen.shown()
        self.screenChanged.emit(screen)
        return True

    def go(self, route: str, **kw) -> bool:
        """Open a screen by route: client, template, new_template, new_run, run, export."""
        return bool(self.routes[route](self, **kw))

    def open_area(self, area: str) -> bool:
        """Open an area's top screen (rail click: Clients → C1, Analysis → A0)."""
        ok = self.open_screen(self.factories[area](self))
        if not ok and self.current is not None:
            self.rail.select(self.current.area)
        return ok

    def open_settings(self):
        from sankalan.ui.dialogs.app_settings import AppSettingsDialog
        if self.storage is None:
            return None
        dlg = AppSettingsDialog(self.storage, self.bridge, self)
        dlg.dataFolderChanged.connect(lambda _p: self.reload())
        self.settings_dialog = dlg
        dlg.open()
        return dlg

    def reload(self) -> None:
        """Re-open the current area's top screen (after the data folder moved)."""
        area = self.current.area if self.current is not None else "clients"
        self.open_screen(self.factories[area](self), check_leave=False)

    def _open_job_origin(self) -> None:
        origin = self.bridge.current_origin()
        if origin is not None:
            origin()

    # ------------------------------------------------------------------------------------------ status
    def show_status(self, text: str) -> None:
        """A message over the screen while the window waits (start-up, closing)."""
        self.status.setText(text)
        self.status.setVisible(bool(text))
        self.status.setGeometry(self.rect())
        self.status.raise_()
        self.status.setStyleSheet(f"background: rgba(255,255,255,230); color: {theme.MUTED_2}; "
                                  f"font-size: {theme.BODY_PX}px;")
        self.centralWidget().setEnabled(not text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.status.isVisible():
            self.status.setGeometry(self.rect())

    def _busy_changed(self, busy: bool) -> None:
        if not busy:
            self.rail.show_job(None)

    # ------------------------------------------------------------------------------------------ closing
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._may_close:
            event.accept()
            return
        if self._closing:                       # already waiting for a Job to stop
            event.ignore()
            return
        job = self.bridge.current
        if job is not None and not job.wait(0):
            if job.cancellable:
                key = ask(self, close_prompt(job.operation), "", [("no", "No", None), ("yes", "Yes", "primary")])
                if key != "yes":
                    event.ignore()
                    return
                job.cancel()
                self.show_status("Cancelling… Sankalan closes when it has stopped.")
            else:
                self.show_status(f"Finishing {job.operation[:1].lower() + job.operation[1:]}… "
                                 "Sankalan closes when it's done.")
            self._closing = True
            event.ignore()
            return
        if not self.may_leave():
            event.ignore()
            return
        self._stop_quiet_jobs()
        self._may_close = True
        event.accept()

    def _stop_quiet_jobs(self) -> None:
        for t in list(self.bridge._tracked):
            if t.quiet:
                t.job.cancel()
                t.job.wait(2.0)

    def _job_finished(self, _job) -> None:
        if self._closing and self.bridge.current is None:
            self._closing = False
            self._may_close = True
            self._stop_quiet_jobs()
            self.close()
