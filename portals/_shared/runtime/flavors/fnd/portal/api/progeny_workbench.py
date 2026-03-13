from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, make_response, request

from portal.services.hosted_store import (
    SUPPORTED_PROGENY_TYPES,
    get_progeny_template,
    read_hosted_payload,
    set_progeny_template,
    write_hosted_payload,
)
from portal.services.progeny_workspace import (
    find_profile_by_associated_msn,
    list_instances,
    load_instance,
    parse_instance_stem,
    save_instance,
)

_FORBIDDEN_KEYS = {"secret", "token", "password", "private_key", "client_secret", "aws_secret_access_key"}


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


def _options_payload(
    *,
    options_private_fn: Optional[Callable[[str], Dict[str, Any]]],
    msn_id_provider: Optional[Callable[[], str]],
) -> Dict[str, Any]:
    if options_private_fn is None or msn_id_provider is None:
        return {}
    try:
        msn_id = str(msn_id_provider() or "").strip()
    except Exception:
        msn_id = ""
    if not msn_id:
        return {}
    return {"options_private": options_private_fn(msn_id)}


def _instance_summary(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    profile_refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    return {
        "instance_id": str(record.get("instance_id") or ""),
        "progeny_type": str(record.get("progeny_type") or ""),
        "provider_msn_id": str(record.get("provider_msn_id") or ""),
        "alias_associated_msn_id": str(record.get("alias_associated_msn_id") or ""),
        "title": str(payload.get("title") or display.get("title") or record.get("instance_id") or "").strip(),
        "msn_id": str(payload.get("msn_id") or payload.get("member_msn_id") or "").strip(),
        "contact_collection_ref": str(profile_refs.get("contact_collection_ref") or "").strip(),
        "path": str(record.get("path") or ""),
        "source_kind": str(record.get("source_kind") or ""),
    }


def register_progeny_workbench_routes(
    app,
    *,
    private_dir: Path,
    options_private_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    msn_id_provider: Optional[Callable[[], str]] = None,
) -> None:
    @app.get("/portal/api/hosted")
    def portal_hosted_get():
        payload = read_hosted_payload(private_dir)
        response: Dict[str, Any] = {"item": payload}
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.put("/portal/api/hosted")
    def portal_hosted_put():
        if not request.is_json:
            abort(415, description="Expected application/json body")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")
        if _contains_forbidden_key(body):
            abort(400, description="Do not store secrets in hosted metadata.")
        target = write_hosted_payload(private_dir, body)
        response: Dict[str, Any] = {"ok": True, "item": read_hosted_payload(private_dir), "written_to": str(target)}
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.get("/portal/api/progeny/templates")
    def portal_progeny_templates():
        hosted_payload = read_hosted_payload(private_dir)
        response: Dict[str, Any] = {
            "schema": "mycite.progeny.template.list.v1",
            "items": {token: get_progeny_template(hosted_payload, token) for token in SUPPORTED_PROGENY_TYPES},
        }
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.get("/portal/api/progeny/templates/<progeny_type>")
    def portal_progeny_template_get(progeny_type: str):
        try:
            item = get_progeny_template(read_hosted_payload(private_dir), progeny_type)
        except ValueError as e:
            abort(400, description=str(e))
        response: Dict[str, Any] = {
            "schema": "mycite.progeny.template.v1",
            "progeny_type": progeny_type,
            "item": item,
        }
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.put("/portal/api/progeny/templates/<progeny_type>")
    def portal_progeny_template_put(progeny_type: str):
        if not request.is_json:
            abort(415, description="Expected application/json body")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")
        if _contains_forbidden_key(body):
            abort(400, description="Do not store secrets in progeny templates.")
        try:
            payload = set_progeny_template(read_hosted_payload(private_dir), progeny_type, body)
        except ValueError as e:
            abort(400, description=str(e))
        target = write_hosted_payload(private_dir, payload)
        response: Dict[str, Any] = {"ok": True, "item": get_progeny_template(payload, progeny_type), "written_to": str(target)}
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.get("/portal/api/progeny/instances")
    def portal_progeny_instances():
        progeny_type = str(request.args.get("progeny_type") or "").strip().lower()
        items = [_instance_summary(record) for record in list_instances(private_dir, progeny_type)]
        response: Dict[str, Any] = {"schema": "mycite.progeny.instance.list.v1", "items": items}
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.get("/portal/api/progeny/instances/<instance_id>")
    def portal_progeny_instance_get(instance_id: str):
        record = load_instance(private_dir, instance_id)
        if record is None:
            abort(404, description=f"No progeny instance found for instance_id={instance_id}")
        response: Dict[str, Any] = {"item": record.get("payload") or {}, "summary": _instance_summary(record)}
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.put("/portal/api/progeny/instances/<instance_id>")
    def portal_progeny_instance_put(instance_id: str):
        existing = load_instance(private_dir, instance_id)
        if existing is None:
            abort(404, description=f"No progeny instance found for instance_id={instance_id}")
        if not request.is_json:
            abort(415, description="Expected application/json body")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")
        if _contains_forbidden_key(body):
            abort(400, description="Do not store secrets in progeny metadata.")
        provider_msn_id = str(existing.get("provider_msn_id") or "")
        if not provider_msn_id:
            parsed = parse_instance_stem(instance_id) or {}
            provider_msn_id = str(parsed.get("provider_msn_id") or "")
        if not provider_msn_id and msn_id_provider is not None:
            try:
                provider_msn_id = str(msn_id_provider() or "").strip()
            except Exception:
                provider_msn_id = ""
        target = save_instance(private_dir, body, provider_msn_id, instance_id=instance_id)
        record = load_instance(private_dir, target.stem) or {"payload": body, "instance_id": target.stem}
        response: Dict[str, Any] = {"ok": True, "item": record.get("payload") or body, "summary": _instance_summary(record), "written_to": str(target)}
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.get("/portal/api/progeny/preview/<progeny_type>/<associated_msn_id>")
    def portal_progeny_preview_lookup(progeny_type: str, associated_msn_id: str):
        record = find_profile_by_associated_msn(private_dir, associated_msn_id, progeny_type)
        if record is None:
            abort(404, description="No progeny instance matched the requested type + associated_msn_id")
        response: Dict[str, Any] = {"summary": _instance_summary(record), "item": record.get("payload") or {}}
        response.update(_options_payload(options_private_fn=options_private_fn, msn_id_provider=msn_id_provider))
        return jsonify(response)

    @app.route("/portal/api/hosted", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/templates", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/templates/<progeny_type>", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/instances", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/instances/<instance_id>", methods=["OPTIONS"])
    @app.route("/portal/api/progeny/preview/<progeny_type>/<associated_msn_id>", methods=["OPTIONS"])
    def portal_progeny_workbench_options(
        progeny_type: str = "",
        instance_id: str = "",
        associated_msn_id: str = "",
    ):
        _ = (progeny_type, instance_id, associated_msn_id)
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, PUT, OPTIONS"
        return resp
