"""Ports for portal-shell AWS-CSM mailbox onboarding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AwsCsmOnboardingProfileStorePort(Protocol):
    """Load/save canonical live profile JSON (``mycite.service_tool.aws_csm.profile.v1``)."""

    def load_profile(self, *, tenant_scope_id: str, profile_id: str) -> dict[str, Any] | None:
        ...

    def save_profile(self, *, tenant_scope_id: str, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist and return the stored document (read-after-write source)."""
        ...


@runtime_checkable
class AwsCsmOnboardingCloudPort(Protocol):
    """External AWS / evidence IO; production adapters implement; tests use fakes."""

    def supplemental_profile_patch(self, action: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Top-level partial profile fragments (identity/smtp/verification/provider/workflow/inbound)."""
        ...

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        """Fail closed unless confirmation evidence exists."""
        ...

    def describe_profile_readiness(self, profile: dict[str, Any]) -> dict[str, Any]:
        """AWS-backed readiness/evidence summary used for operator-facing surfaces."""
        ...


_ALLOWED_ACTIONS = frozenset(
    {
        "begin_onboarding",
        "prepare_send_as",
        "stage_smtp_credentials",
        "capture_verification",
        "refresh_provider_status",
        "refresh_inbound_status",
        "enable_inbound_capture",
        "replay_verification_forward",
        "confirm_receive_verified",
        "confirm_verified",
    }
)


@dataclass(frozen=True)
class AwsCsmOnboardingCommand:
    tenant_scope_id: str
    focus_subject: str
    profile_id: str
    onboarding_action: str

    def __post_init__(self) -> None:
        tenant_scope_id = str(self.tenant_scope_id or "").strip()
        profile_id = str(self.profile_id or "").strip()
        action = str(self.onboarding_action or "").strip()
        if not tenant_scope_id:
            raise ValueError("aws_csm_onboarding.tenant_scope_id is required")
        if not profile_id:
            raise ValueError("aws_csm_onboarding.profile_id is required")
        if action not in _ALLOWED_ACTIONS:
            raise ValueError(f"aws_csm_onboarding.onboarding_action is not cataloged: {action}")
        object.__setattr__(self, "tenant_scope_id", tenant_scope_id)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "onboarding_action", action)
        fs = str(self.focus_subject or "").strip()
        if not fs:
            raise ValueError("aws_csm_onboarding.focus_subject is required")
        object.__setattr__(self, "focus_subject", fs)

    def to_audit_details(self) -> dict[str, Any]:
        return {
            "tenant_scope_id": self.tenant_scope_id,
            "profile_id": self.profile_id,
            "onboarding_action": self.onboarding_action,
            "focus_subject": self.focus_subject,
        }


@dataclass(frozen=True)
class AwsCsmOnboardingOutcome:
    command: AwsCsmOnboardingCommand
    updated_sections: tuple[str, ...]
    saved_profile: dict[str, Any]

    def to_local_audit_payload(self) -> dict[str, Any]:
        return {
            "event_type": "aws.csm_onboarding.accepted",
            "focus_subject": self.command.focus_subject,
            "shell_verb": "admin.aws.csm_onboarding",
            "details": {
                **self.command.to_audit_details(),
                "updated_sections": list(self.updated_sections),
            },
        }


class AwsCsmOnboardingPolicyError(ValueError):
    """Raised for explicit policy blocks (mapped to runtime error codes)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


__all__ = [
    "AwsCsmOnboardingCloudPort",
    "AwsCsmOnboardingCommand",
    "AwsCsmOnboardingOutcome",
    "AwsCsmOnboardingPolicyError",
    "AwsCsmOnboardingProfileStorePort",
]
