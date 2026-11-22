r"""Job work for the New run wizard (4.1–4.5) and the Run screen (5.1): the issue grid's pages, stored default outputs
read back, a committed run's figures, and export requests resolved to queries (UX-8, UX-9, ISS-1 to ISS-4, DO-7,
RUN-12, T19). No SQL here: everything goes through ``sankalan.query``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from sankalan import manage
from sankalan.db.datafolder import DataFolder
from sankalan.jobs import JobContext
from sankalan.model import export as ex
from sankalan.model.definition import Definition
from sankalan.model.rule import ERROR, RULE_NAMES, Rule, with_type_rules
from sankalan.model.template import Column, Template
from sankalan.query import catalogue as q
from sankalan.query import convert, layer
from sankalan.query import export as qx
from sankalan.query import validate as qv
from sankalan.query.split import LEFT_OUT
from sankalan.validation import issues as iss


class RunProblem(ValueError):
    """Something the screen says in plain words (e.g. "R-0001 has no left-out rows")."""


# ---------------------------------------------------------------------------------------------- start of the wizard
@dataclass
class WizardStart:
    template: Template
    client_id: str
    client_name: str
    free_bytes: int
    next_number: int = 1            # the Run ID this run gets if committed next (issued at commit, T22)

    @property
    def low_disk(self) -> bool:
        """RUNF-14: below the low-disk threshold (10 GB, confirmed 17-11-2026) on the data folder's drive."""
        return self.free_bytes < manage.LOW_DISK_BYTES


def wizard_start(ctx: JobContext, folder: DataFolder, template_id: str) -> WizardStart:
    con = ctx.cursor()
    head = q.template_header(con, template_id)
    if head is None:
        raise KeyError(template_id)
    return WizardStart(q.load_template(con, template_id), head[0], head[1], folder.free_bytes(),
                       q.last_run_number(con, template_id) + 1)


# ---------------------------------------------------------------------------------------------- by-rule table
@dataclass(frozen=True)
class RuleLine:
    """One row of the by-rule table (ISS-1): "Not blank · Invoice Date · Error · 2"."""
    rule_id: str
    rule: str
    column: str
    column_id: str
    severity: str
    count: int


def rule_lines(rules: list[Rule], counts: dict[str, int], columns: list[Column]) -> tuple[list[RuleLine], int]:
    """The rules that failed somewhere, Errors first, then in column and rule order; and how many passed on every
    row ("13 other rules passed on every row")."""
    order = {c.id: i for i, c in enumerate(columns)}
    names = {c.id: c.name for c in columns}
    failed, passed = [], 0
    for i, r in enumerate(rules):
        n = int(counts.get(r.id, 0))
        if not n:
            passed += 1
            continue
        failed.append((r.severity != ERROR, order.get(r.column_id, 10 ** 6), i,
                       RuleLine(r.id, RULE_NAMES[r.type], names.get(r.column_id, r.column_id), r.column_id,
                                r.severity, n)))
    return [x[-1] for x in sorted(failed, key=lambda x: x[:3])], passed


def stored_rule_lines(con, issues: Path, columns: list[Column]) -> list[RuleLine]:
    """The by-rule table of a committed run, from its stored issue list (ISS-4)."""
    order = {c.id: i for i, c in enumerate(columns)}
    names = {c.id: c.name for c in columns}
    lines = [RuleLine(rid, RULE_NAMES[rt], names.get(cid, cid), cid, sev, int(n))
             for rid, rt, cid, sev, n in qv.rule_lines(con, issues)] if issues.is_file() else []
    return sorted(lines, key=lambda x: (x.severity != ERROR, order.get(x.column_id, 10 ** 6), x.rule_id))


# ---------------------------------------------------------------------------------------------- issue grid (ISS-2)
ISSUE_KEYS = ("file", "sheet", "row", "column", "value", "rule", "severity")


