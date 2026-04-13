from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAuditLogAdapter,
    FilesystemAwsCsmOnboardingProfileStore,
    FilesystemAwsCsmNewsletterStateAdapter,
    FilesystemAwsNarrowWriteAdapter,
    FilesystemAwsReadOnlyStatusAdapter,
    FilesystemLiveAwsProfileAdapter,
    is_live_aws_profile_file,
)
from MyCiteV2.packages.adapters.event_transport import AwsEc2RoleNewsletterCloudAdapter
from MyCiteV2.packages.modules.cross_domain.aws_csm_onboarding import (
    AwsCsmOnboardingService,
    AwsCsmOnboardingUnconfiguredCloudPort,
)
from MyCiteV2.packages.modules.cross_domain.aws_csm_newsletter import AwsCsmNewsletterService
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
    AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
    AdminTenantScope,
    build_portal_activity_dispatch_bodies,
    resolve_admin_tool_launch,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_FAMILY_HOME_SURFACE_SCHEMA,
    ADMIN_AWS_CSM_NEWSLETTER_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_NEWSLETTER_SURFACE_SCHEMA,
    ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA,
    ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
    ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA,
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    AWS_CSM_ONBOARDING_RECOVERY_REFERENCE,
    AWS_NARROW_WRITE_RECOVERY_REFERENCE,
    admin_tool_exposure_config_enabled,
    build_admin_runtime_envelope,
    build_admin_runtime_error,
)

ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID = "admin.aws.newsletter"


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


def _normalize_family_request(payload: dict[str, Any] | None) -> AdminTenantScope:
    if payload is None:
        raise ValueError("admin.aws.family_home requires a request payload")
    if not isinstance(payload, dict):
        raise ValueError("admin.aws.family_home request payload must be a dict")
    schema = _as_text(payload.get("schema"))
    if schema != ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA:
        raise ValueError(
            f"admin.aws.family_home request.schema must be {ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA}"
        )
    return AdminTenantScope.from_value(payload.get("tenant_scope"))


def _normalize_newsletter_request(
    payload: dict[str, Any] | None,
) -> tuple[AdminTenantScope, str, str, str]:
    if payload is None:
        raise ValueError("admin.aws.newsletter requires a request payload")
    if not isinstance(payload, dict):
        raise ValueError("admin.aws.newsletter request payload must be a dict")
    schema = _as_text(payload.get("schema"))
    if schema != ADMIN_AWS_CSM_NEWSLETTER_REQUEST_SCHEMA:
        raise ValueError(
            f"admin.aws.newsletter request.schema must be {ADMIN_AWS_CSM_NEWSLETTER_REQUEST_SCHEMA}"
        )
    tenant_scope = AdminTenantScope.from_value(payload.get("tenant_scope"))
    return (
        tenant_scope,
        _as_text(payload.get("domain")).lower(),
        _as_text(payload.get("action")) or "inspect",
        _as_text(payload.get("selected_author_profile_id")),
    )


def _resolve_aws_family_launch(tenant_scope: AdminTenantScope) -> Any:
    return resolve_admin_tool_launch(
        slice_id=AWS_READ_ONLY_SLICE_ID,
        audience=tenant_scope.audience,
        expected_entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
    )


def _dispatcher_callback_url(domain: str) -> str:
    scheme = "https"
    return f"{scheme}://{_as_text(domain).lower()}/__fnd/newsletter/dispatch-result"


def _inbound_callback_url(domain: str) -> str:
    scheme = "https"
    return f"{scheme}://{_as_text(domain).lower()}/__fnd/newsletter/inbound-capture"


def _newsletter_service(*, private_dir: str | Path, portal_tenant_id: str) -> AwsCsmNewsletterService:
    return AwsCsmNewsletterService(
        FilesystemAwsCsmNewsletterStateAdapter(private_dir),
        AwsEc2RoleNewsletterCloudAdapter(),
        tenant_id=portal_tenant_id,
    )


