from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

NEWSLETTER_PROFILE_SCHEMA = "mycite.service_tool.newsletter.profile.v2"
NEWSLETTER_CONTACT_LOG_SCHEMA = "mycite.service_tool.newsletter.contact_log.v3"
# Back-compat: older schema strings accepted on read; writers emit the
# current constant. v3 adds the canonical contact-entry row contract
# (see packages/domain/contact_entry.py); v2/v1 rows still load.
_PRIOR_NEWSLETTER_CONTACT_LOG_SCHEMA = "mycite.service_tool.newsletter.contact_log.v2"
_LEGACY_NEWSLETTER_PROFILE_SCHEMA = "mycite.service_tool.aws_csm.newsletter_profile.v1"
_LEGACY_NEWSLETTER_CONTACT_LOG_SCHEMA = "mycite.service_tool.aws_csm.newsletter_contact_log.v1"
_ACCEPTED_NEWSLETTER_PROFILE_SCHEMAS = frozenset(
    {NEWSLETTER_PROFILE_SCHEMA, _LEGACY_NEWSLETTER_PROFILE_SCHEMA}
)
_ACCEPTED_NEWSLETTER_CONTACT_LOG_SCHEMAS = frozenset(
    {
        NEWSLETTER_CONTACT_LOG_SCHEMA,
        _PRIOR_NEWSLETTER_CONTACT_LOG_SCHEMA,
        _LEGACY_NEWSLETTER_CONTACT_LOG_SCHEMA,
    }
)


@runtime_checkable
class NewsletterStatePort(Protocol):
    def list_newsletter_domains(self) -> list[str]:
        ...

    def ensure_domain_bootstrap(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
        unsubscribe_secret_name: str,
        dispatch_callback_secret_name: str,
        inbound_callback_secret_name: str,
        inbound_processor_lambda_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        ...

    def list_verified_author_profiles(self, *, domain: str) -> list[dict[str, Any]]:
        ...

    def load_profile(self, *, domain: str) -> dict[str, Any]:
        ...

    def save_profile(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        ...

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def runtime_secret_seed(self, *, secret_kind: str) -> str:
        ...


@runtime_checkable
class NewsletterCloudPort(Protocol):
    def get_or_create_secret_value(
        self,
        *,
        secret_name: str,
        initial_value: str,
    ) -> str:
        ...

    def queue_dispatch_message(
        self,
        *,
        queue_url: str,
        payload: dict[str, Any],
        region: str,
    ) -> str:
        ...

    def read_s3_bytes(self, *, s3_uri: str, region: str) -> bytes:
        ...

    def caller_identity_summary(self) -> dict[str, Any]:
        ...

    def queue_health_summary(self, *, queue_url: str, queue_arn: str, region: str) -> dict[str, Any]:
        ...

    def lambda_health_summary(self, *, function_name: str, region: str) -> dict[str, Any]:
        ...

    def receipt_rule_summary(
        self,
        *,
        domain: str,
        expected_recipient: str,
        expected_lambda_name: str,
        region: str,
    ) -> dict[str, Any]:
        ...
