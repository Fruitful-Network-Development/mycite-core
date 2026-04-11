from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.admin_runtime import (
    ADMIN_HOME_STATUS_SURFACE_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA,
    run_admin_shell_entry,
)
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND0_NAME,
    ADMIN_ENTRYPOINT_ID,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_COMPOSITION_SCHEMA,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_SLICE_ID,
)


class AdminRuntimeCompositionTests(unittest.TestCase):
    def test_default_admin_shell_entry_returns_internal_home_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            audit_storage_file = Path(temp_dir) / "local_audit.ndjson"

            result = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
                audit_storage_file=audit_storage_file,
            )

            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["admin_band"], ADMIN_BAND0_NAME)
            self.assertEqual(result["exposure_status"], "internal-only")
            self.assertEqual(result["entrypoint_id"], ADMIN_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], ADMIN_HOME_STATUS_SLICE_ID)
            self.assertEqual(result["requested_slice_id"], ADMIN_HOME_STATUS_SLICE_ID)
            self.assertEqual(result["read_write_posture"], "read-only")
            self.assertEqual(result["tenant_scope"], {"scope_id": "internal-admin", "audience": "internal"})
            self.assertIsNone(result["error"])
            self.assertEqual(result["warnings"], [])
            self.assertEqual(result["surface_payload"]["schema"], ADMIN_HOME_STATUS_SURFACE_SCHEMA)
            self.assertEqual(result["surface_payload"]["active_surface_id"], ADMIN_HOME_STATUS_SLICE_ID)
            self.assertEqual(result["surface_payload"]["current_admin_band"], ADMIN_BAND0_NAME)
            self.assertEqual(
                result["surface_payload"]["runtime_health"]["audit_log"],
                {
                    "status": "configured",
                    "record_readback": "ok",
                    "storage_state": "missing_or_empty",
                },
            )
            self.assertFalse(audit_storage_file.exists())

            available_slice_ids = [entry["slice_id"] for entry in result["surface_payload"]["available_admin_slices"]]
            self.assertEqual(available_slice_ids, [ADMIN_HOME_STATUS_SLICE_ID, ADMIN_TOOL_REGISTRY_SLICE_ID])

            available_tool_entries = result["surface_payload"]["available_tool_slices"]
            self.assertEqual(len(available_tool_entries), 4)
            self.assertEqual(
                [entry["slice_id"] for entry in available_tool_entries],
                [
                    AWS_READ_ONLY_SLICE_ID,
                    AWS_NARROW_WRITE_SLICE_ID,
                    AWS_CSM_SANDBOX_SLICE_ID,
                    AWS_CSM_ONBOARDING_SLICE_ID,
                ],
            )
            self.assertTrue(all(entry["launchable"] for entry in available_tool_entries))
            self.assertEqual(result["surface_payload"]["gated_tool_slices"], [])
            comp = result["shell_composition"]
            self.assertEqual(comp["schema"], ADMIN_SHELL_COMPOSITION_SCHEMA)
            self.assertIn("regions", comp)
            self.assertIn("activity_bar", comp["regions"])
            self.assertIn("control_panel", comp["regions"])
            self.assertIn("workbench", comp["regions"])
            self.assertIn("inspector", comp["regions"])
            self.assertTrue(comp["regions"]["activity_bar"]["items"])

    def test_tool_registry_surface_is_catalog_driven_and_deny_by_default(self) -> None:
        result = run_admin_shell_entry(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            }
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["slice_id"], ADMIN_TOOL_REGISTRY_SLICE_ID)
        self.assertEqual(result["surface_payload"]["schema"], ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA)
        self.assertEqual(result["surface_payload"]["registry_owner"], "shell")
        self.assertEqual(result["surface_payload"]["default_posture"], "deny-by-default")
        self.assertEqual(
            result["surface_payload"]["launchable_tool_slice_ids"],
            [
                AWS_READ_ONLY_SLICE_ID,
                AWS_NARROW_WRITE_SLICE_ID,
                AWS_CSM_SANDBOX_SLICE_ID,
                AWS_CSM_ONBOARDING_SLICE_ID,
            ],
        )
        self.assertEqual(result["surface_payload"]["gated_tool_slice_ids"], [])
        self.assertEqual(len(result["surface_payload"]["tool_entries"]), 4)
        self.assertNotIn("newsletter-admin", json.dumps(result["surface_payload"], sort_keys=True))
        self.assertEqual(result["shell_composition"]["composition_mode"], "system")
        self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "tool_registry")

    def test_requested_aws_slice_redirects_to_registry_and_does_not_launch_inline(self) -> None:
        result = run_admin_shell_entry(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            }
        )

        self.assertEqual(result["slice_id"], ADMIN_TOOL_REGISTRY_SLICE_ID)
        self.assertEqual(result["requested_slice_id"], AWS_READ_ONLY_SLICE_ID)
        self.assertEqual(
            result["error"],
            {
                "code": "launch_via_registry",
                "message": "AWS tool slices launch through the shell-owned registry and their cataloged runtime entrypoints.",
            },
        )
        self.assertEqual(result["warnings"], [result["error"]["message"]])
        self.assertEqual(result["surface_payload"]["schema"], ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA)
        self.assertEqual(result["shell_composition"]["regions"]["workbench"].get("banner", {}).get("code"), "launch_via_registry")

    def test_non_internal_request_is_denied_without_surface_payload(self) -> None:
        result = run_admin_shell_entry(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
            }
        )

        self.assertEqual(result["slice_id"], ADMIN_HOME_STATUS_SLICE_ID)
        self.assertEqual(result["error"]["code"], "audience_not_allowed")
        self.assertIn("Trusted-tenant shell requests", result["error"]["message"])
        self.assertIsNone(result["surface_payload"])
        self.assertIsNotNone(result["shell_composition"])

    def test_trusted_tenant_aws_read_only_slice_composes_tool_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "aws.json"
            status_file.write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.tff.x",
                            "tenant_id": "tff",
                            "domain": "trappfamilyfarm.com",
                            "mailbox_local_part": "x",
                            "send_as_email": "x@trappfamilyfarm.com",
                        },
                        "smtp": {"handoff_ready": True, "credentials_secret_state": "configured"},
                        "verification": {"status": "verified"},
                        "provider": {"gmail_send_as_status": "verified"},
                        "workflow": {
                            "initiated": True,
                            "lifecycle_state": "operational",
                            "is_ready_for_user_handoff": True,
                            "is_mailbox_operational": True,
                        },
                        "inbound": {"receive_verified": True, "receive_state": "receive_operational"},
                    }
                ),
                encoding="utf-8",
            )
            data_dir = Path(temp_dir) / "data"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text("{}\n", encoding="utf-8")

            result = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                },
                portal_tenant_id="tff",
                aws_status_file=status_file,
                data_dir=data_dir,
            )
            self.assertIsNone(result["error"])
            self.assertEqual(result["slice_id"], AWS_READ_ONLY_SLICE_ID)
            self.assertEqual(result["shell_composition"]["composition_mode"], "tool")
            self.assertEqual(result["shell_composition"]["foreground_shell_region"], "interface-panel")
            self.assertFalse(result["shell_composition"]["inspector_collapsed"])
            ins = result["shell_composition"]["regions"]["inspector"]
            self.assertEqual(ins["kind"], "aws_read_only_surface")
            self.assertEqual(ins["tenant_scope_id"], "tff")

    def test_shell_chrome_mediates_inspector_collapse_in_tool_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "aws.json"
            status_file.write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.tff.x",
                            "tenant_id": "tff",
                            "domain": "trappfamilyfarm.com",
                            "mailbox_local_part": "x",
                            "send_as_email": "x@trappfamilyfarm.com",
                        },
                        "smtp": {"handoff_ready": True, "credentials_secret_state": "configured"},
                        "verification": {"status": "verified"},
                        "provider": {"gmail_send_as_status": "verified"},
                        "workflow": {
                            "initiated": True,
                            "lifecycle_state": "operational",
                            "is_ready_for_user_handoff": True,
                            "is_mailbox_operational": True,
                        },
                        "inbound": {"receive_verified": True, "receive_state": "receive_operational"},
                    }
                ),
                encoding="utf-8",
            )
            data_dir = Path(temp_dir) / "data"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text("{}\n", encoding="utf-8")

            dismissed = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                    "shell_chrome": {"inspector_collapsed": True},
                },
                portal_tenant_id="tff",
                aws_status_file=status_file,
                data_dir=data_dir,
            )
            self.assertTrue(dismissed["shell_composition"]["inspector_collapsed"])
            self.assertEqual(dismissed["shell_composition"]["foreground_shell_region"], "center-workbench")
            wb = dismissed["shell_composition"]["regions"]["workbench"]
            self.assertEqual(wb.get("kind"), "tool_collapsed_inspector")


if __name__ == "__main__":
    unittest.main()
