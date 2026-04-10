"""
Group anthology table rows into layer / value-group bands for workbench UIs.

Consumes the payload shape returned by ``Workspace.anthology_table_view()``:
``table``, ``layers`` (with ``value_groups`` and ``rows``), ``rows``, ``warnings``.
"""

from __future__ import annotations

from typing import Any


def build_grouped_workbench_bundle(table_view: dict[str, Any] | None) -> dict[str, Any]:
    """
    Build a stable, JSON-serializable grouped layout bundle for Data Tool / portals.

    This does not replace anthology row grammar; it reshapes the same rows for
    grouped/clustered presentation (family = layer + value group).
    """
    tv = table_view if isinstance(table_view, dict) else {}
    table = tv.get("table") if isinstance(tv.get("table"), dict) else {}
    layers_in = list(tv.get("layers") or [])
    flat_rows = list(tv.get("rows") or [])
    warnings = list(tv.get("warnings") or [])

    bands: list[dict[str, Any]] = []
    for layer_block in layers_in:
        if not isinstance(layer_block, dict):
            continue
        layer_val = layer_block.get("layer")
        vgs = list(layer_block.get("value_groups") or [])
        group_payloads: list[dict[str, Any]] = []
        for vg_block in vgs:
            if not isinstance(vg_block, dict):
                continue
            vg_val = vg_block.get("value_group")
            rows = [dict(r) for r in list(vg_block.get("rows") or []) if isinstance(r, dict)]
            identifiers = [str(r.get("identifier") or "").strip() for r in rows if str(r.get("identifier") or "").strip()]
            group_payloads.append(
                {
                    "value_group": vg_val,
                    "row_count": int(vg_block.get("row_count") or len(rows)),
                    "identifiers": identifiers,
                    "rows": rows,
                    "family_key": f"L{layer_val}::VG{vg_val}",
                }
            )
        bands.append(
            {
                "layer": layer_val,
                "row_count": int(layer_block.get("row_count") or sum(g.get("row_count") or 0 for g in group_payloads)),
                "value_groups": group_payloads,
            }
        )

    return {
        "schema": "mycite.portal.workbench.grouped_bundle.v1",
        "table": dict(table),
        "bands": bands,
        "row_count": len(flat_rows),
        "warnings": warnings,
    }


__all__ = ["build_grouped_workbench_bundle"]
