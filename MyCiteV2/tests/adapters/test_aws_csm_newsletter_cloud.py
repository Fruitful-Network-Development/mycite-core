from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.event_transport.aws_csm_newsletter_cloud import (  # noqa: E402
    AwsEc2RoleNewsletterCloudAdapter,
)


class _FakeSesClient:
    def describe_active_receipt_rule_set(self) -> dict[str, object]:
        return {
            "Rules": [
                {
                    "Name": "portal-capture-trappfamilyfarm-com",
                    "Recipients": ["trappfamilyfarm.com"],
                    "Actions": [
                        {
                            "S3Action": {
                                "BucketName": "ses-inbound-fnd-mail",
                                "ObjectKeyPrefix": "inbound/trappfamilyfarm.com/",
                            }
                        },
                        {
                            "LambdaAction": {
                                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:newsletter-inbound-capture",
                            }
                        },
                    ],
                }
            ]
        }


class AwsCsmNewsletterCloudAdapterTests(unittest.TestCase):
    def test_receipt_rule_summary_matches_domain_level_recipient_rules(self) -> None:
        adapter = AwsEc2RoleNewsletterCloudAdapter()
        with patch.object(adapter, "_client", return_value=_FakeSesClient()):
            summary = adapter.receipt_rule_summary(
                domain="trappfamilyfarm.com",
                expected_recipient="mark@trappfamilyfarm.com",
                expected_lambda_name="newsletter-inbound-capture",
                region="us-east-1",
            )

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["expected_domain"], "trappfamilyfarm.com")
        self.assertEqual(len(summary["matching_rules"]), 1)
        rule = summary["matching_rules"][0]
        self.assertEqual(rule["recipient_match_kind"], "domain_recipient")
        self.assertEqual(rule["matched_recipient"], "trappfamilyfarm.com")
        self.assertEqual(rule["s3_bucket"], "ses-inbound-fnd-mail")
        self.assertEqual(rule["s3_prefix"], "inbound/trappfamilyfarm.com/")


if __name__ == "__main__":
    unittest.main()
