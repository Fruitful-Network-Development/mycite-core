from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    build_portal_cts_gis_surface_bundle,
    run_portal_cts_gis,
)
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
    build_system_workspace_bundle,
    read_system_workbench_projection,
)
from MyCiteV2.packages.adapters.filesystem.network_root_read_model import build_system_log_document
from MyCiteV2.packages.state_machine.portal_shell import (
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    NETWORK_ROOT_SURFACE_ID,
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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_network_chronology_authority(data_dir: Path) -> None:
    (data_dir / "system").mkdir(parents=True, exist_ok=True)
    _write_json(
        data_dir / "system" / "anthology.json",
        {
            "1-1-1": [
                [
                    "1-1-1",
                    "0-0-1",
                    "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                ],
                ["HOPS-chronological"],
            ]
        },
    )
    _write_json(
        data_dir / "system" / "sources" / "sc.fnd.quadrennium_cycle.json",
        {
            "datum_addressing_abstraction_space": {
                "1-1-1": [["1-1-1", "rf.0-0-1", "00000100011100000101100100011011111101110110110101110001111001111001111101000"], ["HOPS-quadrennium_cycle"]],
                "2-0-1": [["2-0-1", "~", "1-1-1"], ["HOPS-space-quadrennium"]],
                "3-1-1": [["3-1-1", "2-0-1", "0"], ["HOPS-babelette-quadrennium_cycle"]],
            }
        },
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

    def test_unknown_removed_surface_falls_back_to_system_workspace(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.legacy_removed_surface",
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
        self.assertTrue(envelope["reducer_owned"])
        self.assertEqual(envelope["surface_id"], SYSTEM_ROOT_SURFACE_ID)
        self.assertEqual(envelope["canonical_route"], "/portal/system")
        self.assertEqual(envelope["canonical_query"]["file"], "anthology")
        self.assertEqual(envelope["error"]["code"], "surface_unknown")

    def test_network_root_projects_system_log_workbench_without_reducer_ownership(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            public_dir = root / "public"
            for path in (data_dir, private_dir, public_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_network_chronology_authority(data_dir)
            _write_json(
                data_dir / "system" / "system_log.json",
                build_system_log_document(
                    records=[
                        {
                            "source_key": "canonical-general",
                            "source_kind": "canonical_seed",
                            "source_timestamp": "2026-07-04T00:00:00Z",
                            "title": "americas_250th_anniversary_2026_07_04",
                            "label": "americas_250th_anniversary_2026_07_04",
                            "event_type_slug": "general_event",
                            "event_type_label": "general_event",
                            "status": "scheduled",
                            "counterparty": "",
                            "contract_id": "",
                            "hops_timestamp": "0-0-0-507-916-0-0-0",
                            "raw": {"kind": "calendar"},
                        }
                    ],
                    preserved_event_types={"general_event": "general_event"},
                ),
            )
            _write_json(private_dir / "config.json", {"msn_id": "3-2-3-17-77-1-6-4-1-4"})

            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": NETWORK_ROOT_SURFACE_ID,
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "surface_query": {"view": "system_logs"},
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                private_dir=private_dir,
                audit_storage_file=None,
                aws_status_file=None,
                aws_csm_sandbox_status_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
            )

            self.assertFalse(envelope["reducer_owned"])
            self.assertEqual(envelope["surface_id"], NETWORK_ROOT_SURFACE_ID)
            self.assertEqual(envelope["canonical_route"], "/portal/network")
            self.assertEqual(envelope["canonical_query"], {"view": "system_logs"})
            self.assertEqual(envelope["surface_payload"]["kind"], "network_system_log_workspace")
            self.assertEqual(envelope["surface_payload"]["workspace"]["state"], "ready")
            self.assertEqual(
                envelope["shell_composition"]["regions"]["workbench"]["kind"],
                "network_system_log_workbench",
            )
            self.assertEqual(
                envelope["shell_composition"]["regions"]["inspector"]["kind"],
                "network_system_log_inspector",
            )
            self.assertFalse(envelope["shell_composition"]["inspector_collapsed"])

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
                "requested_surface_id": "system.legacy_removed_surface",
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
        control_panel = operational_envelope["shell_composition"]["regions"]["control_panel"]
        self.assertEqual(control_panel["kind"], "focus_selection_panel")
        self.assertEqual(control_panel["surface_label"], "SYSTEM")

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
            control_panel = bundle["control_panel"]
            self.assertEqual(document["presentation"], "anthology_layered_table")
            self.assertEqual(document["layer_groups"][0]["layer"], 1)
            self.assertEqual(document["layer_groups"][0]["value_groups"][0]["value_group"], 0)
            self.assertEqual(document["layer_groups"][0]["value_groups"][1]["rows"][1]["coordinates"]["iteration"], 2)
            self.assertIsNone(document["selected_datum"])
            self.assertEqual(control_panel["kind"], "focus_selection_panel")
            self.assertEqual(control_panel["surface_label"], "SYSTEM")
            self.assertEqual(
                control_panel["context_items"][:2],
                [
                    {"label": "Sandbox", "value": "SYSTEM"},
                    {"label": "File", "value": "anthology.json"},
                ],
            )
            self.assertIn("Layer 1", [group["title"] for group in control_panel["groups"]])

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
            selected_panel = selected_bundle["control_panel"]
            self.assertEqual(selected_panel["context_items"][2]["label"], "Datum")
            self.assertEqual(selected_panel["groups"][0]["title"], "Below Focus")

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
