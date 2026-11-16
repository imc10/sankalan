"""The catalogue: schema, upgrades by schema_version, and start-up backups (T8, T10).

The catalogue (``<data folder>\\catalogue.duckdb``) records which clients, templates, runs and saved analyses exist.
A run is visible only once its catalogue row exists, so the row is the commit point (T8). Definitions are stored
as JSON text and parsed in Python, so no DuckDB JSON extension is needed.

Table names follow the Technical Spec, except that the spec's ``column`` table is ``template_column`` here
(COLUMN is an SQL keyword). There are no foreign keys: DuckDB can't cascade, and the delete protocol removes
child rows explicitly in one transaction.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import duckdb

SCHEMA_VERSION = 1
BACKUPS_KEPT = 5

_V1 = [
    """CREATE TABLE schema_version (
        version INTEGER NOT NULL,
        upgraded_on TIMESTAMP NOT NULL)""",
    """CREATE TABLE client (
        id VARCHAR PRIMARY KEY,
        name VARCHAR NOT NULL,
        created_on TIMESTAMP NOT NULL)""",
    """CREATE TABLE template (
        id VARCHAR PRIMARY KEY,
        client_id VARCHAR NOT NULL,
        name VARCHAR NOT NULL,
        version INTEGER NOT NULL,           -- TPL-7: up by one on every save, stored with each run
        created_on TIMESTAMP NOT NULL,
        modified_on TIMESTAMP NOT NULL,
        settings VARCHAR NOT NULL)          -- JSON: sheets, header row, file pattern, ...""",
    """CREATE TABLE template_version (
        template_id VARCHAR NOT NULL,
        version INTEGER NOT NULL,
        saved_on TIMESTAMP NOT NULL,
        snapshot VARCHAR NOT NULL,          -- JSON: settings, columns, rules and default outputs (TPL-7)
        PRIMARY KEY (template_id, version))""",
    """CREATE TABLE template_column (
        template_id VARCHAR NOT NULL,
        id VARCHAR NOT NULL,                -- stable Parquet column name c001, c002, ... never reused
        name VARCHAR NOT NULL,
        type VARCHAR NOT NULL,              -- Text | Number | Date
        decimals INTEGER,                   -- Number only, 0-6 (T13)
        position INTEGER NOT NULL,
        aliases VARCHAR NOT NULL,           -- JSON list
        totals_check BOOLEAN NOT NULL,
        removed BOOLEAN NOT NULL,
        PRIMARY KEY (template_id, id))""",
    """CREATE TABLE rule (
        template_id VARCHAR NOT NULL,
        column_id VARCHAR NOT NULL,
        rule_type VARCHAR NOT NULL,         -- VAL-1 ... VAL-9
        settings VARCHAR NOT NULL,          -- JSON
        severity VARCHAR NOT NULL,          -- Error | Warning
        position INTEGER NOT NULL)""",
    """CREATE TABLE default_output (
        template_id VARCHAR NOT NULL,
        position INTEGER NOT NULL,
        name VARCHAR NOT NULL,
        definition VARCHAR NOT NULL,        -- JSON, compiled to SQL by query/compiler.py
        PRIMARY KEY (template_id, position))""",
    """CREATE TABLE run (
        id VARCHAR PRIMARY KEY,             -- internal ID; also the run folder name t\\<template>\\runs\\<id>
        template_id VARCHAR NOT NULL,
        run_number INTEGER NOT NULL,        -- shown as R-0001; per template, never reused (T22)
        template_version INTEGER NOT NULL,
        loaded_on TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,            -- committed | committed_override
        damaged BOOLEAN NOT NULL,           -- folder missing at start-up
        comment VARCHAR NOT NULL,
        rows_read BIGINT NOT NULL,
        rows_loaded BIGINT NOT NULL,
        rows_left_out BIGINT NOT NULL,
        left_out_by_reason VARCHAR NOT NULL,  -- JSON {"blank": n, "errors": n, "duplicates": n} (RUN-12)
        errors BIGINT NOT NULL,
        warnings BIGINT NOT NULL,
        run_changes VARCHAR NOT NULL,       -- JSON: run-only rule changes and aliases
        totals VARCHAR NOT NULL)            -- JSON: per ticked column Input / Loaded / Left out as text (T20)""",
    """CREATE TABLE run_file (
        run_id VARCHAR NOT NULL,
        file_index INTEGER NOT NULL,        -- the _src_file value in the Parquet files
        file_name VARCHAR NOT NULL,
        path VARCHAR NOT NULL,
        size BIGINT NOT NULL,
        modified TIMESTAMP,
        sheet VARCHAR NOT NULL,
        sha256 VARCHAR NOT NULL,
        header_row INTEGER,
        rows_read BIGINT NOT NULL,
        hidden_rows BIGINT NOT NULL,
        sheets_skipped VARCHAR NOT NULL,    -- JSON list of hidden sheets skipped
        duplicate_decision VARCHAR NOT NULL,  -- RUN-7
        PRIMARY KEY (run_id, file_index))""",
    """CREATE TABLE run_issue_count (
        run_id VARCHAR NOT NULL,
        rule VARCHAR NOT NULL,
        file_index INTEGER NOT NULL,
        sheet VARCHAR NOT NULL,
        errors BIGINT NOT NULL,
        warnings BIGINT NOT NULL)""",
    """CREATE TABLE run_output (
        run_id VARCHAR NOT NULL,
        position INTEGER NOT NULL,
        name VARCHAR NOT NULL,
        definition VARCHAR NOT NULL,        -- JSON: the definition used for this run (DO-6)
        file VARCHAR NOT NULL,              -- outputs\\<n>.parquet, relative to the run folder
        PRIMARY KEY (run_id, position))""",
    """CREATE TABLE run_id_counter (
        template_id VARCHAR PRIMARY KEY,
        last_number INTEGER NOT NULL)       -- last Run ID number issued (T22)""",
    """CREATE TABLE saved_analysis (
        id VARCHAR PRIMARY KEY,
        template_id VARCHAR NOT NULL,
        name VARCHAR NOT NULL,
        definition VARCHAR NOT NULL,
        created_on TIMESTAMP NOT NULL,
        modified_on TIMESTAMP NOT NULL)""",
]

# version -> statements that take the catalogue from (version - 1) to version. Parquet files are never rewritten.
MIGRATIONS: dict[int, list[str]] = {1: _V1}
TABLES = ("schema_version", "client", "template", "template_version", "template_column", "rule", "default_output",
          "run", "run_file", "run_issue_count", "run_output", "run_id_counter", "saved_analysis")


class CatalogueTooNew(Exception):
    """The catalogue was written by a newer Sankalan than this one."""


def current_version(con: duckdb.DuckDBPyConnection) -> int:
    has = con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'schema_version' "
                      "AND database_name = current_database()").fetchone()[0]
    if not has:
        return 0
    row = con.execute("SELECT max(version) FROM schema_version").fetchone()
    return int(row[0] or 0)


def ensure_schema(con: duckdb.DuckDBPyConnection, target: int = SCHEMA_VERSION) -> int:
    """Create a new catalogue or upgrade an older one, each step in its own transaction. Returns the version."""
    version = current_version(con)
    if version > target:
        raise CatalogueTooNew(version)
    for v in range(version + 1, target + 1):
        con.execute("BEGIN TRANSACTION")
        try:
            for stmt in MIGRATIONS[v]:
                con.execute(stmt)
            con.execute("INSERT INTO schema_version VALUES (?, current_localtimestamp())", [v])
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
    return max(version, target)


# ---------------------------------------------------------------------------------------------- backups (T10)
def backup(catalogue: Path, backups: Path, keep: int = BACKUPS_KEPT, now: datetime | None = None) -> Path | None:
    """Copy the catalogue (and its WAL, if a crash left one) into ``backups``; keep the newest ``keep`` copies.
    Call before the connection is opened, so the copy is consistent. Nothing to copy on the very first start."""
    if not catalogue.exists():
        return None
    backups.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S-%f")
    target = backups / f"catalogue-{stamp}.duckdb"
    n = 1
    while target.exists():
        target = backups / f"catalogue-{stamp}-{n}.duckdb"
        n += 1
    tmp = target.with_name(target.name + ".part")
    shutil.copy2(catalogue, tmp)
    wal = catalogue.with_name(catalogue.name + ".wal")
    if wal.exists():
        shutil.copy2(wal, target.with_name(target.name + ".wal"))
    os.replace(tmp, target)
    prune_backups(backups, keep)
    return target


def list_backups(backups: Path) -> list[Path]:
    """Backups, oldest first (names sort by time)."""
    if not backups.is_dir():
        return []
    return sorted(p for p in backups.glob("catalogue-*.duckdb"))


def prune_backups(backups: Path, keep: int = BACKUPS_KEPT) -> None:
    for p in backups.glob("*.part"):
        p.unlink(missing_ok=True)
    copies = list_backups(backups)
    for old in copies[:max(0, len(copies) - keep)]:
        old.unlink(missing_ok=True)
        old.with_name(old.name + ".wal").unlink(missing_ok=True)
