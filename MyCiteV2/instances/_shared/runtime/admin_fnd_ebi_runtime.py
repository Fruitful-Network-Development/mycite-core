from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemFndEbiReadOnlyAdapter
from MyCiteV2.packages.modules.cross_domain.fnd_ebi import FndEbiReadOnlyService
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND6_FND_EBI_NAME,
    ADMIN_EXPOSURE_INTERNAL_ONLY,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_NETWORK_ROOT_SLICE_ID,
    ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
    ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    DATUM_RESOURCE_WORKBENCH_SLICE_ID,
    FND_EBI_READ_ONLY_ENTRYPOINT_ID,
    FND_EBI_READ_ONLY_SLICE_ID,
    AdminShellChrome,
    AdminTenantScope,
    activity_icon_id_for_slice,
    build_admin_tool_registry_entries,
    build_portal_activity_dispatch_bodies,
    build_shell_composition_payload,
    map_surface_to_active_service,
    resolve_admin_tool_launch,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_FND_EBI_READ_ONLY_SURFACE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    admin_tool_exposure_config_enabled,
    build_admin_runtime_envelope,
    build_admin_runtime_error,
    build_allow_all_admin_tool_exposure_policy,
)

_FND_EBI_SURFACE_CACHE: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _current_year_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def _resolved_tool_exposure_policy(tool_exposure_policy: dict[str, Any] | None) -> dict[str, Any]:
    if tool_exposure_policy is not None:
        return tool_exposure_policy
    return build_allow_all_admin_tool_exposure_policy(
        known_tool_ids=[entry.tool_id for entry in build_admin_tool_registry_entries()]
    )


