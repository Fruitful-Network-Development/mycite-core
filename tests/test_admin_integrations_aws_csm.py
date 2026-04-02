from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


def _load_admin_integrations_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "portals"
        / "_shared"
        / "runtime"
        / "flavors"
        / "fnd"
        / "portal"
        / "api"
        / "admin_integrations.py"
    )
    portals_root = path.parents[7]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("admin_integrations_aws_csm_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        if str(getattr(exc, "name", "")) == "flask":
            raise unittest.SkipTest("flask is not installed in host python")
        raise
    return module


class AdminIntegrationsAwsCsmTests(unittest.TestCase):
    def _headers(self) -> dict[str, str]:
        return {
            "X-Portal-User": "operator",
            "X-Portal-Username": "operator",
            "X-Portal-Roles": "admin",
        }

    def _make_client(self, private_dir: Path):
        _, client = self._make_client_with_module(private_dir)
        return client

    def _make_client_with_module(self, private_dir: Path):
        module = _load_admin_integrations_module()
        try:
            from flask import Flask
        except ModuleNotFoundError as exc:
            if str(getattr(exc, "name", "")) == "flask":
                raise unittest.SkipTest("flask is not installed in host python")
            raise
        app = Flask(__name__)
        app.config["TESTING"] = True
        module.register_admin_integration_routes(app, private_dir=private_dir)
        return module, app.test_client()

    def test_admin_aws_status_ignores_removed_admin_runtime_root(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            legacy_root = private_dir / "admin_runtime" / "aws"
            legacy_root.mkdir(parents=True, exist_ok=True)
            (legacy_root / "fnd.json").write_text(
                json.dumps({"configured": True, "region": "us-east-1"}) + "\n",
                encoding="utf-8",
            )

            client = self._make_client(private_dir)
            response = client.get("/portal/api/admin/aws/profile/fnd", headers=self._headers())
            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertFalse(payload.get("configured"))
            self.assertTrue(str(payload.get("canonical_root") or "").endswith("/private/utilities/tools/aws-csm"))
            self.assertTrue(str(payload.get("profile_path") or "").endswith("/private/utilities/tools/aws-csm/aws-csm.fnd.json"))
            self.assertNotIn("admin_runtime", str(payload.get("profile_path") or ""))
            self.assertFalse((private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.fnd.json").exists())

            tenant_response = client.get("/portal/api/admin/aws/tenant/fnd/status", headers=self._headers())
            self.assertEqual(tenant_response.status_code, 200)
            tenant_payload = tenant_response.get_json() or {}
            self.assertEqual(((tenant_payload.get("deprecation") or {}).get("canonical_endpoint")), "/portal/api/admin/aws/profile/fnd")

    def test_admin_aws_profile_save_and_provision_write_only_to_canonical_root(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            client = self._make_client(private_dir)

            save_response = client.put(
                "/portal/api/admin/aws/profile/fnd",
                headers=self._headers(),
                json={
                    "identity": {
                        "tenant_id": "fnd",
                        "domain": "fruitfulnetworkdevelopment.com",
                        "region": "us-east-1",
                        "single_user_email": "dylancarsonmontgomery@gmail.com",
                        "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                    },
                    "smtp": {
                        "username": "AKIAEXAMPLE",
                        "credentials_secret_name": "aws-cms/smtp/fnd",
                        "credentials_secret_state": "configured",
                        "forward_to_email": "dylancarsonmontgomery@gmail.com",
                        "forwarding_status": "active",
                    },
                    "verification": {
                        "status": "pending",
                        "code": "123456",
                        "portal_state": "verification_email_received",
                    },
                    "provider": {
                        "aws_ses_identity_status": "verified",
                        "gmail_send_as_status": "not_started",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)
            save_payload = save_response.get_json() or {}
            profile_path = private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.fnd.json"
            self.assertEqual(Path(save_payload.get("profile_path") or ""), profile_path)
            self.assertTrue(profile_path.exists())
            stored = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(((stored.get("identity") or {}).get("tenant_id")), "fnd")
            self.assertEqual((((stored.get("smtp") or {}).get("credentials_secret_name"))), "aws-cms/smtp/fnd")
            self.assertEqual((((stored.get("smtp") or {}).get("credentials_secret_state"))), "configured")
            self.assertEqual(((stored.get("workflow") or {}).get("flow")), "single_user_send_as")
            self.assertEqual(((stored.get("workflow") or {}).get("handoff_status")), "ready_for_gmail_handoff")
            self.assertNotIn("alias_email", stored)
            self.assertNotIn("gmail_send_as_status", stored)

            provision_response = client.post(
                "/portal/api/admin/aws/profile/fnd/provision",
                headers=self._headers(),
                json={"action": "prepare_send_as"},
            )
            self.assertEqual(provision_response.status_code, 202)
            provision_payload = provision_response.get_json() or {}
            self.assertEqual(Path(provision_payload.get("profile_path") or ""), profile_path)
            self.assertTrue(str(provision_payload.get("canonical_root") or "").endswith("/private/utilities/tools/aws-csm"))

            actions_log = private_dir / "utilities" / "tools" / "aws-csm" / "actions.ndjson"
            provision_log = private_dir / "utilities" / "tools" / "aws-csm" / "provision_requests.ndjson"
            self.assertTrue(actions_log.exists())
            self.assertTrue(provision_log.exists())
            self.assertFalse((private_dir / "admin_runtime" / "aws").exists())

    def test_admin_aws_profile_rejects_newsletter_and_emailer_actions(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            client = self._make_client(private_dir)

            client.put(
                "/portal/api/admin/aws/profile/fnd",
                headers=self._headers(),
                json={
                    "identity": {
                        "tenant_id": "fnd",
                        "domain": "fruitfulnetworkdevelopment.com",
                        "single_user_email": "dylancarsonmontgomery@gmail.com",
                        "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                    },
                    "smtp": {
                        "username": "AKIAEXAMPLE",
                    },
                },
            )

            rejected = client.post(
                "/portal/api/admin/aws/profile/fnd/provision",
                headers=self._headers(),
                json={"action": "emailer_sync_preview"},
            )
            self.assertEqual(rejected.status_code, 400)
            payload = rejected.get_json() or {}
            self.assertIn("newsletter/emailer actions are not part of the active AWS-CMS scope", list(payload.get("errors") or []))

    def test_admin_aws_capture_verification_returns_metadata_and_updates_profile(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            module, client = self._make_client_with_module(private_dir)

            client.put(
                "/portal/api/admin/aws/profile/fnd",
                headers=self._headers(),
                json={
                    "identity": {
                        "tenant_id": "fnd",
                        "domain": "fruitfulnetworkdevelopment.com",
                        "region": "us-east-1",
                        "single_user_email": "dylancarsonmontgomery@gmail.com",
                        "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                    },
                    "smtp": {
                        "username": "AKIAEXAMPLE",
                        "credentials_secret_name": "aws-cms/smtp/fnd",
                        "credentials_secret_state": "configured",
                        "forward_to_email": "dylancarsonmontgomery@gmail.com",
                    },
                    "verification": {"status": "not_started"},
                    "provider": {
                        "aws_ses_identity_status": "verified",
                        "gmail_send_as_status": "not_started",
                    },
                },
            )

            with mock.patch.object(
                module,
                "_find_latest_verification_message",
                return_value=(
                    {
                        "sender": "Gmail Team <gmail-noreply@google.com>",
                        "subject": "Gmail Confirmation - Send Mail as dylan@fruitfulnetworkdevelopment.com",
                        "captured_at": "2026-04-02T15:21:24+00:00",
                        "message_date": "2026-04-02T15:21:20+00:00",
                        "s3_bucket": "ses-inbound-fnd-mail",
                        "s3_key": "inbound/example",
                        "s3_uri": "s3://ses-inbound-fnd-mail/inbound/example",
                        "message_id": "example",
                        "confirmation_link": "https://mail-settings.google.com/mail/vf-example",
                    },
                    {
                        "receipt_rule_set": "fnd-inbound-rules",
                        "receipt_rule_name": "mode-a-forward-dcmontgomery",
                        "forward_to_email": "dylancarsonmontgomery@gmail.com",
                        "forward_from_email": "forwarder@fruitfulnetworkdevelopment.com",
                    },
                ),
            ):
                response = client.post(
                    "/portal/api/admin/aws/profile/fnd/provision",
                    headers=self._headers(),
                    json={"action": "capture_verification"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            verification_message = payload.get("verification_message") if isinstance(payload.get("verification_message"), dict) else {}
            self.assertEqual(payload.get("status"), "completed")
            self.assertEqual(verification_message.get("s3_uri"), "s3://ses-inbound-fnd-mail/inbound/example")
            self.assertEqual(verification_message.get("confirmation_link"), "https://mail-settings.google.com/mail/vf-example")
            stored = json.loads((private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.fnd.json").read_text(encoding="utf-8"))
            verification = stored.get("verification") if isinstance(stored.get("verification"), dict) else {}
            self.assertEqual(verification.get("email_received_at"), "2026-04-02T15:21:24+00:00")
            self.assertEqual(verification.get("portal_state"), "verification_email_received")

    def test_admin_aws_confirm_verified_marks_send_as_complete(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            module, client = self._make_client_with_module(private_dir)

            client.put(
                "/portal/api/admin/aws/profile/fnd",
                headers=self._headers(),
                json={
                    "identity": {
                        "tenant_id": "fnd",
                        "domain": "fruitfulnetworkdevelopment.com",
                        "region": "us-east-1",
                        "single_user_email": "dylancarsonmontgomery@gmail.com",
                        "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                    },
                    "smtp": {
                        "username": "AKIAEXAMPLE",
                        "credentials_secret_name": "aws-cms/smtp/fnd",
                        "credentials_secret_state": "configured",
                        "forward_to_email": "dylancarsonmontgomery@gmail.com",
                    },
                    "verification": {"status": "not_started"},
                    "provider": {
                        "aws_ses_identity_status": "verified",
                        "gmail_send_as_status": "not_started",
                    },
                },
            )

            with mock.patch.object(
                module,
                "_find_latest_verification_message",
                return_value=(
                    {
                        "sender": "Gmail Team <gmail-noreply@google.com>",
                        "subject": "Gmail Confirmation - Send Mail as dylan@fruitfulnetworkdevelopment.com",
                        "captured_at": "2026-04-02T15:21:24+00:00",
                        "message_date": "2026-04-02T15:21:20+00:00",
                        "s3_bucket": "ses-inbound-fnd-mail",
                        "s3_key": "inbound/example",
                        "s3_uri": "s3://ses-inbound-fnd-mail/inbound/example",
                        "message_id": "example",
                        "confirmation_link": "https://mail-settings.google.com/mail/vf-example",
                    },
                    {
                        "receipt_rule_set": "fnd-inbound-rules",
                        "receipt_rule_name": "mode-a-forward-dcmontgomery",
                        "forward_to_email": "dylancarsonmontgomery@gmail.com",
                        "forward_from_email": "forwarder@fruitfulnetworkdevelopment.com",
                    },
                ),
            ):
                response = client.post(
                    "/portal/api/admin/aws/profile/fnd/provision",
                    headers=self._headers(),
                    json={"action": "confirm_verified"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
            verification = profile.get("verification") if isinstance(profile.get("verification"), dict) else {}
            provider = profile.get("provider") if isinstance(profile.get("provider"), dict) else {}
            workflow = profile.get("workflow") if isinstance(profile.get("workflow"), dict) else {}
            self.assertEqual(verification.get("status"), "verified")
            self.assertEqual(verification.get("portal_state"), "verified")
            self.assertTrue(str(verification.get("verified_at") or ""))
            self.assertEqual(provider.get("gmail_send_as_status"), "verified")
            self.assertEqual(workflow.get("handoff_status"), "send_as_confirmed")
            self.assertEqual(workflow.get("completion_boundary"), "completed")
            self.assertTrue(bool(workflow.get("is_send_as_confirmed")))

    def test_admin_aws_replay_verification_forward_uses_existing_forwarder_path(self):
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            module, client = self._make_client_with_module(private_dir)

            client.put(
                "/portal/api/admin/aws/profile/fnd",
                headers=self._headers(),
                json={
                    "identity": {
                        "tenant_id": "fnd",
                        "domain": "fruitfulnetworkdevelopment.com",
                        "region": "us-east-1",
                        "single_user_email": "dylancarsonmontgomery@gmail.com",
                        "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                    },
                    "smtp": {
                        "username": "AKIAEXAMPLE",
                        "credentials_secret_name": "aws-cms/smtp/fnd",
                        "credentials_secret_state": "configured",
                        "forward_to_email": "dylancarsonmontgomery@gmail.com",
                    },
                    "verification": {"status": "not_started"},
                    "provider": {
                        "aws_ses_identity_status": "verified",
                        "gmail_send_as_status": "not_started",
                    },
                },
            )

            def fake_aws_cli(args, *, input_bytes=None):
                _ = input_bytes
                Path(str(args[-1])).write_text('{"ok": true, "message_id": "example"}', encoding="utf-8")
                return None

            with mock.patch.object(
                module,
                "_capture_verification_for_profile",
                return_value={
                    "profile": {"workflow": {}},
                    "profile_path": str(private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.fnd.json"),
                    "warnings": [],
                    "verification_message": {
                        "message_id": "example",
                        "s3_uri": "s3://ses-inbound-fnd-mail/inbound/example",
                    },
                    "legacy_inbound": {
                        "lambda_function": "ses-forwarder",
                        "ses_region": "us-east-1",
                    },
                },
            ), mock.patch.object(module, "_aws_cli", side_effect=fake_aws_cli):
                response = client.post(
                    "/portal/api/admin/aws/profile/fnd/provision",
                    headers=self._headers(),
                    json={"action": "replay_verification_forward"},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("status"), "completed")
            self.assertEqual(((payload.get("lambda_result") or {}).get("message_id")), "example")


if __name__ == "__main__":
    unittest.main()
