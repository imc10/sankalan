"""Feature D through the screens (Feature Spec A2 5, 10.5; Tech spec A2 7.3, 7.4): the Choose sheets… link, the
Sheet not found banner and footer, and the 4.1c dialog, on the sheet files S01-S06 with the rule "Sales and Sales
Returns" (AC-SHT-1 to AC-SHT-9). Offscreen, real storage; files are read in the Job's thread."""
import shutil

import pytest

from conftest import open_storage, settle_window, spec, tpl_a_columns
from sankalan.model.rule import with_type_rules
from sankalan.model.template import SourceSettings, Template
from sankalan.query import catalogue as q
from sankalan.ui.dialogs.choose_sheets import ChooseSheetsDialog
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens import new_run as nrui
from sankalan.ui.screens.new_run import COMMIT, FILES, MAPPING, VALIDATE, NewRunScreen
from sankalan.ui.screens.run import RunScreen
from sankalan.ui.window import MainWindow

CENTRAL, EAST, WEST = "Sales_Nov-2026_Central.xlsx", "Sales_Nov-2026_East.xlsx", "Sales_Nov-2026_West.xlsx"
PLENTY = 50 * 1024 ** 3


def settle(qtbot, w, timeout=60_000):
    settle_window(qtbot, w, timeout)


@pytest.fixture(autouse=True)
def inline_reader(monkeypatch):
    monkeypatch.setattr(nrui, "WORKERS", 0)


@pytest.fixture(autouse=True)
def discard_on_close(monkeypatch):
    from sankalan.ui.dialogs import base
    monkeypatch.setattr(base, "answer_hook", lambda dlg: "discard")


@pytest.fixture(scope="module")
def env(tmp_path_factory, fixtures_dir):
    s = open_storage(tmp_path_factory.mktemp("sheets_ui"))
    cols = tpl_a_columns()
    tid = q.create_template(s.con, Template("", q.insert_client(s.con, "Acme Traders"), "Sales Register",
                                            SourceSettings(sheets="name", sheet_names=["Sales", "Sales Returns"]),
                                            cols, with_type_rules(cols, [])))
    yield {"s": s, "tid": tid, "fx": fixtures_dir}
    s.close()


@pytest.fixture
def win(app, qtbot, env):
    w = MainWindow(JobBridge(env["s"].runner), env["s"])
    qtbot.addWidget(w)
    w.resize(1366, 768)
    w.show()
    yield w
    w.bridge.wait_all(30)
    w.bridge.poll()


def wizard(qtbot, w, env, *paths) -> NewRunScreen:
    assert w.go("new_run", template_id=env["tid"], name="Sales Register")
    settle(qtbot, w)
    wz = w.current
    assert isinstance(wz, NewRunScreen) and wz.session is not None
    wz.start_info.free_bytes = PLENTY
    wz.free_bytes_for_commit = PLENTY
    wz.files_step.load()
    if paths:
        assert wz.add_files(list(paths))
        settle(qtbot, w)
    return wz


def banners(wz):
    from sankalan.ui.widgets.banner import Banner
    return [b for b in wz.files_step.findChildren(Banner) if b.parent() is wz.files_step and b.kind == "error"]


def choose(qtbot, wz, path, names=None, accept=True) -> ChooseSheetsDialog:
    dlg = wz.choose_sheets(path)
    assert isinstance(dlg, ChooseSheetsDialog)
    if names is not None:
        for name, *_r in dlg.rows():
            dlg.tick(name, name in names)
    (dlg.ok if accept else dlg.buttons["Cancel"]).click()
    settle(qtbot, wz.window_)
    return dlg


