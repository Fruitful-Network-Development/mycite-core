"""Records + Campaigns analytics routes, and summary widget aggregates.

All three are grantee-scoped and read/write the monthly leaflet + campaign
registry under the caller's own entity.
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
    from MyCiteV2.instances._shared.runtime.analytics_ingest import ingest_batch
    from MyCiteV2.packages.adapters.filesystem import (
        AnalyticsLeafletStore,
        entity_for_domain,
    )
    from MyCiteV2.packages.core.grantee import GRANTEE_PROFILE_SCHEMA

FND = "3-2-3-17-77-1-6-4-1-4"
DOMAIN = "fnd.example.test"
PERIOD = "2026-06"


def _raw(occurred, **kw):
    base = {
        "event_id": "evt-" + occurred + kw.get("session_id", ""),
        "received_at_utc": occurred,
        "visitor_cookie_id_hash": "cookieA",
        "session_id": "s1",
        "event_type": "page_view",
        "occurred_at_utc": occurred,
        "page_path": "/",
        "referrer_domain": "",
        "is_bot": False,
        "bot_evidence": [],
    }
    base.update(kw)
    return base


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class AnalyticsRecordsCampaignsTests(unittest.TestCase):
    def _client(self):
        tmp = Path(tempfile.mkdtemp(prefix="analytics_routes_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        fnd_csm.mkdir(parents=True, exist_ok=True)
        (fnd_csm / f"grantee.fnd.{FND}.json").write_text(json.dumps({
            "schema": GRANTEE_PROFILE_SCHEMA, "msn_id": FND, "label": "FND",
            "short_name": "FND", "domains": [DOMAIN], "users": [],
        }), encoding="utf-8")
        entity = entity_for_domain(DOMAIN)
        store = AnalyticsLeafletStore(private_dir=tmp / "private", webapps_root=tmp / "webapps")
        ingest_batch(store, entity, DOMAIN, PERIOD, [
            _raw("2026-06-01T09:00:00+00:00", session_id="s1", page_path="/",
                 referrer_domain="google.com"),
            _raw("2026-06-01T09:01:00+00:00", session_id="s1", page_path="/pricing",
                 event_id="e2"),
            _raw("2026-06-02T09:00:00+00:00", session_id="sb", visitor_cookie_id_hash="bot",
                 is_bot=True, bot_class="scraper", event_id="e3"),
        ])
        config = V2PortalHostConfig(
            portal_instance_id="fnd", public_dir=tmp / "public", private_dir=tmp / "private",
            data_dir=tmp / "data", portal_domain="example.test", webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client()

    def test_records_lists_periods_and_returns_leaflet(self):
        resp = self._client().get(
            "/__fnd/analytics/records", headers={"X-Auth-Request-Grantee": FND}
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertIn(PERIOD, body["periods"])
        self.assertEqual(body["period"], PERIOD)
        self.assertGreaterEqual(len(body["leaflet"]["visitors"]), 1)

    def test_summary_carries_widgets(self):
        resp = self._client().get(
            "/__fnd/analytics/summary?from=2026-06-01&to=2026-06-30",
            headers={"X-Auth-Request-Grantee": FND},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertIn("widgets", body)
        w = body["widgets"]
        self.assertIn("human_vs_bot", w)
        self.assertIn("referrers_by_sessions", w)
        hv = {row["key"]: row["count"] for row in w["human_vs_bot"]}
        self.assertEqual(hv["bot"], 1)
        self.assertEqual(hv["human"], 2)

    def test_campaign_create_then_list(self):
        client = self._client()
        resp = client.post(
            "/__fnd/analytics/campaigns",
            json={"label": "Summer QR", "target_path": "/campaign/summer",
                  "source": "instagram", "medium": "qr"},
            headers={"X-Auth-Request-Grantee": FND},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        row = resp.get_json()["campaign"]
        self.assertTrue(row["token"])
        self.assertIn(f"fnd_c={row['token']}", row["tracked_url"])
        self.assertIn(DOMAIN, row["tracked_url"])

        listed = client.get(
            "/__fnd/analytics/campaigns", headers={"X-Auth-Request-Grantee": FND}
        ).get_json()
        tokens = {c["token"] for c in listed["campaigns"]}
        self.assertIn(row["token"], tokens)

    def test_cross_grantee_rejected(self):
        resp = self._client().get(
            "/__fnd/analytics/records?grantee=3-2-3-17-77-3-6-1-1-2",
            headers={"X-Auth-Request-Grantee": FND},
        )
        self.assertEqual(resp.status_code, 403)

    def test_records_cross_month_merges_and_dedupes(self):
        """?from=&to= spanning two months returns ONE merged visitor list: a
        visitor seen in both months collapses to a single row whose first/last
        seen span the range and whose sessions concatenate."""
        tmp = Path(tempfile.mkdtemp(prefix="analytics_xmonth_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        fnd_csm.mkdir(parents=True, exist_ok=True)
        (fnd_csm / f"grantee.fnd.{FND}.json").write_text(json.dumps({
            "schema": GRANTEE_PROFILE_SCHEMA, "msn_id": FND, "label": "FND",
            "short_name": "FND", "domains": [DOMAIN], "users": [],
        }), encoding="utf-8")
        entity = entity_for_domain(DOMAIN)
        store = AnalyticsLeafletStore(private_dir=tmp / "private", webapps_root=tmp / "webapps")
        ingest_batch(store, entity, DOMAIN, "2026-05", [
            _raw("2026-05-15T09:00:00+00:00", session_id="s1", visitor_cookie_id_hash="A"),
            _raw("2026-05-16T09:00:00+00:00", session_id="sm", visitor_cookie_id_hash="M",
                 event_id="em"),
        ])
        ingest_batch(store, entity, DOMAIN, "2026-06", [
            _raw("2026-06-02T09:00:00+00:00", session_id="s2", visitor_cookie_id_hash="A",
                 event_id="e2"),
        ])
        config = V2PortalHostConfig(
            portal_instance_id="fnd", public_dir=tmp / "public", private_dir=tmp / "private",
            data_dir=tmp / "data", portal_domain="example.test", webapps_root=tmp / "webapps",
        )
        body = create_app(config).test_client().get(
            "/__fnd/analytics/records?from=2026-05-01&to=2026-06-30",
            headers={"X-Auth-Request-Grantee": FND},
        ).get_json()
        self.assertEqual(set(body["periods_loaded"]), {"2026-05", "2026-06"})
        visitors = body["leaflet"]["visitors"]
        by_cookie = {v["visitor_cookie_id_hash"]: v for v in visitors}
        self.assertIn("A", by_cookie)
        self.assertIn("M", by_cookie)
        # A appears exactly once (de-duplicated across months)…
        self.assertEqual(sum(1 for v in visitors if v["visitor_cookie_id_hash"] == "A"), 1)
        a = by_cookie["A"]
        # …spanning May→June with both sessions concatenated.
        self.assertEqual(a["first_seen_at"][:7], "2026-05")
        self.assertEqual(a["last_seen_at"][:7], "2026-06")
        self.assertGreaterEqual(len(a["sessions"]), 2)
        # PII strip still applies on the merged path.
        self.assertNotIn("share_id", a["visitor_context"])

    def test_records_resolves_referral_and_trims_sensitive_fields(self):
        tmp = Path(tempfile.mkdtemp(prefix="analytics_referral_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        fnd_csm.mkdir(parents=True, exist_ok=True)
        (fnd_csm / f"grantee.fnd.{FND}.json").write_text(json.dumps({
            "schema": GRANTEE_PROFILE_SCHEMA, "msn_id": FND, "label": "FND",
            "short_name": "FND", "domains": [DOMAIN], "users": [],
        }), encoding="utf-8")
        entity = entity_for_domain(DOMAIN)
        store = AnalyticsLeafletStore(private_dir=tmp / "private", webapps_root=tmp / "webapps")
        ingest_batch(store, entity, DOMAIN, PERIOD, [
            _raw("2026-06-01T09:00:00+00:00", session_id="sa", visitor_cookie_id_hash="A",
                 share_id="sid_A", ip_prefix="1.2.3.0/24"),
            _raw("2026-06-01T10:00:00+00:00", session_id="sb", visitor_cookie_id_hash="B",
                 share_id="sid_B", referred_by="sid_A", event_id="e2"),
        ])
        config = V2PortalHostConfig(
            portal_instance_id="fnd", public_dir=tmp / "public", private_dir=tmp / "private",
            data_dir=tmp / "data", portal_domain="example.test", webapps_root=tmp / "webapps",
        )
        body = create_app(config).test_client().get(
            f"/__fnd/analytics/records?period={PERIOD}", headers={"X-Auth-Request-Grantee": FND}
        ).get_json()
        by_cookie = {v["visitor_cookie_id_hash"]: v for v in body["leaflet"]["visitors"]}
        # B's visit is recognized as referred by A (A is B's "origin router").
        self.assertEqual(by_cookie["B"]["referred_by_visitor"], by_cookie["A"]["visitor_record_id"])
        self.assertEqual(by_cookie["A"]["referred_by_visitor"], "")
        # coarse IP / geo / raw share ids are NOT exposed to the grantee.
        for v in body["leaflet"]["visitors"]:
            ctx = v["visitor_context"]
            self.assertNotIn("ip_prefixes", ctx)
            self.assertNotIn("share_id", ctx)
            self.assertNotIn("network", ctx)


if __name__ == "__main__":
    unittest.main()
