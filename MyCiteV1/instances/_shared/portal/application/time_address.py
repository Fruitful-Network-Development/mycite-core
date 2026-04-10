from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .time_address_schema import validate_address_with_schema

_MAX_TEMPORAL_DEPTH = 5  # year, month, day, hour, minute


@dataclass(frozen=True)
class ParsedTimeAddress:
    segments: tuple[int, ...]
    prefix: tuple[int, int]
    temporal: tuple[int, ...]

    @property
    def depth(self) -> int:
        return len(self.temporal)


def _as_int_segments(address: str) -> tuple[int, ...]:
    token = str(address or "").strip()
    if not token:
        raise ValueError("time address is required")
    parts = token.split("-")
    if len(parts) < 3:
        raise ValueError("time address must include prefix and at least year segment")
    values: list[int] = []
    for part in parts:
        piece = str(part).strip()
        if not piece.isdigit():
            raise ValueError(f"time address segment must be non-negative integer: {part!r}")
        values.append(int(piece))
    return tuple(values)


def parse_time_address(address: str) -> ParsedTimeAddress:
    segments = _as_int_segments(address)
    prefix = (segments[0], segments[1])
    temporal = segments[2:]
    return ParsedTimeAddress(segments=segments, prefix=prefix, temporal=temporal)


def normalize_time_address(address: str) -> str:
    parsed = parse_time_address(address)
    return "-".join(str(item) for item in parsed.segments)


def normalize_time_address_for_schema(address: str, schema_payload: dict[str, Any]) -> str:
    validation = validate_address_with_schema(address, schema_payload)
    if not bool(validation.get("ok")):
        raise ValueError(str(validation.get("error") or "time address does not satisfy schema authority"))
    return normalize_time_address(address)


def _schema_denotations(schema_payload: dict[str, Any]) -> tuple[int, ...]:
    schema = schema_payload.get("schema") if isinstance(schema_payload.get("schema"), dict) else {}
    out: list[int] = []
    for item in list(schema.get("denotations") or []):
        if isinstance(item, int) and item > 0:
            out.append(item)
    return tuple(out)


def _fallback_radix(idx: int) -> int:
    if idx == 0:
        return 14
    if idx == 1:
        return 1000
    return 1000


def _schema_is_authoritative(schema_payload: dict[str, Any] | None) -> bool:
    payload = schema_payload if isinstance(schema_payload, dict) else {}
    schema = payload.get("schema") if isinstance(payload.get("schema"), dict) else {}
    denotations = _schema_denotations(payload)
    mode = str(schema.get("validation_mode") or "").strip().lower()
    return bool(payload.get("ok")) and bool(denotations) and mode == "full"


def _effective_radices(schema_payload: dict[str, Any] | None, required_len: int) -> tuple[int, ...]:
    denotations = _schema_denotations(schema_payload or {})
    out = list(denotations[:required_len])
    while len(out) < required_len:
        out.append(_fallback_radix(len(out)))
    return tuple(max(1, int(item)) for item in out)


def _clamp_to_radices(segments: tuple[int, ...], radices: tuple[int, ...]) -> tuple[int, ...]:
    out: list[int] = []
    for idx, value in enumerate(segments):
        radix = radices[idx] if idx < len(radices) else _fallback_radix(idx)
        if radix <= 0:
            out.append(0)
            continue
        out.append(max(0, min(int(value), int(radix) - 1)))
    return tuple(out)


def _compose_scope(prefix: tuple[int, int], temporal: tuple[int, ...]) -> str:
    return "-".join(str(item) for item in (*prefix, *temporal))


def default_time_scope_for_schema(schema_payload: dict[str, Any], *, specificity: str = "year") -> str:
    if not _schema_is_authoritative(schema_payload):
        raise ValueError("time schema authority is unavailable or invalid")
    radices = _effective_radices(schema_payload, _MAX_TEMPORAL_DEPTH + 2)
    prefix = (0, 0)
    temporal_radices = tuple(radices[2:])
    depth_by_specificity = {"year": 1, "month": 2, "day": 3, "hour": 4, "minute": 5}
    depth = depth_by_specificity.get(str(specificity or "").strip().lower(), 1)
    temporal = tuple([0] * max(1, depth))
    temporal = _clamp_to_radices(temporal[:depth], temporal_radices[:depth] if temporal_radices else ())
    return _compose_scope(prefix, temporal)


def infer_specificity(address: str) -> str:
    depth = parse_time_address(address).depth
    if depth <= 1:
        return "year"
    if depth == 2:
        return "month"
    if depth == 3:
        return "day"
    if depth == 4:
        return "hour"
    if depth == 5:
        return "minute"
    return f"segment_{depth}"


def compare_time_addresses(a: str, b: str) -> int:
    aa = parse_time_address(a).segments
    bb = parse_time_address(b).segments
    min_len = min(len(aa), len(bb))
    for idx in range(min_len):
        if aa[idx] < bb[idx]:
            return -1
        if aa[idx] > bb[idx]:
            return 1
    if len(aa) == len(bb):
        return 0
    return -1 if len(aa) < len(bb) else 1


def _same_prefix(a: ParsedTimeAddress, b: ParsedTimeAddress) -> bool:
    return a.prefix == b.prefix


def _pad_temporal(values: tuple[int, ...], depth: int, fill: int) -> tuple[int, ...]:
    if len(values) >= depth:
        return values[:depth]
    return tuple(list(values) + [fill] * (depth - len(values)))


