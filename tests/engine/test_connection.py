"""db/connection.py: memory, threads, temp folder, extensions off, external access off, locked (T7, SEC-1, S1).

The tests never run INSTALL: if the hardening were broken it would download. LOAD and https reads are local
refusals and are tested instead; the source guard in tests/security forbids INSTALL in app code."""
import os

import duckdb
import pytest

from conftest import spec
from sankalan.db import connection


@pytest.fixture
def con(tmp_path):
    data, temp = tmp_path / "Data", tmp_path / "Temp"
    data.mkdir()
    c = connection.open_connection(data / "catalogue.duckdb", data, temp, memory_limit="1GiB", threads=2)
    yield c, data, temp, tmp_path
    c.close()


@spec("T7", "SEC-1")
def test_settings_are_hardened_and_locked(con):
    c, data, temp, _ = con
    s = connection.settings(c)
    assert s["lock_configuration"] == "true"
    assert s["enable_external_access"] == "false"
    for k in ("autoinstall_known_extensions", "autoload_known_extensions", "allow_community_extensions",
              "allow_unsigned_extensions"):
        assert s[k] == "false", k
    assert s["threads"] == "2"
    assert s["temp_directory"].rstrip("/") == temp.as_posix()
    assert "MiB" in s["memory_limit"] or "GiB" in s["memory_limit"]


@spec("T7")
def test_default_memory_is_half_of_ram_and_threads_are_cores(tmp_path):
    assert connection.memory_limit_text(16 * 1024 ** 3) == "8192MiB"
    data = tmp_path / "Data"
    data.mkdir()
    c = connection.open_connection(data / "c.duckdb", data, tmp_path / "Temp")
    try:
        s = connection.settings(c)
        assert int(s["threads"]) == os.cpu_count()
        half_gib = connection.total_ram_bytes() / 2 / 1024 ** 3
        value, unit = s["memory_limit"].split()
        gib = float(value) / (1024 if unit == "MiB" else 1)
        assert abs(gib - half_gib) < 0.1
    finally:
        c.close()


@spec("SEC-1")
@pytest.mark.parametrize("sql", ["SET lock_configuration = false", "SET enable_external_access = true",
                                 "SET autoload_known_extensions = true", "SET memory_limit = '2GB'",
                                 "SET allowed_directories = ['C:/']"])
def test_configuration_cannot_be_changed(con, sql):
    c, *_ = con
    with pytest.raises(duckdb.Error):
        c.execute(sql)


@spec("SEC-1")
def test_extensions_and_remote_reads_refused(con):
    c, *_ = con
    with pytest.raises(duckdb.Error):
        c.execute("LOAD httpfs")
    with pytest.raises(duckdb.Error):
        c.execute("SELECT * FROM read_csv('https://sankalan.invalid/x.csv')")


@spec("SEC-1", "S1")
def test_files_only_inside_data_and_temp_folders(con):
    c, data, temp, base = con
    outside = base / "Elsewhere"
    outside.mkdir()
    c.execute(f"COPY (SELECT 1 AS a) TO '{(data / 'a.parquet').as_posix()}' (FORMAT parquet)")
    c.execute(f"COPY (SELECT 2 AS a) TO '{(temp / 'b.parquet').as_posix()}' (FORMAT parquet)")
    assert c.execute(f"SELECT a FROM read_parquet('{(data / 'a.parquet').as_posix()}')").fetchall() == [(1,)]
    with pytest.raises(duckdb.Error):
        c.execute(f"COPY (SELECT 1) TO '{(outside / 'x.csv').as_posix()}'")
    (outside / "y.csv").write_text("a\n1\n")
    with pytest.raises(duckdb.Error):
        c.execute(f"SELECT * FROM read_csv('{(outside / 'y.csv').as_posix()}')")
    assert list(outside.iterdir()) == [outside / "y.csv"]


@spec("T13")
def test_decimal_cast_rounds_half_away_from_zero(con):
    """Confirms spike S-T13 on the hardened connection."""
    c, *_ = con
    got = c.execute("SELECT CAST('2.345' AS DECIMAL(38,2)), CAST('-2.345' AS DECIMAL(38,2)), "
                    "CAST('2.5' AS DECIMAL(38,0))").fetchone()
    assert [str(v) for v in got] == ["2.35", "-2.35", "3"]
