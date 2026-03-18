from __future__ import annotations

import re
from typing import Any, TypedDict

_TOOL_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class ServiceNavItem(TypedDict):
    service_id: str
    label: str
    href: str
    icon: str
    active: bool


class NetworkTabItem(TypedDict):
    tab_id: str
    label: str
    href: str
    active: bool


class SystemTabItem(TypedDict):
    tab_id: str
    label: str
    href: str
    active: bool

DEFAULT_SERVICE_ORDER = ["network", "utilities", "system"]
SERVICE_LABELS = {
    "system": "SYSTEM",
    "network": "NETWORK",
    "utilities": "UTILITIES",
}
SERVICE_ICONS = {
    "system": "/portal/static/icons/ui/home.svg",
    "network": "/portal/static/icons/ui/network.svg",
    "utilities": "/portal/static/icons/ui/inbox.svg",
}

NETWORK_TAB_ORDER = ["messages", "hosted", "profile", "contracts"]
NETWORK_TAB_LABELS = {
    "messages": "Messages",
    "hosted": "Hosted",
    "profile": "Profile",
    "contracts": "Contracts",
}

SYSTEM_TAB_ORDER = ["workbench", "local_resources", "inheritance"]
SYSTEM_TAB_LABELS = {
    "workbench": "Workbench",
    "local_resources": "Local Resources",
    "inheritance": "Inheritance",
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


def normalize_system_tab(tab_id: str) -> str:
    token = str(tab_id or "").strip().lower()
    # Compatibility alias during system tab migration.
    if token == "sandbox":
        token = "local_resources"
    if token in SYSTEM_TAB_ORDER:
        return token
    return SYSTEM_TAB_ORDER[0]


def service_href(service_id: str) -> str:
    token = str(service_id or "").strip().lower()
    if token == "system":
        return "/portal/system"
    if token == "network":
        return "/portal/network"
    if token == "utilities":
        return "/portal/utilities"
    if token == "peripherals":
        return "/portal/utilities?tab=peripherals"
    return "/portal/system"


def build_service_nav(config: dict[str, Any], *, active_service: str) -> list[ServiceNavItem]:
    active = str(active_service or "system").strip().lower()
    nav: list[ServiceNavItem] = []
    for service_id in resolve_service_order(config):
        nav.append(
            {
                "service_id": service_id,
                "label": SERVICE_LABELS.get(service_id, service_id.title()),
                "href": service_href(service_id),
                "icon": SERVICE_ICONS.get(service_id, ""),
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
                "href": f"/portal/network?tab={tab_id}",
                "active": tab_id == active,
            }
        )
    return out


def build_system_tabs(active_tab: str) -> list[SystemTabItem]:
    active = normalize_system_tab(active_tab)
    out: list[SystemTabItem] = []
    for tab_id in SYSTEM_TAB_ORDER:
        out.append(
            {
                "tab_id": tab_id,
                "label": SYSTEM_TAB_LABELS.get(tab_id, tab_id.title()),
                "href": f"/portal/system?tab={tab_id}",
                "active": tab_id == active,
            }
        )
    return out


def active_service_from_path(path: str) -> str:
    token = str(path or "").strip().lower()
    if token.startswith("/portal/peripherals"):
        return "utilities"
    if token.startswith("/portal/peripheral"):
        return "utilities"
    if token.startswith("/portal/clients"):
        return "network"
    if token.startswith("/portal/client/"):
        return "network"
    if token.startswith("/portal/alias/"):
        return "network"
    if token.startswith("/portal/utilities"):
        return "utilities"
    if token.startswith("/portal/network"):
        return "network"
    if token.startswith("/portal/inbox"):
        return "network"
    if token.startswith("/portal/data"):
        return "system"
    if token.startswith("/portal/tools/"):
        rest = token[len("/portal/tools/"):].lstrip("/")
        parts = rest.split("/")
        if parts and parts[0] and _TOOL_ID_RE.match(parts[0]):
            return parts[0].lower()
    if token.startswith("/portal/tools"):
        return "utilities"
    if token.startswith("/portal/vault"):
        return "utilities"
    if token.startswith("/portal/home"):
        return "system"
    if token.startswith("/portal/system"):
        return "system"
    if token == "/portal":
        return "system"
    return "system"
