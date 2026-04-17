from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_tool_control_panel
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    CTS_GIS_TOOL_REQUEST_SCHEMA,
    CTS_GIS_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.cts_gis import CtsGisReadOnlyService
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_ENTRYPOINT_ID,
    CTS_GIS_TOOL_ROUTE,
    CTS_GIS_TOOL_SURFACE_ID,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    PortalShellState,
    build_canonical_url,
    build_portal_shell_request_payload,
    canonical_query_for_shell_state,
    canonicalize_portal_shell_state,
    resolve_portal_tool_registry_entry,
)

_DEFAULT_ATTENTION_NODE_ID = "3-2-3-17-77"
_DEFAULT_INTENTION_RULE_ID = "descendants_depth_1_or_2"
_DEFAULT_TIME_DIRECTIVE = ""
_DEFAULT_ARCHETYPE_FAMILY_ID = "samras_nominal"
_DEFAULT_NIMM_DIRECTIVE = "mediate"
_DEFAULT_SUPPORTING_DOCUMENT_NAME = "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"
_CANONICAL_TOOL_PUBLIC_ID = "cts_gis"
_CANONICAL_TOOL_SLUG = "cts-gis"
_CANONICAL_TOOL_ANCHOR_PATTERN = "tool.*.cts-gis.json"
_LEGACY_DOCUMENT_PREFIX = "sandbox:" + ("map" + "s") + ":"
_SERVICE_SELF_TOKEN = "0"
_SERVICE_CHILDREN_TOKEN = "1-0"
_SERVICE_BRANCH_PREFIX = "branch:"
_CTS_GIS_NAV_MODE_ORDERED = "ordered_hierarchy"
_CTS_GIS_NAV_MODE_LEGACY = "legacy_branch_canvas"
_CTS_GIS_WIRING_STAGE_SYNTHETIC = "synthetic_baseline"
_CTS_GIS_WIRING_STAGE_GARLAND = "real_garland_geometry"
_CTS_GIS_WIRING_STAGE_HIERARCHY = "real_ordered_hierarchy"


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


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_or_none(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def _safe_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tool_state_clone(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "nimm_directive": _as_text(payload.get("nimm_directive")),
        "aitas": dict(payload.get("aitas") or {}),
        "source": dict(payload.get("source") or {}),
        "selection": dict(payload.get("selection") or {}),
    }


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


def _canonical_intention_rule_id(value: object) -> str:
    token = _as_text(value)
    if token in {"", _DEFAULT_INTENTION_RULE_ID}:
        return _DEFAULT_INTENTION_RULE_ID
    if token in {_SERVICE_SELF_TOKEN, "self"}:
        return "self"
    if token in {_SERVICE_CHILDREN_TOKEN, "children"}:
        return "children"
    return token


def _service_intention_token(rule_id: object) -> str:
    token = _canonical_intention_rule_id(rule_id)
    if token == "self":
        return _SERVICE_SELF_TOKEN
    if token == "children":
        return _SERVICE_CHILDREN_TOKEN
    return token or _DEFAULT_INTENTION_RULE_ID


def _normalize_tool_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    raw_tool_state = normalized_payload.get("tool_state") if isinstance(normalized_payload.get("tool_state"), dict) else {}
    raw_aitas = raw_tool_state.get("aitas") if isinstance(raw_tool_state.get("aitas"), dict) else {}
    raw_source = raw_tool_state.get("source") if isinstance(raw_tool_state.get("source"), dict) else {}
    raw_selection = raw_tool_state.get("selection") if isinstance(raw_tool_state.get("selection"), dict) else {}
    mediation_state = (
        normalized_payload.get("mediation_state") if isinstance(normalized_payload.get("mediation_state"), dict) else {}
    )
    return {
        "nimm_directive": _as_text(raw_tool_state.get("nimm_directive") or normalized_payload.get("nimm_directive"))
        or _DEFAULT_NIMM_DIRECTIVE,
        "aitas": {
            "attention_node_id": _as_text(
                raw_aitas.get("attention_node_id")
                or mediation_state.get("attention_node_id")
                or normalized_payload.get("attention_node_id")
            )
            or _DEFAULT_ATTENTION_NODE_ID,
            "intention_rule_id": _canonical_intention_rule_id(
                raw_aitas.get("intention_rule_id")
                or mediation_state.get("intention_token")
                or normalized_payload.get("intention_token")
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
        },
        "selection": {
            "selected_row_address": _as_text(
                raw_selection.get("selected_row_address") or normalized_payload.get("selected_row_address")
            ),
            "selected_feature_id": _as_text(
                raw_selection.get("selected_feature_id") or normalized_payload.get("selected_feature_id")
            ),
        },
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


def _normalize_request(
    payload: dict[str, Any] | None,
) -> tuple[PortalScope, PortalShellState, dict[str, Any], dict[str, Any]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    if normalized_payload.get("schema") in {None, ""}:
        normalized_payload = {"schema": CTS_GIS_TOOL_REQUEST_SCHEMA, **normalized_payload}
    if _as_text(normalized_payload.get("schema")) != CTS_GIS_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {CTS_GIS_TOOL_REQUEST_SCHEMA}")
    _assert_no_legacy_maps_aliases(normalized_payload)
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    shell_state = canonicalize_portal_shell_state(
        normalized_payload.get("shell_state"),
        active_surface_id=CTS_GIS_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        seed_anchor_file=normalized_payload.get("shell_state") is None,
    )
    return portal_scope, shell_state, normalized_payload, _normalize_tool_state(normalized_payload)


def _datum_summary(data_dir: str | Path | None, *, portal_instance_id: str) -> dict[str, Any]:
    if data_dir is None:
        return {
            "configured": False,
            "document_count": 0,
            "source_files": [],
            "warnings": ["data_dir_missing"],
        }
    try:
        datum_store = FilesystemSystemDatumStoreAdapter(Path(data_dir))
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


def _cts_gis_private_tool_root(private_dir: str | Path | None) -> Path | None:
    root = _path_or_none(private_dir)
    if root is None:
        return None
    candidate = root / "utilities" / "tools" / _CANONICAL_TOOL_SLUG
    if candidate.exists() and candidate.is_dir():
        return candidate
    return candidate


def _cts_gis_data_tool_root(data_dir: str | Path | None) -> Path | None:
    root = _path_or_none(data_dir)
    if root is None:
        return None
    candidate = root / "sandbox" / _CANONICAL_TOOL_SLUG
    if candidate.exists() and candidate.is_dir():
        return candidate
    return candidate


def _split_row_source(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("datum_addressing_abstraction_space"), dict):
        return dict(payload.get("datum_addressing_abstraction_space") or {})
    return dict(payload)


def _cts_gis_tool_anchor_path(data_dir: str | Path | None) -> Path | None:
    tool_root = _cts_gis_data_tool_root(data_dir)
    if tool_root is None:
        return None
    patterns = (_CANONICAL_TOOL_ANCHOR_PATTERN,)
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(sorted(tool_root.glob(pattern)))
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[0] if deduped else None


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
    for marker in (".msn-", ".fnd.", ".registrar"):
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


def _build_source_evidence(
    *,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    service_surface: dict[str, Any],
) -> dict[str, Any]:
    selected_document = dict(service_surface.get("selected_document") or {})
    supporting_document = _supporting_document_summary(service_surface)
    supporting_document_name = _as_text(supporting_document.get("document_name")) or _DEFAULT_SUPPORTING_DOCUMENT_NAME
    corpus_prefix = _cts_gis_corpus_prefix(supporting_document_name)
    private_tool_root = _cts_gis_private_tool_root(private_dir)
    data_tool_root = _cts_gis_data_tool_root(data_dir)
    spec_path = None if private_tool_root is None else private_tool_root / "spec.json"
    tool_anchor_path = _cts_gis_tool_anchor_path(data_dir)
    tool_anchor_payload = _safe_json_object(tool_anchor_path)
    member_files = _anchor_member_files(tool_anchor_payload)
    source_path = None if data_tool_root is None else data_tool_root / "sources" / supporting_document_name
    payload_cache_root = None if data_dir is None else Path(data_dir) / "payloads" / "cache"
    registrar_path = None if payload_cache_root is None or not corpus_prefix else payload_cache_root / f"{corpus_prefix}.registrar.json"
    administrative_cache_path = (
        None if payload_cache_root is None or not corpus_prefix else payload_cache_root / f"{corpus_prefix}.msn-administrative.json"
    )

    tool_spec = _evidence_path_payload(spec_path, canonical_tool_id=_CANONICAL_TOOL_PUBLIC_ID)
    tool_anchor = _evidence_path_payload(tool_anchor_path)
    tool_anchor["member_files"] = member_files
    administrative_source = _evidence_path_payload(source_path)
    administrative_source["document_id"] = _as_text(supporting_document.get("document_id"))
    administrative_source["document_name"] = supporting_document_name
    registrar_payload = _evidence_path_payload(registrar_path)
    if registrar_payload["payload"]:
        registrar_payload["payload_id"] = _as_text(registrar_payload["payload"].get("payload_id"))
        registrar_payload["target_mss_anchor_datum"] = _as_text(registrar_payload["payload"].get("target_mss_anchor_datum"))
    administrative_payload_cache = _evidence_path_payload(administrative_cache_path)
    if administrative_payload_cache["payload"]:
        administrative_payload_cache["payload_id"] = _as_text(administrative_payload_cache["payload"].get("payload_id"))

    samras_seed_status = _as_text(selected_document.get("samras_seed_status"))
    readiness_state = "ready"
    readiness_message = "CTS-GIS evidence is ready."
    if _as_text((service_surface.get("map_projection") or {}).get("projection_state")) == "no_authoritative_cts_gis_documents":
        readiness_state = "no_authoritative_cts_gis_documents"
        readiness_message = "No authoritative CTS-GIS source document is available for the active tenant."
    elif not tool_anchor["exists"] or not registrar_payload["exists"] or samras_seed_status not in {"", "ready"}:
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
        "payload_corpus": {
            "corpus_prefix": corpus_prefix,
            "member_file_count": len(member_files),
        },
        "warnings": [],
        "readiness": {
            "state": readiness_state,
            "message": readiness_message,
            "samras_seed_status": samras_seed_status or ("ready" if readiness_state == "ready" else "missing"),
        },
    }


def _resolved_tool_state(
    requested_tool_state: dict[str, Any],
    service_surface: dict[str, Any],
) -> dict[str, Any]:
    mediation_state = dict(service_surface.get("mediation_state") or {})
    diagnostic_summary = dict(service_surface.get("diagnostic_summary") or {})
    return {
        "nimm_directive": _as_text(requested_tool_state.get("nimm_directive")) or _DEFAULT_NIMM_DIRECTIVE,
        "aitas": {
            "attention_node_id": _as_text(mediation_state.get("attention_node_id"))
            or _as_text(requested_tool_state.get("aitas", {}).get("attention_node_id"))
            or _DEFAULT_ATTENTION_NODE_ID,
            "intention_rule_id": _canonical_intention_rule_id(
                mediation_state.get("intention_token")
                or requested_tool_state.get("aitas", {}).get("intention_rule_id")
            ),
            "time_directive": _as_text(requested_tool_state.get("aitas", {}).get("time_directive")) or _DEFAULT_TIME_DIRECTIVE,
            "archetype_family_id": _as_text(requested_tool_state.get("aitas", {}).get("archetype_family_id"))
            or _DEFAULT_ARCHETYPE_FAMILY_ID,
        },
        "source": {
            "attention_document_id": _as_text(
                mediation_state.get("attention_document_id")
                or _as_text((service_surface.get("selected_document") or {}).get("document_id"))
                or requested_tool_state.get("source", {}).get("attention_document_id")
            ),
        },
        "selection": {
            "selected_row_address": _as_text(diagnostic_summary.get("selected_row_address"))
            or _as_text(requested_tool_state.get("selection", {}).get("selected_row_address")),
            "selected_feature_id": _as_text(diagnostic_summary.get("selected_feature_id"))
            or _as_text(requested_tool_state.get("selection", {}).get("selected_feature_id")),
        },
    }


def _tool_state_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
) -> dict[str, Any]:
    request_body = build_portal_shell_request_payload(
        portal_scope=portal_scope,
        shell_state=shell_state,
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
    )
    request_body["tool_state"] = _tool_state_clone(tool_state)
    return request_body


def _node_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    attention_node_id: str,
    intention_rule_id: str = _DEFAULT_INTENTION_RULE_ID,
    selected_row_address: str = "",
    selected_feature_id: str = "",
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["aitas"]["attention_node_id"] = _as_text(attention_node_id)
    next_state["aitas"]["intention_rule_id"] = _canonical_intention_rule_id(intention_rule_id)
    next_state["selection"]["selected_row_address"] = _as_text(selected_row_address)
    next_state["selection"]["selected_feature_id"] = _as_text(selected_feature_id)
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _intention_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    intention_rule_id: str,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["aitas"]["intention_rule_id"] = _canonical_intention_rule_id(intention_rule_id)
    next_state["selection"]["selected_row_address"] = ""
    next_state["selection"]["selected_feature_id"] = ""
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _document_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    attention_document_id: str,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["source"]["attention_document_id"] = _as_text(attention_document_id)
    next_state["selection"]["selected_row_address"] = ""
    next_state["selection"]["selected_feature_id"] = ""
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _selection_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    selected_row_address: str,
    selected_feature_id: str,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["selection"]["selected_row_address"] = _as_text(selected_row_address)
    next_state["selection"]["selected_feature_id"] = _as_text(selected_feature_id)
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _context_items_from_base_panel(base_panel: dict[str, Any], source_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    items = list(base_panel.get("context_items") or [])
    tool_anchor_file = _as_text((source_evidence.get("tool_anchor") or {}).get("file"))
    if tool_anchor_file and len(items) >= 2:
        items[1] = {"label": "File", "value": tool_anchor_file}
    return items


def _cts_gis_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    tool_rows: list[dict[str, Any]],
    resolved_tool_state: dict[str, Any],
    source_evidence: dict[str, Any],
    service_surface: dict[str, Any],
) -> dict[str, Any]:
    base_panel = build_tool_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=data_dir,
        public_dir=None,
        private_dir=private_dir,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        active_document=None,
        selected_datum=None,
        selected_object=None,
        tool_rows=list(tool_rows or []),
        title="CTS-GIS",
    )
    attention_profile = dict(service_surface.get("attention_profile") or {})
    directive_entries = [
        {"label": "NIMM directive", "meta": _as_text(resolved_tool_state["nimm_directive"]), "active": True},
        {"label": "Tool posture", "meta": "interface-panel-led"},
    ]
    aitas_entries = [
        {
            "label": "Attention",
            "meta": _as_text(attention_profile.get("profile_label")) or _as_text(resolved_tool_state["aitas"]["attention_node_id"]),
            "prefix": _as_text(resolved_tool_state["aitas"]["attention_node_id"]),
            "active": True,
        },
        {
            "label": "Intention",
            "meta": _as_text(resolved_tool_state["aitas"]["intention_rule_id"]) or _DEFAULT_INTENTION_RULE_ID,
            "active": True,
        },
        {
            "label": "Time",
            "meta": _as_text(resolved_tool_state["aitas"]["time_directive"]) or "inactive",
        },
        {
            "label": "Archetype",
            "meta": _as_text(resolved_tool_state["aitas"]["archetype_family_id"]) or _DEFAULT_ARCHETYPE_FAMILY_ID,
        },
    ]
    attention_entries = [
        {
            "label": _as_text(item.get("profile_label")) or _as_text(item.get("node_id")),
            "prefix": _as_text(item.get("node_id")),
            "meta": "lineage" if item in list(service_surface.get("lineage") or []) else "renderable node",
            "active": bool(item.get("selected")),
            "shell_request": _node_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                attention_node_id=_as_text(item.get("node_id")),
            ),
        }
        for item in (list(service_surface.get("lineage") or []) + list(service_surface.get("render_profiles") or []))
        if _as_text(item.get("node_id"))
    ]
    intention_entries = [
        {
            "label": _as_text(option.get("label")) or _as_text(option.get("token")) or "Rule",
            "prefix": _as_text(option.get("token")),
            "meta": f"{int(option.get('profile_count') or 0)} profiles · {int(option.get('feature_count') or 0)} features",
            "active": bool(option.get("active")),
            "shell_request": _intention_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                intention_rule_id=_as_text(option.get("token")),
            ),
        }
        for option in list((service_surface.get("mediation_state") or {}).get("available_intentions") or [])
    ]
    source_entries = [
        {
            "label": "Tool spec",
            "prefix": _as_text((source_evidence.get("tool_spec") or {}).get("file")) or "spec.json",
            "meta": "tool-owned governance file",
            "active": True,
        },
        {
            "label": "Tool anchor",
            "prefix": _as_text((source_evidence.get("tool_anchor") or {}).get("file")) or "tool.<msn>.cts-gis.json",
            "meta": "tool-owned data anchor",
            "active": True,
        },
        {
            "label": "Registrar payload",
            "prefix": _as_text((source_evidence.get("registrar_payload") or {}).get("file")) or "registrar.json",
            "meta": _as_text((source_evidence.get("readiness") or {}).get("state")),
            "active": bool((source_evidence.get("registrar_payload") or {}).get("exists")),
        },
    ]
    for document in list(service_surface.get("document_catalog") or []):
        document_id = _as_text(document.get("document_id"))
        source_entries.append(
            {
                "label": _as_text(document.get("document_name")) or document_id or "document",
                "prefix": _as_text(document.get("default_attention_node_id")),
                "meta": _as_text(document.get("projection_state")) or "pending",
                "active": bool(document.get("selected")),
                "shell_request": _document_shell_request(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    tool_state=resolved_tool_state,
                    attention_document_id=document_id,
                ),
            }
        )
    return {
        **base_panel,
        "context_items": _context_items_from_base_panel(base_panel, source_evidence),
        "groups": [
            {"title": "Directive", "entries": directive_entries},
            {"title": "AITAS", "entries": aitas_entries},
            {"title": "Attention", "entries": attention_entries},
            {"title": "Projection Rules", "entries": intention_entries},
            {"title": "Source Evidence", "entries": source_entries},
        ],
        "actions": [],
    }


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


