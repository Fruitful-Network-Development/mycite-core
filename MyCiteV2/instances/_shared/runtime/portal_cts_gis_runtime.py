from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    CTS_GIS_TOOL_REQUEST_SCHEMA,
    CTS_GIS_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_ENTRYPOINT_ID,
    CTS_GIS_TOOL_SURFACE_ID,
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
        normalized_payload = {"schema": CTS_GIS_TOOL_REQUEST_SCHEMA, **normalized_payload}
    if _as_text(normalized_payload.get("schema")) != CTS_GIS_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {CTS_GIS_TOOL_REQUEST_SCHEMA}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    return portal_scope, normalized_payload


def _datum_summary(data_dir: str | Path | None, *, portal_instance_id: str) -> dict[str, Any]:
    if data_dir is None:
        return {
            "configured": False,
            "document_count": 0,
            "source_files": [],
            "warnings": ["data_dir_missing"],
        }
    try:
        datum_store = FilesystemSystemDatumStoreAdapter(Path(data_dir))
        catalog = datum_store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=portal_instance_id)
        )
    except Exception as exc:
        return {
            "configured": True,
            "document_count": 0,
            "source_files": [],
            "warnings": [f"datum_read_failed:{type(exc).__name__}"],
        }
    return {
        "configured": True,
        "document_count": catalog.document_count,
        "source_files": list(catalog.source_files),
        "warnings": list(catalog.warnings),
        "readiness_status": dict(catalog.readiness_status),
    }


def build_portal_cts_gis_surface_bundle(
    *,
    portal_scope: PortalScope,
    data_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=CTS_GIS_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("CTS-GIS tool surface is not registered")
    datum_summary = _datum_summary(data_dir, portal_instance_id=portal_scope.scope_id)
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    missing_integrations = [] if datum_summary.get("configured") else ["data_dir"]
    missing_capabilities = [
        capability for capability in tool_entry.required_capabilities if capability not in portal_scope.capabilities
    ]
    operational = bool(configured and enabled and not missing_integrations and not missing_capabilities)
    surface_payload = {
        "schema": CTS_GIS_TOOL_SURFACE_SCHEMA,
        "kind": "tool_status_surface",
        "tool_id": tool_entry.tool_id,
        "surface_id": CTS_GIS_TOOL_SURFACE_ID,
        "entrypoint_id": CTS_GIS_TOOL_ENTRYPOINT_ID,
        "title": "CTS-GIS",
        "subtitle": "Spatial mediation surface owned by SYSTEM.",
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
        "datum_summary": datum_summary,
        "request_contract": {
            "schema": CTS_GIS_TOOL_REQUEST_SCHEMA,
            "route": "/portal/api/v2/system/tools/cts-gis",
            "surface_id": CTS_GIS_TOOL_SURFACE_ID,
        },
    }
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_status_surface",
        "title": "CTS-GIS",
        "subtitle": "Spatial mediation surface owned by SYSTEM.",
        "visible": True,
        "surface_payload": surface_payload,
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": "CTS-GIS",
        "summary": "Capability-driven mediation posture.",
        "sections": [
            {
                "title": "Readiness",
                "rows": [
                    {
                        "label": "configured",
                        "status": "yes" if configured else "no",
                        "detail": "Configuration surface is managed under UTILITIES.",
                    },
                    {
                        "label": "enabled",
                        "status": "yes" if enabled else "no",
                        "detail": "Tool exposure is controlled independently from visibility.",
                    },
                    {
                        "label": "operational",
                        "status": "yes" if operational else "no",
                        "detail": "Operational only when data and capabilities are present.",
                    },
                ],
            }
        ],
    }
    return {
        "entrypoint_id": CTS_GIS_TOOL_ENTRYPOINT_ID,
        "read_write_posture": tool_entry.read_write_posture,
        "page_title": "CTS-GIS",
        "page_subtitle": "Spatial mediation surface owned by SYSTEM.",
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
            CTS_GIS_TOOL_SURFACE_ID,
        }:
            continue
        items.append(
            {
                "item_id": entry.surface_id,
                "label": entry.label,
                "icon_id": "cts_gis" if entry.surface_id == CTS_GIS_TOOL_SURFACE_ID else entry.root_surface_id.split(".", 1)[0],
                "href": entry.route,
                "active": entry.surface_id == CTS_GIS_TOOL_SURFACE_ID,
                "nav_kind": "surface",
                "nav_behavior": "dispatch",
                "shell_request": dispatch_bodies.get(entry.surface_id),
            }
        )
    return items


def run_portal_cts_gis(
    request_payload: dict[str, Any] | None,
    *,
    data_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, _ = _normalize_request(request_payload)
    bundle = build_portal_cts_gis_surface_bundle(
        portal_scope=portal_scope,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    composition = build_shell_composition_payload(
        active_surface_id=CTS_GIS_TOOL_SURFACE_ID,
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
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        shell_state={
            "schema": "mycite.v2.portal.shell.state.v1",
            "requested_surface_id": CTS_GIS_TOOL_SURFACE_ID,
            "active_surface_id": CTS_GIS_TOOL_SURFACE_ID,
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
    "build_portal_cts_gis_surface_bundle",
    "run_portal_cts_gis",
]
