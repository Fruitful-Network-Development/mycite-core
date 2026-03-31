from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "aws_csm_inspect.py"
SPEC = importlib.util.spec_from_file_location("aws_csm_inspect", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AwsCsmInspectTests(unittest.TestCase):
    def test_secret_health_marks_placeholder_values_without_exposing_them(self) -> None:
        health = MODULE._smtp_secret_health_from_payload(
            "aws-cms/smtp/fnd",
            {
                "username": "REPLACE_WITH_SES_SMTP_USERNAME",
                "password": "REPLACE_WITH_REAL_SMTP_PASSWORD",
            },
        )

        self.assertEqual(health["secret_name"], "aws-cms/smtp/fnd")
        self.assertEqual(health["username_state"], "placeholder")
        self.assertEqual(health["password_state"], "placeholder")
        self.assertEqual(health["smtp_auth_state"], "not_attempted")
        self.assertFalse(bool(health["usable_for_handoff"]))

    def test_secret_health_marks_present_values_as_candidates_for_auth(self) -> None:
        health = MODULE._smtp_secret_health_from_payload(
            "aws-cms/smtp/fnd",
            {
                "username": "AKIAIOSFODNN7ABCD123",
                "password": "wJalrXUtnFEMI/K7MDENG/bPxRfiCY123456KEY",
            },
        )

        self.assertEqual(health["username_state"], "present")
        self.assertEqual(health["password_state"], "present")
        self.assertEqual(health["smtp_auth_state"], "not_attempted")

    def test_candidate_addresses_stay_on_domain_and_include_legacy_mail_from_alias(self) -> None:
        profile = {
            "identity": {
                "domain": "fruitfulnetworkdevelopment.com",
                "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                "single_user_email": "dylancarsonmontgomery@gmail.com",
            },
            "smtp": {
                "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
            },
        }
        domain_identity = {
            "MailFromAttributes": {
                "MailFromDomain": "dcmontgomery.fruitfulnetworkdevelopment.com",
            }
        }

        addresses = MODULE._candidate_addresses(profile, domain_identity)

        self.assertEqual(addresses[0], "dylan@fruitfulnetworkdevelopment.com")
        self.assertIn("dcmontgomery@fruitfulnetworkdevelopment.com", addresses)
        self.assertIn("marilyn@fruitfulnetworkdevelopment.com", addresses)
        self.assertNotIn("dylancarsonmontgomery@gmail.com", addresses)

    def test_classification_flags_conflicting_fnd_legacy_resources(self) -> None:
        profile = {
            "identity": {
                "domain": "fruitfulnetworkdevelopment.com",
                "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
            },
            "smtp": {
                "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
            },
        }
        entries = MODULE._build_classification(
            tenant="fnd",
            profile=profile,
            domain_identity={
                "VerificationStatus": "SUCCESS",
                "VerifiedForSendingStatus": True,
                "MailFromAttributes": {
                    "MailFromDomain": "dcmontgomery.fruitfulnetworkdevelopment.com",
                },
            },
            hosted_zone={"Id": "/hostedzone/Z123"},
            mail_records=[
                {
                    "Name": "_dmarc.fruitfulnetworkdevelopment.com.",
                    "Type": "TXT",
                    "ResourceRecords": [
                        {
                            "Value": '"v=DMARC1; p=none; rua=mailto:dcmontgomery@fruitfulnetworkdevelopment.com"',
                        }
                    ],
                },
                {
                    "Name": "dcmontgomery.fruitfulnetworkdevelopment.com.",
                    "Type": "TXT",
                    "ResourceRecords": [
                        {
                            "Value": '"v=spf1 include:amazonses.com ~all"',
                        }
                    ],
                },
                {
                    "Name": "qctu6aiwav2j5l3bbntgucvtzu5z52br._domainkey.fruitfulnetworkdevelopment.com.",
                    "Type": "CNAME",
                    "ResourceRecords": [
                        {
                            "Value": "qctu6aiwav2j5l3bbntgucvtzu5z52br.dkim.amazonses.com",
                        }
                    ],
                },
            ],
            secrets=[{"Name": "aws-cms/smtp/fnd"}],
            smtp_secret_health={
                "secret_name": "aws-cms/smtp/fnd",
                "username_state": "placeholder",
                "password_state": "placeholder",
                "smtp_auth_state": "placeholder_detected",
                "usable_for_handoff": False,
            },
            address_identities={},
            active_receipt_rule_set={"Metadata": {"Name": "fnd-inbound-rules"}, "Rules": [{}]},
            referenced_buckets={"ses-inbound-fnd-mail": {"prefixes": ["inbound/"], "latest_object": "2026-03-29T10:23:50+00:00"}},
            referenced_lambdas={"ses-forwarder": {"arn": "arn:aws:lambda:us-east-1:123456789012:function:ses-forwarder"}},
            local_references={"dylan@fruitfulnetworkdevelopment.com": ["/tmp/aws-csm.fnd.json:10"]},
        )
        by_item = {entry["item"]: entry for entry in entries}

        self.assertEqual(
            by_item["SES domain identity fruitfulnetworkdevelopment.com"]["classification"],
            MODULE.CLASS_CURRENT,
        )
        self.assertEqual(
            by_item["SMTP secret payload aws-cms/smtp/fnd"]["classification"],
            MODULE.CLASS_REQUIRED,
        )
        self.assertEqual(
            by_item["Custom MAIL FROM dcmontgomery.fruitfulnetworkdevelopment.com"]["classification"],
            MODULE.CLASS_CONFLICTING,
        )
        self.assertEqual(
            by_item["Active receipt rule set fnd-inbound-rules"]["classification"],
            MODULE.CLASS_CONFLICTING,
        )
        self.assertEqual(
            by_item["Canonical sender candidate dylan@fruitfulnetworkdevelopment.com"]["classification"],
            MODULE.CLASS_CURRENT,
        )


if __name__ == "__main__":
    unittest.main()
