#!/usr/bin/env python3
"""Read-only AWS-CMS inspection helper for operator send-as staging.

This script is intentionally non-destructive. It reads the canonical staged
AWS-CMS profile, inspects matching AWS resources through the installed AWS CLI,
and emits a compact JSON report with classification hints.
"""

from __future__ import annotations

import argparse
import json
import smtplib
import ssl
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm")
DEFAULT_SEARCH_ROOTS = (
    Path("/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm"),
    Path("/srv/repo/mycite-core"),
)
SKIP_DIR_NAMES = {".git", ".venv", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".json", ".py", ".js", ".ts", ".md", ".txt", ".html"}
CLASS_CURRENT = "current and mappable"
CLASS_HARMLESS = "legacy but harmless"
CLASS_CONFLICTING = "legacy and conflicting"
CLASS_REQUIRED = "missing and required"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_hint_candidates(path: Path, payload: dict[str, Any]) -> set[str]:
    identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
    profile_id = str(identity.get("profile_id") or "").strip()
    candidates = {
        path.stem.removeprefix("aws-csm."),
        profile_id,
        profile_id.removeprefix("aws-csm.") if profile_id else "",
        str(identity.get("tenant_id") or "").strip(),
        str(identity.get("domain") or "").strip(),
    }
    return {item for item in candidates if item}


def _resolve_profile_path(root: Path, tenant: str) -> Path:
    exact = root / f"aws-csm.{tenant}.json"
    if exact.exists():
        return exact
    matches: list[Path] = []
    for path in sorted(root.glob("aws-csm.*.json")):
        if not path.is_file():
            continue
        payload = _safe_read_json(path)
        if tenant in _profile_hint_candidates(path, payload):
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    if matches:
        for path in matches:
            payload = _safe_read_json(path)
            identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
            if str(identity.get("tenant_id") or "").strip() != tenant:
                return path
        return matches[0]
    raise FileNotFoundError(f"profile not found under {root}: {tenant}")


def _run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    payload: Any = None
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = stdout
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "payload": payload,
    }


def _aws_command(*args: str, region: str | None = None) -> dict[str, Any]:
    command = ["aws"]
    if region:
        command.extend(["--region", region])
    command.extend(args)
    return _run_command(command)


def _looks_placeholder_secret_value(value: str) -> bool:
    token = str(value or "").strip()
    if not token:
        return False
    lowered = token.lower()
    if lowered in {"replace_me", "placeholder", "example"}:
        return True
    if token.startswith("<") and token.endswith(">"):
        return True
    markers = (
        "replace_me",
        "replace-with-real",
        "replace_with_real",
        "replace_with_",
        "replace_",
        "placeholder",
        "example",
    )
    return any(marker in lowered for marker in markers)


