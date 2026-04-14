from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import build_portal_aws_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import build_portal_cts_gis_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime import build_portal_fnd_ebi_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_system_workspace_bundle
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    build_allow_all_tool_exposure_policy,
    build_portal_runtime_envelope,
    build_portal_runtime_error,
    surface_schema_for_surface,
)
from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAuditLogAdapter,
    FilesystemNetworkRootReadModelAdapter,
    FilesystemSystemDatumStoreAdapter,
    is_live_aws_profile_file,
)
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.modules.cross_domain.network_root import NetworkRootReadModelService
from MyCiteV2.packages.modules.domains.publication import PublicationProfileBasicsService
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
    AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
    AWS_NARROW_WRITE_TOOL_SURFACE_ID,
    AWS_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    PORTAL_SHELL_ENTRYPOINT_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    PortalShellRequest,
    PortalShellState,
    SYSTEM_ANCHOR_FILE_KEY,
    SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
    SYSTEM_PROFILE_BASICS_FILE_KEY,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_FOCUS_FILE,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    VERB_NAVIGATE,
    activity_icon_id_for_surface,
    build_portal_activity_dispatch_bodies,
    build_portal_shell_request_payload,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
    build_shell_composition_payload,
    canonical_query_for_shell_state,
    canonicalize_portal_shell_state,
    initial_portal_shell_state,
    resolve_portal_shell_request,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_or_none(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def _default_capabilities(portal_instance_id: str) -> tuple[str, ...]:
    base = {"datum_recognition", "spatial_projection"}
    if _as_text(portal_instance_id).lower() == "fnd":
        base.update({"fnd_peripheral_routing", "hosted_site_visibility"})
    return tuple(sorted(base))


def _portal_scope_from_request(request_payload: dict[str, Any] | None, *, portal_instance_id: str) -> PortalScope:
    normalized_payload = request_payload if isinstance(request_payload, dict) else {}
    if isinstance(normalized_payload.get("portal_scope"), dict):
        raw_scope = dict(normalized_payload.get("portal_scope") or {})
        raw_scope.setdefault("scope_id", portal_instance_id)
        existing_capabilities = raw_scope.get("capabilities")
        if not isinstance(existing_capabilities, list) or not existing_capabilities:
            raw_scope["capabilities"] = list(_default_capabilities(portal_instance_id))
        return PortalScope.from_value(raw_scope)
    return PortalScope(
        scope_id=portal_instance_id,
        capabilities=_default_capabilities(portal_instance_id),
    )


def _normalize_request(request_payload: dict[str, Any] | None, *, portal_instance_id: str) -> PortalShellRequest:
    portal_scope = _portal_scope_from_request(request_payload, portal_instance_id=portal_instance_id)
    normalized_payload = dict(request_payload or {})
    normalized_payload["portal_scope"] = portal_scope.to_dict()
    if "schema" not in normalized_payload:
        normalized_payload["schema"] = "mycite.v2.portal.shell.request.v1"
    return PortalShellRequest.from_dict(normalized_payload)


def _resolved_tool_exposure_policy(tool_exposure_policy: dict[str, Any] | None) -> dict[str, Any]:
    if tool_exposure_policy is not None:
        return tool_exposure_policy
    return build_allow_all_tool_exposure_policy(
        known_tool_ids=[entry.tool_id for entry in build_portal_tool_registry_entries()]
    )


def _integration_flags(
    *,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None,
    data_dir: str | Path | None,
    webapps_root: str | Path | None,
) -> dict[str, bool]:
    return {
        "aws_status_file": bool(aws_status_file and is_live_aws_profile_file(aws_status_file)),
        "aws_csm_sandbox_status_file": bool(
            aws_csm_sandbox_status_file and is_live_aws_profile_file(aws_csm_sandbox_status_file)
        ),
        "data_dir": bool(data_dir and Path(data_dir).exists()),
        "webapps_root": bool(webapps_root and Path(webapps_root).exists()),
    }


def _tool_posture_rows(
    *,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    integration_flags: dict[str, bool],
) -> list[dict[str, Any]]:
    policy = _resolved_tool_exposure_policy(tool_exposure_policy)
    rows: list[dict[str, Any]] = []
    for entry in build_portal_tool_registry_entries():
        configured_tools = policy.get("configured_tools") if isinstance(policy.get("configured_tools"), dict) else {}
        enabled_tools = policy.get("enabled_tools") if isinstance(policy.get("enabled_tools"), dict) else {}
        configured = (
            configured_tools.get(entry.tool_id, entry.default_enabled) is True
            if isinstance(configured_tools, dict)
            else entry.default_enabled
        )
        enabled = (
            enabled_tools.get(entry.tool_id, entry.default_enabled) is True
            if isinstance(enabled_tools, dict)
            else entry.default_enabled
        )
        integration_name = {
            "aws": "aws_status_file",
            "aws_narrow_write": "aws_status_file",
            "aws_csm_onboarding": "aws_status_file",
            "aws_csm_sandbox": "aws_csm_sandbox_status_file",
            "cts_gis": "data_dir",
            "fnd_ebi": "webapps_root",
        }.get(entry.tool_id, "")
        missing_integrations = []
        if integration_name and not integration_flags.get(integration_name, False):
            missing_integrations.append(integration_name)
        missing_capabilities = [
            capability for capability in entry.required_capabilities if capability not in portal_scope.capabilities
        ]
        rows.append(
            {
                "tool_id": entry.tool_id,
                "label": entry.label,
                "route": entry.route,
                "surface_id": entry.surface_id,
                "configured": configured,
                "enabled": enabled,
                "operational": bool(configured and enabled and not missing_integrations and not missing_capabilities),
                "missing_integrations": missing_integrations,
                "required_capabilities": list(entry.required_capabilities),
                "missing_capabilities": missing_capabilities,
                "summary": entry.summary,
            }
        )
    return rows


def _activity_items(
    *,
    portal_scope: PortalScope,
    active_surface_id: str,
    shell_state: PortalShellState | None,
) -> list[dict[str, Any]]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(portal_scope=portal_scope, shell_state=shell_state)
    visible_surface_ids = [
        SYSTEM_ROOT_SURFACE_ID,
        SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
        NETWORK_ROOT_SURFACE_ID,
        UTILITIES_ROOT_SURFACE_ID,
    ]
    items: list[dict[str, Any]] = []
    for entry in build_portal_surface_catalog():
        if entry.surface_id not in visible_surface_ids:
            continue
        items.append(
            {
                "item_id": entry.surface_id,
                "label": entry.label,
                "icon_id": activity_icon_id_for_surface(entry.surface_id),
                "href": entry.route,
                "active": entry.surface_id == active_surface_id,
                "nav_kind": "surface",
                "nav_behavior": "dispatch" if entry.surface_id in dispatch_bodies else "direct",
                "shell_request": dispatch_bodies.get(entry.surface_id),
            }
        )
    return items


def _plain_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    active_surface_id: str,
    title: str,
    surface_group_title: str,
    surface_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(portal_scope=portal_scope, shell_state=shell_state)
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "plain_navigation",
        "title": title,
        "sections": [
            {
                "title": "Roots",
                "entries": [
                    {
                        "label": "System",
                        "href": "/portal/system",
                        "active": active_surface_id == SYSTEM_ROOT_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(SYSTEM_ROOT_SURFACE_ID),
                    },
                    {
                        "label": "Network",
                        "href": "/portal/network",
                        "active": active_surface_id == NETWORK_ROOT_SURFACE_ID,
                    },
                    {
                        "label": "Utilities",
                        "href": "/portal/utilities",
                        "active": active_surface_id == UTILITIES_ROOT_SURFACE_ID,
                    },
                ],
            },
            {
                "title": surface_group_title,
                "entries": surface_entries,
            },
        ],
    }


