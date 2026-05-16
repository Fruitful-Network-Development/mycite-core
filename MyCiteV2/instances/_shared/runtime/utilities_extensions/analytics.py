"""ext_analytics — page-view + event aggregates + derived insights.

Phase 18c rewrites the renderer so insights derive on demand from
the canonical raw NDJSON log (Phase 18a) via the pure functions in
``MyCiteV2.packages.core.analytics.derivations``. The operator sees:

  * Summary counts (humans-only + bots-only)
  * Visitor count + repeat-visitor count
  * High-intent session count
  * Top referrers (with sessions, unique visitors, avg active time)
  * Top entry / exit pages
  * Common page-path sequences

The read is bounded to the current + previous month's NDJSON files
to keep per-request latency tight. The legacy MOS summary datum
is retained as a fast-path cache for the 4-bucket count + recent
events (so old refresh-button flows keep working).
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
    analytics_root: str | Path | None = None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
    webapps_root: str | Path | None = None,  # legacy fallback only
) -> dict[str, Any]:
    from MyCiteV2.packages.adapters.filesystem import AnalyticsEventPathResolver

    data_source: dict[str, str] = {
        "label": "Data source",
        "summary": "Raw events read from the canonical NDJSON log; insights derived on demand.",
        "events_dir": "",
        "kind": "",
    }
    if not domain:
        return {
            "domain": domain,
            "summary": {},
            "recent_events": [],
            "top_paths": [],
            "data_source": data_source,
            "notice": "No domain selected.",
        }

    if analytics_root is not None:
        resolver = AnalyticsEventPathResolver(analytics_root=analytics_root)
    elif webapps_root is not None:
        resolver = AnalyticsEventPathResolver(webapps_root=webapps_root)
    else:
        resolver = AnalyticsEventPathResolver()
    data_source["events_dir"] = str(resolver.analytics_root)

    # Phase 18c: on-demand derivation from the raw NDJSON. Bounded
    # to the last 2 month files so the read stays cheap (<200ms for
    # any realistic event volume).
    from MyCiteV2.packages.core.analytics import derivations

    year_months = _current_year_months(n=2)
    events = list(
        derivations.read_events(
            domain=domain, year_months=year_months, resolver=resolver
        )
    )
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

    data_source["kind"] = "raw_events"
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

    # Suppress the unused authority_db / instance_id args for now —
    # the on-demand derivation path doesn't need MOS data. The
    # caller's existing context still passes them through.
    del authority_db_file, portal_instance_id

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
        "source": "raw_events",
        "data_source": data_source,
        "refresh_action": _refresh_action(domain),
    }


def _render_ext_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    # ctx may supply analytics_root directly, or a private_dir from which
    # we derive it, or the legacy webapps_root as a last resort.
    analytics_root = ctx.get("analytics_root")
    if analytics_root is None and ctx.get("private_dir") is not None:
        analytics_root = Path(ctx["private_dir"]) / "utilities" / "tools" / "analytics"
    return _build_analytics_extension_payload(
        domain=_as_text(ctx.get("domain")),
        analytics_root=analytics_root,
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
        webapps_root=ctx.get("webapps_root"),
    )


__all__ = ["_build_analytics_extension_payload", "_render_ext_analytics"]
