"""Unit tests for `utilities_extensions.tolling`: grantee directory
lookup, bandwidth share computation from nginx access logs, and
auth-header → grantee resolution."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
    _parse_log_window_bytes,
    bandwidth_share_by_domain,
    bandwidth_share_for_grantee,
    domains_for_grantee,
    load_grantee_directory,
    resolve_grantee_from_headers,
)


def _write_grantee_profiles(root: Path, profiles: list[dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(profiles):
        (root / f"grantee.{p['msn_id']}.{i}.json").write_text(
            json.dumps(p), encoding="utf-8"
        )


def _write_access_log(domain_dir: Path, lines: list[str]) -> None:
    (domain_dir / "nginx").mkdir(parents=True, exist_ok=True)
    (domain_dir / "nginx" / "access.log").write_text("\n".join(lines) + "\n")


class GranteeDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="tolling_grantee_"))
        _write_grantee_profiles(self.tmp, [
            {"msn_id": "abc", "short_name": "FND",
             "domains": ["fruitfulnetworkdevelopment.com"],
             "users": ["dylan@fruitfulnetworkdevelopment.com"]},
            {"msn_id": "def", "short_name": "CVCC",
             "domains": ["cuyahogavalleycountrysideconservancy.org",
                         "cvccboard.org"],
             "users": ["board@cvcc.org"]},
        ])

    def test_load_returns_all_profiles(self) -> None:
        profiles = load_grantee_directory(self.tmp)
        self.assertEqual(len(profiles), 2)
        self.assertEqual(
            {p["msn_id"] for p in profiles},
            {"abc", "def"},
        )

    def test_domains_for_grantee_known(self) -> None:
        self.assertEqual(
            domains_for_grantee("abc", self.tmp),
            ["fruitfulnetworkdevelopment.com"],
        )
        self.assertEqual(
            sorted(domains_for_grantee("def", self.tmp)),
            ["cuyahogavalleycountrysideconservancy.org", "cvccboard.org"],
        )

    def test_domains_for_grantee_unknown(self) -> None:
        self.assertEqual(domains_for_grantee("nonexistent", self.tmp), [])

    def test_load_skips_malformed_json(self) -> None:
        (self.tmp / "grantee.broken.json").write_text("not valid json")
        profiles = load_grantee_directory(self.tmp)
        self.assertEqual(len(profiles), 2)  # the two good ones remain


class AccessLogBytesTests(unittest.TestCase):
    """`_parse_log_window_bytes` sums body_bytes_sent over a date window."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="tolling_log_"))
        self.log = self.tmp / "access.log"

    def _write(self, *lines: str) -> None:
        self.log.write_text("\n".join(lines) + "\n")

    def test_includes_lines_within_window(self) -> None:
        self._write(
            '1.2.3.4 - - [15/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 1000 "-" "-"',
            '1.2.3.4 - - [15/Apr/2026:11:00:00 +0000] "GET / HTTP/1.1" 200 2000 "-" "-"',
        )
        start = datetime(2026, 4, 15, tzinfo=timezone.utc)
        end = datetime(2026, 4, 16, tzinfo=timezone.utc)
        self.assertEqual(_parse_log_window_bytes(self.log, start, end), 3000)

    def test_excludes_lines_outside_window(self) -> None:
        self._write(
            '1.2.3.4 - - [10/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 1000 "-" "-"',
            '1.2.3.4 - - [15/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 500 "-" "-"',
            '1.2.3.4 - - [20/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 9999 "-" "-"',
        )
        start = datetime(2026, 4, 15, tzinfo=timezone.utc)
        end = datetime(2026, 4, 16, tzinfo=timezone.utc)
        self.assertEqual(_parse_log_window_bytes(self.log, start, end), 500)

    def test_end_is_exclusive(self) -> None:
        self._write(
            '1.2.3.4 - - [16/Apr/2026:00:00:00 +0000] "GET / HTTP/1.1" 200 7777 "-" "-"',
        )
        start = datetime(2026, 4, 15, tzinfo=timezone.utc)
        end = datetime(2026, 4, 16, tzinfo=timezone.utc)
        self.assertEqual(_parse_log_window_bytes(self.log, start, end), 0)

    def test_missing_file_returns_zero(self) -> None:
        self.assertEqual(
            _parse_log_window_bytes(self.tmp / "missing.log",
                                     datetime(2026, 1, 1, tzinfo=timezone.utc),
                                     datetime(2026, 2, 1, tzinfo=timezone.utc)),
            0,
        )

    def test_malformed_lines_skipped(self) -> None:
        self._write(
            'random gibberish that does not match',
            '1.2.3.4 - - [15/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 1000 "-" "-"',
            '  ',
        )
        self.assertEqual(
            _parse_log_window_bytes(self.log,
                                     datetime(2026, 4, 15, tzinfo=timezone.utc),
                                     datetime(2026, 4, 16, tzinfo=timezone.utc)),
            1000,
        )


class BandwidthShareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analytics_root = Path(tempfile.mkdtemp(prefix="tolling_share_"))
        _write_access_log(self.analytics_root / "fruitfulnetworkdevelopment.com", [
            '1.2.3.4 - - [15/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 600 "-" "-"',
            '1.2.3.4 - - [15/Apr/2026:11:00:00 +0000] "GET / HTTP/1.1" 200 400 "-" "-"',
        ])
        _write_access_log(self.analytics_root / "cvcc.org", [
            '1.2.3.4 - - [15/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 3000 "-" "-"',
        ])
        _write_access_log(self.analytics_root / "tff.com", [
            # outside window — should not count
            '1.2.3.4 - - [01/Mar/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 99999 "-" "-"',
        ])

    def test_shares_sum_to_one_when_total_nonzero(self) -> None:
        result = bandwidth_share_by_domain(
            date(2026, 4, 15), date(2026, 4, 16),
            analytics_root=self.analytics_root,
        )
        self.assertAlmostEqual(
            sum(r["share"] for r in result.values()),
            1.0,
            places=6,
        )

    def test_share_proportional_to_bytes(self) -> None:
        result = bandwidth_share_by_domain(
            date(2026, 4, 15), date(2026, 4, 16),
            analytics_root=self.analytics_root,
        )
        self.assertEqual(result["fruitfulnetworkdevelopment.com"]["bytes_sent"], 1000)
        self.assertEqual(result["cvcc.org"]["bytes_sent"], 3000)
        self.assertEqual(result["tff.com"]["bytes_sent"], 0)
        self.assertAlmostEqual(result["fruitfulnetworkdevelopment.com"]["share"], 0.25)
        self.assertAlmostEqual(result["cvcc.org"]["share"], 0.75)

    def test_zero_total_yields_zero_shares(self) -> None:
        result = bandwidth_share_by_domain(
            date(2026, 1, 1), date(2026, 2, 1),
            analytics_root=self.analytics_root,
        )
        for entry in result.values():
            self.assertEqual(entry["share"], 0.0)

    def test_for_grantee_sums_only_its_domains(self) -> None:
        fnd_csm = Path(tempfile.mkdtemp(prefix="tolling_csm_"))
        _write_grantee_profiles(fnd_csm, [
            {"msn_id": "fnd-msn", "domains": ["fruitfulnetworkdevelopment.com"]},
            {"msn_id": "cvcc-msn", "domains": ["cvcc.org"]},
        ])
        result = bandwidth_share_for_grantee(
            "fnd-msn", date(2026, 4, 15), date(2026, 4, 16),
            fnd_csm_root=fnd_csm, analytics_root=self.analytics_root,
        )
        self.assertEqual(result["bytes_sent"], 1000)
        self.assertEqual(result["domains"], ["fruitfulnetworkdevelopment.com"])
        self.assertAlmostEqual(result["share"], 0.25)


class ResolveGranteeFromHeadersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fnd_csm = Path(tempfile.mkdtemp(prefix="tolling_csm_"))
        _write_grantee_profiles(self.fnd_csm, [
            {"msn_id": "abc", "short_name": "FND",
             "domains": ["fnd.com"],
             "users": ["dylan@fnd.com", "ops@fnd.com"]},
            {"msn_id": "def", "short_name": "CVCC",
             "domains": ["cvcc.org"],
             "users": ["board@cvcc.org"]},
        ])

    def test_resolves_by_msn_id_claim(self) -> None:
        headers = {"X-Auth-Request-Grantee": "abc"}
        result = resolve_grantee_from_headers(headers, self.fnd_csm)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["msn_id"], "abc")

    def test_resolves_by_email_fallback(self) -> None:
        headers = {"X-Auth-Request-Email": "ops@fnd.com"}
        result = resolve_grantee_from_headers(headers, self.fnd_csm)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["msn_id"], "abc")

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(
            resolve_grantee_from_headers({"X-Auth-Request-Grantee": "nope"}, self.fnd_csm)
        )

    def test_no_headers_returns_none(self) -> None:
        self.assertIsNone(resolve_grantee_from_headers({}, self.fnd_csm))


if __name__ == "__main__":
    unittest.main()
