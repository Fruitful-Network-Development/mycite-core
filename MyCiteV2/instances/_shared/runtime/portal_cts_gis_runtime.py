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
    selected_row = dict(service_surface.get("selected_row") or {})
    map_projection = dict(service_surface.get("map_projection") or {})
    selected_feature = dict(map_projection.get("selected_feature") or {})
    feature_collection = dict(map_projection.get("feature_collection") or {})
    render_set_summary = dict(service_surface.get("render_set_summary") or {})
    projection_state = _as_text(map_projection.get("projection_state")) or "inspect_only"
    selected_row_address = _as_text(selected_row.get("datum_address"))
    feature_rows = list(feature_collection.get("features") or [])
    feature_entries = [
        {
            "feature_id": _as_text(feature.get("id")),
            "label": _as_text((feature.get("properties") or {}).get("profile_label"))
            or _as_text((feature.get("properties") or {}).get("samras_node_id"))
            or _as_text(feature.get("id"))
            or "feature",
            "node_id": _as_text((feature.get("properties") or {}).get("samras_node_id")),
            "geometry_type": _as_text((feature.get("geometry") or {}).get("type")) or "unknown",
            "selected": bool(feature.get("selected")),
            "shell_request": _selection_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                selected_row_address=selected_row_address,
                selected_feature_id=_as_text(feature.get("id")),
            ),
        }
        for feature in feature_rows[:16]
        if _as_text(feature.get("id"))
    ]
    feature_collection_bounds = feature_collection.get("bounds")
    feature_collection_bounds = (
        list(feature_collection_bounds)
        if isinstance(feature_collection_bounds, list)
        else []
    )
    selected_feature_bounds = list(selected_feature.get("bounds") or [])
    selected_feature_geometry_type = _as_text(selected_feature.get("geometry_type"))
    supporting_document_name = _as_text(supporting_document.get("document_name")) or _DEFAULT_SUPPORTING_DOCUMENT_NAME
    projection_document_name = _as_text(selected_document.get("document_name"))
    if projection_state == "no_authoritative_cts_gis_documents":
        geospatial_empty_message = "No authoritative CTS-GIS documents are available for this portal scope."
    elif int(map_projection.get("feature_count") or 0) <= 0:
        geospatial_empty_message = "No projected geometry is available for the current navigation root."
    else:
        geospatial_empty_message = "Projection ready."
    context_items = [
        {
            "label": "Attention",
            "value": _as_text(attention_profile.get("profile_label")) or _as_text(resolved_tool_state["aitas"]["attention_node_id"]),
            "detail": _as_text(resolved_tool_state["aitas"]["attention_node_id"]),
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
    active_profile_card = {
        "label": _as_text(attention_profile.get("profile_label")) or _as_text(resolved_tool_state["aitas"]["attention_node_id"]),
        "node_id": _as_text(attention_profile.get("node_id")) or _as_text(resolved_tool_state["aitas"]["attention_node_id"]),
        "feature_count": int(attention_profile.get("feature_count") or 0),
        "child_count": int(attention_profile.get("child_count") or 0),
        "document_id": _as_text(attention_profile.get("document_id")),
    }
    navigation_nodes = [
        {
            "node_id": _as_text(item.get("node_id")),
            "label": _as_text(item.get("profile_label")) or _as_text(item.get("node_id")),
            "title_display": _as_text(item.get("title_display")),
            "detail": f"{int(item.get('feature_count') or 0)} features · {int(item.get('child_count') or 0)} children",
            "depth": len(_as_text(item.get("node_id")).split("-")),
            "parent_node_id": "-".join(_as_text(item.get("node_id")).split("-")[:-1]),
            "selected": bool(item.get("selected")),
            "shell_request": _node_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                attention_node_id=_as_text(item.get("node_id")),
            ),
        }
        for item in list(service_surface.get("render_profiles") or [])
        if _as_text(item.get("node_id"))
    ]
    anchored_path_entries = [
        {
            "node_id": _as_text(item.get("node_id")),
            "label": _as_text(item.get("profile_label")) or _as_text(item.get("node_id")),
            "selected": bool(item.get("selected")),
            "shell_request": _node_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                attention_node_id=_as_text(item.get("node_id")),
            ),
        }
        for item in list(service_surface.get("lineage") or [])
        if _as_text(item.get("node_id"))
    ]
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
    projected_rows = [
        {
            "datum_address": _as_text(row.get("datum_address")),
            "label": _as_text(row.get("profile_label")) or _as_text(row.get("label_text")) or _as_text(row.get("datum_address")),
            "detail": ", ".join(str(item) for item in list(row.get("labels") or [])[:3]) or _as_text(row.get("recognized_anchor")),
            "selected": bool(row.get("selected")),
            "shell_request": _selection_shell_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
                selected_row_address=_as_text(row.get("datum_address")),
                selected_feature_id=_as_text(selected_feature.get("feature_id")),
            ),
        }
        for row in list(service_surface.get("rows") or [])[:12]
    ]
    feature_geometry_entries = [
        {
            "feature_id": _as_text(feature.get("id")),
            "label": _as_text((feature.get("properties") or {}).get("profile_label"))
            or _as_text((feature.get("properties") or {}).get("samras_node_id"))
            or _as_text(feature.get("id"))
            or "feature",
            "node_id": _as_text((feature.get("properties") or {}).get("samras_node_id")),
            "geometry": dict(feature.get("geometry") or {}),
            "selected": bool(feature.get("selected")),
        }
        for feature in feature_rows[:48]
        if _as_text(feature.get("id"))
    ]
    profile_projection_rows = [
        {"label": "Supporting document", "value": supporting_document_name},
        {"label": "Projection document", "value": projection_document_name or "—"},
        {"label": "Attention node", "value": _as_text(resolved_tool_state["aitas"]["attention_node_id"]) or "—"},
        {"label": "Projection state", "value": projection_state},
        {"label": "Rendered features", "value": str(int(render_set_summary.get("render_feature_count") or 0))},
        {"label": "Rendered rows", "value": str(int(render_set_summary.get("render_row_count") or 0))},
        {"label": "Selected row", "value": selected_row_address or "—"},
        {"label": "Selected feature", "value": _as_text(selected_feature.get("feature_id")) or "—"},
        {"label": "GeoJSON cache", "value": "ready" if (source_evidence.get("administrative_payload_cache") or {}).get("exists") else "pending"},
    ]
    if selected_feature.get("bounds"):
        profile_projection_rows.append(
            {
                "label": "Feature bounds",
                "value": ", ".join(str(item) for item in list(selected_feature.get("bounds") or [])),
            }
        )
    return {
        "kind": "cts_gis_interface_body",
        "layout": "dual_section",
        "narrow_layout": "context_diktataograph_garland_stack",
        "feature_flags": {
            "hover_attention_redistribution": False,
        },
        "context_strip": {
            "title": "CTS-GIS Context",
            "compact": True,
            "items": context_items,
        },
        "navigation_canvas": {
            "kind": "diktataograph_navigation_canvas",
            "title": "Diktataograph",
            "summary": "Structural navigation canvas for the active SAMRAS-defined address space, with correlated ASCII labels from the supporting source document.",
            "active_node_id": _as_text(resolved_tool_state["aitas"]["attention_node_id"]),
            "anchored_path": {
                "title": "Anchored Path",
                "entries": anchored_path_entries,
            },
            "structure_field": {
                "title": "Structure Field",
                "entries": navigation_nodes,
            },
            "projection_rule_field": {
                "title": "Projection Rule",
                "entries": projection_rule_entries,
            },
        },
        "garland_split_projection": {
            "kind": "garland_split_projection",
            "title": "Garland",
            "summary": "Correlated projection surface for the currently navigated address node with respect to the supporting source file.",
            "geospatial_projection": {
                "title": "Geospatial Projection",
                "projection_state": projection_state,
                "feature_count": int(map_projection.get("feature_count") or 0),
                "render_feature_count": int(render_set_summary.get("render_feature_count") or 0),
                "render_row_count": int(render_set_summary.get("render_row_count") or 0),
                "supporting_document_name": supporting_document_name,
                "projection_document_name": projection_document_name,
                "selected_feature_id": _as_text(selected_feature.get("feature_id")),
                "selected_feature_geometry_type": selected_feature_geometry_type,
                "selected_feature_bounds": selected_feature_bounds,
                "collection_bounds": feature_collection_bounds,
                "empty_message": geospatial_empty_message,
                "feature_collection": {
                    "type": _as_text(feature_collection.get("type")) or "FeatureCollection",
                    "features": feature_geometry_entries,
                    "bounds": feature_collection_bounds,
                },
                "features": feature_entries,
            },
            "profile_projection": {
                "title": "Profile Projection",
                "active_profile": active_profile_card,
                "hierarchy": anchored_path_entries,
                "summary_rows": profile_projection_rows,
                "projected_rows": projected_rows,
                "correlated_profiles": list(service_surface.get("related_profiles") or []),
                "warnings": list(service_surface.get("warnings") or []),
            },
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
