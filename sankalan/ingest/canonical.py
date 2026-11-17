r"""The raw staged text form (Tech spec, Ingestion → Read).

One UTF-8 CSV per file and sheet in ``_staging\<id>\raw\``, with ``_src_row`` first and every value as text:

- numbers: the shortest exact decimal, never in exponent form (spike S6: calamine gives binary floats)
- Excel dates: ``YYYY-MM-DD``; a date-time with a time of day ``YYYY-MM-DD HH:MM:SS`` (the Date rule drops the time)
- text: exactly as typed, spaces included (T14; V1 stripped them, V2 must not)
- an empty cell: an empty field
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

RAW_ENCODING = "utf-8"
SRC_ROW = "_src_row"


def value_name(i: int) -> str:
    """Raw CSV column for the source column at 0-based position ``i``."""
    return f"v{i}"


def _float(v: float) -> str:
    if v.is_integer():
        return str(int(v))
    r = repr(v)                                 # shortest round-trip form
    if "e" in r or "n" in r:                    # exponent (or inf/nan): write it out in full
        if v != v or v in (float("inf"), float("-inf")):
            return r
        return format(Decimal(r), "f")
    return r


def _datetime(v: datetime) -> str:
    if v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0:
        return v.date().isoformat()
    return v.strftime("%Y-%m-%d %H:%M:%S")


_BY_TYPE = {
    str: lambda v: v,
    type(None): lambda v: "",
    float: _float,
    bool: lambda v: "TRUE" if v else "FALSE",
    int: str,
    datetime: _datetime,
    date: lambda v: v.isoformat(),
    time: lambda v: v.strftime("%H:%M:%S"),
    timedelta: str,
}


def staged_text(v) -> str:
    f = _BY_TYPE.get(type(v))
    if f is not None:
        return f(v)
    if isinstance(v, datetime):
        return _datetime(v)
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def is_blank_row(vals: list[str]) -> bool:
    """T14: every value empty or only spaces."""
    for v in vals:
        if v and v.strip(" "):
            return False
    return True


class RawWriter:
    """Writes one raw staged file. ``width`` is the number of source columns (the header width)."""

    def __init__(self, path: Path, width: int):
        self.path = Path(path)
        self.width = width
        self._fh = open(self.path, "w", encoding=RAW_ENCODING, newline="")
        self._w = csv.writer(self._fh, lineterminator="\n")
        self._w.writerow([SRC_ROW] + [value_name(i) for i in range(width)])
        self.rows = 0

    def write(self, src_row: int, values: list[str]) -> None:
        self._w.writerow([src_row, *values])
        self.rows += 1

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
