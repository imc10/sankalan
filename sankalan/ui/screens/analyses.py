"""6.1 Analyses (UX-10, ANA-1; A0-01, A0-04, A0-05): every saved analysis with its client, template and the date it
was saved; search by name, client or template; New analysis; per row Open, Rename, Duplicate, Delete."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QStackedWidget, QVBoxLayout, QWidget

from sankalan import analyses, formats
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.screens.common import DataScreen
from sankalan.ui.widgets import icons
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.controls import SearchBox, primary
from sankalan.ui.widgets.paged_grid import DATETIME, LINK, MENU, GridColumn, ListSource, PagedGrid, PagedModel

EMPTY = "No saved analyses yet. Start a new analysis, run it, then save it to rerun it on later runs."
NO_MATCH = "No analyses match “{}”."
SUBTITLE = "{}. Open one to rerun it on the runs you pick."

COLUMNS = [
    GridColumn("name", "Name", LINK),
    GridColumn("client", "Client"),
    GridColumn("template", "Template"),
    GridColumn("saved", "Saved on", DATETIME, width=150, muted=True, right=False,
               fmt=lambda v: formats.date(v.date()) if v is not None else ""),
    GridColumn("menu", "", MENU, width=56, sortable=False, fmt=lambda _v: "⋯"),
]
NAME, CLIENT, TEMPLATE, SAVED, MENU_, ROW = range(6)


class AnalysesScreen(DataScreen):
    area = "analysis"
    title = "Analyses"

    def __init__(self, window=None, parent=None):
        super().__init__(window, parent)
        self.items: list[analyses.AnalysisRow] = []
        self.search = SearchBox("Search name, client or template", self, width=300)
        self.search.textChanged.connect(self._search)
        self.actions.addWidget(self.search)
        self.new_button = primary("New analysis", self)
        self.new_button.setIcon(icons.icon("plus", theme.WHITE, 16))
        self.new_button.clicked.connect(self.new_analysis)
        self.actions.addWidget(self.new_button)

        self.source = ListSource(COLUMNS, default_sort=[("name", True)],
                                 matches=lambda row, text: analyses.matches(row[ROW], text))
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
        self.empty_button = primary("New analysis", self.empty)
        self.empty_button.clicked.connect(self.new_analysis)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.empty_button)
        row.addStretch(1)
        el.addLayout(row)
        el.addStretch(1)
        self.stack.addWidget(self.empty)
        self.content.addWidget(self.stack, 1)
        if isinstance(self.grid, PagedGrid):
            self.grid.cellClicked.connect(self._cell)
            self.grid.rowActivated.connect(lambda r: self.open_row(r))

    # -------------------------------------------------------------------------------------------- data
    def shown(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self.storage is None:
            return
        self.load("Read analyses", analyses.list_analyses, self._loaded)

    def _loaded(self, items: list[analyses.AnalysisRow]) -> None:
        self.items = items
        self.set_title("Analyses", SUBTITLE.format(formats.count(len(items), "saved analysis", "saved analyses"))
                       if items else "")
        self.source.rows = [(a.name, a.client, a.template, a.saved_on, None, a) for a in items]
        self.search.setVisible(bool(items))
        self._show()

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

    def row(self, r: int) -> analyses.AnalysisRow | None:
        values = self.model.row_values(r) if self.model is not None else None
        return values[ROW] if values is not None else None

    # -------------------------------------------------------------------------------------------- actions
    def _cell(self, r: int, key: str) -> None:
        if key == "name":
            self.open_row(r)
        elif key == "menu":
            self.row_menu(r).popup(self.grid.viewport().mapToGlobal(self.grid.cell_rect(r, "menu").bottomRight()))

    def new_analysis(self) -> bool:
        return self.window_.go("analysis")

    def open_row(self, r: int) -> bool:
        a = self.row(r)
        return a is not None and self.window_.go("analysis", analysis_id=a.id)

    def row_menu(self, r: int) -> QMenu:
        a = self.row(r)
        menu = QMenu(self)
        menu.addAction("Open", partial(self.open_row, r))
        rename = menu.addAction("Rename", partial(self.rename, a))
        menu.addAction("Duplicate", partial(self.duplicate, a))
        delete = menu.addAction("Delete", partial(self.delete, a))
        for act in (rename, delete):
            act.setEnabled(not self.bridge.busy)
        self.menu = menu
        return menu

    def rename(self, a: analyses.AnalysisRow) -> None:
        self.ask_name("Rename analysis", "Name", a.name,
                      lambda new: (lambda ctx: analyses.rename(ctx, a.id, new)), "Rename analysis",
                      lambda _n: self.refresh())

    def duplicate(self, a: analyses.AnalysisRow) -> None:
        """ANA-1: the settings in a new, editable, unsaved analysis."""
        self.load("Read analysis", lambda ctx: analyses.open_saved(ctx, a.id),
                  lambda saved: self.window_.go("analysis", template_id=saved.data.template.id,
                                                definition=saved.definition))

    def delete(self, a: analyses.AnalysisRow) -> None:
        """A0-05: a plain confirmation; runs and data are not affected."""
        key = ask(self, f"Delete “{a.name}”?", "The saved analysis is removed. Runs and their data don't change.",
                  [("cancel", "Cancel", None), ("delete", "Delete", "destructive")])
        if key != "delete":
            return

        def done(_r):
            self.show_banner(Banner("success", f"“{a.name}” deleted."))
            self.refresh()
        self.start("Delete analysis", lambda ctx: analyses.delete(ctx, a.id), done)
