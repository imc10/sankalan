"""One consolidation run: add files -> map -> validate -> write. Used by the UI and the tests."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from . import convert as cv
from .mapping import auto_map, unmapped_sources
from .output import build_filename, read_back_totals, write_output, write_issue_list
from .readers import Cancelled, FileData, PasswordRequired, collect_files, read_file
from .template import Template, new_column
from .validation import ERROR, WARNING, Issue, run_validation

log = logging.getLogger("sankalan")


@dataclass
class ValidationResult:
    issues: list
    rows_checked: int

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == ERROR]

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == WARNING]

    def by_rule(self):
        """Summary: count per check and severity, with the files involved."""
        out = {}
        for i in self.issues:
            k = (i.rule, i.severity, i.message.split(" ", 1)[0] if i.rule != "duplicates" else i.column)
            e = out.setdefault((i.rule, i.severity), {"count": 0, "files": []})
            e["count"] += 1
            if i.file not in e["files"]:
                e["files"].append(i.file)
        return out

    def by_file(self):
        out = {}
        for i in self.issues:
            out.setdefault(i.file, {ERROR: 0, WARNING: 0})[i.severity] += 1
        return out


@dataclass
class TotalLine:
    column: str
    input_total: float
    output_total: float

    @property
    def match(self):
        return round(self.input_total, 2) == round(self.output_total, 2)


@dataclass
class RunSummary:
    path: Optional[Path]
    files_read: int
    rows_read: int
    rows_written: int
    rows_left_out: int
    warnings: int
    errors_overridden: int
    hidden: list = field(default_factory=list)        # "file: 12 hidden rows"
    skipped_rows: list = field(default_factory=list)  # blank/total rows info
    totals: list = field(default_factory=list)        # TotalLine
    seconds: float = 0.0

    @property
    def totals_match(self):
        return all(t.match for t in self.totals)


def source_key(fd: FileData) -> str:
    return f"{fd.path}|{fd.sheet}"


class Session:
    def __init__(self, template: Template):
        self.template = template
        self.paths: list[Path] = []
        self.skipped = []
        self.sources: list[FileData] = []
        self.file_options: dict = {}       # str(path) -> {sheet_mode, sheet_value, header_row, password}
        self.needs_password: list[Path] = []
        self.manual: dict = {}             # source_key -> {target: header|None}
        self.new_aliases: list = []        # (target, alias) learned this run
        self.validation: Optional[ValidationResult] = None
        self._merged = None

    # ------------------------------------------------------------------ files (IN-*)
    def add(self, paths, pattern=None, include_subfolders=None):
        inp = self.template.input
        found, skipped = collect_files(paths, pattern or inp.get("pattern") or "*",
                                       inp.get("include_subfolders") if include_subfolders is None
                                       else include_subfolders)
        from .readers import Skipped
        known = {str(p.resolve()).lower() for p in self.paths}
        for p in found:
            k = str(p.resolve()).lower()
            if k in known:
                skipped.append(Skipped(p, "same file added twice"))
                continue
            known.add(k)
            self.paths.append(p)
        self.skipped.extend(skipped)
        self.paths.sort(key=lambda p: p.name.lower())
        return found, skipped

    def remove(self, path):
        path = Path(path)
        self.paths = [p for p in self.paths if p != path]
        self.sources = [s for s in self.sources if s.path != path]

    def _read_one(self, p: Path, cancel=None):
        inp = self.template.input
        o = self.file_options.get(str(p), {})
        return read_file(p, sheet_mode=o.get("sheet_mode", inp["sheet_mode"]),
                         sheet_value=o.get("sheet_value", inp["sheet_value"]),
                         header_row=o.get("header_row", inp["header_row"]),
                         known_names=self.template.known_names() or None,
                         trailer_words=inp.get("trailer_words") or [],
                         password=o.get("password"),
                         csv_delimiter=inp.get("csv_delimiter"), cancel=cancel)

    def load(self, progress: Optional[Callable] = None, cancel: Optional[Callable] = None):
        self.sources, self.needs_password = [], []
        for i, p in enumerate(self.paths):
            if cancel and cancel():
                raise Cancelled()
            if progress:
                progress("Reading files", i, len(self.paths))
            try:
                self.sources.extend(self._read_one(p, cancel))
            except PasswordRequired:
                self.needs_password.append(p)
                self.sources.append(FileData(p, status="password", error="password needed"))
        log.info("read %d files, %d sources, %d need password", len(self.paths), len(self.sources),
                 len(self.needs_password))
        self.validation = None
        return self.sources

    def reload(self, path):
        path = Path(path)
        idx = [i for i, s in enumerate(self.sources) if s.path == path]
        try:
            new = self._read_one(path)
            if path in self.needs_password:
                self.needs_password.remove(path)
        except PasswordRequired:
            new = [FileData(path, status="password", error="password needed or wrong password")]
            if path not in self.needs_password:
                self.needs_password.append(path)
        at = idx[0] if idx else len(self.sources)
        self.sources = [s for s in self.sources if s.path != path]
        self.sources[at:at] = new
        self.validation = None
        return new

    def set_password(self, path, password):
        """IN-9: kept in memory for this run only; never written anywhere."""
        self.file_options.setdefault(str(path), {})["password"] = password
        return self.reload(path)

    def set_file_options(self, path, sheet_mode=None, sheet_value=None, header_row="keep"):
        o = self.file_options.setdefault(str(path), {})
        if sheet_mode is not None:
            o["sheet_mode"] = sheet_mode
        if sheet_value is not None:
            o["sheet_value"] = sheet_value
        if header_row != "keep":
            o["header_row"] = header_row
        return self.reload(path)

    def good_sources(self):
        return [s for s in self.sources if s.status in ("OK", "warning") and s.headers]

    # ------------------------------------------------------------------ mapping (MAP-*)
    def mapping_for(self, fd: FileData):
        m = auto_map(self.output_columns(), fd.headers)
        for tgt, src in self.manual.get(source_key(fd), {}).items():
            # a manual choice wins; release that header from any other target
            if src:
                for k, (s, meth) in list(m.items()):
                    if s == src and k != tgt:
                        m[k] = (None, None)
            m[tgt] = (src, "manual" if src else None)
        return m

    def set_mapping(self, fd: FileData, target: str, header: Optional[str], save_alias=False):
        self.manual.setdefault(source_key(fd), {})[target] = header
        if save_alias and header and self.template.add_alias(target, header):
            self.new_aliases.append((target, header))
        self.validation = None

    def output_columns(self):
        return [c for c in self.template.columns if c.get("include", True)]

    def mapping_problems(self):
        """MAP-6: required target columns with no source column, per source."""
        probs = []
        for fd in self.good_sources():
            m = self.mapping_for(fd)
            for c in self.output_columns():
                if m[c["name"]][0] is None and c.get("required"):
                    probs.append((fd, c["name"]))
        return probs

    def unmatched(self):
        """Cells in the mapping grid with no match (required or not)."""
        out = []
        for fd in self.good_sources():
            m = self.mapping_for(fd)
            for c in self.output_columns():
                if m[c["name"]][0] is None:
                    out.append((fd, c["name"]))
        return out

    def extra_headers(self):
        seen = []
        for fd in self.good_sources():
            for h in unmapped_sources(self.mapping_for(fd), fd.headers):
                if h not in seen:
                    seen.append(h)
        return seen

    # ------------------------------------------------------------------ merge + validate (VAL-*)
    def _merge(self, cancel=None):
        t = self.template
        cols = self.output_columns()
        keep_extra = t.extra_columns == "keep"
        extras = self.extra_headers() if keep_extra else []
        rows, raws, oks, origins = [], [], [], []
        for fd in self.good_sources():
            m = self.mapping_for(fd)
            idx = {h: i for i, h in enumerate(fd.headers)}
            col_idx = [idx.get(m[c["name"]][0]) if m[c["name"]][0] else None for c in cols]
            ext_idx = [idx.get(h) for h in extras]
            for n, r in zip(fd.row_numbers, fd.rows):
                if cancel and len(rows) % 20000 == 0 and cancel():
                    raise Cancelled()
                raw = [r[i] if i is not None else None for i in col_idx]
                conv, ok = [], []
                for c, v in zip(cols, raw):
                    cvv, cok = cv.convert(v, c.get("type", "text"), c.get("date_order", "DMY"))
                    conv.append(cvv)
                    ok.append(cok)
                ext = [cv.to_text(r[i])[0] if i is not None else None for i in ext_idx]
                rows.append(conv + ext)
                raws.append(raw)
                oks.append(ok)
                origins.append((fd.name, fd.sheet, n))
        self._merged = (cols, extras, rows, raws, oks, origins)
        return self._merged

    def validate(self, progress=None, cancel=None) -> ValidationResult:
        if progress:
            progress("Checking rows", 0, 1)
        probs = self.mapping_problems()
        cols, extras, rows, raws, oks, origins = self._merge(cancel)
        issues = []
        for fd, target in probs:
            issues.append(Issue(fd.name, fd.sheet, fd.header_row, target, "(no column)", "mapping", ERROR,
                                f"{target} is required but has no matching column in this file"))
        for fd in self.sources:
            if fd.status == "error":
                issues.append(Issue(fd.name, fd.sheet or "-", 0, "-", "-", "read", ERROR,
                                    f"File could not be used: {fd.error}"))
            elif fd.status == "password":
                issues.append(Issue(fd.name, "-", 0, "-", "-", "read", ERROR,
                                    "File is password-protected; enter its password"))
        issues += run_validation(cols, [r[:len(cols)] for r in rows], raws, oks, origins,
                                 self.template.duplicate_keys, self.template.gstin_exceptions, cancel)
        self.validation = ValidationResult(issues, len(rows))
        log.info("validated %d rows: %d errors, %d warnings", len(rows), len(self.validation.errors),
                 len(self.validation.warnings))
        return self.validation

    def export_issues(self, path):
        return write_issue_list(path, self.validation.issues if self.validation else [])

    # ------------------------------------------------------------------ output (OUT-*)
    def output_path(self, folder=None):
        o = self.template.output
        cols, extras, rows, *_ = self._merged or self._merge()
        period = None
        for ci, c in enumerate(cols):
            if c.get("type") == "date":
                ds = [r[ci] for r in rows if isinstance(r[ci], date)]
                if ds:
                    period = max(ds)
                break
        name = build_filename(o.get("name_pattern"), self.template.client, self.template.task,
                              o.get("format", "xlsx"), period)
        return Path(folder or o.get("folder") or Path.cwd()) / name

    def write(self, override_errors=False, overwrite=False, folder=None, progress=None,
              cancel=None) -> RunSummary:
        """D4: errors stop the run unless the executive overrides."""
        t0 = time.time()
        if self.validation is None:
            self.validate(progress, cancel)
        v = self.validation
        if v.errors and not override_errors:
            raise PermissionError(f"{len(v.errors)} errors: output not written")
        o = self.template.output
        cols, extras, rows, raws, oks, origins = self._merged
        meta_h, meta_t = [], []
        if o.get("source_file"):
            meta_h.append("Source File"); meta_t.append("meta")
        if o.get("source_sheet"):
            meta_h.append("Source Sheet"); meta_t.append("meta")
        if o.get("source_row"):
            meta_h.append("Source Row"); meta_t.append("meta")
        headers = meta_h + [c["name"] for c in cols] + extras
        types = meta_t + [c.get("type", "text") for c in cols] + ["text"] * len(extras)

        def out_rows():
            res = []
            for (f, s, n), r in zip(origins, rows):
                meta = []
                if o.get("source_file"):
                    meta.append(f)
                if o.get("source_sheet"):
                    meta.append(s)
                if o.get("source_row"):
                    meta.append(n)
                res.append(meta + r)
            return res

        path = self.output_path(folder)
        fmt = o.get("format", "xlsx")
        prog = (lambda d, tot: progress("Writing output", d, tot)) if progress else None
        write_output(path, headers, types, out_rows(), fmt=fmt, indian=o.get("indian_format", True),
                     issues=v.warnings if (fmt == "xlsx" and o.get("issues_sheet")) else None,
                     csv_encoding=o.get("csv_encoding", "utf-8-sig"),
                     csv_delimiter=o.get("csv_delimiter", ","), overwrite=overwrite,
                     progress=prog, cancel=cancel)
        # OUT-11 grand totals: sum of inputs vs sum read back from the written file
        tot_cols = [c["name"] for c in cols if c.get("total") and c.get("type") == "number"]
        totals = []
        if tot_cols:
            back = read_back_totals(path, fmt, tot_cols, o.get("csv_encoding", "utf-8-sig"),
                                    o.get("csv_delimiter", ","))
            for name in tot_cols:
                ci = [c["name"] for c in cols].index(name)
                inp = sum(r[ci] for r in rows if isinstance(r[ci], (int, float)) and not isinstance(r[ci], bool))
                totals.append(TotalLine(name, inp, back[name]))
        hidden = []
        skipped_rows = []
        for fd in self.sources:
            if fd.hidden_rows:
                hidden.append(f"{fd.name}: {fd.hidden_rows} hidden row{'s' if fd.hidden_rows != 1 else ''}")
            for hs in fd.hidden_sheets:
                entry = f'{fd.name}: hidden sheet "{hs}"'
                if entry not in hidden:
                    hidden.append(entry)
            if fd.trailer_rows:
                skipped_rows.append(f"{fd.name}: {fd.trailer_rows} total row(s)")
        files_read = len({s.path for s in self.good_sources()})
        summary = RunSummary(path, files_read, len(rows), len(rows), 0, len(v.warnings),
                             len(v.errors) if override_errors else 0, hidden, skipped_rows, totals,
                             time.time() - t0)
        log.info("wrote %s: %d rows, totals match=%s", path.name, len(rows), summary.totals_match)
        return summary

    def save_template(self, store):
        return store.save(self.template)


def template_from_sample(path, client, task, sheet_mode="first", sheet_value="", header_row=None):
    """TPL-3: build a new template from a sample file, guessing column types and default checks."""
    fds = read_file(path, sheet_mode=sheet_mode, sheet_value=sheet_value, header_row=header_row)
    fd = fds[0]
    if fd.status == "error":
        raise ValueError(f"{fd.name}: {fd.error}")
    cols = []
    for i, h in enumerate(fd.headers):
        values = [r[i] for r in fd.rows]
        typ = cv.guess_type(values)
        rules = []
        n = h.lower().replace(" ", "")
        if "gstin" in n or n in ("gstno", "gstnumber"):
            rules = [{"type": "gstin_format", "severity": ERROR}, {"type": "gstin_state", "severity": ERROR},
                     {"type": "gstin_checksum", "severity": ERROR}]
        elif typ == "number":
            rules = [{"type": "is_number", "severity": ERROR}]
        elif typ == "date":
            rules = [{"type": "is_date", "severity": ERROR}]
        cols.append(new_column(h, typ, required=False, rules=rules, total=(typ == "number")))
    t = Template(client, task, cols)
    if sheet_mode != "first":
        t.input["sheet_mode"], t.input["sheet_value"] = sheet_mode, sheet_value
    return t


def setup_logging(folder=None):
    """SEC-4: technical log only (file names, counts, error types) - never cell values."""
    folder = Path(folder or os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "Sankalan" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    h = logging.FileHandler(folder / "sankalan.log", encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.handlers[:] = [h]
    log.setLevel(logging.INFO)
    return folder / "sankalan.log"
