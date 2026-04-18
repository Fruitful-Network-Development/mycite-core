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

_VALID_OVERLAY_MODES = frozenset({"auto", "raw_only"})
_CTS_GIS_CANONICAL_TOOL_PUBLIC_ID = "cts_gis"
_CTS_GIS_CANONICAL_DOCUMENT_PREFIX = "sandbox:cts_gis:"
_DEFAULT_ATTENTION_NODE_ID = "3-2-3-17-77"
_DEFAULT_ATTENTION_PROFILE_LABEL = "summit_county"
_DEFAULT_SUPPORTING_DOCUMENT_NAME = "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"
_DEFAULT_PROJECTION_DOCUMENT_SUFFIX = f".{_DEFAULT_ATTENTION_NODE_ID}.json"
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


def _geometry_points(geometry: dict[str, Any]) -> list[list[float]]:
    geometry_type = _as_text((geometry or {}).get("type"))
    coordinates = (geometry or {}).get("coordinates")
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


def _feature_bounds_from_geometry(geometry: dict[str, Any]) -> list[float] | None:
    return _feature_bounds(_geometry_points(geometry))


def _dedupe_texts(values: list[object] | tuple[object, ...]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = _as_text(value)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _row_declared_coordinate_count(row_address: object) -> int:
    parts = _address_tuple(row_address)
    if len(parts) == 3 and parts[0] == 4:
        return int(parts[1])
    return 0


def _decoded_coordinate_payload(
    token: str,
    *,
    longitude: float,
    latitude: float,
    encoding: str,
) -> dict[str, Any]:
    return {
        "encoding": encoding,
        "address": token,
        "segments": [int(piece) for piece in token.split("-") if piece.isdigit()],
        "longitude": {
            "value": float(longitude),
            "text": f"{float(longitude):.13f}",
            "range": [float(longitude), float(longitude)],
        },
        "latitude": {
            "value": float(latitude),
            "text": f"{float(latitude):.13f}",
            "range": [float(latitude), float(latitude)],
        },
        "pair_text": [f"{float(longitude):.13f}", f"{float(latitude):.13f}"],
    }


def _primary_samras_node_id(row: DatumRecognitionRow) -> str:
    for binding in row.reference_bindings:
        if _binding_family(binding.anchor_label) == "samras_babelette":
            return _as_text(binding.value_token)
    return ""


def _geometry_polygons(geometry: dict[str, Any]) -> list[list[list[list[float]]]]:
    geometry_type = _as_text((geometry or {}).get("type"))
    coordinates = (geometry or {}).get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return [[
            [
                [float(point[0]), float(point[1])]
                for point in ring
                if isinstance(point, list) and len(point) >= 2
            ]
            for ring in coordinates
            if isinstance(ring, list)
        ]]
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return [
            [
                [
                    [float(point[0]), float(point[1])]
                    for point in ring
                    if isinstance(point, list) and len(point) >= 2
                ]
                for ring in polygon
                if isinstance(ring, list)
            ]
            for polygon in coordinates
            if isinstance(polygon, list)
        ]
    return []


def _row_polygon_groups(row_address: str, raw_row_index: dict[str, DatumRecognitionRow]) -> list[list[str]]:
    row = raw_row_index.get(row_address)
    if row is None:
        return []
    family = _row_family(row_address)
    linked = _linked_row_addresses(row, set(raw_row_index))
    if family == "4":
        return [[row_address]]
    if family == "5":
        rings = [address for address in linked if address in raw_row_index and _row_family(address) == "4"]
        return [rings] if rings else []
    if family == "6":
        polygons: list[list[str]] = []
        for address in linked:
            if address not in raw_row_index:
                continue
            if _row_family(address) == "5":
                polygons.extend(_row_polygon_groups(address, raw_row_index))
            elif _row_family(address) == "4":
                polygons.append([address])
        return polygons
    if family == "7":
        polygons = []
        for address in linked:
            if address not in raw_row_index or _row_family(address) not in {"6", "5", "4"}:
                continue
            polygons.extend(_row_polygon_groups(address, raw_row_index))
        return polygons
    return []


def _normalized_reference_ring(ring: list[list[float]], *, expected_count: int) -> list[list[float]]:
    points = [
        [float(point[0]), float(point[1])]
        for point in ring
        if isinstance(point, list) and len(point) >= 2
    ]
    if not points:
        return []
    if expected_count <= 0:
        return points
    if len(points) == expected_count:
        return points
    if len(points) > 1 and points[0] == points[-1] and len(points) - 1 == expected_count:
        return points[:-1]
    if len(points) > 1 and points[0] != points[-1] and len(points) + 1 == expected_count:
        return points + [list(points[0])]
    return []


def _build_cts_gis_coordinate_authority(document: DatumRecognitionDocument) -> dict[str, Any]:
    metadata = dict(document.document_metadata or {})
    payload = metadata.get("reference_geojson")
    expected_node_id = _as_text(metadata.get("reference_geojson_node_id"))
    authority: dict[str, Any] = {
        "node_id": expected_node_id,
        "row_coordinate_map": {},
        "warnings": [],
    }
    if not isinstance(payload, dict) or not expected_node_id:
        return authority

    raw_row_index = {row.datum_address: row for row in document.rows}
    owner_row = next(
        (row for row in document.rows if _primary_samras_node_id(row) == expected_node_id and _row_family(row.datum_address) == "7"),
        None,
    )
    if owner_row is None:
        authority["warnings"] = [
            f"{document.document_name} carries reference GeoJSON for {expected_node_id}, but no matching 7-row binding was found."
        ]
        return authority

    polygon_groups = _row_polygon_groups(owner_row.datum_address, raw_row_index)
    reference_polygons: list[list[list[list[float]]]] = []
    payload_type = _as_text(payload.get("type"))
    if payload_type == "FeatureCollection":
        features = [item for item in list(payload.get("features") or []) if isinstance(item, dict)]
    elif payload_type == "Feature":
        features = [payload]
    else:
        features = []
    for feature in features:
        reference_polygons.extend(_geometry_polygons(dict(feature.get("geometry") or {})))

    warnings: list[str] = []
    if len(reference_polygons) != len(polygon_groups):
        warnings.append(
            f"{document.document_name} reference GeoJSON carries {len(reference_polygons)} polygon members, "
            f"but the HOPS row chain resolves {len(polygon_groups)}."
        )

    row_coordinate_map: dict[str, list[list[float]]] = {}
    for polygon_index, (row_group, reference_polygon) in enumerate(
        zip(polygon_groups, reference_polygons),
        start=1,
    ):
        if len(row_group) != len(reference_polygon):
            warnings.append(
                f"{document.document_name} polygon {polygon_index} carries {len(reference_polygon)} rings, "
                f"but the HOPS row chain resolves {len(row_group)}."
            )
            continue
        for ring_index, (row_address, reference_ring) in enumerate(zip(row_group, reference_polygon), start=1):
            normalized_ring = _normalized_reference_ring(
                reference_ring,
                expected_count=_row_declared_coordinate_count(row_address),
            )
            if not normalized_ring:
                warnings.append(
                    f"{document.document_name} ring {polygon_index}.{ring_index} did not align with {row_address}."
                )
                continue
            row_coordinate_map[row_address] = normalized_ring

    authority["row_coordinate_map"] = row_coordinate_map
    authority["warnings"] = _dedupe_texts(warnings)
    return authority


def _coordinate_projection(
    row: DatumRecognitionRow,
    *,
    coordinate_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapped_ring = list(((coordinate_authority or {}).get("row_coordinate_map") or {}).get(row.datum_address) or [])
    hops_bindings = [
        binding for binding in row.reference_bindings if _binding_family(binding.anchor_label) == "hops_babelette"
    ]
    if not hops_bindings:
        return {
            "entries": [],
            "reference_binding_count": 0,
            "decoded_coordinate_count": 0,
            "failed_token_count": 0,
            "projection_source": "none",
            "warnings": [],
        }
    out: list[dict[str, Any]] = []
    warnings: list[str] = []
    reference_binding_count = 0
    for binding in hops_bindings:
        binding_index = reference_binding_count
        reference_binding_count += 1
        token = _as_text(binding.value_token)
        decoded = None
        if binding_index < len(mapped_ring):
            decoded = _decoded_coordinate_payload(
                token,
                longitude=float(mapped_ring[binding_index][0]),
                latitude=float(mapped_ring[binding_index][1]),
                encoding="cts_gis_parity_hops",
            )
        else:
            decoded = decode_hops_coordinate_token(token)
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

    declared_coordinate_count = _row_declared_coordinate_count(row.datum_address)
    if declared_coordinate_count and declared_coordinate_count != reference_binding_count:
        warnings.append(
            f"{row.datum_address} declares {declared_coordinate_count} HOPS vertices but carries {reference_binding_count}."
        )
    if mapped_ring and len(mapped_ring) != reference_binding_count:
        warnings.append(
            f"{row.datum_address} parity authority mapped {len(mapped_ring)} coordinates for {reference_binding_count} HOPS bindings."
        )
    decoded_coordinate_count = len(out)
    failed_token_count = max(reference_binding_count - decoded_coordinate_count, 0)
    if reference_binding_count and failed_token_count:
        warnings.append(
            f"{row.datum_address} decoded {decoded_coordinate_count}/{reference_binding_count} HOPS coordinates."
        )
    return {
        "entries": out,
        "reference_binding_count": reference_binding_count,
        "decoded_coordinate_count": decoded_coordinate_count,
        "failed_token_count": failed_token_count,
        "projection_source": "hops" if decoded_coordinate_count else "none",
        "warnings": _dedupe_texts(warnings),
    }


def _feature_from_row(
    *,
    document: DatumRecognitionDocument,
    row: DatumRecognitionRow,
    overlays: list[dict[str, Any]],
    coordinates: list[dict[str, Any]],
    primary_samras_node_id: str,
    profile_label: str,
    title_display: str,
    projection_source: str = "none",
    decode_summary: dict[str, Any] | None = None,
    projection_warnings: list[str] | None = None,
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
        "projection_source": projection_source,
        "decode_summary": dict(decode_summary or {}),
        "projection_warnings": list(projection_warnings or []),
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
                "projection_source": projection_source,
                "decode_summary": dict(decode_summary or {}),
                "projection_warnings": list(projection_warnings or []),
            },
        },
    }


