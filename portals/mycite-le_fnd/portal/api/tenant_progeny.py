from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, make_response, request

_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FORBIDDEN_KEYS = {"secret", "token", "password", "private_key", "client_secret", "aws_secret_access_key"}


def _tenant_dir(private_dir: Path) -> Path:
    return private_dir / "progeny" / "tenant"


def _safe_tenant_id(value: str) -> str:
    token = str(value or "").strip()
    if not _TENANT_ID_RE.fullmatch(token):
        raise ValueError("tenant_id must match [A-Za-z0-9._:-]{1,128}")
    return token


def _contains_forbidden_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                return True
            if _contains_forbidden_key(value):
                return True
        return False
    if isinstance(obj, list):
        return any(_contains_forbidden_key(item) for item in obj)
    return False


def _profile_path(private_dir: Path, tenant_id: str) -> Path:
    return _tenant_dir(private_dir) / f"{tenant_id}.json"


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _normalize_profile(tenant_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    tenant_msn_id = str(payload.get("tenant_msn_id") or "").strip()
    display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
    profile_refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    contract_refs = payload.get("contract_refs") if isinstance(payload.get("contract_refs"), dict) else {}
    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}

    state = str(status.get("state") or "active").strip().lower()
    if state not in {"active", "suspended"}:
        state = "active"

    return {
        "schema": "mycite.progeny.tenant.profile.v1",
        "tenant_id": tenant_id,
        "tenant_msn_id": tenant_msn_id,
        "display": {
            "title": str(display.get("title") or f"Tenant {tenant_id}").strip() or f"Tenant {tenant_id}",
        },
        "capabilities": {
            "paypal": bool(capabilities.get("paypal", False)),
            "aws": bool(capabilities.get("aws", False)),
        },
        "profile_refs": {
            "paypal_profile_id": str(profile_refs.get("paypal_profile_id") or f"paypal:tenant:{tenant_id}").strip(),
            "aws_profile_id": str(profile_refs.get("aws_profile_id") or f"aws:tenant:{tenant_id}").strip(),
            "aws_emailer_list_ref": str(profile_refs.get("aws_emailer_list_ref") or "").strip(),
            "aws_emailer_entry_ref": str(profile_refs.get("aws_emailer_entry_ref") or "").strip(),
        },
        "contract_refs": {
            "authorization_contract_id": str(contract_refs.get("authorization_contract_id") or "").strip(),
            "service_agreement_ref": str(contract_refs.get("service_agreement_ref") or "").strip(),
        },
        "status": {
            "state": state,
            "updated_unix_ms": int(status.get("updated_unix_ms") or int(time.time() * 1000)),
        },
    }


def _write_profile(private_dir: Path, profile: Dict[str, Any]) -> Path:
    target = _profile_path(private_dir, str(profile.get("tenant_id") or ""))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    return target


def register_tenant_progeny_routes(
    app,
    *,
    private_dir: Path,
    options_private_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    msn_id_provider: Optional[Callable[[], str]] = None,
):
    def _options_payload() -> Dict[str, Any]:
        msn_id = ""
        if msn_id_provider is not None:
            try:
                msn_id = str(msn_id_provider() or "").strip()
            except Exception:
                msn_id = ""
        if options_private_fn is not None and msn_id:
            return {"options_private": options_private_fn(msn_id)}
        return {}

    @app.get("/portal/api/progeny/tenants")
    def progeny_tenants_list():
        out: list[dict[str, Any]] = []
        root = _tenant_dir(private_dir)
        root.mkdir(parents=True, exist_ok=True)
        for path in sorted(root.glob("*.json")):
            try:
                payload = _read_json(path)
                tenant_id = _safe_tenant_id(str(payload.get("tenant_id") or path.stem))
                profile = _normalize_profile(tenant_id, payload)
                out.append(profile)
            except Exception:
                continue

        response: Dict[str, Any] = {"schema": "mycite.progeny.tenant.list.v1", "items": out}
        response.update(_options_payload())
        return jsonify(response)

    @app.get("/portal/api/progeny/tenants/<tenant_id>")
    def progeny_tenant_get(tenant_id: str):
        try:
            token = _safe_tenant_id(tenant_id)
        except ValueError as e:
            abort(400, description=str(e))

        path = _profile_path(private_dir, token)
        if not path.exists() or not path.is_file():
            abort(404, description=f"No progeny profile found for tenant_id={token}")

        payload = _read_json(path)
        profile = _normalize_profile(token, payload)
        response: Dict[str, Any] = {"item": profile}
        response.update(_options_payload())
        return jsonify(response)

    @app.put("/portal/api/progeny/tenants/<tenant_id>")
    def progeny_tenant_put(tenant_id: str):
        try:
            token = _safe_tenant_id(tenant_id)
        except ValueError as e:
            abort(400, description=str(e))

        if not request.is_json:
            abort(415, description="Expected application/json body")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")
        if _contains_forbidden_key(body):
            abort(400, description="Do not store secrets in tenant progeny metadata.")

        profile = _normalize_profile(token, body)
        path = _write_profile(private_dir, profile)
        response: Dict[str, Any] = {"ok": True, "item": profile, "written_to": str(path)}
        response.update(_options_payload())
        return jsonify(response)

    @app.route("/portal/api/progeny/tenants", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/tenants/<tenant_id>", methods=["OPTIONS"])
    def progeny_tenants_options(tenant_id: str = ""):
        _ = tenant_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, PUT, OPTIONS"
        return resp
