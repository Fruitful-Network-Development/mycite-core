from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, g, jsonify, make_response, request


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "portals").exists() and (parent / "tools").exists():
            return parent
    raise RuntimeError("Unable to resolve mycite-core repo root")


REPO_ROOT = _repo_root()
token = str(REPO_ROOT)
if token not in sys.path:
    sys.path.insert(0, token)

from tools.aws_csm.state_adapter.paths import aws_csm_state_root
from tools.aws_csm.state_adapter.profile import normalize_aws_csm_profile_payload
from tools.paypal_csm.state_adapter.paths import paypal_csm_state_root, paypal_csm_tenants_dir

_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_TENANT_PATH_RE = re.compile(r"^/portal/api/admin/(paypal|aws)/(?:tenant|profile)/([^/]+)/")
_FORBIDDEN_LOG_KEYS = {
    "secret",
    "token",
    "password",
    "client_secret",
    "authorization",
    "access_key",
    "secret_access_key",
    "session_token",
}
_MAX_CHECKOUT_PREVIEW_BYTES = 64 * 1024
_GMAIL_CONFIRMATION_SUBJECT_PREFIX = "Gmail Confirmation - Send Mail as "
_AWS_CLI_BIN = str(os.getenv("AWS_CLI_BIN", "aws")).strip() or "aws"
_AWS_CAPTURE_SCAN_LIMIT = 40


class _AwsProvisionError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = int(status_code)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _split_csv(value: str) -> set[str]:
    out: set[str] = set()
    for token in (value or "").replace(";", ",").split(","):
        item = token.strip()
        if item:
            out.add(item)
    return out


def _required_roles() -> set[str]:
    return _split_csv(os.getenv("PORTAL_ADMIN_ROLES", "admin"))


def _token_required(scope: str) -> str:
    scope_token = ""
    if scope == "paypal":
        scope_token = str(os.getenv("PAYPAL_PROXY_SHARED_TOKEN", "")).strip()
    elif scope == "aws":
        scope_token = str(os.getenv("AWS_PROXY_SHARED_TOKEN", "")).strip()
    if scope_token:
        return scope_token
    return str(os.getenv("PORTAL_ADMIN_SHARED_TOKEN", "")).strip()


def _request_id() -> str:
    current = getattr(g, "request_id", "")
    if current:
        return str(current)
    rid = (request.headers.get("X-Request-Id", "") or "").strip() or uuid.uuid4().hex
    g.request_id = rid
    return rid


def _portal_username() -> str:
    return (request.headers.get("X-Portal-Username", "") or "").strip()


def _safe_tenant_id(value: str) -> str:
    token = str(value or "").strip()
    if not _TENANT_ID_RE.fullmatch(token):
        raise ValueError("tenant_id must match [A-Za-z0-9._:-]{1,128}")
    return token


def _is_http_url(value: str) -> bool:
    token = str(value or "").strip()
    if not token:
        return False
    try:
        parsed = urlparse(token)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clean_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key or "").strip().lower() in _FORBIDDEN_LOG_KEYS:
            continue
        cleaned[key] = value
    return cleaned