def _preferred_family_domain(
    *,
    visibility: dict[str, Any],
    domain_states: list[dict[str, Any]],
) -> dict[str, Any]:
    if not domain_states:
        return {}
    preferred_domain = _as_text(
        ((visibility.get("canonical_newsletter_operational_profile") or {}).get("domain"))
    ).lower()
    if not preferred_domain:
        allowed_domains = list(visibility.get("allowed_send_domains") or [])
        preferred_domain = _as_text(allowed_domains[0] if allowed_domains else "").lower()
    if not preferred_domain:
        sender = _as_text(visibility.get("selected_verified_sender")).lower()
        if "@" in sender:
            preferred_domain = sender.split("@", 1)[1]
    for state in domain_states:
        if _as_text(state.get("domain")).lower() == preferred_domain:
            return state
    return domain_states[0]


def _build_family_surface_payload(
    *,
    tenant_scope: AdminTenantScope,
    visibility: dict[str, Any],
    private_dir: str | Path,
    tool_exposure_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    service = _newsletter_service(private_dir=private_dir, portal_tenant_id=tenant_scope.scope_id)
    newsletter_enabled = admin_tool_exposure_config_enabled(
        tool_exposure_policy,
        tool_id="aws_csm_newsletter",
    )
    domains = service.list_domains()
    domain_states = [
        service.resolve_domain_state(
            domain=domain,
            dispatcher_callback_url=_dispatcher_callback_url(domain),
            inbound_callback_url=_inbound_callback_url(domain),
        )
        for domain in domains
    ] if newsletter_enabled else []
    family_health = service.family_health(
        domains=domains if newsletter_enabled else [],
        dispatcher_callback_builder=_dispatcher_callback_url,
        inbound_callback_builder=_inbound_callback_url,
    ) if newsletter_enabled else {"schema": "mycite.v2.admin.aws_csm.family_health.v1", "status": "newsletter_disabled"}
    shell_requests = build_portal_activity_dispatch_bodies(portal_tenant_id=tenant_scope.scope_id)
    selected_domain_state = _preferred_family_domain(
        visibility=visibility,
        domain_states=domain_states,
    )
    return {
        "schema": ADMIN_AWS_CSM_FAMILY_HOME_SURFACE_SCHEMA,
        "active_surface_id": AWS_READ_ONLY_SLICE_ID,
        "tenant_scope_id": tenant_scope.scope_id,
        "current_admin_band": ADMIN_BAND1_AWS_NAME,
        "exposure_status": ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        "read_write_posture": "read-only",
        "primary_read_only": visibility,
        "newsletter_enabled": newsletter_enabled,
        "domain_states": domain_states,
        "selected_domain_state": selected_domain_state,
        "family_health": family_health,
        "newsletter_request_contract": {
            "route": "/portal/api/v2/admin/aws/newsletter",
            "request_schema": ADMIN_AWS_CSM_NEWSLETTER_REQUEST_SCHEMA,
            "fixed_request_fields": {
                "tenant_scope": tenant_scope.to_dict(),
            },
        },
        "subsurface_navigation": {
            "aws_read_only_route": "/portal/api/v2/admin/aws/read-only",
            "narrow_write_shell_request": shell_requests.get(AWS_NARROW_WRITE_SLICE_ID),
            "onboarding_shell_request": shell_requests.get(AWS_CSM_ONBOARDING_SLICE_ID),
            "sandbox_shell_request": shell_requests.get(AWS_CSM_SANDBOX_SLICE_ID)
            if admin_tool_exposure_config_enabled(tool_exposure_policy, tool_id="aws_csm_sandbox")
            else None,
            "newsletter_route": "/portal/api/v2/admin/aws/newsletter",
        },
        "gated_subsurfaces": {
            "newsletter": not newsletter_enabled,
            "sandbox": not admin_tool_exposure_config_enabled(tool_exposure_policy, tool_id="aws_csm_sandbox"),
        },
    }


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
    tool_id: str,
    admin_band: str,
    exposure_status: str,
    tenant_scope: AdminTenantScope,
    requested_slice_id: str,
    slice_id: str,
    entrypoint_id: str,
    read_write_posture: str,
    launch_decision: Any,
) -> dict[str, Any] | None:
    if tool_exposure_policy is None:
        return None
    if admin_tool_exposure_config_enabled(tool_exposure_policy, tool_id=tool_id):
        return None
    message = "Requested admin tool is disabled by instance tool_exposure configuration."
    return build_admin_runtime_envelope(
        admin_band=admin_band,
        exposure_status=exposure_status,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=requested_slice_id,
        slice_id=slice_id,
        entrypoint_id=entrypoint_id,
        read_write_posture=read_write_posture,
        shell_state=_tool_not_exposed_shell_state(launch_decision, message=message),
        surface_payload=None,
        warnings=[message],
        error=build_admin_runtime_error(code=ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE, message=message),
    )


