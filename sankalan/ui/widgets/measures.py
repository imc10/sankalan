"""The Measures section (Feature Spec A2 3.1, 3.2; Tech spec A2 9.6): measures picked by column.

- ``MeasuresSection``: "Measures" with "+ Add column"; the cards; the note under them; the empty text. Emits
  ``changed`` on add, remove, move and tick.
- ``MeasureCardWidget``: a bordered card: name, type, ↑ ↓ ✕, then one chip per operation that fits the type (MEA-3),
  and an error line under the card (MEA-4).
- ``OpChip``: a checkable pill; its tooltip is the full name ("Count distinct", "Average").
- ``AddColumnPopup``: Rows first, then the columns not yet used, in template order, each with its type; a search box
  when the template has more than 12 columns (MEA-1).

A card keeps each ticked op's custom name (set from a result header, MEA-8) while it stays ticked; unticking drops
the name, and ticking again starts from the default (MEA-9).
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from sankalan.model import definition as d
from sankalan.model.definition import MeasureCard, Op
from sankalan.model.template import Column
from sankalan.ui import theme
from sankalan.ui.widgets.controls import SearchBox, heading, icon_button, note, plus_button

NOTE = "Results show each column's ticked operations together, in this order. Rename a result column from its header."
EMPTY = "No measures. Add a column, or Rows to count rows."
ROW_PX = 30
SEARCH_FROM = 12            # a search box when the template has more columns than this


def type_text(column_id: str, columns: dict[str, Column]) -> str:
    if column_id == d.ROWS:
        return d.ROWS_TYPE
    col = columns.get(column_id)
    return col.type if col is not None else ""


class OpChip(QPushButton):
    def __init__(self, fn: str, parent=None):
        super().__init__(d.CHIP_NAMES[fn], parent)
        self.fn = fn
        self.setCheckable(True)
        self.setProperty("kind", "op")
        self.setFixedHeight(26)
        self.setToolTip(d.FN_NAMES[fn])
        self.setAccessibleName(d.FN_NAMES[fn])
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class MeasureCardWidget(QWidget):
    changed = Signal()
    remove = Signal(object)
    move = Signal(object, int)

    def __init__(self, column_id: str, columns: dict[str, Column], ops: list[Op] | None = None, parent=None):
        super().__init__(parent)
        self.column_id = column_id
        self.names: dict[str, str | None] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        self.frame = QFrame(self)
        self.frame.setObjectName("MeasureCard")
        outer.addWidget(self.frame)
        lay = QVBoxLayout(self.frame)
        lay.setContentsMargins(12, 6, 6, 10)
        lay.setSpacing(6)
        line = QHBoxLayout()
        line.setSpacing(8)
        self.name = QLabel(d.card_name(column_id, columns), self.frame)
        self.name.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; font-weight: 500; color: {theme.TEXT}; "
                                f"border: 0;")
        self.type = QLabel(type_text(column_id, columns), self.frame)
        self.type.setStyleSheet(f"font-size: {theme.SMALL_PX}px; color: {theme.MUTED}; border: 0;")
        line.addWidget(self.name)
        line.addWidget(self.type)
        line.addStretch(1)
        self.up = icon_button("up", "Move up", self.frame, 26)
        self.down = icon_button("down", "Move down", self.frame, 26)
        self.close = icon_button("close", f"Remove {self.name.text()}", self.frame, 26)
        self.up.clicked.connect(lambda: self.move.emit(self, -1))
        self.down.clicked.connect(lambda: self.move.emit(self, 1))
        self.close.clicked.connect(lambda: self.remove.emit(self))
        for b in (self.up, self.down, self.close):
            line.addWidget(b)
        lay.addLayout(line)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chips: dict[str, OpChip] = {}
        for fn in d.card_ops(column_id, columns):
            chip = OpChip(fn, self.frame)
            chip.toggled.connect(lambda on, f=fn: self._toggled(f, on))
            self.chips[fn] = chip
            chips.addWidget(chip)
        chips.addStretch(1)
        lay.addLayout(chips)
        self.error = QLabel("", self)
        self.error.setProperty("kind", "error")
        self.error.setWordWrap(True)
        self.error.hide()
        outer.addWidget(self.error)
        for o in ops or []:
            if o.fn in self.chips:
                self.chips[o.fn].blockSignals(True)
                self.chips[o.fn].setChecked(True)
                self.chips[o.fn].blockSignals(False)
                self.names[o.fn] = o.name

    def _toggled(self, fn: str, on: bool) -> None:
        if on:
            self.names[fn] = None               # ticked again: the default name (MEA-9)
        else:
            self.names.pop(fn, None)
        self.show_error(None)
        self.changed.emit()

    def tick(self, fn: str, on: bool = True) -> None:
        self.chips[fn].setChecked(on)

    def ticked(self) -> list[str]:
        return [fn for fn in d.MEASURE_FNS if fn in self.chips and self.chips[fn].isChecked()]

    def card(self) -> MeasureCard:
        return MeasureCard(self.column_id, [Op(fn, self.names.get(fn)) for fn in self.ticked()])

    def show_error(self, message: str | None) -> None:
        self.error.setText(message or "")
        self.error.setVisible(bool(message))
        self.frame.setProperty("error", "true" if message else "false")
        self.frame.style().unpolish(self.frame)
        self.frame.style().polish(self.frame)


class AddColumnPopup(QFrame):
    """The + Add column list (MEA-1)."""
    picked = Signal(str)

    def __init__(self, choices: list[tuple[str, str, str]], search: bool, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)     # closed by a pick, Esc or a click outside
        self.setObjectName("AddColumnPopup")
        self.setStyleSheet(f"#AddColumnPopup {{ background: {theme.WHITE}; border: 1px solid {theme.BORDER}; "
                           f"border-radius: 6px; }}")
        self.choices = choices          # (column id, name, type)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        self.search = None
        if search:
            self.search = SearchBox("Search columns", self, 260)
            self.search.textChanged.connect(self._filter)
            lay.addWidget(self.search)
        self.list = QListWidget(self)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setAccessibleName("Columns")
        for cid, name, typ in choices:
            item = QListWidgetItem("")
            item.setData(Qt.ItemDataRole.UserRole, cid)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{name}, {typ}")
            item.setSizeHint(QSize(0, ROW_PX))
            self.list.addItem(item)
            row = QWidget(self.list)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 0, 8, 0)
            rl.setSpacing(8)
            n = QLabel(name, row)
            n.setStyleSheet(f"font-size: {theme.GRID_TEXT_PX}px; color: {theme.TEXT};")
            t = QLabel(typ, row)
            t.setStyleSheet(f"font-size: {theme.SMALL_PX}px; color: {theme.MUTED};")
            rl.addWidget(n, 1)
            rl.addWidget(t)
            self.list.setItemWidget(item, row)
        self.list.itemClicked.connect(lambda it: self.pick(it.data(Qt.ItemDataRole.UserRole)))
        self.list.itemActivated.connect(lambda it: self.pick(it.data(Qt.ItemDataRole.UserRole)))
        lay.addWidget(self.list)
        rows = min(len(choices), 10)
        self.list.setFixedHeight(max(1, rows) * ROW_PX + 4)
        self.setFixedWidth(300)

    def items(self) -> list[str]:
        """The column IDs listed (visible ones), in order."""
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if not self.list.item(i).isHidden()]

    def text(self, row: int) -> str:
        """Name and type of a listed row (tests)."""
        return self.list.item(row).data(Qt.ItemDataRole.AccessibleTextRole)

    def _filter(self, text: str) -> None:
        t = text.strip().lower()
        for i, (_cid, name, _typ) in enumerate(self.choices):
            self.list.item(i).setHidden(bool(t) and t not in name.lower())

    def pick(self, column_id: str) -> None:
        self.picked.emit(column_id)
        self.close()


class MeasuresSection(QWidget):
    changed = Signal()

    def __init__(self, columns: list[Column], parent=None):
        super().__init__(parent)
        self.columns = list(columns)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(heading("Measures", self, theme.GRID_TEXT_PX))
        head.addStretch(1)
        self.add = plus_button("Add column", self)
        self.add.clicked.connect(self.open_popup)
        head.addWidget(self.add)
        lay.addLayout(head)
        self.cards_lay = QVBoxLayout()
        self.cards_lay.setSpacing(8)
        lay.addLayout(self.cards_lay)
        self.note = note(NOTE, self)
        self.empty = note(EMPTY, self)
        self.error = QLabel("", self)
        self.error.setProperty("kind", "error")
        self.error.setWordWrap(True)
        self.error.hide()
        for w in (self.note, self.empty, self.error):
            lay.addWidget(w)
        self.cards: list[MeasureCardWidget] = []
        self.popup: AddColumnPopup | None = None
        self._update()

    @property
    def by_id(self) -> dict[str, Column]:
        return {c.id: c for c in self.columns}

    # ------------------------------------------------------------------------------------------ adding
    def choices(self) -> list[tuple[str, str, str]]:
        """Rows first, then the columns not used yet, in template order (MEA-1)."""
        used = {c.column_id for c in self.cards}
        out = [] if d.ROWS in used else [(d.ROWS, d.ROWS_NAME, d.ROWS_TYPE)]
        return out + [(c.id, c.name, c.type) for c in self.columns if c.id not in used]

    def open_popup(self) -> AddColumnPopup:
        if self.popup is not None:                  # one list at a time
            self.popup.close()
        self.popup = AddColumnPopup(self.choices(), len(self.columns) > SEARCH_FROM, self)
        self.popup.picked.connect(self._picked)
        self.popup.destroyed.connect(lambda _o=None, p=self.popup: self._popup_gone(p))
        pos = self.add.mapToGlobal(QPoint(self.add.width() - 300, self.add.height()))
        self.popup.move(pos)
        self.popup.show()
        if self.popup.search is not None:
            self.popup.search.setFocus()
        return self.popup

    def _popup_gone(self, popup) -> None:
        if self.popup is popup:
            self.popup = None

    def _picked(self, column_id: str) -> None:
        card = self.add_card(column_id)
        if column_id == d.ROWS:
            card.tick(d.COUNT)                 # Rows comes with Count ticked (MEA-10)
        self.changed.emit()

    def add_card(self, column_id: str, ops: list[Op] | None = None) -> MeasureCardWidget:
        card = MeasureCardWidget(column_id, self.by_id, ops, self)
        card.changed.connect(self._card_changed)
        card.remove.connect(self.remove_card)
        card.move.connect(self.move_card)
        self.cards.append(card)
        self.cards_lay.addWidget(card)
        card.show()
        self._update()
        return card

    def card_for(self, column_id: str) -> MeasureCardWidget | None:
        return next((c for c in self.cards if c.column_id == column_id), None)

    # ------------------------------------------------------------------------------------------ editing
    def _card_changed(self) -> None:
        self.clear_errors()
        self.changed.emit()

    def remove_card(self, card: MeasureCardWidget) -> None:
        self.cards.remove(card)
        self.cards_lay.removeWidget(card)
        card.deleteLater()
        self.clear_errors()
        self._update()
        self.changed.emit()

    def move_card(self, card: MeasureCardWidget, step: int) -> None:
        i = self.cards.index(card)
        j = i + step
        if not 0 <= j < len(self.cards):
            return
        self.cards[i], self.cards[j] = self.cards[j], self.cards[i]
        self.cards_lay.removeWidget(card)
        self.cards_lay.insertWidget(j, card)
        self._update()
        self.changed.emit()

    def clear(self) -> None:
        for c in self.cards:
            self.cards_lay.removeWidget(c)
            c.deleteLater()
        self.cards = []
        self.clear_errors()
        self._update()

    def set_cards(self, cards: list[MeasureCard], columns: list[Column] | None = None) -> None:
        if columns is not None:
            self.columns = list(columns)
        self.clear()
        for c in cards:
            self.add_card(c.column_id, c.ops)

    def value(self) -> list[MeasureCard]:
        return [c.card() for c in self.cards]

    def set_name(self, column_id: str, fn: str, name: str | None) -> None:
        """A rename from a result header (MEA-8): None restores the default."""
        card = self.card_for(column_id)
        if card is not None and fn in card.names:
            card.names[fn] = name

    # ------------------------------------------------------------------------------------------ checks
    def clear_errors(self) -> None:
        self.error.hide()
        for c in self.cards:
            c.show_error(None)

    def show_problem(self, where: str, index: int | None, message: str) -> None:
        """A check before Run, Save or Preview (Tech spec A2 9.2): under the section or under a card."""
        self.clear_errors()
        if where == "card" and index is not None and index < len(self.cards):
            target = self.cards[index]
            target.show_error(message)
        else:
            target = self.error
            self.error.setText(message)
            self.error.show()
        scroll = self.parentWidget()
        while scroll is not None and not isinstance(scroll, QScrollArea):
            scroll = scroll.parentWidget()
        if scroll is not None:                      # the message may be below the fold (Run is under the panel)
            scroll.ensureWidgetVisible(target, 0, 48)

    def _update(self) -> None:
        n = len(self.cards)
        self.note.setVisible(n > 0)
        self.empty.setVisible(n == 0)
        for i, c in enumerate(self.cards):
            c.up.setEnabled(i > 0)
            c.down.setEnabled(i < n - 1)
        self.add.setEnabled(bool(self.choices()))
