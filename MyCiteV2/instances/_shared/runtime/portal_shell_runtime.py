from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import build_portal_aws_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import build_portal_cts_gis_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime import build_portal_fnd_ebi_surface_bundle
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    build_portal_runtime_envelope,
    build_portal_runtime_error,
    build_allow_all_tool_exposure_policy,
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
from MyCiteV2.packages.modules.domains.publication import (
    PublicationProfileBasicsService,
    PublicationTenantSummary,
    PublicationTenantSummaryService,
)
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
    SYSTEM_ACTIVITY_SURFACE_ID,
    SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
    SYSTEM_PROFILE_BASICS_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    activity_icon_id_for_surface,
    apply_surface_posture_to_composition,
    build_portal_activity_dispatch_bodies,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
    build_shell_composition_payload,
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
        raw_scope.setdefault("capabilities", list(_default_capabilities(portal_instance_id)))
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


def _tool_posture_map(
    *,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    integration_flags: dict[str, bool],
) -> dict[str, dict[str, Any]]:
    return {
        row["surface_id"]: row
        for row in _tool_posture_rows(
            portal_scope=portal_scope,
            tool_exposure_policy=tool_exposure_policy,
            integration_flags=integration_flags,
        )
    }


def _activity_items(
    *,
    portal_instance_id: str,
    active_surface_id: str,
) -> list[dict[str, Any]]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(portal_instance_id=portal_instance_id)
    items: list[dict[str, Any]] = []
    visible_surface_ids = [
        SYSTEM_ROOT_SURFACE_ID,
        SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
        SYSTEM_ACTIVITY_SURFACE_ID,
        SYSTEM_PROFILE_BASICS_SURFACE_ID,
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
        NETWORK_ROOT_SURFACE_ID,
        UTILITIES_ROOT_SURFACE_ID,
    ]
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
                "nav_behavior": "dispatch",
                "shell_request": dispatch_bodies.get(entry.surface_id),
            }
        )
    return items


