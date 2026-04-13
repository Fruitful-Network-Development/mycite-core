from __future__ import annotations

from typing import Any

from MyCiteV2.packages.ports.fnd_ebi_read_only import (
    FndEbiReadOnlyPort,
    FndEbiReadOnlyRequest,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_profile_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _dedupe_warnings(*sources: object) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for source in sources:
        if not isinstance(source, list):
            continue
        for item in source:
            token = _as_text(item)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


class FndEbiReadOnlyService:
    def __init__(self, read_port: FndEbiReadOnlyPort) -> None:
        self._read_port = read_port

    def read_surface(
        self,
        *,
        portal_tenant_id: str,
        portal_tenant_domain: object = "",
        selected_domain: object = "",
        year_month: object = "",
    ) -> dict[str, Any]:
        result = self._read_port.read_fnd_ebi_read_only(
            FndEbiReadOnlyRequest(
                portal_tenant_id=portal_tenant_id,
                selected_domain=selected_domain,
                year_month=year_month,
            )
        )

        payload = dict(result.source.payload) if result.source is not None else {}
        profiles = _as_profile_list(payload.get("profiles"))
        global_warnings = list(payload.get("warnings") or []) if isinstance(payload.get("warnings"), list) else []
        year_month_token = _as_text(payload.get("year_month") or year_month)
        requested_domain = _as_text(selected_domain or payload.get("selected_domain")).lower()
        tenant_domain = _as_text(portal_tenant_domain).lower()

        selected_profile: dict[str, Any] | None = None
        if requested_domain:
            selected_profile = next(
                (profile for profile in profiles if _as_text(profile.get("domain")).lower() == requested_domain),
                None,
            )
        if selected_profile is None and tenant_domain:
            selected_profile = next(
                (profile for profile in profiles if _as_text(profile.get("domain")).lower() == tenant_domain),
                None,
            )
        if selected_profile is None and profiles:
            selected_profile = profiles[0]

        selected = dict(selected_profile or {})
        traffic = dict(selected.get("traffic") or {})
        events_summary = dict(selected.get("events_summary") or {})
        errors_noise = dict(selected.get("errors_noise") or {})
        access_log = dict(selected.get("access_log") or {})
        error_log = dict(selected.get("error_log") or {})
        events_file = dict(selected.get("events_file") or {})
        freshness = dict(selected.get("freshness") or {})

        profile_cards = []
        for profile in profiles:
            domain = _as_text(profile.get("domain"))
            traffic_summary = dict(profile.get("traffic") or {})
            event_summary = dict(profile.get("events_summary") or {})
            profile_cards.append(
                {
                    "domain": domain,
                    "selected": bool(domain and domain == _as_text(selected.get("domain"))),
                    "health_label": _as_text(profile.get("health_label")) or "unknown",
                    "requests_30d": int(traffic_summary.get("requests_30d") or 0),
                    "real_page_requests_30d": int(traffic_summary.get("real_page_requests_30d") or 0),
                    "events_30d": int(event_summary.get("events_30d") or 0),
                    "unique_visitors_approx_30d": int(traffic_summary.get("unique_visitors_approx_30d") or 0),
                    "bot_share": float(traffic_summary.get("bot_share") or 0.0),
                    "warning_count": len(list(profile.get("warnings") or [])),
                }
            )

        overview = {
            "domain": _as_text(selected.get("domain")),
            "profile_file": _as_text(selected.get("profile_file")),
            "site_root": _as_text(selected.get("site_root")),
            "analytics_root": _as_text(selected.get("analytics_root")),
            "year_month": year_month_token,
            "health_label": _as_text(selected.get("health_label")) or "unavailable",
            "access_last_seen_utc": _as_text(freshness.get("access_last_seen_utc")),
            "error_last_seen_utc": _as_text(freshness.get("error_last_seen_utc")),
            "events_last_seen_utc": _as_text(freshness.get("events_last_seen_utc")),
        }
        files = {
            "profile_file": {
                "path": _as_text(selected.get("profile_file")),
                "exists": bool(selected),
                "readable": bool(selected),
                "state": "ready" if selected else "missing",
                "warnings": [],
            },
            "access_log": access_log,
            "error_log": error_log,
            "events_file": events_file,
        }
        warnings = _dedupe_warnings(global_warnings, list(selected.get("warnings") or []))
        if not selected:
            warnings = _dedupe_warnings(warnings, ["No FND-EBI profile matched the requested selection."])

        return {
            "profile_cards": profile_cards,
            "selected_domain": _as_text(selected.get("domain")),
            "overview": overview,
            "traffic": traffic,
            "events_summary": events_summary,
            "errors_noise": errors_noise,
            "files": files,
            "selected_profile": selected,
            "year_month": year_month_token,
            "warnings": warnings,
        }
