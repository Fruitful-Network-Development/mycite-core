from __future__ import annotations

from typing import Any

from .types import MediationResult, result


def decode_length(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    errors: list[str] = []
    warnings: list[str] = []
    token = str(magnitude or "").strip()
    try:
        value = float(token)
    except Exception:
        errors.append("invalid length value")
        value = 0.0
    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=str(value),
        value=value,
        display=f"{value:g} m",
        warnings=warnings,
        errors=errors,
    )


def encode_length(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    return decode_length(standard_id=standard_id, reference="", magnitude=str(value or "0"))


def decode_coordinate(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    errors: list[str] = []
    warnings: list[str] = []
    token = str(magnitude or "").strip()
    lat = 0.0
    lon = 0.0
    if token:
        parts = [part.strip() for part in token.split(",")]
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
            except Exception:
                errors.append("invalid coordinate tuple")
        else:
            errors.append("coordinate must be 'lat,lon'")
    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=f"{lat:g},{lon:g}",
        value={"lat": lat, "lon": lon},
        display=f"({lat:g}, {lon:g})",
        warnings=warnings,
        errors=errors,
    )


def encode_coordinate(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    if isinstance(value, dict):
        lat = value.get("lat")
        lon = value.get("lon")
        return decode_coordinate(standard_id=standard_id, reference="", magnitude=f"{lat},{lon}")
    return decode_coordinate(standard_id=standard_id, reference="", magnitude=str(value or ""))
