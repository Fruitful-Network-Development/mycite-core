from __future__ import annotations

from typing import Any

from tools._shared.tool_contracts.service_catalog import AWS_CSM_DEFAULT_REGION, AWS_CSM_PROFILE_SCHEMA


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    token = _text(value).lower()
    return token in {"1", "true", "yes", "on"}


def _aws_csm_default_smtp_host(region: str) -> str:
    token = _text(region) or AWS_CSM_DEFAULT_REGION
    return f"email-smtp.{token}.amazonaws.com"


def normalize_aws_csm_profile_payload(payload: Any, *, profile_hint: str = "") -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ({}, ["profile payload must be a JSON object"], warnings)

    body = dict(payload)
    identity_raw = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    smtp_raw = body.get("smtp") if isinstance(body.get("smtp"), dict) else {}
    verification_raw = body.get("verification") if isinstance(body.get("verification"), dict) else {}
    provider_raw = body.get("provider") if isinstance(body.get("provider"), dict) else {}
    workflow_raw = body.get("workflow") if isinstance(body.get("workflow"), dict) else {}

    profile_token = _text(profile_hint)
    tenant_id = _text(identity_raw.get("tenant_id") or body.get("tenant_id") or profile_token)
    if not tenant_id and profile_token:
        tenant_id = profile_token
    region = _text(identity_raw.get("region") or body.get("region")) or AWS_CSM_DEFAULT_REGION
    forward_to_email = _text(smtp_raw.get("forward_to_email") or body.get("forward_to_email"))
    single_user_email = _text(identity_raw.get("single_user_email") or body.get("single_user_email") or forward_to_email)
    send_as_email = _text(
        identity_raw.get("send_as_email") or smtp_raw.get("send_as_email") or body.get("alias_email")
    )
    profile_id = _text(identity_raw.get("profile_id") or body.get("profile_id"))
    if not profile_id and tenant_id:
        profile_id = f"aws-csm.{tenant_id}"
    credentials_source = _text(
        smtp_raw.get("credentials_source") or body.get("smtp_credentials_source") or body.get("credentials_source")
    ) or "operator_managed"
    credentials_secret_name = _text(
        smtp_raw.get("credentials_secret_name") or body.get("smtp_credentials_secret_name")
    )
    smtp_username = _text(smtp_raw.get("username") or body.get("smtp_username"))
    credentials_secret_state = _text(
        smtp_raw.get("credentials_secret_state") or body.get("smtp_credentials_secret_state")
    )
    if not credentials_secret_state:
        if credentials_secret_name and smtp_username:
            credentials_secret_state = "configured"
        elif credentials_secret_name:
            credentials_secret_state = "placeholder_present"
        else:
            credentials_secret_state = "missing"
    smtp_host = _text(smtp_raw.get("host") or body.get("smtp_host")) or _aws_csm_default_smtp_host(region)
    smtp_port = _text(smtp_raw.get("port") or body.get("smtp_port")) or "587"
    verification_status = _text(
        verification_raw.get("status") or provider_raw.get("gmail_send_as_status") or body.get("gmail_send_as_status")
    ) or "not_started"
    provider_status = _text(
        provider_raw.get("gmail_send_as_status") or body.get("gmail_send_as_status") or verification_status
    ) or "not_started"
    aws_identity_status = _text(
        provider_raw.get("aws_ses_identity_status") or body.get("aws_ses_identity_status")
    ) or "not_started"
    verification_code = _text(verification_raw.get("code") or body.get("verification_code"))
    verification_link = _text(verification_raw.get("link") or body.get("verification_link"))
    verification_portal_state = _text(verification_raw.get("portal_state") or body.get("verification_portal_state"))
    verified_provider_statuses = {"verified", "success", "active", "ready", "configured"}
    confirmed_send_as_statuses = {"active", "configured", "verified", "ready"}

    if not tenant_id:
        warnings.append("recommended field missing: identity.tenant_id")
    if not profile_id:
        warnings.append("recommended field missing: identity.profile_id")

    identity = {
        "profile_id": profile_id,
        "tenant_id": tenant_id,
        "domain": _text(identity_raw.get("domain") or body.get("domain")),
        "region": region,
        "single_user_msn_id": _text(identity_raw.get("single_user_msn_id") or body.get("single_user_msn_id")),
        "single_user_email": single_user_email,
        "send_as_email": send_as_email,
    }
    smtp = {
        "host": smtp_host,
        "port": smtp_port,
        "username": smtp_username,
        "credentials_source": credentials_source,
        "handoff_ready": _boolish(smtp_raw.get("handoff_ready") or body.get("smtp_handoff_ready")),
        "credentials_secret_name": credentials_secret_name,
        "credentials_secret_state": credentials_secret_state,
        "send_as_email": _text(smtp_raw.get("send_as_email") or send_as_email),
        "local_part": _text(smtp_raw.get("local_part") or body.get("local_part")),
        "forward_to_email": forward_to_email,
        "forwarding_status": _text(smtp_raw.get("forwarding_status") or body.get("forwarding_status")),
    }
    verification = {
        "status": verification_status,
        "code": verification_code,
        "link": verification_link,
        "email_received_at": _text(
            verification_raw.get("email_received_at") or body.get("verification_email_received_at")
        ),
        "verified_at": _text(verification_raw.get("verified_at") or body.get("verified_at")),
        "portal_state": verification_portal_state,
    }
    provider = {
        "gmail_send_as_status": provider_status,
        "aws_ses_identity_status": aws_identity_status,
        "last_checked_at": _text(provider_raw.get("last_checked_at") or body.get("provider_last_checked_at")),
    }

    configuration_required = {
        "identity.domain": _text(identity.get("domain")),
        "identity.single_user_email": _text(identity.get("single_user_email")),
        "smtp.send_as_email": _text(smtp.get("send_as_email")),
        "smtp.host": _text(smtp.get("host")),
        "smtp.port": _text(smtp.get("port")),
        "smtp.username": _text(smtp.get("username")),
        "smtp.credentials_source": _text(smtp.get("credentials_source")),
    }
    configuration_blockers = [key for key, value in configuration_required.items() if not value]
    if aws_identity_status not in verified_provider_statuses:
        configuration_blockers.append("provider.aws_ses_identity_status")
    gmail_handoff_blockers: list[str] = []
    if verification_status not in confirmed_send_as_statuses:
        gmail_handoff_blockers.append("verification.status")
    if provider_status not in confirmed_send_as_statuses:
        gmail_handoff_blockers.append("provider.gmail_send_as_status")
    missing_required = list(configuration_blockers)
    for key in gmail_handoff_blockers:
        if key not in missing_required:
            missing_required.append(key)
    send_as_confirmed = provider_status in confirmed_send_as_statuses or verification_status == "verified"
    ready_for_user_handoff = not configuration_blockers
    smtp["handoff_ready"] = ready_for_user_handoff
    handoff_status = "staging_required"
    if send_as_confirmed:
        handoff_status = "send_as_confirmed"
    elif ready_for_user_handoff:
        handoff_status = "ready_for_gmail_handoff"
    if not verification_portal_state:
        if send_as_confirmed:
            verification_portal_state = "verified"
        elif verification_code or verification_link or verification_status in {"pending", "verification_pending"}:
            verification_portal_state = "verification_pending"
        elif ready_for_user_handoff:
            verification_portal_state = "awaiting_gmail_handoff"
        else:
            verification_portal_state = "awaiting_operator_setup"
    verification["portal_state"] = verification_portal_state
    workflow = {
        "schema": _text(workflow_raw.get("schema")) or "mycite.service_tool.aws_csm.onboarding.v1",
        "flow": _text(workflow_raw.get("flow")) or "single_user_send_as",
        "configuration_blockers_now": configuration_blockers,
        "gmail_handoff_blockers_now": gmail_handoff_blockers,
        "missing_required_now": missing_required,
        "handoff_status": handoff_status,
        "completion_boundary": "completed" if send_as_confirmed else "gmail_inbox_dependent",
        "is_ready_for_user_handoff": ready_for_user_handoff,
        "is_send_as_confirmed": send_as_confirmed,
    }

    if not _text(identity.get("domain")):
        errors.append("missing required field: identity.domain")
    if not _text(smtp.get("send_as_email")):
        errors.append("missing required field: smtp.send_as_email")

    return (
        {
            "schema": AWS_CSM_PROFILE_SCHEMA,
            "identity": identity,
            "smtp": smtp,
            "verification": verification,
            "provider": provider,
            "workflow": workflow,
        },
        errors,
        warnings,
    )

