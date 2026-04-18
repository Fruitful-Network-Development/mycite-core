from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    FND_DCM_TOOL_REQUEST_SCHEMA,
    FND_DCM_TOOL_SURFACE_SCHEMA,
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    PORTAL_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
    PORTAL_RUNTIME_REQUIRED_ENVELOPE_KEYS,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    build_portal_runtime_envelope,
    build_portal_runtime_entrypoint_catalog,
    build_portal_runtime_error,
    resolve_portal_runtime_entrypoint,
)


class PortalRuntimePlatformContractTests(unittest.TestCase):
    def test_entrypoint_catalog_is_static_and_serializable(self) -> None:
        descriptors = [entry.to_dict() for entry in build_portal_runtime_entrypoint_catalog()]
        self.assertTrue(descriptors)
        self.assertEqual(
            {entry["schema"] for entry in descriptors},
            {PORTAL_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA},
        )
        self.assertEqual(descriptors[0]["entrypoint_id"], "portal.shell")
        self.assertEqual(descriptors[0]["route"], "/portal/api/v2/shell")
        self.assertIn("portal.system.tools.fnd_dcm", [entry["entrypoint_id"] for entry in descriptors])
        self.assertIn("/portal/api/v2/system/tools/fnd-dcm", [entry["route"] for entry in descriptors])
        self.assertEqual(json.loads(json.dumps(descriptors, sort_keys=True)), descriptors)
        self.assertIsNone(resolve_portal_runtime_entrypoint("missing.entrypoint"))

    def test_runtime_envelope_shape_is_fixed_and_includes_canonical_navigation(self) -> None:
        envelope = build_portal_runtime_envelope(
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            requested_surface_id="system.root",
            surface_id="system.root",
            entrypoint_id="portal.shell",
            read_write_posture="read-only",
            reducer_owned=True,
            canonical_route="/portal/system",
            canonical_query={"file": "anthology", "verb": "navigate"},
            canonical_url="/portal/system?file=anthology&verb=navigate",
            shell_state={"schema": "mycite.v2.portal.shell.state.v1", "active_surface_id": "system.root"},
            surface_payload={"schema": "mycite.v2.portal.system.workspace.surface.v1"},
            shell_composition={"schema": "mycite.v2.portal.shell.composition.v1", "regions": {}},
            warnings=[],
            error=None,
        )
        self.assertEqual(tuple(envelope.keys()), PORTAL_RUNTIME_REQUIRED_ENVELOPE_KEYS)
        self.assertEqual(envelope["schema"], PORTAL_RUNTIME_ENVELOPE_SCHEMA)
        self.assertTrue(envelope["reducer_owned"])
        self.assertEqual(envelope["canonical_route"], "/portal/system")
        self.assertEqual(envelope["canonical_query"]["file"], "anthology")
        self.assertEqual(
            build_portal_runtime_error(code="surface_unknown", message="Missing"),
            {"code": "surface_unknown", "message": "Missing"},
        )

    def test_workspace_profile_basics_action_schema_is_neutral(self) -> None:
        self.assertEqual(
            SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
            "mycite.v2.portal.system.workspace.profile_basics.action.request.v1",
        )

    def test_fnd_dcm_request_and_surface_schemas_are_fixed(self) -> None:
        self.assertEqual(
            FND_DCM_TOOL_REQUEST_SCHEMA,
            "mycite.v2.portal.system.tools.fnd_dcm.request.v1",
        )
        self.assertEqual(
            FND_DCM_TOOL_SURFACE_SCHEMA,
            "mycite.v2.portal.system.tools.fnd_dcm.surface.v1",
        )


if __name__ == "__main__":
    unittest.main()
