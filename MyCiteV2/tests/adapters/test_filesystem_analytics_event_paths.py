from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import AnalyticsEventPathResolver


class AnalyticsEventPathResolverCanonicalTests(unittest.TestCase):
    """Canonical mode: per-grantee flat files under a single analytics_root."""

    def test_resolves_flat_filename_under_analytics_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolution = AnalyticsEventPathResolver(analytics_root=root).resolve_events_file(
                domain="TrappFamilyFarm.com",
                year_month="2026-04",
            )

            self.assertEqual(
                resolution.events_file,
                root / "analytics.trappfamilyfarm.com.events.2026-04.ndjson",
            )
            self.assertEqual(resolution.warnings, ())

    def test_appends_payload_to_canonical_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolution = AnalyticsEventPathResolver(analytics_root=root).append_payload(
                domain="trappfamilyfarm.com",
                year_month="2026-04",
                payload={"schema": "test", "path": "/"},
            )

            self.assertTrue(resolution.events_file.exists())
            self.assertEqual(
                resolution.events_file.read_text(encoding="utf-8").strip(),
                '{"path":"/","schema":"test"}',
            )

    def test_iter_domain_event_files_returns_files_newest_first(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolver = AnalyticsEventPathResolver(analytics_root=root)
            for ym in ("2026-02", "2026-03", "2026-04"):
                resolver.append_payload(
                    domain="trappfamilyfarm.com",
                    year_month=ym,
                    payload={"schema": "test", "ym": ym},
                )
            files = resolver.iter_domain_event_files("trappfamilyfarm.com")
            self.assertEqual(
                [f.name for f in files],
                [
                    "analytics.trappfamilyfarm.com.events.2026-04.ndjson",
                    "analytics.trappfamilyfarm.com.events.2026-03.ndjson",
                    "analytics.trappfamilyfarm.com.events.2026-02.ndjson",
                ],
            )

    def test_discover_domains(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolver = AnalyticsEventPathResolver(analytics_root=root)
            for dom in ("trappfamilyfarm.com", "cuyahogavalleycountrysideconservancy.org"):
                resolver.append_payload(
                    domain=dom, year_month="2026-04", payload={"schema": "t"}
                )
            self.assertEqual(
                resolver.discover_domains(),
                [
                    "cuyahogavalleycountrysideconservancy.org",
                    "trappfamilyfarm.com",
                ],
            )

    def test_env_var_default(self) -> None:
        import os
        with TemporaryDirectory() as temp_dir:
            old = os.environ.get("MYCITE_ANALYTICS_ROOT")
            os.environ["MYCITE_ANALYTICS_ROOT"] = temp_dir
            try:
                resolver = AnalyticsEventPathResolver()
                self.assertEqual(resolver.analytics_root, Path(temp_dir))
            finally:
                if old is None:
                    del os.environ["MYCITE_ANALYTICS_ROOT"]
                else:
                    os.environ["MYCITE_ANALYTICS_ROOT"] = old


class AnalyticsEventPathResolverLegacyTests(unittest.TestCase):
    """Legacy mode: <webapps>/clients/<domain>/analytics/events/<YM>.ndjson.

    Kept for any pre-2026-05-16 reader that hasn't switched yet.
    """

    def test_legacy_mode_resolves_under_clients_domain_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolution = AnalyticsEventPathResolver(webapps_root=root).resolve_events_file(
                domain="TrappFamilyFarm.com",
                year_month="2026-04",
            )

            self.assertEqual(
                resolution.events_file,
                root / "clients" / "trappfamilyfarm.com" / "analytics" / "events" / "2026-04.ndjson",
            )

    def test_legacy_mode_appends_payload(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolution = AnalyticsEventPathResolver(webapps_root=root).append_payload(
                domain="trappfamilyfarm.com",
                year_month="2026-04",
                payload={"schema": "test", "path": "/"},
            )
            self.assertTrue(resolution.events_file.exists())


class AnalyticsEventPathResolverValidationTests(unittest.TestCase):
    def test_rejects_unsafe_domain_or_month(self) -> None:
        with TemporaryDirectory() as temp_dir:
            resolver = AnalyticsEventPathResolver(analytics_root=Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "plain domain"):
                resolver.resolve_events_file(domain="../trappfamilyfarm.com", year_month="2026-04")
            with self.assertRaisesRegex(ValueError, "YYYY-MM"):
                resolver.resolve_events_file(domain="trappfamilyfarm.com", year_month="04-2026")


if __name__ == "__main__":
    unittest.main()
