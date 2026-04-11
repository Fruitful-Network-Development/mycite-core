from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAuditLogAdapter,
    FilesystemAwsCsmOnboardingProfileStore,
    FilesystemAwsNarrowWriteAdapter,
    FilesystemAwsReadOnlyStatusAdapter,
    FilesystemLiveAwsProfileAdapter,
    is_live_aws_profile_file,
)
from MyCiteV2.packages.modules.cross_domain.aws_csm_onboarding import (
    AwsCsmOnboardingService,
    AwsCsmOnboardingUnconfiguredCloudPort,
)
from MyCiteV2.packages.modules.cross_domain.aws_narrow_write import AwsNarrowWriteService
from MyCiteV2.packages.modules.cross_domain.aws_operational_visibility import AwsOperationalVisibilityService
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.ports.aws_csm_onboarding import (
    AwsCsmOnboardingCloudPort,
    AwsCsmOnboardingPolicyError,
    AwsCsmOnboardingProfileStorePort,
)
from MyCiteV2.packages.ports.aws_narrow_write import AwsNarrowWritePort
from MyCiteV2.packages.ports.aws_read_only_status import AwsReadOnlyStatusPort
from MyCiteV2.packages.sandboxes.tool import validate_staged_aws_csm_profile_path
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND1_AWS_NAME,
    ADMIN_BAND2_AWS_NAME,
    ADMIN_BAND3_AWS_SANDBOX_NAME,
    ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
    ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
    ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
    ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
    ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
    AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
    AdminTenantScope,
    resolve_admin_tool_launch,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA,
    ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
    ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA,
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    AWS_CSM_ONBOARDING_RECOVERY_REFERENCE,
    AWS_NARROW_WRITE_RECOVERY_REFERENCE,
    build_admin_runtime_envelope,
    build_admin_runtime_error,
)


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


def _build_read_only_surface_payload(
    *,
    tenant_scope: AdminTenantScope,
    visibility: dict[str, Any],
    active_surface_id: str | None = None,
) -> dict[str, Any]:
    surface_id = active_surface_id or AWS_READ_ONLY_SLICE_ID
    return {
        "schema": ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
        "active_surface_id": surface_id,
        "tenant_scope_id": tenant_scope.scope_id,
        "mailbox_readiness": visibility["mailbox_readiness"],
        "smtp_state": visibility["smtp_state"],
        "gmail_state": visibility["gmail_state"],
        "verified_evidence_state": visibility["verified_evidence_state"],
        "selected_verified_sender": visibility["selected_verified_sender"],
        "allowed_send_domains": list(visibility.get("allowed_send_domains") or []),
        "canonical_newsletter_operational_profile": visibility["canonical_newsletter_profile"],
        "compatibility_warnings": visibility["compatibility_warnings"],
        "inbound_capture": visibility["inbound_capture"],
        "dispatch_health": visibility["dispatch_health"],
        "write_capability": "not_available",
    }


def _aws_read_only_status_port_for_file(aws_status_file: str | Path) -> AwsReadOnlyStatusPort:
    if is_live_aws_profile_file(aws_status_file):
        return FilesystemLiveAwsProfileAdapter(aws_status_file)
    return FilesystemAwsReadOnlyStatusAdapter(aws_status_file)


def _aws_narrow_write_port_for_file(aws_status_file: str | Path) -> AwsNarrowWritePort:
    if is_live_aws_profile_file(aws_status_file):
        return FilesystemLiveAwsProfileAdapter(aws_status_file)
    return FilesystemAwsNarrowWriteAdapter(aws_status_file)


