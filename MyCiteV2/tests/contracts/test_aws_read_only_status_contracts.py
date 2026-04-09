from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.aws_read_only_status import (
    AwsReadOnlyStatusRequest,
    AwsReadOnlyStatusResult,
    AwsReadOnlyStatusSource,
)


class AwsReadOnlyStatusContractTests(unittest.TestCase):
    def test_request_and_source_are_explicit_and_serializable(self) -> None:
        request = AwsReadOnlyStatusRequest.from_dict({"tenant_scope_id": "tenant-a"})
        source = AwsReadOnlyStatusSource.from_dict(
            {
                "payload": {
                    "tenant_scope_id": "tenant-a",
                    "mailbox_readiness": "ready",
                    "smtp_state": "smtp_ready",
                }
            }
        )

        self.assertEqual(
            json.loads(json.dumps(request.to_dict(), sort_keys=True)),
            request.to_dict(),
        )
        self.assertEqual(
            json.loads(json.dumps(source.to_dict(), sort_keys=True)),
            source.to_dict(),
        )

    def test_contracts_reject_missing_scope_or_bad_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "tenant_scope_id is required"):
            AwsReadOnlyStatusRequest.from_dict({"tenant_scope_id": ""})

        with self.assertRaisesRegex(ValueError, "non-empty dict"):
            AwsReadOnlyStatusSource.from_dict({"payload": {}})

        with self.assertRaisesRegex(ValueError, "JSON-serializable"):
            AwsReadOnlyStatusSource.from_dict({"payload": {"bad": object()}})

    def test_result_supports_found_and_not_found_shapes(self) -> None:
        found = AwsReadOnlyStatusResult.from_dict(
            {
                "source": {
                    "payload": {
                        "tenant_scope_id": "tenant-a",
                        "mailbox_readiness": "ready",
                    }
                }
            }
        )
        missing = AwsReadOnlyStatusResult.from_dict({"source": None})

        self.assertTrue(found.found)
        self.assertEqual(
            found.to_dict(),
            {
                "found": True,
                "source": {
                    "payload": {
                        "tenant_scope_id": "tenant-a",
                        "mailbox_readiness": "ready",
                    }
                },
            },
        )
        self.assertFalse(missing.found)
        self.assertEqual(missing.to_dict(), {"found": False, "source": None})


if __name__ == "__main__":
    unittest.main()
