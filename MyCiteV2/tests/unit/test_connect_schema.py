"""Phase 17a — ConnectConfig + connect-form contact magnitudes.

The grantee profile gains an optional ``connect`` sub-config carrying
``forward_to_email``. The newsletter contact log gains three new
magnitudes — ``subject_ascii``, ``message_ascii``, ``forward_status``
— so a Connect-form submission lands inline next to the contact
entry with its full record. The mutation runtime gains a
``submit_connect_form`` operation that upserts the contact with
``subscribed=false, source=connect_form`` while preserving any
existing newsletter subscription.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
    run_datum_workbench_mutation_action,
)
from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
    MosDatumNewsletterContactLogAdapter,
)
from MyCiteV2.packages.core.grantee import ConnectConfig, GranteeProfile


class ConnectConfigSchemaTests(unittest.TestCase):
    def test_default_is_empty(self) -> None:
        c = ConnectConfig()
        self.assertEqual(c.forward_to_email, "")

    def test_accepts_valid_email(self) -> None:
        c = ConnectConfig(forward_to_email="dylan@fruitfulnetworkdevelopment.com")
        self.assertEqual(c.forward_to_email, "dylan@fruitfulnetworkdevelopment.com")

    def test_rejects_invalid_email(self) -> None:
        with self.assertRaises(ValueError):
            ConnectConfig(forward_to_email="not-an-email")

    def test_round_trip_via_to_dict_from_dict(self) -> None:
        c = ConnectConfig(forward_to_email="ops@example.test")
        self.assertEqual(
            ConnectConfig.from_dict(c.to_dict()).forward_to_email, "ops@example.test"
        )


class GranteeProfileWithConnectTests(unittest.TestCase):
    def test_grantee_profile_serializes_connect_when_set(self) -> None:
        gp = GranteeProfile(
            msn_id="alpha",
            connect=ConnectConfig(forward_to_email="contact@alpha.test"),
        )
        data = gp.to_dict()
        self.assertIn("connect", data)
        self.assertEqual(data["connect"]["forward_to_email"], "contact@alpha.test")

    def test_grantee_profile_omits_connect_when_none(self) -> None:
        # Default profile (no connect) must not include the key so
        # legacy grantee files stay byte-identical.
        gp = GranteeProfile(msn_id="alpha")
        self.assertNotIn("connect", gp.to_dict())

    def test_from_dict_hydrates_connect(self) -> None:
        gp = GranteeProfile.from_dict(
            {
                "msn_id": "alpha",
                "connect": {"forward_to_email": "contact@alpha.test"},
            }
        )
        self.assertIsNotNone(gp.connect)
        assert gp.connect is not None
        self.assertEqual(gp.connect.forward_to_email, "contact@alpha.test")


class ConnectMagnitudeRoundTripTests(unittest.TestCase):
    def test_subject_message_forward_status_persist(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="phase17a_connect_"))
        db = tmp / "authority.sqlite3"
        db.touch()
        adapter = MosDatumNewsletterContactLogAdapter(authority_db_file=db, tenant_id="fnd")
        adapter.save_contact_log(
            domain="example.test",
            payload={
                "domain": "example.test",
                "contacts": [
                    {
                        "email": "visitor@example.test",
                        "first_name": "Visitor",
                        "subject": "Question about turkeys",
                        "message": "When can I order one?",
                        "forward_status": "sent",
                        "subscribed": False,
                        "source": "connect_form",
                        "send_count": 0,
                        "last_newsletter_sent_at": "",
                    }
                ],
            },
        )
        row = adapter.load_contact_log(domain="example.test")["contacts"][0]
        self.assertEqual(row["subject"], "Question about turkeys")
        self.assertEqual(row["message"], "When can I order one?")
        self.assertEqual(row["forward_status"], "sent")
        self.assertEqual(row["source"], "connect_form")
        self.assertFalse(row["subscribed"])


class SubmitConnectFormOperationTests(unittest.TestCase):
    def _build(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase17a_submit_"))
        db = tmp / "authority.sqlite3"
        db.touch()
        return MosDatumNewsletterContactLogAdapter(authority_db_file=db, tenant_id="fnd"), db

    def test_inserts_new_contact_unsubscribed(self) -> None:
        adapter, db = self._build()
        envelope = run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "submit_connect_form",
                "domain": "example.test",
                "email": "visitor@example.test",
                "first_name": "Visitor",
                "last_name": "Test",
                "phone": "216-555-0001",
                "subject": "Hello",
                "message": "Just saying hi.",
                "forward_status": "sent",
            },
            authority_db_file=db,
            portal_instance_id="fnd",
        )
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["preview"]["forward_status"], "sent")
        row = adapter.load_contact_log(domain="example.test")["contacts"][0]
        self.assertFalse(row["subscribed"])
        self.assertEqual(row["source"], "connect_form")
        self.assertEqual(row["subject"], "Hello")
        self.assertEqual(row["message"], "Just saying hi.")
        self.assertEqual(row["forward_status"], "sent")
        self.assertEqual(row["first_name"], "Visitor")

    def test_preserves_existing_subscription(self) -> None:
        # A visitor who is already a newsletter subscriber and then
        # submits the Connect form keeps their subscribed=True state.
        adapter, db = self._build()
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "upsert_subscriber",
                "domain": "example.test",
                "email": "loyal@example.test",
                "first_name": "Loyal",
            },
            authority_db_file=db,
            portal_instance_id="fnd",
        )
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "submit_connect_form",
                "domain": "example.test",
                "email": "loyal@example.test",
                "first_name": "Loyal",
                "last_name": "Subscriber",
                "subject": "Question",
                "message": "Here's my question.",
                "forward_status": "sent",
            },
            authority_db_file=db,
            portal_instance_id="fnd",
        )
        row = adapter.load_contact_log(domain="example.test")["contacts"][0]
        self.assertTrue(row["subscribed"])  # still subscribed
        self.assertEqual(row["last_name"], "Subscriber")  # updated last_name
        self.assertEqual(row["subject"], "Question")
        # source was promoted to connect_form to reflect the latest
        # interaction.
        self.assertEqual(row["source"], "connect_form")


if __name__ == "__main__":
    unittest.main()
