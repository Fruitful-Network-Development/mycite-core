from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import run_portal_aws_csm
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis
from MyCiteV2.instances._shared.runtime.portal_fnd_dcm_runtime import run_portal_fnd_dcm
from MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime import run_portal_fnd_ebi
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import run_portal_workbench_ui
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    initial_portal_shell_state,
)


def _assert_region_family_contracts(
    testcase: unittest.TestCase,
    envelope: dict[str, object],
    *,
    expected_surface_id: str,
    expected_interface_body_kind: str | None = None,
) -> None:
    retired_compatibility_kinds = {
        "aws_csm_inspector",
        "network_system_log_inspector",
        "aws_csm_workspace",
        "cts_gis_interface_body",
        "tool_secondary_evidence",
        "state_directive_compact",
        "tool_mediation_panel",
    }
    composition = dict(envelope.get("shell_composition") or {})
    regions = dict(composition.get("regions") or {})
    control_panel = dict(regions.get("control_panel") or {})
    workbench = dict(regions.get("workbench") or {})
    interface_panel = dict(regions.get("interface_panel") or regions.get("inspector") or {})

    testcase.assertEqual(control_panel["family_contract"]["family"], "directive_panel")
    testcase.assertEqual(control_panel["family_contract"]["surface_id"], expected_surface_id)
    testcase.assertTrue(control_panel["family_contract"]["compatibility_kind"])
    testcase.assertNotIn(control_panel["family_contract"]["compatibility_kind"], retired_compatibility_kinds)

    testcase.assertEqual(workbench["family_contract"]["family"], "reflective_workspace")
    testcase.assertEqual(workbench["family_contract"]["surface_id"], expected_surface_id)
    testcase.assertTrue(workbench["family_contract"]["compatibility_kind"])
    testcase.assertNotIn(workbench["family_contract"]["compatibility_kind"], retired_compatibility_kinds)
    if isinstance(workbench.get("surface_payload"), dict):
        testcase.assertEqual(
            workbench["family_contract"]["surface_payload_kind"],
            str((workbench.get("surface_payload") or {}).get("kind") or ""),
        )
        testcase.assertNotIn(workbench["family_contract"]["surface_payload_kind"], retired_compatibility_kinds)

    testcase.assertEqual(interface_panel["family_contract"]["family"], "presentation_surface")
    testcase.assertEqual(interface_panel["family_contract"]["surface_id"], expected_surface_id)
    testcase.assertTrue(interface_panel["family_contract"]["compatibility_kind"])
    testcase.assertNotIn(interface_panel["family_contract"]["compatibility_kind"], retired_compatibility_kinds)
    if expected_interface_body_kind is not None:
        testcase.assertEqual(interface_panel["family_contract"]["interface_body_kind"], expected_interface_body_kind)
        testcase.assertNotIn(interface_panel["family_contract"]["interface_body_kind"], retired_compatibility_kinds)


class PortalRegionFamilyContractTests(unittest.TestCase):
    def test_root_shell_routes_emit_family_contract_markers(self) -> None:
        cases = (
            (SYSTEM_ROOT_SURFACE_ID, {}),
            (NETWORK_ROOT_SURFACE_ID, {}),
            (UTILITIES_ROOT_SURFACE_ID, {}),
        )
        for surface_id, extra_request in cases:
            with self.subTest(surface_id=surface_id):
                envelope = run_portal_shell_entry(
                    {
                        "schema": "mycite.v2.portal.shell.request.v1",
                        "requested_surface_id": surface_id,
                        "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection", "fnd_peripheral_routing"]},
                        **extra_request,
                    },
                    portal_instance_id="fnd",
                    portal_domain="fruitfulnetworkdevelopment.com",
                    data_dir=None,
                    public_dir=None,
                    private_dir=None,
                    audit_storage_file=None,
                    webapps_root=None,
                    authority_db_file=None,
                    tool_exposure_policy=None,
                )
                _assert_region_family_contracts(self, envelope, expected_surface_id=surface_id)

    def test_tool_routes_emit_family_contract_markers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            webapps_root = Path(temp_dir) / "webapps"
            webapps_root.mkdir(parents=True, exist_ok=True)

            aws_envelope = run_portal_aws_csm(
                {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
                private_dir=None,
                tool_exposure_policy=None,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            _assert_region_family_contracts(self, aws_envelope, expected_surface_id="system.tools.aws_csm")

            cts_envelope = run_portal_cts_gis(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "shell_state": initial_portal_shell_state(
                        surface_id=CTS_GIS_TOOL_SURFACE_ID,
                        portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    ).to_dict(),
                },
                data_dir=None,
                private_dir=None,
                tool_exposure_policy=None,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            _assert_region_family_contracts(
                self,
                cts_envelope,
                expected_surface_id=CTS_GIS_TOOL_SURFACE_ID,
                expected_interface_body_kind="",
            )

            fnd_dcm_envelope = run_portal_fnd_dcm(
                {
                    "schema": "mycite.v2.portal.system.tools.fnd_dcm.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                },
                webapps_root=Path(temp_dir) / "missing-webapps",
                private_dir=None,
                tool_exposure_policy=None,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            _assert_region_family_contracts(self, fnd_dcm_envelope, expected_surface_id="system.tools.fnd_dcm")

            fnd_ebi_envelope = run_portal_fnd_ebi(
                {
                    "schema": "mycite.v2.portal.system.tools.fnd_ebi.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "shell_state": initial_portal_shell_state(
                        surface_id=FND_EBI_TOOL_SURFACE_ID,
                        portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    ).to_dict(),
                },
                webapps_root=webapps_root,
                private_dir=None,
                tool_exposure_policy=None,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            _assert_region_family_contracts(self, fnd_ebi_envelope, expected_surface_id=FND_EBI_TOOL_SURFACE_ID)

            workbench_ui_envelope = run_portal_workbench_ui(
                {
                    "schema": "mycite.v2.portal.system.tools.workbench_ui.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": []},
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                authority_db_file=None,
            )
            _assert_region_family_contracts(self, workbench_ui_envelope, expected_surface_id="system.tools.workbench_ui")


if __name__ == "__main__":
    unittest.main()
