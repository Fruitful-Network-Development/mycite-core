from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

if "boto3" not in sys.modules:
    try:
        import boto3  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        fake = types.SimpleNamespace(client=lambda *args, **kwargs: object())
        sys.modules["boto3"] = fake  # type: ignore[assignment]

from MyCiteV2.packages.adapters.event_transport import aws_csm_inbound_capture_lambda as lam


class _FakeSesV2:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_email(self, *, FromEmailAddress: str, Destination: dict[str, object], Content: dict[str, object]) -> dict[str, object]:
        self.calls.append(
            {
                "from": FromEmailAddress,
                "destination": Destination,
                "content": Content,
            }
        )
        return {"MessageId": "ses-message-001"}


class AwsCsmInboundCaptureLambdaTests(unittest.TestCase):
    def test_verification_routes_accepts_compact_string_and_short_dict_entries(self) -> None:
        previous_json = lam.VERIFICATION_ROUTE_MAP_JSON
        previous_cache = lam._cached_routes
        try:
            lam.VERIFICATION_ROUTE_MAP_JSON = (
                '{'
                '"admin@cuyahogavalleycountrysideconservancy.org":"dylancarsonmontgomery@gmail.com",'
                '"news@cuyahogavalleycountrysideconservancy.org":{"f":"dylancarsonmontgomery@gmail.com","p":"generic_manual"}'
                '}'
            )
            lam._cached_routes = None
            routes = lam._verification_routes()
        finally:
            lam.VERIFICATION_ROUTE_MAP_JSON = previous_json
            lam._cached_routes = previous_cache
        self.assertEqual(
            routes["admin@cuyahogavalleycountrysideconservancy.org"]["resolved_forward_to_email"],
            "dylancarsonmontgomery@gmail.com",
        )
        self.assertEqual(routes["news@cuyahogavalleycountrysideconservancy.org"]["handoff_provider"], "generic_manual")

    def test_decision_accepts_outlook_confirmation_with_link(self) -> None:
        raw = (
            "From: no-reply@microsoft.com\r\n"
            "To: admin@cuyahogavalleycountrysideconservancy.org\r\n"
            "Subject: Verify your email address\r\n"
            "\r\n"
            "Verify at https://outlook.live.com/verify\r\n"
        ).encode("utf-8")
        decision = lam._decision(
            tracked_recipients={"admin@cuyahogavalleycountrysideconservancy.org"},
            sender="no-reply@microsoft.com",
            recipient="admin@cuyahogavalleycountrysideconservancy.org",
            subject="Verify your email address",
            raw_bytes=raw,
            handoff_provider="outlook",
        )
        self.assertTrue(decision["should_forward"])
        self.assertEqual(decision["reason"], "outlook_confirmation")

    def test_decision_accepts_generic_manual_without_sender_allowlist(self) -> None:
        raw = (
            "From: any@customdomain.example\r\n"
            "To: news@cuyahogavalleycountrysideconservancy.org\r\n"
            "Subject: Please verify sender\r\n"
            "\r\n"
            "Open https://example.org/verify\r\n"
        ).encode("utf-8")
        decision = lam._decision(
            tracked_recipients={"news@cuyahogavalleycountrysideconservancy.org"},
            sender="any@customdomain.example",
            recipient="news@cuyahogavalleycountrysideconservancy.org",
            subject="Please verify sender",
            raw_bytes=raw,
            handoff_provider="generic_manual",
        )
        self.assertTrue(decision["should_forward"])

    def test_send_verification_forward_prefers_resolved_forward_target(self) -> None:
        fake = _FakeSesV2()
        previous = lam._sesv2
        lam._sesv2 = fake
        try:
            result = lam._send_verification_forward(
                route={
                    "forward_to_email": "admin@cuyahogavalleycountrysideconservancy.org",
                    "resolved_forward_to_email": "dylancarsonmontgomery@gmail.com",
                    "handoff_provider": "gmail",
                },
                tracked_recipient="news@cuyahogavalleycountrysideconservancy.org",
                sender="gmail-noreply@google.com",
                subject="Gmail Confirmation - Send Mail as news@cuyahogavalleycountrysideconservancy.org",
                links=["https://mail.google.com/verify"],
                s3_uri="s3://ses-inbound-fnd-mail/inbound/cuyahogavalleycountrysideconservancy.org/msg-1",
            )
        finally:
            lam._sesv2 = previous
        self.assertEqual(result["sent_to"], "dylancarsonmontgomery@gmail.com")
        self.assertEqual(
            fake.calls[0]["destination"],
            {"ToAddresses": ["dylancarsonmontgomery@gmail.com"]},
        )


if __name__ == "__main__":
    unittest.main()
