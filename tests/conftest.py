"""Shared test set-up. GUI tests run with QT_QPA_PLATFORM=offscreen."""
import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

RESULTS = []


def spec(*ids):
    """Tag a test with the spec items or test-case IDs it proves."""
    return pytest.mark.spec(*ids)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        m = item.get_closest_marker("spec")
        RESULTS.append({"test": item.nodeid, "spec": list(m.args) if m else [], "outcome": rep.outcome,
                        "seconds": round(rep.duration, 2), "doc": (item.function.__doc__ or "").strip()})


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("SANKALAN_TEST_REPORT")
    if path:
        Path(path).write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory):
    """The fixture pack F01-F21, generated once per test session and verified against the Fixtures tab."""
    import generate
    out = generate.generate(tmp_path_factory.mktemp("fixtures"))
    generate.verify(out)
    return out


# ---------------------------------------------------------------------------------------------- storage (Phase 1)
def make_paths(base: Path):
    from sankalan.paths import AppPaths
    return AppPaths(base / "LocalAppData" / "Sankalan", base / "Temp" / "Sankalan")


def open_storage(base: Path):
    from sankalan.db.storage import Storage
    s = Storage(make_paths(base), memory_limit="1GiB", threads=2)
    s.open()
    return s


@pytest.fixture
def storage(tmp_path):
    """An opened Storage in a temporary %LOCALAPPDATA% / %TEMP%, closed afterwards."""
    s = open_storage(tmp_path)
    yield s
    s.close()


def stage_fake_run(storage, rows: int = 10, start: int = 1):
    r"""A staged run written by hand: raw\ text, data.parquet with the fixed columns and two template columns,
    an empty left_out.parquet and one output. Stands in for Phases 2-5 until the pipeline exists."""
    st = storage.folder.new_staging()
    (st.raw / "f1.csv").write_text("x\n" * rows, encoding="utf-8")
    con = storage.con
    data = (st.path / "data.parquet").as_posix()
    con.execute(f"""COPY (SELECT NULL::VARCHAR AS run_id, 0 AS _src_file, 'Sales' AS _src_sheet, i + 2 AS _src_row,
                    'INV-' || (i + {start}) AS c001, CAST((i + {start}) * 1.25 AS DECIMAL(38,2)) AS c002
                    FROM range({rows}) t(i)) TO '{data}' (FORMAT parquet)""")
    con.execute(f"""COPY (SELECT * , '' AS _reason FROM read_parquet('{data}') LIMIT 0)
                    TO '{(st.path / 'left_out.parquet').as_posix()}' (FORMAT parquet)""")
    (st.path / "outputs").mkdir()
    con.execute(f"COPY (SELECT 1 AS n) TO '{(st.path / 'outputs' / '1.parquet').as_posix()}' (FORMAT parquet)")
    return st


def new_run(template_id: str, rows: int = 10):
    from sankalan.model.run import IssueCount, NewRun, RunFile, RunOutput
    return NewRun(template_id=template_id, template_version=1, rows_read=rows, rows_loaded=rows,
                  files=[RunFile(0, "Sales_Oct.xlsx", r"C:\in\Sales_Oct.xlsx", 1234, "Sales", "ab" * 32, rows)],
                  issue_counts=[IssueCount("VAL-1", 0, "Sales", 0, 0)],
                  outputs=[RunOutput(1, "By state", {"group": ["c001"]}, "outputs/1.parquet")])


# ---------------------------------------------------------------------------------------------- ingestion (Phase 2)
def tpl_a_columns():
    """TPL-A Sales Register (Test Cases, Reference templates)."""
    from sankalan.model.template import Column
    return [Column("c001", "Invoice No"), Column("c002", "Invoice Date", "Date"), Column("c003", "Customer"),
            Column("c004", "GSTIN"), Column("c005", "State"),
            Column("c006", "Taxable Value", "Number", decimals=2, totals_check=True),
            Column("c007", "GST Rate", "Number", decimals=0),
            Column("c008", "Tax Amount", "Number", decimals=2, totals_check=True)]


