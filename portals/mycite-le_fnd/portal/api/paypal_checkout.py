from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from flask import abort, jsonify, make_response

_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _tenant_dir(private_dir: Path) -> Path:
    return private_dir / "progeny" / "tenant"


def _safe_tenant_id(value: str) -> str:
    token = str(value or "").strip()
    if not _TENANT_ID_RE.fullmatch(token):
        raise ValueError("tenant_id must match [A-Za-z0-9._:-]{1,128}")
    return token


def _profile_path(private_dir: Path, tenant_id: str) -> Path:
    return _tenant_dir(private_dir) / f"{tenant_id}.json"


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _is_http_url(value: str) -> bool:
    token = str(value or "").strip()
    if not token:
        return False
    try:
        parsed = urlparse(token)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _with_base_path(base_url: str, path: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{path}"


def register_paypal_checkout_routes(app, *, private_dir: Path) -> None:
    @app.get("/portal/api/paypal/tenant/<tenant_id>/checkout_preview")
    def paypal_tenant_checkout_preview(tenant_id: str):
        try:
            token = _safe_tenant_id(tenant_id)
        except ValueError as e:
            abort(400, description=str(e))

        path = _profile_path(private_dir, token)
        if not path.exists() or not path.is_file():
            abort(404, description=f"No progeny profile found for tenant_id={token}")

        payload = _read_json(path)
        profile_refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}

        profile_id = str(profile_refs.get("paypal_profile_id") or f"paypal:tenant:{token}").strip()
        site_base_url = str(profile_refs.get("paypal_site_base_url") or "").strip()
        return_url = str(profile_refs.get("paypal_checkout_return_url") or "").strip()
        cancel_url = str(profile_refs.get("paypal_checkout_cancel_url") or "").strip()
        webhook_listener_url = str(profile_refs.get("paypal_webhook_listener_url") or "").strip()
        brand_name = str(profile_refs.get("paypal_checkout_brand_name") or "").strip()

        warnings: list[str] = []
        errors: list[str] = []

        if site_base_url and not _is_http_url(site_base_url):
            errors.append("profile_refs.paypal_site_base_url must be an absolute http/https URL")
        if site_base_url and not return_url:
            return_url = _with_base_path(site_base_url, "/payments/paypal/return")
            warnings.append("Derived paypal_checkout_return_url from paypal_site_base_url")
        if site_base_url and not cancel_url:
            cancel_url = _with_base_path(site_base_url, "/payments/paypal/cancel")
            warnings.append("Derived paypal_checkout_cancel_url from paypal_site_base_url")

        if not return_url:
            errors.append("profile_refs.paypal_checkout_return_url is required")
        elif not _is_http_url(return_url):
            errors.append("profile_refs.paypal_checkout_return_url must be an absolute http/https URL")

        if not cancel_url:
            errors.append("profile_refs.paypal_checkout_cancel_url is required")
        elif not _is_http_url(cancel_url):
            errors.append("profile_refs.paypal_checkout_cancel_url must be an absolute http/https URL")

        if webhook_listener_url and not _is_http_url(webhook_listener_url):
            errors.append("profile_refs.paypal_webhook_listener_url must be an absolute http/https URL")
        if not webhook_listener_url:
            warnings.append("paypal_webhook_listener_url is not set; webhook verification path remains external")

        checkout_context = {
            "paypal_profile_id": profile_id,
            "site_base_url": site_base_url,
            "return_url": return_url,
            "cancel_url": cancel_url,
            "webhook_listener_url": webhook_listener_url,
            "brand_name": brand_name or f"Tenant {token}",
        }
        if errors:
            return (
                jsonify(
                    {
                        "ok": False,
                        "tenant_id": token,
                        "source": checkout_context,
                        "errors": errors,
                        "warnings": warnings,
                    }
                ),
                400,
            )

        response = {
            "ok": True,
            "tenant_id": token,
            "source": checkout_context,
            "order_template": {
                "intent": "CAPTURE",
                "purchase_units": [{"amount": {"currency_code": "USD", "value": "10.00"}}],
                "application_context": {
                    "brand_name": checkout_context["brand_name"],
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING",
                },
            },
            "warnings": warnings,
        }
        return jsonify(response)

    @app.route("/portal/api/paypal/tenant/<tenant_id>/checkout_preview", methods=["OPTIONS"])
    def paypal_tenant_checkout_preview_options(tenant_id: str):
        _ = tenant_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, OPTIONS"
        return resp
