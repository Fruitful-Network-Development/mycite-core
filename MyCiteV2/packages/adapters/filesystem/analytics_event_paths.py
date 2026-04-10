from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

DEFAULT_WEBAPPS_ROOT = Path("/srv/webapps")
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
    legacy_events_file: Path
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "year_month": self.year_month,
            "analytics_root": str(self.analytics_root),
            "events_file": str(self.events_file),
            "legacy_events_file": str(self.legacy_events_file),
            "warnings": list(self.warnings),
        }


class AnalyticsEventPathResolver:
    def __init__(self, webapps_root: str | Path = DEFAULT_WEBAPPS_ROOT) -> None:
        self._webapps_root = Path(webapps_root)

    def resolve_events_file(self, *, domain: object, year_month: object) -> AnalyticsEventPathResolution:
        normalized_domain = _normalize_domain(domain)
        normalized_year_month = _normalize_year_month(year_month)
        analytics_root = self._webapps_root / "clients" / normalized_domain / "analytics"
        events_file = analytics_root / "events" / f"{normalized_year_month}.ndjson"
        legacy_events_file = self._webapps_root / normalized_domain / "analytics" / "events" / f"{normalized_year_month}.ndjson"

        warnings: list[str] = []
        if legacy_events_file.exists():
            warnings.append("Legacy root analytics file exists and must not receive V2 events.")
        if str(events_file).startswith(str(self._webapps_root / normalized_domain)):
            warnings.append("Resolved analytics path points at the legacy root layout.")

        return AnalyticsEventPathResolution(
            domain=normalized_domain,
            year_month=normalized_year_month,
            analytics_root=analytics_root,
            events_file=events_file,
            legacy_events_file=legacy_events_file,
            warnings=tuple(warnings),
        )

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
