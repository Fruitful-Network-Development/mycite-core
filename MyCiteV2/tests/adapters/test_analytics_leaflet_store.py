"""AnalyticsLeafletStore + CampaignLeafletStore filesystem behavior."""

from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.analytics_ingest import ingest_batch
from MyCiteV2.packages.adapters.filesystem import (
    AnalyticsLeafletStore,
    CampaignLeafletStore,
)

ENTITY = "trapp_family_farm"
DOMAIN = "trappfamilyfarm.com"


def _raw(occurred, **kw):
    base = {
        "event_id": "evt-" + occurred + kw.get("session_id", ""),
        "received_at_utc": occurred,
        "visitor_cookie_id_hash": "cookieA",
        "session_id": "s1",
        "event_type": "page_view",
        "occurred_at_utc": occurred,
        "page_path": "/",
        "is_bot": False,
        "bot_evidence": [],
    }
    base.update(kw)
    return base


class AnalyticsLeafletStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="leaflet_store_"))
        self.store = AnalyticsLeafletStore(private_dir=self.tmp, webapps_root=self.tmp)

    def test_ingest_persists_and_path_shape(self):
        ingest_batch(self.store, ENTITY, DOMAIN, "2026-06",
                                [_raw("2026-06-01T09:00:00+00:00")])
        path = self.store.leaflet_path(ENTITY, "2026-06")
        self.assertEqual(
            path.name,
            "2026-06-00.record-analytics.trapp_family_farm-website.june_analytics.yaml",
        )
        self.assertTrue(path.exists())
        month = self.store.load_month(ENTITY, "2026-06")
        self.assertEqual(len(month["visitors"]), 1)
        self.assertEqual(month["domain"], DOMAIN)

    def test_available_periods_and_read_range(self):
        ingest_batch(self.store, ENTITY, DOMAIN, "2026-05", [_raw("2026-05-01T09:00:00+00:00")])
        ingest_batch(self.store, ENTITY, DOMAIN, "2026-06", [_raw("2026-06-01T09:00:00+00:00")])
        self.assertEqual(self.store.available_periods(ENTITY), ["2026-05", "2026-06"])
        leaflets = self.store.read_range(ENTITY, ["2026-05", "2026-06"])
        self.assertEqual(len(leaflets), 2)

    def test_cross_month_returning_visitor(self):
        ingest_batch(self.store, ENTITY, DOMAIN, "2026-05",
                                [_raw("2026-05-20T09:00:00+00:00", visitor_cookie_id_hash="X")])
        ingest_batch(self.store, ENTITY, DOMAIN, "2026-06",
                                [_raw("2026-06-02T09:00:00+00:00", visitor_cookie_id_hash="X")])
        june = self.store.load_month(ENTITY, "2026-06")
        self.assertTrue(june["visitors"][0]["returning_from_prior_month"])
        self.assertEqual(june["visitors"][0]["prior_period"], "2026-05")

    def test_concurrent_ingest_loses_nothing(self):
        # 20 threads each append a distinct session under the flock; all land.
        def worker(i):
            ingest_batch(self.store, 
                ENTITY, DOMAIN, "2026-06",
                [_raw("2026-06-01T09:00:00+00:00", session_id=f"s{i}",
                      visitor_cookie_id_hash=f"c{i}", event_id=f"e{i}")],
            )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        month = self.store.load_month(ENTITY, "2026-06")
        self.assertEqual(len(month["visitors"]), 20)


class CampaignLeafletStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="campaign_store_"))
        self.store = CampaignLeafletStore(private_dir=self.tmp, webapps_root=self.tmp)

    def test_add_list_resolve(self):
        row = self.store.add_campaign(ENTITY, DOMAIN, label="Summer flyer",
                                      target_path="campaign/summer", source="instagram",
                                      medium="qr")
        self.assertTrue(row["token"])
        self.assertEqual(row["target_path"], "/campaign/summer")  # normalized leading slash
        self.assertEqual(row["medium"], "qr")
        listed = self.store.list_campaigns(ENTITY)
        self.assertEqual(len(listed), 1)
        self.assertEqual(self.store.resolve(ENTITY, row["token"])["label"], "Summer flyer")

    def test_requires_label(self):
        with self.assertRaises(ValueError):
            self.store.add_campaign(ENTITY, DOMAIN, label="")

    def test_invalid_medium_defaults_to_link(self):
        row = self.store.add_campaign(ENTITY, DOMAIN, label="x", medium="bogus")
        self.assertEqual(row["medium"], "link")


if __name__ == "__main__":
    unittest.main()
