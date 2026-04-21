from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import PORTAL_SHELL_ASSET_MANIFEST_SCHEMA, PORTAL_SHELL_MODULE_FILES, build_shell_asset_manifest
from MyCiteV2.packages.state_machine.portal_shell import (
    SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
    SURFACE_POSTURE_WORKBENCH_PRIMARY,
    build_portal_tool_registry_entries,
)


class PortalOneShellBoundaryTests(unittest.TestCase):
    def test_retired_split_artifacts_are_absent(self) -> None:
        retired_history_dir = REPO_ROOT / ("MyCite" + "V" + "1")
        retired_bridge_dir = REPO_ROOT / "MyCiteV2" / "packages" / "adapters" / ("portal_" + "runtime")
        retired_surface_file = REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / ("trusted" + "_tenant" + "_portal.py")
        retired_runtime_file = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / ("tenant" + "_portal_runtime.py")
        retired_shell_file = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / ("admin" + "_runtime.py")
        retired_shell_dir = REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / ("hanus" + "_shell")
        self.assertFalse(retired_history_dir.exists())
        self.assertFalse(retired_bridge_dir.exists())
        self.assertFalse(retired_surface_file.exists())
        self.assertFalse(retired_runtime_file.exists())
        self.assertFalse(retired_shell_file.exists())
        self.assertFalse(retired_shell_dir.exists())

    def test_host_and_runtime_use_only_canonical_shell_routes(self) -> None:
        app_source = (REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "app.py").read_text(encoding="utf-8")
        runtime_source = (REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "runtime_platform.py").read_text(encoding="utf-8")
        shell_source = (REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / "portal_shell" / "shell.py").read_text(encoding="utf-8")

        self.assertIn("/portal/api/v2/shell", app_source)
        self.assertIn('@app.get("/portal")', app_source)
        self.assertIn("/portal/system/tools/<tool_slug>", app_source)
        self.assertIn("/portal/system", shell_source)
        self.assertIn("/portal/network", shell_source)
        self.assertIn("/portal/utilities", shell_source)
        self.assertNotIn("/portal/api/v2/" + "tenant", app_source)
        self.assertNotIn("/portal/api/v2/" + "admin" + "/shell", app_source)
        self.assertNotIn("/portal/system/activity", app_source)
        self.assertNotIn("/portal/system/profile-basics", app_source)
        self.assertNotIn("trusted" + "_tenant", runtime_source)
        self.assertNotIn("admin" + " shell", shell_source.lower())

    def test_shell_contracts_enforce_workspace_and_tool_behavior(self) -> None:
        shell_source = (REPO_ROOT / "MyCiteV2" / "packages" / "state_machine" / "portal_shell" / "shell.py").read_text(encoding="utf-8")
        self.assertIn('SYSTEM_ANCHOR_FILE_KEY = "anthology"', shell_source)
        self.assertIn("TRANSITION_BACK_OUT", shell_source)
        self.assertIn("SYSTEM_SANDBOX_QUERY_FILE_TOKEN", shell_source)
        self.assertIn("default_workbench_visible: bool = False", shell_source)
        self.assertNotIn("system.activity", shell_source)
        self.assertNotIn("system.profile_basics", shell_source)

    def test_tool_registry_keeps_explicit_surface_posture_contracts(self) -> None:
        registry = {entry.tool_id: entry for entry in build_portal_tool_registry_entries()}
        for tool_id in ("aws_csm", "cts_gis", "fnd_dcm", "fnd_ebi"):
            self.assertEqual(registry[tool_id].surface_posture, SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY)
            self.assertFalse(registry[tool_id].default_workbench_visible)
        self.assertEqual(registry["workbench_ui"].surface_posture, SURFACE_POSTURE_WORKBENCH_PRIMARY)
        self.assertTrue(registry["workbench_ui"].default_workbench_visible)

    def test_shell_asset_manifest_is_canonical_and_loader_reads_it_dynamically(self) -> None:
        manifest = build_shell_asset_manifest(build_id="build-123")
        loader_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_shell.js"
        ).read_text(encoding="utf-8")

        self.assertEqual(manifest["schema"], PORTAL_SHELL_ASSET_MANIFEST_SCHEMA)
        self.assertEqual(
            [entry["file"] for entry in manifest["scripts"]["shell_modules"]],
            list(PORTAL_SHELL_MODULE_FILES),
        )
        self.assertIn('document.getElementById("v2-shell-asset-manifest")', loader_source)
        self.assertIn("scripts.shell_modules", loader_source)
        self.assertIn("window.__MYCITE_V2_SHELL_ASSET_MANIFEST = assetManifest", loader_source)
        self.assertIn("v2_portal_tool_surface_adapter.js", PORTAL_SHELL_MODULE_FILES)
        for filename in PORTAL_SHELL_MODULE_FILES:
            self.assertNotIn(f'"{filename}"', loader_source)

    def test_shell_static_sources_expose_workbench_toggle_and_interface_panel_aliases(self) -> None:
        template_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "templates" / "portal.html"
        ).read_text(encoding="utf-8")
        portal_js = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "portal.js"
        ).read_text(encoding="utf-8")
        shell_core = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_shell_core.js"
        ).read_text(encoding="utf-8")
        portal_css = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "portal.css"
        ).read_text(encoding="utf-8")

        self.assertIn('data-shell-toggle="workbench"', template_source)
        self.assertIn('data-workbench-collapsed="false"', template_source)
        self.assertIn('data-tool-panel-lock="false"', template_source)
        self.assertIn('data-shell-title="Control Panel"', template_source)
        self.assertIn('data-shell-toggle="interface-panel"', template_source)
        self.assertIn('data-shell-title="Interface Panel"', template_source)
        self.assertIn('data-shell-lockable="tool-panel"', template_source)

        self.assertIn("mycite.layout.workbench.open", portal_js)
        self.assertIn("mycite.layout.interface_panel.width", portal_js)
        self.assertIn("mycite.layout.interface_panel.open", portal_js)
        self.assertIn("mycite.layout.inspector.width", portal_js)
        self.assertIn("mycite.layout.inspector.open", portal_js)
        self.assertIn("mycite:v2:workbench-toggle-request", portal_js)
        self.assertIn("mycite:v2:interface-panel-toggle-request", portal_js)
        self.assertIn("data-tool-panel-lock", portal_js)
        self.assertIn("data-tool-panel-lock-route", portal_js)
        self.assertIn("dblclick", portal_js)
        self.assertIn("firstV2ShellCompositionApplied", portal_js)
        self.assertIn("useStoredWorkbenchPreference: false", portal_js)
        self.assertIn("syncFromDom: (options) => layoutApi.syncFromDom && layoutApi.syncFromDom(options)", portal_js)
        self.assertIn("fromShellComposition: true", shell_core)
        self.assertIn("routeKeyFromUrl", shell_core)
        self.assertIn("routeKey: routeKey", shell_core)
        tool_adapter = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_tool_surface_adapter.js"
        ).read_text(encoding="utf-8")
        self.assertIn("loading", tool_adapter)
        self.assertIn("error", tool_adapter)
        self.assertIn("empty", tool_adapter)
        self.assertIn("unsupported", tool_adapter)
        self.assertIn("buildDirectSurfaceRequest", tool_adapter)
        self.assertIn("buildAwsProfileRows", tool_adapter)
        self.assertIn("buildAwsNewsletterRows", tool_adapter)
        self.assertIn("PortalToolSurfaceAdapter", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_workbench_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("PortalToolSurfaceAdapter", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertNotIn("PortalFndEbi", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_workbench_renderers.js"
        ).read_text(encoding="utf-8"))

        self.assertIn("data-workbench-collapsed", shell_core)
        self.assertIn("data-interface-panel-collapsed", shell_core)
        self.assertIn("regions.interface_panel", shell_core)
        self.assertIn('data-shell-composition") === "tool"', shell_core)

        self.assertIn('data-workbench-collapsed="true"', portal_css)
        self.assertIn("minmax(0, 1fr)", portal_css)
        self.assertIn("cts_gis_interface_body", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("Diktataograph", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("Garland", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("navigation_canvas", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("garland_split_projection", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("renderDirectoryDropdownCanvas", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn('"directory_dropdowns"', (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("renderGeospatialStage", (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("cts-gis-garlandSplit__geospatial", portal_css)
        self.assertIn("cts-gis-directoryCanvas", portal_css)
        self.assertIn("cts-gis-stageSelector", portal_css)
        self.assertIn("cts-gis-stageColumn__frame", portal_css)
        self.assertIn("cts-gis-navDiagnostics", portal_css)
        self.assertIn("cts-gis-mapStage__svg", portal_css)
        self.assertIn("cts-gis-profileHierarchy__item", portal_css)
        self.assertIn(".cts-gis-interface__body", portal_css)

    def test_cts_gis_runtime_and_renderer_expose_only_directory_dropdown_navigation_mode(self) -> None:
        runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_cts_gis_runtime.py"
        ).read_text(encoding="utf-8")
        contract_source = (
            REPO_ROOT / "MyCiteV2" / "packages" / "modules" / "cross_domain" / "cts_gis" / "contracts.py"
        ).read_text(encoding="utf-8")
        renderer_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
        ).read_text(encoding="utf-8")

        self.assertIn("CTS_GIS_NAV_MODE_DIRECTORY", runtime_source)
        self.assertIn("directory_dropdowns", contract_source)
        self.assertIn("directory_dropdowns", renderer_source)
        self.assertNotIn("staged_diktataograph", runtime_source)
        self.assertNotIn("ordered_hierarchy", runtime_source)
        self.assertNotIn("legacy_branch_canvas", runtime_source)

    def test_active_repo_text_does_not_reference_retired_split_routes(self) -> None:
        forbidden_tokens = (
            "MyCite" + "V" + "1",
            "v" + "1_" + "host_" + "bridge",
            "/portal/" + "home",
            "/portal/" + "fnd",
            "/portal/" + "tff",
            "/portal/" + "switch",
        )
        scan_roots = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "MyCiteV2",
            REPO_ROOT / "docs",
        ]
        violations: list[str] = []
        for root in scan_roots:
            paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
            for path in paths:
                if "__pycache__" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                for token in forbidden_tokens:
                    if token in text:
                        violations.append(f"{path.relative_to(REPO_ROOT)} -> {token}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
