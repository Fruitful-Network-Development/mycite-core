"""AWS peripheral contract — the surface every consumer (extensions,
portal surfaces, CLI) talks to.

There is one peripheral, one Protocol, one source of truth. Adapters
implement `AwsPeripheralPort`; tests can use fakes that satisfy the same
Protocol.

This is the canonical AWS contract surface. The legacy onboarding port
has been retired; all consumers now program against `AwsPeripheralPort`
and construct `AwsPeripheralCloudAdapter` directly.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class ForwardingRoutesSyncResult(TypedDict):
    status: str
    route_count: int
    tracked_recipients: list[str]
    route_changed: bool
    domains_wired: list[str]
    permissions_added: list[str]
    notes: list[str]


class ProfileReadiness(TypedDict):
    profile_id: str
    ses_identity_verified: bool
    dkim_verified: bool
    receipt_rule_present: bool
    forward_map_contains_send_as: bool
    lambda_permission_present: bool
    notes: list[str]


class DomainStatus(TypedDict):
    domain: str
    hosted_zone_id: str
    ses_identity_verified: bool
    dkim_verified: bool
    mx_present: bool
    spf_present: bool
    dmarc_present: bool
    dkim_cnames_present: int
    receipt_rule_present: bool
    notes: list[str]


class SesSendResult(TypedDict):
    status: str  # "sent"
    message_id: str
    configuration_set: str


class SesSendError(RuntimeError):
    """Raised when SES rejects a send call. Carries enough fields to log
    the failure without re-querying AWS."""

    def __init__(
        self,
        *,
        operation: str,
        identity: str,
        reason: str,
        aws_error_code: str = "",
        aws_request_id: str = "",
    ) -> None:
        self.operation = operation
        self.identity = identity
        self.reason = reason
        self.aws_error_code = aws_error_code
        self.aws_request_id = aws_request_id
        super().__init__(
            f"{operation} from={identity} code={aws_error_code or '?'} reason={reason}"
        )


@runtime_checkable
class AwsPeripheralPort(Protocol):
    """All AWS operations the portal + extensions need.

    Idempotent semantics: every mutating method returns a result dict
    shaped `{ok, changed, unchanged, errors}` (or the typed variant
    above). Re-running with no underlying change is a no-op.
    """

    def sync_operator_forwarding_routes(
        self,
        *,
        profiles: list[dict[str, Any]] | None = None,
        dry_run: bool = False,
    ) -> ForwardingRoutesSyncResult:
        ...

    def describe_profile_readiness(
        self,
        profile: dict[str, Any],
    ) -> ProfileReadiness:
        ...

    def describe_domain_status(self, domain: str) -> DomainStatus:
        ...

    def ensure_domain_identity(self, domain: str) -> dict[str, Any]:
        ...

    def sync_domain_dns(self, domain: str) -> dict[str, Any]:
        ...

    def ensure_domain_receipt_rule(self, domain: str) -> dict[str, Any]:
        ...

    def confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        ...

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        ...

    def send_email(
        self,
        *,
        aws_ses_profile: dict[str, Any],
        to: list[str],
        subject: str,
        body_text: str,
        body_html: str | None = None,
        reply_to: list[str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> SesSendResult:
        ...

    def send_raw_email(
        self,
        *,
        aws_ses_profile: dict[str, Any],
        destinations: list[str],
        raw_message_bytes: bytes,
    ) -> SesSendResult:
        ...


__all__ = [
    "AwsPeripheralPort",
    "DomainStatus",
    "ForwardingRoutesSyncResult",
    "ProfileReadiness",
    "SesSendError",
    "SesSendResult",
]
