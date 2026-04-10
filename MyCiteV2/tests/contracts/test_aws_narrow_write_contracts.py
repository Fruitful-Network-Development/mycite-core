from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.aws_narrow_write import (
    AwsNarrowWriteRequest,
    AwsNarrowWriteResult,
    AwsNarrowWriteSource,
)


class AwsNarrowWriteContractTests(unittest.TestCase):
    def test_request_and_result_are_explicit_and_serializable(self) -> None:
        request = AwsNarrowWriteRequest.from_dict(
            {
                "tenant_scope_id": "tenant-a",
                "profile_id": "newsletter.example.com",
                "selected_verified_sender": "alerts@example.com",
            }
        )
        result = AwsNarrowWriteResult.from_dict(
            {
                "source": {
                    "payload": {
                        "tenant_scope_id": "tenant-a",
                        "selected_verified_sender": "alerts@example.com",
                    }
                }
            }
        )

        self.assertEqual(
            json.loads(json.dumps(request.to_dict(), sort_keys=True)),
            request.to_dict(),
        )
        self.assertEqual(
            json.loads(json.dumps(result.to_dict(), sort_keys=True)),
            result.to_dict(),
        )

    def test_request_rejects_missing_fields_or_bad_sender(self) -> None:
        with self.assertRaisesRegex(ValueError, "tenant_scope_id is required"):
            AwsNarrowWriteRequest.from_dict(
                {
                    "tenant_scope_id": "",
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "alerts@example.com",
                }
            )

        with self.assertRaisesRegex(ValueError, "email-like"):
            AwsNarrowWriteRequest.from_dict(
                {
                    "tenant_scope_id": "tenant-a",
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "not-email",
                }
            )

        with self.assertRaisesRegex(ValueError, "non-empty dict"):
            AwsNarrowWriteSource.from_dict({"payload": {}})


if __name__ == "__main__":
    unittest.main()
