"""Release-coherence primitive: healthz must surface running-vs-on-disk drift.

Locks `_code_coherence` (the stale-in-memory detector added after the 2026-05
contact-form outage, where the live worker ran old code while disk moved ahead).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import MyCiteV2.instances._shared.portal_host.app as app


class CodeCoherenceTests(unittest.TestCase):
    def _coherence(self, running: str, head: str | None) -> dict:
        with patch.object(app, "_current_git_head_build_id", return_value=head):
            return app._code_coherence(running)

    def test_current_when_running_equals_head(self) -> None:
        self.assertEqual(self._coherence("git-abc1234", "git-abc1234")["status"], "current")

    def test_current_when_deploy_label_embeds_head_sha(self) -> None:
        # The deploy script stamps ``<ts>-<label>-git<sha>``; coherence must
        # recognize the embedded sha so a stamped build still reads "current".
        result = self._coherence("20260527-000055-manual-update-gitabc1234", "git-abc1234")
        self.assertEqual(result["status"], "current")

    def test_stale_when_running_git_build_differs_from_head(self) -> None:
        result = self._coherence("git-10d132b", "git-26d8c07")
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["disk_head"], "git-26d8c07")

    def test_pinned_when_nongit_label_without_head_sha(self) -> None:
        # An opaque deploy label that does NOT embed the sha can't be equated to
        # HEAD — report "pinned" + the disk head for the operator to eyeball.
        self.assertEqual(
            self._coherence("20260514-000401-visual-verify", "git-26d8c07")["status"],
            "pinned",
        )

    def test_unknown_when_head_unavailable(self) -> None:
        self.assertEqual(self._coherence("git-abc1234", None)["status"], "unknown")


class SourceFreshnessTests(unittest.TestCase):
    """Locks the mtime-based stale-worker detector: it catches "disk source newer
    than the running worker" — the --preload deploy-without-restart failure mode
    that the build-id string compare in _code_coherence structurally cannot see."""

    def _freshness(self, baseline: float, disk: float) -> dict:
        with patch.object(app, "_newest_source_mtime", return_value=disk):
            return app._source_freshness(baseline)

    def test_fresh_when_disk_not_newer_than_baseline(self) -> None:
        self.assertEqual(self._freshness(1000.0, 1000.0)["status"], "fresh")

    def test_fresh_within_tolerance(self) -> None:
        # mtime granularity / same-second deploy stays fresh.
        disk = 1000.0 + (app._FRESHNESS_TOLERANCE_SECONDS / 2)
        self.assertEqual(self._freshness(1000.0, disk)["status"], "fresh")

    def test_stale_when_disk_newer_beyond_tolerance(self) -> None:
        disk = 1000.0 + app._FRESHNESS_TOLERANCE_SECONDS + 1.0
        self.assertEqual(self._freshness(1000.0, disk)["status"], "stale")

    def test_unknown_when_no_baseline(self) -> None:
        self.assertEqual(self._freshness(0.0, 1000.0)["status"], "unknown")

    def test_build_health_unhealthy_when_source_stale(self) -> None:
        from unittest.mock import MagicMock

        cfg = MagicMock()
        cfg.to_public_dict.return_value = {}
        with patch.object(app, "_shell_asset_files_from_manifest", return_value=[]), patch.object(
            app, "_source_freshness",
            return_value={"status": "stale", "loaded_mtime": 1.0, "disk_mtime": 9.0},
        ):
            health = app._build_health(cfg)
        self.assertFalse(health["ok"])
        self.assertEqual(health["source_freshness"]["status"], "stale")

    def test_build_health_ok_when_source_fresh(self) -> None:
        from unittest.mock import MagicMock

        cfg = MagicMock()
        cfg.to_public_dict.return_value = {}
        with patch.object(app, "_shell_asset_files_from_manifest", return_value=[]), patch.object(
            app, "_source_freshness",
            return_value={"status": "fresh", "loaded_mtime": 1.0, "disk_mtime": 1.0},
        ):
            health = app._build_health(cfg)
        self.assertTrue(health["ok"])


if __name__ == "__main__":
    unittest.main()
