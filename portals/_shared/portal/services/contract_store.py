from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from ..runtime_paths import contract_read_dirs, contracts_dir


CONTRACT_SCHEMA_V1 = "mycite.portal.contract.v1"
CONTRACT_SCHEMA_V2 = "mycite.portal.contract.v2"

FORBIDDEN_SECRET_KEYS = {
    "private_key",
    "private_key_pem",
    "secret",
    "token",
    "password",
    "symmetric_key",
    "hmac_key",
    "hmac_key_b64",
    "api_key",
}

ALLOWED_STATUS = {"pending", "active", "revoked", "expired"}


class ContractValidationError(ValueError):
    pass


class ContractNotFoundError(FileNotFoundError):
    pass


class ContractAlreadyExistsError(FileExistsError):
    pass


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContractValidationError(f"Expected object JSON at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _safe_contract_id(contract_id: str) -> str:
    return _as_text(contract_id).replace("/", "_").replace("\\", "_").replace("..", "_")


def _canonical_filename(contract_id: str) -> str:
    return f"contract-{_safe_contract_id(contract_id)}.json"


def _new_contract_id() -> str:
    return uuid.uuid4().hex


def _normalize_status(payload: dict[str, Any]) -> None:
    status = _as_text(payload.get("status"))
    if not status:
        return
    if status not in ALLOWED_STATUS:
        raise ContractValidationError(f"Invalid contract status: {status}")


def _reject_secrets(payload: dict[str, Any]) -> None:
    bad = {key for key in payload if str(key).lower() in FORBIDDEN_SECRET_KEYS}
    if bad:
        raise ContractValidationError(
            f"Do not store secrets in contract metadata. Forbidden keys: {sorted(bad)}"
        )


def _normalize_mss_value(value: Any, *, field_name: str) -> str:
    if isinstance(value, list) and not value:
        return ""
    token = _as_text(value)
    if not token:
        return ""
    if any(char not in {"0", "1"} for char in token):
        raise ContractValidationError(f"{field_name} must be a raw bitstring")
    return token


def _normalize_selected_refs(value: Any, *, field_name: str) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise ContractValidationError(f"{field_name} must be a list of datum refs")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        token = _as_text(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _normalize_tracked_resource_ids(payload: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    candidates: list[Any] = []
    candidates.append(payload.get("tracked_resource_ids"))
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    candidates.append(details.get("tracked_resource_ids"))
    for candidate in candidates:
        if not isinstance(candidate, list):
            continue
        for item in candidate:
            token = _as_text(item)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


def _infer_contract_id(payload: dict[str, Any], filename: str = "") -> str:
    explicit = _as_text(payload.get("contract_id"))
    if explicit:
        return explicit
    stem = Path(filename).stem
    if stem.startswith("contract-"):
        return stem.replace("contract-", "", 1)
    return stem


def normalize_contract_payload(
    payload: dict[str, Any],
    *,
    contract_id: str = "",
    owner_msn_id: str = "",
    for_write: bool = False,
    reject_secrets: bool = True,
    now_ms: int | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("Contract payload must be a JSON object")

    base = dict(payload)
    if for_write and reject_secrets:
        _reject_secrets(base)

    normalized_id = _as_text(contract_id or base.get("contract_id")) or _new_contract_id()
    contract_type = _as_text(base.get("contract_type") or base.get("type"))
    counterparty_msn_id = _as_text(base.get("counterparty_msn_id"))
    local_owner_msn_id = _as_text(base.get("owner_msn_id") or owner_msn_id)
    created_unix_ms = int(base.get("created_unix_ms") or (now_ms or int(time.time() * 1000)))
    updated_unix_ms = int(base.get("updated_unix_ms") or (now_ms or int(time.time() * 1000)))

    if for_write and not contract_type:
        raise ContractValidationError("Missing required field: contract_type")
    if for_write and not counterparty_msn_id:
        raise ContractValidationError("Missing required field: counterparty_msn_id")
    if for_write and not local_owner_msn_id:
        raise ContractValidationError("Missing required field: owner_msn_id")

    out = dict(base)
    out["schema"] = CONTRACT_SCHEMA_V2
    if _as_text(base.get("schema")) and _as_text(base.get("schema")) != CONTRACT_SCHEMA_V2:
        out["schema_input"] = _as_text(base.get("schema"))
    out["contract_id"] = normalized_id
    if contract_type:
        out["contract_type"] = contract_type
    if local_owner_msn_id:
        out["owner_msn_id"] = local_owner_msn_id
    if counterparty_msn_id:
        out["counterparty_msn_id"] = counterparty_msn_id
    out["status"] = _as_text(base.get("status") or "pending") or "pending"
    out["template_version"] = _as_text(base.get("template_version") or "1.0.0") or "1.0.0"
    out["created_unix_ms"] = created_unix_ms
    out["updated_unix_ms"] = updated_unix_ms
    out["details"] = dict(base.get("details") or {}) if isinstance(base.get("details"), dict) else {}
    out["owner_mss"] = _normalize_mss_value(base.get("owner_mss"), field_name="owner_mss")
    out["counterparty_mss"] = _normalize_mss_value(
        base.get("counterparty_mss"),
        field_name="counterparty_mss",
    )
    out["owner_selected_refs"] = _normalize_selected_refs(
        base.get("owner_selected_refs"),
        field_name="owner_selected_refs",
    )
    out["counterparty_selected_refs"] = _normalize_selected_refs(
        base.get("counterparty_selected_refs"),
        field_name="counterparty_selected_refs",
    )
    out["tracked_resource_ids"] = _normalize_tracked_resource_ids(base)
    out["details"]["tracked_resource_ids"] = list(out["tracked_resource_ids"])
    # Optional compact-array index / update-protocol fields (CONTRACT_COMPACT_INDEX, CONTRACT_UPDATE_PROTOCOL)
    for key in ("relationship_mode", "access_mode", "sync_mode", "source_card_revision"):
        if key in base and _as_text(base.get(key)):
            out[key] = _as_text(base[key])
    rev = base.get("compact_index_revision", base.get("revision"))
    if rev is not None:
        try:
            out["compact_index_revision"] = int(rev)
        except (TypeError, ValueError):
            pass
    compiled_ms = base.get("compact_index_compiled_at_unix_ms")
    if compiled_ms is not None:
        try:
            out["compact_index_compiled_at_unix_ms"] = int(compiled_ms)
        except (TypeError, ValueError):
            pass
    _normalize_status(out)
    return out


def _iter_contract_files(private_dir: Path) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for directory in contract_read_dirs(private_dir):
        if not directory.exists() or not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            if path in seen:
                continue
            seen.add(path)
            out.append(path)
    return out


def _matching_paths(private_dir: Path, contract_id: str) -> list[Path]:
    token = _safe_contract_id(contract_id)
    candidates = [_canonical_filename(contract_id), f"{token}.json"]
    out: list[Path] = []
    for directory in contract_read_dirs(private_dir):
        for filename in candidates:
            path = directory / filename
            if path.exists() and path.is_file():
                out.append(path)
    return out


def list_contracts(private_dir: Path, filter_type: str | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in _iter_contract_files(private_dir):
        try:
            payload = _read_json(path)
            contract_id = _infer_contract_id(payload, path.name)
            normalized = normalize_contract_payload(payload, contract_id=contract_id)
        except Exception:
            continue
        contract_id = _as_text(normalized.get("contract_id"))
        if not contract_id or contract_id in seen_ids:
            continue
        if filter_type and _as_text(normalized.get("contract_type")) != _as_text(filter_type):
            continue
        seen_ids.add(contract_id)
        items.append(
            {
                "contract_id": contract_id,
                "contract_type": _as_text(normalized.get("contract_type")),
                "owner_msn_id": _as_text(normalized.get("owner_msn_id")),
                "counterparty_msn_id": _as_text(normalized.get("counterparty_msn_id")),
                "status": _as_text(normalized.get("status")),
                "updated_unix_ms": int(normalized.get("updated_unix_ms") or 0),
                "owner_mss_present": bool(_as_text(normalized.get("owner_mss"))),
                "counterparty_mss_present": bool(_as_text(normalized.get("counterparty_mss"))),
                "owner_selected_refs": list(normalized.get("owner_selected_refs") or []),
                "path": str(path),
            }
        )
    return sorted(items, key=lambda item: (_as_text(item.get("contract_id")).lower(), _as_text(item.get("path"))))


def get_contract(private_dir: Path, contract_id: str) -> dict[str, Any]:
    for path in _matching_paths(private_dir, contract_id):
        payload = _read_json(path)
        inferred_id = _infer_contract_id(payload, path.name)
        normalized = normalize_contract_payload(payload, contract_id=inferred_id)
        if _as_text(normalized.get("contract_id")) == _as_text(contract_id):
            normalized["path"] = str(path)
            return normalized

    for path in _iter_contract_files(private_dir):
        try:
            payload = _read_json(path)
            inferred_id = _infer_contract_id(payload, path.name)
            normalized = normalize_contract_payload(payload, contract_id=inferred_id)
        except Exception:
            continue
        if _as_text(normalized.get("contract_id")) == _as_text(contract_id):
            normalized["path"] = str(path)
            return normalized

    raise ContractNotFoundError(f"Contract not found: {contract_id}")


def _write_contract(private_dir: Path, contract_id: str, payload: dict[str, Any]) -> Path:
    target = contracts_dir(private_dir) / _canonical_filename(contract_id)
    _write_json(target, payload)
    return target


def create_contract(private_dir: Path, metadata: dict[str, Any], *, owner_msn_id: str = "") -> str:
    contract_id = _as_text(metadata.get("contract_id")) or _new_contract_id()
    now_ms = int(time.time() * 1000)
    for path in _matching_paths(private_dir, contract_id):
        if path.exists():
            raise ContractAlreadyExistsError(f"Contract already exists: {contract_id}")

    normalized = normalize_contract_payload(
        metadata,
        contract_id=contract_id,
        owner_msn_id=owner_msn_id,
        for_write=True,
        now_ms=now_ms,
    )
    normalized["created_unix_ms"] = now_ms
    normalized["updated_unix_ms"] = now_ms
    _write_contract(private_dir, contract_id, normalized)
    return contract_id


def upsert_contract(private_dir: Path, contract_id: str, payload: dict[str, Any], *, owner_msn_id: str = "") -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    existing: dict[str, Any] = {}
    try:
        existing = get_contract(private_dir, contract_id)
    except ContractNotFoundError:
        existing = {}

    merged = dict(existing)
    merged.update(dict(payload))
    merged["contract_id"] = contract_id
    if owner_msn_id and not _as_text(merged.get("owner_msn_id")):
        merged["owner_msn_id"] = owner_msn_id
    normalized = normalize_contract_payload(
        merged,
        contract_id=contract_id,
        owner_msn_id=owner_msn_id,
        for_write=True,
        reject_secrets=False,
        now_ms=now_ms,
    )
    normalized["created_unix_ms"] = int(existing.get("created_unix_ms") or now_ms)
    normalized["updated_unix_ms"] = now_ms
    _write_contract(private_dir, contract_id, normalized)
    return normalized


def update_contract(private_dir: Path, contract_id: str, patch: dict[str, Any], *, owner_msn_id: str = "") -> dict[str, Any]:
    existing = get_contract(private_dir, contract_id)
    _reject_secrets(dict(patch or {}))
    merged = dict(existing)
    for key, value in dict(patch or {}).items():
        if key in {"contract_id", "created_unix_ms", "schema", "schema_input", "path"}:
            continue
        merged[key] = value
    merged["contract_id"] = contract_id
    merged["created_unix_ms"] = int(existing.get("created_unix_ms") or int(time.time() * 1000))
    return upsert_contract(private_dir, contract_id, merged, owner_msn_id=owner_msn_id or _as_text(existing.get("owner_msn_id")))


def apply_compact_array_update(
    private_dir: Path,
    contract_id: str,
    *,
    from_revision: int,
    to_revision: int,
    change_type: str,
    source_msn_id: str,
    target_msn_id: str,
    ts_unix_ms: int,
    payload: dict[str, Any] | None = None,
    local_msn_id: str = "",
) -> dict[str, Any]:
    """
    Apply an external compact-array update: validate from_revision, apply payload, persist.
    Used when this portal receives an update from a counterparty (e.g. new counterparty_mss).
    Caller is responsible for appending request_log evidence.
    """
    existing = get_contract(private_dir, contract_id)
    current_rev = int(existing.get("compact_index_revision") or existing.get("revision") or 0)
    if from_revision != current_rev:
        raise ContractValidationError(
            f"Revision mismatch: expected from_revision={current_rev}, got {from_revision}"
        )
    payload = dict(payload or {})
    patch: dict[str, Any] = {
        "compact_index_revision": to_revision,
        "compact_index_compiled_at_unix_ms": ts_unix_ms,
        "updated_unix_ms": ts_unix_ms,
    }
    if _as_text(payload.get("counterparty_mss")):
        patch["counterparty_mss"] = _normalize_mss_value(
            payload.get("counterparty_mss"), field_name="counterparty_mss"
        )
    return update_contract(
        private_dir, contract_id, patch, owner_msn_id=local_msn_id or _as_text(existing.get("owner_msn_id"))
    )
