from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso(*, seconds_precision: bool = False) -> str:
    now = datetime.now(timezone.utc)
    if seconds_precision:
        now = now.replace(microsecond=0)
    return now.isoformat()


__all__ = [
    "utc_now_iso",
]
