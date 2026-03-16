from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from flask import abort, jsonify, make_response, request

from ..data_engine import build_compiled_index
from ..mss import load_anthology_payload, preview_mss_context
from ..sandbox import SandboxEngine

try:
    from portal.services.alias_factory import (
        alias_filename,
        build_alias_from_contract,
        client_key_for_msn,
        merge_field_names,
        write_alias_file,
    )
except Exception:  # pragma: no cover - flavor dependent
    alias_filename = None
    build_alias_from_contract = None
    client_key_for_msn = None
    merge_field_names = None
    write_alias_file = None

try:
    from portal.services.progeny_config_store import get_client_config, get_config
except Exception:  # pragma: no cover - flavor dependent
    get_client_config = None
    get_config = None

from portal.services.contract_store import (
    ContractAlreadyExistsError,
    ContractNotFoundError,
    ContractValidationError,
    apply_compact_array_update,
    create_contract,
    get_contract,
    list_contracts,
    update_contract,
)
from portal.services.request_log_store import append_event


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


def _anthology_payload(anthology_path_fn: Callable[[], Path] | None) -> dict[str, Any]:
    if anthology_path_fn is None:
        return {}
    path = anthology_path_fn()
    if not path.exists():
        return {}
    try:
        return load_anthology_payload(path)
    except Exception as exc:  # pragma: no cover - malformed local data
        raise ContractValidationError(f"Unable to read anthology payload from {path}: {exc}") from exc


def _selected_refs_from_body(body: dict[str, Any]) -> list[str]:
    raw = body.get("owner_selected_refs")
    if isinstance(raw, list):
        return [_as_str(item) for item in raw if _as_str(item)]
    alt = body.get("selected_refs")
    if isinstance(alt, list):
        return [_as_str(item) for item in alt if _as_str(item)]
    return []


def _sandbox_engine_from_anthology_path(anthology_path_fn: Callable[[], Path] | None) -> SandboxEngine | None:
    if anthology_path_fn is None:
        return None
    try:
        path = anthology_path_fn()
    except Exception:
        return None
    data_root = path.parent if isinstance(path, Path) else None
    if data_root is None:
        return None
    return SandboxEngine(data_root=data_root)


def _maybe_compile_owner_mss(
    *,
    body: dict[str, Any],
    anthology_path_fn: Callable[[], Path] | None,
    local_msn_id: str,
) -> dict[str, Any]:
    compiled = dict(body)
    selected_refs = _selected_refs_from_body(compiled)
    if not selected_refs:
        compiled["owner_selected_refs"] = selected_refs
        return compiled
    sandbox_engine = _sandbox_engine_from_anthology_path(anthology_path_fn)
    if sandbox_engine is not None:
        compiled_result = sandbox_engine.compile_mss_resource(
            resource_id=f"contract:{_as_str(compiled.get('contract_id') or 'preview')}:owner_mss",
            selected_refs=selected_refs,
            anthology_payload=_anthology_payload(anthology_path_fn),
            local_msn_id=local_msn_id,
        )
        preview = dict(compiled_result.compiled_payload if isinstance(compiled_result.compiled_payload, dict) else {})
    else:
        preview = preview_mss_context(
            anthology_payload=_anthology_payload(anthology_path_fn),
            selected_refs=selected_refs,
            local_msn_id=local_msn_id,
        )
    compiled["owner_selected_refs"] = selected_refs
    compiled["owner_mss"] = _as_str(preview.get("bitstring"))
    return compiled


