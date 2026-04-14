from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    build_portal_cts_gis_surface_bundle,
    run_portal_cts_gis,
)
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
    build_focus_stack_sections,
    build_system_workspace_bundle,
    read_system_workbench_projection,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    PortalScope,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_BACK_OUT,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_FILE,
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

    def test_system_root_shell_composition_uses_logo_as_the_only_system_activity_entry(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.root",
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
        activity_items = envelope["shell_composition"]["regions"]["activity_bar"]["items"]
        self.assertNotIn("system.root", [item["item_id"] for item in activity_items])
        operational_envelope = run_portal_shell_entry(
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
        roots = operational_envelope["shell_composition"]["regions"]["control_panel"]["sections"][0]["entries"]
        self.assertIn("System", [entry["label"] for entry in roots])

    def test_system_workspace_bundle_projects_anthology_as_layered_datum_table(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n'
                '  "1-0-1": [["1-0-1", "rf.3-1-1", "0"], ["anchor-root"]],\n'
                '  "1-1-1": [["1-1-1", "rf.1-0-1", "111"], ["first-datum"]],\n'
                '  "1-1-2": [["1-1-2", "rf.1-0-1", "222"], ["second-datum"]],\n'
                '  "2-3-1": [["2-3-1", "rf.1-0-1", "333"], ["third-datum"]]\n'
                '}\n',
                encoding="utf-8",
            )

            base_state = initial_portal_shell_state(
                surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            )
            bundle = build_system_workspace_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=base_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
            )
            workspace = bundle["surface_payload"]["workspace"]
            document = workspace["document"]
            self.assertEqual(document["presentation"], "anthology_layered_table")
            self.assertEqual(document["layer_groups"][0]["layer"], 1)
            self.assertEqual(document["layer_groups"][0]["value_groups"][0]["value_group"], 0)
            self.assertEqual(document["layer_groups"][0]["value_groups"][1]["rows"][1]["coordinates"]["iteration"], 2)
            self.assertIsNone(document["selected_datum"])

            datum_state = reduce_portal_shell_state(
                active_surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                current_state=base_state,
                transition={"kind": TRANSITION_FOCUS_DATUM, "file_key": "anthology", "datum_id": "1-1-2"},
                seed_anchor_file=False,
            )
            selected_bundle = build_system_workspace_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=datum_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
            )
            selected_datum = selected_bundle["surface_payload"]["workspace"]["document"]["selected_datum"]
            self.assertEqual(selected_datum["datum_id"], "1-1-2")
            self.assertEqual(selected_datum["coordinates"]["layer"], 1)
            self.assertEqual(selected_datum["coordinates"]["value_group"], 1)
            self.assertEqual(selected_datum["coordinates"]["iteration"], 2)
            self.assertIn("reference_bindings", selected_datum)
            self.assertIn("raw", selected_datum)

    def test_non_anthology_documents_keep_generic_workspace_rendering(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            (data_dir / "sandbox" / "maps" / "sources").mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n  "1-0-1": [["1-0-1", "rf.3-1-1", "0"], ["anchor-root"]]\n}\n',
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "maps" / "tool.maps.json").write_text(
                '{\n  "datum_addressing_abstraction_space": {\n    "3-1-1": [["3-1-1", "2-1-1", "0"], ["maps-anchor"]]\n  }\n}\n',
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "maps" / "sources" / "sc.example.json").write_text(
                '{\n  "4-2-118": [["4-2-118", "rf.3-1-1", "HERE"], ["summit_county_cities"]]\n}\n',
                encoding="utf-8",
            )

            scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            projection = read_system_workbench_projection(
                portal_scope=scope,
                data_dir=data_dir,
                public_dir=public_dir,
            )
            sandbox_document_id = [
                document.document_id for document in projection.documents if document.document_id != "system:anthology"
            ][0]
            shell_state = reduce_portal_shell_state(
                active_surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                current_state=initial_portal_shell_state(
                    surface_id=SYSTEM_ROOT_SURFACE_ID,
                    portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                ),
                transition={"kind": TRANSITION_FOCUS_FILE, "file_key": sandbox_document_id},
                seed_anchor_file=False,
            )
            bundle = build_system_workspace_bundle(
                portal_scope=scope,
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=shell_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
            )
            document = bundle["surface_payload"]["workspace"]["document"]
            self.assertNotIn("presentation", document)
            self.assertEqual(document["document_id"], sandbox_document_id)


if __name__ == "__main__":
    unittest.main()
