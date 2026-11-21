"""Feature F through the screens (Feature Spec A2 7, 10.7; Tech spec A2 6): the New run wizard's Load step and the
4.5b Commit for TPL-N small, the Run screen and Runs list of a run without checks, and Template › Settings and
Columns & rules changing TPL-R to No and back (AC-NCK-2 to AC-NCK-8). Offscreen, real storage; files are read in
the Job's thread."""
import threading

import pytest

import tpl_n
from conftest import settle_window, spec
from sankalan.query import catalogue as q
from sankalan.ui.jobs import JobBridge
from sankalan.ui.screens import new_run as nrui
from sankalan.ui.screens.new_run import COMMIT, FILES, MAPPING, OUTPUTS, VALIDATE, NewRunScreen
from sankalan.ui.screens.run import ISSUES, RunScreen
from sankalan.ui.screens.template import SETTINGS, TemplateScreen
from sankalan.ui.window import MainWindow

PLENTY = 50 * 1024 ** 3
F1, F2 = tpl_n.FILES
COLS_TAB = 2


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
def env(tpl_r_runs, tpl_n_small):
    """TPL-R small with R-0001…R-0003 (checked) and TPL-N (no checks) in one storage."""
    s = tpl_r_runs["s"]
    fx, m = tpl_n_small
    tid = q.create_template(s.con, tpl_n.template(tpl_r_runs["client"]))
    return {**tpl_r_runs, "ntid": tid, "nfx": fx, "nm": m, "nruns": {}}


@pytest.fixture
def win(app, qtbot, env):
    w = MainWindow(JobBridge(env["s"].runner), env["s"])
    qtbot.addWidget(w)
    w.resize(1366, 768)
    w.show()
    yield w
    w.bridge.wait_all(30)
    w.bridge.poll()


def wizard(qtbot, w, env, *files, tid=None) -> NewRunScreen:
    assert w.go("new_run", template_id=tid or env["ntid"], name="Purchase Register N")
    settle(qtbot, w)
    wz = w.current
    assert isinstance(wz, NewRunScreen) and wz.session is not None
    wz.start_info.free_bytes = PLENTY
    wz.free_bytes_for_commit = PLENTY
    wz.files_step.load()
    if files:
        assert wz.add_files([env["nfx"] / f for f in files])
        settle(qtbot, w)
    return wz


def nxt(qtbot, wz, expect=None):
    wz.next()
    settle(qtbot, wz.window_)
    if expect is not None:
        assert wz.step == expect, (wz.step, [b.plain_text for b in wz.banners()])


