from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, make_response, request

from portal.services.request_log_store import RequestLogValidationError, append_event


def register_request_log_routes(
    app,
    *,
    private_dir: Path,
    msn_id_provider: Callable[[], str],
    options_private_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
):
    @app.post("/portal/api/request_log")
    def request_log_append():
        msn_id = str(msn_id_provider() or "").strip()
        if not msn_id:
            abort(400, description="msn_id is not configured for portal runtime.")
        if not request.is_json:
            abort(415, description="Expected application/json body")

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")

        try:
            path = append_event(private_dir, msn_id, body)
        except RequestLogValidationError as e:
            return jsonify({"ok": False, "errors": list(e.errors)}), 400
        except ValueError as e:
            return jsonify({"ok": False, "errors": [str(e)]}), 400

        response: Dict[str, Any] = {"ok": True, "msn_id": msn_id, "written_to": str(path)}
        if options_private_fn is not None:
            response["options_private"] = options_private_fn(msn_id)
        return jsonify(response)

    @app.route("/portal/api/request_log", methods=["OPTIONS"])
    def request_log_options():
        resp = make_response("", 204)
        resp.headers["Allow"] = "POST, OPTIONS"
        return resp
