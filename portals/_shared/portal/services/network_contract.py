from __future__ import annotations

from typing import Any, Callable
from urllib.parse import quote


def build_contract_preview(
    contract_payload: dict[str, Any],
    *,
    preview_mss_context_fn: Callable[..., dict[str, Any]],
    anthology_payload: dict[str, Any],
    local_msn_id: str,
) -> dict[str, Any]:
    owner_selected_refs = list(contract_payload.get("owner_selected_refs") or [])
    owner_preview = preview_mss_context_fn(
        anthology_payload=anthology_payload,
        selected_refs=owner_selected_refs,
        bitstring="" if owner_selected_refs else str(contract_payload.get("owner_mss") or ""),
        local_msn_id=str(local_msn_id or ""),
    )
    counterparty_preview = preview_mss_context_fn(bitstring=str(contract_payload.get("counterparty_mss") or ""))
    return {
        "owner_selected_refs": owner_selected_refs,
        "owner": owner_preview,
        "counterparty": counterparty_preview,
    }


def build_network_contract_items(
    *,
    private_dir,
    list_contracts_fn: Callable[[Any], list[dict[str, Any]]],
    get_contract_fn: Callable[[Any, str], dict[str, Any]],
    preview_mss_context_fn: Callable[..., dict[str, Any]],
    load_anthology_payload_fn: Callable[[], dict[str, Any]],
    local_msn_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    anthology_payload = load_anthology_payload_fn()
    for item in list_contracts_fn(private_dir):
        contract_id = str(item.get("contract_id") or "").strip()
        if not contract_id:
            continue
        try:
            contract_payload = get_contract_fn(private_dir, contract_id)
        except Exception:
            contract_payload = {"contract_id": contract_id}
        preview = build_contract_preview(
            contract_payload,
            preview_mss_context_fn=preview_mss_context_fn,
            anthology_payload=anthology_payload,
            local_msn_id=local_msn_id,
        )
        out.append(
            {
                "id": contract_id,
                "contract_id": contract_id,
                "label": str(contract_payload.get("contract_type") or contract_id).strip() or contract_id,
                "counterparty_msn_id": str(contract_payload.get("counterparty_msn_id") or "").strip(),
                "status": str(contract_payload.get("status") or "pending").strip(),
                "owner_selected_refs": list(contract_payload.get("owner_selected_refs") or []),
                "owner_mss_present": bool(str(contract_payload.get("owner_mss") or "").strip()),
                "counterparty_mss_present": bool(str(contract_payload.get("counterparty_mss") or "").strip()),
                "href": f"/portal/network?tab=contracts&id={quote(contract_id, safe='')}",
                "payload": contract_payload,
                "preview": preview,
            }
        )
    return out


def resolve_network_refs(
    payload: dict[str, Any],
    *,
    local_msn_id: str,
    anthology_payload: dict[str, Any],
    contract_payloads: list[dict[str, Any]],
    resolve_contract_datum_ref_fn: Callable[..., dict[str, Any]],
    preferred_contract_id: str = "",
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("event_datum", "status"):
        token = str(payload.get(key) or "").strip()
        if not token:
            continue
        try:
            out[key] = resolve_contract_datum_ref_fn(
                token,
                local_msn_id=str(local_msn_id or ""),
                anthology_payload=anthology_payload,
                contract_payloads=contract_payloads,
                preferred_contract_id=preferred_contract_id,
            )
        except Exception:
            continue
    return out
