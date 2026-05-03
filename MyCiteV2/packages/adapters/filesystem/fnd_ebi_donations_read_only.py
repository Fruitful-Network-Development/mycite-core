from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from ...ports.fnd_ebi_donations_read_only import (
    FndEbiDonationsReadOnlyPort,
    FndEbiDonationsReadOnlyRequest,
    FndEbiDonationsReadOnlyResult,
    FndEbiDonationsReadOnlySource,
)

FND_EBI_PROFILE_SCHEMA = "mycite.service_tool.fnd_ebi.profile.v1"
DEFAULT_WEBAPPS_ROOT = Path("/srv/webapps")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_domain(value: object) -> str:
    token = _as_text(value).lower()
    if not token or "." not in token or "/" in token or "\\" in token or ".." in token:
        raise ValueError("fnd_ebi_donations profile domain must be a plain domain-like value")
    return token


def _parse_any_timestamp(value: object) -> datetime | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 0:
            return None
        if number > 10_000_000_000:
            number = number / 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except Exception:
            return None
    token = _as_text(value)
    if not token:
        return None
    if token.isdigit():
        return _parse_any_timestamp(int(token))
    try:
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        parsed = datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _build_daily_series(day_counts: dict[str, int], *, days: int, now_utc: datetime) -> list[int]:
    out: list[int] = []
    for idx in range(days - 1, -1, -1):
        day = (now_utc - timedelta(days=idx)).date().isoformat()
        out.append(int(day_counts.get(day) or 0))
    return out


def _donation_timestamp(record: dict[str, Any]) -> datetime | None:
    """Extract timestamp from a donation record using common field names."""
    for key in (
        "created_at",
        "timestamp",
        "ts",
        "completed_at",
        "received_at",
        "occurred_at",
        "time",
        "received_at_unix_ms",
    ):
        parsed = _parse_any_timestamp(record.get(key))
        if parsed is not None:
            return parsed
    return None


def _summarize_donations(lines: list[str], *, now_utc: datetime) -> dict[str, Any]:
    """Parse NDJSON donation records and return a summary dict.

    Provisional: total_amount_30d_usd and status_counts rely on `amount`,
    `currency`, and `status` fields. These are gracefully omitted (set to 0
    or empty) if absent, pending confirmation from FND-PayPal-CVCC-Donation-Form-2026-05-03.
    """
    record_count = 0
    invalid_line_count = 0
    last_seen: datetime | None = None
    donations_24h = 0
    donations_7d = 0
    donations_30d = 0
    day_counts: dict[str, int] = {}
    # Provisional: status_counts
    status_counts: dict[str, int] = {"COMPLETED": 0, "PENDING": 0, "FAILED": 0}
    # Provisional: total_amount_30d_usd
    total_amount_30d_usd: float = 0.0

    for line in lines:
        try:
            record = json.loads(line)
        except Exception:
            invalid_line_count += 1
            continue
        if not isinstance(record, dict):
            invalid_line_count += 1
            continue
        record_count += 1

        ts = _donation_timestamp(record)
        if ts is not None:
            if last_seen is None or ts > last_seen:
                last_seen = ts
            age = now_utc - ts
            if age <= timedelta(hours=24):
                donations_24h += 1
            if age <= timedelta(days=7):
                donations_7d += 1
            if age <= timedelta(days=30):
                donations_30d += 1
                # Provisional: accumulate amount if present and in USD
                currency = _as_text(record.get("currency", "")).upper()
                try:
                    amount_raw = record.get("amount")
                    if amount_raw is not None and (not currency or currency == "USD"):
                        total_amount_30d_usd += float(amount_raw)
                except Exception:
                    pass
            day_key = ts.date().isoformat()
            day_counts[day_key] = int(day_counts.get(day_key) or 0) + 1

        # Provisional: status field
        raw_status = _as_text(record.get("status", "")).upper()
        if raw_status in status_counts:
            status_counts[raw_status] = status_counts[raw_status] + 1

    return {
        "line_count": len(lines),
        "record_count": int(record_count),
        "invalid_line_count": int(invalid_line_count),
        "last_seen_utc": last_seen.isoformat() if last_seen else "",
        "donations_24h": int(donations_24h),
        "donations_7d": int(donations_7d),
        "donations_30d": int(donations_30d),
        # Provisional: status_counts and total_amount_30d_usd require confirmed
        # schema from FND-PayPal-CVCC-Donation-Form-2026-05-03.
        "status_counts": {k: int(v) for k, v in status_counts.items()},
        "total_amount_30d_usd": round(float(total_amount_30d_usd), 2),
        "trend_7d": _build_daily_series(day_counts, days=7, now_utc=now_utc),
        "trend_30d": _build_daily_series(day_counts, days=30, now_utc=now_utc),
    }


def _source_state(
    *,
    path: Path | None,
    exists: bool,
    readable: bool,
    record_count: int,
    source_warnings: list[str],
    empty_state: str = "empty",
) -> dict[str, Any]:
    if path is None:
        state = "unavailable"
    elif not exists:
        state = "missing"
    elif source_warnings and "file is unreadable" in source_warnings:
        state = "unreadable"
    elif record_count == 0:
        state = empty_state
    else:
        state = "ready"
    return {
        "path": "" if path is None else str(path),
        "exists": bool(exists),
        "readable": bool(readable),
        "record_count": int(record_count),
        "state": state,
        "warnings": list(source_warnings),
    }


