"""Agronomics — the portal's primary tool: FARM / PLAN / NETWORK tabs.

Renders a ``container:"tabbed"`` payload. The FARM tab is a COMPOSITE of two existing
single-purpose viewers laid out side by side; PLAN and NETWORK are blank scaffolds that
future agronomics sub-component tools slot into:

    ┌─ Agronomics ──[ FARM ][ PLAN ][ NETWORK ]──┐
    │  Farm Profile (map)   │  LCL ID Space (tree) │   ← FARM tab
    └────────────────────────────────────────────┘

Each pane is just another tool's panel_payload, carried under a generic ``container:
"composite"`` payload that the client's composite renderer lays out and delegates back to
each pane's own renderer; the tabs are a ``container:"tabbed"`` wrapper switched client-side
(no shell reload). This is the abstraction seam: a composite/tab is a declaration of panes,
so a section can be reworked (or new sub-tools assembled) without touching the sub-tools.
``farm_profile`` and ``samras_structure`` remain available standalone (still selectable in
the menubar search).
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
from .local_domain_viewer import LocalDomainViewer, build_record_view
from .plot_manager_viewer import PlotManagerViewer
from .record_studio import ContractEditor
from .record_synopsis import InventorySynopsis

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
        eq = extra_query or {}
        sandbox = sandbox_id or "agro_erp"
        # Full-tab takeover: an expand-view node (local_view = its record-view token) shifts
        # the FARM tab from the map+tree composite into a full-width record table of that
        # node's child instances, with a back affordance the renderer turns into a ← bar.
        local_view = _as_text(eq.get("local_view"))
        record_table = (
            build_record_view(local_view, authority_db_file=authority_db_file, sandbox_id=sandbox)
            if local_view else None
        )
        if record_table is not None:
            farm_panel = {
                **record_table,
                "back": {"label": "Back to farm view", "param": "local_view", "value": ""},
            }
        else:
            # Left pane: the farm-profile map (resolves its own doc by archetype).
            farm_payload = FarmProfileViewer().build_panel_payload(
                authority_db_file=authority_db_file,
                sandbox_id=sandbox_id,
                document_id=document_id,
                datum_address=datum_address,
            )
            # Right pane: the LOCAL DOMAIN viewer (the SAMRAS lcl tree extended with
            # expand-to-table instance containers), defaulted to the lcl id-space.
            structure = _as_text(eq.get("samras_structure")) or _DEFAULT_STRUCTURE
            lcl_payload = LocalDomainViewer().build_panel_payload(
                authority_db_file=authority_db_file,
                sandbox_id=sandbox_id,
                document_id=document_id,
                datum_address=datum_address,
                extra_query={"samras_structure": structure},
            )
            farm_panel = {
                "schema": _SCHEMA,
                "container": "composite",
                "title": "Agronomics",
                "sandbox_id": sandbox,
                "panes": [
                    {"tool_id": "farm_profile", "label": "Farm Profile", "panel_payload": farm_payload},
                    {"tool_id": "local_domain", "label": "Local Domain", "panel_payload": lcl_payload},
                ],
            }
        # PLAN tab layout (operator spec): a COLUMN composite — a top ROW of [Plot Manager |
        # reserved slot | Inventory synopsis], then the Contract Editor as a thin widget across
        # the bottom. NETWORK stays a blank scaffold.
        _kw = {"authority_db_file": authority_db_file, "sandbox_id": sandbox_id,
               "document_id": "", "datum_address": ""}
        plot_payload = PlotManagerViewer().build_panel_payload(**_kw)
        inventory_payload = InventorySynopsis().build_panel_payload(**_kw)
        contract_payload = ContractEditor().build_panel_payload(**_kw, extra_query=eq)
        plan_top = {
            "schema": _SCHEMA, "container": "composite", "direction": "row", "widgets": True,
            "sandbox_id": sandbox,
            "panes": [
                {"tool_id": "plot_manager", "label": "Plot Manager", "panel_payload": plot_payload},
                {"tool_id": "plan_slot", "label": "", "panel_payload": {
                    "schema": _SCHEMA, "container": "synopsis", "title": "",
                    "items": [], "empty_text": "Reserved for a later tool."}},
                {"tool_id": "inventory_synopsis", "label": "Inventory", "panel_payload": inventory_payload},
            ],
        }
        plan_panel = {
            "schema": _SCHEMA, "container": "composite", "direction": "column", "title": "Plan",
            "sandbox_id": sandbox,
            "panes": [
                {"tool_id": "plan_top", "label": "", "panel_payload": plan_top},
                {"tool_id": "contract_editor", "label": "Contract Editor", "panel_payload": contract_payload},
            ],
        }
        # FARM / PLAN / NETWORK tabs. Tab switching is client-side in the ``tabbed`` container
        # renderer (no shell reload); ``active_tab`` lets an overlay/surface_query param
        # (agronomics_tab) re-open on a chosen tab.
        return {
            "schema": _SCHEMA,
            "container": "tabbed",
            "title": "Agronomics",
            "sandbox_id": sandbox,
            "active_tab": _as_text(eq.get("agronomics_tab")) or "farm",
            "tab_query_param": "agronomics_tab",
            "tabs": [
                {"id": "farm", "label": "FARM", "panel_payload": farm_panel},
                {"id": "plan", "label": "PLAN", "panel_payload": plan_panel},
                {"id": "network", "label": "NETWORK", "panel_payload": None},
            ],
        }


# Self-register on import.
register(AgronomicsViewer())
