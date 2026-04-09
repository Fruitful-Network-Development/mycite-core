from __future__ import annotations

from typing import Any

from MyCiteV2.packages.state_machine.aitas import AitasContext

from .contracts import ShellAction, ShellResult, ShellState


def reduce_shell_action(
    state: ShellState | dict[str, Any] | None,
    action: ShellAction | dict[str, Any],
) -> ShellResult:
    normalized_state = state if isinstance(state, ShellState) else ShellState.from_dict(state)
    normalized_action = action if isinstance(action, ShellAction) else ShellAction.from_dict(action)

    next_state = ShellState(
        aitas_context=AitasContext(
            attention=normalized_action.focus_subject,
            intention=normalized_action.shell_verb,
        )
    )

    if normalized_state.attention == next_state.attention and normalized_state.intention == next_state.intention:
        next_state = normalized_state

    return ShellResult(
        shell_verb=normalized_action.shell_verb,
        focus_subject=normalized_action.focus_subject,
        shell_state=next_state,
    )
