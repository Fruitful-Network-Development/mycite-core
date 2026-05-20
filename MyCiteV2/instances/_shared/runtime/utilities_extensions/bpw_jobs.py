"""ext_bpw_jobs — Brock's Pressure Washing job records (read-only).

The 42 customer job records live in operator territory at
`/srv/webapps/mycite/fnd/private/utilities/tools/bpw-jobs/job.<date>.<slug>.yaml`,
moved out of the public website tree where they had been leaking
customer PII via `/frontend/assets/`. This module loads and serves
them through the portal API.

Read-only surface for now — operator manages the YAMLs directly. A
mutation surface (add/edit/delete jobs from the dashboard) is a
follow-up workstream.
"""

from __future__ import annotations

import glob
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
    # Sort newest first by job.date then by filename (which carries
    # the date prefix as a secondary tiebreaker).
    def _key(r: dict[str, Any]) -> tuple[str, str]:
        job = r.get("job") if isinstance(r.get("job"), dict) else {}
        date = str(job.get("date") or "")
        return (date, str(r.get("_source_file", "")))
    rows.sort(key=_key, reverse=True)
    return rows


def jobs_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate quick-look stats from a job list — total jobs, total
    revenue, status counts, average price. The dashboard calls this
    for the KPI cards above the jobs table."""
    total = len(rows)
    revenue = 0.0
    statuses: dict[str, int] = {}
    paid_count = 0
    for r in rows:
        job = r.get("job") if isinstance(r.get("job"), dict) else {}
        pricing = r.get("pricing") if isinstance(r.get("pricing"), dict) else {}
        status = str(job.get("status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
        try:
            revenue += float(pricing.get("total") or 0)
        except (TypeError, ValueError):
            pass
        if pricing.get("paid"):
            paid_count += 1
    avg = (revenue / total) if total else 0.0
    return {
        "total_jobs": total,
        "total_revenue": round(revenue, 2),
        "average_price": round(avg, 2),
        "paid_count": paid_count,
        "status_counts": statuses,
    }
