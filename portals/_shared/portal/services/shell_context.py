from __future__ import annotations

from typing import Any


def build_shell_context(
    *,
    active_service: str,
    active_service_tab: str,
    active_tool: dict[str, Any] | None,
    tool_tabs: list[dict[str, Any]],
    service_nav: list[dict[str, Any]],
    network_tabs: list[dict[str, Any]],
    sidebar_progeny: list[dict[str, Any]],
    portal_name: str,
    active_portal_username: str,
    sign_out_url: str,
    switch_portal_url: str,
    current_path: str,
    control_panel_sections: list[dict[str, Any]],
    shell_verbs: list[dict[str, Any]] | None = None,
    portal_instance_context: dict[str, Any] | None = None,
    activity_tool_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_tool_id = str(active_tool.get("tool_id") or "") if active_tool else ""
    return {
        "tool_tabs": tool_tabs,
        "active_tool": active_tool,
        "active_tool_id": active_tool_id,
        "service_nav": service_nav,
        "active_service": active_service,
        "active_service_tab": active_service_tab,
        "network_tabs": network_tabs,
        "sidebar_progeny": sidebar_progeny,
        "portal_name": portal_name,
        "active_portal_username": active_portal_username,
        "sign_out_url": sign_out_url,
        "switch_portal_url": switch_portal_url,
        "current_path": current_path,
        "control_panel_sections": control_panel_sections,
        "shell_verbs": list(shell_verbs or []),
        "portal_instance_context": dict(portal_instance_context or {}),
        "activity_tool_links": list(activity_tool_links or []),
    }
