"""The Measures section (Feature Spec A2 3.1, 3.2; Tech spec A2 9.6) on the builder, without a window."""
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from conftest import spec, tpl_a_columns
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Group, MeasureCard, Op
from sankalan.model.template import Column
from sankalan.ui import theme
from sankalan.ui.widgets.builder import DefinitionBuilder
from sankalan.ui.widgets.measures import AddColumnPopup

INV, DATE_, CUST, GSTIN, STATE, TAXABLE = "c001", "c002", "c003", "c004", "c005", "c006"


@pytest.fixture(autouse=True)
def close_widgets(app):
    """Close every popup and builder a test made: a popup left open slows the GUI tests after this file."""
    yield
    for w in QApplication.topLevelWidgets():
        if isinstance(w, (AddColumnPopup, DefinitionBuilder)):
            w.close()
            w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def builder(cols=None):
    b = DefinitionBuilder(cols or tpl_a_columns())
    b.resize(380, 900)
    return b


def pick(b, column_id):
    popup = b.measures.open_popup()
    popup.pick(column_id)
    return b.measures.card_for(column_id)


@spec("AC-MEA-1", "MEA-1", "MEA-10")
def test_add_column_lists_rows_first_then_unused(app):
    b = builder()
    popup = b.measures.open_popup()
    assert popup.items() == [d.ROWS] + [c.id for c in tpl_a_columns()]
    assert popup.search is None                                     # 8 columns: no search box
    assert popup.text(0) == "Rows, All rows" and popup.text(1) == "Invoice No, Text"
    popup.pick(TAXABLE)
    card = b.measures.card_for(TAXABLE)
    assert card.ticked() == [] and card.type.text() == "Number"     # nothing ticked
    rows = pick(b, d.ROWS)
    assert rows.ticked() == [d.COUNT] and rows.type.text() == "All rows"      # Rows: Count ticked
    assert b.measures.open_popup().items() == [c.id for c in tpl_a_columns() if c.id != TAXABLE]
    b.measures.remove_card(rows)
    assert b.measures.open_popup().items()[0] == d.ROWS


@spec("AC-MEA-3", "MEA-3", "D70")
def test_chips_per_type_and_tooltips(app):
    b = builder()
    chips = {cid: pick(b, cid).chips for cid in (TAXABLE, DATE_, CUST, d.ROWS)}
    assert [c.text() for c in chips[TAXABLE].values()] == ["Sum", "Count", "Avg", "Min", "Max"]
    assert [c.text() for c in chips[DATE_].values()] == ["Count", "Distinct", "Min", "Max"]
    assert [c.text() for c in chips[CUST].values()] == ["Count", "Distinct"]
    assert [c.text() for c in chips[d.ROWS].values()] == ["Count"]
    assert chips[DATE_][d.COUNT_DISTINCT].toolTip() == "Count distinct"
    assert chips[TAXABLE][d.AVG].toolTip() == "Average"
    assert all(c.minimumHeight() == c.maximumHeight() == 26 for c in chips[TAXABLE].values())


@spec("MEA-4", "MEA-6", "MEA-9")
def test_ticking_order_names_and_moves(app):
    b = builder()
    inv = pick(b, INV)
    inv.tick(d.COUNT)
    tax = pick(b, TAXABLE)
    tax.tick(d.MAX)
    tax.tick(d.SUM)
    assert [(m.column_id, m.fn) for m in d.flat_measures(b.definition())] == [
        (INV, d.COUNT), (TAXABLE, d.SUM), (TAXABLE, d.MAX)]                       # Sum before Max (MEA-6)
    b.rename(1, "Taxable value")
    assert d.flat_measures(b.definition())[1].name == "Taxable value"
    tax.up.click()                                                                # the card moves with its ops
    assert [(m.column_id, m.fn, m.name) for m in d.flat_measures(b.definition())] == [
        (TAXABLE, d.SUM, "Taxable value"), (TAXABLE, d.MAX, None), (INV, d.COUNT, None)]
    assert not tax.up.isEnabled() and not inv.down.isEnabled()
    tax.tick(d.MIN)                                                               # another op keeps the name
    assert d.flat_measures(b.definition())[0].name == "Taxable value"
    tax.tick(d.SUM, False)
    tax.tick(d.SUM, True)                                                         # untick, re-tick: default
    assert d.flat_measures(b.definition())[0] == d.FlatMeasure(TAXABLE, d.SUM, None)
    assert b.summary() == "0 groups · 4 measures"


