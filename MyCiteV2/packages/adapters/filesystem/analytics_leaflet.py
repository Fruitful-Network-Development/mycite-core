"""Monthly analytics *leaflet* persistence — the canonical analytics store.

One YAML file per site per month, shaped ``visitors → sessions → events``
(assembled by ``MyCiteV2.packages.core.analytics.leaflet_model`` and consumed by
the dashboard + the operator extension):

    <webapps_root>/clients/_shared/site-core/analytics/
        <YYYY-MM>-00.record-analytics.<entity>-website.<month>_analytics.yaml

This REPLACES the per-domain raw NDJSON log — there is no second store behind
it. This adapter is **pure persistence**: it loads/saves YAML, lists periods,
and offers a flock-guarded read-modify-write hook (``locked_update``). It holds
NO analytics semantics — the merge/coalesce orchestration lives in the runtime
composition layer (the ``analytics_ingest`` module) where importing the core
model is allowed, keeping this adapter free of business logic per the
filesystem-adapter boundary contract.

Concurrency: two gunicorn workers may write the same month, so every
read-modify-write takes an exclusive ``flock`` on a sibling ``.lock`` file and
replaces the leaflet atomically (temp + ``os.replace``).

PII NOTE: like the contact roster, the leaflet holds runtime visitor data and
is an untracked artifact — never commit a real leaflet (the webapps
``site-core/.gitignore`` enforces this; only ``*.example.*`` is tracked).
"""

from __future__ import annotations

import fcntl
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .contact_leaflet import _entity_slug

_log = logging.getLogger("mycite.portal_host")

# Mirrors leaflet_model.ANALYTICS_RECORD_SCHEMA (kept as a literal here so this
# adapter imports no core module). Used only to recognise a well-formed leaflet.
ANALYTICS_RECORD_SCHEMA = "mycite.site_core.analytics_record.v1"

# Soft guard: warn if a month leaflet grows past this on disk.
LARGE_LEAFLET_BYTES = 4 * 1024 * 1024

