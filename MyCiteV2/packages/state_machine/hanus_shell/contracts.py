from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from MyCiteV2.packages.state_machine.aitas import AitasContext, normalize_attention
from MyCiteV2.packages.state_machine.nimm import DEFAULT_SHELL_VERB, normalize_shell_verb

SHELL_ACTION_SCHEMA = "mycite.v2.shell.action.v1"
SHELL_STATE_SCHEMA = "mycite.v2.shell.state.v1"
SHELL_RESULT_SCHEMA = "mycite.v2.shell.result.v1"


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = str(payload.get("schema") or "").strip()
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


@dataclass(frozen=True)
class ShellAction:
    shell_verb: str
    focus_subject: str
    schema: str = field(default=SHELL_ACTION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "shell_verb",
            normalize_shell_verb(self.shell_verb, field_name="shell_action.shell_verb"),
        )
        object.__setattr__(
            self,
            "focus_subject",
            normalize_attention(self.focus_subject, field_name="shell_action.focus_subject"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "shell_verb": self.shell_verb,
            "focus_subject": self.focus_subject,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ShellAction":
        if not isinstance(payload, dict):
            raise ValueError("shell_action must be a dict")
        _require_schema(payload, expected=SHELL_ACTION_SCHEMA, field_name="shell_action.schema")
        return cls(
            shell_verb=payload.get("shell_verb"),
            focus_subject=payload.get("focus_subject"),
        )


@dataclass(frozen=True)
class ShellState:
    aitas_context: AitasContext = field(default_factory=lambda: AitasContext(intention=DEFAULT_SHELL_VERB))
    schema: str = field(default=SHELL_STATE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if isinstance(self.aitas_context, AitasContext):
            context = self.aitas_context
        elif isinstance(self.aitas_context, dict):
            context = AitasContext.from_dict(self.aitas_context)
        else:
            raise ValueError("shell_state.aitas_context must be an AitasContext or dict")

        intention = context.intention or DEFAULT_SHELL_VERB
        object.__setattr__(
            self,
            "aitas_context",
            AitasContext(
                attention=context.attention,
                intention=normalize_shell_verb(intention, field_name="shell_state.intention"),
            ),
        )

    @property
    def attention(self) -> str:
        return self.aitas_context.attention

    @property
    def intention(self) -> str:
        return self.aitas_context.intention

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "attention": self.attention,
            "intention": self.intention,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ShellState":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("shell_state must be a dict")
        _require_schema(payload, expected=SHELL_STATE_SCHEMA, field_name="shell_state.schema")
        return cls(
            aitas_context=AitasContext.from_dict(
                {
                    "attention": payload.get("attention"),
                    "intention": payload.get("intention"),
                }
            )
        )


@dataclass(frozen=True)
class ShellResult:
    shell_verb: str
    focus_subject: str
    shell_state: ShellState
    schema: str = field(default=SHELL_RESULT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        state = self.shell_state if isinstance(self.shell_state, ShellState) else ShellState.from_dict(self.shell_state)
        normalized_verb = normalize_shell_verb(self.shell_verb, field_name="shell_result.shell_verb")
        normalized_subject = normalize_attention(self.focus_subject, field_name="shell_result.focus_subject")
        if state.attention != normalized_subject:
            raise ValueError("shell_result.shell_state.attention must match shell_result.focus_subject")
        if state.intention != normalized_verb:
            raise ValueError("shell_result.shell_state.intention must match shell_result.shell_verb")
        object.__setattr__(self, "shell_state", state)
        object.__setattr__(self, "shell_verb", normalized_verb)
        object.__setattr__(self, "focus_subject", normalized_subject)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "shell_verb": self.shell_verb,
            "focus_subject": self.focus_subject,
            "shell_state": self.shell_state.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ShellResult":
        if not isinstance(payload, dict):
            raise ValueError("shell_result must be a dict")
        _require_schema(payload, expected=SHELL_RESULT_SCHEMA, field_name="shell_result.schema")
        return cls(
            shell_verb=payload.get("shell_verb"),
            focus_subject=payload.get("focus_subject"),
            shell_state=ShellState.from_dict(payload.get("shell_state")),
        )
