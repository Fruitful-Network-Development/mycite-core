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
from MyCiteV2.packages.core.structures.samras import (
    InvalidSamrasStructure,
    find_structure_authorities,
    reconstruct_structure_from_rows,
    select_preferred_structure_authority,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis import CtsGisReadOnlyService
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    CTS_GIS_NAV_MODE_DIRECTORY as _CTS_GIS_NAV_MODE_DIRECTORY,
    DEFAULT_ARCHETYPE_FAMILY_ID as _DEFAULT_ARCHETYPE_FAMILY_ID,
    DEFAULT_INTENTION_TOKEN as _DEFAULT_INTENTION_RULE_ID,
    DEFAULT_NIMM_DIRECTIVE as _DEFAULT_NIMM_DIRECTIVE,
    DEFAULT_SUPPORTING_DOCUMENT_NAME as _DEFAULT_SUPPORTING_DOCUMENT_NAME,
    DEFAULT_TIME_DIRECTIVE as _DEFAULT_TIME_DIRECTIVE,
    as_text as _as_text,
    canonical_runtime_intention_rule_id,
    canonical_service_intention_token,
)
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

_CANONICAL_TOOL_PUBLIC_ID = "cts_gis"
_CANONICAL_TOOL_SLUG = "cts-gis"
_CANONICAL_TOOL_ANCHOR_PATTERN = "tool.*.cts-gis.json"
_LEGACY_DOCUMENT_PREFIX = "sandbox:" + ("map" + "s") + ":"
_DATUM_STORE_BY_DATA_DIR: dict[str, FilesystemSystemDatumStoreAdapter] = {}


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