def _normalize_narrow_write_request(
    payload: dict[str, Any] | None,
) -> tuple[AdminTenantScope, dict[str, Any]]:
    if payload is None:
        raise ValueError("admin.aws.narrow_write requires a request payload")
    if not isinstance(payload, dict):
        raise ValueError("admin.aws.narrow_write request payload must be a dict")
    schema = _as_text(payload.get("schema"))
    if schema != ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA:
        raise ValueError(f"admin.aws.narrow_write request.schema must be {ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA}")
    tenant_scope = AdminTenantScope.from_value(payload.get("tenant_scope"))
    return tenant_scope, {
        "tenant_scope_id": tenant_scope.scope_id,
        "focus_subject": payload.get("focus_subject"),
        "profile_id": payload.get("profile_id"),
        "selected_verified_sender": payload.get("selected_verified_sender"),
    }


def run_admin_aws_read_only(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_status_file: str | Path | None = None,
    aws_status_port: AwsReadOnlyStatusPort | None = None,
) -> dict[str, Any]:
    tenant_scope = _normalize_request(request_payload)
    launch_decision = resolve_admin_tool_launch(
        slice_id=AWS_READ_ONLY_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
    )

    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message] if message else [],
            error=build_admin_runtime_error(code=launch_decision.reason_code, message=message),
        )

    if aws_status_port is None and aws_status_file is None:
        message = "AWS read-only status source is not configured."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="status_source_not_configured", message=message),
        )

    adapter = aws_status_port or _aws_read_only_status_port_for_file(aws_status_file)
    service = AwsOperationalVisibilityService(adapter)
    surface = service.read_surface(tenant_scope.scope_id)

    if surface is None:
        message = "No AWS read-only status snapshot matched the requested tenant scope."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="status_snapshot_not_found", message=message),
        )

    surface_payload = _build_read_only_surface_payload(
        tenant_scope=tenant_scope,
        visibility=surface.to_dict(),
        active_surface_id=AWS_READ_ONLY_SLICE_ID,
    )

    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND1_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=AWS_READ_ONLY_SLICE_ID,
        slice_id=AWS_READ_ONLY_SLICE_ID,
        entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=launch_decision.to_dict(),
        surface_payload=surface_payload,
        warnings=list(surface_payload["compatibility_warnings"]),
        error=None,
    )


def run_admin_aws_csm_sandbox_read_only(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_sandbox_status_file: str | Path | None = None,
    aws_status_port: AwsReadOnlyStatusPort | None = None,
) -> dict[str, Any]:
    """Read-only AWS operational visibility using a **sandbox** profile path (internal audience only)."""
    tenant_scope = _normalize_request(request_payload)
    if tenant_scope.audience != "internal":
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state={
                "schema": "mycite.v2.admin.shell.state.v1",
                "slice_id": AWS_CSM_SANDBOX_SLICE_ID,
                "entrypoint_id": AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
                "allowed": False,
                "selection_status": "audience_denied",
                "reason_code": "audience_not_allowed",
                "reason_message": "AWS-CSM sandbox read-only requires internal audience.",
            },
            surface_payload=None,
            warnings=["AWS-CSM sandbox requires internal audience."],
            error=build_admin_runtime_error(
                code="audience_not_allowed",
                message="AWS-CSM sandbox read-only requires internal audience.",
            ),
        )

    launch_decision = resolve_admin_tool_launch(
        slice_id=AWS_CSM_SANDBOX_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    )

    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message] if message else [],
            error=build_admin_runtime_error(code=launch_decision.reason_code, message=message),
        )

    if aws_status_port is None and aws_sandbox_status_file is None:
        message = "AWS-CSM sandbox status file is not configured."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="status_source_not_configured", message=message),
        )

    if aws_status_port is not None:
        adapter = aws_status_port
    else:
        try:
            validated = validate_staged_aws_csm_profile_path(aws_sandbox_status_file)
        except ValueError as exc:
            message = str(exc)
            return build_admin_runtime_envelope(
                admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
                exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
                tenant_scope=tenant_scope.to_dict(),
                requested_slice_id=AWS_CSM_SANDBOX_SLICE_ID,
                slice_id=AWS_CSM_SANDBOX_SLICE_ID,
                entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
                read_write_posture="read-only",
                shell_state=launch_decision.to_dict(),
                surface_payload=None,
                warnings=[message],
                error=build_admin_runtime_error(code="sandbox_profile_invalid", message=message),
            )
        adapter = _aws_read_only_status_port_for_file(validated)
    service = AwsOperationalVisibilityService(adapter)
    surface = service.read_surface(tenant_scope.scope_id)

    if surface is None:
        message = "No AWS read-only status snapshot matched the requested tenant scope."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="status_snapshot_not_found", message=message),
        )

    surface_payload = _build_read_only_surface_payload(
        tenant_scope=tenant_scope,
        visibility=surface.to_dict(),
        active_surface_id=AWS_CSM_SANDBOX_SLICE_ID,
    )

    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
        exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=AWS_CSM_SANDBOX_SLICE_ID,
        slice_id=AWS_CSM_SANDBOX_SLICE_ID,
        entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=launch_decision.to_dict(),
        surface_payload=surface_payload,
        warnings=list(surface_payload["compatibility_warnings"]),
        error=None,
    )


