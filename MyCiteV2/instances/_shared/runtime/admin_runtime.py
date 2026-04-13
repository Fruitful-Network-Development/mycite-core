from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAuditLogAdapter,
    FilesystemSystemDatumStoreAdapter,
    is_live_aws_profile_file,
)
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.modules.domains.datum_recognition import DatumWorkbenchService
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND0_NAME,
    ADMIN_ENTRYPOINT_ID,
    ADMIN_EXPOSURE_INTERNAL_ONLY,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_NETWORK_ROOT_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
    ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_SLICE_ID,
    DATUM_RESOURCE_WORKBENCH_SLICE_ID,
    MAPS_READ_ONLY_SLICE_ID,
    AdminShellChrome,
    AdminShellRequest,
    activity_icon_id_for_slice,
    build_admin_surface_catalog,
    build_admin_tool_registry_entries,
    build_portal_activity_dispatch_bodies,
    build_shell_composition_payload,
    map_surface_to_active_service,
    resolve_admin_shell_request,
)
from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
    ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA,
    ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    run_admin_aws_csm_family_home,
    run_admin_aws_csm_newsletter,
    run_admin_aws_csm_sandbox_read_only,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.admin_maps_runtime import (
    build_admin_maps_inspector,
    build_admin_maps_surface_payload,
    build_admin_maps_workbench,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_FAMILY_HOME_SURFACE_SCHEMA,
    ADMIN_HOME_STATUS_SURFACE_SCHEMA,
    ADMIN_MAPS_READ_ONLY_SURFACE_SCHEMA,
    ADMIN_NETWORK_ROOT_SURFACE_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA,
    admin_tool_exposure_config_enabled,
    build_allow_all_admin_tool_exposure_policy,
    build_admin_runtime_envelope,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_request(payload: dict[str, Any] | None) -> AdminShellRequest:
    if payload is None:
        return AdminShellRequest()
    if not isinstance(payload, dict):
        raise ValueError("admin_runtime.request_payload must be a dict")
    return AdminShellRequest.from_dict(payload)


def _build_audit_health(storage_file: str | Path | None) -> dict[str, str]:
    if storage_file is None:
        return {
            "status": "not_configured",
            "record_readback": "not_configured",
            "storage_state": "not_configured",
        }

    storage_path = Path(storage_file)
    adapter = FilesystemAuditLogAdapter(storage_path)
    local_audit_service = LocalAuditService(adapter)

    try:
        local_audit_service.read_record("__admin_band0_health_probe__")
    except Exception:
        return {
            "status": "error",
            "record_readback": "failed",
            "storage_state": "unavailable",
        }

    return {
        "status": "configured",
        "record_readback": "ok",
        "storage_state": "present" if storage_path.exists() else "missing_or_empty",
    }


def _resolved_tool_exposure_policy(tool_exposure_policy: dict[str, Any] | None) -> dict[str, Any]:
    if tool_exposure_policy is not None:
        return tool_exposure_policy
    return build_allow_all_admin_tool_exposure_policy(
        known_tool_ids=[entry.tool_id for entry in build_admin_tool_registry_entries()]
    )


def _tool_exposure_summary(tool_exposure_policy: dict[str, Any] | None) -> dict[str, Any]:
    policy = _resolved_tool_exposure_policy(tool_exposure_policy)
    return {
        "policy_source": _as_text(policy.get("policy_source")) or "runtime_default_allow_all",
        "configured_tool_ids": list(policy.get("configured_tool_ids") or []),
        "enabled_tool_ids": list(policy.get("enabled_tool_ids") or []),
        "disabled_tool_ids": list(policy.get("disabled_tool_ids") or []),
        "missing_tool_ids": list(policy.get("missing_tool_ids") or []),
        "unknown_tool_ids": list(policy.get("unknown_tool_ids") or []),
        "invalid_tool_ids": list(policy.get("invalid_tool_ids") or []),
        "configured_tools": dict(policy.get("configured_tools") or {}),
    }


def _runtime_tool_entries(
    *,
    tool_exposure_policy: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    policy = _resolved_tool_exposure_policy(tool_exposure_policy)
    rows: list[dict[str, Any]] = []
    for entry in build_admin_tool_registry_entries():
        config_enabled = admin_tool_exposure_config_enabled(policy, tool_id=entry.tool_id)
        activity_bar_visible = bool(entry.to_dict().get("activity_bar_visible", True))
        visible_in_activity_bar = bool(entry.launchable and config_enabled and activity_bar_visible)
        if not entry.launchable:
            visibility_status = "shell_gated"
        elif config_enabled:
            visibility_status = "visible" if activity_bar_visible else "family_subsurface"
        else:
            visibility_status = "config_disabled"
        row = entry.to_dict()
        row["config_enabled"] = config_enabled
        row["visibility_status"] = visibility_status
        row["visible_in_activity_bar"] = visible_in_activity_bar
        rows.append(row)
    return rows


def _tool_entry_by_slice_id(
    *,
    tool_exposure_policy: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    return {entry["slice_id"]: entry for entry in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)}


def _canonical_shell_href(slice_id: str) -> str:
    if slice_id == ADMIN_HOME_STATUS_SLICE_ID:
        return "/portal/system"
    if slice_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return "/portal/network"
    if slice_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return "/portal/utilities"
    if slice_id == DATUM_RESOURCE_WORKBENCH_SLICE_ID:
        return "/portal/system/datum"
    if slice_id == AWS_READ_ONLY_SLICE_ID:
        return "/portal/utilities/aws-csm"
    if slice_id == AWS_NARROW_WRITE_SLICE_ID:
        return "/portal/utilities/aws-write"
    if slice_id == AWS_CSM_ONBOARDING_SLICE_ID:
        return "/portal/utilities/aws-csm-onboarding"
    if slice_id == AWS_CSM_SANDBOX_SLICE_ID:
        return "/portal/utilities/aws-csm-sandbox"
    if slice_id == MAPS_READ_ONLY_SLICE_ID:
        return "/portal/utilities/maps"
    return "/portal/system"


def _root_surface_label(slice_id: str) -> str:
    if slice_id == ADMIN_HOME_STATUS_SLICE_ID:
        return "System"
    if slice_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return "Network"
    if slice_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return "Utilities"
    return _as_text(slice_id)


def _build_home_status_surface(
    *,
    audit_storage_file: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface_catalog = [entry.to_dict() for entry in build_admin_surface_catalog()]
    tool_entries = _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
    launchable_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["visible_in_activity_bar"]]
    gated_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if not entry["visible_in_activity_bar"]]
    available_tool_slices = [entry for entry in tool_entries if entry["visible_in_activity_bar"]]
    gated_tool_slices = [entry for entry in tool_entries if not entry["visible_in_activity_bar"]]

    return {
        "schema": ADMIN_HOME_STATUS_SURFACE_SCHEMA,
        "active_surface_id": ADMIN_HOME_STATUS_SLICE_ID,
        "current_admin_band": ADMIN_BAND0_NAME,
        "exposure_posture": ADMIN_EXPOSURE_INTERNAL_ONLY,
        "available_admin_slices": surface_catalog,
        "available_tool_slices": available_tool_slices,
        "gated_tool_slices": gated_tool_slices,
        "runtime_health": {
            "entrypoint_status": "ready",
            "registry_status": "deny-by-default",
            "provider_route_mode": "shell_only",
            "audit_log": _build_audit_health(audit_storage_file),
            "tool_exposure": _tool_exposure_summary(tool_exposure_policy),
        },
        "readiness_summary": {
            "shell_entry": "ready",
            "home_status": "ready",
            "tool_registry": "ready",
            "launchable_tool_slice_ids": launchable_tool_slice_ids,
            "gated_tool_slice_ids": gated_tool_slice_ids,
            "next_tool_slice_id": MAPS_READ_ONLY_SLICE_ID if MAPS_READ_ONLY_SLICE_ID in launchable_tool_slice_ids else AWS_READ_ONLY_SLICE_ID,
        },
        "follow_on_order": [
            MAPS_READ_ONLY_SLICE_ID,
            "agro_erp_after_maps",
        ],
    }


def _build_tool_registry_surface(
    *,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface_catalog = [entry.to_dict() for entry in build_admin_surface_catalog()]
    tool_entries = _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
    launchable_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["launchable"]]
    visible_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["visible_in_activity_bar"]]
    gated_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if not entry["visible_in_activity_bar"]]

    return {
        "schema": ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA,
        "active_surface_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
        "registry_owner": "shell",
        "default_posture": "deny-by-default",
        "launchable_admin_slice_ids": [entry["slice_id"] for entry in surface_catalog if entry["launchable"]],
        "launchable_tool_slice_ids": launchable_tool_slice_ids,
        "visible_tool_slice_ids": visible_tool_slice_ids,
        "gated_tool_slice_ids": gated_tool_slice_ids,
        "tool_entries": tool_entries,
        "tool_exposure": _tool_exposure_summary(tool_exposure_policy),
        "follow_on_constraints": {
            "maps": "implemented_read_only",
            "agro_erp": "blocked_until_maps",
        },
    }


