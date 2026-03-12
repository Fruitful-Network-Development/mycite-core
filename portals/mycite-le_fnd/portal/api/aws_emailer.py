from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from flask import abort, jsonify, make_response
from portal.services.runtime_paths import member_profile_read_dirs

_MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _member_dir(private_dir: Path) -> Path:
    return member_profile_read_dirs(private_dir)[0]


def _legacy_tenant_dir(private_dir: Path) -> Path:
    return member_profile_read_dirs(private_dir)[-1]


def _safe_member_id(value: str) -> str:
    token = str(value or "").strip()
    if not _MEMBER_ID_RE.fullmatch(token):
        raise ValueError("member_id must match [A-Za-z0-9._:-]{1,128}")
    return token


def _profile_path(private_dir: Path, member_id: str) -> Path:
    for directory in member_profile_read_dirs(private_dir):
        candidate = directory / f"{member_id}.json"
        if candidate.exists() and candidate.is_file():
            return candidate
    return _member_dir(private_dir) / f"{member_id}.json"


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _emailer_preview_response(
    *,
    workspace,
    private_dir: Path,
    member_id: str,
    legacy_route_term: str,
) -> tuple[dict[str, Any], int]:
    path = _profile_path(private_dir, member_id)
    if not path.exists() or not path.is_file():
        abort(404, description=f"No progeny profile found for member_id={member_id}")

    payload = _read_json(path)
    profile_refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    aws_emailer_list_ref = str(profile_refs.get("aws_emailer_list_ref") or "").strip()
    aws_emailer_entry_ref = str(profile_refs.get("aws_emailer_entry_ref") or "").strip()
    if not aws_emailer_list_ref:
        return (
            {
                "ok": False,
                "member_id": member_id,
                "tenant_id": member_id,
                "errors": ["aws_emailer_list_ref is required in profile_refs for this member"],
                "warnings": [],
            },
            400,
        )

    if not hasattr(workspace, "aws_emailer_preview"):
        abort(501, description="aws emailer preview is unavailable")

    result = workspace.aws_emailer_preview(
        tenant_id=member_id,
        aws_emailer_list_ref=aws_emailer_list_ref,
        aws_emailer_entry_ref=aws_emailer_entry_ref,
    )
    status_code = int(result.get("status_code") or (200 if bool(result.get("ok")) else 400))
    response = dict(result)
    response.setdefault("member_id", member_id)
    response.setdefault("tenant_id", member_id)
    if legacy_route_term == "tenant":
        response.setdefault(
            "deprecation",
            {
                "legacy_term": "tenant",
                "canonical_term": "member",
                "canonical_endpoint": f"/portal/api/aws/member/{member_id}/emailer_preview",
            },
        )
    return response, status_code


def register_aws_emailer_routes(app, *, private_dir: Path, workspace) -> None:
    @app.get("/portal/api/aws/member/<member_id>/emailer_preview")
    def aws_member_emailer_preview(member_id: str):
        try:
            token = _safe_member_id(member_id)
        except ValueError as e:
            abort(400, description=str(e))
        payload, status_code = _emailer_preview_response(
            workspace=workspace,
            private_dir=private_dir,
            member_id=token,
            legacy_route_term="member",
        )
        return jsonify(payload), status_code

    @app.get("/portal/api/aws/tenant/<tenant_id>/emailer_preview")
    def aws_tenant_emailer_preview(tenant_id: str):
        try:
            token = _safe_member_id(tenant_id)
        except ValueError as e:
            abort(400, description=str(e))
        payload, status_code = _emailer_preview_response(
            workspace=workspace,
            private_dir=private_dir,
            member_id=token,
            legacy_route_term="tenant",
        )
        return jsonify(payload), status_code

    @app.route("/portal/api/aws/member/<member_id>/emailer_preview", methods=["OPTIONS"])
    @app.route("/portal/api/aws/tenant/<member_id>/emailer_preview", methods=["OPTIONS"])
    def aws_member_emailer_preview_options(member_id: str):
        _ = member_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, OPTIONS"
        return resp
