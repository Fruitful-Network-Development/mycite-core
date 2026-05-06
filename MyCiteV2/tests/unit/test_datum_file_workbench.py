from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_workbench import (
    DATUM_FILE_WORKBENCH_KIND,
    WORKBENCH_MODE_ANCHOR,
    WORKBENCH_MODE_GALLERY,
    WORKBENCH_MODE_SELECTED_DOCUMENT,
    build_datum_file_workbench,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    PortalScope,
    SYSTEM_ROOT_SURFACE_ID,
)


def _document(
    *,
    document_id: str,
    document_name: str,
    sandbox: str,
    is_anchor: bool = False,
    rows: list | None = None,
    version_hash: str = "",
    source_kind: str = "sandbox_source",
) -> dict:
    return {
        "document_id": document_id,
        "document_name": document_name,
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

    def test_anchor_mode_emits_layered_datum_table(self) -> None:
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
        self.assertEqual(region["mode"], WORKBENCH_MODE_ANCHOR)
        self.assertEqual(region["anchor"]["document_id"], anchor["document_id"])
        self.assertIn("layered_datum_table", region)
        self.assertEqual(len(region["layered_datum_table"]["rows"]), 2)

    def test_gallery_mode_lists_sandbox_documents_with_anchor_first(self) -> None:
        anchor = _document(
            document_id="lv.fnd.cts_gis.anchor.aaaa",
            document_name="anchor.json",
            sandbox="cts_gis",
            is_anchor=True,
        )
        secondary = _document(
            document_id="lv.fnd.cts_gis.natural_entity.bbbb",
            document_name="natural_entity.json",
            sandbox="cts_gis",
        )
        tertiary = _document(
            document_id="lv.fnd.cts_gis.address_nodes.cccc",
            document_name="address_nodes.json",
            sandbox="cts_gis",
        )
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            anchor_document=None,
            sandbox_documents=[secondary, anchor, tertiary],
            explicit_mode=WORKBENCH_MODE_GALLERY,
        )
        self.assertEqual(region["mode"], WORKBENCH_MODE_GALLERY)
        cards = region["gallery"]["documents"]
        self.assertEqual(cards[0]["document_id"], anchor["document_id"])
        # address_nodes sorts before natural_entity alphabetically.
        self.assertEqual(
            [card["document_id"] for card in cards],
            [anchor["document_id"], tertiary["document_id"], secondary["document_id"]],
        )

    def test_selected_document_mode_emits_layered_datum_table_for_selection(self) -> None:
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
            surface_id=AWS_CSM_TOOL_SURFACE_ID,
            sandbox_id="aws_csm",
            anchor_document=anchor,
            selected_document=selected,
        )
        self.assertEqual(region["mode"], WORKBENCH_MODE_SELECTED_DOCUMENT)
        self.assertEqual(region["selected_document"]["document_id"], selected["document_id"])
        self.assertEqual(region["layered_datum_table"]["document"]["document_id"], selected["document_id"])
        self.assertEqual(len(region["layered_datum_table"]["rows"]), 1)

    def test_projection_bundle_input_emits_gallery_card_and_layer_groups(self) -> None:
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
        gallery = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            sandbox_documents=[bundle],
            explicit_mode=WORKBENCH_MODE_GALLERY,
        )
        self.assertEqual(gallery["gallery"]["documents"][0]["document_id"], "lv.fnd.cts_gis.natural_entity.bbbb")
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

    def test_explicit_gallery_overrides_anchor_resolution(self) -> None:
        anchor = _document(
            document_id="lv.fnd.system.anthology.aaaa",
            document_name="anthology.json",
            sandbox="system",
            is_anchor=True,
        )
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            sandbox_id="system",
            anchor_document=anchor,
            sandbox_documents=[anchor],
            explicit_mode=WORKBENCH_MODE_GALLERY,
        )
        self.assertEqual(region["mode"], WORKBENCH_MODE_GALLERY)
        self.assertIn("gallery", region)
        self.assertNotIn("layered_datum_table", region)

    def test_attaches_region_family_contract(self) -> None:
        region = build_datum_file_workbench(
            portal_scope=self.portal_scope,
            shell_state=None,
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            sandbox_id="cts_gis",
            anchor_document=None,
            explicit_mode=WORKBENCH_MODE_GALLERY,
        )
        self.assertIn("family_contract", region)
        self.assertEqual(region["family_contract"]["family"], "reflective_workspace")


if __name__ == "__main__":
    unittest.main()
