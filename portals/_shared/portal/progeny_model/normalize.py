from __future__ import annotations

import time
from typing import Any

_LEGACY_TYPE_MAP = {
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


def normalize_member_profile_refs(payload: dict[str, Any], member_id: str) -> dict[str, str]:
    refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    member_token = _as_text(member_id)
    return {
        "paypal_profile_id": _as_text(refs.get("paypal_profile_id") or f"paypal:member:{member_token}"),
        "paypal_site_base_url": _as_text(refs.get("paypal_site_base_url")),
        "paypal_checkout_return_url": _as_text(refs.get("paypal_checkout_return_url")),
        "paypal_checkout_cancel_url": _as_text(refs.get("paypal_checkout_cancel_url")),
        "paypal_webhook_listener_url": _as_text(refs.get("paypal_webhook_listener_url")),
        "paypal_checkout_brand_name": _as_text(refs.get("paypal_checkout_brand_name")),
        "aws_profile_id": _as_text(refs.get("aws_profile_id") or f"aws:member:{member_token}"),
        "aws_emailer_list_ref": _as_text(refs.get("aws_emailer_list_ref")),
        "aws_emailer_entry_ref": _as_text(refs.get("aws_emailer_entry_ref")),
        "keycloak_realm_ref": _as_text(refs.get("keycloak_realm_ref")),
        "keycloak_client_ref": _as_text(refs.get("keycloak_client_ref")),
    }


def normalize_member_profile(member_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    member_token = _as_text(member_id)
    member_msn_id = _as_text(payload.get("member_msn_id") or payload.get("tenant_msn_id") or payload.get("msn_id"))
    display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
    contract_refs = payload.get("contract_refs") if isinstance(payload.get("contract_refs"), dict) else {}
    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}

    state = _as_text(status.get("state") or "active").lower()
    if state not in {"active", "suspended"}:
        state = "active"

    normalized = {
        "schema": "mycite.progeny.member.profile.v1",
        "member_id": member_token,
        "member_msn_id": member_msn_id,
        "display": {
            "title": _as_text(display.get("title") or f"Member {member_token}") or f"Member {member_token}",
        },
        "capabilities": {
            "paypal": bool(capabilities.get("paypal", False)),
            "aws": bool(capabilities.get("aws", False)),
        },
        "profile_refs": normalize_member_profile_refs(payload, member_token),
        "contract_refs": {
            "authorization_contract_id": _as_text(contract_refs.get("authorization_contract_id")),
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
