import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, send_from_directory
from jinja2 import TemplateNotFound

from data.engine.workspace import Workspace
from data.storage_json import JsonStorageBackend
from portal.api.aliases import get_alias_record, list_alias_records, register_aliases_routes
from portal.api.data_workspace import register_data_routes
from portal.core_services.runtime import (
    active_service_from_path,
    active_private_config_filename,
    build_network_cards,
    build_network_tabs,
    build_property_geography_model,
    build_service_nav,
    load_active_private_config,
    resolve_active_private_config_path,
    normalize_network_tab,
)
from portal.services.board_access import require_board_member
from portal.services.progeny_embed import build_embed_progeny_landing
from portal.services.request_log_store import append_event as append_request_log_event
from portal.services.workspace_store import append_event as append_workspace_event
from portal.services.workspace_store import materialize_people, read_events, workspace_root
from portal.tools.runtime import active_tool_for_path, read_enabled_tools, register_tool_blueprints

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "portal", "ui", "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "portal", "ui", "static"),
    static_url_path="/portal/static",
)

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = Path(os.environ.get("PUBLIC_DIR", str(BASE_DIR / "public")))
PRIVATE_DIR = Path(os.environ.get("PRIVATE_DIR", str(BASE_DIR / "private")))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
FALLBACK_DIR = BASE_DIR
REPO_ROOT = BASE_DIR.parent
ICONS_DIR = REPO_ROOT / "assets" / "icons"
PORTAL_INSTANCE_ID = str(os.environ.get("PORTAL_INSTANCE_ID") or BASE_DIR.name).strip().lower()
IS_TFF_PORTAL = "tff" in PORTAL_INSTANCE_ID
DEFAULT_EMBED_PORT = str(os.environ.get("DEFAULT_EMBED_PORT") or "5201").strip() or "5201"
DEFAULT_FEED_TYPES = {"post.create", "board_notice"}
DEFAULT_CALENDAR_TYPES = {"meeting", "group_event", "committee_meeting"}
ALIAS_EXPECTED_BY_TYPE = {
    "board_member": False,
    "poc": True,
    "constituent_farm": True,
}
DEFAULT_PROFILE_SOURCE_PRIORITY = ["progeny.internal", "progeny.config_ref", "alias"]
LEGAL_ENTITY_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "discovery_engine.json": {
        "schema": "mycite.legal_entity_type.v1",
        "type": "discovery_engine",
        "title": "Discovery Engine",
        "role_groups": {"members": [], "users": [], "poc_admin": []},
    },
    "social_network.json": {
        "schema": "mycite.legal_entity_type.v1",
        "type": "social_network",
        "title": "Social Network",
        "role_groups": {"members": [], "users": [], "poc_admin": []},
    },
    "subject_congregation.json": {
        "schema": "mycite.legal_entity_type.v1",
        "type": "subject_congregation",
        "title": "Subject Congregation",
        "role_groups": {"members": [], "users": [], "poc_admin": []},
        "workflow_defaults": {"farm_fields": [], "committees": []},
    },
}


def _default_portal_sign_out_url() -> str:
    if "tff" in PORTAL_INSTANCE_ID:
        target = "/portal/tff"
    else:
        target = "/portal/fnd"
    encoded_target = quote(target, safe="")
    return f"/oauth2/sign_out?rd=%2Foauth2%2Fsign_in%3Frd%3D{encoded_target}"


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected object JSON in {path}")
    return payload


def _read_json_relaxed(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r",(\s*[\]}])", r"\1", text)
        payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _find_first(paths) -> Optional[Path]:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _resolve_public_profile_path(msn_id: str) -> Optional[Path]:
    candidates = [
        PUBLIC_DIR / f"{msn_id}.json",
        PUBLIC_DIR / f"msn-{msn_id}.json",
        PUBLIC_DIR / f"mss-{msn_id}.json",
        FALLBACK_DIR / f"{msn_id}.json",
        FALLBACK_DIR / f"msn-{msn_id}.json",
        FALLBACK_DIR / f"mss-{msn_id}.json",
    ]
    return _find_first(candidates)


def _sanitize_public_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"msn_id", "schema", "title", "public_key", "entity_type", "accessible"}
    out = {k: payload.get(k) for k in allowed if k in payload}
    out.setdefault("accessible", {})
    return out


def _options_public(msn_id: str) -> Dict[str, Any]:
    return {
        "self": {
            "href": f"/{msn_id}.json",
            "methods": ["GET", "OPTIONS"],
            "auth": "none",
        }
    }


