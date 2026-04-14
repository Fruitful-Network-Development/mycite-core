from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
    TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
    TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
    TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA,
    build_trusted_tenant_runtime_envelope,
    build_trusted_tenant_runtime_error,
)
from MyCiteV2.instances._shared.runtime.tenant_portal_runtime import (
    build_trusted_tenant_visible_slice_catalog,
)
from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
    TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
    TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
    TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
    TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
    TRUSTED_TENANT_PORTAL_STATE_SCHEMA,
    TrustedTenantPortalChrome,
    TrustedTenantPortalScope,
    build_trusted_tenant_activity_items,
    build_trusted_tenant_control_panel_region,
    build_trusted_tenant_portal_composition_payload,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = _as_text(payload.get("schema"))
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


@dataclass(frozen=True)
class TrustedTenantAuditActivityRequest:
    tenant_scope: TrustedTenantPortalScope = field(
        default_factory=lambda: TrustedTenantPortalScope(scope_id="fnd")
    )
    shell_chrome: TrustedTenantPortalChrome = field(default_factory=TrustedTenantPortalChrome)
    schema: str = field(default=TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        tenant_scope = (
            self.tenant_scope
            if isinstance(self.tenant_scope, TrustedTenantPortalScope)
            else TrustedTenantPortalScope.from_value(self.tenant_scope)
        )
        shell_chrome = (
            self.shell_chrome
            if isinstance(self.shell_chrome, TrustedTenantPortalChrome)
            else TrustedTenantPortalChrome.from_value(self.shell_chrome)
        )
        object.__setattr__(self, "tenant_scope", tenant_scope)
        object.__setattr__(self, "shell_chrome", shell_chrome)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "tenant_scope": self.tenant_scope.to_dict(),
        }
        chrome = self.shell_chrome.to_dict()
        if chrome:
            payload["shell_chrome"] = chrome
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "TrustedTenantAuditActivityRequest":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("trusted_tenant_audit_activity_request must be a dict")
        _require_schema(
            payload,
            expected=TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
            field_name="trusted_tenant_audit_activity_request.schema",
        )
        return cls(
            tenant_scope=TrustedTenantPortalScope.from_value(payload.get("tenant_scope")),
            shell_chrome=TrustedTenantPortalChrome.from_value(
                payload.get("shell_chrome") if isinstance(payload.get("shell_chrome"), dict) else None
            ),
        )


def _normalize_request(
    payload: dict[str, Any] | None,
) -> TrustedTenantAuditActivityRequest:
    if payload is None:
        return TrustedTenantAuditActivityRequest()
    if not isinstance(payload, dict):
        raise ValueError("trusted_tenant_audit_activity_runtime.request_payload must be a dict")
    return TrustedTenantAuditActivityRequest.from_dict(payload)


def _selection_state(
    *,
    allowed: bool,
    selection_status: str,
    reason_code: str = "",
    reason_message: str = "",
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_STATE_SCHEMA,
        "requested_slice_id": BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        "active_surface_id": BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        "selection_status": selection_status,
        "allowed": bool(allowed),
        "reason_code": _as_text(reason_code),
        "reason_message": _as_text(reason_message),
    }


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


def _derive_read_write_posture(available_slices: list[dict[str, Any]]) -> str:
    for entry in available_slices:
        if _as_text(entry.get("read_write_posture")) == "write":
            return "write"
    return "read-only"


def _activity_warning(recent_activity: dict[str, Any]) -> str:
    activity_state = _as_text(recent_activity.get("activity_state"))
    if activity_state == "unavailable":
        return "Recent activity storage is unreadable; showing degraded recent activity."
    if activity_state == "empty":
        return "No recent tenant-facing audit activity was found in the fixed recent window."
    return ""


def _activity_items(*, portal_tenant_id: str) -> list[dict[str, Any]]:
    return build_trusted_tenant_activity_items(
        portal_tenant_id=portal_tenant_id,
        active_surface_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
    )


