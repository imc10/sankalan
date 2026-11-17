r"""The run pipeline, headless: the New run wizard's state from Files to Commit (RUN-2 to RUN-14, DO-1 to DO-8,
MAP-5 to MAP-7, MAP-11 to MAP-13, TPL-6, TPL-8, T18 to T22).

A ``RunSession`` holds one run in progress. Steps that touch files or DuckDB are Job work: call them as
``runner.run(name, lambda ctx: session.step(ctx, ...))`` (the commit with ``cancellable=False``). Everything else
is plain state the wizard reads.

    Files      add_files / remove_file / load_anyway → files_next() → MappingPlan (skipped when TPL-6 holds)
    Mapping    session.mapping.map / leave_null / leave_out / add_column → mapping_next()
    Validate   validate (read + convert + scan) · edit_rules (scan only; optionally Save to template) · recheck
               → leave_validate(reason=None | override reason): the split Job (T18)
    Outputs    run_outputs (per-output status; cancel → Retry by running it again) · skipped with none (DO-4)
    Commit     check_totals · commit_blockers(comment) · commit (rename + one catalogue transaction, T8)
    Leave      discard(): the staging folder is deleted and nothing is kept (RUN-14)

Template changes made in a run: "Save to template" on a rule edit saves a new template version at once (VR-5);
aliases learned (MAP-5) and columns added (MAP-7) are saved in the commit transaction, so a discarded run never
changes the template.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sankalan import mapping as mapping_mod
from sankalan.db import datafolder
from sankalan.db.datafolder import DataFolder, Staging
from sankalan.ingest import stage
from sankalan.ingest.probe import ERROR, READY, REFUSED, SKIPPED, FileSheet
from sankalan.jobs import JobContext
from sankalan.model.definition import Definition
from sankalan.model.rule import UNIQUE, Rule, copy_rules, rule_changes
from sankalan.model.run import STATUS_COMMITTED, STATUS_OVERRIDE, IssueCount, NewRun, RunFile, RunOutput, run_label
from sankalan.model.template import Column, Template
from sankalan.query import catalogue as q
from sankalan.query import convert, layer
from sankalan.query import totals as totals_q
from sankalan.query.split import LEFT_OUT, left_out_breakdown, split
from sankalan.validation import scan

COMMENT_MAX = 500                       # RUN-13
COMMIT_FREE_BYTES = 100 * 1024 * 1024   # decision confirmed 17-11-2026: commit needs 100 MB free on the data drive
FAULT_ENV = "SANKALAN_FAULT_TOTALS"     # RUNC-10, read only when running from source (decision confirmed 17-11-2026)
OUTPUTS_DIR = "outputs"

# step names (the wizard's step bar)
FILES, MAPPING, VALIDATE, OUTPUTS, COMMIT = "files", "mapping", "validate", "outputs", "commit"

# per-output status (DO-4, DO-5)
PENDING, RUNNING, DONE, FAILED, CANCELLED = "pending", "running", "done", "failed", "cancelled"

LOAD_ANYWAY = "load_anyway"             # RUN-7 duplicate decision


class RunBlocked(Exception):
    """A step can't go on yet; ``message`` says why in plain words."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def fault_from_env(environ=None, frozen: bool | None = None) -> dict[str, Decimal]:
    """RUNC-10 fault hook: ``SANKALAN_FAULT_TOTALS=c006:0.01,c008:-1`` adds the amounts to Loaded totals. Read only
    when running from source; the packaged app (``sys.frozen``) ignores it."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    text = (environ if environ is not None else os.environ).get(FAULT_ENV, "")
    if frozen or not text.strip():
        return {}
    out: dict[str, Decimal] = {}
    for item in text.split(","):
        cid, _, amount = item.partition(":")
        try:
            out[cid.strip()] = Decimal(amount.strip())
        except InvalidOperation:
            continue
    return out


@dataclass
class OutputState:
    position: int               # 1-based, the file outputs\<n>.parquet
    name: str
    definition: dict
    status: str = PENDING
    note: str | None = None     # "No dates in this run" (T21)
    result: layer.Result | None = None

    @property
    def file(self) -> str:
        return f"{OUTPUTS_DIR}/{self.position}.parquet"


@dataclass
class Validation:
    """The Validate step's figures (RUN-12, RUNV-01 to RUNV-03)."""
    scan: scan.ScanResult
    rows_read: int              # data rows + blank rows (RUNV-02, confirmed 17-11-2026)
    rows_to_load: int
    blank_rows: int
    hidden_rows: int
    hidden_sheets: list[str]

    @property
    def errors(self) -> int:
        return self.scan.errors

    @property
    def warnings(self) -> int:
        return self.scan.warnings

    @property
    def passed(self) -> bool:
        return self.scan.passed

    @property
    def left_out_on_override(self) -> int:
        """"N rows with errors will be left out" (7.1, T18)."""
        return self.scan.left_out


