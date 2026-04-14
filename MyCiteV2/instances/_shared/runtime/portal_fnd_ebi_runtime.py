from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    FND_EBI_TOOL_REQUEST_SCHEMA,
    FND_EBI_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    FND_EBI_TOOL_ENTRYPOINT_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    build_portal_activity_dispatch_bodies,
    build_portal_surface_catalog,
    build_shell_composition_payload,
    resolve_portal_tool_registry_entry,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_request(payload: dict[str, Any] | None) -> tuple[PortalScope, dict[str, Any]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    if normalized_payload.get("schema") in {None, ""}:
        normalized_payload = {"schema": FND_EBI_TOOL_REQUEST_SCHEMA, **normalized_payload}
    if _as_text(normalized_payload.get("schema")) != FND_EBI_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {FND_EBI_TOOL_REQUEST_SCHEMA}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    return portal_scope, normalized_payload


def _webapps_summary(webapps_root: str | Path | None) -> dict[str, Any]:
    if webapps_root is None:
        return {
            "configured": False,
            "present": False,
            "root": "",
        }
    resolved = Path(webapps_root)
    return {
        "configured": True,
        "present": resolved.exists() and resolved.is_dir(),
        "root": str(resolved),
        "entry_count": len(list(resolved.iterdir())) if resolved.exists() and resolved.is_dir() else 0,
    }


def build_portal_fnd_ebi_surface_bundle(
    *,
    portal_scope: PortalScope,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=FND_EBI_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("FND-EBI tool surface is not registered")
    webapps_summary = _webapps_summary(webapps_root)
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    missing_integrations = [] if webapps_summary.get("present") else ["webapps_root"]
    missing_capabilities = [
        capability for capability in tool_entry.required_capabilities if capability not in portal_scope.capabilities
    ]
    operational = bool(configured and enabled and not missing_integrations and not missing_capabilities)
    surface_payload = {
        "schema": FND_EBI_TOOL_SURFACE_SCHEMA,
        "kind": "tool_status_surface",
        "tool_id": tool_entry.tool_id,
        "surface_id": FND_EBI_TOOL_SURFACE_ID,
        "entrypoint_id": FND_EBI_TOOL_ENTRYPOINT_ID,
        "title": "FND-EBI",
        "subtitle": "Hosted visibility surface routed through shared infrastructure.",
        "tool": {
            "tool_id": tool_entry.tool_id,
            "label": tool_entry.label,
            "summary": tool_entry.summary,
            "configured": configured,
            "enabled": enabled,
            "operational": operational,
            "missing_integrations": missing_integrations,
            "required_capabilities": list(tool_entry.required_capabilities),
            "missing_capabilities": missing_capabilities,
        },
        "webapps_summary": webapps_summary,
        "request_contract": {
            "schema": FND_EBI_TOOL_REQUEST_SCHEMA,
            "route": "/portal/api/v2/system/tools/fnd-ebi",
            "surface_id": FND_EBI_TOOL_SURFACE_ID,
        },
    }
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_status_surface",
        "title": "FND-EBI",
        "subtitle": "Hosted visibility surface routed through shared infrastructure.",
        "visible": True,
        "surface_payload": surface_payload,
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": "FND-EBI",
        "summary": "Shared hosted visibility posture.",
        "sections": [
            {
                "title": "Prerequisites",
                "rows": [
                    {
                        "label": "webapps_root",
                        "status": "present" if webapps_summary.get("present") else "missing",
                        "detail": "Hosted site metadata is read from the shared webapps root.",
                    },
                    {
                        "label": "fnd_peripheral_routing",
                        "status": "available" if "fnd_peripheral_routing" in portal_scope.capabilities else "missing",
                        "detail": "FND routing capability is required for operational task handoff.",
                    },
                ],
            }
        ],
    }
    return {
        "entrypoint_id": FND_EBI_TOOL_ENTRYPOINT_ID,
        "read_write_posture": tool_entry.read_write_posture,
        "page_title": "FND-EBI",
        "page_subtitle": "Hosted visibility surface routed through shared infrastructure.",
        "surface_payload": surface_payload,
        "workbench": workbench,
        "inspector": inspector,
    }


def _tool_activity_items(portal_instance_id: str) -> list[dict[str, Any]]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(portal_instance_id=portal_instance_id)
    items: list[dict[str, Any]] = []
    for entry in build_portal_surface_catalog():
        if entry.surface_id not in {
            SYSTEM_ROOT_SURFACE_ID,
            NETWORK_ROOT_SURFACE_ID,
            UTILITIES_ROOT_SURFACE_ID,
            FND_EBI_TOOL_SURFACE_ID,
        }:
            continue
        items.append(
            {
                "item_id": entry.surface_id,
                "label": entry.label,
                "icon_id": "fnd_ebi" if entry.surface_id == FND_EBI_TOOL_SURFACE_ID else entry.root_surface_id.split(".", 1)[0],
                "href": entry.route,
                "active": entry.surface_id == FND_EBI_TOOL_SURFACE_ID,
                "nav_kind": "surface",
                "nav_behavior": "dispatch",
                "shell_request": dispatch_bodies.get(entry.surface_id),
            }
        )
    return items


def run_portal_fnd_ebi(
    request_payload: dict[str, Any] | None,
    *,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, _ = _normalize_request(request_payload)
    bundle = build_portal_fnd_ebi_surface_bundle(
        portal_scope=portal_scope,
        webapps_root=webapps_root,
        tool_exposure_policy=tool_exposure_policy,
    )
    composition = build_shell_composition_payload(
        active_surface_id=FND_EBI_TOOL_SURFACE_ID,
        portal_instance_id=portal_scope.scope_id,
        page_title=bundle["page_title"],
        page_subtitle=bundle["page_subtitle"],
        activity_items=_tool_activity_items(portal_scope.scope_id),
        control_panel={
            "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
            "kind": "system_control_panel",
            "title": "System Surfaces",
            "sections": [],
        },
        workbench=bundle["workbench"],
        inspector=bundle["inspector"],
    )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=FND_EBI_TOOL_SURFACE_ID,
        surface_id=FND_EBI_TOOL_SURFACE_ID,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        shell_state={
            "schema": "mycite.v2.portal.shell.state.v1",
            "requested_surface_id": FND_EBI_TOOL_SURFACE_ID,
            "active_surface_id": FND_EBI_TOOL_SURFACE_ID,
            "selection_status": "available",
            "allowed": True,
            "reason_code": "",
            "reason_message": "",
        },
        surface_payload=bundle["surface_payload"],
        shell_composition=composition,
        warnings=[],
        error=None,
    )


__all__ = [
    "build_portal_fnd_ebi_surface_bundle",
    "run_portal_fnd_ebi",
]
