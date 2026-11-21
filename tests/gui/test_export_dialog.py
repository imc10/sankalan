"""A2-3: the Export dialog with export in parts (7.4, 7.5; Feature Spec A2 4.3, Tech spec A2 8.6): the size check on
open, the summary and parts lines, the disk-space message (AC-EXP-13), the overwrite list (AC-EXP-10), progress with
"part K of M" (AC-EXP-11), the split banner (AC-EXP-14c) and the cancel banner.

Storage: TPL-R small with R-0001…R-0003 committed (2,500 rows each). The part size is lowered to 1,000 through the
dialog's test hook, so a run's data is written as 3 parts.
"""
import collections
import csv
import io
import re
import threading
from pathlib import Path

import pytest

from conftest import settle_window, spec
from sankalan import exporting
from sankalan.query import catalogue as q
from sankalan.ui.dialogs import export_dialog
from sankalan.ui.jobs import JobBridge
from sankalan.ui.window import MainWindow

GB = 1024 ** 3


@pytest.fixture
def win(app, qtbot, tpl_r_runs):
    from sankalan.ui.dialogs import base
    s = tpl_r_runs["s"]
    export_dialog.part_rows_hook = 1000
    w = MainWindow(JobBridge(s.runner), s)
    w.resize(1366, 768)
    w.show()
    yield w
    export_dialog.part_rows_hook = None
    if w.export_dialog is not None:
        try:
            w.export_dialog.hide()
        except RuntimeError:
            pass
    w.bridge.wait_all(30)
    w.bridge.poll()
    hook, base.answer_hook = base.answer_hook, (lambda _d: "leave")
    try:
        w.close()
    finally:
        base.answer_hook = hook
    w.deleteLater()


def settle(qtbot, w):
    settle_window(qtbot, w, 30_000)


def open_export(qtbot, win, r, kind="data", k=1, settle_first=True):
    assert win.go("run", run_id=r["runs"][k], template_id=r["tid"])
    settle(qtbot, win)
    assert win.current.export(kind)
    dlg = win.export_dialog
    if settle_first:
        settle(qtbot, win)
    return dlg


def choose(dlg, folder):
    export_dialog.folder_hook = lambda _d: str(folder)
    try:
        dlg.change.click()
    finally:
        export_dialog.folder_hook = None


def template_name(r):
    return q.load_template(r["s"].con, r["tid"]).name


@spec("EXP-13", "8.6", "EXP-9", "EXP-10", "4.3")
def test_size_check_on_open_then_summary_and_parts_line(win, qtbot, tpl_r_runs, tmp_path):
    dlg = open_export(qtbot, win, tpl_r_runs, settle_first=False)
    assert dlg.info.text() == "Checking size…" and not dlg.export_button.isEnabled()      # until it returns
    settle(qtbot, win)
    assert dlg.export_button.isEnabled() and dlg.estimate.files == 3
    assert re.fullmatch(r"2,500 rows · 3 CSV files · about [0-9.]+ (KB|MB)", dlg.info.text())
    name = f"Rao & Co_{template_name(tpl_r_runs)}_R-0001_Data"
    assert dlg.parts.isVisible() and dlg.parts.text() == (
        f"Saved as 3 files of up to 1,000 rows each, so each opens fully in Excel: {name}_part01of03.csv to "
        f"…_part03of03.csv")
    dlg.name.setText("March.CSV")
    dlg.name.textEdited.emit("March.CSV")
    assert dlg.parts.text().endswith(": March_part01of03.csv to …_part03of03.csv")
    assert not dlg.space.isVisible()
    dlg.reject()
    # a small export: one file, no parts line, no size
    dlg = open_export(qtbot, win, tpl_r_runs, kind="left_out", k=2)
    assert dlg.info.text() == "63 rows · CSV file" and not dlg.parts.isVisible()
    dlg.reject()


@spec("AC-EXP-13", "EXP-13", "T34")
def test_disk_message_and_a_roomy_folder(win, qtbot, tpl_r_runs, tmp_path, monkeypatch):
    small, roomy = tmp_path / "small", tmp_path / "roomy"
    small.mkdir()
    roomy.mkdir()
    real_drive = exporting._drive
    monkeypatch.setattr(exporting, "_drive", lambda p: "X:" if Path(p) == small else real_drive(p))
    Usage = collections.namedtuple("Usage", "total used free")
    monkeypatch.setattr(exporting.shutil, "disk_usage",
                        lambda p: Usage(0, 0, 512 * 1024 ** 2 if Path(p) == small else 1024 * GB))
    dlg = open_export(qtbot, win, tpl_r_runs)
    choose(dlg, small)
    assert dlg.space.isVisible() and dlg.space.text() == (
        "Not enough free space on X:. This export needs about 1.0 GB, including working space; 512 MB is free. "
        "Free up space or choose a folder on another drive.")
    assert not dlg.export_button.isEnabled() and not dlg.export()
    choose(dlg, roomy)
    assert not dlg.space.isVisible() and dlg.export_button.isEnabled()
    dlg.reject()


