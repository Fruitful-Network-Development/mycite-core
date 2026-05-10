from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from pathlib import Path
from threading import Lock
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    SYSTEM_ROOT_SURFACE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    attach_region_family_contract,
)
from MyCiteV2.instances._shared.runtime.portal_workbench import (
    build_datum_file_workbench,
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
    FOCUS_LEVEL_DATUM,
    FOCUS_LEVEL_FILE,
    FOCUS_LEVEL_OBJECT,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
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
    TRANSITION_BACK_OUT,
    TRANSITION_SET_VERB,
    VERB_INVESTIGATE,
    VERB_MANIPULATE,
    VERB_MEDIATE,
    VERB_NAVIGATE,
    build_portal_shell_request_payload,
    canonical_query_for_shell_state,
    anchor_file_key_for_sandbox,
    focus_level_for_shell_state,
    sandbox_id_for_file_key,
    segment_id_for_level,
)
from MyCiteV2.packages.modules.shared.scalars import as_text

_DIRECTIVE_CONTEXT_TOOL_ID = "system_workspace"
_WORKBENCH_PROJECTION_CACHE_LOCK = Lock()
_WORKBENCH_PROJECTION_CACHE_MAX = 8
_WORKBENCH_PROJECTION_CACHE: "OrderedDict[tuple[str, str, int], DatumWorkbenchProjection]" = OrderedDict()