def _build_network_root_surface(
    *,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_summary = _tool_exposure_summary(tool_exposure_policy)
    visible_utility_count = len(
        [entry for entry in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy) if entry["visible_in_activity_bar"]]
    )
    return {
        "schema": ADMIN_NETWORK_ROOT_SURFACE_SCHEMA,
        "active_surface_id": ADMIN_NETWORK_ROOT_SLICE_ID,
        "network_state": "lightweight_placeholder",
        "summary": {
            "hosted_root": "pending_fnd_ebi",
            "tool_visibility_source": tool_summary.get("policy_source") or "runtime_default_allow_all",
            "visible_utility_count": visible_utility_count,
        },
        "blocks": [
            {"kind": "metric", "label": "Hosted root", "value": "pending"},
            {"kind": "metric", "label": "Visible utilities", "value": str(visible_utility_count)},
            {"kind": "metric", "label": "FND-EBI", "value": "follow-on"},
        ],
        "notes": [
            "Network is now a first-class shell root and remains intentionally lightweight in this pass.",
            "No hosted service runtimes are loaded here until a dedicated network family surface lands.",
            "System remains the default core root; utility tools continue to launch only when explicitly selected.",
        ],
    }


def _select_band0_surface_payload(
    *,
    active_surface_id: str,
    audit_storage_file: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if active_surface_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return _build_network_root_surface(tool_exposure_policy=tool_exposure_policy)
    if active_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return _build_tool_registry_surface(tool_exposure_policy=tool_exposure_policy)
    return _build_home_status_surface(
        audit_storage_file=audit_storage_file,
        tool_exposure_policy=tool_exposure_policy,
    )


def _live_aws_path(aws_status_file: str | Path | None) -> Path | None:
    if aws_status_file is None:
        return None
    p = Path(aws_status_file)
    if is_live_aws_profile_file(p):
        return p
    return None


def _activity_items(
    *,
    portal_tenant_id: str,
    nav_active_slice_id: str,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    bodies = build_portal_activity_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    active_service = map_surface_to_active_service(nav_active_slice_id)
    visible_tool_slice_ids = {
        entry["slice_id"]
        for entry in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
        if entry["visible_in_activity_bar"]
    }
    items: list[dict[str, Any]] = [
        {
            "slice_id": ADMIN_HOME_STATUS_SLICE_ID,
            "label": "FND",
            "aria_label": "Go to System root",
            "icon_id": "fnd-logo",
            "nav_kind": "root_logo",
            "active": False,
            "shell_request": bodies[ADMIN_HOME_STATUS_SLICE_ID],
            "href": _canonical_shell_href(ADMIN_HOME_STATUS_SLICE_ID),
        },
        {
            "slice_id": ADMIN_NETWORK_ROOT_SLICE_ID,
            "label": "Network",
            "aria_label": "Open Network root",
            "icon_id": activity_icon_id_for_slice(ADMIN_NETWORK_ROOT_SLICE_ID),
            "nav_kind": "root_service",
            "active": active_service == "network",
            "shell_request": bodies[ADMIN_NETWORK_ROOT_SLICE_ID],
            "href": _canonical_shell_href(ADMIN_NETWORK_ROOT_SLICE_ID),
        },
        {
            "slice_id": ADMIN_HOME_STATUS_SLICE_ID,
            "label": "System",
            "aria_label": "Open System root",
            "icon_id": activity_icon_id_for_slice(ADMIN_HOME_STATUS_SLICE_ID),
            "nav_kind": "root_service",
            "active": active_service == "system",
            "shell_request": bodies[ADMIN_HOME_STATUS_SLICE_ID],
            "href": _canonical_shell_href(ADMIN_HOME_STATUS_SLICE_ID),
        },
        {
            "slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
            "label": "Utilities",
            "aria_label": "Open Utilities root",
            "icon_id": activity_icon_id_for_slice(ADMIN_TOOL_REGISTRY_SLICE_ID),
            "nav_kind": "root_service",
            "active": active_service == "utilities",
            "shell_request": bodies[ADMIN_TOOL_REGISTRY_SLICE_ID],
            "href": _canonical_shell_href(ADMIN_TOOL_REGISTRY_SLICE_ID),
        },
    ]
    for tool in build_admin_tool_registry_entries():
        if not tool.launchable or tool.slice_id not in bodies or tool.slice_id not in visible_tool_slice_ids:
            continue
        items.append(
            {
                "slice_id": tool.slice_id,
                "label": tool.label,
                "aria_label": tool.label,
                "icon_id": activity_icon_id_for_slice(tool.slice_id),
                "nav_kind": "tool",
                "active": tool.slice_id == nav_active_slice_id,
                "shell_request": bodies[tool.slice_id],
                "href": _canonical_shell_href(tool.slice_id),
                "entrypoint_id": tool.entrypoint_id,
                "read_write_posture": tool.read_write_posture,
            }
        )
    return items


def _control_panel_region(
    *,
    portal_tenant_id: str,
    nav_active_slice_id: str,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bodies = build_portal_activity_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    visible_tool_rows = [
        entry
        for entry in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
        if entry["visible_in_activity_bar"]
    ]
    system_entries = [
        {
            "label": "Home and status",
            "meta": "default core root",
            "active": nav_active_slice_id == ADMIN_HOME_STATUS_SLICE_ID,
            "shell_request": bodies[ADMIN_HOME_STATUS_SLICE_ID],
            "href": _canonical_shell_href(ADMIN_HOME_STATUS_SLICE_ID),
        },
        {
            "label": "Authoritative datum",
            "meta": DATUM_RESOURCE_WORKBENCH_SLICE_ID,
            "active": nav_active_slice_id == DATUM_RESOURCE_WORKBENCH_SLICE_ID,
            "shell_request": bodies[DATUM_RESOURCE_WORKBENCH_SLICE_ID],
            "href": _canonical_shell_href(DATUM_RESOURCE_WORKBENCH_SLICE_ID),
        },
    ]
    network_entries = [
        {
            "label": "Network overview",
            "meta": "hosted and service follow-on root",
            "active": nav_active_slice_id == ADMIN_NETWORK_ROOT_SLICE_ID,
            "shell_request": bodies[ADMIN_NETWORK_ROOT_SLICE_ID],
            "href": _canonical_shell_href(ADMIN_NETWORK_ROOT_SLICE_ID),
        }
    ]
    utility_entries: list[dict[str, Any]] = [
        {
            "label": "Tool launcher",
            "meta": ADMIN_TOOL_REGISTRY_SLICE_ID,
            "active": nav_active_slice_id == ADMIN_TOOL_REGISTRY_SLICE_ID,
            "shell_request": bodies[ADMIN_TOOL_REGISTRY_SLICE_ID],
            "href": _canonical_shell_href(ADMIN_TOOL_REGISTRY_SLICE_ID),
        }
    ]
    for tool in build_admin_tool_registry_entries():
        row = next((item for item in visible_tool_rows if item["slice_id"] == tool.slice_id), None)
        if row is None:
            continue
        utility_entries.append(
            {
                "label": tool.label,
                "meta": tool.entrypoint_id,
                "active": tool.slice_id == nav_active_slice_id,
                "shell_request": bodies.get(tool.slice_id),
                "href": _canonical_shell_href(tool.slice_id),
            }
        )
    return {
        "schema": ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "sections": [
            {"title": "System", "entries": system_entries},
            {"title": "Network", "entries": network_entries},
            {"title": "Utilities", "entries": utility_entries},
        ],
    }


def _workbench_error(*, title: str, message: str) -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "error",
        "title": title,
        "subtitle": "",
        "visible": True,
        "message": message,
    }


def _workbench_home(*, surface_payload: dict[str, Any] | None) -> dict[str, Any]:
    sp = surface_payload or {}
    audit = (sp.get("runtime_health") or {}).get("audit_log") or {}
    tool_exposure = (sp.get("runtime_health") or {}).get("tool_exposure") or {}
    readiness = sp.get("readiness_summary") or {}
    available_tools = sp.get("available_tool_slices") or []
    gated_tools = sp.get("gated_tool_slices") or []
    blocks = [
        {"kind": "metric", "label": "Admin audit", "value": _as_text(audit.get("status")) or "—"},
        {"kind": "metric", "label": "Shell entry", "value": _as_text(readiness.get("shell_entry")) or "—"},
        {"kind": "metric", "label": "Tool registry", "value": _as_text(readiness.get("tool_registry")) or "—"},
        {"kind": "metric", "label": "Visible tools", "value": str(len(available_tools))},
        {"kind": "metric", "label": "Config gated tools", "value": str(len(gated_tools))},
    ]
    notes = [
        {
            "label": "Enabled tool ids",
            "value": ", ".join(tool_exposure.get("enabled_tool_ids") or []) or "None",
        },
        {
            "label": "Config gated tools",
            "value": ", ".join(entry.get("label") or entry.get("tool_id") or "" for entry in gated_tools) or "None",
        },
    ]
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "home_summary",
        "title": "System",
        "subtitle": "Default core root",
        "visible": True,
        "blocks": blocks,
        "notes": notes,
    }


def _workbench_registry(*, surface_payload: dict[str, Any] | None) -> dict[str, Any]:
    sp = surface_payload or {}
    rows = sp.get("tool_entries") or []
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_registry",
        "title": "Utilities",
        "subtitle": "Tool launcher and utility surfaces",
        "visible": True,
        "tool_rows": rows,
    }


