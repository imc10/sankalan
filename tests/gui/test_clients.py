"""Phase 7: Clients (1.1) and Client (1.2) screens: C1-01 to C1-11, C2-01 to C2-08 (offscreen, real storage)."""
import pytest
from PySide6.QtCore import Qt

from conftest import new_run, settle_window, spec, stage_fake_run
from sankalan import formats, manage
from sankalan.db import datafolder
from sankalan.model.template import Column, DefaultOutput, Template
from sankalan.query import catalogue as q
from sankalan.ui import theme
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens.client import ClientScreen
from sankalan.ui.screens.clients import EMPTY, ClientsScreen
from sankalan.ui.screens.common import NameDialog
from sankalan.ui.window import MainWindow


def settle(qtbot, w, timeout=10_000):
    settle_window(qtbot, w, timeout)


@pytest.fixture
def win(app, qtbot, storage):
    w = MainWindow(JobBridge(storage.runner), storage)
    qtbot.addWidget(w)
    w.resize(1366, 768)
    w.show()
    w.open_area("clients")
    settle(qtbot, w)
    yield w
    settle(qtbot, w)


def names(screen):
    return [r[0] for r in screen.visible_rows()]


def submit_name(qtbot, w, text):
    dlg = w.current.dialog
    assert isinstance(dlg, NameDialog)
    dlg.edit.setText(text)
    dlg.save.click()
    settle(qtbot, w)
    return dlg


def add_client(qtbot, w, name):
    w.current.new_client()
    dlg = submit_name(qtbot, w, name)
    assert not dlg.isVisible(), dlg.error.text()
    settle(qtbot, w)


def simple_template(con, client_id, name="Sales Register", outputs=1):
    cols = [Column("c001", "Invoice No"), Column("c002", "Amount", "Number")]
    t = Template("", client_id, name, columns=cols,
                 outputs=[DefaultOutput(f"Out {i}", {"definition_version": 2, "template_id": "", "filters": [],
                                                     "groups": [],
                                                     "measures": [{"column_id": "_rows",
                                                                   "ops": [{"fn": "count", "name": None}]}],
                                                     "subtotals": False}) for i in range(outputs)])
    return q.create_template(con, t)


def commit_fake(storage, tid, rows):
    st = stage_fake_run(storage, rows)
    run = new_run(tid, rows)
    run.template_version = q.template_version(storage.con, tid)
    datafolder.commit(storage.con, storage.folder, st, run)


# ---------------------------------------------------------------------------------------------- C1
@spec("C1-01", "UX-1")
def test_empty_state_and_footer(win):
    s = win.current
    assert isinstance(s, ClientsScreen)
    assert s.stack.currentWidget() is s.empty and s.empty_text.text() == EMPTY
    assert s.empty_button.isVisible() and s.empty_button.text() == "New client"
    assert s.footer.text().startswith("Data stored: 0 rows · 0 GB · ")
    assert s.footer.text().endswith(f" free on {storage_drive(win)}")


def storage_drive(w):
    return manage.drive_of(w.storage.folder.path)


@spec("C1-02", "C1-03", "C1-04", "TPL-2")
def test_create_client_name_required_and_unique(win, qtbot):
    s = win.current
    add_client(qtbot, win, "Acme Traders")
    assert s.visible_rows()[0][:5] == ("Acme Traders", 0, 0, 0, None)
    assert s.stack.currentWidget() is s.grid
    for bad in ("", "   "):                                    # C1-03
        s.new_client()
        dlg = submit_name(qtbot, win, bad)
        assert dlg.isVisible() and dlg.error.text() == "Enter a client name."
        dlg.reject()
    for dup in ("Acme Traders", "acme traders", "  ACME TRADERS "):   # C1-04 (case ignored, confirmed 17-11-2026)
        s.new_client()
        dlg = submit_name(qtbot, win, dup)
        assert dlg.isVisible() and "already in use" in dlg.error.text()
        dlg.reject()
    add_client(qtbot, win, "Bharat Foods")
    s.rename_client(next(r[6] for r in s.visible_rows() if r[0] == "Bharat Foods"), "Bharat Foods")
    dlg = submit_name(qtbot, win, "Acme Traders")                     # C1-04 step 3
    assert dlg.isVisible() and "already in use" in dlg.error.text()
    dlg.reject()
    assert sorted(q.client_names(win.storage.con).values()) == ["Acme Traders", "Bharat Foods"]


