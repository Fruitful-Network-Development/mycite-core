from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from ..data_engine import build_compiled_index
from ..mss import load_anthology_payload, preview_mss_context
from ..sandbox import SandboxEngine


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _anthology_payload(anthology_path_fn: Callable[[], Path] | None) -> dict[str, Any]:
    if anthology_path_fn is None:
        return {}
    path = anthology_path_fn()
    if not path.exists():
        return {}
    return load_anthology_payload(path)


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


def compile_owner_contract_context(
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


def preview_contract_context(
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


def apply_contract_context_patch(
    *,
    existing: dict[str, Any],
    patch: dict[str, Any],
    anthology_path_fn: Callable[[], Path] | None,
    local_msn_id: str,
) -> dict[str, Any]:
    compiled = compile_owner_contract_context(
        body=patch,
        anthology_path_fn=anthology_path_fn,
        local_msn_id=local_msn_id,
    )
    current_rev = int(existing.get("compact_index_revision") or existing.get("revision") or 0)
    if (
        _as_str(compiled.get("owner_mss")) != _as_str(existing.get("owner_mss"))
        or compiled.get("owner_selected_refs") != existing.get("owner_selected_refs")
    ):
        compiled["compact_index_revision"] = current_rev + 1
        compiled["compact_index_compiled_at_unix_ms"] = int(time.time() * 1000)
    return compiled


def build_compiled_index_payload(contract: dict[str, Any], *, local_msn_id: str, context_preview: dict[str, Any]) -> dict[str, Any] | None:
    owner_rows = (context_preview.get("owner_preview") or {}).get("rows") or []
    if not owner_rows:
        return None
    compiled_index = build_compiled_index(
        contract_id=_as_str(contract.get("contract_id")),
        source_msn_id=local_msn_id,
        target_msn_id=_as_str(contract.get("counterparty_msn_id")),
        decoded_rows=list(owner_rows),
        relationship_mode=_as_str(contract.get("relationship_mode") or ""),
        access_mode=_as_str(contract.get("access_mode") or ""),
        sync_mode=_as_str(contract.get("sync_mode") or ""),
        revision=int(_as_str(contract.get("compact_index_revision") or "0") or 0),
        compiled_at_unix_ms=int(_as_str(contract.get("compact_index_compiled_at_unix_ms") or "0") or 0),
        source_card_revision=_as_str(contract.get("source_card_revision") or ""),
    )
    return {
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