def _metric_card(label: str, value: object, *, meta: object = "") -> dict[str, str]:
    return {
        "label": _as_text(label),
        "value": _as_text(value) or "—",
        "meta": _as_text(meta),
    }


def _rows_for_tool_table(tool_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in tool_rows:
        rows.append(
            {
                "tool": row["label"],
                "configured": "yes" if row["configured"] else "no",
                "enabled": "yes" if row["enabled"] else "no",
                "operational": "yes" if row["operational"] else "no",
            }
        )
    return rows


def _surface_payload_for_operational_status(
    *,
    tool_rows: list[dict[str, Any]],
    audit_storage_file: str | Path | None,
    integration_flags: dict[str, bool],
) -> dict[str, Any]:
    operational_status = LocalAuditService(
        None if audit_storage_file is None else FilesystemAuditLogAdapter(Path(audit_storage_file))
    ).read_operational_status_summary()
    return {
        "schema": surface_schema_for_surface(SYSTEM_OPERATIONAL_STATUS_SURFACE_ID),
        "kind": "operational_status",
        "title": "Operational Status",
        "subtitle": "Plain read-model status view outside reducer ownership.",
        "cards": [
            _metric_card("audit health", operational_status.health_state),
            _metric_card("audit storage", operational_status.storage_state),
            _metric_card("recent records", operational_status.recent_record_count),
            _metric_card(
                "live integrations",
                sum(1 for value in integration_flags.values() if value),
                meta=f"{len(integration_flags)} tracked",
            ),
        ],
        "sections": [
            {
                "title": "Tool posture",
                "columns": [
                    {"key": "tool", "label": "Tool"},
                    {"key": "configured", "label": "Configured"},
                    {"key": "enabled", "label": "Enabled"},
                    {"key": "operational", "label": "Operational"},
                ],
                "items": _rows_for_tool_table(tool_rows),
            }
        ],
    }


def _surface_payload_for_network(
    *,
    portal_instance_id: str,
    portal_domain: str,
    private_dir: str | Path | None,
    audit_storage_file: str | Path | None,
) -> dict[str, Any]:
    service = NetworkRootReadModelService(
        FilesystemNetworkRootReadModelAdapter(
            private_dir=private_dir,
            local_audit_file=audit_storage_file,
        )
    )
    projection = service.read_surface(
        portal_tenant_id=portal_instance_id,
        portal_domain=portal_domain,
    )
    return {
        "schema": surface_schema_for_surface(NETWORK_ROOT_SURFACE_ID),
        "kind": "network_overview",
        "title": "Network",
        "subtitle": "Hosted, contract, alias, and relationship surfaces remain under NETWORK.",
        "cards": list(projection.get("blocks") or []),
        "notes": list(projection.get("notes") or []),
        "sections": [
            {
                "title": panel.get("title") or "Panel",
                "summary": panel.get("summary") or "",
                "metrics": list(panel.get("metrics") or []),
                "subsections": list(panel.get("sections") or []),
            }
            for panel in dict(projection.get("tab_panels") or {}).values()
        ],
    }


def _surface_payload_for_utilities_root(tool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": surface_schema_for_surface(UTILITIES_ROOT_SURFACE_ID),
        "kind": "utilities_overview",
        "title": "Utilities",
        "subtitle": "Configuration, exposure, integration, vault, peripherals, and control surfaces.",
        "cards": [
            _metric_card("tool exposure entries", len(tool_rows)),
            _metric_card("configuration owner", "utilities"),
            _metric_card("tool work pages", "system"),
        ],
        "sections": [
            {
                "title": "Utilities children",
                "rows": [
                    {"label": "Tool Exposure", "status": "available", "detail": "/portal/utilities/tool-exposure"},
                    {"label": "Integrations", "status": "available", "detail": "/portal/utilities/integrations"},
                ],
            }
        ],
    }


def _surface_payload_for_tool_exposure(tool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": surface_schema_for_surface(UTILITIES_TOOL_EXPOSURE_SURFACE_ID),
        "kind": "tool_exposure",
        "title": "Tool Exposure",
        "subtitle": "Visibility, configuration, and enablement are managed under UTILITIES.",
        "sections": [
            {
                "title": "Tool posture",
                "columns": [
                    {"key": "tool", "label": "Tool"},
                    {"key": "configured", "label": "Configured"},
                    {"key": "enabled", "label": "Enabled"},
                    {"key": "operational", "label": "Operational"},
                ],
                "items": _rows_for_tool_table(tool_rows),
            }
        ],
    }


def _surface_payload_for_integrations(integration_flags: dict[str, bool]) -> dict[str, Any]:
    return {
        "schema": surface_schema_for_surface(UTILITIES_INTEGRATIONS_SURFACE_ID),
        "kind": "integrations",
        "title": "Integrations",
        "subtitle": "Shared integration and package state for visible service tools.",
        "sections": [
            {
                "title": "Integration readiness",
                "rows": [
                    {
                        "label": key,
                        "status": "ready" if value else "missing",
                        "detail": "shared integration state",
                    }
                    for key, value in integration_flags.items()
                ],
            }
        ],
    }


def _generic_workbench(surface_payload: dict[str, Any], *, visible: bool = True) -> dict[str, Any]:
    return {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "surface_payload",
        "title": _as_text(surface_payload.get("title")) or "Surface",
        "subtitle": _as_text(surface_payload.get("subtitle")),
        "visible": visible,
        "surface_payload": surface_payload,
    }


def _generic_inspector(surface_payload: dict[str, Any]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for section in list(surface_payload.get("sections") or []):
        rows = list(section.get("rows") or [])
        if rows:
            sections.append({"title": section.get("title") or "Section", "rows": rows})
    return {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": _as_text(surface_payload.get("title")) or "Overview",
        "summary": _as_text(surface_payload.get("subtitle")),
        "sections": sections,
    }


def _tool_bundle_for_surface(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if surface_id in {
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
    }:
        return build_portal_aws_surface_bundle(
            surface_id=surface_id,
            portal_scope=portal_scope,
            shell_state=shell_state,
            aws_status_file=aws_status_file,
            aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
            data_dir=data_dir,
            tool_exposure_policy=tool_exposure_policy,
            tool_rows=tool_rows,
        )
    if surface_id == CTS_GIS_TOOL_SURFACE_ID:
        return build_portal_cts_gis_surface_bundle(
            portal_scope=portal_scope,
            shell_state=shell_state,
            data_dir=data_dir,
            tool_exposure_policy=tool_exposure_policy,
            tool_rows=tool_rows,
        )
    if surface_id == FND_EBI_TOOL_SURFACE_ID:
        return build_portal_fnd_ebi_surface_bundle(
            portal_scope=portal_scope,
            shell_state=shell_state,
            webapps_root=webapps_root,
            tool_exposure_policy=tool_exposure_policy,
            tool_rows=tool_rows,
        )
    raise ValueError(f"Unsupported tool surface: {surface_id}")


def _bundle_for_surface(
    *,
    selection_surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    private_dir: str | Path | None,
    audit_storage_file: str | Path | None,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    integration_flags = _integration_flags(
        aws_status_file=aws_status_file,
        aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
        data_dir=data_dir,
        webapps_root=webapps_root,
    )
    tool_rows = _tool_posture_rows(
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
        integration_flags=integration_flags,
    )
    if selection_surface_id == SYSTEM_ROOT_SURFACE_ID:
        canonical_state = canonicalize_portal_shell_state(
            shell_state,
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=portal_scope,
            seed_anchor_file=shell_state is None,
        )
        workspace_bundle = build_system_workspace_bundle(
            portal_scope=portal_scope,
            portal_domain=portal_domain,
            shell_state=canonical_state,
            data_dir=data_dir,
            public_dir=public_dir,
            audit_storage_file=audit_storage_file,
            tool_rows=tool_rows,
        )
        workspace_bundle["entrypoint_id"] = PORTAL_SHELL_ENTRYPOINT_ID
        workspace_bundle["read_write_posture"] = "read-only"
        workspace_bundle["tool_rows"] = tool_rows
        return workspace_bundle
    if selection_surface_id in {
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
    }:
        canonical_state = canonicalize_portal_shell_state(
            shell_state,
            active_surface_id=selection_surface_id,
            portal_scope=portal_scope,
            seed_anchor_file=shell_state is None,
        )
        bundle = _tool_bundle_for_surface(
            surface_id=selection_surface_id,
            portal_scope=portal_scope,
            shell_state=canonical_state,
            data_dir=data_dir,
            aws_status_file=aws_status_file,
            aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
            webapps_root=webapps_root,
            tool_exposure_policy=tool_exposure_policy,
            tool_rows=tool_rows,
        )
        bundle["tool_rows"] = tool_rows
        return bundle
    if selection_surface_id == SYSTEM_OPERATIONAL_STATUS_SURFACE_ID:
        surface_payload = _surface_payload_for_operational_status(
            tool_rows=tool_rows,
            audit_storage_file=audit_storage_file,
            integration_flags=integration_flags,
        )
        return {
            "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "page_title": "Operational Status",
            "page_subtitle": "Plain read-model status view outside reducer ownership.",
            "surface_payload": surface_payload,
            "control_panel": _plain_control_panel(
                portal_scope=portal_scope,
                shell_state=shell_state,
                active_surface_id=selection_surface_id,
                title="System Views",
                surface_group_title="System",
                surface_entries=[
                    {
                        "label": "System Workspace",
                        "href": "/portal/system",
                        "shell_request": build_portal_shell_request_payload(
                            requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
                            portal_scope=portal_scope,
                            shell_state=shell_state,
                            transition={"kind": TRANSITION_FOCUS_FILE, "file_key": SYSTEM_ANCHOR_FILE_KEY},
                        ),
                    }
                ],
            ),
            "workbench": _generic_workbench(surface_payload),
            "inspector": _generic_inspector(surface_payload),
            "tool_rows": tool_rows,
        }
    if selection_surface_id == NETWORK_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_network(
            portal_instance_id=portal_scope.scope_id,
            portal_domain=portal_domain,
            private_dir=private_dir,
            audit_storage_file=audit_storage_file,
        )
        return {
            "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "page_title": "Network",
            "page_subtitle": "Hosted, contract, alias, and relationship surfaces.",
            "surface_payload": surface_payload,
            "control_panel": _plain_control_panel(
                portal_scope=portal_scope,
                shell_state=shell_state,
                active_surface_id=selection_surface_id,
                title="Network",
                surface_group_title="Adjacent roots",
                surface_entries=[
                    {"label": "Operational Status", "href": "/portal/system/operational-status"},
                    {"label": "Tool Exposure", "href": "/portal/utilities/tool-exposure"},
                ],
            ),
            "workbench": _generic_workbench(surface_payload),
            "inspector": _generic_inspector(surface_payload),
            "tool_rows": tool_rows,
        }
    if selection_surface_id == UTILITIES_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_utilities_root(tool_rows)
        return {
            "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "page_title": "Utilities",
            "page_subtitle": "Configuration and control surfaces.",
            "surface_payload": surface_payload,
            "control_panel": _plain_control_panel(
                portal_scope=portal_scope,
                shell_state=shell_state,
                active_surface_id=selection_surface_id,
                title="Utilities",
                surface_group_title="Utilities children",
                surface_entries=[
                    {"label": "Tool Exposure", "href": "/portal/utilities/tool-exposure"},
                    {"label": "Integrations", "href": "/portal/utilities/integrations"},
                ],
            ),
            "workbench": _generic_workbench(surface_payload),
            "inspector": _generic_inspector(surface_payload),
            "tool_rows": tool_rows,
        }
    if selection_surface_id == UTILITIES_TOOL_EXPOSURE_SURFACE_ID:
        surface_payload = _surface_payload_for_tool_exposure(tool_rows)
    else:
        surface_payload = _surface_payload_for_integrations(integration_flags)
    return {
        "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": _as_text(surface_payload.get("title")) or "Utilities",
        "page_subtitle": _as_text(surface_payload.get("subtitle")),
        "surface_payload": surface_payload,
        "control_panel": _plain_control_panel(
            portal_scope=portal_scope,
            shell_state=shell_state,
            active_surface_id=selection_surface_id,
            title="Utilities",
            surface_group_title="Utilities children",
            surface_entries=[
                {"label": "Tool Exposure", "href": "/portal/utilities/tool-exposure", "active": selection_surface_id == UTILITIES_TOOL_EXPOSURE_SURFACE_ID},
                {"label": "Integrations", "href": "/portal/utilities/integrations", "active": selection_surface_id == UTILITIES_INTEGRATIONS_SURFACE_ID},
            ],
        ),
        "workbench": _generic_workbench(surface_payload),
        "inspector": _generic_inspector(surface_payload),
        "tool_rows": tool_rows,
    }


def run_portal_shell_entry(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None = None,
    public_dir: str | Path | None = None,
    private_dir: str | Path | None = None,
    audit_storage_file: str | Path | None = None,
    aws_status_file: str | Path | None = None,
    aws_csm_sandbox_status_file: str | Path | None = None,
    webapps_root: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_request = _normalize_request(request_payload, portal_instance_id=portal_instance_id)
    selection = resolve_portal_shell_request(normalized_request)
    portal_scope = normalized_request.portal_scope
    bundle = _bundle_for_surface(
        selection_surface_id=selection.active_surface_id,
        portal_scope=portal_scope,
        shell_state=selection.shell_state,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
        private_dir=private_dir,
        audit_storage_file=audit_storage_file,
        aws_status_file=aws_status_file,
        aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
        webapps_root=webapps_root,
        tool_exposure_policy=tool_exposure_policy,
    )
    composition = build_shell_composition_payload(
        active_surface_id=selection.active_surface_id,
        portal_instance_id=portal_scope.scope_id,
        page_title=bundle["page_title"],
        page_subtitle=bundle["page_subtitle"],
        activity_items=_activity_items(
            portal_scope=portal_scope,
            active_surface_id=selection.active_surface_id,
            shell_state=selection.shell_state,
        ),
        control_panel=bundle["control_panel"],
        workbench=bundle["workbench"],
        inspector=bundle["inspector"],
        shell_state=selection.shell_state,
        control_panel_collapsed=bool(
            selection.shell_state.chrome.control_panel_collapsed if selection.shell_state is not None else False
        ),
    )
    error = None
    if not selection.allowed:
        error = build_portal_runtime_error(
            code=selection.reason_code or "surface_unknown",
            message=selection.reason_message or "Requested surface is not available.",
        )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=selection.requested_surface_id,
        surface_id=selection.active_surface_id,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=selection.reducer_owned,
        canonical_route=selection.canonical_route,
        canonical_query=selection.canonical_query,
        canonical_url=selection.canonical_url,
        shell_state=None if selection.shell_state is None else selection.shell_state.to_dict(),
        surface_payload=bundle["surface_payload"],
        shell_composition=composition,
        warnings=[],
        error=error,
    )


def run_system_profile_basics_action(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    audit_storage_file: str | Path | None = None,
) -> dict[str, Any]:
    payload = dict(request_payload or {})
    if _as_text(payload.get("schema")) != SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA}")
    if data_dir is None:
        raise ValueError("data_dir is required for profile basics updates")
    adapter = FilesystemSystemDatumStoreAdapter(Path(data_dir), public_dir=public_dir)
    outcome = PublicationProfileBasicsService(adapter).apply_write(
        {
            "tenant_id": portal_instance_id,
            "tenant_domain": portal_domain,
            "profile_title": payload.get("profile_title") or "",
            "profile_summary": payload.get("profile_summary") or "",
            "contact_email": payload.get("contact_email") or "",
            "public_website_url": payload.get("public_website_url") or "",
        }
    )
    if audit_storage_file is not None:
        try:
            LocalAuditService(FilesystemAuditLogAdapter(Path(audit_storage_file))).append_record(
                outcome.to_local_audit_payload()
            )
        except Exception:
            pass
    portal_scope = _portal_scope_from_request(payload, portal_instance_id=portal_instance_id)
    incoming_state = payload.get("shell_state")
    shell_state = (
        PortalShellState.from_value(incoming_state, portal_scope=portal_scope, fallback_surface_id=SYSTEM_ROOT_SURFACE_ID)
        if incoming_state is not None
        else None
    )
    if shell_state is None:
        shell_state = initial_portal_shell_state(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=portal_scope,
        )
    shell_state = canonicalize_portal_shell_state(
        shell_state,
        active_surface_id=SYSTEM_ROOT_SURFACE_ID,
        portal_scope=portal_scope,
        seed_anchor_file=False,
    )
    selection = resolve_portal_shell_request(
        {
            "schema": "mycite.v2.portal.shell.request.v1",
            "requested_surface_id": SYSTEM_ROOT_SURFACE_ID,
            "portal_scope": portal_scope.to_dict(),
            "shell_state": shell_state.to_dict(),
            "transition": {"kind": TRANSITION_FOCUS_FILE, "file_key": SYSTEM_PROFILE_BASICS_FILE_KEY},
        }
    )
    integration_flags = _integration_flags(
        aws_status_file=None,
        aws_csm_sandbox_status_file=None,
        data_dir=data_dir,
        webapps_root=None,
    )
    tool_rows = _tool_posture_rows(
        portal_scope=portal_scope,
        tool_exposure_policy=None,
        integration_flags=integration_flags,
    )
    workspace_bundle = build_system_workspace_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=selection.shell_state,
        data_dir=data_dir,
        public_dir=public_dir,
        audit_storage_file=audit_storage_file,
        tool_rows=tool_rows,
        profile_save_status="saved",
    )
    workspace_bundle["surface_payload"]["workspace"]["profile_basics"]["confirmed_summary"] = outcome.confirmed_summary.to_dict()
    composition = build_shell_composition_payload(
        active_surface_id=SYSTEM_ROOT_SURFACE_ID,
        portal_instance_id=portal_scope.scope_id,
        page_title=workspace_bundle["page_title"],
        page_subtitle=workspace_bundle["page_subtitle"],
        activity_items=_activity_items(
            portal_scope=portal_scope,
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            shell_state=selection.shell_state,
        ),
        control_panel=workspace_bundle["control_panel"],
        workbench=workspace_bundle["workbench"],
        inspector=workspace_bundle["inspector"],
        shell_state=selection.shell_state,
    )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
        surface_id=SYSTEM_ROOT_SURFACE_ID,
        entrypoint_id=PORTAL_SHELL_ENTRYPOINT_ID,
        read_write_posture="write",
        reducer_owned=True,
        canonical_route=selection.canonical_route,
        canonical_query=canonical_query_for_shell_state(selection.shell_state, surface_id=SYSTEM_ROOT_SURFACE_ID),
        canonical_url=selection.canonical_url,
        shell_state=selection.shell_state.to_dict(),
        surface_payload=workspace_bundle["surface_payload"],
        shell_composition=composition,
        warnings=[],
        error=None,
    )


__all__ = [
    "PORTAL_RUNTIME_ENVELOPE_SCHEMA",
    "run_portal_shell_entry",
    "run_system_profile_basics_action",
]
