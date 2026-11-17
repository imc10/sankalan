"""Export options and file names (EXP-2 to EXP-4, Tech spec Exports).

Every export is a CSV file (EXP-2): UTF-8 with BOM by default or plain UTF-8, delimiter comma, semicolon, tab or
pipe (EXP-3). File names come from the template's pattern, e.g. ``{Client}_{Template}_{RunID}_{Output}`` (EXP-4);
characters Windows doesn't allow in file names become ``_``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

DELIMITERS = {",": "Comma", ";": "Semicolon", "\t": "Tab", "|": "Pipe"}
DEFAULT_PATTERN = "{Client}_{Template}_{RunID}_{Output}"
PLACEHOLDERS = ("Client", "Template", "RunID", "Output")

# What {Output} stands for in exports that aren't a default output
DATA_NAME, LEFT_OUT_NAME, ISSUES_NAME = "Data", "Left-out rows", "Issues"

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


@dataclass(frozen=True)
class ExportOptions:
    delimiter: str = ","
    bom: bool = True                # UTF-8 with BOM (default, EXP-3); False = plain UTF-8

    def __post_init__(self):
        if self.delimiter not in DELIMITERS:
            raise ValueError(f"unknown delimiter {self.delimiter!r}")


def safe_file_name(name: str) -> str:
    """``: / \\ * ? " < > |`` and control characters become ``_`` (EXP-07). Trailing dots and spaces, which
    Windows drops, become ``_`` too, and a reserved device name (CON, NUL, ...) gets a leading ``_``."""
    out = _ILLEGAL.sub("_", name)
    stripped = out.rstrip(". ")
    if stripped != out:
        out = stripped + "_" * (len(out) - len(stripped))
    if out.split(".")[0].upper() in _RESERVED:
        out = "_" + out
    return out or "_"


def fill_pattern(pattern: str, **values: str) -> str:
    """The pattern with each ``{Placeholder}`` filled. An empty one (e.g. {RunID} for an analysis) drops out with its
    separator, so no doubled or trailing ``_`` is left."""
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in PLACEHOLDERS:
            return m.group(0)
        return str(values.get(key) or "\0")
    text = re.sub(r"\{(\w+)\}", sub, pattern)
    for empty in ("_\0", "\0_", "\0"):
        text = text.replace(empty, "")
    return text.strip()


def csv_file_name(pattern: str, **values: str) -> str:
    """The export file name: pattern filled, illegal characters replaced, ``.csv`` added."""
    name = safe_file_name(fill_pattern(pattern, **values) or "Export")
    return name if name.lower().endswith(".csv") else name + ".csv"


# ---------------------------------------------------------------------------------------------- template export defaults
# Keys of ``Template.export`` (TPL-1, UX-7): folder, pattern, delimiter, encoding ("utf-8-sig" = with BOM, "utf-8").
ENC_BOM, ENC_PLAIN = "utf-8-sig", "utf-8"
ENCODINGS = {ENC_BOM: "UTF-8 with BOM (opens cleanly in Excel)", ENC_PLAIN: "UTF-8"}


def default_folder() -> str:
    """Documents, when a template has no export folder yet."""
    import os
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, "Documents")


@dataclass(frozen=True)
class ExportDefaults:
    folder: str
    pattern: str = DEFAULT_PATTERN
    delimiter: str = ","
    bom: bool = True

    @classmethod
    def of(cls, export: dict | None) -> "ExportDefaults":
        e = export or {}
        delimiter = e.get("delimiter") if e.get("delimiter") in DELIMITERS else ","
        return cls(e.get("folder") or default_folder(), e.get("pattern") or DEFAULT_PATTERN, delimiter,
                   e.get("encoding", ENC_BOM) != ENC_PLAIN)

    def to_dict(self) -> dict:
        return {"folder": self.folder, "pattern": self.pattern, "delimiter": self.delimiter,
                "encoding": ENC_BOM if self.bom else ENC_PLAIN}

    @property
    def options(self) -> ExportOptions:
        return ExportOptions(self.delimiter, self.bom)


@dataclass(frozen=True)
class ExportRequest:
    """What the Export dialog (7.4, Phase 10) opens with (EXP-4, C4-18): the template's export defaults with the
    name pattern resolved for this export. ``kind``: data | issues | left_out | output | outputs (every output of
    the run, one file each) | analysis. ``output``: the output's position for ``output``; ``subtotals``: as shown;
    ``items``: set by a screen whose data isn't a committed run yet (the Validate step's issue list, RUNV-07): Job
    work returning the queries and file names. ``sankalan.runs.export_items`` resolves every other request."""
    kind: str
    template_id: str
    run_id: str | None
    folder: str
    file_name: str
    pattern: str
    options: ExportOptions
    output: int | None = None
    subtotals: bool | None = None
    values: dict | None = None          # Client, Template, RunID for the per-output names of Export all outputs
    items: Callable | None = field(default=None, compare=False)    # Job work → [(ExportQuery, file name)]


def prefill(kind: str, export: dict | None, *, template_id: str, client: str, template: str,
            run_id: str | None = None, run_label: str = "", output: str = "", position: int | None = None,
            subtotals: bool | None = None, items: Callable | None = None) -> ExportRequest:
    d = ExportDefaults.of(export)
    name = output or {"data": DATA_NAME, "issues": ISSUES_NAME, "left_out": LEFT_OUT_NAME}.get(kind, "")
    file_name = csv_file_name(d.pattern, Client=client, Template=template, RunID=run_label, Output=name)
    return ExportRequest(kind, template_id, run_id, d.folder, file_name, d.pattern, d.options, position, subtotals,
                         {"Client": client, "Template": template, "RunID": run_label}, items)
