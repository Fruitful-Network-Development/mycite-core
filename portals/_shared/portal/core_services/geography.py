from __future__ import annotations

import json
import string
from pathlib import Path
from typing import Any

_COORD_SCALE = 10_000_000.0


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _signed_axis_value(raw: int, axis_bits: int) -> int:
    sign = 1 << (axis_bits - 1)
    if raw & sign:
        return raw - (1 << axis_bits)
    return raw


def _decode_fixed_hex_coordinate(raw_value: Any) -> dict[str, Any] | None:
    token = str(raw_value or "").strip()
    if token.lower().startswith("0x"):
        token = token[2:]
    token = token.replace("_", "").strip()
    if not token or (len(token) % 2) != 0:
        return None
    if any(ch not in string.hexdigits for ch in token):
        return None

    half = len(token) // 2
    row_hex = token[:half].upper()
    col_hex = token[half:].upper()
    axis_bits = half * 4
    row_value = int(row_hex, 16)
    col_value = int(col_hex, 16)
    longitude_signed = _signed_axis_value(row_value, axis_bits)
    latitude_signed = _signed_axis_value(col_value, axis_bits)
    longitude = longitude_signed / _COORD_SCALE
    latitude = latitude_signed / _COORD_SCALE
    longitude_text = f"{longitude:.13f}"
    latitude_text = f"{latitude:.13f}"
    return {
        "normalized_hex": f"0x{token.upper()}",
        "axis_bits": axis_bits,
        "row": {"hex": f"0x{row_hex}", "value": row_value},
        "column": {"hex": f"0x{col_hex}", "value": col_value},
        "longitude": {"signed_value": longitude_signed, "value": longitude, "text": longitude_text},
        "latitude": {"signed_value": latitude_signed, "value": latitude, "text": latitude_text},
        "pair_text": [longitude_text, latitude_text],
    }


def _resolve_datum(payload: dict[str, Any], datum_id: str) -> dict[str, Any]:
    token = str(datum_id or "").strip()
    out: dict[str, Any] = {
        "datum_id": token,
        "exists": False,
        "label": "",
        "reference": "",
        "magnitude": "",
        "decoded_coordinate": None,
    }
    if not token:
        return out

    datum = payload.get(token)
    if datum is None:
        direct_decode = _decode_fixed_hex_coordinate(token)
        if direct_decode is not None:
            out["magnitude"] = token
            out["decoded_coordinate"] = direct_decode
        return out
    out["exists"] = True

    if isinstance(datum, list):
        header = datum[0] if datum and isinstance(datum[0], list) else []
        if isinstance(header, list):
            if len(header) > 1:
                out["reference"] = str(header[1] or "").strip()
            if len(header) > 2:
                out["magnitude"] = str(header[2] or "").strip()
        label_block = datum[1] if len(datum) > 1 and isinstance(datum[1], list) else []
        if isinstance(label_block, list) and label_block:
            out["label"] = str(label_block[0] or "").strip()
    elif isinstance(datum, dict):
        out["reference"] = str(datum.get("reference") or datum.get("value_type") or "").strip()
        out["magnitude"] = str(datum.get("magnitude") or datum.get("value") or "").strip()
        out["label"] = str(datum.get("label") or "").strip()
    else:
        out["magnitude"] = str(datum).strip()

    out["decoded_coordinate"] = _decode_fixed_hex_coordinate(out.get("magnitude"))
    return out


