"""3.1 Template (UX-4 to UX-7): header with the summary line and New run; tabs Runs · Default outputs · Columns and
rules · Settings (C4-01 to C4-18).

Each editing tab keeps its own unsaved edits. Leaving a tab or the screen with unsaved edits asks Save / Discard /
Stay (C4-08). A save reloads the template as last saved and applies only that tab's part, so tabs never overwrite
each other's settings; every save is a new template version (TPL-7).
"""
from __future__ import annotations

from functools import partial
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QStackedWidget, QVBoxLayout, QWidget

from sankalan import formats, manage
from sankalan.jobs import JobContext
from sankalan.model import export as ex
from sankalan.model.run import STATUS_OVERRIDE
from sankalan.model.template import Template
from sankalan.query import catalogue as q
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.screens.base import STAY, LeaveGuard
from sankalan.ui.screens.common import DataScreen, error_text
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.breadcrumb import Crumb
from sankalan.ui.widgets.controls import CountTabs, SearchBox, primary
from sankalan.ui.widgets.paged_grid import (DATETIME, INTEGER, LINK, MENU, TEXT, GridColumn, ListSource, PagedGrid,
                                            PagedModel)

RUNS, OUTPUTS, COLUMNS_TAB, SETTINGS = range(4)
TAB_LABELS = ["Runs", "Default outputs", "Columns and rules", "Settings"]


def update_template(ctx: JobContext, template_id: str, apply: Callable[[Template], None]) -> Template:
    """Load the template as last saved, apply one tab's edits, save it as a new version (TPL-7)."""
    t = q.load_template(ctx.cursor(), template_id)
    apply(t)
    return manage.save_template(ctx, t)


def summary_line(d: manage.TemplateDetail) -> str:
    """C4-01: "3 runs · 10,937 rows · 0.1 GB · last loaded 16-11-2026 14:32"."""
    if not d.runs:
        return "No runs yet"
    return (f"{formats.count(len(d.runs), 'run')} · {formats.count(d.rows, 'row')} · "
            f"{formats.gigabytes(d.size_bytes)} · last loaded {formats.date_time(d.last_loaded)}")


def status_text(status: str, damaged: bool = False) -> str:
    if damaged:
        return "Files missing"
    return "Committed with override" if status == STATUS_OVERRIDE else "Committed"


NOT_CHECKED = "Not checked"


def issues_text(v) -> str:
    """"2 errors · 1 warning", or "Not checked" for a run loaded without checks (NCK-12), held as (-1, -1) so the
    column still sorts."""
    if v is None or v[0] < 0:
        return NOT_CHECKED
    errors, warnings = v
    return f"{formats.count(errors, 'error')} · {formats.count(warnings, 'warning')}"


RUN_COLUMNS = [
    GridColumn("run", "Run ID", LINK, width=88, fmt=lambda n: f"R-{n:04d}"),
    GridColumn("loaded", "Loaded on", DATETIME, width=150),
    GridColumn("files", "Files", INTEGER, width=84, fmt=lambda v: formats.count(len(v), "file"), tooltip=2),
    GridColumn("rows", "Rows", INTEGER, width=120),
    GridColumn("issues", "Issues", TEXT, width=180, fmt=issues_text),
    GridColumn("status", "Status", TEXT, width=196, fmt=lambda v: v,
               colour=lambda v: theme.OVERRIDE_TEXT if v == "Committed with override"
               else theme.ERROR if v == "Files missing" else None),
    GridColumn("comment", "Comment", TEXT, tooltip=6),
    GridColumn("menu", "", MENU, width=44, sortable=False, fmt=lambda _v: "⋯"),
]
RUN_ID = len(RUN_COLUMNS)


class TemplateTab(QWidget):
    """An editing tab. ``dirty`` while it holds unsaved edits; ``apply`` copies them onto a template."""
    def __init__(self, screen: "TemplateScreen"):
        super().__init__(screen)
        self.screen = screen
        self.dirty = False

    def load(self, detail: manage.TemplateDetail) -> None: ...

    def apply(self, t: Template) -> None: ...

    def check(self) -> str | None:
        """A reason the edits can't be saved yet, shown before any Job starts."""
        return None

    def discard(self) -> None:
        self.set_dirty(False)
        if self.screen.detail is not None:
            self.load(self.screen.detail)

    def set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        bar = getattr(self, "bar", None)
        if bar is not None:
            bar.set_dirty(dirty)

    def save(self, then: Callable[[], None] | None = None) -> None:
        self.screen.save_tab(self, then)


