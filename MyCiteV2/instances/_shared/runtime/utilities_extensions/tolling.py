"""ext_tolling — operator cost ledger + per-grantee invoice derivation.

Two layers:

  Layer 1 — **Operator ledger** (`tolling_ledger.json`). One row per
  month, every Cost Explorer line item itemized (service, usage_type,
  quantity, amount), each tagged with an attribution: `direct`
  (msn_id-tagged resource), `shared_pool` (shared infra, currently the
  `fnd_operator` pool), or `residue` (no msn_id tag at all). FND-owned;
  surfaces full raw cost.

  Layer 2 — **Per-grantee invoice** (`tolling.<sponsor>.<msn>.json`).
  Derived from the ledger by applying `tolling_billing_rules.json` —
  per-grantee margin %, waivers, flat rates. Clients never see raw AWS
  dollars; they see what FND chooses to bill them.

Bandwidth share (EC2 egress on a shared instance) is attributed from
per-domain nginx access logs and shows up as a `data_transfer` line
item on each grantee's invoice when the rules engine doesn't waive it.

Routes:
  GET  /__fnd/tolling/snapshot      — read per-grantee invoice
  POST /__fnd/tolling/refresh       — operator-only: recompute ledger + all invoices
  GET  /__fnd/tolling/ledger        — operator-only: read raw ledger row
  GET  /__fnd/tolling/billing-rules — operator-only
  POST /__fnd/tolling/billing-rules — operator-only

Back-compat: ``compute_tolling_row`` + ``upsert_tolling_row`` still work
and now write the invoice.v1 schema underneath; callers don't need to
change. ``read_tolling_snapshot`` returns invoice.v1 unchanged on the
wire.
"""

from __future__ import annotations

import glob
import json
import re
import time
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

# Per-process caches. Grantee profiles and bandwidth-share both back
# every dashboard request and are derived from disk; without caching,
# the same JSON globs + log walks happen 4-8x per page load. A short
# TTL keeps operator-driven edits visible within ~1 minute.
_CACHE_TTL_SECONDS = 60.0
_GRANTEE_DIRECTORY_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_BANDWIDTH_SHARE_CACHE: dict[
    tuple[str, str, str], tuple[float, dict[str, dict[str, Any]]]
] = {}


def clear_caches() -> None:
    """Drop all module caches. For tests and operator-triggered refresh."""
    _GRANTEE_DIRECTORY_CACHE.clear()
    _BANDWIDTH_SHARE_CACHE.clear()


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
    key = str(root)
    now = time.monotonic()
    cached = _GRANTEE_DIRECTORY_CACHE.get(key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    out: list[dict[str, Any]] = []
    for path in sorted(glob.glob(str(root / "grantee.*.json"))):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.append(data)
    _GRANTEE_DIRECTORY_CACHE[key] = (now, out)
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
    root = Path(analytics_root)
    cache_key = (str(root), start.isoformat(), end.isoformat())
    now = time.monotonic()
    cached = _BANDWIDTH_SHARE_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    # Treat the date bounds as UTC midnight, matching how nginx logs
    # tag entries with offset-aware timestamps (we don't shift, we
    # compare to the same instant in time across timezones).
    from datetime import timezone
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)

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
        result = {d: {"bytes_sent": 0, "share": 0.0} for d in raw}
    else:
        result = {
            d: {"bytes_sent": b, "share": b / total}
            for d, b in raw.items()
        }
    _BANDWIDTH_SHARE_CACHE[cache_key] = (now, result)
    return result