def _runtime_tool_entries(
    *,
    tool_exposure_policy: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    policy = _resolved_tool_exposure_policy(tool_exposure_policy)
    rows: list[dict[str, Any]] = []
    for entry in build_admin_tool_registry_entries():
        config_enabled = admin_tool_exposure_config_enabled(policy, tool_id=entry.tool_id)
        promoted_tool = entry.tool_id == "aws"
        family_subsurface = entry.tool_id in {"aws_narrow_write", "aws_csm_onboarding", "aws_csm_sandbox"}
        visible_in_activity_bar = bool(entry.launchable and config_enabled and promoted_tool)
        if not entry.launchable:
            visibility_status = "shell_gated"
        elif not config_enabled:
            visibility_status = "config_disabled"
        elif promoted_tool and bool(entry.to_dict().get("activity_bar_visible", True)):
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


def _canonical_shell_href(slice_id: str) -> str:
    if slice_id == ADMIN_HOME_STATUS_SLICE_ID:
        return "/portal/system"
    if slice_id == ADMIN_NETWORK_ROOT_SLICE_ID:
        return "/portal/network"
    if slice_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return "/portal/utilities"
    if slice_id == DATUM_RESOURCE_WORKBENCH_SLICE_ID:
        return "/portal/system/datum"
    if slice_id == FND_EBI_READ_ONLY_SLICE_ID:
        return "/portal/utilities/fnd-ebi"
    return "/portal/system"


def _activity_items(
    *,
    portal_tenant_id: str,
    nav_active_slice_id: str,
    tool_exposure_policy: dict[str, Any] | None,
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


def _control_panel_region(
    *,
    portal_tenant_id: str,
    nav_active_slice_id: str,
    tool_exposure_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    bodies = build_portal_activity_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    utility_entries: list[dict[str, Any]] = []
    for row in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy):
        if row["visibility_status"] not in {"principal_activity", "utility_tool"}:
            continue
        utility_entries.append(
            {
                "label": _as_text(row.get("label")) or "tool",
                "meta": _as_text(row.get("entrypoint_id")) or _as_text(row.get("visibility_status")) or "—",
                "active": _as_text(row.get("slice_id")) == nav_active_slice_id,
                "shell_request": bodies.get(_as_text(row.get("slice_id"))),
                "href": _canonical_shell_href(_as_text(row.get("slice_id"))),
            }
        )
    return {
        "schema": ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "utilities_control_panel",
        "title": "UTILITIES",
        "tabs": [
            {
                "tab_id": "tools",
                "label": "Tools",
                "active": True,
                "href": "/portal/utilities",
                "shell_request": bodies[ADMIN_TOOL_REGISTRY_SLICE_ID],
            },
            {
                "tab_id": "config",
                "label": "Config",
                "active": False,
                "href": "/portal/utilities?tab=config",
                "shell_request": {
                    **bodies[ADMIN_TOOL_REGISTRY_SLICE_ID],
                    "root_tab": "config",
                },
            },
            {
                "tab_id": "vault",
                "label": "Vault",
                "active": False,
                "href": "/portal/utilities?tab=vault",
                "shell_request": {
                    **bodies[ADMIN_TOOL_REGISTRY_SLICE_ID],
                    "root_tab": "vault",
                },
            },
        ],
        "sections": [{"title": "Utilities", "entries": utility_entries}],
    }


def _normalize_request(payload: dict[str, Any] | None) -> tuple[AdminTenantScope, AdminShellChrome, dict[str, Any]]:
    if payload is None:
        raise ValueError("admin.fnd_ebi.read_only requires a request payload")
    if not isinstance(payload, dict):
        raise ValueError("admin.fnd_ebi.read_only request payload must be a dict")
    schema = _as_text(payload.get("schema"))
    if schema != ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA:
        raise ValueError(f"admin.fnd_ebi.read_only request.schema must be {ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA}")
    tenant_scope = AdminTenantScope.from_value(payload.get("tenant_scope"))
    shell_chrome = AdminShellChrome.from_value(
        payload.get("shell_chrome") if isinstance(payload.get("shell_chrome"), dict) else None
    )
    return tenant_scope, shell_chrome, {
        "selected_domain": _as_text(payload.get("selected_domain")).lower(),
        "year_month": _as_text(payload.get("year_month")) or _current_year_month(),
    }


def _tool_not_exposed_shell_state(launch_decision: Any, *, message: str) -> dict[str, Any]:
    shell_state = dict(launch_decision.to_dict())
    shell_state["allowed"] = False
    shell_state["selection_status"] = "gated"
    shell_state["reason_code"] = ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE
    shell_state["reason_message"] = message
    return shell_state


def _config_gate_envelope(
    *,
    tool_exposure_policy: dict[str, Any] | None,
    tenant_scope: AdminTenantScope,
    launch_decision: Any,
) -> dict[str, Any] | None:
    if tool_exposure_policy is None:
        return None
    if admin_tool_exposure_config_enabled(tool_exposure_policy, tool_id="fnd_ebi"):
        return None
    message = "Requested admin tool is disabled by instance tool_exposure configuration."
    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND6_FND_EBI_NAME,
        exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
        slice_id=FND_EBI_READ_ONLY_SLICE_ID,
        entrypoint_id=FND_EBI_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=_tool_not_exposed_shell_state(launch_decision, message=message),
        surface_payload=None,
        warnings=[message],
        error=build_admin_runtime_error(code=ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE, message=message),
    )


def build_admin_fnd_ebi_surface_payload(
    *,
    portal_tenant_id: str,
    portal_tenant_domain: str,
    private_dir: str | Path,
    webapps_root: str | Path,
    selected_domain: object = "",
    year_month: object = "",
) -> dict[str, Any]:
    normalized_year_month = _as_text(year_month) or _current_year_month()
    cache_key = (
        str(Path(private_dir)),
        str(Path(webapps_root)),
        _as_text(portal_tenant_id) or "fnd",
        _as_text(portal_tenant_domain).lower(),
        _as_text(selected_domain).lower(),
        normalized_year_month,
    )
    now = time.time()
    cached = _FND_EBI_SURFACE_CACHE.get(cache_key)
    if cached is not None and (now - float(cached.get("_cached_at_unix") or 0.0)) < 5.0:
        return copy.deepcopy({key: value for key, value in cached.items() if key != "_cached_at_unix"})

    surface_payload = FndEbiReadOnlyService(
        FilesystemFndEbiReadOnlyAdapter(
            private_dir,
            webapps_root=webapps_root,
        )
    ).read_surface(
        portal_tenant_id=portal_tenant_id,
        portal_tenant_domain=portal_tenant_domain,
        selected_domain=selected_domain,
        year_month=normalized_year_month,
    )
    payload = {
        "schema": ADMIN_FND_EBI_READ_ONLY_SURFACE_SCHEMA,
        "active_surface_id": FND_EBI_READ_ONLY_SLICE_ID,
        **surface_payload,
    }
    _FND_EBI_SURFACE_CACHE[cache_key] = copy.deepcopy({**payload, "_cached_at_unix": now})
    return payload


def build_admin_fnd_ebi_workbench(
    *,
    surface_payload: dict[str, Any],
    portal_tenant_id: str,
) -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "fnd_ebi_workbench",
        "title": "FND-EBI",
        "profile_cards": list(surface_payload.get("profile_cards") or []),
        "overview": dict(surface_payload.get("overview") or {}),
        "traffic": dict(surface_payload.get("traffic") or {}),
        "events_summary": dict(surface_payload.get("events_summary") or {}),
        "errors_noise": dict(surface_payload.get("errors_noise") or {}),
        "files": dict(surface_payload.get("files") or {}),
        "selected_profile": dict(surface_payload.get("selected_profile") or {}),
        "warnings": list(surface_payload.get("warnings") or []),
        "request_contract": {
            "request_schema": ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA,
            "route": "/portal/api/v2/admin/fnd-ebi/read-only",
            "fixed_request_fields": {
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
        },
    }


def build_admin_fnd_ebi_inspector(*, surface_payload: dict[str, Any]) -> dict[str, Any]:
    overview = dict(surface_payload.get("overview") or {})
    files = dict(surface_payload.get("files") or {})
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "fnd_ebi_summary",
        "title": "FND-EBI Summary",
        "summary": {
            "domain": _as_text(overview.get("domain")),
            "health_label": _as_text(overview.get("health_label")) or "unavailable",
            "year_month": _as_text(overview.get("year_month")),
            "access_state": _as_text((files.get("access_log") or {}).get("state")),
            "events_state": _as_text((files.get("events_file") or {}).get("state")),
        },
        "selected_profile": dict(surface_payload.get("selected_profile") or {}),
        "warnings": list(surface_payload.get("warnings") or []),
    }