def _datum_store_for_data_dir(data_dir: str | Path | None) -> FilesystemSystemDatumStoreAdapter | None:
    root = _path_or_none(data_dir)
    if root is None:
        return None
    cache_key = str(root.resolve())
    cached = _DATUM_STORE_BY_DATA_DIR.get(cache_key)
    if cached is not None:
        return cached
    store = FilesystemSystemDatumStoreAdapter(root)
    _DATUM_STORE_BY_DATA_DIR[cache_key] = store
    return store


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
        "active_path": [_as_text(item) for item in list(payload.get("active_path") or []) if _as_text(item)],
        "selected_node_id": _as_text(payload.get("selected_node_id")),
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
    return {
        "nimm_directive": _as_text(raw_tool_state.get("nimm_directive") or normalized_payload.get("nimm_directive"))
        or _DEFAULT_NIMM_DIRECTIVE,
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
        datum_store = _datum_store_for_data_dir(data_dir)
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


def _cts_gis_source_path(data_dir: str | Path | None, *, document_name: str) -> Path | None:
    tool_root = _cts_gis_data_tool_root(data_dir)
    if tool_root is None:
        return None
    token = _as_text(document_name)
    if not token:
        return None
    source_root = tool_root / "sources"
    direct = source_root / token
    if direct.exists() and direct.is_file():
        return direct
    precinct = source_root / "precincts" / token
    if precinct.exists() and precinct.is_file():
        return precinct
    return direct


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
    source_path = _cts_gis_source_path(data_dir, document_name=supporting_document_name)
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
    selection_summary = dict(mediation_state.get("selection_summary") or {})
    requested_selection = dict(requested_tool_state.get("selection") or {})
    requested_active_path = _normalize_requested_active_path(requested_tool_state.get("active_path"))
    fallback_selected_node_id = ""
    if (
        not requested_active_path
        and not _as_text(requested_tool_state.get("selected_node_id"))
        and not _as_text(requested_tool_state.get("aitas", {}).get("attention_node_id"))
    ):
        fallback_selected_node_id = (
            _as_text(selection_summary.get("selected_profile_node_id"))
            or _as_text((service_surface.get("attention_profile") or {}).get("node_id"))
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
        "nimm_directive": _as_text(requested_tool_state.get("nimm_directive")) or _DEFAULT_NIMM_DIRECTIVE,
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
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _intention_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    intention_rule_id: str,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["aitas"]["intention_rule_id"] = canonical_runtime_intention_rule_id(
        intention_rule_id,
        attention_node_id=_as_text(next_state.get("selected_node_id") or next_state.get("aitas", {}).get("attention_node_id")),
    )
    next_state["selection"]["selected_row_address"] = ""
    next_state["selection"]["selected_feature_id"] = ""
    next_state["selection"]["selected_row_explicit"] = False
    next_state["selection"]["selected_feature_explicit"] = False
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _attention_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    attention_node_id: str,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    _apply_selected_node_state(next_state, attention_node_id)
    next_state["aitas"]["intention_rule_id"] = canonical_runtime_intention_rule_id(
        _as_text(next_state.get("aitas", {}).get("intention_rule_id")) or "self",
        attention_node_id=attention_node_id,
    )
    next_state["selection"]["selected_row_address"] = ""
    next_state["selection"]["selected_feature_id"] = ""
    next_state["selection"]["selected_row_explicit"] = False
    next_state["selection"]["selected_feature_explicit"] = False
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _time_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    time_directive: str,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state["aitas"]["time_directive"] = _as_text(time_directive)
    next_state["selection"]["selected_row_address"] = ""
    next_state["selection"]["selected_feature_id"] = ""
    next_state["selection"]["selected_row_explicit"] = False
    next_state["selection"]["selected_feature_explicit"] = False
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _precinct_overlay_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    enabled: bool,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    next_state.setdefault("source", {})
    next_state["source"]["precinct_district_overlay_enabled"] = bool(enabled)
    next_state["selection"]["selected_row_address"] = ""
    next_state["selection"]["selected_feature_id"] = ""
    next_state["selection"]["selected_row_explicit"] = False
    next_state["selection"]["selected_feature_explicit"] = False
    return _tool_state_request(portal_scope=portal_scope, shell_state=shell_state, tool_state=next_state)


def _document_shell_request(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    tool_state: dict[str, Any],
    attention_document_id: str,
) -> dict[str, Any]:
    next_state = _tool_state_clone(tool_state)
    _apply_selected_node_state(next_state, "")
    next_state["source"]["attention_document_id"] = _as_text(attention_document_id)
    next_state["selection"]["selected_row_address"] = ""
    next_state["selection"]["selected_feature_id"] = ""
    next_state["selection"]["selected_row_explicit"] = False
    next_state["selection"]["selected_feature_explicit"] = False
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
    next_state["selection"]["selected_row_explicit"] = bool(_as_text(selected_row_address))
    next_state["selection"]["selected_feature_explicit"] = bool(_as_text(selected_feature_id))
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
                ),
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
            ),
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
                ),
            }
            for token, label in fallback_options
        ]
    intention_self_token = "self"
    intention_children_token = (
        f"{current_attention_node_id}-0" if current_attention_node_id else canonical_runtime_intention_rule_id("children", attention_node_id="")
    )
    intention_descendants_token = (
        f"{current_attention_node_id}-0-0"
        if current_attention_node_id
        else canonical_runtime_intention_rule_id("descendants_depth_1_or_2", attention_node_id="")
    )
    intention_levels = [
        {"display": "1", "token": intention_self_token},
        {"display": "0", "token": intention_children_token},
        {"display": "0-0", "token": intention_descendants_token},
    ]
    intention_level_index = 0
    for index, level in enumerate(intention_levels):
        if _as_text(level.get("token")) == current_intention_rule_id:
            intention_level_index = index
            break
    time_tokens = [_DEFAULT_TIME_DIRECTIVE]
    if current_time_directive and current_time_directive not in time_tokens:
        time_tokens.insert(0, current_time_directive)
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
            ),
        }
        for token in time_tokens
    ]
    locked_entries = [
        {"label": "Archetype", "meta": _as_text(resolved_tool_state["aitas"]["archetype_family_id"]) or _DEFAULT_ARCHETYPE_FAMILY_ID, "active": False},
        {"label": "NAV", "meta": "locked", "active": False},
        {"label": "INV", "meta": "locked", "active": False},
        {"label": "MED", "meta": "locked", "active": False},
        {"label": "MAN", "meta": "locked", "active": False},
    ]
    state_directive_entries = [
        {"label": "NIMM directive", "meta": _as_text(resolved_tool_state["nimm_directive"]), "active": True},
        *attention_entries,
        *intention_entries,
        *time_entries,
        *locked_entries,
    ]
    state_directive_compact = {
        "nimm_buttons": [
            {"label": "NAV", "active": _as_text(resolved_tool_state.get("nimm_directive")) == "nav"},
            {"label": "INV", "active": _as_text(resolved_tool_state.get("nimm_directive")) == "inv"},
            {"label": "MED", "active": _as_text(resolved_tool_state.get("nimm_directive")) == "med"},
            {"label": "MAN", "active": _as_text(resolved_tool_state.get("nimm_directive")) == "man"},
        ],
        "script_input": {
            "placeholder": "/enter...",
            "enabled": False,
            "help": "Directive script input is not active yet.",
        },
        "aitas_modes": [
            {"id": "A", "label": "A", "field": "attention"},
            {"id": "I", "label": "I", "field": "intention"},
            {"id": "T", "label": "T", "field": "time"},
            {"id": "A2", "label": "A", "field": "archetype", "locked": True},
            {"id": "S", "label": "S", "field": "source", "locked": True},
        ],
        "active_mode": "I",
        "attention": {
            "value": current_attention_node_id,
            "shell_template": _tool_state_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
            ),
        },
        "time": {
            "value": current_time_directive,
            "shell_template": _tool_state_request(
                portal_scope=portal_scope,
                shell_state=shell_state,
                tool_state=resolved_tool_state,
            ),
        },
        "intention": {
            "active_index": intention_level_index,
            "levels": [
                {
                    "display": _as_text(level.get("display")),
                    "token": _as_text(level.get("token")),
                    "shell_request": _intention_shell_request(
                        portal_scope=portal_scope,
                        shell_state=shell_state,
                        tool_state=resolved_tool_state,
                        intention_rule_id=_as_text(level.get("token")),
                    ),
                }
                for level in intention_levels
            ],
        },
        "validation": {
            "node_id_pattern": r"^\d+(?:-\d+)*$",
            "invalid_attention_message": "Invalid attention node id.",
            "invalid_time_message": "Invalid time token; use HOPS-style address id.",
        },
    }
    return {
        **base_panel,
        "context_items": _context_items_from_base_panel(base_panel, source_evidence),
        "verb_tabs": [],
        "groups": [{"title": "STATE DIRECTIVE", "entries": state_directive_entries}],
        "state_directive_compact": state_directive_compact,
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


def _row_data_tokens(raw_row: object) -> list[Any]:
    if not isinstance(raw_row, list) or not raw_row:
        return []
    data_tokens = raw_row[0] if isinstance(raw_row[0], list) else raw_row
    return list(data_tokens) if isinstance(data_tokens, list) else []


def _row_label_tokens(raw_row: object) -> list[str]:
    if not isinstance(raw_row, list) or len(raw_row) < 2 or not isinstance(raw_row[1], list):
        return []
    return [_as_text(item) for item in raw_row[1] if _as_text(item)]


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
        ),
    }


