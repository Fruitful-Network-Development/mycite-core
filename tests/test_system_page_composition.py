from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SystemPageCompositionTests(unittest.TestCase):
    def test_data_tool_shell_center_only_no_embedded_inspector(self) -> None:
        partial = REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/partials/data_tool_shell.html"
        text = partial.read_text(encoding="utf-8")
        self.assertNotIn('id="dtAnthologyInspector"', text)
        self.assertNotIn("data-tool__workbenchWithInspector", text)
        self.assertNotIn('class="page-tabs"', text)
        self.assertNotIn("data-dt-workspace-tab", text)
        self.assertIn('id="dtWorkbenchGrid"', text)
        self.assertIn('id="dtWorkspaceResources"', text)
        self.assertIn('id="dtResourcesTableBody"', text)
        self.assertIn('data-layout-mode="table"', text)
        self.assertIn('option value="table"', text)
        self.assertIn('option value="grouped"', text)

    def test_system_shell_owns_inspector_slots(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            self.assertIn('id="systemShellInspectorRoot"', text)
            self.assertIn('id="dtAnthologyInspectorBody"', text)
            self.assertIn('id="dtAnthologyInvMount"', text)
            self.assertIn('id="dtResourcesInspectorStack"', text)
            self.assertIn('id="dtResourcesInspectorEmpty"', text)
            self.assertIn("data-resources-inspector-panel", text)
            self.assertNotIn('id="dtResourcesInspectorMount"', text)
            self.assertIn("{% block inspector_content %}", text)
            self.assertNotIn('class="page-tabs"', text)
            self.assertNotIn("page-tab", text)

    def test_system_resources_task_sidebar_and_workbench_query_links(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            if flavor == "fnd":
                self.assertNotIn('id="resourcesTaskSection"', text)
                self.assertIn('id="systemResourceFileSection"', text)
                self.assertIn('id="systemResourceFileList"', text)
                self.assertIn('id="resourcesDatumProfile"', text)
                self.assertNotIn("Local Resources", text)
                self.assertNotIn("Inheritance", text)
            else:
                self.assertIn('id="resourcesTaskSection"', text)
                self.assertIn('id="resourcesDatumProfile"', text)
            self.assertIn("workbench=anthology", text)
            self.assertIn("workbench=resources", text)

    def test_system_local_resources_defaults_to_workspace_tab(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            if flavor == "fnd":
                self.assertNotIn('id="lrTabWorkspace"', text)
                self.assertNotIn('id="lrPanelWorkspace"', text)
                self.assertNotIn("lr-workbench__layout--centerOnly", text)
                self.assertNotIn('id="lrSidebarMount"', text)
                self.assertNotIn('id="lrCanonicalPath"', text)
                self.assertNotIn('id="lrSamrasActionRow"', text)
                self.assertNotIn('id="lrBtnPromoteSamras"', text)
            else:
                self.assertIn('id="lrTabWorkspace"', text)
                self.assertIn('data-lr-tab="workspace"', text)
                self.assertIn('id="lrPanelWorkspace"', text)
                self.assertIn('class="lr-workbench__tab is-active" data-lr-tab="workspace" id="lrTabWorkspace"', text)
                self.assertIn("lr-workbench__layout--centerOnly", text)
                self.assertIn('id="lrSidebarMount"', text)
                self.assertIn('id="lrCanonicalPath"', text)
                self.assertIn('id="lrSamrasActionRow"', text)
                self.assertIn('id="lrBtnPromoteSamras"', text)

    def test_data_tool_shell_resources_workbench_controls(self) -> None:
        partial = REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/partials/data_tool_shell.html"
        text = partial.read_text(encoding="utf-8")
        self.assertIn('id="dtResourcesRefreshBtn"', text)
        self.assertIn('id="dtResourcesStatus"', text)
        self.assertIn('id="dtResourcesFilesJson"', text)
        self.assertIn('id="dtWorkspaceResources"', text)
        self.assertIn('id="dtResourcesWorkbenchTitle"', text)
        self.assertIn('id="dtResourcesWorkbenchMeta"', text)
        self.assertNotIn('id="dtResourcesTabTxa"', text)
        self.assertNotIn('id="dtResourcesTabMsn"', text)
        self.assertIn('id="dtResourcesExplorerTable"', text)
        self.assertNotIn("<th scope=\"col\">File</th>", text)

    def test_system_inheritance_workbench_markup(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            if flavor == "fnd":
                self.assertNotIn('id="inhWorkbenchRoot"', text)
                self.assertNotIn("inheritance_workbench.js", text)
                self.assertNotIn('id="inheritanceSourceList"', text)
                self.assertNotIn('id="inheritanceResourceList"', text)
                self.assertNotIn("inh-workbench__layout--twoCol", text)
                self.assertNotIn('id="inheritanceSelectedSummary"', text)
            else:
                self.assertIn('id="inhWorkbenchRoot"', text)
                self.assertIn("inheritance_workbench.js", text)
                self.assertIn('id="inheritanceSourceList"', text)
                self.assertIn('id="inheritanceResourceList"', text)
                self.assertIn("inh-workbench__layout--twoCol", text)
                self.assertIn('id="inheritanceSelectedSummary"', text)

    def test_base_template_exposes_inspector_block_and_transient_mount(self) -> None:
        base = REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/templates/base.html"
        text = base.read_text(encoding="utf-8")
        self.assertIn("{% block inspector_content %}", text)
        self.assertIn('id="portalInspectorTransientMount"', text)

    def test_inherited_inventory_api_exposes_grouped_by_source(self) -> None:
        """Backend support for inheritance UI grouping (no regression)."""
        data_workspace = REPO_ROOT / "portals/_shared/portal/api/data_workspace.py"
        body = data_workspace.read_text(encoding="utf-8")
        self.assertIn("_group_inherited_index", body)
        self.assertIn("grouped_by_source_fn=_group_inherited_index", body)
        self.assertIn("/portal/api/data/system/resource_workbench", body)


if __name__ == "__main__":
    unittest.main()
