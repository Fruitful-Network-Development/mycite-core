from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import uuid
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


def _aws_csm_profile_path(private_dir: Path, tenant_id: str) -> Path:
    token = _safe_tenant_id(tenant_id)
    root = _aws_csm_root(private_dir)
    exact = root / f"aws-csm.{token}.json"
    if exact.exists() and exact.is_file():
        return exact
    for path in _aws_csm_profile_paths(private_dir):
        payload = _read_json(path, {})
        identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
        candidates = {
            path.stem.removeprefix("aws-csm."),
            str(identity.get("tenant_id") or "").strip(),
            str(identity.get("profile_id") or "").strip(),
            str(identity.get("domain") or "").strip(),
        }
        if token in {item for item in candidates if item}:
            return path
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


def _aws_profile_status(private_dir: Path, tenant_id: str) -> tuple[dict[str, Any], Path, bool]:
    path = _aws_csm_profile_path(private_dir, tenant_id)
    exists = path.exists() and path.is_file()
    raw = _read_json(path, {}) if exists else {"identity": {"tenant_id": tenant_id}}
    profile, errors, warnings = normalize_aws_csm_profile_payload(raw, profile_hint=tenant_id)
    workflow = profile.get("workflow") if isinstance(profile.get("workflow"), dict) else {}
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    smtp = profile.get("smtp") if isinstance(profile.get("smtp"), dict) else {}
    provider = profile.get("provider") if isinstance(profile.get("provider"), dict) else {}
    status = {
        "ok": True,
        "tenant_id": tenant_id,
        "profile_id": str(identity.get("profile_id") or ""),
        "configured": exists,
        "canonical_root": str(_aws_csm_root(private_dir)),
        "profile_path": str(path),
        "region": str(identity.get("region") or ""),
        "send_as_email": str(smtp.get("send_as_email") or ""),
        "single_user_email": str(identity.get("single_user_email") or ""),
        "gmail_send_as_status": str(provider.get("gmail_send_as_status") or ""),
        "aws_ses_identity_status": str(provider.get("aws_ses_identity_status") or ""),
        "handoff_ready": bool(workflow.get("is_ready_for_user_handoff")),
        "send_as_confirmed": bool(workflow.get("is_send_as_confirmed")),
        "missing_required_now": list(workflow.get("missing_required_now") or []),
        "last_checked_at": str(provider.get("last_checked_at") or ""),
        "warnings": list(warnings or []),
        "validation_errors": list(errors or []),
        "profile": profile,
        "last_checked_unix_ms": int(time.time() * 1000),
    }
    return status, path, exists


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
        current_profile = current_status.get("profile") if isinstance(current_status.get("profile"), dict) else {}
        merged = _deep_merge_dicts(current_profile, raw_profile)
        incoming_identity = raw_profile.get("identity") if isinstance(raw_profile.get("identity"), dict) else {}
        if str(incoming_identity.get("tenant_id") or "").strip() not in {"", token}:
            return jsonify({"ok": False, "errors": ["identity.tenant_id must match the profile route token"]}), 400
        merged = _deep_merge_dicts(merged, {"identity": {"tenant_id": token}})
        normalized, validation_errors, warnings = normalize_aws_csm_profile_payload(merged, profile_hint=token)
        if validation_errors:
            return jsonify({"ok": False, "errors": validation_errors, "warnings": warnings}), 400

        _write_json(path, normalized)
        response = {
            "ok": True,
            "tenant_id": token,
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
                "tenant_id": token,
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
                "errors": ["newsletter/emailer actions are not part of the active AWS-CMS scope"],
            }
            _append_action(private_dir, "aws", "aws.profile.provision.rejected", rejected)
            return jsonify(rejected), 400

        allowed_actions = {
            "prepare_send_as",
            "setup_ses_identity",
            "setup_dkim",
            "stage_smtp_credentials",
            "capture_verification",
            "refresh_provider_status",
            "enable_inbound_capture",
        }
        if action not in allowed_actions:
            rejected = {
                "ok": False,
                "profile_id": token,
                "errors": [f"unsupported aws provision action: {action}"],
            }
            _append_action(private_dir, "aws", "aws.profile.provision.rejected", rejected)
            return jsonify(rejected), 400

        status_payload, path, exists = _aws_profile_status(private_dir, token)
        if not exists:
            rejected = {
                "ok": False,
                "profile_id": token,
                "configured": False,
                "errors": ["AWS-CMS profile is not staged in the canonical aws-csm root"],
            }
            _append_action(private_dir, "aws", "aws.profile.provision.rejected", rejected)
            return jsonify(rejected), 409

        request_id = f"AWSREQ-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8].upper()}"
        response = {
            "ok": True,
            "profile_id": token,
            "tenant_id": token,
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
                "profile_id": token,
                "tenant_id": token,
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
        profiles = []
        ready_count = 0
        confirmed_count = 0
        for path in _aws_csm_profile_paths(private_dir):
            profile_token = path.stem.removeprefix("aws-csm.")
            status_payload, _, _ = _aws_profile_status(private_dir, profile_token)
            profiles.append(
                {
                    "profile_id": str(status_payload.get("profile_id") or profile_token),
                    "tenant_id": profile_token,
                    "send_as_email": str(status_payload.get("send_as_email") or ""),
                    "handoff_ready": bool(status_payload.get("handoff_ready")),
                    "send_as_confirmed": bool(status_payload.get("send_as_confirmed")),
                }
            )
            if status_payload.get("handoff_ready"):
                ready_count += 1
            if status_payload.get("send_as_confirmed"):
                confirmed_count += 1
        response = {
            "ok": True,
            "scope": "fnd",
            "canonical_root": str(_aws_csm_root(private_dir)),
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
