r"""The validation scan as Job work (Tech spec, Validation and issues; VR-3 to VR-8, ISS-1, ISS-4).

- ``validate``: after the load (``sankalan.ingest.stage.load``), one scan of the staged ``data.parquet`` (values
  with their text companions) writes ``_staging\<id>\issues.parquet`` and returns the counts. Editing rules
  for this run (VR-5) calls it again with the run's rules: only the scan reruns, never the read.
- ``dry_run``: the New template wizard's counts and first 20 failing rows per rule on the staged sample (VR-8).
  Nothing is written.
- ``test_rules_on_run``: "Test rules on latest run" on a committed run's ``data.parquet``, counts only (VR-8).
  Nothing is written. Committed rows keep their text companions, so type rules find text values there too.

``issues.parquet`` is written as ``issues.parquet.part`` and renamed, so a cancelled or failed scan never leaves a
half-written issue list.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from sankalan.db.datafolder import Staging
from sankalan.jobs import JobContext
from sankalan.model.rule import Rule, with_type_rules
from sankalan.model.run import IssueCount
from sankalan.model.template import Column
from sankalan.query import convert
from sankalan.query import validate as q
from sankalan.validation.rules import check_rule

STAGE = "Checking rules"


def prepare(columns: list[Column], rules: list[Rule]) -> list[Rule]:
    """The rules that run: the given ones plus the automatic type rules (VR-7), each checked (``RuleError``)."""
    out = with_type_rules(columns, rules)
    for r in out:
        check_rule(r, columns)
    return out


@dataclass
class ScanResult:
    issues: Path
    errors: int
    warnings: int
    by_rule: dict[str, int]                 # rule ID -> failures (rules with none: 0)
    counts: list[IssueCount] = field(default_factory=list)   # per rule, file and sheet (run_issue_count)
    left_out: int = 0                       # rows Continue despite errors would leave out (T18, 7.1)
    rules: list[Rule] = field(default_factory=list)          # the rules that ran

    @property
    def passed(self) -> bool:
        """No Error-level failures: Next is enabled (VR-3, VR-4)."""
        return self.errors == 0


def _remove(path: Path) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def validate(ctx: JobContext, staging: Staging, columns: list[Column], rules: list[Rule],
             file_names: dict[int, str] | None = None) -> ScanResult:
    run_rules = prepare(columns, rules)
    data = staging.path / convert.DATA
    out = staging.path / q.ISSUES
    part = out.with_name(out.name + ".part")
    ctx.on_abort(lambda: _remove(part))
    ctx.set_stage(STAGE)
    _remove(out)                            # a rerun replaces the list; until then there is none
    _remove(part)
    cur = ctx.cursor()
    q.write_issues(cur, data, columns, run_rules, part, file_names)
    ctx.check_cancelled()
    os.replace(part, out)
    errors, warnings = q.totals(cur, out)
    by_rule = {r.id: 0 for r in run_rules}
    by_rule.update(q.rule_counts(cur, out))
    return ScanResult(out, errors, warnings, by_rule, q.issue_counts(cur, out), q.left_out_rows(cur, out),
                      run_rules)


def dry_run(ctx: JobContext, data: Path, columns: list[Column], rules: list[Rule],
            file_names: dict[int, str] | None = None, keep: int = q.SHOW_FIRST):
    """(counts per rule ID, first ``keep`` issue rows per rule ID). Nothing is written."""
    run_rules = prepare(columns, rules)
    ctx.set_stage(STAGE)
    return q.dry_run(ctx.cursor(), data, columns, run_rules, keep, file_names)


def test_rules_on_run(ctx: JobContext, run_dir: Path, columns: list[Column], rules: list[Rule]) -> dict[str, int]:
    """Failure counts per rule ID on a committed run's rows (C4-12). Nothing is written."""
    run_rules = prepare(columns, rules)
    ctx.set_stage(STAGE)
    counts, _ = q.dry_run(ctx.cursor(), Path(run_dir) / convert.DATA, columns, run_rules, keep=0)
    return counts


test_rules_on_run.__test__ = False          # not a pytest test, despite the name
