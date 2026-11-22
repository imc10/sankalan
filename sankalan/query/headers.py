"""Result headers (Feature Spec A2 MEA-7, MEA-8, P3; Tech spec A2 9.3).

``resolve_headers`` gives a result's header text in result order: the group levels, then the measures in MEA-6 order
(``definition.flat_measures``).

- Group: the column's name, " (removed)" added for a removed column (T23).
- Measure with a custom name: the name.
- Measure with the default name: "<Column> · <Sum | Count | Count distinct | Average | Min | Max>", or "Rows · Count";
  a default follows later renames of the column (MEA-7).
- Clashes (P3): group headers and custom names are placed first; then each default, in order, gets " (2)", " (3)" …
  when its name is already taken, ignoring case. Two group levels on the same column get the same treatment.

The hover text of a measure header is its default form, whatever its name (MEA-8).
"""
from __future__ import annotations

from sankalan.model import definition as d
from sankalan.model.definition import Definition
from sankalan.model.template import Column


def _free(name: str, taken: set[str]) -> str:
    if name.lower() not in taken:
        return name
    n = 2
    while f"{name} ({n})".lower() in taken:
        n += 1
    return f"{name} ({n})"


def resolve_headers(definition: Definition, columns: list[Column]) -> list[str]:
    """Header text per result column: groups, then measures (MEA-6 order)."""
    by_id = {c.id: c for c in columns}
    taken: set[str] = set()
    out: list[str | None] = []
    for g in definition.groups:
        name = _free(d.card_name(g.column_id, by_id), taken)
        taken.add(name.lower())
        out.append(name)
    flat = d.flat_measures(definition)
    for m in flat:                                  # custom names are placed before any default
        if m.name is not None:
            taken.add(m.name.lower())
    for m in flat:
        if m.name is not None:
            out.append(m.name)
        else:
            name = _free(d.default_name(m.column_id, m.fn, by_id), taken)
            taken.add(name.lower())
            out.append(name)
    return out


def hover_texts(definition: Definition, columns: list[Column]) -> list[str | None]:
    """The tooltip per result column: None for a group, the default form ("Invoice No · Count") for a measure."""
    by_id = {c.id: c for c in columns}
    return ([None] * len(definition.groups)
            + [d.default_name(m.column_id, m.fn, by_id) for m in d.flat_measures(definition)])


def rename_problem(headers: list[str], index: int, name: str | None) -> str | None:
    """MEA-8: a typed name for result column ``index`` (already trimmed; None restores the default). The message
    when it is too long or another header already has it, ignoring case; None when it can be used."""
    if name is None:
        return None
    if len(name) > d.NAME_MAX:
        return f"A column name can be up to {d.NAME_MAX} characters"
    if any(h.lower() == name.lower() for i, h in enumerate(headers) if i != index):
        return d.name_taken_message(name)
    return None
