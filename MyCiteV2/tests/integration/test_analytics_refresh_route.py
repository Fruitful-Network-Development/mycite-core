"""Phase 14d.4 — Analytics refresh route contract pins.

``POST /__fnd/analytics/refresh`` re-runs the per-domain aggregation
that normally happens in ``sync_fnd_analytics_summary`` and persists
the result through ``MosDatumAnalyticsSummaryAdapter`` so the
Analytics extension card on ``/portal/utilities/extensions`` can
show fresh numbers without waiting for the scheduled sync.

These tests pin:

  * Success path: feeds two NDJSON events into the webapps tree,
    POSTs to /__fnd/analytics/refresh, expects the MOS summary
    datum to land with the right counts.
  * Idempotency: calling refresh twice yields the same counts.
  * 400 on missing domain.
  * 404 when the events directory doesn't exist for the domain.
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


def _seed_events(webapps_root: Path, domain: str, events: list[dict]) -> None:
    events_dir = webapps_root / "clients" / domain / "analytics" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / "2026-05.ndjson").write_text(
        "\n".join(json.dumps(e) for e in events),
        encoding="utf-8",
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class AnalyticsRefreshRouteTests(unittest.TestCase):
    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase14d4_analytics_refresh_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
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

    def test_refresh_trigger_writes_summary_datum(self) -> None:
        from MyCiteV2.packages.adapters.sql.fnd_analytics_summary import (
            MosDatumAnalyticsSummaryAdapter,
        )

        client, tmp = self._build_client()
        _seed_events(
            tmp / "webapps",
            "alpha.example.test",
            [
                {"event_type": "page_view", "path": "/", "timestamp": "2026-05-01T00:00:00Z"},
                {"event_type": "page_view", "path": "/about", "timestamp": "2026-05-02T00:00:00Z"},
                {"event_type": "form_submit", "path": "/contact", "timestamp": "2026-05-03T00:00:00Z"},
            ],
        )
        resp = client.post(
            "/__fnd/analytics/refresh",
            data=json.dumps({"domain": "alpha.example.test"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["counts"]["page_view"], 2)
        self.assertEqual(body["counts"]["form_submit"], 1)
        self.assertEqual(body["recent_events_captured"], 3)

        # Sanity: the MOS adapter can now load what the refresh wrote.
        adapter = MosDatumAnalyticsSummaryAdapter(
            authority_db_file=tmp / "authority.sqlite3", tenant_id="fnd"
        )
        cached = adapter.load_summary(domain="alpha.example.test")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["summary"]["page_view"], 2)

    def test_refresh_is_idempotent(self) -> None:
        client, tmp = self._build_client()
        _seed_events(
            tmp / "webapps",
            "alpha.example.test",
            [{"event_type": "page_view", "path": "/", "timestamp": "2026-05-01T00:00:00Z"}],
        )
        first = client.post(
            "/__fnd/analytics/refresh",
            data=json.dumps({"domain": "alpha.example.test"}),
            content_type="application/json",
        )
        second = client.post(
            "/__fnd/analytics/refresh",
            data=json.dumps({"domain": "alpha.example.test"}),
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json()["counts"], second.get_json()["counts"])

    def test_refresh_rejects_missing_domain(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/analytics/refresh",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "missing_domain")

    def test_refresh_rejects_domain_without_events_dir(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/analytics/refresh",
            data=json.dumps({"domain": "no-events.example.test"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "no_events_directory")


class AnalyticsExtensionPayloadRefreshActionTests(unittest.TestCase):
    """The analytics extension payload must carry a ``refresh_action``
    so the JS renderer can wire the Refresh button.
    """

    def test_pending_payload_has_refresh_action(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.analytics import (
            _build_analytics_extension_payload,
        )

        tmp = Path(tempfile.mkdtemp(prefix="phase14d4_pending_"))
        payload = _build_analytics_extension_payload(
            domain="alpha.example.test",
            webapps_root=tmp,
            authority_db_file=None,
        )
        self.assertEqual(payload["data_source"]["kind"], "pending")
        self.assertEqual(payload["refresh_action"]["route"], "/__fnd/analytics/refresh")
        self.assertEqual(payload["refresh_action"]["payload"]["domain"], "alpha.example.test")

    def test_payload_emits_top_paths_from_recent_events(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.analytics import (
            _top_paths,
        )

        events = [
            {"event_type": "page_view", "path": "/", "timestamp": "t1"},
            {"event_type": "page_view", "path": "/", "timestamp": "t2"},
            {"event_type": "page_view", "path": "/about", "timestamp": "t3"},
        ]
        top = _top_paths(events)
        self.assertEqual(top[0]["path"], "/")
        self.assertEqual(top[0]["count"], 2)
        self.assertEqual(top[1]["path"], "/about")


if __name__ == "__main__":
    unittest.main()
