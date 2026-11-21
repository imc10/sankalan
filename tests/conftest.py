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


# ---------------------------------------------------------------------------------------------- time budgets
# Each test file has an expected completion time (tests/time_budgets.py). More than 10% over it stops the run at once;
# a test that hangs is stopped at the same limit by a faulthandler watchdog that prints every thread's stack and ends
# the process. The one-off building of shared test data (fixture pack, TPL-R) doesn't count against the file that
# happens to build it. Off with SANKALAN_NO_TIME_BUDGET=1 (debugging only).
import time as _time  # noqa: E402

import time_budgets as _tb  # noqa: E402

_BUDGET_ON = os.environ.get("SANKALAN_NO_TIME_BUDGET") != "1"
_clock = {"file": None, "start": 0.0, "excluded": 0.0, "suite": None, "limit": None, "out": None}
WATCHDOG_GRACE = 10.0         # s past the limit: a test that ends late gets the TIME BUDGET stop, a hang the dump
WATCHDOG_FILE = ROOT / "tests" / "fixtures" / "_generated" / "watchdog.txt"   # used only if pytest's stderr isn't


def _watchdog_out(config):
    """Where the watchdog writes: the real stderr pytest's faulthandler plugin keeps (output capture would swallow
    fd 2), else a file."""
    try:
        from _pytest.faulthandler import fault_handler_stderr_fd_key
        return config.stash[fault_handler_stderr_fd_key]
    except (ImportError, KeyError):
        WATCHDOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        return open(WATCHDOG_FILE, "w", encoding="utf-8")


def _file_of(item) -> str:
    return Path(str(item.fspath)).resolve().relative_to(ROOT).as_posix()


def file_budget(name: str) -> float:
    budget = _tb.BUDGETS.get(name, _tb.DEFAULT)
    if name == "tests/packaging/test_installer.py" and os.environ.get("SANKALAN_BUILD_TESTS") == "1":
        budget += _tb.BUILD_BUDGET
    return budget


def _elapsed() -> float:
    return _time.monotonic() - _clock["start"] - _clock["excluded"]


def _arm_watchdog() -> None:
    """End the process with every thread's stack when the current file reaches its limit (a hang)."""
    import faulthandler
    if _clock["limit"] is not None:
        faulthandler.dump_traceback_later(max(1.0, _clock["limit"] - _elapsed()) + WATCHDOG_GRACE, exit=True,
                                          file=_clock["out"])


class untimed:
    """Time spent inside (building shared test data) doesn't count against the current file's budget; the watchdog
    is paused meanwhile."""

    def __enter__(self):
        import faulthandler
        faulthandler.cancel_dump_traceback_later()
        self.t = _time.monotonic()

    def __exit__(self, *exc):
        _clock["excluded"] += _time.monotonic() - self.t
        _arm_watchdog()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if not _BUDGET_ON:
        yield
        return
    import faulthandler
    name = _file_of(item)
    if _clock["suite"] is None:
        _clock["suite"] = _time.monotonic()
    if _clock["file"] != name:
        _clock.update(file=name, start=_time.monotonic(), excluded=0.0)
    limit = file_budget(name) * _tb.OVERRUN
    if _clock["out"] is None:
        _clock["out"] = _watchdog_out(item.config)
    _clock["limit"] = limit
    _arm_watchdog()
    try:
        yield
    finally:
        _clock["limit"] = None
        faulthandler.cancel_dump_traceback_later()
    spent = _elapsed()
    if spent > limit:
        pytest.exit(f"TIME BUDGET: {name} took {spent:.1f} s, more than 10% over its expected {file_budget(name):g} s "
                    f"(tests/time_budgets.py). Stop, investigate the cause, fix it, then run again.", returncode=3)


def pytest_terminal_summary(terminalreporter):
    if _BUDGET_ON and _clock["suite"] is not None:
        spent = _time.monotonic() - _clock["suite"]
        terminalreporter.write_line(f"Time budget: tests took {spent:.0f} s; the full normal suite is expected to "
                                    f"take {_tb.SUITE} s (stop and investigate above {_tb.SUITE * _tb.OVERRUN:.0f} s)")


