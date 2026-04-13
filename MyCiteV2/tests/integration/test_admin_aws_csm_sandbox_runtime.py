from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
    run_admin_aws_csm_sandbox_read_only,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    build_admin_tool_exposure_policy,
)
from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
    build_admin_tool_registry_entries,
    resolve_admin_tool_launch,
)


def _live_profile_fnd() -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.fnd.sandbox",
            "tenant_id": "fnd",
            "domain": "fruitfulnetworkdevelopment.com",
            "mailbox_local_part": "technicalcontact",
            "send_as_email": "technicalcontact@fruitfulnetworkdevelopment.com",
        },
        "smtp": {
            "handoff_ready": True,
            "credentials_secret_state": "configured",
            "send_as_email": "technicalcontact@fruitfulnetworkdevelopment.com",
            "local_part": "technicalcontact",
        },
        "verification": {"status": "verified", "portal_state": "verified"},
        "provider": {"gmail_send_as_status": "verified"},
        "workflow": {
            "initiated": True,
            "lifecycle_state": "operational",
            "is_ready_for_user_handoff": True,
            "is_mailbox_operational": True,
        },
        "inbound": {
            "receive_verified": True,
            "portal_native_display_ready": True,
            "receive_state": "receive_operational",
            "latest_message_id": "message-1",
        },
    }


class AdminAwsCsmSandboxRuntimeIntegrationTests(unittest.TestCase):
    def test_registry_includes_distinct_sandbox_descriptor(self) -> None:
        entries = list(build_admin_tool_registry_entries())
        self.assertEqual(len(entries), 5)
        ids = [e.tool_id for e in entries]
        self.assertEqual(ids, ["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis"])
        sandbox = entries[2]
        self.assertEqual(sandbox.slice_id, AWS_CSM_SANDBOX_SLICE_ID)
        self.assertEqual(sandbox.entrypoint_id, AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID)
        self.assertEqual(sandbox.audience, "internal-admin")

    def test_trusted_tenant_cannot_launch_sandbox_slice(self) -> None:
        decision = resolve_admin_tool_launch(
            slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            audience="trusted-tenant",
            expected_entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "audience_not_allowed")

    def test_internal_cannot_launch_production_read_only_via_registry_launch(self) -> None:
        decision = resolve_admin_tool_launch(
            slice_id=AWS_READ_ONLY_SLICE_ID,
            audience="internal",
            expected_entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
        )
        self.assertFalse(decision.allowed)

    def test_sandbox_read_only_happy_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile = Path(temp_dir) / "sandbox-aws.json"
            profile.write_text(json.dumps(_live_profile_fnd()) + "\n", encoding="utf-8")
            result = run_admin_aws_csm_sandbox_read_only(
                {
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "fnd", "audience": "internal"},
                },
                aws_sandbox_status_file=profile,
            )
            self.assertIsNone(result.get("error"))
            self.assertEqual(result["slice_id"], AWS_CSM_SANDBOX_SLICE_ID)
            self.assertEqual(result["entrypoint_id"], AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID)
            sp = result.get("surface_payload")
            assert isinstance(sp, dict)
            self.assertEqual(sp["schema"], ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA)
            self.assertEqual(sp["active_surface_id"], AWS_CSM_SANDBOX_SLICE_ID)

    def test_shell_entry_allows_internal_sandbox_surface(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile = Path(temp_dir) / "sandbox-aws.json"
            profile.write_text(json.dumps(_live_profile_fnd()) + "\n", encoding="utf-8")
            result = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": AWS_CSM_SANDBOX_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                },
                portal_tenant_id="fnd",
                aws_csm_sandbox_status_file=profile,
            )
            self.assertIsNone(result.get("error"))
            self.assertEqual(result["slice_id"], AWS_CSM_SANDBOX_SLICE_ID)
            comp = result.get("shell_composition")
            assert isinstance(comp, dict)
            self.assertEqual(comp.get("composition_mode"), "tool")
            self.assertEqual(comp.get("active_tool_slice_id"), AWS_CSM_SANDBOX_SLICE_ID)

    def test_disabled_sandbox_returns_tool_not_exposed_before_path_validation(self) -> None:
        policy = build_admin_tool_exposure_policy(
            {"aws_csm_sandbox": {"enabled": False}},
            known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis"],
        )

        result = run_admin_aws_csm_sandbox_read_only(
            {
                "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "fnd", "audience": "internal"},
            },
            aws_sandbox_status_file=None,
            tool_exposure_policy=policy,
        )

        self.assertIsNotNone(result.get("error"))
        self.assertEqual(result["error"]["code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)
        self.assertEqual(result["shell_state"]["reason_code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)

    def test_production_read_only_unchanged_for_trusted_tenant(self) -> None:
        with TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "aws_status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "tenant_scope_id": "tenant-a",
                        "mailbox_readiness": "ready",
                        "smtp_state": "smtp_ready",
                        "gmail_state": "gmail_pending",
                        "verified_evidence_state": "sender_selected",
                        "selected_verified_sender": "alerts@example.com",
                        "canonical_newsletter_profile": {
                            "profile_id": "newsletter.example.com",
                            "domain": "example.com",
                            "list_address": "news@example.com",
                            "selected_verified_sender": "alerts@example.com",
                            "delivery_mode": "inbound-mail-only",
                        },
                        "compatibility": {"canonical_profile_matches_compatibility_inputs": False},
                        "inbound_capture": {"status": "ready"},
                        "dispatch_health": {"status": "healthy"},
                    }
                ),
                encoding="utf-8",
            )
            result = run_admin_aws_read_only(
                {
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                },
                aws_status_file=status_file,
            )
            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], AWS_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], AWS_READ_ONLY_SLICE_ID)

    def test_registry_surface_lists_all_catalog_tools(self) -> None:
        result = run_admin_shell_entry(
            {
                "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                "requested_slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            }
        )
        self.assertEqual(len(result["surface_payload"]["tool_entries"]), 5)


if __name__ == "__main__":
    unittest.main()
