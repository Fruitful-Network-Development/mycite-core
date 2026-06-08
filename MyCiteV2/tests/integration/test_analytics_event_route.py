"""/__fnd/analytics/event route contract (leaflet cutover).

Verifies:
  * Valid event lands in the monthly leaflet (visitor → session → event) with
    the right server-stamped fields.
  * First POST mints a fnd_vid cookie via Set-Cookie; a repeat visitor re-uses
    the visitor hash (one visitor, two page_views).
  * Googlebot UA flips the visitor's bot_assessment.is_bot + bot_class.
  * Invalid bodies (missing required field, unknown event_type) → 400.
  * Same visitor + page + event_type within 250ms is dedup'd.

The event route buffers writes (heartbeats are frequent); tests flush the
in-process buffer explicitly before reading the leaflet off disk.
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

ENTITY = "fruitful_network_development_llc"  # entity_for_domain(fruitfulnetworkdevelopment.com)


def _build_client():
    tmp = Path(tempfile.mkdtemp(prefix="analytics_event_route_"))
    for sub in ("public", "private", "data", "webapps"):
        (tmp / sub).mkdir()
    config = V2PortalHostConfig(
        portal_instance_id="fnd",
        public_dir=tmp / "public",
        private_dir=tmp / "private",
        data_dir=tmp / "data",
        portal_domain="fruitfulnetworkdevelopment.com",
        webapps_root=tmp / "webapps",
    )
    return create_app(config).test_client(), tmp


def _flush_and_load(tmp: Path, period: str = "2026-05"):
    """Flush the in-process ingest buffer then load the month leaflet."""
    from MyCiteV2.instances._shared.runtime.analytics_ingest import get_ingest_buffer
    from MyCiteV2.packages.adapters.filesystem import AnalyticsLeafletStore

    get_ingest_buffer(private_dir=tmp / "private", webapps_root=tmp / "webapps").flush_all()
    store = AnalyticsLeafletStore(private_dir=tmp / "private", webapps_root=tmp / "webapps")
    return store.load_month(ENTITY, period)


def _minimal_event():
    return {
        "event_type": "page_view",
        "occurred_at_utc": "2026-05-16T00:00:00Z",
        "session_id": "sid-abc",
        "page_path": "/",
    }


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class AnalyticsEventRouteTests(unittest.TestCase):
    def test_valid_event_lands_in_leaflet(self) -> None:
        client, tmp = _build_client()
        resp = client.post(
            "/__fnd/analytics/event",
            data=json.dumps(_minimal_event()),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        month = _flush_and_load(tmp)
        self.assertEqual(month["domain"], "fruitfulnetworkdevelopment.com")
        self.assertEqual(len(month["visitors"]), 1)
        visitor = month["visitors"][0]
        self.assertTrue(visitor["visitor_cookie_id_hash"])
        self.assertEqual(len(visitor["sessions"]), 1)
        events = visitor["sessions"][0]["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "page_view")
        self.assertEqual(events[0]["page_path"], "/")
        self.assertTrue(events[0]["received_at"])

    def test_first_post_mints_cookie(self) -> None:
        client, _ = _build_client()
        resp = client.post(
            "/__fnd/analytics/event",
            data=json.dumps(_minimal_event()),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 200)
        cookies = resp.headers.getlist("Set-Cookie")
        self.assertTrue(any("fnd_vid=" in c for c in cookies))
        vid = next(c for c in cookies if c.startswith("fnd_vid="))
        self.assertIn("HttpOnly", vid)
        self.assertIn("SameSite=Lax", vid)
        self.assertIn("Secure", vid)

    def test_repeat_visitor_reuses_hash(self) -> None:
        client, tmp = _build_client()
        first_body = dict(_minimal_event(), page_path="/")
        second_body = dict(_minimal_event(), page_path="/about")
        r1 = client.post(
            "/__fnd/analytics/event",
            data=json.dumps(first_body),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        cookies = r1.headers.getlist("Set-Cookie")
        vid_cookie = next(c.split(";", 1)[0] for c in cookies if c.startswith("fnd_vid="))
        client.post(
            "/__fnd/analytics/event",
            data=json.dumps(second_body),
            content_type="application/json",
            headers={"Cookie": vid_cookie},
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        month = _flush_and_load(tmp)
        # One visitor (cookie reused), one session, two page_view events.
        self.assertEqual(len(month["visitors"]), 1)
        events = month["visitors"][0]["sessions"][0]["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {e["page_path"] for e in events}, {"/", "/about"}
        )

    def test_googlebot_ua_flags_bot(self) -> None:
        client, tmp = _build_client()
        client.post(
            "/__fnd/analytics/event",
            data=json.dumps(_minimal_event()),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            },
        )
        month = _flush_and_load(tmp)
        ba = month["visitors"][0]["visitor_context"]["bot_assessment"]
        self.assertTrue(ba["is_bot"])
        self.assertEqual(ba["bot_class"], "verified_search")
        self.assertIn("ua_googlebot", ba["bot_evidence"])

    def test_missing_required_field_is_400(self) -> None:
        client, _ = _build_client()
        body = _minimal_event()
        body.pop("event_type")
        resp = client.post(
            "/__fnd/analytics/event",
            data=json.dumps(body),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_event")

    def test_unknown_event_type_is_400(self) -> None:
        client, _ = _build_client()
        resp = client.post(
            "/__fnd/analytics/event",
            data=json.dumps(dict(_minimal_event(), event_type="rave_party")),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 400)

    def test_dedup_drops_same_event_within_window(self) -> None:
        client, tmp = _build_client()
        body = _minimal_event()
        for _ in range(3):
            client.post(
                "/__fnd/analytics/event",
                data=json.dumps(body),
                content_type="application/json",
                base_url="http://fruitfulnetworkdevelopment.com",
            )
        # The test client carries the minted cookie across requests, so all
        # three share a visitor hash + page + event_type → 2 are deduped.
        month = _flush_and_load(tmp)
        events = month["visitors"][0]["sessions"][0]["events"]
        self.assertEqual(len(events), 1)

    def test_analytics_js_route_serves_javascript(self) -> None:
        client, _ = _build_client()
        resp = client.get(
            "/__fnd/analytics.js",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            resp.headers["Content-Type"].startswith("application/javascript")
        )


if __name__ == "__main__":
    unittest.main()