@pytest.fixture(autouse=True)
def collect_garbage():
    """Collect after every test, while no Job runs. A closed DuckDB connection left in a reference cycle by an
    earlier test (storage ↔ runner ↔ Jobs) could otherwise be finalised by a collection on the main thread while a
    later test's Job thread was inside DuckDB on another connection: the process crashed (access violation) in
    some test orders, e.g. tests/engine + tests/gui (seen on the Phase 7 commit too)."""
    yield
    import gc
    gc.collect()


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory):
    """The fixture pack F01-F21, generated once per test session and verified against the Fixtures tab."""
    import generate
    with untimed():
        out = generate.generate(tmp_path_factory.mktemp("fixtures"))
        generate.verify(out)
    return out


# ---------------------------------------------------------------------------------------------- storage (Phase 1)
def make_paths(base: Path):
    from sankalan.paths import AppPaths
    return AppPaths(base / "LocalAppData" / "Sankalan", base / "Temp" / "Sankalan")


def temp_leftovers(temp: Path) -> list[str]:
    """What a Job left in the app's temp folder besides the open connection's own DuckDB spill files, which stay for
    temporary tables kept between Jobs (SEC-4 as changed by BUG-1, T54)."""
    from sankalan.db.storage import own_spill_file
    return sorted(p.name for p in temp.iterdir() if not own_spill_file(p.name)) if temp.is_dir() else []


def version_1_folder(tmp_path):
    """A data folder as a test build left it: settings.json, a version-1 catalogue, a backup and a run folder."""
    import hashlib

    import duckdb
    p = make_paths(tmp_path)
    data = p.root / "Data"
    (data / "catalogue-backups").mkdir(parents=True)
    (data / "t" / "x" / "runs" / "y").mkdir(parents=True)
    (data / "t" / "x" / "runs" / "y" / "data.parquet").write_bytes(b"PAR1")
    p.settings_file.parent.mkdir(parents=True, exist_ok=True)
    p.settings_file.write_text(json.dumps({"data_folder": str(data)}), encoding="utf-8")
    c = duckdb.connect(str(data / "catalogue.duckdb"))
    c.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, upgraded_on TIMESTAMP NOT NULL)")
    c.execute("INSERT INTO schema_version VALUES (1, current_localtimestamp())")
    c.execute("CREATE TABLE client (id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, created_on TIMESTAMP NOT NULL)")
    c.close()

    def snapshot():
        return {str(f.relative_to(p.root)): (hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else "dir")
                for f in sorted(p.root.rglob("*")) if "Logs" not in f.parts}
    return p, data, snapshot


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


def settle_window(qtbot, w, timeout: int = 30_000, extra=None) -> None:
    """Wait until the window is idle: its bridge tracks no Job, the shared runner is free, and no screen holds a
    deferred quiet load. Tests share one runner between windows, so a Job started by an earlier test's window (its
    teardown's "Read clients") can still hold the runner when this window's screen asks for a read. That read is
    deferred and retried only on this window's own ``jobFinished``, which never comes for the other window's Job,
    so the deferred reads are retried here once the runner is free. Settling also keeps a test from reading
    ``storage.con`` on the main thread while a Job still holds the connection (DuckDB raises
    ``ResourceInUseException`` rather than waiting)."""
    import shiboken6
    from sankalan.ui.screens.common import DataScreen

    def idle():
        if not shiboken6.isValid(w):
            return True
        w.bridge.poll()
        runner = w.bridge.runner
        if w.bridge._tracked or (runner is not None and runner.busy):
            return False
        for sc in w.findChildren(DataScreen):
            if sc._pending:
                sc._retry_pending()
                return False
        return extra() if extra is not None else True
    qtbot.waitUntil(idle, timeout=timeout)


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


# ---------------------------------------------------------------------------------------------- template screens (Phase 7)
OVERRIDE_REASON = "Client confirmed errors; revised file next month"


