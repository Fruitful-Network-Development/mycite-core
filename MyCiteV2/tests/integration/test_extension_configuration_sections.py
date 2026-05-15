"""Phase 10 integration tests for the reflective/operational split.

Each operational extension (email, newsletter, paypal) now exposes a
"configuration" key that mirrors the relevant grantee JSON sub-config
with an edit_link back to ext_grantee_profile. Analytics has no
operator-editable configuration but surfaces a data_source hint.

Tests:
  - PayPal extension exposes paypal configuration with masked client_secret
  - Email extension exposes aws_ses configuration with masked smtp_password
  - Newsletter extension exposes newsletter configuration
  - Analytics extension exposes data_source with kind populated
  - edit_link.href points at ext_grantee_profile with the right focus_field
  - Empty grantee sub-config still renders the section with empty values
  - Secret-masking helper redacts long secrets, masks short ones entirely
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    _build_analytics_extension_payload,
    _build_email_extension_payload,
    _build_newsletter_extension_payload,
    _build_paypal_extension_payload,
)
from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import (
    _grantee_edit_link,
    _mask_secret,
)


def _full_grantee() -> dict:
    return {
        "msn_id": "g1",
        "label": "Test Grantee",
        "domains": ["example.org"],
        "users": ["alice@example.org"],
        "paypal": {
            "webhook_url": "https://example.org/hook",
            "client_id": "ABC123",
            "client_secret": "verylongsecretvalue",
            "environment": "live",
        },
        "aws_ses": {
            "region": "us-east-1",
            "identity": "noreply@example.org",
            "smtp_username": "AKIATESTUSER",
            "smtp_password": "smtp-password-12345678",
        },
        "newsletter": {
            "selected_sender_address": "hello@example.org",
            "sender_display_name": "Example",
            "reply_to": "alice@example.org",
        },
    }


class SecretMaskingTests(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(_mask_secret(""), "")
        self.assertEqual(_mask_secret(None), "")

    def test_short_secret_fully_masked(self) -> None:
        masked = _mask_secret("abc")
        self.assertEqual(masked, "•••")

    def test_long_secret_keeps_last_four(self) -> None:
        masked = _mask_secret("abcdef123456")
        self.assertTrue(masked.endswith("3456"))
        self.assertEqual(len(masked), len("abcdef123456"))


class GranteeEditLinkTests(unittest.TestCase):
    def test_link_points_at_utilities_tool_exposure_with_focus_field(self) -> None:
        link = _grantee_edit_link("paypal")
        self.assertEqual(link["focus_field"], "paypal")
        self.assertIn("/portal/utilities/tool-exposure", link["href"])
        self.assertIn("focus_field=paypal", link["href"])
        self.assertIn("utilities_extension=ext_grantee_profile", link["href"])


class PaypalExtensionConfigurationTests(unittest.TestCase):
    def test_configuration_section_present_with_masked_secret(self) -> None:
        out = _build_paypal_extension_payload(_full_grantee(), "example.org", None)
        cfg = out["configuration"]
        items = {item["label"]: item["value"] for item in cfg["items"]}
        self.assertEqual(items["Webhook URL"], "https://example.org/hook")
        self.assertEqual(items["Environment"], "live")
        self.assertEqual(items["Client ID"], "ABC123")
        # Secret is masked but ends with the last 4 chars.
        self.assertTrue(items["Client secret"].endswith("alue"))
        self.assertNotIn("verylongsecret", items["Client secret"])
        self.assertEqual(cfg["edit_link"]["focus_field"], "paypal")

    def test_orders_dashboard_still_returned_alongside_configuration(self) -> None:
        out = _build_paypal_extension_payload(_full_grantee(), "example.org", None)
        # Operational reality (orders, webhook_url top-level) remains.
        self.assertIn("orders", out)
        self.assertIn("webhook_url", out)
        # And the new configuration sits alongside, not in place of, it.
        self.assertIn("configuration", out)


class EmailExtensionConfigurationTests(unittest.TestCase):
    def test_aws_ses_configuration_section_present_with_masked_password(self) -> None:
        out = _build_email_extension_payload(_full_grantee(), "example.org", None)
        cfg = out["configuration"]
        items = {item["label"]: item["value"] for item in cfg["items"]}
        self.assertEqual(items["Region"], "us-east-1")
        self.assertEqual(items["Identity"], "noreply@example.org")
        self.assertEqual(items["SMTP username"], "AKIATESTUSER")
        self.assertTrue(items["SMTP password"].endswith("5678"))
        self.assertNotIn("smtp-password", items["SMTP password"])
        self.assertEqual(cfg["edit_link"]["focus_field"], "aws_ses")

    def test_configuration_present_on_no_domain_path(self) -> None:
        # When private_dir is None the function returns early; configuration
        # must still surface so operators can see + edit credentials.
        out = _build_email_extension_payload(_full_grantee(), "", None)
        self.assertIn("configuration", out)
        self.assertEqual(out["configuration"]["edit_link"]["focus_field"], "aws_ses")


class NewsletterExtensionConfigurationTests(unittest.TestCase):
    def test_newsletter_configuration_section_present(self) -> None:
        out = _build_newsletter_extension_payload(_full_grantee(), "example.org", None)
        cfg = out["configuration"]
        items = {item["label"]: item["value"] for item in cfg["items"]}
        self.assertEqual(items["Sender address"], "hello@example.org")
        self.assertEqual(items["Display name"], "Example")
        self.assertEqual(items["Reply-to"], "alice@example.org")
        self.assertEqual(cfg["edit_link"]["focus_field"], "newsletter")

    def test_empty_subconfig_renders_empty_values(self) -> None:
        grantee = {"msn_id": "g2", "label": "G"}  # No newsletter sub-config.
        out = _build_newsletter_extension_payload(grantee, "example.org", None)
        cfg = out["configuration"]
        values = [item["value"] for item in cfg["items"]]
        # All empty, but the section is still rendered with the edit link.
        self.assertEqual(values, ["", "", ""])
        self.assertEqual(cfg["edit_link"]["focus_field"], "newsletter")


class AnalyticsDataSourceTests(unittest.TestCase):
    def test_data_source_kind_unset_when_no_domain(self) -> None:
        out = _build_analytics_extension_payload("", None)
        ds = out["data_source"]
        self.assertEqual(ds["kind"], "")
        self.assertEqual(ds["label"], "Data source")

    def test_data_source_kind_pending_when_summary_datum_absent(self) -> None:
        # Phase 14c: the in-request 3-month NDJSON fallback is removed. When
        # the MOS summary datum is absent the renderer returns a `pending`
        # data_source + a `notice` pointing operators at the refresh job;
        # the events_dir is still echoed so they know where the source
        # files would live.
        out = _build_analytics_extension_payload("example.org", "/nonexistent")
        ds = out["data_source"]
        self.assertEqual(ds["kind"], "pending")
        self.assertIn("example.org", ds["events_dir"])
        self.assertIn("notice", out)
        self.assertIn("sync", out["notice"].lower())


if __name__ == "__main__":
    unittest.main()
