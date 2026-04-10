from __future__ import annotations

import importlib
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_internal_sources_module():
    portals_root = Path(__file__).resolve().parents[1] / "instances"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.application.internal_sources")


class InternalSourcesTests(unittest.TestCase):
    def test_derive_client_analytics_paths(self):
        module = _load_internal_sources_module()
        derived = module.derive_client_analytics_paths("/srv/webapps/example.com/frontend")
        self.assertEqual(str(derived["client_root"]), "/srv/webapps/example.com")
        self.assertEqual(str(derived["analytics_root"]), "/srv/webapps/example.com/analytics")
        self.assertTrue(str(derived["access_log"]).endswith("/analytics/nginx/access.log"))
        self.assertTrue(str(derived["events_file"]).endswith(".ndjson"))
        self.assertEqual(len(derived.get("events_file_candidates") or []), 2)
        self.assertIn("/analytics/evnts/", str((derived.get("events_file_legacy"))))

    def test_read_internal_file_detects_kinds_and_counts(self):
        module = _load_internal_sources_module()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "clients"
            path = root / "demo" / "analytics" / "nginx" / "access.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '127.0.0.1 - - [24/Mar/2026:00:00:01 +0000] "GET / HTTP/1.1" 200 123\n'
                '127.0.0.1 - - [24/Mar/2026:00:00:02 +0000] "GET /x HTTP/1.1" 404 12\n',
                encoding="utf-8",
            )
            previous_roots = os.environ.get("MYCITE_INTERNAL_FILE_ROOTS")
            os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = str(root)
            try:
                result = module.read_internal_file(path, kind_hint="nginx_access_log")
            finally:
                if previous_roots is None:
                    os.environ.pop("MYCITE_INTERNAL_FILE_ROOTS", None)
                else:
                    os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = previous_roots
            self.assertTrue(result.ok)
            self.assertEqual(result.record_count, 2)
            self.assertEqual((result.summary or {}).get("response_breakdown", {}).get("2xx"), 1)
            self.assertEqual((result.summary or {}).get("response_breakdown", {}).get("4xx"), 1)

    def test_access_log_summary_includes_bot_and_probe_signals(self):
        module = _load_internal_sources_module()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "clients"
            path = root / "demo" / "analytics" / "nginx" / "access.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '127.0.0.1 - - [24/Mar/2026:00:00:01 +0000] "GET / HTTP/1.1" 200 123 "-" "Mozilla/5.0"\n'
                '127.0.0.2 - - [24/Mar/2026:00:00:02 +0000] "GET /wp-admin/setup-config.php HTTP/1.1" 404 12 "-" "Mozilla/5.0"\n'
                '127.0.0.3 - - [24/Mar/2026:00:00:03 +0000] "GET /robots.txt HTTP/1.1" 404 12 "-" "AhrefsBot/7.0"\n',
                encoding="utf-8",
            )
            previous_roots = os.environ.get("MYCITE_INTERNAL_FILE_ROOTS")
            os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = str(root)
            try:
                result = module.read_internal_file(path, kind_hint="nginx_access_log")
            finally:
                if previous_roots is None:
                    os.environ.pop("MYCITE_INTERNAL_FILE_ROOTS", None)
                else:
                    os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = previous_roots
            summary = result.summary or {}
            self.assertEqual(summary.get("suspicious_probe_count"), 1)
            self.assertEqual(summary.get("robots_404_count"), 1)
            self.assertGreater(summary.get("bot_share") or 0, 0)

    def test_access_log_summary_prefers_real_pages_and_tracks_truncation(self):
        module = _load_internal_sources_module()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "clients"
            path = root / "demo" / "analytics" / "nginx" / "access.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '127.0.0.1 - - [24/Mar/2026:00:00:01 +0000] "GET /xmlrpc.php HTTP/1.1" 404 12 "-" "Mozilla/5.0"\n'
                '127.0.0.1 - - [24/Mar/2026:00:00:02 +0000] "GET /real-page HTTP/1.1" 200 120 "-" "Mozilla/5.0"\n'
                '127.0.0.1 - - [24/Mar/2026:00:00:03 +0000] "GET /real-page HTTP/1.1" 200 120 "-" "Mozilla/5.0"\n',
                encoding="utf-8",
            )
            previous_roots = os.environ.get("MYCITE_INTERNAL_FILE_ROOTS")
            os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = str(root)
            try:
                result = module.read_internal_file(path, kind_hint="nginx_access_log", max_lines=2)
            finally:
                if previous_roots is None:
                    os.environ.pop("MYCITE_INTERNAL_FILE_ROOTS", None)
                else:
                    os.environ["MYCITE_INTERNAL_FILE_ROOTS"] = previous_roots
            summary = result.summary or {}
            self.assertTrue(summary.get("truncated"))
            self.assertEqual(summary.get("raw_line_count"), 3)
            self.assertEqual(summary.get("parsed_line_count"), 2)
            top_pages = summary.get("top_pages") or []
            self.assertEqual((top_pages[0] if top_pages else {}).get("key"), "/real-page")
            self.assertEqual(summary.get("real_page_requests_30d"), 2)


if __name__ == "__main__":
    unittest.main()
