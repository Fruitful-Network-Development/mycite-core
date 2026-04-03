from __future__ import annotations

from pathlib import Path
from typing import Any

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

from mycite_core.external_events.store import append_external_event


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def maybe_create_alias_from_contract(
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
    append_external_event(
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
