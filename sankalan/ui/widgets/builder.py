"""The analysis builder (ANA-4, ANA-5, DO-1, DO-3, MEA-1 to MEA-11): AND filters, group levels and the Measures
section (cards, ``measures.MeasuresSection``), plus Show subtotals.

Shared by the template's Default outputs tab (3.2), the New template wizard (2.5, Phase 8) and the Analysis screen
(6.2, Phase 10). With ``output=True`` date filters are relative only (latest month, quarter or year in the run) or
Blank / Not blank (DO-3, C3-19). Columns are referenced by stable ID (V3-2).

Is one of: on the Analysis screen (a ``picker`` is given) the values are chosen from the 1,000 most frequent values
with their counts, plus a search across the whole column (ANA-4, ``ValuesDialog``). Default outputs have no runs
ticked to read values from, so there the values are typed, separated by commas.
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from sankalan.model import definition as d
from sankalan.model.definition import Definition, Filter, FlatMeasure, Group, MeasureCard, Op
from sankalan.model.template import DATE, Column
from sankalan.ui import theme
from sankalan.ui.widgets.controls import heading, icon_button, plus_button
from sankalan.ui.widgets.measures import MeasureCardWidget, MeasuresSection

OP_LABELS = {
    d.LATEST_MONTH: "latest month in this run", d.LATEST_QUARTER: "latest quarter in this run",
    d.LATEST_YEAR: "latest year in this run", d.BLANK: "is blank", d.NOT_BLANK: "is not blank",
    d.ONE_OF: "is one of", d.CONTAINS: "contains", d.EQUALS: "equals", d.BETWEEN: "is between",
    d.YEAR: "year is", d.QUARTER: "quarter is", d.MONTH: "month is",
    d.NOT_NUMBER: "is not a number", d.NOT_DATE: "is not a date",
}
GRAIN_LABELS = {"day": "Day", "month": "Month", "quarter": "Quarter", "year": "Year"}
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")


def ops_for(column: Column, output: bool) -> list[str]:
    if column.type == DATE:
        return list(d.OUTPUT_DATE_OPS) if output else [o for o in d.FILTER_OPS[DATE] if o not in d.RELATIVE]
    return list(d.FILTER_OPS[column.type])


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


def narrow(cb: QComboBox, chars: int = 3) -> None:
    """A combo box whose minimum width doesn't follow its longest item, so a filter or group row fits the 380 px
    settings panel (FIT-04); the open list still shows whole items."""
    cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    cb.setMinimumContentsLength(chars)


class ElidedButton(QPushButton):
    """A button whose text is cut with an ellipsis to its width, so long picks ("Maharashtra, Gujarat and 2
    more") don't widen the 380 px settings panel (FIT-04). ``text()`` is the whole text."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(64)
        self.setStyleSheet("text-align: left; padding-left: 10px; padding-right: 10px;")
        self._full = ""
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        self._elide()

    def text(self) -> str:
        return self._full

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        width = max(0, self.width() - 22)
        super().setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, width))


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
        narrow(cb)
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


def picked_text(values: list[str]) -> str:
    """The Is one of button: "Choose values…", "B2B", "B2B, B2C", "Delhi, Goa and 3 more"."""
    if not values:
        return "Choose values…"
    if len(values) <= 2:
        return ", ".join(values)
    return f"{values[0]}, {values[1]} and {len(values) - 2} more"


