"""1.2 Client (UX-2, TPL-2, TPL-4): the client's templates with columns, default outputs, runs, rows stored, last
load and last change; New template, New run on each row (after a confirmation), rename, duplicate, delete
(C2-01 to C2-08)."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QStackedWidget, QVBoxLayout, QWidget

from sankalan import formats, manage
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.screens.common import DataScreen
from sankalan.ui.widgets import icons
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.breadcrumb import Crumb
from sankalan.ui.widgets.controls import SearchBox, primary
from sankalan.ui.widgets.paged_grid import (ACTION, DATE, DATETIME, INTEGER, LINK, MENU, GridColumn, ListSource,
                                            PagedGrid, PagedModel)

EMPTY = "No templates for {} yet. A template is set up from one sample file."
NO_MATCH = "No templates match “{}”."

COLUMNS = [
    GridColumn("name", "Template", LINK),
    GridColumn("columns", "Columns", INTEGER, width=84),
    GridColumn("outputs", "Default outputs", INTEGER, width=124),
    GridColumn("runs", "Runs", INTEGER, width=72),
    GridColumn("rows", "Rows stored", INTEGER, width=144),
    GridColumn("last", "Last loaded on", DATETIME, width=156, muted=True),
    GridColumn("modified", "Modified", DATE, width=108, muted=True,
               fmt=lambda v: formats.date(v.date() if v is not None else None)),
    GridColumn("new_run", "", ACTION, width=104, sortable=False, fmt=lambda _v: "New run"),
    GridColumn("menu", "", MENU, width=44, sortable=False, fmt=lambda _v: "⋯"),
]
ID = len(COLUMNS)           # the template ID follows the shown values in each row


class ClientScreen(DataScreen):
    area = "clients"

    def __init__(self, client_id: str, name: str = "", window=None, parent=None):
        self.client_id = client_id
        self.client_name = name
        self.title = name
        super().__init__(window, parent)
        self.detail: manage.ClientDetail | None = None
        self.search = SearchBox("Search templates", self)
        self.search.textChanged.connect(self._search)
        self.actions.addWidget(self.search)
        self.new_button = primary("New template", self)
        self.new_button.setIcon(icons.icon("plus", theme.WHITE, 16))
        self.new_button.clicked.connect(self.new_template)
        self.actions.addWidget(self.new_button)

        self.source = ListSource(COLUMNS, default_sort=[("name", True)],
                                 matches=lambda row, text: text.casefold() in row[0].casefold())
        self.model = PagedModel(self.bridge, COLUMNS, None, parent=self)
        self.stack = QStackedWidget(self)
        self.grid = PagedGrid(self.model, self.stack)
        self.grid.cellClicked.connect(self._cell)
        self.grid.rowActivated.connect(self.open_row)
        self.stack.addWidget(self.grid)
        self.empty = QWidget(self.stack)
        el = QVBoxLayout(self.empty)
        el.setContentsMargins(0, 48, 0, 0)
        el.setSpacing(16)
        self.empty_text = QLabel("", self.empty)
        self.empty_text.setProperty("kind", "body")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.empty_text.setWordWrap(True)
        el.addWidget(self.empty_text)
        self.empty_button = primary("New template", self.empty)
        self.empty_button.clicked.connect(self.new_template)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.empty_button)
        row.addStretch(1)
        el.addLayout(row)
        el.addStretch(1)
        self.stack.addWidget(self.empty)
        self.content.addWidget(self.stack, 1)

    def crumbs(self) -> list[Crumb]:
        return [Crumb("Clients", lambda: self.window_.open_area("clients")), Crumb(self.client_name)]

    # ------------------------------------------------------------------------------------------ data
    def shown(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self.storage is None:
            return
        self.load("Read client", lambda ctx: manage.client_detail(ctx, self.client_id), self._loaded)

    def _loaded(self, detail: manage.ClientDetail) -> None:
        self.detail = detail
        self.client_name = detail.name
        n = len(detail.templates)
        self.set_title(detail.name, " · ".join([formats.count(n, "template"), formats.count(detail.runs, "run"),
                                                formats.count(detail.rows, "row")]) if n else "")
        self.refresh_crumbs()
        self.source.rows = [(t.name, t.columns, t.outputs, t.runs, t.rows, t.last_loaded, t.modified, None, None,
                             t.id) for t in detail.templates]
        self.search.setVisible(bool(n))
        self._show()

    def _search(self, text: str) -> None:
        self.source.search = text
        self._show()

    def _show(self) -> None:
        if not self.source.rows:
            self.empty_text.setText(EMPTY.format(self.client_name))
            self.empty_button.show()
            self.stack.setCurrentWidget(self.empty)
        elif not self.source.view([]):
            self.empty_text.setText(NO_MATCH.format(self.search.text().strip()))
            self.empty_button.hide()
            self.stack.setCurrentWidget(self.empty)
        else:
            self.stack.setCurrentWidget(self.grid)
        self.model.set_source(self.source)

    def visible_rows(self) -> list[tuple]:
        return self.source.view(self.model.sort_spec)

    def row(self, r: int):
        return self.model.row_values(r)

    # ------------------------------------------------------------------------------------------ actions
    def _cell(self, r: int, key: str) -> None:
        if key == "name":
            self.open_row(r)
        elif key == "new_run":
            self.new_run(r)
        elif key == "menu":
            self.row_menu(r).popup(self.grid.viewport().mapToGlobal(self.grid.cell_rect(r, "menu").bottomRight()))

    def open_row(self, r: int) -> None:
        row = self.row(r)
        if row is not None:
            self.window_.go("template", template_id=row[ID], name=row[0])

    def new_template(self) -> None:
        self.window_.go("new_template", client_id=self.client_id)

    def new_run(self, r: int) -> bool:
        """C2-04: a confirmation first; Cancel stays here."""
        row = self.row(r)
        if row is None:
            return False
        if self.bridge.busy:
            self.show_banner(Banner("warning", "Another operation is running. Start the run when it has finished."))
            return False
        key = ask(self, f"Start a new run on {row[0]}?",
                  "You'll add this period's files next. Nothing is stored until you commit the run.",
                  [("cancel", "Cancel", None), ("start", "Start run", "primary")])
        if key != "start":
            return False
        return self.window_.go("new_run", template_id=row[ID], name=row[0])

    def row_menu(self, r: int) -> QMenu:
        """C2-02: Rename, Duplicate, Delete only."""
        row = self.row(r)
        menu = QMenu(self)
        tid, name = row[ID], row[0]
        for label, fn in (("Rename", partial(self.rename_template, tid, name)),
                          ("Duplicate", partial(self.duplicate_template, tid)),
                          ("Delete", partial(self.delete_template, tid))):
            menu.addAction(label, fn).setEnabled(not self.bridge.busy)
        self.menu = menu
        return menu

    def rename_template(self, template_id: str, name: str) -> None:
        self.ask_name("Rename template", "Template name", name,
                      lambda new: (lambda ctx: manage.rename_template(ctx, template_id, new)), "Rename template",
                      lambda _n: self.refresh())

    def duplicate_template(self, template_id: str) -> None:
        def done(_new_id):
            self.show_banner(Banner("success", "Template duplicated. The copy has no runs."))
            self.refresh()
        self.start("Duplicate template", lambda ctx: manage.duplicate_template(ctx, template_id), done)

    def delete_template(self, template_id: str) -> None:
        def confirmed():
            def done(_r):
                self.show_banner(Banner("success", "Template deleted."))
                self.refresh()
            self.start("Delete template", lambda ctx: manage.delete_template(ctx, self.folder, template_id), done)
        self.load("Read template", lambda ctx: manage.template_delete_summary(ctx, template_id),
                  lambda summary: self.confirm_delete(summary, confirmed))
