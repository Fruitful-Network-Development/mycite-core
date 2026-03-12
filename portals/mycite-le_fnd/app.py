import json
import os
import re
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
from portal.api.contracts import register_contract_routes
from portal.api.data_workspace import register_data_routes as register_data_workspace_routes
from portal.api.inbox import register_inbox_routes
from portal.api.paypal_checkout import register_paypal_checkout_routes
from portal.api.progeny_config import register_progeny_config_routes
from portal.api.request_log import register_request_log_routes
from portal.api.tenant_progeny import register_tenant_progeny_routes
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
from portal.services.progeny_embed import build_embed_progeny_landing
from portal.services.progeny_config_store import get_client_config, get_config
from portal.services.request_log_store import append_event
from portal.services.tenant_progeny_store import load_profile, save_profile, set_paypal_config
from portal.tools.runtime import active_tool_for_path, read_enabled_tools, register_tool_blueprints

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "portal", "ui", "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "portal", "ui", "static"),
    static_url_path="/portal/static",
)

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
PUBLIC_DIR = Path(os.environ.get("PUBLIC_DIR", str(BASE_DIR / "public")))
PRIVATE_DIR = Path(os.environ.get("PRIVATE_DIR", str(BASE_DIR / "private")))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
FALLBACK_DIR = BASE_DIR
ICONS_DIR = REPO_ROOT / "assets" / "icons"
PORTAL_INSTANCE_ID = str(os.environ.get("PORTAL_INSTANCE_ID") or "fnd").strip().lower()


for required in (
    PRIVATE_DIR / "contracts",
    PRIVATE_DIR / "request_log",
    PRIVATE_DIR / "aliases",
    PRIVATE_DIR / "progeny" / "tenant",
    PRIVATE_DIR / "vault" / "contracts",
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
            "methods": ["GET", "POST", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
        "progeny_config": {
            "href": f"/portal/api/progeny_config/tenant?msn_id={msn_id}",
            "methods": ["GET", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
        "paypal_demo_update": {
            "href": f"/portal/api/tools/paypal_demo/update?msn_id={msn_id}",
            "methods": ["POST", "OPTIONS"],
            "auth": "keycloak_or_local",
        },
        "paypal_demo_confirm": {
            "href": f"/portal/api/tools/paypal_demo/confirm?msn_id={msn_id}",
            "methods": ["POST", "OPTIONS"],
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
        query = urlencode({"member_msn_id": member_msn_id, "as_alias_id": alias_id, "tab": "streams"})
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
                "progeny_type": _canonical_progeny_type(str(record.get("progeny_type") or "").strip()),
                "tenant_id": str(record.get("child_msn_id") or record.get("tenant_id") or "").strip(),
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
def _tool_shell_context() -> Dict[str, Any]:
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
    return jsonify({"ok": True, "service": "fnd_portal"})


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
def portal_data_root():
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
def portal_network_legacy(tab_id: str):
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
register_contract_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
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
