"""Phase 18a — legacy analytics NDJSON transpose tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.analytics import EVENT_SCHEMA
from MyCiteV2.scripts.transpose_legacy_analytics_events import (
    LEGACY_SCHEMA,
    _transpose_file,
)


def _build_legacy_layout():
    tmp = Path(tempfile.mkdtemp(prefix="phase18a_transpose_"))
    events_dir = (
        tmp
        / "clients"
        / "fruitfulnetworkdevelopment.com"
        / "analytics"
        / "events"
    )
    events_dir.mkdir(parents=True)
    return tmp, events_dir


def _write_legacy(events_dir: Path, name: str, rows: list[dict]) -> Path:
    path = events_dir / name
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return path


def _legacy_row(**overrides) -> dict:
    base = {
        "schema": LEGACY_SCHEMA,
        "domain": "fruitfulnetworkdevelopment.com",
        "event_type": "page_view",
        "path": "/",
        "timestamp": "2026-04-01T01:15:53.449Z",
        "session_id": "sid-legacy-abc",
        "title": "Fruitful Network Development",
        "referrer": "https://google.com/?q=fnd",
        "host": "www.fruitfulnetworkdevelopment.com",
        "remote_addr": "192.0.2.10",
        "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1)",
        "received_at": "2026-04-01T01:15:42.265933+00:00",
    }
    base.update(overrides)
    return base


class LegacyTransposeTests(unittest.TestCase):
    def test_legacy_row_transposes_to_v2(self) -> None:
        _, events_dir = _build_legacy_layout()
        path = _write_legacy(events_dir, "2026-04.ndjson", [_legacy_row()])
        seen, out = _transpose_file(path, site_id="fnd")
        self.assertEqual(seen, 1)
        self.assertEqual(out, 1)
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(rows[0]["schema"], EVENT_SCHEMA)
        self.assertEqual(rows[0]["page_path"], "/")
        self.assertEqual(rows[0]["session_id"], "sid-legacy-abc")
        self.assertEqual(rows[0]["referrer_domain"], "google.com")
        self.assertTrue(rows[0]["ip_hash"])  # IP got hashed
        self.assertEqual(rows[0]["ip_prefix"], "192.0.2.0/24")
        self.assertTrue(rows[0]["is_bot"])
        self.assertEqual(rows[0]["bot_class"], "verified_search")
        # Legacy file preserved as a sibling.
        self.assertTrue(path.with_suffix(".legacy.ndjson").exists())

    def test_missing_fields_land_empty(self) -> None:
        _, events_dir = _build_legacy_layout()
        # Bare-minimum legacy row: only event_type + path + timestamp +
        # a UA so the UA-regex doesn't flag the row as likely_bot
        # (an empty UA is treated as automation by design — see
        # bot_detection.classify_user_agent).
        bare = {
            "schema": LEGACY_SCHEMA,
            "event_type": "page_view",
            "path": "/about",
            "timestamp": "2026-04-02T00:00:00Z",
            "session_id": "",
            "user_agent": "Mozilla/5.0 Chrome/130.0",
        }
        path = _write_legacy(events_dir, "2026-04.ndjson", [bare])
        _transpose_file(path, site_id="fnd")
        row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(row["page_path"], "/about")
        self.assertEqual(row["referrer_domain"], "")
        self.assertEqual(row["ip_hash"], "")
        self.assertFalse(row["is_bot"])

    def test_idempotent_does_not_double_transpose(self) -> None:
        _, events_dir = _build_legacy_layout()
        path = _write_legacy(events_dir, "2026-04.ndjson", [_legacy_row()])
        first = _transpose_file(path, site_id="fnd")
        second = _transpose_file(path, site_id="fnd")
        self.assertEqual(first, (1, 1))
        self.assertEqual(second, (0, 0))  # skipped — .legacy.ndjson exists

    def test_pre_existing_v2_row_passes_through_unchanged(self) -> None:
        _, events_dir = _build_legacy_layout()
        v2_row = {"schema": EVENT_SCHEMA, "event_type": "page_view", "page_path": "/"}
        legacy_row = _legacy_row()
        path = _write_legacy(events_dir, "2026-04.ndjson", [v2_row, legacy_row])
        _transpose_file(path, site_id="fnd")
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # Two rows: the v2 row untouched + the legacy row transposed.
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["page_path"], "/")
        self.assertEqual(rows[1]["page_path"], "/")
        self.assertEqual(rows[1]["schema"], EVENT_SCHEMA)


if __name__ == "__main__":
    unittest.main()
