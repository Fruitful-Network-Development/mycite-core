from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    build_portal_cts_gis_surface_bundle,
    run_portal_cts_gis,
)
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_focus_stack_sections
from MyCiteV2.packages.state_machine.portal_shell import (
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    PortalScope,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_BACK_OUT,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_OBJECT,
    TRANSITION_SET_VERB,
    VERB_MEDIATE,
    VERB_NAVIGATE,
    initial_portal_shell_state,
    reduce_portal_shell_state,
)


class PortalWorkspaceRuntimeBehaviorTests(unittest.TestCase):
    def test_mediation_transition_opens_interface_panel_and_back_out_clears_removed_subject(self) -> None:
        scope = {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]}
        state = initial_portal_shell_state(surface_id=SYSTEM_ROOT_SURFACE_ID, portal_scope=scope)
        datum_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=state,
            transition={"kind": TRANSITION_FOCUS_DATUM, "file_key": "anthology", "datum_id": "1-1-1"},
            seed_anchor_file=False,
        )
        object_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=datum_state,
            transition={"kind": TRANSITION_FOCUS_OBJECT, "file_key": "anthology", "datum_id": "1-1-1", "object_id": "1-0-0"},
            seed_anchor_file=False,
        )
        mediation_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=object_state,
            transition={"kind": TRANSITION_SET_VERB, "verb": VERB_MEDIATE},
            seed_anchor_file=False,
        )
        self.assertEqual(mediation_state.verb, VERB_MEDIATE)
        self.assertTrue(mediation_state.chrome.interface_panel_open)
        self.assertEqual(mediation_state.mediation_subject, {"level": FOCUS_LEVEL_OBJECT, "id": "1-0-0"})

        backed_out = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=mediation_state,
            transition={"kind": TRANSITION_BACK_OUT},
            seed_anchor_file=False,
        )
        self.assertEqual(backed_out.verb, VERB_NAVIGATE)
        self.assertFalse(backed_out.chrome.interface_panel_open)
        self.assertIsNone(backed_out.mediation_subject)

    def test_focus_stack_sections_preserve_order_and_compression(self) -> None:
        shell_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope={"scope_id": "fnd", "capabilities": []},
            current_state=reduce_portal_shell_state(
                active_surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": []},
                current_state=initial_portal_shell_state(
                    surface_id=SYSTEM_ROOT_SURFACE_ID,
                    portal_scope={"scope_id": "fnd", "capabilities": []},
                ),
                transition={"kind": TRANSITION_FOCUS_DATUM, "file_key": "anthology", "datum_id": "datum-1"},
                seed_anchor_file=False,
            ),
            transition={"kind": TRANSITION_FOCUS_OBJECT, "file_key": "anthology", "datum_id": "datum-1", "object_id": "object-1"},
            seed_anchor_file=False,
        )
        portal_scope = PortalScope(scope_id="fnd", capabilities=())
        binding = SimpleNamespace(
            anchor_address="object-1",
            normalized_reference_form="object-1",
            anchor_label="Object 1",
            resolution_state="resolved",
            value_token="value-1",
        )
        row = SimpleNamespace(
            datum_address="datum-1",
            labels=("Datum 1",),
            diagnostic_states=("ok",),
            reference_bindings=(binding,),
            primary_value_token="value-1",
        )
        document = SimpleNamespace(
            rows=(row,),
            diagnostic_totals={},
            document_id="system:anthology",
            document_name="Anthology",
            tool_id="",
            source_kind="authoritative",
            relative_path="anthology.json",
        )
        sections = build_focus_stack_sections(
            portal_scope=portal_scope,
            shell_state=shell_state,
            file_entries=[
                {"file_key": "anthology", "label": "Anthology", "detail": "anchor", "active": True},
                {"file_key": "activity", "label": "Activity", "detail": "history", "active": False},
            ],
            active_document=document,
            selected_datum=row,
            selected_object={"label": "Object 1", "detail": "resolved"},
            tool_rows=[],
        )
        self.assertEqual(
            [section["title"] for section in sections],
            ["Sandbox", "File", "Datum", "Object", "Current Intention"],
        )
        self.assertTrue(sections[0]["compressed"])
        self.assertTrue(sections[1]["compressed"])
        self.assertTrue(sections[2]["compressed"])
        self.assertFalse(sections[3]["compressed"])
        self.assertEqual(sections[0]["facts"][0]["value"], FOCUS_LEVEL_OBJECT)

    def test_tool_runtime_hides_workbench_by_default_and_returns_canonical_url(self) -> None:
        bundle = build_portal_cts_gis_surface_bundle(
            portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
            shell_state=initial_portal_shell_state(
                surface_id="system.tools.cts_gis",
                portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            ),
            data_dir=None,
        )
        self.assertFalse(bundle["workbench"]["visible"])

        envelope = run_portal_cts_gis(
            {
                "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            },
            data_dir=None,
        )
        self.assertEqual(envelope["surface_id"], "system.tools.cts_gis")
        self.assertTrue(envelope["reducer_owned"])
        self.assertEqual(envelope["canonical_query"]["file"], "anthology")
        self.assertEqual(envelope["canonical_query"]["verb"], "mediate")
        self.assertEqual(envelope["canonical_url"], "/portal/system/tools/cts-gis?file=anthology&verb=mediate")

    def test_operational_status_is_outside_reducer_ownership(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.operational_status",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            aws_status_file=None,
            aws_csm_sandbox_status_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        self.assertFalse(envelope["reducer_owned"])
        self.assertEqual(envelope["surface_id"], "system.operational_status")
        self.assertEqual(envelope["canonical_route"], "/portal/system/operational-status")
        self.assertEqual(envelope["canonical_query"], {})


if __name__ == "__main__":
    unittest.main()
