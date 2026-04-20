"""Default cloud port: no external IO; ``confirm_verified`` stays fail-closed."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingCloudPort


class AwsCsmOnboardingUnconfiguredCloudPort:
    """Production default until SES/S3/Route53 adapters are wired."""

    def supplemental_profile_patch(self, action: str, profile: dict[str, Any]) -> dict[str, Any]:
        _ = action, profile
        return {}

    def confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        _ = profile
        return False

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        return self.confirmation_evidence_satisfied(profile)

    def describe_profile_readiness(self, profile: dict[str, Any]) -> dict[str, Any]:
        _ = profile
        return {
            "schema": "mycite.v2.portal.system.tools.aws_csm.cloud_readiness.v1",
            "checked_at": "",
            "smtp": {
                "status": "action_required",
                "credentials_secret_state": "missing",
                "secret_name": "",
                "username": "",
                "smtp_host": "",
                "smtp_port": "",
                "handoff_ready": False,
                "message": "AWS-backed onboarding readiness is not configured in this runtime.",
            },
            "provider": {
                "status": "action_required",
                "aws_ses_identity_status": "",
                "last_checked_at": "",
                "message": "AWS-backed onboarding readiness is not configured in this runtime.",
            },
            "inbound": {
                "status": "action_required",
                "expected_recipient": "",
                "expected_lambda_name": "",
                "receipt_rule": {"status": "not_configured"},
                "inbound_lambda": {"status": "not_configured"},
                "latest_capture": {
                    "s3_uri": "",
                    "message_id": "",
                    "subject": "",
                    "captured_at": "",
                    "has_verification_link": False,
                    "accessible": False,
                    "access_error": "",
                    "portal_native_evidence_present": False,
                },
                "portal_native_evidence_present": False,
                "message": "AWS-backed onboarding readiness is not configured in this runtime.",
            },
            "confirmation": {
                "status": "blocked",
                "already_verified": False,
                "can_confirm_verified": False,
                "portal_native_evidence_present": False,
                "message": "confirm_verified remains fail-closed until AWS-backed capture evidence is configured.",
            },
        }

    def describe_domain_status(self, domain_record: dict[str, Any]) -> dict[str, Any]:
        _ = domain_record
        return {
            "dns": {
                "hosted_zone_present": False,
                "nameserver_match": False,
                "registrar_nameservers": [],
                "hosted_zone_nameservers": [],
                "mx_record_present": False,
                "mx_record_values": [],
                "dkim_records_present": False,
                "dkim_record_values": [],
            },
            "ses": {
                "identity_exists": False,
                "identity_status": "not_started",
                "verified_for_sending_status": False,
                "dkim_status": "not_started",
                "dkim_tokens": [],
            },
            "receipt": {"status": "not_ready"},
            "observation": {
                "last_checked_at": "",
                "account": "",
                "role_arn": "",
            },
        }

    def ensure_domain_identity(self, domain_record: dict[str, Any]) -> None:
        _ = domain_record
        raise ValueError("AWS-backed domain identity creation is not configured in this runtime.")

    def sync_domain_dns(self, domain_record: dict[str, Any]) -> None:
        _ = domain_record
        raise ValueError("AWS-backed domain DNS synchronization is not configured in this runtime.")

    def ensure_domain_receipt_rule(self, domain_record: dict[str, Any]) -> None:
        _ = domain_record
        raise ValueError("AWS-backed domain receipt-rule wiring is not configured in this runtime.")

    def send_handoff_email(self, profile: dict[str, Any]) -> dict[str, Any]:
        _ = profile
        raise ValueError("AWS-backed onboarding handoff is not configured in this runtime.")

    def read_handoff_secret(self, profile: dict[str, Any]) -> dict[str, Any]:
        _ = profile
        raise ValueError("AWS-backed onboarding handoff is not configured in this runtime.")


__all__ = ["AwsCsmOnboardingUnconfiguredCloudPort"]
