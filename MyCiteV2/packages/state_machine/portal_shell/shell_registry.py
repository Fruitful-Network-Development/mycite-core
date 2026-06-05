"""Portal surface catalog and tool registry builders and resolvers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from MyCiteV2.packages.core.scalars import as_text

if TYPE_CHECKING:
    # Lazy at runtime to break the circular import with shell.py (Phase 12a).
    from .shell import PortalToolRegistryEntry

from .shell_schemas import (
    AGRO_ERP_TOOL_ENTRYPOINT_ID,
    AGRO_ERP_TOOL_ROUTE,
    AGRO_ERP_TOOL_SURFACE_ID,
    NETWORK_ROOT_ROUTE,
    NETWORK_ROOT_SURFACE_ID,
    REDUCER_OWNED_SURFACE_IDS,
    SURFACE_POSTURE_PALETTE_TARGET,
    SYSTEM_ROOT_ROUTE,
    SYSTEM_ROOT_SURFACE_ID,
    TOOL_KIND_GENERAL,
    TOOL_KIND_SERVICE,
    TOOL_SURFACE_IDS,
    UTILITIES_EXTENSIONS_ROUTE,
    UTILITIES_EXTENSIONS_SURFACE_ID,
    UTILITIES_GRANTEE_PROFILE_ROUTE,
    UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
    UTILITIES_PERIPHERALS_ROUTE,
    UTILITIES_PERIPHERALS_SURFACE_ID,
    UTILITIES_ROOT_ROUTE,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_ROUTE,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    UTILITIES_TOOLS_ROUTE,
    UTILITIES_TOOLS_SURFACE_ID,
    WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
    WORKBENCH_UI_TOOL_ROUTE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
)
from .shell_state import PortalSurfaceCatalogEntry

# Phase 12a: PortalToolRegistryEntry now lives canonically in shell.py only.
# Top-level import would create a cycle (shell.py imports this module at
# module load), so the functions below resolve the class lazily.


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
        # Phase 14b: four dedicated Utilities surfaces. The legacy
        # tool-exposure entry above remains registered for one transition
        # cycle so
        # external bookmarks resolve via a 302 redirect at the HTTP layer.
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_EXTENSIONS_SURFACE_ID,
            label="Extensions",
            route=UTILITIES_EXTENSIONS_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_extensions",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
            label="Grantee Profile",
            route=UTILITIES_GRANTEE_PROFILE_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_grantee_profile",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_TOOLS_SURFACE_ID,
            label="Tools",
            route=UTILITIES_TOOLS_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_tools",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_PERIPHERALS_SURFACE_ID,
            label="Peripherals",
            route=UTILITIES_PERIPHERALS_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_peripherals",
            page_owner="utilities",
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
        PortalSurfaceCatalogEntry(
            surface_id=AGRO_ERP_TOOL_SURFACE_ID,
            label="Agro-ERP",
            route=AGRO_ERP_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="agro_erp",
        ),
    )


def build_portal_tool_registry_entries() -> tuple[PortalToolRegistryEntry, ...]:
    from .shell import PortalToolRegistryEntry  # lazy to break import cycle
    return (
        PortalToolRegistryEntry(
            tool_id="agro_erp",
            label="Agro-ERP",
            surface_id=AGRO_ERP_TOOL_SURFACE_ID,
            entrypoint_id=AGRO_ERP_TOOL_ENTRYPOINT_ID,
            route=AGRO_ERP_TOOL_ROUTE,
            tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            required_capabilities=("datum_recognition",),
            default_workbench_visible=True,
            # Plain datum-workbench surface (no spatial projection). Eligible
            # only for documents whose archetype is the agro_erp taxonomy row,
            # so cts_gis / samras_family documents don't accidentally pick up
            # agro_erp in the palette. See
            # docs/contracts/agro_erp_workbench_contract.md.
            applies_to_archetype=("agro_erp_taxonomy_row",),
            manipulates_datum_kinds=("sandbox_source",),
            summary="Agro-ERP taxonomy and source-document workbench (MOS-backed).",
        ),
        PortalToolRegistryEntry(
            tool_id="workbench_ui",
            label="Workbench UI",
            surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            entrypoint_id=WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
            route=WORKBENCH_UI_TOOL_ROUTE,
            tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="read-only",
            required_capabilities=("datum_recognition",),
            default_enabled=True,
            default_workbench_visible=True,
            # Workbench UI is the universal datum grid; appears in the palette
            # for both sandbox-source and system-anthology documents.
            applies_to_source_kind=("sandbox_source", "system_anthology"),
            summary="Read-only SQL datum grid with additive directive-overlay inspection.",
        ),
        # Utilities extensions — Phase 2 migration of former FND-CSM tabs.
        # Renderers live in utilities_extensions.EXTENSION_RENDERERS; see
        # portal_tool_surface_contract.md.
        PortalToolRegistryEntry(
            tool_id="ext_aws_email",
            label="Email",
            surface_id=UTILITIES_EXTENSIONS_SURFACE_ID,
            entrypoint_id="portal.utilities.ext_aws_email",
            route=UTILITIES_EXTENSIONS_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            is_extension=True,
            summary="AWS-CSM mailbox profiles and domain configuration for a grantee.",
        ),
        PortalToolRegistryEntry(
            tool_id="ext_analytics",
            label="Analytics",
            surface_id=UTILITIES_EXTENSIONS_SURFACE_ID,
            entrypoint_id="portal.utilities.ext_analytics",
            route=UTILITIES_EXTENSIONS_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="read-only",
            required_capabilities=("fnd_peripheral_routing",),
            is_extension=True,
            summary="Webapp NDJSON event aggregates for a domain.",
        ),
        PortalToolRegistryEntry(
            tool_id="ext_newsletter",
            label="Newsletter",
            surface_id=UTILITIES_EXTENSIONS_SURFACE_ID,
            entrypoint_id="portal.utilities.ext_newsletter",
            route=UTILITIES_EXTENSIONS_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            is_extension=True,
            summary="Newsletter contact log and sender assignment for a domain.",
        ),
        PortalToolRegistryEntry(
            tool_id="ext_paypal",
            label="PayPal",
            surface_id=UTILITIES_EXTENSIONS_SURFACE_ID,
            entrypoint_id="portal.utilities.ext_paypal",
            route=UTILITIES_EXTENSIONS_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            is_extension=True,
            summary="PayPal webhook configuration and donation orders log.",
        ),
        # Phase 17b: the Connect extension surfaces website-visitor
        # messages forwarded to a configured grantee email address.
        # Lead-collection sibling to the newsletter extension —
        # submissions land as unsubscribed contacts tagged
        # source=connect_form so the operator builds a leads list.
        PortalToolRegistryEntry(
            tool_id="ext_connect",
            label="Connect",
            surface_id=UTILITIES_EXTENSIONS_SURFACE_ID,
            entrypoint_id="portal.utilities.ext_connect",
            route=UTILITIES_EXTENSIONS_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            is_extension=True,
            summary="Connect-form visitor messages forwarded to the grantee inbox via SES.",
        ),
        # Phase 9 (grantee_profile_contract.md): editable form over the
        # grantee JSON file. This is the single home for per-grantee
        # configuration that the other extensions read (paypal, aws_ses,
        # newsletter sub-configs). Phase 14b: hosted by its own dedicated
        # Utilities/Grantee Profile surface — not bundled with the
        # operational extensions.
        PortalToolRegistryEntry(
            tool_id="ext_grantee_profile",
            label="Grantee Profile",
            surface_id=UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
            entrypoint_id="portal.utilities.ext_grantee_profile",
            route=UTILITIES_GRANTEE_PROFILE_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            is_extension=True,
            summary="Editable form for grantee identity + credentials (paypal, aws_ses, newsletter).",
        ),
        # Wave 2 (resources extension): the shared site-core asset library —
        # profiles (a viewer/editor "contact app"), images, icons, documents,
        # events, contacts. RETIRES the Wave-1 ``resources.root`` top-level
        # surface; resources is a proper Utilities → Extensions extension, the
        # same as every other operator feature here. Renderer lives in
        # utilities_extensions.EXTENSION_RENDERERS["ext_resources"].
        PortalToolRegistryEntry(
            tool_id="ext_resources",
            label="Resources",
            surface_id=UTILITIES_EXTENSIONS_SURFACE_ID,
            entrypoint_id="portal.utilities.ext_resources",
            route=UTILITIES_EXTENSIONS_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            is_extension=True,
            summary=(
                "Shared site-core leaflet library: search, view and edit every "
                "resource by naming convention; allocate resources to a grantee's "
                "site from a grantee view."
            ),
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
