from __future__ import annotations

from typing import Any, Callable

from flask import abort, jsonify, redirect, request
from _shared.portal.data_engine.field_contracts import default_profile_field_contracts
from _shared.portal.data_engine.write_pipeline import apply_write_preview, preview_write_intent


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

    def _external_plan_for_intent(payload: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
        if external_resource_resolver is None or anthology_payload_provider is None:
            return True, {"ok": True, "ordered_writes": []}, ""
        try:
            plan = external_resource_resolver.plan_materialization(
                source_msn_id=str(payload.get("source_msn_id") or "").strip(),
                resource_id=str(payload.get("resource_id") or "").strip(),
                target_ref=str(payload.get("target_ref") or "").strip(),
                required_refs=[str(item or "").strip() for item in list(payload.get("required_refs") or [])],
                anthology_payload=anthology_payload_provider() or {},
                allow_auto_create=bool(payload.get("allow_auto_create", False)),
            )
            out = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
            return bool(out.get("ok")), out, str(out.get("error") or "")
        except Exception as exc:
            return False, {}, str(exc)

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
        preview = preview_write_intent(
            intent=intent if isinstance(intent, dict) else {},
            current_config=_load_active_config(),
            external_plan_fn=_external_plan_for_intent,
        )
        payload = preview.to_dict()
        payload["schema"] = "mycite.portal.write.preview.v1"
        return jsonify(payload), (200 if preview.ok else 400)

    @app.post("/portal/api/data/write/apply")
    def portal_data_write_apply():
        body = _json_body()
        intent = body.get("intent") if isinstance(body.get("intent"), dict) else {}
        if body.get("preview") and isinstance(body.get("preview"), dict):
            preview_payload = dict(body.get("preview"))
            preview_payload.pop("schema", None)
            preview = preview_write_intent(
                intent=preview_payload.get("intent") if isinstance(preview_payload.get("intent"), dict) else {},
                current_config=_load_active_config(),
                external_plan_fn=_external_plan_for_intent,
            )
        else:
            preview = preview_write_intent(
                intent=intent,
                current_config=_load_active_config(),
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
        preview = preview_write_intent(
            intent=intent,
            current_config=_load_active_config(),
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
        preview = preview_write_intent(
            intent=intent,
            current_config=_load_active_config(),
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
        return jsonify(payload)

    @app.get("/portal/api/data/anthology/graph")
    def portal_data_anthology_graph():
        if not hasattr(workspace, "anthology_graph_view"):
            abort(501, description="anthology graph view is unavailable")
        focus = str(request.args.get("focus") or "").strip()
        layout = str(request.args.get("layout") or "linear").strip().lower()
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
        result = workspace.update_anthology_label(
            row_id=str(body.get("row_id") or body.get("identifier") or "").strip(),
            label=str(body.get("label") or ""),
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "anthology_table_view"):
            response["table_view"] = workspace.anthology_table_view()
        return jsonify(response), status

    @app.get("/portal/api/data/anthology/profile/<path:row_id>")
    def portal_data_anthology_profile(row_id: str):
        if not hasattr(workspace, "anthology_profile"):
            abort(501, description="anthology profile is unavailable")
        result = workspace.anthology_profile(row_id=str(row_id or "").strip())
        status = 200 if bool(result.get("ok")) else 404
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
        result = workspace.update_anthology_profile(
            row_id=str(body.get("row_id") or body.get("identifier") or "").strip(),
            label=str(body.get("label") or ""),
            magnitude=body.get("magnitude"),
            pairs=pairs,
            icon_relpath=body.get("icon_relpath"),
        )
        status = 200 if bool(result.get("ok")) else 400
        response = dict(result)
        if hasattr(workspace, "anthology_table_view"):
            response["table_view"] = workspace.anthology_table_view()
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
