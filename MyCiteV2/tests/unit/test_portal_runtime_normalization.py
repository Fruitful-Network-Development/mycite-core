from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    _normalize_action_request as normalize_cts_gis_action_request,
)
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    _normalize_request as normalize_cts_gis_request,
)
from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
    _normalize_request as normalize_workbench_request,
)


class PortalRuntimeNormalizationTests(unittest.TestCase):
    def test_workbench_request_normalization_preserves_legacy_query_aliases(self) -> None:
        portal_scope, surface_query = normalize_workbench_request(
            {
                "portal_scope": {"scope_id": "fnd"},
                "document": "sandbox:cts_gis:sc.example.json",
                "group": "documents",
                "overlay": "raw",
            }
        )
        self.assertEqual(portal_scope.scope_id, "fnd")
        self.assertEqual(
            surface_query,
            {
                "document": "sandbox:cts_gis:sc.example.json",
            },
        )

    def test_cts_gis_action_normalization_preserves_tool_state_and_payload(self) -> None:
        portal_scope, shell_state, normalized_payload, tool_state, action_kind, action_payload = normalize_cts_gis_action_request(
            {
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "shell_state": {
                    "schema": "mycite.v2.portal.shell.state.v1",
                    "active_surface_id": "system.tools.cts_gis",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                },
                "tool_state": {
                    "selected_node_id": "3-2-3-17",
                    "source": {"precinct_district_overlay_enabled": True},
                },
                "action_kind": "toggle_overlay",
                "action_payload": {"enabled": True},
            }
        )
        self.assertEqual(portal_scope.scope_id, "fnd")
        self.assertEqual(shell_state.active_surface_id, "system.tools.cts_gis")
        self.assertEqual(normalized_payload["schema"], "mycite.v2.portal.system.tools.cts_gis.action.request.v1")
        self.assertEqual(tool_state["selected_node_id"], "3-2-3-17")
        self.assertTrue(tool_state["source"]["precinct_district_overlay_enabled"])
        self.assertEqual(action_kind, "toggle_overlay")
        self.assertEqual(action_payload, {"enabled": True})

    def test_cts_gis_request_normalization_preserves_tool_state_projection_context(self) -> None:
        portal_scope, shell_state, normalized_payload, tool_state = normalize_cts_gis_request(
            {
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "shell_state": {
                    "schema": "mycite.v2.portal.shell.state.v1",
                    "active_surface_id": "system.tools.cts_gis",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                },
                "tool_state": {
                    "selected_node_id": "3-2-3-17-77",
                    "aitas": {"time_directive": "23_present-district_31"},
                },
            }
        )
        self.assertEqual(portal_scope.scope_id, "fnd")
        self.assertEqual(shell_state.active_surface_id, "system.tools.cts_gis")
        self.assertEqual(normalized_payload["schema"], "mycite.v2.portal.system.tools.cts_gis.request.v1")
        self.assertEqual(tool_state["selected_node_id"], "3-2-3-17-77")
        self.assertEqual(tool_state["aitas"]["time_directive"], "23_present-district_31")


if __name__ == "__main__":
    unittest.main()
