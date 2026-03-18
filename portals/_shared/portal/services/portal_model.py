from __future__ import annotations

from typing import Any


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(dict(out.get(key) or {}), value)
        else:
            out[key] = value
    return out


def legacy_portal_model_keys_used(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return []
    legacy_keys = [
        "organization_config",
        "organization_configuration",
        "orangization_configuration",
        "organization_config_file",
        "legal_entity_config_file",
        "legal_entity_type",
    ]
    return [key for key in legacy_keys if key in payload]


def canonicalize_portal_model_config(payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload if isinstance(payload, dict) else {})

    old_org_cfg = body.get("organization_config") if isinstance(body.get("organization_config"), dict) else {}
    old_org_cfg_alt = (
        body.get("organization_configuration") if isinstance(body.get("organization_configuration"), dict) else {}
    )
    old_org_cfg_typo = (
        body.get("orangization_configuration") if isinstance(body.get("orangization_configuration"), dict) else {}
    )
    merged_org_cfg = _deep_merge(_deep_merge(old_org_cfg, old_org_cfg_alt), old_org_cfg_typo)

    defaults = merged_org_cfg.get("default_values") if isinstance(merged_org_cfg.get("default_values"), dict) else {}
    added = merged_org_cfg.get("added_values") if isinstance(merged_org_cfg.get("added_values"), dict) else {}

    file_name = _as_text(
        body.get("organization_config_file")
        or body.get("legal_entity_config_file")
        or merged_org_cfg.get("file_name")
        or merged_org_cfg.get("config_file")
        or merged_org_cfg.get("legal_entity_config_file")
        or merged_org_cfg.get("legal_entity_type")
        or merged_org_cfg.get("type")
    )
    if file_name and "." not in file_name:
        file_name = f"{file_name}.json"

    legal_type = _as_text(
        body.get("legal_entity_type")
        or merged_org_cfg.get("legal_entity_type")
        or merged_org_cfg.get("type")
        or file_name.replace(".json", "")
    ).lower()

    portal_profile = body.get("portal_profile") if isinstance(body.get("portal_profile"), dict) else {}
    portal_behavior = body.get("portal_behavior") if isinstance(body.get("portal_behavior"), dict) else {}
    portal_features = body.get("portal_features") if isinstance(body.get("portal_features"), dict) else {}

    profile_defaults = defaults.get("legal_entity_defaults") if isinstance(defaults.get("legal_entity_defaults"), dict) else {}
    profile_overrides = added.get("legal_entity_defaults") if isinstance(added.get("legal_entity_defaults"), dict) else {}
    next_profile = _deep_merge(
        {
            "schema": "mycite.portal_profile.v1",
            "portal_type": "portal",
            "profile_kind": legal_type or _as_text(profile_defaults.get("type")),
            "organization_config_file": file_name,
            "defaults": _deep_merge(profile_defaults, profile_overrides),
        },
        portal_profile,
    )

    next_behavior = _deep_merge(
        {
            "schema": "mycite.portal_behavior.v1",
            "defaults": defaults,
            "overrides": added,
        },
        portal_behavior,
    )

    workflow_defaults = defaults.get("workflow_config") if isinstance(defaults.get("workflow_config"), dict) else {}
    workflow_overrides = added.get("workflow_config") if isinstance(added.get("workflow_config"), dict) else {}
    workflow_enabled = bool(
        workflow_overrides.get("enabled")
        if "enabled" in workflow_overrides
        else workflow_defaults.get("enabled")
        if "enabled" in workflow_defaults
        else False
    )
    next_features = _deep_merge(
        {
            "schema": "mycite.portal_features.v1",
            "workflow_enabled": workflow_enabled,
        },
        portal_features,
    )

    body["portal_profile"] = next_profile
    body["portal_behavior"] = next_behavior
    body["portal_features"] = next_features

    # Canonical writes should not keep legacy legal-entity shape as source-of-truth.
    for key in (
        "organization_config",
        "organization_configuration",
        "orangization_configuration",
        "organization_config_file",
        "legal_entity_config_file",
        "legal_entity_type",
    ):
        body.pop(key, None)
    return body
