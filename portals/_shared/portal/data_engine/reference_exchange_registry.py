from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..runtime_paths import reference_subscription_registry_path

REGISTRY_SCHEMA = "mycite.portal.reference_exchange.subscriptions.v1"


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _normalize_ids(raw_ids: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(raw_ids or []):
        token = _as_text(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _normalize_sync(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_subscription(record: dict[str, Any]) -> dict[str, Any]:
    tracked = record.get("tracked_reference_ids")
    if not isinstance(tracked, list):
        tracked = record.get("tracked_resource_ids") if isinstance(record.get("tracked_resource_ids"), list) else []
    normalized = {
        "contract_id": _as_text(record.get("contract_id")),
        "source_msn_id": _as_text(record.get("source_msn_id")),
        "tracked_reference_ids": _normalize_ids(list(tracked or [])),
        "sync": _normalize_sync(record.get("sync")),
        "updated_unix_ms": int(record.get("updated_unix_ms") or 0),
    }
    # Compatibility field kept for current APIs while the ontology shifts to references.
    normalized["tracked_resource_ids"] = list(normalized["tracked_reference_ids"])
    return normalized


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_registry(private_dir: Path) -> dict[str, Any]:
    path = reference_subscription_registry_path(private_dir)
    if not path.exists() or not path.is_file():
        return {"schema": REGISTRY_SCHEMA, "subscriptions": []}
    try:
        payload = _read_json(path)
    except Exception:
        return {"schema": REGISTRY_SCHEMA, "subscriptions": []}
    raw = payload.get("subscriptions") if isinstance(payload.get("subscriptions"), list) else []
    return {"schema": REGISTRY_SCHEMA, "subscriptions": [_normalize_subscription(item) for item in raw if isinstance(item, dict)]}


def _write_registry(private_dir: Path, payload: dict[str, Any]) -> Path:
    path = reference_subscription_registry_path(private_dir)
    normalized = {"schema": REGISTRY_SCHEMA, "subscriptions": [_normalize_subscription(item) for item in list(payload.get("subscriptions") or []) if isinstance(item, dict)]}
    _write_json(path, normalized)
    return path


def list_reference_subscriptions(private_dir: Path) -> list[dict[str, Any]]:
    payload = _load_registry(private_dir)
    items = list(payload.get("subscriptions") or [])
    items.sort(key=lambda item: (_as_text(item.get("source_msn_id")), _as_text(item.get("contract_id"))))
    return items


def get_reference_subscription(
    private_dir: Path,
    *,
    contract_id: str,
    source_msn_id: str = "",
) -> dict[str, Any]:
    token = _as_text(contract_id)
    for item in list_reference_subscriptions(private_dir):
        if _as_text(item.get("contract_id")) == token:
            if source_msn_id and _as_text(item.get("source_msn_id")) and _as_text(item.get("source_msn_id")) != _as_text(source_msn_id):
                continue
            return dict(item)
    return {
        "contract_id": token,
        "source_msn_id": _as_text(source_msn_id),
        "tracked_reference_ids": [],
        "tracked_resource_ids": [],
        "sync": {},
        "updated_unix_ms": 0,
    }


def save_reference_subscription(private_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    normalized = _normalize_subscription(record)
    normalized["updated_unix_ms"] = int(normalized.get("updated_unix_ms") or now_ms)
    payload = _load_registry(private_dir)
    items = []
    replaced = False
    for item in list(payload.get("subscriptions") or []):
        if _as_text(item.get("contract_id")) == _as_text(normalized.get("contract_id")):
            items.append(dict(normalized))
            replaced = True
        else:
            items.append(dict(item))
    if not replaced:
        items.append(dict(normalized))
    payload["subscriptions"] = items
    _write_registry(private_dir, payload)
    return normalized


def register_reference_ids(
    private_dir: Path,
    *,
    contract_id: str,
    source_msn_id: str,
    reference_ids: list[str],
) -> dict[str, Any]:
    existing = get_reference_subscription(private_dir, contract_id=contract_id, source_msn_id=source_msn_id)
    merged = _normalize_ids(list(existing.get("tracked_reference_ids") or []) + list(reference_ids or []))
    return save_reference_subscription(
        private_dir,
        {
            **existing,
            "contract_id": contract_id,
            "source_msn_id": _as_text(source_msn_id) or _as_text(existing.get("source_msn_id")),
            "tracked_reference_ids": merged,
            "sync": _normalize_sync(existing.get("sync")),
            "updated_unix_ms": int(time.time() * 1000),
        },
    )


def unregister_reference_ids(
    private_dir: Path,
    *,
    contract_id: str,
    source_msn_id: str,
    reference_ids: list[str],
) -> dict[str, Any]:
    existing = get_reference_subscription(private_dir, contract_id=contract_id, source_msn_id=source_msn_id)
    remove_set = set(_normalize_ids(list(reference_ids or [])))
    remaining = [item for item in list(existing.get("tracked_reference_ids") or []) if item not in remove_set]
    return save_reference_subscription(
        private_dir,
        {
            **existing,
            "contract_id": contract_id,
            "source_msn_id": _as_text(source_msn_id) or _as_text(existing.get("source_msn_id")),
            "tracked_reference_ids": remaining,
            "sync": _normalize_sync(existing.get("sync")),
            "updated_unix_ms": int(time.time() * 1000),
        },
    )


def update_reference_sync(
    private_dir: Path,
    *,
    contract_id: str,
    source_msn_id: str,
    sync: dict[str, Any],
) -> dict[str, Any]:
    existing = get_reference_subscription(private_dir, contract_id=contract_id, source_msn_id=source_msn_id)
    return save_reference_subscription(
        private_dir,
        {
            **existing,
            "contract_id": contract_id,
            "source_msn_id": _as_text(source_msn_id) or _as_text(existing.get("source_msn_id")),
            "tracked_reference_ids": list(existing.get("tracked_reference_ids") or []),
            "sync": _normalize_sync(sync),
            "updated_unix_ms": int(time.time() * 1000),
        },
    )


def disconnect_reference_source(private_dir: Path, *, source_msn_id: str) -> list[dict[str, Any]]:
    token_source = _as_text(source_msn_id)
    payload = _load_registry(private_dir)
    now_ms = int(time.time() * 1000)
    updated: list[dict[str, Any]] = []
    next_items: list[dict[str, Any]] = []
    for item in list(payload.get("subscriptions") or []):
        normalized = _normalize_subscription(item)
        if _as_text(normalized.get("source_msn_id")) != token_source:
            next_items.append(normalized)
            continue
        sync = _normalize_sync(normalized.get("sync"))
        resources = sync.get("resources") if isinstance(sync.get("resources"), list) else []
        marked: list[dict[str, Any]] = []
        for entry in resources:
            if not isinstance(entry, dict):
                continue
            next_entry = dict(entry)
            next_entry["status"] = "disconnected"
            next_entry["next_poll_unix_ms"] = 0
            marked.append(next_entry)
        sync["resources"] = marked
        sync["status"] = "disconnected"
        sync["updated_unix_ms"] = now_ms
        normalized["sync"] = sync
        normalized["updated_unix_ms"] = now_ms
        updated.append(dict(normalized))
        next_items.append(dict(normalized))
    payload["subscriptions"] = next_items
    _write_registry(private_dir, payload)
    return updated
