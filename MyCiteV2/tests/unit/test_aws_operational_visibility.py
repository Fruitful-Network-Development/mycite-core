from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.aws_operational_visibility import (
    AwsOperationalVisibilityService,
    AwsReadOnlyOperationalVisibility,
    FORBIDDEN_AWS_VISIBILITY_KEYS,
    normalize_aws_operational_visibility,
)
from MyCiteV2.packages.ports.aws_read_only_status import AwsReadOnlyStatusResult, AwsReadOnlyStatusSource


class _FakeAwsReadOnlyStatusPort:
    def __init__(self, payload: dict[str, object] | None) -> None:
        self.payload = payload
        self.requests = []

    def read_aws_read_only_status(self, request):
        self.requests.append(request)
        if self.payload is None:
            return AwsReadOnlyStatusResult(source=None)
        return AwsReadOnlyStatusResult(source=AwsReadOnlyStatusSource(payload=self.payload))


class AwsOperationalVisibilityTests(unittest.TestCase):
    def test_normalization_derives_compatibility_warning_and_safe_summary(self) -> None:
        summary = normalize_aws_operational_visibility(
            {
                "tenant_scope_id": "tenant-a",
                "mailbox_readiness": "ready_for_gmail_handoff",
                "smtp_state": "smtp_ready",
                "gmail_state": "gmail_pending",
                "verified_evidence_state": "sender_selected",
                "selected_verified_sender": "alerts@example.com",
                "canonical_newsletter_profile": {
                    "profile_id": "newsletter.example.com",
                    "domain": "example.com",
                    "list_address": "news@example.com",
                    "selected_verified_sender": "alerts@example.com",
                    "delivery_mode": "inbound-mail-only",
                },
                "compatibility": {
                    "canonical_profile_matches_compatibility_inputs": False,
                },
                "inbound_capture": {
                    "status": "ready",
                    "last_capture_state": "idle",
                },
                "dispatch_health": {
                    "status": "healthy",
                    "last_delivery_outcome": "ok",
                    "pending_message_count": 0,
                },
            }
        )

        self.assertIsInstance(summary, AwsReadOnlyOperationalVisibility)
        self.assertEqual(
            summary.to_dict(),
            {
                "tenant_scope_id": "tenant-a",
                "mailbox_readiness": "ready_for_gmail_handoff",
                "smtp_state": "smtp_ready",
                "gmail_state": "gmail_pending",
                "verified_evidence_state": "sender_selected",
                "selected_verified_sender": "alerts@example.com",
                "allowed_send_domains": ["example.com"],
                "canonical_newsletter_profile": {
                    "profile_id": "newsletter.example.com",
                    "domain": "example.com",
                    "list_address": "news@example.com",
                    "selected_verified_sender": "alerts@example.com",
                    "delivery_mode": "inbound-mail-only",
                },
                "compatibility_warnings": [
                    "Compatibility-read newsletter metadata disagrees with the canonical newsletter operational profile."
                ],
                "inbound_capture": {
                    "status": "ready",
                    "last_capture_state": "idle",
                },
                "dispatch_health": {
                    "status": "healthy",
                    "last_delivery_outcome": "ok",
                    "pending_message_count": 0,
                },
            },
        )

    def test_secret_bearing_keys_and_sender_mismatch_are_rejected(self) -> None:
        forbidden_key = sorted(FORBIDDEN_AWS_VISIBILITY_KEYS)[0]
        with self.assertRaisesRegex(ValueError, "forbidden in aws operational visibility"):
            normalize_aws_operational_visibility(
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
                    "dispatch_health": {"status": "healthy"},
                    forbidden_key: "bad",
                }
            )

        with self.assertRaisesRegex(ValueError, "must match canonical_newsletter_profile"):
            normalize_aws_operational_visibility(
                {
                    "tenant_scope_id": "tenant-a",
                    "mailbox_readiness": "ready",
                    "smtp_state": "smtp_ready",
                    "gmail_state": "gmail_verified",
                    "verified_evidence_state": "verified_evidence_present",
                    "selected_verified_sender": "other@example.com",
                    "canonical_newsletter_profile": {
                        "profile_id": "newsletter.example.com",
                        "domain": "example.com",
                        "list_address": "news@example.com",
                        "selected_verified_sender": "alerts@example.com",
                        "delivery_mode": "inbound-mail-only",
                    },
                    "compatibility": {"canonical_profile_matches_compatibility_inputs": True},
                    "inbound_capture": {"status": "ready"},
                    "dispatch_health": {"status": "healthy"},
                }
            )

    def test_secondary_send_domain_must_cover_selected_sender(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowed_send_domains"):
            normalize_aws_operational_visibility(
                {
                    "tenant_scope_id": "tenant-a",
                    "mailbox_readiness": "ready",
                    "smtp_state": "smtp_ready",
                    "gmail_state": "gmail_verified",
                    "verified_evidence_state": "verified_evidence_present",
                    "selected_verified_sender": "board@cvccboard.org",
                    "allowed_send_domains": ["cuyahogavalleycountrysideconservancy.org"],
                    "canonical_newsletter_profile": {
                        "profile_id": "aws-csm.cvcc.technicalContact",
                        "domain": "cuyahogavalleycountrysideconservancy.org",
                        "list_address": "board@cvccboard.org",
                        "selected_verified_sender": "board@cvccboard.org",
                        "delivery_mode": "inbound-mail-only",
                    },
                    "compatibility": {"canonical_profile_matches_compatibility_inputs": True},
                    "inbound_capture": {"status": "ready"},
                    "dispatch_health": {"status": "healthy"},
                }
            )

        summary = normalize_aws_operational_visibility(
            {
                "tenant_scope_id": "tenant-a",
                "mailbox_readiness": "ready",
                "smtp_state": "smtp_ready",
                "gmail_state": "gmail_verified",
                "verified_evidence_state": "verified_evidence_present",
                "selected_verified_sender": "board@cvccboard.org",
                "allowed_send_domains": ["cvccboard.org"],
                "canonical_newsletter_profile": {
                    "profile_id": "aws-csm.cvcc.technicalContact",
                    "domain": "cuyahogavalleycountrysideconservancy.org",
                    "list_address": "board@cvccboard.org",
                    "selected_verified_sender": "board@cvccboard.org",
                    "delivery_mode": "inbound-mail-only",
                },
                "compatibility": {"canonical_profile_matches_compatibility_inputs": True},
                "inbound_capture": {"status": "ready"},
                "dispatch_health": {"status": "healthy"},
            }
        )
        self.assertEqual(
            list(summary.allowed_send_domains),
            ["cuyahogavalleycountrysideconservancy.org", "cvccboard.org"],
        )

    def test_service_reads_through_port_and_returns_none_when_missing(self) -> None:
        payload = {
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
            "dispatch_health": {"status": "healthy", "pending_message_count": 1},
        }
        service = AwsOperationalVisibilityService(_FakeAwsReadOnlyStatusPort(payload))
        missing_service = AwsOperationalVisibilityService(_FakeAwsReadOnlyStatusPort(None))

        result = service.read_surface("tenant-a")
        missing = missing_service.read_surface("tenant-a")

        self.assertEqual(result.to_dict()["allowed_send_domains"], ["example.com"])
        self.assertEqual(
            result.to_dict()["dispatch_health"],
            {
                "status": "healthy",
                "last_delivery_outcome": "unknown",
                "pending_message_count": 1,
            },
        )
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
