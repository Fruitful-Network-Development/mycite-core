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
    title_binary = (
        "011100110111010101101101011011010110100101110100"
        "0000000000000000"
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
                    ["point_alpha"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-2",
                raw=[
                    [
                        "4-2-2",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-81-25-68-43-68-84-44-22-24",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
                    ],
                    ["polygon_1"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-3",
                raw=[
                    ["4-2-3", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", title_binary],
                    ["named_area"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-4",
                raw=[
                    ["4-2-4", "rf.3-1-2", "3-2-3-17-77-1-1", "rf.3-1-3", "HERE"],
                    ["bad_title"],
                ],
            ),
        ),
    )


class CtsGisReadOnlyUnitTests(unittest.TestCase):
    def test_builds_point_and_polygon_features_and_title_overlay(self) -> None:
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
        self.assertEqual(surface["map_projection"]["feature_count"], 2)
        self.assertEqual(surface["map_projection"]["selected_feature"]["geometry_type"], "Point")
        feature_types = [feature["geometry"]["type"] for feature in surface["map_projection"]["feature_collection"]["features"]]
        self.assertEqual(feature_types, ["Point", "Polygon"])

        named_row = [row for row in surface["rows"] if row["datum_address"] == "4-2-3"][0]
        title_overlay = [entry for entry in named_row["overlay_preview"] if entry["overlay_family"] == "title_babelette"][0]
        self.assertEqual(title_overlay["display_value"], "summit")

        self.assertEqual(surface["selected_row"]["datum_address"], "4-2-1")

        bad_row = [row for row in surface["rows"] if row["datum_address"] == "4-2-4"][0]
        bad_title_overlay = [entry for entry in bad_row["overlay_preview"] if entry["overlay_family"] == "title_babelette"][0]
        self.assertEqual(bad_title_overlay["raw_value"], "HERE")
        self.assertEqual(bad_title_overlay["display_value"], "HERE")
        self.assertIn("illegal_magnitude_literal", bad_row["diagnostic_states"])

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
