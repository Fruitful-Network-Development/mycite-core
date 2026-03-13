from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, make_response, request

from portal.services.hosted_store import read_hosted_payload
from portal.services.progeny_workspace import find_member_instance, list_instances
from portal.services.website_analytics_store import list_member_analytics, load_member_analytics


def register_website_analytics_routes(
    app,
    *,
    private_dir: Path,
    options_private_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    msn_id_provider: Optional[Callable[[], str]] = None,
) -> None:
    def _options_payload() -> Dict[str, Any]:
        if options_private_fn is None or msn_id_provider is None:
            return {}
        try:
            msn_id = str(msn_id_provider() or "").strip()
        except Exception:
            msn_id = ""
        if not msn_id:
            return {}
        return {"options_private": options_private_fn(msn_id)}

    @app.get("/portal/api/analytics/members")
    def website_analytics_members():
        hosted_payload = read_hosted_payload(private_dir)
        members = []
        for record in list_instances(private_dir, "member"):
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            if payload:
                members.append(payload)
        response: Dict[str, Any] = {
            "schema": "mycite.analytics.member.list.v1",
            "items": list_member_analytics(private_dir, members, hosted_payload),
        }
        response.update(_options_payload())
        return jsonify(response)

    @app.get("/portal/api/analytics/members/<member_id>")
    def website_analytics_member(member_id: str):
        token = str(member_id or "").strip()
        if not token:
            abort(400, description="member_id is required")
        record = find_member_instance(private_dir, token)
        if record is None:
            abort(404, description=f"No member progeny profile found for member_id={token}")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        hosted_payload = read_hosted_payload(private_dir)
        response: Dict[str, Any] = {
            "item": load_member_analytics(private_dir, token, payload, hosted_payload),
        }
        response.update(_options_payload())
        return jsonify(response)

    @app.route("/portal/api/analytics/members", methods=["OPTIONS"])
    @app.route("/portal/api/analytics/members/<member_id>", methods=["OPTIONS"])
    def website_analytics_options(member_id: str = ""):
        _ = member_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, OPTIONS"
        return resp
