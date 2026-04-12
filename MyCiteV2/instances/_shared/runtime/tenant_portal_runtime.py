from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.modules.domains.publication import (
    PublicationTenantSummary,
    PublicationTenantSummaryService,
    normalize_publication_tenant_summary,
)
from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
    BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
    TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
    TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
    TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
    TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
    TrustedTenantPortalChrome,
    TrustedTenantPortalRequest,
    build_trusted_tenant_portal_composition_payload,
    build_trusted_tenant_portal_dispatch_bodies,
    build_trusted_tenant_portal_surface_catalog,
    resolve_trusted_tenant_portal_request,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
    BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
    TRUSTED_TENANT_HOME_SURFACE_SCHEMA,
    TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
    build_trusted_tenant_runtime_envelope,
    build_trusted_tenant_runtime_error,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_request(payload: dict[str, Any] | None) -> TrustedTenantPortalRequest:
    if payload is None:
        return TrustedTenantPortalRequest()
    if not isinstance(payload, dict):
        raise ValueError("trusted_tenant_portal_runtime.request_payload must be a dict")
    return TrustedTenantPortalRequest.from_dict(payload)


def build_trusted_tenant_visible_slice_catalog() -> tuple[dict[str, Any], ...]:
    return (
        {
            "slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            "label": "Portal Home and Tenant Status",
            "exposure_status": "implemented_trusted_tenant_read_only",
            "read_write_posture": "read-only",
            "status_summary": "default_landing",
            "surface_kind": "tenant_home_status",
            "launchable": True,
            "default_surface": True,
        },
        {
            "slice_id": BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
            "label": "Operational Status",
            "exposure_status": "implemented_trusted_tenant_read_only",
            "read_write_posture": "read-only",
            "status_summary": "read_only_status_surface",
            "surface_kind": "operational_status",
            "launchable": True,
            "default_surface": False,
        },
        {
            "slice_id": BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
            "label": "Recent Activity",
            "exposure_status": "implemented_trusted_tenant_read_only",
            "read_write_posture": "read-only",
            "status_summary": "recent_local_audit_window",
            "surface_kind": "audit_activity",
            "launchable": True,
            "default_surface": False,
        },
        {
            "slice_id": BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
            "label": "Profile Basics",
            "exposure_status": "implemented_trusted_tenant_writable",
            "read_write_posture": "write",
            "status_summary": "bounded_profile_basics_write",
            "surface_kind": "profile_basics_write",
            "launchable": True,
            "default_surface": False,
        },
    )


def _derive_read_write_posture(available_slices: list[dict[str, Any]]) -> str:
    for entry in available_slices:
        if _as_text(entry.get("read_write_posture")) == "write":
            return "write"
    return "read-only"


def _activity_items(*, portal_tenant_id: str, nav_active_slice_id: str) -> list[dict[str, Any]]:
    bodies = build_trusted_tenant_portal_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    items: list[dict[str, Any]] = []
    for entry in build_trusted_tenant_portal_surface_catalog():
        if not entry.launchable:
            continue
        items.append(
            {
                "slice_id": entry.slice_id,
                "label": entry.label,
                "active": entry.slice_id == nav_active_slice_id,
                "shell_request": bodies.get(entry.slice_id),
            }
        )
    return items


def _control_panel_region(*, portal_tenant_id: str, nav_active_slice_id: str) -> dict[str, Any]:
    bodies = build_trusted_tenant_portal_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    available_slices = [dict(entry) for entry in build_trusted_tenant_visible_slice_catalog()]
    read_write_posture = _derive_read_write_posture(available_slices)
    slice_entries: list[dict[str, Any]] = []
    for entry in available_slices:
        slice_id = _as_text(entry.get("slice_id"))
        slice_entries.append(
            {
                "label": _as_text(entry.get("label")),
                "meta": _as_text(entry.get("status_summary")),
                "active": slice_id == nav_active_slice_id,
                "shell_request": bodies.get(slice_id),
            }
        )
    posture_entries = [
        {
            "label": "Rollout band",
            "meta": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
            "active": False,
        },
        {
            "label": "Exposure posture",
            "meta": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
            "active": False,
        },
        {
            "label": "Read/write posture",
            "meta": read_write_posture,
            "active": False,
        },
        {
            "label": "Tenant scope",
            "meta": portal_tenant_id,
            "active": False,
        },
    ]
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
        "sections": [
            {"title": "Available in this band", "entries": slice_entries},
            {"title": "Portal posture", "entries": posture_entries},
        ],
    }


