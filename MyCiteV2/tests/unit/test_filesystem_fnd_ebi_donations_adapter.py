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

from MyCiteV2.packages.adapters.filesystem.fnd_ebi_donations_read_only import (
    FilesystemFndEbiDonationsReadOnlyAdapter,
)
from MyCiteV2.packages.ports.fnd_ebi_donations_read_only import FndEbiDonationsReadOnlyRequest

NOW_UTC = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)


def _write_profile(
    private_dir: Path,
    *,
    domain: str,
    donations_enabled: bool = True,
    log_path: str | None = None,
) -> None:
    tool_root = private_dir / "utilities" / "tools" / "fnd-ebi"
    tool_root.mkdir(parents=True, exist_ok=True)
    profile: dict = {
        "schema": "mycite.service_tool.fnd_ebi.profile.v1",
        "domain": domain,
        "site_root": f"/srv/webapps/clients/{domain}/frontend",
    }
    if log_path is not None:
        profile["donations"] = {
            "enabled": donations_enabled,
            "log_path": log_path,
        }
    elif donations_enabled:
        profile["donations"] = {"enabled": True}

    slug = domain.split(".", 1)[0]
    (tool_root / f"fnd-ebi.{slug}.json").write_text(
        json.dumps(profile) + "\n",
        encoding="utf-8",
    )


