from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
    WORKBENCH_UI_TOOL_SURFACE_SCHEMA,
    attach_region_family_contract,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.state_machine.portal_shell import (
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
    WORKBENCH_UI_TOOL_ROUTE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    build_canonical_url,
    build_portal_shell_request_payload,
    canonical_query_for_runtime_request_payload,
    canonical_query_for_surface_query,
    normalize_runtime_surface_request_payload,
)
from MyCiteV2.packages.tools.workbench_ui import WorkbenchUiReadService

def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_or_none(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def _workbench_sql_runtime_error(*, portal_instance_id: str, authority_db_file: str | Path | None) -> dict[str, str] | None:
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return {
            "code": "sql_authority_required",
            "message": "The MOS SQL authority database is required for the workbench UI surface.",
        }
    datum_store = SqliteSystemDatumStoreAdapter(authority_path)
    if not datum_store.has_authoritative_catalog(portal_instance_id) or not datum_store.has_system_workbench(portal_instance_id):
        return {
            "code": "sql_authority_uninitialized",
            "message": "The MOS SQL authority database is not initialized for the requested tenant.",
        }
    return None


def _normalize_request(payload: dict[str, Any] | None) -> tuple[PortalScope, dict[str, str]]:
    portal_scope, _, surface_query = normalize_runtime_surface_request_payload(
        payload,
        expected_schema=WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
        legacy_query_keys=(
            "document",
            "document_filter",
            "document_sort",
            "document_dir",
            "filter",
            "sort",
            "dir",
            "group",
            "workbench_lens",
            "source",
            "overlay",
            "row",
        ),
    )
    return portal_scope, surface_query


def _surface_query(base_query: dict[str, Any], **updates: object) -> dict[str, str]:
    merged = dict(base_query)
    for key, value in updates.items():
        token = _as_text(value)
        if token:
            merged[key] = token
        else:
            merged.pop(key, None)
    return canonical_query_for_surface_query(merged, surface_id=WORKBENCH_UI_TOOL_SURFACE_ID)


def _surface_request(*, portal_scope: PortalScope, surface_query: dict[str, str]) -> dict[str, Any]:
    return {
        "href": build_canonical_url(surface_id=WORKBENCH_UI_TOOL_SURFACE_ID, query=surface_query),
        "shell_request": build_portal_shell_request_payload(
            requested_surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            portal_scope=portal_scope,
            surface_query=surface_query,
        ),
    }


def _control_entry(
    *,
    label: str,
    portal_scope: PortalScope,
    surface_query: dict[str, Any],
    active: bool = False,
    meta: object = "",
) -> dict[str, Any]:
    request = _surface_request(portal_scope=portal_scope, surface_query=dict(surface_query))
    return {
        "label": label,
        "href": request["href"],
        "active": active,
        "meta": _as_text(meta),
        "shell_request": request["shell_request"],
    }


def _decorate_workspace_navigation(
    *,
    portal_scope: PortalScope,
    base_query: dict[str, str],
    model: dict[str, Any],
) -> None:
    surface_payload = model.get("surface_payload")
    if not isinstance(surface_payload, dict):
        return
    workspace = surface_payload.get("workspace")
    if not isinstance(workspace, dict):
        return

    document_table = workspace.get("document_table")
    if isinstance(document_table, dict):
        for document in list(document_table.get("rows") or []):
            document_query = _surface_query(
                base_query,
                document=document.get("document_id"),
                row="",
            )
            document.update(_surface_request(portal_scope=portal_scope, surface_query=document_query))

    datum_grid = workspace.get("datum_grid")
    if isinstance(datum_grid, dict):
        for row in list(datum_grid.get("rows") or []):
            row_query = _surface_query(base_query, row=row.get("datum_address"))
            row.update(_surface_request(portal_scope=portal_scope, surface_query=row_query))
        for group in list(datum_grid.get("groups") or []):
            for row in list((group or {}).get("items") or []):
                row_query = _surface_query(base_query, row=row.get("datum_address"))
                row.update(_surface_request(portal_scope=portal_scope, surface_query=row_query))

    navigation = workspace.get("navigation")
    if isinstance(navigation, dict):
        for key, item in list(navigation.items()):
            if not isinstance(item, dict):
                continue
            if "document" in key:
                item_query = _surface_query(base_query, document=item.get("id"), row="")
            else:
                item_query = _surface_query(base_query, row=item.get("id"))
            item.update(_surface_request(portal_scope=portal_scope, surface_query=item_query))


def build_portal_workbench_ui_surface_bundle(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    shell_state: object | None,
    authority_db_file: str | Path | None,
    tool_rows: list[dict[str, Any]] | None = None,
    surface_query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del shell_state, tool_rows
    runtime_error = _workbench_sql_runtime_error(
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
    )
    model = {
        "surface_payload": {
            "schema": WORKBENCH_UI_TOOL_SURFACE_SCHEMA,
            "kind": "workbench_ui_surface",
            "title": "Workbench UI",
            "subtitle": "Read-only two-pane SQL-backed spreadsheet.",
            "sections": [],
            "notes": ["The SQL authority database is required for this surface."],
        },
        "document_rows": [],
        "document_id": "",
        "document_name": "",
        "document_filter": "",
        "document_sort_key": "version_hash",
        "document_sort_direction": "asc",
        "document_version_hash": "",
        "document_version_hash_short": "",
        "sort_key": "datum_address",
        "sort_direction": "asc",
        "text_filter": "",
        "group_mode": "flat",
        "workbench_lens": "interpreted",
        "source_visibility": "show",
        "overlay_visibility": "show",
        "selected_row": {},
        "selected_row_hyphae_hash_short": "",
        "navigation": {},
        "inspector_sections": [],
    }
    authority_path = _path_or_none(authority_db_file)
    if authority_path is not None and runtime_error is None:
        model = WorkbenchUiReadService(authority_path).read_surface(
            portal_instance_id=portal_scope.scope_id,
            portal_domain=portal_domain,
            surface_query=surface_query,
        )
        model["surface_payload"]["schema"] = WORKBENCH_UI_TOOL_SURFACE_SCHEMA
        model["surface_payload"]["request_contract"] = {
            "schema": WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
            "route": WORKBENCH_UI_TOOL_ROUTE,
            "surface_id": WORKBENCH_UI_TOOL_SURFACE_ID,
        }

    workspace_query = (
        ((model.get("surface_payload") or {}).get("workspace") or {}).get("query")
        if isinstance(model.get("surface_payload"), dict)
        else {}
    )
    active_query = canonical_query_for_surface_query(
        workspace_query or surface_query,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
    )
    _decorate_workspace_navigation(portal_scope=portal_scope, base_query=active_query, model=model)

    navigation = model.get("navigation") or {}
    navigation_entries = []
    for key, label in (
        ("previous_document", "previous document"),
        ("next_document", "next document"),
        ("previous_row", "previous row"),
        ("next_row", "next row"),
    ):
        item = navigation.get(key)
        if not isinstance(item, dict):
            continue
        navigation_entries.append(
            {
                "label": label,
                "href": item.get("href", "#"),
                "shell_request": item.get("shell_request"),
                "meta": _as_text(item.get("label")) or _as_text(item.get("id")) or "—",
            }
        )

    control_panel = attach_region_family_contract(
        {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "WORKBENCH UI",
        "context_items": [
            {"label": "Document", "value": _as_text(model.get("document_id")) or "—"},
            {"label": "Version", "value": _as_text(model.get("document_version_hash_short")) or "—"},
            {"label": "Selected Row", "value": _as_text((model.get("selected_row") or {}).get("datum_address")) or "—"},
            {"label": "Row Identity", "value": _as_text(model.get("selected_row_hyphae_hash_short")) or "—"},
            {"label": "Resolved Lens", "value": _as_text((model.get("selected_row") or {}).get("resolved_lens")) or "—"},
            {
                "label": "Document Sort",
                "value": (
                    f"{_as_text(model.get('document_sort_key')) or 'version_hash'}:"
                    f"{_as_text(model.get('document_sort_direction')) or 'asc'}"
                ),
            },
            {
                "label": "Row Sort",
                "value": f"{_as_text(model.get('sort_key')) or 'datum_address'}:{_as_text(model.get('sort_direction')) or 'asc'}",
            },
            {"label": "Grouping", "value": _as_text(model.get("group_mode")) or "flat"},
            {"label": "Lens", "value": _as_text(model.get("workbench_lens")) or "interpreted"},
            {"label": "Source", "value": _as_text(model.get("source_visibility")) or "show"},
            {"label": "Overlay", "value": _as_text(model.get("overlay_visibility")) or "show"},
        ],
        "verb_tabs": [],
        "groups": [
            {
                "title": "Documents",
                "entries": [
                    {
                        "label": _as_text(document.get("label")) or _as_text(document.get("document_id")) or "Document",
                        "href": document.get("href", "#"),
                        "shell_request": document.get("shell_request"),
                        "active": bool(document.get("selected")),
                        "meta": (
                            f"{_as_text(document.get('source_kind')) or '—'} · "
                            f"{_as_text(document.get('version_hash_short')) or '—'} · "
                            f"{document.get('row_count') or 0}"
                        ),
                    }
                    for document in list(model.get("document_rows") or [])
                ],
            },
            {
                "title": "Document Sorting",
                "entries": [
                    _control_entry(
                        label=f"sort {sort_key}",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, document_sort=sort_key),
                        active=_as_text(model.get("document_sort_key")) == sort_key,
                    )
                    for sort_key in ("version_hash", "document_name", "document_id", "row_count", "source_kind")
                ],
            },
            {
                "title": "Document Direction",
                "entries": [
                    _control_entry(
                        label="asc",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, document_dir="asc"),
                        active=_as_text(model.get("document_sort_direction")) != "desc",
                    ),
                    _control_entry(
                        label="desc",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, document_dir="desc"),
                        active=_as_text(model.get("document_sort_direction")) == "desc",
                    ),
                ],
            },
            {
                "title": "Row Sorting",
                "entries": [
                    _control_entry(
                        label=f"sort {sort_key}",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, sort=sort_key),
                        active=_as_text(model.get("sort_key")) == sort_key,
                    )
                    for sort_key in ("datum_address", "layer", "value_group", "iteration", "labels", "relation", "object_ref", "hyphae_hash")
                ],
            },
            {
                "title": "Row Direction",
                "entries": [
                    _control_entry(
                        label="asc",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, dir="asc"),
                        active=_as_text(model.get("sort_direction")) != "desc",
                    ),
                    _control_entry(
                        label="desc",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, dir="desc"),
                        active=_as_text(model.get("sort_direction")) == "desc",
                    ),
                ],
            },
            {
                "title": "Grouping",
                "entries": [
                    _control_entry(
                        label=group_mode.replace("_", " "),
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, group=group_mode),
                        active=_as_text(model.get("group_mode")) == group_mode,
                    )
                    for group_mode in ("flat", "layer", "layer_value_group", "layer_value_group_iteration")
                ],
            },
            {
                "title": "Workbench Lens",
                "entries": [
                    _control_entry(
                        label=lens,
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, workbench_lens=lens),
                        active=_as_text(model.get("workbench_lens")) == lens,
                    )
                    for lens in ("interpreted", "raw")
                ],
            },
            {
                "title": "Source Visibility",
                "entries": [
                    _control_entry(
                        label="show source",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, source="show"),
                        active=_as_text(model.get("source_visibility")) != "hide",
                    ),
                    _control_entry(
                        label="hide source",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, source="hide"),
                        active=_as_text(model.get("source_visibility")) == "hide",
                    ),
                ],
            },
            {
                "title": "Overlay",
                "entries": [
                    _control_entry(
                        label="show overlay",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, overlay="show"),
                        active=_as_text(model.get("overlay_visibility")) != "hide",
                    ),
                    _control_entry(
                        label="hide overlay",
                        portal_scope=portal_scope,
                        surface_query=_surface_query(active_query, overlay="hide"),
                        active=_as_text(model.get("overlay_visibility")) == "hide",
                    ),
                ],
            },
            {
                "title": "Navigation",
                "entries": navigation_entries,
            },
        ],
        "actions": [],
        },
        family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
    )
    workbench = attach_region_family_contract(
        {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "surface_payload",
        "title": "Workbench UI",
        "subtitle": "Read-only two-pane SQL-backed spreadsheet.",
        "visible": True,
        "surface_payload": model["surface_payload"],
        },
        family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
    )
    inspector = attach_region_family_contract(
        {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": "Selection",
        "summary": "Selected document/version metadata, row semantics, and additive directive overlays.",
        "visible": True,
        "subject": {
            "level": "datum",
            "id": _as_text((model.get("selected_row") or {}).get("datum_address")) or _as_text(model.get("document_id")),
        },
        "sections": list(model.get("inspector_sections") or []),
        },
        family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
    )
    return {
        "entrypoint_id": WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": "Workbench UI",
        "page_subtitle": "Read-only two-pane SQL-backed spreadsheet.",
        "canonical_query": active_query,
        "surface_payload": model["surface_payload"],
        "control_panel": control_panel,
        "workbench": workbench,
        "inspector": inspector,
        "route": WORKBENCH_UI_TOOL_ROUTE,
    }


def run_portal_workbench_ui(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    portal_domain: str,
    authority_db_file: str | Path | None,
) -> dict[str, Any]:
    portal_scope, surface_query = _normalize_request(request_payload)
    if not portal_scope.scope_id:
        portal_scope = PortalScope(scope_id=portal_instance_id, capabilities=())
    shell_request = {
        "schema": "mycite.v2.portal.shell.request.v1",
        "requested_surface_id": WORKBENCH_UI_TOOL_SURFACE_ID,
        "portal_scope": portal_scope.to_dict(),
        "surface_query": surface_query,
    }
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        authority_db_file=authority_db_file,
    )


__all__ = [
    "build_portal_workbench_ui_surface_bundle",
    "run_portal_workbench_ui",
]
