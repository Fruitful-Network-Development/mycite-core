"""Tests for MosDatumNewsletterContactLogAdapter + composite delegation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
    V2_SCHEMA,
    CompositeAwsCsmNewsletterStateAdapter,
    MosDatumNewsletterContactLogAdapter,
)


def _payload_with_contacts(contacts: list[dict]) -> dict:
    return {
        "schema": V2_SCHEMA,
        "domain": "example.com",
        "msn_id": "test-msn",
        "contacts": contacts,
        "dispatches": [],
    }


class MosAdapterRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "mos.sqlite3"
        self.adapter = MosDatumNewsletterContactLogAdapter(
            authority_db_file=self.db_path,
            tenant_id="tenant",
            msn_id="test-msn",
        )

    def test_load_returns_empty_when_doc_missing(self):
        result = self.adapter.load_contact_log(domain="example.com")
        self.assertEqual(result, {})

    def test_save_then_load_round_trips_contacts(self):
        payload = _payload_with_contacts(
            [
                {
                    "email": "Alice@Example.com",
                    "name": "Alice",
                    "subscribed": True,
                    "source": "signup",
                    "send_count": 0,
                    "last_newsletter_sent_at": "",
                },
                {
                    "email": "bob@example.com",
                    "name": "",
                    "subscribed": False,
                    "source": "unsubscribe_link",
                    "send_count": 3,
                    "last_newsletter_sent_at": "2026-04-01T12:00:00Z",
                },
            ]
        )
        self.adapter.save_contact_log(domain="example.com", payload=payload)
        loaded = self.adapter.load_contact_log(domain="example.com")
        self.assertEqual(loaded["domain"], "example.com")
        self.assertEqual(loaded["schema"], V2_SCHEMA)
        contacts = sorted(loaded["contacts"], key=lambda c: c["email"])
        self.assertEqual([c["email"] for c in contacts], ["alice@example.com", "bob@example.com"])
        # Bacillete fields are populated by save
        alice = next(c for c in contacts if c["email"] == "alice@example.com")
        self.assertTrue(alice["email_confirmed"])
        self.assertTrue(alice["name_confirmed"])
        self.assertNotEqual(alice["email_binary"], "")
        self.assertEqual(alice["subscribed"], True)
        bob = next(c for c in contacts if c["email"] == "bob@example.com")
        self.assertEqual(bob["subscribed"], False)
        self.assertEqual(bob["send_count"], 3)
        # Empty name → not confirmed
        self.assertFalse(bob["name_confirmed"])

    def test_save_advances_version_hash(self):
        self.adapter.save_contact_log(
            domain="example.com",
            payload=_payload_with_contacts([
                {"email": "a@b.com", "name": "A", "subscribed": True, "source": "s",
                 "send_count": 0, "last_newsletter_sent_at": ""},
            ]),
        )
        # Find document_id after first save
        first_doc = self.adapter._find_document(domain="example.com")  # type: ignore[attr-defined]
        self.assertIsNotNone(first_doc)
        first_id = first_doc.document_id

        self.adapter.save_contact_log(
            domain="example.com",
            payload=_payload_with_contacts([
                {"email": "a@b.com", "name": "A", "subscribed": True, "source": "s",
                 "send_count": 0, "last_newsletter_sent_at": ""},
                {"email": "c@d.com", "name": "C", "subscribed": True, "source": "s",
                 "send_count": 0, "last_newsletter_sent_at": ""},
            ]),
        )
        second_doc = self.adapter._find_document(domain="example.com")  # type: ignore[attr-defined]
        self.assertIsNotNone(second_doc)
        self.assertNotEqual(first_id, second_doc.document_id)
        # The catalog should hold only ONE document for the canonical
        # name (the prior one is replaced).
        from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
        from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
        store = SqliteSystemDatumStoreAdapter(self.db_path)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id="tenant")
        )
        matching = [
            d for d in catalog.documents
            if d.canonical_name == "fnd_newsletter_contact_log_example_com"
        ]
        self.assertEqual(len(matching), 1)


class CompositeDelegationTests(unittest.TestCase):
    def test_composite_delegates_non_contact_log_to_filesystem(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "mos.sqlite3"
            composite = CompositeAwsCsmNewsletterStateAdapter(
                private_dir=tmp_path,
                authority_db_file=db_path,
                tenant_id="tenant",
                msn_id="test-msn",
            )
            # runtime_secret_seed is filesystem-only — should return ""
            # for an empty tmp dir without raising.
            self.assertEqual(composite.runtime_secret_seed(secret_kind="signing_secret"), "")

    def test_composite_routes_contact_log_to_mos(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "mos.sqlite3"
            composite = CompositeAwsCsmNewsletterStateAdapter(
                private_dir=tmp_path,
                authority_db_file=db_path,
                tenant_id="tenant",
                msn_id="test-msn",
            )
            composite.save_contact_log(
                domain="example.com",
                payload=_payload_with_contacts([
                    {"email": "x@y.com", "name": "X", "subscribed": True, "source": "s",
                     "send_count": 0, "last_newsletter_sent_at": ""},
                ]),
            )
            loaded = composite.load_contact_log(domain="example.com")
            self.assertEqual(len(loaded["contacts"]), 1)
            self.assertEqual(loaded["contacts"][0]["email"], "x@y.com")


if __name__ == "__main__":
    unittest.main()
