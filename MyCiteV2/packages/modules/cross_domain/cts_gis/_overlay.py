"""Precinct overlay, district grouping, and timeframe logic for CTS-GIS."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    DEFAULT_TIME_DIRECTIVE as _DEFAULT_TIME_DIRECTIVE,
    as_text as _as_text,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis._utils import (
    _address_tuple,
    _profile_sort_key,
)
from MyCiteV2.packages.modules.domains.datum_recognition import DatumRecognitionDocument


def _precinct_profile_matches_attention(*, precinct_node_id: str, attention_node_id: str) -> bool:
    precinct_parts = _address_tuple(precinct_node_id)
    attention_parts = _address_tuple(attention_node_id)
    # Precinct cohort addressing convention: 247-<state>-<county>-<precinct...>
    if len(precinct_parts) < 4 or not attention_parts:
        return False
    if precinct_parts[0] != 247:
        return False
    # state attention: 3-2-3-<state>
    if len(attention_parts) == 4 and tuple(attention_parts[:3]) == (3, 2, 3):
        return precinct_parts[1] == attention_parts[3]
    # county attention: 3-2-3-<state>-<county>
    if len(attention_parts) == 5 and tuple(attention_parts[:3]) == (3, 2, 3):
        return precinct_parts[1] == attention_parts[3] and precinct_parts[2] == attention_parts[4]
    return False


def _matching_precinct_profiles(
    *,
    profile_index: dict[str, dict[str, Any]],
    attention_node_id: str,
    exclude_node_ids: set[str],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for node_id, profile in profile_index.items():
        node_id_text = _as_text(node_id)
        if (
            not node_id_text
            or node_id_text in exclude_node_ids
            or not _precinct_profile_matches_attention(
                precinct_node_id=node_id_text,
                attention_node_id=attention_node_id,
            )
        ):
            continue
        if int(profile.get("feature_count") or 0) <= 0:
            continue
        matches.append(profile)
    return sorted(matches, key=_profile_sort_key)


def _precinct_overlay_attention_supported(attention_node_id: str) -> bool:
    attention_parts = _address_tuple(attention_node_id)
    return bool(attention_parts) and tuple(attention_parts[:3]) == (3, 2, 3) and len(attention_parts) in {4, 5}


def _precinct_overlay_gate_failures(
    *,
    overlay_requested: bool,
    attention_node_id: str,
    time_context_payload: dict[str, Any],
    chronological_anchor_present: bool,
    district_timeframe_match: bool,
) -> list[str]:
    if not overlay_requested:
        return []
    failures: list[str] = []
    if not attention_node_id:
        failures.append("attention_node_missing")
    elif not _precinct_overlay_attention_supported(attention_node_id):
        failures.append("attention_lineage_unsupported")
    if not bool(time_context_payload.get("active")):
        failures.append("time_context_inactive")
        return failures
    if not chronological_anchor_present:
        failures.append("chronological_anchor_missing")
    if not district_timeframe_match:
        failures.append("district_timeframe_mismatch")
    return failures


def _district_timeframe_tokens(document_bundle: dict[str, Any]) -> list[str]:
    tokens: set[str] = set()
    for row in list(document_bundle.get("row_views") or []):
        for label in list(row.get("labels") or []):
            token = _as_text(label).lower()
            if not token:
                continue
            if any(marker in token for marker in ("time_frame", "district", "present", "precinct_group")):
                tokens.add(token)
    return sorted(tokens)


def _time_context_in_timeframe(*, time_token: str, timeframe_tokens: list[str]) -> bool:
    token = _as_text(time_token).lower()
    if not token or not timeframe_tokens:
        return False
    if token in timeframe_tokens:
        return True
    if token in {"today", _as_text(_DEFAULT_TIME_DIRECTIVE).lower()}:
        return any("present" in item for item in timeframe_tokens)
    for timeframe in timeframe_tokens:
        parts = [part for part in timeframe.replace("-", "_").split("_") if part]
        if token in parts:
            return True
    return False


def _document_district_timeframe_tokens(document: DatumRecognitionDocument) -> list[str]:
    tokens: set[str] = set()
    for row in list(getattr(document, "rows", ()) or []):
        raw = getattr(row, "raw", None)
        labels: list[object] = []
        if isinstance(raw, list) and len(raw) > 1:
            labels = list(raw[1]) if isinstance(raw[1], (list, tuple)) else [raw[1]]
        for label in labels:
            token = _as_text(label).lower()
            if not token:
                continue
            if any(marker in token for marker in ("time_frame", "district", "present", "precinct_group")):
                tokens.add(token)
    return sorted(tokens)


def _precinct_overlay_scope_node_id(attention_node_id: str) -> str:
    attention_parts = _address_tuple(attention_node_id)
    if len(attention_parts) == 4 and tuple(attention_parts[:3]) == (3, 2, 3):
        return f"247-{attention_parts[3]}"
    if len(attention_parts) == 5 and tuple(attention_parts[:3]) == (3, 2, 3):
        return f"247-{attention_parts[3]}-{attention_parts[4]}"
    return ""


def _district_collection_label(timeframe_token: object) -> str:
    token = _as_text(timeframe_token).lower().replace("-", "_")
    if not token:
        return "District precinct collection"
    parts = [part for part in token.split("_") if part]
    district_number = ""
    district_index = -1
    district_consumed = False
    for index, part in enumerate(parts):
        if part == "district" and index + 1 < len(parts) and parts[index + 1].isdigit():
            district_index = index
            district_number = parts[index + 1]
            district_consumed = True
            break
        if part.startswith("district") and part[len("district"):].isdigit():
            district_index = index
            district_number = part[len("district"):]
            district_consumed = False
            break
    timeframe_parts: list[str] = []
    for index, part in enumerate(parts):
        if index == district_index:
            continue
        if district_consumed and district_index >= 0 and index == district_index + 1:
            continue
        if part in {"time", "frame"}:
            continue
        timeframe_parts.append(part)
    label_parts: list[str] = []
    if district_number:
        label_parts.append(f"District {district_number}")
    if timeframe_parts:
        label_parts.append(" ".join(part.capitalize() if not part.isdigit() else part for part in timeframe_parts))
    return " · ".join(label_parts) or _as_text(timeframe_token)


def _district_precinct_collection_summaries(
    *,
    attention_node_id: str,
    time_context_payload: dict[str, Any],
    timeframe_tokens: list[str],
    overlay_requested: bool,
    overlay_active: bool,
    precinct_profiles: list[dict[str, Any]],
    gate_failures: list[str],
    chronological_anchor_present: bool,
) -> list[dict[str, Any]]:
    unique_timeframes = sorted({_as_text(token).lower() for token in timeframe_tokens if _as_text(token)})
    time_token = _as_text(time_context_payload.get("value_token"))
    scope_node_id = _precinct_overlay_scope_node_id(attention_node_id)
    supported_attention_lineage = _precinct_overlay_attention_supported(attention_node_id)
    scope_kind = (
        "state" if len(_address_tuple(attention_node_id)) == 4
        else "county" if len(_address_tuple(attention_node_id)) == 5
        else ""
    )
    if not unique_timeframes and not time_token:
        return []
    if not unique_timeframes and time_token:
        unique_timeframes = [time_token.lower()]
    member_node_ids = [
        _as_text(profile.get("node_id"))
        for profile in precinct_profiles
        if _as_text(profile.get("node_id"))
    ]
    member_labels = [
        _as_text(profile.get("profile_label")) or _as_text(profile.get("node_id"))
        for profile in precinct_profiles
        if _as_text(profile.get("profile_label")) or _as_text(profile.get("node_id"))
    ]
    collection_summaries: list[dict[str, Any]] = []
    for timeframe_token in unique_timeframes:
        timeframe_match = _time_context_in_timeframe(
            time_token=time_token,
            timeframe_tokens=[timeframe_token],
        )
        collection_overlay_active = bool(overlay_active and timeframe_match)
        if collection_overlay_active:
            summary_state = "loaded"
        elif overlay_requested and gate_failures:
            summary_state = "blocked"
        else:
            summary_state = "deferred"
        collection_summaries.append(
            {
                "collection_id": timeframe_token or "district_precinct_collection",
                "label": _district_collection_label(timeframe_token),
                "timeframe_token": timeframe_token,
                "time_context_active": bool(time_context_payload.get("active")),
                "timeframe_match": timeframe_match,
                "overlay_requested": bool(overlay_requested),
                "overlay_active": collection_overlay_active,
                "overlay_toggle_available": bool(
                    supported_attention_lineage
                    and chronological_anchor_present
                    and time_context_payload.get("active")
                ),
                "scope_node_id": scope_node_id,
                "scope_kind": scope_kind,
                "precinct_count": len(member_node_ids) if collection_overlay_active else 0,
                "precinct_count_known": bool(collection_overlay_active),
                "member_node_ids": list(member_node_ids) if collection_overlay_active else [],
                "member_labels": list(member_labels) if collection_overlay_active else [],
                "gate_failures": list(gate_failures),
                "summary_state": summary_state,
            }
        )
    return collection_summaries
