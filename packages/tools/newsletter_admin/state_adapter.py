from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mycite_core.runtime_paths import utility_tools_dir
from packages.tools.aws_csm.state_adapter.profile import normalize_aws_csm_profile_payload

NEWSLETTER_CONTACT_LOG_SCHEMA = "mycite.webapp.contact_log.v1"
NEWSLETTER_PROFILE_SCHEMA = "mycite.service_tool.newsletter.profile.v1"
NEWSLETTER_NAMESPACE = "newsletter-admin"


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def newsletter_state_root(private_dir: Path) -> Path:
    return utility_tools_dir(Path(private_dir)) / NEWSLETTER_NAMESPACE


def newsletter_profile_path(private_dir: Path, domain: str) -> Path:
    token = _text(domain).lower()
    return newsletter_state_root(private_dir) / f"newsletter-admin.{token}.json"


def newsletter_secret_path(private_dir: Path) -> Path:
    return newsletter_state_root(private_dir) / ".newsletter-signing-secret"


def newsletter_dispatch_secret_path(private_dir: Path) -> Path:
    return newsletter_state_root(private_dir) / ".newsletter-dispatch-secret"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fallback_client_root(domain: str) -> Path:
    return Path("/srv/webapps/clients") / _text(domain).lower()


def _csv_addresses(value: object) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    raw = _text(value).replace(";", ",")
    for token in raw.split(","):
        item = _text(token).lower()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def newsletter_site_roots(private_dir: Path) -> dict[str, Path]:
    root = utility_tools_dir(Path(private_dir)) / "fnd-ebi"
    out: dict[str, Path] = {}
    if root.exists() and root.is_dir():
        for path in sorted(root.glob("fnd-ebi.*.json")):
            payload = _read_json(path)
            domain = _text(payload.get("domain")).lower()
            site_root = _text(payload.get("site_root"))
            if not domain or not site_root:
                continue
            out[domain] = Path(site_root).resolve()
    for domain in list(out.keys()):
        continue
    return out


def newsletter_contact_log_path(private_dir: Path, domain: str) -> Path:
    token = _text(domain).lower()
    site_root = newsletter_site_roots(private_dir).get(token)
    if site_root is None:
        site_root = (_fallback_client_root(token) / "frontend").resolve()
    client_root = site_root.parent
    return (client_root / "contacts" / f"{token}-contact_log.json").resolve()


def _compatibility_newsletter_profile(private_dir: Path, domain: str) -> dict[str, Any]:
    token = _text(domain).lower()
    root = Path(private_dir) / "network" / "progeny"
    if not root.exists() or not root.is_dir():
        return {}
    for path in sorted(root.glob("*.json")):
        payload = _read_json(path)
        refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
        policy = payload.get("email_policy") if isinstance(payload.get("email_policy"), dict) else {}
        newsletter = policy.get("newsletter") if isinstance(policy.get("newsletter"), dict) else {}
        sender_address = _text(newsletter.get("sender_address") or refs.get("newsletter_sender_address")).lower()
        ingest_address = _text(newsletter.get("ingest_address") or refs.get("newsletter_ingest_address")).lower()
        resolved_domain = ""
        if "@" in sender_address:
            resolved_domain = sender_address.split("@", 1)[1].strip().lower()
        elif "@" in ingest_address:
            resolved_domain = ingest_address.split("@", 1)[1].strip().lower()
        else:
            resolved_domain = _text(refs.get("paypal_site_domain") or payload.get("domain")).lower()
        if resolved_domain != token:
            continue
        allowed_from = list(newsletter.get("allowed_from") or []) if isinstance(newsletter.get("allowed_from"), list) else []
        allowed_from_csv = _text(refs.get("newsletter_allowed_from_csv")) or ", ".join(
            [_text(item).lower() for item in allowed_from if _text(item)]
        )
        return {
            "domain": token,
            "sender_address": sender_address,
            "ingest_address": ingest_address,
            "allowed_from_csv": allowed_from_csv,
            "allowed_from": _csv_addresses(allowed_from_csv),
            "dispatch_mode": _text(newsletter.get("dispatch_mode") or refs.get("newsletter_dispatch_mode")) or "aws_internal",
            "source_path": str(path),
        }
    return {}


def default_contact_log(domain: str) -> dict[str, Any]:
    token = _text(domain).lower()
    return {
        "schema": NEWSLETTER_CONTACT_LOG_SCHEMA,
        "domain": token,
        "contacts": [],
        "dispatches": [],
        "updated_at": _utc_now_iso(),
    }


