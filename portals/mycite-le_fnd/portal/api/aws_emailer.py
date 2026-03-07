from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

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


def register_aws_emailer_routes(app, *, private_dir: Path, workspace) -> None:
    @app.get("/portal/api/aws/tenant/<tenant_id>/emailer_preview")
    def aws_tenant_emailer_preview(tenant_id: str):
        try:
            token = _safe_tenant_id(tenant_id)
        except ValueError as e:
            abort(400, description=str(e))

        path = _profile_path(private_dir, token)
        if not path.exists() or not path.is_file():
            abort(404, description=f"No progeny profile found for tenant_id={token}")

        payload = _read_json(path)
        profile_refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
        aws_emailer_list_ref = str(profile_refs.get("aws_emailer_list_ref") or "").strip()
        aws_emailer_entry_ref = str(profile_refs.get("aws_emailer_entry_ref") or "").strip()
        if not aws_emailer_list_ref:
            return jsonify(
                {
                    "ok": False,
                    "tenant_id": token,
                    "errors": ["aws_emailer_list_ref is required in profile_refs for this tenant"],
                    "warnings": [],
                }
            ), 400

        if not hasattr(workspace, "aws_emailer_preview"):
            abort(501, description="aws emailer preview is unavailable")

        result = workspace.aws_emailer_preview(
            tenant_id=token,
            aws_emailer_list_ref=aws_emailer_list_ref,
            aws_emailer_entry_ref=aws_emailer_entry_ref,
        )
        status_code = int(result.get("status_code") or (200 if bool(result.get("ok")) else 400))
        response = dict(result)
        response.setdefault("tenant_id", token)
        return jsonify(response), status_code

    @app.route("/portal/api/aws/tenant/<tenant_id>/emailer_preview", methods=["OPTIONS"])
    def aws_tenant_emailer_preview_options(tenant_id: str):
        _ = tenant_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, OPTIONS"
        return resp
