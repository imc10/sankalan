"""BUG-1: the clean-up after a Job deleted DuckDB's live spill files (Feature Spec A2 13.1; Tech spec A2 11, T54).

After every Job, %TEMP%\\Sankalan is emptied except the open connection's own ``duckdb_temp_<pid>_*`` files; closing
the data folder (and start-up) still empty it completely.

The scenario: a temporary table large enough to spill under a small memory limit is made in one Job; the next Job
sorts it into a second table (DuckDB frees and reuses spill blocks) and the Job after reads both in full. With the
old clean-up DuckDB failed with "Failed to delete file …duckdb_temp_<pid>_0_storage_S32K-0.tmp" and then "Cannot
open file …block…" (checked on the dev PC, 21-11-2026; ``test_old_cleanup_breaks_spilled_tables`` keeps that
evidence). DuckDB's error text is never logged or shown (SEC-5); the tests read it only here.
"""
import os

import pytest

from conftest import make_paths, spec, temp_leftovers
from sankalan import paths as app_paths
from sankalan.db.storage import Storage, own_spill_file

ROWS = 2_000_000
MAKE = ("CREATE TEMP TABLE big AS SELECT range AS i, md5(CAST(range AS VARCHAR)) || repeat('x', 40) AS t "
        f"FROM range({ROWS})")
EXPECT = (ROWS, ROWS * 72, ROWS * (ROWS - 1) // 2)


@pytest.fixture
def small(tmp_path):
    s = Storage(make_paths(tmp_path), memory_limit="128MiB", threads=2)
    s.open()
    yield s
    s.close()


def _sql(s, sql):
    job = s.runner.run("Query", lambda ctx: ctx.cursor().execute(sql).fetchall())
    return job


def _scenario(s) -> list:
    """Make (Job 1), sort into a second table (Job 2), read both in full (Jobs 3, 4)."""
    out = []
    for sql in (MAKE, "CREATE TEMP TABLE b AS SELECT * FROM big ORDER BY t",
                "SELECT count(*), sum(length(t)), sum(i) FROM b", "SELECT count(*), sum(length(t)), sum(i) FROM big"):
        out.append(_sql(s, sql))
    return out


@spec("AC-BUG-1a", "BUG-1", "T54")
def test_spilled_temp_table_survives_the_next_jobs(small):
    jobs = _scenario(small)
    assert [j.error for j in jobs] == [None] * 4
    assert tuple(jobs[2].result[0]) == EXPECT and tuple(jobs[3].result[0]) == EXPECT
    spills = [p.name for p in small.paths.temp.iterdir() if own_spill_file(p.name)]
    assert spills, "the test data no longer spills: raise ROWS or lower the memory limit"


@spec("BUG-1")
def test_old_cleanup_breaks_spilled_tables(small):
    """The same scenario with the old clean-up (everything deleted after a Job) fails: proof that the test above
    exercises BUG-1. Whether a spill file is deleted while DuckDB still needs it depends on timing (about 1 run in 4
    passed on the old code too, 21-11-2026), so the scenario is tried up to three times and must fail at least once."""
    small.runner.on_job_end = lambda _job: app_paths.empty_folder(small.paths.temp)
    for _attempt in range(3):
        jobs = _scenario(small)
        if any(j.error is not None for j in jobs[1:]):
            return
        for sql in ("DROP TABLE IF EXISTS b", "DROP TABLE IF EXISTS big"):
            _sql(small, sql)
    pytest.fail("the old clean-up never broke a spilled table in three tries")


@spec("AC-BUG-1b", "SEC-4", "T54")
def test_only_own_spill_files_stay_and_close_empties(tmp_path):
    p = make_paths(tmp_path)
    s = Storage(p, memory_limit="128MiB", threads=2)
    s.open()
    try:
        p.temp.mkdir(parents=True, exist_ok=True)
        other = p.temp / "duckdb_temp_1_0_storage_DEFAULT-0.tmp"          # another process id
        export_part = p.temp / "x.csv.part"

        def work(ctx):
            other.write_bytes(b"x")
            export_part.write_bytes(b"x")
            return ctx.cursor().execute(MAKE).fetchall()
        job = s.runner.run("Query", work)
        assert job.error is None
        assert temp_leftovers(p.temp) == []                                # only this process's spill files
        own = [x.name for x in p.temp.iterdir()]
        assert own and all(n.startswith(f"duckdb_temp_{os.getpid()}_") for n in own)
    finally:
        s.close()
    assert list(p.temp.iterdir()) == []                                    # close empties it completely
    (p.temp / f"duckdb_temp_{os.getpid()}_9_owner").write_bytes(b"x")     # e.g. left by a crash
    s2 = Storage(p, memory_limit="128MiB", threads=2)
    s2.open()
    try:
        assert list(p.temp.iterdir()) in ([], [p.temp / "no-extensions"])  # start-up empties it too
    finally:
        s2.close()


def test_empty_folder_keep_filter(tmp_path):
    for name in ("a.tmp", "keep_me", "dir"):
        (tmp_path / name).mkdir() if name == "dir" else (tmp_path / name).write_bytes(b"x")
    app_paths.empty_folder(tmp_path, keep=lambda n: n.startswith("keep"))
    assert [x.name for x in tmp_path.iterdir()] == ["keep_me"]
