"""Phase 18c — Analytics extension renderer surfaces derived insights.

The on-demand path reads NDJSON files from
<webapps>/clients/<domain>/analytics/events/ and computes the rich
insight set inline. This test seeds 3 visitors + 1 bot into a
tempdir, runs the renderer, and asserts the new sections are
present + accurate.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions.analytics import (
    _build_analytics_extension_payload,
)


def _v2_row(**overrides):
    # Helper name is historical — produces a row at the *current*
    # schema (v3 as of 2026-05). v3 readers happily ingest v2 rows
    # too; the fixture just keeps parity with the producer.
    base = {
        "schema": "mycite.v2.analytics.event.v3",
        "event_id": "evt-1",
        "received_at_utc": "2026-05-15T00:00:01Z",
        "site_id": "fnd",
        "domain": "example.test",
        "environment": "prod",
        "visitor_cookie_id_hash": "visitor-a",
        "ip_hash": "ip-a",
        "ip_prefix": "192.0.2.0/24",
        "is_bot": False,
        "bot_class": "",
        "bot_evidence": [],
        "event_type": "page_view",
        "occurred_at_utc": "2026-05-15T00:00:00Z",
        "session_id": "sid-1",
        "page_path": "/",
        "page_title": "",
        "referrer_url": "",
        "referrer_domain": "",
        "active_time_ms": 0,
        "scroll_depth_percent": 0,
        "user_agent_raw": "Mozilla/5.0 Chrome/130.0",
        "properties": {},
    }
    base.update(overrides)
    return base


def _seed_events(webapps_root: Path, year_month: str, rows: list[dict]) -> None:
    events_dir = webapps_root / "clients" / "example.test" / "analytics" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / f"{year_month}.ndjson").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def _current_year_month() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m")


class AnalyticsExtensionPayloadTests(unittest.TestCase):
    def test_payload_carries_derived_insights(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="phase18c_payload_"))
        ym = _current_year_month()
        rows = [
            # Visitor A: 2 sessions.
            _v2_row(
                visitor_cookie_id_hash="visitor-a",
                session_id="sid-a1",
                page_path="/",
                referrer_domain="google.com",
                active_time_ms=30_000,
            ),
            _v2_row(
                visitor_cookie_id_hash="visitor-a",
                session_id="sid-a1",
                page_path="/services",
                active_time_ms=60_000,
            ),
            _v2_row(
                visitor_cookie_id_hash="visitor-a",
                session_id="sid-a2",
                page_path="/contact",
                active_time_ms=90_000,
                occurred_at_utc="2026-05-15T02:00:00Z",
            ),
            # Visitor B: 1 session.
            _v2_row(
                visitor_cookie_id_hash="visitor-b",
                session_id="sid-b1",
                page_path="/",
                referrer_domain="bing.com",
                active_time_ms=10_000,
            ),
            # Visitor C: 1 session.
            _v2_row(
                visitor_cookie_id_hash="visitor-c",
                session_id="sid-c1",
                page_path="/about",
                referrer_domain="google.com",
                active_time_ms=5_000,
            ),
            # Bot: should not count toward visitor or session metrics.
            _v2_row(
                visitor_cookie_id_hash="bot-1",
                is_bot=True,
                bot_class="verified_search",
                session_id="sid-bot",
                page_path="/",
            ),
        ]
        _seed_events(tmp, ym, rows)

        payload = _build_analytics_extension_payload(
            domain="example.test", webapps_root=tmp
        )
        self.assertEqual(payload["visitor_count"], 3)
        self.assertEqual(payload["session_count"], 4)  # a1, a2, b1, c1
        self.assertEqual(payload["bot_event_count"], 1)
        # Visitor A has 2 sessions → 1 repeat visitor.
        self.assertEqual(payload["repeat_visitor_count"], 1)
        # /contact visit with 90s active time is the only high-intent session.
        self.assertEqual(payload["high_intent_count"], 1)

        top_referrers = payload["top_referrers"]
        ref_by_domain = {r["referrer_domain"]: r for r in top_referrers}
        self.assertIn("google.com", ref_by_domain)
        # google.com: visitor A's first session + visitor C's session.
        self.assertEqual(ref_by_domain["google.com"]["sessions"], 2)

        top_paths = {row["path"] for row in payload["top_paths"]}
        self.assertIn("/", top_paths)
        self.assertIn("/services", top_paths)

        common = payload["common_paths"]
        # Visitor A's session 1 hits "/" → "/services" — must show.
        seqs = {row["path"] for row in common}
        self.assertIn("/ → /services", seqs)

        # Top entry/exit pages computed from sessions.
        entries = {row["page_path"] for row in payload["top_entry_pages"]}
        self.assertIn("/", entries)
        self.assertEqual(payload["data_source"]["kind"], "raw_events")

    def test_empty_log_returns_pending(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="phase18c_empty_"))
        payload = _build_analytics_extension_payload(
            domain="example.test", webapps_root=tmp
        )
        self.assertEqual(payload["data_source"]["kind"], "pending")
        self.assertEqual(payload["summary"], {})


if __name__ == "__main__":
    unittest.main()
