"""Phase 18b — /__fnd/analytics.js is served + valid + non-empty.

The route reads the analytics script straight from
``/srv/webapps/clients/_shared/site-core/js/extensions/analytics.js``
so a deploy of the shared library propagates without restarting the
portal (5-minute browser cache, see app.py).

This smoke confirms the file lands, the Content-Type is right, and
the body contains the canonical endpoint URL + the public mount
name so we can't ship an empty body by accident.
"""

from __future__ import annotations

import importlib.util
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


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class AnalyticsJsServedSmokeTests(unittest.TestCase):
    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase18b_analytics_js_"))
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
        return create_app(config).test_client()

    def test_serves_javascript_content_type(self) -> None:
        client = self._build_client()
        resp = client.get(
            "/__fnd/analytics.js",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            resp.headers["Content-Type"].startswith("application/javascript")
        )

    def test_served_body_contains_canonical_endpoint(self) -> None:
        client = self._build_client()
        resp = client.get(
            "/__fnd/analytics.js",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        body = resp.get_data(as_text=True)
        self.assertGreater(len(body), 100, "analytics.js body is empty / too short")
        self.assertIn("/__fnd/analytics/event", body)
        self.assertIn("MyciteAnalytics", body)
        self.assertIn("fnd_analytics_session", body)

    def test_response_includes_cache_header(self) -> None:
        client = self._build_client()
        resp = client.get(
            "/__fnd/analytics.js",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        cache = resp.headers.get("Cache-Control", "")
        self.assertIn("max-age", cache)


if __name__ == "__main__":
    unittest.main()
