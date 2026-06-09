"""Shared analytics rollups — the one derivation pipeline both readers use.

The grantee dashboard's ``/__fnd/analytics/summary`` route and the operator
``ext_analytics`` extension both flatten the monthly leaflet to a flat event
list and then run the *same* derivation sequence over it. Keeping two copies of
that sequence is exactly the "two live paths" drift the codebase warns against
(they had already started to diverge), so it lives here once. Each caller layers
only its own payload shaping on top of these primitives.

Runtime/composition layer: free to import core (``derivations``), unlike the
filesystem adapters.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from MyCiteV2.packages.core.analytics import derivations


def derive_insights(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the shared derivation pipeline once over a flat event list.

    Returns the primitives both the dashboard summary and the operator
    extension assemble their payloads from. Callers add their own extras
    (the route adds pie ``widgets`` + device split; the extension adds
    entry/exit pages, common paths, vpn/geo-jump, recent events).
    """
    humans, bots = derivations.filter_bots(events)
    sessions = derivations.sessionize(humans)

    # Group humans by cookie ONCE, in first-seen order, so each per-visitor pass
    # below operates on that visitor's own (small) event list rather than
    # re-filtering the whole `humans` list — turns the old O(visitors × events)
    # rescans into a single O(events) grouping pass.
    by_cookie: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tokens: list[str] = []
    seen: set[str] = set()
    for e in humans:
        t = e.get("visitor_cookie_id_hash") or ""
        if not t:
            continue
        if t not in seen:
            seen.add(t)
            tokens.append(t)
        by_cookie[t].append(e)

    visitor_summaries = [derivations.visitor_summary(by_cookie[t], t) for t in tokens]
    visitor_summaries.sort(key=lambda v: v.get("total_active_time_ms") or 0, reverse=True)

    interest_counts: Counter = Counter()
    interest_total_views = 0
    for token in tokens:
        prof = derivations.visitor_interest_profile(by_cookie[token], token)
        for cat, info in (prof.get("categories") or {}).items():
            interest_counts[cat] += info.get("hits", 0)
        interest_total_views += prof.get("total_page_views", 0)
    interest_rows = (
        [
            {
                "category": cat,
                "hits": hits,
                "pct_of_views": round(100 * hits / interest_total_views, 2)
                if interest_total_views
                else 0.0,
            }
            for cat, hits in interest_counts.most_common()
        ]
        if interest_total_views
        else []
    )

    bot_class_counts: Counter = Counter()
    for event in bots:
        bot_class_counts[event.get("bot_class") or "unclassified"] += 1

    quality_flag_counts: Counter = Counter()
    for event in events:
        for token in event.get("quality_flags") or []:
            quality_flag_counts[token] += 1

    return {
        "humans": humans,
        "bots": bots,
        "sessions": sessions,
        "visitor_tokens": tokens,
        "visitor_summary_top10": visitor_summaries[:10],
        "interest_profile_categories": interest_rows,
        "abandoned": derivations.abandoned_intent_sessions(sessions),
        "dead_ends": derivations.dead_end_pages(sessions),
        "assists": derivations.conversion_assisting_pages(humans),
        "origin_distribution": derivations.traffic_origin_classification(humans),
        "top_paths": derivations.rank_pages_by_attention(humans, top_k=10),
        "top_referrers_by_session": derivations.rank_referrers(humans, top_k=10),
        "bot_separation": {
            "human_events": len(humans),
            "bot_events": len(bots),
            "bot_class_breakdown": [
                {"bot_class": k, "count": v} for k, v in bot_class_counts.most_common()
            ],
        },
        "quality_flag_buckets": [
            {"flag": flag, "count": count}
            for flag, count in quality_flag_counts.most_common()
        ],
    }


__all__ = ["derive_insights"]
