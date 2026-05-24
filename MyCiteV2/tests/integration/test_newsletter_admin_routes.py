"""Phase 14d.1 — Newsletter admin route contract pins.

Three operator-facing routes back the Newsletter extension's
interactive controls on ``/portal/utilities/extensions``:

  * ``POST /__fnd/newsletter/admin/add``         — upsert_subscriber
  * ``POST /__fnd/newsletter/admin/remove``      — mark_unsubscribed
  * ``POST /__fnd/newsletter/admin/set_sender``  — persist sender to grantee JSON

Unlike the public ``/__fnd/newsletter/{subscribe,unsubscribe}``
endpoints, these accept the target ``domain`` explicitly in the body
so the operator can manage any grantee's list from the portal host.

These tests pin the success path, the validation rejects, and the
404/409 paths for each route. They use a tempdir-backed portal with
a seeded grantee + a seeded newsletter-admin profile so the domain
resolves through ``_newsletter_known_domains``.
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

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA


def _seed_grantee(grantee_dir: Path, msn_id: str, label: str, domain: str, users: list[str]) -> None:
    grantee_dir.mkdir(parents=True, exist_ok=True)
    (grantee_dir / f"grantee.fnd-msn.{msn_id}.json").write_text(
        json.dumps(
            {
                "schema": GRANTEE_PROFILE_SCHEMA,
                "msn_id": msn_id,
                "label": label,
                "short_name": msn_id,
                "domains": [domain],
                "users": users,
                "newsletter": {"selected_sender_address": users[0] if users else ""},
            }
        ),
        encoding="utf-8",
    )


def _seed_newsletter_admin_profile(private_dir: Path, domain: str) -> None:
    admin_dir = private_dir / "utilities" / "tools" / "newsletter-admin"
    admin_dir.mkdir(parents=True, exist_ok=True)
    (admin_dir / f"newsletter-admin.{domain}.json").write_text(
        json.dumps({"domain": domain, "configured": True}),
        encoding="utf-8",
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class NewsletterAdminRoutesTests(unittest.TestCase):
    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase14d1_newsletter_admin_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_grantee(
            tmp / "private" / "utilities" / "tools" / "fnd-csm",
            "alpha",
            "Alpha Grantee",
            "alpha.example.test",
            ["sender@alpha.example.test", "alt@alpha.example.test"],
        )
        _seed_newsletter_admin_profile(tmp / "private", "alpha.example.test")
        # The mutation runtime requires an authority_db_file for the
        # newsletter contact log target. The MOS adapter creates the
        # contact-log document on first write, so an empty SQLite file
        # at this path is sufficient.
        authority_db = tmp / "authority.sqlite3"
        authority_db.touch()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
            authority_db_file=authority_db,
        )
        return create_app(config).test_client(), tmp

    def test_add_subscriber_succeeds(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {"email": "new@subscriber.test", "name": "New"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["email"], "new@subscriber.test")
        self.assertTrue(body["subscribed"])

    def test_add_subscriber_persists_split_name_fields(self) -> None:
        # Phase 15b: the admin form sends first_name / middle_name /
        # last_name separately. The mutation runtime + adapter persist
        # them as their own magnitudes, recoverable via load_contact_log.
        from MyCiteV2.packages.adapters.filesystem import (
            FilesystemNewsletterStateAdapter,
        )

        client, tmp = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {
                        "email": "mary.zaun@subscriber.test",
                        "first_name": "Mary",
                        "middle_name": "Anne",
                        "last_name": "Zaun",
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        adapter = FilesystemNewsletterStateAdapter(tmp / "private")
        loaded = adapter.load_contact_log(domain="alpha.example.test")
        row = next(
            c for c in loaded["contacts"] if c["email"] == "mary.zaun@subscriber.test"
        )
        self.assertEqual(row["first_name"], "Mary")
        self.assertEqual(row["middle_name"], "Anne")
        self.assertEqual(row["last_name"], "Zaun")
        self.assertEqual(row["name"], "Mary Anne Zaun")

    def test_add_subscriber_persists_phone_zip(self) -> None:
        # Phase 16a: phone + zip are now first-class magnitudes that
        # the admin form supplies + the adapter persists.
        from MyCiteV2.packages.adapters.filesystem import (
            FilesystemNewsletterStateAdapter,
        )

        client, tmp = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {
                        "email": "phone.fan@subscriber.test",
                        "first_name": "Phone",
                        "last_name": "Fan",
                        "phone": "216-555-9999",
                        "zip": "44264",
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        adapter = FilesystemNewsletterStateAdapter(tmp / "private")
        loaded = adapter.load_contact_log(domain="alpha.example.test")
        row = next(c for c in loaded["contacts"] if c["email"] == "phone.fan@subscriber.test")
        self.assertEqual(row["phone"], "216-555-9999")
        self.assertEqual(row["zip"], "44264")
        self.assertRegex(row["signup_date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_edit_route_updates_named_fields(self) -> None:
        from MyCiteV2.packages.adapters.filesystem import (
            FilesystemNewsletterStateAdapter,
        )

        client, tmp = self._build_client()
        client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {"email": "edit.me@subscriber.test", "first_name": "Edit"},
                }
            ),
            content_type="application/json",
        )
        resp = client.post(
            "/__fnd/newsletter/admin/edit",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {
                        "email": "edit.me@subscriber.test",
                        "first_name": "Edited",
                        "last_name": "Done",
                        "phone": "555-1234",
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(
            set(body["updated_fields"]), {"first_name", "last_name", "phone"}
        )

        adapter = FilesystemNewsletterStateAdapter(tmp / "private")
        row = next(
            c
            for c in adapter.load_contact_log(domain="alpha.example.test")["contacts"]
            if c["email"] == "edit.me@subscriber.test"
        )
        self.assertEqual(row["first_name"], "Edited")
        self.assertEqual(row["last_name"], "Done")
        self.assertEqual(row["phone"], "555-1234")

    def test_edit_route_404_on_unknown_email(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/edit",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {"email": "ghost@subscriber.test", "phone": "x"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "contact_not_found")

    def test_add_subscriber_legacy_single_name_auto_splits(self) -> None:
        # Phase 15b back-compat: clients that still post a single
        # ``name`` field continue to work — the runtime auto-splits.
        from MyCiteV2.packages.adapters.filesystem import (
            FilesystemNewsletterStateAdapter,
        )

        client, tmp = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {"email": "legacy@subscriber.test", "name": "Adrienne Gordon"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        adapter = FilesystemNewsletterStateAdapter(tmp / "private")
        loaded = adapter.load_contact_log(domain="alpha.example.test")
        row = next(
            c for c in loaded["contacts"] if c["email"] == "legacy@subscriber.test"
        )
        self.assertEqual(row["first_name"], "Adrienne")
        self.assertEqual(row["last_name"], "Gordon")

    def test_add_subscriber_rejects_missing_domain(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps({"fields": {"email": "x@example.test"}}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "missing_domain")

    def test_add_subscriber_rejects_invalid_email(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {"domain": "alpha.example.test", "fields": {"email": "not-an-email"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_email")

    def test_add_subscriber_rejects_unknown_domain(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "unknown.example.test",
                    "fields": {"email": "x@example.test"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "domain_not_configured")

    def test_remove_subscriber_succeeds(self) -> None:
        # First add, then remove.
        client, _ = self._build_client()
        client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {"email": "tobego@subscriber.test"},
                }
            ),
            content_type="application/json",
        )
        resp = client.post(
            "/__fnd/newsletter/admin/remove",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {"email": "tobego@subscriber.test"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["subscribed"])

    def test_remove_unknown_email_returns_404(self) -> None:
        # Removing an email that isn't on the list must 404, not a false 200.
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/remove",
            data=json.dumps(
                {
                    "domain": "alpha.example.test",
                    "fields": {"email": "never.subscribed@subscriber.test"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "contact_not_found")

    def test_admin_write_blocked_for_foreign_grantee(self) -> None:
        # A request that arrives with a grantee header (per-grantee dashboard
        # proxy) may only mutate that grantee's own domains.
        client, tmp = self._build_client()
        # beta is a known newsletter domain, but grantee "alpha" doesn't own it.
        _seed_newsletter_admin_profile(tmp / "private", "beta.example.test")
        resp = client.post(
            "/__fnd/newsletter/admin/add",
            data=json.dumps(
                {
                    "domain": "beta.example.test",
                    "fields": {"email": "x@beta.example.test"},
                }
            ),
            content_type="application/json",
            headers={"X-Auth-Request-Grantee": "alpha"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json()["error"], "domain_not_owned")

    def test_remove_subscriber_rejects_invalid_email(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/remove",
            data=json.dumps(
                {"domain": "alpha.example.test", "fields": {"email": "garbage"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_email")

    def test_set_sender_succeeds(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/set_sender",
            data=json.dumps(
                {
                    "msn_id": "alpha",
                    "fields": {"sender_address": "alt@alpha.example.test"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(
            body["newsletter"]["selected_sender_address"], "alt@alpha.example.test"
        )

    def test_set_sender_rejects_email_outside_users(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/set_sender",
            data=json.dumps(
                {
                    "msn_id": "alpha",
                    "fields": {"sender_address": "stranger@example.test"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "sender_not_in_users")

    def test_set_sender_rejects_unknown_msn(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/newsletter/admin/set_sender",
            data=json.dumps(
                {
                    "msn_id": "ghost",
                    "fields": {"sender_address": "sender@alpha.example.test"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "grantee_not_found")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class NewsletterExtensionPayloadAdminFormsTests(unittest.TestCase):
    """The newsletter extension payload must surface the new admin
    forms + per-row remove_actions so the JS renderer can wire them.
    """

    def test_payload_includes_admin_forms_and_remove_actions(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.newsletter import (
            _build_newsletter_extension_payload,
        )

        tmp = Path(tempfile.mkdtemp(prefix="phase14d1_payload_"))
        (tmp / "utilities" / "tools" / "fnd-csm").mkdir(parents=True)
        payload = _build_newsletter_extension_payload(
            grantee={
                "msn_id": "alpha",
                "users": ["sender@alpha.example.test", "alt@alpha.example.test"],
                "newsletter": {"selected_sender_address": "sender@alpha.example.test"},
            },
            domain="alpha.example.test",
            private_dir=tmp,
        )
        admin_forms = payload.get("admin_forms") or []
        frame_ids = {f.get("frame_id") for f in admin_forms}
        self.assertIn("newsletter_add_subscriber", frame_ids)
        self.assertIn("newsletter_set_sender", frame_ids)

    def test_payload_drops_set_sender_form_when_no_users(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.newsletter import (
            _build_newsletter_extension_payload,
        )

        tmp = Path(tempfile.mkdtemp(prefix="phase14d1_payload_nousers_"))
        payload = _build_newsletter_extension_payload(
            grantee={"msn_id": "alpha", "users": []},
            domain="alpha.example.test",
            private_dir=tmp,
        )
        admin_forms = payload.get("admin_forms") or []
        frame_ids = {f.get("frame_id") for f in admin_forms}
        self.assertNotIn("newsletter_set_sender", frame_ids)


if __name__ == "__main__":
    unittest.main()