def _feature_from_geometry(
    *,
    document: DatumRecognitionDocument,
    feature_id: str,
    row_address: str,
    geometry: dict[str, Any],
    label_text: str,
    labels: list[str],
    diagnostic_states: list[str],
    primary_samras_node_id: str,
    profile_label: str,
    title_display: str,
    properties_extra: dict[str, Any] | None = None,
    projection_source: str = "none",
    decode_summary: dict[str, Any] | None = None,
    projection_warnings: list[str] | None = None,
) -> dict[str, Any] | None:
    geometry_type = _as_text((geometry or {}).get("type"))
    if geometry_type not in {"Point", "Polygon", "MultiPolygon"}:
        return None
    geometry_points = _geometry_points(geometry)
    if not geometry_points:
        return None
    feature_properties = {
        **dict(properties_extra or {}),
        "row_address": row_address,
        "label_text": label_text,
        "labels": list(labels),
        "title_display": title_display,
        "samras_node_id": primary_samras_node_id,
        "profile_label": profile_label,
        "diagnostic_states": list(diagnostic_states),
        "projection_source": projection_source,
        "decode_summary": dict(decode_summary or {}),
        "projection_warnings": list(projection_warnings or []),
    }
    return {
        "feature_id": feature_id,
        "row_address": row_address,
        "label_text": label_text,
        "labels": list(labels),
        "geometry_type": geometry_type,
        "bounds": _feature_bounds(geometry_points),
        "title_display": title_display,
        "samras_node_id": primary_samras_node_id,
        "profile_label": profile_label,
        "diagnostic_states": list(diagnostic_states),
        "projection_source": projection_source,
        "decode_summary": dict(decode_summary or {}),
        "projection_warnings": list(projection_warnings or []),
        "feature": {
            "type": "Feature",
            "id": feature_id,
            "geometry": geometry,
            "properties": feature_properties,
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
    coordinate_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overlays = [_binding_overlay(binding, overlay_mode=overlay_mode) for binding in row.reference_bindings]
    coordinate_projection = _coordinate_projection(row, coordinate_authority=coordinate_authority)
    coordinates = list(coordinate_projection.get("entries") or [])
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
        projection_source=_as_text(coordinate_projection.get("projection_source")) or "none",
        decode_summary={
            "reference_binding_count": int(coordinate_projection.get("reference_binding_count") or 0),
            "decoded_coordinate_count": int(coordinate_projection.get("decoded_coordinate_count") or 0),
            "failed_token_count": int(coordinate_projection.get("failed_token_count") or 0),
        },
        projection_warnings=list(coordinate_projection.get("warnings") or []),
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
        "reference_binding_count": int(coordinate_projection.get("reference_binding_count") or 0),
        "decoded_coordinate_count": int(coordinate_projection.get("decoded_coordinate_count") or 0),
        "failed_token_count": int(coordinate_projection.get("failed_token_count") or 0),
        "coordinate_projection_source": _as_text(coordinate_projection.get("projection_source")) or "none",
        "coordinate_warnings": list(coordinate_projection.get("warnings") or []),
        # Profile features are attached at the 7 -> 6 -> 5 -> 4 chain during
        # document projection so Garland operates on profile geometry rather than
        # raw coordinate rows.
        "feature_ids": [],
        "linked_row_addresses": _linked_row_addresses(row, row_address_set),
        "samras_node_id": primary_samras_node_id,
        "samras_node_ids": list(samras_node_ids),
        "title_display": title_display,
        "profile_label": profile_label,
        "depth": _node_depth(primary_samras_node_id),
        "direct_feature": feature,
    }


def _row_family(row_address: str) -> str:
    return _as_text(row_address).split("-", 1)[0]


def _coordinate_ring(row: dict[str, Any]) -> list[list[float]]:
    points = [list(entry["coordinates"]) for entry in list(row.get("projectable_coordinates") or [])]
    if len(points) < 2:
        return []
    ring = [list(point) for point in points]
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return ring if len(ring) >= 4 else []


def _geometry_from_row_address(row_address: str, row_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    row = row_index.get(row_address)
    if row is None:
        return None
    family = _row_family(row_address)
    if family == "4":
        points = [list(entry["coordinates"]) for entry in list(row.get("projectable_coordinates") or [])]
        if not points:
            return None
        if len(points) == 1:
            return {"type": "Point", "coordinates": list(points[0])}
        ring = _coordinate_ring(row)
        return None if not ring else {"type": "Polygon", "coordinates": [ring]}

    if family == "5":
        rings = [
            ring
            for address in list(row.get("linked_row_addresses") or [])
            if address in row_index and _row_family(address) == "4"
            for ring in [_coordinate_ring(row_index[address])]
            if ring
        ]
        return None if not rings else {"type": "Polygon", "coordinates": rings}

    if family == "6":
        polygons: list[list[list[list[float]]]] = []
        child_addresses = [
            address
            for address in list(row.get("linked_row_addresses") or [])
            if address in row_index and _row_family(address) in {"5", "4"}
        ]
        for address in child_addresses:
            child_geometry = _geometry_from_row_address(address, row_index)
            geometry_type = _as_text((child_geometry or {}).get("type"))
            if geometry_type == "Polygon":
                polygons.append(list(child_geometry.get("coordinates") or []))
            elif geometry_type == "MultiPolygon":
                polygons.extend(list(child_geometry.get("coordinates") or []))
            elif geometry_type == "Point" and len(child_addresses) == 1:
                return child_geometry
        if not polygons:
            return None
        if len(polygons) == 1:
            return {"type": "Polygon", "coordinates": polygons[0]}
        return {"type": "MultiPolygon", "coordinates": polygons}

    if family == "7":
        for address in list(row.get("linked_row_addresses") or []):
            if address not in row_index or _row_family(address) not in {"6", "5", "4"}:
                continue
            geometry = _geometry_from_row_address(address, row_index)
            if geometry is not None:
                return geometry
    return None


def _projection_summary_for_row_addresses(
    row_addresses: list[str],
    row_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reference_binding_count = 0
    decoded_coordinate_count = 0
    failed_token_count = 0
    warnings: list[str] = []
    for row_address in row_addresses:
        row = row_index.get(row_address)
        if row is None or _row_family(row_address) != "4":
            continue
        reference_binding_count += int(row.get("reference_binding_count") or 0)
        decoded_coordinate_count += int(row.get("decoded_coordinate_count") or 0)
        failed_token_count += int(row.get("failed_token_count") or 0)
        warnings.extend(list(row.get("coordinate_warnings") or []))
    return {
        "reference_binding_count": reference_binding_count,
        "decoded_coordinate_count": decoded_coordinate_count,
        "failed_token_count": failed_token_count,
        "warnings": _dedupe_texts(warnings),
    }


def _reference_geojson_profile_features(
    document: DatumRecognitionDocument,
    *,
    owner_row: dict[str, Any],
    decode_summary: dict[str, Any] | None = None,
    projection_warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    metadata = dict(document.document_metadata or {})
    expected_node_id = _as_text(metadata.get("reference_geojson_node_id"))
    owner_node_id = _as_text(owner_row.get("samras_node_id"))
    if expected_node_id and expected_node_id != owner_node_id:
        return []

    payload = metadata.get("reference_geojson")
    if not isinstance(payload, dict):
        return []

    payload_type = _as_text(payload.get("type"))
    if payload_type == "FeatureCollection":
        candidate_features = [item for item in list(payload.get("features") or []) if isinstance(item, dict)]
    elif payload_type == "Feature":
        candidate_features = [payload]
    else:
        return []

    out: list[dict[str, Any]] = []
    for index, feature_payload in enumerate(candidate_features, start=1):
        geometry = dict(feature_payload.get("geometry") or {})
        properties = dict(feature_payload.get("properties") or {})
        label_text = _first_non_empty(
            [
                properties.get("community_name"),
                properties.get("municipality"),
                properties.get("twp_name"),
                owner_row.get("label_text"),
                owner_row.get("profile_label"),
                owner_node_id,
            ]
        )
        profile_label = _first_non_empty(
            [owner_row.get("profile_label"), properties.get("community_name"), label_text, owner_node_id]
        )
        title_display = _first_non_empty(
            [owner_row.get("title_display"), properties.get("community_name"), label_text, profile_label]
        )
        warnings = _dedupe_texts(
            list(projection_warnings or [])
            + [f"{owner_row['datum_address']} fell back to reference GeoJSON geometry."]
        )
        feature = _feature_from_geometry(
            document=document,
            feature_id=f"{document.document_id}:{owner_row['datum_address']}:{index}",
            row_address=_as_text(owner_row.get("datum_address")),
            geometry=geometry,
            label_text=label_text,
            labels=list(owner_row.get("labels") or []),
            diagnostic_states=list(owner_row.get("diagnostic_states") or []),
            primary_samras_node_id=owner_node_id,
            profile_label=profile_label,
            title_display=title_display,
            properties_extra=properties,
            projection_source="reference_geojson_fallback",
            decode_summary=dict(decode_summary or {}),
            projection_warnings=warnings,
        )
        if feature is not None:
            out.append(feature)
    return out


def _attach_feature_ids(row_addresses: list[str], feature_ids: list[str], row_index: dict[str, dict[str, Any]]) -> None:
    for row_address in row_addresses:
        row = row_index.get(row_address)
        if row is None:
            continue
        existing_ids = list(row.get("feature_ids") or [])
        for feature_id in feature_ids:
            if feature_id not in existing_ids:
                existing_ids.append(feature_id)
        row["feature_ids"] = existing_ids


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


def _build_document_projection(document: DatumRecognitionDocument, *, overlay_mode: str) -> dict[str, Any]:
    row_address_set = {row.datum_address for row in document.rows}
    coordinate_authority = _build_cts_gis_coordinate_authority(document)
    row_views = [
        _row_projection(
            document,
            row,
            overlay_mode=overlay_mode,
            row_address_set=row_address_set,
            coordinate_authority=coordinate_authority,
        )
        for row in document.rows
    ]
    row_index = {row["datum_address"]: row for row in row_views}
    feature_index: dict[str, dict[str, Any]] = {}

    for row in row_views:
        node_id = _as_text(row.get("samras_node_id"))
        if not node_id:
            continue

        reachable_addresses = _reachable_row_addresses(row["datum_address"], row_index)
        if not reachable_addresses:
            reachable_addresses = [row["datum_address"]]

        projection_summary = _projection_summary_for_row_addresses(reachable_addresses, row_index)
        profile_features: list[dict[str, Any]] = []
        geometry = _geometry_from_row_address(row["datum_address"], row_index)
        if geometry is not None:
            feature = _feature_from_geometry(
                document=document,
                feature_id=f"{document.document_id}:{row['datum_address']}",
                row_address=_as_text(row.get("datum_address")),
                geometry=geometry,
                label_text=_as_text(row.get("label_text")),
                labels=list(row.get("labels") or []),
                diagnostic_states=list(row.get("diagnostic_states") or []),
                primary_samras_node_id=node_id,
                profile_label=_as_text(row.get("profile_label")) or node_id,
                title_display=_as_text(row.get("title_display")),
                properties_extra={
                    "bound_node_ids": list(row.get("samras_node_ids") or [])[1:],
                },
                projection_source="hops",
                decode_summary={
                    "reference_binding_count": int(projection_summary.get("reference_binding_count") or 0),
                    "decoded_coordinate_count": int(projection_summary.get("decoded_coordinate_count") or 0),
                    "failed_token_count": int(projection_summary.get("failed_token_count") or 0),
                },
                projection_warnings=list(projection_summary.get("warnings") or []),
            )
            if feature is not None:
                profile_features = [feature]
        if not profile_features:
            profile_features = _reference_geojson_profile_features(
                document,
                owner_row=row,
                decode_summary={
                    "reference_binding_count": int(projection_summary.get("reference_binding_count") or 0),
                    "decoded_coordinate_count": int(projection_summary.get("decoded_coordinate_count") or 0),
                    "failed_token_count": int(projection_summary.get("failed_token_count") or 0),
                },
                projection_warnings=list(projection_summary.get("warnings") or [])
                + list(coordinate_authority.get("warnings") or []),
            )
        if not profile_features and row.get("direct_feature") is not None:
            profile_features = [row["direct_feature"]]
        if not profile_features:
            continue

        feature_ids: list[str] = []
        for feature in profile_features:
            feature_id = _as_text(feature.get("feature_id"))
            if not feature_id:
                continue
            feature_index[feature_id] = feature
            feature_ids.append(feature_id)
        if feature_ids:
            _attach_feature_ids(reachable_addresses, feature_ids, row_index)

    for row in row_views:
        if row.get("feature_ids") or row.get("direct_feature") is None:
            continue
        direct_feature = row["direct_feature"]
        feature_id = _as_text(direct_feature.get("feature_id"))
        if not feature_id:
            continue
        feature_index.setdefault(feature_id, direct_feature)
        row["feature_ids"] = [feature_id]

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
    document_summary["projection_warnings"] = _dedupe_texts(
        list(document_summary.get("warnings") or [])
        + list(coordinate_authority.get("warnings") or [])
    )

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
        "coordinate_authority": coordinate_authority,
    }


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
        attention_node_id: object = "",
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
                and _as_lower(document.tool_id) == _CTS_GIS_CANONICAL_TOOL_PUBLIC_ID
            )
        ]
        requested_document_id_raw = _as_text(attention_document_id) or _as_text(selected_document_id)
        requested_document_id = requested_document_id_raw
        requested_row_address = _as_text(selected_row_address)
        requested_feature_id = _as_text(selected_feature_id)
        requested_attention_node_id = _as_text(attention_node_id)
        project_all_documents = not requested_document_id
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
        navigation_bundle = dict(projection_bundle.get("navigation_bundle") or {})
        requested_document_id = _as_text(selected_document_id)
        requested_row_address = _as_text(selected_row_address)
        requested_feature_id = _as_text(selected_feature_id)
        mediation_state = mediation_state if isinstance(mediation_state, dict) else {}
        requested_attention_document_id = _as_text(mediation_state.get("attention_document_id"))
        requested_attention_node_id = _as_text(mediation_state.get("attention_node_id"))
        requested_intention_token = _as_text(mediation_state.get("intention_token"))

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
                    and not requested_attention_node_id
                    and not requested_row_address
                    and not requested_feature_id
                    and attention_node_id
                )
                else requested_intention_token
            ),
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
        navigation_bundle = dict(projection_bundle.get("navigation_bundle") or {})
        overlay_mode = _as_text(projection_bundle.get("overlay_mode")) or "auto"
        raw_underlay_visible = bool(projection_bundle.get("raw_underlay_visible"))
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
        profile_index = dict(navigation_bundle.get("profile_index") or {})
        row_profile_index = selected_document_bundle.get("row_profile_index") or {}
        feature_profile_index = dict(navigation_bundle.get("feature_profile_index") or {})
        attention_node_id_text = _as_text(attention_node_id)
        attention_profile = profile_index.get(attention_node_id_text)
        navigation_surface_bundle = {
            "profile_index": profile_index,
            "children_by_parent": dict(navigation_bundle.get("children_by_parent") or {}),
        }
        intention_token_text = _normalize_intention_token(navigation_surface_bundle, attention_node_id_text, intention_token)
        available_intentions = _available_intentions(navigation_surface_bundle, attention_node_id_text)
        available_token_set = {option["token"] for option in available_intentions}
        if intention_token_text not in available_token_set:
            intention_token_text = _DEFAULT_INTENTION_TOKEN

        render_profiles: list[dict[str, Any]] = []
        if intention_token_text == _DEFAULT_INTENTION_TOKEN:
            render_profiles = _descendant_profiles(
                navigation_surface_bundle,
                attention_node_id=attention_node_id_text,
                min_extra_segments=1,
                max_extra_segments=2,
            )
        elif intention_token_text == _LEGACY_SELF_INTENTION_TOKEN:
            render_profiles = [] if attention_profile is None else [attention_profile]
        elif intention_token_text == _CHILDREN_INTENTION_TOKEN:
            render_profiles = [
                profile_index[node_id]
                for node_id in list((navigation_bundle.get("children_by_parent") or {}).get(attention_node_id_text, []))
                if node_id in profile_index
            ]
        elif intention_token_text.startswith(_BRANCH_INTENTION_PREFIX):
            target_node_id = _as_text(intention_token_text[len(_BRANCH_INTENTION_PREFIX) :])
            target_profile = profile_index.get(target_node_id)
            if target_profile is not None:
                render_profiles = [target_profile]
        render_row_addresses: set[str] = set()
        render_feature_ids: list[str] = []
        selected_document_id_text = _as_text(document_summary.get("document_id"))
        for profile in render_profiles:
            if _as_text(profile.get("document_id")) == selected_document_id_text:
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
        feature_index = dict(navigation_bundle.get("feature_index") or {})
        render_features = [feature_index[feature_id] for feature_id in render_feature_ids if feature_id in feature_index]

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
                for point in _geometry_points(dict((feature.get("feature") or {}).get("geometry") or {}))
            ]
        )
        render_projection_summary = _projection_summary_for_row_addresses(ordered_render_row_addresses, row_index)
        render_projection_warnings = _dedupe_texts(
            list(render_projection_summary.get("warnings") or [])
            + [
                warning
                for feature in render_features
                for warning in list(feature.get("projection_warnings") or [])
            ]
            + list(document_summary.get("projection_warnings") or [])
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
                for profile in render_profiles
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
            attention_node_id=(mediation_state or {}).get("attention_node_id") if isinstance(mediation_state, dict) else "",
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