def _control_panel(
    *,
    portal_instance_id: str,
    active_surface_id: str,
    tool_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(portal_instance_id=portal_instance_id)
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "surface_navigation",
        "title": "Portal Surfaces",
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
                        "shell_request": dispatch_bodies.get(NETWORK_ROOT_SURFACE_ID),
                    },
                    {
                        "label": "Utilities",
                        "href": "/portal/utilities",
                        "active": active_surface_id == UTILITIES_ROOT_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(UTILITIES_ROOT_SURFACE_ID),
                    },
                ],
            },
            {
                "title": "System Surfaces",
                "entries": [
                    {
                        "label": "Operational Status",
                        "href": "/portal/system/operational-status",
                        "active": active_surface_id == SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(SYSTEM_OPERATIONAL_STATUS_SURFACE_ID),
                    },
                    {
                        "label": "Recent Activity",
                        "href": "/portal/system/activity",
                        "active": active_surface_id == SYSTEM_ACTIVITY_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(SYSTEM_ACTIVITY_SURFACE_ID),
                    },
                    {
                        "label": "Profile Basics",
                        "href": "/portal/system/profile-basics",
                        "active": active_surface_id == SYSTEM_PROFILE_BASICS_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(SYSTEM_PROFILE_BASICS_SURFACE_ID),
                    },
                ],
            },
            {
                "title": "Service Tools",
                "entries": [
                    {
                        "label": row["label"],
                        "href": row["route"],
                        "active": active_surface_id == row["surface_id"],
                        "meta": (
                            "operational"
                            if row["operational"]
                            else "visible, non-operational"
                        ),
                        "shell_request": dispatch_bodies.get(row["surface_id"]),
                    }
                    for row in tool_rows
                ],
            },
            {
                "title": "Utilities",
                "entries": [
                    {
                        "label": "Tool Exposure",
                        "href": "/portal/utilities/tool-exposure",
                        "active": active_surface_id == UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(UTILITIES_TOOL_EXPOSURE_SURFACE_ID),
                    },
                    {
                        "label": "Integrations",
                        "href": "/portal/utilities/integrations",
                        "active": active_surface_id == UTILITIES_INTEGRATIONS_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(UTILITIES_INTEGRATIONS_SURFACE_ID),
                    },
                ],
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


def _surface_payload_for_system_root(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    tool_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    operational_count = sum(1 for row in tool_rows if row["operational"])
    return {
        "schema": surface_schema_for_surface(SYSTEM_ROOT_SURFACE_ID),
        "kind": "system_overview",
        "title": "System",
        "subtitle": "Shared landing surface for shell-owned work pages.",
        "cards": [
            _metric_card("portal instance", portal_scope.scope_id),
            _metric_card("domain", portal_domain),
            _metric_card("visible tools", len(tool_rows)),
            _metric_card("operational tools", operational_count),
        ],
        "sections": [
            {
                "title": "System child surfaces",
                "rows": [
                    {
                        "label": "Operational Status",
                        "status": "available",
                        "detail": "/portal/system/operational-status",
                    },
                    {
                        "label": "Recent Activity",
                        "status": "available",
                        "detail": "/portal/system/activity",
                    },
                    {
                        "label": "Profile Basics",
                        "status": "available",
                        "detail": "/portal/system/profile-basics",
                    },
                ],
            },
            {
                "title": "Tool posture",
                "columns": [
                    {"key": "tool", "label": "Tool"},
                    {"key": "configured", "label": "Configured"},
                    {"key": "enabled", "label": "Enabled"},
                    {"key": "operational", "label": "Operational"},
                ],
                "items": _rows_for_tool_table(tool_rows),
            },
        ],
    }


def _audit_service(audit_storage_file: str | Path | None) -> LocalAuditService:
    if audit_storage_file is None:
        return LocalAuditService(None)
    return LocalAuditService(FilesystemAuditLogAdapter(Path(audit_storage_file)))


def _surface_payload_for_operational_status(
    *,
    tool_rows: list[dict[str, Any]],
    audit_storage_file: str | Path | None,
    integration_flags: dict[str, bool],
) -> dict[str, Any]:
    operational_status = _audit_service(audit_storage_file).read_operational_status_summary()
    return {
        "schema": surface_schema_for_surface(SYSTEM_OPERATIONAL_STATUS_SURFACE_ID),
        "kind": "operational_status",
        "title": "Operational Status",
        "subtitle": "Readiness snapshot for the shared shell and visible tools.",
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


def _surface_payload_for_activity(audit_storage_file: str | Path | None) -> dict[str, Any]:
    activity = _audit_service(audit_storage_file).read_recent_activity_projection()
    return {
        "schema": surface_schema_for_surface(SYSTEM_ACTIVITY_SURFACE_ID),
        "kind": "activity_feed",
        "title": "Recent Activity",
        "subtitle": "Recent local audit evidence for shell and tool activity.",
        "cards": [
            _metric_card("activity state", activity.activity_state),
            _metric_card("records", activity.recent_record_count),
        ],
        "sections": [
            {
                "title": "Recent records",
                "columns": [
                    {"key": "timestamp", "label": "Timestamp"},
                    {"key": "event_type", "label": "Event"},
                    {"key": "shell_verb", "label": "Verb"},
                    {"key": "focus_subject", "label": "Focus"},
                ],
                "items": [
                    {
                        "timestamp": str(record.recorded_at_unix_ms),
                        "event_type": record.event_type,
                        "shell_verb": record.shell_verb,
                        "focus_subject": record.focus_subject,
                    }
                    for record in activity.records
                ],
            }
        ],
    }


def _publication_services(
    *,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
) -> tuple[PublicationTenantSummaryService, PublicationProfileBasicsService] | None:
    if data_dir is None:
        return None
    adapter = FilesystemSystemDatumStoreAdapter(Path(data_dir), public_dir=public_dir)
    return PublicationTenantSummaryService(adapter), PublicationProfileBasicsService(adapter)


def _profile_summary(
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
) -> PublicationTenantSummary:
    services = _publication_services(data_dir=data_dir, public_dir=public_dir)
    if services is None:
        return PublicationTenantSummary.fallback(
            tenant_id=portal_instance_id,
            tenant_domain=portal_domain,
            warnings=("data_dir_not_configured",),
        )
    summary_service, _ = services
    summary = summary_service.read_summary(portal_instance_id, portal_domain)
    if summary is None:
        return PublicationTenantSummary.fallback(
            tenant_id=portal_instance_id,
            tenant_domain=portal_domain,
            warnings=("publication_profile_not_found",),
        )
    return summary


def _surface_payload_for_profile_basics(
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    save_status: str = "",
) -> dict[str, Any]:
    summary = _profile_summary(
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
    )
    return {
        "schema": surface_schema_for_surface(SYSTEM_PROFILE_BASICS_SURFACE_ID),
        "kind": "profile_basics",
        "title": "Profile Basics",
        "subtitle": "Publication summary rehomed as a SYSTEM child surface.",
        "cards": [
            _metric_card("profile title", summary.profile_title),
            _metric_card("entity type", summary.entity_type or "—"),
            _metric_card("profile resolution", summary.profile_resolution),
            _metric_card("publication mode", summary.publication_mode),
        ],
        "sections": [
            {
                "title": "Contact",
                "rows": [
                    {"label": "contact email", "status": "set" if summary.contact_email else "empty", "detail": summary.contact_email or "—"},
                    {"label": "public website", "status": "set" if summary.public_website_url else "empty", "detail": summary.public_website_url or "—"},
                ],
            }
        ],
        "form": {
            "title": "Edit profile basics",
            "action_label": "Save profile basics",
            "action_route": "/portal/api/v2/system/profile-basics",
            "schema": SYSTEM_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
            "status": save_status,
            "fields": [
                {"field_id": "profile_title", "label": "Profile title", "type": "text", "value": summary.profile_title},
                {"field_id": "profile_summary", "label": "Profile summary", "type": "textarea", "value": summary.profile_summary},
                {"field_id": "contact_email", "label": "Contact email", "type": "email", "value": summary.contact_email},
                {"field_id": "public_website_url", "label": "Public website", "type": "url", "value": summary.public_website_url},
            ],
        },
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
        "subtitle": "Configuration, exposure, and integration control surfaces only.",
        "cards": [
            _metric_card("tool exposure entries", len(tool_rows)),
            _metric_card("configuration owner", "utilities"),
            _metric_card("work pages", "system"),
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


def _inspector_for_surface(surface_payload: dict[str, Any]) -> dict[str, Any]:
    inspector_sections: list[dict[str, Any]] = []
    for section in list(surface_payload.get("sections") or []):
        rows = list(section.get("rows") or [])
        if rows:
            inspector_sections.append({"title": section.get("title") or "Section", "rows": rows})
    return {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": _as_text(surface_payload.get("title")) or "Overview",
        "summary": _as_text(surface_payload.get("subtitle")),
        "sections": inspector_sections,
    }


def _workbench_for_surface(surface_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "surface_payload",
        "title": _as_text(surface_payload.get("title")) or "Surface",
        "subtitle": _as_text(surface_payload.get("subtitle")),
        "visible": True,
        "surface_payload": surface_payload,
    }


def _tool_bundle_for_surface(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None,
    data_dir: str | Path | None,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
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
            aws_status_file=aws_status_file,
            aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
            tool_exposure_policy=tool_exposure_policy,
        )
    if surface_id == CTS_GIS_TOOL_SURFACE_ID:
        return build_portal_cts_gis_surface_bundle(
            portal_scope=portal_scope,
            data_dir=data_dir,
            tool_exposure_policy=tool_exposure_policy,
        )
    if surface_id == FND_EBI_TOOL_SURFACE_ID:
        return build_portal_fnd_ebi_surface_bundle(
            portal_scope=portal_scope,
            webapps_root=webapps_root,
            tool_exposure_policy=tool_exposure_policy,
        )
    raise ValueError(f"Unsupported tool surface: {surface_id}")


def _bundle_for_surface(
    *,
    active_surface_id: str,
    portal_scope: PortalScope,
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
    if active_surface_id in {
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
    }:
        bundle = _tool_bundle_for_surface(
            surface_id=active_surface_id,
            portal_scope=portal_scope,
            aws_status_file=aws_status_file,
            aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
            data_dir=data_dir,
            webapps_root=webapps_root,
            tool_exposure_policy=tool_exposure_policy,
        )
        bundle["tool_rows"] = tool_rows
        return bundle
    if active_surface_id == SYSTEM_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_system_root(
            portal_scope=portal_scope,
            portal_domain=portal_domain,
            tool_rows=tool_rows,
        )
    elif active_surface_id == SYSTEM_OPERATIONAL_STATUS_SURFACE_ID:
        surface_payload = _surface_payload_for_operational_status(
            tool_rows=tool_rows,
            audit_storage_file=audit_storage_file,
            integration_flags=integration_flags,
        )
    elif active_surface_id == SYSTEM_ACTIVITY_SURFACE_ID:
        surface_payload = _surface_payload_for_activity(audit_storage_file)
    elif active_surface_id == SYSTEM_PROFILE_BASICS_SURFACE_ID:
        surface_payload = _surface_payload_for_profile_basics(
            portal_instance_id=portal_scope.scope_id,
            portal_domain=portal_domain,
            data_dir=data_dir,
            public_dir=public_dir,
        )
    elif active_surface_id == NETWORK_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_network(
            portal_instance_id=portal_scope.scope_id,
            portal_domain=portal_domain,
            private_dir=private_dir,
            audit_storage_file=audit_storage_file,
        )
    elif active_surface_id == UTILITIES_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_utilities_root(tool_rows)
    elif active_surface_id == UTILITIES_TOOL_EXPOSURE_SURFACE_ID:
        surface_payload = _surface_payload_for_tool_exposure(tool_rows)
    elif active_surface_id == UTILITIES_INTEGRATIONS_SURFACE_ID:
        surface_payload = _surface_payload_for_integrations(integration_flags)
    else:
        surface_payload = _surface_payload_for_system_root(
            portal_scope=portal_scope,
            portal_domain=portal_domain,
            tool_rows=tool_rows,
        )
        active_surface_id = SYSTEM_ROOT_SURFACE_ID

    return {
        "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
        "read_write_posture": "write" if active_surface_id == SYSTEM_PROFILE_BASICS_SURFACE_ID else "read-only",
        "page_title": _as_text(surface_payload.get("title")) or "MyCite",
        "page_subtitle": _as_text(surface_payload.get("subtitle")),
        "surface_payload": surface_payload,
        "workbench": _workbench_for_surface(surface_payload),
        "inspector": _inspector_for_surface(surface_payload),
        "tool_rows": tool_rows,
    }


def _apply_shell_chrome(composition: dict[str, Any], request: PortalShellRequest) -> None:
    chrome = request.shell_chrome
    if chrome.control_panel_collapsed is not None:
        composition["control_panel_collapsed"] = chrome.control_panel_collapsed
    if chrome.inspector_collapsed is not None:
        composition["inspector_collapsed"] = chrome.inspector_collapsed
        apply_surface_posture_to_composition(composition)


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
        active_surface_id=selection.active_surface_id,
        portal_scope=portal_scope,
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
            portal_instance_id=portal_scope.scope_id,
            active_surface_id=selection.active_surface_id,
        ),
        control_panel=_control_panel(
            portal_instance_id=portal_scope.scope_id,
            active_surface_id=selection.active_surface_id,
            tool_rows=bundle["tool_rows"],
        ),
        workbench=bundle["workbench"],
        inspector=bundle["inspector"],
    )
    _apply_shell_chrome(composition, normalized_request)
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
        shell_state=selection.to_dict(),
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
    if _as_text(payload.get("schema")) != SYSTEM_PROFILE_BASICS_ACTION_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {SYSTEM_PROFILE_BASICS_ACTION_REQUEST_SCHEMA}")
    services = _publication_services(data_dir=data_dir, public_dir=public_dir)
    if services is None:
        raise ValueError("data_dir is required for profile basics updates")
    _summary_service, profile_service = services
    command = {
        "tenant_id": portal_instance_id,
        "tenant_domain": portal_domain,
        "profile_title": payload.get("profile_title") or "",
        "profile_summary": payload.get("profile_summary") or "",
        "contact_email": payload.get("contact_email") or "",
        "public_website_url": payload.get("public_website_url") or "",
    }
    outcome = profile_service.apply_write(command)
    if audit_storage_file is not None:
        try:
            _audit_service(audit_storage_file).append_record(outcome.to_local_audit_payload())
        except Exception:
            pass
    portal_scope = PortalScope(
        scope_id=portal_instance_id,
        capabilities=_default_capabilities(portal_instance_id),
    )
    bundle = _bundle_for_surface(
        active_surface_id=SYSTEM_PROFILE_BASICS_SURFACE_ID,
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
        private_dir=None,
        audit_storage_file=audit_storage_file,
        aws_status_file=None,
        aws_csm_sandbox_status_file=None,
        webapps_root=None,
        tool_exposure_policy=None,
    )
    surface_payload = dict(bundle["surface_payload"])
    surface_payload["form"] = dict(surface_payload.get("form") or {})
    surface_payload["form"]["status"] = "saved"
    surface_payload["confirmed_summary"] = outcome.confirmed_summary.to_dict()
    bundle["surface_payload"] = surface_payload
    bundle["workbench"] = _workbench_for_surface(surface_payload)
    bundle["inspector"] = _inspector_for_surface(surface_payload)
    composition = build_shell_composition_payload(
        active_surface_id=SYSTEM_PROFILE_BASICS_SURFACE_ID,
        portal_instance_id=portal_scope.scope_id,
        page_title=bundle["page_title"],
        page_subtitle=bundle["page_subtitle"],
        activity_items=_activity_items(
            portal_instance_id=portal_scope.scope_id,
            active_surface_id=SYSTEM_PROFILE_BASICS_SURFACE_ID,
        ),
        control_panel=_control_panel(
            portal_instance_id=portal_scope.scope_id,
            active_surface_id=SYSTEM_PROFILE_BASICS_SURFACE_ID,
            tool_rows=bundle["tool_rows"],
        ),
        workbench=bundle["workbench"],
        inspector=bundle["inspector"],
    )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=SYSTEM_PROFILE_BASICS_SURFACE_ID,
        surface_id=SYSTEM_PROFILE_BASICS_SURFACE_ID,
        entrypoint_id=PORTAL_SHELL_ENTRYPOINT_ID,
        read_write_posture="write",
        shell_state={
            "schema": "mycite.v2.portal.shell.state.v1",
            "requested_surface_id": SYSTEM_PROFILE_BASICS_SURFACE_ID,
            "active_surface_id": SYSTEM_PROFILE_BASICS_SURFACE_ID,
            "selection_status": "available",
            "allowed": True,
            "reason_code": "",
            "reason_message": "",
        },
        surface_payload=surface_payload,
        shell_composition=composition,
        warnings=[],
        error=None,
    )


__all__ = [
    "PORTAL_RUNTIME_ENVELOPE_SCHEMA",
    "run_portal_shell_entry",
    "run_system_profile_basics_action",
]
