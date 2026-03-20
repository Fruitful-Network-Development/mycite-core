from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SystemPageCompositionTests(unittest.TestCase):
    def test_data_tool_shell_has_workbench_inspector_mounts(self) -> None:
        shell = REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/partials/data_tool_shell.html"
        text = shell.read_text(encoding="utf-8")
        self.assertIn('id="dtAnthologyInspector"', text)
        self.assertIn('id="dtAnthologyInspectorBody"', text)
        self.assertIn('id="dtAnthologyInvMount"', text)
        self.assertIn("data-tool__workbenchWithInspector", text)
        self.assertIn('option value="grouped"', text)

    def test_system_local_resources_defaults_to_workspace_tab(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            self.assertIn('id="lrTabWorkspace"', text)
            self.assertIn('data-lr-tab="workspace"', text)
            self.assertIn('id="lrPanelWorkspace"', text)
            self.assertIn('class="lr-workbench__tab is-active" data-lr-tab="workspace" id="lrTabWorkspace"', text)

    def test_system_inheritance_workbench_markup(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            self.assertIn('id="inhWorkbenchRoot"', text)
            self.assertIn("inheritance_workbench.js", text)
            self.assertIn('id="inheritanceSourceList"', text)
            self.assertIn('id="inheritanceResourceList"', text)

    def test_inherited_inventory_api_exposes_grouped_by_source(self) -> None:
        """Backend support for inheritance UI grouping (no regression)."""
        data_workspace = REPO_ROOT / "portals/_shared/portal/api/data_workspace.py"
        body = data_workspace.read_text(encoding="utf-8")
        self.assertIn('"grouped_by_source"', body)
        self.assertIn("_group_inherited_index", body)


if __name__ == "__main__":
    unittest.main()
