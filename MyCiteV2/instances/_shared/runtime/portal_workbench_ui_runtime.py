from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
    build_unified_control_panel,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
    WORKBENCH_UI_TOOL_SURFACE_SCHEMA,
    attach_region_family_contract,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_templates import TemplateRegistry
from MyCiteV2.packages.state_machine.portal_shell import (
    AGRO_ERP_SANDBOX_TOKEN,
    PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    WORKBENCH_UI_SANDBOX_TOKEN,
    WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
    WORKBENCH_UI_TOOL_ROUTE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    PortalScope,
    build_canonical_url,
    build_portal_shell_request_payload,
    canonical_query_for_surface_query,
    normalize_runtime_surface_request_payload,
    sandbox_display_name,
)
from MyCiteV2.packages.tools.workbench_ui import WorkbenchUiReadService

_log = logging.getLogger("mycite.portal_host")

# MSN id used when scaffolding new documents. Every sandbox is writable;
# this map holds the canonical default MSN per sandbox so the new-document
# form can pre-fill it. The FND tenant's canonical MSN is reused for
# sandboxes that don't register their own.
_SANDBOX_DEFAULT_MSN: dict[str, str] = {
    AGRO_ERP_SANDBOX_TOKEN: "3-2-3-17-77-1-6-4-1-4",
}
_FND_DEFAULT_MSN = "3-2-3-17-77-1-6-4-1-4"


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
            "mode",
            "sandbox_filter",
            "tool",
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


def _resolve_sandbox(
    *,
    sandbox: str | None,
    surface_query: dict[str, Any] | None,
    shell_state: object | None,
) -> str:
    """Resolve the effective sandbox the workbench is being opened against.

    Priority: explicit kwarg > surface_query["sandbox_filter"] >
    shell_state focus_path sandbox segment > WORKBENCH_UI_SANDBOX_TOKEN
    ("system" — the reflective corpus-wide view).
    """
    token = _as_text(sandbox)
    if token:
        return token
    if isinstance(surface_query, dict):
        filter_token = _as_text(surface_query.get("sandbox_filter"))
        if filter_token:
            return filter_token
    focus_path = getattr(shell_state, "focus_path", None) if shell_state is not None else None
    if focus_path:
        first = focus_path[0] if isinstance(focus_path, (list, tuple)) and focus_path else None
        candidate = _as_text(getattr(first, "id", None))
        if candidate:
            return candidate
    return WORKBENCH_UI_SANDBOX_TOKEN


def _is_document_in_sandbox(document_row: dict[str, Any], sandbox: str) -> bool:
    """Match a workbench document_row against a sandbox token.

    Documents follow the canonical id pattern
    ``lv.<MSN>.<sandbox>.<name>.<hash>``, so a token match against the
    dot-bounded substring is decisive. Falls back to
    ``document_metadata.sandbox`` when the canonical id is missing.
    """
    if not sandbox:
        return True
    document_id = str(document_row.get("document_id") or "")
    if f".{sandbox}." in document_id:
        return True
    metadata = document_row.get("document_metadata") or {}
    if isinstance(metadata, dict) and metadata.get("sandbox") == sandbox:
        return True
    return False


def _available_templates_for_sandbox(sandbox: str) -> list[dict[str, str]]:
    """Templates whose ``sandbox`` matches the given token.

    Drives the template-picker in the ``new_source_document_form`` slot.
    Lazy-loads the registry so a missing template dir doesn't crash the
    surface; reports an empty list and the renderer hides the form.
    """
    if not sandbox:
        return []
    try:
        registry = TemplateRegistry()
        templates = [t for t in registry.all() if t.sandbox == sandbox]
    except Exception:
        _log.warning("workbench_template_registry_load_failed", exc_info=True)
        return []
    out: list[dict[str, str]] = []
    for template in templates:
        out.append(
            {
                "template_id": template.template_id,
                "label": template.template_id.replace("_", " ").title(),
                "description": template.description or "",
                "archetype": template.archetype,
            }
        )
    return out


def _build_new_source_document_form(*, sandbox: str) -> dict[str, Any]:
    """Build the create-source-document form slot. Every sandbox is writable."""
    templates = _available_templates_for_sandbox(sandbox)
    return {
        "schema": "mycite.v2.portal.workbench.new_source_document_form.v1",
        "sandbox_id": sandbox,
        "msn_id_default": _SANDBOX_DEFAULT_MSN.get(sandbox, _FND_DEFAULT_MSN),
        "available_templates": templates,
        "name_input": {
            "field": "document_name",
            "label": "Document name",
            "placeholder": "e.g. product_profiles",
            "pattern": "^[a-z][a-z0-9_]*$",
            "max_length": 64,
            "required": True,
        },
        "operation": "scaffold_datum",
        "target_authority": "datum_workbench",
        "endpoint_stage": "/portal/api/v2/mutations/stage",
        "endpoint_preview": "/portal/api/v2/mutations/preview",
        "endpoint_apply": "/portal/api/v2/mutations/apply",
    }