@spec("C1-05", "C1-06")
def test_sort_and_search(win, qtbot):
    s = win.current
    for n in ("Acme Traders", "Bharat Foods", "Zenith Exports", "Chopra & Co"):
        add_client(qtbot, win, n)
    assert names(s) == ["Acme Traders", "Bharat Foods", "Chopra & Co", "Zenith Exports"]
    s.grid._header_clicked(0)
    settle(qtbot, win)
    assert names(s) == ["Acme Traders", "Bharat Foods", "Chopra & Co", "Zenith Exports"]
    s.grid._header_clicked(0)
    settle(qtbot, win)
    assert names(s) == ["Zenith Exports", "Chopra & Co", "Bharat Foods", "Acme Traders"]
    assert s.model.data(s.model.index(0, 0)) == "Zenith Exports"
    s.search.setText("bha")
    settle(qtbot, win)
    assert names(s) == ["Bharat Foods"] and s.model.rowCount() == 1
    s.search.setText("xyz")
    settle(qtbot, win)
    assert names(s) == [] and s.stack.currentWidget() is s.empty and "xyz" in s.empty_text.text()
    assert not s.empty_button.isVisible()
    s.search.clear()
    settle(qtbot, win)
    assert len(names(s)) == 4


@spec("C1-07", "C1-08", "GEN-06")
def test_rename_and_open_client(win, qtbot):
    s = win.current
    add_client(qtbot, win, "Acme Traders")
    cid = s.visible_rows()[0][6]
    tid = simple_template(win.storage.con, cid)
    commit_fake(win.storage, tid, 10)
    folders = sorted(p.name for p in win.storage.folder.templates_root.iterdir())
    s.rename_client(cid, "Acme Traders")
    submit_name(qtbot, win, "Acme Traders Pvt")
    assert names(win.current) == ["Acme Traders Pvt"]
    assert sorted(p.name for p in win.storage.folder.templates_root.iterdir()) == folders == [tid]
    win.current._cell(0, "name")                                   # C1-08
    settle(qtbot, win)
    c = win.current
    assert isinstance(c, ClientScreen) and c.breadcrumb.text() == "Clients › Acme Traders Pvt"
    assert c.h1.text() == "Acme Traders Pvt"
    c.breadcrumb.activate(0)
    settle(qtbot, win)
    assert isinstance(win.current, ClientsScreen)


@spec("C1-09", "C1-10", "UX-1")
def test_grid_figures_and_footer(win, qtbot, monkeypatch):
    con = win.storage.con
    cid = q.insert_client(con, "Acme Traders")
    tid = simple_template(con, cid)
    for rows in (5000, 4000, 1937):
        commit_fake(win.storage, tid, rows)
    last = q.latest_run(con, tid)[3]
    s = win.current
    s.refresh()
    settle(qtbot, win)
    assert s.visible_rows()[0][:5] == ("Acme Traders", 1, 3, 10937, last)
    assert s.model.data(s.model.index(0, 3)) == "10,937"
    assert s.model.data(s.model.index(0, 4)) == formats.date_time(last)
    assert s.subtitle.text() == "1 client · 1 template · 3 runs"
    size = win.storage.folder.size_bytes()
    assert s.footer.text().startswith(f"Data stored: 10,937 rows · {formats.gigabytes(size)} · ")
    assert s.footer.property("low") is False or s.overview.storage.free_bytes < manage.LOW_DISK_BYTES
    monkeypatch.setattr(type(win.storage.folder), "free_bytes", lambda self: 3 * 1024 ** 3)   # C1-10
    s.refresh()
    settle(qtbot, win)
    assert s.footer.property("low") is True and theme.WARNING in s.footer.styleSheet()
    assert "3.0 GB free on" in s.footer.text()


@spec("C1-11", "TPL-2", "UI-8")
def test_delete_client(win, qtbot):
    con, folder = win.storage.con, win.storage.folder
    keep = q.insert_client(con, "Acme Traders")
    simple_template(con, keep)
    cid = q.insert_client(con, "Delete Me Ltd")
    tid = simple_template(con, cid, "Temp")
    commit_fake(win.storage, tid, 1000)
    q.insert_saved_analysis(con, tid, "AN", {})
    s = win.current
    s.refresh()
    settle(qtbot, win)
    s.delete_client(cid)
    settle(qtbot, win)
    dlg = s.dialog
    assert dlg.windowTitle() == "Delete Delete Me Ltd?"
    assert dlg.listed == ["1 template", "1 run and 1,000 rows", "1 saved analysis"]
    assert not dlg.delete_button.isEnabled()
    dlg.understand.setChecked(True)
    dlg.delete_button.click()
    settle(qtbot, win)
    assert names(s) == ["Acme Traders"]
    assert not folder.template_dir(tid).exists()
    assert q.saved_analysis_count(con, template_id=tid) == 0
    assert s.footer.text().startswith("Data stored: 0 rows")