def _geometry_points(geometry: dict[str, Any]) -> list[list[float]]:
    geometry_type = _as_text(geometry.get("type"))
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        return [[float(coordinates[0]), float(coordinates[1])]]
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        points: list[list[float]] = []
        for ring in coordinates:
            if not isinstance(ring, list):
                continue
            for point in ring:
                if isinstance(point, list) and len(point) >= 2:
                    points.append([float(point[0]), float(point[1])])
        return points
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        points = []
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            for ring in polygon:
                if not isinstance(ring, list):
                    continue
                for point in ring:
                    if isinstance(point, list) and len(point) >= 2:
                        points.append([float(point[0]), float(point[1])])
        return points
    return []


def _bounds_from_points(points: list[list[float]]) -> list[float]:
    if not points:
        return []
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _build_ordered_hierarchy_navigation(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    selected_node_id: str,
    node_titles: dict[str, str],
) -> dict[str, Any]:
    title_map = {_as_text(node_id): _as_text(title) for node_id, title in dict(node_titles or {}).items() if _looks_like_msn_node_id(node_id)}
    nodes: set[str] = set(title_map.keys())
    target_node_id = _as_text(selected_node_id) or _DEFAULT_ATTENTION_NODE_ID
    if _looks_like_msn_node_id(target_node_id):
        nodes.add(target_node_id)
    expanded_nodes: set[str] = set()
    for node_id in nodes:
        parts = [part for part in node_id.split("-") if part]
        for depth in range(1, len(parts) + 1):
            expanded_nodes.add("-".join(parts[:depth]))
    for node_id in expanded_nodes:
        title_map.setdefault(node_id, "")
    ordered_nodes = sorted(expanded_nodes, key=_node_sort_key)
    if not ordered_nodes:
        ordered_nodes = [_DEFAULT_ATTENTION_NODE_ID]
        title_map.setdefault(_DEFAULT_ATTENTION_NODE_ID, "")
        target_node_id = _DEFAULT_ATTENTION_NODE_ID
    if target_node_id not in ordered_nodes:
        target_node_id = ordered_nodes[0]

    children_by_parent: dict[str, list[str]] = {}
    for node_id in ordered_nodes:
        parent = _parent_node_id(node_id)
        children_by_parent.setdefault(parent, []).append(node_id)
    for node_ids in children_by_parent.values():
        node_ids.sort(key=_node_sort_key)

    active_path_node_ids = [
        "-".join(target_node_id.split("-")[:depth])
        for depth in range(1, _node_depth(target_node_id) + 1)
    ]
    active_path_set = set(active_path_node_ids)

    def _entry_payload(node_id: str) -> dict[str, Any]:
        title = _as_text(title_map.get(node_id))
        child_count = len(children_by_parent.get(node_id, []))
        return {
            "node_id": node_id,
            "msn_id": node_id,
            "title": title,
            "label": title or node_id,
            "detail": f"{child_count} children",
            "depth": _node_depth(node_id),
            "parent_node_id": _parent_node_id(node_id),
            "child_count": child_count,
            "selected": node_id == target_node_id,
            "in_active_path": node_id in active_path_set,
            "shell_request": _node_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                attention_node_id=node_id,
            ),
        }

    active_path_entries = [_entry_payload(node_id) for node_id in active_path_node_ids]
    structure_entries = [_entry_payload(node_id) for node_id in ordered_nodes]
    root_entries = [_entry_payload(node_id) for node_id in list(children_by_parent.get("", []))]

    columns = [
        {
            "column_id": "depth_1",
            "depth": 1,
            "kind": "lineage_root",
            "anchor_node_id": "",
            "anchor_msn_id": "",
            "anchor_title": "",
            "entries": root_entries,
        }
    ]
    for path_node_id in active_path_node_ids:
        columns.append(
            {
                "column_id": f"depth_{_node_depth(path_node_id) + 1}",
                "depth": _node_depth(path_node_id) + 1,
                "kind": "ordered_child_field" if path_node_id == target_node_id else "lineage_child_field",
                "anchor_node_id": path_node_id,
                "anchor_msn_id": path_node_id,
                "anchor_title": _as_text(title_map.get(path_node_id)),
                "entries": [_entry_payload(node_id) for node_id in list(children_by_parent.get(path_node_id, []))],
            }
        )

    return {
        "active_node_id": target_node_id,
        "anchored_path": {
            "title": "Anchored Path",
            "entries": active_path_entries,
        },
        "structure_field": {
            "title": "Structure Field",
            "entries": structure_entries,
        },
        "ordered_hierarchy": {
            "title": "Ordered Hierarchy",
            "columns": columns,
            "active_path": active_path_entries,
            "selected_node_id": target_node_id,
            "interaction": {
                "dynamic_depth": True,
                "expand_behavior": "structural_selection_expand",
                "compress_behavior": "structural_non_focus_compress",
                "selection_model": "click_to_focus",
            },
        },
    }


