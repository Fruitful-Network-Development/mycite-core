from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.admin_cts_gis_runtime import run_admin_cts_gis_read_only
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    build_admin_tool_exposure_policy,
)
from MyCiteV2.packages.state_machine.hanus_shell import CTS_GIS_READ_ONLY_ENTRYPOINT_ID, CTS_GIS_READ_ONLY_SLICE_ID


def _write_minimal_data(data_dir: Path) -> None:
    (data_dir / "system" / "sources").mkdir(parents=True)
    (data_dir / "payloads" / "cache").mkdir(parents=True)
    (data_dir / "system" / "anthology.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "payloads" / "cache" / "sc.example.txa.json").write_text("{}\n", encoding="utf-8")


def _write_maps_data(data_dir: Path) -> None:
    tool_dir = data_dir / "sandbox" / "maps"
    source_dir = tool_dir / "sources"
    source_dir.mkdir(parents=True)
    summit_binary = "01110011011101010110110101101101011010010111010000000000"
    fairlawn_binary = "011001100110000101101001011100100110110001100001011101110110111000000000"
    (tool_dir / "tool.maps.json").write_text(
        json.dumps(
            {
                "3-1-1": [["3-1-1", "~", "0-0-0"], ["HOPS-babelette-coordinate"]],
                "3-1-2": [["3-1-2", "~", "0-0-0"], ["SAMRAS-babelette-msn_id"]],
                "3-1-3": [["3-1-3", "~", "0-0-0"], ["title-babelette"]],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source_dir / "sc.example.json").write_text(
        json.dumps(
            {
                "anchor_file_version": "<hash here>",
                "datum_addressing_abstraction_space": {
                    "4-2-1": [
                        [
                            "4-2-1",
                            "rf.3-1-1",
                            "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                            "rf.3-1-1",
                            "3-76-11-40-92-20-21-92-81-25-68-43-68-84-44-22-24",
                            "rf.3-1-1",
                            "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
                        ],
                        ["polygon_1"],
                    ],
                    "4-2-2": [
                        ["4-2-2", "rf.3-1-1", "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73"],
                        ["point_alpha"],
                    ],
                    "5-0-1": [
                        ["5-0-1", "~", "4-2-1"],
                        ["summit_boundary"],
                    ],
                    "6-0-1": [
                        ["6-0-1", "~", "4-2-2"],
                        ["fairlawn_boundary_collection"],
                    ],
                    "7-3-1": [
                        ["7-3-1", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", summit_binary, "5-0-1", "1"],
                        ["summit_county"],
                    ],
                    "7-3-2": [
                        ["7-3-2", "rf.3-1-2", "3-2-3-17-77-1-1", "rf.3-1-3", fairlawn_binary, "6-0-1", "1"],
                        ["fairlawn_city"],
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


class AdminCtsGisRuntimeIntegrationTests(unittest.TestCase):
    def test_cts_gis_read_only_returns_projectable_surface_when_enabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            _write_minimal_data(data_dir)
            _write_maps_data(data_dir)
            policy = build_admin_tool_exposure_policy(
                {"cts_gis": {"enabled": True}},
                known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis", "fnd_ebi"],
            )

            result = run_admin_cts_gis_read_only(
                {
                    "schema": ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
                data_dir=data_dir,
                portal_tenant_id="fnd",
                tool_exposure_policy=policy,
            )

            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], CTS_GIS_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], CTS_GIS_READ_ONLY_SLICE_ID)
            self.assertIsNone(result["error"])
            self.assertEqual(result["shell_composition"]["composition_mode"], "tool")
            self.assertEqual(result["shell_composition"]["foreground_shell_region"], "interface-panel")
            self.assertFalse(result["shell_composition"]["inspector_collapsed"])
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "cts_gis_workbench")
            self.assertEqual(result["shell_composition"]["regions"]["inspector"]["kind"], "cts_gis_interface_panel")
            self.assertTrue(result["shell_composition"]["regions"]["inspector"]["primary_surface"])
            self.assertEqual(result["shell_composition"]["regions"]["inspector"]["layout_mode"], "dominant")
            self.assertEqual(
                result["shell_composition"]["regions"]["inspector"]["request_contract"]["route"],
                "/portal/api/v2/admin/cts-gis/read-only",
            )
            self.assertEqual(
                result["surface_payload"]["map_projection"]["projection_state"],
                "projectable",
            )
            self.assertGreater(result["surface_payload"]["map_projection"]["feature_count"], 0)
            self.assertEqual(result["surface_payload"]["attention_profile"]["node_id"], "3-2-3-17-77-1")
            self.assertEqual(result["surface_payload"]["mediation_state"]["intention_token"], "0")
            self.assertIn(
                "1-0",
                [item["token"] for item in result["surface_payload"]["mediation_state"]["available_intentions"]],
            )
            first_row = (result["surface_payload"]["rows"] or [])[0]
            self.assertNotIn("raw", first_row)
            self.assertNotIn("reference_bindings", first_row)
            self.assertIn("overlay_preview", first_row)
            self.assertIn("raw", result["surface_payload"]["selected_row"])

            children_result = run_admin_cts_gis_read_only(
                {
                    "schema": ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                    "mediation_state": {
                        "attention_node_id": "3-2-3-17-77-1",
                        "intention_token": "1-0",
                    },
                },
                data_dir=data_dir,
                portal_tenant_id="fnd",
                tool_exposure_policy=policy,
            )
            self.assertEqual(children_result["surface_payload"]["render_set_summary"]["render_mode"], "children")
            child_feature = children_result["surface_payload"]["map_projection"]["feature_collection"]["features"][0]
            self.assertEqual(child_feature["properties"]["samras_node_id"], "3-2-3-17-77-1-1")

            collapsed_result = run_admin_cts_gis_read_only(
                {
                    "schema": ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                    "shell_chrome": {"inspector_collapsed": True},
                },
                data_dir=data_dir,
                portal_tenant_id="fnd",
                tool_exposure_policy=policy,
            )
            self.assertEqual(collapsed_result["shell_composition"]["foreground_shell_region"], "center-workbench")
            self.assertTrue(collapsed_result["shell_composition"]["inspector_collapsed"])
            self.assertEqual(
                collapsed_result["shell_composition"]["regions"]["workbench"]["kind"],
                "tool_collapsed_inspector",
            )

    def test_cts_gis_read_only_returns_renderable_no_documents_surface(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            _write_minimal_data(data_dir)
            policy = build_admin_tool_exposure_policy(
                {"cts_gis": {"enabled": True}},
                known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis", "fnd_ebi"],
            )

            result = run_admin_cts_gis_read_only(
                {
                    "schema": ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
                data_dir=data_dir,
                portal_tenant_id="tff",
                tool_exposure_policy=policy,
            )

            self.assertIsNone(result["error"])
            self.assertEqual(
                result["surface_payload"]["map_projection"]["projection_state"],
                "no_authoritative_cts_gis_documents",
            )
            self.assertEqual(result["surface_payload"]["document_catalog"], [])

    def test_cts_gis_read_only_returns_tool_not_exposed_before_data_validation(self) -> None:
        policy = build_admin_tool_exposure_policy(
            {"cts_gis": {"enabled": False}},
            known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis", "fnd_ebi"],
        )

        result = run_admin_cts_gis_read_only(
            {
                "schema": ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
            data_dir=None,
            portal_tenant_id="tff",
            tool_exposure_policy=policy,
        )

        self.assertEqual(result["error"]["code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)
        self.assertEqual(result["shell_state"]["reason_code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)


if __name__ == "__main__":
    unittest.main()
