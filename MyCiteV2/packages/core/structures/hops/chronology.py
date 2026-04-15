from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .time_address import normalize_time_address_for_schema

_SECONDS_PER_DAY = 24 * 60 * 60


@dataclass(frozen=True)
class ChronologyAuthority:
    schema_payload: dict[str, Any]
    quadrennium_payload: dict[str, Any]
    cosmological_prefix: tuple[int, int] = (0, 0)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_quadrennium_authority(payload: dict[str, Any]) -> None:
    row = payload.get("3-1-1")
    if not isinstance(row, list) or not row:
        raise ValueError("quadrennium authority is missing HOPS-babelette-quadrennium_cycle")


def build_chronology_authority(
    *,
    schema_payload: dict[str, Any],
    quadrennium_payload: dict[str, Any],
    cosmological_prefix: tuple[int, int] = (0, 0),
) -> ChronologyAuthority:
    if not bool(schema_payload.get("ok")):
        raise ValueError(str(schema_payload.get("error") or "chronology schema is unavailable"))
    _require_quadrennium_authority(quadrennium_payload)
    return ChronologyAuthority(
        schema_payload=dict(schema_payload),
        quadrennium_payload=dict(quadrennium_payload),
        cosmological_prefix=(int(cosmological_prefix[0]), int(cosmological_prefix[1])),
    )


def _as_utc_datetime(value: datetime | int | float) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    number = float(value)
    if number > 10_000_000_000:
        number = number / 1000.0
    return datetime.fromtimestamp(number, tz=timezone.utc)


def _day_in_quadrennium(current: datetime, cycle_start_year: int) -> int:
    cycle_start = datetime(cycle_start_year, 1, 1, tzinfo=timezone.utc)
    delta = current - cycle_start
    day_index = int(delta.total_seconds() // _SECONDS_PER_DAY) + 1
    if day_index < 1:
        raise ValueError("computed day-in-cycle fell below 1")
    return day_index


def encode_utc_datetime_as_hops(
    value: datetime | int | float,
    *,
    authority: ChronologyAuthority,
) -> str:
    current = _as_utc_datetime(value)
    cycle_start_year = current.year - (current.year % 4)
    cycle_group = cycle_start_year // 4000
    cycle = (cycle_start_year // 4) + 1 - (cycle_group * 1000)
    day_in_cycle = _day_in_quadrennium(current, cycle_start_year)
    address = "-".join(
        str(part)
        for part in (
            authority.cosmological_prefix[0],
            authority.cosmological_prefix[1],
            cycle_group,
            cycle,
            day_in_cycle,
            current.hour,
            current.minute,
            current.second,
        )
    )
    return normalize_time_address_for_schema(address, authority.schema_payload)


def encode_unix_ms_as_hops(unix_ms: int | float, *, authority: ChronologyAuthority) -> str:
    return encode_utc_datetime_as_hops(unix_ms, authority=authority)


__all__ = [
    "ChronologyAuthority",
    "build_chronology_authority",
    "encode_unix_ms_as_hops",
    "encode_utc_datetime_as_hops",
]
