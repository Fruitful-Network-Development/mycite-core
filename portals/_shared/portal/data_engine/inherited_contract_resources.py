from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..runtime_paths import contract_read_dirs
from ..services.contract_store import get_contract, list_contracts, update_contract
from .external_resources import ExternalResourceResolver
from .resource_registry import (
    INHERITED_SCOPE,
    compute_version_hash,
    ensure_layout,
    resource_file_path,
    upsert_index_entry,
    write_resource_file,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _safe_resource_name(resource_id: str) -> str:
    token = _as_text(resource_id).lower()
    out = []
    for ch in token:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append(".")
    normalized = "".join(out).strip(".")
    return normalized or "resource"


def _contract_refresh_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("inherited_resource_sync")
    return dict(value) if isinstance(value, dict) else {}


def _contract_resources(payload: dict[str, Any]) -> list[str]:
    resources = payload.get("tracked_resource_ids")
    if isinstance(resources, list):
        out = []
        seen: set[str] = set()
        for item in resources:
            token = _as_text(item)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    tracked = details.get("tracked_resource_ids")
    if isinstance(tracked, list):
        out = []
        seen: set[str] = set()
        for item in tracked:
            token = _as_text(item)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out
    return []


def _upsert_contract_sync_metadata(
    private_dir: Path,
    *,
    contract_id: str,
    metadata: dict[str, Any],
    owner_msn_id: str = "",
) -> None:
    patch = {"inherited_resource_sync": dict(metadata)}
    update_contract(private_dir, contract_id, patch, owner_msn_id=owner_msn_id)


def refresh_contract_resource(
    *,
    data_root: Path,
    private_dir: Path,
    resolver: ExternalResourceResolver,
    contract_id: str,
    resource_id: str,
    owner_msn_id: str = "",
    force_refresh: bool = True,
) -> dict[str, Any]:
    ensure_layout(data_root)
    contract = get_contract(private_dir, contract_id)
    source_msn_id = _as_text(contract.get("counterparty_msn_id"))
    if not source_msn_id:
        raise ValueError(f"contract {contract_id} has no counterparty_msn_id")

    fetched = resolver.fetch_and_cache_bundle(
        source_msn_id=source_msn_id,
        resource_id=_as_text(resource_id),
        force_refresh=bool(force_refresh),
    )
    if not bool(fetched.get("ok")):
        return {
            "ok": False,
            "contract_id": contract_id,
            "source_msn_id": source_msn_id,
            "resource_id": _as_text(resource_id),
            "error": _as_text(fetched.get("error")) or "fetch failed",
        }

    bundle = fetched.get("bundle") if isinstance(fetched.get("bundle"), dict) else {}
    resource_name = _safe_resource_name(resource_id)
    resource_path = resource_file_path(
        data_root,
        scope=INHERITED_SCOPE,
        source_msn_id=source_msn_id,
        resource_name=f"{resource_name}.json",
    )
    version_hash = compute_version_hash(bundle)
    now_ms = int(time.time() * 1000)
    resource_body = {
        "schema": "mycite.portal.resource.inherited.v1",
        "resource_id": f"foreign:{source_msn_id}:{resource_name}",
        "resource_kind": "inherited_snapshot",
        "scope": "inherited",
        "source_msn_id": source_msn_id,
        "version_hash": version_hash,
        "updated_at": now_ms,
        "anthology_compatible_payload": bundle,
        "sync_metadata": {
            "contract_id": contract_id,
            "resource_id": _as_text(resource_id),
            "source_msn_id": source_msn_id,
            "last_sync_unix_ms": now_ms,
            "next_poll_unix_ms": now_ms + (15 * 60 * 1000),
            "status": "synced",
        },
    }
    write_resource_file(resource_path, resource_body)
    upsert_index_entry(
        data_root,
        scope=INHERITED_SCOPE,
        entry={
            "resource_id": resource_body["resource_id"],
            "resource_name": f"{resource_name}.json",
            "resource_kind": "inherited_snapshot",
            "scope": "inherited",
            "source_msn_id": source_msn_id,
            "path": str(resource_path),
            "version_hash": version_hash,
            "updated_at": now_ms,
            "status": "synced",
        },
    )

    sync_meta = _contract_refresh_metadata(contract)
    sync_resources = sync_meta.get("resources") if isinstance(sync_meta.get("resources"), list) else []
    next_resources = []
    for item in sync_resources:
        if not isinstance(item, dict):
            continue
        if _as_text(item.get("resource_id")) == _as_text(resource_id):
            continue
        next_resources.append(dict(item))
    next_resources.append(
        {
            "source_msn_id": source_msn_id,
            "contract_id": contract_id,
            "resource_id": _as_text(resource_id),
            "resource_name": resource_name,
            "version_hash": version_hash,
            "last_sync_unix_ms": now_ms,
            "next_poll_unix_ms": now_ms + (15 * 60 * 1000),
            "status": "synced",
        }
    )
    sync_meta["resources"] = next_resources
    sync_meta["updated_unix_ms"] = now_ms
    _upsert_contract_sync_metadata(
        private_dir,
        contract_id=contract_id,
        metadata=sync_meta,
        owner_msn_id=owner_msn_id or _as_text(contract.get("owner_msn_id")),
    )
    return {
        "ok": True,
        "contract_id": contract_id,
        "source_msn_id": source_msn_id,
        "resource_id": _as_text(resource_id),
        "resource_name": resource_name,
        "resource_path": str(resource_path),
        "version_hash": version_hash,
        "from_cache": bool(fetched.get("from_cache")),
    }


def refresh_all_for_source(
    *,
    data_root: Path,
    private_dir: Path,
    resolver: ExternalResourceResolver,
    source_msn_id: str,
    owner_msn_id: str = "",
    force_refresh: bool = True,
) -> dict[str, Any]:
    token_source = _as_text(source_msn_id)
    contracts = list_contracts(private_dir)
    matched = [item for item in contracts if _as_text(item.get("counterparty_msn_id")) == token_source]
    refreshed: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in matched:
        contract_id = _as_text(item.get("contract_id"))
        if not contract_id:
            continue
        contract_payload = get_contract(private_dir, contract_id)
        tracked = _contract_resources(contract_payload)
        if not tracked:
            warnings.append(f"contract {contract_id} has no tracked_resource_ids")
            continue
        for resource_id in tracked:
            result = refresh_contract_resource(
                data_root=data_root,
                private_dir=private_dir,
                resolver=resolver,
                contract_id=contract_id,
                resource_id=resource_id,
                owner_msn_id=owner_msn_id,
                force_refresh=force_refresh,
            )
            refreshed.append(result)
    return {
        "ok": True,
        "source_msn_id": token_source,
        "contracts_count": len(matched),
        "refreshed": refreshed,
        "warnings": warnings,
    }


def discover_contract_subscription_status(private_dir: Path) -> dict[str, Any]:
    contracts = []
    for item in list_contracts(private_dir):
        contract_id = _as_text(item.get("contract_id"))
        if not contract_id:
            continue
        payload = get_contract(private_dir, contract_id)
        source_msn_id = _as_text(payload.get("counterparty_msn_id"))
        sync_meta = _contract_refresh_metadata(payload)
        tracked = _contract_resources(payload)
        contracts.append(
            {
                "contract_id": contract_id,
                "source_msn_id": source_msn_id,
                "tracked_resource_ids": tracked,
                "sync": sync_meta,
            }
        )
    contracts.sort(key=lambda item: (_as_text(item.get("source_msn_id")), _as_text(item.get("contract_id"))))
    return {
        "ok": True,
        "schema": "mycite.portal.inherited_contract_subscriptions.v1",
        "contracts": contracts,
        "contract_dirs": [str(path) for path in contract_read_dirs(private_dir)],
    }


def disconnect_source_subscriptions(
    *,
    private_dir: Path,
    source_msn_id: str,
    owner_msn_id: str = "",
) -> dict[str, Any]:
    token_source = _as_text(source_msn_id)
    now_ms = int(time.time() * 1000)
    affected: list[dict[str, Any]] = []
    for item in list_contracts(private_dir):
        contract_id = _as_text(item.get("contract_id"))
        if not contract_id:
            continue
        payload = get_contract(private_dir, contract_id)
        if _as_text(payload.get("counterparty_msn_id")) != token_source:
            continue
        sync_meta = _contract_refresh_metadata(payload)
        resources = sync_meta.get("resources") if isinstance(sync_meta.get("resources"), list) else []
        next_resources: list[dict[str, Any]] = []
        for entry in resources:
            if not isinstance(entry, dict):
                continue
            next_entry = dict(entry)
            next_entry["status"] = "disconnected"
            next_entry["next_poll_unix_ms"] = 0
            next_resources.append(next_entry)
        sync_meta["resources"] = next_resources
        sync_meta["updated_unix_ms"] = now_ms
        sync_meta["status"] = "disconnected"
        _upsert_contract_sync_metadata(
            private_dir,
            contract_id=contract_id,
            metadata=sync_meta,
            owner_msn_id=owner_msn_id or _as_text(payload.get("owner_msn_id")),
        )
        affected.append({"contract_id": contract_id, "source_msn_id": token_source, "resources_count": len(next_resources)})
    return {
        "ok": True,
        "source_msn_id": token_source,
        "updated_contracts": affected,
    }
