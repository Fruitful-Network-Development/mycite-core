"""ext_analytics — page-view + event aggregates + derived insights.

Insights derive on demand from the canonical monthly analytics *leaflet*
(``<YYYY-MM>-00.record-analytics.<entity>-website.<month>_analytics.yaml`` under
``clients/_shared/site-core/analytics``) via the pure functions in
``MyCiteV2.packages.core.analytics.derivations``. The leaflet replaced the raw
NDJSON log — it is the single store the dashboard reads too, so the operator
extension and the grantee dashboard never diverge. The operator sees:

  * Summary counts (humans-only + bots-only)
  * Visitor count + repeat-visitor count
  * High-intent session count
  * Top referrers (with sessions, unique visitors, avg active time)
  * Top entry / exit pages
  * Common page-path sequences

The read is bounded to the current + previous month's leaflet to keep
per-request latency tight.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ._shared import _as_text


def _current_year_months(n: int = 2) -> list[str]:
    """Last ``n`` calendar months as YYYY-MM tokens, most-recent first
    reversed — i.e. ordered chronologically so chronological reads
    naturally process older events first.
    """
    today = datetime.now(UTC)
    months: list[str] = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))


def _refresh_action(domain: str) -> dict[str, Any]:
    return {
        "label": "Refresh summary",
        "route": "/__fnd/analytics/refresh",
        "schema": "mycite.v2.analytics.refresh.request.v1",
        "payload": {"domain": domain},
        "variant": "primary",
    }


def _build_analytics_extension_payload(
    domain: str,
    private_dir: str | Path | None = None,
    webapps_root: str | Path | None = None,
) -> dict[str, Any]:
    from MyCiteV2.packages.adapters.filesystem import (
        AnalyticsLeafletStore,
        entity_for_domain,
    )
    from MyCiteV2.packages.core.analytics import derivations
    from MyCiteV2.packages.core.analytics import leaflet_model as lm

    data_source: dict[str, str] = {
        "label": "Data source",
        "summary": "Monthly analytics leaflet (site-core); insights derived on demand.",
        "events_dir": "",
        "kind": "",
    }
    if not domain or private_dir is None:
        return {
            "domain": domain,
            "summary": {},
            "recent_events": [],
            "top_paths": [],
            "data_source": data_source,
            "notice": "No domain selected.",
        }

    store = AnalyticsLeafletStore(private_dir=private_dir, webapps_root=webapps_root)
    entity = entity_for_domain(domain)
    data_source["events_dir"] = str(store.analytics_dir)

    # Bounded to the last 2 monthly leaflets so the read stays cheap.
    events: list[dict[str, Any]] = []
    for leaflet in store.read_range(entity, _current_year_months(n=2)):
        events.extend(lm.flatten_events(leaflet))
    if not events:
        data_source["kind"] = "pending"
        return {
            "domain": domain,
            "summary": {},
            "recent_events": [],
            "top_paths": [],
            "data_source": data_source,
            "notice": (
                "No analytics events captured yet for this domain. Visit "
                "the public site to seed the first events."
            ),
            "refresh_action": _refresh_action(domain),
        }

    data_source["kind"] = "leaflet"
    data_source["computed_at"] = datetime.now(UTC).isoformat()
    data_source["event_count"] = str(len(events))

    humans, bots = derivations.filter_bots(events)
    sessions = derivations.sessionize(humans)

    # 4-bucket summary (humans only) — matches the legacy shape so
    # the JS card's "Event totals" table keeps rendering.
    summary_counts: Counter[str] = Counter()
    for event in humans:
        et = _as_text(event.get("event_type"))
        if et in {"page_view", "form_submit", "ops_probe"}:
            summary_counts[et] += 1
        else:
            summary_counts["other"] += 1

    recent_events = [
        {
            "event_type": _as_text(e.get("event_type")),
            "path": _as_text(e.get("page_path") or e.get("path")) or "—",
            "timestamp": _as_text(e.get("occurred_at_utc") or e.get("timestamp")),
        }
        for e in humans[-20:]
    ]
    recent_events.reverse()

    top_paths = derivations.rank_pages_by_attention(humans, top_k=10)
    top_referrers = derivations.rank_referrers(humans, top_k=10)
    top_entry_pages = derivations.top_entry_pages(sessions, top_k=10)
    top_exit_pages_ = derivations.top_exit_pages(sessions, top_k=10)
    common_paths = derivations.find_common_paths(humans, min_length=2, top_k=10)
    common_paths_rows = [
        {"path": " → ".join(row["path"]), "count": row["count"]}
        for row in common_paths
    ]
    visitor_count = derivations.count_visitors(humans, include_bots=False)
    repeat_visitor_count = derivations.count_repeat_visitors(sessions, min_sessions=2)
    high_intent_count = len(derivations.high_intent_sessions(sessions))
    vpn_flags = derivations.detect_vpn_geo_jumps(humans)

    # Schema-v3 / JSON Analytics Log Vision additions.
    abandoned = derivations.abandoned_intent_sessions(sessions)
    dead_ends = derivations.dead_end_pages(sessions)
    assists = derivations.conversion_assisting_pages(humans)
    origin_distribution = derivations.traffic_origin_classification(humans)

    # Top-10 visitor summaries by total active time. Built one visitor
    # at a time over the de-duplicated set; cheaper than O(visitors^2)
    # because each derivation pass is linear over the event list.
    visitor_tokens: list[str] = []
    seen_tokens: set[str] = set()
    for ev in humans:
        token = ev.get("visitor_cookie_id_hash") or ""
        if token and token not in seen_tokens:
            seen_tokens.add(token)
            visitor_tokens.append(token)
    visitor_summaries = [
        derivations.visitor_summary(humans, vt) for vt in visitor_tokens
    ]
    visitor_summaries.sort(
        key=lambda v: v.get("total_active_time_ms") or 0, reverse=True
    )
    visitor_summary_top10 = visitor_summaries[:10]

    # Interest profile rolled up across all visitors: union the
    # per-visitor category counters into one site-wide histogram.
    interest_counts: Counter = Counter()
    interest_total_views = 0
    for vt in visitor_tokens:
        prof = derivations.visitor_interest_profile(humans, vt)
        for cat, info in (prof.get("categories") or {}).items():
            interest_counts[cat] += info.get("hits", 0)
        interest_total_views += prof.get("total_page_views", 0)
    interest_profile_categories = (
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

    # Quality-flags triage histogram over the whole sample.
    quality_flag_counts: Counter = Counter()
    for ev in events:
        for token in ev.get("quality_flags") or []:
            quality_flag_counts[token] += 1
    debugging_triage_buckets = [
        {"flag": flag, "count": count}
        for flag, count in quality_flag_counts.most_common()
    ]

    # Bot separation: counts split by classifier outcome.
    bot_class_counts: Counter = Counter()
    for ev in bots:
        bot_class_counts[ev.get("bot_class") or "unclassified"] += 1
    bot_separation = {
        "human_events": len(humans),
        "bot_events": len(bots),
        "bot_class_breakdown": [
            {"bot_class": k, "count": v}
            for k, v in bot_class_counts.most_common()
        ],
    }

    return {
        "domain": domain,
        "summary": dict(summary_counts),
        "recent_events": recent_events,
        "top_paths": [
            {"path": row["page_path"], "count": row["view_count"]}
            for row in top_paths
        ],
        # Phase 18c additions — surfaced as separate tables in the
        # extension card via the JS renderer below.
        "visitor_count": visitor_count,
        "repeat_visitor_count": repeat_visitor_count,
        "high_intent_count": high_intent_count,
        "bot_event_count": len(bots),
        "vpn_geo_jump_count": len(vpn_flags),
        "session_count": len(sessions),
        "top_referrers": top_referrers,
        "top_entry_pages": top_entry_pages,
        "top_exit_pages": top_exit_pages_,
        "common_paths": common_paths_rows,
        # Schema-v3 / JSON Analytics Log Vision additions.
        "visitor_summary_top10": visitor_summary_top10,
        "interest_profile_categories": interest_profile_categories,
        "abandoned_intent_sessions": {
            "count": len(abandoned),
            "sample": abandoned[:10],
        },
        "dead_end_pages": dead_ends,
        "conversion_assisting_pages": assists,
        "origin_type_distribution": origin_distribution,
        "bot_separation": bot_separation,
        "debugging_triage_buckets": debugging_triage_buckets,
        "source": "leaflet",
        "data_source": data_source,
        "refresh_action": _refresh_action(domain),
    }


def _render_ext_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    from ._global import build_overall_roster, is_global

    if is_global(ctx):
        return build_overall_roster(
            ctx,
            extension_label="Analytics",
            summarize=lambda g: f"{len(g.get('domains') or [])} domain(s)",
        )
    return _build_analytics_extension_payload(
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        webapps_root=ctx.get("webapps_root"),
    )


__all__ = ["_build_analytics_extension_payload", "_render_ext_analytics"]
