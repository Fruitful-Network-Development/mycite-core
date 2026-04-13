from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

AWS_CSM_NEWSLETTER_PROFILE_SCHEMA = "mycite.service_tool.aws_csm.newsletter_profile.v1"
AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA = "mycite.service_tool.aws_csm.newsletter_contact_log.v1"


@runtime_checkable
class AwsCsmNewsletterStatePort(Protocol):
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

    def legacy_runtime_secret_seed(self, *, secret_kind: str) -> str:
        ...


@runtime_checkable
class AwsCsmNewsletterCloudPort(Protocol):
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
