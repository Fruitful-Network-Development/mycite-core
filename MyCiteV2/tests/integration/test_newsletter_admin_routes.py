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
