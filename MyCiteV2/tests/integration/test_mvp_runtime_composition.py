from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.mvp_runtime import run_shell_action_to_local_audit
from MyCiteV2.packages.state_machine.hanus_shell import SHELL_ACTION_SCHEMA, SHELL_STATE_SCHEMA

MSN_ID = "3-2-3-17-77-1-6-4-1-4"
CANONICAL_SUBJECT = f"{MSN_ID}.4-1-77"
LEGACY_HYPHEN_SUBJECT = f"{MSN_ID}-4-1-77"


class MvpRuntimeCompositionTests(unittest.TestCase):
    def test_shell_action_to_local_audit_executes_end_to_end(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage_file = Path(temp_dir) / "local_audit.ndjson"

            result = run_shell_action_to_local_audit(
                {
                    "schema": SHELL_ACTION_SCHEMA,
                    "shell_verb": "navigate",
                    "focus_subject": LEGACY_HYPHEN_SUBJECT,
                },
                storage_file=storage_file,
            )

            self.assertEqual(
                result,
                {
                    "normalized_subject": CANONICAL_SUBJECT,
                    "normalized_shell_verb": "navigate",
                    "normalized_shell_state": {
                        "schema": SHELL_STATE_SCHEMA,
                        "attention": CANONICAL_SUBJECT,
                        "intention": "navigate",
                    },
                    "persisted_audit_identifier": result["persisted_audit_identifier"],
                    "persisted_audit_timestamp": result["persisted_audit_timestamp"],
                },
            )
            self.assertTrue(result["persisted_audit_identifier"])
            self.assertGreaterEqual(result["persisted_audit_timestamp"], 0)

            rows = [json.loads(line) for line in storage_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                rows[0],
                {
                    "record_id": result["persisted_audit_identifier"],
                    "recorded_at_unix_ms": result["persisted_audit_timestamp"],
                    "record": {
                        "event_type": "shell.transition.accepted",
                        "focus_subject": CANONICAL_SUBJECT,
                        "shell_verb": "navigate",
                        "details": {},
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()
