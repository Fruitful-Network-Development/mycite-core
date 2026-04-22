from __future__ import annotations

from datetime import datetime, timezone
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


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _projection_model_from_service(service_surface: dict[str, Any]) -> dict[str, Any]:
    map_projection = dict(service_surface.get("map_projection") or {})
    feature_collection = dict(map_projection.get("feature_collection") or {})
    selected_feature = dict(map_projection.get("selected_feature") or {})
    attention_profile = dict(service_surface.get("attention_profile") or {})
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


def _namespace_roots(navigation_model: dict[str, Any]) -> list[str]:
    roots: set[str] = set()
    for entry in list(navigation_model.get("active_path") or []):
        node_id = as_text((entry or {}).get("node_id"))
        if node_id and "-" in node_id:
            roots.add(node_id.split("-", 1)[0])
        elif node_id:
            roots.add(node_id)
    for dropdown in list(navigation_model.get("dropdowns") or []):
        for option in list((dropdown or {}).get("options") or []):
            node_id = as_text((option or {}).get("node_id"))
            if not node_id:
                continue
            if "-" in node_id:
                roots.add(node_id.split("-", 1)[0])
            else:
                roots.add(node_id)
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
    build_mode: str = CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
) -> dict[str, Any]:
    navigation_model = _navigation_model_from_canvas(navigation_canvas)
    projection_model = _projection_model_from_service(service_surface)
    invariants = _invariants(navigation_model=navigation_model, source_evidence=source_evidence)
    strict_invariants = _strict_invariants(navigation_model=navigation_model, source_evidence=source_evidence)
    return {
        "schema": CTS_GIS_COMPILED_ARTIFACT_SCHEMA,
        "artifact_version": "1",
        "generated_at": _utc_timestamp(),
        "portal_scope_id": as_text(portal_scope_id) or "fnd",
        "build_mode": as_text(build_mode) or CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC,
        "default_runtime_mode": CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT,
        "default_tool_state": dict(default_tool_state or {}),
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


def validate_compiled_artifact(artifact: dict[str, Any] | None) -> tuple[bool, list[str]]:
    payload = artifact if isinstance(artifact, dict) else {}
    issues: list[str] = []
    if as_text(payload.get("schema")) != CTS_GIS_COMPILED_ARTIFACT_SCHEMA:
        issues.append("invalid_schema")
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


def write_compiled_artifact(path: Path | None, artifact: dict[str, Any]) -> Path | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = [
    "build_compiled_artifact",
    "compiled_artifact_path",
    "read_compiled_artifact",
    "validate_compiled_artifact",
    "write_compiled_artifact",
]
