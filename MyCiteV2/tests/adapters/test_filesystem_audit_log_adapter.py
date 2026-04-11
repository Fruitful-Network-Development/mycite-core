from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
from MyCiteV2.packages.ports.audit_log import (
    AUDIT_LOG_RECENT_WINDOW_LIMIT,
    AuditLogAppendRequest,
    AuditLogPort,
    AuditLogRecentWindowRequest,
    AuditLogReadRequest,
)


class FilesystemAuditLogAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_audit_log_port(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemAuditLogAdapter(Path(temp_dir) / "audit.ndjson")
            self.assertIsInstance(adapter, AuditLogPort)

    def test_append_then_read_round_trip_matches_port_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "audit.ndjson"
            adapter = FilesystemAuditLogAdapter(
                storage_file,
                clock=lambda: 1770000000001,
                id_factory=lambda: "audit-0001",
            )

            receipt = adapter.append_audit_record(
                AuditLogAppendRequest(
                    record={
                        "event_type": "shell.transition.accepted",
                        "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                        "shell_verb": "navigate",
                        "details": {"source": "mvp"},
                    }
                )
            )
            read_result = adapter.read_audit_record(AuditLogReadRequest(record_id="audit-0001"))

            self.assertEqual(
                receipt.to_dict(),
                {
                    "record_id": "audit-0001",
                    "recorded_at_unix_ms": 1770000000001,
                },
            )
            self.assertTrue(read_result.found)
            self.assertEqual(
                read_result.to_dict(),
                {
                    "found": True,
                    "record": {
                        "record_id": "audit-0001",
                        "recorded_at_unix_ms": 1770000000001,
                        "record": {
                            "event_type": "shell.transition.accepted",
                            "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                            "shell_verb": "navigate",
                            "details": {"source": "mvp"},
                        },
                    },
                },
            )

    def test_read_returns_not_found_when_storage_missing_or_id_absent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "audit.ndjson"
            adapter = FilesystemAuditLogAdapter(storage_file)

            missing_before_write = adapter.read_audit_record(AuditLogReadRequest(record_id="missing"))
            adapter.append_audit_record(
                AuditLogAppendRequest(
                    record={
                        "event_type": "shell.transition.accepted",
                        "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                        "shell_verb": "navigate",
                        "details": {},
                    }
                )
            )
            missing_after_write = adapter.read_audit_record(AuditLogReadRequest(record_id="still-missing"))

            self.assertEqual(missing_before_write.to_dict(), {"found": False, "record": None})
            self.assertEqual(missing_after_write.to_dict(), {"found": False, "record": None})

    def test_recent_window_returns_newest_valid_records_and_skips_malformed_lines(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "audit.ndjson"
            records = [
                {
                    "record_id": "audit-0001",
                    "recorded_at_unix_ms": 1770000000001,
                    "record": {"event_type": "shell.transition.accepted"},
                },
                {
                    "record_id": "audit-0002",
                    "recorded_at_unix_ms": 1770000000002,
                    "record": {"event_type": "shell.transition.accepted"},
                },
                {
                    "record_id": "audit-0003",
                    "recorded_at_unix_ms": 1770000000003,
                    "record": {"event_type": "shell.transition.accepted"},
                },
            ]
            storage_file.write_text(
                "\n".join(
                    [
                        json.dumps(records[0], separators=(",", ":")),
                        "{not-json",
                        "",
                        json.dumps(records[1], separators=(",", ":")),
                        json.dumps({"record_id": "bad", "recorded_at_unix_ms": -1, "record": {}}),
                        json.dumps(records[2], separators=(",", ":")),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            adapter = FilesystemAuditLogAdapter(storage_file)
            recent = adapter.read_recent_audit_records(AuditLogRecentWindowRequest())

            self.assertEqual(
                [record.record_id for record in recent.records],
                ["audit-0003", "audit-0002", "audit-0001"],
            )
            self.assertEqual(recent.record_count, 3)

    def test_recent_window_returns_empty_when_storage_is_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemAuditLogAdapter(Path(temp_dir) / "missing.ndjson")

            recent = adapter.read_recent_audit_records(AuditLogRecentWindowRequest())

            self.assertEqual(recent.to_dict(), {"record_count": 0, "records": []})

    def test_recent_window_is_bounded_to_fixed_limit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "audit.ndjson"
            lines = []
            for index in range(AUDIT_LOG_RECENT_WINDOW_LIMIT + 3):
                lines.append(
                    json.dumps(
                        {
                            "record_id": f"audit-{index:04d}",
                            "recorded_at_unix_ms": 1770000000000 + index,
                            "record": {"event_type": "shell.transition.accepted"},
                        },
                        separators=(",", ":"),
                    )
                )
            storage_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

            adapter = FilesystemAuditLogAdapter(storage_file)
            recent = adapter.read_recent_audit_records(AuditLogRecentWindowRequest())

            self.assertEqual(recent.record_count, AUDIT_LOG_RECENT_WINDOW_LIMIT)
            self.assertEqual(recent.records[0].record_id, f"audit-{AUDIT_LOG_RECENT_WINDOW_LIMIT + 2:04d}")
            self.assertEqual(recent.records[-1].record_id, "audit-0003")


if __name__ == "__main__":
    unittest.main()
