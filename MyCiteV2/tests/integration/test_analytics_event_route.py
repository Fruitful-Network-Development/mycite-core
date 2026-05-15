"""Phase 18a — /__fnd/analytics/event route contract.

Verifies:
  * Valid event lands in the NDJSON file with the right schema +
    server-stamped fields.
  * First POST mints a fnd_vid cookie via Set-Cookie; second POST
    re-uses the visitor hash.
  * Googlebot UA flips is_bot=True + bot_class=verified_search.
  * Invalid bodies (missing required field, unknown event_type)
    → 400.
  * Same visitor + page + event_type within 250ms is dedup'd.
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


def _build_client():
    tmp = Path(tempfile.mkdtemp(prefix="phase18a_event_route_"))
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


def _minimal_event():
    return {
        "event_type": "page_view",
        "occurred_at_utc": "2026-05-16T00:00:00Z",
        "session_id": "sid-abc",
        "page_path": "/",
    }


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class AnalyticsEventRouteTests(unittest.TestCase):
    def test_valid_event_lands_in_ndjson(self) -> None:
        client, tmp = _build_client()
        resp = client.post(
            "/__fnd/analytics/event",
            data=json.dumps(_minimal_event()),
            content_type="application/json",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        # NDJSON file landed where the resolver expects.
        events_dir = (
            tmp
            / "webapps"
            / "clients"
            / "fruitfulnetworkdevelopment.com"
            / "analytics"
            / "events"
        )
        files = list(events_dir.glob("*.ndjson"))
        self.assertEqual(len(files), 1)
        rows = files[0].read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(rows), 1)
        row = json.loads(rows[0])
        self.assertEqual(row["event_type"], "page_view")
        self.assertEqual(row["page_path"], "/")
        self.assertEqual(row["domain"], "fruitfulnetworkdevelopment.com")
        self.assertTrue(row["visitor_cookie_id_hash"])
        self.assertTrue(row["received_at_utc"])

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
        # The set cookie should be HttpOnly + SameSite=Lax + Secure.
        vid = next(c for c in cookies if c.startswith("fnd_vid="))
        self.assertIn("HttpOnly", vid)
        self.assertIn("SameSite=Lax", vid)
        self.assertIn("Secure", vid)

    def test_repeat_visitor_reuses_hash(self) -> None:
        client, tmp = _build_client()
        # Use a different session to avoid the dedup window.
        first_body = dict(_minimal_event(), page_path="/")
        second_body = dict(_minimal_event(), page_path="/about")
        # The test client persists cookies between requests when we
        # pass them explicitly via headers — simulate by reading the
        # first response's Set-Cookie and replaying on the second.
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
        events_dir = (
            tmp
            / "webapps"
            / "clients"
            / "fruitfulnetworkdevelopment.com"
            / "analytics"
            / "events"
        )
        rows = [
            json.loads(line)
            for line in next(events_dir.glob("*.ndjson")).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0]["visitor_cookie_id_hash"], rows[1]["visitor_cookie_id_hash"]
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
        events_dir = (
            tmp
            / "webapps"
            / "clients"
            / "fruitfulnetworkdevelopment.com"
            / "analytics"
            / "events"
        )
        row = json.loads(
            next(events_dir.glob("*.ndjson")).read_text(encoding="utf-8").splitlines()[0]
        )
        self.assertTrue(row["is_bot"])
        self.assertEqual(row["bot_class"], "verified_search")
        self.assertIn("ua_googlebot", row["bot_evidence"])

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
        # The first POST mints a cookie + writes 1 row.
        # The next two POSTs hit the dedup window (same visitor hash
        # for the no-cookie case → same hash because the cookie is
        # fresh each time, but the test client carries cookies
        # implicitly within a session so visitor_cookie_id_hash stays
        # stable).
        events_dir = (
            tmp
            / "webapps"
            / "clients"
            / "fruitfulnetworkdevelopment.com"
            / "analytics"
            / "events"
        )
        rows = next(events_dir.glob("*.ndjson")).read_text(encoding="utf-8").strip().splitlines()
        # 1 written, 2 deduped.
        self.assertEqual(len(rows), 1)

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
