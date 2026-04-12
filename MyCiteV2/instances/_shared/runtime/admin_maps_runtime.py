from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.maps import MapsReadOnlyService
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND5_MAPS_NAME,
    ADMIN_EXPOSURE_INTERNAL_ONLY,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
    ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    DATUM_RESOURCE_WORKBENCH_SLICE_ID,
    MAPS_READ_ONLY_ENTRYPOINT_ID,
    MAPS_READ_ONLY_SLICE_ID,
    AdminShellChrome,
    AdminTenantScope,
    build_admin_surface_catalog,
    build_admin_tool_registry_entries,
    build_portal_activity_dispatch_bodies,
    build_shell_composition_payload,
    resolve_admin_tool_launch,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_MAPS_READ_ONLY_SURFACE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    admin_tool_exposure_config_enabled,
    build_admin_runtime_envelope,
    build_admin_runtime_error,
    build_allow_all_admin_tool_exposure_policy,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


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
        visible_in_activity_bar = bool(entry.launchable and config_enabled)
        if not entry.launchable:
            visibility_status = "shell_gated"
        elif config_enabled:
            visibility_status = "visible"
        else:
            visibility_status = "config_disabled"
        row = entry.to_dict()
        row["config_enabled"] = config_enabled
        row["visibility_status"] = visibility_status
        row["visible_in_activity_bar"] = visible_in_activity_bar
        rows.append(row)
    return rows