def _workbench_network(*, surface_payload: dict[str, Any] | None) -> dict[str, Any]:
    sp = surface_payload or {}
    notes = sp.get("notes") or []
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "network_root",
        "title": "Network",
        "subtitle": "Lightweight hosted and service readiness root",
        "visible": True,
        "blocks": list(sp.get("blocks") or []),
        "notes": list(notes),
    }


def _workbench_datum(*, datum_dict: dict[str, Any]) -> dict[str, Any]:
    rows = datum_dict.get("rows_preview") or datum_dict.get("rows") or []
    preview: list[Any] = list(cast(list[Any], rows)[:60]) if isinstance(rows, list) else []
    selected_document = datum_dict.get("selected_document") or {}
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "datum_workbench",
        "title": "Authoritative datum",
        "subtitle": (
            f"{datum_dict.get('row_count', '—')} rows · "
            f"{_as_text(selected_document.get('document_name')) or _as_text(datum_dict.get('tenant_id')) or '—'}"
        ),
        "visible": True,
        "summary": {
            "ok": datum_dict.get("ok"),
            "row_count": datum_dict.get("row_count"),
            "document_count": datum_dict.get("document_count"),
            "tenant_id": datum_dict.get("tenant_id"),
            "selected_document": selected_document,
            "diagnostic_totals": datum_dict.get("diagnostic_totals"),
            "readiness_status": datum_dict.get("readiness_status"),
            "source_files": datum_dict.get("source_files"),
        },
        "warnings": list(datum_dict.get("warnings") or []),
        "documents": list(datum_dict.get("documents") or []),
        "rows_preview": preview,
    }


