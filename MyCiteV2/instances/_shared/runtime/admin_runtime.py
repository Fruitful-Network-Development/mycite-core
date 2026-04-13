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
    CTS_GIS_READ_ONLY_SLICE_ID,
    FND_EBI_READ_ONLY_SLICE_ID,
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
from MyCiteV2.instances._shared.runtime.admin_cts_gis_runtime import (
    build_admin_cts_gis_inspector,
    build_admin_cts_gis_surface_payload,
    build_admin_cts_gis_workbench,
)
from MyCiteV2.instances._shared.runtime.admin_fnd_ebi_runtime import (
    build_admin_fnd_ebi_inspector,
    build_admin_fnd_ebi_surface_payload,
    build_admin_fnd_ebi_workbench,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_FAMILY_HOME_SURFACE_SCHEMA,
    ADMIN_HOME_STATUS_SURFACE_SCHEMA,
    ADMIN_CTS_GIS_READ_ONLY_SURFACE_SCHEMA,
    ADMIN_FND_EBI_READ_ONLY_SURFACE_SCHEMA,
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


SYSTEM_ROOT_TABS = ("home", "sources", "sandbox")
NETWORK_ROOT_TABS = ("messages", "hosted", "profile", "contracts")
UTILITIES_ROOT_TABS = ("tools", "config", "vault")


def _normalize_root_tab(active_surface_id: str, requested_tab: object) -> str:
    tab = _as_text(requested_tab).lower()
    if active_surface_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return tab if tab in NETWORK_ROOT_TABS else NETWORK_ROOT_TABS[0]
    if active_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return tab if tab in UTILITIES_ROOT_TABS else UTILITIES_ROOT_TABS[0]
    if active_surface_id in {ADMIN_HOME_STATUS_SLICE_ID, DATUM_RESOURCE_WORKBENCH_SLICE_ID}:
        return tab if tab in SYSTEM_ROOT_TABS else SYSTEM_ROOT_TABS[0]
    return ""


def _root_tab_label(root_tab: str) -> str:
    labels = {
        "home": "Home",
        "sources": "Sources",
        "sandbox": "Sandbox",
        "messages": "Messages",
        "hosted": "Hosted",
        "profile": "Profile",
        "contracts": "Contracts",
        "tools": "Tools",
        "config": "Config",
        "vault": "Vault",
    }
    return labels.get(_as_text(root_tab).lower(), _as_text(root_tab).title())


def _root_tab_path(root_surface_id: str, root_tab: str) -> str:
    if root_surface_id == ADMIN_HOME_STATUS_SLICE_ID:
        return "/portal/system" if root_tab == "home" else f"/portal/system?tab={root_tab}"
    if root_surface_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return "/portal/network" if root_tab == NETWORK_ROOT_TABS[0] else f"/portal/network?tab={root_tab}"
    if root_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return "/portal/utilities" if root_tab == UTILITIES_ROOT_TABS[0] else f"/portal/utilities?tab={root_tab}"
    return _canonical_shell_href(root_surface_id)


def _shell_request_for_slice(
    *,
    slice_id: str,
    portal_tenant_id: str,
    root_tab: str = "",
) -> dict[str, Any]:
    bodies = build_portal_activity_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    request_body = dict(
        bodies.get(
            slice_id,
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": slice_id,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
        )
    )
    if root_tab:
        request_body["root_tab"] = root_tab
    return request_body


def _build_root_tabs(
    *,
    root_surface_id: str,
    portal_tenant_id: str,
    active_root_tab: str,
    tab_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    tabs: list[dict[str, Any]] = []
    for tab_id in tab_ids:
        tabs.append(
            {
                "tab_id": tab_id,
                "label": _root_tab_label(tab_id),
                "active": tab_id == active_root_tab,
                "href": _root_tab_path(root_surface_id, tab_id),
                "shell_request": _shell_request_for_slice(
                    slice_id=root_surface_id,
                    portal_tenant_id=portal_tenant_id,
                    root_tab=tab_id,
                ),
            }
        )
    return tabs


def _runtime_tool_entries(
    *,
    tool_exposure_policy: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    policy = _resolved_tool_exposure_policy(tool_exposure_policy)
    rows: list[dict[str, Any]] = []
    for entry in build_admin_tool_registry_entries():
        config_enabled = admin_tool_exposure_config_enabled(policy, tool_id=entry.tool_id)
        activity_bar_visible = bool(entry.to_dict().get("activity_bar_visible", True))
        promoted_tool = entry.tool_id == "aws"
        family_subsurface = entry.tool_id in {"aws_narrow_write", "aws_csm_onboarding", "aws_csm_sandbox"}
        visible_in_activity_bar = bool(entry.launchable and config_enabled and activity_bar_visible and promoted_tool)
        if not entry.launchable:
            visibility_status = "shell_gated"
        elif not config_enabled:
            visibility_status = "config_disabled"
        elif promoted_tool and activity_bar_visible:
            visibility_status = "principal_activity"
        elif family_subsurface:
            visibility_status = "family_subsurface"
        else:
            visibility_status = "utility_tool"
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
        return "/portal/utilities?tab=tools"
    if slice_id == DATUM_RESOURCE_WORKBENCH_SLICE_ID:
        return "/portal/system?tab=sources"
    if slice_id == AWS_READ_ONLY_SLICE_ID:
        return "/portal/utilities/aws-csm"
    if slice_id == AWS_NARROW_WRITE_SLICE_ID:
        return "/portal/utilities/aws-write"
    if slice_id == AWS_CSM_ONBOARDING_SLICE_ID:
        return "/portal/utilities/aws-csm-onboarding"
    if slice_id == AWS_CSM_SANDBOX_SLICE_ID:
        return "/portal/utilities/aws-csm-sandbox"
    if slice_id == CTS_GIS_READ_ONLY_SLICE_ID:
        return "/portal/utilities/cts-gis"
    if slice_id == FND_EBI_READ_ONLY_SLICE_ID:
        return "/portal/utilities/fnd-ebi"
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
    portal_tenant_id: str,
    data_dir: str | Path | None = None,
    root_tab: str = "home",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface_catalog = [entry.to_dict() for entry in build_admin_surface_catalog()]
    tool_entries = _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
    launchable_tool_slice_ids = [
        entry["slice_id"]
        for entry in tool_entries
        if entry["visibility_status"] in {"principal_activity", "utility_tool"}
    ]
    gated_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["visibility_status"] == "config_disabled"]
    available_tool_slices = [
        entry for entry in tool_entries if entry["visibility_status"] in {"principal_activity", "utility_tool"}
    ]
    family_tool_slices = [entry for entry in tool_entries if entry["visibility_status"] == "family_subsurface"]
    gated_tool_slices = [entry for entry in tool_entries if entry["visibility_status"] == "config_disabled"]
    selected_document = {}
    source_documents: list[dict[str, Any]] = []
    sandbox_documents: list[dict[str, Any]] = []
    warnings: list[str] = []
    row_count = 0
    document_count = 0
    if data_dir is not None and root_tab in {"sources", "sandbox"}:
        dd = DatumWorkbenchService(FilesystemSystemDatumStoreAdapter(Path(data_dir))).read_workbench(portal_tenant_id).to_dict()
        document_count = int(dd.get("document_count") or 0)
        row_count = int(dd.get("row_count") or 0)
        warnings = list(dd.get("warnings") or [])
        all_documents = list(dd.get("documents") or [])
        source_documents = [document for document in all_documents if _as_text(document.get("source_kind")) != "sandbox_source"]
        sandbox_documents = [document for document in all_documents if _as_text(document.get("source_kind")) == "sandbox_source"]
        selected_document = dict(dd.get("selected_document") or {})

    return {
        "schema": ADMIN_HOME_STATUS_SURFACE_SCHEMA,
        "active_surface_id": ADMIN_HOME_STATUS_SLICE_ID,
        "root_tab": root_tab,
        "root_tabs": _build_root_tabs(
            root_surface_id=ADMIN_HOME_STATUS_SLICE_ID,
            portal_tenant_id=portal_tenant_id,
            active_root_tab=root_tab,
            tab_ids=SYSTEM_ROOT_TABS,
        ),
        "current_admin_band": ADMIN_BAND0_NAME,
        "exposure_posture": ADMIN_EXPOSURE_INTERNAL_ONLY,
        "available_admin_slices": surface_catalog,
        "available_tool_slices": available_tool_slices,
        "family_tool_slices": family_tool_slices,
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
            "next_tool_slice_id": (
                FND_EBI_READ_ONLY_SLICE_ID
                if FND_EBI_READ_ONLY_SLICE_ID in launchable_tool_slice_ids
                else CTS_GIS_READ_ONLY_SLICE_ID
                if CTS_GIS_READ_ONLY_SLICE_ID in launchable_tool_slice_ids
                else AWS_READ_ONLY_SLICE_ID
            ),
        },
        "sources_summary": {
            "document_count": document_count,
            "row_count": row_count,
            "selected_document": selected_document,
            "documents": source_documents,
            "warnings": warnings,
        },
        "sandbox_summary": {
            "document_count": len(sandbox_documents),
            "documents": sandbox_documents,
            "warnings": warnings,
        },
        "follow_on_order": [
            FND_EBI_READ_ONLY_SLICE_ID,
            CTS_GIS_READ_ONLY_SLICE_ID,
            "agro_erp_after_cts_gis",
        ],
    }


def _build_tool_registry_surface(
    *,
    portal_tenant_id: str,
    root_tab: str = "tools",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface_catalog = [entry.to_dict() for entry in build_admin_surface_catalog()]
    tool_entries = _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
    launchable_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["launchable"]]
    visible_tool_slice_ids = [
        entry["slice_id"] for entry in tool_entries if entry["visibility_status"] in {"principal_activity", "utility_tool"}
    ]
    gated_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["visibility_status"] == "config_disabled"]

    return {
        "schema": ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA,
        "active_surface_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
        "portal_tenant_id": portal_tenant_id,
        "root_tab": root_tab,
        "root_tabs": _build_root_tabs(
            root_surface_id=ADMIN_TOOL_REGISTRY_SLICE_ID,
            portal_tenant_id=portal_tenant_id,
            active_root_tab=root_tab,
            tab_ids=UTILITIES_ROOT_TABS,
        ),
        "registry_owner": "shell",
        "default_posture": "deny-by-default",
        "launchable_admin_slice_ids": [entry["slice_id"] for entry in surface_catalog if entry["launchable"]],
        "launchable_tool_slice_ids": launchable_tool_slice_ids,
        "visible_tool_slice_ids": visible_tool_slice_ids,
        "gated_tool_slice_ids": gated_tool_slice_ids,
        "tool_entries": tool_entries,
        "tool_exposure": _tool_exposure_summary(tool_exposure_policy),
        "config_sections": [
            {
                "label": "Tool exposure",
                "value": ", ".join(_tool_exposure_summary(tool_exposure_policy).get("enabled_tool_ids") or []) or "None",
            },
            {
                "label": "Disabled tools",
                "value": ", ".join(_tool_exposure_summary(tool_exposure_policy).get("disabled_tool_ids") or []) or "None",
            },
        ],
        "vault_summary": {
            "mode": "inventory_placeholder",
            "notes": [
                "Vault work stays under Utilities as a bounded follow-on surface.",
                "This pass keeps the shell contract ready without reviving legacy utility pages.",
            ],
        },
        "follow_on_constraints": {
            "fnd_ebi": "implemented_read_only",
            "cts_gis": "implemented_read_only",
            "agro_erp": "blocked_until_cts_gis",
        },
    }


