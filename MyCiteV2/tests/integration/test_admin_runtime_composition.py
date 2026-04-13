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
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    build_admin_tool_exposure_policy,
)
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND0_NAME,
    ADMIN_ENTRYPOINT_ID,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_NETWORK_ROOT_SLICE_ID,
    ADMIN_SHELL_COMPOSITION_SCHEMA,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_SLICE_ID,
    DATUM_RESOURCE_WORKBENCH_SLICE_ID,
    MAPS_READ_ONLY_SLICE_ID,
)


def _aws_csm_rollout_policy() -> dict[str, object]:
    return build_admin_tool_exposure_policy(
        {
            "aws": {"enabled": True},
            "aws_csm_newsletter": {"enabled": True},
            "aws_narrow_write": {"enabled": True},
            "aws_csm_onboarding": {"enabled": True},
            "aws_csm_sandbox": {"enabled": False},
        },
        known_tool_ids=["aws", "aws_csm_newsletter", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "maps"],
    )


def _aws_private_dir(temp_dir: str, profile_payload: dict[str, object]) -> Path:
    private_dir = Path(temp_dir) / "private"
    aws_root = private_dir / "utilities" / "tools" / "aws-csm"
    legacy_root = private_dir / "utilities" / "tools" / "newsletter-admin"
    aws_root.mkdir(parents=True, exist_ok=True)
    legacy_root.mkdir(parents=True, exist_ok=True)
    profile_id = ((profile_payload.get("identity") or {}) if isinstance(profile_payload.get("identity"), dict) else {}).get("profile_id")
    filename = f"{profile_id}.json" if profile_id else "aws-csm.test.profile.json"
    (aws_root / filename).write_text(json.dumps(profile_payload) + "\n", encoding="utf-8")
    domain = ((profile_payload.get("identity") or {}) if isinstance(profile_payload.get("identity"), dict) else {}).get("domain") or "trappfamilyfarm.com"
    (legacy_root / f"newsletter-admin.{domain}.json").write_text(
        json.dumps(
            {
                "schema": "mycite.service_tool.newsletter.profile.v1",
                "domain": domain,
                "list_address": f"news@{domain}",
                "sender_address": f"news@{domain}",
                "selected_author_profile_id": profile_id,
                "selected_author_address": ((profile_payload.get("identity") or {}) if isinstance(profile_payload.get("identity"), dict) else {}).get("send_as_email"),
                "dispatch_queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/aws-cms-newsletter-dispatch",
                "dispatch_queue_arn": "arn:aws:sqs:us-east-1:123456789012:aws-cms-newsletter-dispatch",
                "dispatcher_lambda_name": "newsletter-dispatcher",
                "aws_region": "us-east-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return private_dir


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
            self.assertEqual(
                available_slice_ids,
                [ADMIN_HOME_STATUS_SLICE_ID, ADMIN_NETWORK_ROOT_SLICE_ID, ADMIN_TOOL_REGISTRY_SLICE_ID],
            )

            available_tool_entries = result["surface_payload"]["available_tool_slices"]
            self.assertEqual(len(available_tool_entries), 2)
            self.assertEqual(
                [entry["slice_id"] for entry in available_tool_entries],
                [
                    AWS_READ_ONLY_SLICE_ID,
                    MAPS_READ_ONLY_SLICE_ID,
                ],
            )
            self.assertTrue(all(entry["launchable"] for entry in available_tool_entries))
            self.assertEqual(
                [entry["slice_id"] for entry in result["surface_payload"]["family_tool_slices"]],
                [AWS_NARROW_WRITE_SLICE_ID, AWS_CSM_SANDBOX_SLICE_ID, AWS_CSM_ONBOARDING_SLICE_ID],
            )
            self.assertEqual(
                [entry["slice_id"] for entry in result["surface_payload"]["gated_tool_slices"]],
                [],
            )
            comp = result["shell_composition"]
            self.assertEqual(comp["schema"], ADMIN_SHELL_COMPOSITION_SCHEMA)
            self.assertEqual(comp["active_service"], "system")
            self.assertIn("regions", comp)
            self.assertIn("activity_bar", comp["regions"])
            self.assertIn("control_panel", comp["regions"])
            self.assertIn("workbench", comp["regions"])
            self.assertIn("inspector", comp["regions"])
            self.assertTrue(comp["regions"]["activity_bar"]["items"])
            activity_items = comp["regions"]["activity_bar"]["items"]
            self.assertEqual(
                [item["nav_kind"] for item in activity_items[:4]],
                ["root_logo", "root_service", "root_service", "root_service"],
            )
            self.assertEqual(
                [item["icon_id"] for item in activity_items[:4]],
                ["fnd-logo", "network", "system", "utilities"],
            )

    def test_tool_exposure_filters_visible_tools_and_marks_registry_rows(self) -> None:
        result = run_admin_shell_entry(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
            tool_exposure_policy=_aws_csm_rollout_policy(),
        )

        available_tool_entries = result["surface_payload"]["available_tool_slices"]
        self.assertEqual(
            [entry["slice_id"] for entry in available_tool_entries],
            [AWS_READ_ONLY_SLICE_ID],
        )
        gated_tool_entries = result["surface_payload"]["gated_tool_slices"]
        self.assertEqual(
            [entry["slice_id"] for entry in gated_tool_entries],
            [AWS_CSM_SANDBOX_SLICE_ID, MAPS_READ_ONLY_SLICE_ID],
        )
        gated_by_slice = {entry["slice_id"]: entry for entry in gated_tool_entries}
        self.assertEqual(gated_by_slice[AWS_CSM_SANDBOX_SLICE_ID]["visibility_status"], "config_disabled")
        self.assertEqual(gated_by_slice[MAPS_READ_ONLY_SLICE_ID]["visibility_status"], "config_disabled")
        self.assertEqual(
            [entry["slice_id"] for entry in result["surface_payload"]["family_tool_slices"]],
            [AWS_NARROW_WRITE_SLICE_ID, AWS_CSM_ONBOARDING_SLICE_ID],
        )
        activity_slice_ids = [
            item["slice_id"] for item in result["shell_composition"]["regions"]["activity_bar"]["items"]
        ]
        self.assertNotIn(AWS_CSM_SANDBOX_SLICE_ID, activity_slice_ids)
        self.assertNotIn(AWS_CSM_ONBOARDING_SLICE_ID, activity_slice_ids)
        self.assertNotIn(MAPS_READ_ONLY_SLICE_ID, activity_slice_ids)
        self.assertIn(ADMIN_HOME_STATUS_SLICE_ID, activity_slice_ids)
        self.assertIn(ADMIN_NETWORK_ROOT_SLICE_ID, activity_slice_ids)
        self.assertIn(ADMIN_TOOL_REGISTRY_SLICE_ID, activity_slice_ids)

        registry = run_admin_shell_entry(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
            tool_exposure_policy=_aws_csm_rollout_policy(),
        )
        sandbox_row = [
            row for row in registry["surface_payload"]["tool_entries"] if row["slice_id"] == AWS_CSM_SANDBOX_SLICE_ID
        ][0]
        self.assertFalse(sandbox_row["config_enabled"])
        self.assertEqual(sandbox_row["visibility_status"], "config_disabled")

    def test_disabled_tool_request_falls_back_to_registry_with_tool_not_exposed(self) -> None:
        result = run_admin_shell_entry(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": AWS_CSM_SANDBOX_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
            tool_exposure_policy=_aws_csm_rollout_policy(),
        )

        self.assertEqual(result["slice_id"], ADMIN_TOOL_REGISTRY_SLICE_ID)
        self.assertEqual(result["error"]["code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)
        self.assertEqual(result["surface_payload"]["schema"], ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA)
        self.assertEqual(result["shell_composition"]["regions"]["workbench"].get("banner", {}).get("code"), ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)

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
                MAPS_READ_ONLY_SLICE_ID,
            ],
        )
        self.assertEqual(
            result["surface_payload"]["gated_tool_slice_ids"],
            [],
        )
        self.assertEqual(len(result["surface_payload"]["tool_entries"]), 5)
        self.assertNotIn("newsletter-admin", json.dumps(result["surface_payload"], sort_keys=True))
        self.assertEqual(result["shell_composition"]["composition_mode"], "system")
        self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "utilities_root")

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
                "message": "Admin tool slices launch through the shell-owned registry and their cataloged runtime entrypoints.",
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

    def test_datum_workbench_prefers_authoritative_sandbox_source_and_emits_diagnostics(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "maps" / "sources").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "sandbox" / "maps" / "tool.maps.json").write_text(
                json.dumps(
                    {
                        "3-1-2": [["3-1-2", "2-0-2", "0"], ["SAMRAS-babelette-msn_id"]],
                        "3-1-3": [["3-1-3", "2-1-1", "0"], ["title-babelette"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "maps" / "sources" / "sc.example.json").write_text(
                json.dumps(
                    {
                        "anchor_file_version": "<hash here>",
                        "datum_addressing_abstraction_space": {
                            "4-2-118": [
                                ["4-2-118", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", "HERE"],
                                ["summit_county_cities"],
                            ],
                            "4-2-120": [
                                ["4-2-120", "rf.3-1-2", "3-2-3-17-77-1-1", "rf.3-1-3", "HERE"],
                                ["akron_city"],
                            ],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": DATUM_RESOURCE_WORKBENCH_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
                data_dir=data_dir,
            )

            self.assertIsNone(result["error"])
            self.assertEqual(result["slice_id"], DATUM_RESOURCE_WORKBENCH_SLICE_ID)
            workbench = result["surface_payload"]["workbench"]
            self.assertEqual(workbench["selected_document"]["source_kind"], "sandbox_source")
            self.assertEqual(workbench["selected_document"]["document_name"], "sc.example.json")
            self.assertIn("illegal_magnitude_literal", workbench["rows"][0]["diagnostic_states"])
            self.assertIn("address_irregularity", workbench["rows"][1]["diagnostic_states"])
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "datum_workbench")
            self.assertEqual(result["shell_composition"]["regions"]["inspector"]["kind"], "datum_summary")

    def test_trusted_tenant_aws_read_only_slice_keeps_workbench_primary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_payload = {
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
            status_file = Path(temp_dir) / "aws.json"
            status_file.write_text(json.dumps(profile_payload), encoding="utf-8")
            private_dir = _aws_private_dir(temp_dir, profile_payload)
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
                private_dir=private_dir,
                tool_exposure_policy=_aws_csm_rollout_policy(),
            )
            self.assertIsNone(result["error"])
            self.assertEqual(result["slice_id"], AWS_READ_ONLY_SLICE_ID)
            self.assertEqual(result["shell_composition"]["composition_mode"], "tool")
            self.assertEqual(result["shell_composition"]["foreground_shell_region"], "center-workbench")
            self.assertTrue(result["shell_composition"]["inspector_collapsed"])
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "aws_csm_family_workbench")
            ins = result["shell_composition"]["regions"]["inspector"]
            self.assertEqual(ins["kind"], "aws_csm_family_home")
            self.assertEqual(ins["selected_domain_state"]["domain"], "trappfamilyfarm.com")

    def test_shell_chrome_can_open_interface_panel_without_hiding_workbench(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_payload = {
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
            status_file = Path(temp_dir) / "aws.json"
            status_file.write_text(json.dumps(profile_payload), encoding="utf-8")
            private_dir = _aws_private_dir(temp_dir, profile_payload)
            data_dir = Path(temp_dir) / "data"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text("{}\n", encoding="utf-8")

            dismissed = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": AWS_READ_ONLY_SLICE_ID,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                    "shell_chrome": {"inspector_collapsed": False},
                },
                portal_tenant_id="tff",
                aws_status_file=status_file,
                data_dir=data_dir,
                private_dir=private_dir,
                tool_exposure_policy=_aws_csm_rollout_policy(),
            )
            self.assertFalse(dismissed["shell_composition"]["inspector_collapsed"])
            self.assertEqual(dismissed["shell_composition"]["foreground_shell_region"], "center-workbench")
            wb = dismissed["shell_composition"]["regions"]["workbench"]
            self.assertEqual(wb.get("kind"), "aws_csm_family_workbench")


if __name__ == "__main__":
    unittest.main()