def _inspector_empty(*, title: str = "Overview") -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": title,
        "kind": "empty",
        "body_text": "Select a shell projection or open a tool from the activity bar.",
    }


def _inspector_json(*, title: str, document: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": title,
        "kind": "json_document",
        "document": document or {},
    }


def _inspector_datum(*, datum_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "Datum",
        "kind": "datum_summary",
        "selected_document": datum_dict.get("selected_document") or {},
        "readiness_status": datum_dict.get("readiness_status") or {},
        "source_files": datum_dict.get("source_files") or {},
        "warnings": list(datum_dict.get("warnings") or []),
    }


def _inspector_network(*, surface_payload: dict[str, Any] | None) -> dict[str, Any]:
    sp = surface_payload or {}
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "Network",
        "kind": "network_summary",
        "network_state": _as_text(sp.get("network_state")) or "lightweight_placeholder",
        "summary": dict(sp.get("summary") or {}),
        "notes": list(sp.get("notes") or []),
    }


def _inspector_aws_read_only_surface(*, surface: dict[str, Any]) -> dict[str, Any]:
    profile = surface.get("canonical_newsletter_operational_profile") or {}
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "AWS read-only",
        "kind": "aws_read_only_surface",
        "tenant_scope_id": _as_text(surface.get("tenant_scope_id")),
        "mailbox_readiness": _as_text(surface.get("mailbox_readiness")),
        "smtp_state": _as_text(surface.get("smtp_state")),
        "gmail_state": _as_text(surface.get("gmail_state")),
        "verified_evidence_state": _as_text(surface.get("verified_evidence_state")),
        "selected_verified_sender": _as_text(surface.get("selected_verified_sender")),
        "allowed_send_domains": list(surface.get("allowed_send_domains") or []),
        "write_capability": _as_text(surface.get("write_capability")),
        "profile_summary": {
            "profile_id": _as_text(profile.get("profile_id")),
            "domain": _as_text(profile.get("domain")),
            "list_address": _as_text(profile.get("list_address")),
            "delivery_mode": _as_text(profile.get("delivery_mode")),
        },
        "compatibility_warnings": list(surface.get("compatibility_warnings") or []),
        "inbound_capture": surface.get("inbound_capture"),
        "dispatch_health": surface.get("dispatch_health"),
    }


