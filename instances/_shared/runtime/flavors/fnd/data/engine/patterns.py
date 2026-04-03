from __future__ import annotations

from typing import Any


def describe_pattern_hooks() -> list[dict[str, str]]:
    return [
        {
            "id": "collection_row",
            "description": "value_group=0 rows with selection references are treated as collection declarations.",
        },
        {
            "id": "directive_anchor",
            "description": "reference values that contain mediate directives are treated as engine anchor rows.",
        },
        {
            "id": "typed_leaf_candidate",
            "description": "single-pair rows with concrete magnitudes can be interpreted as typed leaves.",
        },
        {
            "id": "table_row_candidate",
            "description": "multi-pair rows in value_group>=1 are recognized as table-like entry candidates.",
        },
    ]


def recognize_row_patterns(row: dict[str, Any]) -> list[str]:
    out: list[str] = []

    try:
        value_group = int(row.get("value_group"))
    except Exception:
        value_group = -1
    pair_count = int(row.get("pair_count") or 0)
    selection_count = int(row.get("selection_count") or 0)
    reference = str(row.get("reference") or "").strip()
    magnitude = str(row.get("magnitude") or "").strip()

    if value_group == 0 and selection_count > 0:
        out.append("collection_row")
    if reference.startswith("inv;(med;"):
        out.append("directive_anchor")
    if pair_count == 1 and magnitude and not reference:
        out.append("typed_leaf_candidate")
    if value_group >= 1 and pair_count >= max(1, value_group):
        out.append("table_row_candidate")

    return out
