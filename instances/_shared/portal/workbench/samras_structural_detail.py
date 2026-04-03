"""
Generic SAMRAS structural detail view-model (right-rail / burst tree), not TXA-specific.

Built from ``branch_context`` produced by :mod:`_shared.portal.sandbox.txa_sandbox_workspace`.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _level(label: str, items: Sequence[Mapping[str, Any]] | None, *, key: str) -> dict[str, Any]:
    rows = [dict(x) for x in list(items or []) if isinstance(x, dict)]
    return {"label": label, "key": key, "items": rows, "count": len(rows)}


def build_samras_structural_detail_vm(
    branch_context: Mapping[str, Any] | None,
    *,
    normalized_staged_entries: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Hierarchical / burst-friendly structural detail for the SAMRAS workspace sidebar.

    ``branch_context`` is expected to include keys like ``path_to_root``, ``siblings``,
    ``children``, ``next_child_preview``, ``parent_address``, ``selected_address_id``.
    """
    bc = dict(branch_context or {})
    staged = [dict(x) for x in list(normalized_staged_entries or []) if isinstance(x, dict)]

    path = [str(p).strip() for p in list(bc.get("path_to_root") or []) if str(p).strip()]
    levels: list[dict[str, Any]] = []
    if path:
        levels.append(
            _level(
                "Path to root",
                [{"address_id": seg, "title": "", "is_selected": seg == str(bc.get("selected_address_id") or "").strip()} for seg in path],
                key="path",
            )
        )
    levels.append(_level("Siblings", list(bc.get("siblings") or []), key="siblings"))
    levels.append(_level("Children", list(bc.get("children") or []), key="children"))

    next_preview = str(bc.get("next_child_preview") or "").strip()
    staged_preview = [
        {
            "parent_address": str(s.get("parent_address") or "").strip(),
            "provisional_child_address": str(s.get("provisional_child_address") or "").strip(),
            "title": str(s.get("title") or "").strip(),
        }
        for s in staged
    ]

    return {
        "schema": "mycite.portal.samras.structural_detail.v1",
        "selected_address_id": str(bc.get("selected_address_id") or "").strip(),
        "parent_address": str(bc.get("parent_address") or "").strip(),
        "path_to_root": path,
        "next_child_preview": next_preview,
        "levels": levels,
        "staged_structural_preview": staged_preview,
        "child_count": int(bc.get("child_count") or 0),
        "sibling_index": bc.get("sibling_index"),
    }


__all__ = ["build_samras_structural_detail_vm"]
