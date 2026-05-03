"""Document projection, coordinate decoding, and GeoJSON feature construction for CTS-GIS."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.structures.hops import (
    classify_hops_coordinate_token,
    decode_hops_coordinate_token,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import (
    DEFAULT_ATTENTION_NODE_ID as _DEFAULT_ATTENTION_NODE_ID,
    as_text as _as_text,
)
from MyCiteV2.packages.modules.cross_domain.cts_gis._utils import (
    _address_tuple,
    _as_lower,
    _first_non_empty,
    _node_depth,
    _parent_node_id,
    _profile_sort_key,
    _sorted_addresses,
)
from MyCiteV2.packages.modules.domains.datum_recognition import (
    DatumRecognitionDocument,
    DatumRecognitionRow,
)

_SEMANTIC_GUARDRAIL_ENVELOPES = {
    # Summit corpus envelope. When decoded HOPS geometry lands far outside this
    # range for this subtree, keep the decode diagnostics but mark geometry as
    # semantically implausible for fallback handling.
    "3-2-3-17-77": {
        "bounds": (-83.0, 40.0, -80.0, 42.5),
        "max_span": (2.5, 2.5),
    },
}


def _binding_family(anchor_label: object) -> str:
    label = _as_lower(anchor_label)
    if "title-babelette" in label or "title-babellette" in label:
        return "title_babelette"
    if "samras" in label and ("babelette" in label or "babellette" in label):
        return "samras_babelette"
    if "hops" in label and ("babelette" in label or "babellette" in label):
        return "hops_babelette"
    return ""


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
    geometry_type = _as_text((geometry or {}).get("type"))
    coordinates = (geometry or {}).get("coordinates")
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
        polygon = [_coerce_coordinate_pairs(ring) for ring in coordinates if isinstance(ring, list)]
        polygon = [ring for ring in polygon if ring]
        return [polygon] if polygon else []
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        out: list[list[list[list[float]]]] = []
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            normalized_polygon = [_coerce_coordinate_pairs(ring) for ring in polygon if isinstance(ring, list)]
            normalized_polygon = [ring for ring in normalized_polygon if ring]
            if normalized_polygon:
                out.append(normalized_polygon)
        return out
    return []


def _row_family(row_address: str) -> str:
    return _as_text(row_address).split("-", 1)[0]


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
    points = _coerce_coordinate_pairs(ring)
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


def _node_guardrail_envelope(node_id: object) -> dict[str, Any] | None:
    token = _as_text(node_id)
    if not token:
        return None
    for prefix, envelope in _SEMANTIC_GUARDRAIL_ENVELOPES.items():
        if token == prefix:
            return dict(envelope)
    return None


def _semantic_projection_assessment(
    *,
    row_address: str,
    node_id: str,
    points: list[list[float]],
) -> dict[str, Any]:
    envelope = _node_guardrail_envelope(node_id)
    if not envelope:
        return {"plausible": True, "reason_codes": [], "warnings": []}
    if not points:
        return {"plausible": True, "reason_codes": [], "warnings": []}

    bounds = _feature_bounds(points)
    if not bounds:
        return {"plausible": True, "reason_codes": [], "warnings": []}

    min_lon, min_lat, max_lon, max_lat = bounds
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    expected_min_lon, expected_min_lat, expected_max_lon, expected_max_lat = tuple(
        float(value) for value in list(envelope.get("bounds") or (-180.0, -90.0, 180.0, 90.0))
    )
    expected_max_lon_span, expected_max_lat_span = tuple(
        float(value) for value in list(envelope.get("max_span") or (360.0, 180.0))
    )

    reason_codes: list[str] = []
    warnings: list[str] = []
    if (
        max_lon < expected_min_lon
        or min_lon > expected_max_lon
        or max_lat < expected_min_lat
        or min_lat > expected_max_lat
    ):
        reason_codes.append("semantic_bounds_outside_expected_envelope")
        warnings.append(
            f"{row_address} geometry bounds {bounds} are outside expected envelope "
            f"[{expected_min_lon}, {expected_min_lat}, {expected_max_lon}, {expected_max_lat}] "
            f"for node {node_id}."
        )
    if lon_span > expected_max_lon_span or lat_span > expected_max_lat_span:
        reason_codes.append("semantic_span_exceeds_expected_envelope")
        warnings.append(
            f"{row_address} geometry span ({lon_span:.3f}, {lat_span:.3f}) exceeds expected "
            f"max span ({expected_max_lon_span:.3f}, {expected_max_lat_span:.3f}) for node {node_id}."
        )

    return {
        "plausible": not reason_codes,
        "reason_codes": _dedupe_texts(reason_codes),
        "warnings": _dedupe_texts(warnings),
    }


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
    primary_samras_node_id: str = "",
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
            "reason_codes": [],
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
            parity_pair = _safe_coordinate_pair(mapped_ring[binding_index])
            if parity_pair is None:
                warnings.append(
                    f"{row.datum_address} parity authority carried non-numeric coordinates at index {binding_index}."
                )
            else:
                decoded = _decoded_coordinate_payload(
                    token,
                    longitude=parity_pair[0],
                    latitude=parity_pair[1],
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
    semantic_assessment = _semantic_projection_assessment(
        row_address=row.datum_address,
        node_id=primary_samras_node_id,
        points=[list(entry["coordinates"]) for entry in out],
    )
    semantic_reason_codes = list(semantic_assessment.get("reason_codes") or [])
    warnings.extend(list(semantic_assessment.get("warnings") or []))
    return {
        "entries": out,
        "reference_binding_count": reference_binding_count,
        "decoded_coordinate_count": decoded_coordinate_count,
        "failed_token_count": failed_token_count,
        "projection_source": "hops" if decoded_coordinate_count else "none",
        "reason_codes": semantic_reason_codes,
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
    projection_reason_codes: list[str] | None = None,
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
        "projection_reason_codes": list(projection_reason_codes or []),
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
                "projection_reason_codes": list(projection_reason_codes or []),
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
    projection_reason_codes: list[str] | None = None,
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
        "projection_reason_codes": list(projection_reason_codes or []),
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
        "projection_reason_codes": list(projection_reason_codes or []),
        "projection_warnings": list(projection_warnings or []),
        "feature": {
            "type": "Feature",
            "id": feature_id,
            "geometry": geometry,
            "properties": feature_properties,
        },
    }


def _row_projection(
    document: DatumRecognitionDocument,
    row: DatumRecognitionRow,
    *,
    overlay_mode: str,
    row_address_set: set[str],
    coordinate_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overlays = [_binding_overlay(binding, overlay_mode=overlay_mode) for binding in row.reference_bindings]
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
    coordinate_projection = _coordinate_projection(
        row,
        coordinate_authority=coordinate_authority,
        primary_samras_node_id=primary_samras_node_id,
    )
    coordinates = list(coordinate_projection.get("entries") or [])
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
        projection_reason_codes=list(coordinate_projection.get("reason_codes") or []),
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
        "coordinate_reason_codes": list(coordinate_projection.get("reason_codes") or []),
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
    reason_codes: list[str] = []
    for row_address in row_addresses:
        row = row_index.get(row_address)
        if row is None or _row_family(row_address) != "4":
            continue
        reference_binding_count += int(row.get("reference_binding_count") or 0)
        decoded_coordinate_count += int(row.get("decoded_coordinate_count") or 0)
        failed_token_count += int(row.get("failed_token_count") or 0)
        warnings.extend(list(row.get("coordinate_warnings") or []))
        reason_codes.extend(list(row.get("coordinate_reason_codes") or []))
    return {
        "reference_binding_count": reference_binding_count,
        "decoded_coordinate_count": decoded_coordinate_count,
        "failed_token_count": failed_token_count,
        "reason_codes": _dedupe_texts(reason_codes),
        "warnings": _dedupe_texts(warnings),
    }


def _reference_geojson_profile_features(
    document: DatumRecognitionDocument,
    *,
    owner_row: dict[str, Any],
    decode_summary: dict[str, Any] | None = None,
    projection_reason_codes: list[str] | None = None,
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
            projection_reason_codes=list(projection_reason_codes or []),
            projection_warnings=warnings,
        )
        if feature is not None:
            out.append(feature)
    return out


def _prefer_reference_geojson_projection(
    document: DatumRecognitionDocument,
    *,
    owner_row: dict[str, Any],
    coordinate_authority: dict[str, Any] | None,
    projection_summary: dict[str, Any] | None,
) -> bool:
    metadata = dict(document.document_metadata or {})
    payload = metadata.get("reference_geojson")
    expected_node_id = _as_text(metadata.get("reference_geojson_node_id"))
    owner_node_id = _as_text(owner_row.get("samras_node_id"))
    if not isinstance(payload, dict):
        return False
    if expected_node_id and expected_node_id != owner_node_id:
        return False
    reference_binding_count = int((projection_summary or {}).get("reference_binding_count") or 0)
    decoded_coordinate_count = int((projection_summary or {}).get("decoded_coordinate_count") or 0)
    failed_token_count = int((projection_summary or {}).get("failed_token_count") or 0)
    if reference_binding_count <= 0:
        return False
    if decoded_coordinate_count <= 0:
        return True
    # HOPS remains authoritative when decode succeeds. Warnings alone do not switch authority.
    return failed_token_count >= reference_binding_count and reference_binding_count > 0


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
        projection_reason_codes = list(projection_summary.get("reason_codes") or [])
        projection_warnings = list(projection_summary.get("warnings") or [])
        profile_features: list[dict[str, Any]] = []
        decode_summary = {
            "reference_binding_count": int(projection_summary.get("reference_binding_count") or 0),
            "decoded_coordinate_count": int(projection_summary.get("decoded_coordinate_count") or 0),
            "failed_token_count": int(projection_summary.get("failed_token_count") or 0),
        }
        semantic_reason_codes = [code for code in projection_reason_codes if _as_text(code).startswith("semantic_")]
        semantic_implausible = bool(semantic_reason_codes)
        prefer_reference_geojson = _prefer_reference_geojson_projection(
            document,
            owner_row=row,
            coordinate_authority=coordinate_authority,
            projection_summary=projection_summary,
        )
        if not prefer_reference_geojson:
            geometry = _geometry_from_row_address(row["datum_address"], row_index)
            if geometry is not None:
                geometry_semantic_assessment = _semantic_projection_assessment(
                    row_address=_as_text(row.get("datum_address")),
                    node_id=node_id,
                    points=_geometry_points(geometry),
                )
                projection_reason_codes = _dedupe_texts(
                    projection_reason_codes + list(geometry_semantic_assessment.get("reason_codes") or [])
                )
                projection_warnings = _dedupe_texts(
                    projection_warnings + list(geometry_semantic_assessment.get("warnings") or [])
                )
                semantic_reason_codes = [
                    code for code in projection_reason_codes if _as_text(code).startswith("semantic_")
                ]
                semantic_implausible = bool(semantic_reason_codes)
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
                    decode_summary=decode_summary,
                    projection_reason_codes=projection_reason_codes,
                    projection_warnings=projection_warnings,
                )
                if feature is not None:
                    profile_features = [feature]
        if semantic_implausible:
            fallback_warnings = _dedupe_texts(
                projection_warnings
                + [
                    f"{_as_text(row.get('datum_address'))} failed semantic guardrails and requested authority fallback."
                ]
                + list(coordinate_authority.get("warnings") or [])
            )
            semantic_fallback_features = _reference_geojson_profile_features(
                document,
                owner_row=row,
                decode_summary=decode_summary,
                projection_reason_codes=projection_reason_codes,
                projection_warnings=fallback_warnings,
            )
            if semantic_fallback_features:
                profile_features = semantic_fallback_features
        if not profile_features:
            profile_features = _reference_geojson_profile_features(
                document,
                owner_row=row,
                decode_summary=decode_summary,
                projection_reason_codes=projection_reason_codes,
                projection_warnings=projection_warnings
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
        feature_ids = []
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
