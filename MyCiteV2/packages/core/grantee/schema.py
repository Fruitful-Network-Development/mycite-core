"""GranteeProfile dataclass and sub-configs.

A grantee profile carries the operator-mutable fields that drive Utilities
extensions: identity (label, short_name, domains, users), PayPal credentials
+ environment, AWS SES identity + SMTP credentials, and newsletter sender
configuration. All sub-configs are optional so legacy grantee files that
predate Phase 8 of TASK-PORTAL-SIMPLIFICATION-2026-05-14 still load cleanly.

The dataclass is pure (no I/O). Filesystem round-trip lives in store.py.
Validation rejects malformed values at construction time so callers can rely
on the invariants once a profile is in hand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

GRANTEE_PROFILE_SCHEMA = "mycite.v2.grantee.profile.v1"

_VALID_PAYPAL_ENVIRONMENTS = frozenset({"sandbox", "live"})
_URL_PREFIX_RE = re.compile(r"^https?://", re.IGNORECASE)
# Loose email shape — defers strict RFC 5322 to the SMTP layer.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _validate_url(value: str, *, field_label: str) -> str:
    text = _as_text(value)
    if not text:
        return ""
    if not _URL_PREFIX_RE.match(text):
        raise ValueError(f"{field_label} must start with http:// or https://; got {text!r}")
    return text


def _validate_email(value: str, *, field_label: str) -> str:
    text = _as_text(value)
    if not text:
        return ""
    if not _EMAIL_RE.match(text):
        raise ValueError(f"{field_label} must look like an email address; got {text!r}")
    return text


@dataclass(frozen=True)
class PaypalConfig:
    webhook_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    environment: str = "sandbox"

    def __post_init__(self) -> None:
        env = _as_text(self.environment).lower() or "sandbox"
        if env not in _VALID_PAYPAL_ENVIRONMENTS:
            raise ValueError(
                f"paypal.environment must be one of {sorted(_VALID_PAYPAL_ENVIRONMENTS)}; got {env!r}"
            )
        object.__setattr__(self, "environment", env)
        object.__setattr__(self, "webhook_url", _validate_url(self.webhook_url, field_label="paypal.webhook_url"))
        object.__setattr__(self, "client_id", _as_text(self.client_id))
        object.__setattr__(self, "client_secret", _as_text(self.client_secret))

    def to_dict(self) -> dict[str, Any]:
        return {
            "webhook_url": self.webhook_url,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "environment": self.environment,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> PaypalConfig:
        data = payload if isinstance(payload, dict) else {}
        return cls(
            webhook_url=_as_text(data.get("webhook_url")),
            client_id=_as_text(data.get("client_id")),
            client_secret=_as_text(data.get("client_secret")),
            environment=_as_text(data.get("environment")) or "sandbox",
        )


@dataclass(frozen=True)
class AwsSesConfig:
    region: str = ""
    identity: str = ""
    smtp_username: str = ""
    smtp_password: str = ""
    from_address: str = ""
    from_name: str = ""
    configuration_set: str = ""
    reply_to: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "region", _as_text(self.region))
        object.__setattr__(self, "identity", _validate_email(self.identity, field_label="aws_ses.identity"))
        object.__setattr__(self, "smtp_username", _as_text(self.smtp_username))
        object.__setattr__(self, "smtp_password", _as_text(self.smtp_password))
        object.__setattr__(self, "from_address", _as_text(self.from_address))
        object.__setattr__(self, "from_name", _as_text(self.from_name))
        object.__setattr__(self, "configuration_set", _as_text(self.configuration_set))
        object.__setattr__(self, "reply_to", _as_text(self.reply_to))

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "identity": self.identity,
            "smtp_username": self.smtp_username,
            "smtp_password": self.smtp_password,
            "from_address": self.from_address,
            "from_name": self.from_name,
            "configuration_set": self.configuration_set,
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> AwsSesConfig:
        data = payload if isinstance(payload, dict) else {}
        return cls(
            region=_as_text(data.get("region")),
            identity=_as_text(data.get("identity")),
            smtp_username=_as_text(data.get("smtp_username")),
            smtp_password=_as_text(data.get("smtp_password")),
            from_address=_as_text(data.get("from_address")),
            from_name=_as_text(data.get("from_name")),
            configuration_set=_as_text(data.get("configuration_set")),
            reply_to=_as_text(data.get("reply_to")),
        )


@dataclass(frozen=True)
class NewsletterConfig:
    selected_sender_address: str = ""
    sender_display_name: str = ""
    reply_to: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selected_sender_address",
            _validate_email(self.selected_sender_address, field_label="newsletter.selected_sender_address"),
        )
        object.__setattr__(self, "sender_display_name", _as_text(self.sender_display_name))
        object.__setattr__(self, "reply_to", _validate_email(self.reply_to, field_label="newsletter.reply_to"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_sender_address": self.selected_sender_address,
            "sender_display_name": self.sender_display_name,
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> NewsletterConfig:
        data = payload if isinstance(payload, dict) else {}
        return cls(
            selected_sender_address=_as_text(data.get("selected_sender_address")),
            sender_display_name=_as_text(data.get("sender_display_name")),
            reply_to=_as_text(data.get("reply_to")),
        )


@dataclass(frozen=True)
class ConnectConfig:
    """Phase 17a: per-grantee Connect-form configuration.

    The Connect form (separate from the Newsletter form) lets a
    website visitor send a message that the FND portal forwards to
    ``forward_to_email`` via SES. The submission also lands in the
    grantee's contact log as an unsubscribed contact tagged with
    ``source=connect_form`` so the operator builds a lead list.
    """

    forward_to_email: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "forward_to_email",
            _validate_email(self.forward_to_email, field_label="connect.forward_to_email"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"forward_to_email": self.forward_to_email}

    @classmethod
    def from_dict(cls, payload: Any) -> ConnectConfig:
        data = payload if isinstance(payload, dict) else {}
        return cls(forward_to_email=_as_text(data.get("forward_to_email")))


@dataclass(frozen=True)
class GranteeProfile:
    msn_id: str
    label: str = ""
    short_name: str = ""
    domains: tuple[str, ...] = ()
    users: tuple[str, ...] = ()
    paypal: PaypalConfig | None = None
    aws_ses: AwsSesConfig | None = None
    newsletter: NewsletterConfig | None = None
    connect: ConnectConfig | None = None
    schema: str = field(default=GRANTEE_PROFILE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        msn = _as_text(self.msn_id)
        if not msn:
            raise ValueError("grantee_profile.msn_id is required")
        object.__setattr__(self, "msn_id", msn)
        object.__setattr__(self, "label", _as_text(self.label))
        object.__setattr__(self, "short_name", _as_text(self.short_name))
        object.__setattr__(self, "domains", tuple(_as_text(d) for d in self.domains if _as_text(d)))
        object.__setattr__(self, "users", tuple(_as_text(u) for u in self.users if _as_text(u)))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "msn_id": self.msn_id,
            "label": self.label,
            "short_name": self.short_name,
            "domains": list(self.domains),
            "users": list(self.users),
        }
        # Sub-configs are emitted only when non-None so legacy file shapes
        # stay byte-identical when no credentials are configured. Phase 9's
        # save route always populates them once the operator edits the form.
        if self.paypal is not None:
            out["paypal"] = self.paypal.to_dict()
        if self.aws_ses is not None:
            out["aws_ses"] = self.aws_ses.to_dict()
        if self.newsletter is not None:
            out["newsletter"] = self.newsletter.to_dict()
        if self.connect is not None:
            out["connect"] = self.connect.to_dict()
        return out

    @classmethod
    def from_dict(cls, payload: Any) -> GranteeProfile:
        if not isinstance(payload, dict):
            raise ValueError("grantee_profile payload must be a dict")
        declared_schema = _as_text(payload.get("schema"))
        if declared_schema and declared_schema != GRANTEE_PROFILE_SCHEMA:
            raise ValueError(
                f"grantee_profile.schema must be {GRANTEE_PROFILE_SCHEMA!r}; got {declared_schema!r}"
            )
        return cls(
            msn_id=_as_text(payload.get("msn_id")),
            label=_as_text(payload.get("label")),
            short_name=_as_text(payload.get("short_name")),
            domains=tuple(_as_text(d) for d in (payload.get("domains") or ())),
            users=tuple(_as_text(u) for u in (payload.get("users") or ())),
            paypal=PaypalConfig.from_dict(payload["paypal"]) if isinstance(payload.get("paypal"), dict) else None,
            aws_ses=AwsSesConfig.from_dict(payload["aws_ses"]) if isinstance(payload.get("aws_ses"), dict) else None,
            newsletter=NewsletterConfig.from_dict(payload["newsletter"]) if isinstance(payload.get("newsletter"), dict) else None,
            connect=ConnectConfig.from_dict(payload["connect"]) if isinstance(payload.get("connect"), dict) else None,
        )

    def with_paypal(self, paypal: PaypalConfig | None) -> GranteeProfile:
        """Return a copy of this profile with paypal sub-config replaced.

        Used by the runtime to hydrate paypal from the legacy sidecar without
        mutating the on-disk grantee JSON.
        """
        return replace(self, paypal=paypal)


__all__ = [
    "GRANTEE_PROFILE_SCHEMA",
    "AwsSesConfig",
    "ConnectConfig",
    "GranteeProfile",
    "NewsletterConfig",
    "PaypalConfig",
]
