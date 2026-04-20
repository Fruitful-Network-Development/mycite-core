from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
import fcntl
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

from MyCiteV2.packages.adapters.event_transport.aws_csm_newsletter_cloud import (
    AwsEc2RoleNewsletterCloudAdapter,
)
from MyCiteV2.packages.adapters.filesystem.aws_csm_newsletter_state import (
    FilesystemAwsCsmNewsletterStateAdapter,
)
from MyCiteV2.packages.modules.cross_domain.aws_csm_forwarder_filter import (
    AwsCsmVerificationForwardFilter,
    extract_links_from_raw_email,
)
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingCloudPort

_AWS_SMTP_IAM_USER = str(os.getenv("AWS_CMS_SMTP_IAM_USER", "aws-cms-smtp")).strip() or "aws-cms-smtp"
_AWS_SMTP_MESSAGE = "SendRawEmail"
_AWS_SMTP_TERMINAL = "aws4_request"
_AWS_SMTP_VERSION = b"\x04"
_AWS_SMTP_DATE_SEED = "11111111"
_DEFAULT_REGION = "us-east-1"
_DEFAULT_INBOUND_LAMBDA = "newsletter-inbound-capture"
_DEFAULT_DOMAIN_RECEIPT_BUCKET = "ses-inbound-fnd-mail"
_ROUTE_MAP_ENV_KEY = "VERIFICATION_ROUTE_MAP_JSON"
_ROUTE_MAP_LAMBDA_ENV_KEY = "AWS_CSM_VERIFICATION_LAMBDA_NAME"
_ROUTE_MAP_SYNC_TIMEOUT_SECONDS = 90
_ALLOWED_HANDOFF_PROVIDERS = frozenset({"gmail", "outlook", "yahoo", "proofpoint", "generic_manual"})


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() == "true"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _normalized_email(value: object) -> str:
    token = _as_text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _local_part(email: object) -> str:
    token = _normalized_email(email)
    return token.split("@", 1)[0] if token else ""


def _email_domain(email: object) -> str:
    token = _normalized_email(email)
    return token.split("@", 1)[1] if token else ""


def _status_is_ready(value: object) -> bool:
    return _as_text(value).lower() in {"ok", "active", "ready", "successful"}


def _normalized_handoff_provider(value: object) -> str:
    token = _as_text(value).lower()
    if token in _ALLOWED_HANDOFF_PROVIDERS:
        return token
    return ""


def _provider_from_email(email: object) -> str:
    domain = _email_domain(email)
    if domain in {"gmail.com", "googlemail.com"}:
        return "gmail"
    if domain in {"outlook.com", "hotmail.com", "live.com", "msn.com"}:
        return "outlook"
    if domain in {"yahoo.com", "rocketmail.com", "ymail.com"}:
        return "yahoo"
    if domain.endswith("proofpoint.com"):
        return "proofpoint"
    return "generic_manual"


def _provider_label(provider: str) -> str:
    if provider == "gmail":
        return "Gmail"
    if provider == "outlook":
        return "Outlook"
    if provider == "yahoo":
        return "Yahoo"
    if provider == "proofpoint":
        return "Proofpoint"
    return "Manual"


def _smtp_secret_description(secret_name: str) -> str:
    token = _as_text(secret_name)
    if not token:
        return "SES SMTP credentials for AWS-CSM send-as onboarding"
    prefix = "aws-cms/smtp/"
    profile_suffix = token[len(prefix) :] if token.startswith(prefix) else token
    profile_suffix = profile_suffix.strip().strip("/")
    profile_id = f"aws-csm.{profile_suffix}" if profile_suffix else "aws-csm"
    return f"SES SMTP credentials for {profile_id} send-as onboarding"


def _aws_smtp_password(secret_access_key: str, *, region: str) -> str:
    secret = _as_text(secret_access_key)
    region_token = _as_text(region) or _DEFAULT_REGION
    if not secret:
        raise ValueError("Missing secret access key for SES SMTP password derivation.")

    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    signature = _sign(("AWS4" + secret).encode("utf-8"), _AWS_SMTP_DATE_SEED)
    signature = _sign(signature, region_token)
    signature = _sign(signature, "ses")
    signature = _sign(signature, _AWS_SMTP_TERMINAL)
    signature = _sign(signature, _AWS_SMTP_MESSAGE)
    return base64.b64encode(_AWS_SMTP_VERSION + signature).decode("utf-8")


def _raw_message_summary(raw_bytes: bytes) -> dict[str, Any]:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    except Exception:  # noqa: BLE001
        return {
            "sender": "",
            "recipient": "",
            "subject": "",
            "links": [],
        }
    sender = next(
        (
            _normalized_email(address)
            for _, address in getaddresses(message.get_all("From", []))
            if _normalized_email(address)
        ),
        "",
    )
    recipient = next(
        (
            _normalized_email(address)
            for _, address in getaddresses(
                message.get_all("Delivered-To", [])
                + message.get_all("X-Original-To", [])
                + message.get_all("To", [])
            )
            if _normalized_email(address)
        ),
        "",
    )
    links = extract_links_from_raw_email(raw_bytes)
    return {
        "sender": sender,
        "recipient": recipient,
        "subject": _as_text(message.get("Subject")),
        "links": links,
    }


