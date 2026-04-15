from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_tool_control_panel
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
    CTS_GIS_TOOL_ROUTE,
    CTS_GIS_TOOL_SURFACE_ID,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    PortalShellState,
    build_canonical_url,
    canonical_query_for_shell_state,
    canonicalize_portal_shell_state,
    resolve_portal_tool_registry_entry,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_request(payload: dict[str, Any] | None) -> tuple[PortalScope, PortalShellState, dict[str, Any]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    if normalized_payload.get("schema") in {None, ""}:
        normalized_payload = {"schema": CTS_GIS_TOOL_REQUEST_SCHEMA, **normalized_payload}
    if _as_text(normalized_payload.get("schema")) != CTS_GIS_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {CTS_GIS_TOOL_REQUEST_SCHEMA}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    shell_state = canonicalize_portal_shell_state(
        normalized_payload.get("shell_state"),
        active_surface_id=CTS_GIS_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        seed_anchor_file=normalized_payload.get("shell_state") is None,
    )
    return portal_scope, shell_state, normalized_payload


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
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    tool_rows: list[dict[str, Any]] | None = None,
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
        "kind": "tool_mediation_surface",
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
        "focus_subject": dict(shell_state.focus_subject or {}),
        "mediation_subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "request_contract": {
            "schema": CTS_GIS_TOOL_REQUEST_SCHEMA,
            "route": CTS_GIS_TOOL_ROUTE,
            "surface_id": CTS_GIS_TOOL_SURFACE_ID,
        },
    }
    control_panel = build_tool_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=data_dir,
        public_dir=None,
        private_dir=private_dir,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        active_document=None,
        selected_datum=None,
        selected_object=None,
        tool_rows=list(tool_rows or []),
        title="CTS-GIS",
    )
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_secondary_evidence",
        "title": "CTS-GIS Evidence",
        "subtitle": "Workbench remains hidden until the runtime requests secondary evidence.",
        "visible": False,
        "surface_payload": {
            "kind": "tool_secondary_evidence",
            "surface_id": CTS_GIS_TOOL_SURFACE_ID,
            "datum_summary": datum_summary,
        },
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "tool_mediation_panel",
        "title": "CTS-GIS",
        "summary": "Capability-driven mediation posture.",
        "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "sections": [
            {
                "title": "Readiness",
                "rows": [
                    {
                        "label": "configured",
                        "value": "yes" if configured else "no",
                        "detail": "Configuration surface is managed under UTILITIES.",
                    },
                    {
                        "label": "enabled",
                        "value": "yes" if enabled else "no",
                        "detail": "Tool exposure is controlled independently from visibility.",
                    },
                    {
                        "label": "operational",
                        "value": "yes" if operational else "no",
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
        "control_panel": control_panel,
        "workbench": workbench,
        "inspector": inspector,
        "shell_state": shell_state,
        "route": CTS_GIS_TOOL_ROUTE,
    }


def run_portal_cts_gis(
    request_payload: dict[str, Any] | None,
    *,
    data_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, shell_state, _ = _normalize_request(request_payload)
    bundle = build_portal_cts_gis_surface_bundle(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    canonical_query = canonical_query_for_shell_state(shell_state, surface_id=CTS_GIS_TOOL_SURFACE_ID)
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=True,
        canonical_route=bundle["route"],
        canonical_query=canonical_query,
        canonical_url=build_canonical_url(surface_id=CTS_GIS_TOOL_SURFACE_ID, query=canonical_query),
        shell_state=shell_state.to_dict(),
        surface_payload=bundle["surface_payload"],
        shell_composition={},
        warnings=[],
        error=None,
    )


__all__ = [
    "build_portal_cts_gis_surface_bundle",
    "run_portal_cts_gis",
]
