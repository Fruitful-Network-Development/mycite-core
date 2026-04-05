from __future__ import annotations

from typing import Any

from packages.tools._shared.tool_contracts.service_catalog import (
    AWS_CSM_DEFAULT_REGION,
    AWS_CSM_PROFILE_SCHEMA,
)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    token = _text(value).lower()
    return token in {"1", "true", "yes", "on"}


def _has_capture_metadata(*, s3_uri: str, s3_key: str, captured_at: str, sender: str, subject: str) -> bool:
    return any([_text(s3_uri), _text(s3_key), _text(captured_at), _text(sender), _text(subject)])


def _aws_csm_default_smtp_host(region: str) -> str:
    token = _text(region) or AWS_CSM_DEFAULT_REGION
    return f"email-smtp.{token}.amazonaws.com"


def _mailbox_local_part(value: str) -> str:
    token = _text(value)
    if "@" not in token:
        return token
    return token.split("@", 1)[0].strip()


def _profile_hint_parts(profile_hint: str) -> tuple[str, str]:
    token = _text(profile_hint)
    if token.startswith("aws-csm."):
        token = token.removeprefix("aws-csm.")
    if not token:
        return "", ""
    parts = [part for part in token.split(".") if part]
    if not parts:
        return "", ""
    tenant_id = parts[0]
    mailbox_local_part = ".".join(parts[1:]) if len(parts) > 1 else ""
    return tenant_id, mailbox_local_part


def _default_role(*, mailbox_local_part: str, tenant_id: str) -> str:
    local_part = _text(mailbox_local_part).lower()
    if local_part == "technicalcontact":
        return "technical_contact"
    if tenant_id == "fnd" and local_part == "dylan":
        return "operator"
    if local_part:
        return "mailbox"
    return ""


def _default_secret_name(*, tenant_id: str, mailbox_local_part: str) -> str:
    tenant = _text(tenant_id)
    local_part = _text(mailbox_local_part)
    if tenant and local_part:
        return f"aws-cms/smtp/{tenant}.{local_part}"
    if tenant:
        return f"aws-cms/smtp/{tenant}"
    return ""


def _default_profile_id(*, tenant_id: str, mailbox_local_part: str) -> str:
    tenant = _text(tenant_id)
    local_part = _text(mailbox_local_part)
    if tenant and local_part:
        return f"aws-csm.{tenant}.{local_part}"
    if tenant:
        return f"aws-csm.{tenant}"
    return ""


def _has_gmail_confirmation_evidence(
    *,
    verification_link: str,
    verification_latest_message_reference: str,
    latest_message_has_verification_link: bool,
) -> bool:
    return bool(
        _text(verification_link)
        or _text(verification_latest_message_reference)
        or latest_message_has_verification_link
    )


def _credentials_secret_state(
    *,
    secret_name: str,
    username: str,
    explicit_state: str,
) -> str:
    token = _text(explicit_state)
    if token:
        return token
    if secret_name and username:
        return "configured"
    return "missing"


def _default_initiated(
    *,
    explicit: Any,
    smtp_username: str,
    credentials_secret_state: str,
    aws_identity_status: str,
    verification_status: str,
    provider_status: str,
) -> bool:
    if explicit not in {None, ""}:
        return _boolish(explicit)
    return any(
        [
            bool(_text(smtp_username)),
            _text(credentials_secret_state).lower() in {"configured", "auth_failed"},
            _text(aws_identity_status).lower() not in {"", "not_started"},
            _text(verification_status).lower() not in {"", "not_started"},
            _text(provider_status).lower() not in {"", "not_started"},
        ]
    )


