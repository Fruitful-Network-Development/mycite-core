from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data_contract import compact_payload_to_rows, rows_to_compact_payload


LOCAL_SCOPE = "local"
INHERITED_SCOPE = "inherited"
SCOPES = {LOCAL_SCOPE, INHERITED_SCOPE}


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _safe_token(value: object) -> str:
    token = _as_text(value).lower()
    out = []
    for ch in token:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("._") or "resource"


def resources_root(data_root: Path) -> Path:
    return Path(data_root) / "resources"


def local_resources_dir(data_root: Path) -> Path:
    return resources_root(data_root) / "local"


def inherited_resources_dir(data_root: Path) -> Path:
    return resources_root(data_root) / "inherited"


def local_index_path(data_root: Path) -> Path:
    return resources_root(data_root) / "index.local.json"


def inherited_index_path(data_root: Path) -> Path:
    return resources_root(data_root) / "index.inherited.json"


def _default_index(schema: str) -> dict[str, Any]:
    return {
        "schema": schema,
        "generated_unix_ms": int(time.time() * 1000),
        "resources": [],
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    raw_text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw_text)
    except Exception:
        # Legacy payloads occasionally carry trailing commas.
        cleaned = re.sub(r",(\s*[}\]])", r"\1", raw_text)
        try:
            payload = json.loads(cleaned)
        except Exception:
            return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def ensure_layout(data_root: Path) -> None:
    local_resources_dir(data_root).mkdir(parents=True, exist_ok=True)
    inherited_resources_dir(data_root).mkdir(parents=True, exist_ok=True)
    if not local_index_path(data_root).exists():
        _write_json(local_index_path(data_root), _default_index("mycite.portal.resources.index.local.v1"))
    if not inherited_index_path(data_root).exists():
        _write_json(inherited_index_path(data_root), _default_index("mycite.portal.resources.index.inherited.v1"))


def _normalize_scope(scope: str) -> str:
    token = _as_text(scope).lower()
    if token not in SCOPES:
        raise ValueError(f"Unsupported resource scope: {scope}")
    return token


def _index_path_for_scope(data_root: Path, scope: str) -> Path:
    token = _normalize_scope(scope)
    return local_index_path(data_root) if token == LOCAL_SCOPE else inherited_index_path(data_root)


def _normalize_index_entry(entry: dict[str, Any], *, scope: str) -> dict[str, Any]:
    token_scope = _normalize_scope(scope)
    resource_name = _safe_token(entry.get("resource_name"))
    source_msn_id = _safe_token(entry.get("source_msn_id")) if token_scope == INHERITED_SCOPE else ""
    resource_kind = _as_text(entry.get("resource_kind")) or "resource"
    path = _as_text(entry.get("path"))
    resource_id = _as_text(entry.get("resource_id"))
    if not resource_id:
        if token_scope == LOCAL_SCOPE:
            resource_id = f"local:{resource_name.rstrip('.json')}"
        else:
            resource_id = f"foreign:{source_msn_id}:{resource_name.rstrip('.json')}"
    return {
        "resource_id": resource_id,
        "resource_name": resource_name,
        "resource_kind": resource_kind,
        "scope": token_scope,
        "source_msn_id": source_msn_id,
        "path": path,
        "version_hash": _as_text(entry.get("version_hash")),
        "updated_at": int(entry.get("updated_at") or 0),
        "status": _as_text(entry.get("status")) or "ready",
    }


def load_index(data_root: Path, *, scope: str) -> dict[str, Any]:
    ensure_layout(data_root)
    path = _index_path_for_scope(data_root, scope)
    payload = _read_json(path)
    if not payload:
        payload = _default_index(
            "mycite.portal.resources.index.local.v1"
            if _normalize_scope(scope) == LOCAL_SCOPE
            else "mycite.portal.resources.index.inherited.v1"
        )
    resources = payload.get("resources") if isinstance(payload.get("resources"), list) else []
    normalized = [_normalize_index_entry(item, scope=scope) for item in resources if isinstance(item, dict)]
    normalized.sort(
        key=lambda item: (
            _as_text(item.get("source_msn_id")),
            _as_text(item.get("resource_name")),
            _as_text(item.get("resource_id")),
        )
    )
    payload["resources"] = normalized
    return payload


