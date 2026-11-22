"""jobs/: states, progress, cancel, one Job at a time, temp emptied after each Job (T5, T6, UI-5, SEC-4, SEC-5)."""
import threading
import time

import duckdb
import pytest

from conftest import spec
from sankalan.jobs import Cancelled, JobBusy, JobRunner, JobState

LONG_SQL = "SELECT sum(i) FROM range(200000000000) t(i)"      # minutes of work; always interrupted


def _until(cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


@spec("T6", "UI-5")
def test_job_states_and_rows_progress():
    gate = threading.Event()

    def work(ctx):
        ctx.set_stage("Reading", rows_total=200)
        ctx.add_rows(50)
        gate.wait(5)
        ctx.set_rows(200)
        return "ok"

    r = JobRunner()
    job = r.start("Load", work)
    assert _until(lambda: job.progress().rows_done == 50)
    p = job.progress()
    assert (p.state, p.stage, p.rows_done, p.rows_total, p.fraction, p.cancellable) == \
        (JobState.RUNNING, "Reading", 50, 200, 0.25, True)
    gate.set()
    assert job.wait(5)
    p = job.progress()
    assert job.state is JobState.DONE and job.result == "ok" and p.fraction == 1.0 and not p.cancellable
    e1 = p.elapsed
    time.sleep(0.05)
    assert job.progress().elapsed == e1                    # elapsed stops when the Job ends


@spec("T53", "EXP-11")
def test_set_detail_reaches_progress():
    gate, shown = threading.Event(), threading.Event()

    def work(ctx):
        ctx.set_stage("Writing files", rows_total=3000)
        ctx.set_detail("part 2 of 3")
        shown.set()
        gate.wait(5)
        ctx.set_stage("Finishing")                         # a new stage clears the detail
        return "ok"

    job = JobRunner().start("Export", work)
    assert shown.wait(5)
    assert job.progress().detail == "part 2 of 3"
    gate.set()
    assert job.wait(5) and job.progress().detail is None


@spec("T6", "SH-02")
def test_only_one_long_job_at_a_time():
    gate = threading.Event()
    r = JobRunner()
    first = r.start("Load", lambda ctx: gate.wait(5))
    assert r.busy
    with pytest.raises(JobBusy):
        r.start("Export", lambda ctx: None)
    gate.set()
    first.wait(5)
    assert not r.busy
    assert r.run("Export", lambda ctx: 1).result == 1


@spec("UI-5")
def test_cancel_between_steps():
    started = threading.Event()

    def work(ctx):
        started.set()
        while True:
            ctx.check_cancelled()
            time.sleep(0.01)

    r = JobRunner()
    job = r.start("Load", work)
    started.wait(5)
    assert job.cancel()
    assert job.wait(5)
    assert job.state is JobState.CANCELLED and job.error is None


@spec("UI-5")
def test_cancel_callbacks_and_abort_cleanup():
    calls = []
    ready = threading.Event()

    def work(ctx):
        ctx.on_cancel(lambda: calls.append("stop workers"))
        ctx.on_abort(lambda: calls.append("discard staging"))
        ready.set()
        while not ctx.cancel_requested:
            time.sleep(0.01)
        raise Cancelled()

    r = JobRunner()
    job = r.start("Load", work)
    assert ready.wait(5)            # a fixed sleep raced the thread start under load (full suite, Phase 9)
    job.cancel()
    job.wait(5)
    assert calls == ["stop workers", "discard staging"]


@spec("RUN-5")
def test_non_cancellable_step():
    gate = threading.Event()

    def work(ctx):
        ctx.set_cancellable(False)
        gate.wait(5)
        return "committed"

    r = JobRunner()
    job = r.start("Commit", work)
    assert _until(lambda: not job.progress().cancellable)
    assert job.cancel() is False
    assert job.state is JobState.RUNNING
    gate.set()
    job.wait(5)
    assert job.state is JobState.DONE and job.result == "committed"
    assert job.cancel() is False                           # finished Jobs can't be cancelled


@spec("SEC-5")
def test_failure_records_class_only_and_logs_no_values(tmp_path):
    from sankalan import log
    log.setup(tmp_path / "logs")
    secret = "INV-SECRET-4711"

    def work(ctx):
        raise ValueError(f"could not read {secret}")

    job = JobRunner().run("Validate", work)
    assert job.state is JobState.FAILED and job.progress().error_class == "ValueError"
    for h in log.log.handlers:
        h.flush()
    text = (tmp_path / "logs" / "sankalan.log").read_text(encoding="utf-8")
    assert "Validate failed: ValueError" in text and secret not in text


@spec("UI-5", "T5")
def test_cancel_interrupts_duckdb_and_reports_query_progress(storage):
    def work(ctx):
        ctx.set_stage("Validate")
        return ctx.cursor().execute(LONG_SQL).fetchall()

    job = storage.runner.start("Validate", work)
    assert _until(lambda: (job.progress().fraction or 0) > 0), "DuckDB query progress is reported"
    t0 = time.monotonic()
    assert job.cancel()
    assert job.wait(10)
    assert time.monotonic() - t0 < 2.0
    assert job.state is JobState.CANCELLED
    assert storage.con.execute("SELECT 42").fetchone() == (42,)            # connection still usable


@spec("UI-5")
def test_cancel_before_query_starts_still_interrupts(storage):
    go = threading.Event()

    def work(ctx):
        go.wait(5)
        return ctx.cursor().execute(LONG_SQL).fetchall()

    job = storage.runner.start("Validate", work)
    job.cancel()
    go.set()
    assert job.wait(10)
    assert job.state is JobState.CANCELLED


@spec("SEC-4", "T7")
def test_temp_folder_emptied_after_every_job(storage):
    spill = storage.paths.temp / "spill.tmp"

    def work(ctx):
        spill.write_bytes(b"x" * 10)
        return spill.exists()

    job = storage.runner.run("Query", work)
    assert job.result is True and not spill.exists()
    spill.write_bytes(b"x")
    storage.runner.run("Fail", lambda ctx: 1 / 0)
    assert not spill.exists()


@spec("SEC-5")
def test_duckdb_error_text_not_logged(storage):
    marker = "MARKER-CELL-9931"

    def work(ctx):
        ctx.cursor().execute(f"SELECT CAST('{marker}' AS INTEGER)").fetchall()

    job = storage.runner.run("Convert", work)
    assert job.state is JobState.FAILED and isinstance(job.error, duckdb.Error)
    from sankalan import log
    for h in log.log.handlers:
        h.flush()
    text = (storage.paths.logs / "sankalan.log").read_text(encoding="utf-8")
    assert "Convert failed: ConversionException" in text and marker not in text
