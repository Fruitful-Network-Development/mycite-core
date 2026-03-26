from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _allowed_internal_roots() -> list[Path]:
    raw = _text(os.environ.get("MYCITE_INTERNAL_FILE_ROOTS"))
    if raw:
        roots = [Path(token).resolve() for token in raw.split(":") if _text(token)]
    else:
        roots = [Path("/srv/webapps/clients").resolve()]
    out: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        out.append(root)
    return out


def _is_path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _is_allowed_path(path: Path) -> bool:
    return any(_is_path_within(path, root) for root in _allowed_internal_roots())


def detect_content_kind(path: Path, *, kind_hint: str = "") -> str:
    hint = _text(kind_hint).lower()
    if hint in {"json", "ndjson", "nginx_access_log", "nginx_error_log", "text"}:
        return hint
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name == "access.log":
        return "nginx_access_log"
    if name == "error.log":
        return "nginx_error_log"
    if suffix == ".ndjson":
        return "ndjson"
    if suffix == ".json":
        return "json"
    return "text"


def derive_client_analytics_paths(site_root: str, *, now_utc: datetime | None = None) -> dict[str, Path]:
    root = Path(_text(site_root)).resolve()
    client_root = root.parent
    analytics_root = (client_root / "analytics").resolve()
    now = now_utc or datetime.now(timezone.utc)
    month_token = f"{now.year:04d}-{now.month:02d}"
    canonical_events = (analytics_root / "events" / f"{month_token}.ndjson").resolve()
    legacy_events = (analytics_root / "evnts" / f"{month_token}.ndjson").resolve()
    return {
        "client_root": client_root,
        "analytics_root": analytics_root,
        "access_log": (analytics_root / "nginx" / "access.log").resolve(),
        "error_log": (analytics_root / "nginx" / "error.log").resolve(),
        "events_file": canonical_events,
        "events_file_candidates": [canonical_events, legacy_events],
        "events_file_legacy": legacy_events,
        "events_month_token": Path(f"{month_token}.ndjson"),
    }