def _scope_bounds(address: str, *, schema_payload: dict[str, Any] | None = None) -> tuple[str, str]:
    parsed = parse_time_address(address)
    temporal = parsed.temporal
    depth = len(temporal)
    if depth < 1:
        raise ValueError("time address must include at least one temporal segment")
    target_len = 2 + max(depth, _MAX_TEMPORAL_DEPTH)
    if schema_payload is not None:
        all_radices = _effective_radices(schema_payload, target_len)
        clipped = list(_clamp_to_radices(parsed.segments, all_radices[: len(parsed.segments)]))
    else:
        all_radices = tuple([10**9] * target_len)
        clipped = list(parsed.segments)
    while len(clipped) < target_len:
        clipped.append(0)
    start = list(clipped)
    end = list(clipped)
    for idx in range(2 + depth, target_len):
        start[idx] = 0
        end[idx] = max(0, all_radices[idx] - 1) if idx < len(all_radices) else 10**9
    start_text = "-".join(str(item) for item in start)
    end_text = "-".join(str(item) for item in end)
    return start_text, end_text


def normalize_range(
    start: str,
    end: str,
    *,
    allow_repair: bool = True,
    schema_payload: dict[str, Any] | None = None,
) -> tuple[str, str]:
    a = parse_time_address(start)
    b = parse_time_address(end)
    if not _same_prefix(a, b):
        raise ValueError("range endpoints must share the same cosmological prefix")

    left = a.temporal
    right = b.temporal
    if len(left) != len(right):
        if not allow_repair:
            raise ValueError("mixed-specificity ranges are invalid without normalization")
        depth = max(len(left), len(right))
        left = _pad_temporal(left, depth, 0)
        if schema_payload is not None:
            radices = _effective_radices(schema_payload, 2 + depth)[2:]
            right_fill = tuple(max(0, int(item) - 1) for item in radices)
            right = tuple(list(right) + list(right_fill[len(right) : depth]))
        else:
            right = _pad_temporal(right, depth, 10**9)

    start_norm = _compose_scope(a.prefix, left)
    end_norm = _compose_scope(a.prefix, right)
    if schema_payload is not None:
        start_norm = normalize_time_address_for_schema(start_norm, schema_payload)
        end_norm = normalize_time_address_for_schema(end_norm, schema_payload)
    if compare_time_addresses(start_norm, end_norm) > 0:
        raise ValueError("range start must be <= range end")
    return start_norm, end_norm


def contains_address(container: str, candidate: str) -> bool:
    a = parse_time_address(container)
    b = parse_time_address(candidate)
    if not _same_prefix(a, b):
        return False
    if len(a.temporal) > len(b.temporal):
        return False
    for idx, value in enumerate(a.temporal):
        if b.temporal[idx] != value:
            return False
    return True


def same_scope(
    selected_scope: str,
    object_range: list[str] | tuple[str, str],
    *,
    schema_payload: dict[str, Any] | None = None,
) -> bool:
    if not isinstance(object_range, (list, tuple)) or len(object_range) != 2:
        return False
    selected_start, selected_end = _scope_bounds(selected_scope, schema_payload=schema_payload)
    obj_start, obj_end = normalize_range(
        str(object_range[0]),
        str(object_range[1]),
        allow_repair=True,
        schema_payload=schema_payload,
    )
    return not (
        compare_time_addresses(obj_end, selected_start) < 0
        or compare_time_addresses(obj_start, selected_end) > 0
    )


def projection_year_month_day(selected_scope: str, *, schema_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = parse_time_address(selected_scope)
    denotations = _effective_radices(schema_payload, max(3, len(parsed.segments)))
    segment_radices = tuple(denotations[2:]) if len(denotations) >= 3 else ()
    year = int(parsed.temporal[0]) if parsed.temporal else 0
    month_radix = int(segment_radices[1]) if len(segment_radices) >= 2 else 12
    day_radix = int(segment_radices[2]) if len(segment_radices) >= 3 else 31
    month = int(parsed.temporal[1]) if len(parsed.temporal) >= 2 else 0
    day = int(parsed.temporal[2]) if len(parsed.temporal) >= 3 else 0
    year = max(0, min(year, max(0, (segment_radices[0] - 1) if segment_radices else 999)))
    month = max(0, min(month, max(0, month_radix - 1)))
    day = max(0, min(day, max(0, day_radix - 1)))
    month_labels = [f"M{idx + 1}" for idx in range(max(1, month_radix))]
    prev_year = year - 1 if year > 0 else max(0, (segment_radices[0] - 1) if segment_radices else 0)
    next_year = 0 if segment_radices and year >= (segment_radices[0] - 1) else year + 1
    month_scope = _compose_scope(parsed.prefix, (year, month))
    day_scope = _compose_scope(parsed.prefix, (year, month, day))
    return {
        "selected_scope": normalize_time_address(selected_scope),
        "specificity": infer_specificity(selected_scope),
        "year": year,
        "month": month,
        "day": day,
        "prefix": [int(parsed.prefix[0]), int(parsed.prefix[1])],
        "segment_radices": list(segment_radices),
        "month_labels": month_labels,
        "months_in_year": max(1, month_radix),
        "days_in_month": max(1, day_radix),
        "month_scope": month_scope,
        "day_scope": day_scope,
        "prev_year_scope": _compose_scope(parsed.prefix, (prev_year,)),
        "next_year_scope": _compose_scope(parsed.prefix, (next_year,)),
    }


__all__ = [
    "ParsedTimeAddress",
    "compare_time_addresses",
    "contains_address",
    "default_time_scope_for_schema",
    "infer_specificity",
    "normalize_range",
    "normalize_time_address",
    "normalize_time_address_for_schema",
    "parse_time_address",
    "projection_year_month_day",
    "same_scope",
]
