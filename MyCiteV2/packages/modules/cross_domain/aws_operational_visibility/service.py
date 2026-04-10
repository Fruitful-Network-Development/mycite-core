from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from MyCiteV2.packages.modules.cross_domain.aws_operational_visibility.sender_domain_policy import (
    effective_allowed_send_domains,
    normalize_optional_domain_list,
    selected_verified_sender_allowed,
)
from MyCiteV2.packages.ports.aws_read_only_status import AwsReadOnlyStatusPort, AwsReadOnlyStatusRequest

FORBIDDEN_AWS_VISIBILITY_KEYS = frozenset(
    {
        "access_key",
        "access_key_id",
        "api_key",
        "aws_secret_access_key",
        "client_secret",
        "credential",
        "credential_blob",
        "password",
        "private_key",
        "private_key_pem",
        "runtime_secrets",
        "secret",
        "secret_access_key",
        "smtp_password",
        "smtp_username",
        "token",
    }
)

_ALLOWED_TOP_LEVEL_FIELDS = frozenset(
    {
        "tenant_scope_id",
        "mailbox_readiness",
        "smtp_state",
        "gmail_state",
        "verified_evidence_state",
        "selected_verified_sender",
        "allowed_send_domains",
        "canonical_newsletter_profile",
        "compatibility",
        "inbound_capture",
        "dispatch_health",
    }
)
_ALLOWED_PROFILE_FIELDS = frozenset(
    {
        "profile_id",
        "domain",
        "list_address",
        "selected_verified_sender",
        "delivery_mode",
    }
)
_ALLOWED_COMPATIBILITY_FIELDS = frozenset({"canonical_profile_matches_compatibility_inputs"})
_ALLOWED_INBOUND_CAPTURE_FIELDS = frozenset({"status", "last_capture_state"})
_ALLOWED_DISPATCH_HEALTH_FIELDS = frozenset({"status", "last_delivery_outcome", "pending_message_count"})

_ALLOWED_MAILBOX_READINESS = frozenset({"not_ready", "ready_for_gmail_handoff", "ready"})
_ALLOWED_SMTP_STATES = frozenset({"not_configured", "smtp_ready"})
_ALLOWED_GMAIL_STATES = frozenset({"not_started", "gmail_pending", "gmail_verified"})
_ALLOWED_VERIFIED_EVIDENCE = frozenset({"not_verified", "sender_selected", "verified_evidence_present"})
_ALLOWED_INBOUND_CAPTURE_STATES = frozenset({"not_ready", "ready", "warning"})
_ALLOWED_DISPATCH_HEALTH_STATES = frozenset({"unknown", "healthy", "warning"})
_ALLOWED_DELIVERY_MODES = frozenset({"inbound-mail-only"})

