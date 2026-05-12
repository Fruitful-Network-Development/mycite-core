from __future__ import annotations

import copy
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import (
    CTS_GIS_COMPILED_ARTIFACT_SCHEMA,
    CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
    CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT,
    as_text,
)

_COMPILED_DIR = Path("payloads") / "compiled"
_SOURCE_ROOT = Path("sandbox") / "cts-gis" / "sources"
CTS_GIS_SOURCE_LAYOUT_SCHEMA = "mycite.v2.portal.system.tools.cts_gis.source_layout.v1"


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cts_gis_source_root(data_dir: str | Path | None) -> Path | None:
    if data_dir is None:
        return None
    return Path(data_dir) / _SOURCE_ROOT


def _deduped_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _iter_cts_gis_source_files(source_root: Path | None) -> tuple[list[Path], list[Path]]:
    if source_root is None or not source_root.exists() or not source_root.is_dir():
        return [], []
    top_level_files = sorted(source_root.glob("*.json"))
    precinct_root = source_root / "precincts"
    precinct_files = sorted(precinct_root.glob("*.json")) if precinct_root.exists() and precinct_root.is_dir() else []
    return _deduped_paths(top_level_files), _deduped_paths(precinct_files)


def build_cts_gis_source_layout_summary(data_dir: str | Path | None) -> dict[str, Any]:
    source_root = cts_gis_source_root(data_dir)
    precinct_root = None if source_root is None else source_root / "precincts"
    top_level_files, precinct_files = _iter_cts_gis_source_files(source_root)
    fingerprint = hashlib.sha256()
    relative_paths: list[str] = []
    for path in [*top_level_files, *precinct_files]:
        if source_root is None:
            continue
        try:
            relative_path = path.relative_to(source_root).as_posix()
        except Exception:
            relative_path = path.name
        stat = path.stat()
        fingerprint.update(f"{relative_path}|{int(stat.st_mtime_ns)}|{int(stat.st_size)}\n".encode("utf-8"))
        relative_paths.append(relative_path)
    return {
        "schema": CTS_GIS_SOURCE_LAYOUT_SCHEMA,
        "source_root": "" if source_root is None else str(source_root),
        "precinct_root": "" if precinct_root is None else str(precinct_root),
        "root_exists": bool(source_root is not None and source_root.exists() and source_root.is_dir()),
        "precinct_root_exists": bool(precinct_root is not None and precinct_root.exists() and precinct_root.is_dir()),
        "top_level_file_count": len(top_level_files),
        "precinct_file_count": len(precinct_files),
        "total_file_count": len(top_level_files) + len(precinct_files),
        "sample_relative_paths": relative_paths[:12],
        "fingerprint": fingerprint.hexdigest() if relative_paths else "",
    }


def validate_cts_gis_source_layout(layout: dict[str, Any] | None) -> tuple[bool, list[str]]:
    payload = layout if isinstance(layout, dict) else {}
    issues: list[str] = []
    if as_text(payload.get("schema")) != CTS_GIS_SOURCE_LAYOUT_SCHEMA:
        issues.append("source_layout_invalid_schema")
    if not bool(payload.get("root_exists")):
        issues.append("source_root_missing")
    if not bool(payload.get("precinct_root_exists")):
        issues.append("precinct_root_missing")
    if int(payload.get("top_level_file_count") or 0) <= 0:
        issues.append("source_root_empty")
    if not as_text(payload.get("fingerprint")):
        issues.append("source_fingerprint_missing")
    return (not issues, issues)


