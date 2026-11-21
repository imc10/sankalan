"""The windowed app: one copy, theme, window, storage opened off the UI thread, and shutdown.

Start-up: a second copy hands over to the first and exits (DEP-05). The window shows at once with "Opening your
data…" while ``Storage.open()`` (backup, schema, recovery: all DuckDB work) runs on a background thread, so the UI
thread never touches DuckDB. Shutdown waits for the Job runner, then closes the connection and empties
%TEMP%\\Sankalan. A data folder made by a test build (catalogue version 1) is refused untouched; the user chooses or
creates another folder, which then opens the same way (T40).
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from sankalan import APP_NAME, log
from sankalan import paths as app_paths
from sankalan.db.catalogue import CatalogueFromTestBuild
from sankalan.db.storage import Storage
from sankalan.jobs import POLL_INTERVAL_MS
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.jobs import JobBridge
from sankalan.ui.single_instance import KEY, SingleInstance
from sankalan.ui.window import MainWindow

OPENING = "Opening your data…"
OPEN_FAILED = ("Sankalan can't open its data folder. Close any other program using it, then start Sankalan "
               "again.")


def make_application(argv=None) -> QApplication:
    app = QApplication.instance() or QApplication(list(argv or sys.argv))
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("")
    theme.apply(app)
    return app


class StorageOpener:
    """Opens storage on a background thread and reports back on the UI thread."""

    def __init__(self, storage: Storage, on_open, on_error):
        self.storage = storage
        self.on_open = on_open
        self.on_error = on_error
        self.error: BaseException | None = None
        self._done = threading.Event()
        self._timer = QTimer()
        self._timer.setInterval(POLL_INTERVAL_MS // 5)
        self._timer.timeout.connect(self._check)

    def start(self) -> None:
        threading.Thread(target=self._run, name="open-storage", daemon=True).start()
        self._timer.start()

    def _run(self) -> None:
        try:
            self.storage.open()
        except BaseException as e:      # noqa: BLE001 - reported on the UI thread
            self.error = e
        finally:
            self._done.set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout)

    def _check(self) -> None:
        if not self._done.is_set():
            return
        self._timer.stop()
        if self.error is None:
            self.on_open(self.storage)
        else:
            log.failed("start", self.error)
            self.on_error(self.error)


class SankalanApp:
    def __init__(self, paths: app_paths.AppPaths | None = None, *, instance_key: str = KEY, screens=None):
        self.paths = paths or app_paths.AppPaths.from_environment()
        self.instance_key = instance_key
        self.screens = screens
        self.storage = Storage(self.paths)
        self.bridge: JobBridge | None = None
        self.window: MainWindow | None = None
        self.instance: SingleInstance | None = None
        self.opener: StorageOpener | None = None
        self.failed = False

    def start(self) -> bool:
        """Build the window and begin opening storage. False when another copy is running (it was activated)."""
        self.instance = SingleInstance(self.instance_key)
        if not self.instance.first:
            self.instance.activate_other()
            return False
        self.bridge = JobBridge()
        self.window = MainWindow(self.bridge, None, self.screens)
        self.window.show_status(OPENING)
        self.window.showMaximized()
        self.instance.publish(int(self.window.winId()))
        self.opener = StorageOpener(self.storage, self._opened, self._failed)
        self.opener.start()
        return True

    def _opened(self, storage: Storage) -> None:
        self.bridge.set_runner(storage.runner)
        self.window.storage = storage
        self.window.show_status("")
        self.window.open_area("clients")

    def _failed(self, error) -> None:
        if isinstance(error, CatalogueFromTestBuild) and self._choose_other_folder():
            return
        self.failed = True
        if not isinstance(error, CatalogueFromTestBuild):
            ask(self.window, APP_NAME, OPEN_FAILED, [("ok", "Close", "primary")])
        self.window._may_close = True
        self.window.close()

    def _choose_other_folder(self) -> bool:
        """T40: the folder made by a test build stays as it was; open the folder the user chooses or creates
        instead (on the background thread, like every start). False when the user closes."""
        from sankalan.ui.dialogs import data_folder_refused
        refused = Path(app_paths.load_settings(self.paths)["data_folder"])
        if data_folder_refused.ask_for_folder(self.window, self.paths, refused) is None:
            return False
        self.window.show_status(OPENING)
        self.opener = StorageOpener(self.storage, self._opened, self._failed)
        self.opener.start()
        return True

    def shutdown(self) -> None:
        if self.opener is not None:
            self.opener.wait()
        if self.storage.con is not None or self.storage.runner is not None:
            self.storage.close()
        if self.instance is not None:
            self.instance.release()


def run(argv=None) -> int:
    app = make_application(argv)
    sk = SankalanApp()
    if not sk.start():
        return 0
    try:
        code = app.exec()
    finally:
        sk.shutdown()
    return 1 if sk.failed else code
