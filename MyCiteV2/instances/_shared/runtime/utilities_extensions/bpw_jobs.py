"""ext_bpw_jobs — Brock's Pressure Washing job records (read + write).

The customer job records live in operator territory at
`/srv/webapps/mycite/fnd/private/utilities/tools/bpw-jobs/job.<date>.<slug>.yaml`,
moved out of the public website tree where they had been leaking
customer PII via `/frontend/assets/`. This module loads and serves
them through the portal API.

Read surface: ``list_jobs``, ``jobs_summary``, ``jobs_analytics``.
Write surface: ``save_job`` (create/update), ``delete_job``.

CRUD writes are scoped at the route layer to BPW only; this module
trusts the caller.
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

_DEFAULT_BPW_JOBS_ROOT = Path(
    "/srv/webapps/mycite/fnd/private/utilities/tools/bpw-jobs"
)


def _load_yaml(path: Path) -> dict[str, Any] | None:
    """Lazy YAML import so callers that never touch jobs don't pay
    for the dependency."""
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


def list_jobs(
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> list[dict[str, Any]]:
    """Glob every job.*.yaml under the jobs root and return parsed
    dicts sorted by date descending. Returns [] when the dir doesn't
    exist or YAML can't load. Source filename appended as
    `_source_file` for the dashboard JS to render or link from."""
    root = Path(jobs_root)
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(glob.glob(str(root / "job.*.yaml"))):
        data = _load_yaml(Path(path))
        if data is None:
            continue
        data["_source_file"] = Path(path).name
        rows.append(data)
    def _key(r: dict[str, Any]) -> tuple[str, str]:
        job = r.get("job") if isinstance(r.get("job"), dict) else {}
        date = str(job.get("date") or "")
        return (date, str(r.get("_source_file", "")))
    rows.sort(key=_key, reverse=True)
    return rows


def jobs_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate quick-look stats — total jobs, total revenue (from
    completed jobs only), average price, paid count, status counts.
    The dashboard surfaces this in the KPI band above the table."""
    total = len(rows)
    revenue = 0.0
    statuses: dict[str, int] = defaultdict(int)
    paid_count = 0
    pipeline = 0.0
    completed = 0
    for r in rows:
        job = r.get("job") if isinstance(r.get("job"), dict) else {}
        pricing = r.get("pricing") if isinstance(r.get("pricing"), dict) else {}
        status = str(job.get("status") or "unknown")
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
        "total_jobs": total,
        "completed_jobs": completed,
        "total_revenue": round(revenue, 2),
        "average_price": round(avg, 2),
        "paid_count": paid_count,
        "pipeline_amount": round(pipeline, 2),
        "status_counts": dict(statuses),
    }


# --------------------------------------------------------------------
# Analytics aggregator
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
    jobs* — the only subset where the job total is honestly
    attributable to one service. Returns Q1/median/Q3/IQR + Tukey
    fences + outliers for the dashboard's IQR plot.
    """
    bucket: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        job = r.get("job") if isinstance(r.get("job"), dict) else {}
        pricing = r.get("pricing") if isinstance(r.get("pricing"), dict) else {}
        if str(job.get("status") or "") != "completed":
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


def jobs_analytics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Richer aggregations for the dashboard's Job Analytics section.

    Surfaces:
      * revenue_by_month  — [{period, completed, revenue}] last 12 months
      * lead_sources      — [{key, count, completed_count, revenue}]
      * status_breakdown  — [{key, count}]
      * tag_types         — [{key, count, sum_total_across_jobs}]
      * price_distribution_by_service — see _service_distribution
      * repeat_customers  — count + share

    Tag totals double-count multi-tag jobs (each tag gets credit for
    the job's full price). The dashboard renders a note explaining
    this; the IQR plot uses single-service jobs only.
    """
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
        job = r.get("job") if isinstance(r.get("job"), dict) else {}
        customer = r.get("customer") if isinstance(r.get("customer"), dict) else {}
        pricing = r.get("pricing") if isinstance(r.get("pricing"), dict) else {}
        status = str(job.get("status") or "unknown")
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

        date_raw = job.get("date")
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
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _slugify(value: str) -> str:
    """Filename-safe slug. Lowercase, replace non-alphanumeric runs
    with a single dot, strip leading/trailing dots."""
    s = _SLUG_RE.sub(".", str(value or "").strip().lower()).strip(".")
    return s or "unknown"


