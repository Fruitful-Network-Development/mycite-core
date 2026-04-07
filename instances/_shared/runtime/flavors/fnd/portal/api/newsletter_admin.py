from __future__ import annotations

import html
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, make_response, request

from instances._shared.runtime.flavors.fnd.portal.api.admin_integrations import _active_inbound_chain as _newsletter_active_inbound_chain
from packages.tools.newsletter_admin.state_adapter import (
    NEWSLETTER_PROFILE_SCHEMA,
    contact_summary,
    newsletter_dispatch_secret,
    load_contact_log,
    load_newsletter_profile,
    newsletter_contact_log_path,
    newsletter_domains,
    newsletter_signing_secret,
    resolve_newsletter_domain_state,
    save_contact_log,
    save_newsletter_profile,
    unsubscribe_contact_record,
    unsubscribe_token,
    upsert_contact_record,
)

_AWS_CLI_BIN = str(os.getenv("AWS_CLI_BIN", "aws")).strip() or "aws"
_AWS_CAPTURE_SCAN_LIMIT = 40


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _normalized_email(value: object) -> str:
    token = _text(value).lower()
    if not token or any(ch.isspace() for ch in token):
        return ""
    if token.count("@") != 1:
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _preserved_email(value: object) -> str:
    token = _text(value)
    for _name, address in getaddresses([token]):
        candidate = str(address or "").strip()
        if _normalized_email(candidate):
            return candidate
    return token if _normalized_email(token) else ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_csv(value: str) -> set[str]:
    out: set[str] = set()
    for token in (value or "").replace(";", ",").split(","):
        item = token.strip()
        if item:
            out.add(item)
    return out


def _required_roles() -> set[str]:
    return _split_csv(os.getenv("PORTAL_ADMIN_ROLES", "admin"))


def _portal_roles() -> set[str]:
    roles: set[str] = set()
    for header in ("X-Portal-Roles", "X-Portal-Role"):
        roles.update(_split_csv(request.headers.get(header, "")))
    return roles


def _portal_username() -> str:
    return _text(request.headers.get("X-Portal-Username") or request.headers.get("X-Portal-User"))


def _ensure_admin() -> tuple[bool, Response | None]:
    if not _required_roles():
        return True, None
    if _required_roles() & _portal_roles():
        return True, None
    return False, (jsonify({"ok": False, "error": "admin role required"}), 403)


def _normalize_domain(raw: str) -> str:
    token = _text(raw).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _request_domain(payload: dict[str, Any] | None = None) -> str:
    body = payload if isinstance(payload, dict) else {}
    explicit = _normalize_domain(_text(body.get("domain") or request.args.get("domain")))
    if explicit:
        return explicit
    host = _normalize_domain(_text(request.headers.get("Host")).split(":", 1)[0])
    return host


def _request_payload() -> dict[str, Any]:
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        return dict(body)
    return {key: _text(value) for key, value in request.form.items()}


def _wants_json() -> bool:
    accept = _text(request.headers.get("Accept")).lower()
    return "application/json" in accept or request.method == "POST"


def _html_message(title: str, message: str, *, status_code: int = 200) -> Response:
    markup = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:0 1rem;line-height:1.6;color:#25302b}"
        "main{border:1px solid #d8e0d7;border-radius:12px;padding:1.5rem 1.25rem;background:#fbfcfa}"
        "h1{margin-top:0;font-size:1.5rem}a{color:#275d57}</style></head><body><main>"
        f"<h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
        "</main></body></html>"
    )
    response = make_response(markup, status_code)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


def _aws_cli_json(args: list[str], *, input_payload: dict[str, Any] | None = None) -> Any:
    env = dict(os.environ)
    env["AWS_PAGER"] = ""
    command = [_AWS_CLI_BIN, *args]
    temp_path = ""
    if isinstance(input_payload, dict):
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        try:
            handle.write(json.dumps(input_payload, separators=(",", ":")))
            handle.close()
            temp_path = handle.name
            command.extend(["--cli-input-json", f"file://{temp_path}"])
        except Exception:
            try:
                handle.close()
            except Exception:
                pass
            raise
    try:
        completed = subprocess.run(command, capture_output=True, check=False, env=env)
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    if completed.returncode != 0:
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = (completed.stdout or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or stdout or f"{_AWS_CLI_BIN} exited {completed.returncode}")
    stdout = (completed.stdout or b"").decode("utf-8", errors="replace").strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw": stdout}


