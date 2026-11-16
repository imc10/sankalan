"""Changing the data folder (UX-11, T25, ENV-5, DEP-07, DEP-08)."""
import json

from conftest import make_paths, new_run, open_storage, spec, stage_fake_run
from sankalan import paths
from sankalan.db import datafolder
from sankalan.db.storage import MoveRefused
from sankalan.jobs import JobState
from sankalan.query import catalogue as q


def _with_runs(storage, n=3):
    tid = q.insert_template(storage.con, q.insert_client(storage.con, "Acme Traders"), "Sales Register")
    for _ in range(n):
        datafolder.commit(storage.con, storage.folder, stage_fake_run(storage, 10), new_run(tid, 10))
    return tid


@spec("UX-11", "T25", "DEP-07")
def test_move_copies_checks_switches_and_deletes_old(tmp_path):
    s = open_storage(tmp_path)
    tid = _with_runs(s)
    old = s.folder.path
    before = q.counts(s.con)
    dest = tmp_path / "D" / "SankalanData"
    seen = []
    job = s.move_to(dest)
    while not job.wait(0.01):
        seen.append(job.progress().stage)
    assert job.state is JobState.DONE, job.progress().error_class
    assert s.folder.path == dest and not old.exists()
    assert json.loads(make_paths(tmp_path).settings_file.read_text(encoding="utf-8"))["data_folder"] == str(dest)
    assert (dest / "catalogue.duckdb").is_file() and (dest / "t" / tid).is_dir()
    assert q.counts(s.con) == before
    run = q.list_runs(s.con, tid)[0]
    f = (dest / "t" / tid / "runs" / run.id / "data.parquet").as_posix()
    assert s.con.execute(f"SELECT count(*) FROM read_parquet('{f}')").fetchone() == (10,)   # new folder allowed
    s.close()
    s = open_storage(tmp_path)                       # a restart uses the new folder
    try:
        assert s.folder.path == dest and len(q.list_runs(s.con, tid)) == 3
        assert datafolder.commit(s.con, s.folder, stage_fake_run(s, 1), new_run(tid, 1)) == 4
    finally:
        s.close()


@spec("ENV-5", "DEP-08")
def test_move_refuses_network_and_non_empty(storage, tmp_path, monkeypatch):
    _with_runs(storage, 1)
    old = storage.folder.path
    monkeypatch.setattr(paths, "_drive_type", lambda d: paths.DRIVE_REMOTE if d == "Z:\\" else 3)
    for dest in (r"\\fileserver\share\Sankalan", r"Z:\Sankalan"):
        assert storage.check_move(dest).refusal == datafolder.NETWORK_REFUSAL
        job = storage.runner.run("Move", lambda ctx, d=dest: storage._move(ctx, d))
        assert job.state is JobState.FAILED and isinstance(job.error, MoveRefused)
    full = tmp_path / "Full"
    full.mkdir()
    (full / "mine.txt").write_text("keep")
    job = storage.move_to(full)
    job.wait(30)
    assert isinstance(job.error, MoveRefused) and job.error.message == datafolder.NOT_EMPTY_REFUSAL
    assert (full / "mine.txt").read_text() == "keep" and sorted(p.name for p in full.iterdir()) == ["mine.txt"]
    assert storage.folder.path == old and old.is_dir()
    assert len(q.list_runs(storage.con)) == 1                      # connection still works on the old folder


@spec("UX-11", "UI-5")
def test_cancelled_move_leaves_everything_as_it_was(storage, tmp_path, monkeypatch):
    tid = _with_runs(storage, 2)
    old = storage.folder.path
    dest = tmp_path / "New"
    real_copy = datafolder.copy_tree

    def slow_copy(src, d, on_bytes=None, check_cancelled=None, chunk=0):
        def check():
            import time
            time.sleep(0.05)
            check_cancelled()
        return real_copy(src, d, on_bytes, check, chunk=1024)

    monkeypatch.setattr(datafolder, "copy_tree", slow_copy)
    job = storage.move_to(dest)
    import time
    deadline = time.monotonic() + 10
    while job.progress().stage != "Copying" and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.2)
    assert job.cancel()
    assert job.wait(30)
    assert job.state is JobState.CANCELLED
    assert not dest.exists()
    assert storage.folder.path == old
    assert json.loads(storage.paths.settings_file.read_text(encoding="utf-8"))["data_folder"] == str(old)
    assert len(q.list_runs(storage.con, tid)) == 2
