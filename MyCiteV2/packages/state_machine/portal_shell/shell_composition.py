"""Portal shell composition, posture, and region layout helpers."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.scalars import as_text

from .shell_schemas import (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_DCM_TOOL_SURFACE_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    PAYPAL_CSM_TOOL_SURFACE_ID,
    PORTAL_SCOPE_DEFAULT_ID,
    PORTAL_SHELL_COMPOSITION_SCHEMA,
    PORTAL_SHELL_REGION_ACTIVITY_BAR_SCHEMA,
    PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    VERB_MEDIATE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
)
from .shell_state import (
    PortalShellState,
)
from .shell_registry import (
    is_tool_surface,
    resolve_portal_tool_registry_entry,
    surface_root_id,
)


def activity_icon_id_for_surface(surface_id: object) -> str:
    normalized_surface_id = as_text(surface_id)
    if normalized_surface_id == SYSTEM_ROOT_SURFACE_ID:
        return "system"
    if normalized_surface_id == NETWORK_ROOT_SURFACE_ID:
        return "network"
    if normalized_surface_id in {UTILITIES_ROOT_SURFACE_ID, UTILITIES_TOOL_EXPOSURE_SURFACE_ID, UTILITIES_INTEGRATIONS_SURFACE_ID}:
        return "utilities"
    if normalized_surface_id in {
        AWS_CSM_TOOL_SURFACE_ID,
    }:
        return "aws"
    if normalized_surface_id == CTS_GIS_TOOL_SURFACE_ID:
        return "cts_gis"
    if normalized_surface_id == FND_DCM_TOOL_SURFACE_ID:
        return "fnd_dcm"
    if normalized_surface_id == FND_EBI_TOOL_SURFACE_ID:
        return "fnd_ebi"
    if normalized_surface_id == PAYPAL_CSM_TOOL_SURFACE_ID:
        return "paypal_csm"
    if normalized_surface_id == WORKBENCH_UI_TOOL_SURFACE_ID:
        return "workbench_ui"
    return "generic"


def map_surface_to_active_service(active_surface_id: str) -> str:
    root_id = surface_root_id(active_surface_id)
    if root_id == NETWORK_ROOT_SURFACE_ID:
        return "network"
    if root_id == UTILITIES_ROOT_SURFACE_ID:
        return "utilities"
    return "system"


def shell_composition_mode_for_surface(active_surface_id: str) -> str:
    if is_tool_surface(active_surface_id):
        return "tool"
    return "system"


def surface_posture_for_surface(active_surface_id: str) -> str:
    if is_tool_surface(active_surface_id):
        entry = resolve_portal_tool_registry_entry(surface_id=active_surface_id)
        if entry is not None:
            return entry.surface_posture
    return SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY


def default_workbench_visible_for_surface(active_surface_id: str) -> bool:
    if is_tool_surface(active_surface_id):
        entry = resolve_portal_tool_registry_entry(surface_id=active_surface_id)
        if entry is not None:
            return entry.default_workbench_visible
        return False
    return True


def foreground_region_for_surface(
    active_surface_id: str,
    *,
    shell_state: PortalShellState | dict[str, Any] | None = None,
    workbench_visible: bool = True,
) -> str:
    if is_tool_surface(active_surface_id):
        if workbench_visible and default_workbench_visible_for_surface(active_surface_id):
            return "center-workbench"
        return "interface-panel"
    if active_surface_id == SYSTEM_ROOT_SURFACE_ID and isinstance(shell_state, (PortalShellState, dict)):
        state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
        if state.verb == VERB_MEDIATE and state.chrome.interface_panel_open:
            return "interface-panel"
    if not workbench_visible:
        return "interface-panel"
    return "center-workbench"


def apply_surface_posture_to_composition(composition: dict[str, Any]) -> None:
    if not isinstance(composition, dict):
        return
    active_surface_id = as_text(composition.get("active_surface_id"))
    regions = composition.get("regions")
    if not isinstance(regions, dict):
        return
    workbench = regions.get("workbench")
    interface_panel = regions.get("interface_panel")
    if not isinstance(workbench, dict) or not isinstance(interface_panel, dict):
        return
    workbench_visible = workbench.get("visible", True) is not False
    shell_state = composition.get("shell_state") if isinstance(composition.get("shell_state"), dict) else None
    composition["foreground_shell_region"] = foreground_region_for_surface(
        active_surface_id,
        shell_state=shell_state,
        workbench_visible=workbench_visible,
    )


def _region_visible(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    return value is not False


def build_shell_composition_payload(
    *,
    active_surface_id: str,
    portal_instance_id: str,
    page_title: str,
    page_subtitle: str,
    activity_items: list[dict[str, Any]],
    control_panel: dict[str, Any],
    workbench: dict[str, Any],
    interface_panel: dict[str, Any],
    shell_state: PortalShellState | dict[str, Any] | None = None,
    control_panel_collapsed: bool = False,
) -> dict[str, Any]:
    state = shell_state if isinstance(shell_state, PortalShellState) else (
        PortalShellState.from_value(shell_state) if isinstance(shell_state, dict) else None
    )
    tool_surface = is_tool_surface(active_surface_id)
    posture = surface_posture_for_surface(active_surface_id)
    workbench_region = dict(workbench or {})
    workbench_region.setdefault("schema", PORTAL_SHELL_REGION_WORKBENCH_SCHEMA)
    interface_panel_region = dict(interface_panel or {})
    interface_panel_region.setdefault("schema", PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA)
    workbench_visible = _region_visible(
        workbench_region.get("visible"),
        default=default_workbench_visible_for_surface(active_surface_id),
    )
    force_workbench_visible = workbench_region.get("forced_visible") is True
    interface_open = bool(tool_surface)
    if not interface_open and state is not None:
        interface_open = state.chrome.interface_panel_open and state.verb == VERB_MEDIATE
    requested_interface_panel_visible = interface_panel_region.get("visible") is True
    if tool_surface:
        # First-load tool posture is composition-owned. Runtime payload visibility
        # hints are treated as content metadata, not posture authority, except for
        # explicit forced-visible diagnostic workbench flows such as staged preview/apply.
        if posture == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY:
            workbench_visible = bool(force_workbench_visible or default_workbench_visible_for_surface(active_surface_id))
            interface_panel_visible = True
        else:
            workbench_visible = bool(force_workbench_visible or default_workbench_visible_for_surface(active_surface_id))
            interface_panel_visible = True
    else:
        interface_panel_visible = bool(interface_open or requested_interface_panel_visible)
    workbench_region["visible"] = workbench_visible
    interface_panel_region["visible"] = interface_panel_visible
    interface_panel_primary = bool(
        interface_open
        and posture == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY
        and not default_workbench_visible_for_surface(active_surface_id)
    )
    interface_panel_region["primary_surface"] = bool(
        interface_panel_primary or interface_panel_region.get("primary_surface") is True
    )
    interface_panel_region["layout_mode"] = (
        "dominant"
        if interface_panel_primary
        else (as_text(interface_panel_region.get("layout_mode")) or "sidebar")
    )
    interface_panel_collapsed = not interface_panel_visible
    workbench_collapsed = not bool(workbench_visible)
    workbench_region["collapsed"] = workbench_collapsed
    interface_panel_region["collapsed"] = interface_panel_collapsed
    composition = {
        "schema": PORTAL_SHELL_COMPOSITION_SCHEMA,
        "composition_mode": shell_composition_mode_for_surface(active_surface_id),
        "active_service": map_surface_to_active_service(active_surface_id),
        "active_surface_id": as_text(active_surface_id),
        "active_tool_surface_id": as_text(active_surface_id) if is_tool_surface(active_surface_id) else None,
        "foreground_shell_region": foreground_region_for_surface(
            active_surface_id,
            shell_state=state,
            workbench_visible=workbench_visible,
        ),
        "control_panel_collapsed": bool(control_panel_collapsed),
        "interface_panel_collapsed": interface_panel_collapsed,
        "workbench_collapsed": workbench_collapsed,
        "portal_instance_id": as_text(portal_instance_id) or PORTAL_SCOPE_DEFAULT_ID,
        "page_title": as_text(page_title) or "MyCite",
        "page_subtitle": as_text(page_subtitle),
        "shell_state": None if state is None else state.to_dict(),
        "regions": {
            "activity_bar": {
                "schema": PORTAL_SHELL_REGION_ACTIVITY_BAR_SCHEMA,
                "dispatch": "post_portal_shell",
                "items": list(activity_items),
            },
            "control_panel": dict(control_panel or {}),
            "workbench": workbench_region,
            "interface_panel": interface_panel_region,
        },
    }
    apply_surface_posture_to_composition(composition)
    return composition