def run_admin_aws_narrow_write(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_status_file: str | Path | None = None,
    audit_storage_file: str | Path | None = None,
    aws_narrow_write_port: AwsNarrowWritePort | None = None,
) -> dict[str, Any]:
    tenant_scope, write_request = _normalize_narrow_write_request(request_payload)
    launch_decision = resolve_admin_tool_launch(
        slice_id=AWS_NARROW_WRITE_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
    )

    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND2_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_NARROW_WRITE_SLICE_ID,
            slice_id=AWS_NARROW_WRITE_SLICE_ID,
            entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message] if message else [],
            error=build_admin_runtime_error(code=launch_decision.reason_code, message=message),
        )

    if aws_narrow_write_port is None and aws_status_file is None:
        message = "AWS narrow write requires an existing status snapshot file."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND2_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_NARROW_WRITE_SLICE_ID,
            slice_id=AWS_NARROW_WRITE_SLICE_ID,
            entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="status_source_not_configured", message=message),
        )

    if audit_storage_file is None:
        message = "AWS narrow write requires the local audit storage path."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND2_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_NARROW_WRITE_SLICE_ID,
            slice_id=AWS_NARROW_WRITE_SLICE_ID,
            entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="audit_log_not_configured", message=message),
        )

    write_adapter = aws_narrow_write_port or _aws_narrow_write_port_for_file(aws_status_file)
    write_service = AwsNarrowWriteService(write_adapter)
    outcome = write_service.apply_write(write_request)

    audit_service = LocalAuditService(FilesystemAuditLogAdapter(audit_storage_file))
    audit_receipt = audit_service.append_record(outcome.to_local_audit_payload())

    confirmed_read_only_surface = _build_read_only_surface_payload(
        tenant_scope=tenant_scope,
        visibility=outcome.confirmed_visibility.to_dict(),
    )
    surface_payload = {
        "schema": ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA,
        "active_surface_id": AWS_NARROW_WRITE_SLICE_ID,
        "writable_field_set": ["selected_verified_sender"],
        "requested_change": {
            "profile_id": outcome.command.profile_id,
            "selected_verified_sender": outcome.command.selected_verified_sender,
        },
        "confirmed_read_only_surface": confirmed_read_only_surface,
        "audit": audit_receipt.to_dict(),
        "rollback_reference": AWS_NARROW_WRITE_RECOVERY_REFERENCE,
        "write_status": "applied",
    }

    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND2_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=AWS_NARROW_WRITE_SLICE_ID,
        slice_id=AWS_NARROW_WRITE_SLICE_ID,
        entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
        read_write_posture="write",
        shell_state=launch_decision.to_dict(),
        surface_payload=surface_payload,
        warnings=list(confirmed_read_only_surface["compatibility_warnings"]),
        error=None,
    )


