from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from MyCiteV2.packages.core.datum_refs import normalize_datum_ref
from MyCiteV2.packages.modules.cross_domain.aws_operational_visibility import (
    AwsReadOnlyOperationalVisibility,
    normalize_aws_operational_visibility,
)
from MyCiteV2.packages.ports.aws_narrow_write import AwsNarrowWritePort, AwsNarrowWriteRequest

ALLOWED_AWS_NARROW_WRITE_FIELDS = frozenset({"selected_verified_sender"})
_ALLOWED_COMMAND_FIELDS = frozenset(
    {"tenant_scope_id", "focus_subject", "profile_id", "selected_verified_sender"}
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_email(value: object, *, field_name: str) -> str:
    token = _as_text(value).lower()
    if not token or "@" not in token or token.startswith("@") or token.endswith("@"):
        raise ValueError(f"{field_name} must be an email-like value")
    return token


@dataclass(frozen=True)
class AwsNarrowWriteCommand:
    tenant_scope_id: str
    focus_subject: str
    profile_id: str
    selected_verified_sender: str
    writable_field_set: tuple[str, ...] = field(default=("selected_verified_sender",), init=False)

    def __post_init__(self) -> None:
        tenant_scope_id = _as_text(self.tenant_scope_id)
        profile_id = _as_text(self.profile_id)
        if not tenant_scope_id:
            raise ValueError("aws_narrow_write.tenant_scope_id is required")
        if not profile_id:
            raise ValueError("aws_narrow_write.profile_id is required")
        object.__setattr__(self, "tenant_scope_id", tenant_scope_id)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(
            self,
            "focus_subject",
            normalize_datum_ref(
                self.focus_subject,
                require_qualified=True,
                write_format="dot",
                field_name="aws_narrow_write.focus_subject",
            ),
        )
        object.__setattr__(
            self,
            "selected_verified_sender",
            _normalize_email(
                self.selected_verified_sender,
                field_name="aws_narrow_write.selected_verified_sender",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_scope_id": self.tenant_scope_id,
            "focus_subject": self.focus_subject,
            "profile_id": self.profile_id,
            "selected_verified_sender": self.selected_verified_sender,
            "writable_field_set": list(self.writable_field_set),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AwsNarrowWriteCommand":
        if not isinstance(payload, dict):
            raise ValueError("aws_narrow_write must be a dict")
        extra_fields = sorted(set(payload.keys()) - _ALLOWED_COMMAND_FIELDS)
        if extra_fields:
            raise ValueError(f"aws_narrow_write has unsupported fields: {extra_fields}")
        return cls(
            tenant_scope_id=payload.get("tenant_scope_id"),
            focus_subject=payload.get("focus_subject"),
            profile_id=payload.get("profile_id"),
            selected_verified_sender=payload.get("selected_verified_sender"),
        )


@dataclass(frozen=True)
class AwsNarrowWriteOutcome:
    command: AwsNarrowWriteCommand
    confirmed_visibility: AwsReadOnlyOperationalVisibility

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.command.profile_id,
            "focus_subject": self.command.focus_subject,
            "updated_fields": list(self.command.writable_field_set),
            "selected_verified_sender": self.command.selected_verified_sender,
            "confirmed_visibility": self.confirmed_visibility.to_dict(),
        }

    def to_local_audit_payload(self) -> dict[str, Any]:
        return {
            "event_type": "aws.operational.write.accepted",
            "focus_subject": self.command.focus_subject,
            "shell_verb": "admin.aws.narrow_write",
            "details": {
                "tenant_scope_id": self.command.tenant_scope_id,
                "profile_id": self.command.profile_id,
                "updated_fields": list(self.command.writable_field_set),
                "selected_verified_sender": self.command.selected_verified_sender,
            },
        }


def normalize_aws_narrow_write_command(
    payload: AwsNarrowWriteCommand | dict[str, Any],
) -> AwsNarrowWriteCommand:
    if isinstance(payload, AwsNarrowWriteCommand):
        return payload
    return AwsNarrowWriteCommand.from_dict(payload)


class AwsNarrowWriteService:
    def __init__(self, narrow_write_port: AwsNarrowWritePort) -> None:
        self._narrow_write_port = narrow_write_port

    def apply_write(self, payload: AwsNarrowWriteCommand | dict[str, Any]) -> AwsNarrowWriteOutcome:
        command = normalize_aws_narrow_write_command(payload)
        result = self._narrow_write_port.apply_aws_narrow_write(
            AwsNarrowWriteRequest(
                tenant_scope_id=command.tenant_scope_id,
                profile_id=command.profile_id,
                selected_verified_sender=command.selected_verified_sender,
            )
        )
        confirmed_payload = dict(result.source.payload)
        if confirmed_payload.get("tenant_scope_id"):
            if _as_text(confirmed_payload.get("tenant_scope_id")) != command.tenant_scope_id:
                raise ValueError("aws_narrow_write confirmation tenant_scope_id does not match request")
        confirmed_payload["tenant_scope_id"] = command.tenant_scope_id
        confirmed_visibility = normalize_aws_operational_visibility(confirmed_payload)
        if confirmed_visibility.canonical_newsletter_profile.profile_id != command.profile_id:
            raise ValueError("aws_narrow_write confirmation profile_id does not match request")
        if confirmed_visibility.selected_verified_sender != command.selected_verified_sender:
            raise ValueError("aws_narrow_write confirmation selected_verified_sender does not match request")
        return AwsNarrowWriteOutcome(
            command=command,
            confirmed_visibility=confirmed_visibility,
        )