def compute_bandwidth_cost(
    bandwidth: dict[str, Any],
    dt_cost: dict[str, Any],
) -> dict[str, Any]:
    """Attribute account-wide EC2 DataTransfer-Out spend to this grantee
    by multiplying its bandwidth share against the account total.

    Returns the components callers want; each caller formats the
    `amount_value` float to its own precision before serializing.
    """
    try:
        dt_amount = float(dt_cost.get("amount", "0") or 0)
    except (TypeError, ValueError):
        dt_amount = 0.0
    share = float(bandwidth.get("share") or 0)
    return {
        "share": share,
        "amount_value": dt_amount * share,
        "currency": dt_cost.get("currency", "") or "",
        "account_total": dt_cost.get("amount", "0") or "0",
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
# Schema constants + operator-side paths
# ---------------------------------------------------------------------

# Legacy per-grantee schema (still produced as a back-compat reader);
# the per-grantee tolling file is now schema `invoice.v1` (below).
TOLLING_SCHEMA = "mycite.v2.grantee.tolling.v1"

# v2 schemas — operator ledger, billing rules, derived invoice.
LEDGER_SCHEMA = "mycite.v2.operator.tolling.ledger.v1"
BILLING_RULES_SCHEMA = "mycite.v2.operator.tolling.billing_rules.v1"
INVOICE_SCHEMA = "mycite.v2.grantee.tolling.invoice.v1"

OPERATOR_MSN_ID = "3-2-3-17-77-1-6-4-1-4"  # FND

# Cost-allocation pools. `fnd_operator` covers shared infra operated by
# FND today. `clients_server` is reserved for a future second EC2 that
# hosts only client sites — no resources are tagged into it yet.
COST_POOL_FND_OPERATOR = "fnd_operator"
COST_POOL_CLIENTS_SERVER = "clients_server"

# Line-item categories the ledger emits. Each line gets exactly one.
LINE_ITEM_CATEGORIES = (
    "compute",
    "storage_block",
    "object_storage",
    "object_storage_api",
    "data_transfer",
    "dns_hosted_zone",
    "domain_registration",
    "email_sending",
    "email_inbound",
    "logs",
    "metrics",
    "notifications",
    "queue",
    "secrets",
    "certificates",
    "tax",
    "unattributed",
)

# USAGE_TYPE pattern → category (first match wins). Patterns are
# substrings against the AWS USAGE_TYPE string. Service-level fallback
# below catches anything that doesn't pattern-match.
_USAGE_TYPE_TO_CATEGORY: tuple[tuple[str, str], ...] = (
    ("BoxUsage",                "compute"),
    ("EBS:VolumeUsage",         "storage_block"),
    ("EBS:VolumeIOUsage",       "storage_block"),
    ("EBS:SnapshotUsage",       "storage_block"),
    ("PublicIPv4",              "compute"),
    ("Lambda-GB-Second",        "compute"),
    ("Lambda-Request",          "compute"),
    ("AWS-Out-Bytes",           "data_transfer"),
    ("DataTransfer-Out",        "data_transfer"),
    ("DataTransfer-Regional",   "data_transfer"),
    ("CloudFront-Out-Bytes",    "data_transfer"),
    ("TimedStorage-ByteHrs",    "object_storage"),
    ("TimedStorage",            "object_storage"),
    ("Requests-Tier1",          "object_storage_api"),
    ("Requests-Tier2",          "object_storage_api"),
    ("Requests-",               "object_storage_api"),
    ("HostedZone",              "dns_hosted_zone"),
    ("DNS-Queries",             "dns_hosted_zone"),
    ("Route53-Domains",         "domain_registration"),
    ("Receipt",                 "email_inbound"),
    ("Send",                    "email_sending"),
    ("DKIM",                    "email_sending"),
    ("AWSSecretsManager-Secrets", "secrets"),
    ("APIRequest",              "metrics"),
    ("LogIngestion",            "logs"),
    ("LogStorage",              "logs"),
    ("DataProcessing-Bytes",    "logs"),
    ("Messages-Tier",           "queue"),
    ("Requests-Notifications",  "notifications"),
    ("ACM-",                    "certificates"),
)

# Fallback category by AWS Cost Explorer SERVICE name.
_SERVICE_TO_CATEGORY: dict[str, str] = {
    "Amazon Simple Email Service": "email_sending",
    "Amazon Route 53": "dns_hosted_zone",
    "Amazon Registrar": "domain_registration",
    "Amazon Simple Storage Service": "object_storage",
    "Amazon Elastic Compute Cloud - Compute": "compute",
    "EC2 - Other": "data_transfer",
    "Amazon Virtual Private Cloud": "compute",
    "AWS Lambda": "compute",
    "AWS Secrets Manager": "secrets",
    "Amazon CloudWatch": "metrics",
    "AmazonCloudWatch": "logs",
    "Amazon Simple Notification Service": "notifications",
    "Amazon Simple Queue Service": "queue",
    "AWS Certificate Manager": "certificates",
    "AWS Cost Explorer": "metrics",
    "AWS Backup": "storage_block",
    "Tax": "tax",
}


def classify_line_item(service: str, usage_type: str) -> str:
    """Map a Cost Explorer (SERVICE, USAGE_TYPE) pair to a ledger category."""
    for needle, category in _USAGE_TYPE_TO_CATEGORY:
        if needle in (usage_type or ""):
            return category
    return _SERVICE_TO_CATEGORY.get(service, "unattributed")


def _ledger_path(fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT) -> Path:
    return Path(fnd_csm_root) / "tolling_ledger.json"


def _billing_rules_path(fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT) -> Path:
    return Path(fnd_csm_root) / "tolling_billing_rules.json"


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


# ---------------------------------------------------------------------
# Atomic JSON write helper — reused by ledger, rules, invoice upserts.
# ---------------------------------------------------------------------


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2, sort_keys=False) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _hash_line_id(period: str, service: str, usage_type: str, attribution_key: str) -> str:
    """Stable id for a ledger line — survives across refreshes so rules
    can target it by id."""
    import hashlib
    raw = f"{period}|{service}|{usage_type}|{attribution_key}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------
