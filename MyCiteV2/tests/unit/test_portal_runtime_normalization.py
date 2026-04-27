from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import _normalize_action_request as normalize_aws_action_request
from MyCiteV2.instances._shared.runtime.portal_aws_runtime import _normalize_request as normalize_aws_request
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import _normalize_action_request as normalize_cts_gis_action_request
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import _normalize_request as normalize_cts_gis_request
from MyCiteV2.instances._shared.runtime.portal_fnd_dcm_runtime import _normalize_request as normalize_fnd_dcm_request
from MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime import _normalize_request as normalize_fnd_ebi_request
from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import _normalize_request as normalize_workbench_request


class PortalRuntimeNormalizationTests(unittest.TestCase):
    def test_aws_request_normalization_preserves_legacy_surface_query_shape(self) -> None:
        portal_scope, surface_query = normalize_aws_request(
            {
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition"]},
                "domain": "cvccboard.org",
                "view": "domains",
                "profile": "aws-csm.cvccboard.nathan",
                "section": "onboarding",
            }
        )
        self.assertEqual(portal_scope.scope_id, "fnd")
        self.assertEqual(
            surface_query,
            {
                "domain": "cvccboard.org",
                "profile": "aws-csm.cvccboard.nathan",
                "section": "onboarding",
                "view": "domains",
            },
        )

    def test_aws_action_normalization_uses_envelope_action_when_payload_omits_it(self) -> None:
        portal_scope, surface_query, shell_state, action_kind, action_payload = normalize_aws_action_request(
            {
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition"]},
                "surface_query": {"domain": "cvccboard.org"},
                "shell_state": {"schema": "mycite.v2.portal.shell.state.v1"},
                "nimm_envelope": {
                    "directive": {
                        "schema": "mycite.v2.nimm.directive.v1",
                        "verb": "manipulate",
                        "target_authority": "aws_csm",
                        "target_document_id": "aws-csm",
                        "targets": [{"object_ref": "cvccboard.org"}],
                        "payload": {"action_kind": "create_domain", "action_payload": {"domain": "cvccboard.org"}},
                    },
                    "aitas": {},
                },
            }
        )
        self.assertEqual(portal_scope.scope_id, "fnd")
        self.assertEqual(surface_query, {"domain": "cvccboard.org", "view": "domains"})
        self.assertIsInstance(shell_state, dict)
        self.assertEqual(action_kind, "create_domain")
        self.assertEqual(action_payload, {"domain": "cvccboard.org"})

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

    def test_fnd_dcm_request_normalization_preserves_default_capabilities(self) -> None:
        portal_scope, surface_query = normalize_fnd_dcm_request(
            {
                "portal_scope": {"scope_id": "fnd"},
                "site": "fruitfulnetworkdevelopment.com",
                "view": "pages",
            }
        )
        self.assertIn("datum_recognition", portal_scope.capabilities)
        self.assertIn("hosted_site_visibility", portal_scope.capabilities)
        self.assertEqual(surface_query, {"site": "fruitfulnetworkdevelopment.com", "view": "pages"})

    def test_fnd_ebi_request_normalization_preserves_shell_state_context(self) -> None:
        portal_scope, shell_state, normalized_payload = normalize_fnd_ebi_request(
            {
                "portal_scope": {"scope_id": "fnd", "capabilities": ["hosted_site_visibility"]},
                "shell_state": {
                    "schema": "mycite.v2.portal.shell.state.v1",
                    "active_surface_id": "system.tools.fnd_ebi",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["hosted_site_visibility"]},
                },
            }
        )
        self.assertEqual(portal_scope.scope_id, "fnd")
        self.assertEqual(shell_state.active_surface_id, "system.tools.fnd_ebi")
        self.assertEqual(normalized_payload["schema"], "mycite.v2.portal.system.tools.fnd_ebi.request.v1")

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
