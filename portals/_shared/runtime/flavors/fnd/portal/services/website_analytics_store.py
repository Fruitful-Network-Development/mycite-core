from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def analytics_root(private_dir: Path) -> Path:
    return private_dir / "admin_runtime" / "analytics" / "tenants"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out.get(key) or {}, value)
            continue
        out[key] = copy.deepcopy(value)
    return out


def _first_non_empty(*values: Any) -> str:
    for value in values:
        token = _as_text(value)
        if token:
            return token
    return ""


def default_member_analytics(member_id: str, profile: dict[str, Any], hosted_payload: dict[str, Any]) -> dict[str, Any]:
    refs = profile.get("profile_refs") if isinstance(profile.get("profile_refs"), dict) else {}
    email_policy = profile.get("email_policy") if isinstance(profile.get("email_policy"), dict) else {}
    workflow = hosted_payload.get("workflow") if isinstance(hosted_payload.get("workflow"), dict) else {}
    callbacks = workflow.get("callback_mailboxes") if isinstance(workflow.get("callback_mailboxes"), list) else []
    domain = _first_non_empty(refs.get("website_domain"), refs.get("paypal_site_domain"))
    base_url = _first_non_empty(refs.get("website_base_url"), refs.get("paypal_site_base_url"))
    if domain and not base_url:
        base_url = f"https://{domain}"
    callback_email = _first_non_empty(
        refs.get("website_analytics_callback_email"),
        callbacks[0] if callbacks else "",
        (email_policy.get("operator_inbox") if isinstance(email_policy, dict) else ""),
    )

    return {
        "schema": "mycite.analytics.member.v1",
        "member_id": member_id,
        "member_msn_id": _first_non_empty(profile.get("member_msn_id"), profile.get("msn_id"), member_id),
        "title": _first_non_empty(profile.get("title"), (profile.get("display") or {}).get("title"), member_id),
        "provider": _first_non_empty(workflow.get("analytics_provider"), "nginx_hosted"),
        "status": _first_non_empty(workflow.get("default_status"), "planned"),
        "domain": domain,
        "base_url": base_url,
        "analytics_ref": _first_non_empty(refs.get("website_analytics_ref"), refs.get("website_analytics_profile_id")),
        "callback_email": callback_email,
        "metrics": {
            "page_views_7d": 0,
            "unique_visitors_7d": 0,
            "contact_events_30d": 0,
        },
        "notes": [
            "This record is sourced from member progeny refs plus hosted workflow defaults.",
        ],
    }


def load_member_analytics(private_dir: Path, member_id: str, profile: dict[str, Any], hosted_payload: dict[str, Any]) -> dict[str, Any]:
    defaults = default_member_analytics(member_id, profile, hosted_payload)
    target = analytics_root(private_dir) / f"{member_id}.json"
    if not target.exists() or not target.is_file():
        defaults["path"] = str(target)
        return defaults
    try:
        stored = _read_json(target)
    except Exception:
        defaults["path"] = str(target)
        return defaults
    merged = _deep_merge(defaults, stored)
    merged["path"] = str(target)
    return merged


def list_member_analytics(private_dir: Path, members: list[dict[str, Any]], hosted_payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in members:
        if not isinstance(item, dict):
            continue
        member_id = _first_non_empty(item.get("member_id"), item.get("tenant_id"), item.get("member_msn_id"), item.get("msn_id"))
        if not member_id:
            continue
        out.append(load_member_analytics(private_dir, member_id, item, hosted_payload))
    out.sort(key=lambda item: (_as_text(item.get("title")), _as_text(item.get("member_id"))))
    return out