def _activity_items(
    *,
    portal_tenant_id: str,
    nav_active_slice_id: str,
    tool_exposure_policy: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    bodies = build_portal_activity_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    visible_tool_slice_ids = {
        entry["slice_id"]
        for entry in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
        if entry["visible_in_activity_bar"]
    }
    items: list[dict[str, Any]] = []
    for entry in build_admin_surface_catalog():
        if not entry.launchable or entry.slice_id not in bodies:
            continue
        items.append(
            {
                "slice_id": entry.slice_id,
                "label": entry.label,
                "active": entry.slice_id == nav_active_slice_id,
                "shell_request": bodies[entry.slice_id],
            }
        )
    for tool in build_admin_tool_registry_entries():
        if not tool.launchable or tool.slice_id not in bodies or tool.slice_id not in visible_tool_slice_ids:
            continue
        items.append(
            {
                "slice_id": tool.slice_id,
                "label": tool.label,
                "active": tool.slice_id == nav_active_slice_id,
                "shell_request": bodies[tool.slice_id],
                "entrypoint_id": tool.entrypoint_id,
                "read_write_posture": tool.read_write_posture,
            }
        )
    items.append(
        {
            "slice_id": DATUM_RESOURCE_WORKBENCH_SLICE_ID,
            "label": "Resource workbench",
            "active": DATUM_RESOURCE_WORKBENCH_SLICE_ID == nav_active_slice_id,
            "shell_request": bodies[DATUM_RESOURCE_WORKBENCH_SLICE_ID],
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
    visible_tool_rows = {
        entry["slice_id"]: entry
        for entry in _runtime_tool_entries(tool_exposure_policy=tool_exposure_policy)
        if entry["visible_in_activity_bar"]
    }
    surface_entries: list[dict[str, Any]] = []
    for entry in build_admin_surface_catalog():
        if not entry.launchable:
            continue
        surface_entries.append(
            {
                "label": entry.label,
                "meta": entry.slice_id,
                "active": entry.slice_id == nav_active_slice_id,
                "shell_request": bodies[entry.slice_id],
            }
        )
    tool_entries: list[dict[str, Any]] = []
    for tool in build_admin_tool_registry_entries():
        if tool.slice_id not in visible_tool_rows:
            continue
        tool_entries.append(
            {
                "label": tool.label,
                "meta": tool.entrypoint_id,
                "active": tool.slice_id == nav_active_slice_id,
                "shell_request": bodies.get(tool.slice_id),
            }
        )
    return {
        "schema": ADMIN_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "sections": [
            {"title": "Admin surfaces", "entries": surface_entries},
            {"title": "Shell-registered tools", "entries": tool_entries},
            {
                "title": "Datum",
                "entries": [
                    {
                        "label": "Resource workbench",
                        "meta": DATUM_RESOURCE_WORKBENCH_SLICE_ID,
                        "active": nav_active_slice_id == DATUM_RESOURCE_WORKBENCH_SLICE_ID,
                        "shell_request": bodies[DATUM_RESOURCE_WORKBENCH_SLICE_ID],
                    }
                ],
            },
        ],
    }


def _normalize_request(
    payload: dict[str, Any] | None,
) -> tuple[AdminTenantScope, AdminShellChrome, dict[str, Any]]:
    if payload is None:
        raise ValueError("admin.maps.read_only requires a request payload")
    if not isinstance(payload, dict):
        raise ValueError("admin.maps.read_only request payload must be a dict")
    schema = _as_text(payload.get("schema"))
    if schema != ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA:
        raise ValueError(f"admin.maps.read_only request.schema must be {ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA}")
    tenant_scope = AdminTenantScope.from_value(payload.get("tenant_scope"))
    shell_chrome = AdminShellChrome.from_value(
        payload.get("shell_chrome") if isinstance(payload.get("shell_chrome"), dict) else None
    )
    overlay_mode = _as_text(payload.get("overlay_mode") or "auto").lower()
    if overlay_mode not in {"auto", "raw_only"}:
        raise ValueError("admin.maps.read_only overlay_mode must be auto or raw_only")
    raw_underlay_visible = payload.get("raw_underlay_visible")
    if raw_underlay_visible is not None and not isinstance(raw_underlay_visible, bool):
        raise ValueError("admin.maps.read_only raw_underlay_visible must be a bool or null")
    return tenant_scope, shell_chrome, {
        "selected_document_id": _as_text(payload.get("selected_document_id")),
        "selected_row_address": _as_text(payload.get("selected_row_address")),
        "selected_feature_id": _as_text(payload.get("selected_feature_id")),
        "overlay_mode": overlay_mode,
        "raw_underlay_visible": bool(raw_underlay_visible) if raw_underlay_visible is not None else False,
    }


def _tool_not_exposed_shell_state(
    launch_decision: Any,
    *,
    message: str,
) -> dict[str, Any]:
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
    if admin_tool_exposure_config_enabled(tool_exposure_policy, tool_id="maps"):
        return None
    message = "Requested admin tool is disabled by instance tool_exposure configuration."
    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND5_MAPS_NAME,
        exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=MAPS_READ_ONLY_SLICE_ID,
        slice_id=MAPS_READ_ONLY_SLICE_ID,
        entrypoint_id=MAPS_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=_tool_not_exposed_shell_state(launch_decision, message=message),
        surface_payload=None,
        warnings=[message],
        error=build_admin_runtime_error(code=ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE, message=message),
    )


def build_admin_maps_surface_payload(
    *,
    portal_tenant_id: str,
    data_dir: str | Path,
    selected_document_id: object = "",
    selected_row_address: object = "",
    selected_feature_id: object = "",
    overlay_mode: object = "auto",
    raw_underlay_visible: object = False,
) -> dict[str, Any]:
    projection = MapsReadOnlyService(FilesystemSystemDatumStoreAdapter(Path(data_dir))).read_surface(
        portal_tenant_id,
        selected_document_id=selected_document_id,
        selected_row_address=selected_row_address,
        selected_feature_id=selected_feature_id,
        overlay_mode=overlay_mode,
        raw_underlay_visible=raw_underlay_visible,
    )
    return {
        "schema": ADMIN_MAPS_READ_ONLY_SURFACE_SCHEMA,
        "active_surface_id": MAPS_READ_ONLY_SLICE_ID,
        "current_admin_band": ADMIN_BAND5_MAPS_NAME,
        "exposure_status": ADMIN_EXPOSURE_INTERNAL_ONLY,
        "read_write_posture": "read-only",
        "document_catalog": projection["document_catalog"],
        "selected_document": projection["selected_document"],
        "selected_row": projection["selected_row"],
        "map_projection": projection["map_projection"],
        "rows": projection["rows"],
        "diagnostic_summary": projection["diagnostic_summary"],
        "lens_state": projection["lens_state"],
        "warnings": projection["warnings"],
    }


def build_admin_maps_workbench(
    *,
    surface_payload: dict[str, Any],
    portal_tenant_id: str,
) -> dict[str, Any]:
    selected_document = surface_payload.get("selected_document") or {}
    map_projection = surface_payload.get("map_projection") or {}
    diagnostic_summary = surface_payload.get("diagnostic_summary") or {}
    return {
        "schema": ADMIN_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "maps_workbench",
        "title": "Maps",
        "subtitle": (
            f"{_as_text(map_projection.get('projection_state')) or 'inspect_only'}"
            f" · {map_projection.get('feature_count', 0)} features"
            f" · {_as_text(selected_document.get('document_name')) or 'No document'}"
        ),
        "visible": True,
        "document_catalog": list(surface_payload.get("document_catalog") or []),
        "selected_document": selected_document,
        "selected_row": surface_payload.get("selected_row"),
        "map_projection": map_projection,
        "rows": list(surface_payload.get("rows") or []),
        "diagnostic_summary": diagnostic_summary,
        "lens_state": surface_payload.get("lens_state") or {},
        "warnings": list(surface_payload.get("warnings") or []),
        "request_contract": {
            "route": "/portal/api/v2/admin/maps/read-only",
            "method": "POST",
            "request_schema": ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA,
            "fixed_request_fields": {
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
            "overlay_mode_options": ["auto", "raw_only"],
            "portal_tenant_id": portal_tenant_id,
        },
    }


def build_admin_maps_inspector(*, surface_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": ADMIN_SHELL_REGION_INSPECTOR_SCHEMA,
        "title": "Maps",
        "kind": "maps_summary",
        "selected_document": surface_payload.get("selected_document"),
        "selected_feature": (surface_payload.get("map_projection") or {}).get("selected_feature"),
        "selected_row": surface_payload.get("selected_row"),
        "map_projection": surface_payload.get("map_projection") or {},
        "diagnostic_summary": surface_payload.get("diagnostic_summary") or {},
        "lens_state": surface_payload.get("lens_state") or {},
        "warnings": list(surface_payload.get("warnings") or []),
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


def run_admin_maps_read_only(
    request_payload: dict[str, Any] | None = None,
    *,
    data_dir: str | Path | None = None,
    portal_tenant_id: str = "fnd",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_scope, shell_chrome, request_state = _normalize_request(request_payload)
    launch_decision = resolve_admin_tool_launch(
        slice_id=MAPS_READ_ONLY_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=MAPS_READ_ONLY_ENTRYPOINT_ID,
    )

    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND5_MAPS_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=MAPS_READ_ONLY_SLICE_ID,
            slice_id=MAPS_READ_ONLY_SLICE_ID,
            entrypoint_id=MAPS_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message] if message else [],
            error=build_admin_runtime_error(code=launch_decision.reason_code, message=message),
        )

    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tenant_scope=tenant_scope,
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated

    if data_dir is None:
        message = "Maps read-only host data root is not configured."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND5_MAPS_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=MAPS_READ_ONLY_SLICE_ID,
            slice_id=MAPS_READ_ONLY_SLICE_ID,
            entrypoint_id=MAPS_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="data_root_not_configured", message=message),
        )

    surface_payload = build_admin_maps_surface_payload(
        portal_tenant_id=_as_text(portal_tenant_id) or "fnd",
        data_dir=data_dir,
        selected_document_id=request_state["selected_document_id"],
        selected_row_address=request_state["selected_row_address"],
        selected_feature_id=request_state["selected_feature_id"],
        overlay_mode=request_state["overlay_mode"],
        raw_underlay_visible=request_state["raw_underlay_visible"],
    )
    shell_composition = build_shell_composition_payload(
        active_surface_id=MAPS_READ_ONLY_SLICE_ID,
        portal_tenant_id=_as_text(portal_tenant_id) or "fnd",
        page_title="MyCite",
        page_subtitle="Maps",
        activity_items=_activity_items(
            portal_tenant_id=_as_text(portal_tenant_id) or "fnd",
            nav_active_slice_id=MAPS_READ_ONLY_SLICE_ID,
            tool_exposure_policy=tool_exposure_policy,
        ),
        control_panel=_control_panel_region(
            portal_tenant_id=_as_text(portal_tenant_id) or "fnd",
            nav_active_slice_id=MAPS_READ_ONLY_SLICE_ID,
            tool_exposure_policy=tool_exposure_policy,
        ),
        workbench=build_admin_maps_workbench(
            surface_payload=surface_payload,
            portal_tenant_id=_as_text(portal_tenant_id) or "fnd",
        ),
        inspector=build_admin_maps_inspector(surface_payload=surface_payload),
    )
    _apply_shell_chrome_to_composition(shell_composition, shell_chrome)

    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND5_MAPS_NAME,
        exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=MAPS_READ_ONLY_SLICE_ID,
        slice_id=MAPS_READ_ONLY_SLICE_ID,
        entrypoint_id=MAPS_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=launch_decision.to_dict(),
        surface_payload=surface_payload,
        shell_composition=shell_composition,
        warnings=list(surface_payload.get("warnings") or []),
        error=None,
    )


__all__ = [
    "ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA",
    "ADMIN_MAPS_READ_ONLY_SURFACE_SCHEMA",
    "build_admin_maps_inspector",
    "build_admin_maps_surface_payload",
    "build_admin_maps_workbench",
    "run_admin_maps_read_only",
]
