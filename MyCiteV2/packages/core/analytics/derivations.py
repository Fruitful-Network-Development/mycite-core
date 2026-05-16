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
    resolver: AnalyticsEventPathResolver | None = None,
    analytics_root: str | Path | None = None,
    webapps_root: str | Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield events from one or more NDJSON files for a domain.

    Skips lines that fail to parse instead of raising — a single
    bad line shouldn't kill the whole derivation pipeline. Caller
    enumerates the year_months explicitly so the read scope is
    bounded.

    Resolution priority:
        1. ``resolver`` — explicit injected resolver.
        2. ``analytics_root`` — construct a canonical-mode resolver.
        3. ``webapps_root`` — construct a legacy-mode resolver (the
           historical interface; kept for backward compat).
        4. ``MYCITE_ANALYTICS_ROOT`` env / default canonical root.
    """
    if resolver is None:
        if analytics_root is not None:
            resolver = AnalyticsEventPathResolver(analytics_root=analytics_root)
        elif webapps_root is not None:
            resolver = AnalyticsEventPathResolver(webapps_root=webapps_root)
        else:
            resolver = AnalyticsEventPathResolver()
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


# ---------------------------------------------------------------------
# Phase 18c — richer insight derivations.
# Each function below reads pre-sessionized events (or accepts raw
# events + sessionizes internally) and returns a JSON-serializable
# result that lands in the Analytics extension card.
# ---------------------------------------------------------------------


def count_visitors(
    events: Iterable[dict[str, Any]], *, include_bots: bool = False
) -> int:
    """Distinct visitor cookies seen, optionally including bots."""
    seen: set[str] = set()
    for event in events:
        if not include_bots and event.get("is_bot"):
            continue
        token = event.get("visitor_cookie_id_hash") or ""
        if token:
            seen.add(token)
    return len(seen)


def count_repeat_visitors(
    sessions: Iterable[dict[str, Any]], *, min_sessions: int = 2
) -> int:
    """Number of visitors with at least ``min_sessions`` sessions."""
    by_visitor: dict[str, int] = defaultdict(int)
    for session in sessions:
        if session.get("is_bot"):
            continue
        token = session.get("visitor_cookie_id_hash") or ""
        if not token:
            continue
        by_visitor[token] += 1
    return sum(1 for c in by_visitor.values() if c >= min_sessions)


def rank_pages_by_attention(
    events: Iterable[dict[str, Any]], *, top_k: int = 10
) -> list[dict[str, Any]]:
    """Rank pages by their engagement signals.

    For each ``page_view`` event we accumulate view count, unique
    visitor count, average active_time_ms, and average scroll
    depth. Sorted by view count descending. Bots are excluded.
    """
    by_path: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "view_count": 0,
            "visitors": set(),
            "active_time_ms": 0,
            "active_samples": 0,
            "scroll_depth_total": 0,
            "scroll_samples": 0,
        }
    )
    for event in events:
        if event.get("is_bot"):
            continue
        path = event.get("page_path") or ""
        if not path:
            continue
        bucket = by_path[path]
        if event.get("event_type") == "page_view":
            bucket["view_count"] += 1
            visitor = event.get("visitor_cookie_id_hash")
            if visitor:
                bucket["visitors"].add(visitor)
        active = int(event.get("active_time_ms") or 0)
        if active:
            bucket["active_time_ms"] += active
            bucket["active_samples"] += 1
        scroll = int(event.get("scroll_depth_percent") or 0)
        if scroll:
            bucket["scroll_depth_total"] += scroll
            bucket["scroll_samples"] += 1
    rows: list[dict[str, Any]] = []
    for path, bucket in by_path.items():
        rows.append(
            {
                "page_path": path,
                "view_count": bucket["view_count"],
                "unique_visitors": len(bucket["visitors"]),
                "average_active_time_ms": (
                    bucket["active_time_ms"] // bucket["active_samples"]
                    if bucket["active_samples"]
                    else 0
                ),
                "scroll_depth_average": (
                    bucket["scroll_depth_total"] // bucket["scroll_samples"]
                    if bucket["scroll_samples"]
                    else 0
                ),
            }
        )
    rows.sort(key=lambda r: (r["view_count"], r["unique_visitors"]), reverse=True)
    return rows[:top_k]


def rank_referrers(
    events: Iterable[dict[str, Any]], *, top_k: int = 10
) -> list[dict[str, Any]]:
    """Rank referrer domains by session count.

    Counts each visitor's first event in a session — that's the
    referrer for the whole session.
    """
    by_session: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        if event.get("is_bot"):
            continue
        key = (
            event.get("visitor_cookie_id_hash") or "",
            event.get("session_id") or "",
        )
        if key in by_session:
            continue
        by_session[key] = {
            "referrer_domain": (event.get("referrer_domain") or "").lower(),
            "active_time_ms": int(event.get("active_time_ms") or 0),
        }
    aggregates: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"sessions": 0, "visitors": set(), "active_time_ms": 0}
    )
    for (visitor, _session), info in by_session.items():
        ref = info["referrer_domain"] or "(direct)"
        bucket = aggregates[ref]
        bucket["sessions"] += 1
        if visitor:
            bucket["visitors"].add(visitor)
        bucket["active_time_ms"] += info["active_time_ms"]
    rows = [
        {
            "referrer_domain": ref,
            "sessions": bucket["sessions"],
            "unique_visitors": len(bucket["visitors"]),
            "average_active_time_ms": (
                bucket["active_time_ms"] // bucket["sessions"]
                if bucket["sessions"]
                else 0
            ),
        }
        for ref, bucket in aggregates.items()
    ]
    rows.sort(key=lambda r: r["sessions"], reverse=True)
    return rows[:top_k]


def top_entry_pages(
    sessions: Iterable[dict[str, Any]], *, top_k: int = 10
) -> list[dict[str, Any]]:
    """Pages that most often start a session."""
    counts: dict[str, int] = defaultdict(int)
    for session in sessions:
        if session.get("is_bot"):
            continue
        entry = session.get("entry_page") or ""
        if entry:
            counts[entry] += 1
    rows = [{"page_path": p, "count": c} for p, c in counts.items()]
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows[:top_k]


def top_exit_pages(
    sessions: Iterable[dict[str, Any]], *, top_k: int = 10
) -> list[dict[str, Any]]:
    """Pages that most often end a session."""
    counts: dict[str, int] = defaultdict(int)
    for session in sessions:
        if session.get("is_bot"):
            continue
        exit_page = session.get("exit_page") or ""
        if exit_page:
            counts[exit_page] += 1
    rows = [{"page_path": p, "count": c} for p, c in counts.items()]
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows[:top_k]


def find_common_paths(
    events: Iterable[dict[str, Any]],
    *,
    min_length: int = 2,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Most common ordered page-path sequences within a session.

    Considers each visitor's session as a string of page_view paths
    in order, and counts identical sub-sequences of at least
    ``min_length``. Returns the top_k most common.
    """
    # Build per-session page sequences.
    by_session: dict[tuple[str, str], list[str]] = defaultdict(list)
    for event in events:
        if event.get("is_bot"):
            continue
        if event.get("event_type") != "page_view":
            continue
        key = (
            event.get("visitor_cookie_id_hash") or "",
            event.get("session_id") or "",
        )
        path = event.get("page_path") or ""
        if path:
            by_session[key].append(path)
    counts: dict[tuple[str, ...], int] = defaultdict(int)
    for seq in by_session.values():
        if len(seq) < min_length:
            continue
        # Sliding window from min_length up to full sequence length.
        for window in range(min_length, len(seq) + 1):
            for start in range(0, len(seq) - window + 1):
                counts[tuple(seq[start : start + window])] += 1
    rows = [
        {"path": list(seq), "count": count, "length": len(seq)}
        for seq, count in counts.items()
    ]
    rows.sort(key=lambda r: (r["count"], r["length"]), reverse=True)
    return rows[:top_k]


