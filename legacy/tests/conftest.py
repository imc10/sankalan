import json
import os
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sankalan.demo import make_misc_set, make_sales_set  # noqa: E402

RESULTS = []


def spec(*ids):
    """Tag a test with the spec items it proves."""
    return pytest.mark.spec(*ids)


def pytest_configure(config):
    config.addinivalue_line("markers", "spec(*ids): spec items covered by the test")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        m = item.get_closest_marker("spec")
        RESULTS.append({"test": item.nodeid, "spec": list(m.args) if m else [], "outcome": rep.outcome,
                        "seconds": round(rep.duration, 2), "doc": (item.function.__doc__ or "").strip()})


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("SANKALAN_TEST_REPORT")
    if path:
        Path(path).write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")


@pytest.fixture
def sales(tmp_path):
    exp = make_sales_set(tmp_path / "sales", rows_per_file=300)
    exp["folder"] = tmp_path / "sales"
    return exp


@pytest.fixture
def misc(tmp_path):
    return make_misc_set(tmp_path / "misc")


@pytest.fixture
def out_dir(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    return d


class FakePrompter:
    """Answers the UI's questions from queues; records what was asked."""

    def __init__(self):
        self.asked = []
        self.answers = {}

    def _next(self, kind, default=None):
        q = self.answers.get(kind)
        if isinstance(q, list):
            return q.pop(0) if q else default
        return q if q is not None else default

    def files(self, title="Add files"):
        self.asked.append(("files", title))
        q = self.answers.get("files") or []
        if q and isinstance(q[0], list):      # queue of answers
            return q.pop(0)
        self.answers["files"] = []            # a single answer: one list of paths
        return list(q)

    def folder(self, title="", start=""):
        self.asked.append(("folder", title))
        return self._next("folder")

    def save_file(self, title, default, filt=""):
        self.asked.append(("save_file", title))
        return self._next("save_file")

    def password(self, filename):
        self.asked.append(("password", filename))
        return self._next("password")

    def confirm(self, title, text, yes="Yes", no="Cancel"):
        self.asked.append(("confirm", title, text))
        return self._next("confirm", False)

    def info(self, title, text):
        self.asked.append(("info", title, text))

    def error(self, title, text):
        self.asked.append(("error", title, text))

    def text(self, title, label, value=""):
        self.asked.append(("text", title, label))
        return self._next("text")

    def new_consolidation(self):
        self.asked.append(("new_consolidation",))
        return self._next("new_consolidation")


@pytest.fixture
def prompter():
    return FakePrompter()


@pytest.fixture
def window(qtbot, tmp_path, prompter):
    from PySide6.QtCore import QSettings
    from sankalan.ui import style as S
    from sankalan.ui.app import MainWindow
    from PySide6.QtWidgets import QApplication
    QApplication.instance().setStyleSheet(S.QSS)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    w = MainWindow(prompter=prompter, store_folder=tmp_path / "templates", settings=settings)
    qtbot.addWidget(w)
    w.show()
    return w


def wait_idle(qtbot, w, timeout=60000):
    qtbot.waitUntil(lambda: not w.is_busy, timeout=timeout)
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
