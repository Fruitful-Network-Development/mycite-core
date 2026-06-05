"""ext_events — generic shared "events" leaflets (read + write).

This module generalizes the former bespoke BPW "Jobs" feature into a
shared ``event-job`` leaflet type so no single client dashboard is
special. Event leaflets live in the operator/runtime tree at::

    <webapps_root>/clients/_shared/site-core/events/
        <yyyy-mm-dd>.event-job.<client>.<name>.yaml

Each leaflet carries schema ``mycite.site_core.event_job.v1`` with an
``event_kind`` discriminator (``job`` today). The generic envelope is
promoted to the TOP LEVEL — ``client`` / ``id`` / ``date`` / ``status``
/ ``title`` / ``location`` / ``description`` / ``leaflet_url`` — so the
dashboard's flat event model reads/writes it directly. Job-kind extras
(``customer`` / ``home`` / ``tags`` / ``pricing`` / ``notes``) remain
nested and are consumed only by the BPW analytics.

Read surface:  ``list_events``, ``events_summary``, ``events_analytics``.
Write surface: ``save_event`` (create/update), ``delete_event``.

The aggregation logic (KPI strip, revenue-by-month, status / lead-source
/ tag breakdowns, IQR price distribution) is ported verbatim from the
old ``bpw_jobs`` module so BPW retains identical analytics after the
migration.

PII NOTE: event leaflets contain customer data and are RUNTIME state.
They are never tracked in git. Callers scope writes at the route layer.
"""

from __future__ import annotations

import glob
import os
import re
import tempfile
from collections import defaultdict
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

#: Schema identifier stamped on every event leaflet.
EVENT_SCHEMA = "mycite.site_core.event_job.v1"

#: The only event_kind implemented today. Future kinds (e.g. ``visit``,
#: ``inspection``) would reuse the same gallery + aggregation spine.
DEFAULT_EVENT_KIND = "job"


# --------------------------------------------------------------------
# Path resolution
# --------------------------------------------------------------------


def events_root(webapps_root: str | Path) -> Path:
    """Return the canonical events gallery dir under ``webapps_root``.

    ``<webapps_root>/clients/_shared/site-core/events``. The directory is
    NOT created here; use :func:`ensure_events_root` for that.
    """
    return Path(webapps_root) / "clients" / "_shared" / "site-core" / "events"


