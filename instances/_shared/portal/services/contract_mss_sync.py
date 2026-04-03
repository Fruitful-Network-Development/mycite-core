from __future__ import annotations

from pathlib import Path
from typing import Any

from mycite_core.datum_refs import parse_datum_ref
from mycite_core.contract_line.store import get_contract, list_contracts, update_contract
from mycite_core.mss_resolution import compile_mss_payload, load_anthology_payload


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _normalize_selected_refs(
    selected_refs: list[str] | None,
    *,
    identifier_map: dict[str, str] | None = None,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    remap = dict(identifier_map or {})
    for raw in selected_refs or []:
        token = _as_text(raw)
        if not token:
            continue
        try:
            parsed = parse_datum_ref(token, field_name="owner_selected_ref")
            token = _as_text(remap.get(parsed.datum_address) or parsed.datum_address)
        except Exception:
            token = _as_text(remap.get(token) or token)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def sync_owner_contract_mss(
    *,
    private_dir: Path,
    owner_msn_id: str = "",
    anthology_path: str | Path | None = None,
    anthology_payload: dict[str, Any] | None = None,
    identifier_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    private_root = Path(private_dir)
    local_owner = _as_text(owner_msn_id)
    payload = dict(anthology_payload or {})
    if not payload:
        if anthology_path is None:
            raise ValueError("anthology_path or anthology_payload is required for contract MSS sync")
        payload = load_anthology_payload(Path(anthology_path))

    summary: dict[str, Any] = {
        "ok": True,
        "owner_msn_id": local_owner,
        "recompiled_contract_ids": [],
        "unchanged_contract_ids": [],
        "skipped_manual_contract_ids": [],
        "skipped_unowned_contract_ids": [],
        "failed_contracts": [],
        "warnings": [],
    }

    for item in list_contracts(private_root):
        contract_id = _as_text(item.get("contract_id"))
        if not contract_id:
            continue
        try:
            contract = get_contract(private_root, contract_id)
        except Exception as exc:
            summary["ok"] = False
            summary["failed_contracts"].append({"contract_id": contract_id, "error": str(exc)})
            continue

        contract_owner = _as_text(contract.get("owner_msn_id"))
        if local_owner and contract_owner and contract_owner != local_owner:
            summary["skipped_unowned_contract_ids"].append(contract_id)
            continue

        existing_selected_refs = list(contract.get("owner_selected_refs") or [])
        existing_owner_mss = _as_text(contract.get("owner_mss"))
        if not existing_selected_refs:
            if existing_owner_mss:
                summary["skipped_manual_contract_ids"].append(contract_id)
            continue

        selected_refs = _normalize_selected_refs(existing_selected_refs, identifier_map=identifier_map)
        try:
            compiled = compile_mss_payload(
                payload,
                selected_refs,
                local_msn_id=contract_owner or local_owner,
                include_selection_root=True,
            )
        except Exception as exc:
            summary["ok"] = False
            summary["failed_contracts"].append({"contract_id": contract_id, "error": str(exc)})
            continue

        next_owner_mss = _as_text(compiled.get("bitstring"))
        if selected_refs == existing_selected_refs and next_owner_mss == existing_owner_mss:
            summary["unchanged_contract_ids"].append(contract_id)
            continue

        try:
            update_contract(
                private_root,
                contract_id,
                {
                    "owner_selected_refs": selected_refs,
                    "owner_mss": next_owner_mss,
                },
                owner_msn_id=contract_owner or local_owner,
            )
        except Exception as exc:
            summary["ok"] = False
            summary["failed_contracts"].append({"contract_id": contract_id, "error": str(exc)})
            continue

        summary["recompiled_contract_ids"].append(contract_id)

    summary["contracts_seen"] = (
        len(summary["recompiled_contract_ids"])
        + len(summary["unchanged_contract_ids"])
        + len(summary["skipped_manual_contract_ids"])
        + len(summary["skipped_unowned_contract_ids"])
        + len(summary["failed_contracts"])
    )
    return summary
