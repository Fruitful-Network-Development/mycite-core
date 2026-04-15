from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemFndEbiReadOnlyAdapter
from MyCiteV2.packages.ports.fnd_ebi_read_only import FndEbiReadOnlyRequest


def _write_profile(private_dir: Path, *, domain: str, site_root: Path) -> None:
    tool_root = private_dir / "utilities" / "tools" / "fnd-ebi"
    tool_root.mkdir(parents=True, exist_ok=True)
    (tool_root / f"fnd-ebi.{domain.split('.', 1)[0]}.json").write_text(
        json.dumps(
            {
                "schema": "mycite.service_tool.fnd_ebi.profile.v1",
                "domain": domain,
                "site_root": str(site_root),
            }
        )
        + "\n",
        encoding="utf-8",
    )


class FilesystemFndEbiReadOnlyAdapterTests(unittest.TestCase):
    def test_reads_profile_led_logs_and_events_from_site_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            client_root = webapps_root / "clients" / "fruitfulnetworkdevelopment.com"
            site_root = client_root / "site"
            analytics_root = client_root / "analytics"
            (analytics_root / "nginx").mkdir(parents=True, exist_ok=True)
            (analytics_root / "events").mkdir(parents=True, exist_ok=True)
            site_root.mkdir(parents=True, exist_ok=True)
            _write_profile(private_dir, domain="fruitfulnetworkdevelopment.com", site_root=site_root)
            (analytics_root / "nginx" / "access.log").write_text(
                '127.0.0.1 - - [12/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 120 "-" "Mozilla/5.0"\n',
                encoding="utf-8",
            )
            (analytics_root / "nginx" / "error.log").write_text(
                "[2026/04/12 10:00:00] [warn] 100#0: *1 sample warning\n",
                encoding="utf-8",
            )
            (analytics_root / "events" / "2026-04.ndjson").write_text(
                json.dumps({"event_type": "page_view", "timestamp": "2026-04-12T10:00:00+00:00", "session_id": "sess-1"}) + "\n",
                encoding="utf-8",
            )

            result = FilesystemFndEbiReadOnlyAdapter(
                private_dir,
                webapps_root=webapps_root,
                now_utc=datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc),
            ).read_fnd_ebi_read_only(
                FndEbiReadOnlyRequest(
                    portal_tenant_id="fnd",
                    year_month="2026-04",
                )
            )

            profile = (result.source.payload.get("profiles") or [])[0]
            self.assertEqual(profile["domain"], "fruitfulnetworkdevelopment.com")
            self.assertEqual(profile["access_log"]["state"], "ready")
            self.assertEqual(profile["events_file"]["state"], "ready")
            self.assertEqual(profile["traffic"]["requests_30d"], 1)
            self.assertEqual(profile["events_summary"]["events_30d"], 1)

    def test_reports_missing_events_when_canonical_month_file_is_absent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            client_root = webapps_root / "clients" / "fruitfulnetworkdevelopment.com"
            site_root = client_root / "site"
            analytics_root = client_root / "analytics"
            (analytics_root / "nginx").mkdir(parents=True, exist_ok=True)
            site_root.mkdir(parents=True, exist_ok=True)
            _write_profile(private_dir, domain="fruitfulnetworkdevelopment.com", site_root=site_root)
            (analytics_root / "nginx" / "access.log").write_text("", encoding="utf-8")
            (analytics_root / "nginx" / "error.log").write_text("", encoding="utf-8")

            result = FilesystemFndEbiReadOnlyAdapter(
                private_dir,
                webapps_root=webapps_root,
                now_utc=datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc),
            ).read_fnd_ebi_read_only(
                FndEbiReadOnlyRequest(
                    portal_tenant_id="fnd",
                    year_month="2026-04",
                )
            )

            profile = (result.source.payload.get("profiles") or [])[0]
            self.assertIn("events file is missing", " ".join(profile["warnings"]))
            self.assertTrue(str(profile["events_file"]["path"]).endswith("/analytics/events/2026-04.ndjson"))
            self.assertEqual(profile["events_file"]["state"], "missing")


if __name__ == "__main__":
    unittest.main()
