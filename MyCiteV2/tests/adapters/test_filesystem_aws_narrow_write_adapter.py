from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemAwsNarrowWriteAdapter
from MyCiteV2.packages.ports.aws_narrow_write import AwsNarrowWritePort, AwsNarrowWriteRequest


class FilesystemAwsNarrowWriteAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_aws_narrow_write_port(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemAwsNarrowWriteAdapter(Path(temp_dir) / "aws_status.json")
            self.assertIsInstance(adapter, AwsNarrowWritePort)

    def test_apply_write_updates_selected_verified_sender_and_reads_back(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "aws_status.json"
            storage_file.write_text(
                json.dumps(
                    {
                        "tenant_scope_id": "tenant-a",
                        "selected_verified_sender": "old@example.com",
                        "canonical_newsletter_profile": {
                            "profile_id": "newsletter.example.com",
                            "selected_verified_sender": "old@example.com",
                        },
                    }
                ),
                encoding="utf-8",
            )
            adapter = FilesystemAwsNarrowWriteAdapter(storage_file)

            result = adapter.apply_aws_narrow_write(
                AwsNarrowWriteRequest(
                    tenant_scope_id="tenant-a",
                    profile_id="newsletter.example.com",
                    selected_verified_sender="new@example.com",
                )
            )

            self.assertEqual(
                result.to_dict(),
                {
                    "source": {
                        "payload": {
                            "tenant_scope_id": "tenant-a",
                            "selected_verified_sender": "new@example.com",
                            "canonical_newsletter_profile": {
                                "profile_id": "newsletter.example.com",
                                "selected_verified_sender": "new@example.com",
                            },
                        }
                    }
                },
            )

    def test_apply_write_rejects_missing_snapshot_or_profile_mismatch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "aws_status.json"
            adapter = FilesystemAwsNarrowWriteAdapter(storage_file)

            with self.assertRaisesRegex(ValueError, "existing status snapshot file"):
                adapter.apply_aws_narrow_write(
                    AwsNarrowWriteRequest(
                        tenant_scope_id="tenant-a",
                        profile_id="newsletter.example.com",
                        selected_verified_sender="new@example.com",
                    )
                )

            storage_file.write_text(
                json.dumps(
                    {
                        "tenant_scope_id": "tenant-a",
                        "selected_verified_sender": "old@example.com",
                        "canonical_newsletter_profile": {
                            "profile_id": "other.example.com",
                            "selected_verified_sender": "old@example.com",
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "profile_id does not match"):
                adapter.apply_aws_narrow_write(
                    AwsNarrowWriteRequest(
                        tenant_scope_id="tenant-a",
                        profile_id="newsletter.example.com",
                        selected_verified_sender="new@example.com",
                    )
                )


if __name__ == "__main__":
    unittest.main()
