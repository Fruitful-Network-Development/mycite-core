from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
    TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
    TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
    TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA,
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
class TrustedTenantOperationalStatusRequest:
    tenant_scope: TrustedTenantPortalScope = field(
        default_factory=lambda: TrustedTenantPortalScope(scope_id="fnd")
    )
    shell_chrome: TrustedTenantPortalChrome = field(default_factory=TrustedTenantPortalChrome)
    schema: str = field(default=TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA, init=False)

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
    def from_dict(cls, payload: dict[str, Any] | None) -> "TrustedTenantOperationalStatusRequest":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("trusted_tenant_operational_status_request must be a dict")
        _require_schema(
            payload,
            expected=TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
            field_name="trusted_tenant_operational_status_request.schema",
        )
        return cls(
            tenant_scope=TrustedTenantPortalScope.from_value(payload.get("tenant_scope")),
            shell_chrome=TrustedTenantPortalChrome.from_value(
                payload.get("shell_chrome") if isinstance(payload.get("shell_chrome"), dict) else None
            ),
        )


def _normalize_request(
    payload: dict[str, Any] | None,
) -> TrustedTenantOperationalStatusRequest:
    if payload is None:
        return TrustedTenantOperationalStatusRequest()
    if not isinstance(payload, dict):
        raise ValueError("trusted_tenant_operational_status_runtime.request_payload must be a dict")
    return TrustedTenantOperationalStatusRequest.from_dict(payload)


def _selection_state(
    *,
    allowed: bool,
    selection_status: str,
    reason_code: str = "",
    reason_message: str = "",
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_STATE_SCHEMA,
        "requested_slice_id": BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        "active_surface_id": BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        "selection_status": selection_status,
        "allowed": bool(allowed),
        "reason_code": _as_text(reason_code),
        "reason_message": _as_text(reason_message),
    }


def _status_shell_request(*, portal_tenant_id: str) -> dict[str, Any]:
    return TrustedTenantOperationalStatusRequest(
        tenant_scope=TrustedTenantPortalScope(
            scope_id=_as_text(portal_tenant_id) or "fnd",
            audience="trusted-tenant",
        )
    ).to_dict()


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


def _health_warning(audit_persistence: dict[str, Any]) -> str:
    health_state = _as_text(audit_persistence.get("health_state"))
    if health_state == "not_configured":
        return "Audit persistence is not configured for this portal route."
    if health_state == "unavailable":
        return "Audit persistence storage is unreadable; showing degraded operational status."
    if health_state == "no_recent_persistence_evidence":
        return "No recent audit persistence evidence was found in the fixed recent window."
    return ""


def _activity_items(*, portal_tenant_id: str) -> list[dict[str, Any]]:
    return [
        {
            "slice_id": BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
            "label": "Operational Status",
            "active": True,
            "shell_request": _status_shell_request(portal_tenant_id=portal_tenant_id),
        }
    ]


def _control_panel_region(
    *,
    portal_tenant_id: str,
    available_slices: list[dict[str, Any]],
    audit_persistence: dict[str, Any],
    read_write_posture: str,
) -> dict[str, Any]:
    slice_entries: list[dict[str, Any]] = []
    for entry in available_slices:
        slice_entries.append(
            {
                "label": _as_text(entry.get("label")),
                "meta": _as_text(entry.get("status_summary")),
                "active": _as_text(entry.get("slice_id")) == BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
                "shell_request": (
                    _status_shell_request(portal_tenant_id=portal_tenant_id)
                    if _as_text(entry.get("slice_id")) == BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID
                    else None
                ),
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
            "label": "Audit persistence",
            "meta": _as_text(audit_persistence.get("health_state")).replace("_", " "),
            "active": False,
        },
    ]
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
        "sections": [
            {"title": "Available in this band", "entries": slice_entries},
            {"title": "Operational posture", "entries": posture_entries},
        ],
    }


def _workbench_error(*, message: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "error",
        "title": "Operational status",
        "subtitle": "Trusted-tenant read-only posture",
        "visible": True,
        "message": message,
    }


def _workbench_status(
    *,
    available_slices: list[dict[str, Any]],
    audit_persistence: dict[str, Any],
    read_write_posture: str,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "operational_status",
        "title": "Operational status",
        "subtitle": "Trusted-tenant read-only posture",
        "visible": True,
        "current_rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "audit_persistence": dict(audit_persistence),
        "available_slices": list(available_slices),
        "warnings": list(warnings),
    }


