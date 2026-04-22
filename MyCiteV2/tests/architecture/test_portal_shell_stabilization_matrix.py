from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_DCM_TOOL_SURFACE_ID,
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
            "/portal/system/tools/aws-csm",
            "/portal/system/tools/cts-gis",
            "/portal/system/tools/fnd-dcm",
            "/portal/system/tools/workbench-ui",
            "/portal/network",
            "/portal/utilities",
        ):
            self.assertIn(route, matrix_doc)
        self.assertIn("reflective_workspace", matrix_doc)
        self.assertIn("directive_panel", matrix_doc)
        self.assertIn("presentation_surface", matrix_doc)

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
                inspector={},
                shell_state=None,
            )

        system = composition_for(SYSTEM_ROOT_SURFACE_ID)
        self.assertFalse(system["workbench_collapsed"])
        self.assertTrue(system["interface_panel_collapsed"])

        aws = composition_for(AWS_CSM_TOOL_SURFACE_ID)
        cts = composition_for(CTS_GIS_TOOL_SURFACE_ID)
        fnd = composition_for(FND_DCM_TOOL_SURFACE_ID)
        for tool_composition in (aws, cts, fnd):
            self.assertTrue(tool_composition["workbench_collapsed"])
            self.assertFalse(tool_composition["interface_panel_collapsed"])

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
