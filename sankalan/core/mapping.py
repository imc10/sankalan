"""Column mapping (MAP-1 .. MAP-8)."""
from __future__ import annotations

import re


def norm(s) -> str:
    """MAP-2: ignore case, spaces, dots, underscores and hyphens."""
    return re.sub(r"[\s._\-]+", "", str(s).strip().lower())


def auto_map(columns, headers):
    """Return {target: (source_header|None, method)} with method in name|alias|None.
    Each source header is used at most once."""
    by_norm = {}
    for h in headers:
        by_norm.setdefault(norm(h), h)
    used = set()
    result = {}
    for c in columns:
        src, method = None, None
        n = norm(c["name"])
        if n in by_norm and by_norm[n] not in used:
            src, method = by_norm[n], "name"
        else:
            for a in c.get("aliases", []):
                na = norm(a)
                if na in by_norm and by_norm[na] not in used:
                    src, method = by_norm[na], "alias"
                    break
        if src:
            used.add(src)
        result[c["name"]] = (src, method)
    return result


def unmapped_sources(mapping: dict, headers):
    used = {s for s, _ in mapping.values() if s}
    return [h for h in headers if h not in used]
