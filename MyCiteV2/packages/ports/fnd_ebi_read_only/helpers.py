from __future__ import annotations

from typing import Any

NDJSON_KIND_COUNTS_KEY = "event_type_counts"


def classify_ndjson_log_kind(payload: dict[str, Any]) -> str:
    for key in ("event_type", "event", "type", "name", "action"):
        value = payload.get(key)
        token = "" if value is None else str(value).strip().lower()
        if token:
            return token
    schema = "" if payload.get("schema") is None else str(payload.get("schema")).strip().lower()
    if schema.endswith(".web_event.v1"):
        return "web_event"
    return "unknown"


__all__ = [
    "NDJSON_KIND_COUNTS_KEY",
    "classify_ndjson_log_kind",
]
