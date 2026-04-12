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


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_lower(value: object) -> str:
    return _as_text(value).lower()


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
        raise ValueError("maps.overlay_mode must be auto or raw_only")
    return mode


def _normalize_raw_underlay_visible(value: object) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError("maps.raw_underlay_visible must be a bool when provided")
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

    title_overlay = next((item for item in overlays if item["overlay_family"] == "title_babelette"), None)
    samras_overlay = next((item for item in overlays if item["overlay_family"] == "samras_babelette"), None)
    return {
        "feature_id": feature_id,
        "row_address": row.datum_address,
        "label_text": label_text,
        "labels": label_tokens,
        "geometry_type": geometry_type,
        "bounds": _feature_bounds(points),
        "title_display": _as_text((title_overlay or {}).get("display_value")),
        "samras_display": _as_text((samras_overlay or {}).get("display_value")),
        "diagnostic_states": list(row.diagnostic_states),
        "feature": {
            "type": "Feature",
            "id": feature_id,
            "geometry": geometry,
            "properties": {
                "row_address": row.datum_address,
                "label_text": label_text,
                "labels": label_tokens,
                "title_display": _as_text((title_overlay or {}).get("display_value")),
                "samras_display": _as_text((samras_overlay or {}).get("display_value")),
                "diagnostic_states": list(row.diagnostic_states),
            },
        },
    }


