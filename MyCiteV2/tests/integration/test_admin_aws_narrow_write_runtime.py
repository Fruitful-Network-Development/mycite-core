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
    ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
    ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA,
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    run_admin_aws_narrow_write,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_SLICE_ID,
)

FOCUS_SUBJECT = "3-2-3-17-77-1-6-4-1-4.4-1-77"


class AdminAwsNarrowWriteRuntimeIntegrationTests(unittest.TestCase):
    def test_shell_registry_entry_launches_narrow_write_with_read_after_write_and_audit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "aws_status.json"
            audit_file = Path(temp_dir) / "audit.ndjson"
            status_file.write_text(
                json.dumps(
                    {
                        "tenant_scope_id": "tenant-a",
                        "mailbox_readiness": "ready_for_gmail_handoff",
                        "smtp_state": "smtp_ready",
                        "gmail_state": "gmail_pending",
                        "verified_evidence_state": "sender_selected",
                        "selected_verified_sender": "old@example.com",
                        "canonical_newsletter_profile": {
                            "profile_id": "newsletter.example.com",
                            "domain": "example.com",
                            "list_address": "news@example.com",
                            "selected_verified_sender": "old@example.com",
                            "delivery_mode": "inbound-mail-only",
                        },
                        "compatibility": {
                            "canonical_profile_matches_compatibility_inputs": True,
                        },
                        "inbound_capture": {"status": "ready", "last_capture_state": "idle"},
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
            write_entry = [entry for entry in registry_result["surface_payload"]["tool_entries"] if entry["slice_id"] == AWS_NARROW_WRITE_SLICE_ID][0]

            result = run_admin_aws_narrow_write(
                {
                    "schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "new@example.com",
                },
                aws_status_file=status_file,
                audit_storage_file=audit_file,
            )

            self.assertTrue(write_entry["launchable"])
            self.assertEqual(write_entry["entrypoint_id"], AWS_NARROW_WRITE_ENTRYPOINT_ID)
            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], AWS_NARROW_WRITE_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], AWS_NARROW_WRITE_SLICE_ID)
            self.assertEqual(result["read_write_posture"], "write")
            self.assertEqual(result["surface_payload"]["schema"], ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA)
            self.assertEqual(result["surface_payload"]["writable_field_set"], ["selected_verified_sender"])
            self.assertEqual(
                result["surface_payload"]["requested_change"],
                {
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "new@example.com",
                },
            )
            confirmed = result["surface_payload"]["confirmed_read_only_surface"]
            self.assertEqual(confirmed["selected_verified_sender"], "new@example.com")
            self.assertEqual(
                confirmed["canonical_newsletter_operational_profile"]["selected_verified_sender"],
                "new@example.com",
            )
            self.assertEqual(result["surface_payload"]["write_status"], "applied")
            self.assertTrue(result["surface_payload"]["audit"]["record_id"])
            self.assertTrue(audit_file.exists())

            audit_service = LocalAuditService(FilesystemAuditLogAdapter(audit_file))
            stored = audit_service.read_record(result["surface_payload"]["audit"]["record_id"])
            self.assertIsNotNone(stored)
            self.assertEqual(stored.record.event_type, "aws.operational.write.accepted")
            self.assertEqual(stored.record.focus_subject, FOCUS_SUBJECT)
            self.assertEqual(stored.record.details["selected_verified_sender"], "new@example.com")

            read_back = run_admin_aws_read_only(
                {
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                },
                aws_status_file=status_file,
            )
            self.assertEqual(read_back["surface_payload"]["selected_verified_sender"], "new@example.com")

    def test_write_requires_audit_path_before_applying(self) -> None:
        with TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "aws_status.json"
            original_payload = {
                "tenant_scope_id": "tenant-a",
                "mailbox_readiness": "ready",
                "smtp_state": "smtp_ready",
                "gmail_state": "gmail_verified",
                "verified_evidence_state": "verified_evidence_present",
                "selected_verified_sender": "old@example.com",
                "canonical_newsletter_profile": {
                    "profile_id": "newsletter.example.com",
                    "domain": "example.com",
                    "list_address": "news@example.com",
                    "selected_verified_sender": "old@example.com",
                    "delivery_mode": "inbound-mail-only",
                },
                "compatibility": {"canonical_profile_matches_compatibility_inputs": True},
                "inbound_capture": {"status": "ready"},
                "dispatch_health": {"status": "healthy"},
            }
            status_file.write_text(json.dumps(original_payload), encoding="utf-8")

            result = run_admin_aws_narrow_write(
                {
                    "schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "new@example.com",
                },
                aws_status_file=status_file,
                audit_storage_file=None,
            )

            self.assertEqual(result["error"]["code"], "audit_log_not_configured")
            self.assertEqual(
                json.loads(status_file.read_text(encoding="utf-8")),
                original_payload,
            )

    def test_live_aws_profile_narrow_write_updates_canonical_live_artifact(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.tff.technicalContact.json"
            audit_file = Path(temp_dir) / "audit.ndjson"
            original_payload = {
                "schema": "mycite.service_tool.aws_csm.profile.v1",
                "identity": {
                    "profile_id": "aws-csm.tff.technicalContact",
                    "tenant_id": "tff",
                    "domain": "trappfamilyfarm.com",
                    "mailbox_local_part": "technicalcontact",
                    "send_as_email": "technicalcontact@trappfamilyfarm.com",
                },
                "smtp": {
                    "handoff_ready": True,
                    "credentials_secret_state": "configured",
                    "send_as_email": "technicalcontact@trappfamilyfarm.com",
                    "local_part": "technicalcontact",
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
            profile_file.write_text(json.dumps(original_payload) + "\n", encoding="utf-8")

            result = run_admin_aws_narrow_write(
                {
                    "schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "aws-csm.tff.technicalContact",
                    "selected_verified_sender": "ops@trappfamilyfarm.com",
                },
                aws_status_file=profile_file,
                audit_storage_file=audit_file,
            )

            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertIsNone(result["error"])
            stored = json.loads(profile_file.read_text(encoding="utf-8"))
            self.assertEqual(stored["identity"]["send_as_email"], "ops@trappfamilyfarm.com")
            self.assertEqual(stored["smtp"]["send_as_email"], "ops@trappfamilyfarm.com")
            confirmed = result["surface_payload"]["confirmed_read_only_surface"]
            self.assertEqual(confirmed["selected_verified_sender"], "ops@trappfamilyfarm.com")
            self.assertTrue(audit_file.exists())

    def test_live_aws_profile_denied_write_leaves_canonical_artifact_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.tff.technicalContact.json"
            original_payload = {
                "schema": "mycite.service_tool.aws_csm.profile.v1",
                "identity": {
                    "profile_id": "aws-csm.tff.technicalContact",
                    "tenant_id": "tff",
                    "domain": "trappfamilyfarm.com",
                    "send_as_email": "technicalcontact@trappfamilyfarm.com",
                },
                "smtp": {
                    "handoff_ready": True,
                    "send_as_email": "technicalcontact@trappfamilyfarm.com",
                },
                "verification": {"status": "verified"},
                "workflow": {"initiated": True},
                "inbound": {},
            }
            profile_file.write_text(json.dumps(original_payload) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "allowed send domain"):
                run_admin_aws_narrow_write(
                    {
                        "schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
                        "tenant_scope": {"scope_id": "tff", "audience": "trusted-tenant"},
                        "focus_subject": FOCUS_SUBJECT,
                        "profile_id": "aws-csm.tff.technicalContact",
                        "selected_verified_sender": "ops@example.com",
                    },
                    aws_status_file=profile_file,
                    audit_storage_file=Path(temp_dir) / "audit.ndjson",
                )

            self.assertEqual(json.loads(profile_file.read_text(encoding="utf-8")), original_payload)


if __name__ == "__main__":
    unittest.main()
