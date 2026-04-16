from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.structures.hops import (
    classify_hops_coordinate_token,
    decode_hops_coordinate_token,
)
from MyCiteV2.packages.modules.domains.datum_recognition import (
    DatumRecognitionDocument,
    DatumRecognitionRow,
    DatumWorkbenchService,
)
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentPort
from MyCiteV2.packages.ports.datum_store.cts_gis_legacy_compat import (
    CTS_GIS_CANONICAL_TOOL_PUBLIC_ID,
    CTS_GIS_LEGACY_WARNING_CODE,
    canonicalize_cts_gis_sandbox_document_id,
    canonicalize_cts_gis_tool_public_id,
    is_cts_gis_legacy_sandbox_document_id,
    matches_cts_gis_sandbox_document_id,
)

_VALID_OVERLAY_MODES = frozenset({"auto", "raw_only"})
_DEFAULT_ATTENTION_NODE_ID = "3-2-3-17-77"
_DEFAULT_SUPPORTING_DOCUMENT_NAME = "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"
_DEFAULT_INTENTION_TOKEN = "descendants_depth_1_or_2"
_LEGACY_SELF_INTENTION_TOKEN = "0"
_CHILDREN_INTENTION_TOKEN = "1-0"
_BRANCH_INTENTION_PREFIX = "branch:"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_lower(value: object) -> str:
    return _as_text(value).lower()


def _address_tuple(value: object) -> tuple[int, ...]:
    token = _as_text(value)
    if not token or any(not part.isdigit() for part in token.split("-")):
        return ()
    return tuple(int(part) for part in token.split("-"))


def _node_depth(node_id: object) -> int:
    return len(_address_tuple(node_id))


def _parent_node_id(node_id: object) -> str:
    parts = _address_tuple(node_id)
    if len(parts) <= 1:
        return ""
    return "-".join(str(part) for part in parts[:-1])


def _first_non_empty(values: list[object] | tuple[object, ...]) -> str:
    for value in values:
        token = _as_text(value)
        if token:
            return token
    return ""


def _sorted_addresses(values: set[str] | list[str] | tuple[str, ...]) -> list[str]:
    return sorted(
        (_as_text(value) for value in values if _as_text(value)),
        key=lambda item: (_address_tuple(item) or (10**9,), item),
    )


def _address_is_descendant(node_id: str, *, root_node_id: str, min_extra_segments: int, max_extra_segments: int) -> bool:
    node_parts = _address_tuple(node_id)
    root_parts = _address_tuple(root_node_id)
    if not node_parts or not root_parts or len(node_parts) <= len(root_parts):
        return False
    if tuple(node_parts[: len(root_parts)]) != tuple(root_parts):
        return False
    extra_segments = len(node_parts) - len(root_parts)
    return min_extra_segments <= extra_segments <= max_extra_segments


def _binding_family(anchor_label: object) -> str:
    label = _as_lower(anchor_label)
    if "title-babelette" in label or "title-babellette" in label:
        return "title_babelette"
    if "samras" in label and ("babelette" in label or "babellette" in label):
        return "samras_babelette"
    if "hops" in label and ("babelette" in label or "babellette" in label):
        return "hops_babelette"
    return ""


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


def _decode_title_babelette(raw_value: object) -> dict[str, Any]:
    token = _as_text(raw_value)
    if not token:
        return {"state": "empty", "display_value": "", "decoded_text": ""}
    if any(ch not in {"0", "1"} for ch in token) or (len(token) % 8) != 0:
        return {"state": "invalid_binary", "display_value": token, "decoded_text": ""}
    data = bytearray(int(token[index : index + 8], 2) for index in range(0, len(token), 8))
    while data and data[-1] == 0:
        data.pop()
    if not data:
        return {"state": "decoded", "display_value": "", "decoded_text": ""}
    try:
        text = bytes(data).decode("utf-8")
        return {"state": "decoded", "display_value": text, "decoded_text": text}
    except UnicodeDecodeError:
        text = bytes(data).decode("utf-8", errors="replace")
        return {"state": "decoded_with_replacement", "display_value": text, "decoded_text": text}


