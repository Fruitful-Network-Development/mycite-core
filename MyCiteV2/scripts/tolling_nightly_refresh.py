#!/usr/bin/env python3
"""tolling_nightly_refresh — operator-side cron job.

POSTs ``/__fnd/tolling/refresh?period=<YYYY-MM>`` once. The portal route
rebuilds the operator ledger from live Cost Explorer + nginx logs, then
derives every grantee's invoice from the ledger × billing-rules so the
per-client dashboards (read via ``/__fnd/tolling/snapshot``) serve fresh
numbers without on-page-load CE calls.

One HTTP call replaces the previous per-grantee fan-out: the new
``refresh_all`` handles every known grantee from a single ledger pass.

Default cadence is once-per-day at 04:15 UTC (see the systemd timer).
The script is safe to run more often — refresh is idempotent.

Exit codes: 0 on success, 1 if the portal returned an error, 2 if the
portal is unreachable.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime

DEFAULT_PORTAL_URL = "http://127.0.0.1:6101"
DEFAULT_TIMEOUT = 300  # seconds — one ledger pass covers all grantees


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
    args = parser.parse_args(argv)

    period = args.period or datetime.now(UTC).strftime("%Y-%m")
    url = f"{args.portal.rstrip('/')}/__fnd/tolling/refresh?period={period}"
    try:
        status, body = _post(url, args.timeout)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  UNREACHABLE  {exc}", file=sys.stderr)
        return 2

    if status != 200 or not body.get("ok"):
        print(f"  FAIL  status={status} err={body.get('error')}", file=sys.stderr)
        return 1

    changed = body.get("invoices_changed") or {}
    print(f"  ok  period={period} lines={body.get('line_item_count')} "
          f"grantees={len(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
