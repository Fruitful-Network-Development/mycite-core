import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

REPO_ROOT_IMPORT = Path(__file__).resolve().parents[5]
INSTANCES_ROOT_IMPORT = REPO_ROOT_IMPORT / "instances"
PACKAGES_ROOT_IMPORT = REPO_ROOT_IMPORT / "packages"
V2_REPO_PARENT_IMPORT = REPO_ROOT_IMPORT.parent
FLAVOR_ROOT_IMPORT = Path(__file__).resolve().parent
for path in (REPO_ROOT_IMPORT, INSTANCES_ROOT_IMPORT, PACKAGES_ROOT_IMPORT, V2_REPO_PARENT_IMPORT, FLAVOR_ROOT_IMPORT):
    token = str(path)
    if token not in sys.path:
        sys.path.insert(0, token)

from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, send_from_directory
from jinja2 import ChoiceLoader, FileSystemLoader, TemplateNotFound

from data.engine.workspace import Workspace
from data.storage_json import JsonStorageBackend
from instances._shared.portal.api.contract_handshake import register_contract_handshake_routes
from instances._shared.portal.api.contracts import register_contract_routes
from instances._shared.portal.api.data_workspace import register_data_routes
from instances._shared.portal.api.external_events import register_external_event_routes
from instances._shared.portal.application.service_tools import service_tool_definition
from instances._shared.portal.core_services.behavior_builder import (
    build_portal_behavior_config as shared_build_portal_behavior_config,
    collect_org_layers as shared_collect_org_layers,
    default_portal_behavior as shared_default_portal_behavior,
    organization_config_filename as shared_organization_config_filename,
)
from instances._shared.portal.core_services.runtime_config import build_runtime_config
from instances._shared.portal.core_services.shell_models import (
    build_portal_profile_model,
    sanitize_fnd_profile,
    sanitize_public_profile,
)
from instances._shared.portal.data_engine.external_resources import ExternalResourceResolver
from instances._shared.portal.sandbox.resource_workbench import build_system_resource_workbench_view_model
from instances._shared.portal.services.alias_utils import (
    alias_contact_collection_ref as shared_alias_contact_collection_ref,
    alias_label as shared_alias_label,
    canonical_progeny_type as shared_canonical_progeny_type,
    extract_contract_id as shared_extract_contract_id,
    extract_member_msn_id as shared_extract_member_msn_id,
    extract_tenant_msn_id as shared_extract_tenant_msn_id,
    format_sidebar_entity_title as shared_format_sidebar_entity_title,
    list_aliases_for_sidebar as shared_list_aliases_for_sidebar,
)
from instances._shared.portal.services.app_io import load_object_json_if_exists, read_object_json, write_object_json
from instances._shared.portal.services.control_panel import build_control_panel_sections
from instances._shared.portal.services.embed_urls import build_widget_url as shared_build_widget_url
from instances._shared.portal.services.network_contract import (
    build_network_contract_items as shared_build_network_contract_items,
    resolve_network_refs as shared_resolve_network_refs,
)
from instances._shared.portal.services.portal_model import canonicalize_portal_model_config
from instances._shared.portal.services.progeny_refs import iter_progeny_refs
from instances._shared.portal.services.runtime_mode import build_session_presentation, env_flag, install_read_only_guard
from instances._shared.portal.services.shell_context import build_shell_context
from instances._shared.portal.shell import canonical_shell_static_dir, canonical_shell_template_dir
from instances._shared.runtime.flavors.tff.portal.api.aliases import (
    get_alias_record,
    list_alias_records,
    register_aliases_routes,
)
from instances._shared.runtime.flavors.tff.portal.api.config import register_config_routes
from instances._shared.runtime.flavors.tff.portal.api.inbox import register_inbox_routes
from instances._shared.runtime.flavors.tff.portal.core_services.runtime import (
    active_service_from_path,
    active_private_config_filename,
    build_activity_tool_links,
    build_network_cards,
    build_network_tabs,
    build_property_geography_model,
    build_service_nav,
    load_active_private_config,
    resolve_active_private_config_path,
    normalize_network_tab,
)
from instances._shared.runtime.flavors.tff.portal.services.board_access import require_board_member
from instances._shared.runtime.flavors.tff.portal.services.workspace_store import (
    append_event as append_workspace_event,
)
from instances._shared.runtime.flavors.tff.portal.services.workspace_store import (
    materialize_people,
    read_events,
    workspace_root,
)
from instances._shared.runtime.flavors.tff.portal.tools.runtime import (
    active_tool_for_path,
    read_enabled_tools,
    register_tool_blueprints,
)
from mycite_core.contract_line.store import get_contract, list_contracts
from mycite_core.external_events.feed import (
    build_network_message_feed as shared_build_network_message_feed,
    event_actor_label as shared_event_actor_label,
    event_channel_id as shared_event_channel_id,
    event_contains_any as shared_event_contains_any,
    event_summary as shared_event_summary,
    format_event_timestamp as shared_format_event_timestamp,
    initials as shared_initials,
    iter_string_values as shared_iter_string_values,
    network_placeholder_item as shared_network_placeholder_item,
)
from mycite_core.local_audit import append_local_audit_event
from mycite_core.mss_resolution import preview_mss_context, resolve_contract_datum_ref
from mycite_core.publication.profile_paths import resolve_fnd_profile_path, resolve_public_profile_path
from mycite_core.runtime_paths import (
    external_event_read_paths,
    external_event_types_dir,
    hosted_read_paths,
    keypass_db_path,
    keypass_inventory_path,
    utility_peripherals_dir,
    utility_tools_dir,
    vault_contract_read_dirs,
)

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
SHARED_SHELL_TEMPLATE_DIR = canonical_shell_template_dir(REPO_ROOT)
SHARED_SHELL_STATIC_DIR = canonical_shell_static_dir(REPO_ROOT)
PORTAL_INSTANCE_ID = str(os.environ.get("PORTAL_INSTANCE_ID") or BASE_DIR.name).strip().lower()
PORTAL_RUNTIME_FLAVOR = str(os.environ.get("PORTAL_RUNTIME_FLAVOR") or PORTAL_INSTANCE_ID or BASE_DIR.name).strip().lower()
AUTH_MODE = str(os.environ.get("AUTH_MODE") or "keycloak").strip().lower() or "keycloak"
PORTAL_READ_ONLY = env_flag("PORTAL_READ_ONLY", default=False)
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

