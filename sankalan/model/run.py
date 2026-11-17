"""What a run commit writes to the catalogue (RUN-2, T8, T22)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

STATUS_COMMITTED = "committed"
STATUS_OVERRIDE = "committed_override"


def run_label(number: int) -> str:
    """The Run ID shown on screen: R-0001, R-0002, ..."""
    return f"R-{number:04d}"


@dataclass
class RunFile:
    file_index: int
    file_name: str
    path: str
    size: int
    sheet: str
    sha256: str
    rows_read: int
    modified: datetime | None = None
    header_row: int | None = None
    hidden_rows: int = 0
    sheets_skipped: list = field(default_factory=list)
    duplicate_decision: str = ""


@dataclass
class IssueCount:
    rule: str
    file_index: int
    sheet: str
    errors: int
    warnings: int


@dataclass
class RunOutput:
    position: int
    name: str
    definition: dict
    file: str


@dataclass
class NewRun:
    """Everything the commit transaction inserts. The Run ID number is issued inside that transaction."""
    template_id: str
    template_version: int
    rows_read: int
    rows_loaded: int
    rows_left_out: int = 0
    left_out_by_reason: dict = field(default_factory=dict)
    errors: int = 0
    warnings: int = 0
    status: str = STATUS_COMMITTED
    comment: str = ""
    run_changes: dict = field(default_factory=dict)
    totals: dict = field(default_factory=dict)
    files: list[RunFile] = field(default_factory=list)
    issue_counts: list[IssueCount] = field(default_factory=list)
    outputs: list[RunOutput] = field(default_factory=list)


@dataclass(frozen=True)
class RunRow:
    """A committed run as listed from the catalogue."""
    id: str
    template_id: str
    run_number: int
    template_version: int
    loaded_on: datetime
    status: str
    damaged: bool
    comment: str
    rows_read: int
    rows_loaded: int
    rows_left_out: int

    @property
    def label(self) -> str:
        return run_label(self.run_number)