def _classify_secret_value(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        return "missing"
    if _looks_placeholder_secret_value(token):
        return "placeholder"
    return "present"


def _smtp_secret_health_from_payload(secret_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    username = str(payload.get("username") or "")
    password = str(payload.get("password") or "")
    return {
        "secret_name": secret_name,
        "keys": sorted(str(key) for key in payload.keys()),
        "username_state": _classify_secret_value(username),
        "password_state": _classify_secret_value(password),
        "smtp_auth_state": "not_attempted",
        "usable_for_handoff": False,
    }


def _smtp_auth_result(*, host: str, port: str, username: str, password: str) -> dict[str, str]:
    try:
        smtp_port = int(str(port or "587"))
    except ValueError:
        smtp_port = 587
    try:
        with smtplib.SMTP(host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(username, password)
        return {"state": "success", "error": ""}
    except Exception as exc:  # pragma: no cover - network failures vary in test hosts
        return {"state": "failed", "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _inspect_smtp_secret(secret_name: str, *, region: str, host: str, port: str) -> dict[str, Any]:
    response = _aws_command(
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        secret_name,
        "--query",
        "SecretString",
        "--output",
        "text",
        region=region,
    )
    summary: dict[str, Any] = {
        "secret_name": secret_name,
        "exists": bool(response.get("ok")),
        "keys": [],
        "username_state": "missing",
        "password_state": "missing",
        "smtp_auth_state": "not_attempted",
        "usable_for_handoff": False,
    }
    if not response.get("ok"):
        summary["fetch_error"] = str(response.get("stderr") or response.get("stdout") or "").strip()[:200]
        return summary

    secret_text = ""
    if isinstance(response.get("payload"), str):
        secret_text = str(response.get("payload") or "")
    elif isinstance(response.get("stdout"), str):
        secret_text = str(response.get("stdout") or "")
    try:
        payload = json.loads(secret_text) if secret_text else {}
    except json.JSONDecodeError:
        summary["parse_error"] = "secret-string is not valid JSON"
        return summary
    if not isinstance(payload, dict):
        summary["parse_error"] = "secret-string is not a JSON object"
        return summary

    summary.update(_smtp_secret_health_from_payload(secret_name, payload))
    username = str(payload.get("username") or "")
    password = str(payload.get("password") or "")
    if summary["username_state"] == "present" and summary["password_state"] == "present":
        auth = _smtp_auth_result(host=host, port=port, username=username, password=password)
        summary["smtp_auth_state"] = auth["state"]
        if auth["error"]:
            summary["smtp_auth_error"] = auth["error"]
        summary["usable_for_handoff"] = auth["state"] == "success"
    elif "placeholder" in {summary["username_state"], summary["password_state"]}:
        summary["smtp_auth_state"] = "placeholder_detected"
    return summary


def _exact_zone(hosted_zone_payload: dict[str, Any], domain: str) -> dict[str, Any] | None:
    zones = hosted_zone_payload.get("HostedZones") if isinstance(hosted_zone_payload, dict) else []
    needle = f"{domain.rstrip('.')}.".lower()
    for zone in zones or []:
        if not isinstance(zone, dict):
            continue
        if str(zone.get("Name") or "").lower() == needle:
            return zone
    return None


def _mail_records(
    records: list[dict[str, Any]],
    *,
    domain: str,
    dkim_tokens: list[str],
    mail_from_domain: str,
) -> list[dict[str, Any]]:
    relevant: list[dict[str, Any]] = []
    names = {
        f"{domain}.",
        f"_dmarc.{domain}.",
    }
    if mail_from_domain:
        names.add(f"{mail_from_domain}.")
    token_names = {f"{token}._domainkey.{domain}." for token in dkim_tokens if token}
    for record in records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("Name") or "")
        record_type = str(record.get("Type") or "")
        if record_type not in {"MX", "TXT", "CNAME"}:
            continue
        if name in names or name in token_names:
            relevant.append(record)
            continue
        if record_type == "CNAME" and name.endswith(f"._domainkey.{domain}."):
            relevant.append(record)
    return relevant


def _candidate_addresses(profile: dict[str, Any], domain_identity: dict[str, Any]) -> list[str]:
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    smtp = profile.get("smtp") if isinstance(profile.get("smtp"), dict) else {}
    domain = str(identity.get("domain") or "").strip().lower()
    out: list[str] = []
    for value in (
        identity.get("send_as_email"),
        smtp.get("send_as_email"),
    ):
        token = str(value or "").strip().lower()
        if token and token.endswith(f"@{domain}") and token not in out:
            out.append(token)
    mail_from = (
        ((domain_identity.get("MailFromAttributes") or {}) if isinstance(domain_identity, dict) else {}).get("MailFromDomain")
        if isinstance(domain_identity, dict)
        else ""
    )
    mail_from = str(mail_from or "").strip().lower()
    if mail_from and domain and mail_from.endswith(f".{domain}"):
        legacy_local = mail_from[: -(len(domain) + 1)]
        legacy_address = f"{legacy_local}@{domain}"
        if legacy_local and legacy_address not in out:
            out.append(legacy_address)
    if domain == "fruitfulnetworkdevelopment.com":
        for legacy in (
            "dcmontgomery@fruitfulnetworkdevelopment.com",
            "marilyn@fruitfulnetworkdevelopment.com",
        ):
            if legacy not in out:
                out.append(legacy)
    return out


def _search_references(terms: list[str], search_roots: tuple[Path, ...]) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {term: [] for term in terms if term}
    lowered_terms = {term: term.lower() for term in terms if term}
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lowered = text.lower()
            for needle, lowered_needle in lowered_terms.items():
                if lowered_needle not in lowered:
                    continue
                lines: list[str] = []
                for lineno, raw in enumerate(text.splitlines(), start=1):
                    if lowered_needle in raw.lower():
                        lines.append(f"{path}:{lineno}")
                    if len(lines) >= 5:
                        break
                findings.setdefault(needle, []).extend(lines)
    return findings


def _build_classification(
    *,
    tenant: str,
    profile: dict[str, Any],
    domain_identity: dict[str, Any],
    hosted_zone: dict[str, Any] | None,
    mail_records: list[dict[str, Any]],
    secrets: list[dict[str, Any]],
    smtp_secret_health: dict[str, Any],
    address_identities: dict[str, dict[str, Any]],
    active_receipt_rule_set: dict[str, Any] | None,
    referenced_buckets: dict[str, dict[str, Any]],
    referenced_lambdas: dict[str, dict[str, Any]],
    local_references: dict[str, list[str]],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    smtp = profile.get("smtp") if isinstance(profile.get("smtp"), dict) else {}
    domain = str(identity.get("domain") or "")
    canonical_sender = str(identity.get("send_as_email") or smtp.get("send_as_email") or "").strip().lower()
    domain_verified = (
        str(domain_identity.get("VerificationStatus") or "").upper() == "SUCCESS"
        and bool(domain_identity.get("VerifiedForSendingStatus"))
    )
    entries.append(
        {
            "item": f"SES domain identity {domain}",
            "source": "AWS SES",
            "classification": CLASS_CURRENT if domain_verified else CLASS_REQUIRED,
            "recommended_action": (
                "Keep as the canonical domain-level send-as identity."
                if domain_verified
                else "Verify the domain identity before continuing onboarding."
            ),
        }
    )

    secret_name = str(smtp.get("credentials_secret_name") or f"aws-cms/smtp/{tenant}")
    secret_entry = next((item for item in secrets if str(item.get("Name") or "") == secret_name), None)
    entries.append(
        {
            "item": f"SMTP secret reference {secret_name}",
            "source": "AWS Secrets Manager",
            "classification": CLASS_CURRENT if secret_entry else CLASS_REQUIRED,
            "recommended_action": (
                "Keep the secret reference external to profile JSON."
                if secret_entry
                else "Create the standardized SMTP secret before handoff."
            ),
        }
    )
    if smtp_secret_health:
        username_state = str(smtp_secret_health.get("username_state") or "missing")
        password_state = str(smtp_secret_health.get("password_state") or "missing")
        auth_state = str(smtp_secret_health.get("smtp_auth_state") or "not_attempted")
        payload_classification = CLASS_REQUIRED
        recommended_action = "Replace the secret contents with valid SES SMTP credentials before Gmail handoff."
        if bool(smtp_secret_health.get("usable_for_handoff")):
            payload_classification = CLASS_CURRENT
            recommended_action = "Keep the secret contents external; current SMTP credentials are usable for send-as handoff."
        elif "placeholder" in {username_state, password_state}:
            payload_classification = CLASS_REQUIRED
            recommended_action = "Replace placeholder-like secret values with real SES SMTP credentials before Gmail handoff."
        elif auth_state == "failed":
            payload_classification = CLASS_CONFLICTING
            recommended_action = "Rotate or repair the secret contents; the current values fail SMTP authentication."
        entries.append(
            {
                "item": f"SMTP secret payload {secret_name}",
                "source": "AWS Secrets Manager + SES SMTP auth",
                "classification": payload_classification,
                "recommended_action": recommended_action,
            }
        )

    dkim_records = [record for record in mail_records if str(record.get("Type") or "") == "CNAME"]
    entries.append(
        {
            "item": f"Route 53 DKIM records for {domain}",
            "source": "AWS Route 53",
            "classification": CLASS_CURRENT if dkim_records else CLASS_REQUIRED,
            "recommended_action": (
                "Keep the SES-issued DKIM records in place."
                if dkim_records
                else "Apply the SES-issued DKIM records."
            ),
        }
    )

    if hosted_zone:
        entries.append(
            {
                "item": f"Hosted zone {domain}",
                "source": "AWS Route 53",
                "classification": CLASS_CURRENT,
                "recommended_action": "Use the hosted zone for non-destructive DNS inspection and exact SES record placement.",
            }
        )

    mail_from = (
        ((domain_identity.get("MailFromAttributes") or {}) if isinstance(domain_identity, dict) else {}).get("MailFromDomain")
        if isinstance(domain_identity, dict)
        else ""
    )
    mail_from = str(mail_from or "")
    if mail_from:
        classification = CLASS_CURRENT
        recommended_action = "Keep the mail-from domain aligned with the canonical sender model."
        if canonical_sender and canonical_sender.split("@", 1)[0].lower() not in mail_from.lower():
            classification = CLASS_CONFLICTING
            recommended_action = (
                "Do not mutate live mail-from settings blindly. Plan a neutral or canonical mail-from replacement before cleanup."
            )
        entries.append(
            {
                "item": f"Custom MAIL FROM {mail_from}",
                "source": "AWS SES",
                "classification": classification,
                "recommended_action": recommended_action,
            }
        )

    legacy_record_names: set[str] = set()
    for record in mail_records:
        name = str(record.get("Name") or "")
        values = " ".join(item.get("Value") or "" for item in list(record.get("ResourceRecords") or []) if isinstance(item, dict))
        if name.startswith("_dmarc.") and "dcmontgomery@" in values.lower():
            entries.append(
                {
                    "item": f"DMARC record {name}",
                    "source": "AWS Route 53",
                    "classification": CLASS_CONFLICTING,
                    "recommended_action": "Retarget DMARC reporting to a canonical or neutral mailbox only after the legacy FND path is explicitly retired.",
                }
            )
        if name.startswith("dcmontgomery.") and name not in legacy_record_names:
            legacy_record_names.add(name)
            entries.append(
                {
                    "item": f"Legacy record {name}",
                    "source": "AWS Route 53",
                    "classification": CLASS_CONFLICTING,
                    "recommended_action": "Treat as part of the legacy dcmontgomery mail-from path; preview replacement before removal.",
                }
            )

    if active_receipt_rule_set:
        entries.append(
            {
                "item": f"Active receipt rule set {active_receipt_rule_set.get('Metadata', {}).get('Name', '')}",
                "source": "AWS SES inbound",
                "classification": CLASS_CONFLICTING,
                "recommended_action": "Keep for now, but do not treat inbound forwarding as part of the current AWS-CMS send-as baseline.",
            }
        )

    for bucket_name in sorted(referenced_buckets):
        bucket_info = referenced_buckets[bucket_name]
        latest_object = str(bucket_info.get("latest_object") or "")
        prefixes = ", ".join(str(item) for item in list(bucket_info.get("prefixes") or []) if item)
        prefix_hint = f" Prefixes: {prefixes}." if prefixes else ""
        latest_hint = f" Latest object: {latest_object}." if latest_object else ""
        entries.append(
            {
                "item": f"S3 bucket {bucket_name}",
                "source": "AWS S3",
                "classification": CLASS_CONFLICTING,
                "recommended_action": (
                    f"Bucket is tied to active inbound capture and should be treated as legacy inbound infrastructure.{prefix_hint}{latest_hint}"
                ).strip(),
            }
        )

    for function_name in sorted(referenced_lambdas):
        entries.append(
            {
                "item": f"Lambda {function_name}",
                "source": "AWS Lambda",
                "classification": CLASS_CONFLICTING,
                "recommended_action": "Treat as legacy inbound automation until the FND cleanup plan explicitly decides whether to keep or retire it.",
            }
        )

    if canonical_sender:
        refs = local_references.get(canonical_sender) or local_references.get(canonical_sender.lower()) or []
        entries.append(
            {
                "item": f"Canonical sender candidate {canonical_sender}",
                "source": "AWS-CMS staged profile and local code references",
                "classification": CLASS_CURRENT if refs else CLASS_REQUIRED,
                "recommended_action": (
                    "Use this as the reference FND sender path for future onboarding."
                    if refs
                    else "Stage this sender explicitly before treating it as canonical."
                ),
            }
        )

    for address, identity_info in address_identities.items():
        if identity_info.get("ok"):
            entries.append(
                {
                    "item": f"SES email identity {address}",
                    "source": "AWS SES",
                    "classification": CLASS_HARMLESS,
                    "recommended_action": "Review whether the explicit email identity is still needed now that domain-level send-as is the active model.",
                }
            )
    return entries


def inspect_profile(root: Path, tenant: str) -> dict[str, Any]:
    profile_path = _resolve_profile_path(root, tenant)
    profile = _safe_read_json(profile_path)
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    smtp = profile.get("smtp") if isinstance(profile.get("smtp"), dict) else {}
    provider = profile.get("provider") if isinstance(profile.get("provider"), dict) else {}
    domain = str(identity.get("domain") or "").strip().lower()
    region = str(identity.get("region") or "us-east-1").strip() or "us-east-1"
    canonical_sender = str(identity.get("send_as_email") or smtp.get("send_as_email") or "").strip().lower()
    smtp_host = str(smtp.get("host") or f"email-smtp.{region}.amazonaws.com").strip() or f"email-smtp.{region}.amazonaws.com"
    smtp_port = str(smtp.get("port") or "587").strip() or "587"
    secret_name = str(smtp.get("credentials_secret_name") or "").strip()
    if not secret_name:
        mailbox_local_part = str(identity.get("mailbox_local_part") or smtp.get("local_part") or "").strip()
        secret_name = f"aws-cms/smtp/{tenant}.{mailbox_local_part}" if mailbox_local_part else f"aws-cms/smtp/{tenant}"

    domain_identity_result = _aws_command("sesv2", "get-email-identity", "--email-identity", domain, region=region)
    domain_identity = domain_identity_result.get("payload") if isinstance(domain_identity_result.get("payload"), dict) else {}

    hosted_zone_result = _aws_command("route53", "list-hosted-zones-by-name", "--dns-name", domain, "--max-items", "1")
    hosted_zone_payload = hosted_zone_result.get("payload") if isinstance(hosted_zone_result.get("payload"), dict) else {}
    hosted_zone = _exact_zone(hosted_zone_payload, domain)

    hosted_zone_id = ""
    records: list[dict[str, Any]] = []
    if hosted_zone:
        hosted_zone_id = str(hosted_zone.get("Id") or "").split("/")[-1]
        record_result = _aws_command("route53", "list-resource-record-sets", "--hosted-zone-id", hosted_zone_id, "--max-items", "100")
        record_payload = record_result.get("payload") if isinstance(record_result.get("payload"), dict) else {}
        records = list(record_payload.get("ResourceRecordSets") or [])

    dkim_tokens = list((((domain_identity.get("DkimAttributes") or {}) if isinstance(domain_identity, dict) else {}).get("Tokens") or []))
    mail_from_domain = str((((domain_identity.get("MailFromAttributes") or {}) if isinstance(domain_identity, dict) else {}).get("MailFromDomain") or ""))
    relevant_mail_records = _mail_records(records, domain=domain, dkim_tokens=dkim_tokens, mail_from_domain=mail_from_domain)

    secrets_result = _aws_command(
        "secretsmanager",
        "list-secrets",
        "--query",
        "SecretList[?contains(Name, 'smtp') || contains(Name, 'ses') || contains(Name, 'mail')]",
        region=region,
    )
    secrets_payload = secrets_result.get("payload") if isinstance(secrets_result.get("payload"), list) else []
    smtp_secret_health = _inspect_smtp_secret(secret_name, region=region, host=smtp_host, port=smtp_port)

    addresses = _candidate_addresses(profile, domain_identity)
    address_identities: dict[str, dict[str, Any]] = {}
    for address in addresses:
        response = _aws_command("sesv2", "get-email-identity", "--email-identity", address, region=region)
        address_identities[address] = {
            "ok": bool(response.get("ok")),
            "stderr": str(response.get("stderr") or ""),
            "payload": response.get("payload") if isinstance(response.get("payload"), dict) else {},
        }

    receipt_rule_result = _aws_command("ses", "describe-active-receipt-rule-set", region=region)
    active_rule_set = receipt_rule_result.get("payload") if isinstance(receipt_rule_result.get("payload"), dict) else None
    relevant_rules: list[dict[str, Any]] = []
    referenced_buckets: dict[str, dict[str, Any]] = {}
    referenced_lambdas: dict[str, dict[str, Any]] = {}
    if active_rule_set:
        for rule in list(active_rule_set.get("Rules") or []):
            if not isinstance(rule, dict):
                continue
            recipients = [str(item or "").lower() for item in list(rule.get("Recipients") or [])]
            if not any(item == domain or item.endswith(f"@{domain}") for item in recipients):
                continue
            relevant_rules.append(rule)
            for action in list(rule.get("Actions") or []):
                if not isinstance(action, dict):
                    continue
                s3_action = action.get("S3Action") if isinstance(action.get("S3Action"), dict) else None
                if s3_action:
                    bucket_name = str(s3_action.get("BucketName") or "")
                    prefix = str(s3_action.get("ObjectKeyPrefix") or "")
                    if bucket_name:
                        bucket_info = referenced_buckets.setdefault(
                            bucket_name,
                            {
                                "prefixes": [],
                                "latest_object": "",
                            },
                        )
                        if prefix and prefix not in bucket_info["prefixes"]:
                            bucket_info["prefixes"].append(prefix)
                        listed = _aws_command(
                            "s3api",
                            "list-objects-v2",
                            "--bucket",
                            bucket_name,
                            "--prefix",
                            prefix,
                            region=region,
                        )
                        payload = listed.get("payload") if isinstance(listed.get("payload"), dict) else {}
                        objects = list(payload.get("Contents") or [])
                        if objects:
                            latest_object = max(str(item.get("LastModified") or "") for item in objects if isinstance(item, dict))
                            if latest_object > str(bucket_info.get("latest_object") or ""):
                                bucket_info["latest_object"] = latest_object
                lambda_action = action.get("LambdaAction") if isinstance(action.get("LambdaAction"), dict) else None
                if lambda_action:
                    function_arn = str(lambda_action.get("FunctionArn") or "")
                    function_name = function_arn.rsplit(":", 1)[-1]
                    if function_name and function_name not in referenced_lambdas:
                        config = _aws_command("lambda", "get-function-configuration", "--function-name", function_name, region=region)
                        referenced_lambdas[function_name] = {
                            "arn": function_arn,
                            "payload": config.get("payload") if isinstance(config.get("payload"), dict) else {},
                        }

    local_terms = [domain, canonical_sender] + [item for item in addresses if item != canonical_sender]
    local_references = _search_references(local_terms, DEFAULT_SEARCH_ROOTS)

    classification = _build_classification(
        tenant=tenant,
        profile=profile,
        domain_identity=domain_identity,
        hosted_zone=hosted_zone,
        mail_records=relevant_mail_records,
        secrets=list(secrets_payload or []),
        smtp_secret_health=smtp_secret_health,
        address_identities=address_identities,
        active_receipt_rule_set={"Metadata": (active_rule_set or {}).get("Metadata", {}), "Rules": relevant_rules} if active_rule_set else None,
        referenced_buckets=referenced_buckets,
        referenced_lambdas=referenced_lambdas,
        local_references=local_references,
    )

    return {
        "generated_at": _utc_now(),
        "canonical_root": str(root),
        "profile_path": str(profile_path),
        "tenant": tenant,
        "domain": domain,
        "canonical_sender": canonical_sender,
        "provider_last_checked_at": str(provider.get("last_checked_at") or ""),
        "profile": profile,
        "aws": {
            "ses_domain_identity": domain_identity,
            "hosted_zone": hosted_zone or {},
            "mail_records": relevant_mail_records,
            "smtp_secrets": list(secrets_payload or []),
            "smtp_secret_health": smtp_secret_health,
            "address_identities": address_identities,
            "active_receipt_rule_set": {"Metadata": (active_rule_set or {}).get("Metadata", {}), "Rules": relevant_rules}
            if active_rule_set
            else {},
            "referenced_buckets": referenced_buckets,
            "referenced_lambdas": referenced_lambdas,
        },
        "local_references": local_references,
        "classification": classification,
        "safe_next_steps": [
            (
                "Replace placeholder or non-working SMTP secret contents with valid SES SMTP credentials before Gmail handoff."
                if not bool(smtp_secret_health.get("usable_for_handoff"))
                else "SMTP credentials are usable; continue to Gmail send-as handoff."
            ),
            "Keep Gmail send-as verification as the next human handoff boundary unless an operator can complete it live.",
            "Do not remove legacy inbound FND resources until a previewed cleanup plan is approved.",
        ],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only AWS-CMS inspection helper.")
    parser.add_argument("--tenant", default="fnd", help="Tenant/profile token, for example: fnd, tff, cvcc")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Canonical aws-csm state root")
    parser.add_argument(
        "--write-report",
        default="",
        help="Optional path to save the JSON report. The command remains read-only for AWS resources.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).expanduser().resolve()
    report = inspect_profile(root, str(args.tenant).strip())
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.write_report:
        target = Path(args.write_report).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
