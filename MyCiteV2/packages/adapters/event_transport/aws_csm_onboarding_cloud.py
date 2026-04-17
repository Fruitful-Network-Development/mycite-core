from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Iterator

from MyCiteV2.packages.adapters.event_transport.aws_csm_newsletter_cloud import (
    AwsEc2RoleNewsletterCloudAdapter,
)
from MyCiteV2.packages.adapters.filesystem.aws_csm_newsletter_state import (
    FilesystemAwsCsmNewsletterStateAdapter,
)
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingCloudPort

_AWS_SMTP_IAM_USER = str(os.getenv("AWS_CMS_SMTP_IAM_USER", "aws-cms-smtp")).strip() or "aws-cms-smtp"
_AWS_SMTP_MESSAGE = "SendRawEmail"
_AWS_SMTP_TERMINAL = "aws4_request"
_AWS_SMTP_VERSION = b"\x04"
_AWS_SMTP_DATE_SEED = "11111111"
_DEFAULT_REGION = "us-east-1"
_DEFAULT_INBOUND_LAMBDA = "newsletter-inbound-capture"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() == "true"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _normalized_email(value: object) -> str:
    token = _as_text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _local_part(email: object) -> str:
    token = _normalized_email(email)
    return token.split("@", 1)[0] if token else ""


def _status_is_ready(value: object) -> bool:
    return _as_text(value).lower() in {"ok", "active", "ready", "successful"}


def _smtp_secret_description(secret_name: str) -> str:
    token = _as_text(secret_name)
    if not token:
        return "SES SMTP credentials for AWS-CSM send-as onboarding"
    prefix = "aws-cms/smtp/"
    profile_suffix = token[len(prefix) :] if token.startswith(prefix) else token
    profile_suffix = profile_suffix.strip().strip("/")
    profile_id = f"aws-csm.{profile_suffix}" if profile_suffix else "aws-csm"
    return f"SES SMTP credentials for {profile_id} send-as onboarding"


def _aws_smtp_password(secret_access_key: str, *, region: str) -> str:
    secret = _as_text(secret_access_key)
    region_token = _as_text(region) or _DEFAULT_REGION
    if not secret:
        raise ValueError("Missing secret access key for SES SMTP password derivation.")

    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    signature = _sign(("AWS4" + secret).encode("utf-8"), _AWS_SMTP_DATE_SEED)
    signature = _sign(signature, region_token)
    signature = _sign(signature, "ses")
    signature = _sign(signature, _AWS_SMTP_TERMINAL)
    signature = _sign(signature, _AWS_SMTP_MESSAGE)
    return base64.b64encode(_AWS_SMTP_VERSION + signature).decode("utf-8")


