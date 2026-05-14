"""Sync NDJSON analytics events into the per-domain MOS summary datum.

For each known domain, glob ``<webapps>/clients/<domain>/analytics/events/*.ndjson``,
aggregate counts + capture the 20 most recent events, write to MOS via
:class:`MosDatumAnalyticsSummaryAdapter`.

Run periodically (cron / systemd timer). Replaces the per-request
filesystem glob in ``portal_fnd_csm_runtime._build_analytics_extension_payload``.

Usage::

    python -m MyCiteV2.scripts.sync_fnd_analytics_summary \
        --webapps-root /srv/webapps \
        --domains trappfamilyfarm.com cvccboard.org \
        [--window-months 3] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.fnd_analytics_summary import (
    MAX_RECENT_EVENTS,
    MosDatumAnalyticsSummaryAdapter,
)


DEFAULT_WINDOW_MONTHS = 3


def _aggregate_for_domain(
    *, webapps_root: Path, domain: str, window_months: int
) -> tuple[dict[str, int], list[dict[str, str]]]:
    counts = {"page_view": 0, "form_submit": 0, "ops_probe": 0, "other": 0}
    recent: list[dict[str, str]] = []
    events_dir = webapps_root / "clients" / domain / "analytics" / "events"
    if not events_dir.exists() or not events_dir.is_dir():
        return counts, recent
    for ndjson_path in sorted(events_dir.glob("*.ndjson"), reverse=True)[:window_months]:
        try:
            for line in ndjson_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = str(event.get("event_type") or "").strip()
                bucket = etype if etype in {"page_view", "form_submit", "ops_probe"} else "other"
                counts[bucket] = counts.get(bucket, 0) + 1
                if len(recent) < MAX_RECENT_EVENTS:
                    recent.append({
                        "event_type": etype,
                        "path": str(event.get("path") or ""),
                        "timestamp": str(event.get("timestamp") or ""),
                    })
        except Exception:
            continue
    return counts, recent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webapps-root", type=Path, default=Path("/srv/webapps"))
    parser.add_argument(
        "--authority-db",
        type=Path,
        default=Path("/srv/mycite-state/instances/fnd/private/mos_authority.sqlite3"),
    )
    parser.add_argument("--tenant-id", default="fnd")
    parser.add_argument("--msn-id", default="3-2-3-17-77-1-6-4-1-4")
    parser.add_argument("--window-months", type=int, default=DEFAULT_WINDOW_MONTHS)
    parser.add_argument(
        "--domains",
        nargs="*",
        help="Explicit domain list; if absent, discovers from webapps/clients/*/analytics/events",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.domains:
        domains = list(args.domains)
    else:
        domains = sorted(
            p.name
            for p in (args.webapps_root / "clients").iterdir()
            if p.is_dir() and (p / "analytics" / "events").exists()
        ) if (args.webapps_root / "clients").exists() else []

    print(f"Syncing analytics summaries for {len(domains)} domains (window={args.window_months} months)")
    adapter = MosDatumAnalyticsSummaryAdapter(
        authority_db_file=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
    )
    for domain in domains:
        counts, recent = _aggregate_for_domain(
            webapps_root=args.webapps_root,
            domain=domain,
            window_months=args.window_months,
        )
        total = sum(counts.values())
        print(f"  {domain}: events={total} recent_captured={len(recent)} counts={counts}")
        if args.dry_run:
            continue
        adapter.save_summary(
            domain=domain,
            window_months=args.window_months,
            counts=counts,
            recent_events=recent,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
