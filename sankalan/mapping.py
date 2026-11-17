"""Column mapping: source headers to template column IDs (MAP-1 to MAP-7, MAP-11, MAP-13, TPL-6, TPL-8), the
automatic match carried over from V1 ``mapping.py``.

``MappingPlan`` holds the Mapping step's decisions: one cell per template column and file-sheet, plus every source
header no template column uses. Nothing is written to the template here; the run applies learned aliases and added
columns at commit, inside the commit transaction (RUN-14: a discarded run keeps nothing).
"""
from __future__ import annotations

from dataclasses import dataclass

from sankalan.ingest.detect import norm
from sankalan.model.template import (DATE, NUMBER, TYPES, Column, Template, TemplateError, active, next_column_id,
                                     outputs_using)


def known_names(columns: list[Column]) -> set[str]:
    """Normalised names and aliases of the template's columns, for header detection."""
    out = set()
    for c in active(columns):
        out.add(norm(c.name))
        out.update(norm(a) for a in c.aliases)
    return out


def auto_map(columns: list[Column], headers: list[str]) -> dict[str, int | None]:
    """Column ID → position of the matching source header (by name, then alias), or None. Each header is used at
    most once."""
    by_norm: dict[str, int] = {}
    for i, h in enumerate(headers):
        by_norm.setdefault(norm(h), i)
    used: set[int] = set()
    result: dict[str, int | None] = {}
    for c in active(columns):
        pos = None
        for candidate in [c.name, *c.aliases]:
            i = by_norm.get(norm(candidate))
            if i is not None and i not in used:
                pos = i
                break
        if pos is not None:
            used.add(pos)
        result[c.id] = pos
    return result


def unmapped_headers(mapping: dict[str, int | None], headers: list[str]) -> list[int]:
    used = {p for p in mapping.values() if p is not None}
    return [i for i in range(len(headers)) if i not in used]


def headers_match(columns: list[Column], headers: list[str]) -> bool:
    """TPL-6: every template column found and no new header, so the Mapping step can be skipped."""
    m = auto_map(columns, headers)
    return all(p is not None for p in m.values()) and not unmapped_headers(m, headers)


# ---------------------------------------------------------------------------------------------- decisions (Phase 5)
# How a template column gets its value in one file-sheet
BY_NAME, BY_ALIAS = "name", "alias"                 # automatic (MAP-2, MAP-3)
SAVE_ALIAS, RUN_ONLY = "save_alias", "run_only"     # picked by hand (MAP-5)
LEAVE_NULL = "null"                                  # MAP-6
ADDED = "added"                                      # a column added in this run (MAP-7)
AUTOMATIC = (BY_NAME, BY_ALIAS)
# What happens to a source header no template column uses (MAP-7)
LEAVE_OUT, ADD_COLUMN = "leave_out", "add"


def _copy(c: Column) -> Column:
    return Column(**{**c.__dict__, "aliases": list(c.aliases)})


@dataclass
class Sheet:
    """One file-sheet in the grid. ``key`` is its file index (``_src_file``)."""
    key: int
    file_name: str
    sheet: str
    headers: list[str]

    @property
    def label(self) -> str:
        return f"{self.file_name} · {self.sheet}" if self.sheet else self.file_name


@dataclass
class Cell:
    column_id: str
    sheet: int
    position: int | None = None
    how: str | None = None          # None = undecided (highlighted, MAP-4)

    @property
    def decided(self) -> bool:
        return self.how is not None


@dataclass
class NewColumn:
    """A source header added as a template column in this run (MAP-7). Its type is fixed once the run commits."""
    column: Column
    sheet: int
    position: int


@dataclass
class MappingResult:
    mappings: dict[int, dict[str, int | None]]      # file index -> column ID -> source position (None = null)
    columns: list[Column]                           # the run's columns: the template's plus any added
    aliases: dict[str, list[str]]                   # column ID -> aliases to save to the template at commit
    new_columns: list[Column]
    decisions: list[dict]                           # for the run summary (RUN-12, C6-04)


class MappingError(ValueError):
    """A decision that can't be made; the message is plain enough to show."""