def ensure_events_root(webapps_root: str | Path) -> Path:
    """Resolve the events gallery dir and create it (and parents) if it
    does not yet exist. Returns the directory path."""
    root = events_root(webapps_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_yaml(path: Path) -> dict[str, Any] | None:
    """Lazy YAML import so callers that never touch events don't pay for
    the dependency."""
    try:
        import yaml
    except ImportError:
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


# --------------------------------------------------------------------
# Read surface
# --------------------------------------------------------------------


def list_events(
    webapps_root: str | Path,
    client: str | None = None,
) -> list[dict[str, Any]]:
    """Glob every ``*.event-job.*.yaml`` leaflet under the events gallery
    and return parsed dicts sorted by date descending.

    When ``client`` is given, only events whose top-level ``client``
    slug matches (case-insensitive) are returned — the per-grantee
    dashboard scopes its view this way. Returns ``[]`` when the gallery
    doesn't exist or YAML can't load. The source filename is appended as
    ``_source_file`` for the dashboard JS to render or link from.
    """
    root = events_root(webapps_root)
    if not root.exists():
        return []
    want = _client_slug(client) if client else None
    rows: list[dict[str, Any]] = []
    for path in sorted(glob.glob(str(root / "*.event-job.*.yaml"))):
        data = _load_yaml(Path(path))
        if data is None:
            continue
        if want is not None and _client_slug(data.get("client")) != want:
            continue
        data["_source_file"] = Path(path).name
        rows.append(data)

    def _key(r: dict[str, Any]) -> tuple[str, str]:
        date = str(r.get("date") or "")
        return (date, str(r.get("_source_file", "")))

    rows.sort(key=_key, reverse=True)
    return rows


def events_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate quick-look stats — total events, total revenue (from
    completed events only), average price, paid count, status counts.
    The dashboard surfaces this in the KPI band above the table."""
    total = len(rows)
    revenue = 0.0
    statuses: dict[str, int] = defaultdict(int)
    paid_count = 0
    pipeline = 0.0
    completed = 0
    for r in rows:
        pricing = r.get("pricing") if isinstance(r.get("pricing"), dict) else {}
        status = str(r.get("status") or "unknown")
        statuses[status] += 1
        try:
            total_amt = float(pricing.get("total") or 0)
        except (TypeError, ValueError):
            total_amt = 0.0
        if status == "completed":
            completed += 1
            revenue += total_amt
        elif status == "booked":
            pipeline += total_amt
        if pricing.get("paid"):
            paid_count += 1
    avg = (revenue / completed) if completed else 0.0
    return {
        # Generalized KPI keys. The legacy ``total_jobs`` / ``completed_jobs``
        # aliases are kept so existing dashboard JS keeps working through
        # the migration.
        "total_events": total,
        "completed_events": completed,
        "total_jobs": total,
        "completed_jobs": completed,
        "total_revenue": round(revenue, 2),
        "average_price": round(avg, 2),
        "paid_count": paid_count,
        "pipeline_amount": round(pipeline, 2),
        "status_counts": dict(statuses),
    }


# --------------------------------------------------------------------
# Analytics aggregator (ported verbatim from bpw_jobs)
# --------------------------------------------------------------------


def _quantile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation quantile (numpy/legacy-dashboard default)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    h = (len(sorted_values) - 1) * p
    lo = int(h)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (h - lo) * (sorted_values[hi] - sorted_values[lo])


def _service_distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-service price distribution from *single-service completed
    events* — the only subset where the event total is honestly
    attributable to one service. Returns Q1/median/Q3/IQR + Tukey fences
    + outliers for the dashboard's IQR plot.
    """
    bucket: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        pricing = r.get("pricing") if isinstance(r.get("pricing"), dict) else {}
        if str(r.get("status") or "") != "completed":
            continue
        tags = r.get("tags") if isinstance(r.get("tags"), list) else []
        # Single-service only: total attributable to one tag type.
        priced_tags = [t for t in tags if isinstance(t, dict) and t.get("type")]
        if len(priced_tags) != 1:
            continue
        try:
            total_amt = float(pricing.get("total") or 0)
        except (TypeError, ValueError):
            continue
        if total_amt <= 0:
            continue
        bucket[str(priced_tags[0]["type"])].append(total_amt)

    out: dict[str, dict[str, Any]] = {}
    for tag, values in bucket.items():
        values = sorted(values)
        n = len(values)
        q1 = _quantile(values, 0.25)
        median = _quantile(values, 0.5)
        q3 = _quantile(values, 0.75)
        iqr = q3 - q1
        fence_lo = q1 - 1.5 * iqr
        fence_hi = q3 + 1.5 * iqr
        outliers = [v for v in values if v < fence_lo or v > fence_hi]
        out[tag] = {
            "n": n,
            "min": values[0],
            "max": values[-1],
            "q1": round(q1, 2),
            "median": round(median, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "fence_lo": round(fence_lo, 2),
            "fence_hi": round(fence_hi, 2),
            "mean": round(sum(values) / n, 2),
            "values": values,
            "outliers": outliers,
        }
    return out


def events_analytics(
    webapps_root: str | Path,
    client: str | None = None,
) -> dict[str, Any]:
    """Richer aggregations for the dashboard's Analytics section.

    Reads + scopes the event leaflets via :func:`list_events` (so route
    handlers pass only ``webapps_root`` + ``client``), then surfaces:

      * revenue_by_month  — [{period, completed, revenue}] last 12 months
      * lead_sources      — [{key, count, completed_count, revenue}]
      * status_breakdown  — [{key, count}]
      * tag_types         — [{key, count, sum_total_across_events}]
      * price_distribution_by_service — see _service_distribution
      * repeat_customers  — count + share

    Tag totals double-count multi-tag events (each tag gets credit for
    the event's full price). The dashboard renders a note explaining
    this; the IQR plot uses single-service events only.
    """
    return aggregate_analytics(list_events(webapps_root, client=client))


def aggregate_analytics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure aggregation over already-loaded event rows. Split out from
    :func:`events_analytics` so tests (and the legacy bpw shim) can feed
    rows directly without touching disk."""
    revenue_by_month: dict[str, dict[str, float]] = defaultdict(
        lambda: {"completed": 0, "revenue": 0.0}
    )
    lead_buckets: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0, "completed_count": 0, "revenue": 0.0}
    )
    tag_buckets: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0, "sum_total": 0.0}
    )
    status_counts: dict[str, int] = defaultdict(int)
    repeat_count = 0

    for r in rows:
        customer = r.get("customer") if isinstance(r.get("customer"), dict) else {}
        pricing = r.get("pricing") if isinstance(r.get("pricing"), dict) else {}
        status = str(r.get("status") or "unknown")
        status_counts[status] += 1
        try:
            total_amt = float(pricing.get("total") or 0)
        except (TypeError, ValueError):
            total_amt = 0.0
        lead = str(customer.get("lead_source") or "unspecified")
        lead_buckets[lead]["count"] += 1
        if status == "completed":
            lead_buckets[lead]["completed_count"] += 1
            lead_buckets[lead]["revenue"] += total_amt
        if customer.get("is_repeat"):
            repeat_count += 1

        date_raw = r.get("date")
        if status == "completed" and date_raw:
            ymd = str(date_raw)[:7]
            revenue_by_month[ymd]["completed"] += 1
            revenue_by_month[ymd]["revenue"] += total_amt

        tags = r.get("tags") if isinstance(r.get("tags"), list) else []
        for t in tags:
            if not isinstance(t, dict) or not t.get("type"):
                continue
            key = str(t["type"])
            tag_buckets[key]["count"] += 1
            if status == "completed":
                tag_buckets[key]["sum_total"] += total_amt

    months = sorted(revenue_by_month.keys())[-12:]
    revenue_series = [
        {
            "period": m,
            "completed": int(revenue_by_month[m]["completed"]),
            "revenue": round(revenue_by_month[m]["revenue"], 2),
        }
        for m in months
    ]

    lead_sources = [
        {
            "key": k,
            "count": int(v["count"]),
            "completed_count": int(v["completed_count"]),
            "revenue": round(v["revenue"], 2),
        }
        for k, v in sorted(lead_buckets.items(), key=lambda kv: -kv[1]["count"])
    ]
    tag_types = [
        {
            "key": k,
            "count": int(v["count"]),
            "sum_total": round(v["sum_total"], 2),
        }
        for k, v in sorted(tag_buckets.items(), key=lambda kv: -kv[1]["count"])
    ]
    status_breakdown = [
        {"key": k, "count": v}
        for k, v in sorted(status_counts.items(), key=lambda kv: -kv[1])
    ]

    return {
        "revenue_by_month": revenue_series,
        "lead_sources": lead_sources,
        "status_breakdown": status_breakdown,
        "tag_types": tag_types,
        "price_distribution_by_service": _service_distribution(rows),
        "repeat_customers": {
            "count": repeat_count,
            "share": round(repeat_count / len(rows), 4) if rows else 0.0,
        },
    }


# --------------------------------------------------------------------
# CRUD writes — create / update / delete
# --------------------------------------------------------------------


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_CLIENT_SLUG_RE = re.compile(r"[^a-z0-9]+")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _slugify(value: object) -> str:
    """Filename-safe slug. Lowercase, replace non-alphanumeric runs with
    a single dot, strip leading/trailing dots. Used for the customer-name
    component of a leaflet filename."""
    s = _SLUG_RE.sub(".", str(value or "").strip().lower()).strip(".")
    return s or "unknown"


def _client_slug(value: object) -> str:
    """Normalize a client identifier into the filename component.

    Lowercase, drop apostrophes (so "Brock's" -> "brocks" rather than
    "brock_s"), then collapse remaining non-alphanumeric runs to a single
    underscore and strip leading/trailing underscores. Underscores (not
    dots) so the client component reads as one token (e.g.
    ``brocks_pressure_washing``) and is unambiguous against the
    dot-separated filename structure. Deriving from a grantee's label
    this way yields the same slug the migration stamps.
    """
    text = str(value or "").strip().lower()
    # Drop both straight and curly (U+2019) apostrophes before slugging.
    text = text.replace("'", "").replace("\u2019", "")
    s = _CLIENT_SLUG_RE.sub("_", text).strip("_")
    return s or "unknown"


def _filename_for(payload: dict[str, Any]) -> str:
    """Compute the canonical filename for an event payload.

    Convention: ``<YYYY-MM-DD>.event-<kind>.<client>.<name-slug>.yaml``,
    where the name component is derived from the generic ``title`` if
    present, falling back to the (job-kind) customer name and then the
    event ``id``. ``id``/``date`` are top-level on the reconciled shape.
    """
    customer = (
        payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    )
    date_part = str(payload.get("date") or _date.today().isoformat())[:10]
    client_part = _client_slug(payload.get("client"))
    name_part = _slugify(
        payload.get("title") or customer.get("name") or payload.get("id") or "untitled"
    )
    kind = _slugify(payload.get("event_kind") or DEFAULT_EVENT_KIND)
    return f"{date_part}.event-{kind}.{client_part}.{name_part}.yaml"


def _path_for_id(
    webapps_root: str | Path,
    event_id: str,
    client: str | None = None,
) -> Path | None:
    """Find the leaflet whose ``job.id`` matches ``event_id``. Walking the
    whole gallery is O(n) but n is small and the lookup is on-demand from
    the dashboard; not worth a separate index. When ``client`` is given,
    only that client's leaflets are considered (so one client can't
    address another's events by id)."""
    if not _ID_RE.match(str(event_id or "")):
        return None
    want = _client_slug(client) if client else None
    for path in sorted(
        glob.glob(str(events_root(webapps_root) / "*.event-job.*.yaml"))
    ):
        data = _load_yaml(Path(path))
        if data is None:
            continue
        if want is not None and _client_slug(data.get("client")) != want:
            continue
        if str(data.get("id") or "") == str(event_id):
            return Path(path)
    return None


def _next_event_id(webapps_root: str | Path) -> str:
    """Allocate the next sequential id following the existing YYYY-NNNN
    pattern (year-prefix + 4-digit counter). Uses the current UTC year
    and the max existing counter+1 across the whole gallery."""
    year = datetime.utcnow().year
    prefix = f"{year}-"
    max_seen = 0
    for path in sorted(
        glob.glob(str(events_root(webapps_root) / "*.event-job.*.yaml"))
    ):
        data = _load_yaml(Path(path))
        if data is None:
            continue
        cur = str(data.get("id") or "")
        if cur.startswith(prefix):
            try:
                max_seen = max(max_seen, int(cur.split("-", 1)[1]))
            except (IndexError, ValueError):
                pass
    return f"{prefix}{max_seen + 1:04d}"


def _coerce_number(value: object) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f


def normalize_payload(
    payload: dict[str, Any],
    *,
    webapps_root: str | Path,
    client: str | None = None,
) -> dict[str, Any]:
    """Coerce a UI payload into the on-disk leaflet shape.

    Accepts the dashboard's FLAT form (``event_id`` / ``date`` /
    ``status`` / ``title`` / ``location`` / ``description`` /
    ``leaflet_url``) and promotes the generic envelope to the TOP LEVEL
    (``id`` / ``date`` / ``status`` / ``title`` / ``location`` /
    ``description`` / ``leaflet_url``). The job-kind extras
    (``customer`` / ``home`` / ``tags`` / ``pricing`` / ``notes``) are
    still read from nested keys when present — BPW-migrated leaflets
    carry them and the analytics consume them.

    Stamps schema + event_kind + client, assigns a sequential id when
    missing, defaults date (today) + status ("booked"), and coerces
    numeric fields. ``client`` (the route-resolved grantee slug)
    overrides any client field in the body so a caller can't write into
    another client's namespace.
    """
    customer = dict(payload.get("customer") or {})
    home = dict(payload.get("home") or {})
    pricing = dict(payload.get("pricing") or {})
    tags_raw = payload.get("tags") or []
    notes = payload.get("notes") or payload.get("description") or ""

    # Top-level envelope. The dashboard posts ``event_id``; accept that
    # plus a bare ``id``. Default id (next sequential), date (today),
    # status ("booked").
    event_id = payload.get("id") or payload.get("event_id")
    if not event_id:
        event_id = _next_event_id(webapps_root)
    date = payload.get("date") or _date.today().isoformat()
    status = str(payload.get("status") or "booked")

    tags: list[dict[str, Any]] = []
    for t in tags_raw:
        if not isinstance(t, dict):
            continue
        kind = str(t.get("type") or "").strip()
        if not kind:
            continue
        entry: dict[str, Any] = {"type": kind}
        if t.get("coverage"):
            entry["coverage"] = str(t["coverage"])
        if t.get("detail"):
            entry["detail"] = str(t["detail"])
        entry["price"] = _coerce_number(t.get("price"))
        tags.append(entry)

    client_slug = _client_slug(
        client if client is not None else payload.get("client")
    )
    event_kind = str(payload.get("event_kind") or DEFAULT_EVENT_KIND)

    return {
        "schema": EVENT_SCHEMA,
        "event_kind": event_kind,
        "client": client_slug,
        "id": str(event_id),
        "date": str(date),
        "status": status,
        "title": str(payload.get("title") or ""),
        "location": str(payload.get("location") or ""),
        "description": str(payload.get("description") or notes or ""),
        "leaflet_url": payload.get("leaflet_url") or None,
        "customer": customer,
        "home": home,
        "tags": tags,
        "pricing": {
            "total": _coerce_number(pricing.get("total")),
            "paid": bool(pricing.get("paid")),
            "method": pricing.get("method") or None,
            "discount": pricing.get("discount") or "",
        },
        "notes": str(notes or ""),
    }


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write YAML via tempfile + rename so a partial write can't replace
    a good file."""
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def save_event(
    payload: dict[str, Any],
    *,
    webapps_root: str | Path,
    client: str | None = None,
) -> dict[str, Any]:
    """Create or update an event leaflet.

    Update semantics: if the payload ``id`` matches an existing leaflet
    (within ``client`` scope), the existing on-disk record is used as the
    base and the incoming payload is layered on top, so fields the
    dashboard's FLAT edit form omits — the nested job-kind extras
    (``customer`` / ``home`` / ``tags`` / ``pricing`` / ``notes``) the BPW
    analytics depend on — are PRESERVED rather than wiped. The flat
    envelope fields the form does send (date / status / title / location /
    description / leaflet_url) still win. If the canonical filename
    changes (date, client, or title/name edited) the old file is removed
    and the record written under the new name so disk layout stays
    consistent.

    Returns the normalized payload + the on-disk filename. Raises
    ``ValueError`` on invalid input.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    ensure_events_root(webapps_root)

    # On update, hydrate the incoming payload with the existing on-disk
    # leaflet so nested extras the flat form doesn't carry survive. The
    # incoming payload's keys override the existing ones; a present-but-
    # empty nested key in the payload (rare) is treated as no-override.
    event_id = payload.get("id") or payload.get("event_id")
    existing = (
        _path_for_id(webapps_root, str(event_id), client=client)
        if event_id
        else None
    )
    if existing is not None:
        base = _load_yaml(existing) or {}
        base.pop("_source_file", None)
        merged = dict(base)
        for key, value in payload.items():
            # Don't let an absent/empty nested extra clobber the stored one.
            if key in ("customer", "home", "tags", "pricing") and not value:
                continue
            merged[key] = value
        payload = merged

    normalized = normalize_payload(payload, webapps_root=webapps_root, client=client)
    event_id = str(normalized["id"])
    target_path = events_root(webapps_root) / _filename_for(normalized)
    if existing is not None and existing != target_path:
        try:
            existing.unlink()
        except OSError:
            pass
    _atomic_write_yaml(target_path, normalized)
    normalized["_source_file"] = target_path.name
    return normalized


def delete_event(
    event_id: str,
    *,
    webapps_root: str | Path,
    client: str | None = None,
) -> bool:
    """Remove the leaflet for ``event_id`` (within ``client`` scope when
    given). Returns ``True`` if a file was removed, ``False`` if no
    matching leaflet existed."""
    path = _path_for_id(webapps_root, event_id, client=client)
    if path is None:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True
