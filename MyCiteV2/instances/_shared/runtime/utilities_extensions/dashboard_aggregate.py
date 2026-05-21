"""dashboard_aggregate — payload builders for Home + Email dashboard tabs.

Pure functions that compose existing adapters into the JSON shapes the
per-client `/dashboard/` consumes. Keeps the portal's `app.py` thin —
each new route is ~15 lines once the heavy lifting lives here.

Adapters consumed (all already in production):

* ``MyCiteV2.packages.core.grantee.store.load_grantee_profile``
* ``MyCiteV2.instances._shared.runtime.utilities_extensions.tolling``
  (``read_tolling_snapshot``, ``bandwidth_share_for_grantee``,
  ``domains_for_grantee``, ``load_grantee_directory``)
* ``MyCiteV2.packages.adapters.sql.fnd_analytics_summary.MosDatumAnalyticsSummaryAdapter``
* ``MyCiteV2.packages.adapters.filesystem.newsletter_state.FilesystemNewsletterStateAdapter``
* ``MyCiteV2.packages.adapters.sql.fnd_email_deliverability.MosDatumEmailDeliverabilityAdapter``

The functions return dicts ready for ``jsonify(...)``; they do not call
``flask.request`` or other framework state. That means the same module
is unit-testable without spinning up the WSGI app.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import _as_text
from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
    bandwidth_share_for_grantee,
    domains_for_grantee,
    load_grantee_directory,
    read_tolling_snapshot,
)
from MyCiteV2.packages.adapters.sql._common import _rate


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _profile_for(msn_id: str, fnd_csm_root: str | Path) -> dict[str, Any] | None:
    for profile in load_grantee_directory(fnd_csm_root):
        if str(profile.get("msn_id", "")) == msn_id:
            return profile
    return None


def _count_subscribers_and_dispatches(
    domains: list[str],
    contacts_root: Path,
    *,
    period: tuple[date, date] | None = None,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Sum subscribed contacts + count dispatches in window across the
    grantee's domains. Returns (subscriber_count, dispatch_count,
    recent_dispatches[])."""
    subs = 0
    dispatch_count = 0
    recent: list[dict[str, Any]] = []
    for d in domains:
        path = contacts_root / f"newsletter.{d}.contacts.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for c in data.get("contacts") or []:
            if c.get("subscribed"):
                subs += 1
        for disp in data.get("dispatches") or []:
            completed_at = _as_text(disp.get("completed_at"))
            if not completed_at:
                continue
            if period:
                start, end = period
                # half-open window
                completed_d = completed_at[:10]
                if completed_d < start.isoformat() or completed_d >= end.isoformat():
                    continue
            dispatch_count += 1
            recent.append(disp)
    recent.sort(key=lambda x: _as_text(x.get("completed_at")), reverse=True)
    return subs, dispatch_count, recent


