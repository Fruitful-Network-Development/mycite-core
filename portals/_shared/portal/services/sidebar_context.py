from __future__ import annotations

from typing import Any


def build_context_sidebar_sections(
    *,
    active_service: str,
    network_tab: str,
    network_kind: str,
    utilities_tab: str,
    selected_id: str,
    tool_tabs: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
    p2p_channels: list[dict[str, Any]],
    include_alias_interfaces: bool,
    include_progeny_utility: bool,
    progeny_type_entries: list[dict[str, Any]] | None = None,
    local_msn_id: str = "",
) -> list[dict[str, Any]]:
    token = str(active_service or "system").strip().lower()
    progeny_type_entries = list(progeny_type_entries or [])

    active_tool_meta = next(
        (t for t in tool_tabs if str(t.get("tool_id") or "").strip().lower() == token),
        None,
    )
    if active_tool_meta:
        display_name = str(active_tool_meta.get("display_name") or active_tool_meta.get("tool_id") or token).strip() or token
        home_path = str(active_tool_meta.get("home_path") or "").strip() or f"/portal/tools/{token}/home"
        return [
            {
                "title": "Tool",
                "entries": [
                    {"label": f"Using {display_name}", "href": home_path, "active": True, "meta": "tool home"},
                    {"label": "Configure tools", "href": "/portal/utilities?tab=tools", "active": False, "meta": "Utilities"},
                ],
                "empty_text": "",
            }
        ]

    if token == "network":
        sections: list[dict[str, Any]] = []
        if include_alias_interfaces and aliases:
            sections.append(
                {
                    "title": "Alias Interfaces",
                    "entries": [
                        {
                            "label": item["label"],
                            "meta": item.get("org_msn_id") or "",
                            "href": item["href"],
                            "active": network_tab == "messages" and network_kind == "alias" and selected_id == item["id"],
                        }
                        for item in aliases
                    ],
                    "empty_text": "No aliases loaded",
                }
            )
        sections.append(
            {
                "title": "Direct Messages",
                "entries": [
                    {
                        "label": item["label"],
                        "meta": f"{item['event_count']} event(s)",
                        "href": item["href"],
                        "active": network_tab == "messages" and network_kind == "p2p" and selected_id == item["id"],
                    }
                    for item in p2p_channels
                ],
                "empty_text": "No P2P channels derived yet",
            }
        )
        return sections

    if token == "utilities":
        utility_entries = [
            {"label": "Tools", "href": "/portal/utilities?tab=tools", "active": utilities_tab == "tools", "meta": "launchers + mounts"},
            {"label": "Vault", "href": "/portal/utilities?tab=vault", "active": utilities_tab == "vault", "meta": "KeePass inventory"},
            {"label": "Peripherals", "href": "/portal/utilities?tab=peripherals", "active": utilities_tab == "peripherals", "meta": "runtime directory"},
        ]
        if include_progeny_utility:
            utility_entries.append(
                {
                    "label": "Progeny",
                    "href": "/portal/utilities?tab=progeny&progeny_type=member",
                    "active": utilities_tab == "progeny",
                    "meta": "templates + instances",
                }
            )
        sections = [{"title": "Utility Views", "entries": utility_entries, "empty_text": ""}]
        if include_progeny_utility:
            sections.append(
                {
                    "title": "Progeny Types",
                    "entries": progeny_type_entries,
                    "empty_text": "Select the Progeny utility view to browse templates and instances.",
                }
            )
        return sections

    return [
        {
            "title": "Profile",
            "entries": [
                {"label": "Portal Contact Card", "href": "/portal/system", "active": True, "meta": f"msn-{local_msn_id}.json"},
                {"label": "Data Workbench", "href": "/portal/system#data-workbench", "active": False, "meta": "Anthology/NIMM/AITAS"},
            ],
            "empty_text": "",
        }
    ]
