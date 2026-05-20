"""ext_tolling — per-grantee cost itemization (Tolling extension).

Surfaces three things on top of the peripherals.aws Cost Explorer + tag
infrastructure:

  1. ``get_costs_by_grantee`` from `peripherals.aws.cloud_adapter` —
     direct AWS spend for SES, Route53, S3, etc. filtered by
     `Tag:msn_id`. Already lives on the peripheral; this module is the
     consuming surface.

  2. Bandwidth share. EC2 egress on a shared instance can't be sliced
     per-grantee by AWS billing. We attribute it by parsing per-domain
     nginx access logs (already maintained at
     `/srv/webapps/mycite/fnd/private/utilities/tools/analytics/<domain>/nginx/access.log`)
     and computing each domain's share of total bytes_sent over the
     window.

  3. Resolution of `msn_id -> domains` from the grantee profile JSONs
     under `/srv/webapps/mycite/fnd/private/utilities/tools/fnd-csm/`
     so the caller doesn't have to pre-fetch the mapping.

This module is consumed by the portal's `/__fnd/tolling/itemize`
+ `/__fnd/tolling/overview` routes (defined in `portal_host/app.py`)
which the per-client `/dashboard/` static surfaces fetch from.
"""

from __future__ import annotations

import glob
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


# Match the standard nginx "combined" access-log format:
#   $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent ...
# We only care about $time_local (group 1) and $body_bytes_sent (group 2).
_ACCESS_LOG_RE = re.compile(
    r'^\S+\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+"[^"]*"\s+\d+\s+(?P<bytes>\d+)'
)
_TIME_FORMAT = "%d/%b/%Y:%H:%M:%S %z"

_DEFAULT_ANALYTICS_ROOT = Path(
    "/srv/webapps/mycite/fnd/private/utilities/tools/analytics"
)
_DEFAULT_FND_CSM_ROOT = Path(
    "/srv/webapps/mycite/fnd/private/utilities/tools/fnd-csm"
)


# ---------------------------------------------------------------------
# Grantee profile lookup (no MOS dependency — JSON files only)
# ---------------------------------------------------------------------


