from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from flask import abort, jsonify, make_response, request

from mycite_core.contract_line.context import (
    apply_compact_array_line_update,
    build_compiled_index_payload,
    create_contract_line,
    patch_contract_line,
    preview_contract_context,
)
from mycite_core.contract_line.store import (
    ContractAlreadyExistsError,
    ContractNotFoundError,
    ContractValidationError,
    get_contract,
    list_contracts,
)
from mycite_core.external_events.store import append_external_event


def _as_int(value: str | None, default: int, *, min_value: int = 0, max_value: int = 10_000) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except Exception:
        return default
    if number < min_value:
        return min_value
    if number > max_value:
        return max_value
    return number


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _json_body() -> dict[str, Any]:
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    return dict(body)


def _mss_preview_payload(
    *,
    body: dict[str, Any],
    anthology_path_fn: Callable[[], Path] | None,
    local_msn_id: str,
) -> dict[str, Any]:
    return preview_contract_context(
        body=body,
        anthology_path_fn=anthology_path_fn,
        local_msn_id=local_msn_id,
    )


def register_contract_routes(
    app,
    *,
    private_dir: Path,
    options_private_fn: Callable[[str], dict[str, Any]] | None = None,
    anthology_path_fn: Callable[[], Path] | None = None,
):
    @app.get("/portal/api/contracts")
    def contracts_list():
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")

        contract_type = _as_str(request.args.get("type")) or None
        limit = _as_int(request.args.get("limit"), 200, min_value=1, max_value=2000)
        offset = _as_int(request.args.get("offset"), 0, min_value=0, max_value=10_000_000)

        items = list_contracts(private_dir, filter_type=contract_type)
        sliced = items[offset : offset + limit]
        out: dict[str, Any] = {
            "msn_id": msn_id,
            "contracts": sliced,
            "meta": {"limit": limit, "offset": offset, "returned": len(sliced), "total": len(items)},
        }
        if options_private_fn is not None:
            out["options_private"] = options_private_fn(msn_id)
        return jsonify(out)

    @app.get("/portal/api/contracts/<contract_id>")
    def contracts_get(contract_id: str):
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")

        include_mss = _as_str(request.args.get("include_mss")).lower() in {"1", "true", "yes"}
        try:
            contract = get_contract(private_dir, contract_id)
        except ContractNotFoundError as exc:
            abort(404, description=str(exc))

        out: dict[str, Any] = {"msn_id": msn_id, "contract_id": contract_id, "contract": contract}
        if include_mss:
            mss_preview = _mss_preview_payload(
                body=contract,
                anthology_path_fn=anthology_path_fn,
                local_msn_id=msn_id,
            )
            out["mss"] = mss_preview

            compiled_index = build_compiled_index_payload(contract, local_msn_id=msn_id, context_preview=mss_preview)
            if compiled_index is not None:
                out["compiled_index"] = compiled_index
        if options_private_fn is not None:
            out["options_private"] = options_private_fn(msn_id)
        return jsonify(out)

    @app.post("/portal/api/contracts")
    def contracts_create():
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")

        try:
            result = create_contract_line(
                private_dir=private_dir,
                body=_json_body(),
                anthology_path_fn=anthology_path_fn,
                local_msn_id=msn_id,
            )
        except ContractValidationError as exc:
            abort(400, description=str(exc))
        except ContractAlreadyExistsError as exc:
            abort(409, description=str(exc))

        out: dict[str, Any] = {
            "ok": True,
            "msn_id": msn_id,
            "contract_id": result["contract_id"],
            "contract": result["contract"],
            "mss": result["mss"],
        }
        if result.get("alias"):
            out["alias"] = result["alias"]
        return jsonify(out)

    @app.patch("/portal/api/contracts/<contract_id>")
    def contracts_patch(contract_id: str):
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")

        try:
            result = patch_contract_line(
                private_dir=private_dir,
                contract_id=contract_id,
                patch=_json_body(),
                anthology_path_fn=anthology_path_fn,
                local_msn_id=msn_id,
            )
        except ContractNotFoundError as exc:
            abort(404, description=str(exc))
        except ContractValidationError as exc:
            abort(400, description=str(exc))

        out: dict[str, Any] = {
            "ok": True,
            "msn_id": msn_id,
            "contract_id": contract_id,
            "contract": result["contract"],
            "mss": result["mss"],
        }
        if options_private_fn is not None:
            out["options_private"] = options_private_fn(msn_id)
        return jsonify(out)

    @app.post("/portal/api/contracts/<contract_id>/compact-array/apply-update")
    def contracts_apply_compact_array_update(contract_id: str):
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")
        body = _json_body()
        try:
            contract = apply_compact_array_line_update(
                private_dir=private_dir,
                contract_id=contract_id,
                body=body,
                local_msn_id=msn_id,
            )
        except ContractNotFoundError as exc:
            abort(404, description=str(exc))
        except ContractValidationError as exc:
            abort(400, description=str(exc))
        from_revision = int(body.get("from_revision", 0))
        to_revision = int(body.get("to_revision", 0))
        change_type = _as_str(body.get("change_type")) or "replace_snapshot"
        source_msn_id = _as_str(body.get("source_msn_id"))
        target_msn_id = _as_str(body.get("target_msn_id"))
        ts_unix_ms = int(body.get("ts_unix_ms") or (time.time() * 1000))
        append_external_event(
            private_dir,
            msn_id,
            {
                "type": "compact_array.update_applied",
                "contract_id": contract_id,
                "from_revision": from_revision,
                "to_revision": to_revision,
                "change_type": change_type,
                "source_msn_id": source_msn_id,
                "target_msn_id": target_msn_id,
                "ts_unix_ms": ts_unix_ms,
            },
        )
        out = {
            "ok": True,
            "msn_id": msn_id,
            "contract_id": contract_id,
            "contract": contract,
        }
        if options_private_fn is not None:
            out["options_private"] = options_private_fn(msn_id)
        return jsonify(out)

    @app.post("/portal/api/contracts/mss/preview")
    def contracts_mss_preview():
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")
        body = _json_body()
        try:
            out: dict[str, Any] = {
                "ok": True,
                "msn_id": msn_id,
                "mss": _mss_preview_payload(
                    body=body,
                    anthology_path_fn=anthology_path_fn,
                    local_msn_id=msn_id,
                ),
            }
        except ContractValidationError as exc:
            abort(400, description=str(exc))
        if options_private_fn is not None:
            out["options_private"] = options_private_fn(msn_id)
        return jsonify(out)

    @app.route("/portal/api/contracts", methods=["OPTIONS"])
    @app.route("/portal/api/contracts/mss/preview", methods=["OPTIONS"])
    def contracts_collection_options():
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, POST, OPTIONS"
        return resp

    @app.route("/portal/api/contracts/<contract_id>", methods=["OPTIONS"])
    def contracts_item_options(contract_id: str):
        _ = contract_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, PATCH, OPTIONS"
        return resp
