"""Canonical raw-event contract for the analytics log.

A row in the NDJSON log is one observed event. The schema is split
into two layers:

  * **Client-stamped** fields (occurred_at_utc, event_type, page_path,
    session_id, etc.) — supplied by the browser via
    ``POST /__fnd/analytics/event``.
  * **Server-stamped** fields (received_at_utc,
    visitor_cookie_id_hash, ip_hash, ip_prefix, is_bot, bot_class,
    bot_evidence, schema_version, collector_version, domain,
    event_id) — derived inside the route from the request +
    cookies + IP + UA.

No "insights" are persisted here — bot_class is *evidence* (UA
regex match), not a *conclusion* about whether the visitor is real.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

EVENT_SCHEMA = "mycite.v2.analytics.event.v2"
COLLECTOR_VERSION = "fnd-analytics/2.0"

KNOWN_EVENT_TYPES = frozenset(
    {
        "page_view",
        "click",
        "scroll",
        "heartbeat",
        "form_submit",
        "outbound_click",
        "download",
        "error",
        "ops_probe",
    }
)

# The smallest fact-set that makes an event row meaningful. Everything
# else is optional and falls back to empty strings / zero / None.
REQUIRED_EVENT_FIELDS = ("event_type", "occurred_at_utc", "session_id", "page_path")

# Bound the free-form ``properties`` JSON to defeat abuse / accidental
# unbounded blobs. Anything beyond this is dropped at write time.
MAX_PROPERTIES_BYTES = 4 * 1024
# Bound user-agent / referrer text the same way.
MAX_TEXT_FIELD_BYTES = 2 * 1024


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _as_text(value).lower() in {"true", "1", "yes"}


def _bounded(text: str, *, limit: int = MAX_TEXT_FIELD_BYTES) -> str:
    return text[:limit] if len(text) > limit else text


def salted_hash(value: str, *, salt: str) -> str:
    """Stable salted hash for visitor / IP identifiers.

    The salt is a per-instance secret held under
    ``<private>/utilities/tools/analytics/secret.txt`` so production
    hashes never collide with test fixtures and the raw cookie /
    IP values are never persistable from the digest.
    """
    if not _as_text(value):
        return ""
    digest = hashlib.sha256()
    digest.update((salt or "").encode("utf-8"))
    digest.update(b"::")
    digest.update(_as_text(value).encode("utf-8"))
    return digest.hexdigest()


def coarse_ip_prefix(ip: str) -> str:
    """Return a coarse IP-prefix token suitable for VPN / geo-jump
    heuristics. IPv4 → ``a.b.c.0/24``; IPv6 → first 3 hextets +
    ``::/48``. Empty / unrecognised input returns the empty string.
    """
    token = _as_text(ip)
    if not token:
        return ""
    if ":" in token:
        # IPv6 — keep the first 3 hextets, anonymise the rest.
        parts = token.split(":")
        head = ":".join(parts[:3])
        return f"{head}::/48"
    parts = token.split(".")
    if len(parts) != 4:
        return ""
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"


def _new_event_id() -> str:
    """ULID-shaped 26-char identifier. k-sortable by timestamp
    prefix so the NDJSON files stay roughly chronological even if a
    delayed event slips in.
    """
    millis = int(time.time() * 1000)
    rand = secrets.token_bytes(10)
    return f"{millis:012x}-{rand.hex()}"


@dataclass(frozen=True)
class RawEvent:
    """Raw event row. Field set is the entire factual schema; the
    derivation layer reads these without ever re-writing the row.
    """

    # Server-stamped
    event_id: str
    received_at_utc: str
    schema_version: str
    collector_version: str
    site_id: str
    domain: str
    environment: str
    visitor_cookie_id_hash: str
    ip_hash: str
    ip_prefix: str
    is_bot: bool
    bot_class: str
    bot_evidence: tuple[str, ...]

    # Client-stamped (required subset)
    event_type: str
    occurred_at_utc: str
    session_id: str
    page_path: str

    # Client-stamped (optional)
    event_name: str = ""
    event_index_in_session: int = 0
    page_query_hash: str = ""
    page_title: str = ""
    referrer_url: str = ""
    referrer_domain: str = ""
    origin_type: str = ""
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    utm_content: str = ""
    utm_term: str = ""
    previous_page_path: str = ""
    time_since_previous_ms: int = 0
    active_time_ms: int = 0
    visible_time_ms: int = 0
    scroll_depth_percent: int = 0
    user_agent_raw: str = ""
    device_type: str = ""
    browser_name: str = ""
    viewport_width: int = 0
    viewport_height: int = 0
    language: str = ""
    do_not_track: bool = False
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_request(
        cls,
        body: dict[str, Any],
        *,
        domain: str,
        site_id: str,
        environment: str,
        visitor_cookie: str,
        remote_addr: str,
        user_agent: str,
        salt: str,
        received_at_utc: str,
    ) -> RawEvent:
        """Build a RawEvent from a request body + server context.

        Raises ``ValueError`` if any required field is missing or
        the event_type isn't in ``KNOWN_EVENT_TYPES``.
        """
        if not isinstance(body, dict):
            raise ValueError("analytics event body must be a JSON object")
        for key in REQUIRED_EVENT_FIELDS:
            if not _as_text(body.get(key)):
                raise ValueError(f"missing required field: {key}")
        event_type = _as_text(body.get("event_type"))
        if event_type not in KNOWN_EVENT_TYPES:
            raise ValueError(f"unknown event_type: {event_type!r}")

        # Lazy import: bot_detection lives next door but importing
        # at module top would create a cycle once derivations.py
        # consumes both.
        from .bot_detection import classify_user_agent

        is_bot, bot_class, bot_evidence = classify_user_agent(user_agent)

        properties_raw = body.get("properties")
        properties: dict[str, Any] = {}
        if isinstance(properties_raw, dict):
            # Cheap bound: serialised size <= MAX_PROPERTIES_BYTES.
            import json as _json

            raw = _json.dumps(properties_raw, separators=(",", ":"))
            if len(raw) <= MAX_PROPERTIES_BYTES:
                properties = dict(properties_raw)

        return cls(
            event_id=_new_event_id(),
            received_at_utc=received_at_utc,
            schema_version=EVENT_SCHEMA,
            collector_version=COLLECTOR_VERSION,
            site_id=_as_text(site_id) or _as_text(domain),
            domain=_as_text(domain).lower(),
            environment=_as_text(environment) or "prod",
            visitor_cookie_id_hash=salted_hash(visitor_cookie, salt=salt),
            ip_hash=salted_hash(remote_addr, salt=salt),
            ip_prefix=coarse_ip_prefix(remote_addr),
            is_bot=is_bot,
            bot_class=bot_class,
            bot_evidence=tuple(bot_evidence),
            event_type=event_type,
            occurred_at_utc=_as_text(body.get("occurred_at_utc")),
            session_id=_bounded(_as_text(body.get("session_id"))),
            page_path=_bounded(_as_text(body.get("page_path"))),
            event_name=_bounded(_as_text(body.get("event_name"))),
            event_index_in_session=_as_int(body.get("event_index_in_session")),
            page_query_hash=_bounded(_as_text(body.get("page_query_hash"))),
            page_title=_bounded(_as_text(body.get("page_title"))),
            referrer_url=_bounded(_as_text(body.get("referrer_url"))),
            referrer_domain=_bounded(_as_text(body.get("referrer_domain"))),
            origin_type=_bounded(_as_text(body.get("origin_type"))),
            utm_source=_bounded(_as_text(body.get("utm_source"))),
            utm_medium=_bounded(_as_text(body.get("utm_medium"))),
            utm_campaign=_bounded(_as_text(body.get("utm_campaign"))),
            utm_content=_bounded(_as_text(body.get("utm_content"))),
            utm_term=_bounded(_as_text(body.get("utm_term"))),
            previous_page_path=_bounded(_as_text(body.get("previous_page_path"))),
            time_since_previous_ms=_as_int(body.get("time_since_previous_ms")),
            active_time_ms=_as_int(body.get("active_time_ms")),
            visible_time_ms=_as_int(body.get("visible_time_ms")),
            scroll_depth_percent=_as_int(body.get("scroll_depth_percent")),
            user_agent_raw=_bounded(_as_text(user_agent)),
            device_type=_bounded(_as_text(body.get("device_type"))),
            browser_name=_bounded(_as_text(body.get("browser_name"))),
            viewport_width=_as_int(body.get("viewport_width")),
            viewport_height=_as_int(body.get("viewport_height")),
            language=_bounded(_as_text(body.get("language"))),
            do_not_track=_as_bool(body.get("do_not_track")),
            properties=properties,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "collector_version": self.collector_version,
            "event_id": self.event_id,
            "received_at_utc": self.received_at_utc,
            "site_id": self.site_id,
            "domain": self.domain,
            "environment": self.environment,
            "visitor_cookie_id_hash": self.visitor_cookie_id_hash,
            "ip_hash": self.ip_hash,
            "ip_prefix": self.ip_prefix,
            "is_bot": self.is_bot,
            "bot_class": self.bot_class,
            "bot_evidence": list(self.bot_evidence),
            "event_type": self.event_type,
            "occurred_at_utc": self.occurred_at_utc,
            "session_id": self.session_id,
            "page_path": self.page_path,
            "event_name": self.event_name,
            "event_index_in_session": self.event_index_in_session,
            "page_query_hash": self.page_query_hash,
            "page_title": self.page_title,
            "referrer_url": self.referrer_url,
            "referrer_domain": self.referrer_domain,
            "origin_type": self.origin_type,
            "utm_source": self.utm_source,
            "utm_medium": self.utm_medium,
            "utm_campaign": self.utm_campaign,
            "utm_content": self.utm_content,
            "utm_term": self.utm_term,
            "previous_page_path": self.previous_page_path,
            "time_since_previous_ms": self.time_since_previous_ms,
            "active_time_ms": self.active_time_ms,
            "visible_time_ms": self.visible_time_ms,
            "scroll_depth_percent": self.scroll_depth_percent,
            "user_agent_raw": self.user_agent_raw,
            "device_type": self.device_type,
            "browser_name": self.browser_name,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "language": self.language,
            "do_not_track": self.do_not_track,
            "properties": dict(self.properties),
        }


__all__ = [
    "COLLECTOR_VERSION",
    "EVENT_SCHEMA",
    "KNOWN_EVENT_TYPES",
    "MAX_PROPERTIES_BYTES",
    "MAX_TEXT_FIELD_BYTES",
    "REQUIRED_EVENT_FIELDS",
    "RawEvent",
    "coarse_ip_prefix",
    "salted_hash",
]