def _workbench_error(*, message: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "error",
        "title": "Portal home",
        "subtitle": "Trusted-tenant read-only landing surface",
        "visible": True,
        "message": message,
    }


def _workbench_home(
    *,
    summary: PublicationTenantSummary,
    available_slices: list[dict[str, Any]],
    read_write_posture: str,
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "tenant_home_status",
        "title": "Portal home",
        "subtitle": "Trusted-tenant portal landing surface",
        "visible": True,
        "where_you_are": "Portal home",
        "rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "tenant_profile": summary.to_dict(),
        "available_slices": available_slices,
        "warnings": list(summary.warnings),
    }


def _inspector_summary(summary: PublicationTenantSummary) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
        "title": "Tenant profile",
        "kind": "tenant_profile_summary",
        "summary": summary.to_dict(),
    }


def _surface_payload(
    *,
    summary: PublicationTenantSummary,
    available_slices: list[dict[str, Any]],
    read_write_posture: str,
    selection_allowed: bool,
    selection_reason: str = "",
) -> dict[str, Any]:
    payload = {
        "schema": TRUSTED_TENANT_HOME_SURFACE_SCHEMA,
        "active_surface_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
        "current_rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "location": {
            "surface_label": "Portal home",
            "audience": "trusted-tenant",
        },
        "tenant_profile": summary.to_dict(),
        "available_slices": list(available_slices),
        "slice_gate_posture": {
            "hidden_write_actions": "blocked",
            "provider_admin_surfaces": "out_of_band",
            "tool_and_sandbox_surfaces": "out_of_band",
            "selection_status": "available" if selection_allowed else "blocked",
        },
    }
    if selection_reason:
        payload["slice_gate_posture"]["selection_reason"] = selection_reason
    return payload


def _apply_shell_chrome_to_composition(
    composition: dict[str, Any],
    chrome: TrustedTenantPortalChrome,
) -> None:
    echo = chrome.to_dict()
    if echo:
        composition["requested_shell_chrome"] = echo
    if chrome.control_panel_collapsed is not None:
        composition["control_panel_collapsed"] = bool(chrome.control_panel_collapsed)
    if chrome.inspector_collapsed is not None:
        composition["inspector_collapsed"] = bool(chrome.inspector_collapsed)


def _fallback_summary(
    *,
    tenant_id: str,
    tenant_domain: str,
    warnings: tuple[str, ...],
) -> PublicationTenantSummary:
    notice = "Publication-backed tenant summary is not yet available for this tenant."
    merged = tuple(list(warnings) + [notice])
    return PublicationTenantSummary.fallback(
        tenant_id=tenant_id,
        tenant_domain=tenant_domain,
        warnings=merged,
    )


