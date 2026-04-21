from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
    WORKBENCH_UI_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
)
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
    canonical_query_for_surface_query,
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


def _normalize_request(payload: dict[str, Any] | None) -> tuple[PortalScope, dict[str, str]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    if normalized_payload.get("schema") in {None, ""}:
        normalized_payload = {"schema": WORKBENCH_UI_TOOL_REQUEST_SCHEMA, **normalized_payload}
    if _as_text(normalized_payload.get("schema")) != WORKBENCH_UI_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {WORKBENCH_UI_TOOL_REQUEST_SCHEMA}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    surface_query = canonical_query_for_surface_query(
        normalized_payload.get("surface_query"),
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
    )
    return portal_scope, surface_query


def _control_entry(
    *,
    label: str,
    portal_scope: PortalScope,
    surface_query: dict[str, Any],
    active: bool = False,
    meta: object = "",
) -> dict[str, Any]:
    return {
        "label": label,
        "href": build_canonical_url(surface_id=WORKBENCH_UI_TOOL_SURFACE_ID, query=surface_query),
        "active": active,
        "meta": _as_text(meta),
        "shell_request": build_portal_shell_request_payload(
            requested_surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            portal_scope=portal_scope,
            surface_query=surface_query,
        ),
    }


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
    authority_path = _path_or_none(authority_db_file)
    model = {
        "surface_payload": {
            "schema": WORKBENCH_UI_TOOL_SURFACE_SCHEMA,
            "kind": "workbench_ui_surface",
            "title": "Workbench UI",
            "subtitle": "Read-only SQL-backed datum grid.",
            "sections": [],
            "notes": ["The SQL authority database is required for this surface."],
        },
        "document_rows": [],
        "document_id": "",
        "document_version_hash": "",
        "sort_key": "datum_address",
        "sort_direction": "asc",
        "text_filter": "",
        "overlay_visibility": "show",
        "inspector_sections": [],
    }
    if authority_path is not None:
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

    active_query = dict(surface_query or {})
    control_panel = {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "WORKBENCH UI",
        "context_items": [
            {"label": "Document", "value": _as_text(model.get("document_id")) or "—"},
            {"label": "Version", "value": _as_text(model.get("document_version_hash")) or "—"},
            {"label": "Filter", "value": _as_text(model.get("text_filter")) or "—"},
            {
                "label": "Sort",
                "value": f"{_as_text(model.get('sort_key')) or 'datum_address'}:{_as_text(model.get('sort_direction')) or 'asc'}",
            },
        ],
        "verb_tabs": [],
        "groups": [
            {
                "title": "Documents",
                "entries": [
                    _control_entry(
                        label=_as_text(document.get("label")) or _as_text(document.get("document_id")) or "Document",
                        portal_scope=portal_scope,
                        surface_query={**active_query, "document": document.get("document_id", "")},
                        active=bool(document.get("selected")),
                        meta=f"{_as_text(document.get('source_kind'))} · {document.get('row_count')}",
                    )
                    for document in list(model.get("document_rows") or [])
                ],
            },
            {
                "title": "Sorting",
                "entries": [
                    _control_entry(
                        label=f"sort {sort_key}",
                        portal_scope=portal_scope,
                        surface_query={**active_query, "sort": sort_key},
                        active=_as_text(model.get("sort_key")) == sort_key,
                    )
                    for sort_key in ("datum_address", "layer", "value_group", "iteration", "hyphae_hash")
                ],
            },
            {
                "title": "Overlay",
                "entries": [
                    _control_entry(
                        label="show overlay",
                        portal_scope=portal_scope,
                        surface_query={**active_query, "overlay": "show"},
                        active=_as_text(model.get("overlay_visibility")) != "hide",
                    ),
                    _control_entry(
                        label="hide overlay",
                        portal_scope=portal_scope,
                        surface_query={**active_query, "overlay": "hide"},
                        active=_as_text(model.get("overlay_visibility")) == "hide",
                    ),
                ],
            },
        ],
        "actions": [],
    }
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "surface_payload",
        "title": "Workbench UI",
        "subtitle": "Read-only SQL-backed datum grid.",
        "visible": True,
        "surface_payload": model["surface_payload"],
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": "Selection",
        "summary": "Selected row semantics and additive directive overlays.",
        "visible": True,
        "subject": {"level": "datum", "id": _as_text(active_query.get("row")) or _as_text(model.get("document_id"))},
        "sections": list(model.get("inspector_sections") or []),
    }
    return {
        "entrypoint_id": WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": "Workbench UI",
        "page_subtitle": "Read-only SQL-backed datum grid.",
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
    bundle = build_portal_workbench_ui_surface_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=None,
        authority_db_file=authority_db_file,
        surface_query=surface_query,
    )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=False,
        canonical_route=bundle["route"],
        canonical_query=surface_query,
        canonical_url=build_canonical_url(surface_id=WORKBENCH_UI_TOOL_SURFACE_ID, query=surface_query),
        shell_state={},
        surface_payload=bundle["surface_payload"],
        shell_composition={},
        warnings=[],
        error=None if authority_db_file is not None else {
            "code": "sql_authority_required",
            "message": "The MOS SQL authority database is required for the workbench UI surface.",
        },
    )


__all__ = [
    "build_portal_workbench_ui_surface_bundle",
    "run_portal_workbench_ui",
]