def _receive_state(
    *,
    explicit_state: str,
    receive_routing_target: str,
    initiated: bool,
    receive_verified: bool,
    send_as_confirmed: bool,
    portal_native_display_ready: bool,
) -> str:
    token = _text(explicit_state).lower()
    if token == "staged":
        token = "receive_configured" if _text(receive_routing_target) else "receive_unconfigured"
    elif token == "inbound_pending":
        token = "receive_pending"
    elif token == "inbound_verified":
        token = "receive_verified"
    if token == "receive_legacy_dependent":
        token = "receive_verified" if (receive_verified or portal_native_display_ready) else "receive_pending"

    # Always derive the current receive state from live mailbox facts so stale
    # persisted states don't mask a newer capture or verification result.
    if not _text(receive_routing_target):
        derived = "receive_unconfigured"
    elif send_as_confirmed and receive_verified and portal_native_display_ready:
        derived = "receive_operational"
    elif receive_verified or portal_native_display_ready:
        derived = "receive_verified"
    elif initiated:
        derived = "receive_pending"
    else:
        derived = "receive_configured"

    return derived


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
    inbound_raw = body.get("inbound") if isinstance(body.get("inbound"), dict) else {}

    hinted_tenant, hinted_mailbox = _profile_hint_parts(profile_hint)
    tenant_id = _text(identity_raw.get("tenant_id") or body.get("tenant_id") or hinted_tenant)
    region = _text(identity_raw.get("region") or body.get("region")) or AWS_CSM_DEFAULT_REGION
    send_as_email = _text(
        identity_raw.get("send_as_email") or smtp_raw.get("send_as_email") or body.get("alias_email")
    )
    mailbox_local_part = _text(
        identity_raw.get("mailbox_local_part")
        or smtp_raw.get("local_part")
        or body.get("mailbox_local_part")
        or _mailbox_local_part(send_as_email)
        or hinted_mailbox
    )
    operator_inbox_target = _text(
        identity_raw.get("operator_inbox_target")
        or body.get("operator_inbox_target")
        or identity_raw.get("single_user_email")
        or body.get("single_user_email")
        or smtp_raw.get("forward_to_email")
        or body.get("forward_to_email")
    )
    profile_id = _text(identity_raw.get("profile_id") or body.get("profile_id")) or _default_profile_id(
        tenant_id=tenant_id,
        mailbox_local_part=mailbox_local_part,
    )
    role = _text(identity_raw.get("role") or body.get("role")) or _default_role(
        mailbox_local_part=mailbox_local_part,
        tenant_id=tenant_id,
    )
    credentials_source = _text(
        smtp_raw.get("credentials_source") or body.get("smtp_credentials_source") or body.get("credentials_source")
    ) or "operator_managed"
    credentials_secret_name = _text(
        smtp_raw.get("credentials_secret_name") or body.get("smtp_credentials_secret_name")
    ) or _default_secret_name(tenant_id=tenant_id, mailbox_local_part=mailbox_local_part)
    smtp_username = _text(smtp_raw.get("username") or body.get("smtp_username"))
    credentials_secret_state = _credentials_secret_state(
        secret_name=credentials_secret_name,
        username=smtp_username,
        explicit_state=_text(smtp_raw.get("credentials_secret_state") or body.get("smtp_credentials_secret_state")),
    )
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
    verification_email_received_at = _text(
        verification_raw.get("email_received_at") or body.get("verification_email_received_at")
    )
    verification_verified_at = _text(verification_raw.get("verified_at") or body.get("verified_at"))
    verification_latest_message_reference = _text(
        verification_raw.get("latest_message_reference")
        if "latest_message_reference" in verification_raw
        else body.get("verification_latest_message_reference", "")
    )
    verified_provider_statuses = {"verified", "success", "active", "ready", "configured"}
    confirmed_send_as_statuses = {"active", "configured", "verified", "ready"}

    initiated = _default_initiated(
        explicit=workflow_raw.get("initiated") if "initiated" in workflow_raw else body.get("initiated"),
        smtp_username=smtp_username,
        credentials_secret_state=credentials_secret_state,
        aws_identity_status=aws_identity_status,
        verification_status=verification_status,
        provider_status=provider_status,
    )
    initiated_at = _text(workflow_raw.get("initiated_at") or body.get("initiated_at"))

    receive_routing_target = _text(
        inbound_raw.get("receive_routing_target")
        or inbound_raw.get("operator_inbox_target")
        or body.get("receive_routing_target")
        or operator_inbox_target
    )
    latest_message_sender = _text(inbound_raw.get("latest_message_sender") or body.get("latest_message_sender"))
    latest_message_recipient = _text(inbound_raw.get("latest_message_recipient") or body.get("latest_message_recipient"))
    latest_message_subject = _text(inbound_raw.get("latest_message_subject") or body.get("latest_message_subject"))
    latest_message_captured_at = _text(
        inbound_raw.get("latest_message_captured_at") or body.get("latest_message_captured_at")
    )
    latest_message_s3_key = _text(inbound_raw.get("latest_message_s3_key") or body.get("latest_message_s3_key"))
    latest_message_s3_uri = _text(inbound_raw.get("latest_message_s3_uri") or body.get("latest_message_s3_uri"))
    latest_message_id = _text(inbound_raw.get("latest_message_id") or body.get("latest_message_id"))
    latest_message_has_verification_link = _boolish(
        inbound_raw.get("latest_message_has_verification_link") or body.get("latest_message_has_verification_link")
    )
    capture_source_kind = _text(inbound_raw.get("capture_source_kind") or body.get("capture_source_kind"))
    capture_source_reference = _text(
        inbound_raw.get("capture_source_reference") or body.get("capture_source_reference")
    )
    portal_native_display_ready = _boolish(
        inbound_raw.get("portal_native_display_ready") or body.get("portal_native_display_ready")
    )
    receive_last_checked_at = _text(inbound_raw.get("receive_last_checked_at") or body.get("receive_last_checked_at"))
    receive_verified_at = _text(inbound_raw.get("receive_verified_at") or body.get("receive_verified_at"))
    legacy_forwarder_dependency = _boolish(
        inbound_raw.get("legacy_forwarder_dependency")
        or body.get("legacy_forwarder_dependency")
    )
    receive_verified = _boolish(inbound_raw.get("receive_verified") or body.get("receive_verified"))
    has_capture_metadata = _has_capture_metadata(
        s3_uri=latest_message_s3_uri,
        s3_key=latest_message_s3_key,
        captured_at=latest_message_captured_at,
        sender=latest_message_sender,
        subject=latest_message_subject,
    )
    if not capture_source_reference:
        capture_source_reference = latest_message_s3_uri or latest_message_s3_key
    if not capture_source_kind and capture_source_reference:
        capture_source_kind = "s3_object"
    if not portal_native_display_ready:
        portal_native_display_ready = bool(capture_source_reference or has_capture_metadata)
    if not latest_message_has_verification_link:
        latest_message_has_verification_link = bool(_text(verification_link))
    has_confirmation_evidence = _has_gmail_confirmation_evidence(
        verification_link=verification_link,
        verification_latest_message_reference=verification_latest_message_reference,
        latest_message_has_verification_link=latest_message_has_verification_link,
    )
    if (
        verification_status in confirmed_send_as_statuses
        or provider_status in confirmed_send_as_statuses
        or verification_portal_state == "verified"
    ) and not has_confirmation_evidence:
        verification_status = "not_started"
        provider_status = "not_started"
        verification_portal_state = ""
        verification_verified_at = ""
    send_as_confirmed = provider_status in confirmed_send_as_statuses or verification_status == "verified"
    receive_state = _receive_state(
        explicit_state=_text(inbound_raw.get("receive_state") or body.get("receive_state")),
        receive_routing_target=receive_routing_target,
        initiated=initiated,
        receive_verified=receive_verified,
        send_as_confirmed=send_as_confirmed,
        portal_native_display_ready=portal_native_display_ready,
    )
    legacy_dependency_state = (
        "receive_legacy_dependent"
        if legacy_forwarder_dependency
        else ("portal_native_display" if portal_native_display_ready else "portal_native_pending")
    )
    legacy_replay_available = legacy_forwarder_dependency and bool(latest_message_id or latest_message_s3_uri or latest_message_s3_key)

    if not tenant_id:
        warnings.append("recommended field missing: identity.tenant_id")
    if not mailbox_local_part:
        warnings.append("recommended field missing: identity.mailbox_local_part")
    if not profile_id:
        warnings.append("recommended field missing: identity.profile_id")

    identity = {
        "profile_id": profile_id,
        "tenant_id": tenant_id,
        "domain": _text(identity_raw.get("domain") or body.get("domain")),
        "region": region,
        "mailbox_local_part": mailbox_local_part,
        "role": role,
        "profile_kind": "mailbox",
        "single_user_msn_id": _text(identity_raw.get("single_user_msn_id") or body.get("single_user_msn_id")),
        "single_user_email": operator_inbox_target,
        "operator_inbox_target": operator_inbox_target,
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
        "local_part": _text(smtp_raw.get("local_part") or body.get("local_part") or mailbox_local_part),
        "forward_to_email": operator_inbox_target,
        "forwarding_status": _text(smtp_raw.get("forwarding_status") or body.get("forwarding_status")),
    }
    verification = {
        "status": verification_status,
        "code": verification_code,
        "link": verification_link,
        "email_received_at": verification_email_received_at,
        "verified_at": verification_verified_at,
        "portal_state": verification_portal_state,
        "latest_message_reference": verification_latest_message_reference,
    }
    provider = {
        "gmail_send_as_status": provider_status,
        "aws_ses_identity_status": aws_identity_status,
        "last_checked_at": _text(provider_raw.get("last_checked_at") or body.get("provider_last_checked_at")),
    }
    inbound = {
        "receive_routing_target": receive_routing_target,
        "receive_state": receive_state,
        "receive_verified": receive_verified,
        "receive_last_checked_at": receive_last_checked_at,
        "receive_verified_at": receive_verified_at,
        "legacy_forwarder_dependency": legacy_forwarder_dependency,
        "legacy_dependency_state": legacy_dependency_state,
        "legacy_replay_available": legacy_replay_available,
        "portal_native_display_ready": portal_native_display_ready,
        "capture_source_kind": capture_source_kind,
        "capture_source_reference": capture_source_reference,
        "latest_message_sender": latest_message_sender,
        "latest_message_recipient": latest_message_recipient,
        "latest_message_subject": latest_message_subject,
        "latest_message_captured_at": latest_message_captured_at,
        "latest_message_s3_key": latest_message_s3_key,
        "latest_message_s3_uri": latest_message_s3_uri,
        "latest_message_id": latest_message_id,
        "latest_message_has_verification_link": latest_message_has_verification_link,
    }

    configuration_required = {
        "identity.domain": _text(identity.get("domain")),
        "identity.operator_inbox_target": _text(identity.get("operator_inbox_target")),
        "identity.mailbox_local_part": _text(identity.get("mailbox_local_part")),
        "smtp.send_as_email": _text(smtp.get("send_as_email")),
        "smtp.host": _text(smtp.get("host")),
        "smtp.port": _text(smtp.get("port")),
        "smtp.credentials_source": _text(smtp.get("credentials_source")),
    }
    configuration_blockers: list[str] = []
    if initiated:
        configuration_blockers = [key for key, value in configuration_required.items() if not value]
        if not _text(smtp.get("username")):
            configuration_blockers.append("smtp.username")
        if aws_identity_status not in verified_provider_statuses:
            configuration_blockers.append("provider.aws_ses_identity_status")
    gmail_handoff_blockers: list[str] = []
    if initiated:
        if verification_status not in confirmed_send_as_statuses:
            gmail_handoff_blockers.append("verification.status")
        if provider_status not in confirmed_send_as_statuses:
            gmail_handoff_blockers.append("provider.gmail_send_as_status")
    missing_required = list(configuration_blockers)
    for key in gmail_handoff_blockers:
        if key not in missing_required:
            missing_required.append(key)
    ready_for_user_handoff = bool(initiated) and not configuration_blockers
    smtp["handoff_ready"] = ready_for_user_handoff
    inbound_blockers: list[str] = []
    if not _text(inbound.get("receive_routing_target")):
        inbound_blockers.append("inbound.receive_routing_target")
    if initiated and not bool(inbound.get("portal_native_display_ready")):
        inbound_blockers.append("inbound.portal_native_display_ready")
    if initiated and not bool(inbound.get("receive_verified")):
        inbound_blockers.append("inbound.receive_verified")
    operational_blockers = list(missing_required)
    for key in inbound_blockers:
        if key not in operational_blockers:
            operational_blockers.append(key)
    is_mailbox_operational = bool(send_as_confirmed) and not operational_blockers

    lifecycle_state = "uninitiated"
    if initiated:
        if is_mailbox_operational:
            lifecycle_state = "operational"
        elif send_as_confirmed:
            lifecycle_state = "send_as_verified"
        elif ready_for_user_handoff:
            lifecycle_state = "send_as_pending"
        elif _text(smtp.get("username")) or _text(smtp.get("credentials_secret_state")) == "configured":
            lifecycle_state = "smtp_configured"
        else:
            lifecycle_state = "staged"

    handoff_status = "uninitiated"
    if initiated:
        if send_as_confirmed:
            handoff_status = "send_as_confirmed"
        elif ready_for_user_handoff:
            handoff_status = "ready_for_gmail_handoff"
        elif _text(smtp.get("username")) or _text(smtp.get("credentials_secret_state")) == "configured":
            handoff_status = "smtp_configured"
        else:
            handoff_status = "staging_required"

    if not verification_portal_state:
        if send_as_confirmed:
            verification_portal_state = "verified"
        elif verification_email_received_at or verification_link or verification_code or verification_status in {"pending", "verification_pending"}:
            verification_portal_state = "verification_email_received"
        elif ready_for_user_handoff:
            verification_portal_state = "awaiting_gmail_handoff"
        elif not initiated:
            verification_portal_state = "staged"
        else:
            verification_portal_state = "awaiting_operator_setup"
    verification["portal_state"] = verification_portal_state

    workflow = {
        "schema": _text(workflow_raw.get("schema")) or "mycite.service_tool.aws_csm.onboarding.v1",
        "flow": _text(workflow_raw.get("flow")) or "mailbox_send_as",
        "initiated": bool(initiated),
        "initiated_at": initiated_at,
        "lifecycle_state": lifecycle_state,
        "configuration_blockers_now": configuration_blockers,
        "gmail_handoff_blockers_now": gmail_handoff_blockers,
        "inbound_blockers_now": inbound_blockers,
        "operational_blockers_now": operational_blockers,
        "missing_required_now": missing_required,
        "handoff_status": handoff_status,
        "completion_boundary": (
            "completed"
            if is_mailbox_operational
            else ("receive_path_pending" if send_as_confirmed else ("uninitiated" if not initiated else "gmail_inbox_dependent"))
        ),
        "is_ready_for_user_handoff": ready_for_user_handoff,
        "is_send_as_confirmed": send_as_confirmed,
        "is_receive_path_modeled": bool(_text(inbound.get("receive_routing_target"))),
        "is_receive_path_confirmed": bool(inbound.get("receive_verified")),
        "is_portal_native_inbound_ready": bool(inbound.get("portal_native_display_ready")),
        "is_mailbox_operational": is_mailbox_operational,
    }

    if not _text(identity.get("domain")):
        errors.append("missing required field: identity.domain")
    if not _text(identity.get("send_as_email")):
        errors.append("missing required field: identity.send_as_email")

    return (
        {
            "schema": AWS_CSM_PROFILE_SCHEMA,
            "identity": identity,
            "smtp": smtp,
            "verification": verification,
            "provider": provider,
            "workflow": workflow,
            "inbound": inbound,
        },
        errors,
        warnings,
    )
