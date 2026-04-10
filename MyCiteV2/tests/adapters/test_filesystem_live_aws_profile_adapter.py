from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemLiveAwsProfileAdapter, is_live_aws_profile_file
from MyCiteV2.packages.ports.aws_narrow_write import AwsNarrowWritePort, AwsNarrowWriteRequest
from MyCiteV2.packages.ports.aws_read_only_status import AwsReadOnlyStatusPort, AwsReadOnlyStatusRequest


def _live_profile(selected_sender: str = "technicalcontact@trappfamilyfarm.com") -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.tff.technicalContact",
            "tenant_id": "tff",
            "domain": "trappfamilyfarm.com",
            "mailbox_local_part": "technicalcontact",
            "send_as_email": selected_sender,
        },
        "smtp": {
            "handoff_ready": True,
            "credentials_secret_state": "configured",
            "send_as_email": selected_sender,
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


class FilesystemLiveAwsProfileAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_read_and_write_ports(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemLiveAwsProfileAdapter(Path(temp_dir) / "aws-csm.tff.json")
            self.assertIsInstance(adapter, AwsReadOnlyStatusPort)
            self.assertIsInstance(adapter, AwsNarrowWritePort)

    def test_read_maps_live_profile_to_v2_visibility_shape_without_live_fields(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.tff.json"
            profile_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")
            adapter = FilesystemLiveAwsProfileAdapter(profile_file)

            result = adapter.read_aws_read_only_status(AwsReadOnlyStatusRequest(tenant_scope_id="tff"))

            self.assertTrue(is_live_aws_profile_file(profile_file))
            self.assertTrue(result.found)
            payload = dict(result.source.payload) if result.source else {}
            self.assertEqual(payload["tenant_scope_id"], "tff")
            self.assertEqual(payload["mailbox_readiness"], "ready")
            self.assertEqual(payload["smtp_state"], "smtp_ready")
            self.assertEqual(payload["gmail_state"], "gmail_verified")
            self.assertEqual(payload["verified_evidence_state"], "verified_evidence_present")
            self.assertEqual(payload["selected_verified_sender"], "technicalcontact@trappfamilyfarm.com")
            self.assertEqual(payload["allowed_send_domains"], ["trappfamilyfarm.com"])
            self.assertEqual(
                payload["canonical_newsletter_profile"],
                {
                    "profile_id": "aws-csm.tff.technicalContact",
                    "domain": "trappfamilyfarm.com",
                    "list_address": "technicalcontact@trappfamilyfarm.com",
                    "selected_verified_sender": "technicalcontact@trappfamilyfarm.com",
                    "delivery_mode": "inbound-mail-only",
                },
            )
            serialized = json.dumps(payload, sort_keys=True)
            self.assertNotIn("AKIA", serialized)
            self.assertNotIn("credentials_secret_state", serialized)
            self.assertNotIn("latest_message_s3_uri", serialized)

    def test_read_returns_not_found_for_scope_mismatch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.tff.json"
            profile_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")
            adapter = FilesystemLiveAwsProfileAdapter(profile_file)

            result = adapter.read_aws_read_only_status(AwsReadOnlyStatusRequest(tenant_scope_id="fnd"))

            self.assertFalse(result.found)

    def test_narrow_write_updates_the_live_profile_artifact_and_reads_back(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.tff.json"
            profile_file.write_text(json.dumps(_live_profile()) + "\n", encoding="utf-8")
            adapter = FilesystemLiveAwsProfileAdapter(profile_file)

            result = adapter.apply_aws_narrow_write(
                AwsNarrowWriteRequest(
                    tenant_scope_id="tff",
                    profile_id="aws-csm.tff.technicalContact",
                    selected_verified_sender="ops@trappfamilyfarm.com",
                )
            )

            stored = json.loads(profile_file.read_text(encoding="utf-8"))
            self.assertEqual(stored["identity"]["send_as_email"], "ops@trappfamilyfarm.com")
            self.assertEqual(stored["smtp"]["send_as_email"], "ops@trappfamilyfarm.com")
            self.assertEqual(stored["smtp"]["local_part"], "ops")
            self.assertEqual(result.source.payload["selected_verified_sender"], "ops@trappfamilyfarm.com")

    def test_narrow_write_rejects_profile_mismatch_without_mutating_live_profile(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.tff.json"
            original = _live_profile()
            profile_file.write_text(json.dumps(original) + "\n", encoding="utf-8")
            adapter = FilesystemLiveAwsProfileAdapter(profile_file)

            with self.assertRaisesRegex(ValueError, "profile_id does not match"):
                adapter.apply_aws_narrow_write(
                    AwsNarrowWriteRequest(
                        tenant_scope_id="tff",
                        profile_id="aws-csm.tff.other",
                        selected_verified_sender="ops@trappfamilyfarm.com",
                    )
                )

            self.assertEqual(json.loads(profile_file.read_text(encoding="utf-8")), original)

    def test_narrow_write_accepts_secondary_domain_when_allowlisted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile_file = Path(temp_dir) / "aws-csm.cvcc.json"
            base = _live_profile()
            payload = dict(base)
            payload["identity"] = dict(payload["identity"])  # type: ignore[arg-type]
            payload["identity"]["domain"] = "cuyahogavalleycountrysideconservancy.org"
            payload["identity"]["tenant_id"] = "cvcc"
            payload["identity"]["profile_id"] = "aws-csm.cvcc.technicalContact"
            payload["identity"]["send_as_email"] = "board@cvccboard.org"
            payload["identity"]["mailbox_local_part"] = "board"
            payload["smtp"] = dict(payload["smtp"])  # type: ignore[arg-type]
            payload["smtp"]["send_as_email"] = "board@cvccboard.org"
            payload["smtp"]["local_part"] = "board"
            payload["allowed_send_domains"] = ["cvccboard.org"]
            profile_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            adapter = FilesystemLiveAwsProfileAdapter(profile_file)

            result = adapter.apply_aws_narrow_write(
                AwsNarrowWriteRequest(
                    tenant_scope_id="cvcc",
                    profile_id="aws-csm.cvcc.technicalContact",
                    selected_verified_sender="chair@cvccboard.org",
                )
            )

            stored = json.loads(profile_file.read_text(encoding="utf-8"))
            self.assertEqual(stored["identity"]["send_as_email"], "chair@cvccboard.org")
            self.assertEqual(result.source.payload["selected_verified_sender"], "chair@cvccboard.org")


if __name__ == "__main__":
    unittest.main()
