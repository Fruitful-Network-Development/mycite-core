"""Ports for portal-shell AWS-CSM mailbox onboarding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AwsCsmOnboardingProfileStorePort(Protocol):
    """Load/save canonical live profile JSON (``mycite.service_tool.aws_csm.profile.v1``)."""

    def load_profile(self, *, tenant_scope_id: str, profile_id: str) -> dict[str, Any] | None:
        ...

    def save_profile(self, *, tenant_scope_id: str, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist and return the stored document (read-after-write source)."""
        ...

    def list_profiles(self, *, tenant_scope_id: str | None = None) -> list[dict[str, Any]]:
        """Return operator profiles under ``tenant_scope_id`` (or every
        profile when ``None``). The auto-sync for FORWARD_TO_MAP_JSON
        passes ``None`` because the ses-forwarder env var is global
        across tenants — filtering by tenant would silently prune other
        tenants' routes on every sync."""
        ...


@runtime_checkable
class AwsCsmOnboardingCloudPort(Protocol):
    """External AWS / evidence IO; production adapters implement; tests use fakes."""

    def supplemental_profile_patch(self, action: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Top-level partial profile fragments (identity/smtp/verification/provider/workflow/inbound)."""
        ...

    def confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        """Fail closed unless confirmation evidence exists."""
        ...

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        """Backward-compatible alias for confirmation evidence checks."""
        ...

    def describe_profile_readiness(self, profile: dict[str, Any]) -> dict[str, Any]:
        """AWS-backed readiness/evidence summary used for operator-facing surfaces."""
        ...

    def describe_domain_status(self, domain_record: dict[str, Any]) -> dict[str, Any]:
        """AWS-backed Route53/SES/receipt-rule summary for domain onboarding."""
        ...

    def ensure_domain_identity(self, domain_record: dict[str, Any]) -> None:
        """Create or confirm the SES domain identity backing a domain onboarding record."""
        ...

    def sync_domain_dns(self, domain_record: dict[str, Any]) -> None:
        """Upsert Route53 MX and DKIM records for a domain onboarding record."""
        ...

    def ensure_domain_receipt_rule(self, domain_record: dict[str, Any]) -> None:
        """Create or update the bare-domain receipt rule used by portal-native capture."""
        ...

    def send_handoff_email(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Send the non-secret SMTP handoff instructions to the operator inbox target."""
        ...

    def read_handoff_secret(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Return ephemeral SMTP material for operator-only handoff without persisting it."""
        ...

    def sync_operator_forwarding_routes(
        self,
        *,
        profiles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Reconcile the per-recipient operator-mailbox forwarding state.

        Updates the ses-forwarder lambda's FORWARD_TO_MAP_JSON env var to
        reflect every operator profile whose ``inbound.receive_state`` is
        in ``{receive_pending, receive_configured, receive_operational}``
        and that carries a non-empty ``inbound.receive_routing_target``.

        Also ensures every domain represented in the route map has its
        ``portal-capture-<domain-slug>`` SES receipt rule's LambdaAction
        wired to ses-forwarder, and that ses-forwarder grants SES invoke
        from each such rule.

        Idempotent. Returns a structured result with ``status``,
        ``route_count``, ``tracked_recipients``, ``route_changed``,
        ``domains_wired``, ``permissions_added``.
        """
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
        "confirm_verified_attested",
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
    forwarding_sync: dict[str, Any] | None = None

    def to_local_audit_payload(self) -> dict[str, Any]:
        details: dict[str, Any] = {
            **self.command.to_audit_details(),
            "updated_sections": list(self.updated_sections),
        }
        if self.forwarding_sync is not None:
            details["forwarding_sync"] = dict(self.forwarding_sync)
        return {
            "event_type": "aws.csm_onboarding.accepted",
            "focus_subject": self.command.focus_subject,
            "shell_verb": "admin.aws.csm_onboarding",
            "details": details,
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
