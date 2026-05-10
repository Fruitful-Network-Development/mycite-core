"""Portal surface catalog and tool registry builders and resolvers."""

from __future__ import annotations

from MyCiteV2.packages.core.scalars import as_text

from .shell_schemas import (
    CTS_GIS_TOOL_ENTRYPOINT_ID,
    CTS_GIS_TOOL_ROUTE,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_CSM_TOOL_ENTRYPOINT_ID,
    FND_CSM_TOOL_ROUTE,
    FND_CSM_TOOL_SURFACE_ID,
    NETWORK_ROOT_ROUTE,
    NETWORK_ROOT_SURFACE_ID,
    REDUCER_OWNED_SURFACE_IDS,
    SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
    SYSTEM_ROOT_ROUTE,
    SYSTEM_ROOT_SURFACE_ID,
    TOOL_KIND_GENERAL,
    TOOL_KIND_SERVICE,
    TOOL_SURFACE_IDS,
    UTILITIES_INTEGRATIONS_ROUTE,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_ROUTE,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_ROUTE,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
    WORKBENCH_UI_TOOL_ROUTE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
)
from .shell_state import (
    PortalSurfaceCatalogEntry,
    PortalToolRegistryEntry,
)


def build_portal_surface_catalog() -> tuple[PortalSurfaceCatalogEntry, ...]:
    return (
        PortalSurfaceCatalogEntry(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            label="System",
            route=SYSTEM_ROOT_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="system_workspace",
            page_owner="system",
            default_surface=True,
        ),
        PortalSurfaceCatalogEntry(
            surface_id=NETWORK_ROOT_SURFACE_ID,
            label="Network",
            route=NETWORK_ROOT_ROUTE,
            root_surface_id=NETWORK_ROOT_SURFACE_ID,
            surface_kind="network_root",
            page_owner="network",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_ROOT_SURFACE_ID,
            label="Utilities",
            route=UTILITIES_ROOT_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_root",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
            label="Tool Exposure",
            route=UTILITIES_TOOL_EXPOSURE_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_tool_exposure",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_INTEGRATIONS_SURFACE_ID,
            label="Integrations",
            route=UTILITIES_INTEGRATIONS_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_integrations",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            label="CTS-GIS",
            route=CTS_GIS_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="cts_gis",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=FND_CSM_TOOL_SURFACE_ID,
            label="FND-CSM",
            route=FND_CSM_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="fnd_csm",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            label="Workbench UI",
            route=WORKBENCH_UI_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="workbench_ui",
        ),
    )


def build_portal_tool_registry_entries() -> tuple[PortalToolRegistryEntry, ...]:
    return (
        PortalToolRegistryEntry(
            tool_id="fnd_csm",
            label="FND-CSM",
            surface_id=FND_CSM_TOOL_SURFACE_ID,
            entrypoint_id=FND_CSM_TOOL_ENTRYPOINT_ID,
            route=FND_CSM_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            summary="Grantee service management — email, analytics, newsletter, and PayPal.",
        ),
        PortalToolRegistryEntry(
            tool_id="cts_gis",
            label="CTS-GIS",
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            entrypoint_id=CTS_GIS_TOOL_ENTRYPOINT_ID,
            route=CTS_GIS_TOOL_ROUTE,
            tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
            read_write_posture="write",
            required_capabilities=("datum_recognition", "spatial_projection"),
            default_workbench_visible=True,
            summary="Spatial mediation with staged validation, preview, and apply diagnostics.",
        ),
        PortalToolRegistryEntry(
            tool_id="workbench_ui",
            label="Workbench UI",
            surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            entrypoint_id=WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
            route=WORKBENCH_UI_TOOL_ROUTE,
            tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("datum_recognition",),
            default_enabled=True,
            default_workbench_visible=True,
            summary="Read-only SQL datum grid with additive directive-overlay inspection.",
        ),
    )


def resolve_portal_surface(surface_id: object) -> PortalSurfaceCatalogEntry | None:
    normalized_surface_id = as_text(surface_id)
    for entry in build_portal_surface_catalog():
        if entry.surface_id == normalized_surface_id:
            return entry
    return None


def resolve_portal_tool_registry_entry(tool_id: object = "", *, surface_id: object = "") -> PortalToolRegistryEntry | None:
    normalized_tool_id = as_text(tool_id)
    normalized_surface_id = as_text(surface_id)
    for entry in build_portal_tool_registry_entries():
        if normalized_tool_id and entry.tool_id == normalized_tool_id:
            return entry
        if normalized_surface_id and entry.surface_id == normalized_surface_id:
            return entry
    return None


def canonical_route_for_surface(surface_id: object) -> str:
    entry = resolve_portal_surface(surface_id)
    return entry.route if entry is not None else SYSTEM_ROOT_ROUTE


def surface_root_id(surface_id: object) -> str:
    entry = resolve_portal_surface(surface_id)
    return entry.root_surface_id if entry is not None else SYSTEM_ROOT_SURFACE_ID


def is_tool_surface(surface_id: object) -> bool:
    return as_text(surface_id) in TOOL_SURFACE_IDS


def requires_shell_state_machine(surface_id: object) -> bool:
    return as_text(surface_id) in REDUCER_OWNED_SURFACE_IDS