def _mss_preview_payload(
    *,
    body: dict[str, Any],
    anthology_path_fn: Callable[[], Path] | None,
    local_msn_id: str,
) -> dict[str, Any]:
    selected_refs = _selected_refs_from_body(body)
    sandbox_engine = _sandbox_engine_from_anthology_path(anthology_path_fn)
    if sandbox_engine is not None and selected_refs:
        owner_compiled = sandbox_engine.compile_mss_resource(
            resource_id=f"contract:{_as_str(body.get('contract_id') or 'preview')}:owner_mss",
            selected_refs=selected_refs,
            anthology_payload=_anthology_payload(anthology_path_fn),
            local_msn_id=local_msn_id,
        )
        owner_preview = dict(owner_compiled.compiled_payload if isinstance(owner_compiled.compiled_payload, dict) else {})
    else:
        owner_preview = preview_mss_context(
            anthology_payload=_anthology_payload(anthology_path_fn),
            selected_refs=selected_refs,
            bitstring="" if selected_refs else _as_str(body.get("owner_mss")),
            local_msn_id=local_msn_id,
        )
    if sandbox_engine is not None:
        counterparty_decoded = sandbox_engine.decode_mss_resource(
            bitstring=_as_str(body.get("counterparty_mss")),
            resource_id=f"contract:{_as_str(body.get('contract_id') or 'preview')}:counterparty_mss",
        )
        counterparty_preview = dict(
            counterparty_decoded.compiled_payload if isinstance(counterparty_decoded.compiled_payload, dict) else {}
        )
    else:
        counterparty_preview = preview_mss_context(bitstring=_as_str(body.get("counterparty_mss")))
    return {
        "owner_selected_refs": selected_refs,
        "owner_preview": owner_preview,
        "counterparty_preview": counterparty_preview,
        "owner_mss": _as_str(owner_preview.get("bitstring") or body.get("owner_mss")),
        "counterparty_mss": _as_str(body.get("counterparty_mss")),
    }


