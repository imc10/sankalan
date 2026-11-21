"""Prompt buttons clicked for real. Every other GUI test answers ``ask()`` through ``base.answer_hook``, which skips
the dialog's own buttons; these tests leave the hook off, wait for the modal dialog and click its button with the
mouse. Regression: the buttons of every ``ask()`` prompt returned False (Qt's ``clicked(bool)`` filled the lambda's
key parameter), so "Discard", "Discard run", "Leave without saving" and the rest did nothing.

Covers each Discard point: New template (Cancel and leaving by the rail), New run (Cancel and leaving by the rail),
the Template screen's editing tabs (the bar's Discard, switching tab, leaving the screen) and an unsaved analysis.
"""
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from conftest import commit_tpl_a_run, open_storage, settle_window, tpl_a_template
from sankalan.model import definition as d
from sankalan.model.definition import Group, Measure
from sankalan.query import catalogue as q
from sankalan.ui.dialogs import base
from sankalan.ui.dialogs.base import Choice, ask
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens import new_run as nrui
from sankalan.ui.screens import new_template as ntui
from sankalan.ui.screens.analyses import AnalysesScreen
from sankalan.ui.screens.analysis import AnalysisScreen
from sankalan.ui.screens.client import ClientScreen
from sankalan.ui.screens.clients import ClientsScreen
from sankalan.ui.screens.new_run import NewRunScreen
from sankalan.ui.screens.new_template import NewTemplateScreen
from sankalan.ui.screens.template import OUTPUTS, RUNS, TemplateScreen
from sankalan.ui.window import MainWindow

STATE, TAXABLE = "c005", "c006"


def settle(qtbot, w, timeout=30_000):
    settle_window(qtbot, w, timeout)


@pytest.fixture(autouse=True)
def real_dialogs(monkeypatch):
    monkeypatch.setattr(base, "answer_hook", None)
    monkeypatch.setattr(ntui, "WORKERS", 0)
    monkeypatch.setattr(nrui, "WORKERS", 0)


@pytest.fixture(scope="module")
def tpla(tmp_path_factory, fixtures_dir):
    s = open_storage(tmp_path_factory.mktemp("buttons"))
    acme = q.insert_client(s.con, "Acme Traders")
    tid = q.create_template(s.con, tpl_a_template(acme))
    commit_tpl_a_run(s, tid, fixtures_dir, "Sales_Oct.xlsx")
    yield {"s": s, "tid": tid, "client": acme, "fx": fixtures_dir}
    s.close()


@pytest.fixture
def win(app, qtbot, tpla):
    w = MainWindow(JobBridge(tpla["s"].runner), tpla["s"])
    w.resize(1366, 768)
    w.show()
    yield w
    w.bridge.wait_all(30)
    w.bridge.poll()
    # a failed test can leave a wizard open: answer its leave prompt so closing never waits on a real dialog
    base.answer_hook = lambda dlg: next((k for k in ("discard", "leave") if k in KEYS.get(dlg.windowTitle(), ())),
                                        None)
    try:
        w.open_area("clients")
        w._may_close = True
        w.close()
    finally:
        base.answer_hook = None
    w.deleteLater()


KEYS = {"Discard this template?": ("discard",), "Leave and discard this run?": ("discard",),
        "Save your changes?": ("discard",), "This analysis isn't saved": ("leave",)}


class Clicker:
    """Clicks ``label`` in the next modal ``Choice`` with the mouse; records its title and buttons."""

    def __init__(self):
        self.seen: list[tuple[str, list[str]]] = []

    def arm(self, label: str, tries: int = 100) -> None:
        def go(left=tries):
            dlg = QApplication.activeModalWidget()
            if not isinstance(dlg, Choice):
                if left:
                    QTimer.singleShot(50, lambda: go(left - 1))
                return
            self.seen.append((dlg.windowTitle(), list(dlg.buttons)))
            button = dlg.buttons.get(label)
            if button is None:
                dlg.reject()
                return
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        QTimer.singleShot(0, go)


@pytest.fixture
def clicker():
    return Clicker()


def staging(tpla):
    return list(tpla["s"].folder.staging_root.iterdir())


# ---------------------------------------------------------------------------------------------- ask() itself
@pytest.mark.parametrize("label,key", [("Stay", "stay"), ("Discard", "discard"), ("Save", "save")])
def test_every_choice_button_returns_its_key(app, clicker, label, key):
    clicker.arm(label)
    got = ask(None, "Save your changes?", "", [("stay", "Stay", None), ("discard", "Discard", None),
                                                ("save", "Save", "primary")])
    assert got == key
    assert clicker.seen == [("Save your changes?", ["Stay", "Discard", "Save"])]


# ---------------------------------------------------------------------------------------------- New template
def open_new_template(qtbot, win, tpla, sample=True) -> NewTemplateScreen:
    assert win.go("new_template", client_id=tpla["client"], name="Acme Traders")
    settle(qtbot, win)
    wz = win.current
    assert isinstance(wz, NewTemplateScreen)
    if sample:
        wz.sample_step.name.setText("Sales Register 2")
        assert wz.pick(tpla["fx"] / "Sample_Sales.xlsx")
        settle(qtbot, win)
        assert wz.staged is not None and staging(tpla)
    return wz