def run_trusted_tenant_portal_home(
    request_payload: dict[str, Any] | None = None,
    *,
    data_dir: str | Path | None = None,
    public_dir: str | Path | None = None,
    portal_tenant_id: str = "fnd",
    tenant_domain: str = "",
) -> dict[str, Any]:
    normalized_request = _normalize_request(request_payload)
    selection = resolve_trusted_tenant_portal_request(normalized_request)
    tenant_scope = normalized_request.tenant_scope.to_dict()
    normalized_portal_tenant_id = _as_text(portal_tenant_id).lower() or "fnd"
    normalized_tenant_domain = _as_text(tenant_domain).lower()
    nav_active_slice_id = normalized_request.requested_slice_id
    available_slices = [dict(entry) for entry in build_trusted_tenant_visible_slice_catalog()]
    read_write_posture = _derive_read_write_posture(available_slices)

    if normalized_request.tenant_scope.scope_id.lower() != normalized_portal_tenant_id:
        return build_trusted_tenant_runtime_envelope(
            rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
            exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
            tenant_scope=tenant_scope,
            requested_slice_id=normalized_request.requested_slice_id,
            slice_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            entrypoint_id=TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
            read_write_posture=read_write_posture,
            shell_state=selection.to_dict(),
            surface_payload=None,
            shell_composition=build_trusted_tenant_portal_composition_payload(
                active_surface_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                portal_tenant_id=normalized_portal_tenant_id,
                page_title="MyCite",
                page_subtitle="Tenant scope mismatch",
                activity_items=_activity_items(
                    portal_tenant_id=normalized_portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                ),
                control_panel=_control_panel_region(
                    portal_tenant_id=normalized_portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                ),
                workbench=_workbench_error(
                    message="Trusted-tenant portal requests must stay inside the configured portal tenant scope."
                ),
                inspector={
                    "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
                    "title": "Tenant profile",
                    "kind": "empty",
                    "body_text": "Tenant profile details are unavailable for a rejected scope.",
                },
            ),
            warnings=["Trusted-tenant portal request rejected because the tenant scope did not match the portal tenant."],
            error=build_trusted_tenant_runtime_error(
                code="tenant_scope_mismatch",
                message="Trusted-tenant portal requests must match the configured portal tenant scope.",
            ),
        )

    if data_dir is None or public_dir is None or not normalized_tenant_domain:
        return build_trusted_tenant_runtime_envelope(
            rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
            exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
            tenant_scope=tenant_scope,
            requested_slice_id=normalized_request.requested_slice_id,
            slice_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            entrypoint_id=TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
            read_write_posture=read_write_posture,
            shell_state=selection.to_dict(),
            surface_payload=None,
            shell_composition=build_trusted_tenant_portal_composition_payload(
                active_surface_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
                portal_tenant_id=normalized_portal_tenant_id,
                page_title="MyCite",
                page_subtitle="Portal home unavailable",
                activity_items=_activity_items(
                    portal_tenant_id=normalized_portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                ),
                control_panel=_control_panel_region(
                    portal_tenant_id=normalized_portal_tenant_id,
                    nav_active_slice_id=nav_active_slice_id,
                ),
                workbench=_workbench_error(
                    message="The publication-backed tenant summary source is not configured for this portal runtime."
                ),
                inspector={
                    "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
                    "title": "Tenant profile",
                    "kind": "empty",
                    "body_text": "Publication-backed tenant summary is unavailable until the runtime is configured.",
                },
            ),
            warnings=["Trusted-tenant portal runtime is missing data_dir, public_dir, or tenant_domain."],
            error=build_trusted_tenant_runtime_error(
                code="publication_source_not_configured",
                message="The trusted-tenant portal runtime requires data_dir, public_dir, and tenant_domain.",
            ),
        )

    adapter = FilesystemSystemDatumStoreAdapter(
        Path(data_dir),
        public_dir=Path(public_dir),
    )
    service = PublicationTenantSummaryService(adapter)
    projection = service.read_projection(normalized_portal_tenant_id, normalized_tenant_domain)
    summary = (
        normalize_publication_tenant_summary(projection.source, warnings=projection.warnings)
        if projection.source is not None
        else _fallback_summary(
            tenant_id=normalized_portal_tenant_id,
            tenant_domain=normalized_tenant_domain,
            warnings=projection.warnings,
        )
    )

    surface_payload = _surface_payload(
        summary=summary,
        available_slices=available_slices,
        read_write_posture=read_write_posture,
        selection_allowed=selection.allowed,
        selection_reason=selection.reason_message,
    )
    if selection.allowed:
        workbench = _workbench_home(
            summary=summary,
            available_slices=available_slices,
            read_write_posture=read_write_posture,
        )
    else:
        workbench = _workbench_error(
            message=selection.reason_message or "Requested trusted-tenant slice is not approved."
        )
    inspector = _inspector_summary(summary)
    shell_composition = build_trusted_tenant_portal_composition_payload(
        active_surface_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
        portal_tenant_id=normalized_portal_tenant_id,
        page_title="MyCite",
        page_subtitle="Portal home",
        activity_items=_activity_items(
            portal_tenant_id=normalized_portal_tenant_id,
            nav_active_slice_id=nav_active_slice_id,
        ),
        control_panel=_control_panel_region(
            portal_tenant_id=normalized_portal_tenant_id,
            nav_active_slice_id=nav_active_slice_id,
        ),
        workbench=workbench,
        inspector=inspector,
    )
    _apply_shell_chrome_to_composition(shell_composition, normalized_request.shell_chrome)

    warnings = list(summary.warnings)
    error = None
    if not selection.allowed:
        warnings.append(selection.reason_message)
        error = build_trusted_tenant_runtime_error(
            code=selection.reason_code or "slice_unknown",
            message=selection.reason_message or "Requested trusted-tenant slice is not approved.",
        )

    return build_trusted_tenant_runtime_envelope(
        rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        tenant_scope=tenant_scope,
        requested_slice_id=normalized_request.requested_slice_id,
        slice_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
        entrypoint_id=TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
        read_write_posture=read_write_posture,
        shell_state=selection.to_dict(),
        surface_payload=surface_payload,
        shell_composition=shell_composition,
        warnings=warnings,
        error=error,
    )


__all__ = [
    "TRUSTED_TENANT_HOME_SURFACE_SCHEMA",
    "build_trusted_tenant_visible_slice_catalog",
    "run_trusted_tenant_portal_home",
]