def _maybe_create_alias(
    *,
    private_dir: Path,
    local_msn_id: str,
    contract_id: str,
    contract_payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not all(
        [
            alias_filename,
            build_alias_from_contract,
            client_key_for_msn,
            merge_field_names,
            write_alias_file,
            get_client_config,
            get_config,
        ]
    ):
        return None

    progeny_type = _as_str(contract_payload.get("progeny_type"))
    if not progeny_type:
        return None

    client_msn_id = _as_str(contract_payload.get("client_msn_id")) or _as_str(
        contract_payload.get("counterparty_msn_id")
    )
    if not client_msn_id:
        return None

    base_cfg = get_config(progeny_type)
    base_fields = base_cfg.get("fields") if isinstance(base_cfg.get("fields"), list) else []

    client_overlay_fields = []
    client_key = client_key_for_msn(client_msn_id)
    if client_key:
        client_cfg = get_client_config(client_key)
        if isinstance(client_cfg, dict) and isinstance(client_cfg.get("fields"), list):
            client_overlay_fields = client_cfg.get("fields") or []

    alias_id = alias_filename(client_msn_id, local_msn_id, progeny_type)
    alias_payload = build_alias_from_contract(
        company_msn_id=local_msn_id,
        client_msn_id=client_msn_id,
        contract_id=contract_id,
        progeny_type=progeny_type,
        field_names=merge_field_names(base_fields, client_overlay_fields),
        host_title=_as_str(contract_payload.get("host_title")),
        alias_msn_id=_as_str(contract_payload.get("msn_id")) or local_msn_id,
        child_msn_id=_as_str(contract_payload.get("child_msn_id")),
        status=_as_str(contract_payload.get("status")) or "active",
    )
    alias_path = write_alias_file(private_dir, alias_id, alias_payload)
    append_event(
        private_dir,
        local_msn_id,
        {
            "type": "alias.created",
            "status": "active",
            "alias_id": alias_id,
            "client_msn_id": client_msn_id,
            "company_msn_id": local_msn_id,
            "contract_id": contract_id,
            "progeny_type": progeny_type,
            "details": {"alias_path": str(alias_path)},
        },
    )
    return {"alias_id": alias_id, "alias_path": str(alias_path)}


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

            owner_rows = (mss_preview.get("owner_preview") or {}).get("rows") or []
            if owner_rows:
                compiled_index = build_compiled_index(
                    contract_id=contract_id,
                    source_msn_id=msn_id,
                    target_msn_id=_as_str(contract.get("counterparty_msn_id")),
                    decoded_rows=list(owner_rows),
                    relationship_mode=_as_str(contract.get("relationship_mode") or ""),
                    access_mode=_as_str(contract.get("access_mode") or ""),
                    sync_mode=_as_str(contract.get("sync_mode") or ""),
                    revision=int(_as_str(contract.get("compact_index_revision") or "0") or 0),
                    compiled_at_unix_ms=int(_as_str(contract.get("compact_index_compiled_at_unix_ms") or "0") or 0),
                    source_card_revision=_as_str(contract.get("source_card_revision") or ""),
                )
                out["compiled_index"] = {
                    "contract_id": compiled_index.contract_id,
                    "relationship_mode": compiled_index.relationship_mode,
                    "access_mode": compiled_index.access_mode,
                    "sync_mode": compiled_index.sync_mode,
                    "source_msn_id": compiled_index.source_msn_id,
                    "target_msn_id": compiled_index.target_msn_id,
                    "revision": compiled_index.revision,
                    "compiled_at_unix_ms": compiled_index.compiled_at_unix_ms,
                    "source_card_revision": compiled_index.source_card_revision,
                    "entries": compiled_index.entries,
                }
        if options_private_fn is not None:
            out["options_private"] = options_private_fn(msn_id)
        return jsonify(out)

    @app.post("/portal/api/contracts")
    def contracts_create():
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")

        body = _maybe_compile_owner_mss(body=_json_body(), anthology_path_fn=anthology_path_fn, local_msn_id=msn_id)
        body.setdefault("owner_msn_id", msn_id)
        try:
            contract_id = create_contract(private_dir, body, owner_msn_id=msn_id)
        except ContractValidationError as exc:
            abort(400, description=str(exc))
        except ContractAlreadyExistsError as exc:
            abort(409, description=str(exc))

        alias_info = _maybe_create_alias(
            private_dir=private_dir,
            local_msn_id=msn_id,
            contract_id=contract_id,
            contract_payload=body,
        )
        out: dict[str, Any] = {
            "ok": True,
            "msn_id": msn_id,
            "contract_id": contract_id,
            "mss": _mss_preview_payload(body=body, anthology_path_fn=anthology_path_fn, local_msn_id=msn_id),
        }
        if alias_info:
            out["alias"] = alias_info
        return jsonify(out)

    @app.patch("/portal/api/contracts/<contract_id>")
    def contracts_patch(contract_id: str):
        msn_id = _as_str(request.args.get("msn_id"))
        if not msn_id:
            abort(400, description="Missing required query param: msn_id")

        body = _maybe_compile_owner_mss(body=_json_body(), anthology_path_fn=anthology_path_fn, local_msn_id=msn_id)
        try:
            existing = get_contract(private_dir, contract_id)
        except ContractNotFoundError as exc:
            abort(404, description=str(exc))
        current_rev = int(existing.get("compact_index_revision") or existing.get("revision") or 0)
        if (
            _as_str(body.get("owner_mss")) != _as_str(existing.get("owner_mss"))
            or body.get("owner_selected_refs") != existing.get("owner_selected_refs")
        ):
            body["compact_index_revision"] = current_rev + 1
            body["compact_index_compiled_at_unix_ms"] = int(time.time() * 1000)
        try:
            contract = update_contract(private_dir, contract_id, body, owner_msn_id=msn_id)
        except ContractNotFoundError as exc:
            abort(404, description=str(exc))
        except ContractValidationError as exc:
            abort(400, description=str(exc))

        out: dict[str, Any] = {
            "ok": True,
            "msn_id": msn_id,
            "contract_id": contract_id,
            "contract": contract,
            "mss": _mss_preview_payload(body=contract, anthology_path_fn=anthology_path_fn, local_msn_id=msn_id),
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
        from_revision = int(body.get("from_revision", 0))
        to_revision = int(body.get("to_revision", 0))
        change_type = _as_str(body.get("change_type")) or "replace_snapshot"
        source_msn_id = _as_str(body.get("source_msn_id"))
        target_msn_id = _as_str(body.get("target_msn_id"))
        ts_unix_ms = int(body.get("ts_unix_ms") or (time.time() * 1000))
        payload = body.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        try:
            contract = apply_compact_array_update(
                private_dir,
                contract_id,
                from_revision=from_revision,
                to_revision=to_revision,
                change_type=change_type,
                source_msn_id=source_msn_id,
                target_msn_id=target_msn_id,
                ts_unix_ms=ts_unix_ms,
                payload=payload,
                local_msn_id=msn_id,
            )
        except ContractNotFoundError as exc:
            abort(404, description=str(exc))
        except ContractValidationError as exc:
            abort(400, description=str(exc))
        append_event(
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
