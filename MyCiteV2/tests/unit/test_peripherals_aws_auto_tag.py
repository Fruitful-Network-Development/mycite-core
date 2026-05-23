"""A8 — auto-tag-on-create kwarg passthrough on the three ensure_* methods.

Pins:
  * ensure_domain_identity tags the SES identity via ResourceGroupsTagging
    after verify_domain_identity (SES v1 doesn't accept Tags directly).
  * sync_domain_dns tags the Route53 hosted zone via change_tags_for_resource
    after the RRS sync (records aren't taggable).
  * ensure_domain_receipt_rule accepts the kwarg but currently no-ops
    (SES v1 receipt rules aren't directly taggable); surfaces the intent
    in the return value.
  * Tagging failures are opportunistic — they do NOT fail the ensure_*
    operation.
  * Default (no tags kwarg) is unchanged behavior — no tagging call made.
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


def _ses_stub_for_identity(already_verified: bool = False) -> MagicMock:
    stub = MagicMock()
    stub.get_identity_verification_attributes.return_value = {
        "VerificationAttributes": {
            "example.test": {
                "VerificationStatus": "Success" if already_verified else "Pending"
            }
        }
    }
    stub.get_identity_dkim_attributes.return_value = {
        "DkimAttributes": {
            "example.test": {"DkimTokens": ["tok1"], "DkimEnabled": True}
        }
    }
    return stub


def _ses_stub_for_receipt_rule() -> MagicMock:
    stub = MagicMock()
    stub.describe_active_receipt_rule_set.return_value = {"Rules": []}
    return stub


class EnsureDomainIdentityTagsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
        self.ses_stub = _ses_stub_for_identity(already_verified=False)
        self.sts_stub = MagicMock()
        self.sts_stub.get_caller_identity.return_value = {"Account": "065948377733"}
        self.rgt_stub = MagicMock()
        self.rgt_stub.tag_resources.return_value = {"FailedResourcesMap": {}}
        self.adapter._cached_clients["ses@us-east-1"] = self.ses_stub
        self.adapter._cached_clients["sts@us-east-1"] = self.sts_stub
        self.adapter._cached_clients["resourcegroupstaggingapi@us-east-1"] = self.rgt_stub

    def test_no_tags_kwarg_means_no_tagging_call(self) -> None:
        result = self.adapter.ensure_domain_identity("example.test")
        self.assertTrue(result["ok"])
        self.rgt_stub.tag_resources.assert_not_called()
        self.assertNotIn("tagged_arn", result)

    def test_tags_kwarg_applies_to_ses_identity_arn(self) -> None:
        result = self.adapter.ensure_domain_identity(
            "example.test",
            tags={"msn_id": "alpha-msn", "tenant": "alpha"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["tagged_arn"],
            "arn:aws:ses:us-east-1:065948377733:identity/example.test",
        )
        self.rgt_stub.tag_resources.assert_called_once()
        kwargs = self.rgt_stub.tag_resources.call_args.kwargs
        self.assertEqual(
            kwargs["ResourceARNList"],
            ["arn:aws:ses:us-east-1:065948377733:identity/example.test"],
        )
        self.assertEqual(kwargs["Tags"], {"msn_id": "alpha-msn", "tenant": "alpha"})

    def test_tagging_failure_does_not_fail_ensure(self) -> None:
        self.rgt_stub.tag_resources.side_effect = RuntimeError("aws is down")
        result = self.adapter.ensure_domain_identity(
            "example.test", tags={"msn_id": "alpha-msn"}
        )
        self.assertTrue(result["ok"])
        self.assertNotIn("tagged_arn", result)

    def test_missing_account_id_skips_tagging_gracefully(self) -> None:
        self.sts_stub.get_caller_identity.side_effect = RuntimeError("STS denied")
        self.adapter._cached_account_id = None  # reset
        result = self.adapter.ensure_domain_identity(
            "example.test", tags={"msn_id": "alpha-msn"}
        )
        self.assertTrue(result["ok"])
        self.rgt_stub.tag_resources.assert_not_called()


class SyncDomainDnsTagsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
        self.r53_stub = MagicMock()
        self.r53_stub.list_hosted_zones.return_value = {
            "HostedZones": [
                {"Name": "example.test.", "Id": "/hostedzone/Z123ABC"}
            ]
        }
        self.r53_stub.list_resource_record_sets.return_value = {
            "ResourceRecordSets": [
                # Pre-existing — no changes needed for the sync portion
                {"Name": "example.test.", "Type": "MX"},
                {"Name": "example.test.", "Type": "TXT"},
                {"Name": "_dmarc.example.test.", "Type": "TXT"},
            ]
        }
        self.ses_stub = MagicMock()
        self.ses_stub.get_identity_dkim_attributes.return_value = {
            "DkimAttributes": {"example.test": {"DkimTokens": []}}
        }
        self.adapter._cached_clients["route53@us-east-1"] = self.r53_stub
        self.adapter._cached_clients["ses@us-east-1"] = self.ses_stub

    def test_no_tags_kwarg_means_no_tagging_call(self) -> None:
        result = self.adapter.sync_domain_dns("example.test")
        self.assertTrue(result["ok"])
        self.r53_stub.change_tags_for_resource.assert_not_called()
        self.assertNotIn("tagged_zone", result)

    def test_tags_kwarg_applies_to_hosted_zone(self) -> None:
        result = self.adapter.sync_domain_dns(
            "example.test", tags={"msn_id": "alpha-msn", "tenant": "alpha"}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["zone_id"], "Z123ABC")
        self.assertTrue(result["tagged_zone"])
        self.r53_stub.change_tags_for_resource.assert_called_once()
        kwargs = self.r53_stub.change_tags_for_resource.call_args.kwargs
        self.assertEqual(kwargs["ResourceType"], "hostedzone")
        self.assertEqual(kwargs["ResourceId"], "Z123ABC")
        # AddTags must be the [{Key, Value}, ...] shape Route53 expects
        applied = {t["Key"]: t["Value"] for t in kwargs["AddTags"]}
        self.assertEqual(applied, {"msn_id": "alpha-msn", "tenant": "alpha"})

    def test_tag_failure_does_not_fail_dns_sync(self) -> None:
        self.r53_stub.change_tags_for_resource.side_effect = RuntimeError("denied")
        result = self.adapter.sync_domain_dns(
            "example.test", tags={"msn_id": "alpha-msn"}
        )
        self.assertTrue(result["ok"])
        self.assertNotIn("tagged_zone", result)


class EnsureDomainReceiptRuleTagsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
        self.ses_stub = _ses_stub_for_receipt_rule()
        self.lam_stub = MagicMock()
        self.adapter._cached_clients["ses@us-east-1"] = self.ses_stub
        self.adapter._cached_clients["lambda@us-east-1"] = self.lam_stub

    def test_no_tags_kwarg_means_no_intent_recorded(self) -> None:
        result = self.adapter.ensure_domain_receipt_rule("example.test")
        self.assertTrue(result["ok"])
        self.assertNotIn("tags_requested", result)
        self.assertNotIn("tags_applied", result)

    def test_tags_kwarg_recorded_but_noop_per_ses_v1(self) -> None:
        """SES v1 receipt rules are not directly taggable; document intent."""
        result = self.adapter.ensure_domain_receipt_rule(
            "example.test", tags={"msn_id": "alpha-msn", "tenant": "alpha"}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["tags_requested"], {"msn_id": "alpha-msn", "tenant": "alpha"})
        self.assertFalse(result["tags_applied"])
        self.assertIn("not directly taggable", result["tags_note"])


if __name__ == "__main__":
    unittest.main()
