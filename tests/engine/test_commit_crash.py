"""Crash during commit (Tech spec, Tests): the process is killed at each commit step; after a restart only committed
runs exist and no extra folders remain (RUN-5, T8)."""
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, open_storage, spec
from sankalan.db import datafolder
from sankalan.query import catalogue as q

CHILD = r"""
import os, sys
from pathlib import Path
sys.path.insert(0, {root!r}); sys.path.insert(0, {tests!r})
from conftest import open_storage, stage_fake_run, new_run
from sankalan.db import datafolder
from sankalan.query import catalogue as q
s = open_storage(Path({base!r}))
tid = q.template_ids(s.con)[0]
st = stage_fake_run(s, 5)
def on_step(name):
    if name == {crash_at!r}:
        os._exit(9)                      # no clean-up, no close: like a power cut or a killed process
crash_before = {crash_at!r} == "before"
if crash_before:
    os._exit(9)
datafolder.commit(s.con, s.folder, st, new_run(tid, 5), on_step=on_step)
os._exit(0)
"""


def _setup(base: Path) -> tuple[str, str]:
    s = open_storage(base)
    tid = q.insert_template(s.con, q.insert_client(s.con, "Acme"), "Sales")
    from conftest import new_run, stage_fake_run
    st = stage_fake_run(s, 3)
    datafolder.commit(s.con, s.folder, st, new_run(tid, 3))       # R-0001 is committed before the crash
    s.close()
    return tid, st.id


@spec("RUN-5", "T8")
@pytest.mark.parametrize("crash_at,committed", [("before", False), ("flushed", False), ("renamed", False),
                                                ("recorded", True)])
def test_crash_at_each_commit_step(tmp_path, crash_at, committed):
    tid, first = _setup(tmp_path)
    code = CHILD.format(root=str(ROOT), tests=str(ROOT / "tests"), base=str(tmp_path), crash_at=crash_at)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 9, out.stderr[-2000:]

    s = open_storage(tmp_path)
    try:
        runs = q.list_runs(s.con, tid)
        assert [r.label for r in runs] == (["R-0001", "R-0002"] if committed else ["R-0001"])
        assert not any(r.damaged for r in runs)
        on_disk = sorted(p.name for p in (s.folder.template_dir(tid) / "runs").iterdir())
        assert on_disk == sorted(r.id for r in runs)                # no extra folders
        assert list(s.folder.staging_root.iterdir()) == []
        if committed:
            rows = s.con.execute("SELECT count(*) FROM run_file").fetchone()[0]
            assert rows == 2                                         # the whole transaction survived
        # the next commit gets the next number and nothing was half-issued
        from conftest import new_run, stage_fake_run
        st = stage_fake_run(s, 1)
        n = datafolder.commit(s.con, s.folder, st, new_run(tid, 1))
        assert n == (3 if committed else 2)
    finally:
        s.close()
