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

    Resolution order:
      1. ``X-Auth-Request-Grantee`` explicit msn_id claim.
      2. ``X-Auth-Request-User`` username with our ``<SHORT_NAME>-<...>``
         convention (e.g. ``BPW-brock``, ``TFF-mark``). Prefix matches
         a grantee `short_name` (case-insensitive). Established when
         dashboard auth was wired to a Keycloak realm without a
         per-user grantee_id attribute mapping.
      3. ``X-Auth-Request-Email`` matched against grantee profile
         `users` lists.

    Returns the matching grantee profile dict or None when no auth
    headers are present / no match is found.
    """
    if hasattr(headers, "get"):
        get = headers.get
    else:
        get = lambda key, default=None: default  # noqa: E731

    claimed_msn = str(get("X-Auth-Request-Grantee", "") or "").strip()
    claimed_user = str(get("X-Auth-Request-User", "") or "").strip()
    claimed_email = str(get("X-Auth-Request-Email", "") or "").strip().lower()

    if not claimed_msn and not claimed_user and not claimed_email:
        return None

    short_name_prefix = ""
    if claimed_user and "-" in claimed_user:
        short_name_prefix = claimed_user.split("-", 1)[0].lower()

    for profile in load_grantee_directory(fnd_csm_root):
        if claimed_msn and str(profile.get("msn_id", "")) == claimed_msn:
            return profile
        if short_name_prefix:
            if str(profile.get("short_name", "")).lower() == short_name_prefix:
                return profile
        if claimed_email:
            users = [str(u).lower() for u in profile.get("users") or []]
            if claimed_email in users:
                return profile
    return None


# ---------------------------------------------------------------------
# Tolling snapshot JSON — operator-curated per-grantee monthly rollups
# ---------------------------------------------------------------------

TOLLING_SCHEMA = "mycite.v2.grantee.tolling.v1"


def _tolling_path_for(
    msn_id: str,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> Path:
    """Sibling file to grantee profile: tolling.<sponsor>.<msn>.json.

    Filenames mirror the grantee profile shape: the sponsor msn (always
    FND today) and the grantee msn. Glob the existing grantee profile
    for `msn_id` to derive the sponsor token, fall back to the FND
    sponsor msn for grantees that don't have one yet.
    """
    root = Path(fnd_csm_root)
    for profile_path in sorted(root.glob(f"grantee.*.{msn_id}.json")):
        # filename is `grantee.<sponsor>.<grantee>.json`
        parts = profile_path.name.split(".")
        if len(parts) >= 4 and parts[-2] == msn_id:
            sponsor = parts[1]
            return root / f"tolling.{sponsor}.{msn_id}.json"
    # No grantee profile found yet; use FND as the sponsor.
    return root / f"tolling.3-2-3-17-77-1-6-4-1-4.{msn_id}.json"


def read_tolling_snapshot(
    msn_id: str,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    """Read the tolling JSON for a grantee. Returns an empty-shaped
    snapshot when the file doesn't exist yet (so dashboards don't 404
    on a never-refreshed grantee)."""
    path = _tolling_path_for(msn_id, fnd_csm_root)
    if not path.exists():
        return {
            "schema": TOLLING_SCHEMA,
            "msn_id": msn_id,
            "last_refreshed_at": "",
            "currency": "",
            "monthly": [],
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "schema": TOLLING_SCHEMA,
            "msn_id": msn_id,
            "last_refreshed_at": "",
            "currency": "",
            "monthly": [],
            "error": "snapshot_unreadable",
        }


def upsert_tolling_row(
    msn_id: str,
    row: dict[str, Any],
    *,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    """Insert or replace the monthly row keyed by `period` (YYYY-MM)
    in the grantee's tolling JSON. Atomic write via tempfile+rename so
    a half-written file never replaces a good one. Returns the new
    full snapshot."""
    from datetime import UTC, datetime
    import os
    import tempfile

    path = _tolling_path_for(msn_id, fnd_csm_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = read_tolling_snapshot(msn_id, fnd_csm_root)
    snapshot.setdefault("schema", TOLLING_SCHEMA)
    snapshot["msn_id"] = msn_id
    snapshot["last_refreshed_at"] = datetime.now(UTC).isoformat()
    monthly = list(snapshot.get("monthly") or [])
    target_period = str(row.get("period") or "")
    monthly = [r for r in monthly if str(r.get("period")) != target_period]
    monthly.append(row)
    monthly.sort(key=lambda r: str(r.get("period")), reverse=True)
    snapshot["monthly"] = monthly
    short_name = ""
    for profile in load_grantee_directory(fnd_csm_root):
        if str(profile.get("msn_id", "")) == msn_id:
            short_name = str(profile.get("short_name", ""))
            break
    if short_name:
        snapshot["short_name"] = short_name
    payload = json.dumps(snapshot, indent=2) + "\n"
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return snapshot


def _count_active_contacts(
    domains: list[str],
    analytics_root: str | Path = _DEFAULT_ANALYTICS_ROOT,
) -> int:
    """Count `subscribed=true` contacts across the grantee's domains."""
    contacts_root = Path(analytics_root).parent / "aws-csm" / "newsletter"
    total = 0
    for d in domains:
        path = contacts_root / f"newsletter.{d}.contacts.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        total += sum(
            1 for c in data.get("contacts") or []
            if c.get("subscribed")
        )
    return total