@spec("AC-MEA-4", "MEA-11", "9.2")
def test_checks_show_under_their_section(app):
    b = builder()
    assert b.problem() == ("measures", None, "Add a group level or a measure")
    assert b.measures.error.isVisibleTo(b) and b.measures.error.text() == "Add a group level or a measure"
    b.add_group(Group(STATE))
    assert not b.measures.error.isVisibleTo(b)                                     # an edit clears it
    assert b.problem() is None                                                     # groups, no measures: fine
    pick(b, INV).tick(d.COUNT)
    tax = pick(b, TAXABLE)
    assert b.problem() == ("card", 1, "Tick at least one operation for Taxable Value, or remove it")
    assert tax.error.isVisibleTo(b) and tax.frame.property("error") == "true"
    assert not b.measures.cards[0].error.isVisibleTo(b)
    tax.tick(d.SUM)
    assert not tax.error.isVisibleTo(b) and b.problem() is None


@spec("MEA-11", "T39")
def test_subtotals_disabled_without_measures(app):
    b = builder()
    b.add_group(Group(STATE))
    assert not b.subtotals.isEnabled()
    card = pick(b, d.ROWS)
    assert b.subtotals.isEnabled()
    b.measures.remove_card(card)
    assert not b.subtotals.isEnabled()


@spec("3.2")
def test_note_and_empty_text(app):
    b = builder()
    assert b.measures.empty.isVisibleTo(b) and not b.measures.note.isVisibleTo(b)
    assert b.measures.empty.text() == "No measures. Add a column, or Rows to count rows."
    pick(b, INV)
    assert not b.measures.empty.isVisibleTo(b) and b.measures.note.isVisibleTo(b)
    assert b.measures.note.text() == ("Results show each column's ticked operations together, in this order. "
                                      "Rename a result column from its header.")


@spec("MEA-1", "3.2")
def test_search_box_above_12_columns(app):
    cols = [Column(f"c{i:03d}", f"Column {i}") for i in range(1, 14)]
    b = builder(cols)
    popup = b.measures.open_popup()
    assert popup.search is not None and len(popup.items()) == 14
    popup.search.setText("column 1")
    assert popup.items() == ["c001", "c010", "c011", "c012", "c013"]
    popup.search.setText("")
    QTest.keyClick(popup.list, Qt.Key.Key_Escape)
    assert builder(cols[:12]).measures.open_popup().search is None


@spec("T49")
def test_set_definition_keeps_names(app):
    b = builder()
    x = Definition("t", [], [Group(STATE)], [MeasureCard(d.ROWS, [Op(d.COUNT, "Rows")]),
                                             MeasureCard(TAXABLE, [Op(d.MAX), Op(d.SUM, "Taxable")])], True)
    b.set_definition(x)
    assert b.definition().to_dict() == x.to_dict()
    assert [c.ticked() for c in b.measures.cards] == [[d.COUNT], [d.SUM, d.MAX]]


@spec("FIT-04", "3.2")
def test_four_cards_and_popup_fit(app):
    b = builder()
    for cid in (d.ROWS, INV, TAXABLE, DATE_):
        pick(b, cid).tick(d.COUNT)
    b.add_group(Group(STATE))
    hint = b.sizeHint()
    assert hint.width() <= 380 and hint.height() <= 900
    card = b.measures.cards[2]
    assert card.sizeHint().width() <= 380 - 2 * 16                       # Number: 5 chips on one line
    popup = b.measures.open_popup()
    assert popup.sizeHint().height() <= theme.MIN_LAYOUT.height() and popup.width() == 300
    popup.hide()
