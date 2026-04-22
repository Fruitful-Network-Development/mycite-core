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


if __name__ == "__main__":
    unittest.main()
