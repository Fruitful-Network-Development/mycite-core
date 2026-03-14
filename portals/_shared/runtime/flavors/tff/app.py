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
from portal.api.contract_handshake import register_contract_handshake_routes
from portal.api.data_workspace import register_data_routes
from portal.api.inbox import register_inbox_routes
from portal.api.request_log import register_request_log_routes
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
from portal.services.runtime_paths import (
    hosted_read_paths,
    keypass_db_path,
    keypass_inventory_path,
    request_log_read_paths,
    request_log_types_dir,
    utility_peripherals_dir,
    vault_contract_read_dirs,
)
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
def _resolve_portals_root() -> Path:
    override = str(os.environ.get("MYCITE_PORTALS_ROOT") or "").strip()
    if override:
        return Path(override)
    for candidate in (BASE_DIR, *BASE_DIR.parents):
        if (candidate / "assets").exists() and (candidate / "_shared").exists():
            return candidate
    return BASE_DIR.parent


PUBLIC_DIR = Path(os.environ.get("PUBLIC_DIR", str(BASE_DIR / "public")))
PRIVATE_DIR = Path(os.environ.get("PRIVATE_DIR", str(BASE_DIR / "private")))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
FALLBACK_DIR = BASE_DIR
REPO_ROOT = _resolve_portals_root()
ICONS_DIR = REPO_ROOT / "assets" / "icons"
PORTAL_INSTANCE_ID = str(os.environ.get("PORTAL_INSTANCE_ID") or BASE_DIR.name).strip().lower()
PORTAL_RUNTIME_FLAVOR = str(os.environ.get("PORTAL_RUNTIME_FLAVOR") or PORTAL_INSTANCE_ID or BASE_DIR.name).strip().lower()
IS_TFF_PORTAL = PORTAL_RUNTIME_FLAVOR == "tff" or "tff" in PORTAL_RUNTIME_FLAVOR
PORTAL_ENTRY_PATH = (
    str(os.environ.get("PORTAL_ENTRY_PATH") or ("/portal/tff" if IS_TFF_PORTAL else "/portal/fnd")).strip()
    or ("/portal/tff" if IS_TFF_PORTAL else "/portal/fnd")
)
DEFAULT_EMBED_PORT = str(os.environ.get("DEFAULT_EMBED_PORT") or "5201").strip() or "5201"
FND_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
TFF_MSN_ID = "3-2-3-17-77-2-6-3-1-6"
KNOWN_EMBED_PORT_BY_MSN = {
    FND_MSN_ID: "5101",
    TFF_MSN_ID: "5203",
}
DEFAULT_FEED_TYPES = {"post.create", "board_notice"}
DEFAULT_CALENDAR_TYPES = {"meeting", "group_event", "committee_meeting"}
ALIAS_EXPECTED_BY_TYPE = {
    "admin": True,
    "member": False,
    "user": False,
}
DEFAULT_PROFILE_SOURCE_PRIORITY = ["progeny.internal", "progeny.config_ref", "alias"]
LEGAL_ENTITY_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "discovery_engine.json": {
        "schema": "mycite.legal_entity_type.v1",
        "type": "discovery_engine",
        "title": "Discovery Engine",
        "role_groups": {"admins": [], "members": [], "users": []},
    },
    "social_network.json": {
        "schema": "mycite.legal_entity_type.v1",
        "type": "social_network",
        "title": "Social Network",
        "role_groups": {"admins": [], "members": [], "users": []},
    },
    "subject_congregation.json": {
        "schema": "mycite.legal_entity_type.v1",
        "type": "subject_congregation",
        "title": "Subject Congregation",
        "role_groups": {"admins": [], "members": [], "users": []},
        "workflow_defaults": {"farm_fields": [], "committees": []},
    },
}


def _canonical_progeny_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if token in {"board_member", "constituent_farm", "tenant"}:
        return "member"
    if token == "poc":
        return "admin"
    return token


def _default_portal_sign_out_url() -> str:
    encoded_target = quote(PORTAL_ENTRY_PATH, safe="")
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


