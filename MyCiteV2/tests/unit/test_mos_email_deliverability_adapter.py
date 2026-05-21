"""Tests for MosDatumEmailDeliverabilityAdapter (Email tab MOS backing)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.fnd_email_deliverability import (
    EVENT_KEYS,
    SCHEMA,
    MosDatumEmailDeliverabilityAdapter,
)


class DeliverabilityAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "mos.sqlite3"
        self.adapter = MosDatumEmailDeliverabilityAdapter(
            authority_db_file=self.db,
            tenant_id="tenant",
            msn_id="test-msn",
        )

    # --- gap path: no doc ⇒ available=False --------------------------

    def test_load_when_no_doc_returns_unavailable_zero_shape(self) -> None:
        rollup = self.adapter.load_rollup(domain="example.com")
        # The Email tab branches on `available` — zero counts must NOT
        # be confused with "pipeline not wired yet".
        self.assertEqual(rollup["available"], False)
        self.assertEqual(rollup["schema"], SCHEMA)
        for key in (
            "send_count", "delivery_count", "bounce_count",
            "complaint_count", "open_count", "click_count",
        ):
            self.assertEqual(rollup[key], 0)
        self.assertEqual(rollup["bounce_rate"], 0.0)
        self.assertEqual(rollup["complaint_rate"], 0.0)
        self.assertEqual(rollup["by_day"], [])

    # --- happy path --------------------------------------------------

    def _save_three_days(self) -> None:
        self.adapter.save_rollup(
            domain="example.com",
            by_day=[
                {"date": "2026-05-18", "send": 10, "delivery": 10, "bounce": 0,
                 "complaint": 0, "open": 4, "click": 1},
                {"date": "2026-05-19", "send": 20, "delivery": 18, "bounce": 2,
                 "complaint": 0, "open": 7, "click": 3},
                {"date": "2026-05-20", "send": 30, "delivery": 28, "bounce": 1,
                 "complaint": 1, "open": 12, "click": 5},
            ],
        )

    def test_load_full_window_totals_and_rates(self) -> None:
        self._save_three_days()
        rollup = self.adapter.load_rollup(domain="example.com")
        self.assertTrue(rollup["available"])
        self.assertEqual(rollup["send_count"],      60)
        self.assertEqual(rollup["delivery_count"],  56)
        self.assertEqual(rollup["bounce_count"],     3)
        self.assertEqual(rollup["complaint_count"],  1)
        # bounce_rate = 3 / 60 = 0.05
        self.assertAlmostEqual(rollup["bounce_rate"], 0.05, places=4)
        self.assertAlmostEqual(rollup["complaint_rate"], 1 / 60, places=4)
        self.assertEqual(len(rollup["by_day"]), 3)

    def test_load_period_filter_half_open(self) -> None:
        # Half-open [from, to): include 2026-05-19 only.
        self._save_three_days()
        rollup = self.adapter.load_rollup(
            domain="example.com",
            period=("2026-05-19", "2026-05-20"),
        )
        self.assertTrue(rollup["available"])
        self.assertEqual(rollup["send_count"], 20)
        self.assertEqual(len(rollup["by_day"]), 1)
        self.assertEqual(rollup["by_day"][0]["date"], "2026-05-19")

    def test_load_period_empty_window_returns_zero_rates_not_div_by_zero(self) -> None:
        self._save_three_days()
        rollup = self.adapter.load_rollup(
            domain="example.com",
            period=("2026-01-01", "2026-01-02"),  # no events
        )
        # Doc exists ⇒ available=True even though counts are zero.
        self.assertTrue(rollup["available"])
        self.assertEqual(rollup["send_count"], 0)
        self.assertEqual(rollup["bounce_rate"], 0.0)
        self.assertEqual(rollup["complaint_rate"], 0.0)

    def test_save_dedupes_by_date(self) -> None:
        self.adapter.save_rollup(
            domain="example.com",
            by_day=[
                {"date": "2026-05-20", "send": 10, "delivery": 10, "bounce": 0,
                 "complaint": 0, "open": 0, "click": 0},
                {"date": "2026-05-20", "send": 99, "delivery": 99, "bounce": 0,
                 "complaint": 0, "open": 0, "click": 0},  # last write wins
            ],
        )
        rollup = self.adapter.load_rollup(domain="example.com")
        self.assertEqual(len(rollup["by_day"]), 1)
        self.assertEqual(rollup["by_day"][0]["send"], 99)
        self.assertEqual(rollup["send_count"], 99)

    def test_event_keys_constant_matches_schema_layout(self) -> None:
        # Guard against silent key drift between adapter and tests.
        self.assertEqual(
            EVENT_KEYS,
            ("send", "delivery", "bounce", "complaint", "open", "click"),
        )


if __name__ == "__main__":
    unittest.main()
