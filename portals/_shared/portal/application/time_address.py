from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from calendar import monthrange
from typing import Any


_TIME_SCOPE_PREFIX = (13, 787)
_TIME_SCOPE_PREFIX_ALT = (13, 786)
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
    if prefix not in {_TIME_SCOPE_PREFIX, _TIME_SCOPE_PREFIX_ALT}:
        # Keep parser permissive for forward compatibility while preserving examples.
        prefix = (segments[0], segments[1])
    return ParsedTimeAddress(segments=segments, prefix=prefix, temporal=temporal)


def normalize_time_address(address: str) -> str:
    parsed = parse_time_address(address)
    return "-".join(str(item) for item in parsed.segments)


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


def _days_in_month(year: int, month: int) -> int:
    if month < 1:
        month = 1
    if month > 12:
        month = 12
    year = max(1, year)
    try:
        return int(monthrange(year, month)[1])
    except Exception:
        return 31


def _scope_bounds(address: str) -> tuple[str, str]:
    parsed = parse_time_address(address)
    temporal = parsed.temporal
    depth = len(temporal)
    if depth < 1:
        raise ValueError("time address must include at least year")
    year = temporal[0]
    month = temporal[1] if depth >= 2 else 1
    day = temporal[2] if depth >= 3 else 1
    hour = temporal[3] if depth >= 4 else 0
    minute = temporal[4] if depth >= 5 else 0

    if depth == 1:
        start = (year, 1, 1, 0, 0)
        end = (year, 12, 31, 23, 59)
    elif depth == 2:
        mdays = _days_in_month(year, month)
        start = (year, month, 1, 0, 0)
        end = (year, month, mdays, 23, 59)
    elif depth == 3:
        start = (year, month, day, 0, 0)
        end = (year, month, day, 23, 59)
    elif depth == 4:
        start = (year, month, day, hour, 0)
        end = (year, month, day, hour, 59)
    else:
        start = (year, month, day, hour, minute)
        end = (year, month, day, hour, minute)

    start_text = "-".join(str(item) for item in (*parsed.prefix, *start))
    end_text = "-".join(str(item) for item in (*parsed.prefix, *end))
    return start_text, end_text


def normalize_range(start: str, end: str, *, allow_repair: bool = True) -> tuple[str, str]:
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
        right = _pad_temporal(right, depth, 0)

    start_norm = "-".join(str(item) for item in (*a.prefix, *left))
    end_norm = "-".join(str(item) for item in (*a.prefix, *right))
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


def same_scope(selected_scope: str, object_range: list[str] | tuple[str, str]) -> bool:
    if not isinstance(object_range, (list, tuple)) or len(object_range) != 2:
        return False
    selected_start, selected_end = _scope_bounds(selected_scope)
    obj_start, obj_end = normalize_range(str(object_range[0]), str(object_range[1]), allow_repair=True)
    return not (
        compare_time_addresses(obj_end, selected_start) < 0
        or compare_time_addresses(obj_start, selected_end) > 0
    )


def projection_year_month_day(selected_scope: str) -> dict[str, Any]:
    parsed = parse_time_address(selected_scope)
    now = datetime.now(timezone.utc)
    year = int(parsed.temporal[0]) if parsed.temporal else int(now.year)
    month = int(parsed.temporal[1]) if len(parsed.temporal) >= 2 else int(now.month)
    day = int(parsed.temporal[2]) if len(parsed.temporal) >= 3 else int(now.day)
    month = max(1, min(12, month))
    day = max(1, min(_days_in_month(year, month), day))
    month_labels = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    return {
        "selected_scope": normalize_time_address(selected_scope),
        "specificity": infer_specificity(selected_scope),
        "year": year,
        "month": month,
        "day": day,
        "month_labels": month_labels,
        "days_in_month": _days_in_month(year, month),
        "prev_year_scope": f"{parsed.prefix[0]}-{parsed.prefix[1]}-{year - 1}",
        "next_year_scope": f"{parsed.prefix[0]}-{parsed.prefix[1]}-{year + 1}",
    }


__all__ = [
    "ParsedTimeAddress",
    "compare_time_addresses",
    "contains_address",
    "infer_specificity",
    "normalize_range",
    "normalize_time_address",
    "parse_time_address",
    "projection_year_month_day",
    "same_scope",
]
