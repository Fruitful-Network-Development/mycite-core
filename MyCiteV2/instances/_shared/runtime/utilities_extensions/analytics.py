"""ext_analytics — page-view + event aggregates from webapps NDJSON.

Prefers the pre-aggregated MOS summary datum
(``fnd_analytics_summary_<domain_token>``) when present, falling back
to the live NDJSON glob otherwise. The summary datum is refreshed by
``MyCiteV2.scripts.sync_fnd_analytics_summary`` (run periodically).

Phase 10: analytics has no operator-editable configuration; the events
directory is observed only. The payload surfaces a small
``data_source`` hint so the client can show operators where the numbers
come from.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._shared import _as_text

_ANALYTICS_EVENT_WINDOW_MONTHS = 3


def _build_analytics_extension_payload(
    domain: str,
    webapps_root: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    data_source: dict[str, str] = {
        "label": "Data source",
        "summary": "Read-only operational events. Configure analytics ingestion at the webapps layer.",
        "events_dir": "",
        "kind": "",
    }
    if not domain or webapps_root is None:
        return {"domain": domain, "summary": {}, "recent_events": [], "data_source": data_source}
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
                return {
                    "domain": domain,
                    "summary": cached.get("summary", {}),
                    "recent_events": cached.get("recent_events", []),
                    "source": "mos_datum",
                    "computed_at": cached.get("computed_at", ""),
                    "data_source": data_source,
                }
        except Exception:
            pass
    events_dir = Path(webapps_root) / "clients" / domain / "analytics" / "events"
    counts: dict[str, int] = {"page_view": 0, "form_submit": 0, "ops_probe": 0, "other": 0}
    recent: list[dict[str, Any]] = []
    if events_dir.exists() and events_dir.is_dir():
        for ndjson_path in sorted(events_dir.glob("*.ndjson"), reverse=True)[:_ANALYTICS_EVENT_WINDOW_MONTHS]:
            try:
                for line in Path(ndjson_path).read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        etype = _as_text(event.get("event_type"))
                        counts[etype if etype in counts else "other"] += 1
                        if len(recent) < 20:
                            recent.append({
                                "event_type": etype,
                                "path": _as_text(event.get("path")),
                                "timestamp": _as_text(event.get("timestamp") or event.get("received_at")),
                            })
                    except Exception:
                        pass
            except Exception:
                pass
    data_source["events_dir"] = str(events_dir)
    data_source["kind"] = "webapps_ndjson"
    return {
        "domain": domain,
        "summary": counts,
        "recent_events": recent,
        "events_dir_present": events_dir.exists(),
        "data_source": data_source,
    }


def _render_ext_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_analytics_extension_payload(
        domain=_as_text(ctx.get("domain")),
        webapps_root=ctx.get("webapps_root"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = ["_build_analytics_extension_payload", "_render_ext_analytics"]