app.jinja_loader = ChoiceLoader(
    [
        FileSystemLoader(str(BASE_DIR / "portal" / "ui" / "templates")),
        FileSystemLoader(str(SHARED_SHELL_TEMPLATE_DIR)),
    ]
)
app.static_folder = str(SHARED_SHELL_STATIC_DIR)
install_read_only_guard(app, enabled=PORTAL_READ_ONLY)


# Warm the system workbench view without materializing legacy root files.
try:
    build_system_resource_workbench_view_model(data_root=DATA_DIR)
except Exception:
    pass


def _canonical_progeny_type(value: str) -> str:
    return shared_canonical_progeny_type(value)


def _default_portal_sign_out_url() -> str:
    encoded_target = quote(PORTAL_ENTRY_PATH, safe="")
    return f"/oauth2/sign_out?rd=%2Foauth2%2Fsign_in%3Frd%3D{encoded_target}"


def _read_json(path: Path) -> Dict[str, Any]:
    return read_object_json(path)


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
    write_object_json(path, payload)


def _anthology_path() -> Path:
    return DATA_DIR / "anthology.json"


def _load_local_anthology_payload() -> Dict[str, Any]:
    return load_object_json_if_exists(_anthology_path())


def _load_active_config_for_write() -> Dict[str, Any]:
    return dict(ACTIVE_PRIVATE_CONFIG if isinstance(ACTIVE_PRIVATE_CONFIG, dict) else {})