def _path_or_none(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {as_text(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return as_text(value)


def _workbench_cache_key(*, tenant_id: str, authority_db_file: str | Path | None) -> tuple[str, str, int] | None:
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return None
    try:
        mtime_ns = authority_path.stat().st_mtime_ns
    except OSError:
        return None
    return (tenant_id, str(authority_path.resolve()), int(mtime_ns))


def _cache_get_workbench_projection(cache_key: tuple[str, str, int]) -> DatumWorkbenchProjection | None:
    with _WORKBENCH_PROJECTION_CACHE_LOCK:
        projection = _WORKBENCH_PROJECTION_CACHE.get(cache_key)
        if projection is not None:
            _WORKBENCH_PROJECTION_CACHE.move_to_end(cache_key)
        return projection


def _cache_set_workbench_projection(cache_key: tuple[str, str, int], projection: DatumWorkbenchProjection) -> None:
    with _WORKBENCH_PROJECTION_CACHE_LOCK:
        _WORKBENCH_PROJECTION_CACHE[cache_key] = projection
        _WORKBENCH_PROJECTION_CACHE.move_to_end(cache_key)
        while len(_WORKBENCH_PROJECTION_CACHE) > _WORKBENCH_PROJECTION_CACHE_MAX:
            _WORKBENCH_PROJECTION_CACHE.popitem(last=False)


def _invalidate_workbench_projection_cache(*, authority_db_file: str | Path | None = None) -> None:
    authority_path = _path_or_none(authority_db_file)
    with _WORKBENCH_PROJECTION_CACHE_LOCK:
        if authority_path is None:
            _WORKBENCH_PROJECTION_CACHE.clear()
            return
        needle = str(authority_path.resolve())
        for key in [key for key in _WORKBENCH_PROJECTION_CACHE if key[1] == needle]:
            _WORKBENCH_PROJECTION_CACHE.pop(key, None)

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
    cache_key = _workbench_cache_key(tenant_id=portal_scope.scope_id, authority_db_file=authority_db_file)
    if cache_key is not None:
        cached = _cache_get_workbench_projection(cache_key)
        if cached is not None:
            return cached
    projection = DatumWorkbenchService(store).read_workbench(portal_scope.scope_id)
    if cache_key is not None:
        _cache_set_workbench_projection(cache_key, projection)
    return projection


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
    bits = [f"{as_text(key)}={as_text(item)}" for key, item in value.items() if as_text(key) and as_text(item)]
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
    document_id = as_text(getattr(active_document, "document_id", "")) if active_document is not None else ""
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
    datum_id = as_text(getattr(selected_datum, "datum_address", "")) if selected_datum is not None else ""
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
        subject_hyphae_hash=as_text((datum_identity or {}).get("hyphae_hash")),
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
        "subject_hyphae_hash": as_text((datum_identity or {}).get("hyphae_hash")),
        "resolution_status": dict(result.resolution_status),
        "warnings": warnings,
        "overlay": overlay,
    }


def _directive_context_section(directive_context: dict[str, Any]) -> dict[str, Any]:
    overlay = directive_context.get("overlay") if isinstance(directive_context.get("overlay"), dict) else None
    rows = [
        {"label": "subject level", "value": as_text(directive_context.get("subject_level")) or "document"},
        {"label": "overlay", "value": "loaded" if overlay is not None else "missing"},
        {"label": "version hash", "value": as_text(directive_context.get("subject_version_hash")) or "—"},
        {"label": "hyphae hash", "value": as_text(directive_context.get("subject_hyphae_hash")) or "—"},
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
                "value": _directive_state_summary(dict(overlay.get("provenance") or {})) or as_text(overlay.get("context_id")),
            }
        )
    return {"title": "Directive context", "rows": rows}


def _document_label(document: Any) -> str:
    if _is_system_anchor_document(document):
        return "Anthology"
    canonical_name = as_text(getattr(document, "canonical_name", ""))
    if canonical_name:
        return canonical_name
    name = as_text(getattr(document, "document_name", ""))
    tool_id = as_text(getattr(document, "tool_id", ""))
    if tool_id and name:
        return f"{tool_id}: {name}"
    return name or as_text(getattr(document, "document_id", "")) or "Document"


def _is_system_anchor_document(document: Any) -> bool:
    return bool(getattr(document, "is_anchor", False)) and _document_sandbox_id(document) == "system"


def _document_file_key(document: Any) -> str:
    if _is_system_anchor_document(document):
        return SYSTEM_ANCHOR_FILE_KEY
    return as_text(getattr(document, "document_id", ""))


def _document_sandbox_id(document: Any) -> str:
    document_id = as_text(getattr(document, "document_id", ""))
    parsed = sandbox_id_for_file_key(document_id)
    if parsed:
        return parsed
    tool_id = as_text(getattr(document, "tool_id", "")).replace("_", "-")
    return tool_id or "system"


def _system_documents(projection: DatumWorkbenchProjection) -> list[Any]:
    return [document for document in projection.documents if _document_sandbox_id(document) == "system"]


def _document_detail(document: Any) -> str:
    detail_bits = []
    source_kind = as_text(getattr(document, "source_kind", ""))
    if source_kind:
        detail_bits.append(source_kind.replace("_", " "))
    relative_path = as_text(getattr(document, "relative_path", ""))
    if relative_path:
        detail_bits.append(relative_path)
    return " · ".join(detail_bits)


def _sandbox_segment_for_entry(entry: dict[str, Any]) -> str:
    """Derive the canonical sandbox segment for a file entry.

    Recognises:
    * built-in virtual file keys (``activity``, ``profile_basics``) and the
      anchor key → ``system``
    * canonical document ids ``lv.<msn>.<sandbox>.<name>.<hash>`` →
      ``<sandbox>``
    * legacy document ids ``system:<name>`` → ``system``
    * legacy document ids ``sandbox:<tool>:<file>.json`` → ``<tool>``
    * everything else falls back to ``system`` so the entry still has a
      home in the navigation groups.
    """

    file_key = as_text(entry.get("file_key"))
    if not file_key or file_key in {
        SYSTEM_ANCHOR_FILE_KEY,
        SYSTEM_ACTIVITY_FILE_KEY,
        SYSTEM_PROFILE_BASICS_FILE_KEY,
    }:
        return "system"
    if file_key.startswith("lv."):
        parts = file_key.split(".")
        if len(parts) >= 4:
            return parts[2]
        return "system"
    if file_key.startswith("system:"):
        return "system"
    if file_key.startswith("sandbox:"):
        rest = file_key[len("sandbox:"):]
        sandbox_token = rest.split(":", 1)[0]
        return sandbox_token.replace("_", "-")
    return "system"


def build_workspace_file_entries(
    *,
    projection: DatumWorkbenchProjection,
    shell_state: PortalShellState,
    portal_scope: PortalScope,
) -> list[dict[str, Any]]:
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)

    def _shell_request_for(file_key: str) -> dict[str, Any]:
        return _entry_shell_request(
            portal_scope=portal_scope,
            shell_state=shell_state,
            transition={"kind": TRANSITION_FOCUS_FILE, "file_key": file_key},
            requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
        )

    file_entries = [
        {
            "file_key": SYSTEM_ANCHOR_FILE_KEY,
            "label": "Anthology",
            "kind": "document",
            "detail": "canonical anchor file",
            "active": active_file_key == SYSTEM_ANCHOR_FILE_KEY,
            "shell_request": _shell_request_for(SYSTEM_ANCHOR_FILE_KEY),
        },
        {
            "file_key": SYSTEM_ACTIVITY_FILE_KEY,
            "label": "Activity",
            "kind": "virtual",
            "detail": "workspace activity history",
            "active": active_file_key == SYSTEM_ACTIVITY_FILE_KEY,
            "shell_request": _shell_request_for(SYSTEM_ACTIVITY_FILE_KEY),
        },
        {
            "file_key": SYSTEM_PROFILE_BASICS_FILE_KEY,
            "label": "Profile Basics",
            "kind": "virtual",
            "detail": "workspace profile basics editor",
            "active": active_file_key == SYSTEM_PROFILE_BASICS_FILE_KEY,
            "shell_request": _shell_request_for(SYSTEM_PROFILE_BASICS_FILE_KEY),
        },
    ]
    seen_keys = {entry["file_key"] for entry in file_entries}
    for document in _system_documents(projection):
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
                "shell_request": _shell_request_for(file_key),
            }
        )
        seen_keys.add(file_key)
    return file_entries


def _selected_document(projection: DatumWorkbenchProjection, *, file_key: str) -> Any | None:
    system_documents = _system_documents(projection)
    if file_key == SYSTEM_ANCHOR_FILE_KEY:
        for document in system_documents:
            if _document_file_key(document) == SYSTEM_ANCHOR_FILE_KEY:
                return document
    for document in system_documents:
        if _document_file_key(document) == file_key:
            return document
    selected = projection.selected_document
    if selected is not None and _document_sandbox_id(selected) == "system":
        return selected
    return None


