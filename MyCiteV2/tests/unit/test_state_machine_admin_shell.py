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
    ADMIN_BAND2_AWS_NAME,
    ADMIN_BAND3_AWS_SANDBOX_NAME,
    ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
    ADMIN_BAND5_MAPS_NAME,
    ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
    ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_ENTRY_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_DESCRIPTOR_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_SLICE_ID,
    MAPS_READ_ONLY_ENTRYPOINT_ID,
    MAPS_READ_ONLY_SLICE_ID,
    AdminShellRequest,
    AdminTenantScope,
    build_admin_surface_catalog,
    build_admin_tool_registry_entries,
    resolve_admin_tool_launch,
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

    def test_tool_registry_surface_is_available_and_aws_redirects_to_registry(self) -> None:
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
        self.assertEqual(aws_selection.active_surface_id, ADMIN_TOOL_REGISTRY_SLICE_ID)
        self.assertEqual(aws_selection.selection_status, "gated")
        self.assertEqual(aws_selection.reason_code, "launch_via_registry")
        self.assertIn("registry", aws_selection.reason_message)

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

    def test_catalog_and_registry_are_serializable_and_shell_owned(self) -> None:
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
                    "schema": ADMIN_TOOL_DESCRIPTOR_SCHEMA,
                    "tool_id": "aws",
                    "label": "AWS-CSM",
                    "slice_id": AWS_READ_ONLY_SLICE_ID,
                    "entrypoint_id": AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
                    "admin_band": ADMIN_BAND1_AWS_NAME,
                    "exposure_status": "implemented_trusted_tenant_read_only",
                    "read_write_posture": "read-only",
                    "surface_pattern": "read-only",
                    "status_summary": "launchable_family_home",
                    "audience": "trusted-tenant-admin",
                    "internal_only_reason": "",
                    "audit_required": False,
                    "read_after_write_required": False,
                    "discovery_mode": "catalog-driven",
                    "launch_contract": "shell-owned-registry",
                    "default_posture": "deny-by-default",
                    "launchable": True,
                    "activity_bar_visible": True,
                },
                {
                    "schema": ADMIN_TOOL_DESCRIPTOR_SCHEMA,
                    "tool_id": "aws_narrow_write",
                    "label": "AWS-CSM Sender Selection",
                    "slice_id": AWS_NARROW_WRITE_SLICE_ID,
                    "entrypoint_id": AWS_NARROW_WRITE_ENTRYPOINT_ID,
                    "admin_band": ADMIN_BAND2_AWS_NAME,
                    "exposure_status": "implemented_trusted_tenant_narrow_write",
                    "read_write_posture": "write",
                    "surface_pattern": "bounded-write",
                    "status_summary": "launchable_narrow_write",
                    "audience": "trusted-tenant-admin",
                    "internal_only_reason": "",
                    "audit_required": True,
                    "read_after_write_required": True,
                    "discovery_mode": "catalog-driven",
                    "launch_contract": "shell-owned-registry",
                    "default_posture": "deny-by-default",
                    "launchable": True,
                    "activity_bar_visible": False,
                },
                {
                    "schema": ADMIN_TOOL_DESCRIPTOR_SCHEMA,
                    "tool_id": "aws_csm_sandbox",
                    "label": "AWS-CSM Sandbox (read-only)",
                    "slice_id": AWS_CSM_SANDBOX_SLICE_ID,
                    "entrypoint_id": AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
                    "admin_band": ADMIN_BAND3_AWS_SANDBOX_NAME,
                    "exposure_status": "implemented_internal_sandbox_read_only",
                    "read_write_posture": "read-only",
                    "surface_pattern": "read-only",
                    "status_summary": "launchable_sandbox_read_only",
                    "audience": "internal-admin",
                    "internal_only_reason": "",
                    "audit_required": False,
                    "read_after_write_required": False,
                    "discovery_mode": "catalog-driven",
                    "launch_contract": "shell-owned-registry",
                    "default_posture": "deny-by-default",
                    "launchable": True,
                    "activity_bar_visible": False,
                },
                {
                    "schema": ADMIN_TOOL_DESCRIPTOR_SCHEMA,
                    "tool_id": "aws_csm_onboarding",
                    "label": "AWS-CSM Mailbox Onboarding",
                    "slice_id": AWS_CSM_ONBOARDING_SLICE_ID,
                    "entrypoint_id": AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
                    "admin_band": ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
                    "exposure_status": "implemented_trusted_tenant_csm_onboarding",
                    "read_write_posture": "write",
                    "surface_pattern": "bounded-write",
                    "status_summary": "launchable_bounded_onboarding",
                    "audience": "trusted-tenant-admin",
                    "internal_only_reason": "",
                    "audit_required": True,
                    "read_after_write_required": True,
                    "discovery_mode": "catalog-driven",
                    "launch_contract": "shell-owned-registry",
                    "default_posture": "deny-by-default",
                    "launchable": True,
                    "activity_bar_visible": False,
                },
                {
                    "schema": ADMIN_TOOL_DESCRIPTOR_SCHEMA,
                    "tool_id": "maps",
                    "label": "Maps",
                    "slice_id": MAPS_READ_ONLY_SLICE_ID,
                    "entrypoint_id": MAPS_READ_ONLY_ENTRYPOINT_ID,
                    "admin_band": ADMIN_BAND5_MAPS_NAME,
                    "exposure_status": "implemented_internal_maps_read_only",
                    "read_write_posture": "read-only",
                    "surface_pattern": "read-only",
                    "status_summary": "launchable_maps_read_only",
                    "audience": "internal-admin",
                    "internal_only_reason": "",
                    "audit_required": False,
                    "read_after_write_required": False,
                    "discovery_mode": "catalog-driven",
                    "launch_contract": "shell-owned-registry",
                    "default_posture": "deny-by-default",
                    "launchable": True,
                    "activity_bar_visible": True,
                },
            ],
        )
        self.assertNotIn("newsletter-admin", json.dumps(tool_entries, sort_keys=True))

    def test_launch_decision_is_shell_owned_and_approved_for_trusted_tenant(self) -> None:
        allowed = resolve_admin_tool_launch(
            slice_id=AWS_READ_ONLY_SLICE_ID,
            audience="trusted-tenant",
            expected_entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
        )
        mismatch = resolve_admin_tool_launch(
            slice_id=AWS_READ_ONLY_SLICE_ID,
            audience="trusted-tenant",
            expected_entrypoint_id="admin.aws.other",
        )
        write_allowed = resolve_admin_tool_launch(
            slice_id=AWS_NARROW_WRITE_SLICE_ID,
            audience="trusted-tenant",
            expected_entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
        )

        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.selection_status, "available")
        self.assertEqual(allowed.exposure_status, "implemented_trusted_tenant_read_only")
        self.assertEqual(
            json.loads(json.dumps(allowed.to_dict(), sort_keys=True)),
            {
                "schema": "mycite.v2.admin.shell.state.v1",
                "slice_id": AWS_READ_ONLY_SLICE_ID,
                "entrypoint_id": AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
                "allowed": True,
                "selection_status": "available",
                "reason_code": "",
                "reason_message": "",
                "exposure_status": "implemented_trusted_tenant_read_only",
            },
        )
        self.assertFalse(mismatch.allowed)
        self.assertEqual(mismatch.reason_code, "catalog_mismatch")
        self.assertTrue(write_allowed.allowed)
        self.assertEqual(write_allowed.entrypoint_id, AWS_NARROW_WRITE_ENTRYPOINT_ID)
        self.assertEqual(write_allowed.exposure_status, "implemented_trusted_tenant_narrow_write")

        onboarding_allowed = resolve_admin_tool_launch(
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            audience="trusted-tenant",
            expected_entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
        )
        self.assertTrue(onboarding_allowed.allowed)
        self.assertEqual(onboarding_allowed.entrypoint_id, AWS_CSM_ONBOARDING_ENTRYPOINT_ID)

        maps_allowed = resolve_admin_tool_launch(
            slice_id=MAPS_READ_ONLY_SLICE_ID,
            audience="internal",
            expected_entrypoint_id=MAPS_READ_ONLY_ENTRYPOINT_ID,
        )
        self.assertTrue(maps_allowed.allowed)
        self.assertEqual(maps_allowed.entrypoint_id, MAPS_READ_ONLY_ENTRYPOINT_ID)

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

    def test_shell_chrome_round_trips_in_request_dict(self) -> None:
        payload = {
            "schema": ADMIN_SHELL_REQUEST_SCHEMA,
            "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
            "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            "shell_chrome": {"inspector_collapsed": True, "control_panel_collapsed": False},
        }
        req = AdminShellRequest.from_dict(payload)
        self.assertTrue(req.shell_chrome.inspector_collapsed)
        self.assertFalse(req.shell_chrome.control_panel_collapsed)
        self.assertEqual(req.to_dict()["shell_chrome"], payload["shell_chrome"])

    def test_band_name_is_fixed_for_admin_band0(self) -> None:
        self.assertEqual(ADMIN_BAND0_NAME, "Admin Band 0 Internal Admin Replacement")
        self.assertEqual(ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY, "trusted-tenant-read-only")
        self.assertEqual(ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE, "trusted-tenant-narrow-write")


if __name__ == "__main__":
    unittest.main()
