"""
Shared ToolSandboxSession promotion hooks for flavor workspaces.

Keeps anthology row updates and profile/config apply paths aligned across
``register_data_routes`` and tool blueprints (e.g. AGRO ERP).
"""

from __future__ import annotations

from typing import Any, Callable

from _shared.portal.data_engine.write_pipeline import apply_write_preview, write_preview_result_from_dict

from .tool_sandbox_session import ToolSandboxPromotionHooks


def build_tool_sandbox_promotion_hooks(
    *,
    workspace: Any,
    load_config_fn: Callable[[], dict[str, Any]],
    save_config_fn: Callable[[dict[str, Any]], bool],
) -> ToolSandboxPromotionHooks:
    """
    Build hooks that delegate anthology updates and staged tool config writes to the
    active data workspace + write pipeline.
    """

    def update_anthology_row(datum_id: str, row: dict[str, Any]) -> dict[str, Any]:
        if not hasattr(workspace, "update_anthology_profile"):
            return {"ok": False, "errors": ["update_anthology_profile is unavailable"], "warnings": []}
        rid = str(row.get("id") or row.get("row_id") or row.get("identifier") or datum_id).strip()
        label = str(row.get("label") or row.get("name") or "").strip()
        pairs_obj = row.get("pairs")
        if not isinstance(pairs_obj, list):
            avp = row.get("attribute_value_pairs")
            if isinstance(avp, list):
                pairs_obj = [
                    {
                        "reference": str(p.get("reference") or p.get("attribute") or "").strip(),
                        "magnitude": str(p.get("magnitude") or p.get("value") or "").strip(),
                    }
                    for p in avp
                    if isinstance(p, dict)
                ]
            else:
                pairs_obj = None
        return workspace.update_anthology_profile(row_id=rid, label=label, pairs=pairs_obj)

    def apply_tool_config_write(field_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
        preview_dict = bundle.get("write_preview") if isinstance(bundle.get("write_preview"), dict) else None
        if preview_dict is None and isinstance(bundle.get("preview"), dict):
            preview_dict = bundle["preview"]
        if not isinstance(preview_dict, dict):
            return {"ok": False, "errors": ["bundle.write_preview (WritePreviewResult dict) is required"], "warnings": []}
        obj = write_preview_result_from_dict(preview_dict)
        result = apply_write_preview(
            preview=obj,
            workspace=workspace,
            load_config_fn=load_config_fn,
            save_config_fn=save_config_fn,
        )
        return result.to_dict()

    return ToolSandboxPromotionHooks(
        update_anthology_row=update_anthology_row,
        apply_tool_config_write=apply_tool_config_write,
    )


__all__ = ["build_tool_sandbox_promotion_hooks"]