@dataclass
class IssueSource:
    """A ``PageSource`` over an issue list: the first 10,000 issues per rule (ISS-2), filtered by rule, severity
    or column. Rows: (file, sheet, row, column, value, rule, severity, message)."""
    issues: Path
    file_names: dict[int, str]
    column_names: dict[str, str]
    rule_id: str | None = None
    severity: str | None = None
    column_id: str | None = None

    def _filters(self) -> dict:
        return {"rule_id": self.rule_id, "severity": self.severity, "column_id": self.column_id}

    def count(self, ctx, sort) -> int:
        if not Path(self.issues).is_file():
            return 0
        return qv.grid_count(ctx.cursor(), self.issues, **self._filters())

    def page(self, ctx, offset: int, limit: int, sort) -> list[tuple]:
        if not Path(self.issues).is_file():
            return []
        key, asc = (sort[0] if sort else (None, True))
        rows = qv.grid_page(ctx.cursor(), self.issues, offset=offset, limit=limit, sort=key, descending=not asc,
                            **self._filters())
        out = []
        for r in rows:
            i = iss.from_row(r, self.file_names, self.column_names)
            out.append((i.file, i.sheet, i.row, i.column, i.value if i.value not in (None, "") else "(blank)",
                        i.rule, i.severity, i.message))
        return out


# ---------------------------------------------------------------------------------------------- outputs (DO-6, DO-7)
def stored_output(ctx: JobContext, definition: dict, columns: list[Column], path: Path, *,
                  subtotals: bool | None = None, limit: int = manage.PREVIEW_ROWS,
                  headers: list[str] | None = None) -> manage.Preview:
    """A generated output read back as stored, never recalculated (DO-6, C6-10): headers (those stored at commit,
    T50, when given), first rows, total."""
    start = time.monotonic()
    defn = Definition.from_dict(definition)
    cur = ctx.cursor()
    res = layer.open_output(defn, columns, Path(path), cur, headers)
    sub = defn.subtotals if subtotals is None else subtotals
    rows = layer.rows(cur, res, subtotals=sub, limit=limit)
    total = layer.grand_total(cur, res)
    n = layer.count_rows(cur, res, sub)
    return manage.Preview([c.label for c in res.columns], [(c.type, c.decimals, c.grain) for c in res.columns],
                          rows, total, n, 0, time.monotonic() - start, res.note, res.levels)


# ---------------------------------------------------------------------------------------------- the Run screen (5.1)
@dataclass
class RunView:
    run: dict                       # ``query.catalogue.run_details``
    template: Template              # as it is now (today's column names)
    client_id: str
    client_name: str
    run_dir: Path
    rules: list[Rule]               # the rules that ran for this run
    lines: list[RuleLine] = field(default_factory=list)
    rows_loaded: dict[int, int] = field(default_factory=dict)      # file index -> rows loaded (Source files)

    @property
    def label(self) -> str:
        return self.run["label"]

    @property
    def checks(self) -> bool:
        """False for a run loaded without checks (NCK-12): no issues, nothing left out."""
        return bool(self.run.get("checks", True))

    @property
    def blank_rows(self) -> int:
        """Blank rows skipped (T45): in ``left_out_by_reason`` for a checked run, Rows read − Rows loaded for a run
        without checks."""
        if self.checks:
            return int(self.run["left_out_by_reason"].get("blank", 0))
        return int(self.run["rows_read"]) - int(self.run["rows_loaded"])

    @property
    def issues(self) -> Path:
        return self.run_dir / qv.ISSUES

    @property
    def file_names(self) -> dict[int, str]:
        return {f["file_index"]: f["file_name"] for f in self.run["files"]}

    @property
    def column_names(self) -> dict[str, str]:
        return {c.id: c.name for c in self.template.columns}


def rules_that_ran(snapshot: dict, run_changes: dict, columns: list[Column]) -> list[Rule]:
    """The template's rules at the run's version with this run's run-only edits applied (VR-5, RUN-12)."""
    rules = {r["id"]: Rule.from_dict(r) for r in snapshot.get("rules", [])}
    for ch in run_changes.get("rules_run_only", []):
        if ch["after"] is None:
            rules.pop(ch["rule_id"], None)
        else:
            rules[ch["rule_id"]] = Rule.from_dict(ch["after"])
    return with_type_rules(columns, list(rules.values()))


