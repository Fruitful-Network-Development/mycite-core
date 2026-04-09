from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemAwsReadOnlyStatusAdapter
from MyCiteV2.packages.modules.cross_domain.aws_operational_visibility import AwsOperationalVisibilityService
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND1_AWS_NAME,
    ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
    AdminTenantScope,
    resolve_admin_tool_launch,
)

ADMIN_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.admin.runtime.envelope.v1"
ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.aws.read_only.request.v1"
ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA = "mycite.v2.admin.aws.read_only.surface.v1"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_request(payload: dict[str, Any] | None) -> AdminTenantScope:
    if payload is None:
        raise ValueError("admin.aws.read_only requires a request payload")
    if not isinstance(payload, dict):
        raise ValueError("admin.aws.read_only request payload must be a dict")
    schema = _as_text(payload.get("schema"))
    if schema != ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA:
        raise ValueError(f"admin.aws.read_only request.schema must be {ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA}")
    return AdminTenantScope.from_value(payload.get("tenant_scope"))


def _build_surface_payload(*, tenant_scope: AdminTenantScope, visibility: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
        "active_surface_id": AWS_READ_ONLY_SLICE_ID,
        "tenant_scope_id": tenant_scope.scope_id,
        "mailbox_readiness": visibility["mailbox_readiness"],
        "smtp_state": visibility["smtp_state"],
        "gmail_state": visibility["gmail_state"],
        "verified_evidence_state": visibility["verified_evidence_state"],
        "selected_verified_sender": visibility["selected_verified_sender"],
        "canonical_newsletter_operational_profile": visibility["canonical_newsletter_profile"],
        "compatibility_warnings": visibility["compatibility_warnings"],
        "inbound_capture": visibility["inbound_capture"],
        "dispatch_health": visibility["dispatch_health"],
        "write_capability": "not_available",
    }


def run_admin_aws_read_only(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_status_file: str | Path | None = None,
) -> dict[str, Any]:
    tenant_scope = _normalize_request(request_payload)
    launch_decision = resolve_admin_tool_launch(
        slice_id=AWS_READ_ONLY_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
    )

    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return {
            "schema": ADMIN_RUNTIME_ENVELOPE_SCHEMA,
            "admin_band": ADMIN_BAND1_AWS_NAME,
            "exposure_status": ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            "tenant_scope": tenant_scope.to_dict(),
            "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
            "slice_id": AWS_READ_ONLY_SLICE_ID,
            "entrypoint_id": AWS_READ_ONLY_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "shell_state": launch_decision.to_dict(),
            "surface_payload": None,
            "warnings": [message] if message else [],
            "error": {
                "code": launch_decision.reason_code,
                "message": message,
            },
        }

    if aws_status_file is None:
        return {
            "schema": ADMIN_RUNTIME_ENVELOPE_SCHEMA,
            "admin_band": ADMIN_BAND1_AWS_NAME,
            "exposure_status": ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            "tenant_scope": tenant_scope.to_dict(),
            "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
            "slice_id": AWS_READ_ONLY_SLICE_ID,
            "entrypoint_id": AWS_READ_ONLY_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "shell_state": launch_decision.to_dict(),
            "surface_payload": None,
            "warnings": ["AWS read-only status source is not configured."],
            "error": {
                "code": "status_source_not_configured",
                "message": "AWS read-only status source is not configured.",
            },
        }

    adapter = FilesystemAwsReadOnlyStatusAdapter(aws_status_file)
    service = AwsOperationalVisibilityService(adapter)
    surface = service.read_surface(tenant_scope.scope_id)

    if surface is None:
        return {
            "schema": ADMIN_RUNTIME_ENVELOPE_SCHEMA,
            "admin_band": ADMIN_BAND1_AWS_NAME,
            "exposure_status": ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            "tenant_scope": tenant_scope.to_dict(),
            "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
            "slice_id": AWS_READ_ONLY_SLICE_ID,
            "entrypoint_id": AWS_READ_ONLY_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "shell_state": launch_decision.to_dict(),
            "surface_payload": None,
            "warnings": ["No AWS read-only status snapshot matched the requested tenant scope."],
            "error": {
                "code": "status_snapshot_not_found",
                "message": "No AWS read-only status snapshot matched the requested tenant scope.",
            },
        }

    surface_payload = _build_surface_payload(tenant_scope=tenant_scope, visibility=surface.to_dict())

    return {
        "schema": ADMIN_RUNTIME_ENVELOPE_SCHEMA,
        "admin_band": ADMIN_BAND1_AWS_NAME,
        "exposure_status": ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        "tenant_scope": tenant_scope.to_dict(),
        "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
        "slice_id": AWS_READ_ONLY_SLICE_ID,
        "entrypoint_id": AWS_READ_ONLY_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "shell_state": launch_decision.to_dict(),
        "surface_payload": surface_payload,
        "warnings": list(surface_payload["compatibility_warnings"]),
        "error": None,
    }
