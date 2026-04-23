from __future__ import annotations

import re
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
        aws_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_aws_runtime.py"
        ).read_text(encoding="utf-8")
        cts_gis_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_cts_gis_runtime.py"
        ).read_text(encoding="utf-8")
        fnd_ebi_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_fnd_ebi_runtime.py"
        ).read_text(encoding="utf-8")
        fnd_dcm_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_fnd_dcm_runtime.py"
        ).read_text(encoding="utf-8")
        workbench_ui_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_workbench_ui_runtime.py"
        ).read_text(encoding="utf-8")

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
        self.assertRegex(
            aws_runtime_source,
            re.compile(
                r"def run_portal_aws_csm\([\s\S]*?"
                r"run_portal_shell_entry\(",
                re.MULTILINE,
            ),
        )
        self.assertRegex(
            aws_runtime_source,
            re.compile(
                r"def run_portal_aws_csm_action\([\s\S]*?"
                r"_runtime_envelope_from_bundle\(",
                re.MULTILINE,
            ),
        )
        self.assertIn("run_portal_shell_entry(", cts_gis_runtime_source)
        self.assertNotIn("build_portal_runtime_envelope(", cts_gis_runtime_source)
        self.assertIn("run_portal_shell_entry(", fnd_ebi_runtime_source)
        self.assertNotIn("build_portal_runtime_envelope(", fnd_ebi_runtime_source)
        self.assertIn("run_portal_shell_entry(", fnd_dcm_runtime_source)
        self.assertNotIn("build_portal_runtime_envelope(", fnd_dcm_runtime_source)
        self.assertIn("run_portal_shell_entry(", workbench_ui_runtime_source)
        self.assertNotIn("build_portal_runtime_envelope(", workbench_ui_runtime_source)

    def test_shell_runtime_uses_registry_backed_tool_bundle_lookup(self) -> None:
        shell_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_shell_runtime.py"
        ).read_text(encoding="utf-8")

        self.assertIn("_TOOL_SURFACE_BUNDLE_BUILDERS", shell_runtime_source)
        self.assertIn("builder = _TOOL_SURFACE_BUNDLE_BUILDERS.get(surface_id)", shell_runtime_source)
        self.assertIn("if selection_surface_id in _TOOL_SURFACE_BUNDLE_BUILDERS:", shell_runtime_source)
        self.assertNotIn("if surface_id == AWS_CSM_TOOL_SURFACE_ID:", shell_runtime_source)
        self.assertNotIn("if surface_id == CTS_GIS_TOOL_SURFACE_ID:", shell_runtime_source)
        self.assertNotIn("if surface_id == FND_DCM_TOOL_SURFACE_ID:", shell_runtime_source)
        self.assertNotIn("if surface_id == FND_EBI_TOOL_SURFACE_ID:", shell_runtime_source)
        self.assertNotIn("if surface_id == WORKBENCH_UI_TOOL_SURFACE_ID:", shell_runtime_source)

    def test_runtime_owned_tool_query_normalization_uses_single_runtime_request_helper(self) -> None:
        aws_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_aws_runtime.py"
        ).read_text(encoding="utf-8")
        fnd_dcm_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_fnd_dcm_runtime.py"
        ).read_text(encoding="utf-8")
        workbench_ui_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_workbench_ui_runtime.py"
        ).read_text(encoding="utf-8")

        self.assertIn("canonical_query_for_runtime_request_payload", aws_runtime_source)
        self.assertIn("canonical_query_for_runtime_request_payload", fnd_dcm_runtime_source)
        self.assertIn("canonical_query_for_runtime_request_payload", workbench_ui_runtime_source)

    def test_runtime_emitters_attach_region_family_contract_markers(self) -> None:
        runtime_platform_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "runtime_platform.py"
        ).read_text(encoding="utf-8")
        runtime_sources = [
            (
                REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_system_workspace_runtime.py"
            ).read_text(encoding="utf-8"),
            (
                REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_shell_runtime.py"
            ).read_text(encoding="utf-8"),
            (
                REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_aws_runtime.py"
            ).read_text(encoding="utf-8"),
            (
                REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_cts_gis_runtime.py"
            ).read_text(encoding="utf-8"),
            (
                REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_fnd_dcm_runtime.py"
            ).read_text(encoding="utf-8"),
            (
                REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_fnd_ebi_runtime.py"
            ).read_text(encoding="utf-8"),
            (
                REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_workbench_ui_runtime.py"
            ).read_text(encoding="utf-8"),
        ]

        self.assertIn("build_portal_region_family_contract", runtime_platform_source)
        self.assertIn("attach_region_family_contract", runtime_platform_source)
        self.assertIn("PORTAL_REGION_FAMILY_DIRECTIVE_PANEL", runtime_platform_source)
        self.assertIn("PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE", runtime_platform_source)
        self.assertIn("PORTAL_REGION_FAMILY_PRESENTATION_SURFACE", runtime_platform_source)
        for source in runtime_sources:
            self.assertIn("attach_region_family_contract(", source)

    def test_shell_runtime_forwards_runtime_owned_workbench_ui_surface_query(self) -> None:
        shell_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_shell_runtime.py"
        ).read_text(encoding="utf-8")

        self.assertRegex(
            shell_runtime_source,
            re.compile(
                r"def _build_workbench_ui_tool_bundle\([\s\S]*?"
                r"build_portal_workbench_ui_surface_bundle\([\s\S]*?"
                r"surface_query=surface_query,",
                re.MULTILINE,
            ),
        )

    def test_system_workspace_and_workbench_ui_runtime_keep_distinct_boundary_terms(self) -> None:
        system_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_system_workspace_runtime.py"
        ).read_text(encoding="utf-8")
        workbench_ui_runtime_source = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_workbench_ui_runtime.py"
        ).read_text(encoding="utf-8")

        self.assertIn("SYSTEM_ANCHOR_FILE_KEY", system_runtime_source)
        self.assertIn("anthology_layered_table", system_runtime_source)
        self.assertNotIn("document_sort", system_runtime_source)
        self.assertNotIn("document_filter", system_runtime_source)
        self.assertNotIn("workbench_lens", system_runtime_source)
        self.assertNotIn("selected_row_hyphae_hash_short", system_runtime_source)

        self.assertIn("document_sort", workbench_ui_runtime_source)
        self.assertIn("document_filter", workbench_ui_runtime_source)
        self.assertIn("workbench_lens", workbench_ui_runtime_source)
        self.assertIn("selected_row_hyphae_hash_short", workbench_ui_runtime_source)
        self.assertNotIn("SYSTEM_ANCHOR_FILE_KEY", workbench_ui_runtime_source)
        self.assertNotIn("TRANSITION_FOCUS_FILE", workbench_ui_runtime_source)
        self.assertNotIn("anthology_layered_table", workbench_ui_runtime_source)

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
        expected_module_ids = [
            "region_renderers",
            "tool_surface_adapter",
            "aws_workspace",
            "system_workspace",
            "network_workspace",
            "workbench_renderers",
            "inspector_renderers",
            "shell_core",
            "shell_watchdog",
        ]

        self.assertEqual(manifest["schema"], PORTAL_SHELL_ASSET_MANIFEST_SCHEMA)
        self.assertEqual(
            [entry["file"] for entry in manifest["scripts"]["shell_modules"]],
            list(PORTAL_SHELL_MODULE_FILES),
        )
        self.assertEqual(
            [entry["module_id"] for entry in manifest["scripts"]["shell_modules"]],
            expected_module_ids,
        )
        system_module = manifest["scripts"]["shell_modules"][3]
        self.assertEqual(system_module["module_id"], "system_workspace")
        self.assertEqual(
            system_module["exports"],
            [{"global": "PortalSystemWorkspaceRenderer", "required_callables": ["render"]}],
        )
        tool_adapter_module = manifest["scripts"]["shell_modules"][1]
        self.assertEqual(tool_adapter_module["module_id"], "tool_surface_adapter")
        self.assertIn(
            "resolveToolId",
            tool_adapter_module["exports"][0]["required_callables"],
        )
        self.assertIn('document.getElementById("v2-shell-asset-manifest")', loader_source)
        self.assertIn("scripts.shell_modules", loader_source)
        self.assertIn("window.__MYCITE_V2_SHELL_ASSET_MANIFEST = assetManifest", loader_source)
        self.assertIn("window.__MYCITE_V2_SHELL_MODULE_REGISTRY = buildModuleRegistry", loader_source)
        self.assertIn("window.__MYCITE_V2_REGISTER_SHELL_MODULE = registerShellModule", loader_source)
        self.assertIn("window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS = buildModuleDiagnostics", loader_source)
        self.assertIn("window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT = resolveShellModuleExport", loader_source)
        self.assertIn("invalid_registrations", loader_source)
        self.assertIn("script_load_order", loader_source)
        self.assertIn("v2_portal_tool_surface_adapter.js", PORTAL_SHELL_MODULE_FILES)
        for filename in PORTAL_SHELL_MODULE_FILES:
            self.assertNotIn(f'"{filename}"', loader_source)

    def test_shell_static_sources_self_register_required_modules_and_use_registry_contracts(self) -> None:
        static_root = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
        expected_registrations = {
            "v2_portal_shell_region_renderers.js": "region_renderers",
            "v2_portal_tool_surface_adapter.js": "tool_surface_adapter",
            "v2_portal_aws_workspace.js": "aws_workspace",
            "v2_portal_system_workspace.js": "system_workspace",
            "v2_portal_network_workspace.js": "network_workspace",
            "v2_portal_workbench_renderers.js": "workbench_renderers",
            "v2_portal_inspector_renderers.js": "inspector_renderers",
            "v2_portal_shell_core.js": "shell_core",
            "v2_portal_shell_watchdog.js": "shell_watchdog",
        }
        for filename, module_id in expected_registrations.items():
            source = (static_root / filename).read_text(encoding="utf-8")
            self.assertIn(f'__MYCITE_V2_REGISTER_SHELL_MODULE("{module_id}")', source, filename)

        workbench_source = (static_root / "v2_portal_workbench_renderers.js").read_text(encoding="utf-8")
        inspector_source = (static_root / "v2_portal_inspector_renderers.js").read_text(encoding="utf-8")
        core_source = (static_root / "v2_portal_shell_core.js").read_text(encoding="utf-8")

        self.assertIn("resolveReflectiveWorkspaceModuleSpec", workbench_source)
        self.assertIn("resolveRegisteredModuleExport(spec.moduleId, spec.globalName)", workbench_source)
        self.assertIn("__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS", workbench_source)
        self.assertNotIn("window.PortalSystemWorkspaceRenderer &&", workbench_source)
        self.assertIn("__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT", inspector_source)
        self.assertIn("module_registration_missing", core_source)
        self.assertIn('resolveRegisteredModuleExport("region_renderers", "PortalShellRegionRenderers")', core_source)

    def test_tool_surface_adapter_keeps_canonical_tool_and_readiness_resolution_order(self) -> None:
        tool_adapter = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_tool_surface_adapter.js"
        ).read_text(encoding="utf-8")

        readiness_tokens = [
            "surfacePayload && surfacePayload.readiness",
            "surfacePayload && surfacePayload.source_evidence).readiness",
            "surfacePayload && surfacePayload.workspace).readiness",
            "region && region.interface_body).readiness",
        ]
        tool_id_tokens = [
            "surfacePayload && surfacePayload.tool_id",
            "surfacePayload && surfacePayload.tool_state).tool_id",
            "surfacePayload && surfacePayload.source_evidence).tool_spec).tool_id",
            "region && region.tool_id",
        ]
        readiness_indexes = [tool_adapter.index(token) for token in readiness_tokens]
        tool_id_indexes = [tool_adapter.index(token) for token in tool_id_tokens]

        self.assertEqual(readiness_indexes, sorted(readiness_indexes))
        self.assertEqual(tool_id_indexes, sorted(tool_id_indexes))
        self.assertIn("toolId: resolveToolId(region, surfacePayload)", tool_adapter)
        self.assertIn("readiness: readiness", tool_adapter)
        self.assertIn("resolveToolId: resolveToolId", tool_adapter)

    def test_directive_panel_host_dispatches_by_family_contract_before_cts_gis_compatibility(self) -> None:
        static_root = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
        region_renderers = (static_root / "v2_portal_shell_region_renderers.js").read_text(encoding="utf-8")
        tool_adapter = (static_root / "v2_portal_tool_surface_adapter.js").read_text(encoding="utf-8")

        self.assertIn("resolveDirectivePanelMode", region_renderers)
        self.assertIn('family === "directive_panel"', region_renderers)
        self.assertIn("state_directive_compact", region_renderers)
        self.assertNotIn('region.surface_label === "CTS-GIS"', region_renderers)

        self.assertIn("function resolveDirectivePanelMode(region)", tool_adapter)
        self.assertIn("function resolveRegionFamily(region)", tool_adapter)
        self.assertIn("resolveDirectivePanelMode: resolveDirectivePanelMode", tool_adapter)
        self.assertIn("resolveRegionFamily: resolveRegionFamily", tool_adapter)
        self.assertIn("family_contract", tool_adapter)

    def test_reflective_workspace_host_dispatches_by_family_contract_before_payload_kind_compatibility(self) -> None:
        static_root = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
        workbench_renderers = (static_root / "v2_portal_workbench_renderers.js").read_text(encoding="utf-8")
        tool_adapter = (static_root / "v2_portal_tool_surface_adapter.js").read_text(encoding="utf-8")

        self.assertIn("resolveReflectiveWorkspaceMode", workbench_renderers)
        self.assertIn("resolveReflectiveWorkspaceModuleSpec", workbench_renderers)
        self.assertIn('family === "reflective_workspace"', workbench_renderers)
        self.assertNotIn('surfacePayload.kind === "aws_csm_workspace"', workbench_renderers)
        self.assertNotIn('surfacePayload.kind === "system_workspace"', workbench_renderers)
        self.assertNotIn('surfacePayload.kind === "network_system_log_workspace"', workbench_renderers)
        self.assertNotIn('surfacePayload.kind === "workbench_ui_surface"', workbench_renderers)
        self.assertNotIn('surfacePayload.kind === "tool_secondary_evidence"', workbench_renderers)
        self.assertNotIn('surfacePayload.tool_id === "cts_gis"', workbench_renderers)

        self.assertIn("function resolveReflectiveWorkspaceMode(region, surfacePayload)", tool_adapter)
        self.assertIn("function resolveReflectiveWorkspaceModuleSpec(region, surfacePayload)", tool_adapter)
        self.assertIn("resolveReflectiveWorkspaceMode: resolveReflectiveWorkspaceMode", tool_adapter)
        self.assertIn("resolveReflectiveWorkspaceModuleSpec: resolveReflectiveWorkspaceModuleSpec", tool_adapter)
        self.assertIn("resolveSurfacePayloadKind", tool_adapter)
        self.assertIn("resolveRegionSurfaceId", tool_adapter)

    def test_presentation_surface_host_dispatches_by_family_contract_before_legacy_inspector_kinds(self) -> None:
        static_root = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
        inspector_renderers = (static_root / "v2_portal_inspector_renderers.js").read_text(encoding="utf-8")
        tool_adapter = (static_root / "v2_portal_tool_surface_adapter.js").read_text(encoding="utf-8")

        self.assertIn("resolvePresentationSurfaceMode", inspector_renderers)
        self.assertIn("resolvePresentationSurfaceModuleSpec", inspector_renderers)
        self.assertIn('family === "presentation_surface"', inspector_renderers)
        self.assertIn("renderPresentationSurfaceHost", inspector_renderers)
        self.assertIn("renderRegisteredPresentationSurface", inspector_renderers)
        self.assertNotIn('region.kind === "aws_csm_inspector"', inspector_renderers)
        self.assertNotIn('region.kind === "network_system_log_inspector"', inspector_renderers)
        self.assertNotIn('region.kind === "tool_mediation_panel"', inspector_renderers)
        self.assertNotIn('region.interface_body.kind === "cts_gis_interface_body"', inspector_renderers)

        self.assertIn("function resolvePresentationSurfaceMode(region, surfacePayload)", tool_adapter)
        self.assertIn("function resolvePresentationSurfaceModuleSpec(region, surfacePayload)", tool_adapter)
        self.assertIn("resolvePresentationSurfaceMode: resolvePresentationSurfaceMode", tool_adapter)
        self.assertIn("resolvePresentationSurfaceModuleSpec: resolvePresentationSurfaceModuleSpec", tool_adapter)
        self.assertIn("resolveRegionCompatibilityKind", tool_adapter)
        self.assertIn("resolveRegionInterfaceBodyKind", tool_adapter)
        self.assertIn("family_contract", tool_adapter)

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
