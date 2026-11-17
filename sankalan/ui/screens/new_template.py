"""2.1–2.6 New template wizard (UX-3, F1, TPL-3; C3-01 to C3-22).

Six steps from one sample file: Sample file · Sheets · Columns · Rules · Default outputs · Review. The sample's
first 100,000 rows are read into a staging folder (``sankalan.newtemplate``); nothing is loaded and nothing is
written under ``t\\`` until Save. Back keeps every entry, and the file is read again only when it or the sheets
to read changed (C3-22). Cancel, or leaving the wizard any other way, asks "Discard this template?" (C3-01).
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QRadioButton, QSpinBox, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from sankalan import formats
from sankalan import newtemplate as nt
from sankalan.ingest import sample as smp
from sankalan.ingest import values
from sankalan.ingest.detect import norm
from sankalan.model.definition import Definition
from sankalan.model.rule import ERROR, Rule
from sankalan.model.template import (DATE, DATE_FORMATS, DECIMALS_DEFAULT, DECIMALS_MAX, DELIMITERS,
                                     ENCODING_LABELS, ENC_UTF8_BOM, NUMBER, SHEETS_ALL_VISIBLE, SHEETS_BY_NAME,
                                     SHEETS_FIRST_VISIBLE, TEXT, TYPES, Column, SourceSettings, Template,
                                     next_column_id)
from sankalan.ui import theme
from sankalan.ui.dialogs.base import ask
from sankalan.ui.screens.base import STAY, LeaveGuard
from sankalan.ui.screens.common import DataScreen, error_text
from sankalan.ui.screens.new_template_rules import OutputsStep, RulesStep, rules_summary
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.breadcrumb import Crumb
from sankalan.ui.widgets.controls import heading, icon_button, note, panel, primary
from sankalan.ui.widgets.progress import ProgressPanel
from sankalan.ui.widgets.stepbar import StepBar

SAMPLE, SHEETS, COLUMNS, RULES, OUTPUTS, REVIEW = range(6)
FILE_FILTER = "Excel and CSV files (*.xlsx *.xlsm *.csv)"       # IN-3, C3-04
WORKERS: int | None = None          # reader workers for the sample (tests set 0: read in the Job's thread)
DISCARD_TITLE = "Discard this template?"
DISCARD_TEXT = "Your entries will be lost. Nothing has been saved."
SHEET_OPTIONS = [(SHEETS_BY_NAME, "By name (one or more)"), (SHEETS_FIRST_VISIBLE, "First visible sheet"),
                 (SHEETS_ALL_VISIBLE, "All visible sheets")]
EXCEL_DATES = "Excel dates"


def and_list(names: list[str]) -> str:
    """"Sales", "Sales and Sales Returns", "A, B and C"."""
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def sheets_text(source: SourceSettings, info: smp.SampleInfo | None = None) -> str:
    """The Review line: "By name: Sales", "First visible sheet", "All visible sheets"."""
    if info is not None and info.is_csv:
        enc = ENCODING_LABELS.get(info.encoding, info.encoding)
        return f"CSV file · {enc} · {DELIMITERS.get(info.delimiter, info.delimiter)}"
    if source.sheets == SHEETS_BY_NAME:
        return "By name: " + ", ".join(source.sheet_names)
    return dict(SHEET_OPTIONS)[source.sheets]


def sample_text(raw: str, col: Column) -> str:
    """A sample value as the column will read it: numbers grouped, dates DD-MM-YYYY (UI-7); else as typed."""
    if col.type == NUMBER:
        v, ok = values.to_number(raw, col.decimals or 0)
        if ok and v is not None:
            return formats.number(v, col.decimals)
    elif col.type == DATE:
        v, ok = values.to_date(raw, col.date_format)
        if ok and v is not None:
            return formats.date(v)
    return raw


def columns_summary(cols: list[Column], left_out: list[str]) -> str:
    """"9 · 5 Text, 1 Date, 3 Number (Remarks left out)" (canvas 2.6)."""
    parts = [f"{sum(1 for c in cols if c.type == t)} {t}" for t in (TEXT, DATE, NUMBER)
             if any(c.type == t for c in cols)]
    text = f"{len(cols)} · {', '.join(parts)}"
    if left_out:
        text += f" ({and_list(left_out)} left out)"
    return text


# ---------------------------------------------------------------------------------------------- step 1
class SampleStep(QWidget):
    def __init__(self, wizard: "NewTemplateScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)
        box = QWidget(self)
        box.setMaximumWidth(640)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)
        bl.addWidget(heading("Template name", box, theme.GRID_TEXT_PX))
        self.name = QLineEdit(box)
        self.name.setAccessibleName("Template name")
        self.name.setMaxLength(100)
        bl.addWidget(self.name)
        self.name_note = note("", box)
        bl.addWidget(self.name_note)
        self.name_error = note("", box, "error")
        self.name_error.hide()
        bl.addWidget(self.name_error)
        bl.addSpacing(14)
        bl.addWidget(heading("Sample file", box, theme.GRID_TEXT_PX))
        row = QHBoxLayout()
        row.setSpacing(12)
        file_box = panel(box)
        fl = QVBoxLayout(file_box)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(2)
        self.file_name = QLabel("No file chosen", file_box)
        self.file_name.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; font-weight: 500;")
        self.file_meta = note("Drag a file here, or choose one.", file_box)
        fl.addWidget(self.file_name)
        fl.addWidget(self.file_meta)
        row.addWidget(file_box, 1)
        self.choose = primary("Choose…", box, "secondary")
        self.choose.clicked.connect(self.browse)
        wizard.bridge.guard(self.choose)
        row.addWidget(self.choose)
        bl.addLayout(row)
        bl.addWidget(note(".xlsx, .xlsm or .csv. Use a file that looks like the ones you'll load every month.", box))
        self.file_error = note("", box, "error")
        self.file_error.hide()
        bl.addWidget(self.file_error)
        bl.addSpacing(14)
        self.rows = heading("", box, theme.GRID_TEXT_PX)
        self.rows.hide()
        bl.addWidget(self.rows)
        self.rows_note = note("The next steps preview on these rows. Nothing is loaded into the database while you "
                              "set up the template.", box)
        self.rows_note.hide()
        bl.addWidget(self.rows_note)
        lay.addWidget(box)
        lay.addStretch(1)
        self.setAcceptDrops(True)

    def browse(self) -> None:
        path, _f = QFileDialog.getOpenFileName(self, "Choose a sample file", "", FILE_FILTER)
        if path:
            self.wizard.pick(path)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.wizard.pick(urls[0])
            event.acceptProposedAction()

    def show_file(self, info: smp.SampleInfo | None, staged: nt.StagedSample | None) -> None:
        if info is None:
            self.file_name.setText("No file chosen")
            self.file_meta.setText("Drag a file here, or choose one.")
            self.choose.setText("Choose…")
            self.rows.hide()
            self.rows_note.hide()
            return
        self.file_name.setText(info.file_name)
        meta = f"{Path(info.path).parent} · {formats.size(info.size)}"
        if not info.is_csv:
            meta += f" · {formats.count(len(info.sheets), 'sheet')}"
        self.file_meta.setText(meta)
        self.choose.setText("Change…")
        if staged is not None:
            self.rows.setText(f"Read {formats.count(staged.rows, 'row')} for previews")
            self.rows.show()
            self.rows_note.show()

    def set_file_error(self, text: str) -> None:
        self.file_error.setText(text)
        self.file_error.setVisible(bool(text))

    def set_name_error(self, text: str) -> None:
        self.name_error.setText(text)
        self.name_error.setVisible(bool(text))


# ---------------------------------------------------------------------------------------------- step 2
class SheetsStep(QWidget):
    def __init__(self, wizard: "NewTemplateScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        self.current = ""
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        left = panel(self)
        left.setFixedWidth(330)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 12, 16, 12)
        ll.setSpacing(8)
        self.excel_box = QWidget(left)
        el = QVBoxLayout(self.excel_box)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(8)
        el.addWidget(heading("Sheets to read in every file", self.excel_box, theme.GRID_TEXT_PX))
        self.group = QButtonGroup(self)
        self.radios: dict[str, QRadioButton] = {}
        for key, label in SHEET_OPTIONS:
            rb = QRadioButton(label, self.excel_box)
            self.group.addButton(rb)
            self.radios[key] = rb
            el.addWidget(rb)
            rb.toggled.connect(lambda on, k=key: on and self._mode(k))
        self.sheet_list = QListWidget(self.excel_box)
        self.sheet_list.setAccessibleName("Sheets")
        self.sheet_list.itemChanged.connect(self._ticked)
        self.sheet_list.currentItemChanged.connect(lambda cur, _prev: cur is not None and self.show_sheet(
            cur.data(Qt.ItemDataRole.UserRole)))
        el.addWidget(self.sheet_list, 1)
        ll.addWidget(self.excel_box, 1)
        self.csv_box = QWidget(left)
        cl = QFormLayout(self.csv_box)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setVerticalSpacing(10)
        self.encoding = QComboBox(self.csv_box)
        self.encoding.setAccessibleName("Encoding")
        for k, label in ENCODING_LABELS.items():
            if k != ENC_UTF8_BOM:
                self.encoding.addItem(label, k)
        self.delimiter = QComboBox(self.csv_box)
        self.delimiter.setAccessibleName("Delimiter")
        for k, label in DELIMITERS.items():
            self.delimiter.addItem(label, k)
        cl.addRow(heading("CSV reading", self.csv_box, theme.GRID_TEXT_PX))
        cl.addRow("Encoding", self.encoding)
        cl.addRow("Delimiter", self.delimiter)
        self.csv_note = note("", self.csv_box)
        cl.addRow(self.csv_note)
        self.encoding.activated.connect(lambda _i: self.wizard.reread_csv(self.encoding.currentData(),
                                                                          self.delimiter.currentData()))
        self.delimiter.activated.connect(lambda _i: self.wizard.reread_csv(self.encoding.currentData(),
                                                                           self.delimiter.currentData()))
        ll.addWidget(self.csv_box)
        ll.addWidget(note("The header row is found automatically in each sheet, and every row with data below it "
                          "is read.", left))
        lay.addWidget(left)

        right = panel(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(8)
        head = QHBoxLayout()
        self.preview_title = heading("", right, theme.GRID_TEXT_PX)
        head.addWidget(self.preview_title)
        head.addStretch(1)
        self.header_found = note("", right)
        head.addWidget(self.header_found)
        rl.addLayout(head)
        self.preview = QTableWidget(right)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.preview.verticalHeader().hide()
        self.preview.horizontalHeader().hide()
        self.preview.verticalHeader().setDefaultSectionSize(32)
        self.preview.setShowGrid(False)
        rl.addWidget(self.preview, 1)
        lay.addWidget(right, 1)

    def load(self) -> None:
        info, source = self.wizard.info, self.wizard.source
        csv = info.is_csv
        self.excel_box.setVisible(not csv)
        self.csv_box.setVisible(csv)
        if csv:
            with QSignalBlocker(self.encoding), QSignalBlocker(self.delimiter):
                enc = info.encoding if info.encoding != ENC_UTF8_BOM else "utf-8"
                self.encoding.setCurrentIndex(self.encoding.findData(enc))
                self.delimiter.setCurrentIndex(self.delimiter.findData(info.delimiter))
            self.csv_note.setText(f"Detected: {ENCODING_LABELS[info.detected_encoding]}, "
                                  f"{DELIMITERS[info.detected_delimiter].lower()}. Change them if the preview looks "
                                  "wrong.")
            self.show_sheet("")
        else:
            with QSignalBlocker(self.group):
                for rb in self.radios.values():
                    rb.blockSignals(True)
                self.radios[source.sheets].setChecked(True)
                for rb in self.radios.values():
                    rb.blockSignals(False)
            self._fill_sheets()
            names = nt.sheets_to_read(info, source)
            self.show_sheet(names[0] if names else info.visible_sheets[0].name)
        self.wizard.update_footer()

    def _fill_sheets(self) -> None:
        info, source = self.wizard.info, self.wizard.source
        reading = set(nt.sheets_to_read(info, source))
        by_name = source.sheets == SHEETS_BY_NAME
        with QSignalBlocker(self.sheet_list):
            self.sheet_list.clear()
            for s in info.sheets:
                if s.visible:
                    rows = (f"{formats.count(s.rows_approx, 'row')}" if s.rows_approx is not None else
                            "Header not found" if s.header_row is None else "")
                    item = QListWidgetItem(f"{s.name}    {rows}".rstrip())
                    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                    if by_name:
                        flags |= Qt.ItemFlag.ItemIsUserCheckable
                    item.setFlags(flags)
                    item.setCheckState(Qt.CheckState.Checked if s.name in reading else Qt.CheckState.Unchecked)
                else:
                    item = QListWidgetItem(f"{s.name}    Hidden, skipped")
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    item.setForeground(QColor(theme.DISABLED_TEXT))
                item.setData(Qt.ItemDataRole.UserRole, s.name)
                self.sheet_list.addItem(item)

    def sheet_rows(self) -> list[tuple[str, bool, bool, bool]]:
        """(sheet, visible, ticked, tickable) per list row, for tests."""
        out = []
        for i in range(self.sheet_list.count()):
            it = self.sheet_list.item(i)
            out.append((it.data(Qt.ItemDataRole.UserRole), bool(it.flags() & Qt.ItemFlag.ItemIsEnabled),
                        it.checkState() == Qt.CheckState.Checked,
                        bool(it.flags() & Qt.ItemFlag.ItemIsUserCheckable)))
        return out

    def _mode(self, key: str) -> None:
        info, src = self.wizard.info, self.wizard.source
        names = list(src.sheet_names) or [info.visible_sheets[0].name]
        self.wizard.source = SourceSettings(key, names if key == SHEETS_BY_NAME else [], src.csv_encoding,
                                            src.csv_delimiter)
        self._fill_sheets()
        self.wizard.update_footer()

    def set_mode(self, key: str) -> None:
        self.radios[key].setChecked(True)

    def tick(self, name: str, on: bool) -> None:
        for i in range(self.sheet_list.count()):
            it = self.sheet_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == name:
                it.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def _ticked(self, item: QListWidgetItem) -> None:
        src = self.wizard.source
        if src.sheets != SHEETS_BY_NAME:
            return
        names = [self.sheet_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.sheet_list.count())
                 if self.sheet_list.item(i).checkState() == Qt.CheckState.Checked]
        # SourceSettings needs a name for "by name"; an empty choice is kept as a list and refused on Next
        self.wizard.source = copy.copy(src)
        self.wizard.source.sheet_names = names
        self.wizard.update_footer()

    def show_sheet(self, name: str) -> None:
        info = self.wizard.info
        self.current = name
        sheet = info.sheet(name)
        self.preview_title.setText(f"{info.file_name if info.is_csv else name} · first rows")
        self.header_found.setText(f"Header found in row {sheet.header_row}" if sheet.header_row else
                                  "Header not found")
        rows = sheet.preview
        width = max((len(v) for _n, v in rows), default=0)
        self.preview.setRowCount(len(rows))
        self.preview.setColumnCount(width + 1)
        medium = QFont(self.preview.font())
        medium.setWeight(QFont.Weight.Medium)
        for r, (n, vals) in enumerate(rows):
            head = n == sheet.header_row
            title = sheet.header_row is not None and n < sheet.header_row
            for c, text in enumerate([str(n)] + list(vals) + [""] * (width - len(vals))):
                item = QTableWidgetItem(text)
                if head:
                    item.setBackground(QColor(theme.TINT))
                    item.setForeground(QColor(theme.TEAL_DARK))
                    item.setFont(medium)
                elif title or c == 0:
                    item.setForeground(QColor(theme.DISABLED_TEXT))
                self.preview.setItem(r, c, item)
        self.preview.resizeColumnsToContents()

    def preview_rows(self) -> list[list[str]]:
        return [[self.preview.item(r, c).text() for c in range(self.preview.columnCount())]
                for r in range(self.preview.rowCount())]

    def header_row_shown(self) -> int | None:
        """The preview row marked as the header (its row number), for tests."""
        for r in range(self.preview.rowCount()):
            if self.preview.item(r, 0).background().color() == QColor(theme.TINT):
                return int(self.preview.item(r, 0).text())
        return None


# ---------------------------------------------------------------------------------------------- step 3
COLUMN_HEADERS = ["Include", "Header in the file", "Column name", "Type", "Decimals", "Date format", "Detected",
                  "Sample values", ""]
INCLUDE, HEADER, NAME, TYPE, DECIMALS, DATE_FORMAT, DETECTED, SAMPLES, MOVE = range(9)


class ColumnsStep(QWidget):
    def __init__(self, wizard: "NewTemplateScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.table = QTableWidget(0, len(COLUMN_HEADERS), self)
        self.table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(theme.ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        for i, w in ((INCLUDE, 64), (HEADER, 170), (NAME, 190), (TYPE, 104), (DECIMALS, 76), (DATE_FORMAT, 140),
                     (DETECTED, 190), (MOVE, 64)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            hh.resizeSection(i, w)
        hh.setSectionResizeMode(SAMPLES, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        self.error = note("", self, "error")
        self.error.hide()
        lay.addWidget(self.error)

    @property
    def drafts(self) -> list[nt.DraftColumn]:
        return self.wizard.drafts

    def load(self) -> None:
        self.table.setRowCount(len(self.drafts))
        staged = self.wizard.staged
        for r, d in enumerate(self.drafts):
            c = d.column
            inc = QCheckBox()
            inc.setAccessibleName(f"Include {d.header}")
            inc.setChecked(d.include)
            inc.toggled.connect(lambda on, dc=d: self._include(dc, on))
            self.table.setCellWidget(r, INCLUDE, self._centre(inc))
            self.table.setItem(r, HEADER, QTableWidgetItem(d.header))
            name = QLineEdit(c.name)
            name.setAccessibleName(f"Column name for {d.header}")
            name.textEdited.connect(lambda t, dc=d: self._rename(dc, t))
            self.table.setCellWidget(r, NAME, name)
            typ = QComboBox()
            typ.setAccessibleName(f"Type of {d.header}")
            for t in TYPES:
                typ.addItem(t, t)
            typ.setCurrentIndex(TYPES.index(c.type))
            typ.currentIndexChanged.connect(lambda _i, dc=d, cb=typ: self._retype(dc, cb.currentData()))
            self.table.setCellWidget(r, TYPE, typ)
            if c.type == NUMBER:
                dec = QSpinBox()
                dec.setRange(0, DECIMALS_MAX)
                dec.setValue(c.decimals if c.decimals is not None else DECIMALS_DEFAULT)
                dec.setAccessibleName(f"Decimals for {d.header}")
                dec.valueChanged.connect(lambda v, dc=d: self._decimals(dc, v))
                self.table.setCellWidget(r, DECIMALS, dec)
            else:
                self.table.removeCellWidget(r, DECIMALS)
                self.table.setItem(r, DECIMALS, QTableWidgetItem(""))
            if c.type == DATE:
                fmt = QComboBox()
                fmt.setAccessibleName(f"Date format for {d.header}")
                excel = d.detected.type == DATE and d.detected.date_format is None
                if excel:                       # C3-11: Excel dates need no format
                    fmt.addItem(EXCEL_DATES, None)
                    fmt.setEnabled(False)
                    fmt.setToolTip("Excel dates are read as dates; no format is needed.")
                else:
                    for f in DATE_FORMATS:
                        fmt.addItem(f, f)
                    if c.date_format is None:
                        c.date_format = DATE_FORMATS[0]
                    fmt.setCurrentIndex(fmt.findData(c.date_format))
                fmt.currentIndexChanged.connect(lambda _i, dc=d, cb=fmt: self._date_format(dc, cb.currentData()))
                self.table.setCellWidget(r, DATE_FORMAT, fmt)
            else:
                self.table.removeCellWidget(r, DATE_FORMAT)
                self.table.setItem(r, DATE_FORMAT, QTableWidgetItem(""))
            det = QTableWidgetItem(d.detected.note)
            det.setForeground(QColor(theme.MUTED if d.detected.exact else theme.OVERRIDE_TEXT))
            self.table.setItem(r, DETECTED, det)
            raw = staged.columns[d.source].profile.samples if staged else []
            self.table.setItem(r, SAMPLES, QTableWidgetItem(", ".join(sample_text(v, c) for v in raw)))
            cell = QWidget()
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(0, 0, 4, 0)
            cl.setSpacing(0)
            up = icon_button("up", f"Move {c.name} up", cell, 26)
            down = icon_button("down", f"Move {c.name} down", cell, 26)
            up.setEnabled(r > 0)
            down.setEnabled(r < len(self.drafts) - 1)
            up.clicked.connect(lambda _c=False, i=r: self.move(i, -1))
            down.clicked.connect(lambda _c=False, i=r: self.move(i, 1))
            cl.addWidget(up)
            cl.addWidget(down)
            self.table.setCellWidget(r, MOVE, cell)
            fg = QColor(theme.TEXT if d.include else theme.DISABLED_TEXT)
            for i in (HEADER, SAMPLES):
                self.table.item(r, i).setForeground(fg)
        self.wizard.update_footer()

    @staticmethod
    def _centre(w: QWidget) -> QWidget:
        box = QWidget()
        bl = QHBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(w, 0, Qt.AlignmentFlag.AlignCenter)
        return box

    def widget(self, row: int, col: int):
        w = self.table.cellWidget(row, col)
        if col == INCLUDE and w is not None:
            return w.findChild(QCheckBox)
        return w

    def rows(self) -> list[list[str]]:
        """What each row shows, for tests: header, name, type, decimals, date format, detected, samples."""
        out = []
        for r in range(self.table.rowCount()):
            dec, fmt = self.table.cellWidget(r, DECIMALS), self.table.cellWidget(r, DATE_FORMAT)
            out.append([self.table.item(r, HEADER).text(), self.table.cellWidget(r, NAME).text(),
                        self.table.cellWidget(r, TYPE).currentText(), str(dec.value()) if dec else "",
                        fmt.currentText() if fmt else "", self.table.item(r, DETECTED).text(),
                        self.table.item(r, SAMPLES).text()])
        return out

    # ------------------------------------------------------------------------------------------ edits
    def _include(self, d: nt.DraftColumn, on: bool) -> None:
        d.include = on
        r = self.drafts.index(d)
        fg = QColor(theme.TEXT if on else theme.DISABLED_TEXT)
        for i in (HEADER, SAMPLES):
            self.table.item(r, i).setForeground(fg)
        self.wizard.update_footer()

    def _rename(self, d: nt.DraftColumn, text: str) -> None:
        d.column.name = text

    def _retype(self, d: nt.DraftColumn, typ: str) -> None:
        c = d.column
        if typ == c.type:
            return
        c.type = typ
        c.decimals = DECIMALS_DEFAULT if typ == NUMBER else None
        c.date_format = (d.detected.date_format if d.detected.type == DATE else DATE_FORMATS[0]) \
            if typ == DATE else None
        c.totals_check = False
        self.load()

    def _decimals(self, d: nt.DraftColumn, v: int) -> None:
        if d.column.type == NUMBER and 0 <= v <= DECIMALS_MAX:
            d.column.decimals = v

    def _date_format(self, d: nt.DraftColumn, fmt) -> None:
        if d.column.type == DATE:
            d.column.date_format = fmt

    def move(self, index: int, step: int) -> None:
        j = index + step
        if 0 <= j < len(self.drafts):
            self.drafts[index], self.drafts[j] = self.drafts[j], self.drafts[index]
            self.load()

    def show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))


# ---------------------------------------------------------------------------------------------- step 6
class ReviewStep(QWidget):
    def __init__(self, wizard: "NewTemplateScreen"):
        super().__init__(wizard)
        self.wizard = wizard
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        left = panel(self)
        left.setMaximumWidth(720)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 16, 20, 16)
        ll.setSpacing(12)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(10)
        self.values: dict[str, QLabel] = {}
        for i, key in enumerate(("Client", "Template name", "Sample file", "Sheets to read", "Columns", "Rules",
                                 "Default outputs")):
            k = QLabel(key, left)
            k.setProperty("kind", "subtitle")
            v = QLabel("", left)
            v.setWordWrap(True)
            v.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px;")
            self.grid.addWidget(k, i, 0, Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(v, i, 1)
            self.values[key] = v
        self.grid.setColumnStretch(1, 1)
        ll.addLayout(self.grid)
        ll.addWidget(note("Column types become fixed after the first run is committed. Everything else can be changed "
                          "later on the template's tabs.", left))
        ll.addStretch(1)
        lay.addWidget(left, 3)
        right = panel(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 3, right)
        self.table.setHorizontalHeaderLabels(["Column", "Type", "Rules"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.horizontalHeader().setFixedHeight(theme.ROW_HEIGHT)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("QTableWidget { border: 0; }")
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, w in ((1, 90), (2, 64)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            hh.resizeSection(i, w)
        rl.addWidget(self.table)
        lay.addWidget(right, 2)

    def load(self) -> None:
        w = self.wizard
        t = w.draft_template()
        cols = t.active_columns
        left_out = [d.column.name for d in w.drafts if not d.include]
        outs = t.outputs
        texts = {"Client": w.client_name, "Template name": t.name, "Sample file": w.info.file_name,
                 "Sheets to read": sheets_text(t.source, w.info),
                 "Columns": columns_summary(cols, left_out), "Rules": rules_summary(t.rules),
                 "Default outputs": (f"{len(outs)} · {', '.join(o.name for o in outs)}" if outs else "0")}
        for k, v in texts.items():
            self.values[k].setText(v)
        self.table.setRowCount(len(cols))
        for r, c in enumerate(cols):
            n = sum(1 for rule in t.rules if rule.column_id == c.id)
            for i, text in enumerate((c.name, c.type, str(n))):
                item = QTableWidgetItem(text)
                if i == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, i, item)

    def summary(self) -> dict[str, str]:
        return {k: v.text() for k, v in self.values.items()}

    def column_rows(self) -> list[tuple[str, str, str]]:
        return [tuple(self.table.item(r, i).text() for i in range(3)) for r in range(self.table.rowCount())]


# ---------------------------------------------------------------------------------------------- the wizard
class NewTemplateScreen(DataScreen):
    area = "clients"
    title = "New template"

    def __init__(self, client_id: str, client_name: str = "", window=None, parent=None):
        self.client_id = client_id
        self.client_name = client_name
        super().__init__(window, parent)
        self.step = SAMPLE
        self.info: smp.SampleInfo | None = None
        self.source = SourceSettings()
        self.staged: nt.StagedSample | None = None
        self.drafts: list[nt.DraftColumn] = []
        self.finished = False               # saved or discarded: leaving asks nothing
        self.job = None
        self._dry_job = None
        self._dry_again = False
        self._dry_sig = None
        self.bridge.busyChanged.connect(self._runner_free)

        self.steps = StepBar(nt.STEPS, self)
        self.content.addWidget(self.steps)
        self.pages = QStackedWidget(self)
        self.sample_step = SampleStep(self)
        self.sheets_step = SheetsStep(self)
        self.columns_step = ColumnsStep(self)
        self.rules_step = RulesStep(self)
        self.outputs_step = OutputsStep(self)
        self.review_step = ReviewStep(self)
        for p in (self.sample_step, self.sheets_step, self.columns_step, self.rules_step, self.outputs_step,
                  self.review_step):
            self.pages.addWidget(p)
        self.content.addWidget(self.pages, 1)
        self.progress = ProgressPanel(self)
        self.progress.hide()
        self.content.addWidget(self.progress)

        foot = QHBoxLayout()
        foot.setSpacing(12)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setProperty("kind", "plain")
        self.cancel_button.clicked.connect(self.cancel)
        self.back_button = primary("Back", self, "secondary")
        self.back_button.clicked.connect(self.back)
        foot.addWidget(self.cancel_button)
        foot.addWidget(self.back_button)
        foot.addStretch(1)
        self.footer = note("", self)
        self.footer.setWordWrap(False)
        foot.addWidget(self.footer)
        self.next_button = primary("Next: Sheets", self)
        self.next_button.clicked.connect(self.next)
        self.save_button = primary("Save template", self, "secondary")
        self.save_button.clicked.connect(lambda: self.save(False))
        self.save_run_button = primary("Save and start first run", self)
        self.save_run_button.clicked.connect(lambda: self.save(True))
        for b in (self.next_button, self.save_button, self.save_run_button):
            foot.addWidget(b)
            self.bridge.guard(b)
        self.content.addLayout(foot)
        self.sample_step.name_note.setText(f"Must be unique within {client_name}." if client_name else "")
        self._show_step()

    # ------------------------------------------------------------------------------------------ frame
    def crumbs(self) -> list[Crumb]:
        return [Crumb("Clients", lambda: self.window_.open_area("clients")),
                Crumb(self.client_name, lambda: self.window_.go("client", client_id=self.client_id,
                                                               name=self.client_name)),
                Crumb("New template")]

    def shown(self) -> None:
        if not self.client_name:
            from sankalan.query import catalogue as q
            self.load("Read client", lambda ctx: q.client_name(ctx.cursor(), self.client_id), self._client_named)

    def _client_named(self, name) -> None:
        self.client_name = name or ""
        self.sample_step.name_note.setText(f"Must be unique within {self.client_name}.")
        self.refresh_crumbs()

    @property
    def sample_rows(self) -> int:
        return self.staged.rows if self.staged else 0

    @property
    def sample_name(self) -> str:
        return self.info.file_name if self.info else ""

    def _show_step(self) -> None:
        self.pages.setCurrentIndex(self.step)
        self.steps.set_current(self.step)
        self.back_button.setVisible(self.step > SAMPLE)
        last = self.step == REVIEW
        self.next_button.setVisible(not last)
        self.save_button.setVisible(last)
        self.save_run_button.setVisible(last)
        if not last:
            self.next_button.setText(f"Next: {nt.STEPS[self.step + 1]}")
        self.update_footer()

    def update_footer(self) -> None:
        text = ""
        if self.step == SHEETS and self.info is not None:
            if self.info.is_csv:
                text = f"{self.info.file_name} will be read"
            else:
                names = nt.sheets_to_read(self.info, self.source)
                text = f"{and_list(names)} will be read" if names else "No sheet ticked"
        elif self.step == COLUMNS:
            n = sum(1 for d in self.drafts if d.include)
            text = f"{n} of {len(self.drafts)} columns included"
        elif self.step == OUTPUTS:
            text = "Optional: you can skip this step"
        self.footer.setText(text)

    # ------------------------------------------------------------------------------------------ Jobs
    def run(self, operation: str, work, on_done, *, cancellable: bool = True, progress: bool = True,
            on_failed=None):
        def done(result):
            self.progress.hide()
            self.job = None
            on_done(result)

        def failed(error):
            self.progress.hide()
            self.job = None
            (on_failed or self._failed)(error)

        def cancelled():
            self.progress.hide()
            self.job = None

        job = self.start(operation, work, done, failed, cancellable=cancellable, on_cancelled=cancelled)
        self.job = job
        if job is not None and progress:
            self.progress.bind(job)
            self.progress.show()
        return job

    def _failed(self, error) -> None:
        text = str(error) if isinstance(error, nt.SampleProblem) else error_text(error)
        if self.step == SAMPLE:
            self.sample_step.set_file_error(text)
        else:
            self.show_banner(Banner("error", text))

    # ------------------------------------------------------------------------------------------ step 1
    def pick(self, path) -> bool:
        """A file picked or dropped: refused types get a plain message (C3-04); else it is opened and its first
        rows read (C3-02, C3-03)."""
        self.sample_step.set_file_error("")
        msg = smp.refusal(path)
        if msg is not None:
            self.sample_step.set_file_error(msg)
            return False
        folder, previous = self.folder, self.staged
        self.staged = None

        def work(ctx):
            info = nt.inspect(ctx, path)
            source = nt.default_source(info)
            return info, source, nt.stage(ctx, folder, info, source, previous, workers=WORKERS)

        def done(result):
            self.info, self.source, self.staged = result
            self.drafts = nt.draft_columns(self.staged)
            self.rules_step.rules = []
            self.outputs_step.outputs = []
            self.outputs_step.selected = -1
            self.sample_step.show_file(self.info, self.staged)

        def failed(error):
            self.info = None
            self.sample_step.show_file(None, None)
            self._failed(error)

        return self.run("Read sample", work, done, on_failed=failed) is not None

    # ------------------------------------------------------------------------------------------ step 2
    def reread_csv(self, encoding: str, delimiter: str) -> None:
        """C3-08: encoding and delimiter can be changed; the preview is read again with them."""
        info = self.info
        if info is None or not info.is_csv:
            return

        def done(new: smp.SampleInfo):
            self.info = new
            self.source = SourceSettings(self.source.sheets, list(self.source.sheet_names),
                                         None if encoding == _plain(new.detected_encoding) else encoding,
                                         None if delimiter == new.detected_delimiter else delimiter)
            self.sheets_step.load()

        self.run("Read sample", lambda ctx: nt.inspect(ctx, info.path, encoding, delimiter), done, progress=False)

    # ------------------------------------------------------------------------------------------ navigation
    def next(self) -> None:
        if self.job is not None:
            return
        handler = {SAMPLE: self._next_sample, SHEETS: self._next_sheets, COLUMNS: self._next_columns,
                   RULES: self._next_rules, OUTPUTS: self._next_outputs}.get(self.step)
        if handler is not None:
            handler()

    def go_step(self, step: int) -> None:
        self.step = step
        if step == SHEETS:
            self.sheets_step.load()
        elif step == COLUMNS:
            self.columns_step.show_error("")
            self.columns_step.load()
        elif step == RULES:
            self.rules_step.load(nt.included(self.drafts), self.rules_step.rules)
            self.run_dry()
        elif step == OUTPUTS:
            self.outputs_step.load_draft(self.draft_template())
        elif step == REVIEW:
            self.review_step.load()
        self._show_step()

    def back(self) -> None:
        """Back keeps every entry (C3-22)."""
        if self.step > SAMPLE and self.job is None:
            if self.step == OUTPUTS:
                self.outputs_step._store()
            self.go_step(self.step - 1)

    def _next_sample(self) -> None:
        st = self.sample_step
        st.set_name_error("")
        if not st.name.text().strip():
            st.set_name_error("Enter a template name.")
            return
        if self.info is None or self.staged is None:
            st.set_file_error("Choose a sample file.")
            return
        try:
            if smp.file_key(self.info.path) != self.info.key():
                st.set_file_error(f"{self.info.file_name} has changed since it was picked. Pick it again.")
                return
        except OSError:
            st.set_file_error(f"{self.info.file_name} was not found. It may have been moved or deleted.")
            return
        client, name = self.client_id, st.name.text()

        def failed(error):
            st.set_name_error(error_text(error))

        self.run("Check name", lambda ctx: nt.check_name(ctx, client, name), lambda _n: self.go_step(SHEETS),
                 progress=False, on_failed=failed)

    def _next_sheets(self) -> None:
        problem = nt.sheets_problem(self.info, self.source)
        if problem:
            self.show_banner(Banner("error", problem))
            return
        self._clear_errors()
        if self.staged is not None and self.staged.key == nt.stage_key(self.info, self.source):
            self.go_step(COLUMNS)           # C3-22: not read again
            return
        folder, info, source, previous = self.folder, self.info, copy.deepcopy(self.source), self.staged
        self.staged = None

        def done(staged: nt.StagedSample):
            self.staged = staged
            self.drafts = merge_drafts(self.drafts, nt.draft_columns(staged), staged)
            self.sample_step.show_file(self.info, staged)
            self.go_step(COLUMNS)

        self.run("Read sample", lambda ctx: nt.stage(ctx, folder, info, source, previous, workers=WORKERS), done)

    def _next_columns(self) -> None:
        problem = nt.columns_problem(self.drafts)
        self.columns_step.show_error(problem or "")
        if not problem:
            self.go_step(RULES)

    def _next_rules(self) -> None:
        problem = self.rules_step.check()
        self.rules_step.show_error(problem or "")
        if not problem:
            self.go_step(OUTPUTS)

    def _next_outputs(self) -> None:
        problem = self.outputs_step.check()          # C3-18: an output needs a name
        self.outputs_step.show_error(problem or "")
        if not problem:
            self.go_step(REVIEW)

    def _clear_errors(self) -> None:
        for b in self.banners():
            b.hide()

    # ------------------------------------------------------------------------------------------ dry run (VR-8)
    def run_dry(self, force: bool = False) -> None:
        """Count each rule's failures on the sample (VR-8). One dry run at a time: a change while one runs (or
        while another Job runs) queues one more, started when the runner is free."""
        if self.staged is None or not self.alive:
            return
        rules = [Rule.from_dict(r.to_dict()) for r in self.rules_step.all_rules()]
        sig = (nt.columns_signature(self.drafts), tuple(str(r.to_dict()) for r in rules))
        if not force and sig == self._dry_sig and self.rules_step.counts is not None:
            return                          # counts still current (Back to this step, C3-22)
        if self._dry_job is not None or self.bridge.busy:
            self._dry_again = True
            self.rules_step.set_counts(None)
            return
        self._dry_again = False
        staged, drafts = self.staged, copy.deepcopy(self.drafts)
        self.rules_step.set_counts(None)

        def done(result: nt.DryRun):
            self._dry_job = None
            if not self._dry_again:
                self._dry_sig = sig
                self.rules_step.set_counts(result.counts, result.first)

        def failed(error):
            self._dry_job = None
            self._dry_again = False
            self.rules_step.show_error(error_text(error))

        def cancelled():
            self._dry_job = None

        self._dry_job = self.start("Check rules on the sample", lambda ctx: nt.dry_run(ctx, staged, drafts, rules),
                                   done, failed, cancellable=True, on_cancelled=cancelled)

    def _runner_free(self, busy: bool) -> None:
        if not busy and self._dry_again and self.alive and self.step == RULES:
            QTimer.singleShot(0, lambda: self.alive and self._dry_again and self.run_dry(force=True))

    def rules_changed(self) -> None:
        self.run_dry()

    # ------------------------------------------------------------------------------------------ preview (DO-8)
    def preview_work(self, definition: Definition):
        staged, drafts = self.staged, copy.deepcopy(self.drafts)
        return lambda ctx: nt.preview(ctx, staged, drafts, definition)

    # ------------------------------------------------------------------------------------------ save
    def draft_template(self) -> Template:
        """The template as entered so far (draft column IDs; ``build_template`` renumbers them on save)."""
        cols = nt.included(self.drafts)
        outs = copy.deepcopy(self.outputs_step.outputs)
        return Template("", self.client_id, self.sample_step.name.text().strip(), copy.deepcopy(self.source),
                        copy.deepcopy(cols), self.rules_step.all_rules(), outs)

    def save(self, start_run: bool) -> None:
        """C3-20 Save template → the client's templates; C3-21 Save and start first run → New run, step 1."""
        if self.job is not None:
            return
        t = nt.build_template(self.client_id, self.sample_step.name.text(), self.source, self.drafts,
                              self.rules_step.all_rules(), self.outputs_step.outputs)

        def done(tid: str):
            self.finished = True
            self._discard_sample()
            if start_run:
                self.window_.go("new_run", template_id=tid, name=t.name)
            else:
                self.window_.go("client", client_id=self.client_id, name=self.client_name,
                                banner=Banner("success", f"{t.name} saved."))

        self.run("Save template", lambda ctx: nt.save(ctx, t), done, cancellable=False)

    # ------------------------------------------------------------------------------------------ leaving
    def cancel(self) -> bool:
        """C3-01: "Discard this template?" Keep editing stays on the step with entries intact."""
        key = ask(self, DISCARD_TITLE, DISCARD_TEXT,
                  [(STAY, "Keep editing", None), ("discard", "Discard", "destructive")])
        if key != "discard":
            return False
        self._discard()
        self.window_.go("client", client_id=self.client_id, name=self.client_name)
        return True

    def _discard(self) -> bool:
        self.finished = True
        if self.job is not None:
            self.job.cancel()
        self._discard_sample()
        return True

    def _discard_sample(self) -> None:
        if self.staged is not None:
            nt.discard(self.folder, self.staged)
            self.staged = None

    def leave_guard(self) -> LeaveGuard | None:
        if self.finished:
            return None
        return LeaveGuard(DISCARD_TITLE, DISCARD_TEXT, [(STAY, "Keep editing", None, None),
                                                         ("discard", "Discard", "destructive", self._discard)])

    def closing(self) -> None:
        for job in (self.job, self._dry_job):
            if job is not None and job.cancellable:
                job.cancel()
                job.wait(2.0)
        self._discard_sample()
        super().closing()


def _plain(encoding: str | None) -> str | None:
    return "utf-8" if encoding == ENC_UTF8_BOM else encoding


def merge_drafts(old: list[nt.DraftColumn], new: list[nt.DraftColumn],
                 staged: nt.StagedSample) -> list[nt.DraftColumn]:
    """After the sample is read again (other sheets), keep each header's entries and position; new headers go
    last with fresh column IDs; headers no longer in the sample drop out (with their rules)."""
    if not old:
        return new
    by_key = {norm(d.header): d for d in new}
    out, used = [], set()
    for d in old:
        n = by_key.get(norm(d.header))
        if n is None or id(n) in used:
            continue
        used.add(id(n))
        d.source = n.source
        d.detected = n.detected
        out.append(d)
    cols = [d.column for d in old]
    for n in new:
        if id(n) not in used:
            n.column.id = next_column_id(cols)
            cols.append(n.column)
            out.append(n)
    return out
