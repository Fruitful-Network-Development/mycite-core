from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.aws_narrow_write import (
    ALLOWED_AWS_NARROW_WRITE_FIELDS,
    AwsNarrowWriteCommand,
    AwsNarrowWriteService,
    normalize_aws_narrow_write_command,
)
from MyCiteV2.packages.ports.aws_narrow_write import AwsNarrowWriteResult, AwsNarrowWriteSource

FOCUS_SUBJECT = "3-2-3-17-77-1-6-4-1-4.4-1-77"


class _FakeAwsNarrowWritePort:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests = []

    def apply_aws_narrow_write(self, request):
        self.requests.append(request)
        return AwsNarrowWriteResult(source=AwsNarrowWriteSource(payload=self.payload))


class AwsNarrowWriteTests(unittest.TestCase):
    def test_command_normalizes_focus_subject_and_selected_verified_sender(self) -> None:
        command = normalize_aws_narrow_write_command(
            {
                "tenant_scope_id": "tenant-a",
                "focus_subject": "3-2-3-17-77-1-6-4-1-4-4-1-77",
                "profile_id": "newsletter.example.com",
                "selected_verified_sender": " Alerts@Example.com ",
            }
        )

        self.assertEqual(
            command.to_dict(),
            {
                "tenant_scope_id": "tenant-a",
                "focus_subject": FOCUS_SUBJECT,
                "profile_id": "newsletter.example.com",
                "selected_verified_sender": "alerts@example.com",
                "writable_field_set": ["selected_verified_sender"],
            },
        )
        self.assertEqual(ALLOWED_AWS_NARROW_WRITE_FIELDS, frozenset({"selected_verified_sender"}))

    def test_command_rejects_unapproved_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            normalize_aws_narrow_write_command(
                {
                    "tenant_scope_id": "tenant-a",
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "alerts@example.com",
                    "delivery_mode": "inbound-mail-only",
                }
            )

    def test_service_applies_write_and_prepares_local_audit_payload(self) -> None:
        service = AwsNarrowWriteService(
            _FakeAwsNarrowWritePort(
                {
                    "tenant_scope_id": "tenant-a",
                    "mailbox_readiness": "ready",
                    "smtp_state": "smtp_ready",
                    "gmail_state": "gmail_verified",
                    "verified_evidence_state": "verified_evidence_present",
                    "selected_verified_sender": "alerts@example.com",
                    "canonical_newsletter_profile": {
                        "profile_id": "newsletter.example.com",
                        "domain": "example.com",
                        "list_address": "news@example.com",
                        "selected_verified_sender": "alerts@example.com",
                        "delivery_mode": "inbound-mail-only",
                    },
                    "compatibility": {"canonical_profile_matches_compatibility_inputs": True},
                    "inbound_capture": {"status": "ready"},
                    "dispatch_health": {"status": "healthy", "pending_message_count": 0},
                }
            )
        )

        outcome = service.apply_write(
            AwsNarrowWriteCommand(
                tenant_scope_id="tenant-a",
                focus_subject=FOCUS_SUBJECT,
                profile_id="newsletter.example.com",
                selected_verified_sender="alerts@example.com",
            )
        )

        self.assertEqual(
            outcome.to_dict()["updated_fields"],
            ["selected_verified_sender"],
        )
        self.assertEqual(
            outcome.to_local_audit_payload(),
            {
                "event_type": "aws.operational.write.accepted",
                "focus_subject": FOCUS_SUBJECT,
                "shell_verb": "admin.aws.narrow_write",
                "details": {
                    "tenant_scope_id": "tenant-a",
                    "profile_id": "newsletter.example.com",
                    "updated_fields": ["selected_verified_sender"],
                    "selected_verified_sender": "alerts@example.com",
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