def tpl_a_template(client_id: str):
    """TPL-A with its two default outputs DO1 and DO2 (Test Cases, Reference templates)."""
    from sankalan.model import definition as d
    from sankalan.model.definition import Definition, Filter, Group, Measure
    from sankalan.model.rule import with_type_rules
    from sankalan.model.template import DefaultOutput, Template
    cols = tpl_a_columns()
    do1 = Definition("", [], [Group("c005")], [Measure("c006", d.SUM, "Taxable"), Measure("c008", d.SUM, "Tax"),
                                               Measure("c001", d.COUNT, "Invoices")])
    do2 = Definition("", [Filter("c002", d.LATEST_MONTH)], [Group("c002", "month"), Group("c007")],
                     [Measure("c006", d.SUM)], subtotals=True)
    return Template("", client_id, "Sales Register", tpl_a_settings(), cols, with_type_rules(cols, tpl_a_rules()),
                    [DefaultOutput("State-wise sales", do1.to_dict()),
                     DefaultOutput("Latest month by GST rate", do2.to_dict())],
                    {"pattern": "{Client}_{Template}_{RunID}_{Output}", "delimiter": ",", "encoding": "utf-8-sig"})


def commit_tpl_a_run(storage, template_id, fx, name, reason=None, comment=""):
    """One TPL-A run through the real pipeline (validate, split, outputs, totals, commit)."""
    from sankalan.query import catalogue as q
    from sankalan.run.pipeline import RunSession
    sess = RunSession(storage.folder, q.load_template(storage.con, template_id), workers=0)
    run_job(storage.runner, lambda ctx: sess.add_files(ctx, [fx / name]))
    plan = sess.files_next()
    if not plan.skip:                       # extra source columns (e.g. Branch) are left out
        for kind, sheet, position in sess.mapping.undecided():
            assert kind == "extra", (kind, sheet, position)
            sess.mapping.leave_out(sheet, position)
        sess.mapping_next()
    run_job(storage.runner, sess.validate)
    run_job(storage.runner, lambda ctx: sess.leave_validate(ctx, reason))
    if sess.outputs:
        run_job(storage.runner, sess.run_outputs)
    run_job(storage.runner, lambda ctx: sess.check_totals(ctx, fault={}))
    job = storage.runner.run("commit", lambda ctx: sess.commit(ctx, comment or (reason or ""),
                                                                free_bytes=10 * 1024 ** 3), cancellable=False)
    if job.error is not None:
        raise job.error
    return job.result


# ---------------------------------------------------------------------------------------------- TPL-R (A2-1)
def _tpl_r_files(tmp_path_factory, size):
    import tpl_r
    out = tmp_path_factory.mktemp(f"tpl_r_{size}")
    with untimed():
        m = tpl_r.generate(out, size)
        tpl_r.verify(out, m)
    return out, m


@pytest.fixture(scope="session")
def tpl_r_small(tmp_path_factory):
    """TPL-R small (3 × 2,500 rows) generated once per session and verified: (folder, manifest)."""
    import tpl_r
    return _tpl_r_files(tmp_path_factory, tpl_r.SMALL)


@pytest.fixture(scope="session")
def tpl_r_full():
    """TPL-R full (3 × 2,500,000 rows), for ``slow`` tests only: built once into tests/fixtures/_generated and kept
    there, keyed by a hash of the generator, so later sessions reuse it."""
    import hashlib

    import tpl_r
    key = hashlib.sha256(Path(tpl_r.__file__).read_bytes()).hexdigest()[:12]
    out = ROOT / "tests" / "fixtures" / "_generated" / f"tpl_r_full_{key}"
    if (out / f"tpl_r_{tpl_r.FULL}.json").is_file():
        return out, tpl_r.load_manifest(out, tpl_r.FULL)
    with untimed():                 # ~5 minutes, once; not part of the slow file's budget
        m = tpl_r.generate(out, tpl_r.FULL)
        tpl_r.verify(out, m)
    return out, m


