"""Read-only operations over the raw analytics event log.

Every function in this module is a *pure derivation*: it reads
events (already-persisted RawEvent dicts) and returns a
JSON-serializable summary. No I/O beyond reading NDJSON files, no
mutation, no caching at the function level (the caller decides
when to memoize).

This file ships the operations 18a depends on. 18c extends with
the richer insight set (page-attention ranks, referrer ranks,
path-sequence enumeration, conversion funnels, etc.).
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem.analytics_event_paths import (
    AnalyticsEventPathResolver,
)

# Default sessionization gap: a visitor is in the same session as
# long as consecutive events are within this many ms.
DEFAULT_INACTIVITY_GAP_MS = 30 * 60 * 1000


def _year_months_between(start: str, end: str) -> list[str]:
    """Inclusive list of YYYY-MM tokens between two YYYY-MM bounds."""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out: list[str] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def read_events(
    *,
    domain: str,
    year_months: Iterable[str],
    webapps_root: str | Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield events from one or more NDJSON files for a domain.

    Skips lines that fail to parse instead of raising — a single
    bad line shouldn't kill the whole derivation pipeline. Caller
    enumerates the year_months explicitly so the read scope is
    bounded.
    """
    resolver = AnalyticsEventPathResolver(
        webapps_root=webapps_root or Path("/srv/webapps")
    )
    for year_month in year_months:
        try:
            resolution = resolver.resolve_events_file(
                domain=domain, year_month=year_month
            )
        except ValueError:
            continue
        path = resolution.events_file
        if not path.exists() or not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


