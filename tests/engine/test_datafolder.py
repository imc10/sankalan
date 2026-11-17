"""Data folder: staging, commit, list, query, delete, Run IDs and start-up recovery (T8, T9, T22, RUN-1/5/9, SEC-4).

Phase 1 exit: a fake run (hand-written Parquet) can be staged, committed, listed, deleted and recovered."""
import shutil

import pytest

from conftest import new_run, open_storage, spec, stage_fake_run
from sankalan.db import datafolder
from sankalan.model.run import run_label
from sankalan.query import catalogue as q


@pytest.fixture
def tpl(storage):
    cid = q.insert_client(storage.con, "Acme Traders")
    return cid, q.insert_template(storage.con, cid, "Sales Register", {"sheets": "Sales"})


def _commit(storage, tid, rows=10, start=1):
    st = stage_fake_run(storage, rows, start)
    return st, datafolder.commit(storage.con, storage.folder, st, new_run(tid, rows))


@spec("RUN-1", "RUN-5", "T8", "T9")
def test_stage_commit_list_and_query(storage, tpl):
    cid, tid = tpl
    st, n = _commit(storage, tid, rows=10)
    assert n == 1 and run_label(n) == "R-0001"
    run_dir = storage.folder.run_dir(tid, st.id)
    assert not st.path.exists()                                     # staging renamed away
    assert sorted(p.name for p in run_dir.iterdir()) == ["data.parquet", "left_out.parquet", "outputs"]
    assert not (run_dir / "raw").exists()                           # raw\ removed by the commit
    runs = q.list_runs(storage.con, tid)
    assert [(r.id, r.label, r.rows_loaded, r.status, r.damaged) for r in runs] == \
        [(st.id, "R-0001", 10, "committed", False)]
    con = storage.con
    assert con.execute("SELECT file_name, sheet, rows_read FROM run_file WHERE run_id = ?", [st.id]).fetchall() \
        == [("Sales_Oct.xlsx", "Sales", 10)]
    assert con.execute("SELECT name, file FROM run_output WHERE run_id = ?", [st.id]).fetchall() \
        == [("By state", "outputs/1.parquet")]
    total = con.execute(f"SELECT sum(c002) FROM read_parquet('{(run_dir / 'data.parquet').as_posix()}')").fetchone()
    assert str(total[0]) == "68.75"                                 # 1.25 × (1 + … + 10)
    assert q.rows_stored(con) == 10 and q.rows_stored(con, cid) == 10


@spec("RUN-1", "MAP-11")
def test_runs_read_together_by_column_name(storage, tpl):
    """Several runs' files read as one dataset; a newer column is NULL in older runs (union_by_name)."""
    _, tid = tpl
    st1, _ = _commit(storage, tid, rows=3)
    st2 = stage_fake_run(storage, 2, start=100)
    con = storage.con
    p = (st2.path / "data.parquet").as_posix()
    con.execute(f"COPY (SELECT *, 'Pune' AS c003 FROM read_parquet('{p}')) TO '{p}.new' (FORMAT parquet)")
    (st2.path / "data.parquet").unlink()
    (st2.path / "data.parquet.new").rename(st2.path / "data.parquet")
    datafolder.commit(con, storage.folder, st2, new_run(tid, 2))
    files = [(storage.folder.run_dir(tid, r.id) / "data.parquet").as_posix() for r in q.list_runs(con, tid)]
    rows = con.execute(f"SELECT c003, count(*) FROM read_parquet({files!r}, union_by_name = true) "
                       "GROUP BY ALL ORDER BY 1 NULLS FIRST").fetchall()
    assert rows == [(None, 3), ("Pune", 2)]


@spec("T22", "RUNC-07")
def test_discarded_staging_does_not_use_a_run_id(storage, tpl):
    _, tid = tpl
    _commit(storage, tid)
    _commit(storage, tid)
    discarded = stage_fake_run(storage)
    storage.folder.discard_staging(discarded)
    assert not discarded.path.exists()
    _, n = _commit(storage, tid)
    assert run_label(n) == "R-0003"


@spec("T22", "RUNC-08", "RUN-9")
def test_run_ids_never_reused_after_delete(storage, tpl):
    _, tid = tpl
    ids = [_commit(storage, tid)[0].id for _ in range(6)]
    assert datafolder.delete_run(storage.con, storage.folder, ids[-1])     # delete R-0006
    assert not storage.folder.run_dir(tid, ids[-1]).exists()
    _, n = _commit(storage, tid)
    assert run_label(n) == "R-0007"
    assert [r.label for r in q.list_runs(storage.con, tid)] == ["R-0001", "R-0002", "R-0003", "R-0004", "R-0005",
                                                                 "R-0007"]
    assert not datafolder.delete_run(storage.con, storage.folder, "no-such-run")


@spec("T22")
def test_run_ids_count_per_template(storage, tpl):
    cid, tid = tpl
    other = q.insert_template(storage.con, cid, "Purchase Register")
    _commit(storage, tid)
    _commit(storage, tid)
    _, n = _commit(storage, other)
    assert n == 1