def _aws_cli_bytes(args: list[str]) -> bytes:
    env = dict(os.environ)
    env["AWS_PAGER"] = ""
    completed = subprocess.run([_AWS_CLI_BIN, *args], capture_output=True, check=False, env=env)
    if completed.returncode != 0:
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = (completed.stdout or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or stdout or f"{_AWS_CLI_BIN} exited {completed.returncode}")
    return completed.stdout or b""


def _render_text_body(content: str, unsubscribe_url: str) -> str:
    body = _text(content)
    out = body.rstrip()
    if out:
        out += "\n\n"
    out += f"Unsubscribe: {unsubscribe_url}\n"
    return out


def _render_html_body(content: str, unsubscribe_url: str) -> str:
    paragraphs = [segment.strip() for segment in _text(content).splitlines()]
    body = "".join(f"<p>{html.escape(segment)}</p>" for segment in paragraphs if segment)
    if not body:
        body = "<p>(No message body provided.)</p>"
    body += (
        "<hr><p style=\"font-size:0.95rem;color:#47524b\">"
        f"If you no longer want these updates, <a href=\"{html.escape(unsubscribe_url)}\">unsubscribe here</a>."
        "</p>"
    )
    return body


def _render_submission_text_body(content: str) -> str:
    return _text(content).rstrip() + "\n"


def _render_submission_html_body(content: str) -> str:
    paragraphs = [segment.strip() for segment in _text(content).splitlines()]
    body = "".join(f"<p>{html.escape(segment)}</p>" for segment in paragraphs if segment)
    return body or "<p>(No message body provided.)</p>"


def _message_text_from_email(message: Any) -> str:
    if hasattr(message, "walk"):
        for part in message.walk():
            if str(part.get_content_type() or "").lower() != "text/plain":
                continue
            if str(part.get_content_disposition() or "").lower() == "attachment":
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


def _candidate_message_payload(raw_bytes: bytes, *, bucket: str, key: str, captured_at: str) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    return {
        "message_id": Path(str(key or "").strip()).name,
        "sender": _text(message.get("From")),
        "subject": _text(message.get("Subject")),
        "recipient": _text(message.get("To")),
        "to": _text(message.get("To")),
        "captured_at": _text(captured_at),
        "s3_bucket": bucket,
        "s3_key": key,
        "s3_uri": f"s3://{bucket}/{key}",
        "plain_text": _message_text_from_email(message),
    }


def _email_addresses(value: object) -> set[str]:
    out: set[str] = set()
    token = _text(value)
    for _name, address in getaddresses([token]):
        normalized = _normalized_email(address)
        if normalized:
            out.add(normalized)
    fallback = _normalized_email(token)
    if fallback:
        out.add(fallback)
    return out


