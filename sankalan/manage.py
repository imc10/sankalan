"""Clients, templates and runs as Job work for the C1, C2 and C4 screens (UX-1, UX-2, UX-4 to UX-7, TPL-2, TPL-4).

DuckDB is used only inside Jobs: the screens start these through the window's Job bridge and get plain Python
objects back. Names are checked here: required, and unique ignoring case and leading or trailing spaces (clients
across the app, C1-04 confirmed 17-11-2026; templates within their client, C2-05).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from sankalan.db import datafolder
from sankalan.db.datafolder import DataFolder
from sankalan.jobs import JobContext
from sankalan.model.run import run_label
from sankalan.model.template import Template
from sankalan.query import catalogue as q
from sankalan.query import convert

LOW_DISK_BYTES = 10 * 1024 ** 3      # C1-10, RUNF-14: amber below 10 GB free (decided 17-11-2026; revisit after PERF-08)
NAME_MAX = 100


class NameRefused(ValueError):
    """A client or template name that can't be used; ``str(e)`` is shown under the name field."""


def name_key(name: str) -> str:
    return name.strip().casefold()


def check_name(name: str, taken: dict[str, str], *, what: str, exclude: str | None = None) -> str:
    """The name to store (trimmed), or ``NameRefused``. ``taken``: id -> name of the names it must differ from."""
    clean = (name or "").strip()
    if not clean:
        raise NameRefused(f"Enter a {what} name.")
    if len(clean) > NAME_MAX:
        raise NameRefused(f"Use at most {NAME_MAX} characters.")
    for other_id, other in taken.items():
        if other_id != exclude and name_key(other) == name_key(clean):
            raise NameRefused(f"“{other}” is already in use. Choose another name.")
    return clean


# ---------------------------------------------------------------------------------------------- C1 Clients
@dataclass
class StorageFigures:
    """The storage footer (UX-1, Tech spec Figures on screen)."""
    rows: int
    size_bytes: int
    free_bytes: int
    drive: str

    @property
    def low(self) -> bool:
        return self.free_bytes < LOW_DISK_BYTES


@dataclass
class ClientRow:
    id: str
    name: str
    templates: int
    runs: int
    rows: int
    last_loaded: dt.datetime | None


@dataclass
class ClientsOverview:
    clients: list[ClientRow]
    templates: int
    runs: int
    storage: StorageFigures


def drive_of(path: Path) -> str:
    p = Path(path)
    return p.drive or p.anchor or str(p)


def storage_figures(con, folder: DataFolder) -> StorageFigures:
    _c, _t, _r, rows = q.overview(con)
    return StorageFigures(rows, folder.size_bytes(), folder.free_bytes(), drive_of(folder.path))


def clients_overview(ctx: JobContext, folder: DataFolder) -> ClientsOverview:
    con = ctx.cursor()
    rows = [ClientRow(*r) for r in q.client_rows(con)]
    _c, templates, runs, _rows = q.overview(con)
    return ClientsOverview(rows, templates, runs, storage_figures(con, folder))


def create_client(ctx: JobContext, name: str) -> str:
    con = ctx.cursor()
    clean = check_name(name, q.client_names(con), what="client")
    return q.insert_client(con, clean)


def rename_client(ctx: JobContext, client_id: str, name: str) -> str:
    """Only the catalogue changes: folders are named by ID (C1-07)."""
    con = ctx.cursor()
    clean = check_name(name, q.client_names(con), what="client", exclude=client_id)
    q.rename_client(con, client_id, clean)
    return clean


@dataclass
class DeleteSummary:
    """What a delete removes (UI-8, dialogs 7.2 and 7.3)."""
    title: str
    intro: str
    items: list[str]
    note: str | None = None
    button: str = "Delete"


def _runs_and_rows(runs: int, rows: int) -> str:
    from sankalan.formats import count
    return f"{count(runs, 'run')} and {count(rows, 'row')}"


