from __future__ import annotations

import importlib.util
import json
import re
import time
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, make_response, request
from portal.services.runtime_paths import legacy_tenant_progeny_dir, member_progeny_dir

_MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FORBIDDEN_KEYS = {"secret", "token", "password", "private_key", "client_secret", "aws_secret_access_key"}


def _load_shared_progeny_normalize() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "progeny_model" / "normalize.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_progeny_normalize", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared progeny normalize module from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED_NORMALIZE = _load_shared_progeny_normalize()
normalize_member_profile = _SHARED_NORMALIZE.normalize_member_profile


def _member_dir(private_dir: Path) -> Path:
    return member_progeny_dir(private_dir)


def _legacy_tenant_dir(private_dir: Path) -> Path:
    return legacy_tenant_progeny_dir(private_dir)


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


def _canonical_profile_path(private_dir: Path, member_id: str) -> Path:
    return _member_dir(private_dir) / f"{member_id}.json"


def _legacy_profile_path(private_dir: Path, member_id: str) -> Path:
    return _legacy_tenant_dir(private_dir) / f"{member_id}.json"


def _profile_path(private_dir: Path, member_id: str) -> Path:
    canonical = _canonical_profile_path(private_dir, member_id)
    if canonical.exists() and canonical.is_file():
        return canonical
    legacy = _legacy_profile_path(private_dir, member_id)
    if legacy.exists() and legacy.is_file():
        return legacy
    return canonical


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
    member_id = str(profile.get("member_id") or "").strip()
    canonical_target = _canonical_profile_path(private_dir, member_id)

    canonical_target.parent.mkdir(parents=True, exist_ok=True)
    canonical_target.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

    return canonical_target


def _iter_profile_paths(private_dir: Path) -> list[Path]:
    # Canonical member dir wins on duplicate IDs; legacy tenant dir remains read-compatible.
    by_id: dict[str, Path] = {}

    for path in sorted(_legacy_tenant_dir(private_dir).glob("*.json")):
        by_id[path.stem] = path
    for path in sorted(_member_dir(private_dir).glob("*.json")):
        by_id[path.stem] = path

    return [by_id[key] for key in sorted(by_id.keys())]


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
        _member_dir(private_dir).mkdir(parents=True, exist_ok=True)
        _legacy_tenant_dir(private_dir).mkdir(parents=True, exist_ok=True)

        for path in _iter_profile_paths(private_dir):
            try:
                payload = _read_json(path)
                member_id = _safe_member_id(str(payload.get("member_id") or payload.get("tenant_id") or path.stem))
                profile = _normalize_profile(member_id, payload)
                out.append(profile)
            except Exception:
                continue
        return out

    def _get_member(member_id: str) -> Dict[str, Any]:
        token = _safe_member_id(member_id)
        path = _profile_path(private_dir, token)
        if not path.exists() or not path.is_file():
            abort(404, description=f"No progeny profile found for member_id={token}")
        payload = _read_json(path)
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
