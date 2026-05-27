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


if __name__ == "__main__":
    unittest.main()