class RunsTab(QWidget):
    """3.1 Runs grid (UX-4, RUN-2, C4-02 to C4-04)."""

    def __init__(self, screen: "TemplateScreen"):
        super().__init__(screen)
        self.screen = screen
        self.dirty = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(12)
        top = QHBoxLayout()
        self.search = SearchBox("Search comments and file names", self, 320)
        self.search.textChanged.connect(self._search)
        top.addWidget(self.search)
        top.addStretch(1)
        self.order = QLabel("Newest first", self)
        self.order.setProperty("kind", "small")
        top.addWidget(self.order)
        lay.addLayout(top)
        self.source = ListSource(RUN_COLUMNS, default_sort=[("run", False)], matches=self._matches)
        self.model = PagedModel(screen.bridge, RUN_COLUMNS, None, parent=self)
        self.stack = QStackedWidget(self)
        self.grid = PagedGrid(self.model, self.stack)
        self.grid.cellClicked.connect(self._cell)
        self.grid.rowActivated.connect(self.open_row)
        self.stack.addWidget(self.grid)
        self.empty = QLabel("", self.stack)
        self.empty.setProperty("kind", "body")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.empty.setContentsMargins(0, 48, 0, 0)
        self.stack.addWidget(self.empty)
        lay.addWidget(self.stack, 1)

    @staticmethod
    def _matches(row, text: str) -> bool:
        t = text.casefold()
        return t in (row[6] or "").casefold() or any(t in f.casefold() for f in row[2])

    def load(self, d: manage.TemplateDetail) -> None:
        self.source.rows = [(r.number, r.loaded_on, r.files, r.rows, (r.errors, r.warnings) if r.checks else (-1, -1),
                             status_text(r.status, r.damaged), r.comment, None, r.id) for r in d.runs]
        self._show()

    def _search(self, text: str) -> None:
        self.source.search = text
        self._show()

    def _show(self) -> None:
        if not self.source.rows:
            self.empty.setText("No runs yet. Start a run to load this template's first files.")
            self.stack.setCurrentWidget(self.empty)
        elif not self.source.view([]):
            self.empty.setText(f"No runs match “{self.search.text().strip()}”.")
            self.stack.setCurrentWidget(self.empty)
        else:
            self.stack.setCurrentWidget(self.grid)
        self.model.set_source(self.source)

    def visible_rows(self) -> list[tuple]:
        return self.source.view(self.model.sort_spec)

    def _cell(self, r: int, key: str) -> None:
        if key == "run":
            self.open_row(r)
        elif key == "menu":
            self.row_menu(r).popup(self.grid.viewport().mapToGlobal(self.grid.cell_rect(r, "menu").bottomRight()))

    def open_row(self, r: int) -> None:
        row = self.model.row_values(r)
        if row is not None:
            self.screen.window_.go("run", run_id=row[RUN_ID], template_id=self.screen.template_id)

    def row_menu(self, r: int) -> QMenu:
        """C4-04: Open, Export data, Export issue list, Export left-out rows, Delete (T19)."""
        row = self.model.row_values(r)
        menu = QMenu(self)
        run_id, label = row[RUN_ID], f"R-{row[0]:04d}"
        menu.addAction("Open", partial(self.open_row, r))
        items = [("Export data", "data")]
        if row[4][0] >= 0:                  # not for a run loaded without checks (NCK-12)
            items += [("Export issue list", "issues"), ("Export left-out rows", "left_out")]
        for text, kind in items:
            menu.addAction(text, partial(self.screen.export, kind, run_id, label))
        menu.addAction("Delete", partial(self.screen.delete_run, run_id)).setEnabled(not self.screen.bridge.busy)
        self.menu = menu
        return menu