def _latest_inbound_newsletter_message(
    *,
    region: str,
    domain: str,
    expected_sender: str,
    expected_recipient: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    chain = _newsletter_active_inbound_chain(region=region, domain=domain)
    bucket = _text(chain.get("s3_bucket"))
    prefix = _text(chain.get("s3_prefix"))
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
    sender_token = _normalized_email(expected_sender)
    recipient_token = _normalized_email(expected_recipient)
    for item in list(objects or []):
        if not isinstance(item, list) or len(item) < 2:
            continue
        key = _text(item[0])
        captured_at = _text(item[1])
        raw_bytes = _aws_cli_bytes(["s3", "cp", f"s3://{bucket}/{key}", "-"])
        candidate = _candidate_message_payload(raw_bytes, bucket=bucket, key=key, captured_at=captured_at)
        senders = _email_addresses(candidate.get("sender"))
        recipients = _email_addresses(candidate.get("recipient")) | _email_addresses(candidate.get("to"))
        if sender_token and sender_token not in senders:
            continue
        if recipient_token and recipient_token not in recipients:
            continue
        if not _text(candidate.get("subject")) and not _text(candidate.get("plain_text")):
            continue
        return candidate, chain
    return {}, chain


def _newsletter_callback_url(profile: dict[str, Any], domain: str) -> str:
    token = _text((profile or {}).get("dispatcher_callback_url"))
    if token:
        return token
    return f"https://{_text(domain).lower()}/__fnd/newsletter/dispatch-result"


def _queue_inbound_newsletter(
    private_dir: Path,
    *,
    domain: str,
    inbound_message: dict[str, Any],
) -> dict[str, Any]:
    state = resolve_newsletter_domain_state(private_dir, domain)
    profile = dict(state.get("profile") or {})
    selected = dict(state.get("selected_author") or state.get("selected_sender") or {})
    author_address = _preserved_email(inbound_message.get("sender")) or _preserved_email(selected.get("send_as_email"))
    if not author_address:
        raise RuntimeError(f"No verified sender is available for {domain}")
    queue_url = _text(profile.get("dispatch_queue_url"))
    if not queue_url:
        raise RuntimeError(f"Newsletter queue is not configured for {domain}")
    delivery_mode = _text(profile.get("delivery_mode")) or "aws_sqs_lambda_us_east_1"
    if delivery_mode != "aws_sqs_lambda_us_east_1":
        raise RuntimeError(f"Unsupported newsletter delivery mode for {domain}: {delivery_mode}")
    region = _text(profile.get("aws_region")) or "us-east-1"
    subject = _text(inbound_message.get("subject"))
    body_text = _text(inbound_message.get("plain_text")).strip()
    if not subject:
        raise RuntimeError("Inbound newsletter is missing a subject")
    if not body_text:
        raise RuntimeError("Inbound newsletter is missing a plain-text body")
    recipients = [
        dict(item)
        for item in list(state.get("contacts") or [])
        if isinstance(item, dict) and bool(item.get("subscribed")) and _normalized_email(item.get("email"))
    ]
    if not recipients:
        raise RuntimeError(f"No subscribed contacts are available for {domain}")
    secret = newsletter_signing_secret(private_dir)
    callback_secret = newsletter_dispatch_secret(private_dir)
    dispatch_id = f"dispatch-{uuid.uuid4().hex}"
    list_address = _text(state.get("list_address")) or f"news@{domain}"
    sender_address = _text(profile.get("sender_address")) or list_address
    callback_url = _newsletter_callback_url(profile, domain)
    results: list[dict[str, Any]] = []
    path, contact_log = load_contact_log(private_dir, domain)
    for recipient in recipients:
        email = _normalized_email(recipient.get("email"))
        if not email:
            continue
        token = unsubscribe_token(secret, domain=domain, email=email)
        unsubscribe_url = f"https://{domain}/__fnd/newsletter/unsubscribe?email={email}&token={token}"
        message_body = {
            "domain": _text(domain).lower(),
            "dispatch_id": dispatch_id,
            "recipient_email": email,
            "sender_address": sender_address,
            "reply_to_address": author_address,
            "author_address": author_address,
            "author_profile_id": _text(selected.get("profile_id")),
            "list_address": list_address,
            "subject": _text(subject),
            "body_text": _text(body_text),
            "unsubscribe_url": unsubscribe_url,
            "callback_url": callback_url,
            "callback_token": callback_secret,
            "aws_region": region,
            "source_kind": "inbound_email",
            "source_message_id": _text(inbound_message.get("message_id")),
            "source_message_s3_uri": _text(inbound_message.get("s3_uri")),
        }
        result_row = {
            "email": email,
            "status": "queued",
            "unsubscribe_url": unsubscribe_url,
        }
        try:
            queued = _aws_cli_json(
                ["sqs", "send-message", "--region", region, "--output", "json"],
                input_payload={
                    "QueueUrl": queue_url,
                    "MessageBody": json.dumps(message_body, separators=(",", ":")),
                },
            )
            result_row["queue_message_id"] = _text((queued or {}).get("MessageId"))
        except Exception as exc:
            result_row["status"] = "failed"
            result_row["error"] = _text(exc)
        results.append(result_row)
    now_iso = _utc_now_iso()
    dispatch_row = {
        "dispatch_id": dispatch_id,
        "requested_at": now_iso,
        "completed_at": "",
        "requested_by": _portal_username(),
        "domain": _text(domain).lower(),
        "author_profile_id": _text(selected.get("profile_id")),
        "author_address": author_address,
        "sender_profile_id": _text(selected.get("profile_id")),
        "sender_address": sender_address,
        "list_address": list_address,
        "reply_to_address": author_address,
        "subject": _text(subject),
        "body_text": _text(body_text),
        "target_count": len(recipients),
        "queued_count": sum(1 for row in results if _text(row.get("status")) == "queued"),
        "sent_count": 0,
        "failed_count": sum(1 for row in results if _text(row.get("status")) == "failed"),
        "delivery_mode": delivery_mode,
        "aws_region": region,
        "source_kind": "inbound_email",
        "source_message_id": _text(inbound_message.get("message_id")),
        "source_message_s3_uri": _text(inbound_message.get("s3_uri")),
        "source_message_captured_at": _text(inbound_message.get("captured_at")),
        "status": "queued",
        "results": results,
    }
    contact_log["dispatches"] = list(contact_log.get("dispatches") or [])[-19:] + [dispatch_row]
    save_contact_log(path, contact_log)
    return dispatch_row


def _persist_inbound_status(
    private_dir: Path,
    *,
    domain: str,
    profile: dict[str, Any],
    message_payload: dict[str, Any] | None,
    status: str,
    error: str = "",
    dispatch_id: str = "",
) -> None:
    profile_path, current = load_newsletter_profile(private_dir, domain)
    body = dict(current)
    body.update(dict(profile or {}))
    message = dict(message_payload or {})
    body["last_inbound_message_id"] = _text(message.get("message_id"))
    body["last_inbound_status"] = _text(status)
    body["last_inbound_checked_at"] = _utc_now_iso()
    body["last_inbound_subject"] = _text(message.get("subject"))
    body["last_inbound_sender"] = _text(message.get("sender"))
    body["last_inbound_recipient"] = _text(message.get("recipient") or message.get("to"))
    body["last_inbound_s3_uri"] = _text(message.get("s3_uri"))
    body["last_inbound_error"] = _text(error)
    if _text(status) == "processed":
        body["last_inbound_processed_at"] = _utc_now_iso()
    if dispatch_id:
        body["last_dispatch_id"] = dispatch_id
    save_newsletter_profile(profile_path, body)


def process_latest_inbound_newsletter(private_dir: Path, *, domain: str) -> dict[str, Any]:
    state = resolve_newsletter_domain_state(private_dir, domain)
    profile = dict(state.get("profile") or {})
    selected = dict(state.get("selected_author") or state.get("selected_sender") or {})
    author_address = _normalized_email(selected.get("send_as_email"))
    list_address = _normalized_email(state.get("list_address") or f"news@{domain}")
    if not author_address:
        _persist_inbound_status(private_dir, domain=domain, profile=profile, message_payload=None, status="blocked", error="selected sender is not verified")
        return {"ok": False, "error": "selected sender is not verified for this domain"}
    try:
        message_payload, chain = _latest_inbound_newsletter_message(
            region=_text(profile.get("aws_region")) or "us-east-1",
            domain=domain,
            expected_sender=author_address,
            expected_recipient=list_address,
        )
    except Exception as exc:
        _persist_inbound_status(private_dir, domain=domain, profile=profile, message_payload=None, status="error", error=_text(exc))
        return {"ok": False, "error": _text(exc)}
    if not message_payload:
        _persist_inbound_status(private_dir, domain=domain, profile=profile, message_payload=None, status="no_message", error="no captured inbound newsletter matched the selected sender")
        return {"ok": False, "error": "no captured inbound newsletter matched the selected sender", "inbound_chain": chain}
    if _text(profile.get("last_inbound_message_id")) == _text(message_payload.get("message_id")) and _text(profile.get("last_inbound_status")) == "processed":
        _persist_inbound_status(private_dir, domain=domain, profile=profile, message_payload=message_payload, status="already_processed", dispatch_id=_text(profile.get("last_dispatch_id")))
        return {
            "ok": True,
            "already_processed": True,
            "dispatch_id": _text(profile.get("last_dispatch_id")),
            "inbound_message": message_payload,
            "inbound_chain": chain,
        }
    sender_addresses = _email_addresses(message_payload.get("sender"))
    recipient_addresses = _email_addresses(message_payload.get("recipient")) | _email_addresses(message_payload.get("to"))
    if author_address not in sender_addresses:
        error = f"inbound sender does not match the selected verified sender: {author_address}"
        _persist_inbound_status(private_dir, domain=domain, profile=profile, message_payload=message_payload, status="blocked", error=error)
        return {"ok": False, "error": error, "inbound_message": message_payload, "inbound_chain": chain}
    if list_address not in recipient_addresses:
        error = f"inbound recipient does not target the canonical list address: {list_address}"
        _persist_inbound_status(private_dir, domain=domain, profile=profile, message_payload=message_payload, status="blocked", error=error)
        return {"ok": False, "error": error, "inbound_message": message_payload, "inbound_chain": chain}
    try:
        dispatch = _queue_inbound_newsletter(private_dir, domain=domain, inbound_message=message_payload)
    except Exception as exc:
        _persist_inbound_status(private_dir, domain=domain, profile=profile, message_payload=message_payload, status="error", error=_text(exc))
        return {"ok": False, "error": _text(exc), "inbound_message": message_payload, "inbound_chain": chain}
    _persist_inbound_status(
        private_dir,
        domain=domain,
        profile=profile,
        message_payload=message_payload,
        status="processed",
        dispatch_id=_text(dispatch.get("dispatch_id")),
    )
    return {"ok": True, "dispatch": dispatch, "inbound_message": message_payload, "inbound_chain": chain}


def register_aws_newsletter_routes(app: Flask, *, private_dir: Path) -> None:
    @app.get("/portal/api/admin/aws/newsletter/status")
    def newsletter_admin_status():
        ok, failure = _ensure_admin()
        if not ok:
            return failure
        domains = [resolve_newsletter_domain_state(private_dir, domain) for domain in newsletter_domains(private_dir)]
        return jsonify(
            {
                "ok": True,
                "domains": domains,
                "domain_count": len(domains),
            }
        )

    @app.get("/portal/api/admin/aws/newsletter/domain/<domain>")
    def newsletter_admin_domain(domain: str):
        ok, failure = _ensure_admin()
        if not ok:
            return failure
        return jsonify({"ok": True, **resolve_newsletter_domain_state(private_dir, domain)})

    @app.post("/portal/api/admin/aws/newsletter/domain/<domain>/config")
    def newsletter_admin_config(domain: str):
        ok, failure = _ensure_admin()
        if not ok:
            return failure
        body = _request_payload()
        state = resolve_newsletter_domain_state(private_dir, domain)
        profile_path, profile = load_newsletter_profile(private_dir, domain)
        selected_sender_profile_id = _text(body.get("selected_author_profile_id") or body.get("selected_sender_profile_id"))
        matched = {}
        for item in list(state.get("verified_senders") or []):
            if _text(item.get("profile_id")) == selected_sender_profile_id:
                matched = dict(item)
                break
        if not matched and selected_sender_profile_id:
            return jsonify({"ok": False, "error": "selected sender is not verified for this domain"}), 400
        if matched:
            profile["selected_author_profile_id"] = _text(matched.get("profile_id"))
            profile["selected_author_address"] = _text(matched.get("send_as_email"))
            profile["selected_sender_profile_id"] = _text(matched.get("profile_id"))
            profile["selected_sender_address"] = _text(matched.get("send_as_email"))
        save_newsletter_profile(profile_path, profile)
        return jsonify({"ok": True, **resolve_newsletter_domain_state(private_dir, domain)})

    @app.post("/portal/api/admin/aws/newsletter/domain/<domain>/send")
    def newsletter_admin_send(domain: str):
        ok, failure = _ensure_admin()
        if not ok:
            return failure
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "AWS-CMS newsletter mediation is inbound-mail workflow only: send a message from the selected verified mailbox to the canonical news@<domain> address, then process the captured inbound message",
                }
            ),
            409,
        )

    @app.post("/portal/api/admin/aws/newsletter/domain/<domain>/process_inbound")
    def newsletter_admin_process_inbound(domain: str):
        ok, failure = _ensure_admin()
        if not ok:
            return failure
        result = process_latest_inbound_newsletter(private_dir, domain=domain)
        status_code = 200 if bool(result.get("ok")) else 400
        return jsonify({**result, **resolve_newsletter_domain_state(private_dir, domain)}), status_code

    @app.post("/portal/api/admin/aws/newsletter/domain/<domain>/contact")
    def newsletter_admin_contact(domain: str):
        ok, failure = _ensure_admin()
        if not ok:
            return failure
        body = _request_payload()
        email = _normalized_email(body.get("email"))
        if not email:
            return jsonify({"ok": False, "error": "a valid email is required"}), 400
        path, payload = load_contact_log(private_dir, domain)
        row = upsert_contact_record(
            payload,
            email=email,
            name=_text(body.get("name")),
            zip_code=_text(body.get("zip")),
            source="admin_contact_upsert",
            subscribed=bool(body.get("subscribed", True)),
        )
        save_contact_log(path, payload)
        return jsonify({"ok": True, "contact": row, **resolve_newsletter_domain_state(private_dir, domain)})

    @app.post("/__fnd/newsletter/subscribe")
    def newsletter_public_subscribe():
        body = _request_payload()
        domain = _request_domain(body)
        if not domain:
            return jsonify({"ok": False, "error": "newsletter domain could not be resolved"}), 400
        email = _normalized_email(body.get("email"))
        if not email:
            return jsonify({"ok": False, "error": "a valid email is required"}), 400
        path, payload = load_contact_log(private_dir, domain)
        row = upsert_contact_record(
            payload,
            email=email,
            name=_text(body.get("name")),
            zip_code=_text(body.get("zip")),
            source="website_signup",
            subscribed=True,
        )
        save_contact_log(path, payload)
        return jsonify(
            {
                "ok": True,
                "domain": domain,
                "contact": row,
                "contact_log_path": str(path),
                **contact_summary(payload),
            }
        )

    @app.post("/__fnd/newsletter/dispatch-result")
    def newsletter_public_dispatch_result():
        body = _request_payload()
        domain = _request_domain(body)
        token = _text(request.headers.get("X-Newsletter-Dispatch-Token") or body.get("callback_token"))
        if token != newsletter_dispatch_secret(private_dir):
            return jsonify({"ok": False, "error": "dispatch callback token is invalid"}), 403
        dispatch_id = _text(body.get("dispatch_id"))
        email = _normalized_email(body.get("email"))
        status = _text(body.get("status")).lower()
        if not domain or not dispatch_id or not email or status not in {"sent", "failed"}:
            return jsonify({"ok": False, "error": "dispatch callback is incomplete"}), 400
        path, payload = load_contact_log(private_dir, domain)
        contacts = {
            _text(item.get("email")).lower(): dict(item)
            for item in list(payload.get("contacts") or [])
            if isinstance(item, dict) and _text(item.get("email"))
        }
        now_iso = _utc_now_iso()
        updated = False
        for dispatch in list(payload.get("dispatches") or []):
            if _text(dispatch.get("dispatch_id")) != dispatch_id:
                continue
            results = list(dispatch.get("results") or [])
            for row in results:
                if not isinstance(row, dict) or _text(row.get("email")).lower() != email:
                    continue
                prior_status = _text(row.get("status")).lower()
                row["status"] = status
                if _text(body.get("message_id")):
                    row["message_id"] = _text(body.get("message_id"))
                if _text(body.get("queue_message_id")):
                    row["queue_message_id"] = _text(body.get("queue_message_id"))
                if _text(body.get("error")):
                    row["error"] = _text(body.get("error"))
                row["updated_at"] = now_iso
                if status == "sent" and prior_status != "sent":
                    current = contacts.get(email)
                    if current:
                        current["last_newsletter_sent_at"] = now_iso
                        current["send_count"] = int(current.get("send_count") or 0) + 1
                        current["updated_at"] = now_iso
                        contacts[email] = current
                updated = True
                break
            dispatch["results"] = results
            dispatch["queued_count"] = sum(1 for row in results if _text((row or {}).get("status")).lower() == "queued")
            dispatch["sent_count"] = sum(1 for row in results if _text((row or {}).get("status")).lower() == "sent")
            dispatch["failed_count"] = sum(1 for row in results if _text((row or {}).get("status")).lower() == "failed")
            if int(dispatch.get("queued_count") or 0) == 0:
                dispatch["completed_at"] = now_iso
                dispatch["status"] = "completed" if int(dispatch.get("failed_count") or 0) == 0 else "completed_with_errors"
            break
        if not updated:
            return jsonify({"ok": False, "error": "dispatch result target was not found"}), 404
        payload["contacts"] = [contacts[key] for key in sorted(contacts.keys())]
        save_contact_log(path, payload)
        return jsonify({"ok": True, "domain": domain, "dispatch_id": dispatch_id, "email": email, "status": status})

    @app.route("/__fnd/newsletter/unsubscribe", methods=["GET", "POST"])
    def newsletter_public_unsubscribe():
        body = _request_payload()
        domain = _request_domain(body)
        email = _normalized_email(body.get("email") or request.args.get("email"))
        token = _text(body.get("token") or request.args.get("token"))
        if not domain or not email or not token:
            message = "The unsubscribe link is incomplete."
            if _wants_json():
                return jsonify({"ok": False, "error": message}), 400
            return _html_message("Unsubscribe failed", message, status_code=400)
        expected = unsubscribe_token(newsletter_signing_secret(private_dir), domain=domain, email=email)
        if token != expected:
            message = "The unsubscribe link is not valid for this address."
            if _wants_json():
                return jsonify({"ok": False, "error": message}), 403
            return _html_message("Unsubscribe failed", message, status_code=403)
        path, payload = load_contact_log(private_dir, domain)
        updated = unsubscribe_contact_record(payload, email=email, source="unsubscribe_link")
        save_contact_log(path, payload)
        message = f"{email} has been unsubscribed from {domain}."
        if _wants_json():
            return jsonify({"ok": True, "domain": domain, "contact": updated, "contact_log_path": str(path)})
        return _html_message("Unsubscribed", message)

    @app.route("/portal/api/admin/aws/newsletter/status", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/newsletter/domain/<domain>", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/newsletter/domain/<domain>/config", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/newsletter/domain/<domain>/send", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/newsletter/domain/<domain>/process_inbound", methods=["OPTIONS"])
    @app.route("/portal/api/admin/aws/newsletter/domain/<domain>/contact", methods=["OPTIONS"])
    @app.route("/__fnd/newsletter/subscribe", methods=["OPTIONS"])
    @app.route("/__fnd/newsletter/dispatch-result", methods=["OPTIONS"])
    @app.route("/__fnd/newsletter/unsubscribe", methods=["OPTIONS"])
    def newsletter_admin_options(domain: str | None = None):  # pragma: no cover - exercised via Flask routing
        response = make_response("", 204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Portal-User, X-Portal-Username, X-Portal-Roles"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response


def register_newsletter_admin_routes(app: Flask, *, private_dir: Path) -> None:
    register_aws_newsletter_routes(app, private_dir=private_dir)