def _normalize_contact(contact: Any) -> dict[str, Any] | None:
    if not isinstance(contact, dict):
        return None
    email = _text(contact.get("email")).lower()
    if not email:
        return None
    created_at = _text(contact.get("created_at")) or _utc_now_iso()
    subscribed = bool(contact.get("subscribed", True))
    return {
        "email": email,
        "name": _text(contact.get("name")),
        "zip": _text(contact.get("zip")),
        "source": _text(contact.get("source")) or "unknown",
        "subscribed": subscribed,
        "created_at": created_at,
        "subscribed_at": _text(contact.get("subscribed_at")) or (created_at if subscribed else ""),
        "unsubscribed_at": _text(contact.get("unsubscribed_at")),
        "updated_at": _text(contact.get("updated_at")) or created_at,
        "last_newsletter_sent_at": _text(contact.get("last_newsletter_sent_at")),
        "send_count": int(contact.get("send_count") or 0),
        "notes": _text(contact.get("notes")),
    }


def load_contact_log(private_dir: Path, domain: str) -> tuple[Path, dict[str, Any]]:
    token = _text(domain).lower()
    path = newsletter_contact_log_path(private_dir, token)
    payload = _read_json(path)
    if _text(payload.get("schema")) != NEWSLETTER_CONTACT_LOG_SCHEMA:
        payload = default_contact_log(token)
    payload["domain"] = token
    contacts_by_email: dict[str, dict[str, Any]] = {}
    for raw in list(payload.get("contacts") or []):
        normalized = _normalize_contact(raw)
        if normalized is None:
            continue
        contacts_by_email[normalized["email"]] = normalized
    payload["contacts"] = [
        contacts_by_email[key]
        for key in sorted(contacts_by_email.keys())
    ]
    dispatches = []
    for item in list(payload.get("dispatches") or []):
        if not isinstance(item, dict):
            continue
        dispatches.append(dict(item))
    payload["dispatches"] = dispatches[-20:]
    payload["updated_at"] = _text(payload.get("updated_at")) or _utc_now_iso()
    return path, payload


def save_contact_log(path: Path, payload: dict[str, Any]) -> None:
    body = dict(payload if isinstance(payload, dict) else {})
    body["schema"] = NEWSLETTER_CONTACT_LOG_SCHEMA
    body["domain"] = _text(body.get("domain")).lower()
    body["updated_at"] = _utc_now_iso()
    _write_json(path, body)


def upsert_contact_record(
    contact_log: dict[str, Any],
    *,
    email: str,
    name: str = "",
    zip_code: str = "",
    source: str = "website_signup",
    subscribed: bool = True,
) -> dict[str, Any]:
    token = _text(email).lower()
    if not token:
        raise ValueError("email is required")
    now_iso = _utc_now_iso()
    contacts = list(contact_log.get("contacts") or [])
    current = None
    remaining = []
    for item in contacts:
        normalized = _normalize_contact(item)
        if normalized is None:
            continue
        if normalized["email"] == token:
            current = normalized
            continue
        remaining.append(normalized)
    if current is None:
        current = {
            "email": token,
            "name": _text(name),
            "zip": _text(zip_code),
            "source": _text(source) or "website_signup",
            "subscribed": bool(subscribed),
            "created_at": now_iso,
            "subscribed_at": now_iso if subscribed else "",
            "unsubscribed_at": "",
            "updated_at": now_iso,
            "last_newsletter_sent_at": "",
            "send_count": 0,
            "notes": "",
        }
    else:
        if _text(name):
            current["name"] = _text(name)
        if _text(zip_code):
            current["zip"] = _text(zip_code)
        current["source"] = _text(source) or _text(current.get("source")) or "website_signup"
        current["subscribed"] = bool(subscribed)
        current["updated_at"] = now_iso
        if subscribed:
            current["subscribed_at"] = _text(current.get("subscribed_at")) or now_iso
            current["unsubscribed_at"] = ""
    remaining.append(current)
    contact_log["contacts"] = sorted(remaining, key=lambda item: _text(item.get("email")).lower())
    contact_log["updated_at"] = now_iso
    return current


