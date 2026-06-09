"""Newsletter composer — leaflet store, compose-send service, grantee routes.

Three layers:
  * NewsletterLeafletStore round-trip (one file per newsletter, deduped by slug).
  * NewsletterService.send_composed_newsletter — Lambda-queue path, SES-fallback
    path, and the no-transport error, all with fakes (no AWS).
  * /__fnd/newsletter/grantee/{save,list} through the real app (scope + store).
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

from MyCiteV2.packages.adapters.filesystem import NewsletterLeafletStore
from MyCiteV2.packages.adapters.filesystem.newsletter_leaflet import entity_for_domain
from MyCiteV2.packages.modules.cross_domain.newsletter import NewsletterService

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA

FND = "3-2-3-17-77-1-6-4-1-4"
DOMAIN = "fnd.example.test"
H = {"X-Auth-Request-Grantee": FND}


class NewsletterLeafletStoreTests(unittest.TestCase):
    def test_round_trip_list_overwrite_delete(self):
        d = Path(tempfile.mkdtemp(prefix="nl_store_"))
        store = NewsletterLeafletStore(private_dir=d)
        ent = entity_for_domain("trappfamilyfarm.com")
        store.save(ent, {"slug": "spring-update", "subject": "Hi", "body_text": "B",
                         "status": "draft", "created_at": "2026-06-09T00:00:00Z"})
        store.save(ent, {"slug": "second", "subject": "Two", "body_text": "B2",
                         "status": "sent", "created_at": "2026-06-08T00:00:00Z"})
        # newest-created first
        self.assertEqual([n["slug"] for n in store.list_newsletters(ent)],
                         ["spring-update", "second"])
        self.assertEqual(store.load(ent, "spring-update")["subject"], "Hi")
        # overwrite keeps a single file
        store.save(ent, {"slug": "spring-update", "subject": "Hi2", "body_text": "B",
                         "status": "draft", "created_at": "2026-06-09T00:00:00Z"})
        self.assertEqual(len(store.list_newsletters(ent)), 2)
        self.assertEqual(store.load(ent, "spring-update")["subject"], "Hi2")
        self.assertTrue(store.delete(ent, "second"))
        self.assertEqual(len(store.list_newsletters(ent)), 1)


# --- service: send_composed_newsletter, faked state + cloud (no AWS) ---------

class _FakeState:
    def __init__(self, profile, contacts):
        self.profile = dict(profile)
        self.contacts = contacts
        self.saved = None

    def list_newsletter_domains(self):
        return ["example.com"]

    def ensure_domain_bootstrap(self, **k):
        return dict(self.profile), {
            "schema": "mycite.service_tool.newsletter.contact_log.v3",
            "domain": "example.com",
            "contacts": [dict(c) for c in self.contacts],
            "dispatches": [],
        }

    def list_verified_author_profiles(self, *, domain):
        return [{"profile_id": "p1", "send_as_email": "author@example.com"}]

    def load_profile(self, *, domain):
        return dict(self.profile)

    def save_profile(self, *, domain, payload):
        self.profile = dict(payload)
        return self.profile

    def load_contact_log(self, *, domain):
        return {"contacts": self.contacts, "dispatches": []}

    def save_contact_log(self, *, domain, payload):
        self.saved = payload
        return payload

    def runtime_secret_seed(self, *, secret_kind):
        return "seed"


class _FakeCloud:
    def __init__(self):
        self.queued = []

    def get_or_create_secret_value(self, *, secret_name, initial_value):
        return "secret"

    def queue_dispatch_message(self, *, queue_url, payload, region):
        self.queued.append(payload)
        return f"q{len(self.queued)}"


_SUBS = [
    {"email": "a@x.com", "subscribed": True},
    {"email": "b@x.com", "subscribed": True},
    {"email": "c@x.com", "subscribed": False},
]


class SendComposedNewsletterTests(unittest.TestCase):
    def test_ses_fallback_when_no_queue(self):
        st = _FakeState({"list_address": "news@example.com", "aws_region": "us-east-1"}, _SUBS)
        svc = NewsletterService(st, _FakeCloud(), tenant_id="fnd")
        sent = []

        def ses(*, to, subject, body_text, reply_to, unsubscribe_url):
            self.assertTrue(unsubscribe_url.startswith("https://example.com/__fnd/newsletter/unsubscribe"))
            sent.append(to)
            return "mid-" + to

        r = svc.send_composed_newsletter(
            domain="example.com", subject="Hi", body_text="Body",
            dispatcher_callback_url="cb", inbound_callback_url="ib", ses_sender=ses)
        self.assertEqual(r["transport"], "ses_direct")
        self.assertEqual(sorted(sent), ["a@x.com", "b@x.com"])  # only subscribed
        self.assertEqual((r["sent_count"], r["failed_count"], r["target_count"]), (2, 0, 2))
        saved = {c["email"]: c for c in st.saved["contacts"]}
        self.assertEqual(saved["a@x.com"]["send_count"], 1)
        self.assertEqual(saved["c@x.com"].get("send_count", 0), 0)
        self.assertEqual(st.saved["dispatches"][-1]["status"], "completed")

    def test_lambda_queue_when_provisioned(self):
        st = _FakeState({"list_address": "news@example.com",
                         "dispatch_queue_url": "https://sqs/q"}, _SUBS)
        cloud = _FakeCloud()
        svc = NewsletterService(st, cloud, tenant_id="fnd")
        r = svc.send_composed_newsletter(
            domain="example.com", subject="Hi", body_text="Body",
            dispatcher_callback_url="cb", inbound_callback_url="ib", ses_sender=None)
        self.assertEqual(r["transport"], "lambda_queue")
        self.assertEqual(r["queued_count"], 2)
        self.assertEqual(len(cloud.queued), 2)
        self.assertEqual(cloud.queued[0]["source_kind"], "dashboard_compose")
        self.assertEqual(st.saved["dispatches"][-1]["status"], "queued")

    def test_raises_when_no_queue_and_no_ses(self):
        st = _FakeState({"list_address": "news@example.com"}, _SUBS)
        svc = NewsletterService(st, _FakeCloud(), tenant_id="fnd")
        with self.assertRaises(ValueError):
            svc.send_composed_newsletter(
                domain="example.com", subject="Hi", body_text="B",
                dispatcher_callback_url="cb", inbound_callback_url="ib", ses_sender=None)


# --- routes: /__fnd/newsletter/grantee/{save,list} ---------------------------

@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class NewsletterGranteeRoutesTests(unittest.TestCase):
    def _client(self):
        tmp = Path(tempfile.mkdtemp(prefix="nl_routes_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        fnd_csm.mkdir(parents=True, exist_ok=True)
        (fnd_csm / f"grantee.fnd.{FND}.json").write_text(json.dumps({
            "schema": GRANTEE_PROFILE_SCHEMA, "msn_id": FND, "label": "FND",
            "short_name": "FND", "domains": [DOMAIN], "users": [],
        }), encoding="utf-8")
        config = V2PortalHostConfig(
            portal_instance_id="fnd", public_dir=tmp / "public", private_dir=tmp / "private",
            data_dir=tmp / "data", portal_domain="example.test", webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), tmp

    def test_save_then_list(self):
        client, _ = self._client()
        r = client.post("/__fnd/newsletter/grantee/save",
                        json={"subject": "Spring update", "body_text": "Hello"}, headers=H)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        nl = r.get_json()["newsletter"]
        self.assertEqual(nl["status"], "draft")
        self.assertEqual(nl["slug"], "spring_update")
        listed = client.get("/__fnd/newsletter/grantee/list", headers=H).get_json()
        self.assertIn("spring_update", [n["slug"] for n in listed["newsletters"]])

    def test_save_missing_subject_rejected(self):
        client, _ = self._client()
        r = client.post("/__fnd/newsletter/grantee/save",
                        json={"subject": "", "body_text": "x"}, headers=H)
        self.assertEqual(r.status_code, 400)

    def test_save_rejected_after_sent(self):
        client, tmp = self._client()
        # Seed a SENT newsletter directly, then confirm save refuses to clobber it.
        store = NewsletterLeafletStore(private_dir=tmp / "private", webapps_root=tmp / "webapps")
        ent = entity_for_domain(DOMAIN)
        store.save(ent, {"slug": "spring_update", "subject": "Spring update",
                         "body_text": "x", "status": "sent", "created_at": "2026-06-01T00:00:00Z"})
        r = client.post("/__fnd/newsletter/grantee/save",
                        json={"slug": "spring_update", "subject": "Spring update",
                              "body_text": "y"}, headers=H)
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
