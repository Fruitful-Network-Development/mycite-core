from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, make_response, request
from portal.services.progeny_workspace import find_member_instance, list_instances, save_instance

_MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FORBIDDEN_KEYS = {"secret", "token", "password", "private_key", "client_secret", "aws_secret_access_key"}


def _load_shared_progeny_normalize():
    portals_root = Path(__file__).resolve().parents[6]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    import _shared.portal.progeny_model.normalize as module

    return module


_SHARED_NORMALIZE = _load_shared_progeny_normalize()
normalize_member_profile = _SHARED_NORMALIZE.normalize_member_profile


def _safe_member_id(value: str) -> str:
    token = str(value or "").strip()
    if not _MEMBER_ID_RE.fullmatch(token):
        raise ValueError("member_id must match [A-Za-z0-9._:-]{1,128}")
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


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _with_legacy_aliases(profile: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(profile)
    out["tenant_id"] = str(profile.get("member_id") or "").strip()
    out["tenant_msn_id"] = str(profile.get("member_msn_id") or "").strip()
    out.setdefault("schema_legacy", "mycite.progeny.tenant.profile.v1")
    return out


def _normalize_profile(member_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_member_profile(member_id, payload)
    if not isinstance(normalized, dict):
        raise ValueError("Expected normalized member profile object")

    status = normalized.get("status") if isinstance(normalized.get("status"), dict) else {}
    status["updated_unix_ms"] = int(status.get("updated_unix_ms") or int(time.time() * 1000))
    normalized["status"] = status
    return normalized


def _write_profile(private_dir: Path, profile: Dict[str, Any]) -> Path:
    profile["profile_type"] = "member"
    provider_msn_id = str(
        profile.get("provider_msn_id")
        or profile.get("provider")
        or profile.get("host_msn_id")
        or "local"
    )
    return save_instance(
        private_dir,
        profile,
        provider_msn_id,
        instance_id=str(profile.get("instance_id") or ""),
    )


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

    def _list_members() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for record in list_instances(private_dir, "member"):
            try:
                payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                member_id = _safe_member_id(
                    str(
                        payload.get("member_id")
                        or payload.get("member_msn_id")
                        or payload.get("tenant_id")
                        or payload.get("tenant_msn_id")
                        or payload.get("msn_id")
                        or record.get("alias_associated_msn_id")
                        or record.get("instance_id")
                    )
                )
                profile = _normalize_profile(member_id, payload)
                out.append(profile)
            except Exception:
                continue
        return out

    def _get_member(member_id: str) -> Dict[str, Any]:
        token = _safe_member_id(member_id)
        record = find_member_instance(private_dir, token)
        if record is None:
            abort(404, description=f"No progeny profile found for member_id={token}")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        return _normalize_profile(token, payload)

    @app.get("/portal/api/progeny/members")
    def progeny_members_list():
        items = _list_members()
        response: Dict[str, Any] = {"schema": "mycite.progeny.member.list.v1", "items": [_with_legacy_aliases(item) for item in items]}
        response.update(_options_payload())
        return jsonify(response)

    @app.get("/portal/api/progeny/members/<member_id>")
    def progeny_member_get(member_id: str):
        try:
            profile = _get_member(member_id)
        except ValueError as e:
            abort(400, description=str(e))
        response: Dict[str, Any] = {"item": _with_legacy_aliases(profile)}
        response.update(_options_payload())
        return jsonify(response)

    @app.put("/portal/api/progeny/members/<member_id>")
    def progeny_member_put(member_id: str):
        try:
            token = _safe_member_id(member_id)
        except ValueError as e:
            abort(400, description=str(e))

        if not request.is_json:
            abort(415, description="Expected application/json body")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")
        if _contains_forbidden_key(body):
            abort(400, description="Do not store secrets in member progeny metadata.")

        profile = _normalize_profile(token, body)
        if msn_id_provider is not None:
            try:
                profile["provider_msn_id"] = str(msn_id_provider() or "").strip()
            except Exception:
                profile["provider_msn_id"] = ""
        existing = find_member_instance(private_dir, token)
        if existing is not None:
            profile["instance_id"] = str(existing.get("instance_id") or "")
        path = _write_profile(private_dir, profile)
        response: Dict[str, Any] = {
            "ok": True,
            "item": _with_legacy_aliases(profile),
            "written_to": str(path),
        }
        response.update(_options_payload())
        return jsonify(response)

    # Compatibility aliases for legacy tenant terminology.
    @app.get("/portal/api/progeny/tenants")
    def progeny_tenants_list():
        items = _list_members()
        response: Dict[str, Any] = {
            "schema": "mycite.progeny.tenant.list.v1",
            "items": [_with_legacy_aliases(item) for item in items],
            "deprecation": {
                "legacy_term": "tenant",
                "canonical_term": "member",
                "canonical_endpoint": "/portal/api/progeny/members",
            },
        }
        response.update(_options_payload())
        return jsonify(response)

    @app.get("/portal/api/progeny/tenants/<tenant_id>")
    def progeny_tenant_get(tenant_id: str):
        try:
            profile = _get_member(tenant_id)
        except ValueError as e:
            abort(400, description=str(e))
        response: Dict[str, Any] = {
            "item": _with_legacy_aliases(profile),
            "deprecation": {
                "legacy_term": "tenant",
                "canonical_term": "member",
                "canonical_endpoint": f"/portal/api/progeny/members/{tenant_id}",
            },
        }
        response.update(_options_payload())
        return jsonify(response)

    @app.put("/portal/api/progeny/tenants/<tenant_id>")
    def progeny_tenant_put(tenant_id: str):
        return progeny_member_put(tenant_id)

    @app.route("/portal/api/progeny/members", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/members/<member_id>", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/tenants", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/tenants/<member_id>", methods=["OPTIONS"])
    def progeny_members_options(member_id: str = ""):
        _ = member_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, PUT, OPTIONS"
        return resp
