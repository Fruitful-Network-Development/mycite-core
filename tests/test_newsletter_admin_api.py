from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


def _load_newsletter_admin_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "instances" / "_shared" / "runtime" / "flavors" / "fnd" / "portal" / "api" / "newsletter_admin.py"
    for candidate in (repo_root, repo_root / "instances", repo_root / "packages"):
        token = str(candidate)
        if token not in sys.path:
            sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("newsletter_admin_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        if str(getattr(exc, "name", "")) == "flask":
            raise unittest.SkipTest("flask is not installed in host python")
        raise
    return module


class NewsletterAdminApiTests(unittest.TestCase):
    def _headers(self) -> dict[str, str]:
        return {
            "X-Portal-User": "operator",
            "X-Portal-Username": "operator",
            "X-Portal-Roles": "admin",
        }

    def _make_client_with_module(self, private_dir: Path):
        module = _load_newsletter_admin_module()
        try:
            from flask import Flask
        except ModuleNotFoundError as exc:
            if str(getattr(exc, "name", "")) == "flask":
                raise unittest.SkipTest("flask is not installed in host python")
            raise
        app = Flask(__name__)
        app.config["TESTING"] = True
        module.register_newsletter_admin_routes(app, private_dir=private_dir)
        return module, app.test_client()

    def _seed_domain(self, private_dir: Path, domain: str, profile_id: str, sender_email: str) -> Path:
        frontend_root = private_dir.parent / "clients" / domain / "frontend"
        frontend_root.mkdir(parents=True, exist_ok=True)
        fnd_ebi_root = private_dir / "utilities" / "tools" / "fnd-ebi"
        fnd_ebi_root.mkdir(parents=True, exist_ok=True)
        (fnd_ebi_root / f"fnd-ebi.{domain}.json").write_text(
            json.dumps(
                {
                    "schema": "mycite.service_tool.fnd_ebi.profile.v1",
                    "domain": domain,
                    "site_root": str(frontend_root),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        aws_root = private_dir / "utilities" / "tools" / "aws-csm"
        aws_root.mkdir(parents=True, exist_ok=True)
        (aws_root / f"{profile_id}.json").write_text(
            json.dumps(
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": profile_id.replace(".json", ""),
                        "domain": domain,
                        "mailbox_local_part": "technicalContact",
                        "role": "technical_contact",
                        "operator_inbox_target": "operator@example.com",
                        "send_as_email": sender_email,
                    },
                    "verification": {"status": "verified"},
                    "provider": {
                        "aws_ses_identity_status": "verified",
                        "gmail_send_as_status": "verified",
                    },
                    "workflow": {
                        "handoff_status": "send_as_confirmed",
                        "is_send_as_confirmed": True,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        newsletter_root = private_dir / "utilities" / "tools" / "newsletter-admin"
        newsletter_root.mkdir(parents=True, exist_ok=True)
        (newsletter_root / f"newsletter-admin.{domain}.json").write_text(
            json.dumps(
                {
                    "schema": "mycite.service_tool.newsletter.profile.v1",
                    "domain": domain,
                    "list_address": f"news@{domain}",
                    "sender_address": f"news@{domain}",
                    "selected_author_profile_id": profile_id,
                    "selected_author_address": sender_email,
                    "selected_sender_profile_id": profile_id,
                    "selected_sender_address": sender_email,
                    "contact_log_path": str(frontend_root.parent / "contacts" / f"{domain}-contact_log.json"),
                    "delivery_mode": "aws_sqs_lambda_us_east_1",
                    "aws_region": "us-east-1",
                    "dispatch_queue_url": "https://sqs.us-east-1.amazonaws.com/065948377733/aws-cms-newsletter-dispatch",
                    "dispatch_queue_arn": "arn:aws:sqs:us-east-1:065948377733:aws-cms-newsletter-dispatch",
                    "dispatcher_lambda_name": "newsletter-dispatcher",
                    "dispatcher_callback_url": f"https://{domain}/__fnd/newsletter/dispatch-result",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return frontend_root.parent / "contacts" / f"{domain}-contact_log.json"

    def test_public_signup_and_unsubscribe_mutate_canonical_contact_log(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            log_path = self._seed_domain(
                private_dir,
                "trappfamilyfarm.com",
                "aws-csm.tff.technicalContact",
                "technicalContact@trappfamilyfarm.com",
            )
            module, client = self._make_client_with_module(private_dir)

            subscribe = client.post(
                "/__fnd/newsletter/subscribe",
                data={"domain": "trappfamilyfarm.com", "email": "tester@example.com", "name": "Tester"},
            )
            self.assertEqual(subscribe.status_code, 200)
            self.assertTrue(log_path.exists())
            payload = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload.get("contacts") or []), 1)
            self.assertTrue((payload.get("contacts") or [])[0].get("subscribed"))

            token = module.unsubscribe_token(
                module.newsletter_signing_secret(private_dir),
                domain="trappfamilyfarm.com",
                email="tester@example.com",
            )
            unsubscribe = client.get(
                f"/__fnd/newsletter/unsubscribe?domain=trappfamilyfarm.com&email=tester@example.com&token={token}",
                headers={"Accept": "text/html"},
            )
            self.assertEqual(unsubscribe.status_code, 200)
            payload = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertFalse((payload.get("contacts") or [])[0].get("subscribed"))

    def test_admin_send_rejects_manual_dispatch_in_favor_of_inbound_workflow(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            self._seed_domain(
                private_dir,
                "cuyahogavalleycountrysideconservancy.org",
                "aws-csm.cvcc.technicalContact",
                "technicalContact@cuyahogavalleycountrysideconservancy.org",
            )
            module, client = self._make_client_with_module(private_dir)
            response = client.post(
                "/portal/api/admin/newsletter/domain/cuyahogavalleycountrysideconservancy.org/send",
                headers=self._headers(),
                json={
                    "subject": "Test subject",
                    "body_text": "Test body",
                    "selected_sender_profile_id": "aws-csm.cvcc.technicalContact",
                },
            )
            self.assertEqual(response.status_code, 409)
            payload = response.get_json() or {}
            self.assertFalse(payload.get("ok"))
            self.assertIn("inbound-mail workflow only", str(payload.get("error") or ""))

    def test_process_inbound_queues_recipient_jobs_and_callback_records_delivery(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            log_path = self._seed_domain(
                private_dir,
                "cuyahogavalleycountrysideconservancy.org",
                "aws-csm.cvcc.technicalContact",
                "technicalContact@cuyahogavalleycountrysideconservancy.org",
            )
            module, client = self._make_client_with_module(private_dir)
            client.post(
                "/__fnd/newsletter/subscribe",
                data={"domain": "cuyahogavalleycountrysideconservancy.org", "email": "reader@example.com"},
            )
            client.post(
                "/__fnd/newsletter/subscribe",
                data={"domain": "cuyahogavalleycountrysideconservancy.org", "email": "skip@example.com"},
            )
            token = module.unsubscribe_token(
                module.newsletter_signing_secret(private_dir),
                domain="cuyahogavalleycountrysideconservancy.org",
                email="skip@example.com",
            )
            client.get(
                "/__fnd/newsletter/unsubscribe?domain=cuyahogavalleycountrysideconservancy.org&email=skip@example.com&token=" + token,
                headers={"Accept": "text/html"},
            )
            inbound_bytes = (
                "From: technicalContact@cuyahogavalleycountrysideconservancy.org\n"
                "To: news@cuyahogavalleycountrysideconservancy.org\n"
                "Subject: Inbound newsletter subject\n"
                "\n"
                "Inbound newsletter body.\n"
            ).encode("utf-8")
            with mock.patch.object(
                module,
                "_newsletter_active_inbound_chain",
                return_value={"s3_bucket": "bucket", "s3_prefix": "inbound/cvcc/"},
            ), mock.patch.object(
                module,
                "_aws_cli_json",
                side_effect=[
                    [["inbound/cvcc/message-1", "2026-04-06T05:44:11Z", 128]],
                    {"MessageId": "queue-msg-1"},
                ],
            ), mock.patch.object(module, "_aws_cli_bytes", return_value=inbound_bytes):
                response = client.post(
                    "/portal/api/admin/newsletter/domain/cuyahogavalleycountrysideconservancy.org/process_inbound",
                    headers=self._headers(),
                    json={},
                )
            self.assertEqual(response.status_code, 200)
            payload = json.loads(log_path.read_text(encoding="utf-8"))
            dispatches = payload.get("dispatches") or []
            self.assertEqual(len(dispatches), 1)
            self.assertEqual((dispatches[0].get("sender_profile_id")), "aws-csm.cvcc.technicalContact")
            self.assertEqual((dispatches[0].get("sender_address")), "news@cuyahogavalleycountrysideconservancy.org")
            self.assertEqual((dispatches[0].get("author_address")), "technicalContact@cuyahogavalleycountrysideconservancy.org")
            self.assertEqual((dispatches[0].get("queued_count")), 1)
            self.assertEqual((dispatches[0].get("target_count")), 1)
            self.assertEqual((dispatches[0].get("source_kind")), "inbound_email")
            self.assertEqual(((dispatches[0].get("results") or [])[0].get("queue_message_id")), "queue-msg-1")
            contacts = payload.get("contacts") or []
            by_email = {str(item.get("email") or ""): item for item in contacts}
            self.assertEqual((by_email["reader@example.com"].get("send_count")), 0)
            self.assertEqual((by_email["skip@example.com"].get("send_count")), 0)

            callback = client.post(
                "/__fnd/newsletter/dispatch-result",
                headers={"X-Newsletter-Dispatch-Token": module.newsletter_dispatch_secret(private_dir)},
                json={
                    "domain": "cuyahogavalleycountrysideconservancy.org",
                    "dispatch_id": dispatches[0].get("dispatch_id"),
                    "email": "reader@example.com",
                    "status": "sent",
                    "message_id": "ses-msg-1",
                },
            )
            self.assertEqual(callback.status_code, 200)
            payload = json.loads(log_path.read_text(encoding="utf-8"))
            dispatches = payload.get("dispatches") or []
            self.assertEqual((dispatches[0].get("sent_count")), 1)
            self.assertEqual(((dispatches[0].get("results") or [])[0].get("message_id")), "ses-msg-1")
            contacts = payload.get("contacts") or []
            by_email = {str(item.get("email") or ""): item for item in contacts}
            self.assertEqual((by_email["reader@example.com"].get("send_count")), 1)
            self.assertEqual((by_email["skip@example.com"].get("send_count")), 0)

    def test_public_signup_rejects_invalid_email(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            self._seed_domain(
                private_dir,
                "trappfamilyfarm.com",
                "aws-csm.tff.technicalContact",
                "technicalContact@trappfamilyfarm.com",
            )
            _module, client = self._make_client_with_module(private_dir)

            response = client.post(
                "/__fnd/newsletter/subscribe",
                data={"domain": "trappfamilyfarm.com", "email": "bad address"},
            )
            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertFalse(payload.get("ok"))
