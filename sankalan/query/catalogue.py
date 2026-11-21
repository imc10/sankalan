"""Catalogue reads and writes. All catalogue SQL outside the schema DDL lives here (V3-1).

Every function takes a DuckDB cursor (``con``) and is called only inside a Job or during start-up, never on the
UI thread. Functions that write several tables run inside a transaction opened by the caller unless their name
says otherwise.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sankalan.model.rule import Rule
from sankalan.model.run import NewRun, RunOutput, RunRow
from sankalan.model.template import Column, DefaultOutput, Template, check_change, settings_from_dict


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


def template_version(con, template_id: str) -> int:
    return int(con.execute("SELECT version FROM template WHERE id = ?", [template_id]).fetchone()[0])


def template_snapshot(con, template_id: str, version: int | None = None) -> dict:
    """The saved snapshot of a template version (TPL-7); the current version when ``version`` is None."""
    if version is None:
        version = template_version(con, template_id)
    row = con.execute("SELECT snapshot FROM template_version WHERE template_id = ? AND version = ?",
                      [template_id, version]).fetchone()
    return json.loads(row[0]) if row else {}


def load_rules(con, template_id: str) -> list[Rule]:
    rows = con.execute("SELECT id, column_id, rule_type, settings, severity FROM rule WHERE template_id = ? "
                       "ORDER BY position", [template_id]).fetchall()
    return [Rule(r[0], r[1], r[2], json.loads(r[3]), r[4]) for r in rows]


def save_rules(con, template_id: str, rules: list[Rule]) -> int:
    """Replace the template's rules and save a new template version with them (VR-5 "Save to template", TPL-7).
    Opens its own transaction. Returns the new version number."""
    with Transaction(con):
        version = template_version(con, template_id) + 1
        snapshot = template_snapshot(con, template_id)
        snapshot["rules"] = [r.to_dict() for r in rules]
        now = _now()
        con.execute("DELETE FROM rule WHERE template_id = ?", [template_id])
        for pos, r in enumerate(rules):
            con.execute("INSERT INTO rule (template_id, id, column_id, rule_type, settings, severity, position) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [template_id, r.id, r.column_id, r.type, json.dumps(r.settings, ensure_ascii=False),
                         r.severity, pos])
        con.execute("UPDATE template SET version = ?, modified_on = ? WHERE id = ?", [version, now, template_id])
        con.execute("INSERT INTO template_version VALUES (?, ?, ?, ?)",
                    [template_id, version, now, json.dumps(snapshot, ensure_ascii=False)])
    return version


# ---------------------------------------------------------------------------------------------- whole templates
def template_has_runs(con, template_id: str) -> bool:
    """True once the template has a committed run: column types and decimals are then fixed (TPL-9, MAP-12)."""
    return bool(con.execute("SELECT count(*) FROM run WHERE template_id = ?", [template_id]).fetchone()[0])


def _write_template(con, t: Template, version: int, now: datetime, created: bool) -> None:
    """Write every table of a template at ``version``. Call inside a transaction."""
    settings = json.dumps(t.settings_dict(), ensure_ascii=False)
    if created:
        con.execute("INSERT INTO template VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [t.id, t.client_id, t.name, version, now, now, settings])
    else:
        con.execute("UPDATE template SET name = ?, version = ?, modified_on = ?, settings = ? WHERE id = ?",
                    [t.name, version, now, settings, t.id])
    for table in ("template_column", "rule", "default_output"):
        con.execute(f"DELETE FROM {table} WHERE template_id = ?", [t.id])
    for pos, c in enumerate(t.columns):
        con.execute("INSERT INTO template_column VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [t.id, c.id, c.name, c.type, c.decimals, c.date_format, pos,
                     json.dumps(c.aliases, ensure_ascii=False), c.totals_check, c.removed])
    for pos, r in enumerate(t.rules):
        con.execute("INSERT INTO rule (template_id, id, column_id, rule_type, settings, severity, position) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [t.id, r.id, r.column_id, r.type, json.dumps(r.settings, ensure_ascii=False), r.severity, pos])
    for pos, o in enumerate(t.outputs, 1):
        con.execute("INSERT INTO default_output VALUES (?, ?, ?, ?)",
                    [t.id, pos, o.name, json.dumps(o.definition, ensure_ascii=False)])
    snapshot = t.snapshot()
    con.execute("INSERT INTO template_version VALUES (?, ?, ?, ?)",
                [t.id, version, now, json.dumps(snapshot, ensure_ascii=False)])
    t.version = version


def create_template(con, t: Template) -> str:
    """A new template at version 1 (TPL-3). Opens its own transaction."""
    if not t.id:
        t.id = new_id()
    check_change(None, t, has_runs=False)
    with Transaction(con):
        _write_template(con, t, 1, _now(), created=True)
    return t.id


def save_template_in(con, t: Template) -> int:
    """Save every setting as a new version (TPL-7) inside the caller's transaction (the run commit uses this for
    aliases learned and columns added in the run). Raises ``TemplateError`` for a change that isn't allowed."""
    before = load_template(con, t.id)
    check_change(before, t, has_runs=template_has_runs(con, t.id))
    version = template_version(con, t.id) + 1
    _write_template(con, t, version, _now(), created=False)
    return version