def run_view(ctx: JobContext, folder: DataFolder, run_id: str) -> RunView:
    con = ctx.cursor()
    run = q.run_details(con, run_id)
    if run is None:
        raise KeyError(run_id)
    tid = run["template_id"]
    head = q.template_header(con, tid)
    t = q.load_template(con, tid)
    rules = rules_that_ran(q.template_snapshot(con, tid, run["template_version"]), run["run_changes"], t.columns)
    run_dir = folder.run_dir(tid, run_id)
    view = RunView(run, t, head[0], head[1], run_dir, rules)
    view.lines = stored_rule_lines(con, view.issues, t.columns)
    data = run_dir / convert.DATA
    view.rows_loaded = convert.rows_by_file(con, data) if data.is_file() else {}
    return view


# ---------------------------------------------------------------------------------------------- exports (T19, DO-7)
def _output_name(request: ex.ExportRequest, name: str) -> str:
    v = request.values or {}
    return ex.csv_file_name(request.pattern, Client=v.get("Client", ""), Template=v.get("Template", ""),
                            RunID=v.get("RunID", ""), Output=name)


def export_items(ctx: JobContext, folder: DataFolder, request: ex.ExportRequest) -> list[tuple[qx.ExportSource, str]]:
    """The sources and file names an Export request writes (run data, left-out rows, issue list, one output, all
    outputs: one source each, Tech spec A2 8.1). Requests from screens whose data isn't committed yet (the Validate
    step's issue list) or that aren't a run (an analysis result) carry their own ``items``."""
    if request.items is not None:
        return request.items(ctx)
    if request.run_id is None:
        raise RunProblem("Nothing to export.")
    view = run_view(ctx, folder, request.run_id)
    con = ctx.cursor()
    label = view.label
    if request.kind in ex.CHECKED_ONLY and not view.checks:       # NCK-12, Tech spec A2 6.8 (defence behind the UI)
        raise RunProblem(f"{label} was loaded without checks: it has no issue list or left-out rows.")
    if request.kind == "data":
        return [(qx.run_data(con, view.run_dir / convert.DATA, view.template.columns, view.file_names, label),
                 request.file_name)]
    if request.kind == "left_out":
        path = view.run_dir / LEFT_OUT
        if not path.is_file() or convert.parquet_rows(con, path) == 0:
            raise RunProblem(f"{label} has no left-out rows with errors to export.")
        return [(qx.left_out(con, path, view.template.columns, view.file_names, label, view.rules),
                 request.file_name)]
    if request.kind == "issues":
        return [(qx.issue_list(con, view.issues, view.file_names, view.column_names), request.file_name)]
    if request.kind in ("output", "outputs"):
        outs = view.run["outputs"]
        if request.kind == "output":
            outs = [o for o in outs if o.position == request.output]
        if not outs:
            raise RunProblem(f"{label} has no saved outputs.")
        items = []
        for o in outs:
            res = layer.open_output(Definition.from_dict(o.definition), view.template.columns, view.run_dir / o.file,
                                    con, o.headers)
            sub = Definition.from_dict(o.definition).subtotals if request.subtotals is None else request.subtotals
            name = request.file_name if request.kind == "output" else _output_name(request, o.name)
            items.append((qx.result(con, res, subtotals=sub, label=o.name), name))
        return items
    raise RunProblem(f"Unknown export {request.kind!r}.")


# ---------------------------------------------------------------------------------------------- summary lines (RUN-12)
def rule_change_lines(changes: list[dict], columns: list[Column], saved: bool) -> list[str]:
    """"Changed for this run only: Allowed values (GST Rate): 0, 5, 12, 15, 18, 28 · Error" (RUNV-09, RUNV-10)."""
    from sankalan.validation.rules import describe
    where = "saved to the template" if saved else "for this run only"
    out = []
    for ch in changes:
        rule = Rule.from_dict(ch["after"] or ch["before"])
        verb = {"added": "Added", "removed": "Removed", "changed": "Changed"}[ch["change"]]
        out.append(f"{verb} {where}: {describe(rule, columns)}")
    return out


def mapping_lines(decisions: list[dict]) -> list[str]:
    from sankalan.mapping import describe
    return [describe(d) for d in decisions]
