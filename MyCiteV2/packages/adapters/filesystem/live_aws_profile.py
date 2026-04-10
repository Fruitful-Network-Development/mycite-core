from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyCiteV2.packages.ports.aws_narrow_write import (
    AwsNarrowWritePort,
    AwsNarrowWriteRequest,
    AwsNarrowWriteResult,
    AwsNarrowWriteSource,
)
from MyCiteV2.packages.ports.aws_read_only_status import (
    AwsReadOnlyStatusPort,
    AwsReadOnlyStatusRequest,
    AwsReadOnlyStatusResult,
    AwsReadOnlyStatusSource,
)

LIVE_AWS_PROFILE_SCHEMA = "mycite.service_tool.aws_csm.profile.v1"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() == "true"


def _email(value: object) -> str:
    return _as_text(value).lower()


def _local_part(email: str) -> str:
    return email.split("@", 1)[0] if "@" in email else ""


def is_live_aws_profile_file(storage_file: str | Path | None) -> bool:
    if storage_file is None:
        return False
    path = Path(storage_file)
    if not path.exists() or not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(payload, dict) and _as_text(payload.get("schema")) == LIVE_AWS_PROFILE_SCHEMA


class FilesystemLiveAwsProfileAdapter(AwsReadOnlyStatusPort, AwsNarrowWritePort):
    def __init__(self, storage_file: str | Path) -> None:
        self._storage_file = Path(storage_file)

    def read_aws_read_only_status(self, request: AwsReadOnlyStatusRequest) -> AwsReadOnlyStatusResult:
        normalized_request = (
            request if isinstance(request, AwsReadOnlyStatusRequest) else AwsReadOnlyStatusRequest.from_dict(request)
        )
        payload = self._read_profile_or_none()
        if payload is None or not self._matches_request(payload, normalized_request.tenant_scope_id):
            return AwsReadOnlyStatusResult(source=None)
        return AwsReadOnlyStatusResult(
            source=AwsReadOnlyStatusSource(
                payload=self._to_visibility_payload(
                    payload,
                    tenant_scope_id=normalized_request.tenant_scope_id,
                )
            )
        )

    def apply_aws_narrow_write(self, request: AwsNarrowWriteRequest) -> AwsNarrowWriteResult:
        normalized_request = (
            request if isinstance(request, AwsNarrowWriteRequest) else AwsNarrowWriteRequest.from_dict(request)
        )
        payload = self._read_profile()
        if not self._matches_request(payload, normalized_request.tenant_scope_id):
            raise ValueError("live aws profile tenant_scope_id does not match the stored profile")

        identity = _as_dict(payload.get("identity"))
        profile_id = _as_text(identity.get("profile_id"))
        if profile_id != normalized_request.profile_id:
            raise ValueError("live aws profile profile_id does not match the stored profile")

        selected_sender = _email(normalized_request.selected_verified_sender)
        domain = _as_text(identity.get("domain")).lower()
        selected_domain = selected_sender.split("@", 1)[1] if "@" in selected_sender else ""
        if domain and selected_domain != domain:
            raise ValueError("live aws profile selected_verified_sender must stay within the profile domain")

        identity["send_as_email"] = selected_sender
        identity["mailbox_local_part"] = _local_part(selected_sender) or _as_text(identity.get("mailbox_local_part"))
        payload["identity"] = identity

        smtp = _as_dict(payload.get("smtp"))
        smtp["send_as_email"] = selected_sender
        smtp["local_part"] = _local_part(selected_sender) or _as_text(smtp.get("local_part"))
        payload["smtp"] = smtp

        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._storage_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        confirmed = self._read_profile()
        return AwsNarrowWriteResult(
            source=AwsNarrowWriteSource(
                payload=self._to_visibility_payload(
                    confirmed,
                    tenant_scope_id=normalized_request.tenant_scope_id,
                )
            )
        )

    def _read_profile_or_none(self) -> dict[str, Any] | None:
        if not self._storage_file.exists() or not self._storage_file.is_file():
            return None
        payload = json.loads(self._storage_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("live aws profile payload must be a dict")
        if _as_text(payload.get("schema")) != LIVE_AWS_PROFILE_SCHEMA:
            return None
        return payload

    def _read_profile(self) -> dict[str, Any]:
        payload = self._read_profile_or_none()
        if payload is None:
            raise ValueError("live aws profile adapter requires an existing live profile file")
        return payload

    def _matches_request(self, payload: dict[str, Any], tenant_scope_id: str) -> bool:
        identity = _as_dict(payload.get("identity"))
        requested = _as_text(tenant_scope_id).lower()
        allowed = {
            _as_text(identity.get("tenant_id")).lower(),
            _as_text(identity.get("domain")).lower(),
            _as_text(identity.get("profile_id")).lower(),
        }
        return bool(requested and requested in allowed)

    def _to_visibility_payload(self, payload: dict[str, Any], *, tenant_scope_id: str) -> dict[str, Any]:
        identity = _as_dict(payload.get("identity"))
        smtp = _as_dict(payload.get("smtp"))
        verification = _as_dict(payload.get("verification"))
        provider = _as_dict(payload.get("provider"))
        workflow = _as_dict(payload.get("workflow"))
        inbound = _as_dict(payload.get("inbound"))

        domain = _as_text(identity.get("domain")).lower()
        selected_sender = _email(identity.get("send_as_email") or smtp.get("send_as_email"))
        if not selected_sender and domain:
            selected_sender = f"{_as_text(identity.get('mailbox_local_part'))}@{domain}".lower()

        profile = {
            "profile_id": _as_text(identity.get("profile_id")),
            "domain": domain,
            "list_address": selected_sender,
            "selected_verified_sender": selected_sender,
            "delivery_mode": "inbound-mail-only",
        }

        mailbox_readiness = "not_ready"
        if _as_bool(workflow.get("is_mailbox_operational")):
            mailbox_readiness = "ready"
        elif _as_bool(workflow.get("is_ready_for_user_handoff")):
            mailbox_readiness = "ready_for_gmail_handoff"

        smtp_ready = _as_bool(smtp.get("handoff_ready")) or _as_text(smtp.get("credentials_secret_state")).lower() == "configured"
        gmail_verified = (
            _as_text(provider.get("gmail_send_as_status")).lower() == "verified"
            or _as_text(verification.get("status")).lower() == "verified"
            or _as_text(verification.get("portal_state")).lower() == "verified"
        )
        initiated = _as_bool(workflow.get("initiated"))
        inbound_ready = _as_bool(inbound.get("receive_verified")) or _as_bool(inbound.get("portal_native_display_ready"))
        latest_message_id = _as_text(inbound.get("latest_message_id"))

        return {
            "tenant_scope_id": _as_text(tenant_scope_id),
            "mailbox_readiness": mailbox_readiness,
            "smtp_state": "smtp_ready" if smtp_ready else "not_configured",
            "gmail_state": "gmail_verified" if gmail_verified else ("gmail_pending" if initiated else "not_started"),
            "verified_evidence_state": "verified_evidence_present"
            if gmail_verified
            else ("sender_selected" if selected_sender else "not_verified"),
            "selected_verified_sender": selected_sender,
            "canonical_newsletter_profile": profile,
            "compatibility": {"canonical_profile_matches_compatibility_inputs": True},
            "inbound_capture": {
                "status": "ready" if inbound_ready else ("warning" if latest_message_id else "not_ready"),
                "last_capture_state": "captured" if latest_message_id else _as_text(inbound.get("receive_state")) or "none",
            },
            "dispatch_health": {
                "status": "healthy" if _as_bool(workflow.get("is_mailbox_operational")) else "unknown",
                "last_delivery_outcome": _as_text(workflow.get("lifecycle_state")) or "unknown",
                "pending_message_count": 0,
            },
        }
