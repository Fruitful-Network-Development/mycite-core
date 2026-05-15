"""Portal shell composition, posture, and region layout helpers."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.scalars import as_text

from .shell_registry import (
    is_tool_surface,
    resolve_portal_tool_registry_entry,
    surface_root_id,
)
from .shell_schemas import (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_DCM_TOOL_SURFACE_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    PAYPAL_CSM_TOOL_SURFACE_ID,
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


# Phase 12b: build_shell_composition_payload was duplicated here and in
# shell.py. The canonical definition lives in shell.py (re-exported through
# the package __init__.py via `from .shell import *`). This module keeps the
# helpers it uniquely owns: apply_surface_posture_to_composition,
# foreground_region_for_surface, _region_visible, plus the surface-posture
# lookup helpers above.
