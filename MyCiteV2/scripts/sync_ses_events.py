"""sync_ses_events — mirror S3 SES event objects into a MOS rollup.

The Lambda `ses_event_sink` writes one normalized JSON object per
(event_type, recipient_domain) under
`s3://<EVENTS_BUCKET>/ses_events/<domain>/<YYYY-MM-DD>/<EventType>/<message-id>-<ulid>.json`.

This script:

  1. Lists every key under each grantee domain's ses_events prefix for
     the last ``--since-days`` days (default 7, since the dashboard
     supports up to a 30-day window plus headroom for the operator).
  2. Buckets the keys by (domain, YYYY-MM-DD, event_type) and counts
     them (the object body is small enough that we don't need to read
     it — the key path is authoritative).
  3. Writes a per-domain rollup to MOS via MosDatumEmailDeliverabilityAdapter.
     Header totals + per-day rows are computed from the bucketed counts
     and the adapter dedupes by date on save.

Idempotent — running multiple times produces the same MOS state.

Usage:
  python3 -m MyCiteV2.scripts.sync_ses_events \
      --events-bucket fnd-ses-events \
      --since-days 7

Optional:
  --domain example.com   (restrict to one domain)
  --dry-run              (compute + log, do not write to MOS)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    import boto3  # type: ignore
except ImportError:  # pragma: no cover — boto3 absent on dev hosts
    boto3 = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
    load_grantee_directory,
)
from MyCiteV2.packages.adapters.sql.fnd_email_deliverability import (
    EVENT_KEYS,
    MosDatumEmailDeliverabilityAdapter,
)

_log = logging.getLogger("sync_ses_events")


# SES event type → adapter key. Reject + DeliveryDelay are intentionally
# unmapped (not displayed on the dashboard).
EVENT_TYPE_TO_KEY = {
    "Send":      "send",
    "Delivery":  "delivery",
    "Bounce":    "bounce",
    "Complaint": "complaint",
    "Open":      "open",
    "Click":     "click",
}
assert set(EVENT_TYPE_TO_KEY.values()) == set(EVENT_KEYS), (
    "EVENT_TYPE_TO_KEY values must match adapter EVENT_KEYS"
)


def _iso_days(since_days: int) -> list[str]:
    today = datetime.now(UTC).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(since_days)]


def _list_keys(s3, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            keys.append(obj["Key"])
    return keys


def _parse_key(key: str) -> tuple[str, str, str] | None:
    """Return (domain, day, event_type) parsed from the key, or None
    if the layout doesn't match what the Lambda writes."""
    # ses_events/<domain>/<YYYY-MM-DD>/<EventType>/<msg-ulid>.json
    parts = key.split("/")
    if len(parts) < 5:
        return None
    if parts[0] != "ses_events":
        return None
    return parts[1], parts[2], parts[3]


def _aggregate(keys: list[str]) -> dict[str, dict[str, dict[str, int]]]:
    """domain → day → {event_key: count}"""
    out: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {k: 0 for k in EVENT_KEYS})
    )
    for key in keys:
        parsed = _parse_key(key)
        if parsed is None:
            continue
        domain, day, event_type = parsed
        adapter_key = EVENT_TYPE_TO_KEY.get(event_type)
        if adapter_key is None:
            continue
        out[domain][day][adapter_key] += 1
    return out


def _write_rollup(
    *,
    domain: str,
    days: dict[str, dict[str, int]],
    authority_db_file: Path,
    tenant_id: str,
    msn_id: str,
    dry_run: bool,
) -> None:
    by_day = [{"date": day, **counts} for day, counts in sorted(days.items())]
    if dry_run:
        _log.info("[dry-run] %s — %d day(s), totals=%s",
                  domain, len(by_day),
                  {k: sum(d[k] for d in by_day) for k in EVENT_KEYS})
        return
    adapter = MosDatumEmailDeliverabilityAdapter(
        authority_db_file=authority_db_file,
        tenant_id=tenant_id,
        msn_id=msn_id,
    )
    adapter.save_rollup(domain=domain, by_day=by_day)
    _log.info("%s — wrote %d day(s) to MOS", domain, len(by_day))


def _grantee_for_domain(target: str, directory) -> tuple[str, str] | None:
    """(tenant_id, msn_id) for the grantee that owns ``target``."""
    for profile in directory:
        domains = [str(d).lower() for d in (profile.get("domains") or [])]
        if target.lower() in domains:
            short = str(profile.get("short_name", "")).lower()
            return (short or "fnd", str(profile.get("msn_id", "")))
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events-bucket", required=True, help="S3 bucket name")
    ap.add_argument("--events-prefix", default="ses_events",
                    help="S3 prefix under the bucket (default: ses_events)")
    ap.add_argument("--since-days", type=int, default=7,
                    help="ingest keys from the last N days (default: 7)")
    ap.add_argument("--domain", action="append", default=[],
                    help="restrict to one or more recipient domains")
    ap.add_argument("--authority-db", default=os.environ.get("MYCITE_V2_PORTAL_AUTHORITY_DB", ""),
                    help="path to mos_authority.sqlite3 (or set "
                         "$MYCITE_V2_PORTAL_AUTHORITY_DB)")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute + log, do not write to MOS")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if boto3 is None:
        _log.error("boto3 is not installed; cannot sync from S3")
        return 2

    if not args.authority_db and not args.dry_run:
        _log.error("--authority-db (or $MYCITE_V2_PORTAL_AUTHORITY_DB) required")
        return 2

    directory = load_grantee_directory()
    if not directory:
        _log.warning("no grantee profiles loaded; nothing to sync")
        return 0

    selected: list[str] = []
    if args.domain:
        selected = [d.lower() for d in args.domain]
    else:
        for profile in directory:
            for d in profile.get("domains") or []:
                selected.append(str(d).lower())

    s3 = boto3.client("s3")
    authority_db_file = Path(args.authority_db) if args.authority_db else Path("/dev/null")

    total_written = 0
    for domain in sorted(set(selected)):
        prefix = f"{args.events_prefix.strip('/')}/{domain}/"
        try:
            keys = _list_keys(s3, args.events_bucket, prefix)
        except Exception as exc:
            _log.error("%s — list failed: %s", domain, exc)
            continue
        if not keys:
            _log.info("%s — no keys under %s", domain, prefix)
            continue
        # Filter to the requested day window.
        wanted_days = set(_iso_days(args.since_days))
        agg = _aggregate(keys)
        days = agg.get(domain) or {}
        days = {d: counts for d, counts in days.items() if d in wanted_days}
        if not days:
            _log.info("%s — keys present but none in last %dd window",
                      domain, args.since_days)
            continue

        gid = _grantee_for_domain(domain, directory)
        if gid is None:
            _log.warning("%s — no grantee profile owns this domain; skipping", domain)
            continue
        tenant_id, msn_id = gid

        _write_rollup(
            domain=domain, days=days,
            authority_db_file=authority_db_file,
            tenant_id=tenant_id, msn_id=msn_id,
            dry_run=args.dry_run,
        )
        total_written += 1

    _log.info("sync complete; %d domain(s) updated", total_written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
