from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    SYSTEM_ROOT_SURFACE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
)
from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter, FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.modules.domains.datum_recognition.service import DatumWorkbenchProjection, DatumWorkbenchService
from MyCiteV2.packages.modules.domains.publication import (
    PublicationProfileBasicsService,
    PublicationTenantSummary,
    PublicationTenantSummaryService,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    FOCUS_LEVEL_DATUM,
    FOCUS_LEVEL_FILE,
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    PortalShellState,
    SYSTEM_ACTIVITY_FILE_KEY,
    SYSTEM_ANCHOR_FILE_KEY,
    SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
    SYSTEM_PROFILE_BASICS_FILE_KEY,
    SYSTEM_ROOT_SURFACE_ID,
    SYSTEM_ROOT_ROUTE,
    TRANSITION_BACK_OUT,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_FILE,
    TRANSITION_FOCUS_OBJECT,
    TRANSITION_SET_VERB,
    VERB_INVESTIGATE,
    VERB_MANIPULATE,
    VERB_MEDIATE,
    VERB_NAVIGATE,
    build_portal_shell_request_payload,
    canonical_query_for_shell_state,
    focus_level_for_shell_state,
    segment_id_for_level,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_or_none(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value)


def _audit_service(audit_storage_file: str | Path | None) -> LocalAuditService:
    if audit_storage_file is None:
        return LocalAuditService(None)
    return LocalAuditService(FilesystemAuditLogAdapter(Path(audit_storage_file)))


def _publication_services(
    *,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
) -> tuple[PublicationTenantSummaryService, PublicationProfileBasicsService] | None:
    if data_dir is None:
        return None
    adapter = FilesystemSystemDatumStoreAdapter(Path(data_dir), public_dir=public_dir)
    return PublicationTenantSummaryService(adapter), PublicationProfileBasicsService(adapter)


def _profile_summary(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
) -> PublicationTenantSummary:
    services = _publication_services(data_dir=data_dir, public_dir=public_dir)
    if services is None:
        return PublicationTenantSummary.fallback(
            tenant_id=portal_scope.scope_id,
            tenant_domain=portal_domain,
            warnings=("data_dir_not_configured",),
        )
    summary_service, _ = services
    summary = summary_service.read_summary(portal_scope.scope_id, portal_domain)
    if summary is None:
        return PublicationTenantSummary.fallback(
            tenant_id=portal_scope.scope_id,
            tenant_domain=portal_domain,
            warnings=("publication_profile_not_found",),
        )
    return summary


def read_system_workbench_projection(
    *,
    portal_scope: PortalScope,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
) -> DatumWorkbenchProjection:
    if data_dir is None:
        return DatumWorkbenchProjection(
            tenant_id=portal_scope.scope_id,
            documents=(),
            selected_document_id="",
            source_files={},
            readiness_status={"authoritative_catalog": "missing", "data_dir": "not_configured"},
            warnings=("data_dir_not_configured",),
        )
    store = FilesystemSystemDatumStoreAdapter(Path(data_dir), public_dir=public_dir)
    return DatumWorkbenchService(store).read_workbench(portal_scope.scope_id)


def _document_label(document: Any) -> str:
    if getattr(document, "document_id", "") == "system:anthology":
        return "Anthology"
    name = _as_text(getattr(document, "document_name", ""))
    tool_id = _as_text(getattr(document, "tool_id", ""))
    if tool_id and name:
        return f"{tool_id}: {name}"
    return name or _as_text(getattr(document, "document_id", "")) or "Document"


def _document_file_key(document: Any) -> str:
    if getattr(document, "document_id", "") == "system:anthology":
        return SYSTEM_ANCHOR_FILE_KEY
    return _as_text(getattr(document, "document_id", ""))


def _document_detail(document: Any) -> str:
    detail_bits = []
    source_kind = _as_text(getattr(document, "source_kind", ""))
    if source_kind:
        detail_bits.append(source_kind.replace("_", " "))
    relative_path = _as_text(getattr(document, "relative_path", ""))
    if relative_path:
        detail_bits.append(relative_path)
    return " · ".join(detail_bits)


def build_workspace_file_entries(
    *,
    projection: DatumWorkbenchProjection,
    shell_state: PortalShellState,
    portal_scope: PortalScope,
) -> list[dict[str, Any]]:
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    file_entries = [
        {
            "file_key": SYSTEM_ANCHOR_FILE_KEY,
            "label": "Anthology",
            "kind": "document",
            "detail": "canonical anchor file",
            "active": active_file_key == SYSTEM_ANCHOR_FILE_KEY,
        },
        {
            "file_key": SYSTEM_ACTIVITY_FILE_KEY,
            "label": "Activity",
            "kind": "virtual",
            "detail": "workspace activity history",
            "active": active_file_key == SYSTEM_ACTIVITY_FILE_KEY,
        },
        {
            "file_key": SYSTEM_PROFILE_BASICS_FILE_KEY,
            "label": "Profile Basics",
            "kind": "virtual",
            "detail": "workspace profile basics editor",
            "active": active_file_key == SYSTEM_PROFILE_BASICS_FILE_KEY,
        },
    ]
    seen_keys = {entry["file_key"] for entry in file_entries}
    for document in projection.documents:
        file_key = _document_file_key(document)
        if not file_key or file_key in seen_keys:
            continue
        file_entries.append(
            {
                "file_key": file_key,
                "label": _document_label(document),
                "kind": "document",
                "detail": _document_detail(document),
                "active": active_file_key == file_key,
            }
        )
        seen_keys.add(file_key)
    return file_entries


def _selected_document(projection: DatumWorkbenchProjection, *, file_key: str) -> Any | None:
    if file_key == SYSTEM_ANCHOR_FILE_KEY:
        for document in projection.documents:
            if getattr(document, "document_id", "") == "system:anthology":
                return document
    for document in projection.documents:
        if _document_file_key(document) == file_key:
            return document
    return projection.selected_document


def _row_label(row: Any) -> str:
    labels = list(getattr(row, "labels", ()) or ())
    if labels:
        return _as_text(labels[0])
    return _as_text(getattr(row, "datum_address", "")) or "Datum"


def _row_diagnostics(row: Any) -> str:
    diagnostics = [item for item in list(getattr(row, "diagnostic_states", ()) or ()) if _as_text(item)]
    return ", ".join(diagnostics) if diagnostics else "ok"


def _datum_coordinates(datum_id: object) -> dict[str, int] | None:
    token = _as_text(datum_id)
    parts = token.split("-")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return {
        "layer": int(parts[0]),
        "value_group": int(parts[1]),
        "iteration": int(parts[2]),
    }


def _row_reference_bindings(row: Any) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for binding in list(getattr(row, "reference_bindings", ()) or ()):
        bindings.append(
            {
                "label": _as_text(getattr(binding, "anchor_label", "")) or _as_text(getattr(binding, "anchor_address", "")),
                "object_id": _as_text(getattr(binding, "anchor_address", "")) or _as_text(getattr(binding, "normalized_reference_form", "")),
                "reference_form": _as_text(getattr(binding, "reference_form", "")),
                "resolution_state": _as_text(getattr(binding, "resolution_state", "")),
                "value_token": _as_text(getattr(binding, "value_token", "")),
            }
        )
    return bindings


def _row_item(row: Any, *, selected_datum_id: str) -> dict[str, Any]:
    datum_id = _as_text(getattr(row, "datum_address", ""))
    diagnostics = list(getattr(row, "diagnostic_states", ()) or ())
    return {
        "datum_id": datum_id,
        "label": _row_label(row),
        "detail": _row_diagnostics(row),
        "diagnostics": diagnostics,
        "selected": datum_id == selected_datum_id,
        "coordinates": _datum_coordinates(datum_id),
        "primary_value_token": _as_text(getattr(row, "primary_value_token", "")),
        "recognized_family": _as_text(getattr(row, "recognized_family", "")),
        "recognized_anchor": _as_text(getattr(row, "recognized_anchor", "")),
    }


def _selected_datum_payload(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    datum_id = _as_text(getattr(row, "datum_address", ""))
    return {
        "datum_id": datum_id,
        "label": _row_label(row),
        "labels": list(getattr(row, "labels", ()) or ()),
        "coordinates": _datum_coordinates(datum_id),
        "diagnostic_states": list(getattr(row, "diagnostic_states", ()) or ()),
        "primary_value_token": _as_text(getattr(row, "primary_value_token", "")),
        "recognized_family": _as_text(getattr(row, "recognized_family", "")),
        "recognized_anchor": _as_text(getattr(row, "recognized_anchor", "")),
        "reference_bindings": _row_reference_bindings(row),
        "raw": getattr(row, "raw", None),
        "render_hints": dict(getattr(row, "render_hints", {}) or {}),
    }


def _anthology_layer_groups(document: Any, *, selected_datum_id: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[object, object], list[dict[str, Any]]] = {}
    layer_meta: dict[object, dict[str, Any]] = {}
    value_group_meta: dict[tuple[object, object], dict[str, Any]] = {}

    for row in list(getattr(document, "rows", ()) or ()):
        item = _row_item(row, selected_datum_id=selected_datum_id)
        datum_id = item["datum_id"]
        if not datum_id:
            continue
        coordinates = item.get("coordinates") or {}
        layer = coordinates.get("layer")
        value_group = coordinates.get("value_group")
        layer_key: object = layer if layer is not None else "unstructured"
        value_group_key: object = value_group if value_group is not None else "unstructured"
        grouped.setdefault((layer_key, value_group_key), []).append(item)
        if layer_key not in layer_meta:
            layer_meta[layer_key] = {
                "layer": layer,
                "label": f"Layer {layer}" if layer is not None else "Unstructured",
            }
        if (layer_key, value_group_key) not in value_group_meta:
            value_group_meta[(layer_key, value_group_key)] = {
                "value_group": value_group,
                "label": f"Value Group {value_group}" if value_group is not None else "Unstructured",
            }

    def _sort_key(token: object) -> tuple[int, object]:
        return (0, token) if isinstance(token, int) else (1, str(token))

    layer_groups: list[dict[str, Any]] = []
    layer_keys = sorted({layer_key for layer_key, _ in grouped.keys()}, key=_sort_key)
    for layer_key in layer_keys:
        group_pairs = sorted(
            [pair for pair in grouped.keys() if pair[0] == layer_key],
            key=lambda pair: _sort_key(pair[1]),
        )
        value_groups: list[dict[str, Any]] = []
        layer_row_count = 0
        layer_selected = False
        for pair in group_pairs:
            rows = sorted(
                grouped[pair],
                key=lambda item: (
                    (item.get("coordinates") or {}).get("iteration")
                    if isinstance((item.get("coordinates") or {}).get("iteration"), int)
                    else 10**9,
                    item.get("datum_id") or "",
                ),
            )
            row_count = len(rows)
            selected = any(bool(item.get("selected")) for item in rows)
            layer_row_count += row_count
            layer_selected = layer_selected or selected
            value_groups.append(
                {
                    "value_group": value_group_meta[pair]["value_group"],
                    "label": value_group_meta[pair]["label"],
                    "row_count": row_count,
                    "selected": selected,
                    "rows": rows,
                }
            )
        layer_groups.append(
            {
                "layer": layer_meta[layer_key]["layer"],
                "label": layer_meta[layer_key]["label"],
                "row_count": layer_row_count,
                "selected": layer_selected,
                "value_groups": value_groups,
            }
        )
    return layer_groups


def _document_row_items(document: Any, *, selected_datum_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in list(getattr(document, "rows", ()) or ())[:80]:
        datum_id = _as_text(getattr(row, "datum_address", ""))
        if not datum_id:
            continue
        items.append(_row_item(row, selected_datum_id=selected_datum_id))
    return items


def _selected_datum(document: Any | None, *, datum_id: str) -> Any | None:
    if document is None or not datum_id:
        return None
    for row in list(getattr(document, "rows", ()) or ()):
        if _as_text(getattr(row, "datum_address", "")) == datum_id:
            return row
    return None


def _object_items(row: Any | None, *, selected_object_id: str) -> list[dict[str, Any]]:
    if row is None:
        return []
    entries = []
    for binding in list(getattr(row, "reference_bindings", ()) or ()):
        object_id = _as_text(getattr(binding, "anchor_address", "")) or _as_text(getattr(binding, "normalized_reference_form", ""))
        if not object_id:
            continue
        entries.append(
            {
                "object_id": object_id,
                "label": _as_text(getattr(binding, "anchor_label", "")) or object_id,
                "detail": _as_text(getattr(binding, "resolution_state", "")) or "reference",
                "selected": object_id == selected_object_id,
            }
        )
    primary_value = _as_text(getattr(row, "primary_value_token", ""))
    if primary_value:
        entries.append(
            {
                "object_id": primary_value,
                "label": primary_value,
                "detail": "primary value token",
                "selected": primary_value == selected_object_id,
            }
        )
    return entries


def _selected_object(row: Any | None, *, object_id: str) -> dict[str, Any] | None:
    if row is None or not object_id:
        return None
    for entry in _object_items(row, selected_object_id=object_id):
        if entry["object_id"] == object_id:
            return entry
    return None


def _focus_section(
    *,
    title: str,
    level: str,
    compressed: bool,
    entries: list[dict[str, Any]] | None = None,
    facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "level": level,
        "compressed": bool(compressed),
        "entries": list(entries or []),
        "facts": list(facts or []),
    }


def _entry_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    transition: dict[str, Any],
    requested_surface_id: str | None = None,
) -> dict[str, Any]:
    return build_portal_shell_request_payload(
        requested_surface_id=requested_surface_id or shell_state.active_surface_id,
        portal_scope=portal_scope,
        shell_state=shell_state,
        transition=transition,
    )


def build_focus_stack_sections(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    file_entries: list[dict[str, Any]],
    active_document: Any | None,
    selected_datum: Any | None,
    selected_object: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    focus_level = focus_level_for_shell_state(shell_state)
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    selected_datum_id = segment_id_for_level(shell_state, level=FOCUS_LEVEL_DATUM)
    selected_object_id = segment_id_for_level(shell_state, level=FOCUS_LEVEL_OBJECT)

    sandbox_entries: list[dict[str, Any]] = [
        {
            "label": entry["label"],
            "meta": entry["detail"],
            "active": entry["active"],
            "href": SYSTEM_ROOT_ROUTE,
            "shell_request": _entry_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                transition={"kind": TRANSITION_FOCUS_FILE, "file_key": entry["file_key"]},
                requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
            ),
        }
        for entry in file_entries
    ]
    sandbox_entries.insert(
        0,
        {
            "label": "Sandbox overview",
            "meta": "return to sandbox management",
            "active": not active_file_key,
            "href": SYSTEM_ROOT_ROUTE,
            "shell_request": _entry_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                transition={"kind": TRANSITION_FOCUS_FILE, "file_key": "sandbox"},
                requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
            ),
        },
    )
    sections = [
        _focus_section(
            title="Sandbox",
            level=FOCUS_LEVEL_SANDBOX,
            compressed=focus_level != FOCUS_LEVEL_SANDBOX,
            entries=sandbox_entries,
            facts=[
                {"label": "focus", "value": focus_level},
                {"label": "visible tools", "value": str(len(tool_rows))},
            ],
        )
    ]

    if active_file_key:
        file_entries_for_section: list[dict[str, Any]] = []
        if active_document is not None:
            for item in _document_row_items(active_document, selected_datum_id=selected_datum_id):
                file_entries_for_section.append(
                    {
                        "label": item["label"],
                        "meta": item["detail"],
                        "active": item["selected"],
                        "href": SYSTEM_ROOT_ROUTE,
                        "shell_request": _entry_shell_request(
                            portal_scope=portal_scope,
                            shell_state=shell_state,
                            transition={
                                "kind": TRANSITION_FOCUS_DATUM,
                                "file_key": active_file_key,
                                "datum_id": item["datum_id"],
                            },
                            requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
                        ),
                    }
                )
        file_facts = [
            {"label": "file", "value": active_file_key},
        ]
        if active_document is not None:
            file_facts.append({"label": "rows", "value": str(len(list(getattr(active_document, "rows", ()) or ())))})
        sections.append(
            _focus_section(
                title="File",
                level=FOCUS_LEVEL_FILE,
                compressed=focus_level in {FOCUS_LEVEL_DATUM, FOCUS_LEVEL_OBJECT},
                entries=file_entries_for_section,
                facts=file_facts,
            )
        )

    if selected_datum is not None:
        datum_entries = []
        for object_item in _object_items(selected_datum, selected_object_id=selected_object_id):
            datum_entries.append(
                {
                    "label": object_item["label"],
                    "meta": object_item["detail"],
                    "active": object_item["selected"],
                    "href": SYSTEM_ROOT_ROUTE,
                    "shell_request": _entry_shell_request(
                        portal_scope=portal_scope,
                        shell_state=shell_state,
                        transition={
                            "kind": TRANSITION_FOCUS_OBJECT,
                            "file_key": active_file_key,
                            "datum_id": _as_text(getattr(selected_datum, "datum_address", "")),
                            "object_id": object_item["object_id"],
                        },
                        requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
                    ),
                }
            )
        sections.append(
            _focus_section(
                title="Datum",
                level=FOCUS_LEVEL_DATUM,
                compressed=focus_level == FOCUS_LEVEL_OBJECT,
                entries=datum_entries,
                facts=[
                    {"label": "datum", "value": _as_text(getattr(selected_datum, "datum_address", ""))},
                    {"label": "diagnostics", "value": _row_diagnostics(selected_datum)},
                ],
            )
        )

    if selected_object is not None:
        sections.append(
            _focus_section(
                title="Object",
                level=FOCUS_LEVEL_OBJECT,
                compressed=False,
                entries=[],
                facts=[
                    {"label": "object", "value": selected_object["label"]},
                    {"label": "detail", "value": selected_object["detail"]},
                ],
            )
        )

    active_subject_label = (
        _as_text(getattr(selected_datum, "datum_address", ""))
        or _as_text(selected_object.get("label") if isinstance(selected_object, dict) else "")
        or active_file_key
        or portal_scope.scope_id
    )
    sections.append(
        _focus_section(
            title="Current Intention",
            level="verb",
            compressed=False,
            entries=[
                {
                    "label": verb.title(),
                    "meta": "active" if shell_state.verb == verb else "switch",
                    "active": shell_state.verb == verb,
                    "href": SYSTEM_ROOT_ROUTE,
                    "shell_request": _entry_shell_request(
                        portal_scope=portal_scope,
                        shell_state=shell_state,
                        transition={"kind": TRANSITION_SET_VERB, "verb": verb},
                        requested_surface_id=shell_state.active_surface_id,
                    ),
                }
                for verb in (VERB_NAVIGATE, VERB_INVESTIGATE, VERB_MEDIATE, VERB_MANIPULATE)
            ],
            facts=[
                {"label": "subject", "value": active_subject_label},
                {"label": "panel", "value": "open" if shell_state.chrome.interface_panel_open else "closed"},
                {"label": "back out", "value": "object→datum→file→sandbox"},
            ],
        )
    )
    return sections


def build_tool_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    active_document: Any | None,
    selected_datum: Any | None,
    selected_object: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
    title: str,
) -> dict[str, Any]:
    projection = read_system_workbench_projection(portal_scope=portal_scope, data_dir=data_dir, public_dir=public_dir)
    file_entries = build_workspace_file_entries(
        projection=projection,
        shell_state=shell_state,
        portal_scope=portal_scope,
    )
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    resolved_document = active_document
    if resolved_document is None and active_file_key not in {"", SYSTEM_ACTIVITY_FILE_KEY, SYSTEM_PROFILE_BASICS_FILE_KEY}:
        resolved_document = _selected_document(projection, file_key=active_file_key)
    resolved_datum = selected_datum
    if resolved_datum is None:
        resolved_datum = _selected_datum(
            resolved_document,
            datum_id=segment_id_for_level(shell_state, level=FOCUS_LEVEL_DATUM),
        )
    resolved_object = selected_object
    if resolved_object is None:
        resolved_object = _selected_object(
            resolved_datum,
            object_id=segment_id_for_level(shell_state, level=FOCUS_LEVEL_OBJECT),
        )
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "stacked_focus_panel",
        "title": title,
        "sections": build_focus_stack_sections(
            portal_scope=portal_scope,
            shell_state=shell_state,
            file_entries=file_entries,
            active_document=resolved_document,
            selected_datum=resolved_datum,
            selected_object=resolved_object,
            tool_rows=tool_rows,
        ),
    }


