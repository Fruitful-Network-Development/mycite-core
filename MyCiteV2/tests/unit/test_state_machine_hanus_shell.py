from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.aitas import AitasContext, normalize_attention
from MyCiteV2.packages.state_machine.hanus_shell import (
    SHELL_ACTION_SCHEMA,
    SHELL_RESULT_SCHEMA,
    SHELL_STATE_SCHEMA,
    ShellAction,
    ShellResult,
    ShellState,
    reduce_shell_action,
)
from MyCiteV2.packages.state_machine.nimm import DEFAULT_SHELL_VERB

MSN_ID = "3-2-3-17-77-1-6-4-1-4"
CANONICAL_SUBJECT = f"{MSN_ID}.4-1-77"
LEGACY_HYPHEN_SUBJECT = f"{MSN_ID}-4-1-77"


class HanusShellUnitTests(unittest.TestCase):
    def test_shell_action_normalizes_focus_subject_to_canonical_dot(self) -> None:
        action = ShellAction.from_dict(
            {
                "schema": SHELL_ACTION_SCHEMA,
                "shell_verb": DEFAULT_SHELL_VERB,
                "focus_subject": LEGACY_HYPHEN_SUBJECT,
            }
        )

        self.assertEqual(action.shell_verb, DEFAULT_SHELL_VERB)
        self.assertEqual(action.focus_subject, CANONICAL_SUBJECT)
        self.assertEqual(
            action.to_dict(),
            {
                "schema": SHELL_ACTION_SCHEMA,
                "shell_verb": DEFAULT_SHELL_VERB,
                "focus_subject": CANONICAL_SUBJECT,
            },
        )

    def test_shell_action_rejects_non_contract_or_noncanonical_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "shell_action.schema"):
            ShellAction.from_dict(
                {
                    "schema": "wrong.schema",
                    "shell_verb": DEFAULT_SHELL_VERB,
                    "focus_subject": CANONICAL_SUBJECT,
                }
            )

        with self.assertRaisesRegex(ValueError, "shell_action.shell_verb"):
            ShellAction.from_dict(
                {
                    "schema": SHELL_ACTION_SCHEMA,
                    "shell_verb": "investigate",
                    "focus_subject": CANONICAL_SUBJECT,
                }
            )

        with self.assertRaisesRegex(ValueError, "qualified datum_ref"):
            ShellAction.from_dict(
                {
                    "schema": SHELL_ACTION_SCHEMA,
                    "shell_verb": DEFAULT_SHELL_VERB,
                    "focus_subject": "4-1-77",
                }
            )

    def test_reducer_produces_normalized_state_and_shell_result(self) -> None:
        current_state = ShellState()
        action = ShellAction.from_dict(
            {
                "schema": SHELL_ACTION_SCHEMA,
                "shell_verb": DEFAULT_SHELL_VERB,
                "focus_subject": CANONICAL_SUBJECT,
            }
        )

        result = reduce_shell_action(current_state, action)

        self.assertEqual(result.shell_verb, DEFAULT_SHELL_VERB)
        self.assertEqual(result.focus_subject, CANONICAL_SUBJECT)
        self.assertEqual(result.shell_state.attention, CANONICAL_SUBJECT)
        self.assertEqual(result.shell_state.intention, DEFAULT_SHELL_VERB)
        self.assertEqual(
            result.to_dict(),
            {
                "schema": SHELL_RESULT_SCHEMA,
                "shell_verb": DEFAULT_SHELL_VERB,
                "focus_subject": CANONICAL_SUBJECT,
                "shell_state": {
                    "schema": SHELL_STATE_SCHEMA,
                    "attention": CANONICAL_SUBJECT,
                    "intention": DEFAULT_SHELL_VERB,
                },
            },
        )

    def test_contract_shapes_round_trip_through_serializable_payloads(self) -> None:
        action = ShellAction.from_dict(
            {
                "schema": SHELL_ACTION_SCHEMA,
                "shell_verb": DEFAULT_SHELL_VERB,
                "focus_subject": LEGACY_HYPHEN_SUBJECT,
            }
        )
        state = ShellState.from_dict(
            {
                "schema": SHELL_STATE_SCHEMA,
                "attention": CANONICAL_SUBJECT,
                "intention": DEFAULT_SHELL_VERB,
            }
        )
        result = ShellResult.from_dict(
            {
                "schema": SHELL_RESULT_SCHEMA,
                "shell_verb": DEFAULT_SHELL_VERB,
                "focus_subject": CANONICAL_SUBJECT,
                "shell_state": state.to_dict(),
            }
        )

        self.assertEqual(
            json.loads(json.dumps(action.to_dict(), sort_keys=True)),
            action.to_dict(),
        )
        self.assertEqual(
            json.loads(json.dumps(state.to_dict(), sort_keys=True)),
            state.to_dict(),
        )
        self.assertEqual(
            json.loads(json.dumps(result.to_dict(), sort_keys=True)),
            result.to_dict(),
        )

    def test_aitas_context_serializes_only_attention_and_intention(self) -> None:
        context = AitasContext(attention=LEGACY_HYPHEN_SUBJECT, intention=DEFAULT_SHELL_VERB)

        self.assertEqual(
            context.to_dict(),
            {
                "attention": CANONICAL_SUBJECT,
                "intention": DEFAULT_SHELL_VERB,
            },
        )
        self.assertEqual(normalize_attention(LEGACY_HYPHEN_SUBJECT), CANONICAL_SUBJECT)

    def test_reducer_is_deterministic_for_identical_input(self) -> None:
        initial_state = ShellState()
        action_payload = {
            "schema": SHELL_ACTION_SCHEMA,
            "shell_verb": DEFAULT_SHELL_VERB,
            "focus_subject": LEGACY_HYPHEN_SUBJECT,
        }

        first = reduce_shell_action(initial_state, action_payload)
        second = reduce_shell_action(initial_state, action_payload)

        self.assertEqual(first.to_dict(), second.to_dict())


if __name__ == "__main__":
    unittest.main()
