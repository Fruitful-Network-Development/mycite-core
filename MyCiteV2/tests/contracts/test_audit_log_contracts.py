from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.audit_log import (
    AUDIT_LOG_RECENT_WINDOW_LIMIT,
    AuditLogAppendReceipt,
    AuditLogAppendRequest,
    AuditLogRecentWindowRequest,
    AuditLogRecentWindowResult,
    AuditLogReadRequest,
    AuditLogReadResult,
    AuditLogRecord,
)


class AuditLogContractTests(unittest.TestCase):
    def test_append_request_accepts_one_normalized_record_payload(self) -> None:
        request = AuditLogAppendRequest.from_dict(
            {
                "record": {
                    "event_type": "shell.transition.accepted",
                    "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                    "shell_verb": "navigate",
                    "details": {"source": "mvp"},
                }
            }
        )

        self.assertEqual(
            request.to_dict(),
            {
                "record": {
                    "event_type": "shell.transition.accepted",
                    "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                    "shell_verb": "navigate",
                    "details": {"source": "mvp"},
                }
            },
        )

    def test_append_request_rejects_non_json_or_empty_record_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty dict"):
            AuditLogAppendRequest.from_dict({"record": {}})

        with self.assertRaisesRegex(ValueError, "JSON-serializable"):
            AuditLogAppendRequest.from_dict({"record": {"bad": object()}})

        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            AuditLogAppendRequest.from_dict({"record": {"": "bad"}})

    def test_append_receipt_and_read_request_are_explicit_and_serializable(self) -> None:
        receipt = AuditLogAppendReceipt.from_dict(
            {
                "record_id": "audit-0001",
                "recorded_at_unix_ms": 1770000000001,
            }
        )
        read_request = AuditLogReadRequest.from_dict({"record_id": "audit-0001"})

        self.assertEqual(
            json.loads(json.dumps(receipt.to_dict(), sort_keys=True)),
            receipt.to_dict(),
        )
        self.assertEqual(
            json.loads(json.dumps(read_request.to_dict(), sort_keys=True)),
            read_request.to_dict(),
        )

    def test_read_result_supports_found_and_not_found_shapes(self) -> None:
        found = AuditLogReadResult.from_dict(
            {
                "record": {
                    "record_id": "audit-0001",
                    "recorded_at_unix_ms": 1770000000001,
                    "record": {
                        "event_type": "shell.transition.accepted",
                        "shell_verb": "navigate",
                    },
                }
            }
        )
        missing = AuditLogReadResult.from_dict({"record": None})

        self.assertTrue(found.found)
        self.assertEqual(
            found.to_dict(),
            {
                "found": True,
                "record": {
                    "record_id": "audit-0001",
                    "recorded_at_unix_ms": 1770000000001,
                    "record": {
                        "event_type": "shell.transition.accepted",
                        "shell_verb": "navigate",
                    },
                },
            },
        )
        self.assertFalse(missing.found)
        self.assertEqual(missing.to_dict(), {"found": False, "record": None})

    def test_recent_window_request_is_fixed_and_serializable(self) -> None:
        request = AuditLogRecentWindowRequest.from_dict({})

        self.assertEqual(request.to_dict(), {"limit": AUDIT_LOG_RECENT_WINDOW_LIMIT})
        self.assertEqual(
            json.loads(json.dumps(request.to_dict(), sort_keys=True)),
            request.to_dict(),
        )

        with self.assertRaisesRegex(ValueError, str(AUDIT_LOG_RECENT_WINDOW_LIMIT)):
            AuditLogRecentWindowRequest.from_dict({"limit": 10})

    def test_recent_window_result_serializes_records_newest_first(self) -> None:
        result = AuditLogRecentWindowResult.from_dict(
            {
                "records": [
                    {
                        "record_id": "audit-0002",
                        "recorded_at_unix_ms": 1770000000002,
                        "record": {"event_type": "shell.transition.accepted"},
                    },
                    {
                        "record_id": "audit-0001",
                        "recorded_at_unix_ms": 1770000000001,
                        "record": {"event_type": "shell.transition.accepted"},
                    },
                ]
            }
        )

        self.assertEqual(
            result.to_dict(),
            {
                "record_count": 2,
                "records": [
                    {
                        "record_id": "audit-0002",
                        "recorded_at_unix_ms": 1770000000002,
                        "record": {"event_type": "shell.transition.accepted"},
                    },
                    {
                        "record_id": "audit-0001",
                        "recorded_at_unix_ms": 1770000000001,
                        "record": {"event_type": "shell.transition.accepted"},
                    },
                ],
            },
        )

    def test_record_contract_rejects_missing_identifier_or_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "record_id is required"):
            AuditLogRecord.from_dict(
                {
                    "record_id": "",
                    "recorded_at_unix_ms": 1770000000001,
                    "record": {"event_type": "ok"},
                }
            )

        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            AuditLogRecord.from_dict(
                {
                    "record_id": "audit-0001",
                    "recorded_at_unix_ms": -1,
                    "record": {"event_type": "ok"},
                }
            )


if __name__ == "__main__":
    unittest.main()