def client_delete_summary(ctx: JobContext, client_id: str) -> DeleteSummary:
    from sankalan.formats import count
    con = ctx.cursor()
    row = next((r for r in q.client_rows(con) if r[0] == client_id), None)
    if row is None:
        raise KeyError(client_id)
    _id, name, templates, runs, rows, _last = row
    analyses = q.saved_analysis_count(con, client_id=client_id)
    return DeleteSummary(f"Delete {name}?", "Everything stored for this client is deleted:",
                         [count(templates, "template"), _runs_and_rows(runs, rows),
                          count(analyses, "saved analysis", "saved analyses")], button="Delete client")


def delete_client(ctx: JobContext, folder: DataFolder, client_id: str) -> None:
    ctx.set_stage("Deleting client")
    datafolder.delete_client(ctx.cursor(), folder, client_id)


# ---------------------------------------------------------------------------------------------- C2 Client
@dataclass
class TemplateRow:
    id: str
    name: str
    columns: int
    outputs: int
    runs: int
    rows: int
    last_loaded: dt.datetime | None
    modified: dt.datetime


@dataclass
class ClientDetail:
    id: str
    name: str
    templates: list[TemplateRow]

    @property
    def runs(self) -> int:
        return sum(t.runs for t in self.templates)

    @property
    def rows(self) -> int:
        return sum(t.rows for t in self.templates)


def client_detail(ctx: JobContext, client_id: str) -> ClientDetail:
    con = ctx.cursor()
    name = q.client_name(con, client_id)
    if name is None:
        raise KeyError(client_id)
    return ClientDetail(client_id, name, [TemplateRow(*r) for r in q.template_rows(con, client_id)])


def _template_client(con, template_id: str) -> str:
    head = q.template_header(con, template_id)
    if head is None:
        raise KeyError(template_id)
    return head[0]


def rename_template(ctx: JobContext, template_id: str, name: str) -> str:
    """A rename is a save: the template's version goes up (TPL-7)."""
    con = ctx.cursor()
    t = q.load_template(con, template_id)
    t.name = check_name(name, q.template_names(con, t.client_id), what="template", exclude=template_id)
    q.save_template(con, t)
    return t.name


def copy_name(name: str, taken: dict[str, str]) -> str:
    """"Sales Register (copy)", then "(copy 2)", … until unique within the client."""
    keys = {name_key(n) for n in taken.values()}
    base = f"{name} (copy)"
    candidate, n = base, 2
    while name_key(candidate) in keys:
        candidate, n = f"{name} (copy {n})", n + 1
    return candidate


def duplicate_template(ctx: JobContext, template_id: str) -> str:
    """TPL-4: every setting, no runs or saved analyses (C2-06)."""
    con = ctx.cursor()
    t = q.load_template(con, template_id)
    return q.duplicate_template(con, template_id, copy_name(t.name, q.template_names(con, t.client_id)))


def template_delete_summary(ctx: JobContext, template_id: str) -> DeleteSummary:
    from sankalan.formats import count
    con = ctx.cursor()
    head = q.template_header(con, template_id)
    if head is None:
        raise KeyError(template_id)
    _cid, _client, name, runs, rows, _last = head
    analyses = q.saved_analysis_count(con, template_id=template_id)
    return DeleteSummary(f"Delete {name}?", "Everything stored for this template is deleted:",
                         [_runs_and_rows(runs, rows), count(analyses, "saved analysis", "saved analyses")],
                         note="Its columns, rules and default outputs are deleted too.", button="Delete template")


def delete_template(ctx: JobContext, folder: DataFolder, template_id: str) -> None:
    ctx.set_stage("Deleting template")
    datafolder.delete_template(ctx.cursor(), folder, template_id)


# ---------------------------------------------------------------------------------------------- C4 Template
@dataclass
class RunItem:
    id: str
    number: int
    loaded_on: dt.datetime
    files: list[str]
    rows: int
    errors: int
    warnings: int
    status: str
    comment: str
    damaged: bool

    @property
    def label(self) -> str:
        return run_label(self.number)


@dataclass
class LatestRun:
    id: str
    number: int
    rows: int
    loaded_on: dt.datetime
    data: Path

    @property
    def label(self) -> str:
        return run_label(self.number)


