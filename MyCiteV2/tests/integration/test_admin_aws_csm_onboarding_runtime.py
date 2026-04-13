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
    run_admin_aws_csm_onboarding,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA,
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    build_admin_tool_exposure_policy,
)
from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingCloudPort
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    build_admin_tool_registry_entries,
    resolve_admin_tool_launch,
)

FOCUS_SUBJECT = "3-2-3-17-77-1-6-4-1-4.4-1-77"


def _live_profile_tenant_a(*, initiated: bool = False) -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "newsletter.example.com",
            "tenant_id": "tenant-a",
            "domain": "example.com",
            "mailbox_local_part": "news",
            "send_as_email": "news@example.com",
        },
        "smtp": {
            "handoff_ready": False,
            "credentials_secret_state": "pending",
            "send_as_email": "news@example.com",
            "local_part": "news",
        },
        "verification": {"status": "pending", "portal_state": "pending"},
        "provider": {"gmail_send_as_status": "pending"},
        "workflow": {"initiated": initiated},
        "inbound": {},
    }


class _FakeOnboardingCloud(AwsCsmOnboardingCloudPort):
    def __init__(self, *, evidence_ok: bool = False) -> None:
        self._evidence_ok = evidence_ok

    def supplemental_profile_patch(self, action: str, profile: dict[str, object]) -> dict[str, object]:
        _ = profile
        if action == "stage_smtp_credentials":
            return {
                "smtp": {
                    "handoff_ready": True,
                    "credentials_secret_state": "configured",
                    "staging_state": "material_ready",
                }
            }
        return {}

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, object]) -> bool:
        _ = profile
        return self._evidence_ok


class AdminAwsCsmOnboardingRuntimeIntegrationTests(unittest.TestCase):
    def test_registry_includes_onboarding_tool_for_trusted_tenant(self) -> None:
        entries = list(build_admin_tool_registry_entries())
        self.assertEqual(len(entries), 5)
        onboarding = [e for e in entries if e.tool_id == "aws_csm_onboarding"][0]
        self.assertEqual(onboarding.slice_id, AWS_CSM_ONBOARDING_SLICE_ID)
        self.assertEqual(onboarding.entrypoint_id, AWS_CSM_ONBOARDING_ENTRYPOINT_ID)
        self.assertTrue(onboarding.audit_required and onboarding.read_after_write_required)

    def test_internal_audience_cannot_launch_onboarding_slice(self) -> None:
        decision = resolve_admin_tool_launch(
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            audience="internal",
            expected_entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "audience_not_allowed")

    def test_begin_onboarding_applies_audit_and_read_after_write(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws_live.json"
            audit_file = Path(temp_dir) / "audit.ndjson"
            profile_file.write_text(json.dumps(_live_profile_tenant_a()) + "\n", encoding="utf-8")
            tool_exposure_policy = build_admin_tool_exposure_policy(
                {"aws_csm_onboarding": {"enabled": True}},
                known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis"],
            )

            registry_result = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                }
            )
            onboarding_entry = [
                e for e in registry_result["surface_payload"]["tool_entries"] if e["slice_id"] == AWS_CSM_ONBOARDING_SLICE_ID
            ][0]

            result = run_admin_aws_csm_onboarding(
                {
                    "schema": ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "onboarding_action": "begin_onboarding",
                },
                aws_status_file=profile_file,
                audit_storage_file=audit_file,
                tool_exposure_policy=tool_exposure_policy,
            )

            self.assertEqual(onboarding_entry["entrypoint_id"], AWS_CSM_ONBOARDING_ENTRYPOINT_ID)
            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], AWS_CSM_ONBOARDING_ENTRYPOINT_ID)
            self.assertEqual(result["surface_payload"]["schema"], ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA)
            self.assertEqual(result["surface_payload"]["onboarding_action"], "begin_onboarding")
            self.assertIn("workflow", result["surface_payload"]["updated_sections"])
            self.assertEqual(result["surface_payload"]["write_status"], "applied")
            self.assertTrue(result["surface_payload"]["audit"]["record_id"])

            reloaded = json.loads(profile_file.read_text(encoding="utf-8"))
            self.assertTrue(reloaded["workflow"]["initiated"])
            self.assertIn("initiated_at", reloaded["workflow"])

            ro = run_admin_aws_read_only(
                {
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                },
                aws_status_file=profile_file,
            )
            self.assertIsNone(ro.get("error"))
            self.assertEqual(ro["surface_payload"]["gmail_state"], "gmail_pending")

    def test_replay_verification_forward_is_policy_blocked(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws_live.json"
            audit_file = Path(temp_dir) / "audit.ndjson"
            profile_file.write_text(json.dumps(_live_profile_tenant_a(initiated=True)) + "\n", encoding="utf-8")

            result = run_admin_aws_csm_onboarding(
                {
                    "schema": ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "onboarding_action": "replay_verification_forward",
                },
                aws_status_file=profile_file,
                audit_storage_file=audit_file,
            )
            self.assertIsNotNone(result.get("error"))
            self.assertEqual(result["error"]["code"], "replay_verification_forward_not_enabled")

    def test_confirm_verified_fail_closed_without_cloud_evidence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws_live.json"
            audit_file = Path(temp_dir) / "audit.ndjson"
            profile_file.write_text(json.dumps(_live_profile_tenant_a(initiated=True)) + "\n", encoding="utf-8")

            result = run_admin_aws_csm_onboarding(
                {
                    "schema": ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "onboarding_action": "confirm_verified",
                },
                aws_status_file=profile_file,
                audit_storage_file=audit_file,
            )
            self.assertEqual(result["error"]["code"], "gmail_confirmation_evidence_required")

    def test_confirm_verified_succeeds_when_cloud_port_attests_evidence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws_live.json"
            audit_file = Path(temp_dir) / "audit.ndjson"
            profile_file.write_text(json.dumps(_live_profile_tenant_a(initiated=True)) + "\n", encoding="utf-8")

            result = run_admin_aws_csm_onboarding(
                {
                    "schema": ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "onboarding_action": "confirm_verified",
                },
                aws_status_file=profile_file,
                audit_storage_file=audit_file,
                onboarding_cloud_port=_FakeOnboardingCloud(evidence_ok=True),
            )
            self.assertIsNone(result.get("error"))
            sp = result["surface_payload"]["confirmed_read_only_surface"]
            self.assertEqual(sp["gmail_state"], "gmail_verified")


if __name__ == "__main__":
    unittest.main()
