"""1.1 Clients (UX-1, TPL-2): every client with its templates, runs, rows stored and last load; search, sort, New
client, rename, delete; the storage footer, amber when the drive is low (C1-01 to C1-11)."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QStackedWidget, QVBoxLayout, QWidget

from sankalan import formats, manage
from sankalan.ui import theme
from sankalan.ui.screens.common import DataScreen
from sankalan.ui.widgets import icons
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.controls import SearchBox, primary
from sankalan.ui.widgets.paged_grid import (DATETIME, INTEGER, LINK, MENU, GridColumn, ListSource, PagedGrid,
                                            PagedModel)

EMPTY = "No clients yet. Add a client, then set up its first template from a sample file."
NO_MATCH = "No clients match “{}”."

COLUMNS = [
    GridColumn("name", "Client", LINK),
    GridColumn("templates", "Templates", INTEGER, width=110),
    GridColumn("runs", "Runs", INTEGER, width=100),
    GridColumn("rows", "Rows stored", INTEGER, width=160),
    GridColumn("last", "Last loaded on", DATETIME, width=180, muted=True),
    GridColumn("menu", "", MENU, width=56, sortable=False, fmt=lambda _v: "⋯"),
]


def footer_text(s: manage.StorageFigures) -> str:
    return (f"Data stored: {formats.count(s.rows, 'row')} · {formats.gigabytes(s.size_bytes)} · "
            f"{formats.gigabytes(s.free_bytes)} free on {s.drive}")


class ClientsScreen(DataScreen):
    area = "clients"
    title = "Clients"

    def __init__(self, window=None, parent=None):
        super().__init__(window, parent)
        self.overview: manage.ClientsOverview | None = None
        self.search = SearchBox("Search clients", self)
        self.search.textChanged.connect(self._search)
        self.actions.addWidget(self.search)
        self.new_button = primary("New client", self)
        self.new_button.setIcon(icons.icon("plus", theme.WHITE, 16))
        self.new_button.clicked.connect(self.new_client)
        self.actions.addWidget(self.new_button)
        if self.bridge is not None:
            self.bridge.guard(self.new_button)

        self.source = ListSource(COLUMNS, default_sort=[("name", True)],
                                 matches=lambda row, text: text.casefold() in row[0].casefold())
        self.model = PagedModel(self.bridge, COLUMNS, None, parent=self) if self.bridge else None
        self.stack = QStackedWidget(self)
        self.grid = PagedGrid(self.model, self.stack) if self.model is not None else QWidget(self.stack)
        self.stack.addWidget(self.grid)
        self.empty = QWidget(self.stack)
        el = QVBoxLayout(self.empty)
        el.setContentsMargins(0, 48, 0, 0)
        el.setSpacing(16)
        self.empty_text = QLabel(EMPTY, self.empty)
        self.empty_text.setProperty("kind", "body")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.empty_text.setWordWrap(True)
        el.addWidget(self.empty_text)
        self.empty_button = primary("New client", self.empty)
        self.empty_button.clicked.connect(self.new_client)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.empty_button)
        row.addStretch(1)
        el.addLayout(row)
        el.addStretch(1)
        self.stack.addWidget(self.empty)
        self.content.addWidget(self.stack, 1)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        self.footer_icon = QLabel(self)
        foot.addWidget(self.footer_icon)
        self.footer = QLabel("", self)
        self.footer.setObjectName("storage-footer")
        foot.addWidget(self.footer, 1)
        self.content.addLayout(foot)
        if isinstance(self.grid, PagedGrid):
            self.grid.cellClicked.connect(self._cell)
            self.grid.rowActivated.connect(lambda r: self.open_row(r))
        self._footer_colour(False)

    # ------------------------------------------------------------------------------------------ data
    def shown(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self.storage is None:
            return
        self.load("Read clients", lambda ctx: manage.clients_overview(ctx, self.folder), self._loaded)

    def _loaded(self, ov: manage.ClientsOverview) -> None:
        self.overview = ov
        n = len(ov.clients)
        self.set_title("Clients", " · ".join([formats.count(n, "client"), formats.count(ov.templates, "template"),
                                              formats.count(ov.runs, "run")]) if n else "")
        self.source.rows = [(c.name, c.templates, c.runs, c.rows, c.last_loaded, None, c.id) for c in ov.clients]
        self.footer.setText(footer_text(ov.storage))
        self._footer_colour(ov.storage.low)
        self.search.setVisible(bool(n))
        self._show()

    def _footer_colour(self, low: bool) -> None:
        colour = theme.WARNING if low else theme.MUTED
        self.footer.setStyleSheet(f"font-size: {theme.SMALL_PX}px; color: {colour};")
        self.footer.setProperty("low", low)
        self.footer_icon.setPixmap(icons.pixmap("storage", colour, 14, stroke=1.8))

    def _search(self, text: str) -> None:
        self.source.search = text
        self._show()

    def _show(self) -> None:
        rows = self.source.view([])
        if not self.source.rows:
            self.empty_text.setText(EMPTY)
            self.empty_button.show()
            self.stack.setCurrentWidget(self.empty)
        elif not rows:
            self.empty_text.setText(NO_MATCH.format(self.search.text().strip()))
            self.empty_button.hide()
            self.stack.setCurrentWidget(self.empty)
        else:
            self.stack.setCurrentWidget(self.grid)
        if self.model is not None:
            self.model.set_source(self.source)

    def visible_rows(self) -> list[tuple]:
        return self.source.view(self.model.sort_spec if self.model else [])

    def row(self, r: int) -> tuple | None:
        return self.model.row_values(r) if self.model is not None else None

    # ------------------------------------------------------------------------------------------ actions
    def _cell(self, r: int, key: str) -> None:
        if key == "name":
            self.open_row(r)
        elif key == "menu":
            self.row_menu(r).popup(self.grid.viewport().mapToGlobal(self.grid.cell_rect(r, "menu").bottomRight()))

    def open_row(self, r: int) -> None:
        row = self.row(r)
        if row is not None:
            self.window_.go("client", client_id=row[6], name=row[0])

    def row_menu(self, r: int) -> QMenu:
        row = self.row(r)
        menu = QMenu(self)
        menu.addAction("Open", partial(self.open_row, r))
        rename = menu.addAction("Rename", partial(self.rename_client, row[6], row[0]))
        delete = menu.addAction("Delete", partial(self.delete_client, row[6]))
        for a in (rename, delete):
            a.setEnabled(not self.bridge.busy)
        self.menu = menu
        return menu

    def new_client(self) -> None:
        self.ask_name("New client", "Client name", "",
                      lambda name: (lambda ctx: manage.create_client(ctx, name)), "Add client",
                      lambda _cid: self.refresh(), button="Add client")

    def rename_client(self, client_id: str, name: str) -> None:
        self.ask_name("Rename client", "Client name", name,
                      lambda new: (lambda ctx: manage.rename_client(ctx, client_id, new)), "Rename client",
                      lambda _n: self.refresh())

    def delete_client(self, client_id: str) -> None:
        def confirmed():
            def done(_r):
                self.show_banner(Banner("success", "Client deleted."))
                self.refresh()
            self.start("Delete client", lambda ctx: manage.delete_client(ctx, self.folder, client_id), done)
        self.load("Read client", lambda ctx: manage.client_delete_summary(ctx, client_id),
                  lambda summary: self.confirm_delete(summary, confirmed))
