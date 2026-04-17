from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemAwsCsmToolProfileStore
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingProfileStorePort
from MyCiteV2.packages.ports.aws_csm_profile_registry import AwsCsmProfileRegistryPort


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_profile() -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.fnd.dylan",
            "tenant_id": "fnd",
            "domain": "fruitfulnetworkdevelopment.com",
            "region": "us-east-1",
            "mailbox_local_part": "dylan",
            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
            "single_user_email": "dylan@fruitfulnetworkdevelopment.com",
        },
        "smtp": {"forward_to_email": "dylan@fruitfulnetworkdevelopment.com"},
        "workflow": {"lifecycle_state": "ready"},
        "verification": {"portal_state": "verified"},
        "provider": {"aws_ses_identity_status": "verified"},
        "inbound": {"receive_state": "receive_operational"},
    }


class FilesystemAwsCsmToolProfileStoreTests(unittest.TestCase):
    def test_registry_creation_updates_collection_and_profile_loading(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {
                    "schema": "mycite.portal.tool_collection.v1",
                    "member_files": ["aws-csm.fnd.dylan.json"],
                },
            )
            _write_json(tool_root / "aws-csm.fnd.dylan.json", _seed_profile())

            adapter = FilesystemAwsCsmToolProfileStore(tool_root)
            self.assertIsInstance(adapter, AwsCsmProfileRegistryPort)
            self.assertIsInstance(adapter, AwsCsmOnboardingProfileStorePort)

            created = adapter.create_profile(
                profile_id="aws-csm.fnd.alex",
                payload={
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.fnd.alex",
                        "tenant_id": "fnd",
                        "domain": "fruitfulnetworkdevelopment.com",
                        "region": "us-east-1",
                        "mailbox_local_part": "alex",
                        "send_as_email": "alex@fruitfulnetworkdevelopment.com",
                        "single_user_email": "alex@example.com",
                    },
                    "smtp": {"forward_to_email": "ops@example.com"},
                    "workflow": {"lifecycle_state": "draft"},
                    "verification": {"portal_state": "not_started"},
                    "provider": {"gmail_send_as_status": "not_started"},
                    "inbound": {"receive_state": "receive_unconfigured"},
                },
            )

            self.assertEqual(created["identity"]["profile_id"], "aws-csm.fnd.alex")
            collection_payload = json.loads(
                (tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json").read_text(encoding="utf-8")
            )
            self.assertIn("aws-csm.fnd.alex.json", collection_payload["member_files"])
            loaded = adapter.load_profile(tenant_scope_id="fnd", profile_id="aws-csm.fnd.alex")
            self.assertEqual(loaded["identity"]["send_as_email"], "alex@fruitfulnetworkdevelopment.com")

    def test_save_profile_round_trips_for_onboarding_updates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {"schema": "mycite.portal.tool_collection.v1", "member_files": ["aws-csm.fnd.dylan.json"]},
            )
            _write_json(tool_root / "aws-csm.fnd.dylan.json", _seed_profile())
            adapter = FilesystemAwsCsmToolProfileStore(tool_root)

            payload = adapter.load_profile(tenant_scope_id="fruitfulnetworkdevelopment.com", profile_id="aws-csm.fnd.dylan")
            payload["workflow"]["handoff_status"] = "ready_for_gmail_handoff"
            payload["smtp"]["username"] = "SMTPUSER"
            saved = adapter.save_profile(
                tenant_scope_id="fruitfulnetworkdevelopment.com",
                profile_id="aws-csm.fnd.dylan",
                payload=payload,
            )

            self.assertEqual(saved["workflow"]["handoff_status"], "ready_for_gmail_handoff")
            self.assertEqual(saved["smtp"]["username"], "SMTPUSER")


if __name__ == "__main__":
    unittest.main()
