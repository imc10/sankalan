"""Phase 8 engine: the New template wizard's sample (TPL-3, C3-03, C3-06 to C3-11, C3-16, C3-20)."""
import csv
import time

import pytest

from conftest import run_job, spec
from sankalan import newtemplate as nt
from sankalan.ingest import sample as smp
from sankalan.model.definition import Definition, Group, Measure
from sankalan.model.rule import UNIQUE, Rule
from sankalan.model.template import DATE, NUMBER, TEXT, DefaultOutput, SourceSettings
from sankalan.query import catalogue as q
from sankalan.query.sample import Profile


def staged_sample(storage, path, source=None, **kw):
    info = run_job(storage.runner, lambda ctx: nt.inspect(ctx, path))
    src = source or nt.default_source(info)
    return info, run_job(storage.runner, lambda ctx: nt.stage(ctx, storage.folder, info, src, workers=0, **kw))


@spec("C3-03", "TPL-3")
def test_sample_stops_at_100000_rows(storage, tmp_path):
    big = tmp_path / "Perf.csv"
    with open(big, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Invoice No", "Amount"])
        for i in range(150_000):
            w.writerow([f"INV-{i:06d}", f"{i}.50"])
    info, st = staged_sample(storage, big)
    assert st.rows == 100_000 and st.limited
    raw_lines = sum(1 for _ in open(st.parts[0].raw_path, encoding="utf-8"))
    assert raw_lines == 100_001                         # header + 100,000 rows: the rest is never read
    assert [nt.detect(c.profile).type for c in st.columns] == [TEXT, NUMBER]


def test_limit_on_excel_and_workers(storage, fixtures_dir):
    _info, st = staged_sample(storage, fixtures_dir / "Sales_Errors.xlsx", limit=150)
    assert st.rows == 150 and st.limited
    info = run_job(storage.runner, lambda ctx: nt.inspect(ctx, fixtures_dir / "Sample_Sales.xlsx"))
    st2 = run_job(storage.runner, lambda ctx: nt.stage(ctx, storage.folder, info, nt.default_source(info),
                                                        workers=1))
    assert st2.rows == 1000 and not st2.limited
    assert not st.staging.path.exists() or st.staging.path != st2.staging.path


@spec("C3-06", "C3-07", "IN-6", "IN-13")
def test_inspect_sheets_and_header(fixtures_dir):
    info = smp.inspect(fixtures_dir / "Sample_Sales.xlsx")
    assert [(s.name, s.header_row, s.rows_approx) for s in info.sheets] == [("Sales", 3, 1000)]
    regions = smp.inspect(fixtures_dir / "Sales_Regions.xlsx")
    assert [(s.name, s.visible) for s in regions.sheets] == [("North", True), ("South", True), ("Archive", False)]
    for setting, expect in ((SourceSettings("first"), ["North"]), (SourceSettings("all"), ["North", "South"]),
                            (SourceSettings("name", ["south", "Archive"]), ["South"])):
        assert nt.sheets_to_read(regions, setting) == expect
    assert nt.sheets_problem(regions, SourceSettings("name", ["Archive"])) == "Tick at least one sheet to read."


@spec("C3-08", "IN-4")
def test_inspect_csv_1252(fixtures_dir):
    info = smp.inspect(fixtures_dir / "Conversion_1252.csv")
    assert (info.encoding, info.delimiter) == ("cp1252", ";")
    assert [r[1][5] for r in info.sheets[0].preview[1:]] == ["Café", "Müller", "Señor"]
    forced = smp.inspect(fixtures_dir / "Conversion_1252.csv", "utf-8", ",")
    assert forced.detected_encoding == "cp1252" and forced.delimiter == ","


def test_refusals(fixtures_dir, tmp_path):
    assert smp.refusal(fixtures_dir / "Sales_Old.xls") is None
    (tmp_path / "notes.txt").write_text("x")
    assert smp.refusal(tmp_path / "notes.txt") == ("notes.txt: only .xlsx, .xlsm, .xlsb, .xls and .csv files can be "
                                                   "added.")
    assert "not found" in smp.refusal(tmp_path / "gone.xlsx")
    with pytest.raises(smp.FileProblem) as e:
        smp.inspect(fixtures_dir / "Sales_Protected.xlsx")
    assert e.value.kind == "password"
    for name in ("Sales_Protected.xls", "Sales_Protected.xlsb"):
        with pytest.raises(smp.FileProblem) as e:
            smp.inspect(fixtures_dir / name)
        assert e.value.kind == "password"
        assert e.value.message == f"{name} is password-protected. Remove the password, or pick another file."
    with pytest.raises(smp.FileProblem) as e:
        smp.inspect(fixtures_dir / "Sales_Export.xls")
    assert e.value.kind == "web_page"


@spec("C3-04", "C3-06", "IN-3", "IN-13", "D38")
@pytest.mark.parametrize("name,kind", [("Sales_Nov.xls", "xls"), ("Sales_Nov.xlsb", "xlsb")])
def test_inspect_and_stage_xls_and_xlsb(storage, fixtures_dir, name, kind):
    ref = smp.inspect(fixtures_dir / "Sales_Nov.xlsx")
    info = smp.inspect(fixtures_dir / name)
    assert info.kind == kind
    assert [(s.name, s.visible, s.header_row, s.headers, s.rows_approx) for s in info.sheets] == \
        [(s.name, s.visible, s.header_row, s.headers, s.rows_approx) for s in ref.sheets]
    assert info.sheet("Sales").preview == ref.sheet("Sales").preview
    _info, st = staged_sample(storage, fixtures_dir / name)
    assert st.rows == 4000 and not st.limited


@spec("C3-09", "C3-11", "MAP-9", "MAP-10")
def test_type_detection(storage, fixtures_dir):
    _i, st = staged_sample(storage, fixtures_dir / "Conversion_Values.csv")
    det = [nt.detect(c.profile) for c in st.columns]
    assert [(x.type, x.date_format) for x in det] == [(TEXT, None), (NUMBER, None), (NUMBER, None),
                                                      (DATE, "DD-MM-YYYY"), (DATE, "DD/MM/YYYY"), (TEXT, None)]
    assert det[1].note == "90.9% numbers" and not det[1].exact
    assert det[3].note == "84.61% dates · DD-MM-YYYY"
    assert nt.detect(Profile(total=10, filled=1, samples=["x"])).note == "90% blank"
    assert nt.detect(Profile(total=10, filled=0)).note == "100% blank"
    assert nt.percent(9998, 10000) == "99.98%" and nt.percent(99999, 100000) == "99.99%"
    assert nt.percent(1, 1) == "100%"


@spec("C3-16", "VR-8")
def test_dry_run_counts_on_f04(storage, fixtures_dir):
    from conftest import tpl_a_rules
    _i, st = staged_sample(storage, fixtures_dir / "Sales_Errors.xlsx")
    drafts = nt.draft_columns(st)
    drafts[6].column.decimals = 0
    res = run_job(storage.runner, lambda ctx: nt.dry_run(ctx, st, drafts, tpl_a_rules()))
    assert res.counts == {"c002.type": 4, "c006.type": 15, "c007.type": 0, "c008.type": 0, "r1": 12, "r2": 8,
                          "r3": 6, "r4": 0, "r5": 7, "r6": 10, "r7": 25, "r8": 5, "r9": 6}
    assert len(res.first["r7"]) == 20 and len(res.first["c006.type"]) == 15
    assert res.first["c006.type"][0][2] == 214


@spec("C3-20", "C3-12", "V3-2")
def test_build_template_renumbers_in_order(storage, fixtures_dir):
    _i, st = staged_sample(storage, fixtures_dir / "Sample_Sales.xlsx")
    drafts = nt.draft_columns(st)
    drafts[2], drafts[1] = drafts[1], drafts[2]          # Customer before Invoice Date
    drafts[3].include = False                            # GSTIN left out
    rules = [Rule("r1", "c003", UNIQUE, {"columns": ["c003", "c005"]}), Rule("r2", "c004", "VAL-1")]
    outs = [DefaultOutput("By state", Definition("", [], [Group("c005")], [Measure("c006", "sum")]).to_dict())]
    t = nt.build_template("cl", " Sales ", SourceSettings("name", ["Sales"]), drafts, rules, outs)
    assert [(c.id, c.name) for c in t.columns][:4] == [("c001", "Invoice No"), ("c002", "Customer"),
                                                      ("c003", "Invoice Date"), ("c004", "State")]
    user = [r for r in t.rules if not r.automatic]
    assert len(user) == 1 and user[0].column_id == "c002" and user[0].settings == {"columns": ["c002", "c004"]}
    assert t.outputs[0].definition["groups"][0]["column_id"] == "c004"
    assert t.outputs[0].definition["measures"][0]["column_id"] == "c005"
    cid = q.insert_client(storage.con, "Acme Traders")
    t.client_id = cid
    tid = run_job(storage.runner, lambda ctx: nt.save(ctx, t))
    saved = q.load_template(storage.con, tid)
    assert saved.name == "Sales" and saved.version == 1 and saved.outputs[0].definition["template_id"] == tid
    assert not storage.folder.template_dir(tid).exists()


def test_stage_refuses_changed_file(storage, fixtures_dir, tmp_path):
    import shutil
    p = tmp_path / "s.xlsx"
    shutil.copy(fixtures_dir / "Sample_Sales.xlsx", p)
    info = smp.inspect(p)
    time.sleep(0.05)
    with open(p, "ab") as fh:
        fh.write(b"\0")
    with pytest.raises(nt.SampleProblem):
        run_job(storage.runner, lambda ctx: nt.stage(ctx, storage.folder, info, nt.default_source(info), workers=0))
    assert list(storage.folder.staging_root.iterdir()) == []