def _inspector_aws_csm_family_home(*, surface: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "AWS-CSM",
        "kind": "aws_csm_family_home",
        "family_health": surface.get("family_health") or {},
        "primary_read_only": surface.get("primary_read_only") or {},
        "domain_states": list(surface.get("domain_states") or []),
        "selected_domain_state": surface.get("selected_domain_state") or {},
        "newsletter_enabled": bool(surface.get("newsletter_enabled")),
        "subsurface_navigation": surface.get("subsurface_navigation") or {},
        "gated_subsurfaces": surface.get("gated_subsurfaces") or {},
    }


def _inspector_aws_tool_error(*, error: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "AWS tool",
        "kind": "aws_tool_error",
        "error_code": _as_text(error.get("code")),
        "error_message": _as_text(error.get("message")),
        "warnings": list(warnings),
    }


def _apply_shell_chrome_to_composition(composition: dict[str, Any], chrome: AdminShellChrome) -> None:
    echo = chrome.to_dict()
    if echo:
        composition["requested_shell_chrome"] = echo
    if chrome.control_panel_collapsed is not None:
        composition["control_panel_collapsed"] = bool(chrome.control_panel_collapsed)
    if chrome.inspector_collapsed is None:
        return
    composition["inspector_collapsed"] = bool(chrome.inspector_collapsed)
    if composition.get("composition_mode") == "tool" and chrome.inspector_collapsed:
        composition["foreground_shell_region"] = "center-workbench"
        wb = composition["regions"].get("workbench")
        if isinstance(wb, dict) and wb.get("visible") is False:
            composition["regions"]["workbench"] = {
                **wb,
                "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
                "visible": True,
                "kind": "tool_collapsed_inspector",
                "title": wb.get("title") or "Tool",
                "subtitle": "Interface panel dismissed in shell state. Re-open via the menu bar or repeat the shell request without collapsing shell_chrome.",
            }


def _inspector_csm_onboarding_form(
    *,
    portal_tenant_id: str,
    read_only_document: dict[str, Any] | None,
) -> dict[str, Any]:
    sp = read_only_document or {}
    profile = sp.get("canonical_newsletter_operational_profile") or {}
    initial = {
        "profile_id": _as_text(profile.get("profile_id")),
        "onboarding_action": "begin_onboarding",
    }
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "AWS-CSM onboarding",
        "kind": "csm_onboarding_form",
        "read_only_context": sp,
        "submit_contract": {
            "route": "/portal/api/v2/admin/aws/csm-onboarding",
            "method": "POST",
            "request_schema": ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
            "field_names": ["profile_id", "onboarding_action"],
            "initial_values": initial,
            "fixed_request_fields": {
                "focus_subject": "v2-portal-shell",
                "tenant_scope": {"scope_id": portal_tenant_id, "audience": "trusted-tenant"},
            },
            "onboarding_action_options": [
                "begin_onboarding",
                "prepare_send_as",
                "stage_smtp_credentials",
                "capture_verification",
                "refresh_provider_status",
                "refresh_inbound_status",
                "enable_inbound_capture",
                "replay_verification_forward",
                "confirm_receive_verified",
                "confirm_verified",
            ],
        },
    }


