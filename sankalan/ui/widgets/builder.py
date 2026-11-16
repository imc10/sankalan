"""The analysis builder (ANA-4 to ANA-6, DO-1, DO-3): AND filters, group levels and measures, plus Show subtotals.

Shared by the template's Default outputs tab (3.2), the New template wizard (2.5, Phase 8) and the Analysis screen
(6.2, Phase 10). With ``output=True`` date filters are relative only (latest month, quarter or year in the run) or
Blank / Not blank (DO-3, C3-19). Columns are referenced by stable ID (V3-2).

Values typed for Is one of are separated by commas; Phase 10 adds the picker of the 1,000 most frequent values.
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
                               QVBoxLayout, QWidget)

from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, Group, Measure
from sankalan.model.template import DATE, Column
from sankalan.ui import theme
from sankalan.ui.widgets.controls import heading, icon_button, plus_button

OP_LABELS = {
    d.LATEST_MONTH: "latest month in this run", d.LATEST_QUARTER: "latest quarter in this run",
    d.LATEST_YEAR: "latest year in this run", d.BLANK: "is blank", d.NOT_BLANK: "is not blank",
    d.ONE_OF: "is one of", d.CONTAINS: "contains", d.EQUALS: "equals", d.BETWEEN: "is between",
    d.YEAR: "year is", d.QUARTER: "quarter is", d.MONTH: "month is",
}
GRAIN_LABELS = {"day": "Day", "month": "Month", "quarter": "Quarter", "year": "Year"}
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")


def ops_for(column: Column, output: bool) -> list[str]:
    if column.type == DATE:
        return list(d.OUTPUT_DATE_OPS) if output else [o for o in d.FILTER_OPS[DATE] if o not in d.RELATIVE]
    return list(d.FILTER_OPS[column.type])


def measure_choices(columns: list[Column]) -> list[tuple[str, str | None, str]]:
    """(fn, column id, label) for every valid measure: "Count of rows", then per column in column order."""
    out = [(d.COUNT, None, "Count of rows")]
    for c in columns:
        for fn in d.MEASURE_FNS:
            if c.type in d.MEASURE_TYPES[fn]:
                out.append((fn, c.id, f"{d.FN_NAMES[fn]} of {c.name}"))
    return out


def parse_typed_date(text: str) -> str | None:
    """DD-MM-YYYY (or DD/MM/YYYY) typed on screen → ISO for the definition; None when blank."""
    t = text.strip()
    if not t:
        return None
    try:
        return dt.datetime.strptime(t.replace("/", "-"), "%d-%m-%Y").date().isoformat()
    except ValueError:
        raise d.DefinitionError(f"{t} is not a date. Type it as DD-MM-YYYY.") from None


def show_date(iso) -> str:
    return dt.date.fromisoformat(iso).strftime("%d-%m-%Y") if iso else ""


class _Row(QWidget):
    changed = Signal()
    remove = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)

    def _combo(self, items: list[tuple[str, object]], current=None, name: str = "") -> QComboBox:
        cb = QComboBox(self)
        cb.setAccessibleName(name)
        for label, data in items:
            cb.addItem(label, data)
        if current is not None:
            i = cb.findData(current)
            if i >= 0:
                cb.setCurrentIndex(i)
        return cb

    def _remove_button(self, what: str):
        b = icon_button("close", f"Remove {what}", self)
        b.clicked.connect(lambda: self.remove.emit(self))
        return b


class FilterRow(_Row):
    def __init__(self, columns: list[Column], output: bool, f: Filter | None = None, parent=None):
        super().__init__(parent)
        self.columns = {c.id: c for c in columns}
        self.output = output
        self.column = self._combo([(c.name, c.id) for c in columns], f.column_id if f else None, "Filter column")
        self.op = QComboBox(self)
        self.op.setAccessibleName("Filter condition")
        self.values = QWidget(self)
        self.values_lay = QHBoxLayout(self.values)
        self.values_lay.setContentsMargins(0, 0, 0, 0)
        self.values_lay.setSpacing(6)
        self.lay.addWidget(self.column, 3)
        self.lay.addWidget(self.op, 3)
        self.lay.addWidget(self.values, 4)
        self.lay.addWidget(self._remove_button("filter"))
        self.edits: list[QWidget] = []
        self._fill_ops(f.op if f else None)
        self._fill_values(f.values if f else [])
        self.column.currentIndexChanged.connect(self._column_changed)
        self.op.currentIndexChanged.connect(lambda _i: (self._fill_values([]), self.changed.emit()))

    @property
    def col(self) -> Column:
        return self.columns[self.column.currentData()]

    def _column_changed(self, _i) -> None:
        self._fill_ops(None)
        self._fill_values([])
        self.changed.emit()

    def _fill_ops(self, current) -> None:
        with QSignalBlocker(self.op):
            self.op.clear()
            for o in ops_for(self.col, self.output):
                self.op.addItem(OP_LABELS[o], o)
            i = self.op.findData(current)
            self.op.setCurrentIndex(i if i >= 0 else 0)

    def _line(self, text: str = "", placeholder: str = "") -> QLineEdit:
        e = QLineEdit(text, self.values)
        e.setPlaceholderText(placeholder)
        e.setAccessibleName(placeholder or "Filter value")
        e.textEdited.connect(lambda _t: self.changed.emit())
        return e

    def _fill_values(self, values: list) -> None:
        for w in self.edits:
            self.values_lay.removeWidget(w)
            w.deleteLater()
        self.edits = []
        op, col = self.op.currentData(), self.col
        v = list(values or [])
        if op == d.ONE_OF:
            self.edits = [self._line(", ".join(str(x) for x in v), "Values, separated by commas")]
        elif op == d.CONTAINS:
            self.edits = [self._line(v[0] if v else "", "Text")]
        elif op == d.EQUALS:
            self.edits = [self._line(v[0] if v else "", "Number")]
        elif op == d.BETWEEN:
            a, b = (v + [None, None])[:2]
            if col.type == DATE:
                self.edits = [self._line(show_date(a), "From DD-MM-YYYY"), self._line(show_date(b), "To DD-MM-YYYY")]
            else:
                self.edits = [self._line(a or "", "From"), self._line(b or "", "To")]
        elif op in (d.YEAR, d.QUARTER, d.MONTH):
            year = QSpinBox(self.values)
            year.setRange(1900, 2999)
            year.setValue(int(v[0]) if v else dt.date.today().year)
            year.setAccessibleName("Year")
            year.valueChanged.connect(lambda _x: self.changed.emit())
            self.edits = [year]
            if op != d.YEAR:
                labels = [f"Q{i}" for i in range(1, 5)] if op == d.QUARTER else list(MONTH_NAMES)
                part = QComboBox(self.values)
                part.setAccessibleName("Quarter" if op == d.QUARTER else "Month")
                for i, lab in enumerate(labels, 1):
                    part.addItem(lab, i)
                if len(v) > 1:
                    part.setCurrentIndex(int(v[1]) - 1)
                part.currentIndexChanged.connect(lambda _x: self.changed.emit())
                self.edits.append(part)
        for w in self.edits:
            self.values_lay.addWidget(w, 1)
        self.values.setVisible(bool(self.edits))

    def value(self) -> Filter:
        op, col = self.op.currentData(), self.col
        e = self.edits
        if op == d.ONE_OF:
            values = [x.strip() for x in e[0].text().split(",") if x.strip()]
        elif op in (d.CONTAINS, d.EQUALS):
            values = [e[0].text().strip() if op == d.EQUALS else e[0].text()]
        elif op == d.BETWEEN:
            if col.type == DATE:
                values = [parse_typed_date(e[0].text()), parse_typed_date(e[1].text())]
            else:
                values = [e[0].text().strip() or None, e[1].text().strip() or None]
        elif op == d.YEAR:
            values = [e[0].value()]
        elif op in (d.QUARTER, d.MONTH):
            values = [e[0].value(), e[1].currentData()]
        else:
            values = []
        return Filter(col.id, op, values)


class GroupRow(_Row):
    move = Signal(object, int)

    def __init__(self, columns: list[Column], g: Group | None = None, parent=None):
        super().__init__(parent)
        self.columns = {c.id: c for c in columns}
        self.number = QLabel("1", self)
        self.number.setFixedWidth(16)
        self.number.setProperty("kind", "small")
        self.column = self._combo([(c.name, c.id) for c in columns], g.column_id if g else None, "Group by column")
        self.grain = self._combo([(v, k) for k, v in GRAIN_LABELS.items()], (g.grain or "day") if g else "month",
                                 "Date grouping")
        self.lay.addWidget(self.number)
        self.lay.addWidget(self.column, 3)
        self.lay.addWidget(self.grain, 2)
        up = icon_button("up", "Move level up", self)
        down = icon_button("down", "Move level down", self)
        up.clicked.connect(lambda: self.move.emit(self, -1))
        down.clicked.connect(lambda: self.move.emit(self, 1))
        self.lay.addWidget(up)
        self.lay.addWidget(down)
        self.lay.addWidget(self._remove_button("level"))
        self._grain_visible()
        self.column.currentIndexChanged.connect(lambda _i: (self._grain_visible(), self.changed.emit()))
        self.grain.currentIndexChanged.connect(lambda _i: self.changed.emit())

    def _grain_visible(self) -> None:
        self.grain.setVisible(self.columns[self.column.currentData()].type == DATE)

    def value(self) -> Group:
        col = self.columns[self.column.currentData()]
        if col.type != DATE:
            return Group(col.id)
        grain = self.grain.currentData()
        return Group(col.id, None if grain == "day" else grain)


class MeasureRow(_Row):
    def __init__(self, columns: list[Column], m: Measure | None = None, parent=None):
        super().__init__(parent)
        self.choices = measure_choices(columns)
        self.measure = QComboBox(self)
        self.measure.setAccessibleName("Measure")
        for _fn, _cid, label in self.choices:
            self.measure.addItem(label)
        if m is not None:
            for i, (fn, cid, _label) in enumerate(self.choices):
                if (fn, cid) == (m.fn, m.column_id):
                    self.measure.setCurrentIndex(i)
                    break
        self.label = QLineEdit(m.label or "" if m else "", self)
        self.label.setAccessibleName("Measure name")
        self._placeholder()
        as_ = QLabel("as", self)
        as_.setProperty("kind", "small")
        self.lay.addWidget(self.measure, 4)
        self.lay.addWidget(as_)
        self.lay.addWidget(self.label, 3)
        self.lay.addWidget(self._remove_button("measure"))
        self.measure.currentIndexChanged.connect(lambda _i: (self._placeholder(), self.changed.emit()))
        self.label.textEdited.connect(lambda _t: self.changed.emit())

    def _placeholder(self) -> None:
        self.label.setPlaceholderText(self.measure.currentText())

    def value(self) -> Measure:
        fn, cid, _label = self.choices[self.measure.currentIndex()]
        return Measure(cid, fn, self.label.text().strip() or None)


class _Section(QWidget):
    def __init__(self, title: str, add: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(heading(title, self, theme.GRID_TEXT_PX))
        head.addStretch(1)
        self.add = plus_button(add, self)
        head.addWidget(self.add)
        lay.addLayout(head)
        self.rows_lay = QVBoxLayout()
        self.rows_lay.setSpacing(8)
        lay.addLayout(self.rows_lay)
        self.rows: list[_Row] = []


class DefinitionBuilder(QWidget):
    changed = Signal()

    def __init__(self, columns: list[Column], *, output: bool = False, parent=None):
        super().__init__(parent)
        self.output = output
        self.columns = [c for c in columns if not c.removed]
        self.template_id = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)
        self.filters = _Section("Filters (all must match)", "Add filter", self)
        self.groups = _Section("Group by", "Add level", self)
        self.measures = _Section("Measures", "Add measure", self)
        for s in (self.filters, self.groups, self.measures):
            lay.addWidget(s)
        self.subtotals = QCheckBox("Show subtotals", self)
        self.subtotals.toggled.connect(lambda _b: self.changed.emit())
        lay.addWidget(self.subtotals)
        lay.addStretch(1)
        self.filters.add.clicked.connect(lambda: self.add_filter())
        self.groups.add.clicked.connect(lambda: self.add_group())
        self.measures.add.clicked.connect(lambda: self.add_measure())

    # ------------------------------------------------------------------------------------------ rows
    def _add(self, section: _Section, row: _Row) -> _Row:
        section.rows.append(row)
        section.rows_lay.addWidget(row)
        row.changed.connect(self.changed)
        row.remove.connect(lambda r, s=section: self._remove(s, r))
        if isinstance(row, GroupRow):
            row.move.connect(self._move_group)
        self._number()
        return row

    def _remove(self, section: _Section, row: _Row) -> None:
        section.rows.remove(row)
        section.rows_lay.removeWidget(row)
        row.deleteLater()
        self._number()
        self.changed.emit()

    def _move_group(self, row: GroupRow, step: int) -> None:
        rows = self.groups.rows
        i = rows.index(row)
        j = i + step
        if not 0 <= j < len(rows):
            return
        rows[i], rows[j] = rows[j], rows[i]
        self.groups.rows_lay.removeWidget(row)
        self.groups.rows_lay.insertWidget(j, row)
        self._number()
        self.changed.emit()

    def _number(self) -> None:
        for i, r in enumerate(self.groups.rows, 1):
            r.number.setText(str(i))

    def add_filter(self, f: Filter | None = None, emit: bool = True) -> FilterRow:
        row = self._add(self.filters, FilterRow(self.columns, self.output, f, self))
        if emit:
            self.changed.emit()
        return row

    def add_group(self, g: Group | None = None, emit: bool = True) -> GroupRow:
        row = self._add(self.groups, GroupRow(self.columns, g, self))
        if emit:
            self.changed.emit()
        return row

    def add_measure(self, m: Measure | None = None, emit: bool = True) -> MeasureRow:
        row = self._add(self.measures, MeasureRow(self.columns, m, self))
        if emit:
            self.changed.emit()
        return row

    # ------------------------------------------------------------------------------------------ value
    def clear(self) -> None:
        for s in (self.filters, self.groups, self.measures):
            for r in list(s.rows):
                s.rows_lay.removeWidget(r)
                r.deleteLater()
            s.rows = []

    def set_definition(self, definition: Definition, columns: list[Column] | None = None) -> None:
        if columns is not None:
            self.columns = [c for c in columns if not c.removed]
        self.template_id = definition.template_id
        with QSignalBlocker(self):
            self.clear()
            for f in definition.filters:
                self.add_filter(f, emit=False)
            for g in definition.groups:
                self.add_group(g, emit=False)
            for m in definition.measures:
                self.add_measure(m, emit=False)
            self.subtotals.setChecked(definition.subtotals)

    def definition(self) -> Definition:
        """The settings as a definition. Raises ``DefinitionError`` for a value that can't be read (a date)."""
        return Definition(self.template_id, [r.value() for r in self.filters.rows],
                          [r.value() for r in self.groups.rows], [r.value() for r in self.measures.rows],
                          self.subtotals.isChecked())

    def summary(self) -> str:
        """"2 groups · 3 measures" for the outputs list."""
        from sankalan.formats import count
        return f"{count(len(self.groups.rows), 'group')} · {count(len(self.measures.rows), 'measure')}"


def definition_summary(definition: dict) -> str:
    from sankalan.formats import count
    return (f"{count(len(definition.get('groups') or []), 'group')} · "
            f"{count(len(definition.get('measures') or []), 'measure')}")


NEW_OUTPUT = Definition("", [], [], [Measure(None, d.COUNT, None)], False)
