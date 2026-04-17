from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.event_transport.aws_csm_onboarding_cloud import (
    AwsEc2RoleOnboardingCloudAdapter,
)


def _profile() -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.tff.mark",
            "tenant_id": "tff",
            "domain": "trappfamilyfarm.com",
            "region": "us-east-1",
            "mailbox_local_part": "mark",
            "send_as_email": "mark@trappfamilyfarm.com",
            "operator_inbox_target": "mark@trappfamilyfarm.com",
        },
        "smtp": {
            "credentials_secret_name": "aws-cms/smtp/tff.mark",
            "credentials_secret_state": "missing",
            "send_as_email": "mark@trappfamilyfarm.com",
        },
        "verification": {"status": "pending", "portal_state": "pending"},
        "provider": {"gmail_send_as_status": "pending"},
        "workflow": {"initiated": True},
        "inbound": {},
    }


class _FakeSecretsManagerClient:
    class exceptions:
        class ResourceNotFoundException(Exception):
            pass

    def __init__(self) -> None:
        self.secrets: dict[str, str] = {}

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
        if SecretId not in self.secrets:
            raise self.exceptions.ResourceNotFoundException()
        return {"SecretString": self.secrets[SecretId]}

    def update_secret(self, *, SecretId: str, SecretString: str, Description: str) -> dict[str, str]:
        _ = Description
        if SecretId not in self.secrets:
            raise self.exceptions.ResourceNotFoundException()
        self.secrets[SecretId] = SecretString
        return {"ARN": f"arn:aws:secretsmanager:us-east-1:123456789012:secret:{SecretId}"}

    def create_secret(self, *, Name: str, SecretString: str, Description: str) -> dict[str, str]:
        _ = Description
        self.secrets[Name] = SecretString
        return {"ARN": f"arn:aws:secretsmanager:us-east-1:123456789012:secret:{Name}"}


class _FakeIamClient:
    def list_access_keys(self, *, UserName: str) -> dict[str, object]:
        _ = UserName
        return {"AccessKeyMetadata": []}

    def create_access_key(self, *, UserName: str) -> dict[str, object]:
        _ = UserName
        return {
            "AccessKey": {
                "AccessKeyId": "AKIAEXAMPLEKEY",
                "SecretAccessKey": "secret-example-key",
            }
        }


class _FakeSesV2Client:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    def get_email_identity(self, *, EmailIdentity: str) -> dict[str, object]:
        _ = EmailIdentity
        return {
            "VerificationStatus": "SUCCESS",
            "VerifiedForSendingStatus": True,
        }

    def send_email(
        self,
        *,
        FromEmailAddress: str,
        Destination: dict[str, object],
        Content: dict[str, object],
    ) -> dict[str, object]:
        self.sent_messages.append(
            {
                "from": FromEmailAddress,
                "destination": Destination,
                "content": Content,
            }
        )
        return {"MessageId": "ses-message-001"}


