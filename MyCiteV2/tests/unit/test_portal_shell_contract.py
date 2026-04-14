from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.portal_shell import (
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    AWS_TOOL_SURFACE_ID,
    build_portal_surface_catalog,
    canonical_route_for_surface,
    requires_shell_state_machine,
    resolve_portal_shell_request,
)


class PortalShellContractTests(unittest.TestCase):
    def test_surface_catalog_is_rooted_in_system_network_utilities(self) -> None:
        catalog = [entry.to_dict() for entry in build_portal_surface_catalog()]
        self.assertEqual(
            [entry["surface_id"] for entry in catalog[:3]],
            [
                SYSTEM_ROOT_SURFACE_ID,
                SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
                "system.activity",
            ],
        )
        self.assertIn("/portal/system", [entry["route"] for entry in catalog])
        self.assertIn("/portal/network", [entry["route"] for entry in catalog])
        self.assertIn("/portal/utilities", [entry["route"] for entry in catalog])
        self.assertNotIn("/portal/utilities/aws", [entry["route"] for entry in catalog])

    def test_tool_pages_are_system_children_and_use_shell_state_machine(self) -> None:
        self.assertEqual(canonical_route_for_surface(AWS_TOOL_SURFACE_ID), "/portal/system/tools/aws")
        self.assertTrue(requires_shell_state_machine(SYSTEM_ROOT_SURFACE_ID))
        self.assertTrue(requires_shell_state_machine(AWS_TOOL_SURFACE_ID))
        self.assertFalse(requires_shell_state_machine(NETWORK_ROOT_SURFACE_ID))
        self.assertFalse(requires_shell_state_machine(UTILITIES_ROOT_SURFACE_ID))

    def test_shell_request_resolves_only_cataloged_surfaces(self) -> None:
        allowed = resolve_portal_shell_request(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": SYSTEM_ROOT_SURFACE_ID,
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            }
        )
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.active_surface_id, SYSTEM_ROOT_SURFACE_ID)

        unknown = resolve_portal_shell_request(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "unknown.surface",
                "portal_scope": {"scope_id": "fnd", "capabilities": []},
            }
        )
        self.assertFalse(unknown.allowed)
        self.assertEqual(unknown.active_surface_id, SYSTEM_ROOT_SURFACE_ID)


if __name__ == "__main__":
    unittest.main()