_MONTHS = (
    "", "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)


def period_of(iso: str) -> str:
    """``YYYY-MM`` from an ISO timestamp; ``""`` if unparseable."""
    token = (iso or "").strip()
    if len(token) >= 7 and token[4] == "-" and token[:4].isdigit() and token[5:7].isdigit():
        return token[:7]
    return ""


def prev_period(period: str) -> str:
    parts = period.split("-")
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return ""
    y, m = int(parts[0]), int(parts[1])
    m -= 1
    if m == 0:
        m, y = 12, y - 1
    return f"{y:04d}-{m:02d}"


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write ``text`` to ``path`` (temp in the same dir + os.replace).
    Shared by the analytics + campaign leaflet stores so a torn write can never
    read back as a truncated leaflet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _month_token(period: str) -> str:
    parts = period.split("-")
    if len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 12:
        return _MONTHS[int(parts[1])]
    return "month"


def _analytics_dir_for(private_dir: str | Path, webapps_root: str | Path | None) -> Path:
    """Resolve the analytics-leaflet directory from a private_dir.

    Mirrors ``contact_leaflet._contacts_dir_for``: live layout is
    ``<webapps_root>/mycite/<instance>/private`` and the leaflets live at
    ``<webapps_root>/clients/_shared/site-core/analytics``. Tests pass an
    explicit ``webapps_root`` or fall back to anchoring under ``private_dir``.
    """
    path = Path(private_dir)
    parts = path.resolve().parts
    leaf = ("clients", "_shared", "site-core", "analytics")
    if len(parts) >= 4 and parts[-1] == "private" and parts[-3] == "mycite":
        return Path(*parts[:-3]).joinpath(*leaf)
    if webapps_root is not None:
        return Path(webapps_root).joinpath(*leaf)
    return path.joinpath(*leaf)


class _FileLock:
    """Exclusive flock on a sibling ``.lock`` file (the leaflet itself is
    replaced atomically, so locking it directly would race the inode swap)."""

    def __init__(self, target: Path) -> None:
        self._lock_path = target.with_suffix(target.suffix + ".lock")
        self._fd: int | None = None

    def __enter__(self) -> _FileLock:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


class AnalyticsLeafletStore:
    """Read/write the monthly analytics leaflets for one instance."""

    def __init__(
        self,
        *,
        private_dir: str | Path,
        webapps_root: str | Path | None = None,
    ) -> None:
        self._private_dir = Path(private_dir)
        self._analytics_dir = _analytics_dir_for(private_dir, webapps_root)

    @property
    def analytics_dir(self) -> Path:
        return self._analytics_dir

    def leaflet_path(self, entity: str, period: str) -> Path:
        slug = _entity_slug(entity)
        fname = (
            f"{period}-00.record-analytics.{slug}-website."
            f"{_month_token(period)}_analytics.yaml"
        )
        return self._analytics_dir / fname

    def available_periods(self, entity: str) -> list[str]:
        slug = _entity_slug(entity)
        if not self._analytics_dir.is_dir():
            return []
        owner = f"{slug}-website."
        out: list[str] = []
        for p in self._analytics_dir.iterdir():
            name = p.name
            if ".record-analytics." in name and owner in name and name.endswith(".yaml"):
                period = name.split(".", 1)[0]  # "YYYY-MM-00"
                if period.endswith("-00") and len(period) == 10:
                    out.append(period[:7])
        return sorted(set(out))

    def periods_in_range(self, entity: str, from_iso: str, to_iso: str) -> list[str]:
        """Available ``YYYY-MM`` periods whose month overlaps the inclusive
        ``[from, to]`` range. Month granularity: a leaflet is one month, so any
        range that touches any day of a month includes that whole month. Empty
        bound → open on that side. Returned ascending."""
        periods = self.available_periods(entity)
        if not periods:
            return []
        lo = period_of(from_iso)
        hi = period_of(to_iso)
        if lo and hi and lo > hi:
            lo, hi = hi, lo
        return [p for p in periods if (not lo or p >= lo) and (not hi or p <= hi)]

    # -- low-level yaml --------------------------------------------------------

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning("analytics_leaflet_parse_failed path=%s", path, exc_info=True)
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def _write_yaml(self, path: Path, payload: dict[str, Any]) -> None:
        text = yaml.safe_dump(
            payload, sort_keys=False, allow_unicode=True, default_flow_style=False
        )
        if len(text) > LARGE_LEAFLET_BYTES:
            _log.warning("analytics_leaflet_large path=%s bytes=%d", path, len(text))
        atomic_write_text(path, text)

    # -- month API -------------------------------------------------------------

    def load_month(self, entity: str, period: str) -> dict[str, Any]:
        """Return the parsed leaflet dict, or ``{}`` when absent / malformed."""
        payload = self._read_yaml(self.leaflet_path(entity, period))
        if payload.get("schema") == ANALYTICS_RECORD_SCHEMA and isinstance(
            payload.get("visitors"), list
        ):
            return payload
        return {}

    def save_month(self, entity: str, month: dict[str, Any]) -> None:
        self._write_yaml(self.leaflet_path(entity, month["period"]), month)

    def read_range(self, entity: str, periods: list[str]) -> list[dict[str, Any]]:
        return [self.load_month(entity, p) for p in periods if p]

    def locked_update(
        self,
        entity: str,
        period: str,
        mutate: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """flock the month leaflet, load it, hand the dict to ``mutate``, and
        atomically write whatever ``mutate`` returns. ``mutate`` carries the
        analytics semantics (it lives in the runtime layer); this method owns
        only the lock + load + atomic write. (leaflet_path/load_month/save_month
        each apply _entity_slug, which is idempotent, so entity passes through.)
        """
        target = self.leaflet_path(entity, period)
        with _FileLock(target):
            current = self.load_month(entity, period)
            month = mutate(current)
            self.save_month(entity, month)
            return month


__all__ = [
    "ANALYTICS_RECORD_SCHEMA",
    "AnalyticsLeafletStore",
    "period_of",
    "prev_period",
]