# Operator ledger (v2)
# ---------------------------------------------------------------------


def _period_window(period: str) -> tuple[str, str]:
    """YYYY-MM → (start_iso, end_exclusive_iso)."""
    from calendar import monthrange
    from datetime import date as _date

    try:
        year_str, month_str = period.split("-", 1)
        year, month = int(year_str), int(month_str)
    except ValueError as exc:
        raise ValueError(f"period must be YYYY-MM, got {period!r}") from exc
    start = _date(year, month, 1)
    if month == 12:
        end_exclusive = _date(year + 1, 1, 1)
    else:
        end_exclusive = _date(year, month + 1, 1)
    return start.isoformat(), end_exclusive.isoformat()


def _domain_to_msn(
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, str]:
    """Reverse-index domain → msn_id for invoice derivation."""
    out: dict[str, str] = {}
    for profile in load_grantee_directory(fnd_csm_root):
        msn = str(profile.get("msn_id", ""))
        if not msn:
            continue
        for d in profile.get("domains") or []:
            out[str(d).lower()] = msn
    return out


# A10b — environment knobs for the SES-event enrichment hook. When unset
# the enrichment is a no-op (metrics dicts default to {} so downstream
# code that already reads emails_sent_by_msn etc. doesn't break).
# Operator sets these in the systemd unit / shell env. Default prefix
# matches the ses_event_sink Lambda's default.
import os as _os
_SES_EVENTS_BUCKET_ENV = "MYCITE_SES_EVENTS_BUCKET"
_SES_EVENTS_PREFIX_ENV = "MYCITE_SES_EVENTS_PREFIX"
_SES_EVENTS_PREFIX_DEFAULT = "ses_events"


def _aggregate_ses_event_metrics(
    start: str,
    end_excl: str,
    *,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
    events_bucket: str | None = None,
    events_prefix: str | None = None,
    s3_client: Any | None = None,
) -> dict[str, dict[str, int]]:
    """Walk the ses_event_sink S3 prefix and count Send/Bounce/Complaint
    events per grantee for the period [start, end_excl).

    Returns ``{"emails_sent_by_msn": {msn: count}, "emails_bounced_by_msn":
    {msn: count}, "emails_complained_by_msn": {msn: count}}``.

    The Lambda partitions by recipient domain (see
    `aws_lambdas/ses_event_sink/lambda_function.py`); we reverse-index
    via the grantee profile JSONs' ``domains`` list to attribute each
    domain back to its msn_id.

    Defensive — any AWS / IAM / config error returns empty dicts rather
    than failing the whole ledger compute. The SES enrichment is opt-in;
    not having it must not be a deal-breaker for the rest of the row.
    """
    empty: dict[str, dict[str, int]] = {
        "emails_sent_by_msn": {},
        "emails_bounced_by_msn": {},
        "emails_complained_by_msn": {},
    }

    bucket = (events_bucket if events_bucket is not None
              else _os.environ.get(_SES_EVENTS_BUCKET_ENV, "")).strip()
    if not bucket:
        return empty
    prefix = (events_prefix if events_prefix is not None
              else _os.environ.get(_SES_EVENTS_PREFIX_ENV, _SES_EVENTS_PREFIX_DEFAULT)
              ).strip().strip("/") or _SES_EVENTS_PREFIX_DEFAULT

    domain_to_msn = _domain_to_msn(fnd_csm_root)
    if not domain_to_msn:
        return empty

    # Date list: start .. end_excl - 1 day. Both are YYYY-MM-DD ISO strings.
    from datetime import date as _date, timedelta
    try:
        start_d = _date.fromisoformat(start)
        end_d = _date.fromisoformat(end_excl)
    except ValueError:
        return empty
    dates: list[str] = []
    cur = start_d
    while cur < end_d:
        dates.append(cur.isoformat())
        cur = cur + timedelta(days=1)

    if s3_client is None:
        try:
            import boto3
            s3_client = boto3.client("s3")
        except Exception:  # noqa: BLE001
            return empty

    # Lambda writes one S3 object per event under
    #   <prefix>/<domain>/<YYYY-MM-DD>/<EventType>/<message_id>-<ulid>.json
    # We count objects per (domain, date, event_type) via list_objects_v2
    # KeyCount, paginating to be safe.
    event_type_to_metric = {
        "Send": "emails_sent_by_msn",
        "Bounce": "emails_bounced_by_msn",
        "Complaint": "emails_complained_by_msn",
    }
    result: dict[str, dict[str, int]] = {
        "emails_sent_by_msn": {},
        "emails_bounced_by_msn": {},
        "emails_complained_by_msn": {},
    }
    for domain, msn in domain_to_msn.items():
        for day in dates:
            for event_type, metric_key in event_type_to_metric.items():
                key_prefix = f"{prefix}/{domain}/{day}/{event_type}/"
                count = 0
                continuation: str | None = None
                try:
                    while True:
                        kwargs: dict[str, Any] = {
                            "Bucket": bucket,
                            "Prefix": key_prefix,
                        }
                        if continuation:
                            kwargs["ContinuationToken"] = continuation
                        resp = s3_client.list_objects_v2(**kwargs)
                        count += int(resp.get("KeyCount") or 0)
                        if resp.get("IsTruncated"):
                            continuation = resp.get("NextContinuationToken")
                            if not continuation:
                                break
                        else:
                            break
                except Exception:  # noqa: BLE001
                    # One domain/day failing must not poison the rest.
                    continue
                if count:
                    result[metric_key][msn] = result[metric_key].get(msn, 0) + count
    return result


