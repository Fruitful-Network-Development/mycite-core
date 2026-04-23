from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import build_portal_aws_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import build_portal_cts_gis_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_fnd_dcm_runtime import build_portal_fnd_dcm_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime import build_portal_fnd_ebi_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_system_workspace_bundle
from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import build_portal_workbench_ui_surface_bundle
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    attach_region_family_contract,
    build_allow_all_tool_exposure_policy,
    build_portal_runtime_envelope,
    build_portal_runtime_error,
    surface_schema_for_surface,
)
from MyCiteV2.packages.adapters.filesystem import (
    FilesystemNetworkRootReadModelAdapter,
)
from MyCiteV2.packages.adapters.sql import (
    SqliteAuditLogAdapter,
    SqlitePortalAuthorityAdapter,
    SqliteSystemDatumStoreAdapter,
)
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.modules.cross_domain.network_root import NetworkRootReadModelService
from MyCiteV2.packages.modules.domains.publication import PublicationProfileBasicsService
from MyCiteV2.packages.ports.portal_authority import PortalAuthorityRequest
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_DCM_TOOL_SURFACE_ID,
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
    SYSTEM_PROFILE_BASICS_FILE_KEY,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_FOCUS_FILE,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    VERB_NAVIGATE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    activity_icon_id_for_surface,
    build_canonical_url,
    build_portal_activity_dispatch_bodies,
    build_portal_shell_request_payload,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
    build_shell_composition_payload,
    canonical_query_for_shell_state,
    canonicalize_portal_shell_state,
    initial_portal_shell_state,
    resolve_portal_shell_request,
    SYSTEM_SURFACE_IDS,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_or_none(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def _normalize_authority_mode(value: object) -> str:
    del value
    return "sql_primary"


def _portal_authority_source(
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None,
) -> Any | None:
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return None
    known_tool_ids = tuple(entry.tool_id for entry in build_portal_tool_registry_entries())
    result = SqlitePortalAuthorityAdapter(authority_path).read_portal_authority(
        PortalAuthorityRequest(scope_id=portal_instance_id, known_tool_ids=known_tool_ids)
    )
    return result.source


def _portal_scope_from_request(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> PortalScope:
    del authority_mode, tool_exposure_policy
    normalized_payload = request_payload if isinstance(request_payload, dict) else {}
    if isinstance(normalized_payload.get("portal_scope"), dict):
        raw_scope = dict(normalized_payload.get("portal_scope") or {})
        raw_scope.setdefault("scope_id", portal_instance_id)
        existing_capabilities = raw_scope.get("capabilities")
        if not isinstance(existing_capabilities, list) or not existing_capabilities:
            authority_source = _portal_authority_source(
                portal_instance_id=portal_instance_id,
                authority_db_file=authority_db_file,
            )
            raw_scope["capabilities"] = list(authority_source.capabilities) if authority_source is not None else []
        return PortalScope.from_value(raw_scope)
    authority_source = _portal_authority_source(
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
    )
    if authority_source is not None:
        return PortalScope(
            scope_id=authority_source.scope_id,
            capabilities=authority_source.capabilities,
        )
    return PortalScope(scope_id=portal_instance_id, capabilities=())


def _normalize_request(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> PortalShellRequest:
    portal_scope = _portal_scope_from_request(
        request_payload,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
        tool_exposure_policy=tool_exposure_policy,
    )
    normalized_payload = dict(request_payload or {})
    normalized_payload["portal_scope"] = portal_scope.to_dict()
    if "schema" not in normalized_payload:
        normalized_payload["schema"] = "mycite.v2.portal.shell.request.v1"
    return PortalShellRequest.from_dict(normalized_payload)


def _resolved_tool_exposure_policy(
    tool_exposure_policy: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    del authority_mode
    authority_source = _portal_authority_source(
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
    )
    if authority_source is not None and isinstance(authority_source.tool_exposure_policy, dict):
        return dict(authority_source.tool_exposure_policy)
    if tool_exposure_policy is not None:
        return tool_exposure_policy
    return build_allow_all_tool_exposure_policy(known_tool_ids=[entry.tool_id for entry in build_portal_tool_registry_entries()])


def _sql_runtime_error_for_surface(
    *,
    surface_id: str,
    portal_instance_id: str,
    authority_db_file: str | Path | None,
) -> dict[str, str] | None:
    if surface_id not in SYSTEM_SURFACE_IDS:
        return None
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return build_portal_runtime_error(
            code="sql_authority_required",
            message="The MOS SQL authority database is required for SYSTEM surfaces.",
        )
    authority_source = _portal_authority_source(
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_path,
    )
    if authority_source is None:
        return build_portal_runtime_error(
            code="sql_portal_authority_missing",
            message="The MOS SQL authority database is missing the portal authority snapshot for this scope.",
        )
    if surface_id in {SYSTEM_ROOT_SURFACE_ID, WORKBENCH_UI_TOOL_SURFACE_ID}:
        datum_store = SqliteSystemDatumStoreAdapter(authority_path)
        if not datum_store.has_authoritative_catalog(portal_instance_id) or not datum_store.has_system_workbench(portal_instance_id):
            return build_portal_runtime_error(
                code="sql_authority_uninitialized",
                message="The MOS SQL authority database is not initialized for the requested tenant.",
            )
    return None


def _integration_flags(
    *,
    data_dir: str | Path | None,
    webapps_root: str | Path | None,
) -> dict[str, bool]:
    return {
        "data_dir": bool(data_dir and Path(data_dir).exists()),
        "webapps_root": bool(webapps_root and Path(webapps_root).exists()),
    }


def _tool_posture_rows(
    *,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    integration_flags: dict[str, bool],
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> list[dict[str, Any]]:
    policy = _resolved_tool_exposure_policy(
        tool_exposure_policy,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
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
            "cts_gis": "data_dir",
            "fnd_dcm": "webapps_root",
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
        AWS_CSM_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_DCM_TOOL_SURFACE_ID,
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


def _utilities_surface_label(surface_id: str) -> str:
    if surface_id == UTILITIES_TOOL_EXPOSURE_SURFACE_ID:
        return "Tool Exposure"
    if surface_id == UTILITIES_INTEGRATIONS_SURFACE_ID:
        return "Integrations"
    return "Overview"


def _utilities_control_panel(
    *,
    active_surface_id: str,
) -> dict[str, Any]:
    entries = [
        {
            "label": "Tool Exposure",
            "href": "/portal/utilities/tool-exposure",
            "active": active_surface_id == UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
        },
        {
            "label": "Integrations",
            "href": "/portal/utilities/integrations",
            "active": active_surface_id == UTILITIES_INTEGRATIONS_SURFACE_ID,
        },
    ]
    if active_surface_id == UTILITIES_ROOT_SURFACE_ID:
        entries[0]["active"] = False
        entries[1]["active"] = False
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "UTILITIES",
        "context_items": [
            {"label": "Root", "value": "UTILITIES"},
            {"label": "Section", "value": _utilities_surface_label(active_surface_id)},
        ],
        "verb_tabs": [],
        "groups": [
            {
                "title": "Sections",
                "entries": entries,
            }
        ],
        "actions": [],
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


def _surface_payload_for_network(
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    audit_storage_file: str | Path | None,
    surface_query: dict[str, str] | None,
) -> dict[str, Any]:
    service = NetworkRootReadModelService(
        FilesystemNetworkRootReadModelAdapter(
            data_dir=data_dir,
            private_dir=private_dir,
            local_audit_file=audit_storage_file,
        )
    )
    projection = service.read_surface(
        portal_tenant_id=portal_instance_id,
        portal_domain=portal_domain,
        surface_query=surface_query,
    )
    projection["schema"] = surface_schema_for_surface(NETWORK_ROOT_SURFACE_ID)
    return projection


def _network_entry(
    *,
    label: str,
    href: str,
    active: bool = False,
    meta: object = "",
    shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "label": label,
        "href": href,
        "active": active,
    }
    meta_text = _as_text(meta)
    if meta_text:
        entry["meta"] = meta_text
    if shell_request is not None:
        entry["shell_request"] = shell_request
    return entry


def _network_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    active_surface_id: str,
    surface_payload: dict[str, Any],
) -> dict[str, Any]:
    workspace = dict(surface_payload.get("workspace") or {})
    active_filters = dict(workspace.get("active_filters") or {})
    event_type_filters = list(workspace.get("event_type_filters") or [])
    contract_filters = list(workspace.get("contract_filters") or [])
    system_log_request = build_portal_shell_request_payload(
        requested_surface_id=NETWORK_ROOT_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_query={"view": "system_logs"},
    )
    event_entries = []
    for row in event_type_filters:
        event_type_id = _as_text(row.get("event_type_id"))
        event_entries.append(
            _network_entry(
                label=_as_text(row.get("label") or event_type_id) or "Event Type",
                href=f"/portal/network?view=system_logs&type={event_type_id}",
                active=bool(row.get("active")),
                meta=f"{int(row.get('count') or 0)} row(s)",
                shell_request=build_portal_shell_request_payload(
                    requested_surface_id=NETWORK_ROOT_SURFACE_ID,
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    surface_query={"view": "system_logs", "type": event_type_id},
                ),
            )
        )
    contract_entries = []
    for row in contract_filters:
        contract_id = _as_text(row.get("contract_id"))
        contract_entries.append(
            _network_entry(
                label=contract_id or "Contract",
                href=f"/portal/network?view=system_logs&contract={contract_id}",
                active=bool(row.get("active")),
                meta=f"{_as_text(row.get('relationship_kind')) or 'contract'} · {int(row.get('count') or 0)} row(s)",
                shell_request=build_portal_shell_request_payload(
                    requested_surface_id=NETWORK_ROOT_SURFACE_ID,
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    surface_query={"view": "system_logs", "contract": contract_id},
                ),
            )
        )
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "NETWORK",
        "context_items": [
            {"label": "Root", "value": "NETWORK"},
            {"label": "View", "value": "system_logs"},
            {"label": "Contract", "value": _as_text(active_filters.get("contract_id")) or "all"},
            {"label": "Type", "value": _as_text(active_filters.get("event_type_id")) or "all"},
        ],
        "verb_tabs": [],
        "groups": [
            {
                "title": "Views",
                "entries": [
                    _network_entry(
                        label="System Logs",
                        href="/portal/network?view=system_logs",
                        active=not _as_text(active_filters.get("contract_id")) and not _as_text(active_filters.get("event_type_id")),
                        meta="canonical workbench",
                        shell_request=system_log_request,
                    )
                ],
            },
            {
                "title": "Contracts",
                "entries": contract_entries,
            },
            {
                "title": "Event Types",
                "entries": event_entries,
            },
        ],
        "actions": [],
    }


def _network_workbench(surface_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "network_system_log_workbench",
        "title": _as_text(surface_payload.get("title")) or "Network",
        "subtitle": _as_text(surface_payload.get("subtitle")),
        "visible": True,
        "surface_payload": surface_payload,
    }


def _network_inspector(surface_payload: dict[str, Any]) -> dict[str, Any]:
    workspace = dict(surface_payload.get("workspace") or {})
    selected_record = workspace.get("selected_record")
    subject = None
    if isinstance(selected_record, dict) and _as_text(selected_record.get("datum_address")):
        subject = {"level": "record", "id": _as_text(selected_record.get("datum_address"))}
    return {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "network_system_log_inspector",
        "title": "Log Record",
        "summary": "Read-only log-record inspector.",
        "visible": subject is not None,
        "subject": subject,
        "surface_payload": surface_payload,
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


ToolSurfaceBundleBuilder = Callable[..., dict[str, Any]]


def _build_aws_tool_bundle(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    surface_query: dict[str, str] | None,
    private_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    **_: Any,
) -> dict[str, Any]:
    return build_portal_aws_surface_bundle(
        surface_id=surface_id,
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_query=surface_query,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
    )


def _build_cts_gis_tool_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    request_payload: dict[str, Any] | None,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
    **_: Any,
) -> dict[str, Any]:
    if shell_state is None:
        raise ValueError("CTS-GIS shell bundle requires reducer-owned shell_state")
    return build_portal_cts_gis_surface_bundle(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=data_dir,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
        tool_rows=tool_rows,
        request_payload=request_payload,
    )


def _build_fnd_dcm_tool_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    surface_query: dict[str, str] | None,
    webapps_root: str | Path | None,
    private_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    **_: Any,
) -> dict[str, Any]:
    return build_portal_fnd_dcm_surface_bundle(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_query=surface_query,
        webapps_root=webapps_root,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
    )


def _build_fnd_ebi_tool_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    webapps_root: str | Path | None,
    private_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
    **_: Any,
) -> dict[str, Any]:
    if shell_state is None:
        raise ValueError("FND-EBI shell bundle requires reducer-owned shell_state")
    return build_portal_fnd_ebi_surface_bundle(
        portal_scope=portal_scope,
        shell_state=shell_state,
        webapps_root=webapps_root,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
        tool_rows=tool_rows,
    )


def _build_workbench_ui_tool_bundle(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    shell_state: PortalShellState | None,
    authority_db_file: str | Path | None,
    tool_rows: list[dict[str, Any]],
    surface_query: dict[str, str] | None,
    **_: Any,
) -> dict[str, Any]:
    return build_portal_workbench_ui_surface_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=shell_state,
        authority_db_file=authority_db_file,
        tool_rows=tool_rows,
        surface_query=surface_query,
    )


_TOOL_SURFACE_BUNDLE_BUILDERS: dict[str, ToolSurfaceBundleBuilder] = {
    AWS_CSM_TOOL_SURFACE_ID: _build_aws_tool_bundle,
    CTS_GIS_TOOL_SURFACE_ID: _build_cts_gis_tool_bundle,
    FND_DCM_TOOL_SURFACE_ID: _build_fnd_dcm_tool_bundle,
    FND_EBI_TOOL_SURFACE_ID: _build_fnd_ebi_tool_bundle,
    WORKBENCH_UI_TOOL_SURFACE_ID: _build_workbench_ui_tool_bundle,
}

_RUNTIME_OWNED_TOOL_SURFACE_IDS = frozenset(
    {
        AWS_CSM_TOOL_SURFACE_ID,
        FND_DCM_TOOL_SURFACE_ID,
        WORKBENCH_UI_TOOL_SURFACE_ID,
    }
)


def _tool_shell_state(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
) -> PortalShellState | None:
    if surface_id in _RUNTIME_OWNED_TOOL_SURFACE_IDS:
        return None
    return canonicalize_portal_shell_state(
        shell_state,
        active_surface_id=surface_id,
        portal_scope=portal_scope,
        seed_anchor_file=shell_state is None,
    )


def _tool_bundle_for_surface(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    request_payload: dict[str, Any] | None,
    surface_query: dict[str, str] | None,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
    portal_domain: str,
    authority_db_file: str | Path | None,
) -> dict[str, Any]:
    builder = _TOOL_SURFACE_BUNDLE_BUILDERS.get(surface_id)
    if builder is None:
        raise ValueError(f"Unsupported tool surface: {surface_id}")
    return builder(
        surface_id=surface_id,
        portal_scope=portal_scope,
        shell_state=shell_state,
        request_payload=request_payload,
        surface_query=surface_query,
        data_dir=data_dir,
        private_dir=private_dir,
        webapps_root=webapps_root,
        tool_exposure_policy=tool_exposure_policy,
        tool_rows=tool_rows,
        portal_domain=portal_domain,
        authority_db_file=authority_db_file,
    )


def _bundle_for_surface(
    *,
    selection_surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    request_payload: dict[str, Any] | None,
    surface_query: dict[str, str] | None,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    private_dir: str | Path | None,
    audit_storage_file: str | Path | None,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    integration_flags = _integration_flags(
        data_dir=data_dir,
        webapps_root=webapps_root,
    )
    tool_rows = _tool_posture_rows(
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
        integration_flags=integration_flags,
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
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
            authority_db_file=authority_db_file,
            authority_mode=authority_mode,
        )
        workspace_bundle["entrypoint_id"] = PORTAL_SHELL_ENTRYPOINT_ID
        workspace_bundle["read_write_posture"] = "read-only"
        workspace_bundle["tool_rows"] = tool_rows
        return workspace_bundle
    if selection_surface_id in _TOOL_SURFACE_BUNDLE_BUILDERS:
        bundle = _tool_bundle_for_surface(
            surface_id=selection_surface_id,
            portal_scope=portal_scope,
            shell_state=_tool_shell_state(
                surface_id=selection_surface_id,
                portal_scope=portal_scope,
                shell_state=shell_state,
            ),
            request_payload=request_payload,
            surface_query=surface_query,
            data_dir=data_dir,
            private_dir=private_dir,
            webapps_root=webapps_root,
            tool_exposure_policy=tool_exposure_policy,
            tool_rows=tool_rows,
            portal_domain=portal_domain,
            authority_db_file=authority_db_file,
        )
        bundle["tool_rows"] = tool_rows
        return bundle
    if selection_surface_id == NETWORK_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_network(
            portal_instance_id=portal_scope.scope_id,
            portal_domain=portal_domain,
            data_dir=data_dir,
            private_dir=private_dir,
            audit_storage_file=audit_storage_file,
            surface_query=surface_query,
        )
        return {
            "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "page_title": "Network",
            "page_subtitle": "Portal-instance system-log workbench.",
            "surface_payload": surface_payload,
            "control_panel": attach_region_family_contract(
                _network_control_panel(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    active_surface_id=selection_surface_id,
                    surface_payload=surface_payload,
                ),
                family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
                surface_id=selection_surface_id,
            ),
            "workbench": attach_region_family_contract(
                _network_workbench(surface_payload),
                family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
                surface_id=selection_surface_id,
            ),
            "inspector": attach_region_family_contract(
                _network_inspector(surface_payload),
                family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
                surface_id=selection_surface_id,
            ),
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
            "control_panel": attach_region_family_contract(
                _utilities_control_panel(
                    active_surface_id=selection_surface_id,
                ),
                family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
                surface_id=selection_surface_id,
            ),
            "workbench": attach_region_family_contract(
                _generic_workbench(surface_payload),
                family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
                surface_id=selection_surface_id,
            ),
            "inspector": attach_region_family_contract(
                _generic_inspector(surface_payload),
                family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
                surface_id=selection_surface_id,
            ),
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
        "control_panel": attach_region_family_contract(
            _utilities_control_panel(
                active_surface_id=selection_surface_id,
            ),
            family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
            surface_id=selection_surface_id,
        ),
        "workbench": attach_region_family_contract(
            _generic_workbench(surface_payload),
            family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
            surface_id=selection_surface_id,
        ),
        "inspector": attach_region_family_contract(
            _generic_inspector(surface_payload),
            family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
            surface_id=selection_surface_id,
        ),
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
    webapps_root: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    normalized_request = _normalize_request(
        request_payload,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
        tool_exposure_policy=tool_exposure_policy,
    )
    selection = resolve_portal_shell_request(normalized_request)
    portal_scope = normalized_request.portal_scope
    bundle = _bundle_for_surface(
        selection_surface_id=selection.active_surface_id,
        portal_scope=portal_scope,
        shell_state=selection.shell_state,
        request_payload=request_payload,
        surface_query=normalized_request.surface_query,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
        private_dir=private_dir,
        audit_storage_file=audit_storage_file,
        webapps_root=webapps_root,
        tool_exposure_policy=tool_exposure_policy,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    canonical_route = _as_text(bundle.get("canonical_route")) or selection.canonical_route
    canonical_query = dict(bundle.get("canonical_query") or selection.canonical_query)
    canonical_url = _as_text(bundle.get("canonical_url")) or build_canonical_url(
        surface_id=selection.active_surface_id,
        query=canonical_query,
    )
    composition_shell_state = selection.shell_state if selection.reducer_owned else None
    composition = build_shell_composition_payload(
        active_surface_id=selection.active_surface_id,
        portal_instance_id=portal_scope.scope_id,
        page_title=bundle["page_title"],
        page_subtitle=bundle["page_subtitle"],
        activity_items=_activity_items(
            portal_scope=portal_scope,
            active_surface_id=selection.active_surface_id,
            shell_state=composition_shell_state,
        ),
        control_panel=bundle["control_panel"],
        workbench=bundle["workbench"],
        inspector=bundle["inspector"],
        shell_state=composition_shell_state,
        control_panel_collapsed=bool(
            composition_shell_state.chrome.control_panel_collapsed if composition_shell_state is not None else False
        ),
    )
    error = None
    if not selection.allowed:
        error = build_portal_runtime_error(
            code=selection.reason_code or "surface_unknown",
            message=selection.reason_message or "Requested surface is not available.",
        )
    elif selection.active_surface_id in SYSTEM_SURFACE_IDS:
        error = _sql_runtime_error_for_surface(
            surface_id=selection.active_surface_id,
            portal_instance_id=portal_scope.scope_id,
            authority_db_file=authority_db_file,
        )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=selection.requested_surface_id,
        surface_id=selection.active_surface_id,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=selection.reducer_owned,
        canonical_route=canonical_route,
        canonical_query=canonical_query,
        canonical_url=canonical_url,
        shell_state=None if composition_shell_state is None else composition_shell_state.to_dict(),
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
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    payload = dict(request_payload or {})
    if _as_text(payload.get("schema")) != SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA}")
    _normalize_authority_mode(authority_mode)
    portal_scope = _portal_scope_from_request(
        payload,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
        tool_exposure_policy=None,
    )
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
    preexisting_error = _sql_runtime_error_for_surface(
        surface_id=SYSTEM_ROOT_SURFACE_ID,
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
    )
    authority_path = _path_or_none(authority_db_file)
    if preexisting_error is None and authority_path is not None:
        adapter = SqliteSystemDatumStoreAdapter(authority_path)
        if not adapter.has_publication_summary(portal_instance_id, portal_domain):
            preexisting_error = build_portal_runtime_error(
                code="sql_publication_summary_missing",
                message="The MOS SQL authority database is missing the publication summary required for profile updates.",
            )
    outcome = None
    if preexisting_error is None and authority_path is not None:
        adapter = SqliteSystemDatumStoreAdapter(authority_path)
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
        try:
            LocalAuditService(SqliteAuditLogAdapter(authority_path)).append_record(outcome.to_local_audit_payload())
        except Exception:
            pass
    integration_flags = _integration_flags(
        data_dir=data_dir,
        webapps_root=None,
    )
    tool_rows = _tool_posture_rows(
        portal_scope=portal_scope,
        tool_exposure_policy=None,
        integration_flags=integration_flags,
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    workspace_bundle = build_system_workspace_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=selection.shell_state,
        data_dir=data_dir,
        public_dir=public_dir,
        audit_storage_file=audit_storage_file,
        tool_rows=tool_rows,
        profile_save_status="saved" if outcome is not None else "",
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    if outcome is not None:
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
        error=preexisting_error,
    )


__all__ = [
    "PORTAL_RUNTIME_ENVELOPE_SCHEMA",
    "run_portal_shell_entry",
    "run_system_profile_basics_action",
]