def unsubscribe_contact_record(contact_log: dict[str, Any], *, email: str, source: str = "unsubscribe_link") -> dict[str, Any] | None:
    token = _text(email).lower()
    if not token:
        return None
    now_iso = _utc_now_iso()
    contacts = list(contact_log.get("contacts") or [])
    updated = None
    remaining = []
    for item in contacts:
        normalized = _normalize_contact(item)
        if normalized is None:
            continue
        if normalized["email"] == token:
            normalized["subscribed"] = False
            normalized["source"] = _text(source) or _text(normalized.get("source")) or "unsubscribe_link"
            normalized["unsubscribed_at"] = now_iso
            normalized["updated_at"] = now_iso
            updated = normalized
        remaining.append(normalized)
    contact_log["contacts"] = sorted(remaining, key=lambda item: _text(item.get("email")).lower())
    contact_log["updated_at"] = now_iso
    return updated


def load_newsletter_profile(private_dir: Path, domain: str) -> tuple[Path, dict[str, Any]]:
    token = _text(domain).lower()
    path = newsletter_profile_path(private_dir, token)
    payload = _read_json(path)
    list_address = _text(payload.get("list_address")) or f"news@{token}"
    selected_author_profile_id = _text(payload.get("selected_author_profile_id") or payload.get("selected_sender_profile_id"))
    selected_author_address = _text(payload.get("selected_author_address") or payload.get("selected_sender_address"))
    sender_address = _text(payload.get("sender_address")) or list_address
    profile = {
        "schema": NEWSLETTER_PROFILE_SCHEMA,
        "domain": token,
        "list_address": list_address,
        "sender_address": sender_address,
        "dispatch_mode": _text(payload.get("dispatch_mode")) or "inbound_mail_workflow",
        "selected_author_profile_id": selected_author_profile_id,
        "selected_author_address": selected_author_address,
        "selected_sender_profile_id": selected_author_profile_id,
        "selected_sender_address": selected_author_address,
        "contact_log_path": _text(payload.get("contact_log_path")) or str(newsletter_contact_log_path(private_dir, token)),
        "delivery_mode": _text(payload.get("delivery_mode")) or "aws_sqs_lambda_us_east_1",
        "aws_region": _text(payload.get("aws_region")) or "us-east-1",
        "dispatch_queue_url": _text(payload.get("dispatch_queue_url")),
        "dispatch_queue_arn": _text(payload.get("dispatch_queue_arn")),
        "dispatcher_lambda_name": _text(payload.get("dispatcher_lambda_name")),
        "dispatcher_callback_url": _text(payload.get("dispatcher_callback_url")),
        "last_inbound_message_id": _text(payload.get("last_inbound_message_id")),
        "last_inbound_status": _text(payload.get("last_inbound_status")),
        "last_inbound_checked_at": _text(payload.get("last_inbound_checked_at")),
        "last_inbound_processed_at": _text(payload.get("last_inbound_processed_at")),
        "last_inbound_subject": _text(payload.get("last_inbound_subject")),
        "last_inbound_sender": _text(payload.get("last_inbound_sender")),
        "last_inbound_recipient": _text(payload.get("last_inbound_recipient")),
        "last_inbound_error": _text(payload.get("last_inbound_error")),
        "last_inbound_s3_uri": _text(payload.get("last_inbound_s3_uri")),
        "last_dispatch_id": _text(payload.get("last_dispatch_id")),
        "updated_at": _text(payload.get("updated_at")) or _utc_now_iso(),
    }
    return path, profile


def save_newsletter_profile(path: Path, payload: dict[str, Any]) -> None:
    body = dict(payload if isinstance(payload, dict) else {})
    body["schema"] = NEWSLETTER_PROFILE_SCHEMA
    body["domain"] = _text(body.get("domain")).lower()
    body["updated_at"] = _utc_now_iso()
    _write_json(path, body)