class FilesystemFndEbiDonationsAdapterTests(unittest.TestCase):

    def test_returns_disabled_state_when_donations_not_enabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            _write_profile(private_dir, domain="fruitfulnetworkdevelopment.com", donations_enabled=False)

            adapter = FilesystemFndEbiDonationsReadOnlyAdapter(
                private_dir, now_utc=NOW_UTC
            )
            result = adapter.read_fnd_ebi_donations_read_only(
                FndEbiDonationsReadOnlyRequest(portal_tenant_id="fnd")
            )
            profiles = list(result.source.payload.get("profiles") or [])
            self.assertEqual(len(profiles), 1)
            profile = profiles[0]
            self.assertFalse(profile["donations_enabled"])
            self.assertEqual(profile["donations_log"]["state"], "unavailable")
            self.assertEqual(profile["donations_summary"], {})

    def test_returns_ready_state_when_log_exists_and_is_parseable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            log_dir = root / "donations"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "test-donation_log.ndjson"
            record = {
                "created_at": "2026-05-02T10:00:00+00:00",
                "status": "COMPLETED",
                "amount": "50.00",
                "currency": "USD",
            }
            log_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

            _write_profile(
                private_dir,
                domain="cuyahogavalleycountrysideconservancy.org",
                donations_enabled=True,
                log_path=str(log_file),
            )

            adapter = FilesystemFndEbiDonationsReadOnlyAdapter(
                private_dir, now_utc=NOW_UTC
            )
            result = adapter.read_fnd_ebi_donations_read_only(
                FndEbiDonationsReadOnlyRequest(
                    portal_tenant_id="fnd",
                    selected_domain="cuyahogavalleycountrysideconservancy.org",
                )
            )
            profiles = list(result.source.payload.get("profiles") or [])
            self.assertEqual(len(profiles), 1)
            profile = profiles[0]
            self.assertTrue(profile["donations_enabled"])
            self.assertEqual(profile["donations_log"]["state"], "ready")
            self.assertEqual(profile["donations_summary"]["record_count"], 1)
            self.assertEqual(profile["donations_summary"]["donations_7d"], 1)
            self.assertEqual(profile["donations_summary"]["donations_30d"], 1)
            self.assertEqual(profile["donations_summary"]["status_counts"]["COMPLETED"], 1)
            self.assertEqual(profile["donations_summary"]["total_amount_30d_usd"], 50.0)

    def test_returns_missing_state_when_log_file_does_not_exist(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            _write_profile(
                private_dir,
                domain="cuyahogavalleycountrysideconservancy.org",
                donations_enabled=True,
                log_path="/nonexistent/path/donation_log.ndjson",
            )

            adapter = FilesystemFndEbiDonationsReadOnlyAdapter(
                private_dir, now_utc=NOW_UTC
            )
            result = adapter.read_fnd_ebi_donations_read_only(
                FndEbiDonationsReadOnlyRequest(portal_tenant_id="fnd")
            )
            profiles = list(result.source.payload.get("profiles") or [])
            self.assertEqual(len(profiles), 1)
            profile = profiles[0]
            self.assertTrue(profile["donations_enabled"])
            self.assertEqual(profile["donations_log"]["state"], "missing")
            self.assertFalse(profile["donations_log"]["exists"])

    def test_degrades_gracefully_on_malformed_ndjson_lines(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            log_dir = root / "donations"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "test-donation_log.ndjson"
            valid_record = {
                "created_at": "2026-05-01T10:00:00+00:00",
                "status": "COMPLETED",
                "amount": "25.00",
            }
            content = (
                json.dumps(valid_record) + "\n"
                + "NOT VALID JSON\n"
                + '{"not_closed": \n'
            )
            log_file.write_text(content, encoding="utf-8")

            _write_profile(
                private_dir,
                domain="cuyahogavalleycountrysideconservancy.org",
                donations_enabled=True,
                log_path=str(log_file),
            )

            adapter = FilesystemFndEbiDonationsReadOnlyAdapter(
                private_dir, now_utc=NOW_UTC
            )
            result = adapter.read_fnd_ebi_donations_read_only(
                FndEbiDonationsReadOnlyRequest(portal_tenant_id="fnd")
            )
            profiles = list(result.source.payload.get("profiles") or [])
            profile = profiles[0]
            summary = profile["donations_summary"]
            self.assertEqual(summary["record_count"], 1)
            self.assertEqual(summary["invalid_line_count"], 2)
            self.assertEqual(summary["donations_30d"], 1)

    def test_counts_donations_correctly_by_window(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            log_dir = root / "donations"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "test-donation_log.ndjson"

            records = [
                # within 24h
                {"created_at": "2026-05-03T10:00:00+00:00", "status": "COMPLETED", "amount": "10.00"},
                # within 7d but not 24h
                {"created_at": "2026-05-01T10:00:00+00:00", "status": "COMPLETED", "amount": "20.00"},
                # within 30d but not 7d
                {"created_at": "2026-04-10T10:00:00+00:00", "status": "PENDING", "amount": "30.00"},
                # older than 30d — should not count
                {"created_at": "2026-03-01T10:00:00+00:00", "status": "FAILED", "amount": "40.00"},
            ]
            log_file.write_text(
                "\n".join(json.dumps(r) for r in records) + "\n",
                encoding="utf-8",
            )

            _write_profile(
                private_dir,
                domain="cuyahogavalleycountrysideconservancy.org",
                donations_enabled=True,
                log_path=str(log_file),
            )

            adapter = FilesystemFndEbiDonationsReadOnlyAdapter(
                private_dir, now_utc=NOW_UTC
            )
            result = adapter.read_fnd_ebi_donations_read_only(
                FndEbiDonationsReadOnlyRequest(portal_tenant_id="fnd")
            )
            profiles = list(result.source.payload.get("profiles") or [])
            summary = profiles[0]["donations_summary"]
            self.assertEqual(summary["donations_24h"], 1)
            self.assertEqual(summary["donations_7d"], 2)
            self.assertEqual(summary["donations_30d"], 3)
            # total_amount_30d_usd: 10 + 20 + 30 = 60
            self.assertAlmostEqual(summary["total_amount_30d_usd"], 60.0, places=2)
            self.assertEqual(len(summary["trend_7d"]), 7)
            self.assertEqual(len(summary["trend_30d"]), 30)

    def test_empty_profiles_when_no_profiles_found(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir) / "private"
            private_dir.mkdir(parents=True, exist_ok=True)

            adapter = FilesystemFndEbiDonationsReadOnlyAdapter(
                private_dir, now_utc=NOW_UTC
            )
            result = adapter.read_fnd_ebi_donations_read_only(
                FndEbiDonationsReadOnlyRequest(portal_tenant_id="fnd")
            )
            profiles = list(result.source.payload.get("profiles") or [])
            self.assertEqual(profiles, [])
            warnings = list(result.source.payload.get("warnings") or [])
            self.assertTrue(any("No FND-EBI profiles" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