def _synthetic_ordered_hierarchy_nodes(active_node_id: str) -> dict[str, str]:
    selected_node_id = _as_text(active_node_id) or _DEFAULT_ATTENTION_NODE_ID
    node_titles = {
        "3": "USA",
        "3-2": "State",
        "3-2-3": "Ohio",
        "3-2-3-17": "Summit",
        "3-2-3-17-77": "Summit County",
    }
    selected_parts = [part for part in selected_node_id.split("-") if part]
    for depth in range(1, len(selected_parts) + 1):
        node_titles.setdefault("-".join(selected_parts[:depth]), "")
    if selected_node_id:
        node_titles[f"{selected_node_id}-1"] = "Akron"
        node_titles[f"{selected_node_id}-2"] = "Fairlawn"
        node_titles[f"{selected_node_id}-3"] = "Cuyahoga Falls"
    node_titles.setdefault(f"{selected_node_id}-1-1", "Ward North")
    node_titles.setdefault(f"{selected_node_id}-1-2", "Ward South")
    return node_titles


def _extract_real_ordered_hierarchy_nodes(source_payload: dict[str, Any]) -> dict[str, str]:
    row_source = _split_row_source(source_payload)
    node_titles: dict[str, str] = {}
    for datum_address in sorted(row_source.keys(), key=_node_sort_key):
        raw_row = row_source.get(datum_address)
        if not isinstance(raw_row, list) or not raw_row:
            continue
        data_tokens = raw_row[0] if isinstance(raw_row[0], list) else raw_row
        if not isinstance(data_tokens, list):
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
        if node_id not in node_titles:
            node_titles[node_id] = decoded_title
        elif not node_titles[node_id] and decoded_title:
            node_titles[node_id] = decoded_title
    return node_titles