class MappingPlan:
    """The Mapping step's state. Rows = template columns, columns = file-sheets (MAP-4)."""

    def __init__(self, template: Template, sheets: list[Sheet]):
        self.template = template
        self.columns = [_copy(c) for c in template.columns]
        self.sheets = list(sheets)
        self._sheet = {s.key: s for s in self.sheets}
        self.cells: dict[tuple[str, int], Cell] = {}
        self.extras: dict[tuple[int, int], str | None] = {}     # (sheet, position) -> LEAVE_OUT | ADD_COLUMN | None
        self.new_columns: list[NewColumn] = []
        for s in self.sheets:
            m = auto_map(self.columns, s.headers)
            for c in active(self.columns):
                pos = m.get(c.id)
                how = None
                if pos is not None:
                    how = BY_NAME if norm(s.headers[pos]) == norm(c.name) else BY_ALIAS
                self.cells[(c.id, s.key)] = Cell(c.id, s.key, pos, how)
            for pos in unmapped_headers(m, s.headers):
                self.extras[(s.key, pos)] = None

    # ------------------------------------------------------------------------------------------ reading
    @property
    def skip(self) -> bool:
        """TPL-6: every header in every file-sheet matches, so the Mapping step is skipped."""
        return all(c.how in AUTOMATIC for c in self.cells.values()) and not self.extras

    def cell(self, column_id: str, sheet: int) -> Cell:
        return self.cells[(column_id, sheet)]

    def extra_headers(self, sheet: int) -> dict[int, str | None]:
        """Source headers in a file-sheet that no template column uses, with their decision (None = undecided)."""
        return {pos: how for (key, pos), how in sorted(self.extras.items()) if key == sheet}

    def undecided(self) -> list[tuple]:
        """Undecided items in grid order: ("cell", column ID, sheet) by template column then file-sheet, then
        ("extra", sheet, position) by file-sheet then position (MAP-13)."""
        out: list[tuple] = []
        for c in active(self.columns):
            for s in self.sheets:
                cell = self.cells.get((c.id, s.key))
                if cell is not None and not cell.decided:
                    out.append(("cell", c.id, s.key))
        for s in self.sheets:
            for pos, how in self.extra_headers(s.key).items():
                if how is None:
                    out.append(("extra", s.key, pos))
        return out

    def first_undecided(self) -> tuple | None:
        """Where Next sends the user while decisions are left (MAP-13); None when every decision is made."""
        left = self.undecided()
        return left[0] if left else None

    @property
    def complete(self) -> bool:
        return not self.undecided()

    def headers_free(self, sheet: int) -> list[int]:
        """Positions in a file-sheet that no column (template or added) uses."""
        used = {c.position for (_cid, k), c in self.cells.items() if k == sheet and c.position is not None}
        return [i for i in range(len(self._sheet[sheet].headers)) if i not in used]

    # ------------------------------------------------------------------------------------------ deciding
    def _release(self, cell: Cell) -> None:
        """A header picked by hand goes back to the extra headers when the cell's decision changes."""
        if cell.position is not None and cell.how in (SAVE_ALIAS, RUN_ONLY):
            self.extras[(cell.sheet, cell.position)] = None

    def map(self, column_id: str, sheet: int, position: int, *, save_alias: bool) -> None:
        """Map a template column to a header picked by hand: "Map and save as alias" or "This run only" (MAP-5)."""
        s = self._sheet[sheet]
        if not 0 <= position < len(s.headers):
            raise MappingError("no such header")
        cell = self.cells[(column_id, sheet)]
        self._drop_new(sheet, position)
        if position != cell.position and position not in self.headers_free(sheet):
            raise MappingError(f"{s.headers[position]} is already mapped to another column")
        self._release(cell)
        self.extras.pop((sheet, position), None)
        cell.position = position
        cell.how = SAVE_ALIAS if save_alias else RUN_ONLY

    def leave_null(self, column_id: str, sheet: int) -> list[str]:
        """Leave a missing column as null in this file-sheet (MAP-6). Returns warnings naming each default output
        that uses the column: those rows show as (Null) there."""
        cell = self.cells[(column_id, sheet)]
        self._release(cell)
        cell.position = None
        cell.how = LEAVE_NULL
        return self.null_warnings(column_id)

    def null_warnings(self, column_id: str) -> list[str]:
        return [f'Default output "{name}" will show these rows as (Null).'
                for name in outputs_using(self.template, column_id)]

    def leave_out(self, sheet: int, position: int) -> None:
        """A file column not in the template is not loaded (MAP-7)."""
        if (sheet, position) not in self.extras:
            raise MappingError("That header is mapped to a template column")
        self._drop_new(sheet, position)
        self.extras[(sheet, position)] = LEAVE_OUT

    def add_column(self, sheet: int, position: int, name: str, type_: str, *, decimals: int | None = None,
                   date_format: str | None = None) -> str:
        """Add a file column as a new template column (MAP-7, MAP-11). The same header in the other file-sheets
        maps to it when it is still undecided there; file-sheets without it give null. Returns the column ID."""
        if (sheet, position) not in self.extras:
            raise MappingError("That header is mapped to a template column")
        name = name.strip()
        if not name:
            raise MappingError("The new column needs a name")
        if type_ not in TYPES:
            raise MappingError(f"unknown type {type_!r}")
        self._drop_new(sheet, position)
        if norm(name) in {norm(c.name) for c in active(self.columns)}:
            raise MappingError(f"The template already has a column named {name}")
        col = Column(next_column_id(self.columns), name, type_,
                     decimals if type_ == NUMBER else None, date_format if type_ == DATE else None)
        self.columns.append(col)
        self.new_columns.append(NewColumn(col, sheet, position))
        self.extras[(sheet, position)] = ADD_COLUMN
        header = norm(self._sheet[sheet].headers[position])
        for s in self.sheets:
            pos = position if s.key == sheet else None
            if s.key != sheet:
                for p, how in self.extra_headers(s.key).items():
                    if how is None and norm(s.headers[p]) == header:
                        pos = p
                        self.extras.pop((s.key, p))
                        break
            self.cells[(col.id, s.key)] = Cell(col.id, s.key, pos, ADDED if pos is not None else LEAVE_NULL)
        return col.id

    def _drop_new(self, sheet: int, position: int) -> None:
        """Undo an earlier Add as new column made on this header."""
        for nc in list(self.new_columns):
            if nc.sheet == sheet and nc.position == position:
                self.new_columns.remove(nc)
                self.columns = [c for c in self.columns if c.id != nc.column.id]
                for key in [k for k in self.cells if k[0] == nc.column.id]:
                    cell = self.cells.pop(key)
                    if key[1] != sheet and cell.position is not None:
                        self.extras[(key[1], cell.position)] = None
                self.extras[(sheet, position)] = None

    # ------------------------------------------------------------------------------------------ result
    def result(self) -> MappingResult:
        if not self.complete:
            raise MappingError("Some columns still need a decision")
        mappings: dict[int, dict[str, int | None]] = {s.key: {} for s in self.sheets}
        for (cid, key), cell in self.cells.items():
            mappings[key][cid] = cell.position
        aliases: dict[str, list[str]] = {}
        decisions: list[dict] = []
        for c in active(self.columns):
            for s in self.sheets:
                cell = self.cells.get((c.id, s.key))
                if cell is None or cell.how in AUTOMATIC:
                    continue
                d = {"kind": None, "file": s.file_name, "sheet": s.sheet, "column_id": c.id, "column": c.name}
                if cell.how in (SAVE_ALIAS, RUN_ONLY):
                    header = s.headers[cell.position]
                    d.update(kind="alias" if cell.how == SAVE_ALIAS else "run_only", header=header)
                    if cell.how == SAVE_ALIAS:
                        known = {norm(c.name), *(norm(a) for a in c.aliases),
                                 *(norm(a) for a in aliases.get(c.id, []))}
                        if norm(header) not in known:
                            aliases.setdefault(c.id, []).append(header)
                elif cell.how == LEAVE_NULL:
                    d.update(kind="null")
                elif cell.how == ADDED:
                    d.update(kind="added", header=s.headers[cell.position], type=c.type)
                decisions.append(d)
        for (key, pos), how in sorted(self.extras.items()):
            if how == LEAVE_OUT:
                s = self._sheet[key]
                decisions.append({"kind": "leave_out", "file": s.file_name, "sheet": s.sheet,
                                  "header": s.headers[pos]})
        return MappingResult(mappings, [_copy(c) for c in self.columns], aliases,
                             [_copy(nc.column) for nc in self.new_columns], decisions)


