"""A3 + A4 + A6 — deliverability quick-wins on the portal send sites.

A3: List-Unsubscribe + List-Unsubscribe-Post on every transactional
    nudge emitted by `_send_email_extension_message`; new POST/GET route
    at `/__fnd/profile/<id>/unsubscribe-notifications` records the
    one-click opt-out; send is skipped when the profile is already
    unsubscribed.

A4: Reply-To is always set on every send (no conditional path). When
    the grantee profile doesn't set `aws_ses.reply_to`, default to
    `reply-to@<from_domain>` so it always matches the From domain.

A6: Donation receipt is now multipart/alternative (text + html) under
    a multipart/mixed outer that carries the PDF attachment. Same
    explicit Message-ID + Date headers as A5's send_email path.
"""

from __future__ import annotations

import email
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


def _seed_profile(
    aws_csm_dir: Path,
    profile_id: str = "aws-csm.alpha.support",
    tenant_id: str = "alpha",
    domain: str = "alpha.example.test",
    mailbox: str = "support",
    *,
    handoff_sent: bool = True,
    unsubscribed: bool = False,
    lifecycle_state: str = "draft",
) -> Path:
    aws_csm_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema": "mycite.service_tool.aws.profile.v2",
        "identity": {
            "profile_id": profile_id,
            "tenant_id": tenant_id,
            "domain": domain,
            "region": "us-east-1",
            "mailbox_local_part": mailbox,
            "role": "operator",
            "profile_kind": "mailbox",
            "operator_inbox_target": f"{mailbox}@{domain}",
            "send_as_email": f"{mailbox}@{domain}",
        },
        "workflow": {
            "lifecycle_state": lifecycle_state,
        },
    }
    if handoff_sent:
        payload["workflow"]["handoff_email_sent_at"] = "2026-05-22T10:00:00+00:00"
    if unsubscribed:
        payload["notifications"] = {
            "unsubscribed": True,
            "unsubscribed_at": "2026-05-22T12:00:00+00:00",
        }
    path = aws_csm_dir / f"{profile_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _seed_grantee_json(private_dir: Path, domain: str, *, reply_to: str | None = None) -> None:
    """Mirror the grantee-profile lookup the portal uses.

    Shape matches the live grantee.<fnd_msn>.<grantee_msn>.json JSONs
    parsed by MyCiteV2.packages.core.grantee.store.load_grantee_profile.
    """
    fnd_csm = private_dir / "utilities" / "tools" / "fnd-csm"
    fnd_csm.mkdir(parents=True, exist_ok=True)
    aws_ses: dict[str, str] = {
        "region": "us-east-1",
        "identity": f"support@{domain}",
        "smtp_username": "",
        "smtp_password": "",
        "from_address": f"support@{domain}",
        "from_name": "Alpha",
        "configuration_set": "fnd-default",
    }
    if reply_to is not None:
        aws_ses["reply_to"] = reply_to
    grantee = {
        "schema": "mycite.v2.grantee.profile.v1",
        "msn_id": "alpha-msn",
        "label": "Alpha Org",
        "short_name": "Alpha",
        "domains": [domain],
        "users": [f"support@{domain}"],
        "aws_ses": aws_ses,
        "connect": {"forward_to_email": f"support@{domain}"},
    }
    (fnd_csm / "grantee.fnd-msn.alpha-msn.json").write_text(
        json.dumps(grantee), encoding="utf-8"
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class UnsubscribeRouteTests(unittest.TestCase):
    """A3 — POST + GET routes for one-click unsubscribe."""

    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="a3_unsub_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(aws_csm_dir)
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), aws_csm_dir

    def test_post_marks_profile_unsubscribed(self) -> None:
        client, aws_csm_dir = self._build_client()
        resp = client.post(
            "/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications"
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["profile_id"], "aws-csm.alpha.support")
        self.assertIn("unsubscribed_at", body)
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        self.assertTrue(on_disk["notifications"]["unsubscribed"])

    def test_post_is_idempotent(self) -> None:
        client, _ = self._build_client()
        client.post("/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications")
        resp = client.post(
            "/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["already_unsubscribed"])

    def test_post_rejects_unknown_profile(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/profile/aws-csm.ghost.nobody/unsubscribe-notifications"
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_renders_confirm_form(self) -> None:
        client, _ = self._build_client()
        resp = client.get(
            "/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Confirm unsubscribe", body)
        self.assertIn(
            "/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications",
            body,
        )

    def test_get_already_unsubscribed_shows_done_page(self) -> None:
        client, _ = self._build_client()
        client.post("/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications")
        resp = client.get(
            "/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("already unsubscribed", body.lower())


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class SendExtensionMessageHeaderTests(unittest.TestCase):
    """A3 + A4 — headers and skip-on-unsubscribed on the send helper.

    Exercised via the resend-handoff admin route, which calls
    `_send_email_extension_message` internally. The route's closure
    captures `_aws_peripheral` from the module at create_app time, so
    the test must patch BEFORE create_app is invoked.
    """

    def _capture_send(self) -> list[dict]:
        from unittest.mock import patch

        tmp = Path(tempfile.mkdtemp(prefix="a3a4_send_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(aws_csm_dir)
        _seed_grantee_json(tmp / "private", "alpha.example.test")
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        captured: list[dict] = []

        def fake_send_email(**kwargs):
            captured.append(kwargs)
            return MagicMock(message_id="msg-stub-1")

        with patch(
            "MyCiteV2.instances._shared.portal_host.app._aws_peripheral"
        ) as peripheral:
            peripheral.send_email = fake_send_email
            app = create_app(config)
            client = app.test_client()
            client.post(
                "/__fnd/email/admin/resend-handoff",
                data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
                content_type="application/json",
            )
        return captured

    def test_send_includes_list_unsubscribe_headers(self) -> None:
        captured = self._capture_send()
        self.assertTrue(captured, "no send_email call captured")
        kwargs = captured[-1]
        extra = kwargs.get("extra_headers") or {}
        self.assertIn("List-Unsubscribe", extra)
        self.assertIn(
            "/__fnd/profile/aws-csm.alpha.support/unsubscribe-notifications",
            extra["List-Unsubscribe"],
        )
        self.assertEqual(
            extra.get("List-Unsubscribe-Post"),
            "List-Unsubscribe=One-Click",
        )

    def test_send_passes_reply_to(self) -> None:
        captured = self._capture_send()
        self.assertTrue(captured)
        kwargs = captured[-1]
        reply_to = kwargs.get("reply_to") or []
        self.assertTrue(reply_to, "reply_to missing on send_email kwargs")
        # Defaulted to reply-to@<from_domain> when grantee aws_ses didn't
        # set one — the seeded grantee sets from_address =
        # support@alpha.example.test and no reply_to, so the fallback
        # must trigger.
        self.assertEqual(reply_to, ["reply-to@alpha.example.test"])


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class UnsubscribedProfileSkipsReminderTests(unittest.TestCase):
    """A3 — once a profile is unsubscribed, the send-reminder route returns
    not_eligible / skipped_reason: unsubscribed and does NOT call SES.
    """

    def test_unsubscribed_profile_blocks_reminder(self) -> None:
        from unittest.mock import patch

        tmp = Path(tempfile.mkdtemp(prefix="a3_skip_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(aws_csm_dir, handoff_sent=True, unsubscribed=True)
        _seed_grantee_json(tmp / "private", "alpha.example.test")
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        called: list[dict] = []

        def fake_send_email(**kwargs):
            called.append(kwargs)
            return MagicMock(message_id="should-not-happen")

        with patch(
            "MyCiteV2.instances._shared.portal_host.app._aws_peripheral"
        ) as peripheral:
            peripheral.send_email = fake_send_email
            app = create_app(config)
            client = app.test_client()
            resp = client.post(
                "/__fnd/email/admin/send-reminder",
                data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
                content_type="application/json",
            )
        # send_email must NOT have been invoked.
        self.assertEqual(called, [])
        self.assertGreaterEqual(resp.status_code, 400)


class DonationReceiptHtmlAltTests(unittest.TestCase):
    """A6 — donation receipt now multipart/mixed → multipart/alternative +
    PDF attachment, with A4 Reply-To default and A5 Message-ID/Date.
    """

    def _send_and_capture(self):
        from unittest.mock import patch
        from MyCiteV2.instances._shared.portal_host import app as portal_app

        tmp = Path(tempfile.mkdtemp(prefix="a6_donation_"))
        private_dir = tmp / "private"
        private_dir.mkdir()
        _seed_grantee_json(private_dir, "alpha.example.test")
        receipt = tmp / "receipt.pdf"
        receipt.write_bytes(b"%PDF-1.4\n% fake pdf\n")

        captured_raw: list[bytes] = []

        def fake_send_raw_email(**kwargs):
            captured_raw.append(kwargs["raw_message_bytes"])
            return MagicMock(message_id="msg-donation-1")

        with patch.object(portal_app, "_aws_peripheral") as peripheral:
            peripheral.send_raw_email = fake_send_raw_email
            status = portal_app._send_donation_receipt_email(
                private_dir=private_dir,
                domain="alpha.example.test",
                donor_email="donor@example.com",
                donor_name="Donor McDonor",
                amount="25.00",
                currency_code="USD",
                capture_id="CAPTURE-XYZ",
                receipt_path=receipt,
            )
        self.assertEqual(status, "sent")
        self.assertEqual(len(captured_raw), 1)
        return email.message_from_bytes(captured_raw[0])

    def test_message_is_multipart_mixed_with_alternative_and_attachment(self) -> None:
        msg = self._send_and_capture()
        self.assertEqual(msg.get_content_type(), "multipart/mixed")
        # walk the parts; expect a multipart/alternative wrapper +
        # text/plain + text/html + application/pdf attachment.
        content_types = [p.get_content_type() for p in msg.walk()]
        self.assertIn("multipart/alternative", content_types)
        self.assertIn("text/plain", content_types)
        self.assertIn("text/html", content_types)
        self.assertIn("application/pdf", content_types)

    def test_message_has_anchored_message_id_and_date(self) -> None:
        msg = self._send_and_capture()
        self.assertTrue(
            msg["Message-ID"].endswith("@alpha.example.test>"),
            f"Message-ID {msg['Message-ID']!r} not anchored to from-domain",
        )
        # We set Date via formatdate(usegmt=True) which produces "...GMT";
        # EmailMessage's serialization policy may normalize "GMT" to
        # "+0000" during as_bytes(). Both are RFC 2822 UTC. Accept either,
        # but reject "-0000" (the "unspecified offset" form spam filters
        # score lower) and any non-UTC offset.
        date_header = msg["Date"]
        self.assertTrue(
            date_header.endswith("GMT") or date_header.endswith("+0000"),
            f"Date {date_header!r} not in UTC form (must end with GMT or +0000)",
        )
        self.assertFalse(
            date_header.endswith("-0000"),
            f"Date {date_header!r} uses '-0000' unspecified-offset form",
        )

    def test_message_has_default_reply_to(self) -> None:
        msg = self._send_and_capture()
        # Seeded grantee did not set reply_to → A4 default applies.
        self.assertEqual(msg["Reply-To"], "reply-to@alpha.example.test")


if __name__ == "__main__":
    unittest.main()
