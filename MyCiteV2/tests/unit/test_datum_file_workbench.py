from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_workbench import (
    DATUM_FILE_WORKBENCH_KIND,
    build_datum_file_workbench,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    FND_CSM_TOOL_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    PortalScope,
    PortalShellState,
)


def _document(
    *,
    document_id: str,
    document_name: str,
    sandbox: str,
    canonical_name: str = "",
    is_anchor: bool = False,
    rows: list | None = None,
    version_hash: str = "",
    source_kind: str = "sandbox_source",
) -> dict:
    return {
        "document_id": document_id,
        "document_name": document_name,
        "canonical_name": canonical_name or document_name.replace(".json", ""),
        "relative_path": f"sandbox/{sandbox}/sources/{document_name}",
        "tool_id": sandbox,
        "is_anchor": is_anchor,
        "rows": rows or [],
        "version_hash": version_hash or ("a" * 64),
        "source_kind": source_kind,
    }


class DatumFileWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.portal_scope = PortalScope(scope_id="fnd")

    def test_anchor_focus_emits_state_reflection_and_layered_datum_table(self) -> None:
        anchor = _document(
            document_id="lv.fnd.system.anthology.deadbeef",
            document_name="anthology.json",
            sandbox="system",
            is_anchor=True,
            rows=[{"datum_address": "1-1-1"}, {"datum_address": "1-1-2"}],
        )
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            sandbox_id="system",
            anchor_document=anchor,
        )
        self.assertEqual(region["kind"], DATUM_FILE_WORKBENCH_KIND)
        self.assertNotIn("mode", region)
        self.assertEqual(region["state_reflection"]["current_sandbox"], "system")
        self.assertEqual(region["state_reflection"]["current_file"], anchor["document_id"])
        self.assertEqual(region["document_collection"]["anchor_document"]["document_id"], anchor["document_id"])
        self.assertEqual(region["active_document"]["document_id"], anchor["document_id"])
        self.assertIn("layered_datum_table", region)
        self.assertEqual(len(region["layered_datum_table"]["rows"]), 2)

    def test_document_collection_lists_sandbox_documents_with_anchor_first(self) -> None:
        anchor = _document(
            document_id="lv.fnd.cts_gis.anchor.aaaa",
            document_name="tool.3-2-3.cts-gis.json",
            sandbox="cts_gis",
            canonical_name="anchor",
            is_anchor=True,
        )
        secondary = _document(
            document_id="lv.fnd.cts_gis.natural_entity.bbbb",
            document_name="sc.3-2-3.msn-natural_entity.json",
            sandbox="cts_gis",
            canonical_name="natural_entity",
        )
        tertiary = _document(
            document_id="lv.fnd.cts_gis.address_nodes.cccc",
            document_name="sc.3-2-3.msn-address_nodes.json",
            sandbox="cts_gis",
            canonical_name="address_nodes",
        )
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            anchor_document=None,
            sandbox_documents=[secondary, anchor, tertiary],
        )
        self.assertNotIn("mode", region)
        cards = region["document_collection"]["documents"]
        self.assertEqual(cards[0]["document_id"], anchor["document_id"])
        self.assertEqual(cards[0]["label"], "anchor")
        self.assertEqual(cards[1]["label"], "address_nodes")
        # address_nodes sorts before natural_entity alphabetically.
        self.assertEqual(
            [card["document_id"] for card in cards],
            [anchor["document_id"], tertiary["document_id"], secondary["document_id"]],
        )
        self.assertIsNone(region["active_document"])
        self.assertNotIn("layered_datum_table", region)

    def test_selected_file_emits_active_document_layered_datum_table(self) -> None:
        anchor = _document(
            document_id="lv.fnd.aws_csm.anchor.aaaa",
            document_name="anchor.json",
            sandbox="aws_csm",
            is_anchor=True,
        )
        selected = _document(
            document_id="lv.fnd.aws_csm.profile.bbbb",
            document_name="profile.json",
            sandbox="aws_csm",
            rows=[{"datum_address": "1-1-1"}],
        )
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=FND_CSM_TOOL_SURFACE_ID,
            sandbox_id="fnd_csm",
            anchor_document=anchor,
            selected_document=selected,
        )
        self.assertNotIn("mode", region)
        self.assertEqual(region["active_document"]["document_id"], selected["document_id"])
        self.assertEqual(region["layered_datum_table"]["document"]["document_id"], selected["document_id"])
        self.assertEqual(len(region["layered_datum_table"]["rows"]), 1)

    def test_projection_bundle_input_emits_collection_card_and_layer_groups(self) -> None:
        bundle = {
            "document_summary": {
                "document_id": "lv.fnd.cts_gis.natural_entity.bbbb",
                "document_name": "natural_entity.json",
                "tool_id": "cts_gis",
                "row_count": 2,
            },
            "document": {
                "rows": [
                    {"datum_address": "2-3-1", "raw": [["2-3-1"], ["first"]]},
                    {"datum_address": "2-3-2", "raw": [["2-3-2"], ["second"]]},
                ]
            },
        }
        collection = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            sandbox_documents=[bundle],
        )
        self.assertEqual(collection["document_collection"]["documents"][0]["document_id"], "lv.fnd.cts_gis.natural_entity.bbbb")
        selected = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            anchor_document=None,
            selected_document=bundle,
        )
        table = selected["layered_datum_table"]
        self.assertEqual(table["document"]["document_id"], "lv.fnd.cts_gis.natural_entity.bbbb")
        self.assertEqual(table["layer_groups"][0]["layer"], 2)
        self.assertEqual(table["layer_groups"][0]["value_groups"][0]["value_group"], 3)
        self.assertEqual(table["layer_groups"][0]["value_groups"][0]["row_count"], 2)

    def test_sandbox_level_focus_emits_collection_without_active_table(self) -> None:
        anchor = _document(
            document_id="lv.fnd.system.anthology.aaaa",
            document_name="anthology.json",
            sandbox="system",
            canonical_name="anthology",
            is_anchor=True,
        )
        shell_state = PortalShellState(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            focus_path=[{"level": "sandbox", "id": "system"}],
        )
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=shell_state,
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            sandbox_id="system",
            anchor_document=anchor,
            sandbox_documents=[anchor],
        )
        self.assertNotIn("mode", region)
        self.assertIsNone(region["active_document"])
        self.assertEqual(region["document_collection"]["documents"][0]["document_id"], anchor["document_id"])
        self.assertNotIn("layered_datum_table", region)

    def test_anchor_only_sandbox_still_reflects_anchor_file(self) -> None:
        anchor = _document(
            document_id="lv.fnd.cts_gis.anchor.aaaa",
            document_name="tool.3-2-3.cts-gis.json",
            canonical_name="anchor",
            sandbox="cts_gis",
            is_anchor=True,
            rows=[{"datum_address": "1-1-1"}],
        )
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            anchor_document=anchor,
            sandbox_documents=[anchor],
        )
        self.assertEqual(region["active_document"]["canonical_name"], "anchor")
        self.assertEqual(region["document_collection"]["anchor_document"]["canonical_name"], "anchor")

    def test_attaches_region_family_contract(self) -> None:
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            anchor_document=None,
        )
        self.assertIn("family_contract", region)
        self.assertEqual(region["family_contract"]["family"], "reflective_workspace")


if __name__ == "__main__":
    unittest.main()
