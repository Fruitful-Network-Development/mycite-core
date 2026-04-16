"""CTS-GIS phase-A compatibility helpers for legacy `maps` inputs.

This module centralizes CTS-GIS alias handling for v2.5.3.x soft migration.
Phase B (v2.5.4) removes legacy `maps` compatibility.
"""

from __future__ import annotations

from fnmatch import fnmatch

CTS_GIS_CANONICAL_TOOL_PUBLIC_ID = "cts_gis"
CTS_GIS_CANONICAL_TOOL_SLUG = "cts-gis"
CTS_GIS_LEGACY_TOOL_PUBLIC_ID = "maps"
CTS_GIS_LEGACY_TOOL_SLUG = "maps"
CTS_GIS_LEGACY_WARNING_CODE = "cts_gis.legacy_maps_alias_consumed"

CTS_GIS_CANONICAL_ANCHOR_PATTERNS = (
    "tool.*.cts-gis.json",
    "tool.*.cts_gis.json",
)
CTS_GIS_LEGACY_ANCHOR_PATTERNS = (
    "tool.*.maps.json",
    "tool.maps.json",
)
CTS_GIS_PHASE_A_BROAD_ANCHOR_FALLBACK = (
    "tool*.json",
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def canonicalize_cts_gis_tool_public_id(value: object) -> str:
    token = _as_text(value).lower()
    if token in {
        CTS_GIS_CANONICAL_TOOL_PUBLIC_ID,
        CTS_GIS_CANONICAL_TOOL_SLUG,
        CTS_GIS_LEGACY_TOOL_PUBLIC_ID,
        CTS_GIS_LEGACY_TOOL_SLUG,
    }:
        return CTS_GIS_CANONICAL_TOOL_PUBLIC_ID
    return token


def is_cts_gis_legacy_tool_public_id(value: object) -> bool:
    return _as_text(value).lower() == CTS_GIS_LEGACY_TOOL_PUBLIC_ID


def is_cts_gis_legacy_tool_slug(value: object) -> bool:
    return _as_text(value).lower() == CTS_GIS_LEGACY_TOOL_SLUG


def cts_gis_tool_slug_candidates_phase_a() -> tuple[str, ...]:
    return (
        CTS_GIS_CANONICAL_TOOL_SLUG,
        CTS_GIS_LEGACY_TOOL_SLUG,
    )


def canonicalize_cts_gis_sandbox_document_id(value: object) -> str:
    token = _as_text(value)
    if not token:
        return ""
    if token.startswith("sandbox:maps:"):
        return "sandbox:cts_gis:" + token[len("sandbox:maps:") :]
    return token


def is_cts_gis_legacy_sandbox_document_id(value: object) -> bool:
    token = _as_text(value)
    return token.startswith("sandbox:maps:")


def cts_gis_sandbox_document_id_aliases(value: object) -> tuple[str, ...]:
    token = _as_text(value)
    if not token:
        return ()
    if token.startswith("sandbox:cts_gis:"):
        return (token, "sandbox:maps:" + token[len("sandbox:cts_gis:") :])
    if token.startswith("sandbox:maps:"):
        return ("sandbox:cts_gis:" + token[len("sandbox:maps:") :], token)
    return (token,)


def matches_cts_gis_sandbox_document_id(candidate: object, requested: object) -> bool:
    candidate_token = _as_text(candidate)
    if not candidate_token:
        return False
    return candidate_token in cts_gis_sandbox_document_id_aliases(requested)


def cts_gis_anchor_patterns_phase_a() -> tuple[str, ...]:
    return (
        *CTS_GIS_CANONICAL_ANCHOR_PATTERNS,
        *CTS_GIS_LEGACY_ANCHOR_PATTERNS,
        *CTS_GIS_PHASE_A_BROAD_ANCHOR_FALLBACK,
    )


def is_cts_gis_legacy_anchor_filename(value: object) -> bool:
    token = _as_text(value)
    if not token:
        return False
    return any(fnmatch(token, pattern) for pattern in CTS_GIS_LEGACY_ANCHOR_PATTERNS)


def is_cts_gis_canonical_anchor_filename(value: object) -> bool:
    token = _as_text(value)
    if not token:
        return False
    return any(fnmatch(token, pattern) for pattern in CTS_GIS_CANONICAL_ANCHOR_PATTERNS)


__all__ = [
    "CTS_GIS_CANONICAL_ANCHOR_PATTERNS",
    "CTS_GIS_CANONICAL_TOOL_PUBLIC_ID",
    "CTS_GIS_CANONICAL_TOOL_SLUG",
    "CTS_GIS_LEGACY_ANCHOR_PATTERNS",
    "CTS_GIS_LEGACY_TOOL_PUBLIC_ID",
    "CTS_GIS_LEGACY_TOOL_SLUG",
    "CTS_GIS_LEGACY_WARNING_CODE",
    "CTS_GIS_PHASE_A_BROAD_ANCHOR_FALLBACK",
    "canonicalize_cts_gis_sandbox_document_id",
    "canonicalize_cts_gis_tool_public_id",
    "cts_gis_anchor_patterns_phase_a",
    "cts_gis_sandbox_document_id_aliases",
    "cts_gis_tool_slug_candidates_phase_a",
    "is_cts_gis_canonical_anchor_filename",
    "is_cts_gis_legacy_anchor_filename",
    "is_cts_gis_legacy_sandbox_document_id",
    "is_cts_gis_legacy_tool_public_id",
    "is_cts_gis_legacy_tool_slug",
    "matches_cts_gis_sandbox_document_id",
]