def run_admin_aws_read_only(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_status_file: str | Path | None = None,
    aws_status_port: AwsReadOnlyStatusPort | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_scope = _normalize_request(request_payload)
    launch_decision = _resolve_aws_family_launch(tenant_scope)

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

    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tool_id="aws",
        admin_band=ADMIN_BAND1_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        tenant_scope=tenant_scope,
        requested_slice_id=AWS_READ_ONLY_SLICE_ID,
        slice_id=AWS_READ_ONLY_SLICE_ID,
        entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated

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


def run_admin_aws_csm_family_home(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_status_file: str | Path | None = None,
    aws_status_port: AwsReadOnlyStatusPort | None = None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_scope = _normalize_family_request(request_payload)
    launch_decision = _resolve_aws_family_launch(tenant_scope)

    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message] if message else [],
            error=build_admin_runtime_error(code=launch_decision.reason_code, message=message),
        )

    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tool_id="aws",
        admin_band=ADMIN_BAND1_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        tenant_scope=tenant_scope,
        requested_slice_id=AWS_READ_ONLY_SLICE_ID,
        slice_id=AWS_READ_ONLY_SLICE_ID,
        entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
        read_write_posture="read-only",
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated

    if private_dir is None:
        message = "AWS-CSM family home requires the private state root."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="private_state_not_configured", message=message),
        )

    if aws_status_port is None and aws_status_file is None:
        message = "AWS read-only status source is not configured."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
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
            entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="status_snapshot_not_found", message=message),
        )

    read_only_payload = _build_read_only_surface_payload(
        tenant_scope=tenant_scope,
        visibility=surface.to_dict(),
        active_surface_id=AWS_READ_ONLY_SLICE_ID,
    )
    family_payload = _build_family_surface_payload(
        tenant_scope=tenant_scope,
        visibility=read_only_payload,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    warnings = list(read_only_payload.get("compatibility_warnings") or [])
    for state in list(family_payload.get("domain_states") or []):
        warnings.extend(list((state or {}).get("warnings") or []))
    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND1_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=AWS_READ_ONLY_SLICE_ID,
        slice_id=AWS_READ_ONLY_SLICE_ID,
        entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=launch_decision.to_dict(),
        surface_payload=family_payload,
        warnings=warnings,
        error=None,
    )


