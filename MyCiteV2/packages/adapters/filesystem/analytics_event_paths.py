"""Path resolver for the per-domain analytics event NDJSON.

History: through Phase 18a the events lived under
``/srv/webapps/clients/<domain>/analytics/events/<YYYY-MM>.ndjson``. That
location conflated grantee operational data with the static web frontend
and put live writes inside the directory served by nginx. As of
2026-05-16 the canonical location is per-grantee files under the FND
deployed-utilities tree:

    <private>/utilities/tools/analytics/analytics.<domain>.events.<YYYY-MM>.ndjson

Resolution precedence for ``analytics_root``:

    1. Explicit ``analytics_root`` constructor argument.
    2. ``MYCITE_ANALYTICS_ROOT`` env var.
    3. ``DEFAULT_ANALYTICS_ROOT`` — the legacy webapps path, only used as
       a last-resort fallback when neither (1) nor (2) is set. New
       deployments should always pass an explicit root.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_ANALYTICS_ROOT = Path("/srv/repo/mycite-core/deployed/fnd/private/utilities/tools/analytics")
LEGACY_WEBAPPS_ROOT = Path("/srv/webapps")  # only for legacy resolver behavior
DEFAULT_WEBAPPS_ROOT = LEGACY_WEBAPPS_ROOT  # back-compat for any external import
YEAR_MONTH_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}$")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_domain(domain: object) -> str:
    token = _as_text(domain).lower()
    if not token or "/" in token or "\\" in token or ".." in token:
        raise ValueError("analytics domain must be a plain domain name")
    return token


def _normalize_year_month(year_month: object) -> str:
    token = _as_text(year_month)
    if not YEAR_MONTH_PATTERN.match(token):
        raise ValueError("analytics year_month must use YYYY-MM")
    return token


@dataclass(frozen=True)
class AnalyticsEventPathResolution:
    domain: str
    year_month: str
    analytics_root: Path
    events_file: Path
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "year_month": self.year_month,
            "analytics_root": str(self.analytics_root),
            "events_file": str(self.events_file),
            "warnings": list(self.warnings),
        }


def _events_filename(domain: str, year_month: str) -> str:
    """Flat naming: analytics.<domain>.events.<YYYY-MM>.ndjson."""
    return f"analytics.{domain}.events.{year_month}.ndjson"


class AnalyticsEventPathResolver:
    """Resolves where to read/write per-domain event NDJSON.

    Construct with one of:

        AnalyticsEventPathResolver(analytics_root=path)   # explicit
        AnalyticsEventPathResolver()                       # env / default

    Callers that still pass ``webapps_root`` (legacy API) get the historic
    ``<webapps>/clients/<domain>/analytics`` shape so the migration can
    flip writers one at a time. New code must use ``analytics_root``.
    """

    def __init__(
        self,
        analytics_root: str | Path | None = None,
        *,
        webapps_root: str | Path | None = None,
    ) -> None:
        if analytics_root is not None:
            self._analytics_root = Path(analytics_root)
            self._legacy_webapps_root: Path | None = None
        elif webapps_root is not None:
            # Legacy path: events live under <webapps>/clients/<domain>/analytics/events.
            self._analytics_root = None  # signal legacy mode
            self._legacy_webapps_root = Path(webapps_root)
        else:
            env_value = _as_text(os.environ.get("MYCITE_ANALYTICS_ROOT"))
            self._analytics_root = Path(env_value) if env_value else DEFAULT_ANALYTICS_ROOT
            self._legacy_webapps_root = None

    @property
    def analytics_root(self) -> Path:
        if self._analytics_root is not None:
            return self._analytics_root
        # Legacy mode: there's no single root, only per-domain ones.
        # Return the webapps root for diagnostic display.
        return self._legacy_webapps_root or DEFAULT_ANALYTICS_ROOT

    def domain_events_dir(self, domain: str) -> Path:
        """Directory that holds *.ndjson for one domain.

        Canonical mode: the single analytics_root dir (all domains share it).
        Legacy mode: <webapps_root>/clients/<domain>/analytics/events.
        """
        normalized = _normalize_domain(domain)
        if self._analytics_root is not None:
            return self._analytics_root
        return (
            (self._legacy_webapps_root or LEGACY_WEBAPPS_ROOT)
            / "clients"
            / normalized
            / "analytics"
            / "events"
        )

    def resolve_events_file(self, *, domain: object, year_month: object) -> AnalyticsEventPathResolution:
        normalized_domain = _normalize_domain(domain)
        normalized_year_month = _normalize_year_month(year_month)

        if self._analytics_root is not None:
            analytics_root = self._analytics_root
            events_file = analytics_root / _events_filename(normalized_domain, normalized_year_month)
        else:
            # Legacy fallback.
            webapps_root = self._legacy_webapps_root or LEGACY_WEBAPPS_ROOT
            analytics_root = webapps_root / "clients" / normalized_domain / "analytics"
            events_file = analytics_root / "events" / f"{normalized_year_month}.ndjson"

        return AnalyticsEventPathResolution(
            domain=normalized_domain,
            year_month=normalized_year_month,
            analytics_root=analytics_root,
            events_file=events_file,
            warnings=(),
        )

    def iter_domain_event_files(self, domain: str) -> list[Path]:
        """Return all *.ndjson files for one domain, newest-first by filename.

        In canonical mode, files match ``analytics.<domain>.events.*.ndjson``
        directly in the analytics_root; in legacy mode, files live under
        ``<webapps>/clients/<domain>/analytics/events/*.ndjson``.
        """
        normalized = _normalize_domain(domain)
        if self._analytics_root is not None:
            if not self._analytics_root.exists():
                return []
            pattern = f"analytics.{normalized}.events.*.ndjson"
            return sorted(self._analytics_root.glob(pattern), reverse=True)
        events_dir = self.domain_events_dir(normalized)
        if not events_dir.exists() or not events_dir.is_dir():
            return []
        return sorted(events_dir.glob("*.ndjson"), reverse=True)

    def discover_domains(self) -> list[str]:
        """Discover all domains that have at least one events NDJSON.

        Canonical mode: parse the domain out of file names
        ``analytics.<domain>.events.<YYYY-MM>.ndjson``.
        Legacy mode: list ``<webapps>/clients/*/analytics/events``.
        """
        out: set[str] = set()
        if self._analytics_root is not None:
            if not self._analytics_root.exists():
                return []
            for path in self._analytics_root.glob("analytics.*.events.*.ndjson"):
                # filename format: analytics.<domain>.events.<YM>.ndjson
                stem = path.name.removeprefix("analytics.")
                # Strip the trailing ".events.<YM>.ndjson" — the YM is YYYY-MM
                # so we know the last 5 dot-segments end at <YM>.ndjson:
                #   <domain>.events.<YM>.ndjson  →  drop last 3 dot-segments
                parts = stem.split(".")
                if len(parts) < 4 or parts[-4 + 0]:
                    pass
                # Robust: domain = everything before the literal '.events.'
                idx = stem.rfind(".events.")
                if idx > 0:
                    out.add(stem[:idx])
            return sorted(out)
        root = self._legacy_webapps_root or LEGACY_WEBAPPS_ROOT
        clients = root / "clients"
        if not clients.exists():
            return []
        for child in clients.iterdir():
            if (child / "analytics" / "events").is_dir():
                out.add(child.name.lower())
        return sorted(out)

    def append_payload(
        self,
        *,
        domain: object,
        year_month: object,
        payload: dict[str, Any],
    ) -> AnalyticsEventPathResolution:
        if not isinstance(payload, dict):
            raise ValueError("analytics payload must be a dict")
        resolution = self.resolve_events_file(domain=domain, year_month=year_month)
        resolution.events_file.parent.mkdir(parents=True, exist_ok=True)
        with resolution.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        return resolution
