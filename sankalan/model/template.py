"""What ingestion needs from a template: its columns and how to read source files (TPL-1, IN-4, IN-5, MAP-10, T13).

The full template model (rules, default outputs, versions) grows in later phases; these types are the part the
probe, read and convert stages use.
"""
from __future__ import annotations

from dataclasses import dataclass, field

TEXT, NUMBER, DATE = "Text", "Number", "Date"
TYPES = (TEXT, NUMBER, DATE)

# Date format for text dates (MAP-10). None = the column holds Excel dates; ISO text (YYYY-MM-DD, which is also how
# Excel dates are staged) is always read.
DATE_FORMATS = ("DD-MM-YYYY", "DD/MM/YYYY")

DECIMALS_DEFAULT = 2
DECIMALS_MAX = 6

# Sheets to read (IN-5)
SHEETS_BY_NAME, SHEETS_FIRST_VISIBLE, SHEETS_ALL_VISIBLE = "name", "first", "all"

# CSV encodings (IN-4). "utf-8" reads files with or without a BOM.
ENC_UTF8, ENC_UTF8_BOM, ENC_1252 = "utf-8", "utf-8-sig", "cp1252"
ENCODING_LABELS = {ENC_UTF8: "UTF-8", ENC_UTF8_BOM: "UTF-8 with BOM", ENC_1252: "Windows-1252"}
DELIMITERS = {",": "Comma", ";": "Semicolon", "\t": "Tab", "|": "Pipe"}


@dataclass
class Column:
    id: str                         # stable Parquet column name: c001, c002, ...
    name: str
    type: str = TEXT
    decimals: int | None = None     # Number only, 0-6, default 2 (T13)
    date_format: str | None = None  # Date only: None (Excel dates) or one of DATE_FORMATS
    aliases: list[str] = field(default_factory=list)
    totals_check: bool = False
    removed: bool = False

    def __post_init__(self):
        if self.type not in TYPES:
            raise ValueError(f"unknown column type {self.type!r}")
        if self.type == NUMBER:
            if self.decimals is None:
                self.decimals = DECIMALS_DEFAULT
            if not (0 <= int(self.decimals) <= DECIMALS_MAX):
                raise ValueError("decimals must be 0 to 6")
            self.decimals = int(self.decimals)
        else:
            self.decimals = None
        if self.type == DATE:
            if self.date_format is not None and self.date_format not in DATE_FORMATS:
                raise ValueError(f"unknown date format {self.date_format!r}")
        else:
            self.date_format = None


@dataclass
class SourceSettings:
    """How to read source files (TPL-1): sheets to read, and the CSV encoding and delimiter overrides."""
    sheets: str = SHEETS_FIRST_VISIBLE
    sheet_names: list[str] = field(default_factory=list)   # SHEETS_BY_NAME: one or more names
    csv_encoding: str | None = None                        # None = detect
    csv_delimiter: str | None = None                       # None = detect

    def __post_init__(self):
        if self.sheets not in (SHEETS_BY_NAME, SHEETS_FIRST_VISIBLE, SHEETS_ALL_VISIBLE):
            raise ValueError(f"unknown sheets setting {self.sheets!r}")
        if self.sheets == SHEETS_BY_NAME and not self.sheet_names:
            raise ValueError("sheets by name needs at least one name")
        if self.csv_encoding is not None and self.csv_encoding not in ENCODING_LABELS:
            raise ValueError(f"unknown encoding {self.csv_encoding!r}")
        if self.csv_delimiter is not None and self.csv_delimiter not in DELIMITERS:
            raise ValueError(f"unknown delimiter {self.csv_delimiter!r}")


def active(columns: list[Column]) -> list[Column]:
    return [c for c in columns if not c.removed]


def typed(columns: list[Column]) -> list[Column]:
    """The active Number and Date columns: the ones whose text is kept in a companion column (Tech spec A2 5.1)."""
    return [c for c in active(columns) if c.type in (NUMBER, DATE)]


# ---------------------------------------------------------------------------------------------- the whole template
class TemplateError(ValueError):
    """A template change that isn't allowed; the message is plain enough to show (TPL-9, MAP-11, MAP-12)."""


@dataclass
class DefaultOutput:
    """A default output (DO-1): a required name and an analysis definition (``model.definition.Definition`` as a
    dict, so this module stays free of the query model)."""
    name: str
    definition: dict

    def to_dict(self) -> dict:
        import copy
        return {"name": self.name, "definition": copy.deepcopy(self.definition)}

    @classmethod
    def from_dict(cls, d: dict) -> "DefaultOutput":
        import copy
        return cls(d["name"], copy.deepcopy(d.get("definition") or {}))


def column_to_dict(c: Column) -> dict:
    return {"id": c.id, "name": c.name, "type": c.type, "decimals": c.decimals, "date_format": c.date_format,
            "aliases": list(c.aliases), "totals_check": c.totals_check, "removed": c.removed}


def column_from_dict(d: dict) -> Column:
    return Column(d["id"], d["name"], d.get("type", TEXT), d.get("decimals"), d.get("date_format"),
                  list(d.get("aliases") or []), bool(d.get("totals_check")), bool(d.get("removed")))


