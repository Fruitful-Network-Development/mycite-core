from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    FND_CSM_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    build_shell_composition_payload,
)


class PortalShellStabilizationMatrixTests(unittest.TestCase):
    def test_matrix_document_tracks_required_canonical_routes(self) -> None:
        matrix_doc = (REPO_ROOT / "docs" / "plans" / "one_shell_stabilization_matrix.md").read_text(encoding="utf-8")
        for route in (
            "/portal/system",
            "/portal/system/tools/cts-gis",
            "/portal/system/tools/workbench-ui",
            "/portal/network",
            "/portal/utilities",
        ):
            self.assertIn(route, matrix_doc)
        self.assertIn("reflective_workspace", matrix_doc)
        self.assertIn("directive_panel", matrix_doc)
        self.assertIn("presentation_surface", matrix_doc)
        self.assertIn("all canonical routes now use only", matrix_doc)
        self.assertIn("family-first shell composition is the active route contract", matrix_doc)

    def test_first_load_posture_matches_stabilization_matrix_expectations(self) -> None:
        def composition_for(surface_id: str) -> dict[str, object]:
            return build_shell_composition_payload(
                active_surface_id=surface_id,
                portal_instance_id="fnd",
                page_title="test",
                page_subtitle="",
                activity_items=[],
                control_panel={},
                workbench={"visible": True},
                interface_panel={},
                shell_state=None,
            )

        system = composition_for(SYSTEM_ROOT_SURFACE_ID)
        self.assertFalse(system["workbench_collapsed"])
        self.assertTrue(system["interface_panel_collapsed"])

        fnd_csm = composition_for(FND_CSM_TOOL_SURFACE_ID)
        self.assertTrue(fnd_csm["workbench_collapsed"])
        self.assertFalse(fnd_csm["interface_panel_collapsed"])

        cts = composition_for(CTS_GIS_TOOL_SURFACE_ID)
        # CTS-GIS has default_workbench_visible=True — workbench is center foreground
        self.assertFalse(cts["workbench_collapsed"])
        self.assertFalse(cts["interface_panel_collapsed"])
        self.assertEqual(cts["foreground_shell_region"], "center-workbench")

        workbench_ui = composition_for(WORKBENCH_UI_TOOL_SURFACE_ID)
        self.assertFalse(workbench_ui["workbench_collapsed"])
        self.assertFalse(workbench_ui["interface_panel_collapsed"])

        network = composition_for(NETWORK_ROOT_SURFACE_ID)
        self.assertFalse(network["workbench_collapsed"])
        self.assertTrue(network["interface_panel_collapsed"])

        utilities = composition_for(UTILITIES_ROOT_SURFACE_ID)
        self.assertFalse(utilities["workbench_collapsed"])
        self.assertTrue(utilities["interface_panel_collapsed"])


if __name__ == "__main__":
    unittest.main()
