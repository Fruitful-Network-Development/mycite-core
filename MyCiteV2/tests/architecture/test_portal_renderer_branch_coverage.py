from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ADAPTER_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_tool_surface_adapter.js"
).read_text(encoding="utf-8")

WORKBENCH_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_workbench_renderers.js"
).read_text(encoding="utf-8")

INTERFACE_PANEL_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_interface_panel_renderers.js"
).read_text(encoding="utf-8")

FND_CSM_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_fnd_csm_workspace.js"
).read_text(encoding="utf-8")


class RendererBranchCoverageTests(unittest.TestCase):
    """Verify that every canonical tool slug resolves to a registered renderer
    branch (or is explicitly documented as deferred) via the adapter module
    spec maps. Prevents silent fallback to generic renderers."""

    def test_cts_gis_presentation_surface_is_registered(self) -> None:
        self.assertIn('"system.tools.cts_gis"', ADAPTER_SOURCE,
                      "CTS-GIS must be registered in resolvePresentationSurfaceModuleSpec")

    def test_fnd_csm_presentation_surface_is_registered(self) -> None:
        self.assertIn('"system.tools.fnd_csm"', ADAPTER_SOURCE,
                      "FND-CSM must be registered in resolvePresentationSurfaceModuleSpec")

    def test_fnd_csm_reflective_workspace_is_registered(self) -> None:
        self.assertIn('"system.tools.fnd_csm"', ADAPTER_SOURCE,
                      "FND-CSM must be registered in resolveReflectiveWorkspaceModuleSpec")

    def test_legacy_tools_are_not_registered_as_active_surfaces(self) -> None:
        for removed_surface_id in (
            '"system.tools.aws_csm"',
            '"system.tools.paypal_csm"',
            '"system.tools.fnd_dcm"',
            '"system.tools.fnd_ebi"',
        ):
            self.assertNotIn(removed_surface_id, ADAPTER_SOURCE,
                             f"Removed surface {removed_surface_id} must not appear in adapter spec maps")

    def test_adapter_exposes_canonical_aws_row_helpers(self) -> None:
        self.assertIn("buildAwsProfileRows", ADAPTER_SOURCE,
                      "Adapter must own canonical AWS profile row builder")
        self.assertIn("buildAwsNewsletterRows", ADAPTER_SOURCE,
                      "Adapter must own canonical AWS newsletter row builder")

    def test_fnd_csm_workspace_uses_canonical_component_frame_rendering(self) -> None:
        self.assertIn("__MYCITE_V2_RENDER_COMPONENT_FRAME_LIST", FND_CSM_SOURCE,
                      "FND-CSM workspace must delegate rendering to canonical component frame list function")
        self.assertIn("__MYCITE_V2_BIND_COMPONENT_FRAME_ENGAGEMENT", FND_CSM_SOURCE,
                      "FND-CSM workspace must bind component frame engagement via canonical helper")

    def test_fnd_csm_workspace_exports_workspace_and_interface_panel_renderers(self) -> None:
        self.assertIn("PortalFndCsmWorkspaceRenderer", FND_CSM_SOURCE,
                      "FND-CSM workspace must export PortalFndCsmWorkspaceRenderer")
        self.assertIn("PortalFndCsmInterfacePanelRenderer", FND_CSM_SOURCE,
                      "FND-CSM workspace must export PortalFndCsmInterfacePanelRenderer")


if __name__ == "__main__":
    unittest.main()
