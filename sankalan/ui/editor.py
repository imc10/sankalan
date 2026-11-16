"""Template editor dialog (TPL-1 .. TPL-4): input, columns, checks, output settings."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLineEdit, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget, QHeaderView, QListWidget)

from ..core.template import new_column
from .widgets import RulesEditor, button, label, SEVERITIES

TYPES = [("text", "Text"), ("number", "Number"), ("date", "Date")]


class TemplateEditor(QDialog):
    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.t = template.copy()
        self.setWindowTitle(f"Edit template: {self.t.client} → {self.t.task}" if self.t.client else "New template")
        self.resize(980, 640)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        self._general()
        self._columns()
        self._checks()
        self._input()
        self._output()
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    # ---------------------------------------------------------------- tabs
    def _general(self):
        w = QWidget()
        f = QFormLayout(w)
        self.client = QLineEdit(self.t.client)
        self.client.setObjectName("edClient")
        self.task = QLineEdit(self.t.task)
        self.task.setObjectName("edTask")
        f.addRow("Client", self.client)
        f.addRow("Task", self.task)
        f.addRow("", label(f"Version {self.t.version} · created {self.t.created[:10]} · modified {self.t.modified[:10]}",
                           "small"))
        self.tabs.addTab(w, "General")

    def _columns(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(label("Output columns, in output order. Aliases are other header names the column accepts "
                          "(separate with |).", "small", wrap=True))
        self.cols = QTableWidget(0, 7)
        self.cols.setObjectName("edColumns")
        self.cols.setHorizontalHeaderLabels(["Name", "Type", "Date order", "Required", "Include", "Totals",
                                             "Aliases"])
        self.cols.horizontalHeader().setStretchLastSection(True)
        self.cols.verticalHeader().setVisible(False)
        for c in self.t.columns:
            self._add_col_row(c)
        v.addWidget(self.cols)
        row = QHBoxLayout()
        row.addWidget(button("+ Add column", slot=lambda: self._add_col_row(new_column("New column")),
                             obj="edAddColumn"))
        row.addWidget(button("Remove column", slot=self._remove_col, obj="edRemoveColumn"))
        row.addWidget(button("Move up", slot=lambda: self._move(-1), obj="edUp"))
        row.addWidget(button("Move down", slot=lambda: self._move(1), obj="edDown"))
        row.addStretch()
        v.addLayout(row)
        self.tabs.addTab(w, "Columns")

    def _add_col_row(self, c):
        r = self.cols.rowCount()
        self.cols.insertRow(r)
        self.cols.setItem(r, 0, QTableWidgetItem(c["name"]))
        tp = QComboBox()
        for k, lab in TYPES:
            tp.addItem(lab, k)
        tp.setCurrentIndex(tp.findData(c.get("type", "text")))
        do = QComboBox()
        do.addItem("DD-MM-YYYY", "DMY")
        do.addItem("MM-DD-YYYY", "MDY")
        do.setCurrentIndex(do.findData(c.get("date_order", "DMY")))
        self.cols.setCellWidget(r, 1, tp)
        self.cols.setCellWidget(r, 2, do)
        for j, key in ((3, "required"), (4, "include"), (5, "total")):
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Checked if c.get(key, key == "include") else Qt.CheckState.Unchecked)
            self.cols.setItem(r, j, it)
        self.cols.setItem(r, 6, QTableWidgetItem("|".join(c.get("aliases", []))))
        self.cols.item(r, 0).setData(Qt.ItemDataRole.UserRole, list(c.get("rules", [])))

    def _remove_col(self):
        r = self.cols.currentRow()
        if r >= 0:
            self.cols.removeRow(r)

    def _move(self, d):
        r = self.cols.currentRow()
        n = r + d
        if r < 0 or n < 0 or n >= self.cols.rowCount():
            return
        cols = self._read_columns()
        cols[r], cols[n] = cols[n], cols[r]
        self.cols.setRowCount(0)
        for c in cols:
            self._add_col_row(c)
        self.cols.selectRow(n)

    def _read_columns(self):
        out = []
        for r in range(self.cols.rowCount()):
            name = (self.cols.item(r, 0).text() or "").strip()
            if not name:
                continue
            out.append({
                "name": name,
                "type": self.cols.cellWidget(r, 1).currentData(),
                "date_order": self.cols.cellWidget(r, 2).currentData(),
                "required": self.cols.item(r, 3).checkState() == Qt.CheckState.Checked,
                "include": self.cols.item(r, 4).checkState() == Qt.CheckState.Checked,
                "total": self.cols.item(r, 5).checkState() == Qt.CheckState.Checked,
                "aliases": [a.strip() for a in (self.cols.item(r, 6).text() or "").split("|") if a.strip()],
                "rules": self.cols.item(r, 0).data(Qt.ItemDataRole.UserRole) or [],
            })
        return out

    def _checks(self):
        w = QWidget()
        v = QVBoxLayout(w)
        top = QHBoxLayout()
        self.col_list = QListWidget()
        self.col_list.setObjectName("edCheckColumns")
        self.col_list.setMaximumWidth(220)
        self.col_list.currentRowChanged.connect(self._show_rules)
        top.addWidget(self.col_list)
        self.rules = RulesEditor()
        self.rules.changed.connect(self._store_rules)
        top.addWidget(self.rules, 1)
        v.addLayout(top)
        v.addWidget(label("Duplicate checks: key columns separated by |, e.g. GSTIN|Invoice No", "small"))
        dr = QHBoxLayout()
        self.dup_keys = QLineEdit("; ".join("|".join(d["columns"]) for d in self.t.duplicate_keys))
        self.dup_keys.setObjectName("edDupKeys")
        self.dup_keys.setPlaceholderText("GSTIN|Invoice No   (several checks: separate with ;)")
        self.dup_sev = QComboBox()
        for k, lab in SEVERITIES:
            self.dup_sev.addItem(lab, k)
        if self.t.duplicate_keys:
            self.dup_sev.setCurrentIndex(self.dup_sev.findData(self.t.duplicate_keys[0].get("severity", "error")))
        dr.addWidget(self.dup_keys, 1)
        dr.addWidget(self.dup_sev)
        v.addLayout(dr)
        v.addWidget(label("GSTIN exceptions (accepted as they are, e.g. UN bodies): separate with |", "small"))
        self.gst_exc = QLineEdit("|".join(self.t.gstin_exceptions))
        self.gst_exc.setObjectName("edGstinExceptions")
        v.addWidget(self.gst_exc)
        self.tabs.addTab(w, "Checks")
        self.tabs.currentChanged.connect(self._tab_changed)

    def _tab_changed(self, i):
        if self.tabs.tabText(i) == "Checks":
            cols = self._read_columns()
            self.col_list.blockSignals(True)
            self.col_list.clear()
            self.col_list.addItems([c["name"] for c in cols])
            self.col_list.blockSignals(False)
            self.col_list.setCurrentRow(0)

    def _row_for(self, name):
        for r in range(self.cols.rowCount()):
            if self.cols.item(r, 0).text().strip() == name:
                return r
        return -1

    def _show_rules(self, i):
        if i < 0:
            return
        r = self._row_for(self.col_list.item(i).text())
        self.rules.set_rules(self.cols.item(r, 0).data(Qt.ItemDataRole.UserRole) or [] if r >= 0 else [])

    def _store_rules(self):
        it = self.col_list.currentItem()
        if not it:
            return
        r = self._row_for(it.text())
        if r >= 0:
            self.cols.item(r, 0).setData(Qt.ItemDataRole.UserRole, self.rules.rules())

    def _input(self):
        w = QWidget()
        f = QFormLayout(w)
        i = self.t.input
        self.in_pattern = QLineEdit(i.get("pattern", "*"))
        self.in_pattern.setObjectName("edPattern")
        self.in_sub = QCheckBox("Include subfolders")
        self.in_sub.setChecked(bool(i.get("include_subfolders")))
        self.in_sheet_mode = QComboBox()
        self.in_sheet_mode.setObjectName("edSheetMode")
        for k, lab in (("first", "First visible sheet"), ("name", "Sheet by name"),
                       ("pattern", "Every sheet matching a pattern")):
            self.in_sheet_mode.addItem(lab, k)
        self.in_sheet_mode.setCurrentIndex(self.in_sheet_mode.findData(i.get("sheet_mode", "first")))
        self.in_sheet_value = QLineEdit(i.get("sheet_value", ""))
        self.in_sheet_value.setObjectName("edSheetValue")
        self.in_header = QSpinBox()
        self.in_header.setRange(0, 1000)
        self.in_header.setSpecialValueText("Auto-detect")
        self.in_header.setValue(i.get("header_row") or 0)
        self.in_trailer = QLineEdit("|".join(i.get("trailer_words", [])))
        self.in_trailer.setObjectName("edTrailer")
        self.in_delim = QComboBox()
        for lab, d in (("Detect", "auto"), ("Comma", ","), ("Semicolon", ";"), ("Tab", "\t"), ("Pipe", "|")):
            self.in_delim.addItem(lab, d)
        self.in_delim.setCurrentIndex(max(0, self.in_delim.findData(i.get("csv_delimiter", "auto"))))
        f.addRow("File name pattern", self.in_pattern)
        f.addRow("", self.in_sub)
        f.addRow("Sheets", self.in_sheet_mode)
        f.addRow("Sheet name or pattern", self.in_sheet_value)
        f.addRow("Header row", self.in_header)
        f.addRow("Skip rows starting with (| separated)", self.in_trailer)
        f.addRow("CSV delimiter", self.in_delim)
        self.tabs.addTab(w, "Input")

    def _output(self):
        w = QWidget()
        f = QFormLayout(w)
        o = self.t.output
        self.out_fmt = QComboBox()
        self.out_fmt.setObjectName("edFormat")
        self.out_fmt.addItem("Excel (.xlsx)", "xlsx")
        self.out_fmt.addItem("CSV", "csv")
        self.out_fmt.setCurrentIndex(self.out_fmt.findData(o.get("format", "xlsx")))
        self.out_folder = QLineEdit(o.get("folder", ""))
        self.out_name = QLineEdit(o.get("name_pattern", "{client}_{task}_{yyyymm}"))
        self.out_name.setObjectName("edNamePattern")
        self.out_checks = {}
        f.addRow("Format", self.out_fmt)
        f.addRow("Folder", self.out_folder)
        f.addRow("File name pattern", self.out_name)
        for key, lab in (("source_file", "Source File column"), ("source_sheet", "Source Sheet column"),
                         ("source_row", "Source Row column"), ("indian_format", "Indian number format"),
                         ("issues_sheet", "Issues sheet")):
            cb = QCheckBox(lab)
            cb.setChecked(bool(o.get(key)))
            self.out_checks[key] = cb
            f.addRow("", cb)
        self.tabs.addTab(w, "Output")

    # ---------------------------------------------------------------- result
    def result_template(self):
        t = self.t
        t.client, t.task = self.client.text().strip(), self.task.text().strip()
        self._store_rules()
        t.columns = self._read_columns()
        names = {c["name"] for c in t.columns}
        dups = []
        for part in self.dup_keys.text().split(";"):
            keys = [k.strip() for k in part.split("|") if k.strip() in names]
            if keys:
                dups.append({"columns": keys, "severity": self.dup_sev.currentData()})
        t.duplicate_keys = dups
        t.gstin_exceptions = [g.strip().upper() for g in self.gst_exc.text().split("|") if g.strip()]
        t.input.update({"pattern": self.in_pattern.text().strip() or "*",
                        "include_subfolders": self.in_sub.isChecked(),
                        "sheet_mode": self.in_sheet_mode.currentData(),
                        "sheet_value": self.in_sheet_value.text().strip(),
                        "header_row": self.in_header.value() or None,
                        "trailer_words": [x.strip() for x in self.in_trailer.text().split("|") if x.strip()],
                        "csv_delimiter": self.in_delim.currentData()})
        t.output.update({"format": self.out_fmt.currentData(), "folder": self.out_folder.text().strip(),
                         "name_pattern": self.out_name.text().strip() or "{client}_{task}_{yyyymm}"})
        for k, cb in self.out_checks.items():
            t.output[k] = cb.isChecked()
        return t
