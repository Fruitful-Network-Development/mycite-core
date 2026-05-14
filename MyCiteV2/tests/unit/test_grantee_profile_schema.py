"""Unit tests for GranteeProfile + sub-configs — Phase 8 of
TASK-PORTAL-SIMPLIFICATION-2026-05-14.

Pins the grantee_profile_contract.md schema invariants:
  - msn_id is required
  - schema field defaults to mycite.v2.grantee.profile.v1
  - PaypalConfig.environment ∈ {sandbox, live}
  - URL fields require http(s) prefix
  - email-shaped fields require basic local@host.tld
  - sub-configs are independent — any combination may be None
  - from_dict / to_dict round-trip equality
  - load_grantee_profile + save_grantee_profile atomicity
  - schema mismatch on load raises ValueError
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.grantee import (
    AwsSesConfig,
    GRANTEE_PROFILE_SCHEMA,
    GranteeProfile,
    NewsletterConfig,
    PaypalConfig,
    load_grantee_profile,
    save_grantee_profile,
)


def _legacy_payload() -> dict:
    return {
        "schema": GRANTEE_PROFILE_SCHEMA,
        "msn_id": "3-2-3-17-77-1-6-4-1-4",
        "label": "Fruitful Network Development",
        "short_name": "FND",
        "domains": ["fruitfulnetworkdevelopment.com"],
        "users": ["alice@example.org"],
    }


class GranteeProfileSchemaTests(unittest.TestCase):
    def test_schema_constant_is_canonical(self) -> None:
        self.assertEqual(GRANTEE_PROFILE_SCHEMA, "mycite.v2.grantee.profile.v1")

    def test_legacy_payload_loads_without_subconfigs(self) -> None:
        profile = GranteeProfile.from_dict(_legacy_payload())
        self.assertEqual(profile.msn_id, "3-2-3-17-77-1-6-4-1-4")
        self.assertEqual(profile.label, "Fruitful Network Development")
        self.assertEqual(profile.domains, ("fruitfulnetworkdevelopment.com",))
        self.assertIsNone(profile.paypal)
        self.assertIsNone(profile.aws_ses)
        self.assertIsNone(profile.newsletter)

    def test_msn_id_required(self) -> None:
        with self.assertRaises(ValueError):
            GranteeProfile.from_dict({"schema": GRANTEE_PROFILE_SCHEMA, "msn_id": ""})

    def test_schema_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError) as cm:
            GranteeProfile.from_dict({"schema": "wrong.v1", "msn_id": "x"})
        self.assertIn("schema", str(cm.exception))

    def test_to_dict_omits_none_subconfigs_for_legacy_compat(self) -> None:
        # Round-trip preserves byte-equivalence for legacy grantee files.
        profile = GranteeProfile.from_dict(_legacy_payload())
        out = profile.to_dict()
        self.assertNotIn("paypal", out)
        self.assertNotIn("aws_ses", out)
        self.assertNotIn("newsletter", out)

    def test_full_round_trip_with_subconfigs(self) -> None:
        original = GranteeProfile(
            msn_id="g-1",
            label="Grantee 1",
            short_name="G1",
            domains=("a.org", "b.org"),
            users=("alice@example.org",),
            paypal=PaypalConfig(
                webhook_url="https://a.org/__fnd/paypal/webhook",
                client_id="CID",
                client_secret="SEC",
                environment="live",
            ),
            aws_ses=AwsSesConfig(
                region="us-east-1",
                identity="noreply@a.org",
                smtp_username="AKIA",
                smtp_password="pw",
            ),
            newsletter=NewsletterConfig(
                selected_sender_address="hello@a.org",
                sender_display_name="A",
                reply_to="alice@example.org",
            ),
        )
        restored = GranteeProfile.from_dict(original.to_dict())
        self.assertEqual(restored, original)


class PaypalConfigTests(unittest.TestCase):
    def test_environment_lowercased_and_validated(self) -> None:
        cfg = PaypalConfig(environment="SANDBOX")
        self.assertEqual(cfg.environment, "sandbox")
        with self.assertRaises(ValueError):
            PaypalConfig(environment="staging")

    def test_webhook_url_must_be_http_or_https(self) -> None:
        PaypalConfig(webhook_url="https://example.org/x")  # ok
        PaypalConfig(webhook_url="http://example.org/x")  # ok
        with self.assertRaises(ValueError):
            PaypalConfig(webhook_url="example.org/x")
        # Empty is allowed (means "no webhook configured").
        PaypalConfig(webhook_url="")


class AwsSesConfigTests(unittest.TestCase):
    def test_identity_email_validated(self) -> None:
        AwsSesConfig(identity="noreply@example.org")  # ok
        AwsSesConfig(identity="")  # empty allowed
        with self.assertRaises(ValueError):
            AwsSesConfig(identity="not-an-email")


class NewsletterConfigTests(unittest.TestCase):
    def test_sender_and_reply_to_validated(self) -> None:
        NewsletterConfig(
            selected_sender_address="a@b.org",
            sender_display_name="Anything",
            reply_to="c@d.org",
        )
        with self.assertRaises(ValueError):
            NewsletterConfig(selected_sender_address="bad")
        with self.assertRaises(ValueError):
            NewsletterConfig(reply_to="also-bad")


class LoadSaveTests(unittest.TestCase):
    def test_load_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_grantee_profile("/nonexistent/grantee.x.json")

    def test_load_malformed_json_raises_value_error(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fp:
            fp.write("{ not valid json")
            tmp = Path(fp.name)
        try:
            with self.assertRaises(ValueError):
                load_grantee_profile(tmp)
        finally:
            tmp.unlink()

    def test_save_then_load_round_trip(self) -> None:
        original = GranteeProfile(
            msn_id="round-trip",
            label="RT",
            domains=("rt.org",),
            paypal=PaypalConfig(webhook_url="https://rt.org/x"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "grantee.test.json"
            save_grantee_profile(out, original)
            self.assertTrue(out.exists())
            loaded = load_grantee_profile(out)
            self.assertEqual(loaded, original)
            # No orphan temp files left behind in the parent directory.
            siblings = list(Path(tmp).glob(".grantee_*.tmp"))
            self.assertEqual(siblings, [])

    def test_save_refuses_overwrite_when_disallowed(self) -> None:
        profile = GranteeProfile(msn_id="overwrite-test")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "grantee.test.json"
            save_grantee_profile(out, profile)
            with self.assertRaises(FileExistsError):
                save_grantee_profile(out, profile, allow_overwrite=False)

    def test_save_creates_parent_directories(self) -> None:
        profile = GranteeProfile(msn_id="nested")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "deep" / "nested" / "dir" / "grantee.test.json"
            save_grantee_profile(out, profile)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