def _control_panel_region(
    *,
    portal_tenant_id: str,
    available_slices: list[dict[str, Any]],
    recent_activity: dict[str, Any],
    read_write_posture: str,
) -> dict[str, Any]:
    attention_entries: list[dict[str, Any]] = []
    warning = _activity_warning(recent_activity)
    if warning:
        attention_entries.append(
            {
                "label": "Recent activity",
                "meta": warning,
                "active": False,
            }
        )
    return build_trusted_tenant_control_panel_region(
        portal_tenant_id=portal_tenant_id,
        active_surface_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        title="Recent activity",
        subtitle="Tenant activity attention and approved surfaces.",
        current_rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        read_write_posture=read_write_posture,
        attention_entries=attention_entries,
        context_entries=[
            {
                "label": "Recent activity",
                "meta": _as_text(recent_activity.get("activity_state")).replace("_", " "),
                "active": False,
            }
        ],
    )


def _workbench_error(*, message: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "error",
        "title": "Recent activity",
        "subtitle": "Trusted-tenant read-only posture",
        "visible": True,
        "message": message,
    }


def _workbench_activity(
    *,
    available_slices: list[dict[str, Any]],
    recent_activity: dict[str, Any],
    read_write_posture: str,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "audit_activity",
        "title": "Recent activity",
        "subtitle": "Trusted-tenant read-only posture",
        "visible": True,
        "current_rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "recent_activity": dict(recent_activity),
        "available_slices": list(available_slices),
        "warnings": list(warnings),
    }


def _inspector_error(*, body_text: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
        "title": "Activity summary",
        "kind": "empty",
        "body_text": body_text,
    }


def _inspector_activity(*, recent_activity: dict[str, Any], read_write_posture: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
        "title": "Activity summary",
        "kind": "audit_activity_summary",
        "current_rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "recent_activity": dict(recent_activity),
    }


def _surface_payload(
    *,
    available_slices: list[dict[str, Any]],
    recent_activity: dict[str, Any],
    read_write_posture: str,
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA,
        "active_surface_id": BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        "current_rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "location": {
            "surface_label": "Recent activity",
            "audience": "trusted-tenant",
        },
        "recent_activity": dict(recent_activity),
        "available_slices": list(available_slices),
        "slice_gate_posture": {
            "hidden_write_actions": "blocked",
            "provider_admin_surfaces": "out_of_band",
            "tool_and_sandbox_surfaces": "out_of_band",
            "selection_status": "available",
        },
    }


def _error_envelope(
    *,
    tenant_scope: dict[str, Any],
    shell_state: dict[str, Any],
    portal_tenant_id: str,
    page_subtitle: str,
    message: str,
    inspector_body_text: str,
    warnings: list[str],
    error_code: str,
    error_message: str,
) -> dict[str, Any]:
    shell_composition = build_trusted_tenant_portal_composition_payload(
        active_surface_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        portal_tenant_id=portal_tenant_id,
        page_title="MyCite",
        page_subtitle=page_subtitle,
        activity_items=_activity_items(portal_tenant_id=portal_tenant_id),
        control_panel={
            "schema": TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
            "sections": [],
        },
        workbench=_workbench_error(message=message),
        inspector=_inspector_error(body_text=inspector_body_text),
    )
    return build_trusted_tenant_runtime_envelope(
        rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        tenant_scope=tenant_scope,
        requested_slice_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        slice_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        entrypoint_id=TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=shell_state,
        surface_payload=None,
        shell_composition=shell_composition,
        warnings=list(warnings),
        error=build_trusted_tenant_runtime_error(
            code=error_code,
            message=error_message,
        ),
    )