@pytest.mark.parametrize("sample", [False, True])
def test_new_template_cancel_discard(win, qtbot, tpla, clicker, sample):
    wz = open_new_template(qtbot, win, tpla, sample)
    clicker.arm("Discard")
    QTest.mouseClick(wz.cancel_button, Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert clicker.seen == [("Discard this template?", ["Keep editing", "Discard"])]
    assert isinstance(win.current, ClientScreen)
    assert staging(tpla) == []
    assert list(q.template_names(tpla["s"].con, tpla["client"]).values()) == ["Sales Register"]


def test_new_template_cancel_keep_editing(win, qtbot, tpla, clicker):
    wz = open_new_template(qtbot, win, tpla)
    clicker.arm("Keep editing")
    QTest.mouseClick(wz.cancel_button, Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert win.current is wz and wz.staged is not None
    clicker.arm("Discard")
    QTest.mouseClick(wz.cancel_button, Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert isinstance(win.current, ClientScreen) and staging(tpla) == []


def test_new_template_leave_by_rail_discard(win, qtbot, tpla, clicker):
    open_new_template(qtbot, win, tpla)
    clicker.arm("Discard")
    QTest.mouseClick(win.rail.buttons["clients"], Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert clicker.seen[-1][0] == "Discard this template?"
    assert isinstance(win.current, ClientsScreen) and staging(tpla) == []


# ---------------------------------------------------------------------------------------------- New run
def open_new_run(qtbot, win, tpla, files=True) -> NewRunScreen:
    assert win.go("new_run", template_id=tpla["tid"], name="Sales Register")
    settle(qtbot, win)
    wz = win.current
    assert isinstance(wz, NewRunScreen)
    if files:
        assert wz.add_files([tpla["fx"] / "Sales_Nov.xlsx"])
        settle(qtbot, win)
        wz.next()                                   # read the files: staging now holds them
        settle(qtbot, win)
        assert wz.step > nrui.FILES and staging(tpla)
    return wz


@pytest.mark.parametrize("files", [False, True])
def test_new_run_cancel_discard(win, qtbot, tpla, clicker, files):
    wz = open_new_run(qtbot, win, tpla, files)
    clicker.arm("Discard run")
    QTest.mouseClick(wz.cancel_button, Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert clicker.seen == [("Leave and discard this run?", ["Stay", "Discard run"])]
    assert isinstance(win.current, TemplateScreen)
    assert staging(tpla) == []


def test_new_run_cancel_stay(win, qtbot, tpla, clicker):
    wz = open_new_run(qtbot, win, tpla)
    clicker.arm("Stay")
    QTest.mouseClick(wz.cancel_button, Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert win.current is wz and staging(tpla)
    clicker.arm("Discard run")
    QTest.mouseClick(wz.cancel_button, Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert isinstance(win.current, TemplateScreen) and staging(tpla) == []


def test_new_run_leave_by_rail_discard(win, qtbot, tpla, clicker):
    open_new_run(qtbot, win, tpla)
    clicker.arm("Discard run")
    QTest.mouseClick(win.rail.buttons["analysis"], Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert clicker.seen[-1][0] == "Leave and discard this run?"
    assert isinstance(win.current, AnalysesScreen) and staging(tpla) == []


# ---------------------------------------------------------------------------------------------- Template screen
def dirty_outputs_tab(qtbot, win, tpla):
    assert win.go("template", template_id=tpla["tid"], name="Sales Register")
    settle(qtbot, win)
    sc = win.current
    sc.select_tab(OUTPUTS)
    settle(qtbot, win)
    tab = sc.outputs_tab
    tab.select(0)
    label = tab.builder.measures.rows[0].label
    saved = label.text()
    label.setText("Edited label")
    label.textEdited.emit("Edited label")
    assert tab.dirty
    return sc, tab, saved


def test_template_bar_discard(win, qtbot, tpla):
    sc, tab, saved = dirty_outputs_tab(qtbot, win, tpla)
    QTest.mouseClick(tab.bar.discard, Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert not tab.dirty and tab.builder.measures.rows[0].label.text() == saved


def test_template_switch_tab_discard(win, qtbot, tpla, clicker):
    sc, tab, saved = dirty_outputs_tab(qtbot, win, tpla)
    clicker.arm("Discard")
    sc.tabs.setCurrentIndex(RUNS)                   # as a click on the Runs tab
    settle(qtbot, win)
    assert clicker.seen == [("Save your changes?", ["Stay", "Discard", "Save"])]
    assert sc.pages.currentIndex() == RUNS and not tab.dirty


def test_template_leave_screen_discard(win, qtbot, tpla, clicker):
    sc, tab, saved = dirty_outputs_tab(qtbot, win, tpla)
    clicker.arm("Discard")
    QTest.mouseClick(win.rail.buttons["clients"], Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert clicker.seen[-1][0] == "Save your changes?"
    assert isinstance(win.current, ClientsScreen)
    outputs = q.load_template(tpla["s"].con, tpla["tid"]).outputs
    assert outputs[0].definition["measures"][0].get("label") != "Edited label"


# ---------------------------------------------------------------------------------------------- Analysis
def test_unsaved_analysis_leave_without_saving(win, qtbot, tpla, clicker):
    assert win.go("analysis")
    settle(qtbot, win)
    sc = win.current
    assert isinstance(sc, AnalysisScreen)
    sc.choose_template("Acme Traders", "Sales Register")
    settle(qtbot, win)
    sc.tick(["R-0001"])
    sc.builder.add_group(Group(STATE))
    sc.builder.add_measure(Measure(TAXABLE, d.SUM))
    assert sc.run(), sc.error.text()
    settle(qtbot, win)
    clicker.arm("Leave without saving")
    QTest.mouseClick(win.rail.buttons["clients"], Qt.MouseButton.LeftButton)
    settle(qtbot, win)
    assert clicker.seen[-1] == ("This analysis isn't saved", ["Stay", "Leave without saving", "Save…"])
    assert isinstance(win.current, ClientsScreen)
