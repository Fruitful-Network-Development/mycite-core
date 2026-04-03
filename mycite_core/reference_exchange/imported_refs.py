from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from mycite_core.runtime_paths import contract_read_dirs, reference_subscription_registry_path
from instances._shared.portal.data_engine.external_resources import ExternalResourceResolver
from instances._shared.portal.data_engine.resource_registry import (
    INHERITED_SCOPE,
    REFERENCE_PREFIX,
    compute_version_hash,
    ensure_layout,
    resource_file_path,
    upsert_index_entry,
    write_resource_file,
)

from mycite_core.contract_line.store import get_contract, list_contracts
from mycite_core.reference_exchange.registry import (
    disconnect_reference_source,
    get_reference_subscription,
    register_reference_ids,
    unregister_reference_ids,
    update_reference_sync,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _safe_reference_name(reference_id: str) -> str:
    token = _as_text(reference_id).lower()
    if token.startswith("rc.") or token.startswith("rf."):
        parts = token.split(".", 2)
        if len(parts) == 3:
            return parts[2]
    out = []
    for ch in token:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append(".")
    normalized = "".join(out).strip(".")
    return normalized or "reference"


def _legacy_contract_refresh_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("inherited_resource_sync")
    return dict(value) if isinstance(value, dict) else {}


def _legacy_contract_reference_ids(payload: dict[str, Any]) -> list[str]:
    resource_ids = payload.get("tracked_resource_ids")
    if isinstance(resource_ids, list):
        out = []
        seen: set[str] = set()
        for item in resource_ids:
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


def _normalize_reference_ids(raw_ids: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_ids:
        token = _as_text(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _subscription_record(
    private_dir: Path,
    *,
    contract_id: str,
    contract_payload: dict[str, Any],
) -> dict[str, Any]:
    source_msn_id = _as_text(contract_payload.get("counterparty_msn_id"))
    record = get_reference_subscription(
        private_dir,
        contract_id=contract_id,
        source_msn_id=source_msn_id,
    )
    tracked = list(record.get("tracked_reference_ids") or [])
    if not tracked:
        tracked = _legacy_contract_reference_ids(contract_payload)
    sync = record.get("sync") if isinstance(record.get("sync"), dict) else {}
    if not sync:
        sync = _legacy_contract_refresh_metadata(contract_payload)
    out = dict(record)
    out["source_msn_id"] = source_msn_id or _as_text(record.get("source_msn_id"))
    out["tracked_reference_ids"] = _normalize_reference_ids(tracked)
    out["sync"] = dict(sync)
    return out


def refresh_contract_reference(
    *,
    data_root: Path,
    private_dir: Path,
    resolver: ExternalResourceResolver,
    contract_id: str,
    reference_id: str,
    owner_msn_id: str = "",
    force_refresh: bool = True,
) -> dict[str, Any]:
    _ = owner_msn_id
    ensure_layout(data_root)
    contract = get_contract(private_dir, contract_id)
    source_msn_id = _as_text(contract.get("counterparty_msn_id"))
    if not source_msn_id:
        raise ValueError(f"contract {contract_id} has no counterparty_msn_id")

    fetched = resolver.fetch_and_cache_bundle(
        source_msn_id=source_msn_id,
        resource_id=_as_text(reference_id),
        force_refresh=bool(force_refresh),
    )
    if not bool(fetched.get("ok")):
        return {
            "ok": False,
            "contract_id": contract_id,
            "source_msn_id": source_msn_id,
            "reference_id": _as_text(reference_id),
            "resource_id": _as_text(reference_id),
            "error": _as_text(fetched.get("error")) or "fetch failed",
        }

    bundle = fetched.get("bundle") if isinstance(fetched.get("bundle"), dict) else {}
    decoded_payload = fetched.get("payload") if isinstance(fetched.get("payload"), dict) else {}
    reference_name = _safe_reference_name(reference_id)
    resource_path = resource_file_path(
        data_root,
        scope=INHERITED_SCOPE,
        source_msn_id=source_msn_id,
        resource_name=reference_name,
    )
    version_hash = compute_version_hash(decoded_payload or bundle)
    now_ms = int(time.time() * 1000)
    local_reference_id = f"{REFERENCE_PREFIX}.{source_msn_id}.{reference_name}"
    resource_body = {
        "schema": "mycite.portal.resource.reference.v2",
        "resource_id": local_reference_id,
        "reference_id": local_reference_id,
        "resource_kind": "outside_origin_reference",
        "scope": INHERITED_SCOPE,
        "source_msn_id": source_msn_id,
        "source_reference_id": _as_text(reference_id),
        "source_resource_id": _as_text(reference_id),
        "version_hash": version_hash,
        "updated_at": now_ms,
        "anthology_compatible_payload": decoded_payload,
        "bundle_metadata": bundle,
        "sync_metadata": {
            "contract_id": contract_id,
            "reference_id": local_reference_id,
            "resource_id": local_reference_id,
            "source_reference_id": _as_text(reference_id),
            "source_resource_id": _as_text(reference_id),
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
            "resource_id": local_reference_id,
            "reference_id": local_reference_id,
            "resource_name": resource_path.name,
            "reference_name": resource_path.name,
            "resource_kind": "outside_origin_reference",
            "scope": INHERITED_SCOPE,
            "source_msn_id": source_msn_id,
            "path": str(resource_path),
            "version_hash": version_hash,
            "updated_at": now_ms,
            "status": "synced",
        },
    )

    subscription = _subscription_record(private_dir, contract_id=contract_id, contract_payload=contract)
    sync_meta = subscription.get("sync") if isinstance(subscription.get("sync"), dict) else {}
    sync_resources = sync_meta.get("resources") if isinstance(sync_meta.get("resources"), list) else []
    next_resources = []
    for item in sync_resources:
        if not isinstance(item, dict):
            continue
        if _as_text(item.get("source_reference_id") or item.get("source_resource_id")) == _as_text(reference_id):
            continue
        if _as_text(item.get("reference_id") or item.get("resource_id")) == local_reference_id:
            continue
        next_resources.append(dict(item))
    next_resources.append(
        {
            "source_msn_id": source_msn_id,
            "contract_id": contract_id,
            "reference_id": local_reference_id,
            "resource_id": local_reference_id,
            "source_reference_id": _as_text(reference_id),
            "source_resource_id": _as_text(reference_id),
            "reference_name": reference_name,
            "resource_name": reference_name,
            "version_hash": version_hash,
            "last_sync_unix_ms": now_ms,
            "next_poll_unix_ms": now_ms + (15 * 60 * 1000),
            "status": "synced",
        }
    )
    sync_meta["resources"] = next_resources
    sync_meta["updated_unix_ms"] = now_ms
    update_reference_sync(
        private_dir,
        contract_id=contract_id,
        source_msn_id=source_msn_id,
        sync=sync_meta,
    )
    return {
        "ok": True,
        "contract_id": contract_id,
        "source_msn_id": source_msn_id,
        "reference_id": local_reference_id,
        "resource_id": local_reference_id,
        "source_reference_id": _as_text(reference_id),
        "source_resource_id": _as_text(reference_id),
        "reference_name": reference_name,
        "resource_name": reference_name,
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
        subscription = _subscription_record(private_dir, contract_id=contract_id, contract_payload=contract_payload)
        tracked = list(subscription.get("tracked_reference_ids") or [])
        if not tracked:
            warnings.append(f"contract {contract_id} has no tracked_reference_ids")
            continue
        for reference_id in tracked:
            result = refresh_contract_reference(
                data_root=data_root,
                private_dir=private_dir,
                resolver=resolver,
                contract_id=contract_id,
                reference_id=reference_id,
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
        subscription = _subscription_record(private_dir, contract_id=contract_id, contract_payload=payload)
        contracts.append(
            {
                "contract_id": contract_id,
                "source_msn_id": _as_text(subscription.get("source_msn_id")),
                "tracked_reference_ids": list(subscription.get("tracked_reference_ids") or []),
                "sync": dict(subscription.get("sync") if isinstance(subscription.get("sync"), dict) else {}),
            }
        )
    contracts.sort(key=lambda item: (_as_text(item.get("source_msn_id")), _as_text(item.get("contract_id"))))
    return {
        "ok": True,
        "schema": "mycite.portal.reference_exchange.subscriptions.v1",
        "contracts": contracts,
        "contract_dirs": [str(path) for path in contract_read_dirs(private_dir)],
        "registry_path": str(reference_subscription_registry_path(private_dir)),
    }


def disconnect_source_subscriptions(
    *,
    private_dir: Path,
    source_msn_id: str,
    owner_msn_id: str = "",
) -> dict[str, Any]:
    _ = owner_msn_id
    token_source = _as_text(source_msn_id)
    updated = disconnect_reference_source(private_dir, source_msn_id=token_source)

    # If the registry is still empty, seed disconnected state from legacy contract fields.
    if not updated:
        now_ms = int(time.time() * 1000)
        for item in list_contracts(private_dir):
            contract_id = _as_text(item.get("contract_id"))
            if not contract_id:
                continue
            payload = get_contract(private_dir, contract_id)
            if _as_text(payload.get("counterparty_msn_id")) != token_source:
                continue
            subscription = _subscription_record(private_dir, contract_id=contract_id, contract_payload=payload)
            sync_meta = dict(subscription.get("sync") if isinstance(subscription.get("sync"), dict) else {})
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
            updated_record = update_reference_sync(
                private_dir,
                contract_id=contract_id,
                source_msn_id=token_source,
                sync=sync_meta,
            )
            updated.append(updated_record)

    return {
        "ok": True,
        "source_msn_id": token_source,
        "updated_contracts": [
            {
                "contract_id": _as_text(item.get("contract_id")),
                "source_msn_id": _as_text(item.get("source_msn_id")),
                "resources_count": len(list((item.get("sync") or {}).get("resources") or [])),
            }
            for item in updated
        ],
    }


class InheritedSubscriptionService:
    """Reference exchange service for imported network-carried references."""

    def __init__(self, *, data_root: Path, private_dir: Path, resolver: ExternalResourceResolver, owner_msn_id: str = ""):
        self._data_root = Path(data_root)
        self._private_dir = Path(private_dir)
        self._resolver = resolver
        self._owner_msn_id = _as_text(owner_msn_id)

    def register_reference_subscription(self, *, contract_id: str, reference_ids: list[str]) -> dict[str, Any]:
        contract = get_contract(self._private_dir, contract_id)
        updated = register_reference_ids(
            self._private_dir,
            contract_id=contract_id,
            source_msn_id=_as_text(contract.get("counterparty_msn_id")),
            reference_ids=_normalize_reference_ids(list(reference_ids or [])),
        )
        return {
            "ok": True,
            "schema": "mycite.portal.references.subscription.register.v2",
            "contract_id": contract_id,
            "tracked_reference_ids": list(updated.get("tracked_reference_ids") or []),
        }

    def unregister_reference_subscription(self, *, contract_id: str, reference_ids: list[str]) -> dict[str, Any]:
        contract = get_contract(self._private_dir, contract_id)
        updated = unregister_reference_ids(
            self._private_dir,
            contract_id=contract_id,
            source_msn_id=_as_text(contract.get("counterparty_msn_id")),
            reference_ids=_normalize_reference_ids(list(reference_ids or [])),
        )
        return {
            "ok": True,
            "schema": "mycite.portal.references.subscription.unregister.v2",
            "contract_id": contract_id,
            "tracked_reference_ids": list(updated.get("tracked_reference_ids") or []),
        }

    def refresh_reference(self, *, contract_id: str, reference_id: str, force_refresh: bool = True) -> dict[str, Any]:
        return refresh_contract_reference(
            data_root=self._data_root,
            private_dir=self._private_dir,
            resolver=self._resolver,
            contract_id=contract_id,
            reference_id=reference_id,
            owner_msn_id=self._owner_msn_id,
            force_refresh=force_refresh,
        )

    def refresh_source(self, *, source_msn_id: str, force_refresh: bool = True) -> dict[str, Any]:
        return refresh_all_for_source(
            data_root=self._data_root,
            private_dir=self._private_dir,
            resolver=self._resolver,
            source_msn_id=source_msn_id,
            owner_msn_id=self._owner_msn_id,
            force_refresh=force_refresh,
        )

    def disconnect_source(self, *, source_msn_id: str) -> dict[str, Any]:
        return disconnect_source_subscriptions(
            private_dir=self._private_dir,
            source_msn_id=source_msn_id,
            owner_msn_id=self._owner_msn_id,
        )

    def list_subscriptions(self) -> dict[str, Any]:
        return discover_contract_subscription_status(self._private_dir)
