"""ext_bpw_jobs — backward-compat shim over the generic events module.

The bespoke BPW "Jobs" feature has been hard-migrated into the shared
``events`` leaflet type (see :mod:`events`). The portal API now serves
BPW through the generic ``/__fnd/events/*`` routes; all aggregation logic
lives in ``events.py`` and operates on ``event-job`` leaflets under
``<webapps_root>/clients/_shared/site-core/events/``.

This module is retained only as a thin compatibility shim:

  * ``jobs_summary`` / ``jobs_analytics`` delegate to the events module's
    pure aggregators so BPW analytics stay byte-for-byte identical.
  * ``list_jobs`` / ``save_job`` / ``delete_job`` / ``_filename_for`` are
    the *legacy job-tree* readers/writers over the pre-migration corpus
    at ``/srv/webapps/mycite/fnd/private/utilities/tools/bpw-jobs/``
    (``job.<date>.<slug>.yaml``). They are used only by the one-shot
    xlsx importer and by the migration script that reads the source
    corpus. New code must use the ``events`` functions instead.
"""

from __future__ import annotations

import glob
import os
import re
import tempfile
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.utilities_extensions import events as _events

_DEFAULT_BPW_JOBS_ROOT = Path(
    "/srv/webapps/mycite/fnd/private/utilities/tools/bpw-jobs"
)

# Re-exported pure helpers so old internal imports keep resolving.
_slugify = _events._slugify
_coerce_number = _events._coerce_number
_quantile = _events._quantile
_service_distribution = _events._service_distribution
_load_yaml = _events._load_yaml

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


# --------------------------------------------------------------------
# Pure aggregators (delegate to the events module verbatim)
# --------------------------------------------------------------------


def jobs_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Deprecated alias for :func:`events.events_summary`."""
    return _events.events_summary(rows)


def jobs_analytics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Deprecated alias for the pure aggregation in the events module."""
    return _events.aggregate_analytics(rows)


# --------------------------------------------------------------------
# Legacy job-tree readers/writers (pre-migration corpus only)
# --------------------------------------------------------------------


def list_jobs(
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> list[dict[str, Any]]:
    """Read every ``job.*.yaml`` under the legacy jobs root, newest
    first, each tagged with ``_source_file``."""
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
        return (str(job.get("date") or ""), str(r.get("_source_file", "")))

    rows.sort(key=_key, reverse=True)
    return rows


def _filename_for(payload: dict[str, Any]) -> str:
    """Legacy filename convention: ``job.<YYYY-MM-DD>.<customer-slug>.yaml``."""
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    customer = (
        payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    )
    date_part = str(job.get("date") or _date.today().isoformat())[:10]
    name_part = _slugify(customer.get("name") or job.get("id") or "untitled")
    return f"job.{date_part}.{name_part}.yaml"


def _path_for_id(
    job_id: str,
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> Path | None:
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
    """Coerce a UI payload into the legacy on-disk job shape (no schema /
    client / event_kind stamp)."""
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


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
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


def save_job(
    payload: dict[str, Any],
    *,
    jobs_root: str | Path = _DEFAULT_BPW_JOBS_ROOT,
) -> dict[str, Any]:
    """Create/update a legacy job YAML. Used only by the one-shot xlsx
    importer; the live portal writes event leaflets via ``events``."""
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
    """Remove the legacy job YAML for ``job_id``."""
    path = _path_for_id(job_id, jobs_root)
    if path is None:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True
