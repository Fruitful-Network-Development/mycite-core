from __future__ import annotations

import json
import secrets
from typing import Any

from MyCiteV2.packages.modules.shared import as_text
from MyCiteV2.packages.ports.aws_csm_newsletter import (
    AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
    AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
    AwsCsmNewsletterCloudPort,
    AwsCsmNewsletterStatePort,
)
from MyCiteV2.packages.modules.shared import dedupe_warnings, utc_now_iso
from .payload_utils import (
    DELIVERY_MODE as _DELIVERY_MODE,
    MAX_CONTACT_PREVIEW as _MAX_CONTACT_PREVIEW,
    MAX_DISPATCH_HISTORY as _MAX_DISPATCH_HISTORY,
    MAX_DISPATCH_RESULT_HISTORY as _MAX_DISPATCH_RESULT_HISTORY,
    contact_summary as _contact_summary,
    email_addresses as _email_addresses,
    message_subject_from_email as _message_subject_from_email,
    message_text_from_email as _message_text_from_email,
    normalize_contact as _normalize_contact,
    normalize_contact_log as _normalize_contact_log,
    normalized_domain as _normalized_domain,
    normalized_email as _normalized_email,
    optional_email as _optional_email,
    preserved_email as _preserved_email,
    render_inbound_capture_signature as _render_inbound_capture_signature,
    render_unsubscribe_token as _render_unsubscribe_token,
)


def _as_text(value: object) -> str:
    return as_text(value)


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
        seed = self._state_port.runtime_secret_seed(secret_kind=secret_kind) or secrets.token_urlsafe(32)
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
            "schema": "mycite.v2.portal.system.tools.aws_csm.newsletter_domain_state.v1",
            "domain": token,
            "profile": dict(profile),
            "selected_author": dict(selected_author),
            "verified_author_profiles": list(verified),
            "contacts": list(normalized_contact_log.get("contacts") or []),
            "contacts_preview": list(normalized_contact_log.get("contacts") or [])[:_MAX_CONTACT_PREVIEW],
            "dispatches": list(normalized_contact_log.get("dispatches") or []),
            "latest_dispatch": latest_dispatch,
            "warnings": dedupe_warnings(warnings),
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
            "schema": "mycite.v2.portal.system.tools.aws_csm.family_health.v1",
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
        now_iso = utc_now_iso()
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
        now_iso = utc_now_iso()
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
        now_iso = utc_now_iso()
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

        now_iso = utc_now_iso()
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
