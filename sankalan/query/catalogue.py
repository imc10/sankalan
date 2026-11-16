"""Catalogue reads and writes. All catalogue SQL outside the schema DDL lives here (V3-1).

Every function takes a DuckDB cursor (``con``) and is called only inside a Job or during start-up, never on the
UI thread. Functions that write several tables run inside a transaction opened by the caller unless their name
says otherwise.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sankalan.model.run import NewRun, RunRow


def new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Transaction:
    """``with Transaction(con):`` BEGIN … COMMIT, or ROLLBACK on any exception."""

    def __init__(self, con):
        self.con = con

    def __enter__(self):
        self.con.execute("BEGIN TRANSACTION")
        return self.con

    def __exit__(self, exc_type, exc, tb):
        self.con.execute("COMMIT" if exc_type is None else "ROLLBACK")
        return False


# ---------------------------------------------------------------------------------------------- clients, templates
def insert_client(con, name: str, client_id: str | None = None) -> str:
    cid = client_id or new_id()
    con.execute("INSERT INTO client VALUES (?, ?, ?)", [cid, name, _now()])
    return cid


def insert_template(con, client_id: str, name: str, settings: dict | None = None,
                    template_id: str | None = None) -> str:
    """A new template at version 1, with its first template_version snapshot (TPL-7)."""
    tid = template_id or new_id()
    now = _now()
    settings_json = json.dumps(settings or {}, ensure_ascii=False)
    with Transaction(con):
        con.execute("INSERT INTO template VALUES (?, ?, ?, 1, ?, ?, ?)", [tid, client_id, name, now, now,
                                                                          settings_json])
        con.execute("INSERT INTO template_version VALUES (?, 1, ?, ?)",
                    [tid, now, json.dumps({"settings": settings or {}}, ensure_ascii=False)])
    return tid


def template_ids(con, client_id: str | None = None) -> list[str]:
    if client_id is None:
        return [r[0] for r in con.execute("SELECT id FROM template ORDER BY id").fetchall()]
    return [r[0] for r in con.execute("SELECT id FROM template WHERE client_id = ? ORDER BY id",
                                      [client_id]).fetchall()]


def client_ids(con) -> list[str]:
    return [r[0] for r in con.execute("SELECT id FROM client ORDER BY id").fetchall()]


# ---------------------------------------------------------------------------------------------- runs
_RUN_COLS = ("id, template_id, run_number, template_version, loaded_on, status, damaged, comment, rows_read, "
             "rows_loaded, rows_left_out")


def list_runs(con, template_id: str | None = None) -> list[RunRow]:
    """Committed runs, by template then Run ID."""
    if template_id is None:
        rows = con.execute(f"SELECT {_RUN_COLS} FROM run ORDER BY template_id, run_number").fetchall()
    else:
        rows = con.execute(f"SELECT {_RUN_COLS} FROM run WHERE template_id = ? ORDER BY run_number",
                           [template_id]).fetchall()
    return [RunRow(*r) for r in rows]


def run_locations(con) -> list[tuple[str, str]]:
    """(template_id, run id) of every catalogue run: the folders that should exist."""
    return [tuple(r) for r in con.execute("SELECT template_id, id FROM run").fetchall()]


def set_damaged(con, run_ids: list[str], damaged: bool = True) -> None:
    for rid in run_ids:
        con.execute("UPDATE run SET damaged = ? WHERE id = ?", [damaged, rid])


def insert_run(con, run_id: str, run: NewRun) -> int:
    """Issue the next Run ID number for the template and insert the run with its files, issue counts and outputs.
    Must run inside the commit transaction: this is the commit point (T8). Numbers are never reused (T22): the
    counter only goes up, and deleting a run never lowers it."""
    row = con.execute("SELECT last_number FROM run_id_counter WHERE template_id = ?", [run.template_id]).fetchone()
    number = (row[0] if row else 0) + 1
    if row:
        con.execute("UPDATE run_id_counter SET last_number = ? WHERE template_id = ?", [number, run.template_id])
    else:
        con.execute("INSERT INTO run_id_counter VALUES (?, ?)", [run.template_id, number])
    con.execute("INSERT INTO run VALUES (?, ?, ?, ?, ?, ?, false, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        run_id, run.template_id, number, run.template_version, _now(), run.status, run.comment, run.rows_read,
        run.rows_loaded, run.rows_left_out, json.dumps(run.left_out_by_reason), run.errors, run.warnings,
        json.dumps(run.run_changes, ensure_ascii=False), json.dumps(run.totals, ensure_ascii=False)])
    for f in run.files:
        con.execute("INSERT INTO run_file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            run_id, f.file_index, f.file_name, f.path, f.size, f.modified, f.sheet, f.sha256, f.header_row,
            f.rows_read, f.hidden_rows, json.dumps(f.sheets_skipped, ensure_ascii=False), f.duplicate_decision])
    for c in run.issue_counts:
        con.execute("INSERT INTO run_issue_count VALUES (?, ?, ?, ?, ?, ?)",
                    [run_id, c.rule, c.file_index, c.sheet, c.errors, c.warnings])
    for o in run.outputs:
        con.execute("INSERT INTO run_output VALUES (?, ?, ?, ?, ?)",
                    [run_id, o.position, o.name, json.dumps(o.definition, ensure_ascii=False), o.file])
    return number


def last_run_number(con, template_id: str) -> int:
    row = con.execute("SELECT last_number FROM run_id_counter WHERE template_id = ?", [template_id]).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------------------------- deletes (RUN-9, TPL-2, TPL-4)
def _delete_run_rows(con, run_ids: list[str]) -> None:
    for rid in run_ids:
        for table in ("run_file", "run_issue_count", "run_output"):
            con.execute(f"DELETE FROM {table} WHERE run_id = ?", [rid])
        con.execute("DELETE FROM run WHERE id = ?", [rid])


def delete_run_records(con, run_id: str) -> str | None:
    """Remove one run's records. Returns its template ID, or None when no such run. The Run ID counter is kept."""
    row = con.execute("SELECT template_id FROM run WHERE id = ?", [run_id]).fetchone()
    if not row:
        return None
    _delete_run_rows(con, [run_id])
    return row[0]


