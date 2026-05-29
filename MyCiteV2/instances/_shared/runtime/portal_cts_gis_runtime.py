from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import threading
from collections import OrderedDict
from pathlib import Path
from time import perf_counter
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
    run_document_workbench_action,
)
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
    _nimm_navigation_shell_requests,
    build_unified_control_panel,
)
from MyCiteV2.instances._shared.runtime.portal_workbench import (
    build_datum_file_workbench,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA,
    CTS_GIS_TOOL_REQUEST_SCHEMA,
    CTS_GIS_TOOL_SURFACE_SCHEMA,
    PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    attach_region_family_contract,
    tool_exposure_configured,
    tool_exposure_enabled,
)

# NOTE: FilesystemSystemDatumStoreAdapter is intentionally NOT imported. The
# runtime is MOS-only per docs/contracts/mos_authority_enforcement.md.
from MyCiteV2.packages.adapters.sql import SqliteAuditLogAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.structures.samras import (
    InvalidSamrasStructure,
    find_structure_authorities,
    reconstruct_structure_from_rows,
    select_preferred_structure_authority,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis import (
    CTS_GIS_MANIPULATION_STAGE_SCHEMA,
    CTS_GIS_STAGE_INSERT_SCHEMA,
    CTS_GIS_STAGED_INSERT_STATE_SCHEMA,
    CtsGisMutationError,
    CtsGisMutationService,
    CtsGisReadOnlyService,
    build_compiled_artifact,
    build_cts_gis_source_layout_summary,
    compiled_artifact_path,
    evict_compiled_artifact_read_cache,
    read_admin_profile_static_from_mos,
    read_compiled_artifact_cached,
    read_district_profile_static_from_mos,
    validate_compiled_artifact,
    validate_cts_gis_source_layout,
    write_compiled_artifact,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    CTS_GIS_NAV_MODE_DIRECTORY as _CTS_GIS_NAV_MODE_DIRECTORY,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC as _CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT as _CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    DEFAULT_ARCHETYPE_FAMILY_ID as _DEFAULT_ARCHETYPE_FAMILY_ID,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    DEFAULT_INTENTION_TOKEN as _DEFAULT_INTENTION_RULE_ID,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    DEFAULT_SUPPORTING_DOCUMENT_NAME as _DEFAULT_SUPPORTING_DOCUMENT_NAME,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    DEFAULT_TIME_DIRECTIVE as _DEFAULT_TIME_DIRECTIVE,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    as_text as _as_text,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    canonical_runtime_intention_rule_id,
    canonical_service_intention_token,
)
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService

# Presumed default attention node for the CTS-GIS Garland wireframe.
# Per the daemon-load contract: when the Garland tab loads with no
# explicit attention selection, the runtime resolves the relative
# SAMRAS address "1-1-2" through the CTS-GIS spatial context, which
# yields the Ohio root administrative node "3-2-3-17". The
# administrative_node_profile then mediates on this node by default.
# Until the compiled artifact carries this default explicitly, the
# wireframe build path uses this constant when the resolved attention
# falls below it (i.e. when the artifact's default lands on a child
# node such as a county).
CTS_GIS_PRESUMED_ATTENTION_NODE_ID = "3-2-3-17"
import logging

from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.packages.state_machine.lens import SamrasTitleLens

_log = logging.getLogger("mycite.portal_host")
from MyCiteV2.packages.state_machine.nimm import (
    CTS_GIS_CANONICAL_ACTIONS,
    CTS_GIS_MUTATION_ACTION_ALIASES,
    NIMM_VERB_FRAME_ENGAGEMENT,
    StagingArea,
    build_chronology_matrix_component_frame,
    build_component_group_frame,
    build_geospatial_component_frame,
    build_listing_component_frame,
    build_profile_component_frame,
    cts_gis_runtime_action_kind,
    normalize_mutation_lifecycle_action,
    parse_directive_text,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_ENTRYPOINT_ID,
    CTS_GIS_TOOL_ROUTE,
    CTS_GIS_TOOL_SURFACE_ID,
    FOCUS_LEVEL_FILE,
    PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
    PORTAL_SHELL_REQUEST_SCHEMA,
    TOOL_ANCHOR_FILE_KEY,
    TRANSITION_FOCUS_FILE,
    PortalScope,
    PortalShellState,
    build_portal_shell_request_payload,
    normalize_runtime_shell_action_request_payload,
    normalize_runtime_shell_surface_request_payload,
    resolve_portal_tool_registry_entry,
    segment_id_for_level,
)

_CANONICAL_TOOL_PUBLIC_ID = "cts_gis"
_CANONICAL_TOOL_SLUG = "cts-gis"
_CANONICAL_TOOL_ANCHOR_PATTERN = "tool.*.cts-gis.json"
_LEGACY_DOCUMENT_PREFIX = "sandbox:" + ("map" + "s") + ":"
# _DATUM_STORE_BY_DATA_DIR cache removed — filesystem-backed datum store
# is no longer used at runtime. The MOS authority is the sole source of
# truth per docs/contracts/mos_authority_enforcement.md.
_DATUM_STORE_BY_AUTHORITY_DB: dict[str, SqliteSystemDatumStoreAdapter] = {}
# Workbench projection cache: keyed by (db_file_str, tenant_id) → (db_mtime_ns, bundle_dict)
_WORKBENCH_PROJECTION_CACHE: dict[tuple[str, str], tuple[int, dict]] = {}
# Service-surface-from-compiled-artifact cache: keyed by
# (artifact_path_str, artifact_signature, canonical_tool_state_sha1) → service_surface_dict
_COMPILED_SERVICE_SURFACE_CACHE: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()
_COMPILED_SERVICE_SURFACE_CACHE_MAX = 32


def _compiled_artifact_signature(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        stat = path.stat()
    except OSError:
        return ""
    return f"{int(stat.st_mtime_ns)}:{int(stat.st_size)}"


def _canonical_tool_state(requested_tool_state: dict[str, Any] | None) -> dict[str, Any]:
    payload = requested_tool_state if isinstance(requested_tool_state, dict) else {}
    aitas = payload.get("aitas") if isinstance(payload.get("aitas"), dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    selection = payload.get("selection") if isinstance(payload.get("selection"), dict) else {}
    staged_insert = payload.get("staged_insert") if isinstance(payload.get("staged_insert"), dict) else {}
    return {
        "selected_node_id": _as_text(payload.get("selected_node_id")),
        "active_path": [_as_text(item) for item in list(payload.get("active_path") or []) if _as_text(item)],
        "aitas": {
            "time_directive": _as_text(aitas.get("time_directive")),
            "intention_rule_id": _as_text(aitas.get("intention_rule_id")),
        },
        "source": {
            "attention_document_id": _as_text(source.get("attention_document_id")),
            "precinct_district_overlay_enabled": bool(source.get("precinct_district_overlay_enabled")),
        },
        "selection": {
            "selected_row_address": _as_text(selection.get("selected_row_address")),
            "selected_feature_id": _as_text(selection.get("selected_feature_id")),
            "selected_district_id": _as_text(selection.get("selected_district_id")),
            "selected_precinct_id": _as_text(selection.get("selected_precinct_id")),
        },
        "staged_insert": {
            "staged_insert_id": _as_text(staged_insert.get("staged_insert_id")),
            "lifecycle_state": _as_text(staged_insert.get("lifecycle_state")),
        },
    }


def _canonical_tool_state_hash(requested_tool_state: dict[str, Any] | None) -> str:
    canonical = _canonical_tool_state(requested_tool_state)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def evict_compiled_service_surface_cache() -> None:
    _COMPILED_SERVICE_SURFACE_CACHE.clear()


_COMPILED_REBUILD_LOCK = threading.Lock()
_COMPILED_REBUILD_INPROGRESS: dict[str, bool] = {}
_COMPILE_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "compile_cts_gis_artifact.py"


def _async_compiled_artifact_rebuild(
    *,
    compile_script: Path,
    repo_root: Path,
    data_dir: str,
    private_dir: str,
    scope_id: str,
    inprogress_key: str,
) -> None:
    try:
        cmd: list[str] = [sys.executable, str(compile_script), "--data-dir", data_dir, "--scope-id", scope_id]
        if private_dir:
            cmd.extend(["--private-dir", private_dir])
        subprocess.run(cmd, cwd=str(repo_root), check=False, capture_output=True, timeout=600)
    except Exception:
        pass
    finally:
        with _COMPILED_REBUILD_LOCK:
            _COMPILED_REBUILD_INPROGRESS.pop(inprogress_key, None)
        evict_compiled_artifact_read_cache()
        evict_compiled_service_surface_cache()


def schedule_compiled_artifact_rebuild_async(
    *,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    scope_id: str,
    compiled_path: Path | None,
) -> bool:
    if compiled_path is None or data_dir is None:
        return False
    compile_script = _COMPILE_SCRIPT_PATH
    if not compile_script.exists():
        return False
    repo_root = compile_script.resolve().parents[2]
    inprogress_key = str(compiled_path)
    with _COMPILED_REBUILD_LOCK:
        if _COMPILED_REBUILD_INPROGRESS.get(inprogress_key):
            return False
        _COMPILED_REBUILD_INPROGRESS[inprogress_key] = True
    threading.Thread(
        target=_async_compiled_artifact_rebuild,
        kwargs={
            "compile_script": compile_script,
            "repo_root": repo_root,
            "data_dir": str(data_dir),
            "private_dir": str(private_dir) if private_dir else "",
            "scope_id": scope_id,
            "inprogress_key": inprogress_key,
        },
        daemon=True,
    ).start()
    return True


def _summary_for_workbench_document(document: Any) -> dict[str, Any]:
    if isinstance(document, dict) and isinstance(document.get("document_summary"), dict):
        summary = dict(document.get("document_summary") or {})
    elif hasattr(document, "to_summary_dict"):
        summary = dict(document.to_summary_dict())
    elif isinstance(document, dict):
        summary = dict(document)
    else:
        summary = {
            "document_id": _as_text(getattr(document, "document_id", "")),
            "document_name": _as_text(getattr(document, "document_name", "")),
            "relative_path": _as_text(getattr(document, "relative_path", "")),
            "tool_id": _as_text(getattr(document, "tool_id", "")),
            "row_count": len(list(getattr(document, "rows", ()) or ())),
        }
    metadata = summary.get("document_metadata") if isinstance(summary.get("document_metadata"), dict) else {}
    legacy_alias = _as_text(summary.get("legacy_alias")) or _as_text(metadata.get("legacy_alias"))
    canonical_name = _as_text(summary.get("canonical_name"))
    is_anchor = bool(summary.get("is_anchor"))
    summary["legacy_alias"] = legacy_alias
    summary["canonical_name"] = canonical_name
    summary["is_anchor"] = is_anchor
    return summary


def _wrap_workbench_document(document: Any) -> dict[str, Any]:
    if isinstance(document, dict) and isinstance(document.get("document_summary"), dict):
        nested_document = document.get("document")
    else:
        nested_document = document
    return {
        "document": nested_document,
        "document_summary": _summary_for_workbench_document(document),
    }


def _workbench_document_id(document: Any) -> str:
    return _as_text(_summary_for_workbench_document(document).get("document_id"))


def _workbench_document_matches(document: Any, requested_document_id: object) -> bool:
    requested = _as_text(requested_document_id)
    if not requested:
        return False
    summary = _summary_for_workbench_document(document)
    return requested in {
        _as_text(summary.get("document_id")),
        _as_text(summary.get("legacy_alias")),
    }


def _cts_gis_workbench_documents(service_surface: dict[str, Any]) -> list[dict[str, Any]]:
    raw_documents = list(service_surface.get("workbench_documents") or [])
    if not raw_documents:
        raw_documents = list(service_surface.get("documents") or [])
    return [_wrap_workbench_document(document) for document in raw_documents]


def _cts_gis_control_panel_file_entries(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    documents: list[dict[str, Any]],
    requested_surface_id: str,
) -> list[dict[str, Any]]:
    active_file_key = _as_text(segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE))
    entries: list[dict[str, Any]] = []
    for wrapped in list(documents or []):
        summary = _summary_for_workbench_document(wrapped)
        file_key = _as_text(summary.get("document_id"))
        if not file_key:
            continue
        label = _as_text(summary.get("canonical_name")) or _as_text(summary.get("document_name")) or file_key
        entries.append(
            {
                "file_key": file_key,
                "label": label,
                "detail": "anchor" if bool(summary.get("is_anchor")) else "datum document",
                "active": file_key == active_file_key,
                "shell_request": build_portal_shell_request_payload(
                    requested_surface_id=requested_surface_id,
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    transition={"kind": TRANSITION_FOCUS_FILE, "file_key": file_key},
                ),
            }
        )
    return entries
CTS_GIS_ACTION_RESULT_SCHEMA = "mycite.v2.portal.system.tools.cts_gis.action.result.v1"
CTS_GIS_TOOL_ACTION_ROUTE = "/portal/api/v2/system/tools/cts-gis/actions"
CTS_GIS_TOOL_ACTION_ENTRYPOINT_ID = "portal.system.tools.cts_gis.actions"
_ALLOWED_ACTION_KINDS = frozenset(
    {
        *CTS_GIS_CANONICAL_ACTIONS,
        "toggle_overlay",
        "stage_insert_yaml",
        "validate_stage",
        "preview_apply",
        "apply_stage",
        "discard_stage",
        "expand_structure",
        "insert_datum",
        "reorder_datum",
        "validate_manipulation_stage",
        "soundness_check",
        "engage_component_frame",
        "inject_directive",
        "rename_document",
        "delete_document",
        # Garland cascade selection actions
        # (TASK-CTS-GIS-GARLAND-CASCADE-2026-05-11 Phase 2)
        "select_district_row",
        "select_precinct_row",
    }
)


class LegacyMapsAliasUnsupportedError(ValueError):
    def __init__(self, *, fields: list[str] | None = None) -> None:
        details = ", ".join(fields or []) or "request payload"
        super().__init__(
            "Legacy CTS-GIS aliases are no longer supported in v2.5.4. "
            f"Update {details} to canonical CTS-GIS identifiers "
            "(`cts_gis`, `cts-gis`, `sandbox:cts_gis:*`, `tool.<msn>.cts-gis.json`)."
        )
        self.code = "legacy_maps_alias_unsupported"
        self.fields = tuple(fields or [])

def _path_or_none(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def _datum_store_for_authority_db(
    authority_db_file: str | Path | None,
) -> SqliteSystemDatumStoreAdapter | None:
    root = _path_or_none(authority_db_file)
    if root is None:
        return None
    cache_key = str(root.resolve())
    cached = _DATUM_STORE_BY_AUTHORITY_DB.get(cache_key)
    if cached is not None:
        return cached
    # Canonical-only write posture (2026-05-28). The legacy_alias back-compat
    # was retired ahead of schedule (commit 0c355db); live data is fully
    # canonical, and the runtime must refuse to re-persist any non-canonical
    # catalog id. Tests that exercise the apply path seed canonical fixtures;
    # read-only tests may still reference legacy-keyed seed docs (reads do not
    # validate canonicality).
    store = SqliteSystemDatumStoreAdapter(root, allow_legacy_writes=False)
    _DATUM_STORE_BY_AUTHORITY_DB[cache_key] = store
    return store


def _runtime_datum_store(
    *,
    data_dir: str | Path | None,
    authority_db_file: str | Path | None,
) -> SqliteSystemDatumStoreAdapter | None:
    # MOS-only per docs/contracts/mos_authority_enforcement.md. The
    # data_dir parameter is retained in the signature for backward
    # compatibility with callers but is no longer consulted; the
    # filesystem-backed datum store has been retired from runtime.
    return _datum_store_for_authority_db(authority_db_file)


def _cts_gis_profile_static_payloads(
    *,
    datum_store: SqliteSystemDatumStoreAdapter | None,
    tenant_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Resolve admin_profile_static + district_profile_static for the compile bake — MOS-only.

    Admin identity + district collection/membership come from MOS. There is NO
    disk admin-root read and NO carry-forward of a prior artifact's geometry: the
    disk sources and the old disk-sourced Ohio state boundary were a reverse-fit of
    retired CTS-GIS functionality and have been cut (2026-05-27). Admin geometry is
    whatever MOS provides — currently none, since no admin-state geometry datum
    lives in MOS. Returns (None, None) on failure so the compile still produces an
    artifact rather than raising.
    """
    try:
        admin_profile = read_admin_profile_static_from_mos(datum_store, tenant_id=tenant_id)
        district_profile = read_district_profile_static_from_mos(datum_store, tenant_id=tenant_id)
    except Exception as exc:
        _log.warning("cts_gis profile_static resolution failed: %s", exc)
        return None, None
    return (admin_profile or None), (district_profile or None)


def _safe_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _staged_insert_state(payload: object) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    normalized_payload = (
        dict(state.get("normalized_payload"))
        if isinstance(state.get("normalized_payload"), dict)
        else {}
    )
    last_validation = (
        dict(state.get("last_validation"))
        if isinstance(state.get("last_validation"), dict)
        else {}
    )
    last_preview = (
        dict(state.get("last_preview"))
        if isinstance(state.get("last_preview"), dict)
        else {}
    )
    structure_operation = (
        dict(state.get("structure_operation"))
        if isinstance(state.get("structure_operation"), dict)
        else {}
    )
    compiled_nimm_envelope = (
        dict(state.get("compiled_nimm_envelope"))
        if isinstance(state.get("compiled_nimm_envelope"), dict)
        else {}
    )
    last_error = (
        dict(state.get("last_error"))
        if isinstance(state.get("last_error"), dict)
        else {}
    )
    soundness_report = (
        dict(state.get("soundness_report"))
        if isinstance(state.get("soundness_report"), dict)
        else {}
    )
    return {
        "schema": _as_text(state.get("schema")) or CTS_GIS_STAGED_INSERT_STATE_SCHEMA,
        "draft_text": _as_text(state.get("draft_text")),
        "draft_format": _as_text(state.get("draft_format")) or "yaml",
        "normalized_payload": normalized_payload,
        "placeholder_title_requested": bool(state.get("placeholder_title_requested")),
        "last_validation": last_validation,
        "last_preview": last_preview,
        "structure_operation": structure_operation,
        "compiled_nimm_envelope": compiled_nimm_envelope,
        "last_error": last_error,
        "soundness_report": soundness_report,
    }


def _compile_staged_nimm_envelope(tool_state: dict[str, Any]) -> dict[str, Any]:
    staged_insert = _staged_insert_state(tool_state.get("staged_insert"))
    normalized_payload = dict(staged_insert.get("normalized_payload") or {})
    datums = list(normalized_payload.get("datums") or [])
    document_id = _as_text(normalized_payload.get("document_id"))
    if not datums or not document_id:
        return {}

    stage = StagingArea()
    for datum in datums:
        datum_mapping = dict(datum or {})
        stage = stage.stage_with_lens(
            target={
                "file_key": document_id,
                "datum_address": _as_text(datum_mapping.get("targetNodeAddress")),
                "object_ref": "",
            },
            lens=SamrasTitleLens(),
            display_value=_as_text(datum_mapping.get("title")),
        )
    envelope = stage.compile_manipulation_envelope(
        target_authority="cts_gis",
        document_id=document_id,
        aitas=dict(tool_state.get("aitas") or {}),
    ).to_dict()

    structure_operation = dict(staged_insert.get("structure_operation") or {})
    if structure_operation:
        envelope["compound_directives"] = {
            "schema": "mycite.v2.nimm.compound.v1",
            "steps": [
                {
                    "kind": "structure_space_mutation",
                    "verb": "manipulate",
                    "target_authority": "cts_gis_structure",
                    "payload": structure_operation,
                },
                {
                    "kind": "datum_mutation",
                    "directive": dict(envelope.get("directive") or {}),
                },
            ],
        }
    return envelope


def _tool_state_clone(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "nimm_directive": _as_text(payload.get("nimm_directive")),
        "active_path": [_as_text(item) for item in list(payload.get("active_path") or []) if _as_text(item)],
        "selected_node_id": _as_text(payload.get("selected_node_id")),
        "aitas": dict(payload.get("aitas") or {}),
        "source": dict(payload.get("source") or {}),
        "selection": dict(payload.get("selection") or {}),
        "staged_insert": dict(payload.get("staged_insert") or {}),
    }


def _request_tool_state_overrides(
    requested_tool_state: dict[str, Any],
    request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_payload = request_payload if isinstance(request_payload, dict) else {}
    raw_tool_state = normalized_payload.get("tool_state") if isinstance(normalized_payload.get("tool_state"), dict) else {}
    raw_aitas = raw_tool_state.get("aitas") if isinstance(raw_tool_state.get("aitas"), dict) else {}
    raw_source = raw_tool_state.get("source") if isinstance(raw_tool_state.get("source"), dict) else {}
    raw_selection = raw_tool_state.get("selection") if isinstance(raw_tool_state.get("selection"), dict) else {}
    raw_staged_insert = raw_tool_state.get("staged_insert") if isinstance(raw_tool_state.get("staged_insert"), dict) else {}
    raw_mediation = (
        normalized_payload.get("mediation_state")
        if isinstance(normalized_payload.get("mediation_state"), dict)
        else {}
    )
    overrides: dict[str, Any] = {}
    if _as_text(raw_tool_state.get("nimm_directive") or normalized_payload.get("nimm_directive")):
        overrides["nimm_directive"] = _as_text(requested_tool_state.get("nimm_directive"))
    if (
        isinstance(raw_tool_state.get("active_path"), list)
        or _as_text(raw_tool_state.get("selected_node_id"))
        or _as_text(raw_aitas.get("attention_node_id"))
        or _as_text(raw_mediation.get("attention_node_id"))
        or _as_text(normalized_payload.get("attention_node_id"))
    ):
        overrides["active_path"] = list(requested_tool_state.get("active_path") or [])
        overrides["selected_node_id"] = _as_text(requested_tool_state.get("selected_node_id"))

    aitas: dict[str, Any] = {}
    if (
        _as_text(raw_aitas.get("intention_rule_id"))
        or _as_text(raw_mediation.get("intention_token"))
        or _as_text(normalized_payload.get("intention_token"))
    ):
        aitas["intention_rule_id"] = _as_text((requested_tool_state.get("aitas") or {}).get("intention_rule_id"))
    if _as_text(raw_aitas.get("time_directive")) or isinstance(raw_mediation.get("time"), (dict, str)):
        aitas["time_directive"] = _as_text((requested_tool_state.get("aitas") or {}).get("time_directive"))
    if _as_text(raw_aitas.get("archetype_family_id")):
        aitas["archetype_family_id"] = _as_text((requested_tool_state.get("aitas") or {}).get("archetype_family_id"))
    if aitas:
        overrides["aitas"] = aitas

    source: dict[str, Any] = {}
    if (
        _as_text(raw_source.get("attention_document_id"))
        or _as_text(raw_mediation.get("attention_document_id"))
        or _as_text(normalized_payload.get("selected_document_id"))
        or _as_text(normalized_payload.get("attention_document_id"))
    ):
        source["attention_document_id"] = _as_text((requested_tool_state.get("source") or {}).get("attention_document_id"))
    if "precinct_district_overlay_enabled" in raw_source:
        source["precinct_district_overlay_enabled"] = bool(
            (requested_tool_state.get("source") or {}).get("precinct_district_overlay_enabled")
        )
    if isinstance(raw_tool_state.get("active_path"), list):
        source["requested_active_path_raw"] = [
            _as_text(item)
            for item in list((requested_tool_state.get("source") or {}).get("requested_active_path_raw") or [])
            if _as_text(item)
        ]
    if _as_text(raw_tool_state.get("selected_node_id")):
        source["requested_selected_node_id_raw"] = _as_text(
            (requested_tool_state.get("source") or {}).get("requested_selected_node_id_raw")
        )
    if source:
        overrides["source"] = source

    selection: dict[str, Any] = {}
    selected_row_requested = _as_text(raw_selection.get("selected_row_address") or normalized_payload.get("selected_row_address"))
    selected_feature_requested = _as_text(raw_selection.get("selected_feature_id") or normalized_payload.get("selected_feature_id"))
    selected_district_requested = _as_text(raw_selection.get("selected_district_id"))
    selected_precinct_requested = _as_text(raw_selection.get("selected_precinct_id"))
    context_changed = bool(
        "active_path" in overrides
        or isinstance(overrides.get("aitas"), dict)
        or isinstance(overrides.get("source"), dict)
    )
    if raw_selection or context_changed:
        selection["selected_row_address"] = _as_text((requested_tool_state.get("selection") or {}).get("selected_row_address"))
        selection["selected_feature_id"] = _as_text((requested_tool_state.get("selection") or {}).get("selected_feature_id"))
        selection["selected_row_explicit"] = bool(selected_row_requested)
        selection["selected_feature_explicit"] = bool(selected_feature_requested)
        # Garland cascade district selection — survives across mediation
        # cycles because it identifies a collection, not a SAMRAS row.
        selection["selected_district_id"] = _as_text(
            (requested_tool_state.get("selection") or {}).get("selected_district_id")
        ) or selected_district_requested
        # Phase 4 follow-up — selected_precinct_id parallels
        # selected_district_id: a precinct id (e.g. "247-17-77-121") is
        # not a SAMRAS row, so this field survives mediation finalize
        # untouched. Phase 2's `select_precinct_row` was originally
        # writing to selected_feature_id, but mediation's
        # `finalize_selection` overwrites that with SAMRAS-derived
        # feature ids — causing the panel to re-render on every click.
        selection["selected_precinct_id"] = _as_text(
            (requested_tool_state.get("selection") or {}).get("selected_precinct_id")
        ) or selected_precinct_requested
    if selection:
        overrides["selection"] = selection

    if raw_staged_insert:
        overrides["staged_insert"] = _staged_insert_state(requested_tool_state.get("staged_insert"))
    return overrides


def _merge_tool_state(base_tool_state: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = _tool_state_clone(base_tool_state)
    selected_node_overridden = False
    if "nimm_directive" in overrides:
        merged["nimm_directive"] = _as_text(overrides.get("nimm_directive")) or merged.get("nimm_directive")
    if "active_path" in overrides:
        merged["active_path"] = [_as_text(item) for item in list(overrides.get("active_path") or []) if _as_text(item)]
    if "selected_node_id" in overrides:
        merged["selected_node_id"] = _as_text(overrides.get("selected_node_id"))
        selected_node_overridden = True
    if isinstance(overrides.get("aitas"), dict):
        merged["aitas"] = {
            **dict(merged.get("aitas") or {}),
            **{key: value for key, value in dict(overrides.get("aitas") or {}).items() if value is not None},
        }
    if isinstance(overrides.get("source"), dict):
        merged["source"] = {
            **dict(merged.get("source") or {}),
            **{key: value for key, value in dict(overrides.get("source") or {}).items() if value is not None},
        }
    if isinstance(overrides.get("selection"), dict):
        merged["selection"] = {
            **dict(merged.get("selection") or {}),
            **{key: value for key, value in dict(overrides.get("selection") or {}).items() if value is not None},
        }
    if isinstance(overrides.get("staged_insert"), dict):
        merged["staged_insert"] = _staged_insert_state(overrides.get("staged_insert"))
    if selected_node_overridden:
        merged.setdefault("aitas", {})
        merged["aitas"]["attention_node_id"] = _as_text(merged.get("selected_node_id"))
    return merged


def _canonical_tool_public_id(value: object) -> str:
    token = _as_text(value).lower()
    if token in {_CANONICAL_TOOL_PUBLIC_ID, _CANONICAL_TOOL_SLUG}:
        return _CANONICAL_TOOL_PUBLIC_ID
    return token


def _is_legacy_maps_document_id(value: object) -> bool:
    return _as_text(value).startswith(_LEGACY_DOCUMENT_PREFIX)


def _contains_legacy_maps_tool_id(value: object) -> bool:
    return _as_text(value).lower() == ("map" + "s")


def _request_legacy_maps_fields(payload: dict[str, Any]) -> list[str]:
    mediation_state = payload.get("mediation_state")
    mediation_state = mediation_state if isinstance(mediation_state, dict) else {}
    tool_state = payload.get("tool_state")
    tool_state = tool_state if isinstance(tool_state, dict) else {}
    source_state = tool_state.get("source")
    source_state = source_state if isinstance(source_state, dict) else {}

    field_checks = (
        ("selected_document_id", payload.get("selected_document_id")),
        ("attention_document_id", payload.get("attention_document_id")),
        ("mediation_state.attention_document_id", mediation_state.get("attention_document_id")),
        ("tool_state.source.attention_document_id", source_state.get("attention_document_id")),
    )
    matches = [field for field, value in field_checks if _is_legacy_maps_document_id(value)]

    tool_id_checks = (
        ("tool_id", payload.get("tool_id")),
        ("tool_state.tool_id", tool_state.get("tool_id")),
        ("tool_state.source.tool_id", source_state.get("tool_id")),
    )
    matches.extend(field for field, value in tool_id_checks if _contains_legacy_maps_tool_id(value))
    return matches


def _assert_no_legacy_maps_aliases(payload: dict[str, Any]) -> None:
    fields = _request_legacy_maps_fields(payload)
    if fields:
        raise LegacyMapsAliasUnsupportedError(fields=fields)


def _active_path_from_node_id(node_id: object) -> list[str]:
    token = _as_text(node_id)
    if not token:
        return []
    parts = [part for part in token.split("-") if part]
    if not parts or not all(part.isdigit() for part in parts):
        return []
    return ["-".join(parts[:depth]) for depth in range(1, len(parts) + 1)]


def _normalize_requested_active_path(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        node_id = _as_text(item)
        if not node_id:
            continue
        if "-" in node_id and _parent_node_id(node_id) != (out[-1] if out else ""):
            break
        if not _looks_like_msn_node_id(node_id):
            break
        if not out and _node_depth(node_id) != 1:
            break
        out.append(node_id)
    return out


def _canonical_staged_selection_state(
    *,
    active_path: object,
    selected_node_id: object,
    attention_node_id: object,
) -> tuple[list[str], str]:
    normalized_active_path = _normalize_requested_active_path(active_path)
    fallback_node_id = _as_text(selected_node_id) or _as_text(attention_node_id)
    if not normalized_active_path and fallback_node_id:
        normalized_active_path = _active_path_from_node_id(fallback_node_id)
    return normalized_active_path, normalized_active_path[-1] if normalized_active_path else ""


def _normalize_tool_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    raw_tool_state = normalized_payload.get("tool_state") if isinstance(normalized_payload.get("tool_state"), dict) else {}
    raw_aitas = raw_tool_state.get("aitas") if isinstance(raw_tool_state.get("aitas"), dict) else {}
    raw_source = raw_tool_state.get("source") if isinstance(raw_tool_state.get("source"), dict) else {}
    raw_selection = raw_tool_state.get("selection") if isinstance(raw_tool_state.get("selection"), dict) else {}
    raw_staged_insert = (
        raw_tool_state.get("staged_insert")
        if isinstance(raw_tool_state.get("staged_insert"), dict)
        else {}
    )
    mediation_state = (
        normalized_payload.get("mediation_state") if isinstance(normalized_payload.get("mediation_state"), dict) else {}
    )
    active_path, selected_node_id = _canonical_staged_selection_state(
        active_path=raw_tool_state.get("active_path"),
        selected_node_id=raw_tool_state.get("selected_node_id"),
        attention_node_id=(
            raw_aitas.get("attention_node_id")
            or mediation_state.get("attention_node_id")
            or normalized_payload.get("attention_node_id")
        ),
    )
    requested_intention = (
        raw_aitas.get("intention_rule_id")
        or mediation_state.get("intention_token")
        or normalized_payload.get("intention_token")
    )
    requested_active_path_raw = [
        _as_text(item)
        for item in list(raw_tool_state.get("active_path") or [])
        if _as_text(item)
    ]
    requested_selected_node_id_raw = _as_text(raw_tool_state.get("selected_node_id"))
    return {
        "nimm_directive": _as_text(raw_tool_state.get("nimm_directive") or normalized_payload.get("nimm_directive")),
        "active_path": active_path,
        "selected_node_id": selected_node_id,
        "aitas": {
            "attention_node_id": selected_node_id,
            "intention_rule_id": canonical_runtime_intention_rule_id(
                requested_intention or _DEFAULT_INTENTION_RULE_ID,
                attention_node_id=selected_node_id,
            ),
            "time_directive": _as_text(raw_aitas.get("time_directive")) or _DEFAULT_TIME_DIRECTIVE,
            "archetype_family_id": _as_text(raw_aitas.get("archetype_family_id")) or _DEFAULT_ARCHETYPE_FAMILY_ID,
        },
        "source": {
            "attention_document_id": _as_text(
                raw_source.get("attention_document_id")
                or mediation_state.get("attention_document_id")
                or normalized_payload.get("selected_document_id")
                or normalized_payload.get("attention_document_id")
            ),
            "precinct_district_overlay_enabled": bool(raw_source.get("precinct_district_overlay_enabled")),
            "requested_active_path_raw": requested_active_path_raw,
            "requested_selected_node_id_raw": requested_selected_node_id_raw,
        },
        "selection": {
            "selected_row_address": _as_text(
                raw_selection.get("selected_row_address") or normalized_payload.get("selected_row_address")
            ),
            "selected_feature_id": _as_text(
                raw_selection.get("selected_feature_id") or normalized_payload.get("selected_feature_id")
            ),
            "selected_row_explicit": bool(
                _as_text(raw_selection.get("selected_row_address") or normalized_payload.get("selected_row_address"))
            ),
            "selected_feature_explicit": bool(
                _as_text(raw_selection.get("selected_feature_id") or normalized_payload.get("selected_feature_id"))
            ),
            # Garland cascade district selection identifier — carried through
            # the normalize step so the wireframe builder can read it.
            "selected_district_id": _as_text(raw_selection.get("selected_district_id")),
            # Phase 4 follow-up — precinct selection identifier.
            # Survives across mediation finalize because it identifies a
            # precinct collection node (e.g. "247-17-77-121"), NOT a
            # SAMRAS datum row address.
            "selected_precinct_id": _as_text(raw_selection.get("selected_precinct_id")),
        },
        "staged_insert": _staged_insert_state(raw_staged_insert),
    }


def _runtime_mode_from_request(payload: dict[str, Any] | None) -> str:
    normalized_payload = payload if isinstance(payload, dict) else {}
    requested = _as_text(normalized_payload.get("runtime_mode"))
    if requested in {_CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT, _CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC}:
        return requested
    raw_tool_state = normalized_payload.get("tool_state") if isinstance(normalized_payload.get("tool_state"), dict) else {}
    source = raw_tool_state.get("source") if isinstance(raw_tool_state.get("source"), dict) else {}
    requested = _as_text(source.get("runtime_mode") or raw_tool_state.get("runtime_mode"))
    if requested in {_CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT, _CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC}:
        return requested
    return _CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT


def _shell_action(kind: str, **payload: Any) -> dict[str, Any]:
    return {"kind": _as_text(kind), "payload": dict(payload or {})}


def _tool_action(
    action_kind: str,
    *,
    action_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lifecycle_action = normalize_mutation_lifecycle_action(action_kind)
    return {
        "route": CTS_GIS_TOOL_ACTION_ROUTE,
        "request_schema": CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA,
        "action_kind": _as_text(action_kind),
        "mutation_lifecycle_action": lifecycle_action,
        "action_payload": dict(action_payload or {}),
    }


def _dedupe_warnings(*groups: list[str] | tuple[str, ...]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            token = _as_text(item)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


def _cts_gis_action_result(
    *,
    action_kind: str,
    status: str,
    message: str,
    code: str = "",
    details: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema": CTS_GIS_ACTION_RESULT_SCHEMA,
        "action_kind": _as_text(action_kind),
        "mutation_lifecycle_action": normalize_mutation_lifecycle_action(action_kind),
        "status": _as_text(status) or "accepted",
        "message": _as_text(message),
    }
    if code:
        payload["code"] = _as_text(code)
    if isinstance(details, dict) and details:
        payload["details"] = dict(details)
    if warnings:
        payload["warnings"] = [item for item in warnings if _as_text(item)]
    if errors:
        payload["errors"] = [item for item in errors if _as_text(item)]
    return payload


def _cts_gis_contract_state(
    *,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=CTS_GIS_TOOL_SURFACE_ID)
    required_capabilities = list(tool_entry.required_capabilities) if tool_entry is not None else []
    missing_capabilities = [capability for capability in required_capabilities if capability not in portal_scope.capabilities]
    return {
        "configured": tool_exposure_configured(tool_exposure_policy, tool_id=_CANONICAL_TOOL_PUBLIC_ID),
        "enabled": tool_exposure_enabled(tool_exposure_policy, tool_id=_CANONICAL_TOOL_PUBLIC_ID),
        "required_capabilities": required_capabilities,
        "missing_capabilities": missing_capabilities,
    }


def _append_sql_audit(
    *,
    authority_db_file: str | Path | None,
    event_type: str,
    focus_subject: str,
    shell_verb: str,
    details: dict[str, Any],
) -> None:
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return
    try:
        LocalAuditService(SqliteAuditLogAdapter(authority_path)).append_record(
            {
                "event_type": event_type,
                "focus_subject": focus_subject,
                "shell_verb": shell_verb,
                "details": dict(details or {}),
            }
        )
    except Exception:
        return


def _public_stage_validation(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload or {})


def _public_stage_preview(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload or {})
    public.pop("updated_document", None)
    public.pop("persisted_catalog", None)
    return public


def _document_name_for_id(
    *,
    datum_store: SqliteSystemDatumStoreAdapter | None,
    tenant_id: str,
    document_id: str,
) -> str:
    if datum_store is None or not _as_text(document_id):
        return ""
    try:
        catalog = datum_store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
        )
    except Exception:
        return ""
    for document in catalog.documents:
        if document.document_id == _as_text(document_id):
            return document.document_name
    return ""


def _cts_gis_audit_focus_subject(tool_state: dict[str, Any]) -> str:
    staged_insert = _staged_insert_state(tool_state.get("staged_insert"))
    stage_payload = dict(staged_insert.get("normalized_payload") or {})
    last_preview = dict(staged_insert.get("last_preview") or {})
    first_insert = next(iter(list(last_preview.get("proposed_inserted_rows") or [])), {})
    node_address = (
        _as_text(first_insert.get("target_node_address"))
        or _as_text(tool_state.get("selected_node_id"))
        or _as_text((next(iter(list(stage_payload.get("datums") or [])), {}) or {}).get("targetNodeAddress"))
        or "3"
    )
    datum_address = _as_text(first_insert.get("datum_address")) or "4-2-1"
    return f"{node_address}.{datum_address}"


def _normalize_request(
    payload: dict[str, Any] | None,
) -> tuple[PortalScope, PortalShellState, dict[str, Any], dict[str, Any]]:
    portal_scope, shell_state, normalized_payload = normalize_runtime_shell_surface_request_payload(
        payload,
        expected_schema=CTS_GIS_TOOL_REQUEST_SCHEMA,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    _assert_no_legacy_maps_aliases(normalized_payload)
    return portal_scope, shell_state, normalized_payload, _normalize_tool_state(normalized_payload)


def _normalize_action_request(
    payload: dict[str, Any] | None,
) -> tuple[PortalScope, PortalShellState, dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    portal_scope, shell_state, normalized_payload, action_kind, action_payload = normalize_runtime_shell_action_request_payload(
        payload,
        expected_schema=CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    _assert_no_legacy_maps_aliases(normalized_payload)
    tool_state = _normalize_tool_state({"tool_state": normalized_payload.get("tool_state") or {}})
    action_kind = cts_gis_runtime_action_kind(action_kind)
    if action_kind not in _ALLOWED_ACTION_KINDS:
        raise ValueError(f"action_kind must be one of {sorted(_ALLOWED_ACTION_KINDS)}")
    return portal_scope, shell_state, normalized_payload, tool_state, action_kind, dict(action_payload)


def _datum_summary(
    data_dir: str | Path | None,
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
) -> dict[str, Any]:
    if data_dir is None and authority_db_file is None:
        return {
            "configured": False,
            "document_count": 0,
            "source_files": [],
            "warnings": ["data_dir_missing"],
        }
    try:
        datum_store = _runtime_datum_store(data_dir=data_dir, authority_db_file=authority_db_file)
        if datum_store is None:
            raise ValueError("data_dir_missing")
        catalog = datum_store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=portal_instance_id)
        )
    except Exception as exc:
        return {
            "configured": True,
            "document_count": 0,
            "source_files": [],
            "warnings": [f"datum_read_failed:{type(exc).__name__}"],
        }
    return {
        "configured": True,
        "document_count": catalog.document_count,
        "source_files": list(catalog.source_files),
        "warnings": list(catalog.warnings),
        "readiness_status": dict(catalog.readiness_status),
    }


def _datum_summary_from_service_surface(service_surface: dict[str, Any]) -> dict[str, Any] | None:
    summary = (
        service_surface.get("authority_catalog_summary")
        if isinstance(service_surface.get("authority_catalog_summary"), dict)
        else {}
    )
    if not summary:
        return None
    return {
        "configured": bool(summary.get("configured", True)),
        "document_count": int(summary.get("document_count") or 0),
        "source_files": list(summary.get("source_files") or []),
        "warnings": list(summary.get("warnings") or []),
        "readiness_status": dict(summary.get("readiness_status") or {}),
    }


def _cts_gis_private_tool_root(private_dir: str | Path | None) -> Path | None:
    root = _path_or_none(private_dir)
    if root is None:
        return None
    candidate = root / "utilities" / "tools" / _CANONICAL_TOOL_SLUG
    if candidate.exists() and candidate.is_dir():
        return candidate
    return candidate


# Disk-glob helpers (_cts_gis_data_tool_root, _cts_gis_source_path,
# _cts_gis_tool_anchor_path) were retired. Per
# docs/contracts/mos_authority_enforcement.md the runtime is MOS-only;
# the readiness diagnostic in _build_source_evidence now reports
# `exists=False` for the legacy disk paths because those paths have been
# archived to /srv/agentic/evidence/. Existing downstream logic handles
# the absent case gracefully (degrades to `samras_seed_missing`).


def _split_row_source(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("datum_addressing_abstraction_space"), dict):
        return dict(payload.get("datum_addressing_abstraction_space") or {})
    return dict(payload)


def _anchor_member_files(anchor_payload: dict[str, Any]) -> list[str]:
    row_source = _split_row_source(anchor_payload)
    members: list[str] = []
    for datum_address, raw in sorted(row_source.items()):
        if not _as_text(datum_address).startswith("1-0-"):
            continue
        if not isinstance(raw, list) or len(raw) < 2:
            continue
        labels = raw[1]
        if isinstance(labels, list):
            label = _as_text(labels[0] if labels else "")
            if label:
                members.append(label)
    return members


def _cts_gis_corpus_prefix(document_name: str) -> str:
    token = _as_text(document_name)
    if not token:
        return ""
    # Order matters: `.cts_gis.` is the current precinct convention,
    # `.msn-` covers both the new top-level msn-SAMRAS source datum
    # files and the existing cache files. `.fnd.` and `.cts.` are
    # kept for legacy/test-fixture compatibility.
    for marker in (".cts_gis.", ".msn-", ".fnd.", ".cts.", ".registrar"):
        if marker in token:
            return token.split(marker, 1)[0]
    if token.endswith(".json"):
        return token[:-5]
    return token


def _evidence_path_payload(path: Path | None, *, canonical_tool_id: str = "") -> dict[str, Any]:
    payload = _safe_json_object(path)
    tool_id = _canonical_tool_public_id(payload.get("tool_id"))
    if canonical_tool_id and not tool_id:
        tool_id = canonical_tool_id
    out = {
        "path": "" if path is None else str(path),
        "exists": bool(path is not None and path.exists()),
        "file": "" if path is None else path.name,
        "tool_id": tool_id,
        "payload": payload,
    }
    if "schema" in payload:
        out["schema"] = payload.get("schema")
    return out


def _supporting_document_summary(service_surface: dict[str, Any]) -> dict[str, Any]:
    document_catalog = [
        dict(item)
        for item in list(service_surface.get("document_catalog") or [])
        if isinstance(item, dict)
    ]
    for item in document_catalog:
        if _as_text(item.get("document_name")) == _DEFAULT_SUPPORTING_DOCUMENT_NAME:
            return item
    return dict(service_surface.get("selected_document") or {})


def _administrative_source_payload_from_sql(
    *,
    datum_store: SqliteSystemDatumStoreAdapter | None,
    tenant_id: str,
    document_id: str,
    document_name: str,
) -> dict[str, Any]:
    """Build the SAMRAS source payload for the supporting CTS-GIS document from
    the MOS SQL authority.

    MOS-only runtime: the disk source read was retired (returns empty), which
    starved the SAMRAS seed reconstruction even though the corpus lives in SQL.
    Reads the supporting document's rows from the authoritative catalog and
    shapes them as ``datum_addressing_abstraction_space`` (``{datum_address: raw}``)
    so ``reconstruct_structure_from_rows`` can rebuild the canonical seed.
    """
    if datum_store is None:
        return {}
    target_id = _as_text(document_id)
    target_name = _as_text(document_name)
    if not target_id and not target_name:
        return {}
    try:
        catalog = datum_store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=_as_text(tenant_id) or "fnd")
        )
    except Exception:
        _log.warning("cts_gis_source_payload_catalog_read_failed", exc_info=True)
        return {}
    for document in catalog.documents:
        doc_id = _as_text(getattr(document, "document_id", ""))
        doc_name = _as_text(getattr(document, "document_name", ""))
        if (target_id and doc_id == target_id) or (target_name and doc_name == target_name):
            doc_dict = document.to_dict() if hasattr(document, "to_dict") else {}
            space = {
                _as_text(row.get("datum_address")): row.get("raw")
                for row in (doc_dict.get("rows") or [])
                if isinstance(row, dict) and _as_text(row.get("datum_address"))
            }
            return {"datum_addressing_abstraction_space": space} if space else {}
    return {}


def _build_source_evidence(
    *,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    service_surface: dict[str, Any],
    source_layout: dict[str, Any] | None = None,
    datum_store: SqliteSystemDatumStoreAdapter | None = None,
    tenant_id: str = "",
) -> dict[str, Any]:
    selected_document = dict(service_surface.get("selected_document") or {})
    supporting_document = _supporting_document_summary(service_surface)
    supporting_document_name = _as_text(supporting_document.get("document_name")) or _DEFAULT_SUPPORTING_DOCUMENT_NAME
    corpus_prefix = _cts_gis_corpus_prefix(supporting_document_name)
    private_tool_root = _cts_gis_private_tool_root(private_dir)
    # MOS-only runtime: disk-based tool-anchor/source/cache paths are retired
    # (see docs/contracts/mos_authority_enforcement.md). _evidence_path_payload
    # below returns exists=False for each None path, and downstream readiness
    # logic degrades gracefully to `samras_seed_missing` when the legacy disk
    # artifacts are absent.
    spec_path = None if private_tool_root is None else private_tool_root / "spec.json"
    tool_anchor_path: Path | None = None
    member_files: list[str] = []
    source_path: Path | None = None
    registrar_path: Path | None = None
    administrative_cache_path: Path | None = None

    tool_spec = _evidence_path_payload(spec_path, canonical_tool_id=_CANONICAL_TOOL_PUBLIC_ID)
    tool_anchor = _evidence_path_payload(tool_anchor_path)
    tool_anchor["member_files"] = member_files
    administrative_source = _evidence_path_payload(source_path)
    administrative_source["document_id"] = _as_text(supporting_document.get("document_id"))
    administrative_source["document_name"] = supporting_document_name
    # MOS-only: source the SAMRAS reconstruction payload from the SQL authority
    # (the retired disk read above returns empty). Without this the canonical
    # seed cannot reconstruct and navigation reports blocked_invalid_magnitude
    # even though the applied corpus lives in SQL.
    if not administrative_source.get("payload"):
        sql_payload = _administrative_source_payload_from_sql(
            datum_store=datum_store,
            tenant_id=tenant_id,
            document_id=administrative_source["document_id"],
            document_name=supporting_document_name,
        )
        if sql_payload.get("datum_addressing_abstraction_space"):
            administrative_source["payload"] = sql_payload
            administrative_source["exists"] = True
    registrar_payload = _evidence_path_payload(registrar_path)
    if registrar_payload["payload"]:
        registrar_payload["payload_id"] = _as_text(registrar_payload["payload"].get("payload_id"))
        registrar_payload["target_mss_anchor_datum"] = _as_text(registrar_payload["payload"].get("target_mss_anchor_datum"))
    administrative_payload_cache = _evidence_path_payload(administrative_cache_path)
    if administrative_payload_cache["payload"]:
        administrative_payload_cache["payload_id"] = _as_text(administrative_payload_cache["payload"].get("payload_id"))
    sos_voterid_path: Path | None = None  # MOS-only: see note above
    sos_voterid_source = _evidence_path_payload(sos_voterid_path)
    sos_voterid_source["document_name"] = "sc.3-2-3-17-77-1-6-4-1-4.sos_voterid.json"
    source_layout_valid, source_layout_issues = validate_cts_gis_source_layout(source_layout)

    samras_seed_status = _as_text(selected_document.get("samras_seed_status"))
    readiness_state = "ready"
    readiness_message = "CTS-GIS evidence is ready."
    if _as_text((service_surface.get("map_projection") or {}).get("projection_state")) == "no_authoritative_cts_gis_documents":
        readiness_state = "no_authoritative_cts_gis_documents"
        readiness_message = "No authoritative CTS-GIS source document is available for the active tenant."
    elif not source_layout_valid:
        readiness_state = "source_layout_invalid"
        readiness_message = "CTS-GIS source layout does not match the required sources/ + sources/precincts/ posture."
    elif not administrative_source.get("payload"):
        # MOS-only: the seed reconstructs from the SQL-sourced administrative
        # payload, not the retired disk tool-anchor/registrar artifacts (which
        # are always absent now) and not the stale selected_document flag.
        readiness_state = "samras_seed_missing"
        readiness_message = (
            "CTS-GIS could not resolve the expected SAMRAS seed from the tool anchor, registrar payload, and selected source evidence."
        )

    return {
        "tool_spec": tool_spec,
        "tool_anchor": tool_anchor,
        "registrar_payload": registrar_payload,
        "administrative_source": administrative_source,
        "administrative_payload_cache": administrative_payload_cache,
        "sos_voterid_source": sos_voterid_source,
        "source_layout": dict(source_layout or {}),
        "payload_corpus": {
            "corpus_prefix": corpus_prefix,
            "member_file_count": len(member_files),
        },
        "warnings": list(source_layout_issues),
        "readiness": {
            "state": readiness_state,
            "message": readiness_message,
            "samras_seed_status": "ready" if readiness_state == "ready" else (samras_seed_status or "missing"),
        },
    }


def _resolved_tool_state(
    requested_tool_state: dict[str, Any],
    service_surface: dict[str, Any],
) -> dict[str, Any]:
    mediation_state = dict(service_surface.get("mediation_state") or {})
    diagnostic_summary = dict(service_surface.get("diagnostic_summary") or {})
    selection_summary = dict(mediation_state.get("selection_summary") or {})
    dict(requested_tool_state.get("selection") or {})
    requested_active_path = _normalize_requested_active_path(requested_tool_state.get("active_path"))
    fallback_selected_node_id = ""
    if (
        not requested_active_path
        and not _as_text(requested_tool_state.get("selected_node_id"))
        and not _as_text(requested_tool_state.get("aitas", {}).get("attention_node_id"))
    ):
        fallback_selected_node_id = (
            _as_text(selection_summary.get("selected_profile_node_id"))
            or _as_text(mediation_state.get("attention_node_id"))
        )
    active_path, selected_node_id = _canonical_staged_selection_state(
        active_path=requested_active_path,
        selected_node_id=_as_text(requested_tool_state.get("selected_node_id")) or fallback_selected_node_id,
        attention_node_id=_as_text(requested_tool_state.get("aitas", {}).get("attention_node_id")) or fallback_selected_node_id,
    )
    requested_attention_document_id = _as_text(requested_tool_state.get("source", {}).get("attention_document_id"))
    service_intention_token = _as_text(mediation_state.get("intention_token")) or _as_text(
        requested_tool_state.get("aitas", {}).get("intention_rule_id")
    )
    return {
        "nimm_directive": _as_text(requested_tool_state.get("nimm_directive")),
        "active_path": active_path,
        "selected_node_id": selected_node_id,
        "aitas": {
            "attention_node_id": selected_node_id,
            "intention_rule_id": canonical_runtime_intention_rule_id(
                service_intention_token or _DEFAULT_INTENTION_RULE_ID,
                attention_node_id=selected_node_id,
            ),
            "time_directive": _as_text(requested_tool_state.get("aitas", {}).get("time_directive")) or _DEFAULT_TIME_DIRECTIVE,
            "archetype_family_id": _as_text(requested_tool_state.get("aitas", {}).get("archetype_family_id"))
            or _DEFAULT_ARCHETYPE_FAMILY_ID,
        },
        "source": {
            "attention_document_id": requested_attention_document_id,
            "precinct_district_overlay_enabled": bool(
                requested_tool_state.get("source", {}).get("precinct_district_overlay_enabled")
            ),
            "requested_active_path_raw": [
                _as_text(item)
                for item in list(requested_tool_state.get("source", {}).get("requested_active_path_raw") or [])
                if _as_text(item)
            ],
            "requested_selected_node_id_raw": _as_text(
                requested_tool_state.get("source", {}).get("requested_selected_node_id_raw")
            ),
        },
        "selection": {
            "selected_row_address": _as_text(diagnostic_summary.get("selected_row_address"))
            or _as_text(requested_tool_state.get("selection", {}).get("selected_row_address")),
            "selected_feature_id": _as_text(diagnostic_summary.get("selected_feature_id"))
            or _as_text(requested_tool_state.get("selection", {}).get("selected_feature_id")),
            "selected_row_explicit": bool(_as_text(requested_tool_state.get("selection", {}).get("selected_row_address"))),
            "selected_feature_explicit": bool(
                _as_text(requested_tool_state.get("selection", {}).get("selected_feature_id"))
            ),
            # Garland cascade selection identifiers (Phase 2 + 3):
            # `selected_district_id` survives mediation untouched because it
            # identifies a district collection (e.g. "23_present-district_31"),
            # not a SAMRAS datum row address. The mediation's `finalize_selection`
            # only writes to `selected_row_address` / `selected_feature_id`.
            #
            # Phase 4 follow-up: when the artifact carries
            # `district_profile_static` (single canonical district) and no
            # explicit selection is on the wire, fall back to that district's
            # collection_id. This makes the resolved tool_state match what the
            # wireframe builder paints (auto-select), so the region render_key
            # is stable across the first user click on the auto-selected row
            # — no spurious panel re-render.
            "selected_district_id": _as_text(
                requested_tool_state.get("selection", {}).get("selected_district_id")
            ) or _as_text(
                (service_surface.get("district_profile_static") or {}).get("collection_id")
            ),
            # `selected_precinct_id` is the click selection from the
            # precinct listing (e.g. "247-17-77-121"). Survives
            # mediation finalize because it identifies a precinct
            # collection node, NOT a SAMRAS datum row address.
            "selected_precinct_id": _as_text(
                requested_tool_state.get("selection", {}).get("selected_precinct_id")
            ),
        },
        "staged_insert": _staged_insert_state(requested_tool_state.get("staged_insert")),
    }


def _strict_projection_context_differs(
    *,
    compiled_artifact: dict[str, Any],
    requested_tool_state: dict[str, Any],
) -> bool:
    default_tool_state = _tool_state_clone(dict(compiled_artifact.get("default_tool_state") or {}))
    default_projection_model = dict(compiled_artifact.get("projection_model") or {})
    default_profile = dict(default_projection_model.get("profile_summary") or {})
    default_selected_node_id = _as_text(default_tool_state.get("selected_node_id")) or _as_text(default_profile.get("node_id"))
    requested_selected_node_id = _as_text(requested_tool_state.get("selected_node_id"))
    if requested_selected_node_id and requested_selected_node_id != default_selected_node_id:
        return True

    default_time_directive = _as_text((default_tool_state.get("aitas") or {}).get("time_directive"))
    requested_time_directive = _as_text((requested_tool_state.get("aitas") or {}).get("time_directive"))
    if requested_time_directive and requested_time_directive != default_time_directive:
        return True

    default_source = dict(default_tool_state.get("source") or {})
    requested_source = dict(requested_tool_state.get("source") or {})
    if bool(requested_source.get("precinct_district_overlay_enabled")) != bool(
        default_source.get("precinct_district_overlay_enabled")
    ):
        return True
    requested_attention_document_id = _as_text(requested_source.get("attention_document_id"))
    if requested_attention_document_id and requested_attention_document_id != _as_text(default_source.get("attention_document_id")):
        return True

    default_selection = dict(default_tool_state.get("selection") or {})
    requested_selection = dict(requested_tool_state.get("selection") or {})
    requested_selected_row_address = _as_text(requested_selection.get("selected_row_address"))
    if requested_selected_row_address and requested_selected_row_address != _as_text(default_selection.get("selected_row_address")):
        return True
    requested_selected_feature_id = _as_text(requested_selection.get("selected_feature_id"))
    if requested_selected_feature_id and requested_selected_feature_id != _as_text(default_selection.get("selected_feature_id")):
        return True
    return False


def _read_live_service_surface(
    *,
    portal_scope: PortalScope,
    datum_store: SqliteSystemDatumStoreAdapter | None,
    requested_tool_state: dict[str, Any],
    request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_request_payload = request_payload if isinstance(request_payload, dict) else {}
    raw_tool_state = (
        normalized_request_payload.get("tool_state")
        if isinstance(normalized_request_payload.get("tool_state"), dict)
        else {}
    )
    raw_aitas = raw_tool_state.get("aitas") if isinstance(raw_tool_state.get("aitas"), dict) else {}
    raw_mediation = (
        normalized_request_payload.get("mediation_state")
        if isinstance(normalized_request_payload.get("mediation_state"), dict)
        else {}
    )
    explicit_intention_requested = bool(
        _as_text(raw_aitas.get("intention_rule_id"))
        or _as_text(raw_mediation.get("intention_token"))
        or _as_text(normalized_request_payload.get("intention_token"))
    )
    mediation_time = raw_mediation.get("time")
    if not isinstance(mediation_time, (dict, str)):
        mediation_time = None
    requested_time_directive = _as_text(requested_tool_state.get("aitas", {}).get("time_directive"))
    if requested_time_directive:
        mediation_time = {"value_token": requested_time_directive, "family": "tool_state_time_directive"}

    if datum_store is None:
        return {
            "document_catalog": [],
            "selected_document": None,
            "attention_profile": None,
            "lineage": [],
            "children": [],
            "render_profiles": [],
            "related_profiles": [],
            "render_set_summary": {"render_feature_count": 0, "render_row_count": 0, "render_profile_count": 0},
            "map_projection": {"projection_state": "no_authoritative_cts_gis_documents", "selected_feature": None},
            "rows": [],
            "diagnostic_summary": {},
            "lens_state": {"overlay_mode": "auto", "raw_underlay_visible": False},
            "mediation_state": {
                "attention_document_id": "",
                "attention_node_id": "",
                "intention_token": _DEFAULT_INTENTION_RULE_ID,
                "available_intentions": [],
            },
            "warnings": ["data_dir_missing"],
        }

    return CtsGisReadOnlyService(datum_store).read_surface(
        portal_scope.scope_id,
        selected_document_id=_as_text(requested_tool_state.get("source", {}).get("attention_document_id")),
        selected_row_address=_as_text(requested_tool_state.get("selection", {}).get("selected_row_address")),
        selected_feature_id=_as_text(requested_tool_state.get("selection", {}).get("selected_feature_id")),
        mediation_state={
            "attention_document_id": _as_text(requested_tool_state.get("source", {}).get("attention_document_id")),
            "attention_node_id": _as_text(requested_tool_state.get("aitas", {}).get("attention_node_id")),
            "intention_token": (
                canonical_service_intention_token(
                    requested_tool_state.get("aitas", {}).get("intention_rule_id"),
                    attention_node_id=_as_text(requested_tool_state.get("aitas", {}).get("attention_node_id")),
                )
                if explicit_intention_requested
                else ""
            ),
            "time": mediation_time,
            "precinct_district_overlay_enabled": bool(
                requested_tool_state.get("source", {}).get("precinct_district_overlay_enabled")
            ),
        },
    )


def _tool_state_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_body = dict(
        base_shell_request
        or build_portal_shell_request_payload(
            portal_scope=portal_scope,
            shell_state=shell_state,
            requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
        )
    )
    request_body["tool_state"] = _tool_state_clone(tool_state)
    return request_body


def _apply_selected_node_state(next_state: dict[str, Any], node_id: object) -> None:
    active_path = _active_path_from_node_id(node_id)
    selected_node_id = active_path[-1] if active_path else ""
    next_state["active_path"] = active_path
    next_state["selected_node_id"] = selected_node_id
    next_state.setdefault("aitas", {})
    next_state["aitas"]["attention_node_id"] = selected_node_id


def _node_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    attention_node_id: str,
    intention_rule_id: str = "self",
    selected_row_address: str = "",
    selected_feature_id: str = "",
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    _apply_selected_node_state(next_state, attention_node_id)
    next_state["aitas"]["intention_rule_id"] = canonical_runtime_intention_rule_id(
        intention_rule_id,
        attention_node_id=attention_node_id,
    )
    next_state["selection"]["selected_row_address"] = _as_text(selected_row_address)
    next_state["selection"]["selected_feature_id"] = _as_text(selected_feature_id)
    next_state["selection"]["selected_row_explicit"] = bool(_as_text(selected_row_address))
    next_state["selection"]["selected_feature_explicit"] = bool(_as_text(selected_feature_id))
    return _tool_state_request(
        portal_scope=portal_scope,
        shell_state=shell_state,
        tool_state=next_state,
        base_shell_request=base_shell_request,
    )


def _clear_selection_state(tool_state: dict[str, Any]) -> None:
    tool_state["selection"]["selected_row_address"] = ""
    tool_state["selection"]["selected_feature_id"] = ""
    tool_state["selection"]["selected_row_explicit"] = False
    tool_state["selection"]["selected_feature_explicit"] = False


def _intention_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    intention_rule_id: str,
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["aitas"]["intention_rule_id"] = canonical_runtime_intention_rule_id(
        intention_rule_id,
        attention_node_id=_as_text(next_state.get("selected_node_id") or next_state.get("aitas", {}).get("attention_node_id")),
    )
    _clear_selection_state(next_state)
    return _tool_state_request(
        portal_scope=portal_scope,
        shell_state=shell_state,
        tool_state=next_state,
        base_shell_request=base_shell_request,
    )


def _attention_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    attention_node_id: str,
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    _apply_selected_node_state(next_state, attention_node_id)
    next_state["aitas"]["intention_rule_id"] = canonical_runtime_intention_rule_id(
        _as_text(next_state.get("aitas", {}).get("intention_rule_id")) or "self",
        attention_node_id=attention_node_id,
    )
    _clear_selection_state(next_state)
    return _tool_state_request(
        portal_scope=portal_scope,
        shell_state=shell_state,
        tool_state=next_state,
        base_shell_request=base_shell_request,
    )


def _time_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    time_directive: str,
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["aitas"]["time_directive"] = _as_text(time_directive)
    _clear_selection_state(next_state)
    return _tool_state_request(
        portal_scope=portal_scope,
        shell_state=shell_state,
        tool_state=next_state,
        base_shell_request=base_shell_request,
    )


def _precinct_overlay_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    enabled: bool,
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state.setdefault("source", {})
    next_state["source"]["precinct_district_overlay_enabled"] = bool(enabled)
    _clear_selection_state(next_state)
    return _tool_state_request(
        portal_scope=portal_scope,
        shell_state=shell_state,
        tool_state=next_state,
        base_shell_request=base_shell_request,
    )


def _document_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    attention_document_id: str,
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    _apply_selected_node_state(next_state, "")
    next_state["source"]["attention_document_id"] = _as_text(attention_document_id)
    _clear_selection_state(next_state)
    return _tool_state_request(
        portal_scope=portal_scope,
        shell_state=shell_state,
        tool_state=next_state,
        base_shell_request=base_shell_request,
    )


def _selection_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    selected_row_address: str,
    selected_feature_id: str,
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["selection"]["selected_row_address"] = _as_text(selected_row_address)
    next_state["selection"]["selected_feature_id"] = _as_text(selected_feature_id)
    next_state["selection"]["selected_row_explicit"] = bool(_as_text(selected_row_address))
    next_state["selection"]["selected_feature_explicit"] = bool(_as_text(selected_feature_id))
    return _tool_state_request(
        portal_scope=portal_scope,
        shell_state=shell_state,
        tool_state=next_state,
        base_shell_request=base_shell_request,
    )


def _context_items_from_base_panel(base_panel: dict[str, Any], source_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    items = list(base_panel.get("context_items") or [])
    tool_anchor_file = _as_text((source_evidence.get("tool_anchor") or {}).get("file"))
    if tool_anchor_file and len(items) >= 2:
        items[1] = {"label": "File", "value": tool_anchor_file}
    return items


def _context_option_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    option = {
        "label": _as_text(entry.get("label")) or _as_text(entry.get("prefix")) or "Option",
        "value": _as_text(entry.get("prefix") or entry.get("meta") or entry.get("label")),
        "meta": _as_text(entry.get("meta")),
        "active": bool(entry.get("active")),
    }
    if isinstance(entry.get("shell_request"), dict):
        option["shell_request"] = dict(entry["shell_request"])
    if isinstance(entry.get("action"), dict):
        option["action"] = dict(entry["action"])
    if not (option.get("shell_request") or option.get("action")):
        option["disabled"] = True
    return option


def _context_control_button(
    *,
    label: str,
    control_id: str,
    entry: dict[str, Any] | None = None,
    shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    button: dict[str, Any] = {
        "label": label,
        "control_id": control_id,
        "disabled": True,
    }
    source = dict(entry or {})
    request = shell_request if shell_request is not None else source.get("shell_request")
    if isinstance(request, dict):
        button["shell_request"] = dict(request)
        button["disabled"] = False
    if isinstance(source.get("action"), dict):
        button["action"] = dict(source["action"])
        button["disabled"] = False
    if _as_text(source.get("meta")):
        button["meta"] = _as_text(source.get("meta"))
    return button


def _build_cts_gis_context_controls(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    file_entries: list[dict[str, Any]],
    attention_entries: list[dict[str, Any]],
    intention_entries: list[dict[str, Any]],
    time_entries: list[dict[str, Any]],
    current_attention_node_id: str,
    current_intention_rule_id: str,
    current_time_directive: str,
    archetype_family_id: str,
) -> list[dict[str, Any]]:
    attention_options = [_context_option_from_entry(entry) for entry in attention_entries if _as_text(entry.get("prefix"))]
    intention_options = [_context_option_from_entry(entry) for entry in intention_entries if _as_text(entry.get("prefix"))]
    time_options = [_context_option_from_entry(entry) for entry in time_entries if _as_text(entry.get("prefix"))]

    active_intention_index = next((index for index, item in enumerate(intention_options) if item.get("active")), -1)
    previous_intention = intention_entries[active_intention_index - 1] if active_intention_index > 0 else None
    next_intention = (
        intention_entries[active_intention_index + 1]
        if active_intention_index >= 0 and active_intention_index + 1 < len(intention_entries)
        else None
    )

    active_time_index = next((index for index, item in enumerate(time_options) if item.get("active")), -1)
    previous_time = time_entries[active_time_index - 1] if active_time_index > 0 else None
    next_time = time_entries[active_time_index + 1] if active_time_index >= 0 and active_time_index + 1 < len(time_entries) else None
    first_time = time_entries[0] if time_entries else None
    last_time = time_entries[-1] if time_entries else None

    nav_requests = _nimm_navigation_shell_requests(
        portal_scope=portal_scope,
        shell_state=shell_state,
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
        file_entries=file_entries,
    )

    return [
        {
            "context_id": "attention",
            "label": "Attention",
            "current_value": current_attention_node_id or "unresolved",
            "control_type": "select",
            "options": attention_options,
            "empty_message": "No alternate attention contexts are available.",
        },
        {
            "context_id": "intention",
            "label": "Intention",
            "current_value": current_intention_rule_id or _DEFAULT_INTENTION_RULE_ID,
            "control_type": "stepper",
            "options": intention_options,
            "controls": [
                _context_control_button(label="−", control_id="intention_previous", entry=previous_intention),  # noqa: RUF001 — Unicode MINUS SIGN intentional for symmetry with "+"
                _context_control_button(label="+", control_id="intention_next", entry=next_intention),
            ],
            "empty_message": "No intention controls are available.",
        },
        {
            "context_id": "time",
            "label": "Time",
            "current_value": current_time_directive or _DEFAULT_TIME_DIRECTIVE,
            "control_type": "directional",
            "options": time_options,
            "controls": [
                _context_control_button(label="<", control_id="time_previous", entry=previous_time),
                _context_control_button(label=">", control_id="time_next", entry=next_time),
                _context_control_button(label="^", control_id="time_up", entry=first_time),
                _context_control_button(label="v", control_id="time_down", entry=last_time),
                _context_control_button(label="<<", control_id="time_first", entry=first_time),
                _context_control_button(label=">>", control_id="time_last", entry=last_time),
            ],
        },
        {
            "context_id": "archetype",
            "label": "Archetype",
            "current_value": archetype_family_id or _DEFAULT_ARCHETYPE_FAMILY_ID,
            "control_type": "select",
            "options": [
                {
                    "label": archetype_family_id or _DEFAULT_ARCHETYPE_FAMILY_ID,
                    "value": archetype_family_id or _DEFAULT_ARCHETYPE_FAMILY_ID,
                    "active": True,
                    "disabled": True,
                }
            ],
            "empty_message": "Archetype switching is not wired for CTS-GIS yet.",
        },
        {
            "context_id": "spatial",
            "label": "Spatial",
            "current_value": _as_text((shell_state.focus_subject or {}).get("id")) or portal_scope.scope_id,
            "control_type": "directional",
            "controls": [
                _context_control_button(label="Out", control_id="nav_out", shell_request=nav_requests.get("nav_out")),
                _context_control_button(label="<", control_id="shift_left", shell_request=nav_requests.get("shift_left")),
                _context_control_button(label=">", control_id="shift_right", shell_request=nav_requests.get("shift_right")),
                _context_control_button(label="Attention In", control_id="nav_in", shell_request=nav_requests.get("nav_in")),
            ],
        },
    ]


def _build_cts_gis_directive_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    tool_rows: list[dict[str, Any]],
    resolved_tool_state: dict[str, Any],
    source_evidence: dict[str, Any],
    service_surface: dict[str, Any],
    action_result: dict[str, Any],
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del data_dir, private_dir, tool_rows
    staged_selected_node_id = _as_text(resolved_tool_state.get("selected_node_id"))
    has_staged_selection = bool(staged_selected_node_id)
    attention_profile = dict(service_surface.get("attention_profile") or {}) if has_staged_selection else {}
    current_attention_node_id = _as_text(resolved_tool_state.get("aitas", {}).get("attention_node_id"))
    current_time_directive = _as_text(resolved_tool_state.get("aitas", {}).get("time_directive"))
    current_intention_rule_id = _as_text(resolved_tool_state.get("aitas", {}).get("intention_rule_id")) or _DEFAULT_INTENTION_RULE_ID
    attention_entries = [
        {
            "label": "Attention",
            "meta": _as_text(attention_profile.get("profile_label")) or current_attention_node_id or "unresolved",
            "prefix": current_attention_node_id or "root",
            "active": bool(current_attention_node_id),
        }
    ]
    attention_options: list[tuple[str, str]] = []
    if current_attention_node_id:
        attention_options.append(
            (
                current_attention_node_id,
                _as_text(attention_profile.get("profile_label")) or current_attention_node_id,
            )
        )
    for profile in list(service_surface.get("children") or []):
        node_id = _as_text(profile.get("node_id"))
        label = _as_text(profile.get("profile_label")) or node_id
        if node_id and node_id not in {item[0] for item in attention_options}:
            attention_options.append((node_id, label))
    for profile in list(service_surface.get("lineage") or []):
        node_id = _as_text(profile.get("node_id"))
        label = _as_text(profile.get("profile_label")) or node_id
        if node_id and node_id not in {item[0] for item in attention_options}:
            attention_options.append((node_id, label))
    for node_id, label in attention_options:
        attention_entries.append(
            {
                "label": f"Attention · {label}",
                "prefix": node_id,
                "meta": "set attention context",
                "active": node_id == current_attention_node_id,
                "shell_request": _attention_shell_request(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    tool_state=resolved_tool_state,
                    attention_node_id=node_id,
                    base_shell_request=base_shell_request,
                ),
                "action": _shell_action("select_node", node_id=node_id),
            }
        )
    intention_entries = [
        {
            "label": f"Intention · {(_as_text(option.get('label')) or _as_text(option.get('token')) or 'Rule')}",
            "prefix": _as_text(option.get("token")),
            "meta": f"{int(option.get('profile_count') or 0)} profiles · {int(option.get('feature_count') or 0)} features",
            "active": bool(option.get("active")),
            "shell_request": _intention_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                intention_rule_id=_as_text(option.get("token")),
                base_shell_request=base_shell_request,
            ),
            "action": _shell_action("set_intention", token=_as_text(option.get("token"))),
        }
        for option in list((service_surface.get("mediation_state") or {}).get("available_intentions") or [])
    ]
    if not intention_entries:
        fallback_attention_node_id = current_attention_node_id or staged_selected_node_id
        fallback_options = [("self", "Self")]
        if fallback_attention_node_id:
            fallback_options.extend(
                [
                    (f"{fallback_attention_node_id}-0", "Children"),
                    (f"{fallback_attention_node_id}-0-0", "Descendants depth 1-2"),
                ]
            )
        intention_entries = [
            {
                "label": f"Intention · {label}",
                "prefix": token,
                "meta": "set intention context",
                "active": (_as_text(resolved_tool_state.get("aitas", {}).get("intention_rule_id")) or _DEFAULT_INTENTION_RULE_ID)
                == token,
                "shell_request": _intention_shell_request(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    tool_state=resolved_tool_state,
                    intention_rule_id=token,
                    base_shell_request=base_shell_request,
                ),
                "action": _shell_action("set_intention", token=token),
            }
            for token, label in fallback_options
        ]
    time_tokens = [_DEFAULT_TIME_DIRECTIVE]
    if current_time_directive and current_time_directive not in time_tokens:
        time_tokens.insert(0, current_time_directive)
    _district_precincts_ref = (service_surface.get("contextual_references") or {}).get("district_precincts") or {}
    for _tf_token in list(_district_precincts_ref.get("timeframe_tokens") or []):
        if _as_text(_tf_token) and _as_text(_tf_token) not in time_tokens:
            time_tokens.append(_as_text(_tf_token))
    time_entries = [
        {
            "label": f"Time · {token}",
            "prefix": token,
            "meta": "set time context",
            "active": token == current_time_directive,
            "shell_request": _time_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                time_directive=token,
                base_shell_request=base_shell_request,
            ),
            "action": _shell_action("set_time", token=token),
        }
        for token in time_tokens
    ]
    staged_insert = _staged_insert_state(resolved_tool_state.get("staged_insert"))
    stage_payload = dict(staged_insert.get("normalized_payload") or {})
    stage_validation = dict(staged_insert.get("last_validation") or {})
    stage_preview = dict(staged_insert.get("last_preview") or {})
    compiled_nimm_envelope = dict(staged_insert.get("compiled_nimm_envelope") or {})
    stage_datums = list(stage_payload.get("datums") or [])
    stage_groups: list[dict[str, Any]] = []
    if stage_payload:
        stage_groups = [
            {
                "title": "STAGED INSERT",
                "entries": [
                    {
                        "label": "Document",
                        "meta": _as_text(stage_payload.get("document_name")) or _as_text(stage_payload.get("document_id")),
                        "active": True,
                    },
                    {
                        "label": "Datums",
                        "meta": str(len(stage_datums)),
                        "active": True,
                    },
                    {
                        "label": "Validation",
                        "meta": _as_text(stage_validation.get("expected_document_version_hash"))[:12] or "pending",
                        "active": bool(stage_validation),
                    },
                    {
                        "label": "Preview",
                        "meta": str(len(list(stage_preview.get("proposed_inserted_rows") or []))) or "0",
                        "active": bool(stage_preview),
                    },
                    {
                        "label": "Latest action",
                        "meta": _as_text(action_result.get("action_kind")) or "stage_insert_yaml",
                        "active": bool(action_result),
                    },
                    {
                        "label": "Compiled NIMM",
                        "meta": "ready" if compiled_nimm_envelope else "pending",
                        "active": bool(compiled_nimm_envelope),
                    },
                ],
            }
        ]
    stage_actions: list[dict[str, Any]] = []
    if stage_payload:
        stage_actions.append({"label": "Validate Stage", **_tool_action("validate_stage")})
        stage_actions.append({"label": "Preview Apply", **_tool_action("preview_apply")})
        if stage_preview:
            stage_actions.append({"label": "Apply Stage", **_tool_action("apply_stage")})
        stage_actions.append({"label": "Discard Stage", **_tool_action("discard_stage")})
    # The legacy STATE DIRECTIVE / cts_gis_attention / cts_gis_intention /
    # cts_gis_time / cts_gis_archetype panel sections are superseded by the
    # AITAS context-control table (see context_controls below). The entries
    # lists are still consumed by _build_cts_gis_context_controls.
    base_navigation_groups = list(stage_groups)
    aitas_overlay = dict(resolved_tool_state.get("aitas") or {})
    tool_extensions: dict[str, Any] = {
        "directive_terminal_enabled": True,
    }
    if stage_payload:
        tool_extensions["cts_gis_staged_insert"] = {
            "document_name": _as_text(stage_payload.get("document_name")),
            "document_id": _as_text(stage_payload.get("document_id")),
            "datum_count": len(stage_datums),
            "validation_hash": _as_text(stage_validation.get("expected_document_version_hash")),
            "preview_row_count": len(list(stage_preview.get("proposed_inserted_rows") or [])),
            "compiled_envelope_ready": bool(compiled_nimm_envelope),
            "latest_action_kind": _as_text(action_result.get("action_kind")),
        }
    file_entries = _cts_gis_control_panel_file_entries(
        portal_scope=portal_scope,
        shell_state=shell_state,
        documents=_cts_gis_workbench_documents(service_surface),
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    context_controls = _build_cts_gis_context_controls(
        portal_scope=portal_scope,
        shell_state=shell_state,
        file_entries=file_entries,
        attention_entries=attention_entries,
        intention_entries=intention_entries,
        time_entries=time_entries,
        current_attention_node_id=current_attention_node_id,
        current_intention_rule_id=current_intention_rule_id,
        current_time_directive=current_time_directive,
        archetype_family_id=_as_text(aitas_overlay.get("archetype_family_id")) or _DEFAULT_ARCHETYPE_FAMILY_ID,
    )

    panel = build_unified_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        surface_label="CTS-GIS",
        directive_context=None,
        nimm_directive=_as_text(resolved_tool_state.get("nimm_directive")),
        aitas_state=aitas_overlay,
        file_entries=file_entries,
        navigation_groups=base_navigation_groups,
        actions=stage_actions,
        tool_extensions=tool_extensions,
        context_controls=context_controls,
    )

    panel_context = list(panel.get("context_conditions") or [])
    tool_anchor_file = _as_text((source_evidence.get("tool_anchor") or {}).get("file"))
    if tool_anchor_file:
        for row in panel_context:
            if row.get("label") == "File":
                row["value"] = tool_anchor_file
                break
    # The Sandbox row duplicates the surface label already printed in the
    # directive-panel header; drop it for the CTS-GIS surface.
    panel_context = [row for row in panel_context if row.get("label") != "Sandbox"]
    panel["context_conditions"] = panel_context
    # The auto-derived "Sandbox: cts_gis" navigation group is redundant with
    # the file picker already exposed through the AITAS context controls.
    panel["navigation_groups"] = [
        group for group in (panel.get("navigation_groups") or [])
        if not str(group.get("title") or "").startswith("Sandbox:")
    ]

    return panel


def _node_depth(node_id: object) -> int:
    token = _as_text(node_id)
    if not token:
        return 0
    return len([part for part in token.split("-") if part])


def _parent_node_id(node_id: object) -> str:
    token = _as_text(node_id)
    if not token or "-" not in token:
        return ""
    return "-".join(token.split("-")[:-1])


def _node_sort_key(node_id: object) -> tuple[int, tuple[int, ...], str]:
    token = _as_text(node_id)
    parts = [part for part in token.split("-") if part]
    if not parts:
        return (0, tuple(), token)
    ints = tuple(int(part) if part.isdigit() else 10**9 for part in parts)
    return (len(parts), ints, token)


def _looks_like_msn_node_id(value: object) -> bool:
    token = _as_text(value)
    if not token:
        return False
    parts = token.split("-")
    return all(part.isdigit() for part in parts if part != "")


def _row_data_tokens(raw_row: object) -> list[Any]:
    if not isinstance(raw_row, list) or not raw_row:
        return []
    data_tokens = raw_row[0] if isinstance(raw_row[0], list) else raw_row
    return list(data_tokens) if isinstance(data_tokens, list) else []


def _decode_ascii_title_babelette(value: object) -> str:
    token = _as_text(value)
    if not token:
        return ""
    if any(ch not in {"0", "1"} for ch in token) or (len(token) % 8) != 0:
        return ""
    data = bytearray(int(token[index : index + 8], 2) for index in range(0, len(token), 8))
    while data and data[-1] == 0:
        data.pop()
    if not data:
        return ""
    try:
        decoded = bytes(data).decode("ascii")
    except UnicodeDecodeError:
        return ""
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in decoded):
        return ""
    return decoded.strip()


def _samras_structure_authorities(source_evidence: dict[str, Any]) -> list[Any]:
    authorities: list[Any] = []
    cache_payload = dict((source_evidence.get("administrative_payload_cache") or {}).get("payload") or {})
    cache_path = _as_text((source_evidence.get("administrative_payload_cache") or {}).get("path"))
    authorities.extend(
        find_structure_authorities(
            cache_payload,
            source_kind="administrative_payload_cache",
            source_path=cache_path,
            root_ref="0-0-5",
        )
    )
    anchor_payload = dict((source_evidence.get("tool_anchor") or {}).get("payload") or {})
    anchor_path = _as_text((source_evidence.get("tool_anchor") or {}).get("path"))
    authorities.extend(
        find_structure_authorities(
            anchor_payload,
            source_kind="tool_anchor",
            source_path=anchor_path,
            root_ref="0-0-5",
        )
    )
    return authorities


def _collect_administrative_node_bindings(source_payload: dict[str, Any]) -> dict[str, Any]:
    row_source = _split_row_source(source_payload)
    bindings_by_node: dict[str, list[dict[str, Any]]] = {}
    blank_title_nodes: set[str] = set()
    for datum_address in sorted(row_source.keys(), key=_node_sort_key):
        raw_row = row_source.get(datum_address)
        data_tokens = _row_data_tokens(raw_row)
        if not data_tokens:
            continue
        node_id = ""
        title_bits = ""
        for index, token in enumerate(data_tokens):
            marker = _as_text(token)
            if marker == "rf.3-1-2" and index + 1 < len(data_tokens):
                node_id = _as_text(data_tokens[index + 1])
            if marker == "rf.3-1-3" and index + 1 < len(data_tokens):
                title_bits = _as_text(data_tokens[index + 1])
        if not _looks_like_msn_node_id(node_id):
            continue
        decoded_title = _decode_ascii_title_babelette(title_bits)
        if title_bits and not decoded_title:
            blank_title_nodes.add(node_id)
        bindings_by_node.setdefault(node_id, []).append(
            {
                "node_id": node_id,
                "datum_address": _as_text(datum_address),
                "title_bits": title_bits,
                "title": decoded_title,
            }
        )
    duplicates = sorted(
        (node_id for node_id, bindings in bindings_by_node.items() if len(bindings) > 1),
        key=_node_sort_key,
    )
    unique_bindings = {
        node_id: bindings[0]
        for node_id, bindings in bindings_by_node.items()
        if len(bindings) == 1
    }
    return {
        "bindings_by_node": bindings_by_node,
        "unique_bindings": unique_bindings,
        "duplicates": duplicates,
        "blank_title_nodes": sorted(blank_title_nodes, key=_node_sort_key),
    }


def _navigation_diagnostic(
    code: str,
    message: str,
    *,
    severity: str = "error",
    source_kind: str = "",
    source_path: str = "",
    node_ids: list[str] | None = None,
    datum_addresses: list[str] | None = None,
) -> dict[str, Any]:
    diagnostic = {
        "code": _as_text(code),
        "severity": _as_text(severity) or "error",
        "message": _as_text(message),
    }
    if _as_text(source_kind):
        diagnostic["source_kind"] = _as_text(source_kind)
    if _as_text(source_path):
        diagnostic["source_path"] = _as_text(source_path)
    if node_ids:
        diagnostic["node_ids"] = [_as_text(item) for item in node_ids if _as_text(item)]
    if datum_addresses:
        diagnostic["datum_addresses"] = [_as_text(item) for item in datum_addresses if _as_text(item)]
    return diagnostic


def _directory_option_payload(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    node_id: str,
    title_map: dict[str, str],
    selected_node_id: str,
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title = _as_text(title_map.get(node_id))
    display_title = title.upper() if _node_depth(node_id) == 1 and title else title
    display_label = f"{node_id} {display_title}".strip() if display_title else node_id
    return {
        "node_id": node_id,
        "title": title,
        "display_label": display_label,
        "selected": node_id == selected_node_id,
        "shell_request": _node_shell_request(
            portal_scope=portal_scope,
            shell_state=shell_state,
            tool_state=resolved_tool_state,
            attention_node_id=node_id,
            base_shell_request=base_shell_request,
        ),
        "action": _shell_action("select_node", node_id=node_id),
    }


def _build_directory_dropdown_navigation(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    source_evidence: dict[str, Any],
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    authorities = _samras_structure_authorities(source_evidence)
    source_payload = dict((source_evidence.get("administrative_source") or {}).get("payload") or {})
    bindings = _collect_administrative_node_bindings(source_payload)
    diagnostics: list[dict[str, Any]] = []
    preferred_authority = authorities[0] if authorities else None
    try:
        decodable_authority = (
            select_preferred_structure_authority(authorities, require_decodable=True)
            if authorities
            else None
        )
    except InvalidSamrasStructure:
        decodable_authority = None

    duplicate_nodes = list(bindings.get("duplicates") or [])
    if duplicate_nodes:
        duplicate_rows = [
            _as_text(binding.get("datum_address"))
            for node_id in duplicate_nodes
            for binding in list((bindings.get("bindings_by_node") or {}).get(node_id) or [])
            if _as_text(binding.get("datum_address"))
        ]
        diagnostics.append(
            _navigation_diagnostic(
                "duplicate_node_row",
                "Administrative node rows bind the same SAMRAS address more than once.",
                severity="warning",
                source_kind="administrative_source",
                source_path=_as_text((source_evidence.get("administrative_source") or {}).get("path")),
                node_ids=duplicate_nodes,
                datum_addresses=duplicate_rows,
            )
        )

    blank_title_nodes = list(bindings.get("blank_title_nodes") or [])
    if blank_title_nodes:
        diagnostics.append(
            _navigation_diagnostic(
                "blank_ascii_title",
                "Some administrative node rows do not carry decodable ASCII title overlays; those nodes will render without titles.",
                severity="warning",
                source_kind="administrative_source",
                source_path=_as_text((source_evidence.get("administrative_source") or {}).get("path")),
                node_ids=blank_title_nodes[:25],
            )
        )

    structure = None
    decode_state = "ready"
    for authority in authorities:
        if not _as_text(getattr(authority, "magnitude", "")) or bool(getattr(authority, "decodable", False)):
            continue
        diagnostics.append(
            _navigation_diagnostic(
                "invalid_magnitude_candidate",
                f"CTS-GIS found an msn-SAMRAS candidate that could not decode: {_as_text(getattr(authority, 'error', '')) or 'unknown decode failure'}",
                severity="warning",
                source_kind=_as_text(getattr(authority, "source_kind", "")),
                source_path=_as_text(getattr(authority, "source_path", "")),
                datum_addresses=[_as_text(getattr(authority, "datum_address", ""))],
            )
        )
    if decodable_authority is not None:
        structure = getattr(decodable_authority, "structure", None)
    if structure is None and (authorities or source_payload):
        try:
            structure = reconstruct_structure_from_rows(
                source_payload,
                root_ref="0-0-5",
                warnings=("canonical SAMRAS structure was reconstructed from staged address rows",),
            )
            decodable_authority = {
                "source_kind": "administrative_source_reconstructed",
                "source_path": _as_text((source_evidence.get("administrative_source") or {}).get("path")),
                "datum_address": "",
                "label": "reconstructed",
                "magnitude": structure.bitstream,
            }
            diagnostics.append(
                _navigation_diagnostic(
                    "reconstructed_magnitude",
                    "CTS-GIS reconstructed a canonical SAMRAS tree from staged address rows because no decodable structure row was available.",
                    severity="warning",
                    source_kind="administrative_source_reconstructed",
                    source_path=_as_text((source_evidence.get("administrative_source") or {}).get("path")),
                )
            )
        except InvalidSamrasStructure:
            structure = None
    if structure is None and not _as_text(getattr(preferred_authority, "magnitude", "")):
        decode_state = "blocked_invalid_magnitude"
        diagnostics.insert(
            0,
            _navigation_diagnostic(
                "invalid_magnitude",
                "CTS-GIS could not locate an msn-SAMRAS magnitude for the active corpus authority.",
                source_kind=_as_text(getattr(preferred_authority, "source_kind", "")) or "missing",
                source_path=_as_text(getattr(preferred_authority, "source_path", "")),
            ),
        )
    elif structure is None:
        decode_state = "blocked_invalid_magnitude"
        message = _as_text(getattr(preferred_authority, "error", "")) or "unknown decode failure"
        diagnostics.insert(
            0,
            _navigation_diagnostic(
                "invalid_magnitude",
                f"CTS-GIS could not decode the active SAMRAS magnitude: {message}",
                source_kind=_as_text(getattr(preferred_authority, "source_kind", "")) or "missing",
                source_path=_as_text(getattr(preferred_authority, "source_path", "")),
                datum_addresses=[_as_text(getattr(preferred_authority, "datum_address", ""))],
            ),
        )

    unique_binding_nodes = list((bindings.get("unique_bindings") or {}).keys())
    ordered_nodes = list(structure.addresses) if structure is not None else []
    available_nodes = set(ordered_nodes)
    outside_nodes = sorted(
        (
            node_id
            for node_id in unique_binding_nodes
            if node_id not in available_nodes
        ),
        key=_node_sort_key,
    ) if available_nodes else []
    if structure is not None and outside_nodes and unique_binding_nodes:
        try:
            reconstructed_structure = reconstruct_structure_from_rows(
                source_payload,
                root_ref="0-0-5",
                warnings=("canonical SAMRAS structure was reconstructed from staged address rows",),
            )
            reconstructed_available_nodes = set(reconstructed_structure.addresses)
            reconstructed_outside_nodes = sorted(
                (
                    node_id
                    for node_id in unique_binding_nodes
                    if node_id not in reconstructed_available_nodes
                ),
                key=_node_sort_key,
            )
            if len(reconstructed_outside_nodes) < len(outside_nodes):
                structure = reconstructed_structure
                ordered_nodes = list(structure.addresses)
                available_nodes = set(ordered_nodes)
                outside_nodes = reconstructed_outside_nodes
                decodable_authority = {
                    "source_kind": "administrative_source_reconstructed",
                    "source_path": _as_text((source_evidence.get("administrative_source") or {}).get("path")),
                    "datum_address": "",
                    "label": "reconstructed_override",
                    "magnitude": structure.bitstream,
                }
                diagnostics.append(
                    _navigation_diagnostic(
                        "reconstructed_magnitude_override",
                        "CTS-GIS replaced a decodable SAMRAS magnitude with a reconstructed authority because the decoded namespace excluded many administrative node bindings.",
                        severity="warning",
                        source_kind="administrative_source_reconstructed",
                        source_path=_as_text((source_evidence.get("administrative_source") or {}).get("path")),
                    )
                )
        except InvalidSamrasStructure:
            pass
    if outside_nodes:
        diagnostics.append(
            _navigation_diagnostic(
                "node_outside_magnitude",
                "Administrative node rows reference addresses that are not present in the decoded SAMRAS namespace.",
                severity="warning",
                source_kind="administrative_source",
                source_path=_as_text((source_evidence.get("administrative_source") or {}).get("path")),
                node_ids=outside_nodes,
                datum_addresses=[
                    _as_text((bindings.get("unique_bindings") or {}).get(node_id, {}).get("datum_address"))
                    for node_id in outside_nodes
                ],
            )
        )

    dropdowns: list[dict[str, Any]] = []
    active_path_entries: list[dict[str, Any]] = []
    active_node_id = ""
    if decode_state == "ready" and ordered_nodes:
        children_by_parent: dict[str, list[str]] = {}
        for node_id in ordered_nodes:
            children_by_parent.setdefault(_parent_node_id(node_id), []).append(node_id)
        for node_ids in children_by_parent.values():
            node_ids.sort(key=_node_sort_key)
        title_map = {
            node_id: _as_text((bindings.get("unique_bindings") or {}).get(node_id, {}).get("title"))
            for node_id in ordered_nodes
        }
        requested_path_raw = [
            _as_text(node_id)
            for node_id in list((resolved_tool_state.get("source") or {}).get("requested_active_path_raw") or [])
            if _as_text(node_id)
        ] or [
            _as_text(node_id)
            for node_id in list(resolved_tool_state.get("active_path") or [])
            if _as_text(node_id)
        ]
        requested_active_path = _sanitize_active_path(requested_path_raw, ordered_nodes)
        requested_selected_node_id = _as_text(
            (resolved_tool_state.get("source") or {}).get("requested_selected_node_id_raw")
        ) or _as_text(resolved_tool_state.get("selected_node_id"))
        if requested_path_raw and requested_active_path != requested_path_raw:
            divergence_index = len(requested_active_path)
            for index, node_id in enumerate(requested_path_raw):
                if index >= len(requested_active_path) or requested_active_path[index] != node_id:
                    divergence_index = index
                    break
            diagnostics.append(
                _navigation_diagnostic(
                    "invalid_active_path",
                    "Requested CTS-GIS active path could not be resolved cleanly and was truncated to the last valid lineage node.",
                    severity="warning",
                    source_kind="request_tool_state",
                    node_ids=requested_path_raw[divergence_index:] or requested_path_raw[-1:],
                )
            )
        if requested_selected_node_id and requested_selected_node_id not in available_nodes:
            diagnostics.append(
                _navigation_diagnostic(
                    "unresolved_node_binding",
                    "Requested CTS-GIS selected node is not present in the decoded SAMRAS namespace.",
                    severity="warning",
                    source_kind="request_tool_state",
                    node_ids=[requested_selected_node_id],
                )
            )
        if not requested_active_path and requested_selected_node_id in available_nodes:
            requested_active_path = _sanitize_active_path(_active_path_from_node_id(requested_selected_node_id), ordered_nodes)
        active_node_id = requested_active_path[-1] if requested_active_path else ""
        active_path_entries = [
            {
                **_directory_option_payload(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    resolved_tool_state=resolved_tool_state,
                    node_id=node_id,
                    title_map=title_map,
                    selected_node_id=active_node_id,
                    base_shell_request=base_shell_request,
                ),
                "depth": _node_depth(node_id),
                "parent_node_id": _parent_node_id(node_id),
            }
            for node_id in requested_active_path
        ]
        dropdowns.append(
            {
                "depth": 1,
                "parent_node_id": "",
                "selected_node_id": requested_active_path[0] if requested_active_path else "",
                "options": [
                    _directory_option_payload(
                        portal_scope=portal_scope,
                        shell_state=shell_state,
                        resolved_tool_state=resolved_tool_state,
                        node_id=node_id,
                        title_map=title_map,
                        selected_node_id=requested_active_path[0] if requested_active_path else "",
                        base_shell_request=base_shell_request,
                    )
                    for node_id in list(children_by_parent.get("", []))
                ],
            }
        )
        for depth, parent_node_id in enumerate(requested_active_path):
            child_node_ids = list(children_by_parent.get(parent_node_id, []))
            if not child_node_ids:
                break
            selected_child_id = requested_active_path[depth + 1] if depth + 1 < len(requested_active_path) else ""
            dropdowns.append(
                {
                    "depth": depth + 2,
                    "parent_node_id": parent_node_id,
                    "selected_node_id": selected_child_id,
                    "options": [
                        _directory_option_payload(
                            portal_scope=portal_scope,
                            shell_state=shell_state,
                            resolved_tool_state=resolved_tool_state,
                            node_id=node_id,
                            title_map=title_map,
                            selected_node_id=selected_child_id,
                            base_shell_request=base_shell_request,
                        )
                        for node_id in child_node_ids
                    ],
                }
            )

    return {
        "kind": "diktataograph_navigation_canvas",
        "title": "Diktataograph",
        "summary": "Magnitude-derived directory navigation for CTS-GIS.",
        "mode": _CTS_GIS_NAV_MODE_DIRECTORY,
        "source_authority": "samras_magnitude",
        "magnitude_source_kind": _as_text(
            decodable_authority.get("source_kind") if isinstance(decodable_authority, dict) else getattr(decodable_authority, "source_kind", "")
        ),
        "magnitude_datum_address": _as_text(
            decodable_authority.get("datum_address") if isinstance(decodable_authority, dict) else getattr(decodable_authority, "datum_address", "")
        ),
        "decode_state": decode_state,
        "diagnostics": diagnostics,
        "dropdowns": dropdowns,
        "active_path": active_path_entries,
        "active_node_id": active_node_id,
    }


def _tool_state_for_navigation(
    tool_state: dict[str, Any],
    navigation_canvas: dict[str, Any],
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    active_path = [
        _as_text(entry.get("node_id"))
        for entry in list(navigation_canvas.get("active_path") or [])
        if _as_text(entry.get("node_id"))
    ]
    selected_node_id = _as_text(navigation_canvas.get("active_node_id"))
    next_state["active_path"] = active_path
    next_state["selected_node_id"] = selected_node_id
    next_state.setdefault("aitas", {})
    next_state["aitas"]["attention_node_id"] = selected_node_id
    return next_state


def _safe_coordinate_pair(point: object) -> list[float] | None:
    if not isinstance(point, list) or len(point) < 2:
        return None
    try:
        return [float(point[0]), float(point[1])]
    except (TypeError, ValueError):
        return None


def _coerce_coordinate_pairs(points: object) -> list[list[float]]:
    if not isinstance(points, list):
        return []
    out: list[list[float]] = []
    for point in points:
        pair = _safe_coordinate_pair(point)
        if pair is not None:
            out.append(pair)
    return out


def _geometry_points(geometry: dict[str, Any]) -> list[list[float]]:
    geometry_type = _as_text(geometry.get("type"))
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        pair = _safe_coordinate_pair(coordinates)
        return [pair] if pair is not None else []
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        points: list[list[float]] = []
        for ring in coordinates:
            points.extend(_coerce_coordinate_pairs(ring))
        return points
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        points = []
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            for ring in polygon:
                points.extend(_coerce_coordinate_pairs(ring))
        return points
    return []


def _bounds_from_points(points: list[list[float]]) -> list[float]:
    if not points:
        return []
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _sanitize_active_path(node_ids: list[str], ordered_nodes: list[str]) -> list[str]:
    if not node_ids or not ordered_nodes:
        return []
    available = set(ordered_nodes)
    sanitized: list[str] = []
    for node_id in node_ids:
        token = _as_text(node_id)
        if token not in available:
            break
        if not sanitized and _node_depth(token) != 1:
            break
        if sanitized and _parent_node_id(token) != sanitized[-1]:
            break
        sanitized.append(token)
    return sanitized


def _empty_geospatial_projection() -> dict[str, Any]:
    return {
        "title": "Geospatial Projection",
        "data_source": "",
        "projection_source": "none",
        "projection_state": "awaiting_real_projection",
        "feature_count": 0,
        "render_feature_count": 0,
        "render_row_count": 0,
        "decode_summary": {
            "reference_binding_count": 0,
            "decoded_coordinate_count": 0,
            "failed_token_count": 0,
        },
        "projection_health": {"state": "empty", "reason_codes": []},
        "fallback_reason_codes": [],
        "warnings": [],
        "supporting_document_name": "",
        "projection_document_name": "",
        "selected_feature_id": "",
        "selected_feature_explicit": False,
        "selected_feature_geometry_type": "",
        "selected_feature_bounds": [],
        "focus_bounds": [],
        "collection_bounds": [],
        "empty_message": "No projected geometry is available until the active path resolves real CTS-GIS evidence.",
        "has_real_projection": False,
        "feature_collection": {
            "type": "FeatureCollection",
            "features": [],
            "bounds": [],
        },
        "features": [],
    }


def _real_geospatial_projection(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    service_surface: dict[str, Any],
    source_evidence: dict[str, Any],
    base_shell_request: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    map_projection = dict(service_surface.get("map_projection") or {})
    selected_document = dict(service_surface.get("selected_document") or {})
    selected_row = dict(service_surface.get("selected_row") or {})
    selected_row_address = _as_text(selected_row.get("datum_address"))
    render_set_summary = dict(service_surface.get("render_set_summary") or {})
    feature_collection = dict(map_projection.get("feature_collection") or {})
    raw_features = list(feature_collection.get("features") or [])
    polygon_features = [
        feature
        for feature in raw_features
        if _as_text((feature.get("geometry") or {}).get("type")) in {"Polygon", "MultiPolygon"}
    ]
    if not polygon_features:
        return {}, False

    selected_feature_id = _as_text((map_projection.get("selected_feature") or {}).get("feature_id"))
    selected_feature_explicit = bool(
        resolved_tool_state.get("selection", {}).get("selected_feature_explicit")
    )
    feature_entries: list[dict[str, Any]] = []
    feature_collection_features: list[dict[str, Any]] = []
    selected_feature_bounds: list[float] = []
    selected_geometry_type = ""
    all_points: list[list[float]] = []
    for feature in polygon_features:
        feature_id = _as_text(feature.get("id"))
        if not feature_id:
            continue
        geometry = dict(feature.get("geometry") or {})
        properties = dict(feature.get("properties") or {})
        geometry_points = _geometry_points(geometry)
        all_points.extend(geometry_points)
        is_selected = bool(feature.get("selected")) or (selected_feature_id and feature_id == selected_feature_id)
        feature_collection_features.append(
            {
                "type": "Feature",
                "id": feature_id,
                "geometry": geometry,
                "properties": properties,
            }
        )
        feature_entries.append(
            {
                "feature_id": feature_id,
                "label": _as_text(properties.get("profile_label"))
                or _as_text(properties.get("samras_node_id"))
                or feature_id,
                "node_id": _as_text(properties.get("samras_node_id")),
                "geometry_type": _as_text(geometry.get("type")) or "Polygon",
                "selected": is_selected,
                "shell_request": _selection_shell_request(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    tool_state=resolved_tool_state,
                    selected_row_address=selected_row_address,
                    selected_feature_id=feature_id,
                    base_shell_request=base_shell_request,
                ),
                "action": _shell_action(
                    "select_feature",
                    feature_id=feature_id,
                    row_address=selected_row_address,
                ),
            }
        )
        if is_selected and geometry_points:
            selected_feature_bounds = _bounds_from_points(geometry_points)
            selected_geometry_type = _as_text(geometry.get("type")) or "Polygon"

    if not feature_entries:
        return {}, False
    if not any(entry.get("selected") for entry in feature_entries):
        feature_entries[0]["selected"] = True
        selected_feature_id = _as_text(feature_entries[0].get("feature_id"))
        selected_geometry_type = _as_text(feature_entries[0].get("geometry_type"))
        selected_feature_bounds = []

    supporting_document_name = _as_text((source_evidence.get("administrative_source") or {}).get("document_name")) or _DEFAULT_SUPPORTING_DOCUMENT_NAME
    projection_document_name = _as_text(selected_document.get("document_name"))
    collection_bounds = list(feature_collection.get("bounds") or [])
    if not collection_bounds:
        collection_bounds = _bounds_from_points(all_points)
    return (
        {
            "title": "Geospatial Projection",
            "data_source": "cts_gis_polygon_projection",
            "projection_source": _as_text(map_projection.get("projection_source")) or "none",
            "projection_state": _as_text(map_projection.get("projection_state")) or "projectable",
            "feature_count": len(feature_entries),
            "render_feature_count": int(render_set_summary.get("render_feature_count") or len(feature_entries)),
            "render_row_count": int(render_set_summary.get("render_row_count") or 0),
            "decode_summary": dict(map_projection.get("decode_summary") or {}),
            "projection_health": dict(map_projection.get("projection_health") or {"state": "empty", "reason_codes": []}),
            "fallback_reason_codes": list(map_projection.get("fallback_reason_codes") or []),
            "warnings": list(map_projection.get("warnings") or []),
            "supporting_document_name": supporting_document_name,
            "projection_document_name": projection_document_name,
            "selected_feature_id": selected_feature_id,
            "selected_feature_explicit": selected_feature_explicit,
            "selected_feature_geometry_type": selected_geometry_type,
            "selected_feature_bounds": selected_feature_bounds,
            "focus_bounds": list(map_projection.get("focus_bounds") or []),
            "collection_bounds": collection_bounds,
            "empty_message": "Projection ready.",
            "has_real_projection": True,
            "feature_collection": {
                "type": "FeatureCollection",
                "features": feature_collection_features,
                "bounds": collection_bounds,
            },
            "features": feature_entries,
        },
        True,
    )


def _empty_profile_projection(*, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "title": "Profile Projection",
        "active_profile": {
            "label": "",
            "node_id": "",
            "feature_count": 0,
            "child_count": 0,
            "document_id": "",
        },
        "hierarchy": [],
        "district_precinct_collections": [],
        "summary_rows": [],
        "warnings": list(warnings or []),
        "district_overlay_toggle": {
            "enabled": False,
            "overlay_active": False,
            "time_token": "",
            "timeframe_tokens": [],
            "timeframe_match": False,
            "shell_request": {},
            "action": {},
        },
        "empty_message": "No projected profile is available until the active path resolves real CTS-GIS evidence.",
        "has_profile_state": False,
        "has_real_projection": False,
    }


def _seed_stage_document(
    *,
    document_id: str,
    document_name: str,
    target_node_address: str,
    title: str,
) -> dict[str, Any]:
    return {
        "schema": CTS_GIS_STAGE_INSERT_SCHEMA,
        "document_id": document_id,
        "document_name": document_name,
        "operation": "insert_datums",
        "datums": [
            {
                "family": "administrative_street",
                "valueGroup": 2,
                "targetNodeAddress": target_node_address,
                "title": title,
                "references": [
                    {"type": "msn-samras", "nodeAddress": target_node_address},
                    {"type": "title", "text": title},
                ],
            }
        ],
    }


def _seed_stage_yaml(
    *,
    document_id: str,
    document_name: str,
    target_node_address: str,
    title: str,
) -> str:
    safe_title = _as_text(title) or "ASCII STREET NAME"
    return "\n".join(
        [
            f"schema: {CTS_GIS_STAGE_INSERT_SCHEMA}",
            f"document_id: {document_id}",
            f"document_name: {document_name}",
            "operation: insert_datums",
            "datums:",
            "  - family: administrative_street",
            "    valueGroup: 2",
            f"    targetNodeAddress: {target_node_address}",
            f'    title: "{safe_title}"',
            "    references:",
            "      - type: msn-samras",
            f"        nodeAddress: {target_node_address}",
            "      - type: title",
            f'        text: "{safe_title}"',
        ]
    )


def _cts_gis_staging_widget(
    *,
    resolved_tool_state: dict[str, Any],
    service_surface: dict[str, Any],
    source_evidence: dict[str, Any],
    selected_node_id: str,
    selected_label: str,
    action_result: dict[str, Any],
) -> dict[str, Any]:
    stage_state = _staged_insert_state(resolved_tool_state.get("staged_insert"))
    selected_document = dict(service_surface.get("selected_document") or {})
    administrative_source = dict(source_evidence.get("administrative_source") or {})
    document_id = (
        _as_text(stage_state.get("normalized_payload", {}).get("document_id"))
        or _as_text(selected_document.get("document_id"))
        or _as_text(administrative_source.get("document_id"))
    )
    document_name = (
        _as_text(stage_state.get("normalized_payload", {}).get("document_name"))
        or _as_text(selected_document.get("document_name"))
        or _as_text(administrative_source.get("document_name"))
    )
    seed_title = (_as_text(selected_label) or "ASCII STREET NAME").upper()
    seed_document = _seed_stage_document(
        document_id=document_id,
        document_name=document_name,
        target_node_address=selected_node_id,
        title=seed_title,
    ) if document_id and document_name and selected_node_id else {}
    draft_text = _as_text(stage_state.get("draft_text"))
    if not draft_text and seed_document:
        draft_text = _seed_stage_yaml(
            document_id=document_id,
            document_name=document_name,
            target_node_address=selected_node_id,
            title=seed_title,
        )
    return {
        "kind": "cts_gis_staging_widget",
        "title": "Staged Insert",
        "summary": "YAML-first MOS-safe administrative datum inserts with preview/apply guarded in runtime.",
        "document_id": document_id,
        "document_name": document_name,
        "selected_node_id": selected_node_id,
        "seed_stage_document": seed_document,
        "draft_text": draft_text,
        "draft_format": _as_text(stage_state.get("draft_format")) or "yaml",
        "placeholder_title_requested": bool(stage_state.get("placeholder_title_requested")),
        "validation": dict(stage_state.get("last_validation") or {}),
        "preview": dict(stage_state.get("last_preview") or {}),
        "compiled_nimm_envelope": dict(stage_state.get("compiled_nimm_envelope") or {}),
        "compound_directives": dict((stage_state.get("compiled_nimm_envelope") or {}).get("compound_directives") or {}),
        "last_error": dict(stage_state.get("last_error") or {}),
        "soundness_report": dict(stage_state.get("soundness_report") or {}),
        "action_result": dict(action_result or {}),
        "actions": {
            "stage": _tool_action("stage"),
            "validate": _tool_action("validate"),
            "preview": _tool_action("preview"),
            "apply": _tool_action("apply"),
            "discard": _tool_action("discard"),
            "stage_insert_yaml": _tool_action("stage_insert_yaml"),
            "validate_stage": _tool_action("validate_stage"),
            "preview_apply": _tool_action("preview_apply"),
            "apply_stage": _tool_action("apply_stage"),
            "discard_stage": _tool_action("discard_stage"),
            "soundness_check": _tool_action("soundness_check"),
        },
        "datum_source_browser": _build_datum_source_browser(source_evidence),
        "ready": bool(document_id and selected_node_id),
    }


def _build_datum_source_browser(source_evidence: dict[str, Any]) -> dict[str, Any]:
    member_files = list((source_evidence.get("tool_anchor") or {}).get("member_files") or [])
    sos_voterid_source = dict(source_evidence.get("sos_voterid_source") or {})
    sos_voterid_available = bool(sos_voterid_source.get("exists"))
    voterid_section = _build_voterid_datum_section(source_evidence)
    return {
        "kind": "datum_source_browser",
        "title": "Source Datum Browser",
        "available_sources": [{"name": f, "kind": "member_file"} for f in member_files],
        "sos_voterid_available": sos_voterid_available,
        "voterid_datum_section": voterid_section,
        "empty_message": "" if (member_files or sos_voterid_available) else "No datum source documents found.",
    }


def _build_voterid_datum_section(source_evidence: dict[str, Any]) -> dict[str, Any]:
    sos_voterid_source = dict(source_evidence.get("sos_voterid_source") or {})
    exists = bool(sos_voterid_source.get("exists"))
    datum_entries: list[dict[str, Any]] = []
    if exists:
        payload = dict(sos_voterid_source.get("payload") or {})
        space = dict(payload.get("datum_addressing_abstraction_space") or {})
        for datum_key in sorted(space.keys()):
            raw = space[datum_key]
            if not isinstance(raw, list) or len(raw) < 2:
                continue
            slug = raw[1][0] if isinstance(raw[1], list) and raw[1] else ""
            datum_entries.append({
                "datum_address": datum_key,
                "slug": _as_text(slug),
            })
    return {
        "kind": "voterid_datum_section",
        "title": "Voter ID Source",
        "document_name": _as_text(sos_voterid_source.get("document_name")),
        "exists": exists,
        "entry_count": len(datum_entries),
        "datum_entries": datum_entries,
        "empty_message": "" if exists else "No voter ID source document is available.",
    }


def _build_cts_gis_structured_interface_body(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    navigation_canvas: dict[str, Any],
    source_evidence: dict[str, Any],
    service_surface: dict[str, Any],
    action_result: dict[str, Any],
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attention_profile = dict(service_surface.get("attention_profile") or {})
    lens_state = dict(service_surface.get("lens_state") or {})
    contextual_references = dict(service_surface.get("contextual_references") or {})
    district_precincts = dict(contextual_references.get("district_precincts") or {})
    selected_document = dict(service_surface.get("selected_document") or {})
    supporting_document = dict(source_evidence.get("administrative_source") or {})
    active_path_entries = list(navigation_canvas.get("active_path") or [])
    selected_node_id = _as_text(navigation_canvas.get("active_node_id"))
    supporting_document_name = _as_text(supporting_document.get("document_name")) or _DEFAULT_SUPPORTING_DOCUMENT_NAME
    projection_document_name = _as_text(selected_document.get("document_name")) or "—"
    selected_label = _as_text((active_path_entries[-1] if active_path_entries else {}).get("title")) or selected_node_id
    attention_profile_node_id = _as_text(attention_profile.get("node_id"))
    map_projection = dict(service_surface.get("map_projection") or {})
    decode_summary = dict(map_projection.get("decode_summary") or {})
    decode_summary_text = (
        f"{int(decode_summary.get('decoded_coordinate_count') or 0)}/"
        f"{int(decode_summary.get('reference_binding_count') or 0)} decoded"
        f" · {int(decode_summary.get('failed_token_count') or 0)} failed"
    )

    geospatial_projection = _empty_geospatial_projection()
    profile_projection = _empty_profile_projection(warnings=list(service_surface.get("warnings") or []))
    district_overlay_enabled = bool(resolved_tool_state.get("source", {}).get("precinct_district_overlay_enabled"))
    district_overlay_toggle = {
        "enabled": district_overlay_enabled,
        "overlay_active": bool(district_precincts.get("overlay_active")),
        "time_token": _as_text(district_precincts.get("time_token")),
        "timeframe_tokens": list(district_precincts.get("timeframe_tokens") or []),
        "timeframe_match": bool(district_precincts.get("timeframe_match")),
        "shell_request": _precinct_overlay_shell_request(
            portal_scope=portal_scope,
            shell_state=shell_state,
            tool_state=resolved_tool_state,
            enabled=not district_overlay_enabled,
            base_shell_request=base_shell_request,
        ),
        "action": _shell_action("toggle_overlay", enabled=not district_overlay_enabled),
    }
    district_precinct_collections = list(district_precincts.get("collections") or [])
    # Garland cascade Phase 4 — when the compiled artifact carries a
    # `district_profile_static` payload (direct-read of Ohio's source
    # datum producing the single canonical district + its 84 precinct
    # ids), synthesise a `district_precinct_collections` entry from it.
    # This keeps the existing _district_items / _admin_log_rows /
    # _active_district lookup flow as the single code path — only the
    # source of the collection changes (mediation vs static).
    _district_profile_static = dict(service_surface.get("district_profile_static") or {})
    _district_static_active = bool(_district_profile_static.get("collection_id"))
    if _district_static_active:
        _static_member_ids = [
            _as_text(item)
            for item in (_district_profile_static.get("member_precinct_ids") or [])
            if _as_text(item)
        ]
        _static_collection_id = _as_text(_district_profile_static.get("collection_id"))
        _static_label = _as_text(_district_profile_static.get("label")) or _static_collection_id
        _static_timeframe = _as_text(_district_profile_static.get("timeframe_token")) or _static_collection_id
        district_precinct_collections = [
            {
                "collection_id": _static_collection_id,
                "label": _static_label,
                "timeframe_token": _static_timeframe,
                "member_node_ids": list(_static_member_ids),
                "member_labels": list(_static_member_ids),
                "member_count": len(_static_member_ids),
                "precinct_count": len(_static_member_ids),
                "summary_state": f"{len(_static_member_ids)} precincts",
                "source": "district_profile_static",
            }
        ]
    real_geospatial_projection, garland_swapped = _real_geospatial_projection(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        service_surface=service_surface,
        source_evidence=source_evidence,
        base_shell_request=base_shell_request,
    )
    decode_ready = _as_text(navigation_canvas.get("decode_state")) == "ready"
    attention_matches_selection = bool(selected_node_id) and attention_profile_node_id == selected_node_id
    has_real_profile = (
        decode_ready
        and bool(selected_node_id)
        and attention_matches_selection
        and bool(attention_profile)
        and not bool(attention_profile.get("placeholder"))
        and (
            bool(attention_profile.get("has_geometry"))
            or int(map_projection.get("feature_count") or 0) > 0
        )
    )
    # True when decode ran but found zero HOPS bindings and no reference fallback.
    # Distinct from awaiting_real_projection (decode not yet run / source not loaded).
    _geometry_not_available = (
        not has_real_profile
        and decode_ready
        and bool(selected_node_id)
        and attention_matches_selection
        and int(decode_summary.get("reference_binding_count") or 0) == 0
        and int(map_projection.get("feature_count") or 0) == 0
    )
    if decode_ready and selected_node_id and attention_matches_selection and garland_swapped:
        geospatial_projection = {
            **real_geospatial_projection,
            "lens_state": lens_state,
        }
    elif decode_ready and selected_node_id and bool((source_evidence.get("administrative_source") or {}).get("exists")):
        geospatial_projection = {
            **geospatial_projection,
            "lens_state": lens_state,
            "projection_state": "geometry_not_available" if _geometry_not_available else "awaiting_real_projection",
            "empty_message": (
                "No geometry is registered for this node. Add geometry via the reference-promotion pipeline."
                if _geometry_not_available
                else "The selected node resolves structurally, but no HOPS projection is available for it yet."
            ),
        }

    # Attach overlay_layers to geospatial_projection so the renderer can drive
    # per-layer toggle buttons via renderGarlandSummaryObject.
    # district_overlay_toggle is kept on profile_projection for backwards compat.
    geospatial_projection = {
        **geospatial_projection,
        "overlay_layers": [
            {
                "layer_id": "district_precincts",
                "label": "District Precincts",
                "visible": bool(district_overlay_toggle.get("overlay_active")),
                "action": district_overlay_toggle.get("action") or None,
            }
        ],
    }

    # focus_bounds: populate from active features when navigating at precinct level
    # (few features = precinct scope).  Overrides any service-surface value.
    active_feature_entries = list(geospatial_projection.get("features") or [])
    if active_feature_entries and len(active_feature_entries) < 100:
        if not list(geospatial_projection.get("focus_bounds") or []):
            active_points: list[list[float]] = []
            for _feat in (
                (geospatial_projection.get("feature_collection") or {}).get("features") or []
            ):
                active_points.extend(_geometry_points(dict(_feat.get("geometry") or {})))
            computed_focus = _bounds_from_points(active_points)
            if computed_focus:
                geospatial_projection = {
                    **geospatial_projection,
                    "focus_bounds": computed_focus,
                }

    if has_real_profile:
        profile_projection = {
            "title": "Profile Projection",
            "active_profile": {
                "label": _as_text(attention_profile.get("profile_label")) or selected_label or selected_node_id,
                "node_id": _as_text(attention_profile.get("node_id")) or selected_node_id,
                "feature_count": int(attention_profile.get("feature_count") or 0),
                "child_count": int(attention_profile.get("child_count") or 0),
                "document_id": _as_text(attention_profile.get("document_id")),
            },
            "hierarchy": active_path_entries,
            "district_precinct_collections": district_precinct_collections,
            "summary_rows": [
                {"label": "Supporting document", "value": supporting_document_name},
                {"label": "Projection document", "value": projection_document_name},
                {"label": "Projection source", "value": _as_text(map_projection.get("projection_source")) or "none"},
                {"label": "Projection state", "value": _as_text(map_projection.get("projection_state")) or "inspect_only"},
                {"label": "Decode summary", "value": decode_summary_text},
            ],
            "warnings": list(service_surface.get("warnings") or []),
            "district_overlay_toggle": district_overlay_toggle,
            "empty_message": "",
            "has_profile_state": True,
            "has_real_projection": True,
            "lens_state": lens_state,
        }
    elif decode_ready and selected_node_id:
        _profile_state_value = "geometry_not_available" if _geometry_not_available else "awaiting_real_projection"
        _profile_empty_message = (
            "No geometry is registered for this node. Add geometry via the reference-promotion pipeline."
            if _geometry_not_available
            else "The selected node resolves structurally, but no profile projection is available for it yet."
        )
        profile_projection = {
            **profile_projection,
            "active_profile": {
                "label": selected_label or selected_node_id,
                "node_id": selected_node_id,
                "feature_count": 0,
                "child_count": 0,
                "document_id": "",
            },
            "hierarchy": active_path_entries,
            "district_precinct_collections": district_precinct_collections,
            "summary_rows": [
                {"label": "Supporting document", "value": supporting_document_name},
                {"label": "Projection document", "value": "—"},
                {"label": "Projection source", "value": _as_text(map_projection.get("projection_source")) or "none"},
                {"label": "Projection state", "value": _profile_state_value},
                {"label": "Decode summary", "value": decode_summary_text},
            ],
            "district_overlay_toggle": district_overlay_toggle,
            "empty_message": _profile_empty_message,
            "has_profile_state": True,
            "lens_state": lens_state,
        }

    # Build component frames for the garland tab.
    # lens_key is derived from the selected node so the render_key changes when attention changes.
    # When a frame engagement action arrived (engage_component_frame), action_result carries
    # engaged_frame_id for THIS cycle only (not persisted to tool_state). The matching frame
    # gets a unique render_key suffix so the client registry sees a mismatch and re-renders it.
    _engaged_frame_id = _as_text((action_result.get("details") or {}).get("engaged_frame_id"))
    _lens_key = _as_text(selected_node_id)
    _attention_context = _as_text(attention_profile_node_id) or _as_text(selected_node_id) or "unresolved"

    def _frame_lens(frame_id: str) -> str:
        return f"{_lens_key}:engaged" if _engaged_frame_id == frame_id else _lens_key

    _profile_frame_id = "administrative_node_profile"
    _geo_frame_id = f"{_profile_frame_id}__geospatial"

    # Garland cascade Phase 3.5 — sandbox-spatial-root admin profile.
    # When the compiled artifact carries `admin_profile_static` (baked
    # at compile time via direct-read of the Ohio source datum), the
    # admin profile renders Ohio identity regardless of the user's
    # current navigation. The cascade BELOW the admin profile (district
    # listing, district profile, precinct listing) still uses the
    # dynamic mediation result. When the static field is absent (e.g.
    # live-read path or older artifact), the admin profile falls back
    # to the dynamic mediation's `attention_profile` per the pre-3.5
    # behaviour.
    _admin_profile_static = dict(service_surface.get("admin_profile_static") or {})
    _admin_static_active = bool(_admin_profile_static.get("node_id"))
    if _admin_static_active:
        _admin_attention_node_id = _as_text(_admin_profile_static.get("node_id"))
        _profile_fields = list(_admin_profile_static.get("fields") or [])
        _profile_label = _as_text(_admin_profile_static.get("label")) or _admin_attention_node_id
        _admin_geo_payload = dict(_admin_profile_static.get("geospatial_projection") or {})
        _geo_frame = build_geospatial_component_frame(
            attention_node_id=_admin_attention_node_id,
            geospatial_projection=_admin_geo_payload,
            parent_frame_id=_profile_frame_id,
            lens_key=f"{_admin_attention_node_id}:admin_profile_static",
        )
    else:
        _admin_attention_node_id = _attention_context
        _geo_frame = build_geospatial_component_frame(
            attention_node_id=_attention_context,
            geospatial_projection=geospatial_projection,
            parent_frame_id=_profile_frame_id,
            lens_key=_frame_lens(_geo_frame_id),
        )
        # Admin-node profile contract: the only filament values rendered are the
        # ones a NIMM mediation directive can resolve from the SAMRAS source
        # datum the profile is focused on — TITLE, MSN_ID, CAPITAL_MSN_ID — plus
        # the DISTRICT_COLLECTIONS collection that is forwarded to the
        # administrative log listing. Computed display values (FEATURE_COUNT,
        # CHILD_COUNT, DISTRICT_COLLECTIONS row-count) are NOT source datum and
        # are deliberately omitted so the wireframe never claims data that
        # didn't come out of mediation.
        if has_real_profile:
            _profile_fields = [
                {"label": "TITLE", "value": _as_text(attention_profile.get("profile_label")) or selected_label or ""},
                {"label": "MSN_ID", "value": _as_text(attention_profile.get("node_id")) or selected_node_id or ""},
                {"label": "CAPITAL_MSN_ID", "value": _as_text(attention_profile.get("capital_msn_id")) or ""},
            ]
            _profile_label = _as_text(attention_profile.get("profile_label")) or selected_label or selected_node_id
        else:
            _profile_fields = [
                {"label": "TITLE", "value": ""},
                {"label": "MSN_ID", "value": ""},
                {"label": "CAPITAL_MSN_ID", "value": ""},
            ]
            _profile_label = selected_label or selected_node_id or ""
    _district_items: list[dict[str, str]] = []
    for index, collection in enumerate(district_precinct_collections, start=1):
        member_labels = list(collection.get("member_labels") or [])
        member_node_ids = list(collection.get("member_node_ids") or [])
        preview_source = member_labels or member_node_ids
        # Each district item carries a stable `row_address` (the collection's
        # `collection_id`, typically the timeframe_token like
        # `23_present-district_31`). The admin_log listing surfaces this as a
        # per-row identifier the client dispatches via select_district_row;
        # the wireframe build path matches the selection back to its
        # district collection to repurpose the col-3 slot (Phase 3).
        _district_items.append(
            {
                "label": _as_text(collection.get("label") or collection.get("timeframe_token")) or f"DISTRICT_LIST_{index:02d}",
                "value": _as_text(collection.get("summary_state")) or str(collection.get("precinct_count") or ""),
                "detail": ", ".join(_as_text(item) for item in preview_source[:4] if _as_text(item)),
                "row_address": _as_text(collection.get("collection_id")) or _as_text(collection.get("timeframe_token")),
            }
        )
    _district_collections = [
        {
            "label": "DISTRICT_COLLECTIONS",
            "items": _district_items,
            "empty_message": "No district list source is available for this administrative node yet.",
            "placeholder_item_count": 3,
        }
    ]
    _admin_profile_frame = build_profile_component_frame(
        frame_id=_profile_frame_id,
        attention_node_id=_admin_attention_node_id,
        label=_profile_label,
        fields=_profile_fields,
        variant="administrative_node",
        layout_slot="administrative_node_profile",
        collections=_district_collections,
        geospatial_frame=_geo_frame,
        lens_key=_frame_lens(_profile_frame_id),
        initializer_intent="resolve_administrative_node_profile",
    )
    # The administrative log listing is conceptually a child component of
    # the administrative_node_profile: each row is one DISTRICT_COLLECTIONS
    # entry the profile resolved from the correlated source datum document.
    # The listing only paints wireframe placeholder rows when the profile
    # found no district references; otherwise it paints exactly the rows
    # the profile materialised, so the wireframe matches the source datum.
    # Resolve the active district selection BEFORE building the admin-log
    # rows so each row can carry the `selected` flag (used by the frontend
    # listing renderer for [aria-pressed=true] feedback). Phase 4 auto-
    # selects the single canonical district when the artifact carries
    # `district_profile_static` and no explicit selection is on the wire.
    _selected_district_id = _as_text(
        (resolved_tool_state.get("selection") or {}).get("selected_district_id")
    )
    if not _selected_district_id and _district_static_active:
        _selected_district_id = _as_text(_district_profile_static.get("collection_id"))
    _admin_log_rows: list[dict[str, str]] = []
    for index, item in enumerate(_district_items, start=1):
        _district_label = _as_text(item.get("label"))
        _district_value = _as_text(item.get("value"))
        _district_detail = _as_text(item.get("detail"))
        _district_row_address = _as_text(item.get("row_address"))
        _entry_parts = [part for part in (_district_label, _district_value, _district_detail) if part]
        _admin_log_rows.append(
            {
                "index": f"{index:02d}",
                "entry": " · ".join(_entry_parts) if _entry_parts else _district_label,
                # Stable identifier the client dispatches via
                # `select_district_row {row_address: <this>}` (Phase 2 + 4).
                # The wireframe build path then matches this against the
                # district_precinct_collections collection_id to repurpose
                # the col-3 slot as a district profile (Phase 3).
                "row_address": _district_row_address,
                # Phase 4 — per-row select_action. Listing renderer makes
                # the row clickable and dispatches this on click/Enter/Space.
                "select_action": {
                    "action_kind": "select_district_row",
                    "action_payload": {"row_address": _district_row_address},
                } if _district_row_address else {},
                "selected": bool(
                    _selected_district_id and _district_row_address == _selected_district_id
                ),
            }
        )
    _admin_log_placeholder_count = 16 if not _admin_log_rows else 0
    _admin_log_frame = build_listing_component_frame(
        frame_id="administrative_log_entry_listing",
        label="Administrative Log Entry Listing",
        columns=[{"key": "index", "label": ""}, {"key": "entry", "label": "LOG ENTRY"}],
        rows=_admin_log_rows,
        attention_node_id=_attention_context,
        lens_key=_frame_lens("administrative_log_entry_listing"),
        layout_slot="administrative_log_entry_listing",
        source_kind="administrative_log",
        empty_message="Administrative log entries are not wired yet.",
        placeholder_row_count=_admin_log_placeholder_count,
        initializer_intent="resolve_administrative_log_listing",
    )
    # Phase 4 follow-up — the District Profile's Spatial Projection.
    # Prefer the artifact-baked `district_profile_static.geospatial_projection`
    # (84 precinct polygons, decoded offline from HOPS coordinate tokens
    # at compile/patch time). Falls back to an explicit pending state
    # if the artifact wasn't enriched with geometry yet.
    #
    # When a precinct row is selected (selected_precinct_id), flip the
    # matching feature's `selected` flag so the map renderer highlights
    # it instead of defaulting to the first precinct.
    _selected_precinct_id = _as_text(
        (resolved_tool_state.get("selection") or {}).get("selected_precinct_id")
    )
    _district_static_geo = dict(
        _district_profile_static.get("geospatial_projection") or {}
    )
    if _district_static_geo.get("has_real_projection"):
        _district_static_geo = copy.deepcopy(_district_static_geo)
        _features_with_selection: list[dict[str, Any]] = []
        _matched_selection = False
        for _index, _f in enumerate(list(_district_static_geo.get("features") or [])):
            if _selected_precinct_id:
                _is_match = _as_text(_f.get("feature_id")) == _selected_precinct_id
                _f["selected"] = _is_match
                if _is_match:
                    _matched_selection = True
                    _district_static_geo["selected_feature_id"] = _as_text(_f.get("feature_id"))
                    _district_static_geo["selected_feature_geometry_type"] = _as_text(
                        _f.get("geometry_type")
                    )
                    _district_static_geo["selected_feature_explicit"] = True
                    _bounds = _f.get("bounds") or []
                    if _bounds:
                        _district_static_geo["selected_feature_bounds"] = list(_bounds)
            else:
                # No explicit precinct selection — keep the baked default
                # (first feature selected=True) so the map renderer has
                # a focus target.
                _f["selected"] = _index == 0
            _features_with_selection.append(_f)
        if _selected_precinct_id and not _matched_selection and _features_with_selection:
            _features_with_selection[0]["selected"] = True
        _district_static_geo["features"] = _features_with_selection
        _precinct_geo_payload = _district_static_geo
    else:
        _precinct_geo_payload = _empty_geospatial_projection()
        _precinct_geo_payload["projection_state"] = "awaiting_decode_block"
        _precinct_geo_payload["projection_health"] = {
            "state": "blocked",
            "reason_codes": ["hops_magnitude_decode_unavailable"],
        }
        _precinct_geo_payload["empty_message"] = (
            "Precinct boundary projections pending HOPS magnitude decode."
        )
    _precinct_geo_frame = build_geospatial_component_frame(
        attention_node_id=_attention_context,
        geospatial_projection=_precinct_geo_payload,
        parent_frame_id="precinct_profile",
        lens_key=_frame_lens("precinct_profile__geospatial"),
    )
    # Phase 3 cascade: when the user has selected a district row from the
    # admin log listing (Phase 2 persisted the choice into
    # `tool_state.selection.selected_district_id`), repurpose the col-3
    # slot as a `district_profile`. Phase 4 also auto-selects the single
    # canonical district when the artifact carries `district_profile_static`
    # so the cascade resolves on first load. `_selected_district_id` is
    # already resolved above (needed for admin-log row `selected` flags).
    _active_district: dict[str, Any] | None = None
    if _selected_district_id:
        for _candidate in district_precinct_collections:
            _candidate_id = _as_text(_candidate.get("collection_id")) or _as_text(
                _candidate.get("timeframe_token")
            )
            if _candidate_id and _candidate_id == _selected_district_id:
                _active_district = _candidate
                break
    if _active_district is not None:
        # Phase 4 — col-3 frame is the District Profile. Label is the
        # literal "District Profile" per the cascade contract. The
        # district identifier (label / timeframe_token) is surfaced
        # alongside as a filament field rather than baked into the
        # title, so the variant chrome stays stable as the user
        # navigates between districts.
        _district_identity = (
            _as_text(_active_district.get("label"))
            or _as_text(_active_district.get("timeframe_token"))
            or _as_text(_active_district.get("collection_id"))
            or ""
        )
        _district_precinct_count = int(_active_district.get("member_count") or 0)
        _precinct_profile_frame = build_profile_component_frame(
            frame_id="precinct_profile",
            attention_node_id=_attention_context,
            label="District Profile",
            fields=[
                {"label": "DISTRICT_ID", "value": _district_identity},
                {"label": "PRECINCT_COUNT", "value": str(_district_precinct_count)},
            ],
            variant="district",
            layout_slot="precinct_profile",
            collections=[],
            geospatial_frame=_precinct_geo_frame,
            lens_key=_frame_lens("precinct_profile"),
            initializer_intent="resolve_district_profile",
        )
    else:
        _precinct_profile_frame = build_profile_component_frame(
            frame_id="precinct_profile",
            attention_node_id=_attention_context,
            label="Precinct Profile",
            fields=[
                {"label": "TITLE", "value": "—"},
                {"label": "MSN_ID", "value": "—"},
                {"label": "CAPITAL_MSN_ID", "value": "—"},
            ],
            variant="precinct",
            layout_slot="precinct_profile",
            collections=[
                {
                    "label": "PRECINCT_COLLECTIONS",
                    "items": _district_items,
                    "empty_message": "No selected precinct collection is available yet.",
                    "placeholder_item_count": 3,
                }
            ],
            geospatial_frame=_precinct_geo_frame,
            lens_key=_frame_lens("precinct_profile"),
            initializer_intent="resolve_precinct_profile",
        )
    # Garland cascade Phase 4 — col-4 (formerly "Log Listing Of Other
    # Voters") is repurposed as the *precinct listing* when a district
    # is active. Each row carries a `select_action` payload so the
    # frontend listing renderer can dispatch `select_precinct_row` on
    # click. frame_id stays `log_listing_other_voters` to preserve the
    # CSS layout slot. Selection feedback (`selected` flag) marks the
    # row that matches `tool_state.selection.selected_precinct_id`
    # (the dedicated cascade field — NOT `selected_feature_id`, which
    # mediation finalize churns). `_selected_precinct_id` is hoisted
    # to the top of the function so the district-profile geospatial
    # frame can also consume it.
    if _active_district is not None:
        _precinct_member_ids = [
            _as_text(item)
            for item in (_active_district.get("member_node_ids") or [])
            if _as_text(item)
        ]
        _precinct_rows: list[dict[str, Any]] = []
        for _idx, _pid in enumerate(_precinct_member_ids, start=1):
            _precinct_rows.append(
                {
                    "index": f"{_idx:02d}",
                    "entry": _pid,
                    "precinct_id": _pid,
                    "select_action": {
                        "action_kind": "select_precinct_row",
                        "action_payload": {"precinct_id": _pid},
                    },
                    "selected": bool(_selected_precinct_id and _pid == _selected_precinct_id),
                }
            )
        _precinct_listing_label = (
            f"Precinct Listing — {_as_text(_active_district.get('label')) or _selected_district_id}"
        )
        _other_voters_frame = build_listing_component_frame(
            frame_id="log_listing_other_voters",
            label=_precinct_listing_label,
            columns=[{"key": "index", "label": ""}, {"key": "entry", "label": "PRECINCT"}],
            rows=_precinct_rows,
            attention_node_id=_attention_context,
            lens_key=_frame_lens("log_listing_other_voters"),
            layout_slot="log_listing_other_voters",
            source_kind="precinct_listing",
            empty_message="No precincts are listed for the selected district.",
            placeholder_row_count=0,
            initializer_intent="resolve_precinct_listing",
        )
    else:
        _other_voters_frame = build_listing_component_frame(
            frame_id="log_listing_other_voters",
            label="Log Listing Of Other Voters",
            columns=[{"key": "index", "label": ""}, {"key": "entry", "label": "VOTER"}],
            rows=[],
            attention_node_id=_attention_context,
            lens_key=_frame_lens("log_listing_other_voters"),
            layout_slot="log_listing_other_voters",
            source_kind="voter_log",
            empty_message="Other voter listings are not wired yet.",
            placeholder_row_count=16,
            initializer_intent="resolve_other_voter_listing",
        )
    _election_history_frame = build_chronology_matrix_component_frame(
        frame_id="election_history",
        label="Election History / Election Types Across Time",
        row_headers=[
            {"key": "DISTRICT_31", "label": "DISTRICT_31"},
            {"key": "DISTRICT_32", "label": "DISTRICT_32"},
            {"key": "DISTRICT_33", "label": "DISTRICT_33"},
            {"key": "SPECIAL_ELECTION", "label": "SPECIAL ELECTION"},
            {"key": "REFERENDUM", "label": "REFERENDUM"},
        ],
        column_headers=["2012", "2013", "2014", "2016", "2018", "2020", "2022", "2023", "2024"],
        events=[],
        attention_node_id=_attention_context,
        lens_key=_frame_lens("election_history"),
        layout_slot="election_history",
        empty_message="Election history sources are not wired yet.",
        initializer_intent="resolve_election_history",
    )
    _voter_profile_frame = build_profile_component_frame(
        frame_id="voter_profile",
        attention_node_id=_attention_context,
        label="Voter Profile",
        fields=[
            {"label": "SOS_VOTERID", "value": ""},
            {"label": "FIRST_NAME", "value": ""},
            {"label": "MIDDLE_NAME", "value": ""},
            {"label": "LAST_NAME", "value": ""},
            {"label": "RESIDENTIAL_ADDRESS1 + RESIDENTIAL_SECONDARY_ADDR", "value": ""},
            {"label": "RESIDENTIAL_ZIP_PLUS4", "value": ""},
            {"label": "RESIDENTIAL_HOPS_GEOSPATIAL_ADDRESS", "value": ""},
            {"label": "MAILING_ADDRESS1 + MAILING_SECONDARY_ADDRESS", "value": ""},
            {"label": "MAILING_ZIP_PLUS4", "value": ""},
            {"label": "PARTY_AFFILIATION", "value": ""},
            {"label": "REGISTRATION_DATE", "value": ""},
        ],
        variant="voter",
        layout_slot="voter_profile",
        collections=[{"label": "BALLOT_LIST", "items": [], "empty_message": "No selected voter ballot list is loaded."}],
        lens_key=_frame_lens("voter_profile"),
        initializer_intent="resolve_voter_profile",
    )
    _garland_frame = build_component_group_frame(
        frame_id="garland_component_group",
        label="Garland",
        children=[
            _admin_profile_frame,
            _admin_log_frame,
            _precinct_profile_frame,
            _other_voters_frame,
            _election_history_frame,
            _voter_profile_frame,
        ],
        attention_node_id=_attention_context,
        lens_key=_frame_lens("garland_component_group"),
        layout="garland_wireframe",
        initializer_intent="compose_garland_component_shells",
        tab_id="garland",
    )

    return {
        "tab_host": "shared_interface_tabs",
        "default_tab_id": "garland",
        "tabs": [
            {
                "id": "garland",
                "label": "Garland",
                "summary": "Correlated projection surface that shows provenance, decode health, and document context for the selected SAMRAS node.",
                "active": True,
                "initializer": {
                    "verb": "mediate",
                    "target_authority": "cts_gis",
                    "datum_address": "1-1-2",
                    "intent": "resolve_profile_for_attention",
                },
            },
            {
                "id": "diktataograph",
                "label": "Diktataograph",
                "summary": _as_text(navigation_canvas.get("summary")) or "Magnitude-derived directory navigation for CTS-GIS.",
                "active": False,
            },
        ],
        "layout": "garland_tabbed",
        "narrow_layout": "garland_tabbed",
        "navigation_canvas": navigation_canvas,
        "staging_widget": _cts_gis_staging_widget(
            resolved_tool_state=resolved_tool_state,
            service_surface=service_surface,
            source_evidence=source_evidence,
            selected_node_id=selected_node_id,
            selected_label=selected_label,
            action_result=action_result,
        ),
        "garland_split_projection": {
            "kind": "garland_split_projection",
            "title": "Garland",
            "summary": "Correlated projection surface that shows provenance, decode health, and document context for the selected SAMRAS node.",
            "lens_state": lens_state,
            "geospatial_projection": geospatial_projection,
            "profile_projection": profile_projection,
        },
        "component_frames": [_garland_frame],
        "voterid_datum_section": _build_voterid_datum_section(source_evidence),
    }


def _service_surface_from_compiled_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    projection_model = dict(artifact.get("projection_model") or {})
    evidence_model = dict(artifact.get("evidence_model") or {})
    profile_summary = dict(projection_model.get("profile_summary") or {})
    selected_feature = dict(projection_model.get("selected_feature") or {})
    contextual_references = dict(projection_model.get("contextual_references") or {})
    # Garland cascade Phase 3.5 — sandbox-spatial-root admin profile.
    # The compiled artifact may carry an `admin_profile_static` payload
    # populated at compile time by direct-read of the Ohio source datum.
    # When present, the wireframe builder uses it for the admin profile's
    # filament + geospatial subject_slot, independent of where the user
    # has navigated. Pass it through service_surface so the builder has
    # a stable input.
    admin_profile_static = dict(artifact.get("admin_profile_static") or {})
    # Garland cascade Phase 4 — sandbox-rooted district profile. The
    # compiled artifact may carry a `district_profile_static` payload
    # populated at compile time by direct-read of Ohio's source datum
    # (collection_id + label + 84 member_precinct_ids). When present,
    # the wireframe builder synthesises a single district row for the
    # admin log listing, auto-selects it, and paints the 84 precincts
    # into col-4. Independent of the dynamic mediation cascade.
    district_profile_static = dict(artifact.get("district_profile_static") or {})
    return {
        "admin_profile_static": admin_profile_static,
        "district_profile_static": district_profile_static,
        "document_catalog": [],
        "selected_document": {"document_name": "", "document_id": profile_summary.get("document_id")},
        "attention_profile": {
            "node_id": _as_text(profile_summary.get("node_id")),
            "profile_label": _as_text(profile_summary.get("label")),
            "feature_count": int(profile_summary.get("feature_count") or 0),
            "child_count": int(profile_summary.get("child_count") or 0),
            "document_id": _as_text(profile_summary.get("document_id")),
            "has_geometry": bool(list((projection_model.get("feature_collection") or {}).get("features") or [])),
        },
        "lineage": [],
        "children": [],
        "render_profiles": [],
        "related_profiles": [],
        "render_set_summary": {
            "render_mode": "self",
            "render_profile_count": 0,
            "render_row_count": 0,
            "render_feature_count": len(list((projection_model.get("feature_collection") or {}).get("features") or [])),
        },
        "map_projection": {
            "projection_state": _as_text(projection_model.get("projection_state")) or "inspect_only",
            "projection_source": _as_text(projection_model.get("projection_source")) or "none",
            "projection_health": dict(projection_model.get("projection_health") or {"state": "empty", "reason_codes": []}),
            "fallback_reason_codes": list(projection_model.get("fallback_reason_codes") or []),
            "focus_bounds": projection_model.get("focus_bounds"),
            "selected_feature": selected_feature if selected_feature else None,
            "decode_summary": dict(projection_model.get("decode_summary") or {}),
            "feature_count": len(list((projection_model.get("feature_collection") or {}).get("features") or [])),
            "feature_collection": {
                "type": "FeatureCollection",
                "features": list((projection_model.get("feature_collection") or {}).get("features") or []),
                "bounds": (projection_model.get("feature_collection") or {}).get("bounds"),
            },
            "warnings": [],
        },
        "rows": [],
        "diagnostic_summary": dict(evidence_model.get("diagnostic_summary") or {}),
        "lens_state": {"overlay_mode": "auto", "raw_underlay_visible": False},
        "mediation_state": {
            "attention_document_id": _as_text(profile_summary.get("document_id")),
            "attention_node_id": _as_text(profile_summary.get("node_id")),
            "intention_token": "self",
            "available_intentions": [],
            "selection_summary": {},
        },
        "contextual_references": (
            contextual_references
            if contextual_references
            else {
                "district_precincts": {
                    "enabled": False,
                    "overlay_active": False,
                    "collections": [],
                    "collection_count": 0,
                }
            }
        ),
        "warnings": list(evidence_model.get("warnings") or []),
    }


def _hydrate_compiled_workbench_documents(
    *,
    service_surface: dict[str, Any],
    datum_store: SqliteSystemDatumStoreAdapter | None,
    tenant_id: str,
) -> None:
    """Populate workbench documents for compiled-only service surfaces.

    Production-strict compiled artifacts intentionally minimize payload size and can
    omit ``workbench_documents``. The shared datum-file workbench depends on this
    collection for gallery/anchor rendering, so hydrate it from the live datum store
    when available.
    """

    if list(service_surface.get("workbench_documents") or []):
        return
    if not isinstance(datum_store, SqliteSystemDatumStoreAdapter):
        return
    if list(service_surface.get("documents") or []):
        service_surface["workbench_documents"] = list(service_surface.get("documents") or [])
        return
    if datum_store is None:
        return

    db_file_str = str(datum_store._db_file)
    tenant_key = _as_text(tenant_id) or "fnd"
    cache_key = (db_file_str, tenant_key)
    db_mtime = datum_store._db_mtime_ns()
    cached = _WORKBENCH_PROJECTION_CACHE.get(cache_key)
    if cached is not None and cached[0] == db_mtime:
        projection_bundle = cached[1]
    else:
        projection_bundle = CtsGisReadOnlyService(datum_store).read_projection_bundle(
            tenant_key,
            project_all_documents=False,
        )
        _WORKBENCH_PROJECTION_CACHE[cache_key] = (db_mtime, projection_bundle)

    hydrated_documents = list(projection_bundle.get("workbench_documents") or [])
    if hydrated_documents:
        service_surface["workbench_documents"] = hydrated_documents
    if not list(service_surface.get("document_catalog") or []):
        service_surface["document_catalog"] = list(projection_bundle.get("document_catalog") or [])


def _public_selected_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": _as_text(document.get("document_id")),
        "source_kind": _as_text(document.get("source_kind")),
        "document_name": _as_text(document.get("document_name")),
        "relative_path": _as_text(document.get("relative_path")),
        "tool_id": _as_text(document.get("tool_id")),
        "source_authority": _as_text(document.get("source_authority")),
    }


def _public_projection_model(service_surface: dict[str, Any], *, include_evidence: bool) -> dict[str, Any]:
    map_projection = dict(service_surface.get("map_projection") or {})
    if include_evidence:
        return map_projection

    feature_collection = dict(map_projection.get("feature_collection") or {})
    selected_feature = dict(map_projection.get("selected_feature") or {})
    selected_feature.pop("feature", None)
    feature_count = int(map_projection.get("feature_count") or len(list(feature_collection.get("features") or [])))
    return {
        "projection_state": _as_text(map_projection.get("projection_state")) or "inspect_only",
        "projection_source": _as_text(map_projection.get("projection_source")) or "none",
        "projection_health": dict(map_projection.get("projection_health") or {"state": "empty", "reason_codes": []}),
        "fallback_reason_codes": list(map_projection.get("fallback_reason_codes") or []),
        "focus_bounds": list(map_projection.get("focus_bounds") or []),
        "decode_summary": dict(map_projection.get("decode_summary") or {}),
        "feature_count": feature_count,
        "feature_collection": {
            "type": "FeatureCollection",
            "features": [],
            "bounds": list(feature_collection.get("bounds") or []),
            "feature_count": feature_count,
        },
        "selected_feature": selected_feature,
    }


def _public_service_surface(service_surface: dict[str, Any], *, include_evidence: bool) -> dict[str, Any]:
    if include_evidence:
        return service_surface
    return {
        "selected_document": _public_selected_document(dict(service_surface.get("selected_document") or {})),
        "attention_profile": dict(service_surface.get("attention_profile") or {}),
        "render_set_summary": dict(service_surface.get("render_set_summary") or {}),
        "contextual_references": dict(service_surface.get("contextual_references") or {}),
        "diagnostic_summary": dict(service_surface.get("diagnostic_summary") or {}),
        "lens_state": dict(service_surface.get("lens_state") or {}),
        "mediation_state": dict(service_surface.get("mediation_state") or {}),
        "warnings": list(service_surface.get("warnings") or []),
    }


def _navigation_canvas_from_compiled_artifact(
    *,
    artifact: dict[str, Any],
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    base_shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nav_model = dict(artifact.get("navigation_model") or {})
    dropdown_models = list(nav_model.get("dropdowns") or [])
    active_path_models = list(nav_model.get("active_path") or [])
    diagnostics = list(nav_model.get("diagnostics") or [])
    title_map: dict[str, str] = {}
    available_nodes: set[str] = set()
    for dropdown in dropdown_models:
        for option in list(dropdown.get("options") or []):
            node_id = _as_text(option.get("node_id"))
            if node_id:
                title_map[node_id] = _as_text(option.get("title"))
                available_nodes.add(node_id)
    requested_active_path = _sanitize_active_path(
        list(resolved_tool_state.get("active_path") or []),
        sorted(available_nodes, key=_node_sort_key),
    )
    requested_selected_node_id = _as_text(resolved_tool_state.get("selected_node_id"))
    if not requested_active_path and requested_selected_node_id in available_nodes:
        requested_active_path = _sanitize_active_path(
            _active_path_from_node_id(requested_selected_node_id),
            sorted(available_nodes, key=_node_sort_key),
        )
    model_active_path = [
        _as_text(entry.get("node_id"))
        for entry in active_path_models
        if _as_text(entry.get("node_id"))
    ]
    effective_active_path = requested_active_path or model_active_path
    active_node_id = (
        effective_active_path[-1]
        if effective_active_path
        else (_as_text(nav_model.get("active_node_id")) or requested_selected_node_id)
    )
    requested_active_path_raw = [
        _as_text(item)
        for item in list((resolved_tool_state.get("source") or {}).get("requested_active_path_raw") or [])
        if _as_text(item)
    ]
    requested_selected_node_id_raw = _as_text((resolved_tool_state.get("source") or {}).get("requested_selected_node_id_raw"))
    if requested_selected_node_id_raw and requested_selected_node_id_raw not in available_nodes:
        diagnostics.append(
            _navigation_diagnostic(
                "unresolved_node_binding",
                "Requested selection could not be resolved in compiled SAMRAS dropdown bindings.",
                severity="warning",
                node_ids=[requested_selected_node_id_raw],
            )
        )
    if requested_active_path_raw and requested_active_path != requested_active_path_raw:
        diagnostics.append(
            _navigation_diagnostic(
                "invalid_active_path",
                "Requested active path did not match compiled hierarchical dropdown lineage and was normalized.",
                severity="warning",
                node_ids=requested_active_path_raw,
            )
        )
    dropdowns: list[dict[str, Any]] = []
    effective_selections_by_depth: dict[int, str] = {}
    for depth, node_id in enumerate(effective_active_path, start=1):
        effective_selections_by_depth[depth] = node_id
    for index, dropdown in enumerate(dropdown_models):
        depth = int(dropdown.get("depth") or index + 1)
        selected_node_id = _as_text(dropdown.get("selected_node_id")) or active_node_id
        if depth in effective_selections_by_depth:
            selected_node_id = effective_selections_by_depth[depth]
        dropdown_options = []
        for option in list(dropdown.get("options") or []):
            node_id = _as_text(option.get("node_id"))
            if not node_id:
                continue
            dropdown_options.append(
                _directory_option_payload(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    resolved_tool_state=resolved_tool_state,
                    node_id=node_id,
                    title_map=title_map,
                    selected_node_id=selected_node_id,
                    base_shell_request=base_shell_request,
                )
            )
        dropdowns.append(
            {
                "depth": depth,
                "parent_node_id": _as_text(dropdown.get("parent_node_id")),
                "selected_node_id": selected_node_id,
                "options": dropdown_options,
            }
        )
    active_path = []
    for node_id in effective_active_path:
        if not node_id:
            continue
        active_path.append(
            _directory_option_payload(
                portal_scope=portal_scope,
                shell_state=shell_state,
                resolved_tool_state=resolved_tool_state,
                node_id=node_id,
                title_map=title_map,
                selected_node_id=active_node_id,
                base_shell_request=base_shell_request,
            )
        )
    return {
        "kind": "diktataograph_navigation_canvas",
        "title": "Diktataograph",
        "summary": "Compiled SAMRAS navigation state.",
        "mode": _CTS_GIS_NAV_MODE_DIRECTORY,
        "source_authority": _as_text(nav_model.get("source_authority")) or "samras_magnitude",
        "decode_state": _as_text(nav_model.get("decode_state")) or "blocked_invalid_magnitude",
        "diagnostics": diagnostics,
        "dropdowns": dropdowns,
        "active_path": active_path,
        "active_node_id": active_node_id,
    }


def build_portal_cts_gis_surface_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    tool_rows: list[dict[str, Any]] | None = None,
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total_started_at = perf_counter()
    phase_timings_ms: dict[str, float] = {}
    tool_entry = resolve_portal_tool_registry_entry(surface_id=CTS_GIS_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("CTS-GIS tool surface is not registered")
    normalized_request_payload = request_payload if isinstance(request_payload, dict) else {}
    _assert_no_legacy_maps_aliases(normalized_request_payload)
    requested_tool_state = _normalize_tool_state(normalized_request_payload)
    runtime_mode = _runtime_mode_from_request(normalized_request_payload)
    force_live_read = bool(normalized_request_payload.get("force_live_read"))
    entrypoint_id = _as_text(normalized_request_payload.get("cts_gis_entrypoint_id")) or CTS_GIS_TOOL_ENTRYPOINT_ID
    read_write_posture = _as_text(normalized_request_payload.get("cts_gis_read_write_posture")) or tool_entry.read_write_posture
    action_result = (
        dict(normalized_request_payload.get("cts_gis_action_result"))
        if isinstance(normalized_request_payload.get("cts_gis_action_result"), dict)
        else {}
    )
    include_evidence = bool(normalized_request_payload.get("include_evidence")) or runtime_mode == _CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    missing_integrations: list[str] = []
    missing_capabilities = [
        capability for capability in tool_entry.required_capabilities if capability not in portal_scope.capabilities
    ]
    datum_store = _runtime_datum_store(data_dir=data_dir, authority_db_file=authority_db_file)
    compiled_path = compiled_artifact_path(data_dir, portal_scope_id=portal_scope.scope_id)
    # MOS-aware: the disk sandbox/cts-gis/sources/ tree was retired (2026-05-17);
    # fall back to a MOS-backed summary so source_layout_valid reflects the live store.
    source_layout = build_cts_gis_source_layout_summary(
        data_dir, datum_store=datum_store, tenant_id=portal_scope.scope_id
    )
    source_layout_valid, source_layout_issues = validate_cts_gis_source_layout(source_layout)
    compiled_artifact = read_compiled_artifact_cached(compiled_path)
    compiled_valid, compiled_issues = validate_compiled_artifact(
        compiled_artifact,
        expected_portal_scope_id=portal_scope.scope_id,
        expected_source_layout=source_layout,
    )
    strict_invalid = runtime_mode == _CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT and not compiled_valid
    compiled_refresh_requested = bool(normalized_request_payload.get("persist_compiled_artifact")) or force_live_read
    compiled_refresh_status = {
        "requested": compiled_refresh_requested,
        "performed": False,
        "path": str(compiled_path) if compiled_path is not None else "",
        "reason": "production_strict_compiled_only" if runtime_mode == _CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT else "diagnostic_only",
    }
    tool_shell_request_base = build_portal_shell_request_payload(
        portal_scope=portal_scope,
        shell_state=shell_state,
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    tool_shell_request_base["runtime_mode"] = runtime_mode
    if (
        not force_live_read
        and runtime_mode == _CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT
        and compiled_valid
        and compiled_artifact is not None
    ):
        compiled_default_tool_state = _tool_state_clone(dict(compiled_artifact.get("default_tool_state") or {}))
        requested_tool_state = _merge_tool_state(
            compiled_default_tool_state,
            _request_tool_state_overrides(requested_tool_state, normalized_request_payload),
        )
        # NOTE — Default-to-Ohio override removed.
        #
        # Previously this block force-substituted the request's selected
        # node to CTS_GIS_PRESUMED_ATTENTION_NODE_ID ("3-2-3-17") whenever
        # the URL had no datum/object segment. That looked correct in
        # tests but in production it forced every landing-page request
        # off the compiled-artifact fast path (which keys on Summit
        # County, the artifact's baked default) and onto the live-read
        # path. Live reads cost ~35s per request and ~700 MB extra RSS
        # on this 3.87 GB box, which saturated swap and triggered
        # gunicorn worker SIGKILLs. Nginx then 504'd.
        #
        # Re-enable the Ohio default via the artifact (recompile
        # `compiled/cts_gis.fnd.compiled.json` with
        # default_tool_state.selected_node_id = "3-2-3-17") so the
        # default landing stays on the cached fast path.
        # Tracked: TASK-CTS-GIS-GARLAND-CASCADE-2026-05-11 (Phase 1 +
        # artifact recompile follow-up).
        pass
        navigation_canvas = _navigation_canvas_from_compiled_artifact(
            artifact=compiled_artifact,
            portal_scope=portal_scope,
            shell_state=shell_state,
            resolved_tool_state=requested_tool_state,
            base_shell_request=tool_shell_request_base,
        )
        service_surface_started_at = perf_counter()
        if _strict_projection_context_differs(
            compiled_artifact=compiled_artifact,
            requested_tool_state=requested_tool_state,
        ):
            service_surface = _read_live_service_surface(
                portal_scope=portal_scope,
                datum_store=datum_store,
                requested_tool_state=requested_tool_state,
                request_payload=normalized_request_payload,
            )
        else:
            cache_key = (
                str(compiled_path) if compiled_path is not None else "",
                _compiled_artifact_signature(compiled_path),
                _canonical_tool_state_hash(requested_tool_state),
            )
            cached_surface = (
                _COMPILED_SERVICE_SURFACE_CACHE.get(cache_key) if cache_key[1] else None
            )
            if cached_surface is not None:
                service_surface = copy.deepcopy(cached_surface)
                _COMPILED_SERVICE_SURFACE_CACHE.move_to_end(cache_key)
            else:
                service_surface = _service_surface_from_compiled_artifact(compiled_artifact)
                if cache_key[1]:
                    _COMPILED_SERVICE_SURFACE_CACHE[cache_key] = copy.deepcopy(service_surface)
                    while len(_COMPILED_SERVICE_SURFACE_CACHE) > _COMPILED_SERVICE_SURFACE_CACHE_MAX:
                        _COMPILED_SERVICE_SURFACE_CACHE.popitem(last=False)
        _hydrate_compiled_workbench_documents(
            service_surface=service_surface,
            datum_store=datum_store,
            tenant_id=portal_scope.scope_id,
        )
        # Phase 4 — even when the live-read path produced the surface
        # (`_strict_projection_context_differs` returned True), the
        # Garland cascade still needs `admin_profile_static` and
        # `district_profile_static` to drive col-1 / col-3 / col-4.
        # These are sandbox-rooted (attention-independent), so inject
        # them from the artifact regardless of which path ran.
        if "admin_profile_static" not in service_surface:
            service_surface["admin_profile_static"] = dict(
                compiled_artifact.get("admin_profile_static") or {}
            )
        if "district_profile_static" not in service_surface:
            service_surface["district_profile_static"] = dict(
                compiled_artifact.get("district_profile_static") or {}
            )
        phase_timings_ms["service_surface_read"] = round((perf_counter() - service_surface_started_at) * 1000.0, 3)
        resolved_tool_state = _tool_state_for_navigation(
            _resolved_tool_state(
                requested_tool_state,
                service_surface,
            ),
            navigation_canvas,
        )
        resolved_tool_state.setdefault("source", {})
        for key in ("requested_active_path_raw", "requested_selected_node_id_raw"):
            if key in dict(requested_tool_state.get("source") or {}):
                resolved_tool_state["source"][key] = requested_tool_state["source"][key]
        source_evidence = dict((compiled_artifact.get("evidence_model") or {}).get("source_evidence") or {})
        source_evidence.setdefault(
            "readiness",
            {"state": "ready", "message": "CTS-GIS loaded compiled artifact successfully."},
        )
        source_evidence["source_layout"] = dict(compiled_artifact.get("source_layout") or source_layout)
    elif (
        not force_live_read
        and compiled_artifact is not None
        and runtime_mode == _CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC
        and not compiled_valid
    ):
        # Stale-artifact fallback: serve the previously-compiled projection (with a
        # compiled_state_dirty warning) and kick off a background rebuild instead of
        # blocking the request on a synchronous live read of all source files. This
        # is the path that produced user-visible 504s on cold deploys / source touches.
        rebuild_scheduled = schedule_compiled_artifact_rebuild_async(
            data_dir=data_dir,
            private_dir=private_dir,
            scope_id=portal_scope.scope_id,
            compiled_path=compiled_path,
        )
        compiled_default_tool_state = _tool_state_clone(dict(compiled_artifact.get("default_tool_state") or {}))
        requested_tool_state = _merge_tool_state(
            compiled_default_tool_state,
            _request_tool_state_overrides(requested_tool_state, normalized_request_payload),
        )
        navigation_canvas = _navigation_canvas_from_compiled_artifact(
            artifact=compiled_artifact,
            portal_scope=portal_scope,
            shell_state=shell_state,
            resolved_tool_state=requested_tool_state,
            base_shell_request=tool_shell_request_base,
        )
        service_surface_started_at = perf_counter()
        service_surface = _service_surface_from_compiled_artifact(compiled_artifact)
        _hydrate_compiled_workbench_documents(
            service_surface=service_surface,
            datum_store=datum_store,
            tenant_id=portal_scope.scope_id,
        )
        phase_timings_ms["service_surface_read"] = round((perf_counter() - service_surface_started_at) * 1000.0, 3)
        resolved_tool_state = _tool_state_for_navigation(
            _resolved_tool_state(requested_tool_state, service_surface),
            navigation_canvas,
        )
        resolved_tool_state.setdefault("source", {})
        for key in ("requested_active_path_raw", "requested_selected_node_id_raw"):
            if key in dict(requested_tool_state.get("source") or {}):
                resolved_tool_state["source"][key] = requested_tool_state["source"][key]
        source_evidence = dict((compiled_artifact.get("evidence_model") or {}).get("source_evidence") or {})
        warnings_list = list(source_evidence.get("warnings") or [])
        if "compiled_state_dirty" not in warnings_list:
            warnings_list.append("compiled_state_dirty")
        source_evidence["warnings"] = warnings_list
        source_evidence["readiness"] = {
            "state": "ready_stale",
            "message": (
                "Serving stale CTS-GIS compiled artifact while a background rebuild is running."
                if rebuild_scheduled
                else "Serving stale CTS-GIS compiled artifact; a previous rebuild is still in progress."
            ),
        }
        source_evidence["source_layout"] = dict(compiled_artifact.get("source_layout") or source_layout)
        compiled_refresh_status = {
            "requested": True,
            "performed": False,
            "scheduled_async": rebuild_scheduled,
            "path": str(compiled_path) if compiled_path is not None else "",
            "reason": "compiled_state_dirty_async_rebuild",
        }
    elif (not force_live_read) and runtime_mode == _CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT and strict_invalid:
        service_surface_started_at = perf_counter()
        service_surface = {
            "document_catalog": [],
            "selected_document": None,
            "attention_profile": None,
            "lineage": [],
            "children": [],
            "render_profiles": [],
            "related_profiles": [],
            "render_set_summary": {"render_feature_count": 0, "render_row_count": 0, "render_profile_count": 0},
            "map_projection": {"projection_state": "compiled_state_invalid", "selected_feature": None},
            "rows": [],
            "diagnostic_summary": {"compiled_issues": list(compiled_issues)},
            "lens_state": {"overlay_mode": "auto", "raw_underlay_visible": False},
            "mediation_state": {
                "attention_document_id": "",
                "attention_node_id": "",
                "intention_token": "self",
                "available_intentions": [],
            },
            "warnings": ["compiled_cts_gis_state_invalid"],
        }
        phase_timings_ms["service_surface_read"] = round((perf_counter() - service_surface_started_at) * 1000.0, 3)
        resolved_tool_state = requested_tool_state
        source_evidence = {
            "readiness": {
                "state": "compiled_state_invalid",
                "message": "Compiled CTS-GIS state invalid. Run the CTS-GIS compile command or switch to audit_forensic mode.",
            },
            "warnings": ["compiled_cts_gis_state_invalid", *list(compiled_issues)],
            "source_layout": dict(source_layout),
        }
        navigation_canvas = {
            "kind": "diktataograph_navigation_canvas",
            "title": "Diktataograph",
            "summary": "CTS-GIS navigation is unavailable until compiled state is valid.",
            "mode": _CTS_GIS_NAV_MODE_DIRECTORY,
            "source_authority": "samras_magnitude",
            "decode_state": "blocked_invalid_magnitude",
            "diagnostics": [
                _navigation_diagnostic(
                    "compiled_state_invalid",
                    "Compiled CTS-GIS state is invalid for production_strict mode.",
                    datum_addresses=list(compiled_issues),
                )
            ],
            "dropdowns": [],
            "active_path": [],
            "active_node_id": "",
        }
    else:
        service_surface_started_at = perf_counter()
        service_surface = _read_live_service_surface(
            portal_scope=portal_scope,
            datum_store=datum_store,
            requested_tool_state=requested_tool_state,
            request_payload=normalized_request_payload,
        )
        phase_timings_ms["service_surface_read"] = round((perf_counter() - service_surface_started_at) * 1000.0, 3)
        resolved_tool_state = _resolved_tool_state(requested_tool_state, service_surface)
        source_evidence_started_at = perf_counter()
        source_evidence = _build_source_evidence(
            data_dir=data_dir,
            private_dir=private_dir,
            service_surface=service_surface,
            source_layout=source_layout,
            datum_store=datum_store,
            tenant_id=portal_scope.scope_id,
        )
        phase_timings_ms["source_evidence"] = round((perf_counter() - source_evidence_started_at) * 1000.0, 3)
        navigation_started_at = perf_counter()
        navigation_canvas = _build_directory_dropdown_navigation(
            portal_scope=portal_scope,
            shell_state=shell_state,
            resolved_tool_state=resolved_tool_state,
            source_evidence=source_evidence,
            base_shell_request=tool_shell_request_base,
        )
        phase_timings_ms["navigation_canvas"] = round((perf_counter() - navigation_started_at) * 1000.0, 3)
        resolved_tool_state = _tool_state_for_navigation(resolved_tool_state, navigation_canvas)
        if compiled_refresh_requested and source_layout_valid:
            # Bake the sandbox-rooted profile_static (admin identity + district
            # outline geometry, district membership) so the persisted artifact
            # is complete. Disk-first, MOS-fallback. See
            # CTS-GIS-Compile-Pipeline-MOS-Migration-2026-05-27.
            admin_profile_static, district_profile_static = _cts_gis_profile_static_payloads(
                datum_store=datum_store,
                tenant_id=portal_scope.scope_id,
            )
            compiled_out = build_compiled_artifact(
                portal_scope_id=portal_scope.scope_id,
                source_evidence=source_evidence,
                service_surface=service_surface,
                navigation_canvas=navigation_canvas,
                default_tool_state=resolved_tool_state,
                source_layout=source_layout,
                build_mode=_CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
                admin_profile_static=admin_profile_static,
                district_profile_static=district_profile_static,
            )
            written_path = write_compiled_artifact(compiled_path, compiled_out)
            compiled_refresh_status = {
                "requested": True,
                "performed": True,
                "path": str(written_path) if written_path is not None else "",
                "reason": "force_live_read" if force_live_read else "persist_compiled_artifact",
            }
        elif compiled_refresh_requested:
            compiled_refresh_status = {
                "requested": True,
                "performed": False,
                "path": str(compiled_path) if compiled_path is not None else "",
                "reason": "source_layout_invalid",
            }
    datum_summary_started_at = perf_counter()
    datum_summary = _datum_summary_from_service_surface(service_surface)
    if datum_summary is None:
        datum_summary = _datum_summary(
            data_dir,
            portal_instance_id=portal_scope.scope_id,
            authority_db_file=authority_db_file,
        )
    phase_timings_ms["datum_summary"] = round((perf_counter() - datum_summary_started_at) * 1000.0, 3)
    missing_integrations = [] if datum_summary.get("configured") else ["data_dir"]
    source_warnings = _dedupe_warnings(list(source_evidence.get("warnings") or []))
    source_evidence = {**source_evidence, "warnings": source_warnings}
    service_warnings = _dedupe_warnings(
        list(service_surface.get("warnings") or []),
        source_warnings,
    )
    service_surface = {
        **service_surface,
        "warnings": service_warnings,
    }
    source_evidence_public = source_evidence if include_evidence else {
        "readiness": dict(source_evidence.get("readiness") or {}),
        "warnings": list(source_evidence.get("warnings") or []),
    }
    phase_timings_ms.setdefault("source_evidence", 0.0)
    phase_timings_ms.setdefault("navigation_canvas", 0.0)
    operational = bool(
        configured
        and enabled
        and not missing_integrations
        and not missing_capabilities
        and _as_text((source_evidence.get("readiness") or {}).get("state")) == "ready"
    )
    interface_body_started_at = perf_counter()
    interface_body = _build_cts_gis_structured_interface_body(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        navigation_canvas=navigation_canvas,
        source_evidence=source_evidence,
        service_surface=service_surface,
        action_result=action_result,
        base_shell_request=tool_shell_request_base,
    )
    phase_timings_ms["interface_body"] = round((perf_counter() - interface_body_started_at) * 1000.0, 3)
    control_panel_started_at = perf_counter()
    projection_model_public = _public_projection_model(service_surface, include_evidence=include_evidence)
    service_surface_public = _public_service_surface(service_surface, include_evidence=include_evidence)
    surface_payload = {
        "schema": CTS_GIS_TOOL_SURFACE_SCHEMA,
        "kind": "tool_mediation_surface",
        "tool_id": tool_entry.tool_id,
        "surface_id": CTS_GIS_TOOL_SURFACE_ID,
        "entrypoint_id": entrypoint_id,
        "title": "CTS-GIS",
        "subtitle": "Spatial mediation surface owned by SYSTEM.",
        "tool": {
            "tool_id": tool_entry.tool_id,
            "label": tool_entry.label,
            "summary": tool_entry.summary,
            "configured": configured,
            "enabled": enabled,
            "operational": operational,
            "missing_integrations": missing_integrations,
            "required_capabilities": list(tool_entry.required_capabilities),
            "missing_capabilities": missing_capabilities,
        },
        "datum_summary": datum_summary,
        "focus_subject": dict(shell_state.focus_subject or {}),
        "mediation_subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "request_contract": {
            "schema": CTS_GIS_TOOL_REQUEST_SCHEMA,
            "route": CTS_GIS_TOOL_ROUTE,
            "surface_id": CTS_GIS_TOOL_SURFACE_ID,
            "tool_state_supported": True,
            "runtime_modes": [
                _CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT,
                _CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
            ],
            "legacy_aliases": [
                "mediation_state.attention_node_id",
                "mediation_state.intention_token",
                "selected_row_address",
                "selected_feature_id",
            ],
            "action_contract": {
                "schema": CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA,
                "result_schema": CTS_GIS_ACTION_RESULT_SCHEMA,
                "route": CTS_GIS_TOOL_ACTION_ROUTE,
                "entrypoint_id": CTS_GIS_TOOL_ACTION_ENTRYPOINT_ID,
                "action_kinds": sorted(_ALLOWED_ACTION_KINDS),
                "canonical_lifecycle_actions": sorted(CTS_GIS_CANONICAL_ACTIONS),
                "compatibility_action_aliases": dict(CTS_GIS_MUTATION_ACTION_ALIASES),
            },
        },
        "runtime_mode": runtime_mode,
        "tool_state": resolved_tool_state,
        "staged_insert": dict(_staged_insert_state(resolved_tool_state.get("staged_insert"))),
        "nimm_envelope": dict(_staged_insert_state(resolved_tool_state.get("staged_insert")).get("compiled_nimm_envelope") or {}),
        "action_result": action_result,
        "source_evidence": source_evidence_public,
        "projection_model": projection_model_public,
        "evidence_model": {
            "source_evidence": source_evidence_public,
            "diagnostic_summary": dict(service_surface.get("diagnostic_summary") or {}),
            "warnings": list(service_surface.get("warnings") or []),
        },
        "warnings": service_warnings,
        "readiness": dict(source_evidence_public.get("readiness") or {}),
        "service_surface": service_surface_public,
    }
    control_panel = attach_region_family_contract(
        _build_cts_gis_directive_panel(
            portal_scope=portal_scope,
            shell_state=shell_state,
            data_dir=data_dir,
            private_dir=private_dir,
            tool_rows=list(tool_rows or []),
            resolved_tool_state=resolved_tool_state,
            source_evidence=source_evidence_public,
            service_surface=service_surface,
            action_result=action_result,
            base_shell_request=tool_shell_request_base,
        ),
        family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    phase_timings_ms["control_panel"] = round((perf_counter() - control_panel_started_at) * 1000.0, 3)
    phase_timings_ms["total_bundle_build"] = round((perf_counter() - total_started_at) * 1000.0, 3)
    runtime_diagnostics = {
        "phase_timings_ms": phase_timings_ms,
        "runtime_mode": runtime_mode,
        "compiled_artifact_path": str(compiled_path) if compiled_path is not None else "",
        "compiled_artifact_valid": bool(compiled_valid),
        "compiled_artifact_issues": list(compiled_issues),
        "compiled_refresh": compiled_refresh_status,
        "source_layout_valid": bool(source_layout_valid),
        "source_layout_issues": list(source_layout_issues),
        "source_layout_fingerprint": _as_text(source_layout.get("fingerprint")),
        "source_layout_counts": {
            "top_level_file_count": int(source_layout.get("top_level_file_count") or 0),
            "precinct_file_count": int(source_layout.get("precinct_file_count") or 0),
            "total_file_count": int(source_layout.get("total_file_count") or 0),
        },
        "service_document_catalog_count": len(list(service_surface.get("document_catalog") or [])),
        "service_render_feature_count": int((service_surface.get("render_set_summary") or {}).get("render_feature_count") or 0),
        "authority_document_count": int(datum_summary.get("document_count") or 0),
        "navigation_dropdown_count": len(list(navigation_canvas.get("dropdowns") or [])),
        "geospatial_feature_count": int(
            (
                (
                    (interface_body.get("garland_split_projection") or {}).get("geospatial_projection")
                    if isinstance(interface_body.get("garland_split_projection"), dict)
                    else {}
                )
                or {}
            ).get("feature_count")
            or 0
        ),
    }
    surface_payload["runtime_diagnostics"] = runtime_diagnostics
    stage_state_public = _staged_insert_state(resolved_tool_state.get("staged_insert"))
    stage_preview_public = dict(stage_state_public.get("last_preview") or {})
    dict(stage_state_public.get("last_validation") or {})

    # Determine workbench mode: active manipulation or idle tool overview
    has_active_manipulation = bool(stage_preview_public) or _as_text(action_result.get("action_kind")) in {
        "preview_apply",
        "apply_stage",
        "validate_manipulation_stage",
        "stage_insert_yaml",
        "validate_stage",
    }

    # Always show workbench with appropriate content
    show_workbench = True
    forced_visible = has_active_manipulation  # Force visible only during manipulation

    # Build tool summary for idle state
    {
        "tool_id": tool_entry.tool_id,
        "configured": tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id),
        "operational": operational,
        "source_layout_state": _as_text((source_evidence_public.get("readiness") or {}).get("state")) or "pending",
        "document_count": len(list(service_surface.get("workbench_documents") or service_surface.get("documents") or [])),
        "active_document_id": _as_text((resolved_tool_state.get("source") or {}).get("attention_document_id")),
        "help_text": "Load a structure or stage an insert operation to begin." if not has_active_manipulation else "",
    }

    cts_gis_sandbox_documents = _cts_gis_workbench_documents(service_surface)
    cts_gis_anchor_document = None
    cts_gis_selected_document = None
    focus_file_key = segment_id_for_level(shell_state, level=FOCUS_LEVEL_FILE)
    cts_gis_active_document_id = (
        "" if focus_file_key in {"", TOOL_ANCHOR_FILE_KEY} else _as_text(focus_file_key)
    ) or _as_text((resolved_tool_state.get("source") or {}).get("attention_document_id"))
    for document in cts_gis_sandbox_documents:
        summary = _summary_for_workbench_document(document)
        is_anchor = bool(summary.get("is_anchor"))
        if is_anchor and cts_gis_anchor_document is None:
            cts_gis_anchor_document = document
        if cts_gis_active_document_id and _workbench_document_matches(document, cts_gis_active_document_id):
            cts_gis_selected_document = document

    workbench = build_datum_file_workbench(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        sandbox_id="cts_gis",
        sandbox_label="CTS-GIS",
        anchor_document=cts_gis_anchor_document,
        selected_document=cts_gis_selected_document,
        sandbox_documents=cts_gis_sandbox_documents,
        title="CTS-GIS Datum Workbench",
        subtitle="Layered datum table for the active CTS-GIS sandbox file.",
        visible=show_workbench,
        extra_payload={"forced_visible": forced_visible},
    )
    cts_gis_aitas_state = dict(resolved_tool_state.get("aitas") or {})
    cts_gis_source_state = dict(resolved_tool_state.get("source") or {})
    cts_gis_selection_state = dict(resolved_tool_state.get("selection") or {})
    cts_gis_stage_payload = dict(stage_state_public.get("normalized_payload") or {})
    cts_gis_stage_validation = dict(stage_state_public.get("last_validation") or {})
    cts_gis_stage_preview = dict(stage_state_public.get("last_preview") or {})
    # Phase 4 follow-up — region render_key must reflect rendered output,
    # NOT the transient action that caused it. The previous key included
    # `action_result.action_kind` which guaranteed every action (even a
    # no-op) invalidated the panel and triggered a destructive
    # innerHTML repaint on the client. Replace with the actual selection
    # state delta (`selected_district_id` was previously missing).
    # `engaged_frame_id` is kept so engage_component_frame still flips
    # the key for the targeted frame.
    cts_gis_interface_panel_render_key = "|".join(
        [
            "cts_gis_interface_panel",
            _as_text(resolved_tool_state.get("selected_node_id")),
            "/".join(_as_text(item) for item in list(resolved_tool_state.get("active_path") or []) if _as_text(item)),
            _as_text(cts_gis_aitas_state.get("intention_rule_id")),
            _as_text(cts_gis_aitas_state.get("time_directive")),
            "overlay:1" if bool(cts_gis_source_state.get("precinct_district_overlay_enabled")) else "overlay:0",
            _as_text(cts_gis_source_state.get("attention_document_id")),
            _as_text(cts_gis_selection_state.get("selected_row_address")),
            _as_text(cts_gis_selection_state.get("selected_feature_id")),
            _as_text(cts_gis_selection_state.get("selected_district_id")),
            _as_text(cts_gis_selection_state.get("selected_precinct_id")),
            "stage:"
            + ":".join(
                [
                    _as_text(cts_gis_stage_payload.get("document_id")),
                    str(len(list(cts_gis_stage_payload.get("datums") or []))),
                    _as_text(cts_gis_stage_validation.get("expected_document_version_hash")),
                    str(len(list(cts_gis_stage_preview.get("proposed_inserted_rows") or []))),
                ]
            ),
            _as_text((action_result.get("details") or {}).get("engaged_frame_id")),
        ]
    )
    interface_panel = attach_region_family_contract(
        {
        "schema": PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
        "kind": "mediation_panel",
        "render_key": cts_gis_interface_panel_render_key,
        "title": "CTS-GIS",
        "summary": "CTS-GIS projects one mediation posture through structural navigation and correlated spatial evidence.",
        "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "sections": [
            {
                "title": "Readiness",
                "rows": [
                    {
                        "label": "state",
                        "value": _as_text((source_evidence_public.get("readiness") or {}).get("state")) or "pending",
                        "detail": _as_text((source_evidence_public.get("readiness") or {}).get("message")),
                    },
                    {
                        "label": "tool anchor",
                        "value": "yes" if (source_evidence_public.get("tool_anchor") or {}).get("exists") else "no",
                        "detail": _as_text((source_evidence_public.get("tool_anchor") or {}).get("file")),
                    },
                    {
                        "label": "registrar payload",
                        "value": "yes" if (source_evidence_public.get("registrar_payload") or {}).get("exists") else "no",
                        "detail": _as_text((source_evidence_public.get("registrar_payload") or {}).get("file")),
                    },
                ],
            }
        ],
        "surface_payload": surface_payload,
        "interface_body": interface_body,
        },
        family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    return {
        "entrypoint_id": entrypoint_id,
        "read_write_posture": read_write_posture,
        "page_title": "CTS-GIS",
        "page_subtitle": "Spatial mediation surface owned by SYSTEM.",
        "surface_payload": surface_payload,
        "control_panel": control_panel,
        "workbench": workbench,
        "interface_panel": interface_panel,
        "shell_state": shell_state,
        "route": CTS_GIS_TOOL_ROUTE,
    }


def _apply_cts_gis_action(
    *,
    portal_scope: PortalScope,
    tool_state: dict[str, Any],
    action_kind: str,
    action_payload: dict[str, Any],
    authority_db_file: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    next_tool_state = _tool_state_clone(tool_state)
    next_tool_state["staged_insert"] = _staged_insert_state(next_tool_state.get("staged_insert"))
    sql_store = _datum_store_for_authority_db(authority_db_file)
    mutation_service = CtsGisMutationService(sql_store)
    contract_state = _cts_gis_contract_state(
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
    )
    tenant_id = portal_scope.scope_id
    force_live_read = False

    try:
        if action_kind == "inject_directive":
            # Delegate all parsing and verb normalization to the canonical NIMM parser.
            # Frame engagement routing comes from NIMM_VERB_FRAME_ENGAGEMENT so rules
            # are not duplicated here.
            directive_text = _as_text(action_payload.get("directive_text")).strip()
            try:
                parsed = parse_directive_text(directive_text)
            except ValueError as exc:
                action_result = _cts_gis_action_result(
                    action_kind=action_kind,
                    status="rejected",
                    message=str(exc),
                    details={"directive_text": directive_text},
                )
                return next_tool_state, action_result, force_live_read
            engaged_frame_id = NIMM_VERB_FRAME_ENGAGEMENT.get(parsed["verb"], "")
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message=f"Directive injected: {directive_text}",
                details={
                    "directive_text": directive_text,
                    "verb": parsed["verb"],
                    "engaged_frame_id": engaged_frame_id,
                },
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "engage_component_frame":
            # Signal the requested frame for re-engagement via action_result (ephemeral
            # per request cycle — does NOT persist to tool_state). The interface body
            # builder reads engaged_frame_id from action_result.details and forces a
            # fresh render_key for that frame so the client registry sees a mismatch.
            # Sibling frames are unaffected.
            frame_id = _as_text(action_payload.get("frame_id"))
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message=f"Component frame engagement accepted: {frame_id}",
                details={"engaged_frame_id": frame_id},
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "select_district_row":
            # Garland cascade Phase 2: record a district-listing row selection
            # into tool_state.selection.selected_district_id so the next
            # mediation cycle can read it. The chosen identifier is the
            # district collection's `collection_id` (e.g. "23_present-district_31"),
            # NOT a SAMRAS datum row address — using a dedicated field keeps
            # the value out of `selected_row_address`, which the mediation
            # finalize step rewrites to a render-row address.
            #
            # Sibling selected_feature_id is cleared so a new district
            # selection doesn't carry a stale precinct highlight from the
            # prior district context.
            #
            # This handler does NOT itself materialise the district profile
            # frame — that happens downstream in
            # `_build_cts_gis_structured_interface_body` (Phase 3) when the
            # next shell load reads the recorded selected_district_id.
            # force_live_read stays False; the cached path keys on this
            # field too.
            district_id = _as_text(action_payload.get("row_address"))
            next_tool_state.setdefault("selection", {})
            next_tool_state["selection"]["selected_district_id"] = district_id
            # selected_row_explicit/selected_row_address are left untouched
            # so any SAMRAS row selection the user separately made stays.
            # Clear precinct selection — a new district selection invalidates it.
            next_tool_state["selection"]["selected_feature_id"] = ""
            next_tool_state["selection"]["selected_feature_explicit"] = False
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted" if district_id else "rejected",
                message=(
                    f"District row selected: {district_id}"
                    if district_id
                    else "select_district_row requires a row_address payload"
                ),
                details={"selected_district_id": district_id, "selected_row_address": district_id},
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "select_precinct_row":
            # Garland cascade Phase 4 follow-up: record a precinct-listing
            # row selection into a DEDICATED field
            # `tool_state.selection.selected_precinct_id`, NOT into
            # `selected_feature_id` (which mediation's finalize_selection
            # owns and overwrites with SAMRAS-derived ids) or
            # `selected_row_address` (which the mediation also rewrites).
            # The dedicated field survives mediation untouched and is
            # what the wireframe builder reads for the row's `selected`
            # flag + the region render_key.
            #
            # Accept both `precinct_id` (canonical) and `feature_id`
            # (Phase 2 compat) in the action payload.
            precinct_id = _as_text(action_payload.get("precinct_id")) or _as_text(
                action_payload.get("feature_id")
            )
            next_tool_state.setdefault("selection", {})
            next_tool_state["selection"]["selected_precinct_id"] = precinct_id
            # Do NOT touch selected_feature_id / selected_row_address —
            # those are mediation-owned. Geospatial highlighting of the
            # selected precinct (once precinct polygons exist) will be
            # done by mapping precinct_id -> feature_id in the wireframe
            # builder, not by overloading the mediation fields.
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted" if precinct_id else "rejected",
                message=(
                    f"Precinct selected: {precinct_id}"
                    if precinct_id
                    else "select_precinct_row requires a precinct_id (or feature_id) payload"
                ),
                details={"selected_precinct_id": precinct_id},
            )
            return next_tool_state, action_result, force_live_read

        if action_kind in {"rename_document", "delete_document"}:
            result = run_document_workbench_action(
                action_kind,
                action_payload,
                authority_db_file=authority_db_file,
                portal_instance_id=portal_scope.scope_id,
            )
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted" if result.get("ok") else "rejected",
                message=result.get("error", {}).get("message", action_kind) if not result.get("ok") else action_kind,
                details=dict(result),
            )
            return next_tool_state, action_result, True  # force_live_read refreshes workbench catalog

        if action_kind == "toggle_overlay":
            next_tool_state.setdefault("source", {})
            requested_enabled = action_payload.get("enabled")
            overlay_enabled = (
                bool(requested_enabled)
                if isinstance(requested_enabled, bool)
                else not bool(next_tool_state.get("source", {}).get("precinct_district_overlay_enabled"))
            )
            next_tool_state["source"]["precinct_district_overlay_enabled"] = overlay_enabled
            _clear_selection_state(next_tool_state)
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message=(
                    "CTS-GIS compiled precinct overlay enabled."
                    if overlay_enabled
                    else "CTS-GIS compiled precinct overlay disabled."
                ),
                details={"precinct_district_overlay_enabled": overlay_enabled},
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "stage_insert_yaml":
            stage_document, stage_meta = mutation_service.parse_stage_input(action_payload)
            selected_document_id = _as_text(next_tool_state.get("source", {}).get("attention_document_id"))
            selected_document_name = _document_name_for_id(
                datum_store=sql_store,
                tenant_id=tenant_id,
                document_id=selected_document_id,
            )
            stage_state, warnings = mutation_service.build_stage_state(
                stage_document=stage_document,
                draft_text=_as_text(stage_meta.get("draft_text")),
                draft_format=_as_text(stage_meta.get("draft_format")) or "yaml",
                placeholder_title_requested=bool(stage_meta.get("placeholder_title_requested")),
                selected_document_id=selected_document_id,
                selected_document_name=selected_document_name,
            )
            next_tool_state["staged_insert"] = stage_state
            if isinstance(action_payload.get("structure_operation"), dict):
                next_tool_state["staged_insert"]["structure_operation"] = dict(action_payload.get("structure_operation") or {})
            next_tool_state["staged_insert"]["compiled_nimm_envelope"] = _compile_staged_nimm_envelope(next_tool_state)
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message="CTS-GIS staged insert payload captured.",
                details={
                    "schema": CTS_GIS_STAGE_INSERT_SCHEMA,
                    "document_id": _as_text(stage_state.get("normalized_payload", {}).get("document_id")),
                    "document_name": _as_text(stage_state.get("normalized_payload", {}).get("document_name")),
                    "datum_count": len(list(stage_state.get("normalized_payload", {}).get("datums") or [])),
                    "compiled_nimm": bool(next_tool_state["staged_insert"].get("compiled_nimm_envelope")),
                },
                warnings=warnings,
            )
            _append_sql_audit(
                authority_db_file=authority_db_file,
                event_type="portal.cts_gis.stage_insert_yaml.accepted",
                focus_subject=_cts_gis_audit_focus_subject(next_tool_state),
                shell_verb="portal.cts_gis.stage_insert_yaml",
                details=dict(action_result.get("details") or {}),
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "validate_stage":
            validation = mutation_service.validate_stage(
                tenant_id=tenant_id,
                tool_state=next_tool_state,
                contract_state=contract_state,
            )
            public_validation = _public_stage_validation(validation)
            next_tool_state["staged_insert"]["last_validation"] = public_validation
            next_tool_state["staged_insert"]["compiled_nimm_envelope"] = _compile_staged_nimm_envelope(next_tool_state)
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message="CTS-GIS staged insert payload validated.",
                details=public_validation,
                warnings=list(public_validation.get("warnings") or []),
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "preview_apply":
            validation = mutation_service.validate_stage(
                tenant_id=tenant_id,
                tool_state=next_tool_state,
                contract_state=contract_state,
            )
            public_validation = _public_stage_validation(validation)
            next_tool_state["staged_insert"]["last_validation"] = public_validation
            preview = mutation_service.preview_stage(
                tenant_id=tenant_id,
                tool_state=next_tool_state,
                contract_state=contract_state,
            )
            public_preview = _public_stage_preview(preview)
            next_tool_state["staged_insert"]["last_preview"] = public_preview
            next_tool_state["staged_insert"]["compiled_nimm_envelope"] = _compile_staged_nimm_envelope(next_tool_state)
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message="CTS-GIS staged insert preview is ready.",
                details=public_preview,
                warnings=list(public_preview.get("warnings") or []),
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "apply_stage":
            validation = mutation_service.validate_stage(
                tenant_id=tenant_id,
                tool_state=next_tool_state,
                contract_state=contract_state,
            )
            applied = mutation_service.apply_stage(
                tenant_id=tenant_id,
                tool_state=next_tool_state,
                contract_state=contract_state,
            )
            public_validation = _public_stage_validation(validation)
            public_preview = _public_stage_preview(applied)
            next_tool_state["staged_insert"] = _staged_insert_state({})
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message="CTS-GIS staged insert plan applied transactionally.",
                details={
                    **public_preview,
                    "persisted_version_hash": _as_text(applied.get("persisted_version_hash")),
                    "last_validation": public_validation,
                },
                warnings=list(public_preview.get("warnings") or []),
            )
            force_live_read = True
            CtsGisReadOnlyService.evict_document_projection_cache()
            _append_sql_audit(
                authority_db_file=authority_db_file,
                event_type="portal.cts_gis.apply_stage.accepted",
                focus_subject=_cts_gis_audit_focus_subject(tool_state),
                shell_verb="portal.cts_gis.apply_stage",
                details=dict(action_result.get("details") or {}),
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "discard_stage":
            discarded_payload = dict(next_tool_state.get("staged_insert", {}).get("normalized_payload") or {})
            next_tool_state["staged_insert"] = _staged_insert_state({})
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message="CTS-GIS staged insert payload discarded.",
                details={
                    "document_id": _as_text(discarded_payload.get("document_id")),
                    "document_name": _as_text(discarded_payload.get("document_name")),
                    "datum_count": len(list(discarded_payload.get("datums") or [])),
                },
            )
            _append_sql_audit(
                authority_db_file=authority_db_file,
                event_type="portal.cts_gis.discard_stage.accepted",
                focus_subject=_cts_gis_audit_focus_subject(tool_state),
                shell_verb="portal.cts_gis.discard_stage",
                details=dict(action_result.get("details") or {}),
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "soundness_check":
            report = mutation_service.soundness_check(tenant_id=tenant_id)
            next_tool_state["staged_insert"]["soundness_report"] = report
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted" if report.get("ok") else "warning",
                message="MOS soundness check complete." if report.get("ok") else "MOS soundness check found issues.",
                details=report,
            )
            return next_tool_state, action_result, False

        if action_kind == "expand_structure":
            structure_operation = dict(action_payload.get("structure_operation") or {})
            if not structure_operation:
                raise CtsGisMutationError(
                    "structure_operation_required",
                    "expand_structure requires action_payload.structure_operation with the expansion parameters.",
                )
            next_tool_state["staged_insert"]["structure_operation"] = structure_operation
            next_tool_state["staged_insert"]["compiled_nimm_envelope"] = _compile_staged_nimm_envelope(next_tool_state)
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message="CTS-GIS structure expansion operation staged in compound directive.",
                details={
                    "structure_operation": structure_operation,
                    "compiled_nimm": bool(next_tool_state["staged_insert"].get("compiled_nimm_envelope")),
                },
            )
            return next_tool_state, action_result, force_live_read

        if action_kind in ("insert_datum", "reorder_datum"):
            stage_document, stage_meta = mutation_service.parse_stage_input(action_payload)
            selected_document_id = _as_text(next_tool_state.get("source", {}).get("attention_document_id"))
            selected_document_name = _document_name_for_id(
                datum_store=sql_store,
                tenant_id=tenant_id,
                document_id=selected_document_id,
            )
            stage_state, warnings = mutation_service.build_stage_state(
                stage_document=stage_document,
                draft_text=_as_text(stage_meta.get("draft_text")),
                draft_format=_as_text(stage_meta.get("draft_format")) or "json",
                placeholder_title_requested=bool(stage_meta.get("placeholder_title_requested")),
                selected_document_id=selected_document_id,
                selected_document_name=selected_document_name,
            )
            next_tool_state["staged_insert"] = stage_state
            if action_kind == "reorder_datum":
                next_tool_state["staged_insert"]["structure_operation"] = {
                    "kind": "reorder_datum",
                    **(dict(action_payload.get("structure_operation") or {})),
                }
            elif isinstance(action_payload.get("structure_operation"), dict):
                next_tool_state["staged_insert"]["structure_operation"] = dict(action_payload["structure_operation"])
            next_tool_state["staged_insert"]["compiled_nimm_envelope"] = _compile_staged_nimm_envelope(next_tool_state)
            if action_payload.get("auto_validate"):
                try:
                    validation = mutation_service.validate_stage(
                        tenant_id=tenant_id,
                        tool_state=next_tool_state,
                        contract_state=contract_state,
                    )
                    next_tool_state["staged_insert"]["last_validation"] = _public_stage_validation(validation)
                    next_tool_state["staged_insert"]["compiled_nimm_envelope"] = _compile_staged_nimm_envelope(next_tool_state)
                    warnings = list({*warnings, *list(next_tool_state["staged_insert"]["last_validation"].get("warnings") or [])})
                except CtsGisMutationError:
                    pass
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message=f"CTS-GIS {action_kind} directive staged.",
                details={
                    "schema": CTS_GIS_STAGE_INSERT_SCHEMA,
                    "document_id": _as_text(stage_state.get("normalized_payload", {}).get("document_id")),
                    "document_name": _as_text(stage_state.get("normalized_payload", {}).get("document_name")),
                    "datum_count": len(list(stage_state.get("normalized_payload", {}).get("datums") or [])),
                    "compiled_nimm": bool(next_tool_state["staged_insert"].get("compiled_nimm_envelope")),
                },
                warnings=warnings,
            )
            return next_tool_state, action_result, force_live_read

        if action_kind == "validate_manipulation_stage":
            stage_text = _as_text(action_payload.get("stage_text"))
            if not stage_text and isinstance(action_payload.get("stage_document"), dict):
                import json as _json
                stage_text = _json.dumps(action_payload["stage_document"])
            if not stage_text:
                raise CtsGisMutationError(
                    "stage_text_required",
                    "validate_manipulation_stage requires action_payload.stage_text or action_payload.stage_document.",
                )
            validated_stage, warnings = mutation_service.validate_manipulation_stage(stage_text)
            action_result = _cts_gis_action_result(
                action_kind=action_kind,
                status="accepted",
                message="CTS-GIS manipulation stage validated against contract schema.",
                details={
                    "schema": CTS_GIS_MANIPULATION_STAGE_SCHEMA,
                    "proposed_operation": _as_text(validated_stage.get("proposed_operation")),
                    "target_document": _as_text(validated_stage.get("target_document")),
                    "attention": _as_text(validated_stage.get("attention")),
                    "structure_valid": bool(validated_stage.get("structure_valid")),
                    "structure_decode_confirmed": bool(validated_stage.get("structure_decode_confirmed")),
                },
                warnings=warnings,
            )
            return next_tool_state, action_result, force_live_read

    except CtsGisMutationError as exc:
        if action_kind == "apply_stage":
            next_tool_state["staged_insert"]["last_error"] = {
                "code": exc.code,
                "message": str(exc),
                "details": exc.details or {},
            }
            _append_sql_audit(
                authority_db_file=authority_db_file,
                event_type="portal.cts_gis.apply_stage.failed",
                focus_subject=_cts_gis_audit_focus_subject(tool_state),
                shell_verb="portal.cts_gis.apply_stage",
                details={"code": exc.code, "message": str(exc)},
            )
        return (
            next_tool_state,
            _cts_gis_action_result(
                action_kind=action_kind,
                status="error",
                code=exc.code,
                message=str(exc),
                details=exc.details,
            ),
            False,
        )
    except ValueError as exc:
        return (
            next_tool_state,
            _cts_gis_action_result(
                action_kind=action_kind,
                status="error",
                code="action_failed",
                message=str(exc),
            ),
            False,
        )

    return (
        next_tool_state,
        _cts_gis_action_result(
            action_kind=action_kind,
            status="error",
            code="action_unhandled",
            message=f"CTS-GIS action {action_kind} is not implemented.",
        ),
        False,
    )


def run_portal_cts_gis(
    request_payload: dict[str, Any] | None,
    *,
    data_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    portal_instance_id: str | None = None,
    portal_domain: str = "",
) -> dict[str, Any]:
    portal_scope, shell_state, normalized_payload, _ = _normalize_request(request_payload)
    resolved_portal_instance_id = _as_text(portal_instance_id) or portal_scope.scope_id
    if not portal_scope.scope_id:
        portal_scope = PortalScope(scope_id=resolved_portal_instance_id, capabilities=portal_scope.capabilities)
    shell_request = dict(normalized_payload)
    shell_request["schema"] = PORTAL_SHELL_REQUEST_SCHEMA
    shell_request["requested_surface_id"] = CTS_GIS_TOOL_SURFACE_ID
    shell_request["portal_scope"] = portal_scope.to_dict()
    shell_request["shell_state"] = shell_state.to_dict()
    shell_request["cts_gis_entrypoint_id"] = CTS_GIS_TOOL_ENTRYPOINT_ID
    shell_request["cts_gis_read_write_posture"] = "read-only"
    shell_request.pop("surface_query", None)
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=resolved_portal_instance_id,
        portal_domain=portal_domain,
        data_dir=data_dir,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
        authority_db_file=authority_db_file,
    )


def run_portal_cts_gis_action(
    request_payload: dict[str, Any] | None,
    *,
    data_dir: str | Path | None,
    authority_db_file: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    portal_instance_id: str | None = None,
    portal_domain: str = "",
) -> dict[str, Any]:
    portal_scope, shell_state, normalized_payload, tool_state, action_kind, action_payload = _normalize_action_request(
        request_payload
    )
    resolved_portal_instance_id = _as_text(portal_instance_id) or portal_scope.scope_id
    if not portal_scope.scope_id:
        portal_scope = PortalScope(scope_id=resolved_portal_instance_id, capabilities=portal_scope.capabilities)
    next_tool_state, action_result, force_live_read = _apply_cts_gis_action(
        portal_scope=portal_scope,
        tool_state=tool_state,
        action_kind=action_kind,
        action_payload=action_payload,
        authority_db_file=authority_db_file,
        tool_exposure_policy=tool_exposure_policy,
    )
    shell_request = build_portal_shell_request_payload(
        portal_scope=portal_scope,
        shell_state=shell_state,
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    shell_request["tool_state"] = next_tool_state
    shell_request["cts_gis_action_result"] = action_result
    shell_request["cts_gis_entrypoint_id"] = CTS_GIS_TOOL_ACTION_ENTRYPOINT_ID
    shell_request["cts_gis_read_write_posture"] = "write"
    shell_request["force_live_read"] = force_live_read
    shell_request["runtime_mode"] = _as_text(normalized_payload.get("runtime_mode")) or _CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=resolved_portal_instance_id,
        portal_domain=portal_domain,
        data_dir=data_dir,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
        authority_db_file=authority_db_file,
    )


__all__ = [
    "CTS_GIS_ACTION_RESULT_SCHEMA",
    "CTS_GIS_TOOL_ACTION_ENTRYPOINT_ID",
    "CTS_GIS_TOOL_ACTION_ROUTE",
    "LegacyMapsAliasUnsupportedError",
    "build_portal_cts_gis_surface_bundle",
    "run_portal_cts_gis",
    "run_portal_cts_gis_action",
]
