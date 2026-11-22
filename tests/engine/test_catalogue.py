"""db/catalogue.py and start-up: schema, schema_version upgrades, backups ×5 (T8, T10, DEP-03)."""
import json
from datetime import datetime, timedelta

import duckdb
import pytest

from conftest import make_paths, open_storage, spec, version_1_folder
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
    assert catalogue.ensure_schema(c) == 2
    extra = {3: ["ALTER TABLE client ADD COLUMN note VARCHAR"]}
    monkeypatch.setattr(catalogue, "MIGRATIONS", {**catalogue.MIGRATIONS, **extra})
    assert catalogue.ensure_schema(c, target=3) == 3
    assert catalogue.ensure_schema(c, target=3) == 3          # nothing left to do
    assert [r[0] for r in c.execute("SELECT version FROM schema_version ORDER BY 1").fetchall()] == [2, 3]
    assert "note" in [r[0] for r in c.execute("DESCRIBE client").fetchall()]
    c.close()


def test_failed_upgrade_step_rolls_back(tmp_path, monkeypatch):
    c = duckdb.connect(str(tmp_path / "c.duckdb"))
    catalogue.ensure_schema(c)
    monkeypatch.setattr(catalogue, "MIGRATIONS", {**catalogue.MIGRATIONS,
                                                  3: ["ALTER TABLE client ADD COLUMN note VARCHAR", "SELEC oops"]})
    with pytest.raises(duckdb.Error):
        catalogue.ensure_schema(c, target=3)
    assert catalogue.current_version(c) == 2
    assert "note" not in [r[0] for r in c.execute("DESCRIBE client").fetchall()]
    c.close()


@spec("T40")
def test_new_catalogue_is_version_2_with_the_a2_columns(tmp_path):
    c = duckdb.connect(str(tmp_path / "c.duckdb"))
    assert catalogue.ensure_schema(c) == 2
    assert [r[0] for r in c.execute("SELECT version FROM schema_version").fetchall()] == [2]

    def cols(table):
        return {r[0]: (r[1], r[2]) for r in c.execute(f"DESCRIBE {table}").fetchall()}
    assert cols("run")["checks"] == ("BOOLEAN", "NO") and cols("run")["text_counts"] == ("VARCHAR", "NO")
    assert cols("run_file")["sheets_chosen"] == ("BOOLEAN", "NO")
    assert cols("run_output")["headers"] == ("VARCHAR", "NO")
    c.close()


@spec("T40", "D77")
def test_version_1_catalogue_is_refused_and_the_folder_left_as_it_was(tmp_path):
    from sankalan.db.storage import Storage
    p, data, snapshot = version_1_folder(tmp_path)
    before = snapshot()
    s = Storage(p, memory_limit="1GiB", threads=2)
    with pytest.raises(catalogue.CatalogueFromTestBuild):
        s.open()
    assert s.con is None and s.runner is None
    assert snapshot() == before                               # no backup, no WAL, no new folder, no change
    assert catalogue.list_backups(data / "catalogue-backups") == []
    c = duckdb.connect(str(data / "catalogue.duckdb"))
    with pytest.raises(catalogue.CatalogueFromTestBuild):
        catalogue.ensure_schema(c)
    c.close()


def test_newer_catalogue_is_refused(tmp_path):
    c = duckdb.connect(str(tmp_path / "c.duckdb"))
    catalogue.ensure_schema(c)
    c.execute("INSERT INTO schema_version VALUES (99, current_localtimestamp())")
    with pytest.raises(catalogue.CatalogueTooNew):
        catalogue.ensure_schema(c)
    c.close()
