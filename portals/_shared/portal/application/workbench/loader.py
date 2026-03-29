from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _shared.portal.data_engine.resource_registry import INHERITED_SCOPE, LOCAL_SCOPE, load_index, read_resource_file
from _shared.portal.sandbox.engine import SandboxEngine
from _shared.portal.sandbox.resource_workbench import (
    build_resource_workbench_view_model,
    is_samras_backed_resource,
)
from _shared.portal.sandbox.txa_sandbox_workspace import build_samras_workspace_view_model

from .document_contract import build_workbench_document
from .rules import WorkbenchRulesService


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


@dataclass
class DocumentLoaderService:
    data_root: Path
    sandbox_engine: SandboxEngine
    rules_service: WorkbenchRulesService
    instance_id_provider: Any | None = None

    def _instance_id(self) -> str:
        if self.instance_id_provider is None:
            return ""
        try:
            return _text(self.instance_id_provider())
        except Exception:
            return ""

    def sandbox_resource_detail(self, resource_id: str) -> dict[str, Any]:
        payload = self.sandbox_engine.get_resource(resource_id)
        rid = _text(resource_id)
        has_staged, staged_snapshot = self.sandbox_engine.peek_stage_payload(rid)
        out: dict[str, Any] = {
            "ok": not bool(payload.get("missing")),
            "resource": payload,
            "staged_present": has_staged,
            "staged_payload": dict(staged_snapshot) if has_staged else {},
            "schema": "mycite.portal.sandbox.resource.detail.v1",
        }
        datum_u, rule_pol = self.rules_service.understanding_for_resource_body(dict(payload) if isinstance(payload, dict) else {})
        if datum_u is not None:
            out["datum_understanding"] = datum_u
        if rule_pol is not None:
            out["rule_policy_by_id"] = rule_pol
        if not bool(payload.get("missing")):
            resource_body = dict(payload)
            out["workbench"] = build_resource_workbench_view_model(
                resource_body=resource_body,
                staged_present=has_staged,
                staged_payload=dict(staged_snapshot) if has_staged else {},
                datum_understanding=datum_u,
                rule_policy_by_id=rule_pol,
            )
            out["document"] = build_workbench_document(
                document_id=f"workbench:sandbox:{rid}",
                instance_id=self._instance_id(),
                logical_key=rid,
                display_name=rid,
                family_kind="resource",
                family_type=_text(resource_body.get("kind") or resource_body.get("resource_kind") or "resource"),
                scope_kind="sandbox",
                payload=resource_body,
                metadata={
                    "title": rid,
                    "summary": "Sandbox resource detail",
                    "icon": "resource.svg",
                    "warnings": list(datum_u.get("warnings") or []) if isinstance(datum_u, dict) else [],
                    "badges": ["sandbox"],
                    "content_type": "application/json",
                    "payload_loaded": True,
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
                    "inspect_structure": True,
                },
                provenance={
                    "source_adapter": "sandbox_engine",
                    "source_path": "",
                    "source_msn_id": "",
                    "source_contract_id": "",
                    "source_resource_id": rid,
                },
                persistence={
                    "adapter": "file",
                    "relative_path": f"sandbox/resources/{rid}.json",
                    "write_mode": "sandbox_direct",
                    "publish_target": "resources",
                },
                mutability={"mode": "staged", "editable": True, "reason": ""},
                revision={
                    "version": 1,
                    "etag": _text(resource_body.get("version_hash")),
                    "updated_at_unix_ms": int(resource_body.get("updated_at") or 0),
                },
                inheritance={"relation": "none", "source_document_id": None, "refreshable": False, "disconnectable": False},
            )
            if is_samras_backed_resource(resource_body):
                try:
                    out["samras_workspace"] = build_samras_workspace_view_model(
                        resource_body,
                        selected_address_id="",
                        staged_entries=[],
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    out["samras_workspace_error"] = str(exc)
        return out

    def local_resource_document(self, resource_id: str) -> dict[str, Any] | None:
        return self._load_index_document(scope=LOCAL_SCOPE, resource_id=resource_id)

    def inherited_resource_document(self, resource_id: str) -> dict[str, Any] | None:
        return self._load_index_document(scope=INHERITED_SCOPE, resource_id=resource_id)

    def _load_index_document(self, *, scope: str, resource_id: str) -> dict[str, Any] | None:
        index_payload = load_index(self.data_root, scope=scope)
        for entry in list(index_payload.get("resources") or []):
            if not isinstance(entry, dict):
                continue
            if _text(entry.get("resource_id")) != _text(resource_id):
                continue
            path = Path(_text(entry.get("path")))
            payload = read_resource_file(path) if path.is_file() else {}
            return build_workbench_document(
                document_id=f"workbench:{scope}:{resource_id}",
                instance_id=self._instance_id(),
                logical_key=_text(resource_id),
                display_name=_text(entry.get("resource_name") or resource_id),
                family_kind="resource" if scope == LOCAL_SCOPE else "reference",
                family_type=_text(entry.get("resource_kind") or "resource"),
                scope_kind=scope,
                payload=payload,
                metadata={
                    "title": _text(entry.get("resource_name") or resource_id),
                    "summary": "resource document" if scope == LOCAL_SCOPE else "outside-origin reference document",
                    "icon": "resource.svg",
                    "warnings": [],
                    "badges": [scope],
                    "content_type": "application/json",
                    "payload_loaded": bool(payload),
                },
                capabilities={
                    "read": True,
                    "edit": scope == LOCAL_SCOPE,
                    "stage": scope == LOCAL_SCOPE,
                    "save": scope == LOCAL_SCOPE,
                    "compile": scope == LOCAL_SCOPE,
                    "publish": scope == LOCAL_SCOPE,
                    "refresh": scope == INHERITED_SCOPE,
                    "disconnect_source": scope == INHERITED_SCOPE,
                },
                provenance={
                    "source_adapter": "resource_registry" if scope == LOCAL_SCOPE else "inherited_contract_resources",
                    "source_path": _text(entry.get("path")),
                    "source_msn_id": _text(entry.get("source_msn_id")),
                    "source_contract_id": "",
                    "source_resource_id": _text(resource_id),
                },
                persistence={
                    "adapter": "file",
                    "relative_path": _text(entry.get("path")),
                    "write_mode": "stage_then_promote" if scope == LOCAL_SCOPE else "read_only_cache",
                    "publish_target": _text(entry.get("path")),
                },
                mutability={
                    "mode": "mutable" if scope == LOCAL_SCOPE else "readonly",
                    "editable": scope == LOCAL_SCOPE,
                    "reason": "" if scope == LOCAL_SCOPE else "outside-origin reference",
                },
                revision={
                    "version": 1,
                    "etag": _text(entry.get("version_hash")),
                    "updated_at_unix_ms": int(entry.get("updated_at") or 0),
                },
                inheritance={
                    "relation": "none" if scope == LOCAL_SCOPE else "cached_from_source",
                    "source_document_id": _text(entry.get("source_msn_id")) or None,
                    "refreshable": scope == INHERITED_SCOPE,
                    "disconnectable": scope == INHERITED_SCOPE,
                },
            )
        return None
