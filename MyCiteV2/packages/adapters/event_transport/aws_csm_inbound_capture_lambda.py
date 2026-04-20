from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import urllib.request
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from typing import Any

import boto3


SES_REGION = os.environ.get("SES_REGION", "us-east-1").strip() or "us-east-1"
INBOUND_SECRET_NAME = os.environ.get("INBOUND_SECRET_NAME", "").strip()
CALLBACK_URL_TEMPLATE = os.environ.get(
    "CALLBACK_URL_TEMPLATE",
    "https://{domain}/__fnd/newsletter/inbound-capture",
).strip()
S3_BUCKET = os.environ.get("S3_BUCKET", "ses-inbound-fnd-mail").strip()
S3_PREFIX_TEMPLATE = os.environ.get("S3_PREFIX_TEMPLATE", "inbound/{domain}/").strip()
VERIFICATION_ROUTE_MAP_JSON = os.environ.get("VERIFICATION_ROUTE_MAP_JSON", "{}").strip()
VERIFICATION_ALLOWED_SENDERS_JSON = os.environ.get(
    "VERIFICATION_ALLOWED_SENDERS_JSON",
    "[]",
).strip()
VERIFICATION_FORWARD_FROM_ADDRESS = os.environ.get(
    "VERIFICATION_FORWARD_FROM_ADDRESS",
    "forwarder@fruitfulnetworkdevelopment.com",
).strip()

_REPORT_SUBJECT_TOKENS = (
    "report-id:",
    "report domain:",
    "aggregate report",
    "feedback report",
    "dmarc",
)
_REPORT_SENDER_TOKENS = ("dmarc",)
_CONFIRMATION_SUBJECT_PREFIX = "gmail confirmation - send mail as "
_LINK_PATTERN = re.compile(r"https?://[^\s<>\"]+")
_PROVIDER_SUBJECT_HINTS: dict[str, tuple[str, ...]] = {
    "gmail": (_CONFIRMATION_SUBJECT_PREFIX,),
    "outlook": ("verify", "verification", "confirm", "microsoft", "outlook"),
    "yahoo": ("verify", "verification", "confirm", "yahoo"),
    "proofpoint": ("verify", "verification", "confirm", "proofpoint"),
    "generic_manual": ("verify", "verification", "confirm"),
}
_PROVIDER_ALLOWED_SENDERS: dict[str, set[str]] = {
    "gmail": {"gmail-noreply@google.com"},
    "outlook": {
        "account-security-noreply@accountprotection.microsoft.com",
        "noreply@outlook.com",
        "no-reply@microsoft.com",
    },
    "yahoo": {
        "account-security@yahoo-inc.com",
        "no-reply@yahoo.com",
        "noreply@yahoo.com",
    },
    "proofpoint": set(),
    "generic_manual": set(),
}

_secrets = boto3.client("secretsmanager", region_name=SES_REGION)
_s3 = boto3.client("s3", region_name=SES_REGION)
_sesv2 = boto3.client("sesv2", region_name=SES_REGION)
_cached_secret: str | None = None
_cached_routes: dict[str, dict[str, Any]] | None = None
_cached_allowed_senders: set[str] | None = None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _normalized_domain(value: object) -> str:
    token = _text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _normalized_email(value: object) -> str:
    token = _text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _normalized_provider(value: object) -> str:
    token = _text(value).lower()
    if token in _PROVIDER_SUBJECT_HINTS:
        return token
    return "generic_manual"


def _recipient_domain(recipient: object) -> str:
    token = _normalized_email(recipient)
    return token.split("@", 1)[1] if token else ""


def _provider_from_email(email: object) -> str:
    domain = _recipient_domain(email)
    if domain in {"gmail.com", "googlemail.com"}:
        return "gmail"
    if domain in {"outlook.com", "hotmail.com", "live.com", "msn.com"}:
        return "outlook"
    if domain in {"yahoo.com", "rocketmail.com", "ymail.com"}:
        return "yahoo"
    if domain.endswith("proofpoint.com"):
        return "proofpoint"
    return "generic_manual"