def _synthetic_geospatial_projection(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    selected_node_id: str,
) -> dict[str, Any]:
    polygon_coordinates = [
        [-81.715, 41.145],
        [-81.510, 41.145],
        [-81.510, 41.015],
        [-81.715, 41.015],
        [-81.715, 41.145],
    ]
    feature_id = "synthetic:garland:polygon:1"
    feature_geometry = {"type": "Polygon", "coordinates": [polygon_coordinates]}
    return {
        "title": "Geospatial Projection",
        "data_source": "synthetic",
        "projection_state": "synthetic_baseline",
        "feature_count": 1,
        "render_feature_count": 1,
        "render_row_count": 1,
        "supporting_document_name": _DEFAULT_SUPPORTING_DOCUMENT_NAME,
        "projection_document_name": "synthetic_hops_projection",
        "selected_feature_id": feature_id,
        "selected_feature_geometry_type": "Polygon",
        "selected_feature_bounds": _bounds_from_points(polygon_coordinates),
        "collection_bounds": _bounds_from_points(polygon_coordinates),
        "empty_message": "Synthetic geospatial scaffold is active.",
        "feature_collection": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": feature_id,
                    "geometry": feature_geometry,
                    "properties": {
                        "samras_node_id": _as_text(selected_node_id),
                        "profile_label": "synthetic_polygon_alpha",
                        "title_display": "Synthetic Polygon Alpha",
                    },
                }
            ],
            "bounds": _bounds_from_points(polygon_coordinates),
        },
        "features": [
            {
                "feature_id": feature_id,
                "label": "synthetic_polygon_alpha",
                "node_id": _as_text(selected_node_id),
                "geometry_type": "Polygon",
                "selected": True,
                "shell_request": _selection_shell_request(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    tool_state=resolved_tool_state,
                    selected_row_address="synthetic:row:1",
                    selected_feature_id=feature_id,
                ),
            }
        ],
    }


