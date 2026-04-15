from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_tool_control_panel
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    FND_EBI_TOOL_REQUEST_SCHEMA,
    FND_EBI_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    FND_EBI_TOOL_ENTRYPOINT_ID,
    FND_EBI_TOOL_ROUTE,
    FND_EBI_TOOL_SURFACE_ID,
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
        normalized_payload = {"schema": FND_EBI_TOOL_REQUEST_SCHEMA, **normalized_payload}
    if _as_text(normalized_payload.get("schema")) != FND_EBI_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {FND_EBI_TOOL_REQUEST_SCHEMA}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    shell_state = canonicalize_portal_shell_state(
        normalized_payload.get("shell_state"),
        active_surface_id=FND_EBI_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        seed_anchor_file=normalized_payload.get("shell_state") is None,
    )
    return portal_scope, shell_state, normalized_payload


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
    shell_state: PortalShellState,
    webapps_root: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    tool_rows: list[dict[str, Any]] | None = None,
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
        "kind": "tool_mediation_surface",
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
        "focus_subject": dict(shell_state.focus_subject or {}),
        "mediation_subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "request_contract": {
            "schema": FND_EBI_TOOL_REQUEST_SCHEMA,
            "route": FND_EBI_TOOL_ROUTE,
            "surface_id": FND_EBI_TOOL_SURFACE_ID,
        },
    }
    control_panel = build_tool_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=None,
        public_dir=None,
        private_dir=private_dir,
        surface_id=FND_EBI_TOOL_SURFACE_ID,
        active_document=None,
        selected_datum=None,
        selected_object=None,
        tool_rows=list(tool_rows or []),
        title="FND-EBI",
    )
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_secondary_evidence",
        "title": "FND-EBI Evidence",
        "subtitle": "Workbench remains hidden until the runtime requests supporting evidence.",
        "visible": False,
        "surface_payload": {
            "kind": "tool_secondary_evidence",
            "surface_id": FND_EBI_TOOL_SURFACE_ID,
            "webapps_summary": webapps_summary,
        },
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "tool_mediation_panel",
        "title": "FND-EBI",
        "summary": "Shared hosted visibility posture.",
        "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "sections": [
            {
                "title": "Prerequisites",
                "rows": [
                    {
                        "label": "webapps_root",
                        "value": "present" if webapps_summary.get("present") else "missing",
                        "detail": "Hosted site metadata is read from the shared webapps root.",
                    },
                    {
                        "label": "fnd_peripheral_routing",
                        "value": "available" if "fnd_peripheral_routing" in portal_scope.capabilities else "missing",
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
        "control_panel": control_panel,
        "workbench": workbench,
        "inspector": inspector,
        "shell_state": shell_state,
        "route": FND_EBI_TOOL_ROUTE,
    }


def run_portal_fnd_ebi(
    request_payload: dict[str, Any] | None,
    *,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, shell_state, _ = _normalize_request(request_payload)
    bundle = build_portal_fnd_ebi_surface_bundle(
        portal_scope=portal_scope,
        shell_state=shell_state,
        webapps_root=webapps_root,
        tool_exposure_policy=tool_exposure_policy,
    )
    canonical_query = canonical_query_for_shell_state(shell_state, surface_id=FND_EBI_TOOL_SURFACE_ID)
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=FND_EBI_TOOL_SURFACE_ID,
        surface_id=FND_EBI_TOOL_SURFACE_ID,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=True,
        canonical_route=bundle["route"],
        canonical_query=canonical_query,
        canonical_url=build_canonical_url(surface_id=FND_EBI_TOOL_SURFACE_ID, query=canonical_query),
        shell_state=shell_state.to_dict(),
        surface_payload=bundle["surface_payload"],
        shell_composition={},
        warnings=[],
        error=None,
    )


__all__ = [
    "build_portal_fnd_ebi_surface_bundle",
    "run_portal_fnd_ebi",
]