def _build_new_datum_form(
    *,
    sandbox: str,
    selected_document_id: str,
) -> dict[str, Any]:
    """Build the insert-datum form slot. Every sandbox is writable.

    The renderer uses the `composer` block below to render an always-open
    structured compose bar (tuple mode + reference-list mode) in the
    editor header. The `raw_payload_textarea` block is retained as the
    advanced/fallback path.
    """
    return {
        "schema": "mycite.v2.portal.workbench.new_datum_form.v1",
        "sandbox_id": sandbox,
        "document_id_default": selected_document_id,
        "raw_payload_textarea": {
            "label": "Datum row (YAML 4-tuple)",
            "placeholder": (
                "[[<self-addr>, \"rf.3-1-1\", <node_address>, "
                "\"rf.3-1-2\", <title_binary>], [<title_ascii>]]"
            ),
            "required": True,
        },
        "composer": {
            "modes": ["tuple", "reference_list"],
            "default_mode": "tuple",
            "default_relation_for_reference_list": "~",
            "value_group_zero_layer_default": 0,
            "value_group_zero_group_default": 0,
            "address_pattern": r"^\d+-\d+-\d+$",
        },
        "target_authority": "datum_workbench",
        "endpoint_stage": "/portal/api/v2/mutations/stage",
        "endpoint_preview": "/portal/api/v2/mutations/preview",
        "endpoint_apply": "/portal/api/v2/mutations/apply",
        "operation": "insert_datum",
    }


