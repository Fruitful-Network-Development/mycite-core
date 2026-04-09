from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemAwsReadOnlyStatusAdapter
from MyCiteV2.packages.ports.aws_read_only_status import AwsReadOnlyStatusPort, AwsReadOnlyStatusRequest


class FilesystemAwsReadOnlyStatusAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_aws_read_only_status_port(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemAwsReadOnlyStatusAdapter(Path(temp_dir) / "aws_status.json")
            self.assertIsInstance(adapter, AwsReadOnlyStatusPort)

    def test_read_returns_expected_snapshot_for_matching_tenant(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "aws_status.json"
            storage_file.write_text(
                json.dumps(
                    {
                        "tenant_scope_id": "tenant-a",
                        "mailbox_readiness": "ready_for_gmail_handoff",
                        "smtp_state": "smtp_ready",
                    }
                ),
                encoding="utf-8",
            )
            adapter = FilesystemAwsReadOnlyStatusAdapter(storage_file)

            result = adapter.read_aws_read_only_status(AwsReadOnlyStatusRequest(tenant_scope_id="tenant-a"))

            self.assertTrue(result.found)
            self.assertEqual(
                result.to_dict(),
                {
                    "found": True,
                    "source": {
                        "payload": {
                            "tenant_scope_id": "tenant-a",
                            "mailbox_readiness": "ready_for_gmail_handoff",
                            "smtp_state": "smtp_ready",
                        }
                    },
                },
            )

    def test_read_returns_not_found_for_missing_file_or_scope_mismatch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "aws_status.json"
            adapter = FilesystemAwsReadOnlyStatusAdapter(storage_file)

            missing_before_write = adapter.read_aws_read_only_status(
                AwsReadOnlyStatusRequest(tenant_scope_id="tenant-a")
            )

            storage_file.write_text(
                json.dumps({"tenant_scope_id": "tenant-b", "mailbox_readiness": "ready"}),
                encoding="utf-8",
            )
            mismatch = adapter.read_aws_read_only_status(AwsReadOnlyStatusRequest(tenant_scope_id="tenant-a"))

            self.assertEqual(missing_before_write.to_dict(), {"found": False, "source": None})
            self.assertEqual(mismatch.to_dict(), {"found": False, "source": None})


if __name__ == "__main__":
    unittest.main()
