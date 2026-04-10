from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import AnalyticsEventPathResolver


class AnalyticsEventPathResolverTests(unittest.TestCase):
    def test_resolves_events_under_clients_domain_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolution = AnalyticsEventPathResolver(root).resolve_events_file(
                domain="TrappFamilyFarm.com",
                year_month="2026-04",
            )

            self.assertEqual(
                resolution.events_file,
                root / "clients" / "trappfamilyfarm.com" / "analytics" / "events" / "2026-04.ndjson",
            )
            self.assertNotEqual(
                resolution.events_file,
                root / "trappfamilyfarm.com" / "analytics" / "events" / "2026-04.ndjson",
            )
            self.assertEqual(resolution.warnings, ())

    def test_warns_when_legacy_root_file_exists_but_stays_canonical(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "fruitfulnetworkdevelopment.com" / "analytics" / "events"
            legacy.mkdir(parents=True)
            (legacy / "2026-04.ndjson").write_text("{}\n", encoding="utf-8")

            resolution = AnalyticsEventPathResolver(root).resolve_events_file(
                domain="fruitfulnetworkdevelopment.com",
                year_month="2026-04",
            )

            self.assertEqual(
                resolution.events_file,
                root / "clients" / "fruitfulnetworkdevelopment.com" / "analytics" / "events" / "2026-04.ndjson",
            )
            self.assertIn("Legacy root analytics file exists", " ".join(resolution.warnings))

    def test_appends_payload_only_to_clients_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolution = AnalyticsEventPathResolver(root).append_payload(
                domain="trappfamilyfarm.com",
                year_month="2026-04",
                payload={"schema": "test", "path": "/"},
            )

            self.assertTrue(resolution.events_file.exists())
            self.assertEqual(
                resolution.events_file.read_text(encoding="utf-8").strip(),
                '{"path":"/","schema":"test"}',
            )
            self.assertFalse((root / "trappfamilyfarm.com" / "analytics" / "events" / "2026-04.ndjson").exists())

    def test_rejects_unsafe_domain_or_month(self) -> None:
        with TemporaryDirectory() as temp_dir:
            resolver = AnalyticsEventPathResolver(Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "plain domain"):
                resolver.resolve_events_file(domain="../trappfamilyfarm.com", year_month="2026-04")
            with self.assertRaisesRegex(ValueError, "YYYY-MM"):
                resolver.resolve_events_file(domain="trappfamilyfarm.com", year_month="04-2026")


if __name__ == "__main__":
    unittest.main()
