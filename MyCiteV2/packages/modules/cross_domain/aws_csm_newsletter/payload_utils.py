from __future__ import annotations

from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
import hashlib
import hmac
from typing import Any

from MyCiteV2.packages.modules.shared import as_text, utc_now_iso
from MyCiteV2.packages.ports.aws_csm_newsletter import AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA

MAX_DISPATCH_HISTORY = 20
MAX_DISPATCH_RESULT_HISTORY = 100
MAX_CONTACT_PREVIEW = 50
DELIVERY_MODE = "inbound-mail-workflow"


def normalized_email(value: object, *, field_name: str) -> str:
    token = as_text(value).lower()
    if not token or token.count("@") != 1 or any(ch.isspace() for ch in token):
        raise ValueError(f"{field_name} must be an email-like value")
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        raise ValueError(f"{field_name} must be an email-like value")
    return token


def normalized_domain(value: object, *, field_name: str) -> str:
    token = as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    if not token or "." not in token:
        raise ValueError(f"{field_name} must be a domain-like value")
    return token


def optional_email(value: object) -> str:
    token = as_text(value).lower()
    if not token:
        return ""
    try:
        return normalized_email(token, field_name="email")
    except ValueError:
        return ""


def preserved_email(value: object) -> str:
    raw = as_text(value)
    for _name, address in getaddresses([raw]):
        candidate = optional_email(address)
        if candidate:
            return candidate
    return optional_email(raw)


def email_addresses(value: object) -> set[str]:
    out: set[str] = set()
    raw = as_text(value)
    for _name, address in getaddresses([raw]):
        candidate = optional_email(address)
        if candidate:
            out.add(candidate)
    fallback = optional_email(raw)
    if fallback:
        out.add(fallback)
    return out


def render_unsubscribe_token(secret: str, *, domain: str, email: str) -> str:
    payload = f"{normalized_domain(domain, field_name='domain')}|{normalized_email(email, field_name='email')}".encode(
        "utf-8"
    )
    return hmac.new(as_text(secret).encode("utf-8"), payload, hashlib.sha256).hexdigest()


def render_inbound_capture_signature(
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
            normalized_domain(domain, field_name="domain"),
            as_text(ses_message_id),
            as_text(s3_uri),
            optional_email(sender),
            optional_email(recipient),
            as_text(subject),
            as_text(captured_at),
        ]
    ).encode("utf-8")
    return hmac.new(as_text(secret).encode("utf-8"), payload, hashlib.sha256).hexdigest()


def normalize_contact(contact: Any) -> dict[str, Any] | None:
    if not isinstance(contact, dict):
        return None
    email = optional_email(contact.get("email"))
    if not email:
        return None
    created_at = as_text(contact.get("created_at")) or utc_now_iso()
    subscribed = bool(contact.get("subscribed", True))
    return {
        "email": email,
        "name": as_text(contact.get("name")),
        "zip": as_text(contact.get("zip")),
        "source": as_text(contact.get("source")) or "unknown",
        "subscribed": subscribed,
        "created_at": created_at,
        "subscribed_at": as_text(contact.get("subscribed_at")) or (created_at if subscribed else ""),
        "unsubscribed_at": as_text(contact.get("unsubscribed_at")),
        "updated_at": as_text(contact.get("updated_at")) or created_at,
        "last_newsletter_sent_at": as_text(contact.get("last_newsletter_sent_at")),
        "send_count": int(contact.get("send_count") or 0),
        "notes": as_text(contact.get("notes")),
    }


def normalize_contact_log(payload: dict[str, Any], *, domain: str) -> dict[str, Any]:
    token = normalized_domain(domain, field_name="domain")
    contacts_by_email: dict[str, dict[str, Any]] = {}
    for raw in list(payload.get("contacts") or []):
        normalized = normalize_contact(raw)
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
        "dispatches": dispatches[-MAX_DISPATCH_HISTORY:],
        "updated_at": as_text(payload.get("updated_at")) or utc_now_iso(),
    }


def contact_summary(contact_log: dict[str, Any]) -> dict[str, int]:
    subscribed = 0
    unsubscribed = 0
    for raw in list(contact_log.get("contacts") or []):
        normalized = normalize_contact(raw)
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


def message_text_from_email(raw_bytes: bytes) -> str:
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


def message_subject_from_email(raw_bytes: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    return as_text(message.get("Subject"))


__all__ = [
    "DELIVERY_MODE",
    "MAX_CONTACT_PREVIEW",
    "MAX_DISPATCH_HISTORY",
    "MAX_DISPATCH_RESULT_HISTORY",
    "contact_summary",
    "email_addresses",
    "message_subject_from_email",
    "message_text_from_email",
    "normalize_contact",
    "normalize_contact_log",
    "normalized_domain",
    "normalized_email",
    "optional_email",
    "preserved_email",
    "render_inbound_capture_signature",
    "render_unsubscribe_token",
]
