from __future__ import annotations

from typing import Any


SHELL_ACTION_SCHEMA = "mycite.shell.action.v1"
SHELL_ACTION_SET_VERB = "shell.set_verb"
SHELL_ACTION_FOCUS_SUBJECT = "shell.focus_subject"
SHELL_ACTION_SET_LENS = "shell.set_lens"
SHELL_ACTION_OPEN_TOOL = "shell.open_tool"
SHELL_ACTION_REFRESH_CONTEXT = "shell.refresh_context"
SHELL_ACTION_NAVIGATE = "shell.navigate"
SHELL_ACTION_INVESTIGATE = "shell.investigate"
SHELL_ACTION_MEDIATE = "shell.mediate"
SHELL_ACTION_MANIPULATE = "shell.manipulate"

SHELL_VERB_TO_ACTION = {
    "navigate": SHELL_ACTION_NAVIGATE,
    "investigate": SHELL_ACTION_INVESTIGATE,
    "mediate": SHELL_ACTION_MEDIATE,
    "manipulate": SHELL_ACTION_MANIPULATE,
}


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_shell_action_type(value: object, default: str = SHELL_ACTION_NAVIGATE) -> str:
    token = _text(value).lower()
    if token in SHELL_VERB_TO_ACTION.values() or token in {
        SHELL_ACTION_SET_VERB,
        SHELL_ACTION_FOCUS_SUBJECT,
        SHELL_ACTION_SET_LENS,
        SHELL_ACTION_OPEN_TOOL,
        SHELL_ACTION_REFRESH_CONTEXT,
    }:
        return token
    return default


def build_shell_action(action_type: object, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": SHELL_ACTION_SCHEMA,
        "action_type": normalize_shell_action_type(action_type),
        "payload": dict(payload) if isinstance(payload, dict) else {},
    }


def action_for_shell_verb(shell_verb: object) -> str:
    token = _text(shell_verb).lower()
    return SHELL_VERB_TO_ACTION.get(token, SHELL_ACTION_NAVIGATE)
