from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any

from MyCiteV2.packages.ports.fnd_ebi_read_only import (
    FndEbiReadOnlyPort,
    FndEbiReadOnlyRequest,
    FndEbiReadOnlyResult,
    FndEbiReadOnlySource,
)

FND_EBI_PROFILE_SCHEMA = "mycite.service_tool.fnd_ebi.profile.v1"
DEFAULT_WEBAPPS_ROOT = Path("/srv/webapps")

_NGINX_COMBINED_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)\s+"(?P<referrer>[^"]*)"\s+"(?P<ua>[^"]*)"'
)
_NGINX_COMMON_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)'
)
_REQUEST_RE = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+(?P<protocol>HTTP/\d\.\d)$")
_ASSET_EXTENSIONS = frozenset(
    {
        ".css",
        ".js",
        ".mjs",
        ".map",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".pdf",
        ".zip",
        ".xml",
        ".txt",
    }
)
_BOT_TOKENS = (
    "bot",
    "crawler",
    "spider",
    "ahrefs",
    "googlebot",
    "applebot",
    "bingbot",
    "gptbot",
    "oai-searchbot",
    "censys",
    "curl/",
    "python-requests",
    "go-http-client",
)
_SUSPICIOUS_PATH_TOKENS = (
    "/wp-admin",
    "/wp-content",
    "/wp-includes",
    "/wordpress/",
    "/xmlrpc.php",
    "/.env",
    "/phpinfo.php",
    "/phpmyadmin",
    "/boaform",
    "/cgi-bin",
    "/admin.php",
    "/manager/html",
    "/actuator",
    "/.git",
)
_ERROR_LEVEL_TOKENS = ("emerg", "alert", "crit", "error", "warn", "notice", "info", "debug")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_domain(value: object) -> str:
    token = _as_text(value).lower()
    if not token or "." not in token or "/" in token or "\\" in token or ".." in token:
        raise ValueError("fnd_ebi profile domain must be a plain domain-like value")
    return token


def _top_counts(source: dict[str, int], limit: int = 8) -> list[dict[str, Any]]:
    rows = sorted(source.items(), key=lambda item: (-int(item[1]), str(item[0])))
    return [{"key": key, "count": int(count)} for key, count in rows[:limit]]


def _build_daily_series(day_counts: dict[str, int], *, days: int, now_utc: datetime) -> list[int]:
    out: list[int] = []
    for idx in range(days - 1, -1, -1):
        day = (now_utc - timedelta(days=idx)).date().isoformat()
        out.append(int(day_counts.get(day) or 0))
    return out