def save_template(con, t: Template) -> int:
    """Save every setting as a new template version (TPL-7). Opens its own transaction. Returns the version."""
    with Transaction(con):
        return save_template_in(con, t)


def load_template(con, template_id: str) -> Template:
    """The template as currently saved, with its columns (ordered), rules, default outputs and settings."""
    row = con.execute("SELECT client_id, name, version, settings FROM template WHERE id = ?",
                      [template_id]).fetchone()
    if row is None:
        raise KeyError(template_id)
    client_id, name, version, settings_json = row
    settings = json.loads(settings_json or "{}")
    cols = [Column(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), bool(r[6]), bool(r[7]))
            for r in con.execute("SELECT id, name, type, decimals, date_format, aliases, totals_check, removed "
                                 "FROM template_column WHERE template_id = ? ORDER BY position",
                                 [template_id]).fetchall()]
    outputs = [DefaultOutput(r[0], json.loads(r[1])) for r in con.execute(
        "SELECT name, definition FROM default_output WHERE template_id = ? ORDER BY position",
        [template_id]).fetchall()]
    source = settings.get("source") if isinstance(settings.get("source"), dict) else None
    return Template(template_id, client_id, name, settings_from_dict(source), cols, load_rules(con, template_id),
                    outputs, dict(settings.get("export") or {}), int(version), bool(settings.get("checks", True)))


def duplicate_template(con, template_id: str, name: str, client_id: str | None = None) -> str:
    """A copy with every setting (columns, aliases, types, decimals, rules, default outputs, export defaults) and
    no runs or saved analyses (TPL-4). The copy starts at version 1 and its types are editable until its own first
    commit (C2-07)."""
    t = load_template(con, template_id).copy()
    t.id = new_id()
    t.name = name
    if client_id is not None:
        t.client_id = client_id
    for o in t.outputs:
        o.definition["template_id"] = t.id
    return create_template(con, t)


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


