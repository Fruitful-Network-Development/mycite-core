from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND0_NAME,
    ADMIN_BAND1_AWS_NAME,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_ENTRY_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_READ_ONLY_SLICE_ID,
    AdminShellRequest,
    AdminTenantScope,
    build_admin_surface_catalog,
    build_admin_tool_registry_entries,
    resolve_admin_shell_request,
)


class AdminShellStateMachineUnitTests(unittest.TestCase):
    def test_request_defaults_to_internal_home_status(self) -> None:
        request = AdminShellRequest()

        self.assertEqual(
            request.to_dict(),
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                "tenant_scope": {
                    "scope_id": "internal-admin",
                    "audience": "internal",
                },
            },
        )

    def test_shell_entry_alias_resolves_to_home_status(self) -> None:
        selection = resolve_admin_shell_request(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_SHELL_ENTRY_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            }
        )

        self.assertTrue(selection.allowed)
        self.assertEqual(selection.active_surface_id, ADMIN_HOME_STATUS_SLICE_ID)
        self.assertEqual(selection.selection_status, "available")

    def test_tool_registry_surface_is_available_but_aws_is_gated(self) -> None:
        tool_registry_selection = resolve_admin_shell_request(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            }
        )
        aws_selection = resolve_admin_shell_request(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            }
        )

        self.assertTrue(tool_registry_selection.allowed)
        self.assertEqual(tool_registry_selection.active_surface_id, ADMIN_TOOL_REGISTRY_SLICE_ID)

        self.assertFalse(aws_selection.allowed)
        self.assertEqual(aws_selection.active_surface_id, ADMIN_HOME_STATUS_SLICE_ID)
        self.assertEqual(aws_selection.selection_status, "gated")
        self.assertEqual(aws_selection.reason_code, "slice_gated")
        self.assertIn("Admin Band 0", aws_selection.reason_message)

    def test_non_internal_audience_is_denied_for_admin_band0(self) -> None:
        selection = resolve_admin_shell_request(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
            }
        )

        self.assertFalse(selection.allowed)
        self.assertEqual(selection.selection_status, "audience_denied")
        self.assertEqual(selection.reason_code, "audience_not_allowed")

    def test_catalog_and_registry_are_serializable_and_deny_by_default(self) -> None:
        surface_catalog = [entry.to_dict() for entry in build_admin_surface_catalog()]
        tool_entries = [entry.to_dict() for entry in build_admin_tool_registry_entries()]

        self.assertEqual(
            json.loads(json.dumps(surface_catalog, sort_keys=True)),
            surface_catalog,
        )
        self.assertEqual(
            json.loads(json.dumps(tool_entries, sort_keys=True)),
            tool_entries,
        )
        self.assertEqual(
            surface_catalog,
            [
                {
                    "slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                    "label": "Admin Home and Status",
                    "exposure_status": "implemented_internal",
                    "read_write_posture": "read-only",
                    "status_summary": "default_landing",
                    "surface_kind": "home_status",
                    "launchable": True,
                    "default_surface": True,
                },
                {
                    "slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                    "label": "Tool Registry and Launcher",
                    "exposure_status": "implemented_internal",
                    "read_write_posture": "read-only",
                    "status_summary": "registry_ready",
                    "surface_kind": "tool_registry",
                    "launchable": True,
                    "default_surface": False,
                },
            ],
        )
        self.assertEqual(
            tool_entries,
            [
                {
                    "tool_id": "aws",
                    "label": "AWS Admin",
                    "slice_id": AWS_READ_ONLY_SLICE_ID,
                    "entrypoint_id": "admin.aws.read_only",
                    "admin_band": ADMIN_BAND1_AWS_NAME,
                    "exposure_status": "planned_not_approved_for_build",
                    "read_write_posture": "read-only",
                    "status_summary": "planned_next",
                    "audience": "trusted-tenant-admin",
                    "internal_only_reason": "Admin Band 0 must remain stable before the AWS read-only slice can launch.",
                    "launchable": False,
                }
            ],
        )
        self.assertNotIn("newsletter-admin", json.dumps(tool_entries, sort_keys=True))

    def test_request_contract_rejects_invalid_schema_and_audience(self) -> None:
        with self.assertRaisesRegex(ValueError, "admin_shell_request.schema"):
            AdminShellRequest.from_dict(
                {
                    "schema": "wrong.schema",
                    "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                }
            )

        with self.assertRaisesRegex(ValueError, "admin_tenant_scope.audience"):
            AdminTenantScope.from_value({"scope_id": "internal-admin", "audience": "partner"})

    def test_band_name_is_fixed_for_admin_band0(self) -> None:
        self.assertEqual(ADMIN_BAND0_NAME, "Admin Band 0 Internal Admin Replacement")


if __name__ == "__main__":
    unittest.main()
