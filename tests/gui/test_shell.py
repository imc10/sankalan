"""Phase 6: UI shell and design system (UI-1…8, UX §2–5, NF-3, NF-4, ENV-4).

Covers what is automatable of GEN-01…06, FIT-01…04, SH-02…05 and DEP-04…09 (offscreen). Colour-picker, real
display scaling and Windows dark-mode checks stay manual.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtCore import QLocale, QMargins, QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QPushButton, QScrollArea

from conftest import ROOT, make_paths, spec
from sankalan import APP_NAME, __version__
from sankalan.jobs import JobBusy, JobState
from sankalan.ui import theme
from sankalan.ui.jobs import BUSY_TOOLTIP, JobBridge
from sankalan.ui.screens.base import LeaveGuard, PlaceholderScreen, Screen
from sankalan.ui.widgets.breadcrumb import Crumb
from sankalan.ui.window import MainWindow, close_prompt, minimum_window_size


def wait_job(qtbot, bridge, job, timeout=10_000):
    job.wait(timeout / 1000)
    qtbot.waitUntil(lambda: job not in [t.job for t in bridge._tracked], timeout=timeout)


# ---------------------------------------------------------------------------------------------- theme
@spec("GEN-03", "UI-1")
def test_bundled_fonts_monogram_and_tabular_figures(app):
    """IBM Plex Sans and Plex Sans Devanagari load from the app's own files; the app font is Plex with tabular
    figures; the Devanagari font has the "सं" glyphs; the mark is teal."""
    from PySide6.QtGui import QFontDatabase, QFontMetrics
    assert theme.load_fonts()
    families = QFontDatabase.families()
    assert theme.FAMILY in families and theme.DEVANAGARI_FAMILY in families
    f = app.font()
    assert f.family() == theme.FAMILY and f.pixelSize() == theme.BODY_PX
    assert f.featureValue(QFont.Tag("tnum")) == 1
    fm = QFontMetrics(theme.font(14, family=theme.DEVANAGARI_FAMILY))
    assert all(fm.inFontUcs4(ord(c)) for c in theme.MONOGRAM)
    img = theme.monogram_pixmap(64).toImage()
    assert img.pixelColor(4, 32) == QColor(theme.TEAL)          # teal square
    whites = sum(1 for x in range(64) for y in range(64) if img.pixelColor(x, y).name() == "#ffffff")
    assert whites > 30                                          # the glyph is drawn, not boxes
    assert not app.windowIcon().isNull()


@spec("GEN-02", "UI-3")
def test_light_look_only(app, qtbot):
    """The colour scheme is forced to Light and the palette is the canvas palette; a primary button paints teal,
    a destructive one red."""
    pal = app.palette()
    assert pal.window().color() == QColor(theme.WHITE)
    assert pal.text().color() == QColor(theme.TEXT)
    assert pal.highlight().color() == QColor(theme.TINT)
    for kind, colour in (("primary", theme.TEAL), ("destructive", theme.ERROR), ("secondary", theme.WHITE)):
        b = QPushButton("Go")
        b.setProperty("kind", kind)
        qtbot.addWidget(b)
        b.resize(120, 36)
        b.show()
        img = b.grab().toImage()
        assert img.pixelColor(8, 18) == QColor(colour), kind
    css = theme.style_sheet()
    for token in (theme.TEAL, theme.TINT, theme.TEAL_DARK, theme.ERROR, theme.TEXT, theme.MUTED):
        assert token in css


@spec("GEN-02", "UI-3")
@pytest.mark.skipif(sys.platform != "win32", reason="the Windows platform plugin decides the colour scheme")
def test_light_even_when_windows_is_dark():
    """On the real Windows platform (offscreen ignores colour schemes): with the scheme set to Dark, as Windows
    dark mode does, applying the theme turns it back to Light, so widgets and the title bar stay light."""
    code = ("from PySide6.QtWidgets import QApplication; from PySide6.QtCore import Qt\n"
            "a = QApplication([]); a.styleHints().setColorScheme(Qt.ColorScheme.Dark)\n"
            "assert a.styleHints().colorScheme() == Qt.ColorScheme.Dark\n"
            "from sankalan.ui import theme; theme.apply(a)\n"
            "print(a.styleHints().colorScheme().name, a.palette().window().color().name())\n")
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.split() == ["Light", "#ffffff"]


@spec("GEN-04", "UI-7")
def test_numbers_and_dates_ignore_the_region(app):
    """With Qt and Python set to German, grid values still show 7,536,875.00 and 16-11-2026."""
    import locale
    from sankalan.ui.widgets.paged_grid import DATE, DATETIME, INTEGER, NUMBER, GridColumn, display
    old = QLocale()
    QLocale.setDefault(QLocale(QLocale.Language.German, QLocale.Country.Germany))
    try:
        try:
            locale.setlocale(locale.LC_ALL, "de-DE")
        except locale.Error:
            pass
        assert display(Decimal("7536875.00"), GridColumn("a", "A", NUMBER, 2)) == "7,536,875.00"
        assert display(Decimal("1507.375"), GridColumn("a", "A", NUMBER, 2)) == "1,507.38"
        assert display(5000, GridColumn("a", "A", INTEGER)) == "5,000"
        assert display(dt.date(2026, 11, 16), GridColumn("a", "A", DATE)) == "16-11-2026"
        assert display(dt.datetime(2026, 11, 16, 14, 32), GridColumn("a", "A", DATETIME)) == "16-11-2026 14:32"
    finally:
        locale.setlocale(locale.LC_ALL, "C")
        QLocale.setDefault(old)


def test_format_helpers():
    from sankalan import formats
    assert formats.elapsed(42) == "0:42" and formats.elapsed(725) == "12:05" and formats.elapsed(3729) == "1:02:09"
    assert formats.size(int(41.6 * 1024 ** 3)) == "41.6 GB"
    assert formats.size(112 * 1024 ** 3) == "112 GB"
    assert formats.size(2048) == "2.0 KB" and formats.size(10) == "10 bytes"


# ---------------------------------------------------------------------------------------------- grid
class FakeSource:
    def __init__(self, n=1000):
        self.n = n
        self.pages = []
        self.sorts = []

    def count(self, ctx, sort):
        return self.n

    def page(self, ctx, offset, limit, sort):
        self.pages.append(offset)
        self.sorts.append(list(sort))
        rows = [(f"INV-{i:05d}", Decimal(i) * Decimal("1234.5"), dt.date(2026, 10, 1 + i % 28))
                for i in range(offset, min(self.n, offset + limit))]
        return list(reversed(rows)) if sort and not sort[0][1] else rows


@pytest.fixture
def grid(app, qtbot, runner):
    from sankalan.ui.widgets.paged_grid import DATE, NUMBER, GridColumn, PagedGrid, PagedModel
    bridge = JobBridge(runner)
    src = FakeSource()
    cols = [GridColumn("inv", "Invoice No"), GridColumn("amt", "Taxable Value", NUMBER, 2, width=160),
            GridColumn("dt", "Invoice Date", DATE, width=140, sortable=False)]
    model = PagedModel(bridge, cols, src)
    g = PagedGrid(model)
    qtbot.addWidget(g)
    g.resize(900, 500)
    g.show()
    model.refresh()
    qtbot.waitUntil(lambda: model.total == 1000 and not model.loading, timeout=10_000)
    return g, model, src, bridge


@spec("GEN-05", "UI-2")
def test_grid_density(grid):
    """Rows and header 40 px; grid text 13 px; header 12 px; the grid scrolls inside itself."""
    g, model, _src, _b = grid
    assert g.verticalHeader().defaultSectionSize() == theme.ROW_HEIGHT == 40
    assert g.rowHeight(0) == 40
    assert g.horizontalHeader().height() == 40
    assert g.font().pixelSize() == theme.GRID_TEXT_PX == 13
    assert g.horizontalHeader().font().pixelSize() == theme.GRID_HEADER_PX
    assert not g.verticalHeader().isVisible()
    assert g.verticalScrollBar().maximum() > 0


def test_grid_pages_formats_and_sorts(grid, qtbot):
    g, model, src, _b = grid
    idx = model.index(3, 1)
    assert model.data(idx) == "3,703.50"
    assert model.data(model.index(3, 2)) == "04-10-2026"
    assert model.data(idx, Qt.ItemDataRole.TextAlignmentRole) & int(Qt.AlignmentFlag.AlignRight)
    assert src.pages == [0]
    g.scrollToBottom()
    model.data(model.index(999, 0))
    qtbot.waitUntil(lambda: 800 in src.pages and not model.loading, timeout=10_000)
    assert model.data(model.index(999, 0)) == "INV-00999"
    g._header_clicked(0)
    g._header_clicked(0)                      # second click: descending
    qtbot.waitUntil(lambda: not model.loading and model.row_values(0) is not None, timeout=10_000)
    assert src.sorts[-1] == [("inv", False)]
    assert model.data(model.index(0, 0)) == "INV-00199"
    n = len(src.sorts)
    g._header_clicked(2)                      # not sortable
    assert model.sort_spec == [("inv", False)] and len(src.sorts) == n


# ---------------------------------------------------------------------------------------------- jobs
@spec("SH-02", "T6")
def test_one_long_job_at_a_time(app, qtbot, runner, gate):
    """While a long Job runs, guarded start controls are disabled with "Another operation is running"; they come
    back afterwards with their own state; a second long Job is refused; quiet Jobs disable nothing."""
    bridge = JobBridge(runner)
    run_btn = QPushButton("Run")
    run_btn.setToolTip("Run the analysis")
    off_btn = QPushButton("Export")
    qtbot.addWidget(run_btn)
    qtbot.addWidget(off_btn)
    bridge.guard(run_btn)
    bridge.guard(off_btn, allowed=False)
    assert run_btn.isEnabled() and not off_btn.isEnabled()

    quiet = bridge.try_quiet("Fetch rows", lambda ctx: 1)
    assert quiet is not None
    assert run_btn.isEnabled()
    wait_job(qtbot, bridge, quiet)

    job = bridge.start("Validate", gate)
    assert bridge.busy and bridge.current is job
    assert not run_btn.isEnabled() and run_btn.toolTip() == BUSY_TOOLTIP
    with pytest.raises(JobBusy):
        bridge.start("Export", lambda ctx: None)
    assert bridge.try_quiet("Fetch rows", lambda ctx: 1) is None
    gate.release.set()
    wait_job(qtbot, bridge, job)
    assert not bridge.busy
    assert run_btn.isEnabled() and run_btn.toolTip() == "Run the analysis"
    assert not off_btn.isEnabled()
    bridge.set_allowed(off_btn, True)
    assert off_btn.isEnabled()


def test_long_job_stops_a_quiet_job(app, qtbot, runner, gate):
    bridge = JobBridge(runner)
    cancelled = []
    quiet = bridge.try_quiet("Fetch rows", gate, on_cancelled=lambda: cancelled.append(1))
    assert gate.started.wait(5)
    done = []
    job = bridge.start("Export", lambda ctx: "x", on_done=done.append)
    assert quiet.state is JobState.CANCELLED and cancelled == [1]
    wait_job(qtbot, bridge, job)
    assert done == ["x"]


@spec("UI-5", "NF-3")
def test_progress_panel(app, qtbot, runner, gate):
    """Stage, bar, "1,000 of 4,000 rows", elapsed and Cancel; Cancel stops the Job; no Cancel for a commit."""
    from sankalan.ui.widgets.progress import ProgressPanel
    bridge = JobBridge(runner)
    panel = ProgressPanel(cancel_text="Cancel export")
    qtbot.addWidget(panel)
    panel.show()
    job = bridge.start("Export", gate)
    assert gate.started.wait(5)
    panel.bind(job)
    qtbot.waitUntil(lambda: panel.rows.text() == "1,000 of 4,000 rows", timeout=5_000)
    assert panel.stage.text() == "Working"
    assert panel.bar.value() == 250
    assert panel.elapsed.text().endswith("elapsed")
    assert panel.cancel_button.isVisible() and panel.cancel_button.text() == "Cancel export"
    with qtbot.waitSignal(panel.finished, timeout=10_000):
        panel.cancel_button.click()
    assert job.state is JobState.CANCELLED
    wait_job(qtbot, bridge, job)

    g2 = threading.Event()
    commit = bridge.start("Commit", lambda ctx: g2.wait(10), cancellable=False)
    panel.bind(commit)
    assert not panel.cancel_button.isVisible()
    assert panel.bar.maximum() == 0                # no fraction known: busy indicator
    g2.set()
    wait_job(qtbot, bridge, commit)


# ---------------------------------------------------------------------------------------------- widgets
@spec("UI-8")
def test_delete_confirm(app, qtbot):
    from sankalan.ui.dialogs.delete_confirm import UNDERSTAND, DeleteConfirm
    d = DeleteConfirm("Delete R-0007?", "This removes the run from Monthly Sales Register:",
                      ["9,702,233 rows", "The issue list", "3 saved outputs"],
                      note="Saved analyses that used this run will no longer include its data.", button="Delete run")
    qtbot.addWidget(d)
    assert d.listed == ["9,702,233 rows", "The issue list", "3 saved outputs"]
    assert "The issue list" in d.items.text()
    assert d.understand.text() == UNDERSTAND
    assert not d.delete_button.isEnabled()
    d.understand.setChecked(True)
    assert d.delete_button.isEnabled()
    d.delete_button.click()
    assert d.result() == d.DialogCode.Accepted.value or d.result() == 1
    assert d.width() == theme.DIALOG_WIDTH


def test_step_bar(app, qtbot):
    from sankalan.ui.widgets.stepbar import CURRENT, DONE, PENDING, SKIPPED, StepBar
    s = StepBar(["Files", "Mapping", "Validate", "Outputs", "Commit"])
    qtbot.addWidget(s)
    s.set_skipped({1})
    s.set_current(3)
    assert [s.state(i) for i in range(5)] == [DONE, SKIPPED, DONE, CURRENT, PENDING]
    assert not s.dots[0].pixmap().isNull() and s.dots[1].text() == "–" and s.dots[3].text() == "4"
    assert theme.TEAL in s.dots[3].styleSheet()


@spec("SH-05")
def test_banners(app, qtbot, monkeypatch, tmp_path):
    from sankalan.ui.widgets import banner
    opened = []
    monkeypatch.setattr(banner, "open_folder", lambda p: opened.append(p))
    f = tmp_path / "out.csv"
    b = banner.success("written.", lead="R-0001 exported:", folder=f)
    qtbot.addWidget(b)
    assert b.plain_text == "R-0001 exported: written."
    b.buttons["Open folder"].click()
    assert opened == [f]
    plain = banner.Banner("success", "R-0013 committed.")
    qtbot.addWidget(plain)
    plain.show()
    plain.dismiss()
    assert plain.isHidden()


# ---------------------------------------------------------------------------------------------- window
class Level(Screen):
    def __init__(self, window, depth, names):
        self.title = names[depth]
        super().__init__(window)
        self.depth, self.names = depth, names
        self.dirty = False
        self.saved = False

    def crumbs(self):
        if self.depth == 0:
            return []
        return [Crumb(n, (lambda d=d: self.window_.open_screen(Level(self.window_, d, self.names))))
                for d, n in enumerate(self.names[:self.depth])] + [Crumb(self.names[self.depth])]

    def leave_guard(self):
        if not self.dirty:
            return None
        return LeaveGuard.unsaved(save=self._save)

    def _save(self):
        self.saved = True
        return True


@pytest.fixture
def window(app, qtbot, runner):
    w = MainWindow(JobBridge(runner))
    qtbot.addWidget(w)
    w.resize(theme.MIN_LAYOUT)
    w.show()
    w.open_area("clients")
    return w


@spec("DEP-04", "UI-4", "NF-6")
def test_title_bar(window):
    assert window.windowTitle() == APP_NAME == "Sankalan"
    assert not window.windowIcon().isNull()


@spec("GEN-01")
def test_left_rail(window, monkeypatch):
    """A 64 px rail: Clients and Analysis at the top, the gear at the bottom; each opens its screen; the selected
    item is highlighted."""
    rail = window.rail
    assert rail.width() == 64
    assert [b.text() for b in rail.buttons.values()] == ["Clients", "Analysis"]
    assert rail.buttons["clients"].y() < rail.buttons["analysis"].y() < rail.settings_button.y()
    assert rail.settings_button.y() > rail.height() / 2
    assert window.current.title == "Clients" and rail.selected() == "clients"
    rail.buttons["analysis"].click()
    assert window.current.title == "Analyses" and rail.selected() == "analysis"
    assert rail.buttons["analysis"].isChecked() and not rail.buttons["clients"].isChecked()
    rail.buttons["clients"].click()
    assert window.current.title == "Clients"
    opened = []
    monkeypatch.setattr(window, "open_settings", lambda: opened.append(1))
    rail.settingsClicked.disconnect()
    rail.settingsClicked.connect(window.open_settings)
    rail.settings_button.click()
    assert opened == [1]


@spec("GEN-06", "UX-1")
def test_breadcrumbs_one_level_per_screen(window):
    names = ["Clients", "Acme Traders", "Sales Register", "R-0001"]
    window.open_screen(Level(window, 3, names))
    assert window.stack.count() == 1
    assert window.current.breadcrumb.text() == "Clients › Acme Traders › Sales Register › R-0001"
    for target in (2, 1, 0):
        window.current.breadcrumb.activate(target)
        assert window.current.title == names[target]
        assert window.stack.count() == 1
        if target:
            window.open_screen(Level(window, 3, names))
    assert not window.current.breadcrumb.isVisible()


@spec("UX §5")
def test_leave_guards(window, answers):
    """Unsaved edits: Stay keeps the screen; Save saves and leaves; Discard leaves. Also the run wizard and
    unsaved-analysis prompts carry the canvas copy."""
    s = Level(window, 1, ["Clients", "Acme Traders"])
    window.open_screen(s)
    s.dirty = True
    answers.extend(["stay"])
    assert not window.open_area("clients")
    assert window.current is s and window.rail.selected() == "clients"
    assert answers.asked[-1] == ("Save your changes?", ["Stay", "Discard", "Save"])
    answers.extend(["save"])
    assert window.open_area("analysis")
    assert s.saved
    s2 = Level(window, 1, ["Clients", "Acme Traders"])
    window.open_screen(s2)
    s2.dirty = True
    answers.extend(["discard"])
    assert window.open_area("clients") and not s2.saved
    run = LeaveGuard.discard_run(lambda: True)
    assert run.title == "Leave and discard this run?"
    assert [o[1] for o in run.options] == ["Stay", "Discard run"]
    ana = LeaveGuard.unsaved_analysis(lambda: True)
    assert ana.title == "This analysis isn't saved"
    assert [o[1] for o in ana.options] == ["Stay", "Leave without saving", "Save…"]


@spec("FIT-04", "ENV-4")
def test_minimum_size_is_design_size_capped_to_the_screen():
    """1366×768 including the frame; capped to the work area (1920×1080 at 150% = 1280×720 logical)."""
    frame = QMargins(8, 31, 8, 8)
    assert minimum_window_size(QSize(1920, 1040), frame) == QSize(1366 - 16, 768 - 39)          # 100%
    assert minimum_window_size(QSize(1536, 824), frame) == QSize(1366 - 16, 768 - 39)           # 125%
    assert minimum_window_size(QSize(1280, 688), frame) == QSize(1280 - 16, 688 - 39)           # 150%
    assert minimum_window_size(QSize(1366, 728), frame) == QSize(1366 - 16, 728 - 39)           # laptop
    assert minimum_window_size(QSize(1920, 1040)) == QSize(1366, 768)


@spec("FIT-01", "FIT-02", "FIT-03", "UI-2")
def test_shell_fits_the_smallest_layout(window):
    """The shell's own minimum fits the smallest supported layout, and the window has no scroll area: grids and
    long panels scroll inside themselves."""
    for area in ("clients", "analysis"):
        window.open_area(area)
        hint = window.centralWidget().minimumSizeHint()
        assert hint.width() <= theme.MIN_LAYOUT.width() and hint.height() <= theme.MIN_LAYOUT.height()
    assert window.findChildren(QScrollArea) == []
    assert window.minimumSize().width() <= window.screen().availableGeometry().width()


def test_close_prompt_text():
    assert close_prompt("Validate") == "Cancel validate and close?"
    assert close_prompt("Export") == "Cancel export and close?"


@spec("SH-03")
def test_closing_during_a_cancellable_job(window, qtbot, answers, gate):
    """No keeps working; Yes cancels, and the window closes once the Job has stopped."""
    job = window.bridge.start("Validate", gate)
    assert gate.started.wait(5)
    answers.extend(["no"])
    window.close()
    assert window.isVisible() and job.state is JobState.RUNNING
    assert answers.asked[-1] == ("Cancel validate and close?", ["No", "Yes"])
    answers.extend(["yes"])
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=10_000)
    assert job.state is JobState.CANCELLED


@spec("SH-04", "RUN-5")
def test_closing_during_commit_waits(window, qtbot, answers):
    """No prompt; the window waits for the commit to finish, then closes."""
    release = threading.Event()
    job = window.bridge.start("Commit", lambda ctx: release.wait(10) and "R-0001", cancellable=False)
    window.close()
    assert window.isVisible() and answers.asked == []
    assert window.status.isVisible() and "Finishing commit" in window.status.text()
    assert not window.centralWidget().isEnabled()
    window.close()                                  # a second click still waits
    assert window.isVisible()
    release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=10_000)
    assert job.state is JobState.DONE and job.result == "R-0001"


def test_rail_shows_the_running_job(window, qtbot, gate):
    origin = []
    job = window.bridge.start("Validate", gate, origin=lambda: origin.append(1))
    qtbot.waitUntil(lambda: window.rail.job_button.isVisible(), timeout=5_000)
    assert window.rail.job_button.text() == "25%"
    assert window.rail.job_button.toolTip().startswith("Validate · Working · ")
    window.rail.job_button.click()
    assert origin == [1]
    gate.release.set()
    wait_job(qtbot, window.bridge, job)
    assert not window.rail.job_button.isVisible()


# ---------------------------------------------------------------------------------------------- App settings
@pytest.fixture
def settings_dialog(app, qtbot, storage):
    from sankalan.ui.dialogs.app_settings import AppSettingsDialog
    bridge = JobBridge(storage.runner)
    picks = []
    d = AppSettingsDialog(storage, bridge, chooser=lambda _p, _s: picks.pop(0) if picks else None)
    qtbot.addWidget(d)
    d.show()
    return d, picks, bridge


@spec("DEP-06", "UX-11")
def test_app_settings_shows_folder_and_version(settings_dialog, storage):
    d, _p, _b = settings_dialog
    assert d.windowTitle() == "App settings"
    assert d.folder.text() == str(storage.folder.path) and d.folder.isReadOnly()
    assert d.change.text() == "Change…"
    assert d.version.text() == f"Version {__version__}"


@spec("DEP-08", "ENV-5", "T25")
def test_change_refuses_network_paths(settings_dialog, storage):
    d, picks, _b = settings_dialog
    before = str(storage.folder.path)
    picks.append(r"\\fileserver\share\Sankalan")
    d.change_folder()
    assert d.message.isVisible() and "network" in d.message.text().lower()
    assert str(storage.folder.path) == before and d.folder.text() == before


@spec("DEP-09", "T25")
def test_change_warns_for_onedrive(settings_dialog, storage, tmp_path, answers):
    d, picks, bridge = settings_dialog
    before = str(storage.folder.path)
    picks.append(str(tmp_path / "OneDrive" / "SankalanData"))
    answers.extend(["cancel"])
    d.change_folder()
    assert answers.asked and answers.asked[-1][0] == "Use a synced folder?"
    assert bridge.current is None and str(storage.folder.path) == before


@spec("DEP-07", "UI-5")
def test_change_moves_the_data_folder(settings_dialog, storage, tmp_path, qtbot):
    """Progress in the dialog; afterwards the folder shown, the storage and settings.json point at the new
    folder; the old folder is gone; Close is held while the move runs."""
    d, picks, bridge = settings_dialog
    old = storage.folder.path
    dest = tmp_path / "NewData"
    picks.append(str(dest))
    changed = []
    d.dataFolderChanged.connect(changed.append)
    d.change_folder()
    assert d.moving and not d.close_button.isEnabled() and not d.change.isEnabled()
    d.reject()
    assert d.isVisible()                                   # Esc / ✕ wait for the move
    qtbot.waitUntil(lambda: not d.moving, timeout=30_000)
    assert d.folder.text() == str(dest) == changed[0]
    assert Path(storage.folder.path) == dest and not Path(old).exists()
    settings = json.loads(storage.paths.settings_file.read_text(encoding="utf-8"))
    assert settings["data_folder"] == str(dest)
    assert d.close_button.isEnabled() and d.change.isEnabled()


# ---------------------------------------------------------------------------------------------- app
@spec("DEP-05")
def test_single_instance(app, qtbot):
    from sankalan.ui.single_instance import SingleInstance
    key = f"Sankalan.test.{id(qtbot)}"
    first = SingleInstance(key)
    assert first.first
    first.publish(123456)
    second = SingleInstance(key)
    assert not second.first
    assert second.other_window() == 123456
    second.release()
    first.release()
    third = SingleInstance(key)
    assert third.first                     # the block goes with the first copy
    third.release()


@spec("V3-1", "T5")
def test_app_opens_storage_off_the_ui_thread(app, qtbot, tmp_path, monkeypatch):
    """The window shows "Opening your data…" while storage opens on another thread, then shows Clients."""
    from sankalan import app as app_mod
    from sankalan.db.storage import Storage
    threads = []
    real_open = Storage.open

    def spy(self):
        threads.append(threading.current_thread() is threading.main_thread())
        return real_open(self)

    monkeypatch.setattr(Storage, "open", spy)
    sk = app_mod.SankalanApp(make_paths(tmp_path), instance_key=f"Sankalan.test.app.{id(tmp_path)}")
    assert sk.start()
    qtbot.addWidget(sk.window)
    assert sk.window.status.text() == app_mod.OPENING
    qtbot.waitUntil(lambda: sk.window.current is not None, timeout=20_000)
    assert threads == [False]
    assert sk.window.current.title == "Clients" and not sk.window.status.isVisible()
    assert sk.bridge.runner is sk.storage.runner and sk.window.storage is sk.storage
    sk.window.close()
    sk.shutdown()
    assert sk.storage.con is None


def test_app_start_failure_is_reported(app, qtbot, tmp_path, monkeypatch, answers):
    from sankalan import app as app_mod
    from sankalan.db.storage import Storage

    def boom(self):
        raise OSError("locked")

    monkeypatch.setattr(Storage, "open", boom)
    sk = app_mod.SankalanApp(make_paths(tmp_path), instance_key=f"Sankalan.test.fail.{id(tmp_path)}")
    answers.extend(["ok"])
    assert sk.start()
    qtbot.addWidget(sk.window)
    qtbot.waitUntil(lambda: sk.failed, timeout=10_000)
    assert answers.asked[-1] == (APP_NAME, ["Close"])
    assert not sk.window.isVisible()
    sk.shutdown()


# ---------------------------------------------------------------------------------------------- A2-1: version-1 folders
def _start_refused(app, qtbot, tmp_path, monkeypatch, answers, picked=None):
    from sankalan import app as app_mod
    from sankalan.ui.dialogs import data_folder_refused as dfr
    from conftest import version_1_folder
    p, data, snapshot = version_1_folder(tmp_path)
    before = snapshot()
    chosen = []
    monkeypatch.setattr(dfr, "CHOOSER", lambda parent, start, title: (chosen.append(title), picked)[1])
    sk = app_mod.SankalanApp(p, instance_key=f"Sankalan.test.v1.{id(tmp_path)}")
    return sk, p, data, snapshot, before, chosen


@spec("T40", "D77")
def test_version_1_folder_refused_close_changes_nothing(app, qtbot, tmp_path, monkeypatch, answers):
    sk, p, data, snapshot, before, _chosen = _start_refused(app, qtbot, tmp_path, monkeypatch, answers)
    answers.extend(["close"])
    assert sk.start()
    qtbot.addWidget(sk.window)
    qtbot.waitUntil(lambda: sk.failed, timeout=10_000)
    assert answers.asked[0] == ("Sankalan", ["Close", "Create new folder…", "Choose folder…"])
    assert not sk.window.isVisible()
    sk.shutdown()
    assert snapshot() == before                       # the folder and settings.json exactly as they were


@spec("T40", "D77")
def test_version_1_folder_refused_create_new_folder_opens_it(app, qtbot, tmp_path, monkeypatch, answers):
    import json
    where = tmp_path / "Elsewhere"
    where.mkdir()
    sk, p, data, snapshot, before, chosen = _start_refused(app, qtbot, tmp_path, monkeypatch, answers, str(where))
    answers.extend(["create"])
    assert sk.start()
    qtbot.addWidget(sk.window)
    qtbot.waitUntil(lambda: sk.window.current is not None, timeout=20_000)
    assert chosen == ["Choose where to create the new data folder"]
    new = where / "Sankalan Data"
    assert json.loads(p.settings_file.read_text(encoding="utf-8")) == {"data_folder": str(new)}
    assert sk.storage.folder.path == new and (new / "catalogue.duckdb").is_file()
    assert sk.window.current.title == "Clients" and not sk.failed
    sk.window.close()
    sk.shutdown()
    old = {k: v for k, v in before.items() if k.startswith("Data")}
    assert {k: v for k, v in snapshot().items() if k.startswith("Data")} == old     # the refused folder untouched


@spec("T40")
def test_version_1_folder_choose_refuses_a_full_folder_then_accepts_a_data_folder(app, qtbot, tmp_path, monkeypatch,
                                                                                   answers):
    from conftest import open_storage
    other = tmp_path / "Other"
    open_storage(other).close()                        # a version-2 data folder elsewhere
    other_data = make_paths(other).root / "Data"
    full = tmp_path / "Full"
    full.mkdir()
    (full / "notes.txt").write_text("x", encoding="utf-8")
    picks = iter([str(full), str(other_data)])
    sk, p, data, snapshot, before, chosen = _start_refused(app, qtbot, tmp_path, monkeypatch, answers)
    from sankalan.ui.dialogs import data_folder_refused as dfr
    monkeypatch.setattr(dfr, "CHOOSER", lambda parent, start, title: next(picks))
    answers.extend(["choose", "choose"])
    assert sk.start()
    qtbot.addWidget(sk.window)
    qtbot.waitUntil(lambda: sk.window.current is not None, timeout=20_000)
    assert len(answers.asked) == 2                     # the full folder was refused with the reason, then asked again
    assert sk.storage.folder.path == other_data
    sk.window.close()
    sk.shutdown()
