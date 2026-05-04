from __future__ import annotations

from typing import Any

from MyCiteV2.packages.modules.shared import as_text
from MyCiteV2.packages.modules.shared.warnings import dedupe_warnings
from MyCiteV2.packages.ports.fnd_ebi_donations_read_only import (
    FndEbiDonationsReadOnlyPort,
    FndEbiDonationsReadOnlyRequest,
)


class FndEbiDonationsReadOnlyService:
    def __init__(self, donations_port: FndEbiDonationsReadOnlyPort) -> None:
        self._donations_port = donations_port

    def read_donations_surface(
        self,
        *,
        portal_tenant_id: str,
        selected_domain: object = "",
    ) -> dict[str, Any]:
        result = self._donations_port.read_fnd_ebi_donations_read_only(
            FndEbiDonationsReadOnlyRequest(
                portal_tenant_id=portal_tenant_id,
                selected_domain=selected_domain,
            )
        )

        payload = dict(result.source.payload) if result.source is not None else {}
        profiles: list[dict[str, Any]] = []
        raw_profiles = payload.get("profiles")
        if isinstance(raw_profiles, list):
            for item in raw_profiles:
                if isinstance(item, dict):
                    profiles.append(item)

        global_warnings = list(payload.get("warnings") or []) if isinstance(payload.get("warnings"), list) else []
        requested_domain = as_text(selected_domain or payload.get("selected_domain")).lower()

        selected_profile: dict[str, Any] | None = None
        if requested_domain:
            selected_profile = next(
                (p for p in profiles if as_text(p.get("domain")).lower() == requested_domain),
                None,
            )
        if selected_profile is None and profiles:
            selected_profile = profiles[0]

        selected = dict(selected_profile or {})
        donations_log = dict(selected.get("donations_log") or {})
        donations_summary = dict(selected.get("donations_summary") or {})
        donations_enabled = bool(selected.get("donations_enabled", False))
        profile_warnings = list(selected.get("warnings") or [])

        warnings = dedupe_warnings(global_warnings, profile_warnings)
        if not selected:
            warnings = dedupe_warnings(
                warnings, ["No FND-EBI donations profile matched the requested selection."]
            )

        return {
            "selected_domain": as_text(selected.get("domain")),
            "donations_enabled": donations_enabled,
            "donations_log": donations_log,
            "donations_summary": donations_summary,
            "warnings": warnings,
        }