def verified_sender_profiles(private_dir: Path, domain: str) -> list[dict[str, Any]]:
    root = utility_tools_dir(Path(private_dir)) / "aws-csm"
    token = _text(domain).lower()
    out: list[dict[str, Any]] = []
    if not root.exists() or not root.is_dir():
        return out
    for path in sorted(root.glob("aws-csm.*.json")):
        payload = _read_json(path)
        profile_hint = path.stem.removeprefix("aws-csm.")
        normalized, _, _ = normalize_aws_csm_profile_payload(payload, profile_hint=profile_hint)
        identity_raw = dict(payload.get("identity") or {}) if isinstance(payload.get("identity"), dict) else {}
        verification_raw = dict(payload.get("verification") or {}) if isinstance(payload.get("verification"), dict) else {}
        provider_raw = dict(payload.get("provider") or {}) if isinstance(payload.get("provider"), dict) else {}
        identity = dict(normalized.get("identity") or {})
        raw_domain = _text(identity_raw.get("domain")).lower()
        if (raw_domain or _text(identity.get("domain")).lower()) != token:
            continue
        provider_status = _text(provider_raw.get("gmail_send_as_status") or (normalized.get("provider") or {}).get("gmail_send_as_status")).lower()
        verification_status = _text(verification_raw.get("status") or (normalized.get("verification") or {}).get("status")).lower()
        if provider_status != "verified":
            continue
        if verification_status != "verified":
            continue
        out.append(
            {
                "profile_id": _text(identity_raw.get("profile_id") or identity.get("profile_id")),
                "send_as_email": _text(identity_raw.get("send_as_email") or identity.get("send_as_email")) or _text((normalized.get("smtp") or {}).get("send_as_email")),
                "mailbox_local_part": _text(identity_raw.get("mailbox_local_part") or identity.get("mailbox_local_part")),
                "role": _text(identity_raw.get("role") or identity.get("role")),
                "operator_inbox_target": _text(identity_raw.get("operator_inbox_target") or identity.get("operator_inbox_target") or identity_raw.get("single_user_email") or identity.get("single_user_email")),
            }
        )
    out.sort(
        key=lambda item: (
            0 if _text(item.get("mailbox_local_part")).lower() == "technicalcontact" else 1,
            0 if _text(item.get("role")).lower() == "technical_contact" else 1,
            _text(item.get("send_as_email")).lower(),
        )
    )
    return out


