from __future__ import annotations

from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
import hmac
import hashlib
import json
import secrets
from typing import Any

from MyCiteV2.packages.ports.aws_csm_newsletter import (
    AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
    AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
    AwsCsmNewsletterCloudPort,
    AwsCsmNewsletterStatePort,
)

_MAX_DISPATCH_HISTORY = 20
_MAX_DISPATCH_RESULT_HISTORY = 100
_MAX_CONTACT_PREVIEW = 50
_DELIVERY_MODE = "inbound-mail-workflow"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_email(value: object, *, field_name: str) -> str:
    token = _as_text(value).lower()
    if not token or token.count("@") != 1 or any(ch.isspace() for ch in token):
        raise ValueError(f"{field_name} must be an email-like value")
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        raise ValueError(f"{field_name} must be an email-like value")
    return token


def _normalized_domain(value: object, *, field_name: str) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    if not token or "." not in token:
        raise ValueError(f"{field_name} must be a domain-like value")
    return token


def _optional_email(value: object) -> str:
    token = _as_text(value).lower()
    if not token:
        return ""
    try:
        return _normalized_email(token, field_name="email")
    except ValueError:
        return ""


def _preserved_email(value: object) -> str:
    raw = _as_text(value)
    for _name, address in getaddresses([raw]):
        candidate = _optional_email(address)
        if candidate:
            return candidate
    return _optional_email(raw)


def _email_addresses(value: object) -> set[str]:
    out: set[str] = set()
    raw = _as_text(value)
    for _name, address in getaddresses([raw]):
        candidate = _optional_email(address)
        if candidate:
            out.add(candidate)
    fallback = _optional_email(raw)
    if fallback:
        out.add(fallback)
    return out


