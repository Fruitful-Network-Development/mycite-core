from __future__ import annotations

from pathlib import Path
from typing import Any


def _deep_merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge_dict(dict(out[key]), value)
        else:
            out[key] = value
    return out


def _normalize_org_config_filename(value: str, *, fallback: str) -> str:
    token = str(value or "").strip()
    if not token:
        token = fallback
    token = Path(token).name
    if "." not in token:
        token = f"{token}.json"
    return token.lower()


def organization_config_filename(active_cfg: dict[str, Any], *, is_tff_portal: bool) -> str:
    portal_profile = active_cfg.get("portal_profile") if isinstance(active_cfg.get("portal_profile"), dict) else {}
    org_cfg = active_cfg.get("organization_config") if isinstance(active_cfg.get("organization_config"), dict) else {}
    org_cfg_alt = (
        active_cfg.get("organization_configuration")
        if isinstance(active_cfg.get("organization_configuration"), dict)
        else {}
    )
    org_cfg_typo = (
        active_cfg.get("orangization_configuration")
        if isinstance(active_cfg.get("orangization_configuration"), dict)
        else {}
    )
    fallback = "subject_congregation.json" if is_tff_portal else "discovery_engine.json"
    loose_org_cfg_value = (
        active_cfg.get("organization_configuration")
        if isinstance(active_cfg.get("organization_configuration"), str)
        else active_cfg.get("orangization_configuration")
        if isinstance(active_cfg.get("orangization_configuration"), str)
        else ""
    )
    candidates = [
        portal_profile.get("organization_config_file"),
        portal_profile.get("profile_kind"),
        org_cfg.get("file_name"),
        org_cfg.get("config_file"),
        org_cfg.get("legal_entity_config_file"),
        org_cfg.get("legal_entity_type"),
        org_cfg.get("type"),
        org_cfg_alt.get("file_name"),
        org_cfg_alt.get("config_file"),
        org_cfg_alt.get("legal_entity_config_file"),
        org_cfg_alt.get("legal_entity_type"),
        org_cfg_alt.get("type"),
        org_cfg_typo.get("file_name"),
        org_cfg_typo.get("config_file"),
        org_cfg_typo.get("legal_entity_config_file"),
        org_cfg_typo.get("legal_entity_type"),
        org_cfg_typo.get("type"),
        loose_org_cfg_value,
        active_cfg.get("organization_config_file"),
        active_cfg.get("legal_entity_config_file"),
        active_cfg.get("legal_entity_type"),
    ]
    for candidate in candidates:
        token = str(candidate or "").strip()
        if token:
            return _normalize_org_config_filename(token, fallback=fallback)
    return _normalize_org_config_filename("", fallback=fallback)