def _build_directory_dropdown_navigation(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    source_evidence: dict[str, Any],
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
    if structure is None and authorities:
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
        requested_active_path = _sanitize_active_path(list(resolved_tool_state.get("active_path") or []), ordered_nodes)
        requested_selected_node_id = _as_text(resolved_tool_state.get("selected_node_id"))
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
        "summary_rows": [],
        "warnings": list(warnings or []),
        "district_overlay_toggle": {
            "enabled": False,
            "overlay_active": False,
            "time_token": "",
            "timeframe_tokens": [],
            "timeframe_match": False,
            "shell_request": {},
        },
        "empty_message": "No projected profile is available until the active path resolves real CTS-GIS evidence.",
        "has_profile_state": False,
        "has_real_projection": False,
    }


def _cts_gis_interface_body(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    resolved_tool_state: dict[str, Any],
    navigation_canvas: dict[str, Any],
    source_evidence: dict[str, Any],
    service_surface: dict[str, Any],
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
        ),
    }
    real_geospatial_projection, garland_swapped = _real_geospatial_projection(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        service_surface=service_surface,
        source_evidence=source_evidence,
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
    if decode_ready and selected_node_id and attention_matches_selection and garland_swapped:
        geospatial_projection = {
            **real_geospatial_projection,
            "lens_state": lens_state,
        }
    elif decode_ready and selected_node_id and bool((source_evidence.get("administrative_source") or {}).get("exists")):
        geospatial_projection = {
            **geospatial_projection,
            "lens_state": lens_state,
            "projection_state": "awaiting_real_projection",
            "empty_message": "The selected node resolves structurally, but no HOPS projection is available for it yet.",
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
            "summary_rows": [
                {"label": "Supporting document", "value": supporting_document_name},
                {"label": "Projection document", "value": "—"},
                {"label": "Projection source", "value": _as_text(map_projection.get("projection_source")) or "none"},
                {"label": "Projection state", "value": "awaiting_real_projection"},
                {"label": "Decode summary", "value": decode_summary_text},
            ],
            "district_overlay_toggle": district_overlay_toggle,
            "empty_message": "The selected node resolves structurally, but no profile projection is available for it yet.",
            "has_profile_state": True,
            "lens_state": lens_state,
        }

    return {
        "kind": "cts_gis_interface_body",
        "layout": "diktataograph_garland_split",
        "narrow_layout": "diktataograph_garland_stack",
        "navigation_canvas": navigation_canvas,
        "garland_split_projection": {
            "kind": "garland_split_projection",
            "title": "Garland",
            "summary": "Correlated projection surface that shows provenance, decode health, and document context for the selected SAMRAS node.",
            "lens_state": lens_state,
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
    datum_store = _datum_store_for_data_dir(data_dir)
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
    service_surface = CtsGisReadOnlyService(datum_store).read_surface(
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
            "attention_node_id": "",
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
    navigation_canvas = _build_directory_dropdown_navigation(
        portal_scope=portal_scope,
        shell_state=shell_state,
        resolved_tool_state=resolved_tool_state,
        source_evidence=source_evidence,
    )
    resolved_tool_state = _tool_state_for_navigation(resolved_tool_state, navigation_canvas)
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
        navigation_canvas=navigation_canvas,
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
