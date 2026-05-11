"""Tests for SqliteMosAwsCsmNewsletterStateAdapter."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql import SqliteMosAwsCsmNewsletterStateAdapter
from MyCiteV2.packages.ports.aws_csm_newsletter import (
    AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
    AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
)


def _adapter(tmp_dir: str) -> SqliteMosAwsCsmNewsletterStateAdapter:
    return SqliteMosAwsCsmNewsletterStateAdapter(
        Path(tmp_dir) / "newsletter.sqlite3",
        clock=lambda: 1770000000000,
    )


def _make_contact_log(domain: str, contacts: list[dict]) -> dict:
    return {
        "schema": AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
        "domain": domain,
        "contacts": contacts,
        "dispatches": [],
    }


class SqliteNewsletterContactLogTests(unittest.TestCase):
    def test_load_returns_empty_when_no_record(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            result = adapter.load_contact_log(domain="example.com")
            self.assertEqual(result, {})

    def test_save_and_load_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            log = _make_contact_log("example.com", [
                {"email": "a@example.com", "subscribed": True, "source": "signup", "last_newsletter_sent_at": "", "send_count": 0},
            ])
            adapter.save_contact_log(domain="example.com", payload=log)
            loaded = adapter.load_contact_log(domain="example.com")
            self.assertEqual(loaded["domain"], "example.com")
            self.assertEqual(len(loaded["contacts"]), 1)
            self.assertEqual(loaded["contacts"][0]["email"], "a@example.com")
            self.assertEqual(loaded["schema"], AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA)

    def test_subscribe_pattern(self) -> None:
        """Subscribe: upsert one contact into the contact list."""
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            # Initial empty log
            adapter.save_contact_log(domain="example.com", payload=_make_contact_log("example.com", []))

            # Subscribe
            log = adapter.load_contact_log(domain="example.com")
            contacts = list(log.get("contacts") or [])
            contacts.append({"email": "new@example.com", "subscribed": True, "source": "web", "last_newsletter_sent_at": "", "send_count": 0})
            log["contacts"] = contacts
            adapter.save_contact_log(domain="example.com", payload=log)

            loaded = adapter.load_contact_log(domain="example.com")
            self.assertEqual(len(loaded["contacts"]), 1)
            self.assertTrue(loaded["contacts"][0]["subscribed"])

    def test_unsubscribe_pattern(self) -> None:
        """Unsubscribe: set subscribed=False for a matching contact."""
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            log = _make_contact_log("example.com", [
                {"email": "user@example.com", "subscribed": True, "source": "web", "last_newsletter_sent_at": "", "send_count": 2},
            ])
            adapter.save_contact_log(domain="example.com", payload=log)

            # Unsubscribe
            loaded = adapter.load_contact_log(domain="example.com")
            for contact in loaded.get("contacts", []):
                if contact.get("email") == "user@example.com":
                    contact["subscribed"] = False
            adapter.save_contact_log(domain="example.com", payload=loaded)

            result = adapter.load_contact_log(domain="example.com")
            self.assertFalse(result["contacts"][0]["subscribed"])

    def test_dispatch_result_pattern(self) -> None:
        """Dispatch result: add dispatch record + update contact's last_sent field."""
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            log = _make_contact_log("example.com", [
                {"email": "sub@example.com", "subscribed": True, "source": "web", "last_newsletter_sent_at": "", "send_count": 0},
            ])
            adapter.save_contact_log(domain="example.com", payload=log)

            # Dispatch result
            loaded = adapter.load_contact_log(domain="example.com")
            dispatches = list(loaded.get("dispatches") or [])
            dispatches.append({"dispatch_id": "d001", "sent_at": "2026-05-01T12:00:00Z", "recipient_count": 1})
            loaded["dispatches"] = dispatches
            for contact in loaded.get("contacts", []):
                if contact.get("subscribed"):
                    contact["last_newsletter_sent_at"] = "2026-05-01T12:00:00Z"
                    contact["send_count"] = int(contact.get("send_count") or 0) + 1
            adapter.save_contact_log(domain="example.com", payload=loaded)

            result = adapter.load_contact_log(domain="example.com")
            self.assertEqual(len(result["dispatches"]), 1)
            self.assertEqual(result["contacts"][0]["send_count"], 1)
            self.assertEqual(result["contacts"][0]["last_newsletter_sent_at"], "2026-05-01T12:00:00Z")

    def test_domain_is_normalized_to_lowercase(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            log = _make_contact_log("EXAMPLE.COM", [])
            adapter.save_contact_log(domain="EXAMPLE.COM", payload=log)
            result = adapter.load_contact_log(domain="example.com")
            self.assertEqual(result["domain"], "example.com")

    def test_overwrite_existing_log(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            adapter.save_contact_log(domain="example.com", payload=_make_contact_log("example.com", []))
            adapter.save_contact_log(domain="example.com", payload=_make_contact_log("example.com", [
                {"email": "x@example.com", "subscribed": True, "source": "web", "last_newsletter_sent_at": "", "send_count": 0},
            ]))
            result = adapter.load_contact_log(domain="example.com")
            self.assertEqual(len(result["contacts"]), 1)

    def test_dispatches_capped_at_twenty(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            log = _make_contact_log("example.com", [])
            log["dispatches"] = [{"dispatch_id": str(i)} for i in range(25)]
            adapter.save_contact_log(domain="example.com", payload=log)
            result = adapter.load_contact_log(domain="example.com")
            self.assertEqual(len(result["dispatches"]), 20)


class SqliteNewsletterProfileTests(unittest.TestCase):
    def test_load_returns_empty_when_no_profile(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            result = adapter.load_profile(domain="example.com")
            self.assertEqual(result, {})

    def test_save_and_load_profile_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            profile = {
                "schema": AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
                "domain": "example.com",
                "selected_sender_address": "info@example.com",
            }
            adapter.save_profile(domain="example.com", payload=profile)
            loaded = adapter.load_profile(domain="example.com")
            self.assertEqual(loaded["domain"], "example.com")
            self.assertEqual(loaded["selected_sender_address"], "info@example.com")
            self.assertEqual(loaded["schema"], AWS_CSM_NEWSLETTER_PROFILE_SCHEMA)


class SqliteNewsletterDomainListTests(unittest.TestCase):
    def test_list_domains_returns_all_known_domains(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            adapter.save_contact_log(domain="alpha.com", payload=_make_contact_log("alpha.com", []))
            adapter.save_contact_log(domain="beta.com", payload=_make_contact_log("beta.com", []))
            adapter.save_profile(domain="gamma.com", payload={
                "schema": AWS_CSM_NEWSLETTER_PROFILE_SCHEMA, "domain": "gamma.com"
            })
            domains = adapter.list_newsletter_domains()
            self.assertIn("alpha.com", domains)
            self.assertIn("beta.com", domains)
            self.assertIn("gamma.com", domains)

    def test_list_domains_empty_when_no_records(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            self.assertEqual(adapter.list_newsletter_domains(), [])


class SqliteNewsletterNotImplementedTests(unittest.TestCase):
    def test_list_verified_author_profiles_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            with self.assertRaises(NotImplementedError):
                adapter.list_verified_author_profiles(domain="example.com")

    def test_runtime_secret_seed_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            adapter = _adapter(tmp)
            with self.assertRaises(NotImplementedError):
                adapter.runtime_secret_seed(secret_kind="signing_secret")


if __name__ == "__main__":
    unittest.main()