class TemplateScreen(DataScreen):
    area = "clients"

    def __init__(self, template_id: str, name: str = "", window=None, parent=None, tab: int = RUNS):
        self.template_id = template_id
        self.template_name = name
        self.title = name
        super().__init__(window, parent)
        self.detail: manage.TemplateDetail | None = None
        self.new_run_button = primary("New run", self)
        self.new_run_button.clicked.connect(self.new_run)
        self.actions.addWidget(self.new_run_button)
        self.bridge.guard(self.new_run_button)

        from sankalan.ui.screens.template_columns import ColumnsTab
        from sankalan.ui.screens.template_outputs import OutputsTab
        from sankalan.ui.screens.template_settings import SettingsTab
        self.tabs = CountTabs(TAB_LABELS, self)
        self.content.setSpacing(0)
        self.content.addWidget(self.tabs)
        rule = QWidget(self)
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background: {theme.BORDER};")
        self.content.addWidget(rule)
        self.pages = QStackedWidget(self)
        self.runs_tab = RunsTab(self)
        self.outputs_tab = OutputsTab(self)
        self.columns_tab = ColumnsTab(self)
        self.settings_tab = SettingsTab(self)
        for page in (self.runs_tab, self.outputs_tab, self.columns_tab, self.settings_tab):
            self.pages.addWidget(page)
        self.content.addWidget(self.pages, 1)
        self._tab = tab
        self.tabs.setCurrentIndex(tab)
        self.pages.setCurrentIndex(tab)
        self.tabs.currentChanged.connect(self._tab_changed)

    def crumbs(self) -> list[Crumb]:
        client = self.detail.client_name if self.detail else ""
        cid = self.detail.client_id if self.detail else None
        return [Crumb("Clients", lambda: self.window_.open_area("clients")),
                Crumb(client, (lambda: self.window_.go("client", client_id=cid, name=client)) if cid else None),
                Crumb(self.template_name)]

    @property
    def editing_tabs(self) -> list[TemplateTab]:
        return [self.outputs_tab, self.columns_tab, self.settings_tab]

    @property
    def current_tab(self) -> QWidget:
        return self.pages.currentWidget()

    # ------------------------------------------------------------------------------------------ data
    def shown(self) -> None:
        self.refresh()

    def refresh(self, reload_tabs: bool = True) -> None:
        if self.storage is None:
            return
        self.load("Read template", lambda ctx: manage.template_detail(ctx, self.folder, self.template_id),
                  partial(self._loaded, reload_tabs=reload_tabs))

    def _loaded(self, d: manage.TemplateDetail, reload_tabs: bool = True) -> None:
        self.detail = d
        self.template_name = d.template.name
        self.set_title(d.template.name, summary_line(d))
        self.refresh_crumbs()
        self.tabs.set_count(OUTPUTS, len(d.template.outputs))
        self.runs_tab.load(d)
        for tab in self.editing_tabs:
            if reload_tabs or not tab.dirty:
                tab.set_dirty(False)
                tab.load(d)

    # ------------------------------------------------------------------------------------------ tabs and leaving
    def _tab_changed(self, index: int) -> None:
        old = self.pages.widget(self._tab)
        if getattr(old, "dirty", False):
            self.tabs.blockSignals(True)
            self.tabs.setCurrentIndex(self._tab)            # stay until answered
            self.tabs.blockSignals(False)
            key = ask(self, "Save your changes?", "If you leave without saving, your changes will be lost.",
                      [(STAY, "Stay", None), ("discard", "Discard", None), ("save", "Save", "primary")])
            if key == "discard":
                old.discard()
            elif key == "save":
                old.save(then=lambda: self.select_tab(index))
                return
            else:
                return
        self._show_tab(index)

    def _show_tab(self, index: int) -> None:
        self._tab = index
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(index)
        self.tabs.blockSignals(False)
        self.pages.setCurrentIndex(index)

    def select_tab(self, index: int) -> None:
        """As a click on the tab would (the unsaved-changes prompt included)."""
        if index != self._tab:
            self.tabs.setCurrentIndex(index)

    def leave_guard(self) -> LeaveGuard | None:
        tab = self.current_tab
        if not getattr(tab, "dirty", False):
            return None
        return LeaveGuard.unsaved(lambda: self.save_tab_now(tab), lambda: (tab.discard(), True)[1])

    # ------------------------------------------------------------------------------------------ saving
    def save_tab(self, tab: TemplateTab, then: Callable[[], None] | None = None) -> None:
        problem = tab.check()
        if problem:
            tab.show_error(problem)
            return
        tab.show_error("")
        apply = tab.apply

        def done(_t):
            tab.set_dirty(False)
            self.show_banner(Banner("success", "Template saved."))
            self.refresh(reload_tabs=False)
            if then is not None:
                then()
        self.start("Save template", lambda ctx: update_template(ctx, self.template_id, apply), done,
                   lambda e: tab.show_error(error_text(e)))

    def save_tab_now(self, tab: TemplateTab) -> bool:
        """Save and wait (the leave prompt needs the answer): True once saved."""
        saved: list[bool] = []
        self.save_tab(tab, then=lambda: saved.append(True))
        job = self.bridge.current
        if job is not None:
            job.wait(30)
        self.bridge.poll()
        return bool(saved)

    # ------------------------------------------------------------------------------------------ actions
    def new_run(self) -> bool:
        return self.window_.go("new_run", template_id=self.template_id, name=self.template_name)

    def export(self, kind: str, run_id: str, run_label: str) -> bool:
        """C4-18: the Export dialog opens with the template's export defaults and the name pattern resolved."""
        d = self.detail
        req = ex.prefill(kind, d.template.export, template_id=self.template_id, client=d.client_name,
                         template=d.template.name, run_id=run_id, run_label=run_label)
        return self.window_.go("export", request=req)

    def delete_run(self, run_id: str) -> None:
        def confirmed():
            def done(_r):
                self.show_banner(Banner("success", "Run deleted."))
                self.refresh(reload_tabs=False)
            self.start("Delete run", lambda ctx: manage.delete_run(ctx, self.folder, run_id), done)
        self.load("Read run", lambda ctx: manage.run_delete_summary(ctx, run_id),
                  lambda summary: self.confirm_delete(summary, confirmed))
