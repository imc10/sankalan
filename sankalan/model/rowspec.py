"""The Rows view's settings and the runs it reads (Feature Spec A2 ROW-1 to ROW-14; Tech spec A2 10.1).

A ``RowSpec`` lives in memory only: row views are never saved (ROW-3). There is no sort (D71): rows always come in
stored order, by Run ID, then file and sheet in load order, then Source Row (ROW-12).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sankalan.model.definition import Definition, Filter


@dataclass
class RowSpec:
    template_id: str
    filters: list[Filter] = field(default_factory=list)   # the builder's filters, compiled as for Analysis (ROW-6)
    columns: list[str] = field(default_factory=list)      # ticked column IDs, in the chosen order (ROW-7)
    show_source: bool = False                             # Show them on screen (ROW-8)

    def as_definition(self) -> Definition:
        """The filters as a definition, so ``definition.check`` and ``analyses.describe`` read them as Analysis's."""
        return Definition(self.template_id, list(self.filters), [], [], False)


@dataclass(frozen=True)
class RunRef:
    """A ticked run, read from the catalogue at Run. Runs are always handled in Run ID order (``number``)."""
    id: str
    number: int
    label: str                                            # R-0003
    data_path: Path
    rows_loaded: int
    file_names: dict = field(default_factory=dict, hash=False, compare=False)   # _src_file -> file name