def run_details(con, run_id: str) -> dict | None:
    """One committed run for the Run screen (RUN-2, RUN-12, C6): the run row with its JSON fields parsed, its files
    and its saved outputs. None when no such run."""
    row = con.execute(f"SELECT {_RUN_COLS}, left_out_by_reason, errors, warnings, run_changes, totals, checks, "
                      f"text_counts FROM run WHERE id = ?", [run_id]).fetchone()
    if row is None:
        return None
    keys = [k.strip() for k in _RUN_COLS.split(",")] + ["left_out_by_reason", "errors", "warnings", "run_changes",
                                                        "totals", "checks", "text_counts"]
    out = dict(zip(keys, row))
    for k in ("left_out_by_reason", "run_changes", "totals", "text_counts"):
        out[k] = json.loads(out[k])
    out["label"] = RunRow(*row[:len(_RUN_COLS.split(","))]).label
    fcols = ("file_index", "file_name", "path", "size", "modified", "sheet", "sha256", "header_row", "rows_read",
             "hidden_rows", "sheets_skipped", "duplicate_decision", "sheets_chosen")
    out["files"] = []
    for r in con.execute(f"SELECT {', '.join(fcols)} FROM run_file WHERE run_id = ? ORDER BY file_index",
                         [run_id]).fetchall():
        f = dict(zip(fcols, r))
        f["sheets_skipped"] = json.loads(f["sheets_skipped"])
        out["files"].append(f)
    out["outputs"] = run_outputs(con, run_id)
    return out


def run_outputs(con, run_id: str) -> list[RunOutput]:
    """A run's saved default outputs with the definition used for that run (DO-6) and the headers stored at commit
    (T50), in order."""
    return [RunOutput(r[0], r[1], json.loads(r[2]), r[3], json.loads(r[4])) for r in con.execute(
        "SELECT position, name, definition, file, headers FROM run_output WHERE run_id = ? ORDER BY position",
        [run_id]).fetchall()]


def run_issue_counts(con, run_id: str) -> list[tuple]:
    """(rule, file index, sheet, errors, warnings) stored at commit (ISS-1)."""
    return [tuple(r) for r in con.execute(
        "SELECT rule, file_index, sheet, errors, warnings FROM run_issue_count WHERE run_id = ? "
        "ORDER BY file_index, rule", [run_id]).fetchall()]


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
    con.execute("INSERT INTO run VALUES (?, ?, ?, ?, ?, ?, false, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        run_id, run.template_id, number, run.template_version, _now(), run.status, run.comment, run.rows_read,
        run.rows_loaded, run.rows_left_out, json.dumps(run.left_out_by_reason), run.errors, run.warnings,
        json.dumps(run.run_changes, ensure_ascii=False), json.dumps(run.totals, ensure_ascii=False),
        bool(run.checks), json.dumps({k: int(v) for k, v in run.text_counts.items()})])
    for f in run.files:
        con.execute("INSERT INTO run_file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            run_id, f.file_index, f.file_name, f.path, f.size, f.modified, f.sheet, f.sha256, f.header_row,
            f.rows_read, f.hidden_rows, json.dumps(f.sheets_skipped, ensure_ascii=False), f.duplicate_decision,
            bool(f.sheets_chosen)])
    for c in run.issue_counts:
        con.execute("INSERT INTO run_issue_count VALUES (?, ?, ?, ?, ?, ?)",
                    [run_id, c.rule, c.file_index, c.sheet, c.errors, c.warnings])
    for o in run.outputs:
        con.execute("INSERT INTO run_output VALUES (?, ?, ?, ?, ?, ?)",
                    [run_id, o.position, o.name, json.dumps(o.definition, ensure_ascii=False), o.file,
                     json.dumps(list(o.headers), ensure_ascii=False)])
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


# ---------------------------------------------------------------------------------------------- screens C1, C2, C4 (Phase 7)
def client_rows(con) -> list[tuple]:
    """C1 grid (UX-1): (id, name, templates, runs, rows stored, last loaded on) per client."""
    return [tuple(r) for r in con.execute("""
        SELECT c.id, c.name,
               (SELECT count(*) FROM template t WHERE t.client_id = c.id),
               (SELECT count(*) FROM run r JOIN template t ON r.template_id = t.id WHERE t.client_id = c.id),
               (SELECT coalesce(sum(r.rows_loaded), 0) FROM run r JOIN template t ON r.template_id = t.id
                 WHERE t.client_id = c.id),
               (SELECT max(r.loaded_on) FROM run r JOIN template t ON r.template_id = t.id WHERE t.client_id = c.id)
        FROM client c ORDER BY c.name""").fetchall()]


