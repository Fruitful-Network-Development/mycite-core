from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

from flask import abort, jsonify, redirect, request
from _shared.portal.application.agro import build_agro_config_context, update_agro_config_bindings
from _shared.portal.application.shell.runtime import build_selected_context_payload
from _shared.portal.application.workbench.actions import WorkbenchActionService
from _shared.portal.application.workbench.catalog import DocumentCatalogService
from _shared.portal.application.workbench.loader import DocumentLoaderService
from _shared.portal.application.workbench.publish import WorkbenchPublishService
from _shared.portal.application.workbench.rules import WorkbenchRulesService
from _shared.portal.application.workbench.sandbox_sessions import WorkbenchSandboxSessionService
from _shared.portal.data_engine.aitas_context import (
    inspect_archetype_context,
    inspect_archetype_trace,
    list_archetype_registry_payload,
    list_derived_archetype_bindings,
)
from _shared.portal.data_engine.anthology_context import build_canonical_anthology_context
from _shared.portal.data_engine.anthology_overlay import strip_base_duplicates_from_overlay
from _shared.portal.data_engine.inherited_contract_resources import (
    InheritedSubscriptionService,
    discover_contract_subscription_status,
)
from _shared.portal.data_engine.resource_registry import (
    INHERITED_SCOPE,
    load_index,
)
from _shared.portal.data_engine.anthology_registry import load_base_registry
from _shared.portal.data_engine.field_contracts import default_profile_field_contracts
from _shared.portal.data_engine.inherited_txa_adapter import select_inherited_binding_for_field
from _shared.portal.data_engine.profile_config_refs import get_path
from _shared.portal.data_engine.rules import (
    build_append_row_dict,
    build_updated_row_dict,
    compute_next_append_datum_id,
    derive_rule_policy,
    evaluate_probe_write,
    infer_reference_filter_rule_key,
    reference_filter_options,
    resolve_lens_for_datum,
    understand_datums,
)
from _shared.portal.data_engine.rules.base import parse_datum_id
from _shared.portal.data_engine.write_pipeline import apply_write_preview, preview_write_intent
from _shared.portal.sandbox import LocalResourceLifecycleService, SandboxEngine, migrate_fnd_samras_rows_to_sandbox
from _shared.portal.sandbox.promotion_hooks import build_tool_sandbox_promotion_hooks
from _shared.portal.sandbox.session_registry import get_tool_sandbox_session_manager
from _shared.portal.sandbox.tool_sandbox_session import ToolSandboxRuntimeDeps, ToolSandboxSessionManager
from _shared.portal.sandbox.samras_workspace_promotion import promote_staged_samras_title_entries
from _shared.portal.samras import InvalidSamrasStructure, build_workspace_view_model, mutate_compact_payload
from _shared.portal.sandbox.resource_workbench import (
    _extract_rows_payload_from_json,
    _read_json_object,
    _write_json_object_one_entry_per_line,
    system_workbench_stage_path,
)
from _shared.portal.sandbox.txa_sandbox_workspace import build_samras_workspace_view_model, build_txa_sandbox_view_model
from _shared.portal.sandbox.workspace_contract import AGRO_ERP_SANDBOX_DECLARATION


