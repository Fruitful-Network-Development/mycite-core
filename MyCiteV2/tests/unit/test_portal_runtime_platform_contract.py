from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    PORTAL_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA,
    PORTAL_RUNTIME_REQUIRED_ENVELOPE_KEYS,
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
        self.assertEqual(json.loads(json.dumps(descriptors, sort_keys=True)), descriptors)
        self.assertIsNone(resolve_portal_runtime_entrypoint("missing.entrypoint"))

    def test_runtime_envelope_shape_is_fixed(self) -> None:
        envelope = build_portal_runtime_envelope(
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            requested_surface_id="system.root",
            surface_id="system.root",
            entrypoint_id="portal.shell",
            read_write_posture="read-only",
            shell_state={"schema": "mycite.v2.portal.shell.state.v1", "allowed": True},
            surface_payload={"schema": "mycite.v2.portal.system.surface.v1"},
            shell_composition={"schema": "mycite.v2.portal.shell.composition.v1", "regions": {}},
            warnings=[],
            error=None,
        )
        self.assertEqual(tuple(envelope.keys()), PORTAL_RUNTIME_REQUIRED_ENVELOPE_KEYS)
        self.assertEqual(envelope["schema"], PORTAL_RUNTIME_ENVELOPE_SCHEMA)
        self.assertEqual(
            build_portal_runtime_error(code="surface_unknown", message="Missing"),
            {"code": "surface_unknown", "message": "Missing"},
        )


if __name__ == "__main__":
    unittest.main()