def run_trusted_tenant_audit_activity(
    request_payload: dict[str, Any] | None = None,
    *,
    audit_storage_file: str | Path | None = None,
    portal_tenant_id: str = "fnd",
) -> dict[str, Any]:
    normalized_request = _normalize_request(request_payload)
    tenant_scope = normalized_request.tenant_scope.to_dict()
    normalized_portal_tenant_id = _as_text(portal_tenant_id).lower() or "fnd"

    if normalized_request.tenant_scope.audience != "trusted-tenant":
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="audience_denied",
                reason_code="audience_not_allowed",
                reason_message="Trusted-tenant portal requests require trusted-tenant audience.",
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Audience rejected",
            message="Trusted-tenant portal requests require trusted-tenant audience.",
            inspector_body_text="Recent activity is unavailable for a rejected audience.",
            warnings=["Trusted-tenant audit activity rejected because the audience was not trusted-tenant."],
            error_code="audience_not_allowed",
            error_message="Trusted-tenant portal requests require trusted-tenant audience.",
        )

    if normalized_request.tenant_scope.scope_id.lower() != normalized_portal_tenant_id:
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="unknown",
                reason_code="tenant_scope_mismatch",
                reason_message=(
                    "Trusted-tenant audit activity requests must stay inside the configured portal tenant scope."
                ),
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Tenant scope mismatch",
            message="Trusted-tenant audit activity requests must stay inside the configured portal tenant scope.",
            inspector_body_text="Recent activity is unavailable for a rejected tenant scope.",
            warnings=["Trusted-tenant audit activity rejected because the tenant scope did not match the portal tenant."],
            error_code="tenant_scope_mismatch",
            error_message="Trusted-tenant audit activity requests must match the configured portal tenant scope.",
        )

    if audit_storage_file is None:
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="unknown",
                reason_code="audit_log_not_configured",
                reason_message="Recent activity requires an audit storage file.",
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Recent activity unavailable",
            message="The recent-activity runtime is missing its audit persistence configuration.",
            inspector_body_text="Recent activity is unavailable until the runtime is configured.",
            warnings=["Trusted-tenant audit activity runtime is missing audit_storage_file."],
            error_code="audit_log_not_configured",
            error_message="The trusted-tenant audit activity runtime requires audit_storage_file.",
        )

    available_slices = [dict(entry) for entry in build_trusted_tenant_visible_slice_catalog()]
    read_write_posture = _derive_read_write_posture(available_slices)
    audit_service = LocalAuditService(FilesystemAuditLogAdapter(Path(audit_storage_file)))
    recent_activity = audit_service.read_recent_activity_projection().to_dict()
    warnings: list[str] = []
    activity_warning = _activity_warning(recent_activity)
    if activity_warning:
        warnings.append(activity_warning)

    shell_composition = build_trusted_tenant_portal_composition_payload(
        active_surface_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        portal_tenant_id=normalized_portal_tenant_id,
        page_title="MyCite",
        page_subtitle="Recent activity",
        activity_items=_activity_items(portal_tenant_id=normalized_portal_tenant_id),
        control_panel=_control_panel_region(
            portal_tenant_id=normalized_portal_tenant_id,
            available_slices=available_slices,
            recent_activity=recent_activity,
            read_write_posture=read_write_posture,
        ),
        workbench=_workbench_activity(
            available_slices=available_slices,
            recent_activity=recent_activity,
            read_write_posture=read_write_posture,
            warnings=warnings,
        ),
        inspector=_inspector_activity(
            recent_activity=recent_activity,
            read_write_posture=read_write_posture,
        ),
    )
    _apply_shell_chrome_to_composition(shell_composition, normalized_request.shell_chrome)

    return build_trusted_tenant_runtime_envelope(
        rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        tenant_scope=tenant_scope,
        requested_slice_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        slice_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
        entrypoint_id=TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
        read_write_posture=read_write_posture,
        shell_state=_selection_state(allowed=True, selection_status="available"),
        surface_payload=_surface_payload(
            available_slices=available_slices,
            recent_activity=recent_activity,
            read_write_posture=read_write_posture,
        ),
        shell_composition=shell_composition,
        warnings=warnings,
        error=None,
    )


__all__ = [
    "TrustedTenantAuditActivityRequest",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA",
    "run_trusted_tenant_audit_activity",
]
