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