def _projection_model_from_service(service_surface: dict[str, Any]) -> dict[str, Any]:
    map_projection = dict(service_surface.get("map_projection") or {})
    feature_collection = dict(map_projection.get("feature_collection") or {})
    selected_feature = dict(map_projection.get("selected_feature") or {})
    attention_profile = dict(service_surface.get("attention_profile") or {})
    contextual_references = dict(service_surface.get("contextual_references") or {})
    return {
        "projection_state": as_text(map_projection.get("projection_state")) or "inspect_only",
        "projection_source": as_text(map_projection.get("projection_source")) or "none",
        "projection_health": dict(map_projection.get("projection_health") or {"state": "empty", "reason_codes": []}),
        "fallback_reason_codes": list(map_projection.get("fallback_reason_codes") or []),
        "focus_bounds": map_projection.get("focus_bounds"),
        "feature_collection": {
            "type": "FeatureCollection",
            "features": list(feature_collection.get("features") or []),
            "bounds": feature_collection.get("bounds"),
        },
        "selected_feature": selected_feature,
        "profile_summary": {
            "node_id": as_text(attention_profile.get("node_id")),
            "label": as_text(attention_profile.get("profile_label")) or as_text(attention_profile.get("node_id")),
            "feature_count": int(attention_profile.get("feature_count") or 0),
            "child_count": int(attention_profile.get("child_count") or 0),
            "document_id": as_text(attention_profile.get("document_id")),
        },
        "contextual_references": contextual_references,
    }


def _navigation_model_from_canvas(navigation_canvas: dict[str, Any]) -> dict[str, Any]:
    path_entries = list(navigation_canvas.get("active_path") or [])
    return {
        "decode_state": as_text(navigation_canvas.get("decode_state")) or "blocked_invalid_magnitude",
        "source_authority": as_text(navigation_canvas.get("source_authority")) or "samras_magnitude",
        "active_node_id": as_text(navigation_canvas.get("active_node_id")),
        "active_path": [
            {
                "node_id": as_text(entry.get("node_id")),
                "title": as_text(entry.get("title")),
                "display_label": as_text(entry.get("display_label")),
                "selected": bool(entry.get("selected")),
            }
            for entry in path_entries
            if isinstance(entry, dict)
        ],
        "dropdowns": [
            {
                "depth": int(dropdown.get("depth") or 0),
                "parent_node_id": as_text(dropdown.get("parent_node_id")),
                "selected_node_id": as_text(dropdown.get("selected_node_id")),
                "options": [
                    {
                        "node_id": as_text(option.get("node_id")),
                        "title": as_text(option.get("title")),
                        "display_label": as_text(option.get("display_label")),
                        "selected": bool(option.get("selected")),
                    }
                    for option in list((dropdown.get("options") or []))
                    if isinstance(option, dict)
                ],
            }
            for dropdown in list(navigation_canvas.get("dropdowns") or [])
            if isinstance(dropdown, dict)
        ],
    }


def _invariants(*, navigation_model: dict[str, Any], source_evidence: dict[str, Any]) -> dict[str, Any]:
    decode_state = as_text(navigation_model.get("decode_state"))
    readiness_state = as_text((source_evidence.get("readiness") or {}).get("state"))
    issues: list[str] = []
    if decode_state != "ready":
        issues.append("navigation_decode_not_ready")
    if readiness_state != "ready":
        issues.append("source_evidence_not_ready")
    return {"valid": not issues, "issues": issues}


def _has_samras_authority(payload: dict[str, Any]) -> bool:
    space = payload.get("datum_addressing_abstraction_space")
    if not isinstance(space, dict):
        return False
    for row in list(space.values()):
        if not isinstance(row, list) or len(row) < 2:
            continue
        labels = row[1]
        if isinstance(labels, list) and any(as_text(label) == "msn-SAMRAS" for label in labels):
            return True
    return False


def _node_root(node_id: object) -> str:
    normalized = as_text(node_id)
    if not normalized:
        return ""
    return normalized.split("-", 1)[0] if "-" in normalized else normalized


def _namespace_roots(navigation_model: dict[str, Any]) -> list[str]:
    roots: set[str] = set()
    for entry in list(navigation_model.get("active_path") or []):
        root = _node_root((entry or {}).get("node_id"))
        if root:
            roots.add(root)
    if roots:
        return sorted(roots)

    active_node_root = _node_root(navigation_model.get("active_node_id"))
    if active_node_root:
        roots.add(active_node_root)

    for dropdown in list(navigation_model.get("dropdowns") or []):
        root = _node_root((dropdown or {}).get("selected_node_id"))
        if root:
            roots.add(root)
    return sorted(roots)