def _row_label(row: Any) -> str:
    labels = list(getattr(row, "labels", ()) or ())
    if labels:
        return as_text(labels[0])
    return as_text(getattr(row, "datum_address", "")) or "Datum"


def _row_diagnostics(row: Any) -> str:
    diagnostics = [item for item in list(getattr(row, "diagnostic_states", ()) or ()) if as_text(item)]
    return ", ".join(diagnostics) if diagnostics else "ok"


def _datum_coordinates(datum_id: object) -> dict[str, int] | None:
    token = as_text(datum_id)
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
                "label": as_text(getattr(binding, "anchor_label", "")) or as_text(getattr(binding, "anchor_address", "")),
                "object_id": as_text(getattr(binding, "anchor_address", "")) or as_text(getattr(binding, "normalized_reference_form", "")),
                "reference_form": as_text(getattr(binding, "reference_form", "")),
                "resolution_state": as_text(getattr(binding, "resolution_state", "")),
                "value_token": as_text(getattr(binding, "value_token", "")),
            }
        )
    return bindings


def _row_item(row: Any, *, selected_datum_id: str) -> dict[str, Any]:
    datum_id = as_text(getattr(row, "datum_address", ""))
    diagnostics = list(getattr(row, "diagnostic_states", ()) or ())
    return {
        "datum_id": datum_id,
        "label": _row_label(row),
        "detail": _row_diagnostics(row),
        "diagnostics": diagnostics,
        "selected": datum_id == selected_datum_id,
        "coordinates": _datum_coordinates(datum_id),
        "primary_value_token": as_text(getattr(row, "primary_value_token", "")),
        "recognized_family": as_text(getattr(row, "recognized_family", "")),
        "recognized_anchor": as_text(getattr(row, "recognized_anchor", "")),
    }