def _normalize_csm_onboarding_request(
    payload: dict[str, Any] | None,
) -> tuple[AdminTenantScope, dict[str, Any]]:
    if payload is None:
        raise ValueError("admin.aws.csm_onboarding requires a request payload")
    if not isinstance(payload, dict):
        raise ValueError("admin.aws.csm_onboarding request payload must be a dict")
    schema = _as_text(payload.get("schema"))
    if schema != ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA:
        raise ValueError(
            f"admin.aws.csm_onboarding request.schema must be {ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA}"
        )
    tenant_scope = AdminTenantScope.from_value(payload.get("tenant_scope"))
    return tenant_scope, payload


def run_admin_aws_csm_onboarding(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_status_file: str | Path | None = None,
    audit_storage_file: str | Path | None = None,
    onboarding_profile_store: AwsCsmOnboardingProfileStorePort | None = None,
    onboarding_cloud_port: AwsCsmOnboardingCloudPort | None = None,
) -> dict[str, Any]:
    tenant_scope, full_request = _normalize_csm_onboarding_request(request_payload)
    launch_decision = resolve_admin_tool_launch(
        slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    )

    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message] if message else [],
            error=build_admin_runtime_error(code=launch_decision.reason_code, message=message),
        )

    if onboarding_profile_store is None and aws_status_file is None:
        message = "AWS CSM onboarding requires an existing live profile file."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="status_source_not_configured", message=message),
        )

    if audit_storage_file is None:
        message = "AWS CSM onboarding requires the local audit storage path."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="audit_log_not_configured", message=message),
        )

    profile_store = onboarding_profile_store or FilesystemAwsCsmOnboardingProfileStore(aws_status_file)
    cloud = onboarding_cloud_port or AwsCsmOnboardingUnconfiguredCloudPort()
    service = AwsCsmOnboardingService(profile_store=profile_store, cloud=cloud)

    try:
        outcome = service.apply(full_request)
    except AwsCsmOnboardingPolicyError as exc:
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[str(exc)],
            error=build_admin_runtime_error(code=exc.code, message=str(exc)),
        )
    except ValueError as exc:
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[str(exc)],
            error=build_admin_runtime_error(code="onboarding_rejected", message=str(exc)),
        )

    read_path = aws_status_file
    if read_path is None or not is_live_aws_profile_file(read_path):
        message = "AWS CSM onboarding read-after-write requires a live profile file path."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="read_after_write_not_configured", message=message),
        )

    read_adapter = FilesystemLiveAwsProfileAdapter(read_path)
    vis_service = AwsOperationalVisibilityService(read_adapter)
    surface = vis_service.read_surface(tenant_scope.scope_id)
    if surface is None:
        message = "Read-after-write visibility failed after onboarding write."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            read_write_posture="write",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="read_after_write_failed", message=message),
        )

    audit_service = LocalAuditService(FilesystemAuditLogAdapter(audit_storage_file))
    audit_receipt = audit_service.append_record(outcome.to_local_audit_payload())

    confirmed_read_only_surface = _build_read_only_surface_payload(
        tenant_scope=tenant_scope,
        visibility=surface.to_dict(),
        active_surface_id=AWS_CSM_ONBOARDING_SLICE_ID,
    )
    surface_payload = {
        "schema": ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA,
        "active_surface_id": AWS_CSM_ONBOARDING_SLICE_ID,
        "onboarding_action": outcome.command.onboarding_action,
        "updated_sections": list(outcome.updated_sections),
        "confirmed_read_only_surface": confirmed_read_only_surface,
        "audit": audit_receipt.to_dict(),
        "rollback_reference": AWS_CSM_ONBOARDING_RECOVERY_REFERENCE,
        "write_status": "applied",
    }

    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
        slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
        entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
        read_write_posture="write",
        shell_state=launch_decision.to_dict(),
        surface_payload=surface_payload,
        warnings=list(confirmed_read_only_surface["compatibility_warnings"]),
        error=None,
    )