def apply_to_template(template: Template, result: MappingResult) -> bool:
    """Aliases learned and columns added in a run, applied to the template at commit (MAP-5, MAP-7). Returns True
    when anything changed."""
    changed = False
    for cid, names in result.aliases.items():
        col = template.column(cid)
        for a in names:
            if norm(a) not in {norm(x) for x in col.aliases}:
                col.aliases.append(a)
                changed = True
    have = {c.id for c in template.columns}
    for c in result.new_columns:
        if c.id in have:
            raise TemplateError(f"Column {c.name} was added to the template meanwhile")
        template.columns.append(_copy(c))
        changed = True
    return changed


def describe(decision: dict) -> str:
    """One line of the run summary's mapping decisions (RUN-12, C6-04)."""
    k = decision["kind"]
    where = decision["file"] + (f" · {decision['sheet']}" if decision.get("sheet") else "")
    if k == "alias":
        return f"{decision['header']} mapped to {decision['column']} and saved as an alias ({where})"
    if k == "run_only":
        return f"{decision['header']} mapped to {decision['column']} for this run only ({where})"
    if k == "null":
        return f"{decision['column']} left as null ({where})"
    if k == "added":
        return f"{decision['header']} added as new column {decision['column']} ({decision['type']}) ({where})"
    if k == "leave_out":
        return f"{decision['header']} left out ({where})"
    return k
