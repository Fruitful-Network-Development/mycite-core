from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.domains.datum_recognition import DatumWorkbenchService
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
        raw=[[address, "2-0-1", "0"], [label]],
    )


class DatumRecognitionUnitTests(unittest.TestCase):
    def test_preserves_here_and_distinguishes_reference_legality_from_family_mismatch(self) -> None:
        document = AuthoritativeDatumDocument(
            document_id="sandbox:maps:sc.example.json",
            source_kind="sandbox_source",
            document_name="sc.example.json",
            relative_path="sandbox/maps/sources/sc.example.json",
            tool_id="maps",
            anchor_document_name="tool.maps.json",
            anchor_document_path="sandbox/maps/tool.maps.json",
            anchor_rows=(
                _anchor_row("3-1-2", "SAMRAS-babelette-msn_id"),
                _anchor_row("3-1-3", "title-babelette"),
            ),
            rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="4-2-118",
                    raw=[
                        ["4-2-118", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", "HERE"],
                        ["summit_county_cities"],
                    ],
                ),
            ),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(document,),
                source_files={"anthology": "/tmp/data/system/anthology.json"},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        projection = DatumWorkbenchService(store).read_workbench("fnd")
        payload = projection.to_dict()
        row = payload["rows"][0]

        self.assertEqual(payload["selected_document"]["document_name"], "sc.example.json")
        self.assertEqual(row["reference_bindings"][0]["normalized_reference_form"], "rf.3-1-2")
        self.assertEqual(row["reference_bindings"][1]["normalized_reference_form"], "rf.3-1-3")
        self.assertEqual(row["recognized_family"], "samras_babelette")
        self.assertIn("illegal_magnitude_literal", row["diagnostic_states"])
        self.assertIn("family_magnitude_mismatch", row["diagnostic_states"])
        self.assertNotIn("unresolved_anchor", row["diagnostic_states"])
        self.assertEqual(row["primary_value_token"], "HERE")

    def test_reports_unresolved_anchor_and_missing_reference_without_rewriting_row(self) -> None:
        document = AuthoritativeDatumDocument(
            document_id="sandbox:maps:sc.bad.json",
            source_kind="sandbox_source",
            document_name="sc.bad.json",
            relative_path="sandbox/maps/sources/sc.bad.json",
            tool_id="maps",
            rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="4-2-1",
                    raw=[["4-2-1", "rf.3-1-9", "3-2-3-17-77-1"], ["missing_anchor"]],
                ),
                AuthoritativeDatumDocumentRow(
                    datum_address="4-2-2",
                    raw=[["4-2-2", "rf.3-1-3"], ["missing_value"]],
                ),
            ),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(document,),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        projection = DatumWorkbenchService(store).read_workbench("fnd").to_dict()
        unresolved = projection["rows"][0]
        missing = projection["rows"][1]

        self.assertIn("unresolved_anchor", unresolved["diagnostic_states"])
        self.assertEqual(unresolved["raw"][0][1], "rf.3-1-9")
        self.assertIn("missing_reference", missing["diagnostic_states"])
        self.assertEqual(missing["reference_bindings"][0]["resolution_state"], "missing_reference")

    def test_flags_address_irregularity_without_resequencing_addresses(self) -> None:
        document = AuthoritativeDatumDocument(
            document_id="sandbox:maps:sc.gap.json",
            source_kind="sandbox_source",
            document_name="sc.gap.json",
            relative_path="sandbox/maps/sources/sc.gap.json",
            tool_id="maps",
            rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="4-2-118",
                    raw=[["4-2-118", "rf.3-1-2", "3-2-3-17-77-1"], ["a"]],
                ),
                AuthoritativeDatumDocumentRow(
                    datum_address="4-2-120",
                    raw=[["4-2-120", "rf.3-1-2", "3-2-3-17-77-1-1"], ["b"]],
                ),
            ),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(document,),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        projection = DatumWorkbenchService(store).read_workbench("fnd").to_dict()
        self.assertEqual([row["datum_address"] for row in projection["rows"]], ["4-2-118", "4-2-120"])
        self.assertIn("address_irregularity", projection["rows"][1]["diagnostic_states"])

    def test_flags_unrecognized_family_when_anchor_exists_but_family_is_unknown(self) -> None:
        document = AuthoritativeDatumDocument(
            document_id="sandbox:maps:sc.unknown.json",
            source_kind="sandbox_source",
            document_name="sc.unknown.json",
            relative_path="sandbox/maps/sources/sc.unknown.json",
            tool_id="maps",
            anchor_rows=(_anchor_row("3-1-7", "custom-anchor-shape"),),
            rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="4-2-1",
                    raw=[["4-2-1", "rf.3-1-7", "custom-value"], ["custom_label"]],
                ),
            ),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(document,),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        row = DatumWorkbenchService(store).read_workbench("fnd").to_dict()["rows"][0]
        self.assertIn("unrecognized_family", row["diagnostic_states"])
        self.assertEqual(row["reference_bindings"][0]["anchor_label"], "custom-anchor-shape")


if __name__ == "__main__":
    unittest.main()
