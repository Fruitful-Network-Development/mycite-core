from __future__ import annotations

import re
from typing import Any

# Keep datum ordering semantics explicit here: identifiers are local
# layer-value_group-iteration addresses and must sort numerically by the
# three numeric segments. These are not SAMRAS node addresses and not MSS
# compact-array row indexes.

_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")


def parse_datum_identifier(identifier: str) -> tuple[int | None, int | None, int | None]:
    token = str(identifier or "").strip()
    if not _DATUM_ID_RE.fullmatch(token):
        return (None, None, None)
    try:
        layer_s, value_group_s, iteration_s = token.split("-", 2)
        return (int(layer_s), int(value_group_s), int(iteration_s))
    except Exception:
        return (None, None, None)


def datum_sort_key(identifier: object, fallback: object = "") -> tuple[int, int, int, str]:
    token = str(identifier or fallback or "").strip()
    layer, value_group, iteration = parse_datum_identifier(token)
    if isinstance(layer, int) and isinstance(value_group, int) and isinstance(iteration, int):
        return (layer, value_group, iteration, token)
    return (10**9, 10**9, 10**9, token)


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        list(rows or []),
        key=lambda row: datum_sort_key(
            row.get("identifier"),
            row.get("row_id"),
        ),
    )


class CompactionResult:
    def __init__(self, *, rows: list[dict[str, Any]], identifier_map: dict[str, str], changed: bool):
        self.rows = rows
        self.identifier_map = identifier_map
        self.changed = changed


def compact_iterations(rows: list[dict[str, Any]]) -> CompactionResult:
    payload = [dict(row) for row in list(rows or [])]
    grouped: dict[tuple[int, int], list[tuple[int, str, dict[str, Any]]]] = {}
    identifier_map: dict[str, str] = {}
    changed = False

    for row in payload:
        old_identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
        if not old_identifier:
            continue
        layer, value_group, iteration = parse_datum_identifier(old_identifier)
        if layer is None or value_group is None:
            identifier_map[old_identifier] = old_identifier
            continue
        sort_iteration = int(iteration) if isinstance(iteration, int) and iteration > 0 else 10**9
        grouped.setdefault((int(layer), int(value_group)), []).append((sort_iteration, old_identifier, row))

    for (layer, value_group), entries in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        entries.sort(key=lambda item: (item[0], item[1]))
        for next_iteration, (_old_sort, old_identifier, row) in enumerate(entries, start=1):
            new_identifier = f"{layer}-{value_group}-{next_iteration}"
            identifier_map[old_identifier] = new_identifier
            if new_identifier != old_identifier:
                changed = True
            row["row_id"] = new_identifier
            row["identifier"] = new_identifier

    ordered_rows = sort_rows(payload)
    return CompactionResult(rows=ordered_rows, identifier_map=identifier_map, changed=changed)
