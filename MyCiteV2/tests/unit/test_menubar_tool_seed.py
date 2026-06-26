"""The menubar search tool list is embedded in the authenticated page load (window.
__MYCITE_V2_MENUBAR_TOOLS) so the dropdown never depends on a separate XHR. Guard that the
server seed lists exactly the LIVE_TOOL_IDS allow-list with a usable route."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import _menubar_tool_seed
from MyCiteV2.instances._shared.runtime.portal_palette_runtime import LIVE_TOOL_IDS


class MenubarToolSeedTests(unittest.TestCase):
    def test_seed_lists_live_tools_with_routes(self) -> None:
        seed = _menubar_tool_seed()
        self.assertEqual({t["tool_id"] for t in seed}, set(LIVE_TOOL_IDS))
        for t in seed:
            self.assertTrue(t.get("label"), f"{t['tool_id']} missing label")
            self.assertTrue(t.get("route"), f"{t['tool_id']} missing route")


if __name__ == "__main__":
    unittest.main()