def build_portal_workbench_ui_bundle(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    shell_state: object | None,
    authority_db_file: str | Path | None,
    tool_rows: list[dict[str, Any]] | None = None,
    surface_query: dict[str, Any] | None = None,
    sandbox: str | None = None,
) -> dict[str, Any]:
    del tool_rows
    effective_sandbox = _resolve_sandbox(
        sandbox=sandbox,
        surface_query=surface_query,
        shell_state=shell_state,
    )
    sandbox_label = sandbox_display_name(effective_sandbox)
    runtime_error = _workbench_sql_runtime_error(
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
    )
    model = {
        "surface_payload": {
            "schema": WORKBENCH_UI_TOOL_SURFACE_SCHEMA,
            "kind": "sql_authority_lens",
            "title": "Workbench UI",
            "subtitle": "Reflective view of the SQL authority lens state.",
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
        "interface_panel_sections": [],
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

    workbench_ui_extensions = {
        "workbench_ui_document_filter": _as_text(model.get("document_filter")),
        "workbench_ui_lens": _as_text(model.get("workbench_lens")) or "interpreted",
    }

    # --- Three-mode control panel composition --------------------------------
    # The workbench has exactly three user-visible modes per the
    # simplification doctrine: Docs (browse documents), Datums (browse
    # rows in the selected document), Author (create new docs/rows —
    # only when the sandbox is writable). The control-panel emits only
    # the navigation groups relevant to the active mode, with the
    # noisier toggles (sorting, grouping, lens, visibility) tucked into
    # collapsed disclosure groups.
    selected_row_address = _as_text((model.get("selected_row") or {}).get("datum_address"))
    selected_document_id = _as_text(model.get("document_id"))

    requested_mode = _as_text((surface_query or {}).get("mode")).lower() if isinstance(surface_query, dict) else ""
    explicit_document_query = bool(
        isinstance(surface_query, dict) and _as_text(surface_query.get("document"))
    )
    if requested_mode == "author":
        active_mode = "author"
    elif requested_mode == "datums" and selected_document_id:
        active_mode = "datums"
    elif requested_mode == "docs":
        active_mode = "docs"
    elif explicit_document_query and selected_document_id:
        # Only land in Datums mode when the user actively asked for a
        # document (URL ?document=…). Auto-selected defaults from the
        # read service stay in Docs mode so the user lands on the list.
        active_mode = "datums"
    else:
        active_mode = "docs"

    # Filter the document list by the effective sandbox here so the
    # control-panel "Documents" nav group matches the workbench region's
    # document_collection. Without this the panel would advertise every
    # document in the catalog even when the user has chosen a specific
    # sandbox. The system sandbox is the reflective corpus-wide view
    # and shows everything.
    _all_document_rows = list(model.get("document_rows") or [])
    if effective_sandbox == WORKBENCH_UI_SANDBOX_TOKEN:
        _scoped_document_rows = _all_document_rows
    else:
        _scoped_document_rows = [
            doc for doc in _all_document_rows
            if _is_document_in_sandbox(doc, effective_sandbox)
        ]
    document_entries = [
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
        for document in _scoped_document_rows
    ]

    document_sort_group = {
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
    }
    document_direction_group = {
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
    }
    row_sort_group = {
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
    }
    row_direction_group = {
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
    }
    grouping_group = {
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
    }
    lens_group = {
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
    }
    source_visibility_group = {
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
    }
    overlay_group = {
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
    }
    row_navigation_group = {
        "title": "Navigation",
        "entries": navigation_entries,
    }

    # Mode-tab entries (always emitted so the renderer can show a slim
    # mode strip; entries marked `available=false` are styled disabled
    # rather than hidden so the user still sees the affordance exists).
    mode_tabs = [
        {
            "mode": "docs",
            "label": "Docs",
            "active": active_mode == "docs",
            "available": True,
            "href": _surface_request(
                portal_scope=portal_scope,
                surface_query=_surface_query(active_query, mode="docs", row=""),
            )["href"],
            "shell_request": _surface_request(
                portal_scope=portal_scope,
                surface_query=_surface_query(active_query, mode="docs", row=""),
            )["shell_request"],
        },
        {
            "mode": "datums",
            "label": "Datums",
            "active": active_mode == "datums",
            "available": bool(selected_document_id),
            "href": _surface_request(
                portal_scope=portal_scope,
                surface_query=_surface_query(active_query, mode="datums"),
            )["href"],
            "shell_request": _surface_request(
                portal_scope=portal_scope,
                surface_query=_surface_query(active_query, mode="datums"),
            )["shell_request"],
        },
        {
            "mode": "author",
            "label": "Author",
            "active": active_mode == "author",
            "available": True,
            "href": _surface_request(
                portal_scope=portal_scope,
                surface_query=_surface_query(active_query, mode="author"),
            )["href"],
            "shell_request": _surface_request(
                portal_scope=portal_scope,
                surface_query=_surface_query(active_query, mode="author"),
            )["shell_request"],
        },
    ]
    # Author forms (lifted onto the control panel so the renderer can
    # surface them inline under Author mode without needing the modal
    # wiring we deferred to Phase 5). Every sandbox is writable; the
    # forms are always emitted.
    author_forms_payload: dict[str, Any] = {
        "new_source_document": _build_new_source_document_form(sandbox=effective_sandbox),
        "new_datum": _build_new_datum_form(
            sandbox=effective_sandbox,
            selected_document_id=selected_document_id,
        ),
    }

    workbench_mode_payload = {
        "active": active_mode,
        "tabs": mode_tabs,
        "sandbox_id": effective_sandbox,
        "sandbox_label": sandbox_label,
        "writable": True,
        "author_forms": author_forms_payload,
    }

    # Compose the mode-specific groups. Documents list is always shown
    # in Docs mode and stays available as a smaller "Switch document"
    # group inside Datums mode (the user otherwise loses navigation).
    if active_mode == "docs":
        docs_nav_groups: list[dict[str, Any]] = []
        # Every sandbox is writable; prepend the "+ New document" entry
        # so users browsing the Docs view always see the create affordance.
        author_request = _surface_request(
            portal_scope=portal_scope,
            surface_query=_surface_query(active_query, mode="author"),
        )
        docs_nav_groups.append({
            "title": "Create",
            "entries": [{
                "label": "+ New document",
                "href": author_request["href"],
                "shell_request": author_request["shell_request"],
                "active": False,
                "meta": "scaffold from template",
            }],
        })
        docs_nav_groups.append({
            "title": "Documents",
            "entries": document_entries,
        })
        workbench_ui_navigation_groups = docs_nav_groups
        disclosure_groups = [
            {
                "title": "Display options",
                "expanded": False,
                "groups": [document_sort_group, document_direction_group],
            },
        ]
    elif active_mode == "datums":
        workbench_ui_navigation_groups = [
            {
                "title": "Switch document",
                "entries": document_entries,
                "collapsible": True,
            },
            row_navigation_group,
        ]
        disclosure_groups = [
            {
                "title": "Display options",
                "expanded": False,
                "groups": [
                    row_sort_group,
                    row_direction_group,
                    grouping_group,
                    lens_group,
                    source_visibility_group,
                    overlay_group,
                ],
            },
            {
                "title": "Inspector",
                "expanded": False,
                "context_conditions": [
                    {"level": "version", "label": "Version", "value": _as_text(model.get("document_version_hash_short")) or "—"},
                    {"level": "datum", "label": "Row Identity", "value": _as_text(model.get("selected_row_hyphae_hash_short")) or "—"},
                    {"level": "datum", "label": "Resolved Lens", "value": _as_text((model.get("selected_row") or {}).get("resolved_lens")) or "—"},
                    {"level": "view", "label": "Document Sort", "value": f"{_as_text(model.get('document_sort_key')) or 'document_id'} {_as_text(model.get('document_sort_direction')) or 'asc'}"},
                    {"level": "view", "label": "Grouping", "value": _as_text(model.get("group_mode")) or "flat"},
                    {"level": "view", "label": "Lens", "value": _as_text(model.get("workbench_lens")) or "interpreted"},
                    {"level": "view", "label": "Source", "value": _as_text(model.get("source_visibility")) or "show"},
                    {"level": "view", "label": "Overlay", "value": _as_text(model.get("overlay_visibility")) or "show"},
                ],
            },
        ]
    else:  # author
        # In Author mode the user composes new documents or rows. The
        # forms are emitted as first-class navigation groups so the
        # renderer can show inline inputs without a modal. Switch
        # document stays accessible so the user can target an existing
        # doc for new-datum insertion.
        workbench_ui_navigation_groups = [
            {
                "title": "Switch document",
                "entries": document_entries,
                "collapsible": True,
            },
        ]
        disclosure_groups = []
    workbench_ui_workbench_state = {
        "state_reflection": {
            "current_sandbox": effective_sandbox,
            "current_file": _as_text(model.get("document_id")),
            "current_datum": selected_row_address,
            "current_object": "",
            "aitas": {
                "attention": selected_row_address or _as_text(model.get("document_id")),
                "intention": _as_text(model.get("workbench_lens")) or "interpreted",
                "time": "current",
                "archetype": "sql_authority_lens",
            },
            "nimm": {
                "directive": "observe_state",
                "actions": [
                    "select_document",
                    "select_row",
                    "filter",
                    "sort",
                    "group",
                    "create_document",
                    "create_datum",
                ],
            },
        },
    }
    control_panel = build_unified_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
        surface_label=sandbox_label.upper(),
        navigation_groups=workbench_ui_navigation_groups,
        actions=[],
        workbench_state=workbench_ui_workbench_state,
        tool_extensions=workbench_ui_extensions,
        disclosure_groups=disclosure_groups,
        workbench_mode=workbench_mode_payload,
    )
    # Slim context_conditions: keep only the two identity rows the user
    # always needs (Sandbox + Document + Selected Row when applicable).
    # File / Workbench / Datum rows from _build_context_conditions
    # duplicate information the workbench surfaces elsewhere; Version,
    # Row Identity, Resolved Lens, and the view-state mirrors (Document
    # Sort, Grouping, Lens, Source, Overlay) move into the Inspector
    # disclosure group emitted by the Datums-mode branch above.
    _CHROME_KEEP_LABELS = {"Sandbox"}
    inherited_context = [
        condition
        for condition in (control_panel.get("context_conditions") or [])
        if condition.get("label") in _CHROME_KEEP_LABELS
    ]
    panel_context = inherited_context
    # Only surface Document / Selected Row in the chrome when the user
    # is actually working with a specific document (Datums or Author
    # modes). In Docs mode the read service may auto-select a default
    # document, but exposing that to the user is misleading — they're
    # browsing the list and have not chosen anything yet.
    if active_mode in {"datums", "author"} and selected_document_id:
        panel_context.append(
            {"level": "document", "label": "Document", "value": selected_document_id, "state": "active"}
        )
    if active_mode == "datums" and selected_row_address:
        panel_context.append(
            {"level": "datum", "label": "Selected Row", "value": selected_row_address, "state": "selected"}
        )
    control_panel["context_conditions"] = panel_context
    # Document collection: filter to the effective sandbox unless this is
    # the system reflective view (which shows the whole corpus).
    all_documents = list(model.get("document_rows") or [])
    if effective_sandbox == WORKBENCH_UI_SANDBOX_TOKEN:
        sandbox_documents = all_documents
    else:
        sandbox_documents = [
            doc for doc in all_documents
            if _is_document_in_sandbox(doc, effective_sandbox)
        ]
    workbench_title = f"Workbench — {sandbox_label}"
    workbench_subtitle = (
        "Reflective view of the SQL authority lens state."
        if effective_sandbox == WORKBENCH_UI_SANDBOX_TOKEN
        else f"Datum documents and rows in the {sandbox_label} sandbox."
    )
    workbench = attach_region_family_contract(
        {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "sql_authority_lens",
        "title": workbench_title,
        "subtitle": workbench_subtitle,
        "visible": True,
        "state_reflection": workbench_ui_workbench_state["state_reflection"],
        "document_collection": {
            "sandbox_id": effective_sandbox,
            "documents": sandbox_documents,
        },
        "active_document": ((model.get("surface_payload") or {}).get("workspace") or {}).get("selected_document"),
        "surface_payload": model["surface_payload"],
        },
        family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
    )

    # Inject Author-mode form slots. Every sandbox is writable; the
    # forms always render. The renderer surfaces a status when the
    # sandbox has no templates registered.
    model["surface_payload"]["new_source_document_form"] = (
        _build_new_source_document_form(sandbox=effective_sandbox)
    )
    model["surface_payload"]["new_datum_form"] = _build_new_datum_form(
        sandbox=effective_sandbox,
        selected_document_id=_as_text(model.get("document_id")),
    )
    interface_panel = attach_region_family_contract(
        {
        "schema": PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
        "kind": "summary_panel",
        "title": "Selection",
        "summary": "Selected document/version metadata, row semantics, and additive directive overlays.",
        "visible": True,
        "subject": {
            "level": "datum",
            "id": _as_text((model.get("selected_row") or {}).get("datum_address")) or _as_text(model.get("document_id")),
        },
        "sections": list(model.get("interface_panel_sections") or []),
        },
        family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
        surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
    )
    # Plan v2: dispatch the visualization panel based on surface_query.tool.
    # Looks up the tool in the registry, calls its build_panel_payload with
    # the current workbench context, embeds the result. When no tool is
    # requested the build_shell_composition_payload helper emits a hidden
    # placeholder for schema continuity.
    visualization_panel = _build_visualization_panel(
        surface_query=surface_query,
        authority_db_file=authority_db_file,
        sandbox_id=effective_sandbox,
        document_id=selected_document_id,
        datum_address=selected_row_address,
    )
    return {
        "entrypoint_id": WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
        "read_write_posture": "write",
        "page_title": workbench_title,
        "page_subtitle": workbench_subtitle,
        "canonical_query": active_query,
        "surface_payload": model["surface_payload"],
        "control_panel": control_panel,
        "workbench": workbench,
        "interface_panel": interface_panel,
        "visualization_panel": visualization_panel,
        "route": WORKBENCH_UI_TOOL_ROUTE,
        "sandbox_id": effective_sandbox,
        "sandbox_label": sandbox_label,
    }


def _build_visualization_panel(
    *,
    surface_query: dict[str, Any] | None,
    authority_db_file: str | Path | None,
    sandbox_id: str,
    document_id: str,
    datum_address: str,
) -> dict[str, Any] | None:
    """Resolve surface_query.tool to a registered tool and build the panel.

    Returns None when no tool is requested or the requested tool is not
    registered — the shell composition then emits the canonical hidden
    placeholder.
    """
    if not isinstance(surface_query, dict):
        return None
    tool_id = _as_text(surface_query.get("tool"))
    if not tool_id:
        return None
    # Import lazily to keep tools package import-side-effects (registry
    # population) localized to where they're actually needed.
    from MyCiteV2.packages.tools import get as _tools_get
    tool = _tools_get(tool_id)
    if tool is None:
        return {
            "tool_id": tool_id,
            "tool_label": tool_id,
            "panel_payload": {"error": f"unknown tool: {tool_id}"},
        }
    authority_path = _path_or_none(authority_db_file)
    try:
        payload = tool.build_panel_payload(
            authority_db_file=authority_path,
            sandbox_id=sandbox_id,
            document_id=document_id,
            datum_address=datum_address,
        )
    except Exception as exc:  # pragma: no cover — tool errors must not crash the shell
        payload = {"error": f"tool failed: {exc}"}
    return {
        "tool_id": getattr(tool, "tool_id", tool_id),
        "tool_label": getattr(tool, "label", tool_id),
        "panel_payload": payload,
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
    "build_portal_workbench_ui_bundle",
    "run_portal_workbench_ui",
]