def load_grantee_directory(
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> list[dict[str, Any]]:
    """Return every grantee profile JSON under the fnd-csm tool dir.

    Each entry is the parsed JSON dict. Parsing failures are skipped
    silently; this is a read surface, not a validation surface.
    """
    root = Path(fnd_csm_root)
    out: list[dict[str, Any]] = []
    for path in sorted(glob.glob(str(root / "grantee.*.json"))):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def domains_for_grantee(
    msn_id: str,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> list[str]:
    """Return the list of domains owned by `msn_id` per its profile.

    Returns [] if the grantee has no profile or no `domains` field.
    """
    for profile in load_grantee_directory(fnd_csm_root):
        if str(profile.get("msn_id", "")) != msn_id:
            continue
        return [str(d).lower() for d in profile.get("domains") or [] if str(d)]
    return []


def grantee_for_domain(
    domain: str,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any] | None:
    """Resolve the grantee profile that owns `domain` (case-insensitive).

    Used by the dashboard `whoami` route when no oauth2-proxy header is
    present — the per-client `/dashboard/` lives at the client's own
    domain, so request.host tells us which grantee owns the dashboard.
    Once Keycloak auth is wired, headers take precedence.
    """
    if not domain:
        return None
    target = domain.lower()
    # Strip optional port (e.g. ":6101" on local dev).
    target = target.split(":", 1)[0]
    for profile in load_grantee_directory(fnd_csm_root):
        owned = [str(d).lower() for d in profile.get("domains") or []]
        if target in owned:
            return profile
    return None


# ---------------------------------------------------------------------
# Bandwidth share from nginx access logs
# ---------------------------------------------------------------------


def _parse_log_window_bytes(
    log_path: Path,
    start: datetime,
    end: datetime,
) -> int:
    """Sum body_bytes_sent over [start, end) for one nginx access log.

    Both bounds are timezone-aware. Lines outside the range are
    skipped without parsing the full record. Malformed lines are
    skipped silently.
    """
    if not log_path.exists():
        return 0
    total = 0
    try:
        for line in log_path.open("r", encoding="utf-8", errors="replace"):
            m = _ACCESS_LOG_RE.match(line)
            if not m:
                continue
            try:
                ts = datetime.strptime(m.group("time"), _TIME_FORMAT)
            except ValueError:
                continue
            if ts < start or ts >= end:
                continue
            try:
                total += int(m.group("bytes"))
            except ValueError:
                continue
    except OSError:
        return total
    return total


def bandwidth_share_by_domain(
    start: date,
    end: date,
    analytics_root: str | Path = _DEFAULT_ANALYTICS_ROOT,
) -> dict[str, dict[str, Any]]:
    """For every per-domain nginx access log under `analytics_root`,
    compute bytes sent in the window and the share of total bytes.

    Returns a dict keyed by domain:
      {domain: {bytes_sent: int, share: float}}
    where `share` is in [0.0, 1.0] and shares sum to 1.0 across
    domains. If the total is zero, every share is 0.0.

    Window is half-open: includes `start`, excludes `end` — matches
    AWS Cost Explorer convention.
    """
    # Treat the date bounds as UTC midnight, matching how nginx logs
    # tag entries with offset-aware timestamps (we don't shift, we
    # compare to the same instant in time across timezones).
    from datetime import timezone
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)

    root = Path(analytics_root)
    if not root.exists():
        return {}

    raw: dict[str, int] = {}
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        log_path = entry / "nginx" / "access.log"
        if not log_path.exists():
            continue
        raw[entry.name] = _parse_log_window_bytes(log_path, start_dt, end_dt)

    total = sum(raw.values())
    if total == 0:
        return {d: {"bytes_sent": 0, "share": 0.0} for d in raw}
    return {
        d: {"bytes_sent": b, "share": b / total}
        for d, b in raw.items()
    }


def bandwidth_share_for_grantee(
    msn_id: str,
    start: date,
    end: date,
    *,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
    analytics_root: str | Path = _DEFAULT_ANALYTICS_ROOT,
) -> dict[str, Any]:
    """Aggregate `bandwidth_share_by_domain` across the grantee's domains.

    Returns:
        {bytes_sent: int, share: float, domains: [domain, ...]}

    Falls back to share=0.0 when the grantee has no domains or no
    matching log files.
    """
    grantee_domains = set(domains_for_grantee(msn_id, fnd_csm_root))
    all_shares = bandwidth_share_by_domain(start, end, analytics_root)
    total_bytes = 0
    total_share = 0.0
    matched: list[str] = []
    for domain, entry in all_shares.items():
        if domain in grantee_domains:
            total_bytes += int(entry["bytes_sent"])
            total_share += float(entry["share"])
            matched.append(domain)
    return {
        "bytes_sent": total_bytes,
        "share": total_share,
        "domains": sorted(matched),
    }


# ---------------------------------------------------------------------
# Whoami / scope guard helpers (used by the portal route)
# ---------------------------------------------------------------------


def resolve_grantee_from_headers(
    headers: dict[str, str] | Any,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any] | None:
    """Resolve the calling grantee from oauth2-proxy headers.

    Looks for ``X-Auth-Request-Grantee`` (explicit msn_id claim
    mapped from Keycloak attributes) first, then falls back to
    ``X-Auth-Request-Email`` matched against grantee profile `users`
    lists.

    Returns the matching grantee profile dict or None when no auth
    headers are present / no match is found. The caller decides
    whether to allow unauthenticated reads (operator-only, internal
    tooling) or reject.
    """
    if hasattr(headers, "get"):
        get = headers.get
    else:
        get = lambda key, default=None: default  # noqa: E731

    claimed_msn = str(get("X-Auth-Request-Grantee", "") or "").strip()
    claimed_email = str(get("X-Auth-Request-Email", "") or "").strip().lower()

    if not claimed_msn and not claimed_email:
        return None

    for profile in load_grantee_directory(fnd_csm_root):
        if claimed_msn and str(profile.get("msn_id", "")) == claimed_msn:
            return profile
        if claimed_email:
            users = [str(u).lower() for u in profile.get("users") or []]
            if claimed_email in users:
                return profile
    return None
