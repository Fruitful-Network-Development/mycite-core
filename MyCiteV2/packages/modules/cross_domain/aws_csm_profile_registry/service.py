from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from MyCiteV2.packages.modules.shared import as_dict, as_text, utc_now_iso
from MyCiteV2.packages.ports.aws_csm_profile_registry import AwsCsmProfileRegistryPort

LIVE_AWS_PROFILE_SCHEMA = "mycite.service_tool.aws_csm.profile.v1"
_MAILBOX_LOCAL_PART_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._+-]{0,62}[a-z0-9])?$")
_ALLOWED_HANDOFF_PROVIDERS = frozenset({"gmail", "outlook", "yahoo", "proofpoint", "generic_manual"})


def _handoff_provider_from_email(email: str) -> str:
    token = _normalized_email(email, field_name="aws_csm_profile_registry.handoff_provider_email")
    domain = token.split("@", 1)[1]
    if domain in {"gmail.com", "googlemail.com"}:
        return "gmail"
    if domain in {"outlook.com", "hotmail.com", "live.com", "msn.com"}:
        return "outlook"
    if domain in {"yahoo.com", "rocketmail.com", "ymail.com"}:
        return "yahoo"
    if domain.endswith("proofpoint.com"):
        return "proofpoint"
    return "generic_manual"


def _normalized_handoff_provider(value: object, *, allow_empty: bool = False) -> str:
    token = as_text(value).lower()
    if not token and allow_empty:
        return ""
    if token not in _ALLOWED_HANDOFF_PROVIDERS:
        allowed = ", ".join(sorted(_ALLOWED_HANDOFF_PROVIDERS))
        raise ValueError(
            f"aws_csm_profile_registry.handoff_provider must be one of: {allowed}"
        )
    return token


def _inferred_handoff_provider(*emails: str) -> str:
    for email in emails:
        if not as_text(email):
            continue
        try:
            return _handoff_provider_from_email(email)
        except ValueError:
            continue
    return "generic_manual"


def _normalized_domain(value: object, *, field_name: str) -> str:
    token = as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    if not token or "." not in token or any(ch.isspace() for ch in token):
        raise ValueError(f"{field_name} must be a domain-like value")
    return token


def _normalized_email(value: object, *, field_name: str) -> str:
    token = as_text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        raise ValueError(f"{field_name} must be an email-like value")
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        raise ValueError(f"{field_name} must be an email-like value")
    return token


def _normalized_mailbox_local_part(value: object) -> str:
    token = as_text(value).lower()
    if not _MAILBOX_LOCAL_PART_PATTERN.match(token):
        raise ValueError(
            "aws_csm_profile_registry.mailbox_local_part must use lowercase mailbox characters"
        )
    return token


def _normalized_role(value: object) -> str:
    token = as_text(value).lower() or "operator"
    if not token:
        return "operator"
    return token


@dataclass(frozen=True)
class AwsCsmCreateProfileCommand:
    domain: str
    mailbox_local_part: str
    single_user_email: str
    operator_inbox_target: str = ""
    role: str = "operator"
    handoff_provider: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "domain",
            _normalized_domain(self.domain, field_name="aws_csm_profile_registry.domain"),
        )
        object.__setattr__(
            self,
            "mailbox_local_part",
            _normalized_mailbox_local_part(self.mailbox_local_part),
        )
        object.__setattr__(
            self,
            "single_user_email",
            _normalized_email(
                self.single_user_email,
                field_name="aws_csm_profile_registry.single_user_email",
            ),
        )
        inbox_target = self.operator_inbox_target or self.single_user_email
        object.__setattr__(
            self,
            "operator_inbox_target",
            _normalized_email(
                inbox_target,
                field_name="aws_csm_profile_registry.operator_inbox_target",
            ),
        )
        object.__setattr__(self, "role", _normalized_role(self.role))
        explicit_provider = _normalized_handoff_provider(self.handoff_provider, allow_empty=True)
        object.__setattr__(
            self,
            "handoff_provider",
            explicit_provider
            or _inferred_handoff_provider(self.operator_inbox_target, self.single_user_email),
        )

    @property
    def send_as_email(self) -> str:
        return f"{self.mailbox_local_part}@{self.domain}"

    @property
    def profile_id(self) -> str:
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "mailbox_local_part": self.mailbox_local_part,
            "single_user_email": self.single_user_email,
            "operator_inbox_target": self.operator_inbox_target,
            "role": self.role,
            "handoff_provider": self.handoff_provider,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AwsCsmCreateProfileCommand":
        if not isinstance(payload, dict):
            raise ValueError("aws_csm_profile_registry.create_profile must be a dict")
        return cls(
            domain=payload.get("domain"),
            mailbox_local_part=payload.get("mailbox_local_part"),
            single_user_email=payload.get("single_user_email"),
            operator_inbox_target=payload.get("operator_inbox_target") or "",
            role=payload.get("role") or "operator",
            handoff_provider=payload.get("handoff_provider") or "",
        )


