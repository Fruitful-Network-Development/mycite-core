from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
    SYSTEM_ANCHOR_FILE_KEY,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_BACK_OUT,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_FILE,
    TRANSITION_FOCUS_OBJECT,
    UTILITIES_ROOT_SURFACE_ID,
    VERB_NAVIGATE,
    build_portal_activity_dispatch_bodies,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
    canonical_query_for_shell_state,
    canonical_route_for_surface,
    initial_portal_shell_state,
    reduce_portal_shell_state,
    requires_shell_state_machine,
    resolve_portal_shell_request,
)


class PortalShellContractTests(unittest.TestCase):
    def test_surface_catalog_removes_activity_and_profile_as_first_class_surfaces(self) -> None:
        catalog = [entry.to_dict() for entry in build_portal_surface_catalog()]
        surface_ids = [entry["surface_id"] for entry in catalog]
        routes = [entry["route"] for entry in catalog]
        self.assertEqual(
            surface_ids[:3],
            [
                SYSTEM_ROOT_SURFACE_ID,
                NETWORK_ROOT_SURFACE_ID,
                UTILITIES_ROOT_SURFACE_ID,
            ],
        )
        self.assertNotIn("system.activity", surface_ids)
        self.assertNotIn("system.profile_basics", surface_ids)
        self.assertNotIn("/portal/system/activity", routes)
        self.assertNotIn("/portal/system/profile-basics", routes)

    def test_state_machine_is_limited_to_system_workspace_and_tool_surfaces(self) -> None:
        self.assertEqual(canonical_route_for_surface(AWS_TOOL_SURFACE_ID), "/portal/system/tools/aws")
        self.assertTrue(requires_shell_state_machine(SYSTEM_ROOT_SURFACE_ID))
        self.assertTrue(requires_shell_state_machine(AWS_TOOL_SURFACE_ID))
        self.assertFalse(requires_shell_state_machine(NETWORK_ROOT_SURFACE_ID))
        self.assertFalse(requires_shell_state_machine(UTILITIES_ROOT_SURFACE_ID))

    def test_fresh_system_root_state_seeds_the_anchor_file(self) -> None:
        state = initial_portal_shell_state(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
        )
        self.assertEqual(state.active_surface_id, SYSTEM_ROOT_SURFACE_ID)
        self.assertEqual([segment.level for segment in state.focus_path], ["sandbox", "file"])
        self.assertEqual(state.focus_path[-1].id, SYSTEM_ANCHOR_FILE_KEY)
        self.assertEqual(canonical_query_for_shell_state(state, surface_id=SYSTEM_ROOT_SURFACE_ID)["file"], "anthology")

    def test_back_out_contracts_focus_in_object_datum_file_sandbox_order(self) -> None:
        base_state = initial_portal_shell_state(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
        )
        datum_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            current_state=base_state,
            transition={"kind": TRANSITION_FOCUS_DATUM, "file_key": "anthology", "datum_id": "1-1-1"},
            seed_anchor_file=False,
        )
        object_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            current_state=datum_state,
            transition={"kind": TRANSITION_FOCUS_OBJECT, "file_key": "anthology", "datum_id": "1-1-1", "object_id": "1-0-0"},
            seed_anchor_file=False,
        )
        contracted_datum = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            current_state=object_state,
            transition={"kind": TRANSITION_BACK_OUT},
            seed_anchor_file=False,
        )
        contracted_file = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            current_state=contracted_datum,
            transition={"kind": TRANSITION_BACK_OUT},
            seed_anchor_file=False,
        )
        contracted_sandbox = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            current_state=contracted_file,
            transition={"kind": TRANSITION_BACK_OUT},
            seed_anchor_file=False,
        )
        no_op = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            current_state=contracted_sandbox,
            transition={"kind": TRANSITION_BACK_OUT},
            seed_anchor_file=False,
        )
        self.assertEqual([segment.level for segment in contracted_datum.focus_path], ["sandbox", "file", "datum"])
        self.assertEqual([segment.level for segment in contracted_file.focus_path], ["sandbox", "file"])
        self.assertEqual([segment.level for segment in contracted_sandbox.focus_path], ["sandbox"])
        self.assertEqual([segment.level for segment in no_op.focus_path], ["sandbox"])
        self.assertEqual(no_op.verb, VERB_NAVIGATE)

    def test_tool_defaults_are_interface_led_and_workbench_hidden(self) -> None:
        registry_entries = [entry.to_dict() for entry in build_portal_tool_registry_entries()]
        self.assertTrue(registry_entries)
        for entry in registry_entries:
            self.assertEqual(entry["surface_posture"], SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY)
            self.assertFalse(entry["default_workbench_visible"])

    def test_dispatch_bodies_preserve_portal_capabilities(self) -> None:
        state = initial_portal_shell_state(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing", "datum_recognition"]},
        )
        dispatch = build_portal_activity_dispatch_bodies(
            portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing", "datum_recognition"]},
            shell_state=state,
        )
        self.assertIn(SYSTEM_ROOT_SURFACE_ID, dispatch)
        self.assertIn(AWS_TOOL_SURFACE_ID, dispatch)
        self.assertNotIn(NETWORK_ROOT_SURFACE_ID, dispatch)
        self.assertEqual(
            dispatch[AWS_TOOL_SURFACE_ID]["portal_scope"]["capabilities"],
            ["fnd_peripheral_routing", "datum_recognition"],
        )

    def test_shell_request_resolution_returns_canonical_query_for_reducer_surfaces(self) -> None:
        selection = resolve_portal_shell_request(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": SYSTEM_ROOT_SURFACE_ID,
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            }
        )
        self.assertTrue(selection.allowed)
        self.assertTrue(selection.reducer_owned)
        self.assertEqual(selection.active_surface_id, SYSTEM_ROOT_SURFACE_ID)
        self.assertEqual(selection.canonical_query["file"], "anthology")
        self.assertEqual(selection.canonical_query["verb"], "navigate")

    def test_shell_request_resolution_projects_surface_query_for_network(self) -> None:
        selection = resolve_portal_shell_request(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": NETWORK_ROOT_SURFACE_ID,
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                "surface_query": {
                    "view": "system_logs",
                    "contract": "contract-fnd-001",
                    "type": "4-2-1",
                    "record": "7-3-1",
                    "ignored": "yes",
                },
            }
        )
        self.assertTrue(selection.allowed)
        self.assertFalse(selection.reducer_owned)
        self.assertEqual(selection.active_surface_id, NETWORK_ROOT_SURFACE_ID)
        self.assertEqual(
            selection.canonical_query,
            {
                "view": "system_logs",
                "contract": "contract-fnd-001",
                "type": "4-2-1",
                "record": "7-3-1",
            },
        )

    def test_unknown_removed_surface_resolves_as_unknown_and_falls_back_to_system(self) -> None:
        selection = resolve_portal_shell_request(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.legacy_removed_surface",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            }
        )
        self.assertFalse(selection.allowed)
        self.assertTrue(selection.reducer_owned)
        self.assertEqual(selection.active_surface_id, SYSTEM_ROOT_SURFACE_ID)
        self.assertEqual(selection.reason_code, "surface_unknown")
        self.assertEqual(selection.canonical_route, "/portal/system")
        self.assertEqual(selection.canonical_query["file"], "anthology")


if __name__ == "__main__":
    unittest.main()