@spec("AC-SHT-1", "AC-SHT-2", "AC-SHT-3", "AC-SHT-4", "SHT-2", "SHT-4", "SHT-5", "SHT-6", "SHT-7", "T46")
def test_links_banner_dialog_and_footer(win, qtbot, env, tmp_path):
    fx = env["fx"]
    shutil.copyfile(fx / "Sales_Oct.xlsx", tmp_path / "Sales_Oct.xlsx")
    wz = wizard(qtbot, win, env, fx / CENTRAL, fx / EAST, fx / WEST, fx / "Sales_Nov-2026_Central.xlsb",
                fx / "Sales_Nov-2026_Central.xls", fx / "Conversion_Values.csv", fx / "Sales_Protected.xlsx")
    fs = wz.files_step
    assert fs.accepts.text().endswith("reads sheets Sales and Sales Returns unless you choose others for a file")
    assert fs.choose_links() == [CENTRAL, EAST, WEST, "Sales_Nov-2026_Central.xlsb", "Sales_Nov-2026_Central.xls"]
    texts = {b.plain_text: set(b.buttons) for b in banners(wz)}
    central = "Sales_Nov-2026_Central.xlsx: sheets to read not found. Sheets found: Sales Nov, Returns Nov."
    assert texts[central] == {"Choose sheets…", "Exclude file"}
    assert texts["Sales_Nov-2026_East.xlsx: sheets to read not found. Sheets found: Sales."] == {"Choose sheets…",
                                                                                                "Exclude file"}
    for name in ("Sales_Nov-2026_Central.xlsb", "Sales_Nov-2026_Central.xls", "Sales_Protected.xlsx",
                 "Conversion_Values.csv"):
        wz.remove_file(str(fx / name))
    assert wz.footer.text() == "Choose sheets for 2 files, or exclude them, to continue"
    assert not wz.next_button.isEnabled()
    # AC-SHT-2: the dialog for Central; Cancel leaves the file in error (AC-SHT-3)
    dlg = choose(qtbot, wz, str(fx / CENTRAL), accept=False)
    assert dlg.windowTitle() == "Choose sheets for Sales_Nov-2026_Central.xlsx" and dlg.size_line.text()
    assert dlg.rows() == [("Sales Nov", False, True, "about 300 rows"), ("Returns Nov", False, True, "about 50 rows"),
                          ("Notes", False, False, "Hidden, skipped")]
    assert not dlg.ok.isEnabled() and dlg.ok.text() == "Read 0 sheets"
    dlg2 = wz.choose_sheets(str(fx / CENTRAL))
    dlg2.tick("Sales Nov")
    dlg2.tick("Returns Nov")
    assert dlg2.ok.text() == "Read 2 sheets" and dlg2.total.text() == "2 sheets · about 350 rows"
    assert dlg2.note.text().startswith("The header row is found in each sheet.")
    dlg2.buttons["Cancel"].click()
    settle(qtbot, win)
    assert wz.session.file_rows(fx / CENTRAL)[0].problem == "sheet"
    # AC-SHT-4: East opens with Sales ticked
    dlg = choose(qtbot, wz, str(fx / EAST))
    assert dlg.rows() == [("Sales", True, True, "about 200 rows")] and dlg.ok.text() == "Read 1 sheet"
    assert wz.footer.text() == "Choose sheets for 1 file, or exclude it, to continue"
    choose(qtbot, wz, str(fx / CENTRAL), ["Sales Nov", "Returns Nov"])
    rows = fs.rows()
    assert [(r[0], r[1], r[5]) for r in rows[:2]] == [(CENTRAL, "Sales Nov", "Ready"), (CENTRAL, "Returns Nov",
                                                                                        "Ready")]
    assert banners(wz) == [] and wz.next_button.isEnabled()
    assert "Chosen" not in " ".join(" ".join(r) for r in rows) + wz.footer.text()      # no marker (D66)
    assert choose(qtbot, wz, str(fx / CENTRAL), accept=False).rows()[:2] == [
        ("Sales Nov", True, True, "about 300 rows"), ("Returns Nov", True, True, "about 50 rows")]  # later: the choice
    # AC-SHT-9 (Mapping skipped) and AC-SHT-8 (commit)
    nxt = wz.next
    nxt()
    settle(qtbot, win)
    assert wz.step == VALIDATE and wz.steps.state(MAPPING) == "skipped"
    wz.next()
    settle(qtbot, win)
    if wz.step != COMMIT:
        wz.next()
        settle(qtbot, win)
    assert wz.step == COMMIT
    assert wz.commit()
    settle(qtbot, win)
    sc = win.current
    assert isinstance(sc, RunScreen)
    settle(qtbot, win)
    run = sc.view.run
    assert [(f["file_name"], f["sheet"], f["sheets_chosen"]) for f in run["files"]] == [
        (CENTRAL, "Sales Nov", True), (CENTRAL, "Returns Nov", True), (EAST, "Sales", True),
        (WEST, "Sales", False), (WEST, "Sales Returns", False)]
    assert "Chosen" not in " ".join(" ".join(r) for r in sc.sources_tab.rows())


@spec("AC-SHT-5", "AC-SHT-6", "SHT-8", "SHT-9")
def test_header_not_found_and_renamed_sheet(win, qtbot, env, tmp_path):
    fx = env["fx"]
    west, central = tmp_path / WEST, tmp_path / CENTRAL
    shutil.copyfile(fx / WEST, west)
    shutil.copyfile(fx / CENTRAL, central)
    wz = wizard(qtbot, win, env, west, central)
    choose(qtbot, wz, str(west), ["Cover"])
    (b, _c) = banners(wz)
    assert b.plain_text == "Header not found in sheet Cover." and set(b.buttons) == {"Exclude file"}
    assert WEST not in wz.files_step.choose_links()
    wz.remove_file(str(west))                                            # ✕, then add again: from the rule
    assert wz.add_files([west])
    settle(qtbot, win)
    assert WEST in wz.files_step.choose_links()
    assert [r[1] for r in wz.files_step.rows() if r[0] == WEST] == ["Sales", "Sales Returns"]
    choose(qtbot, wz, str(central), ["Sales Nov", "Returns Nov"])
    assert wz.recheck_files()                                            # the choice is kept
    settle(qtbot, win)
    assert [r[1] for r in wz.files_step.rows() if r[0] == CENTRAL] == ["Sales Nov", "Returns Nov"]
    shutil.copyfile(fx / "Sales_Nov-2026_Central_Renamed.xlsx", central)   # Sales Nov renamed at source
    assert wz.recheck_files()
    settle(qtbot, win)
    assert any(b.plain_text.endswith("Sheets found: Sales November, Returns Nov.") for b in banners(wz))
    dlg = choose(qtbot, wz, str(central), accept=False)
    assert [(n, t) for n, t, _e, _c in dlg.rows()] == [("Sales November", False), ("Returns Nov", True),
                                                       ("Notes", False)]
    assert wz.step == FILES


@spec("FIT-04")
def test_files_with_banner_and_dialog_fit(win, qtbot, env):
    from sankalan.ui import theme
    fx = env["fx"]
    wz = wizard(qtbot, win, env, fx / CENTRAL, fx / EAST)
    frame = wz.minimumSizeHint() - wz.pages.minimumSizeHint()
    hint = wz.files_step.minimumSizeHint() + frame
    assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH and hint.height() <= theme.MIN_LAYOUT.height()
    dlg = wz.choose_sheets(str(fx / CENTRAL))
    assert dlg.sizeHint().height() <= theme.MIN_LAYOUT.height() - 80
    dlg.reject()