def _save_active_config_for_write(payload: Dict[str, Any]) -> bool:
    global ACTIVE_PRIVATE_CONFIG
    if not isinstance(payload, dict):
        return False
    cfg_path = resolve_active_private_config_path(PRIVATE_DIR, MSN_ID or None)
    if cfg_path is None:
        return False
    try:
        canonical_payload = canonicalize_portal_model_config(dict(payload))
        write_object_json(cfg_path, canonical_payload)
        ACTIVE_PRIVATE_CONFIG = dict(canonical_payload)
        app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = ACTIVE_PRIVATE_CONFIG
        return True
    except Exception:
        return False


def _contract_records() -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    for item in list_contracts(PRIVATE_DIR):
        contract_id = str(item.get("contract_id") or "").strip()
        if not contract_id:
            continue
        try:
            out.append(get_contract(PRIVATE_DIR, contract_id))
        except Exception:
            continue
    return out


def _contract_preview(contract_payload: Dict[str, Any]) -> Dict[str, Any]:
    owner_selected_refs = list(contract_payload.get("owner_selected_refs") or [])
    owner_preview = preview_mss_context(
        anthology_payload=_load_local_anthology_payload(),
        selected_refs=owner_selected_refs,
        bitstring="" if owner_selected_refs else str(contract_payload.get("owner_mss") or ""),
        local_msn_id=str(MSN_ID or ""),
    )
    counterparty_preview = preview_mss_context(bitstring=str(contract_payload.get("counterparty_mss") or ""))
    return {
        "owner_selected_refs": owner_selected_refs,
        "owner": owner_preview,
        "counterparty": counterparty_preview,
    }


def _network_contract_items() -> list[Dict[str, Any]]:
    return shared_build_network_contract_items(
        private_dir=PRIVATE_DIR,
        list_contracts_fn=list_contracts,
        get_contract_fn=get_contract,
        preview_mss_context_fn=preview_mss_context,
        load_anthology_payload_fn=_load_local_anthology_payload,
        local_msn_id=str(MSN_ID or ""),
    )


def _network_resolved_refs(payload: Dict[str, Any], *, preferred_contract_id: str = "") -> Dict[str, Any]:
    return shared_resolve_network_refs(
        payload,
        local_msn_id=str(MSN_ID or ""),
        anthology_payload=_load_local_anthology_payload(),
        contract_payloads=_contract_records(),
        resolve_contract_datum_ref_fn=resolve_contract_datum_ref,
        preferred_contract_id=preferred_contract_id,
    )


def _resolve_public_profile_path(msn_id: str) -> Optional[Path]:
    return resolve_public_profile_path(public_dir=PUBLIC_DIR, fallback_dir=FALLBACK_DIR, msn_id=msn_id)