def register_data_routes(
    app,
    *,
    workspace,
    aliases_provider: Callable[[], list[dict]] | None = None,
    options_private_fn: Callable[[str], dict[str, Any]] | None = None,
    msn_id_provider: Callable[[], str] | None = None,
    external_resource_resolver: Any | None = None,
    anthology_payload_provider: Callable[[], dict[str, Any]] | None = None,
    active_config_provider: Callable[[], dict[str, Any]] | None = None,
    active_config_saver: Callable[[dict[str, Any]], bool] | None = None,
    private_dir: Path | None = None,
    tool_tabs: list[dict[str, Any]] | None = None,
    portal_instance_context: Any | None = None,
    include_home_redirect: bool = True,
    include_legacy_shims: bool = True,
) -> None:
    def _known_table_ids() -> set[str]:
        return {
            str(item.get("table_id") or "").strip()
            for item in workspace.list_tables()
            if str(item.get("table_id") or "").strip()
        }

    def _msn_id() -> str:
        if msn_id_provider is None:
            return ""
        try:
            return str(msn_id_provider() or "").strip()
        except Exception:
            return ""

    def _json_body() -> dict[str, Any]:
        if not request.is_json:
            abort(415, description="Expected application/json body")
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            return {"directive": payload}
        abort(400, description="Expected JSON object body")

    def _state_snapshot() -> dict[str, Any]:
        return workspace.get_state_snapshot()

    def _state_payload(result: dict[str, Any]) -> dict[str, Any]:
        snapshot = _state_snapshot()
        return {
            "ok": bool(result.get("ok", True)),
            "result": result,
            "state": snapshot.get("state", {}),
            "left_pane_vm": snapshot.get("left_pane_vm", {}),
            "right_pane_vm": snapshot.get("right_pane_vm", {}),
            "staged_edits": snapshot.get("staged_edits", []),
            "staged_presentation_edits": snapshot.get("staged_presentation_edits", {"datum_icons": {}}),
            "datum_icons_map": snapshot.get("datum_icons_map", {}),
            "daemon_ports": snapshot.get("daemon_ports", []),
            "model_meta": snapshot.get("model_meta", {}),
            "errors": list(result.get("errors") or []),
            "warnings": list(result.get("warnings") or []),
        }

    def _load_active_config() -> dict[str, Any]:
        if active_config_provider is None:
            return {}
        try:
            payload = active_config_provider() or {}
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _save_active_config(payload: dict[str, Any]) -> bool:
        if active_config_saver is None:
            return False
        try:
            return bool(active_config_saver(payload if isinstance(payload, dict) else {}))
        except Exception:
            return False

    def _tool_tabs() -> list[dict[str, Any]]:
        return [dict(item) for item in list(tool_tabs or []) if isinstance(item, dict)]

    def _portal_instance_context_payload() -> dict[str, Any]:
        if portal_instance_context is None:
            return {}
        if is_dataclass(portal_instance_context):
            payload = asdict(portal_instance_context)
            return {str(key): str(value) for key, value in payload.items()}
        if isinstance(portal_instance_context, dict):
            return {str(key): str(value) for key, value in portal_instance_context.items()}
        return {}

    def _local_anthology_payload() -> dict[str, Any]:
        if anthology_payload_provider is None:
            return {}
        try:
            payload = anthology_payload_provider() or {}
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _external_plan_for_intent(payload: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
        if external_resource_resolver is None or anthology_payload_provider is None:
            return True, {"ok": True, "ordered_writes": []}, ""
        try:
            plan = external_resource_resolver.plan_materialization(
                source_msn_id=str(payload.get("source_msn_id") or "").strip(),
                resource_id=str(payload.get("resource_id") or "").strip(),
                target_ref=str(payload.get("target_ref") or "").strip(),
                required_refs=[str(item or "").strip() for item in list(payload.get("required_refs") or [])],
                anthology_payload=_anthology_payload_for_mss_compile(),
                allow_auto_create=bool(payload.get("allow_auto_create", False)),
            )
            out = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
            return bool(out.get("ok")), out, str(out.get("error") or "")
        except Exception as exc:
            return False, {}, str(exc)

    def _sandbox_engine() -> SandboxEngine:
        storage = getattr(workspace, "storage", None)
        data_root = getattr(storage, "data_dir", None)
        if data_root is None:
            data_root = "."
        return SandboxEngine(data_root=Path(str(data_root)))

    def _local_resource_service() -> LocalResourceLifecycleService:
        return LocalResourceLifecycleService(data_root=_data_root(), sandbox_engine=_sandbox_engine())

    def _data_root() -> Path:
        storage = getattr(workspace, "storage", None)
        data_root = getattr(storage, "data_dir", None)
        return Path(str(data_root or "."))

    def _private_dir() -> Path:
        if isinstance(private_dir, Path):
            return private_dir
        return _data_root().parent / "private"

    def _inherited_subscription_service() -> InheritedSubscriptionService:
        if external_resource_resolver is None:
            raise RuntimeError("external resource resolver is unavailable")
        return InheritedSubscriptionService(
            data_root=_data_root(),
            private_dir=_private_dir(),
            resolver=external_resource_resolver,
            owner_msn_id=_msn_id(),
        )

    def _overlay_anthology_path() -> Path:
        return _data_root() / "anthology.json"

    def _canonical_anthology_context():
        overlay_path = _overlay_anthology_path()
        if overlay_path.exists():
            return build_canonical_anthology_context(overlay_path=overlay_path)
        return build_canonical_anthology_context(overlay_payload=_local_anthology_payload())

    def _canonical_rows_payload() -> dict[str, Any]:
        return _canonical_anthology_context().rows_payload

    def _anthology_payload_for_mss_compile() -> dict[str, Any]:
        return dict(_canonical_anthology_context().compact_payload)

    def _rule_rows_payload_from_sandbox_resource(resource_id: str) -> dict[str, Any]:
        resource = _sandbox_engine().get_resource(resource_id)
        if bool(resource.get("missing")):
            return {"rows": {}}
        anthology_payload = (
            resource.get("anthology_compatible_payload")
            if isinstance(resource.get("anthology_compatible_payload"), dict)
            else {}
        )
        if anthology_payload:
            return anthology_payload
        canonical_state = resource.get("canonical_state") if isinstance(resource.get("canonical_state"), dict) else {}
        compact_payload = canonical_state.get("compact_payload") if isinstance(canonical_state.get("compact_payload"), dict) else {}
        if compact_payload:
            return compact_payload
        return {"rows": {}}

    def _canonical_row_entry(row_token: str) -> tuple[str, dict[str, Any]] | None:
        token = str(row_token or "").strip()
        if not token:
            return None
        ctx = _canonical_anthology_context()
        if token in ctx.rows_by_id:
            return token, dict(ctx.rows_by_id[token])
        for key, row in ctx.rows_by_id.items():
            rid = str(row.get("row_id") or "").strip()
            ident = str(row.get("identifier") or "").strip()
            if token in {rid, ident}:
                return str(key), dict(row)
        return None

    def _group_inherited_index(index_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in list(index_payload.get("resources") or []):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source_msn_id") or "").strip() or "unknown"
            grouped.setdefault(source, []).append(dict(item))
        for source in grouped:
            grouped[source].sort(
                key=lambda row: (
                    str(row.get("resource_name") or ""),
                    str(row.get("resource_id") or ""),
                )
            )
        return grouped

    def _system_documents() -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for payload in (
            _document_catalog().local_inventory_payload(),
            _document_catalog().inherited_inventory_payload(grouped_by_source_fn=_group_inherited_index),
            _document_catalog().sandbox_inventory_payload(),
            _document_catalog().system_resource_workbench_payload(),
        ):
            for item in list(payload.get("documents") or []):
                if isinstance(item, dict):
                    documents.append(dict(item))
        return documents

    def _document_for_request(body: dict[str, Any]) -> dict[str, Any] | None:
        candidate = body.get("document")
        if isinstance(candidate, dict) and candidate:
            return dict(candidate)
        document_id = str(body.get("document_id") or "").strip()
        if document_id:
            for item in _system_documents():
                identity = item.get("identity") if isinstance(item.get("identity"), dict) else {}
                if str(identity.get("document_id") or "").strip() == document_id:
                    return item
        scope = str(body.get("scope") or "").strip().lower()
        resource_id = str(body.get("resource_id") or body.get("logical_key") or "").strip()
        if scope == LOCAL_SCOPE and resource_id:
            return _document_loader().local_resource_document(resource_id)
        if scope == INHERITED_SCOPE and resource_id:
            return _document_loader().inherited_resource_document(resource_id)
        if scope == "sandbox" and resource_id:
            detail = _document_loader().sandbox_resource_detail(resource_id)
            document = detail.get("document")
            if isinstance(document, dict):
                return document
        return None

    def _agro_config_context(active_config: dict[str, Any] | None = None) -> dict[str, Any]:
        local_payload = _document_catalog().local_inventory_payload()
        inherited_payload = _document_catalog().inherited_inventory_payload(grouped_by_source_fn=_group_inherited_index)
        sandbox_payload = _document_catalog().sandbox_inventory_payload()
        return build_agro_config_context(
            active_config=active_config if isinstance(active_config, dict) else _load_active_config(),
            tool_tabs=_tool_tabs(),
            local_documents=[dict(item) for item in list(local_payload.get("documents") or []) if isinstance(item, dict)],
            inherited_documents=[dict(item) for item in list(inherited_payload.get("documents") or []) if isinstance(item, dict)],
            sandbox_documents=[dict(item) for item in list(sandbox_payload.get("documents") or []) if isinstance(item, dict)],
            portal_instance_context=portal_instance_context,
            portal_instance_id=str(_portal_instance_context_payload().get("portal_instance_id") or ""),
            msn_id=_msn_id(),
        )

    if include_home_redirect:
        @app.get("/portal/data")
        def portal_data_home_redirect():
            return redirect("/portal/tools/data_tool/home", code=302)

    @app.get("/portal/api/data/state")
    def portal_data_state():
        snapshot = _state_snapshot()
        snapshot["ok"] = True
        msn_id = _msn_id()
        if options_private_fn is not None and msn_id:
            snapshot["options_private"] = options_private_fn(msn_id)
        if aliases_provider is not None:
            try:
                snapshot["aliases"] = aliases_provider()
            except Exception:
                snapshot["aliases"] = []
        return jsonify(snapshot)

    @app.get("/portal/api/data/icons/list")
    def portal_data_icons_list():
        meta = workspace.model_meta() if hasattr(workspace, "model_meta") else {}
        return jsonify(
            {
                "ok": True,
                "icon_relpaths": workspace.list_available_icons(),
                "icon_relpath_mode": str(meta.get("icon_relpath_mode") or "path"),
            }
        )

    @app.get("/portal/api/data/model")
    def portal_data_model():
        meta = workspace.model_meta() if hasattr(workspace, "model_meta") else {}
        return jsonify({"ok": True, "model_meta": meta})

    @app.post("/portal/api/data/system/selection_context")
    def portal_data_system_selection_context():
        body = _json_body()
        document = _document_for_request(body)
        if not isinstance(document, dict) or not document:
            return (
                jsonify(
                    {
                        "ok": False,
                        "schema": "mycite.shell.selected_context.v1",
                        "error": "document or document_id is required",
                    }
                ),
                400,
            )
        payload = build_selected_context_payload(
            document=document,
            selected_row=body.get("selected_row") if isinstance(body.get("selected_row"), dict) else None,
            shell_verb=body.get("current_verb") or body.get("shell_verb"),
            tool_tabs=_tool_tabs(),
            portal_instance_context=portal_instance_context,
        )
        return jsonify(payload)

    @app.route("/portal/api/data/system/config_context/agro_erp", methods=["GET", "POST"])
    def portal_data_system_agro_config_context():
        active_config = _load_active_config()
        saved = False
        if request.method == "POST":
            body = _json_body()
            updated = update_agro_config_bindings(
                active_config,
                resource_roles=body.get("resource_roles") if isinstance(body.get("resource_roles"), dict) else None,
            )
            saved = _save_active_config(updated)
            active_config = updated if saved else active_config
        payload = _agro_config_context(active_config)
        payload["saved"] = saved
        return jsonify(payload), (200 if request.method == "GET" or saved else 500)

    @app.post("/portal/api/data/anthology/overlay/migration")
    def portal_data_anthology_overlay_migration():
        body = _json_body()
        apply_changes = bool(body.get("apply"))
        overlay_path = _overlay_anthology_path()
        try:
            overlay_payload = json.loads(overlay_path.read_text(encoding="utf-8")) if overlay_path.exists() else {}
        except Exception:
            overlay_payload = {}
        if not isinstance(overlay_payload, dict):
            overlay_payload = {}
        base_registry = load_base_registry(strict=False)
        report = strip_base_duplicates_from_overlay(
            overlay_payload=overlay_payload,
            base_registry=base_registry,
        )
        if apply_changes:
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            overlay_path.write_text(json.dumps(report.output_payload, indent=2) + "\n", encoding="utf-8")
        return jsonify(
            {
                "ok": True,
                "apply": apply_changes,
                "overlay_path": str(overlay_path),
                "base_registry_path": str(base_registry.path),
                "removed_duplicate_ids": list(report.removed_duplicate_ids),
                "kept_ids": list(report.kept_ids),
                "warnings": list(report.warnings),
                "counts": {
                    "removed_duplicate_count": len(report.removed_duplicate_ids),
                    "kept_count": len(report.kept_ids),
                },
            }
        )

    @app.get("/portal/api/data/sandbox/resources")
    def portal_data_sandbox_resources():
        return jsonify(_document_catalog().sandbox_inventory_payload())

    def _tool_sandbox_manager() -> ToolSandboxSessionManager:
        return get_tool_sandbox_session_manager(app)

    def _tool_sandbox_runtime_deps() -> ToolSandboxRuntimeDeps:
        return ToolSandboxRuntimeDeps(
            data_root=_data_root(),
            sandbox_engine=_sandbox_engine(),
            local_resource_service=_local_resource_service(),
            get_active_config=_load_active_config,
            get_canonical_rows_payload=_canonical_rows_payload,
            get_path=get_path,
        )

    def _declaration_for_tool_session(tool_key: str, body_decl: Any) -> dict[str, Any]:
        if isinstance(body_decl, dict) and body_decl:
            return dict(body_decl)
        tk = str(tool_key or "").strip().lower()
        if tk == "agro_erp":
            return dict(AGRO_ERP_SANDBOX_DECLARATION)
        abort(400, description="declaration is required for this tool_key")

    def _tool_sandbox_promotion_hooks():
        return build_tool_sandbox_promotion_hooks(
            workspace=workspace,
            load_config_fn=_load_active_config,
            save_config_fn=_save_active_config,
        )

    def _rules_service() -> WorkbenchRulesService:
        return WorkbenchRulesService()

    def _document_catalog() -> DocumentCatalogService:
        return DocumentCatalogService(
            data_root=_data_root(),
            local_inventory_provider=_local_resource_service().list_local_inventory,
            sandbox_engine=_sandbox_engine(),
            instance_id_provider=_msn_id,
        )

    def _document_loader() -> DocumentLoaderService:
        return DocumentLoaderService(
            data_root=_data_root(),
            sandbox_engine=_sandbox_engine(),
            rules_service=_rules_service(),
            instance_id_provider=_msn_id,
        )

    def _action_service() -> WorkbenchActionService:
        return WorkbenchActionService(
            data_root=_data_root(),
            local_resource_service=_local_resource_service(),
            inherited_subscription_service_factory=_inherited_subscription_service if external_resource_resolver is not None else None,
        )

    def _publish_service() -> WorkbenchPublishService:
        return WorkbenchPublishService(local_resource_service=_local_resource_service())

    def _system_workbench_payload() -> dict[str, Any]:
        return _document_catalog().system_resource_workbench_payload()

    def _system_file_meta(file_key: str) -> dict[str, Any]:
        token = str(file_key or "").strip().lower()
        payload = _system_workbench_payload()
        for item in list(payload.get("files") or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("file_key") or "").strip().lower() == token:
                return dict(item)
        abort(404, description=f"unknown system file_key: {file_key}")

    def _looks_like_system_row_key(value: object) -> bool:
        layer, value_group, iteration = parse_datum_id(value)
        return layer is not None and value_group is not None and iteration is not None

    def _system_payload_without_rows(payload: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in dict(payload or {}).items():
            token = str(key or "").strip()
            if token == "rows" or _looks_like_system_row_key(token):
                continue
            out[token] = value
        return out

    def _system_file_storage(file_key: str) -> tuple[dict[str, Any], Path, Path]:
        meta = _system_file_meta(file_key)
        canonical_path = Path(
            str(meta.get("canonical_path") or meta.get("path") or (_data_root() / (str(meta.get("filename") or "")).strip()))
        )
        stage_path = system_workbench_stage_path(data_root=_data_root(), filename=str(meta.get("filename") or canonical_path.name))
        return meta, canonical_path, stage_path

    def _load_system_file_payload(file_key: str, *, prefer_staged: bool = True) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
        meta, canonical_path, stage_path = _system_file_storage(file_key)
        canonical_payload = _read_json_object(canonical_path) if canonical_path.exists() else {}
        if prefer_staged and str(file_key or "").strip().lower() != "anthology" and stage_path.is_file():
            active_payload = _read_json_object(stage_path)
        else:
            active_payload = canonical_payload
        if not isinstance(active_payload, dict):
            active_payload = {}
        if not isinstance(canonical_payload, dict):
            canonical_payload = {}
        return meta, active_payload, canonical_path, stage_path

    def _rows_payload_mapping(payload: dict[str, Any]) -> dict[str, Any]:
        rows_payload = _extract_rows_payload_from_json(payload if isinstance(payload, dict) else {})
        rows_obj = rows_payload.get("rows")
        return dict(rows_obj) if isinstance(rows_obj, dict) else {}

    def _persist_system_rows(file_key: str, base_payload: dict[str, Any], rows_map: dict[str, Any]) -> dict[str, Any]:
        meta, canonical_path, stage_path = _system_file_storage(file_key)
        next_payload = _system_payload_without_rows(base_payload)
        next_payload["rows"] = dict(rows_map)
        target_path = canonical_path if str(file_key or "").strip().lower() == "anthology" else stage_path
        _write_json_object_one_entry_per_line(target_path, next_payload)
        return {
            "file": meta,
            "target_path": str(target_path),
            "write_mode": "direct" if str(file_key or "").strip().lower() == "anthology" else "stage_then_promote",
            "staged_present": bool(str(file_key or "").strip().lower() != "anthology"),
        }

    def _persist_system_payload(file_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        meta, canonical_path, stage_path = _system_file_storage(file_key)
        target_path = canonical_path if str(file_key or "").strip().lower() == "anthology" else stage_path
        _write_json_object_one_entry_per_line(target_path, payload if isinstance(payload, dict) else {})
        return {
            "file": meta,
            "target_path": str(target_path),
            "write_mode": "direct" if str(file_key or "").strip().lower() == "anthology" else "stage_then_promote",
            "staged_present": bool(str(file_key or "").strip().lower() != "anthology"),
        }

    def _sandbox_session_service() -> WorkbenchSandboxSessionService:
        return WorkbenchSandboxSessionService(
            manager_factory=_tool_sandbox_manager,
            runtime_deps_factory=_tool_sandbox_runtime_deps,
            declaration_resolver=_declaration_for_tool_session,
            promotion_hooks_factory=_tool_sandbox_promotion_hooks,
        )

    @app.post("/portal/api/data/sandbox/tool_session/open")
    def portal_data_sandbox_tool_session_open():
        body = _json_body()
        out, status = _sandbox_session_service().open(body)
        return jsonify(out), status

    @app.get("/portal/api/data/sandbox/tool_session/<session_id>")
    def portal_data_sandbox_tool_session_get(session_id: str):
        out, status = _sandbox_session_service().get(session_id)
        return jsonify(out), status

    @app.post("/portal/api/data/sandbox/tool_session/<session_id>/stage")
    def portal_data_sandbox_tool_session_stage(session_id: str):
        body = _json_body()
        out, status = _sandbox_session_service().stage(session_id, body)
        return jsonify(out), status

    @app.post("/portal/api/data/sandbox/tool_session/<session_id>/promote")
    def portal_data_sandbox_tool_session_promote(session_id: str):
        body = _json_body()
        out, status = _sandbox_session_service().promote(session_id, body)
        return jsonify(out), status

    @app.delete("/portal/api/data/sandbox/tool_session/<session_id>")
    def portal_data_sandbox_tool_session_close(session_id: str):
        out, status = _sandbox_session_service().close(session_id)
        return jsonify(out), status

    @app.post("/portal/api/data/sandbox/tool_session/<session_id>/refresh")
    def portal_data_sandbox_tool_session_refresh(session_id: str):
        out, status = _sandbox_session_service().refresh(session_id)
        return jsonify(out), status

    @app.get("/portal/api/data/sandbox/tool_session/<session_id>/understanding")
    def portal_data_sandbox_tool_session_understanding(session_id: str):
        out, status = _sandbox_session_service().understanding(session_id)
        return jsonify(out), status

    @app.get("/portal/api/data/sandbox/samras_workspace")
    def portal_data_sandbox_samras_workspace():
        """
        Generic SAMRAS structural / title-table workspace view for TXA, MSN, and future
        SAMRAS-backed sandbox resources. Optional ``sandbox_session_id`` overlays
        ``working_resources`` when the resource id is present in the session.
        """
        resource_id = str(request.args.get("resource_id") or "").strip()
        if not resource_id:
            abort(400, description="resource_id is required")
        selected_address = str(request.args.get("selected_address") or "").strip()
        session_id = str(request.args.get("sandbox_session_id") or "").strip()
        staged_entries = []
        raw_staged = request.args.get("staged_entries_json", "").strip()
        if raw_staged:
            try:
                parsed = json.loads(raw_staged)
                if isinstance(parsed, list):
                    staged_entries = [item for item in parsed if isinstance(item, dict)]
            except Exception:
                abort(400, description="staged_entries_json must be JSON array of objects")

        engine = _sandbox_engine()
        snap = engine.get_resource(resource_id)
        if bool(snap.get("missing")):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"resource not found: {resource_id}",
                        "schema": "mycite.portal.sandbox.samras_workspace.v1",
                    }
                ),
                404,
            )
        body = snap.get("resource") if isinstance(snap.get("resource"), dict) else {}
        if session_id:
            sess = _tool_sandbox_manager().get(session_id)
            if sess is not None:
                overlay = sess.working_resources.get(resource_id) or sess.loaded_resources.get(resource_id)
                if isinstance(overlay, dict):
                    body = overlay
        vm = build_samras_workspace_view_model(
            body,
            selected_address_id=selected_address,
            staged_entries=staged_entries,
        )
        return jsonify({"ok": True, "schema": "mycite.portal.sandbox.samras_workspace.v1", "view_model": vm})

    @app.post("/portal/api/data/sandbox/samras_workspace/view_model")
    def portal_data_sandbox_samras_workspace_view_model_post():
        """Generic SAMRAS workspace view-model (TXA, MSN, other SAMRAS-backed resources)."""
        body = _json_body()
        rid = str(body.get("resource_id") or "").strip()
        if not rid:
            abort(400, description="resource_id is required")
        payload = _sandbox_engine().get_resource(rid)
        if bool(payload.get("missing")):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"resource not found: {rid}",
                        "schema": "mycite.portal.sandbox.samras_workspace.view_model.v1",
                    }
                ),
                404,
            )
        selected = str(body.get("selected_address_id") or "").strip()
        staged = body.get("staged_entries") if isinstance(body.get("staged_entries"), list) else []
        vm = build_samras_workspace_view_model(payload, selected_address_id=selected, staged_entries=staged)
        return jsonify({"ok": True, **vm})

    @app.post("/portal/api/data/sandbox/resources/<path:resource_id>/promote_staged_samras_titles")
    def portal_data_sandbox_promote_staged_samras_titles(resource_id: str):
        """Persist staged SAMRAS title rows via SandboxEngine (structure-aware when available)."""
        body = _json_body()
        staged = body.get("staged_entries") if isinstance(body.get("staged_entries"), list) else []
        entries = [dict(item) for item in staged if isinstance(item, dict)]
        result = promote_staged_samras_title_entries(_sandbox_engine(), resource_id, staged_entries=entries)
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.samras_promote_staged_titles.v1"
        return jsonify(out), (200 if bool(result.ok) else 400)

    @app.get("/portal/api/data/resources/local")
    def portal_data_resources_local():
        return jsonify(_document_catalog().local_inventory_payload())

    @app.get("/portal/api/data/system/resource_workbench")
    def portal_data_system_resource_workbench():
        return jsonify(_document_catalog().system_resource_workbench_payload())

    @app.post("/portal/api/data/system/mutate")
    def portal_data_system_mutate():
        body = _json_body()
        action = str(body.get("action") or "").strip().lower()
        file_key = str(body.get("file_key") or "").strip().lower()
        if not file_key:
            abort(400, description="file_key is required")
        samras_actions = {
            "samras_create_root",
            "samras_add_child",
            "samras_delete_branch",
            "samras_move_branch",
            "samras_set_child_count",
            "samras_update_title",
        }
        row_actions = {"create_row", "update_row", "delete_row"}
        if action not in row_actions | samras_actions:
            abort(
                400,
                description=(
                    "action must be create_row, update_row, delete_row, "
                    "samras_create_root, samras_add_child, samras_delete_branch, "
                    "samras_move_branch, samras_set_child_count, or samras_update_title"
                ),
            )
        if file_key in {"txa", "msn"} and action in row_actions:
            return (
                jsonify(
                    {
                        "ok": False,
                        "file_key": file_key,
                        "action": action,
                        "error": (
                            "raw SAMRAS row mutation is blocked; use structure-aware SAMRAS actions so addresses remain "
                            "derived from the governing structure"
                        ),
                        "allowed_actions": sorted(samras_actions),
                    }
                ),
                400,
            )
        if file_key == "anthology" and action in samras_actions:
            return (
                jsonify(
                    {
                        "ok": False,
                        "file_key": file_key,
                        "action": action,
                        "error": "SAMRAS structure actions are only valid for txa/msn system files",
                    }
                ),
                400,
            )

        _, active_payload, _, _ = _load_system_file_payload(file_key, prefer_staged=True)
        if file_key in {"txa", "msn"} and action in samras_actions:
            try:
                working_payload = dict(active_payload if isinstance(active_payload, dict) else {})
                child_count_raw = body.get("child_count", body.get("value"))
                child_count = None if child_count_raw is None else int(child_count_raw)
                title = str(body.get("title") or "").strip()
                address_id = str(body.get("address_id") or "").strip()
                parent_address = str(body.get("parent_address") or "").strip()
                updated_payload, updated_workspace, mutation = mutate_compact_payload(
                    working_payload,
                    action=action,
                    address_id=address_id,
                    parent_address=parent_address,
                    child_count=child_count,
                    title=title,
                )
                created_addresses = list(mutation.get("created_addresses") or []) if isinstance(mutation, dict) else []
                selected_address = ""
                if action == "samras_add_child" and created_addresses and child_count is not None and child_count > 0:
                    created_address = str(created_addresses[0]).strip()
                    updated_payload, updated_workspace, resize_mutation = mutate_compact_payload(
                        updated_payload,
                        action="samras_set_child_count",
                        address_id=created_address,
                        child_count=int(child_count),
                    )
                    mutation = {
                        "action": action,
                        "samras_structure": resize_mutation.get("samras_structure") if isinstance(resize_mutation, dict) else {},
                        "canonical_magnitude": resize_mutation.get("canonical_magnitude") if isinstance(resize_mutation, dict) else "",
                        "address_mapping": resize_mutation.get("address_mapping") if isinstance(resize_mutation, dict) else {},
                        "created_addresses": [created_address],
                        "removed_addresses": resize_mutation.get("removed_addresses") if isinstance(resize_mutation, dict) else [],
                    }
                    selected_address = created_address
                elif created_addresses:
                    selected_address = str(created_addresses[0]).strip()
                elif action in {"samras_set_child_count", "samras_update_title"}:
                    selected_address = address_id
                elif action == "samras_move_branch":
                    mapping = mutation.get("address_mapping") if isinstance(mutation, dict) and isinstance(mutation.get("address_mapping"), dict) else {}
                    selected_address = str(mapping.get(address_id) or parent_address).strip()
                elif action == "samras_create_root":
                    selected_address = str(created_addresses[0] if created_addresses else "").strip()
                write_meta = _persist_system_payload(file_key, updated_payload)
            except (InvalidSamrasStructure, ValueError) as exc:
                return jsonify({"ok": False, "file_key": file_key, "action": action, "error": str(exc)}), 400
            return jsonify(
                {
                    "ok": True,
                    "action": action,
                    "file_key": file_key,
                    "write": write_meta,
                    "mutation": mutation,
                    "samras_workspace": build_workspace_view_model(
                        updated_workspace,
                        selected_address_id=selected_address,
                        staged_entries=[],
                    ),
                    "workbench_payload": _document_catalog().system_resource_workbench_payload(),
                }
            )

        rows_map = _rows_payload_mapping(active_payload)

        if action == "create_row":
            layer_value = body.get("layer")
            value_group_value = body.get("value_group")
            try:
                layer = int("" if layer_value is None else str(layer_value).strip())
                value_group = int("" if value_group_value is None else str(value_group_value).strip())
            except Exception:
                abort(400, description="layer and value_group must be integers")
            pairs_body = body.get("pairs")
            pairs: list[dict[str, str]] = []
            if isinstance(pairs_body, list):
                for item in pairs_body:
                    if not isinstance(item, dict):
                        continue
                    pairs.append(
                        {
                            "reference": str(item.get("reference") or "").strip(),
                            "magnitude": str(item.get("magnitude") or "").strip(),
                        }
                    )
            if not pairs:
                pairs = [
                    {
                        "reference": str(body.get("reference") or "").strip(),
                        "magnitude": str(body.get("magnitude") or "").strip(),
                    }
                ]
            probe_payload = {"rows": rows_map}
            row_id = compute_next_append_datum_id(probe_payload, layer, value_group)
            if file_key == "anthology":
                result = workspace.append_anthology_datum(
                    layer=layer,
                    value_group=value_group,
                    reference=str(body.get("reference") or "").strip(),
                    magnitude=str(body.get("magnitude") or "").strip(),
                    label=str(body.get("label") or "").strip(),
                    pairs=pairs,
                )
                if not bool(result.get("ok")):
                    return jsonify(result), 400
                write_meta = {"write_mode": "direct", "target_path": str(_system_file_storage(file_key)[1]), "staged_present": False}
            else:
                rows_map[row_id] = build_append_row_dict(
                    datum_id=row_id,
                    label=str(body.get("label") or "").strip(),
                    pairs=pairs,
                    reference=str(body.get("reference") or "").strip(),
                    magnitude=str(body.get("magnitude") or "").strip(),
                )
                write_meta = _persist_system_rows(file_key, active_payload, rows_map)
            return jsonify(
                {
                    "ok": True,
                    "action": action,
                    "file_key": file_key,
                    "row_id": row_id,
                    "write": write_meta,
                    "workbench_payload": _document_catalog().system_resource_workbench_payload(),
                }
            )

        row_id = str(body.get("row_id") or body.get("identifier") or "").strip()
        if not row_id:
            abort(400, description="row_id is required")
        current_row = rows_map.get(row_id)
        if not isinstance(current_row, dict):
            return jsonify({"ok": False, "error": f"unknown system datum: {row_id}"}), 404

        if action == "delete_row":
            if file_key == "anthology":
                result = workspace.delete_anthology_datum(row_id=row_id)
                if not bool(result.get("ok")):
                    return jsonify(result), 400
                write_meta = {"write_mode": "direct", "target_path": str(_system_file_storage(file_key)[1]), "staged_present": False}
            else:
                rows_map.pop(row_id, None)
                write_meta = _persist_system_rows(file_key, active_payload, rows_map)
            return jsonify(
                {
                    "ok": True,
                    "action": action,
                    "file_key": file_key,
                    "row_id": row_id,
                    "write": write_meta,
                    "workbench_payload": _document_catalog().system_resource_workbench_payload(),
                }
            )

        next_label = str(body.get("label") or current_row.get("label") or "").strip()
        pairs_body = body.get("pairs")
        pairs: list[dict[str, str]] | None = None
        if isinstance(pairs_body, list):
            pairs = []
            for item in pairs_body:
                if not isinstance(item, dict):
                    continue
                pairs.append(
                    {
                        "reference": str(item.get("reference") or "").strip(),
                        "magnitude": str(item.get("magnitude") or "").strip(),
                    }
                )
        elif any(key in body for key in ("reference", "magnitude")):
            base_pairs = current_row.get("pairs") if isinstance(current_row.get("pairs"), list) else []
            first_pair = base_pairs[0] if base_pairs and isinstance(base_pairs[0], dict) else {}
            pairs = [
                {
                    "reference": str(body.get("reference") if "reference" in body else first_pair.get("reference") or current_row.get("reference") or "").strip(),
                    "magnitude": str(body.get("magnitude") if "magnitude" in body else first_pair.get("magnitude") or current_row.get("magnitude") or "").strip(),
                }
            ]

        if file_key == "anthology":
            if pairs is None and any(key in body for key in ("reference", "magnitude")):
                pairs = [
                    {
                        "reference": str(body.get("reference") or current_row.get("reference") or "").strip(),
                        "magnitude": str(body.get("magnitude") or current_row.get("magnitude") or "").strip(),
                    }
                ]
            result = workspace.update_anthology_profile(
                row_id=row_id,
                label=next_label,
                magnitude=body.get("magnitude"),
                pairs=pairs,
                icon_relpath=body.get("icon_relpath"),
            )
            if not bool(result.get("ok")):
                return jsonify(result), 400
            write_meta = {"write_mode": "direct", "target_path": str(_system_file_storage(file_key)[1]), "staged_present": False}
        else:
            if pairs is not None:
                rows_map[row_id] = build_updated_row_dict(current_row, label=next_label, pairs=pairs)
            else:
                rows_map[row_id] = build_updated_row_dict(
                    current_row,
                    label=next_label,
                    pairs=None,
                    magnitude_override=str(body.get("magnitude") or current_row.get("magnitude") or "") if "magnitude" in body else None,
                )
                if "reference" in body:
                    rows_map[row_id]["reference"] = str(body.get("reference") or "").strip()
                    pair_list = rows_map[row_id].get("pairs")
                    if isinstance(pair_list, list) and pair_list:
                        first = pair_list[0] if isinstance(pair_list[0], dict) else {}
                        first["reference"] = str(body.get("reference") or "").strip()
                        pair_list[0] = first
                        rows_map[row_id]["pairs"] = pair_list

            write_meta = _persist_system_rows(file_key, active_payload, rows_map)
        return jsonify(
            {
                "ok": True,
                "action": action,
                "file_key": file_key,
                "row_id": row_id,
                "write": write_meta,
                "workbench_payload": _document_catalog().system_resource_workbench_payload(),
            }
        )

    @app.post("/portal/api/data/system/publish")
    def portal_data_system_publish():
        body = _json_body()
        file_key = str(body.get("file_key") or "").strip().lower()
        if not file_key:
            abort(400, description="file_key is required")
        _, canonical_path, stage_path = _system_file_storage(file_key)
        if file_key == "anthology":
            return jsonify(
                {
                    "ok": True,
                    "file_key": file_key,
                    "published": False,
                    "message": "anthology.json writes are already direct",
                    "workbench_payload": _document_catalog().system_resource_workbench_payload(),
                }
            )
        if not stage_path.is_file():
            return jsonify({"ok": False, "error": "no staged system file exists to publish"}), 400
        staged_payload = _read_json_object(stage_path)
        _write_json_object_one_entry_per_line(canonical_path, staged_payload if isinstance(staged_payload, dict) else {})
        try:
            stage_path.unlink()
        except FileNotFoundError:
            pass
        return jsonify(
            {
                "ok": True,
                "file_key": file_key,
                "published": True,
                "canonical_path": str(canonical_path),
                "workbench_payload": _document_catalog().system_resource_workbench_payload(),
            }
        )

    @app.get("/portal/api/data/resources/inherited")
    def portal_data_resources_inherited():
        return jsonify(_document_catalog().inherited_inventory_payload(grouped_by_source_fn=_group_inherited_index))

    @app.get("/portal/api/data/resources/inherited/subscriptions")
    def portal_data_resources_inherited_subscriptions():
        return jsonify(discover_contract_subscription_status(_private_dir()))

    @app.post("/portal/api/data/resources/inherited/subscriptions/register")
    def portal_data_resources_inherited_subscriptions_register():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        body = _json_body()
        contract_id = str(body.get("contract_id") or "").strip()
        resource_ids = [str(item).strip() for item in list(body.get("resource_ids") or []) if str(item).strip()]
        if not contract_id:
            abort(400, description="contract_id is required")
        if not resource_ids:
            abort(400, description="resource_ids is required")
        payload = _inherited_subscription_service().register_subscription(contract_id=contract_id, resource_ids=resource_ids)
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/resources/inherited/subscriptions/unregister")
    def portal_data_resources_inherited_subscriptions_unregister():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        body = _json_body()
        contract_id = str(body.get("contract_id") or "").strip()
        resource_ids = [str(item).strip() for item in list(body.get("resource_ids") or []) if str(item).strip()]
        if not contract_id:
            abort(400, description="contract_id is required")
        if not resource_ids:
            abort(400, description="resource_ids is required")
        payload = _inherited_subscription_service().unregister_subscription(contract_id=contract_id, resource_ids=resource_ids)
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/resources/local/migrate_legacy_samras")
    def portal_data_resources_local_migrate_legacy_samras():
        body = _json_body()
        payload = _local_resource_service().migrate_legacy_samras(apply_changes=bool(body.get("apply", True)))
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/resources/local/create")
    def portal_data_resources_local_create():
        body = _json_body()
        payload = _action_service().create_local_resource(
            resource_kind=str(body.get("resource_kind") or "resource"),
            resource_name=str(body.get("resource_name") or body.get("resource_id") or "resource").strip(),
            seed_payload=body.get("seed_payload") if isinstance(body.get("seed_payload"), dict) else {},
        )
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/resources/local/publish")
    def portal_data_resources_local_publish():
        body = _json_body()
        resource_id = str(body.get("resource_id") or "").strip()
        if not resource_id:
            abort(400, description="resource_id is required")
        payload = _publish_service().publish_local_resource(
            resource_id=resource_id,
            resource_name=str(body.get("resource_name") or "").strip(),
            resource_kind=str(body.get("resource_kind") or "").strip(),
        )
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/resources/inherited/refresh")
    def portal_data_resources_inherited_refresh():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        body = _json_body()
        contract_id = str(body.get("contract_id") or "").strip()
        resource_id = str(body.get("resource_id") or "").strip()
        if not contract_id or not resource_id:
            abort(400, description="contract_id and resource_id are required")
        payload = _action_service().refresh_inherited_resource(
            contract_id=contract_id,
            resource_id=resource_id,
            force_refresh=bool(body.get("force_refresh", True)),
        )
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/resources/inherited/refresh_source")
    def portal_data_resources_inherited_refresh_source():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        body = _json_body()
        source_msn_id = str(body.get("source_msn_id") or "").strip()
        if not source_msn_id:
            abort(400, description="source_msn_id is required")
        payload = _action_service().refresh_inherited_source(
            source_msn_id=source_msn_id,
            force_refresh=bool(body.get("force_refresh", True)),
        )
        return jsonify(payload), 200

    @app.post("/portal/api/data/resources/inherited/disconnect_source")
    def portal_data_resources_inherited_disconnect_source():
        body = _json_body()
        source_msn_id = str(body.get("source_msn_id") or "").strip()
        if not source_msn_id:
            abort(400, description="source_msn_id is required")
        payload = _action_service().disconnect_inherited_source(source_msn_id=source_msn_id)
        return jsonify(payload), 200

    @app.get("/portal/api/data/sandbox/resources/<path:resource_id>")
    def portal_data_sandbox_resource(resource_id: str):
        return jsonify(_document_loader().sandbox_resource_detail(resource_id))

    @app.post("/portal/api/data/sandbox/resources/<path:resource_id>/stage")
    def portal_data_sandbox_resource_stage(resource_id: str):
        body = _json_body()
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
        out = _action_service().stage_sandbox_resource(resource_id=resource_id, payload=payload if isinstance(payload, dict) else {})
        return jsonify(out), (200 if bool(out.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/resources/<path:resource_id>/save")
    def portal_data_sandbox_resource_save(resource_id: str):
        body = _json_body()
        payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
        override = bool(body.get("rule_write_override"))
        reason = str(body.get("rule_write_override_reason") or "").strip()
        datum_rules: dict[str, Any] | None = None
        if isinstance(payload, dict):
            ev = _rules_service().evaluate_resource_payload(
                payload,
                rule_write_override=override,
                rule_write_override_reason=reason,
            )
            if ev is not None:
                datum_rules = ev
                if not bool(ev.get("ok")):
                    return jsonify(
                        {
                            "ok": False,
                            "datum_rules": ev,
                            "schema": "mycite.portal.sandbox.resource_save_rules.v1",
                            "rule_write_override_reason": reason,
                        }
                    ), 400
        out = _action_service().save_sandbox_resource(resource_id=resource_id, payload=payload if isinstance(payload, dict) else {})
        if datum_rules is not None and isinstance(out, dict):
            out["datum_rules"] = datum_rules
        return jsonify(out), (200 if bool(out.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/resources/<path:resource_id>/compile")
    def portal_data_sandbox_resource_compile(resource_id: str):
        out = _action_service().compile_sandbox_resource(resource_id=resource_id)
        return jsonify(out), (200 if bool(out.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/mss/compile")
    def portal_data_sandbox_mss_compile():
        body = _json_body()
        selected_refs = [str(item).strip() for item in list(body.get("selected_refs") or []) if str(item).strip()]
        resource_id = str(body.get("resource_id") or "mss_resource").strip()
        result = _sandbox_engine().compile_mss_resource(
            resource_id=resource_id,
            selected_refs=selected_refs,
            anthology_payload=_anthology_payload_for_mss_compile(),
            local_msn_id=_msn_id(),
        )
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.mss_compile.v1"
        return jsonify(out), (200 if result.ok else 400)

    @app.post("/portal/api/data/sandbox/mss/decode")
    def portal_data_sandbox_mss_decode():
        body = _json_body()
        bitstring = str(body.get("bitstring") or "").strip()
        resource_id = str(body.get("resource_id") or "mss_decode").strip()
        result = _sandbox_engine().decode_mss_resource(bitstring=bitstring, resource_id=resource_id)
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.mss_decode.v1"
        return jsonify(out), (200 if result.ok else 400)

    @app.post("/portal/api/data/sandbox/samras/upsert")
    def portal_data_sandbox_samras_upsert():
        body = _json_body()
        resource_id = str(body.get("resource_id") or "").strip()
        structure_payload = str(body.get("structure_payload") or "").strip()
        rows = body.get("rows") if isinstance(body.get("rows"), list) else []
        value_kind = str(body.get("value_kind") or "address_id").strip()
        if not resource_id:
            abort(400, description="resource_id is required")
        if not structure_payload:
            abort(400, description="structure_payload is required")
        result = _sandbox_engine().create_or_update_samras_resource(
            resource_id=resource_id,
            structure_payload=structure_payload,
            rows=[dict(item) for item in rows if isinstance(item, dict)],
            value_kind=value_kind,
            source="local_api",
        )
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.samras_upsert.v1"
        return jsonify(out), (200 if result.ok else 400)

    @app.post("/portal/api/data/sandbox/txa_workspace/view_model")
    def portal_data_sandbox_txa_workspace_view_model():
        """Assemble TXA sandbox title table + branch context (staged entries are preview-only)."""
        body = _json_body()
        rid = str(body.get("resource_id") or "").strip()
        if not rid:
            abort(400, description="resource_id is required")
        payload = _sandbox_engine().get_resource(rid)
        if bool(payload.get("missing")):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"resource not found: {rid}",
                        "schema": "mycite.portal.sandbox.txa_workspace.view_model.v1",
                    }
                ),
                404,
            )
        selected = str(body.get("selected_address_id") or "").strip()
        staged = body.get("staged_entries") if isinstance(body.get("staged_entries"), list) else []
        vm = build_txa_sandbox_view_model(payload, selected_address_id=selected, staged_entries=staged)
        return jsonify({"ok": True, **vm})

    @app.get("/portal/api/data/sandbox/samras/<path:resource_id>/decode")
    def portal_data_sandbox_samras_decode(resource_id: str):
        result = _sandbox_engine().decode_samras_resource(resource_id)
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.samras_decode.v1"
        return jsonify(out), (200 if result.ok else 400)

    @app.get("/portal/api/data/sandbox/samras/<path:resource_id>/structure")
    def portal_data_sandbox_samras_structure(resource_id: str):
        result = _sandbox_engine().decode_samras_resource(resource_id)
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.samras_structure.v1"
        return jsonify(out), (200 if result.ok else 400)

    @app.post("/portal/api/data/sandbox/samras/<path:resource_id>/node/inspect")
    def portal_data_sandbox_samras_node_inspect(resource_id: str):
        body = _json_body()
        address_id = str(body.get("address_id") or "").strip()
        if not address_id:
            abort(400, description="address_id is required")
        try:
            payload = _sandbox_engine().inspect_samras_node(resource_id=resource_id, address_id=address_id)
        except Exception as exc:
            return jsonify({"ok": False, "schema": "mycite.portal.sandbox.samras.inspect_node.v1", "errors": [str(exc)]}), 400
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/samras/<path:resource_id>/node/set")
    def portal_data_sandbox_samras_node_set(resource_id: str):
        body = _json_body()
        address_id = str(body.get("address_id") or "").strip()
        if not address_id:
            abort(400, description="address_id is required")
        value = body.get("value")
        try:
            payload = _sandbox_engine().set_samras_node(
                resource_id=resource_id,
                address_id=address_id,
                value=int(value if value is not None else 0),
            )
        except Exception as exc:
            return jsonify({"ok": False, "schema": "mycite.portal.sandbox.samras.set_node.v1", "errors": [str(exc)]}), 400
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/samras/<path:resource_id>/node/create_child")
    def portal_data_sandbox_samras_node_create_child(resource_id: str):
        body = _json_body()
        parent_address = str(body.get("parent_address") or "").strip()
        if not parent_address:
            abort(400, description="parent_address is required")
        value = body.get("value")
        try:
            payload = _sandbox_engine().create_samras_child(
                resource_id=resource_id,
                parent_address=parent_address,
                value=int(value if value is not None else 0),
            )
        except Exception as exc:
            return jsonify({"ok": False, "schema": "mycite.portal.sandbox.samras.create_child.v1", "errors": [str(exc)]}), 400
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/samras/<path:resource_id>/node/delete")
    def portal_data_sandbox_samras_node_delete(resource_id: str):
        body = _json_body()
        address_id = str(body.get("address_id") or "").strip()
        if not address_id:
            abort(400, description="address_id is required")
        try:
            payload = _sandbox_engine().delete_samras_address(resource_id=resource_id, address_id=address_id)
        except Exception as exc:
            return jsonify({"ok": False, "schema": "mycite.portal.sandbox.samras.delete_address.v1", "errors": [str(exc)]}), 400
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/samras/<path:resource_id>/branch/move")
    def portal_data_sandbox_samras_branch_move(resource_id: str):
        body = _json_body()
        from_address = str(body.get("from_address") or "").strip()
        to_parent_address = str(body.get("to_parent_address") or "").strip()
        if not from_address or not to_parent_address:
            abort(400, description="from_address and to_parent_address are required")
        try:
            payload = _sandbox_engine().move_samras_branch(
                resource_id=resource_id,
                from_address=from_address,
                to_parent_address=to_parent_address,
            )
        except Exception as exc:
            return jsonify({"ok": False, "schema": "mycite.portal.sandbox.samras.move_branch.v1", "errors": [str(exc)]}), 400
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/inherited/resolve")
    def portal_data_sandbox_inherited_resolve():
        body = _json_body()
        resource_ref = str(body.get("resource_ref") or "").strip()
        if not resource_ref:
            abort(400, description="resource_ref is required")
        context = _sandbox_engine().resolve_inherited_resource_context(
            resource_ref=resource_ref,
            local_msn_id=_msn_id(),
            external_resolver=external_resource_resolver,
        )
        out = context.to_dict()
        out["schema"] = "mycite.portal.sandbox.inherited_context.v1"
        return jsonify(out), (200 if context.ok else 400)

    @app.post("/portal/api/data/sandbox/inherited/compile_txa")
    def portal_data_sandbox_inherited_compile_txa():
        body = _json_body()
        resource_ref = str(body.get("resource_ref") or "").strip()
        if not resource_ref:
            abort(400, description="resource_ref is required")
        inherited_refs = [str(item).strip() for item in list(body.get("inherited_refs") or []) if str(item).strip()]
        context = _canonical_anthology_context()
        payload = _sandbox_engine().compile_txa_inherited_context(
            resource_ref=resource_ref,
            local_msn_id=_msn_id(),
            external_resolver=external_resource_resolver,
            merged_rows_by_id=context.rows_by_id,
            inherited_refs=inherited_refs,
        )
        payload["schema"] = "mycite.portal.sandbox.inherited_compile_txa.v1"
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/inherited/adapt_txa")
    def portal_data_sandbox_inherited_adapt_txa():
        body = _json_body()
        published_value = body.get("published_resource_value")
        if not isinstance(published_value, dict):
            resource_ref = str(body.get("resource_ref") or "").strip()
            if not resource_ref:
                abort(400, description="published_resource_value or resource_ref is required")
            resolved = _sandbox_engine().resolve_inherited_resource_context(
                resource_ref=resource_ref,
                local_msn_id=_msn_id(),
                external_resolver=external_resource_resolver,
            )
            if not resolved.ok:
                return jsonify({"ok": False, "errors": list(resolved.errors), "warnings": list(resolved.warnings)}), 400
            published_value = resolved.resource_value if isinstance(resolved.resource_value, dict) else {}
        payload = _sandbox_engine().adapt_published_txa_context(
            published_resource_value=published_value,
            context_source="sandbox.inherited.adapt_txa",
        )
        payload["schema"] = "mycite.portal.sandbox.inherited_adapt_txa.v1"
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.get("/portal/api/data/sandbox/exposed/contact_card")
    def portal_data_sandbox_exposed_contact_card():
        source_msn_id = _msn_id()
        card_payload = {}
        if source_msn_id and external_resource_resolver is not None:
            try:
                if hasattr(external_resource_resolver, "_load_public_card"):
                    card_payload = dict(external_resource_resolver._load_public_card(source_msn_id) or {})
                elif hasattr(external_resource_resolver, "_load_contact_card"):
                    card_payload = dict(external_resource_resolver._load_contact_card(source_msn_id) or {})
            except Exception:
                card_payload = {}
        payload = _sandbox_engine().generate_contact_card_public_resources(
            card_payload=card_payload,
            local_msn_id=source_msn_id,
        )
        payload["schema"] = "mycite.portal.sandbox.contact_card_exposed.v1"
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/sandbox/migrate/fnd_samras")
    def portal_data_sandbox_migrate_fnd_samras():
        body = _json_body()
        apply_changes = bool(body.get("apply"))
        data_root = Path(str(getattr(getattr(workspace, "storage", None), "data_dir", ".")))
        anthology_path = data_root / "anthology.json"
        result = migrate_fnd_samras_rows_to_sandbox(
            anthology_path=anthology_path,
            data_root=data_root,
            apply_changes=apply_changes,
        )
        out = result.to_dict()
        out["schema"] = "mycite.portal.sandbox.migrate_fnd_samras.v1"
        out["anthology_path"] = str(anthology_path)
        out["apply"] = apply_changes
        return jsonify(out), (200 if result.ok else 400)

    @app.get("/portal/api/data/aitas/archetypes")
    def portal_data_aitas_archetypes():
        payload = list_archetype_registry_payload()
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/aitas/archetype/inspect")
    def portal_data_aitas_archetype_inspect():
        body = _json_body()
        datum_ref = str(body.get("datum_ref") or body.get("ref") or "").strip()
        if not datum_ref:
            abort(400, description="datum_ref is required")
        payload = inspect_archetype_context(
            datum_ref=datum_ref,
            local_msn_id=_msn_id(),
            anthology_payload=_canonical_rows_payload(),
        )
        payload["schema"] = "mycite.portal.aitas.inspect.v1"
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.post("/portal/api/data/aitas/archetype/trace")
    def portal_data_aitas_archetype_trace():
        body = _json_body()
        datum_ref = str(body.get("datum_ref") or body.get("ref") or "").strip()
        if not datum_ref:
            abort(400, description="datum_ref is required")
        payload = inspect_archetype_trace(
            datum_ref=datum_ref,
            local_msn_id=_msn_id(),
            anthology_payload=_canonical_rows_payload(),
        )
        payload["schema"] = "mycite.portal.aitas.trace.v1"
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.get("/portal/api/data/aitas/archetype/bindings")
    def portal_data_aitas_archetype_bindings():
        limit_raw = str(request.args.get("limit") or "200").strip()
        try:
            limit = max(1, min(1000, int(limit_raw)))
        except Exception:
            limit = 200
        payload = list_derived_archetype_bindings(
            local_msn_id=_msn_id(),
            anthology_payload=_canonical_rows_payload(),
            limit=limit,
        )
        payload["schema"] = "mycite.portal.aitas.bindings.v1"
        return jsonify(payload), (200 if bool(payload.get("ok")) else 400)

    @app.get("/portal/api/data/rules/understanding/anthology")
    def portal_data_rules_understanding_anthology():
        report = understand_datums(_canonical_rows_payload())
        out = report.to_dict()
        out["rule_policy_by_id"] = {k: derive_rule_policy(v).to_dict() for k, v in report.by_id.items()}
        out["schema"] = "mycite.portal.datum_rules.understanding.v1"
        out["scope"] = "anthology"
        return jsonify(out), (200 if bool(out.get("ok")) else 400)

    @app.get("/portal/api/data/rules/understanding/resource/<path:resource_id>")
    def portal_data_rules_understanding_resource(resource_id: str):
        report = understand_datums(_rule_rows_payload_from_sandbox_resource(resource_id))
        out = report.to_dict()
        out["rule_policy_by_id"] = {k: derive_rule_policy(v).to_dict() for k, v in report.by_id.items()}
        out["schema"] = "mycite.portal.datum_rules.understanding.v1"
        out["scope"] = "sandbox_resource"
        out["resource_id"] = str(resource_id or "").strip()
        return jsonify(out), (200 if bool(out.get("ok")) else 400)

    @app.post("/portal/api/data/rules/reference_filter")
    def portal_data_rules_reference_filter():
        body = _json_body()
        rule_key = str(body.get("rule_key") or "").strip()
        scope = str(body.get("scope") or "anthology").strip().lower()
        resource_id = str(body.get("resource_id") or "").strip()
        if scope != "anthology" and not resource_id:
            abort(400, description="resource_id is required when scope is not anthology")
        rows_payload = _canonical_rows_payload() if scope == "anthology" else _rule_rows_payload_from_sandbox_resource(resource_id)
        report = understand_datums(rows_payload)
        if not rule_key:
            vg_raw = body.get("value_group")
            try:
                vgi = int(vg_raw) if vg_raw is not None and str(vg_raw).strip() != "" else None
            except Exception:
                vgi = None
            mag = str(body.get("magnitude_hint") or body.get("magnitude") or "").strip()
            parent = str(body.get("parent_datum_id") or "").strip()
            rule_key = infer_reference_filter_rule_key(
                value_group=vgi,
                magnitude_hint=mag,
                parent_datum_id=parent,
                report=report,
            ) or ""
        if not rule_key:
            abort(
                400,
                description="rule_key is required, or supply inference hints (value_group, optional magnitude_hint, parent_datum_id)",
            )
        filter_ctx = body.get("filter_context") if isinstance(body.get("filter_context"), dict) else {}
        out = reference_filter_options(rows_payload, rule_key=rule_key, filter_context=filter_ctx)
        out["scope"] = scope
        out["resolved_rule_key"] = rule_key
        out["datum_understanding"] = report.to_dict()
        out["rule_policy_by_id"] = {k: derive_rule_policy(v).to_dict() for k, v in report.by_id.items()}
        ref_mode = str(body.get("ref_entry_mode") or "filtered").strip().lower()
        if ref_mode == "manual":
            if not bool(body.get("rule_ref_manual_ack")):
                abort(400, description="ref_entry_mode=manual requires rule_ref_manual_ack=true")
            catalog: list[dict[str, Any]] = []
            for datum_id, u in sorted(report.by_id.items(), key=lambda item: item[0]):
                catalog.append(
                    {
                        "datum_id": datum_id,
                        "family": u.family,
                        "status": u.status,
                        "ui_hints": dict(u.ui_hints),
                    }
                )
            out["references"] = catalog
            out["ref_mode_resolved"] = "manual_catalog"
        else:
            out["ref_mode_resolved"] = "filtered"
        return jsonify(out), (200 if bool(out.get("ok")) else 400)

    @app.post("/portal/api/data/rules/validate_create")
    def portal_data_rules_validate_create():
        body = _json_body()
        rule_key = str(body.get("rule_key") or "").strip()
        scope = str(body.get("scope") or "anthology").strip().lower()
        resource_id = str(body.get("resource_id") or "").strip()
        if scope != "anthology" and not resource_id:
            abort(400, description="resource_id is required when scope is not anthology")
        reference = str(body.get("reference") or "").strip()
        magnitude = str(body.get("magnitude") or "").strip()
        rows_payload = _canonical_rows_payload() if scope == "anthology" else _rule_rows_payload_from_sandbox_resource(resource_id)
        pairs_body = body.get("pairs")
        pairs_list = [dict(item) for item in pairs_body if isinstance(item, dict)] if isinstance(pairs_body, list) else None
        try:
            value_group = int(body.get("value_group"))
        except Exception:
            abort(400, description="value_group must be an integer")
        layer_raw = body.get("layer")
        try:
            layer_i = int(layer_raw) if layer_raw is not None and str(layer_raw).strip() != "" else 999
        except Exception:
            layer_i = 999
        override = bool(body.get("rule_write_override"))
        probe_id = compute_next_append_datum_id(rows_payload, layer_i, value_group)
        pair_rows: list[dict[str, str]] = []
        if isinstance(pairs_body, list):
            for item in pairs_body:
                if not isinstance(item, dict):
                    continue
                pair_rows.append(
                    {
                        "reference": str(item.get("reference") or "").strip(),
                        "magnitude": str(item.get("magnitude") or "").strip(),
                    }
                )
        if not pair_rows:
            pair_rows = [{"reference": reference, "magnitude": magnitude}]
        row_dict = build_append_row_dict(
            datum_id=probe_id,
            label=str(body.get("label") or "").strip(),
            pairs=pair_rows,
            reference=reference,
            magnitude=magnitude,
        )
        ev = evaluate_probe_write(
            rows_payload,
            probe_row_id=probe_id,
            probe_row_dict=row_dict,
            rule_key_hint=rule_key,
            rule_write_override=override,
            pairs_for_hint=pairs_list,
            value_group_hint=value_group,
        )
        ev["scope"] = scope
        ev["schema"] = "mycite.portal.datum_rules.validate_create.v1"
        return jsonify(ev), (200 if bool(ev.get("ok")) else 400)

    @app.post("/portal/api/data/rules/lens")
    def portal_data_rules_lens():
        body = _json_body()
        datum_id = str(body.get("datum_id") or body.get("row_id") or "").strip()
        scope = str(body.get("scope") or "anthology").strip().lower()
        if not datum_id:
            abort(400, description="datum_id is required")
        rows_payload = (
            _canonical_rows_payload()
            if scope == "anthology"
            else _rule_rows_payload_from_sandbox_resource(str(body.get("resource_id") or "").strip())
        )
        out = resolve_lens_for_datum(rows_payload, datum_id=datum_id)
        out["scope"] = scope
        return jsonify(out), (200 if bool(out.get("ok")) else 400)

    @app.get("/portal/api/data/write/field_contracts")
    def portal_data_write_field_contracts():
        contracts = default_profile_field_contracts()
        return jsonify(
            {
                "ok": True,
                "contracts": {key: value.to_dict() for key, value in contracts.items()},
                "schema": "mycite.portal.write.field_contracts.v1",
            }
        )

    @app.post("/portal/api/data/write/preview")
    def portal_data_write_preview():
        body = _json_body()
        intent = body.get("intent") if isinstance(body.get("intent"), dict) else body
        if not isinstance(intent, dict):
            intent = {}
        fields = intent.get("fields") if isinstance(intent.get("fields"), dict) else {}
        write_mode = str(intent.get("write_mode") or "").strip()
        if write_mode == "stage_inherited_ref" and not str(fields.get("inherited_ref") or "").strip():
            txa_context = _sandbox_engine().compile_txa_inherited_context(
                resource_ref=str(intent.get("resource_ref") or intent.get("resource_id") or "").strip(),
                local_msn_id=_msn_id(),
                external_resolver=external_resource_resolver,
                merged_rows_by_id=_canonical_anthology_context().rows_by_id,
            )
            selected = select_inherited_binding_for_field(
                field_id=str(intent.get("field_id") or "").strip(),
                field_ref_bindings=(
                    (txa_context or {}).get("field_ref_bindings")
                    if isinstance((txa_context or {}).get("field_ref_bindings"), dict)
                    else {}
                ),
            )
            inherited_ref = str(selected.get("selected_ref") or "").strip()
            if selected.get("warnings"):
                txa_context["binding_warnings"] = [str(item).strip() for item in list(selected.get("warnings") or []) if str(item).strip()]
            if inherited_ref:
                fields["inherited_ref"] = inherited_ref
                intent["fields"] = fields
            intent["inherited_context"] = txa_context
        if not str(intent.get("local_msn_id") or "").strip():
            intent["local_msn_id"] = _msn_id()
        preview = preview_write_intent(
            intent=intent if isinstance(intent, dict) else {},
            current_config=_load_active_config(),
            local_anthology_payload=_canonical_rows_payload(),
            external_plan_fn=_external_plan_for_intent,
        )
        payload = preview.to_dict()
        payload["schema"] = "mycite.portal.write.preview.v1"
        return jsonify(payload), (200 if preview.ok else 400)

    @app.post("/portal/api/data/write/apply")
    def portal_data_write_apply():
        body = _json_body()
        intent = body.get("intent") if isinstance(body.get("intent"), dict) else {}
        fields = intent.get("fields") if isinstance(intent.get("fields"), dict) else {}
        write_mode = str(intent.get("write_mode") or "").strip()
        if write_mode == "stage_inherited_ref" and not str(fields.get("inherited_ref") or "").strip():
            txa_context = _sandbox_engine().compile_txa_inherited_context(
                resource_ref=str(intent.get("resource_ref") or intent.get("resource_id") or "").strip(),
                local_msn_id=_msn_id(),
                external_resolver=external_resource_resolver,
                merged_rows_by_id=_canonical_anthology_context().rows_by_id,
            )
            selected = select_inherited_binding_for_field(
                field_id=str(intent.get("field_id") or "").strip(),
                field_ref_bindings=(
                    (txa_context or {}).get("field_ref_bindings")
                    if isinstance((txa_context or {}).get("field_ref_bindings"), dict)
                    else {}
                ),
            )
            inherited_ref = str(selected.get("selected_ref") or "").strip()
            if selected.get("warnings"):
                txa_context["binding_warnings"] = [str(item).strip() for item in list(selected.get("warnings") or []) if str(item).strip()]
            if inherited_ref:
                fields["inherited_ref"] = inherited_ref
                intent["fields"] = fields
            intent["inherited_context"] = txa_context
        if body.get("preview") and isinstance(body.get("preview"), dict):
            preview_payload = dict(body.get("preview"))
            preview_payload.pop("schema", None)
            preview_intent = preview_payload.get("intent") if isinstance(preview_payload.get("intent"), dict) else {}
            if not str(preview_intent.get("local_msn_id") or "").strip():
                preview_intent["local_msn_id"] = _msn_id()
            preview = preview_write_intent(
                intent=preview_intent,
                current_config=_load_active_config(),
                local_anthology_payload=_canonical_rows_payload(),
                external_plan_fn=_external_plan_for_intent,
            )
        else:
            if not str(intent.get("local_msn_id") or "").strip():
                intent["local_msn_id"] = _msn_id()
            preview = preview_write_intent(
                intent=intent,
                current_config=_load_active_config(),
                local_anthology_payload=_canonical_rows_payload(),
                external_plan_fn=_external_plan_for_intent,
            )
        result = apply_write_preview(
            preview=preview,
            workspace=workspace,
            load_config_fn=_load_active_config,
            save_config_fn=_save_active_config,
        )
        payload = result.to_dict()
        payload["schema"] = "mycite.portal.write.apply.v1"
        return jsonify(payload), (200 if result.ok else 400)

    @app.post("/portal/api/data/geometry/preview")
    def portal_data_geometry_preview():
        body = _json_body()
        intent = body.get("intent") if isinstance(body.get("intent"), dict) else dict(body)
        intent["intent_type"] = "geometry_datum"
        if not str(intent.get("local_msn_id") or "").strip():
            intent["local_msn_id"] = _msn_id()
        preview = preview_write_intent(
            intent=intent,
            current_config=_load_active_config(),
            local_anthology_payload=_canonical_rows_payload(),
            external_plan_fn=_external_plan_for_intent,
        )
        payload = preview.to_dict()
        payload["schema"] = "mycite.portal.geometry.preview.v1"
        return jsonify(payload), (200 if preview.ok else 400)

    @app.post("/portal/api/data/geometry/apply")
    def portal_data_geometry_apply():
        body = _json_body()
        intent = body.get("intent") if isinstance(body.get("intent"), dict) else dict(body)
        intent["intent_type"] = "geometry_datum"
        if not str(intent.get("local_msn_id") or "").strip():
            intent["local_msn_id"] = _msn_id()
        preview = preview_write_intent(
            intent=intent,
            current_config=_load_active_config(),
            local_anthology_payload=_canonical_rows_payload(),
            external_plan_fn=_external_plan_for_intent,
        )
        result = apply_write_preview(
            preview=preview,
            workspace=workspace,
            load_config_fn=_load_active_config,
            save_config_fn=_save_active_config,
        )
        payload = result.to_dict()
        payload["schema"] = "mycite.portal.geometry.apply.v1"
        return jsonify(payload), (200 if result.ok else 400)

    @app.get("/portal/api/data/external/resources")
    def portal_data_external_resources():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        source_msn_id = str(request.args.get("source_msn_id") or request.args.get("msn_id") or "").strip()
        if not source_msn_id:
            abort(400, description="source_msn_id is required")
        resources = external_resource_resolver.list_public_resources(source_msn_id=source_msn_id)
        return jsonify({"ok": True, "source_msn_id": source_msn_id, "resources": resources})

    @app.post("/portal/api/data/external/fetch")
    def portal_data_external_fetch():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        body = _json_body()
        source_msn_id = str(body.get("source_msn_id") or body.get("msn_id") or "").strip()
        resource_id = str(body.get("resource_id") or "").strip()
        if not source_msn_id or not resource_id:
            abort(400, description="source_msn_id and resource_id are required")
        force_refresh = bool(body.get("force_refresh"))
        result = external_resource_resolver.fetch_and_cache_bundle(
            source_msn_id=source_msn_id,
            resource_id=resource_id,
            force_refresh=force_refresh,
        )
        return jsonify(result), (200 if bool(result.get("ok")) else 400)

    @app.post("/portal/api/data/external/preview_closure")
    def portal_data_external_preview_closure():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        body = _json_body()
        source_msn_id = str(body.get("source_msn_id") or body.get("msn_id") or "").strip()
        resource_id = str(body.get("resource_id") or "").strip()
        target_refs = body.get("target_refs")
        if not source_msn_id or not resource_id:
            abort(400, description="source_msn_id and resource_id are required")
        if not isinstance(target_refs, list):
            abort(400, description="target_refs[] is required")
        result = external_resource_resolver.preview_required_closure(
            source_msn_id=source_msn_id,
            resource_id=resource_id,
            target_refs=[str(item or "").strip() for item in target_refs],
        )
        return jsonify(result), (200 if bool(result.get("ok")) else 400)

    @app.post("/portal/api/data/external/plan_materialization")
    def portal_data_external_plan_materialization():
        if external_resource_resolver is None:
            abort(501, description="external resource resolver is unavailable")
        if anthology_payload_provider is None:
            abort(501, description="anthology payload provider is unavailable")
        body = _json_body()
        source_msn_id = str(body.get("source_msn_id") or body.get("msn_id") or "").strip()
        resource_id = str(body.get("resource_id") or "").strip()
        target_ref = str(body.get("target_ref") or "").strip()
        required_refs = body.get("required_refs")
        allow_auto_create = bool(body.get("allow_auto_create", False))
        if not source_msn_id or not resource_id or not target_ref:
            abort(400, description="source_msn_id, resource_id, and target_ref are required")
        if not isinstance(required_refs, list):
            abort(400, description="required_refs[] is required")
        plan = external_resource_resolver.plan_materialization(
            source_msn_id=source_msn_id,
            resource_id=resource_id,
            target_ref=target_ref,
            required_refs=[str(item or "").strip() for item in required_refs],
            anthology_payload=anthology_payload_provider() or {},
            allow_auto_create=allow_auto_create,
        )
        payload = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
        return jsonify({"ok": bool(payload.get("ok")), "plan": payload}), (200 if bool(payload.get("ok")) else 400)

    @app.get("/portal/api/data/anthology/table")
    def portal_data_anthology_table():
        if not hasattr(workspace, "anthology_table_view"):
            abort(501, description="anthology table view is unavailable")
        payload = workspace.anthology_table_view()
        payload["ok"] = True
        try:
            rule_report = understand_datums(_canonical_rows_payload())
            payload["datum_understanding"] = rule_report.to_dict()
            payload["rule_policy_by_id"] = {k: derive_rule_policy(v).to_dict() for k, v in rule_report.by_id.items()}
        except Exception:
            payload["datum_understanding"] = {"ok": False, "understandings": [], "by_id": {}, "warnings": [], "errors": []}
            payload["rule_policy_by_id"] = {}
        return jsonify(payload)

    @app.get("/portal/api/data/anthology/graph")
    def portal_data_anthology_graph():
        if not hasattr(workspace, "anthology_graph_view"):
            abort(501, description="anthology graph view is unavailable")
        focus = str(request.args.get("focus") or "").strip()
        layout = str(request.args.get("layout") or "grouped").strip().lower()
        context_mode = str(request.args.get("context") or "global").strip().lower()
        depth_raw = str(request.args.get("depth") or "").strip()
        depth: int | None = None
        if depth_raw:
            try:
                depth = max(0, int(depth_raw))
            except Exception:
                depth = None
        try:
            payload = workspace.anthology_graph_view(
                focus_identifier=focus,
                depth_limit=depth,
                layout_mode=layout,
                context_mode=context_mode,
            )
        except TypeError:
            payload = workspace.anthology_graph_view()
        payload["ok"] = bool(payload.get("ok", True))
        return jsonify(payload), (200 if payload["ok"] else 400)

    @app.get("/portal/api/data/daemon/ports")
    def portal_data_daemon_ports():
        if not hasattr(workspace, "daemon_port_catalog"):
            return jsonify({"ok": True, "ports": []})
        return jsonify({"ok": True, "ports": workspace.daemon_port_catalog()})

    @app.post("/portal/api/data/daemon/resolve")
    def portal_data_daemon_resolve():
        if not hasattr(workspace, "daemon_port_resolve"):
            abort(501, description="daemon port resolve is unavailable")
        body = _json_body()
        focus_payload = body.get("default_focus") if isinstance(body.get("default_focus"), dict) else {}
        result = workspace.daemon_port_resolve(
            port_id=str(body.get("port_id") or "").strip(),
            action=(str(body.get("action") or "").strip().lower() or None),
            method=(str(body.get("method") or "").strip().lower() or None),
            aitas_context=body.get("aitas_context") if isinstance(body.get("aitas_context"), dict) else None,
            focus_source=(
                str(body.get("focus_source") or focus_payload.get("focus_source") or "").strip().lower() or None
            ),
            focus_subject=(
                str(body.get("focus_subject") or focus_payload.get("focus_subject") or "").strip() or None
            ),
            output_strategy=(str(body.get("output_strategy") or "").strip().lower() or None),
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "daemon_port_catalog"):
            response["daemon_ports"] = workspace.daemon_port_catalog()
        if hasattr(workspace, "model_meta"):
            response["model_meta"] = workspace.model_meta()
        return jsonify(response), status

    @app.post("/portal/api/data/daemon/resolve_tokens")
    def portal_data_daemon_resolve_tokens():
        if not hasattr(workspace, "daemon_resolve_tokens"):
            abort(501, description="daemon token resolve is unavailable")
        body = _json_body()
        raw_tokens = body.get("tokens")
        if not isinstance(raw_tokens, list):
            abort(400, description="tokens[] is required")
        result = workspace.daemon_resolve_tokens(
            tokens=[str(item or "").strip() for item in raw_tokens],
            standard_id=str(body.get("standard_id") or "coordinate").strip().lower() or "coordinate",
            context=body.get("context") if isinstance(body.get("context"), dict) else {},
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "model_meta"):
            response["model_meta"] = workspace.model_meta()
        return jsonify(response), status

    @app.get("/portal/api/data/time_series/state")
    def portal_data_time_series_state():
        if not hasattr(workspace, "time_series_state"):
            abort(501, description="time series state is unavailable")
        payload = workspace.time_series_state()
        payload["ok"] = bool(payload.get("ok", True))
        return jsonify(payload), (200 if payload["ok"] else 400)

    @app.post("/portal/api/data/time_series/ensure_base")
    def portal_data_time_series_ensure_base():
        if not hasattr(workspace, "time_series_ensure_base"):
            abort(501, description="time series ensure_base is unavailable")
        result = workspace.time_series_ensure_base()
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.post("/portal/api/data/time_series/event/create")
    def portal_data_time_series_event_create():
        if not hasattr(workspace, "time_series_create_event"):
            abort(501, description="time series event/create is unavailable")
        body = _json_body()
        result = workspace.time_series_create_event(
            point_ref=str(body.get("point_ref") or "").strip(),
            duration_ref=str(body.get("duration_ref") or "").strip(),
            start_unix_s=body.get("start_unix_s"),
            duration_s=body.get("duration_s"),
            label=str(body.get("label") or "").strip(),
        )
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.post("/portal/api/data/time_series/event/update")
    def portal_data_time_series_event_update():
        if not hasattr(workspace, "time_series_update_event"):
            abort(501, description="time series event/update is unavailable")
        body = _json_body()
        result = workspace.time_series_update_event(
            event_ref=str(body.get("event_ref") or "").strip(),
            point_ref=(str(body.get("point_ref")).strip() if "point_ref" in body else None),
            duration_ref=(str(body.get("duration_ref")).strip() if "duration_ref" in body else None),
            start_unix_s=(body.get("start_unix_s") if "start_unix_s" in body else None),
            duration_s=(body.get("duration_s") if "duration_s" in body else None),
            label=(str(body.get("label")) if "label" in body else None),
        )
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.post("/portal/api/data/time_series/event/delete")
    def portal_data_time_series_event_delete():
        if not hasattr(workspace, "time_series_delete_event"):
            abort(501, description="time series event/delete is unavailable")
        body = _json_body()
        result = workspace.time_series_delete_event(event_ref=str(body.get("event_ref") or "").strip())
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.get("/portal/api/data/time_series/event/<path:event_ref>")
    def portal_data_time_series_event_detail(event_ref: str):
        if not hasattr(workspace, "time_series_event_detail"):
            abort(501, description="time series event detail is unavailable")
        result = workspace.time_series_event_detail(event_ref=str(event_ref or "").strip())
        status = 200 if bool(result.get("ok")) else 404
        return jsonify(result), status

    @app.get("/portal/api/data/time_series/table/<table_id>/view")
    def portal_data_time_series_table_view(table_id: str):
        if not hasattr(workspace, "time_series_table_view"):
            abort(501, description="time series table view is unavailable")
        mode = str(request.args.get("mode") or "normal").strip().lower()
        result = workspace.time_series_table_view(table_id=str(table_id or "").strip(), mode=mode)
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.get("/portal/api/data/samras/instances")
    def portal_data_samras_instances():
        if not hasattr(workspace, "samras_instances"):
            abort(501, description="samras instances are unavailable")
        result = workspace.samras_instances()
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.get("/portal/api/data/samras/table/<instance_id>")
    def portal_data_samras_table(instance_id: str):
        if not hasattr(workspace, "samras_table_view"):
            abort(501, description="samras table view is unavailable")
        filter_text = str(request.args.get("filter") or "").strip()
        expanded_arg = str(request.args.get("expanded") or "").strip()
        expanded_nodes = [token.strip() for token in expanded_arg.split(",") if token.strip()]
        result = workspace.samras_table_view(
            instance_id=str(instance_id or "").strip(),
            filter_text=filter_text,
            expanded_nodes=expanded_nodes,
        )
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.post("/portal/api/data/samras/table/create")
    def portal_data_samras_table_create():
        if not hasattr(workspace, "samras_create_table"):
            abort(501, description="samras table create is unavailable")
        body = _json_body()
        result = workspace.samras_create_table(
            instance_id=str(body.get("instance_id") or "").strip(),
            table_name=str(body.get("table_name") or "").strip(),
        )
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.post("/portal/api/data/samras/row/upsert")
    def portal_data_samras_row_upsert():
        if not hasattr(workspace, "samras_row_upsert"):
            abort(501, description="samras row upsert is unavailable")
        body = _json_body()
        result = workspace.samras_row_upsert(
            instance_id=str(body.get("instance_id") or "").strip(),
            address_id=str(body.get("address_id") or "").strip(),
            title=str(body.get("title") or "").strip(),
        )
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.post("/portal/api/data/samras/row/delete")
    def portal_data_samras_row_delete():
        if not hasattr(workspace, "samras_row_delete"):
            abort(501, description="samras row delete is unavailable")
        body = _json_body()
        result = workspace.samras_row_delete(
            instance_id=str(body.get("instance_id") or "").strip(),
            address_id=str(body.get("address_id") or "").strip(),
        )
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.get("/portal/api/data/samras/graph/<instance_id>")
    def portal_data_samras_graph(instance_id: str):
        if not hasattr(workspace, "samras_graph_view"):
            abort(501, description="samras graph view is unavailable")
        filter_text = str(request.args.get("filter") or "").strip()
        expanded_arg = str(request.args.get("expanded") or "").strip()
        expanded_nodes = [token.strip() for token in expanded_arg.split(",") if token.strip()]
        result = workspace.samras_graph_view(
            instance_id=str(instance_id or "").strip(),
            filter_text=filter_text,
            expanded_nodes=expanded_nodes,
        )
        status = 200 if bool(result.get("ok")) else 400
        return jsonify(result), status

    @app.post("/portal/api/data/anthology/append")
    def portal_data_anthology_append():
        if not hasattr(workspace, "append_anthology_datum"):
            abort(501, description="anthology append is unavailable")
        body = _json_body()
        layer_value = body.get("layer")
        value_group_value = body.get("value_group")
        layer_raw = "" if layer_value is None else str(layer_value).strip()
        value_group_raw = "" if value_group_value is None else str(value_group_value).strip()
        try:
            layer = int(layer_raw)
            value_group = int(value_group_raw)
        except Exception:
            abort(400, description="layer and value_group must be integers")
        pairs_body = body.get("pairs")
        pairs: list[dict[str, str]] | None = None
        if isinstance(pairs_body, list):
            pairs = []
            for item in pairs_body:
                if not isinstance(item, dict):
                    continue
                pairs.append(
                    {
                        "reference": str(item.get("reference") or "").strip(),
                        "magnitude": str(item.get("magnitude") or "").strip(),
                    }
                )
        rule_key = str(body.get("rule_key") or "").strip()
        override = bool(body.get("rule_write_override"))
        ref = str(body.get("reference") or "").strip()
        mag = str(body.get("magnitude") or "").strip()
        label_token = str(body.get("label") or "").strip()
        pair_rows: list[dict[str, str]]
        if pairs:
            pair_rows = list(pairs)
        else:
            pair_rows = [{"reference": ref, "magnitude": mag}]
        base_rows = _canonical_rows_payload()
        probe_id = compute_next_append_datum_id(base_rows, layer, value_group)
        probe_row = build_append_row_dict(
            datum_id=probe_id,
            label=label_token,
            pairs=pair_rows,
            reference=ref,
            magnitude=mag,
        )
        ev = evaluate_probe_write(
            base_rows,
            probe_row_id=probe_id,
            probe_row_dict=probe_row,
            rule_key_hint=rule_key,
            rule_write_override=override,
            pairs_for_hint=pairs,
            value_group_hint=value_group,
        )
        if not bool(ev.get("ok")):
            return jsonify(
                {
                    "ok": False,
                    "error": "datum creation blocked by datum rule policy",
                    "datum_rules_write": ev,
                    "schema": "mycite.portal.datum_rules.append_validation.v1",
                }
            ), 400
        result = workspace.append_anthology_datum(
            layer=layer,
            value_group=value_group,
            reference=str(body.get("reference") or "").strip(),
            magnitude=str(body.get("magnitude") or "").strip(),
            label=str(body.get("label") or "").strip(),
            pairs=pairs,
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "anthology_table_view"):
            response["table_view"] = workspace.anthology_table_view()
        response["datum_rules_write"] = {
            "datum_understanding": ev.get("datum_understanding"),
            "rule_policy": ev.get("rule_policy"),
            "warnings": list(ev.get("warnings") or []),
        }
        response.setdefault("warnings", []).extend(list(ev.get("warnings") or []))
        return jsonify(response), status

    @app.post("/portal/api/data/anthology/delete")
    def portal_data_anthology_delete():
        if not hasattr(workspace, "delete_anthology_datum"):
            abort(501, description="anthology delete is unavailable")
        body = _json_body()
        result = workspace.delete_anthology_datum(
            row_id=str(body.get("row_id") or body.get("identifier") or "").strip(),
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "anthology_table_view"):
            response["table_view"] = workspace.anthology_table_view()
        return jsonify(response), status

    @app.post("/portal/api/data/anthology/label")
    def portal_data_anthology_label():
        if not hasattr(workspace, "update_anthology_label"):
            abort(501, description="anthology label update is unavailable")
        body = _json_body()
        row_token = str(body.get("row_id") or body.get("identifier") or "").strip()
        entry = _canonical_row_entry(row_token)
        if entry is None:
            return jsonify({"ok": False, "errors": [f"Unknown anthology row_id: {row_token}"], "warnings": []}), 400
        row_key, cur = entry
        override = bool(body.get("rule_write_override"))
        updated = build_updated_row_dict(cur, label=str(body.get("label") or ""), pairs=None)
        _, vg_hint, _ = parse_datum_id(row_key)
        ev = evaluate_probe_write(
            _canonical_rows_payload(),
            probe_row_id=row_key,
            probe_row_dict=updated,
            rule_key_hint=str(body.get("rule_key") or "").strip(),
            rule_write_override=override,
            pairs_for_hint=None,
            value_group_hint=vg_hint,
        )
        if not bool(ev.get("ok")):
            return jsonify(
                {
                    "ok": False,
                    "errors": list(ev.get("errors") or ["label update blocked by datum rules"]),
                    "warnings": list(ev.get("warnings") or []),
                    "datum_rules_write": ev,
                }
            ), 400
        result = workspace.update_anthology_label(
            row_id=row_token,
            label=str(body.get("label") or ""),
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "anthology_table_view"):
            response["table_view"] = workspace.anthology_table_view()
        response["datum_rules_write"] = {
            "datum_understanding": ev.get("datum_understanding"),
            "rule_policy": ev.get("rule_policy"),
            "warnings": list(ev.get("warnings") or []),
        }
        response.setdefault("warnings", []).extend(list(ev.get("warnings") or []))
        return jsonify(response), status

    @app.get("/portal/api/data/anthology/profile/<path:row_id>")
    def portal_data_anthology_profile(row_id: str):
        if not hasattr(workspace, "anthology_profile"):
            abort(501, description="anthology profile is unavailable")
        result = workspace.anthology_profile(row_id=str(row_id or "").strip())
        status = 200 if bool(result.get("ok")) else 404
        if bool(result.get("ok")):
            datum = result.get("datum") if isinstance(result.get("datum"), dict) else {}
            ident = str(datum.get("identifier") or datum.get("row_id") or "").strip()
            if ident:
                rr = understand_datums(_canonical_rows_payload())
                u = rr.by_id.get(ident)
                result["datum_understanding"] = u.to_dict() if u else None
                result["rule_policy"] = derive_rule_policy(u).to_dict()
        return jsonify(result), status

    @app.post("/portal/api/data/anthology/profile/update")
    def portal_data_anthology_profile_update():
        if not hasattr(workspace, "update_anthology_profile"):
            abort(501, description="anthology profile update is unavailable")
        body = _json_body()
        pairs_body = body.get("pairs")
        pairs: list[dict[str, str]] | None = None
        if isinstance(pairs_body, list):
            pairs = []
            for item in pairs_body:
                if not isinstance(item, dict):
                    continue
                pairs.append(
                    {
                        "reference": str(item.get("reference") or "").strip(),
                        "magnitude": str(item.get("magnitude") or "").strip(),
                    }
                )
        row_token = str(body.get("row_id") or body.get("identifier") or "").strip()
        entry = _canonical_row_entry(row_token)
        if entry is None:
            return jsonify({"ok": False, "errors": [f"Unknown anthology row_id: {row_token}"], "warnings": []}), 400
        row_key, cur = entry
        override = bool(body.get("rule_write_override"))
        label_token = str(body.get("label") or "")
        magnitude_param = body.get("magnitude")
        if isinstance(pairs_body, list):
            updated = build_updated_row_dict(cur, label=label_token, pairs=pairs)
        elif magnitude_param is not None:
            updated = build_updated_row_dict(cur, label=label_token, pairs=None, magnitude_override=str(magnitude_param))
        else:
            updated = build_updated_row_dict(cur, label=label_token, pairs=None)
        _, vg_hint, _ = parse_datum_id(row_key)
        ev = evaluate_probe_write(
            _canonical_rows_payload(),
            probe_row_id=row_key,
            probe_row_dict=updated,
            rule_key_hint=str(body.get("rule_key") or "").strip(),
            rule_write_override=override,
            pairs_for_hint=pairs,
            value_group_hint=vg_hint,
        )
        if not bool(ev.get("ok")):
            return jsonify(
                {
                    "ok": False,
                    "errors": list(ev.get("errors") or ["profile update blocked by datum rules"]),
                    "warnings": list(ev.get("warnings") or []),
                    "datum_rules_write": ev,
                }
            ), 400
        result = workspace.update_anthology_profile(
            row_id=row_token,
            label=label_token,
            magnitude=body.get("magnitude"),
            pairs=pairs,
            icon_relpath=body.get("icon_relpath"),
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "anthology_table_view"):
            response["table_view"] = workspace.anthology_table_view()
        response["datum_rules_write"] = {
            "datum_understanding": ev.get("datum_understanding"),
            "rule_policy": ev.get("rule_policy"),
            "warnings": list(ev.get("warnings") or []),
        }
        response.setdefault("warnings", []).extend(list(ev.get("warnings") or []))
        return jsonify(response), status

    @app.post("/portal/api/data/directive")
    def portal_data_directive():
        body = _json_body()
        result = workspace.apply_directive(body)
        result["ok"] = not bool(result.get("errors"))
        return jsonify(result)

    @app.post("/portal/api/data/stage_edit")
    def portal_data_stage_edit():
        body = _json_body()
        result = workspace.stage_edit(
            row_id=str(body.get("row_id") or "").strip(),
            field_id=str(body.get("field_id") or "").strip(),
            display_value=str(body.get("display_value") or ""),
            table_id=str(body.get("table_id") or "").strip() or None,
            instance_id=str(body.get("instance_id") or "").strip() or None,
        )
        return jsonify(_state_payload(result))

    @app.post("/portal/api/data/reset_staging")
    def portal_data_reset_staging():
        body = _json_body()
        result = workspace.reset_staging(
            scope=str(body.get("scope") or "all").strip().lower(),
            table_id=str(body.get("table_id") or "").strip() or None,
            row_id=str(body.get("row_id") or "").strip() or None,
        )
        return jsonify(_state_payload(result))

    @app.post("/portal/api/data/commit")
    def portal_data_commit():
        body = _json_body()
        result = workspace.commit(
            scope=str(body.get("scope") or "all").strip().lower(),
            table_id=str(body.get("table_id") or "").strip() or None,
            row_id=str(body.get("row_id") or "").strip() or None,
        )
        return jsonify(_state_payload(result))

    if not include_legacy_shims:
        return

    @app.get("/portal/api/data/tables")
    def portal_data_tables():
        data: dict[str, Any] = {
            "ok": True,
            "tables": workspace.list_tables(),
            "warnings": ["deprecated endpoint: use /portal/api/data/state and /portal/api/data/directive"],
        }
        msn_id = _msn_id()
        if options_private_fn is not None and msn_id:
            data["options_private"] = options_private_fn(msn_id)
        return jsonify(data)

    @app.get("/portal/api/data/table/<table_id>/instances")
    def portal_data_instances(table_id: str):
        if table_id not in _known_table_ids():
            abort(404, description=f"Unknown table_id: {table_id}")
        return jsonify(
            {
                "ok": True,
                "table_id": table_id,
                "instances": workspace.list_instances(table_id),
                "warnings": ["deprecated endpoint"],
            }
        )

    @app.get("/portal/api/data/table/<table_id>/view")
    def portal_data_view(table_id: str):
        if table_id not in _known_table_ids():
            abort(404, description=f"Unknown table_id: {table_id}")
        instance_id = (request.args.get("instance") or "").strip() or None
        mode = (request.args.get("mode") or "general").strip().lower()
        view = workspace.get_view(table_id, instance_id=instance_id, mode=mode)
        return jsonify({"ok": True, "view": view, "warnings": ["deprecated endpoint"]})

    @app.post("/portal/api/data/revert_edit")
    def portal_data_revert_edit():
        body = _json_body()
        result = workspace.revert_edit(
            table_id=str(body.get("table_id") or "").strip(),
            row_id=str(body.get("row_id") or "").strip(),
            field_id=str(body.get("field_id") or "").strip(),
        )
        payload = _state_payload(result)
        payload.setdefault("warnings", []).append("deprecated endpoint")
        return jsonify(payload)

    @app.post("/portal/api/data/reset")
    def portal_data_reset():
        body = _json_body()
        scope = str(body.get("scope") or "all").strip().lower()
        table_id = str(body.get("table_id") or "").strip() or None
        row_id = str(body.get("row_id") or "").strip() or None
        result = workspace.reset_staging(scope=scope, table_id=table_id, row_id=row_id)
        payload = _state_payload(result)
        payload.setdefault("warnings", []).append("deprecated endpoint")
        return jsonify(payload)