_NGINX_COMBINED_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)\s+"(?P<referrer>[^"]*)"\s+"(?P<ua>[^"]*)"'
)
_NGINX_COMMON_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)'
)
_REQUEST_RE = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+(?P<protocol>HTTP/\d\.\d)$")
_ASSET_EXTENSIONS = {
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


def _parse_nginx_timestamp(value: str) -> datetime | None:
    token = _text(value)
    if not token:
        return None
    try:
        return datetime.strptime(token, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def _parse_any_timestamp(value: Any) -> datetime | None:
    token = _text(value)
    if not token:
        return None
    try:
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        parsed = datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return _parse_nginx_timestamp(token)


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


def _is_bot_user_agent(user_agent: str) -> bool:
    lower = _text(user_agent).lower()
    if not lower:
        return False
    return any(token in lower for token in _BOT_TOKENS)


def _is_suspicious_probe(path_token: str) -> bool:
    lower = _text(path_token).lower()
    if not lower:
        return False
    return any(token in lower for token in _SUSPICIOUS_PATH_TOKENS)


def _strip_query(path_token: str) -> str:
    value = _text(path_token)
    if "?" in value:
        value = value.split("?", 1)[0]
    return value or "/"


def _is_asset_path(path_token: str) -> bool:
    token = _strip_query(path_token)
    lower = token.lower()
    for ext in _ASSET_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return "/assets/" in lower or "/static/" in lower


def _top_counts(source: dict[str, int], limit: int = 5) -> list[dict[str, Any]]:
    rows = sorted(source.items(), key=lambda item: (-int(item[1]), str(item[0])))
    return [{"key": key, "count": int(count)} for key, count in rows[:limit]]


def _build_daily_series(day_counts: dict[str, int], *, days: int, now_utc: datetime) -> list[int]:
    out: list[int] = []
    for idx in range(days - 1, -1, -1):
        day = (now_utc - timedelta(days=idx)).date().isoformat()
        out.append(int(day_counts.get(day) or 0))
    return out


def _summarize_nginx_access(lines: list[str], *, now_utc: datetime) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    requests_24h = 0
    requests_7d = 0
    requests_30d = 0
    unique_ips_30d: set[str] = set()
    bot_count = 0
    probe_count = 0
    page_traffic_count = 0
    asset_traffic_count = 0
    page_counts: dict[str, int] = {}
    referrer_counts: dict[str, int] = {}
    error_route_counts: dict[str, int] = {}
    suspicious_examples: dict[str, int] = {}
    day_counts: dict[str, int] = {}
    last_seen: datetime | None = None
    robots_seen = False
    robots_404 = 0
    sitemap_seen = False
    sitemap_404 = 0
    parse_errors = 0

    for line in lines:
        match = _NGINX_COMBINED_RE.match(line)
        if not match:
            match = _NGINX_COMMON_RE.match(line)
        if not match:
            parse_errors += 1
            continue
        ip = _text(match.group("ip"))
        ts = _parse_nginx_timestamp(match.group("ts"))
        request_line = _text(match.group("request"))
        status_token = _text(match.group("status"))
        referrer = _text(match.groupdict().get("referrer"))
        ua = _text(match.groupdict().get("ua"))
        if ts is not None and (last_seen is None or ts > last_seen):
            last_seen = ts

        req_match = _REQUEST_RE.match(request_line)
        method = _text(req_match.group("method")) if req_match else ""
        path_token = _strip_query(_text(req_match.group("path")) if req_match else "")
        _ = method
        try:
            status_code = int(status_token)
        except Exception:
            status_code = 0
        bucket = _status_bucket(status_code)
        status_counts[bucket] = int(status_counts.get(bucket) or 0) + 1

        if ts is not None:
            age = now_utc - ts
            if age <= timedelta(hours=24):
                requests_24h += 1
            if age <= timedelta(days=7):
                requests_7d += 1
            if age <= timedelta(days=30):
                requests_30d += 1
                if ip:
                    unique_ips_30d.add(ip)
            day_counts[ts.date().isoformat()] = int(day_counts.get(ts.date().isoformat()) or 0) + 1

        is_bot = _is_bot_user_agent(ua)
        if is_bot:
            bot_count += 1
        is_probe = _is_suspicious_probe(path_token)
        if is_probe:
            probe_count += 1
            suspicious_examples[path_token] = int(suspicious_examples.get(path_token) or 0) + 1

        is_asset = _is_asset_path(path_token)
        if is_asset:
            asset_traffic_count += 1
        else:
            page_traffic_count += 1
            if path_token:
                page_counts[path_token] = int(page_counts.get(path_token) or 0) + 1
        if referrer and referrer != "-":
            referrer_counts[referrer] = int(referrer_counts.get(referrer) or 0) + 1
        if 400 <= status_code:
            error_route_counts[path_token or "/"] = int(error_route_counts.get(path_token or "/") or 0) + 1

        if path_token == "/robots.txt":
            robots_seen = True
            if status_code == 404:
                robots_404 += 1
        if path_token == "/sitemap.xml":
            sitemap_seen = True
            if status_code == 404:
                sitemap_404 += 1

    total = len(lines)
    bot_share = float(bot_count / total) if total else 0.0
    return {
        "line_count": total,
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
        "bot_share": bot_share,
        "bot_requests": int(bot_count),
        "suspicious_probe_count": int(probe_count),
        "top_pages": _top_counts(page_counts, limit=8),
        "top_referrers": _top_counts(referrer_counts, limit=8),
        "top_error_routes": _top_counts(error_route_counts, limit=8),
        "suspicious_probe_examples": _top_counts(suspicious_examples, limit=8),
        "asset_vs_page": {
            "asset_requests": int(asset_traffic_count),
            "page_requests": int(page_traffic_count),
        },
        "trend_7d": _build_daily_series(day_counts, days=7, now_utc=now_utc),
        "trend_30d": _build_daily_series(day_counts, days=30, now_utc=now_utc),
        "robots_requests_seen": bool(robots_seen),
        "robots_404_count": int(robots_404),
        "sitemap_requests_seen": bool(sitemap_seen),
        "sitemap_404_count": int(sitemap_404),
        "parse_error_count": int(parse_errors),
    }


def _summarize_nginx_error(lines: list[str], *, now_utc: datetime) -> dict[str, Any]:
    severity_counts: dict[str, int] = {}
    last_seen: datetime | None = None
    for line in lines:
        lower = line.lower()
        level = ""
        for token in ("[emerg]", "[alert]", "[crit]", "[error]", "[warn]", "[notice]", "[info]", "[debug]"):
            if token in lower:
                level = token.strip("[]")
                break
        if not level:
            for token in (" emerg ", " alert ", " crit ", " error ", " warn ", " notice ", " info ", " debug "):
                if token in lower:
                    level = token.strip()
                    break
        if not level:
            level = "unknown"
        severity_counts[level] = int(severity_counts.get(level) or 0) + 1
        match = re.search(r"\[(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]", line)
        if match:
            try:
                parsed = datetime.strptime(match.group("ts"), "%Y/%m/%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if last_seen is None or parsed > last_seen:
                    last_seen = parsed
            except Exception:
                pass
    _ = now_utc
    return {
        "line_count": len(lines),
        "severity_counts": severity_counts,
        "last_seen_utc": last_seen.isoformat() if last_seen else "",
    }


def _event_type(payload: dict[str, Any]) -> str:
    for key in ("event_type", "event", "type", "name", "action"):
        token = _text(payload.get(key))
        if token:
            return token.lower()
    return "unknown"


def _event_timestamp(payload: dict[str, Any]) -> datetime | None:
    for key in ("timestamp", "ts", "occurred_at", "created_at", "time"):
        token = payload.get(key)
        parsed = _parse_any_timestamp(token)
        if parsed is not None:
            return parsed
    return None


def _event_session_id(payload: dict[str, Any]) -> str:
    for key in ("session_id", "sessionId", "sid", "client_id", "clientId", "visitor_id"):
        token = _text(payload.get(key))
        if token:
            return token
    return ""


def _summarize_ndjson_events(lines: list[str], *, now_utc: datetime) -> dict[str, Any]:
    event_type_counts: dict[str, int] = {}
    session_ids: set[str] = set()
    invalid_line_count = 0
    last_seen: datetime | None = None
    requests_24h = 0
    requests_7d = 0
    requests_30d = 0
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
            requests_24h += 1
        if age <= timedelta(days=7):
            requests_7d += 1
        if age <= timedelta(days=30):
            requests_30d += 1
        day_counts[ts.date().isoformat()] = int(day_counts.get(ts.date().isoformat()) or 0) + 1

    return {
        "line_count": len(lines),
        "event_type_counts": event_type_counts,
        "session_count_approx": int(len(session_ids)),
        "invalid_line_count": int(invalid_line_count),
        "last_seen_utc": last_seen.isoformat() if last_seen else "",
        "events_24h": int(requests_24h),
        "events_7d": int(requests_7d),
        "events_30d": int(requests_30d),
        "trend_7d": _build_daily_series(day_counts, days=7, now_utc=now_utc),
        "trend_30d": _build_daily_series(day_counts, days=30, now_utc=now_utc),
    }


@dataclass
class InternalFileReadResult:
    ok: bool
    path: str
    content_kind: str
    exists: bool
    readable: bool
    record_count: int
    summary: dict[str, Any]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "path": self.path,
            "content_kind": self.content_kind,
            "exists": bool(self.exists),
            "readable": bool(self.readable),
            "record_count": int(self.record_count),
            "summary": dict(self.summary or {}),
            "warnings": [str(item) for item in list(self.warnings or []) if _text(item)],
        }


def read_internal_file(path: Path, *, kind_hint: str = "", max_lines: int = 5000) -> InternalFileReadResult:
    token = path.resolve()
    kind = detect_content_kind(token, kind_hint=kind_hint)
    now_utc = datetime.now(timezone.utc)
    warnings: list[str] = []
    if not _is_allowed_path(token):
        return InternalFileReadResult(
            ok=False,
            path=str(token),
            content_kind=kind,
            exists=token.exists(),
            readable=False,
            record_count=0,
            summary={},
            warnings=["path is outside allowed internal roots"],
        )
    if not token.exists() or not token.is_file():
        return InternalFileReadResult(
            ok=False,
            path=str(token),
            content_kind=kind,
            exists=False,
            readable=False,
            record_count=0,
            summary={},
            warnings=["file is missing"],
        )
    try:
        text_payload = token.read_text(encoding="utf-8")
    except Exception as exc:
        return InternalFileReadResult(
            ok=False,
            path=str(token),
            content_kind=kind,
            exists=True,
            readable=False,
            record_count=0,
            summary={},
            warnings=[f"read failed: {exc}"],
        )

    if kind == "json":
        try:
            payload = json.loads(text_payload)
        except Exception as exc:
            return InternalFileReadResult(
                ok=False,
                path=str(token),
                content_kind=kind,
                exists=True,
                readable=True,
                record_count=0,
                summary={"kind": "invalid_json"},
                warnings=[f"json parse failed: {exc}"],
            )
        count = len(payload) if isinstance(payload, (list, dict)) else 1
        summary = {
            "kind": "json",
            "type": "object" if isinstance(payload, dict) else "list" if isinstance(payload, list) else "scalar",
            "last_seen_utc": datetime.fromtimestamp(token.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        return InternalFileReadResult(True, str(token), kind, True, True, int(count), summary, warnings)

    lines = [line for line in text_payload.splitlines() if _text(line)]
    if len(lines) > max_lines:
        warnings.append(f"line limit applied: {max_lines}")
        lines = lines[:max_lines]

    if kind == "ndjson":
        summary = _summarize_ndjson_events(lines, now_utc=now_utc)
        count = int(summary.get("line_count") or 0)
        return InternalFileReadResult(True, str(token), kind, True, True, int(count), summary, warnings)

    if kind == "nginx_access_log":
        summary = _summarize_nginx_access(lines, now_utc=now_utc)
        return InternalFileReadResult(True, str(token), kind, True, True, int(summary.get("line_count") or 0), summary, warnings)

    if kind == "nginx_error_log":
        summary = _summarize_nginx_error(lines, now_utc=now_utc)
        return InternalFileReadResult(True, str(token), kind, True, True, int(summary.get("line_count") or 0), summary, warnings)

    summary = {"kind": "text", "line_count": len(lines)}
    return InternalFileReadResult(True, str(token), kind, True, True, int(len(lines)), summary, warnings)


__all__ = [
    "InternalFileReadResult",
    "detect_content_kind",
    "derive_client_analytics_paths",
    "read_internal_file",
]

