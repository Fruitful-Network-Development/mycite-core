from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from _shared.portal.data_engine.resource_registry import (
    INHERITED_SCOPE,
    LOCAL_SCOPE,
    ensure_layout,
    inherited_resources_dir,
    load_index,
    local_resources_dir,
)
from _shared.portal.sandbox.engine import SandboxEngine
from _shared.portal.sandbox.resource_workbench import build_system_resource_workbench_view_model

from .document_contract import DOCUMENT_SCHEMA, build_workbench_document


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


@dataclass
class DocumentCatalogService:
    data_root: Path
    local_inventory_provider: Callable[[], dict[str, Any]]
    sandbox_engine: SandboxEngine
    instance_id_provider: Callable[[], str] | None = None

    def _instance_id(self) -> str:
        if self.instance_id_provider is None:
            return ""
        try:
            return _text(self.instance_id_provider())
        except Exception:
            return ""

    def sandbox_inventory_payload(self) -> dict[str, Any]:
        resources = self.sandbox_engine.list_resources()
        documents = [self._sandbox_document(item) for item in resources if isinstance(item, dict)]
        return {
            "ok": True,
            "resources": resources,
            "documents_schema": DOCUMENT_SCHEMA,
            "documents": documents,
            "schema": "mycite.portal.sandbox.resources.v1",
        }

    def local_inventory_payload(self) -> dict[str, Any]:
        payload = dict(self.local_inventory_provider() or {})
        resources = [dict(item) for item in list(payload.get("resources") or []) if isinstance(item, dict)]
        payload["documents_schema"] = DOCUMENT_SCHEMA
        payload["documents"] = [self._local_document(item) for item in resources]
        return payload

    def inherited_inventory_payload(
        self,
        *,
        grouped_by_source_fn: Callable[[dict[str, Any]], dict[str, list[dict[str, Any]]]],
    ) -> dict[str, Any]:
        root = Path(self.data_root)
        ensure_layout(root)
        index_payload = load_index(root, scope=INHERITED_SCOPE)
        resources = [dict(item) for item in list(index_payload.get("resources") or []) if isinstance(item, dict)]
        return {
            "ok": True,
            "schema": "mycite.portal.references.inventory.v2",
            "resources_root": str(inherited_resources_dir(root)),
            "resources": resources,
            "grouped_by_source": grouped_by_source_fn(index_payload),
            "documents_schema": DOCUMENT_SCHEMA,
            "documents": [self._inherited_document(item) for item in resources],
        }

    def system_resource_workbench_payload(self) -> dict[str, Any]:
        vm = build_system_resource_workbench_view_model(data_root=self.data_root)
        documents = [self._system_file_document(item) for item in list(vm.get("files") or []) if isinstance(item, dict)]
        out = dict(vm)
        out["documents_schema"] = DOCUMENT_SCHEMA
        out["documents"] = documents
        return out

    def _local_document(self, entry: dict[str, Any]) -> dict[str, Any]:
        resource_id = _text(entry.get("resource_id"))
        resource_name = _text(entry.get("resource_name"))
        resource_kind = _text(entry.get("resource_kind") or "resource")
        return build_workbench_document(
            document_id=f"workbench:local:{resource_id or resource_name}",
            instance_id=self._instance_id(),
            logical_key=resource_id or resource_name,
            display_name=resource_name or resource_id,
            family_kind="resource",
            family_type=resource_kind or "resource",
            scope_kind=LOCAL_SCOPE,
            metadata={
                "title": resource_name or resource_id,
                "summary": "Canonical resource inventory item",
                "icon": "resource.svg",
                "warnings": [],
                "badges": [],
                "content_type": "application/json",
                "payload_loaded": False,
            },
            capabilities={
                "read": True,
                "edit": True,
                "stage": True,
                "save": True,
                "compile": True,
                "publish": True,
                "refresh": False,
                "disconnect_source": False,
            },
            provenance={
                "source_adapter": "resource_registry",
                "source_path": _text(entry.get("path")),
                "source_msn_id": "",
                "source_contract_id": "",
                "source_resource_id": resource_id,
            },
            persistence={
                "adapter": "file",
                "relative_path": _relative_to_root(self.data_root, _text(entry.get("path"))),
                "write_mode": "stage_then_promote",
                "publish_target": str(local_resources_dir(self.data_root)),
            },
            mutability={"mode": "mutable", "editable": True, "reason": ""},
            revision={
                "version": 1,
                "etag": _text(entry.get("version_hash")),
                "updated_at_unix_ms": int(entry.get("updated_at") or 0),
            },
            inheritance={"relation": "none", "source_document_id": None, "refreshable": False, "disconnectable": False},
        )

    def _inherited_document(self, entry: dict[str, Any]) -> dict[str, Any]:
        resource_id = _text(entry.get("resource_id"))
        resource_name = _text(entry.get("resource_name"))
        source_msn_id = _text(entry.get("source_msn_id"))
        resource_kind = _text(entry.get("resource_kind") or "resource")
        return build_workbench_document(
            document_id=f"workbench:reference:{resource_id or resource_name}",
            instance_id=self._instance_id(),
            logical_key=resource_id or resource_name,
            display_name=resource_name or resource_id,
            family_kind="reference",
            family_type=resource_kind or "resource",
            scope_kind=INHERITED_SCOPE,
            metadata={
                "title": resource_name or resource_id,
                "summary": f"Outside-origin reference from {source_msn_id or 'unknown'}",
                "icon": "resource.svg",
                "warnings": [],
                "badges": ["reference"],
                "content_type": "application/json",
                "payload_loaded": False,
            },
            capabilities={
                "read": True,
                "edit": False,
                "stage": False,
                "save": False,
                "compile": False,
                "publish": False,
                "refresh": True,
                "disconnect_source": True,
            },
            provenance={
                "source_adapter": "inherited_contract_resources",
                "source_path": _text(entry.get("path")),
                "source_msn_id": source_msn_id,
                "source_contract_id": "",
                "source_resource_id": resource_id,
            },
            persistence={
                "adapter": "file",
                "relative_path": _relative_to_root(self.data_root, _text(entry.get("path"))),
                "write_mode": "read_only_cache",
                "publish_target": str(inherited_resources_dir(self.data_root)),
            },
            mutability={"mode": "readonly", "editable": False, "reason": "outside-origin reference"},
            revision={
                "version": 1,
                "etag": _text(entry.get("version_hash")),
                "updated_at_unix_ms": int(entry.get("updated_at") or 0),
            },
            inheritance={
                "relation": "cached_from_source",
                "source_document_id": source_msn_id or None,
                "refreshable": True,
                "disconnectable": True,
            },
        )

    def _sandbox_document(self, entry: dict[str, Any]) -> dict[str, Any]:
        resource_id = _text(entry.get("resource_id"))
        kind = _text(entry.get("kind") or "resource")
        return build_workbench_document(
            document_id=f"workbench:sandbox:{resource_id}",
            instance_id=self._instance_id(),
            logical_key=resource_id,
            display_name=resource_id,
            family_kind="resource",
            family_type=kind or "resource",
            scope_kind="sandbox",
            metadata={
                "title": resource_id,
                "summary": "Sandbox resource",
                "icon": "resource.svg",
                "warnings": [],
                "badges": ["sandbox"],
                "content_type": "application/json",
                "payload_loaded": False,
            },
            capabilities={
                "read": True,
                "edit": True,
                "stage": True,
                "save": True,
                "compile": True,
                "publish": True,
                "refresh": False,
                "disconnect_source": False,
            },
            provenance={
                "source_adapter": "sandbox_engine",
                "source_path": _relative_to_root(self.data_root, _text(entry.get("path"))),
                "source_msn_id": "",
                "source_contract_id": "",
                "source_resource_id": resource_id,
            },
            persistence={
                "adapter": "file",
                "relative_path": _relative_to_root(self.data_root, _text(entry.get("path"))),
                "write_mode": "sandbox_direct",
                "publish_target": str(self.data_root / "resources"),
            },
            mutability={"mode": "staged", "editable": True, "reason": ""},
            inheritance={"relation": "none", "source_document_id": None, "refreshable": False, "disconnectable": False},
        )

    def _system_file_document(self, entry: dict[str, Any]) -> dict[str, Any]:
        file_key = _text(entry.get("file_key"))
        filename = _text(entry.get("filename"))
        if file_key == "anthology":
            family_kind = "anthology"
            family_type = "registry"
            scope_kind = "anthology"
            capabilities = {
                "read": True,
                "edit": True,
                "stage": False,
                "save": True,
                "compile": False,
                "publish": False,
                "refresh": False,
                "disconnect_source": False,
            }
        else:
            family_kind = "resource"
            family_type = "samras"
            scope_kind = LOCAL_SCOPE
            capabilities = {
                "read": True,
                "edit": True,
                "stage": True,
                "save": True,
                "compile": True,
                "publish": True,
                "refresh": False,
                "disconnect_source": False,
            }
        return build_workbench_document(
            document_id=f"workbench:system:{file_key}",
            instance_id=self._instance_id(),
            logical_key=file_key,
            display_name=filename or file_key,
            family_kind=family_kind,
            family_type=family_type,
            family_subtype=file_key,
            scope_kind=scope_kind,
            payload={
                "file_key": file_key,
                "filename": filename,
                "row_count": int(entry.get("row_count") or 0),
            },
            metadata={
                "title": filename or file_key,
                "summary": "System workbench canonical file",
                "icon": "resource.svg",
                "warnings": list(entry.get("errors") or []),
                "badges": ["system"],
                "content_type": "application/json",
                "payload_loaded": True,
            },
            capabilities=capabilities,
            provenance={
                "source_adapter": "system_resource_workbench",
                "source_path": _relative_to_root(self.data_root, _text(entry.get("path"))),
                "source_msn_id": "",
                "source_contract_id": "",
                "source_resource_id": file_key,
            },
            persistence={
                "adapter": "file",
                "relative_path": _relative_to_root(self.data_root, _text(entry.get("path"))),
                "write_mode": "direct" if file_key == "anthology" else "stage_then_promote",
                "publish_target": _text(entry.get("path")),
            },
            mutability={"mode": "mutable", "editable": True, "reason": ""},
            revision={"version": 1, "etag": "", "updated_at_unix_ms": 0},
            inheritance={"relation": "none", "source_document_id": None, "refreshable": False, "disconnectable": False},
        )


def _relative_to_root(data_root: Path, raw_path: str) -> str:
    token = _text(raw_path)
    if not token:
        return ""
    path = Path(token)
    try:
        return str(path.relative_to(data_root))
    except Exception:
        return token
