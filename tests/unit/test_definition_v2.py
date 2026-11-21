"""Version-2 measure definitions (Feature Spec A2 3.1, 8.8, 8.9; Tech spec A2 T49, 9.1, 9.2)."""
import json

import pytest

from conftest import spec, tpl_a_columns
from sankalan.model import definition as d
from sankalan.model.definition import Definition, DefinitionError, Group, MeasureCard, Op

INV, DATE_, CUST, STATE, TAXABLE = "c001", "c002", "c003", "c005", "c006"
COLS = tpl_a_columns()


def defn(*cards_, groups=()):
    return Definition("t", [], [Group(g) for g in groups], list(cards_))


@spec("T49", "MEA-6", "8.8")
def test_round_trip_and_json_shape():
    x = defn(MeasureCard(d.ROWS, [Op(d.COUNT)]), MeasureCard(INV, [Op(d.COUNT, "Invoices")]),
             MeasureCard(TAXABLE, [Op(d.MAX), Op(d.SUM, "Taxable value")]), groups=(STATE,))
    out = x.to_dict()
    assert out["definition_version"] == 2
    assert out["measures"] == [
        {"column_id": "_rows", "ops": [{"fn": "count", "name": None}]},
        {"column_id": INV, "ops": [{"fn": "count", "name": "Invoices"}]},
        {"column_id": TAXABLE, "ops": [{"fn": "sum", "name": "Taxable value"}, {"fn": "max", "name": None}]}]
    back = Definition.from_dict(json.loads(json.dumps(out)))
    assert back.to_dict() == out
    assert [(m.column_id, m.fn, m.name) for m in d.flat_measures(back)] == [
        (d.ROWS, d.COUNT, None), (INV, d.COUNT, "Invoices"), (TAXABLE, d.SUM, "Taxable value"),
        (TAXABLE, d.MAX, None)]


@spec("T40", "T49")
def test_version_1_refused():
    v1 = {"template_id": "t", "filters": [], "groups": [],
          "measures": [{"column_id": None, "fn": "count", "label": None}], "subtotals": False}
    with pytest.raises(DefinitionError):
        Definition.from_dict(v1)
    with pytest.raises(DefinitionError):
        Definition.from_dict({**v1, "definition_version": 1})


@spec("MEA-6")
def test_ops_in_fixed_order():
    card = MeasureCard(TAXABLE, [Op(d.MAX), Op(d.MIN), Op(d.AVG), Op(d.COUNT), Op(d.SUM)])
    assert [o["fn"] for o in card.to_dict()["ops"]] == ["sum", "count", "avg", "min", "max"]
    assert [o.fn for o in card.sorted_ops()] == [d.SUM, d.COUNT, d.AVG, d.MIN, d.MAX]


@spec("MEA-3", "D70", "MEA-10")
def test_ops_by_type():
    assert d.card_ops(TAXABLE, {c.id: c for c in COLS}) == (d.SUM, d.COUNT, d.AVG, d.MIN, d.MAX)
    assert d.card_ops(DATE_, {c.id: c for c in COLS}) == (d.COUNT, d.COUNT_DISTINCT, d.MIN, d.MAX)
    assert d.card_ops(CUST, {c.id: c for c in COLS}) == (d.COUNT, d.COUNT_DISTINCT)
    assert d.card_ops(d.ROWS, {}) == (d.COUNT,)
    for good in (MeasureCard(TAXABLE, [Op(f) for f in (d.SUM, d.COUNT, d.AVG, d.MIN, d.MAX)]),
                 MeasureCard(DATE_, [Op(f) for f in (d.COUNT, d.COUNT_DISTINCT, d.MIN, d.MAX)]),
                 MeasureCard(CUST, [Op(d.COUNT), Op(d.COUNT_DISTINCT)]), MeasureCard(d.ROWS, [Op(d.COUNT)])):
        d.check(defn(good), COLS)
    for bad in (MeasureCard(TAXABLE, [Op(d.COUNT_DISTINCT)]), MeasureCard(DATE_, [Op(d.SUM)]),
                MeasureCard(CUST, [Op(d.MAX)]), MeasureCard(d.ROWS, [Op(d.SUM)]),
                MeasureCard(d.ROWS, [Op(d.COUNT_DISTINCT)]), MeasureCard("c099", [Op(d.COUNT)])):
        with pytest.raises(DefinitionError):
            d.check(defn(bad), COLS)


@spec("MEA-1", "9.2")
def test_duplicate_cards_and_ops_refused():
    for x in (defn(MeasureCard(INV, [Op(d.COUNT)]), MeasureCard(INV, [Op(d.COUNT_DISTINCT)])),
              defn(MeasureCard(d.ROWS, [Op(d.COUNT)]), MeasureCard(d.ROWS, [Op(d.COUNT)])),
              defn(MeasureCard(INV, [Op(d.COUNT), Op(d.COUNT)]))):
        with pytest.raises(DefinitionError):
            d.check(x, COLS)


@spec("MEA-8", "9.2")
def test_name_rules():
    def named(name, *more, groups=()):
        return defn(MeasureCard(INV, [Op(d.COUNT, name)]), *more, groups=groups)
    d.check(named("Invoices"), COLS)
    d.check(named("x" * 100), COLS)
    for bad in ("", " Invoices", "Invoices ", "x" * 101):
        with pytest.raises(DefinitionError):
            d.check(named(bad), COLS)
    with pytest.raises(DefinitionError, match="Another column is already called state"):
        d.check(named("state", groups=(STATE,)), COLS)           # a group header, ignoring case
    with pytest.raises(DefinitionError, match="Another column is already called invoices"):
        d.check(named("Invoices", MeasureCard(TAXABLE, [Op(d.SUM, "invoices")])), COLS)


@spec("MEA-4", "MEA-11", "T39", "9.2")
def test_screen_checks_in_order():
    assert d.first_problem(defn(), COLS) == ("measures", None, "Add a group level or a measure")
    assert d.first_problem(defn(groups=(STATE,)), COLS) is None                 # groups and no measures (MEA-11)
    d.check(defn(groups=(STATE,)), COLS)
    x = defn(MeasureCard(INV, [Op(d.COUNT)]), MeasureCard(TAXABLE, []), MeasureCard(d.ROWS, []))
    assert d.first_problem(x, COLS) == ("card", 1, "Tick at least one operation for Taxable Value, or remove it")
    with pytest.raises(DefinitionError, match="Tick at least one operation for Taxable Value"):
        d.check(x, COLS)
    assert d.first_problem(defn(MeasureCard(d.ROWS, [])), COLS)[2] == \
        "Tick at least one operation for Rows, or remove it"


@spec("T49")
def test_cards_from_flat_measures():
    got = d.cards(d.FlatMeasure(TAXABLE, d.MAX), d.FlatMeasure(INV, d.COUNT), d.FlatMeasure(TAXABLE, d.SUM, "T"))
    assert [(c.column_id, [(o.fn, o.name) for o in c.sorted_ops()]) for c in got] == [
        (TAXABLE, [(d.SUM, "T"), (d.MAX, None)]), (INV, [(d.COUNT, None)])]