def filter_bots(
    events: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(human_events, bot_events)`` based on ``is_bot``.

    The raw event captures bot_class as evidence (UA-regex match);
    this function is the canonical split for downstream analytics
    that want to look at one population at a time.
    """
    humans: list[dict[str, Any]] = []
    bots: list[dict[str, Any]] = []
    for event in events:
        if event.get("is_bot"):
            bots.append(event)
        else:
            humans.append(event)
    return humans, bots


def reconstruct_visitor_timeline(
    events: Iterable[dict[str, Any]],
    *,
    visitor_cookie_id_hash: str,
) -> list[dict[str, Any]]:
    """Return all events for one visitor, ordered by occurred_at_utc.

    The hash is the salted visitor_cookie_id_hash from the raw
    event row — callers typically obtain it by reading one event
    and following up with this function for the visitor's full
    history.
    """
    if not visitor_cookie_id_hash:
        return []
    rows = [
        event
        for event in events
        if event.get("visitor_cookie_id_hash") == visitor_cookie_id_hash
    ]
    rows.sort(key=lambda e: e.get("occurred_at_utc") or "")
    return rows


def _to_epoch_ms(iso_string: str) -> int:
    """Parse an ISO-8601 timestamp into epoch ms. Returns 0 on
    failure so sessionize can still group events deterministically
    even when the client clock is missing.
    """
    if not iso_string:
        return 0
    import datetime as _dt

    try:
        # Python 3.11+ handles trailing 'Z'.
        dt = _dt.datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def sessionize(
    events: Iterable[dict[str, Any]],
    *,
    inactivity_gap_ms: int = DEFAULT_INACTIVITY_GAP_MS,
) -> list[dict[str, Any]]:
    """Group events into sessions per visitor.

    Within one visitor, consecutive events whose ``occurred_at_utc``
    gap exceeds ``inactivity_gap_ms`` start a new session. The
    client-supplied ``session_id`` is honored as a tiebreaker — if
    it changes between two adjacent events, that always starts a
    new session even when the time gap is small.

    Returns a flat list of session summary dicts:

      ``[{visitor_cookie_id_hash, session_id, started_at_utc,
         ended_at_utc, duration_ms, active_time_ms,
         page_view_count, entry_page, exit_page, origin_type,
         referrer_domain, event_types}, ...]``
    """
    by_visitor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        visitor = event.get("visitor_cookie_id_hash") or ""
        by_visitor[visitor].append(event)

    summaries: list[dict[str, Any]] = []
    for visitor, rows in by_visitor.items():
        rows.sort(key=lambda e: e.get("occurred_at_utc") or "")
        current: list[dict[str, Any]] = []
        last_ms: int | None = None
        last_session_id: str | None = None
        for event in rows:
            event_ms = _to_epoch_ms(event.get("occurred_at_utc") or "")
            client_session = event.get("session_id") or ""
            split = False
            if last_ms is not None and event_ms - last_ms > inactivity_gap_ms:
                split = True
            if last_session_id is not None and client_session != last_session_id:
                split = True
            if split and current:
                summaries.append(_summarize_session(visitor, current))
                current = []
            current.append(event)
            last_ms = event_ms
            last_session_id = client_session
        if current:
            summaries.append(_summarize_session(visitor, current))
    summaries.sort(key=lambda s: s.get("started_at_utc") or "", reverse=True)
    return summaries


def _summarize_session(
    visitor_cookie_id_hash: str, events: list[dict[str, Any]]
) -> dict[str, Any]:
    started = events[0].get("occurred_at_utc") or ""
    ended = events[-1].get("occurred_at_utc") or ""
    started_ms = _to_epoch_ms(started)
    ended_ms = _to_epoch_ms(ended)
    duration_ms = max(0, ended_ms - started_ms) if started_ms and ended_ms else 0
    active_time_ms = sum(int(e.get("active_time_ms") or 0) for e in events)
    page_view_count = sum(1 for e in events if e.get("event_type") == "page_view")
    page_views = [e for e in events if e.get("event_type") == "page_view"]
    entry_page = page_views[0].get("page_path") if page_views else (events[0].get("page_path") or "")
    exit_page = page_views[-1].get("page_path") if page_views else (events[-1].get("page_path") or "")
    first = events[0]
    return {
        "visitor_cookie_id_hash": visitor_cookie_id_hash,
        "session_id": first.get("session_id") or "",
        "started_at_utc": started,
        "ended_at_utc": ended,
        "duration_ms": duration_ms,
        "active_time_ms": active_time_ms,
        "page_view_count": page_view_count,
        "entry_page": entry_page,
        "exit_page": exit_page,
        "origin_type": first.get("origin_type") or classify_origin(
            first.get("referrer_domain") or "", first.get("utm_source") or ""
        ),
        "referrer_domain": first.get("referrer_domain") or "",
        "event_types": sorted({e.get("event_type") or "" for e in events}),
        "is_bot": any(e.get("is_bot") for e in events),
        "is_bounce": page_view_count <= 1 and len(events) <= 2,
    }


def classify_origin(referrer_domain: str, utm_source: str = "") -> str:
    """Bucket a session's entry source into one of the canonical
    origin types: direct / search / social / email / paid / referral
    / internal / unknown.
    """
    utm = (utm_source or "").lower().strip()
    if utm == "newsletter" or utm == "email":
        return "email"
    if utm in {"google", "bing", "facebook", "twitter", "tiktok", "linkedin"}:
        # An explicit utm_source from a search/social ad is paid.
        return "paid"
    domain = (referrer_domain or "").lower().strip()
    if not domain:
        return "direct"
    if any(s in domain for s in ("google.", "bing.", "duckduckgo.", "yahoo.")):
        return "search"
    if any(
        s in domain
        for s in (
            "facebook.",
            "twitter.",
            "x.com",
            "instagram.",
            "tiktok.",
            "linkedin.",
            "reddit.",
            "youtube.",
        )
    ):
        return "social"
    if "mail." in domain or "gmail." in domain or "outlook." in domain:
        return "email"
    # An internal jump shows the same domain as the page being viewed,
    # but at this layer we don't have the page's domain — caller can
    # post-process. Default to referral.
    return "referral"


__all__ = [
    "DEFAULT_INACTIVITY_GAP_MS",
    "classify_origin",
    "filter_bots",
    "read_events",
    "reconstruct_visitor_timeline",
    "sessionize",
]