@dataclass(frozen=True)
class AwsCsmCreateProfileOutcome:
    profile_id: str
    domain: str
    tenant_id: str
    created_profile: dict[str, Any]

    @property
    def send_as_email(self) -> str:
        identity = as_dict(self.created_profile.get("identity"))
        return as_text(identity.get("send_as_email")).lower()

    @property
    def single_user_email(self) -> str:
        identity = as_dict(self.created_profile.get("identity"))
        return as_text(identity.get("single_user_email")).lower()

    @property
    def operator_inbox_target(self) -> str:
        identity = as_dict(self.created_profile.get("identity"))
        return as_text(identity.get("operator_inbox_target")).lower()

    @property
    def handoff_provider(self) -> str:
        identity = as_dict(self.created_profile.get("identity"))
        provider = as_dict(self.created_profile.get("provider"))
        return (
            as_text(identity.get("handoff_provider")).lower()
            or as_text(provider.get("handoff_provider")).lower()
            or "generic_manual"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "domain": self.domain,
            "tenant_id": self.tenant_id,
            "send_as_email": self.send_as_email,
            "single_user_email": self.single_user_email,
            "operator_inbox_target": self.operator_inbox_target,
            "handoff_provider": self.handoff_provider,
            "created_profile": dict(self.created_profile),
        }


class AwsCsmProfileRegistryService:
    def __init__(self, registry_port: AwsCsmProfileRegistryPort) -> None:
        self._registry_port = registry_port

    def create_profile(
        self,
        payload: AwsCsmCreateProfileCommand | dict[str, Any],
    ) -> AwsCsmCreateProfileOutcome:
        command = (
            payload
            if isinstance(payload, AwsCsmCreateProfileCommand)
            else AwsCsmCreateProfileCommand.from_dict(payload)
        )
        seed = self._registry_port.resolve_domain_seed(domain=command.domain)
        if not isinstance(seed, dict):
            raise ValueError(
                f"AWS-CSM cannot add a user for {command.domain} because no seed tenant metadata exists."
            )
        tenant_id = as_text(seed.get("tenant_id")).lower()
        if not tenant_id:
            raise ValueError(
                f"AWS-CSM cannot add a user for {command.domain} because the seed tenant_id is missing."
            )
        region = as_text(seed.get("region")) or "us-east-1"
        profile_id = f"aws-csm.{tenant_id}.{command.mailbox_local_part}"
        send_as_email = command.send_as_email
        existing_profiles = list(self._registry_port.list_profiles())
        existing_profile_ids = set()
        existing_send_as = set()
        for profile in existing_profiles:
            identity = as_dict(profile.get("identity"))
            existing_profile_ids.add(as_text(identity.get("profile_id")).lower())
            existing_send_as.add(as_text(identity.get("send_as_email")).lower())
        if profile_id.lower() in existing_profile_ids:
            raise ValueError(f"AWS-CSM profile_id already exists: {profile_id}")
        if send_as_email.lower() in existing_send_as:
            raise ValueError(f"AWS-CSM send-as email already exists: {send_as_email}")
        seeded_provider = as_dict(seed.get("provider"))
        aws_identity_status = as_text(seeded_provider.get("aws_ses_identity_status"))
        provider_last_checked_at = as_text(seeded_provider.get("last_checked_at"))
        created_profile = self._registry_port.create_profile(
            profile_id=profile_id,
            payload={
                "schema": LIVE_AWS_PROFILE_SCHEMA,
                "identity": {
                    "profile_id": profile_id,
                    "tenant_id": tenant_id,
                    "domain": command.domain,
                    "region": region,
                    "mailbox_local_part": command.mailbox_local_part,
                    "role": command.role,
                    "profile_kind": "mailbox",
                    "single_user_msn_id": "",
                    "single_user_email": command.single_user_email,
                    "operator_inbox_target": command.operator_inbox_target,
                    "handoff_provider": command.handoff_provider,
                    "send_as_email": send_as_email,
                },
                "smtp": {
                    "host": f"email-smtp.{region}.amazonaws.com",
                    "port": "587",
                    "username": "",
                    "credentials_source": "operator_managed",
                    "credentials_secret_name": f"aws-cms/smtp/{tenant_id}.{command.mailbox_local_part}",
                    "credentials_secret_state": "missing",
                    "send_as_email": send_as_email,
                    "local_part": command.mailbox_local_part,
                    "handoff_provider": command.handoff_provider,
                    "forward_to_email": command.operator_inbox_target,
                    "forwarding_status": "not_configured",
                    "handoff_ready": False,
                },
                "verification": {
                    "status": "not_started",
                    "code": "",
                    "link": "",
                    "email_received_at": "",
                    "verified_at": "",
                    "portal_state": "not_started",
                },
                "provider": {
                    "handoff_provider": command.handoff_provider,
                    "send_as_provider_status": "not_started",
                    "gmail_send_as_status": "not_started",
                    "aws_ses_identity_status": aws_identity_status,
                    "last_checked_at": provider_last_checked_at,
                },
                "workflow": {
                    "schema": "mycite.service_tool.aws_csm.onboarding.v1",
                    "flow": "mailbox_send_as",
                    "initiated": True,
                    "initiated_at": utc_now_iso(seconds_precision=True),
                    "lifecycle_state": "draft",
                    "handoff_provider": command.handoff_provider,
                    "handoff_status": "not_started",
                    "is_ready_for_user_handoff": False,
                },
                "inbound": {
                    "receive_routing_target": command.operator_inbox_target,
                    "receive_state": "receive_unconfigured",
                    "receive_verified": False,
                    "portal_native_display_ready": False,
                    "legacy_forwarder_dependency": False,
                    "latest_message_sender": "",
                    "latest_message_subject": "",
                    "latest_message_captured_at": "",
                    "latest_message_s3_key": "",
                    "latest_message_s3_uri": "",
                },
            },
        )
        return AwsCsmCreateProfileOutcome(
            profile_id=profile_id,
            domain=command.domain,
            tenant_id=tenant_id,
            created_profile=created_profile,
        )


__all__ = [
    "AwsCsmCreateProfileCommand",
    "AwsCsmCreateProfileOutcome",
    "AwsCsmProfileRegistryService",
]