def run_admin_aws_csm_newsletter(
    request_payload: dict[str, Any] | None = None,
    *,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_scope, domain, action, selected_author_profile_id = _normalize_newsletter_request(request_payload)
    launch_decision = _resolve_aws_family_launch(tenant_scope)
    if not launch_decision.allowed:
        message = launch_decision.reason_message
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message] if message else [],
            error=build_admin_runtime_error(code=launch_decision.reason_code, message=message),
        )
    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tool_id="aws",
        admin_band=ADMIN_BAND1_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        tenant_scope=tenant_scope,
        requested_slice_id=AWS_READ_ONLY_SLICE_ID,
        slice_id=AWS_READ_ONLY_SLICE_ID,
        entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
        read_write_posture="read-only",
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated
    if not admin_tool_exposure_config_enabled(tool_exposure_policy, tool_id="aws_csm_newsletter"):
        message = "Requested admin tool is disabled by instance tool_exposure configuration."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=_tool_not_exposed_shell_state(launch_decision, message=message),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code=ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE, message=message),
        )
    if private_dir is None:
        message = "AWS-CSM newsletter state requires the private state root."
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[message],
            error=build_admin_runtime_error(code="private_state_not_configured", message=message),
        )
    service = _newsletter_service(private_dir=private_dir, portal_tenant_id=tenant_scope.scope_id)
    available_domains = service.list_domains()
    selected_domain = domain or (available_domains[0] if available_domains else "")
    if not selected_domain:
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=["No AWS-CSM newsletter domains are available."],
            error=build_admin_runtime_error(code="domain_not_found", message="No AWS-CSM newsletter domains are available."),
        )
    try:
        if action == "select_author":
            domain_state = service.select_author(
                domain=selected_domain,
                selected_author_profile_id=selected_author_profile_id,
                dispatcher_callback_url=_dispatcher_callback_url(selected_domain),
                inbound_callback_url=_inbound_callback_url(selected_domain),
            )
            action_result: dict[str, Any] = {"status": "selected_author_updated"}
        elif action == "reprocess_latest_inbound":
            action_result = service.reprocess_latest_inbound(
                domain=selected_domain,
                dispatcher_callback_url=_dispatcher_callback_url(selected_domain),
                inbound_callback_url=_inbound_callback_url(selected_domain),
            )
            domain_state = service.resolve_domain_state(
                domain=selected_domain,
                dispatcher_callback_url=_dispatcher_callback_url(selected_domain),
                inbound_callback_url=_inbound_callback_url(selected_domain),
            )
        else:
            domain_state = service.resolve_domain_state(
                domain=selected_domain,
                dispatcher_callback_url=_dispatcher_callback_url(selected_domain),
                inbound_callback_url=_inbound_callback_url(selected_domain),
            )
            action_result = {"status": "inspected"}
    except LookupError as exc:
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[str(exc)],
            error=build_admin_runtime_error(code="domain_not_found", message=str(exc)),
        )
    except (PermissionError, ValueError) as exc:
        return build_admin_runtime_envelope(
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            tenant_scope=tenant_scope.to_dict(),
            requested_slice_id=AWS_READ_ONLY_SLICE_ID,
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
            read_write_posture="read-only",
            shell_state=launch_decision.to_dict(),
            surface_payload=None,
            warnings=[str(exc)],
            error=build_admin_runtime_error(code="newsletter_action_rejected", message=str(exc)),
        )
    return build_admin_runtime_envelope(
        admin_band=ADMIN_BAND1_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
        tenant_scope=tenant_scope.to_dict(),
        requested_slice_id=AWS_READ_ONLY_SLICE_ID,
        slice_id=AWS_READ_ONLY_SLICE_ID,
        entrypoint_id=ADMIN_AWS_CSM_NEWSLETTER_ENTRYPOINT_ID,
        read_write_posture="read-only",
        shell_state=launch_decision.to_dict(),
        surface_payload={
            "schema": ADMIN_AWS_CSM_NEWSLETTER_SURFACE_SCHEMA,
            "active_surface_id": AWS_READ_ONLY_SLICE_ID,
            "domain_state": domain_state,
            "action": action,
            "action_result": action_result,
        },
        warnings=list((domain_state or {}).get("warnings") or []),
        error=None,
    )


def run_admin_aws_csm_sandbox_read_only(
    request_payload: dict[str, Any] | None = None,
    *,
    aws_sandbox_status_file: str | Path | None = None,
    aws_status_port: AwsReadOnlyStatusPort | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
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

    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tool_id="aws_csm_sandbox",
        admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
        exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
        tenant_scope=tenant_scope,
        requested_slice_id=AWS_CSM_SANDBOX_SLICE_ID,
        slice_id=AWS_CSM_SANDBOX_SLICE_ID,
        entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
        read_write_posture="read-only",
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated

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
    tool_exposure_policy: dict[str, Any] | None = None,
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

    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tool_id="aws_narrow_write",
        admin_band=ADMIN_BAND2_AWS_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
        tenant_scope=tenant_scope,
        requested_slice_id=AWS_NARROW_WRITE_SLICE_ID,
        slice_id=AWS_NARROW_WRITE_SLICE_ID,
        entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
        read_write_posture="write",
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated

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
    tool_exposure_policy: dict[str, Any] | None = None,
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

    gated = _config_gate_envelope(
        tool_exposure_policy=tool_exposure_policy,
        tool_id="aws_csm_onboarding",
        admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
        exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
        tenant_scope=tenant_scope,
        requested_slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
        slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
        entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
        read_write_posture="write",
        launch_decision=launch_decision,
    )
    if gated is not None:
        return gated

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
