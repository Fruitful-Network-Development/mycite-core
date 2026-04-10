from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store import (
    SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA,
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


if __name__ == "__main__":
    unittest.main()
