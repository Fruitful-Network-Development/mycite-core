from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable


def iter_string_values(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from iter_string_values(nested)
        return
    if isinstance(value, list):
        for nested in value:
            yield from iter_string_values(nested)
        return
    if value is None:
        return
    token = str(value).strip()
    if token:
        yield token


def event_contains_any(event: dict[str, Any], tokens: list[str]) -> bool:
    needles = [str(item).strip().lower() for item in tokens if str(item).strip()]
    if not needles:
        return False
    for value in iter_string_values(event):
        lowered = value.lower()
        if any(needle in lowered for needle in needles):
            return True
    return False


def event_channel_id(event: dict[str, Any]) -> str:
    transmitter = str(event.get("transmitter") or "").strip()
    receiver = str(event.get("receiver") or "").strip()
    if transmitter and receiver:
        return f"{transmitter}->{receiver}"
    return ""


def format_event_timestamp(ts_unix_ms: Any) -> str:
    try:
        stamp = int(ts_unix_ms or 0)
    except Exception:
        return ""
    if stamp <= 0:
        return ""
    try:
        return datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ""


def initials(token: str, fallback: str = "NW") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", str(token or "").strip())
    parts = [part for part in cleaned.split() if part]
    if not parts:
        return fallback
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[1][0]}".upper()


def event_actor_label(event: dict[str, Any], *, local_msn_id: str) -> str:
    transmitter = str(event.get("transmitter") or "").strip()
    receiver = str(event.get("receiver") or "").strip()
    if transmitter:
        if local_msn_id and local_msn_id in transmitter:
            return "Current Portal"
        return transmitter
    if receiver:
        return receiver
    return "Network Event"


def event_summary(event: dict[str, Any]) -> str:
    summary_parts: list[str] = []
    for key in ("status", "receiver", "alias_id", "contract_id", "tenant_msn_id", "client_id", "event_datum"):
        value = str(event.get(key) or "").strip()
        if value:
            summary_parts.append(f"{key}: {value}")
    details = event.get("details")
    if isinstance(details, dict) and details:
        summary_parts.append("details: " + ", ".join(sorted(str(key) for key in details.keys())[:4]))
    return " | ".join(summary_parts[:4])


def network_placeholder_item(kind: str, selected: dict[str, Any] | None) -> dict[str, Any]:
    label = str((selected or {}).get("label") or "conversation").strip()
    if kind == "alias":
        headline = "Interface ready"
        summary = f"No request-log events have been mapped to {label} yet."
    elif kind == "p2p":
        headline = "Direct thread is quiet"
        summary = f"No transmitter/receiver events have been recorded for {label} yet."
    else:
        headline = "Request log ready"
        summary = "No request-log entries have been recorded yet."
    payload = {"selection": selected or {}, "kind": kind}
    return {
        "side": "system",
        "author": "Workbench",
        "avatar": initials(label, "WB"),
        "role": "preview",
        "headline": headline,
        "summary": summary,
        "timestamp": "",
        "payload_json": json.dumps(payload, indent=2, sort_keys=True),
    }


def build_network_message_feed(
    *,
    kind: str,
    selected_alias: dict[str, Any] | None,
    selected_log: dict[str, Any] | None,
    selected_p2p: dict[str, Any] | None,
    local_msn_id: str,
    iter_request_log_records_fn: Callable[[], list[dict[str, Any]]],
    resolve_refs_fn: Callable[[dict[str, Any], str], dict[str, Any]],
) -> list[dict[str, Any]]:
    events = iter_request_log_records_fn()
    filtered: list[dict[str, Any]]
    selected: dict[str, Any] | None

    if kind == "alias":
        selected = selected_alias
        tokens = [
            str((selected_alias or {}).get("id") or "").strip(),
            str((selected_alias or {}).get("alias_id") or "").strip(),
            str((selected_alias or {}).get("org_msn_id") or "").strip(),
            str((selected_alias or {}).get("tenant_id") or "").strip(),
            str((selected_alias or {}).get("label") or "").strip(),
        ]
        filtered = [event for event in events if event_contains_any(event, tokens)]
    elif kind == "p2p":
        selected = selected_p2p
        channel_id = str((selected_p2p or {}).get("id") or "").strip()
        filtered = [event for event in events if event_channel_id(event) == channel_id]
    else:
        selected = selected_log
        filtered = list(events)

    filtered = sorted(filtered, key=lambda item: int(item.get("ts_unix_ms") or 0))
    if len(filtered) > 60:
        filtered = filtered[-60:]
    if not filtered:
        return [network_placeholder_item(kind, selected)]

    feed: list[dict[str, Any]] = []
    for event in filtered:
        transmitter = str(event.get("transmitter") or "").strip()
        side = "system"
        if transmitter:
            side = "outbound" if local_msn_id and local_msn_id in transmitter else "inbound"
        preview_payload = {key: value for key, value in event.items() if key != "msn_id"}
        resolved_refs = resolve_refs_fn(event, str(event.get("contract_id") or "").strip())
        if resolved_refs:
            preview_payload["mss_resolution"] = resolved_refs
        author = event_actor_label(event, local_msn_id=local_msn_id)
        feed.append(
            {
                "side": side,
                "author": author,
                "avatar": initials(author, "EV"),
                "role": str(event.get("status") or "event").strip(),
                "headline": str(event.get("type") or "event").strip(),
                "summary": event_summary(event),
                "timestamp": format_event_timestamp(event.get("ts_unix_ms")),
                "payload_json": json.dumps(preview_payload, indent=2, sort_keys=True),
            }
        )
    return feed
