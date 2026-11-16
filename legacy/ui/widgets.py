"""Small shared widgets and helpers."""
from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
                               QAbstractItemView)

from ..core.validation import RULES

SEVERITIES = [("error", "Error"), ("warning", "Warning")]


def label(text, name=None, wrap=False):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def button(text, name=None, slot=None, obj=None):
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    if obj:
        b.setAccessibleName(obj)
        b.setProperty("testid", obj)
    if slot:
        b.clicked.connect(slot)
    return b


def card(layout_cls=QVBoxLayout, margins=16, spacing=10):
    f = QFrame()
    f.setObjectName("card")
    lay = layout_cls(f)
    lay.setContentsMargins(margins, margins, margins, margins)
    lay.setSpacing(spacing)
    return f, lay


def restyle(w):
    w.style().unpolish(w)
    w.style().polish(w)


class Banner(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("banner")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.title = label("", "h2", wrap=True)
        self.body = label("", wrap=True)
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        self.hide()

    def show_msg(self, kind, title, body=""):
        self.setProperty("kind", kind)
        restyle(self)
        self.title.setText(title)
        self.body.setText(body)
        self.body.setVisible(bool(body))
        self.show()


class Tile(QFrame):
    def __init__(self, caption):
        super().__init__()
        self.setObjectName("tile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(label(caption, "small"))
        self.value = label("", "tileValue")
        lay.addWidget(self.value)

    def set(self, text, color=None):
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color};" if color else "")


def table(headers, stretch_last=True):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch_last:
        t.horizontalHeader().setStretchLastSection(True)
    return t


def item(text, bold=False, color=None, align_right=False, data=None):
    it = QTableWidgetItem("" if text is None else str(text))
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if color:
        from PySide6.QtGui import QColor
        it.setForeground(QColor(color))
    if align_right:
        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if data is not None:
        it.setData(Qt.ItemDataRole.UserRole, data)
    return it


# ---------------------------------------------------------------- rule parameters

def rule_params_text(rule):
    k = rule["type"]
    if k == "number_range":
        parts = []
        if rule.get("min") is not None:
            parts.append(f"min={rule['min']:g}")
        if rule.get("max") is not None:
            parts.append(f"max={rule['max']:g}")
        return ", ".join(parts)
    if k == "date_range":
        parts = []
        if rule.get("from"):
            parts.append(f"from={rule['from']}")
        if rule.get("to"):
            parts.append(f"to={rule['to']}")
        return ", ".join(parts)
    if k == "allowed_values":
        return "values=" + "|".join(rule.get("values", []))
    return ""


def parse_rule_params(kind, text):
    """'min=0, max=100' / 'from=01-09-2026, to=30-09-2026' / 'values=B2B|B2C'."""
    out = {}
    for part in (text or "").split(","):
        if "=" not in part:
            continue
        k, v = (s.strip() for s in part.split("=", 1))
        k = k.lower()
        if kind == "number_range" and k in ("min", "max") and v:
            out[k] = float(v)
        elif kind == "date_range" and k in ("from", "to") and v:
            out[k] = v
        elif kind == "allowed_values" and k == "values":
            out["values"] = [x.strip() for x in v.split("|") if x.strip()]
    return out


class RulesEditor(QWidget):
    """Edit the list of checks on one column: Check, Severity, Parameters."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.t = QTableWidget(0, 3)
        self.t.setHorizontalHeaderLabels(["Check", "Severity", "Settings"])
        self.t.verticalHeader().setVisible(False)
        self.t.horizontalHeader().setStretchLastSection(True)
        self.t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.t.setColumnWidth(0, 190)
        self.t.setColumnWidth(1, 100)
        self.t.setMinimumHeight(150)
        lay.addWidget(self.t)
        row = QHBoxLayout()
        self.add_btn = button("+ Add check", slot=self.add_rule, obj="addCheck")
        self.del_btn = button("Remove check", slot=self.remove_selected, obj="removeCheck")
        row.addWidget(self.add_btn)
        row.addWidget(self.del_btn)
        row.addStretch()
        lay.addLayout(row)
        self._loading = False

    def set_rules(self, rules):
        self._loading = True
        self.t.setRowCount(0)
        for r in rules:
            self._add_row(r)
        self._loading = False

    def _add_row(self, rule):
        i = self.t.rowCount()
        self.t.insertRow(i)
        kind = QComboBox()
        for k, v in RULES.items():
            if k != "duplicates":
                kind.addItem(v, k)
        kind.setCurrentIndex(max(0, kind.findData(rule["type"])))
        sev = QComboBox()
        for k, v in SEVERITIES:
            sev.addItem(v, k)
        sev.setCurrentIndex(max(0, sev.findData(rule.get("severity", "error"))))
        params = QLineEdit(rule_params_text(rule))
        params.setPlaceholderText("e.g. min=0 · from=01-09-2026, to=30-09-2026 · values=B2B|B2C")
        for w in (kind, sev):
            w.currentIndexChanged.connect(self._emit)
        params.editingFinished.connect(self._emit)
        self.t.setCellWidget(i, 0, kind)
        self.t.setCellWidget(i, 1, sev)
        self.t.setCellWidget(i, 2, params)

    def _emit(self):
        if not self._loading:
            self.changed.emit()

    def add_rule(self, rule=None):
        self._add_row(rule if isinstance(rule, dict) else {"type": "not_blank", "severity": "error"})
        self._emit()

    def remove_selected(self):
        r = self.t.currentRow()
        if r >= 0:
            self.t.removeRow(r)
            self._emit()

    def rules(self):
        out = []
        for i in range(self.t.rowCount()):
            kind = self.t.cellWidget(i, 0).currentData()
            rule = {"type": kind, "severity": self.t.cellWidget(i, 1).currentData()}
            rule.update(parse_rule_params(kind, self.t.cellWidget(i, 2).text()))
            out.append(rule)
        return out


class Job(QThread):
    """Runs session work off the UI thread (NF-4) with progress and cancel."""
    progress = Signal(str, int, int)
    done = Signal(object)
    failed = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            res = self.fn(lambda s, d, t: self.progress.emit(s, int(d), int(t)), self._cancel.is_set)
        except BaseException as exc:  # noqa: BLE001 - reported to the UI
            self.failed.emit(exc)
        else:
            self.done.emit(res)