_COMPATIBILITY_WARNING = (
    "Compatibility-read newsletter metadata disagrees with the canonical newsletter operational profile."
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_allowed_fields(payload: dict[str, Any], *, field_name: str, allowed: frozenset[str]) -> None:
    extra_fields = sorted(set(payload.keys()) - allowed)
    if extra_fields:
        raise ValueError(f"{field_name} has unsupported fields: {extra_fields}")


def _reject_forbidden_keys(value: Any, *, field_name: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            token = _as_text(key)
            if not token:
                raise ValueError(f"{field_name} keys must be non-empty strings")
            if token.lower() in FORBIDDEN_AWS_VISIBILITY_KEYS:
                raise ValueError(f"{field_name}.{token} is forbidden in aws operational visibility")
            _reject_forbidden_keys(item, field_name=f"{field_name}.{token}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, field_name=f"{field_name}[{index}]")


def _normalize_state(value: object, *, field_name: str, allowed: frozenset[str]) -> str:
    token = _as_text(value).lower()
    if token not in allowed:
        supported = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {supported}")
    return token


def _normalize_email(value: object, *, field_name: str) -> str:
    token = _as_text(value).lower()
    if not token or "@" not in token or token.startswith("@") or token.endswith("@"):
        raise ValueError(f"{field_name} must be an email-like value")
    return token


def _normalize_domain_token(value: object, *, field_name: str) -> str:
    token = _as_text(value).lower()
    if not token or "." not in token:
        raise ValueError(f"{field_name} must be a domain-like value")
    return token


def _normalize_positive_count(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a non-negative integer") from None
    if number < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return number


@dataclass(frozen=True)
class CanonicalNewsletterOperationalProfile:
    profile_id: str
    domain: str
    list_address: str
    selected_verified_sender: str
    delivery_mode: str

    def __post_init__(self) -> None:
        profile_id = _as_text(self.profile_id)
        domain = _as_text(self.domain).lower()
        if not profile_id:
            raise ValueError("canonical_newsletter_profile.profile_id is required")
        if not domain or "." not in domain:
            raise ValueError("canonical_newsletter_profile.domain must be a domain-like value")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(
            self,
            "list_address",
            _normalize_email(self.list_address, field_name="canonical_newsletter_profile.list_address"),
        )
        object.__setattr__(
            self,
            "selected_verified_sender",
            _normalize_email(
                self.selected_verified_sender,
                field_name="canonical_newsletter_profile.selected_verified_sender",
            ),
        )
        object.__setattr__(
            self,
            "delivery_mode",
            _normalize_state(
                self.delivery_mode,
                field_name="canonical_newsletter_profile.delivery_mode",
                allowed=_ALLOWED_DELIVERY_MODES,
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "profile_id": self.profile_id,
            "domain": self.domain,
            "list_address": self.list_address,
            "selected_verified_sender": self.selected_verified_sender,
            "delivery_mode": self.delivery_mode,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CanonicalNewsletterOperationalProfile":
        if not isinstance(payload, dict):
            raise ValueError("canonical_newsletter_profile must be a dict")
        _require_allowed_fields(
            payload,
            field_name="canonical_newsletter_profile",
            allowed=_ALLOWED_PROFILE_FIELDS,
        )
        _reject_forbidden_keys(payload, field_name="canonical_newsletter_profile")
        return cls(
            profile_id=payload.get("profile_id"),
            domain=payload.get("domain"),
            list_address=payload.get("list_address"),
            selected_verified_sender=payload.get("selected_verified_sender"),
            delivery_mode=payload.get("delivery_mode"),
        )


@dataclass(frozen=True)
class AwsReadOnlyOperationalVisibility:
    tenant_scope_id: str
    mailbox_readiness: str
    smtp_state: str
    gmail_state: str
    verified_evidence_state: str
    selected_verified_sender: str
    allowed_send_domains: tuple[str, ...]
    canonical_newsletter_profile: CanonicalNewsletterOperationalProfile
    compatibility_warnings: tuple[str, ...]
    inbound_capture: dict[str, str]
    dispatch_health: dict[str, Any]

    def __post_init__(self) -> None:
        tenant_scope_id = _as_text(self.tenant_scope_id)
        if not tenant_scope_id:
            raise ValueError("aws_operational_visibility.tenant_scope_id is required")
        object.__setattr__(self, "tenant_scope_id", tenant_scope_id)
        object.__setattr__(
            self,
            "mailbox_readiness",
            _normalize_state(
                self.mailbox_readiness,
                field_name="aws_operational_visibility.mailbox_readiness",
                allowed=_ALLOWED_MAILBOX_READINESS,
            ),
        )
        object.__setattr__(
            self,
            "smtp_state",
            _normalize_state(
                self.smtp_state,
                field_name="aws_operational_visibility.smtp_state",
                allowed=_ALLOWED_SMTP_STATES,
            ),
        )
        object.__setattr__(
            self,
            "gmail_state",
            _normalize_state(
                self.gmail_state,
                field_name="aws_operational_visibility.gmail_state",
                allowed=_ALLOWED_GMAIL_STATES,
            ),
        )
        object.__setattr__(
            self,
            "verified_evidence_state",
            _normalize_state(
                self.verified_evidence_state,
                field_name="aws_operational_visibility.verified_evidence_state",
                allowed=_ALLOWED_VERIFIED_EVIDENCE,
            ),
        )
        object.__setattr__(
            self,
            "selected_verified_sender",
            _normalize_email(
                self.selected_verified_sender,
                field_name="aws_operational_visibility.selected_verified_sender",
            ),
        )
        if isinstance(self.canonical_newsletter_profile, CanonicalNewsletterOperationalProfile):
            profile = self.canonical_newsletter_profile
        elif isinstance(self.canonical_newsletter_profile, dict):
            profile = CanonicalNewsletterOperationalProfile.from_dict(self.canonical_newsletter_profile)
        else:
            raise ValueError(
                "aws_operational_visibility.canonical_newsletter_profile must be a profile or dict"
            )
        object.__setattr__(self, "canonical_newsletter_profile", profile)
        if not isinstance(self.allowed_send_domains, tuple):
            raise ValueError("aws_operational_visibility.allowed_send_domains must be a tuple of domains")
        normalized_allowed = tuple(
            _normalize_domain_token(
                item,
                field_name=f"aws_operational_visibility.allowed_send_domains[{index}]",
            )
            for index, item in enumerate(self.allowed_send_domains)
        )
        object.__setattr__(self, "allowed_send_domains", tuple(sorted(set(normalized_allowed))))
        object.__setattr__(
            self,
            "compatibility_warnings",
            tuple(_as_text(item) for item in self.compatibility_warnings if _as_text(item)),
        )
        object.__setattr__(self, "inbound_capture", dict(self.inbound_capture))
        object.__setattr__(self, "dispatch_health", dict(self.dispatch_health))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_scope_id": self.tenant_scope_id,
            "mailbox_readiness": self.mailbox_readiness,
            "smtp_state": self.smtp_state,
            "gmail_state": self.gmail_state,
            "verified_evidence_state": self.verified_evidence_state,
            "selected_verified_sender": self.selected_verified_sender,
            "allowed_send_domains": list(self.allowed_send_domains),
            "canonical_newsletter_profile": self.canonical_newsletter_profile.to_dict(),
            "compatibility_warnings": list(self.compatibility_warnings),
            "inbound_capture": dict(self.inbound_capture),
            "dispatch_health": dict(self.dispatch_health),
        }


def normalize_aws_operational_visibility(
    payload: AwsReadOnlyOperationalVisibility | dict[str, Any],
) -> AwsReadOnlyOperationalVisibility:
    if isinstance(payload, AwsReadOnlyOperationalVisibility):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("aws_operational_visibility must be a dict")
    _reject_forbidden_keys(payload, field_name="aws_operational_visibility")
    _require_allowed_fields(
        payload,
        field_name="aws_operational_visibility",
        allowed=_ALLOWED_TOP_LEVEL_FIELDS,
    )

    profile = CanonicalNewsletterOperationalProfile.from_dict(payload.get("canonical_newsletter_profile"))

    if "allowed_send_domains" not in payload or payload.get("allowed_send_domains") is None:
        secondary_domains: tuple[str, ...] = ()
    else:
        secondary_domains = normalize_optional_domain_list(
            payload.get("allowed_send_domains"),
            field_name="aws_operational_visibility.allowed_send_domains",
        )
    merged_allowed = effective_allowed_send_domains(primary_domain=profile.domain, extra_domains=secondary_domains)

    compatibility = payload.get("compatibility") or {}
    if not isinstance(compatibility, dict):
        raise ValueError("aws_operational_visibility.compatibility must be a dict")
    _require_allowed_fields(
        compatibility,
        field_name="aws_operational_visibility.compatibility",
        allowed=_ALLOWED_COMPATIBILITY_FIELDS,
    )
    matches_inputs = bool(compatibility.get("canonical_profile_matches_compatibility_inputs", True))
    compatibility_warnings = () if matches_inputs else (_COMPATIBILITY_WARNING,)

    inbound_capture = payload.get("inbound_capture") or {}
    if not isinstance(inbound_capture, dict):
        raise ValueError("aws_operational_visibility.inbound_capture must be a dict")
    _require_allowed_fields(
        inbound_capture,
        field_name="aws_operational_visibility.inbound_capture",
        allowed=_ALLOWED_INBOUND_CAPTURE_FIELDS,
    )
    normalized_inbound_capture = {
        "status": _normalize_state(
            inbound_capture.get("status", "not_ready"),
            field_name="aws_operational_visibility.inbound_capture.status",
            allowed=_ALLOWED_INBOUND_CAPTURE_STATES,
        ),
        "last_capture_state": _as_text(inbound_capture.get("last_capture_state")) or "none",
    }

    dispatch_health = payload.get("dispatch_health") or {}
    if not isinstance(dispatch_health, dict):
        raise ValueError("aws_operational_visibility.dispatch_health must be a dict")
    _require_allowed_fields(
        dispatch_health,
        field_name="aws_operational_visibility.dispatch_health",
        allowed=_ALLOWED_DISPATCH_HEALTH_FIELDS,
    )
    normalized_dispatch_health = {
        "status": _normalize_state(
            dispatch_health.get("status", "unknown"),
            field_name="aws_operational_visibility.dispatch_health.status",
            allowed=_ALLOWED_DISPATCH_HEALTH_STATES,
        ),
        "last_delivery_outcome": _as_text(dispatch_health.get("last_delivery_outcome")) or "unknown",
        "pending_message_count": _normalize_positive_count(
            dispatch_health.get("pending_message_count", 0),
            field_name="aws_operational_visibility.dispatch_health.pending_message_count",
        ),
    }

    selected_verified_sender = _normalize_email(
        payload.get("selected_verified_sender"),
        field_name="aws_operational_visibility.selected_verified_sender",
    )
    if selected_verified_sender != profile.selected_verified_sender:
        raise ValueError(
            "aws_operational_visibility.selected_verified_sender must match canonical_newsletter_profile.selected_verified_sender"
        )
    if merged_allowed and not selected_verified_sender_allowed(selected_verified_sender, merged_allowed):
        raise ValueError(
            "aws_operational_visibility.selected_verified_sender must use a domain listed in allowed_send_domains"
        )

    return AwsReadOnlyOperationalVisibility(
        tenant_scope_id=payload.get("tenant_scope_id"),
        mailbox_readiness=payload.get("mailbox_readiness"),
        smtp_state=payload.get("smtp_state"),
        gmail_state=payload.get("gmail_state"),
        verified_evidence_state=payload.get("verified_evidence_state"),
        selected_verified_sender=selected_verified_sender,
        allowed_send_domains=merged_allowed,
        canonical_newsletter_profile=profile,
        compatibility_warnings=compatibility_warnings,
        inbound_capture=normalized_inbound_capture,
        dispatch_health=normalized_dispatch_health,
    )


class AwsOperationalVisibilityService:
    def __init__(self, aws_status_port: AwsReadOnlyStatusPort) -> None:
        self._aws_status_port = aws_status_port

    def read_surface(self, tenant_scope_id: object) -> AwsReadOnlyOperationalVisibility | None:
        request = AwsReadOnlyStatusRequest(tenant_scope_id=_as_text(tenant_scope_id))
        result = self._aws_status_port.read_aws_read_only_status(request)
        if result.source is None:
            return None
        source_payload = result.source.payload
        if source_payload.get("tenant_scope_id") and _as_text(source_payload.get("tenant_scope_id")) != request.tenant_scope_id:
            return None
        normalized_payload = dict(source_payload)
        normalized_payload["tenant_scope_id"] = request.tenant_scope_id
        return normalize_aws_operational_visibility(normalized_payload)