def _inspector_narrow_write_form(
    *,
    portal_tenant_id: str,
    read_only_document: dict[str, Any] | None,
) -> dict[str, Any]:
    sp = read_only_document or {}
    profile = sp.get("canonical_newsletter_operational_profile") or {}
    initial = {
        "profile_id": _as_text(profile.get("profile_id")),
        "selected_verified_sender": _as_text(sp.get("selected_verified_sender")),
    }
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "AWS narrow write",
        "kind": "narrow_write_form",
        "read_only_context": sp,
        "submit_contract": {
            "route": "/portal/api/v2/admin/aws/narrow-write",
            "method": "POST",
            "request_schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
            "field_names": ["profile_id", "selected_verified_sender"],
            "initial_values": initial,
            "fixed_request_fields": {
                "focus_subject": "v2-portal-shell",
                "tenant_scope": {"scope_id": portal_tenant_id, "audience": "trusted-tenant"},
            },
        },
    }


def _build_regions_and_surface(
    *,
    selection_ok: bool,
    nav_active_slice_id: str,
    portal_tenant_id: str,
    audit_storage_file: str | Path | None,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    selection: Any,
    normalized_request: AdminShellRequest,
) -> tuple[dict[str, Any] | None, dict[str, Any], str, str]:
    """Returns surface_payload, shell_composition, page_title, page_subtitle."""
    if not selection_ok:
        surface_fallback: dict[str, Any] | None = None
        if selection.active_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
            surface_fallback = _select_band0_surface_payload(
                active_surface_id=selection.active_surface_id,
                audit_storage_file=audit_storage_file,
                tool_exposure_policy=tool_exposure_policy,
            )
        elif normalized_request.tenant_scope.audience == "internal" and selection.active_surface_id in {
            ADMIN_HOME_STATUS_SLICE_ID,
            AWS_CSM_SANDBOX_SLICE_ID,
            MAPS_READ_ONLY_SLICE_ID,
        }:
            surface_fallback = _select_band0_surface_payload(
                active_surface_id=selection.active_surface_id,
                audit_storage_file=audit_storage_file,
                tool_exposure_policy=tool_exposure_policy,
            )
        if surface_fallback and selection.active_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
            wb: dict[str, Any] = {
                "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
                "kind": "tool_registry",
                "title": "Utilities",
                "subtitle": _as_text(selection.reason_message) or "Selection blocked",
                "visible": True,
                "tool_rows": surface_fallback.get("tool_entries") or [],
                "banner": {"code": selection.reason_code, "message": selection.reason_message},
            }
        else:
            wb = _workbench_error(
                title="Shell",
                message=_as_text(selection.reason_message) or _as_text(selection.reason_code) or "Request not allowed.",
            )
        comp_layout_surface = (
            selection.active_surface_id
            if selection.active_surface_id in {
                ADMIN_HOME_STATUS_SLICE_ID,
                ADMIN_NETWORK_ROOT_SLICE_ID,
                ADMIN_TOOL_REGISTRY_SLICE_ID,
                AWS_CSM_SANDBOX_SLICE_ID,
                MAPS_READ_ONLY_SLICE_ID,
            }
            else ADMIN_HOME_STATUS_SLICE_ID
        )
        comp = build_shell_composition_payload(
            active_surface_id=comp_layout_surface,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="Shell selection blocked",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
            inspector=_inspector_empty(title="Overview"),
        )
        return surface_fallback, comp, "MyCite", "Shell"

    active = selection.active_surface_id

    if active == ADMIN_HOME_STATUS_SLICE_ID:
        sp = _build_home_status_surface(
            audit_storage_file=audit_storage_file,
            tool_exposure_policy=tool_exposure_policy,
        )
        wb = _workbench_home(surface_payload=sp)
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="System",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
            inspector=_inspector_empty(title="System"),
        )
        return sp, comp, "MyCite", "System"

    if active == ADMIN_NETWORK_ROOT_SLICE_ID:
        sp = _build_network_root_surface(tool_exposure_policy=tool_exposure_policy)
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="Network",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=_workbench_network(surface_payload=sp),
            inspector=_inspector_network(surface_payload=sp),
        )
        return sp, comp, "MyCite", "Network"

    if active == ADMIN_TOOL_REGISTRY_SLICE_ID:
        sp = _build_tool_registry_surface(tool_exposure_policy=tool_exposure_policy)
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="Utilities",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=_workbench_registry(surface_payload=sp),
            inspector=_inspector_empty(title="Utilities"),
        )
        return sp, comp, "MyCite", "Utilities"

    if active == DATUM_RESOURCE_WORKBENCH_SLICE_ID:
        if data_dir is None:
            sp = {"schema": "mycite.v2.admin.datum_workbench.surface.v1", "error": "data_dir_not_configured"}
            wb = _workbench_error(title="Datum", message="Host data directory is not configured for this shell request.")
            comp = build_shell_composition_payload(
                active_surface_id=active,
                portal_tenant_id=portal_tenant_id,
                page_title="MyCite",
                page_subtitle="Datum",
                activity_items=_activity_items(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                control_panel=_control_panel_region(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                workbench=wb,
                inspector=_inspector_empty(),
            )
            return sp, comp, "MyCite", "Resource workbench"
        adapter = FilesystemSystemDatumStoreAdapter(Path(data_dir))
        dd = DatumWorkbenchService(adapter).read_workbench(portal_tenant_id).to_dict()
        sp = {"schema": "mycite.v2.admin.datum_workbench.surface.v1", "workbench": dd}
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="Authoritative datum",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=_workbench_datum(datum_dict=dd),
            inspector=_inspector_datum(datum_dict=dd),
        )
        return sp, comp, "MyCite", "Resource workbench"

    if active == AWS_READ_ONLY_SLICE_ID:
        aws_path = _live_aws_path(aws_status_file)
        family_payload = {
            "schema": ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA,
            "tenant_scope": {"scope_id": portal_tenant_id, "audience": "trusted-tenant"},
        }
        aws_env = run_admin_aws_csm_family_home(
            family_payload,
            aws_status_file=aws_path,
            private_dir=private_dir,
            tool_exposure_policy=tool_exposure_policy,
        )
        sp = aws_env.get("surface_payload")
        err = aws_env.get("error")
        if err:
            wb = _workbench_error(title="AWS-CSM", message=_as_text((err or {}).get("message")) or "AWS surface failed.")
            raw_w = aws_env.get("warnings") or []
            wlist = list(raw_w) if isinstance(raw_w, (list, tuple)) else []
            ins = _inspector_aws_tool_error(error=err if isinstance(err, dict) else {}, warnings=wlist)
        else:
            wb = {
                "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
                "kind": "tool_placeholder",
                "title": "AWS-CSM",
                "subtitle": "Family landing surface",
                "visible": False,
            }
            ins = _inspector_aws_csm_family_home(surface=sp if isinstance(sp, dict) else {})
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="AWS-CSM",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
                inspector=ins,
        )
        return sp, comp, "MyCite", "AWS-CSM"

    if active == AWS_NARROW_WRITE_SLICE_ID:
        aws_path = _live_aws_path(aws_status_file)
        ro_payload = {
            "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
            "tenant_scope": {"scope_id": portal_tenant_id, "audience": "trusted-tenant"},
        }
        aws_env = run_admin_aws_read_only(ro_payload, aws_status_file=aws_path)
        ro_surface = aws_env.get("surface_payload") if not aws_env.get("error") else None
        wb = {
            "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
            "kind": "tool_placeholder",
            "title": "AWS narrow write",
            "subtitle": "Bounded write projection",
            "visible": False,
        }
        ins = _inspector_narrow_write_form(portal_tenant_id=portal_tenant_id, read_only_document=ro_surface if isinstance(ro_surface, dict) else None)
        sp_wrap = {
            "schema": "mycite.v2.admin.aws.narrow_write.panel_surface.v1",
            "read_only_preview_error": aws_env.get("error"),
            "read_only_surface": ro_surface,
        }
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="AWS narrow write",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
            inspector=ins,
        )
        return sp_wrap, comp, "MyCite", "AWS narrow write"

    if active == AWS_CSM_ONBOARDING_SLICE_ID:
        aws_path = _live_aws_path(aws_status_file)
        ro_payload = {
            "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
            "tenant_scope": {"scope_id": portal_tenant_id, "audience": "trusted-tenant"},
        }
        aws_env = run_admin_aws_read_only(ro_payload, aws_status_file=aws_path)
        ro_surface = aws_env.get("surface_payload") if not aws_env.get("error") else None
        wb = {
            "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
            "kind": "tool_placeholder",
            "title": "AWS-CSM onboarding",
            "subtitle": "Bounded orchestration projection",
            "visible": False,
        }
        ins = _inspector_csm_onboarding_form(
            portal_tenant_id=portal_tenant_id,
            read_only_document=ro_surface if isinstance(ro_surface, dict) else None,
        )
        sp_wrap = {
            "schema": "mycite.v2.admin.aws.csm_onboarding.panel_surface.v1",
            "read_only_preview_error": aws_env.get("error"),
            "read_only_surface": ro_surface,
        }
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="AWS-CSM onboarding",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
            inspector=ins,
        )
        return sp_wrap, comp, "MyCite", "AWS-CSM onboarding"

    if active == AWS_CSM_SANDBOX_SLICE_ID:
        sandbox_path = _live_aws_path(aws_csm_sandbox_status_file)
        ro_payload = {
            "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
            "tenant_scope": {"scope_id": portal_tenant_id, "audience": "internal"},
        }
        aws_env = run_admin_aws_csm_sandbox_read_only(ro_payload, aws_sandbox_status_file=sandbox_path)
        sp = aws_env.get("surface_payload")
        err = aws_env.get("error")
        if err:
            wb = _workbench_error(
                title="AWS-CSM Sandbox",
                message=_as_text((err or {}).get("message")) or "Sandbox AWS surface failed.",
            )
            raw_w = aws_env.get("warnings") or []
            wlist = list(raw_w) if isinstance(raw_w, (list, tuple)) else []
            ins = _inspector_aws_tool_error(error=err if isinstance(err, dict) else {}, warnings=wlist)
        else:
            wb = {
                "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
                "kind": "tool_placeholder",
                "title": "AWS-CSM Sandbox",
                "subtitle": "Read-only sandbox profile (interface panel)",
                "visible": False,
            }
            ins = _inspector_aws_read_only_surface(surface=sp if isinstance(sp, dict) else {})
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="AWS-CSM sandbox",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
            inspector=ins,
        )
        return sp, comp, "MyCite", "AWS-CSM sandbox"

    if active == MAPS_READ_ONLY_SLICE_ID:
        if data_dir is None:
            sp = {
                "schema": ADMIN_MAPS_READ_ONLY_SURFACE_SCHEMA,
                "active_surface_id": MAPS_READ_ONLY_SLICE_ID,
                "error": "data_root_not_configured",
            }
            wb = _workbench_error(title="Maps", message="Host data directory is not configured for the maps tool.")
            comp = build_shell_composition_payload(
                active_surface_id=active,
                portal_tenant_id=portal_tenant_id,
                page_title="MyCite",
                page_subtitle="Maps",
                activity_items=_activity_items(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                control_panel=_control_panel_region(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                workbench=wb,
                inspector=_inspector_empty(title="Maps"),
            )
            return sp, comp, "MyCite", "Maps"

        sp = build_admin_maps_surface_payload(
            portal_tenant_id=portal_tenant_id,
            data_dir=data_dir,
        )
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="Maps",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=build_admin_maps_workbench(
                surface_payload=sp,
                portal_tenant_id=portal_tenant_id,
            ),
            inspector=build_admin_maps_inspector(surface_payload=sp),
        )
        return sp, comp, "MyCite", "Maps"

    sp = _build_home_status_surface(
        audit_storage_file=audit_storage_file,
        tool_exposure_policy=tool_exposure_policy,
    )
    comp = build_shell_composition_payload(
        active_surface_id=ADMIN_HOME_STATUS_SLICE_ID,
        portal_tenant_id=portal_tenant_id,
        page_title="MyCite",
        page_subtitle="Unknown surface",
        activity_items=_activity_items(
            portal_tenant_id=portal_tenant_id,
            nav_active_slice_id=nav_active_slice_id,
            tool_exposure_policy=tool_exposure_policy,
        ),
        control_panel=_control_panel_region(
            portal_tenant_id=portal_tenant_id,
            nav_active_slice_id=nav_active_slice_id,
            tool_exposure_policy=tool_exposure_policy,
        ),
        workbench=_workbench_error(title="Shell", message=f"Unhandled surface: {active}"),
        inspector=_inspector_empty(),
    )
    return sp, comp, "MyCite", "Shell"


def run_admin_shell_entry(
    request_payload: dict[str, Any] | None = None,
    *,
    audit_storage_file: str | Path | None = None,
    portal_tenant_id: str = "fnd",
    aws_status_file: str | Path | None = None,
    aws_csm_sandbox_status_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_request = _normalize_request(request_payload)
    selection = resolve_admin_shell_request(normalized_request)
    tool_entry = _tool_entry_by_slice_id(tool_exposure_policy=tool_exposure_policy).get(
        normalized_request.requested_slice_id
    )
    if tool_entry is not None and not bool(tool_entry.get("config_enabled")):
        selection = type(selection)(
            requested_slice_id=normalized_request.requested_slice_id,
            active_surface_id=ADMIN_TOOL_REGISTRY_SLICE_ID,
            selection_status="gated",
            allowed=False,
            reason_code=ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
            reason_message="Requested admin tool is disabled by instance tool_exposure configuration.",
        )

    nav_active_slice_id = normalized_request.requested_slice_id

    surface_payload, shell_composition, page_title, page_subtitle = _build_regions_and_surface(
        selection_ok=selection.allowed,
        nav_active_slice_id=nav_active_slice_id,
        portal_tenant_id=_as_text(portal_tenant_id) or "fnd",
        audit_storage_file=audit_storage_file,
        aws_status_file=aws_status_file,
        aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
        data_dir=data_dir,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
        selection=selection,
        normalized_request=normalized_request,
    )

    shell_composition["page_title"] = page_title
    shell_composition["page_subtitle"] = page_subtitle
    _apply_shell_chrome_to_composition(shell_composition, normalized_request.shell_chrome)

    error = None
    warnings: list[str] = []
    if not selection.allowed:
        error = {
            "code": selection.reason_code,
            "message": selection.reason_message,
        }
        if selection.reason_message:
            warnings.append(selection.reason_message)

    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND0_NAME,
        exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
        tenant_scope=normalized_request.tenant_scope.to_dict(),
        requested_slice_id=normalized_request.requested_slice_id,
        slice_id=selection.active_surface_id,
        entrypoint_id=ADMIN_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=selection.to_dict(),
        surface_payload=surface_payload,
        shell_composition=shell_composition,
        warnings=warnings,
        error=error,
    )


__all__ = [
    "ADMIN_HOME_STATUS_SURFACE_SCHEMA",
    "ADMIN_RUNTIME_ENVELOPE_SCHEMA",
    "ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA",
    "run_admin_shell_entry",
]
