"""
AGRO ERP MVP flows — shared sandbox/session compile + inherited preview helpers.

Routes and tools should call these instead of duplicating direct ``SandboxEngine``
compile/adapt paths. Session attachment (ephemeral state, staged config writes) is
owned by the tool blueprint or generic API; this module stays free of Flask.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from _shared.portal.data_engine.inherited_txa_adapter import (
    build_field_ref_bindings,
    select_inherited_binding_for_field,
)
from _shared.portal.data_engine.write_pipeline import preview_write_intent


def compile_agro_mvp_resource_context(
    *,
    sandbox_engine: Any,
    external_resolver: Any,
    merged_rows_by_id: Mapping[str, Any],
    local_msn_id: str,
    resource_ref: str,
) -> dict[str, Any]:
    """
    Compile / resolve / adapt a TXA or sandbox MSS resource for AGRO MVP flows.

    Mirrors the historical ``_compile_and_adapt_resource_context`` implementation.
    """
    token = str(resource_ref or "").strip()
    if token.startswith("sandbox:") or "." not in token:
        rid = token.split(":", 1)[1] if token.startswith("sandbox:") else token
        sandbox_engine.compile_isolated_mss_resource(resource_id=rid)
        token = f"sandbox:{rid}"
    inherited = sandbox_engine.compile_txa_inherited_context(
        resource_ref=token,
        local_msn_id=local_msn_id,
        external_resolver=external_resolver,
        merged_rows_by_id=merged_rows_by_id,
    )
    resolved = sandbox_engine.resolve_inherited_resource_context(
        resource_ref=token,
        local_msn_id=local_msn_id,
        external_resolver=external_resolver,
    )
    adapted = sandbox_engine.adapt_published_txa_context(
        published_resource_value=resolved.resource_value if resolved.ok and isinstance(resolved.resource_value, dict) else {},
        context_source="agro_erp.mvp.resource_select",
    )
    return {
        "resource_ref": token,
        "inherited_context": inherited,
        "resolved_context": resolved.to_dict(),
        "adapted_context": adapted,
    }


def preview_agro_mvp_inherited_field_with_msn(
    *,
    field_id: str,
    resource_ref: str,
    inherited_ref_override: str,
    local_msn_id: str,
    resource_context: Mapping[str, Any],
    load_active_config: Callable[[], dict[str, Any]],
    local_anthology_rows_payload: Mapping[str, Any],
    external_plan_fn: Callable[[dict[str, Any]], tuple[bool, dict[str, Any], str]],
) -> dict[str, Any]:
    """Build a write preview for an inherited profile field (product / invoice)."""
    inherited = resource_context.get("inherited_context") if isinstance(resource_context.get("inherited_context"), dict) else {}
    bindings = inherited.get("field_ref_bindings") if isinstance(inherited.get("field_ref_bindings"), dict) else {}
    usable = inherited.get("field_usable_refs") if isinstance(inherited.get("field_usable_refs"), list) else []
    if isinstance(bindings, dict):
        has_any = any(bool(list(bindings.get(key) or [])) for key in ("all_refs", "product_profile_refs", "invoice_log_refs"))
        if not has_any and usable:
            refs = [str(item).strip() for item in usable if str(item).strip()]
            if refs:
                bindings = build_field_ref_bindings(refs, source_msn_id=str(local_msn_id or "").strip())
    selection: dict[str, Any]
    if str(inherited_ref_override or "").strip():
        selection = {"selected_ref": str(inherited_ref_override).strip(), "selection_source": "explicit_input", "warnings": []}
    else:
        selection = select_inherited_binding_for_field(
            field_id=field_id,
            field_ref_bindings=bindings if isinstance(bindings, dict) else {},
        )
    intent = {
        "intent_type": "profile_field",
        "field_id": field_id,
        "write_mode": "stage_inherited_ref",
        "resource_ref": resource_ref,
        "local_msn_id": str(local_msn_id or "").strip(),
        "fields": {"inherited_ref": str(selection.get("selected_ref") or "").strip()},
        "inherited_context": inherited,
    }
    preview = preview_write_intent(
        intent=intent,
        current_config=load_active_config(),
        local_anthology_payload=local_anthology_rows_payload,
        external_plan_fn=external_plan_fn,
    )
    return {
        "ok": preview.ok,
        "preview": preview.to_dict(),
        "selection": selection,
        "resource_context": dict(resource_context),
        "errors": list(preview.errors),
        "warnings": list(preview.warnings) + [str(item).strip() for item in list(selection.get("warnings") or []) if str(item).strip()],
    }


AGRO_MVP_EPHEMERAL_KEY = "agro_mvp"


__all__ = [
    "AGRO_MVP_EPHEMERAL_KEY",
    "compile_agro_mvp_resource_context",
    "preview_agro_mvp_inherited_field_with_msn",
]
