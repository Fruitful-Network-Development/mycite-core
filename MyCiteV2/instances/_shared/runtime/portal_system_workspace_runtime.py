from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    SYSTEM_ROOT_SURFACE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
)
from MyCiteV2.packages.adapters.sql import (
    SqliteAuditLogAdapter,
    SqliteDirectiveContextAdapter,
    SqliteSystemDatumStoreAdapter,
)
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.modules.domains.datum_recognition import DatumWorkbenchProjection, DatumWorkbenchService
from MyCiteV2.packages.modules.domains.publication import (
    PublicationProfileBasicsService,
    PublicationTenantSummary,
    PublicationTenantSummaryService,
)
from MyCiteV2.packages.ports.directive_context import DirectiveContextRequest
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FOCUS_LEVEL_DATUM,
    FOCUS_LEVEL_FILE,
    FOCUS_LEVEL_OBJECT,
    FND_EBI_TOOL_SURFACE_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    PortalShellState,
    SYSTEM_ACTIVITY_FILE_KEY,
    SYSTEM_ANCHOR_FILE_KEY,
    SYSTEM_PROFILE_BASICS_FILE_KEY,
    SYSTEM_ROOT_SURFACE_ID,
    SYSTEM_ROOT_ROUTE,
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

_DIRECTIVE_CONTEXT_TOOL_ID = "system_workspace"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_or_none(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value)


def _normalize_authority_mode(value: object) -> str:
    del value
    return "sql_primary"


def _resolved_sql_datum_store(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    authority_db_file: str | Path | None,
    authority_mode: str,
):
    del portal_domain, data_dir, public_dir, authority_mode
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return None
    return SqliteSystemDatumStoreAdapter(authority_path)


