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
from portal.api.config import register_config_routes
from portal.api.contracts import register_contract_routes
from portal.api.data_workspace import register_data_routes
from portal.api.inbox import register_inbox_routes
from portal.api.public_inbox import register_public_inbox_routes
from portal.core_services.runtime import (
    active_service_from_path,
    active_private_config_filename,
    build_network_cards,
    build_network_tabs,
    build_service_nav,
    load_active_private_config,
    normalize_network_tab,
)
from portal.services.progeny_embed import build_embed_progeny_landing
from portal.services.policy import is_external_signed_path, is_portal_path, is_public_path
from portal.services.runtime_paths import (
    hosted_read_paths,
    keypass_db_path,
    keypass_inventory_path,
    request_log_read_paths,
    utility_peripherals_dir,
    vault_contract_read_dirs,
)
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
DEFAULT_EMBED_PORT = str(os.environ.get("DEFAULT_EMBED_PORT") or "5201").strip() or "5201"
ALIAS_EXPECTED_BY_TYPE = {
    "board_member": False,
    "poc": True,
    "constituent_farm": True,
}

AUTH_MODE = os.environ.get("AUTH_MODE", "none")  # none | keycloak (later)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to parse JSON at {path}: {e}") from e

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
    for p in paths:
        if p.exists() and p.is_file():
            return p
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
    }


def _infer_local_msn_id() -> str:
    if os.environ.get("MSN_ID"):
        return str(os.environ.get("MSN_ID")).strip()

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
TOOL_TABS = register_tool_blueprints(
    app,
    read_enabled_tools(PRIVATE_DIR, msn_id=MSN_ID or None),
    tools_dir=BASE_DIR / "portal" / "tools",
    private_dir=PRIVATE_DIR,
)
DATA_WORKSPACE = Workspace(JsonStorageBackend(DATA_DIR), config=WORKSPACE_CONFIG)
DATA_HOME_TEMPLATE = BASE_DIR / "portal" / "ui" / "templates" / "tools" / "data_tool_home.html"
DATA_HOME_AVAILABLE = DATA_HOME_TEMPLATE.exists()


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


def _sanitize_fnd_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"schema", "msn_id", "title", "summary", "logo", "banner", "links"}
    out = {key: payload.get(key) for key in allowed if key in payload}
    links = payload.get("links") if isinstance(payload.get("links"), list) else []
    out["links"] = [item for item in links if isinstance(item, dict)]
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
    for alias in list_aliases_ne(PRIVATE_DIR):
        alias_id = str(alias.get("alias_id") or "").strip()
        if not alias_id:
            continue
        out.append(
            {
                "id": alias_id,
                "label": str(alias.get("label") or alias_id).strip(),
                "org_msn_id": str(alias.get("org_msn_id") or "").strip(),
                "tenant_id": str(alias.get("tenant_id") or "").strip(),
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
    sign_out_url = str(os.environ.get("PORTAL_SIGN_OUT_URL") or "/oauth2/sign_out").strip() or "/oauth2/sign_out"
    current_path = request.full_path if request.query_string else request.path
    if current_path.endswith("?"):
        current_path = current_path[:-1]
    current_path = str(current_path or "/portal/system").strip() or "/portal/system"
    if not current_path.startswith("/"):
        current_path = "/portal/system"
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
def list_aliases_ne(private_dir: Path) -> list[Dict[str, Any]]:
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
            }
        )
    return aliases


def load_alias_ne(private_dir: Path, alias_id: str) -> Dict[str, Any]:
    return get_alias_record(private_dir, alias_id)


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


def _build_org_widget_url(alias_id: str, alias_payload: Dict[str, Any]) -> str:
    org_msn_id = str(alias_payload.get("alias_host") or "").strip()
    org_title = str(alias_payload.get("host_title") or "").strip()
    embed_port = _resolve_embed_port(org_msn_id)
    base_url = f"http://127.0.0.1:{embed_port}"

    progeny_type = str(alias_payload.get("progeny_type") or "").strip().lower()
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
    if progeny_type == "board_member" and member_msn_id:
        query = urlencode({"member_msn_id": member_msn_id, "as_alias_id": alias_id, "tab": "feed"})
        return f"{base_url}/portal/embed/board_member?{query}"

    query = urlencode({"org_msn_id": org_msn_id, "as_alias_id": alias_id, "org_title": org_title})
    return f"{base_url}/portal/embed/poc?{query}"


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
    cfg_paths = sorted(PRIVATE_DIR.glob("mycite-config-*.json"))
    for cfg_path in cfg_paths:
        try:
            cfg = _read_json_relaxed(cfg_path)
        except Exception:
            continue
        progeny_entries = cfg.get("progeny")
        if not isinstance(progeny_entries, list):
            continue
        for entry in progeny_entries:
            if not isinstance(entry, dict) or not entry:
                continue
            progeny_type, ref_value = next(iter(entry.items()))
            progeny_type = str(progeny_type or "").strip().lower()
            ref_token = str(ref_value or "").strip()
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