def build_system_workspace_bundle(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    audit_storage_file: str | Path | None,
    tool_rows: list[dict[str, Any]],
    profile_save_status: str = "",
) -> dict[str, Any]:
    projection = read_system_workbench_projection(
        portal_scope=portal_scope,
        data_dir=data_dir,
        public_dir=public_dir,
    )
    file_entries = build_workspace_file_entries(
        projection=projection,
        shell_state=shell_state,
        portal_scope=portal_scope,
    )
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    selected_datum_id = segment_id_for_level(shell_state, level=FOCUS_LEVEL_DATUM)
    selected_object_id = segment_id_for_level(shell_state, level=FOCUS_LEVEL_OBJECT)
    active_document = None if active_file_key in {"", SYSTEM_ACTIVITY_FILE_KEY, SYSTEM_PROFILE_BASICS_FILE_KEY} else _selected_document(
        projection,
        file_key=active_file_key,
    )
    selected_datum = _selected_datum(active_document, datum_id=selected_datum_id)
    selected_object = _selected_object(selected_datum, object_id=selected_object_id)
    activity_projection = _audit_service(audit_storage_file).read_recent_activity_projection()
    profile_summary = _profile_summary(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
    )
    focus_level = focus_level_for_shell_state(shell_state)
    if not active_file_key:
        workbench_mode = "sandbox_management"
    elif focus_level == FOCUS_LEVEL_FILE:
        workbench_mode = "file_navigation"
    else:
        workbench_mode = "datum_management"

    workspace: dict[str, Any] = {
        "portal_instance_id": portal_scope.scope_id,
        "portal_domain": portal_domain,
        "focus_path": [segment.to_dict() for segment in shell_state.focus_path],
        "focus_subject": dict(shell_state.focus_subject or {}),
        "mediation_subject": dict(shell_state.mediation_subject or {}) if shell_state.mediation_subject else None,
        "verb": shell_state.verb,
        "focus_level": focus_level,
        "workbench_mode": workbench_mode,
        "files": file_entries,
        "active_file_key": active_file_key or "",
        "readiness_status": dict(projection.readiness_status),
        "warnings": list(projection.warnings),
    }

    if not active_file_key:
        workspace["sandbox"] = {
            "title": "Sandbox Management",
            "summary": "Backed out of all files. Manage sources, anchor files, and workspace resources.",
            "source_files": dict(projection.source_files),
        }
    elif active_file_key == SYSTEM_ACTIVITY_FILE_KEY:
        workspace["activity"] = {
            "activity_state": activity_projection.activity_state,
            "records": [
                {
                    "record_id": record.record_id,
                    "timestamp": str(record.recorded_at_unix_ms),
                    "event_type": record.event_type,
                    "shell_verb": record.shell_verb,
                    "focus_subject": record.focus_subject,
                }
                for record in activity_projection.records
            ],
        }
    elif active_file_key == SYSTEM_PROFILE_BASICS_FILE_KEY:
        workspace["profile_basics"] = {
            "profile_title": profile_summary.profile_title,
            "profile_summary": profile_summary.profile_summary,
            "contact_email": profile_summary.contact_email,
            "public_website_url": profile_summary.public_website_url,
            "publication_mode": profile_summary.publication_mode,
            "profile_resolution": profile_summary.profile_resolution,
            "form": {
                "title": "Edit profile basics",
                "action_label": "Save profile basics",
                "action_route": "/portal/api/v2/system/workspace/profile-basics",
                "schema": SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
                "status": profile_save_status,
                "fields": [
                    {"field_id": "profile_title", "label": "Profile title", "type": "text", "value": profile_summary.profile_title},
                    {"field_id": "profile_summary", "label": "Profile summary", "type": "textarea", "value": profile_summary.profile_summary},
                    {"field_id": "contact_email", "label": "Contact email", "type": "email", "value": profile_summary.contact_email},
                    {"field_id": "public_website_url", "label": "Public website", "type": "url", "value": profile_summary.public_website_url},
                ],
            },
        }
    elif active_document is not None:
        document_payload = {
            "document_id": _as_text(getattr(active_document, "document_id", "")),
            "label": _document_label(active_document),
            "detail": _document_detail(active_document),
            "diagnostic_totals": dict(getattr(active_document, "diagnostic_totals", {}) or {}),
            "rows": _document_row_items(active_document, selected_datum_id=selected_datum_id),
            "selected_datum": _selected_datum_payload(selected_datum),
            "selected_object": selected_object,
        }
        if _as_text(getattr(active_document, "document_id", "")) == "system:anthology":
            document_payload["presentation"] = "anthology_layered_table"
            document_payload["summary"] = "Canonical system anchor file rendered as a layered datum table."
            document_payload["inspector_hint"] = (
                "Select a datum row to inspect its structural coordinates, bindings, and raw payload."
            )
            document_payload["layer_groups"] = _anthology_layer_groups(
                active_document,
                selected_datum_id=selected_datum_id,
            )
        workspace["document"] = document_payload

    surface_payload = {
        "schema": SYSTEM_ROOT_SURFACE_SCHEMA,
        "kind": "system_workspace",
        "title": "System",
        "subtitle": "Datum-file workbench for the system sandbox.",
        "workspace": workspace,
    }
    control_panel = {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "stacked_focus_panel",
        "title": "System Context",
        "sections": build_focus_stack_sections(
            portal_scope=portal_scope,
            shell_state=shell_state,
            file_entries=file_entries,
            active_document=active_document,
            selected_datum=selected_datum,
            selected_object=selected_object,
            tool_rows=tool_rows,
        ),
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "mediation_panel" if shell_state.verb == VERB_MEDIATE else "summary_panel",
        "title": "Mediation" if shell_state.verb == VERB_MEDIATE else "Interface Panel",
        "summary": "Mediation is bound to the current focus subject." if shell_state.verb == VERB_MEDIATE else "The interface panel stays collapsed during ordinary navigation.",
        "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "sections": [
            {
                "title": "Current focus",
                "rows": [
                    {"label": "verb", "value": shell_state.verb},
                    {"label": "focus level", "value": focus_level},
                    {"label": "focus subject", "value": _as_text((shell_state.focus_subject or {}).get("id")) or portal_scope.scope_id},
                ],
            },
            {
                "title": "Compatible tool surfaces",
                "rows": [
                    {
                        "label": row["label"],
                        "value": "operational" if row["operational"] else "visible, non-operational",
                        "detail": ", ".join(list(row.get("missing_integrations") or []) + list(row.get("missing_capabilities") or [])) or row["summary"],
                    }
                    for row in tool_rows
                ],
            },
        ],
    }
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "system_workspace",
        "title": "System",
        "subtitle": "Datum-file workbench for the system sandbox.",
        "visible": True,
        "surface_payload": surface_payload,
    }
    return {
        "page_title": "System",
        "page_subtitle": "Datum-file workbench for the system sandbox.",
        "surface_payload": surface_payload,
        "control_panel": control_panel,
        "workbench": workbench,
        "inspector": inspector,
        "active_document": active_document,
        "selected_datum": selected_datum,
        "selected_object": selected_object,
        "projection": projection,
    }


__all__ = [
    "build_focus_stack_sections",
    "build_system_workspace_bundle",
    "build_tool_control_panel",
    "build_workspace_file_entries",
    "read_system_workbench_projection",
]
