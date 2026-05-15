"""Phase 15b — Newsletter contact log name-field split.

The MOS newsletter contact log now persists first / middle / last
name fields alongside the legacy composed ``name_ascii``. This is
the unit-test pin for:

  * ``_split_legacy_name`` — tokenizes a single legacy name into
    first/middle/last.
  * ``_magnitudes_from_contact`` — accepts split fields, auto-splits
    a legacy ``name``, always populates the composed ``name_ascii``
    + the bacillete-encoded forms.
  * ``load_contact_log`` round-trip — split fields persisted via
    ``save_contact_log`` come back out of ``load_contact_log``.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
    MosDatumNewsletterContactLogAdapter,
)


class SplitLegacyNameTests(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(
            MosDatumNewsletterContactLogAdapter._split_legacy_name(""), ("", "", "")
        )

    def test_single_token(self) -> None:
        self.assertEqual(
            MosDatumNewsletterContactLogAdapter._split_legacy_name("Dylan"),
            ("Dylan", "", ""),
        )

    def test_two_tokens(self) -> None:
        self.assertEqual(
            MosDatumNewsletterContactLogAdapter._split_legacy_name("Mary Zaun"),
            ("Mary", "", "Zaun"),
        )

    def test_three_tokens(self) -> None:
        self.assertEqual(
            MosDatumNewsletterContactLogAdapter._split_legacy_name("Adrienne Lyn Gordon"),
            ("Adrienne", "Lyn", "Gordon"),
        )

    def test_extra_whitespace(self) -> None:
        self.assertEqual(
            MosDatumNewsletterContactLogAdapter._split_legacy_name("  Mary   Zaun  "),
            ("Mary", "", "Zaun"),
        )

    def test_four_tokens_joins_middle(self) -> None:
        # First and last anchor the ends; everything between joins into middle.
        self.assertEqual(
            MosDatumNewsletterContactLogAdapter._split_legacy_name("Mary Anne Jane Zaun"),
            ("Mary", "Anne Jane", "Zaun"),
        )


class MagnitudesFromContactTests(unittest.TestCase):
    def test_accepts_split_fields(self) -> None:
        mags = MosDatumNewsletterContactLogAdapter._magnitudes_from_contact(
            {
                "email": "user@example.test",
                "first_name": "Mary",
                "middle_name": "Anne",
                "last_name": "Zaun",
                "subscribed": True,
                "source": "csv_import",
                "send_count": 0,
                "last_newsletter_sent_at": "",
            }
        )
        self.assertEqual(mags["first_name_ascii"], "Mary")
        self.assertEqual(mags["middle_name_ascii"], "Anne")
        self.assertEqual(mags["last_name_ascii"], "Zaun")
        # name_ascii composed from the split parts.
        self.assertEqual(mags["name_ascii"], "Mary Anne Zaun")

    def test_auto_splits_legacy_single_name(self) -> None:
        mags = MosDatumNewsletterContactLogAdapter._magnitudes_from_contact(
            {
                "email": "user@example.test",
                "name": "Dylan",
                "subscribed": True,
                "source": "website_signup",
                "send_count": 0,
                "last_newsletter_sent_at": "",
            }
        )
        self.assertEqual(mags["first_name_ascii"], "Dylan")
        self.assertEqual(mags["middle_name_ascii"], "")
        self.assertEqual(mags["last_name_ascii"], "")
        self.assertEqual(mags["name_ascii"], "Dylan")

    def test_split_fields_win_over_legacy_name(self) -> None:
        # When both supplied, the split fields take precedence — legacy
        # ``name`` is dropped on the floor.
        mags = MosDatumNewsletterContactLogAdapter._magnitudes_from_contact(
            {
                "email": "user@example.test",
                "first_name": "Mary",
                "last_name": "Zaun",
                "name": "should-be-ignored",
                "subscribed": True,
                "source": "csv_import",
                "send_count": 0,
                "last_newsletter_sent_at": "",
            }
        )
        self.assertEqual(mags["first_name_ascii"], "Mary")
        self.assertEqual(mags["last_name_ascii"], "Zaun")
        self.assertEqual(mags["name_ascii"], "Mary Zaun")

    def test_missing_name_yields_empty_strings(self) -> None:
        mags = MosDatumNewsletterContactLogAdapter._magnitudes_from_contact(
            {
                "email": "user@example.test",
                "subscribed": True,
                "source": "website_signup",
                "send_count": 0,
                "last_newsletter_sent_at": "",
            }
        )
        self.assertEqual(mags["first_name_ascii"], "")
        self.assertEqual(mags["middle_name_ascii"], "")
        self.assertEqual(mags["last_name_ascii"], "")
        self.assertEqual(mags["name_ascii"], "")


class RoundTripTests(unittest.TestCase):
    def test_split_fields_survive_save_then_load(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="phase15b_roundtrip_"))
        authority_db = tmp / "authority.sqlite3"
        authority_db.touch()
        adapter = MosDatumNewsletterContactLogAdapter(
            authority_db_file=authority_db, tenant_id="fnd"
        )
        adapter.save_contact_log(
            domain="example.test",
            payload={
                "domain": "example.test",
                "contacts": [
                    {
                        "email": "mary.zaun@example.test",
                        "first_name": "Mary",
                        "middle_name": "Anne",
                        "last_name": "Zaun",
                        "subscribed": True,
                        "source": "csv_import",
                        "send_count": 0,
                        "last_newsletter_sent_at": "",
                    },
                    {
                        "email": "dylan@example.test",
                        # Legacy single-name contact — adapter should auto-split.
                        "name": "Dylan",
                        "subscribed": True,
                        "source": "website_signup",
                        "send_count": 0,
                        "last_newsletter_sent_at": "",
                    },
                ],
            },
        )
        loaded = adapter.load_contact_log(domain="example.test")
        by_email = {c["email"]: c for c in loaded["contacts"]}

        mary = by_email["mary.zaun@example.test"]
        self.assertEqual(mary["first_name"], "Mary")
        self.assertEqual(mary["middle_name"], "Anne")
        self.assertEqual(mary["last_name"], "Zaun")
        self.assertEqual(mary["name"], "Mary Anne Zaun")

        dylan = by_email["dylan@example.test"]
        self.assertEqual(dylan["first_name"], "Dylan")
        self.assertEqual(dylan["middle_name"], "")
        self.assertEqual(dylan["last_name"], "")
        self.assertEqual(dylan["name"], "Dylan")


if __name__ == "__main__":
    unittest.main()