def _real_geospatial_projection(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    service_surface: dict[str, Any],
    source_evidence: dict[str, Any],
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
            "data_source": "real_hops_polygon_projection",
            "projection_state": _as_text(map_projection.get("projection_state")) or "projectable",
            "feature_count": len(feature_entries),
            "render_feature_count": int(render_set_summary.get("render_feature_count") or len(feature_entries)),
            "render_row_count": int(render_set_summary.get("render_row_count") or 0),
            "supporting_document_name": supporting_document_name,
            "projection_document_name": projection_document_name,
            "selected_feature_id": selected_feature_id,
            "selected_feature_geometry_type": selected_geometry_type,
            "selected_feature_bounds": selected_feature_bounds,
            "collection_bounds": collection_bounds,
            "empty_message": "Projection ready.",
            "feature_collection": {
                "type": "FeatureCollection",
                "features": feature_collection_features,
                "bounds": collection_bounds,
            },
            "features": feature_entries,
        },
        True,
    )


def _cts_gis_interface_body(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    source_evidence: dict[str, Any],
    service_surface: dict[str, Any],
) -> dict[str, Any]:
    attention_profile = dict(service_surface.get("attention_profile") or {})
    selected_document = dict(service_surface.get("selected_document") or {})
    supporting_document = dict(source_evidence.get("administrative_source") or {})
    selected_node_id = _as_text(resolved_tool_state["aitas"]["attention_node_id"]) or _DEFAULT_ATTENTION_NODE_ID
    supporting_document_name = _as_text(supporting_document.get("document_name")) or _DEFAULT_SUPPORTING_DOCUMENT_NAME
    projection_document_name = _as_text(selected_document.get("document_name")) or "—"
    projection_rule_entries = [
        {
            "token": _as_text(option.get("token")),
            "label": _as_text(option.get("label")) or _as_text(option.get("token")) or "Rule",
            "detail": f"{int(option.get('profile_count') or 0)} profiles · {int(option.get('feature_count') or 0)} features",
            "selected": bool(option.get("active")),
            "shell_request": _intention_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                intention_rule_id=_as_text(option.get("token")),
            ),
        }
        for option in list((service_surface.get("mediation_state") or {}).get("available_intentions") or [])
    ]
    context_items = [
        {
            "label": "Attention",
            "value": _as_text(attention_profile.get("profile_label")) or selected_node_id,
            "detail": selected_node_id,
        },
        {
            "label": "Intention",
            "value": _as_text(resolved_tool_state["aitas"]["intention_rule_id"]) or _DEFAULT_INTENTION_RULE_ID,
        },
        {
            "label": "Time",
            "value": _as_text(resolved_tool_state["aitas"]["time_directive"]) or "inactive",
        },
        {
            "label": "Archetype",
            "value": _as_text(resolved_tool_state["aitas"]["archetype_family_id"]) or _DEFAULT_ARCHETYPE_FAMILY_ID,
        },
    ]

    synthetic_navigation = _build_ordered_hierarchy_navigation(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        selected_node_id=selected_node_id,
        node_titles=_synthetic_ordered_hierarchy_nodes(selected_node_id),
    )
    navigation_canvas = {
        "kind": "diktataograph_navigation_canvas",
        "title": "Diktataograph",
        "summary": "Ordered hierarchy scaffold for deterministic CTS-GIS reconstruction.",
        "mode": _CTS_GIS_NAV_MODE_ORDERED,
        "available_modes": [_CTS_GIS_NAV_MODE_ORDERED, _CTS_GIS_NAV_MODE_LEGACY],
        "active_node_id": _as_text(synthetic_navigation.get("active_node_id")),
        "ordered_hierarchy": dict(synthetic_navigation.get("ordered_hierarchy") or {}),
        "anchored_path": dict(synthetic_navigation.get("anchored_path") or {"title": "Anchored Path", "entries": []}),
        "structure_field": dict(synthetic_navigation.get("structure_field") or {"title": "Structure Field", "entries": []}),
        "projection_rule_field": {
            "title": "Projection Rule",
            "entries": projection_rule_entries,
        },
    }

    geospatial_projection = _synthetic_geospatial_projection(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        selected_node_id=selected_node_id,
    )
    active_path_entries = list((navigation_canvas.get("anchored_path") or {}).get("entries") or [])
    active_path_entry = active_path_entries[-1] if active_path_entries else {}
    profile_projection = {
        "title": "Profile Projection",
        "active_profile": {
            "label": _as_text(attention_profile.get("profile_label"))
            or _as_text(active_path_entry.get("label"))
            or selected_node_id,
            "node_id": _as_text(attention_profile.get("node_id")) or selected_node_id,
            "feature_count": int(attention_profile.get("feature_count") or 0),
            "child_count": int(attention_profile.get("child_count") or 0),
            "document_id": _as_text(attention_profile.get("document_id")),
        },
        "hierarchy": active_path_entries,
        "summary_rows": [],
        "projected_rows": [
            {
                "datum_address": "synthetic:row:1",
                "label": "synthetic_profile_summary",
                "detail": "Deterministic scaffold row",
                "selected": True,
                "shell_request": _selection_shell_request(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    tool_state=resolved_tool_state,
                    selected_row_address="synthetic:row:1",
                    selected_feature_id="synthetic:garland:polygon:1",
                ),
            }
        ],
        "correlated_profiles": [
            {
                "profile_label": "synthetic_related_profile",
                "node_id": f"{selected_node_id}-1",
                "relation": "synthetic_baseline",
            }
        ],
        "warnings": list(service_surface.get("warnings") or []),
    }

    wiring_sequence = [_CTS_GIS_WIRING_STAGE_SYNTHETIC]
    geometry_state = "synthetic"
    hierarchy_state = "synthetic"
    hierarchy_source = "synthetic_ordered_hierarchy"

    real_geospatial_projection, garland_swapped = _real_geospatial_projection(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        service_surface=service_surface,
        source_evidence=source_evidence,
    )
    if garland_swapped:
        geospatial_projection = real_geospatial_projection
        geometry_state = "applied"
        wiring_sequence.append(_CTS_GIS_WIRING_STAGE_GARLAND)
    elif bool((source_evidence.get("administrative_source") or {}).get("exists")):
        geometry_state = "blocked"

    real_node_titles = _extract_real_ordered_hierarchy_nodes(
        dict((source_evidence.get("administrative_source") or {}).get("payload") or {})
    )
    if garland_swapped and real_node_titles:
        real_navigation = _build_ordered_hierarchy_navigation(
            portal_scope=portal_scope,
            shell_state=shell_state,
            resolved_tool_state=resolved_tool_state,
            selected_node_id=selected_node_id,
            node_titles=real_node_titles,
        )
        navigation_canvas["active_node_id"] = _as_text(real_navigation.get("active_node_id")) or selected_node_id
        navigation_canvas["ordered_hierarchy"] = dict(real_navigation.get("ordered_hierarchy") or {})
        navigation_canvas["anchored_path"] = dict(real_navigation.get("anchored_path") or {"title": "Anchored Path", "entries": []})
        navigation_canvas["structure_field"] = dict(real_navigation.get("structure_field") or {"title": "Structure Field", "entries": []})
        profile_projection["hierarchy"] = list((navigation_canvas.get("anchored_path") or {}).get("entries") or [])
        latest_path_entry = (profile_projection.get("hierarchy") or [{}])[-1]
        profile_projection["active_profile"] = {
            **dict(profile_projection.get("active_profile") or {}),
            "label": _as_text(latest_path_entry.get("title"))
            or _as_text(latest_path_entry.get("msn_id"))
            or selected_node_id,
            "node_id": _as_text(latest_path_entry.get("node_id")) or selected_node_id,
        }
        hierarchy_state = "applied"
        hierarchy_source = "real_samras_namespace"
        wiring_sequence.append(_CTS_GIS_WIRING_STAGE_HIERARCHY)
    elif real_node_titles and not garland_swapped:
        hierarchy_state = "blocked"
        hierarchy_source = "blocked_waiting_for_real_geometry_swap"
    elif bool((source_evidence.get("administrative_source") or {}).get("exists")):
        hierarchy_state = "blocked"
        hierarchy_source = "blocked_no_parseable_samras_rows"

    profile_projection["summary_rows"] = [
        {"label": "Supporting document", "value": supporting_document_name},
        {"label": "Projection document", "value": projection_document_name},
        {"label": "Attention node", "value": selected_node_id},
        {"label": "Geometry source", "value": _as_text(geospatial_projection.get("data_source")) or "synthetic"},
        {"label": "Hierarchy source", "value": hierarchy_source},
        {"label": "Wiring sequence", "value": " -> ".join(wiring_sequence)},
        {"label": "Title fallback", "value": "blank_only_ascii"},
        {"label": "Rendered features", "value": str(int(geospatial_projection.get("feature_count") or 0))},
    ]

    return {
        "kind": "cts_gis_interface_body",
        "layout": "dual_section",
        "narrow_layout": "context_diktataograph_garland_stack",
        "feature_flags": {
            "hover_attention_redistribution": False,
        },
        "wiring_sequence": wiring_sequence,
        "wiring_status": {
            _CTS_GIS_WIRING_STAGE_SYNTHETIC: "applied",
            _CTS_GIS_WIRING_STAGE_GARLAND: geometry_state,
            _CTS_GIS_WIRING_STAGE_HIERARCHY: hierarchy_state,
        },
        "context_strip": {
            "title": "CTS-GIS Context",
            "compact": True,
            "items": context_items,
        },
        "navigation_canvas": navigation_canvas,
        "garland_split_projection": {
            "kind": "garland_split_projection",
            "title": "Garland",
            "summary": "Scaffold-first CTS-GIS projection surface with staged deterministic-to-real wiring.",
            "geospatial_projection": geospatial_projection,
            "profile_projection": profile_projection,
        },
    }