@dataclass
class TemplateDetail:
    template: Template
    client_id: str
    client_name: str
    runs: list[RunItem]
    rows: int
    size_bytes: int
    last_loaded: dt.datetime | None
    latest: LatestRun | None
    has_runs: bool
    extra: dict = field(default_factory=dict)


def folder_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def template_detail(ctx: JobContext, folder: DataFolder, template_id: str) -> TemplateDetail:
    con = ctx.cursor()
    head = q.template_header(con, template_id)
    if head is None:
        raise KeyError(template_id)
    client_id, client_name, _name, _runs, rows, last = head
    t = q.load_template(con, template_id)
    runs = [RunItem(*r) for r in q.run_rows(con, template_id)]
    lr = q.latest_run(con, template_id)
    latest = None
    if lr is not None:
        latest = LatestRun(lr[0], lr[1], lr[2], lr[3], folder.run_dir(template_id, lr[0]) / convert.DATA)
    return TemplateDetail(t, client_id, client_name, runs, int(rows), folder_size(folder.template_dir(template_id)),
                          last, latest, bool(runs))


def save_template(ctx: JobContext, t: Template) -> Template:
    """Save a tab's edits as a new version (TPL-7). Raises ``NameRefused`` or ``TemplateError`` (TPL-9, MAP-11)."""
    con = ctx.cursor()
    t.name = check_name(t.name, q.template_names(con, t.client_id), what="template", exclude=t.id)
    q.save_template(con, t)
    return q.load_template(con, t.id)


def run_delete_summary(ctx: JobContext, run_id: str) -> DeleteSummary:
    from sankalan.formats import count
    row = q.run_delete_figures(ctx.cursor(), run_id)
    if row is None:
        raise KeyError(run_id)
    number, template, rows, outputs = row
    items = [count(rows, "row"), "The issue list"]
    if outputs:
        items.append(count(outputs, "saved output"))
    return DeleteSummary(f"Delete {run_label(number)}?", f"This removes the run from {template}:", items,
                         note="Saved analyses that used this run will no longer include its data.",
                         button="Delete run")


def delete_run(ctx: JobContext, folder: DataFolder, run_id: str) -> bool:
    ctx.set_stage("Deleting run")
    return datafolder.delete_run(ctx.cursor(), folder, run_id)


# ---------------------------------------------------------------------------------------------- previews and tests
PREVIEW_ROWS = 1_000


@dataclass
class Preview:
    """A default output's preview on the latest run (DO-8): headers, the first rows, the grand total."""
    headers: list[str]
    kinds: list[tuple[str, int | None, str | None]]     # (type, decimals, grain) per column
    rows: list[tuple]                                   # (_depth, values...)
    total: tuple | None
    count: int
    input_rows: int
    seconds: float
    note: str | None
    groups: int


def output_preview(ctx: JobContext, definition, columns, data: Path, *, subtotals: bool | None = None,
                   limit: int = PREVIEW_ROWS) -> Preview:
    """Run a default output on one run's rows and read its first rows; nothing is kept (DO-8)."""
    import time
    from sankalan import analysis
    from sankalan.query import layer
    start = time.monotonic()
    res = analysis.preview_output(ctx, definition, columns, data)
    cur = ctx.cursor()
    try:
        sub = definition.subtotals if subtotals is None else subtotals
        rows = layer.rows(cur, res, subtotals=sub, limit=limit)
        total = layer.grand_total(cur, res)
        n = layer.count_rows(cur, res, sub)
    finally:
        layer.drop(cur, res)
    return Preview([c.label for c in res.columns], [(c.type, c.decimals, c.grain) for c in res.columns], rows,
                   total, n, res.input_rows, time.monotonic() - start, res.note, res.levels)


def test_rules(ctx: JobContext, run_dir: Path, columns, rules) -> dict[str, int]:
    """VR-8: failure counts per rule on the latest run; nothing is stored (C4-12)."""
    from sankalan.validation import scan
    return scan.test_rules_on_run(ctx, run_dir, columns, rules)


test_rules.__test__ = False