def _inspector_error(*, body_text: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
        "title": "Operational summary",
        "kind": "empty",
        "body_text": body_text,
    }


def _inspector_status(*, audit_persistence: dict[str, Any], read_write_posture: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
        "title": "Operational summary",
        "kind": "operational_status_summary",
        "current_rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "audit_persistence": dict(audit_persistence),
    }


def _surface_payload(
    *,
    available_slices: list[dict[str, Any]],
    audit_persistence: dict[str, Any],
    read_write_posture: str,
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA,
        "active_surface_id": BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        "current_rollout_band": BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        "exposure_status": TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "location": {
            "surface_label": "Operational status",
            "audience": "trusted-tenant",
        },
        "audit_persistence": dict(audit_persistence),
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
        active_surface_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
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
        requested_slice_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        slice_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        entrypoint_id=TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
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


def run_trusted_tenant_operational_status(
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
            inspector_body_text="Operational status is unavailable for a rejected audience.",
            warnings=["Trusted-tenant operational status rejected because the audience was not trusted-tenant."],
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
                    "Trusted-tenant operational status requests must stay inside the configured portal tenant scope."
                ),
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Tenant scope mismatch",
            message="Trusted-tenant operational status requests must stay inside the configured portal tenant scope.",
            inspector_body_text="Operational status is unavailable for a rejected tenant scope.",
            warnings=["Trusted-tenant operational status rejected because the tenant scope did not match the portal tenant."],
            error_code="tenant_scope_mismatch",
            error_message="Trusted-tenant operational status requests must match the configured portal tenant scope.",
        )

    if audit_storage_file is None:
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="unknown",
                reason_code="audit_log_not_configured",
                reason_message="Operational status requires an audit storage file.",
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Operational status unavailable",
            message="The operational-status runtime is missing its audit persistence configuration.",
            inspector_body_text="Audit persistence is unavailable until the runtime is configured.",
            warnings=["Trusted-tenant operational status runtime is missing audit_storage_file."],
            error_code="audit_log_not_configured",
            error_message="The trusted-tenant operational status runtime requires audit_storage_file.",
        )

    available_slices = [dict(entry) for entry in build_trusted_tenant_visible_slice_catalog()]
    read_write_posture = _derive_read_write_posture(available_slices)
    audit_service = LocalAuditService(FilesystemAuditLogAdapter(Path(audit_storage_file)))
    audit_persistence = audit_service.read_operational_status_summary().to_dict()
    warnings: list[str] = []
    health_warning = _health_warning(audit_persistence)
    if health_warning:
        warnings.append(health_warning)

    shell_composition = build_trusted_tenant_portal_composition_payload(
        active_surface_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        portal_tenant_id=normalized_portal_tenant_id,
        page_title="MyCite",
        page_subtitle="Operational status",
        activity_items=_activity_items(portal_tenant_id=normalized_portal_tenant_id),
        control_panel=_control_panel_region(
            portal_tenant_id=normalized_portal_tenant_id,
            available_slices=available_slices,
            audit_persistence=audit_persistence,
            read_write_posture=read_write_posture,
        ),
        workbench=_workbench_status(
            available_slices=available_slices,
            audit_persistence=audit_persistence,
            read_write_posture=read_write_posture,
            warnings=warnings,
        ),
        inspector=_inspector_status(
            audit_persistence=audit_persistence,
            read_write_posture=read_write_posture,
        ),
    )
    _apply_shell_chrome_to_composition(shell_composition, normalized_request.shell_chrome)

    return build_trusted_tenant_runtime_envelope(
        rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
        exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
        tenant_scope=tenant_scope,
        requested_slice_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        slice_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
        entrypoint_id=TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
        read_write_posture=read_write_posture,
        shell_state=_selection_state(allowed=True, selection_status="available"),
        surface_payload=_surface_payload(
            available_slices=available_slices,
            audit_persistence=audit_persistence,
            read_write_posture=read_write_posture,
        ),
        shell_composition=shell_composition,
        warnings=warnings,
        error=None,
    )


__all__ = [
    "TrustedTenantOperationalStatusRequest",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA",
    "run_trusted_tenant_operational_status",
]