def save_index(data_root: Path, *, scope: str, payload: dict[str, Any]) -> dict[str, Any]:
    index_payload = dict(payload if isinstance(payload, dict) else {})
    resources = index_payload.get("resources") if isinstance(index_payload.get("resources"), list) else []
    normalized = [_normalize_index_entry(item, scope=scope) for item in resources if isinstance(item, dict)]
    normalized.sort(
        key=lambda item: (
            _as_text(item.get("source_msn_id")),
            _as_text(item.get("resource_name")),
            _as_text(item.get("resource_id")),
        )
    )
    index_payload["resources"] = normalized
    index_payload["generated_unix_ms"] = int(time.time() * 1000)
    if _normalize_scope(scope) == LOCAL_SCOPE:
        index_payload.setdefault("schema", "mycite.portal.resources.index.local.v1")
    else:
        index_payload.setdefault("schema", "mycite.portal.resources.index.inherited.v1")
    _write_json(_index_path_for_scope(data_root, scope), index_payload)
    return index_payload


def resource_file_path(
    data_root: Path,
    *,
    scope: str,
    resource_name: str,
    source_msn_id: str = "",
) -> Path:
    token_scope = _normalize_scope(scope)
    name = _safe_token(resource_name)
    if not name.endswith(".json"):
        name += ".json"
    if token_scope == LOCAL_SCOPE:
        return local_resources_dir(data_root) / name
    source = _safe_token(source_msn_id)
    return inherited_resources_dir(data_root) / source / name


def _normalize_row_iterations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for row in rows:
        identifier = _as_text(row.get("identifier") or row.get("row_id"))
        try:
            layer_s, value_group_s, _iteration_s = identifier.split("-", 2)
            layer = int(layer_s)
            value_group = int(value_group_s)
        except Exception:
            passthrough.append(dict(row))
            continue
        grouped.setdefault((layer, value_group), []).append(dict(row))

    out: list[dict[str, Any]] = []
    for (layer, value_group), members in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        def _member_key(item: dict[str, Any]) -> tuple[int, str]:
            identifier = _as_text(item.get("identifier") or item.get("row_id"))
            try:
                _layer_s, _value_group_s, iteration_s = identifier.split("-", 2)
                return (int(iteration_s), identifier)
            except Exception:
                return (10**9, identifier)

        members.sort(key=_member_key)
        for index, row in enumerate(members, start=1):
            identifier = f"{layer}-{value_group}-{index}"
            row["identifier"] = identifier
            row["row_id"] = identifier
            out.append(row)
    out.extend(passthrough)
    out.sort(key=lambda item: _as_text(item.get("identifier") or item.get("row_id")))
    return out


def normalize_anthology_compatible_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    rows = compact_payload_to_rows(raw_payload if isinstance(raw_payload, dict) else {}, strict=False)
    normalized_rows = _normalize_row_iterations(rows)
    return rows_to_compact_payload(normalized_rows)


