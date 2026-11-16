"""Column mapping: source headers to template column IDs (MAP-1, MAP-2, TPL-6), carried over from V1 ``mapping.py``.

Phase 2 needs the automatic match and the header-match check; the mapping decisions (alias learning, leave as
null, leave out, add as new column) come in Phase 5.
"""
from __future__ import annotations

from sankalan.ingest.detect import norm
from sankalan.model.template import Column, active


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