def _extract_links(raw_bytes: bytes) -> list[str]:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    text_parts: list[str] = []
    if hasattr(message, "walk"):
        for part in message.walk():
            disposition = str(part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            try:
                text_parts.append(str(part.get_content() or ""))
            except Exception:  # noqa: BLE001
                payload = part.get_payload(decode=True)
                if payload:
                    charset = str(part.get_content_charset() or "utf-8")
                    text_parts.append(payload.decode(charset, errors="replace"))
    joined = "\n".join(part for part in text_parts if part)
    return [match.group(0) for match in _LINK_PATTERN.finditer(joined)]


def _message_summary(raw_bytes: bytes) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    sender = next(
        (
            _normalized_email(address)
            for _, address in getaddresses(message.get_all("From", []))
            if _normalized_email(address)
        ),
        "",
    )
    recipient = next(
        (
            _normalized_email(address)
            for _, address in getaddresses(
                message.get_all("Delivered-To", [])
                + message.get_all("X-Original-To", [])
                + message.get_all("To", [])
            )
            if _normalized_email(address)
        ),
        "",
    )
    return {
        "sender": sender,
        "recipient": recipient,
        "subject": _text(message.get("Subject")),
        "links": _extract_links(raw_bytes),
    }


def _inbound_secret() -> str:
    global _cached_secret
    if _cached_secret:
        return _cached_secret
    response = _secrets.get_secret_value(SecretId=INBOUND_SECRET_NAME)
    _cached_secret = _text(response.get("SecretString"))
    return _cached_secret


def _signature(secret: str, *, domain: str, ses_message_id: str, s3_uri: str, sender: str, recipient: str, subject: str, captured_at: str) -> str:
    payload = "|".join(
        [
            _normalized_domain(domain),
            _text(ses_message_id),
            _text(s3_uri),
            _normalized_email(sender),
            _normalized_email(recipient),
            _text(subject),
            _text(captured_at),
        ]
    ).encode("utf-8")
    return hmac.new(_text(secret).encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _callback_url(domain: str) -> str:
    return CALLBACK_URL_TEMPLATE.format(domain=_normalized_domain(domain))


def _candidate_s3_uris(domain: str, message_id: str) -> list[str]:
    domain_token = _normalized_domain(domain)
    message_token = _text(message_id)
    prefix = S3_PREFIX_TEMPLATE.format(domain=domain_token).lstrip("/")
    candidates = []
    if domain_token and message_token:
        candidates.append(f"s3://{S3_BUCKET}/{prefix}{message_token}")
        candidates.append(f"s3://{S3_BUCKET}/inbound/{domain_token}/{message_token}")
        candidates.append(f"s3://{S3_BUCKET}/inbound/{message_token}")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _split_s3_uri(s3_uri: str) -> tuple[str, str]:
    token = _text(s3_uri)
    if not token.startswith("s3://") or "/" not in token[5:]:
        raise ValueError("invalid s3 uri")
    bucket, key = token[5:].split("/", 1)
    return bucket, key


def _read_raw_message(s3_uri: str) -> bytes:
    bucket, key = _split_s3_uri(s3_uri)
    response = _s3.get_object(Bucket=bucket, Key=key)
    body = response.get("Body")
    if body is None:
        raise RuntimeError("s3 object body missing")
    return bytes(body.read())


def _post_callback(payload: dict[str, str]) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _callback_url(payload["domain"]),
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Newsletter-Inbound-Signature": payload["signature"],
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace").strip()
        if response.status >= 300:
            raise RuntimeError(f"callback failed with HTTP {response.status}: {body}")


def _verification_routes() -> dict[str, dict[str, Any]]:
    global _cached_routes
    if _cached_routes is not None:
        return _cached_routes
    try:
        payload = json.loads(VERIFICATION_ROUTE_MAP_JSON or "{}")
    except json.JSONDecodeError:
        payload = {}
    out: dict[str, dict[str, Any]] = {}
    if isinstance(payload, dict):
        for recipient, route in payload.items():
            normalized_recipient = _normalized_email(recipient)
            if not normalized_recipient:
                continue
            if isinstance(route, str):
                destination = _normalized_email(route)
                if not destination:
                    continue
                out[normalized_recipient] = {
                    "forward_to_email": destination,
                    "resolved_forward_to_email": destination,
                    "source_forward_to_email": destination,
                    "forward_resolution_status": "resolved_external",
                    "forward_chain": [normalized_recipient, destination],
                    "profile_id": "",
                    "domain": _recipient_domain(normalized_recipient),
                    "handoff_provider": _provider_from_email(destination),
                }
                continue
            if not isinstance(route, dict):
                continue
            forward_to_email = _normalized_email(
                route.get("f")
                or route.get("resolved_forward_to_email")
                or route.get("forward_to_email")
            )
            resolved_forward_to_email = _normalized_email(
                route.get("resolved_forward_to_email")
                or route.get("f")
                or route.get("forward_to_email")
                or forward_to_email
            )
            if not forward_to_email or not resolved_forward_to_email:
                continue
            out[normalized_recipient] = {
                "forward_to_email": forward_to_email,
                "resolved_forward_to_email": resolved_forward_to_email,
                "source_forward_to_email": _normalized_email(
                    route.get("source_forward_to_email") or route.get("forward_to_email") or forward_to_email
                ),
                "forward_resolution_status": _text(route.get("s") or route.get("forward_resolution_status")),
                "forward_chain": list(route.get("c") or route.get("forward_chain") or []),
                "profile_id": _text(route.get("profile_id")),
                "domain": _normalized_domain(route.get("domain")) or _recipient_domain(normalized_recipient),
                "handoff_provider": _normalized_provider(
                    route.get("p") or route.get("handoff_provider") or _provider_from_email(forward_to_email)
                ),
            }
    _cached_routes = out
    return out


def _allowed_senders() -> set[str]:
    global _cached_allowed_senders
    if _cached_allowed_senders is not None:
        return _cached_allowed_senders
    try:
        payload = json.loads(VERIFICATION_ALLOWED_SENDERS_JSON or "[]")
    except json.JSONDecodeError:
        payload = []
    allowed = {
        _normalized_email(item)
        for item in list(payload or [])
        if _normalized_email(item)
    }
    _cached_allowed_senders = allowed
    return _cached_allowed_senders


def _allowed_senders_for_provider(provider: str) -> set[str]:
    provider_defaults = set(_PROVIDER_ALLOWED_SENDERS.get(provider, set()))
    return provider_defaults.union(_allowed_senders())


def _subject_matches_provider(*, provider: str, lowered_subject: str) -> bool:
    if provider == "gmail":
        return lowered_subject.startswith(_CONFIRMATION_SUBJECT_PREFIX)
    hints = _PROVIDER_SUBJECT_HINTS.get(provider, _PROVIDER_SUBJECT_HINTS["generic_manual"])
    return any(token in lowered_subject for token in hints)


def _decision(
    *,
    tracked_recipients: set[str],
    sender: str,
    recipient: str,
    subject: str,
    raw_bytes: bytes,
    handoff_provider: str,
) -> dict[str, Any]:
    provider = _normalized_provider(handoff_provider)
    normalized_sender = _normalized_email(sender)
    normalized_recipient = _normalized_email(recipient)
    normalized_subject = _text(subject)
    lowered_subject = normalized_subject.lower()
    if any(token in normalized_sender for token in _REPORT_SENDER_TOKENS):
        return {"should_forward": False, "classification": "blocked_report", "reason": "sender_report_like"}
    if any(token in lowered_subject for token in _REPORT_SUBJECT_TOKENS):
        return {"should_forward": False, "classification": "blocked_report", "reason": "subject_report_like"}
    allowed_senders = _allowed_senders_for_provider(provider)
    if allowed_senders and normalized_sender not in allowed_senders:
        return {"should_forward": False, "classification": "blocked_sender", "reason": "sender_not_allowlisted"}
    if normalized_recipient not in tracked_recipients:
        return {"should_forward": False, "classification": "blocked_recipient", "reason": "recipient_not_tracked"}
    if not _subject_matches_provider(provider=provider, lowered_subject=lowered_subject):
        return {"should_forward": False, "classification": "blocked_subject", "reason": "subject_not_confirmation"}
    links = _extract_links(raw_bytes)
    if not links:
        return {"should_forward": False, "classification": "blocked_missing_link", "reason": "missing_confirmation_link"}
    return {
        "should_forward": True,
        "classification": f"verification_confirmation_{provider}",
        "reason": f"{provider}_confirmation",
        "links": links,
    }


def _send_verification_forward(
    *,
    route: dict[str, Any],
    tracked_recipient: str,
    sender: str,
    subject: str,
    links: list[str],
    s3_uri: str,
) -> dict[str, str]:
    destination = _text(route.get("resolved_forward_to_email") or route.get("forward_to_email"))
    handoff_provider = _normalized_provider(route.get("handoff_provider"))
    response = _sesv2.send_email(
        FromEmailAddress=VERIFICATION_FORWARD_FROM_ADDRESS,
        Destination={"ToAddresses": [destination]},
        Content={
            "Simple": {
                "Subject": {"Data": f"AWS-CSM send-as confirmation ({handoff_provider}) for {tracked_recipient}"},
                "Body": {
                    "Text": {
                        "Data": "\n".join(
                            [
                                f"Send-as confirmation received for {tracked_recipient}.",
                                "",
                                f"Original sender: {sender}",
                                f"Original subject: {subject}",
                                f"Captured message: {s3_uri}",
                                f"Forward provider: {handoff_provider}",
                                "",
                                "Confirmation link:",
                                *(links[:3] or ["(missing)"]),
                                "",
                                "Only verification-class mail is forwarded by this processor.",
                            ]
                        )
                    }
                },
            }
        },
    )
    return {
        "message_id": _text(response.get("MessageId")),
        "sent_to": destination,
    }


def _handle_newsletter_record(*, domain: str, message_id: str, sender: str, recipient: str, subject: str, captured_at: str) -> None:
    s3_uri = _candidate_s3_uris(domain, message_id)[0]
    payload = {
        "domain": domain,
        "ses_message_id": message_id,
        "s3_uri": s3_uri,
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "captured_at": captured_at,
    }
    payload["signature"] = _signature(_inbound_secret(), **payload)
    _post_callback(payload)


def _handle_verification_record(
    *,
    destinations: list[str],
    mail_source: str,
    subject: str,
    message_id: str,
) -> list[dict[str, str]]:
    route_map = _verification_routes()
    tracked = [recipient for recipient in destinations if recipient in route_map]
    if not tracked:
        return []
    recipient = tracked[0]
    domain = _recipient_domain(recipient)
    raw_bytes = b""
    s3_uri = ""
    for candidate in _candidate_s3_uris(domain, message_id):
        try:
            raw_bytes = _read_raw_message(candidate)
            s3_uri = candidate
            break
        except Exception:  # noqa: BLE001
            continue
    if not raw_bytes:
        raise RuntimeError(f"unable to read captured verification message for {recipient}")
    summary = _message_summary(raw_bytes)
    resolved_sender = _text(summary.get("sender") or mail_source)
    resolved_recipient = _text(summary.get("recipient") or recipient)
    resolved_subject = _text(summary.get("subject") or subject)
    decision = _decision(
        tracked_recipients=set(tracked),
        sender=resolved_sender,
        recipient=resolved_recipient,
        subject=resolved_subject,
        raw_bytes=raw_bytes,
        handoff_provider=_text(route_map[recipient].get("handoff_provider")),
    )
    print(
        json.dumps(
            {
                "kind": "aws_csm_verification_forward_decision",
                "message_id": message_id,
                "recipient": resolved_recipient,
                "classification": decision.get("classification"),
                "reason": decision.get("reason"),
                "s3_uri": s3_uri,
                "handoff_provider": _text(route_map[recipient].get("handoff_provider")),
                "forward_resolution_status": _text(route_map[recipient].get("forward_resolution_status")),
            }
        )
    )
    if not decision.get("should_forward"):
        return []
    route = route_map[recipient]
    return [
        _send_verification_forward(
            route=route,
            tracked_recipient=recipient,
            sender=resolved_sender,
            subject=resolved_subject,
            links=list(decision.get("links") or []),
            s3_uri=s3_uri,
        )
    ]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    forwarded: list[dict[str, str]] = []
    processed_records = 0
    for record in list((event or {}).get("Records") or []):
        ses = record.get("ses") or {}
        mail = ses.get("mail") or {}
        receipt = ses.get("receipt") or {}
        message_id = _text(mail.get("messageId"))
        sender = _text(mail.get("source"))
        destinations = [
            _normalized_email(recipient)
            for recipient in list(mail.get("destination") or receipt.get("recipients") or [])
            if _normalized_email(recipient)
        ]
        subject = _text(((mail.get("commonHeaders") or {}).get("subject")))
        captured_at = _text(receipt.get("timestamp"))
        newsletter_recipient = next((recipient for recipient in destinations if recipient.startswith("news@")), "")
        if newsletter_recipient:
            domain = _recipient_domain(newsletter_recipient)
            if not all([message_id, sender, newsletter_recipient, domain]):
                raise RuntimeError("SES event is missing required inbound newsletter fields")
            _handle_newsletter_record(
                domain=domain,
                message_id=message_id,
                sender=sender,
                recipient=newsletter_recipient,
                subject=subject,
                captured_at=captured_at,
            )
        else:
            forwarded.extend(
                _handle_verification_record(
                    destinations=destinations,
                    mail_source=sender,
                    subject=subject,
                    message_id=message_id,
                )
            )
        processed_records += 1
    return {"ok": True, "processed_records": processed_records, "forwarded": forwarded}
