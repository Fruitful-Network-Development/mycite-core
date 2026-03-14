from __future__ import annotations

import time
from urllib.parse import urlparse
from typing import Any

_LEGACY_TYPE_MAP = {
    "constituent_farm": "member",
    "poc": "admin",
    "tenant": "member",
    "board_member": "member",
}


def canonical_progeny_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return "unknown"
    return _LEGACY_TYPE_MAP.get(token, token)


def is_legacy_progeny_type(value: str) -> bool:
    token = str(value or "").strip().lower()
    return token in _LEGACY_TYPE_MAP


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = _as_text(value).lower()
    if token in {"1", "true", "yes", "on", "enabled"}:
        return True
    if token in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _split_tokens(value: object) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            token = _as_text(item)
            if token:
                out.append(token)
        return out
    token = _as_text(value)
    if not token:
        return []
    out: list[str] = []
    for piece in token.replace(";", ",").replace("\n", ",").split(","):
        item = _as_text(piece)
        if item:
            out.append(item)
    return out


def _unique_tokens(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        token = _as_text(item).lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _list_to_csv(values: list[str]) -> str:
    return ",".join(_unique_tokens(values))


def _extract_host(token: str) -> str:
    raw = _as_text(token)
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return _as_text(parsed.netloc).lower()
    return raw.lower()


def _normalize_email_policy(payload: dict[str, Any]) -> dict[str, Any]:
    policy = payload.get("email_policy") if isinstance(payload.get("email_policy"), dict) else {}
    refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    email_map = config.get("email_map") if isinstance(config.get("email_map"), dict) else {}
    inbound_map = email_map.get("inbox_inbound") if isinstance(email_map.get("inbox_inbound"), dict) else {}
    outbound_map = email_map.get("proxy_outbound") if isinstance(email_map.get("proxy_outbound"), dict) else {}

    proxy_candidates: dict[str, int] = {}
    for src, dests in inbound_map.items():
        src_email = _as_text(src).lower()
        for dest in _split_tokens(dests):
            dest_email = _as_text(dest).lower()
            if "@" not in src_email or "@" not in dest_email:
                continue
            if src_email == dest_email:
                continue
            proxy_candidates[dest_email] = proxy_candidates.get(dest_email, 0) + 1
    legacy_forwarder = ""
    if proxy_candidates:
        legacy_forwarder = max(proxy_candidates.items(), key=lambda item: item[1])[0]
    elif inbound_map:
        first_key = next(iter(inbound_map.keys()), "")
        first_values = _split_tokens(inbound_map.get(first_key))
        if first_values:
            legacy_forwarder = _as_text(first_values[0]).lower()

    legacy_inbound_aliases: list[str] = []
    if legacy_forwarder:
        for src, dests in inbound_map.items():
            src_email = _as_text(src).lower()
            if src_email and src_email != legacy_forwarder:
                normalized_dests = [_as_text(item).lower() for item in _split_tokens(dests)]
                if legacy_forwarder in normalized_dests:
                    legacy_inbound_aliases.append(src_email)

    legacy_operator_inbox = ""
    if legacy_forwarder:
        forward_to = _split_tokens(inbound_map.get(legacy_forwarder))
        if forward_to:
            legacy_operator_inbox = _as_text(forward_to[0]).lower()

    legacy_reply_send_as = _split_tokens(outbound_map.get(legacy_forwarder)) if legacy_forwarder else []
    legacy_reply_send_as = [_as_text(item).lower() for item in legacy_reply_send_as if _as_text(item)]

    legacy_news_ingest = ""
    if legacy_operator_inbox:
        operator_routes = [_as_text(item).lower() for item in _split_tokens(outbound_map.get(legacy_operator_inbox))]
        if operator_routes:
            hermes = [item for item in operator_routes if "hermes@" in item]
            legacy_news_ingest = hermes[0] if hermes else operator_routes[0]

    legacy_news_sender = ""
    lambda_routes = [_as_text(item).lower() for item in _split_tokens(outbound_map.get("lambda"))]
    if lambda_routes:
        legacy_news_sender = lambda_routes[0]

    poc_default = ""
    for candidate in legacy_inbound_aliases:
        if "mark@" in candidate:
            poc_default = candidate
            break
    if not poc_default and legacy_inbound_aliases:
        poc_default = legacy_inbound_aliases[0]

    mode = _as_text(
        policy.get("mode")
        or refs.get("email_transport_mode")
        or ("forwarder_no_smtp" if inbound_map or outbound_map else "")
    ).lower()
    if not mode:
        mode = "forwarder_no_smtp"

    forwarder_address = _as_text(
        policy.get("forwarder_address")
        or refs.get("email_forwarder_address")
        or legacy_forwarder
    ).lower()
    operator_inbox = _as_text(
        policy.get("operator_inbox")
        or refs.get("email_operator_inbox")
        or legacy_operator_inbox
    ).lower()
    poc_address = _as_text(
        policy.get("poc_address")
        or refs.get("email_poc_address")
        or poc_default
    ).lower()

    inbound_aliases = _unique_tokens(
        _split_tokens(policy.get("inbound_aliases"))
        + _split_tokens(refs.get("email_inbound_aliases_csv"))
        + legacy_inbound_aliases
    )

    reply = policy.get("reply") if isinstance(policy.get("reply"), dict) else {}
    reply_allowed_from = _unique_tokens(
        _split_tokens(reply.get("allowed_from"))
        + _split_tokens(refs.get("email_reply_allowed_from_csv"))
        + ([poc_address] if poc_address else [])
    )
    reply_send_as = _unique_tokens(
        _split_tokens(reply.get("send_as"))
        + _split_tokens(refs.get("email_reply_send_as_csv"))
        + legacy_reply_send_as
    )
    reply_send_as_policy = _as_text(
        reply.get("send_as_policy")
        or refs.get("email_reply_send_as_policy")
        or "original_contacted_alias"
    ).lower()

    newsletter = policy.get("newsletter") if isinstance(policy.get("newsletter"), dict) else {}
    newsletter_allowed_from = _unique_tokens(
        _split_tokens(newsletter.get("allowed_from"))
        + _split_tokens(refs.get("newsletter_allowed_from_csv"))
        + ([poc_address] if poc_address else [])
    )
    newsletter_ingest_address = _as_text(
        newsletter.get("ingest_address")
        or refs.get("newsletter_ingest_address")
        or legacy_news_ingest
    ).lower()
    newsletter_sender_address = _as_text(
        newsletter.get("sender_address")
        or refs.get("newsletter_sender_address")
        or legacy_news_sender
    ).lower()
    newsletter_dispatch_mode = _as_text(
        newsletter.get("dispatch_mode")
        or refs.get("newsletter_dispatch_mode")
        or "aws_internal"
    ).lower()

    smtp_enabled = _as_bool(policy.get("smtp_enabled"), False)
    if mode == "forwarder_no_smtp":
        smtp_enabled = False

    return {
        "mode": mode,
        "smtp_enabled": smtp_enabled,
        "forwarder_address": forwarder_address,
        "operator_inbox": operator_inbox,
        "poc_address": poc_address,
        "inbound_aliases": inbound_aliases,
        "reply": {
            "allowed_from": reply_allowed_from,
            "send_as": reply_send_as,
            "send_as_policy": reply_send_as_policy or "original_contacted_alias",
        },
        "newsletter": {
            "allowed_from": newsletter_allowed_from,
            "ingest_address": newsletter_ingest_address,
            "sender_address": newsletter_sender_address,
            "dispatch_mode": newsletter_dispatch_mode or "aws_internal",
        },
    }


def normalize_member_profile_refs(
    payload: dict[str, Any],
    member_id: str,
    email_policy: dict[str, Any] | None = None,
) -> dict[str, str]:
    refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    policy = email_policy if isinstance(email_policy, dict) else _normalize_email_policy(payload)
    member_token = _as_text(member_id)
    site_base_url = _as_text(refs.get("paypal_site_base_url"))
    site_domain = _extract_host(_as_text(refs.get("paypal_site_domain")))
    if not site_domain and site_base_url:
        site_domain = _extract_host(site_base_url)
    if site_domain and not site_base_url:
        site_base_url = f"https://{site_domain}"

    website_base_url = _as_text(refs.get("website_base_url"))
    website_domain = _extract_host(_as_text(refs.get("website_domain")))
    if not website_domain and website_base_url:
        website_domain = _extract_host(website_base_url)
    if not website_domain and site_domain:
        website_domain = site_domain
    if not website_base_url and site_base_url:
        website_base_url = site_base_url
    if website_domain and not website_base_url:
        website_base_url = f"https://{website_domain}"

    out: dict[str, str] = {
        "contact_collection_ref": _as_text(refs.get("contact_collection_ref")),
        "paypal_profile_id": _as_text(refs.get("paypal_profile_id") or f"paypal:member:{member_token}"),
        "paypal_site_domain": site_domain,
        "paypal_site_base_url": site_base_url,
        "paypal_checkout_return_url": _as_text(refs.get("paypal_checkout_return_url")),
        "paypal_checkout_cancel_url": _as_text(refs.get("paypal_checkout_cancel_url")),
        "paypal_webhook_listener_url": _as_text(refs.get("paypal_webhook_listener_url")),
        "paypal_checkout_brand_name": _as_text(refs.get("paypal_checkout_brand_name")),
        "aws_profile_id": _as_text(refs.get("aws_profile_id") or f"aws:member:{member_token}"),
        "aws_emailer_list_ref": _as_text(refs.get("aws_emailer_list_ref")),
        "aws_emailer_entry_ref": _as_text(refs.get("aws_emailer_entry_ref")),
        "website_domain": website_domain,
        "website_base_url": website_base_url,
        "website_analytics_profile_id": _as_text(refs.get("website_analytics_profile_id") or f"analytics:member:{member_token}"),
        "website_analytics_ref": _as_text(refs.get("website_analytics_ref")),
        "website_analytics_callback_email": _as_text(refs.get("website_analytics_callback_email")),
        "keycloak_realm_ref": _as_text(refs.get("keycloak_realm_ref")),
        "keycloak_client_ref": _as_text(refs.get("keycloak_client_ref")),
        "email_transport_mode": _as_text(policy.get("mode") or "forwarder_no_smtp"),
        "email_forwarder_address": _as_text(policy.get("forwarder_address")),
        "email_operator_inbox": _as_text(policy.get("operator_inbox")),
        "email_poc_address": _as_text(policy.get("poc_address")),
        "email_inbound_aliases_csv": _list_to_csv(list(policy.get("inbound_aliases") or [])),
        "email_reply_allowed_from_csv": _list_to_csv(list((policy.get("reply") or {}).get("allowed_from") or [])),
        "email_reply_send_as_csv": _list_to_csv(list((policy.get("reply") or {}).get("send_as") or [])),
        "email_reply_send_as_policy": _as_text((policy.get("reply") or {}).get("send_as_policy")),
        "newsletter_ingest_address": _as_text((policy.get("newsletter") or {}).get("ingest_address")),
        "newsletter_sender_address": _as_text((policy.get("newsletter") or {}).get("sender_address")),
        "newsletter_allowed_from_csv": _list_to_csv(list((policy.get("newsletter") or {}).get("allowed_from") or [])),
        "newsletter_dispatch_mode": _as_text((policy.get("newsletter") or {}).get("dispatch_mode")),
    }
    for key, value in refs.items():
        token_key = _as_text(key)
        if not token_key or token_key in out:
            continue
        if isinstance(value, list):
            token = _list_to_csv([_as_text(item) for item in value])
        else:
            token = _as_text(value)
        if token:
            out[token_key] = token
    return out


def normalize_member_profile(member_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    member_token = _as_text(member_id)
    member_msn_id = _as_text(payload.get("member_msn_id") or payload.get("tenant_msn_id") or payload.get("msn_id"))
    display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
    contract_refs = payload.get("contract_refs") if isinstance(payload.get("contract_refs"), dict) else {}
    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
    legacy_contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    raw_refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    raw_config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    email_policy = _normalize_email_policy(payload)

    state = _as_text(status.get("state") or "active").lower()
    if not _as_text(status.get("state")):
        config_status = raw_config.get("status")
        if isinstance(config_status, bool):
            state = "active" if config_status else "suspended"
    if state not in {"active", "suspended"}:
        state = "active"

    paypal_inferred = any(
        _as_text(raw_refs.get(key))
        for key in (
            "paypal_profile_id",
            "paypal_site_domain",
            "paypal_site_base_url",
            "paypal_checkout_return_url",
            "paypal_checkout_cancel_url",
            "paypal_webhook_listener_url",
        )
    )
    if not paypal_inferred:
        legacy_paypal = raw_config.get("paypal") if isinstance(raw_config.get("paypal"), dict) else {}
        paypal_inferred = bool(
            _as_text(legacy_paypal.get("site_base_url"))
            or _as_text(legacy_paypal.get("website_domain"))
            or _as_text(legacy_paypal.get("paypal_user_id"))
            or _as_text(legacy_paypal.get("paypal_webhook"))
        )

    aws_inferred = any(
        _as_text(raw_refs.get(key))
        for key in (
            "aws_profile_id",
            "aws_emailer_list_ref",
            "aws_emailer_entry_ref",
        )
    )
    if not aws_inferred:
        email_map = raw_config.get("email_map") if isinstance(raw_config.get("email_map"), dict) else {}
        aws_inferred = bool(email_map) or bool(_as_text(raw_refs.get("contact_collection_ref")))

    analytics_inferred = any(
        _as_text(raw_refs.get(key))
        for key in (
            "website_domain",
            "website_base_url",
            "website_analytics_profile_id",
            "website_analytics_ref",
            "website_analytics_callback_email",
            "paypal_site_domain",
            "paypal_site_base_url",
        )
    )

    paypal_enabled = _as_bool(capabilities.get("paypal"), paypal_inferred)
    aws_enabled = _as_bool(capabilities.get("aws"), aws_inferred)
    analytics_enabled = _as_bool(capabilities.get("analytics"), analytics_inferred or paypal_inferred)

    title = _as_text(display.get("title") or payload.get("title") or f"Member {member_token}") or f"Member {member_token}"
    authorization_contract_id = _as_text(
        contract_refs.get("authorization_contract_id") or legacy_contract.get("contract_id")
    )

    normalized = {
        "schema": "mycite.progeny.member.profile.v1",
        "profile_type": "member",
        "template_version": _as_text(payload.get("template_version") or "1.0.0"),
        "member_id": member_token,
        "member_msn_id": member_msn_id,
        "title": title,
        "display": {
            "title": title,
        },
        "capabilities": {
            "paypal": paypal_enabled,
            "aws": aws_enabled,
            "analytics": analytics_enabled,
        },
        "profile_refs": normalize_member_profile_refs(payload, member_token, email_policy),
        "email_policy": email_policy,
        "contract_refs": {
            "authorization_contract_id": authorization_contract_id,
            "service_agreement_ref": _as_text(contract_refs.get("service_agreement_ref")),
        },
        "status": {
            "state": state,
            "updated_unix_ms": int(status.get("updated_unix_ms") or int(time.time() * 1000)),
        },
        "legacy": {
            "tenant_id": member_token,
            "tenant_msn_id": member_msn_id,
            "schema": "mycite.progeny.tenant.profile.v1",
        },
    }
    return normalized


def normalize_member_record(payload: dict[str, Any], fallback_type: str = "") -> dict[str, Any]:
    record = dict(payload or {})
    raw_type = _as_text(record.get("progeny_type") or record.get("role") or fallback_type)
    record["progeny_type"] = canonical_progeny_type(raw_type)
    if is_legacy_progeny_type(raw_type):
        record.setdefault("legacy", {})
        if isinstance(record["legacy"], dict):
            record["legacy"]["source_type"] = raw_type.lower()
    return record
