from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .types import MediationResult, result


def _to_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value or "0").strip())


def _duration_display(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m {sec}s"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h {minutes}m {sec}s"


def decode_timestamp(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    warnings: list[str] = []
    errors: list[str] = []
    try:
        unix_s = _to_int(magnitude)
        if unix_s < 0:
            errors.append("timestamp must be >= 0")
            unix_s = 0
    except Exception:
        errors.append("invalid unix timestamp")
        unix_s = 0

    iso_value = datetime.fromtimestamp(unix_s, tz=UTC).isoformat().replace("+00:00", "Z")
    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=str(unix_s),
        value=unix_s,
        display=iso_value,
        warnings=warnings,
        errors=errors,
    )


def encode_timestamp(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    warnings: list[str] = []
    errors: list[str] = []

    unix_s = 0
    if isinstance(value, (int, float)):
        unix_s = int(value)
    else:
        token = str(value or "").strip()
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        try:
            unix_s = int(datetime.fromisoformat(token).timestamp())
        except Exception:
            try:
                unix_s = int(token)
            except Exception:
                errors.append("invalid timestamp value")
                unix_s = 0

    return result(
        standard_id=standard_id,
        reference="",
        magnitude=str(unix_s),
        value=unix_s,
        display=datetime.fromtimestamp(unix_s, tz=UTC).isoformat().replace("+00:00", "Z"),
        warnings=warnings,
        errors=errors,
    )


def decode_duration(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    warnings: list[str] = []
    errors: list[str] = []
    try:
        seconds = _to_int(magnitude)
    except Exception:
        errors.append("invalid duration")
        seconds = 0
    if seconds < 0:
        errors.append("duration must be >= 0")
        seconds = 0
    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=str(seconds),
        value=seconds,
        display=_duration_display(seconds),
        warnings=warnings,
        errors=errors,
    )


def encode_duration(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    warnings: list[str] = []
    errors: list[str] = []
    try:
        seconds = _to_int(value)
    except Exception:
        errors.append("invalid duration value")
        seconds = 0
    if seconds < 0:
        errors.append("duration must be >= 0")
        seconds = 0
    return result(
        standard_id=standard_id,
        reference="",
        magnitude=str(seconds),
        value=seconds,
        display=_duration_display(seconds),
        warnings=warnings,
        errors=errors,
    )
