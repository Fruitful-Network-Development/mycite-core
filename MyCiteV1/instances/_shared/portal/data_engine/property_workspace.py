from __future__ import annotations

from typing import Any

from ..mediation.registry import decode_value as mediate_decode


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        try:
            return float(token)
        except Exception:
            return None
    if isinstance(value, dict):
        for key in ("value", "lat", "lon", "latitude", "longitude", "signed_value"):
            nested = _safe_float(value.get(key))
            if nested is not None:
                return nested
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            nested = _safe_float(item)
            if nested is not None:
                return nested
    return None


def _first_pair(row: dict[str, Any]) -> tuple[str, str]:
    pairs = row.get("pairs")
    if isinstance(pairs, list):
        for item in pairs:
            if not isinstance(item, dict):
                continue
            reference = _as_text(item.get("reference"))
            magnitude = _as_text(item.get("magnitude"))
            if reference or magnitude:
                return reference, magnitude
    return _as_text(row.get("reference")), _as_text(row.get("magnitude"))


def _as_token_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_as_text(item) for item in value if _as_text(item)]
    token = _as_text(value)
    return [token] if token else []


def _as_property_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    # Shared runtime logic treats property as a list-backed collection internally.
    # Dict-backed payloads remain accepted here as a boundary adapter for older configs.
    raw = (config or {}).get("property")
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [dict(raw)]
    return []


def property_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    return _as_property_entries(config)


def primary_property_entry(config: dict[str, Any]) -> dict[str, Any]:
    entries = _as_property_entries(config)
    return dict(entries[0]) if entries else {}


def _resolve_coordinate(
    token: str,
    *,
    rows_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    cleaned = _as_text(token)
    if not cleaned:
        return {}, "empty coordinate token"
    row = rows_by_id.get(cleaned) if isinstance(rows_by_id, dict) else None
    source = "anthology_datum" if isinstance(row, dict) else "raw_token"
    reference = ""
    magnitude = cleaned
    label = ""
    if isinstance(row, dict):
        reference, magnitude = _first_pair(row)
        magnitude = magnitude or cleaned
        label = _as_text(row.get("label"))
    decoded = mediate_decode(
        standard_id="coordinate_fixed_hex",
        reference=reference,
        magnitude=magnitude,
        context={"allow_trailing_null": True},
    )
    value = decoded.get("value") if isinstance(decoded, dict) else {}
    lon = _safe_float((value or {}).get("lon"))
    lat = _safe_float((value or {}).get("lat"))
    if lon is None:
        lon = _safe_float((value or {}).get("longitude"))
    if lat is None:
        lat = _safe_float((value or {}).get("latitude"))
    if lon is None or lat is None:
        return {}, f"invalid coordinate token: {cleaned}"
    return (
        {
            "token": cleaned,
            "source": source,
            "datum_label": label,
            "resolved_reference": reference,
            "resolved_magnitude": magnitude,
            "longitude": lon,
            "latitude": lat,
            "decoded": (value or {}).get("decoded") if isinstance(value, dict) else {},
        },
        "",
    )


def _bbox_summary_from_points(points: list[dict[str, Any]]) -> dict[str, float]:
    if not points:
        return {}
    lons = [float(item["longitude"]) for item in points]
    lats = [float(item["latitude"]) for item in points]
    return {
        "longitude_min": min(lons),
        "longitude_max": max(lons),
        "latitude_min": min(lats),
        "latitude_max": max(lats),
    }


def _centroid(points: list[dict[str, Any]]) -> dict[str, float]:
    if not points:
        return {}
    lon = sum(float(item["longitude"]) for item in points) / len(points)
    lat = sum(float(item["latitude"]) for item in points) / len(points)
    return {"longitude": lon, "latitude": lat}


def resolve_property_workspace(
    *,
    config: dict[str, Any],
    rows_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    parcels: list[dict[str, Any]] = []
    warnings: list[str] = []
    entries = _as_property_entries(config)
    for index, entry in enumerate(entries, start=1):
        title = _as_text(entry.get("title")) or f"parcel-{index}"
        parcel_id = _as_text(entry.get("parcel_id") or entry.get("id")) or f"parcel-{index}"
        bbox_refs = _as_token_list(entry.get("bbox"))
        geometry = entry.get("geometry") if isinstance(entry.get("geometry"), dict) else {}
        geometry_refs = _as_token_list((geometry or {}).get("coordinates"))
        geometry_type = _as_text((geometry or {}).get("type")) or "Polygon"

        polygon_points: list[dict[str, Any]] = []
        parcel_warnings: list[str] = []
        for token in geometry_refs:
            point, warn = _resolve_coordinate(token, rows_by_id=rows_by_id)
            if warn:
                parcel_warnings.append(warn)
                continue
            polygon_points.append(point)

        bbox_points: list[dict[str, Any]] = []
        for token in bbox_refs:
            point, warn = _resolve_coordinate(token, rows_by_id=rows_by_id)
            if warn:
                parcel_warnings.append(f"bbox {warn}")
                continue
            bbox_points.append(point)

        polygon = [{"longitude": p["longitude"], "latitude": p["latitude"]} for p in polygon_points]
        bbox_summary = _bbox_summary_from_points(bbox_points) or _bbox_summary_from_points(polygon_points)
        centroid = _centroid(polygon_points)
        valid_geometry = len(polygon_points) >= 3
        if not valid_geometry:
            parcel_warnings.append("parcel polygon has fewer than 3 valid points")

        parcels.append(
            {
                "parcel_id": parcel_id,
                "title": title,
                "geometry_type": geometry_type,
                "bbox_refs": bbox_refs,
                "geometry_refs": geometry_refs,
                "polygon": polygon,
                "resolved_points": polygon_points,
                "bbox_summary": bbox_summary,
                "focus_hint": centroid,
                "valid": valid_geometry,
                "warnings": parcel_warnings,
                "source": {
                    "config_path": f"property[{index - 1}]",
                    "anthology_resolution": "rows_by_id",
                },
            }
        )
        warnings.extend([f"{parcel_id}: {item}" for item in parcel_warnings])

    return {
        "ok": True,
        "parcel_count": len(parcels),
        "parcels": parcels,
        "warnings": warnings,
    }
