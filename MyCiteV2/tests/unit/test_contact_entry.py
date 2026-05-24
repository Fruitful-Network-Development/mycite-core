"""Unit tests for the canonical contact-entry normalizer.

Pins the row contract every contact writer now shares:
  * full field set with stable defaults ("hidden unused fields"),
  * empty patch value == no change (no blank-clobber),
  * subscribed kept unless explicitly set (no silent re-subscribe),
  * created_at preserved / updated_at stamped, subscribed_at on opt-in,
  * name <-> first/middle/last kept in sync.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.domain.contact_entry import (
    CONTACT_ENTRY_FIELDS,
    blank_contact_entry,
    canonical_contact_entry,
    split_legacy_name,
)

NOW = "2026-05-24T12:00:00+00:00"
EARLIER = "2026-01-01T00:00:00+00:00"


class CanonicalContactEntryTests(unittest.TestCase):
    def test_new_row_carries_full_field_set(self) -> None:
        row = canonical_contact_entry(patch={"email": "A@Example.TEST"}, now=NOW)
        # Every canonical field present.
        for field in CONTACT_ENTRY_FIELDS:
            self.assertIn(field, row)
        self.assertEqual(row["email"], "a@example.test")  # lowercased
        self.assertEqual(row["subscribed"], False)
        self.assertEqual(row["send_count"], 0)
        self.assertEqual(row["created_at"], NOW)
        self.assertEqual(row["updated_at"], NOW)
        # Connect-only + newsletter-only fields are present-but-empty.
        self.assertEqual(row["subject"], "")
        self.assertEqual(row["message"], "")
        self.assertEqual(row["organization"], "")

    def test_blank_entry_has_typed_defaults(self) -> None:
        row = blank_contact_entry()
        self.assertEqual(row["subscribed"], False)
        self.assertEqual(row["send_count"], 0)
        self.assertEqual(row["email"], "")

    def test_empty_patch_value_is_no_change(self) -> None:
        existing = canonical_contact_entry(
            patch={"email": "a@x.test", "phone": "216-555-1212", "zip": "44264"},
            now=EARLIER,
        )
        # Dashboard re-submits the whole form, blanking phone — must NOT clobber.
        row = canonical_contact_entry(
            existing=existing,
            patch={"email": "a@x.test", "phone": "", "zip": "44264"},
            now=NOW,
        )
        self.assertEqual(row["phone"], "216-555-1212")
        self.assertEqual(row["zip"], "44264")

    def test_subscribed_kept_unless_explicit(self) -> None:
        opted_out = canonical_contact_entry(
            patch={"email": "a@x.test", "subscribed": False}, now=EARLIER
        )
        self.assertFalse(opted_out["subscribed"])
        # An edit/add that omits subscribed must NOT resurrect the opt-out.
        edited = canonical_contact_entry(
            existing=opted_out, patch={"email": "a@x.test", "first_name": "Ann"}, now=NOW
        )
        self.assertFalse(edited["subscribed"])
        # Explicit True opts back in.
        resub = canonical_contact_entry(
            existing=opted_out, patch={"email": "a@x.test", "subscribed": True}, now=NOW
        )
        self.assertTrue(resub["subscribed"])

    def test_created_at_preserved_updated_at_stamped(self) -> None:
        existing = canonical_contact_entry(patch={"email": "a@x.test"}, now=EARLIER)
        row = canonical_contact_entry(
            existing=existing, patch={"email": "a@x.test", "phone": "1"}, now=NOW
        )
        self.assertEqual(row["created_at"], EARLIER)
        self.assertEqual(row["updated_at"], NOW)

    def test_subscribed_at_stamped_on_opt_in(self) -> None:
        row = canonical_contact_entry(
            patch={"email": "a@x.test", "subscribed": True}, now=NOW
        )
        self.assertEqual(row["subscribed_at"], NOW)
        # Not stamped when not subscribed.
        off = canonical_contact_entry(patch={"email": "b@x.test"}, now=NOW)
        self.assertEqual(off["subscribed_at"], "")

    def test_name_composed_from_parts(self) -> None:
        row = canonical_contact_entry(
            patch={
                "email": "a@x.test",
                "first_name": "Mary",
                "middle_name": "Anne",
                "last_name": "Zaun",
            },
            now=NOW,
        )
        self.assertEqual(row["name"], "Mary Anne Zaun")

    def test_legacy_single_name_auto_splits(self) -> None:
        row = canonical_contact_entry(
            patch={"email": "a@x.test", "name": "Adrienne Gordon"}, now=NOW
        )
        self.assertEqual(row["first_name"], "Adrienne")
        self.assertEqual(row["last_name"], "Gordon")

    def test_send_count_coerced_to_int(self) -> None:
        row = canonical_contact_entry(
            patch={"email": "a@x.test", "send_count": "3"}, now=NOW
        )
        self.assertEqual(row["send_count"], 3)
        # Bad value falls back to the carried/default value.
        bad = canonical_contact_entry(
            patch={"email": "a@x.test", "send_count": "oops"}, now=NOW
        )
        self.assertEqual(bad["send_count"], 0)

    def test_connect_message_persists(self) -> None:
        row = canonical_contact_entry(
            patch={
                "email": "a@x.test",
                "source": "connect_form",
                "subject": "Hello",
                "message": "Hi from the website.",
                "forward_status": "sent",
            },
            now=NOW,
        )
        self.assertEqual(row["subject"], "Hello")
        self.assertEqual(row["message"], "Hi from the website.")
        self.assertEqual(row["source"], "connect_form")


class SplitLegacyNameTests(unittest.TestCase):
    def test_split_variants(self) -> None:
        self.assertEqual(split_legacy_name(""), ("", "", ""))
        self.assertEqual(split_legacy_name("Cher"), ("Cher", "", ""))
        self.assertEqual(split_legacy_name("Ann Lee"), ("Ann", "", "Lee"))
        self.assertEqual(split_legacy_name("Mary Anne Zaun"), ("Mary", "Anne", "Zaun"))
        self.assertEqual(
            split_legacy_name("A B C D"), ("A", "B C", "D")
        )


if __name__ == "__main__":
    unittest.main()
