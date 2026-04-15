from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.cts_gis import CtsGisReadOnlyService
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)


class _FakeDatumStore:
    def __init__(self, result: AuthoritativeDatumDocumentCatalogResult) -> None:
        self.result = result
        self.requests = []

    def read_authoritative_datum_documents(self, request):
        self.requests.append(request)
        return self.result


def _anchor_row(address: str, label: str) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(
        datum_address=address,
        raw=[[address, "~", "0-0-0"], [label]],
    )


def _cts_gis_document() -> AuthoritativeDatumDocument:
    summit_binary = (
        "011100110111010101101101011011010110100101110100"
        "0000000000000000"
    )
    fairlawn_binary = (
        "011001100110000101101001011100100110110001100001"
        "011101110110111000000000"
    )
    return AuthoritativeDatumDocument(
        document_id="sandbox:maps:sc.example.json",
        source_kind="sandbox_source",
        document_name="sc.example.json",
        relative_path="sandbox/maps/sources/sc.example.json",
        tool_id="maps",
        anchor_document_name="tool.maps.json",
        anchor_document_path="sandbox/maps/tool.maps.json",
        anchor_rows=(
            _anchor_row("3-1-1", "HOPS-babelette-coordinate"),
            _anchor_row("3-1-2", "SAMRAS-babelette-msn_id"),
            _anchor_row("3-1-3", "title-babelette"),
        ),
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-1",
                raw=[
                    ["4-2-1", "rf.3-1-1", "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73"],
                    ["polygon_1"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-2",
                raw=[
                    [
                        "4-2-2",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                    ],
                    ["point_alpha"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-1",
                raw=[
                    ["5-0-1", "~", "4-2-1"],
                    ["summit_boundary"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="6-0-1",
                raw=[
                    ["6-0-1", "~", "4-2-2"],
                    ["fairlawn_boundary_collection"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-1",
                raw=[
                    ["7-3-1", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", summit_binary, "5-0-1", "1"],
                    ["summit_county"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-2",
                raw=[
                    [
                        "7-3-2",
                        "rf.3-1-2",
                        "3-2-3-17-77-1-1",
                        "rf.3-1-3",
                        fairlawn_binary,
                        "6-0-1",
                        "1",
                    ],
                    ["fairlawn_city"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-3",
                raw=[
                    ["7-3-3", "rf.3-1-2", "3-2-3-17-77-1-2", "rf.3-1-3", "HERE"],
                    ["bad_title"],
                ],
            ),
        ),
    )


class CtsGisReadOnlyUnitTests(unittest.TestCase):
    def test_builds_attention_first_surface_and_profile_linked_projection(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface("fnd")

        self.assertEqual(surface["map_projection"]["projection_state"], "projectable")
        self.assertEqual(surface["map_projection"]["feature_count"], 1)
        self.assertEqual(surface["map_projection"]["selected_feature"]["geometry_type"], "Point")
        self.assertEqual(surface["attention_profile"]["node_id"], "3-2-3-17-77-1")
        self.assertEqual(surface["selected_row"]["datum_address"], "4-2-2")
        self.assertEqual(surface["mediation_state"]["attention_node_id"], "3-2-3-17-77-1")
        self.assertEqual(surface["mediation_state"]["intention_token"], "descendants_depth_1_or_2")
        self.assertIn("1-0", [item["token"] for item in surface["mediation_state"]["available_intentions"]])
        self.assertIn(
            "descendants_depth_1_or_2",
            [item["token"] for item in surface["mediation_state"]["available_intentions"]],
        )
        feature_types = [feature["geometry"]["type"] for feature in surface["map_projection"]["feature_collection"]["features"]]
        self.assertEqual(feature_types, ["Point"])
        first_feature_props = surface["map_projection"]["feature_collection"]["features"][0]["properties"]
        self.assertEqual(first_feature_props["samras_node_id"], "3-2-3-17-77-1-1")
        self.assertEqual(first_feature_props["profile_label"], "fairlawn")
        self.assertEqual(
            [item["node_id"] for item in surface["render_profiles"]],
            ["3-2-3-17-77-1-1", "3-2-3-17-77-1-2"],
        )

        named_row = [row for row in surface["rows"] if row["datum_address"] == "7-3-2"][0]
        title_overlay = [entry for entry in named_row["overlay_preview"] if entry["overlay_family"] == "title_babelette"][0]
        self.assertEqual(title_overlay["display_value"], "fairlawn")

        bad_row_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1-2",
                "intention_token": "0",
            },
        )
        bad_row = [row for row in bad_row_surface["rows"] if row["datum_address"] == "7-3-3"][0]
        bad_title_overlay = [entry for entry in bad_row["overlay_preview"] if entry["overlay_family"] == "title_babelette"][0]
        self.assertEqual(bad_title_overlay["raw_value"], "HERE")
        self.assertEqual(bad_title_overlay["display_value"], "HERE")
        self.assertIn("illegal_magnitude_literal", bad_row["diagnostic_states"])

    def test_children_intention_and_legacy_row_bridge_select_child_profile(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        children_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "1-0",
            },
        )

        self.assertEqual(children_surface["render_set_summary"]["render_mode"], "children")
        self.assertEqual(children_surface["map_projection"]["feature_count"], 1)
        self.assertEqual(children_surface["children"][0]["node_id"], "3-2-3-17-77-1-1")
        feature_props = children_surface["map_projection"]["feature_collection"]["features"][0]["properties"]
        self.assertEqual(feature_props["samras_node_id"], "3-2-3-17-77-1-1")
        self.assertEqual(feature_props["profile_label"], "fairlawn")

        bridged_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            selected_row_address="7-3-2",
        )
        self.assertEqual(bridged_surface["attention_profile"]["node_id"], "3-2-3-17-77-1-1")
        self.assertEqual(bridged_surface["selected_row"]["datum_address"], "7-3-2")

    def test_reports_no_authoritative_cts_gis_documents_with_fallback_document(self) -> None:
        system_document = AuthoritativeDatumDocument(
            document_id="system:anthology",
            source_kind="system_anthology",
            document_name="anthology.json",
            relative_path="system/anthology.json",
            rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="0-0-1",
                    raw=[["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]],
                ),
            ),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="tff",
                documents=(system_document,),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface("tff")

        self.assertEqual(surface["document_catalog"], [])
        self.assertEqual(surface["map_projection"]["projection_state"], "no_authoritative_cts_gis_documents")
        self.assertEqual(surface["map_projection"]["feature_count"], 0)
        self.assertEqual(surface["selected_document"]["document_name"], "anthology.json")
        self.assertTrue(surface["warnings"])


if __name__ == "__main__":
    unittest.main()