def compute_ledger_for_period(
    period: str,
    *,
    aws_peripheral: Any,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
    analytics_root: str | Path = _DEFAULT_ANALYTICS_ROOT,
) -> dict[str, Any]:
    """Build a complete ledger row for the period from live AWS + nginx data."""
    from datetime import UTC, date as _date, datetime

    start, end_excl = _period_window(period)

    line_items: list[dict[str, Any]] = []
    totals_direct: dict[str, float] = {}
    totals_shared_pool: dict[str, float] = {COST_POOL_FND_OPERATOR: 0.0}
    totals_residue = 0.0
    currency = ""

    # --- per-grantee direct + shared lines via tag_filter
    # For each known grantee, pull every line tagged msn_id=that grantee.
    # The operator (FND) absorbs the shared pool today — we route the
    # shared-leaning categories into the shared_pool bucket so the rules
    # engine can split them across pools later.
    SHARED_LEANING_CATEGORIES = {
        "compute", "storage_block", "object_storage", "logs",
        "metrics", "secrets", "notifications", "queue",
    }

    known_msns: list[str] = []
    for profile in load_grantee_directory(fnd_csm_root):
        msn = str(profile.get("msn_id", ""))
        if msn:
            known_msns.append(msn)
    # FND first so the operator pool gets stable ids.
    if OPERATOR_MSN_ID in known_msns:
        known_msns = [OPERATOR_MSN_ID] + [m for m in known_msns if m != OPERATOR_MSN_ID]

    for msn in known_msns:
        lines = aws_peripheral.get_costs_breakdown(
            start=start, end=end_excl,
            group_by=("SERVICE", "USAGE_TYPE"),
            tag_filter={"Key": "msn_id", "Values": [msn]},
        )
        is_operator = (msn == OPERATOR_MSN_ID)
        for ln in lines:
            keys = tuple(ln.get("keys") or ())
            service = keys[0] if len(keys) > 0 else ""
            usage_type = keys[1] if len(keys) > 1 else ""
            category = classify_line_item(service, usage_type)
            currency = currency or str(ln.get("currency") or "")
            amount = float(ln.get("amount") or 0)
            if amount == 0.0:
                continue
            # Operator: split into direct vs shared_pool by category.
            # Non-operator grantees: all lines are direct.
            if is_operator and category in SHARED_LEANING_CATEGORIES:
                attribution = {
                    "type": "shared_pool",
                    "pool": COST_POOL_FND_OPERATOR,
                }
                attribution_key = f"pool:{COST_POOL_FND_OPERATOR}"
                totals_shared_pool[COST_POOL_FND_OPERATOR] = (
                    totals_shared_pool.get(COST_POOL_FND_OPERATOR, 0.0) + amount
                )
            else:
                tenant = ""
                for profile in load_grantee_directory(fnd_csm_root):
                    if str(profile.get("msn_id", "")) == msn:
                        tenant = str(profile.get("short_name") or "").lower()
                        break
                attribution = {
                    "type": "direct",
                    "msn_id": msn,
                    "tenant": tenant,
                }
                attribution_key = f"direct:{msn}"
                totals_direct[msn] = totals_direct.get(msn, 0.0) + amount
            line_items.append({
                "id": _hash_line_id(period, service, usage_type, attribution_key),
                "category": category,
                "label": f"{service} — {usage_type}" if usage_type else service,
                "service": service,
                "usage_type": usage_type,
                "usage_quantity": str(ln.get("usage_quantity") or "0"),
                "usage_unit": str(ln.get("usage_unit") or ""),
                "amount": f"{amount:.10f}",
                "amount_amortized": f"{amount:.10f}",  # adjusted below for renewals
                "attribution": attribution,
            })

    # --- untagged residue (msn_id tag absent)
    try:
        residue_lines = aws_peripheral.get_costs_breakdown(
            start=start, end=end_excl,
            group_by=("SERVICE", "USAGE_TYPE"),
            tag_filter={"Key": "msn_id", "Values": [""], "MatchOptions": ["ABSENT"]},
        )
    except Exception:
        # Fallback: use get_untagged_residue (loses USAGE_TYPE detail
        # but doesn't crash if MatchOptions support changes).
        residue_lines = []
        residue_bd = aws_peripheral.get_untagged_residue(start=start, end=end_excl)
        for svc, amt in (residue_bd.get("by_service") or {}).items():
            residue_lines.append({
                "keys": (svc, ""),
                "amount": str(amt),
                "currency": residue_bd.get("currency") or "",
                "usage_quantity": "0",
                "usage_unit": "",
            })

    for ln in residue_lines:
        keys = tuple(ln.get("keys") or ())
        service = keys[0] if len(keys) > 0 else ""
        usage_type = keys[1] if len(keys) > 1 else ""
        category = classify_line_item(service, usage_type)
        currency = currency or str(ln.get("currency") or "")
        amount = float(ln.get("amount") or 0)
        if amount == 0.0:
            continue
        totals_residue += amount
        line_items.append({
            "id": _hash_line_id(period, service, usage_type, "residue"),
            "category": category,
            "label": f"{service} — {usage_type} (untagged)" if usage_type else f"{service} (untagged)",
            "service": service,
            "usage_type": usage_type,
            "usage_quantity": str(ln.get("usage_quantity") or "0"),
            "usage_unit": str(ln.get("usage_unit") or ""),
            "amount": f"{amount:.10f}",
            "amount_amortized": f"{amount:.10f}",
            "attribution": {"type": "residue"},
        })

    # --- bandwidth-share metrics (per-domain bytes_sent over the window)
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end_excl)
    bandwidth_by_domain = bandwidth_share_by_domain(
        start_date, end_date, analytics_root,
    )
    total_bytes = sum(int(entry.get("bytes_sent") or 0) for entry in bandwidth_by_domain.values())

    # --- contacts-active per grantee
    contacts_by_msn: dict[str, int] = {}
    domain_idx = _domain_to_msn(fnd_csm_root)
    for profile in load_grantee_directory(fnd_csm_root):
        msn = str(profile.get("msn_id", ""))
        if not msn:
            continue
        domains = [str(d).lower() for d in profile.get("domains") or []]
        contacts_by_msn[msn] = _count_active_contacts(domains, analytics_root)

    # --- amortize annual domain renewals into 1/12 per month
    # Find any domain_registration lines in the ledger window and divide
    # by 12 for the amortized column. The raw `amount` keeps the actual
    # billed value so the operator view shows both.
    for line in line_items:
        if line["category"] == "domain_registration":
            try:
                raw = float(line["amount"])
                line["amount_amortized"] = f"{raw / 12:.10f}"
            except ValueError:
                pass

    sort_amount = lambda r: float(r.get("amount") or 0)  # noqa: E731
    line_items.sort(key=sort_amount, reverse=True)

    # A10b — SES event enrichment. Walks the ses_event_sink S3 prefix
    # for the period and counts Send/Bounce/Complaint events per msn_id.
    # No-op when MYCITE_SES_EVENTS_BUCKET env is unset (returns empty
    # dicts) so this layer is safe even before the sink Lambda is
    # deployed.
    ses_metrics = _aggregate_ses_event_metrics(
        start, end_excl, fnd_csm_root=fnd_csm_root,
    )

    return {
        "period": period,
        "currency": currency or "USD",
        "line_items": line_items,
        "totals_by_attribution": {
            "direct": {k: f"{v:.10f}" for k, v in totals_direct.items()},
            "shared_pool": {k: f"{v:.10f}" for k, v in totals_shared_pool.items()},
            "residue": f"{totals_residue:.10f}",
        },
        "metrics": {
            "bandwidth_bytes_total": total_bytes,
            "bandwidth_by_domain": {
                d: int(e.get("bytes_sent") or 0)
                for d, e in bandwidth_by_domain.items()
            },
            "contacts_active_by_msn": contacts_by_msn,
            "domain_index": domain_idx,
            "emails_sent_by_msn": ses_metrics["emails_sent_by_msn"],
            "emails_bounced_by_msn": ses_metrics["emails_bounced_by_msn"],
            "emails_complained_by_msn": ses_metrics["emails_complained_by_msn"],
        },
        "computed_at": datetime.now(UTC).isoformat(),
        "notes": "",
    }