def _contains_forbidden_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key or "").strip().lower() in _FORBIDDEN_LOG_KEYS:
                return True
            if _contains_forbidden_key(value):
                return True
        return False
    if isinstance(obj, list):
        return any(_contains_forbidden_key(item) for item in obj)
    return False


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return dict(default or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return dict(default or {})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_ndjson(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _aws_cli(args: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    env["AWS_PAGER"] = ""
    command = [_AWS_CLI_BIN, *args]
    completed = subprocess.run(
        command,
        input=input_bytes,
        capture_output=True,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        stderr = _decode_bytes(completed.stderr or b"").strip()
        stdout = _decode_bytes(completed.stdout or b"").strip()
        detail = stderr or stdout or f"{_AWS_CLI_BIN} exited {completed.returncode}"
        raise _AwsProvisionError(detail)
    return completed


def _aws_cli_json(args: list[str]) -> Any:
    completed = _aws_cli(args)
    stdout = _decode_bytes(completed.stdout or b"").strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise _AwsProvisionError(f"Unable to parse AWS CLI JSON output: {exc}") from exc


def _aws_cli_bytes(args: list[str]) -> bytes:
    completed = _aws_cli(args)
    return completed.stdout or b""


def _message_id_from_s3_key(key: str) -> str:
    return Path(str(key or "").strip()).name


def _extract_lambda_name(function_arn: str) -> str:
    token = str(function_arn or "").strip()
    if not token:
        return ""
    if ":" not in token:
        return token
    return token.rsplit(":", 1)[-1]


def _message_text_from_email(message: Any) -> str:
    if hasattr(message, "walk"):
        for part in message.walk():
            if str(part.get_content_type() or "").lower() != "text/plain":
                continue
            disposition = str(part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            try:
                return str(part.get_content() or "")
            except Exception:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = str(part.get_content_charset() or "utf-8")
                    return payload.decode(charset, errors="replace")
    payload = message.get_payload(decode=True)
    if payload:
        charset = str(message.get_content_charset() or "utf-8")
        return payload.decode(charset, errors="replace")
    try:
        return str(message.get_content() or "")
    except Exception:
        return ""


def _extract_confirmation_link(message_text: str) -> str:
    candidates = re.findall(r"https?://[^\s<>()\"']+", str(message_text or ""))
    for candidate in candidates:
        token = str(candidate or "").rstrip(".,)")
        lowered = token.lower()
        if "mail-settings.google.com" in lowered or "google.com" in lowered:
            return token
    return ""


def _safe_message_preview(message_payload: dict[str, Any] | None) -> dict[str, Any]:
    preview = dict(message_payload or {})
    if "confirmation_link" in preview:
        preview["has_confirmation_link"] = bool(preview.get("confirmation_link"))
        preview.pop("confirmation_link", None)
    return preview


def _parse_email_datetime(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    try:
        parsed = parsedate_to_datetime(token)
    except Exception:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _matching_receipt_rule(receipt_payload: dict[str, Any], *, domain: str) -> dict[str, Any]:
    rules = receipt_payload.get("Rules") if isinstance(receipt_payload.get("Rules"), list) else []
    domain_token = str(domain or "").strip().lower()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        recipients = [str(item or "").strip().lower() for item in list(rule.get("Recipients") or [])]
        if domain_token and domain_token in recipients:
            return rule
    if not domain_token:
        for rule in rules:
            if isinstance(rule, dict):
                return rule
    return {}


def _active_inbound_chain(*, region: str, domain: str) -> dict[str, Any]:
    receipt = _aws_cli_json(["--region", region, "ses", "describe-active-receipt-rule-set", "--output", "json"])
    metadata = receipt.get("Metadata") if isinstance(receipt.get("Metadata"), dict) else {}
    rule = _matching_receipt_rule(receipt if isinstance(receipt, dict) else {}, domain=domain)
    actions = rule.get("Actions") if isinstance(rule.get("Actions"), list) else []
    s3_action = {}
    lambda_action = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        if not s3_action and isinstance(action.get("S3Action"), dict):
            s3_action = dict(action.get("S3Action") or {})
        if not lambda_action and isinstance(action.get("LambdaAction"), dict):
            lambda_action = dict(action.get("LambdaAction") or {})
    function_name = _extract_lambda_name(str(lambda_action.get("FunctionArn") or ""))
    lambda_config = {}
    if function_name:
        lambda_config = _aws_cli_json(
            ["--region", region, "lambda", "get-function-configuration", "--function-name", function_name, "--output", "json"]
        )
    env_vars = (
        ((lambda_config.get("Environment") or {}) if isinstance(lambda_config, dict) else {}).get("Variables")
        if isinstance(lambda_config, dict)
        else {}
    )
    env_vars = env_vars if isinstance(env_vars, dict) else {}
    return {
        "receipt_rule_set": str(metadata.get("Name") or ""),
        "receipt_rule_name": str(rule.get("Name") or ""),
        "receipt_rule_recipients": [str(item or "") for item in list(rule.get("Recipients") or [])],
        "s3_bucket": str(s3_action.get("BucketName") or env_vars.get("S3_BUCKET") or ""),
        "s3_prefix": str(s3_action.get("ObjectKeyPrefix") or env_vars.get("S3_PREFIX") or ""),
        "lambda_function": function_name,
        "lambda_role_arn": str(lambda_config.get("Role") or ""),
        "lambda_last_modified": str(lambda_config.get("LastModified") or ""),
        "forward_to_email": str(env_vars.get("FORWARD_TO") or ""),
        "forward_from_email": str(env_vars.get("FROM_ADDRESS") or ""),
        "ses_region": str(env_vars.get("SES_REGION") or region),
    }


def _candidate_message_payload(raw_bytes: bytes, *, bucket: str, key: str, captured_at: str) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    message_text = _message_text_from_email(message)
    return {
        "message_id": _message_id_from_s3_key(key),
        "sender": _text(message.get("From")),
        "subject": _text(message.get("Subject")),
        "to": _text(message.get("To")),
        "message_date": _parse_email_datetime(_text(message.get("Date"))),
        "captured_at": _text(captured_at),
        "s3_bucket": bucket,
        "s3_key": key,
        "s3_uri": f"s3://{bucket}/{key}",
        "confirmation_link": _extract_confirmation_link(message_text),
        "plain_text": message_text,
    }


def _find_latest_verification_message(*, region: str, send_as_email: str, domain: str) -> tuple[dict[str, Any], dict[str, Any]]:
    chain = _active_inbound_chain(region=region, domain=domain)
    bucket = str(chain.get("s3_bucket") or "").strip()
    prefix = str(chain.get("s3_prefix") or "").strip()
    if not bucket:
        return {}, chain
    objects = _aws_cli_json(
        [
            "s3api",
            "list-objects-v2",
            "--bucket",
            bucket,
            "--prefix",
            prefix,
            "--output",
            "json",
            "--query",
            f"reverse(sort_by(Contents,&LastModified))[:{_AWS_CAPTURE_SCAN_LIMIT}].[Key,LastModified,Size]",
        ]
    )
    target = str(send_as_email or "").strip().lower()
    for item in list(objects or []):
        if not isinstance(item, list) or len(item) < 2:
            continue
        key = str(item[0] or "")
        captured_at = str(item[1] or "")
        raw_bytes = _aws_cli_bytes(["s3", "cp", f"s3://{bucket}/{key}", "-"])
        candidate = _candidate_message_payload(raw_bytes, bucket=bucket, key=key, captured_at=captured_at)
        subject = str(candidate.get("subject") or "")
        searchable = "\n".join(
            [
                str(candidate.get("sender") or ""),
                str(candidate.get("to") or ""),
                subject,
                str(candidate.get("plain_text") or ""),
            ]
        ).lower()
        if subject.startswith(_GMAIL_CONFIRMATION_SUBJECT_PREFIX) and target and target in searchable:
            candidate["plain_text"] = ""
            return candidate, chain
    return {}, chain


def _ses_identity_status(region: str, email_identity: str) -> dict[str, Any]:
    payload = _aws_cli_json(
        ["--region", region, "sesv2", "get-email-identity", "--email-identity", email_identity, "--output", "json"]
    )
    verification_status = str(payload.get("VerificationStatus") or "").strip().upper()
    verified_for_sending = bool(payload.get("VerifiedForSendingStatus"))
    aws_status = "not_started"
    if verification_status == "SUCCESS" and verified_for_sending:
        aws_status = "verified"
    elif verification_status:
        aws_status = verification_status.lower()
    return {
        "aws_ses_identity_status": aws_status,
        "identity_payload": payload if isinstance(payload, dict) else {},
    }


def _update_aws_profile(private_dir: Path, tenant_id: str, patch: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    _, path, exists = _aws_profile_status(private_dir, tenant_id)
    current_profile = _read_json(path, {}) if exists else {}
    merged = _deep_merge_dicts(current_profile, patch)
    normalized, validation_errors, warnings = normalize_aws_csm_profile_payload(merged, profile_hint=tenant_id)
    if validation_errors:
        raise _AwsProvisionError("; ".join(validation_errors), status_code=400)
    _write_json(path, normalized)
    return {
        "profile": normalized,
        "warnings": warnings,
        "profile_path": str(path),
    }, path


def _refresh_provider_status_for_profile(private_dir: Path, tenant_id: str) -> dict[str, Any]:
    status_payload, _, _ = _aws_profile_status(private_dir, tenant_id)
    profile = status_payload.get("profile") if isinstance(status_payload.get("profile"), dict) else {}
    canonical_profile_id, canonical_tenant_id = _aws_profile_refs(profile, tenant_id)
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    domain = str(identity.get("domain") or "").strip()
    region = str(identity.get("region") or "") or "us-east-1"
    provider_state = _ses_identity_status(region, domain)
    checked_at = _utc_now_iso()
    updated, _ = _update_aws_profile(
        private_dir,
        tenant_id,
        {
            "provider": {
                "aws_ses_identity_status": provider_state["aws_ses_identity_status"],
                "last_checked_at": checked_at,
            }
        },
    )
    return {
        "ok": True,
        "action": "refresh_provider_status",
        "status": "completed",
        "tenant_id": canonical_tenant_id,
        "profile_id": canonical_profile_id,
        "provider": {
            "aws_ses_identity_status": provider_state["aws_ses_identity_status"],
            "last_checked_at": checked_at,
            "identity_payload": provider_state["identity_payload"],
        },
        "profile": updated["profile"],
        "profile_path": updated["profile_path"],
        "warnings": updated["warnings"],
    }


def _refresh_inbound_status_for_profile(private_dir: Path, tenant_id: str) -> dict[str, Any]:
    status_payload, _, _ = _aws_profile_status(private_dir, tenant_id)
    profile = status_payload.get("profile") if isinstance(status_payload.get("profile"), dict) else {}
    canonical_profile_id, canonical_tenant_id = _aws_profile_refs(profile, tenant_id)
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    workflow = profile.get("workflow") if isinstance(profile.get("workflow"), dict) else {}
    inbound = profile.get("inbound") if isinstance(profile.get("inbound"), dict) else {}
    domain = str(identity.get("domain") or "").strip()
    region = str(identity.get("region") or "") or "us-east-1"
    send_as_email = str(identity.get("send_as_email") or ((profile.get("smtp") or {}) if isinstance(profile.get("smtp"), dict) else {}).get("send_as_email") or "").strip()
    message_payload, chain = _find_latest_verification_message(region=region, send_as_email=send_as_email, domain=domain)
    patch = {
        "inbound": {
            "receive_routing_target": str(inbound.get("receive_routing_target") or identity.get("operator_inbox_target") or ""),
            "legacy_forwarder_dependency": bool(inbound.get("legacy_forwarder_dependency")) or bool(chain.get("lambda_function")),
            "receive_verified": bool(inbound.get("receive_verified")),
            "receive_state": str(inbound.get("receive_state") or ("inbound_pending" if workflow.get("initiated") else "staged")),
            "latest_message_sender": "",
            "latest_message_subject": "",
            "latest_message_captured_at": "",
            "latest_message_s3_key": "",
            "latest_message_s3_uri": "",
        }
    }
    response_status = "completed"
    if message_payload:
        patch["inbound"].update(
            {
                "receive_verified": True,
                "receive_state": "inbound_verified",
                "latest_message_sender": str(message_payload.get("sender") or ""),
                "latest_message_subject": str(message_payload.get("subject") or ""),
                "latest_message_captured_at": str(message_payload.get("captured_at") or ""),
                "latest_message_s3_key": str(message_payload.get("s3_key") or ""),
                "latest_message_s3_uri": str(message_payload.get("s3_uri") or ""),
            }
        )
    elif not chain.get("s3_bucket"):
        response_status = "not_configured"
    updated, _ = _update_aws_profile(private_dir, tenant_id, patch)
    return {
        "ok": True,
        "action": "refresh_inbound_status",
        "status": response_status,
        "tenant_id": canonical_tenant_id,
        "profile_id": canonical_profile_id,
        "legacy_inbound": chain,
        "verification_message": {
            "sender": str(message_payload.get("sender") or ""),
            "subject": str(message_payload.get("subject") or ""),
            "captured_at": str(message_payload.get("captured_at") or ""),
            "s3_uri": str(message_payload.get("s3_uri") or ""),
            "message_id": str(message_payload.get("message_id") or ""),
            "confirmation_link": str(message_payload.get("confirmation_link") or ""),
        }
        if message_payload
        else {},
        "profile": updated["profile"],
        "profile_path": updated["profile_path"],
        "warnings": updated["warnings"],
    }


def _begin_onboarding_for_profile(private_dir: Path, tenant_id: str) -> dict[str, Any]:
    status_payload, _, _ = _aws_profile_status(private_dir, tenant_id)
    profile = status_payload.get("profile") if isinstance(status_payload.get("profile"), dict) else {}
    canonical_profile_id, canonical_tenant_id = _aws_profile_refs(profile, tenant_id)
    workflow = profile.get("workflow") if isinstance(profile.get("workflow"), dict) else {}
    initiated = bool(workflow.get("initiated"))
    initiated_at = str(workflow.get("initiated_at") or "")
    if not initiated:
        initiated = True
    if not initiated_at:
        initiated_at = _utc_now_iso()
    updated, _ = _update_aws_profile(
        private_dir,
        tenant_id,
        {
            "workflow": {
                "initiated": initiated,
                "initiated_at": initiated_at,
            }
        },
    )
    return {
        "ok": True,
        "action": "begin_onboarding",
        "status": "completed",
        "tenant_id": canonical_tenant_id,
        "profile_id": canonical_profile_id,
        "profile": updated["profile"],
        "profile_path": updated["profile_path"],
        "warnings": updated["warnings"],
    }


def _capture_verification_for_profile(private_dir: Path, tenant_id: str) -> dict[str, Any]:
    status_payload, _, _ = _aws_profile_status(private_dir, tenant_id)
    profile = status_payload.get("profile") if isinstance(status_payload.get("profile"), dict) else {}
    canonical_profile_id, canonical_tenant_id = _aws_profile_refs(profile, tenant_id)
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    smtp = profile.get("smtp") if isinstance(profile.get("smtp"), dict) else {}
    inbound = profile.get("inbound") if isinstance(profile.get("inbound"), dict) else {}
    workflow = profile.get("workflow") if isinstance(profile.get("workflow"), dict) else {}
    domain = str(identity.get("domain") or "").strip()
    region = str(identity.get("region") or "") or "us-east-1"
    send_as_email = str(smtp.get("send_as_email") or identity.get("send_as_email") or "").strip()
    message_payload, chain = _find_latest_verification_message(region=region, send_as_email=send_as_email, domain=domain)
    response = {
        "ok": True,
        "action": "capture_verification",
        "status": "not_found",
        "tenant_id": canonical_tenant_id,
        "profile_id": canonical_profile_id,
        "profile": profile,
        "legacy_inbound": chain,
        "verification_message": {},
    }
    if not message_payload:
        if not chain.get("s3_bucket"):
            response["status"] = "not_configured"
        return response
    verification = profile.get("verification") if isinstance(profile.get("verification"), dict) else {}
    patch = {
        "verification": {
            "email_received_at": str(message_payload.get("captured_at") or verification.get("email_received_at") or ""),
            "portal_state": "verified"
            if str(verification.get("status") or "").strip().lower() == "verified"
            else "verification_email_received",
        },
        "workflow": {
            "initiated": True,
            "initiated_at": str(workflow.get("initiated_at") or message_payload.get("captured_at") or ""),
        },
        "inbound": {
            "receive_routing_target": str(inbound.get("receive_routing_target") or identity.get("operator_inbox_target") or ""),
            "receive_state": "inbound_verified",
            "receive_verified": True,
            "legacy_forwarder_dependency": bool(inbound.get("legacy_forwarder_dependency")) or bool(chain.get("lambda_function")),
            "latest_message_sender": str(message_payload.get("sender") or ""),
            "latest_message_subject": str(message_payload.get("subject") or ""),
            "latest_message_captured_at": str(message_payload.get("captured_at") or ""),
            "latest_message_s3_key": str(message_payload.get("s3_key") or ""),
            "latest_message_s3_uri": str(message_payload.get("s3_uri") or ""),
        },
    }
    updated, _ = _update_aws_profile(private_dir, tenant_id, patch)
    response["status"] = "completed"
    response["profile"] = updated["profile"]
    response["profile_path"] = updated["profile_path"]
    response["warnings"] = updated["warnings"]
    response["verification_message"] = {
        "sender": str(message_payload.get("sender") or ""),
        "subject": str(message_payload.get("subject") or ""),
        "captured_at": str(message_payload.get("captured_at") or ""),
        "message_date": str(message_payload.get("message_date") or ""),
        "s3_bucket": str(message_payload.get("s3_bucket") or ""),
        "s3_key": str(message_payload.get("s3_key") or ""),
        "s3_uri": str(message_payload.get("s3_uri") or ""),
        "message_id": str(message_payload.get("message_id") or ""),
        "confirmation_link": str(message_payload.get("confirmation_link") or ""),
        "forward_to_email": str(chain.get("forward_to_email") or ""),
        "forward_from_email": str(chain.get("forward_from_email") or ""),
    }
    return response


def _replay_verification_forward(private_dir: Path, tenant_id: str) -> dict[str, Any]:
    capture = _capture_verification_for_profile(private_dir, tenant_id)
    verification_message = capture.get("verification_message") if isinstance(capture.get("verification_message"), dict) else {}
    legacy_inbound = capture.get("legacy_inbound") if isinstance(capture.get("legacy_inbound"), dict) else {}
    profile = capture.get("profile") if isinstance(capture.get("profile"), dict) else {}
    canonical_profile_id, canonical_tenant_id = _aws_profile_refs(profile, tenant_id)
    message_id = str(verification_message.get("message_id") or "")
    function_name = str(legacy_inbound.get("lambda_function") or "")
    region = str(legacy_inbound.get("ses_region") or "us-east-1")
    if not message_id or not function_name:
        return {
            "ok": True,
            "action": "replay_verification_forward",
            "status": "not_found",
            "tenant_id": canonical_tenant_id,
            "profile_id": canonical_profile_id,
            "legacy_inbound": legacy_inbound,
            "verification_message": verification_message,
        }
    with tempfile.NamedTemporaryFile("wb", delete=False) as payload_file:
        payload_file.write(
            json.dumps(
                {"Records": [{"ses": {"mail": {"messageId": message_id}}}]},
                separators=(",", ":"),
            ).encode("utf-8")
        )
        payload_path = payload_file.name
    with tempfile.NamedTemporaryFile("wb", delete=False) as output_file:
        output_path = output_file.name
    try:
        _aws_cli(
            [
                "--region",
                region,
                "lambda",
                "invoke",
                "--function-name",
                function_name,
                "--payload",
                f"fileb://{payload_path}",
                output_path,
            ]
        )
        try:
            lambda_result = json.loads(Path(output_path).read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            lambda_result = {"raw": Path(output_path).read_text(encoding="utf-8", errors="replace")}
    finally:
        try:
            os.unlink(payload_path)
        except OSError:
            pass
        try:
            os.unlink(output_path)
        except OSError:
            pass
    return {
        "ok": True,
        "action": "replay_verification_forward",
        "status": "completed",
        "tenant_id": canonical_tenant_id,
        "profile_id": canonical_profile_id,
        "verification_message": verification_message,
        "legacy_inbound": legacy_inbound,
        "lambda_result": lambda_result,
        "profile": capture.get("profile"),
        "profile_path": capture.get("profile_path"),
        "warnings": capture.get("warnings") or [],
    }


def _confirm_verified_for_profile(private_dir: Path, tenant_id: str) -> dict[str, Any]:
    status_payload, _, _ = _aws_profile_status(private_dir, tenant_id)
    profile = status_payload.get("profile") if isinstance(status_payload.get("profile"), dict) else {}
    canonical_profile_id, canonical_tenant_id = _aws_profile_refs(profile, tenant_id)
    verification = profile.get("verification") if isinstance(profile.get("verification"), dict) else {}
    workflow = profile.get("workflow") if isinstance(profile.get("workflow"), dict) else {}
    send_as_email = str(
        ((profile.get("identity") or {}) if isinstance(profile.get("identity"), dict) else {}).get("send_as_email") or ""
    )
    capture = _capture_verification_for_profile(private_dir, tenant_id)
    verification_message = capture.get("verification_message") if isinstance(capture.get("verification_message"), dict) else {}
    verified_at = _utc_now_iso()
    updated, _ = _update_aws_profile(
        private_dir,
        tenant_id,
        {
            "verification": {
                "status": "verified",
                "portal_state": "verified",
                "verified_at": verified_at,
                "email_received_at": str(
                    verification_message.get("captured_at") or verification.get("email_received_at") or ""
                ),
            },
            "provider": {
                "gmail_send_as_status": "verified",
                "last_checked_at": verified_at,
            },
            "workflow": {
                "initiated": True,
                "initiated_at": str(workflow.get("initiated_at") or verification.get("email_received_at") or verified_at),
            },
            "inbound": {
                "receive_verified": True,
                "receive_state": "inbound_verified",
                "receive_routing_target": str(
                    (((profile.get("inbound") or {}) if isinstance(profile.get("inbound"), dict) else {}).get("receive_routing_target"))
                    or (((profile.get("identity") or {}) if isinstance(profile.get("identity"), dict) else {}).get("operator_inbox_target"))
                    or ""
                ),
                "legacy_forwarder_dependency": bool(
                    (((profile.get("inbound") or {}) if isinstance(profile.get("inbound"), dict) else {}).get("legacy_forwarder_dependency"))
                    or bool(verification_message)
                ),
                "latest_message_sender": str(verification_message.get("sender") or ""),
                "latest_message_subject": str(verification_message.get("subject") or ""),
                "latest_message_captured_at": str(verification_message.get("captured_at") or ""),
                "latest_message_s3_key": str(verification_message.get("s3_key") or ""),
                "latest_message_s3_uri": str(verification_message.get("s3_uri") or ""),
            },
        },
    )
    return {
        "ok": True,
        "action": "confirm_verified",
        "status": "completed",
        "tenant_id": canonical_tenant_id,
        "profile_id": canonical_profile_id,
        "send_as_email": send_as_email,
        "verification_message": verification_message,
        "profile": updated["profile"],
        "profile_path": updated["profile_path"],
        "warnings": updated["warnings"],
        "verified_at": verified_at,
    }


def _admin_runtime_root(private_dir: Path) -> Path:
    root = private_dir / "admin_runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _legacy_paypal_root(private_dir: Path) -> Path:
    return _admin_runtime_root(private_dir) / "paypal"


def _paypal_root(private_dir: Path) -> Path:
    root = paypal_csm_state_root(private_dir)
    paypal_csm_tenants_dir(private_dir)
    return root


def _aws_csm_root(private_dir: Path) -> Path:
    return aws_csm_state_root(private_dir)


def _paypal_fnd_path(private_dir: Path) -> Path:
    return _paypal_root(private_dir) / "fnd.json"


def _paypal_tenant_path(private_dir: Path, tenant_id: str) -> Path:
    return paypal_csm_tenants_dir(private_dir) / f"{tenant_id}.json"


def _aws_csm_profile_paths(private_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in _aws_csm_root(private_dir).glob("aws-csm.*.json")
            if path.is_file() and path.name != "aws-csm.collection.json"
        ],
        key=lambda item: item.name.lower(),
    )


def _aws_csm_profile_file_token(profile_id: str) -> str:
    token = _safe_tenant_id(profile_id)
    if token.startswith("aws-csm."):
        return token.removeprefix("aws-csm.")
    return token


def _aws_csm_profile_path(private_dir: Path, profile_id: str) -> Path:
    token = _safe_tenant_id(profile_id)
    file_token = _aws_csm_profile_file_token(token)
    root = _aws_csm_root(private_dir)
    exact = root / f"aws-csm.{file_token}.json"
    if exact.exists() and exact.is_file():
        return exact
    legacy_alias_matches: dict[str, list[Path]] = {}
    for path in _aws_csm_profile_paths(private_dir):
        payload = _read_json(path, {})
        identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
        explicit_profile_id = str(identity.get("profile_id") or "").strip()
        candidates = {
            path.stem.removeprefix("aws-csm."),
            explicit_profile_id,
            explicit_profile_id.removeprefix("aws-csm.") if explicit_profile_id else "",
        }
        if token in {item for item in candidates if item} or file_token in {item for item in candidates if item}:
            return path
        tenant_key = str(identity.get("tenant_id") or "").strip()
        domain_key = str(identity.get("domain") or "").strip()
        if tenant_key:
            legacy_alias_matches.setdefault(tenant_key, []).append(path)
        if domain_key:
            legacy_alias_matches.setdefault(domain_key, []).append(path)
    for alias in (token, file_token):
        matches = legacy_alias_matches.get(alias) or []
        if len(matches) == 1:
            return matches[0]
    return exact


def _aws_actions_log(private_dir: Path) -> Path:
    return _aws_csm_root(private_dir) / "actions.ndjson"


def _aws_provision_log(private_dir: Path) -> Path:
    return _aws_csm_root(private_dir) / "provision_requests.ndjson"


def _deep_merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dicts(dict(out.get(key) or {}), value)
            continue
        out[key] = value
    return out


def _aws_profile_status(private_dir: Path, profile_id: str) -> tuple[dict[str, Any], Path, bool]:
    route_token = _safe_tenant_id(profile_id)
    route_file_token = _aws_csm_profile_file_token(route_token)
    hinted_tenant = route_file_token.split(".", 1)[0] if route_file_token else route_token
    hinted_mailbox = route_file_token.split(".", 1)[1] if "." in route_file_token else ""
    path = _aws_csm_profile_path(private_dir, route_token)
    exists = path.exists() and path.is_file()
    raw = (
        _read_json(path, {})
        if exists
        else {
            "identity": {
                "tenant_id": hinted_tenant,
                "profile_id": f"aws-csm.{route_file_token}" if route_file_token else "",
                "mailbox_local_part": hinted_mailbox,
            }
        }
    )
    profile, errors, warnings = normalize_aws_csm_profile_payload(raw, profile_hint=route_token)
    workflow = profile.get("workflow") if isinstance(profile.get("workflow"), dict) else {}
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    smtp = profile.get("smtp") if isinstance(profile.get("smtp"), dict) else {}
    provider = profile.get("provider") if isinstance(profile.get("provider"), dict) else {}
    inbound = profile.get("inbound") if isinstance(profile.get("inbound"), dict) else {}
    status = {
        "ok": True,
        "tenant_id": str(identity.get("tenant_id") or route_token),
        "profile_id": str(identity.get("profile_id") or ""),
        "configured": exists,
        "canonical_root": str(_aws_csm_root(private_dir)),
        "profile_path": str(path),
        "domain": str(identity.get("domain") or ""),
        "mailbox_local_part": str(identity.get("mailbox_local_part") or ""),
        "role": str(identity.get("role") or ""),
        "operator_inbox_target": str(identity.get("operator_inbox_target") or identity.get("single_user_email") or ""),
        "region": str(identity.get("region") or ""),
        "send_as_email": str(smtp.get("send_as_email") or ""),
        "single_user_email": str(identity.get("single_user_email") or ""),
        "gmail_send_as_status": str(provider.get("gmail_send_as_status") or ""),
        "aws_ses_identity_status": str(provider.get("aws_ses_identity_status") or ""),
        "handoff_ready": bool(workflow.get("is_ready_for_user_handoff")),
        "send_as_confirmed": bool(workflow.get("is_send_as_confirmed")),
        "initiated": bool(workflow.get("initiated")),
        "lifecycle_state": str(workflow.get("lifecycle_state") or ""),
        "receive_state": str(inbound.get("receive_state") or ""),
        "missing_required_now": list(workflow.get("missing_required_now") or []),
        "last_checked_at": str(provider.get("last_checked_at") or ""),
        "warnings": list(warnings or []),
        "validation_errors": list(errors or []),
        "profile": profile,
        "last_checked_unix_ms": int(time.time() * 1000),
    }
    return status, path, exists


def _aws_profile_refs(profile: dict[str, Any], route_token: str) -> tuple[str, str]:
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    canonical_profile_id = str(identity.get("profile_id") or "").strip()
    canonical_tenant_id = str(identity.get("tenant_id") or "").strip()
    route_file_token = _aws_csm_profile_file_token(route_token)
    route_profile_id = f"aws-csm.{route_file_token}" if route_file_token else route_token
    route_tenant_id = route_file_token.split(".", 1)[0] if route_file_token else route_token
    return canonical_profile_id or route_profile_id, canonical_tenant_id or route_tenant_id


def _paypal_actions_log(private_dir: Path) -> Path:
    return _paypal_root(private_dir) / "actions.ndjson"


def _paypal_orders_log(private_dir: Path) -> Path:
    return _paypal_root(private_dir) / "orders.ndjson"


def _paypal_profile_sync_log(private_dir: Path) -> Path:
    return _paypal_root(private_dir) / "profile_sync.ndjson"


def _resolve_legacy_root(private_dir: Path, scope: str) -> Path | None:
    env_key = "PORTAL_LEGACY_PAYPAL_STATE_DIR" if scope == "paypal" else "PORTAL_LEGACY_AWS_STATE_DIR"
    env_value = str(os.getenv(env_key, "")).strip()
    candidates: list[Path] = []
    if env_value:
        candidates.append(Path(env_value))
    if scope == "paypal":
        candidates.append(_legacy_paypal_root(private_dir))
    candidates.append(private_dir.parent / f"{scope}_proxy")
    candidates.append(Path(f"/srv/compose/portals/state/{scope}_proxy"))
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _copy_if_missing(dst: Path, src: Path) -> None:
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree_json_if_missing(dst_root: Path, src_root: Path) -> None:
    if not src_root.exists() or not src_root.is_dir():
        return
    for src in src_root.glob("*.json"):
        _copy_if_missing(dst_root / src.name, src)


def _bootstrap_state_from_legacy(private_dir: Path) -> None:
    paypal_legacy = _resolve_legacy_root(private_dir, "paypal")
    if paypal_legacy is not None:
        _copy_if_missing(_paypal_fnd_path(private_dir), paypal_legacy / "fnd.json")
        _copy_if_missing(_paypal_actions_log(private_dir), paypal_legacy / "actions.ndjson")
        _copy_if_missing(_paypal_orders_log(private_dir), paypal_legacy / "orders.ndjson")
        _copy_if_missing(_paypal_profile_sync_log(private_dir), paypal_legacy / "profile_sync.ndjson")
        _copy_tree_json_if_missing(_paypal_root(private_dir) / "tenants", paypal_legacy / "tenants")


def _append_action(private_dir: Path, scope: str, event_type: str, payload: dict[str, Any]) -> None:
    event = _clean_log_payload(dict(payload))
    event["type"] = event_type
    event["ts_unix_ms"] = int(time.time() * 1000)
    if scope == "paypal":
        _append_ndjson(_paypal_actions_log(private_dir), event)
    else:
        _append_ndjson(_aws_actions_log(private_dir), event)


def _tenant_from_path(path: str) -> str:
    match = _TENANT_PATH_RE.match(path or "")
    if not match:
        return ""
    return str(match.group(2) or "").strip()


def _require_admin_headers(scope: str):
    expected_token = _token_required(scope)
    if expected_token:
        got_token = (request.headers.get("X-Proxy-Token", "") or "").strip()
        if got_token != expected_token:
            return jsonify({"error": "Missing or invalid X-Proxy-Token."}), 401

    portal_user = (request.headers.get("X-Portal-User", "") or "").strip()
    if not portal_user:
        return jsonify({"error": "Missing X-Portal-User header."}), 401

    roles = sorted(_split_csv(request.headers.get("X-Portal-Roles", "")))
    required = _required_roles()
    if required and required.isdisjoint(set(roles)):
        return jsonify({"error": f"Admin role required. Need one of {sorted(required)}; got {roles}."}), 403

    g.portal_user = portal_user
    g.portal_roles = roles
    return None


def _validate_checkout_preview_payload(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ["payload.checkout_preview must be an object"]

    try:
        encoded = json.dumps(raw)
    except Exception:
        return None, ["payload.checkout_preview must be JSON-serializable"]
    if len(encoded.encode("utf-8")) > _MAX_CHECKOUT_PREVIEW_BYTES:
        errors.append(f"payload.checkout_preview exceeds {_MAX_CHECKOUT_PREVIEW_BYTES} bytes")
    if _contains_forbidden_key(raw):
        errors.append("payload.checkout_preview may not include secret-like keys")

    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    profile_id = str(source.get("paypal_profile_id") or "").strip()
    site_base_url = str(source.get("site_base_url") or "").strip()
    return_url = str(source.get("return_url") or "").strip()
    cancel_url = str(source.get("cancel_url") or "").strip()
    webhook_listener_url = str(source.get("webhook_listener_url") or "").strip()
    brand_name = str(source.get("brand_name") or "").strip()

    if not profile_id:
        errors.append("payload.checkout_preview.source.paypal_profile_id is required")
    if not return_url:
        errors.append("payload.checkout_preview.source.return_url is required")
    elif not _is_http_url(return_url):
        errors.append("payload.checkout_preview.source.return_url must be an absolute http/https URL")
    if not cancel_url:
        errors.append("payload.checkout_preview.source.cancel_url is required")
    elif not _is_http_url(cancel_url):
        errors.append("payload.checkout_preview.source.cancel_url must be an absolute http/https URL")
    if site_base_url and not _is_http_url(site_base_url):
        errors.append("payload.checkout_preview.source.site_base_url must be an absolute http/https URL")
    if webhook_listener_url and not _is_http_url(webhook_listener_url):
        errors.append("payload.checkout_preview.source.webhook_listener_url must be an absolute http/https URL")

    if errors:
        return None, errors
    return (
        {
            "paypal_profile_id": profile_id,
            "site_base_url": site_base_url,
            "return_url": return_url,
            "cancel_url": cancel_url,
            "webhook_listener_url": webhook_listener_url,
            "brand_name": brand_name,
        },
        [],
    )


def _options_response(allow: str):
    resp = make_response("", 204)
    resp.headers["Allow"] = allow
    return resp


def register_admin_integration_routes(app: Flask, *, private_dir: Path) -> None:
    _bootstrap_state_from_legacy(private_dir)

    @app.before_request
    def _admin_guard():
        path = request.path or ""
        if path.startswith("/portal/api/admin/paypal/"):
            return _require_admin_headers("paypal")
        if path.startswith("/portal/api/admin/aws/"):
            return _require_admin_headers("aws")
        return None

    @app.after_request
    def _admin_audit(response):
        rid = _request_id()
        response.headers["X-Request-Id"] = rid
        path = request.path or ""
        scope = ""
        if path.startswith("/portal/api/admin/paypal/"):
            scope = "paypal"
        elif path.startswith("/portal/api/admin/aws/"):
            scope = "aws"
        if scope:
            payload = {
                "request_id": rid,
                "portal_user": str(getattr(g, "portal_user", "") or request.headers.get("X-Portal-User", "")),
                "portal_username": _portal_username(),
                "portal_roles": list(getattr(g, "portal_roles", sorted(_split_csv(request.headers.get("X-Portal-Roles", ""))))),
                "tenant_id": _tenant_from_path(path),
                "scope": "tenant" if "/tenant/" in path else "fnd",
                "action": f"{request.method} {path}",
                "status_code": int(response.status_code),
            }
            try:
                _append_action(private_dir, scope, f"{scope}.audit.request", payload)
            except Exception:
                pass
        return response

    @app.get("/portal/api/admin/paypal/tenant/<tenant_id>/status")
    def admin_paypal_tenant_status(tenant_id: str):
        try:
            token = _safe_tenant_id(tenant_id)
        except ValueError as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400
        cfg = _read_json(_paypal_tenant_path(private_dir, token), {})
        response = {
            "ok": True,
            "tenant_id": token,
            "profile_id": str(cfg.get("profile_id") or f"paypal:tenant:{token}"),
            "configured": bool(cfg.get("configured", False)),
            "environment": str(cfg.get("environment") or "sandbox"),
            "last_checked_unix_ms": int(time.time() * 1000),
        }
        _append_action(private_dir, "paypal", "paypal.tenant.status.checked", response)
        return jsonify(response)

    @app.post("/portal/api/admin/paypal/tenant/<tenant_id>/profile/sync")
    def admin_paypal_tenant_profile_sync(tenant_id: str):
        try:
            token = _safe_tenant_id(tenant_id)
        except ValueError as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400

        body = request.get_json(silent=True) or {}
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
        action = str(body.get("action") or "checkout_profile_sync").strip().lower()
        if action not in {"checkout_profile_sync", "profile_sync", "sync"}:
            rejected = {
                "ok": False,
                "tenant_id": token,
                "action": action,
                "errors": ["action must be checkout_profile_sync"],
            }
            _append_action(private_dir, "paypal", "paypal.tenant.profile.sync.rejected", rejected)
            return jsonify(rejected), 400

        checkout_preview, validation_errors = _validate_checkout_preview_payload(payload.get("checkout_preview"))
        if validation_errors:
            rejected = {
                "ok": False,
                "tenant_id": token,
                "action": action,
                "errors": validation_errors,
            }
            _append_action(private_dir, "paypal", "paypal.tenant.profile.sync.rejected", rejected)
            return jsonify(rejected), 400

        cfg = _read_json(_paypal_tenant_path(private_dir, token), {})
        checkout_context = dict(checkout_preview or {})
        cfg["schema"] = str(cfg.get("schema") or "portals.paypal.tenant.config.v1")
        cfg["tenant_id"] = token
        cfg["profile_id"] = str(checkout_context.get("paypal_profile_id") or cfg.get("profile_id") or f"paypal:tenant:{token}")
        cfg["checkout_context"] = checkout_context
        cfg["environment"] = str(cfg.get("environment") or "sandbox")
        cfg["configured"] = bool(cfg.get("configured", False) or checkout_context.get("paypal_profile_id"))
        cfg["updated_unix_ms"] = int(time.time() * 1000)
        _write_json(_paypal_tenant_path(private_dir, token), cfg)

        request_id = f"PPSYNC-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8].upper()}"
        response = {
            "ok": True,
            "tenant_id": token,
            "request_id": request_id,
            "status": "queued",
            "action": "checkout_profile_sync",
            "environment": cfg["environment"],
            "paypal_profile_id": cfg["profile_id"],
            "checkout_context": checkout_context,
        }
        _append_ndjson(
            _paypal_profile_sync_log(private_dir),
            {
                "ts_unix_ms": int(time.time() * 1000),
                "tenant_id": token,
                "request_id": request_id,
                "action": "checkout_profile_sync",
                "checkout_context": checkout_context,
            },
        )
        _append_action(private_dir, "paypal", "paypal.tenant.profile.synced", response)
        return jsonify(response), 202

    @app.post("/portal/api/admin/paypal/tenant/<tenant_id>/orders/create")
    def admin_paypal_tenant_order_create(tenant_id: str):
        try:
            token = _safe_tenant_id(tenant_id)
        except ValueError as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400

        body = request.get_json(silent=True) or {}
        cfg = _read_json(_paypal_tenant_path(private_dir, token), {})
        configured = bool(cfg.get("configured", False))
        environment = str(cfg.get("environment") or "sandbox")
        checkout_context = cfg.get("checkout_context") if isinstance(cfg.get("checkout_context"), dict) else {}
        currency = str(body.get("currency") or "USD").upper()
        amount = str(body.get("amount") or "0.00")
        return_url = str(body.get("return_url") or checkout_context.get("return_url") or "").strip()
        cancel_url = str(body.get("cancel_url") or checkout_context.get("cancel_url") or "").strip()

        if return_url and not _is_http_url(return_url):
            payload = {"error": "return_url must be an absolute http/https URL", "tenant_id": token}
            _append_action(private_dir, "paypal", "paypal.tenant.order.create.rejected", payload)
            return jsonify(payload), 400
        if cancel_url and not _is_http_url(cancel_url):
            payload = {"error": "cancel_url must be an absolute http/https URL", "tenant_id": token}
            _append_action(private_dir, "paypal", "paypal.tenant.order.create.rejected", payload)
            return jsonify(payload), 400
        if not configured:
            payload = {"error": "Tenant PayPal profile is not configured.", "tenant_id": token, "configured": False}
            _append_action(private_dir, "paypal", "paypal.tenant.order.create.rejected", payload)
            return jsonify(payload), 409

        order_id = f"ORDER-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8].upper()}"
        if environment == "live":
            approval_url = f"https://www.paypal.com/checkoutnow?token={order_id}"
        else:
            approval_url = f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}"

        response = {
            "ok": True,
            "tenant_id": token,
            "environment": environment,
            "order_id": order_id,
            "approval_url": approval_url,
            "amount": amount,
            "currency": currency,
            "checkout_context": {
                "paypal_profile_id": str(checkout_context.get("paypal_profile_id") or cfg.get("profile_id") or ""),
                "site_base_url": str(checkout_context.get("site_base_url") or ""),
                "return_url": return_url,
                "cancel_url": cancel_url,
                "webhook_listener_url": str(checkout_context.get("webhook_listener_url") or ""),
                "brand_name": str(checkout_context.get("brand_name") or ""),
            },
        }
        _append_ndjson(
            _paypal_orders_log(private_dir),
            {
                "ts_unix_ms": int(time.time() * 1000),
                "tenant_id": token,
                "order_id": order_id,
                "environment": environment,
                "amount": amount,
                "currency": currency,
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        )
        _append_action(private_dir, "paypal", "paypal.tenant.order.created", response)
        return jsonify(response), 201

    @app.get("/portal/api/admin/paypal/fnd/status")
    def admin_paypal_fnd_status():
        cfg = _read_json(_paypal_fnd_path(private_dir), {})
        webhook = cfg.get("webhook") if isinstance(cfg.get("webhook"), dict) else {}
        response = {
            "ok": True,
            "scope": "fnd",
            "configured": bool(cfg.get("configured", False)),
            "environment": str(cfg.get("environment") or "sandbox"),
            "service_agreement_id": str(cfg.get("service_agreement_id") or ""),
            "webhook_url": str(webhook.get("target_url") or ""),
            "last_checked_unix_ms": int(time.time() * 1000),
        }
        _append_action(private_dir, "paypal", "paypal.fnd.status.checked", response)
        return jsonify(response)

    @app.post("/portal/api/admin/paypal/fnd/webhooks/register")
    def admin_paypal_fnd_webhook_register():
        body = request.get_json(silent=True) or {}
        cfg = _read_json(_paypal_fnd_path(private_dir), {})
        webhook_url = str(body.get("webhook_url") or "").strip()
        event_types = body.get("event_types")
        if not isinstance(event_types, list):
            event_types = ["PAYMENT.CAPTURE.COMPLETED"]

        webhook_id = f"WH-{uuid.uuid4().hex[:12].upper()}"
        cfg["configured"] = bool(cfg.get("configured", False) or webhook_url)
        cfg["environment"] = str(cfg.get("environment") or "sandbox")
        cfg["service_agreement_id"] = str(cfg.get("service_agreement_id") or "")
        cfg["webhook"] = {
            "id": webhook_id,
            "target_url": webhook_url,
            "event_types": [str(item).strip() for item in event_types if str(item).strip()],
        }
        cfg["updated_unix_ms"] = int(time.time() * 1000)
        _write_json(_paypal_fnd_path(private_dir), cfg)

        response = {
            "ok": True,
            "scope": "fnd",
            "status": "registered",
            "webhook_id": webhook_id,
            "webhook_url": webhook_url,
            "event_types": cfg["webhook"]["event_types"],
            "environment": cfg["environment"],
        }
        _append_action(private_dir, "paypal", "paypal.fnd.webhook.registered", response)
        return jsonify(response), 201

    def _aws_profile_status_response(profile_id: str):
        try:
            token = _safe_tenant_id(profile_id)
        except ValueError as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400
        response, _, _ = _aws_profile_status(private_dir, token)
        _append_action(private_dir, "aws", "aws.profile.status.checked", response)
        return jsonify(response)

    @app.get("/portal/api/admin/aws/profile/<profile_id>")
    def admin_aws_profile_status(profile_id: str):
        return _aws_profile_status_response(profile_id)

    @app.get("/portal/api/admin/aws/tenant/<tenant_id>/status")
    def admin_aws_tenant_status(tenant_id: str):
        response = _aws_profile_status_response(tenant_id)
        if response.status_code == 200:
            payload = response.get_json() or {}
            payload["deprecation"] = {
                "legacy_term": "tenant",
                "canonical_term": "profile",
                "canonical_endpoint": f"/portal/api/admin/aws/profile/{tenant_id}",
            }
            response.set_data(json.dumps(payload))
            response.mimetype = "application/json"
        return response

    @app.put("/portal/api/admin/aws/profile/<profile_id>")
    def admin_aws_profile_save(profile_id: str):
        try:
            token = _safe_tenant_id(profile_id)
        except ValueError as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400

        body = request.get_json(silent=True) or {}
        raw_profile = body.get("profile") if isinstance(body.get("profile"), dict) else body
        if not isinstance(raw_profile, dict):
            return jsonify({"ok": False, "errors": ["profile payload must be an object"]}), 400
        if _contains_forbidden_key(raw_profile):
            return jsonify({"ok": False, "errors": ["profile payload may not include secret-like keys"]}), 400

        current_status, path, exists = _aws_profile_status(private_dir, token)
        current_profile = _read_json(path, {}) if exists else {}
        merged = _deep_merge_dicts(current_profile, raw_profile)
        incoming_identity = raw_profile.get("identity") if isinstance(raw_profile.get("identity"), dict) else {}
        route_file_token = _aws_csm_profile_file_token(token)
        route_profile_id = f"aws-csm.{route_file_token}"
        incoming_tenant_id = str(incoming_identity.get("tenant_id") or "").strip()
        current_identity = current_profile.get("identity") if isinstance(current_profile.get("identity"), dict) else {}
        current_tenant_id = str(current_identity.get("tenant_id") or "").strip()
        current_profile_id = str(current_identity.get("profile_id") or "").strip()
        resolved_tenant_id = incoming_tenant_id or current_tenant_id or route_file_token.split(".", 1)[0]
        incoming_profile_id = str(incoming_identity.get("profile_id") or "").strip()
        allowed_profile_ids = {route_profile_id, token}
        if current_profile_id:
            allowed_profile_ids.add(current_profile_id)
            allowed_profile_ids.add(current_profile_id.removeprefix("aws-csm."))
        if incoming_profile_id and incoming_profile_id not in {item for item in allowed_profile_ids if item}:
            return jsonify({"ok": False, "errors": ["identity.profile_id must match the mailbox profile route token"]}), 400
        resolved_profile_id = current_profile_id or route_profile_id
        merged = _deep_merge_dicts(
            merged,
            {
                "identity": {
                    "tenant_id": resolved_tenant_id,
                    "profile_id": resolved_profile_id,
                }
            },
        )
        normalized, validation_errors, warnings = normalize_aws_csm_profile_payload(merged, profile_hint=token)
        if validation_errors:
            return jsonify({"ok": False, "errors": validation_errors, "warnings": warnings}), 400

        _write_json(path, normalized)
        response = {
            "ok": True,
            "tenant_id": str(((normalized.get("identity") or {}).get("tenant_id")) or resolved_tenant_id),
            "profile_id": str(((normalized.get("identity") or {}).get("profile_id")) or ""),
            "created": not exists,
            "canonical_root": str(_aws_csm_root(private_dir)),
            "profile_path": str(path),
            "warnings": warnings,
            "profile": normalized,
        }
        _append_action(
            private_dir,
            "aws",
            "aws.profile.saved",
            {
                "tenant_id": response["tenant_id"],
                "profile_id": response["profile_id"],
                "created": bool(response["created"]),
                "profile_path": response["profile_path"],
            },
        )
        return jsonify(response), 200

    @app.put("/portal/api/admin/aws/tenant/<tenant_id>/profile")
    def admin_aws_tenant_profile_save(tenant_id: str):
        return admin_aws_profile_save(tenant_id)

    @app.post("/portal/api/admin/aws/profile/<profile_id>/provision")
    def admin_aws_profile_provision(profile_id: str):
        try:
            token = _safe_tenant_id(profile_id)
        except ValueError as exc:
            return jsonify({"ok": False, "errors": [str(exc)]}), 400

        body = request.get_json(silent=True) or {}
        action = str(body.get("action") or "prepare_send_as").strip().lower()
        if "emailer" in action or "newsletter" in action:
            rejected = {
                "ok": False,
                "profile_id": token,
                "tenant_id": _aws_csm_profile_file_token(token).split(".", 1)[0],
                "errors": ["newsletter/emailer actions are not part of the active AWS-CMS scope"],
            }
            _append_action(private_dir, "aws", "aws.profile.provision.rejected", rejected)
            return jsonify(rejected), 400

        allowed_actions = {
            "begin_onboarding",
            "prepare_send_as",
            "setup_ses_identity",
            "setup_dkim",
            "stage_smtp_credentials",
            "capture_verification",
            "refresh_provider_status",
            "refresh_inbound_status",
            "enable_inbound_capture",
            "replay_verification_forward",
            "confirm_verified",
        }
        if action not in allowed_actions:
            rejected = {
                "ok": False,
                "profile_id": token,
                "tenant_id": _aws_csm_profile_file_token(token).split(".", 1)[0],
                "errors": [f"unsupported aws provision action: {action}"],
            }
            _append_action(private_dir, "aws", "aws.profile.provision.rejected", rejected)
            return jsonify(rejected), 400

        status_payload, path, exists = _aws_profile_status(private_dir, token)
        canonical_profile_id = str(status_payload.get("profile_id") or token)
        canonical_tenant_id = str(
            status_payload.get("tenant_id") or _aws_csm_profile_file_token(token).split(".", 1)[0] or token
        )
        if not exists:
            rejected = {
                "ok": False,
                "profile_id": canonical_profile_id,
                "tenant_id": canonical_tenant_id,
                "configured": False,
                "errors": ["AWS-CMS profile is not staged in the canonical aws-csm root"],
            }
            _append_action(private_dir, "aws", "aws.profile.provision.rejected", rejected)
            return jsonify(rejected), 409

        request_id = f"AWSREQ-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8].upper()}"
        if action in {
            "begin_onboarding",
            "refresh_provider_status",
            "refresh_inbound_status",
            "capture_verification",
            "replay_verification_forward",
            "confirm_verified",
        }:
            try:
                if action == "begin_onboarding":
                    response = _begin_onboarding_for_profile(private_dir, token)
                elif action == "refresh_provider_status":
                    response = _refresh_provider_status_for_profile(private_dir, token)
                elif action == "refresh_inbound_status":
                    response = _refresh_inbound_status_for_profile(private_dir, token)
                elif action == "capture_verification":
                    response = _capture_verification_for_profile(private_dir, token)
                elif action == "replay_verification_forward":
                    response = _replay_verification_forward(private_dir, token)
                else:
                    response = _confirm_verified_for_profile(private_dir, token)
            except _AwsProvisionError as exc:
                rejected = {
                    "ok": False,
                    "profile_id": canonical_profile_id,
                    "tenant_id": canonical_tenant_id,
                    "request_id": request_id,
                    "action": action,
                    "errors": [str(exc)],
                }
                _append_ndjson(
                    _aws_provision_log(private_dir),
                    {
                        "ts_unix_ms": int(time.time() * 1000),
                        "profile_id": canonical_profile_id,
                        "tenant_id": canonical_tenant_id,
                        "request_id": request_id,
                        "status": "failed",
                        "action": action,
                        "profile_path": str(path),
                        "region": str(status_payload.get("region") or ""),
                        "send_as_email": str(status_payload.get("send_as_email") or ""),
                        "error": str(exc),
                    },
                )
                _append_action(private_dir, "aws", "aws.profile.provision.failed", rejected)
                return jsonify(rejected), int(exc.status_code)

            response["request_id"] = request_id
            response["canonical_root"] = str(_aws_csm_root(private_dir))
            response["region"] = str(status_payload.get("region") or "")
            response["send_as_email"] = str(status_payload.get("send_as_email") or "")
            _append_ndjson(
                _aws_provision_log(private_dir),
                {
                    "ts_unix_ms": int(time.time() * 1000),
                    "profile_id": str(response.get("profile_id") or canonical_profile_id),
                    "tenant_id": str(response.get("tenant_id") or canonical_tenant_id),
                    "request_id": request_id,
                    "status": str(response.get("status") or "completed"),
                    "action": action,
                    "profile_path": str(response.get("profile_path") or path),
                    "region": response["region"],
                    "send_as_email": response["send_as_email"],
                },
            )
            _append_action(
                private_dir,
                "aws",
                "aws.profile.provision.completed",
                {
                    "tenant_id": str(response.get("tenant_id") or canonical_tenant_id),
                    "profile_id": str(response.get("profile_id") or canonical_profile_id),
                    "request_id": request_id,
                    "action": action,
                    "status": str(response.get("status") or "completed"),
                    "profile_path": str(response.get("profile_path") or path),
                    "verification_message": _safe_message_preview(
                        response.get("verification_message") if isinstance(response.get("verification_message"), dict) else {}
                    ),
                },
            )
            return jsonify(response), 200

        response = {
            "ok": True,
            "profile_id": canonical_profile_id,
            "tenant_id": canonical_tenant_id,
            "request_id": request_id,
            "status": "queued",
            "action": action,
            "canonical_root": str(_aws_csm_root(private_dir)),
            "profile_path": str(path),
            "region": str(status_payload.get("region") or ""),
            "send_as_email": str(status_payload.get("send_as_email") or ""),
        }
        _append_ndjson(
            _aws_provision_log(private_dir),
            {
                "ts_unix_ms": int(time.time() * 1000),
                "profile_id": canonical_profile_id,
                "tenant_id": canonical_tenant_id,
                "request_id": request_id,
                "status": "queued",
                "action": action,
                "profile_path": str(path),
                "region": response["region"],
                "send_as_email": response["send_as_email"],
            },
        )
        _append_action(private_dir, "aws", "aws.profile.provision.queued", response)
        return jsonify(response), 202

    @app.post("/portal/api/admin/aws/tenant/<tenant_id>/provision")
    def admin_aws_tenant_provision(tenant_id: str):
        return admin_aws_profile_provision(tenant_id)

    @app.get("/portal/api/admin/aws/fnd/status")
    def admin_aws_fnd_status():
        domain_filter = str(request.args.get("domain") or "").strip().lower()
        profiles = []
        ready_count = 0
        confirmed_count = 0
        for path in _aws_csm_profile_paths(private_dir):
            profile_token = path.stem.removeprefix("aws-csm.")
            status_payload, _, _ = _aws_profile_status(private_dir, profile_token)
            domain = str(status_payload.get("domain") or "").strip().lower()
            if domain_filter and domain != domain_filter:
                continue
            profiles.append(
                {
                    "profile_id": str(status_payload.get("profile_id") or profile_token),
                    "tenant_id": str(status_payload.get("tenant_id") or ""),
                    "domain": str(status_payload.get("domain") or ""),
                    "mailbox_local_part": str(status_payload.get("mailbox_local_part") or ""),
                    "role": str(status_payload.get("role") or ""),
                    "send_as_email": str(status_payload.get("send_as_email") or ""),
                    "operator_inbox_target": str(status_payload.get("operator_inbox_target") or ""),
                    "initiated": bool(status_payload.get("initiated")),
                    "lifecycle_state": str(status_payload.get("lifecycle_state") or ""),
                    "receive_state": str(status_payload.get("receive_state") or ""),
                    "handoff_ready": bool(status_payload.get("handoff_ready")),
                    "send_as_confirmed": bool(status_payload.get("send_as_confirmed")),
                }
            )
            if status_payload.get("handoff_ready"):
                ready_count += 1
            if status_payload.get("send_as_confirmed"):
                confirmed_count += 1
        profiles.sort(
            key=lambda item: (
                str(item.get("domain") or "").lower(),
                str(item.get("send_as_email") or "").lower(),
            )
        )
        domain_groups: dict[str, list[str]] = {}
        for item in profiles:
            domain_key = str(item.get("domain") or "").strip().lower()
            if not domain_key:
                continue
            domain_groups.setdefault(domain_key, []).append(str(item.get("profile_id") or ""))
        response = {
            "ok": True,
            "scope": "fnd",
            "canonical_root": str(_aws_csm_root(private_dir)),
            "domain_filter": domain_filter,
            "domain_groups": domain_groups,
            "tenant_profiles_count": len(profiles),
            "ready_for_handoff_count": ready_count,
            "send_as_confirmed_count": confirmed_count,
            "profiles": profiles,
            "last_checked_unix_ms": int(time.time() * 1000),
        }
        _append_action(private_dir, "aws", "aws.fnd.status.checked", response)
        return jsonify(response)

    @app.route("/portal/api/admin/paypal/tenant/<tenant_id>/status", methods=["OPTIONS"])
    @app.route("/portal/api/admin/paypal/tenant/<tenant_id>/profile/sync", methods=["OPTIONS"])
    @app.route("/portal/api/admin/paypal/tenant/<tenant_id>/orders/create", methods=["OPTIONS"])
    def admin_paypal_tenant_options(tenant_id: str):
        _ = tenant_id
        return _options_response("GET, POST, OPTIONS")

    @app.route("/portal/api/admin/paypal/fnd/status", methods=["OPTIONS"])
    @app.route("/portal/api/admin/paypal/fnd/webhooks/register", methods=["OPTIONS"])
    def admin_paypal_fnd_options():
        return _options_response("GET, POST, OPTIONS")

    @app.route("/portal/api/admin/aws/profile/<profile_id>", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/profile/<profile_id>/provision", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/tenant/<tenant_id>/status", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/tenant/<tenant_id>/profile", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/tenant/<tenant_id>/provision", methods=["OPTIONS"])
    def admin_aws_tenant_options(tenant_id: str | None = None, profile_id: str | None = None):
        _ = tenant_id
        _ = profile_id
        return _options_response("GET, PUT, POST, OPTIONS")

    @app.route("/portal/api/admin/aws/fnd/status", methods=["OPTIONS"])
    def admin_aws_fnd_options():
        return _options_response("GET, OPTIONS")
