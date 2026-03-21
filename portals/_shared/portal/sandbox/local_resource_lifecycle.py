from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..data_engine.resource_registry import (
    LOCAL_SCOPE,
    ensure_layout,
    load_index,
    migrate_legacy_samras_root_files,
    resource_file_path,
    upsert_index_entry,
    write_resource_file,
)
from .engine import SandboxEngine


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _resource_name_from_id(resource_id: str) -> str:
    token = _as_text(resource_id).lower()
    if token.startswith("local:"):
        token = token.split(":", 1)[1]
    token = token.replace("/", ".")
    if not token.endswith(".json"):
        token += ".json"
    return token


def _resource_id_from_name(resource_name: str) -> str:
    token = _as_text(resource_name).lower()
    if token.endswith(".json"):
        token = token[: -len(".json")]
    return f"local:{token}"


def _resource_payload_from_sandbox(payload: dict[str, Any]) -> dict[str, Any]:
    canonical_state = payload.get("canonical_state") if isinstance(payload.get("canonical_state"), dict) else {}
    compact = canonical_state.get("compact_payload") if isinstance(canonical_state.get("compact_payload"), dict) else {}
    if compact:
        return compact
    resource_value = payload.get("resource_value") if isinstance(payload.get("resource_value"), dict) else {}
    if resource_value:
        return resource_value
    return {}


class LocalResourceLifecycleService:
    """Canonical local resource lifecycle facade.

    Sandbox remains owner of draft/edit/compile state.
    Resource registry remains owner of durable local inventory/index.
    """

    def __init__(self, *, data_root: Path, sandbox_engine: SandboxEngine):
        self._data_root = Path(data_root)
        self._sandbox_engine = sandbox_engine
        ensure_layout(self._data_root)

    def list_local_inventory(self) -> dict[str, Any]:
        index_payload = load_index(self._data_root, scope=LOCAL_SCOPE)
        return {
            "ok": True,
            "schema": "mycite.portal.resources.local_inventory.v1",
            "resources_root": str(self._data_root / "resources" / "local"),
            "index_path": str(self._data_root / "resources" / "index.local.json"),
            "resources": list(index_payload.get("resources") or []),
        }

    def migrate_legacy_samras(self, *, apply_changes: bool = True) -> dict[str, Any]:
        report = migrate_legacy_samras_root_files(self._data_root, apply_changes=apply_changes)
        payload = report.to_dict()
        payload["ok"] = bool(payload.get("ok"))
        payload["apply"] = bool(apply_changes)
        payload["schema"] = "mycite.portal.resources.local_migration.v1"
        return payload

    def create(self, *, resource_kind: str, resource_name: str, seed_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        name = _resource_name_from_id(resource_name)
        resource_id = _resource_id_from_name(name)
        now_ms = int(time.time() * 1000)
        body = {
            "schema": "mycite.portal.resource.local.v1",
            "resource_id": resource_id,
            "resource_kind": _as_text(resource_kind) or "resource",
            "scope": "local",
            "source_msn_id": "",
            "updated_at": now_ms,
            "anthology_compatible_payload": dict(seed_payload or {}),
            "draft_metadata": {},
            "compile_metadata": {},
            "publish_metadata": {"created_unix_ms": now_ms},
        }
        path = resource_file_path(self._data_root, scope=LOCAL_SCOPE, resource_name=name)
        written = write_resource_file(path, body)
        upsert_index_entry(
            self._data_root,
            scope=LOCAL_SCOPE,
            entry={
                "resource_id": resource_id,
                "resource_name": name,
                "resource_kind": body["resource_kind"],
                "scope": "local",
                "source_msn_id": "",
                "path": str(path),
                "version_hash": _as_text(written.get("version_hash")),
                "updated_at": int(written.get("updated_at") or now_ms),
                "status": "ready",
            },
        )
        return {
            "ok": True,
            "schema": "mycite.portal.resources.local_create.v1",
            "resource_id": resource_id,
            "resource_name": name,
            "resource_path": str(path),
            "version_hash": _as_text(written.get("version_hash")),
        }

    def stage(self, *, resource_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._sandbox_engine.stage_resource(resource_id, payload if isinstance(payload, dict) else {})
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.stage.v1"
        return out

    def update(self, *, resource_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._sandbox_engine.save_resource(resource_id, payload if isinstance(payload, dict) else {})
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.save.v1"
        return out

    def compile(self, *, resource_id: str) -> dict[str, Any]:
        result = self._sandbox_engine.compile_isolated_mss_resource(resource_id=resource_id)
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.resource_compile.v1"
        return out

    def publish(self, *, resource_id: str, resource_name: str = "", resource_kind: str = "") -> dict[str, Any]:
        staged = self._sandbox_engine.get_resource(resource_id)
        if bool(staged.get("missing")):
            has_staged, staged_snapshot = self._sandbox_engine.peek_stage_payload(resource_id)
            if has_staged and isinstance(staged_snapshot, dict) and staged_snapshot:
                staged = staged_snapshot
            else:
                return {
                    "ok": False,
                    "schema": "mycite.portal.resources.local_publish.v1",
                    "error": f"sandbox resource not found: {resource_id}",
                }
        payload = _resource_payload_from_sandbox(staged)
        name = _resource_name_from_id(resource_name or resource_id)
        local_resource_id = _resource_id_from_name(name)
        now_ms = int(time.time() * 1000)
        path = resource_file_path(self._data_root, scope=LOCAL_SCOPE, resource_name=name)
        body = {
            "schema": "mycite.portal.resource.local.v1",
            "resource_id": local_resource_id,
            "resource_kind": _as_text(resource_kind or staged.get("resource_kind")) or "resource",
            "scope": "local",
            "source_msn_id": "",
            "updated_at": now_ms,
            "anthology_compatible_payload": payload,
            "draft_metadata": dict(staged.get("draft_state") or {}),
            "compile_metadata": dict(staged.get("compile_metadata") or {}),
            "publish_metadata": {
                "published_from_sandbox_resource_id": _as_text(resource_id),
                "published_unix_ms": now_ms,
            },
        }
        written = write_resource_file(path, body)
        upsert_index_entry(
            self._data_root,
            scope=LOCAL_SCOPE,
            entry={
                "resource_id": local_resource_id,
                "resource_name": name,
                "resource_kind": body["resource_kind"],
                "scope": "local",
                "source_msn_id": "",
                "path": str(path),
                "version_hash": _as_text(written.get("version_hash")),
                "updated_at": int(written.get("updated_at") or now_ms),
                "status": "published",
            },
        )
        return {
            "ok": True,
            "schema": "mycite.portal.resources.local_publish.v1",
            "resource_id": local_resource_id,
            "resource_name": name,
            "resource_path": str(path),
            "version_hash": _as_text(written.get("version_hash")),
        }