def settings_to_dict(s: SourceSettings) -> dict:
    return {"sheets": s.sheets, "sheet_names": list(s.sheet_names), "csv_encoding": s.csv_encoding,
            "csv_delimiter": s.csv_delimiter}


def settings_from_dict(d: dict | None) -> SourceSettings:
    d = d or {}
    return SourceSettings(d.get("sheets", SHEETS_FIRST_VISIBLE), list(d.get("sheet_names") or []),
                          d.get("csv_encoding"), d.get("csv_delimiter"))


@dataclass
class Template:
    """Every setting of one client task (TPL-1). ``rules`` are ``model.rule.Rule`` objects; ``export`` holds the
    export defaults (folder, file-name pattern, delimiter, encoding) as plain values. ``version`` is the saved
    version this object was loaded from (TPL-7)."""
    id: str
    client_id: str
    name: str
    source: SourceSettings = field(default_factory=SourceSettings)
    columns: list[Column] = field(default_factory=list)
    rules: list = field(default_factory=list)
    outputs: list[DefaultOutput] = field(default_factory=list)
    export: dict = field(default_factory=dict)
    version: int = 0
    checks: bool = True             # Check data before loading (NCK-1, T43): held in the settings JSON


    def column(self, column_id: str) -> Column:
        for c in self.columns:
            if c.id == column_id:
                return c
        raise KeyError(column_id)

    @property
    def active_columns(self) -> list[Column]:
        return active(self.columns)

    def settings_dict(self) -> dict:
        return {"source": settings_to_dict(self.source), "export": dict(self.export), "checks": bool(self.checks)}

    def snapshot(self) -> dict:
        """The template_version snapshot (TPL-7): settings, columns, rules and default outputs."""
        return {"settings": self.settings_dict(), "name": self.name,
                "columns": [column_to_dict(c) for c in self.columns],
                "rules": [r.to_dict() for r in self.rules],
                "outputs": [o.to_dict() for o in self.outputs]}

    def copy(self) -> "Template":
        from sankalan.model.rule import Rule
        snap = self.snapshot()
        return Template(self.id, self.client_id, self.name, settings_from_dict(snap["settings"]["source"]),
                        [column_from_dict(c) for c in snap["columns"]], [Rule.from_dict(r) for r in snap["rules"]],
                        [DefaultOutput.from_dict(o) for o in snap["outputs"]], dict(snap["settings"]["export"]),
                        self.version, bool(snap["settings"]["checks"]))


def next_column_id(columns: list[Column]) -> str:
    """The next stable column ID (c001, c002, ...). IDs are never reused, removed columns included."""
    n = 0
    for c in columns:
        if c.id.startswith("c") and c.id[1:].isdigit():
            n = max(n, int(c.id[1:]))
    return f"c{n + 1:03d}"


def definition_columns(definition: dict) -> set[str]:
    """Column IDs a definition uses in its filters, groups or measure cards (the Rows card uses none)."""
    out = set()
    for key in ("filters", "groups", "measures"):
        for item in definition.get(key) or []:
            if item.get("column_id") and item["column_id"] != "_rows":
                out.add(item["column_id"])
    return out


def outputs_using(template: Template, column_id: str) -> list[str]:
    """Names of the default outputs that use a column (MAP-6 warning, MAP-11 removal check)."""
    return [o.name for o in template.outputs if column_id in definition_columns(o.definition)]


def check_change(before: Template | None, after: Template, *, has_runs: bool) -> None:
    """Raise ``TemplateError`` for a save that isn't allowed:

    - type or decimal places changed on a column once the template has a committed run (TPL-9, MAP-12, T13);
    - a column removed (or missing) while a default output still uses it (MAP-11, C4-15);
    - a default output or rule on a column that doesn't exist;
    - duplicate column IDs."""
    ids = [c.id for c in after.columns]
    if len(ids) != len(set(ids)):
        raise TemplateError("Two columns have the same ID")
    live = {c.id for c in after.active_columns}
    for o in after.outputs:
        if not o.name.strip():
            raise TemplateError("Every default output needs a name")
        gone = definition_columns(o.definition) - live
        if gone:
            names = []
            for cid in sorted(gone):
                try:
                    names.append(after.column(cid).name)
                except KeyError:
                    names.append(cid)
            raise TemplateError(f"{', '.join(names)} can't be removed while the default output \"{o.name}\" "
                                f"uses it. Change that output first.")
    if before is not None and has_runs:
        old = {c.id: c for c in before.columns}
        for c in after.columns:
            o = old.get(c.id)
            if o is None:
                continue
            if o.type != c.type:
                raise TemplateError(f"The type of {o.name} can't change: data has already been loaded with it.")
            if o.decimals != c.decimals:
                raise TemplateError(f"The decimal places of {o.name} can't change: data has already been loaded "
                                    f"with them.")
        missing = set(old) - set(ids)
        if missing:
            raise TemplateError("Columns can be removed but not deleted once data has been loaded")
