"""Unit tests for `AwsPeripheralCloudAdapter` SES send surface."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.peripherals.aws.cloud_adapter import AwsPeripheralCloudAdapter
from MyCiteV2.packages.peripherals.aws.contracts import SesSendError, SesSendResult


def _profile() -> dict[str, Any]:
    return {
        "identity": "dylan@fruitfulnetworkdevelopment.com",
        "region": "us-east-1",
        "from_name": "Dylan Montgomery",
        "from_address": "dylan@fruitfulnetworkdevelopment.com",
        "configuration_set": "fnd-default",
        "reply_to": "dylan@fruitfulnetworkdevelopment.com",
    }


class _StubSesClient:
    def __init__(self) -> None:
        self.send_raw_email_calls: list[dict[str, Any]] = []
        self.next_response: dict[str, Any] = {"MessageId": "msg-1234"}
        self.next_exception: Exception | None = None

    def send_raw_email(self, **kwargs: Any) -> dict[str, Any]:
        self.send_raw_email_calls.append(kwargs)
        if self.next_exception is not None:
            raise self.next_exception
        return self.next_response


class SendSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stub = _StubSesClient()
        self.adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
        # Pre-seed the region-keyed cache so _client returns our stub.
        self.adapter._cached_clients["ses@us-east-1"] = self.stub

    def test_send_email_passes_configuration_set_and_from_header(self) -> None:
        result = self.adapter.send_email(
            aws_ses_profile=_profile(),
            to=["visitor@example.com"],
            subject="hi",
            body_text="hello world",
            reply_to=["dylan@fruitfulnetworkdevelopment.com"],
        )
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["message_id"], "msg-1234")
        self.assertEqual(result["configuration_set"], "fnd-default")
        self.assertEqual(len(self.stub.send_raw_email_calls), 1)
        call = self.stub.send_raw_email_calls[0]
        self.assertEqual(call["Source"], "dylan@fruitfulnetworkdevelopment.com")
        self.assertEqual(call["Destinations"], ["visitor@example.com"])
        self.assertEqual(call["ConfigurationSetName"], "fnd-default")
        raw = call["RawMessage"]["Data"]
        self.assertIn(b'From: "Dylan Montgomery" <dylan@fruitfulnetworkdevelopment.com>', raw)
        self.assertIn(b"Reply-To: dylan@fruitfulnetworkdevelopment.com", raw)
        self.assertIn(b"Subject: hi", raw)
        self.assertIn(b"hello world", raw)

    def test_send_email_omits_configuration_set_when_absent(self) -> None:
        profile = _profile()
        profile.pop("configuration_set")
        self.adapter.send_email(
            aws_ses_profile=profile,
            to=["visitor@example.com"],
            subject="x",
            body_text="x",
        )
        call = self.stub.send_raw_email_calls[0]
        self.assertNotIn("ConfigurationSetName", call)

    def test_send_email_includes_extra_headers(self) -> None:
        self.adapter.send_email(
            aws_ses_profile=_profile(),
            to=["visitor@example.com"],
            subject="x",
            body_text="x",
            extra_headers={
                "List-Unsubscribe": "<https://example.test/unsub>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        )
        raw = self.stub.send_raw_email_calls[0]["RawMessage"]["Data"]
        self.assertIn(b"List-Unsubscribe: <https://example.test/unsub>", raw)
        self.assertIn(b"List-Unsubscribe-Post: List-Unsubscribe=One-Click", raw)

    def test_send_raw_email_translates_clienterror_to_sessenderror(self) -> None:
        from botocore.exceptions import ClientError

        self.stub.next_exception = ClientError(
            {
                "Error": {"Code": "MessageRejected", "Message": "Email rejected"},
                "ResponseMetadata": {"RequestId": "req-9999"},
            },
            "SendRawEmail",
        )
        with self.assertRaises(SesSendError) as ctx:
            self.adapter.send_raw_email(
                aws_ses_profile=_profile(),
                destinations=["visitor@example.com"],
                raw_message_bytes=b"From: x\n\nbody",
            )
        self.assertEqual(ctx.exception.aws_error_code, "MessageRejected")
        self.assertEqual(ctx.exception.aws_request_id, "req-9999")
        self.assertEqual(ctx.exception.identity, "dylan@fruitfulnetworkdevelopment.com")

    def test_send_email_rejects_profile_missing_identity(self) -> None:
        with self.assertRaises(SesSendError):
            self.adapter.send_email(
                aws_ses_profile={"region": "us-east-1"},
                to=["x@example.com"],
                subject="x",
                body_text="x",
            )

    def test_send_raw_email_rejects_empty_destinations(self) -> None:
        with self.assertRaises(SesSendError):
            self.adapter.send_raw_email(
                aws_ses_profile=_profile(),
                destinations=[],
                raw_message_bytes=b"From: x\n\nbody",
            )

    def test_client_cache_is_region_keyed(self) -> None:
        # Pre-seed a distinct stub for a different region; confirm it is
        # selected when the profile specifies that region.
        eu_stub = _StubSesClient()
        self.adapter._cached_clients["ses@eu-west-1"] = eu_stub
        profile = _profile()
        profile["region"] = "eu-west-1"
        self.adapter.send_email(
            aws_ses_profile=profile, to=["x@example.com"], subject="x", body_text="x"
        )
        self.assertEqual(len(eu_stub.send_raw_email_calls), 1)
        self.assertEqual(len(self.stub.send_raw_email_calls), 0)


if __name__ == "__main__":
    unittest.main()
