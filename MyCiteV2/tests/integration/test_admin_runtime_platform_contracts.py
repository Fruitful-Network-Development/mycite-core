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
    ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
    run_admin_aws_narrow_write,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.instances._shared.runtime.runtime_platform import ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
    FND_EBI_READ_ONLY_ENTRYPOINT_ID,
    build_admin_tool_registry_entries,
)

FOCUS_SUBJECT = "3-2-3-17-77-1-6-4-1-4.4-1-77"


class AdminRuntimePlatformIntegrationTests(unittest.TestCase):
    def test_current_admin_entrypoints_return_shared_envelope_shape(self) -> None:
        with TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "aws_status.json"
            status_file.write_text(
                json.dumps(
                    {
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
                ),
                encoding="utf-8",
            )

            home = run_admin_shell_entry(
                {
                    "schema": ADMIN_SHELL_REQUEST_SCHEMA,
                    "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                }
            )
            read_only_missing_config = run_admin_aws_read_only(
                {
                    "schema": ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                }
            )
            narrow_write_missing_audit = run_admin_aws_narrow_write(
                {
                    "schema": ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "tenant-a", "audience": "trusted-tenant"},
                    "focus_subject": FOCUS_SUBJECT,
                    "profile_id": "newsletter.example.com",
                    "selected_verified_sender": "new@example.com",
                },
                aws_status_file=status_file,
            )

            self.assertEqual(tuple(home.keys()), ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS)
            self.assertEqual(tuple(read_only_missing_config.keys()), ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS)
            self.assertEqual(tuple(narrow_write_missing_audit.keys()), ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS)
            self.assertEqual(read_only_missing_config["error"]["code"], "status_source_not_configured")
            self.assertEqual(narrow_write_missing_audit["error"]["code"], "audit_log_not_configured")

    def test_tool_registry_descriptors_match_runtime_entrypoint_ids(self) -> None:
        entrypoint_ids = [entry.entrypoint_id for entry in build_admin_tool_registry_entries()]

        self.assertEqual(
            entrypoint_ids,
            [
                AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
                AWS_NARROW_WRITE_ENTRYPOINT_ID,
                AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
                AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
                CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
                FND_EBI_READ_ONLY_ENTRYPOINT_ID,
            ],
        )
        self.assertNotIn("provider-admin", json.dumps(entrypoint_ids, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
