from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.aws_csm_forwarder_filter import (
    AwsCsmVerificationForwardFilter,
)


def _message_bytes(body: str) -> bytes:
    return (
        "From: gmail-noreply@google.com\r\n"
        "To: mark@trappfamilyfarm.com\r\n"
        "Subject: Gmail Confirmation - Send Mail as mark@trappfamilyfarm.com\r\n"
        "\r\n"
        + body
    ).encode("utf-8")


class AwsCsmForwarderFilterTests(unittest.TestCase):
    def test_accepts_tracked_gmail_confirmation_with_link(self) -> None:
        decision = AwsCsmVerificationForwardFilter().decide(
            tracked_recipients={"mark@trappfamilyfarm.com"},
            sender="gmail-noreply@google.com",
            recipient="mark@trappfamilyfarm.com",
            subject="Gmail Confirmation - Send Mail as mark@trappfamilyfarm.com",
            raw_bytes=_message_bytes("Click https://mail.google.com/mail/u/0/?ui=2&ik=verify to confirm."),
        )

        self.assertTrue(decision.should_forward)
        self.assertEqual(decision.classification, "verification_confirmation")
        self.assertGreaterEqual(decision.confirmation_link_count, 1)

    def test_rejects_report_mail_like_dmarc_forward(self) -> None:
        raw_bytes = (
            "From: noreply-dmarc-support@google.com\r\n"
            "To: mark@trappfamilyfarm.com\r\n"
            "Subject: [FWD] Report domain: fruitfulnetworkdevelopment.com Submitter: google.com Report-ID: 4554987642169396140\r\n"
            "\r\n"
            "Forwarded message received by SES."
        ).encode("utf-8")
        decision = AwsCsmVerificationForwardFilter().decide(
            tracked_recipients={"mark@trappfamilyfarm.com"},
            sender="noreply-dmarc-support@google.com",
            recipient="mark@trappfamilyfarm.com",
            subject="[FWD] Report domain: fruitfulnetworkdevelopment.com Submitter: google.com Report-ID: 4554987642169396140",
            raw_bytes=raw_bytes,
        )

        self.assertFalse(decision.should_forward)
        self.assertEqual(decision.classification, "blocked_report")

    def test_accepts_outlook_confirmation_policy(self) -> None:
        raw_bytes = (
            "From: no-reply@microsoft.com\r\n"
            "To: admin@cuyahogavalleycountrysideconservancy.org\r\n"
            "Subject: Verify your email address\r\n"
            "\r\n"
            "Open https://outlook.live.com/verify now.\r\n"
        ).encode("utf-8")
        decision = AwsCsmVerificationForwardFilter().decide(
            tracked_recipients={"admin@cuyahogavalleycountrysideconservancy.org"},
            sender="no-reply@microsoft.com",
            recipient="admin@cuyahogavalleycountrysideconservancy.org",
            subject="Verify your email address",
            raw_bytes=raw_bytes,
            handoff_provider="outlook",
        )
        self.assertTrue(decision.should_forward)
        self.assertEqual(decision.classification, "verification_confirmation")

    def test_generic_manual_does_not_require_sender_allowlist(self) -> None:
        raw_bytes = (
            "From: admin@custom-provider.example\r\n"
            "To: news@cuyahogavalleycountrysideconservancy.org\r\n"
            "Subject: Please verify this sender\r\n"
            "\r\n"
            "Verify at https://example.org/confirm\r\n"
        ).encode("utf-8")
        decision = AwsCsmVerificationForwardFilter().decide(
            tracked_recipients={"news@cuyahogavalleycountrysideconservancy.org"},
            sender="admin@custom-provider.example",
            recipient="news@cuyahogavalleycountrysideconservancy.org",
            subject="Please verify this sender",
            raw_bytes=raw_bytes,
            handoff_provider="generic_manual",
        )
        self.assertTrue(decision.should_forward)


if __name__ == "__main__":
    unittest.main()
