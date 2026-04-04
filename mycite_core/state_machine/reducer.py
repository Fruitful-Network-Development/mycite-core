from __future__ import annotations

from typing import Any

from .actions import (
    SHELL_ACTION_FOCUS_SUBJECT,
    SHELL_ACTION_OPEN_TOOL,
    SHELL_ACTION_SET_LENS,
    SHELL_ACTION_SET_VERB,
    action_for_shell_verb,
    normalize_shell_action_type,
)
from .state import DataViewState, normalize_aitas_phase


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def reduce_shell_action(state: DataViewState, action: dict[str, Any] | None) -> DataViewState:
    current = state if isinstance(state, DataViewState) else DataViewState()
    body = dict(action or {})
    action_type = normalize_shell_action_type(body.get("action_type"))
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}

    next_state = DataViewState.from_dict(current.to_dict())
    if action_type in {
        action_for_shell_verb("navigate"),
        action_for_shell_verb("investigate"),
        action_for_shell_verb("mediate"),
        action_for_shell_verb("manipulate"),
        SHELL_ACTION_SET_VERB,
    }:
        verb = _text(payload.get("shell_verb") or payload.get("verb"))
        if not verb:
            verb = action_type.removeprefix("shell.")
        next_state.aitas_phase = normalize_aitas_phase(verb)
        next_state.aitas_context = dict(next_state.aitas_context or {})
        next_state.aitas_context["intention"] = verb
        return next_state
    if action_type == SHELL_ACTION_SET_LENS:
        next_state.lens_context = dict(next_state.lens_context or {"default": "default", "overrides": {}})
        next_state.lens_context["default"] = _text(payload.get("lens") or payload.get("lens_id") or "default") or "default"
        return next_state
    if action_type in {SHELL_ACTION_FOCUS_SUBJECT, SHELL_ACTION_OPEN_TOOL}:
        focus_subject = _text(payload.get("focus_subject") or payload.get("subject") or payload.get("tool_id"))
        if focus_subject:
            next_state.focus_subject = focus_subject
            next_state.selection = dict(next_state.selection or {})
            next_state.selection["selected_ref_or_document_id"] = focus_subject
            next_state.aitas_context = dict(next_state.aitas_context or {})
            next_state.aitas_context["attention"] = focus_subject
        return next_state
    return next_state