def client_names(con) -> dict[str, str]:
    """id -> name of every client (name checks are made in Python, ignoring case: C1-04)."""
    return {r[0]: r[1] for r in con.execute("SELECT id, name FROM client").fetchall()}


def client_name(con, client_id: str) -> str | None:
    row = con.execute("SELECT name FROM client WHERE id = ?", [client_id]).fetchone()
    return row[0] if row else None


def rename_client(con, client_id: str, name: str) -> None:
    con.execute("UPDATE client SET name = ? WHERE id = ?", [name, client_id])


def template_names(con, client_id: str) -> dict[str, str]:
    """id -> name of the client's templates (template names are unique within a client: C2-05)."""
    return {r[0]: r[1] for r in con.execute("SELECT id, name FROM template WHERE client_id = ?",
                                            [client_id]).fetchall()}


def template_rows(con, client_id: str) -> list[tuple]:
    """C2 grid (UX-2): (id, name, active columns, default outputs, runs, rows stored, last loaded on, modified)."""
    return [tuple(r) for r in con.execute("""
        SELECT t.id, t.name,
               (SELECT count(*) FROM template_column c WHERE c.template_id = t.id AND NOT c.removed),
               (SELECT count(*) FROM default_output o WHERE o.template_id = t.id),
               (SELECT count(*) FROM run r WHERE r.template_id = t.id),
               (SELECT coalesce(sum(r.rows_loaded), 0) FROM run r WHERE r.template_id = t.id),
               (SELECT max(r.loaded_on) FROM run r WHERE r.template_id = t.id),
               t.modified_on
        FROM template t WHERE t.client_id = ? ORDER BY t.name""", [client_id]).fetchall()]


def template_header(con, template_id: str) -> tuple | None:
    """C4 header (UX-4): (client id, client name, template name, runs, rows stored, last loaded on)."""
    row = con.execute("""
        SELECT t.client_id, c.name, t.name,
               (SELECT count(*) FROM run r WHERE r.template_id = t.id),
               (SELECT coalesce(sum(r.rows_loaded), 0) FROM run r WHERE r.template_id = t.id),
               (SELECT max(r.loaded_on) FROM run r WHERE r.template_id = t.id)
        FROM template t JOIN client c ON c.id = t.client_id WHERE t.id = ?""", [template_id]).fetchone()
    return tuple(row) if row else None


def run_rows(con, template_id: str) -> list[tuple]:
    """C4 Runs grid (UX-4, RUN-2), newest first: (id, run number, loaded on, file names (list, in file order),
    rows loaded, errors, warnings, status, comment, damaged, loaded with checks)."""
    rows = con.execute("""
        SELECT r.id, r.run_number, r.loaded_on, r.rows_loaded, r.errors, r.warnings, r.status, r.comment, r.damaged,
               r.checks
        FROM run r WHERE r.template_id = ? ORDER BY r.run_number DESC""", [template_id]).fetchall()
    files: dict[str, list[str]] = {}
    for run_id, name in con.execute("""
            SELECT f.run_id, f.file_name FROM run_file f JOIN run r ON r.id = f.run_id
            WHERE r.template_id = ? ORDER BY f.run_id, f.file_index""", [template_id]).fetchall():
        names = files.setdefault(run_id, [])
        if name not in names:                       # one row per file and sheet; a file is listed once
            names.append(name)
    return [(r[0], r[1], r[2], files.get(r[0], []), r[3], r[4], r[5], r[6], r[7], r[8], r[9]) for r in rows]


def latest_run(con, template_id: str) -> tuple | None:
    """The latest committed run (DO-8 preview, VR-8 Test rules): (id, run number, rows loaded, loaded on)."""
    row = con.execute("SELECT id, run_number, rows_loaded, loaded_on FROM run WHERE template_id = ? "
                      "ORDER BY run_number DESC LIMIT 1", [template_id]).fetchone()
    return tuple(row) if row else None


