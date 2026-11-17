"""Header row, CSV encoding and delimiter detection (IN-4, IN-6), carried over from V1 ``readers.py``.

Changes from V1: a header that can't be found is an error (no fall-back to the first non-empty row, no manual
override), and blank means empty or only spaces (T14).
"""
from __future__ import annotations

import codecs
import csv
import re
from datetime import date, datetime

from sankalan.model.template import ENC_1252, ENC_UTF8, ENC_UTF8_BOM

HEADER_SCAN_ROWS = 30
CSV_SAMPLE_BYTES = 64 * 1024
CSV_DELIMITERS = ",;\t|"


def norm(s) -> str:
    """MAP-2: header names compare ignoring case, spaces, dots, underscores and hyphens."""
    return re.sub(r"[\s._\-]+", "", str(s).strip().lower())


def is_blank(v) -> bool:
    """T14: a cell is blank when it is empty or holds only spaces."""
    return v is None or (isinstance(v, str) and v.strip(" ") == "")


def _filled(row) -> list:
    return [v for v in row if not is_blank(v)]


def detect_header(rows: list[list], known_names: set[str] | None = None) -> int | None:
    """The 0-based index into ``rows`` of the header row, or None when no row looks like a header.

    With ``known_names`` (normalised template column names and aliases), the row matching most of them wins.
    Otherwise, or when none matches, the first row of text cells that is at least 60% as wide as the widest row
    (two cells or more, unless the sheet has one column)."""
    scan = rows[:HEADER_SCAN_ROWS]
    if known_names:
        best, best_i = 0, None
        for i, r in enumerate(scan):
            score = sum(1 for v in r if isinstance(v, str) and not is_blank(v) and norm(v) in known_names)
            if score > best:
                best, best_i = score, i
        if best_i is not None:
            return best_i
    widest = max((len(_filled(r)) for r in scan), default=0)
    if widest == 0:
        return None
    for i, r in enumerate(scan):
        f = _filled(r)
        if len(f) >= min(2, widest) and len(f) >= 0.6 * widest and all(isinstance(v, str) for v in f):
            return i
    return None


def make_headers(raw: list) -> list[str]:
    """Header names for a header row: up to the last filled cell; empty cells become "Column N"; repeated names get
    " (2)", " (3)"."""
    last = len(raw)
    while last > 0 and is_blank(raw[last - 1]):
        last -= 1
    headers, seen = [], {}
    for i, v in enumerate(raw[:last]):
        if is_blank(v):
            name = f"Column {i + 1}"
        elif isinstance(v, bool):
            name = "TRUE" if v else "FALSE"
        elif isinstance(v, float) and v.is_integer():
            name = str(int(v))
        elif isinstance(v, datetime):
            name = v.strftime("%d-%m-%Y")
        elif isinstance(v, date):
            name = v.strftime("%d-%m-%Y")
        else:
            name = str(v).strip()
        base, n = name, seen.get(name.lower(), 0)
        if n:
            name = f"{base} ({n + 1})"
        seen[base.lower()] = n + 1
        headers.append(name)
    return headers


# ---------------------------------------------------------------------------------------------- CSV (IN-4)
class Utf8Check:
    """Feed a file's bytes in chunks; ``ok`` stays True while they are valid UTF-8 (with or without a BOM)."""

    def __init__(self):
        self._dec = codecs.getincrementaldecoder("utf-8")()
        self.ok = True
        self.bom = None

    def feed(self, chunk: bytes, final: bool = False) -> None:
        if self.bom is None:
            self.bom = chunk.startswith(codecs.BOM_UTF8)
        if not self.ok:
            return
        try:
            self._dec.decode(chunk, final)
        except UnicodeDecodeError:
            self.ok = False


def encoding_from_check(check: Utf8Check) -> str:
    if check.ok:
        return ENC_UTF8_BOM if check.bom else ENC_UTF8
    return ENC_1252


def read_codec(encoding: str) -> str:
    """The codec to read with: any UTF-8 file is read with utf-8-sig, so a BOM never ends up in the first header."""
    return "utf-8-sig" if encoding in (ENC_UTF8, ENC_UTF8_BOM) else ENC_1252


def decode_sample(sample: bytes, encoding: str) -> str:
    text = sample.decode(read_codec(encoding), errors="replace")
    return text


def detect_delimiter(text: str) -> str:
    """Comma, semicolon, tab or pipe, from the first lines of the sample."""
    lines = text.splitlines()
    if len(text) >= CSV_SAMPLE_BYTES and len(lines) > 1:
        lines = lines[:-1]                   # the last line may be cut off
    sample = "\n".join(lines[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=CSV_DELIMITERS).delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in CSV_DELIMITERS}
        return max(counts, key=counts.get) if any(counts.values()) else ","