@spec("RUN-9")
def test_delete_run_removes_child_records(storage, tpl):
    _, tid = tpl
    st, _ = _commit(storage, tid)
    datafolder.delete_run(storage.con, storage.folder, st.id)
    for table in ("run", "run_file", "run_issue_count", "run_output"):
        col = "id" if table == "run" else "run_id"
        assert storage.con.execute(f"SELECT count(*) FROM {table} WHERE {col} = ?", [st.id]).fetchone()[0] == 0


@spec("TPL-4", "TPL-2")
def test_delete_template_and_client(storage, tpl):
    cid, tid = tpl
    other_client = q.insert_client(storage.con, "Other")
    keep = q.insert_template(storage.con, other_client, "Keep")
    _commit(storage, tid)
    st_keep, _ = _commit(storage, keep)
    storage.con.execute("INSERT INTO saved_analysis VALUES ('a1', ?, 'A', '{}', now(), now())", [tid])
    datafolder.delete_template(storage.con, storage.folder, tid)
    assert not storage.folder.template_dir(tid).exists()
    assert q.template_ids(storage.con) == [keep]
    assert storage.con.execute("SELECT count(*) FROM saved_analysis").fetchone()[0] == 0
    assert q.last_run_number(storage.con, tid) == 0
    datafolder.delete_client(storage.con, storage.folder, other_client)
    assert q.client_ids(storage.con) == [cid]
    assert q.list_runs(storage.con) == []
    assert not storage.folder.template_dir(keep).exists()


@spec("RUN-5")
def test_commit_needs_data_file_and_leaves_staging(storage, tpl):
    _, tid = tpl
    st = storage.folder.new_staging()
    with pytest.raises(datafolder.CommitError):
        datafolder.commit(storage.con, storage.folder, st, new_run(tid))
    assert st.path.exists() and q.list_runs(storage.con) == []


@spec("RUN-5", "T8")
def test_failed_catalogue_transaction_moves_folder_back(storage, tpl, monkeypatch):
    _, tid = tpl
    st = stage_fake_run(storage)

    def boom(con, run_id, run):
        con.execute("INSERT INTO run_id_counter VALUES ('half-written', 1)")
        raise RuntimeError("disk full")

    monkeypatch.setattr(q, "insert_run", boom)
    with pytest.raises(RuntimeError):
        datafolder.commit(storage.con, storage.folder, st, new_run(tid))
    assert st.path.is_dir() and not storage.folder.run_dir(tid, st.id).exists()
    assert storage.con.execute("SELECT count(*) FROM run_id_counter").fetchone()[0] == 0   # rolled back
    monkeypatch.undo()
    assert datafolder.commit(storage.con, storage.folder, st, new_run(tid)) == 1


# ---------------------------------------------------------------------------------------------- recovery
@spec("SEC-4", "T9")
def test_recovery_empties_staging(tmp_path):
    s = open_storage(tmp_path)
    st = stage_fake_run(s)
    s.close()
    s = open_storage(tmp_path)
    try:
        assert s.recovery.staging_removed == [st.id]
        assert list(s.folder.staging_root.iterdir()) == []
    finally:
        s.close()


@spec("T8")
def test_recovery_removes_orphan_folders(tmp_path):
    s = open_storage(tmp_path)
    cid = q.insert_client(s.con, "Acme")
    tid = q.insert_template(s.con, cid, "Sales")
    st, _ = _commit(s, tid)
    orphan_run = s.folder.run_dir(tid, "deadbeef")
    orphan_run.mkdir(parents=True)
    (orphan_run / "data.parquet").write_bytes(b"x")
    orphan_tpl = s.folder.template_dir("gone")
    (orphan_tpl / "runs" / "r1").mkdir(parents=True)
    s.close()
    s = open_storage(tmp_path)
    try:
        assert sorted(s.recovery.orphan_folders_removed) == sorted(["t/gone", f"t/{tid}/runs/deadbeef"])
        assert not orphan_run.exists() and not orphan_tpl.exists()
        assert s.folder.run_dir(tid, st.id).is_dir()
        assert [r.id for r in q.list_runs(s.con)] == [st.id]
    finally:
        s.close()


@spec("T8")
def test_recovery_marks_missing_run_damaged_and_clears_when_back(tmp_path):
    s = open_storage(tmp_path)
    tid = q.insert_template(s.con, q.insert_client(s.con, "Acme"), "Sales")
    st, _ = _commit(s, tid)
    run_dir = s.folder.run_dir(tid, st.id)
    s.close()
    hidden = tmp_path / "moved-away"
    shutil.move(str(run_dir), str(hidden))
    s = open_storage(tmp_path)
    try:
        assert s.recovery.damaged == [st.id]
        assert [r.damaged for r in q.list_runs(s.con)] == [True]
    finally:
        s.close()
    shutil.move(str(hidden), str(run_dir))
    s = open_storage(tmp_path)
    try:
        assert s.recovery.repaired == [st.id]
        assert [r.damaged for r in q.list_runs(s.con)] == [False]
    finally:
        s.close()


def test_folder_figures(storage, tpl):
    _, tid = tpl
    _commit(storage, tid)
    assert storage.folder.size_bytes() > 0
    assert storage.folder.free_bytes() > 0