def tpl_c_columns():
    """TPL-C Conversion check."""
    from sankalan.model.template import Column
    return [Column("c001", "Case"), Column("c002", "Amount", "Number", decimals=2),
            Column("c003", "Amount0", "Number", decimals=0),
            Column("c004", "Doc Date", "Date", date_format="DD-MM-YYYY"),
            Column("c005", "Due Date", "Date", date_format="DD/MM/YYYY"), Column("c006", "Code")]


def tpl_a_settings():
    from sankalan.model.template import SourceSettings
    return SourceSettings(sheets="name", sheet_names=["Sales"])


def run_job(runner, work):
    """Run ``work(ctx)`` as a Job and return its result, re-raising a failure."""
    job = runner.run("test", work)
    if job.error is not None:
        raise job.error
    return job.result


def load_files(storage, fx, names, settings, columns, workers=0, mappings=None):
    """Probe and load fixture files into a new staging folder: (staging, LoadResult, probe rows).
    ``mappings``: optional {file name: {column ID: source position}} overriding the automatic match."""
    from sankalan import mapping
    from sankalan.ingest import stage
    rows = run_job(storage.runner, lambda ctx: stage.probe(ctx, [str(fx / n) for n in names], settings=settings,
                                                           columns=columns))
    assert all(r.readable for r in rows), [(r.file_name, r.message) for r in rows]
    parts = []
    for i, r in enumerate(rows):
        m = (mappings or {}).get(r.file_name) or mapping.auto_map(columns, r.headers)
        parts.append(stage.LoadPart.from_probe(i, r, m))
    st = storage.folder.new_staging()
    res = run_job(storage.runner, lambda ctx: stage.load(ctx, storage.folder, st, parts, columns, workers=workers))
    return st, res, rows


# ---------------------------------------------------------------------------------------------- validation (Phase 3)
def tpl_a_rules():
    """TPL-A rule set (Test Cases, Read me): the user's rules; the automatic type rules are added by the scan."""
    from sankalan.model.rule import (ALLOWED_VALUES, DATE_RANGE, NOT_BLANK, NUMBER_RANGE, PATTERN, TEXT_LENGTH,
                                     UNIQUE, WARNING, Rule)
    return [Rule("r1", "c001", NOT_BLANK), Rule("r2", "c001", PATTERN, {"pattern": "AAA-99999"}),
            Rule("r3", "c001", UNIQUE),
            Rule("r4", "c002", DATE_RANGE, {"from": "2026-04-01", "to": "2027-03-31"}, WARNING),
            Rule("r5", "c003", NOT_BLANK, severity=WARNING), Rule("r6", "c004", TEXT_LENGTH, {"exact": 15}),
            Rule("r7", "c005", ALLOWED_VALUES, {"values": ["Maharashtra", "Gujarat", "Karnataka", "Delhi"]}, WARNING),
            Rule("r8", "c006", NUMBER_RANGE, {"not_negative": True}),
            Rule("r9", "c007", ALLOWED_VALUES, {"values": ["0", "5", "12", "18", "28"]})]


# ---------------------------------------------------------------------------------------------- GUI (Phase 6)
import threading  # noqa: E402


@pytest.fixture
def app(qapp):
    from sankalan.ui import theme
    theme.apply(qapp)
    return qapp


@pytest.fixture
def answers():
    """Answer ``ask()`` prompts without showing them: push keys onto the list; each prompt pops the first and
    is recorded in ``answers.asked`` as (title, text, [option keys])."""
    from sankalan.ui.dialogs import base

    class Answers(list):
        asked = []

    a = Answers()

    def hook(dlg):
        a.asked.append((dlg.windowTitle(), [b.text() for b in dlg.buttons.values()]))
        return a.pop(0) if a else None

    base.answer_hook = hook
    yield a
    base.answer_hook = None


@pytest.fixture
def runner():
    from sankalan.jobs import JobRunner
    r = JobRunner(None)
    yield r
    r.wait(10)


class Gate:
    """Job work that runs until released (or cancelled)."""

    def __init__(self, cancellable_check: bool = True):
        self.release = threading.Event()
        self.started = threading.Event()
        self.check = cancellable_check

    def __call__(self, ctx):
        self.started.set()
        ctx.set_stage("Working", rows_total=4000)
        ctx.set_rows(1000)
        while not self.release.wait(0.01):
            if self.check:
                ctx.check_cancelled()
        return "done"


@pytest.fixture
def gate():
    g = Gate()
    yield g
    g.release.set()
