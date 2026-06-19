"""Agronomics — a COMPOSITE tool: farm_profile (left) + LCL structure (right).

The first multi-pane tool. It does not render anything itself; it composes two existing
single-purpose viewers into one interface-panel section laid out side by side:

    ┌─ Agronomics ──────────────────────────────┐
    │  Farm Profile (map)   │  LCL ID Space (tree) │
    └────────────────────────────────────────────┘

Each pane is just another tool's panel_payload, carried under a generic ``container:
"composite"`` payload that the client's composite renderer lays out and delegates back to
each pane's own renderer. This is the abstraction seam: a composite is a declaration of
panes, so a section can be reworked (or new composites assembled) without touching the
sub-tools. ``farm_profile`` and ``samras_structure`` remain available standalone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from ._registry import register
from ._shared.utilities import as_text as _as_text
from .farm_profile_viewer import FarmProfileViewer
from .samras_structure_viewer import SamrasStructureViewer

_SCHEMA = "mycite.v2.portal.workbench.tool.agronomics.v1"
# The LCL id-space is the agronomics structure of interest; default the right pane to it.
_DEFAULT_STRUCTURE = "lcl"


class AgronomicsViewer:
    """Compose farm_profile + the LCL structure viewer into one two-pane section."""

    tool_id = "agronomics"
    label = "Agronomics"
    summary = "Farm profile map beside the LCL id-space tree — the two agronomics views together."
    route = WORKBENCH_UI_TOOL_ROUTE
    # Surfaces wherever EITHER sub-tool would: the agro_erp sandbox has both the
    # hops_geospatial_filament (farm_profile) and samras_taxonomy (lcl) archetypes.
    applies_to_archetype: tuple[str, ...] = ("hops_geospatial_filament", "samras_taxonomy")
    applies_to_source_kind: tuple[str, ...] = ()
    # Pass the surface_query through so the right pane's structure <select> works.
    wants_surface_query = True

    def build_panel_payload(
        self,
        *,
        authority_db_file: Path | None,
        sandbox_id: str,
        document_id: str,
        datum_address: str,
        extra_query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Left pane: the farm-profile map (resolves its own doc by archetype).
        farm_payload = FarmProfileViewer().build_panel_payload(
            authority_db_file=authority_db_file,
            sandbox_id=sandbox_id,
            document_id=document_id,
            datum_address=datum_address,
        )
        # Right pane: the SAMRAS structure viewer, defaulted to the LCL id-space. The
        # pane keeps its own structure selector (composition over a stripped variant);
        # an explicit surface_query.samras_structure overrides the default.
        structure = _as_text((extra_query or {}).get("samras_structure")) or _DEFAULT_STRUCTURE
        lcl_payload = SamrasStructureViewer().build_panel_payload(
            authority_db_file=authority_db_file,
            sandbox_id=sandbox_id,
            document_id=document_id,
            datum_address=datum_address,
            extra_query={"samras_structure": structure},
        )
        return {
            "schema": _SCHEMA,
            "container": "composite",
            "title": "Agronomics",
            "sandbox_id": sandbox_id or "agro_erp",
            "panes": [
                {"tool_id": "farm_profile", "label": "Farm Profile", "panel_payload": farm_payload},
                {"tool_id": "samras_structure", "label": "LCL ID Space", "panel_payload": lcl_payload},
            ],
        }


# Self-register on import.
register(AgronomicsViewer())
