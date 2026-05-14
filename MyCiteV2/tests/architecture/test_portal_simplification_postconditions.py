"""Phase 3 postconditions for TASK-PORTAL-SIMPLIFICATION-2026-05-14.

Locks in the end state described by
/srv/agentic/knowledge/legacy/mycite-core/contracts/portal_tool_surface_contract.md:

  - the retired interface_panel renderer JS files are gone
  - the asset manifest no longer lists interface_panel-related modules
  - the FND-CSM tool surface (catalog + registry) is retired
  - every first-class tool in the registry is a palette target
  - the build_shell_composition_payload pipeline never marks interface_panel
    visible or primary
  - the legacy GET /portal/system/tools/fnd-csm route still 302-redirects to
    /portal/utilities/tool-exposure (preservation contract)

If a future change resurrects any of the above, these assertions catch it.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import (
        PORTAL_SHELL_MODULE_CONTRACTS,
        V2PortalHostConfig,
        create_app,
    )

from MyCiteV2.packages.state_machine.portal_shell import (
    SURFACE_POSTURE_PALETTE_TARGET,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
    build_shell_composition_payload,
)

STATIC_DIR = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
RETIRED_JS_FILES = (
    "v2_portal_interface_panel_host.js",
    "v2_portal_interface_panel_renderers.js",
    "v2_portal_fnd_csm_workspace.js",
)
RETIRED_MODULE_IDS = (
    "interface_panel_renderers",
    "fnd_csm_workspace",
    "cts_gis_surface",
    "cts_gis_workspace",
)


class RetiredJsArtifactsTests(unittest.TestCase):
    def test_retired_interface_panel_js_files_are_deleted(self) -> None:
        for filename in RETIRED_JS_FILES:
            path = STATIC_DIR / filename
            self.assertFalse(
                path.exists(),
                f"Phase 3 deletes {filename}; resurrection violates portal_tool_surface_contract.md",
            )

    def test_tool_palette_js_is_present(self) -> None:
        path = STATIC_DIR / "v2_portal_tool_palette.js"
        self.assertTrue(
            path.exists(),
            "Phase 3a adds v2_portal_tool_palette.js as the palette UI module",
        )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class AssetManifestTests(unittest.TestCase):
    def test_asset_manifest_excludes_retired_module_ids(self) -> None:
        module_ids = {entry["module_id"] for entry in PORTAL_SHELL_MODULE_CONTRACTS}
        for retired_id in RETIRED_MODULE_IDS:
            self.assertNotIn(
                retired_id,
                module_ids,
                f"Phase 3 removes {retired_id} from PORTAL_SHELL_MODULE_CONTRACTS",
            )

    def test_asset_manifest_includes_tool_palette(self) -> None:
        module_ids = {entry["module_id"] for entry in PORTAL_SHELL_MODULE_CONTRACTS}
        self.assertIn("tool_palette", module_ids)


class RegistryPostconditionTests(unittest.TestCase):
    def test_fnd_csm_tool_surface_is_retired(self) -> None:
        surface_ids = [entry.surface_id for entry in build_portal_surface_catalog()]
        self.assertNotIn(
            "system.tools.fnd_csm",
            surface_ids,
            "Phase 3g retires the fnd_csm tool surface",
        )

    def test_no_fnd_csm_registry_entry(self) -> None:
        tool_ids = [entry.tool_id for entry in build_portal_tool_registry_entries()]
        self.assertNotIn(
            "fnd_csm",
            tool_ids,
            "Phase 3g retires the fnd_csm registry entry — its tabs now live as utilities extensions",
        )

    def test_every_tool_is_palette_target(self) -> None:
        for entry in build_portal_tool_registry_entries():
            self.assertEqual(
                entry.surface_posture,
                SURFACE_POSTURE_PALETTE_TARGET,
                f"{entry.tool_id} must have surface_posture=palette_target",
            )

    def test_extensions_live_under_utilities_tool_exposure(self) -> None:
        for entry in build_portal_tool_registry_entries():
            if entry.is_extension:
                self.assertEqual(
                    entry.surface_id,
                    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
                    f"Extension {entry.tool_id} must live under utilities.tool_exposure",
                )


class CompositionPostconditionTests(unittest.TestCase):
    def test_interface_panel_is_never_visible(self) -> None:
        for surface_id in (
            "system.root",
            "network.root",
            "utilities.root",
            "utilities.tool_exposure",
            "system.tools.cts_gis",
            WORKBENCH_UI_TOOL_SURFACE_ID,
        ):
            composition = build_shell_composition_payload(
                active_surface_id=surface_id,
                portal_instance_id="fnd",
                page_title="t",
                page_subtitle="",
                activity_items=[],
                control_panel={},
                workbench={"visible": True},
                interface_panel={"visible": True},
                shell_state=None,
            )
            self.assertFalse(
                composition["regions"]["interface_panel"]["visible"],
                f"interface_panel must be hidden for surface={surface_id}",
            )
            self.assertTrue(composition["interface_panel_collapsed"])
            self.assertFalse(composition["regions"]["interface_panel"]["primary_surface"])


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class LegacyFndCsmRedirectTests(unittest.TestCase):
    def test_legacy_fnd_csm_route_still_redirects(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="phase3_postcond_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.org",
            webapps_root=tmp / "webapps",
        )
        client = create_app(config).test_client()
        resp = client.get("/portal/system/tools/fnd-csm", follow_redirects=False)
        self.assertEqual(
            resp.status_code,
            302,
            "Preservation contract: legacy FND-CSM URL must redirect to Utilities",
        )
        self.assertEqual(resp.headers["Location"], "/portal/utilities/tool-exposure")


if __name__ == "__main__":
    unittest.main()
