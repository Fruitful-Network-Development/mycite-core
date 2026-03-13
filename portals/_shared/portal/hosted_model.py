from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .runtime_paths import hosted_path, hosted_read_paths

SUPPORTED_PROGENY_TYPES = ("admin", "member", "user")
DEFAULT_HOSTED_SCHEMA = "mycite.network.hosted.v2"
DEFAULT_TABS = [
    {"id": "stream", "label": "Stream", "description": "Subscription updates and hosted activity."},
    {"id": "classwork", "label": "Classwork", "description": "Subject congregation tasks and assignments."},
    {"id": "people", "label": "People", "description": "Broadcaster directory for MSN/resource lookup."},
    {"id": "workflow", "label": "Workflow", "description": "Hosted website analytics and operations."},
]


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out.get(key) or {}, value)
            continue
        out[key] = copy.deepcopy(value)
    return out


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _default_email_policy() -> dict[str, Any]:
    return {
        "mode": "forwarder_no_smtp",
        "smtp_enabled": False,
        "forwarder_address": "",
        "operator_inbox": "",
        "poc_address": "",
        "inbound_aliases": [],
        "reply": {
            "allowed_from": [],
            "send_as": [],
            "send_as_policy": "original_contacted_alias",
        },
        "newsletter": {
            "allowed_from": [],
            "ingest_address": "",
            "sender_address": "",
            "dispatch_mode": "aws_internal",
        },
    }


def _default_profile_refs(progeny_type: str) -> dict[str, Any]:
    base = {
        "contact_collection_ref": "",
        "aws_profile_id": "",
        "aws_emailer_list_ref": "",
        "aws_emailer_entry_ref": "",
        "website_domain": "",
        "website_base_url": "",
        "website_analytics_profile_id": "",
        "website_analytics_ref": "",
        "website_analytics_callback_email": "",
        "email_transport_mode": "forwarder_no_smtp",
        "email_forwarder_address": "",
        "email_operator_inbox": "",
        "email_poc_address": "",
        "email_inbound_aliases_csv": "",
        "email_reply_allowed_from_csv": "",
        "email_reply_send_as_csv": "",
        "email_reply_send_as_policy": "original_contacted_alias",
        "newsletter_ingest_address": "",
        "newsletter_sender_address": "",
        "newsletter_allowed_from_csv": "",
        "newsletter_dispatch_mode": "aws_internal",
    }
    if progeny_type == "member":
        base.update(
            {
                "paypal_profile_id": "",
                "paypal_site_domain": "",
                "paypal_site_base_url": "",
                "paypal_checkout_return_url": "",
                "paypal_checkout_cancel_url": "",
                "paypal_webhook_listener_url": "",
                "paypal_checkout_brand_name": "",
            }
        )
    return base


def default_progeny_template(progeny_type: str) -> dict[str, Any]:
    token = _as_text(progeny_type).lower()
    if token not in SUPPORTED_PROGENY_TYPES:
        raise ValueError(f"Unsupported progeny_type: {progeny_type}")

    capabilities = {
        "paypal": token == "member",
        "aws": True,
        "analytics": True,
    }
    config: dict[str, Any] = {
        "contacts": "",
        "status": True,
        "email_map": {
            "inbox_inbound": {},
            "proxy_outbound": {},
        },
        "website": {
            "domain": "",
            "base_url": "",
            "analytics_callback_email": "",
        },
    }
    if token == "member":
        config["paypal"] = {
            "website_domain": "",
            "site_base_url": "",
            "webhook_listener_url": "",
        }
    if token == "admin":
        config["roles"] = ["admin"]
        config["permissions"] = ["*"]
    if token == "user":
        config["preferences"] = {"notifications": True}

    return {
        "profile_type": token,
        "msn_id": "",
        "title": "",
        "contract": None,
        "template_version": "2.0.0",
        "capabilities": capabilities,
        "profile_refs": _default_profile_refs(token),
        "email_policy": _default_email_policy(),
        "hosted_interface": {
            "layout": "subject_congregation",
            "default_tab": "stream",
            "tabs": [item["id"] for item in DEFAULT_TABS],
        },
        "config": config,
    }


