"""Phase 7 helpers: name checks (C1-03, C1-04, C2-05), copy names (C2-06), figures, export prefill (C4-18), the
in-memory grid source, and the builder and rule dialog round trips."""
import pytest

from conftest import spec, tpl_a_columns
from sankalan import formats, manage
from sankalan.manage import NameRefused, check_name, copy_name
from sankalan.model import definition as d
from sankalan.model import export as ex
from sankalan.model.definition import Definition, Filter, Group, FlatMeasure, cards


@spec("C1-03", "C1-04", "C2-05")
def test_check_name():
    taken = {"a": "Acme Traders", "b": "Bharat Foods"}
    assert check_name("  Zenith Exports ", taken, what="client") == "Zenith Exports"
    for bad in ("", "   ", None):
        with pytest.raises(NameRefused, match="Enter a client name."):
            check_name(bad, taken, what="client")
    for dup in ("Acme Traders", "acme traders", " ACME TRADERS"):
        with pytest.raises(NameRefused, match="“Acme Traders” is already in use"):
            check_name(dup, taken, what="client")
    assert check_name("acme traders", taken, what="client", exclude="a") == "acme traders"   # its own name
    with pytest.raises(NameRefused, match="at most 100"):
        check_name("x" * 101, taken, what="client")


def test_copy_name():
    assert copy_name("Sales Register", {"1": "Sales Register"}) == "Sales Register (copy)"
    assert copy_name("Sales Register", {"1": "Sales Register", "2": "sales register (COPY)"}) == \
        "Sales Register (copy 2)"


def test_figures_text():
    assert formats.gigabytes(0) == "0 GB" and formats.gigabytes(40 * 1024 ** 2) == "0 GB"
    assert formats.gigabytes(int(41.6 * 1024 ** 3)) == "41.6 GB"
    assert formats.gigabytes(112 * 1024 ** 3) == "112 GB"
    assert formats.count(1, "template") == "1 template" and formats.count(10937, "row") == "10,937 rows"
    assert formats.count(3, "saved analysis", "saved analyses") == "3 saved analyses"
    assert manage.StorageFigures(0, 0, manage.LOW_DISK_BYTES - 1, "C:").low
    assert not manage.StorageFigures(0, 0, manage.LOW_DISK_BYTES, "C:").low


def test_footer_text(app):
    from sankalan.ui.screens.clients import footer_text
    assert footer_text(manage.StorageFigures(445066953, int(41.6 * 1024 ** 3), 112 * 1024 ** 3, "C:")) == \
        "Data stored: 445,066,953 rows · 41.6 GB · 112 GB free on C:"


@spec("C4-18", "EXP-4")
def test_export_prefill():
    req = ex.prefill("left_out", {"folder": r"D:\Exports", "delimiter": ";", "encoding": "utf-8"}, template_id="t",
                     client="Acme Traders", template="Sales Register", run_id="x", run_label="R-0003")
    assert (req.folder, req.file_name, req.options) == (
        r"D:\Exports", "Acme Traders_Sales Register_R-0003_Left-out rows.csv", ex.ExportOptions(";", False))
    req = ex.prefill("issues", {}, template_id="t", client="A:B", template="T", run_label="R-0001")
    assert req.file_name == "A_B_T_R-0001_Issues.csv" and req.options == ex.ExportOptions(",", True)
    assert req.folder == ex.default_folder()


def test_list_source_sort_and_search():
    from sankalan.ui.widgets.paged_grid import GridColumn, ListSource
    cols = [GridColumn("name", "Name"), GridColumn("n", "N")]
    src = ListSource(cols, [("beta", 2), ("Alpha", None), ("gamma", 10)], default_sort=[("name", True)],
                     matches=lambda r, t: t.casefold() in r[0].casefold())
    assert [r[0] for r in src.view([])] == ["Alpha", "beta", "gamma"]
    assert [r[0] for r in src.view([("n", False)])] == ["gamma", "beta", "Alpha"]      # blanks last
    assert [r[0] for r in src.view([("n", True)])] == ["beta", "gamma", "Alpha"]
    src.search = "AL"
    assert src.count(None, []) == 1 and src.page(None, 0, 10, [])[0][0] == "Alpha"


def test_builder_round_trip(app):
    """Settings → builder → settings unchanged (filters of every kind, groups with grains, measures)."""
    from sankalan.model.template import Column
    from sankalan.ui.widgets.builder import DefinitionBuilder
    cols = tpl_a_columns() + [Column("c009", "Qty", "Number", decimals=0)]
    out = Definition("t1", [Filter("c002", d.LATEST_QUARTER), Filter("c005", d.ONE_OF, ["Delhi", "Goa"]),
                            Filter("c006", d.BETWEEN, ["0", "100.5"]), Filter("c003", d.NOT_BLANK)],
                     [Group("c002", "month"), Group("c007")],
                     cards(FlatMeasure("c006", d.SUM, "Taxable"), FlatMeasure(d.ROWS, d.COUNT, None),
                      FlatMeasure("c003", d.COUNT_DISTINCT, "Customers"), FlatMeasure("c002", d.MAX, None)), True)
    b = DefinitionBuilder(cols, output=True)
    b.set_definition(out)
    assert b.definition().to_dict() == out.to_dict()
    assert b.summary() == "2 groups · 4 measures"
    analysis = Definition("t1", [Filter("c002", d.MONTH, [2026, 10]),
                                 Filter("c002", d.BETWEEN, ["2026-04-01", None]),
                                 Filter("c007", d.EQUALS, ["18"]), Filter("c005", d.CONTAINS, ["ra"])],
                          [Group("c002")], cards(FlatMeasure("c009", d.AVG, None)), False)
    b2 = DefinitionBuilder(cols, output=False)
    b2.set_definition(analysis)
    assert b2.definition().to_dict() == analysis.to_dict()
    d.check(b2.definition(), cols)


def test_rule_dialog_values(app):
    from sankalan.model.rule import DATE_RANGE, NUMBER_RANGE, TEXT_LENGTH, UNIQUE, Rule
    from sankalan.ui.dialogs.rule_editor import RuleDialog
    cols = tpl_a_columns()
    dlg = RuleDialog(Rule("r1", "c002", DATE_RANGE, {"from": "2026-04-01", "to": "2027-03-31"}), cols)
    assert dlg.fields["from"].text() == "01-04-2026"
    dlg.fields["to"].setText("31/03/2027")
    dlg._ok()
    assert dlg.result() == RuleDialog.DialogCode.Accepted
    assert dlg.rule.settings == {"from": "2026-04-01", "to": "2027-03-31"}
    dlg = RuleDialog(Rule("r2", "c006", NUMBER_RANGE, {}), cols)
    dlg.between.setChecked(True)
    dlg.fields["min"].setText("20")
    dlg.fields["max"].setText("10")
    dlg._ok()
    assert dlg.error.text() == "The minimum is more than the maximum."
    dlg = RuleDialog(Rule("r3", "c004", TEXT_LENGTH, {}), cols)
    dlg.fields["exact"].setText("15")
    dlg._ok()
    assert dlg.rule.settings == {"exact": 15}
    dlg = RuleDialog(Rule("r4", "c001", UNIQUE, {}), cols)
    dlg.keys["c004"].setChecked(True)
    dlg._ok()
    assert dlg.rule.settings == {"columns": ["c001", "c004"]}
