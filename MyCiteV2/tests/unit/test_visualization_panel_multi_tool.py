"""C4 — interface-panel tool surface (surface_query.tools → panels[]).

The interface_panel is the unified tool surface (TASK-interface-panel-migration): it
carries a ``tool_search`` context + one panel per tool in ``surface_query.tools`` (each
renders as a removable box client-side), keeping the legacy single-tool fields (= first
panel) for back-compat. Post portal-tool-overlay-restructure the region is always returned
but DORMANT (visible False — tools render in the menubar-search overlay; the region's
tool_search context is what the menubar search mounts with). The canonical query round-trips
``tools`` (and folds the legacy scalar ``tool``).
"""

from __future__ import annotations

import unittest

from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
    _build_interface_tool_panel,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    WORKBENCH_UI_TOOL_SURFACE_ID,
    PortalScope,
    canonical_query_for_surface_query,
)

_SCOPE = PortalScope(scope_id="fnd", capabilities=())


def _panel(surface_query):
    return _build_interface_tool_panel(
        surface_query=surface_query,
        authority_db_file=None,  # tools return graceful error payloads; we assert structure
        sandbox_id="agro_erp",
        document_id="",
        datum_address="",
        portal_scope=_SCOPE,
    )


class InterfaceToolPanelTests(unittest.TestCase):
    def test_no_tool_yields_dormant_panel_with_search_and_no_panels(self) -> None:
        # portal-tool-overlay-restructure: the sidebar is now DORMANT (visible False — tools
        # render in the menubar-search overlay), but the region still carries the tool_search
        # context the menubar search reads, and no panels until a tool is requested.
        for sq in ({}, {"tools": ""}):
            region = _panel(sq)
            self.assertFalse(region["visible"])  # sidebar dormant; search lives in the menubar
            self.assertEqual(region["panels"], [])
            self.assertEqual(region["tool_search"]["sandbox_id"], "agro_erp")
            self.assertEqual(region["tool_search"]["tenant_id"], "fnd")

    def test_legacy_single_tool_yields_one_panel(self) -> None:
        region = _panel({"tool": "product_document"})
        self.assertEqual(len(region["panels"]), 1)
        self.assertEqual(region["panels"][0]["tool_id"], "product_document")
        # legacy fields mirror the first panel
        self.assertEqual(region["tool_id"], "product_document")
        self.assertEqual(region["panel_payload"], region["panels"][0]["panel_payload"])

    def test_tools_list_yields_ordered_panels(self) -> None:
        region = _panel({"tools": "product_document,cts_gis_district,cts_gis_admin"})
        self.assertEqual([p["tool_id"] for p in region["panels"]],
                         ["product_document", "cts_gis_district", "cts_gis_admin"])
        self.assertEqual(region["tool_id"], "product_document")  # first

    def test_tools_dedup_preserves_order(self) -> None:
        region = _panel({"tools": "cts_gis, product_document , cts_gis"})
        self.assertEqual([p["tool_id"] for p in region["panels"]], ["cts_gis", "product_document"])

    def test_unknown_tool_yields_error_panel(self) -> None:
        region = _panel({"tools": "not_a_tool"})
        self.assertEqual(region["panels"][0]["panel_payload"].get("error"), "unknown tool: not_a_tool")

    def test_canonical_query_round_trips_tools(self) -> None:
        q = canonical_query_for_surface_query(
            {"tools": "cts_gis,cts_gis_district"}, surface_id=WORKBENCH_UI_TOOL_SURFACE_ID
        )
        self.assertEqual(q.get("tools"), "cts_gis,cts_gis_district")

    def test_canonical_query_folds_legacy_tool_into_tools(self) -> None:
        q = canonical_query_for_surface_query(
            {"tool": "cts_gis"}, surface_id=WORKBENCH_UI_TOOL_SURFACE_ID
        )
        self.assertEqual(q.get("tools"), "cts_gis")


if __name__ == "__main__":
    unittest.main()
