from __future__ import annotations

import string
from typing import Any

_COORD_SCALE = 10_000_000.0
_DEFAULT_HOPS_RADICES = (8, 81, 100, 100, 100, 100)
_AUTH_HOPS = "hops"
_AUTH_FIXED_HEX = "fixed_hex"
_AUTH_AUTO = "auto"


def _signed_axis_value(raw: int, axis_bits: int) -> int:
    sign = 1 << (axis_bits - 1)
    if raw & sign:
        return raw - (1 << axis_bits)
    return raw


def decode_fixed_hex_coordinate(raw_value: Any) -> dict[str, Any] | None:
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
        "encoding": "legacy_fixed_hex",
        "normalized_hex": f"0x{token.upper()}",
        "axis_bits": axis_bits,
        "row": {"hex": f"0x{row_hex}", "value": row_value},
        "column": {"hex": f"0x{col_hex}", "value": col_value},
        "longitude": {"signed_value": longitude_signed, "value": longitude, "text": longitude_text},
        "latitude": {"signed_value": latitude_signed, "value": latitude, "text": latitude_text},
        "pair_text": [longitude_text, latitude_text],
    }


def _looks_like_hyphenated_hex(token: str) -> bool:
    if "-" not in token:
        return False
    parts = [part for part in token.split("-") if part]
    if not parts:
        return False
    if not all(all(ch in string.hexdigits for ch in part) for part in parts):
        return False
    compact = "".join(parts)
    return bool(compact) and (len(compact) % 2 == 0)


def _as_hops_radices(schema_payload: dict[str, Any] | None) -> tuple[int, ...]:
    if isinstance(schema_payload, dict):
        schema = schema_payload.get("schema") if isinstance(schema_payload.get("schema"), dict) else {}
        denotations = schema.get("denotations") if isinstance(schema, dict) else None
        out = [int(item) for item in list(denotations or []) if isinstance(item, int) and int(item) > 0]
        if out:
            return tuple(out)
    return _DEFAULT_HOPS_RADICES


def _decode_hops_coordinate(raw_value: Any, *, schema_payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    token = str(raw_value or "").strip()
    if not token or "-" not in token:
        return None
    parts = token.split("-")
    if any(not piece.isdigit() for piece in parts):
        return None
    segments = tuple(int(piece) for piece in parts)
    radices = _as_hops_radices(schema_payload)
    if len(segments) > len(radices):
        return None
    for idx, value in enumerate(segments):
        if value < 0 or value >= int(radices[idx]):
            return None

    lon_min, lon_max = -180.0, 180.0
    lat_min, lat_max = -90.0, 90.0
    # Two leading segments are scope/prefix; partitioning starts after those.
    partition_dims = segments[2:]
    for idx, value in enumerate(partition_dims):
        radix = max(1, int(radices[idx + 2] if (idx + 2) < len(radices) else 100))
        if idx % 2 == 0:
            span = (lon_max - lon_min) / radix
            lon_min = lon_min + (span * value)
            lon_max = lon_min + span
        else:
            span = (lat_max - lat_min) / radix
            lat_min = lat_min + (span * value)
            lat_max = lat_min + span
    longitude = (lon_min + lon_max) / 2.0
    latitude = (lat_min + lat_max) / 2.0
    return {
        "encoding": "hops_mixed_radix",
        "address": token,
        "segments": list(segments),
        "radices": list(radices[: len(segments)]),
        "longitude": {"value": longitude, "text": f"{longitude:.13f}", "range": [lon_min, lon_max]},
        "latitude": {"value": latitude, "text": f"{latitude:.13f}", "range": [lat_min, lat_max]},
        "pair_text": [f"{longitude:.13f}", f"{latitude:.13f}"],
    }


def classify_coordinate_token(raw_value: Any, *, schema_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = str(raw_value or "").strip()
    if not token:
        return {"classification": "invalid", "reason": "empty token", "token": token}
    if _looks_like_hyphenated_hex(token):
        return {
            "classification": "ambiguous",
            "reason": "token is hyphenated hex and can be interpreted multiple ways",
            "token": token,
        }
    hops = _decode_hops_coordinate(token, schema_payload=schema_payload)
    fixed_hex = decode_fixed_hex_coordinate(token)
    if hops is not None and fixed_hex is not None:
        return {
            "classification": "ambiguous",
            "reason": "token satisfies both HOPS and fixed-hex decoders",
            "token": token,
        }
    if hops is not None:
        return {"classification": "hops", "reason": "token matches HOPS schema", "token": token}
    if fixed_hex is not None:
        return {"classification": "fixed_hex", "reason": "token matches fixed-hex format", "token": token}
    return {"classification": "invalid", "reason": "token matches no coordinate scheme", "token": token}


def decode_coordinate_token(
    raw_value: Any,
    *,
    schema_payload: dict[str, Any] | None = None,
    authority: str = _AUTH_AUTO,
    allow_legacy_fixed_hex: bool = False,
) -> dict[str, Any] | None:
    token = str(raw_value or "").strip()
    mode = str(authority or _AUTH_AUTO).strip().lower()
    if mode not in {_AUTH_HOPS, _AUTH_FIXED_HEX, _AUTH_AUTO}:
        mode = _AUTH_AUTO
    classification = classify_coordinate_token(token, schema_payload=schema_payload)
    class_id = str(classification.get("classification") or "")
    if class_id == "ambiguous":
        return None
    if mode == _AUTH_HOPS:
        if class_id == "hops":
            return _decode_hops_coordinate(token, schema_payload=schema_payload)
        if class_id == "fixed_hex" and allow_legacy_fixed_hex:
            decoded = decode_fixed_hex_coordinate(token)
            if isinstance(decoded, dict):
                decoded["compatibility_fallback"] = True
            return decoded
        return None
    if mode == _AUTH_FIXED_HEX:
        if class_id != "fixed_hex":
            return None
        return decode_fixed_hex_coordinate(token)
    # AUTO mode remains explicit and never interprets ambiguous tokens.
    if class_id == "hops":
        return _decode_hops_coordinate(token, schema_payload=schema_payload)
    if class_id == "fixed_hex":
        return decode_fixed_hex_coordinate(token) if allow_legacy_fixed_hex else None
    return None


__all__ = [
    "classify_coordinate_token",
    "decode_coordinate_token",
    "decode_fixed_hex_coordinate",
]
