from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    LegacyMapsAliasUnsupportedError,
    run_portal_cts_gis,
    run_portal_cts_gis_action,
)


class CtsGisRequestValidationTests(unittest.TestCase):
    def _base_payload(self) -> dict[str, object]:
        return {
            "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
        }

    def _legacy_document_id(self) -> str:
        return "sandbox:" + ("map" + "s") + ":sc.example.json"

    def test_rejects_legacy_maps_document_ids_across_supported_request_slots(self) -> None:
        cases = (
            (
                "selected_document_id",
                {"selected_document_id": self._legacy_document_id()},
            ),
            (
                "attention_document_id",
                {"attention_document_id": self._legacy_document_id()},
            ),
            (
                "mediation_state.attention_document_id",
                {"mediation_state": {"attention_document_id": self._legacy_document_id()}},
            ),
            (
                "tool_state.source.attention_document_id",
                {"tool_state": {"source": {"attention_document_id": self._legacy_document_id()}}},
            ),
        )

        for expected_field, patch in cases:
            with self.subTest(field=expected_field):
                payload = self._base_payload()
                payload.update(patch)
                with self.assertRaises(LegacyMapsAliasUnsupportedError) as context:
                    run_portal_cts_gis(payload, data_dir=None)
                self.assertEqual(context.exception.code, "legacy_maps_alias_unsupported")
                self.assertIn(expected_field, context.exception.fields)

    def test_rejects_legacy_maps_tool_id_aliases_when_provided(self) -> None:
        payload = self._base_payload()
        payload["tool_id"] = "map" + "s"
        with self.assertRaises(LegacyMapsAliasUnsupportedError) as context:
            run_portal_cts_gis(payload, data_dir=None)
        self.assertIn("tool_id", context.exception.fields)

    def test_accepts_canonical_cts_gis_request(self) -> None:
        payload = self._base_payload()
        payload["selected_document_id"] = "sandbox:cts_gis:sc.example.json"
        envelope = run_portal_cts_gis(payload, data_dir=None)
        self.assertEqual(envelope["surface_id"], "system.tools.cts_gis")
        self.assertTrue(envelope["shell_composition"]["workbench_collapsed"])
        self.assertFalse(envelope["shell_composition"]["interface_panel_collapsed"])
        self.assertFalse(envelope["shell_composition"]["regions"]["workbench"]["visible"])
        self.assertTrue(envelope["shell_composition"]["regions"]["interface_panel"]["visible"])

    def test_rejects_unknown_cts_gis_action_kind(self) -> None:
        with self.assertRaises(ValueError):
            run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": {},
                    "action_kind": "nope",
                    "action_payload": {},
                },
                data_dir=None,
                authority_db_file=None,
            )

    def test_accepts_yaml_text_and_json_mapping_stage_requests(self) -> None:
        base_request = {
            "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            "tool_state": {
                "selected_node_id": "3-2-3-17-77-1",
                "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
            },
            "action_kind": "stage_insert_yaml",
        }
        yaml_request = dict(base_request)
        yaml_request["action_payload"] = {
            "stage_text": "\n".join(
                [
                    "schema: mycite.v2.cts_gis.stage_insert.v1",
                    "document_id: sandbox:cts_gis:sc.example.json",
                    "document_name: sc.example.json",
                    "operation: insert_datums",
                    "datums:",
                    "  - family: administrative_street",
                    "    valueGroup: 2",
                    "    targetNodeAddress: 3-2-3-17-77-1",
                    '    title: "MAIN STREET"',
                    "    references:",
                    "      - type: msn-samras",
                    "        nodeAddress: 3-2-3-17-77-1",
                    "      - type: title",
                    '        text: "MAIN STREET"',
                ]
            )
        }
        json_request = dict(base_request)
        json_request["action_payload"] = {
            "stage_document": {
                "schema": "mycite.v2.cts_gis.stage_insert.v1",
                "document_id": "sandbox:cts_gis:sc.example.json",
                "document_name": "sc.example.json",
                "operation": "insert_datums",
                "datums": [
                    {
                        "family": "administrative_street",
                        "valueGroup": 2,
                        "targetNodeAddress": "3-2-3-17-77-1",
                        "title": "MAIN STREET",
                        "references": [
                            {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                            {"type": "title", "text": "MAIN STREET"},
                        ],
                    }
                ],
            }
        }

        yaml_envelope = run_portal_cts_gis_action(yaml_request, data_dir=None, authority_db_file=None)
        json_envelope = run_portal_cts_gis_action(json_request, data_dir=None, authority_db_file=None)

        self.assertEqual(yaml_envelope["surface_payload"]["action_result"]["action_kind"], "stage_insert_yaml")
        self.assertEqual(json_envelope["surface_payload"]["action_result"]["action_kind"], "stage_insert_yaml")
        self.assertEqual(
            yaml_envelope["surface_payload"]["staged_insert"]["schema"],
            "mycite.v2.cts_gis.staged_insert.state.v1",
        )
        self.assertEqual(
            json_envelope["surface_payload"]["staged_insert"]["schema"],
            "mycite.v2.cts_gis.staged_insert.state.v1",
        )


if __name__ == "__main__":
    unittest.main()