def _ensure_runtime_scaffold() -> None:
    utility_peripherals_dir(PRIVATE_DIR).mkdir(parents=True, exist_ok=True)
    keypass_inventory_path(PRIVATE_DIR).parent.mkdir(parents=True, exist_ok=True)
    _seed_missing_local_progeny_profiles()


def _sanitize_public_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"msn_id", "schema", "title", "public_key", "entity_type", "accessible"}
    out = {k: payload.get(k) for k in allowed if k in payload}
    out.setdefault("accessible", {})
    return out


_ensure_runtime_scaffold()


def require_auth_if_enabled() -> None:
    if AUTH_MODE == "none":
        return
    if AUTH_MODE == "keycloak":
        raise RuntimeError("AUTH_MODE=keycloak set but token verification not implemented")
    raise RuntimeError(f"Unknown AUTH_MODE={AUTH_MODE}")


@app.before_request
def enforce_boundaries() -> None:
    path = request.path
    if is_portal_path(path):
        require_auth_if_enabled()
    elif is_external_signed_path(path):
        return
    elif is_public_path(path):
        return


@app.get("/<msn_id>.json")
def public_contact_card(msn_id: str):
    path = _resolve_public_profile_path(msn_id)
    if not path:
        abort(404, description=f"No public profile JSON found for msn_id={msn_id}")

    raw = _read_json(path)
    limited = _sanitize_public_profile(raw)
    limited["options_public"] = _options_public(msn_id)
    return jsonify(limited)


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


def _render_portal_home():
    return _render_portal_system()


def _tools_by_mount_target(mount_target: str) -> list[Dict[str, Any]]:
    token = str(mount_target or "").strip().lower()
    return [tool for tool in TOOL_TABS if str(tool.get("mount_target") or "peripherals.tools").strip().lower() == token]


def _render_portal_system():
    aliases = list_aliases_ne(PRIVATE_DIR)
    profile_model = _portal_profile_model()
    try:
        return render_template(
            "services/system.html",
            aliases=aliases,
            msn_id=MSN_ID,
            data_home_available=DATA_HOME_AVAILABLE,
            portal_profile=profile_model,
            system_profile_json=json.dumps(profile_model.get("public_profile") or {}, indent=2, sort_keys=True),
        )
    except TemplateNotFound:
        return "<h1>MyCite Portal</h1><p>system.html missing</p>"


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
    hosted_payload = _read_hosted_payload()
    message_feed = _network_message_feed(kind, selected_alias, selected_log, selected_p2p)
    return render_template(
        "services/network.html",
        aliases=list_aliases_ne(PRIVATE_DIR),
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
        aliases=list_aliases_ne(PRIVATE_DIR),
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
    aliases = list_aliases_ne(PRIVATE_DIR)
    try:
        alias_payload = load_alias_ne(PRIVATE_DIR, alias_id)
    except (FileNotFoundError, ValueError):
        abort(404, description=f"No alias record found for alias_id={alias_id}")

    org_msn_id = str(alias_payload.get("alias_host") or "").strip()
    org_title = str(alias_payload.get("host_title") or "").strip()
    progeny_type = str(alias_payload.get("progeny_type") or "").strip().lower()
    tenant_id = str(alias_payload.get("child_msn_id") or alias_payload.get("tenant_id") or "").strip()

    return render_template(
        "alias_shell.html",
        aliases=aliases,
        active_alias_id=alias_id,
        alias_label=_alias_label(alias_payload, alias_id),
        org_title=org_title,
        org_msn_id=org_msn_id,
        org_widget_url=_build_org_widget_url(alias_id, alias_payload),
        msn_id=str(alias_payload.get("msn_id") or "").strip(),
        alias_progeny_type=progeny_type,
        alias_tenant_id=tenant_id,
    )


@app.get("/portal/embed/progeny")
def portal_embed_progeny():
    aliases = list_aliases_ne(PRIVATE_DIR)
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
        widget_url_builder=_build_org_widget_url,
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


register_config_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_aliases_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_inbox_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_contract_routes(app, private_dir=PRIVATE_DIR, options_private_fn=_options_private)
register_public_inbox_routes(app, private_dir=PRIVATE_DIR, public_dir=PUBLIC_DIR, data_dir=DATA_DIR)
register_data_routes(
    app,
    workspace=DATA_WORKSPACE,
    aliases_provider=lambda: list_aliases_ne(PRIVATE_DIR),
    options_private_fn=_options_private,
    msn_id_provider=lambda: MSN_ID,
    include_home_redirect=False,
    include_legacy_shims=True,
)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
