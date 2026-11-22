"""Result headers (Feature Spec A2 MEA-7, MEA-8, P3; Tech spec A2 9.3)."""
import copy

from conftest import spec, tpl_a_columns
from sankalan.model import definition as d
from sankalan.model.definition import Definition, Group, MeasureCard, Op
from sankalan.query.headers import hover_texts, rename_problem, resolve_headers

INV, DATE_, CUST, GSTIN, STATE, TAXABLE = "c001", "c002", "c003", "c004", "c005", "c006"


def cols(**renames):
    out = copy.deepcopy(tpl_a_columns())
    for c in out:
        if c.id in renames:
            c.name = renames[c.id]
    return out


@spec("AC-MEA-7", "MEA-7")
def test_default_names_exact():
    x = Definition("t", [], [Group(STATE)], [MeasureCard(TAXABLE, [Op(d.SUM)]), MeasureCard(INV, [Op(d.COUNT_DISTINCT)]),
                                             MeasureCard(d.ROWS, [Op(d.COUNT)])])
    assert resolve_headers(x, cols()) == ["State", "Taxable Value · Sum", "Invoice No · Count distinct", "Rows · Count"]
    t = MeasureCard(TAXABLE, [Op(f) for f in (d.SUM, d.COUNT, d.AVG, d.MIN, d.MAX)])
    assert resolve_headers(Definition("t", [], [], [t]), cols()) == [
        "Taxable Value · Sum", "Taxable Value · Count", "Taxable Value · Average", "Taxable Value · Min",
        "Taxable Value · Max"]


@spec("AC-MEA-7", "MEA-7")
def test_default_follows_column_rename_custom_does_not():
    x = Definition("t", [], [], [MeasureCard(TAXABLE, [Op(d.SUM), Op(d.MAX, "Biggest")])])
    assert resolve_headers(x, cols()) == ["Taxable Value · Sum", "Biggest"]
    assert resolve_headers(x, cols(c006="Taxable Amt")) == ["Taxable Amt · Sum", "Biggest"]
    assert hover_texts(x, cols(c006="Taxable Amt")) == ["Taxable Amt · Sum", "Taxable Amt · Max"]


@spec("P3", "MEA-7")
def test_clashes_place_groups_and_custom_names_first():
    # a custom name equal to a later default: the default gets " (2)"; one more taken name gives " (3)"
    x = Definition("t", [], [Group(DATE_, "month"), Group(DATE_, "year")],
                   [MeasureCard(TAXABLE, [Op(d.SUM, "Invoice No · Count"), Op(d.MAX, "invoice no · count (2)")]),
                    MeasureCard(INV, [Op(d.COUNT)]), MeasureCard(d.ROWS, [Op(d.COUNT, "Rows")])])
    assert resolve_headers(x, cols()) == ["Invoice Date", "Invoice Date (2)", "Invoice No · Count",
                                          "invoice no · count (2)", "Invoice No · Count (3)", "Rows"]
    # a default equal to a group header (columns renamed so they meet)
    z =Definition("t", [], [Group(STATE)], [MeasureCard(CUST, [Op(d.COUNT)])])
    assert resolve_headers(z, cols(c003="State", c005="State · Count")) == ["State · Count", "State · Count (2)"]


@spec("T23", "9.3")
def test_removed_columns():
    c = cols()
    next(x for x in c if x.id == GSTIN).removed = True
    x = Definition("t", [], [Group(GSTIN)], [MeasureCard(GSTIN, [Op(d.COUNT_DISTINCT)])])
    assert resolve_headers(x, c) == ["GSTIN (removed)", "GSTIN (removed) · Count distinct"]


@spec("AC-MEA-8", "MEA-8")
def test_rename_problem():
    headers = ["State", "Invoices", "Taxable Value · Sum"]
    assert rename_problem(headers, 2, "invoices") == "Another column is already called invoices"
    assert rename_problem(headers, 2, "STATE") == "Another column is already called STATE"
    assert rename_problem(headers, 1, "invoices") is None          # its own name, other case
    assert rename_problem(headers, 2, None) is None                # blank: back to the default
    assert rename_problem(headers, 2, "x" * 101) is not None
    assert rename_problem(headers, 2, "Taxable value") is None