class AwsCsmOnboardingCloudAdapterTests(unittest.TestCase):
    def test_stage_smtp_credentials_materializes_secret_backed_readiness(self) -> None:
        with TemporaryDirectory() as temp_dir:
            secrets = _FakeSecretsManagerClient()
            adapter = AwsEc2RoleOnboardingCloudAdapter(private_dir=temp_dir, tenant_id="tff")

            def fake_client(service_name: str, *, region: str | None = None) -> object:
                _ = region
                if service_name == "secretsmanager":
                    return secrets
                if service_name == "iam":
                    return _FakeIamClient()
                if service_name == "sesv2":
                    return _FakeSesV2Client()
                raise AssertionError(f"unexpected service {service_name}")

            with patch.object(adapter, "_client", side_effect=fake_client):
                patch_payload = adapter.supplemental_profile_patch("stage_smtp_credentials", _profile())

            self.assertTrue(patch_payload["smtp"]["handoff_ready"])
            self.assertEqual(patch_payload["smtp"]["credentials_secret_state"], "configured")
            self.assertEqual(patch_payload["provider"]["aws_ses_identity_status"], "verified")
            secret_string = secrets.secrets["aws-cms/smtp/tff.mark"]
            stored = json.loads(secret_string)
            self.assertEqual(stored["username"], "AKIAEXAMPLEKEY")
            self.assertTrue(stored["password"])

    def test_describe_profile_readiness_reports_receipt_rule_and_capture_evidence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = AwsEc2RoleOnboardingCloudAdapter(private_dir=temp_dir, tenant_id="tff")
            profile = _profile()
            profile["smtp"] = {
                "credentials_secret_name": "aws-cms/smtp/tff.mark",
                "credentials_secret_state": "configured",
                "send_as_email": "mark@trappfamilyfarm.com",
                "username": "SMTPUSER",
            }
            profile["verification"] = {
                "status": "pending",
                "portal_state": "pending",
                "latest_message_reference": "s3://ses-bucket/inbound/message-1",
            }
            profile["inbound"] = {
                "latest_message_s3_uri": "s3://ses-bucket/inbound/message-1",
                "latest_message_subject": "Gmail Confirmation - Send Mail as mark@trappfamilyfarm.com",
                "latest_message_has_verification_link": True,
                "portal_native_display_ready": False,
            }

            with patch.object(
                adapter,
                "_smtp_secret_material",
                return_value={
                    "state": "configured",
                    "secret_name": "aws-cms/smtp/tff.mark",
                    "username": "SMTPUSER",
                    "persisted_username": "SMTPUSER",
                    "password": "SMTPPASS",
                    "smtp_host": "email-smtp.us-east-1.amazonaws.com",
                    "smtp_port": "587",
                    "message": "",
                },
            ), patch.object(
                adapter,
                "_ses_identity_summary",
                return_value={"aws_ses_identity_status": "verified", "message": ""},
            ), patch.object(
                adapter,
                "receipt_rule_summary",
                return_value={"status": "ok", "matching_rules": [{"rule_name": "capture-mail"}]},
            ), patch.object(
                adapter,
                "lambda_health_summary",
                return_value={"status": "active", "function_arn": "arn:aws:lambda:us-east-1:123:function:newsletter-inbound-capture"},
            ), patch.object(
                adapter,
                "read_s3_bytes",
                return_value=(
                    "From: gmail-noreply@google.com\r\n"
                    "To: mark@trappfamilyfarm.com\r\n"
                    "Subject: Gmail Confirmation - Send Mail as mark@trappfamilyfarm.com\r\n"
                    "\r\n"
                    "Click https://mail.google.com/mail/u/0/?ui=2&ik=verify to confirm.\r\n"
                ).encode("utf-8"),
            ):
                readiness = adapter.describe_profile_readiness(profile)

            self.assertEqual(readiness["smtp"]["status"], "ready")
            self.assertEqual(readiness["provider"]["status"], "ready")
            self.assertEqual(readiness["inbound"]["status"], "captured")
            self.assertTrue(readiness["confirmation"]["can_confirm_verified"])

    def test_confirmation_stays_fail_closed_without_accessible_capture_evidence(self) -> None:
        adapter = AwsEc2RoleOnboardingCloudAdapter(tenant_id="tff")
        profile = _profile()
        profile["smtp"]["credentials_secret_state"] = "configured"
        profile["inbound"] = {
            "latest_message_s3_uri": "s3://ses-bucket/inbound/message-1",
            "latest_message_has_verification_link": True,
        }

        with patch.object(
            adapter,
            "_smtp_secret_material",
            return_value={
                "state": "configured",
                "secret_name": "aws-cms/smtp/tff.mark",
                "username": "SMTPUSER",
                "persisted_username": "SMTPUSER",
                "password": "SMTPPASS",
                "smtp_host": "email-smtp.us-east-1.amazonaws.com",
                "smtp_port": "587",
                "message": "",
            },
        ), patch.object(
            adapter,
            "_ses_identity_summary",
            return_value={"aws_ses_identity_status": "verified", "message": ""},
        ), patch.object(
            adapter,
            "receipt_rule_summary",
            return_value={"status": "ok"},
        ), patch.object(
            adapter,
            "lambda_health_summary",
            return_value={"status": "active"},
        ), patch.object(
            adapter,
            "read_s3_bytes",
            side_effect=ValueError("missing object"),
        ):
            self.assertFalse(adapter.gmail_confirmation_evidence_satisfied(profile))

    def test_read_handoff_secret_returns_ephemeral_material_without_persistence(self) -> None:
        adapter = AwsEc2RoleOnboardingCloudAdapter(tenant_id="tff")
        with patch.object(
            adapter,
            "_smtp_secret_material",
            return_value={
                "state": "configured",
                "secret_name": "aws-cms/smtp/tff.mark",
                "username": "SMTPUSER",
                "persisted_username": "SMTPUSER",
                "password": "SMTPPASS",
                "smtp_host": "email-smtp.us-east-1.amazonaws.com",
                "smtp_port": "587",
                "message": "",
            },
        ):
            revealed = adapter.read_handoff_secret(_profile())

        self.assertEqual(revealed["send_as_email"], "mark@trappfamilyfarm.com")
        self.assertEqual(revealed["username"], "SMTPUSER")
        self.assertEqual(revealed["password"], "SMTPPASS")
        self.assertEqual(revealed["secret_name"], "aws-cms/smtp/tff.mark")

    def test_describe_profile_readiness_discovers_capture_from_receipt_rule_backed_s3(self) -> None:
        adapter = AwsEc2RoleOnboardingCloudAdapter(tenant_id="tff")
        profile = _profile()
        profile["smtp"]["credentials_secret_state"] = "configured"
        raw_confirmation = (
            "From: gmail-noreply@google.com\r\n"
            "To: mark@trappfamilyfarm.com\r\n"
            "Subject: Gmail Confirmation - Send Mail as mark@trappfamilyfarm.com\r\n"
            "\r\n"
            "Click https://mail.google.com/mail/u/0/?ui=2&ik=verify to confirm.\r\n"
        ).encode("utf-8")

        with patch.object(
            adapter,
            "_smtp_secret_material",
            return_value={
                "state": "configured",
                "secret_name": "aws-cms/smtp/tff.mark",
                "username": "SMTPUSER",
                "persisted_username": "SMTPUSER",
                "password": "SMTPPASS",
                "smtp_host": "email-smtp.us-east-1.amazonaws.com",
                "smtp_port": "587",
                "message": "",
            },
        ), patch.object(
            adapter,
            "_ses_identity_summary",
            return_value={"aws_ses_identity_status": "verified", "message": ""},
        ), patch.object(
            adapter,
            "receipt_rule_summary",
            return_value={
                "status": "ok",
                "matching_rules": [
                    {
                        "rule_name": "portal-capture-trappfamilyfarm-com",
                        "recipient_match": True,
                        "recipient_match_kind": "domain_recipient",
                        "matched_recipient": "trappfamilyfarm.com",
                        "s3_action_present": True,
                        "lambda_action_present": True,
                        "s3_bucket": "ses-inbound-fnd-mail",
                        "s3_prefix": "inbound/trappfamilyfarm.com/",
                    }
                ],
            },
        ), patch.object(
            adapter,
            "lambda_health_summary",
            return_value={"status": "active"},
        ), patch.object(
            adapter,
            "list_s3_objects",
            return_value=[
                {
                    "bucket": "ses-inbound-fnd-mail",
                    "key": "inbound/trappfamilyfarm.com/msg-1",
                    "s3_uri": "s3://ses-inbound-fnd-mail/inbound/trappfamilyfarm.com/msg-1",
                    "last_modified": "2026-04-17T06:00:00+00:00",
                }
            ],
        ), patch.object(
            adapter,
            "read_s3_bytes",
            return_value=raw_confirmation,
        ):
            readiness = adapter.describe_profile_readiness(profile)

        capture = readiness["inbound"]["latest_capture"]
        self.assertEqual(readiness["inbound"]["status"], "captured")
        self.assertTrue(readiness["confirmation"]["can_confirm_verified"])
        self.assertEqual(capture["s3_uri"], "s3://ses-inbound-fnd-mail/inbound/trappfamilyfarm.com/msg-1")
        self.assertEqual(capture["recipient"], "mark@trappfamilyfarm.com")
        self.assertTrue(capture["has_verification_link"])
        self.assertIn("https://mail.google.com/mail/u/0/?ui=2&ik=verify", capture["link"])

    def test_send_handoff_email_omits_password_from_message_body(self) -> None:
        with TemporaryDirectory() as temp_dir:
            sesv2 = _FakeSesV2Client()
            adapter = AwsEc2RoleOnboardingCloudAdapter(private_dir=temp_dir, tenant_id="tff")

            def fake_client(service_name: str, *, region: str | None = None) -> object:
                _ = region
                if service_name == "sesv2":
                    return sesv2
                raise AssertionError(f"unexpected service {service_name}")

            with patch.object(
                adapter,
                "_smtp_secret_material",
                return_value={
                    "state": "configured",
                    "secret_name": "aws-cms/smtp/tff.mark",
                    "username": "SMTPUSER",
                    "persisted_username": "SMTPUSER",
                    "password": "SMTPPASS",
                    "smtp_host": "email-smtp.us-east-1.amazonaws.com",
                    "smtp_port": "587",
                    "message": "",
                },
            ), patch.object(adapter, "_client", side_effect=fake_client):
                result = adapter.send_handoff_email(_profile())

        self.assertEqual(result["sent_to"], "mark@trappfamilyfarm.com")
        self.assertEqual(result["message_id"], "ses-message-001")
        body = sesv2.sent_messages[0]["content"]["Simple"]["Body"]["Text"]["Data"]
        self.assertIn("SMTP username: SMTPUSER", body)
        self.assertNotIn("SMTPPASS", body)


if __name__ == "__main__":
    unittest.main()