def default_hosted_payload(hero_title: str = "Member Orientation") -> dict[str, Any]:
    tabs = copy.deepcopy(DEFAULT_TABS)
    return {
        "schema": DEFAULT_HOSTED_SCHEMA,
        "type": "subject_congregation",
        "type_values": {
            "default_hosted": [{tab["id"]: f"subject_congregation/{tab['id']}.json"} for tab in tabs],
            "channels": ["contracts.json", "request_log.json"],
            "members": ["members.json"],
            "orientation": {
                "style": "google_classroom_reference",
                "hero_title": hero_title,
            },
        },
        "subject_congregation": {
            "style": "google_classroom_reference",
            "hero_title": hero_title,
            "tabs": tabs,
            "calendar_enabled": False,
        },
        "broadcaster": {
            "schema": "mycite.network.broadcaster.v1",
            "enabled": True,
            "stream": {
                "title": "Subscriptions",
                "description": "Updates for followed subscriptions and hosted surfaces.",
            },
            "people": {
                "title": "People",
                "description": "Search portals and resources by msn_id.",
                "search_key": "msn_id",
            },
            "workflow": {
                "title": "Workflow",
                "description": "Website analytics for hosted domains.",
            },
            "resource_types": ["portal", "resource"],
        },
        "progeny": {
            "storage": {
                "mode": "single_directory",
                "directory": "private/network/progeny",
                "filename_pattern": "msn-<provider_msn_id>.<progeny_type>-<alias_associated_msn_id>.json",
                "legacy_read_dirs": [
                    "private/network/progeny/admin_progeny",
                    "private/network/progeny/member_progeny",
                    "private/network/progeny/user_progeny",
                    "private/progeny/member",
                    "private/progeny/tenant",
                ],
            },
            "templates": {token: default_progeny_template(token) for token in SUPPORTED_PROGENY_TYPES},
        },
        "aws": {
            "email_transport_mode": "forwarder_only",
            "callback_mailboxes": {
                "fnd_callback_addresses": [],
                "member_callback_addresses": [],
            },
        },
        "workflow": {
            "analytics_provider": "nginx_hosted",
            "domain_ref_fields": ["website_domain", "paypal_site_domain"],
            "callback_mailboxes": [],
            "metrics": ["page_views_7d", "unique_visitors_7d", "contact_events_30d"],
        },
    }


def normalize_hosted_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = copy.deepcopy(payload or {})
    hero_title = ""

    type_values = raw.get("type_values") if isinstance(raw.get("type_values"), dict) else {}
    orientation = type_values.get("orientation") if isinstance(type_values.get("orientation"), dict) else {}
    subject = raw.get("subject_congregation") if isinstance(raw.get("subject_congregation"), dict) else {}
    hero_title = (
        _as_text(subject.get("hero_title"))
        or _as_text(orientation.get("hero_title"))
        or "Member Orientation"
    )

    normalized = default_hosted_payload(hero_title)
    normalized = _deep_merge(normalized, raw)

    if not isinstance(normalized.get("type_values"), dict):
        normalized["type_values"] = {}
    if not isinstance(normalized.get("subject_congregation"), dict):
        normalized["subject_congregation"] = {}
    if not isinstance(normalized.get("broadcaster"), dict):
        normalized["broadcaster"] = {}
    if not isinstance(normalized.get("progeny"), dict):
        normalized["progeny"] = {}
    if not isinstance(normalized.get("aws"), dict):
        normalized["aws"] = {}
    if not isinstance(normalized.get("workflow"), dict):
        normalized["workflow"] = {}

    subject_cfg = _deep_merge(default_hosted_payload(hero_title)["subject_congregation"], normalized.get("subject_congregation") or {})
    tabs = subject_cfg.get("tabs")
    if not isinstance(tabs, list) or not tabs:
        subject_cfg["tabs"] = copy.deepcopy(DEFAULT_TABS)
    else:
        normalized_tabs: list[dict[str, Any]] = []
        for raw_tab in tabs:
            if isinstance(raw_tab, str):
                normalized_tabs.append({"id": _as_text(raw_tab).lower(), "label": _as_text(raw_tab).title()})
            elif isinstance(raw_tab, dict):
                tab_id = _as_text(raw_tab.get("id")).lower()
                if not tab_id:
                    continue
                tab = dict(raw_tab)
                tab["id"] = tab_id
                tab["label"] = _as_text(tab.get("label") or tab_id.title()) or tab_id.title()
                normalized_tabs.append(tab)
        subject_cfg["tabs"] = normalized_tabs or copy.deepcopy(DEFAULT_TABS)
    subject_cfg["calendar_enabled"] = bool(subject_cfg.get("calendar_enabled", False))
    normalized["subject_congregation"] = subject_cfg

    type_values_cfg = dict(normalized.get("type_values") or {})
    default_hosted = type_values_cfg.get("default_hosted")
    if not isinstance(default_hosted, list) or not default_hosted:
        type_values_cfg["default_hosted"] = [
            {tab["id"]: f"subject_congregation/{tab['id']}.json"} for tab in subject_cfg.get("tabs") or []
        ]
    type_values_cfg.setdefault("orientation", {})
    if isinstance(type_values_cfg.get("orientation"), dict):
        type_values_cfg["orientation"].setdefault("style", _as_text(subject_cfg.get("style")) or "google_classroom_reference")
        type_values_cfg["orientation"].setdefault("hero_title", hero_title)
    normalized["type_values"] = type_values_cfg

    broadcaster_cfg = _deep_merge(default_hosted_payload(hero_title)["broadcaster"], normalized.get("broadcaster") or {})
    normalized["broadcaster"] = broadcaster_cfg

    progeny_cfg = _deep_merge(default_hosted_payload(hero_title)["progeny"], normalized.get("progeny") or {})
    templates = progeny_cfg.get("templates") if isinstance(progeny_cfg.get("templates"), dict) else {}
    next_templates: dict[str, Any] = {}
    for progeny_type in SUPPORTED_PROGENY_TYPES:
        seed = default_progeny_template(progeny_type)
        overlay = templates.get(progeny_type) if isinstance(templates.get(progeny_type), dict) else {}
        next_templates[progeny_type] = _deep_merge(seed, overlay)
    progeny_cfg["templates"] = next_templates
    normalized["progeny"] = progeny_cfg

    workflow_cfg = _deep_merge(default_hosted_payload(hero_title)["workflow"], normalized.get("workflow") or {})
    if not isinstance(workflow_cfg.get("domain_ref_fields"), list):
        workflow_cfg["domain_ref_fields"] = ["website_domain", "paypal_site_domain"]
    normalized["workflow"] = workflow_cfg

    aws_cfg = _deep_merge(default_hosted_payload(hero_title)["aws"], normalized.get("aws") or {})
    callback_mailboxes = aws_cfg.get("callback_mailboxes") if isinstance(aws_cfg.get("callback_mailboxes"), dict) else {}
    callback_mailboxes.setdefault("fnd_callback_addresses", [])
    callback_mailboxes.setdefault("member_callback_addresses", [])
    aws_cfg["callback_mailboxes"] = callback_mailboxes
    normalized["aws"] = aws_cfg

    normalized["schema"] = _as_text(normalized.get("schema") or DEFAULT_HOSTED_SCHEMA)
    type_token = _as_text(normalized.get("type") or "subject_congregation").lower()
    if type_token in {"classroom_workbench", "classroom_orientation"}:
        type_token = "subject_congregation"
    normalized["type"] = type_token or "subject_congregation"
    normalized["raw"] = raw
    return normalized