# ---------------------------------------------------------------------------------------------- Load and Commit
@spec("AC-NCK-2", "AC-NCK-4", "AC-NCK-6", "AC-NCK-8", "NCK-6", "NCK-8", "NCK-9", "NCK-10", "NCK-12", "T45")
def test_load_commit_and_run_screen(win, qtbot, env):
    m = env["nm"]
    wz = wizard(qtbot, win, env, F1, F2)
    assert wz.steps.labels == ["Files", "Mapping", "Load", "Outputs", "Commit"]
    nxt(qtbot, wz, VALIDATE)                                    # Mapping skipped: Files → Load
    assert wz.steps.state(MAPPING) == "skipped" and wz.pages.currentWidget() is wz.load_step
    ls = wz.load_step
    assert ls.result_banner.plain_text == "2 files read · 10,000 rows to load"
    assert ls.stat_values() == {"files": "2 files · 2 sheets", "rows": "10,003", "load": "10,000", "text": "80"}
    assert ls.skipped.text() == "Blank rows skipped: 3" and ls.skipped.isVisible()
    assert ls.column_rows() == [("Invoice Date", "Date", "12"), ("Taxable Value", "Number", "68")]
    assert wz.next_button.text() == "Next: Outputs" and wz.next_button.isEnabled()
    assert wz.recheck_button.isVisible() and not wz.override_button.isVisible()
    assert wz.footer.text() == "10,000 rows will load"
    ls.columns.selectRow(1)                                     # Taxable Value: the values list (AC-NCK-4)
    settle(qtbot, win)
    want = [(t["text"], f"{t['count']:,}", tpl_n.FILES[t["file_index"]], "", f"{t['row']:,}")
            for t in m.taxable_text]
    assert ls.value_rows() == want and ls.value_rows()[0][:2] == ("NA", "40")
    assert ls.values_title.text() == "Taxable Value: values as typed"
    nxt(qtbot, wz, OUTPUTS)
    settle(qtbot, win)
    assert wz.session.outputs_done
    nxt(qtbot, wz, COMMIT)
    settle(qtbot, win)
    cs = wz.commit_step
    assert cs.summary["Data checks"] == "Not checked · template setting"
    assert cs.summary["Rows left out"] == "None" and cs.summary["Blank rows skipped"] == "3"
    assert cs.summary["Rows to load"] == "10,000" and "Errors" not in cs.summary
    assert cs.text_lines == ["Invoice Date: 12 values aren't dates and are left out of date filters and groups",
                             "Taxable Value: 68 values aren't numbers and are left out of sums"]
    assert cs.totals_note.isVisible() and cs.totals_note.text() == "Values that aren't numbers count as 0 on both sides"
    assert cs.totals_state.text() == "All totals match: In the files = Loaded."
    assert cs.comment_label.text() == "Comment · optional" and cs.can_commit()       # no comment needed (NCK-10)
    assert wz.commit()
    settle(qtbot, win)
    sc = win.current
    assert isinstance(sc, RunScreen)
    settle(qtbot, win)
    env["nruns"]["R-0001"] = sc.run_id
    assert any("R-0001 committed: 10,000 rows and 1 output saved." in b.plain_text for b in sc.banners())
    # AC-NCK-8: Run detail
    assert not sc.tabs.isTabVisible(ISSUES)
    figs = dict(sc.summary_tab.figures)
    assert figs["Data checks"] == "Not checked" and figs["Rows left out"] == "None"
    assert figs["Blank rows skipped"] == "3" and figs["Rows read"] == "10,003" and "Errors" not in figs
    assert sc.subtitle.text().endswith("10,000 rows · Not checked")
    assert [a.text() for a in sc.more_menu().actions() if a.text()] == ["Delete run"]
    assert sc.export_request("issues") is None and sc.export_request("left_out") is None
    # Runs list
    assert win.go("template", template_id=env["ntid"], name="Purchase Register N")
    settle(qtbot, win)
    ts = win.current
    from sankalan.ui.widgets.paged_grid import display
    from sankalan.ui.screens.template import RUN_COLUMNS
    issues = next(c for c in RUN_COLUMNS if c.key == "issues")
    assert [display(r[4], issues) for r in ts.runs_tab.visible_rows()] == ["Not checked"]
    assert [a.text() for a in ts.runs_tab.row_menu(0).actions() if a.text()] == ["Open", "Export data", "Delete"]


@spec("AC-NCK-3", "NCK-7")
def test_cancel_load_goes_back_and_empties_staging(win, qtbot, env):
    wz = wizard(qtbot, win, env, F2)
    wz.load_anyway(str(env["nfx"] / F2))                        # loaded in R-0001 already
    sess = wz.session
    orig = sess.load_unchecked
    hold = threading.Event()

    def slow(ctx):
        hold.set()
        while not ctx.cancel_requested:
            threading.Event().wait(0.01)
        return orig(ctx)
    sess.load_unchecked = slow
    wz.next()
    assert hold.wait(30)
    assert wz.step == VALIDATE and wz.progress.isVisible() and wz.progress.cancel_button.isVisible()
    wz.progress.cancel()
    settle(qtbot, win)
    assert wz.step == FILES and sess.staging is None                     # Mapping was skipped
    assert not any(env["s"].folder.staging_root.iterdir())


@spec("AC-NCK-3", "AC-NCK-5", "NCK-5", "Tech spec A2 6.6")
def test_new_header_maps_then_back_from_load_and_recheck(win, qtbot, env, tmp_path):
    extra = tmp_path / "Purchases_Extra.csv"
    lines = (env["nfx"] / F1).read_text(encoding="utf-8").splitlines()[:6]
    extra.write_text("".join(f"{x},{'Remarks' if i == 0 else 'ok'}\n" for i, x in enumerate(lines)), encoding="utf-8")
    wz = wizard(qtbot, win, env)
    assert wz.add_files([extra])
    settle(qtbot, win)
    nxt(qtbot, wz, MAPPING)                                     # a new header needs a decision (AC-NCK-5)
    assert wz.next_button.text() == "Next: Load"
    kind, sheet, position = wz.session.mapping.first_undecided()
    wz.session.mapping.leave_out(sheet, position)
    nxt(qtbot, wz, VALIDATE)
    assert wz.load_step.stat_values()["load"] == "5"
    assert wz.recheck()                                         # headers unchanged: loads again, decisions kept
    settle(qtbot, win)
    assert wz.step == VALIDATE and wz.load_step.stat_values()["load"] == "5"
    extra.write_text("".join(f"{x},{'Remarks' if i == 0 else 'ok'},{'Branch Code' if i == 0 else 'B1'}\n"
                             for i, x in enumerate(lines)), encoding="utf-8")
    assert wz.recheck()                                         # a new header: back to Mapping
    settle(qtbot, win)
    assert wz.step == MAPPING and wz.session.staging is None
    wz.back()
    settle(qtbot, win)
    assert wz.step == FILES
    extra.unlink()
    assert wz.recheck_files()
    settle(qtbot, win)
    assert wz.session.files_blockers()


