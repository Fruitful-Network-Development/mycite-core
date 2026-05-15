"""Phase 16a — phone / zip / signup_date persistence + edit_subscriber.

The newsletter contact log now persists three additional contact-detail
magnitudes: ``phone_ascii``, ``zip_ascii``, and ``signup_date``. The
mutation runtime gains an ``edit_subscriber`` operation for the
inline row edit UX.
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


def _build_adapter() -> tuple[MosDatumNewsletterContactLogAdapter, Path]:
    tmp = Path(tempfile.mkdtemp(prefix="phase16a_extended_"))
    authority_db = tmp / "authority.sqlite3"
    authority_db.touch()
    adapter = MosDatumNewsletterContactLogAdapter(
        authority_db_file=authority_db, tenant_id="fnd"
    )
    return adapter, authority_db


class ExtendedFieldsRoundTripTests(unittest.TestCase):
    def test_phone_zip_signup_date_survive_save_load(self) -> None:
        adapter, _ = _build_adapter()
        adapter.save_contact_log(
            domain="example.test",
            payload={
                "domain": "example.test",
                "contacts": [
                    {
                        "email": "mary@example.test",
                        "first_name": "Mary",
                        "last_name": "Zaun",
                        "phone": "+1-216-555-0123",
                        "zip": "44264",
                        "signup_date": "2026-05-15",
                        "subscribed": True,
                        "source": "website_signup",
                        "send_count": 0,
                        "last_newsletter_sent_at": "",
                    }
                ],
            },
        )
        loaded = adapter.load_contact_log(domain="example.test")
        row = loaded["contacts"][0]
        self.assertEqual(row["phone"], "+1-216-555-0123")
        self.assertEqual(row["zip"], "44264")
        self.assertEqual(row["signup_date"], "2026-05-15")

    def test_signup_date_falls_back_to_created_at_date_prefix(self) -> None:
        adapter, _ = _build_adapter()
        adapter.save_contact_log(
            domain="example.test",
            payload={
                "domain": "example.test",
                "contacts": [
                    {
                        "email": "legacy@example.test",
                        "name": "Legacy User",
                        "subscribed": True,
                        "source": "csv_import",
                        "send_count": 0,
                        "last_newsletter_sent_at": "",
                        # No signup_date in payload, but created_at can
                        # be projected to a date string by the adapter.
                        "created_at": "2024-11-03T18:22:00+00:00",
                    }
                ],
            },
        )
        row = adapter.load_contact_log(domain="example.test")["contacts"][0]
        self.assertEqual(row["signup_date"], "2024-11-03")


class UpsertSubscriberAcceptsExtendedFieldsTests(unittest.TestCase):
    def test_upsert_persists_phone_zip(self) -> None:
        adapter, authority_db = _build_adapter()
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "upsert_subscriber",
                "domain": "example.test",
                "email": "mary@example.test",
                "first_name": "Mary",
                "last_name": "Zaun",
                "phone": "216-555-0123",
                "zip": "44264",
            },
            authority_db_file=authority_db,
            portal_instance_id="fnd",
        )
        row = adapter.load_contact_log(domain="example.test")["contacts"][0]
        self.assertEqual(row["phone"], "216-555-0123")
        self.assertEqual(row["zip"], "44264")
        # signup_date defaulted to today (we just check the format).
        self.assertRegex(row["signup_date"], r"^\d{4}-\d{2}-\d{2}$")


class EditSubscriberOperationTests(unittest.TestCase):
    def _seed_one(self):
        adapter, authority_db = _build_adapter()
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "upsert_subscriber",
                "domain": "example.test",
                "email": "mary@example.test",
                "first_name": "Mary",
                "last_name": "Zaun",
                "phone": "old-phone",
            },
            authority_db_file=authority_db,
            portal_instance_id="fnd",
        )
        return adapter, authority_db

    def test_edit_updates_named_fields_only(self) -> None:
        adapter, authority_db = self._seed_one()
        envelope = run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "edit_subscriber",
                "domain": "example.test",
                "email": "mary@example.test",
                "phone": "new-phone-555",
                "zip": "44264",
            },
            authority_db_file=authority_db,
            portal_instance_id="fnd",
        )
        self.assertTrue(envelope["ok"])
        preview = envelope["preview"]
        self.assertEqual(set(preview["updated_fields"]), {"phone", "zip"})
        row = adapter.load_contact_log(domain="example.test")["contacts"][0]
        self.assertEqual(row["phone"], "new-phone-555")
        self.assertEqual(row["zip"], "44264")
        # Untouched fields preserved.
        self.assertEqual(row["first_name"], "Mary")
        self.assertEqual(row["last_name"], "Zaun")
        self.assertTrue(row["subscribed"])  # edit must not touch subscription state

    def test_edit_recomposes_name_on_first_last_change(self) -> None:
        adapter, authority_db = self._seed_one()
        run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "edit_subscriber",
                "domain": "example.test",
                "email": "mary@example.test",
                "first_name": "Marigold",
                "last_name": "Zaun",
            },
            authority_db_file=authority_db,
            portal_instance_id="fnd",
        )
        row = adapter.load_contact_log(domain="example.test")["contacts"][0]
        self.assertEqual(row["first_name"], "Marigold")
        self.assertEqual(row["name"], "Marigold Zaun")

    def test_edit_unknown_email_envelope_carries_contact_not_found(self) -> None:
        # The inner ValueError("contact_not_found") is wrapped by the
        # mutation runtime into the envelope's error.message rather
        # than raised. The /__fnd/newsletter/admin/edit route inspects
        # that message and maps to 404.
        _, authority_db = self._seed_one()
        envelope = run_datum_workbench_mutation_action(
            "apply",
            {
                "target_authority": "aws_csm_newsletter_contact_log",
                "operation": "edit_subscriber",
                "domain": "example.test",
                "email": "ghost@example.test",
                "phone": "555",
            },
            authority_db_file=authority_db,
            portal_instance_id="fnd",
        )
        self.assertFalse(envelope["ok"])
        self.assertIn("contact_not_found", envelope["error"]["message"])


if __name__ == "__main__":
    unittest.main()
