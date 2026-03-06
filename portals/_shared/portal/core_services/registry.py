from __future__ import annotations

from typing import Any

from .models import NetworkTabItem, ServiceNavItem

DEFAULT_SERVICE_ORDER = ["home", "data", "network", "tools", "inbox"]
SERVICE_LABELS = {
    "home": "Home",
    "data": "Data",
    "network": "Network",
    "tools": "Tools",
    "inbox": "Inbox",
}

NETWORK_TAB_ORDER = ["contracts", "magnetlinks", "progeny", "alias"]
NETWORK_TAB_LABELS = {
    "contracts": "Contracts",
    "magnetlinks": "Magnetlinks",
    "progeny": "Progeny",
    "alias": "Alias",
}


def _safe_tokens(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        token = item.strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def resolve_service_order(config: dict[str, Any]) -> list[str]:
    configured = [t for t in _safe_tokens(config.get("enabled_services")) if t in SERVICE_LABELS]
    if configured:
        return configured
    return list(DEFAULT_SERVICE_ORDER)


def normalize_network_tab(tab_id: str) -> str:
    token = str(tab_id or "").strip().lower()
    if token in NETWORK_TAB_ORDER:
        return token
    return NETWORK_TAB_ORDER[0]


def service_href(service_id: str) -> str:
    token = str(service_id or "").strip().lower()
    if token == "home":
        return "/portal/home"
    if token == "data":
        return "/portal/data"
    if token == "network":
        return "/portal/network/contracts"
    if token == "tools":
        return "/portal/tools"
    if token == "inbox":
        return "/portal/inbox"
    return "/portal/home"


def build_service_nav(config: dict[str, Any], *, active_service: str) -> list[ServiceNavItem]:
    active = str(active_service or "home").strip().lower()
    nav: list[ServiceNavItem] = []
    for service_id in resolve_service_order(config):
        nav.append(
            {
                "service_id": service_id,
                "label": SERVICE_LABELS.get(service_id, service_id.title()),
                "href": service_href(service_id),
                "active": service_id == active,
            }
        )
    return nav


def build_network_tabs(active_tab: str) -> list[NetworkTabItem]:
    active = normalize_network_tab(active_tab)
    out: list[NetworkTabItem] = []
    for tab_id in NETWORK_TAB_ORDER:
        out.append(
            {
                "tab_id": tab_id,
                "label": NETWORK_TAB_LABELS.get(tab_id, tab_id.title()),
                "href": f"/portal/network/{tab_id}",
                "active": tab_id == active,
            }
        )
    return out


def active_service_from_path(path: str) -> str:
    token = str(path or "").strip().lower()
    if token.startswith("/portal/network"):
        return "network"
    if token.startswith("/portal/data"):
        return "data"
    if token.startswith("/portal/tools"):
        return "tools"
    if token.startswith("/portal/inbox"):
        return "inbox"
    if token.startswith("/portal/home"):
        return "home"
    if token == "/portal":
        return "home"
    return "home"
