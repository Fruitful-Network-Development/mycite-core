"""Phase 18a — transpose legacy v1 analytics events to v2.

The pre-Phase-18 NDJSON rows carried a thin schema (event_type,
path, timestamp, session_id, title, referrer, remote_addr,
user_agent, received_at). The v2 schema adds visitor_cookie_id_hash,
ip_hash, ip_prefix, bot fields, and a clearer client/server-stamped
split. This script does the best-effort one-shot migration:

  * Walk ``/srv/webapps/clients/<domain>/analytics/events/*.ndjson``
  * Parse each line; recognise schema=mycite.analytics.event.v1
  * Map to v2 RawEvent.to_dict() shape, leaving unfilled fields
    empty / zero
  * Write the file back with the v2 rows. Old content is preserved
    in a sibling ``.legacy.ndjson`` file the first time.

Idempotent: if a ``.legacy.ndjson`` already exists, the live file
is assumed to be the v2 transposition and is left alone.

Usage::

    python -m MyCiteV2.scripts.transpose_legacy_analytics_events \
        --webapps-root /srv/webapps
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.analytics import (
    EVENT_SCHEMA,
    classify_user_agent,
    coarse_ip_prefix,
    salted_hash,
)

LEGACY_SCHEMA = "mycite.analytics.event.v1"
WEB_EVENT_SCHEMA = "mycite.v2.analytics.web_event.v1"
TRANSPOSE_SALT = "phase18a-transpose-fixed-salt"  # Stable across re-runs.


def _unix_ms_to_iso(value) -> str:
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return ""
    from datetime import UTC, datetime

    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


def _transpose_web_event(row: dict, *, site_id: str) -> dict:
    """Map a ``mycite.v2.analytics.web_event.v1`` row.

    web_event.v1 carries a nested ``payload`` dict + received_at_
    unix_ms but no explicit session_id / event_type / occurred_at.
    Treat each row as an implicit page_view; synthesise the
    session_id from the request_id so the same browser request's
    associated rows cluster.
    """
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    user_agent = str(row.get("user_agent") or "")
    is_bot, bot_class, evidence = classify_user_agent(user_agent)
    referrer_url = str(payload.get("referrer") or "")
    referrer_domain = urlparse(referrer_url).netloc.lower() if referrer_url else ""
    remote_addr = str(row.get("remote_addr") or "")
    received_at = _unix_ms_to_iso(row.get("received_at_unix_ms"))
    return {
        "schema": EVENT_SCHEMA,
        "collector_version": "transpose-phase18a/1.0",
        "event_id": f"transposed-web-{row.get('request_id', '')}",
        "received_at_utc": received_at,
        "site_id": site_id,
        "domain": str(row.get("domain") or "").lower(),
        "environment": "prod",
        "visitor_cookie_id_hash": salted_hash(
            str(row.get("request_id") or remote_addr), salt=TRANSPOSE_SALT
        ),
        "ip_hash": salted_hash(remote_addr, salt=TRANSPOSE_SALT),
        "ip_prefix": coarse_ip_prefix(remote_addr),
        "is_bot": is_bot,
        "bot_class": bot_class,
        "bot_evidence": list(evidence),
        "event_type": "page_view",
        "occurred_at_utc": received_at,
        "session_id": (f"transposed-{row.get('request_id', '')}"[:64]) or "transposed",
        "page_path": str(payload.get("path") or "/"),
        "event_name": "",
        "event_index_in_session": 0,
        "page_query_hash": "",
        "page_title": str(payload.get("title") or ""),
        "referrer_url": referrer_url,
        "referrer_domain": referrer_domain,
        "origin_type": "",
        "utm_source": "",
        "utm_medium": "",
        "utm_campaign": "",
        "utm_content": "",
        "utm_term": "",
        "previous_page_path": "",
        "time_since_previous_ms": 0,
        "active_time_ms": 0,
        "visible_time_ms": 0,
        "scroll_depth_percent": 0,
        "user_agent_raw": user_agent,
        "device_type": "",
        "browser_name": "",
        "viewport_width": int(payload.get("width") or 0),
        "viewport_height": int(payload.get("height") or 0),
        "language": "",
        "do_not_track": False,
        "properties": {},
    }


def _transpose_row(row: dict, *, site_id: str) -> dict:
    user_agent = str(row.get("user_agent") or "")
    is_bot, bot_class, evidence = classify_user_agent(user_agent)
    referrer_url = str(row.get("referrer") or "")
    referrer_domain = urlparse(referrer_url).netloc.lower() if referrer_url else ""
    remote_addr = str(row.get("remote_addr") or "")
    return {
        "schema": EVENT_SCHEMA,
        "collector_version": "transpose-phase18a/1.0",
        "event_id": f"transposed-{row.get('session_id', '')}-{row.get('timestamp', '')}",
        "received_at_utc": str(row.get("received_at") or ""),
        "site_id": site_id,
        "domain": str(row.get("domain") or "").lower(),
        "environment": "prod",
        # The legacy schema had no per-visitor cookie. The
        # session_id is the only stable identifier; use it (salted)
        # so multi-event sessions cluster correctly even if cross-
        # session visitor identity is lost.
        "visitor_cookie_id_hash": salted_hash(
            str(row.get("session_id") or ""), salt=TRANSPOSE_SALT
        ),
        "ip_hash": salted_hash(remote_addr, salt=TRANSPOSE_SALT),
        "ip_prefix": coarse_ip_prefix(remote_addr),
        "is_bot": is_bot,
        "bot_class": bot_class,
        "bot_evidence": list(evidence),
        "event_type": str(row.get("event_type") or "page_view"),
        "occurred_at_utc": str(row.get("timestamp") or ""),
        "session_id": str(row.get("session_id") or ""),
        "page_path": str(row.get("path") or "/"),
        "event_name": "",
        "event_index_in_session": 0,
        "page_query_hash": "",
        "page_title": str(row.get("title") or ""),
        "referrer_url": referrer_url,
        "referrer_domain": referrer_domain,
        "origin_type": "",
        "utm_source": "",
        "utm_medium": "",
        "utm_campaign": "",
        "utm_content": "",
        "utm_term": "",
        "previous_page_path": "",
        "time_since_previous_ms": 0,
        "active_time_ms": 0,
        "visible_time_ms": 0,
        "scroll_depth_percent": 0,
        "user_agent_raw": user_agent,
        "device_type": "",
        "browser_name": "",
        "viewport_width": 0,
        "viewport_height": 0,
        "language": "",
        "do_not_track": False,
        "properties": {},
    }


def _transpose_file(path: Path, *, site_id: str, dry_run: bool = False) -> tuple[int, int]:
    """Return (lines_in, lines_out). Skips already-transposed files
    (recognised by an existing .legacy.ndjson sibling)."""
    legacy_path = path.with_suffix(".legacy.ndjson")
    if legacy_path.exists():
        return 0, 0  # already transposed
    raw = path.read_text(encoding="utf-8").splitlines()
    out_rows: list[str] = []
    seen = 0
    for line in raw:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        seen += 1
        schema = row.get("schema")
        if schema == EVENT_SCHEMA:
            # Already in v2 shape — keep as-is.
            out_rows.append(line)
            continue
        if schema == WEB_EVENT_SCHEMA:
            out_rows.append(
                json.dumps(_transpose_web_event(row, site_id=site_id), separators=(",", ":"))
            )
            continue
        if schema and schema != LEGACY_SCHEMA:
            # Unknown schema — skip but log.
            print(f"  skip unknown schema: {schema!r}")
            continue
        out_rows.append(json.dumps(_transpose_row(row, site_id=site_id), separators=(",", ":")))
    if dry_run:
        return seen, len(out_rows)
    path.rename(legacy_path)
    path.write_text("\n".join(out_rows) + ("\n" if out_rows else ""), encoding="utf-8")
    return seen, len(out_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webapps-root", type=Path, default=Path("/srv/webapps"))
    parser.add_argument(
        "--site-id",
        default="fnd",
        help="Site identifier to stamp on transposed rows (default: fnd)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    clients_root = args.webapps_root / "clients"
    if not clients_root.exists():
        print(f"clients root not found: {clients_root}")
        return 1
    print(f"Transposing legacy analytics events under {clients_root}")
    total_in = 0
    total_out = 0
    files_touched = 0
    for domain_dir in sorted(clients_root.iterdir()):
        events_dir = domain_dir / "analytics" / "events"
        if not events_dir.exists():
            continue
        for path in sorted(events_dir.glob("*.ndjson")):
            if path.name.endswith(".legacy.ndjson"):
                continue
            seen, out = _transpose_file(path, site_id=args.site_id, dry_run=args.dry_run)
            if seen == 0 and out == 0:
                continue
            print(f"  {path.relative_to(clients_root)}: in={seen} out={out}")
            total_in += seen
            total_out += out
            files_touched += 1
    print(f"Done. files={files_touched} in={total_in} out={total_out} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