def delete_template_records(con, template_id: str) -> None:
    """Remove a template with its versions, columns, rules, default outputs, runs and saved analyses."""
    run_ids = [r[0] for r in con.execute("SELECT id FROM run WHERE template_id = ?", [template_id]).fetchall()]
    _delete_run_rows(con, run_ids)
    for table in ("template_version", "template_column", "rule", "default_output", "saved_analysis",
                  "run_id_counter"):
        con.execute(f"DELETE FROM {table} WHERE template_id = ?", [template_id])
    con.execute("DELETE FROM template WHERE id = ?", [template_id])


def delete_client_records(con, client_id: str) -> list[str]:
    """Remove a client and everything under it. Returns the template IDs removed (their folders go next)."""
    tids = template_ids(con, client_id)
    for tid in tids:
        delete_template_records(con, tid)
    con.execute("DELETE FROM client WHERE id = ?", [client_id])
    return tids


# ---------------------------------------------------------------------------------------------- figures (UX-1)
def rows_stored(con, client_id: str | None = None) -> int:
    """Sum of rows loaded over committed runs (C1 Rows stored)."""
    if client_id is None:
        row = con.execute("SELECT coalesce(sum(rows_loaded), 0) FROM run").fetchone()
    else:
        row = con.execute("SELECT coalesce(sum(r.rows_loaded), 0) FROM run r JOIN template t "
                          "ON r.template_id = t.id WHERE t.client_id = ?", [client_id]).fetchone()
    return int(row[0])


def counts(con) -> dict:
    """Row counts per catalogue table: used to check a moved data folder."""
    from sankalan.db.catalogue import TABLES
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}


def checkpoint(con) -> None:
    con.execute("CHECKPOINT")


# ---------------------------------------------------------------------------------------------- duplicate contents (RUN-7)
def runs_with_sha256(con, template_id: str, shas: list[str]) -> dict[str, tuple[int, datetime]]:
    """For each SHA-256 already loaded in a committed run of this template: (latest run number, its loaded-on time).
    The check is per template only (C2-08 scope, decision confirmed 16-11-2026)."""
    shas = sorted({s for s in shas if s})
    if not shas:
        return {}
    marks = ", ".join("?" for _ in shas)
    rows = con.execute(
        f"SELECT f.sha256, r.run_number, r.loaded_on FROM run_file f JOIN run r ON r.id = f.run_id "
        f"WHERE r.template_id = ? AND f.sha256 IN ({marks}) ORDER BY r.run_number", [template_id, *shas]).fetchall()
    out: dict[str, tuple[int, datetime]] = {}
    for sha, number, loaded_on in rows:
        out[sha] = (number, loaded_on)          # ordered by run number, so the latest run wins
    return out
