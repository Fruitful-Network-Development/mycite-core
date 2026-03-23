"""
Promote staged SAMRAS title-tree entries into a sandbox resource via :class:`SandboxEngine`.

Uses existing structure compile/save paths — no ad-hoc second persistence model.
"""

from __future__ import annotations

from typing import Any

from _shared.portal.samras import load_workspace_from_resource_body, mutate_resource_body

from .engine import SandboxEngine
from .models import SandboxStageResult
from .samras import decode_resource_rows
from .txa_sandbox_workspace import normalize_staged_entries


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def promote_staged_samras_title_entries(
    engine: SandboxEngine,
    resource_id: str,
    *,
    staged_entries: list[dict[str, Any]],
) -> SandboxStageResult:
    """
    Merge normalized staged title rows into the resource and persist.

    - If a ``structure_payload`` / ``canonical_magnitude`` / ``legacy_structure_payload_input``
      is present, uses :meth:`SandboxEngine.create_or_update_samras_resource` so structure
      and titles stay aligned.
    - Otherwise merges into ``rows_by_address`` and saves the payload (rows-only resources).
    """
    rid = _as_text(resource_id)
    if not rid:
        return SandboxStageResult(
            ok=False,
            resource_type="samras_resource",
            resource_id="",
            staged_payload={},
            warnings=[],
            errors=["resource_id is required"],
        )

    base = engine.get_resource(rid)
    if bool(base.get("missing")):
        return SandboxStageResult(
            ok=False,
            resource_type="samras_resource",
            resource_id=rid,
            staged_payload={},
            warnings=[],
            errors=[f"resource not found: {rid}"],
        )

    try:
        workspace = load_workspace_from_resource_body(base if isinstance(base, dict) else {})
        persisted_rows = [{"address_id": item.address_id, "title": item.title} for item in workspace.nodes]
    except Exception:
        persisted_rows = decode_resource_rows(base if isinstance(base, dict) else {})
    normalized, stage_warnings = normalize_staged_entries(persisted_rows, staged_entries)
    if not normalized:
        return SandboxStageResult(
            ok=False,
            resource_type=_as_text(base.get("kind")) or "resource",
            resource_id=rid,
            staged_payload=dict(base),
            warnings=list(stage_warnings),
            errors=["no promotable staged entries (see warnings)"],
        )

    try:
        updated = dict(base)
        for st in normalized:
            updated, _workspace, _mutation = mutate_resource_body(
                updated,
                action="samras_add_child",
                parent_address=_as_text(st.get("parent_address")),
                title=_as_text(st.get("title")),
            )
        saved = engine.save_resource(rid, updated)
        merged_warnings = list(stage_warnings) + list(saved.warnings)
        return SandboxStageResult(
            ok=saved.ok,
            resource_type=saved.resource_type,
            resource_id=saved.resource_id,
            staged_payload=dict(saved.staged_payload),
            warnings=merged_warnings,
            errors=list(saved.errors),
        )
    except Exception:
        pass

    merged = dict(base.get("rows_by_address") if isinstance(base.get("rows_by_address"), dict) else {})
    for st in normalized:
        prov = _as_text(st.get("provisional_child_address"))
        title = _as_text(st.get("title"))
        if prov:
            merged[prov] = [title]
    out = dict(base)
    out["rows_by_address"] = merged
    saved = engine.save_resource(rid, out)
    merged_warnings = list(stage_warnings) + list(saved.warnings)
    return SandboxStageResult(
        ok=saved.ok,
        resource_type=saved.resource_type,
        resource_id=saved.resource_id,
        staged_payload=dict(saved.staged_payload),
        warnings=merged_warnings,
        errors=list(saved.errors),
    )


__all__ = ["promote_staged_samras_title_entries"]
