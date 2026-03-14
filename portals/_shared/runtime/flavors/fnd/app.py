import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, send_from_directory
from jinja2 import TemplateNotFound

from data.engine.workspace import Workspace
from data.storage_json import JsonStorageBackend
from portal.api.aliases import get_alias_record, list_alias_records, register_aliases_routes
from portal.api.aws_emailer import register_aws_emailer_routes
from portal.api.admin_integrations import register_admin_integration_routes
from portal.api.config import register_config_routes
from portal.api.contract_handshake import register_contract_handshake_routes
from portal.api.contracts import register_contract_routes
from portal.api.data_workspace import register_data_routes as register_data_workspace_routes
from portal.api.inbox import register_inbox_routes
from portal.api.paypal_checkout import register_paypal_checkout_routes
from portal.api.progeny_config import register_progeny_config_routes
from portal.api.progeny_workbench import register_progeny_workbench_routes
from portal.api.request_log import register_request_log_routes
from portal.api.tenant_progeny import register_tenant_progeny_routes
from portal.api.website_analytics import register_website_analytics_routes
from portal.core_services.runtime import (
    active_service_from_path,
    build_network_cards,
    build_network_tabs,
    build_property_geography_model,
    build_service_nav,
    load_active_private_config,
    normalize_network_tab,
    active_private_config_filename,
)
from portal.services.alias_factory import alias_path, client_key_for_msn, merge_field_names
from portal.services.hosted_store import DEFAULT_TABS as HOSTED_DEFAULT_TABS, read_hosted_payload
from portal.services.contract_store import get_contract, list_contracts
from portal.services.mss import preview_mss_context, resolve_contract_datum_ref
from portal.services.progeny_embed import build_embed_progeny_landing
from portal.services.progeny_config_store import get_client_config, get_config
from portal.services.progeny_workspace import find_profile_by_associated_msn, list_instances
from portal.services.request_log_store import append_event
from portal.services.runtime_paths import (
    aliases_dir,
    contracts_dir,
    keypass_db_path,
    keypass_inventory_path,
    progeny_root,
    request_log_read_paths,
    request_log_types_dir,
    utility_peripherals_dir,
    utility_tools_dir,
    vault_contract_read_dirs,
    vault_contracts_dir,
    vault_keys_dir,
)
from portal.services.tenant_progeny_store import load_profile, save_profile, set_paypal_config
from portal.services.website_analytics_store import load_member_analytics, list_member_analytics
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


REPO_ROOT = _resolve_portals_root()
PUBLIC_DIR = Path(os.environ.get("PUBLIC_DIR", str(BASE_DIR / "public")))
PRIVATE_DIR = Path(os.environ.get("PRIVATE_DIR", str(BASE_DIR / "private")))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
FALLBACK_DIR = BASE_DIR
ICONS_DIR = REPO_ROOT / "assets" / "icons"
PORTAL_INSTANCE_ID = str(os.environ.get("PORTAL_INSTANCE_ID") or "fnd").strip().lower()
FND_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
TFF_MSN_ID = "3-2-3-17-77-2-6-3-1-6"
KNOWN_EMBED_PORT_BY_MSN = {
    FND_MSN_ID: "5101",
    TFF_MSN_ID: "5203",
}


for required in (
    aliases_dir(PRIVATE_DIR),
    contracts_dir(PRIVATE_DIR),
    request_log_types_dir(PRIVATE_DIR).parent,
    request_log_types_dir(PRIVATE_DIR),
    progeny_root(PRIVATE_DIR),
    utility_tools_dir(PRIVATE_DIR),
    utility_peripherals_dir(PRIVATE_DIR),
    vault_contracts_dir(PRIVATE_DIR),
    vault_keys_dir(PRIVATE_DIR),
    DATA_DIR / "cache" / "contacts",
    DATA_DIR / "cache" / "tenant",
):
    required.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _anthology_path() -> Path:
    return DATA_DIR / "anthology.json"


def _load_local_anthology_payload() -> Dict[str, Any]:
    path = _anthology_path()
    if not path.exists() or not path.is_file():
        return {}
    try:
        return _read_json(path)
    except Exception:
        return {}


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
    out: list[Dict[str, Any]] = []
    for item in list_contracts(PRIVATE_DIR):
        contract_id = str(item.get("contract_id") or "").strip()
        if not contract_id:
            continue
        try:
            contract_payload = get_contract(PRIVATE_DIR, contract_id)
        except Exception:
            contract_payload = {"contract_id": contract_id}
        preview = _contract_preview(contract_payload)
        out.append(
            {
                "id": contract_id,
                "contract_id": contract_id,
                "label": str(contract_payload.get("contract_type") or contract_id).strip() or contract_id,
                "counterparty_msn_id": str(contract_payload.get("counterparty_msn_id") or "").strip(),
                "status": str(contract_payload.get("status") or "pending").strip(),
                "owner_selected_refs": list(contract_payload.get("owner_selected_refs") or []),
                "owner_mss_present": bool(str(contract_payload.get("owner_mss") or "").strip()),
                "counterparty_mss_present": bool(str(contract_payload.get("counterparty_mss") or "").strip()),
                "href": f"/portal/network?tab=contracts&id={quote(contract_id, safe='')}",
                "payload": contract_payload,
                "preview": preview,
            }
        )
    return out