# ---------------------------------------------------------------------------------------------- Settings, 3.3
@spec("AC-NCK-7", "NCK-11", "NCK-13", "TPL-7")
def test_settings_no_then_yes_on_tpl_r(win, qtbot, env):
    s, tid = env["s"], env["tid"]
    before = q.template_version(s.con, tid)
    assert win.go("template", template_id=tid, name="Sales Register R")
    settle(qtbot, win)
    ts = win.current
    assert isinstance(ts, TemplateScreen)
    ts.select_tab(SETTINGS)
    st = ts.settings_tab
    assert st.checks.value() and st.checks.hint.text() == ("A change applies from the next run. Runs already loaded "
                                                           "don't change.")
    st.checks.no.click()
    assert st.dirty
    st.save()
    settle(qtbot, win)
    assert q.template_version(s.con, tid) == before + 1
    t = q.load_template(s.con, tid)
    assert t.checks is False and any(r.id == "r1" for r in t.rules)          # rules kept
    ts.select_tab(COLS_TAB)
    settle(qtbot, win)
    ct = ts.columns_tab
    ct.select("c001")
    assert ct.not_in_use.isVisible() and ct.not_in_use.text() == "Not in use: this template loads without checks"
    assert not ct.add_rule_button.isEnabled() and not ct.test_button.isVisible()
    assert ct.rule_rows() and all(not ct.rules_table.cellWidget(r, 2).isEnabled()
                                  for r in range(ct.rules_table.rowCount()))
    assert ct.rules_table.cellWidget(1, 4) is None                           # no remove control
    n = len(ct.rules)
    assert ct.add_rule("not_blank", {}) is None and len(ct.rules) == n       # not editable
    assert ct.name.isEnabled()                                               # column edits allowed
    # the next run has a Load step; earlier runs keep their Issues tab
    wz = wizard(qtbot, win, env, tid=tid)
    assert wz.steps.labels[VALIDATE] == "Load"
    assert win.go("run", run_id=env["runs"][2], template_id=tid)
    settle(qtbot, win)
    assert win.current.tabs.isTabVisible(ISSUES)
    # No -> Yes puts the rules back in use
    assert win.go("template", template_id=tid, name="Sales Register R")
    settle(qtbot, win)
    ts = win.current
    ts.select_tab(SETTINGS)
    ts.settings_tab.checks.yes.click()
    ts.settings_tab.save()
    settle(qtbot, win)
    assert q.template_version(s.con, tid) == before + 2 and q.load_template(s.con, tid).checks
    ts.select_tab(COLS_TAB)
    settle(qtbot, win)
    assert not ts.columns_tab.not_in_use.isVisible() and ts.columns_tab.add_rule_button.isEnabled()
    assert ts.columns_tab.test_button.isVisible()


@spec("FIT-04")
def test_new_screens_fit_the_smallest_layout(win, qtbot, env):
    from sankalan.ui import theme
    wz = wizard(qtbot, win, env, F1)
    wz.load_anyway(str(env["nfx"] / F1))
    nxt(qtbot, wz, VALIDATE)
    nxt(qtbot, wz, OUTPUTS)
    settle(qtbot, win)
    nxt(qtbot, wz, COMMIT)
    settle(qtbot, win)
    # The stacked pages' hint is the tallest page's, and a Mapping page that was skipped (never loaded) is taller
    # than these; so each new page is measured with the frame around it.
    frame = wz.minimumSizeHint() - wz.pages.minimumSizeHint()
    for step in (VALIDATE, COMMIT):
        hint = wz.pages.widget(step).minimumSizeHint() + frame
        assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH, (step, hint)
        assert hint.height() <= theme.MIN_LAYOUT.height(), (step, hint)
    assert win.go("template", template_id=env["ntid"], name="Purchase Register N")
    settle(qtbot, win)
    ts = win.current
    for tab in (COLS_TAB, SETTINGS):
        ts.select_tab(tab)
        settle(qtbot, win)
        hint = ts.minimumSizeHint()
        assert hint.width() <= theme.MIN_LAYOUT.width() - theme.RAIL_WIDTH, (tab, hint)
        assert hint.height() <= theme.MIN_LAYOUT.height(), (tab, hint)
