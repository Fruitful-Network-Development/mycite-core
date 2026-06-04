"""Round-trip tests for the per-entity YAML contact-leaflet roster store.

Covers upsert / edit / unsubscribe / set_subscription on a temp dir, plus the
domain->entity resolution and the atomic-write contract (a torn write must
never leave the roster empty).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem.contact_leaflet import (
    CONTACT_RECORD_SCHEMA,
    ContactLeafletStore,
    entity_for_domain,
)

ENTITY = "trapp_family_farm"


class ContactLeafletRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Flat layout -> contacts anchored under private_dir (test/dev fallback).
        self.private_dir = Path(self.tmp.name)
        self.store = ContactLeafletStore(private_dir=self.private_dir)

    def test_empty_roster_when_absent(self) -> None:
        self.assertEqual(self.store.load_roster(ENTITY), [])
        self.assertFalse(self.store.leaflet_present(ENTITY))

    def test_upsert_inserts_then_replaces_by_email(self) -> None:
        self.store.upsert_contact(
            ENTITY, {"email": "Jo@Example.com", "first_name": "Jo", "subscribed": True}
        )
        roster = self.store.load_roster(ENTITY)
        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["email"], "jo@example.com")  # lowercased
        self.assertTrue(roster[0]["subscribed"])
        self.assertTrue(self.store.leaflet_present(ENTITY))

        # Upsert by same email (case-insensitive) replaces, not appends.
        self.store.upsert_contact(
            ENTITY, {"email": "jo@example.com", "first_name": "Joanne"}
        )
        roster = self.store.load_roster(ENTITY)
        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["first_name"], "Joanne")

    def test_edit_merges_and_returns_none_when_absent(self) -> None:
        self.store.upsert_contact(ENTITY, {"email": "a@x.com", "phone": "111"})
        out = self.store.edit_contact(ENTITY, "a@x.com", {"phone": "222", "zip": "44106"})
        self.assertIsNotNone(out)
        self.assertEqual(out["phone"], "222")
        self.assertEqual(out["zip"], "44106")
        self.assertIsNone(self.store.edit_contact(ENTITY, "missing@x.com", {"zip": "1"}))

    def test_mark_unsubscribed_and_set_subscription(self) -> None:
        self.store.upsert_contact(ENTITY, {"email": "a@x.com", "subscribed": True})
        self.assertTrue(self.store.mark_unsubscribed(ENTITY, "a@x.com", now="2026-06-04T00:00:00Z"))
        roster = self.store.load_roster(ENTITY)
        self.assertFalse(roster[0]["subscribed"])
        self.assertEqual(roster[0]["unsubscribed_at"], "2026-06-04T00:00:00Z")

        self.assertTrue(self.store.set_subscription(ENTITY, "a@x.com", True))
        self.assertTrue(self.store.load_roster(ENTITY)[0]["subscribed"])
        # No match -> False, roster untouched.
        self.assertFalse(self.store.set_subscription(ENTITY, "nobody@x.com", True))

    def test_save_roster_writes_schema_and_entity(self) -> None:
        import yaml

        self.store.save_roster(ENTITY, [{"email": "a@x.com"}])
        payload = yaml.safe_load(self.store.leaflet_path(ENTITY).read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], CONTACT_RECORD_SCHEMA)
        self.assertEqual(payload["entity"], ENTITY)
        self.assertEqual(payload["contacts"][0]["email"], "a@x.com")

    def test_atomic_write_leaves_no_temp_files(self) -> None:
        self.store.upsert_contact(ENTITY, {"email": "a@x.com"})
        leftovers = list(self.store.contacts_dir.glob(".tmp-*"))
        self.assertEqual(leftovers, [])

    def test_entity_resolution(self) -> None:
        self.assertEqual(
            entity_for_domain("fruitfulnetworkdevelopment.com"),
            "fruitful_network_development_llc",
        )
        # CVCC owns two domains -> one entity.
        self.assertEqual(
            entity_for_domain("cuyahogavalleycountrysideconservancy.org"),
            entity_for_domain("cvccboard.org"),
        )
        # Unknown domain -> deterministic derived slug (never an empty key).
        self.assertEqual(entity_for_domain("example.com"), "example_com")


if __name__ == "__main__":
    unittest.main()
