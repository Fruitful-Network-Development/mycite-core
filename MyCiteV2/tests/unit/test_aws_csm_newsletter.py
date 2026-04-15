from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from typing import Any

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.aws_csm_newsletter import (
    AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
    AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
    AwsCsmNewsletterService,
)


class _MemoryStatePort:
    def __init__(self) -> None:
        self._domains = ["fruitfulnetworkdevelopment.com"]
        self._profiles: dict[str, dict[str, Any]] = {}
        self._contact_logs: dict[str, dict[str, Any]] = {}
        self._verified = {
            "fruitfulnetworkdevelopment.com": [
                {
                    "profile_id": "aws-csm.fnd.dylan",
                    "domain": "fruitfulnetworkdevelopment.com",
                    "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                    "mailbox_local_part": "dylan",
                    "role": "operator",
                }
            ]
        }
        self._runtime_seeds = {
            "signing_secret": "signing-seed",
            "dispatch_secret": "dispatch-seed",
            "inbound_secret": "inbound-seed",
        }

    def list_newsletter_domains(self) -> list[str]:
        return list(self._domains)

    def ensure_domain_bootstrap(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
        unsubscribe_secret_name: str,
        dispatch_callback_secret_name: str,
        inbound_callback_secret_name: str,
        inbound_processor_lambda_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if domain not in self._profiles:
            author = self._verified[domain][0]
            self._profiles[domain] = {
                "schema": AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
                "domain": domain,
                "list_address": f"news@{domain}",
                "sender_address": f"news@{domain}",
                "selected_author_profile_id": author["profile_id"],
                "selected_author_address": author["send_as_email"],
                "delivery_mode": "inbound-mail-workflow",
                "aws_region": "us-east-1",
                "dispatch_queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/aws-cms-newsletter-dispatch",
                "dispatch_queue_arn": "arn:aws:sqs:us-east-1:123456789012:aws-cms-newsletter-dispatch",
                "dispatcher_lambda_name": "newsletter-dispatcher",
                "inbound_processor_lambda_name": inbound_processor_lambda_name,
                "callback_url": dispatcher_callback_url,
                "inbound_callback_url": inbound_callback_url,
                "unsubscribe_secret_name": unsubscribe_secret_name,
                "dispatch_callback_secret_name": dispatch_callback_secret_name,
                "inbound_callback_secret_name": inbound_callback_secret_name,
                "last_inbound_message_id": "",
                "last_inbound_status": "",
                "last_inbound_checked_at": "",
                "last_inbound_processed_at": "",
                "last_inbound_subject": "",
                "last_inbound_sender": "",
                "last_inbound_recipient": "",
                "last_inbound_error": "",
                "last_inbound_s3_uri": "",
                "last_dispatch_id": "",
            }
        if domain not in self._contact_logs:
            self._contact_logs[domain] = {
                "schema": AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
                "domain": domain,
                "contacts": [],
                "dispatches": [],
                "updated_at": "",
            }
        return deepcopy(self._profiles[domain]), deepcopy(self._contact_logs[domain])

    def list_verified_author_profiles(self, *, domain: str) -> list[dict[str, Any]]:
        return deepcopy(self._verified.get(domain, []))

    def load_profile(self, *, domain: str) -> dict[str, Any]:
        return deepcopy(self._profiles.get(domain, {}))

    def save_profile(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._profiles[domain] = deepcopy(payload)
        return deepcopy(payload)

    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        return deepcopy(self._contact_logs.get(domain, {}))

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._contact_logs[domain] = deepcopy(payload)
        return deepcopy(payload)

    def runtime_secret_seed(self, *, secret_kind: str) -> str:
        return self._runtime_seeds.get(secret_kind, "")


class _MemoryCloudPort:
    def __init__(self) -> None:
        self.secrets: dict[str, str] = {}
        self.queued_messages: list[dict[str, Any]] = []
        self.s3_objects: dict[str, bytes] = {}

    def get_or_create_secret_value(self, *, secret_name: str, initial_value: str) -> str:
        if secret_name not in self.secrets:
            self.secrets[secret_name] = initial_value
        return self.secrets[secret_name]

    def queue_dispatch_message(self, *, queue_url: str, payload: dict[str, Any], region: str) -> str:
        self.queued_messages.append(
            {
                "queue_url": queue_url,
                "payload": deepcopy(payload),
                "region": region,
            }
        )
        return f"msg-{len(self.queued_messages)}"

    def read_s3_bytes(self, *, s3_uri: str, region: str) -> bytes:
        return self.s3_objects[s3_uri]

    def caller_identity_summary(self) -> dict[str, Any]:
        return {"status": "ok", "arn": "arn:aws:sts::123456789012:assumed-role/EC2-AWSCMS-Admin/test"}

    def queue_health_summary(self, *, queue_url: str, queue_arn: str, region: str) -> dict[str, Any]:
        return {"status": "ok", "queue_arn": queue_arn, "pending_message_count": 0}

    def lambda_health_summary(self, *, function_name: str, region: str) -> dict[str, Any]:
        return {"status": "active", "function_arn": f"arn:aws:lambda:{region}:123456789012:function:{function_name}"}

    def receipt_rule_summary(
        self,
        *,
        domain: str,
        expected_recipient: str,
        expected_lambda_name: str,
        region: str,
    ) -> dict[str, Any]:
        return {
            "status": "ok",
            "domain": domain,
            "expected_recipient": expected_recipient,
            "matching_rules": [
                {
                    "rule_name": f"capture-{domain}",
                    "recipient_match": True,
                    "s3_action_present": True,
                    "lambda_action_present": True,
                }
            ],
        }


class AwsCsmNewsletterServiceUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = _MemoryStatePort()
        self.cloud = _MemoryCloudPort()
        self.service = AwsCsmNewsletterService(self.state, self.cloud, tenant_id="fnd")

    def test_unknown_domain_is_rejected(self) -> None:
        with self.assertRaisesRegex(LookupError, "not configured"):
            self.service.resolve_domain_state(
                domain="example.com",
                dispatcher_callback_url="https://example.com/__fnd/newsletter/dispatch-result",
                inbound_callback_url="https://example.com/__fnd/newsletter/inbound-capture",
            )

    def test_subscribe_then_unsubscribe_preserves_record(self) -> None:
        domain = "fruitfulnetworkdevelopment.com"
        subscribed = self.service.subscribe(
            domain=domain,
            email="friend@example.com",
            name="Friend",
            zip_code="44236",
            dispatcher_callback_url=f"https://{domain}/__fnd/newsletter/dispatch-result",
            inbound_callback_url=f"https://{domain}/__fnd/newsletter/inbound-capture",
        )
        self.assertTrue(subscribed["subscribed"])

        token = self.service.render_unsubscribe_token(domain=domain, email="friend@example.com")
        unsubscribed = self.service.unsubscribe(
            domain=domain,
            email="friend@example.com",
            token=token,
            dispatcher_callback_url=f"https://{domain}/__fnd/newsletter/dispatch-result",
            inbound_callback_url=f"https://{domain}/__fnd/newsletter/inbound-capture",
        )

        self.assertIsNotNone(unsubscribed)
        self.assertFalse(bool((unsubscribed or {}).get("subscribed")))
        stored = self.state.load_contact_log(domain=domain)
        self.assertEqual(len(stored["contacts"]), 1)
        self.assertFalse(bool(stored["contacts"][0]["subscribed"]))

    def test_inbound_capture_queues_only_subscribed_contacts(self) -> None:
        domain = "fruitfulnetworkdevelopment.com"
        self.service.subscribe(
            domain=domain,
            email="subscribed@example.com",
            dispatcher_callback_url=f"https://{domain}/__fnd/newsletter/dispatch-result",
            inbound_callback_url=f"https://{domain}/__fnd/newsletter/inbound-capture",
        )
        self.service.subscribe(
            domain=domain,
            email="later-unsubscribed@example.com",
            dispatcher_callback_url=f"https://{domain}/__fnd/newsletter/dispatch-result",
            inbound_callback_url=f"https://{domain}/__fnd/newsletter/inbound-capture",
        )
        token = self.service.render_unsubscribe_token(domain=domain, email="later-unsubscribed@example.com")
        self.service.unsubscribe(
            domain=domain,
            email="later-unsubscribed@example.com",
            token=token,
            dispatcher_callback_url=f"https://{domain}/__fnd/newsletter/dispatch-result",
            inbound_callback_url=f"https://{domain}/__fnd/newsletter/inbound-capture",
        )
        self.cloud.s3_objects["s3://ses-inbound-fnd-mail/inbound/fnd/test-message"] = (
            b"Subject: April Update\r\n\r\nThis is the current newsletter body.\r\n"
        )
        signature = self.service.render_inbound_capture_signature(
            domain=domain,
            ses_message_id="ses-message-1",
            s3_uri="s3://ses-inbound-fnd-mail/inbound/fnd/test-message",
            sender="dylan@fruitfulnetworkdevelopment.com",
            recipient="news@fruitfulnetworkdevelopment.com",
            subject="April Update",
            captured_at="2026-04-13T00:00:00+00:00",
        )

        result = self.service.process_inbound_capture(
            signature=signature,
            domain=domain,
            ses_message_id="ses-message-1",
            s3_uri="s3://ses-inbound-fnd-mail/inbound/fnd/test-message",
            sender="dylan@fruitfulnetworkdevelopment.com",
            recipient="news@fruitfulnetworkdevelopment.com",
            subject="April Update",
            captured_at="2026-04-13T00:00:00+00:00",
            dispatcher_callback_url=f"https://{domain}/__fnd/newsletter/dispatch-result",
            inbound_callback_url=f"https://{domain}/__fnd/newsletter/inbound-capture",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["queued_count"], 1)
        self.assertEqual(len(self.cloud.queued_messages), 1)
        payload = self.cloud.queued_messages[0]["payload"]
        self.assertEqual(payload["recipient_email"], "subscribed@example.com")
        self.assertEqual(payload["sender_address"], "news@fruitfulnetworkdevelopment.com")
        self.assertEqual(payload["reply_to_address"], "dylan@fruitfulnetworkdevelopment.com")

    def test_inbound_capture_with_no_subscribers_completes_without_error_status(self) -> None:
        domain = "fruitfulnetworkdevelopment.com"
        self.cloud.s3_objects["s3://ses-inbound-fnd-mail/inbound/fnd/empty-audience-message"] = (
            b"Subject: Empty Audience Update\r\n\r\nThis should not be treated as an error.\r\n"
        )
        signature = self.service.render_inbound_capture_signature(
            domain=domain,
            ses_message_id="ses-message-empty",
            s3_uri="s3://ses-inbound-fnd-mail/inbound/fnd/empty-audience-message",
            sender="dylan@fruitfulnetworkdevelopment.com",
            recipient="news@fruitfulnetworkdevelopment.com",
            subject="Empty Audience Update",
            captured_at="2026-04-13T00:30:00+00:00",
        )

        result = self.service.process_inbound_capture(
            signature=signature,
            domain=domain,
            ses_message_id="ses-message-empty",
            s3_uri="s3://ses-inbound-fnd-mail/inbound/fnd/empty-audience-message",
            sender="dylan@fruitfulnetworkdevelopment.com",
            recipient="news@fruitfulnetworkdevelopment.com",
            subject="Empty Audience Update",
            captured_at="2026-04-13T00:30:00+00:00",
            dispatcher_callback_url=f"https://{domain}/__fnd/newsletter/dispatch-result",
            inbound_callback_url=f"https://{domain}/__fnd/newsletter/inbound-capture",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["queued_count"], 0)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["dispatch"]["target_count"], 0)
        self.assertEqual(result["dispatch"]["status"], "completed")
        self.assertEqual(len(self.cloud.queued_messages), 0)


if __name__ == "__main__":
    unittest.main()