class AwsEc2RoleOnboardingCloudAdapter(AwsEc2RoleNewsletterCloudAdapter, AwsCsmOnboardingCloudPort):
    def __init__(self, *, private_dir: str | Path | None = None, tenant_id: str = "") -> None:
        self._private_dir = None if private_dir is None else Path(private_dir)
        self._tenant_id = _as_text(tenant_id)
        self._newsletter_state = (
            None
            if self._private_dir is None
            else FilesystemAwsCsmNewsletterStateAdapter(self._private_dir)
        )

    def supplemental_profile_patch(self, action: str, profile: dict[str, Any]) -> dict[str, Any]:
        token = _as_text(action)
        if token in {"prepare_send_as", "stage_smtp_credentials"}:
            return self._stage_smtp_patch(profile)
        if token == "refresh_provider_status":
            return self._provider_status_patch(profile)
        if token in {"enable_inbound_capture", "refresh_inbound_status"}:
            readiness = self.describe_profile_readiness(profile)
            return self._inbound_status_patch(profile, readiness=readiness)
        if token == "capture_verification":
            readiness = self.describe_profile_readiness(profile)
            patch = self._inbound_status_patch(profile, readiness=readiness)
            capture = _as_dict(_as_dict(readiness.get("inbound")).get("latest_capture"))
            verification_patch = self._verification_capture_patch(profile, capture=capture)
            if verification_patch:
                patch["verification"] = verification_patch
            return patch
        return {}

    def confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        readiness = self.describe_profile_readiness(profile)
        confirmation = _as_dict(readiness.get("confirmation"))
        return bool(confirmation.get("already_verified")) or bool(confirmation.get("can_confirm_verified"))

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        return self.confirmation_evidence_satisfied(profile)

    def describe_profile_readiness(self, profile: dict[str, Any]) -> dict[str, Any]:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        provider = _as_dict(profile.get("provider"))
        verification = _as_dict(profile.get("verification"))
        inbound = _as_dict(profile.get("inbound"))

        checked_at = _utc_now_iso()
        region = self._region_for_profile(profile)
        domain = _normalized_domain(identity.get("domain"))
        send_as_email = self._send_as_email(profile)
        handoff_provider = self._handoff_provider(profile)
        secret_name = self._smtp_secret_name(profile)
        smtp_material = (
            self._smtp_secret_material(secret_name=secret_name, region=region)
            if secret_name
            else {"state": "missing", "secret_name": "", "username": "", "password": "", "message": "No SMTP secret is configured."}
        )
        smtp_state = _as_text(smtp_material.get("state")).lower()
        smtp_status = "ready" if smtp_state == "configured" else ("blocked" if smtp_state in {"error", "quota_blocked"} else "action_required")
        provider_summary = self._ses_identity_summary(
            region=region,
            email_identity=domain or send_as_email,
        )
        provider_state = _as_text(provider_summary.get("aws_ses_identity_status") or provider.get("aws_ses_identity_status")).lower()
        provider_status = "ready" if provider_state == "verified" else ("blocked" if provider_state in {"error", "access_denied"} else "action_required")
        expected_lambda_name = self._inbound_lambda_name(profile)
        receipt_rule = self.receipt_rule_summary(
            domain=domain,
            expected_recipient=send_as_email or (f"news@{domain}" if domain else ""),
            expected_lambda_name=expected_lambda_name,
            region=region,
        ) if (domain and expected_lambda_name) else {"status": "not_configured", "message": "Inbound receipt rule target is not configured."}
        inbound_lambda = (
            self.lambda_health_summary(function_name=expected_lambda_name, region=region)
            if expected_lambda_name
            else {"status": "not_configured", "message": "Inbound capture Lambda is not configured."}
        )
        capture = self._capture_summary(profile, region=region, receipt_rule=receipt_rule)
        capture_evidence = bool(capture.get("portal_native_evidence_present"))
        provider_send_as_status = self._provider_send_as_status(profile)
        already_verified = (
            _as_text(verification.get("status")).lower() == "verified"
            or _as_text(verification.get("portal_state")).lower() == "verified"
            or provider_send_as_status == "verified"
            or _as_text(provider.get("gmail_send_as_status")).lower() == "verified"
        )
        inbound_ready = bool(inbound.get("receive_verified")) or _as_bool(inbound.get("portal_native_display_ready"))
        if inbound_ready:
            inbound_status = "ready"
        elif _status_is_ready(receipt_rule.get("status")) and _status_is_ready(inbound_lambda.get("status")) and capture_evidence:
            inbound_status = "captured"
        elif _status_is_ready(receipt_rule.get("status")) and _status_is_ready(inbound_lambda.get("status")):
            inbound_status = "listening"
        elif _as_text(receipt_rule.get("status")).lower() == "error" or _as_text(inbound_lambda.get("status")).lower() == "error":
            inbound_status = "blocked"
        else:
            inbound_status = "action_required"
        if already_verified:
            confirmation_status = "ready"
        elif capture_evidence:
            confirmation_status = "action_required"
        elif smtp_status == "ready":
            confirmation_status = "manual"
        else:
            confirmation_status = "blocked"

        return {
            "schema": "mycite.v2.portal.system.tools.aws_csm.cloud_readiness.v1",
            "checked_at": checked_at,
            "profile_id": _as_text(identity.get("profile_id")),
            "domain": domain,
            "smtp": {
                "status": smtp_status,
                "credentials_secret_state": _as_text(smtp_material.get("state")),
                "secret_name": _as_text(smtp_material.get("secret_name") or secret_name),
                "username": _as_text(smtp_material.get("persisted_username") or smtp_material.get("username") or smtp.get("username")),
                "smtp_host": _as_text(smtp_material.get("smtp_host") or smtp.get("host") or f"email-smtp.{region}.amazonaws.com"),
                "smtp_port": _as_text(smtp_material.get("smtp_port") or smtp.get("port") or "587"),
                "handoff_ready": smtp_status == "ready",
                "message": _as_text(smtp_material.get("message"))
                or ("SMTP secret material is ready for handoff." if smtp_status == "ready" else "SMTP credentials still need operator attention."),
            },
            "provider": {
                "status": provider_status,
                "handoff_provider": handoff_provider,
                "send_as_provider_status": provider_send_as_status,
                "aws_ses_identity_status": provider_state or _as_text(provider.get("aws_ses_identity_status")),
                "last_checked_at": checked_at,
                "message": _as_text(provider_summary.get("message"))
                or ("AWS SES identity is verified." if provider_status == "ready" else "AWS SES identity still needs verification or refresh."),
            },
            "inbound": {
                "status": inbound_status,
                "expected_recipient": send_as_email or (f"news@{domain}" if domain else ""),
                "expected_lambda_name": expected_lambda_name,
                "receipt_rule": receipt_rule,
                "inbound_lambda": inbound_lambda,
                "latest_capture": capture,
                "portal_native_evidence_present": capture_evidence,
                "message": (
                    "Portal-native inbound evidence is available."
                    if capture_evidence
                    else "Inbound capture is waiting for an AWS-backed verification message."
                ),
            },
            "confirmation": {
                "status": confirmation_status,
                "handoff_provider": handoff_provider,
                "already_verified": already_verified,
                "can_confirm_verified": capture_evidence and not already_verified,
                "portal_native_evidence_present": capture_evidence,
                "message": (
                    "Portal-native verification evidence is ready to confirm."
                    if capture_evidence and not already_verified
                    else (
                        f"{_provider_label(handoff_provider)} send-as is already verified."
                        if already_verified
                        else "Confirm send-as only after portal-native evidence is captured."
                    )
                ),
            },
        }

    def describe_domain_status(self, domain_record: dict[str, Any]) -> dict[str, Any]:
        identity = _as_dict(domain_record.get("identity"))
        dns = _as_dict(domain_record.get("dns"))
        receipt = _as_dict(domain_record.get("receipt"))
        domain = _normalized_domain(identity.get("domain"))
        region = _as_text(identity.get("region")) or _DEFAULT_REGION
        hosted_zone_id = _as_text(identity.get("hosted_zone_id"))
        caller = self.caller_identity_summary()

        registrar_nameservers = self._registrar_nameservers(domain)
        hosted_zone_nameservers = self._hosted_zone_nameservers(hosted_zone_id)
        hosted_zone_present = bool(hosted_zone_nameservers)
        nameserver_match = bool(registrar_nameservers and hosted_zone_nameservers and registrar_nameservers == hosted_zone_nameservers)

        identity_summary = self._domain_identity_summary(domain=domain, region=region)
        mx_expected_value = f"10 inbound-smtp.{region}.amazonaws.com"
        record_summary = self._route53_record_summary(
            hosted_zone_id=hosted_zone_id,
            domain=domain,
            region=region,
            dkim_tokens=_as_list(identity_summary.get("dkim_tokens")),
        )
        receipt_summary = self.receipt_rule_summary(
            domain=domain,
            expected_recipient=domain,
            expected_lambda_name=_as_text(receipt.get("expected_lambda_name")) or _DEFAULT_INBOUND_LAMBDA,
            region=region,
        )
        matching_rules = _as_list(receipt_summary.get("matching_rules"))
        primary_rule = _as_dict(matching_rules[0]) if matching_rules else {}
        return {
            "dns": {
                "hosted_zone_present": hosted_zone_present,
                "registrar_nameservers": registrar_nameservers,
                "hosted_zone_nameservers": hosted_zone_nameservers,
                "nameserver_match": nameserver_match,
                "mx_expected_value": mx_expected_value,
                "mx_record_present": _as_bool(record_summary.get("mx_record_present")),
                "mx_record_values": _as_list(record_summary.get("mx_record_values")),
                "dkim_records_present": _as_bool(record_summary.get("dkim_records_present")),
                "dkim_record_values": _as_list(record_summary.get("dkim_record_values")),
            },
            "ses": identity_summary,
            "receipt": {
                "status": _as_text(receipt_summary.get("status")) or "not_ready",
                "rule_name": _as_text(primary_rule.get("rule_name") or receipt.get("rule_name") or self._domain_rule_name(domain)),
                "expected_recipient": _as_text(receipt_summary.get("expected_recipient") or domain),
                "expected_lambda_name": _as_text(receipt.get("expected_lambda_name")) or _DEFAULT_INBOUND_LAMBDA,
                "bucket": _as_text(primary_rule.get("s3_bucket") or receipt.get("bucket") or _DEFAULT_DOMAIN_RECEIPT_BUCKET),
                "prefix": _as_text(primary_rule.get("s3_prefix") or receipt.get("prefix") or f"inbound/{domain}/"),
                "matching_rules": matching_rules,
            },
            "observation": {
                "last_checked_at": _utc_now_iso(),
                "account": _as_text(caller.get("account")),
                "role_arn": _as_text(caller.get("arn")),
            },
        }

    def ensure_domain_identity(self, domain_record: dict[str, Any]) -> None:
        identity = _as_dict(domain_record.get("identity"))
        domain = _normalized_domain(identity.get("domain"))
        region = _as_text(identity.get("region")) or _DEFAULT_REGION
        if not domain:
            raise ValueError("AWS-CSM domain onboarding record is missing identity.domain.")
        client = self._client("sesv2", region=region)
        try:
            client.get_email_identity(EmailIdentity=domain)
            return
        except Exception as exc:  # noqa: BLE001
            message = _as_text(exc).lower()
            if "notfound" not in message and "not found" not in message:
                raise
        client.create_email_identity(EmailIdentity=domain)

    def sync_domain_dns(self, domain_record: dict[str, Any]) -> None:
        status = self.describe_domain_status(domain_record)
        identity = _as_dict(domain_record.get("identity"))
        dns = _as_dict(status.get("dns"))
        ses = _as_dict(status.get("ses"))
        domain = _normalized_domain(identity.get("domain"))
        region = _as_text(identity.get("region")) or _DEFAULT_REGION
        hosted_zone_id = _as_text(identity.get("hosted_zone_id"))
        if not _as_bool(dns.get("hosted_zone_present")):
            raise ValueError("The configured Route 53 hosted zone is missing or unreadable.")
        if not _as_bool(dns.get("nameserver_match")):
            raise ValueError("Refusing DNS sync because registrar nameservers do not match the selected hosted zone.")
        dkim_tokens = [token for token in (_as_text(item) for item in _as_list(ses.get("dkim_tokens"))) if token]
        if len(dkim_tokens) < 3:
            raise ValueError("Create the SES domain identity first so DKIM tokens exist before syncing DNS.")
        route53 = self._client("route53")
        changes: list[dict[str, Any]] = [
            {
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": domain,
                    "Type": "MX",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": f"10 inbound-smtp.{region}.amazonaws.com"}],
                },
            }
        ]
        for token in dkim_tokens[:3]:
            changes.append(
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": f"{token}._domainkey.{domain}",
                        "Type": "CNAME",
                        "TTL": 1800,
                        "ResourceRecords": [{"Value": f"{token}.dkim.amazonses.com"}],
                    },
                }
            )
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Comment": f"Sync AWS-CSM SES records for {domain}", "Changes": changes},
        )

    def ensure_domain_receipt_rule(self, domain_record: dict[str, Any]) -> None:
        identity = _as_dict(domain_record.get("identity"))
        receipt = _as_dict(domain_record.get("receipt"))
        domain = _normalized_domain(identity.get("domain"))
        region = _as_text(identity.get("region")) or _DEFAULT_REGION
        rule_name = _as_text(receipt.get("rule_name")) or self._domain_rule_name(domain)
        expected_lambda_name = _as_text(receipt.get("expected_lambda_name")) or _DEFAULT_INBOUND_LAMBDA
        bucket = _as_text(receipt.get("bucket")) or _DEFAULT_DOMAIN_RECEIPT_BUCKET
        prefix = _as_text(receipt.get("prefix")) or f"inbound/{domain}/"
        if not domain:
            raise ValueError("AWS-CSM domain onboarding record is missing identity.domain.")
        ses = self._client("ses", region=region)
        active = ses.describe_active_receipt_rule_set()
        rule_set_name = _as_text(_as_dict(active.get("Metadata")).get("Name"))
        if not rule_set_name:
            raise ValueError("No active SES receipt rule set is configured.")
        rules = [row for row in _as_list(active.get("Rules")) if isinstance(row, dict)]
        lambda_arn = _as_text(self.lambda_health_summary(function_name=expected_lambda_name, region=region).get("function_arn"))
        if not lambda_arn:
            raise ValueError(f"Unable to resolve Lambda ARN for {expected_lambda_name}.")
        rule_payload = {
            "Name": rule_name,
            "Enabled": True,
            "TlsPolicy": "Optional",
            "Recipients": [domain],
            "Actions": [
                {
                    "S3Action": {
                        "BucketName": bucket,
                        "ObjectKeyPrefix": prefix,
                    }
                },
                {
                    "LambdaAction": {
                        "FunctionArn": lambda_arn,
                        "InvocationType": "Event",
                    }
                },
            ],
            "ScanEnabled": True,
        }
        existing = next((row for row in rules if _as_text(row.get("Name")) == rule_name), None)
        if existing is not None:
            ses.update_receipt_rule(RuleSetName=rule_set_name, Rule=rule_payload)
            return
        after = _as_text(rules[-1].get("Name")) if rules else ""
        kwargs: dict[str, Any] = {"RuleSetName": rule_set_name, "Rule": rule_payload}
        if after:
            kwargs["After"] = after
        ses.create_receipt_rule(**kwargs)

    def send_handoff_email(self, profile: dict[str, Any]) -> dict[str, Any]:
        send_as_email = self._send_as_email(profile)
        if not send_as_email:
            raise ValueError("AWS-CSM send-as email is not configured for this profile.")
        destination = self._handoff_destination(profile)
        if not destination:
            raise ValueError("AWS-CSM operator inbox target is not configured for this profile.")
        material = self.read_handoff_secret(profile)
        username = _as_text(material.get("username"))
        password = _as_text(material.get("password"))
        smtp_host = _as_text(material.get("smtp_host"))
        smtp_port = _as_text(material.get("smtp_port"))
        handoff_provider = self._handoff_provider(profile)
        provider_label = _provider_label(handoff_provider)
        instructions = self._handoff_instruction_lines(
            handoff_provider=handoff_provider,
            send_as_email=send_as_email,
        )
        region = self._region_for_profile(profile)
        response = self._client("sesv2", region=region).send_email(
            FromEmailAddress=send_as_email,
            Destination={"ToAddresses": [destination]},
            Content={
                "Simple": {
                    "Subject": {"Data": f"AWS-CSM {provider_label} send-as handoff for {send_as_email}"},
                    "Body": {
                        "Text": {
                            "Data": "\n".join(
                                [
                                    f"Set up send-as for {send_as_email} using {provider_label}.",
                                    "",
                                    f"SMTP host: {smtp_host}",
                                    f"SMTP port: {smtp_port}",
                                    f"SMTP username: {username}",
                                    f"SMTP password: {password}",
                                    "",
                                    "If the provider asks again, you can also reveal the SMTP password from the AWS-CSM portal action.",
                                    *instructions,
                                ]
                            )
                        }
                    },
                }
            },
        )
        return {
            "message_id": _as_text(response.get("MessageId")),
            "sent_to": destination,
            "send_as_email": send_as_email,
            "username": username,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "state": _as_text(material.get("state")),
            "handoff_provider": handoff_provider,
        }

    def sync_verification_route_map(self, *, profiles: list[dict[str, Any]]) -> dict[str, Any]:
        routes = self._verification_route_map_from_profiles(profiles=profiles)
        lambda_name = (
            _as_text(os.getenv(_ROUTE_MAP_LAMBDA_ENV_KEY))
            or self._verification_lambda_name(profiles=profiles)
            or _DEFAULT_INBOUND_LAMBDA
        )
        region = _DEFAULT_REGION
        client = self._client("lambda", region=region)
        configuration = client.get_function_configuration(FunctionName=lambda_name)
        environment = dict(_as_dict(configuration.get("Environment")).get("Variables") or {})
        existing_raw = _as_text(environment.get(_ROUTE_MAP_ENV_KEY)) or "{}"
        try:
            existing_routes = json.loads(existing_raw)
        except json.JSONDecodeError:
            existing_routes = {}
        existing_routes = existing_routes if isinstance(existing_routes, dict) else {}
        if existing_routes == routes:
            return {
                "status": "success",
                "message": "Verification-forward route map already up to date.",
                "route_count": len(routes),
                "tracked_recipients": sorted(routes),
                "lambda_name": lambda_name,
                "region": region,
                "changed": False,
            }
        environment[_ROUTE_MAP_ENV_KEY] = json.dumps(routes, separators=(",", ":"), sort_keys=True)
        client.update_function_configuration(
            FunctionName=lambda_name,
            Environment={"Variables": environment},
        )
        self._wait_for_lambda_update(client=client, function_name=lambda_name)
        return {
            "status": "success",
            "message": "Verification-forward route map synced to Lambda environment.",
            "route_count": len(routes),
            "tracked_recipients": sorted(routes),
            "lambda_name": lambda_name,
            "region": region,
            "changed": True,
        }

    def read_handoff_secret(self, profile: dict[str, Any]) -> dict[str, Any]:
        send_as_email = self._send_as_email(profile)
        secret_name = self._smtp_secret_name(profile)
        if not secret_name:
            raise ValueError("AWS-CSM SMTP secret name is not configured for this profile.")
        region = self._region_for_profile(profile)
        material = self._smtp_secret_material(secret_name=secret_name, region=region)
        state = _as_text(material.get("state")).lower()
        username = _as_text(material.get("persisted_username") or material.get("username"))
        secret_value = _as_text(material.get("password"))
        if state != "configured" or not username or not secret_value:
            raise ValueError("SMTP credentials must be staged before the password can be revealed.")
        return {
            "send_as_email": send_as_email,
            "secret_name": _as_text(material.get("secret_name") or secret_name),
            "state": state,
            "username": username,
            "password": secret_value,
            "smtp_host": _as_text(material.get("smtp_host")) or f"email-smtp.{region}.amazonaws.com",
            "smtp_port": _as_text(material.get("smtp_port")) or "587",
        }

    def _stage_smtp_patch(self, profile: dict[str, Any]) -> dict[str, Any]:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        workflow = _as_dict(profile.get("workflow"))
        checked_at = _utc_now_iso()
        region = self._region_for_profile(profile)
        secret_name = self._smtp_secret_name(profile)
        material = (
            self._ensure_smtp_secret_material(secret_name=secret_name, region=region)
            if secret_name
            else {"state": "missing", "secret_name": "", "username": "", "password": "", "message": "No SMTP secret name is configured."}
        )
        provider = self._ses_identity_summary(
            region=region,
            email_identity=_normalized_domain(identity.get("domain")) or self._send_as_email(profile),
        )
        handoff_ready = _as_text(material.get("state")).lower() == "configured"
        send_as_email = self._send_as_email(profile)
        handoff_provider = self._handoff_provider(profile)
        local_part = _local_part(send_as_email) or _as_text(identity.get("mailbox_local_part")) or _as_text(smtp.get("local_part"))
        return {
            "smtp": {
                "host": _as_text(material.get("smtp_host") or smtp.get("host") or f"email-smtp.{region}.amazonaws.com"),
                "port": _as_text(material.get("smtp_port") or smtp.get("port") or "587"),
                "username": _as_text(material.get("persisted_username") or material.get("username") or smtp.get("username")),
                "credentials_source": _as_text(smtp.get("credentials_source")) or "operator_managed",
                "handoff_ready": handoff_ready,
                "credentials_secret_name": _as_text(material.get("secret_name") or secret_name),
                "credentials_secret_state": "configured" if handoff_ready else (_as_text(smtp.get("credentials_secret_state")) or "missing"),
                "send_as_email": send_as_email,
                "local_part": local_part,
                "handoff_provider": handoff_provider,
                "staging_state": "material_ready" if handoff_ready else "operator_attention_required",
            },
            "provider": {
                "handoff_provider": handoff_provider,
                "send_as_provider_status": self._provider_send_as_status(profile),
                "aws_ses_identity_status": _as_text(provider.get("aws_ses_identity_status")),
                "last_checked_at": checked_at,
            },
            "workflow": {
                "is_ready_for_user_handoff": handoff_ready,
                "handoff_provider": handoff_provider,
                "handoff_status": (
                    f"ready_for_{handoff_provider}_handoff"
                    if handoff_ready
                    else (_as_text(workflow.get("handoff_status")) or "smtp_pending")
                ),
            },
        }

    def _provider_status_patch(self, profile: dict[str, Any]) -> dict[str, Any]:
        identity = _as_dict(profile.get("identity"))
        checked_at = _utc_now_iso()
        summary = self._ses_identity_summary(
            region=self._region_for_profile(profile),
            email_identity=_normalized_domain(identity.get("domain")) or self._send_as_email(profile),
        )
        return {
            "provider": {
                "handoff_provider": self._handoff_provider(profile),
                "send_as_provider_status": self._provider_send_as_status(profile),
                "aws_ses_identity_status": _as_text(summary.get("aws_ses_identity_status")),
                "last_checked_at": checked_at,
            }
        }

    def _inbound_status_patch(self, profile: dict[str, Any], *, readiness: dict[str, Any]) -> dict[str, Any]:
        inbound = _as_dict(profile.get("inbound"))
        workflow = _as_dict(profile.get("workflow"))
        inbound_summary = _as_dict(readiness.get("inbound"))
        capture = _as_dict(inbound_summary.get("latest_capture"))
        receipt_rule = _as_dict(inbound_summary.get("receipt_rule"))
        inbound_lambda = _as_dict(inbound_summary.get("inbound_lambda"))
        capture_evidence = bool(inbound_summary.get("portal_native_evidence_present"))
        receipt_ready = _status_is_ready(receipt_rule.get("status"))
        lambda_ready = _status_is_ready(inbound_lambda.get("status"))
        existing_receive_verified = _as_bool(inbound.get("receive_verified"))
        existing_portal_ready = _as_bool(inbound.get("portal_native_display_ready"))
        if existing_receive_verified:
            receive_state = "receive_operational"
        elif capture_evidence:
            receive_state = "receive_pending"
        elif receipt_ready and lambda_ready:
            receive_state = "receive_configured"
        else:
            receive_state = _as_text(inbound.get("receive_state")) or "receive_unconfigured"
        patch = {
            "inbound": {
                "receive_state": receive_state,
                "receive_last_checked_at": _as_text(readiness.get("checked_at")),
                "portal_native_display_ready": capture_evidence or existing_portal_ready,
                "capture_source_kind": "s3_object" if _as_text(capture.get("s3_uri")) else _as_text(inbound.get("capture_source_kind")),
                "capture_source_reference": _as_text(capture.get("s3_uri") or inbound.get("capture_source_reference")),
                "latest_message_s3_uri": _as_text(capture.get("s3_uri") or inbound.get("latest_message_s3_uri")),
                "latest_message_s3_key": _as_text(capture.get("s3_key") or inbound.get("latest_message_s3_key")),
                "latest_message_id": _as_text(capture.get("message_id") or inbound.get("latest_message_id")),
                "latest_message_sender": _as_text(capture.get("sender") or inbound.get("latest_message_sender")),
                "latest_message_recipient": _as_text(capture.get("recipient") or inbound.get("latest_message_recipient")),
                "latest_message_subject": _as_text(capture.get("subject") or inbound.get("latest_message_subject")),
                "latest_message_captured_at": _as_text(capture.get("captured_at") or inbound.get("latest_message_captured_at")),
                "latest_message_has_verification_link": bool(
                    capture.get("has_verification_link") or inbound.get("latest_message_has_verification_link")
                ),
            },
            "workflow": {
                "is_receive_path_modeled": receipt_ready and lambda_ready,
                "is_portal_native_inbound_ready": capture_evidence or _as_bool(workflow.get("is_portal_native_inbound_ready")),
            },
        }
        if existing_receive_verified:
            patch["inbound"]["receive_verified"] = True
        return patch

    def _verification_capture_patch(self, profile: dict[str, Any], *, capture: dict[str, Any]) -> dict[str, Any]:
        verification = _as_dict(profile.get("verification"))
        s3_uri = _as_text(capture.get("s3_uri"))
        if not s3_uri:
            return {}
        return {
            "portal_state": "capture_received",
            "latest_message_reference": s3_uri,
            "email_received_at": _as_text(capture.get("captured_at") or verification.get("email_received_at")),
            "link": _as_text(capture.get("link") or verification.get("link")),
        }

    def _capture_summary(
        self,
        profile: dict[str, Any],
        *,
        region: str,
        receipt_rule: dict[str, Any],
    ) -> dict[str, Any]:
        inbound = _as_dict(profile.get("inbound"))
        verification = _as_dict(profile.get("verification"))
        s3_uri = _as_text(
            inbound.get("latest_message_s3_uri")
            or inbound.get("capture_source_reference")
            or verification.get("latest_message_reference")
        )
        expected_recipient = self._send_as_email(profile)
        existing = self._capture_from_s3_uri(
            s3_uri=s3_uri,
            region=region,
            expected_recipient=expected_recipient,
            handoff_provider=self._handoff_provider(profile),
            fallback_subject=_as_text(inbound.get("latest_message_subject")),
            fallback_captured_at=_as_text(inbound.get("latest_message_captured_at")),
            fallback_message_id=_as_text(inbound.get("latest_message_id")),
        )
        if existing.get("portal_native_evidence_present"):
            return existing

        discovered = self._discover_latest_capture(
            profile,
            region=region,
            receipt_rule=receipt_rule,
        )
        if discovered.get("portal_native_evidence_present"):
            return discovered
        if _as_text(existing.get("s3_uri")):
            return existing
        if _as_text(discovered.get("s3_uri")):
            return discovered
        return {
            "s3_uri": "",
            "message_id": "",
            "subject": _as_text(inbound.get("latest_message_subject")),
            "captured_at": _as_text(inbound.get("latest_message_captured_at")),
            "has_verification_link": bool(inbound.get("latest_message_has_verification_link")) or bool(_as_text(verification.get("link"))),
            "accessible": False,
            "access_error": "",
            "portal_native_evidence_present": False,
            "sender": _as_text(inbound.get("latest_message_sender")),
            "recipient": _as_text(inbound.get("latest_message_recipient")),
            "link": _as_text(verification.get("link")),
            "s3_key": _as_text(inbound.get("latest_message_s3_key")),
        }

    def _capture_from_s3_uri(
        self,
        *,
        s3_uri: str,
        region: str,
        expected_recipient: str,
        handoff_provider: str,
        fallback_subject: str = "",
        fallback_captured_at: str = "",
        fallback_message_id: str = "",
    ) -> dict[str, Any]:
        s3_uri_token = _as_text(s3_uri)
        summary = {
            "s3_uri": s3_uri_token,
            "message_id": _as_text(fallback_message_id),
            "subject": _as_text(fallback_subject),
            "captured_at": _as_text(fallback_captured_at),
            "has_verification_link": False,
            "accessible": False,
            "access_error": "",
            "portal_native_evidence_present": False,
            "sender": "",
            "recipient": expected_recipient,
            "link": "",
            "s3_key": s3_uri_token.split("/", 3)[3] if s3_uri_token.startswith("s3://") and s3_uri_token.count("/") >= 3 else "",
        }
        if not s3_uri_token:
            return summary
        try:
            raw_bytes = self.read_s3_bytes(s3_uri=s3_uri_token, region=region)
        except Exception as exc:  # noqa: BLE001
            summary["access_error"] = _as_text(exc)
            return summary
        summary["accessible"] = bool(raw_bytes)
        raw_message = _raw_message_summary(raw_bytes)
        sender = _as_text(raw_message.get("sender"))
        recipient = _as_text(raw_message.get("recipient") or expected_recipient)
        subject = _as_text(raw_message.get("subject") or fallback_subject)
        links = list(raw_message.get("links") or [])
        decision = AwsCsmVerificationForwardFilter().decide(
            tracked_recipients={expected_recipient} if expected_recipient else set(),
            sender=sender,
            recipient=recipient,
            subject=subject,
            raw_bytes=raw_bytes,
            handoff_provider=handoff_provider,
        )
        summary.update(
            {
                "message_id": _as_text(fallback_message_id) or summary["s3_key"].split("/")[-1],
                "subject": subject,
                "captured_at": _as_text(fallback_captured_at),
                "has_verification_link": bool(links),
                "portal_native_evidence_present": decision.should_forward,
                "sender": sender,
                "recipient": recipient,
                "link": links[0] if links else "",
            }
        )
        return summary

    def _discover_latest_capture(
        self,
        profile: dict[str, Any],
        *,
        region: str,
        receipt_rule: dict[str, Any],
    ) -> dict[str, Any]:
        identity = _as_dict(profile.get("identity"))
        expected_recipient = self._send_as_email(profile)
        domain = _normalized_domain(identity.get("domain"))
        fallback_prefixes = [f"inbound/{domain}/"] if domain else []
        if domain == "fruitfulnetworkdevelopment.com":
            fallback_prefixes.append("inbound/")
        candidates: list[dict[str, str]] = []
        seen: set[str] = set()
        matching_rules = list(_as_dict(receipt_rule).get("matching_rules") or [])
        for rule in matching_rules:
            if not isinstance(rule, dict):
                continue
            bucket = _as_text(rule.get("s3_bucket"))
            prefix = _as_text(rule.get("s3_prefix"))
            if bucket and prefix:
                key = f"{bucket}/{prefix}"
                if key not in seen:
                    seen.add(key)
                    try:
                        candidates.extend(self.list_s3_objects(bucket=bucket, prefix=prefix, region=region, max_keys=20))
                    except Exception:  # noqa: BLE001
                        continue
        if matching_rules:
            default_bucket = _as_text(_as_dict(matching_rules[0]).get("s3_bucket"))
            for prefix in fallback_prefixes:
                key = f"{default_bucket}/{prefix}"
                if default_bucket and key not in seen:
                    seen.add(key)
                    try:
                        candidates.extend(self.list_s3_objects(bucket=default_bucket, prefix=prefix, region=region, max_keys=20))
                    except Exception:  # noqa: BLE001
                        continue
        candidates.sort(key=lambda item: item.get("last_modified") or "", reverse=True)
        for candidate in candidates[:40]:
            summary = self._capture_from_s3_uri(
                s3_uri=_as_text(candidate.get("s3_uri")),
                region=region,
                expected_recipient=expected_recipient,
                handoff_provider=self._handoff_provider(profile),
                fallback_captured_at=_as_text(candidate.get("last_modified")),
                fallback_message_id=_as_text(candidate.get("key")).split("/")[-1],
            )
            if summary.get("portal_native_evidence_present"):
                return summary
        return {}

    def _region_for_profile(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        token = (
            _as_text(identity.get("region"))
            or _as_text(smtp.get("smtp_region"))
            or _as_text(self._newsletter_profile(_normalized_domain(identity.get("domain"))).get("aws_region"))
            or _DEFAULT_REGION
        )
        return token

    def _send_as_email(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        return _normalized_email(identity.get("send_as_email") or smtp.get("send_as_email"))

    def _handoff_provider(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        provider = _as_dict(profile.get("provider"))
        explicit = _normalized_handoff_provider(
            provider.get("handoff_provider")
            or identity.get("handoff_provider")
            or smtp.get("handoff_provider")
        )
        if explicit:
            return explicit
        inferred = _provider_from_email(
            smtp.get("forward_to_email")
            or identity.get("operator_inbox_target")
            or identity.get("single_user_email")
        )
        return inferred or "generic_manual"

    def _provider_send_as_status(self, profile: dict[str, Any]) -> str:
        provider = _as_dict(profile.get("provider"))
        status = _as_text(provider.get("send_as_provider_status")).lower()
        if status:
            return status
        legacy = _as_text(provider.get("gmail_send_as_status")).lower()
        return legacy or "not_started"

    def _handoff_destination(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        return _normalized_email(smtp.get("forward_to_email") or identity.get("operator_inbox_target"))

    def _handoff_instruction_lines(self, *, handoff_provider: str, send_as_email: str) -> list[str]:
        provider = _normalized_handoff_provider(handoff_provider) or "generic_manual"
        if provider == "gmail":
            return [
                "In Gmail, open Settings -> Accounts and Import -> Send mail as -> Add another email address.",
                f"Use the SMTP values above for {send_as_email}.",
                "After saving the entry, wait for the Gmail confirmation email and open its verification link.",
            ]
        if provider == "outlook":
            return [
                "In Outlook/Hotmail, add a connected address or alias using the SMTP values above.",
                "Complete the Microsoft verification flow when prompted, then confirm the send-as address.",
            ]
        if provider == "yahoo":
            return [
                "In Yahoo Mail, add a sending address using the SMTP values above.",
                "Complete Yahoo verification and confirm the send-as address from the provider message.",
            ]
        if provider == "proofpoint":
            return [
                "Use your Proofpoint/mail gateway workflow to add the external send-as identity with the SMTP values above.",
                "Complete the verification message flow and confirm the send-as link or code.",
            ]
        return [
            "Use your mail provider's manual send-as / external SMTP setup flow with the SMTP values above.",
            "Complete the provider verification email flow and confirm the send-as address.",
        ]

    def _smtp_secret_name(self, profile: dict[str, Any]) -> str:
        identity = _as_dict(profile.get("identity"))
        smtp = _as_dict(profile.get("smtp"))
        configured = _as_text(smtp.get("credentials_secret_name"))
        if configured:
            return configured
        tenant_id = _as_text(identity.get("tenant_id"))
        mailbox_local_part = _as_text(identity.get("mailbox_local_part")) or _local_part(self._send_as_email(profile))
        if not tenant_id or not mailbox_local_part:
            return ""
        return f"aws-cms/smtp/{tenant_id}.{mailbox_local_part}"

    def _newsletter_profile(self, domain: str) -> dict[str, Any]:
        if self._newsletter_state is None or not domain:
            return {}
        try:
            payload = self._newsletter_state.load_profile(domain=domain)
        except Exception:  # noqa: BLE001
            return {}
        return payload if isinstance(payload, dict) else {}

    def _inbound_lambda_name(self, profile: dict[str, Any]) -> str:
        inbound = _as_dict(profile.get("inbound"))
        identity = _as_dict(profile.get("identity"))
        configured = _as_text(inbound.get("inbound_processor_lambda_name"))
        if configured:
            return configured
        newsletter_profile = self._newsletter_profile(_normalized_domain(identity.get("domain")))
        return _as_text(newsletter_profile.get("inbound_processor_lambda_name")) or _DEFAULT_INBOUND_LAMBDA

    def _domain_rule_name(self, domain: str) -> str:
        return f"portal-capture-{domain.replace('.', '-')}"

    def _normalized_record_token(self, value: object) -> str:
        return _as_text(value).lower().rstrip(".")

    def _registrar_nameservers(self, domain: str) -> list[str]:
        if not domain:
            return []
        try:
            response = self._client("route53domains", region=_DEFAULT_REGION).get_domain_detail(DomainName=domain)
        except Exception:  # noqa: BLE001
            return []
        nameservers = []
        for row in _as_list(response.get("Nameservers")):
            if not isinstance(row, dict):
                continue
            token = self._normalized_record_token(row.get("Name"))
            if token:
                nameservers.append(token)
        return sorted(set(nameservers))

    def _hosted_zone_nameservers(self, hosted_zone_id: str) -> list[str]:
        if not hosted_zone_id:
            return []
        try:
            response = self._client("route53").get_hosted_zone(Id=hosted_zone_id)
        except Exception:  # noqa: BLE001
            return []
        delegation = _as_dict(response.get("DelegationSet"))
        nameservers = [
            self._normalized_record_token(item)
            for item in _as_list(delegation.get("NameServers"))
            if self._normalized_record_token(item)
        ]
        return sorted(set(nameservers))

    def _route53_record_summary(
        self,
        *,
        hosted_zone_id: str,
        domain: str,
        region: str,
        dkim_tokens: list[Any],
    ) -> dict[str, Any]:
        if not hosted_zone_id:
            return {
                "mx_record_present": False,
                "mx_record_values": [],
                "dkim_records_present": False,
                "dkim_record_values": [],
            }
        try:
            response = self._client("route53").list_resource_record_sets(HostedZoneId=hosted_zone_id)
        except Exception:  # noqa: BLE001
            return {
                "mx_record_present": False,
                "mx_record_values": [],
                "dkim_records_present": False,
                "dkim_record_values": [],
            }
        records = [row for row in _as_list(response.get("ResourceRecordSets")) if isinstance(row, dict)]
        mx_values = [
            self._normalized_record_token(item.get("Value"))
            for row in records
            if self._normalized_record_token(row.get("Name")) == domain and _as_text(row.get("Type")) == "MX"
            for item in _as_list(row.get("ResourceRecords"))
            if isinstance(item, dict) and self._normalized_record_token(item.get("Value"))
        ]
        dkim_tokens_text = [token for token in (_as_text(item) for item in dkim_tokens) if token]
        matched_dkim_values: list[str] = []
        for token in dkim_tokens_text:
            expected_name = self._normalized_record_token(f"{token}._domainkey.{domain}")
            expected_value = self._normalized_record_token(f"{token}.dkim.amazonses.com")
            record = next(
                (
                    row
                    for row in records
                    if self._normalized_record_token(row.get("Name")) == expected_name and _as_text(row.get("Type")) == "CNAME"
                ),
                None,
            )
            if not isinstance(record, dict):
                continue
            values = [
                self._normalized_record_token(item.get("Value"))
                for item in _as_list(record.get("ResourceRecords"))
                if isinstance(item, dict) and self._normalized_record_token(item.get("Value"))
            ]
            if expected_value in values:
                matched_dkim_values.append(expected_value)
        expected_mx = self._normalized_record_token(f"10 inbound-smtp.{region}.amazonaws.com")
        return {
            "mx_record_present": expected_mx in mx_values,
            "mx_record_values": mx_values,
            "dkim_records_present": len(dkim_tokens_text) >= 3 and len(matched_dkim_values) >= 3,
            "dkim_record_values": matched_dkim_values,
        }

    def _domain_identity_summary(self, *, domain: str, region: str) -> dict[str, Any]:
        if not domain:
            return {
                "identity_exists": False,
                "identity_status": "not_started",
                "verified_for_sending_status": False,
                "dkim_status": "not_started",
                "dkim_tokens": [],
            }
        client = self._client("sesv2", region=region)
        try:
            response = client.get_email_identity(EmailIdentity=domain)
        except Exception as exc:  # noqa: BLE001
            message = _as_text(exc).lower()
            if "notfound" in message or "not found" in message:
                return {
                    "identity_exists": False,
                    "identity_status": "not_started",
                    "verified_for_sending_status": False,
                    "dkim_status": "not_started",
                    "dkim_tokens": [],
                }
            return {
                "identity_exists": False,
                "identity_status": "error",
                "verified_for_sending_status": False,
                "dkim_status": "error",
                "dkim_tokens": [],
            }
        dkim = _as_dict(response.get("DkimAttributes"))
        verification_status = _as_text(response.get("VerificationStatus")).upper()
        verified_for_sending = bool(response.get("VerifiedForSendingStatus"))
        identity_status = "not_started"
        if verification_status == "SUCCESS" and verified_for_sending:
            identity_status = "verified"
        elif verification_status:
            identity_status = verification_status.lower()
        dkim_status = _as_text(dkim.get("Status")).lower() or "not_started"
        return {
            "identity_exists": True,
            "identity_status": identity_status,
            "verified_for_sending_status": verified_for_sending,
            "dkim_status": dkim_status,
            "dkim_tokens": [token for token in (_as_text(item) for item in _as_list(dkim.get("Tokens"))) if token],
        }

    def _smtp_secret_material(self, *, secret_name: str, region: str) -> dict[str, Any]:
        client = self._client("secretsmanager", region=_DEFAULT_REGION)
        try:
            response = client.get_secret_value(SecretId=secret_name)
            secret_string = _as_text(response.get("SecretString"))
        except client.exceptions.ResourceNotFoundException:
            return {
                "secret_name": secret_name,
                "username": "",
                "persisted_username": "",
                "password": "",
                "smtp_host": f"email-smtp.{region}.amazonaws.com",
                "smtp_port": "587",
                "state": "missing",
                "message": "No SMTP secret exists yet.",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "secret_name": secret_name,
                "username": "",
                "persisted_username": "",
                "password": "",
                "smtp_host": f"email-smtp.{region}.amazonaws.com",
                "smtp_port": "587",
                "state": "error",
                "message": _as_text(exc) or "Unable to read SMTP secret material.",
            }
        payload: dict[str, Any] = {}
        if secret_string:
            try:
                parsed = json.loads(secret_string)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                payload = parsed
        username = _as_text(payload.get("username"))
        password = _as_text(payload.get("password"))
        is_placeholder = any(token.startswith("REPLACE_") for token in (username, password) if token)
        state = "configured" if username and password and not is_placeholder else ("placeholder" if (username or password) else "missing")
        return {
            "secret_name": secret_name,
            "username": username,
            "persisted_username": "" if is_placeholder else username,
            "password": password,
            "smtp_host": _as_text(payload.get("smtp_host")) or f"email-smtp.{region}.amazonaws.com",
            "smtp_port": _as_text(payload.get("smtp_port")) or "587",
            "state": state,
            "message": "",
        }

    def _ensure_smtp_secret_material(self, *, secret_name: str, region: str) -> dict[str, Any]:
        with self._smtp_provision_lock():
            current = self._smtp_secret_material(secret_name=secret_name, region=region)
            if _as_text(current.get("state")).lower() == "configured":
                return current
            active_keys = [
                row
                for row in self._list_smtp_access_keys()
                if _as_text(row.get("status")).lower() == "active"
            ]
            if len(active_keys) >= 2:
                reused = self._reuse_existing_smtp_secret_material(secret_name=secret_name, region=region)
                if _as_text(reused.get("state")).lower() == "configured":
                    return reused
                current["state"] = "quota_blocked"
                current["message"] = (
                    f"{_AWS_SMTP_IAM_USER} already has two active access keys; rotate or reuse existing SMTP material first."
                )
                return current
            try:
                created = self._create_smtp_secret_material(secret_name=secret_name, region=region)
            except Exception as exc:  # noqa: BLE001
                current["state"] = "error"
                current["message"] = _as_text(exc) or "Unable to materialize SMTP secret material."
                return current
            return created

    def _reuse_existing_smtp_secret_material(self, *, secret_name: str, region: str) -> dict[str, Any]:
        token = _as_text(secret_name)
        if not token:
            return {}
        prefix = "aws-cms/smtp/"
        suffix = token[len(prefix) :] if token.startswith(prefix) else token
        tenant_id = suffix.split(".", 1)[0].strip()
        if not tenant_id:
            return {}
        tenant_secret = f"{prefix}{tenant_id}"
        candidate_names = [tenant_secret]
        candidate_names.extend(
            name
            for name in self._list_smtp_secret_names(prefix=f"{prefix}{tenant_id}.")
            if _as_text(name)
        )
        seen: set[str] = set()
        ordered_candidates: list[str] = []
        for candidate in candidate_names:
            normalized = _as_text(candidate)
            if not normalized or normalized == token or normalized in seen:
                continue
            seen.add(normalized)
            ordered_candidates.append(normalized)
        # If tenant-local secrets are not configured, fall back to any configured SMTP secret.
        # This keeps staging operable when IAM SMTP keys are quota-blocked for new profiles.
        for candidate in sorted(self._list_smtp_secret_names(prefix=prefix)):
            normalized = _as_text(candidate)
            if not normalized or normalized == token or normalized in seen:
                continue
            seen.add(normalized)
            ordered_candidates.append(normalized)
        for candidate in ordered_candidates:
            material = self._smtp_secret_material(secret_name=candidate, region=region)
            if _as_text(material.get("state")).lower() != "configured":
                continue
            username = _as_text(material.get("persisted_username") or material.get("username"))
            password = _as_text(material.get("password"))
            if not username or not password:
                continue
            payload = {
                "username": username,
                "password": password,
                "iam_user": _AWS_SMTP_IAM_USER,
                "access_key_id": _as_text(material.get("access_key_id") or username),
                "smtp_region": region,
                "smtp_host": _as_text(material.get("smtp_host")) or f"email-smtp.{region}.amazonaws.com",
                "smtp_port": _as_text(material.get("smtp_port")) or "587",
                "tls_mode": "TLS",
                "provisioned_at": _utc_now_iso(),
                "reused_from_secret": candidate,
            }
            self._upsert_secret_payload(
                secret_name=token,
                payload=payload,
                description=_smtp_secret_description(token),
            )
            reused = self._smtp_secret_material(secret_name=token, region=region)
            reused["message"] = (
                f"SMTP secret material was reused from {candidate} because new IAM access keys are quota blocked."
            )
            reused["reused_from_secret"] = candidate
            return reused
        return {}

    def _list_smtp_secret_names(self, *, prefix: str) -> list[str]:
        token = _as_text(prefix)
        if not token:
            return []
        client = self._client("secretsmanager", region=_DEFAULT_REGION)
        collected: list[str] = []
        next_token = ""
        while True:
            kwargs: dict[str, Any] = {
                "Filters": [{"Key": "name", "Values": [token]}],
                "MaxResults": 100,
            }
            if next_token:
                kwargs["NextToken"] = next_token
            try:
                response = client.list_secrets(**kwargs)
            except Exception:  # noqa: BLE001
                return collected
            for row in _as_list(response.get("SecretList")):
                if not isinstance(row, dict):
                    continue
                name = _as_text(row.get("Name"))
                if name and name.startswith(token):
                    collected.append(name)
            next_token = _as_text(response.get("NextToken"))
            if not next_token:
                break
        collected.sort()
        return collected

    def _list_smtp_access_keys(self) -> list[dict[str, Any]]:
        try:
            payload = self._client("iam").list_access_keys(UserName=_AWS_SMTP_IAM_USER)
        except Exception:  # noqa: BLE001
            return []
        rows = payload.get("AccessKeyMetadata") if isinstance(payload, dict) else []
        out: list[dict[str, Any]] = []
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "access_key_id": _as_text(row.get("AccessKeyId")),
                    "status": _as_text(row.get("Status")),
                    "created_at": _as_text(row.get("CreateDate")),
                }
            )
        out.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return out

    def _create_smtp_secret_material(self, *, secret_name: str, region: str) -> dict[str, Any]:
        payload = self._client("iam").create_access_key(UserName=_AWS_SMTP_IAM_USER)
        access_key = _as_dict(payload.get("AccessKey"))
        access_key_id = _as_text(access_key.get("AccessKeyId"))
        secret_access_key = _as_text(access_key.get("SecretAccessKey"))
        if not access_key_id or not secret_access_key:
            raise ValueError("AWS IAM create_access_key did not return usable key material.")
        password = _aws_smtp_password(secret_access_key, region=region)
        secret_payload = {
            "username": access_key_id,
            "password": password,
            "iam_user": _AWS_SMTP_IAM_USER,
            "access_key_id": access_key_id,
            "smtp_region": region,
            "smtp_host": f"email-smtp.{region}.amazonaws.com",
            "smtp_port": "587",
            "tls_mode": "TLS",
            "provisioned_at": _utc_now_iso(),
        }
        self._upsert_secret_payload(
            secret_name=secret_name,
            payload=secret_payload,
            description=_smtp_secret_description(secret_name),
        )
        return {
            "secret_name": secret_name,
            "username": access_key_id,
            "persisted_username": access_key_id,
            "password": password,
            "smtp_host": secret_payload["smtp_host"],
            "smtp_port": secret_payload["smtp_port"],
            "state": "configured",
            "message": "SMTP secret material was created from the shared IAM sender user.",
        }

    def _upsert_secret_payload(self, *, secret_name: str, payload: dict[str, Any], description: str) -> None:
        client = self._client("secretsmanager", region=_DEFAULT_REGION)
        secret_string = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        try:
            client.update_secret(
                SecretId=secret_name,
                SecretString=secret_string,
                Description=description,
            )
        except client.exceptions.ResourceNotFoundException:
            client.create_secret(
                Name=secret_name,
                SecretString=secret_string,
                Description=description,
            )

    def _verification_route_map_from_profiles(self, *, profiles: list[dict[str, Any]]) -> dict[str, Any]:
        routes: dict[str, dict[str, Any]] = {}
        for profile in list(profiles or []):
            if not isinstance(profile, dict):
                continue
            identity = _as_dict(profile.get("identity"))
            smtp = _as_dict(profile.get("smtp"))
            send_as_email = _normalized_email(identity.get("send_as_email") or smtp.get("send_as_email"))
            forward_to_email = _normalized_email(smtp.get("forward_to_email") or identity.get("operator_inbox_target"))
            if not send_as_email or not forward_to_email:
                continue
            routes[send_as_email] = {
                "forward_to_email": forward_to_email,
                "profile_id": _as_text(identity.get("profile_id")),
                "domain": _normalized_domain(identity.get("domain")) or _email_domain(send_as_email),
                "handoff_provider": self._handoff_provider(profile),
            }
        resolved: dict[str, Any] = {}
        for send_as_email, route in sorted(routes.items()):
            resolved_forward_to_email, resolution_status, chain = self._resolve_forward_target(
                start_recipient=send_as_email,
                routes=routes,
            )
            destination = resolved_forward_to_email or _as_text(route.get("forward_to_email"))
            provider = _as_text(route.get("handoff_provider")) or "generic_manual"
            inferred_provider = _provider_from_email(destination)
            # Keep Lambda env payload compact so route-map sync remains under the 4KB env-var limit.
            # Use the shortest representation when provider can be inferred from destination.
            if provider == inferred_provider:
                resolved[send_as_email] = destination
                continue
            resolved[send_as_email] = {
                "f": destination,
                "p": provider,
                "s": resolution_status,
                "c": list(chain),
            }
        return resolved

    def _resolve_forward_target(
        self,
        *,
        start_recipient: str,
        routes: dict[str, dict[str, Any]],
    ) -> tuple[str, str, list[str]]:
        current = _normalized_email(start_recipient)
        chain: list[str] = []
        visited: set[str] = set()
        while current:
            if current in visited:
                chain.append(current)
                return current, "cycle_detected", chain
            visited.add(current)
            chain.append(current)
            route = _as_dict(routes.get(current))
            forward_to_email = _normalized_email(route.get("forward_to_email"))
            if not forward_to_email:
                return "", "missing_target", chain
            if forward_to_email == current:
                chain.append(forward_to_email)
                return forward_to_email, "resolved_self", chain
            if forward_to_email not in routes:
                chain.append(forward_to_email)
                return forward_to_email, "resolved_external", chain
            if len(chain) >= 24:
                chain.append(forward_to_email)
                return forward_to_email, "max_hops_exceeded", chain
            current = forward_to_email
        return "", "missing_target", chain

    def _verification_lambda_name(self, *, profiles: list[dict[str, Any]]) -> str:
        for profile in list(profiles or []):
            if not isinstance(profile, dict):
                continue
            lambda_name = _as_text(self._inbound_lambda_name(profile))
            if lambda_name:
                return lambda_name
        return _DEFAULT_INBOUND_LAMBDA

    def _wait_for_lambda_update(self, *, client: Any, function_name: str) -> None:
        deadline = time.time() + _ROUTE_MAP_SYNC_TIMEOUT_SECONDS
        while time.time() < deadline:
            payload = client.get_function_configuration(FunctionName=function_name)
            status = _as_text(payload.get("LastUpdateStatus"))
            state = _as_text(payload.get("State"))
            if status in {"Successful", ""} and state in {"Active", ""}:
                return
            if status == "Failed":
                raise ValueError(
                    f"Lambda route-map update failed for {function_name}: {_as_text(payload.get('LastUpdateStatusReason'))}"
                )
            time.sleep(2)
        raise TimeoutError(f"Timed out waiting for Lambda route-map update on {function_name}.")

    def _ses_identity_summary(self, *, region: str, email_identity: str) -> dict[str, Any]:
        identity = _as_text(email_identity)
        if not identity:
            return {
                "aws_ses_identity_status": "not_started",
                "message": "No SES identity target is configured.",
            }
        client = self._client("sesv2", region=region)
        try:
            response = client.get_email_identity(EmailIdentity=identity)
        except Exception as exc:  # noqa: BLE001
            message = _as_text(exc)
            lowered = message.lower()
            if "notfound" in lowered or "not found" in lowered:
                return {
                    "aws_ses_identity_status": "not_started",
                    "message": "SES identity has not been created for this domain yet.",
                }
            return {
                "aws_ses_identity_status": "error",
                "message": message or "Unable to query SES identity status.",
            }
        verification_status = _as_text(response.get("VerificationStatus")).upper()
        verified_for_sending = bool(response.get("VerifiedForSendingStatus"))
        aws_status = "not_started"
        if verification_status == "SUCCESS" and verified_for_sending:
            aws_status = "verified"
        elif verification_status:
            aws_status = verification_status.lower()
        return {
            "aws_ses_identity_status": aws_status,
            "message": "",
        }

    @contextmanager
    def _smtp_provision_lock(self) -> Iterator[None]:
        if self._private_dir is None:
            yield
            return
        lock_path = self._private_dir / "utilities" / "tools" / "aws-csm" / "smtp_provision.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


__all__ = ["AwsEc2RoleOnboardingCloudAdapter"]