def compute_version_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload if isinstance(payload, dict) else {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_resource_file(path: Path) -> dict[str, Any]:
    return _read_json(path)


def write_resource_file(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload if isinstance(payload, dict) else {})
    anthology_payload = body.get("anthology_compatible_payload")
    if isinstance(anthology_payload, dict):
        body["anthology_compatible_payload"] = normalize_anthology_compatible_payload(anthology_payload)
    body["updated_at"] = int(body.get("updated_at") or time.time() * 1000)
    body["version_hash"] = _as_text(body.get("version_hash")) or compute_version_hash(body.get("anthology_compatible_payload") or {})
    _write_json(path, body)
    return body


def _extract_payload_from_sandbox_resource(data_root: Path, *, kind: str) -> dict[str, Any]:
    sandbox_root = Path(data_root) / "sandbox" / "resources"
    if not sandbox_root.exists() or not sandbox_root.is_dir():
        return {}
    prefix = "msn.samras." if kind == "samras_msn" else "txa.samras."
    candidates = sorted(sandbox_root.glob(f"{prefix}*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        payload = _read_json(candidate)
        canonical_state = payload.get("canonical_state") if isinstance(payload.get("canonical_state"), dict) else {}
        compact = canonical_state.get("compact_payload") if isinstance(canonical_state.get("compact_payload"), dict) else {}
        if compact:
            return compact
        resource_value = payload.get("resource_value") if isinstance(payload.get("resource_value"), dict) else {}
        if resource_value:
            return resource_value
    return {}


def upsert_index_entry(
    data_root: Path,
    *,
    scope: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    index_payload = load_index(data_root, scope=scope)
    resources = list(index_payload.get("resources") or [])
    normalized = _normalize_index_entry(entry, scope=scope)
    keep: list[dict[str, Any]] = []
    for item in resources:
        same_id = _as_text(item.get("resource_id")) == _as_text(normalized.get("resource_id"))
        same_name = (
            _as_text(item.get("resource_name")) == _as_text(normalized.get("resource_name"))
            and _as_text(item.get("source_msn_id")) == _as_text(normalized.get("source_msn_id"))
        )
        if same_id or same_name:
            continue
        keep.append(item)
    keep.append(normalized)
    index_payload["resources"] = keep
    save_index(data_root, scope=scope, payload=index_payload)
    return normalized


def remove_inherited_source(data_root: Path, *, source_msn_id: str) -> dict[str, Any]:
    index_payload = load_index(data_root, scope=INHERITED_SCOPE)
    token = _safe_token(source_msn_id)
    resources = list(index_payload.get("resources") or [])
    kept = [item for item in resources if _safe_token(item.get("source_msn_id")) != token]
    removed = [item for item in resources if _safe_token(item.get("source_msn_id")) == token]
    index_payload["resources"] = kept
    save_index(data_root, scope=INHERITED_SCOPE, payload=index_payload)
    source_dir = inherited_resources_dir(data_root) / token
    if source_dir.exists() and source_dir.is_dir():
        for path in source_dir.glob("*.json"):
            try:
                path.unlink()
            except Exception:
                continue
        try:
            source_dir.rmdir()
        except Exception:
            pass
    return {"removed_count": len(removed), "source_msn_id": token}


@dataclass(frozen=True)
class LegacySamrasMigrationReport:
    ok: bool
    migrated: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "migrated": [dict(item) for item in self.migrated],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def migrate_legacy_samras_root_files(data_root: Path, *, apply_changes: bool = True) -> LegacySamrasMigrationReport:
    ensure_layout(data_root)
    targets = [
        (["samras-msn.json", "samras-msn.legacy.json"], "samras.msn.json", "samras_msn", "local:samras.msn"),
        (["samras-txa.json", "samras-txa.legacy.json"], "samras.txa.json", "samras_txa", "local:samras.txa"),
    ]
    migrated: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    for legacy_candidates, next_name, kind, resource_id in targets:
        legacy_path = None
        for candidate in legacy_candidates:
            candidate_path = Path(data_root) / candidate
            if candidate_path.exists() and candidate_path.is_file():
                legacy_path = candidate_path
                break
        if legacy_path is None:
            warnings.append(f"legacy file missing: {legacy_candidates[0]}")
            continue
        if not legacy_path.exists() or not legacy_path.is_file():
            warnings.append(f"legacy file missing: {legacy_candidates[0]}")
            continue
        raw_payload = _read_json(legacy_path)
        if not raw_payload:
            raw_payload = _extract_payload_from_sandbox_resource(data_root, kind=kind)
        anthology_payload = normalize_anthology_compatible_payload(raw_payload)
        target_path = resource_file_path(data_root, scope=LOCAL_SCOPE, resource_name=next_name)
        resource_body = {
            "schema": "mycite.portal.resource.local.v1",
            "resource_id": resource_id,
            "resource_kind": kind,
            "scope": LOCAL_SCOPE,
            "source_msn_id": "",
            "updated_at": int(time.time() * 1000),
            "anthology_compatible_payload": anthology_payload,
            "draft_metadata": {},
            "compile_metadata": {},
            "publish_metadata": {},
        }
        version_hash = compute_version_hash(anthology_payload)
        resource_body["version_hash"] = version_hash
        if apply_changes:
            write_resource_file(target_path, resource_body)
            upsert_index_entry(
                data_root,
                scope=LOCAL_SCOPE,
                entry={
                    "resource_id": resource_id,
                    "resource_name": next_name,
                    "resource_kind": kind,
                    "scope": LOCAL_SCOPE,
                    "source_msn_id": "",
                    "path": str(target_path),
                    "version_hash": version_hash,
                    "updated_at": int(time.time() * 1000),
                    "status": "ready",
                },
            )
        migrated.append(
            {
                "legacy_path": str(legacy_path),
                "resource_path": str(target_path),
                "resource_id": resource_id,
                "resource_name": next_name,
                "version_hash": version_hash,
            }
        )

    ok = not errors
    return LegacySamrasMigrationReport(ok=ok, migrated=migrated, warnings=warnings, errors=errors)
