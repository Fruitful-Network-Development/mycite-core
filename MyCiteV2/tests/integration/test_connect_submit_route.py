"""Phase 17c — /__fnd/connect/submit route contract.

The public Connect-form endpoint:
  - validates email + message
  - resolves the grantee for the request host's domain
  - attempts SES forwarding to ``grantee.connect.forward_to_email``
  - persists the visitor as an unsubscribed contact with
    source=connect_form, forward_status reflecting the SES outcome

All SES interactions are mocked via boto3 so the test suite stays
deterministic and offline.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA


def _seed_grantee(grantee_dir: Path, msn_id: str, domains: list, forward_to: str = "", ses_identity: str = "") -> None:
    grantee_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": GRANTEE_PROFILE_SCHEMA,
        "msn_id": msn_id,
        "label": msn_id,
        "short_name": msn_id,
        "domains": domains,
        "users": [],
    }
    if forward_to:
        payload["connect"] = {"forward_to_email": forward_to}
    if ses_identity:
        payload["aws_ses"] = {"identity": ses_identity, "region": "us-east-1"}
    (grantee_dir / f"grantee.fnd-msn.{msn_id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _seed_newsletter_admin_profile(private_dir: Path, domain: str) -> None:
    admin_dir = private_dir / "utilities" / "tools" / "newsletter-admin"
    admin_dir.mkdir(parents=True, exist_ok=True)
    (admin_dir / f"newsletter-admin.{domain}.json").write_text(
        json.dumps({"domain": domain, "configured": True}), encoding="utf-8"
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class ConnectSubmitRouteTests(unittest.TestCase):
    def _build_client(self, *, forward_to: str = "dylan@fruitfulnetworkdevelopment.com", ses_identity: str = "noreply@fruitfulnetworkdevelopment.com"):
        tmp = Path(tempfile.mkdtemp(prefix="phase17c_connect_submit_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_grantee(
            tmp / "private" / "utilities" / "tools" / "fnd-csm",
            "fnd",
            ["fruitfulnetworkdevelopment.com"],
            forward_to=forward_to,
            ses_identity=ses_identity,
        )
        _seed_newsletter_admin_profile(tmp / "private", "fruitfulnetworkdevelopment.com")
        authority_db = tmp / "authority.sqlite3"
        authority_db.touch()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="fruitfulnetworkdevelopment.com",
            webapps_root=tmp / "webapps",
            authority_db_file=authority_db,
        )
        return create_app(config).test_client(), tmp

    def _post_connect(self, client, **fields):
        body = {"email": "visitor@example.test", "message": "Hi", **fields}
        return client.post(
            "/__fnd/connect/submit",
            data=json.dumps(body),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )

    def test_success_forwards_via_ses_and_persists(self) -> None:
        from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
            MosDatumNewsletterContactLogAdapter,
        )

        client, tmp = self._build_client()
        with patch("boto3.client") as boto:
            boto.return_value.send_email.return_value = {"MessageId": "test-msg-1"}
            resp = self._post_connect(
                client,
                first_name="Visitor",
                last_name="Test",
                subject="Hello",
                message="Just saying hi from the website.",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["forward_status"], "sent")
        self.assertFalse(body["subscribed"])

        # boto3.client called with the right service + region.
        boto.assert_called_with("ses", region_name="us-east-1")
        # send_email called with the configured forward_to + reply-to set
        # to the visitor's email.
        call_kwargs = boto.return_value.send_email.call_args.kwargs
        self.assertEqual(call_kwargs["Source"], "noreply@fruitfulnetworkdevelopment.com")
        self.assertEqual(
            call_kwargs["Destination"]["ToAddresses"],
            ["dylan@fruitfulnetworkdevelopment.com"],
        )
        self.assertEqual(call_kwargs["ReplyToAddresses"], ["visitor@example.test"])
        self.assertIn("Hello", call_kwargs["Message"]["Subject"]["Data"])

        # Persisted as unsubscribed contact with source=connect_form.
        adapter = MosDatumNewsletterContactLogAdapter(
            authority_db_file=tmp / "authority.sqlite3", tenant_id="fnd"
        )
        row = adapter.load_contact_log(domain="fruitfulnetworkdevelopment.com")["contacts"][0]
        self.assertFalse(row["subscribed"])
        self.assertEqual(row["source"], "connect_form")
        self.assertEqual(row["subject"], "Hello")
        self.assertEqual(row["forward_status"], "sent")

    def test_ses_failure_persists_with_failed_status(self) -> None:
        from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
            MosDatumNewsletterContactLogAdapter,
        )

        client, tmp = self._build_client()
        with patch("boto3.client") as boto:
            boto.return_value.send_email.side_effect = RuntimeError("SES timeout")
            resp = self._post_connect(client, message="Body")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        # We still ack ok=True because the contact was persisted, but
        # forward_status carries the failure so the operator can retry.
        self.assertTrue(body["ok"])
        self.assertEqual(body["forward_status"], "failed")
        adapter = MosDatumNewsletterContactLogAdapter(
            authority_db_file=tmp / "authority.sqlite3", tenant_id="fnd"
        )
        row = adapter.load_contact_log(domain="fruitfulnetworkdevelopment.com")["contacts"][0]
        self.assertEqual(row["forward_status"], "failed")

    def test_no_forward_config_marks_pending(self) -> None:
        # Grantee has no connect.forward_to_email — submission should
        # still persist; forward_status=pending.
        client, _tmp = self._build_client(forward_to="", ses_identity="")
        with patch("boto3.client") as boto:
            resp = self._post_connect(client, message="Body")
        # boto3 must not have been called — forwarding is not configured.
        boto.assert_not_called()
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["forward_status"], "pending")

    def test_missing_message_returns_400(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/connect/submit",
            data=json.dumps({"email": "visitor@example.test"}),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "missing_message")

    def test_invalid_email_returns_400(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/connect/submit",
            data=json.dumps({"email": "garbage", "message": "x"}),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_email")

    # ------------------------------------------------------------------
    # Form-encoded fallback (no-JS submit). The frontend form carries
    # action="/__fnd/connect/submit" method="post", so a visitor with
    # JavaScript disabled posts urlencoded fields instead of JSON.
    # ------------------------------------------------------------------

    def test_form_encoded_success_returns_html(self) -> None:
        from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
            MosDatumNewsletterContactLogAdapter,
        )

        client, tmp = self._build_client()
        with patch("boto3.client") as boto:
            boto.return_value.send_email.return_value = {"MessageId": "test-msg-2"}
            resp = client.post(
                "/__fnd/connect/submit",
                data={
                    "email": "noscript@example.test",
                    "message": "Hi from a browser with JS disabled.",
                    "first_name": "Pat",
                    "last_name": "Reader",
                    "subject": "No-JS test",
                },
                base_url="http://fruitfulnetworkdevelopment.com",
                headers={"Referer": "http://fruitfulnetworkdevelopment.com/contact.html"},
            )
        self.assertEqual(resp.status_code, 200)
        # HTML response, not JSON — that's the visible no-JS UX.
        self.assertIn("text/html", resp.headers["Content-Type"])
        body = resp.get_data(as_text=True)
        self.assertIn("Message received", body)
        self.assertIn("contact.html", body)  # link back to referrer
        # Contact still persisted via the same mutation runtime as the JSON path.
        adapter = MosDatumNewsletterContactLogAdapter(
            authority_db_file=tmp / "authority.sqlite3", tenant_id="fnd"
        )
        row = adapter.load_contact_log(domain="fruitfulnetworkdevelopment.com")["contacts"][0]
        self.assertEqual(row["email"], "noscript@example.test")
        self.assertEqual(row["source"], "connect_form")
        self.assertEqual(row["forward_status"], "sent")

    def test_form_encoded_missing_message_returns_html_400(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/connect/submit",
            data={"email": "noscript@example.test"},
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("text/html", resp.headers["Content-Type"])
        body = resp.get_data(as_text=True)
        self.assertIn("Could not send your message", body)
        self.assertIn("Please include a message", body)

    def test_form_encoded_invalid_email_returns_html_400(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/connect/submit",
            data={"email": "not-an-email", "message": "Hi"},
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("text/html", resp.headers["Content-Type"])
        self.assertIn("Please enter a valid email", resp.get_data(as_text=True))

    def test_accept_json_header_overrides_form_encoded(self) -> None:
        """A form-encoded body with Accept: application/json gets JSON back.

        Lets a JS client POST form-data (matching the HTML action form)
        while still receiving a structured response.
        """
        client, _ = self._build_client()
        with patch("boto3.client") as boto:
            boto.return_value.send_email.return_value = {"MessageId": "test-msg-3"}
            resp = client.post(
                "/__fnd/connect/submit",
                data={"email": "json@example.test", "message": "Hi"},
                headers={"Accept": "application/json"},
                base_url="http://fruitfulnetworkdevelopment.com",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.headers["Content-Type"])
        self.assertTrue(resp.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