class FilterRow(_Row):
    def __init__(self, columns: list[Column], output: bool, f: Filter | None = None, parent=None, picker=None):
        super().__init__(parent)
        self.columns = {c.id: c for c in columns}
        self.output = output
        self.picker = picker                # fn(row): opens the value picker (Analysis screen)
        self.picked: list[str] = list(f.values) if f is not None and f.op == d.ONE_OF else []
        self.column = self._combo([(c.name, c.id) for c in columns], f.column_id if f else None, "Filter column")
        self.op = QComboBox(self)
        self.op.setAccessibleName("Filter condition")
        narrow(self.op, 8)                          # "is one of" stays whole
        self.help = QLabel("", self)                 # the op's help text, under the op picker (Tech spec A2 5.8)
        self.help.setProperty("kind", "small")
        self.help.setWordWrap(True)
        self.help.hide()
        self.values = QWidget(self)
        self.values_lay = QHBoxLayout(self.values)
        self.values_lay.setContentsMargins(0, 0, 0, 0)
        self.values_lay.setSpacing(6)
        # a grid inside the row: the pickers on the first line, the help text on its own line under the op picker
        # (spanning the value column too, which these ops leave empty)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        grid.addWidget(self.column, 0, 0)
        grid.addWidget(self.op, 0, 1)
        grid.addWidget(self.values, 0, 2)
        grid.addWidget(self._remove_button("filter"), 0, 3)
        grid.addWidget(self.help, 1, 1, 1, 2)
        for col, stretch in ((0, 3), (1, 3), (2, 4)):
            grid.setColumnStretch(col, stretch)
        self.lay.addLayout(grid)
        self.edits: list[QWidget] = []
        self._fill_ops(f.op if f else None)
        self._fill_values(f.values if f else [])
        self.column.currentIndexChanged.connect(self._column_changed)
        self.op.currentIndexChanged.connect(lambda _i: (self._show_help(), self._fill_values([]),
                                                        self.changed.emit()))

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
                if o in d.FILTER_HELP:
                    self.op.setItemData(self.op.count() - 1, d.FILTER_HELP[o], Qt.ItemDataRole.ToolTipRole)
            i = self.op.findData(current)
            self.op.setCurrentIndex(i if i >= 0 else 0)
        self._show_help()

    def _show_help(self) -> None:
        text = d.FILTER_HELP.get(self.op.currentData(), "")
        self.help.setText(text)
        self.help.setVisible(bool(text))

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
        if op == d.ONE_OF and self.picker is not None:
            self.picked = [str(x) for x in v]
            b = ElidedButton(picked_text(self.picked), self.values)
            b.setAccessibleName("Choose values")
            b.setToolTip(", ".join(self.picked))
            b.clicked.connect(lambda: self.picker(self))
            self.edits = [b]
        elif op == d.ONE_OF:
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

    def set_picked(self, values: list[str]) -> None:
        """The values chosen in the picker."""
        self.picked = list(values)
        if self.edits and isinstance(self.edits[0], QPushButton):
            self.edits[0].setText(picked_text(self.picked))
            self.edits[0].setToolTip(", ".join(self.picked))
        self.changed.emit()

    def value(self) -> Filter:
        op, col = self.op.currentData(), self.col
        e = self.edits
        if op == d.ONE_OF and self.picker is not None:
            values = list(self.picked)
        elif op == d.ONE_OF:
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

    def __init__(self, columns: list[Column], *, output: bool = False, parent=None, picker=None):
        super().__init__(parent)
        self.output = output
        self.picker = picker
        self.columns = [c for c in columns if not c.removed]
        self.template_id = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)
        self.filters = _Section("Filters (all must match)", "Add filter", self)
        self.groups = _Section("Group by", "Add level", self)
        self.measures = MeasuresSection(self.columns, self)
        self.measures.changed.connect(self._measures_changed)
        for s in (self.filters, self.groups, self.measures):
            lay.addWidget(s)
        self.subtotals = QCheckBox("Show subtotals", self)
        self.subtotals.toggled.connect(lambda _b: self.changed.emit())
        lay.addWidget(self.subtotals)
        lay.addStretch(1)
        self.filters.add.clicked.connect(lambda: self.add_filter())
        self.groups.add.clicked.connect(lambda: self.add_group())
        self._subtotals_enabled()

    def _measures_changed(self) -> None:
        self._subtotals_enabled()
        self.changed.emit()

    def _subtotals_enabled(self) -> None:
        """No measures, no subtotal rows (MEA-11, T39): Show subtotals is disabled."""
        on = bool(self.measures.cards)
        self.subtotals.setEnabled(on)
        self.subtotals.setToolTip("" if on else "Add a measure to show subtotals")

    def set_sections(self, *, filters: bool = True, groups: bool = True, measures: bool = True,
                     subtotals: bool = True) -> None:
        """Which sections show (the Rows view shows filters only, A2-5)."""
        self.filters.setVisible(filters)
        self.groups.setVisible(groups)
        self.measures.setVisible(measures)
        self.subtotals.setVisible(subtotals)

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
        self.measures.clear_errors()
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
        row = self._add(self.filters, FilterRow(self.columns, self.output, f, self, self.picker))
        if emit:
            self.changed.emit()
        return row

    def add_group(self, g: Group | None = None, emit: bool = True) -> GroupRow:
        row = self._add(self.groups, GroupRow(self.columns, g, self))
        self.measures.clear_errors()
        if emit:
            self.changed.emit()
        return row

    def add_card(self, column_id: str, fns: tuple[str, ...] = (), emit: bool = True) -> MeasureCardWidget:
        """A measure card with ``fns`` ticked (as + Add column, then ticking chips)."""
        card = self.measures.add_card(column_id, [Op(fn) for fn in fns])
        self._subtotals_enabled()
        if emit:
            self.changed.emit()
        return card

    def add_measure(self, m: FlatMeasure, emit: bool = True) -> MeasureCardWidget:
        """Tick one operation (with its name), adding the column's card when it has none."""
        card = self.measures.card_for(m.column_id) or self.measures.add_card(m.column_id)
        card.chips[m.fn].blockSignals(True)
        card.chips[m.fn].setChecked(True)
        card.chips[m.fn].blockSignals(False)
        card.names[m.fn] = m.name
        self._subtotals_enabled()
        if emit:
            self.changed.emit()
        return card

    # ------------------------------------------------------------------------------------------ value
    def clear(self) -> None:
        for s in (self.filters, self.groups):
            for r in list(s.rows):
                s.rows_lay.removeWidget(r)
                r.deleteLater()
            s.rows = []
        self.measures.clear()
        self._subtotals_enabled()

    def set_definition(self, definition: Definition, columns: list[Column] | None = None) -> None:
        if columns is not None:
            self.columns = [c for c in columns if not c.removed]
            self.measures.columns = list(self.columns)
        self.template_id = definition.template_id
        with QSignalBlocker(self):
            self.clear()
            for f in definition.filters:
                self.add_filter(f, emit=False)
            for g in definition.groups:
                self.add_group(g, emit=False)
            with QSignalBlocker(self.measures):
                self.measures.set_cards(definition.measures)
            self._subtotals_enabled()
            self.subtotals.setChecked(definition.subtotals)

    def definition(self) -> Definition:
        """The settings as a definition. Raises ``DefinitionError`` for a value that can't be read (a date)."""
        return Definition(self.template_id, [r.value() for r in self.filters.rows],
                          [r.value() for r in self.groups.rows], self.measures.value(),
                          self.subtotals.isChecked())

    def problem(self) -> tuple[str, int | None, str] | None:
        """Checks 3 and 4 (Tech spec A2 9.2), shown under their section; None when there is none."""
        try:
            defn = self.definition()
        except d.DefinitionError:
            return None
        p = d.first_problem(defn, self.columns)
        if p is not None:
            self.measures.show_problem(*p)
        return p

    def rename(self, flat_index: int, name: str | None) -> None:
        """A result header renamed (MEA-8): the name goes with the op while it stays ticked."""
        flat = d.flat_measures(self.definition())
        if 0 <= flat_index < len(flat):
            m = flat[flat_index]
            self.measures.set_name(m.column_id, m.fn, name)

    def summary(self) -> str:
        """"2 groups · 3 measures" for the outputs list."""
        return _summary(len(self.groups.rows), sum(len(c.ticked()) for c in self.measures.cards))


def _summary(groups: int, measures: int) -> str:
    from sankalan.formats import count
    return f"{count(groups, 'group')} · {count(measures, 'measure')}"


def definition_summary(definition: dict) -> str:
    return _summary(len(definition.get("groups") or []),
                    sum(len(c.get("ops") or []) for c in definition.get("measures") or []))


NEW_OUTPUT = Definition("", [], [], [MeasureCard(d.ROWS, [Op(d.COUNT)])], False)