def _decode_samras_babelette(raw_value: object) -> dict[str, Any]:
    token = _as_text(raw_value)
    return {
        "state": "decoded" if token else "empty",
        "display_value": token,
        "segment_count": 0 if not token else token.count("-") + 1,
    }


def _decode_hops_babelette(raw_value: object) -> dict[str, Any]:
    token = _as_text(raw_value)
    classification = classify_hops_coordinate_token(token)
    decoded = decode_hops_coordinate_token(token)
    if decoded is None:
        return {
            "state": _as_text(classification.get("classification")) or "invalid",
            "display_value": token,
            "classification": classification,
        }
    return {
        "state": "decoded",
        "display_value": ", ".join(decoded.get("pair_text") or []),
        "classification": classification,
        "decoded": decoded,
    }


def _binding_overlay(binding: Any, *, overlay_mode: str) -> dict[str, Any]:
    family = _binding_family(getattr(binding, "anchor_label", ""))
    raw_value = _as_text(getattr(binding, "value_token", ""))
    overlay_state = "raw_only"
    decoded_payload: dict[str, Any] | None = None
    display_value = raw_value
    if overlay_mode != "raw_only":
        if family == "title_babelette":
            decoded_payload = _decode_title_babelette(raw_value)
        elif family == "samras_babelette":
            decoded_payload = _decode_samras_babelette(raw_value)
        elif family == "hops_babelette":
            decoded_payload = _decode_hops_babelette(raw_value)
        if decoded_payload is not None:
            overlay_state = _as_text(decoded_payload.get("state")) or "decoded"
            display_value = _as_text(decoded_payload.get("display_value")) or raw_value
    return {
        "reference_form": _as_text(getattr(binding, "reference_form", "")),
        "normalized_reference_form": _as_text(getattr(binding, "normalized_reference_form", "")),
        "anchor_address": _as_text(getattr(binding, "anchor_address", "")),
        "anchor_label": _as_text(getattr(binding, "anchor_label", "")),
        "expected_value_kind": _as_text(getattr(binding, "expected_value_kind", "")),
        "resolution_state": _as_text(getattr(binding, "resolution_state", "")),
        "overlay_family": family or "raw_only",
        "raw_value": raw_value,
        "display_value": display_value,
        "overlay_state": overlay_state,
        "decoded_payload": decoded_payload,
    }


def _row_label_text(row: DatumRecognitionRow) -> str:
    labels = [item for item in row.labels if _as_text(item)]
    return ", ".join(labels)


def _feature_bounds(points: list[list[float]]) -> list[float] | None:
    if not points:
        return None
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]


def _coordinate_entries(row: DatumRecognitionRow) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for binding in row.reference_bindings:
        if _binding_family(binding.anchor_label) != "hops_babelette":
            continue
        decoded = decode_hops_coordinate_token(binding.value_token)
        if decoded is None:
            continue
        longitude = decoded["longitude"]
        latitude = decoded["latitude"]
        out.append(
            {
                "reference_form": binding.reference_form,
                "normalized_reference_form": binding.normalized_reference_form,
                "raw_value": binding.value_token,
                "coordinates": [longitude["value"], latitude["value"]],
                "bounds": [
                    longitude["range"][0],
                    latitude["range"][0],
                    longitude["range"][1],
                    latitude["range"][1],
                ],
                "decoded": decoded,
            }
        )
    return out


def _feature_from_row(
    *,
    document: DatumRecognitionDocument,
    row: DatumRecognitionRow,
    overlays: list[dict[str, Any]],
    coordinates: list[dict[str, Any]],
    primary_samras_node_id: str,
    profile_label: str,
    title_display: str,
) -> dict[str, Any] | None:
    if not coordinates:
        return None

    label_tokens = [label for label in row.labels if _as_text(label)]
    label_text = ", ".join(label_tokens)
    polygon_label = any(_as_lower(label).startswith("polygon_") for label in label_tokens)
    feature_id = f"{document.document_id}:{row.datum_address}"
    points = [list(entry["coordinates"]) for entry in coordinates]
    if len(points) == 1 and not polygon_label:
        geometry = {"type": "Point", "coordinates": list(points[0])}
        geometry_type = "Point"
    else:
        ring = [list(point) for point in points]
        if ring and ring[0] != ring[-1]:
            ring.append(list(ring[0]))
        geometry = {"type": "Polygon", "coordinates": [ring]}
        geometry_type = "Polygon"

    return {
        "feature_id": feature_id,
        "row_address": row.datum_address,
        "label_text": label_text,
        "labels": label_tokens,
        "geometry_type": geometry_type,
        "bounds": _feature_bounds(points),
        "title_display": title_display,
        "samras_node_id": primary_samras_node_id,
        "profile_label": profile_label,
        "diagnostic_states": list(row.diagnostic_states),
        "feature": {
            "type": "Feature",
            "id": feature_id,
            "geometry": geometry,
            "properties": {
                "row_address": row.datum_address,
                "label_text": label_text,
                "labels": label_tokens,
                "title_display": title_display,
                "samras_node_id": primary_samras_node_id,
                "profile_label": profile_label,
                "diagnostic_states": list(row.diagnostic_states),
            },
        },
    }


