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


class CostBreakdown(TypedDict):
    """Per-grantee or per-account cost slice over a date range.

    `by_service` keys are AWS service names as returned by Cost Explorer
    (e.g. "Amazon Simple Email Service", "Amazon Route 53").
    `currency` and `grand_total` reflect the SUM of UnblendedCost across
    `by_service`. `period` is a (start, end) tuple of ISO dates.
    """
    currency: str
    grand_total: str            # decimal-as-string, exact AWS format
    by_service: dict[str, str]  # service_name -> decimal-as-string
    period_start: str           # ISO date
    period_end: str             # ISO date
    granularity: str            # "DAILY" | "MONTHLY"


class TagOperationResult(TypedDict):
    """Result of a tagging call. `failed_arns` carries any ARN that the
    API rejected (per-resource failures don't fail the whole call)."""
    ok: bool
    tagged_arns: list[str]
    failed_arns: list[dict[str, str]]  # [{arn, error_code, error_message}]


class CostLineItem(TypedDict):
    """One row in a Cost Explorer GroupBy response.

    `keys` is the tuple of group-dimension values (e.g. ("Amazon Elastic
    Compute Cloud - Compute", "BoxUsage:t3.medium")) — order matches the
    `group_by` argument. `amount` is UnblendedCost as decimal-string.
    `usage_quantity` + `usage_unit` are populated when the underlying
    line has a UsageQuantity metric (compute hours, GB-month, requests);
    otherwise both are empty strings.
    """
    keys: tuple[str, ...]
    amount: str
    currency: str
    usage_quantity: str
    usage_unit: str


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

    # ---- Tagging + cost attribution (tolling extension surface) -------

    def tag_resource(
        self,
        *,
        arns: list[str],
        tags: dict[str, str],
    ) -> TagOperationResult:
        """Apply a set of tags to one or more AWS resource ARNs.

        Backed by the Resource Groups Tagging API. Idempotent — running
        with the same arns + tags is a no-op. Per-resource failures are
        reported in the result rather than raising, so callers can
        process partial successes.
        """
        ...

    def get_costs_by_grantee(
        self,
        *,
        msn_id: str,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> CostBreakdown:
        """Cost Explorer GetCostAndUsage filtered by Tag:msn_id, grouped
        by SERVICE. `start`/`end` are ISO dates; range is half-open
        per AWS convention. Returns the grantee's full cost slice for
        the period — caller adds bandwidth-share attribution from
        nginx access logs separately."""
        ...

    def get_costs_overview(
        self,
        *,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> dict[str, CostBreakdown]:
        """Same Cost Explorer query grouped by Tag:msn_id — returns
        every tagged grantee's cost slice in one round trip. Result
        keys are msn_id values; an empty string key holds the
        un-tagged remainder."""
        ...

    def get_costs_breakdown(
        self,
        *,
        start: str,
        end: str,
        group_by: tuple[str, ...] = ("SERVICE", "USAGE_TYPE"),
        tag_filter: dict[str, list[str]] | None = None,
        service_filter: list[str] | None = None,
        granularity: str = "MONTHLY",
    ) -> list[CostLineItem]:
        """Fine-grained Cost Explorer breakdown.

        `group_by` accepts up to 2 entries (CE limit). Each entry is
        either a DIMENSION name (SERVICE, USAGE_TYPE, REGION, …) or the
        literal string ``"TAG:<key>"`` to group by a tag value.

        `tag_filter` is a `{Key, Values}` dict that becomes a CE
        ``Filter.Tags`` clause when set. `service_filter` constrains
        to specific SERVICE dimension values.

        Returns one `CostLineItem` per non-empty group, summed across
        the time window. Also returns the line's UsageQuantity when AWS
        emits one (compute hours, GB-month, requests). Used by the
        tolling ledger to itemize every billable line.
        """
        ...

    def get_untagged_residue(
        self,
        *,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> CostBreakdown:
        """The slice of account cost that no `msn_id` tag attributed.

        Wraps `get_costs_overview` and returns the breakdown registered
        under the empty-string key. Surfaced by the tolling ledger as
        its own `residue` line item rather than being silently absorbed
        into FND."""
        ...

    def get_route53_registrar_renewal_lines(
        self,
        *,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> list[CostLineItem]:
        """One row per domain-registration renewal posted in the window.

        Filters Cost Explorer by SERVICE=`Amazon Registrar`, grouped by
        SERVICE+USAGE_TYPE so each domain's renewal surfaces separately.
        Amortization (1/12 per month for annual renewals) is computed
        downstream in the tolling extension, not here."""
        ...


__all__ = [
    "AwsPeripheralPort",
    "CostBreakdown",
    "CostLineItem",
    "DomainStatus",
    "ForwardingRoutesSyncResult",
    "ProfileReadiness",
    "SesSendError",
    "SesSendResult",
    "TagOperationResult",
]
