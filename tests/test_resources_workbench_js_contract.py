"""Static checks for Resources workbench JS structure (no duplicate shell tab drivers)."""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResourcesWorkbenchJsContractTests(unittest.TestCase):
    def test_resources_loader_and_state_are_singular(self) -> None:
        js = (
            REPO_ROOT
            / "portals/_shared/runtime/flavors/fnd/portal/ui/static/tools/data_tool.js"
        ).read_text(encoding="utf-8")
        self.assertIn("loadSystemResourceWorkbench", js)
        self.assertIn("resourcesWorkbenchState", js)
        self.assertIn("setDtWorkspaceTab", js)
        self.assertNotIn("WORKSPACE_TAB_STORAGE_KEY", js)
        self.assertNotIn("dtWorkspaceTabButtons", js)
        self.assertIn("dtResourcesSourceMenu", js)
        self.assertIn("data-resources-file-key", js)
        self.assertIn("data-resources-task", js)
        self.assertIn("renderAbstractionChainInto", js)
        self.assertIn("groupedResourceRows", js)
        self.assertIn("dtResourcesLayers", js)
        self.assertIn("overlay collision on reserved base id:", js)
        self.assertNotIn("Local Resources", js)


if __name__ == "__main__":
    unittest.main()