def collect_org_layers(active_cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    defaults: dict[str, Any] = {}
    added: dict[str, Any] = {}

    portal_behavior = active_cfg.get("portal_behavior") if isinstance(active_cfg.get("portal_behavior"), dict) else {}
    pb_defaults = portal_behavior.get("defaults") if isinstance(portal_behavior.get("defaults"), dict) else {}
    pb_overrides = portal_behavior.get("overrides") if isinstance(portal_behavior.get("overrides"), dict) else {}
    if pb_defaults:
        defaults = _deep_merge_dict(defaults, pb_defaults)
    if pb_overrides:
        added = _deep_merge_dict(added, pb_overrides)

    org_cfg = active_cfg.get("organization_config") if isinstance(active_cfg.get("organization_config"), dict) else {}
    org_cfg_alt = (
        active_cfg.get("organization_configuration")
        if isinstance(active_cfg.get("organization_configuration"), dict)
        else {}
    )
    org_cfg_typo = (
        active_cfg.get("orangization_configuration")
        if isinstance(active_cfg.get("orangization_configuration"), dict)
        else {}
    )
    containers = [active_cfg, org_cfg, org_cfg_alt, org_cfg_typo]
    for container in containers:
        for key in ("default_values", "defaults"):
            section = container.get(key)
            if isinstance(section, dict):
                defaults = _deep_merge_dict(defaults, section)
        for key in ("added_values", "added", "overrides"):
            section = container.get(key)
            if isinstance(section, dict):
                added = _deep_merge_dict(added, section)

    for container in containers:
        for section_key in ("stream_config", "calendar_config", "people_config", "workflow_config", "legal_entity_defaults"):
            section = container.get(section_key)
            if isinstance(section, dict):
                existing = added.get(section_key) if isinstance(added.get(section_key), dict) else {}
                added[section_key] = _deep_merge_dict(existing, section)
    return defaults, added


def generic_legal_entity_defaults(file_name: str) -> dict[str, Any]:
    legal_type = Path(file_name).stem.lower().strip() or "subject_congregation"
    title = legal_type.replace("_", " ").replace("-", " ").title()
    return {
        "schema": "mycite.legal_entity_type.v1",
        "type": legal_type,
        "title": title,
        "role_groups": {"admins": [], "members": [], "users": []},
    }


def default_portal_behavior(
    *,
    active_cfg: dict[str, Any],
    is_tff_portal: bool,
    legal_entity_profile_defaults: dict[str, dict[str, Any]],
    default_feed_types: set[str],
    default_calendar_types: set[str],
    default_profile_source_priority: list[str],
) -> dict[str, Any]:
    portal_profile = active_cfg.get("portal_profile") if isinstance(active_cfg.get("portal_profile"), dict) else {}
    org_config_file = organization_config_filename(active_cfg, is_tff_portal=is_tff_portal)
    legal_type = (
        str(portal_profile.get("profile_kind") or "").strip().lower()
        or Path(org_config_file).stem.lower().strip()
        or "subject_congregation"
    )
    legal_defaults = legal_entity_profile_defaults.get(org_config_file) or generic_legal_entity_defaults(org_config_file)

    return {
        "organization_config_file": org_config_file,
        "legal_entity_type": legal_type,
        "stream_config": {
            "schema": "mycite.portal.stream_config.v1",
            "allowed_post_types": sorted(default_feed_types),
            "newest_first": True,
        },
        "calendar_config": {
            "schema": "mycite.portal.calendar_config.v1",
            "allowed_event_types": sorted(default_calendar_types),
            "exclude_request_log_types": True,
        },
        "people_config": {
            "schema": "mycite.portal.people_config.v1",
            "profile_source_priority": list(default_profile_source_priority),
        },
        "workflow_config": {
            "schema": "mycite.portal.workflow_config.v1",
            "enabled": bool(is_tff_portal),
            "legal_entity_type": legal_type,
            "sections": [
                {"id": "operations", "title": "Operations", "description": "Core operating workflow checkpoints."},
                {"id": "farm_fields", "title": "Farm Fields", "description": "Field inventories and seasonal status references."},
                {"id": "compliance", "title": "Compliance", "description": "Compliance and policy milestones."},
            ],
            "anthology_refs": {"farm_fields": "", "workflow_state": ""},
        },
        "legal_entity_defaults": dict(legal_defaults),
    }


def build_portal_behavior_config(
    *,
    active_cfg: dict[str, Any],
    is_tff_portal: bool,
    legal_entity_profile_defaults: dict[str, dict[str, Any]],
    default_feed_types: set[str],
    default_calendar_types: set[str],
    default_profile_source_priority: list[str],
) -> dict[str, Any]:
    portal_profile = active_cfg.get("portal_profile") if isinstance(active_cfg.get("portal_profile"), dict) else {}
    base = default_portal_behavior(
        active_cfg=active_cfg,
        is_tff_portal=is_tff_portal,
        legal_entity_profile_defaults=legal_entity_profile_defaults,
        default_feed_types=default_feed_types,
        default_calendar_types=default_calendar_types,
        default_profile_source_priority=default_profile_source_priority,
    )
    defaults, added = collect_org_layers(active_cfg)
    merged = _deep_merge_dict(base, defaults)
    merged = _deep_merge_dict(merged, added)

    org_config_file = organization_config_filename(active_cfg, is_tff_portal=is_tff_portal)
    legal_type = (
        str(portal_profile.get("profile_kind") or "").strip().lower()
        or Path(org_config_file).stem.lower().strip()
        or "subject_congregation"
    )
    merged["organization_config_file"] = org_config_file
    merged["legal_entity_type"] = legal_type

    workflow_cfg = merged.get("workflow_config") if isinstance(merged.get("workflow_config"), dict) else {}
    workflow_cfg.setdefault("legal_entity_type", legal_type)
    merged["workflow_config"] = workflow_cfg

    legal_defaults = merged.get("legal_entity_defaults") if isinstance(merged.get("legal_entity_defaults"), dict) else {}
    legal_defaults.setdefault("schema", "mycite.legal_entity_type.v1")
    legal_defaults.setdefault("type", legal_type)
    legal_defaults.setdefault("title", legal_type.replace("_", " ").replace("-", " ").title())
    if not isinstance(legal_defaults.get("role_groups"), dict):
        legal_defaults["role_groups"] = {"admins": [], "members": [], "users": []}
    merged["legal_entity_defaults"] = legal_defaults
    return merged