def run_admin_fnd_ebi_read_only(
    payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    portal_tenant_id: str,
    portal_tenant_domain: str = "",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_scope, shell_chrome, request_args = _normalize_request(payload)
    launch_decision = resolve_admin_tool_launch(
        slice_id=FND_EBI_READ_ONLY_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=FND_EBI_READ_ONLY_ENTRYPOINT_ID,
    )
    if not launch_decision.allowed:
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND6_FND_EBI_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
            slice_id=FND_EBI_READ_ONLY_SLICE_ID,
            entrypoint_id=FND_EBI_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[launch_decision.reason_message] if launch_decision.reason_message else [],
            error=build_admin_runtime_error(
                code=launch_decision.reason_code or "tool_launch_denied",
                message=launch_decision.reason_message or "Shell registry denied this tool launch.",
            ),
        )

    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tenant_scope=tenant_scope,
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated

    if private_dir is None or webapps_root is None:
        message = "Host private/tool roots are not configured for the FND-EBI tool."
        workbench = {
            "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
            "kind": "fnd_ebi_workbench",
            "title": "FND-EBI",
            "warnings": [message],
        }
        composition = build_shell_composition_payload(
            active_surface_id=FND_EBI_READ_ONLY_SLICE_ID,
            portal_tenant_id=portal_tenant_id,
            page_title="MyCite",
            page_subtitle="FND-EBI",
            activity_items=_activity_items(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
                tool_exposure_policy=tool_exposure_policy,
            ),
            control_panel=_control_panel_region(
                portal_tenant_id=portal_tenant_id,
                nav_active_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
                tool_exposure_policy=tool_exposure_policy,
            ),
            workbench=workbench,
            inspector={
                "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
                "kind": "fnd_ebi_summary",
                "title": "FND-EBI Summary",
                "warnings": [message],
            },
            control_panel_collapsed=bool(shell_chrome.control_panel_collapsed),
        )
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND6_FND_EBI_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
            slice_id=FND_EBI_READ_ONLY_SLICE_ID,
            entrypoint_id=FND_EBI_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload={
                "schema": ADMIN_FND_EBI_READ_ONLY_SURFACE_SCHEMA,
                "active_surface_id": FND_EBI_READ_ONLY_SLICE_ID,
                "error": "fnd_ebi_root_not_configured",
            },
            shell_composition=composition,
            warnings=[message],
            error=build_admin_runtime_error(code="fnd_ebi_root_not_configured", message=message),
        )

    surface_payload = build_admin_fnd_ebi_surface_payload(
        portal_tenant_id=portal_tenant_id,
        portal_tenant_domain=portal_tenant_domain,
        private_dir=private_dir,
        webapps_root=webapps_root,
        selected_domain=request_args["selected_domain"],
        year_month=request_args["year_month"],
    )
    composition = build_shell_composition_payload(
        active_surface_id=FND_EBI_READ_ONLY_SLICE_ID,
        portal_tenant_id=portal_tenant_id,
        page_title="MyCite",
        page_subtitle="FND-EBI",
        activity_items=_activity_items(
            portal_tenant_id=portal_tenant_id,
            nav_active_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
            tool_exposure_policy=tool_exposure_policy,
        ),
        control_panel=_control_panel_region(
            portal_tenant_id=portal_tenant_id,
            nav_active_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
            tool_exposure_policy=tool_exposure_policy,
        ),
        workbench=build_admin_fnd_ebi_workbench(
            surface_payload=surface_payload,
            portal_tenant_id=portal_tenant_id,
        ),
        inspector=build_admin_fnd_ebi_inspector(surface_payload=surface_payload),
        control_panel_collapsed=bool(shell_chrome.control_panel_collapsed),
    )
    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND6_FND_EBI_NAME,
        exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=FND_EBI_READ_ONLY_SLICE_ID,
        slice_id=FND_EBI_READ_ONLY_SLICE_ID,
        entrypoint_id=FND_EBI_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=launch_decision.to_dict(),
        surface_payload=surface_payload,
        shell_composition=composition,
        warnings=list(surface_payload.get("warnings") or []),
        error=None,
    )


__all__ = [
    "build_admin_fnd_ebi_inspector",
    "build_admin_fnd_ebi_surface_payload",
    "build_admin_fnd_ebi_workbench",
    "run_admin_fnd_ebi_read_only",
]