def _strict_invariants(*, navigation_model: dict[str, Any], source_evidence: dict[str, Any]) -> dict[str, Any]:
    authority_sources: list[str] = []
    tool_anchor_payload = dict((source_evidence.get("tool_anchor") or {}).get("payload") or {})
    administrative_cache_payload = dict((source_evidence.get("administrative_payload_cache") or {}).get("payload") or {})
    if _has_samras_authority(tool_anchor_payload):
        authority_sources.append("tool_anchor")
    if _has_samras_authority(administrative_cache_payload):
        authority_sources.append("administrative_payload_cache")
    namespace_roots = _namespace_roots(navigation_model)
    issues: list[str] = []
    one_authority = len(authority_sources) == 1
    one_namespace = len(namespace_roots) <= 1
    if not one_authority:
        issues.append("strict_one_authority_failed")
    if not one_namespace:
        issues.append("strict_one_namespace_failed")
    return {
        "one_authority": one_authority,
        "authority_sources": authority_sources,
        "one_namespace": one_namespace,
        "namespace_roots": namespace_roots,
        "valid": not issues,
        "issues": issues,
    }


def build_compiled_artifact(
    *,
    portal_scope_id: object,
    source_evidence: dict[str, Any],
    service_surface: dict[str, Any],
    navigation_canvas: dict[str, Any],
    default_tool_state: dict[str, Any],
    source_layout: dict[str, Any],
    build_mode: str = CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
    admin_profile_static: dict[str, Any] | None = None,
) -> dict[str, Any]:
    navigation_model = _navigation_model_from_canvas(navigation_canvas)
    projection_model = _projection_model_from_service(service_surface)
    invariants = _invariants(navigation_model=navigation_model, source_evidence=source_evidence)
    strict_invariants = _strict_invariants(navigation_model=navigation_model, source_evidence=source_evidence)
    artifact: dict[str, Any] = {
        "schema": CTS_GIS_COMPILED_ARTIFACT_SCHEMA,
        "artifact_version": "1",
        "generated_at": _utc_timestamp(),
        "portal_scope_id": as_text(portal_scope_id) or "fnd",
        "build_mode": as_text(build_mode) or CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
        "default_runtime_mode": CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT,
        "default_tool_state": dict(default_tool_state or {}),
        "source_layout": dict(source_layout or {}),
        "navigation_model": navigation_model,
        "projection_model": projection_model,
        "evidence_model": {
            "source_evidence": dict(source_evidence or {}),
            "diagnostic_summary": dict(service_surface.get("diagnostic_summary") or {}),
            "warnings": list(service_surface.get("warnings") or []),
        },
        "invariants": invariants,
        "strict_invariants": strict_invariants,
    }
    # admin_profile_static is the sandbox-spatial-root identity baked
    # once at compile time. The Garland tab's admin profile is rooted in
    # this field independent of the user's current navigation — the
    # cascade adds frames BELOW it, never replaces it. See
    # `evidence/reports/TASK-CTS-GIS-GARLAND-CASCADE-2026-05-11-admin-profile-attention-investigation.md`.
    if admin_profile_static:
        artifact["admin_profile_static"] = dict(admin_profile_static)
    return artifact


