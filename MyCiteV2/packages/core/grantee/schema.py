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
# Integration mode: "link" = a hosted PayPal donate link / PayPal.me URL (zero
# secret custody, no server mediation — the default); "rest" = server-mediated
# REST credentials (client_id/secret) for receipts + a donation ledger.
_VALID_PAYPAL_MODES = frozenset({"link", "rest"})
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
    webhook_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    environment: str = "sandbox"
    # "link" (default) = hosted donate link, no secret custody; "rest" = server
    # REST mediation. payment_link is the donate URL used in link mode.
    mode: str = "link"
    payment_link: str = ""

    def __post_init__(self) -> None:
        env = _as_text(self.environment).lower() or "sandbox"
        if env not in _VALID_PAYPAL_ENVIRONMENTS:
            raise ValueError(
                f"paypal.environment must be one of {sorted(_VALID_PAYPAL_ENVIRONMENTS)}; got {env!r}"
            )
        mode = _as_text(self.mode).lower() or "link"
        if mode not in _VALID_PAYPAL_MODES:
            raise ValueError(
                f"paypal.mode must be one of {sorted(_VALID_PAYPAL_MODES)}; got {mode!r}"
            )
        object.__setattr__(self, "environment", env)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "payment_link", _validate_url(self.payment_link, field_label="paypal.payment_link"))
        object.__setattr__(self, "webhook_url", _validate_url(self.webhook_url, field_label="paypal.webhook_url"))
        object.__setattr__(self, "webhook_id", _as_text(self.webhook_id))
        object.__setattr__(self, "client_id", _as_text(self.client_id))
        object.__setattr__(self, "client_secret", _as_text(self.client_secret))

    def to_dict(self) -> dict[str, Any]:
        return {
            "webhook_url": self.webhook_url,
            "webhook_id": self.webhook_id,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "environment": self.environment,
            "mode": self.mode,
            "payment_link": self.payment_link,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> PaypalConfig:
        data = payload if isinstance(payload, dict) else {}
        mode = _as_text(data.get("mode")).lower()
        if not mode:
            # Migrate legacy profiles: a stored secret => REST (the prior
            # behaviour); an otherwise-empty config => link (the new default).
            mode = "rest" if _as_text(data.get("client_secret")) else "link"
        return cls(
            webhook_url=_as_text(data.get("webhook_url")),
            webhook_id=_as_text(data.get("webhook_id")),
            client_id=_as_text(data.get("client_id")),
            client_secret=_as_text(data.get("client_secret")),
            environment=_as_text(data.get("environment")) or "sandbox",
            mode=mode,
            payment_link=_as_text(data.get("payment_link")),
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


_DEFAULT_ACKNOWLEDGEMENT_STATEMENT = (
    "No goods or services were provided in exchange for this contribution."
)


@dataclass(frozen=True)
class ReceiptConfig:
    """Organization legal identity for emailed donation acknowledgements.

    These are receipt-body facts — the org's legal name, EIN, tax status,
    mailing address, optional authorized signer, and the standard
    "no goods or services" statement — orthogonal to the payment processor
    (``PaypalConfig``) and to mail transport (``AwsSesConfig``). They drive
    the donor receipt sent after a successful REST-mode donation. In link
    mode PayPal emails its own confirmation and this is informational only.

    ``acknowledgement_statement`` is the single source mirrored to both the
    donate-page checkbox and the receipt body. Values are stored as entered
    (loose ``_as_text``); the EIN is display-only and not format-validated so
    operators can paste whatever the IRS letter shows.
    """

    legal_name: str = ""
    ein: str = ""
    tax_status: str = "501(c)(3)"
    mailing_address: str = ""
    signer_name: str = ""
    signer_title: str = ""
    acknowledgement_statement: str = _DEFAULT_ACKNOWLEDGEMENT_STATEMENT

    def __post_init__(self) -> None:
        object.__setattr__(self, "legal_name", _as_text(self.legal_name))
        object.__setattr__(self, "ein", _as_text(self.ein))
        object.__setattr__(self, "tax_status", _as_text(self.tax_status) or "501(c)(3)")
        object.__setattr__(self, "mailing_address", _as_text(self.mailing_address))
        object.__setattr__(self, "signer_name", _as_text(self.signer_name))
        object.__setattr__(self, "signer_title", _as_text(self.signer_title))
        object.__setattr__(
            self,
            "acknowledgement_statement",
            _as_text(self.acknowledgement_statement) or _DEFAULT_ACKNOWLEDGEMENT_STATEMENT,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "legal_name": self.legal_name,
            "ein": self.ein,
            "tax_status": self.tax_status,
            "mailing_address": self.mailing_address,
            "signer_name": self.signer_name,
            "signer_title": self.signer_title,
            "acknowledgement_statement": self.acknowledgement_statement,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> ReceiptConfig:
        data = payload if isinstance(payload, dict) else {}
        return cls(
            legal_name=_as_text(data.get("legal_name")),
            ein=_as_text(data.get("ein")),
            tax_status=_as_text(data.get("tax_status")),
            mailing_address=_as_text(data.get("mailing_address")),
            signer_name=_as_text(data.get("signer_name")),
            signer_title=_as_text(data.get("signer_title")),
            acknowledgement_statement=_as_text(data.get("acknowledgement_statement")),
        )


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
    receipt: ReceiptConfig | None = None
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
        if self.receipt is not None:
            out["receipt"] = self.receipt.to_dict()
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
            receipt=ReceiptConfig.from_dict(payload["receipt"]) if isinstance(payload.get("receipt"), dict) else None,
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
    "ReceiptConfig",
]