def commit_tpl_r_runs(storage, fx, manifest, workers=0) -> dict:
    """TPL-R R-0001…R-0003 through the real pipeline: R-0002's Place of Supply added as a new column (MAP-11) and
    committed with override (its 63 Character pattern errors left out); R-0003's file without Invoice No left as
    null (MAP-6). Returns {"client", "tid", "runs": {1: run id, …}}."""
    import tpl_r
    from sankalan.query import catalogue as q
    from sankalan.run.pipeline import RunSession
    client = q.insert_client(storage.con, "Rao & Co")
    tid = q.create_template(storage.con, tpl_r.template(client))
    runs = {}
    for k in (1, 2, 3):
        sess = RunSession(storage.folder, q.load_template(storage.con, tid), workers=workers)
        run_job(storage.runner, lambda ctx: sess.add_files(ctx, [fx / n for n in manifest.files[str(k)]]))
        plan = sess.files_next()
        if not plan.skip:
            while not plan.complete:            # adding a column maps the same header in the other file-sheets
                kind, a, b = plan.first_undecided()
                if kind == "extra":
                    plan.add_column(a, b, tpl_r.PLACE, "Text")
                else:
                    assert a == tpl_r.INV, (kind, a, b)
                    plan.leave_null(a, b)
            sess.mapping_next()
        run_job(storage.runner, sess.validate)
        reason = OVERRIDE_REASON if sess.validation.scan.errors else None
        run_job(storage.runner, lambda ctx: sess.leave_validate(ctx, reason))
        if sess.outputs:
            run_job(storage.runner, sess.run_outputs)
        run_job(storage.runner, lambda ctx: sess.check_totals(ctx, fault={}))
        job = storage.runner.run("commit", lambda ctx: sess.commit(ctx, reason or "", free_bytes=10 * 1024 ** 3),
                                 cancellable=False)
        if job.error is not None:
            raise job.error
        runs[k] = job.result.run_id
    return {"client": client, "tid": tid, "runs": runs}


@pytest.fixture(scope="module")
def tpl_r_runs(tmp_path_factory, tpl_r_small):
    """A storage with TPL-R small R-0001…R-0003 committed (module scope; tests only read it)."""
    fx, m = tpl_r_small
    s = open_storage(tmp_path_factory.mktemp("tpl_r_runs"))
    info = commit_tpl_r_runs(s, fx, m)
    yield {"s": s, "fx": fx, "m": m, **info}
    s.close()


# ---------------------------------------------------------------------------------------------- TPL-N (A2-2)
@pytest.fixture(scope="session")
def tpl_n_small(tmp_path_factory):
    """TPL-N small (2 × 5,000 rows, checks No) generated once per session and verified: (folder, manifest)."""
    import tpl_n
    out = tmp_path_factory.mktemp("tpl_n_small")
    with untimed():
        m = tpl_n.generate(out, tpl_n.SMALL)
        tpl_n.verify(out, m)
    return out, m


@pytest.fixture(scope="session")
def tpl_n_full():
    """TPL-N full (2 × 500,000 rows), for ``slow`` tests only: cached in tests/fixtures/_generated by a hash of the
    generator (and TPL-R's, whose row values it reuses)."""
    import hashlib

    import tpl_n
    import tpl_r
    key = hashlib.sha256(Path(tpl_n.__file__).read_bytes() + Path(tpl_r.__file__).read_bytes()).hexdigest()[:12]
    out = ROOT / "tests" / "fixtures" / "_generated" / f"tpl_n_full_{key}"
    if (out / f"tpl_n_{tpl_n.FULL}.json").is_file():
        return out, tpl_n.load_manifest(out, tpl_n.FULL)
    with untimed():
        m = tpl_n.generate(out, tpl_n.FULL)
        try:
            tpl_n.verify(out, m)
        except AssertionError:
            (out / f"tpl_n_{tpl_n.FULL}.json").unlink()      # never reuse a set that failed its check
            raise
    return out, m


def load_tpl_n(storage, template_id, fx, names, workers=0):
    """A TPL-N run up to the end of Load (no checks): the session with its LoadSummary."""
    from sankalan.query import catalogue as q
    from sankalan.run.pipeline import RunSession
    sess = RunSession(storage.folder, q.load_template(storage.con, template_id), workers=workers)
    run_job(storage.runner, lambda ctx: sess.add_files(ctx, [fx / n for n in names]))
    plan = sess.files_next()
    assert plan.skip, "TPL-N headers match the template"
    run_job(storage.runner, sess.load_unchecked)
    return sess


def commit_unchecked(storage, sess, comment=""):
    """Outputs, totals and commit of a run at the end of Load."""
    if sess.outputs:
        run_job(storage.runner, sess.run_outputs)
    run_job(storage.runner, lambda ctx: sess.check_totals(ctx, fault={}))
    job = storage.runner.run("commit", lambda ctx: sess.commit(ctx, comment, free_bytes=10 * 1024 ** 3),
                             cancellable=False)
    if job.error is not None:
        raise job.error
    return job.result