def _audit_service(
    audit_storage_file: str | Path | None,
    *,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> LocalAuditService:
    del audit_storage_file, authority_mode
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return LocalAuditService(None)
    return LocalAuditService(SqliteAuditLogAdapter(authority_path))


def _publication_services(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> tuple[PublicationTenantSummaryService, PublicationProfileBasicsService] | None:
    adapter = _resolved_sql_datum_store(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    if adapter is None:
        return None
    return PublicationTenantSummaryService(adapter), PublicationProfileBasicsService(adapter)


def _profile_summary(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> PublicationTenantSummary:
    services = _publication_services(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    if services is None:
        return PublicationTenantSummary.fallback(
            tenant_id=portal_scope.scope_id,
            tenant_domain=portal_domain,
            warnings=("sql_authority_required",),
        )
    summary_service, _ = services
    summary = summary_service.read_summary(portal_scope.scope_id, portal_domain)
    if summary is None:
        return PublicationTenantSummary.fallback(
            tenant_id=portal_scope.scope_id,
            tenant_domain=portal_domain,
            warnings=("sql_publication_summary_missing",),
        )
    return summary


def read_system_workbench_projection(
    *,
    portal_scope: PortalScope,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> DatumWorkbenchProjection:
    store = _resolved_sql_datum_store(
        portal_scope=portal_scope,
        portal_domain="",
        data_dir=data_dir,
        public_dir=public_dir,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    if store is None:
        return DatumWorkbenchProjection(
            tenant_id=portal_scope.scope_id,
            documents=(),
            selected_document_id="",
            source_files={},
            readiness_status={"authoritative_catalog": "missing", "sql_authority": "required"},
            warnings=("sql_authority_required",),
        )
    if not store.has_authoritative_catalog(portal_scope.scope_id) or not store.has_system_workbench(portal_scope.scope_id):
        return DatumWorkbenchProjection(
            tenant_id=portal_scope.scope_id,
            documents=(),
            selected_document_id="",
            source_files={},
            readiness_status={"authoritative_catalog": "missing", "sql_authority": "uninitialized"},
            warnings=("sql_authority_uninitialized",),
        )
    return DatumWorkbenchService(store).read_workbench(portal_scope.scope_id)


def _directive_context_adapter(
    *,
    authority_db_file: str | Path | None,
    authority_mode: str,
) -> SqliteDirectiveContextAdapter | None:
    normalized_mode = _normalize_authority_mode(authority_mode)
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None or normalized_mode != "sql_primary":
        return None
    return SqliteDirectiveContextAdapter(authority_path)


def _directive_state_summary(value: dict[str, Any]) -> str:
    bits = [f"{_as_text(key)}={_as_text(item)}" for key, item in value.items() if _as_text(key) and _as_text(item)]
    return ", ".join(bits[:4])


def _workspace_directive_context(
    *,
    portal_scope: PortalScope,
    active_document: Any | None,
    selected_datum: Any | None,
    authority_db_file: str | Path | None,
    authority_mode: str,
) -> dict[str, Any] | None:
    adapter = _directive_context_adapter(
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    authority_path = _path_or_none(authority_db_file)
    document_id = _as_text(getattr(active_document, "document_id", "")) if active_document is not None else ""
    if adapter is None or authority_path is None or not document_id:
        return None
    datum_store = SqliteSystemDatumStoreAdapter(authority_path)
    document_identity = datum_store.read_document_version_identity(
        tenant_id=portal_scope.scope_id,
        document_id=document_id,
    )
    if document_identity is None:
        return {
            "subject_level": "document",
            "tool_id": _DIRECTIVE_CONTEXT_TOOL_ID,
            "document_id": document_id,
            "subject_version_hash": "",
            "subject_hyphae_hash": "",
            "resolution_status": {"directive_context": "semantic_identity_missing"},
            "warnings": ["sql_document_version_identity_missing"],
            "overlay": None,
        }
    datum_id = _as_text(getattr(selected_datum, "datum_address", "")) if selected_datum is not None else ""
    datum_identity = None
    subject_level = "document"
    if datum_id:
        datum_identity = datum_store.read_datum_semantic_identity(
            tenant_id=portal_scope.scope_id,
            document_id=document_id,
            datum_address=datum_id,
        )
        if datum_identity is not None:
            subject_level = "datum"
    request = DirectiveContextRequest(
        portal_instance_id=portal_scope.scope_id,
        tool_id=_DIRECTIVE_CONTEXT_TOOL_ID,
        subject_hyphae_hash=_as_text((datum_identity or {}).get("hyphae_hash")),
        subject_version_hash=document_identity["version_hash"],
    )
    result = adapter.read_directive_context(request)
    overlay = None
    if result.source is not None:
        overlay = {
            "context_id": result.source.context_id,
            "portal_instance_id": result.source.portal_instance_id,
            "tool_id": result.source.tool_id,
            "subject_hyphae_hash": result.source.subject_hyphae_hash,
            "subject_version_hash": result.source.subject_version_hash,
            "nimm_state": dict(result.source.nimm_state or {}),
            "aitas_state": dict(result.source.aitas_state or {}),
            "scope": dict(result.source.scope or {}),
            "provenance": dict(result.source.provenance or {}),
        }
    warnings = list(result.warnings)
    if datum_id and datum_identity is None:
        warnings.append("sql_datum_semantic_identity_missing")
    return {
        "subject_level": subject_level,
        "tool_id": _DIRECTIVE_CONTEXT_TOOL_ID,
        "document_id": document_id,
        "datum_id": datum_id,
        "subject_version_hash": document_identity["version_hash"],
        "subject_hyphae_hash": _as_text((datum_identity or {}).get("hyphae_hash")),
        "resolution_status": dict(result.resolution_status),
        "warnings": warnings,
        "overlay": overlay,
    }


def _directive_context_section(directive_context: dict[str, Any]) -> dict[str, Any]:
    overlay = directive_context.get("overlay") if isinstance(directive_context.get("overlay"), dict) else None
    rows = [
        {"label": "subject level", "value": _as_text(directive_context.get("subject_level")) or "document"},
        {"label": "overlay", "value": "loaded" if overlay is not None else "missing"},
        {"label": "version hash", "value": _as_text(directive_context.get("subject_version_hash")) or "—"},
        {"label": "hyphae hash", "value": _as_text(directive_context.get("subject_hyphae_hash")) or "—"},
    ]
    if overlay is not None:
        rows.append(
            {
                "label": "NIMM",
                "value": _directive_state_summary(dict(overlay.get("nimm_state") or {})) or "configured",
            }
        )
        rows.append(
            {
                "label": "AITAS",
                "value": _directive_state_summary(dict(overlay.get("aitas_state") or {})) or "configured",
            }
        )
        rows.append(
            {
                "label": "provenance",
                "value": _directive_state_summary(dict(overlay.get("provenance") or {})) or _as_text(overlay.get("context_id")),
            }
        )
    return {"title": "Directive context", "rows": rows}


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


def _panel_entry(
    *,
    label: str,
    meta: object = "",
    active: bool = False,
    href: str = "",
    shell_request: dict[str, Any] | None = None,
    prefix: str = "",
) -> dict[str, Any]:
    entry = {
        "label": _as_text(label),
        "active": bool(active),
        "prefix": _as_text(prefix),
    }
    meta_text = _as_text(meta)
    if meta_text:
        entry["meta"] = meta_text
    href_text = _as_text(href)
    if href_text:
        entry["href"] = href_text
    if shell_request is not None:
        entry["shell_request"] = shell_request
    return entry


def _panel_action(*, label: str, action_kind: str, value: object = "") -> dict[str, Any]:
    return {
        "label": _as_text(label),
        "action_kind": _as_text(action_kind),
        "value": _as_text(value),
    }


def _verb_tab_entries(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    requested_surface_id: str,
) -> list[dict[str, Any]]:
    labels = {
        VERB_NAVIGATE: "NAV",
        VERB_INVESTIGATE: "INV",
        VERB_MEDIATE: "MED",
        VERB_MANIPULATE: "MAN",
    }
    return [
        {
            "label": labels[verb],
            "active": shell_state.verb == verb,
            "shell_request": _entry_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                transition={"kind": TRANSITION_SET_VERB, "verb": verb},
                requested_surface_id=requested_surface_id,
            ),
        }
        for verb in (VERB_NAVIGATE, VERB_INVESTIGATE, VERB_MEDIATE, VERB_MANIPULATE)
    ]


def _file_value_for_panel(*, active_file_key: str, active_document: Any | None) -> str:
    if active_document is not None:
        relative_path = _as_text(getattr(active_document, "relative_path", ""))
        if relative_path:
            return Path(relative_path).name
        document_name = _document_label(active_document)
        if document_name:
            return document_name
    if active_file_key == SYSTEM_ANCHOR_FILE_KEY:
        return "anthology.json"
    if active_file_key == SYSTEM_ACTIVITY_FILE_KEY:
        return "activity"
    if active_file_key == SYSTEM_PROFILE_BASICS_FILE_KEY:
        return "profile_basics"
    return active_file_key or "system"


def _system_context_items(
    *,
    shell_state: PortalShellState,
    active_document: Any | None,
    selected_datum: Any | None,
    selected_object: dict[str, Any] | None,
) -> list[dict[str, str]]:
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    items = [
        {"label": "Sandbox", "value": "SYSTEM"},
        {"label": "File", "value": _file_value_for_panel(active_file_key=active_file_key, active_document=active_document)},
    ]
    if selected_datum is not None:
        items.append(
            {
                "label": "Datum",
                "value": _row_label(selected_datum) or _as_text(getattr(selected_datum, "datum_address", "")),
            }
        )
    if selected_object is not None:
        items.append({"label": "Object", "value": _as_text(selected_object.get("label")) or _as_text(selected_object.get("object_id"))})
    elif shell_state.verb == VERB_MEDIATE:
        subject = _as_text((shell_state.mediation_subject or {}).get("id"))
        if subject:
            items.append({"label": "Mediation", "value": subject})
    return items


def _system_file_groups(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    file_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries = [
        _panel_entry(
            label=_as_text(entry.get("label")) or _as_text(entry.get("file_key")),
            meta=_as_text(entry.get("detail")),
            active=bool(entry.get("active")),
            href=SYSTEM_ROOT_ROUTE,
            shell_request=_entry_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                transition={"kind": TRANSITION_FOCUS_FILE, "file_key": _as_text(entry.get("file_key"))},
                requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
            ),
        )
        for entry in file_entries
    ]
    return [{"title": "Files", "entries": entries}] if entries else []


def _row_meta_from_item(item: dict[str, Any]) -> str:
    coordinates = item.get("coordinates") if isinstance(item.get("coordinates"), dict) else {}
    bits: list[str] = []
    if isinstance(coordinates.get("value_group"), int):
        bits.append(f"VG {coordinates['value_group']}")
    if isinstance(coordinates.get("iteration"), int):
        bits.append(f"I {coordinates['iteration']}")
    diagnostics = ", ".join([_as_text(token) for token in list(item.get("diagnostics") or []) if _as_text(token)])
    if diagnostics:
        bits.append(diagnostics)
    return " | ".join(bits)


def _system_document_groups(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    active_file_key: str,
    active_document: Any,
    selected_datum_id: str,
) -> list[dict[str, Any]]:
    if _as_text(getattr(active_document, "document_id", "")) == "system:anthology":
        groups: list[dict[str, Any]] = []
        for layer_group in _anthology_layer_groups(active_document, selected_datum_id=selected_datum_id):
            entries = []
            for value_group in list(layer_group.get("value_groups") or []):
                for item in list(value_group.get("rows") or []):
                    entries.append(
                        _panel_entry(
                            label=_as_text(item.get("label")) or _as_text(item.get("datum_id")) or "Datum",
                            meta=_row_meta_from_item(item),
                            active=bool(item.get("selected")),
                            href=SYSTEM_ROOT_ROUTE,
                            shell_request=_entry_shell_request(
                                portal_scope=portal_scope,
                                shell_state=shell_state,
                                transition={
                                    "kind": TRANSITION_FOCUS_DATUM,
                                    "file_key": active_file_key,
                                    "datum_id": _as_text(item.get("datum_id")),
                                },
                                requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
                            ),
                        )
                    )
            if entries:
                groups.append({"title": _as_text(layer_group.get("label")) or "Layer", "entries": entries})
        return groups

    rows = _document_row_items(active_document, selected_datum_id=selected_datum_id)
    entries = [
        _panel_entry(
            label=_as_text(item.get("label")) or _as_text(item.get("datum_id")) or "Datum",
            meta=_row_meta_from_item(item) or _as_text(item.get("detail")),
            active=bool(item.get("selected")),
            href=SYSTEM_ROOT_ROUTE,
            shell_request=_entry_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                transition={
                    "kind": TRANSITION_FOCUS_DATUM,
                    "file_key": active_file_key,
                    "datum_id": _as_text(item.get("datum_id")),
                },
                requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
            ),
        )
        for item in rows
    ]
    return [{"title": "Datums", "entries": entries}] if entries else []


def _system_activity_groups(activity_projection: Any) -> list[dict[str, Any]]:
    entries = [
        _panel_entry(
            label=_as_text(getattr(record, "event_type", "")) or "activity",
            meta=_as_text(getattr(record, "recorded_at_unix_ms", "")),
        )
        for record in list(getattr(activity_projection, "records", ()) or ())[:12]
    ]
    return [{"title": "Activity Records", "entries": entries}] if entries else []


def _system_profile_groups(profile_summary: PublicationTenantSummary) -> list[dict[str, Any]]:
    fields = [
        ("Domain", profile_summary.tenant_domain),
        ("Title", profile_summary.profile_title),
        ("Contact", profile_summary.contact_email),
        ("Website", profile_summary.public_website_url),
    ]
    entries = [
        _panel_entry(label=label, meta=value or "unset")
        for label, value in fields
        if _as_text(label)
    ]
    return [{"title": "Profile Fields", "entries": entries}] if entries else []


def _system_selection_groups(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    file_entries: list[dict[str, Any]],
    active_document: Any | None,
    active_file_key: str,
    selected_datum: Any | None,
    selected_object: dict[str, Any] | None,
    activity_projection: Any,
    profile_summary: PublicationTenantSummary,
) -> list[dict[str, Any]]:
    if not active_file_key:
        return _system_file_groups(portal_scope=portal_scope, shell_state=shell_state, file_entries=file_entries)
    if active_file_key == SYSTEM_ACTIVITY_FILE_KEY:
        return _system_activity_groups(activity_projection)
    if active_file_key == SYSTEM_PROFILE_BASICS_FILE_KEY:
        return _system_profile_groups(profile_summary)
    if active_document is not None and selected_datum is None:
        return _system_document_groups(
            portal_scope=portal_scope,
            shell_state=shell_state,
            active_file_key=active_file_key,
            active_document=active_document,
            selected_datum_id="",
        )
    if selected_datum is not None:
        entries = []
        for item in _object_items(selected_datum, selected_object_id=_as_text((selected_object or {}).get("object_id"))):
            entries.append(
                _panel_entry(
                    label=_as_text(item.get("label")) or _as_text(item.get("object_id")) or "Aspect",
                    meta=_as_text(item.get("detail")),
                    active=bool(item.get("selected")),
                    href=SYSTEM_ROOT_ROUTE,
                    shell_request=_entry_shell_request(
                        portal_scope=portal_scope,
                        shell_state=shell_state,
                        transition={
                            "kind": TRANSITION_FOCUS_OBJECT,
                            "file_key": active_file_key,
                            "datum_id": _as_text(getattr(selected_datum, "datum_address", "")),
                            "object_id": _as_text(item.get("object_id")),
                        },
                        requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
                    ),
                )
            )
        return [{"title": "Below Focus", "entries": entries}] if entries else []
    return []


def _tool_root_slug_for_surface(surface_id: str) -> str:
    if surface_id == AWS_CSM_TOOL_SURFACE_ID:
        return "aws-csm"
    if surface_id == FND_EBI_TOOL_SURFACE_ID:
        return "fnd-ebi"
    if surface_id == CTS_GIS_TOOL_SURFACE_ID:
        return "cts-gis"
    return ""


def _safe_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tool_collection_payload(tool_root: Path, *, tool_slug: str) -> tuple[str, list[str]]:
    collection_path = ""
    member_files: list[str] = []
    for candidate in sorted(tool_root.glob(f"tool.*.{tool_slug}.json")):
        payload = _safe_json_object(candidate)
        raw_members = payload.get("member_files")
        if isinstance(raw_members, list):
            member_files = [_as_text(item) for item in raw_members if _as_text(item)]
        collection_path = candidate.name
        break
    if not member_files:
        member_files = [
            path.name
            for path in sorted(tool_root.glob("*.json"))
            if path.name != collection_path
        ]
    return collection_path, member_files


def _aws_csm_domain_groups(tool_root: Path) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    newsletter_root = tool_root / "newsletter"
    if not newsletter_root.exists():
        return groups
    for profile_path in sorted(newsletter_root.glob("newsletter.*.profile.json")):
        profile = _safe_json_object(profile_path)
        domain = _as_text(profile.get("domain")) or profile_path.name
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in (
            profile.get("selected_author_address"),
            profile.get("list_address"),
            profile.get("sender_address"),
        ):
            token = _as_text(candidate).lower()
            if token and token not in seen:
                seen.add(token)
                entries.append(_panel_entry(label=token, prefix="->"))
        contacts_path = newsletter_root / profile_path.name.replace(".profile.json", ".contacts.json")
        contacts = _safe_json_object(contacts_path)
        for contact in list(contacts.get("contacts") or []):
            if not isinstance(contact, dict):
                continue
            token = _as_text(contact.get("email")).lower()
            if token and token not in seen:
                seen.add(token)
                entries.append(_panel_entry(label=token, prefix="->"))
            if len(entries) >= 4:
                break
        if entries:
            groups.append({"title": domain, "entries": entries})
    return groups


def _fnd_ebi_groups(tool_root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(tool_root.glob("fnd-ebi.*.json")):
        payload = _safe_json_object(path)
        domain = _as_text(payload.get("domain"))
        if not domain:
            continue
        entries.append(_panel_entry(label=domain, meta=_as_text(payload.get("site_root"))))
    return [{"title": "Profiles", "entries": entries}] if entries else []


def _tool_groups(tool_root: Path, *, surface_id: str, tool_slug: str, member_files: list[str], active_member: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    if member_files:
        groups.append(
            {
                "title": "Files",
                "entries": [
                    _panel_entry(label=file_name, active=file_name == active_member)
                    for file_name in member_files
                ],
            }
        )
    if tool_slug == "aws-csm":
        groups.extend(_aws_csm_domain_groups(tool_root))
    elif surface_id == FND_EBI_TOOL_SURFACE_ID:
        groups.extend(_fnd_ebi_groups(tool_root))
    return groups


def build_system_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    file_entries: list[dict[str, Any]],
    active_document: Any | None,
    selected_datum: Any | None,
    selected_object: dict[str, Any] | None,
    activity_projection: Any,
    profile_summary: PublicationTenantSummary,
) -> dict[str, Any]:
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    selected_datum_payload = _selected_datum_payload(selected_datum)
    actions: list[dict[str, Any]] = []
    if isinstance(selected_datum_payload, dict) and _as_text(selected_datum_payload.get("primary_value_token")):
        actions.append(
            _panel_action(
                label="Copy Hyphae Value",
                action_kind="copy_text",
                value=selected_datum_payload.get("primary_value_token"),
            )
        )
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "SYSTEM",
        "context_items": _system_context_items(
            shell_state=shell_state,
            active_document=active_document,
            selected_datum=selected_datum,
            selected_object=selected_object,
        ),
        "verb_tabs": _verb_tab_entries(
            portal_scope=portal_scope,
            shell_state=shell_state,
            requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
        ),
        "groups": _system_selection_groups(
            portal_scope=portal_scope,
            shell_state=shell_state,
            file_entries=file_entries,
            active_document=active_document,
            active_file_key=active_file_key,
            selected_datum=selected_datum,
            selected_object=selected_object,
            activity_projection=activity_projection,
            profile_summary=profile_summary,
        ),
        "actions": actions,
    }


def build_tool_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    private_dir: str | Path | None,
    surface_id: str,
    active_document: Any | None,
    selected_datum: Any | None,
    selected_object: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
    title: str,
) -> dict[str, Any]:
    del data_dir, public_dir, active_document, selected_datum, selected_object, tool_rows
    root = _path_or_none(private_dir)
    tool_slug = _tool_root_slug_for_surface(surface_id)
    tool_root = None
    if root is not None and tool_slug:
        candidate_roots = [root / "utilities" / "tools" / tool_slug]
        for candidate in candidate_roots:
            if candidate.exists():
                tool_root = candidate
                break
        if tool_root is None:
            tool_root = candidate_roots[0]
    collection_file = ""
    member_files: list[str] = []
    if tool_root is not None and tool_root.exists():
        collection_file, member_files = _tool_collection_payload(tool_root, tool_slug=tool_slug)
    active_member = "spec.json" if "spec.json" in member_files else (member_files[0] if member_files else "")
    context_items = [{"label": "Sandbox", "value": title.upper()}]
    if collection_file:
        context_items.append({"label": "File", "value": collection_file})
    if active_member:
        context_items.append({"label": "Mediation", "value": active_member})
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": title.upper(),
        "context_items": context_items,
        "verb_tabs": _verb_tab_entries(
            portal_scope=portal_scope,
            shell_state=shell_state,
            requested_surface_id=surface_id,
        ),
        "groups": _tool_groups(
            tool_root or Path("/nonexistent"),
            surface_id=surface_id,
            tool_slug=tool_slug,
            member_files=member_files,
            active_member=active_member,
        ) if tool_slug else [],
        "actions": [],
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
    authority_db_file: str | Path | None = None,
    authority_mode: str = "filesystem",
) -> dict[str, Any]:
    projection = read_system_workbench_projection(
        portal_scope=portal_scope,
        data_dir=data_dir,
        public_dir=public_dir,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
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
    directive_context = _workspace_directive_context(
        portal_scope=portal_scope,
        active_document=active_document,
        selected_datum=selected_datum,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    activity_projection = _audit_service(
        audit_storage_file,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    ).read_recent_activity_projection()
    profile_summary = _profile_summary(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        data_dir=data_dir,
        public_dir=public_dir,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
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
        if directive_context is not None:
            document_payload["directive_context"] = directive_context
        workspace["document"] = document_payload

    surface_payload = {
        "schema": SYSTEM_ROOT_SURFACE_SCHEMA,
        "kind": "system_workspace",
        "title": "System",
        "subtitle": "Datum-file workbench for the system sandbox.",
        "workspace": workspace,
    }
    control_panel = build_system_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        file_entries=file_entries,
        active_document=active_document,
        selected_datum=selected_datum,
        selected_object=selected_object,
        activity_projection=activity_projection,
        profile_summary=profile_summary,
    )
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "mediation_panel" if shell_state.verb == VERB_MEDIATE else "summary_panel",
        "title": "Mediation" if shell_state.verb == VERB_MEDIATE else "Interface Panel",
        "summary": "Mediation is bound to the current focus subject." if shell_state.verb == VERB_MEDIATE else "The interface panel stays collapsed during ordinary navigation.",
        "visible": shell_state.verb == VERB_MEDIATE,
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
    if directive_context is not None:
        inspector["sections"].append(_directive_context_section(directive_context))
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
        "directive_context": directive_context,
        "projection": projection,
    }


__all__ = [
    "build_system_workspace_bundle",
    "build_tool_control_panel",
    "build_workspace_file_entries",
    "read_system_workbench_projection",
]
