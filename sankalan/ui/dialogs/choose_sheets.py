"""4.1c Choose sheets for a file (Feature Spec A2 SHT-4, SHT-5; Tech spec A2 7.4).

Built from the file's sheet list as Probe read it (``FileSheet.sheets``), so no Job is needed to open it: every sheet
in workbook order with a checkbox and "about N rows"; hidden sheets listed, disabled and marked "Hidden, skipped".
The ticks it opens with come from the session (``RunSession.dialog_ticks``). Read N sheets returns the ticked names
in workbook order; the caller probes the file again with them.
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from sankalan import formats
from sankalan.ingest.probe import SheetEntry
from sankalan.ui import theme
from sankalan.ui.dialogs.base import Dialog

NOTE = ("The header row is found in each sheet. Headers that don't match the template's columns are handled in "
        "Mapping.")
HIDDEN = "Hidden, skipped"


def about_rows(n: int | None) -> str:
    return f"about {formats.count(n, 'row')}" if n is not None else "rows not known"


def read_label(n: int) -> str:
    """"Read 2 sheets", "Read 1 sheet"."""
    return f"Read {formats.count(n, 'sheet')}"


def total_text(entries: list[SheetEntry]) -> str:
    """"2 sheets · about 412,300 rows" for the ticked sheets."""
    if not entries:
        return "No sheets ticked"
    rows = sum(e.rows_approx or 0 for e in entries)
    return f"{formats.count(len(entries), 'sheet')} · {about_rows(rows)}"


class ChooseSheetsDialog(Dialog):
    def __init__(self, file_name: str, size: int, sheets: list[SheetEntry], ticked: list[str], parent=None):
        super().__init__(f"Choose sheets for {file_name}", parent, width=520)
        self.entries = list(sheets)
        self.size_line = self.text(formats.size(size) if size else "", "small")
        box = QFrame(self)
        box.setObjectName("SheetList")
        box.setStyleSheet(f"#SheetList {{ border: 1px solid {theme.BORDER}; border-radius: 8px; "
                          f"background: {theme.WHITE}; }}")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 6, 12, 6)
        bl.setSpacing(0)
        want = {t.lower() for t in ticked}
        self.checks: list[QCheckBox] = []
        self.counts: list[QLabel] = []
        for e in self.entries:
            row = QWidget(box)
            row.setMinimumHeight(theme.ROW_HEIGHT)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox(e.name, row)
            cb.setAccessibleName(e.name)
            cb.setChecked(e.visible and e.name.lower() in want)
            cb.setEnabled(e.visible)
            cb.toggled.connect(self._changed)
            rl.addWidget(cb, 1)
            count = QLabel(about_rows(e.rows_approx) if e.visible else HIDDEN, row)
            count.setProperty("kind", "small")
            rl.addWidget(count)
            bl.addWidget(row)
            self.checks.append(cb)
            self.counts.append(count)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(box)
        scroll.setMaximumHeight(theme.ROW_HEIGHT * 8 + 16)
        scroll.setMinimumHeight(min(theme.ROW_HEIGHT * len(self.entries) + 16, theme.ROW_HEIGHT * 8 + 16))
        self.body.addWidget(scroll)
        self.note = self.text(NOTE, "small")
        self.total = self.text("", "body")
        self.add_button("Cancel", None, self.reject)
        self.ok = self.add_button(read_label(0), "primary", self.accept, default=True)
        self._changed()

    def chosen(self) -> list[str]:
        """The ticked sheets in workbook order."""
        return [e.name for e, cb in zip(self.entries, self.checks) if e.visible and cb.isChecked()]

    def tick(self, name: str, on: bool = True) -> None:
        for e, cb in zip(self.entries, self.checks):
            if e.name == name and cb.isEnabled():
                cb.setChecked(on)

    def rows(self) -> list[tuple[str, bool, bool, str]]:
        """(name, ticked, enabled, count text) per sheet, for tests."""
        return [(e.name, cb.isChecked(), cb.isEnabled(), lab.text())
                for e, cb, lab in zip(self.entries, self.checks, self.counts)]

    def _changed(self, *_a) -> None:
        picked = [e for e, cb in zip(self.entries, self.checks) if e.visible and cb.isChecked()]
        self.total.setText(total_text(picked))
        self.ok.setText(read_label(len(picked)))
        self.ok.setEnabled(bool(picked))