def _linked_row_addresses(row: DatumRecognitionRow, row_address_set: set[str]) -> list[str]:
    if not isinstance(row.raw, list) or not row.raw or not isinstance(row.raw[0], list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for token in row.raw[0]:
        address = _as_text(token)
        if address == row.datum_address or address not in row_address_set or address in seen:
            continue
        if not _address_tuple(address):
            continue
        out.append(address)
        seen.add(address)
    return out


def _row_projection(
    document: DatumRecognitionDocument,
    row: DatumRecognitionRow,
    *,
    overlay_mode: str,
    row_address_set: set[str],
) -> dict[str, Any]:
    overlays = [_binding_overlay(binding, overlay_mode=overlay_mode) for binding in row.reference_bindings]
    coordinates = _coordinate_entries(row)
    samras_node_ids = [
        _as_text(item.get("display_value")) or _as_text(item.get("raw_value"))
        for item in overlays
        if _as_text(item.get("overlay_family")) == "samras_babelette"
        and (_as_text(item.get("display_value")) or _as_text(item.get("raw_value")))
    ]
    title_display = _first_non_empty(
        [
            item.get("display_value")
            for item in overlays
            if _as_text(item.get("overlay_family")) == "title_babelette"
        ]
    )
    label_text = _row_label_text(row)
    primary_samras_node_id = samras_node_ids[0] if samras_node_ids else ""
    profile_label = _first_non_empty([title_display, label_text, primary_samras_node_id, row.datum_address])
    feature = _feature_from_row(
        document=document,
        row=row,
        overlays=overlays,
        coordinates=coordinates,
        primary_samras_node_id=primary_samras_node_id,
        profile_label=profile_label,
        title_display=title_display,
    )
    return {
        "datum_address": row.datum_address,
        "labels": list(row.labels),
        "label_text": label_text,
        "recognized_family": row.recognized_family,
        "recognized_anchor": row.recognized_anchor,
        "primary_value_token": row.primary_value_token,
        "diagnostic_states": list(row.diagnostic_states),
        "raw": row.raw,
        "reference_bindings": [binding.to_dict() for binding in row.reference_bindings],
        "overlay_values": overlays,
        "projectable_coordinates": coordinates,
        "feature_ids": [] if feature is None else [feature["feature_id"]],
        "linked_row_addresses": _linked_row_addresses(row, row_address_set),
        "samras_node_id": primary_samras_node_id,
        "samras_node_ids": list(samras_node_ids),
        "title_display": title_display,
        "profile_label": profile_label,
        "depth": _node_depth(primary_samras_node_id),
        "direct_feature": feature,
    }


def _reachable_row_addresses(start_row_address: str, row_index: dict[str, dict[str, Any]]) -> list[str]:
    if start_row_address not in row_index:
        return []
    visited: set[str] = set()
    stack = [start_row_address]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        for linked in list((row_index.get(current) or {}).get("linked_row_addresses") or []):
            if linked not in visited and linked in row_index:
                stack.append(linked)
    return _sorted_addresses(visited)


def _profile_sort_key(profile: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        int(profile.get("depth") or 10**6),
        0 if profile.get("child_count") else 1,
        0 if profile.get("feature_count") else 1,
        _as_text(profile.get("node_id")),
    )


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


def _placeholder_profile_summary(node_id: str, *, relation: str = "") -> dict[str, Any]:
    return {
        "node_id": _as_text(node_id),
        "profile_label": _as_text(node_id) or "profile",
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


def _build_document_projection(document: DatumRecognitionDocument, *, overlay_mode: str) -> dict[str, Any]:
    row_address_set = {row.datum_address for row in document.rows}
    row_views = [_row_projection(document, row, overlay_mode=overlay_mode, row_address_set=row_address_set) for row in document.rows]
    row_index = {row["datum_address"]: row for row in row_views}
    feature_index = {
        row["direct_feature"]["feature_id"]: row["direct_feature"]
        for row in row_views
        if row.get("direct_feature") is not None
    }
    profiles_by_node: dict[str, dict[str, Any]] = {}
    for row in row_views:
        node_id = _as_text(row.get("samras_node_id"))
        if not node_id:
            continue
        reachable_addresses = _reachable_row_addresses(row["datum_address"], row_index)
        feature_ids: list[str] = []
        reachable_rows: list[dict[str, Any]] = []
        for address in reachable_addresses:
            linked_row = row_index[address]
            reachable_rows.append(linked_row)
            for feature_id in list(linked_row.get("feature_ids") or []):
                if feature_id not in feature_ids:
                    feature_ids.append(feature_id)
        candidate = {
            "node_id": node_id,
            "row_address": row["datum_address"],
            "profile_label": row["profile_label"],
            "title_display": row["title_display"],
            "labels": list(row.get("labels") or []),
            "parent_node_id": _parent_node_id(node_id),
            "depth": _node_depth(node_id),
            "document_id": document.document_id,
            "diagnostic_states": list(row.get("diagnostic_states") or []),
            "feature_ids": list(feature_ids),
            "feature_count": len(feature_ids),
            "row_addresses": list(reachable_addresses),
            "bound_node_ids": list(row.get("samras_node_ids") or [])[1:],
            "reachable_rows": reachable_rows,
        }
        existing = profiles_by_node.get(node_id)
        if existing is None:
            profiles_by_node[node_id] = candidate
            continue
        existing["feature_ids"] = _sorted_addresses(set(existing["feature_ids"]) | set(candidate["feature_ids"]))
        existing["feature_count"] = len(existing["feature_ids"])
        existing["row_addresses"] = _sorted_addresses(set(existing["row_addresses"]) | set(candidate["row_addresses"]))
        existing["bound_node_ids"] = _sorted_addresses(set(existing["bound_node_ids"]) | set(candidate["bound_node_ids"]))
        if candidate["feature_count"] > existing["feature_count"] or (
            candidate["feature_count"] == existing["feature_count"]
            and candidate["depth"] < existing["depth"]
        ):
            existing["row_address"] = candidate["row_address"]
            existing["profile_label"] = candidate["profile_label"]
            existing["title_display"] = candidate["title_display"]
            existing["labels"] = candidate["labels"]
            existing["diagnostic_states"] = candidate["diagnostic_states"]

    children_by_parent: dict[str, list[str]] = {}
    row_profile_index: dict[str, list[str]] = {}
    feature_profile_index: dict[str, list[str]] = {}
    for profile in profiles_by_node.values():
        children_by_parent.setdefault(profile["parent_node_id"], []).append(profile["node_id"])
        for address in profile["row_addresses"]:
            row_profile_index.setdefault(address, []).append(profile["node_id"])
        for feature_id in profile["feature_ids"]:
            feature_profile_index.setdefault(feature_id, []).append(profile["node_id"])
    for node_ids in children_by_parent.values():
        node_ids.sort(key=lambda node_id: (_node_depth(node_id), node_id))
    for node_id, profile in profiles_by_node.items():
        profile["child_count"] = len(children_by_parent.get(node_id, []))
        profile["children"] = list(children_by_parent.get(node_id, []))

    document_summary = document.to_summary_dict()
    document_summary["projectable_feature_count"] = len(feature_index)
    document_summary["projection_state"] = "projectable" if feature_index else "inspect_only"
    document_summary["profile_count"] = len(profiles_by_node)
    default_attention_node_id = ""
    sorted_profiles = sorted(profiles_by_node.values(), key=_profile_sort_key)
    if _DEFAULT_ATTENTION_NODE_ID in profiles_by_node:
        default_attention_node_id = _DEFAULT_ATTENTION_NODE_ID
    elif sorted_profiles:
        default_attention_node_id = _as_text(sorted_profiles[0]["node_id"])
    document_summary["default_attention_node_id"] = default_attention_node_id
    document_summary["samras_seed_status"] = "ready" if _DEFAULT_ATTENTION_NODE_ID in profiles_by_node else "missing"

    return {
        "document": document,
        "document_summary": document_summary,
        "row_views": row_views,
        "row_index": row_index,
        "feature_index": feature_index,
        "profiles": sorted_profiles,
        "profile_index": profiles_by_node,
        "children_by_parent": children_by_parent,
        "row_profile_index": row_profile_index,
        "feature_profile_index": feature_profile_index,
        "default_attention_node_id": default_attention_node_id,
    }


def _normalize_intention_token(document_bundle: dict[str, Any], attention_node_id: str, requested: object) -> str:
    token = _as_text(requested) or _DEFAULT_INTENTION_TOKEN
    children = list((document_bundle.get("children_by_parent") or {}).get(attention_node_id, []))
    descendants_depth_1_or_2 = _descendant_profiles(
        document_bundle,
        attention_node_id=attention_node_id,
        min_extra_segments=1,
        max_extra_segments=2,
    )
    if token == _LEGACY_SELF_INTENTION_TOKEN:
        return token
    if token == _DEFAULT_INTENTION_TOKEN:
        return token if descendants_depth_1_or_2 else _LEGACY_SELF_INTENTION_TOKEN
    if token == "self":
        return _LEGACY_SELF_INTENTION_TOKEN
    if token == "children":
        return _CHILDREN_INTENTION_TOKEN if children else _LEGACY_SELF_INTENTION_TOKEN
    if token == _CHILDREN_INTENTION_TOKEN:
        return token if children else _LEGACY_SELF_INTENTION_TOKEN
    if token.startswith(_BRANCH_INTENTION_PREFIX):
        branch_node_id = _as_text(token[len(_BRANCH_INTENTION_PREFIX) :])
        if branch_node_id in children:
            return token
    return _DEFAULT_INTENTION_TOKEN if descendants_depth_1_or_2 else _LEGACY_SELF_INTENTION_TOKEN


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
    out = [
        {
            "token": _LEGACY_SELF_INTENTION_TOKEN,
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
                "token": _DEFAULT_INTENTION_TOKEN,
                "kind": "descendants_depth_1_or_2",
                "label": "Descendants depth 1 or 2",
                "target_node_id": attention_node_id,
                "row_count": sum(len(profile.get("row_addresses") or []) for profile in descendants_depth_1_or_2),
                "feature_count": sum(int(profile.get("feature_count") or 0) for profile in descendants_depth_1_or_2),
                "profile_count": len(descendants_depth_1_or_2),
            },
        )
    if children:
        out.append(
            {
                "token": _CHILDREN_INTENTION_TOKEN,
                "kind": "children",
                "label": "Immediate children",
                "target_node_id": attention_node_id,
                "row_count": sum(len(child.get("row_addresses") or []) for child in children),
                "feature_count": sum(int(child.get("feature_count") or 0) for child in children),
                "profile_count": len(children),
            }
        )
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
    def __init__(self, datum_store: AuthoritativeDatumDocumentPort | None) -> None:
        self._datum_store = datum_store

    def read_projection_bundle(
        self,
        tenant_id: str,
        *,
        selected_document_id: object = "",
        selected_row_address: object = "",
        selected_feature_id: object = "",
        attention_document_id: object = "",
        overlay_mode: object = "auto",
        raw_underlay_visible: object = False,
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
                and canonicalize_cts_gis_tool_public_id(document.tool_id) == CTS_GIS_CANONICAL_TOOL_PUBLIC_ID
            )
        ]
        requested_document_id_raw = _as_text(attention_document_id) or _as_text(selected_document_id)
        requested_document_id = canonicalize_cts_gis_sandbox_document_id(requested_document_id_raw)
        requested_row_address = _as_text(selected_row_address)
        requested_feature_id = _as_text(selected_feature_id)
        project_all_documents = bool((requested_row_address or requested_feature_id) and not requested_document_id)
        target_document = None
        if requested_document_id:
            for document in cts_gis_documents:
                if matches_cts_gis_sandbox_document_id(document.document_id, requested_document_id):
                    target_document = document
                    break
        if target_document is None and cts_gis_documents:
            for document in cts_gis_documents:
                if _as_text(document.document_name) == _DEFAULT_SUPPORTING_DOCUMENT_NAME:
                    target_document = document
                    break
        if target_document is None and cts_gis_documents:
            target_document = cts_gis_documents[0]

        document_catalog = []
        for document in cts_gis_documents:
            summary = document.to_summary_dict()
            summary.setdefault("projectable_feature_count", 0)
            summary.setdefault("projection_state", "pending")
            summary.setdefault("profile_count", 0)
            summary.setdefault("default_attention_node_id", "")
            summary["selected"] = _as_text(summary.get("document_id")) == _as_text(getattr(target_document, "document_id", ""))
            document_catalog.append(summary)

        target_documents = cts_gis_documents if project_all_documents else ([] if target_document is None else [target_document])
        documents = [
            _build_document_projection(document, overlay_mode=normalized_overlay_mode) for document in target_documents
        ]
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
        if is_cts_gis_legacy_sandbox_document_id(requested_document_id_raw):
            warnings.append(CTS_GIS_LEGACY_WARNING_CODE)
        if any(is_cts_gis_legacy_sandbox_document_id(document.document_id) for document in cts_gis_documents):
            warnings.append(CTS_GIS_LEGACY_WARNING_CODE)
        warnings = list(dict.fromkeys(_as_text(item) for item in warnings if _as_text(item)))
        return {
            "tenant_id": _as_text(tenant_id) or "fnd",
            "overlay_mode": normalized_overlay_mode,
            "raw_underlay_visible": normalized_raw_underlay,
            "documents": documents,
            "document_catalog": document_catalog,
            "fallback_document_summary": fallback_document_summary,
            "warnings": warnings,
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
        requested_document_id = canonicalize_cts_gis_sandbox_document_id(selected_document_id)
        requested_row_address = _as_text(selected_row_address)
        requested_feature_id = _as_text(selected_feature_id)
        mediation_state = mediation_state if isinstance(mediation_state, dict) else {}
        requested_attention_document_id = canonicalize_cts_gis_sandbox_document_id(
            mediation_state.get("attention_document_id")
        )
        requested_attention_node_id = _as_text(mediation_state.get("attention_node_id"))
        requested_intention_token = _as_text(mediation_state.get("intention_token"))

        selected_document_bundle = None
        if requested_attention_document_id:
            for document_bundle in documents:
                if matches_cts_gis_sandbox_document_id(
                    (document_bundle.get("document_summary") or {}).get("document_id"),
                    requested_attention_document_id,
                ):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None and requested_document_id:
            for document_bundle in documents:
                if matches_cts_gis_sandbox_document_id(
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
                if _as_text(document_bundle.get("default_attention_node_id")):
                    selected_document_bundle = document_bundle
                    break
        if selected_document_bundle is None and documents:
            selected_document_bundle = documents[0]

        selected_document_summary = (selected_document_bundle or {}).get("document_summary") or {}
        attention_document_id = _as_text(selected_document_summary.get("document_id"))
        profile_index = (selected_document_bundle or {}).get("profile_index") or {}
        row_profile_index = (selected_document_bundle or {}).get("row_profile_index") or {}
        feature_profile_index = (selected_document_bundle or {}).get("feature_profile_index") or {}

        attention_node_id = ""
        if requested_attention_node_id and requested_attention_node_id in profile_index:
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
            attention_node_id = _as_text((selected_document_bundle or {}).get("default_attention_node_id"))
        if not attention_node_id and profile_index:
            attention_node_id = _as_text(sorted(profile_index.keys(), key=lambda item: (_node_depth(item), item))[0])

        intention_token = _normalize_intention_token(
            selected_document_bundle or {},
            attention_node_id,
            requested_intention_token,
        )
        return {
            "attention_document_id": attention_document_id,
            "attention_node_id": attention_node_id,
            "intention_token": intention_token,
            "selected_document_id": requested_document_id,
            "selected_row_address": requested_row_address,
            "selected_feature_id": requested_feature_id,
        }

    def build_mediation_surface(
        self,
        projection_bundle: dict[str, Any],
        *,
        attention_document_id: object = "",
        attention_node_id: object = "",
        intention_token: object = _DEFAULT_INTENTION_TOKEN,
    ) -> dict[str, Any]:
        documents = list(projection_bundle.get("documents") or [])
        overlay_mode = _as_text(projection_bundle.get("overlay_mode")) or "auto"
        raw_underlay_visible = bool(projection_bundle.get("raw_underlay_visible"))
        selected_document_bundle = None
        for document_bundle in documents:
            if matches_cts_gis_sandbox_document_id(
                (document_bundle.get("document_summary") or {}).get("document_id"),
                attention_document_id,
            ):
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
                    "available_intentions": [],
                    "selection_summary": {},
                },
                "warnings": warnings,
                "_render_row_views": [],
                "_render_features": [],
                "_row_profile_index": {},
            }

        document_summary = dict(selected_document_bundle.get("document_summary") or {})
        document_summary["selected"] = True
        profile_index = selected_document_bundle.get("profile_index") or {}
        row_profile_index = selected_document_bundle.get("row_profile_index") or {}
        feature_profile_index = selected_document_bundle.get("feature_profile_index") or {}
        attention_node_id_text = _as_text(attention_node_id)
        attention_profile = profile_index.get(attention_node_id_text)
        intention_token_text = _normalize_intention_token(selected_document_bundle, attention_node_id_text, intention_token)
        available_intentions = _available_intentions(selected_document_bundle, attention_node_id_text)
        available_token_set = {option["token"] for option in available_intentions}
        if intention_token_text not in available_token_set:
            intention_token_text = _DEFAULT_INTENTION_TOKEN

        render_profiles: list[dict[str, Any]] = []
        if attention_profile is not None:
            if intention_token_text == _DEFAULT_INTENTION_TOKEN:
                render_profiles = _descendant_profiles(
                    selected_document_bundle,
                    attention_node_id=attention_node_id_text,
                    min_extra_segments=1,
                    max_extra_segments=2,
                )
            elif intention_token_text == _LEGACY_SELF_INTENTION_TOKEN:
                render_profiles = [attention_profile]
            elif intention_token_text == _CHILDREN_INTENTION_TOKEN:
                render_profiles = [
                    profile_index[node_id]
                    for node_id in list((selected_document_bundle.get("children_by_parent") or {}).get(attention_node_id_text, []))
                    if node_id in profile_index
                ]
            elif intention_token_text.startswith(_BRANCH_INTENTION_PREFIX):
                target_node_id = _as_text(intention_token_text[len(_BRANCH_INTENTION_PREFIX) :])
                target_profile = profile_index.get(target_node_id)
                if target_profile is not None:
                    render_profiles = [target_profile]
        render_row_addresses: set[str] = set()
        render_feature_ids: list[str] = []
        for profile in render_profiles:
            render_row_addresses.update(profile.get("row_addresses") or [])
            for feature_id in list(profile.get("feature_ids") or []):
                if feature_id not in render_feature_ids:
                    render_feature_ids.append(feature_id)
        row_index = selected_document_bundle.get("row_index") or {}
        ordered_render_row_addresses = [
            address
            for address in _sorted_addresses(render_row_addresses)
            if address in row_index
        ]
        render_row_views = [row_index[address] for address in ordered_render_row_addresses]
        feature_index = selected_document_bundle.get("feature_index") or {}
        render_features = [feature_index[feature_id] for feature_id in render_feature_ids if feature_id in feature_index]

        lineage: list[dict[str, Any]] = []
        for depth in range(1, _node_depth(attention_node_id_text) + 1):
            node_id = "-".join(attention_node_id_text.split("-")[:depth])
            profile = profile_index.get(node_id)
            if profile is None:
                lineage.append(_placeholder_profile_summary(node_id))
            else:
                lineage.append(
                    _profile_public_summary(profile, selected=node_id == attention_node_id_text)
                )

        children = [
            _profile_public_summary(profile_index[node_id])
            for node_id in list((selected_document_bundle.get("children_by_parent") or {}).get(attention_node_id_text, []))
            if node_id in profile_index
        ]
        related_profiles: list[dict[str, Any]] = []
        related_seen: set[str] = set()
        for bound_node_id in list((attention_profile or {}).get("bound_node_ids") or []):
            if bound_node_id in related_seen:
                continue
            related_seen.add(bound_node_id)
            profile = profile_index.get(bound_node_id)
            if profile is None:
                related_profiles.append(_placeholder_profile_summary(bound_node_id, relation="bound_profile"))
            else:
                related_profiles.append(_profile_public_summary(profile, relation="bound_profile"))
        parent_node_id = _as_text((attention_profile or {}).get("parent_node_id"))
        for sibling_node_id in list((selected_document_bundle.get("children_by_parent") or {}).get(parent_node_id, [])):
            if sibling_node_id == attention_node_id_text or sibling_node_id in related_seen or sibling_node_id not in profile_index:
                continue
            related_seen.add(sibling_node_id)
            related_profiles.append(_profile_public_summary(profile_index[sibling_node_id], relation="sibling"))

        feature_collection_features = []
        for feature in render_features:
            owner_profile = None
            for node_id in list(feature_profile_index.get(feature["feature_id"]) or []):
                if node_id in {_as_text(profile.get("node_id")) for profile in render_profiles}:
                    owner_profile = profile_index.get(node_id)
                    break
            if owner_profile is None:
                for node_id in list(feature_profile_index.get(feature["feature_id"]) or []):
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
            feature_properties["attention_member"] = (
                _as_text((owner_profile or {}).get("node_id")) == attention_node_id_text
            )
            feature_payload["properties"] = feature_properties
            feature_collection_features.append(feature_payload)

        map_bounds = _feature_bounds(
            [
                point
                for feature in render_features
                for point in (
                    [feature["feature"]["geometry"]["coordinates"]]
                    if feature["geometry_type"] == "Point"
                    else feature["feature"]["geometry"]["coordinates"][0]
                )
            ]
        )
        projection_state = "projectable" if render_features else "inspect_only"
        warnings = list(projection_bundle.get("warnings") or [])
        document = selected_document_bundle.get("document")
        if document is not None:
            warnings.extend(list(document.warnings))
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
                if intention_token_text == _DEFAULT_INTENTION_TOKEN
                else "self"
                if intention_token_text == _LEGACY_SELF_INTENTION_TOKEN
                else "children"
                if intention_token_text == _CHILDREN_INTENTION_TOKEN
                else "branch"
            ),
            "render_profile_count": len(render_profiles),
            "render_row_count": len(render_row_views),
            "render_feature_count": len(render_features),
            "render_profile_labels": [
                _as_text(profile.get("profile_label")) or _as_text(profile.get("node_id"))
                for profile in render_profiles
            ],
        }

        return {
            "document_catalog": document_catalog,
            "selected_document": document_summary,
            "attention_profile": None
            if attention_profile is None
            else _profile_public_summary(attention_profile, selected=True),
            "lineage": lineage,
            "children": children,
            "render_profiles": [
                _profile_public_summary(
                    profile,
                    relation="render_profile",
                    selected=_as_text(profile.get("node_id")) == attention_node_id_text,
                )
                for profile in render_profiles
            ],
            "related_profiles": related_profiles,
            "render_set_summary": render_set_summary,
            "map_projection": {
                "projection_state": projection_state,
                "feature_count": len(render_features),
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
                "available_intentions": [
                    {
                        **option,
                        "active": _as_text(option.get("token")) == intention_token_text,
                    }
                    for option in available_intentions
                ],
                "selection_summary": {},
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
        projection_bundle = self.read_projection_bundle(
            tenant_id,
            selected_document_id=selected_document_id,
            selected_row_address=selected_row_address,
            selected_feature_id=selected_feature_id,
            attention_document_id=(mediation_state or {}).get("attention_document_id") if isinstance(mediation_state, dict) else "",
            overlay_mode=overlay_mode,
            raw_underlay_visible=raw_underlay_visible,
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
        )
        return self.finalize_selection(
            mediation_surface,
            selected_row_address=normalized_request["selected_row_address"],
            selected_feature_id=normalized_request["selected_feature_id"],
        )
