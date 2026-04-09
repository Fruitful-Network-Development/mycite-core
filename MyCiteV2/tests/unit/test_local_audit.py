from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.local_audit import (
    LocalAuditRecord,
    LocalAuditService,
    StoredLocalAuditRecord,
    normalize_local_audit_record,
)
from MyCiteV2.packages.ports.audit_log import (
    AuditLogAppendReceipt,
    AuditLogReadResult,
    AuditLogRecord,
)

MSN_ID = "3-2-3-17-77-1-6-4-1-4"
CANONICAL_SUBJECT = f"{MSN_ID}.4-1-77"
LEGACY_HYPHEN_SUBJECT = f"{MSN_ID}-4-1-77"


class _FakeAuditLogPort:
    def __init__(self) -> None:
        self.append_requests = []
        self.read_requests = []
        self.record = None

    def append_audit_record(self, request):
        self.append_requests.append(request)
        return AuditLogAppendReceipt(record_id="audit-0001", recorded_at_unix_ms=1770000000001)

    def read_audit_record(self, request):
        self.read_requests.append(request)
        return AuditLogReadResult(record=self.record)


class LocalAuditUnitTests(unittest.TestCase):
    def test_local_audit_record_normalizes_subject_and_text_fields(self) -> None:
        record = normalize_local_audit_record(
            {
                "event_type": "Shell.Transition.Accepted",
                "focus_subject": LEGACY_HYPHEN_SUBJECT,
                "shell_verb": " NAVIGATE ",
                "details": {"source": "mvp"},
            }
        )

        self.assertEqual(
            record.to_dict(),
            {
                "event_type": "shell.transition.accepted",
                "focus_subject": CANONICAL_SUBJECT,
                "shell_verb": "navigate",
                "details": {"source": "mvp"},
            },
        )

    def test_local_audit_rejects_forbidden_and_unsupported_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            normalize_local_audit_record(
                {
                    "event_type": "shell.transition.accepted",
                    "focus_subject": CANONICAL_SUBJECT,
                    "shell_verb": "navigate",
                    "secret": "bad",
                }
            )

        with self.assertRaisesRegex(ValueError, "forbidden in local audit"):
            normalize_local_audit_record(
                {
                    "event_type": "shell.transition.accepted",
                    "focus_subject": CANONICAL_SUBJECT,
                    "shell_verb": "navigate",
                    "details": {"password": "bad"},
                }
            )

    def test_append_handoff_uses_normalized_port_payload(self) -> None:
        port = _FakeAuditLogPort()
        service = LocalAuditService(port)

        receipt = service.append_record(
            {
                "event_type": "shell.transition.accepted",
                "focus_subject": LEGACY_HYPHEN_SUBJECT,
                "shell_verb": "navigate",
                "details": {"source": "mvp"},
            }
        )

        self.assertEqual(receipt.record_id, "audit-0001")
        self.assertEqual(len(port.append_requests), 1)
        self.assertEqual(
            port.append_requests[0].to_dict(),
            {
                "record": {
                    "event_type": "shell.transition.accepted",
                    "focus_subject": CANONICAL_SUBJECT,
                    "shell_verb": "navigate",
                    "details": {"source": "mvp"},
                }
            },
        )

    def test_read_by_id_handoff_returns_semantic_record(self) -> None:
        port = _FakeAuditLogPort()
        port.record = AuditLogRecord(
            record_id="audit-0001",
            recorded_at_unix_ms=1770000000001,
            record={
                "event_type": "shell.transition.accepted",
                "focus_subject": LEGACY_HYPHEN_SUBJECT,
                "shell_verb": "navigate",
                "details": {"source": "mvp"},
            },
        )
        service = LocalAuditService(port)

        stored = service.read_record("audit-0001")

        self.assertEqual(len(port.read_requests), 1)
        self.assertIsInstance(stored, StoredLocalAuditRecord)
        self.assertEqual(
            stored.to_dict(),
            {
                "record_id": "audit-0001",
                "recorded_at_unix_ms": 1770000000001,
                "record": {
                    "event_type": "shell.transition.accepted",
                    "focus_subject": CANONICAL_SUBJECT,
                    "shell_verb": "navigate",
                    "details": {"source": "mvp"},
                },
            },
        )

    def test_read_by_id_returns_none_when_not_found(self) -> None:
        port = _FakeAuditLogPort()
        service = LocalAuditService(port)

        self.assertIsNone(service.read_record("missing"))


if __name__ == "__main__":
    unittest.main()