class AwsEc2RoleOnboardingCloudAdapter(AwsEc2RoleNewsletterCloudAdapter, AwsCsmOnboardingCloudPort):
    def __init__(self, *, private_dir: str | Path | None = None, tenant_id: str = "") -> None:
        self._private_dir = None if private_dir is None else Path(private_dir)
        self._tenant_id = _as_text(tenant_id)
        self._newsletter_state = (
            None
            if self._private_dir is None
            else FilesystemAwsCsmNewsletterStateAdapter(self._private_dir)
        )

    def supplemental_profile_patch(self, action: str, profile: dict[str, Any]) -> dict[str, Any]:
        token = _as_text(action)
        if token in {"prepare_send_as", "stage_smtp_credentials"}:
            return self._stage_smtp_patch(profile)
        if token == "refresh_provider_status":
            return self._provider_status_patch(profile)
        if token in {"enable_inbound_capture", "refresh_inbound_status"}:
            readiness = self.describe_profile_readiness(profile)
            return self._inbound_status_patch(profile, readiness=readiness)
        if token == "capture_verification":
            readiness = self.describe_profile_readiness(profile)
            patch = self._inbound_status_patch(profile, readiness=readiness)
            capture = _as_dict(_as_dict(readiness.get("inbound")).get("latest_capture"))
            verification_patch = self._verification_capture_patch(profile, capture=capture)
            if verification_patch:
                patch["verification"] = verification_patch
            return patch
        return {}

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        readiness = self.describe_profile_readiness(profile)
        confirmation = _as_dict(readiness.get("confirmation"))
        return bool(confirmation.get("already_verified")) or bool(confirmation.get("can_confirm_verified"))

    def describe_profile_readiness(self, profile: dict[str, Any]) -> dict[str, Any]:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        provider = _as_dict(profile.get("provider"))
        verification = _as_dict(profile.get("verification"))
        inbound = _as_dict(profile.get("inbound"))

        checked_at = _utc_now_iso()
        region = self._region_for_profile(profile)
        domain = _normalized_domain(identity.get("domain"))
        send_as_email = self._send_as_email(profile)
        secret_name = self._smtp_secret_name(profile)
        smtp_material = (
            self._smtp_secret_material(secret_name=secret_name, region=region)
            if secret_name
            else {"state": "missing", "secret_name": "", "username": "", "password": "", "message": "No SMTP secret is configured."}
        )
        smtp_state = _as_text(smtp_material.get("state")).lower()
        smtp_status = "ready" if smtp_state == "configured" else ("blocked" if smtp_state in {"error", "quota_blocked"} else "action_required")
        provider_summary = self._ses_identity_summary(
            region=region,
            email_identity=domain or send_as_email,
        )
        provider_state = _as_text(provider_summary.get("aws_ses_identity_status") or provider.get("aws_ses_identity_status")).lower()
        provider_status = "ready" if provider_state == "verified" else ("blocked" if provider_state in {"error", "access_denied"} else "action_required")
        expected_lambda_name = self._inbound_lambda_name(profile)
        receipt_rule = self.receipt_rule_summary(
            domain=domain,
            expected_recipient=send_as_email or (f"news@{domain}" if domain else ""),
            expected_lambda_name=expected_lambda_name,
            region=region,
        ) if (domain and expected_lambda_name) else {"status": "not_configured", "message": "Inbound receipt rule target is not configured."}
        inbound_lambda = (
            self.lambda_health_summary(function_name=expected_lambda_name, region=region)
            if expected_lambda_name
            else {"status": "not_configured", "message": "Inbound capture Lambda is not configured."}
        )
        capture = self._capture_summary(profile, region=region)
        capture_evidence = bool(capture.get("portal_native_evidence_present"))
        already_verified = (
            _as_text(verification.get("status")).lower() == "verified"
            or _as_text(verification.get("portal_state")).lower() == "verified"
            or _as_text(provider.get("gmail_send_as_status")).lower() == "verified"
        )
        inbound_ready = bool(inbound.get("receive_verified")) or _as_bool(inbound.get("portal_native_display_ready"))
        if inbound_ready:
            inbound_status = "ready"
        elif _status_is_ready(receipt_rule.get("status")) and _status_is_ready(inbound_lambda.get("status")) and capture_evidence:
            inbound_status = "captured"
        elif _status_is_ready(receipt_rule.get("status")) and _status_is_ready(inbound_lambda.get("status")):
            inbound_status = "listening"
        elif _as_text(receipt_rule.get("status")).lower() == "error" or _as_text(inbound_lambda.get("status")).lower() == "error":
            inbound_status = "blocked"
        else:
            inbound_status = "action_required"
        if already_verified:
            confirmation_status = "ready"
        elif capture_evidence:
            confirmation_status = "action_required"
        elif smtp_status == "ready":
            confirmation_status = "manual"
        else:
            confirmation_status = "blocked"

        return {
            "schema": "mycite.v2.portal.system.tools.aws_csm.cloud_readiness.v1",
            "checked_at": checked_at,
            "profile_id": _as_text(identity.get("profile_id")),
            "domain": domain,
            "smtp": {
                "status": smtp_status,
                "credentials_secret_state": _as_text(smtp_material.get("state")),
                "secret_name": _as_text(smtp_material.get("secret_name") or secret_name),
                "username": _as_text(smtp_material.get("persisted_username") or smtp_material.get("username") or smtp.get("username")),
                "smtp_host": _as_text(smtp_material.get("smtp_host") or smtp.get("host") or f"email-smtp.{region}.amazonaws.com"),
                "smtp_port": _as_text(smtp_material.get("smtp_port") or smtp.get("port") or "587"),
                "handoff_ready": smtp_status == "ready",
                "message": _as_text(smtp_material.get("message"))
                or ("SMTP secret material is ready for Gmail handoff." if smtp_status == "ready" else "SMTP credentials still need operator attention."),
            },
            "provider": {
                "status": provider_status,
                "aws_ses_identity_status": provider_state or _as_text(provider.get("aws_ses_identity_status")),
                "last_checked_at": checked_at,
                "message": _as_text(provider_summary.get("message"))
                or ("AWS SES identity is verified." if provider_status == "ready" else "AWS SES identity still needs verification or refresh."),
            },
            "inbound": {
                "status": inbound_status,
                "expected_recipient": send_as_email or (f"news@{domain}" if domain else ""),
                "expected_lambda_name": expected_lambda_name,
                "receipt_rule": receipt_rule,
                "inbound_lambda": inbound_lambda,
                "latest_capture": capture,
                "portal_native_evidence_present": capture_evidence,
                "message": (
                    "Portal-native inbound evidence is available."
                    if capture_evidence
                    else "Inbound capture is waiting for an AWS-backed verification message."
                ),
            },
            "confirmation": {
                "status": confirmation_status,
                "already_verified": already_verified,
                "can_confirm_verified": capture_evidence and not already_verified,
                "portal_native_evidence_present": capture_evidence,
                "message": (
                    "Portal-native verification evidence is ready to confirm."
                    if capture_evidence and not already_verified
                    else (
                        "Gmail send-as is already verified."
                        if already_verified
                        else "Confirm Gmail send-as only after portal-native evidence is captured."
                    )
                ),
            },
        }

    def send_handoff_email(self, profile: dict[str, Any]) -> dict[str, Any]:
        send_as_email = self._send_as_email(profile)
        if not send_as_email:
            raise ValueError("AWS-CSM send-as email is not configured for this profile.")
        destination = self._handoff_destination(profile)
        if not destination:
            raise ValueError("AWS-CSM operator inbox target is not configured for this profile.")
        material = self.read_handoff_secret(profile)
        username = _as_text(material.get("username"))
        smtp_host = _as_text(material.get("smtp_host"))
        smtp_port = _as_text(material.get("smtp_port"))
        region = self._region_for_profile(profile)
        response = self._client("sesv2", region=region).send_email(
            FromEmailAddress=send_as_email,
            Destination={"ToAddresses": [destination]},
            Content={
                "Simple": {
                    "Subject": {"Data": f"AWS-CSM Gmail send-as handoff for {send_as_email}"},
                    "Body": {
                        "Text": {
                            "Data": "\n".join(
                                [
                                    f"Set up Gmail Send mail as for {send_as_email}.",
                                    "",
                                    f"SMTP host: {smtp_host}",
                                    f"SMTP port: {smtp_port}",
                                    f"SMTP username: {username}",
                                    "",
                                    "Use the separately revealed SMTP password when Gmail asks for it.",
                                    "After saving the Send mail as entry, wait for the Gmail confirmation email to arrive.",
                                    "Open the confirmation link to finish verification.",
                                ]
                            )
                        }
                    },
                }
            },
        )
        return {
            "message_id": _as_text(response.get("MessageId")),
            "sent_to": destination,
            "send_as_email": send_as_email,
            "username": username,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "state": _as_text(material.get("state")),
        }

    def read_handoff_secret(self, profile: dict[str, Any]) -> dict[str, Any]:
        send_as_email = self._send_as_email(profile)
        secret_name = self._smtp_secret_name(profile)
        if not secret_name:
            raise ValueError("AWS-CSM SMTP secret name is not configured for this profile.")
        region = self._region_for_profile(profile)
        material = self._smtp_secret_material(secret_name=secret_name, region=region)
        state = _as_text(material.get("state")).lower()
        username = _as_text(material.get("persisted_username") or material.get("username"))
        secret_value = _as_text(material.get("password"))
        if state != "configured" or not username or not secret_value:
            raise ValueError("SMTP credentials must be staged before the password can be revealed.")
        return {
            "send_as_email": send_as_email,
            "secret_name": _as_text(material.get("secret_name") or secret_name),
            "state": state,
            "username": username,
            "password": secret_value,
            "smtp_host": _as_text(material.get("smtp_host")) or f"email-smtp.{region}.amazonaws.com",
            "smtp_port": _as_text(material.get("smtp_port")) or "587",
        }

    def _stage_smtp_patch(self, profile: dict[str, Any]) -> dict[str, Any]:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        workflow = _as_dict(profile.get("workflow"))
        checked_at = _utc_now_iso()
        region = self._region_for_profile(profile)
        secret_name = self._smtp_secret_name(profile)
        material = (
            self._ensure_smtp_secret_material(secret_name=secret_name, region=region)
            if secret_name
            else {"state": "missing", "secret_name": "", "username": "", "password": "", "message": "No SMTP secret name is configured."}
        )
        provider = self._ses_identity_summary(
            region=region,
            email_identity=_normalized_domain(identity.get("domain")) or self._send_as_email(profile),
        )
        handoff_ready = _as_text(material.get("state")).lower() == "configured"
        send_as_email = self._send_as_email(profile)
        local_part = _local_part(send_as_email) or _as_text(identity.get("mailbox_local_part")) or _as_text(smtp.get("local_part"))
        return {
            "smtp": {
                "host": _as_text(material.get("smtp_host") or smtp.get("host") or f"email-smtp.{region}.amazonaws.com"),
                "port": _as_text(material.get("smtp_port") or smtp.get("port") or "587"),
                "username": _as_text(material.get("persisted_username") or material.get("username") or smtp.get("username")),
                "credentials_source": _as_text(smtp.get("credentials_source")) or "operator_managed",
                "handoff_ready": handoff_ready,
                "credentials_secret_name": _as_text(material.get("secret_name") or secret_name),
                "credentials_secret_state": "configured" if handoff_ready else (_as_text(smtp.get("credentials_secret_state")) or "missing"),
                "send_as_email": send_as_email,
                "local_part": local_part,
                "staging_state": "material_ready" if handoff_ready else "operator_attention_required",
            },
            "provider": {
                "aws_ses_identity_status": _as_text(provider.get("aws_ses_identity_status")),
                "last_checked_at": checked_at,
            },
            "workflow": {
                "is_ready_for_user_handoff": handoff_ready,
                "handoff_status": "ready_for_gmail_handoff"
                if handoff_ready
                else (_as_text(workflow.get("handoff_status")) or "smtp_pending"),
            },
        }

    def _provider_status_patch(self, profile: dict[str, Any]) -> dict[str, Any]:
        identity = _as_dict(profile.get("identity"))
        checked_at = _utc_now_iso()
        summary = self._ses_identity_summary(
            region=self._region_for_profile(profile),
            email_identity=_normalized_domain(identity.get("domain")) or self._send_as_email(profile),
        )
        return {
            "provider": {
                "aws_ses_identity_status": _as_text(summary.get("aws_ses_identity_status")),
                "last_checked_at": checked_at,
            }
        }

    def _inbound_status_patch(self, profile: dict[str, Any], *, readiness: dict[str, Any]) -> dict[str, Any]:
        inbound = _as_dict(profile.get("inbound"))
        workflow = _as_dict(profile.get("workflow"))
        inbound_summary = _as_dict(readiness.get("inbound"))
        capture = _as_dict(inbound_summary.get("latest_capture"))
        receipt_rule = _as_dict(inbound_summary.get("receipt_rule"))
        inbound_lambda = _as_dict(inbound_summary.get("inbound_lambda"))
        capture_evidence = bool(inbound_summary.get("portal_native_evidence_present"))
        receipt_ready = _status_is_ready(receipt_rule.get("status"))
        lambda_ready = _status_is_ready(inbound_lambda.get("status"))
        existing_receive_verified = _as_bool(inbound.get("receive_verified"))
        existing_portal_ready = _as_bool(inbound.get("portal_native_display_ready"))
        if existing_receive_verified:
            receive_state = "receive_operational"
        elif capture_evidence:
            receive_state = "receive_pending"
        elif receipt_ready and lambda_ready:
            receive_state = "receive_configured"
        else:
            receive_state = _as_text(inbound.get("receive_state")) or "receive_unconfigured"
        patch = {
            "inbound": {
                "receive_state": receive_state,
                "receive_last_checked_at": _as_text(readiness.get("checked_at")),
                "portal_native_display_ready": capture_evidence or existing_portal_ready,
                "capture_source_kind": "s3_object" if _as_text(capture.get("s3_uri")) else _as_text(inbound.get("capture_source_kind")),
                "capture_source_reference": _as_text(capture.get("s3_uri") or inbound.get("capture_source_reference")),
                "latest_message_s3_uri": _as_text(capture.get("s3_uri") or inbound.get("latest_message_s3_uri")),
                "latest_message_id": _as_text(capture.get("message_id") or inbound.get("latest_message_id")),
                "latest_message_subject": _as_text(capture.get("subject") or inbound.get("latest_message_subject")),
                "latest_message_captured_at": _as_text(capture.get("captured_at") or inbound.get("latest_message_captured_at")),
                "latest_message_has_verification_link": bool(
                    capture.get("has_verification_link") or inbound.get("latest_message_has_verification_link")
                ),
            },
            "workflow": {
                "is_receive_path_modeled": receipt_ready and lambda_ready,
                "is_portal_native_inbound_ready": capture_evidence or _as_bool(workflow.get("is_portal_native_inbound_ready")),
            },
        }
        if existing_receive_verified:
            patch["inbound"]["receive_verified"] = True
        return patch

    def _verification_capture_patch(self, profile: dict[str, Any], *, capture: dict[str, Any]) -> dict[str, Any]:
        verification = _as_dict(profile.get("verification"))
        s3_uri = _as_text(capture.get("s3_uri"))
        if not s3_uri:
            return {}
        return {
            "portal_state": "capture_received",
            "latest_message_reference": s3_uri,
            "email_received_at": _as_text(capture.get("captured_at") or verification.get("email_received_at")),
            "link": _as_text(verification.get("link")),
        }

    def _capture_summary(self, profile: dict[str, Any], *, region: str) -> dict[str, Any]:
        inbound = _as_dict(profile.get("inbound"))
        verification = _as_dict(profile.get("verification"))
        s3_uri = _as_text(
            inbound.get("latest_message_s3_uri")
            or inbound.get("capture_source_reference")
            or verification.get("latest_message_reference")
        )
        accessible = False
        access_error = ""
        if s3_uri:
            try:
                accessible = bool(self.read_s3_bytes(s3_uri=s3_uri, region=region))
            except Exception as exc:  # noqa: BLE001
                access_error = _as_text(exc)
        subject = _as_text(inbound.get("latest_message_subject"))
        has_verification_link = bool(inbound.get("latest_message_has_verification_link")) or bool(_as_text(verification.get("link")))
        portal_native_evidence_present = accessible and (
            has_verification_link
            or bool(_as_text(verification.get("latest_message_reference")))
            or "confirmation" in subject.lower()
        )
        return {
            "s3_uri": s3_uri,
            "message_id": _as_text(inbound.get("latest_message_id")),
            "subject": subject,
            "captured_at": _as_text(inbound.get("latest_message_captured_at")),
            "has_verification_link": has_verification_link,
            "accessible": accessible,
            "access_error": access_error,
            "portal_native_evidence_present": portal_native_evidence_present,
        }

    def _region_for_profile(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        token = (
            _as_text(identity.get("region"))
            or _as_text(smtp.get("smtp_region"))
            or _as_text(self._newsletter_profile(_normalized_domain(identity.get("domain"))).get("aws_region"))
            or _DEFAULT_REGION
        )
        return token

    def _send_as_email(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        return _normalized_email(identity.get("send_as_email") or smtp.get("send_as_email"))

    def _handoff_destination(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        return _normalized_email(smtp.get("forward_to_email") or identity.get("operator_inbox_target"))

    def _smtp_secret_name(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        configured = _as_text(smtp.get("credentials_secret_name"))
        if configured:
            return configured
        tenant_id = _as_text(identity.get("tenant_id"))
        mailbox_local_part = _as_text(identity.get("mailbox_local_part")) or _local_part(self._send_as_email(profile))
        if not tenant_id or not mailbox_local_part:
            return ""
        return f"aws-cms/smtp/{tenant_id}.{mailbox_local_part}"

    def _newsletter_profile(self, domain: str) -> dict[str, Any]:
        if self._newsletter_state is None or not domain:
            return {}
        try:
            payload = self._newsletter_state.load_profile(domain=domain)
        except Exception:  # noqa: BLE001
            return {}
        return payload if isinstance(payload, dict) else {}

    def _inbound_lambda_name(self, profile: dict[str, Any]) -> str:
        inbound = _as_dict(profile.get("inbound"))
        identity = _as_dict(profile.get("identity"))
        configured = _as_text(inbound.get("inbound_processor_lambda_name"))
        if configured:
            return configured
        newsletter_profile = self._newsletter_profile(_normalized_domain(identity.get("domain")))
        return _as_text(newsletter_profile.get("inbound_processor_lambda_name")) or _DEFAULT_INBOUND_LAMBDA

    def _smtp_secret_material(self, *, secret_name: str, region: str) -> dict[str, Any]:
        client = self._client("secretsmanager", region=_DEFAULT_REGION)
        try:
            response = client.get_secret_value(SecretId=secret_name)
            secret_string = _as_text(response.get("SecretString"))
        except client.exceptions.ResourceNotFoundException:
            return {
                "secret_name": secret_name,
                "username": "",
                "persisted_username": "",
                "password": "",
                "smtp_host": f"email-smtp.{region}.amazonaws.com",
                "smtp_port": "587",
                "state": "missing",
                "message": "No SMTP secret exists yet.",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "secret_name": secret_name,
                "username": "",
                "persisted_username": "",
                "password": "",
                "smtp_host": f"email-smtp.{region}.amazonaws.com",
                "smtp_port": "587",
                "state": "error",
                "message": _as_text(exc) or "Unable to read SMTP secret material.",
            }
        payload: dict[str, Any] = {}
        if secret_string:
            try:
                parsed = json.loads(secret_string)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                payload = parsed
        username = _as_text(payload.get("username"))
        password = _as_text(payload.get("password"))
        is_placeholder = any(token.startswith("REPLACE_") for token in (username, password) if token)
        state = "configured" if username and password and not is_placeholder else ("placeholder" if (username or password) else "missing")
        return {
            "secret_name": secret_name,
            "username": username,
            "persisted_username": "" if is_placeholder else username,
            "password": password,
            "smtp_host": _as_text(payload.get("smtp_host")) or f"email-smtp.{region}.amazonaws.com",
            "smtp_port": _as_text(payload.get("smtp_port")) or "587",
            "state": state,
            "message": "",
        }

    def _ensure_smtp_secret_material(self, *, secret_name: str, region: str) -> dict[str, Any]:
        with self._smtp_provision_lock():
            current = self._smtp_secret_material(secret_name=secret_name, region=region)
            if _as_text(current.get("state")).lower() == "configured":
                return current
            active_keys = [
                row
                for row in self._list_smtp_access_keys()
                if _as_text(row.get("status")).lower() == "active"
            ]
            if len(active_keys) >= 2:
                current["state"] = "quota_blocked"
                current["message"] = (
                    f"{_AWS_SMTP_IAM_USER} already has two active access keys; rotate or reuse existing SMTP material first."
                )
                return current
            try:
                created = self._create_smtp_secret_material(secret_name=secret_name, region=region)
            except Exception as exc:  # noqa: BLE001
                current["state"] = "error"
                current["message"] = _as_text(exc) or "Unable to materialize SMTP secret material."
                return current
            return created

    def _list_smtp_access_keys(self) -> list[dict[str, Any]]:
        try:
            payload = self._client("iam").list_access_keys(UserName=_AWS_SMTP_IAM_USER)
        except Exception:  # noqa: BLE001
            return []
        rows = payload.get("AccessKeyMetadata") if isinstance(payload, dict) else []
        out: list[dict[str, Any]] = []
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "access_key_id": _as_text(row.get("AccessKeyId")),
                    "status": _as_text(row.get("Status")),
                    "created_at": _as_text(row.get("CreateDate")),
                }
            )
        out.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return out

    def _create_smtp_secret_material(self, *, secret_name: str, region: str) -> dict[str, Any]:
        payload = self._client("iam").create_access_key(UserName=_AWS_SMTP_IAM_USER)
        access_key = _as_dict(payload.get("AccessKey"))
        access_key_id = _as_text(access_key.get("AccessKeyId"))
        secret_access_key = _as_text(access_key.get("SecretAccessKey"))
        if not access_key_id or not secret_access_key:
            raise ValueError("AWS IAM create_access_key did not return usable key material.")
        password = _aws_smtp_password(secret_access_key, region=region)
        secret_payload = {
            "username": access_key_id,
            "password": password,
            "iam_user": _AWS_SMTP_IAM_USER,
            "access_key_id": access_key_id,
            "smtp_region": region,
            "smtp_host": f"email-smtp.{region}.amazonaws.com",
            "smtp_port": "587",
            "tls_mode": "TLS",
            "provisioned_at": _utc_now_iso(),
        }
        self._upsert_secret_payload(
            secret_name=secret_name,
            payload=secret_payload,
            description=_smtp_secret_description(secret_name),
        )
        return {
            "secret_name": secret_name,
            "username": access_key_id,
            "persisted_username": access_key_id,
            "password": password,
            "smtp_host": secret_payload["smtp_host"],
            "smtp_port": secret_payload["smtp_port"],
            "state": "configured",
            "message": "SMTP secret material was created from the shared IAM sender user.",
        }

    def _upsert_secret_payload(self, *, secret_name: str, payload: dict[str, Any], description: str) -> None:
        client = self._client("secretsmanager", region=_DEFAULT_REGION)
        secret_string = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        try:
            client.update_secret(
                SecretId=secret_name,
                SecretString=secret_string,
                Description=description,
            )
        except client.exceptions.ResourceNotFoundException:
            client.create_secret(
                Name=secret_name,
                SecretString=secret_string,
                Description=description,
            )

    def _ses_identity_summary(self, *, region: str, email_identity: str) -> dict[str, Any]:
        identity = _as_text(email_identity)
        if not identity:
            return {
                "aws_ses_identity_status": "not_started",
                "message": "No SES identity target is configured.",
            }
        client = self._client("sesv2", region=region)
        try:
            response = client.get_email_identity(EmailIdentity=identity)
        except Exception as exc:  # noqa: BLE001
            message = _as_text(exc)
            lowered = message.lower()
            if "notfound" in lowered or "not found" in lowered:
                return {
                    "aws_ses_identity_status": "not_started",
                    "message": "SES identity has not been created for this domain yet.",
                }
            return {
                "aws_ses_identity_status": "error",
                "message": message or "Unable to query SES identity status.",
            }
        verification_status = _as_text(response.get("VerificationStatus")).upper()
        verified_for_sending = bool(response.get("VerifiedForSendingStatus"))
        aws_status = "not_started"
        if verification_status == "SUCCESS" and verified_for_sending:
            aws_status = "verified"
        elif verification_status:
            aws_status = verification_status.lower()
        return {
            "aws_ses_identity_status": aws_status,
            "message": "",
        }

    @contextmanager
    def _smtp_provision_lock(self) -> Iterator[None]:
        if self._private_dir is None:
            yield
            return
        lock_path = self._private_dir / "utilities" / "tools" / "aws-csm" / "smtp_provision.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


__all__ = ["AwsEc2RoleOnboardingCloudAdapter"]