def high_intent_sessions(
    sessions: Iterable[dict[str, Any]],
    *,
    intent_pages: tuple[str, ...] = ("/pricing", "/contact", "/donate", "/subscribe"),
    min_active_ms: int = 60_000,
) -> list[dict[str, Any]]:
    """Sessions that visited an intent page AND spent meaningful
    active time. Used as the operator's "real buyers" filter.
    """
    intent_set = {p.lower() for p in intent_pages}
    out: list[dict[str, Any]] = []
    for session in sessions:
        if session.get("is_bot"):
            continue
        if session.get("active_time_ms", 0) < min_active_ms:
            continue
        # Cheap heuristic: entry or exit page is an intent page.
        # The full session would need to be re-queried for an
        # exact-match check; this approximation is good enough for
        # the operator-facing high_intent_count metric.
        entry = (session.get("entry_page") or "").lower()
        exit_p = (session.get("exit_page") or "").lower()
        if any(p in entry for p in intent_set) or any(p in exit_p for p in intent_set):
            out.append(session)
    return out


def detect_vpn_geo_jumps(
    events: Iterable[dict[str, Any]],
    *,
    max_prefixes_per_visitor: int = 1,
) -> list[dict[str, Any]]:
    """Suspect VPN / geo-jump: same visitor cookie seen from >1
    distinct ``ip_prefix``. The threshold is conservative — mobile
    networks rotate prefixes legitimately, so this is *evidence*
    not a conclusion.
    """
    prefixes_by_visitor: dict[str, set[str]] = defaultdict(set)
    for event in events:
        visitor = event.get("visitor_cookie_id_hash") or ""
        prefix = event.get("ip_prefix") or ""
        if visitor and prefix:
            prefixes_by_visitor[visitor].add(prefix)
    flagged: list[dict[str, Any]] = []
    for visitor, prefixes in prefixes_by_visitor.items():
        if len(prefixes) > max_prefixes_per_visitor:
            flagged.append(
                {
                    "visitor_cookie_id_hash": visitor,
                    "ip_prefixes": sorted(prefixes),
                    "evidence": ["multi_prefix"],
                }
            )
    return flagged


__all__ = [
    "DEFAULT_INACTIVITY_GAP_MS",
    "classify_origin",
    "count_repeat_visitors",
    "count_visitors",
    "detect_vpn_geo_jumps",
    "filter_bots",
    "find_common_paths",
    "high_intent_sessions",
    "rank_pages_by_attention",
    "rank_referrers",
    "read_events",
    "reconstruct_visitor_timeline",
    "sessionize",
    "top_entry_pages",
    "top_exit_pages",
]