def _status_bucket(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "other"


def _strip_query(path_token: str) -> str:
    value = _as_text(path_token)
    if "?" in value:
        value = value.split("?", 1)[0]
    return value or "/"


def _is_asset_path(path_token: str) -> bool:
    token = _strip_query(path_token).lower()
    for ext in _ASSET_EXTENSIONS:
        if token.endswith(ext):
            return True
    return "/assets/" in token or "/static/" in token


def _is_bot_user_agent(user_agent: str) -> bool:
    lower = _as_text(user_agent).lower()
    if not lower:
        return False
    return any(token in lower for token in _BOT_TOKENS)


def _is_suspicious_probe(path_token: str) -> bool:
    lower = _as_text(path_token).lower()
    if not lower:
        return False
    return any(token in lower for token in _SUSPICIOUS_PATH_TOKENS)


def _parse_nginx_timestamp(value: object) -> datetime | None:
    token = _as_text(value)
    if not token:
        return None
    try:
        return datetime.strptime(token, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
    except Exception:
        return None


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
        return _parse_nginx_timestamp(token)


def _event_type(payload: dict[str, Any]) -> str:
    for key in ("event_type", "event", "type", "name", "action"):
        token = _as_text(payload.get(key)).lower()
        if token:
            return token
    schema = _as_text(payload.get("schema")).lower()
    if schema.endswith(".web_event.v1"):
        return "web_event"
    return "unknown"


def _event_timestamp(payload: dict[str, Any]) -> datetime | None:
    for key in (
        "received_at_unix_ms",
        "received_at_ms",
        "timestamp",
        "ts",
        "occurred_at",
        "created_at",
        "time",
    ):
        parsed = _parse_any_timestamp(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _event_session_id(payload: dict[str, Any]) -> str:
    for key in (
        "session_id",
        "sessionId",
        "sid",
        "client_id",
        "clientId",
        "visitor_id",
        "request_id",
        "remote_addr",
    ):
        token = _as_text(payload.get(key))
        if token:
            return token
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        for key in ("session_id", "sessionId", "visitor_id", "visitorId"):
            token = _as_text(nested_payload.get(key))
            if token:
                return token
    return ""


def _summarize_nginx_access(lines: list[str], *, now_utc: datetime) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    requests_24h = 0
    requests_7d = 0
    requests_30d = 0
    requests_30d_window = 0
    unique_ips_30d: set[str] = set()
    bot_count = 0
    probe_count = 0
    page_traffic_count = 0
    asset_traffic_count = 0
    page_counts: dict[str, int] = {}
    human_page_counts: dict[str, int] = {}
    referrer_counts: dict[str, int] = {}
    error_route_counts: dict[str, int] = {}
    site_error_route_counts: dict[str, int] = {}
    asset_error_route_counts: dict[str, int] = {}
    suspicious_examples: dict[str, int] = {}
    probe_route_counts: dict[str, int] = {}
    day_counts: dict[str, int] = {}
    last_seen: datetime | None = None
    parse_errors = 0

    for line in lines:
        match = _NGINX_COMBINED_RE.match(line) or _NGINX_COMMON_RE.match(line)
        if not match:
            parse_errors += 1
            continue
        ip = _as_text(match.group("ip"))
        ts = _parse_nginx_timestamp(match.group("ts"))
        request_line = _as_text(match.group("request"))
        status_token = _as_text(match.group("status"))
        referrer = _as_text(match.groupdict().get("referrer"))
        ua = _as_text(match.groupdict().get("ua"))
        if ts is not None and (last_seen is None or ts > last_seen):
            last_seen = ts

        req_match = _REQUEST_RE.match(request_line)
        path_token = _strip_query(_as_text(req_match.group("path")) if req_match else "")
        try:
            status_code = int(status_token)
        except Exception:
            status_code = 0
        bucket = _status_bucket(status_code)
        status_counts[bucket] = int(status_counts.get(bucket) or 0) + 1

        age: timedelta | None = None
        if ts is not None:
            age = now_utc - ts
            if age <= timedelta(hours=24):
                requests_24h += 1
            if age <= timedelta(days=7):
                requests_7d += 1
            if age <= timedelta(days=30):
                requests_30d += 1
                requests_30d_window += 1
                if ip:
                    unique_ips_30d.add(ip)
            day_counts[ts.date().isoformat()] = int(day_counts.get(ts.date().isoformat()) or 0) + 1

        in_window_30d = age is not None and age <= timedelta(days=30)
        is_bot = _is_bot_user_agent(ua)
        if is_bot and in_window_30d:
            bot_count += 1
        is_probe = _is_suspicious_probe(path_token)
        if is_probe and in_window_30d:
            probe_count += 1
            suspicious_examples[path_token or "/"] = int(suspicious_examples.get(path_token or "/") or 0) + 1
            probe_route_counts[path_token or "/"] = int(probe_route_counts.get(path_token or "/") or 0) + 1

        is_asset = _is_asset_path(path_token)
        if in_window_30d:
            if is_asset:
                asset_traffic_count += 1
            else:
                page_traffic_count += 1
                if path_token:
                    page_counts[path_token] = int(page_counts.get(path_token) or 0) + 1
                    if not is_bot and not is_probe and status_code < 400:
                        human_page_counts[path_token] = int(human_page_counts.get(path_token) or 0) + 1
            if referrer and referrer != "-":
                referrer_counts[referrer] = int(referrer_counts.get(referrer) or 0) + 1
            if status_code >= 400:
                error_route_counts[path_token or "/"] = int(error_route_counts.get(path_token or "/") or 0) + 1
                if is_probe:
                    probe_route_counts[path_token or "/"] = int(probe_route_counts.get(path_token or "/") or 0) + 1
                elif is_asset:
                    asset_error_route_counts[path_token or "/"] = int(asset_error_route_counts.get(path_token or "/") or 0) + 1
                else:
                    site_error_route_counts[path_token or "/"] = int(site_error_route_counts.get(path_token or "/") or 0) + 1

    return {
        "line_count": len(lines),
        "last_seen_utc": last_seen.isoformat() if last_seen else "",
        "requests_24h": int(requests_24h),
        "requests_7d": int(requests_7d),
        "requests_30d": int(requests_30d),
        "unique_visitors_approx_30d": int(len(unique_ips_30d)),
        "response_breakdown": {
            "2xx": int(status_counts.get("2xx") or 0),
            "3xx": int(status_counts.get("3xx") or 0),
            "4xx": int(status_counts.get("4xx") or 0),
            "5xx": int(status_counts.get("5xx") or 0),
        },
        "bot_share": float(bot_count / requests_30d_window) if requests_30d_window else 0.0,
        "bot_requests": int(bot_count),
        "suspicious_probe_count": int(probe_count),
        "top_pages": _top_counts(human_page_counts, limit=8),
        "top_requested_paths": _top_counts(page_counts, limit=8),
        "top_referrers": _top_counts(referrer_counts, limit=8),
        "top_error_routes": _top_counts(error_route_counts, limit=8),
        "top_site_error_routes": _top_counts(site_error_route_counts, limit=8),
        "top_asset_error_routes": _top_counts(asset_error_route_counts, limit=8),
        "top_probe_routes": _top_counts(probe_route_counts, limit=8),
        "suspicious_probe_examples": _top_counts(suspicious_examples, limit=8),
        "asset_vs_page": {
            "asset_requests": int(asset_traffic_count),
            "page_requests": int(page_traffic_count),
        },
        "real_page_requests_30d": int(sum(human_page_counts.values())),
        "trend_7d": _build_daily_series(day_counts, days=7, now_utc=now_utc),
        "trend_30d": _build_daily_series(day_counts, days=30, now_utc=now_utc),
        "parse_error_count": int(parse_errors),
    }


def _summarize_nginx_error(lines: list[str]) -> dict[str, Any]:
    severity_counts: dict[str, int] = {}
    last_seen: datetime | None = None
    for line in lines:
        lower = line.lower()
        level = "unknown"
        for token in _ERROR_LEVEL_TOKENS:
            if f"[{token}]" in lower or f" {token} " in lower:
                level = token
                break
        severity_counts[level] = int(severity_counts.get(level) or 0) + 1
        match = re.search(r"\[(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]", line)
        if match:
            try:
                parsed = datetime.strptime(match.group("ts"), "%Y/%m/%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if last_seen is None or parsed > last_seen:
                    last_seen = parsed
            except Exception:
                pass
    return {
        "line_count": len(lines),
        "severity_counts": severity_counts,
        "last_seen_utc": last_seen.isoformat() if last_seen else "",
    }


def _summarize_ndjson_events(lines: list[str], *, now_utc: datetime) -> dict[str, Any]:
    event_type_counts: dict[str, int] = {}
    session_ids: set[str] = set()
    invalid_line_count = 0
    last_seen: datetime | None = None
    events_24h = 0
    events_7d = 0
    events_30d = 0
    day_counts: dict[str, int] = {}
    for line in lines:
        try:
            payload = json.loads(line)
        except Exception:
            invalid_line_count += 1
            continue
        if not isinstance(payload, dict):
            invalid_line_count += 1
            continue
        event_kind = _event_type(payload)
        event_type_counts[event_kind] = int(event_type_counts.get(event_kind) or 0) + 1
        sid = _event_session_id(payload)
        if sid:
            session_ids.add(sid)
        ts = _event_timestamp(payload)
        if ts is None:
            continue
        if last_seen is None or ts > last_seen:
            last_seen = ts
        age = now_utc - ts
        if age <= timedelta(hours=24):
            events_24h += 1
        if age <= timedelta(days=7):
            events_7d += 1
        if age <= timedelta(days=30):
            events_30d += 1
        day_counts[ts.date().isoformat()] = int(day_counts.get(ts.date().isoformat()) or 0) + 1

    return {
        "line_count": len(lines),
        "event_type_counts": event_type_counts,
        "session_count_approx": int(len(session_ids)),
        "invalid_line_count": int(invalid_line_count),
        "last_seen_utc": last_seen.isoformat() if last_seen else "",
        "events_24h": int(events_24h),
        "events_7d": int(events_7d),
        "events_30d": int(events_30d),
        "trend_7d": _build_daily_series(day_counts, days=7, now_utc=now_utc),
        "trend_30d": _build_daily_series(day_counts, days=30, now_utc=now_utc),
    }


class FilesystemFndEbiReadOnlyAdapter(FndEbiReadOnlyPort):
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

    def read_fnd_ebi_read_only(self, request: FndEbiReadOnlyRequest) -> FndEbiReadOnlyResult:
        normalized_request = request if isinstance(request, FndEbiReadOnlyRequest) else FndEbiReadOnlyRequest.from_dict(request)
        year_month = normalized_request.year_month or self._current_year_month()
        warnings: list[str] = []
        profiles: list[dict[str, Any]] = []
        for profile_file in self._profile_files():
            payload = self._read_profile_payload(profile_file)
            if payload is None:
                continue
            snapshot = self._snapshot_for_profile(profile_file, payload, year_month=year_month)
            profiles.append(snapshot)

        if not profiles:
            warnings.append("No FND-EBI profiles were available under private/utilities/tools/fnd-ebi.")
            return FndEbiReadOnlyResult(
                source=FndEbiReadOnlySource(
                    payload={
                        "portal_tenant_id": normalized_request.portal_tenant_id,
                        "selected_domain": normalized_request.selected_domain,
                        "year_month": year_month,
                        "profiles": [],
                        "warnings": warnings,
                    }
                )
            )

        return FndEbiReadOnlyResult(
            source=FndEbiReadOnlySource(
                payload={
                    "portal_tenant_id": normalized_request.portal_tenant_id,
                    "selected_domain": normalized_request.selected_domain,
                    "year_month": year_month,
                    "profiles": profiles,
                    "warnings": warnings,
                }
            )
        )

    def _current_year_month(self) -> str:
        now = self._now_utc or datetime.now(timezone.utc)
        return f"{now.year:04d}-{now.month:02d}"

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

    def _safe_text_lines(self, path: Path) -> tuple[bool, list[str], list[str]]:
        if not path.exists() or not path.is_file():
            return False, [], ["file is missing"]
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return True, [], ["file is unreadable"]
        lines = [line for line in text.splitlines() if line.strip()]
        return True, lines, []

    def _derive_paths(
        self,
        *,
        domain: str,
        site_root: str,
        year_month: str,
    ) -> tuple[dict[str, Path | None], list[str]]:
        warnings: list[str] = []
        site_root_token = _as_text(site_root)
        if not site_root_token:
            warnings.append("site_root is missing from the FND-EBI profile")
            return {
                "client_root": None,
                "analytics_root": None,
                "access_log": None,
                "error_log": None,
                "events_file": None,
                "events_file_legacy": None,
            }, warnings

        site_root_path = Path(site_root_token).resolve()
        client_root = site_root_path.parent
        allowed_root = (self._webapps_root / "clients").resolve()
        if client_root.name != domain:
            warnings.append("site_root domain does not match the profile domain")
        try:
            client_root.relative_to(allowed_root)
        except Exception:
            warnings.append("site_root resolves outside the allowed webapps/clients root")
            return {
                "client_root": client_root,
                "analytics_root": None,
                "access_log": None,
                "error_log": None,
                "events_file": None,
                "events_file_legacy": None,
            }, warnings

        analytics_root = client_root / "analytics"
        return {
            "client_root": client_root,
            "analytics_root": analytics_root,
            "access_log": analytics_root / "nginx" / "access.log",
            "error_log": analytics_root / "nginx" / "error.log",
            "events_file": analytics_root / "events" / f"{year_month}.ndjson",
            "events_file_legacy": analytics_root / "evnts" / f"{year_month}.ndjson",
        }, warnings

    def _source_state(
        self,
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

    def _snapshot_for_profile(
        self,
        profile_path: Path,
        payload: dict[str, Any],
        *,
        year_month: str,
    ) -> dict[str, Any]:
        now_utc = self._now_utc or datetime.now(timezone.utc)
        domain = _normalize_domain(payload.get("domain"))
        site_root = _as_text(payload.get("site_root"))
        derived, warnings = self._derive_paths(domain=domain, site_root=site_root, year_month=year_month)
        analytics_root = derived.get("analytics_root")
        access_path = derived.get("access_log")
        error_path = derived.get("error_log")
        events_path = derived.get("events_file")
        legacy_events_path = derived.get("events_file_legacy")

        selected_events_path = events_path
        if events_path is not None and (not events_path.exists()) and legacy_events_path is not None and legacy_events_path.exists():
            selected_events_path = legacy_events_path
            warnings.append("using legacy events path because the canonical current-month file is absent")

        access_exists, access_lines, access_warnings = self._safe_text_lines(access_path) if access_path is not None else (False, [], ["source path unavailable"])
        error_exists, error_lines, error_warnings = self._safe_text_lines(error_path) if error_path is not None else (False, [], ["source path unavailable"])
        events_exists, event_lines, event_warnings = self._safe_text_lines(selected_events_path) if selected_events_path is not None else (False, [], ["source path unavailable"])

        access_summary = _summarize_nginx_access(access_lines, now_utc=now_utc) if access_lines else {}
        error_summary = _summarize_nginx_error(error_lines) if error_lines else {}
        events_summary = _summarize_ndjson_events(event_lines, now_utc=now_utc) if event_lines else {}

        stale_cutoff = now_utc - timedelta(hours=72)
        access_last = _parse_any_timestamp(access_summary.get("last_seen_utc"))
        error_last = _parse_any_timestamp(error_summary.get("last_seen_utc"))
        events_last = _parse_any_timestamp(events_summary.get("last_seen_utc"))
        if access_exists and access_last is not None and access_last < stale_cutoff:
            warnings.append("access log is stale")
        if error_exists and error_last is not None and error_last < stale_cutoff:
            warnings.append("error log is stale")
        if events_exists and events_last is not None and events_last < stale_cutoff:
            warnings.append("events file is stale")
        if access_exists and not access_lines:
            warnings.append("access log exists but has no readable records")
        if events_exists and int(events_summary.get("events_30d") or 0) == 0:
            warnings.append("events file exists but has no recent events")
        if not events_exists:
            warnings.append("events file is missing for the selected month")

        access_state = self._source_state(
            path=access_path,
            exists=access_exists,
            readable="file is unreadable" not in access_warnings and access_path is not None,
            record_count=len(access_lines),
            source_warnings=access_warnings,
        )
        error_state = self._source_state(
            path=error_path,
            exists=error_exists,
            readable="file is unreadable" not in error_warnings and error_path is not None,
            record_count=len(error_lines),
            source_warnings=error_warnings,
        )
        events_state = self._source_state(
            path=selected_events_path,
            exists=events_exists,
            readable="file is unreadable" not in event_warnings and selected_events_path is not None,
            record_count=len(event_lines),
            source_warnings=event_warnings,
            empty_state="no_events_written",
        )

        warnings = list(dict.fromkeys(_as_text(item) for item in warnings if _as_text(item)))
        health_label = "ready" if not warnings and access_state["state"] == "ready" else "attention_required"

        return {
            "domain": domain,
            "profile_file": str(profile_path),
            "site_root": site_root,
            "analytics_root": "" if analytics_root is None else str(analytics_root),
            "year_month": year_month,
            "health_label": health_label,
            "access_log": access_state,
            "error_log": error_state,
            "events_file": events_state,
            "freshness": {
                "access_last_seen_utc": _as_text(access_summary.get("last_seen_utc")),
                "error_last_seen_utc": _as_text(error_summary.get("last_seen_utc")),
                "events_last_seen_utc": _as_text(events_summary.get("last_seen_utc")),
            },
            "traffic": {
                "requests_24h": int(access_summary.get("requests_24h") or 0),
                "requests_7d": int(access_summary.get("requests_7d") or 0),
                "requests_30d": int(access_summary.get("requests_30d") or 0),
                "unique_visitors_approx_30d": int(access_summary.get("unique_visitors_approx_30d") or 0),
                "response_breakdown": dict(access_summary.get("response_breakdown") or {}),
                "bot_share": float(access_summary.get("bot_share") or 0.0),
                "bot_requests": int(access_summary.get("bot_requests") or 0),
                "suspicious_probe_count": int(access_summary.get("suspicious_probe_count") or 0),
                "real_page_requests_30d": int(access_summary.get("real_page_requests_30d") or 0),
                "asset_vs_page": dict(access_summary.get("asset_vs_page") or {}),
                "top_pages": list(access_summary.get("top_pages") or []),
                "top_requested_paths": list(access_summary.get("top_requested_paths") or []),
                "top_referrers": list(access_summary.get("top_referrers") or []),
                "trend_7d": list(access_summary.get("trend_7d") or []),
                "trend_30d": list(access_summary.get("trend_30d") or []),
            },
            "events_summary": {
                "events_24h": int(events_summary.get("events_24h") or 0),
                "events_7d": int(events_summary.get("events_7d") or 0),
                "events_30d": int(events_summary.get("events_30d") or 0),
                "session_count_approx": int(events_summary.get("session_count_approx") or 0),
                "event_type_counts": dict(events_summary.get("event_type_counts") or {}),
                "invalid_line_count": int(events_summary.get("invalid_line_count") or 0),
                "trend_7d": list(events_summary.get("trend_7d") or []),
                "trend_30d": list(events_summary.get("trend_30d") or []),
            },
            "errors_noise": {
                "error_severity_counts": dict(error_summary.get("severity_counts") or {}),
                "top_error_routes": list(access_summary.get("top_error_routes") or []),
                "top_site_error_routes": list(access_summary.get("top_site_error_routes") or []),
                "top_asset_error_routes": list(access_summary.get("top_asset_error_routes") or []),
                "top_probe_routes": list(access_summary.get("top_probe_routes") or []),
                "suspicious_probe_examples": list(access_summary.get("suspicious_probe_examples") or []),
            },
            "warnings": warnings,
        }


__all__ = [
    "FND_EBI_PROFILE_SCHEMA",
    "FilesystemFndEbiReadOnlyAdapter",
]
