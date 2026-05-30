"""Tests for SES SMTP credential derivation.

Cross-checks the production implementation against a separately-written
in-test reference implementation that mirrors Amazon's published Python
sample (`aws_smtp_credentials_generator.py`, linked from the SES
Developer Guide). If either ever drifts from the spec, the equality
assertion fails on multiple test vectors.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.peripherals.aws.smtp_creds import (
    derive_smtp_password,
    scoped_send_policy_document,
    slugify_iam_user_name,
    smtp_host_for_region,
)


def _aws_reference_implementation(secret_access_key: str, region: str) -> str:
    """Mirror of the AWS sample at SES Developer Guide §"Converting
    Existing AWS Credentials into SES SMTP Credentials". Independent of
    the production code, so the cross-check assertion catches drift in
    either direction."""
    DATE = "11111111"
    SERVICE = "ses"
    MESSAGE = "SendRawEmail"
    TERMINAL = "aws4_request"
    VERSION = 0x04

    def sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    signature = sign(("AWS4" + secret_access_key).encode("utf-8"), DATE)
    signature = sign(signature, region)
    signature = sign(signature, SERVICE)
    signature = sign(signature, TERMINAL)
    signature = sign(signature, MESSAGE)
    return base64.b64encode(bytes([VERSION]) + signature).decode("utf-8")


class DeriveSmtpPasswordTests(unittest.TestCase):
    def test_matches_reference_on_multiple_vectors(self) -> None:
        # Two test vectors crossed with two SES regions — 4 cases total.
        # Both implementations must agree on every cell.
        secrets = [
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "test-secret-key-1234567890+/=ABCxyz",
        ]
        regions = ["us-east-1", "eu-west-1"]
        for secret in secrets:
            for region in regions:
                expected = _aws_reference_implementation(secret, region)
                actual = derive_smtp_password(secret, region)
                self.assertEqual(actual, expected, f"drift on (secret_prefix={secret[:6]}…, region={region})")

    def test_different_region_yields_different_password(self) -> None:
        secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        self.assertNotEqual(
            derive_smtp_password(secret, "us-east-1"),
            derive_smtp_password(secret, "us-west-2"),
        )

    def test_version_byte_prefixes_signature(self) -> None:
        # base64 of (0x04 + 32-byte HMAC) is 44 chars; the first decoded
        # byte must be 0x04 (SES SMTP credential format v4).
        import base64
        password = derive_smtp_password("any-secret", "us-east-1")
        decoded = base64.b64decode(password)
        self.assertEqual(len(decoded), 33)
        self.assertEqual(decoded[0], 0x04)

    def test_rejects_empty_inputs(self) -> None:
        with self.assertRaises(ValueError):
            derive_smtp_password("", "us-east-1")
        with self.assertRaises(ValueError):
            derive_smtp_password("secret", "")


class SmtpHostTests(unittest.TestCase):
    def test_region_to_host(self) -> None:
        self.assertEqual(smtp_host_for_region("us-east-1"), "email-smtp.us-east-1.amazonaws.com")
        self.assertEqual(smtp_host_for_region("eu-west-1"), "email-smtp.eu-west-1.amazonaws.com")

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            smtp_host_for_region("")


class ScopedPolicyTests(unittest.TestCase):
    def test_policy_pins_from_address(self) -> None:
        doc = scoped_send_policy_document("marilyn@cvccboard.org")
        statement = doc["Statement"][0]
        self.assertEqual(statement["Effect"], "Allow")
        self.assertIn("ses:SendRawEmail", statement["Action"])
        self.assertIn("ses:SendEmail", statement["Action"])
        self.assertEqual(
            statement["Condition"]["StringEquals"]["ses:FromAddress"],
            "marilyn@cvccboard.org",
        )

    def test_policy_rejects_non_email(self) -> None:
        with self.assertRaises(ValueError):
            scoped_send_policy_document("not-an-email")


class IamUserNameTests(unittest.TestCase):
    def test_form(self) -> None:
        self.assertEqual(
            slugify_iam_user_name("marilyn@cvccboard.org"),
            "ses-smtp-cvccboard-org-marilyn",
        )
        self.assertEqual(
            slugify_iam_user_name("first.last@fruitfulnetworkdevelopment.com"),
            "ses-smtp-fruitfulnetworkdevelopment-com-first-last",
        )

    def test_rejects_non_email(self) -> None:
        with self.assertRaises(ValueError):
            slugify_iam_user_name("nope")


if __name__ == "__main__":
    unittest.main()