def _resolve_fnd_profile_path(msn_id: str) -> Optional[Path]:
    return resolve_fnd_profile_path(public_dir=PUBLIC_DIR, fallback_dir=FALLBACK_DIR, msn_id=msn_id)


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
        "contracts": {
            "href": f"/portal/api/contracts?msn_id={msn_id}",
            "methods": ["GET", "POST", "PATCH", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
        "contract_mss_preview": {
            "href": f"/portal/api/contracts/mss/preview?msn_id={msn_id}",
            "methods": ["POST", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
        "external_events": {
            "href": "/portal/api/external_events",
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
    return shared_format_sidebar_entity_title(raw)


def _alias_label(alias_payload: Dict[str, Any], alias_id: Optional[str] = None) -> str:
    return shared_alias_label(alias_payload, alias_id)
def _extract_tenant_msn_id(alias_payload: Dict[str, Any]) -> str:
    return shared_extract_tenant_msn_id(alias_payload)


def _extract_contract_id(alias_payload: Dict[str, Any]) -> str:
    return shared_extract_contract_id(alias_payload)


def _extract_member_msn_id(alias_payload: Dict[str, Any]) -> str:
    return shared_extract_member_msn_id(alias_payload)


def _build_widget_url(alias_id: str, alias_payload: Dict[str, Any]) -> str:
    request_host_url: str | None = None
    try:
        if request and getattr(request, "host", None):
            request_host_url = request.url_root
    except Exception:
        request_host_url = None
    return shared_build_widget_url(
        alias_id=alias_id,
        alias_payload=alias_payload,
        local_msn_id=str(MSN_ID or ""),
        known_embed_port_by_msn=KNOWN_EMBED_PORT_BY_MSN,
        default_embed_port=DEFAULT_EMBED_PORT,
        canonical_progeny_type_fn=_canonical_progeny_type,
        extract_tenant_msn_id_fn=_extract_tenant_msn_id,
        extract_contract_id_fn=_extract_contract_id,
        extract_member_msn_id_fn=_extract_member_msn_id,
        local_member_path="/portal/embed/board_member",
        remote_member_path="/portal/embed/member_workbench",
        local_member_tab="feed",
        remote_member_tab="stream",
        support_tenant_embed=False,
        request_host_url=request_host_url,
    )


def _alias_contact_collection_ref(record: Dict[str, Any]) -> str:
    return shared_alias_contact_collection_ref(record)


def list_aliases_for_sidebar(private_dir: Path) -> list[Dict[str, Any]]:
    return shared_list_aliases_for_sidebar(private_dir, list_alias_records_fn=list_alias_records)


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
        for progeny_type, ref_token in iter_progeny_refs(cfg.get("progeny")):
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


def _organization_config_filename(active_cfg: Dict[str, Any]) -> str:
    return shared_organization_config_filename(active_cfg, is_tff_portal=IS_TFF_PORTAL)


def _collect_org_layers(active_cfg: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    return shared_collect_org_layers(active_cfg)


def _default_portal_behavior(active_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return shared_default_portal_behavior(
        active_cfg=active_cfg,
        is_tff_portal=IS_TFF_PORTAL,
        legal_entity_profile_defaults=LEGAL_ENTITY_PROFILE_DEFAULTS,
        default_feed_types=DEFAULT_FEED_TYPES,
        default_calendar_types=DEFAULT_CALENDAR_TYPES,
        default_profile_source_priority=DEFAULT_PROFILE_SOURCE_PRIORITY,
    )


def _build_portal_behavior_config(active_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return shared_build_portal_behavior_config(
        active_cfg=active_cfg,
        is_tff_portal=IS_TFF_PORTAL,
        legal_entity_profile_defaults=LEGAL_ENTITY_PROFILE_DEFAULTS,
        default_feed_types=DEFAULT_FEED_TYPES,
        default_calendar_types=DEFAULT_CALENDAR_TYPES,
        default_profile_source_priority=DEFAULT_PROFILE_SOURCE_PRIORITY,
    )


def _workflow_enabled() -> bool:
    features_cfg = ACTIVE_PRIVATE_CONFIG.get("portal_features") if isinstance(ACTIVE_PRIVATE_CONFIG, dict) else {}
    if isinstance(features_cfg, dict) and "workflow_enabled" in features_cfg:
        return bool(features_cfg.get("workflow_enabled"))
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
    portal_profile = ACTIVE_PRIVATE_CONFIG.get("portal_profile") if isinstance(ACTIVE_PRIVATE_CONFIG, dict) else {}
    legal_type = str(
        (portal_profile.get("profile_kind") if isinstance(portal_profile, dict) else "")
        or config.get("legal_entity_type")
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
EXTERNAL_RESOURCE_RESOLVER = ExternalResourceResolver(
    data_dir=DATA_DIR,
    public_dir=PUBLIC_DIR,
    local_msn_id=MSN_ID,
)
app.config["MYCITE_DATA_WORKSPACE"] = DATA_WORKSPACE
app.config["MYCITE_RUNTIME_CONFIG"] = build_runtime_config(
    private_dir=PRIVATE_DIR,
    public_dir=PUBLIC_DIR,
    data_dir=DATA_DIR,
    msn_id=MSN_ID,
    portal_instance_id=PORTAL_INSTANCE_ID,
)
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


def _iter_external_event_records() -> list[Dict[str, Any]]:
    msn_id = str(MSN_ID or _infer_local_msn_id() or "").strip()
    paths = [path for path in external_event_read_paths(PRIVATE_DIR, msn_id or None) if path.exists() and path.is_file()]
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
    return token if token in {"messages", "hosted", "profile", "contracts"} else "messages"


def _normalize_network_kind(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"alias", "log", "p2p"} else "alias"


def _normalize_utilities_tab(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"tools", "vault", "peripherals"} else "tools"


def _normalize_system_query_tab(raw: Any) -> str:
    _ = raw
    return "system"


def _canonical_system_url() -> str:
    query_items = [(key, value) for key, value in request.args.items(multi=True) if key not in {"tab", "workbench"}]
    if not query_items:
        return "/portal/system"
    return f"/portal/system?{urlencode(query_items)}"


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


def _configured_tool_items() -> list[Dict[str, Any]]:
    seen: set[str] = set()
    out: list[Dict[str, Any]] = []
    for mount_target in ("utilities", "peripherals.tools"):
        for tool in _tools_by_mount_target(mount_target):
            tool_id = str(tool.get("tool_id") or "").strip()
            if not tool_id or tool_id in seen:
                continue
            seen.add(tool_id)
            out.append(tool)
    return out


def _configured_tool_status_items() -> list[Dict[str, Any]]:
    config_payload = load_active_private_config(PRIVATE_DIR, MSN_ID or None)
    configured = config_payload.get("tools_configuration") if isinstance(config_payload.get("tools_configuration"), list) else []
    runtime_ids = {str(item.get("tool_id") or "").strip().lower() for item in TOOL_TABS if isinstance(item, dict)}
    out: list[Dict[str, Any]] = []
    for entry in configured:
        if not isinstance(entry, dict):
            continue
        raw_name = str(entry.get("name") or entry.get("tool_id") or entry.get("id") or "").strip().lower()
        if not raw_name:
            continue
        runtime_id = raw_name.replace("-", "_")
        tab = next((item for item in TOOL_TABS if str(item.get("tool_id") or "").strip().lower() == runtime_id), {})
        if not tab:
            for candidate_id in (
                "fnd_ebi",
                "aws_platform_admin",
                "paypal_service_agreement",
                "paypal_tenant_actions",
                "operations",
                "fnd_provisioning",
            ):
                definition = service_tool_definition(candidate_id)
                namespace = str(definition.get("namespace") or "").strip().lower()
                if namespace != raw_name:
                    continue
                runtime_id = candidate_id
                tab = next((item for item in TOOL_TABS if str(item.get("tool_id") or "").strip().lower() == runtime_id), {})
                break
        out.append(
            {
                "name": raw_name,
                "runtime_id": runtime_id,
                "display_name": str(tab.get("display_name") or raw_name.replace("-", " ").replace("_", " ").title()),
                "status": str(entry.get("status") or "enabled").strip().lower() or "enabled",
                "mount_target": str(entry.get("mount_target") or ""),
                "runtime_loaded": runtime_id in runtime_ids,
            }
        )
    out.sort(key=lambda item: str(item.get("display_name") or "").lower())
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
    shared_profile = build_portal_profile_model(
        local_msn_id=local_msn_id,
        read_json_fn=_read_json,
        resolve_public_profile_path_fn=_resolve_public_profile_path,
        resolve_fnd_profile_path_fn=_resolve_fnd_profile_path,
    )

    config_file = active_private_config_filename(PRIVATE_DIR, MSN_ID or None)

    return {
        "msn_id": local_msn_id,
        "public_profile": dict(shared_profile.get("public_profile") or {}),
        "options_public": _options_public(local_msn_id) if local_msn_id else {},
        "fnd_profile": dict(shared_profile.get("fnd_profile") or {}),
        "config_file": config_file,
    }


def _external_event_summary() -> Dict[str, Any]:
    paths = [path for path in external_event_read_paths(PRIVATE_DIR, MSN_ID or None) if path.exists() and path.is_file()]
    return {"file_count": len(paths), "event_count": len(_iter_external_event_records())}


def _external_event_channels() -> list[Dict[str, Any]]:
    event_count = len(_iter_external_event_records())
    return [{"id": "external_events", "label": "external_events", "event_count": event_count, "href": "/portal/network?tab=messages&kind=log&id=external_events"}]


def _p2p_channels() -> list[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for payload in _iter_external_event_records():
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
    yield from shared_iter_string_values(value)


def _event_contains_any(event: Dict[str, Any], tokens: list[str]) -> bool:
    return shared_event_contains_any(event, tokens)


def _event_channel_id(event: Dict[str, Any]) -> str:
    return shared_event_channel_id(event)


def _format_event_timestamp(ts_unix_ms: Any) -> str:
    return shared_format_event_timestamp(ts_unix_ms)


def _initials(token: str, fallback: str = "NW") -> str:
    return shared_initials(token, fallback)


def _event_actor_label(event: Dict[str, Any]) -> str:
    return shared_event_actor_label(event, local_msn_id=str(MSN_ID or ""))


def _event_summary(event: Dict[str, Any]) -> str:
    return shared_event_summary(event)


def _network_placeholder_item(kind: str, selected: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return shared_network_placeholder_item(kind, selected)


def _network_message_feed(
    kind: str,
    selected_alias: Optional[Dict[str, Any]],
    selected_log: Optional[Dict[str, Any]],
    selected_p2p: Optional[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    return shared_build_network_message_feed(
        kind=kind,
        selected_alias=selected_alias,
        selected_log=selected_log,
        selected_p2p=selected_p2p,
        local_msn_id=str(MSN_ID or ""),
        iter_external_event_records_fn=_iter_external_event_records,
        resolve_refs_fn=lambda event, preferred: _network_resolved_refs(event, preferred_contract_id=preferred),
    )


def _control_panel_sections(active_service: str) -> list[Dict[str, Any]]:
    network_tab = _normalize_network_query_tab(request.args.get("tab"))
    kind = _normalize_network_kind(request.args.get("kind"))
    utilities_tab = _normalize_utilities_tab(request.args.get("tab"))
    selected = str(request.args.get("id") or "").strip()
    return build_control_panel_sections(
        active_service=active_service,
        network_tab=network_tab,
        network_kind=kind,
        utilities_tab=utilities_tab,
        selected_id=selected,
        tool_tabs=TOOL_TABS,
        aliases=_network_sidebar_alias_items(),
        p2p_channels=_p2p_channels(),
        include_alias_interfaces=True,
        include_progeny_utility=False,
        local_msn_id=str(MSN_ID or ""),
    )


@app.context_processor
def _shell_context() -> Dict[str, Any]:
    active_service = active_service_from_path(request.path)
    active_service_tab = ""
    if active_service == "network":
        active_service_tab = _normalize_network_query_tab(request.args.get("tab"))
    elif active_service == "utilities":
        active_service_tab = _normalize_utilities_tab(request.args.get("tab"))
    elif active_service == "system":
        active_service_tab = _normalize_system_query_tab(request.args.get("tab"))
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
    session_presentation = build_session_presentation(
        auth_mode=AUTH_MODE,
        active_portal_username=active_portal_username,
        read_only=PORTAL_READ_ONLY,
    )
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
    mediate_tool = str(request.args.get("mediate_tool") or "").strip().lower()
    mediate_tool_meta = next(
        (tool for tool in TOOL_TABS if str(tool.get("tool_id") or "").strip().lower() == mediate_tool),
        None,
    )
    shell_composition_mode = (
        "tool"
        if active_service == "system"
        and mediate_tool_meta is not None
        and str(mediate_tool_meta.get("shell_composition_mode") or "").strip().lower() == "tool"
        else "system"
    )
    activity_tool_links = build_activity_tool_links(TOOL_TABS, active_mediate_tool=mediate_tool)
    context = build_shell_context(
        active_service=active_service,
        active_service_tab=active_service_tab,
        active_tool=active_tool,
        tool_tabs=TOOL_TABS,
        service_nav=build_service_nav(ACTIVE_PRIVATE_CONFIG, active_service=active_service),
        activity_tool_links=activity_tool_links,
        network_tabs=build_network_tabs(active_service_tab),
        sidebar_progeny=sidebar_progeny,
        portal_name=portal_name,
        active_portal_username=str(session_presentation.get("active_portal_username") or ""),
        sign_out_url=sign_out_url,
        switch_portal_url=switch_portal_url,
        current_path=current_path,
        control_panel_sections=_control_panel_sections(active_service),
        active_mediate_tool=mediate_tool,
        shell_composition_mode=shell_composition_mode,
    )
    context.update(session_presentation)
    return context


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


@app.get("/portal/api/tools/icons/<tool_slug>/<icon_name>")
def portal_tool_icon(tool_slug: str, icon_name: str):
    slug = str(tool_slug or "").strip().lower()
    name = str(icon_name or "").strip()
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", slug):
        abort(404)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name):
        abort(404)
    if Path(name).name != name or not name.lower().endswith(".svg"):
        abort(404)
    root = utility_tools_dir(PRIVATE_DIR) / slug / "UI"
    try:
        root_resolved = root.resolve()
        candidate = (root / name).resolve()
        candidate.relative_to(root_resolved)
    except Exception:
        abort(404)
    if not candidate.exists() or not candidate.is_file():
        abort(404)
    return send_from_directory(root_resolved.as_posix(), candidate.name, mimetype="image/svg+xml")


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": BASE_DIR.name})


def _ensure_runtime_dirs() -> None:
    workspace_root()
    external_event_types_dir(PRIVATE_DIR).parent.mkdir(parents=True, exist_ok=True)
    external_event_types_dir(PRIVATE_DIR).mkdir(parents=True, exist_ok=True)
    utility_peripherals_dir(PRIVATE_DIR).mkdir(parents=True, exist_ok=True)
    keypass_inventory_path(PRIVATE_DIR).parent.mkdir(parents=True, exist_ok=True)
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
    safe_payload.setdefault("portal_instance_id", PORTAL_INSTANCE_ID)
    safe_payload.setdefault("msn_id", MSN_ID or _infer_local_msn_id() or PORTAL_INSTANCE_ID)
    append_local_audit_event(PRIVATE_DIR, safe_payload)


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
    if "tab" in request.args or "workbench" in request.args:
        return redirect(_canonical_system_url(), code=302)
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
    return redirect(_canonical_system_url(), code=302)


@app.get("/portal/data/<path:tab_id>")
def portal_data_legacy(tab_id: str):
    _ = tab_id
    return redirect(_canonical_system_url(), code=302)


@app.get("/portal/network")
def portal_network_default():
    tab = _normalize_network_query_tab(request.args.get("tab"))
    kind = _normalize_network_kind(request.args.get("kind"))
    selected_id = str(request.args.get("id") or "").strip()
    aliases = _network_sidebar_alias_items()
    log_channels = _external_event_channels()
    p2p_channels = _p2p_channels()
    contracts = _network_contract_items()

    selected_alias = next((item for item in aliases if item["id"] == selected_id), None) if tab == "messages" and kind == "alias" else None
    selected_log = next((item for item in log_channels if item["id"] == selected_id), None) if tab == "messages" and kind == "log" else None
    selected_p2p = next((item for item in p2p_channels if item["id"] == selected_id), None) if tab == "messages" and kind == "p2p" else None
    selected_contract = next((item for item in contracts if item["id"] == selected_id), None) if tab == "contracts" else None

    if tab == "messages" and not selected_id:
        if kind == "alias" and aliases:
            return redirect(aliases[0]["href"], code=302)
        if kind == "log" and log_channels:
            return redirect(log_channels[0]["href"], code=302)
        if kind == "p2p" and p2p_channels:
            return redirect(p2p_channels[0]["href"], code=302)
    if tab == "contracts" and not selected_id and contracts:
        return redirect(contracts[0]["href"], code=302)

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
        network_contracts=contracts,
        selected_contract=selected_contract,
        message_feed=message_feed,
        external_event_summary=_external_event_summary(),
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
    if token in {"logs"}:
        return redirect("/portal/network?tab=messages&kind=log", code=302)
    if token in {"contracts", "contract"}:
        return redirect("/portal/network?tab=contracts", code=302)
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
        external_event_summary=_external_event_summary(),
        configured_tools=_configured_tool_items(),
        configured_tool_status=_configured_tool_status_items(),
        peripheral_entries=_utility_peripheral_entries(),
        vault_inventory=inventory,
        vault_inventory_json=json.dumps(inventory, indent=2, sort_keys=True),
        vault_contract_files=_vault_contract_files(),
        keypass_db_path=str(keypass_db_path(PRIVATE_DIR)),
        keypass_inventory_path=str(keypass_inventory_path(PRIVATE_DIR)),
    )


@app.put("/portal/api/utilities/tools/<tool_slug>/status")
def portal_tools_status_put(tool_slug: str):
    token = str(tool_slug or "").strip().lower()
    if not token:
        abort(400, description="tool slug is required")
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    desired = str(body.get("status") or "").strip().lower()
    if desired not in {"enabled", "disabled"}:
        abort(400, description="status must be enabled or disabled")

    path = resolve_active_private_config_path(PRIVATE_DIR, MSN_ID or None)
    if path is None:
        abort(404, description="active config path could not be resolved")
    payload = load_active_private_config(PRIVATE_DIR, MSN_ID or None)
    tools_cfg = payload.get("tools_configuration") if isinstance(payload.get("tools_configuration"), list) else []
    updated = False
    for item in tools_cfg:
        if not isinstance(item, dict):
            continue
        item_name = str(item.get("name") or item.get("tool_id") or item.get("id") or "").strip().lower()
        if item_name in {token, token.replace("_", "-"), token.replace("-", "_")}:
            item["status"] = desired
            updated = True
    if not updated:
        abort(404, description=f"tool not found in tools_configuration: {token}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    global ACTIVE_PRIVATE_CONFIG
    ACTIVE_PRIVATE_CONFIG = dict(payload)
    app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = dict(payload)
    return jsonify(
        {
            "ok": True,
            "tool": token,
            "status": desired,
            "written_to": str(path),
            "note": "Tool status was updated in config. A portal reload may be required for newly-enabled tool packages.",
        }
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
    return redirect("/portal/network?tab=messages&kind=log&id=external_events", code=302)


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
register_config_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_inbox_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_contract_routes(
    app,
    private_dir=PRIVATE_DIR,
    options_private_fn=_options_private,
    anthology_path_fn=_anthology_path,
)
register_external_event_routes(
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
    external_resource_resolver=EXTERNAL_RESOURCE_RESOLVER,
    anthology_payload_provider=_load_local_anthology_payload,
    active_config_provider=_load_active_config_for_write,
    active_config_saver=_save_active_config_for_write,
    private_dir=PRIVATE_DIR,
    include_home_redirect=False,
    include_legacy_shims=False,
)


@app.post("/portal/api/data/mss/compile")
def portal_data_mss_compile():
    """Compile selected anthology datum refs into MSS compact array (bitstring). Uses shared MSS algorithm."""
    body = request.get_json(silent=True) or {}
    selected_refs = list(body.get("selected_refs") or [])
    selected_refs = [str(r).strip() for r in selected_refs if str(r).strip()]
    if not selected_refs:
        return jsonify({"ok": False, "error": "selected_refs required (non-empty list of datum identifiers)"}), 400
    try:
        from _shared.portal.sandbox import SandboxEngine

        anthology_payload = _load_local_anthology_payload()
        engine = SandboxEngine(data_root=DATA_DIR)
        result = engine.compile_mss_resource(
            resource_id=str(body.get("resource_id") or "mss_compile").strip(),
            selected_refs=selected_refs,
            anthology_payload=anthology_payload,
            local_msn_id=str(MSN_ID or ""),
        )
        payload = dict(result.compiled_payload if isinstance(result.compiled_payload, dict) else {})
        # Backward-compatible route shape for existing UI callers.
        return jsonify(
            {
                "ok": result.ok,
                "bitstring": str(payload.get("bitstring") or ""),
                "metadata": payload.get("metadata") or {},
                "rows": payload.get("rows") or [],
                "selected_source_refs": payload.get("selected_refs") or selected_refs,
                "sandbox_resource_id": payload.get("resource_id") or "",
                "warnings": list(result.warnings),
            }
        ), (200 if result.ok else 400)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