@spec("AC-EXP-10", "AC-EXP-14c", "EXP-10", "EXP-14")
def test_overwrite_list_split_banner_and_open_folder(win, qtbot, tpl_r_runs, tmp_path, answers, monkeypatch):
    old = {n: tmp_path / n for n in ("D_part01of03.csv", "D_part02of03.csv", "D_part03of03.csv",
                                     "D_part04of04.csv")}
    for n, p in old.items():
        p.write_bytes(b"old")
    dlg = open_export(qtbot, win, tpl_r_runs)
    choose(dlg, tmp_path)
    dlg.name.setText("D.csv")
    answers.append("cancel")
    assert not dlg.export()
    assert answers.asked[-1] == ("Replace 3 files?", ["Cancel", "Replace"])
    assert answers.texts[-1] == ("These files are already in the folder:\nD_part01of03.csv\nD_part02of03.csv\n"
                                 "D_part03of03.csv\nReplacing them can't be undone.")
    assert all(p.read_bytes() == b"old" for p in old.values())
    opened = []
    from sankalan.ui.widgets import banner as banner_mod
    monkeypatch.setattr(banner_mod, "open_folder", lambda p: opened.append(p))
    answers.append("replace")
    assert dlg.export()
    settle(qtbot, win)
    assert old["D_part04of04.csv"].read_bytes() == b"old"                     # never touched
    assert [len(list(csv.reader(io.StringIO(old[f"D_part0{k}of03.csv"].read_text(encoding="utf-8-sig"),
                                            newline="")))) - 1 for k in (1, 2, 3)] == [1000, 1000, 500]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(old)
    b = win.current.banners()[-1]
    assert b.kind == "success" and b.plain_text == "Exported 2,500 rows to 3 files"
    b.buttons["Open folder"].click()
    assert opened == [tmp_path]


def test_replace_prompt_lists_ten_then_and_more(answers):
    answers.append("cancel")
    assert not export_dialog.replace_prompt(None, [f"D_part{k:03d}of120.csv" for k in range(1, 15)])
    assert answers.asked[-1][0] == "Replace 14 files?"
    lines = answers.texts[-1].split("\n")
    assert lines[1:11] == [f"D_part{k:03d}of120.csv" for k in range(1, 11)] and lines[11] == "and 4 more"


@spec("AC-EXP-11", "EXP-11", "T53", "EXP-14")
def test_progress_shows_part_k_of_m_and_cancel_banner(win, qtbot, tpl_r_runs, tmp_path, monkeypatch):
    monkeypatch.setattr(exporting, "SPLIT_BLOCK", 4096)
    monkeypatch.setattr(exporting, "PROGRESS_EVERY_S", 0)
    held, release = threading.Event(), threading.Event()
    part2 = tmp_path / "D_part02of03.csv.partial"

    def hold():
        if part2.exists() and not held.is_set():
            held.set()
            release.wait(20)
    monkeypatch.setattr(exporting, "_after_block", hold)
    dlg = open_export(qtbot, win, tpl_r_runs)
    choose(dlg, tmp_path)
    dlg.name.setText("D.csv")
    assert dlg.export()
    assert held.wait(20)
    p = dlg.progress
    qtbot.waitUntil(lambda: p.detail.text() == "part 2 of 3", timeout=5000)     # refreshed by the poll
    assert p.stage.text() == "Writing files" and p.detail.isVisible()
    rows = p.rows.text()
    m = re.fullmatch(r"([0-9,]+) of 2,500 rows", rows)
    assert m and 1000 <= int(m.group(1).replace(",", "")) < 2000
    assert dlg.title.text() == f"Exporting {win.last_export.what}" and p.cancel_button.isVisible()
    p.cancel_button.click()
    release.set()
    settle(qtbot, win)
    assert list(tmp_path.iterdir()) == []
    assert win.current.banners()[-1].plain_text == (
        "Export cancelled. No files were written; files that would have been replaced are unchanged.")


@spec("NCK-12", "8.6")
def test_runs_without_checks_offer_no_issue_or_left_out_export():
    from sankalan.model import export as ex
    for kind in ("issues", "left_out"):
        with pytest.raises(ValueError):
            ex.prefill(kind, None, template_id="t", client="c", template="t", checks=False)
