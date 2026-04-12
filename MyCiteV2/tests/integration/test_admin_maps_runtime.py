from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.admin_maps_runtime import run_admin_maps_read_only
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    build_admin_tool_exposure_policy,
)
from MyCiteV2.packages.state_machine.hanus_shell import MAPS_READ_ONLY_ENTRYPOINT_ID, MAPS_READ_ONLY_SLICE_ID


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
                        ["4-2-1", "rf.3-1-1", "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73"],
                        ["point_alpha"],
                    ],
                    "4-2-2": [
                        ["4-2-2", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", "0111001101110101011011010110110101101001"],
                        ["named_area"],
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


class AdminMapsRuntimeIntegrationTests(unittest.TestCase):
    def test_maps_read_only_returns_projectable_surface_when_enabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            _write_minimal_data(data_dir)
            _write_maps_data(data_dir)
            policy = build_admin_tool_exposure_policy(
                {"maps": {"enabled": True}},
                known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "maps"],
            )

            result = run_admin_maps_read_only(
                {
                    "schema": ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
                data_dir=data_dir,
                portal_tenant_id="fnd",
                tool_exposure_policy=policy,
            )

            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], MAPS_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], MAPS_READ_ONLY_SLICE_ID)
            self.assertIsNone(result["error"])
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "maps_workbench")
            self.assertEqual(
                result["surface_payload"]["map_projection"]["projection_state"],
                "projectable",
            )
            self.assertGreater(result["surface_payload"]["map_projection"]["feature_count"], 0)

    def test_maps_read_only_returns_renderable_no_documents_surface(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            _write_minimal_data(data_dir)
            policy = build_admin_tool_exposure_policy(
                {"maps": {"enabled": True}},
                known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "maps"],
            )

            result = run_admin_maps_read_only(
                {
                    "schema": ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
                data_dir=data_dir,
                portal_tenant_id="tff",
                tool_exposure_policy=policy,
            )

            self.assertIsNone(result["error"])
            self.assertEqual(
                result["surface_payload"]["map_projection"]["projection_state"],
                "no_authoritative_maps_documents",
            )
            self.assertEqual(result["surface_payload"]["document_catalog"], [])

    def test_maps_read_only_returns_tool_not_exposed_before_data_validation(self) -> None:
        policy = build_admin_tool_exposure_policy(
            {"maps": {"enabled": False}},
            known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "maps"],
        )

        result = run_admin_maps_read_only(
            {
                "schema": ADMIN_MAPS_READ_ONLY_REQUEST_SCHEMA,
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
