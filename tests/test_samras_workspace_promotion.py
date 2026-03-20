"""Tests for promoting staged SAMRAS title rows through SandboxEngine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _shared.portal.sandbox.engine import SandboxEngine
from _shared.portal.sandbox.samras_workspace_promotion import promote_staged_samras_title_entries


class SamrasWorkspacePromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "sandbox" / "resources").mkdir(parents=True, exist_ok=True)
        self.engine = SandboxEngine(data_root=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_promote_rows_only_resource_merges_staged_titles(self):
        self.engine.save_resource(
            "msn.samras.demo",
            {
                "resource_id": "msn.samras.demo",
                "resource_kind": "msn",
                "rows_by_address": {"1": ["Root"], "1-1": ["Child"]},
            },
        )
        result = promote_staged_samras_title_entries(
            self.engine,
            "msn.samras.demo",
            staged_entries=[{"parent_address": "1-1", "title": "staged_msn_leaf"}],
        )
        self.assertTrue(result.ok, result.errors)
        reread = self.engine.get_resource("msn.samras.demo")
        rows = reread.get("rows_by_address") or {}
        self.assertIn("1-1-1", rows)
        self.assertEqual(rows.get("1-1-1"), ["staged_msn_leaf"])


if __name__ == "__main__":
    unittest.main()
