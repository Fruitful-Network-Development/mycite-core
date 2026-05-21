#!/usr/bin/env python3
"""tolling_nightly_refresh — operator-side cron job.

Iterates every grantee profile under fnd-csm and POSTs
``/__fnd/tolling/refresh`` for the current calendar month. The portal
route recomputes from live Cost Explorer + bandwidth logs and persists
to ``tolling.<sponsor>.<msn>.json`` so the dashboard's Tolling tab
serves fresh per-grantee numbers without on-page-load CE calls.

Default cadence is once-per-day at 04:15 UTC (see the systemd timer).
The script is safe to run more often — refresh is idempotent.

Exit codes: 0 on full success, 1 if any grantee's refresh failed, 2
if the portal is unreachable or grantee directory is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (  # noqa: E402
    load_grantee_directory,
)

DEFAULT_PORTAL_URL = "http://127.0.0.1:6101"
DEFAULT_TIMEOUT = 180  # seconds — Cost Explorer + nginx-log walk per grantee


def _post(url: str, timeout: int) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8") or "{}")
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8") or "{}")
        except (OSError, ValueError):
            body = {"error": "non_json_response"}
        return e.code, body


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portal", default=DEFAULT_PORTAL_URL)
    parser.add_argument("--period", default="",
                        help="YYYY-MM (default: current UTC month).")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--grantee", action="append", default=[],
                        help="Restrict to one or more msn_ids "
                             "(may repeat). Defaults to all grantees.")
    args = parser.parse_args(argv)

    period = args.period or datetime.now(UTC).strftime("%Y-%m")
    profiles = load_grantee_directory()
    if not profiles:
        print(f"no grantee profiles under fnd-csm root", file=sys.stderr)
        return 2

    selected = profiles
    if args.grantee:
        wanted = {g for g in args.grantee}
        selected = [p for p in profiles if str(p.get("msn_id", "")) in wanted]
        if not selected:
            print(f"no matching grantee msn_ids in {args.grantee!r}", file=sys.stderr)
            return 2

    failures = 0
    for profile in selected:
        msn = str(profile.get("msn_id", "")).strip()
        if not msn:
            continue
        url = (f"{args.portal.rstrip('/')}/__fnd/tolling/refresh"
               f"?grantee={msn}&period={period}")
        try:
            status, body = _post(url, args.timeout)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  {msn}  UNREACHABLE  {exc}", file=sys.stderr)
            failures += 1
            continue
        ok = status == 200 and body.get("ok")
        marker = "ok" if ok else "FAIL"
        if ok:
            row = body.get("row") or {}
            print(f"  {msn}  ok  subtotal={row.get('subtotal')} "
                  f"currency={row.get('currency')} "
                  f"domains={row.get('domains_count')}")
        else:
            print(f"  {msn}  {marker}  status={status} err={body.get('error')}",
                  file=sys.stderr)
            failures += 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
