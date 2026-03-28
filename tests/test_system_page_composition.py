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
        self.assertNotIn('class="card data-tool"', text)
        self.assertIn('id="dtWorkspaceResources"', text)
        self.assertIn('id="dtResourcesLayers"', text)
        self.assertIn('data-layout-mode="table"', text)
        self.assertIn('id="dtSystemAitasStrip"', text)
        self.assertIn('data-resources-task="navigate"', text)
        self.assertIn('data-resources-task="manipulate"', text)

    def test_system_shell_owns_inspector_slots(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            self.assertIn('id="systemShellInspectorRoot"', text)
            self.assertIn('aria-label="SYSTEM interface panel content"', text)
            self.assertIn('id="systemInspectorCardsMount"', text)
            self.assertIn('id="dtResourcesInspectorStack"', text)
            self.assertIn('id="dtResourcesInspectorEmpty"', text)
            self.assertIn("data-resources-inspector-panel", text)
            self.assertIn('data-system-inspector-panel="system"', text)
            self.assertNotIn('id="dtAnthologyInspectorBody"', text)
            self.assertIn("{% block inspector_content %}", text)
            self.assertNotIn('class="page-tabs"', text)
            self.assertNotIn("page-tab", text)
            self.assertNotIn('id="systemSourceScopeSummary"', text)

    def test_system_resources_task_sidebar_and_workbench_query_links(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('id="resourcesTaskSection"', text)
            self.assertNotIn('id="systemResourceFileSection"', text)
            self.assertNotIn('id="systemResourceFileList"', text)
            self.assertIn('id="resourcesDatumProfile"', text)
            self.assertIn("Control Panel", text)
            self.assertNotIn("System Views", text)
            self.assertNotIn("Local Resources", text)
            self.assertNotIn("Inheritance", text)

    def test_system_local_resources_defaults_to_workspace_tab(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('id="lrTabWorkspace"', text)
            self.assertNotIn('id="lrPanelWorkspace"', text)
            self.assertNotIn("lr-workbench__layout--centerOnly", text)
            self.assertNotIn('id="lrSidebarMount"', text)
            self.assertNotIn('id="lrCanonicalPath"', text)
            self.assertNotIn('id="lrSamrasActionRow"', text)
            self.assertNotIn('id="lrBtnPromoteSamras"', text)

    def test_data_tool_shell_resources_workbench_controls(self) -> None:
        partial = REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/templates/tools/partials/data_tool_shell.html"
        text = partial.read_text(encoding="utf-8")
        self.assertIn('id="dtResourcesRefreshBtn"', text)
        self.assertIn('id="dtWorkspaceResources"', text)
        self.assertNotIn('id="dtResourcesStatus"', text)
        self.assertNotIn('id="dtResourcesFilesJson"', text)
        self.assertNotIn('id="dtResourcesWorkbenchTitle"', text)
        self.assertNotIn('id="dtResourcesWorkbenchMeta"', text)
        self.assertNotIn('id="dtResourcesTabTxa"', text)
        self.assertNotIn('id="dtResourcesTabMsn"', text)
        self.assertIn('id="dtResourcesLayers"', text)
        self.assertIn('id="dtResourcesWorkbenchStatus"', text)
        self.assertIn('id="dtSystemAitasStrip"', text)
        self.assertIn('data-resources-task="navigate"', text)
        self.assertIn('data-resources-task="investigate"', text)
        self.assertIn('data-resources-task="mediate"', text)
        self.assertIn('data-resources-task="manipulate"', text)
        self.assertNotIn('id="dtOpenNimmBtn"', text)
        self.assertNotIn('id="dtAnthologyGraphRefreshBtn"', text)

    def test_system_inheritance_workbench_markup(self) -> None:
        for flavor in ("fnd", "tff"):
            path = REPO_ROOT / f"portals/_shared/runtime/flavors/{flavor}/portal/ui/templates/services/system.html"
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('id="inhWorkbenchRoot"', text)
            self.assertNotIn("inheritance_workbench.js", text)
            self.assertNotIn('id="inheritanceSourceList"', text)
            self.assertNotIn('id="inheritanceResourceList"', text)
            self.assertNotIn("inh-workbench__layout--twoCol", text)
            self.assertNotIn('id="inheritanceSelectedSummary"', text)

    def test_base_template_exposes_inspector_block_and_transient_mount(self) -> None:
        base = REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/templates/base.html"
        text = base.read_text(encoding="utf-8")
        self.assertIn("{% block inspector_content %}", text)
        self.assertIn('id="portalInspectorTransientMount"', text)
        self.assertIn('id="portalControlPanel"', text)
        self.assertIn('data-shell-region="control-panel"', text)
        self.assertIn('data-shell-region="center-workbench"', text)
        self.assertIn('data-shell-region="interface-panel"', text)
        self.assertIn('aria-label="Control panel"', text)
        self.assertIn('aria-label="Interface panel"', text)
        self.assertIn("Interface Panel", text)
        self.assertIn('data-control-panel-collapsed="false"', text)
        self.assertNotIn('class="ide-menubar__spacer"', text)
        self.assertNotIn("activity_tool_nav", text)
        self.assertNotIn("ide-activitylink--tool", text)
        self.assertLess(text.index('data-shell-toggle="control-panel"'), text.index('data-shell-toggle="inspector"'))
        self.assertLess(text.index('data-shell-toggle="inspector"'), text.index('class="themebar ide-menubar__theme"'))

    def test_menubar_css_locks_non_wrapping_system_shell_controls(self) -> None:
        css = (REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/static/portal.css").read_text(encoding="utf-8")
        js = (REPO_ROOT / "portals/_shared/runtime/flavors/fnd/portal/ui/static/portal.js").read_text(encoding="utf-8")
        self.assertIn(".ide-menubar__right {", css)
        self.assertIn(".ide-menubar__shellActions {", css)
        self.assertIn(".ide-menubar__theme {", css)
        self.assertIn(".ide-menubar__menu {", css)
        self.assertIn("flex-wrap: nowrap;", css)
        self.assertIn(".ide-shell--system-workbench.ide-shell--workbench-tight .ide-menubar__pageSub", css)
        self.assertIn('shell.classList.toggle("ide-shell--system-workbench"', js)
        self.assertIn('shell.classList.add("ide-shell--workbench-tight")', js)

    def test_wiki_locks_unified_system_and_hidden_tool_home_framing(self) -> None:
        wiki_readme = (REPO_ROOT / "wiki/README.md").read_text(encoding="utf-8")
        shell_page = (REPO_ROOT / "wiki/architecture/shell-and-page-composition.md").read_text(encoding="utf-8")
        provider_page = (REPO_ROOT / "wiki/tools/provider-model.md").read_text(encoding="utf-8")
        agro_page = (REPO_ROOT / "wiki/tools/agro-erp-mediation.md").read_text(encoding="utf-8")
        archive_page = (REPO_ROOT / "wiki/archive/historical-lineage.md").read_text(encoding="utf-8")
        self.assertIn("primary maintained knowledge base", wiki_readme)
        self.assertIn("former `docs/` tree has been retired", wiki_readme)
        self.assertIn("no visible Local Resources or Inheritance tabs", shell_page)
        self.assertIn("GET /portal/system", shell_page)
        self.assertIn("Tools are providers, not shells.", provider_page)
        self.assertIn("`SYSTEM` under `Mediate`", agro_page)
        self.assertIn("not a separate shell", agro_page)
        self.assertIn("portal_local_resources_workbench.md", archive_page)
        self.assertIn("ANTHOLOGY_WORKBENCH_ARCHITECTURE.md", archive_page)

    def test_inherited_inventory_api_exposes_grouped_by_source(self) -> None:
        """Backend support for inheritance UI grouping (no regression)."""
        data_workspace = REPO_ROOT / "portals/_shared/portal/api/data_workspace.py"
        body = data_workspace.read_text(encoding="utf-8")
        self.assertIn("_group_inherited_index", body)
        self.assertIn("grouped_by_source_fn=_group_inherited_index", body)
        self.assertIn("/portal/api/data/system/resource_workbench", body)
        self.assertIn("/portal/api/data/system/mutate", body)
        self.assertIn("/portal/api/data/system/publish", body)
        runtime_body = (REPO_ROOT / "portals/_shared/portal/application/shell/runtime.py").read_text(encoding="utf-8")
        self.assertIn('"attention_address"', runtime_body)
        self.assertIn('"directive"', runtime_body)
        self.assertIn('"spatial"', (REPO_ROOT / "portals/_shared/portal/application/shell/runtime.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