def preferred_sender(verified_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    for item in list(verified_profiles or []):
        if _text(item.get("mailbox_local_part")).lower() == "technicalcontact":
            return dict(item)
    return dict((verified_profiles or [{}])[0]) if verified_profiles else {}


def newsletter_domains(private_dir: Path) -> list[str]:
    domains: set[str] = set()
    tool_root = newsletter_state_root(private_dir)
    if tool_root.exists() and tool_root.is_dir():
        for path in sorted(tool_root.glob("newsletter-admin.*.json")):
            token = path.stem.removeprefix("newsletter-admin.").strip().lower()
            if token:
                domains.add(token)
    for domain, site_root in newsletter_site_roots(private_dir).items():
        client_root = site_root.parent
        if (client_root / "contacts" / f"{domain}-contact_log.json").exists():
            domains.add(domain)
    aws_root = utility_tools_dir(Path(private_dir)) / "aws-csm"
    if aws_root.exists() and aws_root.is_dir():
        for path in sorted(aws_root.glob("aws-csm.*.json")):
            payload = _read_json(path)
            profile_hint = path.stem.removeprefix("aws-csm.")
            normalized, _, _ = normalize_aws_csm_profile_payload(payload, profile_hint=profile_hint)
            identity_raw = dict(payload.get("identity") or {}) if isinstance(payload.get("identity"), dict) else {}
            verification_raw = dict(payload.get("verification") or {}) if isinstance(payload.get("verification"), dict) else {}
            provider_raw = dict(payload.get("provider") or {}) if isinstance(payload.get("provider"), dict) else {}
            identity = dict(normalized.get("identity") or {})
            domain = _text(identity_raw.get("domain") or identity.get("domain")).lower()
            if not domain:
                continue
            if _text(provider_raw.get("gmail_send_as_status") or (normalized.get("provider") or {}).get("gmail_send_as_status")).lower() == "verified" and _text(verification_raw.get("status") or (normalized.get("verification") or {}).get("status")).lower() == "verified":
                domains.add(domain)
    progeny_root = Path(private_dir) / "network" / "progeny"
    if progeny_root.exists() and progeny_root.is_dir():
        for path in sorted(progeny_root.glob("*.json")):
            payload = _read_json(path)
            refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
            policy = payload.get("email_policy") if isinstance(payload.get("email_policy"), dict) else {}
            newsletter = policy.get("newsletter") if isinstance(policy.get("newsletter"), dict) else {}
            sender_address = _text(newsletter.get("sender_address") or refs.get("newsletter_sender_address")).lower()
            ingest_address = _text(newsletter.get("ingest_address") or refs.get("newsletter_ingest_address")).lower()
            domain = ""
            if "@" in sender_address:
                domain = sender_address.split("@", 1)[1].strip().lower()
            elif "@" in ingest_address:
                domain = ingest_address.split("@", 1)[1].strip().lower()
            else:
                domain = _text(refs.get("paypal_site_domain") or payload.get("domain")).lower()
            if domain:
                domains.add(domain)
    return sorted(domains)


def newsletter_signing_secret(private_dir: Path) -> str:
    path = newsletter_secret_path(private_dir)
    if path.exists() and path.is_file():
        token = _text(path.read_text(encoding="utf-8"))
        if token:
            return token
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    return token


def newsletter_dispatch_secret(private_dir: Path) -> str:
    path = newsletter_dispatch_secret_path(private_dir)
    if path.exists() and path.is_file():
        token = _text(path.read_text(encoding="utf-8"))
        if token:
            return token
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    return token


def unsubscribe_token(secret: str, *, domain: str, email: str) -> str:
    payload = f"{_text(domain).lower()}|{_text(email).lower()}".encode("utf-8")
    digest = hmac.new(_text(secret).encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return digest


def contact_summary(contact_log: dict[str, Any]) -> dict[str, int]:
    contacts = list(contact_log.get("contacts") or [])
    subscribed_count = 0
    unsubscribed_count = 0
    for item in contacts:
        normalized = _normalize_contact(item)
        if normalized is None:
            continue
        if normalized.get("subscribed"):
            subscribed_count += 1
        else:
            unsubscribed_count += 1
    return {
        "contact_count": subscribed_count + unsubscribed_count,
        "subscribed_count": subscribed_count,
        "unsubscribed_count": unsubscribed_count,
    }


def resolve_newsletter_domain_state(private_dir: Path, domain: str) -> dict[str, Any]:
    token = _text(domain).lower()
    contact_log_path, contact_log = load_contact_log(private_dir, token)
    profile_path, profile = load_newsletter_profile(private_dir, token)
    compatibility = _compatibility_newsletter_profile(private_dir, token)
    verified = verified_sender_profiles(private_dir, token)
    selected = {}
    selected_profile_id = _text(profile.get("selected_author_profile_id") or profile.get("selected_sender_profile_id"))
    for item in verified:
        if _text(item.get("profile_id")) == selected_profile_id:
            selected = dict(item)
            break
    if not selected:
        selected = preferred_sender(verified)
    if selected:
        profile["selected_author_profile_id"] = _text(selected.get("profile_id"))
        profile["selected_author_address"] = _text(selected.get("send_as_email"))
        profile["selected_sender_profile_id"] = _text(selected.get("profile_id"))
        profile["selected_sender_address"] = _text(selected.get("send_as_email"))
    warnings: list[str] = []
    if compatibility:
        compat_sender = _text(compatibility.get("sender_address")).lower()
        compat_ingest = _text(compatibility.get("ingest_address")).lower()
        compat_mode = _text(compatibility.get("dispatch_mode"))
        selected_address = _text(profile.get("selected_sender_address") or selected.get("send_as_email")).lower()
        if compat_sender and compat_sender != _text(profile.get("sender_address")).lower():
            warnings.append(
                f"compatibility drift: progeny sender_address ({compat_sender}) does not match canonical profile ({_text(profile.get('sender_address')).lower()})"
            )
        if compat_ingest and compat_ingest != _text(profile.get("list_address")).lower():
            warnings.append(
                f"compatibility drift: progeny ingest_address ({compat_ingest}) does not match canonical profile ({_text(profile.get('list_address')).lower()})"
            )
        if compat_mode and compat_mode != _text(profile.get("dispatch_mode")):
            warnings.append(
                f"compatibility drift: progeny dispatch_mode ({compat_mode}) does not match canonical profile ({_text(profile.get('dispatch_mode'))})"
            )
        allowed_from = list(compatibility.get("allowed_from") or [])
        if selected_address and allowed_from and selected_address not in allowed_from:
            warnings.append(
                f"compatibility drift: selected sender ({selected_address}) is outside progeny allowed_from ({', '.join(allowed_from)})"
            )
    if selected_profile_id and not selected:
        warnings.append(f"canonical selected sender is not currently verified for {token}: {selected_profile_id}")
    summary = contact_summary(contact_log)
    dispatches = list(contact_log.get("dispatches") or [])
    latest_dispatch = dict(dispatches[-1]) if dispatches else {}
    contacts_preview = list(contact_log.get("contacts") or [])[:50]
    return {
        "domain": token,
        "profile_path": str(profile_path),
        "contact_log_path": str(contact_log_path),
        "profile": profile,
        "compatibility": compatibility,
        "verified_senders": verified,
        "selected_author": selected,
        "selected_sender": selected,
        "list_address": _text(profile.get("list_address")) or f"news@{token}",
        "sender_address": _text(profile.get("sender_address")) or _text(profile.get("list_address")) or f"news@{token}",
        "contacts": list(contact_log.get("contacts") or []),
        "contacts_preview": contacts_preview,
        "dispatches": dispatches,
        "latest_dispatch": latest_dispatch,
        "warnings": warnings,
        **summary,
    }