def overview(con) -> tuple[int, int, int, int]:
    """(clients, templates, runs, rows stored) for the C1 subtitle and storage footer."""
    row = con.execute("""SELECT (SELECT count(*) FROM client), (SELECT count(*) FROM template),
                                (SELECT count(*) FROM run), (SELECT coalesce(sum(rows_loaded), 0) FROM run)""").fetchone()
    return tuple(int(x) for x in row)


def saved_analysis_count(con, *, client_id: str | None = None, template_id: str | None = None) -> int:
    if template_id is not None:
        return int(con.execute("SELECT count(*) FROM saved_analysis WHERE template_id = ?",
                               [template_id]).fetchone()[0])
    return int(con.execute("SELECT count(*) FROM saved_analysis a JOIN template t ON t.id = a.template_id "
                           "WHERE t.client_id = ?", [client_id]).fetchone()[0])


def run_delete_figures(con, run_id: str) -> tuple | None:
    """For dialog 7.2: (run number, template name, rows loaded, saved outputs, loaded with checks)."""
    row = con.execute("""SELECT r.run_number, t.name, r.rows_loaded,
                                (SELECT count(*) FROM run_output o WHERE o.run_id = r.id), r.checks
                         FROM run r JOIN template t ON t.id = r.template_id WHERE r.id = ?""", [run_id]).fetchone()
    return tuple(row) if row else None


def insert_saved_analysis(con, template_id: str, name: str, definition: dict, analysis_id: str | None = None) -> str:
    """A saved analysis (ANA-1): the definition only; runs are never stored (D33)."""
    aid = analysis_id or new_id()
    now = _now()
    con.execute("INSERT INTO saved_analysis VALUES (?, ?, ?, ?, ?, ?)",
                [aid, template_id, name, json.dumps(definition, ensure_ascii=False), now, now])
    return aid


# ---------------------------------------------------------------------------------------------- saved analyses (Phase 10)
def saved_analysis_rows(con) -> list[tuple]:
    """6.1 grid (UX-10, ANA-1): (id, name, client id, client name, template id, template name, saved on)."""
    return [tuple(r) for r in con.execute("""
        SELECT a.id, a.name, c.id, c.name, t.id, t.name, a.created_on
        FROM saved_analysis a JOIN template t ON t.id = a.template_id JOIN client c ON c.id = t.client_id
        ORDER BY a.name""").fetchall()]


def saved_analysis(con, analysis_id: str) -> tuple | None:
    """(id, template id, name, definition (dict), saved on)."""
    row = con.execute("SELECT id, template_id, name, definition, created_on FROM saved_analysis WHERE id = ?",
                      [analysis_id]).fetchone()
    return (row[0], row[1], row[2], json.loads(row[3]), row[4]) if row else None


def saved_analysis_names(con, template_id: str) -> dict[str, str]:
    """id -> name of the template's saved analyses (names are unique within a template, ANA-1)."""
    return {r[0]: r[1] for r in con.execute("SELECT id, name FROM saved_analysis WHERE template_id = ?",
                                            [template_id]).fetchall()}


def rename_saved_analysis(con, analysis_id: str, name: str) -> None:
    con.execute("UPDATE saved_analysis SET name = ?, modified_on = ? WHERE id = ?", [name, _now(), analysis_id])


def delete_saved_analysis(con, analysis_id: str) -> None:
    con.execute("DELETE FROM saved_analysis WHERE id = ?", [analysis_id])


def template_choices(con) -> list[tuple]:
    """The New analysis Client and Template lists: (client id, client name, template id, template name), every
    client with at least one template, by client then template name."""
    return [tuple(r) for r in con.execute("""
        SELECT c.id, c.name, t.id, t.name FROM template t JOIN client c ON c.id = t.client_id
        ORDER BY lower(c.name), c.name, lower(t.name), t.name""").fetchall()]