def read_ledger(
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    """Read the full operator ledger (all periods). Returns empty skeleton if missing."""
    path = _ledger_path(fnd_csm_root)
    if not path.exists():
        return {
            "schema": LEDGER_SCHEMA,
            "currency": "USD",
            "last_refreshed_at": "",
            "cost_pools": [COST_POOL_FND_OPERATOR],
            "monthly": [],
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "schema": LEDGER_SCHEMA,
            "currency": "USD",
            "last_refreshed_at": "",
            "cost_pools": [COST_POOL_FND_OPERATOR],
            "monthly": [],
            "error": "ledger_unreadable",
        }


def read_ledger_row(
    period: str,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any] | None:
    """Return the ledger row for `period` (YYYY-MM) or None."""
    ledger = read_ledger(fnd_csm_root)
    for row in ledger.get("monthly") or []:
        if str(row.get("period")) == period:
            return row
    return None


def upsert_ledger_row(
    row: dict[str, Any],
    *,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    """Insert or replace the monthly row in the ledger. Returns the new ledger."""
    from datetime import UTC, datetime

    ledger = read_ledger(fnd_csm_root)
    ledger["schema"] = LEDGER_SCHEMA
    ledger.setdefault("cost_pools", [COST_POOL_FND_OPERATOR])
    ledger["currency"] = row.get("currency") or ledger.get("currency") or "USD"
    ledger["last_refreshed_at"] = datetime.now(UTC).isoformat()
    monthly = [r for r in (ledger.get("monthly") or []) if str(r.get("period")) != str(row.get("period"))]
    monthly.append(row)
    monthly.sort(key=lambda r: str(r.get("period")), reverse=True)
    ledger["monthly"] = monthly
    _atomic_write_json(_ledger_path(fnd_csm_root), ledger)
    return ledger


# ---------------------------------------------------------------------
# Billing rules (v2)
# ---------------------------------------------------------------------


def default_billing_rules() -> dict[str, Any]:
    return {
        "schema": BILLING_RULES_SCHEMA,
        "currency": "USD",
        "defaults": {
            "margin_pct": 25,
            "shared_pool_split": {
                COST_POOL_FND_OPERATOR: {"mode": "absorb_fnd"},
                COST_POOL_CLIENTS_SERVER: {"mode": "by_bandwidth_share"},
            },
            "minimum_invoice": "0.00",
            "residue_handling": "absorb_fnd",
        },
        "per_grantee": {},
    }


def read_billing_rules(
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    path = _billing_rules_path(fnd_csm_root)
    if not path.exists():
        return default_billing_rules()
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default_billing_rules()
    # Merge with defaults so partial files still work.
    base = default_billing_rules()
    base.update({k: v for k, v in rules.items() if v is not None})
    base.setdefault("per_grantee", {})
    defaults = base.get("defaults") or {}
    for k, v in (default_billing_rules()["defaults"]).items():
        defaults.setdefault(k, v)
    base["defaults"] = defaults
    return base


def write_billing_rules(
    rules: dict[str, Any],
    *,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    """Validate + atomically write the rules file. Returns the persisted dict."""
    if not isinstance(rules, dict):
        raise ValueError("rules must be a dict")
    margin = (rules.get("defaults") or {}).get("margin_pct")
    if margin is not None and not (0 <= float(margin) <= 1000):
        raise ValueError("margin_pct must be 0..1000")
    rules.setdefault("schema", BILLING_RULES_SCHEMA)
    rules.setdefault("currency", "USD")
    _atomic_write_json(_billing_rules_path(fnd_csm_root), rules)
    return rules


# ---------------------------------------------------------------------
# Invoice derivation (Ledger × Rules → per-grantee invoice)
# ---------------------------------------------------------------------


def _grantee_rules_for(rules: dict[str, Any], msn_id: str) -> dict[str, Any]:
    return (rules.get("per_grantee") or {}).get(msn_id) or {}


def _margin_for(rules: dict[str, Any], msn_id: str) -> float:
    grantee = _grantee_rules_for(rules, msn_id)
    if grantee.get("margin_pct_override") is not None:
        try:
            return float(grantee["margin_pct_override"])
        except (TypeError, ValueError):
            pass
    try:
        return float((rules.get("defaults") or {}).get("margin_pct") or 0)
    except (TypeError, ValueError):
        return 0.0


def derive_invoice_for_grantee(
    msn_id: str,
    period: str,
    ledger_row: dict[str, Any],
    rules: dict[str, Any],
    *,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    """Produce a per-grantee invoice row from a ledger row and the rules."""
    grantee_rules = _grantee_rules_for(rules, msn_id)
    margin = _margin_for(rules, msn_id)
    waive_categories = set(grantee_rules.get("waive_categories") or [])
    waive_line_ids = set(grantee_rules.get("waive_line_ids") or [])
    flat_rate = grantee_rules.get("flat_rate") or {}

    bandwidth_by_domain = (ledger_row.get("metrics") or {}).get("bandwidth_by_domain") or {}
    domain_idx = (ledger_row.get("metrics") or {}).get("domain_index") or {}
    bytes_for_msn = sum(
        bw for d, bw in bandwidth_by_domain.items() if domain_idx.get(d) == msn_id
    )
    bytes_total = sum(bandwidth_by_domain.values())
    bandwidth_share = (bytes_for_msn / bytes_total) if bytes_total else 0.0

    is_operator = (msn_id == OPERATOR_MSN_ID)
    pool_split = (rules.get("defaults") or {}).get("shared_pool_split") or {}
    residue_handling = (rules.get("defaults") or {}).get("residue_handling") or "absorb_fnd"

    billable_lines: list[dict[str, Any]] = []
    waived: list[dict[str, Any]] = []

    for line in (ledger_row.get("line_items") or []):
        attribution = line.get("attribution") or {}
        atype = attribution.get("type")
        category = str(line.get("category") or "unattributed")
        line_id = str(line.get("id") or "")
        amount = float(line.get("amount_amortized") or line.get("amount") or 0)

        # Routing: does this line surface on THIS grantee's invoice?
        my_share = 0.0
        if atype == "direct":
            if attribution.get("msn_id") == msn_id:
                my_share = 1.0
        elif atype == "shared_pool":
            pool = attribution.get("pool")
            mode = (pool_split.get(pool) or {}).get("mode") or "absorb_fnd"
            if mode == "absorb_fnd":
                my_share = 1.0 if is_operator else 0.0
            elif mode == "by_bandwidth_share":
                my_share = bandwidth_share
            elif mode == "equal":
                # Count active grantees (non-operator) and split equally.
                count = sum(1 for d in domain_idx.values() if d != OPERATOR_MSN_ID)
                my_share = (1.0 / count) if count > 0 and not is_operator else (1.0 if is_operator else 0.0)
            else:
                my_share = 1.0 if is_operator else 0.0
        elif atype == "residue":
            if residue_handling == "absorb_fnd":
                my_share = 1.0 if is_operator else 0.0
            elif residue_handling == "passthrough":
                my_share = 1.0 / max(1, len(set(domain_idx.values()) - {OPERATOR_MSN_ID}))
            else:
                my_share = 1.0 if is_operator else 0.0

        if my_share <= 0.0:
            continue

        share_amount = amount * my_share
        # Waivers
        if category in waive_categories or line_id in waive_line_ids:
            waived.append({
                "category": category,
                "label": line.get("label"),
                "amount": f"{share_amount:.6f}",
            })
            continue
        if share_amount == 0.0:
            continue

        billable_amount = share_amount * (1.0 + margin / 100.0)
        billable_lines.append({
            "id": line_id,
            "category": category,
            "label": line.get("label"),
            "quantity": str(line.get("usage_quantity") or "0"),
            "unit": str(line.get("usage_unit") or ""),
            "rate": f"{(billable_amount / float(line.get('usage_quantity') or 1)):.6f}"
                    if line.get("usage_quantity") and float(line.get("usage_quantity") or 0) > 0
                    else "",
            "amount": f"{billable_amount:.6f}",
        })

    # Bandwidth as its own billable line (already counted within shared_pool data_transfer if applicable;
    # for now emit only if the operator has decided to expose bandwidth attribution explicitly).
    # Skip: data_transfer lines are already routed via shared_pool/direct above.

    subtotal_billable = sum(float(l["amount"]) for l in billable_lines)
    minimum = (rules.get("defaults") or {}).get("minimum_invoice") or "0.00"
    try:
        minimum_v = float(minimum)
    except ValueError:
        minimum_v = 0.0
    if subtotal_billable > 0 and subtotal_billable < minimum_v:
        subtotal_billable = minimum_v

    # Flat-rate override: replaces computed subtotal.
    if flat_rate.get("amount"):
        try:
            subtotal_billable = float(flat_rate["amount"])
        except (TypeError, ValueError):
            pass

    return {
        "period": period,
        "currency": ledger_row.get("currency") or "USD",
        "billable_lines": billable_lines,
        "subtotal_billable": f"{subtotal_billable:.4f}",
        "discounts": [],
        "waived": waived,
        "notes": "",
    }


def upsert_invoice_row(
    msn_id: str,
    row: dict[str, Any],
    *,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
) -> dict[str, Any]:
    """Insert or replace the monthly invoice row for a grantee.

    Writes to the existing `tolling.<sponsor>.<msn>.json` path so the
    dashboard read endpoint keeps working unchanged.
    """
    from datetime import UTC, datetime

    path = _tolling_path_for(msn_id, fnd_csm_root)
    snapshot = read_tolling_snapshot(msn_id, fnd_csm_root)
    snapshot["schema"] = INVOICE_SCHEMA
    snapshot["msn_id"] = msn_id
    snapshot["last_refreshed_at"] = datetime.now(UTC).isoformat()
    snapshot["currency"] = row.get("currency") or snapshot.get("currency") or "USD"
    monthly = [r for r in (snapshot.get("monthly") or []) if str(r.get("period")) != str(row.get("period"))]
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
    _atomic_write_json(path, snapshot)
    return snapshot


def refresh_all(
    period: str,
    *,
    aws_peripheral: Any,
    fnd_csm_root: str | Path = _DEFAULT_FND_CSM_ROOT,
    analytics_root: str | Path = _DEFAULT_ANALYTICS_ROOT,
) -> dict[str, Any]:
    """End-to-end refresh: compute ledger row, persist, derive every
    grantee's invoice, persist each. Returns a summary."""
    ledger_row = compute_ledger_for_period(
        period,
        aws_peripheral=aws_peripheral,
        fnd_csm_root=fnd_csm_root,
        analytics_root=analytics_root,
    )
    upsert_ledger_row(ledger_row, fnd_csm_root=fnd_csm_root)
    rules = read_billing_rules(fnd_csm_root)
    invoices_changed: dict[str, bool] = {}
    for profile in load_grantee_directory(fnd_csm_root):
        msn = str(profile.get("msn_id", ""))
        if not msn:
            continue
        invoice = derive_invoice_for_grantee(
            msn, period, ledger_row, rules,
            fnd_csm_root=fnd_csm_root,
        )
        upsert_invoice_row(msn, invoice, fnd_csm_root=fnd_csm_root)
        invoices_changed[msn] = True
    return {
        "ok": True,
        "period": period,
        "ledger_changed": True,
        "invoices_changed": invoices_changed,
        "line_item_count": len(ledger_row.get("line_items") or []),
    }


# ---------------------------------------------------------------------
# Legacy back-compat — compute_tolling_row produces the v1 shape some
# operator scripts still call. Internally routes through refresh_all.
# ---------------------------------------------------------------------


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
    attribution = compute_bandwidth_cost(bandwidth, dt)
    bw_share = attribution["share"]
    bandwidth_cost = attribution["amount_value"]
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