def _network_resolved_refs(payload: Dict[str, Any], *, preferred_contract_id: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    contracts = _contract_records()
    anthology = _load_local_anthology_payload()
    for key in ("event_datum", "status"):
        token = str(payload.get(key) or "").strip()
        if not token:
            continue
        try:
            out[key] = resolve_contract_datum_ref(
                token,
                local_msn_id=str(MSN_ID or ""),
                anthology_payload=anthology,
                contract_payloads=contracts,
                preferred_contract_id=preferred_contract_id,
            )
        except Exception:
            continue
    return out


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
    candidates = [
        PUBLIC_DIR / f"fnd-{token}.json",
        FALLBACK_DIR / f"fnd-{token}.json",
    ]
    return _find_first(candidates)


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
        "clients": {"href": "/portal/clients", "methods": ["GET", "OPTIONS"], "auth": "keycloak_or_local"},
        "config": {
            "href": f"/portal/api/config?msn_id={msn_id}",
            "methods": ["GET", "PUT", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
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
        "progeny_config": {
            "href": f"/portal/api/progeny_config/tenant?msn_id={msn_id}",
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
        known = KNOWN_EMBED_PORT_BY_MSN.get(host)
        if known:
            return known

    if os.environ.get("EMBED_HOST_PORT"):
        return str(os.environ.get("EMBED_HOST_PORT")).strip()

    return "5001"


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


def _canonical_progeny_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if token == "tenant":
        return "member"
    if token == "board_member":
        return "member"
    return token


def _default_portal_sign_out_url() -> str:
    if PORTAL_INSTANCE_ID == "tff":
        target = "/portal/tff"
    else:
        target = "/portal/fnd"
    encoded_target = quote(target, safe="")
    return f"/oauth2/sign_out?rd=%2Foauth2%2Fsign_in%3Frd%3D{encoded_target}"


def _build_widget_url(alias_id: str, alias_payload: Dict[str, Any]) -> str:
    org_msn_id = str(alias_payload.get("alias_host") or "").strip()
    org_title = str(alias_payload.get("host_title") or "").strip()
    # When the alias is hosted by another portal (org_msn_id != current MSN), the iframe must load
    # that host's origin so the host serves member_workbench/tenant/poc content.
    if org_msn_id and MSN_ID and org_msn_id != MSN_ID:
        url_key = f"EMBED_HOST_URL_{_sanitize_env_suffix(org_msn_id)}"
        base_url = (os.environ.get(url_key) or "").strip().rstrip("/")
        if not base_url:
            embed_port = _resolve_embed_port(org_msn_id)
            base_url = f"http://127.0.0.1:{embed_port}"
    else:
        try:
            if request and getattr(request, "host", None):
                base_url = request.url_root.rstrip("/")
            else:
                raise ValueError("no request")
        except Exception:
            embed_port = _resolve_embed_port(org_msn_id)
            base_url = f"http://127.0.0.1:{embed_port}"

    progeny_type = str(alias_payload.get("progeny_type") or "").strip().lower()
    canonical_progeny_type = _canonical_progeny_type(progeny_type)
    tenant_id = _extract_tenant_msn_id(alias_payload)
    if progeny_type == "tenant" and tenant_id:
        query = urlencode(
            {
                "tenant_msn_id": tenant_id,
                "contract_id": _extract_contract_id(alias_payload),
                "as_alias_id": alias_id,
            }
        )
        return f"{base_url}/portal/embed/tenant?{query}"

    member_msn_id = _extract_member_msn_id(alias_payload)
    if canonical_progeny_type == "member" and member_msn_id:
        query = urlencode({"member_msn_id": member_msn_id, "as_alias_id": alias_id, "tab": "stream"})
        return f"{base_url}/portal/embed/member_workbench?{query}"

    query = urlencode({"org_msn_id": org_msn_id, "as_alias_id": alias_id, "org_title": org_title})
    return f"{base_url}/portal/embed/poc?{query}"


def _alias_contact_collection_ref(record: Dict[str, Any]) -> str:
    profile_refs = record.get("profile_refs") if isinstance(record.get("profile_refs"), dict) else {}
    alias_ref = str(profile_refs.get("contact_collection_ref") or "").strip()
    if alias_ref:
        return alias_ref

    tenant_progeny = record.get("tenant_progeny") if isinstance(record.get("tenant_progeny"), dict) else {}
    tenant_refs = tenant_progeny.get("profile_refs") if isinstance(tenant_progeny.get("profile_refs"), dict) else {}
    progeny_ref = str(tenant_refs.get("contact_collection_ref") or "").strip()
    if progeny_ref:
        return progeny_ref

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
                "contact_collection_ref": _alias_contact_collection_ref(record),
            }
        )
    return aliases


def _field_names_for_alias(alias_payload: Dict[str, Any]) -> list[str]:
    progeny_type = str(alias_payload.get("progeny_type") or "").strip()
    if not progeny_type:
        return []

    base_fields = []
    try:
        cfg = get_config(progeny_type)
        if isinstance(cfg.get("fields"), list):
            base_fields = cfg.get("fields") or []
    except Exception:
        base_fields = []

    overlay_fields = []
    client_key = client_key_for_msn(str(alias_payload.get("client_msn_id") or ""))
    if client_key:
        overlay = get_client_config(client_key)
        if isinstance(overlay, dict) and isinstance(overlay.get("fields"), list):
            overlay_fields = overlay.get("fields") or []

    existing_fields = alias_payload.get("fields") if isinstance(alias_payload.get("fields"), dict) else {}
    return merge_field_names(base_fields, overlay_fields, existing_fields.keys())


MSN_ID = _infer_local_msn_id()


ACTIVE_PRIVATE_CONFIG = load_active_private_config(PRIVATE_DIR, MSN_ID or None)
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
WORKSPACE_CONFIG["msn_id"] = MSN_ID

ENABLED_TOOL_IDS = read_enabled_tools(PRIVATE_DIR, msn_id=MSN_ID or None)
TOOL_TABS = register_tool_blueprints(
    app,
    ENABLED_TOOL_IDS,
    tools_dir=BASE_DIR / "portal" / "tools",
    private_dir=PRIVATE_DIR,
)
DATA_WORKSPACE = Workspace(JsonStorageBackend(DATA_DIR), config=WORKSPACE_CONFIG)
app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = ACTIVE_PRIVATE_CONFIG
app.config["MYCITE_PORTAL_INSTANCE_ID"] = PORTAL_INSTANCE_ID
app.config["MYCITE_MSN_ID"] = MSN_ID
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


def _request_log_root() -> Path:
    paths = request_log_read_paths(PRIVATE_DIR, MSN_ID or None)
    return paths[0].parent if paths else PRIVATE_DIR / "network" / "request_log"


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
    return token if token in {"messages", "hosted", "profile", "contracts"} else "messages"


def _normalize_network_kind(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"alias", "log", "p2p"} else "alias"


def _normalize_utilities_tab(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"tools", "vault", "peripherals", "progeny"} else "tools"


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


_ACTIVITY_TOOL_PRESENTATION: Dict[str, Dict[str, str]] = {
    "data_tool": {"label": "Data Tool", "icon": "/portal/static/icons/ui/data.svg"},
    "tenant_progeny_profiles": {"label": "Profiles", "icon": "/portal/static/icons/progeny.svg"},
    "fnd_provisioning": {"label": "Provision", "icon": "/portal/static/icons/ui/launch.svg"},
    "paypal_tenant_actions": {"label": "PayPal Mbr", "icon": "/portal/static/icons/logos/paypal.svg"},
    "paypal_service_agreement": {"label": "PayPal FND", "icon": "/portal/static/icons/logos/paypal.svg"},
    "aws_tenant_actions": {"label": "AWS Mbr", "icon": "/portal/static/icons/logos/aws.svg"},
    "aws_platform_admin": {"label": "AWS FND", "icon": "/portal/static/icons/logos/aws.svg"},
    "website_analytics": {"label": "Analytics", "icon": "/portal/static/icons/statistics.svg"},
    "operations": {"label": "Ops", "icon": "/portal/static/icons/ui/settings.svg"},
}


def _activity_tool_items(active_tool_id: str) -> list[Dict[str, Any]]:
    if PORTAL_INSTANCE_ID != "fnd":
        return []

    out: list[Dict[str, Any]] = []
    for tool in _utility_tool_items():
        tool_id = str(tool.get("tool_id") or "").strip().lower()
        home_path = str(tool.get("home_path") or "").strip()
        if not tool_id or not home_path:
            continue
        display_name = str(tool.get("display_name") or tool_id).strip() or tool_id
        presentation = _ACTIVITY_TOOL_PRESENTATION.get(tool_id, {})
        out.append(
            {
                "tool_id": tool_id,
                "label": str(presentation.get("label") or display_name).strip() or display_name,
                "title": display_name,
                "href": home_path,
                "icon": str(presentation.get("icon") or tool.get("icon") or "/portal/static/icons/ui/tools.svg").strip(),
                "active": tool_id == str(active_tool_id or "").strip().lower(),
            }
        )
    return out


def _utility_peripheral_entries() -> list[Dict[str, Any]]:
    root = utility_peripherals_dir(PRIVATE_DIR)
    if not root.exists() or not root.is_dir():
        return []
    out: list[Dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        out.append(
            {
                "name": path.name,
                "kind": "directory" if path.is_dir() else "file",
                "path": str(path),
            }
        )
    return out


def _progeny_preview_url(selected_type: str, associated_msn_id: str, alias_id: str) -> str:
    progeny_type = str(selected_type or "").strip().lower()
    associated = str(associated_msn_id or "").strip()
    if not associated:
        return ""
    query = urlencode(
        {
            "member_msn_id": associated,
            "progeny_type": progeny_type,
            "as_alias_id": alias_id,
            "tab": "stream",
        }
    )
    return f"/portal/embed/member_workbench?{query}"


def _progeny_workbench_model(selected_type: str = "", selected_instance_id: str = "") -> Dict[str, Any]:
    hosted_payload = read_hosted_payload(PRIVATE_DIR)
    instances = list_instances(PRIVATE_DIR)
    selected_type_token = str(selected_type or "").strip().lower()
    if selected_type_token not in {"admin", "member", "user"}:
        selected_type_token = "member"

    template_map = {
        token: hosted_payload.get("progeny", {}).get("templates", {}).get(token, {})
        for token in ("admin", "member", "user")
    }
    type_cards: list[Dict[str, Any]] = []
    for token in ("member", "user", "admin"):
        matching = [record for record in instances if str(record.get("progeny_type") or "") == token]
        template = template_map.get(token) if isinstance(template_map.get(token), dict) else {}
        type_cards.append(
            {
                "progeny_type": token,
                "label": token.title(),
                "count": len(matching),
                "template_version": str(template.get("template_version") or ""),
                "href": f"/portal/utilities?tab=progeny&progeny_type={token}",
                "active": token == selected_type_token,
            }
        )

    selected_records = [record for record in instances if str(record.get("progeny_type") or "") == selected_type_token]
    selected_record = None
    if selected_instance_id:
        for record in selected_records:
            if str(record.get("instance_id") or "") == selected_instance_id:
                selected_record = record
                break
    if selected_record is None and selected_records:
        selected_record = selected_records[0]

    selected_payload = selected_record.get("payload") if isinstance((selected_record or {}).get("payload"), dict) else {}
    selected_display = selected_payload.get("display") if isinstance(selected_payload.get("display"), dict) else {}
    selected_alias_id = str((selected_payload.get("alias_profile") or {}).get("alias_id") or "").strip()
    associated_msn_id = str(
        selected_payload.get("alias_associated_msn_id")
        or selected_payload.get("member_msn_id")
        or selected_payload.get("tenant_msn_id")
        or selected_payload.get("msn_id")
        or ""
    ).strip()
    selected_summary = {
        "instance_id": str((selected_record or {}).get("instance_id") or ""),
        "title": str(selected_payload.get("title") or selected_display.get("title") or selected_type_token.title()).strip(),
        "associated_msn_id": associated_msn_id,
        "alias_id": selected_alias_id,
        "path": str((selected_record or {}).get("path") or ""),
        "source_kind": str((selected_record or {}).get("source_kind") or ""),
    }

    selected_template = template_map.get(selected_type_token) if isinstance(template_map.get(selected_type_token), dict) else {}
    return {
        "hosted_payload": hosted_payload,
        "type_cards": type_cards,
        "selected_type": selected_type_token,
        "selected_template": selected_template,
        "selected_template_json": json.dumps(selected_template, indent=2, sort_keys=True),
        "instances": selected_records,
        "selected_instance": selected_record,
        "selected_summary": selected_summary,
        "selected_instance_json": json.dumps(selected_payload, indent=2, sort_keys=True) if selected_payload else "{}",
        "storage": ((hosted_payload.get("progeny") or {}).get("storage") if isinstance(hosted_payload.get("progeny"), dict) else {}) or {},
        "preview_url": _progeny_preview_url(selected_type_token, associated_msn_id, selected_alias_id),
    }


def _default_vault_inventory() -> Dict[str, Any]:
    return {
        "schema": "mycite.utilities.vault.inventory.v1",
        "entries": [],
    }


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
    return [
        {
            "id": "request_log",
            "label": "request_log",
            "event_count": event_count,
            "href": "/portal/network?tab=messages&kind=log&id=request_log",
        }
    ]


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
        resolved_refs = _network_resolved_refs(event, preferred_contract_id=str(event.get("contract_id") or "").strip())
        if resolved_refs:
            preview_payload["mss_resolution"] = resolved_refs
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
        # Navigation (Messages, Hosted, Profile, Contracts) is via tabs only; do not duplicate in sidebar.
        # Request log is the underlying feed for Messages; do not list as a separate sidebar section.
        # Contracts list belongs under the Contracts tab; do not list in sidebar.
        # FND does not host alias profiles (only progeny interfaces for TFF-hosted aliases); omit Alias Interfaces.
        p2p = _p2p_channels()
        return [
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
        progeny_type = str(request.args.get("progeny_type") or "").strip().lower()
        workbench = _progeny_workbench_model(progeny_type, str(request.args.get("instance") or "").strip()) if utilities_tab == "progeny" else {}
        type_entries = []
        if isinstance(workbench, dict):
            for item in workbench.get("type_cards") or []:
                if not isinstance(item, dict):
                    continue
                type_entries.append(
                    {
                        "label": str(item.get("label") or "").strip(),
                        "href": str(item.get("href") or "").strip(),
                        "active": bool(item.get("active")),
                        "meta": f"{int(item.get('count') or 0)} instance(s)",
                    }
                )
        return [
            {
                "title": "Utility Views",
                "entries": [
                    {"label": "Tools", "href": "/portal/utilities?tab=tools", "active": utilities_tab == "tools", "meta": "launchers + mounts"},
                    {"label": "Vault", "href": "/portal/utilities?tab=vault", "active": utilities_tab == "vault", "meta": "KeePass inventory"},
                    {"label": "Peripherals", "href": "/portal/utilities?tab=peripherals", "active": utilities_tab == "peripherals", "meta": "runtime directory"},
                    {"label": "Progeny", "href": "/portal/utilities?tab=progeny&progeny_type=member", "active": utilities_tab == "progeny", "meta": "templates + instances"},
                ],
                "empty_text": "",
            },
            {
                "title": "Progeny Types",
                "entries": type_entries,
                "empty_text": "Select the Progeny utility view to browse templates and instances.",
            },
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
def _tool_shell_context() -> Dict[str, Any]:
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
        "activity_tool_nav": _activity_tool_items(str(active_tool.get("tool_id") or "") if active_tool else ""),
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
    return jsonify({"ok": True, "service": "fnd_portal"})


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
def portal_data_root():
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
    hosted_payload = read_hosted_payload(PRIVATE_DIR)
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
        request_log_summary=_request_log_summary(),
        network_profile_json=json.dumps(profile_model.get("public_profile") or {}, indent=2, sort_keys=True),
        fnd_profile_json=json.dumps(profile_model.get("fnd_profile") or {}, indent=2, sort_keys=True),
        public_profile_json=json.dumps(profile_model.get("public_profile") or {}, indent=2, sort_keys=True),
        network_config_json=json.dumps(ACTIVE_PRIVATE_CONFIG, indent=2, sort_keys=True),
        hosted_payload=hosted_payload,
        hosted_payload_json=json.dumps(hosted_payload, indent=2, sort_keys=True),
        property_geography=geography_model,
    )


@app.get("/portal/network/<tab_id>")
def portal_network_legacy(tab_id: str):
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
    selected_type = str(request.args.get("progeny_type") or "").strip().lower()
    selected_instance = str(request.args.get("instance") or "").strip()
    progeny_workbench = _progeny_workbench_model(selected_type, selected_instance) if tab == "progeny" else {}
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
        progeny_workbench=progeny_workbench,
    )


@app.get("/portal/peripherals")
def portal_peripherals():
    legacy_tab = str(request.args.get("tab") or "peripherals").strip().lower()
    if legacy_tab == "tools":
        return redirect("/portal/utilities?tab=tools", code=302)
    if legacy_tab == "vault":
        return redirect("/portal/utilities?tab=vault", code=302)
    if legacy_tab in {"progeny", "configuration"}:
        return redirect("/portal/utilities?tab=progeny&progeny_type=member", code=302)
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


@app.get("/portal/clients")
def portal_clients():
    aliases = list_aliases_for_sidebar(PRIVATE_DIR)
    records, _ = list_alias_records(PRIVATE_DIR)

    rows = []
    for record in records:
        progeny_type = str(record.get("progeny_type") or "").strip().lower()
        if not progeny_type:
            continue
        if progeny_type != "tenant" and not progeny_type.startswith("client_"):
            continue

        alias_id = str(record.get("alias_id") or "").strip()
        if not alias_id:
            continue

        rows.append(
            {
                "alias_id": alias_id,
                "client_msn_id": str(record.get("client_msn_id") or record.get("alias_host") or "").strip(),
                "progeny_type": progeny_type,
                "status": str(record.get("status") or "active").strip(),
            }
        )

    return render_template("clients.html", aliases=aliases, client_aliases=rows, msn_id=MSN_ID)


@app.get("/portal/client/<alias_id>")
def portal_client_detail(alias_id: str):
    aliases = list_aliases_for_sidebar(PRIVATE_DIR)
    try:
        alias_payload = get_alias_record(PRIVATE_DIR, alias_id)
    except (FileNotFoundError, ValueError):
        abort(404, description=f"No alias record found for alias_id={alias_id}")

    progeny_type = str(alias_payload.get("progeny_type") or "").strip().lower()
    fields = alias_payload.get("fields") if isinstance(alias_payload.get("fields"), dict) else {}

    return render_template(
        "client_detail.html",
        aliases=aliases,
        alias_id=alias_id,
        alias_payload=alias_payload,
        progeny_type=progeny_type,
        fields=fields,
        field_names=_field_names_for_alias(alias_payload),
        save_ok=False,
        msn_id=MSN_ID,
    )


@app.post("/portal/client/<alias_id>")
def portal_client_detail_save(alias_id: str):
    aliases = list_aliases_for_sidebar(PRIVATE_DIR)
    try:
        alias_payload = get_alias_record(PRIVATE_DIR, alias_id)
    except (FileNotFoundError, ValueError):
        abort(404, description=f"No alias record found for alias_id={alias_id}")

    fields = alias_payload.get("fields") if isinstance(alias_payload.get("fields"), dict) else {}
    fields = dict(fields)
    field_names = _field_names_for_alias(alias_payload)
    for name in field_names:
        fields[name] = (request.form.get(f"field_{name}") or "").strip()

    alias_payload["fields"] = fields
    _write_json(alias_path(PRIVATE_DIR, alias_id), alias_payload)

    return render_template(
        "client_detail.html",
        aliases=aliases,
        alias_id=alias_id,
        alias_payload=alias_payload,
        progeny_type=str(alias_payload.get("progeny_type") or "").strip().lower(),
        fields=fields,
        field_names=field_names,
        save_ok=True,
        msn_id=MSN_ID,
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


def _normalize_member_workbench_tab(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    return token if token in {"stream", "classwork", "people", "workflow"} else "stream"


def _load_member_workbench_profile(member_msn_id: str, progeny_type: str = "") -> Dict[str, Any]:
    token = str(member_msn_id or "").strip()
    if not token:
        return {}
    record = find_profile_by_associated_msn(PRIVATE_DIR, token, progeny_type)
    if record is None:
        return {}
    payload = record.get("payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _member_workbench_tab_items(hosted_payload: Dict[str, Any]) -> list[Dict[str, str]]:
    subject = hosted_payload.get("subject_congregation") if isinstance(hosted_payload.get("subject_congregation"), dict) else {}
    tabs = subject.get("tabs") if isinstance(subject.get("tabs"), list) else []
    out: list[Dict[str, str]] = []
    for raw in tabs:
        if isinstance(raw, str):
            tab_id = str(raw).strip().lower()
            if tab_id:
                out.append({"id": tab_id, "label": tab_id.title()})
            continue
        if not isinstance(raw, dict):
            continue
        tab_id = str(raw.get("id") or "").strip().lower()
        if not tab_id:
            continue
        out.append({"id": tab_id, "label": str(raw.get("label") or tab_id.title()).strip() or tab_id.title()})
    return out or [{"id": item["id"], "label": item["label"]} for item in HOSTED_DEFAULT_TABS]


def _member_workbench_stream_cards(member_msn_id: str) -> list[Dict[str, str]]:
    token = str(member_msn_id or "").strip()
    events = _iter_request_log_records()
    out: list[Dict[str, str]] = []
    for event in sorted(events, key=lambda item: int(item.get("ts_unix_ms") or 0), reverse=True):
        if token and not _event_contains_any(event, [token, "contract", "alias"]):
            continue
        out.append(
            {
                "title": str(event.get("type") or "event").strip() or "event",
                "summary": _event_summary(event) or "request_log event",
                "timestamp": _format_event_timestamp(event.get("ts_unix_ms")),
            }
        )
        if len(out) >= 8:
            break

    if out:
        return out
    return [
        {
            "title": "Welcome to the Member Workbench",
            "summary": "This hosted stream is ready for contract-backed alias updates and subscription notices.",
            "timestamp": _format_event_timestamp(int(datetime.now(tz=timezone.utc).timestamp() * 1000)),
        },
        {
            "title": "Orientation",
            "summary": "Use classwork, people, and workflow tabs to navigate hosted organization pages.",
            "timestamp": "",
        },
    ]


def _member_workbench_people_items(profile: Dict[str, Any], hosted_payload: Dict[str, Any]) -> list[Dict[str, str]]:
    broadcaster = hosted_payload.get("broadcaster") if isinstance(hosted_payload.get("broadcaster"), dict) else {}
    people_cfg = broadcaster.get("people") if isinstance(broadcaster.get("people"), dict) else {}
    title = str(profile.get("title") or profile.get("member_msn_id") or profile.get("msn_id") or "Member Alias").strip()
    profile_refs = profile.get("profile_refs") if isinstance(profile.get("profile_refs"), dict) else {}
    return [
        {"name": title, "role": "Alias Subject"},
        {"name": str(ACTIVE_PRIVATE_CONFIG.get("title") or "fruitful_network_development_llc"), "role": "Host Organization"},
        {"name": str(people_cfg.get("search_key") or "msn_id"), "role": "Broadcaster search key"},
        {"name": str(profile_refs.get("contact_collection_ref") or "(unset)"), "role": "Contact collection ref"},
    ]


def _member_workbench_workflow_model(member_msn_id: str, profile: Dict[str, Any], hosted_payload: Dict[str, Any]) -> Dict[str, Any]:
    token = str(member_msn_id or "").strip()
    if not token:
        return {}
    return load_member_analytics(PRIVATE_DIR, token, profile, hosted_payload)


@app.get("/portal/embed/member_workbench")
def portal_embed_member_workbench():
    member_msn_id = (request.args.get("member_msn_id") or "").strip()
    if not member_msn_id:
        abort(400, description="Missing required query param: member_msn_id")
    as_alias_id = (request.args.get("as_alias_id") or "").strip()
    progeny_type = (request.args.get("progeny_type") or "").strip().lower()
    tab = _normalize_member_workbench_tab(request.args.get("tab"))

    profile = _load_member_workbench_profile(member_msn_id, progeny_type)
    hosted_payload = read_hosted_payload(PRIVATE_DIR)
    hosted_tabs = _member_workbench_tab_items(hosted_payload)

    classwork_items = [
        {"title": "Review contract proposal flow", "due": "Today"},
        {"title": "Update alias profile JSON fields", "due": "This week"},
        {"title": "Publish progeny template revision", "due": "Next milestone"},
    ]
    people_items = _member_workbench_people_items(profile, hosted_payload)
    workflow_model = _member_workbench_workflow_model(member_msn_id, profile, hosted_payload)

    return render_template(
        "member_workbench.html",
        workspace_title="Member Workbench",
        member_msn_id=member_msn_id,
        as_alias_id=as_alias_id,
        progeny_type=progeny_type,
        active_tab=tab,
        profile=profile,
        hosted_payload=hosted_payload,
        hosted_tabs=hosted_tabs,
        stream_cards=_member_workbench_stream_cards(member_msn_id),
        classwork_items=classwork_items,
        people_items=people_items,
        workflow_model=workflow_model,
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


_CONTRACT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _is_usable_contract_id(contract_id: str) -> bool:
    token = (contract_id or "").strip()
    if not token or not _CONTRACT_ID_RE.fullmatch(token):
        return False
    lowered = token.lower()
    if "placeholder" in lowered:
        return False
    if lowered.startswith("symmetric_key_contracts_ref_"):
        return False
    return True


def _resolve_tenant_embed_params() -> Dict[str, str]:
    tenant_msn_id = (request.values.get("tenant_msn_id") or request.values.get("tenant_id") or "").strip()
    contract_id = (request.values.get("contract_id") or "").strip()
    as_alias_id = (request.values.get("as_alias_id") or request.values.get("alias_id") or "").strip()
    tab = (request.values.get("tab") or "").strip().lower() or "payments"
    theme = (request.values.get("theme") or "paper").strip().lower() or "paper"
    if tab not in {"payments", "agreement", "analytics", "blog"}:
        tab = "payments"

    alias_payload: Dict[str, Any] = {}
    if as_alias_id:
        try:
            alias_payload = get_alias_record(PRIVATE_DIR, as_alias_id)
        except Exception:
            alias_payload = {}

    if not tenant_msn_id and alias_payload:
        tenant_msn_id = _extract_tenant_msn_id(alias_payload)
    if not contract_id and alias_payload:
        contract_id = _extract_contract_id(alias_payload)

    return {
        "tenant_msn_id": tenant_msn_id,
        "contract_id": contract_id,
        "as_alias_id": as_alias_id,
        "tab": tab,
        "theme": theme,
    }


def _normalize_event_mask(raw_values: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for raw in raw_values:
        parts = str(raw or "").split(",")
        for part in parts:
            token = part.strip()
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out or ["PAYMENT.CAPTURE.COMPLETED"]


def _tenant_redirect(params: Dict[str, str], **extra: str):
    query: Dict[str, str] = {
        "tenant_msn_id": params.get("tenant_msn_id", ""),
        "contract_id": params.get("contract_id", ""),
        "as_alias_id": params.get("as_alias_id", ""),
        "tab": "payments",
        "theme": params.get("theme", "paper"),
    }
    for key, value in extra.items():
        query[key] = str(value)
    return redirect(f"/portal/embed/tenant?{urlencode(query)}")


def _render_tenant_shell(*, force_tab: Optional[str] = None):
    params = _resolve_tenant_embed_params()
    if force_tab:
        params["tab"] = force_tab

    contract_usable = _is_usable_contract_id(params["contract_id"])
    tenant_msn_id = params["tenant_msn_id"]
    profile: Dict[str, Any] = {}
    warning = ""

    if not tenant_msn_id:
        warning = "Missing tenant_msn_id for tenant configuration."
    elif not contract_usable:
        warning = "A valid contract_id is required before saving tenant PayPal configuration."
    else:
        profile = load_profile(tenant_msn_id, params["contract_id"])

    paypal = profile.get("paypal") if isinstance(profile.get("paypal"), dict) else {}
    secret_enc = paypal.get("client_secret_enc") if isinstance(paypal.get("client_secret_enc"), dict) else {}
    has_encrypted_secret = bool(secret_enc.get("ciphertext_b64") and secret_enc.get("nonce_b64"))

    status = profile.get("status") if isinstance(profile.get("status"), dict) else {}
    append_event(
        PRIVATE_DIR,
        MSN_ID,
        {
            "type": "tenant.paypal.config.viewed",
            "status": "ok",
            "tenant_msn_id": tenant_msn_id,
            "contract_id": params["contract_id"],
            "details": {"tab": params["tab"]},
        },
    )

    return render_template(
        "tenant_embed_shell.html",
        theme=params["theme"],
        tab=params["tab"],
        tenant_msn_id=tenant_msn_id,
        contract_id=params["contract_id"],
        as_alias_id=params["as_alias_id"],
        contract_usable=contract_usable,
        warning=warning,
        profile=profile,
        paypal=paypal,
        status=status,
        has_encrypted_secret=has_encrypted_secret,
        saved=(request.args.get("saved") or "").strip() == "1",
        webhook=(request.args.get("webhook") or "").strip(),
    )


@app.get("/portal/embed/tenant")
def embed_tenant():
    return _render_tenant_shell()


@app.get("/portal/embed/tenant/payments")
def embed_tenant_payments():
    return _render_tenant_shell(force_tab="payments")


@app.post("/portal/embed/tenant/payments/paypal/save")
def embed_tenant_paypal_save():
    params = _resolve_tenant_embed_params()
    if not params["tenant_msn_id"] or not _is_usable_contract_id(params["contract_id"]):
        abort(400, description="A valid tenant_msn_id and contract_id are required")

    client_id = (request.form.get("paypal_client_id") or "").strip()
    client_secret_plain = request.form.get("paypal_client_secret") or ""
    webhook_target_url = (request.form.get("webhook_target_url") or "").strip()
    webhook_event_mask = _normalize_event_mask(request.form.getlist("webhook_event_mask"))

    profile = load_profile(params["tenant_msn_id"], params["contract_id"])
    profile = set_paypal_config(
        profile,
        client_id=client_id,
        client_secret_plain=client_secret_plain,
        target_url=webhook_target_url,
        event_mask=webhook_event_mask,
    )
    save_profile(profile)

    append_event(
        PRIVATE_DIR,
        MSN_ID,
        {
            "type": "tenant.paypal.config.saved",
            "status": "ok",
            "tenant_msn_id": params["tenant_msn_id"],
            "contract_id": params["contract_id"],
            "client_id": client_id,
            "details": {
                "webhook.target_url": webhook_target_url,
                "event_mask": webhook_event_mask,
            },
        },
    )
    return _tenant_redirect(params, saved="1")


@app.post("/portal/embed/tenant/payments/paypal/webhook/register")
def embed_tenant_paypal_webhook_register():
    params = _resolve_tenant_embed_params()
    if not params["tenant_msn_id"] or not _is_usable_contract_id(params["contract_id"]):
        abort(400, description="A valid tenant_msn_id and contract_id are required")

    webhook_target_url = (request.form.get("webhook_target_url") or "").strip()
    webhook_event_mask = _normalize_event_mask(request.form.getlist("webhook_event_mask"))
    append_event(
        PRIVATE_DIR,
        MSN_ID,
        {
            "type": "tenant.paypal.webhook.register.requested",
            "status": "requested",
            "tenant_msn_id": params["tenant_msn_id"],
            "contract_id": params["contract_id"],
            "details": {
                "webhook.target_url": webhook_target_url,
                "event_mask": webhook_event_mask,
            },
        },
    )

    try:
        # Stubbed for MVP; real provider registration will be added in a follow-up.
        append_event(
            PRIVATE_DIR,
            MSN_ID,
            {
                "type": "tenant.paypal.webhook.register.completed",
                "status": "completed",
                "tenant_msn_id": params["tenant_msn_id"],
                "contract_id": params["contract_id"],
                "details": {"webhook.target_url": webhook_target_url},
            },
        )
        return _tenant_redirect(params, webhook="registered")
    except Exception as exc:
        append_event(
            PRIVATE_DIR,
            MSN_ID,
            {
                "type": "tenant.paypal.webhook.register.failed",
                "status": "failed",
                "tenant_msn_id": params["tenant_msn_id"],
                "contract_id": params["contract_id"],
                "details": {"error": str(exc)},
            },
        )
        return _tenant_redirect(params, webhook="failed")


register_config_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_aliases_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_inbox_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_contract_routes(
    app,
    private_dir=PRIVATE_DIR,
    options_private_fn=_options_private,
    anthology_path_fn=_anthology_path,
)
register_progeny_config_routes(app, options_private_fn=_options_private)
register_tenant_progeny_routes(
    app,
    private_dir=PRIVATE_DIR,
    options_private_fn=_options_private,
    msn_id_provider=lambda: MSN_ID,
)
register_aws_emailer_routes(
    app,
    private_dir=PRIVATE_DIR,
    workspace=DATA_WORKSPACE,
)
register_progeny_workbench_routes(
    app,
    private_dir=PRIVATE_DIR,
    options_private_fn=_options_private,
    msn_id_provider=lambda: MSN_ID,
)
register_website_analytics_routes(
    app,
    private_dir=PRIVATE_DIR,
    options_private_fn=_options_private,
    msn_id_provider=lambda: MSN_ID,
)
register_admin_integration_routes(
    app,
    private_dir=PRIVATE_DIR,
)
register_paypal_checkout_routes(
    app,
    private_dir=PRIVATE_DIR,
)
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
register_data_workspace_routes(
    app,
    workspace=DATA_WORKSPACE,
    aliases_provider=lambda: list_aliases_for_sidebar(PRIVATE_DIR),
    options_private_fn=_options_private,
    msn_id_provider=lambda: MSN_ID,
    include_home_redirect=False,
    include_legacy_shims=False,
)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