def _resolve_fnd_profile_path(msn_id: str) -> Optional[Path]:
    token = str(msn_id or "").strip()
    if not token:
        return None
    return _find_first([PUBLIC_DIR / f"fnd-{token}.json", FALLBACK_DIR / f"fnd-{token}.json"])


def _sanitize_public_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"msn_id", "schema", "title", "public_key", "entity_type", "accessible"}
    out = {k: payload.get(k) for k in allowed if k in payload}
    out.setdefault("accessible", {})
    return out


def _sanitize_fnd_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"schema", "msn_id", "title", "summary", "logo", "banner", "links"}
    out = {key: payload.get(key) for key in allowed if key in payload}
    links = payload.get("links") if isinstance(payload.get("links"), list) else []
    out["links"] = [item for item in links if isinstance(item, dict)]
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
        "inbox": {
            "href": f"/portal/api/inbox?msn_id={msn_id}",
            "methods": ["GET", "POST", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
        "request_log": {
            "href": "/portal/api/request_log",
            "methods": ["POST", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
        "contract_request": {
            "href": "/portal/api/network/contracts/request",
            "methods": ["POST", "OPTIONS"],
            "auth": "keycloak_or_local",
            "qualifier": "asymmetric",
        },
        "network_anonymous_options": {
            "href": f"/api/network/anonymous/options/{msn_id}",
            "methods": ["GET", "OPTIONS"],
            "auth": "none",
            "qualifier": "anonymous",
        },
        "network_anonymous_contact": {
            "href": f"/api/network/anonymous/contact/{msn_id}",
            "methods": ["GET", "OPTIONS"],
            "auth": "none",
            "qualifier": "anonymous",
        },
        "network_asymmetric_contract_ingress": {
            "href": f"/api/network/asymmetric/contracts/request/{msn_id}",
            "methods": ["POST", "OPTIONS"],
            "auth": "signed_envelope",
            "qualifier": "asymmetric",
            "compat_shim": f"/api/contracts/request/{msn_id}",
        },
        "network_asymmetric_confirmation_ingress": {
            "href": f"/api/network/asymmetric/contracts/confirmation/{msn_id}",
            "methods": ["POST", "OPTIONS"],
            "auth": "signed_envelope",
            "qualifier": "asymmetric",
            "compat_shim": f"/api/contracts/confirmation/{msn_id}",
        },
        "network_symmetric_contract_due": {
            "href": "/portal/api/network/symmetric/contracts/due",
            "methods": ["GET", "OPTIONS"],
            "auth": "keycloak_or_local",
            "qualifier": "symmetric",
        },
        "network_symmetric_contract_renew": {
            "href": "/portal/api/network/symmetric/contracts/<contract_id>/renew",
            "methods": ["POST", "OPTIONS"],
            "auth": "keycloak_or_local",
            "qualifier": "symmetric",
        },
        "network_symmetric_contract_ingress": {
            "href": "/api/network/symmetric/contracts/<contract_id>/renew/<msn_id>",
            "methods": ["POST", "OPTIONS"],
            "auth": "vault_symmetric",
            "qualifier": "symmetric",
        },
        "network_contacts_collection": {
            "href": "/portal/api/network/contacts/collection?alias_id=<alias_id>",
            "methods": ["GET", "OPTIONS"],
            "auth": "keycloak_or_local",
            "qualifier": "anonymous",
        },
        "network_daemon_resolve_references": {
            "href": "/portal/api/network/daemon/resolve_references",
            "methods": ["POST", "OPTIONS"],
            "auth": "keycloak_or_local",
            "qualifier": "anonymous",
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
        known = KNOWN_EMBED_PORT_BY_MSN.get(host)
        if known:
            return known

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

    progeny_type = _canonical_progeny_type(str(alias_payload.get("progeny_type") or "").strip().lower())
    tenant_msn_id = _extract_tenant_msn_id(alias_payload)
    member_msn_id = _extract_member_msn_id(alias_payload)
    if progeny_type == "member" and member_msn_id:
        target_path = "/portal/embed/board_member"
        tab = "feed"
        if org_msn_id and MSN_ID and org_msn_id != MSN_ID:
            target_path = "/portal/embed/member_workbench"
            tab = "stream"
        query = urlencode({"member_msn_id": member_msn_id, "as_alias_id": alias_id, "tab": tab})
        return f"{base_url}{target_path}?{query}"

    query = urlencode({"org_msn_id": org_msn_id, "as_alias_id": alias_id, "org_title": org_title})
    return f"{base_url}/portal/embed/poc?{query}"


def _alias_contact_collection_ref(record: Dict[str, Any]) -> str:
    profile_refs = record.get("profile_refs") if isinstance(record.get("profile_refs"), dict) else {}
    alias_ref = str(profile_refs.get("contact_collection_ref") or "").strip()
    if alias_ref:
        return alias_ref

    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    return str(fields.get("contact_collection_ref") or "").strip()


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
                "contract_id": str(record.get("contract_id") or "").strip(),
                "progeny_type": _canonical_progeny_type(str(record.get("progeny_type") or "").strip()),
                "tenant_id": str(record.get("child_msn_id") or record.get("tenant_id") or "").strip(),
                "member_id": _extract_member_msn_id(record),
                "contact_collection_ref": _alias_contact_collection_ref(record),
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
        "role_groups": {"admins": [], "members": [], "users": []},
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
        legal_defaults["role_groups"] = {"admins": [], "members": [], "users": []}
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
    out: list[str] = []
    seen: set[str] = set()
    for root in vault_contract_read_dirs(PRIVATE_DIR):
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob("*")):
            if not path.is_file() or path.name in seen:
                continue
            seen.add(path.name)
            out.append(path.name)
    return out


def _iter_request_log_records() -> list[Dict[str, Any]]:
    msn_id = str(MSN_ID or _infer_local_msn_id() or "").strip()
    paths = [path for path in request_log_read_paths(PRIVATE_DIR, msn_id or None) if path.exists() and path.is_file()]
    records: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for line in lines:
            token = line.strip()
            if not token:
                continue
            try:
                payload = json.loads(token)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            record_msn_id = str(payload.get("msn_id") or "").strip()
            if msn_id and record_msn_id and record_msn_id != msn_id:
                continue
            dedupe_key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            records.append(payload)
    return records


def _normalize_network_query_tab(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"messages", "hosted", "profile"} else "messages"


def _normalize_network_kind(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"alias", "log", "p2p"} else "alias"


def _normalize_utilities_tab(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"tools", "vault", "peripherals"} else "tools"


def _normalize_hosted_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": "unknown", "type_values": {}, "raw": {}}
    hosted_type = str(payload.get("type") or payload.get("hosted_type") or "unknown").strip() or "unknown"
    if isinstance(payload.get("type_values"), dict):
        type_values = dict(payload.get("type_values") or {})
    else:
        type_values = {}
        default_hosted = payload.get("default_hosted")
        if isinstance(default_hosted, list):
            type_values["default_hosted"] = default_hosted
        addendum = payload.get("addendum")
        if isinstance(addendum, dict):
            for key, value in addendum.items():
                type_values[key] = value
    return {"type": hosted_type, "type_values": type_values, "raw": payload}


def _read_hosted_payload() -> Dict[str, Any]:
    for path in hosted_read_paths(PRIVATE_DIR):
        if not path.exists() or not path.is_file():
            continue
        try:
            payload = _read_json(path)
        except Exception:
            continue
        normalized = _normalize_hosted_payload(payload)
        normalized["path"] = str(path)
        return normalized
    return {"type": "unknown", "type_values": {}, "raw": {}, "path": str(hosted_read_paths(PRIVATE_DIR)[0])}


def _utility_tool_items() -> list[Dict[str, Any]]:
    seen: set[str] = set()
    out: list[Dict[str, Any]] = []
    for mount_target in ("utilities", "peripherals.tools"):
        for tool in _tools_by_mount_target(mount_target):
            home_path = str(tool.get("home_path") or "").strip()
            if not home_path or home_path in seen:
                continue
            seen.add(home_path)
            out.append(tool)
    return out


def _utility_peripheral_entries() -> list[Dict[str, Any]]:
    root = utility_peripherals_dir(PRIVATE_DIR)
    if not root.exists() or not root.is_dir():
        return []
    out: list[Dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        out.append({"name": path.name, "kind": "directory" if path.is_dir() else "file", "path": str(path)})
    return out


def _default_vault_inventory() -> Dict[str, Any]:
    return {"schema": "mycite.utilities.vault.inventory.v1", "entries": []}


def _load_vault_inventory() -> Dict[str, Any]:
    path = keypass_inventory_path(PRIVATE_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_file():
        try:
            payload = _read_json(path)
        except Exception:
            payload = _default_vault_inventory()
    else:
        payload = _default_vault_inventory()
        _write_json(path, payload)
    if not isinstance(payload.get("entries"), list):
        payload["entries"] = []
    return payload


def _write_vault_inventory(payload: Dict[str, Any]) -> Path:
    path = keypass_inventory_path(PRIVATE_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, payload)
    return path


def _portal_profile_model() -> Dict[str, Any]:
    local_msn_id = str(MSN_ID or _infer_local_msn_id() or "").strip()
    public_profile: Dict[str, Any] = {}
    fnd_profile: Dict[str, Any] = {}
    if local_msn_id:
        profile_path = _resolve_public_profile_path(local_msn_id)
        if profile_path and profile_path.exists():
            try:
                public_profile = _sanitize_public_profile(_read_json(profile_path))
            except Exception:
                public_profile = {}
        fnd_profile_path = _resolve_fnd_profile_path(local_msn_id)
        if fnd_profile_path and fnd_profile_path.exists():
            try:
                fnd_profile = _sanitize_fnd_profile(_read_json(fnd_profile_path))
            except Exception:
                fnd_profile = {}

    config_file = active_private_config_filename(PRIVATE_DIR, MSN_ID or None)

    return {
        "msn_id": local_msn_id,
        "public_profile": public_profile,
        "options_public": _options_public(local_msn_id) if local_msn_id else {},
        "fnd_profile": fnd_profile,
        "config_file": config_file,
    }


def _request_log_summary() -> Dict[str, Any]:
    paths = [path for path in request_log_read_paths(PRIVATE_DIR, MSN_ID or None) if path.exists() and path.is_file()]
    return {"file_count": len(paths), "event_count": len(_iter_request_log_records())}


def _request_log_channels() -> list[Dict[str, Any]]:
    event_count = len(_iter_request_log_records())
    return [{"id": "request_log", "label": "request_log", "event_count": event_count, "href": "/portal/network?tab=messages&kind=log&id=request_log"}]


def _p2p_channels() -> list[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for payload in _iter_request_log_records():
        tx = str(payload.get("transmitter") or "").strip()
        rx = str(payload.get("receiver") or "").strip()
        if not tx or not rx:
            continue
        channel_id = f"{tx}->{rx}"
        counts[channel_id] = counts.get(channel_id, 0) + 1

    out: list[Dict[str, Any]] = []
    for channel_id, event_count in sorted(counts.items(), key=lambda item: item[0].lower()):
        out.append(
            {
                "id": channel_id,
                "label": channel_id,
                "event_count": event_count,
                "href": f"/portal/network?tab=messages&kind=p2p&id={quote(channel_id, safe='')}",
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
                "tenant_id": str(alias.get("tenant_id") or "").strip(),
                "contract_id": str(alias.get("contract_id") or "").strip(),
                "contact_collection_ref": str(alias.get("contact_collection_ref") or "").strip(),
                "href": f"/portal/network?tab=messages&kind=alias&id={quote(alias_id, safe='')}",
                "alias_id": alias_id,
                "alias_label": str(alias.get("label") or alias_id).strip(),
            }
        )
    return out


def _iter_string_values(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_string_values(nested)
        return
    if isinstance(value, list):
        for nested in value:
            yield from _iter_string_values(nested)
        return
    if value is None:
        return
    token = str(value).strip()
    if token:
        yield token


def _event_contains_any(event: Dict[str, Any], tokens: list[str]) -> bool:
    needles = [str(item).strip().lower() for item in tokens if str(item).strip()]
    if not needles:
        return False
    for value in _iter_string_values(event):
        lowered = value.lower()
        if any(needle in lowered for needle in needles):
            return True
    return False


def _event_channel_id(event: Dict[str, Any]) -> str:
    transmitter = str(event.get("transmitter") or "").strip()
    receiver = str(event.get("receiver") or "").strip()
    if transmitter and receiver:
        return f"{transmitter}->{receiver}"
    return ""


def _format_event_timestamp(ts_unix_ms: Any) -> str:
    try:
        stamp = int(ts_unix_ms or 0)
    except Exception:
        return ""
    if stamp <= 0:
        return ""
    try:
        return datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ""


def _initials(token: str, fallback: str = "NW") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", str(token or "").strip())
    parts = [part for part in cleaned.split() if part]
    if not parts:
        return fallback
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[1][0]}".upper()


def _event_actor_label(event: Dict[str, Any]) -> str:
    transmitter = str(event.get("transmitter") or "").strip()
    receiver = str(event.get("receiver") or "").strip()
    if transmitter:
        if MSN_ID and MSN_ID in transmitter:
            return "Current Portal"
        return transmitter
    if receiver:
        return receiver
    return "Network Event"


def _event_summary(event: Dict[str, Any]) -> str:
    summary_parts: list[str] = []
    for key in ("status", "receiver", "alias_id", "contract_id", "tenant_msn_id", "client_id", "event_datum"):
        value = str(event.get(key) or "").strip()
        if value:
            summary_parts.append(f"{key}: {value}")
    details = event.get("details")
    if isinstance(details, dict) and details:
        summary_parts.append("details: " + ", ".join(sorted(str(key) for key in details.keys())[:4]))
    return " | ".join(summary_parts[:4])


def _network_placeholder_item(kind: str, selected: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    label = str((selected or {}).get("label") or "conversation").strip()
    if kind == "alias":
        headline = "Interface ready"
        summary = f"No request-log events have been mapped to {label} yet."
    elif kind == "p2p":
        headline = "Direct thread is quiet"
        summary = f"No transmitter/receiver events have been recorded for {label} yet."
    else:
        headline = "Request log ready"
        summary = "No request-log entries have been recorded yet."
    payload = {"selection": selected or {}, "kind": kind}
    return {
        "side": "system",
        "author": "Workbench",
        "avatar": _initials(label, "WB"),
        "role": "preview",
        "headline": headline,
        "summary": summary,
        "timestamp": "",
        "payload_json": json.dumps(payload, indent=2, sort_keys=True),
    }


def _network_message_feed(
    kind: str,
    selected_alias: Optional[Dict[str, Any]],
    selected_log: Optional[Dict[str, Any]],
    selected_p2p: Optional[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    events = _iter_request_log_records()
    filtered: list[Dict[str, Any]]
    selected: Optional[Dict[str, Any]]

    if kind == "alias":
        selected = selected_alias
        tokens = [
            str((selected_alias or {}).get("id") or "").strip(),
            str((selected_alias or {}).get("alias_id") or "").strip(),
            str((selected_alias or {}).get("org_msn_id") or "").strip(),
            str((selected_alias or {}).get("tenant_id") or "").strip(),
            str((selected_alias or {}).get("label") or "").strip(),
        ]
        filtered = [event for event in events if _event_contains_any(event, tokens)]
    elif kind == "p2p":
        selected = selected_p2p
        channel_id = str((selected_p2p or {}).get("id") or "").strip()
        filtered = [event for event in events if _event_channel_id(event) == channel_id]
    else:
        selected = selected_log
        filtered = list(events)

    filtered = sorted(filtered, key=lambda item: int(item.get("ts_unix_ms") or 0))
    if len(filtered) > 60:
        filtered = filtered[-60:]

    if not filtered:
        return [_network_placeholder_item(kind, selected)]

    feed: list[Dict[str, Any]] = []
    for event in filtered:
        transmitter = str(event.get("transmitter") or "").strip()
        side = "system"
        if transmitter:
            side = "outbound" if MSN_ID and MSN_ID in transmitter else "inbound"
        preview_payload = {key: value for key, value in event.items() if key != "msn_id"}
        author = _event_actor_label(event)
        feed.append(
            {
                "side": side,
                "author": author,
                "avatar": _initials(author, "EV"),
                "role": str(event.get("status") or "event").strip(),
                "headline": str(event.get("type") or "event").strip(),
                "summary": _event_summary(event),
                "timestamp": _format_event_timestamp(event.get("ts_unix_ms")),
                "payload_json": json.dumps(preview_payload, indent=2, sort_keys=True),
            }
        )
    return feed


def _context_sidebar_sections(active_service: str) -> list[Dict[str, Any]]:
    token = str(active_service or "system").strip().lower()
    network_tab = _normalize_network_query_tab(request.args.get("tab"))
    kind = _normalize_network_kind(request.args.get("kind"))
    utilities_tab = _normalize_utilities_tab(request.args.get("tab"))
    selected = str(request.args.get("id") or "").strip()

    if token == "network":
        aliases = _network_sidebar_alias_items()
        logs = _request_log_channels()
        p2p = _p2p_channels()
        return [
            {
                "title": "Network Views",
                "entries": [
                    {"label": "Messages", "meta": "aliases / logs / p2p", "href": "/portal/network?tab=messages&kind=alias", "active": network_tab == "messages"},
                    {"label": "Hosted", "meta": "hosted.json", "href": "/portal/network?tab=hosted", "active": network_tab == "hosted"},
                    {"label": "Profile", "meta": "config + public cards", "href": "/portal/network?tab=profile", "active": network_tab == "profile"},
                ],
                "empty_text": "",
            },
            {
                "title": "Alias Interfaces",
                "entries": [
                    {
                        "label": item["label"],
                        "meta": item.get("org_msn_id") or "",
                        "href": item["href"],
                        "active": network_tab == "messages" and kind == "alias" and selected == item["id"],
                    }
                    for item in aliases
                ],
                "empty_text": "No aliases loaded",
            },
            {
                "title": "Request Logs",
                "entries": [
                    {
                        "label": item["label"],
                        "meta": f"{item['event_count']} event(s)",
                        "href": item["href"],
                        "active": network_tab == "messages" and kind == "log" and selected == item["id"],
                    }
                    for item in logs
                ],
                "empty_text": "No request logs found",
            },
            {
                "title": "Direct Messages",
                "entries": [
                    {
                        "label": item["label"],
                        "meta": f"{item['event_count']} event(s)",
                        "href": item["href"],
                        "active": network_tab == "messages" and kind == "p2p" and selected == item["id"],
                    }
                    for item in p2p
                ],
                "empty_text": "No P2P channels derived yet",
            },
        ]

    if token == "utilities":
        return [
            {
                "title": "Utility Views",
                "entries": [
                    {"label": "Tools", "href": "/portal/utilities?tab=tools", "active": utilities_tab == "tools", "meta": "launchers + mounts"},
                    {"label": "Vault", "href": "/portal/utilities?tab=vault", "active": utilities_tab == "vault", "meta": "KeePass inventory"},
                    {"label": "Peripherals", "href": "/portal/utilities?tab=peripherals", "active": utilities_tab == "peripherals", "meta": "runtime directory"},
                ],
                "empty_text": "",
            }
        ]

    return [
        {
            "title": "Profile",
            "entries": [
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
        active_service_tab = _normalize_network_query_tab(request.args.get("tab"))
    elif active_service == "utilities":
        active_service_tab = _normalize_utilities_tab(request.args.get("tab"))
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
                    "href": "/portal/network?tab=profile",
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
    request_log_types_dir(PRIVATE_DIR).parent.mkdir(parents=True, exist_ok=True)
    request_log_types_dir(PRIVATE_DIR).mkdir(parents=True, exist_ok=True)
    utility_peripherals_dir(PRIVATE_DIR).mkdir(parents=True, exist_ok=True)
    keypass_inventory_path(PRIVATE_DIR).parent.mkdir(parents=True, exist_ok=True)
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


@app.get("/fnd-<msn_id>.json")
def public_fnd_profile(msn_id: str):
    path = _resolve_fnd_profile_path(msn_id)
    if not path:
        abort(404, description=f"No FND public profile JSON found for msn_id={msn_id}")
    payload = _sanitize_fnd_profile(_read_json(path))
    payload["options_public"] = _options_public(msn_id)
    return jsonify(payload)


@app.route("/<msn_id>.json", methods=["OPTIONS"])
def public_contact_card_options(msn_id: str):
    resp = make_response(jsonify({"msn_id": msn_id, "options_public": _options_public(msn_id)}), 200)
    resp.headers["Allow"] = "GET, OPTIONS"
    return resp


@app.route("/fnd-<msn_id>.json", methods=["OPTIONS"])
def public_fnd_profile_options(msn_id: str):
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
    return redirect("/portal/utilities?tab=vault", code=302)


@app.get("/portal/data")
def portal_data():
    return redirect("/portal/system", code=302)


@app.get("/portal/data/<path:tab_id>")
def portal_data_legacy(tab_id: str):
    _ = tab_id
    return redirect("/portal/system", code=302)


@app.get("/portal/network")
def portal_network_default():
    tab = _normalize_network_query_tab(request.args.get("tab"))
    kind = _normalize_network_kind(request.args.get("kind"))
    selected_id = str(request.args.get("id") or "").strip()
    aliases = _network_sidebar_alias_items()
    log_channels = _request_log_channels()
    p2p_channels = _p2p_channels()

    selected_alias = next((item for item in aliases if item["id"] == selected_id), None) if tab == "messages" and kind == "alias" else None
    selected_log = next((item for item in log_channels if item["id"] == selected_id), None) if tab == "messages" and kind == "log" else None
    selected_p2p = next((item for item in p2p_channels if item["id"] == selected_id), None) if tab == "messages" and kind == "p2p" else None

    if tab == "messages" and not selected_id:
        if kind == "alias" and aliases:
            return redirect(aliases[0]["href"], code=302)
        if kind == "log" and log_channels:
            return redirect(log_channels[0]["href"], code=302)
        if kind == "p2p" and p2p_channels:
            return redirect(p2p_channels[0]["href"], code=302)

    profile_model = _portal_profile_model()
    geography_model = build_property_geography_model(ACTIVE_PRIVATE_CONFIG, DATA_DIR)
    hosted_payload = _read_hosted_payload()
    message_feed = _network_message_feed(kind, selected_alias, selected_log, selected_p2p)
    return render_template(
        "services/network.html",
        aliases=list_aliases_for_sidebar(PRIVATE_DIR),
        msn_id=MSN_ID,
        network_tab=tab,
        network_kind=kind,
        network_aliases=aliases,
        network_logs=log_channels,
        network_p2p=p2p_channels,
        selected_alias=selected_alias,
        selected_log=selected_log,
        selected_p2p=selected_p2p,
        message_feed=message_feed,
        request_log_summary=_request_log_summary(),
        network_profile_json=json.dumps(profile_model.get("public_profile") or {}, indent=2, sort_keys=True),
        public_profile_json=json.dumps(profile_model.get("public_profile") or {}, indent=2, sort_keys=True),
        fnd_profile_json=json.dumps(profile_model.get("fnd_profile") or {}, indent=2, sort_keys=True),
        network_config_json=json.dumps(ACTIVE_PRIVATE_CONFIG, indent=2, sort_keys=True),
        hosted_payload=hosted_payload,
        hosted_payload_json=json.dumps(hosted_payload, indent=2, sort_keys=True),
        property_geography=geography_model,
    )


@app.get("/portal/network/<tab_id>")
def portal_network(tab_id: str):
    token = str(tab_id or "").strip().lower()
    if token in {"aliases", "alias", "provisions"}:
        return redirect("/portal/network?tab=messages&kind=alias", code=302)
    if token in {"logs", "contracts"}:
        return redirect("/portal/network?tab=messages&kind=log", code=302)
    if token in {"p2p", "messages"}:
        return redirect("/portal/network?tab=messages&kind=p2p", code=302)
    if token == "hosted":
        return redirect("/portal/network?tab=hosted", code=302)
    return redirect("/portal/network?tab=profile", code=302)


@app.get("/portal/utilities")
def portal_utilities():
    tab = _normalize_utilities_tab(request.args.get("tab"))
    inventory = _load_vault_inventory()
    return render_template(
        "services/utilities.html",
        aliases=list_aliases_for_sidebar(PRIVATE_DIR),
        msn_id=MSN_ID,
        utilities_tab=tab,
        request_log_summary=_request_log_summary(),
        utility_tools=_utility_tool_items(),
        peripheral_entries=_utility_peripheral_entries(),
        vault_inventory=inventory,
        vault_inventory_json=json.dumps(inventory, indent=2, sort_keys=True),
        vault_contract_files=_vault_contract_files(),
        keypass_db_path=str(keypass_db_path(PRIVATE_DIR)),
        keypass_inventory_path=str(keypass_inventory_path(PRIVATE_DIR)),
    )


@app.get("/portal/peripherals")
def portal_peripherals():
    legacy_tab = str(request.args.get("tab") or "peripherals").strip().lower()
    if legacy_tab == "tools":
        return redirect("/portal/utilities?tab=tools", code=302)
    if legacy_tab == "vault":
        return redirect("/portal/utilities?tab=vault", code=302)
    if legacy_tab in {"progeny", "configuration"}:
        return redirect("/portal/network?tab=profile", code=302)
    return redirect("/portal/utilities?tab=peripherals", code=302)


@app.get("/portal/peripheral")
def portal_peripheral():
    return redirect("/portal/utilities?tab=peripherals", code=302)


@app.get("/portal/tools")
def portal_tools():
    return redirect("/portal/utilities?tab=tools", code=302)


@app.get("/portal/inbox")
def portal_inbox_page():
    return redirect("/portal/network?tab=messages&kind=log&id=request_log", code=302)


@app.get("/portal/api/utilities/vault/inventory")
def portal_vault_inventory_get():
    return jsonify(_load_vault_inventory())


@app.put("/portal/api/utilities/vault/inventory/<entry_id>")
def portal_vault_inventory_put(entry_id: str):
    token = str(entry_id or "").strip()
    if not token or "/" in token or "\\" in token or ".." in token:
        abort(400, description="entry_id must be a stable identifier")
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")

    inventory = _load_vault_inventory()
    entries = inventory.get("entries") if isinstance(inventory.get("entries"), list) else []
    next_entries: list[Dict[str, Any]] = []
    replaced = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id") or "").strip() != token:
            next_entries.append(entry)
            continue
        merged = dict(entry)
        for key in ("label", "group", "value", "masked", "revealable", "editable", "notes"):
            if key in body:
                merged[key] = body.get(key)
        next_entries.append(merged)
        replaced = True

    if not replaced:
        next_entries.append(
            {
                "id": token,
                "label": str(body.get("label") or token).strip(),
                "group": str(body.get("group") or "").strip(),
                "value": str(body.get("value") or "").strip(),
                "masked": bool(body.get("masked", True)),
                "revealable": bool(body.get("revealable", True)),
                "editable": bool(body.get("editable", True)),
                "notes": str(body.get("notes") or "").strip(),
            }
        )

    inventory["entries"] = next_entries
    written_to = _write_vault_inventory(inventory)
    return jsonify({"ok": True, "written_to": str(written_to), "inventory": inventory})


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
    progeny_type = _canonical_progeny_type(str(alias_payload.get("progeny_type") or "").strip().lower())

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


def _map_member_workbench_tab_to_board(tab: str) -> str:
    token = (tab or "").strip().lower()
    if token == "stream":
        return "feed"
    if token == "classwork":
        return "calendar"
    if token in {"people", "workflow"}:
        return token
    return "feed"


@app.get("/portal/embed/member_workbench")
def portal_embed_member_workbench():
    member_msn_id = (request.args.get("member_msn_id") or "").strip()
    if not member_msn_id:
        abort(400, description="Missing required query param: member_msn_id")
    as_alias_id = (request.args.get("as_alias_id") or "").strip()
    tab = _map_member_workbench_tab_to_board(request.args.get("tab") or "")
    theme = (request.args.get("theme") or "").strip()
    return _board_redirect(member_msn_id, as_alias_id, tab, theme)


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
register_inbox_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_request_log_routes(
    app,
    private_dir=PRIVATE_DIR,
    msn_id_provider=lambda: MSN_ID,
    options_private_fn=_options_private,
)
register_contract_handshake_routes(
    app,
    private_dir=PRIVATE_DIR,
    public_dir=PUBLIC_DIR,
    msn_id_provider=lambda: MSN_ID,
    options_private_fn=_options_private,
    workspace=DATA_WORKSPACE,
)
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