def _selected_datum_payload(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    datum_id = as_text(getattr(row, "datum_address", ""))
    return {
        "datum_id": datum_id,
        "label": _row_label(row),
        "labels": list(getattr(row, "labels", ()) or ()),
        "coordinates": _datum_coordinates(datum_id),
        "diagnostic_states": list(getattr(row, "diagnostic_states", ()) or ()),
        "primary_value_token": as_text(getattr(row, "primary_value_token", "")),
        "recognized_family": as_text(getattr(row, "recognized_family", "")),
        "recognized_anchor": as_text(getattr(row, "recognized_anchor", "")),
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
        datum_id = as_text(getattr(row, "datum_address", ""))
        if not datum_id:
            continue
        items.append(_row_item(row, selected_datum_id=selected_datum_id))
    return items


def _selected_datum(document: Any | None, *, datum_id: str) -> Any | None:
    if document is None or not datum_id:
        return None
    for row in list(getattr(document, "rows", ()) or ()):
        if as_text(getattr(row, "datum_address", "")) == datum_id:
            return row
    return None


def _object_items(row: Any | None, *, selected_object_id: str) -> list[dict[str, Any]]:
    if row is None:
        return []
    entries = []
    for binding in list(getattr(row, "reference_bindings", ()) or ()):
        object_id = as_text(getattr(binding, "anchor_address", "")) or as_text(getattr(binding, "normalized_reference_form", ""))
        if not object_id:
            continue
        entries.append(
            {
                "object_id": object_id,
                "label": as_text(getattr(binding, "anchor_label", "")) or object_id,
                "detail": as_text(getattr(binding, "resolution_state", "")) or "reference",
                "selected": object_id == selected_object_id,
            }
        )
    primary_value = as_text(getattr(row, "primary_value_token", ""))
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
        "label": as_text(label),
        "active": bool(active),
        "prefix": as_text(prefix),
    }
    meta_text = as_text(meta)
    if meta_text:
        entry["meta"] = meta_text
    href_text = as_text(href)
    if href_text:
        entry["href"] = href_text
    if shell_request is not None:
        entry["shell_request"] = shell_request
    return entry


def _panel_action(*, label: str, action_kind: str, value: object = "") -> dict[str, Any]:
    return {
        "label": as_text(label),
        "action_kind": as_text(action_kind),
        "value": as_text(value),
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


def _nimm_navigation_shell_requests(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    requested_surface_id: str,
    file_entries: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if shell_state is None:
        return {}
    sandbox_id = as_text(segment_id_for_level(shell_state, level="sandbox")) or portal_scope.scope_id
    active_file_key = as_text(segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE))
    requests: dict[str, dict[str, Any]] = {}
    if len(tuple(shell_state.focus_path)) > 1:
        requests["nav_out"] = _entry_shell_request(
            portal_scope=portal_scope,
            shell_state=shell_state,
            transition={"kind": TRANSITION_BACK_OUT},
            requested_surface_id=requested_surface_id,
        )
    else:
        requests["nav_in"] = _entry_shell_request(
            portal_scope=portal_scope,
            shell_state=shell_state,
            transition={"kind": TRANSITION_FOCUS_FILE, "file_key": anchor_file_key_for_sandbox(sandbox_id)},
            requested_surface_id=requested_surface_id,
        )
    ordered = [entry for entry in list(file_entries or []) if as_text(entry.get("file_key"))]
    active_index = next(
        (index for index, entry in enumerate(ordered) if as_text(entry.get("file_key")) == active_file_key),
        -1,
    )
    if active_index > 0:
        requests["shift_left"] = _entry_shell_request(
            portal_scope=portal_scope,
            shell_state=shell_state,
            transition={"kind": TRANSITION_FOCUS_FILE, "file_key": as_text(ordered[active_index - 1].get("file_key"))},
            requested_surface_id=requested_surface_id,
        )
    if active_index >= 0 and active_index + 1 < len(ordered):
        requests["shift_right"] = _entry_shell_request(
            portal_scope=portal_scope,
            shell_state=shell_state,
            transition={"kind": TRANSITION_FOCUS_FILE, "file_key": as_text(ordered[active_index + 1].get("file_key"))},
            requested_surface_id=requested_surface_id,
        )
    return requests


def _file_value_for_panel(*, active_file_key: str, active_document: Any | None) -> str:
    if active_document is not None:
        relative_path = as_text(getattr(active_document, "relative_path", ""))
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
                "value": _row_label(selected_datum) or as_text(getattr(selected_datum, "datum_address", "")),
            }
        )
    if selected_object is not None:
        items.append({"label": "Object", "value": as_text(selected_object.get("label")) or as_text(selected_object.get("object_id"))})
    elif shell_state.verb == VERB_MEDIATE:
        subject = as_text((shell_state.mediation_subject or {}).get("id"))
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
            label=as_text(entry.get("label")) or as_text(entry.get("file_key")),
            meta=as_text(entry.get("detail")),
            active=bool(entry.get("active")),
            href=SYSTEM_ROOT_ROUTE,
            shell_request=_entry_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                transition={"kind": TRANSITION_FOCUS_FILE, "file_key": as_text(entry.get("file_key"))},
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
    diagnostics = ", ".join([as_text(token) for token in list(item.get("diagnostics") or []) if as_text(token)])
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
    if _is_system_anchor_document(active_document):
        groups: list[dict[str, Any]] = []
        for layer_group in _anthology_layer_groups(active_document, selected_datum_id=selected_datum_id):
            entries = []
            for value_group in list(layer_group.get("value_groups") or []):
                for item in list(value_group.get("rows") or []):
                    entries.append(
                        _panel_entry(
                            label=as_text(item.get("label")) or as_text(item.get("datum_id")) or "Datum",
                            meta=_row_meta_from_item(item),
                            active=bool(item.get("selected")),
                            href=SYSTEM_ROOT_ROUTE,
                            shell_request=_entry_shell_request(
                                portal_scope=portal_scope,
                                shell_state=shell_state,
                                transition={
                                    "kind": TRANSITION_FOCUS_DATUM,
                                    "file_key": active_file_key,
                                    "datum_id": as_text(item.get("datum_id")),
                                },
                                requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
                            ),
                        )
                    )
            if entries:
                groups.append({"title": as_text(layer_group.get("label")) or "Layer", "entries": entries})
        return groups

    rows = _document_row_items(active_document, selected_datum_id=selected_datum_id)
    entries = [
        _panel_entry(
            label=as_text(item.get("label")) or as_text(item.get("datum_id")) or "Datum",
            meta=_row_meta_from_item(item) or as_text(item.get("detail")),
            active=bool(item.get("selected")),
            href=SYSTEM_ROOT_ROUTE,
            shell_request=_entry_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                transition={
                    "kind": TRANSITION_FOCUS_DATUM,
                    "file_key": active_file_key,
                    "datum_id": as_text(item.get("datum_id")),
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
            label=as_text(getattr(record, "event_type", "")) or "activity",
            meta=as_text(getattr(record, "recorded_at_unix_ms", "")),
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
        if as_text(label)
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
        for item in _object_items(selected_datum, selected_object_id=as_text((selected_object or {}).get("object_id"))):
            entries.append(
                _panel_entry(
                    label=as_text(item.get("label")) or as_text(item.get("object_id")) or "Aspect",
                    meta=as_text(item.get("detail")),
                    active=bool(item.get("selected")),
                    href=SYSTEM_ROOT_ROUTE,
                    shell_request=_entry_shell_request(
                        portal_scope=portal_scope,
                        shell_state=shell_state,
                        transition={
                            "kind": TRANSITION_FOCUS_OBJECT,
                            "file_key": active_file_key,
                            "datum_id": as_text(getattr(selected_datum, "datum_address", "")),
                            "object_id": as_text(item.get("object_id")),
                        },
                        requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
                    ),
                )
            )
        return [{"title": "Below Focus", "entries": entries}] if entries else []
    return []


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
    if isinstance(selected_datum_payload, dict) and as_text(selected_datum_payload.get("primary_value_token")):
        actions.append(
            _panel_action(
                label="Copy Hyphae Value",
                action_kind="copy_text",
                value=selected_datum_payload.get("primary_value_token"),
            )
        )
    return attach_region_family_contract(
        {
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
        },
        family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
        surface_id=SYSTEM_ROOT_SURFACE_ID,
    )


def _build_context_conditions(
    *,
    shell_state: PortalShellState | None,
    surface_label: str,
    active_document: Any | None,
    selected_datum: Any | None,
    selected_object: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build context-condition rows aligned with the canonical focus stack.

    The rows mirror the focus stack ``sandbox -> file -> datum -> object``
    so that the unified panel surface is identical in shape across SYSTEM
    and every tool surface.
    """

    active_file_key = (
        segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
        if shell_state is not None
        else ""
    )
    conditions: list[dict[str, Any]] = [
        {
            "level": FOCUS_LEVEL_FILE,
            "label": "Sandbox",
            "value": surface_label,
            "state": "active",
        },
        {
            "level": FOCUS_LEVEL_FILE,
            "label": "File",
            "value": _file_value_for_panel(
                active_file_key=active_file_key,
                active_document=active_document,
            ),
            "state": "focused" if active_document is not None or active_file_key else "default",
            "metadata": {
                "source_kind": as_text(getattr(active_document, "source_kind", "")) if active_document is not None else "",
                "relative_path": as_text(getattr(active_document, "relative_path", "")) if active_document is not None else "",
            },
        },
    ]

    if selected_datum is not None:
        datum_id = as_text(getattr(selected_datum, "datum_address", ""))
        conditions.append(
            {
                "level": FOCUS_LEVEL_DATUM,
                "label": "Datum",
                "value": _row_label(selected_datum) or datum_id,
                "state": "selected",
                "coordinates": _datum_coordinates(datum_id),
            }
        )

    if isinstance(selected_object, dict) and (selected_object.get("label") or selected_object.get("object_id")):
        conditions.append(
            {
                "level": FOCUS_LEVEL_OBJECT,
                "label": "Object",
                "value": as_text(selected_object.get("label")) or as_text(selected_object.get("object_id")),
                "state": "selected",
            }
        )
    else:
        verb = getattr(shell_state, "verb", None) if shell_state is not None else None
        if verb == VERB_MEDIATE:
            subject = as_text((shell_state.mediation_subject or {}).get("id"))
            if subject:
                conditions.append(
                    {
                        "level": "mediation",
                        "label": "Mediation",
                        "value": subject,
                        "state": "active",
                    }
                )

    return conditions


def _build_nimm_aitas_control_section(
    *,
    shell_state: PortalShellState | None,
    directive_context: dict[str, Any] | None,
    nimm_directive: str | None,
    aitas_state: dict[str, Any] | None,
    portal_scope: PortalScope,
    surface_id: str,
    file_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build unified NIMM-AITAS control section with stacked facets."""

    context = dict(directive_context or {})
    overlay = dict(context.get("overlay") or {})
    nimm_state = dict(overlay.get("nimm_state") or {})
    aitas_state_overlay = dict(overlay.get("aitas_state") or aitas_state or {})
    verb_value = getattr(shell_state, "verb", "") if shell_state is not None else ""
    focus_subject_id = ""
    if shell_state is not None:
        focus_subject_id = as_text((shell_state.focus_subject or {}).get("id"))
    verb_shell_requests = (
        _verb_tab_entries(
            portal_scope=portal_scope,
            shell_state=shell_state,
            requested_surface_id=surface_id,
        )
        if shell_state is not None
        else []
    )
    nav_shell_requests = _nimm_navigation_shell_requests(
        portal_scope=portal_scope,
        shell_state=shell_state,
        requested_surface_id=surface_id,
        file_entries=file_entries,
    )

    return {
        "title": "Directive Control",
        "collapsible": True,
        "default_state": "expanded",
        "facets": [
            {
                "facet_id": "nimm_directive",
                "label": "NIMM Directive",
                "subsections": [
                    {
                        "label": "Verb",
                        "value": verb_value,
                        "editable": True,
                        "control_type": "tabs",
                        "options": [VERB_NAVIGATE, VERB_INVESTIGATE, VERB_MEDIATE, VERB_MANIPULATE],
                        "shell_requests": verb_shell_requests,
                    },
                    {
                        "label": "Operation",
                        "value": as_text(nimm_state.get("operation")) or "—",
                        "editable": False,
                        "control_type": "display",
                    },
                    {
                        "label": "Target",
                        "value": focus_subject_id or portal_scope.scope_id,
                        "editable": False,
                        "control_type": "display",
                    },
                    {
                        "label": "NAV",
                        "value": "Directional shell controls",
                        "editable": True,
                        "control_type": "nav_arrows",
                        "shell_requests": nav_shell_requests,
                    },
                ],
            },
            {
                "facet_id": "aitas_state",
                "label": "AITAS State",
                "subsections": [
                    {
                        "label": "Intention Token",
                        "value": as_text(aitas_state_overlay.get("intention_rule_id") or aitas_state_overlay.get("intention_token")),
                        "editable": True,
                        "control_type": "select",
                        "options": [],  # Runtime-provided
                    },
                    {
                        "label": "Time Directive",
                        "value": as_text(aitas_state_overlay.get("time_directive")),
                        "editable": True,
                        "control_type": "input",
                    },
                    {
                        "label": "Archetype Family",
                        "value": as_text(aitas_state_overlay.get("archetype_family_id")),
                        "editable": True,
                        "control_type": "select",
                        "options": [],
                    },
                    {
                        "label": "Attention Node",
                        "value": as_text(aitas_state_overlay.get("attention_node_id")),
                        "editable": True,
                        "control_type": "input",
                    },
                ],
            },
            {
                "facet_id": "envelope_state",
                "label": "Directive Context",
                "subsections": [
                    {
                        "label": "Context ID",
                        "value": as_text(overlay.get("context_id")),
                        "editable": False,
                        "control_type": "display",
                    },
                    {
                        "label": "Subject Level",
                        "value": as_text(context.get("subject_level")),
                        "editable": False,
                        "control_type": "display",
                    },
                    {
                        "label": "Version Hash",
                        "value": as_text(context.get("subject_version_hash")),
                        "editable": False,
                        "control_type": "display",
                        "copyable": True,
                    },
                    {
                        "label": "Hyphae Hash",
                        "value": as_text(context.get("subject_hyphae_hash")),
                        "editable": False,
                        "control_type": "display",
                        "copyable": True,
                    },
                    {
                        "label": "Overlay Status",
                        "value": "loaded" if overlay else "missing",
                        "editable": False,
                        "control_type": "badge",
                    },
                ],
            },
        ],
    }


def _build_terminal_control_interface(
    *,
    shell_state: PortalShellState | None,
    directive_context: dict[str, Any] | None,
    enabled: bool = False,
) -> dict[str, Any]:
    """Build terminal-style directive injection interface.

    The terminal section is hidden by default. Tools opt in by passing
    ``tool_extensions["directive_terminal_enabled"]=True`` to
    ``build_unified_control_panel``.

    When enabled, the ``inject_directive`` quick-action is wired to dispatch
    ``action_kind="inject_directive"`` with the terminal textarea value as
    ``directive_text``. Other quick-actions (Validate, Clear Overlay, Export)
    remain disabled until their backend routes are implemented.
    """

    return {
        "title": "Directive Terminal",
        "visible": bool(enabled),
        "collapsible": True,
        "default_state": "expanded" if enabled else "collapsed",
        "interface": {
            "mode": "command",
            "placeholder": "> inject directive... (e.g. med;cts_gis:1-1-2)",
            "help_text": "Enter a NIMM directive. Ctrl+Enter to inject.",
            "disabled": not enabled,
            "disabled_reason": None if enabled else "directive_terminal_not_enabled",
        },
        "quick_actions": [
            {
                "action_id": "inject_directive",
                "label": "Inject",
                "shortcut": "Ctrl+Enter",
                "disabled": not enabled,
                "disabled_reason": None if enabled else "directive_terminal_not_enabled",
                # When enabled, the frontend reads textarea value and dispatches:
                # ctx.dispatchToolAction({ action_kind: "inject_directive", directive_text: <value> })
                "action_kind": "inject_directive" if enabled else None,
            },
            {
                "action_id": "validate_context",
                "label": "Validate",
                "shortcut": "Ctrl+K",
                "disabled": True,
                "disabled_reason": "validate_context_route_not_wired",
            },
            {
                "action_id": "clear_overlay",
                "label": "Clear Overlay",
                "disabled": True,
                "disabled_reason": "clear_overlay_route_not_wired",
            },
            {
                "action_id": "export_envelope",
                "label": "Export Envelope",
                "disabled": True,
                "disabled_reason": "export_envelope_route_not_wired",
            },
        ],
        "history": {
            "show": True,
            "max_items": 10,
            "items": [],
        },
    }


_NAVIGATION_GROUP_SYSTEM_SANDBOX_LABEL = "Sandbox: system"


def _navigation_group_label_for_sandbox(sandbox: str) -> str:
    return f"Sandbox: {sandbox}" if sandbox else "Sandbox: system"


def _navigation_group_sort_key(sandbox: str) -> tuple[int, str]:
    if sandbox == "system":
        return (0, "")
    return (1, sandbox)


def _file_entries_to_navigation_groups(
    *,
    file_entries: list[dict[str, Any]],
    portal_scope: PortalScope,
    shell_state: PortalShellState,
) -> list[dict[str, Any]]:
    """Convert file entries to navigation groups, one group per sandbox.

    Groups appear in canonical order: ``system`` first, then alphabetical
    tool sandboxes. Each entry inherits its file-level ``shell_request`` so
    clicks always dispatch ``focus_file``.
    """

    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in file_entries:
        sandbox = _sandbox_segment_for_entry(entry) or "system"
        grouped.setdefault(sandbox, []).append(
            _panel_entry(
                label=as_text(entry.get("label")) or as_text(entry.get("file_key")),
                meta=as_text(entry.get("detail")),
                active=bool(entry.get("active")),
                href=entry.get("href") or "",
                shell_request=entry.get("shell_request"),
            )
        )

    if not grouped:
        return []

    out: list[dict[str, Any]] = []
    for sandbox in sorted(grouped.keys(), key=_navigation_group_sort_key):
        out.append(
            {
                "title": _navigation_group_label_for_sandbox(sandbox),
                "entries": grouped[sandbox],
            }
        )
    return out


def _workbench_state_context_row(workbench_state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(workbench_state, dict):
        return None
    reflection = workbench_state.get("state_reflection")
    if not isinstance(reflection, dict):
        reflection = workbench_state
    current_file = as_text(reflection.get("current_file"))
    current_datum = as_text(reflection.get("current_datum"))
    current_object = as_text(reflection.get("current_object"))
    current_sandbox = as_text(reflection.get("current_sandbox"))
    value = current_object or current_datum or current_file or current_sandbox
    if not value:
        return None
    return {
        "level": "workbench_state",
        "label": "Workbench",
        "value": value,
        "state": "reflecting",
        "metadata": {
            "current_sandbox": current_sandbox,
            "current_file": current_file,
            "current_datum": current_datum,
            "current_object": current_object,
            "aitas": _json_safe(reflection.get("aitas")),
            "nimm": _json_safe(reflection.get("nimm")),
        },
    }


def build_unified_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    surface_id: str,
    surface_label: str,
    active_document: Any | None = None,
    selected_datum: Any | None = None,
    selected_object: dict[str, Any] | None = None,
    directive_context: dict[str, Any] | None = None,
    nimm_directive: str | None = None,
    aitas_state: dict[str, Any] | None = None,
    file_entries: list[dict[str, Any]] | None = None,
    navigation_groups: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    workbench_state: dict[str, Any] | None = None,
    tool_extensions: dict[str, Any] | None = None,
    context_controls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the unified control panel following canonical contract v2.

    Replaces every per-tool control-panel builder. Returns a control
    panel payload with portal identity, context conditions (including
    the optional ``workbench_state`` row), NIMM/AITAS facets, the
    directive terminal (opt-in), navigation groups (file_entries are
    auto-grouped by sandbox when no explicit groups are passed), and a
    free-form ``tool_extensions`` map projected as additional facets in
    the renderer.
    """

    portal_identity = {
        "portal_instance_id": portal_scope.scope_id,
        "portal_domain": getattr(portal_scope, "scope_domain", "") or "",
        "tenant_id": portal_scope.scope_id,
        "build_id": getattr(portal_scope, "build_id", "") or "",
        "host_shape": getattr(portal_scope, "host_shape", "") or "local",
    }

    context_conditions = _build_context_conditions(
        shell_state=shell_state,
        surface_label=surface_label,
        active_document=active_document,
        selected_datum=selected_datum,
        selected_object=selected_object,
    )

    workbench_row = _workbench_state_context_row(workbench_state)
    if workbench_row is not None:
        context_conditions.append(workbench_row)

    nimm_aitas_control = _build_nimm_aitas_control_section(
        shell_state=shell_state,
        directive_context=directive_context,
        nimm_directive=nimm_directive,
        aitas_state=aitas_state,
        portal_scope=portal_scope,
        surface_id=surface_id,
        file_entries=file_entries,
    )
    if context_controls is not None:
        nimm_aitas_control["context_controls"] = list(context_controls)

    extensions = dict(tool_extensions or {})
    terminal_enabled = bool(extensions.pop("directive_terminal_enabled", False))
    terminal_control = _build_terminal_control_interface(
        shell_state=shell_state,
        directive_context=directive_context,
        enabled=terminal_enabled,
    )

    resolved_navigation_groups = list(navigation_groups or [])
    if file_entries:
        derived_file_groups = _file_entries_to_navigation_groups(
            file_entries=file_entries,
            portal_scope=portal_scope,
            shell_state=shell_state,
        )
        if navigation_groups:
            resolved_navigation_groups.extend(derived_file_groups)
        else:
            resolved_navigation_groups = derived_file_groups

    return attach_region_family_contract(
        {
            "schema": "mycite.v2.portal.shell.region.control_panel.v2",
            "kind": "unified_directive_panel",
            "title": "Control Panel",
            "surface_label": surface_label,
            "portal_identity": portal_identity,
            "context_conditions": context_conditions,
            "nimm_aitas_control": nimm_aitas_control,
            "terminal_control": terminal_control,
            "navigation_groups": resolved_navigation_groups,
            "actions": list(actions or []),
            "workbench_state": dict(workbench_state) if isinstance(workbench_state, dict) else None,
            "tool_extensions": extensions,
        },
        family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
        surface_id=surface_id,
    )


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
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    projection = read_system_workbench_projection(
        portal_scope=portal_scope,
        data_dir=data_dir,
        public_dir=public_dir,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    system_documents = _system_documents(projection)
    file_entries = build_workspace_file_entries(
        projection=projection,
        shell_state=shell_state,
        portal_scope=portal_scope,
    )
    active_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    selected_datum_id = segment_id_for_level(shell_state, level=FOCUS_LEVEL_DATUM)
    selected_object_id = segment_id_for_level(shell_state, level=FOCUS_LEVEL_OBJECT)
    anchor_document = _selected_document(projection, file_key=SYSTEM_ANCHOR_FILE_KEY)
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
            "document_id": as_text(getattr(active_document, "document_id", "")),
            "label": _document_label(active_document),
            "detail": _document_detail(active_document),
            "diagnostic_totals": dict(getattr(active_document, "diagnostic_totals", {}) or {}),
            "rows": _document_row_items(active_document, selected_datum_id=selected_datum_id),
            "selected_datum": _selected_datum_payload(selected_datum),
            "selected_object": selected_object,
        }
        if _is_system_anchor_document(active_document):
            document_payload["presentation"] = "anthology_layered_table"
            document_payload["summary"] = "Canonical system anchor file rendered as a layered datum table."
            document_payload["interface_panel_hint"] = (
                "Select a datum row to view its structural coordinates, bindings, and raw payload."
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
    # Build actions list
    actions: list[dict[str, Any]] = []
    selected_datum_payload = _selected_datum_payload(selected_datum)
    if isinstance(selected_datum_payload, dict) and as_text(selected_datum_payload.get("primary_value_token")):
        actions.append(
            _panel_action(
                label="Copy Hyphae Value",
                action_kind="copy_text",
                value=selected_datum_payload.get("primary_value_token"),
            )
        )

    workbench_attention = selected_object_id or selected_datum_id or active_file_key or "system"
    system_workbench_state = {
        "state_reflection": {
            "current_sandbox": "system",
            "current_file": active_file_key or "",
            "current_datum": selected_datum_id or "",
            "current_object": selected_object_id or "",
            "aitas": {
                "attention": workbench_attention,
                "intention": shell_state.verb or VERB_NAVIGATE,
                "time": "current",
                "archetype": "system_workspace",
            },
            "nimm": {
                "directive": shell_state.verb or VERB_NAVIGATE,
                "actions": [action.get("action_kind") or action.get("kind") or action.get("label") for action in actions],
            },
        },
    }

    file_navigation_groups = _file_entries_to_navigation_groups(
        file_entries=file_entries,
        portal_scope=portal_scope,
        shell_state=shell_state,
    )
    additional_navigation_groups: list[dict[str, Any]] = []
    if active_file_key and active_file_key not in {SYSTEM_ACTIVITY_FILE_KEY, SYSTEM_PROFILE_BASICS_FILE_KEY}:
        additional_navigation_groups = _system_selection_groups(
            portal_scope=portal_scope,
            shell_state=shell_state,
            file_entries=[],
            active_document=active_document,
            active_file_key=active_file_key,
            selected_datum=selected_datum,
            selected_object=selected_object,
            activity_projection=activity_projection,
            profile_summary=profile_summary,
        )
    elif active_file_key == SYSTEM_ACTIVITY_FILE_KEY:
        additional_navigation_groups = _system_activity_groups(activity_projection)
    elif active_file_key == SYSTEM_PROFILE_BASICS_FILE_KEY:
        additional_navigation_groups = _system_profile_groups(profile_summary)

    control_panel = build_unified_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=SYSTEM_ROOT_SURFACE_ID,
        surface_label="SYSTEM",
        active_document=active_document,
        selected_datum=selected_datum,
        selected_object=selected_object,
        directive_context=directive_context,
        navigation_groups=file_navigation_groups + additional_navigation_groups,
        actions=actions,
        workbench_state=system_workbench_state,
    )
    interface_panel = attach_region_family_contract(
        {
        "schema": PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
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
                    {"label": "focus subject", "value": as_text((shell_state.focus_subject or {}).get("id")) or portal_scope.scope_id},
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
        },
        family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
        surface_id=SYSTEM_ROOT_SURFACE_ID,
    )
    if directive_context is not None:
        interface_panel["sections"].append(_directive_context_section(directive_context))
    workbench = build_datum_file_workbench(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=SYSTEM_ROOT_SURFACE_ID,
        sandbox_id="system",
        sandbox_label="SYSTEM",
        anchor_document=anchor_document,
        selected_document=active_document,
        sandbox_documents=system_documents,
        title="System Datum-File Workbench",
        subtitle="SYSTEM owns the core datum-file workbench for the system sandbox.",
        visible=True,
        extra_payload={
            "surface_payload": surface_payload,
            "aitas": system_workbench_state["state_reflection"]["aitas"],
            "nimm": system_workbench_state["state_reflection"]["nimm"],
        },
    )
    return {
        "page_title": "System",
        "page_subtitle": "Datum-file workbench for the system sandbox.",
        "surface_payload": surface_payload,
        "control_panel": control_panel,
        "workbench": workbench,
        "interface_panel": interface_panel,
        "active_document": active_document,
        "selected_datum": selected_datum,
        "selected_object": selected_object,
        "directive_context": directive_context,
        "projection": projection,
    }


__all__ = [
    "build_system_workspace_bundle",
    "build_unified_control_panel",
    "build_workspace_file_entries",
    "read_system_workbench_projection",
    "_invalidate_workbench_projection_cache",
]