def build_portal_cts_gis_surface_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    data_dir: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    tool_rows: list[dict[str, Any]] | None = None,
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=CTS_GIS_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("CTS-GIS tool surface is not registered")
    normalized_request_payload = request_payload if isinstance(request_payload, dict) else {}
    _assert_no_legacy_maps_aliases(normalized_request_payload)
    requested_tool_state = _normalize_tool_state(normalized_request_payload)
    datum_summary = _datum_summary(data_dir, portal_instance_id=portal_scope.scope_id)
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    missing_integrations = [] if datum_summary.get("configured") else ["data_dir"]
    missing_capabilities = [
        capability for capability in tool_entry.required_capabilities if capability not in portal_scope.capabilities
    ]
    datum_store = None if data_dir is None else FilesystemSystemDatumStoreAdapter(Path(data_dir))
    service_surface = CtsGisReadOnlyService(datum_store).read_surface(
        portal_scope.scope_id,
        selected_document_id=_as_text(requested_tool_state.get("source", {}).get("attention_document_id")),
        selected_row_address=_as_text(requested_tool_state.get("selection", {}).get("selected_row_address")),
        selected_feature_id=_as_text(requested_tool_state.get("selection", {}).get("selected_feature_id")),
        mediation_state={
            "attention_document_id": _as_text(requested_tool_state.get("source", {}).get("attention_document_id")),
            "attention_node_id": _as_text(requested_tool_state.get("aitas", {}).get("attention_node_id")),
            "intention_token": _service_intention_token(
                requested_tool_state.get("aitas", {}).get("intention_rule_id")
            ),
        },
    ) if datum_store is not None else {
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
            "attention_node_id": _DEFAULT_ATTENTION_NODE_ID,
            "intention_token": _DEFAULT_INTENTION_RULE_ID,
            "available_intentions": [],
        },
        "warnings": ["data_dir_missing"],
    }
    resolved_tool_state = _resolved_tool_state(requested_tool_state, service_surface)
    source_evidence = _build_source_evidence(
        data_dir=data_dir,
        private_dir=private_dir,
        service_surface=service_surface,
    )
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
    operational = bool(
        configured
        and enabled
        and not missing_integrations
        and not missing_capabilities
        and _as_text((source_evidence.get("readiness") or {}).get("state")) == "ready"
    )
    interface_body = _cts_gis_interface_body(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        source_evidence=source_evidence,
        service_surface=service_surface,
    )
    surface_payload = {
        "schema": CTS_GIS_TOOL_SURFACE_SCHEMA,
        "kind": "tool_mediation_surface",
        "tool_id": tool_entry.tool_id,
        "surface_id": CTS_GIS_TOOL_SURFACE_ID,
        "entrypoint_id": CTS_GIS_TOOL_ENTRYPOINT_ID,
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
            "legacy_aliases": [
                "mediation_state.attention_node_id",
                "mediation_state.intention_token",
                "selected_row_address",
                "selected_feature_id",
            ],
        },
        "tool_state": resolved_tool_state,
        "source_evidence": source_evidence,
        "warnings": service_warnings,
        "readiness": dict(source_evidence.get("readiness") or {}),
        "service_surface": service_surface,
    }
    control_panel = _cts_gis_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=data_dir,
        private_dir=private_dir,
        tool_rows=list(tool_rows or []),
        resolved_tool_state=resolved_tool_state,
        source_evidence=source_evidence,
        service_surface=service_surface,
    )
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_secondary_evidence",
        "title": "CTS-GIS Evidence",
        "subtitle": "Raw registrar, source, and cache evidence stays secondary to the Garland projection.",
        "visible": False,
        "surface_payload": {
            "kind": "tool_secondary_evidence",
            "tool_id": tool_entry.tool_id,
            "surface_id": CTS_GIS_TOOL_SURFACE_ID,
            "datum_summary": datum_summary,
            "tool_state": resolved_tool_state,
            "source_evidence": source_evidence,
            "diagnostic_summary": dict(service_surface.get("diagnostic_summary") or {}),
            "warnings": list(service_surface.get("warnings") or []),
        },
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "tool_mediation_panel",
        "title": "CTS-GIS",
        "summary": "CTS-GIS projects one mediation posture through structural navigation and correlated spatial evidence.",
        "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "sections": [
            {
                "title": "Readiness",
                "rows": [
                    {
                        "label": "state",
                        "value": _as_text((source_evidence.get("readiness") or {}).get("state")) or "pending",
                        "detail": _as_text((source_evidence.get("readiness") or {}).get("message")),
                    },
                    {
                        "label": "tool anchor",
                        "value": "yes" if (source_evidence.get("tool_anchor") or {}).get("exists") else "no",
                        "detail": _as_text((source_evidence.get("tool_anchor") or {}).get("file")),
                    },
                    {
                        "label": "registrar payload",
                        "value": "yes" if (source_evidence.get("registrar_payload") or {}).get("exists") else "no",
                        "detail": _as_text((source_evidence.get("registrar_payload") or {}).get("file")),
                    },
                ],
            }
        ],
        "surface_payload": surface_payload,
        "interface_body": interface_body,
    }
    return {
        "entrypoint_id": CTS_GIS_TOOL_ENTRYPOINT_ID,
        "read_write_posture": tool_entry.read_write_posture,
        "page_title": "CTS-GIS",
        "page_subtitle": "Spatial mediation surface owned by SYSTEM.",
        "surface_payload": surface_payload,
        "control_panel": control_panel,
        "workbench": workbench,
        "inspector": inspector,
        "shell_state": shell_state,
        "route": CTS_GIS_TOOL_ROUTE,
    }


def run_portal_cts_gis(
    request_payload: dict[str, Any] | None,
    *,
    data_dir: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, shell_state, normalized_payload, _ = _normalize_request(request_payload)
    bundle = build_portal_cts_gis_surface_bundle(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=data_dir,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
        request_payload=normalized_payload,
    )
    canonical_query = canonical_query_for_shell_state(shell_state, surface_id=CTS_GIS_TOOL_SURFACE_ID)
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=CTS_GIS_TOOL_SURFACE_ID,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=True,
        canonical_route=bundle["route"],
        canonical_query=canonical_query,
        canonical_url=build_canonical_url(surface_id=CTS_GIS_TOOL_SURFACE_ID, query=canonical_query),
        shell_state=shell_state.to_dict(),
        surface_payload=bundle["surface_payload"],
        shell_composition={},
        warnings=list(bundle["surface_payload"].get("warnings") or []),
        error=None,
    )


__all__ = [
    "LegacyMapsAliasUnsupportedError",
    "build_portal_cts_gis_surface_bundle",
    "run_portal_cts_gis",
]
