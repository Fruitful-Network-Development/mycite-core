from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

from flask import abort, jsonify, make_response
from portal.services.progeny_workspace import find_member_instance

_MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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
    record = find_member_instance(private_dir, member_id)
    if record is None:
        abort(404, description=f"No progeny profile found for member_id={member_id}")

    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    normalized_profile = normalize_member_profile(member_id, payload)
    profile_refs = (
        normalized_profile.get("profile_refs")
        if isinstance(normalized_profile.get("profile_refs"), dict)
        else {}
    )
    email_policy = (
        normalized_profile.get("email_policy")
        if isinstance(normalized_profile.get("email_policy"), dict)
        else {}
    )
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
                "member_profile": {
                    "member_id": str(normalized_profile.get("member_id") or member_id),
                    "member_msn_id": str(normalized_profile.get("member_msn_id") or ""),
                    "capabilities": normalized_profile.get("capabilities") if isinstance(normalized_profile.get("capabilities"), dict) else {},
                    "profile_refs": profile_refs,
                    "email_policy": email_policy,
                },
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
    source = response.get("source") if isinstance(response.get("source"), dict) else {}
    if isinstance(source, dict):
        source.setdefault("aws_profile_id", str(profile_refs.get("aws_profile_id") or ""))
        source.setdefault("email_transport_mode", str(profile_refs.get("email_transport_mode") or ""))
        source.setdefault("newsletter_ingest_address", str(profile_refs.get("newsletter_ingest_address") or ""))
        source.setdefault("newsletter_sender_address", str(profile_refs.get("newsletter_sender_address") or ""))
        source.setdefault("email_operator_inbox", str(profile_refs.get("email_operator_inbox") or ""))
        response["source"] = source
    existing_warnings = [str(item) for item in list(response.get("warnings") or [])]
    policy_warnings: list[str] = []
    mode = str(email_policy.get("mode") or "").strip().lower()
    if mode and mode != "forwarder_no_smtp":
        policy_warnings.append(
            "email_policy.mode is not forwarder_no_smtp; this flow is intended for forwarder/no-SMTP routing."
        )
    newsletter = email_policy.get("newsletter") if isinstance(email_policy.get("newsletter"), dict) else {}
    if not str(newsletter.get("ingest_address") or "").strip():
        policy_warnings.append("email_policy.newsletter.ingest_address is not set.")
    if not str(newsletter.get("sender_address") or "").strip():
        policy_warnings.append("email_policy.newsletter.sender_address is not set.")
    response["warnings"] = policy_warnings + existing_warnings
    response.setdefault(
        "member_profile",
        {
            "member_id": str(normalized_profile.get("member_id") or member_id),
            "member_msn_id": str(normalized_profile.get("member_msn_id") or ""),
            "capabilities": normalized_profile.get("capabilities") if isinstance(normalized_profile.get("capabilities"), dict) else {},
            "profile_refs": profile_refs,
            "email_policy": email_policy,
        },
    )
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
