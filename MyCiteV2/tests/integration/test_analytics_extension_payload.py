"""Analytics extension renderer surfaces derived insights (leaflet source).

The renderer now reads the monthly analytics leaflet (the single store the
dashboard reads too) and derives the rich insight set on demand. This test
seeds 3 visitors + 1 bot into a tempdir leaflet via the store, runs the
renderer, and asserts the sections are present + accurate.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.analytics_ingest import ingest_batch
from MyCiteV2.instances._shared.runtime.utilities_extensions.analytics import (
    _build_analytics_extension_payload,
)
from MyCiteV2.packages.adapters.filesystem import AnalyticsLeafletStore, entity_for_domain

DOMAIN = "example.test"
ENTITY = entity_for_domain(DOMAIN)


def _current_year_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _raw(occurred: str, **overrides):
    base = {
        "event_id": "evt-" + occurred,
        "received_at_utc": occurred,
        "domain": DOMAIN,
        "visitor_cookie_id_hash": "visitor-a",
        "ip_prefix": "192.0.2.0/24",
        "is_bot": False,
        "bot_class": "",
        "bot_evidence": [],
        "event_type": "page_view",
        "occurred_at_utc": occurred,
        "session_id": "sid-1",
        "page_path": "/",
        "referrer_domain": "",
        "active_time_ms": 0,
        "scroll_depth_percent": 0,
    }
    base.update(overrides)
    return base


def _seed(tmp: Path, period: str, rows: list[dict]) -> None:
    store = AnalyticsLeafletStore(private_dir=tmp, webapps_root=tmp)
    ingest_batch(store, ENTITY, DOMAIN, period, rows)


class AnalyticsExtensionPayloadTests(unittest.TestCase):
    def test_payload_carries_derived_insights(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="ext_payload_"))
        ym = _current_year_month()
        d = f"{ym}-15"
        rows = [
            # Visitor A: 2 sessions.
            _raw(f"{d}T00:00:00Z", visitor_cookie_id_hash="visitor-a", session_id="sid-a1",
                 page_path="/", referrer_domain="google.com", active_time_ms=30_000),
            _raw(f"{d}T00:01:00Z", visitor_cookie_id_hash="visitor-a", session_id="sid-a1",
                 page_path="/services", active_time_ms=60_000),
            _raw(f"{d}T02:00:00Z", visitor_cookie_id_hash="visitor-a", session_id="sid-a2",
                 page_path="/contact", active_time_ms=90_000),
            # Visitor B: 1 session.
            _raw(f"{d}T00:00:00Z", visitor_cookie_id_hash="visitor-b", session_id="sid-b1",
                 page_path="/", referrer_domain="bing.com", active_time_ms=10_000),
            # Visitor C: 1 session.
            _raw(f"{d}T00:00:00Z", visitor_cookie_id_hash="visitor-c", session_id="sid-c1",
                 page_path="/about", referrer_domain="google.com", active_time_ms=5_000),
            # Bot: excluded from human metrics.
            _raw(f"{d}T03:00:00Z", visitor_cookie_id_hash="bot-1", session_id="sid-bot",
                 page_path="/", is_bot=True, bot_class="verified_search",
                 bot_evidence=["ua_googlebot"]),
        ]
        _seed(tmp, ym, rows)

        payload = _build_analytics_extension_payload(
            domain=DOMAIN, private_dir=tmp, webapps_root=tmp
        )
        self.assertEqual(payload["visitor_count"], 3)
        self.assertEqual(payload["session_count"], 4)  # a1, a2, b1, c1
        self.assertEqual(payload["bot_event_count"], 1)
        self.assertEqual(payload["repeat_visitor_count"], 1)
        self.assertEqual(payload["high_intent_count"], 1)

        ref_by_domain = {r["referrer_domain"]: r for r in payload["top_referrers"]}
        self.assertIn("google.com", ref_by_domain)
        self.assertEqual(ref_by_domain["google.com"]["sessions"], 2)

        top_paths = {row["path"] for row in payload["top_paths"]}
        self.assertIn("/", top_paths)
        self.assertIn("/services", top_paths)

        seqs = {row["path"] for row in payload["common_paths"]}
        self.assertIn("/ → /services", seqs)

        entries = {row["page_path"] for row in payload["top_entry_pages"]}
        self.assertIn("/", entries)
        self.assertEqual(payload["data_source"]["kind"], "leaflet")

    def test_empty_log_returns_pending(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="ext_empty_"))
        payload = _build_analytics_extension_payload(
            domain=DOMAIN, private_dir=tmp, webapps_root=tmp
        )
        self.assertEqual(payload["data_source"]["kind"], "pending")
        self.assertEqual(payload["summary"], {})


if __name__ == "__main__":
    unittest.main()