@dataclass
class Committed:
    run_id: str                 # internal ID, also the folder name
    number: int
    template_version: int

    @property
    def label(self) -> str:
        return run_label(self.number)


@dataclass
class RunSession:
    folder: DataFolder
    template: Template
    workers: int | None = None
    files: list[FileSheet] = field(default_factory=list)
    duplicate_decisions: dict[str, str] = field(default_factory=dict)      # path -> LOAD_ANYWAY
    mapping: mapping_mod.MappingPlan | None = None
    rules: list[Rule] = field(default_factory=list)                         # this run's rules (VR-5)
    staging: Staging | None = None
    validation: Validation | None = None
    override_reason: str | None = None
    split_done: bool = False
    outputs: list[OutputState] = field(default_factory=list)
    totals: list[totals_q.TotalsLine] | None = None
    saved_rule_changes: list[dict] = field(default_factory=list)
    committed: Committed | None = None

    def __post_init__(self):
        self.template = self.template.copy()
        if not self.rules:
            self.rules = copy_rules(self.template.rules)
        self._parts: list[stage.LoadPart] = []
        self._mapping_result: mapping_mod.MappingResult | None = None
        self._load: stage.LoadResult | None = None

    # ------------------------------------------------------------------------------------------ Files (step 1)
    @property
    def readable_files(self) -> list[FileSheet]:
        return [f for f in self.files if f.readable]

    def add_files(self, ctx: JobContext, paths) -> list[FileSheet]:
        """Probe newly added files (IN-1 to IN-15, RUN-7). Returns the new rows."""
        existing = [f.path for f in self.files if f.status not in (SKIPPED, REFUSED)]
        rows = stage.probe(ctx, [str(p) for p in paths], settings=self.template.source,
                           columns=self.template.columns, template_id=self.template.id, existing=existing,
                           workers=self.workers)
        self.files += [r for r in rows if r.status != REFUSED]
        self._invalidate(FILES)
        return rows

    def remove_file(self, path) -> None:
        """Remove a file from the run: Remove on a duplicate warning (RUN-7) or Exclude on an error (IN-15)."""
        key = str(path)
        self.files = [f for f in self.files if f.path != key]
        self.duplicate_decisions.pop(key, None)
        self._invalidate(FILES)

    def recheck_files(self, ctx: JobContext, paths=None) -> list[FileSheet]:
        """Re-check (IN-15, RUNF-06): probe files again where they are in the list, e.g. after closing Excel.
        ``paths`` defaults to every file in the list. A Load anyway decision is kept."""
        keys = list(dict.fromkeys(f.path for f in self.files)) if paths is None else [str(p) for p in paths]
        keys = [k for k in keys if any(f.path == k for f in self.files)]
        if not keys:
            return []
        others = [f.path for f in self.files if f.path not in keys and f.status not in (SKIPPED, REFUSED)]
        fresh = stage.probe(ctx, keys, settings=self.template.source, columns=self.template.columns,
                            template_id=self.template.id, existing=others, workers=self.workers)
        by_path: dict[str, list[FileSheet]] = {}
        for r in fresh:
            if r.status != REFUSED:
                by_path.setdefault(r.path, []).append(r)
        out: list[FileSheet] = []
        done: set[str] = set()
        for f in self.files:
            if f.path not in keys:
                out.append(f)
            elif f.path not in done:
                done.add(f.path)
                out += by_path.get(f.path, [])
        for r in [r for rs in by_path.values() for r in rs]:
            if r.duplicate_of and self.duplicate_decisions.get(r.path) == LOAD_ANYWAY:
                r.status = READY
        self.files = out
        self._invalidate(FILES)
        return [r for rs in by_path.values() for r in rs]

    def load_anyway(self, path) -> None:
        """RUN-7: keep a file whose contents were loaded in an earlier run; it shows as Ready."""
        key = str(path)
        for f in self.files:
            if f.path == key and f.duplicate_of:
                self.duplicate_decisions[key] = LOAD_ANYWAY
                f.status = READY
        self._invalidate(FILES)

    def files_blockers(self) -> list[str]:
        out = []
        if not self.readable_files:
            out.append("Add at least one file.")
        for f in self.files:
            if f.status == ERROR:
                out.append(f.message or f"{f.file_name} can't be read.")
            elif f.duplicate_of and f.path not in self.duplicate_decisions:
                out.append(f.message)
        return out

    def files_next(self) -> mapping_mod.MappingPlan:
        """Next on Files: the Mapping step's plan; ``plan.skip`` is True when every header matches (TPL-6)."""
        blockers = self.files_blockers()
        if blockers:
            raise RunBlocked(blockers[0])
        sheets = [mapping_mod.Sheet(i, f.file_name, f.sheet, list(f.headers))
                  for i, f in enumerate(self.readable_files)]
        self.mapping = mapping_mod.MappingPlan(self.template, sheets)
        self._invalidate(MAPPING)
        return self.mapping

    @property
    def mapping_skipped(self) -> bool:
        return self.mapping is not None and self.mapping.skip

    # ------------------------------------------------------------------------------------------ Mapping (step 2)
    def mapping_next(self) -> mapping_mod.MappingResult:
        """Next on Mapping: every decision made (MAP-13), else ``RunBlocked`` and ``mapping.first_undecided()``
        says where to go."""
        if self.mapping is None:
            raise RunBlocked("Add files first.")
        if not self.mapping.complete:
            raise RunBlocked("Some columns still need a decision.")
        self._mapping_result = self.mapping.result()
        files = self.readable_files
        self._parts = [stage.LoadPart.from_probe(i, f, self._mapping_result.mappings[i]) for i, f in enumerate(files)]
        self._invalidate(VALIDATE)
        return self._mapping_result

    @property
    def columns(self) -> list[Column]:
        """The run's columns: the template's plus any added in Mapping."""
        if self._mapping_result is not None:
            return self._mapping_result.columns
        return self.template.columns

    # ------------------------------------------------------------------------------------------ Validate (step 3)
    def validate(self, ctx: JobContext) -> Validation:
        """Read, convert and check the rules (RUN-3, VR-3). Also Re-check after a source is fixed (VR-6)."""
        if self._mapping_result is None:
            self.mapping_next()
        self._invalidate(VALIDATE)
        if self.staging is None or not self.staging.path.exists():
            self.staging = self.folder.new_staging()   # a cancelled or failed load deleted the last one
        (self.staging.path / LEFT_OUT).unlink(missing_ok=True)
        shutil.rmtree(self.staging.path / OUTPUTS_DIR, ignore_errors=True)
        names = {p.file_index: Path(p.path).name for p in self._parts}
        self._load = stage.load(ctx, self.folder, self.staging, self._parts, self.columns, workers=self.workers)
        result = scan.validate(ctx, self.staging, self.columns, self.rules, names)
        hidden_sheets = sorted({s for f in self.readable_files for s in f.hidden_sheets})
        ld = self._load
        self.validation = Validation(result, ld.rows_read + ld.blank_rows, ld.rows_loaded, ld.blank_rows,
                                     ld.hidden_rows, hidden_sheets)
        return self.validation

    recheck = validate

    def edit_rules(self, ctx: JobContext, rules: list[Rule], *, save_to_template: bool = False) -> Validation:
        """Edit rules for this run (VR-5, TPL-8): only the scan reruns. ``save_to_template`` also saves them as a
        new template version now (RUNV-10)."""
        rules = copy_rules(rules)
        scan.prepare(self.columns, rules)          # RuleError before anything changes
        if save_to_template:
            before = copy_rules(self.template.rules)
            fresh = q.load_template(ctx.cursor(), self.template.id)
            fresh.rules = copy_rules(rules)
            q.save_template(ctx.cursor(), fresh)
            self.template = fresh.copy()
            self.saved_rule_changes += rule_changes(before, rules)
            if self.mapping is not None:
                self.mapping.template = self.template
        self.rules = rules
        if self.validation is None or self.split_done:
            return self.validate(ctx)       # the split rewrote data.parquet: read again
        self._invalidate(OUTPUTS)
        names = {p.file_index: Path(p.path).name for p in self._parts}
        result = scan.validate(ctx, self.staging, self.columns, self.rules, names)
        v = self.validation
        self.validation = Validation(result, v.rows_read, v.rows_to_load, v.blank_rows, v.hidden_rows,
                                     v.hidden_sheets)
        return self.validation

    def leave_validate(self, ctx: JobContext, reason: str | None = None) -> tuple[int, int]:
        """Next, or Continue despite errors… with its reason (RUN-4, T18): split the staged rows into
        ``data.parquet`` and ``left_out.parquet``. Returns (rows loaded, rows left out)."""
        if self.validation is None:
            raise RunBlocked("Validate first.")
        if not self.validation.passed:
            if reason is None or not reason.strip():
                raise RunBlocked("Enter a reason to continue despite errors.")
            if len(reason) > COMMENT_MAX:
                raise RunBlocked(f"The reason can be at most {COMMENT_MAX} characters.")
        if self.split_done:
            raise RunBlocked("The rows have already been split; validate again to change the rules.")
        ctx.set_stage("Preparing rows to load")
        sc = self.validation.scan
        loaded, left = split(ctx.cursor(), self.staging.path, sc.issues, [r.id for r in sc.rules])
        self.split_done = True
        self.override_reason = None if self.validation.passed else reason
        self.outputs = [OutputState(i, o.name, o.definition) for i, o in enumerate(self.template.outputs, 1)]
        return loaded, left

    # ------------------------------------------------------------------------------------------ Outputs (step 4)
    @property
    def outputs_skipped(self) -> bool:
        """DO-4: no default outputs, so the step is skipped (RUNO-07)."""
        return self.split_done and not self.outputs

    @property
    def outputs_done(self) -> bool:
        return self.split_done and all(o.status == DONE for o in self.outputs)

    def run_outputs(self, ctx: JobContext) -> list[OutputState]:
        """Generate every output not yet done, in order, on this run's rows (DO-2, DO-4). Cancel or a failure
        marks the running output and those not started for Retry (DO-5); call again to retry."""
        if not self.split_done:
            raise RunBlocked("Finish Validate first.")
        out_dir = self.staging.path / OUTPUTS_DIR
        out_dir.mkdir(exist_ok=True)
        data = self.staging.path / convert.DATA
        todo = [o for o in self.outputs if o.status != DONE]
        for o in todo:
            o.status = PENDING
        current: OutputState | None = None
        try:
            for o in todo:
                current = o
                o.status = RUNNING
                ctx.set_stage(f"Generating output: {o.name}")
                target = self.staging.path / o.file
                res = layer.write_output(ctx.cursor(), Definition.from_dict(o.definition), self.columns, data, target)
                ctx.check_cancelled()
                o.result, o.note, o.status = res, res.note, DONE
                current = None
        except BaseException as e:
            from sankalan.jobs import Cancelled
            cancelled = isinstance(e, Cancelled) or ctx.cancel_requested
            for o in todo:
                if o.status != DONE:
                    o.status = CANCELLED if cancelled else FAILED
                    o.result = None
            if current is not None:
                (self.staging.path / current.file).unlink(missing_ok=True)
            raise
        return self.outputs

    # ------------------------------------------------------------------------------------------ Commit (step 5)
    def check_totals(self, ctx: JobContext, fault: dict[str, Decimal] | None = None) -> list[totals_q.TotalsLine]:
        """The totals check, calculated when the Commit step opens (RUN-6, T20). ``fault`` (RUNC-10) defaults to
        the environment hook, which works only when running from source."""
        if not self.split_done:
            raise RunBlocked("Finish Validate first.")
        ctx.set_stage("Checking totals")
        raws = [convert.RawPart(p.file_index, p.sheet, stage.raw_path(self.staging, p.file_index), p.width,
                                p.mapping) for p in self._parts]
        self.totals = totals_q.check(ctx.cursor(), raws, self.columns, self.staging.path / convert.DATA,
                                     self.staging.path / LEFT_OUT, fault_from_env() if fault is None else fault)
        return self.totals

    @property
    def totals_passed(self) -> bool:
        return self.totals is not None and all(t.passed for t in self.totals)

    @property
    def comment_prefill(self) -> str:
        """The override reason prefills the comment (RUN-13, RUNC-06)."""
        return self.override_reason or ""

    def commit_blockers(self, comment: str = "", free_bytes: int | None = None) -> list[str]:
        """Why Commit is disabled, or [] when it can run (Tech spec, Commit button enabled when)."""
        out = []
        if not self.split_done:
            return ["Finish Validate first."]
        if self.totals is None:
            out.append("The totals check hasn't run yet.")
        elif not self.totals_passed:
            names = ", ".join(t.name for t in self.totals if not t.passed)
            out.append(f"The totals check doesn't match for {names}. This run can't be committed.")
        if not self.outputs_done:
            out.append("Every default output must be generated first.")
        if self.override_reason is not None and not comment.strip():
            out.append("Enter a comment: this run continues despite errors.")
        if len(comment) > COMMENT_MAX:
            out.append(f"The comment can be at most {COMMENT_MAX} characters.")
        free = self.folder.free_bytes() if free_bytes is None else free_bytes
        if free < COMMIT_FREE_BYTES:
            out.append("There isn't enough free disk space to commit this run.")
        return out

    def commit(self, ctx: JobContext, comment: str = "", free_bytes: int | None = None) -> Committed:
        """Commit (RUN-5, T8, T22): flush, rename, one catalogue transaction that issues the Run ID and saves aliases
        and columns added in this run. Can't be cancelled."""
        ctx.set_cancellable(False)
        blockers = self.commit_blockers(comment, free_bytes)
        if blockers:
            raise RunBlocked(blockers[0])
        ctx.set_stage("Committing")
        con = ctx.cursor()
        run = self._new_run(con, comment)
        (self.staging.path / convert.FAILURES).unlink(missing_ok=True)   # issues.parquet keeps the text (Phase 3)
        result = self._mapping_result

        def save_template_changes(c) -> None:
            t = q.load_template(c, self.template.id)
            if result is not None and mapping_mod.apply_to_template(t, result):
                run.template_version = q.save_template_in(c, t)
            else:
                run.template_version = q.template_version(c, self.template.id)

        number = datafolder.commit(con, self.folder, self.staging, run, in_transaction=save_template_changes)
        self.committed = Committed(self.staging.id, number, run.template_version)
        self.staging = None
        return self.committed

    def _new_run(self, con, comment: str) -> NewRun:
        v = self.validation
        sc = v.scan
        st = self.staging.path
        loaded = convert.parquet_rows(con, st / convert.DATA)
        left = convert.parquet_rows(con, st / LEFT_OUT) if (st / LEFT_OUT).is_file() else 0
        unique_ids = [r.id for r in sc.rules if r.type == UNIQUE]
        errors_n, dups_n = left_out_breakdown(con, st, unique_ids)
        files = []
        parts = {p.file_index: p for p in self._load.parts}
        for i, f in enumerate(self.readable_files):
            p = parts[i]
            files.append(RunFile(i, f.file_name, f.path, f.size, f.sheet, f.sha256, p.rows + p.blank_rows,
                                 datetime.fromtimestamp(f.modified) if f.modified else None, f.header_row,
                                 p.hidden_rows, list(f.hidden_sheets), self.duplicate_decisions.get(f.path, "")))
        run_only = rule_changes(self.template.rules, self.rules)
        changes = {"mapping": self._mapping_result.decisions if self._mapping_result else [],
                   "rules_run_only": run_only, "rules_saved": self.saved_rule_changes,
                   "override_reason": self.override_reason}
        return NewRun(
            template_id=self.template.id, template_version=self.template.version, rows_read=v.rows_read,
            rows_loaded=loaded, rows_left_out=left + v.blank_rows,
            left_out_by_reason={"blank": v.blank_rows, "errors": errors_n, "duplicates": dups_n},
            errors=sc.errors, warnings=sc.warnings,
            status=STATUS_OVERRIDE if self.override_reason is not None else STATUS_COMMITTED,
            comment=comment, run_changes=changes, totals={t.column_id: t.to_dict() for t in self.totals or []},
            files=files, issue_counts=[IssueCount(c.rule, c.file_index, c.sheet, c.errors, c.warnings)
                                       for c in sc.counts],
            outputs=[RunOutput(o.position, o.name, o.definition, o.file) for o in self.outputs])

    # ------------------------------------------------------------------------------------------ leaving
    def drop_staging(self) -> None:
        """Cancel on Validate (RUNV-12): the staging folder goes, files and mapping decisions stay."""
        if self.staging is not None:
            self.folder.discard_staging(self.staging)
        self.staging = None
        self._invalidate(VALIDATE)

    def discard(self) -> None:
        """Leave and discard this run (RUN-14): the staging folder goes; nothing else was written."""
        if self.staging is not None:
            self.folder.discard_staging(self.staging)
        self.staging = None
        self._invalidate(FILES)

    def _invalidate(self, step: str) -> None:
        """Going back to an earlier step drops everything after it."""
        order = (FILES, MAPPING, VALIDATE, OUTPUTS, COMMIT)
        i = order.index(step)
        if i <= order.index(MAPPING):
            self._mapping_result = None
            self._parts = []
            if i < order.index(MAPPING):
                self.mapping = None
        if i <= order.index(VALIDATE):
            self.validation = None
            self.split_done = False
            self.override_reason = None
            self._load = None
        if i <= order.index(OUTPUTS):
            self.outputs = [OutputState(o.position, o.name, o.definition) for o in self.outputs] \
                if i == order.index(OUTPUTS) else []
        self.totals = None

