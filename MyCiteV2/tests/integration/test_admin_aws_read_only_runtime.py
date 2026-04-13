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
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
)


class AdminAwsReadOnlyRuntimeIntegrationTests(unittest.TestCase):
    def test_shell_registry_entry_launches_aws_read_only_entrypoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "aws_status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "tenant_scope_id": "tenant-a",
                        "mailbox_readiness": "ready_for_gmail_handoff",
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
                        "compatibility": {
                            "canonical_profile_matches_compatibility_inputs": False,
                        },
                        "inbound_capture": {
                            "status": "ready",
                            "last_capture_state": "idle",
                        },
                        "dispatch_health": {
                            "status": "healthy",
                            "last_delivery_outcome": "ok",
                            "pending_message_count": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            registry_result = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_TOOL_REGISTRY_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                }
            )
            tool_entry = registry_result["surface_payload"]["tool_entries"][0]
            result = run_admin_aws_read_only(
                {
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                },
                aws_status_file=status_file,
            )

            self.assertTrue(tool_entry["launchable"])
            self.assertEqual(tool_entry["entrypoint_id"], AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID)
            self.assertEqual(tool_entry["slice_id"], AWS_READ_ONLY_SLICE_ID)
            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], AWS_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], AWS_READ_ONLY_SLICE_ID)
            self.assertEqual(result["exposure_status"], "trusted-tenant-read-only")
            self.assertEqual(result["surface_payload"]["schema"], ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA)
            self.assertEqual(result["surface_payload"]["mailbox_readiness"], "ready_for_gmail_handoff")
            self.assertEqual(result["surface_payload"]["smtp_state"], "smtp_ready")
            self.assertEqual(result["surface_payload"]["gmail_state"], "gmail_pending")
            self.assertEqual(result["surface_payload"]["selected_verified_sender"], "alerts@example.com")
            self.assertEqual(
                result["surface_payload"]["canonical_newsletter_operational_profile"],
                {
                    "profile_id": "newsletter.example.com",
                    "domain": "example.com",
                    "list_address": "news@example.com",
                    "selected_verified_sender": "alerts@example.com",
                    "delivery_mode": "inbound-mail-only",
                },
            )
            payload_text = json.dumps(result["surface_payload"], sort_keys=True)
            self.assertNotIn("smtp_password", payload_text)
            self.assertNotIn("secret_access_key", payload_text)
            self.assertNotIn("newsletter-admin", payload_text)

    def test_missing_status_source_is_reported_explicitly(self) -> None:
        missing = run_admin_aws_read_only(
            {
                "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
            }
        )

        self.assertEqual(
            missing["error"],
            {
                "code": "status_source_not_configured",
                "message": "AWS read-only status source is not configured.",
            },
        )

    def test_live_aws_profile_file_is_mapped_at_runtime(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.fnd.dylan.json"
            profile_file.write_text(
                json.dumps(
                    {
                        "schema": "mycite.service_tool.aws_csm.profile.v1",
                        "identity": {
                            "profile_id": "aws-csm.fnd.dylan",
                            "tenant_id": "fnd",
                            "domain": "fruitfulnetworkdevelopment.com",
                            "mailbox_local_part": "dylan",
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                        },
                        "smtp": {
                            "handoff_ready": True,
                            "credentials_secret_state": "configured",
                            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
                        },
                        "verification": {"status": "verified"},
                        "provider": {"gmail_send_as_status": "verified"},
                        "workflow": {
                            "initiated": True,
                            "lifecycle_state": "operational",
                            "is_mailbox_operational": True,
                        },
                        "inbound": {"receive_verified": True, "latest_message_id": "message-1"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_admin_aws_read_only(
                {
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "fnd", "audience": "trusted-tenant"},
                },
                aws_status_file=profile_file,
            )

            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertIsNone(result["error"])
            surface = result["surface_payload"]
            self.assertEqual(surface["selected_verified_sender"], "dylan@fruitfulnetworkdevelopment.com")
            self.assertEqual(surface["allowed_send_domains"], ["fruitfulnetworkdevelopment.com"])
            self.assertEqual(
                surface["canonical_newsletter_operational_profile"]["profile_id"],
                "aws-csm.fnd.dylan",
            )
            self.assertEqual(surface["mailbox_readiness"], "ready")
            serialized = json.dumps(surface, sort_keys=True)
            self.assertNotIn("credentials_secret_state", serialized)
            self.assertNotIn("latest_message_id", serialized)


if __name__ == "__main__":
    unittest.main()
