"""Phase 0: the fixture pack F01-F21 reproduces the Fixtures tab of the Test Cases sheet."""
import hashlib
import shutil
from decimal import Decimal

import pytest

import generate
from conftest import spec


def _hashes(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}


@spec("F00-F21")
def test_pack_has_every_fixture(fixtures_dir):
    """Every file F01-F21 exists with the name the test sheet uses (verify() already compared the figures)."""
    for fid, name in generate.FILES.items():
        assert (fixtures_dir / name).exists(), fid
    assert (fixtures_dir / "Run_Folder").is_dir()


@spec("F02", "F04", "R-0001", "R-0003")
def test_headline_figures_match_the_sheet():
    """The oracle figures are the ones printed in the Fixtures tab and the TPL-A run table."""
    e = generate.EXPECTED
    assert e["F02"]["taxable"] == "7536875.00" and e["F02"]["tax"] == "956722.50"
    assert e["F04"]["taxable"] == {"input": "2986623.75", "loaded": "2946994.00", "left_out": "39629.75"}
    assert e["F04"]["tax"] == {"input": "381662.10", "loaded": "374994.35", "left_out": "6667.75"}
    for col in ("taxable", "tax"):
        t = {k: Decimal(v) for k, v in e["F04"][col].items()}
        assert t["input"] == t["loaded"] + t["left_out"]
    assert e["F04"]["loaded_rows"] + e["F04"]["left_out_rows"] == e["F04"]["rows"]
    assert e["F03"]["rows"] == 4000 and e["F03"]["hidden_rows"] == 25 and e["F03"]["blank_rows"] == 10


@spec("F00-F21")
def test_generation_is_deterministic(fixtures_dir, tmp_path):
    """Generating again gives byte-identical files; only F06 differs (encryption uses a random salt)."""
    again = generate.generate(tmp_path / "again")
    a, b = _hashes(fixtures_dir), _hashes(again)
    assert a.keys() == b.keys()
    assert {n for n in a if a[n] != b[n]} == {"Sales_Protected.xlsx"}


@spec("F00-F21")
def test_verify_catches_a_wrong_file(fixtures_dir, tmp_path):
    """The self-check is not vacuous: a fixture with the wrong contents fails it."""
    bad = tmp_path / "bad"
    shutil.copytree(fixtures_dir, bad)
    shutil.copyfile(bad / "Sales_Locked.xlsx", bad / "Sales_Oct.xlsx")     # F07 (1,000 rows) in place of F02
    with pytest.raises(generate.FixtureError, match="F02"):
        generate.verify(bad)


@spec("F04", "RUNV-03", "RUNC-02")
def test_f04_left_out_rows():
    """63 rows are left out: 60 with Error issues plus 3 later duplicates (n 702, 704, 706)."""
    assert len(generate.F04_LEFT_OUT) == 63
    assert generate.F04_LEFT_OUT[:3] == [101, 102, 103] and generate.F04_LEFT_OUT[-3:] == [702, 704, 706]


@spec("A2-O1", "AC-BUG-1c")
def test_tpl_r_small_generates_verifies_and_is_deterministic(tmp_path, tpl_r_small):
    """TPL-R small (A2-1): the planted figures confirmed 21-11-2026, read back from the files; same bytes twice."""
    import tpl_r
    folder, m = tpl_r_small
    assert m.run(1).taxable_text == {"NA": 10, "Nil": 5, "12,000/-": 1}
    assert m.run(2).date_text == {"NA": 3, "31-02-2026": 2}
    assert (m.run(2).left_out, m.run(3).no_invoice_no, m.rows_searched) == (63, 400, 7_437)
    again = tpl_r.generate(tmp_path, tpl_r.SMALL)
    tpl_r.verify(tmp_path, again)
    assert _hashes(tmp_path) == _hashes(folder)
