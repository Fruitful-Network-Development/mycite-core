"""Workbench-tool package.

Plan v2: tools are simple visualization renderers invoked from the
menubar palette. The contract is in :mod:`_contract`; the registry in
:mod:`_registry`. Each tool module self-registers on import.

To add a new tool: create ``MyCiteV2/packages/tools/<tool_id>.py``
implementing :class:`_contract.WorkbenchTool`, call
``_registry.register(MyTool())`` at module scope, then import the
module from this package's ``__init__`` so the registry is populated
when consumers import :mod:`MyCiteV2.packages.tools`.
"""

from __future__ import annotations

# Self-registering tool modules (import for side effect). Order is irrelevant
# — ``_registry.all_tools()`` sorts by ``tool_id`` on read.
from . import (
    agronomics_viewer,  # noqa: F401  (composite: farm_profile + lcl structure)
    contacts_viewer,  # noqa: F401
    contracts_tool,  # noqa: F401
    farm_profile_viewer,  # noqa: F401  (consolidated: profile_card + geospatial_projection)
    geospatial_projection_viewer,  # noqa: F401  (field/plots map base)
    invoices_viewer,  # noqa: F401
    local_domain_viewer,  # noqa: F401  (lcl tree + expand-to-table instance containers)
    plot_manager_viewer,  # noqa: F401  (geospatial + date + select + create-cluster)
    plots_viewer,  # noqa: F401
    product_document_view,  # noqa: F401
    profile_card_viewer,  # noqa: F401  (base profile contract; farm_profile builds on it)
    record_studio,  # noqa: F401  (write/form base; ContractEditor)
    record_synopsis,  # noqa: F401  (derived-figure summaries; InventorySynopsis)
    samras_structure_viewer,  # noqa: F401  (unified txa/msn/lcl structure viewer)
)

# Intentionally NOT imported (so they do not self-register into the viz palette):
#   * workbench_ui_view — `workbench_ui` is the workbench SURFACE (registered as a
#     surface-routing entry in shell_registry), not a visualization tool; importing it
#     made it a fake "navigates_to_surface" tool on every doc. Surface nav is unaffected.
#   * cts_gis_map / cts_gis_district / cts_gis_admin — legacy fixed-artifact viewers
#     gated on a near-universal `sandbox_source` bucket, so they appeared on EVERY doc.
#     CTS-GIS docs are GeoJSON-metadata based (no reliable per-doc archetype/hyphae) and
#     these tools render a doc-independent compiled artifact — there is no honest per-doc
#     eligibility for them. RETIRED from the palette pending sandbox-scoped eligibility;
#     the modules + `_cts_gis_artifact` infra remain. Re-enable by re-adding the imports
#     once a sandbox-level tool surface exists.
from ._contract import WorkbenchTool
from ._registry import TOOL_REGISTRY, all_tools, describe_for_palette, get, register

__all__ = [
    "WorkbenchTool",
    "TOOL_REGISTRY",
    "all_tools",
    "describe_for_palette",
    "get",
    "register",
]
