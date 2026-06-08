#!/usr/bin/env python3
"""One-time migration: raw NDJSON event logs → monthly analytics leaflets.

The analytics store cut over from a per-domain append-only NDJSON log to the
monthly site-core *leaflet* (``visitors → sessions → events``). This script
reads every existing
``<analytics_root>/analytics.<domain>.events.<YYYY-MM>.ndjson`` and rebuilds the
equivalent leaflet at
``<webapps_root>/clients/_shared/site-core/analytics/<YYYY-MM>-00.record-analytics.<entity>-website.<month>_analytics.yaml``.

It is **idempotent** — each run rebuilds a month's leaflet from scratch from the
NDJSON, so re-running converges. Events are grouped by their ``occurred_at_utc``
month (not the filename) and by owning *entity* (CVCC owns two domains → one
leaflet). Visitors seen in a prior month are flagged ``returning_from_prior_month``.

Usage:
    # dry run (default) — report what would be written, touch nothing
    python -m MyCiteV2.scripts.migrate_ndjson_to_analytics_leaflet

    # write the leaflets
    python -m MyCiteV2.scripts.migrate_ndjson_to_analytics_leaflet --apply

    # write, then move the consumed NDJSON into a timestamped backup dir
    python -m MyCiteV2.scripts.migrate_ndjson_to_analytics_leaflet --apply --retire-ndjson

    # custom roots (tests / a copy of live data)
    python -m MyCiteV2.scripts.migrate_ndjson_to_analytics_leaflet \
        --analytics-root /tmp/copy/analytics --webapps-root /tmp/copy/webapps --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import AnalyticsLeafletStore, entity_for_domain
from MyCiteV2.packages.adapters.filesystem.analytics_leaflet import period_of
from MyCiteV2.packages.core.analytics import leaflet_model as lm

DEFAULT_ANALYTICS_ROOT = Path(
    "/srv/webapps/mycite/fnd/private/utilities/tools/analytics"
)
DEFAULT_WEBAPPS_ROOT = Path("/srv/webapps")

_NDJSON_RE = re.compile(r"^analytics\.(?P<domain>.+)\.events\.(?P<ym>\d{4}-\d{2})\.ndjson$")


def _iter_ndjson(analytics_root: Path):
    for path in sorted(analytics_root.glob("analytics.*.events.*.ndjson")):
        m = _NDJSON_RE.match(path.name)
        if not m:
            continue
        yield path, m.group("domain"), m.group("ym")


def _read_events(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows


def build_leaflets(analytics_root: Path) -> dict[tuple[str, str], dict]:
    """Return ``{(entity, period): month_dict}`` built from every NDJSON file.

    Events are bucketed by entity + their own occurred-month, so a row mis-filed
    in an adjacent month's file still lands in the right leaflet.
    """
    # (entity, period) -> {"domain": first_domain, "events": [...] }
    buckets: dict[tuple[str, str], dict] = {}
    for path, domain, file_ym in _iter_ndjson(analytics_root):
        entity = entity_for_domain(domain)
        for ev in _read_events(path):
            period = period_of(ev.get("occurred_at_utc") or ev.get("received_at_utc") or "") or file_ym
            key = (entity, period)
            slot = buckets.setdefault(key, {"domain": domain, "events": []})
            slot["events"].append(ev)

    months: dict[tuple[str, str], dict] = {}
    for (entity, period), slot in buckets.items():
        month = lm.empty_month(
            entity=entity, domain=slot["domain"], period=period, generated_at=""
        )
        for ev in sorted(slot["events"], key=lambda e: e.get("occurred_at_utc") or ""):
            lm.merge_event(month, ev)
        months[(entity, period)] = month

    # Cross-month lineage: for each entity, walk periods in order and flag
    # visitors that also appear in the immediately-prior built month.
    by_entity: dict[str, list[str]] = {}
    for (entity, period) in months:
        by_entity.setdefault(entity, []).append(period)
    for entity, periods in by_entity.items():
        periods.sort()
        for i, period in enumerate(periods):
            prior = months.get((entity, periods[i - 1])) if i > 0 else None
            lm.link_prior_month(months[(entity, period)], prior)

    return months


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--analytics-root", type=Path, default=DEFAULT_ANALYTICS_ROOT)
    parser.add_argument("--webapps-root", type=Path, default=DEFAULT_WEBAPPS_ROOT)
    parser.add_argument("--private-dir", type=Path, default=None,
                        help="Override; defaults to <webapps-root>/mycite/fnd/private.")
    parser.add_argument("--apply", action="store_true", help="Write leaflets (default: dry run).")
    parser.add_argument("--retire-ndjson", action="store_true",
                        help="After --apply, MOVE consumed NDJSON into a .pre-leaflet backup dir.")
    args = parser.parse_args()

    analytics_root = args.analytics_root
    if not analytics_root.is_dir():
        print(f"[migrate] analytics root not found: {analytics_root}", file=sys.stderr)
        return 2

    private_dir = args.private_dir or (args.webapps_root / "mycite" / "fnd" / "private")
    store = AnalyticsLeafletStore(private_dir=private_dir, webapps_root=args.webapps_root)

    months = build_leaflets(analytics_root)
    generated_at = datetime.now(UTC).isoformat()

    total_visitors = total_events = 0
    print(f"[migrate] {'APPLY' if args.apply else 'DRY-RUN'} → {store.analytics_dir}")
    for (entity, period) in sorted(months):
        month = months[(entity, period)]
        lm.finalize_month(month, generated_at=generated_at)
        n_visitors = len(month["visitors"])
        n_events = sum(len(s["events"]) for v in month["visitors"] for s in v["sessions"])
        total_visitors += n_visitors
        total_events += n_events
        target = store.leaflet_path(entity, period)
        print(f"  {entity:42s} {period}  visitors={n_visitors:4d} events={n_events:5d} -> {target.name}")
        if args.apply:
            store.save_month(entity, month)

    print(f"[migrate] {len(months)} leaflet(s); visitors={total_visitors} events={total_events}")

    if args.retire_ndjson:
        if not args.apply:
            print("[migrate] --retire-ndjson ignored without --apply", file=sys.stderr)
        else:
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            backup = analytics_root / f".pre-leaflet-{stamp}"
            backup.mkdir(parents=True, exist_ok=True)
            moved = 0
            for path, _domain, _ym in _iter_ndjson(analytics_root):
                path.rename(backup / path.name)
                moved += 1
            print(f"[migrate] retired {moved} NDJSON file(s) -> {backup}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