def _svg_polygon(entries: list[dict[str, Any]]) -> dict[str, Any]:
    width = 420.0
    height = 240.0
    pad = 16.0
    if not entries:
        return {"available": False, "viewbox": "0 0 420 240", "points": ""}

    use_geo_axes = all(
        isinstance(entry.get("decoded_coordinate", {}).get("longitude"), dict)
        and isinstance(entry.get("decoded_coordinate", {}).get("latitude"), dict)
        for entry in entries
    )

    if use_geo_axes:
        xs = [float(entry["decoded_coordinate"]["longitude"]["value"]) for entry in entries]
        ys = [float(entry["decoded_coordinate"]["latitude"]["value"]) for entry in entries]
        x_span_floor = 0.0000001
        y_span_floor = 0.0000001
    else:
        xs = [float(entry["decoded_coordinate"]["column"]["value"]) for entry in entries]
        ys = [float(entry["decoded_coordinate"]["row"]["value"]) for entry in entries]
        x_span_floor = 1.0
        y_span_floor = 1.0

    x_min = min(xs)
    x_max = max(xs)
    y_min = min(ys)
    y_max = max(ys)
    x_span = float(max(x_span_floor, x_max - x_min))
    y_span = float(max(y_span_floor, y_max - y_min))
    scale = min((width - (2 * pad)) / x_span, (height - (2 * pad)) / y_span)

    points: list[str] = []
    for x_raw, y_raw in zip(xs, ys):
        x = pad + ((x_raw - x_min) * scale)
        y = height - pad - ((y_raw - y_min) * scale)
        points.append(f"{x:.2f},{y:.2f}")

    bounds: dict[str, Any]
    if use_geo_axes:
        bounds = {
            "longitude_min": x_min,
            "longitude_max": x_max,
            "latitude_min": y_min,
            "latitude_max": y_max,
        }
    else:
        bounds = {
            "row_min": y_min,
            "row_max": y_max,
            "column_min": x_min,
            "column_max": x_max,
        }

    return {
        "available": len(points) >= 3,
        "viewbox": "0 0 420 240",
        "points": " ".join(points),
        "bounds": bounds,
    }


def _geojson_polygon(entries: list[dict[str, Any]], geometry_type: str) -> dict[str, Any] | None:
    pairs: list[list[float]] = []
    for entry in entries:
        decoded = entry.get("decoded_coordinate") if isinstance(entry, dict) else None
        longitude = (
            decoded.get("longitude", {}).get("value")
            if isinstance(decoded, dict)
            else None
        )
        latitude = (
            decoded.get("latitude", {}).get("value")
            if isinstance(decoded, dict)
            else None
        )
        if isinstance(longitude, (int, float)) and isinstance(latitude, (int, float)):
            pairs.append([float(longitude), float(latitude)])

    if len(pairs) < 3:
        return None

    geom = str(geometry_type or "Polygon").strip() or "Polygon"
    geom_l = geom.lower()
    if geom_l == "linestring":
        return {"type": "LineString", "coordinates": pairs}

    if pairs[0] != pairs[-1]:
        pairs.append(list(pairs[0]))
    return {"type": "Polygon", "coordinates": [pairs]}


def build_property_geography_model(config: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    property_cfg = config.get("property") if isinstance(config.get("property"), dict) else {}
    geometry_cfg = property_cfg.get("geometry") if isinstance(property_cfg.get("geometry"), dict) else {}
    bbox_refs = [str(item).strip() for item in (property_cfg.get("bbox") or []) if str(item or "").strip()]
    coordinate_refs = [str(item).strip() for item in (geometry_cfg.get("coordinates") or []) if str(item or "").strip()]

    anthology_path = data_dir / "anthology.json"
    anthology_payload = _read_json(anthology_path) if anthology_path.exists() else {}
    anthology_payload = anthology_payload if isinstance(anthology_payload, dict) else {}

    bbox_rows = [_resolve_datum(anthology_payload, ref) for ref in bbox_refs]
    coordinate_rows = [_resolve_datum(anthology_payload, ref) for ref in coordinate_refs]
    decoded_polygon_points = [row for row in coordinate_rows if isinstance(row.get("decoded_coordinate"), dict)]
    geojson_polygon = _geojson_polygon(decoded_polygon_points, str(geometry_cfg.get("type") or "Polygon"))

    return {
        "property_title": str(property_cfg.get("title") or "property").strip(),
        "geometry_type": str(geometry_cfg.get("type") or "Polygon").strip() or "Polygon",
        "bbox_refs": bbox_refs,
        "coordinate_refs": coordinate_refs,
        "bbox_rows": bbox_rows,
        "coordinate_rows": coordinate_rows,
        "anthology_path": str(anthology_path),
        "polygon_svg": _svg_polygon(decoded_polygon_points),
        "geojson_polygon": geojson_polygon,
        "geojson_text": json.dumps(geojson_polygon, indent=2) if geojson_polygon is not None else "",
        "notation": {
            "split_mode": "fixed-width",
            "description": (
                "Coordinates are stored as one hex scalar split into equal row/column halves. "
                "Daemon mediation resolves config tokens through anthology, then decodes by positional split."
            ),
        },
        "mediation": {
            "mode": "daemon-like_config_resolution",
            "path": "property -> anthology -> fixed_hex -> [longitude, latitude]",
        },
    }