def validate_compiled_artifact(
    artifact: dict[str, Any] | None,
    *,
    expected_portal_scope_id: object | None = None,
    expected_source_layout: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    payload = artifact if isinstance(artifact, dict) else {}
    issues: list[str] = []
    if as_text(payload.get("schema")) != CTS_GIS_COMPILED_ARTIFACT_SCHEMA:
        issues.append("invalid_schema")
    if expected_portal_scope_id is not None and as_text(payload.get("portal_scope_id")) != (as_text(expected_portal_scope_id) or "fnd"):
        issues.append("portal_scope_id_mismatch")
    source_layout = dict(payload.get("source_layout") or {})
    source_layout_valid, source_layout_issues = validate_cts_gis_source_layout(source_layout)
    if not source_layout_valid:
        issues.extend(source_layout_issues)
    if isinstance(expected_source_layout, dict):
        expected_layout_valid, expected_layout_issues = validate_cts_gis_source_layout(expected_source_layout)
        if not expected_layout_valid:
            issues.extend(f"expected_{issue}" for issue in expected_layout_issues)
        expected_fingerprint = as_text(expected_source_layout.get("fingerprint"))
        actual_fingerprint = as_text(source_layout.get("fingerprint"))
        if expected_fingerprint and actual_fingerprint != expected_fingerprint:
            issues.append("source_fingerprint_mismatch")
    if not isinstance(payload.get("navigation_model"), dict):
        issues.append("navigation_model_missing")
    if not isinstance(payload.get("projection_model"), dict):
        issues.append("projection_model_missing")
    invariants = payload.get("invariants")
    if not isinstance(invariants, dict):
        issues.append("invariants_missing")
    elif not bool(invariants.get("valid")):
        issues.append("invariants_invalid")
    strict_invariants = payload.get("strict_invariants")
    if not isinstance(strict_invariants, dict):
        issues.append("strict_invariants_missing")
    elif not bool(strict_invariants.get("valid")):
        issues.append("strict_invariants_invalid")
        issues.extend(list(strict_invariants.get("issues") or []))
    return (not issues, issues)


def compiled_artifact_path(data_dir: str | Path | None, *, portal_scope_id: object) -> Path | None:
    root = Path(data_dir) if data_dir else None
    if root is None:
        return None
    scope_id = as_text(portal_scope_id) or "fnd"
    return root / _COMPILED_DIR / f"cts_gis.{scope_id}.compiled.json"


def read_compiled_artifact(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


_COMPILED_ARTIFACT_READ_CACHE: OrderedDict[tuple[str, int, int], dict[str, Any]] = OrderedDict()
_COMPILED_ARTIFACT_READ_CACHE_MAX = 4


def read_compiled_artifact_cached(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    cached = _COMPILED_ARTIFACT_READ_CACHE.get(key)
    if cached is not None:
        _COMPILED_ARTIFACT_READ_CACHE.move_to_end(key)
        return copy.deepcopy(cached)
    payload = read_compiled_artifact(path)
    if payload is None:
        return None
    _COMPILED_ARTIFACT_READ_CACHE[key] = copy.deepcopy(payload)
    while len(_COMPILED_ARTIFACT_READ_CACHE) > _COMPILED_ARTIFACT_READ_CACHE_MAX:
        _COMPILED_ARTIFACT_READ_CACHE.popitem(last=False)
    return payload


def evict_compiled_artifact_read_cache() -> None:
    _COMPILED_ARTIFACT_READ_CACHE.clear()


def write_compiled_artifact(path: Path | None, artifact: dict[str, Any]) -> Path | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return path


# --- admin_profile_static direct-read helpers --------------------------------
#
# The Garland tab's admin profile is the sandbox spatial root for CTS-GIS
# (Ohio, `3-2-3-17`). Its filament values and boundary geometry live in
# the Ohio source datum (`sc.<addr>.fnd.3-2-3-17.json`) but the runtime
# mediation pipeline currently can't decode Ohio's SAMRAS magnitude
# (issue documented in
# `evidence/reports/TASK-CTS-GIS-GARLAND-CASCADE-2026-05-11-phase2-fix.md`).
#
# These helpers read the filament + boundary directly from the source
# datum JSON, bypassing the mediation/decode pipeline. The result is
# baked into the compiled artifact's `admin_profile_static` field at
# compile time and read straight at request time — no decode required.

CTS_GIS_ADMIN_ROOT_DATUM_RELATIVE_PATH = (
    Path("sandbox") / "cts-gis" / "sources" / "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17.json"
)
"""Repo-relative path (under data_dir) to the Ohio admin-root source datum."""


def cts_gis_admin_root_source_path(data_dir: str | Path | None) -> Path | None:
    """Resolve the Ohio admin-root source-datum path under the given data_dir."""
    if data_dir is None:
        return None
    return Path(data_dir) / CTS_GIS_ADMIN_ROOT_DATUM_RELATIVE_PATH


def _admin_root_record(das: dict[str, Any]) -> tuple[list[Any], list[Any]] | None:
    """Return the (row, labels) tuple for the admin-root record.

    The admin-root record is identified by:
      - row[2] equals the admin-root MSN_ID (e.g. "3-2-3-17"), AND
      - labels[0] is the admin-root name (e.g. "ohio").

    Returns None if no record matches.
    """
    for value in das.values():
        if not isinstance(value, list) or len(value) < 2:
            continue
        row = value[0] if isinstance(value[0], list) else None
        labels = value[1] if isinstance(value[1], list) else None
        if row is None or labels is None or not labels:
            continue
        if as_text(labels[0]).lower() in {"ohio"} and len(row) >= 3 and as_text(row[2]) == "3-2-3-17":
            return row, labels
    return None


def _geojson_bbox(geometry: dict[str, Any]) -> list[float]:
    """Compute a [min_lon, min_lat, max_lon, max_lat] bbox for a GeoJSON geometry.

    Walks Point / LineString / Polygon / MultiPolygon coordinate trees.
    Returns an empty list if no coordinates can be extracted.
    """
    coords_xs: list[float] = []
    coords_ys: list[float] = []

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            if (
                len(node) >= 2
                and all(isinstance(item, (int, float)) for item in node[:2])
            ):
                coords_xs.append(float(node[0]))
                coords_ys.append(float(node[1]))
                return
            for child in node:
                _walk(child)

    _walk(geometry.get("coordinates"))
    if not coords_xs or not coords_ys:
        return []
    return [min(coords_xs), min(coords_ys), max(coords_xs), max(coords_ys)]


def build_admin_profile_static(source_datum: dict[str, Any]) -> dict[str, Any]:
    """Build the admin_profile_static payload from a parsed source-datum dict.

    Pure function — takes the JSON-decoded source datum, returns the
    payload that goes into the compiled artifact's `admin_profile_static`
    field. No I/O, no mediation, no decode.

    Shape: {node_id, label, capital_msn_id, fields[], geospatial_projection}

    The geospatial_projection conforms to the full
    `_real_geospatial_projection` contract used by the interface-panel
    renderer (`v2_portal_interface_panel_renderers.js:renderGeospatialStage`).
    It must include `has_real_projection: True` and per-feature entries
    in `features[]` (each with `feature_id`, `label`, `node_id`,
    `geometry_type`, `selected`, plus empty `shell_request` / `action`
    stubs) — otherwise the renderer treats it as an empty placeholder
    and paints "No projected geometry is available".
    """
    das = source_datum.get("datum_addressing_abstraction_space") or {}
    record = _admin_root_record(das) if isinstance(das, dict) else None
    label = ""
    msn_id = ""
    capital_msn_id = ""
    if record is not None:
        row, labels = record
        label = as_text(labels[0]) if labels else ""
        # row layout (per Ohio source datum):
        # [self_address, "rf.3-1-2", msn_id, "rf.3-1-2", capital_msn_id, boundary_ref, count, district_ref, count]
        if len(row) >= 3:
            msn_id = as_text(row[2])
        if len(row) >= 5:
            capital_msn_id = as_text(row[4])
    # Fallback to the file's reference_geojson_node_id when the record
    # is shaped differently. Better to emit an empty profile than to
    # break the compile.
    if not msn_id:
        msn_id = as_text(source_datum.get("reference_geojson_node_id"))

    reference_geojson = source_datum.get("reference_geojson")
    raw_features = []
    if isinstance(reference_geojson, dict):
        raw_features = [
            feature for feature in (reference_geojson.get("features") or [])
            if isinstance(feature, dict)
        ]

    # Build the full renderer-contract feature payloads. Each reference-
    # geojson feature gets a synthetic `id` (= the admin-root msn_id, with
    # a per-feature suffix when multiple features exist); the first
    # feature is marked `selected: True` so the renderer has a focus
    # target. shell_request and action are empty dicts — the admin
    # profile's geospatial is not interactive at this layer.
    feature_entries: list[dict[str, Any]] = []
    feature_collection_features: list[dict[str, Any]] = []
    all_bbox_xs: list[float] = []
    all_bbox_ys: list[float] = []
    for index, feature in enumerate(raw_features):
        geometry = dict(feature.get("geometry") or {})
        properties = dict(feature.get("properties") or {})
        feature_id_suffix = "" if len(raw_features) == 1 else f"-{index + 1}"
        feature_id = as_text(feature.get("id")) or f"{msn_id}{feature_id_suffix}" or f"feature-{index + 1}"
        feature_bbox = _geojson_bbox(geometry) if isinstance(geometry, dict) else []
        if feature_bbox:
            all_bbox_xs.extend([feature_bbox[0], feature_bbox[2]])
            all_bbox_ys.extend([feature_bbox[1], feature_bbox[3]])
        is_selected = index == 0
        feature_collection_features.append(
            {
                "type": "Feature",
                "id": feature_id,
                "geometry": copy.deepcopy(geometry),
                "properties": copy.deepcopy(properties),
            }
        )
        feature_label = (
            as_text(properties.get("name"))
            or as_text(properties.get("profile_label"))
            or label
            or feature_id
        )
        feature_entries.append(
            {
                "feature_id": feature_id,
                "label": feature_label,
                "node_id": msn_id,
                "geometry_type": as_text(geometry.get("type")) or "Polygon",
                "selected": is_selected,
                "shell_request": {},
                "action": {},
            }
        )
    collection_bbox = (
        [min(all_bbox_xs), min(all_bbox_ys), max(all_bbox_xs), max(all_bbox_ys)]
        if all_bbox_xs and all_bbox_ys
        else []
    )
    selected_feature_id = feature_entries[0]["feature_id"] if feature_entries else ""
    selected_geometry_type = feature_entries[0]["geometry_type"] if feature_entries else ""
    has_real_projection = bool(feature_entries)

    geospatial_projection: dict[str, Any] = {
        "title": "Geospatial Projection",
        "data_source": "cts_gis_admin_root_reference_geojson",
        "projection_source": "reference_geojson" if has_real_projection else "none",
        "projection_state": "projectable" if has_real_projection else "awaiting_real_projection",
        "feature_count": len(feature_entries),
        "render_feature_count": len(feature_entries),
        "render_row_count": 0,
        "decode_summary": {
            "reference_binding_count": len(feature_entries),
            "decoded_coordinate_count": len(feature_entries),
            "failed_token_count": 0,
        },
        "projection_health": {
            "state": "ok" if has_real_projection else "empty",
            "reason_codes": [],
        },
        "fallback_reason_codes": [],
        "warnings": [],
        "supporting_document_name": "",
        "projection_document_name": "",
        "selected_feature_id": selected_feature_id,
        "selected_feature_explicit": False,
        "selected_feature_geometry_type": selected_geometry_type,
        "selected_feature_bounds": collection_bbox if has_real_projection else [],
        "focus_bounds": list(collection_bbox),
        "collection_bounds": list(collection_bbox),
        "empty_message": (
            "Projection ready."
            if has_real_projection
            else "No projected geometry is available until the active path resolves real CTS-GIS evidence."
        ),
        "has_real_projection": has_real_projection,
        "feature_collection": {
            "type": "FeatureCollection",
            "features": feature_collection_features,
            "bounds": list(collection_bbox),
        },
        "features": feature_entries,
    }

    fields = [
        {"label": "TITLE", "value": label},
        {"label": "MSN_ID", "value": msn_id},
        {"label": "CAPITAL_MSN_ID", "value": capital_msn_id},
    ]

    return {
        "node_id": msn_id,
        "label": label,
        "capital_msn_id": capital_msn_id,
        "fields": fields,
        "geospatial_projection": geospatial_projection,
    }


def read_admin_profile_static_from_source_datum(
    source_datum_path: str | Path,
) -> dict[str, Any]:
    """Read + parse the Ohio source datum and return the admin_profile_static payload.

    Raises FileNotFoundError if the path is missing. Raises json.JSONDecodeError
    on a malformed file. Returns an empty dict if the file decodes but
    contains no admin-root record (caller decides how to react).
    """
    path = Path(source_datum_path)
    with path.open("r", encoding="utf-8") as fh:
        source_datum = json.load(fh)
    if not isinstance(source_datum, dict):
        return {}
    return build_admin_profile_static(source_datum)


__all__ = [
    "CTS_GIS_ADMIN_ROOT_DATUM_RELATIVE_PATH",
    "build_admin_profile_static",
    "build_compiled_artifact",
    "build_cts_gis_source_layout_summary",
    "compiled_artifact_path",
    "cts_gis_admin_root_source_path",
    "cts_gis_source_root",
    "evict_compiled_artifact_read_cache",
    "read_admin_profile_static_from_source_datum",
    "read_compiled_artifact",
    "read_compiled_artifact_cached",
    "validate_cts_gis_source_layout",
    "validate_compiled_artifact",
    "write_compiled_artifact",
]