# ---------------------------------------------------------------------------------------------- C2
def open_client(win, qtbot, cid, name):
    win.go("client", client_id=cid, name=name)
    settle(qtbot, win)
    return win.current


@spec("C2-01")
def test_client_empty_state(win, qtbot):
    cid = q.insert_client(win.storage.con, "Acme Traders")
    c = open_client(win, qtbot, cid, "Acme Traders")
    assert c.stack.currentWidget() is c.empty
    assert c.empty_text.text() == "No templates for Acme Traders yet. A template is set up from one sample file."
    assert c.empty_button.text() == "New template"
    assert c.breadcrumb.text() == "Clients › Acme Traders"


@spec("C2-02", "C2-03", "C2-04", "UX-2")
def test_template_grid_new_run_and_search(win, qtbot, answers):
    con = win.storage.con
    cid = q.insert_client(con, "Acme Traders")
    tid = simple_template(con, cid, outputs=2)
    commit_fake(win.storage, tid, 5000)
    c = open_client(win, qtbot, cid, "Acme Traders")
    row = c.visible_rows()[0]
    modified = con.execute("SELECT modified_on FROM template WHERE id = ?", [tid]).fetchone()[0]
    assert row[:7] == ("Sales Register", 2, 2, 1, 5000, q.latest_run(con, tid)[3], modified)
    assert c.model.data(c.model.index(0, 6)) == formats.date(modified.date())
    assert c.model.data(c.model.index(0, 7)) == "New run"
    assert [a.text() for a in c.row_menu(0).actions()] == ["Rename", "Duplicate", "Delete"]
    answers.append("cancel")                                       # C2-04
    assert not c.new_run(0) and win.current is c
    assert answers.asked[-1][0] == "Start a new run on Sales Register?"
    c.duplicate_template(tid)
    settle(qtbot, win)
    c.search.setText("copy")                                       # C2-03
    settle(qtbot, win)
    assert [r[0] for r in c.visible_rows()] == ["Sales Register (copy)"]
    c.search.clear()
    settle(qtbot, win)
    answers.append("start")
    assert c.new_run(0)
    assert win.current.h1.text() == "New run"


@spec("C2-05", "TPL-4")
def test_rename_template_unique_within_client(win, qtbot):
    con = win.storage.con
    acme = q.insert_client(con, "Acme Traders")
    bharat = q.insert_client(con, "Bharat Foods")
    tid = simple_template(con, acme)
    simple_template(con, bharat, "Conversion check")
    second = simple_template(con, acme, "Purchase Register")
    c = open_client(win, qtbot, acme, "Acme Traders")
    v = q.template_version(con, tid)
    c.rename_template(tid, "Sales Register")
    dlg = submit_name(qtbot, win, "Conversion check")              # other client's name: accepted
    assert not dlg.isVisible()
    assert q.template_version(con, tid) == v + 1                   # a rename is a save (TPL-7)
    c.rename_template(tid, "Conversion check")
    submit_name(qtbot, win, "Sales Register")
    c.rename_template(second, "Purchase Register")
    dlg = submit_name(qtbot, win, "sales register")
    assert dlg.isVisible() and "already in use" in dlg.error.text()
    dlg.reject()


@spec("C2-06", "C2-08", "TPL-4", "UI-8")
def test_duplicate_and_delete_template(win, qtbot):
    con, folder = win.storage.con, win.storage.folder
    cid = q.insert_client(con, "Acme Traders")
    tid = simple_template(con, cid, outputs=2)
    commit_fake(win.storage, tid, 5000)
    c = open_client(win, qtbot, cid, "Acme Traders")
    c.duplicate_template(tid)
    settle(qtbot, win)
    copy = next(r for r in c.visible_rows() if r[0] == "Sales Register (copy)")
    assert copy[1:6] == (2, 2, 0, 0, None)
    copy_id = copy[-1]
    commit_fake(win.storage, copy_id, 5000)
    q.insert_saved_analysis(con, copy_id, "AN-3", {})
    c.delete_template(copy_id)
    settle(qtbot, win)
    dlg = c.dialog
    assert dlg.windowTitle() == "Delete Sales Register (copy)?"
    assert dlg.listed == ["1 run and 5,000 rows", "1 saved analysis"]
    assert not dlg.delete_button.isEnabled()
    dlg.understand.setChecked(True)
    dlg.delete_button.click()
    settle(qtbot, win)
    assert [r[0] for r in c.visible_rows()] == ["Sales Register"]
    assert not folder.template_dir(copy_id).exists() and folder.template_dir(tid).exists()
    assert q.saved_analysis_count(con, template_id=copy_id) == 0
    assert len(q.list_runs(con, tid)) == 1
