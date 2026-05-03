from __future__ import annotations

import json
from typing import Any

from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    BRANCH_INTENTION_PREFIX as _BRANCH_INTENTION_PREFIX,
    CTS_GIS_CANONICAL_DOCUMENT_PREFIX as _CTS_GIS_CANONICAL_DOCUMENT_PREFIX,
    CTS_GIS_CANONICAL_TOOL_PUBLIC_ID as _CTS_GIS_CANONICAL_TOOL_PUBLIC_ID,
    DEFAULT_ATTENTION_NODE_ID as _DEFAULT_ATTENTION_NODE_ID,
    DEFAULT_ATTENTION_PROFILE_LABEL as _DEFAULT_ATTENTION_PROFILE_LABEL,
    DEFAULT_INTENTION_TOKEN as _DEFAULT_INTENTION_TOKEN,
    DEFAULT_PROJECTION_DOCUMENT_SUFFIX as _DEFAULT_PROJECTION_DOCUMENT_SUFFIX,
    DEFAULT_SUPPORTING_DOCUMENT_NAME as _DEFAULT_SUPPORTING_DOCUMENT_NAME,
    DEFAULT_TIME_DIRECTIVE as _DEFAULT_TIME_DIRECTIVE,
    LEGACY_SELF_INTENTION_TOKEN as _LEGACY_SELF_INTENTION_TOKEN,
    as_text as _as_text,
    canonical_service_intention_token,
    children_intention_token as _contract_children_intention_token,
    descendants_intention_token as _contract_descendants_intention_token,
)
from MyCiteV2.packages.modules.domains.datum_recognition import (
    DatumRecognitionDocument,
    DatumRecognitionRow,
    DatumWorkbenchService,
)
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentPort
from MyCiteV2.packages.modules.cross_domain.cts_gis._utils import (
    _address_is_descendant,
    _address_tuple,
    _as_lower,
    _first_non_empty,
    _node_depth,
    _parent_node_id,
    _profile_sort_key,
    _sorted_addresses,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis._overlay import (
    _district_collection_label,
    _district_precinct_collection_summaries,
    _district_timeframe_tokens,
    _document_district_timeframe_tokens,
    _matching_precinct_profiles,
    _precinct_overlay_attention_supported,
    _precinct_overlay_gate_failures,
    _precinct_overlay_scope_node_id,
    _precinct_profile_matches_attention,
    _time_context_in_timeframe,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis._projection import (
    _binding_family,
    _binding_overlay,
    _build_document_projection,
    _build_cts_gis_coordinate_authority,
    _coordinate_projection,
    _coordinate_ring,
    _dedupe_texts,
    _feature_bounds,
    _feature_bounds_from_geometry,
    _feature_from_geometry,
    _feature_from_row,
    _geometry_from_row_address,
    _geometry_points,
    _geometry_polygons,
    _linked_row_addresses,
    _node_guardrail_envelope,
    _normalized_reference_ring,
    _prefer_reference_geojson_projection,
    _primary_samras_node_id,
    _projection_summary_for_row_addresses,
    _reachable_row_addresses,
    _reference_geojson_profile_features,
    _row_declared_coordinate_count,
    _row_family,
    _row_label_text,
    _row_polygon_groups,
    _row_projection,
    _safe_coordinate_pair,
    _semantic_projection_assessment,
)

_VALID_OVERLAY_MODES = frozenset({"auto", "raw_only"})


def _is_cts_gis_document_id(value: object) -> bool:
    return _as_text(value).startswith(_CTS_GIS_CANONICAL_DOCUMENT_PREFIX)


def _matches_cts_gis_document_id(candidate: object, requested: object) -> bool:
    candidate_token = _as_text(candidate)
    requested_token = _as_text(requested)
    if not candidate_token or not requested_token:
        return False
    return candidate_token == requested_token


def _matches_attention_profile_document(document: DatumRecognitionDocument, attention_node_id: object) -> bool:
    node_id = _as_text(attention_node_id)
    if not node_id:
        return False
    document_name = _as_text(getattr(document, "document_name", ""))
    if document_name.endswith(f".{node_id}.json"):
        return True
    document_id = _as_text(getattr(document, "document_id", ""))
    return document_id.endswith(f".{node_id}.json")


def _anchor_row_tokens(raw: Any) -> list[Any]:
    if not isinstance(raw, list) or not raw:
        return []
    if isinstance(raw[0], list):
        return list(raw[0])
    return list(raw)


def _normalize_time_context(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        token = _first_non_empty(
            (value.get("value_token"), value.get("value"), value.get("token"), value.get("node_id"))
        )
        family = _as_text(value.get("family"))
        return {
            "active": bool(token),
            "value_token": token,
            "family": family,
            "raw": dict(value),
        }
    token = _as_text(value)
    return {
        "active": bool(token),
        "value_token": token,
        "family": "",
        "raw": token,
    }


def _anchor_context_metadata(document: Any) -> dict[str, Any]:
    anchor_rows = list(getattr(document, "anchor_rows", ()) or [])
    row_map: dict[str, list[Any]] = {}
    for row in anchor_rows:
        address = _as_text(getattr(row, "datum_address", ""))
        if not address:
            continue
        row_map[address] = _anchor_row_tokens(getattr(row, "raw", None))

    ruiqi_bits = _as_text((row_map.get("1-1-4") or [None, None, ""])[2] if len(row_map.get("1-1-4") or []) > 2 else "")
    chronological_bits = _as_text(
        (row_map.get("1-1-5") or [None, None, ""])[2] if len(row_map.get("1-1-5") or []) > 2 else ""
    )
    return {
        "samras_ruiqi": {
            "space_row": "1-1-4" if "1-1-4" in row_map else "",
            "space_binding_row": "2-0-3" if "2-0-3" in row_map else "",
            "babelette_row": "3-1-4" if "3-1-4" in row_map else "",
            "bit_length": len(ruiqi_bits),
            "present": bool(ruiqi_bits),
        },
        "chronological_hops": {
            "space_row": "1-1-5" if "1-1-5" in row_map else "",
            "space_binding_row": "2-0-4" if "2-0-4" in row_map else "",
            "babelette_row": "3-1-5" if "3-1-5" in row_map else "",
            "bit_length": len(chronological_bits),
            "present": bool(chronological_bits),
        },
    }


def _descendants_intention_token(attention_node_id: str) -> str:
    return _contract_descendants_intention_token(attention_node_id)


def _children_intention_token(attention_node_id: str) -> str:
    return _contract_children_intention_token(attention_node_id)


def _structural_child_node_ids(
    document_bundle: dict[str, Any],
    attention_node_id: str,
    *,
    descendants_depth_1_or_2: list[dict[str, Any]] | None = None,
) -> list[str]:
    if not attention_node_id:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for node_id in list((document_bundle.get("children_by_parent") or {}).get(attention_node_id, [])):
        node_id_text = _as_text(node_id)
        if not node_id_text or node_id_text in seen:
            continue
        seen.add(node_id_text)
        out.append(node_id_text)
    depth = _node_depth(attention_node_id)
    descendants = list(
        descendants_depth_1_or_2
        if descendants_depth_1_or_2 is not None
        else _descendant_profiles(
            document_bundle,
            attention_node_id=attention_node_id,
            min_extra_segments=1,
            max_extra_segments=2,
        )
    )
    for profile in descendants:
        node_id_text = _as_text(profile.get("node_id"))
        if not _address_is_descendant(
            node_id_text,
            root_node_id=attention_node_id,
            min_extra_segments=1,
            max_extra_segments=2,
        ):
            continue
        child_node_id = "-".join(node_id_text.split("-")[: depth + 1])
        if not child_node_id or child_node_id in seen:
            continue
        seen.add(child_node_id)
        out.append(child_node_id)
    return out


def _normalize_overlay_mode(value: object) -> str:
    mode = _as_lower(value) or "auto"
    if mode not in _VALID_OVERLAY_MODES:
        raise ValueError("cts_gis.overlay_mode must be auto or raw_only")
    return mode


def _normalize_raw_underlay_visible(value: object) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError("cts_gis.raw_underlay_visible must be a bool when provided")
    return value


def _descendant_profiles(
    document_bundle: dict[str, Any],
    *,
    attention_node_id: str,
    min_extra_segments: int,
    max_extra_segments: int,
) -> list[dict[str, Any]]:
    profiles = list((document_bundle.get("profile_index") or {}).values())
    return sorted(
        [
            profile
            for profile in profiles
            if _address_is_descendant(
                _as_text(profile.get("node_id")),
                root_node_id=attention_node_id,
                min_extra_segments=min_extra_segments,
                max_extra_segments=max_extra_segments,
            )
        ],
        key=_profile_sort_key,
    )


def _profile_public_summary(profile: dict[str, Any], *, relation: str = "", selected: bool = False) -> dict[str, Any]:
    return {
        "node_id": _as_text(profile.get("node_id")),
        "profile_label": _as_text(profile.get("profile_label")) or _as_text(profile.get("node_id")),
        "title_display": _as_text(profile.get("title_display")),
        "row_address": _as_text(profile.get("row_address")),
        "parent_node_id": _as_text(profile.get("parent_node_id")),
        "depth": int(profile.get("depth") or 0),
        "child_count": int(profile.get("child_count") or 0),
        "feature_count": int(profile.get("feature_count") or 0),
        "labels": list(profile.get("labels") or []),
        "document_id": _as_text(profile.get("document_id")),
        "diagnostic_states": list(profile.get("diagnostic_states") or []),
        "has_geometry": bool(profile.get("feature_count")),
        "relation": relation,
        "selected": bool(selected),
    }


def _placeholder_profile_summary(node_id: str, *, relation: str = "", profile_label: str = "") -> dict[str, Any]:
    return {
        "node_id": _as_text(node_id),
        "profile_label": _as_text(profile_label) or _as_text(node_id) or "profile",
        "title_display": "",
        "row_address": "",
        "parent_node_id": _parent_node_id(node_id),
        "depth": _node_depth(node_id),
        "child_count": 0,
        "feature_count": 0,
        "labels": [],
        "document_id": "",
        "diagnostic_states": [],
        "has_geometry": False,
        "relation": relation,
        "selected": False,
        "placeholder": True,
    }


def _canonical_placeholder_profile_summary(node_id: str, *, relation: str = "") -> dict[str, Any]:
    return _placeholder_profile_summary(
        node_id,
        relation=relation,
        profile_label=_DEFAULT_ATTENTION_PROFILE_LABEL if _as_text(node_id) == _DEFAULT_ATTENTION_NODE_ID else "",
    )


def _preferred_default_projection_document(
    documents: list[DatumRecognitionDocument],
) -> DatumRecognitionDocument | None:
    for document in documents:
        if _as_text(document.document_name).endswith(_DEFAULT_PROJECTION_DOCUMENT_SUFFIX):
            return document
    return None


def _document_node_id(document: DatumRecognitionDocument) -> str:
    candidates = [
        _as_text(getattr(document, "document_name", "")),
        _as_text(getattr(document, "document_id", "")),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        stem = candidate[:-5] if candidate.endswith(".json") else candidate
        tail = stem.rsplit(".", 1)[-1]
        if _address_tuple(tail):
            return tail
    return ""


def _document_projection_cache_key(document: DatumRecognitionDocument, *, overlay_mode: str) -> tuple[Any, ...]:
    metadata = dict(getattr(document, "document_metadata", {}) or {})
    filesystem_cache = dict(metadata.get("__filesystem_cache__") or {})
    source_signature = dict(filesystem_cache.get("source_signature") or {})
    anchor_signature = dict(filesystem_cache.get("anchor_signature") or {})
    row_count = len(tuple(getattr(document, "rows", ()) or ()))
    anchor_row_count = len(tuple(getattr(document, "anchor_rows", ()) or ()))
    metadata_fingerprint = ""
    if not source_signature and not anchor_signature:
        normalized_metadata = {
            key: value
            for key, value in metadata.items()
            if key != "__filesystem_cache__"
        }
        metadata_fingerprint = json.dumps(normalized_metadata, sort_keys=True, default=str)
    return (
        _as_text(getattr(document, "document_id", "")),
        _as_text(getattr(document, "relative_path", "")),
        _as_text(overlay_mode),
        metadata_fingerprint,
        bool(source_signature.get("exists")),
        int(source_signature.get("mtime_ns") or 0),
        int(source_signature.get("size") or 0),
        bool(anchor_signature.get("exists")),
        int(anchor_signature.get("mtime_ns") or 0),
        int(anchor_signature.get("size") or 0),
        row_count,
        anchor_row_count,
    )


def _is_descendants_intention_token(token: str, *, attention_node_id: str) -> bool:
    if not token:
        return False
    return token == _descendants_intention_token(attention_node_id) or token == "descendants_depth_1_or_2"


def _is_children_intention_token(token: str, *, attention_node_id: str) -> bool:
    if not token:
        return False
    return token == _children_intention_token(attention_node_id) or token == "children"


def _scoped_projection_documents(
    *,
    documents: list[DatumRecognitionDocument],
    target_document: DatumRecognitionDocument | None,
    requested_attention_node_id: str,
    requested_intention_token: str,
    time_context_active: bool,
    precinct_district_overlay_enabled: bool,
) -> list[DatumRecognitionDocument]:
    if not documents:
        return []
    if (
        not _as_text(requested_attention_node_id)
        and not _as_text(requested_intention_token)
        and not bool(time_context_active)
    ):
        return list(documents)
    attention_node_id = _as_text(requested_attention_node_id)
    intention_token = _as_text(requested_intention_token)
    if not attention_node_id and target_document is not None:
        attention_node_id = _document_node_id(target_document)
    if not attention_node_id:
        return [target_document] if target_document is not None else [documents[0]]

    descendant_intention = _is_descendants_intention_token(intention_token, attention_node_id=attention_node_id)
    children_intention = _is_children_intention_token(intention_token, attention_node_id=attention_node_id)
    branch_node_id = ""
    if intention_token.startswith(_BRANCH_INTENTION_PREFIX):
        branch_node_id = _as_text(intention_token[len(_BRANCH_INTENTION_PREFIX) :])

    out: list[DatumRecognitionDocument] = []
    seen_ids: set[str] = set()

    def _include(document: DatumRecognitionDocument) -> None:
        doc_id = _as_text(getattr(document, "document_id", ""))
        if not doc_id or doc_id in seen_ids:
            return
        seen_ids.add(doc_id)
        out.append(document)

    if target_document is not None:
        _include(target_document)
    for document in documents:
        node_id = _document_node_id(document)
        if not node_id:
            relative_path = _as_text(getattr(document, "relative_path", ""))
            if (
                precinct_district_overlay_enabled
                and time_context_active
                and "/precincts/" in relative_path.replace("\\", "/")
            ):
                _include(document)
                continue
            if intention_token and intention_token not in {"self", _LEGACY_SELF_INTENTION_TOKEN}:
                _include(document)
            continue
        include = node_id == attention_node_id
        if branch_node_id and node_id == branch_node_id:
            include = True
        if children_intention:
            include = include or _address_is_descendant(
                node_id,
                root_node_id=attention_node_id,
                min_extra_segments=1,
                max_extra_segments=1,
            )
        if descendant_intention:
            include = include or _address_is_descendant(
                node_id,
                root_node_id=attention_node_id,
                min_extra_segments=1,
                max_extra_segments=2,
            )
        if (
            precinct_district_overlay_enabled
            and time_context_active
            and _precinct_profile_matches_attention(
                precinct_node_id=node_id,
                attention_node_id=attention_node_id,
            )
        ):
            include = True
        if include:
            _include(document)
    if out:
        return out
    return [target_document] if target_document is not None else [documents[0]]


def _build_navigation_bundle(documents: list[dict[str, Any]]) -> dict[str, Any]:
    if not documents:
        return {
            "profile_index": {},
            "children_by_parent": {},
            "feature_index": {},
            "feature_profile_index": {},
            "default_attention_node_id": "",
        }

    if len(documents) == 1:
        document_bundle = documents[0]
        return {
            "profile_index": dict(document_bundle.get("profile_index") or {}),
            "children_by_parent": {
                key: list(value)
                for key, value in dict(document_bundle.get("children_by_parent") or {}).items()
            },
            "feature_index": dict(document_bundle.get("feature_index") or {}),
            "feature_profile_index": {
                key: list(value)
                for key, value in dict(document_bundle.get("feature_profile_index") or {}).items()
            },
            "default_attention_node_id": _as_text(document_bundle.get("default_attention_node_id")),
        }

    profiles_by_node: dict[str, dict[str, Any]] = {}
    feature_index: dict[str, dict[str, Any]] = {}
    feature_profile_index: dict[str, list[str]] = {}

    for document_bundle in documents:
        for feature_id, feature in dict(document_bundle.get("feature_index") or {}).items():
            feature_index[_as_text(feature_id)] = feature
        for feature_id, node_ids in dict(document_bundle.get("feature_profile_index") or {}).items():
            merged_node_ids = feature_profile_index.setdefault(_as_text(feature_id), [])
            for node_id in list(node_ids or []):
                node_id_text = _as_text(node_id)
                if node_id_text and node_id_text not in merged_node_ids:
                    merged_node_ids.append(node_id_text)
        for node_id, profile in dict(document_bundle.get("profile_index") or {}).items():
            node_id_text = _as_text(node_id)
            if not node_id_text:
                continue
            candidate = {
                **dict(profile),
                "feature_ids": list(profile.get("feature_ids") or []),
                "row_addresses": list(profile.get("row_addresses") or []),
                "bound_node_ids": list(profile.get("bound_node_ids") or []),
                "labels": list(profile.get("labels") or []),
                "diagnostic_states": list(profile.get("diagnostic_states") or []),
                "children": list(profile.get("children") or []),
            }
            existing = profiles_by_node.get(node_id_text)
            if existing is None:
                profiles_by_node[node_id_text] = candidate
                continue
            existing["feature_ids"] = _sorted_addresses(set(existing["feature_ids"]) | set(candidate["feature_ids"]))
            existing["feature_count"] = len(existing["feature_ids"])
            existing["row_addresses"] = _sorted_addresses(set(existing["row_addresses"]) | set(candidate["row_addresses"]))
            existing["bound_node_ids"] = _sorted_addresses(set(existing["bound_node_ids"]) | set(candidate["bound_node_ids"]))
            existing["labels"] = sorted(set(existing["labels"]) | set(candidate["labels"]))
            existing["diagnostic_states"] = sorted(
                set(existing["diagnostic_states"]) | set(candidate["diagnostic_states"])
            )
            if candidate["feature_count"] > existing["feature_count"] or (
                candidate["feature_count"] == existing["feature_count"]
                and candidate["depth"] < existing["depth"]
            ):
                for field in ("row_address", "profile_label", "title_display", "document_id"):
                    existing[field] = candidate[field]

    children_by_parent: dict[str, list[str]] = {}
    for node_id, profile in profiles_by_node.items():
        children_by_parent.setdefault(_as_text(profile.get("parent_node_id")), []).append(node_id)
    for node_ids in children_by_parent.values():
        node_ids.sort(key=lambda item: (_node_depth(item), item))
    for node_id, profile in profiles_by_node.items():
        profile["child_count"] = len(children_by_parent.get(node_id, []))
        profile["children"] = list(children_by_parent.get(node_id, []))

    default_attention_node_id = ""
    if _DEFAULT_ATTENTION_NODE_ID in profiles_by_node:
        default_attention_node_id = _DEFAULT_ATTENTION_NODE_ID
    elif profiles_by_node:
        default_attention_node_id = _as_text(
            sorted(profiles_by_node.values(), key=_profile_sort_key)[0].get("node_id")
        )
    return {
        "profile_index": profiles_by_node,
        "children_by_parent": children_by_parent,
        "feature_index": feature_index,
        "feature_profile_index": feature_profile_index,
        "default_attention_node_id": default_attention_node_id,
    }


def _normalize_intention_token(document_bundle: dict[str, Any], attention_node_id: str, requested: object) -> str:
    token = canonical_service_intention_token(requested, attention_node_id=attention_node_id)
    if not attention_node_id:
        if token == "self":
            return "self"
        return _DEFAULT_INTENTION_TOKEN
    children = list((document_bundle.get("children_by_parent") or {}).get(attention_node_id, []))
    descendants_depth_1_or_2 = _descendant_profiles(
        document_bundle,
        attention_node_id=attention_node_id,
        min_extra_segments=1,
        max_extra_segments=2,
    )
    structural_child_node_ids = _structural_child_node_ids(
        document_bundle,
        attention_node_id,
        descendants_depth_1_or_2=descendants_depth_1_or_2,
    )
    descendants_token = _descendants_intention_token(attention_node_id)
    children_token = _children_intention_token(attention_node_id)
    if token == "self":
        return "self"
    if token == descendants_token:
        return descendants_token if descendants_depth_1_or_2 else "self"
    if token == children_token:
        return children_token if structural_child_node_ids or children else "self"
    if token.startswith(_BRANCH_INTENTION_PREFIX):
        branch_node_id = _as_text(token[len(_BRANCH_INTENTION_PREFIX) :])
        if branch_node_id in children:
            return token
    return "self"


def _available_intentions(document_bundle: dict[str, Any], attention_node_id: str) -> list[dict[str, Any]]:
    profile_index = document_bundle.get("profile_index") or {}
    attention_profile = profile_index.get(attention_node_id)
    children = [
        profile_index[node_id]
        for node_id in list((document_bundle.get("children_by_parent") or {}).get(attention_node_id, []))
        if node_id in profile_index
    ]
    descendants_depth_1_or_2 = _descendant_profiles(
        document_bundle,
        attention_node_id=attention_node_id,
        min_extra_segments=1,
        max_extra_segments=2,
    )
    structural_child_node_ids = _structural_child_node_ids(
        document_bundle,
        attention_node_id,
        descendants_depth_1_or_2=descendants_depth_1_or_2,
    )
    out = [
        {
            "token": "self",
            "kind": "self",
            "label": "Self",
            "target_node_id": attention_node_id,
            "row_count": len((attention_profile or {}).get("row_addresses") or []),
            "feature_count": int((attention_profile or {}).get("feature_count") or 0),
            "profile_count": 1 if attention_profile is not None else 0,
        }
    ]
    if descendants_depth_1_or_2:
        out.insert(
            0,
            {
                "token": _descendants_intention_token(attention_node_id),
                "kind": "descendants_depth_1_or_2",
                "label": "Descendants depth 1 or 2",
                "target_node_id": attention_node_id,
                "row_count": sum(len(profile.get("row_addresses") or []) for profile in descendants_depth_1_or_2),
                "feature_count": sum(int(profile.get("feature_count") or 0) for profile in descendants_depth_1_or_2),
                "profile_count": len(descendants_depth_1_or_2),
            },
        )
    if structural_child_node_ids:
        out.append(
            {
                "token": _children_intention_token(attention_node_id),
                "kind": "children",
                "label": "Immediate children",
                "target_node_id": attention_node_id,
                "row_count": sum(len(child.get("row_addresses") or []) for child in children),
                "feature_count": sum(int(child.get("feature_count") or 0) for child in children),
                "profile_count": len(children),
            }
        )
    if children:
        for child in children:
            out.append(
                {
                    "token": f"{_BRANCH_INTENTION_PREFIX}{child['node_id']}",
                    "kind": "branch",
                    "label": _as_text(child.get("profile_label")) or _as_text(child.get("node_id")) or "Branch",
                    "target_node_id": _as_text(child.get("node_id")),
                    "row_count": len(child.get("row_addresses") or []),
                    "feature_count": int(child.get("feature_count") or 0),
                    "profile_count": 1,
                }
            )
    return out


def _document_lookup_by_feature_id(
    projection_bundle: dict[str, Any],
    selected_feature_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for document_bundle in list(projection_bundle.get("documents") or []):
        feature = (document_bundle.get("feature_index") or {}).get(selected_feature_id)
        if feature is not None:
            return document_bundle, feature
    return None, None


def _document_lookup_by_row_address(
    projection_bundle: dict[str, Any],
    row_address: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for document_bundle in list(projection_bundle.get("documents") or []):
        row = (document_bundle.get("row_index") or {}).get(row_address)
        if row is not None:
            return document_bundle, row
    return None, None


class CtsGisReadOnlyService:
    _DOCUMENT_PROJECTION_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
    _DOCUMENT_PROJECTION_CACHE_MAX = 512

    def __init__(self, datum_store: AuthoritativeDatumDocumentPort | None) -> None:
        self._datum_store = datum_store

    @classmethod
    def _cached_document_projection(cls, document: DatumRecognitionDocument, *, overlay_mode: str) -> dict[str, Any]:
        cache_key = _document_projection_cache_key(document, overlay_mode=overlay_mode)
        cached = cls._DOCUMENT_PROJECTION_CACHE.get(cache_key)
        if cached is not None:
            return cached
        projection = _build_document_projection(document, overlay_mode=overlay_mode)
        cls._DOCUMENT_PROJECTION_CACHE[cache_key] = projection
        if len(cls._DOCUMENT_PROJECTION_CACHE) > cls._DOCUMENT_PROJECTION_CACHE_MAX:
            cls._DOCUMENT_PROJECTION_CACHE.pop(next(iter(cls._DOCUMENT_PROJECTION_CACHE)))
        return projection

    @classmethod
    def evict_document_projection_cache(cls) -> int:
        evicted = len(cls._DOCUMENT_PROJECTION_CACHE)
        cls._DOCUMENT_PROJECTION_CACHE.clear()
        return evicted

    def read_projection_bundle(
        self,
        tenant_id: str,
        *,
        selected_document_id: object = "",
        selected_row_address: object = "",
        selected_feature_id: object = "",
        attention_document_id: object = "",
        attention_node_id: object = "",
        overlay_mode: object = "auto",
        raw_underlay_visible: object = False,
        project_all_documents: object | None = None,
        requested_intention_token: object = "",
        time_context_active: object = False,
        precinct_district_overlay_enabled: object = False,
        requested_time_token: object = "",
    ) -> dict[str, Any]:
        if self._datum_store is None:
            raise ValueError("cts_gis.datum_store is not configured")

        normalized_overlay_mode = _normalize_overlay_mode(overlay_mode)
        normalized_raw_underlay = _normalize_raw_underlay_visible(raw_underlay_visible)
        workbench = DatumWorkbenchService(self._datum_store).read_workbench(_as_text(tenant_id) or "fnd")

        cts_gis_documents = [
            document
            for document in workbench.documents
            if (
                document.source_kind == "sandbox_source"
                and _as_lower(document.tool_id) == _CTS_GIS_CANONICAL_TOOL_PUBLIC_ID
            )
        ]
        requested_document_id_raw = _as_text(attention_document_id) or _as_text(selected_document_id)
        requested_document_id = requested_document_id_raw
        requested_row_address = _as_text(selected_row_address)
        requested_feature_id = _as_text(selected_feature_id)
        requested_attention_node_id = _as_text(attention_node_id)
        requested_intention_token_text = _as_text(requested_intention_token)
        time_context_active_flag = bool(time_context_active)
        precinct_district_overlay_enabled_flag = bool(precinct_district_overlay_enabled)
        requested_time_token_text = _as_text(requested_time_token)
        if project_all_documents is None:
            project_all_documents = not requested_document_id
        project_all_documents = bool(project_all_documents)
        target_document = None
        if requested_document_id and _is_cts_gis_document_id(requested_document_id):
            for document in cts_gis_documents:
                if _matches_cts_gis_document_id(document.document_id, requested_document_id):
                    target_document = document
                    break
        if target_document is None and requested_attention_node_id:
            for document in cts_gis_documents:
                if _matches_attention_profile_document(document, requested_attention_node_id):
                    target_document = document
                    break
        if target_document is None and cts_gis_documents:
            target_document = _preferred_default_projection_document(cts_gis_documents)
        if target_document is None and cts_gis_documents:
            for document in cts_gis_documents:
                if _as_text(document.document_name) == _DEFAULT_SUPPORTING_DOCUMENT_NAME:
                    target_document = document
                    break
        if target_document is None and cts_gis_documents:
            target_document = cts_gis_documents[0]
        scope_attention_node_id = requested_attention_node_id
        if not scope_attention_node_id and target_document is not None:
            scope_attention_node_id = _document_node_id(target_document)
        scope_anchor_context = _anchor_context_metadata(target_document) if target_document is not None else {}
        scope_time_context = {
            "active": time_context_active_flag,
            "value_token": requested_time_token_text,
        }
        scope_timeframes = _document_district_timeframe_tokens(target_document) if target_document is not None else []
        precinct_scope_gate_failures = _precinct_overlay_gate_failures(
            overlay_requested=precinct_district_overlay_enabled_flag,
            attention_node_id=scope_attention_node_id,
            time_context_payload=scope_time_context,
            chronological_anchor_present=bool((scope_anchor_context.get("chronological_hops") or {}).get("present")),
            district_timeframe_match=_time_context_in_timeframe(
                time_token=requested_time_token_text,
                timeframe_tokens=scope_timeframes,
            ),
        )
        precinct_scope_active = bool(
            precinct_district_overlay_enabled_flag
            and not precinct_scope_gate_failures
        )

        document_catalog = []
        for document in cts_gis_documents:
            summary = document.to_summary_dict()
            summary.setdefault("projectable_feature_count", 0)
            summary.setdefault("projection_state", "pending")
            summary.setdefault("profile_count", 0)
            summary.setdefault("default_attention_node_id", "")
            summary["selected"] = _as_text(summary.get("document_id")) == _as_text(getattr(target_document, "document_id", ""))
            document_catalog.append(summary)

        target_documents = (
            _scoped_projection_documents(
                documents=cts_gis_documents,
                target_document=target_document,
                requested_attention_node_id=requested_attention_node_id,
                requested_intention_token=requested_intention_token_text,
                time_context_active=time_context_active_flag,
                precinct_district_overlay_enabled=precinct_scope_active,
            )
            if project_all_documents
            else ([] if target_document is None else [target_document])
        )
        documents = [
            self._cached_document_projection(document, overlay_mode=normalized_overlay_mode)
            for document in target_documents
        ]
        navigation_bundle = _build_navigation_bundle(documents)
        projected_summary_map = {
            _as_text((document_bundle.get("document_summary") or {}).get("document_id")): dict(
                document_bundle.get("document_summary") or {}
            )
            for document_bundle in documents
        }
        for summary in document_catalog:
            projected_summary = projected_summary_map.get(_as_text(summary.get("document_id")))
            if projected_summary is None:
                continue
            summary.update(
                {
                    "projectable_feature_count": int(projected_summary.get("projectable_feature_count") or 0),
                    "projection_state": _as_text(projected_summary.get("projection_state")) or "inspect_only",
                    "profile_count": int(projected_summary.get("profile_count") or 0),
                    "default_attention_node_id": _as_text(projected_summary.get("default_attention_node_id")),
                }
            )
        fallback_document_summary = None
        if not documents and workbench.selected_document is not None:
            fallback_document_summary = workbench.selected_document.to_summary_dict()
            fallback_document_summary["selected"] = True
        warnings = list(workbench.warnings)
        for document_bundle in documents:
            document = document_bundle.get("document")
            if document is not None:
                warnings.extend(list(document.warnings))
        warnings = list(dict.fromkeys(_as_text(item) for item in warnings if _as_text(item)))
        return {
            "tenant_id": _as_text(tenant_id) or "fnd",
            "overlay_mode": normalized_overlay_mode,
            "raw_underlay_visible": normalized_raw_underlay,
            "documents": documents,
            "navigation_bundle": navigation_bundle,
            "document_catalog": document_catalog,
            "fallback_document_summary": fallback_document_summary,
            "authority_catalog_summary": {
                "configured": True,
                "document_count": len(workbench.documents),
                "source_files": list(workbench.source_files),
                "readiness_status": dict(workbench.readiness_status),
                "warnings": list(workbench.warnings),
            },
            "warnings": warnings,
            "precinct_district_overlay_enabled": precinct_district_overlay_enabled_flag,
        }

    def normalize_mediation_request(
        self,
        projection_bundle: dict[str, Any],
        *,
        selected_document_id: object = "",
        selected_row_address: object = "",
        selected_feature_id: object = "",
        mediation_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        documents = list(projection_bundle.get("documents") or [])
        navigation_bundle = dict(projection_bundle.get("navigation_bundle") or {})
        requested_document_id = _as_text(selected_document_id)
        requested_row_address = _as_text(selected_row_address)
        requested_feature_id = _as_text(selected_feature_id)
        mediation_state = mediation_state if isinstance(mediation_state, dict) else {}
        requested_attention_document_id = _as_text(mediation_state.get("attention_document_id"))
        requested_attention_node_id = _as_text(mediation_state.get("attention_node_id"))
        requested_intention_token = _as_text(mediation_state.get("intention_token"))
        requested_time_context = _normalize_time_context(mediation_state.get("time"))
        intention_warnings: list[str] = []

        selected_document_bundle = None
        if requested_attention_document_id:
            for document_bundle in documents:
                if _matches_cts_gis_document_id(
                    (document_bundle.get("document_summary") or {}).get("document_id"),
                    requested_attention_document_id,
                ):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None and requested_attention_node_id:
            for document_bundle in documents:
                if requested_attention_node_id in dict(document_bundle.get("profile_index") or {}):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None and requested_document_id:
            for document_bundle in documents:
                if _matches_cts_gis_document_id(
                    (document_bundle.get("document_summary") or {}).get("document_id"),
                    requested_document_id,
                ):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None and requested_feature_id:
            selected_document_bundle, _ = _document_lookup_by_feature_id(projection_bundle, requested_feature_id)
        if selected_document_bundle is None and requested_row_address:
            selected_document_bundle, _ = _document_lookup_by_row_address(projection_bundle, requested_row_address)
        if selected_document_bundle is None:
            for document_bundle in documents:
                if bool((document_bundle.get("document_summary") or {}).get("selected")):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None:
            for document_bundle in documents:
                if _as_text(document_bundle.get("default_attention_node_id")) == _DEFAULT_ATTENTION_NODE_ID:
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None:
            for document_bundle in documents:
                if _as_text(document_bundle.get("default_attention_node_id")):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None and documents:
            selected_document_bundle = documents[0]

        selected_document_summary = (selected_document_bundle or {}).get("document_summary") or {}
        attention_document_id = _as_text(selected_document_summary.get("document_id"))
        profile_index = dict(navigation_bundle.get("profile_index") or {})
        row_profile_index = (selected_document_bundle or {}).get("row_profile_index") or {}
        feature_profile_index = dict(navigation_bundle.get("feature_profile_index") or {})

        attention_node_id = requested_attention_node_id
        if not attention_node_id and requested_feature_id:
            candidates = list(feature_profile_index.get(requested_feature_id) or [])
            if candidates:
                attention_node_id = _as_text(candidates[0])
        if not attention_node_id and requested_row_address:
            row_candidates = list(row_profile_index.get(requested_row_address) or [])
            if row_candidates:
                attention_node_id = _as_text(row_candidates[0])
        if not attention_node_id:
            attention_node_id = _as_text((selected_document_bundle or {}).get("default_attention_node_id")) or _as_text(
                navigation_bundle.get("default_attention_node_id")
            )
        if not attention_node_id and profile_index:
            attention_node_id = _as_text(sorted(profile_index.keys(), key=lambda item: (_node_depth(item), item))[0])

        intention_token = _normalize_intention_token(
            {
                "profile_index": profile_index,
                "children_by_parent": dict(navigation_bundle.get("children_by_parent") or {}),
            },
            attention_node_id,
            (
                _LEGACY_SELF_INTENTION_TOKEN
                if (
                    not _as_text(requested_intention_token)
                    and attention_node_id
                )
                else requested_intention_token
            ),
        )
        if requested_intention_token and requested_intention_token != intention_token:
            intention_warnings.append(
                f"Requested intention `{requested_intention_token}` normalized to `{intention_token}` for attention node `{attention_node_id or 'none'}`."
            )
        selected_row_address_out = requested_row_address
        selected_feature_id_out = requested_feature_id
        if requested_intention_token and requested_intention_token != intention_token and intention_token == "self":
            # Stale selection from widened scopes should not leak into strict self rendering.
            selected_row_address_out = ""
            selected_feature_id_out = ""
        return {
            "attention_document_id": attention_document_id,
            "attention_node_id": attention_node_id,
            "intention_token": intention_token,
            "selected_document_id": requested_document_id,
            "selected_row_address": selected_row_address_out,
            "selected_feature_id": selected_feature_id_out,
            "time_context": requested_time_context,
            "intention_warnings": intention_warnings,
        }

    def build_mediation_surface(
        self,
        projection_bundle: dict[str, Any],
        *,
        attention_document_id: object = "",
        attention_node_id: object = "",
        intention_token: object = _DEFAULT_INTENTION_TOKEN,
        time_context: object = None,
        precinct_district_overlay_enabled: object = False,
    ) -> dict[str, Any]:
        documents = list(projection_bundle.get("documents") or [])
        navigation_bundle = dict(projection_bundle.get("navigation_bundle") or {})
        overlay_mode = _as_text(projection_bundle.get("overlay_mode")) or "auto"
        raw_underlay_visible = bool(projection_bundle.get("raw_underlay_visible"))
        time_context_payload = _normalize_time_context(time_context)
        precinct_district_overlay_enabled_flag = bool(precinct_district_overlay_enabled)
        selected_document_bundle = None
        for document_bundle in documents:
            if _matches_cts_gis_document_id(
                (document_bundle.get("document_summary") or {}).get("document_id"),
                attention_document_id,
            ):
                selected_document_bundle = document_bundle
                break
        if selected_document_bundle is None:
            attention_node_id_text = _as_text(attention_node_id)
            for document_bundle in documents:
                if attention_node_id_text in dict(document_bundle.get("profile_index") or {}):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None:
            for document_bundle in documents:
                if bool((document_bundle.get("document_summary") or {}).get("selected")):
                    selected_document_bundle = document_bundle
                    break

        if selected_document_bundle is None:
            fallback_document_summary = projection_bundle.get("fallback_document_summary")
            document_catalog = list(projection_bundle.get("document_catalog") or [])
            warnings = list(projection_bundle.get("warnings") or [])
            if not documents:
                warnings.append("No authoritative sandbox CTS-GIS documents were available for the current tenant.")
            warnings = list(dict.fromkeys(_as_text(item) for item in warnings if _as_text(item)))
            return {
                "document_catalog": document_catalog,
                "selected_document": fallback_document_summary,
                "attention_profile": None,
                "lineage": [],
                "children": [],
                "related_profiles": [],
                "render_set_summary": {
                    "render_mode": "none",
                    "render_profile_count": 0,
                    "render_row_count": 0,
                    "render_feature_count": 0,
                },
                "map_projection": {
                    "projection_state": "no_authoritative_cts_gis_documents",
                    "feature_count": 0,
                    "projection_source": "none",
                    "decode_summary": {
                        "reference_binding_count": 0,
                        "decoded_coordinate_count": 0,
                        "failed_token_count": 0,
                    },
                    "warnings": [],
                    "selected_feature": None,
                    "feature_collection": {
                        "type": "FeatureCollection",
                        "features": [],
                        "bounds": None,
                    },
                },
                "rows": [],
                "diagnostic_summary": {
                    "document_count": 0,
                    "selected_document_id": _as_text((fallback_document_summary or {}).get("document_id")),
                    "attention_node_id": "",
                    "intention_token": _DEFAULT_INTENTION_TOKEN,
                    "render_row_count": 0,
                    "render_feature_count": 0,
                    "projection_state": "no_authoritative_cts_gis_documents",
                    "document_row_count": _as_text((fallback_document_summary or {}).get("row_count")),
                    "time_context_active": bool(time_context_payload.get("active")),
                    "precinct_district_gate_failures": [],
                },
                "lens_state": {
                    "overlay_mode": overlay_mode,
                    "raw_underlay_visible": raw_underlay_visible,
                    "lens_presentation_only": True,
                },
                "mediation_state": {
                    "attention_document_id": "",
                    "attention_node_id": "",
                    "intention_token": _DEFAULT_INTENTION_TOKEN,
                    "time": time_context_payload,
                    "anchor_context": {
                        "samras_ruiqi": {"present": False, "bit_length": 0},
                        "chronological_hops": {"present": False, "bit_length": 0},
                    },
                    "available_intentions": [],
                    "selection_summary": {},
                    "precinct_district_overlay_enabled": precinct_district_overlay_enabled_flag,
                    "precinct_district_overlay_active": False,
                    "precinct_district_gate_failures": [],
                },
                "contextual_references": {
                    "time_context": time_context_payload,
                    "anchor_context": {
                        "samras_ruiqi": {"present": False, "bit_length": 0},
                        "chronological_hops": {"present": False, "bit_length": 0},
                    },
                    "district_precincts": {
                        "enabled": precinct_district_overlay_enabled_flag,
                        "overlay_active": False,
                        "attention_node_id": "",
                        "supported_attention_lineage": False,
                        "chronological_anchor_present": False,
                        "time_token": _as_text(time_context_payload.get("value_token")),
                        "timeframe_tokens": [],
                        "timeframe_match": False,
                        "scope_node_id": "",
                        "collection_count": 0,
                        "collections": [],
                        "gate_failures": [],
                    },
                },
                "warnings": warnings,
                "_render_row_views": [],
                "_render_features": [],
                "_row_profile_index": {},
            }

        document_summary = dict(selected_document_bundle.get("document_summary") or {})
        document_summary["selected"] = True
        profile_index = dict(navigation_bundle.get("profile_index") or {})
        row_profile_index = selected_document_bundle.get("row_profile_index") or {}
        feature_profile_index = dict(navigation_bundle.get("feature_profile_index") or {})
        anchor_context = _anchor_context_metadata(selected_document_bundle.get("document"))
        chronological_anchor_present = bool((anchor_context.get("chronological_hops") or {}).get("present"))
        time_context_without_anchor = bool(time_context_payload.get("active")) and not chronological_anchor_present
        time_context_token = _as_text(time_context_payload.get("value_token"))
        district_timeframes = _district_timeframe_tokens(selected_document_bundle)
        district_timeframe_match = _time_context_in_timeframe(
            time_token=time_context_token,
            timeframe_tokens=district_timeframes,
        )
        attention_node_id_text = _as_text(attention_node_id)
        precinct_gate_failures = _precinct_overlay_gate_failures(
            overlay_requested=precinct_district_overlay_enabled_flag,
            attention_node_id=attention_node_id_text,
            time_context_payload=time_context_payload,
            chronological_anchor_present=chronological_anchor_present,
            district_timeframe_match=district_timeframe_match,
        )
        attention_profile = profile_index.get(attention_node_id_text)
        descendants_token = _descendants_intention_token(attention_node_id_text)
        children_token = _children_intention_token(attention_node_id_text)
        navigation_surface_bundle = {
            "profile_index": profile_index,
            "children_by_parent": dict(navigation_bundle.get("children_by_parent") or {}),
        }
        intention_token_text = _normalize_intention_token(navigation_surface_bundle, attention_node_id_text, intention_token)
        available_intentions = _available_intentions(navigation_surface_bundle, attention_node_id_text)
        available_token_set = {option["token"] for option in available_intentions}
        if intention_token_text not in available_token_set:
            intention_token_text = "self" if attention_node_id_text else _DEFAULT_INTENTION_TOKEN

        overlay_profiles: list[dict[str, Any]] = []
        if intention_token_text == descendants_token:
            overlay_profiles = _descendant_profiles(
                navigation_surface_bundle,
                attention_node_id=attention_node_id_text,
                min_extra_segments=1,
                max_extra_segments=2,
            )
        elif intention_token_text == children_token:
            overlay_profiles = sorted(
                [
                profile_index[node_id]
                for node_id in list((navigation_bundle.get("children_by_parent") or {}).get(attention_node_id_text, []))
                if node_id in profile_index
                ],
                key=_profile_sort_key,
            )
        elif intention_token_text.startswith(_BRANCH_INTENTION_PREFIX):
            target_node_id = _as_text(intention_token_text[len(_BRANCH_INTENTION_PREFIX) :])
            target_profile = profile_index.get(target_node_id)
            if target_profile is not None:
                overlay_profiles = [target_profile]
        # Time-contextualized overlays may include precinct cohorts that map to
        # the active state/county attention lineage.
        precinct_overlay_active = bool(
            precinct_district_overlay_enabled_flag
            and not precinct_gate_failures
        )
        precinct_overlay_profiles: list[dict[str, Any]] = []
        if precinct_overlay_active:
            overlay_seen = {
                _as_text(profile.get("node_id"))
                for profile in overlay_profiles
                if _as_text(profile.get("node_id"))
            }
            precinct_overlay_profiles = _matching_precinct_profiles(
                profile_index=profile_index,
                attention_node_id=attention_node_id_text,
                exclude_node_ids=overlay_seen,
            )
            overlay_profiles.extend(precinct_overlay_profiles)
        district_collection_summaries = _district_precinct_collection_summaries(
            attention_node_id=attention_node_id_text,
            time_context_payload=time_context_payload,
            timeframe_tokens=district_timeframes,
            overlay_requested=precinct_district_overlay_enabled_flag,
            overlay_active=precinct_overlay_active,
            precinct_profiles=precinct_overlay_profiles,
            gate_failures=precinct_gate_failures,
            chronological_anchor_present=chronological_anchor_present,
        )
        projected_profiles: list[dict[str, Any]] = []
        projected_seen: set[str] = set()
        if attention_profile is not None:
            attention_profile_node_id = _as_text(attention_profile.get("node_id"))
            if attention_profile_node_id:
                projected_profiles.append(attention_profile)
                projected_seen.add(attention_profile_node_id)
        for profile in overlay_profiles:
            node_id = _as_text(profile.get("node_id"))
            if not node_id or node_id in projected_seen:
                continue
            projected_seen.add(node_id)
            projected_profiles.append(profile)
        render_document_row_addresses: dict[str, set[str]] = {}
        render_feature_id_set: set[str] = set()
        render_document_ids: set[str] = set()
        for profile in projected_profiles:
            document_id = _as_text(profile.get("document_id"))
            if document_id:
                render_document_ids.add(document_id)
                render_document_row_addresses.setdefault(document_id, set()).update(profile.get("row_addresses") or [])
            for feature_id in list(profile.get("feature_ids") or []):
                feature_id_text = _as_text(feature_id)
                if feature_id_text:
                    render_feature_id_set.add(feature_id_text)
        selected_document_id_text = _as_text(document_summary.get("document_id"))
        row_index = selected_document_bundle.get("row_index") or {}
        ordered_render_row_addresses = [
            address
            for address in _sorted_addresses(render_document_row_addresses.get(selected_document_id_text, set()))
            if address in row_index
        ]
        render_row_views = [row_index[address] for address in ordered_render_row_addresses]
        projected_profile_order = {
            _as_text(profile.get("node_id")): index
            for index, profile in enumerate(projected_profiles)
            if _as_text(profile.get("node_id"))
        }
        render_feature_ids = sorted(
            render_feature_id_set,
            key=lambda feature_id: (
                min(
                    [
                        projected_profile_order[node_id]
                        for node_id in list(feature_profile_index.get(feature_id) or [])
                        if node_id in projected_profile_order
                    ]
                    or [len(projected_profiles) + 1]
                ),
                feature_id,
            ),
        )
        feature_index = dict(navigation_bundle.get("feature_index") or {})
        render_features = [feature_index[feature_id] for feature_id in render_feature_ids if feature_id in feature_index]
        document_bundle_index = {
            _as_text((document_bundle.get("document_summary") or {}).get("document_id")): document_bundle
            for document_bundle in documents
        }

        attention_profile_display = attention_profile
        if attention_profile_display is None and attention_node_id_text:
            attention_profile_display = _canonical_placeholder_profile_summary(attention_node_id_text)

        lineage: list[dict[str, Any]] = []
        for depth in range(1, _node_depth(attention_node_id_text) + 1):
            node_id = "-".join(attention_node_id_text.split("-")[:depth])
            profile = profile_index.get(node_id)
            if profile is None:
                lineage.append(_canonical_placeholder_profile_summary(node_id))
            else:
                lineage.append(
                    _profile_public_summary(profile, selected=node_id == attention_node_id_text)
                )

        children = [
            _profile_public_summary(profile_index[node_id])
            for node_id in list((navigation_bundle.get("children_by_parent") or {}).get(attention_node_id_text, []))
            if node_id in profile_index
        ]
        related_profiles: list[dict[str, Any]] = []
        if attention_profile is not None:
            related_seen: set[str] = set()
            for bound_node_id in list((attention_profile or {}).get("bound_node_ids") or []):
                if bound_node_id in related_seen:
                    continue
                related_seen.add(bound_node_id)
                profile = profile_index.get(bound_node_id)
                if profile is None:
                    related_profiles.append(_canonical_placeholder_profile_summary(bound_node_id, relation="bound_profile"))
                else:
                    related_profiles.append(_profile_public_summary(profile, relation="bound_profile"))
            parent_node_id = _as_text((attention_profile or {}).get("parent_node_id"))
            for sibling_node_id in list((navigation_bundle.get("children_by_parent") or {}).get(parent_node_id, [])):
                if sibling_node_id == attention_node_id_text or sibling_node_id in related_seen or sibling_node_id not in profile_index:
                    continue
                related_seen.add(sibling_node_id)
                related_profiles.append(_profile_public_summary(profile_index[sibling_node_id], relation="sibling"))

        attention_feature_ids = {
            _as_text(feature_id)
            for feature_id in list((attention_profile or {}).get("feature_ids") or [])
            if _as_text(feature_id)
        }
        projected_node_ids = {
            _as_text(profile.get("node_id"))
            for profile in projected_profiles
            if _as_text(profile.get("node_id"))
        }
        feature_collection_features = []
        all_render_points: list[list[float]] = []
        focused_render_points: list[list[float]] = []
        for feature in render_features:
            feature_id = _as_text(feature.get("feature_id"))
            owner_profile = None
            for node_id in list(feature_profile_index.get(feature_id) or []):
                if node_id in projected_node_ids:
                    owner_profile = profile_index.get(node_id)
                    break
            if owner_profile is None:
                for node_id in list(feature_profile_index.get(feature_id) or []):
                    owner_profile = profile_index.get(node_id)
                    if owner_profile is not None:
                        break
            feature_payload = dict(feature["feature"])
            feature_properties = dict(feature_payload.get("properties") or {})
            feature_properties["samras_node_id"] = _as_text((owner_profile or {}).get("node_id")) or _as_text(
                feature_properties.get("samras_node_id")
            )
            feature_properties["profile_label"] = _as_text((owner_profile or {}).get("profile_label")) or _as_text(
                feature_properties.get("profile_label")
            )
            feature_properties["title_display"] = _as_text((owner_profile or {}).get("title_display")) or _as_text(
                feature_properties.get("title_display")
            )
            feature_properties["lineage"] = list(
                _as_text(item)
                for item in (
                    []
                    if owner_profile is None
                    else ["-".join(_as_text(owner_profile.get("node_id")).split("-")[:index]) for index in range(1, _node_depth(owner_profile.get("node_id")) + 1)]
                )
                if _as_text(item)
            )
            feature_properties["parent_node_id"] = _as_text((owner_profile or {}).get("parent_node_id"))
            attention_member = _as_text((owner_profile or {}).get("node_id")) == attention_node_id_text
            feature_properties["attention_member"] = attention_member
            feature_payload["properties"] = feature_properties
            feature_collection_features.append(feature_payload)
            geometry_points = _geometry_points(dict(feature_payload.get("geometry") or {}))
            if geometry_points:
                all_render_points.extend(geometry_points)
                if feature_id in attention_feature_ids or attention_member:
                    focused_render_points.extend(geometry_points)
        map_bounds = _feature_bounds(focused_render_points or all_render_points)
        render_projection_summary = {
            "reference_binding_count": 0,
            "decoded_coordinate_count": 0,
            "failed_token_count": 0,
            "reason_codes": [],
            "warnings": [],
        }
        total_render_row_count = 0
        render_projection_warnings: list[str] = []
        for document_id, row_addresses in render_document_row_addresses.items():
            document_bundle = document_bundle_index.get(document_id)
            if document_bundle is None:
                continue
            document_row_index = document_bundle.get("row_index") or {}
            ordered_document_row_addresses = [
                address
                for address in _sorted_addresses(row_addresses)
                if address in document_row_index
            ]
            total_render_row_count += len(ordered_document_row_addresses)
            document_projection_summary = _projection_summary_for_row_addresses(
                ordered_document_row_addresses,
                document_row_index,
            )
            render_projection_summary["reference_binding_count"] += int(
                document_projection_summary.get("reference_binding_count") or 0
            )
            render_projection_summary["decoded_coordinate_count"] += int(
                document_projection_summary.get("decoded_coordinate_count") or 0
            )
            render_projection_summary["failed_token_count"] += int(
                document_projection_summary.get("failed_token_count") or 0
            )
            render_projection_summary["reason_codes"] = _dedupe_texts(
                list(render_projection_summary.get("reason_codes") or [])
                + list(document_projection_summary.get("reason_codes") or [])
            )
            render_projection_warnings.extend(list(document_projection_summary.get("warnings") or []))
            render_projection_warnings.extend(
                list(((document_bundle.get("document_summary") or {}).get("projection_warnings")) or [])
            )
        render_projection_warnings = _dedupe_texts(
            render_projection_warnings
            + [
                warning
                for feature in render_features
                for warning in list(feature.get("projection_warnings") or [])
            ]
        )
        render_projection_summary["reason_codes"] = _dedupe_texts(
            list(render_projection_summary.get("reason_codes") or [])
            + [
                reason_code
                for feature in render_features
                for reason_code in list(feature.get("projection_reason_codes") or [])
            ]
        )
        projection_sources = {
            _as_text(feature.get("projection_source"))
            for feature in render_features
            if _as_text(feature.get("projection_source")) and _as_text(feature.get("projection_source")) != "none"
        }
        if not render_features:
            projection_source = "none"
            projection_state = "inspect_only"
        elif projection_sources == {"hops"}:
            projection_source = "hops"
            projection_state = (
                "projectable_degraded"
                if int(render_projection_summary.get("failed_token_count") or 0) or render_projection_warnings
                else "projectable"
            )
        elif "reference_geojson_fallback" in projection_sources:
            projection_source = "reference_geojson_fallback"
            projection_state = "projectable_fallback"
        else:
            projection_source = "none"
            projection_state = "inspect_only"
        fallback_reason_codes = _dedupe_texts(
            [
                "decode_failure"
                if int(render_projection_summary.get("failed_token_count") or 0) > 0
                else "",
                "parity_mismatch"
                if any(
                    ("did not align" in warning)
                    or ("reference GeoJSON carries" in warning)
                    or ("HOPS row chain resolves" in warning)
                    for warning in render_projection_warnings
                )
                else "",
                "authority_warning"
                if any("reference GeoJSON geometry" in warning for warning in render_projection_warnings)
                else "",
            ]
            + list(render_projection_summary.get("reason_codes") or [])
        )
        if projection_state == "projectable":
            projection_health = {"state": "ok", "reason_codes": []}
        elif projection_state == "projectable_degraded":
            projection_health = {"state": "degraded", "reason_codes": fallback_reason_codes}
        elif projection_state == "projectable_fallback":
            projection_health = {"state": "fallback", "reason_codes": fallback_reason_codes or ["authority_warning"]}
        else:
            projection_health = {"state": "empty", "reason_codes": []}
        warnings = list(projection_bundle.get("warnings") or [])
        document = selected_document_bundle.get("document")
        if document is not None:
            warnings.extend(list(document.warnings))
        if time_context_without_anchor:
            warnings.append("Time context requested but no chronological anchor space was found in supporting anchor rows.")
        if precinct_district_overlay_enabled_flag and "attention_node_missing" in precinct_gate_failures:
            warnings.append("Precinct overlays require an active state or county attention node; overlays were skipped.")
        if precinct_district_overlay_enabled_flag and "attention_lineage_unsupported" in precinct_gate_failures:
            warnings.append("Precinct overlays require state or county attention lineage under `3-2-3-*`; overlays were skipped.")
        if precinct_district_overlay_enabled_flag and "time_context_inactive" in precinct_gate_failures:
            warnings.append("Precinct overlays require an active time context; overlays were skipped.")
        if (
            precinct_district_overlay_enabled_flag
            and bool(time_context_payload.get("active"))
            and not district_timeframe_match
        ):
            warnings.append(
                f"Time context `{time_context_token or 'inactive'}` is outside district timeframe scope; precinct overlays were skipped."
            )
        warnings = list(dict.fromkeys(_as_text(item) for item in warnings if _as_text(item)))

        document_catalog = []
        for summary_in in list(projection_bundle.get("document_catalog") or []):
            summary = dict(summary_in)
            summary["selected"] = _as_text(summary.get("document_id")) == _as_text(document_summary.get("document_id"))
            document_catalog.append(summary)
        if not document_catalog:
            for document_bundle in documents:
                summary = dict(document_bundle.get("document_summary") or {})
                summary["selected"] = _as_text(summary.get("document_id")) == _as_text(document_summary.get("document_id"))
                document_catalog.append(summary)

        render_set_summary = {
            "render_mode": (
                "descendants_depth_1_or_2"
                if intention_token_text == descendants_token
                else "self"
                if intention_token_text == "self"
                else "children"
                if intention_token_text == children_token
                else "branch"
            ),
            "render_profile_count": len(projected_profiles),
            "render_row_count": total_render_row_count,
            "render_feature_count": len(render_features),
            "render_profile_labels": [
                _as_text(profile.get("profile_label")) or _as_text(profile.get("node_id"))
                for profile in projected_profiles
            ],
        }

        return {
            "document_catalog": document_catalog,
            "selected_document": document_summary,
            "attention_profile": None
            if attention_profile_display is None
            else (
                _profile_public_summary(attention_profile_display, selected=True)
                if attention_profile is not None
                else {**dict(attention_profile_display), "selected": True}
            ),
            "lineage": lineage,
            "children": children,
            "render_profiles": [
                _profile_public_summary(
                    profile,
                    relation="render_profile",
                    selected=_as_text(profile.get("node_id")) == attention_node_id_text,
                )
                for profile in projected_profiles
            ],
            "related_profiles": related_profiles,
            "render_set_summary": render_set_summary,
            "map_projection": {
                "projection_state": projection_state,
                "feature_count": len(render_features),
                "projection_source": projection_source,
                "decode_summary": {
                    "reference_binding_count": int(render_projection_summary.get("reference_binding_count") or 0),
                    "decoded_coordinate_count": int(render_projection_summary.get("decoded_coordinate_count") or 0),
                    "failed_token_count": int(render_projection_summary.get("failed_token_count") or 0),
                },
                "projection_health": projection_health,
                "fallback_reason_codes": list(projection_health.get("reason_codes") or []),
                "semantic_guardrails": {
                    "triggered": any(
                        _as_text(code).startswith("semantic_")
                        for code in list(projection_health.get("reason_codes") or [])
                    ),
                    "reason_codes": [
                        code
                        for code in list(projection_health.get("reason_codes") or [])
                        if _as_text(code).startswith("semantic_")
                    ],
                },
                "focus_node_id": attention_node_id_text,
                "focus_bounds": _feature_bounds(focused_render_points),
                "warnings": render_projection_warnings,
                "selected_feature": None,
                "feature_collection": {
                    "type": "FeatureCollection",
                    "features": feature_collection_features,
                    "bounds": map_bounds,
                },
            },
            "rows": [],
            "diagnostic_summary": {
                "document_count": len(document_catalog) or len(documents),
                "selected_document_id": _as_text(document_summary.get("document_id")),
                "attention_node_id": attention_node_id_text,
                "intention_token": intention_token_text,
                "document_row_count": int(document_summary.get("row_count") or 0),
                "render_row_count": len(render_row_views),
                "render_feature_count": len(render_features),
                "projection_state": projection_state,
                "time_context_active": bool(time_context_payload.get("active")),
                "precinct_district_overlay_enabled": precinct_district_overlay_enabled_flag,
                "precinct_district_overlay_active": precinct_overlay_active,
                "precinct_district_timeframe_match": district_timeframe_match,
                "precinct_district_gate_failures": list(precinct_gate_failures),
            },
            "lens_state": {
                "overlay_mode": overlay_mode,
                "raw_underlay_visible": raw_underlay_visible,
                "lens_presentation_only": True,
            },
            "mediation_state": {
                "attention_document_id": _as_text(document_summary.get("document_id")),
                "attention_node_id": attention_node_id_text,
                "intention_token": intention_token_text,
                "time": time_context_payload,
                "anchor_context": anchor_context,
                "available_intentions": [
                    {
                        **option,
                        "active": _as_text(option.get("token")) == intention_token_text,
                    }
                    for option in available_intentions
                ],
                "selection_summary": {},
                "precinct_district_overlay_enabled": precinct_district_overlay_enabled_flag,
                "precinct_district_overlay_active": precinct_overlay_active,
                "precinct_district_gate_failures": list(precinct_gate_failures),
            },
            "contextual_references": {
                "time_context": time_context_payload,
                "anchor_context": anchor_context,
                "district_precincts": {
                    "enabled": precinct_district_overlay_enabled_flag,
                    "overlay_active": precinct_overlay_active,
                    "attention_node_id": attention_node_id_text,
                    "supported_attention_lineage": _precinct_overlay_attention_supported(attention_node_id_text),
                    "chronological_anchor_present": chronological_anchor_present,
                    "time_token": time_context_token,
                    "timeframe_tokens": district_timeframes,
                    "timeframe_match": district_timeframe_match,
                    "scope_node_id": _precinct_overlay_scope_node_id(attention_node_id_text),
                    "collection_count": len(district_collection_summaries),
                    "collections": district_collection_summaries,
                    "gate_failures": list(precinct_gate_failures),
                },
            },
            "warnings": warnings,
            "_render_row_views": render_row_views,
            "_render_features": render_features,
            "_row_profile_index": row_profile_index,
        }

    def finalize_selection(
        self,
        mediation_surface: dict[str, Any],
        *,
        selected_row_address: object = "",
        selected_feature_id: object = "",
    ) -> dict[str, Any]:
        render_row_views = list(mediation_surface.get("_render_row_views") or [])
        render_features = list(mediation_surface.get("_render_features") or [])
        row_profile_index = dict(mediation_surface.get("_row_profile_index") or {})
        requested_row_address = _as_text(selected_row_address)
        requested_feature_id = _as_text(selected_feature_id)
        selected_row = None
        if requested_row_address:
            for row in render_row_views:
                if row["datum_address"] == requested_row_address:
                    selected_row = row
                    break
        selected_feature = None
        if requested_feature_id:
            for feature in render_features:
                if feature["feature_id"] == requested_feature_id:
                    selected_feature = feature
                    break
        if selected_row is None and selected_feature is not None:
            feature_row_address = _as_text(selected_feature.get("row_address"))
            for row in render_row_views:
                if row["datum_address"] == feature_row_address:
                    selected_row = row
                    break
        if selected_row is None and render_row_views:
            attention_row_address = _as_text((mediation_surface.get("attention_profile") or {}).get("row_address"))
            for row in render_row_views:
                if row["datum_address"] == attention_row_address:
                    selected_row = row
                    break
        if selected_row is None and render_row_views:
            selected_row = render_row_views[0]
        if selected_feature is None and selected_row is not None:
            selected_row_feature_ids = list(selected_row.get("feature_ids") or [])
            for feature in render_features:
                if feature["feature_id"] in selected_row_feature_ids:
                    selected_feature = feature
                    break
        if selected_feature is None and render_features:
            selected_feature = render_features[0]

        selected_row_address_text = _as_text((selected_row or {}).get("datum_address"))
        selected_feature_id_text = _as_text((selected_feature or {}).get("feature_id"))
        selected_profile_node_id = ""
        if selected_row_address_text:
            selected_profile_candidates = list(row_profile_index.get(selected_row_address_text) or [])
            if selected_profile_candidates:
                selected_profile_node_id = _as_text(selected_profile_candidates[0])

        row_summaries = []
        for row in render_row_views:
            overlay_preview = [
                {
                    "overlay_family": _as_text(overlay.get("overlay_family")) or "raw_only",
                    "anchor_label": _as_text(overlay.get("anchor_label")) or _as_text(overlay.get("overlay_family")),
                    "display_value": _as_text(overlay.get("display_value")) or _as_text(overlay.get("raw_value")),
                    "raw_value": _as_text(overlay.get("raw_value")),
                    "overlay_state": _as_text(overlay.get("overlay_state")) or "raw_only",
                }
                for overlay in list(row.get("overlay_values") or [])[:4]
            ]
            row_summaries.append(
                {
                    "datum_address": row["datum_address"],
                    "labels": list(row.get("labels") or []),
                    "label_text": row.get("label_text"),
                    "recognized_family": row.get("recognized_family"),
                    "recognized_anchor": row.get("recognized_anchor"),
                    "primary_value_token": row.get("primary_value_token"),
                    "diagnostic_states": list(row.get("diagnostic_states") or []),
                    "feature_ids": list(row.get("feature_ids") or []),
                    "overlay_preview": overlay_preview,
                    "samras_node_id": _as_text(row.get("samras_node_id")),
                    "profile_label": _as_text(row.get("profile_label")) or _as_text(row.get("samras_node_id")),
                    "title_display": _as_text(row.get("title_display")),
                    "linked_row_addresses": list(row.get("linked_row_addresses") or []),
                    "projection_source": _as_text(row.get("coordinate_projection_source")) or "none",
                    "decode_summary": {
                        "reference_binding_count": int(row.get("reference_binding_count") or 0),
                        "decoded_coordinate_count": int(row.get("decoded_coordinate_count") or 0),
                        "failed_token_count": int(row.get("failed_token_count") or 0),
                    },
                    "projection_warnings": list(row.get("coordinate_warnings") or []),
                    "selected": row["datum_address"] == selected_row_address_text,
                    "selected_feature": selected_feature_id_text in (row.get("feature_ids") or []),
                }
            )

        feature_collection = dict((mediation_surface.get("map_projection") or {}).get("feature_collection") or {})
        feature_collection["features"] = [
            {
                **feature,
                "selected": _as_text(feature.get("id")) == selected_feature_id_text,
            }
            for feature in list(feature_collection.get("features") or [])
        ]

        out = {
            "document_catalog": list(mediation_surface.get("document_catalog") or []),
            "selected_document": dict(mediation_surface.get("selected_document") or {}),
            "attention_profile": (
                None
                if mediation_surface.get("attention_profile") is None
                else dict(mediation_surface.get("attention_profile") or {})
            ),
            "lineage": list(mediation_surface.get("lineage") or []),
            "children": list(mediation_surface.get("children") or []),
            "render_profiles": list(mediation_surface.get("render_profiles") or []),
            "related_profiles": list(mediation_surface.get("related_profiles") or []),
            "render_set_summary": dict(mediation_surface.get("render_set_summary") or {}),
            "selected_row": selected_row,
            "map_projection": {
                "projection_state": _as_text((mediation_surface.get("map_projection") or {}).get("projection_state"))
                or "inspect_only",
                "feature_count": int((mediation_surface.get("map_projection") or {}).get("feature_count") or 0),
                "projection_source": _as_text((mediation_surface.get("map_projection") or {}).get("projection_source"))
                or "none",
                "decode_summary": dict((mediation_surface.get("map_projection") or {}).get("decode_summary") or {}),
                "projection_health": dict(
                    (mediation_surface.get("map_projection") or {}).get("projection_health")
                    or {"state": "empty", "reason_codes": []}
                ),
                "fallback_reason_codes": list(
                    (mediation_surface.get("map_projection") or {}).get("fallback_reason_codes") or []
                ),
                "semantic_guardrails": dict(
                    (mediation_surface.get("map_projection") or {}).get("semantic_guardrails")
                    or {"triggered": False, "reason_codes": []}
                ),
                "focus_node_id": _as_text((mediation_surface.get("map_projection") or {}).get("focus_node_id")),
                "focus_bounds": list((mediation_surface.get("map_projection") or {}).get("focus_bounds") or []),
                "warnings": list((mediation_surface.get("map_projection") or {}).get("warnings") or []),
                "selected_feature": selected_feature,
                "feature_collection": feature_collection,
            },
            "rows": row_summaries,
            "diagnostic_summary": {
                **dict(mediation_surface.get("diagnostic_summary") or {}),
                "selected_row_address": selected_row_address_text,
                "selected_feature_id": selected_feature_id_text,
            },
            "lens_state": dict(mediation_surface.get("lens_state") or {}),
            "mediation_state": {
                **dict(mediation_surface.get("mediation_state") or {}),
                "selection_summary": {
                    "selected_row_address": selected_row_address_text,
                    "selected_feature_id": selected_feature_id_text,
                    "selected_profile_node_id": selected_profile_node_id,
                    "render_row_count": len(row_summaries),
                    "render_feature_count": int((mediation_surface.get("map_projection") or {}).get("feature_count") or 0),
                },
            },
            "contextual_references": dict(mediation_surface.get("contextual_references") or {}),
            "warnings": list(mediation_surface.get("warnings") or []),
        }
        return out

    def read_surface(
        self,
        tenant_id: str,
        *,
        selected_document_id: object = "",
        selected_row_address: object = "",
        selected_feature_id: object = "",
        overlay_mode: object = "auto",
        raw_underlay_visible: object = False,
        mediation_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mediation_state = mediation_state if isinstance(mediation_state, dict) else {}
        requested_intention_token = _as_text(mediation_state.get("intention_token"))
        requested_time_context = _normalize_time_context(mediation_state.get("time"))
        widened_intention_requested = bool(
            requested_intention_token
            and requested_intention_token not in {"self", _LEGACY_SELF_INTENTION_TOKEN}
        )
        precinct_overlay_requested = bool(mediation_state.get("precinct_district_overlay_enabled"))
        projection_bundle = self.read_projection_bundle(
            tenant_id,
            selected_document_id=selected_document_id,
            selected_row_address=selected_row_address,
            selected_feature_id=selected_feature_id,
            attention_document_id=mediation_state.get("attention_document_id"),
            attention_node_id=mediation_state.get("attention_node_id"),
            overlay_mode=overlay_mode,
            raw_underlay_visible=raw_underlay_visible,
            project_all_documents=widened_intention_requested or precinct_overlay_requested,
            requested_intention_token=requested_intention_token,
            time_context_active=bool(requested_time_context.get("active")),
            precinct_district_overlay_enabled=precinct_overlay_requested,
            requested_time_token=_as_text(requested_time_context.get("value_token")),
        )
        normalized_request = self.normalize_mediation_request(
            projection_bundle,
            selected_document_id=selected_document_id,
            selected_row_address=selected_row_address,
            selected_feature_id=selected_feature_id,
            mediation_state=mediation_state,
        )
        mediation_surface = self.build_mediation_surface(
            projection_bundle,
            attention_document_id=normalized_request["attention_document_id"],
            attention_node_id=normalized_request["attention_node_id"],
            intention_token=normalized_request["intention_token"],
            time_context=normalized_request.get("time_context"),
            precinct_district_overlay_enabled=precinct_overlay_requested,
        )
        intention_warnings = list(normalized_request.get("intention_warnings") or [])
        if intention_warnings:
            merged_warnings = _dedupe_texts(list(mediation_surface.get("warnings") or []) + intention_warnings)
            mediation_state = dict(mediation_surface.get("mediation_state") or {})
            mediation_state["normalization_warnings"] = intention_warnings
            mediation_surface = {
                **mediation_surface,
                "warnings": merged_warnings,
                "mediation_state": mediation_state,
            }
        finalized_surface = self.finalize_selection(
            mediation_surface,
            selected_row_address=normalized_request["selected_row_address"],
            selected_feature_id=normalized_request["selected_feature_id"],
        )
        finalized_surface["authority_catalog_summary"] = dict(projection_bundle.get("authority_catalog_summary") or {})
        return finalized_surface
