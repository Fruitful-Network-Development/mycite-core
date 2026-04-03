from __future__ import annotations

import json
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, redirect

config_schema_bp = Blueprint("config_schema", __name__)

TOOL_ID = "config_schema"
TOOL_TITLE = "Config Structure"
TOOL_HOME_PATH = "/portal/tools/config_schema/home"
TOOL_BLUEPRINT = config_schema_bp


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _json_default(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _expected_field_rows(default_behavior: Dict[str, Any]) -> List[Dict[str, str]]:
    stream_cfg = _as_dict(default_behavior.get("stream_config"))
    calendar_cfg = _as_dict(default_behavior.get("calendar_config"))
    people_cfg = _as_dict(default_behavior.get("people_config"))
    workflow_cfg = _as_dict(default_behavior.get("workflow_config"))
    legal_defaults = _as_dict(default_behavior.get("legal_entity_defaults"))
    role_groups = _as_dict(legal_defaults.get("role_groups"))

    return [
        {
            "path": "organization_config.file_name",
            "kind": "string",
            "required": "yes",
            "default_value": str(default_behavior.get("organization_config_file") or "subject_congregation.json"),
            "note": "Legal-entity profile filename used as the base type selector.",
        },
        {
            "path": "organization_config.default_values.stream_config.allowed_post_types",
            "kind": "list[string]",
            "required": "no",
            "default_value": _json_default(stream_cfg.get("allowed_post_types") or []),
            "note": "Feed event types visible in board-member stream.",
        },
        {
            "path": "organization_config.default_values.stream_config.newest_first",
            "kind": "boolean",
            "required": "no",
            "default_value": _json_default(bool(stream_cfg.get("newest_first", True))),
            "note": "Controls feed ordering preference.",
        },
        {
            "path": "organization_config.default_values.calendar_config.allowed_event_types",
            "kind": "list[string]",
            "required": "no",
            "default_value": _json_default(calendar_cfg.get("allowed_event_types") or []),
            "note": "Calendar event types allowed in embedded board workspace.",
        },
        {
            "path": "organization_config.default_values.calendar_config.exclude_request_log_types",
            "kind": "boolean",
            "required": "no",
            "default_value": _json_default(bool(calendar_cfg.get("exclude_request_log_types", True))),
            "note": "Whether calendar filters out request-log style event types.",
        },
        {
            "path": "organization_config.default_values.people_config.profile_source_priority",
            "kind": "list[string]",
            "required": "no",
            "default_value": _json_default(people_cfg.get("profile_source_priority") or []),
            "note": "Priority order for people-profile source resolution.",
        },
        {
            "path": "organization_config.default_values.workflow_config.enabled",
            "kind": "boolean",
            "required": "no",
            "default_value": _json_default(bool(workflow_cfg.get("enabled", True))),
            "note": "Enables or disables the workflow tab for board members.",
        },
        {
            "path": "organization_config.default_values.workflow_config.sections",
            "kind": "list[object]",
            "required": "no",
            "default_value": _json_default(workflow_cfg.get("sections") or []),
            "note": "UI workflow sections and descriptors.",
        },
        {
            "path": "organization_config.default_values.legal_entity_defaults.type",
            "kind": "string",
            "required": "no",
            "default_value": str(legal_defaults.get("type") or ""),
            "note": "Resolved legal entity type inferred from the selected profile file.",
        },
        {
            "path": "organization_config.default_values.legal_entity_defaults.role_groups",
            "kind": "object",
            "required": "no",
            "default_value": _json_default(role_groups),
            "note": "Default role-group buckets for members/users/poc_admin.",
        },
        {
            "path": "organization_config.added_values.broadcast_config",
            "kind": "object",
            "required": "no",
            "default_value": "{}",
            "note": "Optional broadcast overlay merged on top of defaults.",
        },
    ]


def _build_model_payload() -> Dict[str, Any]:
    active_cfg = _as_dict(current_app.config.get("MYCITE_ACTIVE_PRIVATE_CONFIG"))
    default_behavior = _as_dict(current_app.config.get("MYCITE_PORTAL_BEHAVIOR_DEFAULTS"))
    resolved_behavior = _as_dict(current_app.config.get("MYCITE_PORTAL_BEHAVIOR_CONFIG"))
    org_cfg = _as_dict(active_cfg.get("organization_config"))

    return {
        "tool_id": TOOL_ID,
        "msn_id": str(current_app.config.get("MYCITE_MSN_ID") or ""),
        "portal_instance_id": str(current_app.config.get("MYCITE_PORTAL_INSTANCE_ID") or ""),
        "expected_fields": _expected_field_rows(default_behavior),
        "organization_config": org_cfg,
        "default_behavior": default_behavior,
        "resolved_behavior": resolved_behavior,
    }


@config_schema_bp.get("/portal/tools/config_schema/home")
def config_schema_home():
    return redirect("/portal/system", code=302)


@config_schema_bp.get("/portal/tools/config_schema/model.json")
def config_schema_model_json():
    return jsonify(_build_model_payload())


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