def _options_private(msn_id: str) -> Dict[str, Any]:
    return {
        "portal": {"href": "/portal", "methods": ["GET", "OPTIONS"], "auth": "keycloak_or_local"},
        "aliases": {
            "href": f"/portal/api/aliases?msn_id={msn_id}",
            "methods": ["GET", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
    }


def _infer_local_msn_id() -> str:
    if os.environ.get("MSN_ID"):
        return str(os.environ.get("MSN_ID")).strip()

    active_cfg = load_active_private_config(PRIVATE_DIR, None)
    msn_id = str(active_cfg.get("msn_id") or "").strip() if isinstance(active_cfg, dict) else ""
    if msn_id:
        return msn_id

    for cfg in sorted(PRIVATE_DIR.glob("mycite-config-*.json")):
        try:
            payload = _read_json(cfg)
        except Exception:
            continue
        msn_id = str(payload.get("msn_id") or "").strip()
        if msn_id:
            return msn_id

    for path in sorted(PUBLIC_DIR.glob("*.json")):
        try:
            payload = _read_json(path)
        except Exception:
            continue
        msn_id = str(payload.get("msn_id") or "").strip()
        if msn_id:
            return msn_id

    return ""


def _format_sidebar_entity_title(raw: str) -> str:
    token = re.sub(r"[_-]+", " ", str(raw or "").strip())
    token = re.sub(r"\s+", " ", token).strip()
    return token.upper()


def _alias_label(alias_payload: Dict[str, Any], alias_id: Optional[str] = None) -> str:
    host_title = str(alias_payload.get("host_title") or "").strip()
    if host_title:
        return _format_sidebar_entity_title(host_title)

    if alias_id:
        return _format_sidebar_entity_title(alias_id)

    return "UNNAMED ALIAS"
def _sanitize_env_suffix(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", value).upper()


def _resolve_embed_port(alias_host: str) -> str:
    host = (alias_host or "").strip()
    if host:
        per_host_key = f"EMBED_HOST_PORT_{_sanitize_env_suffix(host)}"
        if os.environ.get(per_host_key):
            return str(os.environ.get(per_host_key)).strip()

    if os.environ.get("EMBED_HOST_PORT"):
        return str(os.environ.get("EMBED_HOST_PORT")).strip()

    return DEFAULT_EMBED_PORT


def _extract_tenant_msn_id(alias_payload: Dict[str, Any]) -> str:
    return str(alias_payload.get("child_msn_id") or alias_payload.get("tenant_id") or "").strip()


def _extract_contract_id(alias_payload: Dict[str, Any]) -> str:
    return str(alias_payload.get("contract_id") or alias_payload.get("symmetric_key_contract") or "").strip()


def _extract_member_msn_id(alias_payload: Dict[str, Any]) -> str:
    return str(
        alias_payload.get("member_msn_id")
        or alias_payload.get("child_msn_id")
        or alias_payload.get("tenant_id")
        or alias_payload.get("msn_id")
        or ""
    ).strip()


def _build_widget_url(alias_id: str, alias_payload: Dict[str, Any]) -> str:
    org_msn_id = str(alias_payload.get("alias_host") or "").strip()
    org_title = str(alias_payload.get("host_title") or "").strip()
    embed_port = _resolve_embed_port(org_msn_id)
    base_url = f"http://127.0.0.1:{embed_port}"

    progeny_type = str(alias_payload.get("progeny_type") or "").strip().lower()
    tenant_msn_id = _extract_tenant_msn_id(alias_payload)
    if progeny_type == "tenant" and tenant_msn_id:
        query = urlencode(
            {
                "tenant_msn_id": tenant_msn_id,
                "contract_id": _extract_contract_id(alias_payload),
                "as_alias_id": alias_id,
            }
        )
        return f"{base_url}/portal/embed/tenant?{query}"

    member_msn_id = _extract_member_msn_id(alias_payload)
    if progeny_type == "board_member" and member_msn_id:
        query = urlencode({"member_msn_id": member_msn_id, "as_alias_id": alias_id, "tab": "feed"})
        return f"{base_url}/portal/embed/board_member?{query}"

    query = urlencode({"org_msn_id": org_msn_id, "as_alias_id": alias_id, "org_title": org_title})
    return f"{base_url}/portal/embed/poc?{query}"


def list_aliases_for_sidebar(private_dir: Path) -> list[Dict[str, Any]]:
    records, _ = list_alias_records(private_dir)
    aliases: list[Dict[str, Any]] = []
    for record in records:
        alias_id = str(record.get("alias_id") or "").strip()
        if not alias_id:
            continue
        aliases.append(
            {
                "alias_id": alias_id,
                "label": _alias_label(record, alias_id),
                "org_title": str(record.get("host_title") or "").strip(),
                "org_msn_id": str(record.get("alias_host") or "").strip(),
                "progeny_type": str(record.get("progeny_type") or "").strip(),
                "tenant_id": str(record.get("child_msn_id") or record.get("tenant_id") or "").strip(),
                "member_id": _extract_member_msn_id(record),
            }
        )
    return aliases


def _safe_progeny_ref_path(ref_token: str) -> Optional[Path]:
    rel = Path(str(ref_token or "").strip())
    if not str(rel) or rel.is_absolute() or ".." in rel.parts:
        return None
    return PRIVATE_DIR / "progeny" / rel


def _infer_msn_id_from_progeny_ref(ref_token: str) -> str:
    name = Path(str(ref_token or "")).name
    match = re.search(r"progeny-(?P<msn>[0-9-]+)-[a-z_]+\.json$", name, re.IGNORECASE)
    if match:
        return str(match.group("msn") or "").strip()
    if name.endswith(".json"):
        stem = Path(name).stem
        if re.fullmatch(r"[0-9-]+", stem):
            return stem
    return ""


def _iter_progeny_refs(raw: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def _push(progeny_type: str, ref_token: Any) -> None:
        t = str(progeny_type or "").strip().lower()
        r = str(ref_token or "").strip()
        if not t or not r:
            return
        out.append((t, r))

    def _walk(node: Any, fallback_type: str = "") -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item, fallback_type=fallback_type)
            return
        if isinstance(node, dict):
            explicit_type = str(node.get("progeny_type") or node.get("type") or fallback_type or "").strip().lower()
            explicit_ref = node.get("ref") or node.get("path") or node.get("file") or node.get("source")
            if explicit_type and explicit_ref:
                _push(explicit_type, explicit_ref)
                refs = node.get("refs")
                if isinstance(refs, list):
                    for ref in refs:
                        _push(explicit_type, ref)
                return
            for key, value in node.items():
                key_token = str(key or "").strip().lower()
                if key_token in {"progeny_type", "type", "ref", "path", "file", "source", "refs"}:
                    continue
                if isinstance(value, str):
                    _push(key_token or fallback_type, value)
                else:
                    _walk(value, fallback_type=key_token or fallback_type)

    _walk(raw)
    return out


def _seed_missing_local_progeny_profiles() -> None:
    candidate_cfg_paths: list[Path] = []
    active_cfg_path = resolve_active_private_config_path(PRIVATE_DIR, MSN_ID or None)
    if active_cfg_path is not None:
        candidate_cfg_paths.append(active_cfg_path)
    candidate_cfg_paths.extend(sorted(PRIVATE_DIR.glob("mycite-config-*.json")))

    cfg_paths: list[Path] = []
    seen_cfg_paths: set[Path] = set()
    for path in candidate_cfg_paths:
        if path in seen_cfg_paths:
            continue
        seen_cfg_paths.add(path)
        cfg_paths.append(path)
    if not cfg_paths:
        return

    for cfg_path in cfg_paths:
        try:
            cfg = _read_json_relaxed(cfg_path)
        except Exception:
            continue
        for progeny_type, ref_token in _iter_progeny_refs(cfg.get("progeny")):
            if not progeny_type or not ref_token:
                continue

            target = _safe_progeny_ref_path(ref_token)
            if target is None or target.exists():
                continue

            stem = target.stem
            inferred_msn = _infer_msn_id_from_progeny_ref(ref_token)
            payload: Dict[str, Any] = {
                "schema": "mycite.progeny.profile_card.v1",
                "progeny_id": stem,
                "msn_id": inferred_msn,
                "progeny_type": progeny_type,
                "display": {
                    "title": inferred_msn or stem,
                    "subtitle": "Auto-seeded local progeny profile",
                },
                "contact": {},
                "alias_expected": ALIAS_EXPECTED_BY_TYPE.get(progeny_type, False),
                "status": {
                    "state": "active",
                    "note": "Auto-generated from mycite-config progeny reference.",
                },
                "source": {
                    "kind": "config_ref_seed",
                    "ref": ref_token,
                    "local_only": True,
                },
            }
            _write_json(target, payload)


def _deep_merge_dict(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dict(dict(out.get(key) or {}), value)
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


def _generic_legal_entity_defaults(file_name: str) -> Dict[str, Any]:
    legal_type = Path(file_name).stem.lower().strip() or "subject_congregation"
    title = legal_type.replace("_", " ").replace("-", " ").title()
    return {
        "schema": "mycite.legal_entity_type.v1",
        "type": legal_type,
        "title": title,
        "role_groups": {"members": [], "users": [], "poc_admin": []},
    }


def _organization_config_filename(active_cfg: Dict[str, Any]) -> str:
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
    fallback = "subject_congregation.json" if IS_TFF_PORTAL else "discovery_engine.json"
    loose_org_cfg_value = (
        active_cfg.get("organization_configuration")
        if isinstance(active_cfg.get("organization_configuration"), str)
        else active_cfg.get("orangization_configuration")
        if isinstance(active_cfg.get("orangization_configuration"), str)
        else ""
    )
    candidates = [
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


def _collect_org_layers(active_cfg: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    defaults: Dict[str, Any] = {}
    added: Dict[str, Any] = {}

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


def _default_portal_behavior(active_cfg: Dict[str, Any]) -> Dict[str, Any]:
    org_config_file = _organization_config_filename(active_cfg)
    legal_type = Path(org_config_file).stem.lower().strip() or "subject_congregation"
    legal_defaults = LEGAL_ENTITY_PROFILE_DEFAULTS.get(org_config_file) or _generic_legal_entity_defaults(org_config_file)

    return {
        "organization_config_file": org_config_file,
        "legal_entity_type": legal_type,
        "stream_config": {
            "schema": "mycite.portal.stream_config.v1",
            "allowed_post_types": sorted(DEFAULT_FEED_TYPES),
            "newest_first": True,
        },
        "calendar_config": {
            "schema": "mycite.portal.calendar_config.v1",
            "allowed_event_types": sorted(DEFAULT_CALENDAR_TYPES),
            "exclude_request_log_types": True,
        },
        "people_config": {
            "schema": "mycite.portal.people_config.v1",
            "profile_source_priority": list(DEFAULT_PROFILE_SOURCE_PRIORITY),
        },
        "workflow_config": {
            "schema": "mycite.portal.workflow_config.v1",
            "enabled": IS_TFF_PORTAL,
            "legal_entity_type": legal_type,
            "sections": [
                {"id": "operations", "title": "Operations", "description": "Core operating workflow checkpoints."},
                {
                    "id": "farm_fields",
                    "title": "Farm Fields",
                    "description": "Field inventories and seasonal status references.",
                },
                {"id": "compliance", "title": "Compliance", "description": "Compliance and policy milestones."},
            ],
            "anthology_refs": {
                "farm_fields": "",
                "workflow_state": "",
            },
        },
        "legal_entity_defaults": dict(legal_defaults),
    }


def _build_portal_behavior_config(active_cfg: Dict[str, Any]) -> Dict[str, Any]:
    base = _default_portal_behavior(active_cfg)
    defaults, added = _collect_org_layers(active_cfg)
    merged = _deep_merge_dict(base, defaults)
    merged = _deep_merge_dict(merged, added)

    org_config_file = _organization_config_filename(active_cfg)
    legal_type = Path(org_config_file).stem.lower().strip() or "subject_congregation"
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
        legal_defaults["role_groups"] = {"members": [], "users": [], "poc_admin": []}
    merged["legal_entity_defaults"] = legal_defaults
    return merged


def _workflow_enabled() -> bool:
    if not IS_TFF_PORTAL:
        return False
    workflow_cfg = PORTAL_BEHAVIOR_CONFIG.get("workflow_config") if isinstance(PORTAL_BEHAVIOR_CONFIG, dict) else {}
    if not isinstance(workflow_cfg, dict):
        return False
    return bool(workflow_cfg.get("enabled", True))


def _board_tabs() -> list[str]:
    tabs = ["feed", "calendar", "people"]
    if _workflow_enabled():
        tabs.append("workflow")
    return tabs


def _feed_allowed_types() -> set[str]:
    config = PORTAL_BEHAVIOR_CONFIG.get("stream_config") if isinstance(PORTAL_BEHAVIOR_CONFIG, dict) else {}
    if not isinstance(config, dict):
        config = {}
    raw = config.get("allowed_post_types")
    if not isinstance(raw, list):
        return set(DEFAULT_FEED_TYPES)
    out = {str(item).strip() for item in raw if str(item or "").strip()}
    return out or set(DEFAULT_FEED_TYPES)


def _calendar_allowed_types() -> set[str]:
    config = PORTAL_BEHAVIOR_CONFIG.get("calendar_config") if isinstance(PORTAL_BEHAVIOR_CONFIG, dict) else {}
    if not isinstance(config, dict):
        config = {}
    raw = config.get("allowed_event_types")
    if not isinstance(raw, list):
        return set(DEFAULT_CALENDAR_TYPES)
    out = {str(item).strip() for item in raw if str(item or "").strip()}
    return out or set(DEFAULT_CALENDAR_TYPES)


def _workflow_model() -> Dict[str, Any]:
    if not _workflow_enabled():
        return {}
    config = PORTAL_BEHAVIOR_CONFIG.get("workflow_config") if isinstance(PORTAL_BEHAVIOR_CONFIG, dict) else {}
    config = dict(config) if isinstance(config, dict) else {}
    legal_type = str(
        config.get("legal_entity_type")
        or PORTAL_BEHAVIOR_CONFIG.get("legal_entity_type")
        or "subject_congregation"
    ).strip().lower()
    legal_defaults = PORTAL_BEHAVIOR_CONFIG.get("legal_entity_defaults") if isinstance(PORTAL_BEHAVIOR_CONFIG, dict) else {}
    legal_defaults = dict(legal_defaults) if isinstance(legal_defaults, dict) else {}
    return {
        "config": config,
        "legal_entity_type": legal_type,
        "legal_defaults": legal_defaults,
        "organization_config_file": str(PORTAL_BEHAVIOR_CONFIG.get("organization_config_file") or ""),
    }


MSN_ID = _infer_local_msn_id()
ACTIVE_PRIVATE_CONFIG = load_active_private_config(PRIVATE_DIR, MSN_ID or None)
PORTAL_BEHAVIOR_DEFAULTS = _default_portal_behavior(ACTIVE_PRIVATE_CONFIG)
PORTAL_BEHAVIOR_CONFIG = _build_portal_behavior_config(ACTIVE_PRIVATE_CONFIG)
app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = ACTIVE_PRIVATE_CONFIG
app.config["MYCITE_PORTAL_BEHAVIOR_DEFAULTS"] = PORTAL_BEHAVIOR_DEFAULTS
app.config["MYCITE_PORTAL_BEHAVIOR_CONFIG"] = PORTAL_BEHAVIOR_CONFIG
app.config["MYCITE_PORTAL_INSTANCE_ID"] = PORTAL_INSTANCE_ID
app.config["MYCITE_MSN_ID"] = MSN_ID
DATA_TOOL_CONFIG = (
    ACTIVE_PRIVATE_CONFIG.get("data_tool")
    if isinstance(ACTIVE_PRIVATE_CONFIG.get("data_tool"), dict)
    else {}
)
WORKSPACE_CONFIG: Dict[str, Any] = dict(DATA_TOOL_CONFIG)
WORKSPACE_CONFIG["state_path"] = str(PRIVATE_DIR / "daemon_state" / "data_workspace.json")
WORKSPACE_CONFIG["icon_root"] = str(ICONS_DIR)
WORKSPACE_CONFIG["icon_base_url"] = "/portal/static/icons"
WORKSPACE_CONFIG["icon_relpath_mode"] = str(WORKSPACE_CONFIG.get("icon_relpath_mode") or "basename").strip().lower()
TOOL_TABS = register_tool_blueprints(
    app,
    read_enabled_tools(PRIVATE_DIR, msn_id=MSN_ID or None),
    tools_dir=BASE_DIR / "portal" / "tools",
    private_dir=PRIVATE_DIR,
)
DATA_WORKSPACE = Workspace(JsonStorageBackend(DATA_DIR), config=WORKSPACE_CONFIG)
app.config["MYCITE_DATA_WORKSPACE"] = DATA_WORKSPACE
DATA_HOME_TEMPLATE = BASE_DIR / "portal" / "ui" / "templates" / "tools" / "data_tool_home.html"
DATA_HOME_AVAILABLE = DATA_HOME_TEMPLATE.exists()
HOME_TAB_IDS = ("portal", "data", "tools", "vault")


def _normalize_home_tab(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in HOME_TAB_IDS else "portal"


def _home_tab_routes() -> list[Dict[str, str]]:
    return [
        {"tab_id": "portal", "label": "Portal", "href": "/portal/home?tab=portal"},
        {"tab_id": "data", "label": "Data", "href": "/portal/home?tab=data"},
        {"tab_id": "tools", "label": "Tools", "href": "/portal/home?tab=tools"},
        {"tab_id": "vault", "label": "Vault", "href": "/portal/home?tab=vault"},
    ]


def _collect_vault_refs(payload: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                _walk(value)
            return
        if isinstance(node, list):
            for value in node:
                _walk(value)
            return
        if not isinstance(node, str):
            return
        token = node.strip()
        if token.startswith("vault://") and token not in seen:
            seen.add(token)
            out.append(token)

    _walk(payload)
    return out


def _vault_contract_files() -> list[str]:
    root = PRIVATE_DIR / "vault" / "contracts"
    if not root.exists() or not root.is_dir():
        return []
    return [path.name for path in sorted(root.glob("*.json")) if path.is_file()]


def _portal_profile_model() -> Dict[str, Any]:
    local_msn_id = str(MSN_ID or _infer_local_msn_id() or "").strip()
    public_profile: Dict[str, Any] = {}
    if local_msn_id:
        profile_path = _resolve_public_profile_path(local_msn_id)
        if profile_path and profile_path.exists():
            try:
                public_profile = _sanitize_public_profile(_read_json(profile_path))
            except Exception:
                public_profile = {}

    config_file = active_private_config_filename(PRIVATE_DIR, MSN_ID or None)

    return {
        "msn_id": local_msn_id,
        "public_profile": public_profile,
        "options_public": _options_public(local_msn_id) if local_msn_id else {},
        "fnd_profile": {
            "status": "planned",
            "description": "Public profile extensions (banner, avatar, bio) are reserved for the next iteration.",
        },
        "config_file": config_file,
    }


def _request_log_summary() -> Dict[str, Any]:
    root = PRIVATE_DIR / "request_log"
    if not root.exists() or not root.is_dir():
        return {"file_count": 0, "event_count": 0}
    files = sorted(path for path in root.glob("*.ndjson") if path.is_file())
    event_count = 0
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        event_count += 1
        except Exception:
            continue
    return {"file_count": len(files), "event_count": event_count}


def _request_log_channels() -> list[Dict[str, Any]]:
    root = PRIVATE_DIR / "request_log"
    if not root.exists() or not root.is_dir():
        return []
    out: list[Dict[str, Any]] = []
    for path in sorted(root.glob("*.ndjson")):
        if not path.is_file():
            continue
        event_count = 0
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        event_count += 1
        except Exception:
            event_count = 0
        channel_id = str(path.stem)
        out.append(
            {
                "id": channel_id,
                "label": channel_id,
                "event_count": event_count,
                "href": f"/portal/network?view=log&id={quote(channel_id, safe='')}",
            }
        )
    return out


def _p2p_channels() -> list[Dict[str, Any]]:
    root = PRIVATE_DIR / "request_log"
    if not root.exists() or not root.is_dir():
        return []
    counts: Dict[str, int] = {}
    for path in sorted(root.glob("*.ndjson")):
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    token = line.strip()
                    if not token:
                        continue
                    try:
                        payload = json.loads(token)
                    except Exception:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    tx = str(payload.get("transmitter") or "").strip()
                    rx = str(payload.get("receiver") or "").strip()
                    if not tx or not rx:
                        continue
                    channel_id = f"{tx}->{rx}"
                    counts[channel_id] = counts.get(channel_id, 0) + 1
        except Exception:
            continue

    out: list[Dict[str, Any]] = []
    for channel_id, event_count in sorted(counts.items(), key=lambda item: item[0].lower()):
        out.append(
            {
                "id": channel_id,
                "label": channel_id,
                "event_count": event_count,
                "href": f"/portal/network?view=p2p&id={quote(channel_id, safe='')}",
            }
        )
    return out


def _network_sidebar_alias_items() -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    for alias in list_aliases_for_sidebar(PRIVATE_DIR):
        alias_id = str(alias.get("alias_id") or "").strip()
        if not alias_id:
            continue
        out.append(
            {
                "id": alias_id,
                "label": str(alias.get("label") or alias_id).strip(),
                "org_msn_id": str(alias.get("org_msn_id") or "").strip(),
                "href": f"/portal/network?view=alias&id={quote(alias_id, safe='')}",
                "alias_id": alias_id,
                "alias_label": str(alias.get("label") or alias_id).strip(),
            }
        )
    return out


def _context_sidebar_sections(active_service: str) -> list[Dict[str, Any]]:
    token = str(active_service or "system").strip().lower()
    view = str(request.args.get("view") or "alias").strip().lower()
    selected = str(request.args.get("id") or "").strip()

    if token == "network":
        aliases = _network_sidebar_alias_items()
        logs = _request_log_channels()
        p2p = _p2p_channels()
        return [
            {
                "title": "Alias Interfaces",
                "items": [
                    {
                        "label": item["label"],
                        "meta": item.get("org_msn_id") or "",
                        "href": item["href"],
                        "active": view == "alias" and selected == item["id"],
                    }
                    for item in aliases
                ],
                "empty_text": "No aliases loaded",
            },
            {
                "title": "Request Logs",
                "items": [
                    {
                        "label": item["label"],
                        "meta": f"{item['event_count']} event(s)",
                        "href": item["href"],
                        "active": view == "log" and selected == item["id"],
                    }
                    for item in logs
                ],
                "empty_text": "No request logs found",
            },
            {
                "title": "P2P",
                "items": [
                    {
                        "label": item["label"],
                        "meta": f"{item['event_count']} event(s)",
                        "href": item["href"],
                        "active": view == "p2p" and selected == item["id"],
                    }
                    for item in p2p
                ],
                "empty_text": "No P2P channels derived yet",
            },
        ]

    if token == "utilities":
        tab = str(request.args.get("tab") or "inbox").strip().lower()
        return [
            {
                "title": "Utility Views",
                "items": [
                    {"label": "Inbox", "href": "/portal/utilities?tab=inbox", "active": tab == "inbox", "meta": ""},
                    {"label": "Launchers", "href": "/portal/utilities?tab=launchers", "active": tab == "launchers", "meta": ""},
                ],
                "empty_text": "",
            }
        ]

    if token == "peripherals":
        tab = str(request.args.get("tab") or "peripherals").strip().lower()
        return [
            {
                "title": "Peripheral Tabs",
                "items": [
                    {"label": "Tools", "href": "/portal/peripherals?tab=tools", "active": tab == "tools", "meta": ""},
                    {"label": "Peripherals", "href": "/portal/peripherals?tab=peripherals", "active": tab == "peripherals", "meta": ""},
                    {"label": "Progeny", "href": "/portal/peripherals?tab=progeny", "active": tab == "progeny", "meta": ""},
                    {"label": "Configuration", "href": "/portal/peripherals?tab=configuration", "active": tab == "configuration", "meta": ""},
                    {"label": "Vault", "href": "/portal/peripherals?tab=vault", "active": tab == "vault", "meta": ""},
                ],
                "empty_text": "",
            }
        ]

    return [
        {
            "title": "Profile",
            "items": [
                {"label": "Portal Contact Card", "href": "/portal/system", "active": True, "meta": f"msn-{MSN_ID}.json"},
                {"label": "Data Workbench", "href": "/portal/system#data-workbench", "active": False, "meta": "Anthology/NIMM/AITAS"},
            ],
            "empty_text": "",
        }
    ]


@app.context_processor
def _shell_context() -> Dict[str, Any]:
    active_service = active_service_from_path(request.path)
    active_service_tab = ""
    if active_service == "network":
        active_service_tab = str(request.args.get("view") or "alias").strip().lower()
    active_tool = active_tool_for_path(TOOL_TABS, request.path)
    network_cards = build_network_cards(PRIVATE_DIR, ACTIVE_PRIVATE_CONFIG)
    progeny_cards = network_cards.get("progeny") if isinstance(network_cards, dict) else []
    sidebar_progeny: list[Dict[str, str]] = []
    if isinstance(progeny_cards, list):
        for card in progeny_cards:
            if not isinstance(card, dict):
                continue
            display = card.get("display") if isinstance(card.get("display"), dict) else {}
            progeny_id = str(card.get("progeny_id") or card.get("msn_id") or "").strip()
            title = str(display.get("title") or card.get("progeny_id") or card.get("msn_id") or "Unnamed progeny").strip()
            sidebar_progeny.append(
                {
                    "progeny_id": progeny_id,
                    "title": title,
                    "href": "/portal/network/provisions",
                }
            )

    display_cfg = ACTIVE_PRIVATE_CONFIG.get("display") if isinstance(ACTIVE_PRIVATE_CONFIG.get("display"), dict) else {}
    portal_name = str(
        display_cfg.get("title")
        or ACTIVE_PRIVATE_CONFIG.get("portal_title")
        or ACTIVE_PRIVATE_CONFIG.get("title")
        or MSN_ID
        or "Portal"
    ).strip()
    active_portal_username = str(
        request.headers.get("X-Portal-Username")
        or request.headers.get("X-Auth-Request-Preferred-Username")
        or request.headers.get("X-Portal-User")
        or ""
    ).strip()
    current_path = request.full_path if request.query_string else request.path
    if current_path.endswith("?"):
        current_path = current_path[:-1]
    current_path = str(current_path or "/portal/system").strip() or "/portal/system"
    if not current_path.startswith("/"):
        current_path = "/portal/system"

    sign_out_url = str(os.environ.get("PORTAL_SIGN_OUT_URL") or "").strip()
    if not sign_out_url:
        sign_out_url = _default_portal_sign_out_url()
    switch_portal_url = str(os.environ.get("PORTAL_SWITCH_URL") or "/oauth2/sign_in?rd=%2Fportal%2Fsystem").strip()
    if not switch_portal_url:
        switch_portal_url = "/oauth2/sign_in?rd=%2Fportal%2Fsystem"
    return {
        "tool_tabs": TOOL_TABS,
        "active_tool": active_tool,
        "active_tool_id": str(active_tool.get("tool_id") or "") if active_tool else "",
        "service_nav": build_service_nav(ACTIVE_PRIVATE_CONFIG, active_service=active_service),
        "active_service": active_service,
        "active_service_tab": active_service_tab,
        "network_tabs": build_network_tabs(active_service_tab),
        "sidebar_progeny": sidebar_progeny,
        "portal_name": portal_name,
        "active_portal_username": active_portal_username,
        "sign_out_url": sign_out_url,
        "switch_portal_url": switch_portal_url,
        "current_path": current_path,
        "context_sidebar_sections": _context_sidebar_sections(active_service),
    }


@app.get("/portal/static/icons/<path:relpath>")
def portal_static_icons(relpath: str):
    token = str(relpath or "").strip().replace("\\", "/")
    rel = Path(token)
    if not token or rel.is_absolute() or ".." in rel.parts:
        abort(404)
    if rel.suffix.lower() != ".svg":
        abort(404)

    def _resolve_candidate(candidate_rel: Path) -> Path | None:
        try:
            candidate = (ICONS_DIR / candidate_rel).resolve()
            candidate.relative_to(ICONS_DIR.resolve())
        except Exception:
            return None
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    resolved = _resolve_candidate(rel)
    if resolved is None:
        # Backward-compatible lookup for prior foldered relpaths when icons are now flat.
        base = rel.name
        matches = [path for path in ICONS_DIR.rglob(base) if path.is_file()]
        if len(matches) == 1:
            resolved = matches[0].resolve()

    if resolved is None:
        abort(404)

    try:
        resolved.relative_to(ICONS_DIR.resolve())
    except Exception:
        abort(404)
    return send_from_directory(ICONS_DIR, resolved.relative_to(ICONS_DIR.resolve()).as_posix(), mimetype="image/svg+xml")


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": BASE_DIR.name})


def _ensure_runtime_dirs() -> None:
    workspace_root()
    (PRIVATE_DIR / "request_log").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "cache" / "workspaces" / "board").mkdir(parents=True, exist_ok=True)
    _seed_missing_local_progeny_profiles()


def _normalize_board_tab(value: str) -> str:
    tab = (value or "").strip().lower()
    return tab if tab in set(_board_tabs()) else "feed"


def _format_ts_label(ts_unix_ms: Any) -> str:
    try:
        ts = int(ts_unix_ms)
    except Exception:
        return "unknown time"
    dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _stream_rows() -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    allowed_types = _feed_allowed_types()
    for event in reversed(read_events("feed", limit=200)):
        event_type = str(event.get("type") or "").strip()
        if event_type not in allowed_types:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        rows.append(
            {
                "id": str(event.get("id") or ""),
                "type": event_type,
                "author_msn_id": str(event.get("author_msn_id") or "").strip(),
                "ts_unix_ms": int(event.get("ts_unix_ms") or 0),
                "ts_label": _format_ts_label(event.get("ts_unix_ms")),
                "payload": {
                    "title": str(payload.get("title") or "").strip(),
                    "text": str(payload.get("text") or "").strip(),
                },
            }
        )
    return rows


def _calendar_rows() -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    allowed_types = _calendar_allowed_types()
    for event in read_events("calendar", limit=400):
        event_type = str(event.get("type") or "").strip()
        if event_type not in allowed_types:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        rows.append(
            {
                "id": str(event.get("id") or ""),
                "type": event_type,
                "author_msn_id": str(event.get("author_msn_id") or "").strip(),
                "ts_unix_ms": int(event.get("ts_unix_ms") or 0),
                "ts_label": _format_ts_label(event.get("ts_unix_ms")),
                "payload": {
                    "title": str(payload.get("title") or "").strip(),
                    "start_iso": str(payload.get("start_iso") or "").strip(),
                    "end_iso": str(payload.get("end_iso") or "").strip(),
                    "location": str(payload.get("location") or "").strip(),
                    "notes": str(payload.get("notes") or "").strip(),
                },
            }
        )

    rows.sort(key=lambda row: row["payload"]["start_iso"] or "9999-99-99T99:99:99Z")
    return rows


def _append_workspace_audit(event_type: str, payload: Dict[str, Any]) -> None:
    safe_payload = dict(payload)
    safe_payload["type"] = event_type
    append_request_log_event(PRIVATE_DIR, MSN_ID or _infer_local_msn_id() or PORTAL_INSTANCE_ID, safe_payload)


def _board_redirect(member_msn_id: str, as_alias_id: str, tab: str, theme: str, *, status: str = "", error: str = ""):
    query: Dict[str, str] = {
        "member_msn_id": member_msn_id,
        "tab": _normalize_board_tab(tab),
    }
    if as_alias_id:
        query["as_alias_id"] = as_alias_id
    if theme:
        query["theme"] = theme
    if status:
        query["status"] = status
    if error:
        query["error"] = error
    return redirect(f"/portal/embed/board_member?{urlencode(query)}")


_ensure_runtime_dirs()


@app.get("/<msn_id>.json")
def public_contact_card(msn_id: str):
    path = _resolve_public_profile_path(msn_id)
    if not path:
        abort(404, description=f"No public profile JSON found for msn_id={msn_id}")

    payload = _sanitize_public_profile(_read_json(path))
    payload["options_public"] = _options_public(msn_id)
    return jsonify(payload)


@app.route("/<msn_id>.json", methods=["OPTIONS"])
def public_contact_card_options(msn_id: str):
    resp = make_response(jsonify({"msn_id": msn_id, "options_public": _options_public(msn_id)}), 200)
    resp.headers["Allow"] = "GET, OPTIONS"
    return resp


def _tools_by_mount_target(mount_target: str) -> list[Dict[str, Any]]:
    token = str(mount_target or "").strip().lower()
    return [tool for tool in TOOL_TABS if str(tool.get("mount_target") or "peripherals.tools").strip().lower() == token]


def _render_portal_system():
    aliases = list_aliases_for_sidebar(PRIVATE_DIR)
    profile_model = _portal_profile_model()
    return render_template(
        "services/system.html",
        aliases=aliases,
        msn_id=MSN_ID,
        data_home_available=DATA_HOME_AVAILABLE,
        portal_profile=profile_model,
        system_profile_json=json.dumps(profile_model.get("public_profile") or {}, indent=2, sort_keys=True),
    )


def _normalize_network_view(raw: str) -> str:
    token = str(raw or "").strip().lower()
    if token in {"alias", "log", "p2p"}:
        return token
    return "alias"


@app.get("/portal/system")
def portal_system_page():
    return _render_portal_system()


@app.get("/portal/home")
def portal_home_page():
    return redirect("/portal/system", code=302)


@app.get("/portal")
def portal_home():
    return redirect("/portal/system", code=302)


@app.get("/portal/vault")
def portal_vault():
    return redirect("/portal/peripherals?tab=vault", code=302)


@app.get("/portal/data")
def portal_data():
    return redirect("/portal/system", code=302)


@app.get("/portal/data/<path:tab_id>")
def portal_data_legacy(tab_id: str):
    _ = tab_id
    return redirect("/portal/system", code=302)


@app.get("/portal/network")
def portal_network_default():
    view = _normalize_network_view(request.args.get("view"))
    selected_id = str(request.args.get("id") or "").strip()
    aliases = _network_sidebar_alias_items()
    log_channels = _request_log_channels()
    p2p_channels = _p2p_channels()

    selected_alias = next((item for item in aliases if item["id"] == selected_id), None) if view == "alias" else None
    selected_log = next((item for item in log_channels if item["id"] == selected_id), None) if view == "log" else None
    selected_p2p = next((item for item in p2p_channels if item["id"] == selected_id), None) if view == "p2p" else None

    if not selected_id:
        if view == "alias" and aliases:
            return redirect(aliases[0]["href"], code=302)
        if view == "log" and log_channels:
            return redirect(log_channels[0]["href"], code=302)
        if view == "p2p" and p2p_channels:
            return redirect(p2p_channels[0]["href"], code=302)

    profile_model = _portal_profile_model()
    geography_model = build_property_geography_model(ACTIVE_PRIVATE_CONFIG, DATA_DIR)
    return render_template(
        "services/network.html",
        aliases=list_aliases_for_sidebar(PRIVATE_DIR),
        msn_id=MSN_ID,
        network_view=view,
        selected_alias=selected_alias,
        selected_log=selected_log,
        selected_p2p=selected_p2p,
        network_profile_json=json.dumps(profile_model.get("public_profile") or {}, indent=2, sort_keys=True),
        network_config_json=json.dumps(ACTIVE_PRIVATE_CONFIG, indent=2, sort_keys=True),
        property_geography=geography_model,
    )


@app.get("/portal/network/<tab_id>")
def portal_network(tab_id: str):
    token = normalize_network_tab(tab_id)
    if token in {"aliases", "profile", "alias", "provisions"}:
        return redirect("/portal/network?view=alias", code=302)
    if token in {"logs", "contracts"}:
        return redirect("/portal/network?view=log", code=302)
    return redirect("/portal/network?view=p2p", code=302)


@app.get("/portal/utilities")
def portal_utilities():
    tab = str(request.args.get("tab") or "inbox").strip().lower()
    if tab not in {"inbox", "launchers"}:
        tab = "inbox"
    return render_template(
        "services/utilities.html",
        aliases=list_aliases_for_sidebar(PRIVATE_DIR),
        msn_id=MSN_ID,
        utilities_tab=tab,
        request_log_summary=_request_log_summary(),
        utility_tools=_tools_by_mount_target("utilities"),
    )


@app.get("/portal/peripherals")
def portal_peripherals():
    tab = str(request.args.get("tab") or "peripherals").strip().lower()
    if tab not in {"tools", "peripherals", "progeny", "configuration", "vault"}:
        tab = "peripherals"
    cards = build_network_cards(PRIVATE_DIR, ACTIVE_PRIVATE_CONFIG)
    return render_template(
        "services/peripherals.html",
        aliases=list_aliases_for_sidebar(PRIVATE_DIR),
        msn_id=MSN_ID,
        peripherals_tab=tab,
        peripheral_tools=_tools_by_mount_target("peripherals.tools"),
        provision_progeny_items=cards.get("progeny", []),
        provision_alias_items=cards.get("alias", []),
        contract_items=cards.get("contracts", []),
        request_log_summary=_request_log_summary(),
        configuration_json=json.dumps(ACTIVE_PRIVATE_CONFIG, indent=2, sort_keys=True),
        vault_refs=_collect_vault_refs(ACTIVE_PRIVATE_CONFIG),
        vault_contract_files=_vault_contract_files(),
        keypass_db_path=str(PRIVATE_DIR / "vault" / "keypass.kdbx"),
    )


@app.get("/portal/peripheral")
def portal_peripheral():
    return redirect("/portal/peripherals?tab=peripherals", code=302)


@app.get("/portal/tools")
def portal_tools():
    return redirect("/portal/peripherals?tab=tools", code=302)


@app.get("/portal/inbox")
def portal_inbox_page():
    return redirect("/portal/utilities?tab=inbox", code=302)


@app.route("/portal", methods=["OPTIONS"])
def portal_options():
    resp = make_response("", 204)
    resp.headers["Allow"] = "GET, OPTIONS"
    return resp


@app.get("/portal/alias/<alias_id>")
def portal_alias_session(alias_id: str):
    aliases = list_aliases_for_sidebar(PRIVATE_DIR)
    try:
        alias_payload = get_alias_record(PRIVATE_DIR, alias_id)
    except (FileNotFoundError, ValueError):
        abort(404, description=f"No alias record found for alias_id={alias_id}")

    tenant_id = str(alias_payload.get("child_msn_id") or alias_payload.get("tenant_id") or "").strip()
    progeny_type = str(alias_payload.get("progeny_type") or "").strip().lower()

    return render_template(
        "alias_shell.html",
        aliases=aliases,
        active_alias_id=alias_id,
        alias_label=_alias_label(alias_payload, alias_id),
        org_title=str(alias_payload.get("host_title") or "").strip(),
        org_msn_id=str(alias_payload.get("alias_host") or "").strip(),
        org_widget_url=_build_widget_url(alias_id, alias_payload),
        msn_id=str(alias_payload.get("msn_id") or "").strip() or MSN_ID,
        alias_progeny_type=progeny_type,
        alias_tenant_id=tenant_id,
    )


@app.get("/portal/embed/poc")
def portal_embed_poc():
    org_msn_id = (request.args.get("org_msn_id") or "").strip()
    as_alias_id = (request.args.get("as_alias_id") or "").strip()
    org_title = (request.args.get("org_title") or "").strip()
    if not org_title and org_msn_id:
        org_title = f"Organization {org_msn_id}"

    return render_template(
        "embed_poc.html",
        org_msn_id=org_msn_id,
        as_alias_id=as_alias_id,
        org_title=org_title,
    )


@app.get("/portal/embed/progeny")
def portal_embed_progeny():
    aliases = list_aliases_for_sidebar(PRIVATE_DIR)
    records, _ = list_alias_records(PRIVATE_DIR)
    member_msn_id = (request.args.get("member_msn_id") or "").strip()
    as_alias_id = (request.args.get("as_alias_id") or "").strip()
    portal_title = str(
        ACTIVE_PRIVATE_CONFIG.get("title")
        or ACTIVE_PRIVATE_CONFIG.get("portal_title")
        or MSN_ID
        or PORTAL_INSTANCE_ID
    ).strip()

    landing = build_embed_progeny_landing(
        private_dir=PRIVATE_DIR,
        alias_records=records,
        member_msn_id=member_msn_id,
        as_alias_id=as_alias_id,
        alias_label_builder=_alias_label,
        widget_url_builder=_build_widget_url,
        portal_instance_id=PORTAL_INSTANCE_ID,
        portal_title=portal_title,
        msn_id=MSN_ID,
        active_private_config=ACTIVE_PRIVATE_CONFIG,
    )
    return render_template(
        "embed_progeny.html",
        aliases=aliases,
        msn_id=MSN_ID,
        member_msn_id=member_msn_id,
        as_alias_id=as_alias_id,
        cards=landing.get("cards", []),
        warnings=landing.get("warnings", []),
        broadcast=landing.get("broadcast", {}),
    )


@app.get("/portal/embed/board_member")
def portal_embed_board_member():
    member_msn_id = (request.args.get("member_msn_id") or "").strip()
    if not member_msn_id:
        abort(400, description="Missing required query param: member_msn_id")
    require_board_member(member_msn_id)

    as_alias_id = (request.args.get("as_alias_id") or "").strip()
    requested_tab = (request.args.get("tab") or "").strip().lower()
    theme = (request.args.get("theme") or "").strip()

    status_token = (request.args.get("status") or "").strip().lower()
    error_message = (request.args.get("error") or "").strip()
    if requested_tab == "streams":
        return _board_redirect(
            member_msn_id,
            as_alias_id,
            "feed",
            theme,
            status=status_token,
            error=error_message,
        )
    if requested_tab == "workflow" and not _workflow_enabled():
        return _board_redirect(
            member_msn_id,
            as_alias_id,
            "feed",
            theme,
            error="workflow tab is not enabled for this portal.",
        )
    active_tab = _normalize_board_tab(requested_tab)

    status_message = ""
    status_level = "warn"
    if status_token == "post_saved":
        status_message = "Post saved to shared board feed."
        status_level = "success"
    elif status_token == "event_saved":
        status_message = "Calendar event saved to shared board calendar."
        status_level = "success"
    elif error_message:
        status_message = error_message
        status_level = "warn"

    return render_template(
        "board_member_embed_shell.html",
        member_msn_id=member_msn_id,
        as_alias_id=as_alias_id,
        active_tab=active_tab,
        board_tabs=_board_tabs(),
        workspace_title=f"{str(ACTIVE_PRIVATE_CONFIG.get('title') or ACTIVE_PRIVATE_CONFIG.get('portal_title') or MSN_ID or 'Portal')} Board Workspace",
        feed_rows=_stream_rows(),
        calendar_events=_calendar_rows(),
        people=materialize_people(),
        workflow_model=_workflow_model(),
        theme=theme,
        status_message=status_message,
        status_level=status_level,
    )


@app.post("/portal/embed/board_member/feed/post")
@app.post("/portal/embed/board_member/streams/post")
def portal_embed_board_member_feed_post():
    member_msn_id = (request.form.get("member_msn_id") or "").strip()
    as_alias_id = (request.form.get("as_alias_id") or "").strip()
    theme = (request.form.get("theme") or "").strip()
    require_board_member(member_msn_id)

    post_text = (request.form.get("post_text") or "").strip()
    post_title = (request.form.get("post_title") or "").strip()
    post_type = (request.form.get("post_type") or "post.create").strip()
    if not post_text:
        return _board_redirect(member_msn_id, as_alias_id, "feed", theme, error="Post text is required.")
    if post_type not in _feed_allowed_types():
        return _board_redirect(member_msn_id, as_alias_id, "feed", theme, error=f"post_type not allowed: {post_type}")

    event_payload = {"text": post_text}
    if post_title:
        event_payload["title"] = post_title

    append_workspace_event(
        "feed",
        {
            "id": str(uuid.uuid4()),
            "ts_unix_ms": int(time.time() * 1000),
            "author_msn_id": member_msn_id,
            "type": post_type,
            "payload": event_payload,
        },
    )
    _append_workspace_audit(
        "workspace.feed.post.created",
        {
            "member_msn_id": member_msn_id,
            "as_alias_id": as_alias_id,
            "title": post_title,
            "post_type": post_type,
            "text_len": len(post_text),
        },
    )
    return _board_redirect(member_msn_id, as_alias_id, "feed", theme, status="post_saved")


@app.post("/portal/embed/board_member/calendar/event")
def portal_embed_board_member_calendar_event():
    member_msn_id = (request.form.get("member_msn_id") or "").strip()
    as_alias_id = (request.form.get("as_alias_id") or "").strip()
    theme = (request.form.get("theme") or "").strip()
    require_board_member(member_msn_id)

    title = (request.form.get("title") or "").strip()
    start_iso = (request.form.get("start_iso") or "").strip()
    end_iso = (request.form.get("end_iso") or "").strip()
    location = (request.form.get("location") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    event_type = (request.form.get("event_type") or "meeting").strip()

    if not title or not start_iso or not end_iso:
        return _board_redirect(
            member_msn_id,
            as_alias_id,
            "calendar",
            theme,
            error="title, start_iso, and end_iso are required.",
        )
    if event_type not in _calendar_allowed_types():
        return _board_redirect(
            member_msn_id,
            as_alias_id,
            "calendar",
            theme,
            error=f"event_type not allowed: {event_type}",
        )

    append_workspace_event(
        "calendar",
        {
            "id": str(uuid.uuid4()),
            "ts_unix_ms": int(time.time() * 1000),
            "author_msn_id": member_msn_id,
            "type": event_type,
            "payload": {
                "title": title,
                "start_iso": start_iso,
                "end_iso": end_iso,
                "location": location,
                "notes": notes,
            },
        },
    )
    _append_workspace_audit(
        "workspace.calendar.event.created",
        {
            "member_msn_id": member_msn_id,
            "as_alias_id": as_alias_id,
            "title": title,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "location": location,
            "event_type": event_type,
        },
    )
    return _board_redirect(member_msn_id, as_alias_id, "calendar", theme, status="event_saved")


register_aliases_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_data_routes(
    app,
    workspace=DATA_WORKSPACE,
    aliases_provider=lambda: list_aliases_for_sidebar(PRIVATE_DIR),
    options_private_fn=_options_private,
    msn_id_provider=lambda: MSN_ID,
    include_home_redirect=False,
    include_legacy_shims=True,
)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
