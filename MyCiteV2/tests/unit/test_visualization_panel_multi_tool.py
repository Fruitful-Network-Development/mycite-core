"""build_tool_panels — surface_query.tools → [{tool_id, tool_label, panel_payload}].

The portal renders tools in the menubar-search → full-screen overlay; the overlay's
/portal/api/tool-panels endpoint goes through ``build_tool_panels`` (the reusable tool-render
core). This asserts the tool-id grammar (comma list, dedup, legacy scalar ``tool``) + per-tool
panel resolution. The canonical query round-trips ``tools`` (and folds the legacy scalar
``tool``).
"""

from __future__ import annotations

import unittest

from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
    _parse_tool_ids,
    build_tool_panels,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    WORKBENCH_UI_TOOL_SURFACE_ID,
    canonical_query_for_surface_query,
)


def _panels(surface_query):
    return build_tool_panels(
        tool_ids=_parse_tool_ids(surface_query),
        surface_query=surface_query,
        authority_db_file=None,  # tools return graceful error payloads; we assert structure
        sandbox_id="agro_erp",
        document_id="",
        datum_address="",
    )


class BuildToolPanelsTests(unittest.TestCase):
    def test_no_tool_yields_no_panels(self) -> None:
        for sq in ({}, {"tools": ""}):
            self.assertEqual(_panels(sq), [])

    def test_legacy_single_tool_yields_one_panel(self) -> None:
        panels = _panels({"tool": "product_document"})
        self.assertEqual(len(panels), 1)
        self.assertEqual(panels[0]["tool_id"], "product_document")

    def test_tools_list_yields_ordered_panels(self) -> None:
        panels = _panels({"tools": "product_document,cts_gis_district,cts_gis_admin"})
        self.assertEqual(
            [p["tool_id"] for p in panels],
            ["product_document", "cts_gis_district", "cts_gis_admin"],
        )

    def test_tools_dedup_preserves_order(self) -> None:
        panels = _panels({"tools": "cts_gis, product_document , cts_gis"})
        self.assertEqual([p["tool_id"] for p in panels], ["cts_gis", "product_document"])

    def test_unknown_tool_yields_error_panel(self) -> None:
        panels = _panels({"tools": "not_a_tool"})
        self.assertEqual(panels[0]["panel_payload"].get("error"), "unknown tool: not_a_tool")

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