class FilesystemFndEbiDonationsReadOnlyAdapter(FndEbiDonationsReadOnlyPort):
    def __init__(
        self,
        private_dir: str | Path,
        *,
        webapps_root: str | Path = DEFAULT_WEBAPPS_ROOT,
        now_utc: datetime | None = None,
    ) -> None:
        self._private_dir = Path(private_dir)
        self._webapps_root = Path(webapps_root)
        self._now_utc = now_utc

    def read_fnd_ebi_donations_read_only(
        self, request: FndEbiDonationsReadOnlyRequest
    ) -> FndEbiDonationsReadOnlyResult:
        normalized_request = (
            request
            if isinstance(request, FndEbiDonationsReadOnlyRequest)
            else FndEbiDonationsReadOnlyRequest.from_dict(request)
        )
        now_utc = self._now_utc or datetime.now(timezone.utc)
        warnings: list[str] = []
        profiles: list[dict[str, Any]] = []

        for profile_file in self._profile_files():
            payload = self._read_profile_payload(profile_file)
            if payload is None:
                continue
            snapshot = self._snapshot_for_profile(profile_file, payload, now_utc=now_utc)
            profiles.append(snapshot)

        if not profiles:
            warnings.append(
                "No FND-EBI profiles were available under private/utilities/tools/fnd-ebi."
            )

        return FndEbiDonationsReadOnlyResult(
            source=FndEbiDonationsReadOnlySource(
                payload={
                    "portal_tenant_id": normalized_request.portal_tenant_id,
                    "selected_domain": normalized_request.selected_domain,
                    "profiles": profiles,
                    "warnings": warnings,
                }
            )
        )

    def _profile_root(self) -> Path:
        return self._private_dir / "utilities" / "tools" / "fnd-ebi"

    def _profile_files(self) -> list[Path]:
        root = self._profile_root()
        if not root.exists() or not root.is_dir():
            return []

        candidates: list[Path] = []
        seen: set[Path] = set()
        for collection_path in sorted(root.glob("tool.*.fnd-ebi.json")):
            try:
                payload = json.loads(collection_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            members = payload.get("member_files") if isinstance(payload, dict) else None
            if not isinstance(members, list):
                continue
            for item in members:
                token = _as_text(item)
                if not token:
                    continue
                member_path = (root / token).resolve()
                if member_path.parent != root.resolve():
                    continue
                if member_path.name == "spec.json" or member_path.suffix != ".json":
                    continue
                if member_path not in seen:
                    seen.add(member_path)
                    candidates.append(member_path)

        if candidates:
            return candidates

        for candidate in sorted(root.glob("fnd-ebi.*.json")):
            if candidate.name == "spec.json":
                continue
            if candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
        return candidates

    def _read_profile_payload(self, path: Path) -> dict[str, Any] | None:
        if not path.exists() or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        if _as_text(payload.get("schema")) != FND_EBI_PROFILE_SCHEMA:
            return None
        return payload

    def _donations_path_for_profile(self, payload: dict[str, Any]) -> Path | None:
        """Return the log path if donations.enabled is True, else None."""
        donations_block = payload.get("donations")
        if not isinstance(donations_block, dict):
            return None
        if not donations_block.get("enabled"):
            return None
        log_path_token = _as_text(donations_block.get("log_path"))
        if not log_path_token:
            return None
        return Path(log_path_token)

    def _safe_text_lines(self, path: Path) -> tuple[bool, list[str], list[str]]:
        if not path.exists() or not path.is_file():
            return False, [], ["file is missing"]
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return True, [], ["file is unreadable"]
        lines = [line for line in text.splitlines() if line.strip()]
        return True, lines, []

    def _snapshot_for_profile(
        self,
        profile_path: Path,
        payload: dict[str, Any],
        *,
        now_utc: datetime,
    ) -> dict[str, Any]:
        domain = _normalize_domain(payload.get("domain"))
        log_path = self._donations_path_for_profile(payload)
        donations_enabled = log_path is not None
        warnings: list[str] = []

        if log_path is None:
            donations_log = _source_state(
                path=None,
                exists=False,
                readable=False,
                record_count=0,
                source_warnings=["donations not enabled for this profile"],
            )
            donations_summary: dict[str, Any] = {}
        else:
            exists, lines, file_warnings = self._safe_text_lines(log_path)
            summary = _summarize_donations(lines, now_utc=now_utc) if lines else {}
            donations_log = _source_state(
                path=log_path,
                exists=exists,
                readable="file is unreadable" not in file_warnings and log_path is not None,
                record_count=len(lines),
                source_warnings=file_warnings,
                empty_state="no_donations_written",
            )
            donations_summary = summary
            warnings.extend(file_warnings)
            if not exists:
                warnings.append("donations log file is missing")

        warnings = list(dict.fromkeys(_as_text(item) for item in warnings if _as_text(item)))

        return {
            "domain": domain,
            "donations_enabled": bool(donations_enabled),
            "donations_log_path": "" if log_path is None else str(log_path),
            "donations_log": donations_log,
            "donations_summary": donations_summary,
            "warnings": warnings,
        }


__all__ = [
    "FND_EBI_PROFILE_SCHEMA",
    "FilesystemFndEbiDonationsReadOnlyAdapter",
]