def _live_analytics_counts(
    *,
    domains: list[str],
    analytics_root: Path,
    period: tuple[date, date],
) -> tuple[int, int]:
    """Live-walk per-domain NDJSON shards over `period` and return
    (total_events, unique_visitors). Mirrors the logic in
    /__fnd/analytics/summary so Home quick-counts match the Analytics
    tab exactly.

    Window is half-open: [start, end). Bot events count toward total
    but not unique visitors (also matches the analytics route).
    """
    start_d, end_d = period
    months: list[str] = []
    y, m = start_d.year, start_d.month
    while (y, m) <= (end_d.year, end_d.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    total_events = 0
    visitors: set[str] = set()
    for domain in domains:
        for month in months:
            path = analytics_root / f"analytics.{domain}.events.{month}.ndjson"
            if not path.exists():
                continue
            try:
                fh = path.open("r", encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    occurred = _as_text(event.get("occurred_at_utc"))[:10]
                    # Inclusive on both ends — see analytics_summary
                    # route for the rationale (dashboard MTD/7d/30d
                    # presets set `to` to today; users expect today to
                    # count).
                    if occurred < start_d.isoformat() or occurred > end_d.isoformat():
                        continue
                    total_events += 1
                    if event.get("is_bot"):
                        continue
                    v = _as_text(event.get("visitor_cookie_id_hash"))
                    if v:
                        visitors.add(v)
    return total_events, len(visitors)


def _describe_domains_parallel(
    aws_peripheral: Any, domains: list[str],
) -> list[dict[str, Any]]:
    """Resolve SES/DKIM/MX status for each domain in parallel.

    Each call hits AWS (~200–500ms). With N domains the sequential
    version blocked the Home tab for N×latency; the executor caps
    fan-out at 8 so we don't open a new connection for every grantee
    that ever gets 100 domains.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _describe(d: str) -> dict[str, Any]:
        try:
            status = aws_peripheral.describe_domain_status(domain=d)
        except Exception:  # noqa: BLE001
            status = None
        if status is None:
            return {
                "domain": d,
                "ses_verified": None,
                "dkim_verified": None,
                "mx_ok": None,
            }
        return {
            "domain": d,
            "ses_verified": bool(status.get("ses_identity_verified")),
            "dkim_verified": bool(status.get("dkim_verified")),
            "mx_ok": bool(status.get("mx_present")),
        }

    if not domains:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(domains))) as pool:
        # map preserves input order so the dashboard renders domains in
        # the order the grantee profile declares.
        return list(pool.map(_describe, domains))


def _sum_tolled(snapshot: dict[str, Any], period_yyyy_mm: str) -> tuple[float, str]:
    """Return (subtotal, currency) for the snapshot row matching `period_yyyy_mm`,
    or (0, "") when no row exists yet."""
    monthly = snapshot.get("monthly") or []
    for row in monthly:
        if str(row.get("period") or "") == period_yyyy_mm:
            try:
                amount = float(row.get("subtotal") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            return amount, _as_text(row.get("currency"))
    return 0.0, ""


# ---------------------------------------------------------------------
# Home tab
# ---------------------------------------------------------------------


def build_grantee_summary(
    *,
    msn_id: str,
    period: tuple[date, date],
    fnd_csm_root: str | Path,
    aws_peripheral,
    private_dir: Path,
) -> dict[str, Any]:
    """Compose the Home-tab payload."""
    profile = _profile_for(msn_id, fnd_csm_root) or {}
    domains = domains_for_grantee(msn_id, fnd_csm_root)
    start_d, end_d = period

    total_events, unique_visitors = _live_analytics_counts(
        domains=domains,
        analytics_root=private_dir / "utilities" / "tools" / "analytics",
        period=(start_d, end_d),
    )

    bw = bandwidth_share_for_grantee(msn_id, start_d, end_d)
    bandwidth_gb = float(bw.get("bytes_sent", 0)) / (1024 ** 3)

    contacts_root = private_dir / "utilities" / "tools" / "aws-csm" / "newsletter"
    subs, dispatches, _ = _count_subscribers_and_dispatches(
        domains, contacts_root, period=period,
    )

    snap = read_tolling_snapshot(msn_id, fnd_csm_root)
    yyyy_mm = start_d.strftime("%Y-%m")
    tolled_amount, currency = _sum_tolled(snap, yyyy_mm)

    # Field rename: peripheral DomainStatus uses ses_identity_verified +
    # mx_present; dashboard surface uses ses_verified + mx_ok.
    identity_status = _describe_domains_parallel(aws_peripheral, domains)

    return {
        "grantee": {
            "msn_id":     _as_text(profile.get("msn_id") or msn_id),
            "short_name": _as_text(profile.get("short_name")),
            "label":      _as_text(profile.get("label")),
            "domains":    [str(d) for d in domains],
        },
        "period": {"from": start_d.isoformat(), "to": end_d.isoformat()},
        "quick_counts": {
            "total_events":      int(total_events),
            "unique_visitors":   int(unique_visitors),
            "bandwidth_gb":      round(bandwidth_gb, 4),
            "subscribers":       int(subs),
            "dispatches":        int(dispatches),
            "tolled_amount_usd": round(float(tolled_amount), 4),
        },
        "identity_status": identity_status,
        "currency": currency,
    }


# ---------------------------------------------------------------------
# Email tab
# ---------------------------------------------------------------------


def build_email_dashboard(
    *,
    msn_id: str,
    period: tuple[date, date],
    fnd_csm_root: str | Path,
    private_dir: Path,
    deliverability_adapter,
    aws_peripheral,
) -> dict[str, Any]:
    """Compose the Email-tab payload.

    When the deliverability adapter has no MOS document yet (SES event
    sink not deployed), the ``deliverability`` block sets
    ``available=False`` rather than reporting zeros as real metrics.
    """
    profile = _profile_for(msn_id, fnd_csm_root) or {}
    domains = domains_for_grantee(msn_id, fnd_csm_root)
    start_d, end_d = period
    contacts_root = private_dir / "utilities" / "tools" / "aws-csm" / "newsletter"

    # Single pass per contacts file: contact counts + dispatch slice.
    subscribed = 0
    unsubscribed = 0
    recent_contacts: list[dict[str, Any]] = []
    dispatches_all: list[dict[str, Any]] = []
    for d in domains:
        path = contacts_root / f"newsletter.{d}.contacts.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for c in data.get("contacts") or []:
            if c.get("subscribed"):
                subscribed += 1
            else:
                unsubscribed += 1
            recent_contacts.append({**c, "_domain": d})
        for disp in data.get("dispatches") or []:
            completed = _as_text(disp.get("completed_at"))[:10]
            if completed and start_d.isoformat() <= completed < end_d.isoformat():
                dispatches_all.append(disp)
    recent_contacts.sort(
        key=lambda c: _as_text(c.get("unsubscribed_at") or c.get("subscribed_at") or c.get("created_at")),
        reverse=True,
    )
    dispatches_all.sort(key=lambda x: _as_text(x.get("completed_at")), reverse=True)
    dispatches = [
        {
            "dispatch_id":  _as_text(d.get("dispatch_id")),
            "completed_at": _as_text(d.get("completed_at")),
            "subject":      _as_text(d.get("subject")),
            "target_count": int(d.get("target_count") or 0),
            "sent_count":   int(d.get("sent_count") or 0),
        }
        for d in dispatches_all[:20]
    ]

    # Forward map — one aws-csm.<short>.<user>.json per mailbox. Scope
    # by grantee short_name; one grantee may own multiple tenant tokens
    # (e.g. CVCC owns both `cvcc.*` and `cvccboard.*`), so include any
    # token whose identity.domain falls in the grantee's domain list.
    forward_map: list[dict[str, Any]] = []
    aws_csm_root = private_dir / "utilities" / "tools" / "aws-csm"
    domain_set = {d.lower() for d in domains}
    short = str(profile.get("short_name") or "").lower()
    if aws_csm_root.exists():
        patterns = [f"aws-csm.{short}.*.json"] if short else []
        # Fallback: also consider tokens whose identity.domain is in the
        # grantee's domain list but whose short token doesn't match
        # (CVCC's `cvccboard.*` files). One extra glob to find them.
        patterns.append("aws-csm.*.json")
        seen: set[Path] = set()
        for pattern in patterns:
            for path in sorted(aws_csm_root.glob(pattern)):
                if path in seen or path.name.startswith("aws-csm-domain."):
                    continue
                seen.add(path)
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                identity = data.get("identity") or {}
                if _as_text(identity.get("domain")).lower() not in domain_set:
                    continue
                alias = _as_text(identity.get("send_as_email"))
                dest  = _as_text(identity.get("operator_inbox_target"))
                if alias and dest:
                    forward_map.append({"alias": alias, "send_as_email": dest})
    forward_map.sort(key=lambda r: r["alias"])

    # Allowed submitters — per-domain newsletter-admin profiles carry
    # `allowed_submitters` (the list authorized to email news@<domain>).
    # Falls back to `selected_author_address` so the grantee always sees
    # *something* — that matches the runtime behavior in app.py's
    # inbound-capture allowlist resolution.
    newsletter_admin_root = private_dir / "utilities" / "tools" / "newsletter-admin"
    allowed_submitters: list[dict[str, Any]] = []
    if newsletter_admin_root.exists():
        for d in domains:
            path = newsletter_admin_root / f"newsletter-admin.{d}.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            explicit = [
                _as_text(e).lower()
                for e in (data.get("allowed_submitters") or [])
                if _as_text(e)
            ]
            entries = explicit or (
                [_as_text(data.get("selected_author_address")).lower()]
                if _as_text(data.get("selected_author_address")) else []
            )
            for email in entries:
                allowed_submitters.append({
                    "email": email,
                    "domain": d,
                    "source": "allowed_submitters" if explicit else "selected_author_address",
                })
    allowed_submitters.sort(key=lambda r: (r["domain"], r["email"]))

    # Sender identity — pull from grantee.aws_ses + live SES status.
    aws_ses = profile.get("aws_ses") or {}
    sender_address = _as_text(aws_ses.get("from_address") or aws_ses.get("identity"))
    configset = _as_text(aws_ses.get("configuration_set"))
    ses_verified = None
    dkim_verified = None
    primary_domain = domains[0] if domains else ""
    if primary_domain:
        try:
            status = aws_peripheral.describe_domain_status(domain=primary_domain) or {}
            ses_verified  = bool(status.get("ses_identity_verified"))
            dkim_verified = bool(status.get("dkim_verified"))
        except Exception:  # noqa: BLE001
            pass

    # Deliverability (period-filtered). Aggregate across domains.
    period_iso = (start_d.isoformat(), end_d.isoformat())
    deliverability: dict[str, Any] = {
        "available": False,
        "period": {"from": period_iso[0], "to": period_iso[1]},
        "send_count": 0, "delivery_count": 0,
        "bounce_count": 0, "complaint_count": 0,
        "open_count": 0, "click_count": 0,
        "bounce_rate": 0.0, "complaint_rate": 0.0,
    }
    for d in domains:
        rollup = deliverability_adapter.load_rollup(domain=d, period=period_iso)
        if rollup.get("available"):
            deliverability["available"] = True
            for k in ("send_count", "delivery_count", "bounce_count",
                      "complaint_count", "open_count", "click_count"):
                deliverability[k] += int(rollup.get(k, 0))
    send = deliverability["send_count"]
    deliverability["bounce_rate"]    = _rate(deliverability["bounce_count"],    send)
    deliverability["complaint_rate"] = _rate(deliverability["complaint_count"], send)

    return {
        "grantee": {
            "msn_id":     _as_text(profile.get("msn_id") or msn_id),
            "short_name": _as_text(profile.get("short_name")),
            "label":      _as_text(profile.get("label")),
            "domains":    [str(d) for d in domains],
        },
        "period": {"from": period_iso[0], "to": period_iso[1]},
        "identity": {
            "sender_address": sender_address,
            "configset":      configset,
            "ses_verified":   ses_verified,
            "dkim_verified":  dkim_verified,
        },
        "contacts": {
            "subscribed_count":   subscribed,
            "unsubscribed_count": unsubscribed,
            "recent":             recent_contacts[:25],
        },
        "dispatches":    dispatches,
        "forward_map":   forward_map,
        "allowed_submitters": allowed_submitters,
        "deliverability": deliverability,
    }


__all__ = [
    "build_grantee_summary",
    "build_email_dashboard",
]
