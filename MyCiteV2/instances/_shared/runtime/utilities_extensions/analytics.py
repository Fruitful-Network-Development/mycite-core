"""ext_analytics — page-view + event aggregates.

Prefers the pre-aggregated MOS summary datum
(``fnd_analytics_summary_<domain_token>``) refreshed by
``MyCiteV2.scripts.sync_fnd_analytics_summary``.

Phase 14c: the legacy fallback that globbed up to 3 months of webapps
NDJSON event files + json.loads-ed every line in the request critical
path is REMOVED. That fallback was the dominant latency driver on
``/portal/utilities/extensions``. When the MOS summary datum is absent,
the renderer now returns a ``pending`` placeholder pointing operators
at the refresh endpoint. The expensive aggregation only happens in
the offline sync job (or via the manually-triggered refresh route).

Phase 14d.4: the payload now carries a ``refresh_action`` button (row
action shape) that POSTs to ``/__fnd/analytics/refresh`` and triggers
the sync for the current domain on demand. ``top_paths`` is also
derived from ``recent_events`` so operators see the most-visited
pages without leaving the extension card.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ._shared import _as_text


def _top_paths(recent_events: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for event in recent_events or []:
        path = _as_text(event.get("path")) if isinstance(event, dict) else ""
        if path and path != "—":
            counter[path] += 1
    return [{"path": path, "count": count} for path, count in counter.most_common(limit)]


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
    webapps_root: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    data_source: dict[str, str] = {
        "label": "Data source",
        "summary": "Pre-aggregated MOS summary datum. Refresh via the analytics sync job.",
        "events_dir": "",
        "kind": "",
    }
    if not domain or webapps_root is None:
        return {
            "domain": domain,
            "summary": {},
            "recent_events": [],
            "top_paths": [],
            "data_source": data_source,
            "notice": "No domain selected.",
        }
    if authority_db_file is not None:
        try:
            from MyCiteV2.packages.adapters.sql.fnd_analytics_summary import (
                MosDatumAnalyticsSummaryAdapter,
            )

            adapter = MosDatumAnalyticsSummaryAdapter(
                authority_db_file=authority_db_file,
                tenant_id=portal_instance_id or "fnd",
            )
            cached = adapter.load_summary(domain=domain)
            if cached is not None:
                data_source["kind"] = "mos_datum"
                events_dir = Path(webapps_root) / "clients" / domain / "analytics" / "events"
                data_source["events_dir"] = str(events_dir)
                computed_at = _as_text(cached.get("computed_at"))
                if computed_at:
                    data_source["computed_at"] = computed_at
                recent_events = cached.get("recent_events", []) or []
                return {
                    "domain": domain,
                    "summary": cached.get("summary", {}),
                    "recent_events": recent_events,
                    "top_paths": _top_paths(recent_events),
                    "source": "mos_datum",
                    "computed_at": computed_at,
                    "data_source": data_source,
                    "refresh_action": _refresh_action(domain),
                }
        except Exception:
            pass
    # Pending state: no MOS summary datum yet for this domain. Don't
    # block the request walking the NDJSON tree.
    events_dir = Path(webapps_root) / "clients" / domain / "analytics" / "events"
    data_source["events_dir"] = str(events_dir)
    data_source["kind"] = "pending"
    return {
        "domain": domain,
        "summary": {},
        "recent_events": [],
        "top_paths": [],
        "data_source": data_source,
        "notice": (
            "Analytics summary not yet computed for this domain. Use the "
            "Refresh button to trigger the sync now, or wait for the next "
            "scheduled sync_fnd_analytics_summary run."
        ),
        "refresh_action": _refresh_action(domain),
    }


def _render_ext_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_analytics_extension_payload(
        domain=_as_text(ctx.get("domain")),
        webapps_root=ctx.get("webapps_root"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = ["_build_analytics_extension_payload", "_render_ext_analytics"]