def _project_document(
    document: DatumRecognitionDocument,
    *,
    overlay_mode: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    feature_collection_features: list[dict[str, Any]] = []
    for row in document.rows:
        overlays = [_binding_overlay(binding, overlay_mode=overlay_mode) for binding in row.reference_bindings]
        coordinates = _coordinate_entries(row)
        feature = _feature_from_row(document=document, row=row, overlays=overlays, coordinates=coordinates)
        if feature is not None:
            features.append(feature)
            feature_collection_features.append(dict(feature["feature"]))
        rows.append(
            {
                "datum_address": row.datum_address,
                "labels": list(row.labels),
                "label_text": _row_label_text(row),
                "recognized_family": row.recognized_family,
                "recognized_anchor": row.recognized_anchor,
                "primary_value_token": row.primary_value_token,
                "diagnostic_states": list(row.diagnostic_states),
                "raw": row.raw,
                "reference_bindings": [binding.to_dict() for binding in row.reference_bindings],
                "overlay_values": overlays,
                "projectable_coordinates": coordinates,
                "feature_ids": [] if feature is None else [feature["feature_id"]],
            }
        )

    bounds = _feature_bounds(
        [
            point
            for feature in features
            for point in (
                [feature["feature"]["geometry"]["coordinates"]]
                if feature["geometry_type"] == "Point"
                else feature["feature"]["geometry"]["coordinates"][0]
            )
        ]
    )
    projection_state = "projectable" if features else "inspect_only"
    summary = document.to_summary_dict()
    summary["projectable_feature_count"] = len(features)
    summary["projection_state"] = projection_state
    return {
        "document_summary": summary,
        "rows": rows,
        "features": features,
        "map_projection": {
            "projection_state": projection_state,
            "feature_count": len(features),
            "selected_feature": None,
            "feature_collection": {
                "type": "FeatureCollection",
                "features": feature_collection_features,
                "bounds": bounds,
            },
        },
    }


def _select_feature(features: list[dict[str, Any]], *, selected_feature_id: str) -> dict[str, Any] | None:
    if selected_feature_id:
        for feature in features:
            if feature["feature_id"] == selected_feature_id:
                return feature
    return features[0] if features else None


def _select_row(
    rows: list[dict[str, Any]],
    *,
    selected_row_address: str,
    selected_feature: dict[str, Any] | None,
) -> dict[str, Any] | None:
    target_row_address = selected_row_address or _as_text((selected_feature or {}).get("row_address"))
    if target_row_address:
        for row in rows:
            if row["datum_address"] == target_row_address:
                return row
    return rows[0] if rows else None


class MapsReadOnlyService:
    def __init__(self, datum_store: AuthoritativeDatumDocumentPort | None) -> None:
        self._datum_store = datum_store

    def read_surface(
        self,
        tenant_id: str,
        *,
        selected_document_id: object = "",
        selected_row_address: object = "",
        selected_feature_id: object = "",
        overlay_mode: object = "auto",
        raw_underlay_visible: object = False,
    ) -> dict[str, Any]:
        if self._datum_store is None:
            raise ValueError("maps.datum_store is not configured")

        normalized_overlay_mode = _normalize_overlay_mode(overlay_mode)
        normalized_raw_underlay = _normalize_raw_underlay_visible(raw_underlay_visible)
        workbench = DatumWorkbenchService(self._datum_store).read_workbench(_as_text(tenant_id) or "fnd")

        maps_documents = [
            document
            for document in workbench.documents
            if document.source_kind == "sandbox_source" and document.tool_id == "maps"
        ]
        projection_cache: dict[str, dict[str, Any]] = {}

        def project(document: DatumRecognitionDocument) -> dict[str, Any]:
            cached = projection_cache.get(document.document_id)
            if cached is not None:
                return cached
            projected = _project_document(document, overlay_mode=normalized_overlay_mode)
            projection_cache[document.document_id] = projected
            return projected

        selected_document: DatumRecognitionDocument | None = None
        requested_document_id = _as_text(selected_document_id)
        if requested_document_id:
            for document in (*maps_documents, *workbench.documents):
                if document.document_id == requested_document_id:
                    selected_document = document
                    break
        if selected_document is None:
            feature_ready = [
                document for document in maps_documents if project(document)["map_projection"]["feature_count"] > 0
            ]
            if feature_ready:
                selected_document = feature_ready[0]
            else:
                diagnostic_ready = [document for document in maps_documents if document.diagnostic_row_count > 0]
                if diagnostic_ready:
                    selected_document = diagnostic_ready[0]
                elif maps_documents:
                    selected_document = maps_documents[0]
                else:
                    selected_document = workbench.selected_document

        selected_projection = project(selected_document) if selected_document is not None else None
        selected_rows = [] if selected_projection is None else list(selected_projection["rows"])
        selected_features = [] if selected_projection is None else list(selected_projection["features"])
        selected_feature = _select_feature(
            selected_features,
            selected_feature_id=_as_text(selected_feature_id),
        )
        selected_row = _select_row(
            selected_rows,
            selected_row_address=_as_text(selected_row_address),
            selected_feature=selected_feature,
        )
        selected_row_address_text = _as_text((selected_row or {}).get("datum_address"))
        selected_feature_id_text = _as_text((selected_feature or {}).get("feature_id"))
        for row in selected_rows:
            row["selected"] = row["datum_address"] == selected_row_address_text
            row["selected_feature"] = selected_feature_id_text in (row.get("feature_ids") or [])
        feature_collection = (
            {"type": "FeatureCollection", "features": [], "bounds": None}
            if selected_projection is None
            else dict(selected_projection["map_projection"]["feature_collection"])
        )
        feature_collection["features"] = [
            {
                **feature,
                "selected": _as_text(feature.get("id")) == selected_feature_id_text,
            }
            for feature in feature_collection.get("features") or []
        ]

        projection_state = "no_authoritative_maps_documents"
        feature_count = 0
        if maps_documents:
            projection_state = (
                _as_text((selected_projection or {}).get("map_projection", {}).get("projection_state"))
                or "inspect_only"
            )
            feature_count = len(selected_features)

        document_catalog = []
        for document in maps_documents:
            summary = dict(project(document)["document_summary"])
            summary["selected"] = bool(selected_document and selected_document.document_id == document.document_id)
            document_catalog.append(summary)

        warnings = list(workbench.warnings)
        if selected_document is not None:
            warnings.extend(selected_document.warnings)
        if not maps_documents:
            warnings.append("No authoritative sandbox maps documents were available for the current tenant.")
        warnings = list(dict.fromkeys(_as_text(item) for item in warnings if _as_text(item)))

        selected_document_summary = None
        if selected_document is not None:
            if selected_projection is not None:
                selected_document_summary = dict(selected_projection["document_summary"])
            else:
                selected_document_summary = selected_document.to_summary_dict()
            selected_document_summary["selected"] = True

        return {
            "document_catalog": document_catalog,
            "selected_document": selected_document_summary,
            "selected_row": selected_row,
            "map_projection": {
                "projection_state": projection_state,
                "feature_count": feature_count,
                "selected_feature": selected_feature,
                "feature_collection": feature_collection,
            },
            "rows": selected_rows,
            "diagnostic_summary": {
                "document_count": len(maps_documents),
                "selected_document_id": _as_text((selected_document_summary or {}).get("document_id")),
                "selected_row_address": selected_row_address_text,
                "selected_feature_id": selected_feature_id_text,
                "diagnostic_totals": dict((selected_document_summary or {}).get("diagnostic_totals") or {}),
                "diagnostic_row_count": (selected_document_summary or {}).get("diagnostic_row_count", 0),
                "row_count": (selected_document_summary or {}).get("row_count", 0),
                "feature_count": feature_count,
                "projection_state": projection_state,
            },
            "lens_state": {
                "overlay_mode": normalized_overlay_mode,
                "raw_underlay_visible": normalized_raw_underlay,
                "lens_presentation_only": True,
            },
            "warnings": warnings,
        }
