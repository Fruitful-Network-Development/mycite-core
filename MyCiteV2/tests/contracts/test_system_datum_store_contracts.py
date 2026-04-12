from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store import (
    AUTHORITATIVE_DATUM_DOCUMENT_CATALOG_SCHEMA,
    AUTHORITATIVE_DATUM_DOCUMENT_ROW_SCHEMA,
    AUTHORITATIVE_DATUM_DOCUMENT_SCHEMA,
    SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA,
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
    SystemDatumResourceRow,
    SystemDatumStoreRequest,
    SystemDatumWorkbenchResult,
)


class SystemDatumStoreContractTests(unittest.TestCase):
    def test_request_row_and_result_are_serializable(self) -> None:
        request = SystemDatumStoreRequest.from_dict({"tenant_id": "FND"})
        row = SystemDatumResourceRow(
            resource_id="0-0-1",
            subject_ref="0-0-1",
            relation="~",
            object_ref="0-0-0",
            labels=("time-ordinal-position",),
            raw=[["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]],
        )
        result = SystemDatumWorkbenchResult(
            tenant_id=request.tenant_id,
            rows=(row,),
            source_files={"anthology": "/tmp/data/system/anthology.json"},
            materialization_status={"canonical_source": "loaded", "legacy_root_fallback": "blocked"},
        )

        self.assertEqual(request.tenant_id, "fnd")
        payload = result.to_dict()
        self.assertEqual(payload["schema"], SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["row_count"], 1)
        self.assertEqual(json.loads(json.dumps(payload, sort_keys=True)), payload)

    def test_contracts_reject_missing_identity_or_non_json_raw_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "tenant_id is required"):
            SystemDatumStoreRequest.from_dict({"tenant_id": ""})

        with self.assertRaisesRegex(ValueError, "resource_id is required"):
            SystemDatumResourceRow(
                resource_id="",
                subject_ref="",
                relation="",
                object_ref="",
                labels=(),
                raw={},
            )

        with self.assertRaisesRegex(ValueError, "JSON-serializable"):
            SystemDatumResourceRow(
                resource_id="0-0-1",
                subject_ref="0-0-1",
                relation="~",
                object_ref="0-0-0",
                labels=(),
                raw={"bad": object()},
            )

    def test_authoritative_document_contracts_serialize_and_preserve_anchor_rows(self) -> None:
        request = AuthoritativeDatumDocumentRequest.from_dict({"tenant_id": "FND"})
        row = AuthoritativeDatumDocumentRow(
            datum_address="4-2-118",
            raw=[["4-2-118", "rf.3-1-3", "HERE"], ["summit_county_cities"]],
        )
        document = AuthoritativeDatumDocument(
            document_id="sandbox:maps:sc.example.json",
            source_kind="sandbox_source",
            document_name="sc.example.json",
            relative_path="sandbox/maps/sources/sc.example.json",
            tool_id="maps",
            anchor_document_name="tool.maps.json",
            anchor_document_path="sandbox/maps/tool.maps.json",
            anchor_rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="3-1-3",
                    raw=[["3-1-3", "2-1-1", "0"], ["title-babelette"]],
                ),
            ),
            rows=(row,),
        )
        result = AuthoritativeDatumDocumentCatalogResult(
            tenant_id=request.tenant_id,
            documents=(document,),
            source_files={"sandbox_source_documents": ["/tmp/data/sandbox/maps/sources/sc.example.json"]},
            readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
        )

        payload = result.to_dict()
        self.assertEqual(payload["schema"], AUTHORITATIVE_DATUM_DOCUMENT_CATALOG_SCHEMA)
        self.assertEqual(payload["documents"][0]["schema"], AUTHORITATIVE_DATUM_DOCUMENT_SCHEMA)
        self.assertEqual(
            payload["documents"][0]["anchor_rows"][0]["schema"],
            AUTHORITATIVE_DATUM_DOCUMENT_ROW_SCHEMA,
        )
        self.assertEqual(payload["documents"][0]["rows"][0]["raw"][0][2], "HERE")
        self.assertEqual(json.loads(json.dumps(payload, sort_keys=True)), payload)

    def test_authoritative_document_contracts_reject_invalid_kinds_and_missing_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "tenant_id is required"):
            AuthoritativeDatumDocumentRequest.from_dict({"tenant_id": ""})

        with self.assertRaisesRegex(ValueError, "datum_address is required"):
            AuthoritativeDatumDocumentRow(
                datum_address="",
                raw={},
            )

        with self.assertRaisesRegex(ValueError, "source_kind is invalid"):
            AuthoritativeDatumDocument(
                document_id="bad",
                source_kind="cache",
                document_name="bad.json",
                relative_path="bad.json",
                rows=(),
            )


if __name__ == "__main__":
    unittest.main()