def _build_network_root_surface(
    *,
    portal_tenant_id: str,
    root_tab: str = "messages",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_summary = _tool_exposure_summary(tool_exposure_policy)
    visible_utility_count = len(
        [
            entry
            for entry in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
            if entry["visibility_status"] in {"principal_activity", "utility_tool"}
        ]
    )
    return {
        "schema": ADMIN_NETWORK_ROOT_SURFACE_SCHEMA,
        "active_surface_id": ADMIN_NETWORK_ROOT_SLICE_ID,
        "root_tab": root_tab,
        "root_tabs": _build_root_tabs(
            root_surface_id=ADMIN_NETWORK_ROOT_SLICE_ID,
            portal_tenant_id=portal_tenant_id,
            active_root_tab=root_tab,
            tab_ids=NETWORK_ROOT_TABS,
        ),
        "network_state": "lightweight_placeholder",
        "summary": {
            "hosted_root": "contracts_first",
            "tool_visibility_source": tool_summary.get("policy_source") or "runtime_default_allow_all",
            "visible_utility_count": visible_utility_count,
        },
        "blocks": [
            {"kind": "metric", "label": "Hosted root", "value": "contracts-first"},
            {"kind": "metric", "label": "Visible utilities", "value": str(visible_utility_count)},
            {"kind": "metric", "label": "P2P/MSS split", "value": "contract-first"},
        ],
        "notes": [
            "Network is now a first-class shell root and remains intentionally lightweight in this pass.",
            "No hosted or host-alias runtimes are loaded here until the hosted/network contracts are approved.",
            "P2P authority, MSS projection, request-log evidence, and local audit stay separated by contract in this phase.",
            "System remains the default core root; utility tools continue to launch only when explicitly selected.",
        ],
        "tab_panels": {
            "messages": {
                "title": "Messages",
                "summary": "Message operations remain lightweight until the hosted/network contract set is implemented.",
            },
            "hosted": {
                "title": "Hosted",
                "summary": "Hosted views stay contract-first here; portal instances and host aliases are not runtime-loaded yet.",
            },
            "profile": {
                "title": "Profile",
                "summary": "Alias/profile projection stays distinct from provider truth and runtime ownership.",
            },
            "contracts": {
                "title": "Contracts",
                "summary": "P2P contracts, progeny links, request evidence, and local audit are sequenced here before implementation.",
            },
        },
    }


def _select_band0_surface_payload(
    *,
    active_surface_id: str,
    portal_tenant_id: str,
    audit_storage_file: str | Path | None,
    data_dir: str | Path | None = None,
    root_tab: str = "",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if active_surface_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return _build_network_root_surface(
            portal_tenant_id=portal_tenant_id,
            root_tab=_normalize_root_tab(active_surface_id, root_tab),
            tool_exposure_policy=tool_exposure_policy,
        )
    if active_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return _build_tool_registry_surface(
            portal_tenant_id=portal_tenant_id,
            root_tab=_normalize_root_tab(active_surface_id, root_tab),
            tool_exposure_policy=tool_exposure_policy,
        )
    return _build_home_status_surface(
        audit_storage_file=audit_storage_file,
        portal_tenant_id=portal_tenant_id,
        data_dir=data_dir,
        root_tab=_normalize_root_tab(active_surface_id, root_tab),
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
            "label": "Portal",
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


def _compact_document_entries(documents: list[dict[str, Any]], *, max_items: int = 18) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for document in list(documents or [])[:max_items]:
        entries.append(
            {
                "label": _as_text(document.get("document_name")) or "document",
                "meta": _as_text(document.get("anchor_document_name")) or _as_text(document.get("source_kind")) or "—",
                "active": bool(document.get("selected")),
            }
        )
    return entries


def _control_panel_region(
    *,
    portal_tenant_id: str,
    nav_active_slice_id: str,
    surface_payload: dict[str, Any] | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sp = surface_payload or {}
    tool_entries = _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
    if nav_active_slice_id in {
        AWS_READ_ONLY_SLICE_ID,
        AWS_NARROW_WRITE_SLICE_ID,
        AWS_CSM_SANDBOX_SLICE_ID,
        AWS_CSM_ONBOARDING_SLICE_ID,
    }:
        domain_states = list(sp.get("domain_states") or [])
        selected_domain_state = dict(sp.get("selected_domain_state") or {})
        selected_author = dict(selected_domain_state.get("selected_author") or {})
        subsurface_navigation = dict(sp.get("subsurface_navigation") or {})
        sections = [
            {
                "title": "Family navigation",
                "entries": [
                    {
                        "label": "AWS-CSM overview",
                        "meta": "family landing",
                        "active": nav_active_slice_id == AWS_READ_ONLY_SLICE_ID,
                        "shell_request": _shell_request_for_slice(slice_id=AWS_READ_ONLY_SLICE_ID, portal_tenant_id=portal_tenant_id),
                        "href": _canonical_shell_href(AWS_READ_ONLY_SLICE_ID),
                    },
                    {
                        "label": "Sender selection",
                        "meta": "bounded write",
                        "active": nav_active_slice_id == AWS_NARROW_WRITE_SLICE_ID,
                        "shell_request": subsurface_navigation.get("narrow_write_shell_request")
                        or _shell_request_for_slice(slice_id=AWS_NARROW_WRITE_SLICE_ID, portal_tenant_id=portal_tenant_id),
                        "href": _canonical_shell_href(AWS_NARROW_WRITE_SLICE_ID),
                    },
                    {
                        "label": "Mailbox onboarding",
                        "meta": "workflow",
                        "active": nav_active_slice_id == AWS_CSM_ONBOARDING_SLICE_ID,
                        "shell_request": subsurface_navigation.get("onboarding_shell_request")
                        or _shell_request_for_slice(slice_id=AWS_CSM_ONBOARDING_SLICE_ID, portal_tenant_id=portal_tenant_id),
                        "href": _canonical_shell_href(AWS_CSM_ONBOARDING_SLICE_ID),
                    },
                ],
            },
            {
                "title": "Domain groups",
                "entries": [
                    {
                        "label": _as_text(state.get("domain")) or "domain",
                        "meta": _as_text(((state.get("selected_author") or {}) if isinstance(state.get("selected_author"), dict) else {}).get("address"))
                        or _as_text(state.get("dispatch_state"))
                        or "family state",
                        "active": _as_text(state.get("domain")) == _as_text(selected_domain_state.get("domain")),
                    }
                    for state in domain_states
                ]
                or [
                    {
                        "label": "No domain groups",
                        "meta": "Newsletter family state is not configured for this instance.",
                        "active": True,
                    }
                ],
            },
        ]
        if selected_domain_state:
            sections.append(
                {
                    "title": "Selected author",
                    "entries": [
                        {
                            "label": _as_text(selected_author.get("address")) or "No selected author",
                            "meta": _as_text(selected_author.get("profile_id")) or _as_text(selected_domain_state.get("inbound_state")) or "—",
                            "active": True,
                        }
                    ],
                }
            )
        return {
            "schema": ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
            "kind": "aws_csm_control_panel",
            "title": "AWS-CSM",
            "tabs": [],
            "sections": sections,
        }

    if nav_active_slice_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return {
            "schema": ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
            "kind": "network_control_panel",
            "title": "NETWORK",
            "tabs": list(sp.get("root_tabs") or []),
            "sections": [
                {
                    "title": "Current root",
                    "entries": [
                        {
                            "label": _root_tab_label(sp.get("root_tab") or "messages"),
                            "meta": _as_text((((sp.get("tab_panels") or {}).get(sp.get("root_tab") or "messages")) or {}).get("summary"))
                            or "Placeholder network surface",
                            "active": True,
                        }
                    ],
                }
            ],
        }

    if nav_active_slice_id in {ADMIN_HOME_STATUS_SLICE_ID, DATUM_RESOURCE_WORKBENCH_SLICE_ID}:
        source_summary = dict(sp.get("sources_summary") or {})
        sandbox_summary = dict(sp.get("sandbox_summary") or {})
        active_tab = _as_text(sp.get("root_tab")) or ("sources" if nav_active_slice_id == DATUM_RESOURCE_WORKBENCH_SLICE_ID else "home")
        root_tabs = list(sp.get("root_tabs") or []) or _build_root_tabs(
            root_surface_id=ADMIN_HOME_STATUS_SLICE_ID,
            portal_tenant_id=portal_tenant_id,
            active_root_tab=active_tab,
            tab_ids=SYSTEM_ROOT_TABS,
        )
        system_sections = [
            {
                "title": "System context",
                "entries": [
                    {
                        "label": "Default core sandbox",
                        "meta": "SYSTEM owns the datum-facing workbench and source tabs.",
                        "active": nav_active_slice_id == ADMIN_HOME_STATUS_SLICE_ID and active_tab == "home",
                    }
                ],
            }
        ]
        if active_tab == "sources":
            system_sections.append(
                {
                    "title": "Authoritative sources",
                    "entries": _compact_document_entries(list(source_summary.get("documents") or []))
                    or [{"label": "No source documents", "meta": "No authoritative source documents are available.", "active": True}],
                }
            )
        elif active_tab == "sandbox":
            system_sections.append(
                {
                    "title": "Sandbox documents",
                    "entries": _compact_document_entries(list(sandbox_summary.get("documents") or []))
                    or [{"label": "No sandbox documents", "meta": "No sandbox source documents are available.", "active": True}],
                }
            )
        else:
            system_sections.append(
                {
                    "title": "Workbench",
                    "entries": [
                        {
                            "label": "Home and status",
                            "meta": "Primary system workbench.",
                            "active": True,
                            "shell_request": _shell_request_for_slice(
                                slice_id=ADMIN_HOME_STATUS_SLICE_ID,
                                portal_tenant_id=portal_tenant_id,
                                root_tab="home",
                            ),
                            "href": _root_tab_path(ADMIN_HOME_STATUS_SLICE_ID, "home"),
                        }
                    ],
                }
            )
        return {
            "schema": ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
            "kind": "system_control_panel",
            "title": "SYSTEM",
            "tabs": root_tabs,
            "sections": system_sections,
        }

    visible_utility_rows = [
        entry for entry in tool_entries if entry["visibility_status"] in {"principal_activity", "utility_tool"}
    ]
    utility_sections: list[dict[str, Any]] = []
    active_tab = _as_text(sp.get("root_tab")) or "tools"
    if active_tab == "config":
        utility_sections.append(
            {
                "title": "Tool exposure",
                "entries": [
                    {
                        "label": _as_text(section.get("label")) or "Config",
                        "meta": _as_text(section.get("value")) or "—",
                        "active": index == 0,
                    }
                    for index, section in enumerate(list(sp.get("config_sections") or []))
                ],
            }
        )
    elif active_tab == "vault":
        utility_sections.append(
            {
                "title": "Vault",
                "entries": [
                    {
                        "label": "Inventory placeholder",
                        "meta": warning,
                        "active": index == 0,
                    }
                    for index, warning in enumerate(list(((sp.get("vault_summary") or {}).get("notes")) or []))
                ]
                or [{"label": "Inventory placeholder", "meta": "Vault follow-on surface pending.", "active": True}],
            }
        )
    else:
        utility_sections.append(
            {
                "title": "Tools",
                "entries": [
                    {
                        "label": _as_text(row.get("label")) or "tool",
                        "meta": _as_text(row.get("entrypoint_id")) or _as_text(row.get("visibility_status")) or "—",
                        "active": _as_text(row.get("slice_id")) == nav_active_slice_id,
                        "shell_request": _shell_request_for_slice(
                            slice_id=_as_text(row.get("slice_id")),
                            portal_tenant_id=portal_tenant_id,
                        ),
                        "href": _canonical_shell_href(_as_text(row.get("slice_id"))),
                    }
                    for row in visible_utility_rows
                ]
                or [{"label": "No tools", "meta": "No utility tools are enabled for this instance.", "active": True}],
            }
        )
    return {
        "schema": ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "utilities_control_panel",
        "title": "UTILITIES",
        "tabs": list(sp.get("root_tabs") or [])
        or _build_root_tabs(
            root_surface_id=ADMIN_TOOL_REGISTRY_SLICE_ID,
            portal_tenant_id=portal_tenant_id,
            active_root_tab=active_tab,
            tab_ids=UTILITIES_ROOT_TABS,
        ),
        "sections": utility_sections,
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
        "kind": "system_root",
        "title": "System",
        "subtitle": "Default core root",
        "visible": True,
        "root_tab": _as_text(sp.get("root_tab")) or "home",
        "root_tabs": list(sp.get("root_tabs") or []),
        "blocks": blocks,
        "notes": notes,
        "sources_summary": dict(sp.get("sources_summary") or {}),
        "sandbox_summary": dict(sp.get("sandbox_summary") or {}),
    }


def _workbench_registry(*, surface_payload: dict[str, Any] | None) -> dict[str, Any]:
    sp = surface_payload or {}
    portal_tenant_id = _as_text(sp.get("portal_tenant_id")) or "fnd"
    rows = []
    for row in list(sp.get("tool_entries") or []):
        next_row = dict(row)
        slice_id = _as_text(next_row.get("slice_id"))
        if slice_id:
            next_row["shell_request"] = _shell_request_for_slice(
                slice_id=slice_id,
                portal_tenant_id=portal_tenant_id,
            )
            next_row["href"] = _canonical_shell_href(slice_id)
        rows.append(next_row)
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "utilities_root",
        "title": "Utilities",
        "subtitle": "Tool launcher and utility surfaces",
        "visible": True,
        "root_tab": _as_text(sp.get("root_tab")) or "tools",
        "root_tabs": list(sp.get("root_tabs") or []),
        "tool_rows": rows,
        "config_sections": list(sp.get("config_sections") or []),
        "vault_summary": dict(sp.get("vault_summary") or {}),
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
        "root_tab": _as_text(sp.get("root_tab")) or "messages",
        "root_tabs": list(sp.get("root_tabs") or []),
        "blocks": list(sp.get("blocks") or []),
        "notes": list(notes),
        "tab_panels": dict(sp.get("tab_panels") or {}),
    }


def _workbench_aws_csm_family(*, surface_payload: dict[str, Any] | None) -> dict[str, Any]:
    sp = surface_payload or {}
    family_health = dict(sp.get("family_health") or {})
    selected_domain_state = dict(sp.get("selected_domain_state") or {})
    selected_author = dict(selected_domain_state.get("selected_author") or {})
    domain_states = list(sp.get("domain_states") or [])
    selected_navigation = dict(sp.get("subsurface_navigation") or {})
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "aws_csm_family_workbench",
        "title": "AWS-CSM",
        "subtitle": "Unified family landing",
        "visible": True,
        "family_health": family_health,
        "selected_domain_state": selected_domain_state,
        "selected_author": selected_author,
        "domain_states": domain_states,
        "subsurface_navigation": selected_navigation,
        "gated_subsurfaces": dict(sp.get("gated_subsurfaces") or {}),
    }


def _workbench_aws_subsurface(
    *,
    title: str,
    subtitle: str,
    mode: str,
    read_only_document: dict[str, Any] | None,
    help_text: str,
    submit_route: str,
) -> dict[str, Any]:
    preview = read_only_document or {}
    profile = dict(preview.get("canonical_newsletter_operational_profile") or {})
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "aws_csm_subsurface_workbench",
        "title": title,
        "subtitle": subtitle,
        "visible": True,
        "mode": mode,
        "help_text": help_text,
        "submit_route": submit_route,
        "selected_verified_sender": _as_text(preview.get("selected_verified_sender")),
        "mailbox_readiness": _as_text(preview.get("mailbox_readiness")),
        "smtp_state": _as_text(preview.get("smtp_state")),
        "gmail_state": _as_text(preview.get("gmail_state")),
        "verified_evidence_state": _as_text(preview.get("verified_evidence_state")),
        "profile_summary": {
            "profile_id": _as_text(profile.get("profile_id")),
            "domain": _as_text(profile.get("domain")),
            "list_address": _as_text(profile.get("list_address")),
            "delivery_mode": _as_text(profile.get("delivery_mode")),
        },
        "compatibility_warnings": list(preview.get("compatibility_warnings") or []),
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
    if chrome.inspector_collapsed is not None:
        composition["inspector_collapsed"] = bool(chrome.inspector_collapsed)


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
    portal_domain: str,
    audit_storage_file: str | Path | None,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
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
                portal_tenant_id=portal_tenant_id,
                root_tab=normalized_request.root_tab,
                tool_exposure_policy=tool_exposure_policy,
            )
        elif normalized_request.tenant_scope.audience == "internal" and selection.active_surface_id in {
            ADMIN_HOME_STATUS_SLICE_ID,
            AWS_CSM_SANDBOX_SLICE_ID,
            CTS_GIS_READ_ONLY_SLICE_ID,
            FND_EBI_READ_ONLY_SLICE_ID,
        }:
            surface_fallback = _select_band0_surface_payload(
                active_surface_id=selection.active_surface_id,
                audit_storage_file=audit_storage_file,
                portal_tenant_id=portal_tenant_id,
                data_dir=data_dir,
                root_tab=normalized_request.root_tab,
                tool_exposure_policy=tool_exposure_policy,
            )
        if surface_fallback and selection.active_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
            wb = _workbench_registry(surface_payload=surface_fallback)
            wb["banner"] = {"code": selection.reason_code, "message": selection.reason_message}
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
                CTS_GIS_READ_ONLY_SLICE_ID,
                FND_EBI_READ_ONLY_SLICE_ID,
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
                surface_payload=surface_fallback,
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
            portal_tenant_id=portal_tenant_id,
            data_dir=data_dir,
            root_tab=_normalize_root_tab(active, normalized_request.root_tab),
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
                surface_payload=sp,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
            inspector=_inspector_empty(title="System"),
        )
        return sp, comp, "MyCite", "System"

    if active == ADMIN_NETWORK_ROOT_SLICE_ID:
        sp = _build_network_root_surface(
            portal_tenant_id=portal_tenant_id,
            root_tab=_normalize_root_tab(active, normalized_request.root_tab),
            tool_exposure_policy=tool_exposure_policy,
        )
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
                surface_payload=sp,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=_workbench_network(surface_payload=sp),
            inspector=_inspector_network(surface_payload=sp),
        )
        return sp, comp, "MyCite", "Network"

    if active == ADMIN_TOOL_REGISTRY_SLICE_ID:
        sp = _build_tool_registry_surface(
            portal_tenant_id=portal_tenant_id,
            root_tab=_normalize_root_tab(active, normalized_request.root_tab),
            tool_exposure_policy=tool_exposure_policy,
        )
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
                surface_payload=sp,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=_workbench_registry(surface_payload=sp),
            inspector=_inspector_empty(title="Utilities"),
        )
        return sp, comp, "MyCite", "Utilities"

    if active == DATUM_RESOURCE_WORKBENCH_SLICE_ID:
        system_surface = _build_home_status_surface(
            audit_storage_file=audit_storage_file,
            portal_tenant_id=portal_tenant_id,
            data_dir=data_dir,
            root_tab="sources",
            tool_exposure_policy=tool_exposure_policy,
        )
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
                    surface_payload=system_surface,
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
                surface_payload=system_surface,
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
            wb = _workbench_aws_csm_family(surface_payload=sp if isinstance(sp, dict) else {})
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
                surface_payload=sp if isinstance(sp, dict) else None,
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
        wb = _workbench_aws_subsurface(
            title="AWS-CSM Sender Selection",
            subtitle="Bounded write projection",
            mode="narrow_write",
            read_only_document=ro_surface if isinstance(ro_surface, dict) else None,
            help_text="Open the interface panel when you want to submit a sender change.",
            submit_route="/portal/api/v2/admin/aws/narrow-write",
        )
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
                surface_payload=ro_surface if isinstance(ro_surface, dict) else None,
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
        wb = _workbench_aws_subsurface(
            title="AWS-CSM Mailbox Onboarding",
            subtitle="Bounded orchestration projection",
            mode="onboarding",
            read_only_document=ro_surface if isinstance(ro_surface, dict) else None,
            help_text="Open the interface panel when you want to advance onboarding steps.",
            submit_route="/portal/api/v2/admin/aws/csm-onboarding",
        )
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
                surface_payload=ro_surface if isinstance(ro_surface, dict) else None,
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
            wb = _workbench_aws_subsurface(
                title="AWS-CSM Sandbox",
                subtitle="Read-only sandbox profile",
                mode="sandbox",
                read_only_document=sp if isinstance(sp, dict) else None,
                help_text="Sandbox remains a bounded read-only view for this shell.",
                submit_route="",
            )
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
                surface_payload=sp if isinstance(sp, dict) else None,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=wb,
            inspector=ins,
        )
        return sp, comp, "MyCite", "AWS-CSM sandbox"

    if active == CTS_GIS_READ_ONLY_SLICE_ID:
        utilities_surface = _build_tool_registry_surface(
            portal_tenant_id=portal_tenant_id,
            root_tab="tools",
            tool_exposure_policy=tool_exposure_policy,
        )
        if data_dir is None:
            sp = {
                "schema": ADMIN_CTS_GIS_READ_ONLY_SURFACE_SCHEMA,
                "active_surface_id": CTS_GIS_READ_ONLY_SLICE_ID,
                "error": "data_root_not_configured",
            }
            wb = _workbench_error(title="CTS-GIS", message="Host data directory is not configured for the CTS-GIS tool.")
            comp = build_shell_composition_payload(
                active_surface_id=active,
                portal_tenant_id=portal_tenant_id,
                page_title="MyCite",
                page_subtitle="CTS-GIS",
                activity_items=_activity_items(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                control_panel=_control_panel_region(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    surface_payload=utilities_surface,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                workbench=wb,
                inspector=_inspector_empty(title="CTS-GIS"),
            )
            return sp, comp, "MyCite", "CTS-GIS"

        sp = build_admin_cts_gis_surface_payload(
            portal_tenant_id=portal_tenant_id,
            data_dir=data_dir,
        )
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="CTS-GIS",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                surface_payload=utilities_surface,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=build_admin_cts_gis_workbench(
                surface_payload=sp,
                portal_tenant_id=portal_tenant_id,
            ),
            inspector=build_admin_cts_gis_inspector(surface_payload=sp),
        )
        return sp, comp, "MyCite", "CTS-GIS"

    if active == FND_EBI_READ_ONLY_SLICE_ID:
        utilities_surface = _build_tool_registry_surface(
            portal_tenant_id=portal_tenant_id,
            root_tab="tools",
            tool_exposure_policy=tool_exposure_policy,
        )
        if private_dir is None or webapps_root is None:
            sp = {
                "schema": ADMIN_FND_EBI_READ_ONLY_SURFACE_SCHEMA,
                "active_surface_id": FND_EBI_READ_ONLY_SLICE_ID,
                "error": "fnd_ebi_root_not_configured",
            }
            wb = _workbench_error(
                title="FND-EBI",
                message="Host private/tool roots are not configured for the FND-EBI tool.",
            )
            comp = build_shell_composition_payload(
                active_surface_id=active,
                portal_tenant_id=portal_tenant_id,
                page_title="MyCite",
                page_subtitle="FND-EBI",
                activity_items=_activity_items(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                control_panel=_control_panel_region(
                    portal_tenant_id=portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                    surface_payload=utilities_surface,
                    tool_exposure_policy=tool_exposure_policy,
                ),
                workbench=wb,
                inspector=_inspector_empty(title="FND-EBI"),
            )
            return sp, comp, "MyCite", "FND-EBI"

        sp = build_admin_fnd_ebi_surface_payload(
            portal_tenant_id=portal_tenant_id,
            portal_tenant_domain=portal_domain,
            private_dir=private_dir,
            webapps_root=webapps_root,
        )
        comp = build_shell_composition_payload(
            active_surface_id=active,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="FND-EBI",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=nav_active_slice_id,
                surface_payload=utilities_surface,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=build_admin_fnd_ebi_workbench(
                surface_payload=sp,
                portal_tenant_id=portal_tenant_id,
            ),
            inspector=build_admin_fnd_ebi_inspector(surface_payload=sp),
        )
        return sp, comp, "MyCite", "FND-EBI"

    sp = _build_home_status_surface(
        audit_storage_file=audit_storage_file,
        portal_tenant_id=portal_tenant_id,
        data_dir=data_dir,
        root_tab="home",
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
            surface_payload=sp,
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
    portal_domain: str = "",
    aws_status_file: str | Path | None = None,
    aws_csm_sandbox_status_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    private_dir: str | Path | None = None,
    webapps_root: str | Path | None = None,
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
        portal_domain=_as_text(portal_domain).lower(),
        audit_storage_file=audit_storage_file,
        aws_status_file=aws_status_file,
        aws_csm_sandbox_status_file=aws_csm_sandbox_status_file,
        data_dir=data_dir,
        private_dir=private_dir,
        webapps_root=webapps_root,
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
