"""Integration tests for the generic events backend + routes.

Covers:
  * the ``events`` module CRUD + aggregation round-trip against a temp
    events gallery (save -> list -> analytics -> delete), asserting the
    leaflet is written with the right name + schema;
  * the Flask ``/__fnd/events/*`` routes via ``app.test_client()`` with a
    grantee scoped to a client;
  * the legacy ``/__fnd/bpw-jobs/*`` aliases still respond;
  * the bpw_jobs shim's pure aggregators match the events module;
  * the migration script (dry-run prints, --apply writes correctly-named
    leaflets) over a temp fixture dir.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
YAML_AVAILABLE = importlib.util.find_spec("yaml") is not None

from MyCiteV2.instances._shared.runtime.utilities_extensions import events as ev

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


def _sample_payload(name: str = "Dave Atch", date: str = "2026-04-14",
                    status: str = "completed", total: float = 100,
                    tag: str = "house_wash") -> dict:
    """A reconciled flat-envelope payload (top-level id/date/status/etc.)
    that still carries the nested job-kind extras the BPW analytics read.
    Mirrors what the dashboard's flat form POSTs, plus the nested
    customer/home/tags/pricing a BPW-migrated record retains."""
    return {
        "date": date,
        "status": status,
        "location": "123 Main St, Hudson",
        "customer": {"name": name, "phone": "(216) 543-2703",
                     "lead_source": "repeat_customer", "is_repeat": True},
        "home": {"house_sqft": 2211},
        "tags": [{"type": tag, "coverage": "2_sides", "price": 0}],
        "pricing": {"total": total, "paid": True, "method": "venmo"},
        "notes": "side of house",
    }


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestEventsModule(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="events_mod_"))
        self.webapps = self.root / "webapps"
        self.webapps.mkdir(parents=True, exist_ok=True)

    def test_save_list_analytics_delete_roundtrip(self) -> None:
        client = "brocks_pressure_washing"
        saved = ev.save_event(_sample_payload(), webapps_root=self.webapps, client=client)

        # Leaflet written under the canonical name + correct schema.
        gallery = ev.events_root(self.webapps)
        self.assertTrue(gallery.is_dir())
        fname = saved["_source_file"]
        self.assertEqual(
            fname, "2026-04-14.event-job.brocks_pressure_washing.dave.atch.yaml"
        )
        leaflet_path = gallery / fname
        self.assertTrue(leaflet_path.exists())
        import yaml
        on_disk = yaml.safe_load(leaflet_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["schema"], ev.EVENT_SCHEMA)
        self.assertEqual(on_disk["event_kind"], "job")
        self.assertEqual(on_disk["client"], client)
        self.assertEqual(on_disk["customer"]["name"], "Dave Atch")
        # Generic envelope is promoted to the top level.
        event_id = on_disk["id"]
        self.assertTrue(event_id)
        self.assertEqual(on_disk["date"], "2026-04-14")
        self.assertEqual(on_disk["status"], "completed")
        self.assertEqual(on_disk["location"], "123 Main St, Hudson")
        self.assertNotIn("job", on_disk)

        # list scoped to the client returns the row.
        rows = ev.list_events(self.webapps, client=client)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], event_id)
        self.assertEqual(rows[0]["date"], "2026-04-14")
        self.assertEqual(rows[0]["status"], "completed")

        # A different client sees nothing.
        self.assertEqual(ev.list_events(self.webapps, client="other_co"), [])

        # analytics reflects the completed job.
        analytics = ev.events_analytics(self.webapps, client=client)
        self.assertEqual(analytics["status_breakdown"], [{"key": "completed", "count": 1}])
        self.assertEqual(analytics["repeat_customers"]["count"], 1)
        self.assertEqual(len(analytics["revenue_by_month"]), 1)
        self.assertEqual(analytics["revenue_by_month"][0]["period"], "2026-04")

        # summary KPI strip.
        summary = ev.events_summary(rows)
        self.assertEqual(summary["total_events"], 1)
        self.assertEqual(summary["completed_events"], 1)
        self.assertEqual(summary["total_revenue"], 100.0)

        # delete removes the leaflet.
        self.assertTrue(ev.delete_event(event_id, webapps_root=self.webapps, client=client))
        self.assertFalse(leaflet_path.exists())
        self.assertEqual(ev.list_events(self.webapps, client=client), [])
        # second delete is a no-op.
        self.assertFalse(ev.delete_event(event_id, webapps_root=self.webapps, client=client))

    def test_example_template_is_excluded_from_listing(self) -> None:
        # The tracked *.example.* schema template lives in the gallery for
        # documentation; it must never be read as a real event.
        client = "brocks_pressure_washing"
        ev.save_event(_sample_payload(), webapps_root=self.webapps, client=client)
        gallery = ev.ensure_events_root(self.webapps)
        (gallery / "0000-00-00.event-job.example.brocks_pressure_washing.example.yaml").write_text(
            "schema: mycite.site_core.event_job.v1\n"
            "event_kind: job\n"
            "client: brocks_pressure_washing\n"
            "id: EXAMPLE\n"
            "date: '0000-00-00'\n"
            "status: booked\n",
            encoding="utf-8",
        )
        rows = ev.list_events(self.webapps, client=client)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("EXAMPLE", [r.get("id") for r in rows])

    def test_client_scope_isolation_on_delete(self) -> None:
        a = ev.save_event(_sample_payload(name="A One"), webapps_root=self.webapps,
                          client="client_a")
        ev.save_event(_sample_payload(name="B Two"), webapps_root=self.webapps,
                      client="client_b")
        # client_b can't delete client_a's event by id.
        self.assertFalse(
            ev.delete_event(a["id"], webapps_root=self.webapps, client="client_b")
        )
        # client_a can.
        self.assertTrue(
            ev.delete_event(a["id"], webapps_root=self.webapps, client="client_a")
        )

    def test_filename_rename_on_edit(self) -> None:
        client = "acme"
        saved = ev.save_event(_sample_payload(), webapps_root=self.webapps, client=client)
        eid = saved["id"]
        gallery = ev.events_root(self.webapps)
        first = gallery / saved["_source_file"]
        self.assertTrue(first.exists())
        # Re-save same id with a new date -> old file removed, new written.
        payload2 = _sample_payload(date="2026-05-01")
        payload2["id"] = eid
        saved2 = ev.save_event(payload2, webapps_root=self.webapps, client=client)
        self.assertNotEqual(saved2["_source_file"], saved["_source_file"])
        self.assertFalse(first.exists())
        self.assertEqual(len(ev.list_events(self.webapps, client=client)), 1)

    def test_flat_edit_preserves_nested_extras(self) -> None:
        """The dashboard's flat edit form posts only the top-level
        envelope (no customer/home/tags/pricing). Re-saving such a flat
        payload over an existing leaflet must PRESERVE the nested BPW
        analytics extras rather than wipe them."""
        client = "brocks_pressure_washing"
        saved = ev.save_event(_sample_payload(), webapps_root=self.webapps, client=client)
        eid = saved["id"]
        # A flat-only edit (status flips draft->completed via the form),
        # carrying none of the nested extras.
        flat_edit = {
            "event_id": eid,
            "date": "2026-04-14",
            "status": "completed",
            "title": "House wash — Dave Atch",
            "location": "123 Main St, Hudson",
            "description": "edited note",
        }
        saved2 = ev.save_event(flat_edit, webapps_root=self.webapps, client=client)
        # Flat fields updated...
        self.assertEqual(saved2["id"], eid)
        self.assertEqual(saved2["title"], "House wash — Dave Atch")
        self.assertEqual(saved2["description"], "edited note")
        # ...but the nested analytics extras survived the flat edit.
        self.assertEqual(saved2["customer"]["name"], "Dave Atch")
        self.assertEqual(saved2["customer"]["lead_source"], "repeat_customer")
        self.assertEqual(saved2["pricing"]["total"], 100)
        self.assertEqual([t["type"] for t in saved2["tags"]], ["house_wash"])
        # And analytics still see the customer/tag/pricing data.
        analytics = ev.events_analytics(self.webapps, client=client)
        self.assertEqual(analytics["tag_types"][0]["key"], "house_wash")
        self.assertEqual(
            analytics["lead_sources"][0]["key"], "repeat_customer"
        )


@unittest.skipUnless(FLASK_AVAILABLE and YAML_AVAILABLE, "Flask/PyYAML not installed")
class TestEventsRoutes(unittest.TestCase):
    def _build(self) -> tuple[V2PortalHostConfig, Path]:
        root = Path(tempfile.mkdtemp(prefix="events_routes_"))
        public = root / "public"
        private = root / "private"
        data = root / "data"
        webapps = root / "webapps"
        for d in (public, private, data, webapps):
            d.mkdir(parents=True, exist_ok=True)
        # Seed a BPW grantee so the host-domain resolver scopes the caller.
        fnd_csm = private / "utilities" / "tools" / "fnd-csm"
        fnd_csm.mkdir(parents=True, exist_ok=True)
        (fnd_csm / "grantee.fnd.bpw.json").write_text(
            json.dumps({
                "schema": "mycite.v2.grantee.profile.v1",
                "msn_id": "fnd.bpw",
                "label": "Brock's Pressure Washing",
                "short_name": "bpw",
                "domains": ["brockspressurewashing.com"],
                "users": [],
            }),
            encoding="utf-8",
        )
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            portal_domain="example.org",
            public_dir=public,
            private_dir=private,
            data_dir=data,
            webapps_root=webapps,
        )
        return config, webapps

    def test_save_list_analytics_delete_via_client(self) -> None:
        config, webapps = self._build()
        app = create_app(config)
        client = app.test_client()
        host = "brockspressurewashing.com"

        # save
        resp = client.post(
            "/__fnd/events/save",
            json=_sample_payload(),
            headers={"Host": host},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        eid = body["event"]["id"]
        self.assertEqual(body["event"]["client"], "brocks_pressure_washing")
        # Flat envelope round-trips through the route.
        self.assertEqual(body["event"]["date"], "2026-04-14")
        self.assertEqual(body["event"]["status"], "completed")
        self.assertEqual(body["event"]["location"], "123 Main St, Hudson")

        # the leaflet exists on disk under the right name.
        gallery = ev.events_root(webapps)
        self.assertTrue(
            (gallery / "2026-04-14.event-job.brocks_pressure_washing.dave.atch.yaml").exists()
        )

        # list
        resp = client.get("/__fnd/events/list", headers={"Host": host})
        self.assertEqual(resp.status_code, 200)
        listing = resp.get_json()
        self.assertEqual(len(listing["events"]), 1)
        self.assertEqual(listing["summary"]["total_events"], 1)
        # legacy alias key present
        self.assertIn("jobs", listing)

        # analytics
        resp = client.get("/__fnd/events/analytics", headers={"Host": host})
        self.assertEqual(resp.status_code, 200)
        analytics = resp.get_json()
        self.assertEqual(analytics["status_breakdown"], [{"key": "completed", "count": 1}])
        # The analytics payload now includes the KPI summary so the
        # dashboard's renderKpis(analytics.summary) populates.
        self.assertIn("summary", analytics)
        self.assertEqual(analytics["summary"]["total_events"], 1)
        self.assertEqual(analytics["summary"]["completed_events"], 1)
        self.assertEqual(analytics["summary"]["total_revenue"], 100.0)

        # legacy bpw-jobs alias still works (list)
        resp = client.get("/__fnd/bpw-jobs/list", headers={"Host": host})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["events"]), 1)

        # delete
        resp = client.delete(f"/__fnd/events/{eid}", headers={"Host": host})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        # gone
        resp = client.get("/__fnd/events/list", headers={"Host": host})
        self.assertEqual(len(resp.get_json()["events"]), 0)

    def test_other_client_does_not_see_events(self) -> None:
        config, _webapps = self._build()
        # Add a second grantee on a different host.
        fnd_csm = Path(config.private_dir) / "utilities" / "tools" / "fnd-csm"
        (fnd_csm / "grantee.fnd.other.json").write_text(
            json.dumps({
                "schema": "mycite.v2.grantee.profile.v1",
                "msn_id": "fnd.other",
                "label": "Other Co",
                "short_name": "other",
                "domains": ["otherco.example"],
                "users": [],
            }),
            encoding="utf-8",
        )
        app = create_app(config)
        client = app.test_client()
        # BPW saves an event.
        client.post("/__fnd/events/save", json=_sample_payload(),
                    headers={"Host": "brockspressurewashing.com"})
        # Other Co lists -> empty (scoped).
        resp = client.get("/__fnd/events/list", headers={"Host": "otherco.example"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["events"]), 0)


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestBpwShim(unittest.TestCase):
    def test_shim_aggregators_match_events(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import bpw_jobs
        rows = [_sample_payload(), _sample_payload(name="X Y", status="booked")]
        self.assertEqual(bpw_jobs.jobs_summary(rows), ev.events_summary(rows))
        self.assertEqual(bpw_jobs.jobs_analytics(rows), ev.aggregate_analytics(rows))


@unittest.skipUnless(YAML_AVAILABLE, "PyYAML not installed")
class TestMigrationScript(unittest.TestCase):
    def setUp(self) -> None:
        import yaml
        self._yaml = yaml
        self.root = Path(tempfile.mkdtemp(prefix="events_mig_"))
        self.jobs_root = self.root / "bpw-jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.webapps = self.root / "webapps"
        self.webapps.mkdir(parents=True, exist_ok=True)
        # 3 sample legacy job yamls.
        samples = [
            ("job.2026-04-14.atch.yaml", {
                "job": {"id": "2026-0038", "date": "2026-04-14", "status": "completed"},
                "customer": {"name": "Dave Atch", "lead_source": "repeat_customer",
                             "address": "1719 Tannery Circle, Hudson"},
                "home": {"house_sqft": 2211},
                "tags": [{"type": "house_wash", "price": 100}],
                "pricing": {"total": 100, "paid": True, "method": "venmo"},
                "notes": "n1",
            }),
            ("job.2026-04-15.white.yaml", {
                "job": {"id": "2026-0039", "date": "2026-04-15", "status": "booked"},
                "customer": {"name": "Sam White"},
                "tags": [{"type": "driveway", "price": 60}],
                "pricing": {"total": 60, "paid": False},
                "notes": "",
            }),
            ("job.2025-05-18.steve.baker.yaml", {
                "job": {"id": "2025-0001", "date": "2025-05-18", "status": "completed"},
                "customer": {"name": "Steve Baker"},
                "tags": [{"type": "house_wash", "price": 250}],
                "pricing": {"total": 250, "paid": True},
                "notes": "",
            }),
        ]
        for fname, doc in samples:
            (self.jobs_root / fname).write_text(
                self._yaml.safe_dump(doc, sort_keys=False), encoding="utf-8"
            )

    def _migrate(self, apply: bool):
        from MyCiteV2.scripts.migrate_bpw_jobs_to_events import migrate
        return migrate(
            jobs_root=self.jobs_root,
            webapps_root=self.webapps,
            client="brocks_pressure_washing",
            apply=apply,
        )

    def test_dry_run_writes_nothing(self) -> None:
        summary = self._migrate(apply=False)
        self.assertFalse(summary["applied"])
        self.assertEqual(summary["source_count"], 3)
        self.assertEqual(summary["planned_count"], 3)
        # No leaflets written.
        self.assertFalse(ev.events_root(self.webapps).exists())
        # Planned names are the canonical event-job names. The name
        # component derives from the generic title (first tag + customer).
        names = {t for _, t in summary["planned"]}
        self.assertIn(
            "2026-04-14.event-job.brocks_pressure_washing.house.wash.dave.atch.yaml",
            names,
        )

    def test_apply_writes_leaflets_and_backup(self) -> None:
        summary = self._migrate(apply=True)
        self.assertTrue(summary["applied"])
        self.assertEqual(summary["written_count"], 3)
        self.assertIsNotNone(summary["backup_dir"])
        self.assertTrue(Path(summary["backup_dir"]).is_dir())

        gallery = ev.events_root(self.webapps)
        written = sorted(p.name for p in gallery.glob("*.event-job.*.yaml"))
        self.assertEqual(len(written), 3)
        self.assertIn(
            "2026-04-14.event-job.brocks_pressure_washing.house.wash.dave.atch.yaml",
            written,
        )

        # A migrated leaflet has the schema stamp + preserved payload.
        leaflet = self._yaml.safe_load(
            (gallery
             / "2026-04-14.event-job.brocks_pressure_washing.house.wash.dave.atch.yaml")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(leaflet["schema"], ev.EVENT_SCHEMA)
        self.assertEqual(leaflet["event_kind"], "job")
        self.assertEqual(leaflet["client"], "brocks_pressure_washing")
        # Legacy nested job.{id,date,status} is promoted to the top level.
        self.assertNotIn("job", leaflet)
        self.assertEqual(leaflet["id"], "2026-0038")
        self.assertEqual(leaflet["date"], "2026-04-14")
        self.assertEqual(leaflet["status"], "completed")
        # A generic title is derived from the first tag + customer name.
        self.assertEqual(leaflet["title"], "House wash — Dave Atch")
        # notes -> description; customer.address -> location.
        self.assertEqual(leaflet["description"], "n1")
        self.assertEqual(leaflet["location"], "1719 Tannery Circle, Hudson")
        # Job-kind extras are preserved nested.
        self.assertEqual(leaflet["customer"]["name"], "Dave Atch")
        self.assertEqual(leaflet["pricing"]["total"], 100)

        # Migrated gallery is readable + analytics work end-to-end.
        rows = ev.list_events(self.webapps, client="brocks_pressure_washing")
        self.assertEqual(len(rows), 3)
        analytics = ev.events_analytics(self.webapps, client="brocks_pressure_washing")
        # 2 completed jobs across 2 months.
        self.assertEqual(len(analytics["revenue_by_month"]), 2)

    def test_apply_is_idempotent(self) -> None:
        self._migrate(apply=True)
        gallery = ev.events_root(self.webapps)
        first = sorted(p.name for p in gallery.glob("*.event-job.*.yaml"))
        # Re-run --apply: same target names, no duplicates.
        self._migrate(apply=True)
        second = sorted(p.name for p in gallery.glob("*.event-job.*.yaml"))
        self.assertEqual(first, second)

    def test_target_collision_aborts_apply(self) -> None:
        # Two distinct source jobs, same customer + date -> same target.
        for fname, jid in (("job.2026-06-01.dup.a.yaml", "2026-1001"),
                           ("job.2026-06-01.dup.b.yaml", "2026-1002")):
            (self.jobs_root / fname).write_text(
                self._yaml.safe_dump({
                    "job": {"id": jid, "date": "2026-06-01", "status": "booked"},
                    "customer": {"name": "Dup Customer"},
                    "tags": [{"type": "house_wash", "price": 1}],
                    "pricing": {"total": 1, "paid": False},
                    "notes": "",
                }, sort_keys=False),
                encoding="utf-8",
            )
        # Dry-run reports the collision but doesn't raise.
        summary = self._migrate(apply=False)
        self.assertTrue(summary["collisions"])
        # --apply refuses to write.
        with self.assertRaises(SystemExit):
            self._migrate(apply=True)
        # Nothing written.
        self.assertFalse(ev.events_root(self.webapps).exists())


if __name__ == "__main__":
    unittest.main()