def compute_tolling_row(
    msn_id: str,
    period: str,
    *,
    aws_peripheral: Any,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
    analytics_root: str | Path = _DEFAULT_ANALYTICS_ROOT,
) -> dict[str, Any]:
    """Build a single monthly tolling row for the grantee from live AWS
    + nginx-log data. `period` is YYYY-MM. Window is the calendar
    month; end is exclusive per Cost Explorer convention.

    `aws_peripheral` is an `AwsPeripheralCloudAdapter` (injected so
    callers can pass a singleton or a mock)."""
    from calendar import monthrange
    from datetime import date as _date

    try:
        year_str, month_str = period.split("-", 1)
        year, month = int(year_str), int(month_str)
    except ValueError as exc:
        raise ValueError(f"period must be YYYY-MM, got {period!r}") from exc
    start = _date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end = _date(year, month, last_day) if month != 12 else _date(year, 12, 31)
    # half-open: end_exclusive = first of next month, or 31-day-month for Dec.
    if month == 12:
        end_exclusive = _date(year + 1, 1, 1)
    else:
        end_exclusive = _date(year, month + 1, 1)

    breakdown = aws_peripheral.get_costs_by_grantee(
        msn_id=msn_id,
        start=start.isoformat(),
        end=end_exclusive.isoformat(),
    )
    dt = aws_peripheral.get_data_transfer_out_cost(
        start=start.isoformat(), end=end_exclusive.isoformat()
    )
    bandwidth = bandwidth_share_for_grantee(
        msn_id, start, end_exclusive,
        fnd_csm_root=fnd_csm_root, analytics_root=analytics_root,
    )
    domains = domains_for_grantee(msn_id, fnd_csm_root)
    contacts_active = _count_active_contacts(domains, analytics_root)

    by_service = breakdown.get("by_service") or {}
    def _sum_services(*needles: str) -> float:
        total = 0.0
        for svc, amount in by_service.items():
            low = svc.lower()
            if any(needle in low for needle in needles):
                try:
                    total += float(amount)
                except ValueError:
                    continue
        return total

    ses_cost = _sum_services("simple email", "ses")
    domain_fees = _sum_services("route 53")
    s3_cost = _sum_services("simple storage", "s3")
    grand = float(breakdown.get("grand_total") or 0)
    other_aws_cost = grand - ses_cost - domain_fees - s3_cost
    if other_aws_cost < 0:
        other_aws_cost = 0.0
    bw_share = float(bandwidth.get("share") or 0)
    try:
        dt_total = float(dt.get("amount") or 0)
    except ValueError:
        dt_total = 0.0
    bandwidth_cost = dt_total * bw_share
    subtotal = ses_cost + domain_fees + s3_cost + other_aws_cost + bandwidth_cost

    return {
        "period": period,
        "emails_sent": 0,
        "emails_bounced": 0,
        "contacts_active": contacts_active,
        "domains_count": len(domains),
        "domain_fees": f"{domain_fees:.4f}",
        "ses_cost": f"{ses_cost:.4f}",
        "s3_cost": f"{s3_cost:.4f}",
        "other_aws_cost": f"{other_aws_cost:.4f}",
        "bandwidth_bytes": int(bandwidth.get("bytes_sent") or 0),
        "bandwidth_share_pct": round(bw_share * 100, 4),
        "bandwidth_cost": f"{bandwidth_cost:.6f}",
        "account_data_transfer_total": dt.get("amount", "0"),
        "subtotal": f"{subtotal:.4f}",
        "currency": breakdown.get("currency") or dt.get("currency") or "",
        "notes": "",
    }