def _render_unsubscribe_token(secret: str, *, domain: str, email: str) -> str:
    payload = f"{_normalized_domain(domain, field_name='domain')}|{_normalized_email(email, field_name='email')}".encode(
        "utf-8"
    )
    return hmac.new(_as_text(secret).encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _render_inbound_capture_signature(
    secret: str,
    *,
    domain: str,
    ses_message_id: str,
    s3_uri: str,
    sender: str,
    recipient: str,
    subject: str,
    captured_at: str,
) -> str:
    payload = "|".join(
        [
            _normalized_domain(domain, field_name="domain"),
            _as_text(ses_message_id),
            _as_text(s3_uri),
            _optional_email(sender),
            _optional_email(recipient),
            _as_text(subject),
            _as_text(captured_at),
        ]
    ).encode("utf-8")
    return hmac.new(_as_text(secret).encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _normalize_contact(contact: Any) -> dict[str, Any] | None:
    if not isinstance(contact, dict):
        return None
    email = _optional_email(contact.get("email"))
    if not email:
        return None
    created_at = _as_text(contact.get("created_at")) or _utc_now_iso()
    subscribed = bool(contact.get("subscribed", True))
    return {
        "email": email,
        "name": _as_text(contact.get("name")),
        "zip": _as_text(contact.get("zip")),
        "source": _as_text(contact.get("source")) or "unknown",
        "subscribed": subscribed,
        "created_at": created_at,
        "subscribed_at": _as_text(contact.get("subscribed_at")) or (created_at if subscribed else ""),
        "unsubscribed_at": _as_text(contact.get("unsubscribed_at")),
        "updated_at": _as_text(contact.get("updated_at")) or created_at,
        "last_newsletter_sent_at": _as_text(contact.get("last_newsletter_sent_at")),
        "send_count": int(contact.get("send_count") or 0),
        "notes": _as_text(contact.get("notes")),
    }


def _normalize_contact_log(payload: dict[str, Any], *, domain: str) -> dict[str, Any]:
    token = _normalized_domain(domain, field_name="domain")
    contacts_by_email: dict[str, dict[str, Any]] = {}
    for raw in list(payload.get("contacts") or []):
        normalized = _normalize_contact(raw)
        if normalized is None:
            continue
        contacts_by_email[normalized["email"]] = normalized
    dispatches: list[dict[str, Any]] = []
    for item in list(payload.get("dispatches") or []):
        if isinstance(item, dict):
            dispatches.append(dict(item))
    return {
        "schema": AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
        "domain": token,
        "contacts": [contacts_by_email[key] for key in sorted(contacts_by_email.keys())],
        "dispatches": dispatches[-_MAX_DISPATCH_HISTORY:],
        "updated_at": _as_text(payload.get("updated_at")) or _utc_now_iso(),
    }


def _contact_summary(contact_log: dict[str, Any]) -> dict[str, int]:
    subscribed = 0
    unsubscribed = 0
    for raw in list(contact_log.get("contacts") or []):
        normalized = _normalize_contact(raw)
        if normalized is None:
            continue
        if normalized["subscribed"]:
            subscribed += 1
        else:
            unsubscribed += 1
    return {
        "contact_count": subscribed + unsubscribed,
        "subscribed_count": subscribed,
        "unsubscribed_count": unsubscribed,
    }


def _message_text_from_email(raw_bytes: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    if hasattr(message, "walk"):
        for part in message.walk():
            if str(part.get_content_type() or "").lower() != "text/plain":
                continue
            if str(part.get_content_disposition() or "").lower() == "attachment":
                continue
            try:
                return str(part.get_content() or "")
            except Exception:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = str(part.get_content_charset() or "utf-8")
                    return payload.decode(charset, errors="replace")
    payload = message.get_payload(decode=True)
    if payload:
        charset = str(message.get_content_charset() or "utf-8")
        return payload.decode(charset, errors="replace")
    try:
        return str(message.get_content() or "")
    except Exception:
        return ""


def _message_subject_from_email(raw_bytes: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    return _as_text(message.get("Subject"))


class AwsCsmNewsletterService:
    def __init__(
        self,
        state_port: AwsCsmNewsletterStatePort,
        cloud_port: AwsCsmNewsletterCloudPort,
        *,
        tenant_id: str,
    ) -> None:
        self._state_port = state_port
        self._cloud_port = cloud_port
        self._tenant_id = _normalized_domain(f"{tenant_id}.internal", field_name="tenant_id").split(".", 1)[0]
        self._unsubscribe_secret_name = f"aws-cms/newsletter/unsubscribe-signing/{self._tenant_id}"
        self._dispatch_callback_secret_name = f"aws-cms/newsletter/dispatch-callback/{self._tenant_id}"
        self._inbound_callback_secret_name = f"aws-cms/newsletter/inbound-capture/{self._tenant_id}"

    def _ensure_secret_value(self, *, secret_name: str, secret_kind: str) -> str:
        seed = self._state_port.legacy_runtime_secret_seed(secret_kind=secret_kind) or secrets.token_urlsafe(32)
        return self._cloud_port.get_or_create_secret_value(secret_name=secret_name, initial_value=seed)

    def _known_domains(self) -> list[str]:
        return sorted({_normalized_domain(domain, field_name="domain") for domain in self._state_port.list_newsletter_domains()})

    def _require_known_domain(self, *, domain: str) -> str:
        token = _normalized_domain(domain, field_name="domain")
        if token not in self._known_domains():
            raise LookupError(f"domain {token} is not configured for AWS-CSM newsletter operations")
        return token

    def _ensure_domain_state(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        token = self._require_known_domain(domain=domain)
        return self._state_port.ensure_domain_bootstrap(
            domain=token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
            unsubscribe_secret_name=self._unsubscribe_secret_name,
            dispatch_callback_secret_name=self._dispatch_callback_secret_name,
            inbound_callback_secret_name=self._inbound_callback_secret_name,
            inbound_processor_lambda_name="newsletter-inbound-capture",
        )

    def list_domains(self) -> list[str]:
        return self._known_domains()

    def resolve_domain_state(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> dict[str, Any]:
        token = self._require_known_domain(domain=domain)
        profile, contact_log = self._ensure_domain_state(
            domain=token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )
        verified = list(self._state_port.list_verified_author_profiles(domain=token))
        selected_author = {}
        selected_author_profile_id = _as_text(profile.get("selected_author_profile_id"))
        for item in verified:
            if _as_text(item.get("profile_id")) == selected_author_profile_id:
                selected_author = dict(item)
                break
        if not selected_author and verified:
            selected_author = dict(verified[0])
            profile["selected_author_profile_id"] = _as_text(selected_author.get("profile_id"))
            profile["selected_author_address"] = _as_text(selected_author.get("send_as_email"))
            self._state_port.save_profile(domain=token, payload=profile)

        normalized_contact_log = _normalize_contact_log(contact_log, domain=token)
        summary = _contact_summary(normalized_contact_log)
        latest_dispatch = dict((normalized_contact_log.get("dispatches") or [{}])[-1]) if normalized_contact_log.get("dispatches") else {}

        warnings: list[str] = []
        if not verified:
            warnings.append(f"No verified AWS-CSM author profiles are available for {token}.")
        if not _as_text(profile.get("dispatch_queue_url")):
            warnings.append(f"Dispatch queue is not configured for {token}.")
        if not _as_text(profile.get("callback_url")):
            warnings.append(f"Dispatch callback URL is not configured for {token}.")

        delivery_mode = _as_text(profile.get("delivery_mode")) or _DELIVERY_MODE
        readiness = {
            "author_selected": bool(selected_author),
            "contact_log_ready": True,
            "dispatch_configured": bool(_as_text(profile.get("dispatch_queue_url")) and _as_text(profile.get("dispatcher_lambda_name"))),
            "delivery_mode": delivery_mode,
            "inbound_capture_status": _as_text(profile.get("last_inbound_status")) or "not_processed",
        }
        return {
            "schema": "mycite.v2.admin.aws_csm.newsletter_domain_state.v1",
            "domain": token,
            "profile": dict(profile),
            "selected_author": dict(selected_author),
            "verified_author_profiles": list(verified),
            "contacts": list(normalized_contact_log.get("contacts") or []),
            "contacts_preview": list(normalized_contact_log.get("contacts") or [])[:_MAX_CONTACT_PREVIEW],
            "dispatches": list(normalized_contact_log.get("dispatches") or []),
            "latest_dispatch": latest_dispatch,
            "warnings": warnings,
            "readiness": readiness,
            **summary,
        }

    def family_health(
        self,
        *,
        domains: list[str],
        dispatcher_callback_builder: Any,
        inbound_callback_builder: Any,
    ) -> dict[str, Any]:
        domain_states = [
            self.resolve_domain_state(
                domain=domain,
                dispatcher_callback_url=str(dispatcher_callback_builder(domain)),
                inbound_callback_url=str(inbound_callback_builder(domain)),
            )
            for domain in domains
        ]
        caller_identity = self._cloud_port.caller_identity_summary()
        queue_summary = {"status": "not_configured"}
        dispatcher_summary = {"status": "not_configured"}
        inbound_summary = {"status": "not_configured"}
        receipt_rules: list[dict[str, Any]] = []
        if domain_states:
            first_profile = domain_states[0]["profile"]
            region = _as_text(first_profile.get("aws_region")) or "us-east-1"
            queue_url = _as_text(first_profile.get("dispatch_queue_url"))
            queue_arn = _as_text(first_profile.get("dispatch_queue_arn"))
            if queue_url and queue_arn:
                queue_summary = self._cloud_port.queue_health_summary(
                    queue_url=queue_url,
                    queue_arn=queue_arn,
                    region=region,
                )
            dispatcher_name = _as_text(first_profile.get("dispatcher_lambda_name"))
            if dispatcher_name:
                dispatcher_summary = self._cloud_port.lambda_health_summary(
                    function_name=dispatcher_name,
                    region=region,
                )
            inbound_name = _as_text(first_profile.get("inbound_processor_lambda_name"))
            if inbound_name:
                inbound_summary = self._cloud_port.lambda_health_summary(
                    function_name=inbound_name,
                    region=region,
                )
            for state in domain_states:
                profile = state["profile"]
                receipt_rules.append(
                    self._cloud_port.receipt_rule_summary(
                        domain=state["domain"],
                        expected_recipient=_as_text(profile.get("list_address")) or f"news@{state['domain']}",
                        expected_lambda_name=_as_text(profile.get("inbound_processor_lambda_name")),
                        region=_as_text(profile.get("aws_region")) or "us-east-1",
                    )
                )
        return {
            "schema": "mycite.v2.admin.aws_csm.family_health.v1",
            "caller_identity": caller_identity,
            "dispatch_queue": queue_summary,
            "dispatcher_lambda": dispatcher_summary,
            "inbound_processor_lambda": inbound_summary,
            "receipt_rules": receipt_rules,
            "domain_count": len(domain_states),
            "ready_domain_count": sum(
                1
                for state in domain_states
                if state["readiness"]["author_selected"]
                and state["readiness"]["dispatch_configured"]
            ),
        }

    def select_author(
        self,
        *,
        domain: str,
        selected_author_profile_id: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> dict[str, Any]:
        token = self._require_known_domain(domain=domain)
        self._ensure_domain_state(
            domain=token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )
        verified = list(self._state_port.list_verified_author_profiles(domain=token))
        matched = next(
            (item for item in verified if _as_text(item.get("profile_id")) == _as_text(selected_author_profile_id)),
            None,
        )
        if matched is None:
            raise ValueError("selected author is not currently verified for this domain")
        profile = self._state_port.load_profile(domain=token)
        profile["selected_author_profile_id"] = _as_text(matched.get("profile_id"))
        profile["selected_author_address"] = _as_text(matched.get("send_as_email"))
        self._state_port.save_profile(domain=token, payload=profile)
        return self.resolve_domain_state(
            domain=token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )

    def subscribe(
        self,
        *,
        domain: str,
        email: str,
        name: str = "",
        zip_code: str = "",
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> dict[str, Any]:
        token = self._require_known_domain(domain=domain)
        normalized_email = _normalized_email(email, field_name="email")
        self._ensure_domain_state(
            domain=token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )
        contact_log = self._state_port.load_contact_log(domain=token)
        normalized = _normalize_contact_log(contact_log, domain=token)
        contacts = list(normalized.get("contacts") or [])
        now_iso = _utc_now_iso()
        by_email: dict[str, dict[str, Any]] = {row["email"]: dict(row) for row in contacts if isinstance(row, dict)}
        current = by_email.get(normalized_email)
        if current is None:
            current = {
                "email": normalized_email,
                "name": _as_text(name),
                "zip": _as_text(zip_code),
                "source": "website_signup",
                "subscribed": True,
                "created_at": now_iso,
                "subscribed_at": now_iso,
                "unsubscribed_at": "",
                "updated_at": now_iso,
                "last_newsletter_sent_at": "",
                "send_count": 0,
                "notes": "",
            }
        else:
            if _as_text(name):
                current["name"] = _as_text(name)
            if _as_text(zip_code):
                current["zip"] = _as_text(zip_code)
            current["source"] = "website_signup"
            current["subscribed"] = True
            current["updated_at"] = now_iso
            current["subscribed_at"] = _as_text(current.get("subscribed_at")) or now_iso
            current["unsubscribed_at"] = ""
        by_email[normalized_email] = current
        normalized["contacts"] = [by_email[key] for key in sorted(by_email.keys())]
        self._state_port.save_contact_log(domain=token, payload=normalized)
        return current

    def unsubscribe(
        self,
        *,
        domain: str,
        email: str,
        token: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> dict[str, Any] | None:
        domain_token = self._require_known_domain(domain=domain)
        normalized_email = _normalized_email(email, field_name="email")
        signing_secret = self._ensure_secret_value(
            secret_name=self._unsubscribe_secret_name,
            secret_kind="signing_secret",
        )
        expected = _render_unsubscribe_token(signing_secret, domain=domain_token, email=normalized_email)
        if token != expected:
            raise PermissionError("unsubscribe token is invalid")
        self._ensure_domain_state(
            domain=domain_token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )
        contact_log = _normalize_contact_log(self._state_port.load_contact_log(domain=domain_token), domain=domain_token)
        now_iso = _utc_now_iso()
        updated: dict[str, Any] | None = None
        contacts: list[dict[str, Any]] = []
        for row in list(contact_log.get("contacts") or []):
            current = dict(row)
            if _as_text(current.get("email")).lower() == normalized_email:
                current["subscribed"] = False
                current["source"] = "unsubscribe_link"
                current["unsubscribed_at"] = now_iso
                current["updated_at"] = now_iso
                updated = current
            contacts.append(current)
        contact_log["contacts"] = contacts
        self._state_port.save_contact_log(domain=domain_token, payload=contact_log)
        return updated

    def render_unsubscribe_token(self, *, domain: str, email: str) -> str:
        self._require_known_domain(domain=domain)
        signing_secret = self._ensure_secret_value(
            secret_name=self._unsubscribe_secret_name,
            secret_kind="signing_secret",
        )
        return _render_unsubscribe_token(signing_secret, domain=domain, email=email)

    def render_inbound_capture_signature(
        self,
        *,
        domain: str,
        ses_message_id: str,
        s3_uri: str,
        sender: str,
        recipient: str,
        subject: str,
        captured_at: str,
    ) -> str:
        domain_token = self._require_known_domain(domain=domain)
        inbound_secret = self._ensure_secret_value(
            secret_name=self._inbound_callback_secret_name,
            secret_kind="inbound_secret",
        )
        return _render_inbound_capture_signature(
            inbound_secret,
            domain=domain_token,
            ses_message_id=ses_message_id,
            s3_uri=s3_uri,
            sender=sender,
            recipient=recipient,
            subject=subject,
            captured_at=captured_at,
        )

    def apply_dispatch_result(
        self,
        *,
        domain: str,
        callback_token: str,
        dispatch_id: str,
        email: str,
        status: str,
        message_id: str = "",
        queue_message_id: str = "",
        error_message: str = "",
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> dict[str, Any]:
        domain_token = self._require_known_domain(domain=domain)
        normalized_email = _normalized_email(email, field_name="email")
        expected = self._ensure_secret_value(
            secret_name=self._dispatch_callback_secret_name,
            secret_kind="dispatch_secret",
        )
        if callback_token != expected:
            raise PermissionError("dispatch callback token is invalid")
        self._ensure_domain_state(
            domain=domain_token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )
        if _as_text(status).lower() not in {"sent", "failed"}:
            raise ValueError("dispatch result status must be sent or failed")
        contact_log = _normalize_contact_log(self._state_port.load_contact_log(domain=domain_token), domain=domain_token)
        contacts = {
            _as_text(item.get("email")).lower(): dict(item)
            for item in list(contact_log.get("contacts") or [])
            if isinstance(item, dict) and _as_text(item.get("email"))
        }
        now_iso = _utc_now_iso()
        updated = False
        for dispatch in list(contact_log.get("dispatches") or []):
            if _as_text(dispatch.get("dispatch_id")) != _as_text(dispatch_id):
                continue
            results = list(dispatch.get("results") or [])
            for row in results:
                if not isinstance(row, dict) or _as_text(row.get("email")).lower() != normalized_email:
                    continue
                prior_status = _as_text(row.get("status")).lower()
                row["status"] = _as_text(status).lower()
                if _as_text(message_id):
                    row["message_id"] = _as_text(message_id)
                if _as_text(queue_message_id):
                    row["queue_message_id"] = _as_text(queue_message_id)
                if _as_text(error_message):
                    row["error"] = _as_text(error_message)
                row["updated_at"] = now_iso
                if row["status"] == "sent" and prior_status != "sent":
                    current = contacts.get(normalized_email)
                    if current is not None:
                        current["last_newsletter_sent_at"] = now_iso
                        current["send_count"] = int(current.get("send_count") or 0) + 1
                        current["updated_at"] = now_iso
                        contacts[normalized_email] = current
                updated = True
                break
            dispatch["results"] = results[-_MAX_DISPATCH_RESULT_HISTORY:]
            dispatch["queued_count"] = sum(
                1 for row in results if _as_text((row or {}).get("status")).lower() == "queued"
            )
            dispatch["sent_count"] = sum(
                1 for row in results if _as_text((row or {}).get("status")).lower() == "sent"
            )
            dispatch["failed_count"] = sum(
                1 for row in results if _as_text((row or {}).get("status")).lower() == "failed"
            )
            if int(dispatch.get("queued_count") or 0) == 0:
                dispatch["completed_at"] = now_iso
                dispatch["status"] = "completed" if int(dispatch.get("failed_count") or 0) == 0 else "completed_with_errors"
            break
        if not updated:
            raise LookupError("dispatch result target was not found")
        contact_log["contacts"] = [contacts[key] for key in sorted(contacts.keys())]
        self._state_port.save_contact_log(domain=domain_token, payload=contact_log)
        return {
            "domain": domain_token,
            "dispatch_id": _as_text(dispatch_id),
            "email": normalized_email,
            "status": _as_text(status).lower(),
        }

    def _profile_from_dispatcher_urls(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return self._ensure_domain_state(
            domain=domain,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )

    def _selected_author_for_domain(self, *, domain: str, profile: dict[str, Any]) -> dict[str, Any]:
        verified = list(self._state_port.list_verified_author_profiles(domain=domain))
        selected_profile_id = _as_text(profile.get("selected_author_profile_id"))
        for item in verified:
            if _as_text(item.get("profile_id")) == selected_profile_id:
                return dict(item)
        return dict(verified[0]) if verified else {}

    def process_inbound_capture(
        self,
        *,
        signature: str,
        domain: str,
        ses_message_id: str,
        s3_uri: str,
        sender: str,
        recipient: str,
        subject: str,
        captured_at: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
        force_reprocess: bool = False,
    ) -> dict[str, Any]:
        domain_token = self._require_known_domain(domain=domain)
        expected = self._ensure_secret_value(
            secret_name=self._inbound_callback_secret_name,
            secret_kind="inbound_secret",
        )
        if not force_reprocess:
            expected_signature = _render_inbound_capture_signature(
                expected,
                domain=domain_token,
                ses_message_id=ses_message_id,
                s3_uri=s3_uri,
                sender=sender,
                recipient=recipient,
                subject=subject,
                captured_at=captured_at,
            )
            if signature != expected_signature:
                raise PermissionError("inbound callback signature is invalid")
        profile, contact_log = self._profile_from_dispatcher_urls(
            domain=domain_token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )
        selected_author = self._selected_author_for_domain(domain=domain_token, profile=profile)
        expected_sender = _optional_email(profile.get("selected_author_address") or selected_author.get("send_as_email"))
        list_address = _optional_email(profile.get("list_address")) or f"news@{domain_token}"
        if not expected_sender:
            raise ValueError("selected sender is not verified for this domain")
        if _optional_email(sender) != expected_sender:
            raise ValueError("inbound sender does not match the selected verified sender")
        if _optional_email(recipient) != list_address:
            raise ValueError("inbound recipient does not target the canonical list address")
        if (
            not force_reprocess
            and _as_text(profile.get("last_inbound_message_id")) == _as_text(ses_message_id)
            and _as_text(profile.get("last_inbound_status")) == "processed"
        ):
            return {
                "ok": True,
                "already_processed": True,
                "dispatch_id": _as_text(profile.get("last_dispatch_id")),
            }

        region = _as_text(profile.get("aws_region")) or "us-east-1"
        raw_bytes = self._cloud_port.read_s3_bytes(s3_uri=_as_text(s3_uri), region=region)
        body_text = _message_text_from_email(raw_bytes).strip()
        if not body_text:
            raise ValueError("captured inbound newsletter body is empty")
        effective_subject = _as_text(subject) or _message_subject_from_email(raw_bytes)
        if not effective_subject:
            raise ValueError("captured inbound newsletter subject is missing")

        unsubscribe_secret = self._ensure_secret_value(
            secret_name=self._unsubscribe_secret_name,
            secret_kind="signing_secret",
        )
        contact_log = _normalize_contact_log(contact_log, domain=domain_token)
        subscribers = [
            dict(item)
            for item in list(contact_log.get("contacts") or [])
            if isinstance(item, dict) and bool(item.get("subscribed")) and _optional_email(item.get("email"))
        ]

        dispatch_id = f"dispatch-{secrets.token_hex(16)}"
        callback_secret = self._ensure_secret_value(
            secret_name=self._dispatch_callback_secret_name,
            secret_kind="dispatch_secret",
        )
        results: list[dict[str, Any]] = []
        queue_url = _as_text(profile.get("dispatch_queue_url"))
        if not queue_url:
            raise ValueError("newsletter dispatch queue is not configured")
        sender_address = _optional_email(profile.get("sender_address")) or list_address
        reply_to_address = expected_sender

        for recipient_row in subscribers:
            email = _optional_email(recipient_row.get("email"))
            if not email:
                continue
            unsubscribe_url = (
                f"https://{domain_token}/__fnd/newsletter/unsubscribe?email={email}&token="
                f"{_render_unsubscribe_token(unsubscribe_secret, domain=domain_token, email=email)}"
            )
            message_body = {
                "domain": domain_token,
                "dispatch_id": dispatch_id,
                "recipient_email": email,
                "sender_address": sender_address,
                "reply_to_address": reply_to_address,
                "author_address": reply_to_address,
                "author_profile_id": _as_text(selected_author.get("profile_id")),
                "list_address": list_address,
                "subject": effective_subject,
                "body_text": body_text,
                "unsubscribe_url": unsubscribe_url,
                "callback_url": dispatcher_callback_url,
                "callback_token": callback_secret,
                "aws_region": region,
                "source_kind": "inbound_email",
                "source_message_id": _as_text(ses_message_id),
                "source_message_s3_uri": _as_text(s3_uri),
            }
            result_row = {"email": email, "status": "queued", "unsubscribe_url": unsubscribe_url}
            try:
                result_row["queue_message_id"] = self._cloud_port.queue_dispatch_message(
                    queue_url=queue_url,
                    payload=message_body,
                    region=region,
                )
            except Exception as exc:
                result_row["status"] = "failed"
                result_row["error"] = _as_text(exc)
            results.append(result_row)

        now_iso = _utc_now_iso()
        dispatch_row = {
            "dispatch_id": dispatch_id,
            "requested_at": now_iso,
            "completed_at": "" if any(_as_text(row.get("status")) == "queued" for row in results) else now_iso,
            "requested_by": "inbound_capture",
            "domain": domain_token,
            "author_profile_id": _as_text(selected_author.get("profile_id")),
            "author_address": reply_to_address,
            "sender_profile_id": _as_text(selected_author.get("profile_id")),
            "sender_address": sender_address,
            "list_address": list_address,
            "reply_to_address": reply_to_address,
            "subject": effective_subject,
            "body_text": body_text,
            "target_count": len(subscribers),
            "queued_count": sum(1 for row in results if _as_text(row.get("status")) == "queued"),
            "sent_count": sum(1 for row in results if _as_text(row.get("status")) == "sent"),
            "failed_count": sum(1 for row in results if _as_text(row.get("status")) == "failed"),
            "delivery_mode": _DELIVERY_MODE,
            "aws_region": region,
            "source_kind": "inbound_email",
            "source_message_id": _as_text(ses_message_id),
            "source_message_s3_uri": _as_text(s3_uri),
            "source_message_captured_at": _as_text(captured_at),
            "status": (
                "queued"
                if any(_as_text(row.get("status")) == "queued" for row in results)
                else "completed"
                if not any(_as_text(row.get("status")) == "failed" for row in results)
                else "completed_with_errors"
            ),
            "results": results[-_MAX_DISPATCH_RESULT_HISTORY:],
        }
        contact_log["dispatches"] = list(contact_log.get("dispatches") or [])[-(_MAX_DISPATCH_HISTORY - 1):] + [dispatch_row]
        self._state_port.save_contact_log(domain=domain_token, payload=contact_log)

        profile["last_inbound_message_id"] = _as_text(ses_message_id)
        profile["last_inbound_status"] = "processed"
        profile["last_inbound_checked_at"] = now_iso
        profile["last_inbound_processed_at"] = now_iso
        profile["last_inbound_subject"] = effective_subject
        profile["last_inbound_sender"] = expected_sender
        profile["last_inbound_recipient"] = list_address
        profile["last_inbound_error"] = ""
        profile["last_inbound_s3_uri"] = _as_text(s3_uri)
        profile["last_dispatch_id"] = dispatch_id
        self._state_port.save_profile(domain=domain_token, payload=profile)

        return {
            "ok": True,
            "dispatch": dispatch_row,
            "queued_count": dispatch_row["queued_count"],
            "failed_count": dispatch_row["failed_count"],
        }

    def reprocess_latest_inbound(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
    ) -> dict[str, Any]:
        token = self._require_known_domain(domain=domain)
        profile, _contact_log = self._profile_from_dispatcher_urls(
            domain=token,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
        )
        s3_uri = _as_text(profile.get("last_inbound_s3_uri"))
        message_id = _as_text(profile.get("last_inbound_message_id"))
        sender = _as_text(profile.get("last_inbound_sender"))
        recipient = _as_text(profile.get("last_inbound_recipient"))
        subject = _as_text(profile.get("last_inbound_subject"))
        captured_at = _as_text(profile.get("last_inbound_checked_at"))
        if not s3_uri or not message_id:
            raise LookupError("no previously captured inbound newsletter is available for reprocessing")
        return self.process_inbound_capture(
            signature=self.render_inbound_capture_signature(
                domain=token,
                ses_message_id=message_id,
                s3_uri=s3_uri,
                sender=sender,
                recipient=recipient,
                subject=subject,
                captured_at=captured_at,
            ),
            domain=token,
            ses_message_id=message_id,
            s3_uri=s3_uri,
            sender=sender,
            recipient=recipient,
            subject=subject,
            captured_at=captured_at,
            dispatcher_callback_url=dispatcher_callback_url,
            inbound_callback_url=inbound_callback_url,
            force_reprocess=True,
        )
