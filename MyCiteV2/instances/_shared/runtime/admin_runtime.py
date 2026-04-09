from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND0_NAME,
    ADMIN_ENTRYPOINT_ID,
    ADMIN_EXPOSURE_INTERNAL_ONLY,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_READ_ONLY_SLICE_ID,
    AdminShellRequest,
    build_admin_surface_catalog,
    build_admin_tool_registry_entries,
    resolve_admin_shell_request,
)

ADMIN_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.admin.runtime.envelope.v1"
ADMIN_HOME_STATUS_SURFACE_SCHEMA = "mycite.v2.admin.home_status.surface.v1"
ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA = "mycite.v2.admin.tool_registry.surface.v1"


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


def _build_home_status_surface(
    *,
    audit_storage_file: str | Path | None,
) -> dict[str, Any]:
    surface_catalog = [entry.to_dict() for entry in build_admin_surface_catalog()]
    tool_entries = [entry.to_dict() for entry in build_admin_tool_registry_entries()]
    launchable_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["launchable"]]
    gated_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if not entry["launchable"]]
    available_tool_slices = [entry for entry in tool_entries if entry["launchable"]]
    gated_tool_slices = [entry for entry in tool_entries if not entry["launchable"]]

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
        },
        "readiness_summary": {
            "shell_entry": "ready",
            "home_status": "ready",
            "tool_registry": "ready",
            "launchable_tool_slice_ids": launchable_tool_slice_ids,
            "gated_tool_slice_ids": gated_tool_slice_ids,
            "next_tool_slice_id": AWS_READ_ONLY_SLICE_ID,
        },
        "follow_on_order": [
            "admin_band1.aws_read_only_surface",
            "maps_after_aws",
            "agro_erp_after_maps",
        ],
    }


def _build_tool_registry_surface() -> dict[str, Any]:
    surface_catalog = [entry.to_dict() for entry in build_admin_surface_catalog()]
    tool_entries = [entry.to_dict() for entry in build_admin_tool_registry_entries()]
    launchable_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if entry["launchable"]]
    gated_tool_slice_ids = [entry["slice_id"] for entry in tool_entries if not entry["launchable"]]

    return {
        "schema": ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA,
        "active_surface_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
        "registry_owner": "shell",
        "default_posture": "deny-by-default",
        "launchable_admin_slice_ids": [entry["slice_id"] for entry in surface_catalog if entry["launchable"]],
        "launchable_tool_slice_ids": launchable_tool_slice_ids,
        "gated_tool_slice_ids": gated_tool_slice_ids,
        "tool_entries": tool_entries,
        "follow_on_constraints": {
            "maps": "blocked_until_aws",
            "agro_erp": "blocked_until_maps",
        },
    }


def _select_surface_payload(
    *,
    active_surface_id: str,
    audit_storage_file: str | Path | None,
) -> dict[str, Any]:
    if active_surface_id == ADMIN_TOOL_REGISTRY_SLICE_ID:
        return _build_tool_registry_surface()
    return _build_home_status_surface(audit_storage_file=audit_storage_file)


def run_admin_shell_entry(
    request_payload: dict[str, Any] | None = None,
    *,
    audit_storage_file: str | Path | None = None,
) -> dict[str, Any]:
    normalized_request = _normalize_request(request_payload)
    selection = resolve_admin_shell_request(normalized_request)

    surface_payload = None
    if normalized_request.tenant_scope.audience == "internal":
        surface_payload = _select_surface_payload(
            active_surface_id=selection.active_surface_id,
            audit_storage_file=audit_storage_file,
        )

    error = None
    warnings: list[str] = []
    if not selection.allowed:
        error = {
            "code": selection.reason_code,
            "message": selection.reason_message,
        }
        if selection.reason_message:
            warnings.append(selection.reason_message)

    return {
        "schema": ADMIN_RUNTIME_ENVELOPE_SCHEMA,
        "admin_band": ADMIN_BAND0_NAME,
        "exposure_status": ADMIN_EXPOSURE_INTERNAL_ONLY,
        "tenant_scope": normalized_request.tenant_scope.to_dict(),
        "requested_slice_id": normalized_request.requested_slice_id,
        "slice_id": selection.active_surface_id,
        "entrypoint_id": ADMIN_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "shell_state": selection.to_dict(),
        "surface_payload": surface_payload,
        "warnings": warnings,
        "error": error,
    }