def _filename_for(payload: dict[str, Any]) -> str:
    """Compute the canonical filename for a job payload.

    Convention: job.<YYYY-MM-DD>.<customer-slug>.yaml — matches the
    existing on-disk corpus.
    """
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    date_part = str(job.get("date") or _date.today().isoformat())[:10]
    name_part = _slugify(customer.get("name") or job.get("id") or "untitled")
    return f"job.{date_part}.{name_part}.yaml"


def _path_for_id(
    job_id: str,
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> Path | None:
    """Find the YAML file whose `job.id` matches `job_id`. Walking the
    whole directory is O(n) but n is small (~50) and the lookup is
    on-demand from the dashboard; not worth a separate index."""
    if not _ID_RE.match(str(job_id or "")):
        return None
    for path in sorted(glob.glob(str(Path(jobs_root) / "job.*.yaml"))):
        data = _load_yaml(Path(path))
        if data is None:
            continue
        job = data.get("job") if isinstance(data.get("job"), dict) else {}
        if str(job.get("id") or "") == str(job_id):
            return Path(path)
    return None


def _next_job_id(jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT) -> str:
    """Allocate the next sequential id following the existing
    YYYY-NNNN pattern (year-prefix + 4-digit counter). Uses the
    current UTC year and the max existing counter+1."""
    year = datetime.utcnow().year
    prefix = f"{year}-"
    max_seen = 0
    for path in sorted(glob.glob(str(Path(jobs_root) / "job.*.yaml"))):
        data = _load_yaml(Path(path))
        if data is None:
            continue
        job = data.get("job") if isinstance(data.get("job"), dict) else {}
        cur = str(job.get("id") or "")
        if cur.startswith(prefix):
            try:
                max_seen = max(max_seen, int(cur.split("-", 1)[1]))
            except (IndexError, ValueError):
                pass
    return f"{prefix}{max_seen + 1:04d}"


def _normalize_payload(
    payload: dict[str, Any],
    *,
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> dict[str, Any]:
    """Coerce a UI payload into the on-disk YAML shape — assign an id
    if missing, coerce numeric fields, drop unknown top-level keys."""
    job = dict(payload.get("job") or {})
    customer = dict(payload.get("customer") or {})
    home = dict(payload.get("home") or {})
    pricing = dict(payload.get("pricing") or {})
    tags_raw = payload.get("tags") or []
    notes = payload.get("notes") or ""

    if not job.get("id"):
        job["id"] = _next_job_id(jobs_root)
    if not job.get("date"):
        job["date"] = _date.today().isoformat()
    job["status"] = str(job.get("status") or "booked")

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

    return {
        "job": job,
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


def _coerce_number(value: object) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write YAML via tempfile + rename so a partial write can't
    replace a good file."""
    import yaml  # imported here (call site already implicitly requires yaml)
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


def save_job(
    payload: dict[str, Any],
    *,
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> dict[str, Any]:
    """Create or update a job YAML.

    Update semantics: if `payload.job.id` matches an existing file
    *and* the date/customer haven't moved (so the canonical filename
    is unchanged), overwrite in place. If the canonical filename
    changes (date or customer name edited), remove the old file and
    write under the new name so disk layout stays consistent.

    Returns the normalized payload + the on-disk filename. Raises
    ValueError on invalid input.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    normalized = _normalize_payload(payload, jobs_root=jobs_root)
    job_id = str(normalized["job"]["id"])
    target_path = Path(jobs_root) / _filename_for(normalized)
    existing = _path_for_id(job_id, jobs_root)
    if existing is not None and existing != target_path:
        try:
            existing.unlink()
        except OSError:
            pass
    _atomic_write_yaml(target_path, normalized)
    normalized["_source_file"] = target_path.name
    return normalized


def delete_job(
    job_id: str,
    *,
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> bool:
    """Remove the YAML for `job_id`. Returns True if a file was
    removed, False if no matching file existed."""
    path = _path_for_id(job_id, jobs_root)
    if path is None:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True
