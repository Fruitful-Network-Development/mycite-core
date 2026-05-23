"""C1 — custom MAIL FROM auto-bootstrap inside sync_domain_dns.

Pins:
  * When SES MAIL FROM differs from mail.<domain>, set_identity_mail_from_domain
    is called with BehaviorOnMXFailure=UseDefaultValue.
  * Idempotent: when SES already reports MailFromDomain == mail.<domain>,
    set_identity_mail_from_domain is NOT called again.
  * The mail.<domain> MX (feedback-smtp) + SPF TXT records are added to
    Route53 when absent.
  * A SES MAIL FROM API error does not fail the whole DNS sync.
"""

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


def _r53_stub(existing_rrs: list[dict] | None = None) -> MagicMock:
    stub = MagicMock()
    stub.list_hosted_zones.return_value = {
        "HostedZones": [{"Name": "example.test.", "Id": "/hostedzone/ZTEST"}]
    }
    stub.list_resource_record_sets.return_value = {
        "ResourceRecordSets": existing_rrs or []
    }
    return stub


def _ses_stub(*, dkim_tokens=None, mail_from="") -> MagicMock:
    stub = MagicMock()
    stub.get_identity_dkim_attributes.return_value = {
        "DkimAttributes": {
            "example.test": {"DkimTokens": dkim_tokens or [], "DkimEnabled": True}
        }
    }
    stub.get_identity_mail_from_domain_attributes.return_value = {
        "MailFromDomainAttributes": {
            "example.test": {"MailFromDomain": mail_from}
        }
    }
    return stub


class MailFromBootstrapTests(unittest.TestCase):
    def _adapter(self, r53, ses):
        adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
        adapter._cached_clients["route53@us-east-1"] = r53
        adapter._cached_clients["ses@us-east-1"] = ses
        return adapter

    def test_sets_mail_from_when_unconfigured(self) -> None:
        r53 = _r53_stub()
        ses = _ses_stub(mail_from="")  # not yet set
        adapter = self._adapter(r53, ses)
        result = adapter.sync_domain_dns("example.test")
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("mail_from_changed"))
        self.assertEqual(result.get("mail_from_domain"), "mail.example.test")
        ses.set_identity_mail_from_domain.assert_called_once()
        kwargs = ses.set_identity_mail_from_domain.call_args.kwargs
        self.assertEqual(kwargs["Identity"], "example.test")
        self.assertEqual(kwargs["MailFromDomain"], "mail.example.test")
        self.assertEqual(kwargs["BehaviorOnMXFailure"], "UseDefaultValue")

    def test_idempotent_when_mail_from_already_set(self) -> None:
        r53 = _r53_stub()
        ses = _ses_stub(mail_from="mail.example.test")  # already correct
        adapter = self._adapter(r53, ses)
        result = adapter.sync_domain_dns("example.test")
        self.assertTrue(result["ok"])
        self.assertNotIn("mail_from_changed", result)
        ses.set_identity_mail_from_domain.assert_not_called()

    def test_mail_from_mx_and_spf_records_added(self) -> None:
        r53 = _r53_stub()
        ses = _ses_stub(mail_from="")
        adapter = self._adapter(r53, ses)
        adapter.sync_domain_dns("example.test")
        # Inspect the change batch submitted to Route53.
        r53.change_resource_record_sets.assert_called_once()
        changes = r53.change_resource_record_sets.call_args.kwargs["ChangeBatch"]["Changes"]
        records = {
            (c["ResourceRecordSet"]["Name"], c["ResourceRecordSet"]["Type"]): c
            for c in changes
        }
        # mail.example.test MX → feedback-smtp
        self.assertIn(("mail.example.test.", "MX"), records)
        mx_val = records[("mail.example.test.", "MX")]["ResourceRecordSet"]["ResourceRecords"][0]["Value"]
        self.assertIn("feedback-smtp.us-east-1.amazonses.com", mx_val)
        # mail.example.test SPF TXT
        self.assertIn(("mail.example.test.", "TXT"), records)
        spf_val = records[("mail.example.test.", "TXT")]["ResourceRecordSet"]["ResourceRecords"][0]["Value"]
        self.assertIn("v=spf1 include:amazonses.com", spf_val)

    def test_mail_from_records_not_duplicated_when_present(self) -> None:
        # Pre-seed mail.example.test MX + TXT so they aren't re-added.
        existing = [
            {"Name": "mail.example.test.", "Type": "MX"},
            {"Name": "mail.example.test.", "Type": "TXT"},
            {"Name": "example.test.", "Type": "MX"},
            {"Name": "example.test.", "Type": "TXT"},
            {"Name": "_dmarc.example.test.", "Type": "TXT"},
        ]
        r53 = _r53_stub(existing)
        ses = _ses_stub(mail_from="mail.example.test")
        adapter = self._adapter(r53, ses)
        adapter.sync_domain_dns("example.test")
        # No change batch needed (everything present) → not called.
        r53.change_resource_record_sets.assert_not_called()

    def test_ses_mail_from_api_error_does_not_fail_sync(self) -> None:
        r53 = _r53_stub()
        ses = _ses_stub(mail_from="")
        ses.get_identity_mail_from_domain_attributes.side_effect = RuntimeError("throttle")
        adapter = self._adapter(r53, ses)
        result = adapter.sync_domain_dns("example.test")
        # DNS sync still succeeds; mail_from just didn't get set.
        self.assertTrue(result["ok"])
        self.assertNotIn("mail_from_changed", result)


if __name__ == "__main__":
    unittest.main()