def get_progeny_template(payload: dict[str, Any] | None, progeny_type: str) -> dict[str, Any]:
    token = _as_text(progeny_type).lower()
    if token not in SUPPORTED_PROGENY_TYPES:
        raise ValueError(f"Unsupported progeny_type: {progeny_type}")
    normalized = normalize_hosted_payload(payload or {})
    progeny = normalized.get("progeny") if isinstance(normalized.get("progeny"), dict) else {}
    templates = progeny.get("templates") if isinstance(progeny.get("templates"), dict) else {}
    template = templates.get(token) if isinstance(templates.get(token), dict) else {}
    return _deep_merge(default_progeny_template(token), template)


def set_progeny_template(payload: dict[str, Any] | None, progeny_type: str, template: dict[str, Any]) -> dict[str, Any]:
    token = _as_text(progeny_type).lower()
    if token not in SUPPORTED_PROGENY_TYPES:
        raise ValueError(f"Unsupported progeny_type: {progeny_type}")
    if not isinstance(template, dict):
        raise ValueError("Template payload must be an object")
    normalized = normalize_hosted_payload(payload or {})
    normalized.setdefault("progeny", {})
    progeny = normalized.get("progeny") if isinstance(normalized.get("progeny"), dict) else {}
    templates = progeny.get("templates") if isinstance(progeny.get("templates"), dict) else {}
    templates[token] = _deep_merge(default_progeny_template(token), template)
    progeny["templates"] = templates
    normalized["progeny"] = progeny
    normalized.pop("raw", None)
    return normalized


def read_hosted_payload(private_dir: Path) -> dict[str, Any]:
    for path in hosted_read_paths(private_dir):
        if not path.exists() or not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        normalized = normalize_hosted_payload(payload)
        normalized["path"] = str(path)
        return normalized
    normalized = normalize_hosted_payload({})
    normalized["path"] = str(hosted_path(private_dir))
    return normalized


def write_hosted_payload(private_dir: Path, payload: dict[str, Any]) -> Path:
    target = hosted_path(private_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = copy.deepcopy(payload)
    clean.pop("raw", None)
    clean.pop("path", None)
    target.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    return target
