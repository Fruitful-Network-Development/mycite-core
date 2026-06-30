"""Dashboard bulk subscribe/unsubscribe — /__fnd/contacts/{subscribe,unsubscribe}-all.

Exercises the two grantee-scoped bulk actions added for the dashboard Contacts
subtab through the real app + the live filesystem contact store (no AWS): the
flag flips both ways, is idempotent, honours grantee scope + domain ownership +
the newsletter-enabled gate, and never records a dispatch (no email sent).
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

from MyCiteV2.packages.adapters.filesystem import FilesystemNewsletterStateAdapter
from MyCiteV2.packages.domain.contact_entry import canonical_contact_entry

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA

# A NON-operator client grantee — its caller may only touch its own contacts
# (the operator FND msn would bypass the scope check, so we don't use it here).
CLIENT_MSN = "7-1-2-3-4-5"
CLIENT_DOMAIN = "client.example.test"
HC = {"X-Auth-Request-Grantee": CLIENT_MSN}

# A second non-operator grantee with NO newsletter block.
NONEWS_MSN = "7-9-9-9-9-9"
NONEWS_DOMAIN = "plain.example.test"
HN = {"X-Auth-Request-Grantee": NONEWS_MSN}

SEED_TS = "2026-06-01T00:00:00+00:00"


def _contact(email: str, subscribed: bool, *, source: str = "website_signup",
             unsubscribed_at: str = "") -> dict:
    row = canonical_contact_entry(
        existing=None,
        patch={"email": email, "subscribed": subscribed, "source": source},
        now=SEED_TS,
    )
    if unsubscribed_at:
        row["unsubscribed_at"] = unsubscribed_at
    return row


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class ContactsBulkRoutesTests(unittest.TestCase):
    def _client(self):
        tmp = Path(tempfile.mkdtemp(prefix="contacts_bulk_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        fnd_csm.mkdir(parents=True, exist_ok=True)
        (fnd_csm / f"grantee.fnd.{CLIENT_MSN}.json").write_text(json.dumps({
            "schema": GRANTEE_PROFILE_SCHEMA, "msn_id": CLIENT_MSN, "label": "Client",
            "short_name": "CLIENT", "domains": [CLIENT_DOMAIN], "users": [],
            "newsletter": {"selected_sender_address": f"news@{CLIENT_DOMAIN}"},
        }), encoding="utf-8")
        (fnd_csm / f"grantee.fnd.{NONEWS_MSN}.json").write_text(json.dumps({
            "schema": GRANTEE_PROFILE_SCHEMA, "msn_id": NONEWS_MSN, "label": "Plain",
            "short_name": "PLAIN", "domains": [NONEWS_DOMAIN], "users": [],
        }), encoding="utf-8")
        config = V2PortalHostConfig(
            portal_instance_id="fnd", public_dir=tmp / "public", private_dir=tmp / "private",
            data_dir=tmp / "data", portal_domain="example.test", webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), tmp

    def _adapter(self, tmp):
        return FilesystemNewsletterStateAdapter(tmp / "private")

    def _seed(self, tmp, contacts, domain=CLIENT_DOMAIN):
        self._adapter(tmp).save_contact_log(
            domain=domain, payload={"contacts": contacts, "dispatches": []})

    def _rows(self, tmp, domain=CLIENT_DOMAIN):
        log = self._adapter(tmp).load_contact_log(domain=domain) or {}
        return {r["email"]: r for r in log.get("contacts") or []}

    # -- flips ----------------------------------------------------------------

    def test_unsubscribe_all_flips_only_subscribed(self):
        client, tmp = self._client()
        self._seed(tmp, [
            _contact("a@client.example.test", True),
            _contact("b@client.example.test", True),
            _contact("c@client.example.test", False),  # already off
        ])
        r = client.post("/__fnd/contacts/unsubscribe-all", json={}, headers=HC)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["updated"], 2)  # only the 2 subscribed flip
        rows = self._rows(tmp)
        self.assertFalse(any(rows[e]["subscribed"] for e in rows))
        self.assertTrue(rows["a@client.example.test"]["unsubscribed_at"])  # stamped

    def test_subscribe_all_reactivates_explicit_optout(self):
        client, tmp = self._client()
        self._seed(tmp, [
            _contact("a@client.example.test", True),  # already on
            _contact("b@client.example.test", False, source="unsubscribe_link",
                     unsubscribed_at=SEED_TS),
        ])
        r = client.post("/__fnd/contacts/subscribe-all", json={}, headers=HC)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["updated"], 1)  # only the opt-out flips
        b = self._rows(tmp)["b@client.example.test"]
        self.assertTrue(b["subscribed"])
        self.assertTrue(b["subscribed_at"])       # stamped on re-subscribe
        self.assertEqual(b["unsubscribed_at"], "")  # stale opt-out stamp cleared

    def test_idempotent_second_call_updates_zero(self):
        client, tmp = self._client()
        self._seed(tmp, [_contact("a@client.example.test", True)])
        first = client.post("/__fnd/contacts/unsubscribe-all", json={}, headers=HC)
        self.assertEqual(first.get_json()["updated"], 1)
        second = client.post("/__fnd/contacts/unsubscribe-all", json={}, headers=HC)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["updated"], 0)

    def test_no_dispatch_recorded(self):
        # The bulk flip must never touch the send path — dispatch history stays
        # empty and per-contact send_count is unchanged (proxy for "no email").
        client, tmp = self._client()
        self._seed(tmp, [_contact("a@client.example.test", True)])
        client.post("/__fnd/contacts/unsubscribe-all", json={}, headers=HC)
        log = self._adapter(tmp).load_contact_log(domain=CLIENT_DOMAIN)
        self.assertEqual(log.get("dispatches"), [])
        self.assertEqual(self._rows(tmp)["a@client.example.test"]["send_count"], 0)

    # -- scope / gating -------------------------------------------------------

    def test_domain_not_owned_rejected(self):
        client, tmp = self._client()
        self._seed(tmp, [_contact("a@client.example.test", True)])
        r = client.post("/__fnd/contacts/unsubscribe-all",
                        json={"domain": "someoneelse.example.test"}, headers=HC)
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        self.assertEqual(r.get_json().get("error"), "domain_not_owned")

    def test_cross_grantee_scope_mismatch(self):
        client, _ = self._client()
        # CLIENT caller (non-operator) targeting another grantee via ?grantee=.
        r = client.post(f"/__fnd/contacts/subscribe-all?grantee={NONEWS_MSN}",
                        json={}, headers=HC)
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        self.assertEqual(r.get_json().get("error"), "scope_mismatch")

    def test_newsletter_not_enabled_rejected(self):
        client, _ = self._client()
        r = client.post("/__fnd/contacts/subscribe-all", json={}, headers=HN)
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        self.assertEqual(r.get_json().get("error"), "newsletter_not_enabled")


if __name__ == "__main__":
    unittest.main()
