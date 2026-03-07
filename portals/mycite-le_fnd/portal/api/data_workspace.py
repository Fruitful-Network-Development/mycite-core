from __future__ import annotations

from typing import Any, Callable, Optional

from flask import abort, jsonify, redirect, request


def register_data_routes(
    app,
    *,
    workspace,
    aliases_provider: Callable[[], list[dict]] | None = None,
    options_private_fn: Optional[Callable[[str], dict[str, Any]]] = None,
    msn_id_provider: Optional[Callable[[], str]] = None,
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
            "errors": list(result.get("errors") or []),
            "warnings": list(result.get("warnings") or []),
        }

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

    @app.get("/portal/api/data/anthology/table")
    def portal_data_anthology_table():
        if not hasattr(workspace, "anthology_table_view"):
            abort(501, description="anthology table view is unavailable")
        payload = workspace.anthology_table_view()
        payload["ok"] = True
        return jsonify(payload)

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
        result = workspace.time_series_delete_event(
            event_ref=str(body.get("event_ref") or "").strip(),
        )
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
