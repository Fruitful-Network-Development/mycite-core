"""Sync NDJSON analytics events into the per-domain MOS summary datum.

For each known domain, find the canonical per-grantee NDJSON files via
:class:`AnalyticsEventPathResolver`, aggregate counts + capture the 20
most recent events, write to MOS via
:class:`MosDatumAnalyticsSummaryAdapter`.

Run periodically (cron / systemd timer). Replaces the per-request
filesystem glob in ``portal_fnd_csm_runtime._build_analytics_extension_payload``.

Usage::

    python -m MyCiteV2.scripts.sync_fnd_analytics_summary \\
        --analytics-root /srv/repo/mycite-core/deployed/fnd/private/utilities/tools/analytics \\
        --domains trappfamilyfarm.com cvccboard.org \\
        [--window-months 3] [--dry-run]

The legacy ``--webapps-root`` flag is still accepted for back-compat
testing against the pre-2026-05-16 layout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import AnalyticsEventPathResolver
from MyCiteV2.packages.adapters.sql.fnd_analytics_summary import (
    MAX_RECENT_EVENTS,
    MosDatumAnalyticsSummaryAdapter,
)

DEFAULT_WINDOW_MONTHS = 3
DEFAULT_ANALYTICS_ROOT = Path(
    "/srv/repo/mycite-core/deployed/fnd/private/utilities/tools/analytics"
)


def _aggregate_for_domain(
    *,
    resolver: AnalyticsEventPathResolver | None = None,
    domain: str,
    window_months: int,
    # Legacy back-compat: still accept webapps_root as a positional/kw arg
    # so callers (esp. tests) that haven't switched yet keep working.
    webapps_root: Path | None = None,
) -> tuple[dict[str, int], list[dict[str, str]]]:
    if resolver is None:
        if webapps_root is not None:
            resolver = AnalyticsEventPathResolver(webapps_root=webapps_root)
        else:
            resolver = AnalyticsEventPathResolver()

    counts = {"page_view": 0, "form_submit": 0, "ops_probe": 0, "other": 0}
    recent: list[dict[str, str]] = []
    ndjson_paths = resolver.iter_domain_event_files(domain)[:window_months]
    if not ndjson_paths:
        return counts, recent
    for ndjson_path in ndjson_paths:
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
    parser.add_argument(
        "--analytics-root",
        type=Path,
        default=DEFAULT_ANALYTICS_ROOT,
        help="Per-grantee analytics root (canonical mode). Default: %(default)s",
    )
    parser.add_argument(
        "--webapps-root",
        type=Path,
        default=None,
        help="Legacy webapps root (pre-2026-05-16 layout). If set, overrides --analytics-root.",
    )
    parser.add_argument(
        "--authority-db",
        type=Path,
        default=Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3"),
    )
    parser.add_argument("--tenant-id", default="fnd")
    parser.add_argument("--msn-id", default="3-2-3-17-77-1-6-4-1-4")
    parser.add_argument("--window-months", type=int, default=DEFAULT_WINDOW_MONTHS)
    parser.add_argument(
        "--domains",
        nargs="*",
        help="Explicit domain list; if absent, discovers from the resolver.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.webapps_root is not None:
        resolver = AnalyticsEventPathResolver(webapps_root=args.webapps_root)
    else:
        resolver = AnalyticsEventPathResolver(analytics_root=args.analytics_root)

    if args.domains:
        domains = list(args.domains)
    else:
        domains = resolver.discover_domains()

    print(
        f"Syncing analytics summaries for {len(domains)} domains "
        f"(window={args.window_months} months, root={resolver.analytics_root})"
    )
    adapter = MosDatumAnalyticsSummaryAdapter(
        authority_db_file=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
    )
    for domain in domains:
        counts, recent = _aggregate_for_domain(
            resolver=resolver,
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
