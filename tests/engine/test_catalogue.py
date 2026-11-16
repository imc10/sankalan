"""db/catalogue.py and start-up: schema, schema_version upgrades, backups ×5 (T8, T10, DEP-03)."""
import json
from datetime import datetime, timedelta

import duckdb
import pytest

from conftest import make_paths, open_storage, spec
from sankalan.db import catalogue


@spec("DEP-03", "T25", "T8")
def test_first_start_creates_data_folder_catalogue_settings_and_logs(tmp_path):
    s = open_storage(tmp_path)
    try:
        p = make_paths(tmp_path)
        data = p.root / "Data"
        assert s.folder.path == data
        assert (data / "catalogue.duckdb").is_file()
        assert (data / "_staging").is_dir() and (data / "t").is_dir() and (data / "catalogue-backups").is_dir()
        assert json.loads(p.settings_file.read_text(encoding="utf-8")) == {"data_folder": str(data)}
        assert p.logs.is_dir()
        tables = {r[0] for r in s.con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
        assert set(catalogue.TABLES) <= tables
        assert catalogue.current_version(s.con) == catalogue.SCHEMA_VERSION
        assert catalogue.list_backups(s.folder.backups) == []        # nothing to back up on the first start
    finally:
        s.close()


@spec("T10")
def test_backup_at_each_start_keeps_last_five(tmp_path):
    for _ in range(7):
        open_storage(tmp_path).close()
    s = open_storage(tmp_path)
    try:
        backups = catalogue.list_backups(s.folder.backups)
        assert len(backups) == 5
        c = duckdb.connect(str(backups[-1]), read_only=True)
        assert c.execute("SELECT max(version) FROM schema_version").fetchone()[0] == catalogue.SCHEMA_VERSION
        c.close()
    finally:
        s.close()


@spec("T10")
def test_backup_rotation_drops_oldest(tmp_path):
    cat = tmp_path / "catalogue.duckdb"
    cat.write_bytes(b"x")
    t0 = datetime(2026, 11, 16, 9, 0, 0)
    made = [catalogue.backup(cat, tmp_path / "b", now=t0 + timedelta(minutes=i)) for i in range(8)]
    assert catalogue.list_backups(tmp_path / "b") == made[-5:]


@spec("T10")
def test_backup_copies_a_leftover_wal(tmp_path):
    cat = tmp_path / "catalogue.duckdb"
    cat.write_bytes(b"db")
    (tmp_path / "catalogue.duckdb.wal").write_bytes(b"wal")
    b = catalogue.backup(cat, tmp_path / "b")
    assert b.read_bytes() == b"db" and b.with_name(b.name + ".wal").read_bytes() == b"wal"


def test_upgrade_runs_each_missing_step_once(tmp_path, monkeypatch):
    c = duckdb.connect(str(tmp_path / "c.duckdb"))
    assert catalogue.ensure_schema(c) == 1
    extra = {2: ["ALTER TABLE client ADD COLUMN note VARCHAR"]}
    monkeypatch.setattr(catalogue, "MIGRATIONS", {**catalogue.MIGRATIONS, **extra})
    assert catalogue.ensure_schema(c, target=2) == 2
    assert catalogue.ensure_schema(c, target=2) == 2          # nothing left to do
    assert [r[0] for r in c.execute("SELECT version FROM schema_version ORDER BY 1").fetchall()] == [1, 2]
    assert "note" in [r[0] for r in c.execute("DESCRIBE client").fetchall()]
    c.close()


def test_failed_upgrade_step_rolls_back(tmp_path, monkeypatch):
    c = duckdb.connect(str(tmp_path / "c.duckdb"))
    catalogue.ensure_schema(c)
    monkeypatch.setattr(catalogue, "MIGRATIONS", {**catalogue.MIGRATIONS,
                                                  2: ["ALTER TABLE client ADD COLUMN note VARCHAR", "SELEC oops"]})
    with pytest.raises(duckdb.Error):
        catalogue.ensure_schema(c, target=2)
    assert catalogue.current_version(c) == 1
    assert "note" not in [r[0] for r in c.execute("DESCRIBE client").fetchall()]
    c.close()


def test_newer_catalogue_is_refused(tmp_path):
    c = duckdb.connect(str(tmp_path / "c.duckdb"))
    catalogue.ensure_schema(c)
    c.execute("INSERT INTO schema_version VALUES (99, current_localtimestamp())")
    with pytest.raises(catalogue.CatalogueTooNew):
        catalogue.ensure_schema(c)
    c.close()
