"""Export options and file names (EXP-2 to EXP-4, Tech spec Exports).

Every export is a CSV file (EXP-2): UTF-8 with BOM by default or plain UTF-8, delimiter comma, semicolon, tab or
pipe (EXP-3). File names come from the template's pattern, e.g. ``{Client}_{Template}_{RunID}_{Output}`` (EXP-4);
characters Windows doesn't allow in file names become ``_``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

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
