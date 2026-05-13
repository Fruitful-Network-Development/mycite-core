"""Tests for MosDatumAnalyticsSummaryAdapter (Analytics tab MOS backing)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.fnd_analytics_summary import (
    MAX_RECENT_EVENTS,
    MosDatumAnalyticsSummaryAdapter,
    SCHEMA,
)


class AnalyticsAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "mos.sqlite3"
        self.adapter = MosDatumAnalyticsSummaryAdapter(
            authority_db_file=self.db,
            tenant_id="tenant",
            msn_id="test-msn",
        )

    def test_load_returns_none_when_missing(self) -> None:
        self.assertIsNone(self.adapter.load_summary(domain="example.com"))

    def test_save_then_load_round_trips(self) -> None:
        self.adapter.save_summary(
            domain="example.com",
            window_months=3,
            counts={"page_view": 42, "form_submit": 5, "ops_probe": 7, "other": 1},
            recent_events=[
                {"event_type": "page_view", "path": "/", "timestamp": "2026-05-01T00:00:00Z"},
                {"event_type": "form_submit", "path": "/contact", "timestamp": "2026-05-02T00:00:00Z"},
            ],
        )
        loaded = self.adapter.load_summary(domain="example.com")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["schema"], SCHEMA)
        self.assertEqual(loaded["domain"], "example.com")
        self.assertEqual(loaded["window_months"], 3)
        self.assertEqual(loaded["summary"]["page_view"], 42)
        self.assertEqual(loaded["summary"]["form_submit"], 5)
        self.assertEqual(len(loaded["recent_events"]), 2)
        self.assertEqual(loaded["recent_events"][0]["event_type"], "page_view")

    def test_save_caps_recent_events(self) -> None:
        events = [
            {"event_type": "page_view", "path": f"/{i}", "timestamp": f"t-{i}"}
            for i in range(MAX_RECENT_EVENTS + 10)
        ]
        self.adapter.save_summary(
            domain="example.com",
            window_months=3,
            counts={"page_view": MAX_RECENT_EVENTS + 10, "form_submit": 0, "ops_probe": 0, "other": 0},
            recent_events=events,
        )
        loaded = self.adapter.load_summary(domain="example.com")
        assert loaded is not None
        self.assertEqual(len(loaded["recent_events"]), MAX_RECENT_EVENTS)

    def test_save_advances_version_hash(self) -> None:
        self.adapter.save_summary(
            domain="ex.com",
            window_months=3,
            counts={"page_view": 1, "form_submit": 0, "ops_probe": 0, "other": 0},
            recent_events=[],
        )
        first_doc = self.adapter._find_doc(domain="ex.com")  # type: ignore[attr-defined]
        assert first_doc is not None
        self.adapter.save_summary(
            domain="ex.com",
            window_months=3,
            counts={"page_view": 2, "form_submit": 0, "ops_probe": 0, "other": 0},
            recent_events=[],
        )
        second_doc = self.adapter._find_doc(domain="ex.com")  # type: ignore[attr-defined]
        assert second_doc is not None
        self.assertNotEqual(first_doc.document_id, second_doc.document_id)


if __name__ == "__main__":
    unittest.main()
