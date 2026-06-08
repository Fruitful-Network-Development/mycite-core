"""Contract pins for POST /__fnd/analytics/refresh.

Post-2026-05 the route no longer persists anything to MOS. The legacy
MosDatumAnalyticsSummaryAdapter is retired (see
``docs/contracts/analytics_event_schema.md``). The route now just
invalidates the in-memory cache that fronts ``/__fnd/analytics/summary``
so the next call recomputes from the canonical NDJSON event log.

These tests pin:
  * Success path: refresh returns ok=true + an invalidated count.
  * 400 on missing domain.
  * 404 when the events directory doesn't exist for the domain.
  * No write to mos_authority.sqlite3 happens (the documents/datum_*
    tables remain unchanged across a refresh call).
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
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


def _build_minimal_mos_db(path: Path) -> None:
    """Create a stand-in mos_authority.sqlite3 with the schema columns
    the route guard checks. Tests assert this DB is unchanged after a
    refresh."""
    con = sqlite3.connect(path)
    try:
        con.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                prefix TEXT NOT NULL,
                msn_id TEXT NOT NULL,
                sandbox TEXT,
                name TEXT NOT NULL,
                version_hash TEXT NOT NULL,
                is_anchor INTEGER NOT NULL DEFAULT 0,
                origin TEXT NOT NULL DEFAULT 'local',
                legacy_alias TEXT,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE datum_document_semantics (document_id TEXT PRIMARY KEY);
            CREATE TABLE datum_row_semantics (id INTEGER PRIMARY KEY, document_id TEXT);
            """
        )
        con.commit()
    finally:
        con.close()


def _table_counts(path: Path) -> tuple[int, int, int]:
    con = sqlite3.connect(path)
    try:
        c1 = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        c2 = con.execute("SELECT COUNT(*) FROM datum_document_semantics").fetchone()[0]
        c3 = con.execute("SELECT COUNT(*) FROM datum_row_semantics").fetchone()[0]
        return c1, c2, c3
    finally:
        con.close()


@unittest.skipUnless(FLASK_AVAILABLE, "flask not installed")
class AnalyticsRefreshRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="analytics_refresh_"))
        for sub in ("public", "private", "data", "webapps"):
            (self.tmp / sub).mkdir(parents=True, exist_ok=True)
        self.private_dir = self.tmp / "private"
        self.authority_db = self.private_dir / "mos_authority.sqlite3"
        _build_minimal_mos_db(self.authority_db)

        self.domain = "example.test"

        cfg = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=self.tmp / "public",
            private_dir=self.private_dir,
            data_dir=self.tmp / "data",
            portal_domain="example.test",
            webapps_root=self.tmp / "webapps",
            authority_db_file=self.authority_db,
        )
        self.app = create_app(cfg)
        self.client = self.app.test_client()

    def test_refresh_success_bumps_cache_generation(self) -> None:
        resp = self.client.post(
            "/__fnd/analytics/refresh",
            json={"domain": self.domain},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["domain"], self.domain)
        self.assertTrue(body.get("cache_generation_bumped"))
        # The token file should now exist and have a recent mtime.
        gen_path = self.private_dir / "utilities" / "tools" / "analytics" / ".cache_gen"
        self.assertTrue(gen_path.exists(), "cache-gen file should be created on refresh")

    def test_refresh_missing_domain_returns_400(self) -> None:
        resp = self.client.post("/__fnd/analytics/refresh", json={})
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "missing_domain")

    def test_refresh_unknown_domain_is_ok(self) -> None:
        # The leaflet is authoritative; refresh just flushes the buffer + bumps
        # the cache generation, so it is idempotent and harmless for any domain
        # (no NDJSON events-directory gate any more).
        resp = self.client.post(
            "/__fnd/analytics/refresh",
            json={"domain": "no-such-domain.test"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body.get("cache_generation_bumped"))

    def test_refresh_does_not_write_to_mos(self) -> None:
        before = _table_counts(self.authority_db)
        resp = self.client.post(
            "/__fnd/analytics/refresh",
            json={"domain": self.domain},
        )
        self.assertEqual(resp.status_code, 200)
        after = _table_counts(self.authority_db)
        self.assertEqual(
            before,
            after,
            "refresh must not mutate the MOS authority DB — the legacy "
            "summary adapter is retired.",
        )


if __name__ == "__main__":
    unittest.main()
