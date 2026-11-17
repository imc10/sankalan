"""3.4 Template › Settings (UX-7, TPL-1, IN-4, IN-5, EXP-3, EXP-4; C4-17, C4-18): template name, sheets to read, CSV
delimiter and encoding, and the export defaults that prefill the Export dialog. No header-row, trailer or
number-grouping setting: the header row is found in each sheet, and dates are always DD-MM-YYYY."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QRadioButton, QVBoxLayout, QWidget)

from sankalan import manage
from sankalan.model import export as ex
from sankalan.model.template import (DELIMITERS, ENC_1252, ENC_UTF8, SHEETS_ALL_VISIBLE, SHEETS_BY_NAME,
                                     SHEETS_FIRST_VISIBLE, SourceSettings, Template)
from sankalan.ui import theme
from sankalan.ui.screens.template import TemplateTab
from sankalan.ui.widgets.controls import ChipList, SaveBar, heading, note, panel

NOTE = "Input settings apply from the next run. Export settings prefill the Export dialog."
ROWS_NOTE = "The header row is found automatically in each sheet. Every row with data below it is read."
DETECT = "Detect automatically"
CSV_ENCODINGS = {ENC_UTF8: "UTF-8", ENC_1252: "Windows-1252"}

FolderChooser = Callable[[QWidget, str], str | None]


def choose_folder(parent: QWidget, start: str) -> str | None:
    path = QFileDialog.getExistingDirectory(parent, "Export folder", start)
    return path or None


class SettingsTab(TemplateTab):
    chooser: FolderChooser = staticmethod(choose_folder)

    def __init__(self, screen):
        super().__init__(screen)
        self.template: Template | None = None
        self.client_name = ""
        self.example_run = "R-0001"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(12)
        self.bar = SaveBar("Save changes", NOTE, self, screen.bridge)
        self.bar.save.clicked.connect(lambda: self.save())
        self.bar.discard.clicked.connect(self.discard)
        lay.addWidget(self.bar)
        self.error = note("", self, "error")
        self.error.hide()
        lay.addWidget(self.error)
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ---- template and input
        left = panel(self)
        g = QGridLayout(left)
        g.setContentsMargins(20, 12, 20, 12)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(8)
        g.setColumnMinimumWidth(0, 150)
        g.addWidget(heading("Template and input", left), 0, 0, 1, 2)
        self.name = QLineEdit(left)
        self.name.setAccessibleName("Template name")
        self.name.textEdited.connect(self._edited)
        g.addWidget(self._label("Template name", left), 1, 0)
        g.addWidget(self.name, 1, 1)
        sheets = QWidget(left)
        sl = QVBoxLayout(sheets)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(4)
        self.sheet_group = QButtonGroup(self)
        self.by_name = QRadioButton("By name (one or more)", sheets)
        self.sheet_names = ChipList("Add sheet name", sheets, "Sheet name")
        self.sheet_names.changed.connect(self._edited)
        self.first = QRadioButton("First visible sheet", sheets)
        self.all = QRadioButton("All visible sheets", sheets)
        for i, (b, key) in enumerate(((self.by_name, SHEETS_BY_NAME), (self.first, SHEETS_FIRST_VISIBLE),
                                      (self.all, SHEETS_ALL_VISIBLE))):
            b.setProperty("sheets", key)
            self.sheet_group.addButton(b, i)
        sl.addWidget(self.by_name)
        sl.addWidget(self.sheet_names)
        sl.addWidget(self.first)
        sl.addWidget(self.all)
        self.sheet_group.buttonToggled.connect(lambda _b, on: on and self._sheets_toggled())
        g.addWidget(self._label("Sheets to read", left), 2, 0)
        g.addWidget(sheets, 2, 1)
        g.addWidget(self._label("Rows", left), 3, 0)
        g.addWidget(note(ROWS_NOTE, left, "body"), 3, 1)
        g.addWidget(heading("CSV files only", left, theme.GRID_TEXT_PX), 4, 0, 1, 2)
        self.csv_delimiter = self._combo(left, [(DETECT, None)] + [(v, k) for k, v in DELIMITERS.items()],
                                         "CSV delimiter")
        self.csv_encoding = self._combo(left, [(DETECT, None)] + [(v, k) for k, v in CSV_ENCODINGS.items()],
                                        "CSV encoding")
        g.addWidget(self._label("Delimiter", left), 5, 0)
        g.addWidget(self.csv_delimiter, 5, 1)
        g.addWidget(self._label("Encoding", left), 6, 0)
        g.addWidget(self.csv_encoding, 6, 1)
        g.setRowStretch(7, 1)
        cols.addWidget(left, 1)

        # ---- export defaults
        right = panel(self)
        e = QGridLayout(right)
        e.setContentsMargins(20, 12, 20, 12)
        e.setHorizontalSpacing(16)
        e.setVerticalSpacing(8)
        e.setColumnMinimumWidth(0, 150)
        e.addWidget(heading("Export defaults", right), 0, 0, 1, 2)
        folder_row = QHBoxLayout()
        self.folder = QLineEdit(right)
        self.folder.setReadOnly(True)
        self.folder.setAccessibleName("Export folder")
        folder_row.addWidget(self.folder, 1)
        self.change_folder = QPushButton("Change…", right)
        self.change_folder.setProperty("kind", "secondary")
        self.change_folder.clicked.connect(self.pick_folder)
        folder_row.addWidget(self.change_folder)
        e.addWidget(self._label("Folder", right), 1, 0)
        e.addLayout(folder_row, 1, 1)
        self.pattern = QLineEdit(right)
        self.pattern.setAccessibleName("File name pattern")
        self.pattern.textEdited.connect(self._edited)
        e.addWidget(self._label("File name", right), 2, 0)
        e.addWidget(self.pattern, 2, 1)
        self.example = note("", right)
        e.addWidget(self.example, 3, 1)
        self.delimiter = self._combo(right, [(v, k) for k, v in ex.DELIMITERS.items()], "Export CSV delimiter")
        self.encoding = self._combo(right, [(v, k) for k, v in ex.ENCODINGS.items()], "Export CSV encoding")
        e.addWidget(self._label("CSV delimiter", right), 4, 0)
        e.addWidget(self.delimiter, 4, 1)
        e.addWidget(self._label("CSV encoding", right), 5, 0)
        e.addWidget(self.encoding, 5, 1)
        e.addWidget(self._label("Dates in files", right), 6, 0)
        self.dates = QLabel("DD-MM-YYYY · same as the app", right)
        self.dates.setProperty("kind", "body")
        e.addWidget(self.dates, 6, 1)
        e.setRowStretch(7, 1)
        cols.addWidget(right, 1)
        lay.addLayout(cols, 1)

    def _label(self, text: str, parent) -> QLabel:
        lab = QLabel(text, parent)
        lab.setProperty("kind", "body")
        return lab

    def _combo(self, parent, items, name: str) -> QComboBox:
        cb = QComboBox(parent)
        cb.setAccessibleName(name)
        for label, data in items:
            cb.addItem(label, data)
        cb.currentIndexChanged.connect(self._edited)
        return cb

    @staticmethod
    def _set(cb: QComboBox, data) -> None:
        i = cb.findData(data)
        cb.setCurrentIndex(i if i >= 0 else 0)

    # ------------------------------------------------------------------------------------------ load
    def load(self, detail: manage.TemplateDetail) -> None:
        t = self.template = detail.template
        self.client_name = detail.client_name
        self.example_run = detail.latest.label if detail.latest else "R-0001"
        self._loading = True
        try:
            self.name.setText(t.name)
            {SHEETS_BY_NAME: self.by_name, SHEETS_FIRST_VISIBLE: self.first,
             SHEETS_ALL_VISIBLE: self.all}[t.source.sheets].setChecked(True)
            self.sheet_names.set_values(t.source.sheet_names)
            self.sheet_names.setEnabled(t.source.sheets == SHEETS_BY_NAME)
            self._set(self.csv_delimiter, t.source.csv_delimiter)
            self._set(self.csv_encoding, ENC_UTF8 if t.source.csv_encoding == "utf-8-sig" else t.source.csv_encoding)
            d = ex.ExportDefaults.of(t.export)
            self.folder.setText(d.folder)
            self.pattern.setText(d.pattern)
            self._set(self.delimiter, d.delimiter)
            self._set(self.encoding, ex.ENC_BOM if d.bom else ex.ENC_PLAIN)
        finally:
            self._loading = False
        self._example()

    def _edited(self, *_a) -> None:
        if getattr(self, "_loading", False):
            return
        self.set_dirty(True)
        self._example()

    def _sheets_toggled(self) -> None:
        self.sheet_names.setEnabled(self.by_name.isChecked())
        self._edited()

    def _example(self) -> None:
        first = self.template.outputs[0].name if self.template and self.template.outputs else ex.DATA_NAME
        name = ex.csv_file_name(self.pattern.text() or ex.DEFAULT_PATTERN, Client=self.client_name,
                                Template=self.name.text().strip(), RunID=self.example_run, Output=first)
        self.example.setText(f"Example: {name}")

    def pick_folder(self) -> None:
        path = self.chooser(self, self.folder.text())
        if path:
            self.folder.setText(path)
            self._edited()

    # ------------------------------------------------------------------------------------------ save
    def show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def sheets_value(self) -> str:
        return self.sheet_group.checkedButton().property("sheets")

    def check(self) -> str | None:
        if not self.name.text().strip():
            return "Enter a template name."
        if self.sheets_value() == SHEETS_BY_NAME and not self.sheet_names.values:
            return "Add at least one sheet name, or choose another option."
        if not self.pattern.text().strip():
            return "Enter a file name pattern, e.g. {Client}_{Template}_{RunID}_{Output}."
        return None

    def apply(self, t: Template) -> None:
        sheets = self.sheets_value()
        t.name = self.name.text().strip()
        t.source = SourceSettings(sheets, list(self.sheet_names.values) if sheets == SHEETS_BY_NAME else [],
                                  self.csv_encoding.currentData(), self.csv_delimiter.currentData())
        export = dict(t.export)
        export.update(ex.ExportDefaults(self.folder.text(), self.pattern.text().strip(), self.delimiter.currentData(),
                                        self.encoding.currentData() == ex.ENC_BOM).to_dict())
        t.export = export
