"""Migration test: per-domain JSON contact logs -> per-entity YAML rosters.

Verifies on a temp fixture that:
  * contacts move into the entity leaflet (roster)
  * two domains owned by ONE entity (CVCC) merge into a single leaflet, each
    row tagged with its source domain
  * dispatch history stays in the JSON log
  * --apply backs up the JSON to *.bak and optionally clears its contacts[]
  * the migration is idempotent (re-running converges, no duplicate rows)
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml

from MyCiteV2.packages.adapters.filesystem.contact_leaflet import ContactLeafletStore
from MyCiteV2.scripts.migrate_contacts_json_to_yaml import run_migration

_NEWSLETTER_SUBPATH = ("utilities", "tools", "aws-csm", "newsletter")


class MigrateContactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.private_dir = Path(self.tmp.name)
        self.newsletter_root = self.private_dir.joinpath(*_NEWSLETTER_SUBPATH)
        self.newsletter_root.mkdir(parents=True)
        self.store = ContactLeafletStore(private_dir=self.private_dir)

    def _write_json(self, domain: str, contacts, dispatches=()):
        payload = {
            "schema": "mycite.service_tool.newsletter.contact_log.v3",
            "domain": domain,
            "contacts": list(contacts),
            "dispatches": list(dispatches),
        }
        (self.newsletter_root / f"newsletter.{domain}.contacts.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def test_dry_run_writes_nothing(self) -> None:
        self._write_json(
            "trappfamilyfarm.com", [{"email": "a@x.com", "subscribed": True}]
        )
        summary = run_migration(
            private_dir=self.private_dir,
            webapps_root=None,
            apply=False,
            clear_json_contacts=False,
        )
        self.assertFalse(summary["apply"])
        self.assertEqual(summary["entities"]["trapp_family_farm"]["contact_count"], 1)
        # Nothing on disk.
        self.assertFalse(self.store.leaflet_present("trapp_family_farm"))

    def test_apply_moves_roster_keeps_dispatches(self) -> None:
        self._write_json(
            "trappfamilyfarm.com",
            [{"email": "a@x.com", "subscribed": True, "send_count": 2}],
            dispatches=[{"dispatch_id": "d-1", "completed_at": "2026-05-10T00:00:00Z"}],
        )
        run_migration(
            private_dir=self.private_dir,
            webapps_root=None,
            apply=True,
            clear_json_contacts=True,
        )
        # Roster in YAML.
        roster = self.store.load_roster("trapp_family_farm")
        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["email"], "a@x.com")
        self.assertEqual(roster[0]["domain"], "trappfamilyfarm.com")

        # Dispatch history untouched in JSON; contacts cleared; backup written.
        src = self.newsletter_root / "newsletter.trappfamilyfarm.com.contacts.json"
        bak = src.with_suffix(src.suffix + ".bak")
        self.assertTrue(bak.exists())
        json_payload = json.loads(src.read_text(encoding="utf-8"))
        self.assertEqual(json_payload["contacts"], [])
        self.assertEqual(len(json_payload["dispatches"]), 1)
        # Backup retains the original contacts.
        bak_payload = json.loads(bak.read_text(encoding="utf-8"))
        self.assertEqual(len(bak_payload["contacts"]), 1)

    def test_two_domains_merge_into_one_entity(self) -> None:
        self._write_json(
            "cuyahogavalleycountrysideconservancy.org",
            [{"email": "a@x.com", "subscribed": True}],
        )
        self._write_json("cvccboard.org", [{"email": "b@x.com", "subscribed": False}])
        run_migration(
            private_dir=self.private_dir,
            webapps_root=None,
            apply=True,
            clear_json_contacts=False,
        )
        roster = self.store.load_roster("cuyahoga_valley_countryside_conservancy_inc")
        emails = {r["email"]: r["domain"] for r in roster}
        self.assertEqual(
            emails,
            {
                "a@x.com": "cuyahogavalleycountrysideconservancy.org",
                "b@x.com": "cvccboard.org",
            },
        )

    def test_idempotent_apply(self) -> None:
        self._write_json(
            "trappfamilyfarm.com", [{"email": "a@x.com", "updated_at": "2026-01-01"}]
        )
        for _ in range(2):
            run_migration(
                private_dir=self.private_dir,
                webapps_root=None,
                apply=True,
                clear_json_contacts=False,
            )
        roster = self.store.load_roster("trapp_family_farm")
        self.assertEqual(len(roster), 1)  # no duplicate

    def test_newer_updated_at_wins_on_merge(self) -> None:
        # Seed the leaflet with an old row, then migrate a newer one.
        self.store.save_roster(
            "trapp_family_farm",
            [{"email": "a@x.com", "first_name": "Old", "updated_at": "2026-01-01",
              "domain": "trappfamilyfarm.com"}],
        )
        self._write_json(
            "trappfamilyfarm.com",
            [{"email": "a@x.com", "first_name": "New", "updated_at": "2026-06-01"}],
        )
        run_migration(
            private_dir=self.private_dir,
            webapps_root=None,
            apply=True,
            clear_json_contacts=False,
        )
        roster = self.store.load_roster("trapp_family_farm")
        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["first_name"], "New")

    def test_leaflet_is_valid_yaml_with_schema(self) -> None:
        self._write_json("brockspressurewashing.com", [{"email": "a@x.com"}])
        run_migration(
            private_dir=self.private_dir,
            webapps_root=None,
            apply=True,
            clear_json_contacts=False,
        )
        path = self.store.leaflet_path("brocks_pressure_washing")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "mycite.site_core.contact_record.v1")


if __name__ == "__main__":
    unittest.main()
